# Mosaic tessera

Reference works: Basilica of San Vitale, Ravenna.

## References

- *Mosaics of the Basilica of San Vitale* (547), Byzantine workshops, Ravenna, glass and stone mosaic. https://en.wikipedia.org/wiki/Basilica_of_San_Vitale
- *Alexander Mosaic* (c. 100 BC), Roman workshop, House of the Faun, Pompeii, floor mosaic. https://en.wikipedia.org/wiki/Alexander_Mosaic
- *Mosaics of the Mausoleum of Galla Placidia* (c. 425-450), Late Roman workshops, Ravenna, glass mosaic. https://en.wikipedia.org/wiki/Mausoleum_of_Galla_Placidia
- *Park Guell trencadis* (1914), Antoni Gaudi and Josep Maria Jujol, broken-tile mosaic. https://en.wikipedia.org/wiki/Park_Güell

## Visual definition

- **Shape language and proportions:** Images and surfaces are built from thousands of small tiles (tesserae), roughly square, 5 to 15 mm, laid in rows that follow the contours of each shape. Figures are frontal and stylised with large eyes.
- **Line and outline:** Dark grout fills the gaps between tiles; darker tile rows trace the contours of figures.
- **Shading model:** Tone is stepped: each form uses three to five tile colours from light to dark, placed in rows. Individual tiles catch light at slightly different angles.
- **Palette:** `#c9a227` `#1f3f7a` `#2f7a5a` `#9a2f2a` `#e8dcc0` `#3a3a3a` `#d98a5a` `#f5f1e6`. Gold backgrounds with deep blue, green, red, flesh tones and white.
- **Lighting:** Raking light so tile tilt and gold sparkle are visible.
- **Texture and surface:** The tile grid itself: irregular small pieces, uneven gaps, varied tilt and gloss.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** Frontal for wall panels; any angle for mosaic-covered 3D objects.
- **UI and typography:** Panels are mosaic bands: gold tile fields edged with rows of dark and white tesserae, with icons as small tile pictures in round or square medallions. Type is a square Roman or Byzantine capital laid in dark tiles on gold. Numbers are tile-built numerals in white or deep blue.
- **VFX and motion:** Effects are made of tiles: hits knock tesserae loose and scatter them, colour changes ripple across a surface tile by tile, and gold tiles glint in sequence as the light moves. Figures hold stiff frontal poses and change position by re-laying rows of tiles, not by bending smoothly.

## Fits

- **Genres:** `puzzle`, `strategy`, `rpg`, `tower-defense`, `exploration`
- **Moods:** solemn, ancient, ornate
- **Settings:** Byzantine basilica, Roman villa, Mediterranean port, tiled garden park

## Godot recipe

### Assets

Surfaces must be built from tiles. A generator script converts images or textures into tessera layouts with `Image`: quantise the source to three to five tile colours per form, compute a flow field that follows shape contours, and lay rows of roughly square pieces (5 to 15 mm at world scale) with uneven gaps; dark rows trace figure contours. Output either real geometry (small bevelled quads with random tilt in a `MultiMeshInstance3D`, one colour per instance) for hero surfaces, or baked maps (albedo, normal with per-tile tilt, roughness varying per tile, a grout mask, a tile-ID map) for the rest. Figures are frontal with large eyes.

### Materials

`StandardMaterial3D` with the baked maps does most of the work: per-tile normal tilt makes tiles catch light differently, grout is dark `#3a3a3a` and rough. Gold tiles use metallic 1, albedo `#c9a227` and low, varied roughness so they sparkle. For glints in sequence, write `mosaic.gdshader`, a spatial shader that sets `ALBEDO`, `NORMAL_MAP`, `ROUGHNESS` and `METALLIC` from the same maps and adds an `EMISSION` pulse on gold whose phase is a per-tile random value from the tile-ID texture plus the angle of a light-direction uniform that a script updates from the moving light, so glints sweep with the light. Hero surfaces made of real tiles use one material with `vertex_color_use_as_albedo` on, reading each instance's colour.

### Lighting and atmosphere

Raking light: a `DirectionalLight3D` or `SpotLight3D` at a low angle to the mosaic plane, moving slowly, so tile tilt and gold sparkle show. Moderate neutral ambient, lit from the front. Soft shadows (`shadow_blur`), short `directional_shadow_max_distance`. A `ReflectionProbe` with a few bright emissive sources helps gold. SSAO on, tiny radius, to deepen grout. No fog. On the Mobile renderer: darken the grout further in the baked albedo, or bake occlusion with `LightmapGI`, in place of SSAO.

### Post-processing

None of note: tonemap Linear, optional faint glow restricted to gold glints (HDR threshold above 1.2). No grain or blur. MSAA 4x or screen-space AA SMAA and `rendering/scaling_3d/scale` 1: tile edges must stay crisp.

### UI and effects

Panels are mosaic bands: gold tile fields edged with rows of dark and white tesserae as `StyleBoxTexture` 9-slices, icons as tile pictures in medallions; bake them with the same layout script. Lettering is laid in tiles: use a square Roman capital face such as Cinzel or Marcellus SC, draw title text into an `Image` and pass it through the tile layout script, with the same face imported as the theme default `FontFile` for small text. Effects are tiles: hits knock tesserae loose as small `RigidBody3D` pieces, colour changes ripple tile by tile using the tile-ID phase, and figures change pose by re-laying rows instead of bending.

## Do / Do not

Do:

- Lay tiles in rows that follow contours.
- Give each tile one colour and a slightly different tilt.
- Use gold metallic tiles for backgrounds.
- Light at a raking angle.

Do not:

- Do not use a perfectly regular geometric star pattern in glazed tile; that reads as `100`.
- Do not use large panes with black lines and backlight; that reads as `054`.
- Do not use round paint dots without grout; that reads as `077`.
- Do not let colours vary inside one tile.

## Nearest styles

- `100` Islamic geometric tile: here small irregular tiles follow the contours of figures, with tone stepped from light to dark and many colours on gold; `100` is smooth glazed tile in a few colours, cut to a perfectly regular star pattern with no figures.
- `077` Pointillist dot field: dark grout separates every tile here and tone steps in rows; `077` is round paint dots that touch with no dark gaps and blend into soft colour at a distance.
- `054` Stained glass: the surface here is a dense field of tiny tiles lit from the front; `054` is large smooth panes held in thick black lead and lit from behind.
