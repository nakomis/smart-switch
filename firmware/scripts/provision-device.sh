#!/usr/bin/env bash
# PETRO-3: give a Petro its IoT certificate and the settings its firmware reads, and flash them.
# Safe to re-run. Adapted from the nakostat heatlink's provision-device.sh (and katooni's).
#
#   firmware/scripts/provision-device.sh <thing> [--new] [--env sandbox|prod] [--port <port>]
#
#   <thing>   petro-<env>-bN, e.g. petro-prod-b1: a Thing PetroDeviceStack made (add the unit to
#             infra/devices.json and deploy first). --env defaults to the env in the name, and must
#             agree with it.
#   --new     retires the Thing's existing certificates (detach, deactivate, delete) and makes a
#             fresh one; use it if a private key may have leaked.
#   --port    flashes prov.bin to the board on that port (USB only, mains unplugged: the whole board
#             is at mains potential when it's plugged in). Without it, prints the command.
#
# Each run makes sure the unit's certificate is active and attached to its Thing and to the
# petro-device-<env> policy. Fleet needs nothing more: it lists the Thing from its attributes, finds
# its firmware under the bucket's petro/ prefix, and adds a registry row the first time it hears
# from the unit.
#
# Writes, never committed (firmware/certs/ is gitignored), under firmware/certs/<thing>/:
#   device.pem.crt, device.pem.key, certificate-arn
#   prov.bin   the unit's prov partition (firmware/esp32c6/partitions.csv): NVS namespace "petro",
#              keys as firmware/esp32c6/main/prov.c reads them (wifi_ssid, wifi_pass, endpoint, thing,
#              cert, key, and metrics_url, metrics_user, metrics_pass when there's a vmauth password).
#              None of it is in the firmware image, so every Petro runs the same (published) image.
#
# INSECURE, TEST ONLY: the private key is made by AWS, kept here and flashed in plain text, and the
# Wi-Fi and vmauth passwords sit in prov.bin and the unit's flash (no flash encryption yet).
#
# Profiles (eu-west-2 unless AWS_REGION says otherwise):
#   AWS_PROFILE      the unit's account: default nakom.is-sandbox for sandbox, nakom.is-admin for prod
#   WIFI_PROFILE     /Nakomis/Wifi/{SSID,Password}: default nakom.is-sandbox (they live only there,
#                    so a prod unit reads them from there too)
#   METRICS_PROFILE  /vmauth/device-<thing>-password: default nakom.is-admin, where vmauth's live.
#                    vmauth (on Cal, HOME-437) has a user per unit, named after the Thing, and pins
#                    host_name to it. No password, no metrics: a warning, not a failure.
#   METRICS_URL      vmauth's base URL, default http://172.29.0.33:8427 ("none" for no metrics); the
#                    firmware appends the write path, as tinycrypt's does
#   IDF_PATH         default ~/esp/v5.5/esp-idf; its export.sh gives the NVS generator and esptool.
#                    IDF_PYTHON, if set, is used instead of sourcing export.sh.
set -euo pipefail
umask 077

usage() { sed -n '5p' "$0" | sed 's/^# *//' >&2; exit 2; }

thing=""
new=false
env=""
port=""
while [ $# -gt 0 ]; do
    case "$1" in
        --new) new=true ;;
        --env) env=${2:-}; [ -n "$env" ] || usage; shift ;;
        --port) port=${2:-}; [ -n "$port" ] || usage; shift ;;
        -h | --help) usage ;;
        -*) echo "unknown option: $1" >&2; usage ;;
        *) [ -z "$thing" ] || usage; thing=$1 ;;
    esac
    shift
done
[ -n "$thing" ] || usage
if [[ ! "$thing" =~ ^petro-(sandbox|prod)-b[1-9][0-9]*$ ]]; then
    echo "the Thing must be petro-<sandbox|prod>-bN, e.g. petro-prod-b1, not '${thing}'" >&2
    exit 2
