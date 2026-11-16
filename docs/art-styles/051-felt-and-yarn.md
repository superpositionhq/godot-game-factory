# Felt and yarn

Reference works: Kirby's Epic Yarn.

## References

- *Kirby's Epic Yarn* (2010), Good-Feel, video game. https://en.wikipedia.org/wiki/Kirby's_Epic_Yarn
- *Yoshi's Woolly World* (2015), Good-Feel, video game. https://en.wikipedia.org/wiki/Yoshi's_Woolly_World
- *Unravel* (2016), Coldwood Interactive, video game. https://en.wikipedia.org/wiki/Unravel_(video_game)
- *LittleBigPlanet* (2008), Media Molecule, video game. https://en.wikipedia.org/wiki/LittleBigPlanet_(2008_video_game)

## Visual definition

- **Shape language and proportions:** Soft, stuffed, slightly lumpy forms. Characters are yarn outlines or plush shapes; scenery is fabric patches, buttons, zips and pompoms.
- **Line and outline:** Visible stitching: dashed thread lines along every seam and patch border, in a darker or contrasting thread.
- **Shading model:** Smooth and very soft; fabric fuzz brightens grazing angles.
- **Palette:** `#f48fb1` `#81d4fa` `#fff59d` `#a5d6a7` `#ce93d8` `#ffab91` `#f5f0e6`. Bright nursery pastels: pink, sky blue, lemon, mint, lilac, on a cream fabric ground.
- **Lighting:** Soft, even craft-table lighting with gentle contact shadows.
- **Texture and surface:** Dense fibre detail: knit loops, felt fuzz, woven cloth grain, twisted yarn strands.
- **Atmosphere and post-processing:** Mild depth of field; nothing else.
- **Camera and framing:** Side-on or slightly raised, close enough to read the fabric weave.
- **UI and typography:** Panels are felt patches with dashed stitch borders, buttons are sewn-on buttons and icons are appliqué shapes or embroidered badges. Type is a soft rounded sans that looks stitched in yarn or cut from felt. Counters are chunky rounded numerals in pink, sky blue and lemon on cream fabric.
- **VFX and motion:** Particles are yarn puffs, loose threads, pompoms and popping buttons, never sparks or smoke. A hit unravels a strand or bursts a seam with a puff of stuffing. Motion is bouncy with squash and stretch, and yarn outlines whip loose and re-form into new shapes.

## Fits

- **Genres:** `platformer`, `puzzle`, `exploration`, `action-adventure`
- **Moods:** cosy, playful, gentle
- **Settings:** craft-table world, patchwork countryside, toy bedroom, knitted seaside

## Godot recipe

### Assets

Soft, stuffed, slightly lumpy forms: plush characters, fabric-patch scenery, buttons, zips, pompoms. Inflate and round store models in Blender background mode, add seams and export them as `.glb`. Generate fabric maps in a generator script with `Image` and `FastNoiseLite`, or take CC0 fabric scans: knit loops, felt, woven cloth and twisted yarn as albedo plus normal, tiled finely. Stitching is a dashed thread texture laid along seams and patch borders through the UV2 set, or thin tube meshes built along edge loops with `SurfaceTool` in a generator script. Yarn outlines are tube meshes swept along curves the same way.

### Materials

Fabric needs a fuzz term that `StandardMaterial3D` lacks. Write `felt.gdshader`, a spatial shader: `fragment()` sets `ALBEDO` and `NORMAL_MAP` from the fabric maps, `ROUGHNESS` near 1 and `METALLIC` 0; a custom `light()` writes a slightly wrapped diffuse, `max((dot(NORMAL, LIGHT) + 0.3) / 1.3, 0.0)` times `ATTENUATION` and `LIGHT_COLOR`, into `DIFFUSE_LIGHT`, then adds a sheen, `pow(1.0 - dot(NORMAL, VIEW), 3.0)` times a pale tint of the base colour times `LIGHT_COLOR` and `ATTENUATION`, so grazing angles brighten; add the same sheen times a small ambient strength to `EMISSION` so it shows in shade. Shadows and depth come with the spatial shader, no extra passes. For close-ups add short shell layers: a chain of a few `next_pass` materials, each pushing vertices a little further along `NORMAL` in `vertex()` and clipping a fibre noise with `ALPHA_SCISSOR_THRESHOLD`. Buttons use an ordinary `StandardMaterial3D` plastic.

### Lighting and atmosphere

Soft, even craft-table light: a broad `DirectionalLight3D` with very soft shadows (a large `light_angular_distance`) at reduced `shadow_opacity`, and strong flat ambient in warm white (ambient source Color in the `Environment`). Short `directional_shadow_max_distance`. SSAO on, gentle, small radius. No fog. Background is cream fabric (`#f5f0e6`) with its own weave, a backdrop mesh in front of a background colour of the same cream. On the Mobile renderer: soften shadows with `shadow_blur` instead of angular distance, and bake a gentle contact occlusion into the fabric textures or vertex colours in place of SSAO.

### Post-processing

Mild depth-of-field blur on the camera's `CameraAttributesPractical` with the bokeh shape set to circle in the project settings, and nothing else of note: tonemap Linear, no glow, no grain, no vignette. Screen-space AA SMAA; keep `rendering/scaling_3d/scale` at 1 so fibre detail holds.

### UI and effects

Panels are felt patches with dashed stitch borders, buttons are sewn-on buttons, icons are appliqué shapes or embroidered badges, all as PNG sprites rendered from the 3D materials through a `SubViewport` and used in the `Theme` as `StyleBoxTexture` 9-slices and `TextureRect` icons. Import a soft rounded sans such as Baloo 2 or Fredoka as a `FontFile` and make it the theme default font; put a dashed-stitch outline sprite behind headings. Chunky numerals in pink, sky blue and lemon on cream. Particles are mesh puffs of yarn, loose threads (short `GPUParticles3D` trails with the yarn texture), pompoms and popping buttons; never sparks or smoke. A hit unravels a strand or bursts a seam with white stuffing tufts.

## Do / Do not

Do:

- Put a stitch line on every seam.
- Use sheen for fabric fuzz.
- Give every surface a knit, felt or weave pattern.
- Inflate forms like stuffed cushions.

Do not:

- Do not leave surfaces smooth; that reads as `048` or `057`.
- Do not flatten the scene into a long band of stitched figures on linen; that reads as `056`.
- Do not use flat paper sheets; that reads as `050`.
- Do not use hard plastic gloss.

## Nearest styles

- `056` Embroidered tapestry: this style builds plump, softly shaded stuffed forms in bright nursery pastels; `056` is a flat stitched picture on bare linen in muted plant-dyed wools, with no shading or depth.
- `048` Claymation: every surface here shows knit loops, felt fuzz and dashed stitch lines; `048` is smooth matte clay with thumb marks and no stitching.
- `050` Papercraft: forms here are inflated cushions covered in thick fuzzy fibre; `050` is built from flat folded paper sheets with crisp creases and only a faint paper grain.
