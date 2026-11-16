# Glossy ink-splat pop

Reference works: Splatoon.

## References

- *Splatoon* (2015), Nintendo EAD, video game. https://en.wikipedia.org/wiki/Splatoon_(video_game)
- *Splatoon 2* (2017), Nintendo EPD, video game. https://en.wikipedia.org/wiki/Splatoon_2
- *Splatoon 3* (2022), Nintendo EPD, video game. https://en.wikipedia.org/wiki/Splatoon_3
- *De Blob* (2008), Blue Tongue Entertainment, video game. https://en.wikipedia.org/wiki/De_Blob

## Visual definition

- **Shape language and proportions:** Stylised teen characters with large heads; urban props with rounded, toy-like simplification. Ink splats are thick, blobby pools with raised edges.
- **Line and outline:** No outlines.
- **Shading model:** Smooth PBR-like shading. Ink is glossy with sharp bright specular highlights; base surfaces are matte.
- **Palette:** `#f02d7d` `#19d719` `#603bff` `#ff8a00` `#1ad6c5` `#2b2b33` `#f5f5f0`. Two opposing neon ink colours (for example pink against green) covering neutral grey concrete and white.
- **Lighting:** Bright overcast-sun mix with a clear environment reflection in the ink.
- **Texture and surface:** Base surfaces have simple material detail (concrete speckle, painted metal). Ink has glitter flecks and a visible thickness.
- **Atmosphere and post-processing:** Light bloom on ink highlights; colours stay clean.
- **Camera and framing:** Third-person, slightly above, 35 mm equivalent.
- **UI and typography:** Sticker-like panels tilted off axis with rounded, wobbly edges, in the two ink colours on dark grey (`#2b2b33`) or white. Type is a chunky rounded display face with a hand-cut look, and icons are flat splat-shaped badges. Counters are big bold numerals that bounce when they change.
- **VFX and motion:** Ink flies as thick glossy blobs and droplets that land as splats with a raised rim; hits burst in the attacker's ink colour with glitter flecks. Animation is quick and bouncy, with squash and stretch on characters and wobble on ink.

## Fits

- **Genres:** `third-person-shooter`, `sports`, `platformer`, `top-down-shooter`, `puzzle`
- **Moods:** playful, energetic, upbeat
- **Settings:** city plaza, skate park, shopping district, rooftop arena

## Godot recipe

### Assets

Stylised urban packs with rounded, toy-like props and teen-proportioned characters. Keep the pack's PBR maps but simplify: flatten albedos to concrete grey and white, keep a light concrete speckle, set roughness high. Ink is built from scratch: generate splat masks and a matching height map with `Image` in a generator script, and thick blob meshes (metaball-like lumps with a raised rim) in Blender by script, imported as `.glb`, for pools and projectiles.

### Materials

Base surfaces use a `StandardMaterial3D` with high roughness. Ink surfaces need a custom spatial shader, for example `ink_coat.gdshader`, that keeps Godot's own PBR lighting (no `light()` function) and only fills `ALBEDO`, `ROUGHNESS`, `NORMAL_MAP` and `EMISSION`. A world-space splat mask (a `SubViewport` that draws splat stamps from above at runtime, read as a `ViewportTexture` by world XZ) selects ink colour and sets roughness to 0.05; derive a normal from the mask's height so the edge looks raised. Add glitter by thresholding a high-frequency noise against the view direction into `EMISSION`. Shadows, depth and `LightmapGI` baking need nothing extra. The two ink colours are global shader uniforms set with `RenderingServer.global_shader_parameter_set` so teams can be swapped.

### Lighting and atmosphere

Bright `DirectionalLight3D` sun with soft shadows mixed with a strong sky ambient. Reflection probes matter here: place `ReflectionProbe`s with box projection on and update mode Once so ink shows clear environment reflections. PSSM 4 Splits, `directional_shadow_max_distance` 100 m. SSAO on at low intensity. No fog. On the Mobile renderer: there is no SSAO, so paint soft contact darkening into the base albedos or vertex colour, or bake it with `LightmapGI`.

### Post-processing

Tonemap Linear keeps the neons clean; ACES or Filmic would dull them. Glow with an HDR threshold near 1.1 and low intensity so only ink highlights and glitter glow. `adjustment_saturation` slightly above 1. No grain, no vignette. MSAA 3D 4x.

### UI and effects

Use a chunky rounded display face such as Lilita One. Panels are `StyleBoxTexture` stickers with wobbly rounded edges, rotated off axis, in the two ink colours on `#2b2b33` or white; icons sit on splat-shaped badges. Counters bounce with a scale `Tween` when they change. Ink shots are projectiles carrying the blob mesh with the ink shader, stretched along velocity, that stamp a splat into the mask viewport on contact; hits burst in the attacker's colour with small additive (`blend_add`) glitter billboards from `GPUParticles3D`.

## Do / Do not

Do:

- Limit ink to two opposing hues per scene.
- Make ink clearly glossier than the base surface.
- Give ink pools a raised rounded rim.
- Cover large parts of the floor with ink and leave bare ground visible between the pools.

Do not:

- Do not add black outlines or flat bands; that reads as `004`.
- Do not use many unrelated hues; that reads as `013`.
- Do not make every surface hard glossy plastic with studs; that reads as `052`.
- Do not leave ink flat without specular.

## Nearest styles

- `013` Stylised hero PBR: this style lets two neon ink hues dominate neutral grey and white ground, with glossy ink on matte surfaces; `013` spreads many softer hues across the scene with an even material finish.
- `052` Brick toy: this style shows concrete speckle and painted metal on base surfaces and keeps gloss for the ink; `052` makes everything clean glossy plastic with studs and seams.
- `004` Graffiti street cel: this style has no outline and smooth shading with glossy highlights; `004` puts a black outline on every silhouette and shades in two flat tone steps.
