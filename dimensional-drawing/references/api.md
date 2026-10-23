# dimdraw API reference

`import sys; sys.path.insert(0, "<skill>/scripts"); from dimdraw import Sheet, save_pdf, rect_path, circle_path, slot_path, polygon_path, Path`

Coordinate systems:

| space | units | origin | y | used by |
|---|---|---|---|---|
| **sheet** | mm | top-left corner of the paper | down | view placement, `offset`, `dx/dy`, `shift`, labels, notes, checker messages |
| **model** | mm | anywhere (usually the product center) | **up** | all geometry and the points you dimension |
| **iso model** | mm | anywhere | Y up, Z toward the front-view viewer | `IsoView` solids |

All lengths passed as sheet distances (`offset`, `dx`, `length`, `extend`, `spacing`...) are
real sheet mm. Style sizes (text height, arrows, line weights) are tuned for ANSI D and scale
with the sheet width automatically for other sizes.

---

## Sheet

```python
sh = Sheet(size="D", product="", page=1, date=None, company="", copyright=None,
           frame=True, footer=True, zones=True, style=None, year=None, footer_left=None)
```
- `size`: `"A"`–`"E"`, `"A4"`–`"A0"` (landscape) or `(w_mm, h_mm)`. Apple uses `"D"` (863.6 × 558.8).
- `product`, `page`: bottom-right footer (`Product | 1`, product name in blue).
- Footer left: `{date} | Copyright © {year} {company}. All Rights Reserved.` `date` is an ISO
  string (default today), `year` defaults to the date's year (Apple often prints a later
  copyright year than the sheet date), `copyright=` replaces only the part after the date (`""`
  leaves just the date), and `footer_left=` replaces the whole left footer.
