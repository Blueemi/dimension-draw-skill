"""Starting point for a new dimensional drawing. Copy this file next to where the
output should go, fix SKILL_SCRIPTS if you moved it, then fill in the product.

Run: python3 template.py   (writes out/<name>.svg/.png and prints the CHECK report)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_SCRIPTS = os.path.join(HERE, "..", "scripts")      # <skill>/scripts
sys.path.insert(0, SKILL_SCRIPTS)
from dimdraw import Sheet, rect_path, circle_path, slot_path  # noqa: E402,F401

OUT = os.path.join(HERE, "out")

# ---- 1. the product, in mm (one place, with sources) ----------------------------------
W, H, T = 60.00, 120.00, 9.00      # width, length, thickness   (source: ...)
R = 8.00                           # plan corner radius          (source: ...)
EDGE_R = 1.50                      # edge round                  (estimated)
BTN = (30.00, 12.00, 2.40)         # button: from top edge, length, width


def main():
    # ---- 2. the sheet ----------------------------------------------------------------
    sh = Sheet("D", product="Product Name", page=1, company="Company Inc.")
    sh.notes([
        "NO METAL CONTACT WITH PRODUCT.",
        "DO NOT OBSTRUCT PORTS.",
    ])
    sh.title_block(title="PRODUCT NAME\nCASE DESIGN GUIDE", drawing_number="DG-0001", rev="A",
                   sheet=(1, 1))

    s = 1.5          # view scale (sheet mm per model mm)
    yc = 300         # sheet y shared by the front and side views (projection alignment)

    # ---- 3. front view ---------------------------------------------------------------
    f = sh.view(x=330, y=yc, scale=s, name="front")
    body = f.rect(0, 0, W, H, r=R, corner="continuous")
    f.dim_h(body.tl, body.tr, offset=16, ref=body, label="PRODUCT\nWIDTH")
    f.dim_v(body.tr, body.br, offset=16, ref=body, label="PRODUCT\nLENGTH")

    # ---- 4. left side view (third-angle: to the left of the front view) --------------
    lv = sh.view(x=180, y=yc, scale=s, name="left")
    lb = lv.rect(0, 0, T, H, r=EDGE_R)
    btn = lv.slot(0, H / 2 - BTN[0] - BTN[1] / 2, BTN[1], BTN[2], angle=90, style="thick")
    lv.dim_v(lb.tl, btn.tl, offset=-12, ref=lb)
    lv.dim_v(btn.top_mid, btn.bottom_mid, offset=4, ref=lb, place="outside", side="end")
    lv.dim_h(lb.bl, lb.br, offset=-12, ref=lb, label="PRODUCT\nTHICKNESS")

    # ---- 5. hero view ----------------------------------------------------------------
    iv = sh.iso(620, 300, 0.9, yaw=-35, pitch=35, pre=[("x", 90)], name="hero")
    iv.extrude(rect_path(-W / 2, -H / 2, W / 2, H / 2, R, "continuous"), -T / 2, T / 2,
               fillet=EDGE_R)
    iv.callout((0, 0, -T / 2), "ENTIRE PRODUCT SURFACE", dx=30, dy=40, arrow="dot", flags=[1])

    # ---- 6. save, read the CHECK report, look at the PNG, iterate ---------------------
    os.makedirs(OUT, exist_ok=True)
    sh.save(os.path.join(OUT, "product.svg"), pdf=True)


if __name__ == "__main__":
    main()
