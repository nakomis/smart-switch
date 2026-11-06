import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { GithubCiStack, ciReadRoleName, ciRoleName, githubRepoFrom, publishContext } from '../lib/github-ci-stack';

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

type RoleProps = {
  RoleName: string;
  MaxSessionDuration: number;
  AssumeRolePolicyDocument: { Statement: (Statement & { Principal: { Federated: string } })[] };
};

const roleResources = (t: Template) =>
  t.findResources('AWS::IAM::Role') as Record<string, { Properties: RoleProps }>;

/** The publishing role (CiRole), or the sandbox read-only role (CiReadRole). */
const role = (t: Template, which: 'CiRole' | 'CiReadRole' = 'CiRole'): RoleProps => {
  // Logical ids are the construct id plus a hash: CiRole… and CiReadRole… don't share a prefix.
  const [r] = Object.entries(roleResources(t)).filter(([id]) => id.startsWith(which));
  return r[1].Properties;
};

/** The statements of the policies attached to the role whose logical id starts with `which`. */
const statements = (t: Template, which: 'CiRole' | 'CiReadRole' = 'CiRole'): Statement[] =>
  (Object.values(t.findResources('AWS::IAM::Policy')) as {
    Properties: { PolicyDocument: { Statement: Statement[] }; Roles: { Ref: string }[] };
  }[])
    .filter((p) => p.Properties.Roles.some((r) => r.Ref.startsWith(which)))
    .flatMap((p) => p.Properties.PolicyDocument.Statement);

const actions = (s: Statement) => ([] as string[]).concat(s.Action);
const resources = (s: Statement) => ([] as string[]).concat(s.Resource);

describe('GithubCiStack', () => {
  const sandbox = synth('sandbox');
  const prod = synth('prod');

  test('cdk.json carries the repository ids GitHub gave it', () => {
    expect(GITHUB).toEqual({ owner: 'nakomis', ownerId: '1488244', repo: 'smart-switch', repoId: '1443001490' });
  });

  test('a publishing role per environment, named for the tracker allow-list; a read role in sandbox', () => {
    sandbox.resourceCountIs('AWS::IAM::Role', 2);
    prod.resourceCountIs('AWS::IAM::Role', 1);
    expect(role(sandbox).RoleName).toBe('nakomis-petro-github-ci-sandbox');
    expect(role(sandbox, 'CiReadRole').RoleName).toBe('nakomis-petro-github-ci-sandbox-read');
    expect(ciReadRoleName('sandbox')).toBe('nakomis-petro-github-ci-sandbox-read');
    expect(role(sandbox, 'CiReadRole').MaxSessionDuration).toBe(3600);
    expect(role(prod).RoleName).toBe('nakomis-petro-github-ci-prod');
    expect(ciRoleName('prod')).toBe('nakomis-petro-github-ci-prod');
    expect(role(sandbox).MaxSessionDuration).toBe(3600);
  });

  test.each([
    ['sandbox', 'CiRole'],
    ['sandbox', 'CiReadRole'],
    ['prod', 'CiRole'],
  ] as const)("%s %s trusts the account's GitHub OIDC provider, for sts.amazonaws.com only", (env, which) => {
    const [trust] = role(env === 'sandbox' ? sandbox : prod, which).AssumeRolePolicyDocument.Statement;
    expect(trust.Action).toBe('sts:AssumeRoleWithWebIdentity');
    expect(trust.Principal.Federated).toBe(
      `arn:aws:iam::${ACCOUNT}:oidc-provider/token.actions.githubusercontent.com`,
    );
    expect(trust.Condition).toMatchObject({
      StringEquals: { 'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com' },
    });
  });

  test('sandbox publishes only from pushes to main, in both subject forms', () => {
    expect(publishContext('sandbox')).toBe('ref:refs/heads/main');
    const [trust] = role(sandbox).AssumeRolePolicyDocument.Statement;
    expect(trust.Condition).toEqual({
      StringEquals: { 'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com' },
      StringLike: {
        'token.actions.githubusercontent.com:sub': [
          'repo:nakomis@1488244/smart-switch@1443001490:ref:refs/heads/main',
          'repo:nakomis/smart-switch:ref:refs/heads/main',
        ],
      },
    });
  });

  test('the sandbox read role trusts any ref of this repository, in both subject forms', () => {
    const [trust] = role(sandbox, 'CiReadRole').AssumeRolePolicyDocument.Statement;
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
    expect(publishContext('prod')).toBe('environment:production');
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

  test('the sandbox read role may only read and list petro/ in the sandbox bucket', () => {
    const s = statements(sandbox, 'CiReadRole');
    expect(s.flatMap(actions).sort()).toEqual(['s3:GetObject', 's3:ListBucket']);
    const get = s.find((x) => actions(x).includes('s3:GetObject'))!;
    expect(resources(get)).toEqual(['arn:aws:s3:::nakomis-firmware-sandbox/petro/*']);
    const list = s.find((x) => actions(x).includes('s3:ListBucket'))!;
    expect(resources(list)).toEqual(['arn:aws:s3:::nakomis-firmware-sandbox']);
    expect(JSON.stringify(s)).not.toMatch(/PutObject|execute-api|sts:AssumeRole|[0-9]{12}/);
  });

  test('outputs the role ARNs for the AWS_*_ROLE_ARN repo variables', () => {
    sandbox.hasOutput('CiRoleArn', {});
    sandbox.hasOutput('CiReadRoleArn', {});
    prod.hasOutput('CiRoleArn', {});
    expect(Object.keys(prod.findOutputs('CiReadRoleArn'))).toEqual([]);
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
