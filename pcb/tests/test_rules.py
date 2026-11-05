"""The mains rules: the working-voltage matrix, the IEC 60664-1 table, the generated DRU, and DRC
controls that prove each rule fails a board that breaks it (and passes one that doesn't)."""
import json
import subprocess

import pytest
from conftest import KICAD_CLI

from board.kicad_pcb import PRO, Slot, Track, Via, write_board
from board.netlist import Circuit
from board.placement import Placement
from board.rules import (BARRIER_EDGE, GROUPS, HIGH_CURRENT_WIDTH, MAINS_EDGE, REINFORCED,
                         REINFORCED_CLEARANCE, SCENARIOS, Rules, creepage, working_voltage)
from board.sexpr import Sym

BASE = ([c for c in PRO["net_settings"]["classes"] if c["name"] != "Mains"],
        [p for p in PRO["net_settings"]["netclass_patterns"] if p["netclass"] != "Mains"])


# --- the matrix and the table ---------------------------------------------------------------

def test_matrix_is_symmetric_and_zero_on_the_diagonal():
    for a in GROUPS:
        assert working_voltage(a, a) == 0
        for b in GROUPS:
            assert working_voltage(a, b) == working_voltage(b, a)


@pytest.mark.parametrize("a, b, volts", [
    ("LINE", "NEUTRAL", 250), ("LIVE", "NEUTRAL", 250), ("LOAD", "LIVE", 250), ("LOAD", "NEUTRAL", 250),
    ("LINE", "LIVE", 250),       # across F1 when it has blown
    ("LIVE", "PSU", 250),        # across F2 when it has blown
    ("DIV1", "NEUTRAL", 50), ("DIV1", "DIV2", 50), ("DIV4", "LIVE", 50),   # one divider step each
    ("DIV1", "LIVE", 200), ("DIV2", "LOAD", 150), ("LINE", "DIV4", 250),
])
def test_working_voltages(a, b, volts):
    assert working_voltage(a, b) == volts


def test_every_scenario_names_every_group():
    for name, p in SCENARIOS.items():
        assert set(p) == set(GROUPS), name
        assert all(0.0 <= v <= 1.0 for v in p.values()), name


@pytest.mark.parametrize("volts, mm", [(250, 2.5), (200, 2.0), (50, 1.2), (100, 1.4), (5, 0.4),
                                       (150, 1.6),      # 1.571 between the 125 and 160 V rows, rounded up
                                       (400, 4.0)])
def test_creepage_table_iec_60664_1_pd2_mg3(volts, mm):
    assert creepage(volts) == pytest.approx(mm)


def test_creepage_beyond_the_table_is_refused():
    with pytest.raises(ValueError):
        creepage(631)


def test_unknown_group_and_stray_high_current_net_are_refused():
    with pytest.raises(ValueError):
        Rules({"L": "HOT"})
    with pytest.raises(ValueError):
        Rules({"L": "LIVE"}, high_current={"GND"})


# --- the generated DRU and net classes ------------------------------------------------------

def _rules():
    return Rules({"L_IN": "LINE", "L_F": "LIVE", "GND_M": "LIVE", "N": "NEUTRAL", "L_OUT": "LOAD",
                  "DIV1": "DIV1", "DIV2": "DIV2"},
                 high_current={"L_IN", "L_F", "N", "L_OUT"}, barriers=("U9",))


def test_dru_has_a_rule_for_every_pair_and_every_group_to_selv():
    dru = _rules().dru()
    used = ["LINE", "LIVE", "NEUTRAL", "LOAD", "DIV1", "DIV2"]
    for g in used:
        assert f'(rule "{g} to SELV"' in dru
    for i, a in enumerate(used):
        for b in used[i:]:
            if a == b:
                continue
            (x, y) = (a, b) if a < b else (b, a)
            assert f'(rule "{x} to {y} (' in dru, (x, y)
    assert f"creepage (min {REINFORCED}mm)" in dru and f"track_width (min {HIGH_CURRENT_WIDTH}mm)" in dru
    assert dru.index('"U9 own pads') > dru.index('"LINE to SELV"')      # exceptions come last


def test_netclasses_put_high_current_nets_in_two_classes():
    classes, patterns = _rules().netclasses(BASE)
    names = [c["name"] for c in classes]
    assert names == ["Default", "Power", "LINE", "LIVE", "NEUTRAL", "LOAD", "DIV1", "DIV2", "Mains16A"]
    assert {"netclass": "LINE", "pattern": "L_IN"} in patterns
    assert {"netclass": "Mains16A", "pattern": "L_IN"} in patterns
    assert {"netclass": "Mains16A", "pattern": "GND_M"} not in patterns


# --- DRC controls ---------------------------------------------------------------------------
# A probe board: one via per copper object under test, and a resistor per net far off to the side
# so that each net exists. Vias are 0.6 mm, so the copper gap between two is (distance - 0.6).

