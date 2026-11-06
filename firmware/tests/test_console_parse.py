"""port/console_parse: the Gate 2 console's command lines."""

import pytest


@pytest.fixture
def parse(json_tool):
    run = json_tool("petro-console")
    return lambda line: run(line)[0]


@pytest.mark.parametrize("line,kind", [
    ("help", "help"), ("info", "info"), ("button", "button"), ("bl", "bl"), ("edges", "edges"),
    ("ntc", "ntc"), ("j3", "j3"), ("wifi scan", "wifi scan"), ("relay on", "relay on"),
    ("relay off", "relay off"), ("  info  ", "info"), ("\trelay\ton", "relay on"),
])
def test_plain_commands(parse, line, kind):
    assert parse(line) == {"ok": True, "kind": kind}


def test_relay_cycle(parse):
    assert parse("relay cycle 20 200 200") == {"ok": True, "kind": "relay cycle", "n": 20,
                                                "on_ms": 200, "off_ms": 200}


def test_relay_cycle_limits(parse):
    assert parse("relay cycle 10000 50 50")["ok"]
    assert parse("relay cycle 1 60000 60000")["ok"]
    assert parse("relay cycle 10000 180 180")["ok"]  # exactly an hour


@pytest.mark.parametrize("line", [
    "relay cycle 10000 60000 60000",  # about 14 days
    "relay cycle 10000 180 181",      # an hour and 10 s
    "relay cycle 31 60000 60000",     # 62 minutes
])
def test_relay_cycle_over_an_hour_is_refused(parse, line):
    r = parse(line)
    assert r["ok"] is False
    assert "at most 1 h" in r["error"]


@pytest.mark.parametrize("line,why", [
    ("relay cycle 0 200 200", "n must be"),
    ("relay cycle 10001 200 200", "n must be"),
    ("relay cycle 5 49 200", "on_ms must be"),
    ("relay cycle 5 200 60001", "off_ms must be"),
    ("relay cycle 5 -200 200", "on_ms must be"),
    ("relay cycle 5 2e2 200", "on_ms must be"),
    ("relay cycle 5 200", "usage: relay cycle"),
    ("relay cycle 5 200 200 9", "usage: relay cycle"),
    ("relay cycle 9999999999 200 200", "n must be"),
])
def test_relay_cycle_rejects(parse, line, why):
    r = parse(line)
    assert r["ok"] is False
    assert why in r["error"]


@pytest.mark.parametrize("mode", ["on", "off", "auto"])
def test_mode(parse, mode):
    assert parse(f"mode {mode}") == {"ok": True, "kind": "mode", "mode": mode}


@pytest.mark.parametrize("line", ["mode", "mode toggle", "mode on now", "mode ON"])
def test_mode_rejects(parse, line):
    r = parse(line)
    assert r["ok"] is False
    assert "usage: mode on" in r["error"]


def test_led_auto(parse):
    assert parse("led auto") == {"ok": True, "kind": "led auto"}


def test_led(parse):
    assert parse("led 255 0 128") == {"ok": True, "kind": "led", "r": 255, "g": 0, "b": 128}


@pytest.mark.parametrize("line,why", [
    ("led 256 0 0", "'256' is not 0-255"),
    ("led 0 -1 0", "'-1' is not 0-255"),
    ("led 0 0 x", "'x' is not 0-255"),
    ("led 0 0", "expected 3 arguments, got 2"),
    ("led auto now", "expected 3 arguments, got 2"),
    ("led 0 0 0 0", "expected 3 arguments, got 4"),
])
def test_led_rejects(parse, line, why):
    r = parse(line)
    assert r["ok"] is False
    assert why in r["error"]


@pytest.mark.parametrize("line,why", [
    ("info now", "expected 0 arguments, got 1"),
    ("relay", "usage: relay on"),
    ("relay on now", "relay on: no arguments"),
    ("relay toggle", "unknown subcommand 'toggle'"),
    ("wifi", "usage: wifi scan"),
    ("wifi join", "usage: wifi scan"),
    ("reboot", "unknown command 'reboot'"),
    ("INFO", "unknown command 'INFO'"),
    ("", "empty command"),
    ("a b c d e f g h i", "too many words"),
])
def test_rejects(parse, line, why):
    r = parse(line)
    assert r["ok"] is False
    assert why in r["error"]


def test_usage_lists_every_command(tool):
    usage = tool("petro-console", "usage")()
    for word in ("info", "mode auto", "led auto", "relay on", "relay cycle", "led", "button", "bl", "edges", "ntc",
                 "wifi scan", "j3", "help"):
        assert word in usage
