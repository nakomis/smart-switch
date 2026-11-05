"""Mains design rules from a working-voltage matrix.

Every mains net belongs to one potential group, and every other net is SELV. Each scenario (the
relay closed or open, either fuse blown) gives every group a potential, as a fraction of the supply
between live (0) and neutral (1). The working voltage between two groups is their largest
difference over the scenarios, times the rated voltage. That gives the creepage required between them (IEC
60664-1 Table F.4), and the generated .kicad_dru makes KiCad's DRC enforce it. The build fails on
any violation.

Insulation between groups:
- mains <-> mains: functional. Creepage from Table F.4 for the working voltage; clearance is the
  same figure (more than the 1.5 mm that a 2.5 kV impulse needs, Table F.2).
- mains <-> SELV, including the GND pour: reinforced. 8 mm clearance and 8 mm creepage (Martin's
  rule, above IEC's 5.0 mm reinforced creepage at 250 V and 3.0 mm clearance at 4 kV). The one
  exception is between the pads of a certified barrier part (the isolator, the relay, the PSU),
  whose own pin spacing is set by its certification: there, clearance must still be at least
  REINFORCED_CLEARANCE (3.0 mm). Creepage stays at 8 mm, which a slot under the part provides.
- mains <-> board edge, and holes not on a mains net: 3 mm, so a screw or the case wall is never
  close to mains copper.
  Pads of a barrier part may come within BARRIER_EDGE of a slot under that part.
- High-current nets (Mains16A): tracks at least HIGH_CURRENT_WIDTH wide.

Non-isolated mode (rest=<group>): there is no SELV. Every net not named in a group sits at that
group's potential (on Petro revision B the low-voltage circuitry is tied to neutral), so its spacing
to each mains group is the matrix's functional creepage, not the reinforced 8 mm. The mounting
holes take screws that could be reachable, so all copper, low-voltage too, keeps MAINS_EDGE from an
unplated hole. Low-voltage copper may come near the board edge (the case is plastic); mains-group
copper keeps MAINS_EDGE from it as before.

A SELV island in non-isolated mode (nets in the group SELV): copper that may be touched (rev B's
safe I/O on J3), powered and signalled across reinforced isolators. It keeps REINFORCED (8 mm)
clearance and creepage from every other net, mains and the neutral-referenced rest alike. The
isolators are barrier parts: between their own SELV and other pads, clearance REINFORCED_CLEARANCE,
and creepage (checked by barrier_creepage, not KiCad) 8 mm, which a slot under each provides.

IEC 60664-1 basis: rated voltage 250 V (the rationalised voltage for a 230 V supply), overvoltage
category II, pollution degree 2, material group III (any FR-4: CTI 175-400 is IIIa). Linear
interpolation between table rows is permitted by the standard; results round up to 0.05 mm.
"""
import math
from dataclasses import dataclass, field

V_RATED = 250.0                  # V rms
REINFORCED = 8.0                 # mm, mains <-> SELV clearance and creepage
REINFORCED_CLEARANCE = 3.0       # mm, IEC 60664-1 Table F.2: 4 kV impulse, reinforced, PD2
MAINS_EDGE = 3.0                 # mm, mains copper to the board edge and to holes
BARRIER_EDGE = 1.0               # mm, a barrier part's pads to the edge of a slot under it
HIGH_CURRENT = "Mains16A"
HIGH_CURRENT_WIDTH = 4.5         # mm: IPC-2221, 16 A, 20 C rise, 2 oz external copper

# IEC 60664-1 Table F.4, creepage (mm) for pollution degree 2, material group III, by working
# voltage (V rms).
CREEPAGE_PD2_MG3 = ((10, 0.40), (12.5, 0.42), (16, 0.45), (20, 0.48), (25, 0.50), (32, 0.53),
                    (40, 1.10), (50, 1.20), (63, 1.25), (80, 1.30), (100, 1.40), (125, 1.50),
                    (160, 1.60), (200, 2.00), (250, 2.50), (320, 3.20), (400, 4.00))

