"""Example: two-sheet accessory design guide for a fictional handset, laid out
like Apple's iPhone sheets (overview sheet + keep-out sheet).

Run:  python3 examples/handset.py   ->  examples/out/handset-1.png, -2.png, handset.pdf
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from dimdraw import Sheet, rect_path, circle_path, slot_path, save_pdf  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---- the product, in mm ---------------------------------------------------------
W, H, T = 71.50, 149.60, 8.25         # width, length, thickness
R = 10.50                             # plan-view corner radius (continuous corner)
GLASS_IN, ACTIVE_IN = 1.15, 2.60      # cover glass / active area insets from the outline
PILL_W, PILL_H, PILL_TOP = 18.00, 5.40, 6.20
EDGE_R = 1.60                         # band-to-glass edge round

# buttons: (name, distance from top edge to button top, length)
LEFT_BUTTONS = [("ACTION BUTTON", 33.90, 6.90), ("(+) VOLUME BUTTON", 47.90, 11.00),
                ("(-) VOLUME BUTTON", 61.90, 11.00)]
RIGHT_BUTTONS = [("SIDE BUTTON", 58.00, 18.50), ("CAMERA CONTROL", 98.00, 19.00)]
BTN_W, BTN_PROUD = 2.60, 0.45         # button width across the band, protrusion

# camera plateau on the back, positions measured on the back from its top-left corner
PLAT = dict(x0=3.00, y0=3.00, size=42.00, r=8.40, rise=1.40)
LENS_D, LENS_IN_D, LENS_RISE = 15.60, 12.80, 2.00
LENSES = [(13.80, 13.80), (13.80, 34.20), (31.00, 24.00)]   # (x from left, y from top)
FLASH = (40.00, 9.80, 6.60)
MIC = (40.00, 24.00, 1.20)
SENSOR = (40.00, 38.20, 6.60)

PORT_W, PORT_H = 8.90, 3.20
SPEAKER_X = [11.50 + 2.10 * i for i in range(6)]
MIC_X = [-11.50 - 2.10 * i for i in range(4)]
SCREW_X = 7.40


def back_xy(x_from_left, y_from_top):
    """Back-view model coords (origin at the product center, back facing you)."""
    return (-W / 2 + x_from_left, H / 2 - y_from_top)


def corner_points(shape, xs_from_left):
    """Points on the top-left corner curve of a rounded outline at given x."""
    pl = shape.path.polylines()[0]
    out = []
    for dx in xs_from_left:
        x = shape.left + dx
        best = None
        for p, q in zip(pl, pl[1:]):
            if (p[0] - x) * (q[0] - x) <= 0 and p[0] != q[0] and min(p[1], q[1]) > shape.cy:
                if p[0] < shape.cx:
                    t = (x - p[0]) / (q[0] - p[0])
                    y = p[1] + t * (q[1] - p[1])
                    best = y if best is None else max(best, y)
        out.append((x, best))
    return out


def sheet_one():
    sh = Sheet("D", product="Handset", page=1, company="Acme Inc.", date="2026-10-23")
    sh.notes([
        "NO METAL CONTACT WITH PRODUCT.",
        "DO NOT OBSTRUCT PORTS.",
        "DO NOT OBSTRUCT THE IMAGING FEATURES: FRONT CAMERA, REAR CAMERA, REAR FLASH, REAR SENSOR.",
        "DO NOT OBSTRUCT FORWARD FACING SENSORS.",
        "RELATIVE MAGNETIC PERMEABILITY OF ANY METAL USED ON CASE: 1.05µ MAX, PER ASTM A342/A342M-14.",
        "DO NOT TOUCH GLASS.",
        "NO MAGNETS ON REAR OF PRODUCT EXCEPT CHARGING MAGNETS.",
        "CASE THICKNESS ON BACKSIDE OF PRODUCT: 2.1 mm MAX TO ENSURE FULL FUNCTIONALITY.",
    ])
    sh.title_block(title="HANDSET\nCASE DESIGN GUIDE", drawing_number="ACME-DG-0001", rev="A",
                   sheet=(1, 2))
    s = 1.47
    yc = 305

    # ---- front view --------------------------------------------------------------
    f = sh.view(x=318, y=yc, scale=s, name="front")
    body = f.rect(0, 0, W, H, r=R, corner="continuous")
    glass = f.rect(0, 0, W - 2 * GLASS_IN, H - 2 * GLASS_IN, r=R - GLASS_IN,
                   corner="continuous", style="thin")
    active = f.rect(0, 0, W - 2 * ACTIVE_IN, H - 2 * ACTIVE_IN, r=R - ACTIVE_IN,
                    corner="continuous", style="thin")
    f.hatch(active, angle=45, spacing=2.0)
    pill = f.slot(0, H / 2 - PILL_TOP - PILL_H / 2, PILL_W, PILL_H, angle=0, fill="#fff")
    for name, top, L in LEFT_BUTTONS:
        f.box(-W / 2 - BTN_PROUD, H / 2 - top, -W / 2, H / 2 - top - L, style="thick")
    for name, top, L in RIGHT_BUTTONS:
        f.box(W / 2, H / 2 - top, W / 2 + BTN_PROUD, H / 2 - top - L, style="thick")
    # Apple's PRODUCT WIDTH / THICKNESS exclude buttons and the camera bump
    f.dim_h(body.tl, body.tr, offset=50, ref=body, label="PRODUCT\nWIDTH", overall=False)
    f.ordinate_x([pill.top_mid], datum=-W / 2, ref=body, offset=20, datum_at=body.left_mid,
                 datum_shift=-9)
    f.dim_h(pill.tl, pill.tr, offset=7, ref=body, place="outside", side="start")
    f.ordinate_y([(pill.left, pill.top), (pill.left, pill.bottom)], datum=H / 2, ref=body,
                 offset=-12, datum_at=(body.left + R * 0.3, body.top))
    f.dim_h(active.bl, active.br, offset=-12, ref=body, label="DISPLAY\nACTIVE AREA")
    f.dim_h(glass.bl, glass.br, offset=-26, ref=body, label="GLASS")
    f.dim_v(active.tr, active.br, offset=14, ref=body, label="DISPLAY\nACTIVE AREA")
    f.dim_v(glass.tr, glass.br, offset=28, ref=body, label="GLASS")
    f.dim_v(body.tr, body.br, offset=42, ref=body, label="PRODUCT\nLENGTH")
    for name, top, L in LEFT_BUTTONS:
        y = H / 2 - top - L / 2
        f.dim_h((-W / 2 - BTN_PROUD, y), (-W / 2, y), offset=0, place="outside", side="start",
                label=name)
    f.callout((active.left + 9, -20), "ACTIVE AREA", dx=-30, dy=0, arrow="dot")
    f.callout((glass.left + 0.5, -40), "COVER GLASS", dx=-26, dy=0, arrow="dot", flags=[6])
    f.detail_rect(-W / 2 - 3, H / 2 - 22, -W / 2 + 22, H / 2 + 3, "A", corner="tl", length=9)

    # ---- left side view (third-angle: left of the front view) ---------------------
    # x axis = product Z (display toward the front view, camera plateau away from it)
    lv = sh.view(x=150, y=yc, scale=s, name="left")
    lb = lv.rect(0, 0, T, H, r=EDGE_R)
    for x in (T / 2 - 0.9, -T / 2 + 0.9):
        lv.line((x, H / 2 - EDGE_R), (x, -H / 2 + EDGE_R), style="thin")
    for y in (H / 2 - 12, -H / 2 + 12):
        lv.line((-T / 2, y), (T / 2, y), style="thin")
    plat_top, plat_bot = H / 2 - PLAT["y0"], H / 2 - PLAT["y0"] - PLAT["size"]
    lv.box(-T / 2 - PLAT["rise"], plat_top, -T / 2, plat_bot, r=0.5)
    lens_top = H / 2 - (LENSES[0][1] - LENS_D / 2)
    lens_bot = H / 2 - (LENSES[1][1] + LENS_D / 2)
    lv.box(-T / 2 - PLAT["rise"] - LENS_RISE, lens_top, -T / 2 - PLAT["rise"], lens_bot, r=0.4)
    btns = []
    for name, top, L in LEFT_BUTTONS:
        btns.append(lv.slot(0, H / 2 - top - L / 2, L, BTN_W, angle=90, style="thick"))
    lv.dim_baseline(lb.tl, [b.tl for b in btns], axis="v", offset=-14, step=11, ref=lb)
    lv.dim_v(lb.tl, lb.bl, offset=-48, ref=lb)
    lv.dim_v(btns[0].top_mid, btns[0].bottom_mid, offset=4, ref=lb, place="outside",
             side="end")
    lv.dim_v(btns[1].top_mid, btns[1].bottom_mid, offset=4, ref=lb, prefix="2X",
             place="outside", side="end")
    lv.dim_h(btns[2].bl, btns[2].br, offset=-6, ref=btns[2], prefix="3X", place="outside",
             side="end")
    lv.dim_h(lb.bl, lb.br, offset=-12, ref=lb, label="PRODUCT\nTHICKNESS", overall=False)

    # ---- right side view -----------------------------------------------------------
    # x axis = -Z (display toward the front view on the left)
    rv = sh.view(x=490, y=yc, scale=s, name="right")
    rb = rv.rect(0, 0, T, H, r=EDGE_R)
    for x in (T / 2 - 0.9, -T / 2 + 0.9):
        rv.line((x, H / 2 - EDGE_R), (x, -H / 2 + EDGE_R), style="thin")
    for y in (H / 2 - 12, -H / 2 + 12):
        rv.line((-T / 2, y), (T / 2, y), style="thin")
    rv.box(T / 2, plat_top, T / 2 + PLAT["rise"], plat_bot, r=0.5)
    rv.box(T / 2 + PLAT["rise"], lens_top, T / 2 + PLAT["rise"] + LENS_RISE, lens_bot, r=0.4)
    rbtn = []
    for name, top, L in RIGHT_BUTTONS:
        rbtn.append(rv.slot(0, H / 2 - top - L / 2, L, BTN_W, angle=90, style="thick"))
    rv.dim_baseline(rb.tr, [b.tr for b in rbtn], axis="v", offset=16, step=12, ref=rb)
    for b, (name, _, _) in zip(rbtn, RIGHT_BUTTONS):
        rv.dim_v(b.top_mid, b.bottom_mid, offset=-3.5, ref=rb, place="outside", side="start",
                 label=name)
    rv.dim_h((T / 2, plat_top), (T / 2 + PLAT["rise"], plat_top), offset=25, ref=rb,
             place="outside", side="start", label="BACK PLATE TO\nCAMERA PLATEAU")
    rv.dim_h((T / 2 + PLAT["rise"], lens_top), (T / 2 + PLAT["rise"] + LENS_RISE, lens_top),
             offset=11, ref=rb, place="outside", side="start",
             label="CAMERA PLATEAU TO\nREAR CAMERA GLASS")

    # ---- back view -------------------------------------------------------------------
    bv = sh.view(x=612, y=yc, scale=s, name="back")
    bb = bv.rect(0, 0, W, H, r=R, corner="continuous")
    pcx, pcy = back_xy(PLAT["x0"] + PLAT["size"] / 2, PLAT["y0"] + PLAT["size"] / 2)
    bv.rect(pcx, pcy, PLAT["size"], PLAT["size"], r=PLAT["r"], corner="continuous")
    for (lx, ly) in LENSES:
        c = back_xy(lx, ly)
        bv.circle(*c, d=LENS_D)
        bv.circle(*c, d=LENS_IN_D, style="thin")
    for (x, y, d) in (FLASH, SENSOR, MIC):
        bv.circle(*back_xy(x, y), d=d)
    logo = bv.circle(0, 0, d=14, style="phantom")
    bv.center_mark(logo, extend=3)
    bv.dim_v(bb.tl, (0, 0), offset=-14, ref=bb, label="PRODUCT\nCENTER")
    bv.dim_h(bb.bl, (0, 0), offset=-12, ref=bb, label="PRODUCT\nCENTER")
    bv.detail_rect(-W / 2 - 2, H / 2 - PLAT["size"] - 5, -W / 2 + PLAT["size"] + 5, H / 2 + 2,
                   "D", corner="tr", length=9)

    # ---- detail D: camera plateau, enlarged ------------------------------------------
    k = 2.0
    d = sh.view(x=762, y=128, scale=k, name="detailD", center=(pcx, pcy))
    d.set_clip(-W / 2 - 1, H / 2 - PLAT["size"] - 6, -W / 2 + PLAT["size"] + 6, H / 2 + 1)
    db = d.rect(0, 0, W, H, r=R, corner="continuous")
    d.set_clip(None, None, None, None)
    plat = d.rect(pcx, pcy, PLAT["size"], PLAT["size"], r=PLAT["r"], corner="continuous")
    lens_shapes = []
    for (lx, ly) in LENSES:
        c = back_xy(lx, ly)
        lens_shapes.append(d.circle(*c, d=LENS_D, style="thick"))
        d.circle(*c, d=LENS_IN_D, style="thin")
        d.center_mark(lens_shapes[-1], extend=1.5)
    fl = d.circle(*back_xy(FLASH[0], FLASH[1]), d=FLASH[2])
    mic = d.circle(*back_xy(MIC[0], MIC[1]), d=MIC[2])
    sen = d.circle(*back_xy(SENSOR[0], SENSOR[1]), d=SENSOR[2])
    d.center_mark(fl, extend=1.5)
    d.center_mark(sen, extend=1.5)
    d.ordinate_y([l.center for l in lens_shapes], datum=H / 2, ref=db, offset=-8,
                 datum_at=(db.left, db.top))
    d.ordinate_y([fl.center, mic.center, sen.center], datum=H / 2, ref=plat, offset=8)
    d.ordinate_x([(lens_shapes[0].cx, lens_shapes[0].cy, "2X"), lens_shapes[2].center,
                  (fl.cx, fl.cy, "3X")], datum=-W / 2, ref=db, offset=8,
                 datum_at=(db.left, db.top))
    col_x = d.S((db.left, 0))[0] - 8
    row_y = (d.S(lens_shapes[1].center)[1] + d.S(lens_shapes[2].center)[1]) / 2
    d.diameter(lens_shapes[1], angle=150, prefix="3X", at=(col_x + 4, row_y))
    d.diameter(fl, angle=-30, length=11, flags=[3], label="FLASH", dy=-9)
    d.diameter(mic, angle=-30, length=11, flags=[2], label="REAR MIC", dy=-9)
    d.diameter(sen, angle=-40, length=11, flags=[3], label="REAR SENSOR", dy=-10)
    d.callout(lens_shapes[0].at(150), "REAR CAMERA 1", dx=-12, dy=8, flags=[3])
    d.callout(lens_shapes[1].at(210), "REAR CAMERA 2", dx=-12, dy=-12, flags=[3])
    d.callout(lens_shapes[2].at(-100), "REAR CAMERA 3", dx=-4, dy=-36, flags=[3])
    sh.label(790, 202, "DETAIL", "D")

    # ---- detail A: corner profile ------------------------------------------------------
    a = sh.view(x=96, y=488, scale=3.0, name="detailA", center=(-W / 2 + 9, H / 2 - 9))
    a.set_clip(-W / 2 - 1, H / 2 - 19, -W / 2 + 19, H / 2 + 1)
    ab = a.rect(0, 0, W, H, r=R, corner="continuous")
    a.rect(0, 0, W - 2 * GLASS_IN, H - 2 * GLASS_IN, r=R - GLASS_IN, corner="continuous",
           style="thin")
    a.set_clip(None, None, None, None)
    pts = corner_points(ab, [0.05, 0.9, 3.8, 8.4, 16.05])
    a.ordinate_x(pts, datum=-W / 2, ref=ab, offset=8, datum_at=(ab.left, H / 2 - 17),
                 mark="tick")
    a.ordinate_y(pts[:-1], datum=H / 2, ref=ab, offset=-8, datum_at=(-W / 2 + 18, ab.top))
    sh.label(212, 522, "DETAIL", "A", sub="CORNER PROFILE (ALL FOUR CORNERS)")

    # ---- hero view -------------------------------------------------------------------
    iv = sh.iso(762, 338, 0.8, yaw=-35, pitch=35, pre=[("x", 90)], name="hero")
    hero_solids(iv)
    iv.callout((-12, 10, -T / 2), "ENTIRE PRODUCT SURFACE", dx=8, dy=40, arrow="dot",
               flags=[1, 5])
    iv.callout((6, -30, -T / 2), "BACK OF PRODUCT ONLY", dx=14, dy=34, arrow="dot", flags=[7, 8])
    return sh


def hero_solids(iv):
    body = iv.extrude(rect_path(-W / 2, -H / 2, W / 2, H / 2, R, "continuous"), -T / 2, T / 2,
                      fillet=(EDGE_R, EDGE_R), name="body")
    # camera plateau and lenses sit on the back (-Z); profile coords are front-view x, y
    px0 = W / 2 - PLAT["x0"] - PLAT["size"]
    py1 = H / 2 - PLAT["y0"]
    plat = rect_path(px0, py1 - PLAT["size"], px0 + PLAT["size"], py1, PLAT["r"], "continuous")
    iv.extrude(plat, -T / 2 - PLAT["rise"], -T / 2, fillet=(0.5, 0), name="plateau")
    z_plat = -T / 2 - PLAT["rise"]
    for (lx, ly) in LENSES:
        x, y = W / 2 - lx, H / 2 - ly
        iv.cylinder((x, y, z_plat - LENS_RISE), LENS_D / 2, LENS_RISE, fillet=(0.4, 0), name="lens")
        iv.cylinder((x, y, z_plat - LENS_RISE - 0.3), LENS_IN_D / 2, 0.3, name="lens glass")
    for (lx, ly, dd) in (FLASH, SENSOR):
        iv.cylinder((W / 2 - lx, H / 2 - ly, z_plat - 0.15), dd / 2, 0.15, name="window")
    for name, top, L in LEFT_BUTTONS:
        iv.extrude(slot_path(H / 2 - top - L / 2, 0, L, BTN_W, angle=0), -W / 2 - BTN_PROUD,
                   -W / 2 + 0.3, plane="yz", name="button")
    for name, top, L in RIGHT_BUTTONS:
        iv.extrude(slot_path(H / 2 - top - L / 2, 0, L, BTN_W, angle=0), W / 2 - 0.3,
                   W / 2 + BTN_PROUD, plane="yz", name="button")
    iv.model.joint("body", "button")      # buttons sit 0.3 mm into the frame
    body.mark(circle_path(0, 0, 7), face="bottom")
    return body


def sheet_two():
    sh = Sheet("D", product="Handset", page=2, company="Acme Inc.", date="2026-10-23")
    sh.title_block(title="HANDSET\nCASE DESIGN GUIDE", drawing_number="ACME-DG-0001", rev="A",
                   sheet=(2, 2))
    s = 1.47
    yc = 252
    # ---- keep out area 1: antenna windows ---------------------------------------------
    v1 = sh.view(x=200, y=yc, scale=s, name="koa1")
    b1 = v1.rect(0, 0, W, H, r=R, corner="continuous")
    pcx, pcy = back_xy(PLAT["x0"] + PLAT["size"] / 2, PLAT["y0"] + PLAT["size"] / 2)
    v1.rect(pcx, pcy, PLAT["size"], PLAT["size"], r=PLAT["r"], corner="continuous")
    for (lx, ly) in LENSES:
        v1.circle(*back_xy(lx, ly), d=LENS_D)
    top_y, bot_y = H / 2 - 16.5, -H / 2 + 14.0
    v1.line((-W / 2, top_y), (W / 2, top_y), style="thin")
    v1.line((-W / 2, bot_y), (W / 2, bot_y), style="thin")
    v1.hatch(b1, angle=45, spacing=1.4, within=(-W / 2, top_y, W / 2, H / 2))
    v1.hatch(b1, angle=45, spacing=1.4, within=(-W / 2, -H / 2, W / 2, bot_y))
    v1.dim_v(b1.tr, (W / 2, top_y), offset=12, ref=b1)
    v1.dim_v((W / 2, bot_y), b1.br, offset=12, ref=b1)
    v1.callout((10, H / 2 - 9), "DO NOT OBSTRUCT THIS AREA WITH METAL OR\nOTHER CONDUCTIVE MATERIAL",
               dx=26, dy=30, arrow="dot")
    v1.callout((-12, -H / 2 + 6), "DO NOT OBSTRUCT THIS AREA WITH METAL OR\nOTHER CONDUCTIVE MATERIAL",
               dx=-26, dy=-24, arrow="dot")
    sh.caption("KEEP OUT AREA 1", 200, yc + H * s / 2 + 32)

    # ---- keep out area 2: charging coil + magnets -------------------------------------
    v2 = sh.view(x=430, y=yc, scale=s, name="koa2")
    b2 = v2.rect(0, 0, W, H, r=R, corner="continuous")
    v2.rect(pcx, pcy, PLAT["size"], PLAT["size"], r=PLAT["r"], corner="continuous")
    ring_o = v2.circle(0, -2.0, d=56.0, style="thin")
    ring_i = v2.circle(0, -2.0, d=46.0, style="thin")
    coil = v2.circle(0, -2.0, d=40.0, style="thin")
    v2.hatch(ring_o, holes=ring_i, angle=45, spacing=1.6)
    v2.hatch(coil, angle=-45, spacing=1.6)
    v2.center_mark(ring_o, extend=4)
    v2.diameter(ring_o, angle=-20, length=26, flags=[5, 7], label="MAGNET RING: NO MAGNETIC\nOR PERMEABLE MATERIAL")
    v2.diameter(coil, angle=160, length=40, flags=[5], label="CHARGING COIL: NO METAL OR\nCONDUCTIVE MATERIAL")
    v2.dim_v(b2.tr, (ring_o.cx, ring_o.cy), offset=14, ref=b2, label="COIL\nCENTER")
    sh.caption("KEEP OUT AREA 2", 430, yc + H * s / 2 + 32)

    # ---- section S-S through rear camera 1: field-of-view keep-out cone --------------------
    # section plane: vertical cut through lens 1; x = distance across, y = product Z
    k = 3.4
    sx = sh.view(x=712, y=208, scale=k, name="sectionS")
    lx = back_xy(*LENSES[0])[0]
    # back plate, plateau and lens in section (hatched solid material)
    plate = sx.box(-22, 0, 22, -4.0, style="visible")
    platb = sx.box(-15, 0, 15, PLAT["rise"], r=(0.5, 0.5, 0, 0))
    lens = sx.box(-LENS_D / 2, PLAT["rise"], LENS_D / 2, PLAT["rise"] + LENS_RISE, r=(0.4, 0.4, 0, 0))
    sx.hatch([plate, platb], angle=45, spacing=1.0)
    sx.hatch(lens, angle=-45, spacing=0.8, cross=True)
    top = PLAT["rise"] + LENS_RISE
    half = math.radians(84 / 2)
    L = 14.0
    apex = (0, top - LENS_IN_D / 2 / math.tan(half))
    pa = (-LENS_IN_D / 2, top)
    pb = (LENS_IN_D / 2, top)
    ea = (-LENS_IN_D / 2 - L * math.tan(half), top + L)
    eb = (LENS_IN_D / 2 + L * math.tan(half), top + L)
    sx.line(pa, ea, style="phantom")
    sx.line(pb, eb, style="phantom")
    sx.angle(apex, ea, eb, r=40, label="REAR CAMERA\nKEEP-OUT CONE")
    sx.dim_h(pa, pb, offset=-14, ref=plate, label="KEEP-OUT CONE\nBASE DIAMETER", prefix="Ø")
    sx.dim_v((LENS_D / 2, PLAT["rise"]), (LENS_D / 2, top), offset=10, ref=plate, place="outside",
             side="end")
    sx.dim_v((15, 0), (15, PLAT["rise"]), offset=10, ref=plate, place="outside", side="end")
    sh.label(712, 290, "SECTION", "S - S")

    # ---- the section line on a small back view ---------------------------------------------
    v3 = sh.view(x=712, y=366, scale=0.6, name="key")
    v3.rect(0, 0, W, H, r=R, corner="continuous")
    v3.rect(pcx, pcy, PLAT["size"], PLAT["size"], r=PLAT["r"], corner="continuous")
    for (lxx, lyy) in LENSES:
        v3.circle(*back_xy(lxx, lyy), d=LENS_D)
    c1 = back_xy(*LENSES[0])
    v3.section_line((-W / 2 - 4, c1[1]), (W / 2 + 4, c1[1]), "S", look=(0, -1), arm=6)
    # ---- detail C: bottom of the product, enlarged -----------------------------------
    # x axis = product X, y axis = product Z (display up)
    bt = sh.view(x=330, y=468, scale=2.6, name="detailC")
    bo = bt.rect(0, 0, W, T, r=EDGE_R)
    for z in (T / 2 - 0.9, -T / 2 + 0.9):
        bt.line((-W / 2 + EDGE_R, z), (W / 2 - EDGE_R, z), style="thin")
    bt.box(W / 2 - PLAT["x0"] - PLAT["size"], -T / 2, W / 2 - PLAT["x0"], -T / 2 - PLAT["rise"],
           r=0.5)
    port = bt.slot(0, 0, PORT_W, PORT_H, angle=0, style="thick")
    holes = [bt.circle(x, 0, d=1.5) for x in SPEAKER_X]
    mics = [bt.circle(x, 0, d=1.0) for x in MIC_X]
    screws = [bt.circle(sx, 0, d=1.5) for sx in (-SCREW_X, SCREW_X)]
    bt.ordinate_x([port.center] + [h.center for h in holes] + [m.center for m in mics],
                  datum=-W / 2, ref=bo, offset=10, datum_at=bo.left_mid)
    bt.dim_h(port.bl, port.br, offset=-8, ref=bo, label="RECOMMENDED\nCONNECTOR KEEPOUT")
    bt.dim_v(port.br, port.tr, offset=8, ref=bo, place="outside", side="end")
    bt.diameter(holes[-1], angle=-40, length=10, prefix=f"{len(holes)}X", flags=[2],
                label="SPEAKER PORTS")
    bt.diameter(mics[-1], angle=-140, length=10, prefix=f"{len(mics)}X", flags=[2],
                label="BOTTOM MIC")
    bt.diameter(screws[0], angle=-115, length=12, prefix="2X", label="SCREW")
    sh.label(330, 524, "DETAIL", "C")

    sh.notes([(5, "RELATIVE MAGNETIC PERMEABILITY OF ANY METAL USED ON CASE: 1.05µ MAX."),
              (7, "NO MAGNETS ON REAR OF PRODUCT EXCEPT CHARGING MAGNETS.")],
             title="NOTES:", subtitle="(SEE SHEET 1 FOR ALL NOTES)")
    return sh


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    s1 = sheet_one()
    s1.save(os.path.join(OUT, "handset-1.svg"))
    s2 = sheet_two()
    s2.save(os.path.join(OUT, "handset-2.svg"))
    save_pdf([s1, s2], os.path.join(OUT, "handset.pdf"))
