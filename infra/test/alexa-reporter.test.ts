process.env.DEPLOY_ENV = 'sandbox';
process.env.HOME_REGION = 'eu-west-2';
process.env.TABLE_NAME = 'petro-alexa-sandbox';
process.env.SKILL_SECRET_ID = 'petro/sandbox/alexa/skill-messaging';

import { GetSecretValueCommand, SecretsManagerClient } from '@aws-sdk/client-secrets-manager';
import { DeleteCommand, DynamoDBDocumentClient, GetCommand, PutCommand, ScanCommand } from '@aws-sdk/lib-dynamodb';
import { mockClient } from 'aws-sdk-client-mock';
import { DEFAULT_EVENT_GATEWAY, LWA_TOKEN_URL, resetGatewayCache } from '../lambda/alexa/gateway';
import { causeOf, handler } from '../lambda/alexa/reporter';
import type { GrantItem, StatusItem } from '../lambda/alexa/shared';

const ddb = mockClient(DynamoDBDocumentClient);
const sm = mockClient(SecretsManagerClient);

const THING = 'petro-sandbox-b1';
const HOUR = 3600_000;

const grant = (sub: string, groups: string[], expiresAt = Date.now() + HOUR): GrantItem => ({
  pk: `grant#${sub}`,
  sub,
  groups,
  accessToken: `access-${sub}`,
  refreshToken: `refresh-${sub}`,
  expiresAt,
});

let fetchSpy: jest.SpyInstance;
const sent = () =>
  fetchSpy.mock.calls
    .filter(([url]) => url === DEFAULT_EVENT_GATEWAY)
    .map(([, init]) => ({ auth: init.headers.Authorization, body: JSON.parse(init.body) }));
const puts = () => ddb.commandCalls(PutCommand).map((c) => c.args[0].input.Item!);

const setGrants = (...items: GrantItem[]) =>
  ddb.on(ScanCommand, { ExpressionAttributeValues: { ':p': 'grant#' } }).resolves({ Items: items });
const setReported = (item: object | undefined) =>
  ddb.on(GetCommand, { Key: { pk: `reported#${THING}` } }).resolves({ Item: item });
const setPrevStatus = (item: StatusItem | undefined) =>
  ddb.on(GetCommand, { Key: { pk: `status#${THING}` } }).resolves({ Item: item });

beforeEach(() => {
  ddb.reset();
  sm.reset();
  resetGatewayCache();
  ddb.on(GetCommand).resolves({});
  ddb.on(ScanCommand).resolves({ Items: [] });
  sm.on(GetSecretValueCommand).resolves({ SecretString: JSON.stringify({ clientId: 'amzn1.app', clientSecret: 's' }) });
  fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(new Response(null, { status: 202 }));
  jest.spyOn(console, 'warn').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
  jest.spyOn(console, 'log').mockImplementation(() => {});
});

afterEach(() => jest.restoreAllMocks());

const statusEvent = (s: object, receivedAt = Date.now()) => ({
  mode: 'auto',
  relay: false,
  trip: null,
  remote: true,
  reason: 'change',
  ...s,
  thing: THING,
  receivedAt,
});

