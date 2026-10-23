"""Annotation engine. Everything here works in sheet (paper) space: mm, origin
top-left, y down. Views convert model geometry to sheet points and call in.

Conventions follow Apple's accessory drawings: unidirectional (horizontal) text,
text sits in a break of the dimension line, hollow narrow arrowheads, boxed
datum 0.00, ordinate leaders that jog to stay legible, boxed flag-note numbers.
"""

import math

from . import fonts
from .geom import add, sub, mul, dot, unit, dist, polar, fmt, box_overlap, seg_hits_box


def fmt_num(v, decimals=2):
    if decimals <= 0:
        s = f"{round(v):d}"
    else:
        s = f"{v:.{decimals}f}"
    if s.startswith("-") and float(s) == 0:
        s = s[1:]
    return s


def _item_bb(it):
    bb = it.get("_bb")
    if bb is None:
        if it["t"] == "text":
            xs = [p[0] for p in it["box"]]
            ys = [p[1] for p in it["box"]]
            bb = (min(xs), min(ys), max(xs), max(ys))
        elif it.get("lines"):
            xs = [p[0] for pl in it["lines"] for p in pl]
            ys = [p[1] for pl in it["lines"] for p in pl]
            bb = (min(xs), min(ys), max(xs), max(ys)) if xs else False
        else:
            bb = False
        it["_bb"] = bb
    return bb


def clutter(sh, box, owner=None):
    """How busy a sheet region already is: text there counts heavily, each line
    crossing it a little, hatching very little. Used to auto-place text."""
    score = 0.0
    if box[0] < sh.fx0 or box[1] < sh.fy0 or box[2] > sh.fx1 or box[3] > sh.fy1:
        score += 50
    for r in sh.reserved:
        if box_overlap(box, r[1:5]):
            score += 50
    for it in sh.items:
        if owner is not None and it.get("owner") == owner:
            continue
        bb = _item_bb(it)
        if not bb or not box_overlap(bb, box):
            continue
        if it["t"] == "text":
            score += 10
        elif it.get("lines") and it["layer"] in ("geom", "annot"):
            wgt = 0.15 if it.get("kind") == "hatch" else 1.0
            for pl in it["lines"]:
                if any(seg_hits_box(a, b, box) for a, b in zip(pl, pl[1:])):
                    score += wgt
    return score


# ---- low-level emitters ---------------------------------------------------

def line(sh, a, b, w=None, dash=None, owner=None, check=True, layer="annot", color=None,
         kind="line"):
    w = sh.st("thin") if w is None else w
    sh.add_path(f"M{fmt(a[0])} {fmt(a[1])} L{fmt(b[0])} {fmt(b[1])}", w=w, dash=dash,
                lines=[[a, b]], owner=owner, check=check, layer=layer, color=color, kind=kind)


def polyline(sh, pts, w=None, dash=None, owner=None, check=True, layer="annot", closed=False):
    w = sh.st("thin") if w is None else w
    d = "M" + " L".join(f"{fmt(p[0])} {fmt(p[1])}" for p in pts) + (" Z" if closed else "")
    pl = list(pts) + ([pts[0]] if closed else [])
    sh.add_path(d, w=w, dash=dash, lines=[pl], owner=owner, check=check, layer=layer)


def arrow(sh, tip, direction, kind="open", owner=None):
    """Arrowhead with its point at `tip`, pointing along `direction`.
    Returns the point where the shaft should stop."""
    u = unit(direction)
    if kind in (None, "none"):
        return tip
    if kind == "dot":
        r = sh.st("dot_r")
        sh.add_path(_circle_d(tip, r), w=sh.st("thin"), fill="#000", lines=[_circle_pts(tip, r)],
                    owner=owner, layer="annot")
        return tip
    if kind == "tick":
        L = sh.st("arrow_len") * 0.55
        n = (-u[1], u[0])
        a = add(tip, mul(add(u, n), L * 0.7))
        b = sub(tip, mul(add(u, n), L * 0.7))
        line(sh, a, b, w=sh.st("visible"), owner=owner)
        return tip
    L, hw = sh.st("arrow_len"), sh.st("arrow_half")
    n = (-u[1], u[0])
    base = sub(tip, mul(u, L))
    p1 = add(base, mul(n, hw))
    p2 = sub(base, mul(n, hw))
    fill = "#000" if kind == "filled" else "none"
    sh.add_path(f"M{fmt(tip[0])} {fmt(tip[1])} L{fmt(p1[0])} {fmt(p1[1])} "
                f"L{fmt(p2[0])} {fmt(p2[1])} Z", w=sh.st("thin"), fill=fill,
                lines=[[tip, p1, p2, tip]], owner=owner, layer="annot", join="miter")
    return base


