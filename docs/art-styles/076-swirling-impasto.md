# Swirling impasto

Reference works: Vincent van Gogh; Loving Vincent.

## References

- *The Starry Night* (1889), Vincent van Gogh, oil painting. https://en.wikipedia.org/wiki/The_Starry_Night
- *Wheatfield with Crows* (1890), Vincent van Gogh, oil painting. https://en.wikipedia.org/wiki/Wheatfield_with_Crows
- *Cafe Terrace at Night* (1888), Vincent van Gogh, oil painting. https://en.wikipedia.org/wiki/Café_Terrace_at_Night
- *Loving Vincent* (2017), Dorota Kobiela and Hugh Welchman (BreakThru Films), oil-painted animated film. https://en.wikipedia.org/wiki/Loving_Vincent
- *Bedroom in Arles* (1888), Vincent van Gogh, oil painting. https://en.wikipedia.org/wiki/Bedroom_in_Arles

## Visual definition

- **Shape language and proportions:** Simplified, slightly warped forms: leaning buildings, flame-like cypress trees, rolling hills, a sky made of spirals and halos. Perspective is steep and a little wrong.
- **Line and outline:** Dark blue or black contour strokes around major objects (roofs, trees, furniture), drawn with the brush.
- **Shading model:** Little tonal modelling. Form is shown by stroke direction and by a few colour steps.
- **Palette:** `#1f3b7a` `#f2c12e` `#2e6f8e` `#e07b2a` `#3f7a3a` `#f5e6a8` `#16203a`. Strong complementary pairs: deep blue with chrome yellow, orange with blue, green with red-brown.
- **Lighting:** Night skies with haloed stars and lamps, or blazing daylight fields.
- **Texture and surface:** Thick impasto: long, directional, rhythmic strokes laid side by side, following contours of objects and swirling in the sky; ridges of paint catch the light.
- **Atmosphere and post-processing:** Full-frame stroke-flow pass and paint relief lighting.
- **Camera and framing:** Slightly high viewpoint over a village or field, or a tilted interior.
- **UI and typography:** Panels are slabs of thick paint in deep blue `#1f3b7a` or night navy `#16203a` with a brushed chrome-yellow `#f2c12e` border, and icons are simple objects drawn with dark brush contours. Text is a heavy hand-painted brush lettering with uneven strokes, and numbers are fat yellow brush numerals with a dark blue contour.
- **VFX and motion:** Effects are made of strokes: stars and lamps pulse with concentric ringed halos, wind and magic show as curling ribbons of parallel strokes, and impacts are bursts of short radiating yellow and orange strokes. The whole surface flows slowly along its stroke directions, and characters move on twos or threes like repainted frames.

## Fits

- **Genres:** `exploration`, `action-adventure`, `detective-mystery`, `rpg`, `puzzle`
- **Moods:** restless, dreamlike, intense
- **Settings:** Provençal village, wheat fields, starry night hillside, café terrace

## Godot recipe

### Assets

Simplified, slightly warped forms: leaning buildings, flame-shaped cypress trees, rolling hills, a few pieces of furniture. Warp pack models with a bend and shear in a generator script (`MeshDataTool`, moving vertices, then saved with `ResourceSaver`) and steepen the scene's perspective with a wide `Camera3D` field of view. Remove textures and assign a few strong colours per object. The sky is built: a sky texture and flow map with spirals and haloed stars, generated in a generator script with `Image`. Also generate a long-stroke brush tile and a matching height map.

### Materials

Write `impasto.gdshader`, a spatial shader. `light()` gives each surface two or three colour steps from `dot(NORMAL, LIGHT)` times `ATTENUATION` (little tonal modelling) in complementary pairs: blue shadow under yellow light, orange against blue. The stroke tile is sampled along the UV direction so strokes follow object contours, and it scrolls slowly along that direction with `TIME` so the surface appears to flow. Its height map, turned into a normal map in the generator script, goes to `NORMAL_MAP`, and `light()` adds a tight highlight to `SPECULAR_LIGHT` so paint ridges catch the light. The sky is a `shader_type sky;` shader driven by the flow map so strokes swirl. Dark contour strokes on roofs, trees and furniture are an outline shell in `next_pass`: a shader with `render_mode unshaded, cull_front` that pushes vertices along `NORMAL`, in `#16203a`, with width broken by a brush-noise texture read in `vertex()`.

### Lighting and atmosphere

Either a night scene (dim blue `DirectionalLight3D`, emissive stars and lamps with `OmniLight3D` nodes) or blazing daylight (strong warm sun). Soft shadows through `shadow_blur`, low `shadow_opacity`. Flat coloured ambient in deep blue or warm yellow: `Environment` ambient source colour. No fog, no SSAO.

### Post-processing

A full-screen `QuadMesh` in front of the camera with a spatial shader reading `hint_screen_texture` applies an anisotropic Kuwahara filter before tonemapping (kernel stretched along the local structure direction, radius about 6 px) to turn remaining detail into long strokes. A `ColorRect` on a `CanvasLayer` with a `canvas_item` shader reading `hint_screen_texture` then computes a relief light from the luminance gradient and adds a thin highlight and shadow to stroke edges. Tonemap Linear, adjustments saturation 1.15, light glow with an HDR threshold above 1 so only emissive stars and lamps get halos. No blur or grain.

### UI and effects

Panels are slabs of thick paint in `#1f3b7a` or `#16203a` with a brushed chrome-yellow border, a `StyleBoxTexture` 9-sliced from a painted slab in the `Theme`; icons have dark brush contours. Heavy brush lettering from a face such as Rock Salt or Permanent Marker, imported as a `FontFile` and set as the theme default font; fat yellow numerals through `LabelSettings` with a dark blue outline colour and a large outline size. Effects are strokes: concentric ring halos pulsing around stars and lamps (billboard quads with a ring stroke texture, scaled by a `Tween`), curling ribbons of parallel strokes for wind and magic (`GPUParticles3D` trails with the stroke texture), radiating yellow and orange strokes on impact. Step characters on twos or threes: `AnimationPlayer` in manual process mode, advanced 12 or 8 times per second by script.

## Do / Do not

Do:

- Make strokes long, parallel and rhythmic along a flow field.
- Swirl the sky around stars.
- Use blue and yellow complementary contrast.
- Add brushed dark contours to main objects.

Do not:

- Do not use short soft dabs in pastel daylight; that reads as `075`.
- Do not use uniform dots; that reads as `077`.
- Do not mute the palette and randomise stroke direction; that reads as `028`.
- Do not smooth the paint relief away.

## Nearest styles

- `075` Impressionist broken colour: this style has dark brushed contours, long swirling strokes and strong blue-and-yellow contrast; `075` has no contours and uses short soft dabs of pastel colour.
- `028` Expressionist oil isometric: this style uses strong blue, yellow and orange with dark contours and strokes that flow in one rhythm; `028` is muted green, grey and brown with no contours and strokes in many directions.
- `077` Pointillist dot field: this style draws dark contours and lays colour in long ridged strokes of a few distinct steps; `077` has no contours and covers smooth forms with small round dots that blend at a distance.
