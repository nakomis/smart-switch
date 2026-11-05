/**
 * Reads one environment's list from infra/devices.json: the units, named b1, b2, … after the
 * board's build number. Committed, so every deploy declares every unit: one left out of a deploy
 * would have its Thing deleted.
 */
export function deviceNamesFor(devices: unknown, deployEnv: 'sandbox' | 'prod'): string[] {
  const names = (devices as Record<string, unknown> | null)?.[deployEnv];
  if (
    !Array.isArray(names) ||
    names.some((d) => typeof d !== 'string' || !/^b[1-9][0-9]*$/.test(d)) ||
    new Set(names).size !== names.length
  ) {
    throw new Error(`infra/devices.json: "${deployEnv}" must be a list of distinct names like b1`);
  }
  return names as string[];
}

export function deployEnvFrom(value: string | undefined): 'sandbox' | 'prod' {
  if (value !== 'sandbox' && value !== 'prod') {
    throw new Error('NPM_ENVIRONMENT must be "sandbox" or "prod". Use `pnpm run deploy-sandbox`.');
  }
  return value;
}
