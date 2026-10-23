"""Example: a compact hatchback, modelled in 3-D from lofted cross-sections, revolved
tires and intersecting details, then drawn as a vehicle dimension sheet: side, front,
rear and plan views generated with hidden-line removal, plus a 3/4 hero view.

Run:  python3 examples/car.py   ->  examples/out/car.png
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from dimdraw import Sheet, Model, spline  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---- vehicle package (mm). Axes: X length (nose at -X), Y up, Z width. ---------------
L, WID, HGT = 4100.0, 1760.0, 1460.0
WB = 2560.0
FRONT_OH = 820.0
X_FA = -L / 2 + FRONT_OH          # front axle
X_RA = X_FA + WB                  # rear axle
TRACK = 1520.0
TIRE_R, RIM_R, TIRE_W = 320.0, 215.0, 205.0
CLEAR = 150.0                     # ground clearance (sill)
ARCH_R = 372.0
BELT_F, BELT_R = 880.0, 960.0     # beltline at the windshield base / rear
A_X, ROOF_X0, ROOF_X1, C_X = -820.0, -170.0, 1250.0, 1800.0   # cabin stations


def hood(x):
    """Top of the lower body (hood -> beltline -> tail)."""
    if x < A_X:
        u = (x + L / 2) / (A_X + L / 2)
        return 610 + (BELT_F - 610) * math.sin(u * math.pi / 2) ** 0.9
    if x < 1950:
        return BELT_F + (BELT_R - BELT_F) * (x - A_X) / (1950 - A_X)
    return BELT_R - 30 * (x - 1950) / 100


def bottom(x):
    b = CLEAR + 10
    if x < -1800:
        b += 230 * ((-1800 - x) / 250) ** 1.6
    if x > 1750:
        b += 260 * ((x - 1750) / 300) ** 1.6
    for xa in (X_FA, X_RA):
        d = abs(x - xa)
        if d < ARCH_R:
            b = max(b, TIRE_R + math.sqrt(ARCH_R ** 2 - d ** 2))
    return b


def width(x):
    w = WID
    if x < -1750:
        w -= 220 * ((-1750 - x) / 300) ** 2
    if x > 1800:
        w -= 160 * ((x - 1800) / 250) ** 2
    return w


def roof(x):
    """Roof line: windshield rise, near-flat roof, hatch drop."""
    if x <= ROOF_X0:
        u = (x - A_X) / (ROOF_X0 - A_X)
        return hood(A_X) + (HGT - hood(A_X)) * (1 - (1 - u) ** 1.35)
    if x <= ROOF_X1:
        return HGT - 25 * ((x - ROOF_X0) / (ROOF_X1 - ROOF_X0)) ** 2
    u = (x - ROOF_X1) / (C_X - ROOF_X1)
    top = HGT - 25
    return top - (top - hood(C_X)) * u ** 1.25


def end_round(x):
    """0 at the bumper faces, 1 inside: rounds the nose and tail in plan and elevation."""
    d = min(x + L / 2, L / 2 - x)
    u = max(0.0, min(1.0, d / 160.0))
    return math.sqrt(1 - (1 - u) ** 2)


R_TOP, R_BOT = 100.0, 45.0      # body shoulder and sill radii


def half_width(x, y):
    """Body half-width at height y: tuck-under below the waist, tumblehome above.
    Independent of the floor height, so raising the floor over the wheels just
    truncates the side and the arches come out clean."""
    w = width(x) * (0.82 + 0.18 * end_round(x)) / 2
    waist = 500.0
    if y < waist:
        return w * (1 - 0.05 * ((waist - y) / (waist - CLEAR)) ** 2)
    return w * (1 - 0.045 * ((y - waist) / 500.0) ** 1.5)


def body_ring(x):
    """Closed (z, y) outline of the lower body at station x, CCW, fixed point counts."""
    f = end_round(x)
    t0, b0 = hood(x), bottom(x)
    shrink = (1 - f) * 0.42 * (t0 - b0)      # round the ends toward mid-height (never inverts)
    t, b = t0 - shrink, b0 + shrink
    rt = min(R_TOP, (t - b) * 0.45)
    rb = min(R_BOT, (t - b) * 0.25)
    right = []
    zb = half_width(x, b + rb)
    for i in range(6):                                   # floor, centre -> corner
        right.append(((zb - rb) * i / 6, b))
    for i in range(5):                                   # sill radius
        a = math.radians(-90 + 90 * i / 4)
        right.append((zb - rb + rb * math.cos(a), b + rb + rb * math.sin(a)))
    ys0, ys1 = b + rb, t - rt
    lo = CLEAR + 10 + R_BOT                              # side rows at fixed heights, so
    for i in range(1, 15):                               # raising the floor over a wheel
        y = lo + (ys1 - lo) * i / 15                     # doesn't skew the side surface
        y = max(y, ys0)
        right.append((half_width(x, y), y))
    zt = half_width(x, ys1)
    for i in range(9):                                   # shoulder radius
        a = math.radians(90 * i / 8)
        right.append((zt - rt + rt * math.cos(a), ys1 + rt * math.sin(a)))
    for i in range(1, 8):                                # deck, corner -> centre
        right.append(((zt - rt) * (1 - i / 8), t))
    left = [(-z, y) for z, y in reversed(right[1:])]
    return right + left[:-1], (t, zt - rt)


def cabin_ring(x):
    """Greenhouse outline standing exactly on the body deck (coplanar base, sharp
    base corners so the belt line shows as a crisp crease)."""
    t, deck = body_ring(x)[1]
    yt = max(roof(x), t + 6)
    wb = 2 * deck - 30
    wt = wb - 300
    rr = min(150.0, (yt - t) * 0.45)
    right = [(wb / 2 * i / 6, t) for i in range(6)]
    for i in range(12):
        u = i / 12
        y = t + (yt - rr - t) * u
        right.append((wb / 2 + (wt / 2 - wb / 2) * (y - t) / max(yt - t, 1e-6), y))
    zc = wb / 2 + (wt / 2 - wb / 2) * (yt - rr - t) / max(yt - t, 1e-6)
    for i in range(9):
        a = math.radians(90 * i / 8)
        right.append((zc - rr + rr * math.cos(a), yt - rr + rr * math.sin(a)))
    for i in range(1, 8):
        right.append(((zc - rr) * (1 - i / 8), yt))
    left = [(-z, y) for z, y in reversed(right[1:])]
    return right + left[:-1]


def ring3(x, ring):
    return [(x, y, z) for z, y in ring]


def z_on(ring, y, out=4.0):
    """+z of a ring's right side at height y (just proud of the surface)."""
    best = None
    for (z0, y0), (z1, y1) in zip(ring, ring[1:]):
        if z0 > 0 and z1 > 0 and min(y0, y1) <= y <= max(y0, y1) and y0 != y1:
            z = z0 + (z1 - z0) * (y - y0) / (y1 - y0)
            best = z if best is None else max(best, z)
    return (best or 0.0) + out


