import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/** The repository GitHub Actions runs in, from cdk.json's `github` context. */
export interface GithubRepo {
  owner: string;
  /** `gh api users/<owner> --jq .id` */
  ownerId: string;
  repo: string;
  /** `gh api repos/<owner>/<repo> --jq .id` */
  repoId: string;
}

/** Reads and checks cdk.json's `github` context: names, and the numeric ids GitHub gave them. */
export function githubRepoFrom(context: unknown): GithubRepo {
  const c = context as Record<string, unknown> | null | undefined;
  const ok =
    !!c &&
    typeof c.owner === 'string' &&
    typeof c.repo === 'string' &&
    /^[A-Za-z0-9-]+$/.test(c.owner) &&
    /^[A-Za-z0-9._-]+$/.test(c.repo) &&
    typeof c.ownerId === 'string' &&
    typeof c.repoId === 'string' &&
    /^[0-9]+$/.test(c.ownerId) &&
    /^[0-9]+$/.test(c.repoId);
  if (!ok) {
    throw new Error('cdk.json: context "github" must be { owner, ownerId, repo, repoId }, the ids as digit strings');
  }
  return { owner: c.owner, ownerId: c.ownerId, repo: c.repo, repoId: c.repoId } as GithubRepo;
}

export interface GithubCiStackProps extends cdk.StackProps {
  deployEnv: 'sandbox' | 'prod';
  github: GithubRepo;
}

/** The CI role's name: the deployment tracker allow-lists it by this name (nakomis-infra). */
export const ciRoleName = (deployEnv: string) => `nakomis-petro-github-ci-${deployEnv}`;

/** The read-only role PR and branch runs check the sandbox bucket with (sandbox only). */
export const ciReadRoleName = (deployEnv: string) => `nakomis-petro-github-ci-${deployEnv}-read`;

/**
 * The OIDC subject context the publishing role trusts. A job with an `environment:` is issued
 * `environment:<name>` in place of its ref, so prod (behind `production`) trusts that; sandbox's
 * publish jobs have no environment, so it trusts pushes to main only.
 */
export const publishContext = (deployEnv: 'sandbox' | 'prod') =>
  deployEnv === 'prod' ? 'environment:production' : 'ref:refs/heads/main';

/**
 * GitHub's OIDC subject carries immutable ids (repo:OWNER@OWNER_ID/REPO@REPO_ID:CONTEXT) as well as
 * the older name-only form; both are accepted, with the names pinned either way. The ids survive a
 * rename, so whoever later claims the name can't inherit the trust.
 */
export const oidcSubjects = (github: GithubRepo, context: string) => [
  `repo:${github.owner}@${github.ownerId}/${github.repo}@${github.repoId}:${context}`,
  `repo:${github.owner}/${github.repo}:${context}`,
];

/**
 * PETRO-9: the role GitHub Actions assumes to publish Petro's firmware for Fleet. Narrow on purpose
 * (tinycrypt's and nakostat's pattern): put and check builds under petro/ in this environment's
 * firmware bucket, and call the shared deployment tracker (which allow-lists the role in
 * nakomis-infra). Nothing else: CI synthesises the CDK but never deploys it, so the role has no
 * sts:AssumeRole on the CDK bootstrap roles (add `cdk-hnb659fds-*` here when it does).
 *
 * The sandbox publishing role trusts only pushes to main (the version job, which computes the version
 * from the tracker, and the sandbox publish): a branch or PR run can't publish. Prod's trusts only
 * jobs in the `production` GitHub environment, which Martin approves (and which is limited to main),
 * so neither a branch nor an unapproved run can publish to the units on the wall. In sandbox a
 * second, read-only role trusts any ref, for the PR check that version.txt isn't published yet: it
 * may only read and list the bucket's petro/ objects, and doesn't call the tracker. Forks get no
 * OIDC token.
 */
export class GithubCiStack extends cdk.Stack {
  public readonly role: iam.Role;
  /** The read-only role for PR and branch runs; sandbox only. */
  public readonly readRole?: iam.Role;

  constructor(scope: Construct, id: string, props: GithubCiStackProps) {
    super(scope, id, props);
    const { deployEnv, github } = props;

    // The account's one GitHub OIDC provider (made once per account, outside this repo).
    const provider = iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
      this,
      'GithubOidc',
      `arn:${this.partition}:iam::${this.account}:oidc-provider/token.actions.githubusercontent.com`,
    );
    const bucket = `nakomis-firmware-${deployEnv}`;
    const trust = (context: string) =>
      new iam.WebIdentityPrincipal(provider.openIdConnectProviderArn, {
        StringEquals: { 'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com' },
        StringLike: { 'token.actions.githubusercontent.com:sub': oidcSubjects(github, context) },
      });
    const objects = `arn:${this.partition}:s3:::${bucket}/petro/*`;
    // So a missing object answers 404, not 403 (unconditional: S3's implicit check carries no prefix).
    const list = () =>
      new iam.PolicyStatement({
        actions: ['s3:ListBucket'],
        resources: [`arn:${this.partition}:s3:::${bucket}`],
      });

    this.role = new iam.Role(this, 'CiRole', {
      roleName: ciRoleName(deployEnv),
      description: `Assumed by smart-switch (Petro) GitHub Actions to publish firmware (${deployEnv})`,
      maxSessionDuration: cdk.Duration.hours(1),
      assumedBy: trust(publishContext(deployEnv)),
    });

    this.role.addToPolicy(
      new iam.PolicyStatement({ actions: ['s3:PutObject', 's3:GetObject'], resources: [objects] }),
    );
    this.role.addToPolicy(list());
    // The deployment tracker (nakomis-infra's DeploymentTrackerStack) is a REST API in the prod
    // account, so the sandbox role calls it cross-account and needs this identity grant as well as
    // the tracker's resource-policy allow-list. Its account isn't this stack's to know: the resource
    // policy is what pins who may call it.
    this.role.addToPolicy(
      new iam.PolicyStatement({
        actions: ['execute-api:Invoke'],
        resources: [`arn:${this.partition}:execute-api:${this.region}:*:*/*/*/deployments/*`],
      }),
    );

    new cdk.CfnOutput(this, 'CiRoleArn', { value: this.role.roleArn });

    if (deployEnv === 'sandbox') {
      this.readRole = new iam.Role(this, 'CiReadRole', {
        roleName: ciReadRoleName(deployEnv),
        description: 'Assumed by smart-switch (Petro) GitHub Actions on PRs and branches: read-only (sandbox)',
        maxSessionDuration: cdk.Duration.hours(1),
        assumedBy: trust('*'),
      });
      this.readRole.addToPolicy(new iam.PolicyStatement({ actions: ['s3:GetObject'], resources: [objects] }));
      this.readRole.addToPolicy(list());
      new cdk.CfnOutput(this, 'CiReadRoleArn', { value: this.readRole.roleArn });
    }
  }
}
