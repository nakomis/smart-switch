import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as iot from 'aws-cdk-lib/aws-iot';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as nodejs from 'aws-cdk-lib/aws-lambda-nodejs';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import loginBranding from './login-branding.json';

// PETRO-8: Petro as an Alexa Smart Home smart plug, from nakostat's AlexaAuthStack and AlexaStack.
// Three stacks: the account-linking client beside the shared pool (eu-west-2), the state table and
// reporter beside IoT Core (eu-west-2), and the skill's Lambda in eu-west-1, Alexa's EU endpoint
// region. Two-step first deploy (docs/alexa-setup.md).

/** Returned by the SSM lookups until Martin has created the skill and set the parameters. */
export const SKILL_ID_PLACEHOLDER = 'SKILL_ID_NOT_SET';
export const VENDOR_ID_PLACEHOLDER = 'VENDOR_ID_NOT_SET';

const SKILL_ID_PATTERN = /^amzn1\.ask\.skill\.[0-9a-f-]+$/;

export const skillIdParameter = (deployEnv: string) => `/petro/${deployEnv}/alexa/skillId`;
export const vendorIdParameter = (deployEnv: string) => `/petro/${deployEnv}/alexa/vendorId`;
export const clientIdParameter = (deployEnv: string) => `/petro/${deployEnv}/alexa/cognito/client-id`;
export const tableName = (deployEnv: string) => `petro-alexa-${deployEnv}`;
/** The skill's Send Alexa Events client ID and secret, as {"clientId","clientSecret"}. */
export const skillSecretName = (deployEnv: string) => `petro/${deployEnv}/alexa/skill-messaging`;

/** Alexa's account-linking redirect hosts (UK/EU skills use layla; the console lists all three). */
export const alexaRedirectUris = (vendorId: string) => [
  `https://layla.amazon.com/api/skill/link/${vendorId}`,
  `https://pitangui.amazon.com/api/skill/link/${vendorId}`,
  `https://alexa.amazon.co.jp/api/skill/link/${vendorId}`,
];

const lambdaDir = path.join(__dirname, '..', 'lambda', 'alexa');

const logGroup = (scope: Construct, id: string, name: string) =>
  new logs.LogGroup(scope, id, {
    logGroupName: `/aws/lambda/${name}`,
    retention: logs.RetentionDays.ONE_MONTH,
    removalPolicy: cdk.RemovalPolicy.DESTROY,
  });

// ── Account linking (eu-west-2, alongside the shared user pool) ──────────────

export interface AlexaAuthStackProps extends cdk.StackProps {
  deployEnv: 'sandbox' | 'prod';
  /** The units, for their one-unit groups (petro-b1, …). */
  deviceNames: string[];
  /** Overrides the SSM lookup of the vendor ID (tests, or `-c alexaVendorId=`). */
  vendorId?: string;
}

/**
 * The Cognito app client Alexa links accounts through, its managed login style, and the groups
 * that decide who sees which unit: `petro` (every unit) and `petro-<name>` (one, e.g. for the
 * certification account). Nobody is put in a group here: Martin does that (docs/alexa-setup.md).
 */
export class AlexaAuthStack extends cdk.Stack {
  readonly userPoolId: string;
  readonly client: cognito.UserPoolClient;

