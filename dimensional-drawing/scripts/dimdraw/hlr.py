"""Analytic hidden-line removal for triangle meshes (orthographic camera).

Lines that can appear in a drawing:
  * crease edges   - mesh edges whose faces meet at more than the mesh's crease
                     angle (box edges, cylinder caps, the cut outline of a section)
  * boundary edges - edges of open meshes
  * contours       - smooth silhouettes, interpolated inside triangles from the
                     corner normals (so a sphere's outline is a smooth curve, not
                     a staircase of mesh edges)
  * feature lines  - tangent edges and decals the builders attach to meshes
  * intersections  - curves where two different meshes pass through each other

Each line is clipped exactly against every triangle in front of it (planar
triangles + orthographic projection make both the coverage and the depth test
linear along the segment). A screen-space grid keeps it fast in pure Python.
"""

import math

from .mesh import v_cross, v_dot, v_unit


def _mv(R, p):
    return (R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2],
            R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2],
            R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2])


class Result:
    def __init__(self):
        self.visible = []   # (style, [(x, y), ...]) polylines, camera units
        self.hidden = []    # [(x, y), ...] polylines
        self.stats = {}


def render(meshes, R, hidden=False, caps=None, cap_depth=None, intersections=True,
           silhouettes="auto"):
    """meshes: list of Mesh. R: 3x3 rotation (camera = R @ model; camera x right,
    y up, z toward the viewer). caps: optional list of 2-D loops (camera xy) of
    section faces at depth cap_depth that hide everything behind them.
    silhouettes: "edges" (mesh edges between front- and back-facing faces;
    exact for axis-aligned views of these meshes), "interp" (smooth contours
    interpolated inside triangles; best for oblique views) or "auto".
    Returns a Result with visible (and optionally hidden) polylines."""
    view = (R[2][0], R[2][1], R[2][2])
    if silhouettes == "auto":
        silhouettes = "edges" if max(abs(c) for c in view) > 0.99999 else "interp"
    # ---- occluders --------------------------------------------------------------
    OX0, OY0, OX1, OY1, OX2, OY2 = [], [], [], [], [], []
    PA, PB, PC, ZMAX = [], [], [], []
    BX0, BY0, BX1, BY1 = [], [], [], []
    gid = []        # per mesh: face index -> occluder id (or -1)
    cams = []
    fronts = []
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for m in meshes:
        top = m.topology()
        cv = [_mv(R, p) for p in m.v]
        cams.append(cv)
        for p in cv:
            for i in range(3):
                if p[i] < lo[i]:
                    lo[i] = p[i]
                if p[i] > hi[i]:
                    hi[i] = p[i]
        fn = top["fn"]
        front = [view[0] * n[0] + view[1] * n[1] + view[2] * n[2] > 1e-9 for n in fn]
        fronts.append(front)
        two_sided = not top["closed"]
        ids = []
        for fi, (a, b, c) in enumerate(m.f):
            if not (front[fi] or two_sided):
                ids.append(-1)
                continue
            x0, y0, z0 = cv[a]
            x1, y1, z1 = cv[b]
            x2, y2, z2 = cv[c]
            D = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if abs(D) < 1e-14:
                ids.append(-1)
                continue
            if D < 0:
                x1, y1, z1, x2, y2, z2 = x2, y2, z2, x1, y1, z1
                D = -D
            pa = ((z1 - z0) * (y2 - y0) - (z2 - z0) * (y1 - y0)) / D
            pb = ((x1 - x0) * (z2 - z0) - (x2 - x0) * (z1 - z0)) / D
            ids.append(len(OX0))
            OX0.append(x0); OY0.append(y0); OX1.append(x1); OY1.append(y1); OX2.append(x2); OY2.append(y2)  # noqa: E702
            PA.append(pa); PB.append(pb); PC.append(z0 - pa * x0 - pb * y0)  # noqa: E702
            ZMAX.append(max(z0, z1, z2))
            BX0.append(min(x0, x1, x2)); BY0.append(min(y0, y1, y2))  # noqa: E702
            BX1.append(max(x0, x1, x2)); BY1.append(max(y0, y1, y2))  # noqa: E702
        gid.append(ids)
    if lo[0] == float("inf"):
        return Result()
    diag = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))
    eps = max(1e-7, 2e-5 * diag)
    n_occ = len(OX0)
    # ---- screen grid --------------------------------------------------------------
    W = max(hi[0] - lo[0], 1e-9)
    H = max(hi[1] - lo[1], 1e-9)
    cells = max(1, min(160, int(math.sqrt(max(n_occ, 1) / 2.0))))
    cs = max(W, H) / cells
    nx = int(W / cs) + 1
    ny = int(H / cs) + 1
    gx0, gy0 = lo[0], lo[1]
    grid = [[] for _ in range(nx * ny)]
    for g in range(n_occ):
        i0 = int((BX0[g] - gx0) / cs)
        i1 = int((BX1[g] - gx0) / cs)
        j0 = int((BY0[g] - gy0) / cs)
        j1 = int((BY1[g] - gy0) / cs)
        for j in range(max(j0, 0), min(j1, ny - 1) + 1):
            row = j * nx
            for i in range(max(i0, 0), min(i1, nx - 1) + 1):
                grid[row + i].append(g)
    stamp = [0] * n_occ
    # ---- candidate lines ----------------------------------------------------------
    cands = []    # (A, B, style, excluded occluder ids)

    def ring_ids(mi, vids):
        vf = meshes[mi].topology()["vf"]
        ids = gid[mi]
        out = set()
        for v in vids:
            for f in vf[v]:
                g = ids[f]
                if g >= 0:
                    out.add(g)
        return out

    for mi, m in enumerate(meshes):
        top = m.topology()
        cv = cams[mi]
        fn = top["fn"]
        front = fronts[mi]
        cosc = math.cos(math.radians(m.crease))
        closed = top["closed"]
        style = m.style
        for (i, j), fs in top["edges"].items():
            if len(fs) == 1:
                if front[fs[0]] or not closed:
                    cands.append((cv[i], cv[j], style, ring_ids(mi, (i, j))))
                continue
            n1, n2 = fn[fs[0]], fn[fs[1]]
            crease = len(fs) > 2 or (n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]) < cosc
            if crease and (front[fs[0]] or front[fs[1]] or not closed):
                cands.append((cv[i], cv[j], style, ring_ids(mi, (i, j))))
            elif not crease and silhouettes == "edges" and front[fs[0]] != front[fs[1]]:
                cands.append((cv[i], cv[j], style, ring_ids(mi, (i, j))))
        if silhouettes == "edges":
            pass
        # smooth silhouettes from corner normals
        cn = top["cn"]
        for fi, (a, b, c) in enumerate(m.f if silhouettes == "interp" else ()):
            ns = cn[fi]
            g0 = view[0] * ns[0][0] + view[1] * ns[0][1] + view[2] * ns[0][2]
            g1 = view[0] * ns[1][0] + view[1] * ns[1][1] + view[2] * ns[1][2]
            g2 = view[0] * ns[2][0] + view[1] * ns[2][1] + view[2] * ns[2][2]
            s0, s1, s2 = g0 >= 0, g1 >= 0, g2 >= 0
            if s0 == s1 == s2:
                continue
            pts = []
            for (va, ga, sa), (vb, gb, sb) in (((a, g0, s0), (b, g1, s1)), ((b, g1, s1), (c, g2, s2)),
                                               ((c, g2, s2), (a, g0, s0))):
                if sa != sb:
                    t = ga / (ga - gb)
                    pa_, pb_ = cv[va], cv[vb]
                    pts.append((pa_[0] + (pb_[0] - pa_[0]) * t, pa_[1] + (pb_[1] - pa_[1]) * t,
                                pa_[2] + (pb_[2] - pa_[2]) * t))
            if len(pts) == 2:
                # contours sit on folding, nearly edge-on bands: exclude two rings of
                # neighbours so thin adjacent faces can't nibble gaps out of them
                vf = top["vf"]
                ring1 = {v for f in set(vf[a]) | set(vf[b]) | set(vf[c]) for v in m.f[f]}
                cands.append((pts[0], pts[1], style, ring_ids(mi, ring1)))
        # feature lines
        for pts, st, vids, hosts in m.lines:
            cp = [_mv(R, p) for p in pts]
            host_ex = None
            if not vids and hosts:
                # the host faces plus everything touching them (a decal on a cap)
                host_ex = {gid[mi][f] for f in hosts if gid[mi][f] >= 0}
                host_ex |= ring_ids(mi, {v for f in hosts for v in m.f[f]})
            for k in range(len(cp) - 1):
                if vids:
                    ex = ring_ids(mi, (vids[k], vids[min(k + 1, len(vids) - 1)]))
                else:
                    ex = host_ex or set()
                cands.append((cp[k], cp[k + 1], st, ex))
    if intersections and len(meshes) > 1:
        cands.extend(_intersections(meshes, R, gid, ring_ids))
    # ---- visibility ---------------------------------------------------------------
    res = Result()
    vis_segs = []
    hid_segs = []
    qid = 0
    cap_list = caps or []
    cap_d = cap_depth if cap_depth is not None else float("inf")
    for A, B, st, excl in cands:
        ax, ay, az = A
        bx, by, bz = B
        dx, dy, dz = bx - ax, by - ay, bz - az
        if dx * dx + dy * dy < 1e-18:
            continue
        sx0, sx1 = (ax, bx) if ax < bx else (bx, ax)
        sy0, sy1 = (ay, by) if ay < by else (by, ay)
        zmin = az if az < bz else bz
        qid += 1
        i0 = max(int((sx0 - gx0) / cs), 0)
        i1 = min(int((sx1 - gx0) / cs), nx - 1)
        j0 = max(int((sy0 - gy0) / cs), 0)
        j1 = min(int((sy1 - gy0) / cs), ny - 1)
        hid = []
        for j in range(j0, j1 + 1):
            row = j * nx
            for i in range(i0, i1 + 1):
                for g in grid[row + i]:
                    if stamp[g] == qid:
                        continue
                    stamp[g] = qid
                    if g in excl:
                        continue
                    if BX1[g] < sx0 or BX0[g] > sx1 or BY1[g] < sy0 or BY0[g] > sy1:
                        continue
                    if ZMAX[g] <= zmin + eps:
                        continue
                    t0, t1 = 0.0, 1.0
                    ok = True
                    for xi, yi, xj, yj in ((OX0[g], OY0[g], OX1[g], OY1[g]),
                                           (OX1[g], OY1[g], OX2[g], OY2[g]),
                                           (OX2[g], OY2[g], OX0[g], OY0[g])):
                        ex, ey = xj - xi, yj - yi
                        f0 = ex * (ay - yi) - ey * (ax - xi)
                        fd = ex * dy - ey * dx
                        if -1e-15 < fd < 1e-15:
                            if f0 < 0:
                                ok = False
                                break
                        elif fd > 0:
                            t = -f0 / fd
                            if t > t0:
                                t0 = t
                        else:
                            t = -f0 / fd
                            if t < t1:
                                t1 = t
                        if t0 >= t1:
                            ok = False
                            break
                    if not ok:
                        continue
                    z0 = PA[g] * ax + PB[g] * ay + PC[g] - az
                    zd = PA[g] * dx + PB[g] * dy - dz
                    if -1e-15 < zd < 1e-15:
                        if z0 <= eps:
                            continue
                    elif zd > 0:
                        t = (eps - z0) / zd
                        if t > t0:
                            t0 = t
                    else:
                        t = (eps - z0) / zd
                        if t < t1:
                            t1 = t
                    if t1 - t0 > 1e-9:
                        hid.append((t0, t1))
        if cap_list and min(az, bz) < cap_d - eps:
            hid.extend(_cap_hidden(cap_list, ax, ay, dx, dy))
        if not hid:
            vis_segs.append((st, (ax, ay), (bx, by)))
            continue
        hid.sort()
        merged = []
        for t0, t1 in hid:
            if merged and t0 <= merged[-1][1] + 1e-9:
                if t1 > merged[-1][1]:
                    merged[-1][1] = t1
            else:
                merged.append([t0, t1])
        t = 0.0
        for t0, t1 in merged:
            if t0 > t + 1e-6:
                vis_segs.append((st, (ax + dx * t, ay + dy * t), (ax + dx * t0, ay + dy * t0)))
            if hidden and t1 - t0 > 1e-6:
                hid_segs.append(((ax + dx * t0, ay + dy * t0), (ax + dx * t1, ay + dy * t1)))
            t = max(t, t1)
        if t < 1 - 1e-6:
            vis_segs.append((st, (ax + dx * t, ay + dy * t), (bx, by)))
    res.visible = _chain_styled(vis_segs, eps)
    res.hidden = _chain(_dedupe(hid_segs, max(diag * 0.004, 1e-6)), eps) if hidden else []
    res.stats = {"occluders": n_occ, "candidates": len(cands), "segments": len(vis_segs)}
    return res


