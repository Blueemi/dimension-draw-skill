"""Orthographic views: model-space geometry (mm, y up, origin wherever you like)
placed on the sheet at a scale, plus the dimensioning API.

Every dimension value is measured from the model coordinates you pass in, so
the numbers on the sheet always agree with the geometry that is drawn.
"""

import math

from . import annot
from .geom import (Path, Transform, circle_path, ellipse_path, hatch_segments, polygon_path,
                   rect_path, slot_path, dist, sub, add, mul, unit, fmt)


# Third-angle projection: which product axes become a view's model (x, y).
# Product axes: X right, Y up, Z out of the front face (toward the front-view viewer).
PROJECTION = {
    "front":  (("X", 1), ("Y", 1)),
    "back":   (("X", -1), ("Y", 1)),   # placed right of the right view
    "left":   (("Z", 1), ("Y", 1)),    # placed left of the front view
    "right":  (("Z", -1), ("Y", 1)),   # placed right of the front view
    "top":    (("X", 1), ("Z", -1)),   # placed above the front view
    "bottom": (("X", 1), ("Z", 1)),    # placed below the front view
}


def project(kind, p):
    """Product point (X, Y, Z) -> model (x, y) of a third-angle view `kind`."""
    idx = {"X": 0, "Y": 1, "Z": 2}
    (a, sa), (b, sb) = PROJECTION[kind]
    return (sa * p[idx[a]], sb * p[idx[b]])


class Shape:
    """A drawn shape with handy anchor points (model coordinates)."""

    def __init__(self, view, path, kind="path", **info):
        self.view = view
        self.path = path
        self.kind = kind
        self.__dict__.update(info)
        bb = path.bbox()
        if bb:
            self.left, self.bottom, self.right, self.top = bb
        else:
            self.left = self.bottom = self.right = self.top = 0.0

    # anchors
    @property
    def cx(self):
        return getattr(self, "_cx", (self.left + self.right) / 2)

    @property
    def cy(self):
        return getattr(self, "_cy", (self.bottom + self.top) / 2)

    @property
    def w(self):
        return self.right - self.left

    @property
    def h(self):
        return self.top - self.bottom

    @property
    def center(self):
        return (self.cx, self.cy)

    @property
    def tl(self):
        return (self.left, self.top)

    @property
    def tr(self):
        return (self.right, self.top)

    @property
    def bl(self):
        return (self.left, self.bottom)

    @property
    def br(self):
        return (self.right, self.bottom)

    @property
    def top_mid(self):
        return (self.cx, self.top)

    @property
    def bottom_mid(self):
        return (self.cx, self.bottom)

    @property
    def left_mid(self):
        return (self.left, self.cy)

    @property
    def right_mid(self):
        return (self.right, self.cy)

    def at(self, angle):
        """Point on a circle/ellipse/slot outline at `angle` degrees (CCW from +x)."""
        t = math.radians(angle)
        if self.kind == "circle":
            return (self.cx + self.r * math.cos(t), self.cy + self.r * math.sin(t))
        if self.kind == "ellipse":
            return (self.cx + self.rx * math.cos(t), self.cy + self.ry * math.sin(t))
        # generic: ray from center to bbox-inscribed ellipse
        return (self.cx + self.w / 2 * math.cos(t), self.cy + self.h / 2 * math.sin(t))

    def __repr__(self):
        return (f"<Shape {self.kind} x[{self.left:.3f},{self.right:.3f}] "
                f"y[{self.bottom:.3f},{self.top:.3f}]>")


def _pt(p):
    if isinstance(p, Shape):
        return p.center
    return (float(p[0]), float(p[1]))


