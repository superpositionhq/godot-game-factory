# Soft-gradient minimal desert

Reference works: Journey.

## References

- *Journey* (2012), Thatgamecompany, video game. https://en.wikipedia.org/wiki/Journey_(2012_video_game)
- *Abzu* (2016), Giant Squid, video game. https://en.wikipedia.org/wiki/Abzû
- *The Pathless* (2020), Giant Squid, video game. https://en.wikipedia.org/wiki/The_Pathless
- *Sky: Children of the Light* (2019), Thatgamecompany, video game. https://en.wikipedia.org/wiki/Sky:_Children_of_the_Light

## Visual definition

- **Shape language and proportions:** Wide empty dunes with a few monumental simple ruins: slabs, arches, towers, a distant mountain with a split peak. The figure is a small cone-shaped robed form with thin legs and a long scarf.
- **Line and outline:** No outline.
- **Shading model:** Smooth and soft, with sand that glows: strong warm backscatter, a sharp glitter sparkle layer and soft ridge shadows.
- **Palette:** `#e9a35a` `#f6d08a` `#c9683c` `#7a2e2a` `#fbe9c6` `#5b3a4a`. Almost one hue family: gold, orange, rust and cream, with a dark maroon figure. Other scenes switch the whole frame to one other hue.
- **Lighting:** Low sun with long soft shadows; sky and ground are close in colour so the horizon dissolves.
- **Texture and surface:** Fine sand sparkle and ripple lines; ruins are smooth stone with simple inlaid bands.
- **Atmosphere and post-processing:** Warm haze that removes the horizon, bloom on the sun and sparkle, slight vignette.
- **Camera and framing:** Very wide, subject small, low horizon; slow lateral moves.
- **UI and typography:** Almost no HUD and no panels or frames; state shows in the world, such as glowing white glyphs along the scarf. Any text is a thin, widely spaced geometric sans in cream `#fbe9c6`, icons are simple single-stroke glyph symbols, and counters are small cream glyph marks instead of numerals.
- **VFX and motion:** Sand spray and dust plumes trail behind movement, cloth scraps flutter, and soft cream glow pulses replace hard hit flashes. Motion is slow and gliding, with long eased arcs, floaty jumps and constant follow-through on scarf and robe.

## Fits

- **Genres:** `exploration`, `platformer`, `puzzle`, `action-adventure`
- **Moods:** serene, lonely, awed
- **Settings:** dune desert, buried ruins, mountain pilgrimage, sunken temple

## Godot recipe

### Assets

Wide dunes generated in a generator script: a heightmap with long crescent ridges and sharp crest lines, built into a mesh with `SurfaceTool` and given a `HeightMapShape3D` collision. A few monumental ruins built from simple slabs, arches and towers with inlaid bands. The figure is a small cone-shaped robed form with thin legs and a long scarf driven by a chain of bones on a `Skeleton3D` swung by script; build it from scratch, in Blender by script and imported as `.glb`. Packs are rarely needed; desert ruins can be used if smoothed and stripped of weathering. Generate a fine ripple normal map and a glitter noise texture in a generator script with `FastNoiseLite` and `Image`.

### Materials

Sand needs its own shader, `glow_sand.gdshader` (`shader_type spatial;`). In `light()`: a wrapped, high-contrast diffuse from `dot(NORMAL, LIGHT)` times `ATTENUATION`, shaped so slopes facing the sun are bright and ridge shadows stay soft; a warm backscatter term that brightens when the view looks toward the sun (`pow(clamp(dot(VIEW, -LIGHT), 0.0, 1.0), k)` on grazing slopes); and a glitter layer: threshold the high-frequency noise against the half-vector of `LIGHT` and `VIEW` so tiny sparkles flash as the camera moves, written to `SPECULAR_LIGHT` with values well above 1. In `fragment()` the ripple normals go into `NORMAL_MAP`, blended by slope. Fog and shadows apply to the shader without extra work. Ruins use a `StandardMaterial3D` with smooth, low-detail stone. Scarf glyphs are emissive. On the Mobile renderer: its 10-bit colour buffer clips bright values sooner, so keep the sparkles only about 2 to 3 times white so they still read as glints rather than flat white blots.

### Lighting and atmosphere

One low `DirectionalLight3D` with soft shadows: PSSM 4 Splits, `directional_shadow_max_distance` 300, a high soft shadow filter quality in the project settings, and `light_angular_distance` of a few degrees for a wide penumbra. Sky and ground must be close in colour: a `ProceduralSkyMaterial` (or a small sky shader) running from `#f6d08a` at the horizon to `#fbe9c6` above, and the `Environment` fog (exponential depth fog) in the same warm tone at a density that dissolves the horizon. Ambient light from the sky, so it is a warm gradient. No SSAO. For another scene, switch fog, sky, sun and sand colours together to one other hue family. On the Mobile renderer: there is no soft penumbra from the angular distance, so raise `shadow_blur` instead for soft ridge shadows.

### Post-processing

Glow on, HDR threshold about 1, high strength and bloom with the upper levels enabled so the sun and sparkles spread wide. A slight vignette from a `ColorRect` on a `CanvasLayer` with a `canvas_item` shader reading `hint_screen_texture`. ACES or AgX tonemapping, with a warm colour filter from the adjustments' colour-correction `GradientTexture1D`. No teal anywhere in shadows: keep the correction gradient warm at both ends. TAA can smear glitter; prefer SMAA or MSAA. On the Mobile renderer: wide glow ramps band sooner in its 10-bit buffer, so drop the highest glow levels and let the glow spread less.

### UI and effects

Almost no HUD and no panels. State shows in the world, for example emissive white glyphs along the scarf. Any text uses a thin, widely spaced geometric sans such as Jost ExtraLight, imported as a `FontFile`, set as the theme's default font and spaced out with a `FontVariation`, in `#fbe9c6`; counters are small glyph marks, not numerals. Effects: sand spray and dust plumes from `GPUParticles3D` drawing soft quads stretched along their velocity, in sand colours behind movement, fluttering cloth scraps, and cream glow pulses (additive emissive quads scaled by a `Tween`) in place of hit flashes. Motion is slow with long eased arcs.

## Do / Do not

Do:

- Keep the frame in one hue family.
- Add sharp glitter sparkle to smooth sand.
- Dissolve the horizon with haze of the sky colour.
- Keep the figure small and dark.

Do not:

- Do not add thin ink lines and flat fills; that reads as `012`.
- Do not use hard flat colour layers; that reads as `060`.
- Do not grade to teal and orange with gritty machines; that reads as `033`.
- Do not add realistic rock and plant detail; that reads as `032`.

## Nearest styles

- `012` Thin-line pastel desert: `012` draws thin ink contour lines around flat pastel fills; this style has no lines and models the sand with soft glowing gradients.
- `060` Layered flat-colour wilderness: `060` stacks hard-edged flat colour layers that step through several hues into the distance; this style blends one hue family smoothly with no layer edges.
- `033` Teal-orange desert blockbuster: `033` sets teal sky and shadows against orange sand, with gritty rusted machines; this style stays in gold, orange and rust, with smooth clean surfaces.
