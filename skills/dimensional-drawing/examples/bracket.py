"""Example: a sheet-metal mounting bracket on an A3 sheet. Shows the style
outside consumer electronics: hidden lines, hole patterns with counts,
countersink and slot callouts, bend radius, chain/baseline dims and an iso view.

Run:  python3 examples/bracket.py   ->  examples/out/bracket.png
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from dimdraw import Sheet, polygon_path, rect_path, circle_path, slot_path  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---- the part, mm -------------------------------------------------------------------
L = 80.00            # length along the bend
D = 40.00            # base depth (front to back)
HGT = 50.00          # upright height (outside)
T = 3.00             # sheet thickness
BEND_R = 3.00        # inside bend radius
CORNER_R = 4.00      # plate corner radius
BASE_HOLES = [(-28.0, 14.0), (28.0, 14.0), (-28.0, 30.0), (28.0, 30.0)]   # (x, y from bend face)
HOLE_D, CSK_D = 5.50, 10.00
SLOTS = [(-24.0, 32.0), (24.0, 32.0)]   # (x, height) centers on the upright
SLOT_L, SLOT_W = 12.00, 6.00
CENTER_D = 20.00
CENTER_Z = 24.00


def main():
    sh = Sheet("A3", product="Bracket MB-80", page=1, company="Acme Inc.", date="2026-10-23")
    k = sh.k
    sh.notes([
        "MATERIAL: AL 5052-H32, 3.0 mm.",
        "BREAK ALL SHARP EDGES 0.2 mm MAX.",
        "FINISH: CLEAR ANODIZE, NO FINISH IN COUNTERSINKS.",
        "BEND RADIUS IS INSIDE RADIUS.",
    ])
    sh.title_block(title="MOUNTING BRACKET\nMB-80", drawing_number="ACME-MB-0080", rev="C",
                   sheet=(1, 1), scale="1.6:1",
                   tolerances=[("0 < - < 10", "±0.10"), ("10 < - < 100", "±0.20"),
                               ("ANGLES", "±0.5°")])
    s = 1.6

    # Third-angle arrangement: front view (looking at the upright), top view above it,
    # right view to its right. All share one scale and their aligned axes.
    FX, FY = 122, 262        # sheet position of the front view's (x=0, z=0)

    # ---- top view: base plate from above; y = -depth (bend at the top, front edge down) ---
    tv = sh.view(x=FX, y=97, scale=s, name="top", center=(0, 0))
    base = tv.box(-L / 2, -D, L / 2, 0, r=(0, 0, CORNER_R, CORNER_R))
    tv.line((-L / 2, -T), (L / 2, -T), style="thin")                      # upright inner face
    tv.line((-L / 2, -T - BEND_R), (L / 2, -T - BEND_R), style="phantom")  # bend tangent line
    holes = []
    for (x, y) in BASE_HOLES:
        holes.append(tv.circle(x, -y, d=HOLE_D))
        tv.circle(x, -y, d=CSK_D, style="thin")
        tv.center_mark(holes[-1], extend=2)
    tv.dim_h(base.tl, base.tr, offset=18, ref=base)
    tv.dim_chain([(-L / 2, -D), holes[2].center, holes[3].center], axis="h", offset=8, ref=base)
    tv.dim_v(base.tr, base.br, offset=22, ref=base)
    tv.dim_baseline((L / 2, 0), [holes[1].center, holes[3].center], axis="v", offset=8, step=7,
                    ref=base)
    tv.diameter(holes[2], angle=200, length=14, prefix="4X", flags=[3],
                label="\u2335 \u00d810.00 X 90\u00b0")
    tv.radius((-L / 2 + CORNER_R, -D + CORNER_R), CORNER_R, angle=225, length=8, prefix="2X")

    # ---- front view: the upright seen from the front --------------------------------------
    fv = sh.view(x=FX, y=FY, scale=s, name="front")
    up = fv.box(-L / 2, 0, L / 2, HGT, r=(CORNER_R, CORNER_R, 0, 0))
    fv.line((-L / 2, T), (L / 2, T), style="thin")                        # base top face
    slots = [fv.slot(x, z, SLOT_L, SLOT_W, angle=0) for (x, z) in SLOTS]
    hole = fv.circle(0, CENTER_Z, d=CENTER_D)
    fv.center_mark(hole, extend=3)
    for sl in slots:
        fv.center_mark(sl.center, r=SLOT_L / 2, extend=1.5)
    fv.dim_v(up.tl, up.bl, offset=-14, ref=up)
    fv.dim_v((up.left, 0), slots[0].center, offset=-5, ref=up)
    fv.dim_h(slots[0].center, slots[1].center, offset=6, ref=up)
    fv.dim_v((0, 0), hole.center, offset=6, ref=up, ext=(False, True), place="outside")
    fv.diameter(hole, angle=-45, length=7)
    fv.callout(slots[1].right_mid, f"2X {SLOT_W:.2f} X {SLOT_L:.2f} SLOT", dx=24, dy=10,
               flags=[2], h=sh.st("dim_text"))

    # ---- right view: the L profile; x = -depth (front of the part toward the front view) --
    rv = sh.view(x=FX + 190, y=FY, scale=s, name="right")
    prof = [(-D, 0), (0, 0), (0, HGT), (-T, HGT), (-T, T), (-D, T)]
    rv.polygon(prof, fillet=[0, BEND_R + T, 0, 0, BEND_R, 0])
    for (x, y) in BASE_HOLES[:2]:       # countersunk holes in the base, hidden in this view
        for dx in (-HOLE_D / 2, HOLE_D / 2):
            rv.line((-y + dx, 0), (-y + dx, T), style="hidden")
    for dz in (-CENTER_D / 2, CENTER_D / 2):
        rv.line((-T, CENTER_Z + dz), (0, CENTER_Z + dz), style="hidden")
    rv.dim_v((-D, 0), (-D, T), offset=-6, place="outside", side="start")
    rv.dim_h((-D, 0), (0, 0), offset=-10)
    rv.radius((-T - BEND_R, T + BEND_R), BEND_R, angle=-45, length=10, label="INSIDE")
    rv.angle((-T, T), (-D, T), (-T, HGT), r=16, ext="vertex")

    # ---- iso ---------------------------------------------------------------------------
    iv = sh.iso(352, 120, 0.85, yaw=-40, pitch=28, name="iso")
    # base plate: thickness along Y, profile in (z, x) = (depth toward viewer, length)
    base_prof = rect_path(T, -L / 2, D, L / 2, r=(CORNER_R, 0, 0, CORNER_R))
    b = iv.extrude(base_prof, 0, T, plane="zx")
    upr = rect_path(-L / 2, T, L / 2, HGT, r=(CORNER_R, CORNER_R, 0, 0))
    u = iv.extrude(upr, 0, T, plane="xy")
    iv.extrude(rect_path(0, -L / 2, T, L / 2), 0, T, plane="zx")      # bend corner block
    for (x, y) in BASE_HOLES:
        b.mark(circle_path(y, x, CSK_D / 2), face="top")
        b.mark(circle_path(y, x, HOLE_D / 2), face="top")
    for (x, z) in SLOTS:
        u.mark(slot_path(x, z, SLOT_L, SLOT_W, angle=0), face="top")
    u.mark(circle_path(0, CENTER_Z, CENTER_D / 2), face="top")

    os.makedirs(OUT, exist_ok=True)
    sh.save(os.path.join(OUT, "bracket.svg"), pdf=True)
    return k


if __name__ == "__main__":
    main()
