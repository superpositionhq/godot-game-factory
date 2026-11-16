# Brick toy

Reference works: The Lego Movie.

## References

- *The Lego Movie* (2014), Animal Logic (Phil Lord and Christopher Miller), animated film. https://en.wikipedia.org/wiki/The_Lego_Movie
- *Lego Star Wars: The Skywalker Saga* (2022), Traveller's Tales, video game. https://en.wikipedia.org/wiki/Lego_Star_Wars:_The_Skywalker_Saga
- *Lego Builder's Journey* (2019), Light Brick Studio, video game. https://en.wikipedia.org/wiki/Lego_Builder's_Journey
- *The Lego Batman Movie* (2017), Animal Logic (Chris McKay), animated film. https://en.wikipedia.org/wiki/The_Lego_Batman_Movie

## Visual definition

- **Shape language and proportions:** Everything is assembled from a small set of modular bricks on a stud grid (8 mm pitch, 9.6 mm brick height, plates at one third). Curves are stepped. Figures have cylindrical heads and C-shaped hands.
- **Line and outline:** No drawn outline. Thin dark seams appear between bricks.
- **Shading model:** Smooth glossy plastic with sharp highlights and soft reflections.
- **Palette:** `#d01012` `#0055bf` `#f2cd37` `#237841` `#ffffff` `#1b2a34` `#a0a5a9`. A fixed set of solid plastic colours: red, blue, yellow, green, white, black and greys.
- **Lighting:** Bright studio or macro-photography lighting with soft shadows.
- **Texture and surface:** Clean plastic. At macro scale: fine scratches, slight dents, mould marks and a logo bump on each stud.
- **Atmosphere and post-processing:** Macro depth of field; animation stepped like stop motion.
- **Camera and framing:** Macro, low among the bricks, 50 to 100 mm equivalent with a thin focus plane.
- **UI and typography:** Panels are flat plastic plates with studded rims, buttons are round studs or smooth tiles, and icons look like decals printed on a tile. Type is a bold rounded sans like toy-box lettering. Counters are chunky white or yellow numerals beside a stud icon, on red, blue and black panels.
- **VFX and motion:** Everything breaks into loose parts: destroyed objects burst into bouncing bricks and studs, and smoke, fire and water are built from small bricks and transparent pieces. Animation is stepped like stop motion, with stiff-jointed figure poses and objects that assemble brick by brick.

## Fits

- **Genres:** `action-adventure`, `platformer`, `puzzle`, `racing`, `vehicle-combat`
- **Moods:** playful, comic, energetic
- **Settings:** toy city, pirate island, space base, medieval castle

## Godot recipe

### Assets

Everything is assembled from a small library of bricks on a stud grid: 8 mm pitch, 9.6 mm brick height, plates at one third. Generate the brick library in a generator script (Blender background mode exporting `.glb`, or `SurfaceTool` in GDScript): 1x1 to 2x8 bricks, plates, tiles, slopes, round studs with a small raised mark, with bevelled edges so seams read as thin dark lines. Build scenes by placing bricks from a voxel-like layout (a `GridMap` with a `MeshLibrary` of the bricks works), then merge static bricks per chunk into one `ArrayMesh`. Curves are stepped. Figures have cylindrical heads and C-shaped hands and are rigid parts on pivots. Store models are only useful as shape references to voxelise into bricks.

### Materials

`StandardMaterial3D`, written as one `.tres` per plastic colour from the fixed set: metallic 0, roughness 0.1 to 0.2, a very faint scratch normal and detail map for macro realism. Transparent pieces use alpha transparency with low roughness. Turn on clearcoat only if highlights need more punch. No custom shader; loose static bricks of one kind go into a `MultiMeshInstance3D`.

### Lighting and atmosphere

Bright studio light: a `DirectionalLight3D` key with soft shadows (`shadow_blur` raised), a fill light, and a `ReflectionProbe` (update once) of a studio environment with bright emissive soft-box panels so the plastic shows sharp highlights and soft reflections. Short `directional_shadow_max_distance` for dense contact shadows; SSAO on with a small radius, which darkens the seams between bricks. No fog. Backdrop is a plain sweep or a baseplate. On the Mobile renderer: bake a `LightmapGI` with ambient occlusion into the static bricks, or darken the bevel seams in vertex colours, in place of SSAO.

### Post-processing

Strong far and near depth-of-field blur on the camera's `CameraAttributesPractical` for macro scale, bokeh shape circle in the project settings. Tonemap Linear, mild glow on highlights only (HDR threshold about 1), no grain. No motion blur because animation is stepped. MSAA 4x or screen-space AA SMAA.

### UI and effects

Panels are flat plates with studded rims, buttons are round studs or smooth tiles, icons look like printed tile decals; render them from the brick library to PNG sprites through a `SubViewport` and use them as `StyleBoxTexture` 9-slices in the `Theme`. Import a bold rounded sans such as Fredoka Bold or Baloo 2 as the theme default `FontFile`; chunky white or yellow numerals beside a stud icon on red, blue and black. Effects are bricks: destroyed objects release their bricks as `RigidBody3D` pieces that bounce, and smoke, fire and water are small bricks and transparent pieces emitted by `GPUParticles3D` drawing brick meshes. Objects assemble brick by brick. Step figure animation to 12 poses per second (discrete animation tracks or updating poses on a 1/12 s timer).

## Do / Do not

Do:

- Snap every part to the stud grid.
- Put studs on all exposed tops.
- Use a fixed small set of solid colours.
- Use glossy plastic with macro depth of field.

Do not:

- Do not use plain cubes with pixel textures; that reads as `044`.
- Do not use freeform smooth toy shapes; that reads as `057`.
- Do not add painted or weathered textures.
- Do not use matte primaries without studs or gloss; that reads as `098`.

## Nearest styles

- `044` Voxel block world: bricks here are smooth, glossy, single-colour plastic with studs on top; `044` is plain cubes with pixel-art textures and matte faces, each side a flat step lighter or darker.
- `057` Toy-diorama tilt-shift: forms here are assembled from studded bricks in a small set of strong solid plastic colours; `057` has freeform rounded moulded shapes in a wider, softer range of colours.
- `006` Glossy ink-splat pop: plastic here is clean and plain, in a few solid toy colours; `006` covers surfaces in wet, glittering ink splats and neon paint.
