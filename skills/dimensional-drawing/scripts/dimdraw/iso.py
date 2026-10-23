"""3-D views: pictorial (iso / dimetric / any angle) and model-driven
orthographic views, all drawn with exact hidden-line removal (hlr.py).

    m = Model()                                  # or build directly on the view
    m.extrude(rect_path(...), 0, 30, fillet=2)
    iv = sh.iso(700, 300, 0.8, yaw=-35, pitch=30, model=m)
    fv = sh.model_view(m, "front", x=300, y=300, scale=1.0)
    fv.dim_h(m.point("min", "min", "mid"), m.point("max", "min", "mid"), offset=-12)

Model axes: X right, Y up, Z toward the viewer of the front view. The iso
camera turns the model by `yaw` about Y (positive shows the right side) and then
by `pitch` about X (positive shows the top); `pre` rotations apply first.
"""

import math

from . import hlr, mesh as M
from .geom import fmt, hatch_segments, rect_path
from .view import View, Shape, PROJECTION

ISO_PITCH = math.degrees(math.atan(1 / math.sqrt(2)))  # 35.264
WHEEL_PARTS = ("tire", "tyre", "wheel", "rim", "hub", "lug", "brake")


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


_AX = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}


def projection_matrix(kind):
    """Rotation for a third-angle orthographic view (rows: view x, view y, toward viewer)."""
    (a, sa), (b, sb) = PROJECTION[kind]
    r0 = tuple(sa * c for c in _AX[a])
    r1 = tuple(sb * c for c in _AX[b])
    r2 = M.v_cross(r0, r1)
    return (r0, r1, r2)


def camera_matrix(yaw=45.0, pitch=ISO_PITCH, roll=0.0, pre=()):
    m = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    for axis, deg in pre:
        m = _mm(M.rot_matrix(axis, deg), m)
    m = _mm(M.rot_matrix("z", roll), m)
    m = _mm(M.rot_matrix("y", -yaw), m)
    m = _mm(M.rot_matrix("x", pitch), m)
    return m


