# Biomechanical monochrome

Reference works: H. R. Giger; Scorn.

## References

- *Necronom IV* (1976), H. R. Giger, airbrush painting. https://en.wikipedia.org/wiki/H._R._Giger
- *Alien* (1979), Ridley Scott (creature and derelict design by H. R. Giger), live-action film. https://en.wikipedia.org/wiki/Alien_(film)
- *Scorn* (2022), Ebb Software, video game. https://en.wikipedia.org/wiki/Scorn_(video_game)
- *Dark Seed* (1992), Cyberdreams, video game. https://en.wikipedia.org/wiki/Dark_Seed_(video_game)

## Visual definition

- **Shape language and proportions:** Fusion of anatomy and machinery: ribbed tubes, vertebra-like columns, pelvis-shaped arches, pistons that look like tendons, cable bundles like muscle fibre. Strong bilateral symmetry and repetition of segments.
- **Line and outline:** No outline.
- **Shading model:** Smooth, airbrushed gradients with a wet, semi-gloss sheen; deep occlusion in every recess.
- **Palette:** `#0c0c0d` `#2b2a28` `#5b5852` `#8c877c` `#b9b2a2` `#3f3a36`. Monochrome: black, cold grey, bone and gunmetal, with at most a faint sepia or blue-green cast.
- **Lighting:** Dim, soft, directionless light with a few rim highlights; forms emerge from darkness.
- **Texture and surface:** Very dense relief: closely spaced ribs, grooves, pores, rivet-like nodes and interwoven tubes covering all surfaces.
- **Atmosphere and post-processing:** Deep ambient occlusion, slight haze, fine grain, vignette.
- **Camera and framing:** Symmetric frontal views of corridors and portals, or close views of surface detail.
- **UI and typography:** Frames look grown, not built: ribbed bone-grey borders, vertebra dividers and socket-shaped slots, with icons as embossed relief glyphs. Type is a thin, tall, condensed engraved capital face in bone `#b9b2a2`. Counters are small and sparse in the same bone tone, with no colour; health can be an organ-like gauge.
- **VFX and motion:** Slow drips, viscous strands, pale mist and puffs of spore-like dust; hits land as dull wet impacts with dark grey spray, never bright flashes. Motion is slow and heavy: tubes pulse, pistons flex like tendons, and creatures unfold deliberately.

## Fits

- **Genres:** `survival-horror`, `exploration`, `puzzle`, `fps`, `soulslike`
- **Moods:** oppressive, grotesque, unsettling
- **Settings:** derelict alien ship, living machine temple, bone-walled labyrinth

## Godot recipe

### Assets

Forms that fuse anatomy and machinery: ribbed tubes, vertebra-like columns, pelvis-shaped arches, tendon-like pistons, cable bundles like muscle fibre. Few packs fit; generate much of it by script in Blender background mode and import it as `.glb`: sweep ribbed profiles along curves, array vertebra segments, mirror everything for strict bilateral symmetry, and repeat segments in rows. Sculpt-like detail comes from height maps made in a generator script (closely spaced ribs, grooves, pores, nodes, interwoven tubes) baked to normal and occlusion maps at 2048 to 4096 px. Remove all colour from any pack asset used.

### Materials

`StandardMaterial3D`: albedo in the bone-to-gunmetal range (`#b9b2a2` down to `#2b2a28`), roughness 0.3 to 0.45 for a wet semi-gloss sheen, low metallic, strong normal maps, and ambient occlusion maps at full strength. A written spatial shader can deepen recesses by multiplying albedo and raising roughness by a cavity mask, and add an airbrushed look in its own `light()`: Lambert diffuse plus two specular lobes, one tight and one broad. Pulsing tubes push vertices along `NORMAL` in `vertex()` with a travelling sine of `TIME`. No emission and no colour.

### Lighting and atmosphere

Dim, soft and nearly directionless: low grey ambient from a baked `LightmapGI`, a few weak large-range `OmniLight3D` lights, and two or three narrow `SpotLight3D` rim lights with no visible source to pick out ribs. Soft shadows (a large `light_size`). Deep occlusion is essential: SSAO at high intensity with a medium radius, plus baked occlusion maps. A `ReflectionProbe` with a dim, low-contrast environment for the wet sheen. Thin grey depth fog so forms emerge from darkness. On the Mobile renderer: there is no SSAO, so bake the deep occlusion into the lightmap and occlusion maps and strengthen the cavity mask in the shader.

### Post-processing

Monochrome guard: adjustment saturation 0.1, with at most a faint sepia or blue-green tint from a colour-correction `GradientTexture1D`. `ACES` tonemapping, low exposure. Fine film grain and a 0.45 vignette from a `canvas_item` shader on a `ColorRect`. No glow: nothing glows. Slight depth-of-field blur optional. TAA. On the Mobile renderer: TAA is missing, so use MSAA 4x.

### UI and effects

Frames look grown: ribbed bone-grey borders, vertebra dividers and socket-shaped slots, rendered from the 3D kit to textures in a small capture scene run once as a rendered play (a `SubViewport` saved as PNG; a generator script runs headless and draws nothing) and used as `StyleBoxTexture` 9-slices; icons are embossed relief glyphs. Font imported from a thin, tall, condensed capital face such as Big Shoulders Display Light or Six Caps, in `#b9b2a2`. Counters are small and sparse with no colour; health can be an organ-like `TextureProgressBar` that pulses. Effects: slow drips and viscous strands (a sagging ribbon mesh rebuilt each frame), pale mist, spore-like dust puffs, and dull wet impacts with dark grey spray using shaded particles. No bright flashes. Motion is slow and heavy.

## Do / Do not

Do:

- Merge bone and machine shapes.
- Cover every surface with ribs and tube relief.
- Keep the image monochrome.
- Use bilateral symmetry and repeated segments.

Do not:

- Do not use flat manufactured panels, labels and signal lights; that reads as `092`.
- Do not use gothic masonry and lantern colour; that reads as `031`.
- Do not use rubble and military hardware in daylight; that reads as `030`.
- Do not add colour accents.

## Nearest styles

- `092` Industrial used-future: this style has no colour, and every surface is covered in ribs and interwoven tubes; `092` has flat painted panels, stencil labels and amber, red and teal lights.
- `031` Gothic dark-fantasy realism: this style stays in one cold grey range and is built from bone-and-machine forms; `031` is stone masonry warmed by lantern and candle light.
- `030` Gritty desaturated war realism: this style is dim and enclosed, with smooth, wet organic relief; `030` is daylight rubble with chipped, scratched hard surfaces and military hardware.
