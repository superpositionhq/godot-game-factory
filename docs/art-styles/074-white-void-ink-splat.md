# White void ink-splat

Reference works: The Unfinished Swan.

## References

- *The Unfinished Swan* (2012), Giant Sparrow, video game. https://en.wikipedia.org/wiki/The_Unfinished_Swan
- *Elegy to the Spanish Republic* (1948-1967), Robert Motherwell, painting series. https://en.wikipedia.org/wiki/Robert_Motherwell
- *White on White* (1918), Kazimir Malevich, oil painting. https://en.wikipedia.org/wiki/White_on_White

## Visual definition

- **Shape language and proportions:** A normal 3D world (garden, walls, statues, furniture) that is entirely white and unshaded, so it is invisible until black paint is thrown onto it. Shapes are revealed only where splats land.
- **Line and outline:** No outline. Edges appear where a black splat wraps over a corner.
- **Shading model:** None. Surfaces are pure white; paint is pure black.
- **Palette:** `#ffffff` `#0a0a0a` `#f2f2f2` `#e6c84b` `#d9d9d9`. White and black, with a single rare gold-yellow accent object.
- **Lighting:** None visible. No shadows in the pure variant.
- **Texture and surface:** Paint splats: round blobs with radiating spikes, satellite drops and drips running down vertical surfaces.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** First-person, 70 to 80 degree field of view.
- **UI and typography:** Almost no UI: a small black dot reticle and, where text is needed, a few words in a thin storybook serif set in black directly on the white, with no panels or frames. Counters are plain black numerals, and the gold-yellow `#e6c84b` is used only to mark a goal or collectible.
- **VFX and motion:** Paint balls fly in a visible arc and burst into a splat with spikes, satellite drops and drips that run down walls for a moment before they stop. No glow, smoke or sparks; motion is calm and physical, and splats stay where they land.

## Fits

- **Genres:** `exploration`, `puzzle`, `platformer`, `stealth`
- **Moods:** quiet, curious, eerie
- **Settings:** storybook garden, empty castle, hedge maze, unfinished kingdom

## Godot recipe

### Assets

A normal, readable 3D world: garden, walls, statues, furniture, trees. Any realistic or stylised pack works, because all materials are replaced. Every mesh needs a second, non-overlapping UV set (UV2: turn on the lightmap UV unwrap in each model's import options, or call `ArrayMesh.lightmap_unwrap()` in a generator script) and a `StaticBody3D` with a trimesh collision shape, since paint is stored per object in texture space. A generator script also bakes, per mesh, a position map: an `Image` in UV2 space whose pixels hold each texel's object-space position, saved as a float texture. Generate splat stamps in a generator script with `Image`: round blobs with radiating spikes, satellite drops and drip streaks. One rare object per area is gold-yellow.

### Materials

Write `splat_white.gdshader`, a spatial shader with `render_mode unshaded, shadows_disabled`. It outputs pure white `#ffffff` with no lighting at all, then multiplies by a paint mask sampled at `UV2`, where black marks painted surface. The mask is the texture of a per-object `SubViewport` that is never cleared and updates only when told to. A script paints into it when a paint ball lands: it sets the hit point and normal on a `ColorRect` inside that viewport whose `canvas_item` shader reads the position map and draws the splat stamp, projected along the hit normal, wherever a texel lies near the hit, then asks the viewport to update once. Drips extend the mask downward on vertical surfaces for a second (a few more updates with the stamp moved down) and then stop. Threshold the mask so paint is pure `#0a0a0a` with a crisp edge. Turn `cast_shadow` off on every mesh. The accent object uses a `StandardMaterial3D` with `shading_mode` unshaded in `#e6c84b`.

### Lighting and atmosphere

None. No lights, shadows, fog, SSAO or `ReflectionProbe`; the `Environment` background is the colour `#ffffff`, the same white as the surfaces, so unpainted geometry is invisible. An optional variant adds a `DirectionalLight3D` with faint shadows later in the game, with the white shader switched to a lit one whose `light()` writes only a light grey in shadow.

### Post-processing

None. Tonemap Linear with exposure 1 and white 1 so white stays exactly `#ffffff`, no glow, no vignette, no outline pass: edges must appear only where paint wraps a corner. MSAA 3D 4x. No value above 1 anywhere: no emission, no HDR highlights.

### UI and effects

Almost no UI: a small black dot reticle as a centred `TextureRect`, and where words are needed a few in a thin storybook serif such as Cormorant Garamond or Libre Baskerville imported as a `FontFile`, black `Label` text on white with no panel (`StyleBoxEmpty` in the `Theme`). Plain black numerals. Gold-yellow marks only a goal or collectible. Paint balls are black unshaded `SphereMesh` bodies (`RigidBody3D`) on a visible ballistic arc; on impact, spawn a short burst of small black droplet bodies that each stamp a satellite dot where they land. No glow, smoke or sparks, and splats never fade.

## Do / Do not

Do:

- Keep all unpainted surfaces pure white with no shading.
- Reveal form only with black paint splats.
- Give splats spikes, droplets and drips.
- Keep paint sparse: most of the frame stays blank white, with splats only where the player has thrown paint.

Do not:

- Do not add ambient occlusion or shading on the white; that reads as `063` or `035`.
- Do not draw pencil lines and hatching; that reads as `073`.
- Do not threshold a lit scene to black and white; that reads as `069`.
- Do not use red faceted figures; that reads as `063`.

## Nearest styles

- `063` White-and-red faceted minimal: here the white world has no shading at all and is seen only through black paint splats; `063` shows its white rooms through soft corner shading and fills them with glossy red faceted figures.
- `073` Graphite pencil sketch: this style has no drawn lines and no greys, only black splats on blank white; `073` outlines and shades every object in grey pencil.
- `069` Selective-colour ink noir: this frame is almost all white with scattered black splats; `069` is almost all black, with white shapes cut out by light and one spot of colour.