class IsoView(View):
    """Pictorial view of a Model. Builder methods (extrude, box, cylinder,
    revolve, loft, sweep, sphere, ellipsoid, torus, capsule, load, mesh) add to
    the view's model and return the Mesh."""

    def __init__(self, sheet, x, y, scale, name, yaw=45.0, pitch=ISO_PITCH, roll=0.0, pre=(),
                 model=None, hidden=False, R=None, intersections=True, min_line=0.5):
        super().__init__(sheet, x, y, scale, name)
        self.min_line = min_line   # drop visible fragments shorter than this (sheet mm): noise
        self.pictorial = R is None     # iso / any-angle camera: no dimensions
        self.R = R if R is not None else camera_matrix(yaw, pitch, roll, pre)
        self.model = model if model is not None else M.Model(name)
        self.hidden = hidden
        self.intersections = intersections
        self.free_lines = []
        self._rendered = False
        self.result = None
        sheet._finalizers.append(self.render)

    # ---- projection ---------------------------------------------------------------
    def cam(self, p):
        R = self.R
        return (R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2],
                R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2],
                R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2])

    def _p2(self, p):
        if isinstance(p, Shape):
            return p.center
        if len(p) == 3:
            c = self.cam(p)
            return (c[0], c[1])
        return (float(p[0]), float(p[1]))

    def P(self, p):
        return self.tf.pt(self._p2(p))

    def S(self, p):
        return self.tf.pt(self._p2(p))

    def depth(self, p):
        return self.cam(p)[2]

    # ---- builders (delegate to the model) ------------------------------------------
    def extrude(self, profile, z0, z1, plane="xy", **kw):
        kw.pop("fill", None)
        return self.model.extrude(profile, z0, z1, plane, **kw)

    def box(self, center, size, **kw):
        kw.pop("fill", None)
        return self.model.box(center, size, **kw)

    def cylinder(self, center, r, h, **kw):
        return self.model.cylinder(center, r, h, **kw)

    def revolve(self, profile, **kw):
        return self.model.revolve(profile, **kw)

    def loft(self, sections, **kw):
        return self.model.loft(sections, **kw)

    def sweep(self, profile, path, **kw):
        return self.model.sweep(profile, path, **kw)

    def sphere(self, center, r, **kw):
        return self.model.sphere(center, r, **kw)

    def ellipsoid(self, center, radii, **kw):
        return self.model.ellipsoid(center, radii, **kw)

    def torus(self, center, R, r, **kw):
        return self.model.torus(center, R, r, **kw)

    def capsule(self, center, r, length, **kw):
        return self.model.capsule(center, r, length, **kw)

    def load(self, path, **kw):
        return self.model.load(path, **kw)

    def mesh(self, verts, faces, **kw):
        return self.model.mesh(verts, faces, **kw)

    def add(self, mesh):
        return self.model.add(mesh)

    def line3d(self, p1, p2, style="thin"):
        """Free 3-D line; hidden where solids cover it."""
        self.free_lines.append(([tuple(p1), tuple(p2)], style))

    # ---- extents ---------------------------------------------------------------------
    def extent(self):
        """(x0, y0, x1, y1) of the projected model in view coordinates."""
        xs, ys = [], []
        for m in self.model.meshes:
            for p in m.v:
                c = self.cam(p)
                xs.append(c[0])
                ys.append(c[1])
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def bbox(self):
        """The projected model's bounding box as a Shape (not drawn): use its
        anchors (tl, tr, bl, br, top_mid, ...) for overall dimensions and `ref=`."""
        x0, y0, x1, y1 = self.extent()
        return Shape(self, rect_path(x0, y0, x1, y1), "rect")

    def extent_by_mesh(self):
        """[(mesh name, (x0, y0, x1, y1) on the sheet)] for every drawn mesh."""
        out = []
        for m in self.model.meshes:
            if not m.v:
                continue
            pts = [self.S(p) for p in m.v]
            xs = [q[0] for q in pts]
            ys = [q[1] for q in pts]
            out.append((m.name, (min(xs), min(ys), max(xs), max(ys))))
        return out

    def ref_circle(self, center, d):
        """A reference circle (not drawn) for a round feature seen face-on in this
        view (hole, knob, lens, wheel): pass it to diameter() or center_mark().
        center: 3-D model point of the feature's centre; d: its diameter."""
        from .geom import circle_path
        cx, cy = self._p2(center)
        r = d / 2.0
        self._circles.append(d)
        return Shape(self, circle_path(cx, cy, r), "circle", r=r, d=d, _cx=cx, _cy=cy)

    # ---- rendering -------------------------------------------------------------------
    def _meshes_for_render(self):
        ms = list(self.model.meshes)
        if self.free_lines:
            free = M.Mesh("free-lines")
            for pts, st in self.free_lines:
                free.line(pts, st)
            ms.append(free)
        return ms, None, None

    def _ready(self):
        if not self._rendered:
            self.render()

    def _signature(self):
        ms = self.model.meshes
        return (len(ms), sum(len(m.f) for m in ms), sum(len(m.v) for m in ms),
                sum(len(m.lines) for m in ms), len(self.free_lines), getattr(self, "section", None))

    def render(self):
        sig = self._signature()
        if self._rendered:
            if sig == self._sig:
                return
            # the model changed after the first annotation: draw it again
            sh = self.sheet
            pre = (f"{self.name}:model", f"{self.name}:hatch")
            sh.items = [it for it in sh.items if not str(it.get("owner") or "").startswith(pre)]
            self._geom_bb = None
            for it in sh.items:
                if it.get("layer") == "geom" and str(it.get("owner") or "").startswith(self.name + ":"):
                    for pl in it.get("lines") or ():
                        for q in pl:
                            self._grow_bb(q)
        self._rendered = True
        self._sig = sig
        meshes, caps, cap_depth = self._meshes_for_render()
        meshes = [m for m in meshes if m.f or m.lines]
        solid = [m for m in meshes if m.f]
        res = hlr.render(meshes, self.R, hidden=self.hidden, caps=caps, cap_depth=cap_depth,
                         intersections=self.intersections and len(solid) > 1)
        self.result = res
        lim = self.min_line * self.sheet.k

        def long_enough(pts):
            return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])) >= lim
        for st, pl in res.visible:
            pts = [self.tf.pt(p) for p in pl]
            if long_enough(pts):
                self._emit_polyline(pts, st)
        for pl in res.hidden:
            pts = [self.tf.pt(p) for p in pl]
            if long_enough(pts):
                self._emit_polyline(pts, "hidden")
        self._after_render()

    def _after_render(self):
        pass

    def _emit_polyline(self, pts, style):
        sh = self.sheet
        lines = [pts]
        if self.clip:
            from .view import _clip_polylines
            lines = _clip_polylines(lines, self.clip)
        if not lines:
            return
        w, dash = sh.linestyle(style)
        d = " ".join("M" + " L".join(f"{fmt(p[0])} {fmt(p[1])}" for p in pl) for pl in lines)
        sh.add_path(d, w=w, dash=dash, lines=lines, owner=f"{self.name}:model", layer="geom",
                    kind="geom", cap="butt" if dash else None)
        for pl in lines:
            for q in pl:
                self._grow_bb(q)


