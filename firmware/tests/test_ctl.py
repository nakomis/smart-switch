"""port/ctl: the mode, the relay, the trip latch and relay cycle, through petro-ctl.

Spec (CLAUDE.md, Control; PETRO-3): one button cycling the mode on -> off -> auto -> on (Martin's
decision; nothing stored means off); on and off are local overrides, so remote relay commands are refused;
auto follows remote commands; the mode persists and is the power-on state; a press with a trip
latched clears the trip and leaves the relay off.
"""

import json
import subprocess

import pytest

from conftest import BUILD


class Ctl:
    """One petro-ctl process: state carries over from line to line."""

    def __init__(self):
        self.proc = subprocess.Popen([str(BUILD / "petro-ctl")], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True)

    def __call__(self, op, **kw):
        self.proc.stdin.write(json.dumps({"op": op, **kw}) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


@pytest.fixture
def c():
    ctl = Ctl()
    yield ctl
    ctl.close()


OFF, ON, AUTO = 0, 1, 2


def in_auto(c):
    c("init", stored=True, mode=AUTO)


# ---- power-on --------------------------------------------------------------------------------

def test_nothing_stored_starts_off(c):
    s = c("init", stored=False, mode=ON)
    assert s["mode"] == "off" and s["relay"] is False and s["trip"] is None
    assert s["trip_amps"] == 10.5 and s["temporary"] is False


@pytest.mark.parametrize("stored,mode,relay", [(OFF, "off", False), (ON, "on", True), (AUTO, "auto", False)])
def test_the_stored_mode_is_the_power_on_state(c, stored, mode, relay):
    s = c("init", stored=True, mode=stored)
    assert (s["mode"], s["relay"]) == (mode, relay)


@pytest.mark.parametrize("junk", [3, -1, 255])
def test_a_stored_mode_out_of_range_starts_off(c, junk):
    assert c("init", stored=True, mode=junk)["mode"] == "off"


# ---- the button -------------------------------------------------------------------------------

def test_presses_cycle_on_off_auto_on(c):
    c("init", stored=True, mode=ON)
    assert [(s["mode"], s["relay"]) for s in (c("press"), c("press"), c("press"))] == [
        ("off", False), ("auto", False), ("on", True)]


def test_from_off_two_presses_reach_on(c):
    c("init")
    assert c("press")["mode"] == "auto"
    s = c("press")
    assert (s["mode"], s["relay"]) == ("on", True)


def test_entering_auto_by_button_starts_with_the_relay_off(c):
    in_auto(c)
    assert c("relay", on=True)["relay"] is True
    c("press")  # auto -> on
    c("press")  # on -> off
    s = c("press")  # off -> auto
    assert s["mode"] == "auto" and s["relay"] is False


# ---- remote commands ------------------------------------------------------------------------

def test_auto_follows_remote_relay_commands(c):
    in_auto(c)
    assert c("relay", on=True)["relay"] is True
    assert c("relay", on=False)["relay"] is False


@pytest.mark.parametrize("mode", [OFF, ON])
def test_remote_relay_commands_are_refused_in_on_and_off(c, mode):
    c("init", stored=True, mode=mode)
    s = c("relay", on=mode == OFF)
    assert s["result"] == "not_auto"
    assert s["relay"] is (mode == ON)
    assert s["remote"] is False


def test_set_mode(c):
    c("init")
    assert c("mode", mode="on")["relay"] is True
    s = c("mode", mode="auto")
    assert (s["mode"], s["relay"], s["remote"]) == ("auto", False, True)
    assert c("mode", mode="off")["relay"] is False


def test_an_invalid_mode_is_refused(c):
    c("init")
    assert c("mode", mode="bogus")["result"] == "invalid"


def test_setting_the_same_mode_changes_nothing(c):
    in_auto(c)
    c("relay", on=True)
    s = c("mode", mode="auto")
    assert s["result"] == "ok" and s["relay"] is True


# ---- trips -------------------------------------------------------------------------------------

def test_a_trip_opens_the_relay_and_latches(c):
    c("init", stored=True, mode=ON)
    s = c("trip", cause="overcurrent")
    assert s["result"] == "new" and s["relay"] is False and s["trip"] == "overcurrent"
    assert c("trip", cause="overtemp") == {**s, "result": "not_new"}  # the first cause stays
    assert c("trip", cause="none")["result"] == "not_new"


def test_no_cause_is_no_trip(c):
    c("init", stored=True, mode=ON)
    s = c("trip", cause="none")
    assert s["result"] == "not_new" and s["relay"] is True and s["trip"] is None


def test_a_press_clears_a_trip_and_leaves_the_relay_off(c):
    c("init", stored=True, mode=ON)
    c("trip", cause="overcurrent")
    s = c("press")
    assert (s["trip"], s["mode"], s["relay"]) == (None, "off", False)
    assert c("press")["mode"] == "auto"  # and the next press is an ordinary one: off -> auto


def test_while_tripped_nothing_remote_closes_the_relay(c):
    in_auto(c)
    c("trip", cause="overtemp")
    assert c("relay", on=True)["result"] == "tripped"
    assert c("mode", mode="on")["result"] == "tripped"
    assert c("mode", mode="auto")["result"] == "tripped"
    assert c("cycle", n=3, on_ms=100, off_ms=100)["result"] == "tripped"
    assert c("bench_cycle", n=3, on_ms=100, off_ms=100)["result"] == "tripped"
    assert c("bench", on=True)["result"] == "tripped"
    s = c("tick")
    assert s["relay"] is False and s["remote"] is False


def test_set_mode_off_clears_a_trip(c):
    in_auto(c)
    c("trip", cause="overcurrent")
    s = c("mode", mode="off")
    assert (s["result"], s["trip"], s["mode"], s["relay"]) == ("ok", None, "off", False)


def test_bench_off_is_allowed_while_tripped(c):
    c("init")
    c("trip", cause="overcurrent")
    assert c("bench", on=False)["result"] == "ok"


def test_a_trip_clears_auto_s_wish(c):
    in_auto(c)
    c("relay", on=True)
    c("trip", cause="overcurrent")
    c("mode", mode="off")
    assert c("mode", mode="auto")["relay"] is False


# ---- the trip threshold ------------------------------------------------------------------------

def test_a_temporary_threshold(c):
    c("init")
    s = c("amps", amps=6.5)
    assert (s["result"], s["trip_amps"], s["temporary"]) == ("ok", 6.5, True)
    s = c("amps", amps=-1)
    assert (s["trip_amps"], s["temporary"]) == (10.5, False)


@pytest.mark.parametrize("amps", [0.49, 10.51, 16, 0])
def test_a_threshold_out_of_range_is_refused(c, amps):
    c("init")
    s = c("amps", amps=amps)
    assert s["result"] == "invalid" and s["trip_amps"] == 10.5


def test_a_reboot_forgets_the_temporary_threshold(c):
    c("init")
    c("amps", amps=2)
    assert c("init", stored=True, mode=ON)["trip_amps"] == 10.5


# ---- relay cycle --------------------------------------------------------------------------------

def test_a_remote_cycle_runs_n_times_then_leaves_the_relay_off(c):
    in_auto(c)
    c("relay", on=True, now=0)
    s = c("cycle", n=2, on_ms=100, off_ms=200, now=1000)
    assert s["relay"] is True and s["cycle"] == {"done": 0, "n": 2}
    trace = [(t, c("tick", now=t)["relay"]) for t in (1099, 1100, 1299, 1300, 1399, 1400, 1599)]
    assert trace == [(1099, True), (1100, False), (1299, False), (1300, True), (1399, True), (1400, False),
                     (1599, False)]
    s = c("tick", now=1600)
    assert s["relay"] is False and s["cycle"] is None
    assert c("tick", now=5000)["relay"] is False  # auto's wish is off afterwards


def test_a_late_loop_stretches_a_phase_and_never_skips_one(c):
    in_auto(c)
    c("cycle", n=1, on_ms=100, off_ms=100, now=0)
    s = c("tick", now=5000)  # far past both phases: one step only
    assert s["relay"] is False and s["cycle"] == {"done": 0, "n": 1}
    assert c("tick", now=5099)["cycle"] is not None
    assert c("tick", now=5100)["cycle"] is None


def test_remote_cycles_are_auto_only(c):
    c("init", stored=True, mode=ON)
    assert c("cycle", n=2, on_ms=100, off_ms=100)["result"] == "not_auto"


@pytest.mark.parametrize("n,on,off", [(0, 100, 100), (10001, 50, 50), (5, 49, 100), (5, 100, 60001),
                                      (10000, 360, 361), (61, 60000, 60000)])
def test_cycles_out_of_range_are_refused(c, n, on, off):
    in_auto(c)
    assert c("cycle", n=n, on_ms=on, off_ms=off)["result"] == "invalid"
    assert c("bench_cycle", n=n, on_ms=on, off_ms=off)["result"] == "invalid"


def test_the_console_cap_is_an_hour(c):
    c("init")
    assert c("bench_cycle", n=10000, on_ms=180, off_ms=180)["result"] == "ok"  # exactly an hour
    assert c("bench_cycle", n=10000, on_ms=180, off_ms=181)["result"] == "invalid"
    assert c("bench_cycle", n=500, on_ms=3000, off_ms=5000)["result"] == "invalid"  # 67 min


def test_the_fleet_cap_is_two_hours(c):
    in_auto(c)
    assert c("cycle", n=500, on_ms=3000, off_ms=5000)["result"] == "ok"  # Gate 4: 67 min
    assert c("cycle", n=10000, on_ms=360, off_ms=360)["result"] == "ok"  # exactly two hours
    assert c("cycle", n=10000, on_ms=360, off_ms=361)["result"] == "invalid"


@pytest.mark.parametrize("interrupt", [
    ("press", {}), ("mode", {"mode": "off"}), ("relay", {"on": True}), ("trip", {"cause": "overcurrent"}),
    ("bench", {"on": False}),
])
def test_a_cycle_is_stopped_by_presses_mode_relay_trip_and_bench(c, interrupt):
    in_auto(c)
    c("cycle", n=5, on_ms=100, off_ms=100, now=0)
    op, kw = interrupt
    assert c(op, now=10, **kw)["cycle"] is None


def test_cycle_stop(c):
    in_auto(c)
    assert c("stop")["result"] == "idle"
    c("cycle", n=5, on_ms=100, off_ms=100, now=0)
    s = c("stop", now=10)
    assert s["result"] == "stopped" and s["relay"] is False and s["cycle"] is None


def test_a_console_cycle_runs_in_any_mode_and_leaves_the_relay_off(c):
    c("init", stored=True, mode=ON)
    assert c("bench_cycle", n=1, on_ms=100, off_ms=100, now=0)["relay"] is True
    assert c("tick", now=100)["relay"] is False
    s = c("tick", now=200)
    assert s["cycle"] is None and s["relay"] is False and s["bench"] is True and s["mode"] == "on"
    assert c("press")["mode"] == "off"  # a press ends the bench override: on -> off


def test_a_stopped_console_cycle_leaves_the_relay_off(c):
    c("init", stored=True, mode=ON)
    c("bench_cycle", n=3, on_ms=100, off_ms=100, now=0)
    s = c("stop", now=50)
    assert s["relay"] is False and s["bench"] is True


# ---- the bench override ----------------------------------------------------------------------

def test_the_bench_drives_the_relay_until_a_press(c):
    c("init")
    s = c("bench", on=True)
    assert s["relay"] is True and s["bench"] is True and s["mode"] == "off"
    s = c("press")
    assert s["bench"] is False and s["mode"] == "auto" and s["relay"] is False


def test_the_bench_ends_with_a_mode_change_or_a_remote_relay_command(c):
    in_auto(c)
    c("bench", on=True)
    s = c("relay", on=False)
    assert s["bench"] is False and s["relay"] is False
    c("bench", on=True)
    assert c("mode", mode="off")["bench"] is False


def test_messages(tool):
    lines = tool("petro-fleetcmd", "messages")().splitlines()
    assert lines[0] == "ok"
    assert "set mode auto" in lines[1]
    assert "press the button" in lines[2]
    assert lines[3] == "out of range"
    assert lines[4] == "?"
    assert lines[5] == "? error"
