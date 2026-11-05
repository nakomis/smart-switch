# Alexa skill setup

Every Petro unit appears in Alexa as a **smart plug** called "Petro b1", "Petro b2", … (rename it in
the Alexa app). Alexa can switch it on and off, ask whether it's on, and shows it as offline when
it stops reporting. Adapted from nakostat's `docs/alexa-setup.md`; PETRO-8.

The skill is **public** (Martin's decision): anyone in the UK can find "Petro" in the skills store,
but linking needs a Nakomis Cognito account (the pool is admin-create-only, and this client takes
Cognito users only, not Sign in with Apple), and an account sees **only the units its Cognito
groups allow**. The prod skill goes through certification once; the sandbox skill stays in
development.

## What Alexa can and can't do

The unit is always the authority. The skill sends Fleet's own `{"command":"relay","on":…}` to
`petro/<thing>/commands`, waits up to 4 s for the status that shows the relay switched, and answers
with that. It never answers "OK" for a switch that didn't happen:

| The unit's status | Alexa gets |
|---|---|
| `mode` auto, no trip, `remote` true | The command; the confirmed state |
| `mode` on or off (held at the button) | `NOT_SUPPORTED_IN_CURRENT_MODE` (`currentDeviceMode` OTHER), "held on at its button; press it until the light is blue (auto)" |
| `trip` set (overcurrent, overtemp, overcurrent_instant, meter_fault) | `NOT_SUPPORTED_IN_CURRENT_MODE`, "has tripped (…); press its button to clear the trip" |
| auto, but `remote` false (a relay cycle, …) | `ENDPOINT_BUSY` |
| No status for 3 minutes (three heartbeats) | `ENDPOINT_UNREACHABLE`, and connectivity UNREACHABLE |
| Sent, but no confirming status within 4 s | `ENDPOINT_UNREACHABLE`, "did not confirm" |

Alexa speaks its own wording for each error type (along the lines of "isn't responding" or "can't
do that in its current mode"); the messages above go back in the ErrorResponse and the Lambda's logs.

**Proactive reports.** The reporter sends Alexa a ChangeReport whenever a unit's relay or health
changes for any reason other than an Alexa command: a press of the button (cause
PHYSICAL_INTERACTION), a trip (RULE_TRIGGER), Fleet's relay command (APP_INTERACTION), or the unit
going quiet or coming back (PERIODIC_POLL). So the Alexa app and routines see a press at the plug
within a second or two.

## How it fits together

| Piece | Where | Stack |
|---|---|---|
| Skill Lambda `petro-alexa-{env}` | **eu-west-1** (Alexa's EU endpoint region) | `PetroAlexaStack` |
| Cognito app client `petro-alexa-{env}`, its login style, the groups | eu-west-2, on the shared pool | `PetroAlexaAuthStack` |
| State table `petro-alexa-{env}`, the skill secret, the reporter `petro-alexa-reporter-{env}` (IoT rule `petro_alexa_status_{env}`, a 2-minute sweep) | eu-west-2, beside IoT Core | `PetroAlexaStateStack` |
| Things `petro-{env}-bN` (project=petro) | eu-west-2 | `PetroDeviceStack` |

```
 Echo ──► Alexa ──► petro-alexa (eu-west-1) ──publish──► petro/<thing>/commands ──► unit
                          ▲      │ read                                               │
                          │      ▼                                                    ▼
                     state table (eu-west-2) ◄── reporter ◄── IoT rule ◄── petro/<thing>/status
                                                     │
 Alexa event gateway ◄──────── ChangeReport ─────────┘
```

The state table holds, per unit, `status#<thing>` (the latest status and when IoT received it) and
`reported#<thing>` (what Alexa was last told), and per linked account `grant#<sub>` (its event
gateway tokens, from AcceptGrant). It holds nothing that can't be rebuilt.

**Who sees what.** A linked account's Cognito user must be in the group `petro` (every unit) or
`petro-<name>` (that unit only, e.g. `petro-b5`). A user in neither discovers nothing, and a
directive for a unit outside its groups is `NO_SUCH_ENDPOINT`. Groups are read from the access
token on every directive, and each directive also refreshes the groups stored with the account's
grant, which the reporter uses for ChangeReports. A grant whose groups haven't been refreshed for a
week gets no ChangeReports until its next directive (the Alexa app sends a ReportState whenever
it's opened), so a user taken out of the groups stops hearing about the units within a week at
most, and at once for directives.

The table is encrypted with an AWS-owned key. The grants' LWA tokens can only send events to this
skill; a customer-managed KMS key would add key-level audit and revocation (about $1 a month) if it's
ever wanted.

A failed IoT rule action (the reporter erroring or throttled) is logged to
`/aws/iot/petro-alexa-status-errors-{env}`. One account's failed ChangeReport doesn't stop the
others; it's logged ("missed it"), and that account catches up at its next ReportState.

## Parameters and secrets

| Name | Region | Value |
|---|---|---|
| SSM `/petro/{env}/alexa/skillId` | **eu-west-1** | `amzn1.ask.skill.…` |
| SSM `/petro/{env}/alexa/vendorId` | eu-west-2 | your developer vendor ID, e.g. `M1…` (sandbox: set, `M1MBT2A7GPZ15H`, the one recipator-alexa's redirect URLs use) |
| SSM `/petro/{env}/alexa/cognito/client-id` | eu-west-2 | written by `PetroAlexaAuthStack` |
| Secrets Manager `petro/{env}/alexa/skill-messaging` | eu-west-2 | `{"clientId":"amzn1.application-oa2-client.…","clientSecret":"…"}`; created by `PetroAlexaStateStack` with `clientId` `NOT_SET`, which the code treats as unset |

Below, `ENV` is `sandbox` or `prod` and `PROFILE` is `nakom.is-sandbox` or `nakom.is-admin`. Each
environment is its own skill ("Petro (sandbox)" and "Petro"). Don't enable both on one Amazon
account: both would discover the same names.

## One-off: bootstrap eu-west-1 (prod)

Sandbox is bootstrapped in eu-west-1; check prod first:

```sh
aws cloudformation describe-stacks --profile nakom.is-admin --region eu-west-1 --stack-name CDKToolkit \
  || (cd infra && pnpm exec cdk bootstrap aws://637423226886/eu-west-1 --profile nakom.is-admin)
```

## 1. First deploy (no skill yet)

```sh
cd infra
NPM_ENVIRONMENT=ENV pnpm exec cdk deploy --profile PROFILE \
  PetroAlexaAuthStack PetroAlexaStateStack PetroAlexaStack
```

CDK warns that `alexa/skillId` (and, until it's set, `alexa/vendorId`) is a placeholder: the Lambda
has no Alexa trigger yet and the redirect URLs are dummies. Note the `AlexaFunctionArn` output:
`arn:aws:lambda:eu-west-1:<account>:function:petro-alexa-ENV`. (CI doesn't deploy the CDK; Martin
does.)

## 2. Create the skill

From the package in this repository: stage it for the environment, then import it. The ASK CLI
needs Martin's Amazon developer login once (`npm install -g ask-cli`, `ask configure`).

```sh
cd infra
pnpm run stage-skill ENV <AlexaFunctionArn>          # → infra/build/skill-package/ENV
cd build/skill-package/ENV && zip -r ../ENV.zip . && cd ..
URL=$(ask smapi create-upload-url | jq -r .uploadUrl)
curl -X PUT -T ENV.zip "$URL"
ask smapi import-skill-package --vendor-id <vendorId> --location "$URL"   # prints the skill ID
```

The endpoint check fails until step 4 adds the trigger; that's expected. Or by hand, in the
[Alexa developer console](https://developer.amazon.com/alexa/console/ask): **Create Skill** → name
`Petro` (or `Petro (sandbox)`), locale **English (UK)**, **Smart Home**, **Provision your own**;
then copy the fields from the staged `skill.json` (and upload the two icons from its
`assets/images/`).

Copy the **Skill ID** (`amzn1.ask.skill.…`). Your **vendor ID** is under *Settings* → *Your vendor
ID* (or `ask smapi list-vendors`).

## 3. Set the parameters

```sh
aws ssm put-parameter --profile PROFILE --region eu-west-1 --type String \
  --name /petro/ENV/alexa/skillId --value amzn1.ask.skill.XXXXXXXX
aws ssm put-parameter --profile PROFILE --region eu-west-2 --type String \
  --name /petro/ENV/alexa/vendorId --value MXXXXXXXXXXXX            # sandbox: already set
```

## 4. Second deploy (the trigger and the real redirect URLs)

The SSM lookups are cached in `infra/cdk.context.json` (git-ignored). Clear it first:

```sh
cd infra
rm -f cdk.context.json
NPM_ENVIRONMENT=ENV pnpm exec cdk deploy --profile PROFILE \
  PetroAlexaAuthStack PetroAlexaStateStack PetroAlexaStack
```

No `alexa/skillId` or `alexa/vendorId` warnings this time.

## 5. Point the skill at the Lambda

Smart Home page → **Default endpoint**: the `AlexaFunctionArn`; tick **Europe, India** and paste
the same ARN. **Save**. (Already in the manifest if you imported it: re-import, or
`ask smapi update-skill-manifest --skill-id <skillId> --stage development --manifest "file:infra/build/skill-package/ENV/skill.json"`,
now that the trigger exists.)

## 6. Send Alexa Events (ChangeReports)

The manifest asks for the `alexa::async_event:write` permission. In the console: **Permissions** →
**Send Alexa Events** on; it shows the skill's **Alexa Client Id** and **Alexa Client Secret**. Put
them in the secret **before** anyone links an account (AcceptGrant fails until it's set):

```sh
aws secretsmanager put-secret-value --profile PROFILE --region eu-west-2 \
  --secret-id petro/ENV/alexa/skill-messaging \
  --secret-string '{"clientId":"amzn1.application-oa2-client.…","clientSecret":"…"}'
```

CloudFormation leaves a value set like this alone. The Lambdas cache it while warm: after changing
it, wait a few minutes (or update the functions) before testing.

## 7. Account linking

```sh
POOL=$(aws ssm get-parameter --profile PROFILE --region eu-west-2 \
  --name /nakomis-infra/ENV/cognito/user-pool-id --query Parameter.Value --output text)
CLIENT=$(aws ssm get-parameter --profile PROFILE --region eu-west-2 \
  --name /petro/ENV/alexa/cognito/client-id --query Parameter.Value --output text)
aws cognito-idp describe-user-pool-client --profile PROFILE --region eu-west-2 \
  --user-pool-id "$POOL" --client-id "$CLIENT" \
  --query 'UserPoolClient.[ClientId,ClientSecret]' --output text
```

In the console, **Account Linking**:

| Field | Value |
|---|---|
| Authorization grant type | Auth Code Grant |
| Web Authorization URI | `https://login.nakomis.com/oauth2/authorize` (sandbox: `login.sandbox.nakomis.com`) |
| Access Token URI | `https://login.nakomis.com/oauth2/token` (sandbox: `login.sandbox.nakomis.com`) |
| Your Client ID | `$CLIENT` |
| Your Secret | the secret from above |
| Your Authentication Scheme | HTTP Basic (Recommended) |
| Scope | `openid`, `profile`, `email` (three entries) |
| Default Access Token Expiration Time | 3600 |

The *Alexa Redirect URLs* it shows must match the client's callback URLs (they do once the vendor
ID parameter is right). With the ASK CLI instead: copy `alexa/account-linking.json` **outside the
repo**, fill in `LOGIN_DOMAIN`, `CLIENT_ID` and `CLIENT_SECRET`, then
`ask smapi update-account-linking-info --skill-id <skillId> --stage development --account-linking-request "file:/path/to/copy.json"`.
Never commit the filled-in copy.

## 8. Give yourself the units, enable and discover

```sh
aws cognito-idp admin-add-user-to-group --profile PROFILE --region eu-west-2 \
  --user-pool-id "$POOL" --username <your username> --group-name petro
```

1. Alexa app → *More* → *Skills & Games* → *Your Skills* → *Dev* → **Petro** → *Enable to use*.
2. Sign in on the Nakomis page. (Groups are read from the access token, so a change of groups
   reaches Alexa at the next hourly token refresh, or at once by disabling and re-enabling.)
3. *Discover devices*. **Petro b1** appears as a plug.

## Things to say

- "Alexa, turn on Petro b1." / "Alexa, switch Petro b1 off."
- "Alexa, is Petro b1 on?"
- Routines: "When Petro b1 turns on…" works, because the plug reports button presses.

## Energy

Petro measures power (`watts`) and energy (`energy_kwh`) in every status, but **Alexa doesn't
surface it for this skill**. Alexa's energy dashboard takes measured energy through
`Alexa.DeviceUsage.Meter` (hourly to daily `MeasurementsReport` events to the event gateway), and
estimates through `Alexa.DeviceUsage.Estimation`; both are **en-US only** in Amazon's list of
interfaces and languages (checked 5 Nov 2026), and this skill is en-GB. Nothing for plugs reports
live watts as a property. `TODO(PETRO-8)`: when the Meter interface reaches en-GB, add it to
discovery (`energySources.electricity`: `MILLIWATT_HOUR`, `MEASURED`, `defaultResolution` 3600) and
have the reporter send hourly intervals from the `energy_kwh` deltas (skipping a negative delta, a
counter reset). Grafana keeps the metering meanwhile.

## Certification (prod, once)

A public skill is certified before it's live. The plan:

1. **A unit for the certifier.** Certification switches a real plug. Use one prod unit kept for it,
   assumed **b5** with a lamp, in **auto**, powered and online for the whole review (it can take
   days). The certifier sees only that one.
2. **A test account.** In the prod pool: `admin-create-user` a dedicated user (e.g.
   `alexa-certification`), set a permanent password (`admin-set-user-password --permanent`), and
   add it to `petro-b5` only (never `petro`). Delete it, or disable it, after certification.
3. **Stage with the account**, then import or update the prod skill:
   `PETRO_CERT_USERNAME=… PETRO_CERT_PASSWORD=… pnpm run stage-skill prod <arn>`. The testing
   instructions then carry the credentials and tell the certifier about the button override (the
   staged copy is under `infra/build/`, git-ignored; never commit it).
4. **Run Amazon's Smart Home tests yourself first**, in the console's *Test* tab and the *Validation*
   checks, on the sandbox skill: account linking from the Alexa app; discovery (a SMARTPLUG with
   PowerController, EndpointHealth, Alexa); "turn on/off" and the state shown in the app;
   ReportState (open the device in the app); a press at the button appearing in the app on its own
   (ChangeReport); the unit unplugged showing as offline within about 5 minutes and back when
   powered; and the error cases (held on, held off, tripped) giving an error, not a false "OK".
   The Alexa *Smart Home Skill Validation Tool* (*Certification* → *Validation*) runs the
   capability checks against the live endpoint.
5. **Distribution** page: the store fields come from the manifest (name, descriptions, example
   phrases, icons, privacy policy `https://nakom.is/privacy-policy`, category Smart Home, GB only).
   **Submit for review**.
6. After it's live, **Live** and **Development** versions are separate stages: the endpoint and
   account linking are the same, so nothing changes for existing links.

## Revoking Alexa's access

As nakostat: the client's refresh tokens last 10 years, so a link is revoked deliberately.

- **Take the user out of the groups**: `admin-remove-user-from-group`. Their next directive is
  `NO_SUCH_ENDPOINT`; disable the skill for them too, so the reporter's grant goes.
- **Revoke the refresh token**: `aws cognito-idp revoke-token --client-id "$CLIENT" --client-secret
  "<secret>" --token "<refresh token>"` (the client has token revocation enabled).
- **Global sign-out**: `aws cognito-idp admin-user-global-sign-out --user-pool-id "$POOL" --username <user>`.
- **Disable the client**: remove or replace it in `infra/lib/alexa-stack.ts` and deploy; every link
  breaks at once.

The reporter deletes a grant itself when the gateway says the skill was disabled for that account,
or LWA refuses its refresh token.

## Troubleshooting

- **Logs**: `/aws/lambda/petro-alexa-ENV` in **eu-west-1**; `/aws/lambda/petro-alexa-reporter-ENV`
  in eu-west-2.
- **`EXPIRED_AUTHORIZATION_CREDENTIAL`** in the logs is normal: Alexa refreshes the token and retries.
- **Discovery finds nothing**: the token failed verification (`Token verification failed`), or
  the user isn't in `petro` / `petro-<name>`, or the Thing lacks `project=petro`.
- **"Petro b1 isn't responding"**: no status for 3 minutes (is it online in Fleet?), or no
  confirming status within 4 s of the command (`did not confirm` in the logs).
- **Alexa says it can't do that now**: it's held on or off at its button, or tripped.
  Press the button until the light is blue (auto); a trip is cleared by a press.
- **The app doesn't update on a button press**: the skill secret isn't set (`no ChangeReports` in
  the reporter's logs), Send Alexa Events is off, or the account linked before it was set (AcceptGrant
  failed): disable and re-enable the skill.
- **Endpoint won't save in the console**: the trigger is missing; check the skill ID parameter (in
  eu-west-1), clear `cdk.context.json`, redeploy.
- **Linking fails with `redirect_mismatch`**: the vendor ID parameter (eu-west-2) is wrong or wasn't
  picked up; clear `cdk.context.json` and redeploy `PetroAlexaAuthStack`.
- **"Login pages unavailable"**: the client lost its managed login style; `PetroAlexaAuthStack`
  makes one (copied from recipator-alexa's).