def _circle_d(c, r):
    return (f"M{fmt(c[0] - r)} {fmt(c[1])} A{fmt(r)} {fmt(r)} 0 1 0 {fmt(c[0] + r)} {fmt(c[1])} "
            f"A{fmt(r)} {fmt(r)} 0 1 0 {fmt(c[0] - r)} {fmt(c[1])} Z")


def _circle_pts(c, r, n=16):
    return [polar(c, r, 360 * i / n) for i in range(n + 1)]


def text(sh, s, x, y, h=None, anchor="start", valign="baseline", rotate=0.0, font="mono",
         owner=None, check=True, align=None, mask=False, layer="text", color=None, spacing=None):
    h = sh.st("dim_text") if h is None else h
    g = fonts.layout(s, x, y, h, anchor=anchor, valign=valign, rotate=rotate, font=font,
                     align=align, spacing=spacing)
    if mask:
        m = sh.st("text_gap") * 0.6
        bx = _grow(g.box, m)
        sh.add_path("M" + " L".join(f"{fmt(p[0])} {fmt(p[1])}" for p in bx) + " Z", w=0,
                    fill="#fff", lines=None, owner=owner, layer="mask")
    sh.add_text(g, fonts.stroke_width(h, font), owner=owner, check=check, s=s, layer=layer,
                color=color)
    return g


def _grow(box, m):
    cx = sum(p[0] for p in box) / 4
    cy = sum(p[1] for p in box) / 4
    out = []
    for p in box:
        v = unit(sub(p, (cx, cy)))
        out.append(add(p, mul(v, m * math.sqrt(2))))
    return out


def box_rect(sh, x0, y0, x1, y1, w=None, owner=None, check=True, layer="annot"):
    polyline(sh, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], w=w, owner=owner, check=check,
             layer=layer, closed=True)


# ---- flag notes -------------------------------------------------------------

def flag_size(sh, h):
    return h * 1.75


def flag(sh, n, x, y, h=None, owner=None, shape="box", anchor="start", box=None):
    """Boxed (or hexagon) flag-note number with its left edge at x (anchor
    start) and vertically centered on y. box: square size (default 1.75 h).
    Returns the box width."""
    h = sh.st("flag_text") if h is None else h
    s = str(n)
    tw = fonts.line_width(s, h)
    if shape == "hex":
        H = h * 2.1
        W = max(H * 1.15, tw + h * 1.6)
        x0 = x if anchor == "start" else (x - W / 2 if anchor == "middle" else x - W)
        c = (x0 + W / 2, y)
        a = H / 2
        pts = [(x0, y), (x0 + a * 0.58, y - a), (x0 + W - a * 0.58, y - a), (x0 + W, y),
               (x0 + W - a * 0.58, y + a), (x0 + a * 0.58, y + a)]
        polyline(sh, pts, w=sh.st("thin"), owner=owner, closed=True)
        text(sh, s, c[0], y, h, anchor="middle", valign="middle", owner=owner, check=False)
        return W
    S = flag_size(sh, h) if box is None else box
    W = max(S, tw + h * 0.9)
    x0 = x if anchor == "start" else (x - W / 2 if anchor == "middle" else x - W)
    box_rect(sh, x0, y - S / 2, x0 + W, y + S / 2, w=sh.st("thin"), owner=owner)
    text(sh, s, x0 + W / 2, y, h, anchor="middle", valign="middle", owner=owner, check=False)
    return W


def flags_width(sh, flags, h, shape="box"):
    if not flags:
        return 0.0
    tot = 0.0
    for n in flags:
        tw = fonts.line_width(str(n), h)
        if shape == "hex":
            H = h * 2.1
            tot += max(H * 1.15, tw + h * 1.6)
        else:
            tot += max(flag_size(sh, h), tw + h * 0.9)
    return tot + 0.6 * h * len(flags)


# ---- text blocks ----------------------------------------------------------------

