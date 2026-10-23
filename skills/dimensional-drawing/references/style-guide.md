# Apple dimensional-drawing style guide

What Apple's accessory design guides contain, where everything sits, and the drafting
conventions behind them. Measurements are from the published sheets (ANSI D, 863.6 ×
558.8 mm). The library already applies the visual parameters. This guide is about the
decisions you make: what to draw, what to dimension, and where it goes.

## 1. Anatomy of a sheet

```
 ┌──────────────────────────────────────────────────────────────────────────┐ ← rounded frame,
 │ NOTES: (UNLESS OTHERWISE SPECIFIED)              [DETAIL A]   [DETAIL D] │   zone ticks at ¼
 │ [1] NO METAL CONTACT WITH PRODUCT.                                       │
 │ [2] DO NOT OBSTRUCT PORTS.                                               │
 │ ...                                                                      │
 │      ┌──┐  ┌──────────┐   ┌──┐   ┌──────────┐                ┌─hero─┐    │
 │ dims │  │  │  FRONT   │   │  │   │   BACK   │                │ iso  │    │
 │      │L │  │ (hatched │   │R │   │          │                └──────┘    │
 │      │  │  │  display)│   │  │   │          │                            │
 │      └──┘  └──────────┘   └──┘   └──────────┘                            │
 │ DETAIL B     BOTTOM / DETAIL C                          ┌─title block─┐  │
 │                                                         │METRIC│ Co.  │  │
 └─────────────────────────────────────────────────────────┴──────┴──────┘  ┘
 2026-09-09 | Copyright © 2026 Company. All Rights Reserved.        Product | 1
```

- **Frame** is a thin rounded rectangle inset 22.5 mm left and right, 13 mm top and
  24.5 mm bottom, with corner radius 8.6 mm and short zone ticks at the quarter points.
- **Notes** sit top-left, starting about 9 mm inside the frame. `NOTES:` is set in the
  engraved serif face and followed by `(UNLESS OTHERWISE SPECIFIED)`. Each numbered note
  has a square flag box. Notes are one line each, all capitals, and end with a period.
- **Title block** sits in the lower-right corner, 163 × 99 mm: METRIC | company,
  DRAFTER/DATE, DESIGNER/DATE, DIMENSIONS ARE IN MILLIMETERS / TOLERANCES (with the
  optional tolerance table), DO NOT SCALE DRAWINGS, the third-angle symbol, SIZE D,
  NOTICE OF PROPRIETARY PROPERTY, TITLE, DRAWING NUMBER / REV., SCALE NONE, and SHT n OF m.
- **Watch and AirPods sheets** replace the title block with a compact 168 × 31 mm strip
  (`title_block(layout="compact")`): notice | company, SIZE, DRAWING NUMBER, REV.,
  SCALE NONE and SHT n OF m. They put the sheet title on the drawing in the serif face
  (`sh.heading("OVERALL DIMENSIONS AND CALLOUTS", ...)`) and set captions and callouts
  as large as the values (`Sheet(style="watch")`).
- **Footer** sits outside the frame in the UI sans-serif: date and copyright at
  bottom-left, `Product | page` at bottom-right with the product name in blue.
- **Views** fill the middle band. The empty space is intentional; the sheet never
  feels packed.

## 2. A drawing set

Apple usually issues 1 to 8 sheets per product:

1. **Overview** (always): notes, front, left, right and back views with the overall
   dimensions, button positions, display and glass areas, port and camera detail
   views, and an iso hero carrying the surface-wide notes.
2. **Feature detail**: an enlarged control such as the Camera Control, Digital Crown
   or Action button, with `DETAIL E` and `SECTION H - H` style views and keep-out
   profiles (angles, chamfers, reference dimensions in parentheses).
3. **Sections and cones**: camera, flash and sensor keep-out cones in section views
   (`157°` / `82°` fields of view, cone base diameters), plus the front-sensor windows.
4. **Keep-out areas**: back views with hatched zones (`DO NOT OBSTRUCT THIS AREA WITH
   METAL OR OTHER CONDUCTIVE MATERIAL (FULL PRODUCT VOLUME INCLUDING SIDEWALLS)`),
   MagSafe-style magnet and coil zones, the compass, and antenna windows, each
   titled with a spaced caption (`KEEP OUT AREA 1`).

Soft goods and complex shapes (Vision Pro, AirPods) get mostly pictorial views with
flag notes and shaded keep-out regions (`[1] ACCESSORIES INTRUDING INTO SHADED REGIONS
WILL NEGATIVELY AFFECT PRODUCT PERFORMANCE`), plus a table of contents when the set
is long.

## 3. Views

- **Third-angle projection.** The left view sits left of the front view, the right
  view to its right, the top view above, the bottom view below, and the back view to
  the far right. Projected views share the front view's scale and aligned axis.
- **Scale** follows the product: a phone runs at about 1.47:1 on D, a watch at about
  3:1, earbuds at about 6:1. Details run at 2-4× the main view. The title block
  always says `SCALE NONE` (do not scale drawings).
