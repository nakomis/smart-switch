"""port/prot: when Petro trips (PETRO-5), whether the meter can be trusted, and when a trip may be
cleared, through petro-prot.

Spec (PETRO-5): over-current 10.5 A sustained for 2 s, from the RMS readings; an instant trip from
the BL0939's OC output; over-temperature at 55 C on the NTC (provisional until Gate 4 5), with a
5 C hysteresis on clearing; a meter fault if relay-on is wanted with the BL0939 not initialised or
its readings stale (> 3 s without a good frame); the NTC limit from Gate 4 5's formula.
"""

import json
import subprocess

import pytest

from conftest import BUILD


class Prot:
    def __init__(self):
        self.proc = subprocess.Popen([str(BUILD / "petro-prot")], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True)

    def __call__(self, op, **kw):
        self.proc.stdin.write(json.dumps({"op": op, **kw}) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


@pytest.fixture
def p():
    prot = Prot()
    yield prot
    prot.close()


def healthy(p, now=0, amps=0.2, c=30.0):
    """A started meter with a fresh frame and NTC reading at now."""
    p("meter", ok=True, now=now)
    p("frame", amps=amps, limit=10.5, now=now)
    return p("temp", c=c, now=now)


def test_the_defaults(p):
    assert p("defaults") == {"sustain_ms": 2000, "overtemp_c": 55, "overtemp_ms": 2000, "clear_margin_c": 5,
                             "stale_ms": 3000}


# ---- health -------------------------------------------------------------------------------------

def test_healthy_needs_the_meter_started_a_frame_and_the_ntc(p):
    s = p("tick")
    assert (s["healthy"], s["starting"]) == (False, False)  # the BL0939 hasn't started
    p("meter", ok=True)
    assert p("tick") == {"trip": None, "healthy": False, "starting": True, "blocked": False}
    p("frame", amps=0.1)
    assert p("tick")["healthy"] is False  # the NTC not yet
    assert p("temp", c=25)["healthy"] is True


def test_while_starting_relay_on_is_held_without_a_trip(p):
    p("meter", ok=True)
    assert p("tick", now=2999, wanted=True)["trip"] is None
    s = p("tick", now=3000, wanted=True)
    assert (s["trip"], s["starting"]) == ("meter_fault", False)


def test_a_meter_that_did_not_start_is_a_fault_at_once(p):
    p("meter", ok=False)
    p("frame", amps=0.1)
    p("temp", c=25)
    s = p("tick", wanted=True)
    assert (s["trip"], s["healthy"], s["starting"]) == ("meter_fault", False, False)


def test_unhealthy_with_the_relay_off_is_no_trip(p):
    assert p("tick", now=10000, wanted=False)["trip"] is None


@pytest.mark.parametrize("stale_op", ["frame", "temp"])
def test_stale_readings_fault_after_3_s(p, stale_op):
    healthy(p, now=10000)
    # keep the other one fresh
    fresh = {"frame": ("temp", {"c": 30.0}), "temp": ("frame", {"amps": 0.2})}[stale_op]
    p(fresh[0], now=13000, **fresh[1])
    assert p("tick", now=13000, wanted=True) == {"trip": None, "healthy": True, "starting": False,
                                                 "blocked": False}
    p(fresh[0], now=13001, **fresh[1])
    s = p("tick", now=13001, wanted=True)
    assert (s["trip"], s["healthy"]) == ("meter_fault", False)


def test_an_unreadable_ntc_lets_the_last_reading_age(p):
    healthy(p, now=0)
    p("temp", now=2000)  # couldn't read: no "c"
    assert p("tick", now=3000)["healthy"] is True
    p("frame", amps=0.2, now=3500)
    assert p("tick", now=3500)["healthy"] is False


# ---- over-current, sustained --------------------------------------------------------------------

def test_over_current_trips_after_2_s_without_a_break(p):
    healthy(p)
    assert p("frame", amps=10.6, now=1000)["trip"] is None
    for t in (1250, 1500, 2000, 2999):
        assert p("frame", amps=12, now=t)["trip"] is None
    assert p("frame", amps=10.51, now=3000)["trip"] == "overcurrent"


def test_a_reading_at_or_below_the_threshold_restarts_the_window(p):
    healthy(p)
    p("frame", amps=11, now=1000)
    p("frame", amps=10.5, now=2500)  # at the threshold is not over
    assert p("frame", amps=11, now=3000)["trip"] is None
    assert p("frame", amps=11, now=4999)["trip"] is None
    assert p("frame", amps=11, now=5000)["trip"] == "overcurrent"


def test_the_window_runs_on_the_clock_between_frames(p):
    healthy(p)
    p("frame", amps=11, now=1000)
    assert p("tick", now=2999)["trip"] is None
    assert p("tick", now=3000)["trip"] == "overcurrent"  # the control task's check, no new frame


def test_the_temporary_threshold_is_the_one_in_force(p):
    healthy(p)
    p("frame", amps=8.7, limit=5.0, now=0)
    assert p("frame", amps=8.7, limit=5.0, now=2000)["trip"] == "overcurrent"


def test_over_current_trips_with_the_relay_open_too(p):
    healthy(p)
    p("frame", amps=11, now=0)
    assert p("tick", now=2000, wanted=False)["trip"] == "overcurrent"  # a welded contact


def test_an_infinite_current_counts_as_over(p):
    healthy(p)
    proc = p.proc
    proc.stdin.write('{"op":"frame","amps":1e999,"now":0}\n')  # inf: over
    proc.stdin.flush()
    json.loads(proc.stdout.readline())
    assert p("tick", now=2000)["trip"] == "overcurrent"


# ---- over-current, instant ----------------------------------------------------------------------

def test_the_oc_output_trips_at_once_and_blocks_a_clear(p):
    healthy(p)
    s = p("oc", on=True, latched="overcurrent_instant")
    assert (s["trip"], s["blocked"]) == ("overcurrent_instant", True)
    s = p("oc", on=False, latched="overcurrent_instant")
    assert (s["trip"], s["blocked"]) == (None, False)


def test_the_oc_output_comes_first(p):
    healthy(p)
    p("frame", amps=11, now=0)
    p("temp", c=60, now=0)
    p("oc", on=True)
    assert p("tick", now=5000, wanted=True)["trip"] == "overcurrent_instant"
    p("oc", on=False)
    assert p("tick", now=5000)["trip"] == "overcurrent"


# ---- over-temperature ---------------------------------------------------------------------------

def test_over_temperature_at_55_c_for_2_s(p):
    healthy(p, c=54.9)
    assert p("temp", c=55.0, now=100)["trip"] is None
    assert p("temp", c=56, now=2099)["trip"] is None
    assert p("temp", c=55.5, now=2100)["trip"] == "overtemp"


def test_a_cooler_reading_restarts_the_temperature_window(p):
    healthy(p)
    p("temp", c=56, now=0)
    p("temp", c=54, now=1000)
    p("temp", c=56, now=1500)
    assert p("tick", now=3499)["trip"] is None
    assert p("tick", now=3500)["trip"] == "overtemp"


def test_an_unreadable_ntc_keeps_the_window(p):
    healthy(p)
    p("temp", c=56, now=0)
    p("temp", now=1000)  # unreadable: doesn't reset it
    p("frame", amps=0.1, now=2000)
    assert p("tick", now=2000)["trip"] == "overtemp"


# ---- clearing: the hysteresis -------------------------------------------------------------------

@pytest.mark.parametrize("c,blocked", [(55, True), (50.01, True), (50.0, False), (30, False)])
def test_a_clear_is_blocked_within_5_c_of_the_limit(p, c, blocked):
    healthy(p, c=c)
    for cause in ("overtemp", "overcurrent", "meter_fault", "overcurrent_instant"):
        assert p("tick", latched=cause)["blocked"] is blocked, cause


def test_without_an_ntc_reading_only_an_overtemp_clear_is_blocked(p):
    p("meter", ok=True)
    assert p("tick", latched="overtemp")["blocked"] is True
    assert p("tick", latched="overcurrent")["blocked"] is False
    assert p("tick", latched="meter_fault")["blocked"] is False


def test_a_stale_ntc_reading_counts_as_none(p):
    healthy(p, c=54)
    assert p("tick", now=3000, latched="overcurrent")["blocked"] is True
    s = p("tick", now=3001, latched="overcurrent")
    assert s["blocked"] is False
    assert p("tick", now=3001, latched="overtemp")["blocked"] is True


# ---- the BL0939's threshold and Gate 4's formula ------------------------------------------------

PETRO_CPA = 324004 * 1 / 1.218  # bl0939_petro_scale().amps: counts per amp


@pytest.mark.parametrize("amps,value", [
    (15, round(15 * PETRO_CPA / 256)),   # 0x3CE3, the default
    (12, round(12 * PETRO_CPA / 256)),
    (1, round(PETRO_CPA / 256)),
    (100, 0x7FFF),                       # clamped: 15 bits
    (0, 1), (-3, 1),
])
def test_fast_rms_control(p, amps, value):
    assert p("ctrl", amps=amps, cpa=PETRO_CPA)["value"] == value


def test_the_default_fits_15_bits_with_half_cycle_refresh(p):
    v = p("ctrl", amps=15, cpa=PETRO_CPA)["value"]
    assert v == 0x3CE3 and v < 0x8000


def test_a_negative_infinite_fast_rms_is_the_lowest(p):
    p.proc.stdin.write('{"op":"ctrl","amps":1e999,"cpa":-1}\n')  # -inf
    p.proc.stdin.flush()
    assert json.loads(p.proc.stdout.readline())["value"] == 1


@pytest.mark.parametrize("room,ratio,limit", [(35, 1.75, 55.0), (35, 1.0, 70.0), (35, 2.5, 49.0), (20, 2.0, 45.0)])
def test_gate_4_s_formula(p, room, ratio, limit):
    assert p("limit", room=room, hot=70, ratio=ratio)["limit"] == pytest.approx(limit)