class Block:
    """Value or note text, optionally preceded (flags) and/or followed
    (flags_after) by flag boxes, with smaller label lines underneath.
    Multi-line text hangs from its first line, which is the one the leader
    or dimension line attaches to (Apple's style)."""

    def __init__(self, sh, main, label=None, h=None, hl=None, flags=(), flag_shape="box",
                 boxed=False, flags_after=()):
        self.sh = sh
        self.main = main or ""
        self.label = label
        self.h = sh.st("dim_text") if h is None else h
        self.hl = sh.st("label_text") if hl is None else hl
        self.flags = list(flags or ())
        self.flags_after = list(flags_after or ())
        self.flag_shape = flag_shape
        self.boxed = boxed
        self.fh = self.h * 0.82
        self.fgap = self.h * 0.55
        has_text = bool(self.main)
        self.fw = flags_width(sh, self.flags, self.fh, flag_shape)
        if self.flags:   # boxes are 0.6 fh apart, then fgap before the text (none if no text)
            self.fw += (self.fgap if has_text else 0.0) - 0.6 * self.fh
        self.faw = flags_width(sh, self.flags_after, self.fh, flag_shape)
        if self.flags_after:
            self.faw += self.fgap - 0.6 * self.fh
        self.lines = self.main.split("\n") if has_text else []
        self.sp = fonts.line_spacing(self.h)
        self.mw = max((fonts.line_width(ln, self.h) for ln in self.lines), default=0.0)
        self.pad = self.h * 0.35 if boxed else 0.0
        self.w_main = self.fw + self.mw + 2 * self.pad + self.faw
        if label:
            self.lw, self.lh = fonts.block_size(label, self.hl)
        else:
            self.lw, self.lh = 0.0, 0.0
        self.lgap = self.h * 0.55
        self.w = max(self.w_main, self.lw)
        extra = (len(self.lines) - 1) * self.sp if self.lines else 0.0
        # vertical extents relative to the first line's middle
        self.up = self.h / 2 + self.pad
        self.down = self.h / 2 + self.pad + extra + ((self.lgap + self.lh) if label else 0.0)
        self.text_bottom = self.h / 2 + self.pad + extra

    def draw(self, x, ymid, anchor="middle", owner=None, label_align=None, check=True):
        """Draw with the first text line vertically centered at ymid."""
        sh = self.sh
        if anchor == "start":
            x0 = x
        elif anchor == "end":
            x0 = x - self.w_main
        else:
            x0 = x - self.w_main / 2
        cx = x0
        for n in self.flags:
            wbox = flag(sh, n, cx, ymid, self.fh, owner=owner, shape=self.flag_shape)
            cx += wbox + 0.6 * self.fh
        if self.flags:
            cx += self.fgap - 0.6 * self.fh if self.main else -0.6 * self.fh
        boxes = []
        if self.main:
            align = "end" if (anchor == "end" and len(self.lines) > 1) else "start"
            ax = cx + self.pad + (self.mw if align == "end" else 0.0)
            g = text(sh, self.main, ax, ymid - self.h / 2, self.h, anchor=align, valign="top",
                     owner=owner, check=check, align=align)
            boxes.append(g.box)
        if self.boxed:
            box_rect(sh, cx, ymid - self.up, cx + self.mw + 2 * self.pad, ymid + self.text_bottom,
                     w=sh.st("thin"), owner=owner)
        if self.flags_after:
            fx = cx + self.mw + 2 * self.pad + self.fgap
            for n in self.flags_after:
                wbox = flag(sh, n, fx, ymid, self.fh, owner=owner, shape=self.flag_shape)
                fx += wbox + 0.6 * self.fh
        if self.label:
            la = label_align or anchor
            ly = ymid + self.text_bottom + self.lgap
            if la == "start":
                lx, lanchor = x0, "start"
            elif la == "end":
                lx, lanchor = x0 + self.w_main, "end"
            else:
                lx, lanchor = x0 + self.w_main / 2, "middle"
            g = text(sh, self.label, lx, ly, self.hl, anchor=lanchor, valign="top", owner=owner,
                     check=check)
            boxes.append(g.box)
        return boxes


def block_box(blk, x, ymid, anchor="middle", label_align=None, pad=0.0):
    if anchor == "start":
        x0 = x
    elif anchor == "end":
        x0 = x - blk.w_main
    else:
        x0 = x - blk.w_main / 2
    x1 = x0 + blk.w_main
    if blk.label:
        la = label_align or anchor
        if la == "start":
            lx0, lx1 = x0, x0 + blk.lw
        elif la == "end":
            lx0, lx1 = x1 - blk.lw, x1
        else:
            lx0, lx1 = (x0 + x1) / 2 - blk.lw / 2, (x0 + x1) / 2 + blk.lw / 2
        x0, x1 = min(x0, lx0), max(x1, lx1)
    return (x0 - pad, ymid - blk.up - pad, x1 + pad, ymid + blk.down + pad)


