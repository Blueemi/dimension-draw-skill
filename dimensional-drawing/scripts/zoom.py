"""Render a region of a drawing SVG at high resolution for close inspection.

usage: python3 zoom.py SHEET.svg X0 Y0 X1 Y1 [OUT.png] [--px 1800]
Coordinates are sheet millimetres (origin top-left), as printed by the checker.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dimdraw import export  # noqa: E402


def main(argv):
    px = 1800
    if "--px" in argv:
        i = argv.index("--px")
        px = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) < 5:
        print(__doc__)
        return 2
    src = argv[0]
    x0, y0, x1, y1 = (float(v) for v in argv[1:5])
    out = argv[5] if len(argv) > 5 else re.sub(r"\.svg$", "", src) + f".zoom-{int(x0)}-{int(y0)}.png"
    with open(src) as fh:
        svg = export.crop_svg(fh.read(), x0, y0, x1, y1)
    tmp = out + ".tmp.svg"
    with open(tmp, "w") as fh:
        fh.write(svg)
    try:
        res = export.to_png(tmp, out, x1 - x0, y1 - y0, px / (x1 - x0))
    finally:
        os.unlink(tmp)
    if res:
        print(f"wrote {res}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
