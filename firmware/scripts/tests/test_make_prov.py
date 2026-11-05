"""make_prov.py with dummy values: rows and limits on any Python, and the real prov.bin (read back with
IDF's nvs_tool) where IDF's Python is available. No AWS, no secrets.

    IDF_PYTHON=~/.espressif/python_env/idf5.5_py3.11_env/bin/python python -m pytest -q firmware/scripts/tests
"""

import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
FIRMWARE = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import make_prov  # noqa: E402

IDF_PATH = os.environ.get("IDF_PATH", os.path.expanduser("~/esp/v5.5/esp-idf"))
IDF_PYTHON = os.environ.get("IDF_PYTHON", os.path.expanduser("~/.espressif/python_env/idf5.5_py3.11_env/bin/python"))
NVS_TOOL = os.path.join(IDF_PATH, "components", "nvs_flash", "nvs_partition_tool", "nvs_tool.py")

CERT = "-----BEGIN CERTIFICATE-----\n" + "A" * 1200 + "\n-----END CERTIFICATE-----\n"
KEY = "-----BEGIN RSA PRIVATE KEY-----\n" + "B" * 1600 + "\n-----END RSA PRIVATE KEY-----\n"  # a dummy, not a key: secret-check:allow
ENV = {
    "PETRO_WIFI_SSID": "dummy-ssid",
    "PETRO_WIFI_PASS": "dummy-pass",
    "PETRO_METRICS_URL": "http://172.29.0.33:8427",
    "PETRO_METRICS_USER": "petro-prod-b1",
    "PETRO_METRICS_PASS": "dummy-metrics",
}
ENDPOINT = "example-ats.iot.eu-west-2.amazonaws.com"


@pytest.fixture
def certs(tmp_path):
    (tmp_path / "device.pem.crt").write_text(CERT)
    (tmp_path / "device.pem.key").write_text(KEY)
    return tmp_path


def prov_c_keys():
    """PROV_KEYS, as firmware/esp32c6/main/prov.c lists them."""
    src = open(os.path.join(FIRMWARE, "esp32c6", "main", "prov.c"), encoding="utf-8").read()
    block = re.search(r"PROV_KEYS\[\]\s*=\s*\{(.*?)\};", src, re.S).group(1)
    return re.findall(r'"([a-z_]+)"', block)


def prov_partition():
    """(offset, size) of the prov row in partitions.csv."""
    for line in open(os.path.join(FIRMWARE, "esp32c6", "partitions.csv"), encoding="utf-8"):
        cols = [c.strip() for c in line.split(",")]
        if cols[0] == "prov":
            return cols[3], cols[4]
    raise AssertionError("no prov row")


def test_keys_match_prov_c():
    assert list(make_prov.LIMITS) == prov_c_keys()


def test_namespace_matches_prov_h():
    src = open(os.path.join(FIRMWARE, "esp32c6", "main", "prov.h"), encoding="utf-8").read()
    assert f'#define PROV_NAMESPACE "{make_prov.NAMESPACE}"' in src


def test_all_rows(certs):
    rows = make_prov.rows_for(str(certs), ENDPOINT, "petro-prod-b1", ENV)
    assert rows[0] == ("petro", "namespace", "", "")
    assert [r[0] for r in rows[1:]] == prov_c_keys()
    by_key = {r[0]: r for r in rows[1:]}
    assert by_key["cert"] == ("cert", "file", "string", str(certs / "device.pem.crt"))
    assert by_key["thing"][3] == "petro-prod-b1"
    assert by_key["metrics_url"][3] == "http://172.29.0.33:8427"


def test_no_metrics(certs):
    env = {k: v for k, v in ENV.items() if "METRICS" not in k}
    keys = [r[0] for r in make_prov.rows_for(str(certs), ENDPOINT, "petro-prod-b1", env)[1:]]
    assert keys == [k for k in prov_c_keys() if not k.startswith("metrics_")]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"PETRO_WIFI_SSID": ""}, "SSID"),
        ({"PETRO_WIFI_SSID": "s" * 33}, "wifi_ssid"),
        ({"PETRO_WIFI_PASS": "p" * 64}, "wifi_pass"),
        ({"PETRO_METRICS_PASS": ""}, "all of"),
        ({"PETRO_METRICS_URL": "172.29.0.33:8427"}, "http"),
        ({"PETRO_METRICS_USER": "u" * 33}, "metrics_user"),
    ],
)
def test_rejects(certs, change, message):
    with pytest.raises(ValueError, match=message):
        make_prov.rows_for(str(certs), ENDPOINT, "petro-prod-b1", {**ENV, **change})


def test_rejects_missing_or_huge_key(certs):
    (certs / "device.pem.key").write_text("")
    with pytest.raises(ValueError, match="no device.pem.key"):
        make_prov.rows_for(str(certs), ENDPOINT, "petro-prod-b1", ENV)
    (certs / "device.pem.key").write_text("x" * 4000)  # no room left for the NUL
    with pytest.raises(ValueError, match="longer"):
        make_prov.rows_for(str(certs), ENDPOINT, "petro-prod-b1", ENV)


def test_rejects_long_endpoint(certs):
    with pytest.raises(ValueError, match="endpoint"):
        make_prov.rows_for(str(certs), "e" * 128, "petro-prod-b1", ENV)


def test_rejects_odd_size(certs):
    with pytest.raises(ValueError, match="4 KB"):
        make_prov.build(str(certs), ENDPOINT, "petro-prod-b1", "0x6100", env=ENV)
    assert not (certs / "prov.csv").exists()


def test_scrub_missing_file_is_fine(tmp_path):
    make_prov.scrub(str(tmp_path / "nothing"))


def test_usage():
    assert make_prov.main(["make_prov.py"]) == 2


needs_idf = pytest.mark.skipif(
    not (os.path.exists(IDF_PYTHON) and os.path.exists(NVS_TOOL)), reason="needs IDF 5.5's Python and nvs_tool"
)


@needs_idf
def test_builds_a_partition_the_firmware_can_read(certs):
    _, size = prov_partition()
    keys = make_prov.build(str(certs), ENDPOINT, "petro-prod-b1", size, env=ENV, python=IDF_PYTHON)
    assert keys == prov_c_keys()
    out = certs / "prov.bin"
    assert out.stat().st_size == int(size, 0)
    assert oct(out.stat().st_mode & 0o777) == "0o600"
    assert not (certs / "prov.csv").exists(), "the CSV holds the Wi-Fi password: it must be gone"

    dump = subprocess.run(
        [IDF_PYTHON, NVS_TOOL, "-i", "-d", "minimal", "--color", "never", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout
    # nvs_tool shows each string with its NUL.
    found = {k: v.rstrip("\x00 ") for k, v in re.findall(r"^ petro:([a-z_]+) = (.*?)$", dump, re.M)}
    assert list(found) == prov_c_keys()
    assert found["wifi_ssid"] == "dummy-ssid"
    assert found["thing"] == "petro-prod-b1"
    assert found["endpoint"] == ENDPOINT
    assert found["metrics_url"] == "http://172.29.0.33:8427"
    assert found["cert"].startswith("-----BEGIN CERTIFICATE-----")


@needs_idf
def test_main_prints_only_key_names(certs, capsys, monkeypatch):
    _, size = prov_partition()
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(sys, "executable", IDF_PYTHON)
    assert make_prov.main(["make_prov.py", str(certs), ENDPOINT, "petro-prod-b1", size]) == 0
    out = capsys.readouterr()
    assert out.out.split() == prov_c_keys()
    assert "dummy" not in out.out + out.err