  constructor(scope: Construct, id: string, props: AlexaAuthStackProps) {
    super(scope, id, props);
    const { deployEnv } = props;

    const vendorId =
      props.vendorId ??
      ssm.StringParameter.valueFromLookup(this, vendorIdParameter(deployEnv), VENDOR_ID_PLACEHOLDER);
    if (vendorId === VENDOR_ID_PLACEHOLDER) {
      cdk.Annotations.of(this).addWarningV2(
        'petro:alexaVendorIdMissing',
        `SSM ${vendorIdParameter(deployEnv)} is not set; account linking redirect URIs are placeholders. See docs/alexa-setup.md.`,
      );
    }

    this.userPoolId = ssm.StringParameter.valueForStringParameter(this, `/nakomis-infra/${deployEnv}/cognito/user-pool-id`);
    const userPool = cognito.UserPool.fromUserPoolId(this, 'SharedPool', this.userPoolId);

    this.client = new cognito.UserPoolClient(this, 'AlexaClient', {
      userPoolClientName: `petro-alexa-${deployEnv}`,
      userPool,
      generateSecret: true,
      authFlows: {},
      // Cognito users only: the pool also federates Sign in with Apple, which would let anyone with
      // an Apple ID make themselves a user. (Groups gate the units too, but don't rely on one lock.)
      supportedIdentityProviders: [cognito.UserPoolClientIdentityProvider.COGNITO],
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE, cognito.OAuthScope.EMAIL],
        callbackUrls: alexaRedirectUris(vendorId),
      },
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      // As nakostat: Alexa refreshes hourly and Cognito doesn't rotate refresh tokens, so a short
      // refresh token would silently break the link. Revoking is in docs/alexa-setup.md.
      refreshTokenValidity: cdk.Duration.days(3650),
      enableTokenRevocation: true,
      preventUserExistenceErrors: true,
    });

    // Managed login needs a style per client, or the hosted page says "Login pages unavailable".
    // The settings are copied from the pool's other Alexa client (recipator-alexa).
    const branding = new cognito.CfnManagedLoginBranding(this, 'ManagedLoginBranding', {
      userPoolId: this.userPoolId,
      clientId: this.client.userPoolClientId,
      useCognitoProvidedValues: false,
      settings: loginBranding,
    });
    branding.node.addDependency(this.client);

    new cognito.CfnUserPoolGroup(this, 'AllUnitsGroup', {
      userPoolId: this.userPoolId,
      groupName: 'petro',
      description: `Petro: sees and switches every unit in Alexa (${deployEnv})`,
    });
    for (const name of props.deviceNames) {
      new cognito.CfnUserPoolGroup(this, `UnitGroup-${name}`, {
        userPoolId: this.userPoolId,
        groupName: `petro-${name}`,
        description: `Petro: sees and switches unit ${name} only in Alexa (${deployEnv})`,
      });
    }

    new ssm.StringParameter(this, 'AlexaClientIdParam', {
      parameterName: clientIdParameter(deployEnv),
      stringValue: this.client.userPoolClientId,
      description: `Petro Alexa account-linking Cognito client ID (${deployEnv})`,
    });

    new cdk.CfnOutput(this, 'AlexaClientId', {
      value: this.client.userPoolClientId,
      description: 'Cognito client ID for Alexa account linking (secret: aws cognito-idp describe-user-pool-client)',
    });
  }
}

// ── State and proactive reports (eu-west-2, beside IoT Core) ─────────────────

export interface AlexaStateStackProps extends cdk.StackProps {
  deployEnv: 'sandbox' | 'prod';
}

/**
 * The state table (each unit's latest status, what Alexa was last told, the event gateway grants),
 * the skill's Send Alexa Events credentials (a placeholder until Martin sets them), and the reporter:
 * an IoT rule hands it every petro/<thing>/status and a schedule sweeps for units gone quiet.
 */
export class AlexaStateStack extends cdk.Stack {
  readonly table: dynamodb.TableV2;
  readonly skillSecret: secretsmanager.Secret;
  readonly reporter: nodejs.NodejsFunction;

  constructor(scope: Construct, id: string, props: AlexaStateStackProps) {
    super(scope, id, props);
    const { deployEnv } = props;

    this.table = new dynamodb.TableV2(this, 'StateTable', {
      tableName: tableName(deployEnv),
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      billing: dynamodb.Billing.onDemand(),
      // Nothing here can't be rebuilt: statuses arrive every minute, grants come back on re-linking.
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // A random secret under a placeholder client ID: the reporter and AcceptGrant treat it as unset
    // until Martin puts the real pair with put-secret-value (which CloudFormation leaves alone).
    this.skillSecret = new secretsmanager.Secret(this, 'SkillMessagingSecret', {
      secretName: skillSecretName(deployEnv),
      description: `Petro Alexa skill's Send Alexa Events client ID and secret (${deployEnv}); set by hand, see docs/alexa-setup.md`,
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ clientId: 'NOT_SET' }),
        generateStringKey: 'clientSecret',
        excludePunctuation: true,
      },
    });

    const name = `petro-alexa-reporter-${deployEnv}`;
    this.reporter = new nodejs.NodejsFunction(this, 'Reporter', {
      functionName: name,
      description: 'Petro: keeps unit status for Alexa and sends ChangeReports',
      entry: path.join(lambdaDir, 'reporter.ts'),
      handler: 'handler',
      runtime: lambda.Runtime.NODEJS_22_X,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        DEPLOY_ENV: deployEnv,
        HOME_REGION: this.region,
        TABLE_NAME: this.table.tableName,
        SKILL_SECRET_ID: this.skillSecret.secretName,
      },
      bundling: { externalModules: [] },
      logGroup: logGroup(this, 'ReporterLogs', name),
    });
    this.table.grant(this.reporter, 'dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:DeleteItem', 'dynamodb:Scan');
    this.skillSecret.grantRead(this.reporter);

    // Every unit's status, with the Thing and IoT's receive time. This env's Things only.
    const rule = new iot.CfnTopicRule(this, 'StatusRule', {
      ruleName: `petro_alexa_status_${deployEnv}`,
      topicRulePayload: {
        sql: `SELECT *, topic(2) AS thing, timestamp() AS receivedAt FROM 'petro/+/status' WHERE startswith(topic(2), 'petro-${deployEnv}-')`,
        awsIotSqlVersion: '2016-03-23',
        ruleDisabled: false,
        actions: [{ lambda: { functionArn: this.reporter.functionArn } }],
      },
    });
    this.reporter.addPermission('IotStatusRule', {
      principal: new iam.ServicePrincipal('iot.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: rule.attrArn,
      sourceAccount: this.account,
    });

    new events.Rule(this, 'SweepSchedule', {
      ruleName: `petro-alexa-sweep-${deployEnv}`,
      description: 'Petro: report units that have stopped publishing as UNREACHABLE',
      schedule: events.Schedule.rate(cdk.Duration.minutes(2)),
      targets: [new targets.LambdaFunction(this.reporter, { event: events.RuleTargetInput.fromObject({ sweep: true }) })],
    });

    new cdk.CfnOutput(this, 'SkillSecretName', {
      value: this.skillSecret.secretName,
      description: "Put the skill's Send Alexa Events client ID and secret here (docs/alexa-setup.md)",
    });
  }
}

