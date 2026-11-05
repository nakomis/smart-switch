import * as fs from 'fs';
import * as path from 'path';

// Per-environment staging of the Alexa skill package (PETRO-8; Recipator's RECIP-66 pattern).
//
// alexa/skill-package/ is the single source: an ASK CLI-shaped skill.json and the icons. The JSON
// carries placeholder tokens that differ by environment: ${SKILL_NAME}, ${ENDPOINT_ARN} and
// ${TESTING_INSTRUCTIONS}. Sandbox and prod are separate skills ("Petro (sandbox)" stays in
// development; "Petro" is the one submitted for certification and published).
//
// stageSkillPackage copies the package to outDir and fills the tokens in. The endpoint is passed in
// (PetroAlexaStack's AlexaFunctionArn output), so staging is offline. Staged output goes under
// infra/build/ (git-ignored). The certification test account's password is never committed: it's
// passed in when staging for submission (docs/alexa-setup.md, Certification).

export type SkillEnv = 'sandbox' | 'prod';

export const SKILL_PACKAGE_DIR = path.join(__dirname, '../../alexa/skill-package');

export const SKILL_SETTINGS: Record<SkillEnv, { skillName: string }> = {
  sandbox: { skillName: 'Petro (sandbox)' },
  prod: { skillName: 'Petro' },
};

export interface StageOptions {
  /** ARN of the skill's Lambda (eu-west-1), written into the manifest endpoint. */
  endpointArn: string;
  /** The certification test account, for the certifier's testing instructions. */
  testAccount?: { username: string; password: string };
}

const LAMBDA_ARN = /^arn:aws:lambda:eu-west-1:\d{12}:function:petro-alexa-(sandbox|prod)$/;

export function testingInstructions(testAccount?: StageOptions['testAccount']): string {
  const account = testAccount
    ? `Sign in with username ${testAccount.username} and password ${testAccount.password}.`
    : 'The test account is given with the submission.';
  return [
    'Petro is a mains smart plug; the test account can see and switch one real unit, "Petro b5", with a lamp on it.',
    `Enable the skill and link the account: ${account}`,
    'Discover devices: one smart plug, "Petro b5", appears.',
    '"Alexa, turn on Petro b5" and "Alexa, turn off Petro b5" switch the lamp; the Alexa app shows the state and updates on its own when the unit is switched at its button.',
    'If the unit has been set to on or off at its own button, or a safety trip has opened it, Alexa reports that it cannot switch it: that is deliberate (the button overrides Alexa), not a fault.',
  ].join(' ');
}

export function defaultStageDir(env: SkillEnv): string {
  return path.join(__dirname, '../build/skill-package', env);
}

/** Copies alexa/skill-package/ to outDir with this environment's values filled in. */
export function stageSkillPackage(env: SkillEnv, outDir: string, opts: StageOptions): void {
  const settings = SKILL_SETTINGS[env];
  if (!settings) throw new Error(`Unknown skill environment: ${env}`);
  const m = LAMBDA_ARN.exec(opts.endpointArn);
  if (!m) throw new Error(`endpointArn is not a petro-alexa Lambda ARN in eu-west-1: ${opts.endpointArn}`);
  if (m[1] !== env) throw new Error(`endpointArn is the ${m[1]} Lambda, not ${env}'s`);

  const tokens: Record<string, string> = {
    SKILL_NAME: settings.skillName,
    ENDPOINT_ARN: opts.endpointArn,
    TESTING_INSTRUCTIONS: testingInstructions(opts.testAccount),
  };

  // Start clean so files removed from the source don't linger in the staged copy.
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.cpSync(SKILL_PACKAGE_DIR, outDir, { recursive: true });

  for (const file of jsonFiles(outDir)) {
    const filled = fs.readFileSync(file, 'utf8').replace(/\$\{([A-Z_]+)\}/g, (match, name: string) => {
      if (!(name in tokens)) throw new Error(`Unknown token ${match} in ${path.relative(outDir, file)}`);
      // Every token sits inside a JSON string: escape it as one.
      return JSON.stringify(tokens[name]).slice(1, -1);
    });
    JSON.parse(filled); // a value that broke the JSON would fail here, not at ASK upload
    fs.writeFileSync(file, filled);
  }
}

function jsonFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) return jsonFiles(p);
    return entry.name.endsWith('.json') ? [p] : [];
  });
}
