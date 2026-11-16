# Bioluminescent alien jungle

Reference works: Avatar (2009).

## References

- *Avatar* (2009), James Cameron, live-action and computer-animated film. https://en.wikipedia.org/wiki/Avatar_(2009_film)
- *Avatar: The Way of Water* (2022), James Cameron, live-action and computer-animated film. https://en.wikipedia.org/wiki/Avatar:_The_Way_of_Water
- *Avatar: Frontiers of Pandora* (2023), Massive Entertainment, video game. https://en.wikipedia.org/wiki/Avatar:_Frontiers_of_Pandora
- *Subnautica* (2018), Unknown Worlds Entertainment, video game. https://en.wikipedia.org/wiki/Subnautica

## Visual definition

- **Shape language and proportions:** Dense alien jungle at night: giant trees with buttress roots, hanging vines, fan-shaped and spiral plants, mushroom caps, floating seeds like small jellyfish, moss carpets. Organic forms at many scales.
- **Line and outline:** No outline.
- **Shading model:** Realistic smooth shading in very low light, with self-illuminated patterns and soft subsurface glow in leaves.
- **Palette:** `#030812` `#0a2a3a` `#19e6c8` `#3a7bff` `#c44dff` `#7dff6a` `#ff6ad5`. Blue-black darkness with cyan, teal, violet, magenta and green bioluminescence.
- **Lighting:** No sun. Light comes from glowing dots, veins and fringes on plants and creatures; glow intensifies where things are touched. Faint blue moonlight from above.
- **Texture and surface:** Glowing vein networks and dot rows on leaves, speckled moss, wet bark; fine natural detail.
- **Atmosphere and post-processing:** Bloom, depth of field, drifting glowing particles, light mist.
- **Camera and framing:** Inside the forest at eye level looking through layered foliage; 35 mm equivalent, shallow focus.
- **UI and typography:** Thin glowing line frames and soft-edged translucent blue-black panels, with icons drawn as luminous organic glyphs (leaf, spiral, seed). Type is a light rounded sans with a faint glow. Counters are slim cyan `#19e6c8` numerals, with magenta `#ff6ad5` for damage and green `#7dff6a` for healing.
- **VFX and motion:** Drifting glowing spores, ripples of light that spread across plants where they are touched, and floating seeds that pulse; hits burst into luminous motes that fade slowly. Motion is fluid and organic: swaying fronds, gliding creatures, gentle ease in and out.

## Fits

- **Genres:** `exploration`, `survival-craft`, `action-adventure`, `stealth`, `rpg`
- **Moods:** wondrous, serene, mysterious
- **Settings:** alien jungle at night, glowing cave, deep ocean reef, forested alien moon

## Godot recipe

### Assets

Dense jungle packs with realistic detail: giant trees with buttress roots, hanging vines, fan and spiral plants, mushrooms, moss. Keep full PBR maps at high resolution; fine natural detail is part of the style. Add alien pieces from scratch: spiral plants, floating jellyfish-like seeds, large fan leaves. The key authored asset is the glow pattern: a generator script paints emission masks per plant with `Image`, vein networks (branching lines along leaf UVs) and dot rows along edges, each plant family assigned one hue from cyan, teal, violet, magenta or green.

### Materials

Write `bio_leaf.gdshader`, a spatial shader: normal PBR inputs with a dark albedo and wet low roughness on bark, plus `EMISSION` equal to the mask times the family colour times an animated intensity. Intensity combines a slow pulse with a touch response: scripts write the last touch positions and times into a small data texture set as a global shader parameter, and the shader adds a ring of brightness expanding from each touch. Thin leaves add a subsurface glow: emission also leaks to the back face (`FRONT_FACING`) and diffuse is softened by a wide wrap term in `light()`. Alpha scissor and `cull_disabled` for foliage. Floating seeds use an emissive transparent variant with a Fresnel rim from `NORMAL` and `VIEW`.

### Lighting and atmosphere

No sun. A faint blue `DirectionalLight3D` moon from above with soft shadows at low energy. Most light is emissive; add small `OmniLight3D` lights at the brightest plants and creatures, shadows off on most. Ambient light colour blue-black `#030812`. Bake `LightmapGI` with emissive contribution for static plants. Light depth fog in `#0a2a3a` and thin mist cards. SSAO on, medium; `ReflectionProbe` at low intensity for wet bark. On the Mobile renderer: there is no SSAO, so rely on the lightmap and occlusion maps, and keep at most eight omni lights reaching any one mesh.

### Post-processing

Glow with HDR threshold 1, moderate intensity and medium bloom spread: glow must stay tied to veins and dots, not flood the frame. Depth-of-field blur from `CameraAttributesPractical`, moderate amount, on far and very near foliage. `ACES` tonemapping with adjustment saturation 1.1 so glow hues stay vivid against true darkness. Slight vignette from a `canvas_item` shader on a `ColorRect`. TAA. On the Mobile renderer: TAA is missing, so use MSAA 4x, and keep emission values moderate because the 10-bit colour buffer bands wide glow sooner.

### UI and effects

Thin glowing line frames and soft-edged translucent blue-black panels (`StyleBoxFlat` with a thin cyan border and a cyan shadow as the glow); icons are luminous organic glyphs (leaf, spiral, seed). Font imported from a light rounded sans such as Quicksand Light or Comfortaa, with `LabelSettings` giving a soft cyan outline as the glow; slim cyan numerals, magenta `#ff6ad5` for damage, green `#7dff6a` for healing. Particles: slow drifting additive spores with turbulence and long lifetimes, pulsing floating seeds, and luminous motes on hits that fade over one to two seconds. Fronds sway in `vertex()`; creatures glide with gentle easing.

## Do / Do not

Do:

- Light the scene only from glowing plants and a faint moon.
- Put vein and dot patterns on leaves.
- Use several glow hues: cyan, violet, magenta, green.
- Add drifting glowing particles and bloom.

Do not:

- Do not simplify into soft painted shapes with a glowing hero; that reads as `027`.
- Do not use straight emissive circuit lines on geometric solids; that reads as `088`.
- Do not add urban neon signs and rain; that reads as `089`.
- Do not add daylight.

## Nearest styles

- `027` Glowing forest painterly: this style shows realistic, finely detailed plants in deep darkness with many vivid glow colours; `027` is lighter and softer, with simplified painted shapes and one glowing hero.
- `088` Neon grid cyberspace: glow here follows veins and dot rows on dense organic foliage in many hues; `088` is straight glowing lines on bare geometric solids in only a few colours.
- `089` Rain-soaked tech-noir: light here comes from plants and creatures in vivid cyan, violet and magenta; `089` is a city where neon signs reflect in wet streets, with duller colour between the lights.
