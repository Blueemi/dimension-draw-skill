---
name: dimensional-drawing
description: Make accurate, beautiful dimensional drawings in the exact style of Apple's accessory design guides (developer.apple.com/accessories/dimensional-drawings) for anything, from flat parts and devices (phones, watches, brackets, PCBs) to complex 3-D objects (coffee makers and other appliances, cars, furniture, tools). Builds ANSI-D sheets as SVG/PNG/PDF with a CAD stroke font, NOTES block with boxed flag numbers, title block, ordinate and linear dimensions measured from real geometry, keep-out hatching, detail and section views, and hidden-line 3-D views generated from one model (loft, sweep, revolve, extrude, STL/OBJ import), then verifies the layout and the model automatically. Use it whenever someone asks for a dimension drawing, technical/engineering drawing, spec or case-maker sheet, blueprint, keep-out drawing, accessory design guide, vehicle package drawing, "Apple-style" drawing, or dimensioned views of something, even if they never say "Apple".
license: MIT (LICENSE.txt). Heading fonts are Hershey fonts (assets/HERSHEY-FONTS-LICENSE.txt).
---

# Dimensional drawings, Apple style

This skill makes drawing sheets that look like Apple's published accessory drawings
and are dimensionally correct. A zero-dependency Python library (`scripts/dimdraw`)
does the drafting: you describe the object in millimetres and say what to dimension;
the library draws the views, measures every value from the geometry, lays out the
text, renders the sheet and reports every overlap or inconsistency it finds.

Read `references/style-guide.md` before you plan the sheet; it describes what Apple
puts on these drawings and where. `references/api.md` is the full API;
`references/modeling.md` is the guide to building 3-D models of complex objects.
The examples are complete and run as-is:

| example | shows |
|---|---|
| `examples/template.py` | minimal starting point |
| `examples/handset.py` | 2-sheet phone guide drawn in 2-D views: ordinates, details, keep-outs, iso hero |
| `examples/flask.py` | revolved product, 2-D section with hatching, angles, radii |
| `examples/bracket.py` | sheet-metal part on A3: hidden lines, hole patterns, countersinks |
| `examples/coffee_maker.py` | **3-D model**: every view, section A-A and the hidden-line rear view generated from one model |
| `examples/car.py` | **3-D model** of a vehicle: lofted body, wheels, lamps; side/front/rear/plan views + package dims |

## Two ways to draw

- **2-D views** (`sh.view`): you draw each view's outline in model mm. Best for flat or
  prismatic products where the views are simple outlines, and for keep-out sheets.
- **3-D model** (`Model` + `sh.model_view` / `sh.iso`): you build the object once from
  solids and the library generates every orthographic view, section and pictorial
  view with exact hidden-line removal. Use this for anything with real depth or
  curvature: appliances, vehicles, furniture, tools, toys, enclosures, bottles with
  handles. The views can't disagree because they come from one model, and the
  section views cut the actual geometry.
- You can mix them: a 3-D model for the main views plus 2-D detail views.

## Workflow

1. **Get real dimensions first.** Accuracy matters more than looks; a wrong number is
   worse than none.
   - Sources, best first: the user's numbers or CAD (STL/OBJ can be imported with
     `model.load()`), the maker's spec sheet or drawing, other datasheets. For a real
     product, look up its published dimensions (search the web if you can). Use
     measurements scaled off photos only as a last resort.
   - Put every number in named constants at the top of the script, with a comment
     saying where it came from.
   - Never invent a value and present it as fact. If you have to estimate, say so
     in your reply, mark it as a reference dimension (`reference=True` prints it
     as `(25.00)`), or add a note such as `"DIMENSIONS ARE NOMINAL."`.
2. **Plan the views and the sheet.** Use third-angle projection, as Apple does: front
   view in the middle, the left side view to its left, the right side view to its right,
   top above, bottom below, back view further right. Then enlarged details (`DETAIL A`)
   and sections (`SECTION S - S`), plus an iso hero view. Create projected views with
   `front.projected("left", at=x)`, which keeps scale and alignment (axes in the
   projection table in `references/api.md`). The sheet is ANSI D, 863.6 × 558.8 mm,
   origin top-left, y down. The notes block takes the top-left, the title block the
   bottom-right (x ≥ 678, y ≥ 435). Write a rough position table first (view sizes =
   object size × scale), and don't crowd the sheet: use a second sheet. Use
   `sheet.save(..., grid=True)` for a PNG with a mm grid.