def stations(x0, x1, step, dense=()):
    xs = set()
    x = x0
    while x < x1:
        xs.add(round(x, 3))
        x += step
    xs.add(x1)
    for c, half, st in dense:
        x = c - half
        while x <= c + half:
            if x0 <= x <= x1:
                xs.add(round(x, 3))
            x += st
    return sorted(xs)


def build():
    m = Model("hatchback")
    xs = stations(-L / 2, L / 2, 50.0, dense=[(X_FA - ARCH_R, 30, 6.0), (X_FA + ARCH_R, 30, 6.0),
                                             (X_RA - ARCH_R, 30, 6.0), (X_RA + ARCH_R, 30, 6.0),
                                             (-L / 2 + 80, 80, 10.0), (L / 2 - 80, 80, 10.0),
                                             (A_X, 20, 10.0), (C_X, 20, 10.0)])
    body = m.loft([ring3(x, body_ring(x)[0]) for x in xs], name="body")
    body.crease = 40.0
    cab_x = [x for x in xs if A_X <= x <= C_X]
    cab = m.loft([ring3(x, cabin_ring(x)) for x in cab_x], name="cabin")
    cab.crease = 40.0
    # wheels: tire (closed revolved loop), rim and lug nuts, axis along Z
    tire_prof = spline([(RIM_R - 5, -TIRE_W / 2 + 10), (TIRE_R - 25, -TIRE_W / 2), (TIRE_R, -TIRE_W / 2 + 40),
                        (TIRE_R, TIRE_W / 2 - 40), (TIRE_R - 25, TIRE_W / 2), (RIM_R - 5, TIRE_W / 2 - 10)],
                       per_segment=5)
    for xa in (X_FA, X_RA):
        for side in (-1, 1):
            zc = side * TRACK / 2
            m.revolve(tire_prof, axis="z", center=(xa, TIRE_R, zc), closed=True, segments=72,
                      name="tire")
            face = zc + side * (TIRE_W / 2 - 30)
            m.cylinder((xa, TIRE_R, min(zc, face)), RIM_R, abs(face - zc), axis="z", segments=72,
                       name="rim")
            m.cylinder((xa, TIRE_R, face if side > 0 else face - 12), 62, 12, axis="z", segments=36,
                       name="hub")
            for k in range(5):
                a = 2 * math.pi * k / 5
                m.cylinder((xa + 95 * math.cos(a), TIRE_R + 95 * math.sin(a), face if side > 0 else face - 16),
                           13, 16, axis="z", segments=16, name="lug")
    # lamps: shallow domes just proud of the nose / tail; mirrors on short stalks
    for side in (-1, 1):
        m.ellipsoid((-L / 2 + 185, 600, side * 560), (170, 45, 190), segments=40, rings=16,
                    name="headlamp")
        m.ellipsoid((L / 2 - 175, 820, side * 600), (160, 60, 160), segments=40, rings=16,
                    name="taillamp")
        mx = A_X + 210
        my = hood(mx) + 75
        mz = side * (z_on(body_ring(mx)[0], hood(mx) - 10, 0) + 60)
        m.ellipsoid((mx, my, mz), (55, 48, 95), segments=32, rings=14, name="mirror")
    m.box((-L / 2 + 75, 450, 0), (140, 110, 640), r=30, name="grille")
    for a, b in (("body", "headlamp"), ("body", "taillamp"), ("body", "grille"), ("body", "mirror"),
                 ("tire", "rim"), ("rim", "hub"), ("rim", "lug"), ("hub", "lug")):
        m.joint(a, b)
    # door shut lines, sill line and side windows, on the surfaces (both sides)
    for side in (-1, 1):
        for xd in (-650.0, 560.0):
            ring = body_ring(xd)[0]
            ys = [bottom(xd) + 70 + k * 30 for k in range(int((hood(xd) - bottom(xd) - 160) / 30))]
            body.line([(xd, y, side * z_on(ring, y)) for y in ys], "thin")
        win_x = [x for x in cab_x if roof(x) - hood(x) > 330]
        lo = [(x, hood(x) + 45, side * z_on(cabin_ring(x), hood(x) + 45)) for x in win_x]
        hi = [(x, roof(x) - 75, side * z_on(cabin_ring(x), roof(x) - 75)) for x in reversed(win_x)]
        cab.line(lo + hi + [lo[0]], "thin")
        bp = 520.0
        ring = cabin_ring(bp)
        cab.line([(bp, y, side * z_on(ring, y)) for y in range(int(hood(bp) + 45), int(roof(bp) - 75), 25)],
                 "thin")
    return m


