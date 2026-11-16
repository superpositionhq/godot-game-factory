# Ben-Day pop art

Reference works: Roy Lichtenstein.

## References

- *Whaam!* (1963), Roy Lichtenstein, acrylic and oil painting. https://en.wikipedia.org/wiki/Whaam!
- *Drowning Girl* (1963), Roy Lichtenstein, oil and acrylic painting. https://en.wikipedia.org/wiki/Drowning_Girl
- *Look Mickey* (1961), Roy Lichtenstein, oil painting. https://en.wikipedia.org/wiki/Look_Mickey
- *Oh, Jeff...I Love You, Too...But...* (1964), Roy Lichtenstein, oil and acrylic painting. https://en.wikipedia.org/wiki/Oh,_Jeff...I_Love_You,_Too...But...
- *Marilyn Diptych* (1962), Andy Warhol, silkscreen painting. https://en.wikipedia.org/wiki/Marilyn_Diptych

## Visual definition

- **Shape language and proportions:** Enlarged comic-panel imagery: simplified glamorous faces, machines, explosions as spiky bursts, smoke as scalloped clouds. Shapes are clean and mechanical.
- **Line and outline:** Thick black outlines of even or smoothly swelling weight around every form; black shapes for hair and shadow.
- **Shading model:** None beyond black shadow shapes. Tone is given by a regular grid of large dots (red dots on white for skin, blue dots for sky) or by parallel stripes.
- **Palette:** `#000000` `#ffffff` `#e3202a` `#ffd500` `#1747b5` `#f7c8b0`. Primary red, yellow and blue with black and white. Nothing else.
- **Lighting:** None.
- **Texture and surface:** Mechanical Ben-Day dots: uniform size, perfectly regular grid, large enough to see individually (dot pitch about 1.2 to 2% of frame height).
- **Atmosphere and post-processing:** None; hard clean edges.
- **Camera and framing:** Tight crop like a single comic panel; flat.
- **UI and typography:** Panels are yellow caption boxes with black borders and white speech balloons with pointed tails; icons are thick-outlined black shapes with one flat primary fill. Text is hand-lettered comic capitals in black, bold italic for emphasis. Damage numbers and counters are heavy slanted block numerals in red or yellow with a black outline, set inside spiky burst shapes.
- **VFX and motion:** Hits are spiky red-and-yellow starbursts with a lettered sound word; smoke is scalloped outlined clouds and speed is drawn as straight black lines. Motion uses snappy held poses that change on twos or threes, like one panel replacing another, with no blur.

## Fits

- **Genres:** `fighting`, `vehicle-combat`, `top-down-shooter`, `platformer`, `puzzle`
- **Moods:** bold, ironic, melodramatic
- **Settings:** 1960s America, aerial dogfight, comic-book city

## Godot recipe

### Assets

Comic-panel subjects with clean, mechanical shapes: simplified glamorous faces, machines, aircraft, explosions as spiky bursts, smoke as scalloped clouds. Use smooth stylised models; strip all textures and give each surface only black, white, red, yellow, blue or the skin tint `#f7c8b0`. Hair and deep shadow are solid black shapes: give hair meshes black materials and paint black shadow shapes into a mask texture. Give each material a fill mode: flat, dots or stripes. Build bursts and clouds as flat meshes in a generator script with `SurfaceTool`.

### Materials

Write `ben_day.gdshader` (`shader_type spatial;`) with a fill-mode uniform. It outputs a flat fill with no light gradient: ambient black, `SPECULAR_LIGHT` left at zero, and `light()` adding full flat light to `DIFFUSE_LIGHT`; an optional `step` on the dot of `NORMAL` and `LIGHT` switches a surface region to solid black shadow. In dot mode the surface is white with large dots of the fill colour (red on white for skin, blue for sky); in stripe mode, parallel bands. The pattern is a perfectly regular screen-space grid built from `FRAGCOORD` with a pitch of about 1.5 percent of screen height (16 px at 1080p) and one uniform dot size, not modulated by light, which is the main difference from a halftone shader. Outline: an inverted-hull shell in `next_pass` (`cull_front`, `unshaded`), black, 4 to 6 px, its vertices pushed along `NORMAL` and scaled by a vertex-colour weight for smooth width change. Shadow casting optional.

### Lighting and atmosphere

None in effect: one `DirectionalLight3D` gives a direction for the black shadow shapes; shadows off or hard (no blur). Flat ambient colour in the `Environment`. No fog, SSAO, SDFGI or probes. Backgrounds are flat primary colours (the background colour) or dotted blue sky.

### Post-processing

A full-screen quad (a 2x2 `QuadMesh` in front of the camera whose spatial shader sets `POSITION = vec4(VERTEX.xy, 1.0, 1.0);`) adds thick black inner lines from discontinuities in `hint_depth_texture` and in the normals of `hint_normal_roughness_texture` to complete the outline around every form. On the Mobile renderer: find these lines from depth alone, or from normals rebuilt from neighbouring depth samples in the same shader. Tonemap `Linear` so primaries are pure. No glow, no colour offset, no paper grain, no blur. MSAA 8x or SMAA for hard clean edges and round dots. Keep `rendering/scaling_3d/scale` at 1 so the dot grid stays regular.

### UI and effects

Yellow caption boxes with black borders (`StyleBoxFlat`) and white speech balloons with pointed tails (`NinePatchRect`). Hand-lettered comic capitals from Bangers or Comic Neue Bold as the `Theme` font, a `FontVariation` slant and embolden for emphasis. Damage numbers and counters are heavy slanted block numerals in red or yellow with a black outline (`LabelSettings` outline), placed inside spiky burst sprites. Icons have a thick outline and one flat primary fill. Effects: spiky red-and-yellow starburst meshes with a lettered sound word (`Label3D`), scalloped outlined smoke clouds, straight black speed lines. Change poses on twos or threes with no blending and no motion blur: step the `AnimationPlayer` at a fixed low rate.

## Do / Do not

Do:

- Use only red, yellow, blue, black and white.
- Fill skin and sky with large regular dots.
- Outline everything in thick black.
- Crop like a single comic panel.

Do not:

- Do not use small varied screens, colour offsets and many hues; that reads as `009`.
- Do not use free round paint dots without outlines; that reads as `077`.
- Do not use flat fills with thin even lines and no dots; that reads as `011`.
- Do not add gradients or grain; that reads as `007`.

## Nearest styles

- `009` Halftone print comic: this style puts a thick black outline around every form and uses only red, yellow, blue, black and white with large uniform dots; `009` outlines selectively, uses small dot screens of varied size with colour offsets, and prints many more hues.
- `011` Clear-line adventure comic: this style fills skin and sky with large visible dots inside thick outlines; `011` has plain flat fills with thin even lines and no dots.
- `079` Primary grid neoplasticism: this style shows curved outlined faces, machines and explosions filled with dots; `079` is only plain rectangles of primary colour divided by straight black bars.