3. **Build the geometry.**
   - *2-D:* copy `examples/template.py`. Build each view in model mm (y up, the
     origin usually at the product center), keep the `Shape`s it returns, and
     dimension between their anchors (`body.tl`, `btn.top_mid`, `lens.center`).
   - *3-D:* read `references/modeling.md`, build a `Model` (see coffee_maker.py and
     car.py), then add `sh.model_view(model, "front", x, y, scale)` and its
     `.projected(...)` views. Print `model.envelope()` first: it names the part that
     sets each extreme, so a lamp or handle sticking out shows up before you
     dimension. Dimension with 3-D points on the part: `model.extreme("+x")`,
     `mesh.point(...)`, `view.bbox()` anchors, or computed product coordinates.
     Vehicles: `side.ramp_angle(...)` gives approach and departure angles.
   - Don't type numbers into dimension text.
4. **Run it and read the CHECK report.** Fix every ERROR and WARN. The report flags
   overlapping or nearly touching text, text crossed by lines, anything outside the
   frame or inside the notes or title block, typed values that disagree with the
   geometry, dimension ends that don't line up with any drawn edge, extension lines
   that start in empty space (the point is off the part), `NX` counts that don't
   match the features drawn, flags without notes, detail letters without views,
   projected views that don't line up, overlapping views, and broken 3-D geometry
   (inverted loft sections, folded surfaces). NOTE lines list:
   - 3-D parts that pass through each other. That's right for intended joints
     (declare them with `m.joint`); otherwise it's a modeling error.
   - Overall sizes smaller than the drawn extent, with the parts that stick out.
     Pass `overall=False` when that's deliberate, as with Apple's product width,
     which leaves out the buttons.

   `NAME.check.png` outlines each problem.
5. **Look at the result.** The report can't see everything, so open the PNG with the
   image Read tool. Zoom into dense areas with
   `python3 scripts/zoom.py out/NAME.svg X0 Y0 X1 Y1` (sheet mm). In 3-D views, look for
   stray lines, which usually mean a modeling problem (see modeling.md), and for
   shapes that don't read like the real object. Compare against the style guide:
   spacing, balance, nothing cramped, every feature that matters dimensioned once.
   Repeat steps 3 to 5 until the sheet is clean and looks right.
6. **Deliver** the SVG (the master copy), PNG and PDF (`save_pdf([...])` for a set of
   sheets). Tell the user which numbers are estimated and what was simplified.

Run scripts with `python3 path/to/drawing.py`. Needs Python 3.8+ and nothing else
(pure-Python 3-D engine: about 20-70k triangles render in seconds per view). PNG/PDF
output uses any Chromium-family browser (Chrome, Edge, Brave, Helium, Playwright's
headless shell), rsvg-convert or cairosvg; otherwise you get the SVG only.

## Minimal scripts

