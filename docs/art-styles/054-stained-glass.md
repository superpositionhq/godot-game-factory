# Stained glass

Reference works: Chartres Cathedral; Sainte-Chapelle.

## References

- *Stained glass windows of Chartres Cathedral* (c. 1205-1240), Chartres workshops, stained glass. https://en.wikipedia.org/wiki/Chartres_Cathedral
- *Sainte-Chapelle windows* (1248), Parisian workshops, stained glass. https://en.wikipedia.org/wiki/Sainte-Chapelle
- *Tiffany lamp* (1895), Tiffany Studios (Louis Comfort Tiffany and Clara Driscoll), leaded glass lamps. https://en.wikipedia.org/wiki/Tiffany_lamp
- *Beauty and the Beast (prologue windows)* (1991), Walt Disney Feature Animation, animated film. https://en.wikipedia.org/wiki/Beauty_and_the_Beast_(1991_film)

## Visual definition

- **Shape language and proportions:** Images are divided into cells of coloured glass, each a simple convex or gently curved piece. Figures are stiff and frontal, with forms simplified to fit the cell layout. In 3D, objects are faceted shells of glass panes.
- **Line and outline:** Thick black lead lines (came) between all pieces, of even width, plus thicker iron bars across large windows.
- **Shading model:** None from scene lighting. Each pane is a single glowing colour with internal variation; fine detail is painted in dark enamel.
- **Palette:** `#0d0d10` `#1e3fae` `#c21f2b` `#e8b21a` `#1f8a4c` `#7a2fa0` `#f2e6c2`. Deep ruby red and cobalt blue dominate, with gold, green and violet; all seen against black.
- **Lighting:** Back-lit: the glass is the light source. The surroundings are dark, with coloured light patches cast on nearby surfaces.
- **Texture and surface:** Glass streaks, bubbles and ripples inside each pane; dark painted trace lines for faces and folds.
- **Atmosphere and post-processing:** Glow around bright panes; dark vignette.
- **Camera and framing:** Frontal for windows; for 3D objects, any angle with a dark background.
- **UI and typography:** Panels are leaded window frames: black lead borders around panes of ruby, cobalt and gold glass, with icons set in small roundels. Type is a heavy gothic blackletter or uncial capital, painted in dark enamel on a pale pane or cut as glowing gold glass. Numbers glow gold against black.
- **VFX and motion:** Hits shatter panes into coloured shards with a flash of white light. Effects are shafts of coloured light, glowing dust motes and light patches that sweep across dark floors. Figures move stiffly from pose to pose, like panes sliding inside their lead lines, and the glow pulses slowly.

## Fits

- **Genres:** `puzzle`, `action-adventure`, `platformer`, `rpg`, `exploration`, `soulslike`
- **Moods:** solemn, mystical, radiant
- **Settings:** gothic cathedral, medieval kingdom, enchanted castle

## Godot recipe

### Assets

Build windows and objects from scratch: a generator script divides an image or a surface into convex cells (Voronoi relaxed toward the drawing's contours), extrudes thick black lead strips between them and thicker iron bars across large windows, with `SurfaceTool`, and saves the meshes. In 3D, objects are faceted shells: decimate a model to large facets in Blender by script, turn each facet into a pane and each edge into a lead strip. Generate a glass texture in a generator script with `Image` and `FastNoiseLite`, with streaks, bubbles and ripples, and dark enamel trace lines for faces and folds. One colour per pane.

### Materials

Panes use `glass_pane.gdshader`, a spatial shader with `specular_disabled` that sets `ALBEDO` to black and puts all colour in `EMISSION`: the pane colour uniform times the streak texture at HDR intensity 1.5 to 3, darkened by the enamel line texture, with a slight view-dependent brightness shift (from `dot(NORMAL, VIEW)`) so panes shimmer as the camera moves. Scene lights add nothing to it. Lead and iron use an unshaded `StandardMaterial3D` in `#0d0d10`, or a shaded one with high roughness if a faint edge highlight is wanted. Panes have shadow casting off on their `MeshInstance3D`. Surrounding stone uses dark `StandardMaterial3D` materials.

### Lighting and atmosphere

The glass is the light. The surroundings are dark with near-black ambient. Coloured light patches on floors come from `SpotLight3D` nodes placed behind windows, each with a light projector texture rendered from that window's pane layout, or from `Decal` nodes. Shafts of coloured light are cone or slab meshes with an unshaded `blend_add` material tinted per pane group. No directional light indoors. Faint dark depth fog. No SSAO.

### Post-processing

Glow with HDR threshold 1, moderate intensity and the middle glow levels on gives the halo around bright panes without washing out the lead lines. Vignette 0.45 in black from a `ColorRect` on a `CanvasLayer` with a `canvas_item` shader that darkens the corners. Tonemap Linear to keep ruby and cobalt saturated. MSAA 4x so lead lines stay even. On the Mobile renderer: keep pane emission near 1.5 and lower the glow threshold a little, since its narrower colour buffer clips and bands bright values sooner.

### UI and effects

Panels are leaded frames: black borders around ruby, cobalt and gold panes as `StyleBoxTexture` 9-slices, icons in small roundels. Import a heavy blackletter such as UnifrakturCook or an uncial such as Uncial Antiqua as the theme default `FontFile`, either dark on a pale pane or gold with a glow made by a `LabelSettings` shadow of the same gold at zero offset and a few pixels of size. Numbers glow gold on black. Hits shatter panes into pre-cut coloured shards (`RigidBody3D` pieces) with a white flash. Add glowing dust motes inside light shafts with `GPUParticles3D` and a slow sine pulse on pane emission driven by `TIME`. Figures move pose to pose with discrete animation tracks.

## Do / Do not

Do:

- Separate every colour area with a black lead line.
- Make panes self-lit against a dark surround.
- Use deep red and blue as the main colours.
- Add streak and bubble variation inside panes.

Do not:

- Do not use small square pieces with light grout and surface shading; that reads as `055`.
- Do not use opaque flat fills with black bars on white; that reads as `079`.
- Do not use thin curving outlines with pastel fills; that reads as `083`.
- Do not light the glass from the front.

## Nearest styles

- `079` Primary grid neoplasticism: this style glows in deep ruby and cobalt against a black surround; `079` is mostly white, with a few flat opaque blocks of red, blue and yellow between straight black bars.
- `055` Mosaic tessera: here large panes of one glowing colour are each fully enclosed by thick black lead and lit from behind; `055` is thousands of tiny tiles with thin grout, lit from the front, with tones stepped across each form.
- `086` Insular illuminated manuscript: this style uses large plain panes of glowing colour; `086` packs a painted vellum page with fine knotwork and interlace, with no backlight.
