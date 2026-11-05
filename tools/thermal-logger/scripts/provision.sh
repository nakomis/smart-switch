#!/usr/bin/env bash
# Gives a Zatt its settings: builds the "prov" NVS partition (Wi-Fi, metrics credentials, HTTP token)
# and flashes it. Safe to re-run; the HTTP token is made once and kept. The firmware image holds none
# of this, so every Zatt runs the same image.
#
#   tools/thermal-logger/scripts/provision.sh <serial-port> [thing]    (thing defaults to zatt-prod-zatt)
#   tools/thermal-logger/scripts/provision.sh --no-flash [thing]       (just write certs/<thing>/prov.bin)
#
# Reads, never printing any of it:
#   Wi-Fi         SSM /Nakomis/Wifi/SSID and /Nakomis/Wifi/Password via WIFI_PROFILE (default nakom.is-sandbox)
#   vmauth        SSM /vmauth/device-<thing>-password via METRICS_PROFILE (default nakom.is-admin, the prod
#                 account). Needs the user in vmauth_devices (home-servers cal/ansible/playbook.yml) and
#                 the SSM parameter created first; without the password the Zatt is provisioned without
#                 metrics (a warning, not a failure).
#   METRICS_URL   default http://172.29.0.33:8427 ("none" for no metrics)
#
# Writes, never committed, under tools/thermal-logger/certs/<thing>/ (gitignored):
#   prov.bin      the partition image (Wi-Fi password and metrics password inside, in plain text, as the
#                 house's other devices have them; the flash is not encrypted)
#   http_token    the token for POST /spots (the mapping page asks for it). Keep it; cat it when needed.
#
# INSECURE, TEST ONLY: secrets sit in the device's flash in plain text, on a LAN-only device.
set -euo pipefail
umask 077

port=""
flash=true
thing=zatt-prod-zatt
for arg in "$@"; do
    case "$arg" in
        --no-flash) flash=false ;;
        -*) echo "unknown option: $arg" >&2; exit 2 ;;
        /dev/* | COM*) port=$arg ;;
        *) thing=$arg ;;
    esac
done
if $flash && [ -z "$port" ]; then
    echo "usage: $0 <serial-port> [thing]   or   $0 --no-flash [thing]" >&2
    exit 2
fi

export AWS_REGION=${AWS_REGION:-eu-west-2}
wifi_profile=${WIFI_PROFILE:-nakom.is-sandbox}
metrics_profile=${METRICS_PROFILE:-nakom.is-admin}
metrics_url=${METRICS_URL:-http://172.29.0.33:8427}

here=$(cd "$(dirname "$0")" && pwd)
proj="${here}/.."
dir="${proj}/certs/${thing}"
mkdir -p "$dir"

if [ -z "${IDF_PATH:-}" ]; then
    for c in "$HOME/esp/esp-idf" "$HOME/esp/v5.5/esp-idf"; do [ -f "$c/export.sh" ] && IDF_PATH=$c && break; done
fi
# shellcheck disable=SC1091
. "$IDF_PATH/export.sh" > /dev/null 2>&1   # for its Python (the NVS partition generator) and esptool

# Through the environment, not argv, so no secret shows up in `ps`.
export ZATT_SSID ZATT_WIFI_PASS ZATT_MURL ZATT_MUSER ZATT_MPASS ZATT_TOKEN
ZATT_SSID=$(aws ssm get-parameter --profile "$wifi_profile" --name /Nakomis/Wifi/SSID --query Parameter.Value --output text)
ZATT_WIFI_PASS=$(aws ssm get-parameter --profile "$wifi_profile" --name /Nakomis/Wifi/Password --with-decryption \
    --query Parameter.Value --output text)

ZATT_MURL="" ZATT_MUSER="" ZATT_MPASS=""
if [ "$metrics_url" != none ]; then
    if ZATT_MPASS=$(aws ssm get-parameter --profile "$metrics_profile" --name "/vmauth/device-${thing}-password" \
        --with-decryption --query Parameter.Value --output text 2> /dev/null); then
        ZATT_MURL=$metrics_url
        ZATT_MUSER=$thing
    else
        ZATT_MPASS=""
        echo "warning: can't read /vmauth/device-${thing}-password (profile ${metrics_profile}): no metrics for ${thing}" >&2
    fi
fi

if [ ! -s "${dir}/http_token" ]; then
    openssl rand -hex 16 > "${dir}/http_token"
    echo "new HTTP token for ${thing} in ${dir}/http_token"
fi
ZATT_TOKEN=$(cat "${dir}/http_token")

# It holds the passwords: overwrite it where we can (shred on Linux, rm -P on macOS), else just remove it.
scrub() {
    if command -v shred > /dev/null 2>&1; then
        shred -u "$1" 2> /dev/null || rm -f "$1"
    else
        rm -P "$1" 2> /dev/null || rm -f "$1"
    fi
}
trap 'scrub "${dir}/prov.csv"' EXIT

prov_size=$(awk -F', *' '$1 == "prov" { print $5 }' "${proj}/partitions.csv")
prov_offset=$(awk -F', *' '$1 == "prov" { print $4 }' "${proj}/partitions.csv")
python3 - "$dir" <<'PY'
import csv, os, sys
d = sys.argv[1]
e = os.environ
limits = {"ZATT_SSID": 32, "ZATT_WIFI_PASS": 63, "ZATT_MURL": 127, "ZATT_MUSER": 32, "ZATT_MPASS": 64, "ZATT_TOKEN": 64}
for k, n in limits.items():
    if len(e[k].encode()) > n:
        sys.exit(f"{k} too long for prov ({n} bytes)")
# Namespace and keys as main/prov.c reads them.
rows = [
    ("zatt", "namespace", "", ""),
    ("wifi_ssid", "data", "string", e["ZATT_SSID"]),
    ("wifi_pass", "data", "string", e["ZATT_WIFI_PASS"]),
    ("http_token", "data", "string", e["ZATT_TOKEN"]),
]
if e["ZATT_MURL"]:
    rows += [("metrics_url", "data", "string", e["ZATT_MURL"]),
             ("metrics_user", "data", "string", e["ZATT_MUSER"]),
             ("metrics_pass", "data", "string", e["ZATT_MPASS"])]
with open(os.path.join(d, "prov.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(("key", "type", "encoding", "value"))
    w.writerows(rows)
PY
python -m esp_idf_nvs_partition_gen generate "${dir}/prov.csv" "${dir}/prov.bin" "$prov_size" > /dev/null
echo "wrote ${dir}/prov.bin for ${thing}${ZATT_MURL:+ (metrics to ${ZATT_MURL})}"

if $flash; then
    esptool.py --port "$port" --after watchdog_reset write_flash "$prov_offset" "${dir}/prov.bin" > /dev/null
    echo "flashed prov at ${prov_offset} on ${port}"
fi