def _best(cands, score_fn, pref):
    best = None
    for c in cands:
        sc = score_fn(c)
        key = (round(sc, 3), abs(c - pref))
        if best is None or key < best[0]:
            best = (key, c)
        if sc == 0 and c == pref:
            break
    return best[1]


def _cands(pref, lo, hi, step):
    out = [pref]
    if hi <= lo or step <= 0:
        return out
    k = 1
    while True:
        added = False
        for c in (pref - k * step, pref + k * step):
            if lo <= c <= hi:
                out.append(c)
                added = True
        if not added:
            break
        k += 1
    return out


def compose(value_text, prefix="", suffix="", ref=False):
    s = value_text
    if prefix:
        s = f"{prefix} {s}" if not prefix.endswith((" ", "Ø", "R", "⌀")) else prefix + s
    if suffix:
        s = s + (suffix if suffix.startswith(" ") else " " + suffix)
    if ref:
        s = f"({s})"
    return s


# ---- linear dimension -------------------------------------------------------------

def linear(sh, p1, p2, axis, offset, main, *, label=None, place="auto", side=None,
           text_shift=(0.0, 0.0), arrows="open", owner=None, basic=False, hint_center=None,
           ext=(True, True), flags=(), ref_pts=()):
    """p1, p2: sheet points. axis: 'h' | 'v' | 'a' (aligned). offset: sheet mm
    from the outermost point to the dimension line (sign picks the side:
    h: + above / - below, v: + right / - left, a: + paper-left of p1->p2)."""
    g = sh.st("text_gap")
    La = sh.st("arrow_len")
    if axis == "h":
        u = (1.0, 0.0)
        n = (0.0, -1.0) if offset >= 0 else (0.0, 1.0)
    elif axis == "v":
        u = (0.0, 1.0)
        n = (1.0, 0.0) if offset >= 0 else (-1.0, 0.0)
    else:
        u = unit(sub(p2, p1))
        left = (u[1], -u[0])
        n = left if offset >= 0 else (-left[0], -left[1])
    level = max([dot(p1, n), dot(p2, n)] + [dot(q, n) for q in ref_pts]) + abs(offset)
    D1 = add(p1, mul(n, level - dot(p1, n)))
    D2 = add(p2, mul(n, level - dot(p2, n)))
    if dot(sub(D2, D1), u) < 0:
        D1, D2 = D2, D1
        p1, p2 = p2, p1
        ext = (ext[1], ext[0])
    gap, over = sh.st("ext_gap"), sh.st("ext_over")
    for P, D, e in ((p1, D1, ext[0]), (p2, D2, ext[1])):
        dd = dist(P, D)
        if e and dd > gap + 0.05:
            line(sh, add(P, mul(n, gap)), add(D, mul(n, over)), owner=owner)
            # finished at render time: snapped to the real edge if P is off the geometry
            sh.ext_lines.append((sh.items[-1], P, D, n, gap, over, str(owner).split(":")[0], owner))
    inner = dist(D1, D2)
    blk = Block(sh, main, label=label, flags=flags, boxed=basic)
    if axis == "v":
        need = blk.up + blk.down + 2 * g
    elif axis == "h":
        need = blk.w_main + 2 * g
    else:
        need = _break_len(blk, u) + 2 * g
    mid = mul(add(D1, D2), 0.5)
    if place == "auto":
        if inner >= need + 2 * La + 4.0:
            place = "inside"
        else:
            place = "outside"
    auto_side = side is None
    if side is None:
        side = "end"
        if hint_center is not None:
            side = "start" if dot(sub(mid, hint_center), u) < 0 else "end"
            if axis == "v":
                side = "start" if mid[0] < hint_center[0] else "end"
    if place == "inside":
        arrow(sh, D1, sub(D1, D2), arrows, owner)
        arrow(sh, D2, sub(D2, D1), arrows, owner)
        a1 = add(D1, mul(u, La if arrows in ("open", "filled") else 0))
        a2 = sub(D2, mul(u, La if arrows in ("open", "filled") else 0))
        tm = add(mid, text_shift)
        auto = abs(text_shift[0]) < 1e-9 and abs(text_shift[1]) < 1e-9
        if auto and axis == "v":
            lo = D1[1] + La + g + blk.up
            hi = D2[1] - La - g - blk.down
            step = (blk.up + blk.down) * 0.4 + 0.5
            ym = _best(_cands(mid[1], lo, hi, step),
                       lambda c: clutter(sh, block_box(blk, mid[0], c, "middle", pad=g * 0.5), owner),
                       mid[1])
            tm = (mid[0], ym)
        elif auto and axis == "h":
            lo = D1[0] + La + g + blk.w / 2
            hi = D2[0] - La - g - blk.w / 2
            step = max(1.0, blk.w * 0.25)
            xm = _best(_cands(mid[0], lo, hi, step),
                       lambda c: clutter(sh, block_box(blk, c, mid[1], "middle", pad=g * 0.5), owner),
                       mid[0])
            tm = (xm, mid[1])
        if axis == "v":
            ymid = tm[1]
            b0 = ymid - blk.up - g
            b1 = ymid + blk.down + g
            if b0 > a1[1]:
                line(sh, a1, (D1[0], b0), owner=owner)
            if b1 < a2[1]:
                line(sh, (D1[0], b1), a2, owner=owner)
            blk.draw(tm[0], ymid, "middle", owner=owner)
        elif axis == "h":
            b0 = tm[0] - blk.w_main / 2 - g
            b1 = tm[0] + blk.w_main / 2 + g
            if b0 > a1[0]:
                line(sh, a1, (b0, D1[1]), owner=owner)
            if b1 < a2[0]:
                line(sh, (b1, D1[1]), a2, owner=owner)
            blk.draw(tm[0], D1[1] + text_shift[1], "middle", owner=owner)
        else:
            half = _break_len(blk, u) / 2 + g
            t = dot(sub(tm, D1), u)
            line(sh, a1, add(D1, mul(u, t - half)), owner=owner)
            line(sh, add(D1, mul(u, t + half)), a2, owner=owner)
            blk.draw(tm[0], tm[1], "middle", owner=owner)
        return
    # outside: arrows outside pointing in, unless there is room for them inside
    arrows_in = inner >= 2 * La + 2.0
    tail = sh.st("arrow_tail")
    if arrows_in:
        arrow(sh, D1, sub(D1, D2), arrows, owner)
        arrow(sh, D2, sub(D2, D1), arrows, owner)
        line(sh, add(D1, mul(u, La)), sub(D2, mul(u, La)), owner=owner)
    else:
        arrow(sh, D1, u, arrows, owner)
        arrow(sh, D2, mul(u, -1), arrows, owner)
        line(sh, D1, D2, owner=owner)
    if auto_side:
        side = _pick_side(sh, blk, axis, side, D1, D2, mid, u, arrows_in, La, tail, g, owner,
                          text_shift)
    if axis == "h" or axis == "a":
        if side == "start":
            end_pt, dirv = D1, mul(u, -1)
        else:
            end_pt, dirv = D2, u
        reach = (0 if arrows_in else La) + tail
        stub_end = add(end_pt, mul(dirv, reach))
        if not arrows_in:
            other = D2 if side == "start" else D1
            line(sh, sub(other, mul(dirv, La + tail * 0.6)), sub(other, mul(dirv, La)), owner=owner)
        line(sh, add(end_pt, mul(dirv, 0 if arrows_in else La)), stub_end, owner=owner)
        tp = add(add(stub_end, mul(dirv, g)), text_shift)
        anchor = "start" if dirv[0] >= 0 else "end"
        if abs(text_shift[1]) > 1e-6:
            # dog-leg: shoulder at the text height
            elbow = (tp[0] - (g if anchor == "start" else -g), tp[1])
            line(sh, stub_end, elbow, owner=owner)
        blk.draw(tp[0], tp[1], anchor, owner=owner, label_align=anchor)
    else:  # vertical dimension, horizontal text beside it with a leader
        if not arrows_in:
            line(sh, sub(D1, mul(u, La + tail)), sub(D1, mul(u, La)), owner=owner)
            line(sh, add(D2, mul(u, La)), add(D2, mul(u, La + tail)), owner=owner)
        sgn = -1 if side == "start" else 1
        ty = mid[1] + text_shift[1]
        lead = sh.st("leader_len")
        tx = D1[0] + sgn * lead + text_shift[0]
        anchor = "end" if sgn < 0 else "start"
        # leader: from the text to the dimension line; dog-leg if text is outside the span
        y_hit = min(max(ty, D1[1]), D2[1])
        if abs(y_hit - ty) < 1e-6:
            line(sh, (tx - sgn * 0 + sgn * 0, ty), (D1[0], ty), owner=owner)
        else:
            elbow_x = D1[0] + sgn * min(lead * 0.4, abs(tx - D1[0]) * 0.5)
            polyline(sh, [(tx, ty), (elbow_x, ty), (D1[0], y_hit)], owner=owner)
        blk.draw(tx + sgn * g, ty, anchor, owner=owner, label_align=anchor)


