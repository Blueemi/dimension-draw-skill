"""Sheet: paper, frame, notes, title block, footer, and the item store that
every view and annotation draws into."""

import datetime
import html
import os

from . import annot, fonts
from .geom import fmt

# Landscape sheet sizes in mm. Styles are tuned on ANSI D (Apple's format) and
# scale with the sheet width, so every size keeps the same look.
SIZES = {
    "A": (279.4, 215.9), "B": (431.8, 279.4), "C": (558.8, 431.8), "D": (863.6, 558.8),
    "E": (1117.6, 863.6), "A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0),
    "A1": (841.0, 594.0), "A0": (1189.0, 841.0),
}

# Measured from Apple's published sheets (ANSI D, mm).
STYLE = {
    "visible": 0.30,      # object lines
    "thick": 0.50,        # emphasized features (buttons, lenses)
    "thin": 0.18,         # dimension, extension, leader, hatch, secondary edges
    "frame": 0.40,
    "dim_text": 2.95,     # dimension values
    "label_text": 1.95,   # small captions under values (PRODUCT WIDTH)
    "callout_text": 2.1,  # leader notes that name things (ACTIVE AREA, REAR CAMERA 1)
    "flag_text": 2.5,
    "note_text": 3.1,
    "arrow_len": 2.7,
    "arrow_half": 0.52,
    "arrow_tail": 2.6,
    "dot_r": 0.55,
    "ext_gap": 0.9,       # gap between object and extension line
    "ext_over": 1.6,      # extension past the dimension line
    "text_gap": 0.9,      # clearance around text in a dimension line break
    "leader_len": 6.0,
    "shoulder": 3.0,
    "ord_jog": 5.0,
    "hatch_spacing": 1.25,
    "dash_hidden": (2.2, 1.1),
    "dash_center": (7.0, 1.2, 1.6, 1.2),
    "dash_phantom": (7.0, 1.2, 1.6, 1.2, 1.6, 1.2),
    "dash_detail": (6.0, 1.4, 1.4, 1.4),
}

# Per-sheet overrides (Sheet(style="watch") or Sheet(style={...})). Apple's
# iPhone/iPad sheets use small captions; the Watch and AirPods sheets set
# captions and callouts about as large as the values.
PRESETS = {
    "phone": {},
    "watch": {"label_text": 2.8, "callout_text": 2.8},
    "large": {"dim_text": 3.4, "label_text": 2.6, "callout_text": 2.8, "note_text": 3.3},
}

LINESTYLES = {
    "visible": ("visible", None),
    "thick": ("thick", None),
    "thin": ("thin", None),
    "hidden": ("thin", "dash_hidden"),
    "center": ("thin", "dash_center"),
    "phantom": ("thin", "dash_phantom"),
    "detail": ("thin", "dash_detail"),
}

LAYERS = ("geom", "mask", "cmask_lines", "cmask", "annot", "text", "frame")
BLUE = "#2f6fb0"