// ── The skill's Lambda (eu-west-1, Alexa's EU endpoint region) ───────────────

export interface AlexaStackProps extends cdk.StackProps {
  deployEnv: 'sandbox' | 'prod';
  /** Shared user pool ID (from AlexaAuthStack, cross-region). */
  userPoolId: string;
  /** Alexa account-linking client ID (from AlexaAuthStack, cross-region). */
  alexaClientId: string;
  /** Overrides the SSM lookup of the skill ID (tests, or `-c alexaSkillId=`). */
  skillId?: string;
  /** The region of IoT Core, the Things and the state table. */
  homeRegion: string;
}

export class AlexaStack extends cdk.Stack {
  readonly fn: nodejs.NodejsFunction;

  constructor(scope: Construct, id: string, props: AlexaStackProps) {
    super(scope, id, props);
    const { deployEnv, userPoolId, alexaClientId, homeRegion } = props;

    // The trigger names the skill ID, but the skill can only point at this Lambda once it exists:
    // deploy with the placeholder (no trigger), create the skill, set the parameter, deploy again.
    const skillId =
      props.skillId ?? ssm.StringParameter.valueFromLookup(this, skillIdParameter(deployEnv), SKILL_ID_PLACEHOLDER);

    const name = `petro-alexa-${deployEnv}`;
    const homeArn = (service: string, resource: string) =>
      `arn:${this.partition}:${service}:${homeRegion}:${this.account}:${resource}`;

    this.fn = new nodejs.NodejsFunction(this, 'AlexaHandler', {
      functionName: name,
      description: 'Petro Alexa Smart Home skill',
      entry: path.join(lambdaDir, 'handler.ts'),
      handler: 'handler',
      runtime: lambda.Runtime.NODEJS_22_X,
      // Alexa gives a directive 8 s; the handler waits up to 4 s for the unit to confirm.
      timeout: cdk.Duration.seconds(7),
      memorySize: 256,
      environment: {
        DEPLOY_ENV: deployEnv,
        HOME_REGION: homeRegion,
        TABLE_NAME: tableName(deployEnv),
        SKILL_SECRET_ID: skillSecretName(deployEnv),
        USER_POOL_ID: userPoolId,
        ALEXA_CLIENT_ID: alexaClientId,
      },
      bundling: { externalModules: [] },
      logGroup: logGroup(this, 'AlexaHandlerLogs', name),
    });

    this.fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['dynamodb:GetItem', 'dynamodb:PutItem'],
        resources: [homeArn('dynamodb', `table/${tableName(deployEnv)}`)],
      }),
    );
    // ListThings can't be narrowed to a resource; the handler keeps only this env's Petro Things.
    this.fn.addToRolePolicy(new iam.PolicyStatement({ actions: ['iot:ListThings'], resources: ['*'] }));
    this.fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['iot:Publish'],
        resources: [homeArn('iot', `topic/petro/petro-${deployEnv}-*/commands`)],
      }),
    );
    this.fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        // Secrets Manager adds six random characters to the name's ARN.
        resources: [homeArn('secretsmanager', `secret:${skillSecretName(deployEnv)}-??????`)],
      }),
    );

    if (skillId !== SKILL_ID_PLACEHOLDER) {
      if (!SKILL_ID_PATTERN.test(skillId)) {
        throw new Error(`Alexa skill ID "${skillId}" doesn't look like amzn1.ask.skill.<uuid>`);
      }
      this.fn.addPermission('AlexaSmartHomeTrigger', {
        principal: new iam.ServicePrincipal('alexa-connectedhome.amazon.com'),
        action: 'lambda:InvokeFunction',
        eventSourceToken: skillId,
      });
    } else {
      cdk.Annotations.of(this).addWarningV2(
        'petro:alexaSkillIdMissing',
        `SSM ${skillIdParameter(deployEnv)} is not set (in ${this.region}); the Alexa trigger is not created. See docs/alexa-setup.md.`,
      );
    }

    new cdk.CfnOutput(this, 'AlexaFunctionArn', {
      value: this.fn.functionArn,
      description: 'Smart Home skill endpoint (default and EU) for the skill manifest',
    });
  }
}
