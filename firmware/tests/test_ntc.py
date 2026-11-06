"""port/ntc: TH1 (10k, B 3950) under 10k from 3.3 V."""

import math

import pytest

B = 3950.0


def mv_at(celsius: float) -> float:
    r = 10_000 * math.exp(B * (1 / (celsius + 273.15) - 1 / 298.15))
    return 3300 * r / (r + 10_000)


@pytest.fixture
def ntc(json_tool):
    run = json_tool("petro-ntc")
    return lambda line: run(line)[0]


def test_25c_is_half_the_supply(ntc):
    r = ntc("1650")
    assert r["ok"]
    assert r["ohms"] == pytest.approx(10_000)
    assert r["celsius"] == pytest.approx(25.0, abs=1e-6)


@pytest.mark.parametrize("celsius", [-19.9, 0, 20, 40, 70, 100, 149.9])
def test_round_trip(ntc, celsius):
    mv = ntc(f"at {celsius}")["mv"]
    assert mv == pytest.approx(mv_at(celsius))
    assert ntc(f"{mv}")["celsius"] == pytest.approx(celsius, abs=1e-6)


def test_known_points(ntc):
    """By hand from the B equation: about 2543 mV at 0 C and 871 mV at 50 C."""
    assert ntc("at 0")["mv"] == pytest.approx(2543, abs=1)
    assert ntc("at 50")["mv"] == pytest.approx(871, abs=1)
    assert ntc("871.4")["celsius"] == pytest.approx(50, abs=0.05)


def test_warmer_reads_lower(ntc):
    assert ntc("at 30")["mv"] < ntc("at 25")["mv"] < ntc("at 20")["mv"]


@pytest.mark.parametrize("mv", ["0", "-5", "3300", "3400"])
def test_open_or_short_is_refused(ntc, mv):
    assert ntc(mv) == {"ok": False}


@pytest.mark.parametrize("mv", [
    "3299", "3260", "3251",          # open NTC: near the supply
    "1", "40", "49.9",               # shorted: near 0 V
    f"{mv_at(-21):.3f}",             # colder than -20 C
    f"{mv_at(151):.3f}",             # hotter than 150 C
])
def test_implausible_readings_are_refused(ntc, mv):
    assert ntc(mv) == {"ok": False}


def test_the_window_s_edges_are_accepted(ntc):
    assert ntc(f"{mv_at(-19.99):.6f}")["ok"] and ntc(f"{mv_at(149.99):.6f}")["ok"]


def test_unknown_line(ntc):
    assert ntc("hello") == {"error": "unknown"}
