"""port/prom: the VictoriaMetrics push, exactly the metrics docs/testing/README.md lists."""

import json

import pytest

FULL = {"volts": 239.814, "amps": 0.26114, "watts": 61.237, "energy_kwh": 1.2345678, "board_c": 24.13,
        "relay": True, "zx_hz": 100.0, "rssi": -61, "uptime_s": 3600, "trips_overcurrent": 1,
        "trips_overtemp": 0, "resets": {"poweron": 2, "brownout": 1, "panic": 0}}


@pytest.fixture
def prom(tool):
    def go(sample, cap=None):
        out = tool("petro-prom", *([str(cap)] if cap else []))(json.dumps(sample) + "\n")
        return out if out.strip() == "-1" else out.split("--\n")[0]

    return go


def test_every_metric(prom):
    assert prom(FULL).splitlines() == [
        "petro_voltage_volts 239.81",
        "petro_current_amps 0.2611",
        "petro_power_watts 61.24",
        "petro_energy_kwh_total 1.234568",
        "petro_board_temperature_celsius 24.13",
        "petro_relay_on 1",
        "petro_zx_hz 100.0",
        "petro_wifi_rssi_dbm -61",
        "petro_uptime_seconds 3600",
        'petro_resets_total{reason="poweron"} 2',
        'petro_resets_total{reason="brownout"} 1',
        'petro_trips_total{cause="overcurrent"} 1',
        'petro_trips_total{cause="overtemp"} 0',
    ]


def test_unknown_readings_are_left_out(prom):
    lines = prom({"uptime_s": 5}).splitlines()
    assert lines == ["petro_energy_kwh_total 0.000000", "petro_relay_on 0", "petro_uptime_seconds 5",
                     'petro_trips_total{cause="overcurrent"} 0', 'petro_trips_total{cause="overtemp"} 0']


def test_nan_is_never_sent(prom):
    text = prom({**FULL, "volts": "nan", "board_c": "nan"})
    assert "nan" not in text.lower()
    assert "petro_current_amps" in text


def test_label_values_are_escaped(prom):
    assert 'petro_resets_total{reason="a\\"b\\\\c\\nd"} 1' in prom({"resets": {'a"b\\c\nd': 1}})


@pytest.mark.parametrize("cap", [1, 40, 200])
def test_too_small_a_buffer_fails_whole(prom, cap):
    assert prom(FULL, cap=cap).strip() == "-1"


def test_the_full_sample_fits_the_firmware_buffer(prom):
    assert prom(FULL, cap=1024).strip() != "-1"


@pytest.mark.parametrize("url,out", [
    ("http://172.29.0.33:8427", "http://172.29.0.33:8427/api/v1/import/prometheus"),
    ("http://172.29.0.33:8427/", "http://172.29.0.33:8427/api/v1/import/prometheus"),
    ("https://vm.example/", "https://vm.example/api/v1/import/prometheus"),
    ("http://cal:8427/write", "http://cal:8427/write"),
    ("http://cal:8427/api/v1/import/prometheus", "http://cal:8427/api/v1/import/prometheus"),
    ("http://cal:8427?x=1", "http://cal:8427?x=1"),
    ("ftp://cal", "invalid"),
    ("http://", "invalid"),
    ("http:///path", "invalid"),
    ("http://cal/a b", "invalid"),
    ("cal:8427", "invalid"),
    ("http://" + "a" * 200, "invalid"),
])
def test_the_push_url(tool, url, out):
    assert tool("petro-prom", "url", url)().strip() == out