describe('a status from the IoT rule', () => {
  test('is stored with its Thing and receive time', async () => {
    const at = Date.now();
    await handler(statusEvent({ relay: true, watts: 61.2 }, at));
    expect(puts()[0]).toEqual({
      pk: `status#${THING}`,
      thing: THING,
      receivedAt: at,
      status: expect.objectContaining({ mode: 'auto', relay: true, watts: 61.2 }),
    });
  });

  test("a button press: a ChangeReport to every account that may see the unit, cause PHYSICAL_INTERACTION", async () => {
    setGrants(grant('martin', ['petro']), grant('certifier', ['petro-b2']), grant('kid', ['petro-b1']));
    setReported({ pk: `reported#${THING}`, powerState: 'OFF', connectivity: 'OK' });
    setPrevStatus({ pk: `status#${THING}`, thing: THING, receivedAt: Date.now() - 60_000, status: { mode: 'off', relay: false } });
    await handler(statusEvent({ mode: 'on', relay: true, remote: false }));
    const events = sent();
    expect(events.map((e) => e.auth)).toEqual(['Bearer access-martin', 'Bearer access-kid']);
    const { event, context } = events[0].body;
    expect(event.header).toMatchObject({ namespace: 'Alexa', name: 'ChangeReport', payloadVersion: '3' });
    expect(event.endpoint).toEqual({ scope: { type: 'BearerToken', token: 'access-martin' }, endpointId: THING });
    expect(event.payload.change.cause.type).toBe('PHYSICAL_INTERACTION');
    expect(event.payload.change.properties).toEqual([expect.objectContaining({ name: 'powerState', value: 'ON' })]);
    expect(context.properties).toEqual([expect.objectContaining({ name: 'connectivity', value: { value: 'OK' } })]);
    expect(puts().at(-1)).toEqual({ pk: `reported#${THING}`, powerState: 'ON', connectivity: 'OK' });
  });

  test('a trip: cause RULE_TRIGGER', async () => {
    setGrants(grant('martin', ['petro']));
    setReported({ pk: `reported#${THING}`, powerState: 'ON', connectivity: 'OK' });
    await handler(statusEvent({ relay: false, trip: 'overcurrent', remote: false }));
    expect(sent()[0].body.event.payload.change.cause.type).toBe('RULE_TRIGGER');
  });

  test('a heartbeat that matches what Alexa was told sends nothing', async () => {
    setGrants(grant('martin', ['petro']));
    setReported({ pk: `reported#${THING}`, powerState: 'OFF', connectivity: 'OK' });
    await handler(statusEvent({ reason: 'heartbeat' }));
    expect(sent()).toEqual([]);
    expect(puts()).toHaveLength(1); // the status only
  });

  test('back after being UNREACHABLE: connectivity OK, cause PERIODIC_POLL', async () => {
    setGrants(grant('martin', ['petro']));
    setReported({ pk: `reported#${THING}`, powerState: 'OFF', connectivity: 'UNREACHABLE' });
    await handler(statusEvent({ reason: 'boot' }));
    const { event, context } = sent()[0].body;
    expect(event.payload.change.cause.type).toBe('PERIODIC_POLL');
    expect(event.payload.change.properties).toEqual([expect.objectContaining({ name: 'connectivity', value: { value: 'OK' } })]);
    expect(context.properties).toEqual([expect.objectContaining({ name: 'powerState', value: 'OFF' })]);
  });

  test('an older message arriving late is ignored', async () => {
    setPrevStatus({ pk: `status#${THING}`, thing: THING, receivedAt: Date.now(), status: { relay: true } });
    await handler(statusEvent({ relay: false }, Date.now() - 10_000));
    expect(puts()).toEqual([]);
  });

  test('a status without a Petro Thing name is ignored', async () => {
    await handler({ ...statusEvent({}), thing: 'tinycrypt-sandbox-k1' });
    await handler({ mode: 'auto' });
    expect(puts()).toEqual([]);
  });

  test('a status without a relay field is stored but not reported', async () => {
    setGrants(grant('martin', ['petro']));
    const { relay: _r, ...noRelay } = statusEvent({});
    await handler(noRelay);
    expect(puts()).toHaveLength(1);
    expect(sent()).toEqual([]);
  });

  test('a missing receive time is taken as now', async () => {
    const { receivedAt: _t, ...e } = statusEvent({});
    await handler(e);
    expect(Math.abs((puts()[0].receivedAt as number) - Date.now())).toBeLessThan(5000);
  });

  test('with the skill secret unset: nothing sent, and Alexa is not marked told', async () => {
    sm.on(GetSecretValueCommand).resolves({ SecretString: JSON.stringify({ clientId: 'NOT_SET', clientSecret: 'x' }) });
    setGrants(grant('martin', ['petro']));
    await handler(statusEvent({ relay: true }));
    expect(sent()).toEqual([]);
    expect(puts().filter((p) => String(p.pk).startsWith('reported#'))).toEqual([]);
  });

  test('a gateway failure is logged, and Alexa is not marked told (the next status retries)', async () => {
    setGrants(grant('martin', ['petro']));
    fetchSpy.mockResolvedValue(new Response(JSON.stringify({ payload: { code: 'INTERNAL_SERVICE_EXCEPTION' } }), { status: 500 }));
    await handler(statusEvent({ relay: true }));
    expect(console.error).toHaveBeenCalled();
    expect(puts().filter((p) => String(p.pk).startsWith('reported#'))).toEqual([]);
  });
});

