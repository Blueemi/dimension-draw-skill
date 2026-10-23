# Modeling complex objects in 3-D

For anything with real depth or curvature (appliances, vehicles, furniture, tools,
vessels with handles), build the object once as a `Model` and let the library
generate every view. This guide covers the builders, recipes that work, sections,
dimensioning, and how to read the artifacts that bad geometry produces.

```python
from dimdraw import Model, rect_path, circle_path, slot_path, polygon_path, spline, section, superellipse
m = Model("brewer")
```

## Axes and units

Model mm. **X** runs right, **Y** up and **Z** toward the viewer of the front view.
Put the product's natural front facing +Z and stand it on Y = 0. The third-angle
views then map like this: the front view shows (X, Y), the left view (Z, Y), the
right view (−Z, Y), the top view (X, −Z), the bottom view (X, Z) and the back view
(−X, Y). For a vehicle, put its length along X with the nose at −X, so the
"front" model view is the side elevation and the "left" view looks at the nose.

## Builders (each adds a Mesh to the model and returns it)

| builder | use it for |
|---|---|
| `extrude(profile, z0, z1, plane, fillet=(b, t), holes=[...])` | anything with a constant cross-section: housings, bases, slabs, plates with real holes, buttons |
| `box(center, size, r, fillet)` | quick blocks (r rounds the Z-parallel edges) |
| `cylinder(base_center, r, h, axis, fillet, holes=[r_in])` | posts, feet, knobs, lenses, tubes |
| `revolve(profile_rh, axis, center, closed=False, segments)` | turned shapes: carafes, bottles, lids, filters, wheels; `closed=True` for torus-like loops such as tires and O-rings |
| `loft(sections)` | free-form skins through cross-sections: car bodies, hulls, ergonomic grips, shoes |
| `sweep(profile, path, n)` | a profile along a 3-D path: handles, tubes, cables, frames, rails |
| `sphere`, `ellipsoid(c, (rx, ry, rz))`, `torus(c, R, r, axis)`, `capsule(c, r, length, axis)` | domes, lamps, knobs, mirrors, rounded ends |
| `load("x.stl" / "x.obj", scale)`, `mesh(verts, faces)` | real CAD or scanned geometry |

**Extrude planes.** The profile's 2-D (u, v) coordinates map to model axes as follows.
`plane="xy"`: u = X, v = Y, extruded along Z. `plane="yz"`: u = Y, v = Z, extruded
along X. `plane="zx"`: u = Z, v = X, extruded along **Y**, so plan shapes stand
upright. A rounded-rect footprint 210 wide (X) × 240 deep (Z) rising to 42 tall is
`m.extrude(rect_path(-125, -105, 115, 105, 24), 0, 42, plane="zx", fillet=(3, 6))`.
You can also pass `plane=(u_vec, v_vec)` and `origin=`.

**Profiles** can be any closed `Path` (`rect_path(..., r, "continuous")`,
`circle_path`, `slot_path`, `polygon_path(pts, fillet=...)`) or a list of points.
`holes=[...]` takes more closed profiles that are cut all the way through, so the
hole walls show in iso and section views.

**Smooth shapes.** `spline(points)` passes a centripetal Catmull-Rom curve through
control points, 2-D or 3-D. Use it for revolve profiles (`revolve(spline([...]))`)
so they have no kinks, and for sweep paths. A straight polyline profile draws a
crease line at every kink. The spline is clamped by default: between two
neighbouring points it stays inside their bounding box in every coordinate. So
its extremes are your control points, and a tire profile whose widest point is
`(TIRE_R, ...)` really stops at `TIRE_R` and can't dip below the ground. Pass
`clamp=False` for the plain, freer curve.

Spheres, ellipsoids, tori and capsules are smooth: they draw no crease lines, only
their silhouette. A flat ellipsoid (a lamp lens, a mirror shell) therefore shows no
stray strokes across its rim.

**Hollow parts** (carafes, cups, enclosures) should be shells. Their revolve profile
runs from the axis out along the base, up the outside, over the lip, down the
inside and back to the axis:
```python
outer = [(0, 0)] + OUTER                       # (radius, height) bottom -> lip
inner = [(r - wall, y) for r, y in reversed(OUTER[1:])] + [(OUTER[0][0] - wall, wall), (0, wall)]
m.revolve(outer + inner, axis="y", center=(cx, y0, cz))
```
A section then shows the wall thickness and the cavity, as it should.

