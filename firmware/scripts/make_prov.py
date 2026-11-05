#!/usr/bin/env python3
"""PETRO-3: build a Petro's prov.bin, the `prov` NVS partition firmware/esp32c6/main/prov.c reads.

    make_prov.py <dir> <endpoint> <thing> <size>

Reads <dir>/device.pem.crt and <dir>/device.pem.key, and the secrets from the environment (never
argv, so they never show in `ps`): PETRO_WIFI_SSID, PETRO_WIFI_PASS, and optionally
PETRO_METRICS_URL, PETRO_METRICS_USER, PETRO_METRICS_PASS (all three, or none: no metrics). Writes
<dir>/prov.bin, <size> bytes (the prov row of firmware/esp32c6/partitions.csv). The CSV it feeds
IDF's NVS partition generator holds the Wi-Fi password, so it is overwritten and removed, however
the run ends. Prints nothing secret.

Run it with IDF's Python (esp_idf_nvs_partition_gen); provision-device.sh does.
"""

import csv
import os
import subprocess
import sys

NAMESPACE = "petro"  # PROV_NAMESPACE in prov.h

# Every key prov.c's PROV_KEYS lists, in its order, with the most bytes each may hold here. The
# firmware's buffers must be at least this plus one for the NUL. The NVS limit for a string is 4000.
LIMITS = {
    "wifi_ssid": 32,      # ESP-IDF's wifi_config_t
    "wifi_pass": 63,
    "endpoint": 127,
    "thing": 128,         # IoT Core's Thing name limit
    "cert": 4000,
    "key": 4000,
    "metrics_url": 127,
    "metrics_user": 32,
    "metrics_pass": 64,
}
METRICS = ("metrics_url", "metrics_user", "metrics_pass")


def rows_for(d, endpoint, thing, env):
    """The CSV rows (after the header): the namespace, then each key. Raises ValueError on bad input."""
    values = {
        "wifi_ssid": env.get("PETRO_WIFI_SSID", ""),
        "wifi_pass": env.get("PETRO_WIFI_PASS", ""),
        "endpoint": endpoint,
        "thing": thing,
    }
    if not values["wifi_ssid"]:
        raise ValueError("no Wi-Fi SSID (PETRO_WIFI_SSID)")
    metrics = {k: env.get("PETRO_" + k.upper(), "") for k in METRICS}
    if any(metrics.values()) and not all(metrics.values()):
        raise ValueError("metrics need all of PETRO_METRICS_URL, _USER and _PASS, or none")
    if metrics["metrics_url"] and not metrics["metrics_url"].startswith(("http://", "https://")):
        raise ValueError("PETRO_METRICS_URL must be an http:// or https:// base URL")
    values.update({k: v for k, v in metrics.items() if v})

    for key, value in values.items():
        if len(value.encode()) > LIMITS[key]:
            raise ValueError(f"{key} is longer than prov allows ({LIMITS[key]} bytes)")
    files = {"cert": os.path.join(d, "device.pem.crt"), "key": os.path.join(d, "device.pem.key")}
    for key, path in files.items():
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise ValueError(f"no {os.path.basename(path)} in {d}")
        if os.path.getsize(path) > LIMITS[key]:
            raise ValueError(f"{os.path.basename(path)} is longer than prov allows ({LIMITS[key]} bytes)")

    rows = [(NAMESPACE, "namespace", "", "")]
    for key in LIMITS:
        if key in files:
            rows.append((key, "file", "string", files[key]))
        elif key in values:
            rows.append((key, "data", "string", values[key]))
    return rows


def scrub(path):
    """Overwrites then removes a file holding secrets (best effort: SSDs may keep old blocks)."""
    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as f:
            f.write(b"\0" * size)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def build(d, endpoint, thing, size, env=None, python=None):
    """Writes <d>/prov.bin; returns the keys it holds."""
    env = os.environ if env is None else env
    python = python or sys.executable
    rows = rows_for(d, endpoint, thing, env)
    if int(size, 0) % 4096:
        raise ValueError(f"prov size {size} is not a whole number of 4 KB pages")
    old = os.umask(0o077)
    csv_path = os.path.join(d, "prov.csv")
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(("key", "type", "encoding", "value"))
            w.writerows(rows)
        subprocess.run(
            [python, "-m", "esp_idf_nvs_partition_gen", "generate", csv_path, os.path.join(d, "prov.bin"), size],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    finally:
        scrub(csv_path)
        os.umask(old)
    return [r[0] for r in rows[1:]]


def main(argv):
    if len(argv) != 5:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        keys = build(*argv[1:])
    except (ValueError, subprocess.CalledProcessError) as e:
        print(f"make_prov: {e}", file=sys.stderr)
        return 1
    print(" ".join(keys))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
