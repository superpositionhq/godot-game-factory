# Rain-soaked tech-noir

Reference works: Blade Runner.

## References

- *Blade Runner* (1982), Ridley Scott, live-action film. https://en.wikipedia.org/wiki/Blade_Runner
- *Blade Runner 2049* (2017), Denis Villeneuve, live-action film. https://en.wikipedia.org/wiki/Blade_Runner_2049
- *Cyberpunk 2077* (2020), CD Projekt Red, video game. https://en.wikipedia.org/wiki/Cyberpunk_2077
- *Deus Ex: Human Revolution* (2011), Eidos-Montreal, video game. https://en.wikipedia.org/wiki/Deus_Ex:_Human_Revolution
- *The Fifth Element* (1997), Luc Besson, live-action film. https://en.wikipedia.org/wiki/The_Fifth_Element

## Visual definition

- **Shape language and proportions:** Dense vertical city at street level: massive towers with added pipes and ducts, stacked signs, market stalls, overhead cables, flying vehicles. Layers of old and new construction.
- **Line and outline:** No outline.
- **Shading model:** Physically based and smooth; wet surfaces with strong reflections.
- **Palette:** `#0b0e14` `#1c2a3a` `#ff3b6b` `#18c8e8` `#f2a23a` `#6b4fd8` `#3a3a3a` `#d8e6f0`. Dark blue-black night with neon magenta, cyan, amber and violet light; smog glows in the colour of nearby signs.
- **Lighting:** Night and rain. Light comes from neon signs, video billboards, shop fronts and searchlights sweeping through haze.
- **Texture and surface:** Grimy concrete and metal, wet asphalt with puddles, steam, rain streaks, dense signage with glyphs.
- **Atmosphere and post-processing:** Volumetric haze, bloom, anamorphic horizontal flare streaks, rain, film grain, slight chromatic fringe.
- **Camera and framing:** Street-level or mid-air canyon views with 28 to 40 mm equivalent; shallow depth for close shots.
- **UI and typography:** Overlays are thin-line holographic displays in cyan and amber with slight flicker and scan noise; panels are dark translucent glass, and icons are simple line glyphs like street signage. Text is a condensed technical sans in capitals, with a monospaced terminal face for readouts. Numbers are monospaced, amber for normal values and magenta-red for damage.
- **VFX and motion:** Rain streaks, puddle splashes, steam from vents, sparks from broken signs and muzzle flashes that light the haze. Hits throw sparks, glass and wet spray. Motion is weighty and realistic, with slow camera drift.

## Fits

- **Genres:** `detective-mystery`, `third-person-shooter`, `fps`, `stealth`, `rpg`, `action-adventure`
- **Moods:** brooding, melancholic, tense
- **Settings:** rainy megacity street, neon night market, corporate tower, rooftop landing pad

## Godot recipe

### Assets

Dense street-level sci-fi city packs: towers with added pipes and ducts, stacked signs, market stalls, overhead cables, flying vehicles. Keep full PBR maps and add grime with `Decal` nodes. Layer old and new construction by kitbashing. Signs are emissive panels with glyph textures made in a generator script; video billboards use animated emission (a flipbook stepped by `TIME` in a shader). Wet everything: a generator script lowers roughness and darkens albedo on the materials, and adds puddle masks to streets.

### Materials

`StandardMaterial3D` throughout. Asphalt and concrete: a custom wet shader, `wet_surface.gdshader`, blends puddles by a world-space mask and height, sets `ROUGHNESS` to 0.05 in puddles, and animates ripple normals into `NORMAL_MAP` from a flipbook for rain. Signs use emission with HDR colours (energy above 1) in magenta, cyan, amber and violet. Glass uses `StandardMaterial3D` with alpha transparency. `Decal` nodes for grime and posters. No outline and no cel shading: this is filmed-looking realism.

### Lighting and atmosphere

Night and rain. No sun; a very dim blue ambient. Light comes from many `OmniLight3D` and `SpotLight3D` nodes at signs, shop fronts and billboards, plus sweeping searchlight spots with projector textures. Reflections make the image: box-projected `ReflectionProbe` nodes placed densely along streets and updated with the emissive signs on, plus SSR on wet ground. Haze: exponential fog in dark blue-grey, plus local fog-card sprites tinted by the nearest sign colour so smog glows; searchlight beams are additive cone meshes. SSAO on. SDFGI picks up the emissive signs, or bake `LightmapGI` with emission. On the Mobile renderer: no SSR, SSAO or SDFGI, so lean on the probes (at most 8 per mesh), the fog cards and a baked `LightmapGI`, and split meshes so each is lit by at most 8 omni and 8 spot lights.

### Post-processing

Glow with a lowish HDR threshold (0.9) and a wide spread (upper glow levels on). Anamorphic streaks: a full-screen `ColorRect` on a `CanvasLayer` with a `canvas_item` shader that blurs the brightest parts of `hint_screen_texture` horizontally only and adds them back, plus stretched additive quads on key lights. Medium grain, slight chromatic aberration and a 0.3 vignette in the same shader. `ACES` tonemap. Depth-of-field blur optional (`CameraAttributesPractical`). TAA. On the Mobile renderer: SMAA instead of TAA.

### UI and effects

Thin-line holographic overlays in cyan and amber with slight flicker and scan noise (a scrolling noise in a `canvas_item` shader on the panels); dark translucent glass panels (`StyleBoxFlat` with a translucent fill); line-glyph icons. The `Theme` font is a condensed technical sans in capitals such as Rajdhani or Saira Condensed; readouts and numbers in a monospaced face such as Share Tech Mono; amber for normal values, magenta-red for damage. Effects: velocity-stretched rain streaks from `GPUParticles3D` with collision splashes, puddle ripple rings, vent steam lit by sign colours (particle materials shaded per pixel, not unshaded), sparks from broken signs, muzzle flashes with a brief `OmniLight3D`.

## Do / Do not

Do:

- Make it night, wet and hazy.
- Light the scene from signs and billboards.
- Reflect neon in wet ground.
- Stack signage and pipes on large tower masses.

Do not:

- Do not draw cel bands and ink lines; that reads as `017`.
- Do not reduce to emissive lines on black; that reads as `088`.
- Do not use a clean gradient sunset and grid; that reads as `090`.
- Do not use an empty dark interior with one flashlight; that reads as `029`.

## Nearest styles

- `017` Neon megacity 1980s anime: this style has no drawn line and smooth realistic shading with wet reflections; `017` has ink outlines and flat cel tone bands.
- `029` Survival-horror dark photoreal: this style is full of coloured neon light reflected in wet streets; `029` is nearly colourless, an empty dark interior lit by one flashlight.
- `093` Bioluminescent alien jungle: this style has hard urban surfaces of concrete, metal and signs, with neon dulled by smog; `093` has organic plants and creatures that glow in vivid colour.
