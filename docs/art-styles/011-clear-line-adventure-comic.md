# Clear-line adventure comic

Reference works: The Adventures of Tintin.

## References

- *The Adventures of Tintin* (1929), Herge, comic album series. https://en.wikipedia.org/wiki/The_Adventures_of_Tintin
- *Blake and Mortimer* (1946), Edgar P. Jacobs, comic album series. https://en.wikipedia.org/wiki/Blake_and_Mortimer
- *The Adventures of Tintin (film)* (2011), Amblin Entertainment and WingNut Films, animated film. https://en.wikipedia.org/wiki/The_Adventures_of_Tintin_(film)
- *XIII* (2003), Ubi Soft Paris, video game. https://en.wikipedia.org/wiki/XIII_(2003_video_game)

## Visual definition

- **Shape language and proportions:** Accurate, well-researched objects (vehicles, buildings, machines) drawn with simplified but correct proportions. Characters have simple round faces on realistic bodies.
- **Line and outline:** Black line of one constant weight (about 2 px) on every silhouette and every inner edge. No hatching, no line-weight variation.
- **Shading model:** None. One flat colour per surface, no cast shadows or only a flat ground shadow.
- **Palette:** `#1a1a1a` `#f4efe1` `#d93a2b` `#2f6fb5` `#f2c230` `#7fb069` `#c9a27a`. Clear, medium-saturation flats on off-white: red, blue, yellow, green and skin tan. No gradients.
- **Lighting:** Even, shadowless.
- **Texture and surface:** None. Detail is carried by line alone (bricks, planks and rivets drawn as outlines).
- **Atmosphere and post-processing:** None. Clean anti-aliased edges.
- **Camera and framing:** Eye-level, readable, full-figure compositions with deep focus.
- **UI and typography:** Off-white rectangular panels with a thin black border, like comic caption boxes and speech balloons. Text is hand-lettered upright comic capitals in black; icons are small flat-colour line drawings. Counters and damage numbers are bold black-outlined numerals filled with yellow or red.
- **VFX and motion:** Effects are drawn comic marks: white puff clouds with a black outline, star bursts on impact, speed lines, sweat drops and lettered sound words. Animation is crisp with clear held poses and quick moves between them; nothing glows or blurs.

## Fits

- **Genres:** `action-adventure`, `detective-mystery`, `exploration`, `puzzle`, `stealth`, `platformer`
- **Moods:** adventurous, light-hearted, curious
- **Settings:** 1930s port city, desert expedition, steamship and seaplane travel, mountain monastery

## Godot recipe

### Assets

Use accurate, well-proportioned vehicle, building and machine packs (glTF or FBX); correctness of shape matters more than polygon count. Strip every map. Assign one flat medium-saturation colour per surface from the palette. Surface detail must exist as line, so generate line textures in a generator script with `Image` (brick courses, planks, rivets as thin black outlines on transparent, saved with `save_png`) or model small bevels and seams that the edge pass will pick up. Characters need simple round heads; swap pack heads for simple spheres with drawn features.

### Materials

Write one spatial shader, `clear_line.gdshader`, with `render_mode unshaded, shadows_disabled;`: `fragment()` sets `ALBEDO` to a `source_color` uniform base colour times an optional line texture. Nothing is lit and no mesh casts a shadow (turn off cast shadows on every `MeshInstance3D` too). Each material is a `.tres` `ShaderMaterial` using that shader. A material-ID trick improves inner lines: since every surface is one flat unlit colour, the edge pass can compare the screen colour itself as an ID, so a line appears wherever one material meets another; give two touching surfaces that share a colour a barely different shade so they still split.

### Lighting and atmosphere

No lights are needed. Set the `Environment` ambient light to a flat colour, no shadows, no fog, no SSAO, no probes, no SDFGI. If a ground shadow is wanted, use a flat dark oval quad under each character. Background is one flat pale colour (background mode colour).

### Post-processing

One full-screen quad in front of the camera (a 2x2 `QuadMesh` whose spatial shader sets `POSITION = vec4(VERTEX.xy, 1.0, 1.0);`, unshaded). It reads `hint_screen_texture`, `hint_depth_texture` and `hint_normal_roughness_texture`, runs a Roberts-cross test on depth, normals and the material ID and draws `#1a1a1a` lines of one constant width, about 2 px at 1080p (scale the sample offset with screen height). Keep thresholds strict so every silhouette and inner edge gets a line and curved surfaces do not. Tonemap Linear; no glow, no adjustments. MSAA 4x or SMAA so lines are clean and anti-aliased. On the Mobile renderer: there is no normal-roughness buffer, so rebuild normals from the depth texture (cross product of neighbouring reconstructed view positions) and keep the depth and colour-ID tests as they are.

### UI and effects

Off-white rectangular panels with a thin black border (`StyleBoxFlat`, fill `#f4efe1`, border `#1a1a1a`), and speech balloons with tails as `NinePatchRect` textures. The theme font is an upright comic lettering face such as Comic Neue Bold or Patrick Hand SC, black on `#f4efe1`. Counters are bold numerals filled with `#f2c230` or `#d93a2b` with a black outline (`LabelSettings` outline size and colour). Effects are drawn marks as sprites with a black outline on alpha-scissor billboard quads: white puff clouds, star bursts, speed lines, sweat drops and sound words. No additive blending and no blur.

## Do / Do not

Do:

- Keep one line weight everywhere.
- Use one flat colour per surface.
- Model or draw small details as outline only.
- Keep object proportions accurate.

Do not:

- Do not vary line weight or add hatching; that reads as `001`.
- Do not add shading bands; that reads as `015`.
- Do not shift to pale desaturated washes with sparse thin lines; that reads as `012`.
- Do not add print dots; that reads as `081`.

## Nearest styles

- `012` Thin-line pastel desert: `012` uses pale sand and pastel tints with thin lines that become sparse in open areas; this style uses clear red, blue and yellow flats with one firm black line on every edge.
- `081` Ben-Day pop art: `081` fills skin and skies with visible printed dots; this style keeps every fill a plain flat colour.
- `082` Ukiyo-e woodblock: `082` shows wood grain in its colour areas and fades its skies from dark to light; this style has clean fills with no grain and no fades.
