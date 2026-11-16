# Mecha panel-line cel

Reference works: Mobile Suit Gundam.

## References

- *Mobile Suit Gundam* (1979), Nippon Sunrise (Yoshiyuki Tomino), animated TV series. https://en.wikipedia.org/wiki/Mobile_Suit_Gundam
- *Mobile Suit Gundam: Char's Counterattack* (1988), Sunrise, animated film. https://en.wikipedia.org/wiki/Mobile_Suit_Gundam:_Char's_Counterattack
- *Neon Genesis Evangelion* (1995), Gainax, animated TV series. https://en.wikipedia.org/wiki/Neon_Genesis_Evangelion
- *The Super Dimension Fortress Macross* (1982), Studio Nue and Tatsunoko Production, animated TV series. https://en.wikipedia.org/wiki/Super_Dimension_Fortress_Macross

## Visual definition

- **Shape language and proportions:** Humanoid machines built from large armour blocks with chamfered corners, vents, thrusters and antenna fins. Clear separation between armour plates and dark inner frame.
- **Line and outline:** Black outline on silhouettes plus thin panel lines dividing armour plates. Lines are straight and mechanical.
- **Shading model:** Two flat bands on armour, with a third hard white highlight streak on some edges.
- **Palette:** `#f2f2f2` `#1d3fa6` `#d62828` `#f6c90e` `#3a3f4b` `#9aa3ad` `#111111`. White armour with blue, red and yellow blocks; dark grey joints.
- **Lighting:** Single hard key in space or daylight; shadow shapes are large and simple.
- **Texture and surface:** None apart from panel lines, small warning marks and vent slots.
- **Atmosphere and post-processing:** Clean. Beam and thruster effects glow white-pink with bloom.
- **Camera and framing:** Low angle looking up for scale; long lens for poses.
- **UI and typography:** Cockpit-monitor UI: thin green or amber line frames, targeting brackets, range rings and angular gauges on dark grey. Text is a condensed stencil sans in capitals, like unit numbers and warning marks painted on armour; counters use blocky monospaced digits. Alerts are red blocks with yellow text; friendly markers are blue.
- **VFX and motion:** Pink-white beam shots, round layered explosion balls in flat pink, orange and white, thruster flares, drawn smoke trails and curving missile swarms. Machines move with weight: slow wind-up, hard stops and a held pose after each action, with a white streak sliding along armour edges.

## Fits

- **Genres:** `vehicle-combat`, `third-person-shooter`, `strategy`, `fighting`, `tower-defense`, `top-down-shooter`
- **Moods:** heroic, dramatic, militaristic
- **Settings:** space colony, orbital battlefield, desert military base, fortress city under attack

## Godot recipe

### Assets

Mecha kits and hard-surface robot packs with large armour blocks, vents, thrusters and antenna fins; or build machines from scratch in Blender background mode from chamfered boxes and export as `.glb`, which suits this style well. Separate armour plates from the inner frame as different material slots. Remove all PBR textures. Generate a panel-line texture per model in a generator script: straight thin lines along UV island borders and plate divisions, plus small warning marks and vent slots. In Blender, bake smoothed normals into vertex colour RGB and an edge curvature value into vertex colour alpha.

### Materials

Write `mecha_cel.gdshader`. In `light()`: one `step` on `ATTENUATION * dot(NORMAL, LIGHT)` for two flat bands with large simple shadow shapes, then a third term for a hard white highlight streak: threshold a narrow band of `dot(NORMAL, normalize(LIGHT + VIEW))` and mask it to chamfered edges with the baked curvature (vertex colour alpha, passed through a varying). Animate the streak position with a uniform set by script or `Tween` so it can slide along edges after an action. Multiply by the panel-line texture. Frame materials are flat `#3a3f4b` with the same bands. Outline: a `next_pass` shell (`cull_front`, `unshaded`) in `#111111`, constant width, pushing vertices along the smoothed normals from vertex colour RGB so hard corners do not split.

### Lighting and atmosphere

A single hard `DirectionalLight3D` key, hard shadows (`light_angular_distance` 0, `shadow_blur` 0, soft shadow filter quality set to hard in the project), 4096 directional shadow map size. In space scenes ambient colour is nearly black with a faint blue fill; in daylight use flat grey ambient. No fog, no SSAO, no GI. Backgrounds: a star field panorama sky or a flat colour background.

### Post-processing

Clean frame with glow reserved for beams and thrusters: emissive pink-white HDR colours (energy 4 or more) above an HDR threshold of 1.2. Tonemap Linear, MSAA 4x, no grain, no vignette. Use low camera angles and long lenses (low `fov`) for scale. On the Mobile renderer: its 10-bit buffer clips very bright values sooner, so use emission energy of about 2 and a short glow ramp to keep beams from banding.

### UI and effects

Cockpit-monitor UI on dark grey: thin green or amber line frames, targeting brackets, range rings and angular gauges drawn as textures or in a `Control`'s `_draw()` with `draw_line`, `draw_arc` and `draw_polyline`. Theme font from a condensed stencil face such as Saira Stencil One; counters in a monospaced face such as Share Tech Mono. Alerts are red blocks with yellow text. Effects: beam shots as stretched additive unshaded meshes with a white core, round layered explosion balls from flat pink, orange and white `SphereMesh` instances that a `Tween` scales and pops, thruster flares, flipbook smoke trails and missile swarms on curved paths (`Path3D` or script steering) with `GPUParticles3D` trails.

## Do / Do not

Do:

- Use single flat chamfers on armour edges.
- Separate plates with real gaps over a dark frame.
- Keep to white plus three primary blocks.
- Draw panel lines straight at 45 and 90 degrees.

Do not:

- Do not add weathering, scratches and hatching; that reads as `001`.
- Do not use organic costume shapes and many hues; that reads as `015`.
- Do not use smooth PBR metal; that reads as `013`.
- Do not round the forms into toy bricks with studs; that reads as `052`.

## Nearest styles

- `015` Two-tone fighting-anime cel: `015` shows organic characters in many strong colours with curved shadow shapes; this style shows mostly white machines with a few primary colour blocks and straight panel lines.
- `011` Clear-line adventure comic: `011` has no light or shadow, only one flat colour per surface; this style splits each armour plate into a lit tone and a shadow tone, with white highlight streaks on some edges.
- `098` Bauhaus primary geometry: `098` builds its forms from plain primary-coloured solids with no outline; this style draws a black outline and panel lines on every armour plate.
