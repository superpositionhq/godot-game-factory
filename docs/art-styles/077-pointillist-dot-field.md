# Pointillist dot field

Reference works: Georges Seurat.

## References

- *A Sunday Afternoon on the Island of La Grande Jatte* (1886), Georges Seurat, oil painting. https://en.wikipedia.org/wiki/A_Sunday_Afternoon_on_the_Island_of_La_Grande_Jatte
- *Bathers at Asnieres* (1884), Georges Seurat, oil painting. https://en.wikipedia.org/wiki/Bathers_at_Asnières
- *The Circus* (1891), Georges Seurat, oil painting. https://en.wikipedia.org/wiki/The_Circus_(Seurat)
- *The Port of Saint-Tropez* (1901), Paul Signac, oil painting. https://en.wikipedia.org/wiki/Paul_Signac

## Visual definition

- **Shape language and proportions:** Calm, formal, static compositions. Figures and trees are simplified into smooth columns, cones and ovals with stiff poses, mostly in profile or frontal.
- **Line and outline:** None. Edges are where dot colours change; a slight halo of contrast appears along edges.
- **Shading model:** Smooth modelling achieved by changing the proportions of dot colours: more yellow and orange dots in light, more blue and violet dots in shadow.
- **Palette:** `#2f6fb0` `#f2c94c` `#e2574c` `#4caf6a` `#f08a3c` `#8a5fb5` `#f5efdc`. A small set of pure pigments (blue, yellow, red, green, orange, violet) plus white; apparent colours form by optical mixing.
- **Lighting:** Clear afternoon sun with long, soft, blue-violet shadows.
- **Texture and surface:** Uniform small round dots of pure colour, evenly spaced, covering the whole image including the sky; often a painted dotted border.
- **Atmosphere and post-processing:** Full-frame dot pass; no blur.
- **Camera and framing:** Frontal, level, wide park or riverside view; long lens flattening.
- **UI and typography:** Every panel has a painted dotted border in contrasting colours, like Seurat's painted frames, around a pale cream `#f5efdc` field of fine dots. Text is a tall, formal poster-style sans with even strokes in deep blue `#2f6fb0`, numbers are upright and evenly spaced in the same face, and icons are simple stiff silhouettes filled with dots.
- **VFX and motion:** Particles are loose dots that scatter out of a surface and settle back into the dot field; impacts are rings of dots in the opposite colour (orange against blue, yellow against violet). Motion is slow and poised, with held formal poses and smooth glides instead of quick snaps.

## Fits

- **Genres:** `puzzle`, `strategy`, `simulation`, `sports`, `tower-defense`, `exploration`
- **Moods:** calm, formal, sunny
- **Settings:** riverside park, seaside harbour, circus ring, Sunday promenade

## Godot recipe

### Assets

Calm, formal scenes: parks, riverbanks, promenades, with figures and trees simplified into smooth columns, cones and ovals in stiff profile or frontal poses. Smooth pack models by removing detail and normal maps; give each surface one clear local colour. Forms must be clearly shaped with clean edges, since nothing is dissolved here. Generate a painted dotted border texture for the frame in a generator script with `Image`.

### Materials

Scene shading stays smooth so the dot pass can translate it: a `StandardMaterial3D` with `specular_mode` Disabled, or a short spatial shader `smooth_local.gdshader` whose `light()` writes a soft Lambert from `dot(NORMAL, LIGHT)` times `ATTENUATION`, tinted blue-violet where unlit. Shadow casting and depth come with either. The dots themselves are made in post.

### Lighting and atmosphere

Clear afternoon sun: a `DirectionalLight3D` 25 to 35 degrees above the horizon with long shadows softened by `shadow_blur` at moderate `shadow_opacity`, tinted blue-violet through the `Environment` ambient colour. Bright ambient. No fog, no haze. No SSAO. A plain sky from a `ProceduralSkyMaterial`, which also gets dots.

### Post-processing

A full-screen `QuadMesh` in front of the camera with a spatial shader reading `hint_screen_texture` and `hint_depth_texture` rebuilds the image from dots before tonemapping. Lay a regular but slightly jittered grid of round dots (pitch about 6 to 8 px at 1080p), plus a second grid offset by half a cell. For each dot, sample scene colour at the dot centre and choose one pure pigment from the fixed set (blue, yellow, red, green, orange, violet, white) by probability: decompose the colour into weights over the pigments and pick with a per-dot hash, so lit areas get more yellow and orange dots and shadows more blue and violet. Dots are round, even in size, touch one another, and cover everything including sky; fill between them with pale cream `#f5efdc`. Along depth edges, bias the pick toward complementary pigments on each side to create the contrast halo. Anchor the grid in screen space (`FRAGCOORD`) and keep the camera slow. No blur, glow or grain. Tonemap Linear, `rendering/scaling_3d/scale` 1.

### UI and effects

Every panel has a painted dotted border in contrasting colours around a cream dotted field: a `StyleBoxTexture` 9-sliced from the dotted border texture in the `Theme`. Font from a tall formal poster sans with even strokes such as Josefin Sans SemiBold or Federo, imported as a `FontFile` and set as the theme default font, in `#2f6fb0`; upright, evenly spaced numerals. Icons are stiff silhouettes filled with dots. Particles are round dot quads in a `MultiMeshInstance3D` that a script scatters from a surface and eases back; impacts are rings of dots in the opposite colour from `GPUParticles3D` with a ring emission shape. Motion is slow with held formal poses.

## Do / Do not

Do:

- Cover the entire frame with small round dots.
- Use only a small set of pure pigments.
- Model light by changing dot proportions.
- Keep forms smooth, simplified and static.

Do not:

- Do not use a regular rotated halftone grid with black outlines; that reads as `081` or `009`.
- Do not use elongated, varied brush dabs; that reads as `075`.
- Do not use square tiles with grout; that reads as `055`.
- Do not mix colours inside a dot.

## Nearest styles

- `075` Impressionist broken colour: this style covers smooth, stiff forms with even round dots of a few pure pigments; `075` dissolves its forms into irregular, elongated dabs of many blended pastel colours.
- `081` Ben-Day pop art: this style has no outlines and covers the whole picture with hand-placed dots; `081` has thick black outlines and uses a mechanical dot grid only in some areas, next to flat colour.
- `055` Mosaic tessera: this style has no gaps or lines between its marks and models forms smoothly with round dots; `055` is built from square tiles with dark grout lines and stepped tile tones.
