# Layered flat-colour wilderness

Reference works: Firewatch.

## References

- *Firewatch* (2016), Campo Santo, video game. https://en.wikipedia.org/wiki/Firewatch
- *Alto's Adventure* (2015), Snowman and Harry Nesbitt, video game. https://en.wikipedia.org/wiki/Alto's_Adventure
- *A Short Hike* (2019), Adam Robinson-Yu, video game. https://en.wikipedia.org/wiki/A_Short_Hike
- *Federal Art Project posters* (1935-1943), Works Progress Administration, screen-printed posters. https://en.wikipedia.org/wiki/Federal_Art_Project

## Visual definition

- **Shape language and proportions:** Landscapes simplified into overlapping silhouette layers: ridge lines, tree lines, rock towers. Trees are simple cone and trunk shapes; rocks are angular blocks.
- **Line and outline:** No outline.
- **Shading model:** Each depth layer is one flat colour. Near objects have two to four flat tones with hard edges.
- **Palette:** `#f25c2a` `#f7a531` `#7a2f5a` `#2b1e3f` `#f9d9a0` `#3f7a6a` `#1c4a5a`. A sunset-style ramp from deep purple foreground through magenta and orange to pale yellow sky, or a green-teal variant for daytime.
- **Lighting:** Low sun behind the layers; strong colour-graded atmospheric perspective.
- **Texture and surface:** Almost none. Flat fills with a few simple shapes for rock faces and tree shadows.
- **Atmosphere and post-processing:** Heavy coloured distance fog that shifts hue with depth; soft sun glow.
- **Camera and framing:** Wide vista from a height, 28 to 35 mm equivalent, horizon in the middle third.
- **UI and typography:** Panels are flat, borderless colour blocks taken from the sunset ramp, and icons are simple one-colour silhouettes. Type is a bold condensed sans or wide display capitals in the manner of 1930s national park posters, in pale yellow on deep purple. Numbers are plain flat numerals in orange or pale yellow.
- **VFX and motion:** Effects stay flat: smoke is stacked hard-edged puffs, fire is two or three orange shapes, and ash, dust and tiny bird silhouettes drift across the layers. Motion is smooth and unhurried, with slow tree sway and distant layers that slide in parallax.

## Fits

- **Genres:** `exploration`, `detective-mystery`, `survival-craft`, `action-adventure`, `sports`
- **Moods:** wistful, calm, lonely
- **Settings:** national park forest, mountain range, canyon country, alpine slopes

## Godot recipe

### Assets

Landscapes are stacks of silhouette layers: ridge lines, tree lines, rock towers. Generate ridge meshes in a generator script from `FastNoiseLite` profiles with `SurfaceTool`, and scatter simple trees (a cone on a trunk) and angular rock blocks with `MultiMeshInstance3D`. Low-poly nature packs work once textures are removed. Near objects get two to four flat tones as separate material slots or vertex-colour regions with hard boundaries; far layers need no detail. Place layers at clearly separated depths so the depth ramp bands them.

### Materials

Write `flat_layer.gdshader`, a spatial shader with `render_mode unshaded`. `fragment()` outputs a flat base colour; for near objects, a `step`-based split of the dot product between the world normal and a light-direction global uniform into two to four flat tones with hard edges. Then, in place of the engine's fog, apply a depth ramp: compute normalised view depth from `-VERTEX.z` and sample a 256x1 gradient texture (deep purple foreground, magenta, orange, pale yellow at the horizon), mixing the surface colour fully to the ramp colour over a short range so each distant layer becomes exactly one flat colour. The ramp texture and the light direction are global shader uniforms (`global uniform`, declared in the project's shader globals and set with `RenderingServer.global_shader_parameter_set`), so a green-teal daytime ramp can be swapped in. Shadows are not received by the unshaded shader; turn casting off.

### Lighting and atmosphere

One low `DirectionalLight3D` behind the layers whose direction a script copies into the global light-direction uniform each frame for the tone split on near objects; its shadows off. No `Environment` fog, since the shader ramp replaces it. The sky is the top of the same ramp, drawn by a `shader_type sky;` shader that samples the ramp by `EYEDIR.y` and adds a soft-edged sun disc around `LIGHT0_DIRECTION`. No SSAO, GI or reflection probes.

### Post-processing

Glow with a high HDR threshold so only the sun disc (above 1 in the sky shader) glows softly. Tonemap Linear; no grain, no depth-of-field blur. To keep layer edges crisp use MSAA 4x. A parallax camera rig script moves far layers slowly.

### UI and effects

Panels are flat, borderless colour blocks (`StyleBoxFlat`) sampled from the ramp; icons are one-colour silhouettes. Import bold condensed or wide display capitals in the national-park-poster manner, such as Bebas Neue or Staatliches, as the theme default `FontFile`, in `#f9d9a0` on `#2b1e3f`; plain flat numerals in orange or pale yellow. Effects stay flat and hard-edged: smoke as stacked opaque puffs (mesh discs), fire as two or three orange shapes that swap, ash and dust as tiny quads, bird silhouettes drifting across layers. Trees sway slowly in `vertex()`.

## Do / Do not

Do:

- Reduce the landscape to flat-colour depth layers.
- Drive colour by depth through a fixed ramp.
- Keep the foreground darkest and the sky lightest.
- Use simple cone trees and angular rocks.

Do not:

- Do not use watercolour texture and pale washes; that reads as `025`.
- Do not use only a handful of flat colours with cut-paper figures; that reads as `064`.
- Do not add smooth sand shading and sparkle; that reads as `061`.
- Do not go dark with theatrical spotlights; that reads as `065`.

## Nearest styles

- `064` Mid-century cut-paper poster: this style stacks many depth layers with coloured haze between them, along a full sunset ramp; `064` is a single flat sheet of a few paper colours with no depth haze.
- `061` Soft-gradient minimal desert: near objects here have hard-edged flat tones in strong sunset colour; `061` has smooth soft gradients across its dunes.
- `066` Faceted low-poly gradient: fog here flattens each distant layer to one colour; `066` shows a separately shaded facet on every triangle.