def _pick_side(sh, blk, axis, pref, D1, D2, mid, u, arrows_in, La, tail, g, owner, shift):
    scores = {}
    for side in ("start", "end"):
        if axis in ("h", "a"):
            end_pt, dirv = (D1, mul(u, -1)) if side == "start" else (D2, u)
            stub_end = add(end_pt, mul(dirv, (0 if arrows_in else La) + tail))
            tp = add(add(stub_end, mul(dirv, g)), shift)
            anchor = "start" if dirv[0] >= 0 else "end"
            box = block_box(blk, tp[0], tp[1], anchor, anchor, pad=g * 0.5)
        else:
            sgn = -1 if side == "start" else 1
            tx = D1[0] + sgn * sh.st("leader_len") + shift[0] + sgn * g
            anchor = "end" if sgn < 0 else "start"
            box = block_box(blk, tx, mid[1] + shift[1], anchor, anchor, pad=g * 0.5)
        scores[side] = clutter(sh, box, owner) + (0 if side == pref else 0.5)
    return min(scores, key=scores.get)


def _break_len(blk, u):
    w, hgt = blk.w_main, blk.up * 2
    ux, uy = abs(u[0]), abs(u[1])
    cands = []
    if ux > 1e-6:
        cands.append(w / ux)
    if uy > 1e-6:
        cands.append(hgt / uy)
    return min(cands) if cands else w