# The groups:
#   LINE     live from the terminal to F1
#   LIVE     after F1: the shunt, the relay's common, and the metering island tied to it
#   PSU      after F2 (T500 mA): the two Mean Well modules' AC inputs
#   NEUTRAL
#   LOAD     the relay's switched output to the load terminal
#   DIV1-4   the voltage divider: neutral -> R -> DIV1 -> R -> ... -> DIV4 -> R -> the BL0939's VP
#            input, which sits at the island's ground (LIVE)
# Each scenario gives every group its potential as a fraction of the supply, from line live (0) to
# neutral (1). A blown fuse lets everything after it be pulled to neutral (through the load or a
# PSU's input), so a fuse's two sides see the full supply.
GROUPS = ("LINE", "LIVE", "PSU", "NEUTRAL", "LOAD", "DIV1", "DIV2", "DIV3", "DIV4", "SWNODE")
SELV = "SELV"           # non-isolated mode only: an island that keeps REINFORCED from everything


def _scenario(live, psu, load, divider_top="LIVE"):
    # SWNODE: a non-isolated buck's switching node (and what rides on it), at the bus's potential
    p = {"LINE": 0.0, "LIVE": live, "PSU": psu, "NEUTRAL": 1.0, "LOAD": load, "SWNODE": psu}
    top = p[divider_top]
    for k in range(1, 5):                     # DIVk is k fifths of the way from neutral to the top
        p[f"DIV{k}"] = 1.0 + (top - 1.0) * k / 5
    return p


def scenarios(divider_top="LIVE"):
    """Every scenario's potentials. divider_top: the group the voltage divider hangs from (LIVE,
    after F1, on rev A; LINE, before it, on rev B)."""
    return {
        "relay closed": _scenario(0.0, 0.0, 0.0, divider_top),
        "relay open": _scenario(0.0, 0.0, 1.0, divider_top),
        "F1 blown": _scenario(1.0, 1.0, 1.0, divider_top),
        "F2 blown, relay closed": _scenario(0.0, 1.0, 0.0, divider_top),
        "F2 blown, relay open": _scenario(0.0, 1.0, 1.0, divider_top),
    }


SCENARIOS = scenarios()


def creepage(volts):
    """Creepage (mm) for a working voltage, interpolated in Table F.4 and rounded up to 0.05 mm.
    Below the table's first row, its first value."""
    if volts > CREEPAGE_PD2_MG3[-1][0]:
        raise ValueError(f"{volts} V is beyond the table")
    rows = CREEPAGE_PD2_MG3
    if volts <= rows[0][0]:
        mm = rows[0][1]
    else:
        (v0, c0), (v1, c1) = next((a, b) for a, b in zip(rows, rows[1:]) if a[0] < volts <= b[0])
        mm = c0 + (c1 - c0) * (volts - v0) / (v1 - v0)
    return round(math.ceil(round(mm / 0.05, 6)) * 0.05, 2)


def ipc2221_width(amps, oz, rise=20.0):
    """Track width (mm) for 'amps' on an external layer of 'oz' copper at a 'rise' C temperature
    rise: IPC-2221's I = 0.048 dT^0.44 A^0.725, A in mil^2 (1 oz = 1.378 mil thick)."""
    area = (amps / (0.048 * rise ** 0.44)) ** (1 / 0.725)
    return area / (1.378 * oz) * 0.0254


def working_voltage(g1, g2, divider_top="LIVE"):
    """Worst-case working voltage (V rms) between two mains groups, over every scenario."""
    return round(V_RATED * max(abs(p[g1] - p[g2]) for p in scenarios(divider_top).values()), 6)


