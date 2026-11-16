# Expressionist painted set

Reference works: The Cabinet of Dr. Caligari.

## References

- *The Cabinet of Dr. Caligari* (1920), Robert Wiene (sets by Hermann Warm, Walter Reimann and Walter Rohrig), silent film. https://en.wikipedia.org/wiki/The_Cabinet_of_Dr._Caligari
- *Metropolis* (1927), Fritz Lang, silent film. https://en.wikipedia.org/wiki/Metropolis_(1927_film)
- *The Golem: How He Came into the World* (1920), Paul Wegener and Carl Boese, silent film. https://en.wikipedia.org/wiki/The_Golem:_How_He_Came_into_the_World
- *Vincent* (1982), Tim Burton, stop-motion short film. https://en.wikipedia.org/wiki/Vincent_(1982_film)

## Visual definition

- **Shape language and proportions:** Stage sets with no right angles: walls lean, doors are trapezoids, windows are jagged shards, chimneys and lamp posts bend, paths zig-zag. Flat scenery panels with forced perspective.
- **Line and outline:** Bold painted black lines on set surfaces: outlines of windows, spiky grass, radiating floor stripes.
- **Shading model:** Light and shadow are painted on the sets as hard-edged black and white shapes; real lighting is flat and frontal. Faces are white with dark eye make-up.
- **Palette:** `#0c0c0c` `#f1ead6` `#6b6b63` `#2f3a35` `#b5a878` `#3a2f2a`. Black, white and grey, optionally tinted per scene in one colour (sepia, green or blue) like tinted film stock.
- **Lighting:** Flat front light; the drama comes from painted shadow wedges and painted light pools.
- **Texture and surface:** Painted cloth flats and plaster with visible rough brush strokes; film scratches and flicker.
- **Atmosphere and post-processing:** Monochrome with a single tint, iris vignette, grain, flicker, low frame rate.
- **Camera and framing:** Static, frontal, theatrical framing; often an iris mask.
- **UI and typography:** Silent-film intertitle cards: black panels with a jagged hand-painted white border, text in a crooked, angular hand-lettered display face whose letters lean and vary in size. Counters use the same uneven painted numerals in bone white `#f1ead6`, icons are spiky painted silhouettes, and the whole UI takes the scene's single tint.
- **VFX and motion:** Effects are painted or theatrical: jagged white starburst shapes on impact, flat cut-out smoke, iris-in and iris-out transitions, film scratches and flicker. Characters move like stage actors at a low frame rate, creeping along walls with long held poses and sudden jerky gestures.

## Fits

- **Genres:** `survival-horror`, `detective-mystery`, `stealth`, `puzzle`, `exploration`
- **Moods:** uneasy, feverish, theatrical
- **Settings:** crooked hill town, asylum, travelling fairground, rooftops at night

## Godot recipe

### Assets

Build sets from scratch as painted stage flats: a generator script builds wall, door and window panels with `SurfaceTool` as skewed quads and trapezoids with no right angles, jagged window shards, bent chimneys and lamp posts, zig-zag paths, and saves them for a scene arranged with forced perspective. Paint their textures in the same generator script with `Image`: rough brush-stroked plaster in greys, bold black outlines round windows, spiky grass, radiating floor stripes, and, most important, hard-edged painted shadow wedges and white light pools, saved with `save_png`. Characters are ordinary rigged models (`.glb`) with white faces and dark eye make-up painted into the face texture.

### Materials

Sets use a `StandardMaterial3D` with `shading_mode` unshaded and the painted textures, written as `.tres`: light and shadow are paint, so the surface must not respond to real light. Characters use a `StandardMaterial3D` with `diffuse_mode` Lambert Wrap and `specular_mode` Disabled, or a short spatial shader with `render_mode shadows_disabled, specular_disabled` whose `light()` keeps contrast very low under the frontal light. Turn `cast_shadow` off on every set mesh: no real cast shadows on the sets. Keep textures at 2048 px with `texture_filter` linear with mipmaps, so brush strokes show.

### Lighting and atmosphere

Flat front light only: one `DirectionalLight3D` aimed along the camera's view direction for characters, `shadow_enabled` off, and a bright flat ambient in the `Environment` (ambient source colour, a light grey `ambient_light_color`). No fog, SSAO, SDFGI, `LightmapGI` or `ReflectionProbe`. Stage the `Camera3D` frontally, as in a theatre.

### Post-processing

Monochrome with one tint: in each scene's own `Environment`, adjustments on with saturation 0, and a colour-correction `GradientTexture1D` running from near black through the scene tint (sepia, green or blue) to bone white `#f1ead6`. Tonemap Linear. On a `CanvasLayer` above the world, a `ColorRect` with a `canvas_item` shader reading `hint_screen_texture` adds heavy grain, vertical scratches, brightness flicker and an iris: a dark circular mask with a hard edge closing the corners, whose radius uniform a `Tween` animates for iris-in and iris-out transitions. Low frame rate: set each `AnimationPlayer` to manual process mode and call `advance()` 12 to 16 times per second from a script, and optionally render the world in a `SubViewport` set to update once, re-triggered at the same rate, so the whole frame holds.

### UI and effects

Intertitle cards: `Panel` nodes styled by the `Theme` with a black `StyleBoxTexture` that 9-slices a jagged hand-painted white border. Lettering from a crooked angular display face such as Butcherman or New Rocker imported as a `FontFile` and set as the theme default font; per-character rotation and size variation come from a `RichTextLabel` with a custom `RichTextEffect` that sets each character's transform; numerals in `#f1ead6` through `LabelSettings`. Icons are spiky painted silhouettes in `TextureRect` nodes. The UI takes the scene tint through the `modulate` colour of its root `Control`. Effects are theatrical: jagged white starburst textures on billboard `QuadMesh` quads with an unshaded alpha-scissor material on impact, flat cut-out smoke on quads. Actors creep along walls, hold poses and gesture abruptly.

## Do / Do not

Do:

- Lean and skew every wall and opening.
- Paint shadows and light shapes onto the sets.
- Keep real lighting flat and frontal.
- Tint the monochrome image with one colour.

Do not:

- Do not use real hard-light photography on normal architecture; that reads as `068`.
- Do not use 3D puppets with smooth shading and colour accents; that reads as `049`.
- Do not threshold to two values with a colour spot; that reads as `069`.
- Do not fragment objects into overlapping transparent planes; that reads as `078`.

## Nearest styles

- `068` Film noir hard light: this style paints its shadows and bold black lines onto crooked flat sets under flat front light; `068` photographs normal, upright architecture with real hard light, real cast shadows and no drawn lines.
- `049` Gothic stop-motion puppet: this style is tinted black and white with flat painted scenery and live actors in white make-up; `049` shows solid miniature puppets and sets in blue-violet with orange or green accents, lit by real stage light with smooth shading.
- `078` Analytic cubist facets: here objects stay whole, only leaning and skewed, with painted light and shadow shapes on them; `078` breaks each object into overlapping ochre-grey facets seen from several viewpoints.