class View:
    def __init__(self, sheet, x, y, scale, name):
        self.sheet = sheet
        self.tf = Transform(x, y, scale)
        self.x, self.y, self.scale = x, y, scale
        self.name = name
        self._geom_bb = None
        self.clip = None
        self._circles = []
        self.parent = None
        self.relation = None

    # ---- helpers ------------------------------------------------------------
    def _ready(self):
        """Called before every annotation: views generated from a model draw it
        now, so automatic placement sees the real geometry."""

    def _p2(self, p):
        """Any point argument (2-tuple, Shape) -> view model coordinates."""
        return _pt(p)

    def S(self, p):
        """Model point -> sheet point."""
        return self.tf.pt(self._p2(p))

    def M(self, q):
        """Sheet point -> model point."""
        return self.tf.inv(q)

    def set_clip_circle(self, cx, cy, r):
        """Only draw geometry inside this circle (model / view coordinates), to
        match a detail_circle. set_clip(None, None, None, None) clears it."""
        c = self.S((cx, cy))
        self.clip = ("circle", c[0], c[1], r * self.scale)

    def set_clip(self, x0, y0, x1, y1):
        """Only draw geometry inside this model-space box from now on (for
        enlarged detail views of part of an outline). clear with set_clip(None...)."""
        if x0 is None:
            self.clip = None
            return
        a, b = self.S((x0, y0)), self.S((x1, y1))
        self.clip = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    def _emit(self, path, style="visible", fill=None, check=True, color=None, kind="geom",
              what="geom"):
        sh = self.sheet
        w, dash = sh.linestyle(style)
        if style is None:
            w = 0
        lines = path.polylines(self.tf)
        d = path.svg(self.tf)
        if self.clip:
            lines = _clip_polylines(lines, self.clip)
            if not lines:
                return
            d = " ".join("M" + " L".join(f"{fmt(p[0])} {fmt(p[1])}" for p in pl) for pl in lines)
            fill = None
        sh.add_path(d, w=w, dash=dash, fill=fill, lines=lines,
                    owner=f"{self.name}:{what}", check=check, layer="geom", color=color, kind=kind)
        for pl in lines:
            for q in pl:
                self._grow_bb(q)

    def _grow_bb(self, q):
        if self._geom_bb is None:
            self._geom_bb = [q[0], q[1], q[0], q[1]]
        else:
            b = self._geom_bb
            b[0], b[1] = min(b[0], q[0]), min(b[1], q[1])
            b[2], b[3] = max(b[2], q[0]), max(b[3], q[1])

    def _hint(self):
        if self._geom_bb:
            b = self._geom_bb
            return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        return (self.tf.ox, self.tf.oy)

    def _owner(self, kind, s):
        return f"{self.name}:{kind} '{s}'#{self.sheet.uid('a')}"

    # ---- geometry ------------------------------------------------------------
    def rect(self, cx, cy, w, h, r=0.0, corner="circular", style="visible", fill=None):
        """Rectangle centered at (cx, cy). r: corner radius (or 4-tuple TL,TR,BR,BL).
        corner='continuous' for Apple-style continuous-curvature corners."""
        p = rect_path(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, r, corner)
        self._emit(p, style, fill, what="rect")
        return Shape(self, p, "rect", r=r, _cx=cx, _cy=cy)

    def box(self, x0, y0, x1, y1, r=0.0, corner="circular", style="visible", fill=None):
        """Rectangle from two opposite corners."""
        p = rect_path(x0, y0, x1, y1, r, corner)
        self._emit(p, style, fill, what="box")
        return Shape(self, p, "rect", r=r)

    def circle(self, cx, cy, d=None, r=None, style="visible", fill=None):
        r = d / 2 if r is None else r
        p = circle_path(cx, cy, r)
        self._emit(p, style, fill, what="circle")
        self._circles.append(2 * r)
        return Shape(self, p, "circle", r=r, d=2 * r, _cx=cx, _cy=cy)

    def ellipse(self, cx, cy, rx, ry, rot=0.0, style="visible", fill=None):
        p = ellipse_path(cx, cy, rx, ry, rot)
        self._emit(p, style, fill, what="ellipse")
        return Shape(self, p, "ellipse", rx=rx, ry=ry, _cx=cx, _cy=cy)

    def slot(self, cx, cy, length, width, angle=0.0, style="visible", fill=None):
        """Stadium (button / port / pill): overall length along `angle` degrees
        (0 = horizontal, 90 = vertical) and full width."""
        p = slot_path(cx, cy, length, width, angle)
        self._emit(p, style, fill, what="slot")
        return Shape(self, p, "slot", length=length, width=width, _cx=cx, _cy=cy)

    def polygon(self, pts, fillet=0.0, style="visible", fill=None):
        p = polygon_path(pts, fillet, closed=True)
        self._emit(p, style, fill, what="polygon")
        return Shape(self, p, "polygon")

    def polyline(self, pts, fillet=0.0, style="visible"):
        p = polygon_path(pts, fillet, closed=False)
        self._emit(p, style, what="polyline")
        return Shape(self, p, "polyline")

    def line(self, p1, p2, style="visible"):
        p = Path().move_to(self._p2(p1)).line_to(self._p2(p2))
        self._emit(p, style, what="line")
        return Shape(self, p, "line")

    def arc(self, cx, cy, r, a0, a1, style="visible"):
        p = Path().arc((cx, cy), r, a0, a1)
        self._emit(p, style, what="arc")
        return Shape(self, p, "arc", r=r, _cx=cx, _cy=cy)

    def path(self, path, style="visible", fill=None):
        """Draw a geom.Path built in model coordinates."""
        self._emit(path, style, fill, what="path")
        return Shape(self, path, "path")

    def shape(self, shape, style="visible", fill=None, dx=0.0, dy=0.0):
        """Redraw an existing shape's outline (optionally offset) in another style."""
        p = shape.path
        if dx or dy:
            q = Path()
            for seg in p.segs:
                q.segs.append(_shift_seg(seg, dx, dy))
            p = q
        self._emit(p, style, fill)
        return Shape(self, p, shape.kind)

    def hatch(self, shapes, angle=45.0, spacing=None, cross=False, holes=(), style="thin",
              fill=None, color=None, within=None):
        """Section/keep-out hatching clipped to shapes (even-odd with holes).
        spacing in sheet mm. cross=True adds the perpendicular family.
        within=(x0, y0, x1, y1): also clip to this model-space box, e.g. to
        hatch only the top band of an outline."""
        sh = self.sheet
        if isinstance(shapes, Shape):
            shapes = [shapes]
        if isinstance(holes, Shape):
            holes = [holes]
        rings = []
        for s in list(shapes) + list(holes):
            rings.extend(s.path.polylines(self.tf, tol=0.01))
        sp = sh.st("hatch_spacing") if spacing is None else spacing
        w, dash = sh.linestyle(style)
        if fill:
            d = " ".join(s.path.svg(self.tf) for s in list(shapes) + list(holes))
            sh.items.append({"t": "path", "d": d, "w": 0, "dash": None, "fill": fill,
                             "lines": None, "owner": f"{self.name}:hatch", "check": False,
                             "layer": "geom", "color": None, "join": "round", "cap": None,
                             "kind": "fill", "rule": "evenodd"})
        segs = hatch_segments(rings, angle, sp)
        if cross:
            segs += hatch_segments(rings, angle + 90, sp)
        if self.clip:
            segs = [c for c in (_clip_seg(a, b, self.clip) for a, b in segs) if c]
        if within:
            p0, p1 = self.S((within[0], within[1])), self.S((within[2], within[3]))
            wb = (min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]))
            segs = [c for c in (_clip_seg(a, b, wb) for a, b in segs) if c]
        if not segs:
            return
        d = " ".join(f"M{fmt(a[0])} {fmt(a[1])} L{fmt(b[0])} {fmt(b[1])}" for a, b in segs)
        sh.add_path(d, w=w, dash=dash, lines=[[a, b] for a, b in segs],
                    owner=f"{self.name}:hatch#{sh.uid('h')}", check=True, layer="geom",
                    color=color, kind="hatch", cap="butt")
        sh.items[-1]["rings"] = rings

    def text(self, s, x, y, h=None, anchor="middle", valign="middle", rotate=0.0, mask=False):
        """Text placed at a model point (size in sheet mm)."""
        q = self.S((x, y))
        return annot.text(self.sheet, s, q[0], q[1], h, anchor, valign, rotate,
                          owner=self._owner("text", s), mask=mask)

    # ---- dimensions ------------------------------------------------------------
    def _value_text(self, value, text, prefix, suffix, ref, decimals, owner, verify, sym=""):
        if text is not None:
            if verify:
                self.sheet.verify.append((owner, text, value, decimals))
            return text
        return annot.compose(sym + annot.fmt_num(value, decimals), prefix, suffix, ref)

    def dim(self, p1, p2, axis="h", offset=10.0, text=None, prefix="", suffix="", label=None,
            reference=False, basic=False, decimals=2, place="auto", side=None, shift=(0.0, 0.0),
            arrows="open", flags=(), verify=True, ext=(True, True), ref=None, snap=True,
            overall=None):
        """Linear dimension between model points.
        axis: 'h' horizontal distance, 'v' vertical distance, 'a' aligned (true length).
        offset: sheet mm from the outermost point to the dimension line
                ('h': + above / - below, 'v': + right / - left).
        text: replace the value text (cross-checked against the geometry unless verify=False).
        prefix: '2X', '4X', ... label: small caption under the value ('PRODUCT\\nWIDTH').
        reference: parentheses (reference dim). basic: boxed. place: auto|inside|outside.
        side: where outside text goes ('start' = left/top, 'end' = right/bottom).
        shift: (dx, dy) sheet-mm nudge of the text (dy + is down).
        ref: Shape or list of model points; offset is then measured from the
             outermost of these instead of from p1/p2 (use it to stack dims
             at fixed distances from a part outline).
        overall: the checker compares a dimension with the drawn extent when its
             label says OVERALL or PRODUCT WIDTH/LENGTH/...; overall=False skips
             that (a vehicle's overall width excludes mirrors), True forces it."""
        if getattr(self, "pictorial", False):
            raise ValueError(f"view '{self.name}' is pictorial (iso): lengths there are foreshortened, "
                             "so dimensions would be wrong. Dimension a sh.model_view(...) of the "
                             "same model instead.")
        a, b = self._p2(p1), self._p2(p2)
        if axis == "h":
            value = abs(b[0] - a[0])
        elif axis == "v":
            value = abs(b[1] - a[1])
        else:
            value = dist(a, b)
        owner = self._owner("dim", text or annot.fmt_num(value, decimals))
        main = self._value_text(value, text, prefix, suffix, reference, decimals, owner, verify)
        if snap and axis in ("h", "v"):
            self.sheet.dim_points.append((self, owner, axis, self.S(a), self.S(b), main, label or "",
                                          overall))
        self.sheet.flags_used.update(flags)
        ref_pts = ()
        if isinstance(ref, Shape):
            ref_pts = [self.S(q) for q in (ref.tl, ref.tr, ref.bl, ref.br)]
        elif ref is not None:
            ref_pts = [self.S(q) for q in ref]
        annot.linear(self.sheet, self.S(a), self.S(b), axis, offset, main, label=label,
                     place=place, side=side, text_shift=shift, arrows=arrows, owner=owner,
                     basic=basic, hint_center=self._hint(), ext=ext, flags=flags,
                     ref_pts=ref_pts)
        if getattr(self, "_rendered", False):
            self.sheet._snap_ext_lines(only=self.name)
        return value

    def dim_h(self, p1, p2, offset=10.0, **kw):
        return self.dim(p1, p2, "h", offset, **kw)

    def dim_v(self, p1, p2, offset=10.0, **kw):
        return self.dim(p1, p2, "v", offset, **kw)

    def dim_aligned(self, p1, p2, offset=10.0, **kw):
        return self.dim(p1, p2, "a", offset, **kw)

    def dim_chain(self, pts, axis="h", offset=10.0, **kw):
        """Consecutive dimensions along one line. reference, label, text, place,
        side and verify may be lists with one entry per span, e.g.
        reference=[True, False, True] for estimated overhangs around a published
        wheelbase. Returns the values."""
        n = len(pts) - 1
        per = {k: kw.pop(k) for k in ("reference", "label", "text", "place", "side", "verify")
               if isinstance(kw.get(k), (list, tuple))}
        for k, v in per.items():
            if len(v) != n:
                raise ValueError(f"dim_chain: {k} has {len(v)} entries for {n} spans")
        out = []
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            out.append(self.dim(a, b, axis, offset, **kw, **{k: v[i] for k, v in per.items()}))
        return out

    def dim_baseline(self, base, pts, axis="v", offset=10.0, step=9.0, **kw):
        """Stacked dimensions all measured from one base point; the nearest
        point gets the innermost line."""
        b = self._p2(base)
        k = 0 if axis == "h" else 1
        order = sorted(pts, key=lambda p: abs(self._p2(p)[k] - b[k]))
        sgn = 1 if offset >= 0 else -1
        for i, p in enumerate(order):
            self.dim(b, p, axis, offset + sgn * step * i, **kw)

    # ---- ordinate dimensions ------------------------------------------------------
    def _ord_items(self, pts, k, datum, decimals, show_datum, datum_pt, datum_shift=0.0):
        feats = []
        for p in pts:
            prefix = ""
            if isinstance(p, (tuple, list)) and len(p) == 3:
                prefix = p[2]
                p = (p[0], p[1])
            p = self._p2(p)
            v = p[k] - datum
            s = annot.fmt_num(v, decimals)
            if prefix:
                s = f"{prefix} {s}"
            feats.append((self.S(p), s, False))
        if show_datum and datum_pt is not None:
            feats.append((self.S(datum_pt), annot.fmt_num(0.0, decimals), True, datum_shift))
        return feats

    def ordinate_y(self, pts, datum=0.0, ref=None, offset=-10.0, decimals=2, datum_at=None,
                   jog=None, mark=None, gap=None, datum_shift=0.0):
        """Ordinate values of model y (relative to datum) with horizontal leaders
        to a text column offset sheet mm from ref (+ right / - left). ref: model x
        or a Shape (its left/right edge is used). pts: (x, y) or (x, y, '2X').
        datum_at: model point where the boxed 0.00 datum leader starts.
        datum_shift: sheet mm to slide the datum box along its column (+ up for
        ordinate_y, + right for ordinate_x); its leader then jogs, like Apple's
        slanted datum leaders. mark='tick' puts a small + on each feature point."""
        if getattr(self, "pictorial", False):
            raise ValueError(f"view '{self.name}' is pictorial (iso): measure on a sh.model_view(...) instead.")
        xs = [(self._p2(p)[0]) for p in pts] + ([datum_at[0]] if datum_at else [])
        refx = _ref(ref, xs, offset, "x")
        col = self.S((refx, 0))[0] + offset
        feats = self._ord_items(pts, 1, datum, decimals, datum_at is not None, datum_at,
                                -datum_shift)
        annot.ordinate_set(self.sheet, "y", feats, col, 1 if offset > 0 else -1,
                           owner_prefix=f"{self.name}:ord", jog=jog, mark=mark, gap=gap)

    def ordinate_x(self, pts, datum=0.0, ref=None, offset=10.0, decimals=2, datum_at=None,
                   jog=None, mark=None, gap=None, datum_shift=0.0):
        """Ordinate values of model x with vertical leaders to a row of rotated
        text offset sheet mm from ref (+ above / - below)."""
        if getattr(self, "pictorial", False):
            raise ValueError(f"view '{self.name}' is pictorial (iso): measure on a sh.model_view(...) instead.")
        ys = [(self._p2(p)[1]) for p in pts] + ([datum_at[1]] if datum_at else [])
        refy = _ref(ref, ys, offset, "y")
        col = self.S((0, refy))[1] - offset
        feats = self._ord_items(pts, 0, datum, decimals, datum_at is not None, datum_at,
                                datum_shift)
        annot.ordinate_set(self.sheet, "x", feats, col, -1 if offset > 0 else 1,
                           owner_prefix=f"{self.name}:ord", jog=jog, mark=mark, gap=gap)

    def datum_y(self, at, ref=None, offset=-10.0, label="0.00"):
        """Boxed datum for a horizontal datum line through model point `at`."""
        refx = _ref(ref, [self._p2(at)[0]], offset, "x")
        col = self.S((refx, 0))[0] + offset
        annot.ordinate_set(self.sheet, "y", [(self.S(at), label, True)], col,
                           1 if offset > 0 else -1, owner_prefix=f"{self.name}:datum")

    def datum_x(self, at, ref=None, offset=10.0, label="0.00"):
        """Boxed datum for a vertical datum line through model point `at`."""
        refy = _ref(ref, [self._p2(at)[1]], offset, "y")
        col = self.S((0, refy))[1] - offset
        annot.ordinate_set(self.sheet, "x", [(self.S(at), label, True)], col,
                           -1 if offset > 0 else 1, owner_prefix=f"{self.name}:datum")

    # ---- callouts --------------------------------------------------------------
    def callout(self, target, text, dx=10.0, dy=6.0, label=None, flags=(), arrow="open",
                hexflags=False, shoulder=None, boxed=False, h=None, auto=True, at=None,
                flags_after=(), also=()):
        """Leader note. target: model point. (dx, dy): sheet-mm offset from the
        target to the elbow (dy + is up). The text follows a short shoulder.
        arrow: open | filled | dot | none. Text uses the callout size unless h
        is given (use sheet.st('dim_text') for values). auto: if that spot is
        cluttered, slide the elbow up/down (or mirror it) to a clear one.
        at=(x, y): put the elbow at this sheet position instead (no auto).
        flags_after=[5]: flag boxes after the text ("Ø27.30 [5]").
        also=[pt, ...]: more model targets, each with its own leg from the elbow.
        shoulder: length of the horizontal stub before the text (sheet mm).
        Multi-line text ("\n") hangs from its first line."""
        T = self.S(target)
        sh = self.sheet
        sh.flags_used.update(flags)
        sh.flags_used.update(flags_after)
        elbow = (T[0] + dx, T[1] - dy) if at is None else tuple(at)
        auto = auto and at is None
        owner = self._owner("note", text)
        annot.leader(sh, T, elbow, text, label=label, flags=flags, arrows=arrow,
                     owner=owner, flag_shape="hex" if hexflags else "box", shoulder=shoulder,
                     boxed=boxed, h=sh.st("callout_text") if h is None else h, auto=auto,
                     flags_after=flags_after, also=[self.S(q) for q in also])

    def diameter(self, circle, angle=45.0, length=10.0, prefix="", flags=(), label=None,
                 text=None, decimals=2, arrow="open", verify=True, dy=None, auto=True, at=None,
                 flags_after=()):
        """Ø callout on a circle Shape: leader touching the circle at `angle`,
        running `length` sheet mm (dy overrides its rise). at=(x, y): put the
        elbow at this sheet position instead."""
        T = circle.at(angle)
        Ts = self.S(T)
        t = math.radians(angle)
        elbow = (Ts[0] + math.cos(t) * length, Ts[1] - (math.sin(t) * length if dy is None else dy))
        if at is not None:
            elbow, auto = tuple(at), False
        owner = self._owner("dia", text or annot.fmt_num(circle.d, decimals))
        main = self._value_text(circle.d, text, prefix, "", False, decimals, owner, verify,
                                sym="Ø")
        self.sheet.counts.append((self, owner, prefix, circle.d))
        self.sheet.flags_used.update(flags)
        self.sheet.flags_used.update(flags_after)
        annot.leader(self.sheet, Ts, elbow, main, label=label, flags=flags, arrows=arrow,
                     owner=owner, auto=auto, flags_after=flags_after)
        return circle.d

    def radius(self, center, r, angle=45.0, length=10.0, prefix="", flags=(), label=None,
               text=None, decimals=2, arrow="open", verify=True, reference=False, auto=True,
               at=None, flags_after=()):
        """R callout: leader touching the arc of radius r around center at `angle`."""
        c = self._p2(center)
        T = (c[0] + r * math.cos(math.radians(angle)), c[1] + r * math.sin(math.radians(angle)))
        Ts = self.S(T)
        t = math.radians(angle)
        elbow = (Ts[0] + math.cos(t) * length, Ts[1] - math.sin(t) * length)
        if at is not None:
            elbow, auto = tuple(at), False
        owner = self._owner("rad", text or annot.fmt_num(r, decimals))
        main = text
        if main is None:
            main = annot.compose("R" + annot.fmt_num(r, decimals), prefix, "", reference)
        elif verify:
            self.sheet.verify.append((owner, text, r, decimals))
        annot.leader(self.sheet, Ts, elbow, main, label=label, flags=flags, arrows=arrow,
                     owner=owner, auto=auto, flags_after=flags_after)
        return r

    def angle(self, vertex, p1, p2, r=15.0, text=None, decimals=0, label=None, reflex=False,
              ext=True, shift=(0.0, 0.0), verify=True, suffix=""):
        """Angular dimension between rays vertex->p1 and vertex->p2; r in sheet mm.
        ext=True draws extension lines where a ray ends short of the arc;
        ext="vertex" draws them from the vertex (use for a theoretical sharp
        corner hidden by a fillet); ext=False draws none."""
        if getattr(self, "pictorial", False):
            raise ValueError(f"view '{self.name}' is pictorial (iso): measure on a sh.model_view(...) instead.")
        V = self.S(vertex)
        A = self.S(p1)
        B = self.S(p2)
        aa = math.degrees(math.atan2(-(A[1] - V[1]), A[0] - V[0]))
        ab = math.degrees(math.atan2(-(B[1] - V[1]), B[0] - V[0]))
        sweep = (ab - aa) % 360
        a0, a1 = aa, ab
        if (sweep > 180) != reflex:
            a0, a1 = ab, aa
            sweep = 360 - sweep
        a1 = a0 + sweep
        owner = self._owner("ang", text or annot.fmt_num(sweep, decimals))
        if text is not None:
            if verify:
                self.sheet.verify.append((owner, text, sweep, decimals))
            main = text
        else:
            main = annot.fmt_num(sweep, decimals) + "°" + suffix
        rays = None
        if ext:
            rA, rB = dist(V, A), dist(V, B)
            if ext == "vertex":   # virtual (filleted) corner: extension lines from the vertex
                rA = rB = 0.0
            rays = (rA, rB) if a0 == aa else (rB, rA)
        annot.angular(self.sheet, V, a0, a1, r, main, label=label, owner=owner, rays=rays,
                      text_shift=shift)
        return sweep

    # ---- marks ------------------------------------------------------------------
    def center_mark(self, c, r=None, extend=2.0, cross=1.0, style="thin"):
        """Center cross with dashed center lines reaching `extend` sheet mm past
        the circle. c: Shape (circle) or model point (then pass r)."""
        sh = self.sheet
        if isinstance(c, Shape):
            r = getattr(c, "r", None) or max(c.w, c.h) / 2
            c = c.center
        C = self.S(c)
        R = (r or 0) * self.scale + extend
        w, _ = sh.linestyle(style)
        owner = f"{self.name}:center"
        cr = cross
        for dx, dy in ((1, 0), (0, 1)):
            annot.line(sh, (C[0] - dx * cr, C[1] - dy * cr), (C[0] + dx * cr, C[1] + dy * cr),
                       w=w, owner=owner, layer="cmask_lines", kind="centerline")
            for sgn in (1, -1):
                a = (C[0] + sgn * dx * cr * 1.6, C[1] + sgn * dy * cr * 1.6)
                b = (C[0] + sgn * dx * R, C[1] + sgn * dy * R)
                if dist(a, b) > 0.3:
                    annot.line(sh, a, b, w=w, dash=(2.6 * sh.k, 1.0 * sh.k), owner=owner,
                               layer="cmask_lines", kind="centerline")

    def centerline(self, p1, p2, extend=2.0, style="center"):
        """Chain center line through two model points, extended sheet mm."""
        sh = self.sheet
        A, B = self.S(p1), self.S(p2)
        u = unit(sub(B, A))
        e = extend
        w, dash = sh.linestyle(style)
        annot.line(sh, sub(A, mul(u, e)), add(B, mul(u, e)), w=w, dash=dash,
                   owner=f"{self.name}:centerline", layer="cmask_lines", kind="centerline")

    def construction_line(self, p1, p2, extend=0.0, style="thin"):
        """Thin line that is not part of the object: a ground line, a ramp line,
        a sight line, a reference plane seen edge-on. It doesn't widen the view,
        dimension and extension lines may start on it, and unlike a center line
        it is not broken behind text (the checker reports text it crosses).
        style: thin | phantom | hidden | center. Points are model points."""
        sh = self.sheet
        A, B = self.S(p1), self.S(p2)
        u = unit(sub(B, A))
        w, dash = sh.linestyle(style)
        annot.line(sh, sub(A, mul(u, extend)), add(B, mul(u, extend)), w=w, dash=dash,
                   owner=f"{self.name}:construction", layer="annot", kind="construction")

    def detail_circle(self, center, r, letter, angle=45.0, length=8.0):
        """Phantom circle (model radius r) marking a detail, with its letter."""
        sh = self.sheet
        sh.letters_used.append(("DETAIL", str(letter), self.name))
        c = self._p2(center)
        p = circle_path(c[0], c[1], r)
        w, dash = sh.linestyle("detail")
        owner = self._owner("detail", letter)
        sh.add_path(p.svg(self.tf), w=w, dash=dash, lines=p.polylines(self.tf), owner=owner,
                    layer="annot")
        T = self.S((c[0] + r * math.cos(math.radians(angle)), c[1] + r * math.sin(math.radians(angle))))
        self._detail_letter(T, angle, length, letter, owner)

    def detail_rect(self, x0, y0, x1, y1, letter, corner="tr", length=8.0):
        """Phantom rectangle marking a detail; the letter's leader leaves `corner`."""
        sh = self.sheet
        sh.letters_used.append(("DETAIL", str(letter), self.name))
        p = rect_path(x0, y0, x1, y1)
        w, dash = sh.linestyle("detail")
        owner = self._owner("detail", letter)
        sh.add_path(p.svg(self.tf), w=w, dash=dash, lines=p.polylines(self.tf), owner=owner,
                    layer="annot")
        xs = {"l": min(x0, x1), "r": max(x0, x1)}
        ys = {"b": min(y0, y1), "t": max(y0, y1)}
        T = self.S((xs[corner[1]], ys[corner[0]]))
        ang = {"tr": 45, "tl": 135, "bl": 225, "br": 315}[corner]
        self._detail_letter(T, ang, length, letter, owner)

    def _detail_letter(self, T, angle, d, letter, owner):
        sh = self.sheet
        t = math.radians(angle)
        elbow = (T[0] + math.cos(t) * d, T[1] - math.sin(t) * d)
        h = sh.st("dim_text") * 1.6
        annot.leader(sh, T, elbow, letter, arrows="open", owner=owner, h=h,
                     shoulder=sh.st("shoulder") * 1.4)

    def section_line(self, p1, p2, letter, look=(1.0, 0.0), arm=7.0):
        """Cutting-plane line p1->p2 (model) with view arrows pointing along
        `look` (model direction) and the section letter at both ends."""
        sh = self.sheet
        sh.letters_used.append(("SECTION", str(letter), self.name))
        A, B = self.S(p1), self.S(p2)
        u = unit(sub(B, A))
        L = unit((look[0], -look[1]))
        owner = self._owner("section", letter)
        w = sh.st("thick")
        e = 4.0 * sh.k
        annot.line(sh, A, B, w=sh.st("thin"), dash=sh.st("dash_phantom"), owner=owner)
        h = sh.st("dim_text") * 1.6
        for P, sgn in ((A, -1), (B, 1)):
            Q = add(P, mul(u, sgn * e))
            annot.line(sh, P, Q, w=w, owner=owner)
            tip = add(Q, mul(L, arm))
            stop = annot.arrow(sh, tip, L, "filled", owner)
            annot.line(sh, Q, stop, w=sh.st("thin"), owner=owner)
            lp = add(add(Q, mul(u, sgn * h * 0.9)), mul(L, arm * 0.55))
            annot.text(sh, letter, lp[0], lp[1], h, anchor="middle", valign="middle", owner=owner)

    def flag(self, n, x, y, hexagon=False):
        """Flag box at a model point (left edge)."""
        q = self.S((x, y))
        return annot.flag(self.sheet, n, q[0], q[1], owner=self._owner("flag", n),
                          shape="hex" if hexagon else "box")

    def projected(self, kind, at, name=None):
        """A new view in third-angle projection from this (front) view, same scale.
        kind: 'left' | 'right' | 'back' (at = sheet x of its model origin; shares
        this view's sheet y) or 'top' | 'bottom' (at = sheet y; shares sheet x).
        Draw in it with the axes from PROJECTION[kind]: e.g. in the left view
        model x = product Z, model y = product Y."""
        if kind in ("left", "right", "back"):
            v = self.sheet.view(at, self.tf.oy, self.scale, name or kind)
        elif kind in ("top", "bottom"):
            v = self.sheet.view(self.tf.ox, at, self.scale, name or kind)
        else:
            raise ValueError(f"unknown projection {kind!r}")
        v.parent, v.relation = self, kind
        return v

    def bounds(self):
        """Sheet bbox of the view's geometry (x0, y0, x1, y1)."""
        return tuple(self._geom_bb) if self._geom_bb else None


