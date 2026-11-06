import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { defaultStageDir, SKILL_PACKAGE_DIR, stageSkillPackage, testingInstructions } from '../lib/skill-package';

const ARN = 'arn:aws:lambda:eu-west-1:000000000000:function:petro-alexa-sandbox';
const PROD_ARN = 'arn:aws:lambda:eu-west-1:000000000000:function:petro-alexa-prod';
const readJson = (...p: string[]) => JSON.parse(fs.readFileSync(path.join(...p), 'utf8'));
const pngSize = (file: string) => {
  const b = fs.readFileSync(file);
  expect(b.subarray(1, 4).toString()).toBe('PNG');
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
};

let tmp: string;
beforeEach(() => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-package-'));
});
afterEach(() => {
  fs.rmSync(tmp, { recursive: true, force: true });
});

describe('source skill package', () => {
  const manifest = readJson(SKILL_PACKAGE_DIR, 'skill.json').manifest;

  test('a public Smart Home skill, en-GB only, in GB only', () => {
    const pub = manifest.publishingInformation;
    expect(pub.distributionMode).toBe('PUBLIC');
    expect(pub.isAvailableWorldwide).toBe(false);
    expect(pub.distributionCountries).toEqual(['GB']);
    expect(pub.category).toBe('SMART_HOME');
    expect(Object.keys(pub.locales)).toEqual(['en-GB']);
  });

  test('the privacy policy, and permission to send Alexa events (ChangeReports)', () => {
    expect(manifest.privacyAndCompliance.locales['en-GB'].privacyPolicyUrl).toBe('https://nakom.is/privacy-policy');
    expect(manifest.permissions).toEqual([{ name: 'alexa::async_event:write' }]);
  });

  test('a v3 Smart Home endpoint, default and EU', () => {
    const smartHome = manifest.apis.smartHome;
    expect(smartHome.protocolVersion).toBe('3');
    expect(smartHome.endpoint.uri).toBe('${ENDPOINT_ARN}');
    expect(smartHome.regions.EU.endpoint.uri).toBe('${ENDPOINT_ARN}');
  });

  test('icons at 108 and 512 px', () => {
    const locale = manifest.publishingInformation.locales['en-GB'];
    expect(pngSize(path.join(SKILL_PACKAGE_DIR, locale.smallIconUri.replace('file://', '')))).toEqual([108, 108]);
    expect(pngSize(path.join(SKILL_PACKAGE_DIR, locale.largeIconUri.replace('file://', '')))).toEqual([512, 512]);
  });
});

describe('stageSkillPackage', () => {
  test.each([
    ['sandbox', ARN, 'Petro (sandbox)'],
    ['prod', PROD_ARN, 'Petro'],
  ] as const)('%s: fills the name and endpoint', (env, arn, name) => {
    stageSkillPackage(env, tmp, { endpointArn: arn });
    const manifest = readJson(tmp, 'skill.json').manifest;
    expect(manifest.publishingInformation.locales['en-GB'].name).toBe(name);
    expect(manifest.apis.smartHome.endpoint.uri).toBe(arn);
    expect(manifest.apis.smartHome.regions.EU.endpoint.uri).toBe(arn);
    expect(fs.readFileSync(path.join(tmp, 'skill.json'), 'utf8')).not.toMatch(/\$\{/);
    expect(fs.existsSync(path.join(tmp, 'assets/images/en-GB_largeIconUri.png'))).toBe(true);
  });

  test('puts the test account in the testing instructions only when given, JSON-escaped', () => {
    stageSkillPackage('prod', tmp, { endpointArn: PROD_ARN });
    expect(readJson(tmp, 'skill.json').manifest.publishingInformation.testingInstructions).toMatch(/given with the submission/);
    stageSkillPackage('prod', tmp, { endpointArn: PROD_ARN, testAccount: { username: 'cert', password: 'p"a\\ss' } });
    const text = readJson(tmp, 'skill.json').manifest.publishingInformation.testingInstructions;
    expect(text).toContain('username cert and password p"a\\ss');
  });

  test('says what certification needs', () => {
    const text = testingInstructions();
    expect(text).toMatch(/Petro b5/);
    expect(text).toMatch(/button overrides Alexa/);
  });

  test("refuses an endpoint that isn't this env's petro-alexa Lambda in eu-west-1", () => {
    expect(() => stageSkillPackage('sandbox', tmp, { endpointArn: '${ENDPOINT_ARN}' })).toThrow(/not a petro-alexa/);
    expect(() => stageSkillPackage('sandbox', tmp, { endpointArn: ARN.replace('eu-west-1', 'eu-west-2') })).toThrow(/not a petro-alexa/);
    expect(() => stageSkillPackage('prod', tmp, { endpointArn: ARN })).toThrow(/sandbox Lambda, not prod/);
  });

  test('refuses an unknown environment', () => {
    expect(() => stageSkillPackage('staging' as 'prod', tmp, { endpointArn: PROD_ARN })).toThrow(/Unknown skill environment/);
  });

  test('stages under infra/build/skill-package/{env} by default', () => {
    expect(defaultStageDir('sandbox')).toBe(path.resolve(__dirname, '../build/skill-package/sandbox'));
  });
});
