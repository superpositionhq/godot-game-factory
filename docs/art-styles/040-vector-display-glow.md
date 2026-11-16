# Vector display glow

Reference works: Asteroids; Battlezone.

## References

- *Asteroids* (1979), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Asteroids_(video_game)
- *Battlezone* (1980), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Battlezone_(1980_video_game)
- *Tempest* (1981), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Tempest_(video_game)
- *Star Wars* (1983), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Star_Wars_(1983_video_game)
- *Vectrex* (1982), Smith Engineering, vector display game console. https://en.wikipedia.org/wiki/Vectrex

## Visual definition

- **Shape language and proportions:** Wireframe only. Objects are minimal edge sets: a tank is about 30 lines, a mountain range one polyline. No filled surfaces.
- **Line and outline:** Bright glowing lines of constant width on black. Line ends and corners are brighter dots where the beam dwells.
- **Shading model:** None. Brightness varies only per line (beam intensity).
- **Palette:** `#000000` `#39ff14` `#ffffff` `#00e5ff` `#ff2a2a` `#ffe600`. One phosphor colour (green or white) on black, or a few pure colours for colour vector monitors.
- **Lighting:** None.
- **Texture and surface:** None.
- **Atmosphere and post-processing:** Phosphor glow around lines, short persistence trails on motion, slight flicker.
- **Camera and framing:** First-person or top-down; perspective lines converge to a flat horizon.
- **UI and typography:** The UI is drawn with the same glowing strokes as the world: no panels or fills, only thin line brackets, a line crosshair and wireframe icons such as small ship outlines for lives. Type is a monospaced stroke face in capitals, built from straight segments. Scores are large segment numerals at the top in phosphor green `#39ff14` or white, with red `#ff2a2a` for warnings on colour displays.
- **VFX and motion:** A destroyed object breaks into its separate line segments, which fly apart, spin and fade; shots are bright dots and short dashes, and a big hit flashes the whole screen for a moment. Motion is smooth and rigid: objects drift and rotate with inertia and never deform.

## Fits

- **Genres:** `top-down-shooter`, `vehicle-combat`, `fps`, `racing`, `simulation`
- **Moods:** stark, tense, hypnotic
- **Settings:** deep space, wireframe battlefield, geometric tunnel, trench run

## Godot recipe

### Assets

Build everything from scratch as line sets; store models do not fit. A generator script creates each object as an `ArrayMesh` with the lines primitive (`Mesh.PRIMITIVE_LINES`), or as quads generated along edges with `SurfaceTool` for controllable width: a tank is about 30 segments, a mountain range one polyline. Author edge lists by hand in code or extract feature edges (boundary and sharp edges above an angle) from simple models with `MeshDataTool`. Store per-vertex brightness in vertex colour. No textures.

### Materials

Write `vector_beam.gdshader`, a spatial shader with `unshaded`, `blend_add`, `cull_disabled`, `depth_draw_never` and `depth_test_disabled`, so objects are see-through wireframes with no hidden-line removal. For constant-width lines, expand each segment into a camera-facing quad in `vertex()` using the neighbouring endpoint stored in `UV2`; `fragment()` shapes a soft-edged beam profile across the quad. Output HDR colour in `ALBEDO`: phosphor green `#39ff14` or white at intensity 2 to 3, with brighter round dots at segment ends and corners (a second small quad per vertex) where the beam dwells. One material, meshes cast no shadows.

### Lighting and atmosphere

None. No lights, no shadows, no fog, no sky: the environment background is a pure black colour. SSAO off, and nothing reads the depth texture.

### Post-processing

Glow is the phosphor glow: HDR threshold about 0.9, intensity 1.5 to 3, spread over the middle and upper levels; the beam colour itself tints it. A `CompositorEffect` on the camera's `Compositor` keeps a history texture across frames: each frame it outputs `max(current, history * decay)` with decay around 0.8, giving short persistence trails on motion. A small random brightness flicker (2 to 3 percent) is applied in the same pass. A neutral tonemap (AgX). MSAA 4x or 8x helps thin lines; `rendering/scaling_3d/scale` 1. On the Mobile renderer: the colour buffer holds less HDR range, so keep beam intensity near 1.5 and raise glow intensity instead so the cores do not clip.

### UI and effects

UI uses the same strokes: thin `Line2D` brackets, a line crosshair, wireframe ship icons for lives, no panels or fills. Use a single-stroke monospaced face; a segment-style or stroke-style font such as Major Mono Display works as the theme font, or build numerals from `Line2D` strokes for an exact match. Scores are large at the top; `#ff2a2a` for warnings on colour displays. A destroyed object splits into its segments, each a separate mesh given a velocity and spin by script and faded over a second with a `Tween`. Shots are bright dots and short dashes; big hits flash the screen briefly.

## Do / Do not

Do:

- Draw edges only, on pure black.
- Add glow and short persistence trails.
- Brighten vertices where lines meet.
- Hide back edges with a black occluder mesh.

Do not:

- Do not fill surfaces with dark colour and emissive trim; that reads as `088`.
- Do not add a gradient sunset and filled mountains; that reads as `090`.
- Do not draw white lines on blue with dimension marks; that reads as `062`.
- Do not use pixel-stepped raster lines at low resolution.

## Nearest styles

- `088` Neon grid cyberspace: only lines exist here, so objects are see-through wireframes; `088` has solid dark glossy surfaces that carry light strips and reflect their glow.
- `062` Blueprint technical drawing: this style is glowing lines on pure black; `062` is crisp white lines without glow on a blue paper ground, with dimension marks.
- `090` Synthwave sunset grid: this style uses one phosphor colour or a few pure line colours and fills nothing; `090` has a gradient sky, a large striped sun and magenta and cyan fills.