class ModelView(IsoView):
    """Orthographic third-angle view of a Model (front, back, left, right, top,
    bottom), drawn with hidden-line removal and dimensioned with 3-D points:
    dim_h / dim_v measure along the view's axes. section=value cuts the model
    with a plane perpendicular to the view direction (at that coordinate of
    the product axis the view looks along) and hatches the cut faces."""

    def __init__(self, sheet, model, kind, x, y, scale, name=None, hidden=False, section=None,
                 center=(0.0, 0.0), hatch_spacing=None, hatch_angles=(45, -45, 30, -30, 60),
                 intersections=True, min_line=0.5):
        R = projection_matrix(kind)
        ox, oy = x - scale * center[0], y + scale * center[1]
        super().__init__(sheet, ox, oy, scale, name or kind, model=model, hidden=hidden, R=R,
                         intersections=intersections, min_line=min_line)
        self.kind = kind
        self.section = section
        self.hatch_spacing = hatch_spacing
        self.hatch_angles = hatch_angles
        self._cap_loops = []

    def projected(self, kind, at, name=None, **kw):
        """Another third-angle view of the same model, aligned with this one."""
        if kind in ("left", "right", "back"):
            v = self.sheet.model_view(self.model, kind, at, self.tf.oy, self.scale,
                                      name=name or kind, **kw)
        elif kind in ("top", "bottom"):
            v = self.sheet.model_view(self.model, kind, self.tf.ox, at, self.scale,
                                      name=name or kind, **kw)
        else:
            raise ValueError(f"unknown projection {kind!r}")
        v.parent, v.relation = self, kind
        return v

    def ramp_angle(self, axle, tire_r, toward="left", exclude=WHEEL_PARTS, r=None, decimals=1,
                   label=None, overrun=22.0, draw=True):
        """Approach / departure angle of a vehicle in a side view: the steepest
        ramp, touching the tire, that clears every part beyond the axle in the
        `toward` direction ('left' or 'right' on the sheet). Draws the ground and
        ramp lines (construction lines) out past the end of the vehicle and the
        angle there, in open space; returns (angle in degrees, the limiting
        point in view coordinates).
        axle: 3-D wheel centre; tire_r: tire radius; exclude: substrings of mesh
        names that belong to the wheels (default tire, wheel, rim, hub, lug,
        brake); r: arc radius in sheet mm (default: just past the vehicle end);
        overrun: sheet mm the lines run past the arc."""
        if self.kind in ("top", "bottom"):
            raise ValueError("ramp_angle needs a side elevation (front, back, left or right kind)")
        cx, cy = self._p2(axle)
        s = -1.0 if toward == "left" else 1.0
        best = None
        end = 0.0
        for m in self.model.meshes:
            if any(e in m.name.lower() for e in exclude):
                continue
            for p in m.v:
                u, v = self._p2(p)
                dx, dy = (u - cx) * s, v - cy
                if dx <= 0:
                    continue
                end = max(end, dx)
                rho = math.hypot(dx, dy)
                if rho <= tire_r * 1.0001:
                    continue
                th = math.asin(tire_r / rho) - math.atan2(-dy, dx)
                if best is None or th < best[0]:
                    best = (th, dx, dy)
        if best is None:
            raise ValueError("ramp_angle: no part found beyond the axle on that side")
        th, pdx, pdy = best
        deg = math.degrees(th)

        def back(dx, dy):
            return (cx + s * dx, cy + dy)
        lim = back(pdx, pdy)
        if not draw:
            return deg, lim
        k = self.sheet.k
        gx = tire_r * math.tan(th / 2)                    # the ramp meets the ground here
        G = back(gx, -tire_r)
        rr = r if r is not None else (end - gx) * self.scale + 7.0 * k
        run = (rr + overrun * k) / self.scale
        ramp_end = back(gx + run * math.cos(th), -tire_r + run * math.sin(th))
        ground_end = back(gx + run, -tire_r)
        self.construction_line(back(0.0, -tire_r), ground_end)
        self.construction_line(G, ramp_end)
        self.angle(G, ground_end, ramp_end, r=rr, decimals=decimals, label=label, ext=False)
        return deg, lim

    def _meshes_for_render(self):
        ms, _, _ = super()._meshes_for_render()
        if self.section is None:
            return ms, None, None
        view = self.R[2]
        axis = max(range(3), key=lambda i: abs(view[i]))
        p0 = [0.0, 0.0, 0.0]
        p0[axis] = float(self.section)
        out = []
        caps = []
        self._cap_loops = []
        for m in ms:
            if not m.f:
                out.append(m)
                continue
            cut, loops = m.cut(tuple(p0), view)
            if cut.f:
                out.append(cut)
            if loops:
                loops2 = [[self._p2(p) for p in lp] for lp in loops]
                caps.extend(loops2)
                self._cap_loops.append(loops2)
        depth = sum(view[i] * p0[i] for i in range(3))
        return out, caps, depth

    def _after_render(self):
        sh = self.sheet
        sp = sh.st("hatch_spacing") if self.hatch_spacing is None else self.hatch_spacing
        from .hlr import _cap_hidden
        done = []      # cut regions already hatched: the first part wins where parts overlap
        for k, loops in enumerate(self._cap_loops):
            rings = [[self.tf.pt(p) for p in lp] for lp in loops]
            segs = hatch_segments(rings, self.hatch_angles[k % len(self.hatch_angles)], sp)
            if done:
                kept = []
                for a, b in segs:
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    hid = sorted(iv for prev in done for iv in _cap_hidden(prev, a[0], a[1], dx, dy))
                    t = 0.0
                    for t0, t1 in hid:
                        if t0 > t + 1e-9:
                            kept.append(((a[0] + dx * t, a[1] + dy * t), (a[0] + dx * t0, a[1] + dy * t0)))
                        t = max(t, t1)
                    if t < 1 - 1e-9:
                        kept.append(((a[0] + dx * t, a[1] + dy * t), b))
                segs = kept
            done.append(rings)
            if self.clip:
                from .view import _clip_seg
                segs = [c for c in (_clip_seg(a, b, self.clip) for a, b in segs) if c]
            if not segs:
                continue
            d = " ".join(f"M{fmt(a[0])} {fmt(a[1])} L{fmt(b[0])} {fmt(b[1])}" for a, b in segs)
            sh.add_path(d, w=sh.st("thin"), lines=[[a, b] for a, b in segs],
                        owner=f"{self.name}:hatch#{k}", layer="geom", kind="hatch", cap="butt")
            sh.items[-1]["rings"] = rings
