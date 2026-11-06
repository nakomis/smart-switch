import * as cdk from 'aws-cdk-lib';
import * as iot from 'aws-cdk-lib/aws-iot';
import { Construct } from 'constructs';

export interface DeviceStackProps extends cdk.StackProps {
  deployEnv: 'sandbox' | 'prod';
  /** One IoT Thing per physical Petro, e.g. ['b1']: the Thing is petro-{env}-{name}. */
  deviceNames: string[];
}

/** The Thing's name for one unit: petro-{env}-{name}, e.g. petro-prod-b1. */
export const thingName = (deployEnv: string, name: string) => `petro-${deployEnv}-${name}`;

/** The policy firmware/scripts/provision-device.sh attaches to every unit's certificate. */
export const policyName = (deployEnv: string) => `petro-device-${deployEnv}`;

/**
 * What Fleet (nakomis-fleet) reads from each Thing. A Thing without a Thing type may have only three
 * attributes, so no hwType (Fleet shows it as unknown, as for the heatlink and katooni).
 */
export const FLEET_ATTRIBUTES = {
  project: 'petro',
  deviceType: 'smart-switch',
  // Plain OTA, as the nakostat heatlink: no ota-signed until PETRO-9 signs its builds.
  capabilities: 'ota',
};

/**
 * PETRO-3 (from katooni's DeviceStack, itself from tinycrypt's KeyStack): each Petro is an IoT Thing
 * that may only connect as itself, take Fleet's commands on petro/{thing}/commands and publish on
 * petro/{thing}/responses and petro/{thing}/status (its own only). Its attributes make it show up in
 * Fleet as project petro; Fleet finds its firmware under the bucket's petro/ prefix and adds a
 * registry row the first time it hears from it, so Fleet itself needs no change. Its certificate is
 * made and attached by firmware/scripts/provision-device.sh, never here: the private key must not
 * pass through CloudFormation.
 */
export class DeviceStack extends cdk.Stack {
  public readonly policy: iot.CfnPolicy;

  constructor(scope: Construct, id: string, props: DeviceStackProps) {
    super(scope, id, props);
    const { deployEnv, deviceNames } = props;

    const arn = (resource: string) => `arn:${this.partition}:iot:${this.region}:${this.account}:${resource}`;
    const own = (suffix: string) => `petro/\${iot:Connection.Thing.ThingName}/${suffix}`;

    // Policy variables pin each certificate to its own Thing: the client id must be the Thing's name,
    // and the certificate must be attached to that Thing.
    this.policy = new iot.CfnPolicy(this, 'DevicePolicy', {
      policyName: policyName(deployEnv),
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Action: 'iot:Connect',
            Resource: arn('client/${iot:Connection.Thing.ThingName}'),
            Condition: { Bool: { 'iot:Connection.Thing.IsAttached': 'true' } },
          },
          {
            Effect: 'Allow',
            Action: 'iot:Publish',
            Resource: [arn(`topic/${own('responses')}`), arn(`topic/${own('status')}`)],
          },
          {
            Effect: 'Allow',
            Action: 'iot:Subscribe',
            Resource: arn(`topicfilter/${own('commands')}`),
          },
          {
            Effect: 'Allow',
            Action: 'iot:Receive',
            Resource: arn(`topic/${own('commands')}`),
          },
        ],
      },
    });

    for (const name of deviceNames) {
      const thing = thingName(deployEnv, name);
      new iot.CfnThing(this, `Thing-${name}`, {
        thingName: thing,
        attributePayload: { attributes: FLEET_ATTRIBUTES },
      });
      new cdk.CfnOutput(this, `ThingName-${name}`, { value: thing });
    }
    new cdk.CfnOutput(this, 'DevicePolicyName', { value: this.policy.policyName! });
  }
}