def _cap_hidden(loops, ax, ay, dx, dy):
    """Parameter intervals of a 2-D segment inside even-odd loops."""
    ts = [0.0, 1.0]
    for loop in loops:
        n = len(loop)
        for k in range(n - 1 if loop[0] == loop[-1] else n):
            x1, y1 = loop[k]
            x2, y2 = loop[(k + 1) % n]
            ex, ey = x2 - x1, y2 - y1
            den = dx * ey - dy * ex
            if abs(den) < 1e-15:
                continue
            t = ((x1 - ax) * ey - (y1 - ay) * ex) / den
            u = ((x1 - ax) * dy - (y1 - ay) * dx) / den
            if 0 < t < 1 and 0 <= u <= 1:
                ts.append(t)
    ts.sort()
    out = []
    for t0, t1 in zip(ts, ts[1:]):
        if t1 - t0 < 1e-9:
            continue
        tm = (t0 + t1) / 2
        if _inside(loops, ax + dx * tm, ay + dy * tm):
            out.append((t0, t1))
    return out


def _inside(loops, x, y):
    inside = False
    for loop in loops:
        n = len(loop)
        for k in range(n):
            x1, y1 = loop[k]
            x2, y2 = loop[(k + 1) % n]
            if (y1 > y) != (y2 > y):
                if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
    return inside


