# Boxy toybox low-poly

Reference works: Katamari Damacy.

## References

- *Katamari Damacy* (2004), Namco, video game. https://en.wikipedia.org/wiki/Katamari_Damacy
- *We Love Katamari* (2005), Namco, video game. https://en.wikipedia.org/wiki/We_Love_Katamari
- *Noby Noby Boy* (2009), Namco Bandai Games (Keita Takahashi), video game. https://en.wikipedia.org/wiki/Noby_Noby_Boy
- *Wattam* (2019), Funomena (Keita Takahashi), video game. https://en.wikipedia.org/wiki/Wattam

## Visual definition

- **Shape language and proportions:** Everyday objects reduced to naive boxy models: a cow is a box with four box legs, a person is a rectangular block with a cylinder head, trees are a cone on a stick. Hundreds of small objects scattered densely.
- **Line and outline:** No outline.
- **Shading model:** Simple two- or three-step shading with little contrast. Objects look evenly lit.
- **Palette:** `#ff6fae` `#ffd400` `#3ec1ff` `#7be04a` `#ff8a1f` `#ffffff` `#8a4fff` `#5a3a2a`. Many bright candy colours at once: pink, yellow, sky blue, lime, orange, with white and brown.
- **Lighting:** Flat, bright, shadowless; small blob shadows only.
- **Texture and surface:** Simple flat decals: stripes, dots, checks, faces made of two dots and a line, product labels as plain rectangles.
- **Atmosphere and post-processing:** None. Rainbow or flat pastel backgrounds.
- **Camera and framing:** Low third-person behind a rolling ball, wide angle; scale changes from tabletop to city.
- **UI and typography:** Round bubbles, rainbow arcs and thick circular gauges in candy fills, with icons that are tiny boxy objects or faces made of two dots and a line. Text is a chunky rounded sans mixed with wobbly hand-drawn lettering, in white `#ffffff` or brown `#5a3a2a` on pink, yellow and sky blue; counters are big numerals that bounce when they change.
- **VFX and motion:** Flat stars, hearts, sparkles and plain puffs pop out on pickups and bumps, with no smoke or realistic debris. Animation is stiff and toy-like: objects wobble, hop and spin as whole pieces, characters waddle through a few rigid poses, and everything pops in with squash and stretch.

## Fits

- **Genres:** `puzzle`, `platformer`, `simulation`, `sports`, `racing`, `exploration`
- **Moods:** playful, silly, cheerful
- **Settings:** cluttered living room, suburban town, toy city, playground

## Godot recipe

### Assets

Naive boxy models, hundreds of them: a cow is a box with four box legs, a person a block with a cylinder head, a tree a cone on a stick. Generate the whole object library in a generator script (or in Blender by script, imported as `.glb`) from boxes, cylinders and cones with slightly bevelled edges; this is faster and more consistent than adapting packs. Decals are simple textures drawn with `Image` in the same script: stripes, dots, checks, faces of two dots and a line, plain-rectangle product labels. Scatter objects densely with a placement step into `MultiMeshInstance3D` nodes.

### Materials

A `StandardMaterial3D` with `specular_mode` disabled, or a tiny shader `toybox.gdshader`: in `light()`, a half-Lambert (`dot(NORMAL, LIGHT) * 0.5 + 0.5`) quantised to two or three steps with low contrast (for example 0.8, 0.9, 1.0), ignoring `ATTENUATION`'s shadow so nothing receives shadows; in `fragment()`, the base colour with a decal texture blended by alpha from `UV2`. Use one material per candy colour and draw repeated objects through `MultiMeshInstance3D` with per-instance colours (read as `COLOR` in the shader), or an `instance uniform` colour on single meshes, so hundreds of objects share one material.

### Lighting and atmosphere

Flat, bright and shadowless: one `DirectionalLight3D` for the gentle step with `shadow_enabled` off, strong white flat ambient colour. Each object gets a small dark blob quad beneath it (an unshaded transparent `QuadMesh` with a radial gradient). No fog, SSAO or probes. Background is a flat pastel clear colour or a rainbow gradient drawn by a simple `shader_type sky;` shader from `EYEDIR.y`.

### Post-processing

None. Tonemap `Linear` so candy colours stay pure; no glow, depth-of-field blur or vignette, and the whole frame stays sharp. MSAA 4x. No colour needs to go above 1.

### UI and effects

Round bubbles (`StyleBoxFlat` with full corner radius), rainbow arcs and thick circular gauges (`TextureProgressBar` with a clockwise radial fill) in candy fills; icons are tiny boxy objects or two-dot faces. Mix a chunky rounded sans such as Fredoka Bold with a wobbly hand face such as Gochi Hand or Chewy, white or `#5a3a2a` on pink, yellow and sky blue. Counters bounce when they change. Effects are flat sprites or flat meshes: stars, hearts, sparkles and plain puffs that pop out on pickups and bumps, no smoke or debris. Objects wobble, hop and spin as whole rigid pieces and pop in with a squash-and-stretch scale `Tween`; characters waddle through a few rigid poses.

## Do / Do not

Do:

- Reduce every object to a few boxes and cylinders.
- Scatter objects densely.
- Use many bright colours with flat lighting.
- Use stripe, dot and simple-face decals.

Do not:

- Do not round and gloss the forms with tilt-shift blur; that reads as `057`.
- Do not use sharp light-and-shadow toon shading on smooth caricatured characters; that reads as `003`.
- Do not use irregular triangulated terrain; that reads as `066`.
- Do not limit colours to three primaries with geometric purity; that reads as `098`.

## Nearest styles

- `003` Flat-shape ocean toon: `003` has smooth curved caricature characters with crisp toon shadows in a sea-and-sky colour scheme; this style has crude boxy objects, almost no shadow and candy colours everywhere.
- `098` Bauhaus primary geometry: `098` uses pure circles, squares and triangles in red, yellow and blue with black and white, in sparse ordered layouts; this style crowds the frame with naive boxy objects in every candy colour.
- `057` Toy-diorama tilt-shift: `057` has rounded glossy toy forms with soft shading and a blurred top and bottom of frame, like a miniature photograph; this style is matte, boxy and sharp across the whole frame.
