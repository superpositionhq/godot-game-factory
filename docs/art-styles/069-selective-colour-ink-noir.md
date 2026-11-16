# Selective-colour ink noir

Reference works: Sin City.

## References

- *Sin City* (2005), Robert Rodriguez and Frank Miller, live-action film. https://en.wikipedia.org/wiki/Sin_City_(film)
- *Sin City (comics)* (1991), Frank Miller (Dark Horse Comics), comic series. https://en.wikipedia.org/wiki/Sin_City
- *MadWorld* (2009), PlatinumGames, video game. https://en.wikipedia.org/wiki/MadWorld
- *Schindler's List* (1993), Steven Spielberg, live-action film. https://en.wikipedia.org/wiki/Schindler's_List

## Visual definition

- **Shape language and proportions:** Realistic figures and city settings reduced to stark graphic shapes: silhouettes with white rim shapes, rain as white streaks, blinds and bricks as white lines on black.
- **Line and outline:** Where a black form meets a black ground, a white keyline or rim separates them; where a white form meets white, a black line does. Lines are bold.
- **Shading model:** Two values only: pure black and pure white, with no greys. Shadow shapes are large and designed.
- **Palette:** `#000000` `#ffffff` `#c40000` `#f2d21b` `#1a1a1a`. Black and white plus one small area of a single saturated colour (red lips or dress, yellow skin, blue eyes).
- **Lighting:** Extreme hard side or back light; negative-space lighting where figures are white outlines on black.
- **Texture and surface:** None in tone. Rain streaks, brick lines and spatter are solid white or black marks.
- **Atmosphere and post-processing:** Hard threshold; selective colour mask; optional slight glow on white.
- **Camera and framing:** Dramatic low and high angles, strong perspective, silhouettes against light.
- **UI and typography:** Solid black panels with bold white borders, or the reverse, like comic caption boxes; icons are stark two-value silhouettes. Text is heavy hand-inked comic block capitals in white `#ffffff` on black; the one key colour, red `#c40000` or yellow `#f2d21b`, marks health, damage numbers and the selected item.
- **VFX and motion:** Blood, spatter and muzzle flashes are flat ink shapes in solid white or the one key colour; rain is white streaks, and a hit flips the frame to its negative for an instant. Animation is punchy, with strong held poses and fast smears between them.

## Fits

- **Genres:** `hack-and-slash`, `detective-mystery`, `third-person-shooter`, `fighting`, `stealth`, `action-adventure`
- **Moods:** brutal, lurid, hardboiled
- **Settings:** corrupt city at night, rain-soaked alleys, docks, seedy bar

## Godot recipe

### Assets

Realistic figures and city sets with strong silhouettes; detail is irrelevant, so mid-poly packs are fine. Remove all textures. Replace surface detail with marks that will survive a hard threshold: brick courses, blinds and rain as thin white line geometry or mask textures. Tag one element per scene (lips, a dress, eyes) with a selective-colour material. Design scenes for large shadow shapes, with lights placed by hand.

### Materials

Write `ink_noir.gdshader`. In `light()` each light adds `step(t, max(dot(NORMAL, LIGHT), 0.0) * ATTENUATION)` to `DIFFUSE_LIGHT`, so a pixel is pure white once any light reaches it and pure black otherwise; in `fragment()` a mask texture adds white marks on black (bricks, rain) through `EMISSION` and black marks on white by lowering `ALBEDO`. A rim term with a hard threshold (`step` on `1.0 - dot(NORMAL, VIEW)`, only where the light comes from behind) draws a white rim on the unlit side so black figures separate from black grounds. Selective-colour materials are unshaded and output the key colour (`#c40000` or `#f2d21b`) flat; being the only saturated pixels in the frame is the flag that post keeps them by. Shadows are cast without extra work.

### Lighting and atmosphere

Extreme hard side or back light: one `DirectionalLight3D` or `SpotLight3D`, hard shadows, no fill, ambient black. Back-lit set-ups make figures white outlines on black through the rim term. No fog, GI, SSAO or probes. Background black.

### Post-processing

A full-screen pass in the 3D scene, a `MeshInstance3D` with a 2x2 `QuadMesh` in front of the camera whose shader reads the screen, depth and normal-roughness textures, does three jobs. It thresholds luminance to exactly 0 or 1, so no grey remains. It adds bold keylines: at depth or normal edges, if both sides are black it draws a white line, and if both are white a black one. It passes saturated selective-colour pixels through untouched. Then optional glow at low intensity for a slight glow on white. Tonemap `Linear`, no grain. MSAA on geometry is fine, but the threshold runs last so edges stay hard. On the Mobile renderer: there is no normal-roughness texture, so find the keylines from the depth texture alone (depth jumps, plus normals rebuilt from neighbouring depths).

### UI and effects

Solid black panels with bold white borders or the reverse (`StyleBoxFlat`); stark two-value silhouette icons. Heavy inked block capitals from a comic face such as Bangers or Anton, white on black; the key colour marks health, damage numbers and the selected item. Effects are flat shapes: white or key-colour spatter flipbooks, white rain streaks from stretched particles, flat muzzle-flash shapes. A hit inverts the frame for one frame through a uniform on the full-screen material. Use strong held poses and fast smears.

## Do / Do not

Do:

- Threshold to pure black and white.
- Keep exactly one small selective colour.
- Use white keylines on black forms.
- Design large shadow shapes.

Do not:

- Do not keep grey gradients and film grain; that reads as `068`.
- Do not fill colour areas with muted flats; that reads as `010`.
- Do not use dot screentone for greys; that reads as `020`.
- Do not flood the frame with red; that reads as `008`.

## Nearest styles

- `010` Heavy-black gothic comic: `010` also has heavy black shadows, but fills the lit areas with muted flat colours; this style leaves them pure white and allows one small spot of strong colour.
- `020` Manga screentone monochrome: `020` is mostly white paper with fine ink lines and dot screentone for greys; this style is mostly black, with solid shapes and no dot tones.
- `068` Film noir hard light: `068` is photographic black and white with smooth grey gradients and film grain; this style has no greys, only solid black and white shapes with keylines.
