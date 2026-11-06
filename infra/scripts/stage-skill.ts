// Stages alexa/skill-package/ for one environment (docs/alexa-setup.md):
//
//   pnpm run stage-skill <sandbox|prod> <AlexaFunctionArn> [outDir]
//
// For the certification submission, set PETRO_CERT_USERNAME and PETRO_CERT_PASSWORD to put the test
// account in the testing instructions (the staged copy is git-ignored; never commit it).
import { defaultStageDir, type SkillEnv, stageSkillPackage } from '../lib/skill-package';

const [env, endpointArn, outDir] = process.argv.slice(2);
if ((env !== 'sandbox' && env !== 'prod') || !endpointArn) {
  console.error('usage: pnpm run stage-skill <sandbox|prod> <AlexaFunctionArn> [outDir]');
  process.exit(2);
}
const { PETRO_CERT_USERNAME: username, PETRO_CERT_PASSWORD: password } = process.env;
const dir = outDir ?? defaultStageDir(env as SkillEnv);
stageSkillPackage(env as SkillEnv, dir, {
  endpointArn,
  testAccount: username && password ? { username, password } : undefined,
});
console.log(dir);