```python
import os, sys
sys.path.insert(0, "/ABS/PATH/TO/dimensional-drawing/scripts")   # this skill's scripts/
from dimdraw import Sheet, Model, rect_path

W, H, T, R = 71.5, 149.6, 8.25, 10.5          # source: maker's spec sheet

# --- 2-D views ---
sh = Sheet("D", product="Widget", page=1, company="Acme Inc.")
sh.notes(["NO METAL CONTACT WITH PRODUCT.", "DO NOT OBSTRUCT PORTS."])
sh.title_block(title="WIDGET\nCASE DESIGN GUIDE", drawing_number="DG-001", rev="A", sheet=(1, 1))
f = sh.view(x=318, y=300, scale=1.47, name="front")      # model (0,0) lands at sheet (318,300)
body = f.rect(0, 0, W, H, r=R, corner="continuous")
f.dim_h(body.tl, body.tr, offset=20, ref=body, label="PRODUCT\nWIDTH")
f.dim_v(body.tr, body.br, offset=20, ref=body, label="PRODUCT\nLENGTH")
side = f.projected("left", at=180)        # third-angle: same scale, same sheet y; model x = product Z
sb = side.rect(0, 0, T, H, r=1.6)
side.dim_h(sb.bl, sb.br, offset=-12, ref=sb, label="PRODUCT\nTHICKNESS")
sh.save("out/widget.svg", pdf=True)     # prints CHECK report, writes .svg .png .pdf

# --- 3-D model, views generated ---
m = Model("widget")
m.extrude(rect_path(-W/2, -H/2, W/2, H/2, R, "continuous"), -T/2, T/2, fillet=1.6)  # profile XY, along Z
m.cylinder((20, 55, T/2), 6, 1.2, axis="z")                                          # a lens on the front
sh2 = Sheet("D", product="Widget", page=2)
fv = sh2.model_view(m, "front", 300, 300, 1.47)
rv = fv.projected("right", at=480)
fv.dim_h(m.point("min", "min", "mid"), m.point("max", "min", "mid"), offset=-12, ref=fv.bbox())
rv.dim_h(m.point("max", "min", "min"), m.point("max", "min", "max"), offset=-12, ref=rv.bbox())
sh2.iso(700, 300, 0.8, yaw=-35, pitch=30, model=m)
sh2.model_view(m, "front", 300, 450, 1.0, name="sectionA", section=0.0)   # cut at Z=0, hatched
sh2.save("out/widget-3d.svg")
```

## Rules that make it correct

- **Measure, don't type.** Every `dim*`, `ordinate_*`, `diameter`, `radius` and `angle`
  computes its value from the points you pass. Only use `text=` for wording the
  geometry can't give you. It is still cross-checked, and a mismatch is a WARN.
- **One model, many views.** Keep the product's numbers in one place and derive every
  view from them. Projected views share the scale and the aligned coordinate. With a
  3-D model this is automatic.
- **Dimension to real features.** Each end of a dimension should sit on an edge,
  silhouette, centre mark, centre line or construction line in that view, and the
  checker warns when it doesn't. Draw center lines (`centerline`, `center_mark`)
  before dimensioning centre-to-centre (track, hole spacing). Ground lines and ramp
  lines are `construction_line`s, not geometry.
- **Counts must be true.** `prefix="3X"` means three identical features exist and
  are drawn. Dimension a repeated feature once, with its count.
- **Choose datums like Apple does.** Ordinates start from a boxed `0.00` at a product
  edge or corner (`datum_at=`). Values below or left of the datum are negative.
- **Units and precision.** Millimetres with 2 decimals (`71.85`), angles with 0
  (`55°`), diameters as `Ø6.90`, radii as `R3.25`, reference dims as `(25.00)`.
- **Each feature dimensioned once.** Don't repeat a value in two views unless one
  of them is a reference dimension.
- **Third-angle placement**, with view captions `DETAIL A` / `SECTION H - H`. Every
  detail or section letter marked on a view needs its labelled view, and every flag
  number used needs its note.

## Rules that make it beautiful

- Nearest dimension line about 10-14 mm from the part, then about 12-14 mm between
  stacked lines. Use `ref=part_shape` (or `ref=view.bbox()`) so offsets count from
  the outline.
- Text is horizontal (unidirectional); ordinate values along vertical leaders are the
  only rotated text. Values go in the dimension line's break (automatic); small spans
  flip to arrows outside (`place="outside"`, `side=`).
- Captions under values use `label=` with short stacked lines: `"PRODUCT\nWIDTH"`.
- Name features with flag notes (`flags=[3]` → `[3] REAR CAMERA 1`); `arrow="dot"` for
  leaders that land on a surface. Keep leaders short and uncrossed.
- Line weights: outlines `visible`, emphasized parts `thick`, secondary edges and hatch
  `thin`, hidden `hidden`, center lines `center`.
- Leave whitespace. If a region is crowded, enlarge it into a detail view or add a
  sheet instead of squeezing it.
- Match the text sizes to the kind of sheet: `Sheet(style="phone")` (default, small
  captions) or `style="watch"` (captions as big as values) with
  `title_block(layout="compact")` and a `sh.heading(...)` title.
