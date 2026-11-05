/**
 * The Alexa event gateway: Login with Amazon (LWA) tokens from AcceptGrant, kept fresh, and the
 * proactive events (ChangeReport) sent with them.
 *
 * The skill's own client ID and secret (Alexa developer console → the skill → Permissions → Send
 * Alexa Events) are a Secrets Manager secret, created by CDK with a placeholder client ID that
 * Martin replaces (docs/alexa-setup.md). Until then AcceptGrant fails and nothing is sent.
 */
import { GetSecretValueCommand, SecretsManagerClient } from '@aws-sdk/client-secrets-manager';
import { DeleteCommand, type DynamoDBDocumentClient, PutCommand, ScanCommand } from '@aws-sdk/lib-dynamodb';
import { env, type GrantItem, grantKey } from './shared';

export const LWA_TOKEN_URL = 'https://api.amazon.com/auth/o2/token';
/** The EU gateway: the skill's endpoint is eu-west-1 and its accounts are en-GB. */
export const DEFAULT_EVENT_GATEWAY = 'https://api.eu.amazonalexa.com/v3/events';
/** The placeholder CDK writes into the secret until Martin puts the skill's credentials there. */
export const CLIENT_ID_PLACEHOLDER = 'NOT_SET';
/** Refresh an access token this long before it expires. */
const REFRESH_MARGIN_MS = 60_000;

export interface SkillCredentials {
  clientId: string;
  clientSecret: string;
}

let secrets: SecretsManagerClient | undefined;
let cached: SkillCredentials | undefined;

/** The skill's credentials, or undefined while the secret still holds the placeholder. */
export async function skillCredentials(): Promise<SkillCredentials | undefined> {
  if (cached) return cached;
  secrets ??= new SecretsManagerClient({ region: env('HOME_REGION') });
  const res = await secrets.send(new GetSecretValueCommand({ SecretId: env('SKILL_SECRET_ID') }));
  let value: Partial<SkillCredentials> = {};
  try {
    value = JSON.parse(res.SecretString ?? '{}');
  } catch {
    // Not JSON: treated as not set.
  }
  if (!value.clientId || value.clientId === CLIENT_ID_PLACEHOLDER || !value.clientSecret) return undefined;
  cached = { clientId: value.clientId, clientSecret: value.clientSecret };
  return cached;
}

/** For tests: forget the cached client and credentials. */
export function resetGatewayCache(): void {
  secrets = undefined;
  cached = undefined;
}

export class GatewayError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

async function lwaToken(form: Record<string, string>): Promise<{ accessToken: string; refreshToken: string; expiresAt: number }> {
  const res = await fetch(LWA_TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body: new URLSearchParams(form).toString(),
  });
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok || typeof body.access_token !== 'string' || typeof body.refresh_token !== 'string') {
    throw new GatewayError(`LWA token request failed: ${res.status} ${String(body.error ?? '')}`, res.status, String(body.error ?? ''));
  }
  const expiresIn = typeof body.expires_in === 'number' ? body.expires_in : 3600;
  return { accessToken: body.access_token, refreshToken: body.refresh_token, expiresAt: Date.now() + expiresIn * 1000 };
}

/** AcceptGrant: swaps the grant code for this account's tokens and stores them. */
export async function acceptGrant(
  db: DynamoDBDocumentClient,
  code: string,
  sub: string,
  groups: string[],
): Promise<void> {
  const creds = await skillCredentials();
  if (!creds) throw new GatewayError('The skill credentials secret is not set (docs/alexa-setup.md)');
  const tokens = await lwaToken({
    grant_type: 'authorization_code',
    code,
    client_id: creds.clientId,
    client_secret: creds.clientSecret,
  });
  const item: GrantItem = { pk: grantKey(sub), sub, groups, ...tokens };
  await db.send(new PutCommand({ TableName: env('TABLE_NAME'), Item: item }));
}

/** Every stored grant (one per linked account that allowed events; a handful). */
export async function grants(db: DynamoDBDocumentClient): Promise<GrantItem[]> {
  const items: GrantItem[] = [];
  let start: Record<string, unknown> | undefined;
  do {
    const res = await db.send(
      new ScanCommand({
        TableName: env('TABLE_NAME'),
        FilterExpression: 'begins_with(pk, :p)',
        ExpressionAttributeValues: { ':p': 'grant#' },
        ExclusiveStartKey: start,
      }),
    );
    items.push(...((res.Items ?? []) as GrantItem[]));
    start = res.LastEvaluatedKey;
  } while (start);
  return items;
}

async function refresh(db: DynamoDBDocumentClient, grant: GrantItem, creds: SkillCredentials): Promise<GrantItem> {
  const tokens = await lwaToken({
    grant_type: 'refresh_token',
    refresh_token: grant.refreshToken,
    client_id: creds.clientId,
    client_secret: creds.clientSecret,
  });
  const next = { ...grant, ...tokens };
  await db.send(new PutCommand({ TableName: env('TABLE_NAME'), Item: next }));
  return next;
}

/** Gateway answers that mean the account is gone: the grant is deleted. */
const GONE = new Set(['SKILL_DISABLED_EXCEPTION', 'SKILL_NEVER_ENABLED_EXCEPTION', 'INSUFFICIENT_PERMISSION_EXCEPTION']);

export type SendResult = 'sent' | 'not-configured' | 'grant-removed';

/**
 * Sends one event for one grant, refreshing its token when due (and once more if the gateway calls
 * it invalid). `build` makes the event from an access token. A grant whose account disabled the
 * skill, or whose refresh token LWA refuses, is deleted.
 */
export async function sendEvent(
  db: DynamoDBDocumentClient,
  grant: GrantItem,
  build: (token: string) => unknown,
): Promise<SendResult> {
  const creds = await skillCredentials();
  if (!creds) return 'not-configured';
  const remove = async () => {
    await db.send(new DeleteCommand({ TableName: env('TABLE_NAME'), Key: { pk: grant.pk } }));
    return 'grant-removed' as const;
  };
  let current = grant;
  try {
    if (current.expiresAt - REFRESH_MARGIN_MS < Date.now()) current = await refresh(db, current, creds);
  } catch (e) {
    if (e instanceof GatewayError && e.code === 'invalid_grant') return remove();
    throw e;
  }
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(process.env.EVENT_GATEWAY_URL || DEFAULT_EVENT_GATEWAY, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${current.accessToken}` },
      body: JSON.stringify(build(current.accessToken)),
    });
    if (res.status === 202 || res.ok) return 'sent';
    const body = (await res.json().catch(() => ({}))) as { payload?: { code?: string; description?: string } };
    const code = body.payload?.code ?? '';
    if (GONE.has(code)) return remove();
    if (res.status === 401 && attempt === 0) {
      try {
        current = await refresh(db, current, creds);
      } catch (e) {
        if (e instanceof GatewayError && e.code === 'invalid_grant') return remove();
        throw e;
      }
      continue;
    }
    throw new GatewayError(`Event gateway: ${res.status} ${code} ${body.payload?.description ?? ''}`.trim(), res.status, code);
  }
}
