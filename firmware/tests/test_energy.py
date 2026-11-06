"""port/energy: petro_energy_kwh_total from the BL0939's CF count, kept across reboots."""

import json

import pytest

PPK = 5641.0  # Petro's CF pulses per kWh (bl0939_petro_scale)


@pytest.fixture
def e(json_tool):
    run = json_tool("petro-energy")
    lines = []

    def go(*ops):
        lines.extend(json.dumps(o) for o in ops)
        return run(*lines)[-1]

    return go


def test_the_first_reading_is_only_a_baseline(e):
    assert e({"op": "init", "stored_mwh": 0, "ppk": PPK}, {"op": "cf", "cnt": 500, "now": 0})["mwh"] == 0


def test_pulses_add_to_the_stored_total(e):
    s = e({"op": "init", "stored_mwh": 1_000_000, "ppk": PPK}, {"op": "cf", "cnt": 10, "now": 0},
          {"op": "cf", "cnt": 10 + 5641, "now": 3_600_000})
    assert s["mwh"] == 2_000_000 and s["kwh"] == pytest.approx(2.0)


def test_the_24_bit_counter_wrapping_is_counted(e):
    s = e({"op": "init", "ppk": PPK}, {"op": "cf", "cnt": 0xFFFFFE, "now": 0}, {"op": "cf", "cnt": 3, "now": 60_000})
    assert s["accepted"] and s["mwh"] == int(5 * 1e6 / PPK)


def test_an_implausible_jump_is_dropped_and_rebaselined(e):
    # 1000 pulses in one second would be ~640 kW.
    s = e({"op": "init", "ppk": PPK}, {"op": "cf", "cnt": 100, "now": 0}, {"op": "cf", "cnt": 1100, "now": 1000})
    assert s["accepted"] is False and s["mwh"] == 0 and s["rejected"] == 1
    s = e({"op": "cf", "cnt": 1102, "now": 2000})
    assert s["accepted"] and s["mwh"] == int(2 * 1e6 / PPK)


def test_a_chip_reset_counts_nothing(e):
    s = e({"op": "init", "ppk": PPK}, {"op": "cf", "cnt": 5000, "now": 0}, {"op": "cf", "cnt": 0, "now": 1000})
    assert s["accepted"] is False and s["mwh"] == 0


def test_a_clock_going_backwards_allows_only_timing_slack(e):
    s = e({"op": "init", "ppk": PPK}, {"op": "cf", "cnt": 0, "now": 1000}, {"op": "cf", "cnt": 2, "now": 500})
    assert s["accepted"]


def test_full_load_is_plausible(e):
    # 16 A at 250 V for 10 s: about 6.3 pulses a second.
    s = e({"op": "init", "ppk": PPK}, {"op": "cf", "cnt": 0, "now": 0}, {"op": "cf", "cnt": 63, "now": 10_000})
    assert s["accepted"]


def test_saved_every_10_minutes_when_it_changed(e):
    s = e({"op": "init", "ppk": PPK, "now": 0}, {"op": "cf", "cnt": 0, "now": 0}, {"op": "cf", "cnt": 1, "now": 1000})
    assert s["due"] is False
    assert e({"op": "due", "now": 599_999})["due"] is False
    assert e({"op": "due", "now": 600_000})["due"] is True
    assert e({"op": "saved", "now": 600_000})["due"] is False
    assert e({"op": "due", "now": 1_300_000})["due"] is False  # nothing new since


def test_a_big_change_is_saved_after_a_minute(e):
    s = e({"op": "init", "ppk": PPK, "now": 0}, {"op": "cf", "cnt": 0, "now": 0},
          {"op": "cf", "cnt": 600, "now": 59_000})
    assert s["mwh"] >= 100_000 and s["due"] is False
    assert e({"op": "due", "now": 60_000})["due"] is True


def test_no_scale_means_no_energy(e):
    s = e({"op": "init", "stored_mwh": 7, "ppk": 0}, {"op": "cf", "cnt": 0, "now": 0}, {"op": "cf", "cnt": 1, "now": 1000})
    assert s["mwh"] == 7
