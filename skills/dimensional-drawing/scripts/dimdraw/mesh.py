"""Triangle-mesh solids for 3-D models: the geometry behind iso views and
model-driven orthographic / section views.

Coordinates are model mm: X right, Y up, Z toward the viewer of the front view.
Every builder returns a Mesh; a Model collects meshes. Meshes are welded
(shared vertices) so the hidden-line renderer can find creases and silhouettes.

Builders: extrude (any 2-D profile, holes, edge fillets), box, cylinder, revolve
(open or closed profiles, e.g. a torus), loft (skin through cross-sections),
sweep (profile along a 3-D path), sphere, ellipsoid, torus, capsule, plus
STL / OBJ import and raw meshes.
"""

import math
import struct

from .geom import Path, unit

# ---- small vector helpers ---------------------------------------------------------


def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def v_len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def v_unit(a):
    n = v_len(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-15 else (0.0, 0.0, 0.0)


def rot_matrix(axis, deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    if axis == "x":
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == "y":
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    if axis == "z":
        return ((c, -s, 0), (s, c, 0), (0, 0, 1))
    # arbitrary axis (Rodrigues)
    x, y, z = v_unit(axis)
    C = 1 - c
    return ((c + x * x * C, x * y * C - z * s, x * z * C + y * s),
            (y * x * C + z * s, c + y * y * C, y * z * C - x * s),
            (z * x * C - y * s, z * y * C + x * s, c + z * z * C))


def m_v(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


FRAMES = {
    # profile u, v axes and extrusion axis w (right-handed)
    "xy": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "yz": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "zx": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
}


def frame(plane, origin=(0, 0, 0)):
    if isinstance(plane, str):
        u, v, w = FRAMES[plane]
    else:
        u, v = v_unit(plane[0]), v_unit(plane[1])
        w = v_cross(u, v)
    return tuple(map(float, origin)), u, v, w


def to3(fr, p, h=0.0):
    o, u, v, w = fr
    return (o[0] + u[0] * p[0] + v[0] * p[1] + w[0] * h,
            o[1] + u[1] * p[0] + v[1] * p[1] + w[1] * h,
            o[2] + u[2] * p[0] + v[2] * p[1] + w[2] * h)


# ---- 2-D profile helpers ------------------------------------------------------------

def ring_points(profile, tol=0.01):
    """Path or point list -> closed ring (no repeated end point)."""
    if isinstance(profile, Path):
        pls = profile.polylines(None, tol=tol)
        pts = max(pls, key=len)
    else:
        pts = [tuple(map(float, p[:2])) for p in profile]
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    if len(out) > 2 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) < 1e-9:
        out.pop()
    return out


def signed_area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2


def sharp_flags(pts, deg=22.0):
    n = len(pts)
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        u1 = unit((b[0] - a[0], b[1] - a[1]))
        u2 = unit((c[0] - b[0], c[1] - b[1]))
        cs = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        out.append(math.degrees(math.acos(cs)) > deg)
    return out


def offset_ring(pts, d):
    """Offset a ring toward its left side by d (inward for CCW), keeping the
    vertex count (miter join)."""
    n = len(pts)
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = unit((b[0] - a[0], b[1] - a[1]))
        e2 = unit((c[0] - b[0], c[1] - b[1]))
        n1 = (-e1[1], e1[0])
        n2 = (-e2[1], e2[0])
        m = unit((n1[0] + n2[0], n1[1] + n2[1]))
        cosh = max(0.25, m[0] * n1[0] + m[1] * n1[1])
        out.append((b[0] + m[0] * d / cosh, b[1] + m[1] * d / cosh))
    return out


def resample(profile, n, start_angle=0.0):
    """Closed 2-D profile -> n points evenly spaced by arc length, CCW, starting
    where a ray from the centroid at start_angle (deg) meets the outline.
    Sections resampled this way line up for lofting."""
    pts = ring_points(profile)
    if signed_area(pts) < 0:
        pts.reverse()
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    t = math.radians(start_angle)
    d = (math.cos(t), math.sin(t))
    # find the ray hit to start from
    best = None
    m = len(pts)
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-15:
            continue
        s = ((a[0] - cx) * ey - (a[1] - cy) * ex) / den
        u = ((a[0] - cx) * d[1] - (a[1] - cy) * d[0]) / den
        if s > 0 and -1e-12 <= u <= 1 + 1e-12:
            if best is None or s < best[0]:
                best = (s, i, u)
    if best is None:
        best = (0, 0, 0.0)
    _, i0, u0 = best
    a, b = pts[i0], pts[(i0 + 1) % m]
    start = (a[0] + (b[0] - a[0]) * u0, a[1] + (b[1] - a[1]) * u0)
    ring = [start] + [pts[(i0 + 1 + k) % m] for k in range(m)]
    ring.append(start)
    seg = [math.hypot(ring[k + 1][0] - ring[k][0], ring[k + 1][1] - ring[k][1]) for k in range(len(ring) - 1)]
    total = sum(seg)
    out = []
    acc = 0.0
    k = 0
    for j in range(n):
        target = total * j / n
        while k < len(seg) - 1 and acc + seg[k] < target:
            acc += seg[k]
            k += 1
        f = 0.0 if seg[k] < 1e-15 else (target - acc) / seg[k]
        p, q = ring[k], ring[k + 1]
        out.append((p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f))
    return out


def spline(points, n=None, closed=False, per_segment=12, clamp=True):
    """Smooth curve through 2-D or 3-D control points (centripetal Catmull-Rom).
    Use it for organic profiles: revolve(spline([...])), loft rails, sweep paths.
    n: total output points (default per_segment per span).
    clamp=True (default): no overshoot. Between two neighbouring points the curve
    stays inside their bounding box in every coordinate, so the curve's extremes
    are your points and a dimension to a control point is the true extent (a
    tire profile can't dip below the ground). clamp=False: plain Catmull-Rom,
    which can bulge past the points near sharp turns."""
    P = [tuple(map(float, p)) for p in points]
    dim = len(P[0])
    if len(P) < 3:
        return P
    N = len(P)
    if closed:
        ext = [P[-1]] + P + [P[0]]
    else:
        ext = [tuple(2 * P[0][k] - P[1][k] for k in range(dim))] + P + \
              [tuple(2 * P[-1][k] - P[-2][k] for k in range(dim))]

    def knot(a, b):
        return max(math.sqrt(sum((b[k] - a[k]) ** 2 for k in range(dim))), 1e-9) ** 0.5
    # tangent (derivative in the centripetal parameter) at every point
    tan = []
    for i in range(N):
        p0, p1, p2 = ext[i], ext[i + 1], ext[i + 2]
        d0, d1 = knot(p0, p1), knot(p1, p2)
        tan.append([(p1[k] - p0[k]) / d0 - (p2[k] - p0[k]) / (d0 + d1) + (p2[k] - p1[k]) / d1
                    for k in range(dim)])
    spans = N if closed else N - 1
    seg_dt = [knot(P[i], P[(i + 1) % N]) for i in range(spans)]
    if clamp:
        for i in range(N):
            dt_in = seg_dt[i - 1] if (closed or i > 0) else None
            dt_out = seg_dt[i] if (closed or i < N - 1) else None
            prev = P[i - 1] if dt_in is not None else None
            nxt = P[(i + 1) % N] if dt_out is not None else None
            for k in range(dim):
                m = tan[i][k]
                if prev is not None and nxt is not None and \
                        (prev[k] - P[i][k]) * (nxt[k] - P[i][k]) >= 0:
                    tan[i][k] = 0.0          # a turning point in this coordinate: flat there
                    continue
                for other, dt, sgn in ((nxt, dt_out, 1.0), (prev, dt_in, -1.0)):
                    if other is None:
                        continue
                    room = (other[k] - P[i][k]) * sgn      # signed room toward the neighbour
                    h = m * dt / 3.0
                    if h * room < 0:
                        m = 0.0
                    elif abs(h) > abs(room):
                        m = room / (dt / 3.0)
                tan[i][k] = m
    per = per_segment if n is None else max(2, int(math.ceil(n / spans)))
    out = []
    for i in range(spans):
        a, b = P[i], P[(i + 1) % N]
        dt = seg_dt[i]
        c1 = [a[k] + tan[i][k] * dt / 3.0 for k in range(dim)]
        c2 = [b[k] - tan[(i + 1) % N][k] * dt / 3.0 for k in range(dim)]
        for j in range(per):
            t = j / per
            u = 1 - t
            out.append(tuple(u * u * u * a[k] + 3 * u * u * t * c1[k] + 3 * u * t * t * c2[k]
                             + t * t * t * b[k] for k in range(dim)))
    if not closed:
        out.append(P[-1])
    return out


def superellipse(w, h, e=2.5, n=64, cx=0.0, cy=0.0):
    """Superellipse (squircle) outline of full width w and full height h centred on
    (cx, cy): e=2 is an ellipse, larger e is boxier. Points start at (+w/2, 0) and
    run counter-clockwise."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        x = w / 2 * math.copysign(abs(c) ** (2.0 / e), c)
        y = h / 2 * math.copysign(abs(s) ** (2.0 / e), s)
        pts.append((cx + x, cy + y))
    return pts


# ---- triangulation (ear clipping with hole bridging) ---------------------------------

def _cross2(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_tri(p, a, b, c):
    return (_cross2(a, b, p) >= -1e-12 and _cross2(b, c, p) >= -1e-12 and _cross2(c, a, p) >= -1e-12)


def triangulate(outer, holes=()):
    """Triangulate a simple polygon (CCW or CW) with optional holes.
    Returns (points, triangles) where triangles index into points (outer
    first, then holes in order) and are CCW."""
    pts = [tuple(p) for p in outer]
    poly = list(range(len(pts)))
    if signed_area(pts) < 0:
        poly.reverse()
    hole_rings = []
    for h in holes:
        h = list(h)
        base = len(pts)
        pts.extend(tuple(p) for p in h)
        idx = list(range(base, base + len(h)))
        if signed_area(h) > 0:      # holes must be CW
            idx.reverse()
        hole_rings.append(idx)
    # bridge holes, rightmost first
    hole_rings.sort(key=lambda r: -max(pts[i][0] for i in r))
    for ring in hole_rings:
        hi = max(range(len(ring)), key=lambda k: (pts[ring[k]][0], -pts[ring[k]][1]))
        H = pts[ring[hi]]
        best = None
        m = len(poly)
        for k in range(m):
            a, b = pts[poly[k]], pts[poly[(k + 1) % m]]
            if (a[1] - H[1]) * (b[1] - H[1]) > 0:
                continue
            if abs(b[1] - a[1]) < 1e-15:
                if abs(a[1] - H[1]) > 1e-12:
                    continue
                xi = min(a[0], b[0])
            else:
                xi = a[0] + (H[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if xi < H[0] - 1e-12:
                continue
            if best is None or xi < best[0]:
                best = (xi, k)
        if best is None:
            continue
        xi, k = best
        a_k, b_k = k, (k + 1) % m
        P = a_k if pts[poly[a_k]][0] > pts[poly[b_k]][0] else b_k
        I = (xi, H[1])
        Ppt = pts[poly[P]]
        # a reflex vertex inside triangle (H, I, P) blocks the bridge; take the
        # one with the smallest angle to the ray instead
        cand = None
        for j in range(m):
            q = pts[poly[j]]
            if j == P or q == Ppt:
                continue
            tri = (H, I, Ppt) if _cross2(H, I, Ppt) > 0 else (H, Ppt, I)
            if _in_tri(q, *tri) and q[0] >= H[0]:
                prev, nxt = pts[poly[j - 1]], pts[poly[(j + 1) % m]]
                if _cross2(prev, q, nxt) <= 0:  # reflex
                    ang = abs(math.atan2(q[1] - H[1], q[0] - H[0]))
                    if cand is None or ang < cand[0]:
                        cand = (ang, j)
        if cand is not None:
            P = cand[1]
        start = ring[hi:] + ring[:hi]
        poly = poly[:P + 1] + start + [start[0], poly[P]] + poly[P + 1:]
    # ear clipping
    tris = []
    V = poly[:]
    guard = 0
    while len(V) > 3 and guard < 100000:
        guard += 1
        n = len(V)
        ear_found = False
        for i in range(n):
            ia, ib, ic = V[i - 1], V[i], V[(i + 1) % n]
            a, b, c = pts[ia], pts[ib], pts[ic]
            if _cross2(a, b, c) <= 1e-14:
                continue
            ok = True
            for j in range(n):
                vj = V[j]
                if vj in (ia, ib, ic):
                    continue
                q = pts[vj]
                if q == a or q == b or q == c:
                    continue
                if _in_tri(q, a, b, c):
                    ok = False
                    break
            if ok:
                tris.append((ia, ib, ic))
                del V[i]
                ear_found = True
                break
        if not ear_found:
            # degenerate remainder: drop the flattest vertex
            n = len(V)
            i = min(range(n), key=lambda k: abs(_cross2(pts[V[k - 1]], pts[V[k]], pts[V[(k + 1) % n]])))
            if _cross2(pts[V[i - 1]], pts[V[i]], pts[V[(i + 1) % n]]) > 0:
                tris.append((V[i - 1], V[i], V[(i + 1) % n]))
            del V[i]
    if len(V) == 3 and _cross2(pts[V[0]], pts[V[1]], pts[V[2]]) > 1e-14:
        tris.append((V[0], V[1], V[2]))
    return pts, tris


# ---- the mesh ------------------------------------------------------------------------

class Mesh:
    """Triangle mesh solid. `lines` are feature lines drawn on top of the
    computed edges (tangent edges, decals): (points, style, vertex_ids_or_None,
    host_faces_or_None)."""

    def __init__(self, name=None, style="visible", crease=28.0):
        self.name = name or "mesh"
        self.v = []
        self.f = []
        self.lines = []
        self.style = style
        self.crease = crease
        self.caps = {}
        self.anchors = {}
        self.warnings = []
        self._cache = None

    # -- building --
    def add_v(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def tri(self, a, b, c):
        if a != b and b != c and a != c:
            self.f.append((a, b, c))
        return len(self.f) - 1

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def line(self, pts, style="thin", verts=None, hosts=None):
        self.lines.append(([tuple(map(float, p)) for p in pts], style, verts, hosts))
        return self

    # -- maintenance --
    def weld(self, tol=None):
        if not self.v:
            return self
        if tol is None:
            lo, hi = self.bounds()
            tol = max(1e-9, 1e-7 * max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1e-9))
        inv = 1.0 / tol
        key_to = {}
        remap = []
        nv = []
        for p in self.v:
            k = (round(p[0] * inv), round(p[1] * inv), round(p[2] * inv))
            j = key_to.get(k)
            if j is None:
                j = len(nv)
                key_to[k] = j
                nv.append(p)
            remap.append(j)
        nf = []
        fmap = {}
        for i, (a, b, c) in enumerate(self.f):
            a, b, c = remap[a], remap[b], remap[c]
            if a != b and b != c and a != c:
                fmap[i] = len(nf)
                nf.append((a, b, c))
        self.v, self.f = nv, nf

        def fset(fs):
            return {fmap[f] for f in fs if f in fmap} if fs is not None else None
        self.lines = [(pts, st, ([remap[i] for i in vs] if vs else None), fset(hosts))
                      for pts, st, vs, hosts in self.lines]
        self.caps = {k: (fr, h, fset(fs), ring) for k, (fr, h, fs, ring) in self.caps.items()}
        self._cache = None
        return self

    def bounds(self):
        xs = [p[0] for p in self.v]
        ys = [p[1] for p in self.v]
        zs = [p[2] for p in self.v]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def _apply(self, fn, fn_dir=None):
        self.v = [fn(p) for p in self.v]
        self.lines = [([fn(p) for p in pts], st, vs, hosts) for pts, st, vs, hosts in self.lines]
        caps = {}
        for k, (fr, h, fs, ring) in self.caps.items():
            o, u, v, w = fr
            o2 = fn(o)
            if fn_dir:
                u, v, w = fn_dir(u), fn_dir(v), fn_dir(w)
            caps[k] = ((o2, u, v, w), h, fs, ring)
        self.caps = caps
        self.anchors = {k: fn(p) for k, p in self.anchors.items()}
        self._cache = None
        return self

    def translate(self, dx=0.0, dy=0.0, dz=0.0):
        return self._apply(lambda p: (p[0] + dx, p[1] + dy, p[2] + dz))

    def rotate(self, axis, deg, center=(0, 0, 0)):
        R = rot_matrix(axis, deg)
        c = center
        return self._apply(lambda p: v_add(m_v(R, v_sub(p, c)), c), lambda d: m_v(R, d))

    def scale(self, sx, sy=None, sz=None, center=(0, 0, 0)):
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        c = center
        flip = sx * sy * sz < 0
        self._apply(lambda p: (c[0] + (p[0] - c[0]) * sx, c[1] + (p[1] - c[1]) * sy,
                               c[2] + (p[2] - c[2]) * sz),
                    lambda d: v_unit((d[0] * sx, d[1] * sy, d[2] * sz)))
        if flip:
            self.f = [(a, c_, b) for a, b, c_ in self.f]
        return self

    def mirror(self, axis="x", at=0.0):
        """Mirror copy across the plane axis=at (returns a new Mesh)."""
        m = Mesh(self.name + "-mirror", self.style, self.crease)
        k = {"x": 0, "y": 1, "z": 2}[axis]

        def fn(p):
            q = list(p)
            q[k] = 2 * at - q[k]
            return tuple(q)
        m.v = [fn(p) for p in self.v]
        m.f = [(a, c, b) for a, b, c in self.f]
        m.lines = [([fn(p) for p in pts], st, vs, None) for pts, st, vs, hosts in self.lines]
        return m

    def copy(self):
        m = Mesh(self.name, self.style, self.crease)
        m.v, m.f = list(self.v), list(self.f)
        m.lines = list(self.lines)
        m.caps = dict(self.caps)
        m.anchors = dict(self.anchors)
        return m

    def mark(self, profile, face="top", style="thin", hatch=False, angle=45.0, spacing=None):
        """Draw a 2-D outline (Path or points, in the cap's profile coordinates)
        on a planar cap of an extrusion: face='top' or 'bottom'. hatch=True
        shades it (keep-out areas)."""
        fr, h, fs, _ = self.caps[face]
        pls = profile.polylines(None, tol=0.01) if isinstance(profile, Path) else [list(profile)]
        for pl in pls:
            pts = [to3(fr, p, h) for p in pl]
            if len(pl) > 2 and abs(pl[0][0] - pl[-1][0]) + abs(pl[0][1] - pl[-1][1]) > 1e-9:
                pts.append(pts[0])
            self.lines.append((pts, style, None, set(fs)))
            if hatch:
                from .geom import hatch_segments
                sp = 0.6 if spacing is None else spacing
                for a, b in hatch_segments([[(p[0], -p[1]) for p in pl]], -angle, sp):
                    self.lines.append(([to3(fr, (a[0], -a[1]), h), to3(fr, (b[0], -b[1]), h)],
                                       "thin", None, set(fs)))
        return self

    # -- analysis (cached) --
    def topology(self):
        if self._cache is not None:
            return self._cache
        V, F = self.v, self.f
        fn = []
        fa = []
        for a, b, c in F:
            n = v_cross(v_sub(V[b], V[a]), v_sub(V[c], V[a]))
            ln = v_len(n)
            fa.append(ln / 2)
            fn.append((n[0] / ln, n[1] / ln, n[2] / ln) if ln > 1e-18 else (0.0, 0.0, 0.0))
        edges = {}
        vf = [[] for _ in V]
        for i, (a, b, c) in enumerate(F):
            for x, y in ((a, b), (b, c), (c, a)):
                k = (x, y) if x < y else (y, x)
                edges.setdefault(k, []).append(i)
            vf[a].append(i)
            vf[b].append(i)
            vf[c].append(i)
        cosc = math.cos(math.radians(self.crease))
        # corner normals: average of neighbouring faces within the crease angle
        cn = []
        for i, (a, b, c) in enumerate(F):
            n0 = fn[i]
            corners = []
            for vtx in (a, b, c):
                sx = sy = sz = 0.0
                for j in vf[vtx]:
                    nj = fn[j]
                    if n0[0] * nj[0] + n0[1] * nj[1] + n0[2] * nj[2] >= cosc:
                        w = fa[j]
                        sx += nj[0] * w
                        sy += nj[1] * w
                        sz += nj[2] * w
                corners.append(v_unit((sx, sy, sz)) if (sx or sy or sz) else n0)
            cn.append(corners)
        closed = all(len(fs) == 2 for fs in edges.values())
        self._cache = {"fn": fn, "fa": fa, "edges": edges, "vf": vf, "cn": cn, "closed": closed}
        return self._cache

    def area(self):
        return sum(self.topology()["fa"])

    def raycast(self, origin, direction):
        """First intersection of the ray origin + t*direction (t > 0) with this
        mesh, or None (Moller-Trumbore, brute force)."""
        d = v_unit(direction)
        best = None
        V = self.v
        for a_, b_, c_ in self.f:
            p0, p1, p2 = V[a_], V[b_], V[c_]
            e1, e2 = v_sub(p1, p0), v_sub(p2, p0)
            h = v_cross(d, e2)
            det = v_dot(e1, h)
            if abs(det) < 1e-14:
                continue
            inv = 1.0 / det
            sv = v_sub(origin, p0)
            u = inv * v_dot(sv, h)
            if u < 0 or u > 1:
                continue
            q = v_cross(sv, e1)
            w = inv * v_dot(d, q)
            if w < 0 or u + w > 1:
                continue
            t = inv * v_dot(e2, q)
            if t > 1e-9 and (best is None or t < best):
                best = t
        return None if best is None else v_add(origin, v_mul(d, best))

    def line_on(self, points, direction, offset=0.6, style="thin", tol=None, closed=False):
        """Draw a line ON this surface: each point is shot along `direction` from
        outside the part and lands where the ray first meets the surface, then is
        lifted `offset` mm along the surface normal so it is never hidden by its
        own face. Spans are subdivided until the line follows the curvature within
        `tol` (default offset/3): no chord sag dipping under a fillet. Points whose
        ray misses break the line. Returns the 3-D polylines drawn.
        E.g. a door shut line on the right side of a car body:
            body.line_on([(x, y, 0) for y in range(200, 900, 50)], (0, 0, -1))"""
        tol = offset / 3.0 if tol is None else tol
        d = v_unit(direction)
        caster = _RayGrid(self, d)
        pts = [tuple(map(float, p)) for p in points]
        if closed:
            pts.append(pts[0])
        far = 2.0 * v_len(v_sub(*self.bounds())) + 1.0

        def hit(p):
            return caster.first(v_sub(p, v_mul(d, far)), offset)
        runs, cur = [], []
        prev_p, prev_h = None, None
        for p in pts:
            h = hit(p)
            if h is None:
                if len(cur) > 1:
                    runs.append(cur)
                cur, prev_p, prev_h = [], None, None
                continue
            if prev_h is not None:
                cur.extend(self._refine(hit, prev_p, prev_h, p, h, tol, 0)[1:])
            else:
                cur = [h]
            prev_p, prev_h = p, h
        if len(cur) > 1:
            runs.append(cur)
        for r in runs:
            self.line(r, style)
        return runs

    @staticmethod
    def _refine(hit, pa, ha, pb, hb, tol, depth):
        pm = tuple((pa[k] + pb[k]) / 2 for k in range(3))
        hm = hit(pm)
        if hm is None or depth >= 7:
            return [ha, hb]
        chord = tuple((ha[k] + hb[k]) / 2 for k in range(3))
        if v_len(v_sub(hm, chord)) <= tol and depth >= 1:
            return [ha, hb]
        left = Mesh._refine(hit, pa, ha, pm, hm, tol, depth + 1)
        right = Mesh._refine(hit, pm, hm, pb, hb, tol, depth + 1)
        return left + right[1:]

    def health(self):
        """Problems worth knowing before drawing: builder warnings, open edges on
        a mesh meant to be closed, inconsistent face orientation, slivers."""
        out = list(self.warnings)
        if not self.f:
            return out
        top = self.topology()
        directed = {}
        for a, b, c in self.f:
            for x, y in ((a, b), (b, c), (c, a)):
                directed[(x, y)] = directed.get((x, y), 0) + 1
        flipped = sum(1 for k in directed.values() if k > 1)
        if flipped:
            out.append(f"mesh '{self.name}': {flipped} edges shared by faces facing the same way "
                       f"(folded or inside-out surface)")
        open_edges = sum(1 for fs in top["edges"].values() if len(fs) == 1)
        if open_edges and top.get("closed") is False and len(self.f) > 20:
            out.append(f"mesh '{self.name}': open surface ({open_edges} boundary edges); "
                       f"fine for sheets, otherwise cap it")
        return out

    def point(self, x="mid", y="mid", z="mid"):
        """A point on this mesh's bounding box: each coordinate 'min' | 'mid' |
        'max' or a number. E.g. mesh.point('max', 'min', 'mid')."""
        return _bbox_point(self.bounds(), x, y, z)

    def extreme(self, direction):
        """The vertex furthest along a direction: '+x', '-y', ... or a vector.
        Dimension an envelope from these and the extension lines start on the
        part itself (the tip of a handle, the crown of a dome)."""
        d = _dir(direction)
        return max(self.v, key=lambda p: v_dot(p, d))

    def nearest(self, p):
        """Distance from point p to the mesh surface (brute force)."""
        best = float("inf")
        V = self.v
        for a, b, c in self.f:
            d = _pt_tri_dist(p, V[a], V[b], V[c])
            if d < best:
                best = d
        return best

    # -- sectioning --
    def cut(self, point, normal):
        """Keep the part on the side opposite `normal` of the plane through
        `point`. Returns (new_mesh, loops): loops are the closed cut outlines."""
        n = v_unit(normal)
        d0 = v_dot(n, point)
        V = self.v
        sd = [v_dot(n, p) - d0 for p in V]
        out = Mesh(self.name, self.style, self.crease)
        out.v = list(V)
        newv = {}
        cut_segs = []

        def mid(i, j):
            k = (i, j) if i < j else (j, i)
            m = newv.get(k)
            if m is None:
                t = sd[i] / (sd[i] - sd[j])
                p = v_add(V[i], v_mul(v_sub(V[j], V[i]), t))
                m = len(out.v)
                out.v.append(p)
                newv[k] = m
            return m
        eps = 1e-12
        for a, b, c in self.f:
            s = (sd[a], sd[b], sd[c])
            keep = [x <= eps for x in s]
            if all(keep):
                out.f.append((a, b, c))
                continue
            if not any(keep):
                continue
            tri = (a, b, c)
            # rotate so the odd vertex is first
            if sum(keep) == 1:
                k = keep.index(True)
                i0, i1, i2 = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]
                m1, m2 = mid(i0, i1), mid(i0, i2)
                out.f.append((i0, m1, m2))
                cut_segs.append((m1, m2))
            else:
                k = keep.index(False)
                i0, i1, i2 = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]
                m1, m2 = mid(i0, i1), mid(i0, i2)
                out.f.append((m1, i1, i2))
                out.f.append((m1, i2, m2))
                cut_segs.append((m2, m1))
        # chain cut segments into loops
        nxt = {}
        for a, b in cut_segs:
            nxt.setdefault(a, []).append(b)
        loops = []
        used = set()
        for a, b in cut_segs:
            if (a, b) in used:
                continue
            loop = [a]
            cur = a
            nx = b
            used.add((a, b))
            while True:
                loop.append(nx)
                if nx == loop[0]:
                    break
                cands = [c for c in nxt.get(nx, []) if (nx, c) not in used]
                if not cands:
                    break
                used.add((nx, cands[0]))
                cur, nx = nx, cands[0]
            if len(loop) > 3:
                loops.append([out.v[i] for i in loop])
        # feature lines: keep only what lies behind the plane
        for pts, st, vids, hosts in self.lines:
            run, run_ids = [], []
            sdp = [v_dot(n, p) - d0 for p in pts]

            def flush():
                if len(run) > 1:
                    ok = run_ids and all(i is not None for i in run_ids)
                    out.lines.append((list(run), st, list(run_ids) if ok else None,
                                      hosts if not vids else None))
            for k, p in enumerate(pts):
                vid = vids[k] if vids and k < len(vids) else None
                if sdp[k] <= eps:
                    if run and k > 0 and sdp[k - 1] > eps:
                        t = sdp[k - 1] / (sdp[k - 1] - sdp[k])
                        run.append(v_add(pts[k - 1], v_mul(v_sub(p, pts[k - 1]), t)))
                        run_ids.append(None)
                    elif not run and k > 0 and sdp[k - 1] > eps:
                        t = sdp[k - 1] / (sdp[k - 1] - sdp[k])
                        run.append(v_add(pts[k - 1], v_mul(v_sub(p, pts[k - 1]), t)))
                        run_ids.append(None)
                    run.append(p)
                    run_ids.append(vid)
                else:
                    if run and sdp[k - 1] <= eps:
                        t = sdp[k - 1] / (sdp[k - 1] - sdp[k])
                        run.append(v_add(pts[k - 1], v_mul(v_sub(p, pts[k - 1]), t)))
                        run_ids.append(None)
                    flush()
                    run, run_ids = [], []
            flush()
        out.weld()
        return out, loops


class _RayGrid:
    """Rays all in one direction against one mesh: triangles binned on the plane
    across the rays, so each ray only tests the few under it."""

    def __init__(self, mesh, d):
        self.m, self.d = mesh, d
        a = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
        self.u = v_unit(v_cross(d, a))
        self.w = v_cross(d, self.u)
        V = mesh.v
        uv = [(v_dot(p, self.u), v_dot(p, self.w)) for p in V]
        self.uv = uv
        n = max(len(mesh.f), 1)
        if uv:
            us = [q[0] for q in uv]
            ws = [q[1] for q in uv]
            area = max((max(us) - min(us)) * (max(ws) - min(ws)), 1e-9)
        else:
            area = 1.0
        self.cell = max(math.sqrt(area / n) * 2.0, 1e-6)
        self.bins = {}
        c = self.cell
        for fi, (i, j, k) in enumerate(mesh.f):
            u0 = min(uv[i][0], uv[j][0], uv[k][0])
            u1 = max(uv[i][0], uv[j][0], uv[k][0])
            w0 = min(uv[i][1], uv[j][1], uv[k][1])
            w1 = max(uv[i][1], uv[j][1], uv[k][1])
            for gx in range(int(math.floor(u0 / c)), int(math.floor(u1 / c)) + 1):
                for gy in range(int(math.floor(w0 / c)), int(math.floor(w1 / c)) + 1):
                    self.bins.setdefault((gx, gy), []).append(fi)

    def first(self, origin, lift=0.0):
        d = self.d
        key = (int(math.floor(v_dot(origin, self.u) / self.cell)),
               int(math.floor(v_dot(origin, self.w) / self.cell)))
        V = self.m.v
        best, bf = None, None
        for fi in self.bins.get(key, ()):
            a_, b_, c_ = self.m.f[fi]
            p0, p1, p2 = V[a_], V[b_], V[c_]
            e1, e2 = v_sub(p1, p0), v_sub(p2, p0)
            h = v_cross(d, e2)
            det = v_dot(e1, h)
            if abs(det) < 1e-14:
                continue
            inv = 1.0 / det
            sv = v_sub(origin, p0)
            u = inv * v_dot(sv, h)
            if u < -1e-9 or u > 1 + 1e-9:
                continue
            q = v_cross(sv, e1)
            w = inv * v_dot(d, q)
            if w < -1e-9 or u + w > 1 + 1e-9:
                continue
            t = inv * v_dot(e2, q)
            if t > 1e-9 and (best is None or t < best):
                best, bf = t, (e1, e2)
        if best is None:
            return None
        p = v_add(origin, v_mul(d, best))
        if lift:
            nrm = v_unit(v_cross(*bf))
            if v_dot(nrm, d) > 0:
                nrm = v_mul(nrm, -1.0)
            p = v_add(p, v_mul(nrm, lift))
        return p


def _dir(direction):
    if isinstance(direction, str):
        s = -1.0 if direction.startswith("-") else 1.0
        i = "xyz".index(direction.lstrip("+-").lower())
        d = [0.0, 0.0, 0.0]
        d[i] = s
        return tuple(d)
    return v_unit(direction)


def _bbox_point(bb, x, y, z):
    lo, hi = bb
    out = []
    for i, v in enumerate((x, y, z)):
        if v == "min":
            out.append(lo[i])
        elif v == "max":
            out.append(hi[i])
        elif v == "mid":
            out.append((lo[i] + hi[i]) / 2)
        else:
            out.append(float(v))
    return tuple(out)


def _pt_tri_dist(p, a, b, c):
    # Ericson, Real-Time Collision Detection 5.1.5
    ab, ac, ap = v_sub(b, a), v_sub(c, a), v_sub(p, a)
    d1, d2 = v_dot(ab, ap), v_dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return v_len(ap)
    bp = v_sub(p, b)
    d3, d4 = v_dot(ab, bp), v_dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return v_len(bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3)
        return v_len(v_sub(p, v_add(a, v_mul(ab, v))))
    cp = v_sub(p, c)
    d5, d6 = v_dot(ab, cp), v_dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return v_len(cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6)
        return v_len(v_sub(p, v_add(a, v_mul(ac, w))))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return v_len(v_sub(p, v_add(b, v_mul(v_sub(c, b), w))))
    den = 1.0 / (va + vb + vc)
    v = vb * den
    w = vc * den
    q = v_add(a, v_add(v_mul(ab, v), v_mul(ac, w)))
    return v_len(v_sub(p, q))


# ---- builders ------------------------------------------------------------------------

def extrude(profile, z0, z1, plane="xy", origin=(0, 0, 0), fillet=(0.0, 0.0), holes=(),
            fillet_steps=6, tangent_lines=True, name=None, style="visible", segments=None):
    """Extrude a closed 2-D profile from z0 to z1 along the plane normal.
    holes: inner profiles cut all the way through. fillet=(bottom, top) rounds
    the cap edges; its tangent edges are drawn as thin lines."""
    pts = ring_points(profile)
    if segments:
        pts = resample(profile, segments)
    if signed_area(pts) < 0:
        pts.reverse()
    hl = []
    for h in holes:
        hp = ring_points(h)
        if signed_area(hp) > 0:
            hp.reverse()            # holes clockwise
        hl.append(hp)
    fr = frame(plane, origin)
    fb, ft = (fillet, fillet) if isinstance(fillet, (int, float)) else fillet
    levels = []   # (inset, height, tangent?)
    if fb > 0:
        for i in range(fillet_steps + 1):
            th = math.radians(90 * (1 - i / fillet_steps))
            levels.append((fb * (1 - math.cos(th)), z0 + fb * (1 - math.sin(th)),
                           tangent_lines and i in (0, fillet_steps)))
    else:
        levels.append((0.0, z0, False))
    if ft > 0:
        for i in range(fillet_steps + 1):
            th = math.radians(90 * i / fillet_steps)
            levels.append((ft * (1 - math.cos(th)), z1 - ft * (1 - math.sin(th)),
                           tangent_lines and i in (0, fillet_steps)))
    else:
        levels.append((0.0, z1, False))
    m = Mesh(name or "extrude", style)
    rings = [pts] + hl
    starts = []   # starts[level][ring] = first vertex index
    for inset, hgt, _ in levels:
        row = []
        for r in rings:
            rr = offset_ring(r, inset) if inset > 1e-12 else r
            row.append(len(m.v))
            for p in rr:
                m.add_v(to3(fr, p, hgt))
        starts.append(row)
    for li in range(len(levels) - 1):
        for ri, r in enumerate(rings):
            a, b = starts[li][ri], starts[li + 1][ri]
            n = len(r)
            for i in range(n):
                j = (i + 1) % n
                m.quad(a + i, a + j, b + j, b + i)
    # caps
    for name_, li, flip in (("bottom", 0, True), ("top", len(levels) - 1, False)):
        inset, hgt, _ = levels[li]
        ring2 = [offset_ring(r, inset) if inset > 1e-12 else r for r in rings]
        cpts, tris = triangulate(ring2[0], ring2[1:])
        # map triangulation points back to mesh vertices
        index = {}
        for ri, r in enumerate(ring2):
            for k, p in enumerate(r):
                index[(round(p[0], 9), round(p[1], 9))] = starts[li][ri] + k
        fs = set()
        for t in tris:
            ids = []
            for q in t:
                p = cpts[q]
                ids.append(index.get((round(p[0], 9), round(p[1], 9))))
            if None in ids:
                continue
            fi = len(m.f)
            if flip:
                m.tri(ids[0], ids[2], ids[1])
            else:
                m.tri(ids[0], ids[1], ids[2])
            if len(m.f) > fi:
                fs.add(len(m.f) - 1)
        m.caps[name_] = (fr, hgt, fs, ring2[0])
    # tangent lines where fillets meet the walls (and the cap edge rings)
    for li, (inset, hgt, tan) in enumerate(levels):
        if tan:
            for ri, r in enumerate(rings):
                ids = [starts[li][ri] + k for k in range(len(r))] + [starts[li][ri]]
                m.lines.append(([m.v[i] for i in ids], "thin", ids, None))
    m.anchors.update({"bottom_center": to3(fr, _centroid(pts), z0), "top_center": to3(fr, _centroid(pts), z1)})
    _fix_orientation(m)
    return m.weld()


def _centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def box(center, size, r=0.0, fillet=0.0, corner="circular", name=None, style="visible"):
    from .geom import rect_path
    cx, cy, cz = center
    sx, sy, sz = size
    prof = rect_path(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2, r, corner)
    return extrude(prof, cz - sz / 2, cz + sz / 2, "xy", fillet=fillet, name=name or "box", style=style)


def cylinder(center, r, h, axis="z", fillet=0.0, segments=96, name=None, style="visible", holes=()):
    """Cylinder from base center `center`, height h along +axis. holes: inner
    radii (tubes)."""
    prof = [(r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments))
            for i in range(segments)]
    plane = {"z": "xy", "x": "yz", "y": "zx"}[axis]
    o, u, v, w = frame(plane)
    c = tuple(map(float, center))
    pu, pv, pw = v_dot(c, u), v_dot(c, v), v_dot(c, w)
    prof = [(p[0] + pu, p[1] + pv) for p in prof]
    hl = [[(pu + rh * math.cos(2 * math.pi * i / segments), pv + rh * math.sin(2 * math.pi * i / segments))
           for i in range(segments)] for rh in holes]
    return extrude(prof, pw, pw + h, plane, fillet=fillet, holes=hl, name=name or "cylinder", style=style)


def revolve(profile, axis="y", center=(0, 0, 0), segments=96, closed=False, angle=360.0,
            name=None, style="visible", start=0.0):
    """Solid of revolution. profile: [(radius, height), ...] from one end to the
    other (open), or a closed loop with closed=True (torus-like). Profile points
    on the axis (radius 0) become poles."""
    if isinstance(profile, Path):
        prof = [(max(q[0], 0.0), q[1]) for q in profile.polylines()[0]]
    else:
        prof = [(float(p[0]), float(p[1])) for p in profile]
    a_u, a_v, a_w = {"y": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
                     "z": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                     "x": ((0, 1, 0), (0, 0, 1), (1, 0, 0))}[axis]
    c = tuple(map(float, center))
    m = Mesh(name or "revolve", style)
    full = abs(angle - 360.0) < 1e-9
    nseg = segments if full else max(2, int(round(segments * angle / 360.0)))
    ncol = nseg if full else nseg + 1
    rows = []
    for rr, hh in prof:
        if rr < 1e-9:
            idx = m.add_v(v_add(c, v_mul(a_w, hh)))
            rows.append([idx] * ncol)
            continue
        row = []
        for i in range(ncol):
            t = math.radians(start + angle * i / nseg)
            p = v_add(v_add(v_mul(a_u, rr * math.cos(t)), v_mul(a_v, rr * math.sin(t))), v_mul(a_w, hh))
            row.append(m.add_v(v_add(c, p)))
        rows.append(row)
    nrow = len(rows)
    pairs = [(k, k + 1) for k in range(nrow - 1)]
    if closed:
        pairs.append((nrow - 1, 0))
    for k0, k1 in pairs:
        A, B = rows[k0], rows[k1]
        for i in range(nseg):
            j = (i + 1) % ncol if full else i + 1
            m.quad(A[i], A[j], B[j], B[i])
    if not closed:
        for k, flip, nm in ((0, True, "bottom"), (nrow - 1, False, "top")):
            rr, hh = prof[k]
            if rr > 1e-9 and full:
                ci = m.add_v(v_add(c, v_mul(a_w, hh)))
                fs = set()
                row = rows[k]
                for i in range(nseg):
                    j = (i + 1) % ncol
                    before = len(m.f)
                    if flip:
                        m.tri(ci, row[j], row[i])
                    else:
                        m.tri(ci, row[i], row[j])
                    if len(m.f) > before:
                        fs.add(len(m.f) - 1)
                m.caps[nm] = ((c, a_u, a_v, a_w), hh, fs, None)
    _fix_orientation(m)
    return m.weld()


def _fix_orientation(m):
    """Make a closed mesh's normals point outward (signed volume > 0)."""
    vol = 0.0
    V = m.v
    for a, b, c in m.f:
        vol += v_dot(V[a], v_cross(V[b], V[c]))
    if vol < 0:
        m.f = [(a, c, b) for a, b, c in m.f]


def loft(sections, cap=True, closed=False, name=None, style="visible", dome=None, dome_steps=8):
    """Skin through cross-sections: a list of rings of 3-D points, all with the
    same point count and the same start/orientation (see `section()`).
    cap=True closes both ends flat; cap="dome" closes them with rounded domes
    (depth `dome` mm along the loft, default half the end section's size);
    closed=True joins the last section to the first."""
    if cap == "dome" and not closed and len(sections) > 1:
        sections = _dome_ends(sections, dome, dome_steps)
    n = len(sections[0])
    if any(len(s) != n for s in sections):
        raise ValueError("loft: every section needs the same number of points (use resample)")
    m = Mesh(name or "loft", style)
    # every section should wind the same way around the loft direction; a flipped
    # one means the section is inverted or self-intersecting (e.g. bottom above top)
    if len(sections) > 1:
        cents = [tuple(sum(p[i] for p in sec) / n for i in range(3)) for sec in sections]
        signs = []
        for k, sec in enumerate(sections):
            nx = ny = nz = 0.0
            for i in range(n):
                p, q = sec[i], sec[(i + 1) % n]
                nx += (p[1] - q[1]) * (p[2] + q[2])
                ny += (p[2] - q[2]) * (p[0] + q[0])
                nz += (p[0] - q[0]) * (p[1] + q[1])
            a_ = cents[min(k + 1, len(cents) - 1)]
            b_ = cents[max(k - 1, 0)]
            d = v_sub(a_, b_)
            signs.append(nx * d[0] + ny * d[1] + nz * d[2])
        major = 1 if sum(1 for x in signs if x > 0) >= sum(1 for x in signs if x < 0) else -1
        bad = [k for k, x in enumerate(signs) if x * major < 0]
        if bad:
            m.warnings.append(f"loft '{m.name}': section(s) {bad[:8]}{'...' if len(bad) > 8 else ''} "
                              f"wind the other way: inverted or self-intersecting cross-section")
    rows = []
    for s in sections:
        rows.append([m.add_v(p) for p in s])
    pairs = [(k, k + 1) for k in range(len(rows) - 1)]
    if closed:
        pairs.append((len(rows) - 1, 0))
    for k0, k1 in pairs:
        A, B = rows[k0], rows[k1]
        for i in range(n):
            j = (i + 1) % n
            m.quad(A[i], A[j], B[j], B[i])
    if cap and not closed:
        for k, flip, nm in ((0, True, "start"), (len(rows) - 1, False, "end")):
            ring = sections[k]
            cen = tuple(sum(p[i] for p in ring) / n for i in range(3))
            ci = m.add_v(cen)
            row = rows[k]
            fs = set()
            for i in range(n):
                j = (i + 1) % n
                before = len(m.f)
                if flip:
                    m.tri(ci, row[j], row[i])
                else:
                    m.tri(ci, row[i], row[j])
                if len(m.f) > before:
                    fs.add(len(m.f) - 1)
            m.caps[nm] = (None, None, fs, None)
    _fix_orientation(m)
    return m.weld()


def _dome_ends(sections, depth, steps):
    n = len(sections[0])

    def cen(sec):
        return tuple(sum(p[i] for p in sec) / n for i in range(3))

    def ends(sec, nxt):
        c = cen(sec)
        d = v_unit(v_sub(c, cen(nxt)))
        size = sum(v_len(v_sub(p, c)) for p in sec) / n
        dep = size * 0.5 if depth is None else depth
        rings = []
        for k in range(1, steps + 1):
            th = math.pi / 2 * k / steps
            sc = math.cos(th) if k < steps else 0.02
            rings.append([v_add(v_add(c, v_mul(v_sub(p, c), sc)), v_mul(d, dep * math.sin(th))) for p in sec])
        return rings
    head = ends(sections[0], sections[1])[::-1]
    tail = ends(sections[-1], sections[-2])
    return head + list(sections) + tail


def section(profile, origin=(0, 0, 0), u=(1, 0, 0), v=(0, 1, 0), n=64, start_angle=0.0):
    """Place a 2-D closed profile (Path or points) as a 3-D loft section:
    resampled to n points, profile x along u and profile y along v, at origin."""
    pts = resample(profile, n, start_angle)
    o = tuple(map(float, origin))
    return [(o[0] + u[0] * p[0] + v[0] * p[1], o[1] + u[1] * p[0] + v[1] * p[1],
             o[2] + u[2] * p[0] + v[2] * p[1]) for p in pts]


def sweep(profile, path, closed=False, cap=True, n=32, scale=None, twist=0.0, name=None,
          style="visible"):
    """Sweep a closed 2-D profile along a 3-D path (list of points) using
    rotation-minimizing frames: tubes, handles, cables, rails.
    Profile orientation at the start of the path: profile x points along world +Y
    made perpendicular to the path (world +X if the path starts vertically), and
    profile y = tangent x profile-x. For a path in a vertical plane that starts
    horizontally (a handle loop in X-Y), profile x stays in that plane and
    profile y points across it (along Z). scale: optional per-point list."""
    pts = [tuple(map(float, p)) for p in path]
    prof = resample(profile, n)
    N = len(pts)
    T = []
    for i in range(N):
        if closed:
            a, b = pts[i - 1], pts[(i + 1) % N]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, N - 1)]
        T.append(v_unit(v_sub(b, a)))
    # initial normal: any vector not parallel to T0
    t0 = T[0]
    ref = (0, 1, 0) if abs(t0[1]) < 0.9 else (1, 0, 0)
    r = v_unit(v_cross(v_cross(t0, ref), t0))
    frames = [r]
    for i in range(N - 1):
        # double reflection (Wang et al. 2008)
        v1 = v_sub(pts[i + 1], pts[i])
        c1 = v_dot(v1, v1)
        if c1 < 1e-18:
            frames.append(frames[-1])
            continue
        rL = v_sub(frames[-1], v_mul(v1, 2 / c1 * v_dot(v1, frames[-1])))
        tL = v_sub(T[i], v_mul(v1, 2 / c1 * v_dot(v1, T[i])))
        v2 = v_sub(T[i + 1], tL)
        c2 = v_dot(v2, v2)
        rn = rL if c2 < 1e-18 else v_sub(rL, v_mul(v2, 2 / c2 * v_dot(v2, rL)))
        frames.append(v_unit(rn))
    secs = []
    for i in range(N):
        rv = frames[i]
        bv = v_cross(T[i], rv)
        k = scale[i] if scale else 1.0
        ang = math.radians(twist * i / max(N - 1, 1))
        ca, sa = math.cos(ang), math.sin(ang)
        ring = []
        for (x, y) in prof:
            x2, y2 = (x * ca - y * sa) * k, (x * sa + y * ca) * k
            ring.append(v_add(pts[i], v_add(v_mul(rv, x2), v_mul(bv, y2))))
        secs.append(ring)
    return loft(secs, cap=cap and not closed, closed=closed, name=name or "sweep", style=style)


SMOOTH = 179.0   # crease angle for smooth primitives: no edges, only the silhouette


def sphere(center, r, segments=64, rings=32, name=None, style="visible"):
    prof = [(r * math.sin(math.pi * i / rings), -r * math.cos(math.pi * i / rings)) for i in range(rings + 1)]
    m = revolve(prof, "y", center, segments, name=name or "sphere", style=style)
    m.crease = SMOOTH
    return m


def ellipsoid(center, radii, segments=64, rings=32, name=None, style="visible"):
    m = sphere((0, 0, 0), 1.0, segments, rings, name or "ellipsoid", style)
    m.scale(radii[0], radii[1], radii[2])
    return m.translate(*center)


def torus(center, R, r, axis="y", segments=96, tube=32, name=None, style="visible"):
    prof = [(R + r * math.cos(2 * math.pi * i / tube), r * math.sin(2 * math.pi * i / tube)) for i in range(tube)]
    m = revolve(prof, axis, center, segments, closed=True, name=name or "torus", style=style)
    m.crease = SMOOTH
    return m


def capsule(center, r, length, axis="y", segments=64, rings=16, name=None, style="visible"):
    """Cylinder with hemispherical ends; `length` is the overall length."""
    half = max(length / 2 - r, 0.0)
    prof = []
    for i in range(rings + 1):
        t = math.pi / 2 * i / rings
        prof.append((r * math.sin(t), -half - r * math.cos(t)))
    for i in range(rings + 1):
        t = math.pi / 2 * i / rings
        prof.append((r * math.cos(t), half + r * math.sin(t)))
    m = revolve(prof, axis, center, segments, name=name or "capsule", style=style)
    m.crease = SMOOTH
    return m


def from_triangles(verts, faces, name="mesh", style="visible", crease=28.0):
    m = Mesh(name, style, crease)
    m.v = [tuple(map(float, p)) for p in verts]
    for f in faces:
        f = list(f)
        for k in range(1, len(f) - 1):
            m.tri(f[0], f[k], f[k + 1])
    return m.weld()


def load_stl(path, scale=1.0, name=None, crease=35.0):
    """Binary or ASCII STL -> welded Mesh (units * scale)."""
    with open(path, "rb") as fh:
        data = fh.read()
    verts, faces = [], []
    is_ascii = data[:5].lower() == b"solid" and b"facet" in data[:1024]
    if not is_ascii and len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + 50 * n != len(data):
            is_ascii = data[:5].lower() == b"solid"
    if is_ascii:
        cur = []
        for line in data.decode("ascii", "replace").splitlines():
            t = line.strip().split()
            if len(t) == 4 and t[0] == "vertex":
                cur.append(tuple(float(x) * scale for x in t[1:]))
                if len(cur) == 3:
                    base = len(verts)
                    verts.extend(cur)
                    faces.append((base, base + 1, base + 2))
                    cur = []
    else:
        n = struct.unpack("<I", data[80:84])[0]
        off = 84
        for _ in range(n):
            vals = struct.unpack("<12fH", data[off:off + 50])
            off += 50
            base = len(verts)
            verts.extend([(vals[3] * scale, vals[4] * scale, vals[5] * scale),
                          (vals[6] * scale, vals[7] * scale, vals[8] * scale),
                          (vals[9] * scale, vals[10] * scale, vals[11] * scale)])
            faces.append((base, base + 1, base + 2))
    return from_triangles(verts, faces, name or "stl", crease=crease)


def load_obj(path, scale=1.0, name=None, crease=35.0):
    """Wavefront OBJ (v / f records; polygons are fanned) -> welded Mesh."""
    verts, faces = [], []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            t = line.split()
            if not t:
                continue
            if t[0] == "v" and len(t) >= 4:
                verts.append((float(t[1]) * scale, float(t[2]) * scale, float(t[3]) * scale))
            elif t[0] == "f" and len(t) >= 4:
                idx = []
                for tok in t[1:]:
                    k = int(tok.split("/")[0])
                    idx.append(k - 1 if k > 0 else len(verts) + k)
                faces.append(idx)
    return from_triangles(verts, faces, name or "obj", crease=crease)


def save_stl(meshes, path):
    """Write meshes as one binary STL (for handing models to other tools)."""
    tris = []
    for m in meshes:
        for a, b, c in m.f:
            tris.append((m.v[a], m.v[b], m.v[c]))
    with open(path, "wb") as fh:
        fh.write(b"dimdraw".ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            n = v_unit(v_cross(v_sub(b, a), v_sub(c, a)))
            fh.write(struct.pack("<12fH", *n, *a, *b, *c, 0))


class Model:
    """A collection of meshes: one product, drawn in any number of views.
    Builders (extrude, box, cylinder, revolve, loft, sweep, sphere, ellipsoid,
    torus, capsule) take the same arguments as the module functions of the same
    name, add the mesh to the model and return it."""

    def __init__(self, name="model"):
        self.name = name
        self.meshes = []
        self.joints = set()

    def joint(self, a, b):
        """Declare that meshes a and b (Mesh objects or names) are meant to pass
        through each other, so the checker's interference NOTE skips the pair."""
        na = a.name if isinstance(a, Mesh) else str(a)
        nb = b.name if isinstance(b, Mesh) else str(b)
        self.joints.add(frozenset((na, nb)))
        return self

    def raycast(self, origin, direction):
        """First hit of a ray on any mesh: (point, mesh) or (None, None). Use it to
        put feature lines, decals and callout targets exactly on curved surfaces."""
        best = (None, None, float("inf"))
        for m in self.meshes:
            hit = m.raycast(origin, direction)
            if hit is not None:
                d = v_len(v_sub(hit, origin))
                if d < best[2]:
                    best = (hit, m, d)
        return best[0], best[1]

    def add(self, mesh):
        self.meshes.append(mesh)
        return mesh

    def load(self, path, scale=1.0, name=None, crease=35.0):
        """Import an STL or OBJ (welded). crease: angle in degrees above which
        edges draw; raise it (40-60) for noisy scans, lower it for CAD exports."""
        fn = load_stl if path.lower().endswith(".stl") else load_obj
        return self.add(fn(path, scale, name, crease))

    def mesh(self, verts, faces, name="mesh", style="visible"):
        return self.add(from_triangles(verts, faces, name, style))

    def bounds(self):
        lo = [float("inf")] * 3
        hi = [float("-inf")] * 3
        for m in self.meshes:
            a, b = m.bounds()
            for i in range(3):
                lo[i] = min(lo[i], a[i])
                hi[i] = max(hi[i], b[i])
        return tuple(lo), tuple(hi)

    def point(self, x="mid", y="mid", z="mid"):
        """A point on the model's bounding box: each coordinate 'min' | 'mid' |
        'max' or a number. E.g. model.point('min', 'min', 'mid') is the
        bottom-left of the front view, halfway through the depth."""
        return _bbox_point(self.bounds(), x, y, z)

    def size(self):
        lo, hi = self.bounds()
        return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])

    def extreme(self, direction):
        """The model vertex furthest along a direction ('+x', '-z', or a vector):
        a real point on the part that sets the overall size."""
        d = _dir(direction)
        return max((m.extreme(d) for m in self.meshes if m.v), key=lambda p: v_dot(p, d))

    def envelope(self):
        """Which part sets each extreme: {'x': ((min, mesh name), (max, mesh name)),
        'y': ..., 'z': ...}. Print it before dimensioning overall sizes: a lamp or
        a handle that sticks out past the body shows up here."""
        out = {}
        for i, ax in enumerate("xyz"):
            lo = hi = None
            for m in self.meshes:
                if not m.v:
                    continue
                a, b = m.bounds()
                if lo is None or a[i] < lo[0]:
                    lo = (round(a[i], 3), m.name)
                if hi is None or b[i] > hi[0]:
                    hi = (round(b[i], 3), m.name)
            out[ax] = (lo, hi)
        return out

    def stats(self):
        return {"meshes": len(self.meshes), "triangles": sum(len(m.f) for m in self.meshes),
                "vertices": sum(len(m.v) for m in self.meshes)}

    def save_stl(self, path):
        save_stl(self.meshes, path)

    def interferences(self, min_length=0.5):
        """Pairs of meshes that pass through each other, with the length of
        their intersection curve (mm). Intended joints (a handle entering a
        body) show up here, and so do modeling mistakes (a part sunk into
        another): review the list."""
        from .hlr import _intersections
        ident = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        solid = [m for m in self.meshes if m.f]
        gid = [list(range(len(m.f))) for m in solid]
        segs = _intersections(solid, ident, gid, lambda mi, vids: set(), tag=True)
        out = {}
        for a, b, la, lb in segs:
            L = math.dist(a, b)
            out[(la, lb)] = out.get((la, lb), 0.0) + L
        return [(solid[i].name, solid[j].name, round(L, 2)) for (i, j), L in sorted(out.items())
                if L >= min_length and frozenset((solid[i].name, solid[j].name)) not in self.joints]


def _builder(fn):
    import functools

    @functools.wraps(fn)
    def method(self, *a, **kw):
        return self.add(fn(*a, **kw))
    return method


for _fn in (extrude, box, cylinder, revolve, loft, sweep, sphere, ellipsoid, torus, capsule):
    setattr(Model, _fn.__name__, _builder(_fn))
del _fn
