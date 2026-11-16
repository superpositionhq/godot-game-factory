# Expressionist oil isometric

Reference works: Disco Elysium.

## References

- *Disco Elysium* (2019), ZA/UM, video game. https://en.wikipedia.org/wiki/Disco_Elysium
- *Self-Portrait as a Soldier* (1915), Ernst Ludwig Kirchner, oil painting. https://en.wikipedia.org/wiki/Self-Portrait_as_a_Soldier
- *The Scream* (1893), Edvard Munch, painting. https://en.wikipedia.org/wiki/The_Scream

## Visual definition

- **Shape language and proportions:** Realistic, worn urban setting seen from an isometric angle. Forms are slightly loose and unsteady, as if painted quickly from life.
- **Line and outline:** No drawn outline. Some edges are reinforced by dark paint strokes.
- **Shading model:** Painted light with five to eight visible tone patches per form; transitions are made of separate strokes, not gradients.
- **Palette:** `#3a4a4f` `#8a6f4d` `#c4763a` `#5d7a6a` `#b9b3a0` `#7c3f3a` `#1d2326` `#d7c38a`. Muted greens, greys and browns with unexpected orange, teal and rust strokes inside shadows and highlights.
- **Lighting:** Flat overcast or weak dawn light; colour temperature shifts carry the form more than value contrast.
- **Texture and surface:** Thick oil paint: short, loaded strokes in many directions, palette-knife patches, visible linen weave, colours not fully mixed.
- **Atmosphere and post-processing:** Soft atmospheric haze; optional linen-weave overlay. No sharp digital effects.
- **Camera and framing:** Fixed isometric-like view, about 35 to 45 degrees down, long lens or orthographic.
- **UI and typography:** Painted portrait frames and dark text panels with rough brushed edges; dialogue runs in a tall text column. Body text is a bookish serif, headings are tall condensed sans capitals, and skill-check numbers are small plain numerals. Text is off-white `#b9b3a0` on near-black `#1d2326`, with orange `#c4763a` and grey-green `#5d7a6a` accents.
- **VFX and motion:** Sparse effects: drifting haze, rain and cigarette smoke painted as soft strokes, with no impact flashes. Character motion is slow, heavy and realistic, mostly walking and idle gestures.

## Fits

- **Genres:** `detective-mystery`, `rpg`, `exploration`, `puzzle`
- **Moods:** melancholic, bleak, introspective
- **Settings:** decaying harbour district, post-revolution city, run-down hostel, winter coastline

## Godot recipe

### Assets

Worn urban packs (tenements, harbours, offices, streets) at realistic scale, viewed from above at an angle. Loosen the geometry slightly: jitter vertices by a few centimetres in a generator script (`MeshDataTool`) so lines are unsteady. Repaint every texture in a generator script (`Image`) as thick oil: quantise albedo to the muted palette, then stamp short loaded strokes in random directions, with occasional orange, teal or rust strokes placed inside shadows and highlights, and leave colours unmixed. Add a palette-knife patch layer and a linen-weave tile. Generate a stroke height map and turn it into a normal map.

### Materials

Write `style/oil_patch.gdshader`. Its `light()` takes `dot(NORMAL, LIGHT) * ATTENUATION` from the directional light plus a grey-green ambient uniform, then maps it to five to eight tone patches: instead of a ramp, use a cell noise (Voronoi cells of stroke size in UV or triplanar space, computed in `fragment()` and passed on) to pick a random offset per cell before quantising, so neighbouring cells land on different tones and transitions are made of separate strokes. Shift hue between warm and cool across the steps instead of darkening much. Use the stroke normal map (`NORMAL_MAP`) for a weak `SPECULAR_LIGHT` that catches paint ridges. Keep the `Environment` ambient energy low, since the ambient lives in the shader. No outline.

### Lighting and atmosphere

Flat overcast: a weak `DirectionalLight3D` with very soft shadows (`light_angular_distance`) at low `shadow_opacity`, strong gradient ambient in grey-green. Bake a `LightmapGI`. Soft pale grey `Environment` fog. SSAO low. No reflection probes of note. Fixed `Camera3D` 35 to 45 degrees down, orthogonal projection or a long lens. On the Mobile renderer: soften shadows with `shadow_blur` instead of the angular size, and leave SSAO off.

### Post-processing

A Kuwahara full-screen pass (radius 4 to 5 px): a `QuadMesh` in front of the camera whose spatial shader reads `hint_screen_texture`. After it, a linen-weave multiply at low strength in a `ColorRect` shader on a `CanvasLayer`. `Reinhard` tonemapping, `adjustment_saturation` 0.9, no glow, no sharpening, no chromatic aberration. TAA or SMAA. On the Mobile renderer: SMAA.

### UI and effects

Painted portrait frames and dark text panels with rough brushed edges (`StyleBoxTexture`); dialogue in a tall `RichTextLabel` column. Body from a bookish serif such as Libre Baskerville or Spectral; headings in tall condensed capitals such as Oswald Light. `#b9b3a0` on `#1d2326`, accents `#c4763a` and `#5d7a6a`. Effects are sparse: drifting haze, rain and cigarette smoke as soft stroke-textured alpha-blended particle quads; no impact flashes.

## Do / Do not

Do:

- Place complementary accent strokes inside shadows.
- Vary stroke direction by patch.
- Let under-colour show between strokes.
- Use a fixed high three-quarter view.

Do not:

- Do not align all strokes into flowing swirls with dark contours; that reads as `076`.
- Do not use small soft dabs in bright daylight colours; that reads as `075`.
- Do not use ordered directional strokes on dramatic low-key 3D; that reads as `024`.
- Do not smooth the paint into gradients; that reads as `026`.

## Nearest styles

- `076` Swirling impasto: strokes here are short, run in many directions and have no contour line, in muted greens, greys and browns; `076` has long flowing swirls, dark brush contours and strong blue and yellow.
- `075` Impressionist broken colour: this style is dull and dark under overcast light; `075` is bright, sunny and pastel, with no dark shadows.
- `024` Brush-textured 3D drama: paint here is thick, strokes run in every direction and many unmixed hues sit side by side; `024` has thinner, ordered strokes that follow the form, in a teal and orange scheme.
