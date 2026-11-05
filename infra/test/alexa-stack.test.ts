import * as cdk from 'aws-cdk-lib';
import { Annotations, Match, Template } from 'aws-cdk-lib/assertions';
import {
  AlexaAuthStack,
  AlexaStack,
  AlexaStateStack,
  alexaRedirectUris,
  SKILL_ID_PLACEHOLDER,
  VENDOR_ID_PLACEHOLDER,
} from '../lib/alexa-stack';

const ACCOUNT = '000000000000';
const SKILL = 'amzn1.ask.skill.12345678-1234-1234-1234-123456789012';

const newApp = () => new cdk.App({ context: { '@aws-cdk/core:enablePartitionLiterals': true } });

const authStack = (deployEnv: 'sandbox' | 'prod' = 'sandbox', vendorId: string = 'M1VENDOR') => {
  const app = newApp();
  return new AlexaAuthStack(app, 'Auth', {
    env: { account: ACCOUNT, region: 'eu-west-2' },
    deployEnv,
    deviceNames: ['b1', 'b2'],
    vendorId,
    crossRegionReferences: true,
  });
};

const skillStack = (skillId: string, deployEnv: 'sandbox' | 'prod' = 'sandbox') => {
  const app = newApp();
  return new AlexaStack(app, 'Skill', {
    env: { account: ACCOUNT, region: 'eu-west-1' },
    deployEnv,
    homeRegion: 'eu-west-2',
    userPoolId: 'eu-west-2_pool',
    alexaClientId: 'client',
    skillId,
  });
};

const stateStack = (deployEnv: 'sandbox' | 'prod' = 'sandbox') => {
  const app = newApp();
  return new AlexaStateStack(app, 'State', { env: { account: ACCOUNT, region: 'eu-west-2' }, deployEnv });
};

type Statement = { Action: string | string[]; Resource: unknown };
const statementsOf = (t: Template): Statement[] =>
  Object.values(t.findResources('AWS::IAM::Policy')).flatMap(
    (p) => (p as { Properties: { PolicyDocument: { Statement: Statement[] } } }).Properties.PolicyDocument.Statement,
  );
const actionsOf = (t: Template) => statementsOf(t).flatMap((s) => ([] as string[]).concat(s.Action));

describe('AlexaAuthStack', () => {
  test('an auth-code client on the shared pool, Cognito users only, redirecting to Alexa', () => {
    const t = Template.fromStack(authStack());
    t.hasResourceProperties('AWS::Cognito::UserPoolClient', {
      ClientName: 'petro-alexa-sandbox',
      GenerateSecret: true,
      AllowedOAuthFlows: ['code'],
      AllowedOAuthScopes: Match.arrayWith(['openid', 'profile', 'email']),
      CallbackURLs: alexaRedirectUris('M1VENDOR'),
      SupportedIdentityProviders: ['COGNITO'],
      EnableTokenRevocation: true,
      PreventUserExistenceErrors: 'ENABLED',
    });
  });

  test('has its own managed login style (or the hosted page says "Login pages unavailable")', () => {
    const t = Template.fromStack(authStack());
    t.hasResourceProperties('AWS::Cognito::ManagedLoginBranding', {
      UseCognitoProvidedValues: false,
      Settings: Match.objectLike({ categories: Match.objectLike({ global: Match.objectLike({ colorSchemeMode: 'DARK' }) }) }),
    });
  });

  test('a group for every unit and one for all of them', () => {
    const t = Template.fromStack(authStack());
    for (const g of ['petro', 'petro-b1', 'petro-b2']) {
      t.hasResourceProperties('AWS::Cognito::UserPoolGroup', { GroupName: g });
    }
    t.resourceCountIs('AWS::Cognito::UserPoolGroup', 3);
  });

  test('publishes the client ID to SSM', () => {
    Template.fromStack(authStack('prod')).hasResourceProperties('AWS::SSM::Parameter', {
      Name: '/petro/prod/alexa/cognito/client-id',
    });
  });

  test('warns while the vendor ID is a placeholder', () => {
    const stack = authStack('sandbox', VENDOR_ID_PLACEHOLDER);
    Annotations.fromStack(stack).hasWarning('*', Match.stringLikeRegexp('alexa/vendorId is not set'));
  });
});