@dataclass
class Rules:
    """groups: mains net -> its group in GROUPS (every net not named is SELV).
    high_current: nets that carry the load current (tracks at least HIGH_CURRENT_WIDTH).
    barriers: refs of certified parts whose own pads cross the mains/SELV barrier."""
    groups: dict
    high_current: set = field(default_factory=set)
    barriers: tuple = ()
    rest: str | None = None          # non-isolated: the group every unnamed net belongs to
    divider_top: str = "LIVE"        # the group the voltage divider hangs from
    # group -> mm: functional insulation inside a converter, where a short only trips its current
    # limit (IEC 62368-1 allows less than the table when a short causes no hazard): this spacing
    # to every other group replaces the table's
    reduced: dict = field(default_factory=dict)
    # ref -> (mm, (net, net)): a part rated for the voltage across its own leads at its maker's
    # pitch (C1/C2, 400 V electrolytics at 3.5 mm). Its own pads keep mm clearance from each
    # other; creepage for its net pair drops to mm too, because KiCad's creepage check sees only
    # nets. Everywhere else the pair keeps the full clearance, and with no slots in the board a
    # surface path is never shorter than the straight gap, so that still holds the creepage.
    own_leads: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.rest is not None and self.rest not in GROUPS:
            raise ValueError(f"unknown rest group: {self.rest}")
        bad = {n: g for n, g in self.groups.items() if g not in GROUPS and not (g == SELV and self.rest)}
        if bad:
            raise ValueError(f"unknown groups: {bad}")
        stray = set(self.high_current) - set(self.groups)
        if stray:
            raise ValueError(f"high-current nets that are not mains nets: {sorted(stray)}")

    def used(self):
        """The mains groups in use (the SELV island is not one)."""
        return sorted(set(self.groups.values()) - {SELV}, key=GROUPS.index)

    def has_selv(self):
        return SELV in self.groups.values()

    def is_selv(self, net):
        """Whether 'net' may be touched: in isolated mode every net not in a group; in
        non-isolated mode, the SELV island's nets."""
        return self.groups.get(net) == SELV if self.rest else net not in self.groups

    def spacing(self, a, b):
        """Required clearance and creepage (mm) between groups a and b: the table's for their
        working voltage, or a reduced group's own figure. The SELV island: REINFORCED to anything
        else."""
        if (a == SELV) != (b == SELV):
            return REINFORCED
        if a == b == SELV:
            return 0.0
        if a == b:
            v = working_voltage(a, b, self.divider_top)
            return creepage(v) if v else 0.0
        if a in self.reduced or b in self.reduced:
            return max(self.reduced.get(a, 0.0), self.reduced.get(b, 0.0))
        v = working_voltage(a, b, self.divider_top)
        return creepage(v) if v else 0.0

    def matrix(self):
        """{(g1, g2): (working voltage, mm)} for every pair of groups in use, both ways round,
        including a group with itself (different nets within one group)."""
        out = {}
        for a in self.used():
            for b in self.used():
                out[(a, b)] = (working_voltage(a, b, self.divider_top), self.spacing(a, b))
        return out

    def netclasses(self, base):
        """(classes, patterns) for the .kicad_pro: 'base' (the non-mains classes and patterns,
        as in kicad_pcb.PRO) plus one class per group and the high-current class. A
        high-current net is in both its group's class and Mains16A."""
        classes, patterns = base
        tmpl = {"clearance": 0.15, "track_width": 0.15, "via_diameter": 0.6, "via_drill": 0.3}
        classes = list(classes) + [{"name": g, **tmpl, "track_width": 1.0} for g in self.used()]
        if self.has_selv():
            classes.append({"name": SELV, **tmpl, "track_width": 0.2})
        classes.append({"name": HIGH_CURRENT, **tmpl, "track_width": HIGH_CURRENT_WIDTH})
        patterns = list(patterns) + [{"netclass": g, "pattern": n} for n, g in sorted(self.groups.items())]
        patterns += [{"netclass": HIGH_CURRENT, "pattern": n} for n in sorted(self.high_current)]
        return classes, patterns

    def dru(self):
        """The .kicad_dru text. Later rules take precedence in KiCad, so the barrier exceptions
        come last."""
        groups = self.used()
        mains = lambda side: " || ".join(f"{side}.hasNetclass('{g}')" for g in groups)
        selv = lambda side: f"!({mains(side)})"
        out = ["(version 1)"]

        def rule(name, constraints, cond):
            out.append(f'(rule "{name}"')
            out.extend(f"  (constraint {c})" for c in constraints)
            out.append(f'  (condition "{cond}"))')

        for g in groups:
            if self.rest is None:
                rule(f"{g} to SELV", [f"clearance (min {REINFORCED}mm)", f"creepage (min {REINFORCED}mm)"],
                     f"A.hasNetclass('{g}') && {selv('B')}")
                continue
            v, mm = working_voltage(g, self.rest, self.divider_top), self.spacing(g, self.rest)
            if mm:
                label = f"{mm:g} mm" if g in self.reduced else f"{v:g} V"
                rule(f"{g} to the rest ({label})", [f"clearance (min {mm:g}mm)", f"creepage (min {mm:g}mm)"],
                     f"A.hasNetclass('{g}') && {selv('B')}")
        for (a, b), (v, mm) in self.matrix().items():
            if a > b or not mm:
                continue                          # each pair once; nothing between equal potentials
            same = "A.Net != B.Net && " if a == b else ""
            label = f"{mm:g} mm" if a in self.reduced or b in self.reduced else f"{v:g} V"
            rule(f"{a} to {b} ({label})", [f"clearance (min {mm:g}mm)", f"creepage (min {mm:g}mm)"],
                 f"{same}A.hasNetclass('{a}') && B.hasNetclass('{b}')")
        rule("mains to edge", [f"edge_clearance (min {MAINS_EDGE}mm)"], mains("A"))
        # Holes not on a mains net (mounting holes, SELV vias and pins); mains-to-mains spacing is
        # the pair rules' business, copper to copper.
        if self.rest is None:
            rule("mains to holes", [f"hole_clearance (min {MAINS_EDGE}mm)"], f"({mains('A')}) && {selv('B')}")
        else:       # vias are the pair rules' business; the screws are the mounting holes'
            rule("copper to mounting holes", [f"hole_clearance (min {MAINS_EDGE}mm)"],
                 "B.Pad_Type == 'NPTH, mechanical'")
        if self.high_current:
            rule("high-current track width", [f"track_width (min {HIGH_CURRENT_WIDTH}mm)"],
                 f"A.hasNetclass('{HIGH_CURRENT}')")
        if self.rest is not None and self.has_selv():
            rule(f"SELV island to everything else ({REINFORCED:g} mm)",
                 [f"clearance (min {REINFORCED:g}mm)", f"creepage (min {REINFORCED:g}mm)"],
                 f"A.hasNetclass('{SELV}') && !B.hasNetclass('{SELV}')")
        for ref, (mm, (n1, n2)) in self.own_leads.items():
            rule(f"{ref} own leads ({mm:g} mm)", [f"clearance (min {mm:g}mm)"],
                 f"A.memberOfFootprint('{ref}') && B.memberOfFootprint('{ref}')")
            rule(f"{ref} own leads, creepage ({mm:g} mm)", [f"creepage (min {mm:g}mm)"],
                 f"(A.NetName == '{n1}' && B.NetName == '{n2}') || (A.NetName == '{n2}' && B.NetName == '{n1}')")
        for ref in self.barriers:
            inside = f"A.memberOfFootprint('{ref}') && B.memberOfFootprint('{ref}')"
            if self.rest is None:
                rule(f"{ref} own pads, mains to SELV", [f"clearance (min {REINFORCED_CLEARANCE}mm)"],
                     f"{inside} && ({mains('A')}) && {selv('B')}")
                rule(f"{ref} pads to its slot", [f"edge_clearance (min {BARRIER_EDGE}mm)"],
                     f"A.memberOfFootprint('{ref}') && ({mains('A')})")
            else:
                rule(f"{ref} own pads, SELV to the rest", [f"clearance (min {REINFORCED_CLEARANCE:g}mm)"],
                     f"{inside} && A.hasNetclass('{SELV}') && !B.hasNetclass('{SELV}')")
                rule(f"{ref} pads to its slot", [f"edge_clearance (min {BARRIER_EDGE:g}mm)"],
                     f"A.memberOfFootprint('{ref}')")
        return "\n".join(out) + "\n"


