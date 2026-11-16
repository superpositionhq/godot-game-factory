# Rubber-hose 1930s cartoon

Reference works: Cuphead.

## References

- *Cuphead* (2017), Studio MDHR, video game. https://en.wikipedia.org/wiki/Cuphead
- *Steamboat Willie* (1928), Walt Disney Studio, animated short film. https://en.wikipedia.org/wiki/Steamboat_Willie
- *The Skeleton Dance* (1929), Walt Disney Productions, animated short film. https://en.wikipedia.org/wiki/The_Skeleton_Dance
- *Minnie the Moocher* (1932), Fleischer Studios, animated short film. https://en.wikipedia.org/wiki/Minnie_the_Moocher_(film)
- *Bendy and the Ink Machine* (2017), Kindly Beast, video game. https://en.wikipedia.org/wiki/Bendy_and_the_Ink_Machine

## Visual definition

- **Shape language and proportions:** Limbs are boneless tubes of constant thickness with no elbows or knees. Heads and bodies are circles and pears. Hands have four fingers and white gloves; eyes are tall ovals with a pie-cut pupil.
- **Line and outline:** Thick black outline (4 to 6 px) of even weight on every shape, including inner features.
- **Shading model:** Flat fill. At most one soft airbrushed shadow shape on the body.
- **Palette:** `#1a1612` `#f1e3c2` `#c9543a` `#e2a93b` `#6f8f8a` `#8a5a3c` `#fff8e6`. Cream paper, warm black, and faded red, mustard and teal, as if printed on aged film stock.
- **Lighting:** None in the image-making sense. Everything is evenly lit.
- **Texture and surface:** Characters are flat. Backgrounds look like watercolour: soft washes with paper grain.
- **Atmosphere and post-processing:** Film grain, dust specks, vertical scratches, slight flicker, soft blur, vignette and small chromatic fringing.
- **Camera and framing:** Flat, side-on staging like a theatre stage; orthographic or long lens.
- **UI and typography:** Panels look like 1930s film title cards: cream card (`#f1e3c2`) with warm-black lettering and scalloped or ribbon borders. Faces are bouncy hand-drawn display serifs and brush script. Health and counters appear as playing-card tokens or thick outlined numerals in faded red and mustard.
- **VFX and motion:** Effects are drawn frame by frame with the same thick line: puff clouds, star bursts, sweat drops and smoke rings. Animation runs on ones or twos at 24 frames per second, with constant bounce, heavy squash and stretch and looping idle bobs.

## Fits

- **Genres:** `platformer`, `top-down-shooter`, `fighting`, `puzzle`, `survival-horror`
- **Moods:** zany, mischievous, eerie
- **Settings:** carnival, casino, cartoon islands, 1930s animation studio

## Godot recipe

### Assets

Build characters from scratch or restyle simple cartoon rigs: limbs must be tubes of constant thickness, so replace arm and leg meshes with swept tubes (built in Blender by script or with `SurfaceTool`) and remove elbow and knee shaping. Bodies are spheres and pear shapes; add white glove hands with four fingers. No pack textures: every character material is a flat fill. Backgrounds are quads carrying watercolour paintings made with `Image` in a generator script (soft washes plus paper grain) or pack scenery rendered once to textures through a `SubViewport` and blurred.

### Materials

Characters use a shader such as `rubber_hose.gdshader`: `render_mode unshaded;` with a flat `base_color` in `ALBEDO`, optionally one soft airbrushed shadow from a mask texture. The outline is an inverted hull in `next_pass` (`unshaded`, `cull_front`), constant 4 to 6 px in screen space, colour `#1a1612`; inner features such as mouths and pupils are separate black meshes. Set `cast_shadow` off on every mesh. Backgrounds use an unshaded `StandardMaterial3D`.

### Lighting and atmosphere

No lighting model. No light nodes, no shadows, no fog, no `ReflectionProbe`, no SSAO. Stage scenes side-on with a `Camera3D` in orthogonal projection or a long lens (small `fov`).

### Post-processing

This is where the style is made. Convert to faded stock with `Environment` adjustments: `adjustment_saturation` 0.7 and a warm colour-correction LUT toward `#f1e3c2`. A full-screen `ColorRect` on a `CanvasLayer` with a `canvas_item` shader reading `hint_screen_texture` (`filter_linear_mipmap`) adds strong film grain, vignette, light chromatic fringing and a slight blur by sampling a lower mip with `textureLod`, then animated dust specks, vertical scratches and exposure flicker from a small noise atlas that changes 12 times per second (`floor(TIME * 12.0)`), plus a subtle gate weave of one or two pixels.

### UI and effects

Title-card UI: cream panels with scalloped or ribbon borders as `StyleBoxTexture` 9-slices, lettering from a bouncy display serif such as Chango and a brush script such as Lobster, in warm black. Counters are playing-card tokens or thick outlined numerals in `#c9543a` and `#e2a93b`. Effects are flipbooks drawn with the same thick line: puff clouds, star bursts, sweat drops, smoke rings. Step character animation to 12 poses per second by setting the `AnimationPlayer` callback process mode to Manual and calling `advance(1.0 / 12.0)` on a fixed tick, and add a looping idle bob.

## Do / Do not

Do:

- Bend limbs as smooth arcs without joints.
- Keep outline width constant and thick.
- Apply grain, scratches and flicker over the whole frame.
- Use white gloves and pie-cut eyes on characters.

Do not:

- Do not use thin lines on clean flat colour without grain; that reads as `011`.
- Do not add cel bands or rim highlights; that reads as `015`.
- Do not go fully greyscale with painted shadows; that reads as `071`.
- Do not use sharp digital edges without film softness.

## Nearest styles

- `011` Clear-line adventure comic: this style has a thick line, boneless limbs and film grain, scratches and flicker over faded colours; `011` has a thin clean line on crisp flat colour with no grain.
- `081` Ben-Day pop art: this style uses faded cream, mustard and teal with soft watercolour backgrounds and no dots; `081` uses pure primaries filled with a regular grid of large dots.
- `022` Sumi-e ink wash: this style has a thick line of even weight on aged-film cream; `022` has calligraphic brush strokes that swell, thin and break, on brighter paper with uneven colour wash.
