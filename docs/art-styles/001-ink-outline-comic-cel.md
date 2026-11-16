# Ink-outline comic cel

Reference works: Borderlands.

## References

- *Borderlands* (2009), Gearbox Software, video game. https://en.wikipedia.org/wiki/Borderlands_(video_game)
- *Borderlands 2* (2012), Gearbox Software, video game. https://en.wikipedia.org/wiki/Borderlands_2
- *Borderlands 3* (2019), Gearbox Software, video game. https://en.wikipedia.org/wiki/Borderlands_3
- *Tales from the Borderlands* (2014), Telltale Games, video game. https://en.wikipedia.org/wiki/Tales_from_the_Borderlands

## Visual definition

- **Shape language and proportions:** Realistic proportions with exaggerated mechanical detail. Hard-surface props are boxy, welded, dented and asymmetric; panels overlap and bolts are oversized.
- **Line and outline:** Black ink on every silhouette and on most creases. Line width changes along the stroke (2 to 6 px at 1080p), heavier on silhouettes than on inner edges, with visible wobble.
- **Shading model:** Three flat bands (lit, half tone, shadow). Shadow areas carry hand hatching; full shadow gets cross-hatching.
- **Palette:** `#17110f` `#c9772e` `#e8c27a` `#8a3b24` `#5f7f86` `#6b4f8a` `#f2e2c0`. Dusty oranges, rust and sand against cool steel blue; shadows lean violet; ink is a warm near-black.
- **Lighting:** One hard warm sun at a low angle plus flat ambient. Cast shadows have hard edges.
- **Texture and surface:** Textures look inked by hand: panel lines, scratches, chipped paint, rivets and hatch strokes drawn over flat base colours.
- **Atmosphere and post-processing:** Warm distance haze, light paper grain, soft vignette. No bloom, no depth of field.
- **Camera and framing:** 35 to 50 mm equivalent, eye level or slightly low, wide establishing shots with strong foreground props.
- **UI and typography:** Panels look like inked comic captions: sand and rust fills (`#e8c27a`, `#c9772e`) inside a wobbly warm-black border. Type is bold condensed grotesque capitals set at a slight slant; icons are flat inked pictograms. Damage numbers are heavy outlined digits in cream, with orange for critical hits.
- **VFX and motion:** Explosions, muzzle flashes and smoke are flat inked shapes with black outlines and hatched shadows, not soft sprites. Hits throw short ink speed lines and outlined spark stars; motion is weighty, with snappy recoil and brief held poses on impact.

## Fits

- **Genres:** `fps`, `rpg`, `vehicle-combat`, `third-person-shooter`, `top-down-shooter`
- **Moods:** irreverent, rowdy, gritty
- **Settings:** desert wasteland, scrapyard outpost, frontier mining planet

## Godot recipe

### Assets

Pick hard-surface packs with boxy, welded shapes: scrapyards, industrial kits, post-apocalyptic vehicles, realistic-proportion characters. In a generator script, drop every normal, metallic and occlusion map and rebuild each albedo with `Image`: posterise it to a few flat palette colours, then draw ink over it by running a Sobel filter on the pack's old normal map and albedo and stamping the result as warm-black strokes (`#17110f`). Keep 1024 to 2048 px with linear filtering and mipmaps so strokes stay smooth. Build oversized bolts, weld seams, plates and signs from scratch with `SurfaceTool`, and paint two tiling hatch textures (single hatch, cross-hatch) in the same script with `save_png`.

### Materials

Write one spatial shader, for example `ink_cel.gdshader`. Its `light()` turns `dot(NORMAL, LIGHT) * ATTENUATION` (attenuation carries the shadow) into three bands with two `step` thresholds offset by a low-frequency noise sample, so band edges are hard but slightly irregular. The half-tone band multiplies in the hatch texture and the shadow band the cross-hatch, both sampled in screen space from a screen position passed from `fragment()` through a varying; shadow colour shifts toward `#6b4f8a`. `light()` runs once per light, so extra lights band the same way; shadow casting and depth need nothing extra. The silhouette line is a second material in `next_pass`: a shader with `render_mode unshaded, cull_front;` that pushes vertices in `vertex()` along smoothed normals, which the generator script stores in the `CUSTOM0` vertex channel; vary the width from 2 to 6 px with a noise lookup along the surface. Write the materials as `.tres` files and set them as surface overrides in the scenes.

### Lighting and atmosphere

One `DirectionalLight3D`, warm and low (25 to 35 degrees), with hard shadows: `light_angular_distance` 0, the directional soft shadow filter quality project setting on Hard, shadow mode PSSM 2 Splits, `directional_shadow_max_distance` 60 m. Flat ambient in the `Environment` (source Color) in a warm mid tone, no `LightmapGI`, no SSAO. Depth fog in pale sand gives the distance haze over a simple gradient sky written as a `shader_type sky;` shader.

### Post-processing

Add a full-screen quad (a `MeshInstance3D` with a 2x2 `QuadMesh` in front of the camera, `POSITION = vec4(VERTEX.xy, 1.0, 1.0);`) whose shader reads `hint_depth_texture` and `hint_normal_roughness_texture` and draws thin crease lines where normals break, with the sample position offset by scrolling noise so lines wobble. A `ColorRect` on a `CanvasLayer` with a `canvas_item` shader adds a soft vignette and low grain as paper tooth. Tonemap Linear; glow and depth-of-field blur off. `rendering/scaling_3d/scale` 1, MSAA 3D 4x. On the Mobile renderer: the normal-roughness texture is missing, so the crease pass rebuilds normals from the depth texture and draws lines where they break.

### UI and effects

Import a bold condensed grotesque such as Barlow Condensed ExtraBold Italic as a `FontFile` and set it as the `Theme` default font; `LabelSettings` give it a thick warm-black outline (`outline_size`, `outline_color`). Panels are `StyleBoxTexture` 9-slices of a texture drawn by a generator script: sand or rust fill inside an uneven black border. Particles are `GPUParticles3D` drawing a `QuadMesh` with an unshaded, alpha-scissor, billboard `StandardMaterial3D` and a flipbook of inked smoke, flash and star shapes, its animation speed set to advance 12 frames per second; add stretched black speed-line quads on hits. No soft additive sprites.

## Do / Do not

Do:

- Vary line weight along each stroke and between silhouette and crease.
- Keep band boundaries hard and slightly noisy.
- Put hatching only in shadow and half tone.
- Paint wear marks as ink shapes, not as noise.

Do not:

- Do not use constant-width clean lines with flat fills; that reads as `011`.
- Do not add halftone dots or misregistered colour; that reads as `009`.
- Do not use smooth PBR shading under the outlines.
- Do not fill large areas with solid black; that reads as `010`.

## Nearest styles

- `009` Halftone print comic: this style shades with hand-drawn hatch strokes and inks every silhouette; `009` shades with printed dot screens, leaves some contours unlined and prints its colour layers out of register.
- `004` Graffiti street cel: this style has three tone steps, a wobbly line of changing width and hatching over worn surfaces; `004` has two tone steps, an even line and clean flat surfaces apart from its graffiti.
- `010` Heavy-black gothic comic: this style stays bright, with shadows drawn as hatching over colour; `010` drops about half of every form into solid black.