def _needs_geometry(fn):
    import functools

    @functools.wraps(fn)
    def method(self, *a, **kw):
        self._ready()
        return fn(self, *a, **kw)
    return method


for _n in ("dim", "ordinate_x", "ordinate_y", "datum_x", "datum_y", "callout", "diameter", "radius",
           "angle", "center_mark", "centerline", "construction_line", "detail_circle", "detail_rect",
           "section_line", "text", "flag"):
    setattr(View, _n, _needs_geometry(getattr(View, _n)))
del _n


def _clip_polylines(lines, box):
    if box and box[0] == "circle":
        return _clip_polylines_circle(lines, box[1:])
    x0, y0, x1, y1 = box
    out = []
    for pl in lines:
        cur = []
        for p, q in zip(pl, pl[1:]):
            seg = _clip_seg(p, q, box)
            if seg is None:
                if cur:
                    out.append(cur)
                    cur = []
                continue
            a, b = seg
            if cur and abs(cur[-1][0] - a[0]) + abs(cur[-1][1] - a[1]) < 1e-9:
                cur.append(b)
            else:
                if cur:
                    out.append(cur)
                cur = [a, b]
        if cur:
            out.append(cur)
    return out


def _clip_seg_circle(p, q, c):
    cx, cy, r = c
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - cx, p[1] - cy
    A = dx * dx + dy * dy
    if A < 1e-18:
        return (p, q) if fx * fx + fy * fy <= r * r else None
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - r * r
    disc = B * B - 4 * A * C
    if disc <= 0:
        return None
    sq = disc ** 0.5
    t0 = max(0.0, (-B - sq) / (2 * A))
    t1 = min(1.0, (-B + sq) / (2 * A))
    if t0 >= t1:
        return None
    return ((p[0] + dx * t0, p[1] + dy * t0), (p[0] + dx * t1, p[1] + dy * t1))


