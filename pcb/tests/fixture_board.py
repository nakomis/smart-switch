"""A small, fixed board for testing the generic pipeline (writer, DSN, DRC, fab) without depending
on Petro's own board: USB in, a polyfuse, a 3.3 V LDO with its capacitors, an LED with a series
resistor, two plated mounting holes and one unplated one. 40 x 30 mm."""
from board.netlist import Circuit
from board.placement import Placement

W, H = 40.0, 30.0


def build_mini():
    c = Circuit()
    j1 = c.add("JST5", "J1")
    f1 = c.add("PTC", "F1")
    u1 = c.add("LDO", "U1")
    cin, cout = c.add("C10U", "C1"), c.add("C10U", "C2")
    cd = c.add("C100N", "C3")
    d1 = c.add("LED", "D1")
    r1 = c.add("R330", "R1")
    h1, h2, h3 = c.add("MH", "H1"), c.add("MH", "H2"), c.add("MHN", "H3")
    c.connect("VBUS", (j1, "1"), (f1, "1"))
    c.connect("+5V", (f1, "2"), (u1, "VIN"), (u1, "EN"), (cin, "1"))
    c.connect("+3V3", (u1, "VOUT"), (cout, "1"), (cd, "1"), (d1, "VDD"))
    c.connect("LED_DI", (r1, "2"), (d1, "DI"))
    c.connect("DATA", (r1, "1"), (j1, "2"))
    c.connect("GND", (j1, "5"), (u1, "GND"), (cin, "2"), (cout, "2"), (cd, "2"), (d1, "GND"),
              (h1, "1"), (h2, "1"))
    for pin in ("3", "4", "6", "7"):
        c.no_connect(j1, pin)
    c.no_connect(u1, "NC")
    c.no_connect(d1, "DO")
    return c


def place_mini(c):
    at = {"J1": (6.0, 15.0, 270.0), "F1": (13.0, 9.0, 0.0), "U1": (20.0, 15.0, 0.0),
          "C1": (15.0, 15.0, 90.0), "C2": (25.0, 15.0, 90.0), "C3": (28.0, 15.0, 90.0),
          "D1": (32.0, 22.0, 0.0), "R1": (25.0, 22.0, 0.0),
          "H1": (4.0, 4.0, 0.0), "H2": (36.0, 4.0, 0.0), "H3": (36.0, 26.0, 0.0)}
    p = Placement((0.0, 0.0, W, H), at)
    p.courtyards = {r: i.part.body for r, i in c.instances.items()}
    return p
