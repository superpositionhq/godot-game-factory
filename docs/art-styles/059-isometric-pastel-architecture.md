# Isometric pastel impossible architecture

Reference works: Monument Valley.

## References

- *Monument Valley* (2014), Ustwo Games, video game. https://en.wikipedia.org/wiki/Monument_Valley_(video_game)
- *Monument Valley 2* (2017), Ustwo Games, video game. https://en.wikipedia.org/wiki/Monument_Valley_2
- *Relativity* (1953), M. C. Escher, lithograph. https://en.wikipedia.org/wiki/Relativity_(M._C._Escher)
- *Waterfall* (1961), M. C. Escher, lithograph. https://en.wikipedia.org/wiki/Waterfall_(M._C._Escher)
- *Echochrome* (2008), Japan Studio, video game. https://en.wikipedia.org/wiki/Echochrome

## Visual definition

- **Shape language and proportions:** Small architectural monuments made of cubes, stairs, arches, domes and towers on a strict grid, floating in empty space. Structures form impossible loops that only connect from the fixed view.
- **Line and outline:** No outline.
- **Shading model:** Exactly three tones per colour: top faces lightest, left faces mid, right faces darkest. No gradients on faces, no cast shadows.
- **Palette:** `#f6c6b4` `#e58f8a` `#7fc7c2` `#3d7f8f` `#f7efd9` `#b89ad6` `#2f3e56`. Soft pastels with one deeper contrast colour; each level uses three or four hues.
- **Lighting:** Implied fixed light; tones are assigned by face direction, not computed with falloff.
- **Texture and surface:** None. Faces are flat colour; small details are simple geometric cut-outs (windows, doors, crenellations).
- **Atmosphere and post-processing:** Smooth gradient background; optional soft glow on a few elements.
- **Camera and framing:** Isometric orthographic view, fixed.
- **UI and typography:** UI is minimal: thin geometric line icons and small flat buttons in the level's pastel hues, with no frames or panels. Type is a light, widely spaced geometric sans in cream or the dark contrast colour. Numbers are small and thin, with Roman numerals for chapter titles.
- **VFX and motion:** Effects are few: slow drifting motes, a soft glow on switches and a thin ring that expands from a touched point. Motion is calm and mechanical: pieces of architecture rotate, slide and unfold with smooth eased moves, and the figure walks in small even steps.

## Fits

- **Genres:** `puzzle`, `exploration`, `platformer`, `tower-defense`
- **Moods:** serene, dreamlike, contemplative
- **Settings:** floating temples, impossible palace, sky ruins

## Godot recipe

### Assets

Build levels from scratch on a strict unit grid with `SurfaceTool` or a `GridMap` and `MeshLibrary` in a generator script: cubes, stairs, arches, domes and towers forming small monuments that float in empty space. Details are geometric cut-outs (windows, doors, crenellations), not textures. Impossible loops only connect from the fixed view, so author connectivity in screen space: a level script declares which grid nodes are joined when seen from the camera angle. Store packs do not fit. Split all normals so faces are flat.

### Materials

Write `tritone.gdshader`, a spatial shader with `render_mode unshaded`: `fragment()` turns `NORMAL` into world space with `INV_VIEW_MATRIX` and selects one of three colours by its dominant axis (top lightest, left mid, right darkest), each supplied per material as `uniform vec4 top_color : source_color`, `left_color` and `right_color`. No light is read, no gradient on a face and no falloff. Curved pieces such as domes quantise their normal to the same three choices or use a designed vertex colour. Turn shadow casting off on every mesh because nothing casts a shadow. Each level defines three or four hues from the pastel palette plus the deep contrast colour `#2f3e56`. A soft glow on a few switches is a variant that sets `ALBEDO` above 1 so the glow picks it up.

### Lighting and atmosphere

No lights and no shadows. No fog, SSAO or probes. The background is a smooth two- or three-stop gradient drawn by a `shader_type sky;` shader that mixes the stops by `EYEDIR.y`, or a full-screen quad. The camera is a `Camera3D` with orthographic projection at a true isometric angle (rotate 45 degrees about Y, about 35.26 degrees down) and never orbits freely; it only steps between fixed views.

### Post-processing

Minimal: tonemap Linear so the pastel values are exact, optional glow with a high HDR threshold for the few glowing elements. No depth-of-field blur, grain or vignette. MSAA 8x or screen-space AA SMAA for perfect edges; `rendering/scaling_3d/scale` 1.

### UI and effects

No frames or panels: thin geometric line icons and small flat buttons (`StyleBoxFlat` in the level's hues). Import a light geometric sans such as Josefin Sans Light or Jost Light as the theme default `FontFile` with wide spacing through a `FontVariation`, in cream or the dark contrast colour; small thin numbers, Roman numerals for chapter titles. Effects are few: slow drifting motes (`GPUParticles3D`), a thin ring mesh that expands from a touched point, a soft glow on switches. Architecture rotates, slides and unfolds with smooth eased `Tween`s of 0.6 to 1.2 s; the figure walks in small even steps.

## Do / Do not

Do:

- Use a true isometric orthographic camera.
- Assign exactly three tones by face direction.
- Build on a strict unit grid.
- Float the structure in an empty gradient background.

Do not:

- Do not use perspective or cast shadows.
- Do not use irregular triangulated facets and landscapes; that reads as `066`.
- Do not use pure primaries on white; that reads as `098`.
- Do not add long shadows on an empty plaza; that reads as `084`.

## Nearest styles

- `066` Faceted low-poly gradient: here each colour has just three flat tones set by face direction, on strict cubes and stairs; `066` has irregular triangle facets that each take a different shade, more colours and natural landscapes.
- `098` Bauhaus primary geometry: colours here are soft pastels on a gradient background; `098` uses pure red, yellow and blue on white.
- `084` Metaphysical long-shadow plaza: this style has no cast shadows and plain flat pastel faces; `084` throws long dark shadows across an empty plaza and uses deeper, painted colour.