def _clip_polylines_circle(lines, c):
    out = []
    for pl in lines:
        cur = []
        for p, q in zip(pl, pl[1:]):
            seg = _clip_seg_circle(p, q, c)
            if seg is None:
                if cur:
                    out.append(cur)
                    cur = []
                continue
            a, b = seg
            if cur and abs(cur[-1][0] - a[0]) + abs(cur[-1][1] - a[1]) < 1e-9:
                cur.append(b)
            else:
                if cur:
                    out.append(cur)
                cur = [a, b]
        if cur:
            out.append(cur)
    return out


def _clip_seg(p, q, box):
    if box and box[0] == "circle":
        return _clip_seg_circle(p, q, box[1:])
    x0, y0, x1, y1 = box
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < 1e-12:
            if qq < 0:
                return None
        else:
            t = qq / pp
            if pp < 0:
                if t > t1:
                    return None
                t0 = max(t0, t)
            else:
                if t < t0:
                    return None
                t1 = min(t1, t)
    if t0 > t1:
        return None
    return ((p[0] + dx * t0, p[1] + dy * t0), (p[0] + dx * t1, p[1] + dy * t1))


def _ref(ref, vals, offset, axis):
    if ref is None:
        return min(vals) if offset < 0 else max(vals)
    if isinstance(ref, Shape):
        if axis == "x":
            return ref.left if offset < 0 else ref.right
        return ref.bottom if offset < 0 else ref.top
    return float(ref)


def _shift_seg(seg, dx, dy):
    k = seg[0]
    if k in ("M", "L"):
        return (k, (seg[1][0] + dx, seg[1][1] + dy))
    if k == "C":
        return (k,) + tuple((q[0] + dx, q[1] + dy) for q in seg[1:])
    if k == "E":
        return (k, (seg[1][0] + dx, seg[1][1] + dy)) + tuple(seg[2:])
    return seg

