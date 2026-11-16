# Silhouette fog monochrome

Reference works: Limbo.

## References

- *Limbo* (2010), Playdead, video game. https://en.wikipedia.org/wiki/Limbo_(video_game)
- *Inside* (2016), Playdead, video game. https://en.wikipedia.org/wiki/Inside_(video_game)
- *Nosferatu* (1922), F. W. Murnau, silent film. https://en.wikipedia.org/wiki/Nosferatu

## Visual definition

- **Shape language and proportions:** A small child figure and simple hazards (spider legs, saws, crates, ropes) as solid black silhouettes. Forest, industrial and rooftop scenery in layered silhouette planes.
- **Line and outline:** No line. Foreground objects are solid black shapes.
- **Shading model:** None on the foreground. Background layers are flat greys that get lighter and blurrier with distance.
- **Palette:** `#000000` `#1c1c1c` `#5a5a5a` `#9a9a9a` `#d8d8d8` `#ffffff`. Greyscale only. The only pure white is the figure's eyes and a few light sources.
- **Lighting:** Back-lit fog: a soft bright area behind the scene; light shafts between trees.
- **Texture and surface:** Film grain and soft dust. No surface texture on silhouettes.
- **Atmosphere and post-processing:** Heavy vignette, grain, flicker, depth blur on near and far layers, soft glow in the light area.
- **Camera and framing:** Side-on, orthographic or long lens, with parallax layers.
- **UI and typography:** No HUD panels. Prompts are small soft-edged white text or a single white glyph in the fog. Type is a thin plain sans or a slightly worn light serif in white `#ffffff` or light grey `#d8d8d8`, with the same blur and flicker as the frame; counters, if any, are small white tally marks or numerals.
- **VFX and motion:** Dust motes, falling ash, water splashes and sparks appear as black or soft white specks; deaths are abrupt breaks of the silhouette with no colour. Motion is weighty and physical, with realistic ragdoll and rope swing, and long stillness broken by sudden lethal snaps.

## Fits

- **Genres:** `platformer`, `puzzle`, `survival-horror`, `stealth`, `exploration`, `soulslike`
- **Moods:** bleak, eerie, lonely
- **Settings:** dark forest, abandoned factory, rain-swept rooftops, flooded ruins

## Godot recipe

### Assets

Everything in the play plane is a silhouette, so models need a readable outline and nothing else: a small child figure, spider legs, saws, crates, ropes, trees, machinery, rooftops. Any pack works once materials are replaced by black. Build background planes as layered silhouettes at increasing depth. Ropes and ragdolls need real physics set-ups: joints, a rope of linked `RigidBody3D` pieces, `PhysicalBone3D` bones on the figure's `Skeleton3D`. Add two small emissive white eyes to the figure.

### Materials

Foreground and gameplay objects use an unshaded `StandardMaterial3D`, pure black. Background layers use a second unshaded material whose grey value is set per layer, lighter with distance (`#1c1c1c`, `#5a5a5a`, `#9a9a9a`, `#d8d8d8`). The fog backdrop is an unshaded shader with a gradient above 1 in value and a soft bright area. Light shafts between trees are soft additive quads (`blend_add`) in grey-white. Eyes and the few light sources are unshaded white above the glow threshold. No lighting and no shadow casting; the opaque layers still write depth so the depth-of-field blur works.

### Lighting and atmosphere

No lights and no shadows. Depth comes from layer grey values, optionally reinforced with the `Environment`'s depth fog in light grey so mid layers fade automatically (unshaded materials still receive fog). No SSAO or probes. Side-on camera with slow drift.

### Post-processing

The frame treatment is heavy and is what separates this from a clean cut-out look. Depth-of-field blur near and far from `CameraAttributesPractical`, focused on the play plane so near and far layers blur. Glow with a low HDR threshold and high bloom for a soft glow in the light area. Adjustments saturation 0 as a guard. A `ColorRect` on a `CanvasLayer` with a `canvas_item` shader reading `hint_screen_texture` adds film grain at high strength, a vignette of 0.5 to 0.6, exposure flicker of a few percent at irregular intervals and drifting soft dust specks. Tonemap `Filmic`. SMAA. On the Mobile renderer: the bright backdrop and wide glow band sooner in its 10-bit buffer, so keep the backdrop only slightly above 1 and let the strong grain hide the steps.

### UI and effects

No HUD panels. Prompts are small soft-edged white text or one white glyph in the fog: the theme's default font is a thin plain sans or a light worn serif such as Cormorant Light, with a white `LabelSettings` shadow at zero offset and a few pixels' size so the text shares the frame's blur. Counters, if any, are tally marks. Particles are black or soft white specks: dust motes, ash, water splashes, sparks. Deaths break the silhouette into `RigidBody3D` pieces with no colour. Use ragdoll and rope physics and long stillness.

## Do / Do not

Do:

- Render the play layer as solid black.
- Lighten and blur layers with distance.
- Add grain, flicker and a heavy vignette.
- Keep eyes and lamps as the only pure white.

Do not:

- Do not add a coloured glowing backdrop; that reads as `058`.
- Do not light surfaces with modelled grey gradients; that reads as `068`.
- Do not use hard two-value threshold with a colour accent; that reads as `069`.
- Do not add coloured glows and painted detail; that reads as `027`.

## Nearest styles

- `058` Shadow-puppet cut-out: `058` sets black cut-outs against a glowing coloured backdrop; this style has only grey fog behind them, with grain and blur and no colour.
- `068` Film noir hard light: `068` lights real surfaces, so brick, faces and wet streets show in greys; this style keeps every foreground object a solid black shape with no interior detail.
- `065` Flat-vector stage light: `065` has clean hard-edged flat shapes in blue-grey darkness with yellow light; this style is colourless, soft and grainy, with blurred fog layers and a paler background.