describe('tokens', () => {
  const lwaCalls = () => fetchSpy.mock.calls.filter(([url]) => url === LWA_TOKEN_URL);

  test('an access token about to expire is refreshed first, and the new one stored', async () => {
    setGrants(grant('martin', ['petro'], Date.now() + 10_000));
    fetchSpy.mockImplementation(async (url: string) =>
      url === LWA_TOKEN_URL
        ? new Response(JSON.stringify({ access_token: 'new', refresh_token: 'r2', expires_in: 3600 }), { status: 200 })
        : new Response(null, { status: 202 }),
    );
    await handler(statusEvent({ relay: true }));
    expect(String(lwaCalls()[0][1].body)).toContain('grant_type=refresh_token');
    expect(sent()[0].auth).toBe('Bearer new');
    expect(puts().find((p) => p.pk === 'grant#martin')).toMatchObject({ accessToken: 'new', refreshToken: 'r2' });
  });

  test('a 401 from the gateway refreshes once and retries', async () => {
    setGrants(grant('martin', ['petro']));
    let gateway = 0;
    fetchSpy.mockImplementation(async (url: string) => {
      if (url === LWA_TOKEN_URL) return new Response(JSON.stringify({ access_token: 'new', refresh_token: 'r2' }), { status: 200 });
      gateway++;
      return gateway === 1
        ? new Response(JSON.stringify({ payload: { code: 'INVALID_ACCESS_TOKEN_EXCEPTION' } }), { status: 401 })
        : new Response(null, { status: 202 });
    });
    await handler(statusEvent({ relay: true }));
    expect(sent().map((e) => e.auth)).toEqual(['Bearer access-martin', 'Bearer new']);
  });

  test.each(['SKILL_DISABLED_EXCEPTION', 'SKILL_NEVER_ENABLED_EXCEPTION', 'INSUFFICIENT_PERMISSION_EXCEPTION'])(
    '%s deletes the grant',
    async (code) => {
      setGrants(grant('martin', ['petro']));
      fetchSpy.mockResolvedValue(new Response(JSON.stringify({ payload: { code } }), { status: 403 }));
      await handler(statusEvent({ relay: true }));
      expect(ddb.commandCalls(DeleteCommand)[0].args[0].input.Key).toEqual({ pk: 'grant#martin' });
    },
  );

  test('LWA refusing the refresh token (invalid_grant) deletes the grant', async () => {
    setGrants(grant('martin', ['petro'], 0));
    fetchSpy.mockResolvedValue(new Response(JSON.stringify({ error: 'invalid_grant' }), { status: 400 }));
    await handler(statusEvent({ relay: true }));
    expect(ddb.commandCalls(DeleteCommand)).toHaveLength(1);
    expect(sent()).toEqual([]);
  });

  test('grants are read across Scan pages', async () => {
    ddb
      .on(ScanCommand, { ExpressionAttributeValues: { ':p': 'grant#' } })
      .resolvesOnce({ Items: [grant('a', ['petro'])], LastEvaluatedKey: { pk: 'grant#a' } })
      .resolvesOnce({ Items: [grant('b', ['petro'])] });
    await handler(statusEvent({ relay: true }));
    expect(sent()).toHaveLength(2);
  });
});

describe('the sweep', () => {
  const stored = (thing: string, ageMs: number, relay = true): StatusItem => ({
    pk: `status#${thing}`,
    thing,
    receivedAt: Date.now() - ageMs,
    status: { mode: 'auto', relay },
  });

  test('reports a unit gone quiet as UNREACHABLE, once', async () => {
    setGrants(grant('martin', ['petro']));
    ddb.on(ScanCommand, { ExpressionAttributeValues: { ':p': 'status#' } }).resolves({
      Items: [stored(THING, 10 * 60_000), stored('petro-sandbox-b2', 30_000)],
    });
    setReported({ pk: `reported#${THING}`, powerState: 'ON', connectivity: 'OK' });
    await handler({ sweep: true });
    const events = sent();
    expect(events).toHaveLength(1);
    const { event, context } = events[0].body;
    expect(event.endpoint.endpointId).toBe(THING);
    expect(event.payload.change.properties).toEqual([expect.objectContaining({ name: 'connectivity', value: { value: 'UNREACHABLE' } })]);
    expect(context.properties).toEqual([expect.objectContaining({ name: 'powerState', value: 'ON' })]);
    expect(puts().at(-1)).toEqual({ pk: `reported#${THING}`, powerState: 'ON', connectivity: 'UNREACHABLE' });
  });

  test('a unit already reported UNREACHABLE is not reported again', async () => {
    setGrants(grant('martin', ['petro']));
    ddb.on(ScanCommand, { ExpressionAttributeValues: { ':p': 'status#' } }).resolves({ Items: [stored(THING, 10 * 60_000)] });
    setReported({ pk: `reported#${THING}`, connectivity: 'UNREACHABLE' });
    await handler({ sweep: true });
    expect(sent()).toEqual([]);
  });

  test('reads statuses across Scan pages', async () => {
    ddb
      .on(ScanCommand, { ExpressionAttributeValues: { ':p': 'status#' } })
      .resolvesOnce({ Items: [], LastEvaluatedKey: { pk: 'x' } })
      .resolvesOnce({ Items: [stored(THING, 10 * 60_000, false)] });
    await handler({ sweep: true });
    expect(puts().at(-1)).toMatchObject({ powerState: 'OFF', connectivity: 'UNREACHABLE' });
  });
});

describe('causeOf', () => {
  test.each([
    [{ mode: 'auto', trip: null }, { mode: 'off', trip: 'overtemp' }, 'RULE_TRIGGER'],
    [{ mode: 'off' }, { mode: 'auto' }, 'PHYSICAL_INTERACTION'],
    [{ mode: 'on' }, { mode: 'on' }, 'PHYSICAL_INTERACTION'],
    [{ mode: 'auto' }, { mode: 'auto' }, 'APP_INTERACTION'],
    [undefined, { mode: 'auto' }, 'PHYSICAL_INTERACTION'],
    [{ mode: 'auto', trip: 'overtemp' }, { mode: 'auto', trip: 'overtemp' }, 'APP_INTERACTION'],
  ])('%j → %j is %s', (prev, next, cause) => {
    expect(causeOf(prev, next)).toBe(cause);
  });
});