- **Front view of a display device**: hatch the active display area at 45° (pitch
  about 2 mm), show the cover glass outline as a thin line inside the body outline, and
  fill cutouts (the pill or notch) white so the hatch stops at them.
- **Side views** show the buttons face-on as thick stadium outlines, thin lines where
  the glass meets the band, short thin lines across the band for antenna splits, and
  the camera plateau and lens rings stepping out from the back.
- **Detail views** are marked on the parent view by a phantom circle or rectangle and a
  large letter on a leader. The detail is drawn enlarged with only the relevant part of
  the outline (`set_clip`) and captioned `DETAIL D`, with an optional description line
  above (`CORNER PROFILE (ALL FOUR CORNERS)`).
- **Sections** carry cutting-plane arrows and letters, are hatched where material is
  cut, and are captioned `SECTION S - S`.
- **Hero / iso views** are clean hidden-line pictorials with tangent edges as thin
  lines. Leaders end in dots on surfaces: `[1][5] ENTIRE PRODUCT SURFACE`,
  `[7][8] BACK OF PRODUCT ONLY`.

## 4. What to dimension (and how)

| feature | Apple's treatment |
|---|---|
| overall size | `PRODUCT WIDTH`, `PRODUCT LENGTH`, `PRODUCT THICKNESS`, outermost on their sides |
| display, glass | `DISPLAY ACTIVE AREA`, `GLASS` width and length, stacked inside the overall dims, plus `2.64 ALL AROUND EXTERIOR OF HOUSING TO DISPLAY ACTIVE AREA` style notes |
| buttons | positions as **baseline dimensions from the top edge** to each button's top edge, button lengths with counts (`4X 5.60`), protrusion `0.45` with the button name under it (`ACTION BUTTON`) |
| cutouts and openings | **ordinates** from a boxed `0.00` at the product corner or edge: x ordinates vertical with rotated text above, y ordinates horizontal with negative values going down |
| holes, lenses, ports | center positions by ordinates, size by `Ø` callouts with counts and flag note numbers, caption under (`3X Ø16.58`, `[3] Ø6.90 FLASH`) |
| repeated holes | `10X Ø1.53 PORTS` with an ordinate for each center, like the speaker row |
| corner profile | a dense ordinate list along the curve with jogged leaders and `+` ticks (`DETAIL A`) |
| edge profile | the same in section (`PROFILE (ALL SIDES) DETAIL B`) |
| step heights | small dims with outside arrows and a caption: `2.78 BACK PLATE TO CAMERA PLATEAU` |
| connector keep-out | `12.45 RECOMMENDED CONNECTOR KEEPOUT`, `2X R3.25`, and a note on the mating-connector area |
| keep-out cones | angles in sections (`84° REAR CAMERA KEEPOUT CONE`) and base diameters |
| logo | a centered box, its size and its offset from a corner |
| reference values | in parentheses, e.g. `(25.00)`, when the value is given elsewhere |

Conventions:
- Two decimals everywhere (`0.45`, `150.01`), integer angles (`55°`), and counts written
  as `2X` before the value.
- Unidirectional text: everything reads horizontally except ordinate values on vertical
  leaders.
- The value sits in a break in the dimension line, with any caption under it.
- Stacked dimensions are spaced about 12-15 mm apart, and their values are staggered
  along the lines so they never collide.
- Each feature is dimensioned once, in the view where its true shape shows.

## 5. Notes vocabulary

Pick the notes that apply and number them in order. Callouts refer to them by
the same boxed number.

```
NO METAL CONTACT WITH PRODUCT.
DO NOT OBSTRUCT PORTS.
DO NOT OBSTRUCT THE IMAGING FEATURES: FRONT CAMERA, REAR CAMERA, REAR FLASH, REAR SENSOR.
DO NOT OBSTRUCT FORWARD FACING SENSORS.
RELATIVE MAGNETIC PERMEABILITY OF ANY METAL USED ON CASE: 1.05µ MAX, PER ASTM A342/A342M-14.
DO NOT TOUCH GLASS.
NO MAGNETS ON REAR OF PRODUCT EXCEPT MAGSAFE MAGNETS.
CASE THICKNESS ON BACKSIDE OF PRODUCT: 2.1 mm MAX TO ENSURE FULL FUNCTIONALITY.
CASE DOES NOT INTERFERE WITH CLICK OR ROTATION FUNCTION OF DIGITAL CROWN
CASE DOES NOT OBSTRUCT THE WATCH ACOUSTIC OPENINGS AND ALTIMETER
CASE DOES NOT CONTACT ELECTRICAL SENSORS
NO METAL CASES ALLOWED DUE TO ANTENNA FUNCTION. CASE MUST BE MADE OF RF-TRANSPARENT MATERIAL.
2N MAX ALLOWABLE FORCE APPLIED TO OUTER TEXTILE PERIMETER.
ACCESSORIES INTRUDING INTO SHADED REGIONS WILL NEGATIVELY AFFECT PRODUCT PERFORMANCE
ACCESSORIES MAY NOT COVER THESE METAL SURFACES
UNIT SHALL NOT BE POWERED ON OR UNDER OPERATING CONDITIONS WHILE STORED INSIDE THE CASE.
```
For other kinds of objects, write notes in the same voice: short imperatives that state
limits (`DO NOT ...`, `... MAX`, `... ALL AROUND`).

