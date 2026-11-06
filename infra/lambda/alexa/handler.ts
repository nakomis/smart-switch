/**
 * Alexa Smart Home (payload v3) handler: every Petro unit is a smart plug.
 *
 * Runs in eu-west-1 (Alexa's EU endpoint region); the units' Things, their commands topic and the
 * state table are in eu-west-2. It never pretends: a unit is switched only by publishing Fleet's own
 * relay command to petro/<thing>/commands, and the answer is the unit's next status, not the hope.
 *
 * - **Discover**: the Things with project=petro in this env that the linked account may see
 *   (Cognito group `petro`, or `petro-<name>` for one unit).
 * - **TurnOn / TurnOff**: refused while the unit's mode is a local override (on or off at its
 *   button), while a trip is latched, while it's busy (a relay cycle) or when it's offline; else the
 *   command, then up to CONFIRM_MS waiting for the status that shows the relay switched.
 * - **ReportState**: the latest status, with connectivity from its age.
 * - **AcceptGrant**: stores the account's event gateway tokens for the reporter's ChangeReports.
 */
import { randomUUID } from 'node:crypto';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { IoTClient, ListThingsCommand } from '@aws-sdk/client-iot';
import { IoTDataPlaneClient, PublishCommand } from '@aws-sdk/client-iot-data-plane';
import { DynamoDBDocumentClient, GetCommand, PutCommand } from '@aws-sdk/lib-dynamodb';
import { CognitoJwtVerifier } from 'aws-jwt-verify';
import { JwtExpiredError } from 'aws-jwt-verify/error';
import { acceptGrant, refreshGrantGroups } from './gateway';
import {
  canSee,
  endpointFor,
  env,
  isFresh,
  type Property,
  propertiesOf,
  type ReportedItem,
  reportedKey,
  type StatusItem,
  statusKey,
  THING_PATTERN,
} from './shared';

const HOME_REGION = process.env.HOME_REGION || 'eu-west-2';
const db = DynamoDBDocumentClient.from(new DynamoDBClient({ region: HOME_REGION }), {
  marshallOptions: { removeUndefinedValues: true },
});
const iot = new IoTClient({ region: HOME_REGION });
const iotData = new IoTDataPlaneClient({ region: HOME_REGION });

/** How long TurnOn/TurnOff waits for the unit's status to confirm (Alexa allows 8 s in all). */
export const CONFIRM_MS = Number(process.env.CONFIRM_MS) || 4000;
/** How often it looks for that status. (Both overridable for tests.) */
const POLL_MS = Number(process.env.POLL_MS) || 250;

// ── Types ────────────────────────────────────────────────────────────────────

interface DirectiveHeader {
  namespace: string;
  name: string;
  payloadVersion: string;
  messageId: string;
  correlationToken?: string;
}

interface Endpoint {
  endpointId: string;
  scope?: { type: string; token?: string };
  cookie?: Record<string, string>;
}

export interface AlexaEvent {
  directive: {
    header: DirectiveHeader;
    endpoint?: Endpoint;
    // biome-ignore lint/suspicious/noExplicitAny: directive payloads vary by interface
    payload: any;
  };
}

// biome-ignore lint/suspicious/noExplicitAny: Alexa response envelope
export type AlexaResponse = { event: any; context?: { properties: Property[] } };

