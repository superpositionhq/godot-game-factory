# Oily concept-art realism

Reference works: Dishonored.

## References

- *Dishonored* (2012), Arkane Studios, video game. https://en.wikipedia.org/wiki/Dishonored
- *Dishonored 2* (2016), Arkane Studios, video game. https://en.wikipedia.org/wiki/Dishonored_2
- *Deathloop* (2021), Arkane Lyon, video game. https://en.wikipedia.org/wiki/Deathloop
- *BioShock Infinite* (2013), Irrational Games, video game. https://en.wikipedia.org/wiki/BioShock_Infinite

## Visual definition

- **Shape language and proportions:** Realistic scale with caricatured faces and hands (long angular features) and elongated, top-heavy architecture. Industrial Victorian shapes with heavy metal fixtures.
- **Line and outline:** No outline.
- **Shading model:** Smooth physically based shading, but with broad, simplified material response: wide soft highlights and little micro detail.
- **Palette:** `#2e3138` `#6b5a4a` `#8c8f8a` `#a23b2a` `#c9b68c` `#3f4f5c` `#d8d4c8`. Cold greys and slate blue with rusty brown, brass and a deep red accent. Overall low saturation.
- **Lighting:** Overcast daylight through tall windows, or lamps with soft pools; gentle contrast.
- **Texture and surface:** Textures look like oil studies: large soft brush areas, blurred wear, painted rather than photographed detail.
- **Atmosphere and post-processing:** Light fog, soft ambient occlusion, slight desaturation and a cool grade.
- **Camera and framing:** First-person, 28 to 35 mm equivalent, interiors with tall verticals.
- **UI and typography:** Painted icons in round engraved-brass or carved-bone frames, and parchment panels with ink sketches. Headings use a narrow Victorian serif and labels a plain small-caps serif; counters are plain off-white numerals. UI colours are off-white `#d8d4c8` and brass `#c9b68c` on slate `#2e3138`, with deep red `#a23b2a` for alerts.
- **VFX and motion:** Restrained effects: soft smoke, dark ash-like wisps for supernatural powers, brief dull sparks when steel meets steel. Motion is weighty and realistic, with slightly exaggerated, readable poses for first-person hands and enemies.

## Fits

- **Genres:** `stealth`, `fps`, `action-adventure`, `detective-mystery`, `exploration`
- **Moods:** oppressive, grim, conspiratorial
- **Settings:** plague-ridden port city, Victorian industrial districts, aristocratic mansions, whaling docks

## Godot recipe

### Assets

Realistic-scale Victorian and industrial packs: tall interiors, heavy metal fixtures, brass fittings. Elongate architecture by non-uniform vertical scale and top-heavy cornices; give characters longer, more angular faces and hands through blend shapes or bone scale in the `Skeleton3D`. Keep PBR maps but paint them down in a generator script (`Image`): blur albedo and roughness into large soft areas with a wide kernel, soften wear into blurred patches, and halve normal-map strength so micro detail disappears. 1024 to 2048 px, linear filtering with mipmaps.

### Materials

`StandardMaterial3D` throughout, written as `.tres`. Set `normal_scale` to about 0.5, keep `roughness` in a mid range (0.4 to 0.7) so highlights are wide and soft, and leave detail maps off. Brass uses `metallic` 1 with tarnished albedo (`#c9b68c`) and stays a small accent. Skin can use the same material with high roughness; no special subsurface work is needed. No custom lighting, no outline. Because everything is the standard material, shadows, depth and lightmap baking all work as they are.

### Lighting and atmosphere

Overcast daylight through tall windows: a `DirectionalLight3D` at low energy with soft shadows (`light_angular_distance`), plus emissive window panes and bake-only lights at the windows. Bake a `LightmapGI`; indirect light does most of the work and contrast stays gentle. Lamps are warm `OmniLight3D`s with soft pools. One `ReflectionProbe` per room with `box_projection` on. Light grey-blue `Environment` fog. SSAO on with a soft, wide radius. On the Mobile renderer: soften shadows with `shadow_blur` instead of the angular size, and drop SSAO, relying on the lightmap's baked occlusion.

### Post-processing

`ACES` tonemapping, `adjustment_saturation` 0.8, and a cool colour-correction `GradientTexture1D` that gives the slight cool filter and white balance. Mild vignette in a `ColorRect` shader on a `CanvasLayer`. An optional weak Kuwahara full-screen pass (radius 2 px, a `QuadMesh` shader reading `hint_screen_texture`) can soften the remaining photographic detail. No glow beyond a trace on lamps (high HDR threshold), no chromatic aberration. TAA. On the Mobile renderer: SMAA instead of TAA.

### UI and effects

Painted icons in round engraved-brass or carved-bone frames, and parchment panels with ink sketches (`StyleBoxTexture`). Headings from a narrow Victorian serif such as Playfair Display SC or IM Fell English SC; labels in a plain small-caps serif; plain off-white numerals. `#d8d4c8` and `#c9b68c` on `#2e3138`, `#a23b2a` for alerts. Effects are restrained: soft lit smoke from `GPUParticles3D` with a shaded (per-pixel) billboard `StandardMaterial3D`, dark ash-like wisps for powers (alpha-blended, not additive, with noise-driven motion from the `ParticleProcessMaterial` turbulence), and brief dull sparks.

## Do / Do not

Do:

- Keep texture marks large and soft.
- Stretch architecture vertically.
- Hold saturation low with one red or brass accent.
- Use wide soft highlights.

Do not:

- Do not add sharp photographic micro detail; that reads as `029` or `032`.
- Do not quantise light into blocks; that reads as `021`.
- Do not add visible stroke-by-stroke brushwork; that reads as `024`.
- Do not cover everything in polished brass; that reads as `095`.

## Nearest styles

- `021` Brush-block martial painterly: this style has smooth gradients and grey rooms with little colour; `021` shows light in three to five visible steps and floods each room with one strong colour.
- `095` Brass steampunk: here cold grey and slate blue dominate and brass is a small accent; `095` fills the frame with warm brass, copper and furnace glow.
- `029` Survival-horror dark photoreal: scenes here are lit by soft daylight or lamp pools and textures look softly painted; `029` is mostly black, with sharp photographic detail.