# --- creepage within a barrier part -------------------------------------------------------
# KiCad 10's DRC checks creepage only between different objects, never between two pads of one
# footprint (found 4 Nov 2026: two pads of one part 4.8 mm apart under an 8 mm creepage rule were
# not reported). The barrier parts' mains-to-SELV creepage is checked here instead.
#
# The estimate is never longer than the true surface path, so it can only fail a good board,
# never pass a bad one: pads are taken as their bounding rectangles, and a path blocked by a slot
# runs straight to the nearer end of the slot (beyond its round end) and on, which is no longer
# than the real path around it.

def _pad_box(placement, ref, pad):
    from board.placement import rotate
    x, y, rot = placement.at[ref]
    px, py = rotate(pad.x, pad.y, rot)
    w, h = (pad.h, pad.w) if round((rot + pad.rot) / 90) % 2 else (pad.w, pad.h)
    return (x + px - w / 2, y + py - h / 2, x + px + w / 2, y + py + h / 2)


def _box_to_point(b, p):
    dx = max(b[0] - p[0], 0.0, p[0] - b[2])
    dy = max(b[1] - p[1], 0.0, p[1] - b[3])
    return math.hypot(dx, dy)


def _box_to_box(a, b):
    dx = max(a[0] - b[2], 0.0, b[0] - a[2])
    dy = max(a[1] - b[3], 0.0, b[1] - a[3])
    return math.hypot(dx, dy)


