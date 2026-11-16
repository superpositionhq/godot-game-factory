# Art Nouveau ornamental poster

Reference works: Alphonse Mucha.

## References

- *Gismonda* (1894), Alphonse Mucha, lithographic poster. https://en.wikipedia.org/wiki/Gismonda
- *The Seasons* (1896), Alphonse Mucha, colour lithograph series. https://en.wikipedia.org/wiki/The_Seasons_(Mucha)
- *Hotel Tassel* (1893), Victor Horta, architecture. https://en.wikipedia.org/wiki/Hôtel_Tassel
- *The Kiss* (1908), Gustav Klimt, oil and gold leaf painting. https://en.wikipedia.org/wiki/The_Kiss_(Klimt)
- *Paris Metro entrances* (1900), Hector Guimard, cast-iron architecture. https://en.wikipedia.org/wiki/Paris_Metro_entrances_by_Hector_Guimard

## Visual definition

- **Shape language and proportions:** Long flowing curves everywhere: whiplash tendrils, hair in ribbon-like strands, lily and iris stems, peacock feathers. Figures are tall and framed by circles, arches and ornamental panels. Architecture and furniture curve like plants.
- **Line and outline:** Bold, smooth contour of varying weight around figures (heavier outside, finer inside), in dark brown rather than black.
- **Shading model:** Flat colour with at most one soft tone step; faces may have light gradient modelling.
- **Palette:** `#3b2f2f` `#e8d5a9` `#c9a24b` `#8fa98b` `#d9897a` `#6f8fa8` `#f3ead2` `#a8566a`. Muted warm pastels: cream, peach, sage green, dusty blue and rose, with gold and a dark brown line.
- **Lighting:** None, or a soft even light.
- **Texture and surface:** Dense ornament inside frames: mosaic halos, repeating floral and geometric borders, stylised stars, gold patterns on robes. Lithographic paper grain.
- **Atmosphere and post-processing:** Paper tint; no other effects.
- **Camera and framing:** Frontal, tall vertical format, centred figure inside a decorative frame.
- **UI and typography:** Panels sit in ornamental frames with arched or circular tops, whiplash-curve corners and floral borders in gold on cream; icons are stylised flowers, stars and feathers in a dark brown contour. Text is hand-drawn Art Nouveau display lettering with swelling curved strokes, in dark brown or gold. Numbers use the same lettering, rose for damage and sage green or gold for gains.
- **VFX and motion:** Particles are drifting petals, leaves, stars and gold flecks that follow long curling paths; hits show as a ring of radiating halo lines or a burst of petals. Motion is slow and flowing with long ease-in and ease-out, and hair, ribbons and cloth trail in S-curves.

## Fits

- **Genres:** `puzzle`, `rpg`, `exploration`, `detective-mystery`, `strategy`
- **Moods:** elegant, dreamy, romantic
- **Settings:** Belle Époque Paris, flower garden, theatre, fairy-tale court

## Godot recipe

### Assets

Long flowing curves: tall figures with ribbon-like hair strands, lily and iris stems, peacock feathers, furniture and architecture that curve like plants. Build ornamental frames from scratch: circles, arches and panels generated in a generator script with `SurfaceTool` and filled with repeating borders, mosaic halos, stars and gold patterns as textures. Bend pack architecture with a spline deformation (in the generator script with `MeshDataTool`, or in Blender by script) where possible. Remove PBR maps; assign flat muted pastels. Generate a lithographic paper-grain texture and tiling ornament strips with `Image`.

### Materials

Write `nouveau_flat.gdshader`. It outputs flat colour with at most one soft tone step: in `light()`, `smoothstep` over a wide range on the dot of `NORMAL` and `LIGHT`, lowering value by 10 to 15 percent, written to `DIFFUSE_LIGHT`; face materials allow a gentle gradient. Robe and halo materials overlay a tiling ornament texture in gold `#c9a24b` in `fragment()`, with a subtle view-dependent sheen (a soft `SPECULAR_LIGHT` term from `VIEW`) so gold reads as metallic ink. The contour is an inverted-hull shell in `next_pass` (`cull_front`, `unshaded`, vertices pushed along `NORMAL`) in dark brown `#3b2f2f`, bold (4 to 5 px) on outer silhouettes; inner lines are finer and come from the post pass. Shadow casting optional and usually off.

### Lighting and atmosphere

Soft even light: one `DirectionalLight3D` without shadows for the tone step, flat cream ambient colour. No fog, SSAO, SDFGI or probes. Background is cream `#f3ead2` (the background colour) or a flat pastel panel inside an ornamental frame.

### Post-processing

A full-screen quad shader (2x2 `QuadMesh`, `POSITION = vec4(VERTEX.xy, 1.0, 1.0);`) draws fine inner contours (1.5 px, dark brown) from `hint_normal_roughness_texture` and `hint_depth_texture`, giving the heavier-outside, finer-inside line hierarchy with the hull. On the Mobile renderer: take the inner contours from depth alone, or from normals rebuilt from neighbouring depth samples in the same shader. A `ColorRect` on a `CanvasLayer` with a `canvas_item` shader reading `hint_screen_texture` then multiplies the paper grain and a cream tint. Tonemap `Linear`. No glow, blur or vignette. SMAA.

### UI and effects

Panels sit in ornamental frames with arched or circular tops, whiplash-curve corners and floral borders in gold on cream, as 9-slice `StyleBoxTexture` images made in a generator script. Lettering from a display face with swelling curved strokes such as Federo or Fascinate as the `Theme` font, in dark brown or gold. Numbers in the same face, rose `#a8566a` for damage, sage or gold for gains. Icons are stylised flowers, stars and feathers. Particles follow long curling paths (`GPUParticles3D` with low-frequency turbulence, or moved along a path by script): petals, leaves, stars, gold flecks. Hits show a ring of radiating halo lines or a petal burst. Use long `Tween` eases and S-curve secondary motion on hair, ribbons and cloth.

## Do / Do not

Do:

- Build forms from long whiplash curves.
- Frame the figure with a circle or arch and ornament borders.
- Use muted pastels with gold and a brown line.
- Vary contour weight smoothly.

Do not:

- Do not use straight streamlined geometry with chrome and stepped forms; that reads as `096`.
- Do not use an even thin keyline with blue-dominated flats; that reads as `082`.
- Do not fill the frame with interlaced knotwork in strong colours; that reads as `086`.
- Do not back-light glass panes with black leading; that reads as `054`.

## Nearest styles

- `082` Ukiyo-e woodblock: this style has a contour of changing weight, dense ornament borders, gold and many muted pastels; `082` has an even fine keyline, plain flat colour areas and a small palette built on blue.
- `086` Insular illuminated manuscript: this style has tall flowing figures in muted pastels with plain areas between the ornament; `086` has stiff geometric figures in strong red, blue and green, with knotwork that fills every border and shape.
- `096` Art Deco streamline: this style is outlined in brown, with plant-like curves and flat colour; `096` has no outline and shows straight, stepped, streamlined forms in smooth-shaded metal and stone.
