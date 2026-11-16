# Shadow-puppet cut-out

Reference works: The Adventures of Prince Achmed.

## References

- *The Adventures of Prince Achmed* (1926), Lotte Reiniger, silhouette animated film. https://en.wikipedia.org/wiki/The_Adventures_of_Prince_Achmed
- *Tales of the Night* (2011), Michel Ocelot, animated film. https://en.wikipedia.org/wiki/Tales_of_the_Night_(film)
- *Badland* (2013), Frogmind, video game. https://en.wikipedia.org/wiki/Badland_(video_game)

## Visual definition

- **Shape language and proportions:** All figures and scenery are flat black cut-outs with intricate lace-like perforations: filigree costumes, leaf-by-leaf trees, ornate arches. Figures are in strict profile with jointed limbs.
- **Line and outline:** No line. The silhouette edge is the drawing.
- **Shading model:** None. Foreground shapes are solid black; depth layers behind are progressively lighter translucent tones.
- **Palette:** `#000000` `#f2a23a` `#d9482b` `#2a6f97` `#f6e3b4` `#7a3b69`. Black over a luminous coloured background: amber, red-orange, or deep blue, with a soft bright centre.
- **Lighting:** Back-lit screen: a glowing light source behind translucent layers.
- **Texture and surface:** None in the black. The backlight has a soft gradient and faint paper or tissue mottling.
- **Atmosphere and post-processing:** Slight glow bleeding around silhouette edges; vignette.
- **Camera and framing:** Fixed, flat, orthographic side view.
- **UI and typography:** All UI is black cut-out: filigree frames, perforated borders and silhouette icons laid over the glowing backdrop. Type is an ornate cut-paper display face with thin serifs and curled flourishes, in solid black or cut through so the backlight shows as amber letters. Numbers are plain black silhouette numerals.
- **VFX and motion:** Effects are silhouettes too: black paper sparks and leaves, smoke as layered translucent tissue, and magic as bright holes of backlight that flare through the black. Figures move like jointed puppets, with limbs that pivot at pin joints, a slight frame-by-frame jitter and held profile poses.

## Fits

- **Genres:** `platformer`, `puzzle`, `action-adventure`, `stealth`, `exploration`
- **Moods:** enchanted, eerie, theatrical
- **Settings:** Arabian Nights palace, enchanted forest, fairy-tale kingdom

## Godot recipe

### Assets

All figures and scenery are flat cut-outs. Build them from scratch: draw silhouettes with lace-like perforations in a generator script with `Image` (filigree costumes, leaf-by-leaf trees, ornate arches) into high-resolution alpha textures (2048 to 4096 px, since the edge is the whole drawing), or generate true meshes from vector outlines with `SurfaceTool`. Figures are in strict profile, split into limb pieces joined at pin joints (a node per piece, rotated around its pivot) and animated by rotating the pieces. Store 3D models can be rendered side-on to silhouette masks through a `SubViewport` with an orthographic camera in a small capture scene run once as a rendered play (a generator script runs headless and draws nothing). Arrange layers at set depths in front of a backdrop plane.

### Materials

Foreground cut-outs use an unshaded `StandardMaterial3D`, black, alpha scissor with a high-resolution mask (or a signed distance field mask, generated in the same script and cut at 0.5 with linear filtering, for a crisp edge at any zoom). Deeper layers use an unshaded alpha-transparent material whose colour is a lighter translucent tone, mixed toward the backdrop by layer depth. The backdrop is `backdrop.gdshader`, a spatial shader with black `ALBEDO` and all colour in `EMISSION`: a radial gradient from a soft bright centre (`#f6e3b4`, pushed above 1) to amber, red-orange or deep blue, multiplied by faint tissue mottling. No lighting in any material and shadow casting off on every mesh.

### Lighting and atmosphere

No lights, ambient energy 0, no fog, no SSAO, no probes. Use a `Camera3D` with orthographic projection or a long lens facing the screen. Depth is shown by layer tone only.

### Post-processing

Glow makes the backlight bleed around silhouette edges: HDR threshold just under the backdrop's brightness, low intensity, the middle and upper glow levels on for a wide spread. Vignette 0.4 from a `ColorRect` on a `CanvasLayer` with a `canvas_item` shader. Tonemap Linear. MSAA 8x or screen-space AA SMAA so the perforations stay clean. No grain: this is a glowing coloured screen, not a grey foggy film image. On the Mobile renderer: keep the backdrop centre and the magic holes no brighter than about 1.5 with the threshold just under, since its narrower colour buffer clips and bands a wide glow sooner.

### UI and effects

All UI is black cut-out: filigree frames and perforated borders as `StyleBoxTexture` 9-slices, silhouette icons over the backdrop. Import an ornate thin-serif display face such as Cinzel Decorative or Fredericka the Great as the theme default `FontFile`, in solid black, or inverted so letters are holes showing amber (a `canvas_item` shader that cuts the text out of a black panel). Numerals are plain black silhouettes. Effects are silhouettes: black paper sparks and leaves as alpha-scissor `GPUParticles3D` quads, smoke as layered translucent tissue shapes, magic as bright holes that open in the black (emission above the glow threshold). Add a slight per-frame positional jitter and step limb rotation on twos.

## Do / Do not

Do:

- Keep all foreground shapes solid black.
- Cut fine perforations into silhouettes.
- Use a glowing coloured backdrop with a bright centre.
- Stage in flat profile with an orthographic camera.

Do not:

- Do not use grey fog and film grain without colour; that reads as `070`.
- Do not add incised line detail inside figures on an orange ground; that reads as `087`.
- Do not light the figures from the front.
- Do not use a few coloured flat shapes without black dominance; that reads as `064`.

## Nearest styles

- `070` Silhouette fog monochrome: backdrops here glow amber, red-orange or deep blue; `070` is entirely grey, with fog and film grain.
- `087` Greek black-figure pottery: figures here are pure black, with detail only as holes cut through to a glowing backlight; `087` scratches fine light lines inside its black figures and sets them on a flat, unlit terracotta ground.
- `064` Mid-century cut-paper poster: this style is dark, with black shapes filling most of the frame over a glowing backdrop; `064` is a bright poster of a few flat coloured paper shapes with little black.
