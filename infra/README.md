# infra

Petro's AWS infrastructure: CDK in TypeScript, pnpm, jest. The house pattern (nakostat, tinycrypt,
katooni): `bin/petro.ts` gated on `NPM_ENVIRONMENT` (`sandbox` or `prod`), stacks in `lib/`, tests in
`test/`. The account comes from the profile the deploy runs under, never a literal; the region is
eu-west-2.

## Stacks

| Stack | What |
|---|---|
| `PetroDeviceStack` | One IoT Thing per unit, `petro-<env>-bN`, from `devices.json`, and the `petro-device-<env>` policy |
| `PetroGithubCiStack` | `nakomis-petro-github-ci-<env>`, the role GitHub Actions publishes firmware with, and in sandbox `nakomis-petro-github-ci-sandbox-read` for PR runs (PETRO-9) |

### The CI role

`nakomis-petro-github-ci-<env>` may put and read objects under `petro/` in
`nakomis-firmware-<env>` (and list the bucket, so a missing object is a 404), and call the shared
deployment tracker. Nothing else: CI synthesises the CDK but doesn't deploy it. It trusts the
account's GitHub OIDC provider, for this repository only, in both subject forms
(`repo:nakomis@<owner id>/smart-switch@<repo id>:…` and `repo:nakomis/smart-switch:…`): the ids are
`cdk.json`'s `github` context. Sandbox's trusts only pushes to `main` (subject
`ref:refs/heads/main`: the version job and the sandbox publish, which have no GitHub environment);
prod's trusts only jobs in the `production` GitHub environment (subject `environment:production`),
which Martin approves and which is limited to `main`.

In sandbox only, `nakomis-petro-github-ci-sandbox-read` is for PR and branch runs (it trusts any
ref): it may read and list `petro/` in `nakomis-firmware-sandbox`, for the check that `version.txt`
isn't published yet, and nothing else. It doesn't call the tracker.

The tracker allow-lists both publishing roles by ARN in nakomis-infra (`ALLOWED_CI_ROLE_ARNS`; the
read role needn't be), and the workflow finds the roles in the repository variables
`AWS_SANDBOX_ROLE_ARN`, `AWS_SANDBOX_READ_ROLE_ARN` (the stack's `CiReadRoleArn` output) and
`AWS_PROD_ROLE_ARN`:

```bash
NPM_ENVIRONMENT=prod npx cdk deploy --profile nakom.is-admin PetroGithubCiStack
gh variable set AWS_PROD_ROLE_ARN -R nakomis/smart-switch --body "$(aws cloudformation describe-stacks \
  --profile nakom.is-admin --stack-name PetroGithubCiStack \
  --query "Stacks[0].Outputs[?OutputKey=='CiRoleArn'].OutputValue" --output text)"
```

### Units and Fleet

`devices.json` lists each environment's units (prod `b1` to `b5`, the five rev B boards; sandbox `b1`
for the bench). It's committed, so every deploy declares every unit: **one left out of a deploy has
its Thing deleted**, but not its certificate, which stays active with the
policy attached (it can't connect without its Thing, but it's still a live credential). Before
removing a unit, delete its certificates by hand: `detach-policy`, `detach-thing-principal`,
`update-certificate --new-status INACTIVE`, `delete-certificate`. Add a unit there, deploy, then provision it (`firmware/README.md`, Provisioning).

Each Thing carries the attributes Fleet (nakomis-fleet) reads: `project=petro`,
`deviceType=smart-switch`, `capabilities=ota` (plain OTA; `ota-signed` when PETRO-9 signs builds).
IoT allows only three attributes on a Thing with no type, so there's no `hwType`. Fleet needs no
change for Petro: it lists the Thing, resolves its firmware project from the bucket's `petro/`
prefix, and adds a registry row the first time the unit publishes.

The policy lets a certificate connect only as the Thing it's attached to (client id = Thing name),
publish only `petro/<thing>/responses` and `petro/<thing>/status`, and subscribe to and receive only
`petro/<thing>/commands`: Fleet's topics, its own only. No certificate is made here: the private key
must never pass through CloudFormation; `firmware/scripts/provision-device.sh` makes and attaches it.

## Commands

```bash
cd infra
pnpm install
TEST_MAX_WORKERS=2 pnpm test       # jest with coverage (≥ 70 %)
pnpm build                         # type-check
pnpm run synth-sandbox             # or ci-synth-sandbox / ci-synth-prod, with no credentials
pnpm run deploy-sandbox            # AWS_PROFILE nakom.is-sandbox
pnpm run diff-prod                 # nakom.is-admin: look before you deploy
pnpm run deploy-prod               # nakom.is-admin
```

Running several CDK commands at once? Give each its own `--output <dir>.out`.