describe('AlexaStateStack', () => {
  test('the state table, keyed on pk, on demand', () => {
    Template.fromStack(stateStack()).hasResourceProperties('AWS::DynamoDB::GlobalTable', {
      TableName: 'petro-alexa-sandbox',
      KeySchema: [{ AttributeName: 'pk', KeyType: 'HASH' }],
      BillingMode: 'PAY_PER_REQUEST',
    });
  });

  test('a placeholder skill secret the code treats as unset', () => {
    Template.fromStack(stateStack('prod')).hasResourceProperties('AWS::SecretsManager::Secret', {
      Name: 'petro/prod/alexa/skill-messaging',
      GenerateSecretString: Match.objectLike({ SecretStringTemplate: '{"clientId":"NOT_SET"}', GenerateStringKey: 'clientSecret' }),
    });
  });

  test("an IoT rule hands this env's statuses to the reporter, with the Thing and receive time", () => {
    const t = Template.fromStack(stateStack());
    t.hasResourceProperties('AWS::IoT::TopicRule', {
      TopicRulePayload: Match.objectLike({
        Sql: "SELECT *, topic(2) AS thing, timestamp() AS receivedAt FROM 'petro/+/status' WHERE startswith(topic(2), 'petro-sandbox-')",
        AwsIotSqlVersion: '2016-03-23',
      }),
    });
    t.hasResourceProperties('AWS::Lambda::Permission', { Principal: 'iot.amazonaws.com', Action: 'lambda:InvokeFunction' });
  });

  test('a two-minute sweep', () => {
    Template.fromStack(stateStack()).hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'rate(2 minutes)',
      Targets: [Match.objectLike({ Input: '{"sweep":true}' })],
    });
  });

  test('the reporter reads and writes the table and reads the secret, nothing more', () => {
    const t = Template.fromStack(stateStack());
    t.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'petro-alexa-reporter-sandbox',
      Runtime: 'nodejs22.x',
      Environment: { Variables: Match.objectLike({ DEPLOY_ENV: 'sandbox', HOME_REGION: 'eu-west-2' }) },
    });
    expect(new Set(actionsOf(t))).toEqual(
      new Set([
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:DeleteItem',
        'dynamodb:Scan',
        'secretsmanager:GetSecretValue',
        'secretsmanager:DescribeSecret',
      ]),
    );
  });
});

describe('AlexaStack', () => {
  test('the skill Lambda, in eu-west-1, pointed at eu-west-2', () => {
    const t = Template.fromStack(skillStack(SKILL));
    t.hasResourceProperties('AWS::Lambda::Function', {
      FunctionName: 'petro-alexa-sandbox',
      Runtime: 'nodejs22.x',
      Timeout: 7,
      Environment: {
        Variables: Match.objectLike({
          DEPLOY_ENV: 'sandbox',
          HOME_REGION: 'eu-west-2',
          TABLE_NAME: 'petro-alexa-sandbox',
          SKILL_SECRET_ID: 'petro/sandbox/alexa/skill-messaging',
          USER_POOL_ID: 'eu-west-2_pool',
          ALEXA_CLIENT_ID: 'client',
        }),
      },
    });
  });

  test("may publish only this env's command topics, and touch only its table and secret", () => {
    const t = Template.fromStack(skillStack(SKILL, 'prod'));
    const byAction = (a: string) => statementsOf(t).filter((s) => ([] as string[]).concat(s.Action).includes(a));
    expect(byAction('iot:Publish')[0].Resource).toBe(`arn:aws:iot:eu-west-2:${ACCOUNT}:topic/petro/petro-prod-*/commands`);
    expect(byAction('dynamodb:PutItem')[0].Resource).toBe(`arn:aws:dynamodb:eu-west-2:${ACCOUNT}:table/petro-alexa-prod`);
    expect(byAction('secretsmanager:GetSecretValue')[0].Resource).toBe(
      `arn:aws:secretsmanager:eu-west-2:${ACCOUNT}:secret:petro/prod/alexa/skill-messaging-??????`,
    );
    expect(actionsOf(t)).not.toContain('dynamodb:Scan');
  });

  test('with the skill ID: the Alexa Smart Home trigger, for that skill only', () => {
    Template.fromStack(skillStack(SKILL)).hasResourceProperties('AWS::Lambda::Permission', {
      Principal: 'alexa-connectedhome.amazon.com',
      EventSourceToken: SKILL,
    });
  });

  test('without it: no trigger, and a warning', () => {
    const stack = skillStack(SKILL_ID_PLACEHOLDER);
    Template.fromStack(stack).resourceCountIs('AWS::Lambda::Permission', 0);
    Annotations.fromStack(stack).hasWarning('*', Match.stringLikeRegexp('alexa/skillId is not set'));
  });

  test('refuses a skill ID that is not one', () => {
    expect(() => skillStack('not-a-skill')).toThrow(/doesn't look like/);
  });
});
