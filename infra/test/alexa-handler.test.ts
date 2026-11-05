process.env.DEPLOY_ENV = 'sandbox';
process.env.HOME_REGION = 'eu-west-2';
process.env.TABLE_NAME = 'petro-alexa-sandbox';
process.env.SKILL_SECRET_ID = 'petro/sandbox/alexa/skill-messaging';
process.env.USER_POOL_ID = 'eu-west-2_test';
process.env.ALEXA_CLIENT_ID = 'client';
process.env.POLL_MS = '1';
process.env.CONFIRM_MS = '20';

import { IoTClient, ListThingsCommand } from '@aws-sdk/client-iot';
import { IoTDataPlaneClient, PublishCommand } from '@aws-sdk/client-iot-data-plane';
import { GetSecretValueCommand, SecretsManagerClient } from '@aws-sdk/client-secrets-manager';
import { DynamoDBDocumentClient, GetCommand, PutCommand } from '@aws-sdk/lib-dynamodb';
import { mockClient } from 'aws-sdk-client-mock';
import { resetGatewayCache } from '../lambda/alexa/gateway';
import { type AlexaEvent, handler, setVerifier } from '../lambda/alexa/handler';
import type { PetroStatus, StatusItem } from '../lambda/alexa/shared';

const ddb = mockClient(DynamoDBDocumentClient);
const iot = mockClient(IoTClient);
const iotData = mockClient(IoTDataPlaneClient);
const sm = mockClient(SecretsManagerClient);

const THING = 'petro-sandbox-b1';
const USERS: Record<string, string[]> = {
  martin: ['petro'],
  certifier: ['petro-b2'],
  stranger: ['lightning'],
};