def _probe(tmp_path, vias, tracks=(), slots=(), rules=None, parts=None):
    rules = rules or _rules()
    nets = sorted({v.net for v in vias} | {t.net for t in tracks})
    c = Circuit()
    at = {}
    for k, net in enumerate(nets):
        r = c.add("R330")
        c.connect(net, (r, "1"), (r, "2"))
        at[r.ref] = (95.0, 5.0 + 12.0 * k, 0.0)              # 12 mm apart, 95 mm from the probes
    for ref, (key, x, y, pads) in (parts or {}).items():
        inst = c.add(key, ref)
        for pad, net in pads.items():
            c.connect(net, (inst, pad))
        at[ref] = (x, y, 0.0)
    height = max(60.0, 12.0 * len(nets) + 10)
    pcb = tmp_path / "probe.kicad_pcb"
    classes, patterns = rules.netclasses(BASE)
    write_board(c, Placement((0.0, 0.0, 110.0, height), at), pcb, tracks, vias, layers=2, slots=slots,
                dru=rules.dru(), netclasses=classes, netclass_patterns=patterns)
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", str(tmp_path / "drc.json"), str(pcb)], check=True, capture_output=True)
    drc = json.loads((tmp_path / "drc.json").read_text())
    bad = [v for v in drc["violations"] if v["severity"] == "error" and v["type"] != "track_dangling"]
    return {(v["type"], v["description"].split("'")[1] if "'" in v["description"] else "") for v in bad}


def _pair(tmp_path, net_a, net_b, gap, **kw):
    """Two vias with a copper gap of 'gap' mm between them, mid-board."""
    return _probe(tmp_path, [Via(net_a, 30.0, 30.0), Via(net_b, 30.0 + 0.6 + gap, 30.0)], **kw)


def test_dru_parses_without_rule_errors(tmp_path):
    bad = _pair(tmp_path, "L_IN", "N", 10.0)
    assert not any(t in ("invalid_drc_rule", "drc_rule_error") for t, _ in bad), bad
    assert bad == set()


@pytest.mark.parametrize("selv", ["GND", "+3V3", "IO5"])
def test_mains_to_selv_below_8mm_fails(tmp_path, selv):
    assert ("clearance", "LIVE to SELV") in _pair(tmp_path, "L_F", selv, REINFORCED - 0.1)


def test_mains_to_selv_at_8mm_passes(tmp_path):
    assert _pair(tmp_path, "L_F", "GND", REINFORCED + 0.05) == set()


def test_live_to_neutral_needs_2_5mm(tmp_path):
    assert ("clearance", "LIVE to NEUTRAL (250 V)") in _pair(tmp_path, "L_F", "N", 2.4)
    (tmp_path / "ok").mkdir()
    assert _pair(tmp_path / "ok", "L_F", "N", 2.55) == set()


def test_across_the_fuse_needs_2_5mm(tmp_path):
    assert ("clearance", "LINE to LIVE (250 V)") in _pair(tmp_path, "L_IN", "L_F", 2.4)


def test_one_divider_step_needs_only_1_2mm(tmp_path):
    assert _pair(tmp_path, "DIV1", "DIV2", 1.25) == set()
    (tmp_path / "bad").mkdir()
    assert ("clearance", "DIV1 to DIV2 (50 V)") in _pair(tmp_path / "bad", "DIV1", "DIV2", 1.1)


def test_same_group_different_nets_have_no_mains_rule(tmp_path):
    """The island's ground and the shunt's live side are within millivolts: default rules only."""
    assert _pair(tmp_path, "L_F", "GND_M", 0.5) == set()


def test_mains_near_the_board_edge_fails(tmp_path):
    bad = _probe(tmp_path, [Via("L_F", MAINS_EDGE - 0.1 + 0.3, 30.0)])
    assert ("copper_edge_clearance", "mains to edge") in bad
    (tmp_path / "ok").mkdir()
    assert _probe(tmp_path / "ok", [Via("L_F", MAINS_EDGE + 0.1 + 0.3, 30.0)]) == set()


def test_thin_high_current_track_fails(tmp_path):
    t = [Track("L_F", "F.Cu", 20.0, 30.0, 40.0, 30.0, HIGH_CURRENT_WIDTH - 0.1)]
    # KiCad words this one as a board-setup constraint rather than naming the rule
    assert "track_width" in {kind for kind, _ in _probe(tmp_path, [], tracks=t)}
    (tmp_path / "ok").mkdir()
    t = [Track("L_F", "F.Cu", 20.0, 30.0, 40.0, 30.0, HIGH_CURRENT_WIDTH)]
    assert _probe(tmp_path / "ok", [], tracks=t) == set()


def test_island_track_may_be_thin(tmp_path):
    t = [Track("GND_M", "F.Cu", 20.0, 30.0, 40.0, 30.0, 0.2)]
    assert _probe(tmp_path, [], tracks=t) == set()


