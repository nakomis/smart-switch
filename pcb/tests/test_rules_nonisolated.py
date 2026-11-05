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


def test_a_part_rated_across_its_own_leads_keeps_its_own_pitch(tmp_path):
    """C1/C2, 400 V electrolytics at the maker's 3.5 mm pitch (1.6 mm pads: 1.9 mm between them),
    sit across VBULK and GND: the PSU-to-rest 2.5 mm fails between their own pads unless the part
    is named in own_leads.

    KiCad's creepage check sees only nets (memberOfFootprint never matches there), so the
    exception is clearance between the footprint's own pads plus creepage for its net pair.
    Elsewhere the pair keeps the full clearance, and on a board without slots creepage can't be
    shorter than clearance, so a VBULK via 1.5 mm from a GND via still fails."""
    cap = {"C1": ("C4U7HV", 60.0, 30.0, {"+": "VBULK", "-": "GND"})}
    bad = _probe(tmp_path, [], rules=Rules(GROUPS_B, rest="NEUTRAL"), parts=cap)
    assert ("creepage", "PSU to the rest (250 V)") in bad
    (tmp_path / "ok").mkdir()
    ok = Rules(GROUPS_B, rest="NEUTRAL", own_leads={"C1": (1.0, ("VBULK", "GND"))})
    assert _probe(tmp_path / "ok", [], rules=ok, parts=cap) == set()
    assert 'rule "C1 own leads (1 mm)"' in ok.dru()
    (tmp_path / "elsewhere").mkdir()
    near = [Via("VBULK", 30.0, 30.0), Via("GND", 30.0 + 0.6 + 1.5, 30.0)]
    assert ("clearance", "PSU to the rest (250 V)") in _probe(tmp_path / "elsewhere", near, rules=ok,
                                                               parts=cap)


def test_any_copper_near_a_mounting_hole_fails(tmp_path):
    """An unplated M3 hole (MHN, 3.2 mm) at (60, 30): a GND via 2 mm from its edge fails, 3.1 mm
    passes."""
    hole = {"H1": ("MHN", 60.0, 30.0, {})}
    bad = _probe(tmp_path, [Via("GND", 60.0 + 1.6 + 2.0 + 0.3, 30.0)], rules=_rules(), parts=hole)
    assert ("hole_clearance", "copper to mounting holes") in bad
    (tmp_path / "ok").mkdir()
    assert _probe(tmp_path / "ok", [Via("GND", 60.0 + 1.6 + MAINS_EDGE + 0.1 + 0.3, 30.0)],
                  rules=_rules(), parts=hole) == set()


# --- a SELV island in a non-isolated board (rev B's safe I/O on J3) ---------------------------------
GROUPS_S = {**GROUPS_B, "ISO_3V3": "SELV", "ISO_SDA": "SELV"}


def _rules_s(**kw):
    return Rules(GROUPS_S, rest="NEUTRAL", **kw)


def test_the_selv_island_keeps_8_mm_from_everything_else():
    r = _rules_s()
    for g in ("NEUTRAL", "LIVE", "LINE", "PSU", "DIV4"):
        assert r.spacing("SELV", g) == REINFORCED and r.spacing(g, "SELV") == REINFORCED, g
    assert r.spacing("SELV", "SELV") == 0.0
    assert "SELV" not in r.used()                      # not a mains group: no edge rule, no matrix row
    assert all("SELV" not in pair for pair in r.matrix())


def test_selv_copper_near_the_low_voltage_side_fails_below_8_mm(tmp_path):
    near = [Via("ISO_3V3", 30.0, 30.0), Via("GND", 30.0 + 0.6 + 5.0, 30.0)]
    assert ("clearance", "SELV island to everything else (8 mm)") in _probe(tmp_path, near, rules=_rules_s())
    (tmp_path / "far").mkdir()
    far = [Via("ISO_3V3", 30.0, 30.0), Via("GND", 30.0 + 0.6 + REINFORCED + 0.1, 30.0)]
    assert _probe(tmp_path / "far", far, rules=_rules_s()) == set()


def test_selv_copper_near_live_fails_below_8_mm(tmp_path):
    near = [Via("ISO_SDA", 30.0, 30.0), Via("L_F", 30.0 + 0.6 + 5.0, 30.0)]
    assert ("clearance", "SELV island to everything else (8 mm)") in _probe(tmp_path, near, rules=_rules_s())


def test_selv_may_come_near_the_board_edge():
    edge = _rules_s().dru().split('rule "mains to edge"')[1].split("(rule")[0]
    assert "SELV" not in edge


def test_a_barrier_part_in_rest_mode_keeps_3_mm_between_its_own_sides():
    d = _rules_s(barriers=("U9",)).dru()
    own = d.split('rule "U9 own pads, SELV to the rest"')[1].split("(rule")[0]
    assert "clearance (min 3mm)" in own
    assert "A.memberOfFootprint('U9') && B.memberOfFootprint('U9')" in own
    assert "A.hasNetclass('SELV') && !B.hasNetclass('SELV')" in own
    assert d.index("SELV island to everything else") < d.index("U9 own pads")      # later wins


def test_barrier_creepage_in_rest_mode_pairs_selv_pads_with_the_rest():
    """An isolator across the island's barrier with no slot under it: each SELV pad against each
    other pad, all under 8 mm."""
    from board.netlist import Circuit
    from board.placement import Placement
    from board.rules import barrier_creepage
    c = Circuit()
    inst = c.add("ISO7741", "U9")
    side2 = {"GND2": "ISO_GND", "EN2": "ISO_EN", "IND": "ISO_D", "OUTC": "ISO_C", "OUTB": "ISO_B",
             "OUTA": "ISO_A", "VCC2": "ISO_3V3"}
    for pin, n in {"VCC1": "+3V3", "GND1": "GND", "INA": "S_A", "INB": "S_B", "INC": "S_C", "OUTD": "S_D",
                   "EN1": "EN1", **side2}.items():
        c.connect(n, (inst, pin))
    groups = {**GROUPS_B, **{n: "SELV" for n in side2.values()}}
    p = Placement((0.0, 0.0, 40.0, 40.0), {"U9": (20.0, 20.0, 0.0)})
    bad = barrier_creepage(c, p, Rules(groups, rest="NEUTRAL", barriers=("U9",)))
    selv_pads = {"9", "10", "11", "12", "13", "14", "15", "16"}          # side 2 of the DW body
    assert bad and all(mm < REINFORCED for *_, mm in bad)
    assert all(h not in selv_pads and o in selv_pads for _, h, o, _ in bad)