fi
name_env=${BASH_REMATCH[1]}
env=${env:-$name_env}
case "$env" in sandbox | prod) ;; *) echo "--env must be sandbox or prod" >&2; exit 2 ;; esac
[ "$env" = "$name_env" ] || { echo "${thing} is a ${name_env} Thing, not ${env}" >&2; exit 2; }

if [ "$env" = prod ]; then default_profile=nakom.is-admin; else default_profile=nakom.is-sandbox; fi
export AWS_PROFILE=${AWS_PROFILE:-$default_profile}
export AWS_REGION=${AWS_REGION:-eu-west-2}
wifi_profile=${WIFI_PROFILE:-nakom.is-sandbox}
metrics_profile=${METRICS_PROFILE:-nakom.is-admin}

here=$(cd "$(dirname "$0")" && pwd)
fw=$(cd "${here}/.." && pwd)
policy="petro-device-${env}"
dir="${fw}/certs/${thing}"
mkdir -p "$dir"

prov_offset=$(awk -F', *' '$1 == "prov" { print $4 }' "${fw}/esp32c6/partitions.csv")
prov_size=$(awk -F', *' '$1 == "prov" { print $5 }' "${fw}/esp32c6/partitions.csv")
[ -n "$prov_offset" ] && [ -n "$prov_size" ] || { echo "no prov row in esp32c6/partitions.csv" >&2; exit 1; }

echo "provisioning ${thing} in ${env} (profile ${AWS_PROFILE})"
aws iot describe-thing --thing-name "$thing" > /dev/null   # fails here if PetroDeviceStack lacks this unit

# True if IoT Core no longer has this certificate.
gone() {
    local err
    if err=$(aws iot describe-certificate --certificate-id "$1" 2>&1 > /dev/null); then return 1; fi
    case "$err" in *ResourceNotFoundException*) return 0 ;; esac
    echo "can't check certificate $1: ${err}" >&2
    exit 1
}

# Detach, deactivate and delete one certificate. Each step may legitimately fail (already detached,
# already inactive, detaching still propagating), so what counts is the end: IoT Core deletes only a
# certificate with no Thing and no policy left, and if it isn't gone, we stop.
retire() {
    local arn=$1 id=${1##*/}
    if gone "$id"; then echo "certificate ${id} is already gone"; return; fi
    aws iot detach-policy --policy-name "$policy" --target "$arn" 2> /dev/null || true
    aws iot detach-thing-principal --thing-name "$thing" --principal "$arn" 2> /dev/null || true
    aws iot update-certificate --certificate-id "$id" --new-status INACTIVE 2> /dev/null || true
    # Detaching from a Thing is eventually consistent; deletion can lag a few seconds behind.
    for _ in 1 2 3 4 5 6; do aws iot delete-certificate --certificate-id "$id" 2> /dev/null && break; sleep 5; done
    if ! gone "$id"; then
        echo "couldn't retire certificate ${id}: check what's still attached (aws iot list-principal-things," >&2
        echo "list-attached-policies), delete it by hand, then rerun" >&2
        exit 1
    fi
    echo "retired certificate ${id}"
}

if $new; then
    # The Thing's certificates, and the one recorded here: a run that died between making and
    # attaching it left one the Thing doesn't know about.
    arns=$(aws iot list-thing-principals --thing-name "$thing" --query 'principals[]' --output text)
    if [ -s "${dir}/certificate-arn" ]; then arns="${arns} $(cat "${dir}/certificate-arn")"; fi
    for arn in $(echo "$arns" | tr -s ' \t' '\n' | grep '^arn:' | sort -u); do
        retire "$arn"
    done
    rm -f "${dir}/device.pem.crt" "${dir}/device.pem.key" "${dir}/certificate-arn"
fi

if [ ! -s "${dir}/device.pem.key" ] || [ ! -s "${dir}/certificate-arn" ]; then
    aws iot create-keys-and-certificate --set-as-active \
        --certificate-pem-outfile "${dir}/device.pem.crt" \
        --private-key-outfile "${dir}/device.pem.key" \
        --query certificateArn --output text > "${dir}/certificate-arn"
    echo "new certificate $(cut -d/ -f2 < "${dir}/certificate-arn") for ${thing}"
fi
cert_arn=$(cat "${dir}/certificate-arn")

# Never attach a certificate that isn't active.
status=$(aws iot describe-certificate --certificate-id "${cert_arn##*/}" --query certificateDescription.status --output text)
[ "$status" = ACTIVE ] || { echo "certificate ${cert_arn##*/} is ${status}: rerun with --new" >&2; exit 1; }
# Both attachments are idempotent, so every run repairs a half-finished earlier one.
aws iot attach-policy --policy-name "$policy" --target "$cert_arn"
aws iot attach-thing-principal --thing-name "$thing" --principal "$cert_arn"

endpoint=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query endpointAddress --output text)

