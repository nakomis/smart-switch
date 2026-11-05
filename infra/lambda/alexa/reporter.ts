/**
 * The reporter (eu-west-2, beside IoT Core): keeps each unit's latest status for Alexa and tells
 * Alexa when it changes.
 *
 * - An IoT rule sends it every petro/<thing>/status (with the Thing and IoT's receive time added).
 *   It stores the status, then, if the relay or the unit's health differs from what Alexa was last
 *   told, sends a ChangeReport to every linked account that may see the unit: a press of the
 *   button, a trip, Fleet's relay command or the unit coming back.
 * - A schedule calls it every 2 minutes ({ "sweep": true }) to report units that have gone quiet as
 *   UNREACHABLE.
 *
 * The directive handler writes `reported#<thing>` before it switches a unit, so a change Alexa
 * asked for (already in its Response) isn't reported again.
 */
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, PutCommand, ScanCommand } from '@aws-sdk/lib-dynamodb';
import { grants, sendEvent } from './gateway';
import {
  type ChangeCause,
  canSee,
  changeReport,
  connectivityProperty,
  env,
  isFresh,
  type PetroStatus,
  type Property,
  powerProperty,
  powerStateOf,
  type ReportedItem,
  reportedKey,
  type StatusItem,
  statusKey,
  THING_PATTERN,
} from './shared';

const db = DynamoDBDocumentClient.from(new DynamoDBClient({}), {
  marshallOptions: { removeUndefinedValues: true },
});

/** What the IoT rule sends: the status, plus `thing` (topic(2)) and `receivedAt` (timestamp()). */
export type StatusEvent = PetroStatus & { thing?: string; receivedAt?: number };
export type SweepEvent = { sweep: true };

const table = () => env('TABLE_NAME');

async function get<T>(pk: string): Promise<T | undefined> {
  const res = await db.send(new GetCommand({ TableName: table(), Key: { pk } }));
  return res.Item as T | undefined;
}

/** Why the relay changed, from the previous status to this one. */
export function causeOf(prev: PetroStatus | undefined, next: PetroStatus): ChangeCause {
  if (next.trip && next.trip !== prev?.trip) return 'RULE_TRIGGER';
  // The mode is only ever changed at the unit (the button or the console), or set to off by Fleet;
  // on and off are the button's overrides.
  if (prev?.mode !== next.mode || next.mode === 'on' || next.mode === 'off') return 'PHYSICAL_INTERACTION';
  return 'APP_INTERACTION';
}

/**
 * Sends a ChangeReport about one unit to every account that may see it, and records what Alexa now
 * believes. `changed` is what's new; `unchanged` the rest of its properties.
 */
async function report(
  thing: string,
  cause: ChangeCause,
  changed: Property[],
  unchanged: Property[],
  next: ReportedItem,
): Promise<void> {
  const deployEnv = env('DEPLOY_ENV');
  let notConfigured = false;
  for (const grant of await grants(db)) {
    if (!canSee(grant.groups ?? [], thing, deployEnv)) continue;
    try {
      const result = await sendEvent(db, grant, (token) => changeReport(thing, token, cause, changed, unchanged));
      if (result === 'not-configured') notConfigured = true;
      if (result === 'grant-removed') console.log(`Removed the grant for ${grant.sub}: the account is gone`);
    } catch (e) {
      // One account's failure mustn't stop the others; the next change or heartbeat tries again.
      console.error(`ChangeReport for ${thing} to ${grant.sub} failed:`, (e as Error).message);
      return;
    }
    if (notConfigured) break;
  }
  if (notConfigured) {
    console.warn('The skill credentials secret is not set: no ChangeReports (docs/alexa-setup.md)');
    return;
  }
  await db.send(new PutCommand({ TableName: table(), Item: next }));
}

async function onStatus(event: StatusEvent): Promise<void> {
  const { thing, receivedAt, ...status } = event;
  if (typeof thing !== 'string' || !THING_PATTERN.test(thing)) {
    console.warn('Status without a Petro Thing name; ignored');
    return;
  }
  const at = typeof receivedAt === 'number' ? receivedAt : Date.now();
  const prev = await get<StatusItem>(statusKey(thing));
  if (prev && prev.receivedAt > at) return; // an older message arriving late
  const item: StatusItem = { pk: statusKey(thing), thing, receivedAt: at, status };
  await db.send(new PutCommand({ TableName: table(), Item: item }));

  const power = powerStateOf(status);
  if (!power) return;
  const reported = await get<ReportedItem>(reportedKey(thing));
  const changed: Property[] = [];
  const unchanged: Property[] = [];
  (reported?.powerState === power ? unchanged : changed).push(powerProperty(power, at));
  (reported?.connectivity === 'OK' ? unchanged : changed).push(connectivityProperty(true, at));
  if (changed.length === 0) return;
  const cause = changed.some((p) => p.namespace === 'Alexa.PowerController')
    ? causeOf(prev?.status, status)
    : 'PERIODIC_POLL';
  await report(thing, cause, changed, unchanged, { pk: reportedKey(thing), powerState: power, connectivity: 'OK' });
}

async function sweep(now = Date.now()): Promise<void> {
  let start: Record<string, unknown> | undefined;
  const items: StatusItem[] = [];
  do {
    const res = await db.send(
      new ScanCommand({
        TableName: table(),
        FilterExpression: 'begins_with(pk, :p)',
        ExpressionAttributeValues: { ':p': 'status#' },
        ExclusiveStartKey: start,
      }),
    );
    items.push(...((res.Items ?? []) as StatusItem[]));
    start = res.LastEvaluatedKey;
  } while (start);

  for (const item of items) {
    if (isFresh(item, now)) continue;
    const reported = await get<ReportedItem>(reportedKey(item.thing));
    if (reported?.connectivity === 'UNREACHABLE') continue;
    const power = powerStateOf(item.status);
    const unchanged = power ? [powerProperty(power, item.receivedAt)] : [];
    await report(item.thing, 'PERIODIC_POLL', [connectivityProperty(false, now)], unchanged, {
      pk: reportedKey(item.thing),
      powerState: power,
      connectivity: 'UNREACHABLE',
    });
  }
}

export const handler = async (event: StatusEvent | SweepEvent): Promise<void> => {
  if ((event as SweepEvent)?.sweep === true) return sweep();
  return onStatus(event as StatusEvent);
};
