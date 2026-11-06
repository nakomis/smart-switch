"""port/fleet_cmd: Petro's own commands on petro/<thing>/commands (docs/testing/README.md: relay
on/off, the mode, relay cycle, a temporary trip threshold, Wi-Fi transmit stress)."""

import json

import pytest


@pytest.fixture
def parse(tool):
    run = tool("petro-fleetcmd")

    def go(cmd):
        line = cmd if isinstance(cmd, str) else json.dumps(cmd)
        return json.loads(run(line + "\n"))

    return go


@pytest.mark.parametrize("cmd,want", [
    ({"command": "get_status"}, {"kind": "get_status", "type": "get_status_result"}),
    ({"command": "relay", "on": True}, {"kind": "relay", "type": "relay_result", "on": True}),
    ({"command": "relay", "on": False}, {"kind": "relay", "type": "relay_result", "on": False}),
    ({"command": "set_mode", "mode": "auto"}, {"kind": "set_mode", "type": "set_mode_result", "mode": "auto"}),
    ({"command": "relay_cycle", "n": 500, "on_ms": 3000, "off_ms": 5000},
     {"kind": "relay_cycle", "type": "relay_cycle_result", "n": 500, "on_ms": 3000, "off_ms": 5000}),
    ({"command": "relay_cycle", "n": 10000, "on_ms": 360, "off_ms": 360},
     {"kind": "relay_cycle", "type": "relay_cycle_result", "n": 10000, "on_ms": 360, "off_ms": 360}),
    ({"command": "relay_cycle_stop"}, {"kind": "relay_cycle_stop", "type": "relay_cycle_stop_result"}),
    ({"command": "set_trip_threshold", "amps": 6.5},
     {"kind": "set_trip_threshold", "type": "set_trip_threshold_result", "amps": 6.5}),
    ({"command": "set_trip_threshold", "amps": None},
     {"kind": "set_trip_threshold", "type": "set_trip_threshold_result", "amps": None}),
    ({"command": "set_trip_threshold", "instant_amps": 12},
     {"kind": "set_trip_threshold", "type": "set_trip_threshold_result", "instant_amps": 12}),
    ({"command": "set_trip_threshold", "amps": 5, "instant_amps": None},
     {"kind": "set_trip_threshold", "type": "set_trip_threshold_result", "amps": 5, "instant_amps": None}),
    ({"command": "set_trip_threshold", "amps": 0.5, "instant_amps": 1},
     {"kind": "set_trip_threshold", "type": "set_trip_threshold_result", "amps": 0.5, "instant_amps": 1}),
    ({"command": "set_trip_threshold", "instant_amps": 15},
     {"kind": "set_trip_threshold", "type": "set_trip_threshold_result", "instant_amps": 15}),
    ({"command": "clear_trip"}, {"kind": "clear_trip", "type": "clear_trip_result"}),
    ({"command": "wifi_stress", "on": True},
     {"kind": "wifi_stress", "type": "wifi_stress_result", "on": True, "duration_s": 3600}),
    ({"command": "wifi_stress", "on": True, "duration_s": 60},
     {"kind": "wifi_stress", "type": "wifi_stress_result", "on": True, "duration_s": 60}),
    ({"command": "wifi_stress", "on": False},
     {"kind": "wifi_stress", "type": "wifi_stress_result", "on": False, "duration_s": 3600}),
    ({"command": "reboot"}, {"kind": "reboot", "type": "reboot_result"}),
])
def test_commands(parse, cmd, want):
    assert parse(cmd) == want


@pytest.mark.parametrize("command", ["get_version", "ping", "ota_update", "url_chunk", "ota_cancel"])
def test_fleet_s_own_commands_are_passed_on_unread(parse, command):
    assert parse({"command": command, "junk": [1]}) == {"kind": "fleet", "type": "error"}


@pytest.mark.parametrize("cmd,why", [
    ({"command": "relay"}, "boolean on"),
    ({"command": "relay", "on": 1}, "boolean on"),
    ({"command": "set_mode"}, "mode must be"),
    ({"command": "set_mode", "mode": "AUTO"}, "mode must be"),
    ({"command": "set_mode", "mode": 2}, "mode must be"),
    ({"command": "relay_cycle", "n": 5, "on_ms": 100}, "whole numbers"),
    ({"command": "relay_cycle", "n": 5.5, "on_ms": 100, "off_ms": 100}, "whole numbers"),
    ({"command": "relay_cycle", "n": -1, "on_ms": 100, "off_ms": 100}, "whole numbers"),
    ({"command": "relay_cycle", "n": "5", "on_ms": 100, "off_ms": 100}, "whole numbers"),
    ({"command": "relay_cycle", "n": 5e12, "on_ms": 100, "off_ms": 100}, "whole numbers"),
    ({"command": "relay_cycle", "n": 0, "on_ms": 100, "off_ms": 100}, "at most 2 h"),
    ({"command": "relay_cycle", "n": 5, "on_ms": 49, "off_ms": 100}, "at most 2 h"),
    ({"command": "relay_cycle", "n": 61, "on_ms": 60000, "off_ms": 60000}, "at most 2 h"),
    ({"command": "relay_cycle", "n": 10000, "on_ms": 360, "off_ms": 361}, "at most 2 h"),
    ({"command": "set_trip_threshold"}, "amps must be"),
    ({"command": "set_trip_threshold", "amps": 10.6}, "amps must be"),
    ({"command": "set_trip_threshold", "amps": 0.4}, "amps must be"),
    ({"command": "set_trip_threshold", "amps": "5"}, "amps must be"),
    ({"command": "set_trip_threshold", "instant_amps": 15.1}, "instant_amps must be 1-15"),
    ({"command": "set_trip_threshold", "instant_amps": 0.9}, "instant_amps must be 1-15"),
    ({"command": "set_trip_threshold", "amps": 5, "instant_amps": "x"}, "instant_amps must be"),
    ({"command": "set_trip_threshold", "amps": 11, "instant_amps": 5}, "amps must be 0.5-10.5"),
    ({"command": "wifi_stress"}, "boolean on"),
    ({"command": "wifi_stress", "on": True, "duration_s": 59}, "duration_s"),
    ({"command": "wifi_stress", "on": True, "duration_s": 7201}, "duration_s"),
    ({"command": "wifi_stress", "on": True, "duration_s": None}, "duration_s"),
    ({"command": "bogus"}, "unknown command"),
    ({"cmd": "relay"}, "missing command"),
    ({"command": 7}, "missing command"),
    ("[1, 2]", "not a JSON object"),
    ("not json", "not a JSON object"),
    ('{"command":"reboot"} x', "trailing bytes"),
    ("[" * 9 + "]" * 9, "too deeply nested"),
    ('{"command":"get_status","a":"[[[[[[[[[["}', None),
    ('{"command":"get_status","a":"\\"[[[[[[[[["}', None),
])
def test_refused(parse, cmd, why):
    r = parse(cmd)
    if why is None:  # brackets inside strings don't count
        assert r["kind"] == "get_status"
    else:
        assert r["kind"] == "error" and r["type"] == "error"
        assert why in r["message"]


def test_trailing_whitespace_and_nul_are_fine(parse):
    assert parse('{"command":"reboot"} \\0')["kind"] == "reboot"


def test_empty(parse):
    assert parse("")["message"] == "not a JSON object"


def test_closing_brackets_without_openers_are_harmless(parse):
    assert parse("]]]" + "{" * 3)["kind"] == "error"