# Secrets go to make_prov.py through the environment, not argv, so they never show up in `ps`.
export PETRO_WIFI_SSID PETRO_WIFI_PASS
PETRO_WIFI_SSID=$(aws ssm get-parameter --profile "$wifi_profile" --name /Nakomis/Wifi/SSID \
    --query Parameter.Value --output text)
PETRO_WIFI_PASS=$(aws ssm get-parameter --profile "$wifi_profile" --name /Nakomis/Wifi/Password \
    --with-decryption --query Parameter.Value --output text)

export PETRO_METRICS_URL=${METRICS_URL:-http://172.29.0.33:8427} PETRO_METRICS_USER=$thing PETRO_METRICS_PASS=
if [ "$PETRO_METRICS_URL" = none ]; then
    PETRO_METRICS_URL='' PETRO_METRICS_USER=''
elif ! PETRO_METRICS_PASS=$(aws ssm get-parameter --profile "$metrics_profile" \
        --name "/vmauth/device-${thing}-password" --with-decryption \
        --query Parameter.Value --output text 2> /dev/null); then
    echo "warning: can't read /vmauth/device-${thing}-password (profile ${metrics_profile}): no metrics for ${thing}" >&2
    PETRO_METRICS_URL='' PETRO_METRICS_USER='' PETRO_METRICS_PASS=''
fi

if [ -n "${IDF_PYTHON:-}" ]; then
    python=$IDF_PYTHON
else
    IDF_PATH="${IDF_PATH:-$HOME/esp/v5.5/esp-idf}"
    [ -f "$IDF_PATH/export.sh" ] || { echo "no ESP-IDF at ${IDF_PATH} (set IDF_PATH or IDF_PYTHON)" >&2; exit 1; }
    # For its Python: the NVS partition generator, esptool. export.sh isn't written for set -u.
    set +u
    # shellcheck disable=SC1091
    if ! . "$IDF_PATH/export.sh" > "${dir}/idf-export.log" 2>&1; then
        set -u
        echo "sourcing ${IDF_PATH}/export.sh failed: see ${dir}/idf-export.log" >&2
        exit 1
    fi
    set -u
    rm -f "${dir}/idf-export.log"
    command -v python > /dev/null || { echo "no python after sourcing ${IDF_PATH}/export.sh" >&2; exit 1; }
    python=python
fi
keys=$("$python" "${here}/make_prov.py" "$dir" "$endpoint" "$thing" "$prov_size")
echo "wrote ${dir}/prov.bin for ${thing} (${endpoint}${PETRO_METRICS_URL:+; metrics to ${PETRO_METRICS_URL}}): ${keys}"

flash=("$python" -m esptool --chip esp32c6 --after watchdog_reset)
if [ -n "$port" ]; then
    echo "flashing prov to ${port} at ${prov_offset} (USB only, mains unplugged)"
    "${flash[@]}" -p "$port" write_flash "$prov_offset" "${dir}/prov.bin"
else
    echo "flash it (USB only, mains unplugged) with: esptool --chip esp32c6 -p <port> --after watchdog_reset write_flash ${prov_offset} ${dir}/prov.bin"
    echo "or rerun with --port <port>"
fi