def _intersections(meshes, R, gid, ring_ids, tag=False):
    """Curves where triangles of different meshes cross each other. With
    tag=True returns (p, q, mesh_a, mesh_b) in model space instead."""
    out = []
    boxes = [m.bounds() for m in meshes]
    for a in range(len(meshes)):
        for b in range(a + 1, len(meshes)):
            (alo, ahi), (blo, bhi) = boxes[a], boxes[b]
            if any(ahi[i] < blo[i] or bhi[i] < alo[i] for i in range(3)):
                continue
            lo = [max(alo[i], blo[i]) for i in range(3)]
            hi = [min(ahi[i], bhi[i]) for i in range(3)]
            segs = _mesh_pair(meshes[a], meshes[b], a, b, lo, hi, R, ring_ids)
            if tag:
                out.extend((p, q, a, b) for p, q, _st, _ex in segs)
            else:
                out.extend(segs)
    return out


def _tri_box(V, f):
    p, q, r = V[f[0]], V[f[1]], V[f[2]]
    return (min(p[0], q[0], r[0]), min(p[1], q[1], r[1]), min(p[2], q[2], r[2]),
            max(p[0], q[0], r[0]), max(p[1], q[1], r[1]), max(p[2], q[2], r[2]))


def _mesh_pair(A, B, ia, ib, lo, hi, R, ring_ids):
    VA, VB = A.v, B.v
    size = max(hi[i] - lo[i] for i in range(3))
    pad = 1e-9 + 1e-7 * size
    fa = []
    for i, f in enumerate(A.f):
        bb = _tri_box(VA, f)
        if all(bb[k] <= hi[k] + pad and bb[k + 3] >= lo[k] - pad for k in range(3)):
            fa.append((i, bb))
    fb = []
    for i, f in enumerate(B.f):
        bb = _tri_box(VB, f)
        if all(bb[k] <= hi[k] + pad and bb[k + 3] >= lo[k] - pad for k in range(3)):
            fb.append((i, bb))
    if not fa or not fb:
        return []
    n = max(len(fb), 1)
    cs = max(size / max(1, int(round(n ** (1 / 3.0)))), 1e-9)
    grid = {}
    for i, bb in fb:
        for x in range(int((bb[0] - lo[0]) // cs), int((bb[3] - lo[0]) // cs) + 1):
            for y in range(int((bb[1] - lo[1]) // cs), int((bb[4] - lo[1]) // cs) + 1):
                for z in range(int((bb[2] - lo[2]) // cs), int((bb[5] - lo[2]) // cs) + 1):
                    grid.setdefault((x, y, z), []).append(i)
    topA, topB = A.topology(), B.topology()
    eps = 1e-9 * max(size, 1.0) + 1e-12
    out = []
    for i, bb in fa:
        seen = set()
        for x in range(int((bb[0] - lo[0]) // cs), int((bb[3] - lo[0]) // cs) + 1):
            for y in range(int((bb[1] - lo[1]) // cs), int((bb[4] - lo[1]) // cs) + 1):
                for z in range(int((bb[2] - lo[2]) // cs), int((bb[5] - lo[2]) // cs) + 1):
                    for j in grid.get((x, y, z), ()):
                        if j in seen:
                            continue
                        seen.add(j)
                        seg = _tri_tri(VA, A.f[i], topA["fn"][i], VB, B.f[j], topB["fn"][j], eps)
                        if seg:
                            p, q = seg
                            ex = ring_ids(ia, A.f[i]) | ring_ids(ib, B.f[j])
                            out.append((_mv(R, p), _mv(R, q), A.style, ex))
    return out


def _tri_tri(VA, fa, na, VB, fb, nb, eps):
    """Intersection segment of two triangles (None if they don't properly cross)."""
    if abs(v_dot(na, nb)) > 0.995:
        return None  # (nearly) parallel: grazing contact, numerically meaningless
    a0, a1, a2 = VA[fa[0]], VA[fa[1]], VA[fa[2]]
    b0, b1, b2 = VB[fb[0]], VB[fb[1]], VB[fb[2]]
    db = v_dot(nb, b0)
    da = [v_dot(nb, p) - db for p in (a0, a1, a2)]
    if (da[0] > eps and da[1] > eps and da[2] > eps) or (da[0] < -eps and da[1] < -eps and da[2] < -eps):
        return None
    dA = v_dot(na, a0)
    dbv = [v_dot(na, p) - dA for p in (b0, b1, b2)]
    if (dbv[0] > eps and dbv[1] > eps and dbv[2] > eps) or (dbv[0] < -eps and dbv[1] < -eps and dbv[2] < -eps):
        return None
    # touching (a vertex exactly on the other plane, no crossing) is not an intersection
    if not ((max(da) > eps and min(da) < -eps) and (max(dbv) > eps and min(dbv) < -eps)):
        return None
    L = v_unit(v_cross(na, nb))

    def interval(P, d):
        pts = []
        for k in range(3):
            p, q = P[k], P[(k + 1) % 3]
            dp, dq = d[k], d[(k + 1) % 3]
            if (dp > 0) != (dq > 0) and abs(dp - dq) > 1e-18:
                t = dp / (dp - dq)
                pts.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, p[2] + (q[2] - p[2]) * t))
        if len(pts) < 2:
            return None
        s = [v_dot(L, p) for p in pts]
        if s[0] > s[1]:
            pts = [pts[1], pts[0]]
            s = [s[1], s[0]]
        return pts[0], pts[1], s[0], s[1]
    ia = interval((a0, a1, a2), da)
    ib = interval((b0, b1, b2), dbv)
    if not ia or not ib:
        return None
    s0 = max(ia[2], ib[2])
    s1 = min(ia[3], ib[3])
    if s1 - s0 <= eps:
        return None
    p0 = ia[0] if ia[2] >= ib[2] else ib[0]
    p1 = ia[1] if ia[3] <= ib[3] else ib[1]
    return p0, p1


def _dedupe(segs, cell):
    """Drop segments lying on top of already kept ones (coincident hidden lines
    with out-of-phase dashes read as solid lines)."""
    order = sorted(segs, key=lambda s: -((s[1][0] - s[0][0]) ** 2 + (s[1][1] - s[0][1]) ** 2))
    occ = set()
    out = []
    for a, b in order:
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(2, int(L / cell) + 1)
        keys = [(int((a[0] + (b[0] - a[0]) * i / (n - 1)) // cell),
                 int((a[1] + (b[1] - a[1]) * i / (n - 1)) // cell)) for i in range(n)]
        covered = sum(1 for k in keys if k in occ)
        if covered >= 0.8 * n:
            continue
        out.append((a, b))
        for kx, ky in keys:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    occ.add((kx + dx, ky + dy))
    return out


def _key(p, q):
    return (round(p[0] / q), round(p[1] / q))


def _chain(segs, eps):
    """Join segments sharing endpoints into polylines."""
    if not segs:
        return []
    q = max(eps * 2, 1e-7)
    ends = {}
    for i, (a, b) in enumerate(segs):
        ends.setdefault(_key(a, q), []).append((i, 0))
        ends.setdefault(_key(b, q), []).append((i, 1))
    used = [False] * len(segs)
    out = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        a, b = segs[i]
        line = [a, b]
        for direction in (1, 0):
            while True:
                tip = line[-1] if direction == 1 else line[0]
                nxt = None
                for j, end in ends.get(_key(tip, q), ()):
                    if not used[j]:
                        nxt = (j, end)
                        break
                if nxt is None:
                    break
                j, end = nxt
                used[j] = True
                p = segs[j][1] if end == 0 else segs[j][0]
                if direction == 1:
                    line.append(p)
                else:
                    line.insert(0, p)
        out.append(line)
    return out


def _chain_styled(segs, eps):
    by = {}
    for st, a, b in segs:
        by.setdefault(st, []).append((a, b))
    out = []
    for st, ss in by.items():
        for pl in _chain(ss, eps):
            out.append((st, pl))
    return out
