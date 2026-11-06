#!/usr/bin/env node
import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { AlexaAuthStack, AlexaStack, AlexaStateStack } from '../lib/alexa-stack';
import { DeviceStack } from '../lib/device-stack';
import { GithubCiStack, githubRepoFrom } from '../lib/github-ci-stack';
import { deployEnvFrom, deviceNamesFor } from '../lib/devices';

const deployEnv = deployEnvFrom(process.env.NPM_ENVIRONMENT);

// The account comes from the profile the deploy runs under, never a literal.
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION ?? 'eu-west-2' };

const app = new cdk.App();

const deviceNames = deviceNamesFor(
  JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'devices.json'), 'utf8')),
  deployEnv,
);

new DeviceStack(app, 'PetroDeviceStack', {
  env,
  deployEnv,
  deviceNames,
  description: `Petro smart switches as IoT Things, for Fleet (${deployEnv})`,
});

// PETRO-9: the role CI publishes firmware with. The repository's names and GitHub ids are cdk.json's
// `github` context (from `gh api users/nakomis --jq .id` and `gh api repos/nakomis/smart-switch --jq .id`).
new GithubCiStack(app, 'PetroGithubCiStack', {
  env,
  deployEnv,
  github: githubRepoFrom(app.node.tryGetContext('github')),
  description: `Petro GitHub Actions role: publish firmware for Fleet (${deployEnv})`,
});

// PETRO-8: Alexa Smart Home. The account-linking client sits with the shared pool and the reporter
// with IoT Core (both eu-west-2); the skill's Lambda runs in eu-west-1, Alexa's EU endpoint region.
// Two-step first deploy: docs/alexa-setup.md. `-c alexaSkillId=… -c alexaVendorId=…` skip the SSM
// lookups (CI synthesises without credentials).
const homeRegion = env.region;
const alexaAuth = new AlexaAuthStack(app, 'PetroAlexaAuthStack', {
  env,
  deployEnv,
  deviceNames,
  vendorId: app.node.tryGetContext('alexaVendorId'),
  crossRegionReferences: true,
  description: `Petro: Cognito client for Alexa account linking (${deployEnv})`,
});

new AlexaStateStack(app, 'PetroAlexaStateStack', {
  env,
  deployEnv,
  description: `Petro: unit status for Alexa, and its ChangeReports (${deployEnv})`,
});

new AlexaStack(app, 'PetroAlexaStack', {
  env: { account: env.account, region: 'eu-west-1' },
  deployEnv,
  homeRegion,
  userPoolId: alexaAuth.userPoolId,
  alexaClientId: alexaAuth.client.userPoolClientId,
  skillId: app.node.tryGetContext('alexaSkillId'),
  crossRegionReferences: true,
  description: `Petro: Alexa Smart Home skill Lambda (${deployEnv})`,
});

const { version: infraVersion } = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'version.json'), 'utf8'));
cdk.Tags.of(app).add('MH-Project', 'petro');
cdk.Tags.of(app).add('MH-Version', infraVersion);
cdk.Tags.of(app).add('Project', 'petro');