# ---- leaders & callouts -----------------------------------------------------------

def _text_hits(sh, a, b, owner):
    n = 0
    bb = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
    for it in sh.items:
        if it["t"] != "text" or it.get("owner") == owner:
            continue
        ib = _item_bb(it)
        if ib and box_overlap(ib, bb) and seg_hits_box(a, b, ib):
            n += 1
    return n


def place_leader(sh, target, elbow, blk, shoulder, owner, direction=None, search=True):
    """Pick an elbow near the requested one whose text and leader land in a
    clear area. Returns (elbow, direction)."""
    g = sh.st("text_gap")

    def score(E, dirn, pen):
        se = (E[0] + dirn * shoulder, E[1])
        anchor = "start" if dirn > 0 else "end"
        box = block_box(blk, se[0] + dirn * g, E[1], anchor, anchor, pad=g * 0.6)
        return (clutter(sh, box, owner) + 6 * _text_hits(sh, target, E, owner)
                + 6 * _text_hits(sh, E, se, owner) + pen)

    d0 = direction if direction is not None else (1 if elbow[0] >= target[0] else -1)
    best = (score(elbow, d0, 0.0), elbow, d0)
    if not search or best[0] == 0:
        return best[1], best[2]
    dx, dy = elbow[0] - target[0], elbow[1] - target[1]
    for k, ddy in enumerate((-5, 5, -10, 10, -15, 15, -22, 22)):
        for mirror in (False, True):
            if mirror and direction is not None:
                continue
            E = (target[0] - dx if mirror else elbow[0], elbow[1] + ddy)
            dirn = (-d0 if mirror else d0)
            pen = 0.3 + 0.04 * abs(ddy) + (1.5 if mirror else 0.0)
            sc = score(E, dirn, pen)
            if sc < best[0]:
                best = (sc, E, dirn)
    return best[1], best[2]


def leader(sh, target, elbow, main, *, label=None, flags=(), flag_shape="box", arrows="open",
           owner=None, shoulder=None, direction=None, h=None, boxed=False, label_align=None,
           text_check=True, auto=False, flags_after=(), also=()):
    """Leader from text to target. `elbow` is where the slanted leg meets the
    horizontal shoulder; text follows the shoulder. auto=True moves the elbow
    (up/down, or to the mirrored side) if the requested spot is cluttered.
    also: more target points that get their own leg from the same elbow."""
    shoulder = sh.st("shoulder") if shoulder is None else shoulder
    blk = Block(sh, main, label=label, flags=flags, flag_shape=flag_shape, h=h, boxed=boxed,
                flags_after=flags_after)
    if auto:
        elbow, direction = place_leader(sh, target, elbow, blk, shoulder, owner, direction)
    if direction is None:
        direction = 1 if elbow[0] >= target[0] else -1
    for t2 in also:
        if dist(t2, elbow) > 1e-6:
            stop = arrow(sh, t2, sub(t2, elbow), arrows, owner)
            line(sh, elbow, stop, owner=owner)
    tip_dir = sub(target, elbow)
    if dist(target, elbow) > 1e-6:
        stop = arrow(sh, target, tip_dir, arrows, owner)
        line(sh, elbow, stop, owner=owner)
    shoulder_end = (elbow[0] + direction * shoulder, elbow[1])
    if shoulder > 0:
        line(sh, elbow, shoulder_end, owner=owner)
    g = sh.st("text_gap")
    anchor = "start" if direction > 0 else "end"
    blk.draw(shoulder_end[0] + direction * g, elbow[1], anchor, owner=owner,
             label_align=label_align or anchor, check=text_check)
    return blk