**Lofts.** Each section is a ring of 3-D points. Every section needs the **same point
count and the same start point and winding**, or the skin twists. There are two
ways to build them:
- `section(profile2d, origin=(x, 0, 0), u=(0, 0, 1), v=(0, 1, 0), n=72)` resamples
  any closed 2-D profile by arc length, starting where a ray from its centroid at
  0° meets it. This is fine when the shapes change smoothly.
- Build the rings yourself with a **fixed number of points per segment** (floor,
  corner arc, side, shoulder, top) when the shape changes a lot along the loft.
  `examples/car.py` (`body_ring`) does this, and it is what keeps surfaces free of
  ribs.

Use dense stations where the shape changes fast (wheel arches, ends) and sparse
ones elsewhere. For rounded ends, use `cap="dome"` (depth `dome=` mm, default half
the end section's size), or space the last stations by angle around the end. The
loft checks each section's winding and warns about inverted or self-intersecting
sections.

**Sweeps.** `sweep(circle_path(0, 0, 8), path3d, n=28)` uses rotation-minimizing
frames, so tubes don't twist. Build the path from `spline(control_points)`.
Profile orientation: at the path start, profile x points along world +Y made
perpendicular to the path (world +X if the path starts vertical), and profile y
is tangent × profile x. A handle loop drawn in the X-Y plane therefore keeps
profile x in that plane and profile y along Z. `slot_path(..., angle=90)` gives
a strap that is thin in the loop plane.

**Joints.** When one part enters another (handle into a vessel, head into a column),
sink it **less than the wall it enters**: about half the wall of a shell, or 1-3 mm
into a solid. Make the last path segment run straight into the surface. Joints in
a part you will section should just touch, since overlapping cut faces only hatch
once (the first part wins). Declare intended joints with `m.joint(handle, carafe)`
so the checker's interference NOTE lists only surprises.

**Points on curved surfaces.** `m.raycast(origin, direction)` returns `(point,
mesh)` for the first surface hit. Use it to put vents, labels and callout targets
exactly on a loft or an imported mesh. `mesh.extreme("+x")` (also `"-y"`, ...
or a vector) returns the vertex furthest along a direction. `m.extreme(...)` does
the same over the whole model. Dimension envelopes from these points: the
extension lines then start on the part (the tip of a handle, the crown of a roof).

**Check the envelope before dimensioning it.** `m.envelope()` reports which part
sets each extreme, `{'x': ((-2050.0, 'body'), (2050.0, 'body')), ...}`. If it
names a lamp, a mirror, a button or a handle you didn't expect, the part sticks
out: move it, or label the dimension accordingly (see the overall-size NOTE).

**Placement.** `mesh.translate(dx, dy, dz)`, `.rotate("x" | "y" | "z" | axis_vector,
deg, center)`, `.scale(sx, sy, sz)` and `.mirror("x", at)` (which returns a new mesh;
`model.add` it). Builders take centers directly, so most parts need no transform.

**Lines on surfaces.** Door shut lines, window openings, panel gaps and seams are
feature lines. Use `mesh.line_on(points, direction)`:
```python
# a shut line on the right flank: shoot each point toward -Z onto the body
body.line_on([(x, y, 0) for y in range(200, 900, 40)], (0, 0, -1), offset=0.6)
```
It moves each point along `direction` to where it first meets that mesh. It then
lifts the point `offset` mm along the surface normal, so its own face can't hide
it, even on a shoulder radius that faces up. It also subdivides each span until the
line follows the curvature, so there is no chord sag under a fillet. Points that
miss the part break the line. Use `offset` of about 0.3-0.6 mm, or a little more on
a coarse mesh.

`mesh.line(points3d, "thin")` takes points you computed yourself, e.g. from the same
section function you lofted with, as `car.py`'s `z_on()` does. Lift those yourself,
and sample them at least as densely as the loft stations: a straight span between
sparse points cuts under a curved surface and disappears. Decals on a planar cap
use `mesh.mark(profile2d, face="top")`.

**Imported meshes.** `m.load("part.stl", scale=25.4)` converts inches to mm (OBJ
works too). The loader welds vertices; only edges sharper than the crease angle
draw (default 35° for imports). Pass `crease=45-60` for noisy 3-D scans and 20-30
for clean CAD exports with shallow chamfers. Views drop visible fragments shorter
than `min_line=0.5` sheet mm, which removes scan noise. Check `m.size()` and
`m.bounds()`, then rotate the model so its front faces +Z and its base sits on Y = 0
before drawing (`mesh.rotate("x", -90)` turns a Z-up CAD file into Y-up). Tested:
the Utah teapot (6k triangles), Spot the cow (6k) and the Stanford bunny (69k,
crease=50) each render in about a second per view.

## Recipes

**Appliance (coffee maker, mixer, kettle, printer):**
- Plan footprints extruded up with `plane="zx"`, with fillets on the top and bottom edges.
- Towers and heads as separate extrusions. Let a cantilevered head overlap the
  tower by about 20 mm; that's an intended joint, and its intersection curve draws
  the seam.
- Vessels as revolve shells with spline profiles, and lids as revolves.
- Handles as `sweep` along a `spline` path, with both ends sunk into the vessel wall.
- Buttons, feet and LEDs as small cylinders that protrude 1-3 mm from a face.
- Check that moving parts clear each other. In the coffee maker the carafe first
  sat inside the tower, and the section exposed it.

**Vehicle (car, van, scooter):**
- The body is a loft of fixed-count rings along X.
- The side shape (half-width at each height) must not depend on the floor height.
  Wheel arches then come from raising the floor around each axle, which truncates
  the side cleanly, and the side rows of points stay at fixed heights.
- Round the nose and tail by shrinking the sections toward mid-height. Never let
  the bottom pass the top, or the section inverts.
- The greenhouse is a second loft on the **same stations**. Its base is coplanar
  with the body's flat deck and its base corners are sharp, so the belt line draws
  as a clean crease instead of a jagged intersection.
- Tires are closed revolves of a rounded tread profile about Z, with rims, hubs and
  lug nuts as cylinders.
- Lamps are shallow ellipsoids just proud of the surface; their intersection curve
  is the lamp outline. Keep them inside the body's length: centre x plus radius
  must stay within ±L/2, and the same goes for a grille or plate. Then check
  `m.envelope()`. Mirrors are small ellipsoids on the door.
- Door and window lines go on the surface with `body.line_on(...)`, or are computed
  from the rings.
- Package dimensions in the side view:
  - Overall length between the bumper extremes: `m.extreme("-x")`, `m.extreme("+x")`.
  - Wheelbase and overhangs as one `dim_chain` through the axles at ground level,
    with `reference=[True, False, True]` when the overhangs are estimates.
  - Overall height from the tire contact `(x_axle, 0, z)` to the roof crown.
  - Ground clearance.
  - `side.diameter(side.ref_circle(wheel_center, 2 * tire_r), label="TIRE")`.
- Approach and departure angles:
  ```python
  side.ramp_angle((X_FA, TIRE_R, 0), TIRE_R, toward="left", label="APPROACH")
  side.ramp_angle((X_RA, TIRE_R, 0), TIRE_R, toward="right", label="DEPARTURE")
  ```
  This finds the steepest ramp that touches the tire and clears every non-wheel
  part beyond the axle (wheel parts are recognised by name: tire, wheel, rim, hub,
  lug, brake). It draws the ground and ramp lines out past the bumper, puts the
  angle there in open space, and returns `(degrees, limiting point)`.
  `draw=False` only computes. Angles print with 1 decimal.
- Track goes in the nose view between tire centre lines, body width at the waist,
  and width over mirrors in the plan view. A vehicle's overall width excludes the
  mirrors, so pass `overall=False` on a width labelled OVERALL that leaves them out.

**Furniture and frames:** use boxes and extrusions for panels, sweeps along
polylines for tube frames (bends are `spline` corners), and cylinders for legs.

## Views, sections and hidden lines

```python
fv = sh.model_view(m, "front", x, y, scale)        # orthographic, hidden lines removed
rv = fv.projected("right", at=x2)                    # aligned, same scale
tv = fv.projected("top", at=y2)
sec = sh.model_view(m, "front", x3, y3, scale, name="sectionA", section=36.0)
rear = sh.model_view(m, "back", x4, y4, scale, hidden=True)   # dashed hidden lines
iv = sh.iso(x5, y5, scale, yaw=-35, pitch=25, model=m)          # pictorial
```

- `section=v` cuts the model with a plane perpendicular to the view direction. It
  sits at product coordinate `v` along the axis the view looks along (Z for the
  front and back views, X for the side views, Y for top and bottom). The far side
  is kept, the cut faces are hatched at a different angle for each part, and the
  geometry behind the cut stays visible. Mark the cut on another view with
  `section_line(...)` and caption it `sh.label(x, y, "SECTION", "A - A")`.
- `hidden=True` adds hidden edges as dashed lines. Use it sparingly, on one view, as
  Apple does.
- Iso camera: `yaw` turns the product about the vertical (+ shows the right side),
  `pitch` tilts it to show the top, and `pre=[("x", 90)]` lays a product modeled
  upright onto its back first.
- For **detail views** of a model, call `sh.model_view(m, kind, x, y, big_scale,
  center=(vx, vy))`. Then use `view.set_clip(x0, y0, x1, y1)` or
  `view.set_clip_circle(cx, cy, r)` (view coordinates) to show only the region,
  matching the `detail_rect` / `detail_circle` that marks it on the parent view.

## Dimensioning model views

Every annotation call on a model view accepts **3-D points**: `dim_*`, `ordinate_*`,
`callout` (target and `also=`), `angle`, `centerline`, `center_mark`, `section_line`,
`detail_circle` / `detail_rect` centres, `text`, and `ref=[...]` point lists.
`view.ref_circle(center3d, d)` gives `diameter()` a circle Shape for a round
feature seen face-on.

Pass 3-D points. The view projects them, and `dim_h` / `dim_v` measure along the
view's own axes. These are good sources of points:

- `model.point("min", "min", "mid")` or `mesh.point("max", "mid", "max")` give
  bounding-box points; each coordinate is `"min"`, `"mid"`, `"max"` or a number.
- `view.bbox()` is a Shape of the view's projected extent. Use its anchors (`tl`,
  `br`, ...) and `ref=view.bbox()` to place dimension lines a fixed distance
  outside the part.
