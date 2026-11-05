import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { GithubCiStack, ciRoleName, githubRepoFrom } from '../lib/github-ci-stack';

const ACCOUNT = '000000000000';
const CONTEXT = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'cdk.json'), 'utf8')).context;
const GITHUB = githubRepoFrom(CONTEXT.github);

const synth = (deployEnv: 'sandbox' | 'prod') => {
  const app = new cdk.App({ context: { '@aws-cdk/core:enablePartitionLiterals': true } });
  const stack = new GithubCiStack(app, 'Test', {
    env: { account: ACCOUNT, region: 'eu-west-2' },
    deployEnv,
    github: GITHUB,
  });
  return Template.fromStack(stack);
};

type Statement = { Action: string | string[]; Resource: string | string[]; Condition?: unknown };

const role = (t: Template) => {
  const [r] = Object.values(t.findResources('AWS::IAM::Role')) as {
    Properties: {
      RoleName: string;
      MaxSessionDuration: number;
      AssumeRolePolicyDocument: { Statement: (Statement & { Principal: { Federated: string } })[] };
    };
  }[];
  return r.Properties;
};

const statements = (t: Template): Statement[] =>
  (Object.values(t.findResources('AWS::IAM::Policy')) as {
    Properties: { PolicyDocument: { Statement: Statement[] } };
  }[]).flatMap((p) => p.Properties.PolicyDocument.Statement);

const actions = (s: Statement) => ([] as string[]).concat(s.Action);
const resources = (s: Statement) => ([] as string[]).concat(s.Resource);

describe('GithubCiStack', () => {
  const sandbox = synth('sandbox');
  const prod = synth('prod');

  test('cdk.json carries the repository ids GitHub gave it', () => {
    expect(GITHUB).toEqual({ owner: 'nakomis', ownerId: '1488244', repo: 'smart-switch', repoId: '1443001490' });
  });

  test('one role per environment, named for the tracker allow-list', () => {
    sandbox.resourceCountIs('AWS::IAM::Role', 1);
    expect(role(sandbox).RoleName).toBe('nakomis-petro-github-ci-sandbox');
    expect(role(prod).RoleName).toBe('nakomis-petro-github-ci-prod');
    expect(ciRoleName('prod')).toBe('nakomis-petro-github-ci-prod');
    expect(role(sandbox).MaxSessionDuration).toBe(3600);
  });

  test("trusts the account's GitHub OIDC provider, for sts.amazonaws.com only", () => {
    const [trust] = role(sandbox).AssumeRolePolicyDocument.Statement;
    expect(trust.Action).toBe('sts:AssumeRoleWithWebIdentity');
    expect(trust.Principal.Federated).toBe(
      `arn:aws:iam::${ACCOUNT}:oidc-provider/token.actions.githubusercontent.com`,
    );
    expect(trust.Condition).toMatchObject({
      StringEquals: { 'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com' },
    });
  });

  test('sandbox trusts any ref of this repository, in both subject forms', () => {
    const [trust] = role(sandbox).AssumeRolePolicyDocument.Statement;
    expect(trust.Condition).toMatchObject({
      StringLike: {
        'token.actions.githubusercontent.com:sub': [
          'repo:nakomis@1488244/smart-switch@1443001490:*',
          'repo:nakomis/smart-switch:*',
        ],
      },
    });
  });

  test('prod trusts only the production environment (Martin approves it)', () => {
    const [trust] = role(prod).AssumeRolePolicyDocument.Statement;
    expect(trust.Condition).toMatchObject({
      StringLike: {
        'token.actions.githubusercontent.com:sub': [
          'repo:nakomis@1488244/smart-switch@1443001490:environment:production',
          'repo:nakomis/smart-switch:environment:production',
        ],
      },
    });
  });

  test.each(['sandbox', 'prod'] as const)('%s writes firmware only under petro/ in its own bucket', (env) => {
    const s = statements(env === 'sandbox' ? sandbox : prod);
    const put = s.find((x) => actions(x).includes('s3:PutObject'))!;
    expect(resources(put)).toEqual([`arn:aws:s3:::nakomis-firmware-${env}/petro/*`]);
    expect(actions(put).sort()).toEqual(['s3:GetObject', 's3:PutObject']);
    const list = s.find((x) => actions(x).includes('s3:ListBucket'))!;
    expect(resources(list)).toEqual([`arn:aws:s3:::nakomis-firmware-${env}`]);
  });

  test('may call only the deployment tracker, and nothing else', () => {
    for (const t of [sandbox, prod]) {
      const s = statements(t);
      const invoke = s.find((x) => actions(x).includes('execute-api:Invoke'))!;
      expect(resources(invoke)).toEqual(['arn:aws:execute-api:eu-west-2:*:*/*/*/deployments/*']);
      const all = s.flatMap(actions).sort();
      expect(all).toEqual(['execute-api:Invoke', 's3:GetObject', 's3:ListBucket', 's3:PutObject']);
      // No CDK deploys from CI, so no bootstrap roles; no account ids written into the policies.
      expect(JSON.stringify(s)).not.toMatch(/sts:AssumeRole|[0-9]{12}/);
    }
  });

  test('outputs the role ARN for the AWS_*_ROLE_ARN repo variables', () => {
    sandbox.hasOutput('CiRoleArn', {});
  });
});

describe('githubRepoFrom', () => {
  test.each([
    undefined,
    null,
    {},
    { ...GITHUB, ownerId: 1488244 },
    { ...GITHUB, repoId: 'abc' },
    { ...GITHUB, owner: 'nako mis' },
    { ...GITHUB, repo: 'smart/switch' },
  ])('refuses %p', (c) => {
    expect(() => githubRepoFrom(c)).toThrow(/context "github"/);
  });
});