- `style`: per-sheet size overrides, either a dict (`{"label_text": 2.8}`) or a preset name from
  `PRESETS`. `"phone"` is the default (Apple's iPhone and iPad sheets: small captions).
  `"watch"` is Apple's Watch and AirPods sheets, with captions and callouts about the size of
  the values. `"large"` makes all text bigger, for small sheets or dense parts.
- Frame: rounded rectangle at x 22.5–841.1, y 13–534.3 (D), zone ticks at the quarter points.
  `sh.fx0, sh.fy0, sh.fx1, sh.fy1` hold the frame edges.

### Blocks
```python
bottom_y = sh.notes(items, x=None, y=None, title="NOTES:", subtitle="(UNLESS OTHERWISE SPECIFIED)",
                    h=None, pitch=None, wrap=None)
```
`items`: `"TEXT"` (auto-numbered boxed flag), `(n, "TEXT")` (boxed n), `("9.", "TEXT")` (plain
number), `("", "TEXT")` (unnumbered), `None` (spacer). `\n` inside TEXT = continuation lines,
`wrap=70` wraps by characters. Default position is Apple's (top-left). The area is reserved:
the checker flags drawing content inside it.

```python
sh.title_block(title="", company=None, drawing_number="", rev="", scale="NONE", sheet=None,
               units="METRIC", drafter="", designer="", drafter_date="", designer_date="",
               tolerances=None, notice=None, unit_note=None, size=None)
```
Apple's lower-right block (163 × 99 mm on D). `layout="compact"` gives instead the 168 × 31 mm
strip of the Watch and AirPods sheets: notice, company, size, drawing number, rev, scale and
sheet, with no title cell. Put the sheet title on the drawing with `sh.heading()`. `title` may
contain `\n` (up to ~4 lines, auto-shrinks). `sheet=(n, total)`. `tolerances=[("0 < - < 2", "±0.05"), ("2 < - < 10", "±0.08"),
("ANGLES", "±0.50°")]`. The proprietary notice is generated from `company` unless `notice=` is
given (pass `notice=""` to leave it blank).

```python
sh.revision_block(rows=[("A", "ECO-001", "INITIAL RELEASE")])   # top-right REV/ECO#/DESCRIPTION
sh.table(x, y, columns=[("SHEET", 25), ("CONTENT", 90)], rows=[(1, "OVERVIEW"), ...], title="TABLE OF CONTENTS")
```

### Paper-space annotation
```python
sh.label(x, y, word="DETAIL", letter="A", sub=None)   # "DETAIL A" centered at x, baseline y; sub = line above
sh.label(x, y, "SECTION", "H - H")
sh.caption("KEEP OUT AREA 1", x, y)                   # large spaced view title (mono)
sh.heading("OVERALL DIMENSIONS AND CALLOUTS", x, y)   # sheet heading in the engraved serif
sh.text(s, x, y, h=None, anchor="start|middle|end", valign="baseline|top|middle|bottom",
        rotate=0, font="mono|triplex|duplex", mask=False)
sh.leader(target_xy, elbow_xy, "TEXT", label=None, flags=(), arrow="open|filled|dot|none")
sh.flag(n, x, y, hexagon=False)
sh.reserve(name, x0, y0, x1, y1)                       # keep views out of an area
sh.st("dim_text")                                      # a style size in mm (see STYLE)
```

### Views
```python
v  = sh.view(x, y, scale=1.0, name=None, center=(0, 0))
iv = sh.iso(x, y, scale=1.0, name=None, yaw=45, pitch=35.264, roll=0, pre=())
```
The model point `center` lands on sheet `(x, y)`; `scale` = sheet mm per model mm. Give each view a
`name`; the checker uses it in messages.

**Projected views.** `front.projected(kind, at)` makes a third-angle view that shares the front
view's scale and alignment. For `left`, `right` and `back`, `at` is the sheet x and the sheet y
is shared; for `top` and `bottom`, `at` is the sheet y and the sheet x is shared. Draw each one in
these model axes (product: X right, Y up, Z out of the front face). `project(kind, (X, Y, Z))`
does the conversion:

| view | placed | model x | model y |
|---|---|---|---|
| front | center | X | Y |
| left | left of front | Z | Y |
| right | right of front | −Z | Y |
| back | right of the right view | −X | Y |
| top | above front | X | −Z |
| bottom | below front | X | Z |

### Output
```python
problems = sh.save("out/name.svg", png=True, pdf=False, check=True, px_per_mm=4.0, grid=False)
sh.zoom("out/zoom.png", x0, y0, x1, y1, px=1800)       # close-up of a sheet region
save_pdf([sh1, sh2, sh3], "out/set.pdf")              # multi-page PDF
```
`save` prints the CHECK report and returns the list of problems (dicts with `level`, `msg`).

| level | check |
|---|---|
| ERROR | text overlapping text; anything outside the frame; content inside the notes / title block / revision block |
| WARN | text closer than 0.5 mm to other text; text crossed by a line it doesn't own |
| WARN | a typed value (`text=`) that disagrees with the measured geometry |
| WARN | a dimension end that doesn't line up with any edge, silhouette, centre mark, centre line or construction line in its view (`snap=False` to opt out) |
| WARN | an extension line that starts in empty space: the dimension point is off the part and no edge lies along the line within reach. Extension lines whose point is off the outline but in line with an edge (a bounding-box corner beside a rounded corner) are moved to start at that edge automatically |
| WARN | `NX` prefix on a diameter while fewer than N circles of that size are drawn in the view |
| WARN | a flag number used without a matching note (skipped when the notes subtitle says "SEE SHEET ...") |
| WARN | a detail or section letter marked without its `DETAIL X` / `SECTION X - X` label on the sheet |
| WARN | a projected view whose extent along the shared axis doesn't match its parent's |
| WARN | overlapping views; broken 3-D geometry (inverted loft sections, folded surfaces) |
| NOTE | 3-D parts that pass through each other, with curve lengths (fine for intended joints declared with `m.joint`) |
| NOTE | a dimension labelled as an overall size (OVERALL, or PRODUCT WIDTH / LENGTH / HEIGHT / DEPTH / THICKNESS) that is smaller than the drawn extent of its view; names the parts past it on model views. Apple's own PRODUCT WIDTH excludes buttons, so `overall=False` on the dimension says it's deliberate; `overall=True` checks a dimension with another label |
| NOTE | mesh health: open surfaces (fine for sheets) |

Messages name the view and the shape kind (`front:rect`, `top:circle`) and the sheet position.
If any problems are found it also writes `name.check.png` with them outlined. `grid=True`
writes `name.grid.png` with a labelled mm grid. CLI zoom:
`python3 scripts/zoom.py out/name.svg X0 Y0 X1 Y1 [out.png] [--px 2400]`.

---

## View (orthographic)

### Geometry → `Shape`
Every call takes `style=` (`visible` default, `thick`, `thin`, `hidden`, `center`, `phantom`,
`detail`, or `{"w": 0.4, "dash": (3, 1)}`), and closed shapes take `fill=` (e.g. `"#fff"` to hide
lines/hatch underneath; drawing order = call order).

| call | notes |
|---|---|
| `rect(cx, cy, w, h, r=0, corner="circular")` | centered; `r` scalar or `(tl, tr, br, bl)`; `corner="continuous"` = Apple continuous-curvature corners |
| `box(x0, y0, x1, y1, r=0, corner=...)` | from two corners |
| `circle(cx, cy, d=None, r=None)` | Shape has `.r`, `.d`, `.at(deg)` |
| `ellipse(cx, cy, rx, ry, rot=0)` | |
| `slot(cx, cy, length, width, angle=0)` | stadium; `angle=90` vertical (buttons, pills, ports) |
| `polygon(pts, fillet=0)` / `polyline(pts, fillet=0)` | fillet scalar or per-vertex list |
| `line(p1, p2)`, `arc(cx, cy, r, a0, a1)` | angles in degrees, CCW |
| `path(Path)` | custom outline: `Path().move_to(x,y).line_to(...).arc(center, r, a0, a1).curve_to(c1, c2, p).close()` |
| `shape(existing_shape, style, dx=0, dy=0)` | redraw an outline (e.g. as hidden) |
| `text(s, x, y, h=None, anchor="middle", valign="middle", rotate=0, mask=False)` | text at a model point |

`Shape` anchors (model coords): `left right top bottom cx cy w h center tl tr bl br top_mid
bottom_mid left_mid right_mid`, `at(angle)`; circles also `r d`, slots `length width`.

```python
v.hatch(shapes, angle=45, spacing=None, cross=False, holes=(), style="thin", fill=None, within=None)
```
Clips parallel lines to the shapes (even-odd: `holes` cut out). `spacing` sheet mm (default
1.25), `cross=True` crosshatch, `within=(x0, y0, x1, y1)` model box (hatch just a band of an
outline), `fill="#eee"` adds a tint.

```python
v.set_clip(x0, y0, x1, y1)      # model box; following geometry is clipped (detail views)
v.set_clip(None, None, None, None)
v.S(model_pt) -> sheet_pt       v.M(sheet_pt) -> model_pt       v.bounds() -> sheet bbox
```

### Linear dimensions
```python
v.dim_h(p1, p2, offset=10, **opts)       # horizontal distance |x2-x1|
v.dim_v(p1, p2, offset=10, **opts)       # vertical distance |y2-y1|
v.dim_aligned(p1, p2, offset=10, **opts) # true length
v.dim(p1, p2, axis="h|v|a", offset=10, **opts)
v.dim_baseline(base, [p, ...], axis="v", offset=-14, step=11, **opts)  # stacked from one edge
v.dim_chain([p0, p1, p2, ...], axis="h", offset=10, **opts)   # reference=[True, False, True] per span
```
- `offset`: sheet mm from the outermost point (or from `ref`) to the dimension line.
  `h`: + above / − below. `v`: + right / − left. `a`: + paper-left of p1→p2.
- `ref=shape` (or a list of model points): measure the offset from that outline, so stacked
  dimensions sit at clean distances from the part.
- `label="PRODUCT\nWIDTH"`: small caption under the value. `prefix="2X"`, `suffix="MAX"`.
- `reference=True` → `(25.00)`; `basic=True` → boxed value; `decimals=2`.
- `place="auto|inside|outside"`, `side="start|end"` (outside text: left/right for `h`, beside the
  line for `v`), `shift=(dx, dy)` sheet-mm nudge (dy + down; disables auto-stagger).
- `arrows="open|filled|tick|dot|none"`, `ext=(True, True)` extension lines, `flags=[n]`.
- `text="..."` replaces the value (checked against the geometry unless `verify=False`).
- `overall=False|True`: skip or force the overall-size NOTE (see the check table).
- `dim_chain`: `reference`, `label`, `text`, `place`, `side` and `verify` may be lists with one
  entry per span (estimated overhangs in parentheses around a published wheelbase).
Returns the measured value (`dim_chain`: the list of values). Inside text slides along the line to avoid existing text (as Apple
staggers stacked dimensions); outside text picks the clearer side when `side` is not given.

### Ordinates (Apple's main dimensioning style)
```python
v.ordinate_y(pts, datum=0.0, ref=None, offset=-10, decimals=2, datum_at=None, jog=None,
             mark=None, gap=None, datum_shift=0)
v.ordinate_x(pts, datum=0.0, ref=None, offset=10, ...)
v.datum_y(at, ref=None, offset=-10, label="0.00")     # boxed datum alone
v.datum_x(at, ref=None, offset=10, label="0.00")
```
- `ordinate_y`: values of `y - datum` with horizontal leaders to a text column `offset` sheet mm
  from `ref` (shape edge or model x; default the extreme point): − left, + right.
- `ordinate_x`: values of `x - datum`, vertical leaders, text rotated to read bottom-to-top,
  column `offset` above (+) or below (−) `ref`.
- `pts` items: `(x, y)`, a Shape (its center), or `(x, y, "2X")` to prefix a count.
- `datum_at=(x, y)`: adds the boxed `0.00` datum leader from that model point into the same
  column. `datum_shift` slides it along the column (+ up / + right) with a jogged leader.
- Crowded values are spread apart automatically and their leaders jog (Apple's corner-profile
  look). `mark="tick"` puts a `+` on each feature point.

### Callouts
```python
v.callout(target, "TEXT", dx=10, dy=6, label=None, flags=(), arrow="open", hexflags=False,
          shoulder=None, boxed=False, h=None, auto=True, at=None, flags_after=(), also=())
v.diameter(circle, angle=45, length=10, prefix="", flags=(), label=None, text=None, decimals=2,
           arrow="open", dy=None, auto=True, at=None, flags_after=())   # "3X Ø16.58"
v.radius(center, r, angle=45, length=10, prefix="", ...)        # "2X R3.25"
v.angle(vertex, p1, p2, r=15, text=None, decimals=0, label=None, reflex=False, ext=True,
        shift=(0, 0), suffix="")                                # "55°"
```
- `callout`: the leader runs from `target` to the elbow at `(dx, dy)` sheet mm (dy + up), then
  a short horizontal shoulder, then `[flags] TEXT` with `label` lines below. `arrow="dot"` for
  surfaces. `auto=True` slides or mirrors the elbow if that spot is cluttered. `at=(x, y)` fixes
  the elbow at a sheet position. Text size is `callout_text`; pass `h=sh.st("dim_text")` for
  values.
- Multi-line text (`"CASE DOES NOT\nAPPLY FORCE"`) hangs from its first line: the leader and
  flags attach there, and the following lines align under the text.
- `flags_after=[5]` puts flag boxes after the text (`Ø27.30 [5]`). Text `""` with
  `flags=[4]` gives a bare flag on a leader.
- `also=[pt, ...]` gives one note several leaders, all starting from the same elbow (Apple's
  `[7]` pointing at three sensors).
- `shoulder` is the length of the horizontal stub between the elbow and the text, in sheet mm
  (default 3; `0` for none).
- `diameter`: the leader touches the circle at `angle` and runs `length` mm outward (`dy`
  overrides its rise).
- `angle`: the arc radius `r` is in sheet mm; the smaller angle is used unless `reflex=True`.
  The value is measured from the geometry. Text that doesn't fit inside the arc goes beyond it
  (with a short radial leader) or past either end, wherever it's clearest.
- Callout text runs in the leader's direction: an elbow right of the target puts the text to the
  right of the elbow, an elbow to the left puts it to the left. On an iso view `view.S(p3)` gives
  the sheet position of a 3-D point, which helps when choosing `at=`.

### Marks
```python
v.center_mark(circle_or_pt, r=None, extend=2.0)    # dashed cross through a hole, as Apple does
v.centerline(p1, p2, extend=2.0)                   # chain line, broken behind text
v.construction_line(p1, p2, extend=0, style="thin") # ground / ramp / sight line, not geometry
v.detail_circle(center, r, "B", angle=45, length=8)
v.detail_rect(x0, y0, x1, y1, "A", corner="tr|tl|br|bl", length=8)
v.section_line(p1, p2, "S", look=(0, -1), arm=7)   # look = viewing direction (model)
v.flag(n, x, y, hexagon=False)
```
- `construction_line` is for lines that aren't part of the object: a ground line, a ramp, a
  sight line, a datum plane seen edge-on. It doesn't widen the view or count in the projected
  extent check, and dimension and extension lines may start on it. It is not broken behind text;
  the checker reports text it crosses. Use `view.line` only for object geometry.

---

## 3-D: Model, ModelView, IsoView

Full guide with recipes: `references/modeling.md`.

```python
from dimdraw import Model, section, superellipse, spline, resample, load_stl, load_obj
m = Model("name")
```
Builders (each adds a `Mesh` to the model and returns it):
```python
m.extrude(profile, z0, z1, plane="xy", origin=(0, 0, 0), fillet=(0, 0), holes=(), fillet_steps=4,
          tangent_lines=True, name=None, style="visible", segments=None)
m.box(center, size, r=0, fillet=0, corner="circular")
m.cylinder(base_center, r, h, axis="z", fillet=0, segments=96, holes=())     # holes = inner radii (tubes)
m.revolve(profile_rh, axis="y", center=(0, 0, 0), segments=96, closed=False, angle=360)
m.loft(sections, cap=True, closed=False)        # sections: equal-count rings of 3-D points
m.sweep(profile2d, path3d, closed=False, cap=True, n=32, scale=None, twist=0)
m.sphere(center, r)  m.ellipsoid(center, (rx, ry, rz))  m.torus(center, R, r, axis="y")
m.capsule(center, r, length, axis="y")
m.load("part.stl" | "part.obj", scale=1.0, crease=28)   m.mesh(verts, faces)
```
- `plane`: `"xy"` (profile x,y → X,Y; along Z), `"yz"` (→ Y,Z; along X), `"zx"` (→ Z,X; along Y,
  i.e. plan shapes standing up), or `(u_vec, v_vec)`.
- Helpers: `section(profile2d, origin, u, v, n=64, start_angle=0)` places a resampled 2-D
  profile as a loft ring; `superellipse(w, h, e=2.5, n=64)`; `spline(points, per_segment=12,
  closed=False, clamp=True)` (2-D or 3-D Catmull-Rom; clamped = never overshoots its points, so
  the extremes are the control points); `resample(profile, n)`.
- Mesh: `.translate(dx, dy, dz)`, `.rotate(axis, deg, center)`, `.scale(sx, sy, sz, center)`,
  `.mirror("x", at)` (new mesh), `.copy()`, `.line(points3d, style)` (feature line through points
  you computed), `.line_on(points, direction, offset=0.6, style="thin", tol=None, closed=False)`
  (projects the points onto this surface along `direction`, lifts them along the normal and
  follows the curvature: shut lines, seams, window openings),
  `.mark(profile2d, face="top"|"bottom", hatch=False)` (decal on an extrusion cap),
  `.point("min"|"mid"|"max"|v, ...)`, `.extreme("+x"|"-y"|vector)` (furthest vertex), `.bounds()`,
  `.crease` (degrees, default 28; spheres, ellipsoids, tori and capsules are smooth: no creases),
  `.health()`.
- Model: `.point(...)`, `.bounds()`, `.size()`, `.extreme(direction)`, `.envelope()` (which part
  sets each min / max: `{'x': ((-2050.0, 'body'), (2050.0, 'body')), ...}`), `.stats()`,
  `.interferences()` (pairs of parts
  passing through each other, with curve length), `.joint(a, b)` (mark a pair as intended),
  `.raycast(origin, direction)` → `(point, mesh)`, `.save_stl(path)`. Mesh also has `.raycast`.
- `loft(..., cap="dome", dome=depth)` rounds both ends; `superellipse(w, h)` takes full extents
  and starts at (+w/2, 0) going CCW.

Views:
```python
fv = sh.model_view(model, kind, x, y, scale, name=None, hidden=False, section=None,
                   center=(0, 0), hatch_spacing=None, hatch_angles=(45, -45, 30, -30, 60),
                   intersections=True)
fv.projected("left" | "right" | "back" | "top" | "bottom", at, **kw)   # aligned model view
iv = sh.iso(x, y, scale, yaw=45, pitch=35.264, roll=0, pre=(), model=None, hidden=False)
```
- `kind` uses the third-angle axes (table above). `center` is in view coordinates.
- `section=v` cuts perpendicular to the view direction at product coordinate `v` (Z for
  front/back, X for left/right, Y for top/bottom), keeps the far side, and hatches each part's
  cut face at its own angle.
- `hidden=True` draws hidden edges dashed.
- A model view draws itself at its first annotation, so automatic placement of dimension text,
  callouts and angles sees the real geometry, and extension lines snap at once. Build the model
  before annotating; if it changes afterwards, the view is drawn again at save time.
- `side.ramp_angle(axle3d, tire_r, toward="left"|"right", exclude=("tire", "wheel", "rim", "hub",
  "lug", "brake"), r=None, decimals=1, label=None, overrun=22, draw=True)`: vehicle approach /
  departure angle in a side elevation. It finds the steepest ramp that touches the tire and clears
  every other part beyond the axle, draws the ground and ramp construction lines and the angle out
  past the vehicle end, and returns `(degrees, limiting point)`.
- `view.extent_by_mesh()`: each part's sheet extent (the checker uses it to name what sticks out).
- `view.bbox()` returns the projected extent as a Shape (anchors + `ref=`). `view.extent()` returns
  (x0, y0, x1, y1). `view.ref_circle(center3d, d)` returns an undrawn circle Shape for a round
  feature seen face-on (hole, knob, wheel), to pass to `diameter()` / `center_mark()`.
- All the View annotation methods work on model views with **3-D points**: `dim_h`/`dim_v` measure
  along the view axes, and `callout`, `centerline`, `section_line`, `ordinate_*`, `text` take 3-D
  targets. `view.set_clip(x0, y0, x1, y1)` or `view.set_clip_circle(cx, cy, r)` (view
  coordinates) makes enlarged detail views.
- IsoView also has the builders (`iv.extrude(...)`, ...) if you want a pictorial view without a
  separate Model. Its `callout`/`text` take 3-D points.
- Iso camera: `pre` rotations apply to the model first (`("x", 90)` lays a phone modeled upright
  on its display). Then `yaw` turns it about Y (+ shows the right side) and `pitch` about X
  (+ shows the top). True iso is `yaw=45, pitch=35.264`; an Apple-like phone hero is `yaw=-35,
  pitch=35, pre=[("x", 90)]`.

Rendering is exact hidden-line removal on triangle meshes. Lines come from crease edges (dihedral
above the mesh's crease angle), silhouettes (mesh-edge silhouettes in axis-aligned views,
interpolated smooth contours in oblique ones), feature lines (fillet tangents, decals,
`mesh.line`) and the intersection curves between different meshes, each clipped exactly against
every triangle in front of it.

## Styles

`dimdraw.STYLE` holds the defaults in D-sheet mm. Override them per sheet with
`Sheet(style={...})` or a preset name (see `PRESETS`). Editing `STYLE` itself changes every sheet:

| key | default | use |
|---|---|---|
| `visible` / `thick` / `thin` / `frame` | 0.30 / 0.50 / 0.18 / 0.40 | line widths |
| `dim_text` | 2.95 | dimension values, ordinates |
| `label_text` | 1.95 | captions under values |
| `callout_text` | 2.1 | leader notes |
| `note_text` | 3.1 | NOTES block |
| `flag_text` | 2.5 | standalone flags |
| `arrow_len` / `arrow_half` | 2.7 / 0.52 | hollow narrow arrowheads |
| `ext_gap` / `ext_over` | 0.9 / 1.6 | extension line gap / overshoot |
| `text_gap` | 0.9 | clearance around text in line breaks |
| `hatch_spacing` | 1.25 | default hatch pitch |
| `dash_hidden` / `dash_center` / `dash_phantom` | | dash patterns |

Fonts: `mono` (monospaced single-stroke drafting face, used everywhere), `triplex` (Hershey
Roman Triplex for NOTES:/METRIC/company), `duplex` (sheet size letter). All text is converted
to stroked paths, so the SVG renders identically everywhere. Supported symbols: `Ø ⌀ ° ± × ≤ ≥ µ □
⌴ ⌵ ↧ ← → ↑ ↓ – —` plus ASCII.
