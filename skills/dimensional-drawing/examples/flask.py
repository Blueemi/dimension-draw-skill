"""Example: a revolved product (an insulated bottle) on one sheet: elevation, top
view, hatched section, angle and radius callouts, and an iso view from a revolved profile.

Run:  python3 examples/flask.py   ->  examples/out/flask.png
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from dimdraw import Sheet, polygon_path  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---- the product (r = radius, z = height from the base), mm --------------------------
BODY_R, BODY_Z = 36.50, 190.00          # straight wall ends at the shoulder line
NECK_R, NECK_Z0, NECK_Z1 = 24.00, 208.00, 214.00
CAP_R, CAP_Z1 = 26.00, 244.00
BASE_FILLET, SHOULDER_FILLET, NECK_FILLET, CAP_FILLET = 5.0, 12.0, 4.0, 3.0
WALL = 3.50                             # outer + vacuum gap + inner wall
CAP_WALL = 1.80
GRIP_Z = (222.0, 236.0)                 # knurled band on the cap


def outline(r_body, r_neck, z0, wall=0.0):
    """Closed elevation outline of the body (no cap), optionally inset by `wall`."""
    pts = [(-r_body + wall, z0 + wall), (r_body - wall, z0 + wall), (r_body - wall, BODY_Z - wall * 0.4),
           (r_neck - wall, NECK_Z0 - wall * 0.6), (r_neck - wall, NECK_Z1),
           (-r_neck + wall, NECK_Z1), (-r_neck + wall, NECK_Z0 - wall * 0.6),
           (-r_body + wall, BODY_Z - wall * 0.4)]
    f = [BASE_FILLET - wall * 0.6, BASE_FILLET - wall * 0.6, SHOULDER_FILLET - wall, NECK_FILLET - wall * 0.5,
         0, 0, NECK_FILLET - wall * 0.5, SHOULDER_FILLET - wall]
    return pts, [max(v, 0.5) for v in f]


def cap_outline(inset=0.0):
    pts = [(-CAP_R + inset, NECK_Z1), (CAP_R - inset, NECK_Z1), (CAP_R - inset, CAP_Z1 - inset),
           (-CAP_R + inset, CAP_Z1 - inset)]
    return pts, [0, 0, max(CAP_FILLET - inset, 0.5), max(CAP_FILLET - inset, 0.5)]


def revolve_profile():
    """(radius, height) polyline from the base center to the cap top center."""
    half = [(0, 0), (BODY_R, 0), (BODY_R, BODY_Z), (NECK_R, NECK_Z0), (NECK_R, NECK_Z1),
            (CAP_R, NECK_Z1), (CAP_R, CAP_Z1), (0, CAP_Z1)]
    p = polygon_path(half, fillet=[0, BASE_FILLET, SHOULDER_FILLET, NECK_FILLET, 0, 0, CAP_FILLET, 0],
                     closed=False)
    pts = p.polylines()[0]
    out = []
    for q in pts:
        if not out or abs(q[0] - out[-1][0]) + abs(q[1] - out[-1][1]) > 1e-6:
            out.append((max(q[0], 0.0), q[1]))
    return out


def main():
    sh = Sheet("D", product="Flask 500", page=1, company="Acme Inc.", date="2026-10-23")
    sh.notes([
        "ALL DIMENSIONS NOMINAL, MEASURED AT 23°C.",
        "DO NOT APPLY ADHESIVE TO THE CAP OR THREAD AREA.",
        "SLEEVES AND HOLDERS MUST CLEAR THE CAP GRIP BAND.",
        "BASE MUST STAY FLAT; ACCESSORIES ADD 3.0 mm MAX BELOW THE BASE.",
    ])
    sh.title_block(title="FLASK 500\nACCESSORY DESIGN GUIDE", drawing_number="ACME-DG-0102",
                   rev="B", sheet=(1, 1),
                   tolerances=[("0 < - < 10", "±0.10"), ("10 < - < 100", "±0.20"),
                               ("100 < - < 300", "±0.40"), ("ANGLES", "±1.0°")])
    s = 1.15
    base_y = 486                      # sheet y of the base line in the elevation views

    # ---- elevation ----------------------------------------------------------------------
    e = sh.view(x=290, y=base_y, scale=s, name="front")
    pts, fil = outline(BODY_R, NECK_R, 0.0)
    body = e.polygon(pts, fillet=fil)
    cpts, cfil = cap_outline()
    cap = e.polygon(cpts, fillet=cfil)
    for z in GRIP_Z:
        e.line((-CAP_R, z), (CAP_R, z), style="thin")
    for i in range(1, 12):
        x = -CAP_R + i * 2 * CAP_R / 12
        e.line((x, GRIP_Z[0]), (x, GRIP_Z[1]), style="thin")
    e.line((-BODY_R, BODY_Z), (BODY_R, BODY_Z), style="thin")   # tangent edge at the shoulder
    e.centerline((0, -4), (0, CAP_Z1 + 4))
    e.dim_v((CAP_R, CAP_Z1), (BODY_R, 0), offset=40, ref=body, label="PRODUCT\nHEIGHT")
    e.dim_v((CAP_R, CAP_Z1), (CAP_R, NECK_Z1), offset=14, ref=body, label="CAP")
    e.dim_v((BODY_R, BODY_Z), (BODY_R, 0), offset=14, ref=body, label="STRAIGHT\nWALL")
    e.dim_v((-CAP_R, GRIP_Z[1]), (-CAP_R, GRIP_Z[0]), offset=-10, ref=body, place="outside",
            side="start", label="GRIP BAND")
    e.dim_h((-BODY_R, 0), (BODY_R, 0), offset=-14, prefix="Ø", label="PRODUCT\nDIAMETER")
    e.dim_h((-CAP_R, CAP_Z1), (CAP_R, CAP_Z1), offset=12, prefix="Ø", label="CAP")
    e.radius((BODY_R - BASE_FILLET, BASE_FILLET), BASE_FILLET, angle=-45, length=14, prefix="2X")
    e.callout((-BODY_R + 0.3, 120), "BODY SURFACE", dx=-22, dy=10, arrow="dot", flags=[3])

    # ---- top view (above the elevation, third angle) ------------------------------------
    t = sh.view(x=290, y=122, scale=0.8, name="top")
    tb = t.circle(0, 0, r=BODY_R)
    tc = t.circle(0, 0, r=CAP_R)
    t.circle(0, 0, r=NECK_R, style="hidden")
    t.center_mark(tb, extend=4)
    t.diameter(tc, angle=40, length=14, label="CAP")
    t.diameter(tb, angle=-30, length=12, label="BODY")
    t.section_line((-BODY_R - 6, 0), (BODY_R + 6, 0), "A", look=(0, 1), arm=6)

    # ---- section A-A -----------------------------------------------------------------------
    a = sh.view(x=530, y=base_y, scale=s, name="sectionA")
    opts, ofil = outline(BODY_R, NECK_R, 0.0)
    ipts, ifil = outline(BODY_R, NECK_R, 0.0, wall=WALL)
    outer = a.polygon(opts, fillet=ofil)
    inner = a.polygon(ipts, fillet=ifil, style="visible")
    a.hatch(outer, holes=inner, angle=45, spacing=1.2)
    c_o, c_of = cap_outline()
    c_i = [(-CAP_R + CAP_WALL, NECK_Z1), (CAP_R - CAP_WALL, NECK_Z1),
           (CAP_R - CAP_WALL, CAP_Z1 - CAP_WALL), (-CAP_R + CAP_WALL, CAP_Z1 - CAP_WALL)]
    cap_o = a.polygon(c_o, fillet=c_of)
    cap_i = a.polygon(c_i, fillet=[0, 0, 1.2, 1.2])
    a.hatch(cap_o, holes=cap_i, angle=-45, spacing=1.0)
    a.centerline((0, -4), (0, CAP_Z1 + 4))
    a.dim_h((BODY_R - WALL, 100), (BODY_R, 100), offset=0, place="outside", side="end",
            label="WALL")
    a.dim_h((-NECK_R, NECK_Z1), (NECK_R, NECK_Z1), offset=26, ref=cap_o, prefix="Ø",
            label="NECK")
    a.dim_h((-NECK_R + WALL, NECK_Z1 - 3), (NECK_R - WALL, NECK_Z1 - 3), offset=-30,
            prefix="Ø", label="MOUTH", ref=[(0, NECK_Z0 - 2)])
    a.dim_v((CAP_R, CAP_Z1), (CAP_R - CAP_WALL, CAP_Z1 - CAP_WALL), offset=10, ref=cap_o,
            place="outside", side="end", label="CAP WALL")
    a.callout((BODY_R - WALL / 2, 150), "VACUUM INSULATED\nDOUBLE WALL", dx=22, dy=12,
              arrow="dot")
    a.angle((BODY_R, BODY_Z), (BODY_R, BODY_Z + 30), (NECK_R, NECK_Z0), r=26,
            label="SHOULDER", ext="vertex")
    sh.label(530, 527, "SECTION", "A - A")

    # ---- iso -------------------------------------------------------------------------------
    iv = sh.iso(745, 290, 1.0, yaw=20, pitch=22, name="iso")
    iv.revolve(revolve_profile(), axis="y", center=(0, -CAP_Z1 / 2, 0))
    iv.callout((-BODY_R * 0.7, 30 - CAP_Z1 / 2, BODY_R * 0.7), "BODY SURFACE", dx=-26, dy=-18,
               arrow="dot", flags=[3])
    iv.callout((0, GRIP_Z[0] + 6 - CAP_Z1 / 2, CAP_R), "GRIP BAND", dx=30, dy=22, arrow="dot",
               flags=[2])

    os.makedirs(OUT, exist_ok=True)
    sh.save(os.path.join(OUT, "flask.svg"), pdf=True)


if __name__ == "__main__":
    main()
