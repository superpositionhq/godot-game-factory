# Toy-diorama tilt-shift

Reference works: Link's Awakening (2019).

## References

- *The Legend of Zelda: Link's Awakening* (2019), Grezzo, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Link's_Awakening_(2019_video_game)
- *Captain Toad: Treasure Tracker* (2014), Nintendo EAD Tokyo, video game. https://en.wikipedia.org/wiki/Captain_Toad:_Treasure_Tracker
- *Animal Crossing: New Horizons* (2020), Nintendo EPD, video game. https://en.wikipedia.org/wiki/Animal_Crossing:_New_Horizons
- *The Legend of Zelda: Echoes of Wisdom* (2024), Nintendo EPD and Grezzo, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Echoes_of_Wisdom

## Visual definition

- **Shape language and proportions:** Small, rounded, toy-like forms: stubby characters with bead eyes, trees as glossy lumps, houses like moulded play-set pieces. The world looks like a tabletop diorama.
- **Line and outline:** No outline.
- **Shading model:** Smooth, glossy plastic or glazed-toy shading with clear soft highlights.
- **Palette:** `#7ed957` `#4fc3f7` `#ffd54f` `#ff8a65` `#f5f5f5` `#8d6e63` `#ba68c8`. Bright, clean primaries and pastels: grass green, sky blue, yellow, coral.
- **Lighting:** Bright, soft overhead light with gentle shadows.
- **Texture and surface:** Almost none; smooth moulded surfaces with simple painted colour areas. Grass and water are simplified glossy shapes.
- **Atmosphere and post-processing:** Strong tilt-shift blur at the top and bottom of the frame to give a miniature scale; light bloom.
- **Camera and framing:** High three-quarter view (50 to 60 degrees down) with a long lens.
- **UI and typography:** Panels are rounded glossy plaques with soft drop shadows, and icons are small chunky toy models of the items they stand for. Type is a friendly rounded sans in white or cream. Counters are bold rounded numerals that pop in with a small bounce, with grass green, sky blue, yellow and coral accents.
- **VFX and motion:** Particles are simple chunky shapes: puffy white smoke balls, star bursts, glossy leaf and water blobs. A hit gives a quick squash, a white flash and a pop. Motion is bouncy with squash and stretch, short waddling steps and a toy-like wobble.

## Fits

- **Genres:** `action-adventure`, `puzzle`, `simulation`, `exploration`, `tower-defense`, `survival-craft`
- **Moods:** cheerful, cosy, whimsical
- **Settings:** island village, tabletop dungeon, toy town, seaside meadow

## Godot recipe

### Assets

Small rounded toy-like forms: stubby characters with bead eyes, trees as glossy lumps, houses like moulded play-set pieces. Cute low-poly and cartoon packs fit after smoothing: subdivide and round them in Blender background mode, bevel every edge generously, recalculate smooth normals and export `.glb`. Remove textures and assign simple painted colour areas per material slot. Grass is a smooth green surface, not blades; water is a glossy blue shape. Lay the world out as a compact tabletop diorama with a visible edge.

### Materials

`StandardMaterial3D`, metallic 0, roughness 0.25 to 0.4 for a moulded plastic or glazed finish with clear soft highlights, no normal maps. Water is opaque or slightly alpha-transparent at roughness 0.1. Bead eyes are black with roughness 0.05. Unlike a brick look there are no seams or studs, and unlike clay there are no surface marks: surfaces are perfectly clean. No custom shader needed.

### Lighting and atmosphere

Bright, soft overhead light: a `DirectionalLight3D` at a steep angle with soft shadows (a moderate `light_angular_distance`) at moderate `shadow_opacity`, bright sky ambient. A `ReflectionProbe` (update once) of a soft bright environment for the highlights. `directional_shadow_max_distance` matched to the diorama size; four splits are not needed, use Orthogonal or PSSM 2 Splits. SSAO on, gentle. No fog; a plain pastel background colour. On the Mobile renderer: soften shadows with `shadow_blur` instead of angular distance, and bake a gentle `LightmapGI` occlusion into the static diorama in place of SSAO.

### Post-processing

The tilt-shift is a custom effect, because depth-of-field blur follows depth, not screen position. Add a `ColorRect` covering the screen on a `CanvasLayer` with a `canvas_item` shader that reads `hint_screen_texture` and blurs the top and bottom bands of the frame: blur radius grows with vertical distance from a focus band centred on the player's screen height, using a disc of taps (or the screen texture's mipmaps with `filter_linear_mipmap`). It draws after tonemapping and glow. Combine with a raised camera on a long lens (small `fov`). Light glow (HDR threshold 1, low intensity), saturation adjustment 1.1, tonemap Linear. Screen-space AA SMAA.

### UI and effects

Panels are rounded glossy plaques with soft drop shadows (`StyleBoxFlat` with corner radius and shadow); icons are small chunky toy models rendered to PNG sprites through a `SubViewport` in a small capture scene run once as a rendered play (a generator script runs headless and draws nothing). Import a friendly rounded sans such as Nunito ExtraBold or Fredoka as the theme default `FontFile`, white or cream; bold numerals pop in with a small bounce `Tween`. Particles are simple chunky meshes drawn by `GPUParticles3D`: puffy white smoke balls, star bursts, glossy leaf and water blobs with the same material. A hit gives a quick squash, a white flash and a pop. Add a toy-like wobble with a damped spring on scale in script.

## Do / Do not

Do:

- Round every form like a moulded toy.
- Blur the top and bottom of the frame.
- Use glossy clean materials.
- View from a high angle with a long lens.

Do not:

- Do not add fingerprints and matte clay; that reads as `048`.
- Do not build from studded bricks; that reads as `052`.
- Do not use low-poly blurry-textured forms without gloss; that reads as `037`.
- Do not use pixel sprites; that reads as `047`.

## Nearest styles

- `048` Claymation: surfaces here are smooth, glossy and clean, in many bright colours; `048` is matte clay with fingerprints and tool marks, in fewer colours.
- `037` N64 filtered fog: scenes here are bright, with smooth rounded glossy forms and blur only at the top and bottom of the frame; `037` has angular low-polygon models, blurry matte textures and distance fog.
- `052` Brick toy: this style has freeform rounded shapes in a wide range of soft bright colours; `052` assembles everything from studded bricks in a few strong solid plastic colours.