- Keep-out areas are hatched (`hatch`, `cross=True` for the stronger level), with a
  leader note saying what not to do there. Sections hatch each part at its own angle.
- An iso hero view, with dot leaders for the surface-wide notes, makes the sheet.

## API at a glance (see references/api.md and references/modeling.md)

```text
Sheet(size="D", product, page, company, date, year, style="phone"|"watch"|{...})
  .notes([...])  .title_block(..., layout="full"|"compact")  .heading("OVERALL DIMENSIONS", x, y)
  .view(x, y, scale, name, center=(mx,my)) -> View (2-D)
  .model_view(model, "front"|"back"|"left"|"right"|"top"|"bottom", x, y, scale,
              section=None|value, hidden=False, center=(vx,vy)) -> ModelView (generated, dimension with 3-D pts)
  .iso(x, y, scale, yaw, pitch, pre, model=m) -> IsoView (pictorial)
  view.projected(kind, at) -> aligned view (2-D or model)    view.bbox() -> Shape of the view's extent
  .label(x, y, "DETAIL", "A", sub=...)  .caption("KEEP OUT AREA 1", x, y)  .table(...)  .revision_block(rows)
  .save(path, png=True, pdf=False, grid=False)  .zoom(path, x0, y0, x1, y1)    save_pdf([sheets], "set.pdf")

2-D geometry (model mm, y up; returns Shapes with anchors tl, tr, bl, br, top_mid, center, at(angle) ...):
  rect  box  circle  ellipse  slot  polygon(pts, fillet)  polyline  line  arc  path  hatch(shapes, holes, cross, within)

3-D Model (X right, Y up, Z toward the front-view viewer; every builder returns a Mesh):
  extrude(profile, z0, z1, plane="xy"|"yz"|"zx", fillet=(b,t), holes=[...])  box  cylinder(c, r, h, axis, holes=[r])
  revolve([(r, h), ...], axis, center, closed=False)  loft([section(...), ...])  sweep(profile, path)
  sphere  ellipsoid  torus  capsule  load("part.stl"|"part.obj", scale)  mesh(verts, faces)
  helpers: section(profile2d, origin, u, v, n)  superellipse(w, h, e)  spline(points)  resample(profile, n)
  mesh.translate/rotate/scale/mirror  mesh.mark(path, face="top")  mesh.line(points3d)  mesh.point(...)
  model.point("min"|"mid"|"max"|value, ...)  model.bounds()  model.interferences()  model.save_stl(path)

Dimensions (offset in sheet mm; points are 2-D in View, 2-D or 3-D in ModelView):
  dim_h / dim_v / dim_aligned(p1, p2, offset, ref, label, prefix, reference, place, side, shift, snap)
  dim_baseline  dim_chain  ordinate_x / ordinate_y(pts, datum, ref, offset, datum_at)
  diameter  radius  angle(vertex, p1, p2, r, ext)  callout(target, text, dx, dy, flags, flags_after, label, also)
  center_mark  centerline  detail_circle / detail_rect(..., letter)  section_line(p1, p2, letter, look)
```

## Troubleshooting

- *Text crossed by a line / overlapping text:* change that annotation's `offset`, move
  it with `shift=(dx, dy)` or `side=`, give the leader a different `dx`/`dy`/`at=`, or
  give the view more room. Leaders and dimension text already dodge clutter
  automatically, so a warning that remains means the area really is full.
- *Something outside the frame:* the view is too big. Lower the scale, or move the
  view (`center=` positions a detail view by the region it shows).
- *A detail view of part of an outline:* draw the whole outline after
  `v.set_clip(x0, y0, x1, y1)` (model box), then call `v.set_clip(None, None, None, None)`.
- *Stray or jagged lines in a 3-D view:* see "Reading 3-D artifacts" in modeling.md.
  Usually it's a part sunk into another, an inverted loft section, or two coarse
  surfaces crossing at a shallow angle.
- *No PNG written:* no renderer was found. Set `DIMDRAW_CHROME=/path/to/chrome` or
  install `librsvg` (`rsvg-convert`). The SVG is still complete.

Branding: the style is Apple's, but the sheets are the user's. Use their company and
product names. Don't put Apple's name, logo or legal notice on drawings of non-Apple
products.
