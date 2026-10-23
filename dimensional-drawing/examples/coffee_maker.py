"""Example: a drip coffee maker modelled once in 3-D; every view on both sheets
(front, right, top, section, iso) is generated from that model with hidden-line
removal, and dimensions are taken from 3-D model points.

Run:  python3 examples/coffee_maker.py   ->  examples/out/coffee-1.png, -2.png, coffee.pdf
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from dimdraw import Sheet, Model, rect_path, circle_path, slot_path, spline, save_pdf  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---- product dimensions (mm). Axes: X width, Y up, Z toward the user. ----------------
W = 210.0                      # body width
BASE_Z = (-125.0, 115.0)       # base depth range (rear, front)
BASE_H = 42.0
TOWER_Z = (-125.0, -40.0)      # water-tank tower depth range
TOWER_TOP = 330.0
HEAD_Z = (-60.0, 100.0)        # filter head depth range
HEAD_Y = (270.0, 318.0)
HEAD_W = 190.0
CX, CZ = 0.0, 36.0             # carafe / filter axis (clear of the tower front at Z=-40)
PLATE_Y = (BASE_H, BASE_H + 3.0)
CARAFE_Y0 = PLATE_Y[1]
# carafe outer profile (radius, height) through smooth control points
CARAFE = spline([(66.0, 0.0), (71.5, 38.0), (70.0, 78.0), (54.0, 118.0), (46.5, 136.0),
                 (53.0, 150.0)], per_segment=10)
CARAFE_BULGE = max(CARAFE, key=lambda p: p[0])   # widest point (radius, height)
GLASS = 3.0
FILTER = [(28.0, 214.0), (52.0, 262.0), (56.0, 266.0), (56.0, 270.0)]
BUTTON = (62.0, 21.0, 8.0)     # x, y, radius on the base front
FEET = [(sx * 80.0, sz) for sx in (-1, 1) for sz in (-100.0, 90.0)]


def carafe_r(y):
    """Outer carafe radius at height y above its base (from the profile)."""
    for (r0, y0), (r1, y1) in zip(CARAFE, CARAFE[1:]):
        if y0 <= y <= y1:
            return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
    return CARAFE[-1][0]


def build():
    m = Model("coffee maker")
    # base: plan profile in the Z-X plane, extruded up Y
    m.extrude(rect_path(BASE_Z[0], -W / 2, BASE_Z[1], W / 2, 24), 0.0, BASE_H, plane="zx",
              fillet=(3, 6), name="base")
    m.extrude(rect_path(TOWER_Z[0], -W / 2, TOWER_Z[1], W / 2, 18), BASE_H, TOWER_TOP,
              plane="zx", fillet=(0, 8), name="tower")
    m.extrude(rect_path(HEAD_Z[0], -HEAD_W / 2, HEAD_Z[1], HEAD_W / 2, 26), HEAD_Y[0], HEAD_Y[1],
              plane="zx", fillet=(5, 5), name="head")
    # water-level window on the tower's right side (profile in Y-Z, pushed out along X)
    m.extrude(slot_path(205.0, -82.0, 170.0, 14.0, angle=0), W / 2 - 0.5, W / 2 + 0.8,
              plane="yz", name="window")
    # warming plate, carafe (hollow glass shell), lid and handle
    m.cylinder((CX, PLATE_Y[0], CZ), 74.0, PLATE_Y[1] - PLATE_Y[0], axis="y", name="plate")
    outer = [(0.0, 0.0)] + CARAFE
    inner = [(r - GLASS, y) for r, y in reversed(CARAFE[1:])] + [(CARAFE[0][0] - GLASS, GLASS),
                                                                   (0.0, GLASS)]
    prof = [(r, CARAFE_Y0 + y) for r, y in outer + inner]
    m.revolve(prof, axis="y", center=(CX, 0, CZ), name="carafe")
    lid_y = CARAFE_Y0 + CARAFE[-1][1]
    m.revolve([(0, lid_y - 4), (46, lid_y - 4), (46, lid_y + 4), (38, lid_y + 12), (0, lid_y + 15)],
              axis="y", center=(CX, 0, CZ), name="lid")
    # handle: smooth C through control points; both ends sink 3 mm into the glass
    top_y, bot_y = 114.0, 30.0
    ctrl = [(carafe_r(top_y) - 3, top_y), (carafe_r(top_y) + 22, top_y + 8), (104, 100),
            (112, 70), (104, 42), (carafe_r(bot_y) + 14, bot_y - 2), (carafe_r(bot_y) - 3, bot_y)]
    path = [(CX + x, CARAFE_Y0 + y, CZ) for x, y in spline(ctrl, per_segment=8)]
    m.sweep(circle_path(0, 0, 8.0), path, n=28, name="handle")
    # brew basket under the head
    wall = 2.5
    basket = FILTER + [(r - wall, y) for r, y in reversed(FILTER[1:])] + \
        [(FILTER[0][0] - wall, FILTER[0][1] + wall), (0.0, FILTER[0][1] + wall)]
    m.revolve([(0, FILTER[0][1])] + basket, axis="y", center=(CX, 0, CZ), name="filter")
    # controls and feet
    bx, by, br = BUTTON
    m.cylinder((bx, by, BASE_Z[1] - 1.0), br, 3.0, axis="z", fillet=(0, 0.8), name="button")
    m.cylinder((bx - 22, by, BASE_Z[1] - 0.5), 2.2, 1.5, axis="z", name="led")
    for fx, fz in FEET:
        m.cylinder((fx, -4.0, fz), 10.0, 4.0, axis="y", fillet=(1.0, 0), name="foot")
    # intended joints (the checker lists any other part that passes through another)
    for a, b in (("tower", "head"), ("tower", "window"), ("carafe", "handle"), ("base", "button"),
                 ("base", "led")):
        m.joint(a, b)
    return m


def sheet_one(m):
    sh = Sheet("D", product="Brewer 10", page=1, company="Acme Inc.", date="2026-10-23")
    sh.notes([
        "ACCESSORIES MUST NOT CONTACT THE WARMING PLATE OR CARAFE GLASS.",
        "DO NOT OBSTRUCT THE STEAM VENT ON THE TOP OF THE WATER TANK.",
        "KEEP 100 mm CLEAR ABOVE THE PRODUCT FOR LID ACCESS.",
        "WATER LEVEL WINDOW MUST REMAIN VISIBLE.",
        "DIMENSIONS ARE NOMINAL; MODEL FOR ILLUSTRATION.",
    ])
    sh.title_block(title="BREWER 10\nACCESSORY DESIGN GUIDE", drawing_number="ACME-DG-0210",
                   rev="A", sheet=(1, 2))
    s = 0.8
    f = sh.model_view(m, "front", 268, 462, s, name="front")
    r = f.projected("right", at=530)
    fb, rb = f.bbox(), r.bbox()
    f.dim_h((-W / 2, 0.0, 0.0), (W / 2, 0.0, 0.0), offset=-12, ref=fb, label="BASE\nWIDTH")
    f.dim_h(m.extreme("-x"), m.extreme("+x"), offset=-28, ref=fb, label="OVERALL WIDTH")
    f.dim_v((W / 2, -4.0, -100.0), (W / 2, TOWER_TOP, -100.0), offset=-30, ref=fb,
            label="PRODUCT\nHEIGHT", side="start")
    f.dim_v((W / 2, 0.0, 0.0), (W / 2, BASE_H, 0.0), offset=12, ref=fb, place="outside",
            side="end", label="BASE")
    br, by_ = CARAFE_BULGE
    bulge = CARAFE_Y0 + by_
    f.dim_h((CX - br, bulge, CZ), (CX + br, bulge, CZ), offset=0,
            prefix="\u00d8", label="CARAFE", place="inside")
    f.callout((BUTTON[0], BUTTON[1], BASE_Z[1] + 2.0), "POWER BUTTON", dx=50, dy=-26, flags=[1])
    f.callout((-60.0, HEAD_Y[0] + 24, HEAD_Z[1]), "FILTER HEAD", dx=-44, dy=30)
    # right view: depth, overhang and the brewing clearance
    r.dim_h((W / 2, 0.0, BASE_Z[1]), (W / 2, 0.0, BASE_Z[0]), offset=-12, ref=rb,
            label="BASE\nDEPTH")
    r.dim_h((W / 2, HEAD_Y[1], TOWER_Z[1]), (W / 2, HEAD_Y[1], HEAD_Z[1]), offset=14, ref=rb,
            label="HEAD\nOVERHANG")
    r.dim_v((CX, PLATE_Y[1], CZ + 56), (CX, FILTER[0][1], CZ + 56), offset=-34, ref=rb,
            label="CARAFE\nCLEARANCE")
    r.callout((W / 2 + 0.8, 150.0, -82.0), "WATER LEVEL WINDOW", dx=34, dy=-46, flags=[4])
    # hero
    iv = sh.iso(752, 268, 0.5, yaw=-38, pitch=24, model=m, name="hero")
    iv.callout((40.0, BASE_H, 100.0), "ENTIRE PRODUCT SURFACE", arrow="dot", flags=[1],
               at=(705, 412))
    return sh


def sheet_two(m):
    sh = Sheet("D", product="Brewer 10", page=2, company="Acme Inc.", date="2026-10-23")
    sh.title_block(title="BREWER 10\nACCESSORY DESIGN GUIDE", drawing_number="ACME-DG-0210",
                   rev="A", sheet=(2, 2))
    s = 1.0
    sec = sh.model_view(m, "front", 235, 440, s, name="sectionA", section=CZ)
    sb = sec.bbox()
    br, by_ = CARAFE_BULGE
    bulge = CARAFE_Y0 + by_
    sec.dim_h((CX - br + GLASS, bulge, CZ), (CX + br - GLASS, bulge, CZ),
              offset=0, prefix="\u00d8", label="CARAFE\nINSIDE", place="inside")
    gy = 90.0
    sec.dim_h((CX - carafe_r(gy), CARAFE_Y0 + gy, CZ),
              (CX - carafe_r(gy) + GLASS, CARAFE_Y0 + gy, CZ), offset=0, place="outside",
              side="start", label="GLASS")
    sec.dim_v((-W / 2, PLATE_Y[1], CZ), (-W / 2, FILTER[0][1], CZ), offset=-14, ref=sb,
              label="CARAFE\nCLEARANCE")
    sec.dim_v((-W / 2, FILTER[0][1], CZ), (-W / 2, FILTER[-1][1], CZ), offset=-14, ref=sb,
              label="FILTER\nDEPTH")
    # cone angle measured outside the basket: wall vs. vertical at the rim
    rim = (CX + FILTER[1][0], FILTER[1][1], CZ)
    sec.angle(rim, (CX + FILTER[0][0], FILTER[0][1], CZ), (rim[0], rim[1] - 40, CZ), r=30,
              label="FILTER\nCONE")
    sh.label(235, 500, "SECTION", "A - A", sub="THROUGH CARAFE AXIS")
    # plan with the cutting plane
    top = sh.model_view(m, "top", 520, 250, 0.6, name="top")
    tb = top.bbox()
    top.section_line((-W / 2 - 14, TOWER_TOP, CZ), (W / 2 + 14, TOWER_TOP, CZ), "A",
                     look=(0, 1), arm=6)
    top.dim_v((W / 2, TOWER_TOP, TOWER_Z[0]), (W / 2, TOWER_TOP, TOWER_Z[1]), offset=10, ref=tb,
              label="TANK")
    top.callout((0.0, TOWER_TOP, -82.0), "STEAM VENT AREA", dx=-70, dy=-58, flags=[2],
                arrow="dot")
    sh.caption("TOP VIEW", 520, 345)
    # rear view with hidden lines
    sh.model_view(m, "back", 735, 330, 0.5, name="rear", hidden=True)
    sh.caption("REAR VIEW (HIDDEN LINES SHOWN)", 735, 370)
    sh.notes([(1, "ACCESSORIES MUST NOT CONTACT THE WARMING PLATE OR CARAFE GLASS."),
              (2, "DO NOT OBSTRUCT THE STEAM VENT ON THE TOP OF THE WATER TANK.")],
             subtitle="(SEE SHEET 1 FOR ALL NOTES)")
    return sh


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    model = build()
    print(model.stats())
    s1 = sheet_one(model)
    s1.save(os.path.join(OUT, "coffee-1.svg"))
    s2 = sheet_two(model)
    s2.save(os.path.join(OUT, "coffee-2.svg"))
    save_pdf([s1, s2], os.path.join(OUT, "coffee.pdf"))