class Sheet:
    def __init__(self, size="D", product="", page=1, date=None, company="", copyright=None,
                 frame=True, footer=True, zones=True, style=None, year=None, footer_left=None):
        if isinstance(style, str):
            style = PRESETS[style]
        self.style = dict(style or {})
        self.year = str(year) if year else None
        self.footer_left = footer_left
        if isinstance(size, (tuple, list)):
            self.W, self.H = float(size[0]), float(size[1])
            self.size_letter = ""
        else:
            self.W, self.H = SIZES[size]
            self.size_letter = size
        self.k = self.W / SIZES["D"][0]
        self.items = []
        self.views = []
        self.reserved = []   # (name, x0, y0, x1, y1) regions views must avoid
        self.verify = []     # dimension text overrides to cross-check
        self.product = product
        self.page = page
        self.date = date or datetime.date.today().isoformat()
        self.company = company
        self.copyright = copyright
        self.zones = zones
        k = self.k
        # frame placement measured from Apple's sheets
        self.fx0, self.fy0 = 22.5 * k, 13.0 * k
        self.fx1, self.fy1 = self.W - 22.5 * k, self.H - 24.5 * k
        self.frame_r = 8.6 * k
        self._frame = frame
        self._footer = footer
        self._uid = 0
        self._finalizers = []
        # bookkeeping for the checker
        self.dim_points = []      # (view, owner, axis, sheet p1, sheet p2, text, label, overall)
        self.ext_lines = []       # extension lines to snap onto geometry at render time
        self._ext_done = set()
        self.floating = []        # (owner, point): extension lines that start in empty space
        self.counts = []          # (view, owner, "4X", diameter)
        self.flags_used = set()
        self.note_numbers = None  # set once notes() runs
        self.notes_partial = False
        self.letters_used = []    # ("DETAIL"|"SECTION", letter, view name)
        self.labels = []          # (word, letter)

    # ---- style ------------------------------------------------------------
    def st(self, name):
        v = self.style.get(name, STYLE[name])
        if isinstance(v, tuple):
            return tuple(x * self.k for x in v)
        return v * self.k

    def linestyle(self, style):
        """Resolve a style name (or dict) into (width, dasharray)."""
        if isinstance(style, dict):
            w = style.get("w", self.st("visible"))
            return w * 1.0, style.get("dash")
        wname, dname = LINESTYLES[style]
        return self.st(wname), (self.st(dname) if dname else None)

    def uid(self, kind):
        self._uid += 1
        return f"{kind}#{self._uid}"

    # ---- item store ---------------------------------------------------------
    def add_path(self, d, w=None, dash=None, fill=None, lines=None, owner=None, check=True,
                 layer="geom", color=None, join="round", cap=None, kind="line"):
        self.items.append({
            "t": "path", "d": d, "w": self.st("thin") if w is None else w, "dash": dash,
            "fill": fill, "lines": lines, "owner": owner, "check": check, "layer": layer,
            "color": color, "join": join, "cap": cap, "kind": kind,
        })

    def add_text(self, g, w, owner=None, check=True, s="", layer="text", color=None):
        self.items.append({"t": "text", "d": g.d, "w": w, "box": g.box, "owner": owner,
                           "check": check, "s": s, "layer": layer, "color": color})

    # ---- views --------------------------------------------------------------
    def view(self, x, y, scale=1.0, name=None, center=(0.0, 0.0)):
        """New orthographic view. scale: sheet mm per model mm. The model point
        `center` (default the model origin) lands at sheet position (x, y) mm,
        so an enlarged detail can be placed by the region it shows."""
        from .view import View
        ox, oy = x - scale * center[0], y + scale * center[1]
        v = View(self, ox, oy, scale, name or f"view{len(self.views) + 1}")
        self.views.append(v)
        return v

    def iso(self, x, y, scale=1.0, name=None, **kw):
        """New pictorial (3D) view; see iso.py. Pass model= to draw an existing
        Model, otherwise build solids on the view (iv.extrude(...), ...)."""
        from .iso import IsoView
        v = IsoView(self, x, y, scale, name or f"iso{len(self.views) + 1}", **kw)
        self.views.append(v)
        return v

    def model_view(self, model, kind, x, y, scale=1.0, name=None, **kw):
        """Orthographic view of a Model generated with hidden-line removal.
        kind: front | back | left | right | top | bottom (third-angle axes, see
        PROJECTION). Dimension it with 3-D model points. Options: hidden=True
        (dashed hidden lines), section=value (cut and hatch), center=(vx, vy)
        (view coords placed at x, y), hatch_spacing, intersections."""
        from .iso import ModelView
        v = ModelView(self, model, kind, x, y, scale, name=name or kind, **kw)
        self.views.append(v)
        return v

    # ---- paper-space annotation helpers --------------------------------------
    def text(self, s, x, y, h=None, anchor="start", valign="baseline", rotate=0.0, font="mono",
             check=True, mask=False):
        owner = self.uid("text")
        return annot.text(self, s, x, y, h if h is not None else self.st("dim_text"), anchor,
                          valign, rotate, font, owner=owner, check=check, mask=mask)

    def label(self, x, y, word="DETAIL", letter="", sub=None, h=None):
        """View caption centered at x, baseline y: 'DETAIL A', 'SECTION H - H',
        with an optional line above (e.g. 'CORNER PROFILE (ALL FOUR CORNERS)')."""
        h = self.st("dim_text") if h is None else h
        owner = self.uid("label")
        self.labels.append((word.upper(), "".join(ch for ch in str(letter) if ch.isalnum())[:1]))
        big = h * 2.35
        ww = fonts.line_width(word, h)
        wl = fonts.line_width(letter, big) if letter else 0.0
        gap = h * 1.2 if letter else 0.0
        tot = ww + gap + wl
        x0 = x - tot / 2
        annot.text(self, word, x0, y, h, owner=owner)
        if letter:
            annot.text(self, letter, x0 + ww + gap, y, big, owner=owner)
        if sub:
            annot.text(self, sub, x, y - big - h * 1.6, h, anchor="middle", owner=owner)

    def heading(self, s, x, y, h=None):
        """Sheet heading in the engraved serif, centered at x, baseline y
        (e.g. 'OVERALL DIMENSIONS AND CALLOUTS')."""
        h = self.st("dim_text") * 1.2 if h is None else h
        return self.text(s, x, y, h, anchor="middle", font="triplex")

    def caption(self, s, x, y, h=None, spaced=True):
        """Large spaced view title, e.g. 'KEEP OUT AREA 1'."""
        h = self.st("dim_text") * 1.45 if h is None else h
        s2 = " ".join(s) if spaced and len(s) < 40 else s
        s2 = s2.replace("   ", "  ")
        return self.text(s2 if not spaced else s, x, y, h, anchor="middle")

    def leader(self, target, elbow, s, label=None, flags=(), arrow="open", hexflags=False):
        owner = self.uid("leader")
        self.flags_used.update(flags)
        annot.leader(self, target, elbow, s, label=label, flags=flags, arrows=arrow,
                     owner=owner, flag_shape="hex" if hexflags else "box")

    def flag(self, n, x, y, hexagon=False):
        owner = self.uid("flag")
        return annot.flag(self, n, x, y, owner=owner, shape="hex" if hexagon else "box")

    def reserve(self, name, x0, y0, x1, y1):
        self.reserved.append((name, x0, y0, x1, y1))

    # ---- notes ------------------------------------------------------------
    def notes(self, items, x=None, y=None, title="NOTES:", subtitle="(UNLESS OTHERWISE SPECIFIED)",
              h=None, pitch=None, wrap=None):
        """Numbered notes block (top-left by default).

        items: list of entries, each one of
          "TEXT"               auto-numbered, boxed flag
          (n, "TEXT")          boxed flag n (int or str)
          ("9.", "TEXT")       plain number (a str ending with '.')
          ("", "TEXT")         unnumbered line (e.g. a closing statement)
          None                 blank spacer
        TEXT may contain '\\n' for continuation lines; wrap=N wraps at N chars.
        Returns the bottom y of the block."""
        k = self.k
        h = self.st("note_text") if h is None else h
        x = self.fx0 + 9.5 * k if x is None else x
        y = self.fy0 + 9.0 * k if y is None else y
        owner = self.uid("notes")
        th = h * 1.32
        tw = fonts.line_width(title, th, "triplex")
        annot.text(self, title, x, y, th, font="triplex", owner=owner)
        if subtitle:
            annot.text(self, subtitle, x + tw + h * 0.5, y, h * 0.95, owner=owner)
        pitch = h * 2.85 if pitch is None else pitch
        cont = h * 1.75
        tx = x + h * 4.45
        cy = y + pitch * 0.95
        auto = 0
        maxx = x + tw
        for it in items:
            if it is None:
                cy += pitch * 0.6
                continue
            if isinstance(it, str):
                auto += 1
                num, body = auto, it
            else:
                num, body = it
                if isinstance(num, int):
                    auto = num
            lines = []
            for para in body.split("\n"):
                lines.extend(_wrap(para, wrap) if wrap else [para])
            ymid = cy - h / 2
            if isinstance(num, int) or (isinstance(num, str) and num and not num.endswith(".")):
                annot.flag(self, num, x, ymid, h, owner=owner, box=h * 2.0)
            elif num:
                annot.text(self, str(num), x, cy, h, owner=owner)
            for i, ln in enumerate(lines):
                annot.text(self, ln, tx, cy + i * cont, h, owner=owner)
                maxx = max(maxx, tx + fonts.line_width(ln, h))
            cy += (len(lines) - 1) * cont + pitch
        bottom = cy - pitch + h * 1.2
        self.reserve("notes", x - 1, y - th - 1, maxx + 2, bottom + 2)
        nums = set()
        k = 0
        for it in items:
            if it is None:
                continue
            if isinstance(it, str):
                k += 1
                nums.add(k)
            elif isinstance(it[0], int):
                k = it[0]
                nums.add(it[0])
            elif isinstance(it[0], str) and it[0] and not it[0].endswith("."):
                nums.add(it[0])
        self.note_numbers = (self.note_numbers or set()) | nums
        self.notes_partial = self.notes_partial or "SEE" in (subtitle or "").upper()
        return bottom

    # ---- title block --------------------------------------------------------
    def title_block(self, title="", company=None, drawing_number="", rev="", scale="NONE",
                    sheet=None, units="METRIC", drafter="", designer="", drafter_date="",
                    designer_date="", tolerances=None, notice=None, unit_note=None,
                    size=None, layout="full"):
        """Apple-layout title block in the lower-right corner.

        layout="full": the 163 x 99 mm block of the iPhone/iPad/Vision sheets.
        layout="compact": the 168 x 31 mm strip of the Watch/AirPods sheets
        (notice | company, size, drawing number, rev, scale, sheet; no title).
        tolerances: list of (range, tol) rows, e.g. [("0 < - < 2", "±0.05"), ...]
        plus optional ("ANGLES", "±0.50°"). notice: proprietary notice text; by
        default it is generated from `company` (omitted when no company)."""
        k = self.k
        company = self.company if company is None else company
        if notice is None and company:
            notice = _notice_text(company)
        if layout == "compact":
            return self._title_strip(company, drawing_number, rev, scale, sheet, notice, size)
        x1, y1 = self.fx1, self.fy1
        W, H = 163.3 * k, 99.4 * k
        x0, y0 = x1 - W, y1 - H
        xl = x0 + 70.4 * k        # split left/right columns
        rh = 11.2 * k             # header row
        r1 = y0 + rh
        r2 = r1 + 10.8 * k
        r3 = r2 + 10.8 * k
        rb = y1 - 13.8 * k        # bottom row top
        rn = r1 + 25.9 * k        # notice bottom
        rt = rb - 13.0 * k        # title bottom / drawing-number top
        owner = self.uid("titleblock")
        w = self.st("frame") * 0.85
        rr = 4.0 * k
        ln = lambda a, b: annot.line(self, a, b, w=w, owner=owner, layer="frame")  # noqa: E731
        # outer left/top edges with the rounded top-left corner
        self.add_path(f"M{fmt(x0)} {fmt(y1)} L{fmt(x0)} {fmt(y0 + rr)} "
                      f"A{fmt(rr)} {fmt(rr)} 0 0 1 {fmt(x0 + rr)} {fmt(y0)} L{fmt(x1)} {fmt(y0)}",
                      w=w, lines=[[(x0, y1), (x0, y0), (x1, y0)]], owner=owner, layer="frame")
        ln((x0, r1), (x1, r1))
        ln((xl, y0), (xl, y1))
        ln((x0, r2), (xl, r2))
        ln((x0, r3), (xl, r3))
        xd = x0 + 47.5 * k
        ln((xd, r1), (xd, r3))
        ln((x0, rb), (x1, rb))
        ln((xl, rn), (x1, rn))
        ln((xl, rt), (x1, rt))
        xrev = x1 - 18.6 * k
        ln((xrev, rt), (xrev, rb))
        xsz = xl - 12.1 * k
        ln((xsz, rb), (xsz, y1))
        xsht = xl + 50.5 * k
        ln((xsht, rb), (xsht, y1))
        hs = 1.75 * k   # cell label size
        T = lambda s, x, y, h=hs, **kw: annot.text(self, s, x, y, h, owner=owner, check=False, **kw)  # noqa: E731
        pad = 1.6 * k
        # header row
        if units:
            T(units, (x0 + xl) / 2, y0 + rh / 2, 4.9 * k, anchor="middle", valign="middle",
              font="triplex")
        if company:
            T(company, (xl + x1) / 2, y0 + rh / 2, 4.6 * k, anchor="middle", valign="middle",
              font="triplex")
        T("DRAFTER", x0 + pad, r1 + pad, valign="top")
        T("DATE", xd + pad, r1 + pad, valign="top")
        T("DESIGNER", x0 + pad, r2 + pad, valign="top")
        T("DATE", xd + pad, r2 + pad, valign="top")
        vh = 2.6 * k
        if drafter:
            T(drafter, x0 + pad * 2, r2 - pad, vh)
        if drafter_date:
            T(drafter_date, xd + pad, r2 - pad, vh * 0.8)
        if designer:
            T(designer, x0 + pad * 2, r3 - pad, vh)
        if designer_date:
            T(designer_date, xd + pad, r3 - pad, vh * 0.8)
        cxl = (x0 + xl) / 2
        T(unit_note or "DIMENSIONS ARE IN MILLIMETERS", cxl, r3 + 4.2 * k, anchor="middle")
        T("TOLERANCES", cxl, r3 + 8.4 * k, anchor="middle")
        if tolerances:
            ty = r3 + 18.5 * k
            th = 2.4 * k
            for rng, tol in tolerances:
                T(rng, cxl + 6.0 * k, ty, th, anchor="end")
                T(tol, cxl + 9.0 * k, ty, th, anchor="start")
                ty += th * 1.75
        T("DO NOT SCALE DRAWINGS", cxl, rb - 2.2 * k, anchor="middle")
        # third angle projection symbol
        _third_angle(self, x0 + (xsz - x0) / 2, rb + 5.6 * k, 1.0 * k, owner)
        T("THIRD ANGLE PROJECTION", x0 + (xsz - x0) / 2, y1 - 1.6 * k, anchor="middle")
        T("SIZE", (xsz + xl) / 2, rb + pad, valign="top", anchor="middle")
        letter = self.size_letter if size is None else size
        if letter:
            lh = 7.6 * k
            lw = fonts.line_width(letter, lh, "duplex")
            if lw > (xl - xsz) - 2.0 * k:
                lh *= ((xl - xsz) - 2.0 * k) / lw
            T(letter, (xsz + xl) / 2, y1 - 1.2 * k, lh, anchor="middle", font="duplex")
        # right column
        if notice:
            cxr = (xl + x1) / 2
            T("NOTICE OF PROPRIETARY PROPERTY:", cxr, r1 + 4.0 * k, 1.75 * k, anchor="middle")
            nh = 1.5 * k
            nl = notice.split("\n")
            bw = max(fonts.line_width(s, nh) for s in nl)
            nx = cxr - bw / 2
            for i, s in enumerate(nl):
                T(s, nx, r1 + 8.4 * k + i * nh * 1.55, nh)
        T("TITLE", xl + pad, rn + pad, valign="top")
        if title:
            tl = title.split("\n")
            th = 4.0 * k if len(tl) <= 3 else 3.0 * k
            # shrink to fit the cell width
            maxw = max(fonts.line_width(s, th) for s in tl)
            avail = (x1 - xl) - 8 * k
            if maxw > avail:
                th *= avail / maxw
            cy = (rn + rt) / 2 + 1.5 * k
            tot = th + (len(tl) - 1) * th * 1.5
            for i, s in enumerate(tl):
                T(s, (xl + x1) / 2, cy - tot / 2 + th + i * th * 1.5, th, anchor="middle")
        T("DRAWING NUMBER", xl + pad, rt + pad, valign="top")
        T("REV.", xrev + pad, rt + pad, valign="top")
        if drawing_number:
            T(drawing_number, (xl + xrev) / 2, rb - 2.6 * k, 3.4 * k, anchor="middle")
        if rev:
            T(str(rev), (xrev + x1) / 2, rb - 2.6 * k, 3.4 * k, anchor="middle")
        T("SCALE", xl + pad, rb + pad, valign="top")
        if scale:
            T(str(scale), (xl + xsht) / 2 + 2 * k, y1 - 3.4 * k, 5.4 * k, anchor="middle")
        T("SHT", xsht + pad, (rb + y1) / 2 + 0.9 * k, 1.75 * k)
        T("OF", xsht + 22.0 * k, (rb + y1) / 2 + 0.9 * k, 1.75 * k)
        if sheet is None:
            sheet = (self.page, self.page)
        T(str(sheet[0]), xsht + 15.0 * k, (rb + y1) / 2 + 1.3 * k, 2.6 * k, anchor="middle")
        T(str(sheet[1]), xsht + 34.0 * k, (rb + y1) / 2 + 1.3 * k, 2.6 * k, anchor="middle")
        self.reserve("title block", x0 - 2 * k, y0 - 2 * k, x1, y1)
        return (x0, y0, x1, y1)

    def _title_strip(self, company, drawing_number, rev, scale, sheet, notice, size):
        k = self.k
        x1, y1 = self.fx1, self.fy1
        W, H = 168.0 * k, 31.0 * k
        x0, y0 = x1 - W, y1 - H
        xl = x0 + 88.0 * k
        r1, r2 = y0 + 10.8 * k, y0 + 23.8 * k
        xs1, xs2, xb = xl + 9.5 * k, x1 - 11.0 * k, xl + 40.6 * k
        owner = self.uid("titleblock")
        w = self.st("frame") * 0.85
        rr = 4.0 * k
        ln = lambda a, b: annot.line(self, a, b, w=w, owner=owner, layer="frame")  # noqa: E731
        self.add_path(f"M{fmt(x0)} {fmt(y1)} L{fmt(x0)} {fmt(y0 + rr)} "
                      f"A{fmt(rr)} {fmt(rr)} 0 0 1 {fmt(x0 + rr)} {fmt(y0)} L{fmt(x1)} {fmt(y0)}",
                      w=w, lines=[[(x0, y1), (x0, y0), (x1, y0)]], owner=owner, layer="frame")
        ln((xl, y0), (xl, y1))
        ln((xl, r1), (x1, r1))
        ln((xl, r2), (x1, r2))
        ln((xs1, r1), (xs1, r2))
        ln((xs2, r1), (xs2, r2))
        ln((xb, r2), (xb, y1))
        hs = 1.6 * k
        T = lambda s_, x, y, h=hs, **kw: annot.text(self, s_, x, y, h, owner=owner, check=False, **kw)  # noqa: E731
        pad = 1.2 * k
        if notice:
            cx = (x0 + xl) / 2
            T("NOTICE OF PROPRIETARY PROPERTY:", cx, y0 + 3.6 * k, 1.5 * k, anchor="middle")
            nh = 1.35 * k
            nl = notice.split("\n")
            bw = max(fonts.line_width(t, nh) for t in nl)
            for i, t in enumerate(nl):
                T(t, cx - bw / 2, y0 + 7.4 * k + i * nh * 1.55, nh)
        if company:
            T(company, (xl + x1) / 2, (y0 + r1) / 2, 4.4 * k, anchor="middle", valign="middle",
              font="triplex")
        T("SIZE", xl + pad, r1 + pad, 1.3 * k, valign="top")
        letter = self.size_letter if size is None else size
        if letter:
            lh = 6.0 * k
            lw = fonts.line_width(letter, lh, "duplex")
            if lw > (xs1 - xl) - 1.6 * k:
                lh *= ((xs1 - xl) - 1.6 * k) / lw
            T(letter, (xl + xs1) / 2, r2 - 1.0 * k, lh, anchor="middle", font="duplex")
        T("DRAWING NUMBER", xs1 + pad, r1 + pad, 1.3 * k, valign="top")
        if drawing_number:
            T(drawing_number, (xs1 + xs2) / 2, r2 - 2.0 * k, 3.0 * k, anchor="middle")
        T("REV.", xs2 + pad, r1 + pad, 1.3 * k, valign="top")
        if rev:
            T(str(rev), (xs2 + x1) / 2, r2 - 2.0 * k, 3.4 * k, anchor="middle")
        T("SCALE", xl + pad, (r2 + y1) / 2, 1.3 * k, valign="middle")
        if scale:
            T(str(scale), (xl + xb) / 2 + 3 * k, y1 - 1.2 * k, 4.6 * k, anchor="middle")
        if sheet is None:
            sheet = (self.page, self.page)
        T("SHT", xb + pad * 2, (r2 + y1) / 2, 1.3 * k, valign="middle")
        T(str(sheet[0]), xb + 15 * k, (r2 + y1) / 2, 2.2 * k, anchor="middle", valign="middle")
        T("OF", xb + 23 * k, (r2 + y1) / 2, 1.3 * k, valign="middle")
        T(str(sheet[1]), xb + 33 * k, (r2 + y1) / 2, 2.2 * k, anchor="middle", valign="middle")
        self.reserve("title block", x0 - 2 * k, y0 - 2 * k, x1, y1)
        return (x0, y0, x1, y1)

    def revision_block(self, rows=(), width=None):
        """REV / ECO# / DESCRIPTION OF REVISION table hanging from the top-right."""
        k = self.k
        W = (width or 182.0) * k
        x1, y0 = self.fx1, self.fy0
        x0 = x1 - W
        rh = 5.4 * k
        n = max(1, len(rows))
        y1 = y0 + rh * (n + 1)
        owner = self.uid("revblock")
        c1, c2 = x0 + 12 * k, x0 + 36 * k
        w = self.st("thin")
        for xx in (x0, c1, c2):
            annot.line(self, (xx, y0), (xx, y1), w=w, owner=owner, layer="frame")
        for i in range(n + 2):
            if i == 0:
                continue
            annot.line(self, (x0, y0 + i * rh), (x1, y0 + i * rh), w=w, owner=owner, layer="frame")
        hs = 1.5 * k
        annot.text(self, "REV", (x0 + c1) / 2, y0 + rh / 2, hs, anchor="middle", valign="middle", owner=owner)
        annot.text(self, "ECO#", (c1 + c2) / 2, y0 + rh / 2, hs, anchor="middle", valign="middle", owner=owner)
        annot.text(self, "DESCRIPTION OF REVISION", (c2 + x1) / 2, y0 + rh / 2, hs, anchor="middle",
                   valign="middle", owner=owner)
        for i, row in enumerate(rows):
            yy = y0 + rh * (i + 1.5)
            for txt, cx in zip(row, ((x0 + c1) / 2, (c1 + c2) / 2, (c2 + x1) / 2)):
                annot.text(self, str(txt), cx, yy, 2.0 * k, anchor="middle", valign="middle", owner=owner)
        self.reserve("revision block", x0, y0, x1, y1 + 2 * k)

    def table(self, x, y, columns, rows, title=None, h=None, row_h=None):
        """Grid table, top-left at (x, y). columns: [(header, width_mm), ...]."""
        k = self.k
        h = 2.6 * k if h is None else h
        rh = h * 1.75 if row_h is None else row_h
        owner = self.uid("table")
        W = sum(c[1] for c in columns)
        n = len(rows) + 1 + (1 if title else 0)
        y1 = y + rh * n
        w = self.st("thin")
        annot.box_rect(self, x, y, x + W, y1, w=self.st("visible"), owner=owner)
        for i in range(1, n):
            annot.line(self, (x, y + i * rh), (x + W, y + i * rh), w=w, owner=owner)
        cy = y
        if title:
            annot.text(self, title, x + W / 2, cy + rh / 2, h, anchor="middle", valign="middle", owner=owner)
            cy += rh
        xs = [x]
        for _, cw in columns:
            xs.append(xs[-1] + cw)
        for xx in xs[1:-1]:
            annot.line(self, (xx, cy), (xx, y1), w=w, owner=owner)
        for (hd, cw), xx in zip(columns, xs):
            annot.text(self, hd, xx + cw / 2, cy + rh / 2, h, anchor="middle", valign="middle", owner=owner)
        for r, row in enumerate(rows):
            ry = cy + rh * (r + 1.5)
            for ci, cell in enumerate(row):
                if ci == 0:
                    annot.text(self, str(cell), xs[ci] + columns[ci][1] / 2, ry, h, anchor="middle",
                               valign="middle", owner=owner)
                else:
                    annot.text(self, str(cell), xs[ci] + 1.2 * k, ry, h, valign="middle", owner=owner)
        return (x, y, x + W, y1)

    # ---- frame & footer -------------------------------------------------------
    def _draw_frame(self):
        k = self.k
        x0, y0, x1, y1, r = self.fx0, self.fy0, self.fx1, self.fy1, self.frame_r
        d = (f"M{fmt(x0 + r)} {fmt(y0)} L{fmt(x1 - r)} {fmt(y0)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x1)} {fmt(y0 + r)} "
             f"L{fmt(x1)} {fmt(y1 - r)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x1 - r)} {fmt(y1)} "
             f"L{fmt(x0 + r)} {fmt(y1)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x0)} {fmt(y1 - r)} "
             f"L{fmt(x0)} {fmt(y0 + r)} A{fmt(r)} {fmt(r)} 0 0 1 {fmt(x0 + r)} {fmt(y0)} Z")
        self.add_path(d, w=self.st("frame"), layer="frame", owner="frame",
                      lines=[[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]], check=False)
        if self.zones:
            t = 1.6 * k
            w = self.st("thin")
            for i in (1, 2, 3):
                xx = x0 + (x1 - x0) * i / 4
                yy = y0 + (y1 - y0) * i / 4
                for a, b in (((xx, y0 - t), (xx, y0)), ((xx, y1), (xx, y1 + t)),
                             ((x0 - t, yy), (x0, yy)), ((x1, yy), (x1 + t, yy))):
                    annot.line(self, a, b, w=w, owner="frame", check=False, layer="frame")

    def _footer_svg(self):
        k = self.k
        fs = 5.3 * k
        y = self.H - 9.6 * k
        left = self.footer_left
        if left is None:
            cr = self.copyright
            if cr is None:
                year = self.year or self.date[:4]
                who = f" {self.company.rstrip('.')}." if self.company else ""
                cr = f"Copyright \u00a9 {year}{who} All Rights Reserved."
            left = f"{self.date}\u00a0\u00a0|\u00a0\u00a0{cr}" if cr else self.date
        fam = ("-apple-system, 'SF Pro Text', 'SF Pro', 'Helvetica Neue', Helvetica, Arial, "
               "sans-serif")
        out = [f'<g font-family="{fam}" font-size="{fmt(fs)}" fill="#1d1d1f">']
        if left:
            out.append(f'<text x="{fmt(12.4 * k)}" y="{fmt(y)}">{html.escape(left)}</text>')
        if self.product or self.page:
            prod = html.escape(str(self.product))
            out.append(f'<text x="{fmt(self.W - 12.4 * k)}" y="{fmt(y)}" text-anchor="end">'
                       f'<tspan fill="{BLUE}" font-size="{fmt(fs * 1.12)}">{prod}</tspan>'
                       f'<tspan font-size="{fmt(fs * 1.12)}">\u00a0\u00a0|\u00a0\u00a0{html.escape(str(self.page))}</tspan></text>')
        out.append("</g>")
        return "\n".join(out)

    # ---- output -------------------------------------------------------------
    def _break_centerlines(self):
        """Knock center lines out behind text (drafting practice: center lines
        are interrupted where a value or caption sits on them)."""
        from .geom import box_overlap, seg_hits_box
        self.items = [it for it in self.items if it["layer"] != "cmask"]
        for it in self.items:
            it.pop("masked", None)
        cl = [it for it in self.items if it.get("kind") == "centerline" and it.get("lines")]
        if not cl:
            return
        for bb in cl:
            annot._item_bb(bb)
        masks = []
        for it in self.items:
            if it["t"] != "text":
                continue
            tb = annot._item_bb(it)
            m = 0.7 * self.k
            box = (tb[0] - m, tb[1] - m, tb[2] + m, tb[3] + m)
            hit = False
            for c in cl:
                if c["owner"] == it["owner"] or not box_overlap(c["_bb"], box):
                    continue
                if any(seg_hits_box(p, q, box) for pl in c["lines"] for p, q in zip(pl, pl[1:])):
                    hit = True
                    break
            if hit and not self._other_lines_hit(box, it["owner"]):
                masks.append(box)
                it["masked"] = True
        for b in masks:
            self.add_path(f"M{fmt(b[0])} {fmt(b[1])} L{fmt(b[2])} {fmt(b[1])} L{fmt(b[2])} {fmt(b[3])} "
                          f"L{fmt(b[0])} {fmt(b[3])} Z", w=0, fill="#fff", lines=None, owner="mask",
                          check=False, layer="cmask", kind="fill")

    def _other_lines_hit(self, box, owner):
        from .geom import box_overlap, seg_hits_box
        for it in self.items:
            if it["t"] == "text" or not it.get("lines") or it.get("kind") == "centerline":
                continue
            if it["owner"] == owner or it["layer"] == "frame":
                continue
            bb = annot._item_bb(it)
            if not bb or not box_overlap(bb, box):
                continue
            if any(seg_hits_box(p, q, box) for pl in it["lines"] for p, q in zip(pl, pl[1:])):
                return True
        return False

    def _geometry_grid(self, only=None):
        """Per-view spatial hash of drawn geometry segments (sheet coords)."""
        from collections import defaultdict
        grids = {}
        for it in self.items:
            if not it.get("lines") or it.get("kind") == "hatch":
                continue
            o = str(it.get("owner") or "")
            if only is not None and not o.startswith(only + ":"):
                continue
            if not (it["layer"] == "geom" or it.get("kind") in ("centerline", "construction")
                    or ":center" in o):
                continue
            g = grids.setdefault(o.split(":")[0], defaultdict(list))
            for pl in it["lines"]:
                for a, b in zip(pl, pl[1:]):
                    for cx in range(int(min(a[0], b[0]) // 2), int(max(a[0], b[0]) // 2) + 1):
                        for cy in range(int(min(a[1], b[1]) // 2), int(max(a[1], b[1]) // 2) + 1):
                            g[(cx, cy)].append((a, b))
        return grids

    def _snap_ext_lines(self, only=None):
        """Extension lines start at the feature: when a dimension point is off the
        drawn geometry (a bounding-box corner beside a rounded corner, a point
        inside a face), extend the line back along itself to the first edge it
        meets; if there is none nearby, remember it for the checker.
        only=view name: snap that view's lines now (its geometry is complete), so
        annotations placed later see where they really run."""
        import math
        if not self.ext_lines:
            return
        grids = self._geometry_grid(only)
        tol = 0.15 * self.k
        reach = 60.0 * self.k
        if only is None:
            self.floating = []
        for idx, (item, P, D, n, gap, over, vname, owner) in enumerate(self.ext_lines):
            if idx in self._ext_done or (only is not None and vname != only):
                continue
            g = grids.get(vname)
            if not g:
                continue
            self._ext_done.add(idx)

            def segs_near(q, r):
                out = []
                for cx in range(int((q[0] - r) // 2), int((q[0] + r) // 2) + 1):
                    for cy in range(int((q[1] - r) // 2), int((q[1] + r) // 2) + 1):
                        out.extend(g.get((cx, cy), ()))
                return out
            on = False
            for a, b in segs_near(P, tol):
                dx, dy = b[0] - a[0], b[1] - a[1]
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((P[0] - a[0]) * dx + (P[1] - a[1]) * dy) / L2))
                if math.hypot(P[0] - a[0] - dx * t, P[1] - a[1] - dy * t) <= tol:
                    on = True
                    break
            if on:
                continue
            # nearest geometry to P along the extension line, either direction
            # (proper crossings, colinear edges and tangent extremes all count)
            span = math.hypot(D[0] - P[0], D[1] - P[1])
            best = None
            seen = set()
            k = 0
            while k * 2.0 <= reach:
                for sgn in ((1, -1) if k else (1,)):
                    q = (P[0] + n[0] * 2.0 * k * sgn, P[1] + n[1] * 2.0 * k * sgn)
                    for a, b in segs_near(q, 2.0):
                        if (a, b) in seen:
                            continue
                        seen.add((a, b))
                        cands = []
                        ex, ey = b[0] - a[0], b[1] - a[1]
                        den = n[0] * ey - n[1] * ex
                        if abs(den) > 1e-9:
                            t = ((a[0] - P[0]) * ey - (a[1] - P[1]) * ex) / den
                            w = ((a[0] - P[0]) * n[1] - (a[1] - P[1]) * n[0]) / den
                            if -1e-9 <= w <= 1 + 1e-9:
                                cands.append(t)
                        for e in (a, b):           # vertices on the line (colinear / tangent)
                            off = abs((e[0] - P[0]) * n[1] - (e[1] - P[1]) * n[0])
                            if off <= tol:
                                cands.append((e[0] - P[0]) * n[0] + (e[1] - P[1]) * n[1])
                        for t in cands:
                            if t < span - gap and abs(t) <= reach and (best is None or abs(t) < abs(best)):
                                best = t
                if best is not None and abs(best) < 2.0 * k - 2.0:
                    break
                k += 1
            if best is None:
                if only is None:
                    self.floating.append((owner, P))
                else:
                    self._ext_done.discard(idx)      # try again with the finished sheet
                continue
            u = n
            S = (P[0] + u[0] * best + n[0] * gap, P[1] + u[1] * best + n[1] * gap)
            E = (D[0] + n[0] * over, D[1] + n[1] * over)
            item["d"] = f"M{fmt(S[0])} {fmt(S[1])} L{fmt(E[0])} {fmt(E[1])}"
            item["lines"] = [[S, E]]
            item.pop("_bb", None)

    def svg(self):
        for fn in self._finalizers:
            fn()
        self._snap_ext_lines()
        self._break_centerlines()
        if self._frame:
            self._draw_frame()
            self._frame = False  # draw once even if svg() is called again
        k = self.k
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(self.W)}mm" '
                 f'height="{fmt(self.H)}mm" viewBox="0 0 {fmt(self.W)} {fmt(self.H)}">',
                 f'<rect width="{fmt(self.W)}" height="{fmt(self.H)}" fill="#fff"/>']
        for layer in LAYERS:
            if layer == "text":
                parts.append('<g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round">')
            else:
                parts.append('<g fill="none" stroke="#000" stroke-linecap="round">')
            for it in self.items:
                if it["layer"] != layer:
                    continue
                parts.append(_item_svg(it))
            parts.append("</g>")
        if self._footer:
            parts.append(self._footer_svg())
        parts.append("</svg>")
        return "\n".join(parts)

    def check(self, verbose=True):
        from .check import run_checks
        return run_checks(self, verbose=verbose)

    def zoom(self, path, x0, y0, x1, y1, px=1800):
        """Render the sheet region (x0, y0)-(x1, y1) in sheet mm to a PNG about
        `px` pixels wide, for close visual inspection."""
        from . import export
        import tempfile
        svg = export.crop_svg(self.svg(), x0, y0, x1, y1)
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
            fh.write(svg)
            tmp = fh.name
        try:
            out = export.to_png(tmp, path, x1 - x0, y1 - y0, px / (x1 - x0))
        finally:
            os.unlink(tmp)
        if out:
            print(f"wrote {out}")
        return out

    def save(self, path, png=True, pdf=False, check=True, px_per_mm=4.0, debug=None, grid=False):
        """Write SVG (+ PNG / PDF when a renderer is available) and print the
        layout check report. Returns the list of problems found.
        grid=True also writes NAME.grid.png with sheet coordinates (mm) for
        planning view positions. When problems are found NAME.check.png
        outlines them in red/orange."""
        from . import export
        svg = self.svg()
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        base = path[:-4] if path.lower().endswith(".svg") else path
        svg_path = base + ".svg"
        with open(svg_path, "w") as fh:
            fh.write(svg)
        print(f"wrote {svg_path}")
        problems = self.check(verbose=check) if check else []
        if png:
            out = export.to_png(svg_path, base + ".png", self.W, self.H, px_per_mm)
            if out:
                print(f"wrote {out}")
        if pdf:
            out = export.to_pdf(svg_path, base + ".pdf", self.W, self.H)
            if out:
                print(f"wrote {out}")
        if grid and png:
            from .check import grid_overlay
            with open(base + ".grid.svg", "w") as fh:
                fh.write(grid_overlay(self, svg))
            out = export.to_png(base + ".grid.svg", base + ".grid.png", self.W, self.H, px_per_mm)
            if out:
                print(f"wrote {out}  (sheet coordinate grid, mm)")
        if not problems and not debug:
            for ext in (".check.svg", ".check.png"):   # don't leave a stale report behind
                if os.path.exists(base + ext):
                    os.remove(base + ext)
        if debug or (debug is None and problems):
            from .check import debug_overlay
            dbg = debug_overlay(self, svg, problems)
            with open(base + ".check.svg", "w") as fh:
                fh.write(dbg)
            if png:
                out = export.to_png(base + ".check.svg", base + ".check.png", self.W, self.H, px_per_mm)
                if out:
                    print(f"wrote {out}  (problems outlined in red)")
        return problems


def _item_svg(it):
    attrs = [f'd="{it["d"]}"']
    w = it["w"]
    if it["t"] == "text":
        attrs.append(f'stroke-width="{fmt(w)}"')
        if it.get("color"):
            attrs.append(f'stroke="{it["color"]}"')
        return f'<path {" ".join(attrs)}/>'
    if it.get("fill"):
        attrs.append(f'fill="{it["fill"]}"')
    if w and w > 0:
        attrs.append(f'stroke-width="{fmt(w)}"')
    else:
        attrs.append('stroke="none"')
    if it.get("color") and w:
        attrs.append(f'stroke="{it["color"]}"')
    if it.get("dash"):
        attrs.append(f'stroke-dasharray="{" ".join(fmt(v) for v in it["dash"])}"')
        attrs.append('stroke-linecap="butt"')
    elif it.get("cap"):
        attrs.append(f'stroke-linecap="{it["cap"]}"')
    if it.get("join") and it["join"] != "round":
        attrs.append(f'stroke-linejoin="{it["join"]}"')
    else:
        attrs.append('stroke-linejoin="round"')
    return f'<path {" ".join(attrs)}/>'


def _notice_text(company):
    return ("THE INFORMATION CONTAINED HEREIN IS THE PROPRIETARY\n"
            f"PROPERTY OF {company.upper().rstrip('.')}. THE POSSESSOR AGREES TO\n"
            "THE FOLLOWING:\n"
            "  (I) TO MAINTAIN THIS DOCUMENT IN CONFIDENCE\n"
            " (II) NOT TO REPRODUCE OR COPY IT\n"
            "(III) NOT TO REVEAL OR PUBLISH IT IN WHOLE OR PART\n"
            " (IV) ALL RIGHTS RESERVED")


def _third_angle(sh, cx, cy, s, owner):
    """Third-angle projection symbol: circle view left, truncated cone right."""
    w = sh.st("thin")
    r1, r2 = 2.6 * s, 1.3 * s
    c = (cx - 5.6 * s, cy)
    for r in (r1, r2):
        sh.add_path(annot._circle_d(c, r), w=w, layer="frame", owner=owner,
                    lines=[annot._circle_pts(c, r)], check=False)
    annot.line(sh, (c[0] - r1 - 1.6 * s, cy), (c[0] + r1 + 1.6 * s, cy), w=w, owner=owner,
               check=False, layer="frame")
    annot.line(sh, (c[0], cy - r1 - 1.6 * s), (c[0], cy + r1 + 1.6 * s), w=w, owner=owner,
               check=False, layer="frame")
    x0, x1 = cx + 1.0 * s, cx + 7.4 * s
    annot.polyline(sh, [(x0, cy - r2), (x1, cy - r1), (x1, cy + r1), (x0, cy + r2)], w=w,
                   owner=owner, closed=True, check=False, layer="frame")
    annot.line(sh, (c[0] + r1 + 1.6 * s, cy), (x1 + 1.4 * s, cy), w=w, owner=owner,
               check=False, layer="frame", )


def _wrap(s, n):
    words = s.split(" ")
    lines, cur = [], ""
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > n:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}" if cur else wd
    if cur or not lines:
        lines.append(cur)
    return lines


def save_pdf(sheets, path):
    """Write several sheets as one multi-page PDF (like Apple's drawing sets)."""
    from . import export
    svgs = [s.svg() for s in sheets]
    out = export.to_pdf_multi(svgs, path, sheets[0].W, sheets[0].H)
    if out:
        print(f"wrote {out} ({len(sheets)} sheets)")
    return out
