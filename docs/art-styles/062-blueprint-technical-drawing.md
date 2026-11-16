# Blueprint technical drawing

Reference works: Cyanotype blueprints.

## References

- *Cyanotype process* (1842), John Herschel, photographic printing process. https://en.wikipedia.org/wiki/Cyanotype
- *Blueprint* (19th century), after John Herschel's cyanotype process, reprographic drawing process. https://en.wikipedia.org/wiki/Blueprint
- *Photographs of British Algae: Cyanotype Impressions* (1843), Anna Atkins, cyanotype book. https://en.wikipedia.org/wiki/Anna_Atkins
- *Vitruvian Man* (c. 1490), Leonardo da Vinci, pen and ink drawing. https://en.wikipedia.org/wiki/Vitruvian_Man

## Visual definition

- **Shape language and proportions:** Objects shown as technical drawings: precise edges, visible hidden lines, centre lines, construction circles. Mechanical and architectural subjects.
- **Line and outline:** White or pale blue lines of two weights (visible edges 2 px, hidden and construction lines 1 px dashed) on blue. No dark lines.
- **Shading model:** None. Surfaces are transparent or the flat blue ground; section cuts are hatched with thin diagonal white lines.
- **Palette:** `#0b3d91` `#1f5fbf` `#ffffff` `#bcd4f6` `#082a66`. Prussian blue ground with white line work; pale blue for secondary lines.
- **Lighting:** None.
- **Texture and surface:** Faint paper grain and uneven blue wash; a light grid; fold creases. Dimension lines with arrowheads and tick marks.
- **Atmosphere and post-processing:** Slight blur and bleed on lines, edge darkening of the sheet.
- **Camera and framing:** Orthographic: front, side, top or isometric projection.
- **UI and typography:** Panels are thin white ruled boxes like a drawing title block, with corner ticks and leader lines that point to objects; icons are single-weight white line symbols. Text is an all-caps single-stroke drafting hand or a monospaced technical sans in white `#ffffff`, with secondary labels in pale blue `#bcd4f6`; numbers appear as dimension call-outs with arrowheads and units.
- **VFX and motion:** Effects are line work: impacts are expanding construction circles with radiating tick marks, trails are dashed paths, and destroyed objects separate into an exploded view. Motion is precise and mechanical, with linear moves, rotations that snap in fixed steps and lines that draw themselves on.

## Fits

- **Genres:** `puzzle`, `strategy`, `tower-defense`, `simulation`, `stealth`
- **Moods:** precise, calm, cerebral
- **Settings:** engineering workshop, factory floor plan, machine interior, heist floor plan

## Godot recipe

### Assets

Mechanical and architectural models with precise edges: CAD-like packs, or models built from code with `SurfaceTool` and primitive meshes. Textures are discarded. A generator script extracts feature edges (boundaries and creases above an angle, found with `MeshDataTool`) and builds a line mesh per object, each segment a thin quad that stores both endpoints, plus construction geometry made from scratch: centre lines, construction circles, dimension lines with arrowheads and tick marks, leader lines. Generate a paper texture (grain, uneven blue wash, light grid, fold creases) and a diagonal hatch tile for section cuts with `Image` in the same script.

### Materials

Surfaces are not shaded. Write `blueprint_surface.gdshader`: `render_mode unshaded;`, outputting the sheet colour so it fills depth and hides lines behind it. Lines use `blueprint_line.gdshader`, unshaded, which in `vertex()` pushes each segment's quad sideways in screen space to a constant 2 px width (using `VIEWPORT_SIZE`). Its `next_pass` material draws the same lines with `depth_test_disabled` at 1 px with a dash pattern from the segment's length coordinate in `UV.x`, and a lower `render_priority` so the solid 2 px line covers it wherever the edge is visible: what is left is dashed hidden lines. Section-cut faces use the hatch tile sampled by `SCREEN_UV`. Colours: white for visible edges, `#bcd4f6` for hidden and construction lines. No shadows.

### Lighting and atmosphere

None. No lights, shadows, fog or probes. The `Camera3D` uses orthogonal projection and the `Environment` background is a clear colour of Prussian blue `#0b3d91`.

### Post-processing

One full-screen pass after the scene: a `ColorRect` on a `CanvasLayer` with a `canvas_item` shader reading `hint_screen_texture` that composites the paper texture (multiply the uneven wash and grid over the blue), applies a very small blur by averaging a few neighbouring texels to imitate ink bleed, and darkens the sheet edges. No glow: lines must look printed, not emitted. Tonemap `Linear`. MSAA 8x or SMAA for crisp thin lines.

### UI and effects

Panels are thin white ruled boxes like a drawing title block (`StyleBoxFlat` with a transparent fill and a 1 px white border, no corner radius), with corner ticks and `Line2D` leader lines pointing to objects placed with `Camera3D.unproject_position`; icons are single-weight line symbols. The theme's default font is a single-stroke drafting hand such as Architects Daughter in capitals or a monospaced technical sans such as Share Tech Mono, white with `#bcd4f6` for secondary labels. Numbers appear as dimension call-outs with units. Effects are line work: expanding construction circles with tick marks on impact, dashed trail paths, lines that draw on by animating a length cutoff uniform with a `Tween`, and destroyed objects separating along axes into an exploded view. Rotations snap in fixed steps.

## Do / Do not

Do:

- Draw white lines on a blue ground.
- Show hidden edges as dashed lines.
- Use orthographic projection with dimension lines.
- Hatch section cuts.

Do not:

- Do not use glowing lines on black; that reads as `040`.
- Do not fill surfaces with shaded colour.
- Do not add neon glow and a floor grid in perspective; that reads as `088`.
- Do not use dark lines on white paper; that reads as `073`.

## Nearest styles

- `040` Vector display glow: `040` draws glowing lines on a black screen; this style draws crisp white lines with no glow on a Prussian blue paper ground.
- `088` Neon grid cyberspace: `088` is a dark space in perspective with neon trim, a receding floor grid and bloom; this style is a flat blue sheet in orthographic view with plain white lines.
- `073` Graphite pencil sketch: `073` is grey pencil strokes on white paper; this style is the reverse, white lines on deep blue with no dark lines.
