"""Geometry: paths in model space (mm, y up) and their mapping onto the sheet.

A Path is a list of segments built in model coordinates. It renders to exact SVG
path data (lines, true arcs, cubics) and also samples itself into polylines that
the hatcher and the layout checker use.
"""

import math

TAU = math.tau


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def length(a):
    return math.hypot(a[0], a[1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(a):
    n = math.hypot(a[0], a[1])
    if n < 1e-12:
        return (1.0, 0.0)
    return (a[0] / n, a[1] / n)


def perp(a):
    """Rotate 90 degrees counter-clockwise (in whatever frame a lives in)."""
    return (-a[1], a[0])


def polar(c, r, deg):
    t = math.radians(deg)
    return (c[0] + r * math.cos(t), c[1] + r * math.sin(t))


def angle_of(v):
    return math.degrees(math.atan2(v[1], v[0]))


class Transform:
    """Model (mm, y up) -> sheet (mm, y down): sheet = origin + scale * (x, -y)."""

    def __init__(self, ox, oy, scale):
        self.ox, self.oy, self.s = ox, oy, scale

    def pt(self, p):
        return (self.ox + self.s * p[0], self.oy - self.s * p[1])

    def inv(self, q):
        return ((q[0] - self.ox) / self.s, (self.oy - q[1]) / self.s)

    def len(self, v):
        return v * self.s


class Path:
    """Segments (model space unless built with sheet=True):
    ("M", p) ("L", p) ("C", c1, c2, p) ("E", center, rx, ry, rot_deg, a0, a1) ("Z",)
    Arc angles are degrees, counter-clockwise, measured in the ellipse frame.
    """

    def __init__(self):
        self.segs = []
        self._cur = None
        self._start = None

    # ---- building ---------------------------------------------------------
    def move_to(self, x, y=None):
        p = _p(x, y)
        self.segs.append(("M", p))
        self._cur = self._start = p
        return self

    def line_to(self, x, y=None):
        p = _p(x, y)
        if self._cur is None:
            return self.move_to(p)
        self.segs.append(("L", p))
        self._cur = p
        return self

    def curve_to(self, c1, c2, p):
        self.segs.append(("C", tuple(c1), tuple(c2), tuple(p)))
        self._cur = tuple(p)
        return self

    def arc(self, center, r, a0, a1, ry=None, rot=0.0, connect=True):
        """Arc around center from angle a0 to a1 (degrees, CCW if a1 > a0)."""
        ry = r if ry is None else ry
        start = _ellipse_pt(center, r, ry, rot, a0)
        if self._cur is None or not connect:
            self.move_to(start)
        elif dist(self._cur, start) > 1e-9:
            self.line_to(start)
        self.segs.append(("E", tuple(center), r, ry, rot, a0, a1))
        self._cur = _ellipse_pt(center, r, ry, rot, a1)
        return self

    def arc_to_center(self, center, a1):
        """Continue with a circular arc around center to angle a1, CCW if a1 is
        larger than the current point's angle."""
        r = dist(self._cur, center)
        a0 = angle_of(sub(self._cur, center))
        return self.arc(center, r, a0, a1)

    def close(self):
        if self._cur is not None and self._start is not None:
            self.segs.append(("Z",))
            self._cur = self._start
        return self

    def extend(self, other):
        self.segs.extend(other.segs)
        self._cur, self._start = other._cur, other._start
        return self

    # ---- output -----------------------------------------------------------
    def svg(self, tf=None):
        """SVG path data. tf: Transform (model -> sheet) or None (already sheet)."""
        out = []
        flip = tf is not None
        P = tf.pt if tf else (lambda p: p)
        s = tf.s if tf else 1.0
        for seg in self.segs:
            k = seg[0]
            if k in ("M", "L"):
                q = P(seg[1])
                out.append(f"{k}{fmt(q[0])} {fmt(q[1])}")
            elif k == "C":
                qs = [P(seg[i]) for i in (1, 2, 3)]
                out.append("C" + " ".join(f"{fmt(q[0])} {fmt(q[1])}" for q in qs))
            elif k == "E":
                _, c, rx, ry, rot, a0, a1 = seg
                span = a1 - a0
                n = max(1, int(math.ceil(abs(span) / 179.0)))
                for i in range(n):
                    b0 = a0 + span * i / n
                    b1 = a0 + span * (i + 1) / n
                    q = P(_ellipse_pt(c, rx, ry, rot, b1))
                    ccw = b1 > b0
                    # model CCW appears CCW on paper; with the y flip that is SVG sweep 0
                    sweep = (0 if ccw else 1) if flip else (1 if ccw else 0)
                    srot = -rot if flip else rot
                    out.append(f"A{fmt(rx * s)} {fmt(ry * s)} {fmt(srot)} 0 {sweep} "
                               f"{fmt(q[0])} {fmt(q[1])}")
            else:
                out.append("Z")
        return " ".join(out)

    def polylines(self, tf=None, tol=0.02):
        """Sampled polylines (list of point lists) in sheet space if tf given."""
        P = tf.pt if tf else (lambda p: p)
        s = tf.s if tf else 1.0
        lines = []
        cur = None
        start = None
        last = (0.0, 0.0)
        for seg in self.segs:
            k = seg[0]
            if k == "M":
                cur = [P(seg[1])]
                lines.append(cur)
                start = seg[1]
                last = seg[1]
            elif k == "L":
                if cur is None:
                    cur = [P(seg[1])]
                    lines.append(cur)
                else:
                    cur.append(P(seg[1]))
                last = seg[1]
            elif k == "C":
                p0 = last
                if cur is None:
                    cur = [P(p0)]
                    lines.append(cur)
                for i in range(1, 25):
                    t = i / 24
                    cur.append(P(_bez(p0, seg[1], seg[2], seg[3], t)))
                last = seg[3]
            elif k == "E":
                _, c, rx, ry, rot, a0, a1 = seg
                rmax = max(rx, ry) * s
                step = 2 * math.degrees(math.acos(max(-1.0, 1 - tol / max(rmax, 1e-6)))) if rmax > tol else 45
                step = max(0.5, min(step, 10.0))
                n = max(2, int(math.ceil(abs(a1 - a0) / step)))
                pts = [P(_ellipse_pt(c, rx, ry, rot, a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
                if cur is None:
                    cur = pts
                    lines.append(cur)
                else:
                    cur.extend(pts[1:] if dist(cur[-1], pts[0]) < 1e-6 else pts)
                last = _ellipse_pt(c, rx, ry, rot, a1)
            elif k == "Z":
                if cur is not None and start is not None:
                    cur.append(P(start))
                    last = start
        return lines

    def bbox(self, tf=None):
        xs, ys = [], []
        for pl in self.polylines(tf):
            for p in pl:
                xs.append(p[0])
                ys.append(p[1])
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))


def _p(x, y):
    if y is None:
        return (float(x[0]), float(x[1]))
    return (float(x), float(y))


def _ellipse_pt(c, rx, ry, rot, a):
    t = math.radians(a)
    x, y = rx * math.cos(t), ry * math.sin(t)
    if rot:
        r = math.radians(rot)
        x, y = x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)
    return (c[0] + x, c[1] + y)


def _bez(p0, p1, p2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


# ---- shape constructors (model space) -------------------------------------

def rect_path(x0, y0, x1, y1, r=0.0, corner="circular"):
    """Axis-aligned rectangle, optionally with corner radius r (scalar or a
    4-tuple ordered top-left, top-right, bottom-right, bottom-left).
    corner="continuous" gives Apple-style continuous-curvature corners."""
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    w, h = x1 - x0, y1 - y0
    rs = list(r) if isinstance(r, (tuple, list)) else [r] * 4
    p = Path()
    if not any(rs):
        return p.move_to(x0, y1).line_to(x1, y1).line_to(x1, y0).line_to(x0, y0).close()
    if corner == "continuous":
        k = 1.52866483
        lim = min(w, h) / (2 * k)
        rs = [min(v, lim) for v in rs]
        return _continuous_rect(x0, y0, x1, y1, rs)
    lim = min(w, h) / 2
    tl, tr, br, bl = [min(v, lim) for v in rs]
    p.move_to(x0 + tl, y1)
    p.line_to(x1 - tr, y1)
    if tr:
        p.arc((x1 - tr, y1 - tr), tr, 90, 0)
    p.line_to(x1, y0 + br)
    if br:
        p.arc((x1 - br, y0 + br), br, 0, -90)
    p.line_to(x0 + bl, y0)
    if bl:
        p.arc((x0 + bl, y0 + bl), bl, -90, -180)
    p.line_to(x0, y1 - tl)
    if tl:
        p.arc((x0 + tl, y1 - tl), tl, 180, 90)
    return p.close()


# Continuous-curvature corner (as used across Apple hardware and iOS). One
# corner expressed for the top-right corner in a y-down frame, in multiples of r:
# (end point, control 1, control 2) for the three cubic pieces.
_CC = [
    ((1.52866483, 0.0), None, None),
    ((0.63149399, 0.07491100), (1.08849323, 0.0), (0.86840689, 0.0)),
    ((0.07491100, 0.63149399), (0.37282392, 0.16905899), (0.16905899, 0.37282392)),
    ((0.0, 1.52866471), (0.0, 0.86840689), (0.0, 1.08849323)),
]


def _continuous_rect(x0, y0, x1, y1, rs):
    tl, tr, br, bl = rs
    p = Path()

    # corner helper: corner point (cx, cy), unit vectors a (along incoming edge,
    # pointing toward the corner) and b (along outgoing edge, away from corner)
    def corner(cx, cy, ax, ay, bx, by, r, first=False):
        # point at distance d1 before corner along incoming edge, offset d2 along outgoing
        def q(t):
            # t = (back, out) in multiples of r: back against a, out along b
            return (cx - ax * t[0] * r + bx * t[1] * r, cy - ay * t[0] * r + by * t[1] * r)
        if r <= 0:
            if first:
                p.move_to(cx, cy)
            else:
                p.line_to(cx, cy)
            return
        start = q(_CC[0][0])
        if first:
            p.move_to(start)
        else:
            p.line_to(start)
        for end, c1, c2 in _CC[1:]:
            # pieces are given as (back, out) pairs
            p.curve_to(q(c1), q(c2), q(end))

    # walk clockwise as seen on paper: top edge left->right
    corner(x1, y1, 1, 0, 0, -1, tr, first=True)
    corner(x1, y0, 0, -1, -1, 0, br)
    corner(x0, y0, -1, 0, 0, 1, bl)
    corner(x0, y1, 0, 1, 1, 0, tl)
    return p.close()


def circle_path(cx, cy, r):
    return Path().arc((cx, cy), r, 0, 360).close()


def ellipse_path(cx, cy, rx, ry, rot=0.0):
    return Path().arc((cx, cy), rx, 0, 360, ry=ry, rot=rot).close()


def slot_path(cx, cy, length, width, angle=0.0):
    """Stadium / obround: overall length along `angle` (deg), full width."""
    r = width / 2
    half = max(length / 2 - r, 0.0)
    u = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    c1 = (cx + u[0] * half, cy + u[1] * half)
    c2 = (cx - u[0] * half, cy - u[1] * half)
    p = Path()
    p.arc(c1, r, angle - 90, angle + 90)
    p.arc(c2, r, angle + 90, angle + 270)
    return p.close()


def polygon_path(pts, fillet=0.0, closed=True):
    """Polyline/polygon through pts; fillet = radius (scalar or per-vertex list)
    applied at interior vertices (all vertices when closed)."""
    pts = [tuple(map(float, q)) for q in pts]
    n = len(pts)
    rs = list(fillet) if isinstance(fillet, (list, tuple)) else [fillet] * n
    p = Path()
    if not any(rs):
        p.move_to(pts[0])
        for q in pts[1:]:
            p.line_to(q)
        return p.close() if closed else p
    corners = []
    for i in range(n):
        r = rs[i]
        if not closed and (i == 0 or i == n - 1):
            corners.append((pts[i], None))
            continue
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        if r <= 0:
            corners.append((b, None))
            continue
        u1 = unit(sub(a, b))
        u2 = unit(sub(c, b))
        cosang = max(-1.0, min(1.0, dot(u1, u2)))
        half = math.acos(cosang) / 2
        if half < 1e-6 or abs(half - math.pi / 2) < 1e-9:
            corners.append((b, None))
            continue
        t = r / math.tan(half)
        lim_a = 1.0 if (not closed and i == 1) else 0.5
        lim_c = 1.0 if (not closed and i == n - 2) else 0.5
        t = min(t, dist(a, b) * lim_a, dist(b, c) * lim_c)
        rr = t * math.tan(half)
        p1 = add(b, mul(u1, t))
        p2 = add(b, mul(u2, t))
        bis = unit(add(u1, u2))
        center = add(b, mul(bis, rr / math.sin(half)))
        a0 = angle_of(sub(p1, center))
        a1 = angle_of(sub(p2, center))
        turn = cross(sub(b, a), sub(c, b))
        d = a1 - a0
        if turn > 0:  # left turn -> CCW arc
            while d <= 0:
                d += 360
        else:
            while d >= 0:
                d -= 360
        corners.append((p1, (center, rr, a0, a0 + d)))
    first = True
    for pt, arc in corners:
        if arc is None:
            if first:
                p.move_to(pt)
            else:
                p.line_to(pt)
        else:
            center, rr, a0, a1 = arc
            if first:
                p.move_to(pt)
            p.arc(center, rr, a0, a1)
        first = False
    return p.close() if closed else p


# ---- polygon utilities (sheet space) ----------------------------------------

def point_in_rings(pt, rings):
    """Even-odd point-in-polygon over several rings."""
    x, y = pt
    inside = False
    for ring in rings:
        n = len(ring)
        for i in range(n - 1 if ring[0] == ring[-1] else n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if xi > x:
                    inside = not inside
    return inside


def hatch_segments(rings, angle_deg, spacing, phase=0.0):
    """Clip a family of parallel lines (paper angle in degrees, CCW from +x as
    seen on paper) against even-odd rings. Returns segments in sheet space."""
    t = math.radians(-angle_deg)  # sheet y is down
    d = (math.cos(t), math.sin(t))
    n = (-d[1], d[0])
    pts = [q for ring in rings for q in ring]
    if not pts:
        return []
    proj_n = [dot(q, n) for q in pts]
    lo, hi = min(proj_n), max(proj_n)
    segs = []
    k0 = math.floor((lo - phase) / spacing)
    k1 = math.ceil((hi - phase) / spacing)
    edges = []
    for ring in rings:
        m = len(ring)
        for i in range(m - 1):
            edges.append((ring[i], ring[i + 1]))
        if ring[0] != ring[-1]:
            edges.append((ring[-1], ring[0]))
    edge_n = [(dot(a, n), dot(b, n), a, b) for a, b in edges]
    for k in range(k0, k1 + 1):
        c = phase + k * spacing
        ts = []
        for na, nb, a, b in edge_n:
            if (na > c) != (nb > c):
                f = (c - na) / (nb - na)
                q = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                ts.append(dot(q, d))
        ts.sort()
        for i in range(0, len(ts) - 1, 2):
            t0, t1 = ts[i], ts[i + 1]
            if t1 - t0 < 1e-6:
                continue
            p0 = add(mul(n, c), mul(d, t0))
            p1 = add(mul(n, c), mul(d, t1))
            segs.append((p0, p1))
    return segs


def box_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def seg_hits_box(p, q, b):
    """Liang-Barsky: does segment p-q touch axis-aligned box b=(x0, y0, x1, y1)?"""
    x0, y0, x1, y1 = b
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pp) < 1e-12:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return t0 <= t1
