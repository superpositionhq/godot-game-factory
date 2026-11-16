# Painterly open-air cel

Reference works: The Legend of Zelda: Breath of the Wild.

## References

- *The Legend of Zelda: Breath of the Wild* (2017), Nintendo EPD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Breath_of_the_Wild
- *The Legend of Zelda: Tears of the Kingdom* (2023), Nintendo EPD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Tears_of_the_Kingdom
- *The Legend of Zelda: Skyward Sword* (2011), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Skyward_Sword
- *Immortals Fenyx Rising* (2020), Ubisoft Quebec, video game. https://en.wikipedia.org/wiki/Immortals_Fenyx_Rising

## Visual definition

- **Shape language and proportions:** Natural proportions, simplified. Rocks, trees and ruins are soft, rounded masses with few small details; silhouettes read clearly at long distance.
- **Line and outline:** No drawn outline on scenery. Characters and small props get a thin, soft dark rim (1 to 2 px) and a bright fresnel rim on the lit side.
- **Shading model:** Two bands (lit and shadow) with a narrow soft transition, plus an optional specular highlight band on metal and hair.
- **Palette:** `#8fc46a` `#4f8a5b` `#bfe3f2` `#f3e7b8` `#c98d5a` `#6f7fa8` `#e06a4a`. Fresh greens, sky blues and warm stone; shadows are blue-tinted, never grey or black.
- **Lighting:** Bright outdoor sun with strong sky fill. Shadows are soft-edged and light in value.
- **Texture and surface:** Low-frequency painted gradients and broad brush patches. Grass and foliage are flat colour cards with a vertical gradient.
- **Atmosphere and post-processing:** Strong aerial perspective that fades distance to pale blue, mild bloom on sky and highlights, light volumetric haze.
- **Camera and framing:** Wide 28 to 35 mm equivalent, third-person height, horizon in the upper third to show terrain depth.
- **UI and typography:** Thin, quiet UI: small white icons and translucent dark panels with a fine pale border and soft corner ornaments. Text is a light humanist sans in white or pale cream (`#f3e7b8`). Counters are small plain numerals, with red-orange (`#e06a4a`) only for hearts and danger.
- **VFX and motion:** Effects are soft-edged stylised shapes: curled smoke puffs, pale blue glows, drifting spores and grass that bends in the wind. Hits give a brief white starburst and a short hit-pause; animation is fluid and natural with light anticipation.

## Fits

- **Genres:** `exploration`, `action-adventure`, `survival-craft`, `rpg`, `puzzle`
- **Moods:** serene, adventurous, wistful
- **Settings:** grassy highlands, overgrown ruins, mountain wilderness, sky islands

## Godot recipe

### Assets

Choose nature and ruin packs with large rounded masses: boulders, broad-crowned trees, simple stone architecture. Restyle by removing normal maps and roughness detail, then in a generator script blur each albedo heavily with `Image` and remap it to the palette so only low-frequency painted patches remain; 512 to 1024 px, linear filtering with mipmaps. Replace grass and foliage with flat cards built by `SurfaceTool` that carry a vertical gradient in vertex colour, scattered with `MultiMeshInstance3D`. Rolling terrain is best generated as a mesh with soft slopes from a smooth heightmap instead of using a detailed terrain pack.

### Materials

Write `open_air_cel.gdshader`. In `light()`, shade with `smoothstep(0.45, 0.55, dot(NORMAL, LIGHT) * ATTENUATION)`: two bands with a narrow soft transition. The shadow band mixes toward blue (`#6f7fa8`) and never below mid value. Add a Fresnel rim on the lit side and, in a variant that defines `SPECULAR_BAND` before including a shared `.gdshaderinc`, one stepped Blinn-Phong highlight in `SPECULAR_LIGHT` for metal and hair. Sky fill comes from the environment's ambient light, which Godot adds on top of `light()`, and fog is applied without extra code. Characters and small props get a thin inverted-hull rim in `next_pass` (`unshaded`, `cull_front`) in a soft dark colour at 1 to 2 px; scenery materials leave it off. A foliage variant adds vertex wind in `vertex()`, `cull_disabled` and `ALPHA_SCISSOR_THRESHOLD`.

### Lighting and atmosphere

One `DirectionalLight3D` sun with soft shadows (the directional soft shadow filter quality project setting above Hard, `shadow_blur` raised, PSSM 4 Splits, `directional_shadow_max_distance` 150 m) and a strong sky ambient: a `ProceduralSkyMaterial` with a blue sky top, pale horizon and warm ground, ambient source Sky. Exponential fog in pale blue (`#bfe3f2`) carries the aerial perspective, with low sky affect so the sky keeps its colour. Bake nothing; SSAO off, since it would grey the blue shadows.

### Post-processing

`Environment`: tonemap Filmic, glow with a high HDR threshold and low intensity so only sky and highlights glow, `adjustment_saturation` about 1.1 for a small saturation lift. No outline pass, no grain. Fake haze shafts with a few large unshaded additive quads (`blend_add`) near the sun direction. `rendering/scaling_3d/scale` 1, MSAA 3D 4x.

### UI and effects

Import a light humanist sans such as Nunito Sans Light as the `Theme` default font, in white or `#f3e7b8`. Panels are `StyleBoxFlat` with a translucent dark fill, a 1 px pale border and small corner ornaments as `TextureRect`s; icons are small white glyphs. Keep `#e06a4a` for hearts and danger. Particles are soft-edged alpha-blended billboards: curled smoke puffs, slow pale blue motes, a brief white starburst on hit. Bend grass around the player with a global shader uniform (`global uniform vec3`, declared in the project's shader globals) set each frame with `RenderingServer.global_shader_parameter_set`.

## Do / Do not

Do:

- Tint shadows blue and keep them light.
- Fade distant terrain strongly toward sky colour.
- Use a bright fresnel rim on characters.
- Keep textures as large soft patches.

Do not:

- Do not add heavy black outlines or hatching; that reads as `001`.
- Do not remove all texture and gradient; flat fills read as `003`.
- Do not use full PBR roughness and metal response; that reads as `013`.
- Do not use dense painted backgrounds with brown line art; that reads as `014`.

## Nearest styles

- `003` Flat-shape ocean toon: this style has soft painted gradients, distance haze and natural proportions; `003` uses single flat colours with a knife-sharp shadow edge, clear air and strong caricature.
- `018` Soft open-world anime cel: this style draws no outline on scenery and only a faint rim on characters; `018` draws a thin coloured outline around every character and prop and adds fine ornamental trim on costumes.
- `014` Hand-painted pastoral anime: this style keeps scenery as broad soft colour patches; `014` has densely painted backgrounds with visible brush dabs and a brown line on characters.
