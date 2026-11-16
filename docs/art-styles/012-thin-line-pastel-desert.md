# Thin-line pastel desert

Reference works: Sable; Moebius.

## References

- *Sable* (2021), Shedworks, video game. https://en.wikipedia.org/wiki/Sable_(video_game)
- *Arzach* (1975), Moebius (Jean Giraud), comic. https://en.wikipedia.org/wiki/Arzach
- *The Incal* (1980), Alejandro Jodorowsky and Moebius, comic series. https://en.wikipedia.org/wiki/The_Incal
- *Fantastic Planet* (1973), Rene Laloux, animated film. https://en.wikipedia.org/wiki/Fantastic_Planet
- *Rollerdrome* (2022), Roll7, video game. https://en.wikipedia.org/wiki/Rollerdrome

## Visual definition

- **Shape language and proportions:** Vast empty landscapes with eroded rock arches, bones and ruined machines. Vehicles and architecture are organic, with long curves and thin struts.
- **Line and outline:** Thin dark line (1 to 1.5 px) on silhouettes and creases; in open areas lines are sparse. Contour lines on dunes and rock strata are drawn as fine parallel strokes.
- **Shading model:** Flat colour with at most one flat shadow tone. Shadow is a hard-edged tint, not black.
- **Palette:** `#2b2623` `#f3d9b1` `#e8a87c` `#c38d9e` `#85cdca` `#f6f1e7` `#d96c4f`. Pale sand, peach, dusty rose and mint, with a small strong accent. Large areas of near-white.
- **Lighting:** High desert sun; time of day changes the whole palette at once.
- **Texture and surface:** None in colour. Fine line marks only.
- **Atmosphere and post-processing:** None. Colour areas are perfectly flat; distance is shown by lighter line and colour.
- **Camera and framing:** Very wide shots with a small subject; 24 to 35 mm equivalent.
- **UI and typography:** Minimal UI with no filled panels: thin dark line frames and simple line-drawn glyph icons placed straight on the scene. Text is a light, widely spaced geometric sans in the dark line colour; counters are small thin numerals. Selected items take the orange-red accent, other elements stay sand or near-white.
- **VFX and motion:** Dust trails, smoke and wind are flat pale shapes with a thin outline that break into a few dots and fade. Impacts are a short ring of radiating line strokes. Characters and vehicles animate on twos with calm, gliding movement and long holds.

## Fits

- **Genres:** `exploration`, `racing`, `action-adventure`, `puzzle`, `sports`, `platformer`
- **Moods:** calm, lonely, dreamlike
- **Settings:** desert wasteland, alien planet ruins, nomad camp, crashed starship

## Godot recipe

### Assets

Desert and ruin packs with eroded arches, bones and derelict machines; favour long curves and thin struts. Remove all textures and fill surfaces with flat pale colours. Dunes and rock strata are best built in a generator script with `SurfaceTool` as smooth meshes whose UVs run along the height, so a contour texture of fine parallel strokes can follow them. Keep models light: large empty areas are part of the look.

### Materials

Write `thin_line_pastel.gdshader`, a spatial shader with a `light()` function that outputs a flat colour and at most one flat shadow tint: `step` on `ATTENUATION * dot(NORMAL, LIGHT)`, with the shadow colour a hard-edged darker pastel, never black, and no specular. A second texture adds sparse contour strokes that fade out by a world-space noise mask so open areas stay nearly empty. All base and shadow colours are global shader uniforms (`global uniform vec4`, declared in the project's shader globals) so a time-of-day script can swap the whole scheme at once with `RenderingServer.global_shader_parameter_set`.

### Lighting and atmosphere

One high `DirectionalLight3D` sun, hard shadows (`shadow_blur` low, small `light_angular_distance`), PSSM 2 Splits. Flat colour ambient. No fog in the `Environment`: distance is shown by mixing colours toward `#f6f1e7` with depth in the shader. No SSAO, no probes, no SDFGI. The sky is a single flat tint (background mode colour).

### Post-processing

A full-screen quad in front of the camera (2x2 `QuadMesh`, `POSITION = vec4(VERTEX.xy, 1.0, 1.0);`) draws lines from `hint_depth_texture` and `hint_normal_roughness_texture` at 1 to 1.5 px in `#2b2623`. Two things separate it from a heavier comic line: line opacity falls with scene depth so far forms get a lighter line, and the normal threshold is high so only silhouettes and sharp creases are drawn. Tonemap Linear, no glow, grain or vignette. Use SMAA or MSAA 8x; thin lines need good anti-aliasing. Keep `rendering/scaling_3d/scale` at 1 or above. On the Mobile renderer: there is no normal-roughness buffer, so rebuild normals from the depth texture (cross product of neighbouring reconstructed view positions) and keep the high threshold.

### UI and effects

No filled panels. Frames are thin dark line rectangles (`StyleBoxFlat` with no fill, 1 px `#2b2623` border) and icons are line glyphs in `TextureRect` nodes placed straight on the scene. The theme font is a light geometric sans such as Jost Light with wide character spacing (`FontVariation` spacing); counters are small thin numerals. Selected items switch to `#d96c4f`. Effects are flat pale mesh shapes with a thin outline: dust trails that break into a few dots and fade, impact rings of short radiating strokes drawn as thin unshaded quads or an `ImmediateMesh`. Step vehicle and character animation to twos (12 fps updates) and use long holds.

## Do / Do not

Do:

- Keep lines thin and lighter with distance.
- Use large empty areas of one flat colour.
- Draw strata and dune contours as fine parallel lines.
- Change the whole palette together for mood.

Do not:

- Do not thicken lines or switch to strong primary colours; that reads as `011`.
- Do not add smooth sand gradients and glitter; that reads as `061`.
- Do not add watercolour texture and soft edges; that reads as `025`.
- Do not shade with more than one shadow tone.

## Nearest styles

- `011` Clear-line adventure comic: `011` uses clear red, blue and yellow flats with a heavier line of one weight on every edge; this style uses pale sand and pastel tints with thin lines that thin out in open areas.
- `025` Watercolour wash minimal: `025` has soft bleeding edges, paper grain and almost no drawn line; this style has perfectly flat colour inside thin ink lines.
- `061` Soft-gradient minimal desert: `061` has no lines and shades its dunes with smooth gradients; this style draws every form in line and fills it with flat colour.
