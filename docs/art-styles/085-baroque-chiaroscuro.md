# Baroque chiaroscuro

Reference works: Caravaggio.

## References

- *The Calling of Saint Matthew* (1600), Caravaggio, oil painting. https://en.wikipedia.org/wiki/The_Calling_of_Saint_Matthew
- *Judith Beheading Holofernes* (c. 1599), Caravaggio, oil painting. https://en.wikipedia.org/wiki/Judith_Beheading_Holofernes_(Caravaggio)
- *The Night Watch* (1642), Rembrandt, oil painting. https://en.wikipedia.org/wiki/The_Night_Watch
- *Girl with a Pearl Earring* (c. 1665), Johannes Vermeer, oil painting. https://en.wikipedia.org/wiki/Girl_with_a_Pearl_Earring
- *Barry Lyndon* (1975), Stanley Kubrick, live-action film. https://en.wikipedia.org/wiki/Barry_Lyndon

## Visual definition

- **Shape language and proportions:** Realistic human figures and still-life objects (cloth, fruit, vessels, tables) in close, shallow interior space. Heavy drapery with deep folds.
- **Line and outline:** No outline. Edges on the shadow side dissolve into the background (lost edges).
- **Shading model:** Smooth, strongly directional modelling from bright lit flesh to deep shadow, with a soft terminator. Most of the picture is dark.
- **Palette:** `#0a0705` `#3a2416` `#8a4b2a` `#c9905a` `#e8cfa0` `#7a1f1a` `#2a3a2f`. Warm darks: black-brown background, umber and sienna midtones, golden flesh lights, deep red and dull green drapery.
- **Lighting:** A single shaft of light from high on one side, as from a small window; no fill. The background wall is almost black with a diagonal edge of light.
- **Texture and surface:** Smooth glazed oil surface; fine fabric and skin detail visible only in lit areas; subtle craquelure.
- **Atmosphere and post-processing:** Warm varnish tint, strong vignette into black.
- **Camera and framing:** Close, eye-level, half- or three-quarter-length figures; 50 to 85 mm equivalent.
- **UI and typography:** Minimal and dark: thin gilt frame lines on black-brown panels with a warm varnish tone; icons are small painted still-life objects (candle, key, skull, coin) lit from one side. Text is an old-style serif with italic for emphasis, in golden cream. Numbers are old-style numerals in gold, with deep red for damage.
- **VFX and motion:** Particles are dust motes in the light shaft, candle smoke and sparks from steel; blood is dark red and glossy, visible only where the light hits it. A hit throws the figure into or out of the light. Motion is weighty and realistic, with heavy cloth that follows through.

## Fits

- **Genres:** `soulslike`, `stealth`, `survival-horror`, `detective-mystery`, `action-adventure`, `rpg`
- **Moods:** dramatic, solemn, tense
- **Settings:** 17th-century tavern, candlelit chapel, palace interior, cellar

## Godot recipe

### Assets

Realistic human figures and still-life props (cloth, fruit, vessels, tables, candles) staged in close, shallow interior space. Use high-quality realistic characters and props with full PBR maps; heavy drapery needs deep modelled folds or cloth simulation baked in Blender. Keep fine fabric and skin detail, since it will show only in the light. Smooth, glazed surfaces: reduce roughness-map noise in a generator script with `Image`. Generate a subtle craquelure overlay texture.

### Materials

`StandardMaterial3D` for props and cloth; velvet and heavy drapery with high roughness, vessels and fruit with low roughness for a glazed look. Skin uses `StandardMaterial3D` with `diffuse_mode` Lambert Wrap and sub-surface scattering (`subsurf_scatter`) with a warm transmission tint, to keep the terminator soft and golden. On the Mobile renderer: drop sub-surface scattering and add the warm tint at the terminator in a skin shader's `light()` instead, on top of the wrapped diffuse. Blood is dark red with roughness 0.1. Background walls are dark, rough `StandardMaterial3D` surfaces. No outline; shadow-side edges should vanish into the ground, so avoid rim lighting.

### Lighting and atmosphere

A single shaft from high on one side: one `SpotLight3D` with a narrow-to-medium cone, warm white, `shadow_enabled` with a soft penumbra (raise `light_size`) and a high-resolution positional shadow atlas. No fill light. Ambient almost black with a warm brown tint (`#0a0705`); bake a very dim `LightmapGI` so bounce from lit cloth lifts nearby shadows slightly. Let the spot rake the back wall to draw a diagonal edge of light. No `DirectionalLight3D`, no fog; a faint additive cone mesh with dust motes marks the shaft. SSAO on, medium. On the Mobile renderer: no SSAO; let the baked `LightmapGI` darken the contacts.

### Post-processing

`ACES` tonemap with exposure set for the lit flesh, letting the rest fall to black. Warm varnish tint and warm white balance through the `Environment` adjustments colour-correction texture (a `GradientTexture1D` pulled toward pale amber). Strong vignette (0.5 to 0.6) into black in a `canvas_item` shader on a `ColorRect` on a `CanvasLayer`. Slight depth-of-field blur from `CameraAttributesPractical`. A final optional pass in the same shader overlays craquelure at very low strength. No glow, no grain of note, no chromatic aberration. TAA. On the Mobile renderer: SMAA or MSAA 4x instead of TAA.

### UI and effects

Minimal and dark: thin gilt frame lines on black-brown panels (`StyleBoxFlat` border); icons are small still-life objects (candle, key, skull, coin) rendered from models lit from one side in a `SubViewport`. The `Theme` font is an old-style serif with italics such as EB Garamond or Cormorant Garamond, golden cream `#e8cfa0`; old-style numerals in gold, `#7a1f1a` for damage. Particles: lit dust motes in the shaft, candle smoke, sparks from steel. Give the particle materials normal per-pixel shading, not unshaded, so particles vanish outside the light. Cloth follows through heavily.

## Do / Do not

Do:

- Light with one high side source and no fill.
- Let shadow-side edges disappear into a black background.
- Keep the palette to warm earth colours.
- Use deep drapery folds to catch the light.

Do not:

- Do not use cold grey-green decay and a flashlight; that reads as `029`.
- Do not remove colour; that reads as `068`.
- Do not add coloured neon or rain; that reads as `089`.
- Do not light the background.

## Nearest styles

- `029` Survival-horror dark photoreal: this style has warm earth colours, golden flesh and smooth glazed surfaces under one window shaft; `029` is cold grey-green with gritty decayed surfaces lit by a flashlight.
- `068` Film noir hard light: this style keeps warm colour in golden skin and red and green drapery; `068` is black and white.
- `049` Gothic stop-motion puppet: this style has realistic figures, most of them lost in black; `049` shows more of the scene and has thin stylised puppets.
