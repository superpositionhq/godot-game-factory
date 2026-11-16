# Stylised hero PBR

Reference works: Overwatch.

## References

- *Overwatch* (2016), Blizzard Entertainment, video game. https://en.wikipedia.org/wiki/Overwatch_(2016_video_game)
- *Overwatch 2* (2022), Blizzard Entertainment, video game. https://en.wikipedia.org/wiki/Overwatch_(2023_video_game)
- *Valorant* (2020), Riot Games, video game. https://en.wikipedia.org/wiki/Valorant
- *Fortnite* (2017), Epic Games, video game. https://en.wikipedia.org/wiki/Fortnite
- *Big Hero 6* (2014), Walt Disney Animation Studios, animated film. https://en.wikipedia.org/wiki/Big_Hero_6_(film)

## Visual definition

- **Shape language and proportions:** Heroic, slightly exaggerated proportions with clean large forms, chamfered hard-surface armour and readable silhouettes. Small detail is grouped into a few areas.
- **Line and outline:** No outline.
- **Shading model:** Full PBR with smooth gradients, simplified: broad clean roughness regions, soft ambient occlusion and bright rim light.
- **Palette:** `#f79e1b` `#2d9cdb` `#f2f2f2` `#3c4654` `#e74c3c` `#7ed6a5` `#ffd66b`. Bright, optimistic: clean white and grey armour with orange, blue and teal accents; emissive strips.
- **Lighting:** Sunny key, strong coloured fill and bounce; environments are evenly lit and airy.
- **Texture and surface:** Clean material definition with hand-painted gradients inside PBR maps; little noise or grime.
- **Atmosphere and post-processing:** Bloom on emissives, mild colour grade toward warm highlights and cool shadows, anti-aliased.
- **Camera and framing:** Third or first person, 40 to 50 mm equivalent, heroic low angles.
- **UI and typography:** Slanted, semi-transparent dark panels with chamfered corners and thin white edges; icons are flat white glyphs in circles or hexagons. Text is a bold italic condensed sans in white, with orange for the player and blue or red for teams. Damage numbers and ability counters are large slanted white numerals that pop and fade, with yellow for critical hits.
- **VFX and motion:** Effects are clean, bright shapes colour-coded per character: thick tracer streaks, soft-edged energy shields, chunky sparks and a short shaped flash on hit. Animation is snappy with strong anticipation, slight squash and stretch and a clear held pose at the end of each move.

## Fits

- **Genres:** `fps`, `third-person-shooter`, `top-down-shooter`, `tower-defense`, `vehicle-combat`, `sports`
- **Moods:** optimistic, energetic, heroic
- **Settings:** near-future city, sunny Mediterranean town, high-tech laboratory, moon base

## Godot recipe

### Assets

Hero-shooter style packs: slightly heroic proportions, chamfered hard-surface armour, clean large forms. PBR packs are a good base because the style keeps PBR. Clean them in a generator script with `Image`: remove grime and noise from albedo with a strong blur plus palette remap, add a soft top-to-bottom gradient, and rebuild the roughness map as a few broad flat regions instead of scratches. Keep normal maps for bevels and panel breaks only. Add emissive strips as separate thin meshes or an emission mask painted by script.

### Materials

`StandardMaterial3D` (metallic workflow, per-pixel shading, Burley or Lambert diffuse, SchlickGGX specular) is the right material; no custom lighting is needed. Write each as a `.tres` with albedo texture, a reduced normal map strength, metallic, roughness, the ambient occlusion map, and emission on with an energy of 2 to 4 for strips. For the bright rim, turn on the material's rim (rim about 0.5, tint about 0.3), or place rim lights. Turn on clearcoat for lacquered armour if wanted.

### Lighting and atmosphere

A sunny `DirectionalLight3D` key with soft shadows (`light_angular_distance` about 1 degree), PSSM 4 Splits, `directional_shadow_max_distance` 120 m. Strong coloured fill is the signature: bake indirect light with `LightmapGI` on static scenery (UV2 on the meshes), raise its energy, and add a few baked `OmniLight3D` or `SpotLight3D` lights in accent colours. One `ReflectionProbe` with box projection per room. SSAO on with low intensity and a wide radius. Thin, bright depth fog only for depth; a clear `ProceduralSkyMaterial` sky. On the Mobile renderer: there is no SSAO, so rely on the packs' ambient occlusion maps and the occlusion baked into the lightmaps.

### Post-processing

ACES or AgX tonemap with exposure tuned so whites stay clean. Glow with HDR threshold about 1, moderate intensity, for emissives. Warm highlights and cool shadows through the adjustments colour-correction texture (a warm-to-cool `GradientTexture1D` or a 3D LUT); saturation 1.1. Anti-aliasing by TAA or SMAA, MSAA optional. No grain, outline or vignette. `rendering/scaling_3d/scale` 1. On the Mobile renderer: there is no TAA, so use MSAA 4x with SMAA, and keep emission energy moderate since its 10-bit buffer clips very bright values sooner.

### UI and effects

Theme font from a bold italic condensed sans such as Barlow Condensed Bold Italic or Saira Condensed, white. Panels are semi-transparent dark slanted shapes (`StyleBoxFlat` with skew, a thin white border and corner detail set for chamfer-like corners) with thin white edges; icons are white glyphs in circles or hexagons. Damage numbers are `Label3D` nodes that a `Tween` pops to 130 percent then fades, `#ffd66b` for critical hits. Effects are clean and colour-coded per character: thick stretched quad tracers, shield spheres with a Fresnel-rim spatial shader, chunky spark meshes in `GPUParticles3D` and a short shaped additive flash. Keep lifetimes brief.

## Do / Do not

Do:

- Bevel every hard edge.
- Group detail into a few clusters and leave large clean areas.
- Add emissive accents with bloom.
- Keep roughness regions broad and distinct.

Do not:

- Do not add photographic grime and noise; that reads as `032` or `030`.
- Do not paint heavy detail into albedo with little PBR response; that reads as `023`.
- Do not mute the palette and tint the terminator; that reads as `005`.
- Do not add outlines or bands.

## Nearest styles

- `005` Rim-lit illustrative caricature: `005` uses muted, earthy colours with a warm tint where light turns to shadow; this style is bright and clean with white armour and vivid accent colours.
- `023` Chunky hand-painted fantasy: `023` paints highlights, shadows and wear directly into its textures; this style keeps surfaces clean and lets real light show metal, plastic and cloth.
- `006` Glossy ink-splat pop: `006` covers the scene in wet, glossy splats of two opposing ink colours; this style spreads many accent colours over clean white and grey surfaces.