- Product constants from the top of your script, which are exact. Computed points
  on curved parts work too, such as the carafe's widest point from its profile.

For centre-to-centre values (wheel track, hole pitch), draw the centre lines first
with `view.centerline(p3a, p3b)`. The checker warns when a dimension end doesn't sit
on a drawn edge or centre line (`snap=False` silences one deliberate case).

## Reading 3-D artifacts

| what you see | cause | fix |
|---|---|---|
| unexpected curves inside a cavity, or an odd outline in a section | two parts pass through each other (check the NOTE list) | move the part, or make the overlap intentional and small |
| starbursts or fans of short lines | an inverted or self-intersecting loft section (WARN), or a collapsed cap | keep each section valid (bottom below top, no crossing) |
| ribs or creases along a surface that should be smooth | loft rows skew, or sections change shape abruptly | build rings with fixed counts and rows at fixed heights, add stations, or raise `mesh.crease` |
| jagged junction line between two surfaces | two coarse surfaces cross at a shallow angle | make them share stations and touch coplanar, or add resolution |
| faceted silhouettes | too few segments | raise `segments` / `n` / stations |
| a filleted edge's silhouette broken into dashes in an iso view | too few fillet steps for a large radius | `fillet_steps=8` on that `extrude` |
| crosshatch-like double hatching in a section | two cut parts overlap | the first part now wins; better still, make them touch |
| a handle or insert poking through a shell into the cavity | sunk deeper than the wall | sink less than the wall thickness and approach radially |
| surface lines missing or broken | the line lies on or under the surface: too little lift, or spans so long that the chord cuts under a curve | `mesh.line_on(points, direction)` (lifts along the normal, follows the curvature); for hand-made lines, sample at the loft stations |
| a short stroke where a loft corner goes from sharp to rounded (an A-pillar base) | the crease fades out partway along the corner, so only its sharp part draws | give the corner a small radius everywhere, or a constant one; or raise `mesh.crease` |
| a part sticks past the body in the side view, or an overall-size NOTE | a lamp, grille or handle extends past the body | `m.envelope()` names the part; move it in, or dimension the full envelope |
| an extension-line WARN, "starts in empty space" | the dimension point is off the part (a bounding-box corner, a point inside a face) | use real points: `m.extreme(...)`, points from the section functions, `ref_circle` centres |
| a part missing from a view | it lies entirely inside another part | check `model.interferences()` and the part positions |
| slow (more than about 20 s per sheet) | too many triangles | `segments=48`, fewer stations, simpler hidden parts |

Rendering is exact hidden-line removal on triangles: crease edges, smooth
silhouettes, feature lines and intersection curves between parts, each clipped
against everything in front of it. Measured costs: the coffee maker (36k
triangles) renders 7 views in about 6 s, and the car (61k triangles) renders 5
views in about 8 s.