def _centre(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _crosses(p, q, s):
    """Whether segment p-q crosses slot s's centre line (the slot extended by its radius at each
    end), i.e. the straight path is blocked by it."""
    r = s.width / 2
    if s.y1 == s.y2:
        a, b = (min(s.x1, s.x2) - r, s.y1), (max(s.x1, s.x2) + r, s.y1)
    else:
        a, b = (s.x1, min(s.y1, s.y2) - r), (s.x1, max(s.y1, s.y2) + r)
    cross = lambda o, u, v: (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])
    return cross(p, q, a) * cross(p, q, b) < 0 and cross(a, b, p) * cross(a, b, q) < 0


def _tips(s):
    r = s.width / 2
    if s.y1 == s.y2:
        return [(min(s.x1, s.x2) - r, s.y1), (max(s.x1, s.x2) + r, s.y1)]
    return [(s.x1, min(s.y1, s.y2) - r), (s.x1, max(s.y1, s.y2) + r)]


def creepage_between(a, b, slots):
    """A lower bound on the surface path (mm) between pad boxes a and b, around 'slots'."""
    straight = _box_to_box(a, b)
    blocking = [s for s in slots if _crosses(_centre(a), _centre(b), s)]
    if not blocking:
        return straight
    return max(min(_box_to_point(a, t) + _box_to_point(b, t) for t in _tips(s)) for s in blocking)


def barrier_creepage(circuit, placement, rules, slots=()):
    """Every mains-to-SELV pad pair within each barrier part whose creepage is under REINFORCED:
    [(ref, mains pad, other pad, mm)]. A pad with no net counts as SELV (it could be touched).
    In non-isolated mode the pairs are the SELV island's pads against every other pad."""
    bad = []
    for ref in rules.barriers:
        inst = circuit.instances[ref]
        pads = [p for p in inst.part.footprint.pads if p.layers and any("Cu" in l for l in p.layers)]
        net = lambda p: circuit.net_of(ref, p.number)
        selv = lambda p: net(p) is None or rules.is_selv(net(p))
        hot = [p for p in pads if not selv(p)]
        cold = [p for p in pads if selv(p)]
        for h in hot:
            for c in cold:
                mm = creepage_between(_pad_box(placement, ref, h), _pad_box(placement, ref, c), slots)
                if mm < REINFORCED - 1e-9:
                    bad.append((ref, h.number, c.number, round(mm, 2)))
    return bad