def test_a_slot_does_not_rescue_too_little_clearance(tmp_path):
    """Creepage around a slot can be longer, but clearance through the air is still the gap."""
    bad = _pair(tmp_path, "L_F", "GND", 7.0, slots=[Slot(34.1, 10.0, 34.1, 50.0, 1.0)])
    assert ("clearance", "LIVE to SELV") in bad


def test_an_unconnected_barrier_pad_counts_as_selv(tmp_path):
    """Pin 2, with no net, is 1.3 mm from the live pin 1: a floating pad could be touched."""
    io = {"U9": ("IO", 30.0, 30.0, {"1": "L_F", "3": "GND", "4": "GND", "5": "GND", "6": "GND",
                                    "7": "GND", "8": "GND"})}
    assert ("clearance", "U9 own pads, mains to SELV") in _probe(tmp_path, [], parts=io)


def _barrier(pads):
    from board.parts import part  # noqa: F401  (loads the footprints)
    c = Circuit()
    u = c.add("IO", "U9")
    for pad, net in pads.items():
        c.connect(net, (u, pad))
    return c, Placement((0.0, 0.0, 60.0, 40.0), {"U9": (30.0, 20.0, 0.0)})


IO_PADS = {"1": "L_F", "3": "GND", "4": "GND", "5": "GND", "6": "GND", "7": "GND", "8": "GND"}


def test_kicad_does_not_check_creepage_within_one_footprint(tmp_path):
    """The reason barrier_creepage() exists. If a KiCad release starts reporting this, the
    test fails and the in-house check can be reviewed (but kept: it costs nothing)."""
    from board import rules as R
    lax = Rules({"L_F": "LIVE"}, barriers=("U9",))
    old = R.REINFORCED_CLEARANCE
    R.REINFORCED_CLEARANCE = 1.0                         # let the 1.3 mm pin 1-2 gap pass clearance
    try:
        bad = _probe(tmp_path, [], rules=lax, parts={"U9": ("IO", 30.0, 30.0, IO_PADS)})
    finally:
        R.REINFORCED_CLEARANCE = old
    assert not [b for b in bad if b[0] == "creepage"], bad


def test_barrier_creepage_finds_short_paths_within_the_part():
    from board.rules import barrier_creepage
    c, p = _barrier(IO_PADS)
    bad = barrier_creepage(c, p, Rules({"L_F": "LIVE"}, barriers=("U9",)))
    assert ("U9", "1", "2", 1.3) in bad                  # the unconnected pin counts as SELV
    assert ("U9", "1", "3", 4.8) in bad
    assert not [b for b in bad if b[2] in ("5", "6", "7", "8")]     # 10.5 mm and more: fine


def test_a_slot_between_the_pins_lengthens_the_creepage():
    from board.rules import barrier_creepage
    c, p = _barrier(IO_PADS)
    # pin 1 is at x = 17.75 and pin 2 at 21.25: a 1 mm slot at x = 19.5, 20 mm long
    assert barrier_creepage(c, p, Rules({"L_F": "LIVE"}, barriers=("U9",)),
                            slots=[Slot(19.5, 10.0, 19.5, 30.0, 1.0)]) == []


def test_a_short_slot_is_not_enough():
    from board.rules import barrier_creepage
    c, p = _barrier(IO_PADS)
    bad = barrier_creepage(c, p, Rules({"L_F": "LIVE"}, barriers=("U9",)),
                           slots=[Slot(19.5, 19.0, 19.5, 21.0, 1.0)])
    assert bad and all(mm < REINFORCED for *_, mm in bad)


def test_creepage_estimate_never_exceeds_the_straight_line_around_the_slot_end():
    """The bound: a path via the slot's tip, which is no longer than the true path round it."""
    from board.rules import creepage_between
    a, b = (0.0, -1.0, 2.0, 1.0), (8.0, -1.0, 10.0, 1.0)
    assert creepage_between(a, b, []) == 6.0
    s = Slot(5.0, -3.0, 5.0, 3.0, 1.0)                   # tips at y = -3.5 and 3.5
    got = creepage_between(a, b, [s])
    assert got == pytest.approx(2 * (3.0 ** 2 + 2.5 ** 2) ** 0.5)
    assert got > 6.0


def test_barrier_pads_below_3mm_still_fail(tmp_path):
    io = {"U9": ("IO", 30.0, 30.0, {"1": "L_F", "2": "GND", "3": "GND", "4": "GND",
                                    "5": "GND", "6": "GND", "7": "GND", "8": "GND"})}
    assert ("clearance", "U9 own pads, mains to SELV") in _probe(tmp_path, [], parts=io)


def test_the_exception_is_only_for_the_named_barrier(tmp_path):
    io = {"J9": ("IO", 30.0, 30.0, {"1": "L_F", "2": "L_F", "3": "L_F", "4": "GND",
                                    "5": "GND", "6": "GND", "7": "GND", "8": "GND"})}
    assert ("clearance", "LIVE to SELV") in _probe(tmp_path, [], parts=io)
