import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { DeviceStack, FLEET_ATTRIBUTES } from '../lib/device-stack';
import { deployEnvFrom, deviceNamesFor } from '../lib/devices';

const ARN = 'arn:aws:iot:eu-west-2:000000000000';

// As cdk.json: the partition is a literal (arn:aws:…), not a Ref.
const newApp = () => new cdk.App({ context: { '@aws-cdk/core:enablePartitionLiterals': true } });

const synth = (deployEnv: 'sandbox' | 'prod', deviceNames: string[]) => {
  const app = newApp();
  const stack = new DeviceStack(app, 'Test', {
    env: { account: '000000000000', region: 'eu-west-2' },
    deployEnv,
    deviceNames,
  });
  return Template.fromStack(stack);
};

type Statement = { Action: string; Resource: string | string[]; Condition?: unknown };

const statements = (t: Template): Statement[] => {
  const [policy] = Object.values(t.findResources('AWS::IoT::Policy')) as {
    Properties: { PolicyDocument: { Statement: Statement[] } };
  }[];
  return policy.Properties.PolicyDocument.Statement;
};

/** Every resource the policy grants for one action, flattened. */
const resourcesFor = (t: Template, action: string) =>
  statements(t)
    .filter((s) => s.Action === action)
    .flatMap((s) => ([] as string[]).concat(s.Resource));

const own = (suffix: string) => `petro/\${iot:Connection.Thing.ThingName}/${suffix}`;

describe('DeviceStack', () => {
  test('one Thing per unit, petro-{env}-{name}, with the attributes Fleet reads', () => {
    const t = synth('prod', ['b1', 'b2']);
    t.resourceCountIs('AWS::IoT::Thing', 2);
    for (const name of ['petro-prod-b1', 'petro-prod-b2']) {
      t.hasResourceProperties('AWS::IoT::Thing', {
        ThingName: name,
        AttributePayload: {
          Attributes: { project: 'petro', deviceType: 'smart-switch', capabilities: 'ota' },
        },
      });
    }
    t.hasOutput('ThingNameb1', { Value: 'petro-prod-b1' });
  });

  test('Fleet attributes: at most three (IoT refuses more on a Thing with no type)', () => {
    expect(Object.keys(FLEET_ATTRIBUTES).length).toBeLessThanOrEqual(3);
  });

  test('Fleet attributes use only the characters IoT allows in attribute values', () => {
    for (const v of Object.values(FLEET_ATTRIBUTES)) expect(v).toMatch(/^[a-zA-Z0-9_.,@/:#=\[\]-]+$/);
  });

  test('the policy is named per env and output for the provisioning script', () => {
    const t = synth('sandbox', ['b1']);
    t.hasResourceProperties('AWS::IoT::Policy', { PolicyName: 'petro-device-sandbox' });
    t.hasOutput('DevicePolicyName', { Value: 'petro-device-sandbox' });
  });

  test('connect only as its own attached Thing', () => {
    const t = synth('prod', ['b1']);
    const connect = statements(t).filter((s) => s.Action === 'iot:Connect');
    expect(connect).toHaveLength(1);
    expect(connect[0].Condition).toEqual({ Bool: { 'iot:Connection.Thing.IsAttached': 'true' } });
    expect(resourcesFor(t, 'iot:Connect')).toEqual([`${ARN}:client/\${iot:Connection.Thing.ThingName}`]);
  });

  test('publishes its own responses and status, takes its own commands, nothing more', () => {
    const t = synth('prod', ['b1']);
    expect(resourcesFor(t, 'iot:Publish').sort()).toEqual(
      [`${ARN}:topic/${own('responses')}`, `${ARN}:topic/${own('status')}`].sort(),
    );
    expect(resourcesFor(t, 'iot:Subscribe')).toEqual([`${ARN}:topicfilter/${own('commands')}`]);
    expect(resourcesFor(t, 'iot:Receive')).toEqual([`${ARN}:topic/${own('commands')}`]);
    expect(statements(t).map((s) => s.Action).sort()).toEqual(
      ['iot:Connect', 'iot:Publish', 'iot:Receive', 'iot:Subscribe'],
    );
    const doc = JSON.stringify(statements(t));
    expect(doc).not.toMatch(/topic\/petro\/\*|topic\/\*|"iot:\*"/);
  });

  test('no account id is hard-coded: it comes from the stack env', () => {
    const app = newApp();
    const stack = new DeviceStack(app, 'Other', {
      env: { account: '111111111111', region: 'eu-west-1' },
      deployEnv: 'sandbox',
      deviceNames: ['b1'],
    });
    const doc = JSON.stringify(Template.fromStack(stack).toJSON());
    expect(doc).toContain('eu-west-1:111111111111');
    expect(doc).not.toMatch(/975050268859|637423226886/);
  });

  test('no certificate is made by CloudFormation', () => {
    const t = synth('prod', ['b1']);
    t.resourceCountIs('AWS::IoT::Certificate', 0);
    t.resourceCountIs('AWS::IoT::ThingPrincipalAttachment', 0);
    t.resourceCountIs('AWS::IoT::PolicyPrincipalAttachment', 0);
  });

  test('no units: just the policy', () => {
    const t = synth('prod', []);
    t.resourceCountIs('AWS::IoT::Thing', 0);
    t.resourceCountIs('AWS::IoT::Policy', 1);
  });
});

describe('devices.json', () => {
  const devices = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'devices.json'), 'utf8'));

  test('prod has the five rev B units, matching the vmauth users petro-prod-b1 … b5', () => {
    expect(deviceNamesFor(devices, 'prod')).toEqual(['b1', 'b2', 'b3', 'b4', 'b5']);
  });

  test('sandbox has a bench unit', () => {
    expect(deviceNamesFor(devices, 'sandbox')).toEqual(['b1']);
  });

  test.each([
    [{ prod: ['b1', 'b1'] }],
    [{ prod: ['unit-1'] }],
    [{ prod: ['b0'] }],
    [{ prod: [1] }],
    [{ prod: 'b1' }],
    [{}],
    [null],
  ])('rejects %j', (bad) => {
    expect(() => deviceNamesFor(bad, 'prod')).toThrow(/devices\.json/);
  });

  test('NPM_ENVIRONMENT must be sandbox or prod', () => {
    expect(deployEnvFrom('sandbox')).toBe('sandbox');
    expect(deployEnvFrom('prod')).toBe('prod');
    expect(() => deployEnvFrom(undefined)).toThrow(/NPM_ENVIRONMENT/);
    expect(() => deployEnvFrom('staging')).toThrow(/NPM_ENVIRONMENT/);
  });
});
