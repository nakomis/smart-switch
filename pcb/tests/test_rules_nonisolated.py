"""The rules in non-isolated mode (Petro revision B): every net not named in a mains group sits at
the potential of one group ('rest', neutral here, since GND is tied to neutral), so its spacing to
each mains group comes from the working-voltage matrix, not the 8 mm SELV barrier. The mounting
holes take screws that may be reachable, so all copper keeps MAINS_EDGE from an unplated hole."""
import pytest
from test_rules import BASE, _probe  # noqa: F401  (BASE used by _probe)

from board.kicad_pcb import Via
from board.rules import MAINS_EDGE, REINFORCED, Rules

GROUPS_B = {"L_IN": "LINE", "L_F": "LIVE", "L_PSU": "PSU", "VBULK": "PSU", "N_IN": "NEUTRAL",
            "N_OUT": "NEUTRAL", "L_OUT": "LOAD", "DIV1": "DIV1", "DIV2": "DIV2", "DIV3": "DIV3",
            "DIV4": "DIV4"}


def _rules():
    return Rules(GROUPS_B, high_current={"L_IN", "L_F", "L_OUT", "N_IN", "N_OUT"}, rest="NEUTRAL")


def _pair(tmp_path, a, b, gap):
    return _probe(tmp_path, [Via(a, 30.0, 30.0), Via(b, 30.0 + 0.6 + gap, 30.0)], rules=_rules())


def test_a_divider_from_line_keeps_its_taps_when_f1_blows():
    """Rev B's divider hangs from L_IN (before F1): DIVk is k fifths of the way from neutral to
    LINE in every scenario, so with F1 blown DIV4 still sits 200 V from neutral."""
    from board.rules import working_voltage
    assert working_voltage("DIV4", "NEUTRAL", divider_top="LINE") == 200
    assert working_voltage("DIV4", "LINE", divider_top="LINE") == 50
    assert working_voltage("DIV4", "LIVE", divider_top="LINE") == 200      # F1 blown: LIVE at neutral
    r = Rules(GROUPS_B, rest="NEUTRAL", divider_top="LINE")
    assert r.matrix()[("DIV4", "LINE")][0] == 50


def test_ipc2221_width_matches_the_published_formula():
    """External layers, 20 C rise: rev A's 4.5 mm is 16 A at 2 oz; at 1 oz each of two parallel
    layers needs 3.47 mm for 8 A (the formula is sublinear, so two layers beat one wide one)."""
    from board.rules import ipc2221_width
    assert ipc2221_width(16, 2) == pytest.approx(4.52, abs=0.01)
    assert ipc2221_width(8, 1) == pytest.approx(3.47, abs=0.01)
    assert ipc2221_width(16, 1) > 2 * ipc2221_width(8, 1)


def test_the_switching_node_keeps_a_reduced_functional_spacing(tmp_path):
    """SWNODE (the LNK306's source node and the BP/FB parts riding on it): functional insulation
    inside the converter, where a short only trips its current limit. 1.0 mm to everything (IPC-2221
    B4, coated, 301-500 V: 0.8 mm), via Rules.reduced; the DC bus (PSU) keeps the table's 2.5 mm."""
    r = Rules({**GROUPS_B, "SW": "SWNODE"}, rest="NEUTRAL", reduced={"SWNODE": 1.0})
    assert r.spacing("SWNODE", "NEUTRAL") == 1.0 and r.spacing("SWNODE", "PSU") == 1.0
    assert r.spacing("PSU", "NEUTRAL") == 2.5
    rules = r
    ok = _probe(tmp_path, [Via("SW", 30.0, 30.0), Via("GND", 30.0 + 0.6 + 1.05, 30.0)], rules=rules)
    assert ok == set()
    (tmp_path / "bad").mkdir()
    bad = _probe(tmp_path / "bad", [Via("SW", 30.0, 30.0), Via("GND", 30.0 + 0.6 + 0.9, 30.0)], rules=rules)
    assert ("clearance", "SWNODE to the rest (1 mm)") in bad


def test_rest_must_be_a_group():
    with pytest.raises(ValueError):
        Rules(GROUPS_B, rest="NOPE")


def test_no_reinforced_barrier_in_non_isolated_mode():
    dru = _rules().dru()
    assert "SELV" not in dru and f"{REINFORCED}mm" not in dru


def test_low_voltage_to_live_needs_2_5mm(tmp_path):
    assert ("clearance", "LIVE to the rest (250 V)") in _pair(tmp_path, "L_F", "GND", 2.4)
    (tmp_path / "ok").mkdir()
    assert _pair(tmp_path / "ok", "L_F", "GND", 2.55) == set()


def test_low_voltage_to_the_bulk_capacitor_needs_2_5mm(tmp_path):
    assert ("clearance", "PSU to the rest (250 V)") in _pair(tmp_path, "VBULK", "+3V3", 2.4)


def test_low_voltage_next_to_the_divider_foot_needs_only_1_2mm(tmp_path):
    """DIV1 is one fifth of the way from neutral to live: 50 V from the rest."""
    assert _pair(tmp_path, "DIV1", "GND", 1.25) == set()


def test_low_voltage_beside_neutral_has_no_mains_rule(tmp_path):
    assert _pair(tmp_path, "N_IN", "GND", 0.5) == set()


def test_low_voltage_may_come_near_the_edge_but_live_may_not(tmp_path):
    assert _probe(tmp_path, [Via("GND", 1.0 + 0.3, 30.0)], rules=_rules()) == set()
    (tmp_path / "live").mkdir()
    assert ("copper_edge_clearance", "mains to edge") in _probe(
        tmp_path / "live", [Via("L_F", MAINS_EDGE - 0.1 + 0.3, 30.0)], rules=_rules())


def test_any_copper_near_a_mounting_hole_fails(tmp_path):
    """An unplated M3 hole (MHN, 3.2 mm) at (60, 30): a GND via 2 mm from its edge fails, 3.1 mm
    passes."""
    hole = {"H1": ("MHN", 60.0, 30.0, {})}
    bad = _probe(tmp_path, [Via("GND", 60.0 + 1.6 + 2.0 + 0.3, 30.0)], rules=_rules(), parts=hole)
    assert ("hole_clearance", "copper to mounting holes") in bad
    (tmp_path / "ok").mkdir()
    assert _probe(tmp_path / "ok", [Via("GND", 60.0 + 1.6 + MAINS_EDGE + 0.1 + 0.3, 30.0)],
                  rules=_rules(), parts=hole) == set()
