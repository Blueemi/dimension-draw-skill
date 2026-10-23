"""Stroke text: every character becomes SVG path data, so drawings carry no font
dependency and render identically in any SVG renderer.

Two faces:
  mono    - monospaced single-stroke drafting face (font_mono.py), used for
            nearly all text on the sheet
  triplex - Hershey Roman Triplex, used for the few engraved-looking headings
            (NOTES:, METRIC, company name, sheet size letter)
  duplex  - Hershey Roman Duplex (outline-looking capitals)
"""

import json
import math
import os
import re

from . import font_mono

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOKEN = re.compile(r"[MLACZ]|-?\d*\.?\d+(?:e-?\d+)?")
_parsed_mono = {}
_hershey = {}


def _parse(d):
    toks = _TOKEN.findall(d)
    out = []
    i = 0
    while i < len(toks):
        c = toks[i]
        i += 1
        n = {"M": 2, "L": 2, "A": 7, "C": 6, "Z": 0}[c]
        out.append((c, [float(v) for v in toks[i:i + n]]))
        i += n
    return out


def _mono_glyph(ch):
    g = _parsed_mono.get(ch)
    if g is None:
        d = font_mono.GLYPHS.get(ch, font_mono.MISSING)
        g = _parse(d)
        _parsed_mono[ch] = g
    return g


def _hershey_font(name):
    f = _hershey.get(name)
    if f is None:
        with open(os.path.join(_HERE, f"hershey_{name}.json")) as fh:
            f = json.load(fh)
        _hershey[name] = f
    return f


def _fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class TextGeom:
    """Result of laying out a string: path data plus its oriented box."""

    def __init__(self, d, box, width, height):
        self.d = d            # SVG path data, absolute sheet coordinates
        self.box = box        # 4 corner points (sheet coords) of the ink box
        self.width = width    # unrotated extent along the baseline
        self.height = height  # unrotated block height


def advance(h, font="mono"):
    return h * font_mono.ADVANCE / font_mono.CAP


def line_width(s, h, font="mono"):
    if not s:
        return 0.0
    if font == "mono":
        n = len(s)
        return (n - 1) * advance(h) + h * font_mono.GLYPH_W / font_mono.CAP
    f = _hershey_font(font)
    k = h / 10.0
    return sum(f.get(ch, f["?"])[0] for ch in s) * k


def line_spacing(h):
    return h * 1.55


def block_size(text, h, font="mono", spacing=None):
    lines = text.split("\n")
    sp = line_spacing(h) if spacing is None else spacing
    w = max(line_width(ln, h, font) for ln in lines)
    return w, h + sp * (len(lines) - 1)


def layout(text, x, y, h, anchor="start", valign="baseline", rotate=0.0,
           font="mono", spacing=None, align=None):
    """Lay out (multi-line) text.

    (x, y) is the anchor point in sheet mm. anchor: start|middle|end along the
    baseline direction. valign: baseline|top|middle|bottom of the whole block
    (baseline = first line's baseline). rotate: degrees, counter-clockwise as
    seen on paper (90 reads bottom-to-top). align: start|middle|end alignment of
    lines inside a multi-line block (defaults to anchor).
    """
    lines = text.split("\n")
    sp = line_spacing(h) if spacing is None else spacing
    align = align or anchor
    bw, bh = block_size(text, h, font, sp)
    # block-local coordinates: x right, y down, origin at anchor
    if anchor == "start":
        bx0 = 0.0
    elif anchor == "middle":
        bx0 = -bw / 2
    else:
        bx0 = -bw
    if valign == "baseline":
        by0 = -h
    elif valign == "top":
        by0 = 0.0
    elif valign == "middle":
        by0 = -bh / 2
    else:
        by0 = -bh
    th = math.radians(-rotate)  # paper CCW = screen negative angle
    c, s = math.cos(th), math.sin(th)

    def tp(px, py):
        return (x + px * c - py * s, y + px * s + py * c)

    parts = []
    for li, ln in enumerate(lines):
        lw = line_width(ln, h, font)
        if align == "start":
            lx = bx0
        elif align == "middle":
            lx = bx0 + (bw - lw) / 2
        else:
            lx = bx0 + bw - lw
        top = by0 + li * sp
        if font == "mono":
            k = h / font_mono.CAP
            adv = advance(h)
            for ci, ch in enumerate(ln):
                gx = lx + ci * adv
                for cmd, a in _mono_glyph(ch):
                    if cmd in ("M", "L"):
                        px, py = tp(gx + a[0] * k, top + a[1] * k)
                        parts.append(f"{cmd}{_fmt(px)} {_fmt(py)}")
                    elif cmd == "C":
                        pts = [tp(gx + a[j] * k, top + a[j + 1] * k) for j in (0, 2, 4)]
                        parts.append("C" + " ".join(f"{_fmt(p[0])} {_fmt(p[1])}" for p in pts))
                    elif cmd == "A":
                        px, py = tp(gx + a[5] * k, top + a[6] * k)
                        rot = a[2] + math.degrees(th)
                        parts.append(f"A{_fmt(a[0] * k)} {_fmt(a[1] * k)} {_fmt(rot)} "
                                     f"{int(a[3])} {int(a[4])} {_fmt(px)} {_fmt(py)}")
                    else:
                        parts.append("Z")
        else:
            f = _hershey_font(font)
            k = h / 10.0
            gx = lx
            for ch in ln:
                adv_w, strokes = f.get(ch, f["?"])
                for st in strokes:
                    for j in range(0, len(st), 2):
                        px, py = tp(gx + st[j] * k, top + st[j + 1] * k)
                        parts.append(f"{'M' if j == 0 else 'L'}{_fmt(px)} {_fmt(py)}")
                gx += adv_w * k
    box = [tp(bx0, by0), tp(bx0 + bw, by0), tp(bx0 + bw, by0 + bh), tp(bx0, by0 + bh)]
    return TextGeom(" ".join(parts), box, bw, bh)


def stroke_width(h, font="mono"):
    if font == "mono":
        return max(0.13, 0.085 * h)
    if font == "duplex":       # outline-looking capitals: keep the two strokes apart
        return max(0.1, 0.032 * h)
    return max(0.12, 0.092 * h)
