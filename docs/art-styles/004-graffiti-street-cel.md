# Graffiti street cel

Reference works: Jet Set Radio.

## References

- *Jet Set Radio* (2000), Smilebit, video game. https://en.wikipedia.org/wiki/Jet_Set_Radio
- *Jet Set Radio Future* (2002), Smilebit, video game. https://en.wikipedia.org/wiki/Jet_Set_Radio_Future
- *Bomb Rush Cyberfunk* (2023), Team Reptile, video game. https://en.wikipedia.org/wiki/Bomb_Rush_Cyberfunk
- *Hi-Fi Rush* (2023), Tango Gameworks, video game. https://en.wikipedia.org/wiki/Hi-Fi_Rush

## Visual definition

- **Shape language and proportions:** Lanky characters with big shoes and hands; city blocks are simple boxes tilted into exaggerated perspective. Low polygon counts are visible.
- **Line and outline:** Uniform black outline, 3 to 4 px, on every silhouette. Few inner lines.
- **Shading model:** Two bands with a hard edge. The shadow band is a darker flat colour, not black.
- **Palette:** `#101014` `#ffd21f` `#ff3f8e` `#19c3ff` `#7dff3a` `#ff7a1a` `#f4f4f4`. Acid yellow, hot pink, cyan and lime against asphalt grey and white. Colours clash on purpose.
- **Lighting:** Flat daylight; shading mostly fixed to the model. Ground shadows are solid dark ovals.
- **Texture and surface:** Walls and vehicles carry large graffiti pieces: fat bubble letters, arrows, drips and stars with their own black outline and white highlight.
- **Atmosphere and post-processing:** None, or a slight colour boost. Hard aliased or lightly anti-aliased edges are acceptable.
- **Camera and framing:** Low, wide angle (24 to 28 mm equivalent) with tilted horizon for speed.
- **UI and typography:** UI looks like stickers and spray tags: slanted panels with a thick black outline and white keyline, filled with acid yellow, hot pink or cyan. Titles use fat bubble lettering and labels use a bold italic condensed sans. Score and combo numbers are large, tilted, outlined digits that jump in size when they change.
- **VFX and motion:** Spray puffs, drips, stars, arrows and speed streaks are flat outlined shapes in clashing palette colours. Hits flash a comic burst with a short freeze; animation is snappy and rhythmic, with exaggerated poses held on the beat.

## Fits

- **Genres:** `sports`, `platformer`, `racing`, `hack-and-slash`, `fighting`
- **Moods:** energetic, rebellious, playful
- **Settings:** city streets, skate park, rooftops, train yard

## Godot recipe

### Assets

Low-poly city and character packs fit, and visible facets are welcome. Tilt and taper buildings in a generator script by shearing their vertices with `MeshDataTool` so blocks lean into exaggerated perspective. Replace pack textures with flat palette fills at low resolution. Graffiti is built from scratch: draw bubble letters, arrows, drips and stars with `Image` in a generator script, each with its own black outline and white highlight, into a 2048 px atlas and place them as quads or through a second UV set (`UV2`) on walls and vehicles. Character shadows are dark oval quads under the feet, not shadow maps.

### Materials

Write `street_cel.gdshader`: `light()` uses `step(0.1, dot(NORMAL, L))` for two hard bands; the shadow band multiplies the base colour by a darker flat tint, never black. Shading should look fixed to the model, so `L` mixes `LIGHT` with the camera's up-right vector; `LIGHT` is in view space, so that vector is simply `normalize(vec3(1.0, 1.0, 0.0))`. A `graffiti` bool uniform blends the atlas over the base by alpha. The outline is an inverted hull in `next_pass` (`unshaded`, `cull_front`) with a constant screen-space width of 3 to 4 px (offset the clip-space position along the projected normal, scaled by its w), pure `#101014`. The generator script writes one material `.tres` per palette colour and stores smoothed normals in the `CUSTOM0` vertex channel for the hull.

### Lighting and atmosphere

One `DirectionalLight3D` used only for the band split, with `shadow_enabled` off. Flat white ambient (source Color). No fog, no SSAO, no `ReflectionProbe`. The sky is a flat background colour or a two-stop gradient sky shader.

### Post-processing

Tonemap Linear, `adjustment_saturation` 1.15. No glow, blur or grain. Anti-aliasing can stay off or use FXAA; hard edges are acceptable here. `rendering/scaling_3d/scale` 1.

### UI and effects

Titles use a fat rounded display face such as Bungee or Titan One; labels use Barlow Condensed Bold Italic. `LabelSettings` give text a thick black outline plus a white keyline from a shadow with zero offset and a larger size. Panels are `StyleBoxFlat` slanted with `skew`, filled with `#ffd21f`, `#ff3f8e` or `#19c3ff`; rotate them a few degrees. Combo numbers scale up on change with a short overshoot `Tween`. Particles are flat outlined billboards from a flipbook: spray puffs, drips, stars and speed streaks in clashing colours, with a 3-frame comic burst and a brief `Engine.time_scale` freeze on hits.

## Do / Do not

Do:

- Keep outline width constant in screen space.
- Cover at least one large surface with a graffiti piece.
- Use clashing saturated hues side by side.
- Tilt the camera and use a wide lens.

Do not:

- Do not add hatching or line-weight variation; that reads as `001`.
- Do not restrict the palette to red, black and white; that reads as `008`.
- Do not add rim highlights and gradient shadow tints; that reads as `015`.
- Do not use glossy PBR paint; that reads as `006`.

## Nearest styles

- `001` Ink-outline comic cel: this style has an even line, two tone steps and clean surfaces apart from graffiti; `001` has a wobbly line of changing width, three tone steps, hatching and inked wear marks.
- `015` Two-tone fighting-anime cel: this style clashes loud hues, covers walls with graffiti and shows its low polygon count; `015` keeps surfaces clean, tapers its line and adds tinted shadows and hard highlight shapes.
- `008` Red-black pop-punk graphic cel: this style uses many clashing bright hues in flat daylight; `008` keeps nearly the whole frame red, black and white and drops shadows to solid black.