# ---- ordinates --------------------------------------------------------------------

def spread(desired, min_sep):
    """Move sorted 1-D positions apart to at least min_sep with the least squared
    displacement, keeping their order (isotonic regression on d_k - k*sep)."""
    blocks = []  # [sum, count]
    for k, d in enumerate(desired):
        blocks.append([d - k * min_sep, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s_, c_ = blocks.pop()
            blocks[-1][0] += s_
            blocks[-1][1] += c_
    out = []
    k = 0
    for s_, c_ in blocks:
        m = s_ / c_
        for _ in range(c_):
            out.append(m + k * min_sep)
            k += 1
    return out


def ordinate_set(sh, axis, feats, col, sgn, *, owner_prefix="ord", jog=None, mark=None,
                 gap=None, h=None):
    """feats: list of (sheet_point, text, flags). axis 'y': leaders horizontal,
    column at x=col, texts toward sgn (-1 left, +1 right). axis 'x': leaders
    vertical, column at y=col, sgn -1 up, +1 down; text rotated 90."""
    h = sh.st("dim_text") if h is None else h
    gap = sh.st("ext_gap") if gap is None else gap
    jog = sh.st("ord_jog") if jog is None else jog
    min_sep = h * (1.95 if any(f[2] for f in feats) else 1.55)
    k = 1 if axis == "y" else 0  # coordinate index that the spread acts on
    want = [f[0][k] + (f[3] if len(f) > 3 else 0.0) for f in feats]
    order = sorted(range(len(feats)), key=lambda i: want[i])
    desired = [want[i] for i in order]
    placed = spread(desired, min_sep)
    tg = sh.st("text_gap")
    for idx, pos in zip(order, placed):
        P, s, boxed = feats[idx][:3]
        owner = f"{owner_prefix}:{s}@{P[0]:.0f},{P[1]:.0f}"
        if axis == "y":
            start = (P[0] + sgn * gap, P[1]) if (abs(col - P[0]) > gap and not boxed) else P
            if abs(pos - P[1]) < 1e-6:
                line(sh, start, (col, P[1]), owner=owner)
            else:
                xa = col - sgn * jog
                xb = col - sgn * jog * 0.45
                polyline(sh, [start, (xa, P[1]), (xb, pos), (col, pos)], owner=owner)
            if mark == "tick":
                _cross(sh, P, owner)
            blk = Block(sh, s, boxed=boxed, h=h)
            blk.draw(col + sgn * tg, pos, "start" if sgn > 0 else "end", owner=owner)
        else:
            start = (P[0], P[1] + sgn * gap) if (abs(col - P[1]) > gap and not boxed) else P
            if abs(pos - P[0]) < 1e-6:
                line(sh, start, (P[0], col), owner=owner)
            else:
                ya = col - sgn * jog
                yb = col - sgn * jog * 0.45
                polyline(sh, [start, (P[0], ya), (pos, yb), (pos, col)], owner=owner)
            if mark == "tick":
                _cross(sh, P, owner)
            # rotated text reading bottom-to-top; it extends away from the part
            anchor = "start" if sgn < 0 else "end"
            g = text(sh, s, pos, col + sgn * tg, h, anchor=anchor, valign="middle", rotate=90,
                     owner=owner)
            if boxed:
                p = h * 0.35
                xs = [q[0] for q in g.box]
                ys = [q[1] for q in g.box]
                box_rect(sh, min(xs) - p, min(ys) - p, max(xs) + p, max(ys) + p, owner=owner)


def _cross(sh, P, owner, r=0.9):
    line(sh, (P[0] - r, P[1]), (P[0] + r, P[1]), owner=owner)
    line(sh, (P[0], P[1] - r), (P[0], P[1] + r), owner=owner)


# ---- angles -----------------------------------------------------------------------

def angular(sh, vertex, a_start, a_end, radius, main, *, label=None, owner=None, arrows="open",
            rays=None, text_shift=(0.0, 0.0), text_radius=None):
    """Angular dimension: arc of `radius` (sheet mm) around vertex from paper
    angle a_start to a_end (degrees, CCW on paper; sweep a_start -> a_end CCW).
    rays: optional list of ray end distances (sheet mm) from the vertex for the
    two sides; extension lines are drawn from there out past the arc."""
    La = sh.st("arrow_len")
    span = (a_end - a_start) % 360.0
    if span == 0:
        span = 360.0

    def P(a, r=radius):
        t = math.radians(a)
        return (vertex[0] + r * math.cos(t), vertex[1] - r * math.sin(t))

    over = sh.st("ext_over")
    gap = sh.st("ext_gap")
    if rays:
        for a, rlen in ((a_start, rays[0]), (a_end, rays[1])):
            if rlen is not None and rlen + gap < radius:
                line(sh, P(a, rlen + gap), P(a, radius + over), owner=owner)
    arc_len = math.radians(span) * radius
    dA = math.degrees(La / radius)
    if arc_len > 2 * La + 1:
        # arrows inside, pointing outward along the tangent
        t0 = P(a_start)
        t1 = P(a_end)
        arrow(sh, t0, sub(t0, P(a_start + dA)), arrows, owner)
        arrow(sh, t1, sub(t1, P(a_end - dA)), arrows, owner)
        _arc(sh, vertex, radius, a_start + dA, a_end - dA, owner)
    else:
        t0 = P(a_start)
        t1 = P(a_end)
        arrow(sh, t0, sub(t0, P(a_start - dA)), arrows, owner)
        arrow(sh, t1, sub(t1, P(a_end + dA)), arrows, owner)
        _arc(sh, vertex, radius, a_start - 2.2 * dA, a_end + 2.2 * dA, owner)
    blk = Block(sh, main, label=label)
    tr0 = (radius + sh.st("text_gap") * 1.5) if text_radius is None else text_radius
    hx = blk.w / 2
    hy = (blk.up + blk.down) / 2

    def spot(am, tr):
        ca, sa = math.cos(math.radians(am)), math.sin(math.radians(am))
        c = P(am, tr)
        push = abs(ca) * hx + abs(sa) * hy  # nearest edge of the block clears the arc
        c = (c[0] + ca * push + text_shift[0], c[1] - sa * push + text_shift[1])
        return c[0], c[1] - (blk.down - blk.up) / 2

    am0 = a_start + span / 2
    best = None
    auto = abs(text_shift[0]) < 1e-9 and abs(text_shift[1]) < 1e-9
    cands = [(am0, tr0)]
    if auto:
        for f in (0.3, 0.7, 0.15, 0.85):
            cands.append((a_start + span * f, tr0))
        for extra in (6, 12, 20):
            cands += [(am0, tr0 + extra), (a_start + span * 0.3, tr0 + extra),
                      (a_start + span * 0.7, tr0 + extra)]
        # beyond either end of the arc (the arc is extended to the text)
        out = max(12.0, span * 0.45)
        for extra in (0, 8):
            cands += [(a_start - out, tr0 + extra), (a_end + out, tr0 + extra)]
    g = sh.st("text_gap")
    for i, (am, tr) in enumerate(cands):
        x, ym = spot(am, tr)
        sc = clutter(sh, block_box(blk, x, ym, "middle", pad=g * 0.5), owner) + 0.05 * i
        if best is None or sc < best[0]:
            best = (sc, x, ym, am, tr)
        if sc == 0:
            break
    _, x, ym, am, tr = best
    if am < a_start - 1e-6:
        _arc(sh, vertex, radius, am, a_start, owner)
    elif am > a_end + 1e-6:
        _arc(sh, vertex, radius, a_end, am, owner)
    if tr > tr0 + 1e-6:
        # text sits beyond the arc: a short radial leader ties it to the arc
        line(sh, P(am, radius), P(am, tr - sh.st("text_gap") * 0.5), owner=owner)
    blk.draw(x, ym, "middle", owner=owner)


def _arc(sh, c, r, a0, a1, owner, dash=None, w=None):
    # paper angles CCW -> sheet points
    n = max(2, int(abs(a1 - a0) / 3) + 2)
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((c[0] + r * math.cos(a), c[1] - r * math.sin(a)))
    p0, p1 = pts[0], pts[-1]
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 0 if a1 > a0 else 1
    d = (f"M{fmt(p0[0])} {fmt(p0[1])} A{fmt(r)} {fmt(r)} 0 {large} {sweep} "
         f"{fmt(p1[0])} {fmt(p1[1])}")
    sh.add_path(d, w=sh.st("thin") if w is None else w, dash=dash, lines=[pts], owner=owner,
                layer="annot")
