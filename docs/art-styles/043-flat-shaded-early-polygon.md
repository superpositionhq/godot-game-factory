# Flat-shaded early polygon

Reference works: Star Fox; Virtua Fighter.

## References

- *Star Fox* (1993), Nintendo EAD and Argonaut Software, video game. https://en.wikipedia.org/wiki/Star_Fox_(1993_video_game)
- *Virtua Fighter* (1993), Sega AM2, arcade video game. https://en.wikipedia.org/wiki/Virtua_Fighter_(video_game)
- *Another World* (1991), Eric Chahi (Delphine Software), video game. https://en.wikipedia.org/wiki/Another_World_(video_game)
- *Virtua Racing* (1992), Sega AM2, arcade video game. https://en.wikipedia.org/wiki/Virtua_Racing
- *Alone in the Dark* (1992), Infogrames, video game. https://en.wikipedia.org/wiki/Alone_in_the_Dark_(1992_video_game)

## Visual definition

- **Shape language and proportions:** Very low polygon counts (20 to 300 polygons per object) with large flat facets. Shapes are angular abstractions: wedge ships, box buildings, prism figures.
- **Line and outline:** No outline. Facet edges are visible only as colour changes.
- **Shading model:** Flat shading: one colour per polygon, brightness from the facet's angle to the light. No interpolation, no textures.
- **Palette:** `#1c2a6b` `#3e6fd1` `#c8322b` `#e8b83a` `#8f9aa8` `#2e8b57` `#f0f0f0`. Solid saturated colours per object part (blue, red, yellow, grey) on a simple two-colour sky and ground.
- **Lighting:** One directional light; no shadows.
- **Texture and surface:** None.
- **Atmosphere and post-processing:** Low resolution (about 256x224 or 320x200) with hard pixel edges; no filtering.
- **Camera and framing:** Behind-the-ship or side-on views with a 60 degree field of view.
- **UI and typography:** A sparse arcade overlay: thin single-colour bars for shield, boost and health, flat-polygon or wireframe icons, no panel textures. Text is blocky bitmap capitals or a slanted arcade sans, with large digits for lap time, speed and score in white, yellow `#e8b83a` and red `#c8322b`.
- **VFX and motion:** Explosions are bursts of flat-coloured triangles and spinning polygon shards; lasers are solid coloured bars, and a hit flashes the whole object white for a frame. Figures move stiffly on rigid limb segments at 15 to 20 frames per second, while the ground and scenery rush past the camera.

## Fits

- **Genres:** `vehicle-combat`, `racing`, `fighting`, `action-adventure`, `platformer`
- **Moods:** retro, brisk, abstract
- **Settings:** space battle corridor, race circuit, alien planet, fighting arena

## Godot recipe

### Assets

Very low polygon counts with large flat facets: 20 to 300 polygons per object. Build wedge ships, box buildings and prism figures from scratch in a generator script with `SurfaceTool`, or decimate pack models hard in Blender by script and import them as `.glb`. No textures at all. Split vertices so every polygon has its own normal: in a generator script give every triangle its own three vertices with the face normal; in Blender split all edges before export. Colour is one solid saturated value per object part, stored in vertex colour or one material per colour.

### Materials

Write `flat_facet.gdshader` with `render_mode unshaded;` and a uniform light direction copied from the `DirectionalLight3D` by script. Compute brightness once per face: in `vertex()`, turn `NORMAL` into world space with `MODEL_MATRIX`, take the Lambert term against the light direction and pass it in a `flat` varying, so it is constant across the polygon. Output `base_colour * (ambient + ndotl * strength)` as `ALBEDO`, quantised to a small number of levels (8 to 16) to suggest limited colour depth. No textures, no specular, no shadow receiving; turn the mesh's `cast_shadow` off.

### Lighting and atmosphere

One `DirectionalLight3D`, `shadow_enabled` off, used only for its direction. Flat ambient. No fog, or a hard near-black cut-off at the camera's `far` distance. Sky and ground are two flat colours: a sky shader (`shader_type sky;`) that picks one of two colours by the sign of `EYEDIR.y` for a hard horizon, and a single flat ground plane. No SSAO, no ReflectionProbe.

### Post-processing

Render at about 320x200 or 256x224 in a `SubViewport` with nearest upscaling, so polygon edges are hard jagged steps. MSAA and screen-space anti-aliasing off, no filtering, no glow, no dither pass. Tonemap `Linear`. Optionally cap the frame rate or step object animation at 15 to 20 updates per second (set the `AnimationPlayer` callback mode to manual and call `advance()` in fixed steps) while the camera and scenery move at full rate.

### UI and effects

A sparse arcade overlay: thin single-colour bars for shield, boost and health (`ProgressBar` with flat `StyleBoxFlat` fill), flat-polygon or wireframe icons (`Polygon2D`, `Line2D`), no panel textures. Font: blocky bitmap capitals such as Silkscreen imported with antialiasing off, or a slanted arcade face such as Russo One slanted with a `FontVariation` transform, with large digits for lap time, speed and score in white, `#e8b83a` and `#c8322b`. Explosions are mesh particles: `GPUParticles3D` drawing flat-coloured triangles (`PrismMesh`) and spinning shards with the same facet shader. Lasers are solid coloured bars (unshaded `BoxMesh`). A hit swaps the object's colour to white for one frame through an `instance uniform`.

## Do / Do not

Do:

- Use one flat colour per polygon.
- Keep polygon counts very low.
- Render at low resolution without filtering.
- Use a simple two-colour sky and ground.

Do not:

- Do not add textures, even tiny ones; that reads as `036`.
- Do not raise polygon counts and use soft pastel gradients; that reads as `066`.
- Do not draw only edges; that reads as `040`.
- Do not smooth-shade.

## Nearest styles

- `066` Faceted low-poly gradient: `066` is bright and soft, with many small facets, pastel gradients and smooth edges; this style is darker, with a few large facets, solid colours and hard jagged pixels.
- `036` PS1 low-poly wobble: `036` covers its polygons with small pixelated textures that warp and wobble; this style has no textures, only one flat colour per polygon.
- `063` White-and-red faceted minimal: `063` is almost all white with a few red accents; this style puts strong blue, red and yellow on every object.
