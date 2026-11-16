# Papercraft

Reference works: Tearaway; Paper Mario.

## References

- *Tearaway* (2013), Media Molecule, video game. https://en.wikipedia.org/wiki/Tearaway_(video_game)
- *Paper Mario: The Origami King* (2020), Intelligent Systems, video game. https://en.wikipedia.org/wiki/Paper_Mario:_The_Origami_King
- *Paper Mario: The Thousand-Year Door* (2004), Intelligent Systems, video game. https://en.wikipedia.org/wiki/Paper_Mario:_The_Thousand-Year_Door
- *Lumino City* (2014), State of Play Games, video game. https://en.wikipedia.org/wiki/Lumino_City

## Visual definition

- **Shape language and proportions:** Everything is cut and folded from flat sheets: boxes with tabs, cones rolled from sectors, fringed grass strips, layered cut-outs, accordion folds. Thickness is that of card, and faces stay planar or singly curved.
- **Line and outline:** No drawn outline. Sheet edges show as a thin lighter or darker rim.
- **Shading model:** Each flat panel has one tone, so folded forms show two to four planar steps. Soft contact shadows between layers.
- **Palette:** `#f7f3e8` `#ef5350` `#ffca28` `#42a5f5` `#66bb6a` `#8d6e63` `#ab47bc`. Bright construction-paper colours on cream; each sheet is one solid colour.
- **Lighting:** Soft overhead light with clear, soft drop shadows that separate paper layers.
- **Texture and surface:** Fine paper fibre, faint fold creases, slightly rough cut edges, occasional glue tab or pencil mark.
- **Atmosphere and post-processing:** Slight depth of field. Animation may be stepped.
- **Camera and framing:** Slightly raised three-quarter view, 40 to 50 mm equivalent, like a tabletop model.
- **UI and typography:** Panels are cut paper cards and torn-edge scraps stacked with small drop shadows and held by tape or pins; icons are simple paper cut-outs, stickers and ink stamps. Lettering is chunky cut-out capitals or rounded marker handwriting, and counters are big cut-paper digits in cream `#f7f3e8` on a red, yellow or blue backing sheet.
- **VFX and motion:** Particles are confetti scraps, paper curls and folded stars; water and smoke are paper strips that unroll, and a hit crumples or tears the figure. Things appear by unfolding like a pop-up book or flipping like a turned card, with snappy stepped animation and flutter at loose edges.

## Fits

- **Genres:** `platformer`, `puzzle`, `action-adventure`, `rpg`, `exploration`, `tower-defense`
- **Moods:** playful, cheerful, handmade
- **Settings:** pop-up storybook world, paper town, folded forest, tabletop model city

## Godot recipe

### Assets

Build nearly everything from scratch in a generator script with `SurfaceTool`: every object is thin sheets that stay planar or bend in one direction only. Boxes with tabs, cones rolled from sectors, fringed grass strips, layered cut-outs, accordion folds. Give sheets a small real thickness (about 1 percent of object size) so edges show. To adapt a pack model, decimate it to flat panels and unfold curved parts into single-curvature strips in Blender by script. Generate a fine paper-fibre albedo and normal, a fold-crease overlay and a slightly rough edge mask in a generator script with `Image` and `FastNoiseLite`. One solid colour per sheet.

### Materials

`StandardMaterial3D` works: albedo colour from the construction-paper palette, roughness 0.9 to 0.95, the fibre normal at low `normal_scale`, `cull_mode` disabled for single sheets. Because faces are planar and normals are split at folds, each panel takes one tone and folded forms show two to four planar steps without a custom ramp. A small custom shader can lighten or darken the cut edge using a UV-border mask. Keep shadow casting on: layer shadows are essential.

### Lighting and atmosphere

Soft overhead light: a `DirectionalLight3D` pointing nearly straight down with soft shadows at high quality (`light_angular_distance` of a few degrees), `shadow_opacity` 0.6 to 0.7, plus bright flat ambient light. Use a short `directional_shadow_max_distance` and tight `shadow_bias` and `shadow_normal_bias` values so thin gaps between layers still get a soft drop shadow. SSAO on with a small radius to deepen layer contact. No fog. Background is a cream sheet (`#f7f3e8`). A `ReflectionProbe` is not needed. On the Mobile renderer: soften the shadows with `shadow_blur` instead of the angular distance, and bake the layer contact darkening into a `LightmapGI` instead of SSAO.

### Post-processing

Slight depth-of-field blur on `CameraAttributesPractical`. `AgX` tonemap. No glow, no grain: fibre is in the materials. MSAA 4x for clean sheet edges.

### UI and effects

Panels are cut paper cards and torn-edge scraps as `StyleBoxTexture` 9-slices with the soft drop shadow painted in, held by tape or pins; icons are cut-outs, stickers and ink stamps. Font: chunky cut-out capitals such as Londrina Solid or a marker hand such as Gochi Hand; counters are big cream digits on a red, yellow or blue backing sheet. Particles are mesh quads with the paper material (`GPUParticles3D` drawing a `QuadMesh`): confetti scraps, curls, folded stars with tumbling rotation. Water and smoke are strips that unroll (animate a bend in `vertex()`). Objects appear by unfolding around hinge edges (a `Tween` on hinge pivots); a hit crumples a figure with a noise-driven vertex offset in `vertex()`. Step animation on twos.

## Do / Do not

Do:

- Use only flat or singly curved sheet forms.
- Stack layers with small gaps and soft shadows.
- Keep one solid colour per sheet.
- Show sheet thickness at cut edges.

Do not:

- Do not use doubly curved smooth surfaces; that reads as `048`.
- Do not flatten everything into unshaded poster layers; that reads as `064`.
- Do not use fabric fuzz and stitching; that reads as `051`.
- Do not use pure geometric primaries on white with no paper texture; that reads as `098`.

## Nearest styles

- `064` Mid-century cut-paper poster: `064` is flat, unlit poster layers in a handful of colours; this style has soft shadows between layers, light and dark sides on every fold, and more colours.
- `098` Bauhaus primary geometry: `098` uses solid, smooth primitives in a few primaries with no surface texture; this style uses thin folded sheets with visible paper fibre.
- `067` Boxy toybox low-poly: `067` is solid boxy forms in many strong colours; this style is thin sheets with faint paper fibre and slightly softer colour.
