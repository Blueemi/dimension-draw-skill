"""Layout checks: catches the mistakes that make a drawing look wrong or read
wrong, so an agent can fix them before anyone sees the sheet.

  ERROR  text overlapping text, anything outside the frame, drawing content
         inside the notes / title block / revision areas
  WARN   text crossed by a line it does not own, a typed dimension value that
         disagrees with the geometry, views whose geometry overlaps
"""

import math
import re
from collections import defaultdict

from .annot import fmt_num

CELL = 5.0
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _aabb(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return (min(xs), min(ys), max(xs), max(ys))


def _shrink(b, m):
    return (b[0] + m, b[1] + m, b[2] - m, b[3] - m)


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _seg_hits_box(p, q, b):
    """Liang-Barsky segment vs axis-aligned box."""
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


def _owner_label(o):
    if not o:
        return "?"
    return re.sub(r"#\w+$", "", str(o))


def run_checks(sh, verbose=True):
    problems = []
    texts = []
    segs = []
    for it in sh.items:
        if it["t"] == "text":
            b = _aabb(it["box"])
            texts.append((b, it))
        elif it.get("lines") and it.get("check", True) and it["layer"] != "frame":
            for pl in it["lines"]:
                for i in range(len(pl) - 1):
                    segs.append((pl[i], pl[i + 1], it))
    # spatial hash of segments
    grid = defaultdict(list)
    for si, (p, q, it) in enumerate(segs):
        x0, x1 = sorted((p[0], q[0]))
        y0, y1 = sorted((p[1], q[1]))
        for gx in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
            for gy in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                grid[(gx, gy)].append(si)

    # 1. text vs text (overlap = ERROR, closer than `clear` mm = WARN)
    clear = 0.5 * sh.k
    tg = defaultdict(list)
    for ti, (b, it) in enumerate(texts):
        for gx in range(int(b[0] // CELL), int(b[2] // CELL) + 1):
            for gy in range(int(b[1] // CELL), int(b[3] // CELL) + 1):
                tg[(gx, gy)].append(ti)
    seen = set()
    for idxs in tg.values():
        for a in range(len(idxs)):
            for c in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[c]
                key = (min(i, j), max(i, j))
                if key in seen:
                    continue
                seen.add(key)
                bi, ii = texts[i]
                bj, ij = texts[j]
                if ii["owner"] == ij["owner"] and ii["owner"] is not None:
                    continue
                if not (ii.get("check", True) or ij.get("check", True)):
                    continue
                if _overlap(_shrink(bi, 0.15), _shrink(bj, 0.15)):
                    problems.append({
                        "level": "ERROR",
                        "msg": (f"text '{ii['s']}' ({_owner_label(ii['owner'])}) overlaps text "
                                f"'{ij['s']}' ({_owner_label(ij['owner'])}) near "
                                f"({(bi[0] + bi[2]) / 2:.1f}, {(bi[1] + bi[3]) / 2:.1f})"),
                        "boxes": [bi, bj]})
                elif _overlap(_shrink(bi, -clear), bj):
                    gap = max(bj[0] - bi[2], bi[0] - bj[2], bj[1] - bi[3], bi[1] - bj[3], 0.0)
                    problems.append({
                        "level": "WARN",
                        "msg": (f"text '{ii['s']}' ({_owner_label(ii['owner'])}) nearly touches "
                                f"'{ij['s']}' ({_owner_label(ij['owner'])}), {gap:.2f} mm apart near "
                                f"({(bi[0] + bi[2]) / 2:.1f}, {(bi[1] + bi[3]) / 2:.1f})"),
                        "boxes": [bi, bj]})

    # 2. text crossed by foreign lines
    for b, it in texts:
        if not it.get("check", True):
            continue
        bb = _shrink(b, 0.2)
        hits = {}
        for gx in range(int(bb[0] // CELL), int(bb[2] // CELL) + 1):
            for gy in range(int(bb[1] // CELL), int(bb[3] // CELL) + 1):
                for si in grid.get((gx, gy), ()):
                    p, q, sit = segs[si]
                    if sit["owner"] == it["owner"]:
                        continue
                    if it.get("masked") and sit.get("kind") == "centerline":
                        continue
                    if id(sit) in hits:
                        continue
                    if _seg_hits_box(p, q, bb):
                        hits[id(sit)] = sit
        if hits:
            kinds = sorted({_owner_label(s["owner"]) + (" hatching" if s.get("kind") == "hatch" else "")
                            for s in hits.values()})
            problems.append({
                "level": "WARN",
                "msg": (f"text '{it['s']}' ({_owner_label(it['owner'])}) is crossed by "
                        f"{', '.join(kinds)} near ({(b[0] + b[2]) / 2:.1f}, {(b[1] + b[3]) / 2:.1f})"),
                "boxes": [b]})

    # 3. outside the frame
    fx0, fy0, fx1, fy1 = sh.fx0 + 0.5, sh.fy0 + 0.5, sh.fx1 - 0.5, sh.fy1 - 0.5
    for b, it in texts:
        if b[0] < fx0 or b[1] < fy0 or b[2] > fx1 or b[3] > fy1:
            problems.append({"level": "ERROR",
                             "msg": f"text '{it['s']}' ({_owner_label(it['owner'])}) leaves the frame",
                             "boxes": [b]})
    out_owner = {}
    for p, q, it in segs:
        for pt in (p, q):
            if pt[0] < fx0 or pt[1] < fy0 or pt[0] > fx1 or pt[1] > fy1:
                o = _owner_label(it["owner"])
                ob = out_owner.setdefault(o, [pt[0], pt[1], pt[0], pt[1]])
                ob[0], ob[1] = min(ob[0], pt[0]), min(ob[1], pt[1])
                ob[2], ob[3] = max(ob[2], pt[0]), max(ob[3], pt[1])
    for o, ob in out_owner.items():
        problems.append({"level": "ERROR", "msg": f"{o} extends outside the frame",
                         "boxes": [tuple(ob)]})

    # 4. reserved areas
    for name, x0, y0, x1, y1, owner in _reserved(sh):
        r = (x0, y0, x1, y1)
        bad = {}
        for b, it in texts:
            if it["owner"] and str(it["owner"]).startswith(owner):
                continue
            if _overlap(_shrink(b, 0.1), r):
                bad.setdefault(_owner_label(it["owner"]), b)
        for p, q, it in segs:
            if it["owner"] and str(it["owner"]).startswith(owner):
                continue
            if _seg_hits_box(p, q, r):
                bad.setdefault(_owner_label(it["owner"]), (min(p[0], q[0]), min(p[1], q[1]),
                                                           max(p[0], q[0]), max(p[1], q[1])))
        for o, b in bad.items():
            problems.append({"level": "ERROR", "msg": f"{o} intrudes into the {name}",
                             "boxes": [b, r]})

    # 5. typed values vs geometry
    for owner, s, value, dec in sh.verify:
        nums = [float(n) for n in _NUM.findall(s.replace(",", "."))]
        want = float(fmt_num(abs(value), dec))
        tol = 0.5 * 10 ** (-dec) + 1e-9
        # counts like the 2 in "2X" are ignored as long as some number matches
        if not any(abs(n - want) <= tol for n in nums):
            problems.append({"level": "WARN",
                             "msg": (f"{_owner_label(owner)}: text '{s}' does not match the "
                                     f"geometry, which measures {fmt_num(abs(value), dec)}"),
                             "boxes": []})

    # 6. overlapping views
    vb = [(v.name, v.bounds()) for v in sh.views if v.bounds()]
    for i in range(len(vb)):
        for j in range(i + 1, len(vb)):
            if _overlap(_shrink(vb[i][1], 0.5), _shrink(vb[j][1], 0.5)):
                problems.append({"level": "WARN",
                                 "msg": f"views {vb[i][0]} and {vb[j][0]} overlap",
                                 "boxes": [vb[i][1], vb[j][1]]})

    # 7. dimension ends must line up with something drawn in their view
    tol = 0.12 * sh.k
    marks = {}
    segs_by_view = {}
    for it in sh.items:
        if not it.get("lines") or it.get("kind") == "hatch":
            continue
        o = str(it.get("owner") or "")
        vname = o.split(":")[0]
        if it["layer"] == "geom" or it.get("kind") in ("centerline", "construction") or ":center" in o:
            xs_, ys_ = marks.setdefault(vname, ([], []))
            sg = segs_by_view.setdefault(vname, defaultdict(list))
            for pl in it["lines"]:
                for q in pl:
                    xs_.append(q[0])
                    ys_.append(q[1])
                for p_, q_ in zip(pl, pl[1:]):
                    for cx in range(int(min(p_[0], q_[0]) // 2), int(max(p_[0], q_[0]) // 2) + 1):
                        for cy in range(int(min(p_[1], q_[1]) // 2), int(max(p_[1], q_[1]) // 2) + 1):
                            sg[(cx, cy)].append((p_, q_))
    for k in marks:
        marks[k] = (sorted(marks[k][0]), sorted(marks[k][1]))
    import bisect

    def near(arr, v):
        i = bisect.bisect_left(arr, v - tol)
        return i < len(arr) and arr[i] <= v + tol

    def on_line(vname, P):
        sg = segs_by_view.get(vname)
        if not sg:
            return False
        for p_, q_ in sg.get((int(P[0] // 2), int(P[1] // 2)), ()):
            dx, dy = q_[0] - p_[0], q_[1] - p_[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((P[0] - p_[0]) * dx + (P[1] - p_[1]) * dy) / L2))
            if math.hypot(P[0] - p_[0] - dx * t, P[1] - p_[1] - dy * t) <= tol:
                return True
        return False
    for owner, P in getattr(sh, "floating", ()):
        problems.append({"level": "WARN",
                         "msg": (f"{_owner_label(owner)}: an extension line starts in empty space at "
                                 f"({P[0]:.1f}, {P[1]:.1f}), with no edge within reach along it; the "
                                 f"dimension point is probably off the part"),
                         "boxes": [(P[0] - 1, P[1] - 1, P[0] + 1, P[1] + 1)]})
    # overall dimensions vs. the drawn extent (a NOTE: Apple's own PRODUCT WIDTH /
    # THICKNESS exclude buttons and camera bumps, but a lip or lamp sticking out by
    # mistake shows up here too)
    overall_notes = []
    for view, owner, axis, P1, P2, text, label, overall in sh.dim_points:
        words = " ".join((label or "").upper().split())
        is_overall = "OVERALL" in words or any(
            f"PRODUCT {w}" in words for w in ("WIDTH", "LENGTH", "HEIGHT", "DEPTH", "THICKNESS"))
        if overall is not None:
            is_overall = overall
        if not is_overall or not view.bounds():
            continue
        bb = view.bounds()
        ext = (bb[2] - bb[0]) if axis == "h" else (bb[3] - bb[1])
        meas = abs(P2[0] - P1[0]) if axis == "h" else abs(P2[1] - P1[1])
        if abs(ext - meas) > 0.3 * sh.k:
            who = ""
            if hasattr(view, "extent_by_mesh"):
                lo_, hi_ = sorted((P1[0], P2[0]) if axis == "h" else (P1[1], P2[1]))
                out_ = set()
                for name, (x0, y0, x1, y1) in view.extent_by_mesh():
                    a_, b_ = (x0, x1) if axis == "h" else (y0, y1)
                    if a_ < lo_ - 0.3 * sh.k or b_ > hi_ + 0.3 * sh.k:
                        out_.add(name)
                if out_:
                    who = f" (past it: {', '.join(sorted(out_))})"
            overall_notes.append(
                f"'{text} {words.lower()}' ({view.name}) is smaller than the drawn "
                f"{'width' if axis == 'h' else 'height'} {ext / view.scale:.2f}{who}. Fine if "
                f"deliberate (buttons, bumps, mirrors: pass overall=False); otherwise dimension "
                f"the full envelope")
    for view, owner, axis, P1, P2, text, label, overall in sh.dim_points:
        xs_, ys_ = marks.get(view.name, ([], []))
        if not xs_:
            continue
        idx = 0 if axis == "h" else 1
        arr = xs_ if axis == "h" else ys_
        for P, end in ((P1, "first"), (P2, "second")):
            if not near(arr, P[idx]) and not on_line(view.name, P):
                problems.append({"level": "WARN",
                                 "msg": (f"{_owner_label(owner)}: the {end} point of '{text}' does not line "
                                         f"up with any edge or centre drawn in view '{view.name}' "
                                         f"({'x' if axis == 'h' else 'y'} = {P[idx]:.2f} on the sheet), so "
                                         f"the value may not measure what you meant "
                                         f"(snap=False if intended)"),
                                 "boxes": [(P[0] - 1, P[1] - 1, P[0] + 1, P[1] + 1)]})

    # 8. "4X" style counts must match the features drawn
    for view, owner, prefix, d in sh.counts:
        m_ = re.match(r"\s*(\d+)\s*[Xx]", prefix or "")
        if not m_:
            continue
        n = int(m_.group(1))
        have = sum(1 for c in getattr(view, "_circles", ()) if abs(c - d) < 0.005)
        if have and have < n:
            problems.append({"level": "WARN",
                             "msg": (f"{_owner_label(owner)}: '{prefix}' but view '{view.name}' draws only "
                                     f"{have} circle(s) of \u00d8{fmt_num(d, 2)}"),
                             "boxes": []})

    # 9. flag notes referenced must exist
    if sh.note_numbers is not None and not sh.notes_partial:
        for fl in sorted(sh.flags_used, key=str):
            if fl not in sh.note_numbers and str(fl) not in {str(n) for n in sh.note_numbers}:
                problems.append({"level": "WARN",
                                 "msg": f"flag [{fl}] is used on the sheet but NOTES has no note {fl}",
                                 "boxes": []})

    # 10. detail / section letters need their labelled views
    labelled = {(w, l) for w, l in sh.labels}
    for kind, letter, vname in sh.letters_used:
        if (kind, letter[:1]) not in labelled:
            problems.append({"level": "WARN",
                             "msg": (f"{kind.lower()} {letter} is marked in view '{vname}' but there is no "
                                     f"'{kind} {letter}' view label on this sheet (fine if it is on another sheet)"),
                             "boxes": []})

    # 11. projected views must line up with their parent
    for v in sh.views:
        par = getattr(v, "parent", None)
        if par is None or not v.bounds() or not par.bounds():
            continue
        a_, b_ = par.bounds(), v.bounds()
        if v.relation in ("left", "right", "back"):
            da, db = (a_[1], a_[3]), (b_[1], b_[3])
            what = "height"
        else:
            da, db = (a_[0], a_[2]), (b_[0], b_[2])
            what = "width"
        if abs(da[0] - db[0]) > 0.5 * sh.k or abs(da[1] - db[1]) > 0.5 * sh.k:
            problems.append({"level": "WARN",
                             "msg": (f"views '{par.name}' and '{v.name}' ({v.relation} view) disagree on "
                                     f"{what}: {da[1] - da[0]:.1f} vs {db[1] - db[0]:.1f} sheet mm, or are "
                                     f"not aligned - projected views must line up"),
                             "boxes": [a_, b_]})

    notes = []
    seen_models = set()
    for v in sh.views:
        mdl = getattr(v, "model", None)
        if mdl is None or id(mdl) in seen_models:
            continue
        seen_models.add(id(mdl))
        inter = []
        if len(mdl.meshes) > 1:
            try:
                inter = mdl.interferences()
            except Exception as exc:  # never let a diagnostic break a save
                notes.append(f"could not check interferences of model '{mdl.name}': {exc}")
        for mesh_ in mdl.meshes:
            for msg in mesh_.health():
                if "open surface" in msg:
                    notes.append(msg)
                else:
                    problems.append({"level": "WARN", "msg": msg, "boxes": []})
        if inter:
            pairs = ", ".join(f"{a} x {b} ({L:.0f} mm)" for a, b, L in inter)
            notes.append(f"model '{mdl.name}' has parts passing through each other: {pairs}. "
                         f"Fine where intended (joints, inserts); otherwise fix the model.")
    notes.extend(overall_notes)
    sh.check_notes = notes

    if verbose:
        for n in notes:
            print(f"  NOTE  {n}")
        if problems:
            ne = sum(p["level"] == "ERROR" for p in problems)
            print(f"CHECK: {ne} error(s), {len(problems) - ne} warning(s)")
            for p in problems:
                print(f"  {p['level']:5s} {p['msg']}")
        else:
            print("CHECK: clean (no overlaps, nothing outside the frame, values match geometry)")
    return problems


def _reserved(sh):
    out = []
    for r in sh.reserved:
        name = r[0]
        owner = {"notes": "notes#", "title block": "titleblock#",
                 "revision block": "revblock#"}.get(name, name)
        out.append((name,) + tuple(r[1:5]) + (owner,))
    return out


def debug_overlay(sh, svg, problems):
    marks = []
    for p in problems:
        col = "#e00" if p["level"] == "ERROR" else "#f80"
        for b in p.get("boxes", []):
            marks.append(f'<rect x="{b[0] - 0.6:.2f}" y="{b[1] - 0.6:.2f}" width="{b[2] - b[0] + 1.2:.2f}" '
                         f'height="{b[3] - b[1] + 1.2:.2f}" fill="{col}" fill-opacity="0.12" '
                         f'stroke="{col}" stroke-width="0.35"/>')
    return svg.replace("</svg>", "\n".join(marks) + "\n</svg>")


def grid_overlay(sh, svg):
    """Light coordinate grid: lines every 10 mm, labels every 50 mm."""
    out = ['<g stroke="#3a7bd5" stroke-opacity="0.28" fill="none">']
    x = 0
    while x <= sh.W:
        w = 0.35 if x % 50 == 0 else 0.12
        out.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{sh.H}" stroke-width="{w}"/>')
        x += 10
    y = 0
    while y <= sh.H:
        w = 0.35 if y % 50 == 0 else 0.12
        out.append(f'<line x1="0" y1="{y}" x2="{sh.W}" y2="{y}" stroke-width="{w}"/>')
        y += 10
    out.append("</g><g fill=\"#3a7bd5\" font-family=\"Helvetica, Arial\" font-size=\"4\">")
    for x in range(0, int(sh.W) + 1, 50):
        out.append(f'<text x="{x + 0.8}" y="5">{x}</text>')
    for y in range(50, int(sh.H) + 1, 50):
        out.append(f'<text x="1" y="{y - 0.8}">{y}</text>')
    out.append("</g>")
    return svg.replace("</svg>", "\n".join(out) + "\n</svg>")