def main():
    m = build()
    print(m.stats())
    for ax, (lo, hi) in m.envelope().items():         # which part sets each extreme
        print(f"  {ax}: {lo[0]:9.1f} ({lo[1]})  ..  {hi[0]:9.1f} ({hi[1]})")
    sh = Sheet("D", product="Hatchback C1", page=1, company="Acme Motors", date="2026-10-23")
    sh.notes([
        "VEHICLE AT CURB WEIGHT, TIRES AT NOMINAL PRESSURE.",
        "ACCESSORIES MUST NOT EXTEND BEYOND THE PRODUCT ENVELOPE.",
        "DO NOT COVER LAMPS, CAMERAS OR SENSORS.",
    ])
    sh.title_block(title="HATCHBACK C1\nVEHICLE DIMENSIONS", drawing_number="ACME-VD-0001",
                   rev="A", sheet=(1, 1))
    s = 0.065
    side = sh.model_view(m, "front", 390, 338, s, name="side")       # looking at the car's side
    nose = side.projected("left", at=118)                            # looking at the nose
    tail = side.projected("right", at=650)
    plan = side.projected("top", at=150)
    sb = side.bbox()
    g = 0.0
    side.dim_h((-L / 2, g, 0), (L / 2, g, 0), offset=-30, ref=sb, label="OVERALL LENGTH")
    side.dim_chain([(-L / 2, g, 0), (X_FA, g, 0), (X_RA, g, 0), (L / 2, g, 0)], axis="h",
                   offset=-12, ref=sb)
    side.dim_v((X_RA, 0, 0), (ROOF_X0, HGT, 0), offset=40, ref=sb, label="OVERALL\nHEIGHT")
    side.dim_v((0, 0, 0), (0, CLEAR, 0), offset=0, place="outside", side="end",
               label="GROUND\nCLEARANCE")
    side.diameter(side.ref_circle((X_RA, TIRE_R, TRACK / 2), 2 * TIRE_R), angle=60, length=9,
                  decimals=0, label="TIRE")
    side.ramp_angle((X_FA, TIRE_R, 0), TIRE_R, toward="left", label="APPROACH")
    side.ramp_angle((X_RA, TIRE_R, 0), TIRE_R, toward="right", label="DEPARTURE")
    nb = nose.bbox()
    body = m.meshes[0]
    ymid = 500.0                               # the waist: widest height of the section
    nose.dim_h((0, ymid, -half_width(0, ymid)), (0, ymid, half_width(0, ymid)), offset=-26, ref=nb,
               label="BODY WIDTH")
    for zc in (-TRACK / 2, TRACK / 2):                 # tire centre lines for the track
        nose.centerline((-L / 2, 0, zc), (-L / 2, 2 * TIRE_R, zc), extend=3)
    nose.dim_h((-L / 2, TIRE_R, -TRACK / 2), (-L / 2, TIRE_R, TRACK / 2), offset=-12, ref=nb,
               label="TRACK")
    tail.callout((L / 2, 820, 610), "TAIL LAMP", dx=18, dy=22, flags=[3])
    pb = plan.bbox()
    mirrors = [mm for mm in m.meshes if mm.name == "mirror"]
    lo_z = min(mm.bounds()[0][2] for mm in mirrors)
    hi_z = max(mm.bounds()[1][2] for mm in mirrors)
    mx = A_X + 210
    plan.dim_v((mx, HGT, lo_z), (mx, HGT, hi_z), offset=14, ref=pb, label="WIDTH OVER\nMIRRORS")
    plan.callout(mirrors[-1].point("mid", "max", "max"), "MIRROR", dx=20, dy=-14)
    iv = sh.iso(250, 455, 0.042, yaw=-32, pitch=18, model=m, name="hero")
    iv.callout((300, 1000, WID / 2), "ENTIRE VEHICLE SURFACE", dx=60, dy=40, arrow="dot", flags=[2])
    os.makedirs(OUT, exist_ok=True)
    sh.save(os.path.join(OUT, "car.svg"), pdf=True)


if __name__ == "__main__":
    main()
