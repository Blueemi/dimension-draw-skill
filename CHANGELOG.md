# Changelog

## 1.0.0 (2026-10-23)

First release.

- Sheets: ANSI D (and other sizes) in the style of Apple's accessory design guides:
  rounded frame, `NOTES:` block with boxed flag numbers, full or compact title block, footer.
  All text is a single-stroke CAD font rendered as vector paths.
- Dimensions measured from the geometry: linear, chain, baseline, ordinate with a boxed
  `0.00` datum and jogged leaders, diameter, radius, angle, flag-note leaders, centre marks,
  detail and section callouts, keep-out hatching. Text staggers and leaders dodge clutter
  automatically.
- 3-D models from extrude, box, cylinder, revolve, loft, sweep, sphere, ellipsoid, torus,
  capsule, or STL/OBJ import. Orthographic, section, hidden-line and iso views use exact
  hidden-line removal, including the intersection curves between parts.
- Modelling helpers:
  - a clamped spline that never overshoots its points
  - `mesh.line_on` for lines on curved surfaces
  - `model.envelope()` and `model.extreme()` for overall sizes
  - `view.ramp_angle` for vehicle approach and departure angles
  - `view.construction_line` for ground and ramp lines
- A checker that runs on every save. It reports:
  - text overlaps and text crossed by lines
  - content outside the frame or inside the notes or title block
  - typed values that disagree with the geometry
  - dimension ends and extension lines that miss the part
  - `NX` counts that don't match the features drawn
  - flags without notes, and detail letters without views
  - misaligned projected views and broken 3-D geometry
  - parts passing through each other
  - overall sizes that a part sticks out past
- Output: SVG, PNG and single- or multi-page PDF.
- Examples: phone case design guide (2 sheets), flask, sheet-metal bracket, coffee maker
  (3-D, 2 sheets with section A-A) and a hatchback (3-D vehicle package drawing).
