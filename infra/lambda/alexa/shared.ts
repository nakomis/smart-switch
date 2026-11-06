/**
 * What the Alexa directive handler (eu-west-1) and the reporter (eu-west-2) share: Petro's status as
 * the firmware publishes it, how a status becomes Alexa properties, who may see which unit, and the
 * state table's keys.
 *
 * The firmware's status (firmware/README.md, "The status"; status_json.c) is the only source of
 * truth: nothing here sets a relay state that the unit hasn't reported.
 */
import { randomUUID } from 'node:crypto';

// ── The firmware's status ────────────────────────────────────────────────────

/** The fields of petro/<thing>/status this skill reads. Fleet's shape, unchanged. */
export interface PetroStatus {
  mode?: 'off' | 'on' | 'auto' | string;
  relay?: boolean;
  /** null, or the latched trip's cause: overcurrent, overtemp (PETRO-3), overcurrent_instant, meter_fault (PETRO-5). */
  trip?: string | null;
  /** Whether a relay command would be accepted now (auto, no trip, nothing else holding it). */
  remote?: boolean;
  bench?: boolean;
  cycle?: { done: number; n: number } | null;
  watts?: number | null;
  energy_kwh?: number | null;
  reason?: string;
  version?: string;
}

/** The status item: the latest status, with the Thing and the time IoT Core received it (ms). */
export interface StatusItem {
  pk: string;
  thing: string;
  receivedAt: number;
  status: PetroStatus;
}

/**
 * The firmware publishes a heartbeat every 60 s (and at once on any change): three missed
 * heartbeats mean the unit is offline.
 */
export const STALE_MS = 3 * 60 * 1000;

export const isFresh = (item: StatusItem | undefined, now = Date.now()) =>
  !!item && typeof item.receivedAt === 'number' && now - item.receivedAt < STALE_MS;

// ── The state table (eu-west-2) ──────────────────────────────────────────────

export const statusKey = (thing: string) => `status#${thing}`;
/** What Alexa was last told about a unit, so the reporter sends a ChangeReport only on a change. */
export const reportedKey = (thing: string) => `reported#${thing}`;
/** One per linked Alexa account that granted Send Alexa Events: its event gateway tokens. */
export const grantKey = (sub: string) => `grant#${sub}`;

export interface ReportedItem {
  pk: string;
  powerState?: 'ON' | 'OFF';
  connectivity?: 'OK' | 'UNREACHABLE';
}

export interface GrantItem {
  pk: string;
  sub: string;
  groups: string[];
  /** When `groups` was last read from the account's token (ms): at AcceptGrant and every directive. */
  groupsAt?: number;
  accessToken: string;
  refreshToken: string;
  /** ms since the epoch. */
  expiresAt: number;
}

// ── Units and who may see them ───────────────────────────────────────────────

/** Thing name for a unit, as infra/lib/device-stack.ts: petro-{env}-{name}. */
export const THING_PATTERN = /^petro-(sandbox|prod)-(b[1-9][0-9]*)$/;

/** The Cognito group that sees every unit. */
export const ALL_UNITS_GROUP = 'petro';
/** The Cognito group that sees one unit only, e.g. petro-b5 (for the certification account). */
export const unitGroup = (name: string) => `petro-${name}`;

export const unitName = (thing: string) => THING_PATTERN.exec(thing)?.[2];

/**
 * A linked account sees a unit only if its Cognito user is in `petro` (all units) or in
 * `petro-<name>` (that unit). The shared pool has other projects' users, and the skill is public:
 * being able to sign in is not enough to switch Martin's mains.
 */
export function canSee(groups: readonly string[], thing: string, deployEnv: string): boolean {
  const m = THING_PATTERN.exec(thing);
  if (!m || m[1] !== deployEnv) return false;
  return groups.includes(ALL_UNITS_GROUP) || groups.includes(unitGroup(m[2]));
}

/**
 * A grant's groups are trusted for this long after they were last read from a token. The Alexa app
 * sends a ReportState whenever it's opened (and every directive refreshes them), so a user who's
 * been taken out of the groups stops getting ChangeReports within this time at most.
 */