beforeEach(() => {
  ddb.reset();
  iot.reset();
  iotData.reset();
  sm.reset();
  resetGatewayCache();
  ddb.on(GetCommand).resolves({});
  setVerifier({
    async verify(token: string) {
      if (!(token in USERS)) throw new Error('bad token');
      return { sub: `sub-${token}`, 'cognito:groups': USERS[token] };
    },
  });
  jest.spyOn(console, 'warn').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => jest.restoreAllMocks());

const directive = (namespace: string, name: string, token = 'martin', endpointId = THING, payload = {}): AlexaEvent => ({
  directive: {
    header: { namespace, name, payloadVersion: '3', messageId: 'm', correlationToken: 'ct' },
    endpoint: { endpointId, scope: { type: 'BearerToken', token } },
    payload,
  },
});

const status = (s: PetroStatus, ageMs = 1000): StatusItem => ({
  pk: `status#${THING}`,
  thing: THING,
  receivedAt: Date.now() - ageMs,
  status: { mode: 'auto', relay: false, trip: null, remote: true, cycle: null, ...s },
});

const statusGet = () => ddb.on(GetCommand, { Key: { pk: `status#${THING}` } });

const errorOf = (r: Awaited<ReturnType<typeof handler>>) => ({
  namespace: r.event.header.namespace,
  name: r.event.header.name,
  type: r.event.payload.type,
  mode: r.event.payload.currentDeviceMode,
  message: r.event.payload.message as string,
});

describe('Discovery', () => {
  const discover = (token: string) =>
    handler({
      directive: {
        header: { namespace: 'Alexa.Discovery', name: 'Discover', payloadVersion: '3', messageId: 'm' },
        payload: { scope: { type: 'BearerToken', token } },
      },
    });

  beforeEach(() => {
    iot.on(ListThingsCommand).resolves({
      things: [
        { thingName: 'petro-sandbox-b2' },
        { thingName: 'petro-sandbox-b1' },
        { thingName: 'petro-prod-b1' }, // another env's (can't happen across accounts, but filtered)
        { thingName: 'tinycrypt-sandbox-k1' },
      ],
    });
  });

  test('every unit of this env, as a SMARTPLUG with PowerController, EndpointHealth and Alexa', async () => {
    const r = await discover('martin');
    expect(r.event.header.name).toBe('Discover.Response');
    const endpoints = r.event.payload.endpoints;
    expect(endpoints.map((e: { endpointId: string }) => e.endpointId)).toEqual(['petro-sandbox-b1', 'petro-sandbox-b2']);
    const e = endpoints[0];
    expect(e.friendlyName).toBe('Petro b1');
    expect(e.displayCategories).toEqual(['SMARTPLUG']);
    expect(e.capabilities.map((c: { interface: string }) => c.interface)).toEqual([
      'Alexa.PowerController',
      'Alexa.EndpointHealth',
      'Alexa',
    ]);
    for (const c of e.capabilities.slice(0, 2)) {
      expect(c.properties).toMatchObject({ proactivelyReported: true, retrievable: true });
    }
    expect(iot.commandCalls(ListThingsCommand)[0].args[0].input).toMatchObject({
      attributeName: 'project',
      attributeValue: 'petro',
    });
  });

  test('follows ListThings pages', async () => {
    iot
      .on(ListThingsCommand)
      .resolvesOnce({ things: [{ thingName: 'petro-sandbox-b1' }], nextToken: 'n' })
      .resolvesOnce({ things: [{ thingName: 'petro-sandbox-b3' }] });
    const r = await discover('martin');
    expect(r.event.payload.endpoints).toHaveLength(2);
  });

  test('a one-unit group sees that unit only', async () => {
    const r = await discover('certifier');
    expect(r.event.payload.endpoints.map((e: { endpointId: string }) => e.endpointId)).toEqual(['petro-sandbox-b2']);
  });

  test('a pool user in no Petro group sees nothing', async () => {
    expect((await discover('stranger')).event.payload.endpoints).toEqual([]);
  });

  test('a bad token gets no endpoints, not an error', async () => {
    const r = await discover('forged');
    expect(r.event.header.name).toBe('Discover.Response');
    expect(r.event.payload.endpoints).toEqual([]);
  });
});

describe('ReportState', () => {
  test('the relay from the latest status, and connectivity OK while fresh', async () => {
    const item = status({ relay: true });
    statusGet().resolves({ Item: item });
    const r = await handler(directive('Alexa', 'ReportState'));
    expect(r.event.header).toMatchObject({ name: 'StateReport', correlationToken: 'ct' });
    expect(r.context!.properties).toEqual([
      expect.objectContaining({ namespace: 'Alexa.PowerController', name: 'powerState', value: 'ON', timeOfSample: new Date(item.receivedAt).toISOString() }),
      expect.objectContaining({ namespace: 'Alexa.EndpointHealth', name: 'connectivity', value: { value: 'OK' } }),
    ]);
  });

  test('UNREACHABLE once the status is over 3 minutes old', async () => {
    statusGet().resolves({ Item: status({ relay: false }, 4 * 60 * 1000) });
    const r = await handler(directive('Alexa', 'ReportState'));
    expect(r.context!.properties[1].value).toEqual({ value: 'UNREACHABLE' });
  });

  test('a unit that never reported is ENDPOINT_UNREACHABLE', async () => {
    statusGet().resolves({});
    expect(errorOf(await handler(directive('Alexa', 'ReportState'))).type).toBe('ENDPOINT_UNREACHABLE');
  });

  test("a unit outside the user's groups is NO_SUCH_ENDPOINT", async () => {
    expect(errorOf(await handler(directive('Alexa', 'ReportState', 'certifier'))).type).toBe('NO_SUCH_ENDPOINT');
    expect(errorOf(await handler(directive('Alexa', 'ReportState', 'martin', 'petro-prod-b1'))).type).toBe('NO_SUCH_ENDPOINT');
  });

  test('a bad token is INVALID_AUTHORIZATION_CREDENTIAL', async () => {
    expect(errorOf(await handler(directive('Alexa', 'ReportState', 'forged'))).type).toBe('INVALID_AUTHORIZATION_CREDENTIAL');
    const noScope = directive('Alexa', 'ReportState');
    delete noScope.directive.endpoint!.scope;
    expect(errorOf(await handler(noScope)).type).toBe('INVALID_AUTHORIZATION_CREDENTIAL');
  });
});

describe('TurnOn / TurnOff', () => {
  test("publishes Fleet's relay command and answers with the status that confirms it", async () => {
    const before = status({ relay: false }, 5000);
    const after = { ...status({ relay: true }), receivedAt: Date.now() };
    statusGet().resolvesOnce({ Item: before }).resolves({ Item: after });
    const r = await handler(directive('Alexa.PowerController', 'TurnOn'));
    expect(r.event.header.name).toBe('Response');
    expect(r.context!.properties[0]).toMatchObject({ name: 'powerState', value: 'ON', timeOfSample: new Date(after.receivedAt).toISOString() });
    const [publish] = iotData.commandCalls(PublishCommand);
    expect(publish.args[0].input.topic).toBe(`petro/${THING}/commands`);
    expect(JSON.parse(Buffer.from(publish.args[0].input.payload as Uint8Array).toString())).toEqual({ command: 'relay', on: true });
    // What Alexa now believes, written before the command so the reporter doesn't report it again.
    expect(ddb.commandCalls(PutCommand)[0].args[0].input.Item).toEqual({ pk: `reported#${THING}`, powerState: 'ON', connectivity: 'OK' });
  });

  test('TurnOff publishes on:false', async () => {
    statusGet()
      .resolvesOnce({ Item: status({ relay: true }, 5000) })
      .resolves({ Item: { ...status({ relay: false }), receivedAt: Date.now() } });
    const r = await handler(directive('Alexa.PowerController', 'TurnOff'));
    expect(r.context!.properties[0].value).toBe('OFF');
    const payload = iotData.commandCalls(PublishCommand)[0].args[0].input.payload as Uint8Array;
    expect(JSON.parse(Buffer.from(payload).toString())).toEqual({ command: 'relay', on: false });
  });

  test('already in the asked-for state: answers at once, no command', async () => {
    statusGet().resolves({ Item: status({ relay: true }) });
    const r = await handler(directive('Alexa.PowerController', 'TurnOn'));
    expect(r.event.header.name).toBe('Response');
    expect(iotData.commandCalls(PublishCommand)).toHaveLength(0);
  });

  test('no confirmation in time: ENDPOINT_UNREACHABLE, and what Alexa was told goes back', async () => {
    const before = status({ relay: false }, 5000);
    statusGet().resolves({ Item: before });
    const prior = { pk: `reported#${THING}`, powerState: 'OFF', connectivity: 'OK' };
    ddb.on(GetCommand, { Key: { pk: `reported#${THING}` } }).resolves({ Item: prior });
    const e = errorOf(await handler(directive('Alexa.PowerController', 'TurnOn')));
    expect(e.type).toBe('ENDPOINT_UNREACHABLE');
    expect(e.message).toMatch(/did not confirm/);
    const puts = ddb.commandCalls(PutCommand).map((c) => c.args[0].input.Item);
    expect(puts.at(-1)).toEqual(prior);
  });

  test('a newer status that shows a trip instead: the trip, not a pretend switch', async () => {
    statusGet()
      .resolvesOnce({ Item: status({ relay: false }, 5000) })
      .resolves({ Item: { ...status({ relay: false, trip: 'overcurrent', remote: false }), receivedAt: Date.now() } });
    const e = errorOf(await handler(directive('Alexa.PowerController', 'TurnOn')));
    expect(e).toMatchObject({ type: 'NOT_SUPPORTED_IN_CURRENT_MODE', mode: 'OTHER' });
    expect(e.message).toMatch(/tripped \(overcurrent\)/);
  });

  test('a newer status that still shows the old state keeps waiting, then gives up', async () => {
    statusGet()
      .resolvesOnce({ Item: status({ relay: false }, 5000) })
      .resolves({ Item: { ...status({ relay: false }), receivedAt: Date.now() } });
    expect(errorOf(await handler(directive('Alexa.PowerController', 'TurnOn'))).type).toBe('ENDPOINT_UNREACHABLE');
  });

  test.each([
    ['on', /held on at its button/],
    ['off', /held off at its button/],
  ])('mode %s (the button override) is refused as NOT_SUPPORTED_IN_CURRENT_MODE', async (mode, message) => {
    statusGet().resolves({ Item: status({ mode, relay: mode === 'on', remote: false }) });
    const e = errorOf(await handler(directive('Alexa.PowerController', mode === 'on' ? 'TurnOff' : 'TurnOn')));
    expect(e).toMatchObject({ namespace: 'Alexa', name: 'ErrorResponse', type: 'NOT_SUPPORTED_IN_CURRENT_MODE', mode: 'OTHER' });
    expect(e.message).toMatch(message);
    expect(iotData.commandCalls(PublishCommand)).toHaveLength(0);
  });

  test.each(['overcurrent', 'overtemp', 'overcurrent_instant', 'meter_fault'])(
    'a latched %s trip is refused, whatever the mode',
    async (trip) => {
      statusGet().resolves({ Item: status({ mode: 'off', relay: false, trip, remote: false }) });
      const e = errorOf(await handler(directive('Alexa.PowerController', 'TurnOn')));
      expect(e.type).toBe('NOT_SUPPORTED_IN_CURRENT_MODE');
      expect(e.message).toContain(trip);
      expect(e.message).toMatch(/press its button/);
      expect(iotData.commandCalls(PublishCommand)).toHaveLength(0);
    },
  );

  test('auto but not taking remote commands (a relay cycle) is ENDPOINT_BUSY', async () => {
    statusGet().resolves({ Item: status({ remote: false, cycle: { done: 3, n: 500 } }) });
    const e = errorOf(await handler(directive('Alexa.PowerController', 'TurnOn')));
    expect(e.type).toBe('ENDPOINT_BUSY');
    expect(e.message).toMatch(/relay cycle/);
    statusGet().resolves({ Item: status({ remote: false }) });
    expect(errorOf(await handler(directive('Alexa.PowerController', 'TurnOn'))).message).toMatch(/not taking remote/);
  });

  test('a stale or missing status is ENDPOINT_UNREACHABLE, and nothing is sent', async () => {
    statusGet().resolves({ Item: status({}, 10 * 60 * 1000) });
    expect(errorOf(await handler(directive('Alexa.PowerController', 'TurnOn'))).type).toBe('ENDPOINT_UNREACHABLE');
    statusGet().resolves({});
    expect(errorOf(await handler(directive('Alexa.PowerController', 'TurnOn'))).type).toBe('ENDPOINT_UNREACHABLE');
    expect(iotData.commandCalls(PublishCommand)).toHaveLength(0);
  });

  test('a failure talking to AWS is INTERNAL_ERROR', async () => {
    statusGet().rejects(new Error('boom'));
    expect(errorOf(await handler(directive('Alexa.PowerController', 'TurnOn'))).type).toBe('INTERNAL_ERROR');
  });
});

describe('AcceptGrant', () => {
  const grant = (token = 'martin', code: unknown = 'the-code') =>
    handler({
      directive: {
        header: { namespace: 'Alexa.Authorization', name: 'AcceptGrant', payloadVersion: '3', messageId: 'm' },
        payload: { grant: { type: 'OAuth2.AuthorizationCode', code }, grantee: { type: 'BearerToken', token } },
      },
    });

  test("swaps the code for LWA tokens and stores them with the user's groups", async () => {
    sm.on(GetSecretValueCommand).resolves({ SecretString: JSON.stringify({ clientId: 'amzn1.app', clientSecret: 's' }) });
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'A', refresh_token: 'R', expires_in: 3600 }), { status: 200 }),
    );
    const r = await grant();
    expect(r.event.header).toMatchObject({ namespace: 'Alexa.Authorization', name: 'AcceptGrant.Response' });
    const body = String(fetchSpy.mock.calls[0][1]!.body);
    expect(body).toContain('grant_type=authorization_code');
    expect(body).toContain('code=the-code');
    expect(body).toContain('client_id=amzn1.app');
    const item = ddb.commandCalls(PutCommand)[0].args[0].input.Item!;
    expect(item).toMatchObject({ pk: 'grant#sub-martin', sub: 'sub-martin', groups: ['petro'], accessToken: 'A', refreshToken: 'R' });
  });

  test.each([
    ['the secret still holds the placeholder', { clientId: 'NOT_SET', clientSecret: 'x' }, 'martin', 'c'],
    ['a bad grantee token', { clientId: 'id', clientSecret: 's' }, 'forged', 'c'],
    ['no code', { clientId: 'id', clientSecret: 's' }, 'martin', undefined],
  ])('fails with ACCEPT_GRANT_FAILED when %s', async (_why, secret, token, code) => {
    sm.on(GetSecretValueCommand).resolves({ SecretString: JSON.stringify(secret) });
    const e = errorOf(await grant(token, code));
    expect(e).toMatchObject({ namespace: 'Alexa.Authorization', name: 'ErrorResponse', type: 'ACCEPT_GRANT_FAILED' });
  });

  test('fails with ACCEPT_GRANT_FAILED when LWA refuses the code', async () => {
    sm.on(GetSecretValueCommand).resolves({ SecretString: JSON.stringify({ clientId: 'id', clientSecret: 's' }) });
    jest.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify({ error: 'invalid_grant' }), { status: 400 }));
    expect(errorOf(await grant()).type).toBe('ACCEPT_GRANT_FAILED');
  });
});

describe('the envelope', () => {
  test('a malformed event is INVALID_DIRECTIVE', async () => {
    expect(errorOf(await handler({} as AlexaEvent)).type).toBe('INVALID_DIRECTIVE');
  });

  test('an unsupported directive is INVALID_DIRECTIVE', async () => {
    expect(errorOf(await handler(directive('Alexa.BrightnessController', 'SetBrightness'))).type).toBe('INVALID_DIRECTIVE');
  });
});
