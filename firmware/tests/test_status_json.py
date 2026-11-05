"""port/status_json: the /status message (relay, mode, trip, RSSI, uptime, version, V/A/W/energy,
the thresholds in force)."""

import json

import pytest

FULL = {"mode": "auto", "relay": True, "remote": True, "cycle_n": 500, "cycle_done": 3, "volts": 239.814,
        "amps": 0.26114, "watts": 61.237, "energy_kwh": 1.2345678, "board_c": 24.13, "zx_hz": 100.04,
        "trip_amps": 6.5, "trip_amps_temporary": True, "stress_s": 1234, "rssi": -61, "uptime_s": 3600,
        "reason": "change", "version": "0.2.0"}


@pytest.fixture
def status(tool):
    def go(view, cap=None):
        out = tool("petro-status", *([str(cap)] if cap else []))(json.dumps(view) + "\n").strip()
        return None if out == "-1" else json.loads(out)

    return go


def test_full(status):
    assert status(FULL) == {
        "mode": "auto", "relay": True, "trip": None, "remote": True, "bench": False,
        "cycle": {"done": 3, "n": 500}, "volts": 239.81, "amps": 0.2611, "watts": 61.24,
        "energy_kwh": 1.234568, "board_c": 24.1, "zx_hz": 100.0, "trip_amps": 6.5,
        "trip_amps_temporary": True, "trips_enforced": False, "stress_s": 1234, "rssi": -61,
        "uptime_s": 3600, "reason": "change", "version": "0.2.0"}


def test_unknowns_are_null(status):
    s = status({"mode": "off", "trip": "overcurrent", "bench": True, "trips_enforced": True})
    assert s["trip"] == "overcurrent" and s["bench"] is True and s["trips_enforced"] is True
    for key in ("cycle", "volts", "amps", "watts", "board_c", "zx_hz", "stress_s", "rssi", "version"):
        assert s[key] is None, key
    assert s["reason"] == "heartbeat" and s["energy_kwh"] == 0


@pytest.mark.parametrize("reason", ["boot", "heartbeat", "change", "request"])
def test_reasons(status, reason):
    assert status({"reason": reason})["reason"] == reason


def test_an_unknown_reason(status):
    assert status({"reason": "bogus"})["reason"] == "?"


def test_overtemp(status):
    assert status({"trip": "overtemp"})["trip"] == "overtemp"


def test_the_version_is_escaped(status):
    assert status({"version": 'a"b\\c\n'})["version"] == 'a"b\\c\n'


def test_it_fits_the_firmware_buffer(status):
    assert status(FULL, cap=512) is not None


@pytest.mark.parametrize("cap", [1, 30, 300])
def test_too_small_a_buffer_fails(status, cap):
    assert status(FULL, cap=cap) is None
