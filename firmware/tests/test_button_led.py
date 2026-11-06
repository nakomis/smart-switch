"""port/button (SW1's debounce) and port/led (what the status LED shows)."""

import pytest


@pytest.fixture
def button(json_tool):
    run = json_tool("petro-button")

    def go(*readings):
        return [r["press"] for r in run(*(f'{{"now":{t},"pressed":{str(p).lower()}}}' for t, p in readings))]

    return go


def test_a_clean_press_counts_once_after_30_ms(button):
    assert button((0, False), (5, True), (30, True), (35, True), (40, True), (200, True), (205, False),
                  (300, False)) == [False, False, False, True, False, False, False, False]


def test_bounce_shorter_than_30_ms_is_ignored(button):
    seq = [(0, False)] + [(5 * i, i % 2 == 1) for i in range(1, 8)] + [(40, False), (100, False)]
    assert not any(button(*seq))


def test_a_release_is_no_press_and_a_second_press_counts(button):
    out = button((0, False), (5, True), (40, True), (45, False), (80, False), (85, True), (120, True))
    assert out.count(True) == 2


def test_held_through_boot_is_no_press(button):
    assert not any(button((0, True), (100, True), (200, True), (300, False), (400, False)))


@pytest.fixture
def led(json_tool):
    run = json_tool("petro-led")
    return lambda **state: run(__import__("json").dumps(state))[0]


@pytest.mark.parametrize("mode,relay,colour", [
    ("off", False, "amber"), ("on", True, "green"), ("auto", True, "blue"), ("auto", False, "dim blue"),
])
def test_the_mode_colours_when_connected(led, mode, relay, colour):
    assert led(now=5000, mode=mode, relay=relay)["colour"] == colour


def test_boot_is_white_for_the_first_1_5_s(led):
    assert led(now=0, mode="on")["colour"] == "white"
    assert led(now=1499, mode="on")["colour"] == "white"
    assert led(now=1500, mode="on")["colour"] == "green"


def test_fault_beats_everything_and_blinks_at_4_hz(led):
    assert [led(now=t, tripped=True, ota=True, provisioned=False)["colour"] for t in (0, 125, 250, 375)] == [
        "red", "dark", "red", "dark"]


def test_ota_blinks_cyan_at_2_hz(led):
    assert [led(now=t, ota=True)["colour"] for t in (2000, 2250, 2500)] == ["cyan", "dark", "cyan"]


def test_unprovisioned_alternates_magenta_with_the_mode(led):
    assert [led(now=t, provisioned=False, mode="off")["colour"] for t in (2000, 2500)] == ["magenta", "amber"]


def test_joining_wifi_blinks_the_mode_at_1_hz(led):
    assert [led(now=t, wifi=False, mqtt=False, mode="on", relay=True)["colour"] for t in (2000, 2499, 2500)] == [
        "green", "green", "dark"]


def test_connecting_to_iot_core_blinks_the_mode_at_4_hz(led):
    assert [led(now=t, mqtt=False, mode="on", relay=True)["colour"] for t in (2000, 2125)] == ["green", "dark"]


def test_a_negative_clock_is_taken_as_boot(led):
    assert led(now=-5)["colour"] == "white"


def test_the_level_scales_rgb(led):
    assert led(now=5000, mode="on", relay=True, level=64) == {"colour": "green", "r": 0, "g": 64, "b": 0}


def test_every_colour_has_a_name_and_rgb(tool):
    lines = tool("petro-led", "all")().splitlines()
    assert lines[0] == "dark 0 0 0"
    assert "red 255 0 0" in lines
    assert lines[-1] == "? 255 0 0"  # out of range: red