class AlexaError extends Error {
  constructor(
    readonly type: string,
    message: string,
    readonly namespace = 'Alexa',
    readonly extra: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

// ── The linked account ───────────────────────────────────────────────────────

interface User {
  sub: string;
  groups: string[];
}

type Verifier = { verify(token: string): Promise<Record<string, unknown>> };
let verifier: Verifier | undefined;

/** For tests: use this verifier in place of Cognito's. */
export function setVerifier(v: Verifier | undefined): void {
  verifier = v;
}

/**
 * Verifies the Cognito access token Alexa got through account linking (signature, expiry, the
 * shared pool, token_use access, the Alexa app client) and returns its sub and groups.
 */
export const verifierConfig = () => ({
  userPoolId: env('USER_POOL_ID'),
  tokenUse: 'access' as const,
  clientId: env('ALEXA_CLIENT_ID'),
});

async function userFrom(token: string | undefined): Promise<User> {
  if (!token) throw new AlexaError('INVALID_AUTHORIZATION_CREDENTIAL', 'No bearer token');
  verifier ??= CognitoJwtVerifier.create(verifierConfig()) as unknown as Verifier;
  try {
    const payload = await verifier.verify(token);
    const groups = payload['cognito:groups'];
    return {
      sub: String(payload.sub),
      groups: Array.isArray(groups) ? groups.filter((g): g is string => typeof g === 'string') : [],
    };
  } catch (e) {
    // Alexa refreshes an expired token and retries; anything else is a bad token.
    if (e instanceof JwtExpiredError) throw new AlexaError('EXPIRED_AUTHORIZATION_CREDENTIAL', 'The bearer token has expired');
    console.warn('Token verification failed:', (e as Error).message);
    throw new AlexaError('INVALID_AUTHORIZATION_CREDENTIAL', 'Invalid bearer token');
  }
}

// ── Units ────────────────────────────────────────────────────────────────────

/** This env's Petro Things (Fleet's attribute project=petro, and the petro-{env}- name). */
async function things(): Promise<string[]> {
  const deployEnv = env('DEPLOY_ENV');
  const names: string[] = [];
  let nextToken: string | undefined;
  do {
    const res = await iot.send(
      new ListThingsCommand({ attributeName: 'project', attributeValue: 'petro', nextToken, maxResults: 250 }),
    );
    for (const t of res.things ?? []) {
      const m = t.thingName ? THING_PATTERN.exec(t.thingName) : null;
      if (m && m[1] === deployEnv) names.push(t.thingName as string);
    }
    nextToken = res.nextToken;
  } while (nextToken);
  return names.sort();
}

async function readStatus(thing: string): Promise<StatusItem | undefined> {
  const res = await db.send(new GetCommand({ TableName: env('TABLE_NAME'), Key: { pk: statusKey(thing) }, ConsistentRead: true }));
  return res.Item as StatusItem | undefined;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Why this unit won't take a relay command from Alexa now, as an ErrorResponse; or nothing. */
function refusal(item: StatusItem | undefined, thing: string): AlexaError | undefined {
  if (!isFresh(item)) return new AlexaError('ENDPOINT_UNREACHABLE', `${thing} has not reported for over 3 minutes`);
  const s = item!.status;
  if (s.trip) {
    return new AlexaError(
      'NOT_SUPPORTED_IN_CURRENT_MODE',
      `${thing} has tripped (${s.trip}) and is off; press its button to clear the trip`,
      'Alexa',
      { currentDeviceMode: 'OTHER' },
    );
  }
  if (s.mode !== 'auto' && s.mode !== 'on' && s.mode !== 'off') {
    // Not a mode the firmware sends (ctl_mode_name's "?" or a missing field): a fault, not the button.
    throw new Error(`${thing} reported an unknown mode ${JSON.stringify(s.mode)}`);
  }
  if (s.mode !== 'auto') {
    return new AlexaError(
      'NOT_SUPPORTED_IN_CURRENT_MODE',
      `${thing} is held ${s.mode} at its button; press it until the light is blue (auto) for Alexa to switch it`,
      'Alexa',
      { currentDeviceMode: 'OTHER' },
    );
  }
  if (s.remote === false) {
    return new AlexaError(
      'ENDPOINT_BUSY',
      s.cycle ? `${thing} is running a relay cycle` : `${thing} is not taking remote commands now`,
    );
  }
  return undefined;
}

// ── Responses ────────────────────────────────────────────────────────────────

function respond(d: AlexaEvent['directive'], name: 'Response' | 'StateReport', props: Property[]): AlexaResponse {
  return {
    event: {
      header: {
        namespace: 'Alexa',
        name,
        payloadVersion: '3',
        messageId: randomUUID(),
        correlationToken: d.header.correlationToken,
      },
      endpoint: d.endpoint,
      payload: {},
    },
    context: { properties: props },
  };
}

function errorResponse(d: AlexaEvent['directive'] | undefined, err: AlexaError): AlexaResponse {
  return {
    event: {
      header: {
        namespace: err.namespace,
        name: 'ErrorResponse',
        payloadVersion: '3',
        messageId: randomUUID(),
        correlationToken: d?.header?.correlationToken,
      },
      endpoint: d?.endpoint,
      payload: { type: err.type, message: err.message, ...err.extra },
    },
  };
}

// ── Directives ───────────────────────────────────────────────────────────────

async function discover(d: AlexaEvent['directive']): Promise<AlexaResponse> {
  let endpoints: ReturnType<typeof endpointFor>[] = [];
  let user: User | undefined;
  try {
    user = await userFrom(d.payload?.scope?.token);
  } catch {
    // Alexa's guidance: on a bad token during discovery, return no endpoints rather than an error.
  }
  if (user) {
    await refreshGrantGroups(db, user.sub, user.groups);
    const deployEnv = env('DEPLOY_ENV');
    const seen = user.groups;
    endpoints = (await things()).filter((t) => canSee(seen, t, deployEnv)).map(endpointFor);
  }
  return {
    event: {
      header: { namespace: 'Alexa.Discovery', name: 'Discover.Response', payloadVersion: '3', messageId: randomUUID() },
      payload: { endpoints },
    },
  };
}

async function onAcceptGrant(d: AlexaEvent['directive']): Promise<AlexaResponse> {
  try {
    const code = d.payload?.grant?.code;
    if (typeof code !== 'string' || !code) throw new Error('No grant code');
    const user = await userFrom(d.payload?.grantee?.token);
    await acceptGrant(db, code, user.sub, user.groups);
  } catch (e) {
    console.error('AcceptGrant failed:', (e as Error).message);
    throw new AlexaError('ACCEPT_GRANT_FAILED', 'Could not accept the grant', 'Alexa.Authorization');
  }
  return {
    event: {
      header: { namespace: 'Alexa.Authorization', name: 'AcceptGrant.Response', payloadVersion: '3', messageId: randomUUID() },
      payload: {},
    },
  };
}

async function reportState(d: AlexaEvent['directive'], thing: string): Promise<AlexaResponse> {
  const item = await readStatus(thing);
  if (!item) throw new AlexaError('ENDPOINT_UNREACHABLE', `${thing} has never reported`);
  return respond(d, 'StateReport', propertiesOf(item));
}

/** Time kept back from the Lambda's remaining time for the restore and the reply. */
export const REPLY_MARGIN_MS = 1000;

/** Just what setPower needs of the Lambda context. */
export interface Clock {
  getRemainingTimeInMillis(): number;
}

async function setPower(d: AlexaEvent['directive'], thing: string, on: boolean, clock?: Clock): Promise<AlexaResponse> {
  const want = on ? 'ON' : 'OFF';
  const before = await readStatus(thing);
  const refused = refusal(before, thing);
  if (refused) throw refused;
  if (before!.status.relay === on) return respond(d, 'Response', propertiesOf(before));

  // Alexa learns of this change from our Response: tell the reporter so it doesn't report it again.
  // On any failure from here on, what Alexa was last told goes back.
  const table = env('TABLE_NAME');
  const prior = await db.send(new GetCommand({ TableName: table, Key: { pk: reportedKey(thing) } }));
  const reportedBefore = prior?.Item as ReportedItem | undefined;
  await db.send(new PutCommand({ TableName: table, Item: { pk: reportedKey(thing), powerState: want, connectivity: 'OK' } }));

  try {
    const sentAt = Date.now();
    // The wait is elapsed time, and never runs into the Lambda's own timeout.
    const budget = Math.min(CONFIRM_MS, (clock?.getRemainingTimeInMillis() ?? Infinity) - REPLY_MARGIN_MS);
    // Fleet's own relay command, unchanged (firmware/README.md, Petro's commands).
    await iotData.send(
      new PublishCommand({ topic: `petro/${thing}/commands`, qos: 1, payload: Buffer.from(JSON.stringify({ command: 'relay', on })) }),
    );

    // The firmware publishes a status at once when the relay changes.
    while (Date.now() - sentAt < budget) {
      await sleep(POLL_MS);
      const now = await readStatus(thing);
      if (!now || now.receivedAt <= before!.receivedAt) continue;
      if (now.status.relay === on) return respond(d, 'Response', propertiesOf(now));
      const why = refusal(now, thing);
      if (why) throw why;
    }
    console.warn(`${thing} did not confirm relay ${want} within ${budget} ms of ${new Date(sentAt).toISOString()}`);
    throw new AlexaError('ENDPOINT_UNREACHABLE', `${thing} did not confirm the switch`);
  } catch (e) {
    try {
      await db.send(new PutCommand({ TableName: table, Item: reportedBefore ?? { pk: reportedKey(thing) } }));
    } catch (r) {
      console.error(`Could not restore reported#${thing}:`, (r as Error).message);
    }
    throw e;
  }
}

// ── Entry point ──────────────────────────────────────────────────────────────

export const handler = async (event: AlexaEvent, context?: Clock): Promise<AlexaResponse> => {
  const d = event?.directive;
  try {
    if (!d?.header?.namespace) throw new AlexaError('INVALID_DIRECTIVE', 'Malformed directive');
    const { namespace, name } = d.header;

    if (namespace === 'Alexa.Discovery' && name === 'Discover') return await discover(d);
    if (namespace === 'Alexa.Authorization' && name === 'AcceptGrant') return await onAcceptGrant(d);

    const known =
      (namespace === 'Alexa' && name === 'ReportState') ||
      (namespace === 'Alexa.PowerController' && (name === 'TurnOn' || name === 'TurnOff'));
    if (!known) throw new AlexaError('INVALID_DIRECTIVE', `Unsupported directive ${namespace}.${name}`);

    const user = await userFrom(d.endpoint?.scope?.token);
    await refreshGrantGroups(db, user.sub, user.groups);
    const thing = d.endpoint?.endpointId ?? '';
    if (!canSee(user.groups, thing, env('DEPLOY_ENV'))) {
      throw new AlexaError('NO_SUCH_ENDPOINT', `Unknown endpoint ${thing}`);
    }

    if (name === 'ReportState') return await reportState(d, thing);
    return await setPower(d, thing, name === 'TurnOn', context);
  } catch (e) {
    if (e instanceof AlexaError) return errorResponse(d, e);
    console.error('Unhandled error:', e);
    return errorResponse(d, new AlexaError('INTERNAL_ERROR', 'Internal error'));
  }
};
