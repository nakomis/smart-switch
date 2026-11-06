"""port/zx: zero-cross switching (PETRO-5), through petro-zx.

Spec: time the relay's close and open to the ZX crossings, allowing for the relay's operate
(~8 ms) and release (~4 ms) times; switch at once if there have been no ZX edges for 100 ms (no
mains, on USB). Trips never wait: that is the caller's (app.c), not tested here.
"""

import json

import pytest

OPERATE, RELEASE = 8000, 4000


@pytest.fixture
def zx(tool):
    run = tool("petro-zx")

    def go(edges, now, actuate):
        return json.loads(run(json.dumps({"edges": edges, "now": now, "actuate": actuate}) + "\n"))

    return go


def fifty(start=0, n=3, half=10000, offset=0):
    """n edges of 50 Hz mains from start: alternate halves half+offset and half-offset."""
    t, out = start, []
    for i in range(n):
        out.append(t)
        t += half + (offset if i % 2 == 0 else -offset)
    return out


def test_closing_lands_on_a_crossing(zx):
    edges = fifty()  # 0, 10000, 20000
    r = zx(edges, now=20100, actuate=OPERATE)
    assert r["period"] == 20000
    # earliest the contacts can move: 20100 + 500 + 8000 = 28600 -> the crossing at 30000
    assert r["at"] == 30000 - OPERATE


def test_opening_allows_for_the_release_time(zx):
    r = zx(fifty(), now=20100, actuate=RELEASE)
    # 20100 + 500 + 4000 = 24600 -> 30000
    assert r["at"] == 30000 - RELEASE


def test_too_close_to_a_crossing_waits_for_the_next(zx):
    r = zx(fifty(), now=21600, actuate=OPERATE)  # 21600 + 8500 = 30100 > 30000
    assert r["at"] == 40000 - OPERATE


def test_exactly_on_the_lead_is_fine(zx):
    r = zx(fifty(), now=21500, actuate=OPERATE)  # 21500 + 8500 = 30000
    assert r["at"] == 30000 - OPERATE


def test_unequal_halves_still_predict_both_kinds_of_crossing(zx):
    edges = fifty(offset=400)  # 0, 10400, 20000: rising halves 10.4 ms, falling 9.6 ms
    assert zx(edges, now=20100, actuate=0)["at"] == 30400  # the same kind as 10400
    assert zx(edges, now=31000, actuate=0)["at"] == 40000  # then the same kind as 20000


def test_the_prediction_runs_several_periods_on(zx):
    r = zx(fifty(), now=95000, actuate=OPERATE)  # last edge 75 ms ago: still fresh
    assert r["at"] == 110000 - OPERATE


def test_the_coil_is_never_driven_before_now_plus_the_lead(zx):
    for now in range(20000, 60000, 777):
        for act in (0, RELEASE, OPERATE, 15000):
            at = zx(fifty(), now=now, actuate=act)["at"]
            assert at >= now + 500
            assert (at + act) % 10000 == 0  # on a crossing
            assert at + act - (now + 500 + act) < 10000  # the first one possible


@pytest.mark.parametrize("edges,now", [
    ([], 0),
    ([0], 100),
    ([0, 10000], 10100),
    (fifty(), 20000 + 100001),  # stale: no edge for over 100 ms
])
def test_no_crossings_switches_at_once(zx, edges, now):
    r = zx(edges, now=now, actuate=OPERATE)
    assert (r["period"], r["at"]) == (0, -1)


def test_just_inside_100_ms_still_predicts(zx):
    assert zx(fifty(), now=20000 + 100000, actuate=OPERATE)["at"] > 0


@pytest.mark.parametrize("half", [7900, 12600])
def test_not_mains_frequency_switches_at_once(zx, half):
    r = zx(fifty(half=half), now=2 * half + 100, actuate=OPERATE)
    assert r["at"] == -1


@pytest.mark.parametrize("half", [8000, 12500])  # 62.5 and 40 Hz: the limits
def test_the_frequency_limits(zx, half):
    assert zx(fifty(half=half), now=2 * half + 100, actuate=OPERATE)["period"] == 2 * half


def test_lopsided_halves_are_noise(zx):
    assert zx([0, 3000, 20000], now=20100, actuate=OPERATE)["at"] == -1
    assert zx([0, 17000, 20000], now=20100, actuate=OPERATE)["at"] == -1
    assert zx([0, 5000, 20000], now=20100, actuate=0)["at"] != -1  # a quarter: the limit


def test_a_negative_actuation_time_switches_at_once(zx):
    assert zx(fifty(), now=20100, actuate=-1)["at"] == -1


def test_only_the_last_three_edges_count(zx):
    edges = [0, 3000, 7000] + fifty(start=100000)  # noise first, then clean mains
    r = zx(edges, now=120100, actuate=0)
    assert (r["n"], r["period"], r["at"]) == (3, 20000, 130000)
