# Glowing forest painterly

Reference works: Ori and the Blind Forest.

## References

- *Ori and the Blind Forest* (2015), Moon Studios, video game. https://en.wikipedia.org/wiki/Ori_and_the_Blind_Forest
- *Ori and the Will of the Wisps* (2020), Moon Studios, video game. https://en.wikipedia.org/wiki/Ori_and_the_Will_of_the_Wisps
- *Trine 2* (2011), Frozenbyte, video game. https://en.wikipedia.org/wiki/Trine_2
- *Rayman Legends* (2013), Ubisoft Montpellier, video game. https://en.wikipedia.org/wiki/Rayman_Legends

## Visual definition

- **Shape language and proportions:** Organic, twisting forest forms: gnarled roots, hanging vines, mushrooms, mossy rocks. The hero is a small, simple, glowing white figure.
- **Line and outline:** No outline. Foreground elements are dark silhouettes.
- **Shading model:** Soft painted gradients with strong glow light sources. Smooth.
- **Palette:** `#0d1b2a` `#1b4965` `#5fa8d3` `#bee9e8` `#ffd166` `#7b2cbf` `#2d6a4f` `#ffffff`. Deep blue and teal night forest with cyan, gold and violet light sources and a white-glowing hero.
- **Lighting:** Many small emissive sources (spirit lights, glowing plants) and shafts of light; strong backlight.
- **Texture and surface:** Painterly foliage and bark with soft detail; layered depth with blurred near and far planes.
- **Atmosphere and post-processing:** Heavy bloom, light shafts, floating particles, depth of field on foreground and background layers, vignette.
- **Camera and framing:** Side-on, layered parallax; medium-wide.
- **UI and typography:** Frameless UI: glowing icons and thin luminous lines laid directly over the scene, with round orbs for health and energy. Text is a light, elegant serif with a soft glow, and counters are small glowing numerals. UI colours are pale cyan `#bee9e8` and white `#ffffff`, with gold `#ffd166` for pickups.
- **VFX and motion:** Dense particles: glowing motes, drifting leaves, light trails behind the hero and soft sparkle bursts on hits. Animation is quick and fluid, with strong squash and stretch and bright arcs on jumps and dashes.

## Fits

- **Genres:** `platformer`, `exploration`, `action-adventure`, `puzzle`
- **Moods:** wondrous, bittersweet, magical
- **Settings:** enchanted night forest, glowing caverns, ancient spirit trees, misty swamps

## Godot recipe

### Assets

Organic forest packs: gnarled roots, vines, mushrooms, mossy rocks. Arrange them in side-on parallax layers. Soften textures by blurring albedo in a generator script and lowering `normal_scale` so detail is painterly. Foreground pieces become pure dark silhouettes (a black unshaded material). Glowing plants get emission masks painted in a generator script. The hero is a small simple white figure, easiest to build from scratch, with an emissive material.

### Materials

Midground scenery uses `StandardMaterial3D` with high roughness and emission on (`emission_enabled`, emission colour in cyan, gold or violet with `emission_energy_multiplier` above 1 so it glows). Foreground silhouettes use an unshaded `StandardMaterial3D` in `#0d1b2a`. The hero uses an `unshaded` spatial shader whose `EMISSION` is scaled by a Fresnel falloff (`pow(1.0 - dot(NORMAL, VIEW), k)`) so the glow is brighter at the rim. Foliage uses an alpha-scissor material in a spatial shader with vertex sway from `TIME` in `vertex()`. Light shafts are additive (`blend_add`) unshaded quads with a scrolling noise mask and a soft depth fade against the scene (`proximity_fade_enabled` on a `StandardMaterial3D`, or `hint_depth_texture` in a shader).

### Lighting and atmosphere

Many small `OmniLight3D`s at spirit lights and glowing plants: Forward+ handles them; keep shadows off on most. One dim blue `DirectionalLight3D` backlight with soft shadows (`light_angular_distance`). Ambient deep blue. `Environment` fog in `#1b4965` so far layers stay visible as blue shapes, which keeps the scene readable behind the black foreground. No baked lighting needed for a side-scroller; SSAO off. On the Mobile renderer: keep each mesh within 8 omni lights (split large meshes, move the rest of the glow into emission), and soften the backlight's shadow with `shadow_blur`.

### Post-processing

This style relies on the `Environment` and camera attributes. Glow with a low HDR threshold (0.8), high intensity and the upper glow levels enabled for wide scatter. Far and near depth-of-field blur on `CameraAttributesPractical` focused on the gameplay plane, so near and far layers blur. Vignette at 0.35 to 0.45 in a `ColorRect` shader on a `CanvasLayer`. `Reinhard` or `ACES` tonemapping, `adjustment_saturation` slightly above 1, and a colour-correction `GradientTexture1D` pushing shadows toward blue. SMAA.

### UI and effects

Frameless UI: glowing icons and thin luminous lines over the scene, round orbs for health and energy drawn with a radial `TextureProgressBar` or a radial-fill `canvas_item` shader. Font from a light elegant serif such as Cormorant Garamond Light with a soft glow (a `LabelSettings` shadow in `#bee9e8` with zero offset and a large size), in `#bee9e8` and white; gold for pickups. Particles are dense: hundreds of additive glowing motes with noise motion (`ParticleProcessMaterial` turbulence), drifting leaves, a light trail behind the hero (`GPUParticles3D` trails or a ribbon mesh) and soft sparkle bursts on hits.

## Do / Do not

Do:

- Put a dark silhouette layer in front and blurred layers behind.
- Use many small glowing sources with strong bloom.
- Make the hero the brightest object.
- Add drifting particles and light shafts.

Do not:

- Do not use pure black silhouettes on grey fog without colour; that reads as `070`.
- Do not cover plants in neon patterns with photoreal detail; that reads as `093`.
- Do not light evenly with painted albedo detail; that reads as `023`.
- Do not add outlines.

## Nearest styles

- `093` Bioluminescent alien jungle: this style has soft painted forms, gentle glow and a visible deep-blue forest behind; `093` is almost black, with sharp realistic leaf detail and vivid neon patterns.
- `070` Silhouette fog monochrome: behind the dark foreground this style is full of colour, in deep blue, cyan, gold and violet; `070` uses only black and greys.
- `023` Chunky hand-painted fantasy: this style is dark, with glowing light sources and heavy bloom; `023` is bright and evenly lit, with detail painted onto the surfaces.