## 6. Label vocabulary

`PRODUCT WIDTH / LENGTH / THICKNESS`, `DISPLAY ACTIVE AREA`, `GLASS`, `COVER GLASS`,
`ACTIVE AREA`, `ACTION BUTTON`, `(+) VOLUME BUTTON`, `SIDE BUTTON`, `CAMERA CONTROL`,
`SIM TRAY`, `REAR CAMERA 1`, `FLASH`, `REAR MIC`, `REAR SENSOR`, `BOTTOM MIC 1`,
`SPEAKER PORTS`, `SCREW`, `RECOMMENDED CONNECTOR KEEPOUT`, `PRODUCT CENTER`,
`BACK PLATE TO CAMERA PLATEAU`, `CAMERA PLATEAU TO REAR CAMERA GLASS`,
`CROWN DIAMETER`, `COVER GLASS`, `BACK CRYSTAL WIDTH / HEIGHT`, `ANTENNA SPLIT`,
`DO NOT OBSTRUCT`, `ENTIRE PRODUCT SURFACE`, `BACK OF PRODUCT ONLY`, `ALL AROUND`,
`KEEPOUT DIMENSIONS MEASURED AT GLASS SURFACE`.

## 7. Visual parameters (built in)

| element | value on D |
|---|---|
| object lines | 0.30 mm; emphasized features 0.50; thin lines (dims, hatch, tangent edges) 0.18 |
| dimension text | 2.95 mm cap height, monospaced single-stroke CAD font, serifed `I` and `1`, oval `0` |
| captions under values and leader notes | 1.95 mm / 2.1 mm |
| notes | 3.1 mm, about 8.8 mm line pitch, flag box 2× the text height |
| arrowheads | hollow, closed, narrow: 2.7 mm long, 1.04 mm wide |
| extension lines | 0.9 mm gap from the part, 1.6 mm past the dimension line |
| hatch | 45°, 1.25-2.2 mm pitch, thin; crosshatch marks the stronger keep-out |
| center marks | short solid cross plus dashed center lines about 2 mm past the circle |
| detail boundaries | phantom (long-short) thin lines |
| footer | system sans-serif, 5.3 mm; product name in blue `#2f6fb0` |

## 8. Before you deliver

- [ ] CHECK reports clean: no errors and no warnings, or each remaining one reviewed and explained.
- [ ] Every value comes from the geometry, and estimated ones are marked or reported.
- [ ] Overall size, every opening and every keep-out is dimensioned once.
- [ ] Every flag number used in a callout exists in NOTES, and every detail letter has a view.
- [ ] Views follow third-angle placement and share their scale and alignment.
- [ ] Zoom in on the dense areas (camera, ports, corner profile) and confirm nothing
  touches and everything reads.
- [ ] The title block has the title, drawing number, rev, `SHT n OF m`, and the footer
  page number matches the sheet number.

## 9. Other kinds of products

Apple's sheets are about devices, but the same conventions carry over to any product.
Keep the same visual system: the frame, notes with flags, title block, unidirectional
values, hollow arrows, hatched keep-outs and a hero view. Then choose the content for
the product type.

| product | views | dimension | typical notes |
|---|---|---|---|
| **appliance** (coffee maker, mixer, kettle, printer) | front, side and top views, a section through the main vessel or mechanism, a hidden-line rear view if the back matters, hero | overall width / depth / height; base footprint; clearances (under a spout or head, above a lid that opens); vessel diameter and opening; handle reach; control positions | hot surfaces, steam vents, clearance needed to open lids, keep the water window visible |
| **vehicle** (car, van, scooter) | side elevation (main view), front, rear, plan, hero | overall length / width (body and over mirrors) / height; wheelbase; track; front and rear overhang; ground clearance; tire diameter; approach and departure angles (`angle()` from the tire contact point to the bumper corner); door and hatch openings when needed | vehicle at curb weight; tires at nominal pressure; accessories within the envelope; don't cover lamps or sensors |
| **furniture** | front, side and top views, a section through the seat or shelf, hero | overall size; seat and arm heights; depth of seat; leg spacing; shelf pitch | load ratings, floor protection, wall anchoring |
| **handheld tool or device** | the Apple layout (front, left, right, back, details), hero | as in section 4 | as Apple's: ports, buttons, sensors, keep-outs |
| **packaging or enclosures** | front, top and side views, sections through walls, an exploded iso | outer and inner envelope, wall thickness, draft, fixing points, cable openings | material, finish, tolerances |

For large objects, choose a scale so the main view fills about a third of the sheet
width. A 4.1 m car at 1:15 (scale 0.065) or a 330 mm appliance at 0.8 are examples.
Use a second sheet instead of shrinking everything.