export const GRANT_GROUPS_MAX_AGE_MS = 7 * 24 * 3600 * 1000;

/** Whether the reporter may tell this grant's account about this unit. */
export function grantMaySee(grant: GrantItem, thing: string, deployEnv: string, now = Date.now()): boolean {
  if (typeof grant.groupsAt !== 'number' || now - grant.groupsAt > GRANT_GROUPS_MAX_AGE_MS) return false;
  return canSee(grant.groups ?? [], thing, deployEnv);
}

// ── Alexa ────────────────────────────────────────────────────────────────────

export interface Property {
  namespace: string;
  name: string;
  value: unknown;
  timeOfSample: string;
  uncertaintyInMilliseconds: number;
}

const iso = (ms: number) => new Date(ms).toISOString();

export const powerStateOf = (s: PetroStatus | undefined): 'ON' | 'OFF' | undefined =>
  typeof s?.relay === 'boolean' ? (s.relay ? 'ON' : 'OFF') : undefined;

export const powerProperty = (powerState: 'ON' | 'OFF', sampledAt: number): Property => ({
  namespace: 'Alexa.PowerController',
  name: 'powerState',
  value: powerState,
  timeOfSample: iso(sampledAt),
  uncertaintyInMilliseconds: 0,
});

export const connectivityProperty = (ok: boolean, sampledAt: number): Property => ({
  namespace: 'Alexa.EndpointHealth',
  name: 'connectivity',
  value: { value: ok ? 'OK' : 'UNREACHABLE' },
  timeOfSample: iso(sampledAt),
  uncertaintyInMilliseconds: 0,
});

/** Every property for a unit from its status item: the relay as last reported, and its health now. */
export function propertiesOf(item: StatusItem | undefined, now = Date.now()): Property[] {
  const props: Property[] = [];
  const power = powerStateOf(item?.status);
  if (item && power) props.push(powerProperty(power, item.receivedAt));
  props.push(connectivityProperty(isFresh(item, now), now));
  return props;
}

/**
 * The discovery entry for one unit. Petro's metering isn't offered: Alexa's energy interfaces
 * (Alexa.DeviceUsage.Meter and .Estimation) are en-US only, and this skill is en-GB (see
 * docs/alexa-setup.md, Energy). TODO(PETRO-8): add Alexa.DeviceUsage.Meter when Alexa supports it in
 * en-GB; status has energy_kwh to report from.
 */
export function endpointFor(thing: string) {
  const name = unitName(thing) ?? thing;
  return {
    endpointId: thing,
    manufacturerName: 'Nakomis',
    friendlyName: `Petro ${name}`,
    description: 'Petro smart plug',
    displayCategories: ['SMARTPLUG'],
    cookie: {},
    capabilities: [
      {
        type: 'AlexaInterface',
        interface: 'Alexa.PowerController',
        version: '3',
        properties: { supported: [{ name: 'powerState' }], proactivelyReported: true, retrievable: true },
      },
      {
        type: 'AlexaInterface',
        interface: 'Alexa.EndpointHealth',
        version: '3',
        properties: { supported: [{ name: 'connectivity' }], proactivelyReported: true, retrievable: true },
      },
      { type: 'AlexaInterface', interface: 'Alexa', version: '3' },
    ],
  };
}

export type ChangeCause = 'PHYSICAL_INTERACTION' | 'APP_INTERACTION' | 'RULE_TRIGGER' | 'PERIODIC_POLL';

/** A proactive ChangeReport for the Alexa event gateway. */
export function changeReport(
  thing: string,
  token: string,
  cause: ChangeCause,
  changed: Property[],
  unchanged: Property[],
) {
  return {
    event: {
      header: { namespace: 'Alexa', name: 'ChangeReport', messageId: randomUUID(), payloadVersion: '3' },
      endpoint: { scope: { type: 'BearerToken', token }, endpointId: thing },
      payload: { change: { cause: { type: cause }, properties: changed } },
    },
    context: { properties: unchanged },
  };
}

/** A required environment variable. */
export function env(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} is not set`);
  return v;
}
