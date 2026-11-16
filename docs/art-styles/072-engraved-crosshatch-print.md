# Engraved crosshatch print

Reference works: Gustave Dore engravings.

## References

- *Illustrations for The Divine Comedy* (1861), Gustave Dore, wood engraving. https://en.wikipedia.org/wiki/Gustave_Doré
- *Melencolia I* (1514), Albrecht Durer, copper engraving. https://en.wikipedia.org/wiki/Melencolia_I
- *Knight, Death and the Devil* (1513), Albrecht Durer, copper engraving. https://en.wikipedia.org/wiki/Knight,_Death_and_the_Devil
- *The Rime of the Ancient Mariner (illustrated edition)* (1876), Gustave Dore, wood engraving. https://en.wikipedia.org/wiki/The_Rime_of_the_Ancient_Mariner

## Visual definition

- **Shape language and proportions:** Realistic, dramatic subjects: figures, drapery, rocks, clouds, architecture, rendered with careful volume.
- **Line and outline:** Black contour on forms, plus tone built entirely from fine parallel lines that follow the surface curvature.
- **Shading model:** Four to six tone levels from line density: bare paper, single hatch, closer hatch, cross-hatch, double cross-hatch, solid black. Lines swell and taper.
- **Palette:** `#14110f` `#f2ead8` `#3a332c` `#8a8072` `#d6ccb6`. Black ink on cream paper. The intermediate values listed are apparent tones of hatching.
- **Lighting:** Strong directional light with deep shadows and bright rim-lit edges; light rays drawn as parallel lines.
- **Texture and surface:** Hatching everywhere except highlights. Line direction changes by surface: horizontal for sky and water, curved around limbs, vertical for walls.
- **Atmosphere and post-processing:** Paper tone and slight ink spread; no colour.
- **Camera and framing:** Grand, composed views; any lens.
- **UI and typography:** Panels look like book plates: a thin double ruled border on cream paper `#f2ead8`, with engraved corner ornaments and a caption strip below. Text is a high-contrast old-style book serif with small-capital headings, numbers are old-style engraved numerals in black ink, and icons are small hatched vignettes; bars fill with hatching that gets denser, never with colour.
- **VFX and motion:** Smoke, dust, light rays and water spray are drawn as bundles of parallel or curling engraved lines, and impacts are radiating line bursts with bare-paper flashes. Motion is weighty and stately, with hatch lines that stay attached to surfaces instead of shimmering.

## Fits

- **Genres:** `soulslike`, `rpg`, `action-adventure`, `exploration`, `strategy`, `hack-and-slash`
- **Moods:** solemn, epic, ominous
- **Settings:** underworld, medieval kingdom, storm-tossed sea, gothic cathedral

## Godot recipe

### Assets

Realistic, dramatic subjects with clear volume: figures, drapery, rocks, clouds, architecture. Use realistic packs and keep their geometry and smooth normals; discard colour textures. Hatching must follow surface curvature, so UV layout matters: a generator script checks or rebuilds UVs with `MeshDataTool` so the U direction runs around limbs and along folds, and assigns a hatch direction per material (horizontal for sky and water, vertical for walls). Generate a tonal art map set in a generator script with `Image`: six hatch textures from sparse single lines to double cross-hatch, with lines that swell and taper, each level containing the strokes of the previous one. Draw every mip level yourself so line width stays constant with distance, pack the levels into one `Image` with `Image.create_from_data` and save it with `ResourceSaver`, so no import step regenerates the mips.

### Materials

Write `engraving.gdshader`, a spatial shader. `light()` computes a tone from `dot(NORMAL, LIGHT)` times `ATTENUATION` (so shadows count), plus a rim highlight from `VIEW` that stays bare paper, then blends between the two nearest hatch levels sampled at `UV`, which keeps lines attached to surfaces, and writes the result with `DIFFUSE_LIGHT = max(DIFFUSE_LIGHT, ...)` so lights never add up. `fragment()` sets `ALBEDO` to white, and `render_mode specular_disabled` keeps highlights out. Above the brightest level output paper; below the darkest output solid ink `#14110f`. Threshold the result to keep lines crisp. Shadow casting and depth come with every spatial shader. The sky is a `shader_type sky;` shader drawing horizontal hatch lines from `EYEDIR`. Outline comes from post.

### Lighting and atmosphere

One strong `DirectionalLight3D` with `shadow_enabled` and deep shadows, hard or slightly soft edges (small `light_angular_distance`), plus a second `DirectionalLight3D` from behind with shadows off for bright rim edges. Ambient is ignored: `Environment` ambient light energy 0. No fog; distance is shown by sparser hatch. No SSAO, no `ReflectionProbe`. Light rays are mesh fans built with `SurfaceTool` and textured with parallel lines.

### Post-processing

A full-screen `QuadMesh` in front of the camera with a spatial shader reading `hint_depth_texture` and `hint_normal_roughness_texture` draws firm black contours from depth and normal edges, about 2 px. On a `CanvasLayer` above it, a `ColorRect` with a `canvas_item` shader reading `hint_screen_texture` maps the image to ink on cream paper `#f2ead8`, multiplies a paper texture and applies a very slight blur-then-threshold for ink spread. Tonemap Linear, no glow, no colour, no grain. Keep `rendering/scaling_3d/scale` at 1 or higher with SMAA; fine lines alias badly at low resolution. On the Mobile renderer: the normal-roughness texture is missing, so draw contours from depth edges only, rebuilding normals from depth differences between neighbouring pixels.

### UI and effects

Book-plate panels: a `Theme` `StyleBoxTexture` that 9-slices a thin double ruled border on cream with engraved corner ornaments, and a caption strip below. Font from an old-style book serif such as IM Fell English or EB Garamond, imported as a `FontFile` and set as the theme default font, small-capital headings, old-style numerals. Icons are small hatched vignettes; bars are `TextureProgressBar` nodes filling with denser hatching. Effects are line bundles: smoke and spray as curling ribbon meshes with a line texture on an unshaded alpha-scissor material, radiating line bursts with a bare-paper flash on impact.

## Do / Do not

Do:

- Build all tone from line density.
- Make hatch lines follow surface curvature.
- Swell line width as tone darkens.
- Leave highlights as bare paper.

Do not:

- Do not use dot screens; that reads as `020`.
- Do not use pixel dither at low resolution; that reads as `041`.
- Do not use soft graphite smudges and grey tone; that reads as `073`.
- Do not add colour bands with hatching only in shadow; that reads as `001`.

## Nearest styles

- `020` Manga screentone monochrome: this style builds every grey from fine curved hatch lines that wrap around the forms, covering almost the whole picture; `020` fills flat areas with dot screens and leaves large clean black and white shapes.
- `073` Graphite pencil sketch: this style is pure black ink on cream paper with firm contours and precise, dense hatching; `073` is soft grey pencil with loose doubled lines, smudges and scribbled shading.
- `041` One-bit dither: this style is a mostly light page of smooth curved hatch lines at full resolution; `041` is a darker low-resolution image whose tone comes from square pixel dither patterns.
