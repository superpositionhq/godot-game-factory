# Insular illuminated manuscript

Reference works: Book of Kells; The Secret of Kells.

## References

- *Book of Kells* (c. 800), Columban monks (Iona and Kells), illuminated manuscript. https://en.wikipedia.org/wiki/Book_of_Kells
- *Lindisfarne Gospels* (c. 715-720), Eadfrith of Lindisfarne, illuminated manuscript. https://en.wikipedia.org/wiki/Lindisfarne_Gospels
- *The Secret of Kells* (2009), Cartoon Saloon (Tomm Moore and Nora Twomey), animated film. https://en.wikipedia.org/wiki/The_Secret_of_Kells
- *Song of the Sea* (2014), Cartoon Saloon (Tomm Moore), animated film. https://en.wikipedia.org/wiki/Song_of_the_Sea_(2014_film)

## Visual definition

- **Shape language and proportions:** Flat, geometric stylisation: figures built from circles and rounded rectangles with almond eyes; trees as spirals and concentric rings; everything fitted into circles, squares and bordered panels.
- **Line and outline:** Dark brown-black outline of even weight around every shape and every strand of ornament.
- **Shading model:** None. Flat colour.
- **Palette:** `#2b1d14` `#e9d8a6` `#c8962e` `#b3261e` `#1f6f6b` `#3b4fa0` `#6a3d7c` `#3f7d3a`. Vellum cream ground with gold-yellow, red, teal-green, blue and purple.
- **Lighting:** None.
- **Texture and surface:** Extremely dense ornament filling borders and shapes: interlaced knotwork bands, triple spirals, key patterns, rows of red dots, tiny interlocked animals. Vellum grain.
- **Atmosphere and post-processing:** Vellum overlay with slight mottling.
- **Camera and framing:** Flat, frontal, orthographic; compositions framed by ornamental borders.
- **UI and typography:** Panels are vellum blocks inside knotwork borders with spiral corner bosses; icons are tiny interlaced animals and geometric emblems outlined in dark brown. Text is a rounded insular half-uncial script in brown-black, with large decorated initials in red and gold. Numbers use the same pen-written script, red for damage and gold for rewards, often ringed by red dots.
- **VFX and motion:** Particles are flat outlined shapes: spirals, triple spirals, rows of red dots and gold flecks that unwind along curling paths. Hits burst as concentric rings or a rosette of flat petals. Animation is flat and graphic on twos, and knotwork lines draw themselves along their path.

## Fits

- **Genres:** `puzzle`, `platformer`, `exploration`, `action-adventure`, `rpg`, `tower-defense`
- **Moods:** mystical, reverent, whimsical
- **Settings:** early medieval Ireland, island monastery, enchanted forest, Viking raid coast

## Godot recipe

### Assets

Flat, geometric art fitted into circles, squares and bordered panels. Figures are built from circles and rounded rectangles with almond eyes; trees are spirals and concentric rings. Author everything as flat meshes or sprites on a vellum plane. The ornament is the main workload and should be made in a generator script: interlaced knotwork bands (grid-based over-under weaving), triple spirals, key patterns, rows of red dots and small interlocked animals, output as vector-like meshes (`SurfaceTool`) or 4096 px `Image` textures with a dark outline around every strand. Generate a vellum texture with grain and mottling.

### Materials

`StandardMaterial3D` with `shading_mode` unshaded covers the flat colours: gold-yellow, red, teal-green, blue and purple fills with brown-black `#2b1d14` outlines drawn into the art. A custom unshaded shader, `illumination.gdshader`, adds two things: a `draw` uniform that reveals a knotwork strand along its length (discard where a path-distance value stored in the second UV channel exceeds it) so lines can draw themselves, and an optional faint view-dependent sheen on gold areas. No lighting, shadow casting off; depth or render-priority ordering only if layers need sorting.

### Lighting and atmosphere

None. No lights, shadows, fog, SSAO or probes. Orthographic `Camera3D` facing the page; the background colour is vellum `#e9d8a6`.

### Post-processing

One `ColorRect` on a `CanvasLayer` above the UI, with a `canvas_item` shader in `render_mode blend_mul;`, multiplies the vellum texture and slight mottling over the whole frame, UI included. Tonemap `Linear`. No glow, blur or vignette. MSAA 8x or SMAA: the even outline around fine interlace needs clean edges; `rendering/scaling_3d/scale` 1 or higher.

### UI and effects

Panels are vellum blocks inside knotwork borders with spiral corner bosses, built with the same generator and used as 9-slice `StyleBoxTexture`. Text in a rounded insular script: the `Theme` font is an uncial face such as Uncial Antiqua or Eagle Lake, brown-black, with large decorated initials as separate `TextureRect` images in red and gold. Numbers in the same script, red for damage, gold for rewards, ringed by red dots. Icons are tiny interlaced animals and geometric emblems. Particles are flat outlined sprites (`GPUParticles2D`, or billboard quads in 3D): spirals, triple spirals, red dots and gold flecks moving along curling paths. Hits burst as concentric rings or a rosette of flat petals. Animate on twos.

## Do / Do not

Do:

- Fill borders and shapes with knotwork and spirals.
- Outline every element in dark brown.
- Fit compositions into circles and framed panels.
- Use a vellum ground.

Do not:

- Do not leave large plain areas with thread texture; that reads as `056`.
- Do not use flowing whiplash figures in muted pastels; that reads as `083`.
- Do not use glazed star-and-polygon tiling without figures or outlines; that reads as `100`.
- Do not add shading.

## Nearest styles

- `056` Embroidered tapestry: this style has strong red, blue, purple and gold on vellum, with ornament packed into every border and shape; `056` has muted colours, large plain areas and visible thread texture.
- `083` Art Nouveau ornamental poster: this style has stiff geometric figures, an even outline and strong colours with knotwork everywhere; `083` has tall flowing figures, a contour of changing weight and muted pastels with plain areas between the ornament.
- `100` Islamic geometric tile: this style has a dark outline around every element, flat matte colour and figures and animals; `100` has star-and-polygon tiles with pale grout lines, a glossy glazed surface and no figures.
