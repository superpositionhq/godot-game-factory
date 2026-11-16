# CGA four-colour

Reference works: Alley Cat.

## References

- *Alley Cat* (1983), Synapse Software (Bill Williams), video game. https://en.wikipedia.org/wiki/Alley_Cat_(video_game)
- *Digger* (1983), Windmill Software, video game. https://en.wikipedia.org/wiki/Digger_(video_game)
- *Lode Runner* (1983), Broderbund (Doug Smith), video game. https://en.wikipedia.org/wiki/Lode_Runner
- *Paratrooper* (1982), Orion Software (Greg Kuperberg), video game. https://en.wikipedia.org/wiki/Paratrooper_(video_game)

## Visual definition

- **Shape language and proportions:** Chunky pixel shapes at 320x200. Objects are simple icons: a few rectangles and diagonal steps.
- **Line and outline:** Black gaps and black outlines separate cyan, magenta and white areas where needed.
- **Shading model:** None. Intermediate tones are made by checkerboard dithering two of the four colours.
- **Palette:** `#000000` `#55ffff` `#ff55ff` `#ffffff` `#00aaaa` `#aa00aa`. Exactly four colours on screen: black, bright cyan, bright magenta and white. The two darker hex values listed are the low-intensity variant of the same palette; use one intensity per frame.
- **Lighting:** None.
- **Texture and surface:** Checker and stripe dither patterns; flat fills.
- **Atmosphere and post-processing:** 320x200 output with non-square pixels (stretch to 4:3), optional scanlines and composite colour bleed.
- **Camera and framing:** Fixed side or front view; in 3D, a fixed perspective with simple forms.
- **UI and typography:** Flat black panels with a one-pixel cyan `#55ffff` or magenta `#ff55ff` border, and blocky icons of a few rectangles. Type is a chunky 8x8 px bitmap face in capitals, as in early PC text modes. Score and lives counters sit in a single row at the top in white or cyan, with magenta for highlights.
- **VFX and motion:** Effects are bursts of a few white and magenta pixels, and a hit makes a sprite flicker by swapping its colours; nothing is transparent. Animation has two or three frames per cycle and sprites move in jerky steps of several pixels.

## Fits

- **Genres:** `platformer`, `puzzle`, `top-down-shooter`, `tower-defense`, `roguelike`
- **Moods:** quirky, garish, nostalgic
- **Settings:** back alley, underground mine, brick maze, night-sky gun emplacement

## Godot recipe

### Assets

Chunky icon-like shapes for a 320x200 screen: a few rectangles and diagonal steps per object. Paint sprites and tiles in a generator script (`Image`) directly in the four colours, or use simple 3D models and reduce them in post. Textures use nearest filtering with no mipmaps and lossless compression. Generate checkerboard and stripe dither tiles for the two-colour mixes (cyan and white, magenta and black, and so on). Leave black gaps between adjacent cyan, magenta and white areas.

### Materials

Sprites and tiles are drawn with no material and exact palette colours; keep the default white modulate and avoid any tint. For 3D objects, a spatial shader such as `four_colour_flat.gdshader` with `unshaded` outputs one palette index per material (encoded as a grey level in `ALBEDO`); the outline pass reads the depth texture. No lighting is computed. Nothing is transparent: use alpha scissor only.

### Lighting and atmosphere

None: no lights needed, shadows off, flat ambient, no fog, no SSAO, no probes. Background is black.

### Post-processing

Render into a 320x200 `SubViewport` with nearest filtering and display it stretched to 4:3 (pixels are taller than wide), scaled as far as the window allows (a `TextureRect` showing the viewport texture, sized by script to the largest 4:3 rectangle). A full-screen quad inside the `SubViewport` maps every pixel to black, `#55ffff`, `#ff55ff` or white: quantise by nearest palette colour, and where the source value lies between two entries use a checkerboard of those two based on pixel parity (`FRAGCOORD`). Add black one-pixel outlines from depth edges where two non-black regions touch. Use one intensity set per frame; the dark variant (`#00aaaa`, `#aa00aa`) replaces the bright one for a whole scene, never mixed. Optional last pass at output resolution, a `canvas_item` shader over the screen: faint scanlines and a small horizontal colour smear. Tonemap Linear, no glow, no anti-aliasing.

### UI and effects

Flat black panels with a one-pixel cyan or magenta border (`StyleBoxFlat`, corner radius 0), drawn inside the low-resolution `SubViewport`. Theme font from an 8x8 text-mode style face such as Press Start 2P or a VGA-style pixel font, antialiasing off, capitals. Score and lives sit in one row at the top in white or cyan, magenta for highlights. Effects: bursts of a few white and magenta pixels; a hit swaps the sprite's colours for a few frames. Two or three animation frames per cycle, and movement in steps of several pixels.

## Do / Do not

Do:

- Use only black, cyan, magenta and white.
- Dither with a checkerboard for extra tones.
- Render at 320x200 and stretch to 4:3.
- Keep shapes iconic and blocky.

Do not:

- Do not use green shades; that reads as `038`.
- Do not use a wider tile palette; that reads as `042`.
- Do not draw glowing lines on black without fills; that reads as `040`.
- Do not anti-alias.

## Nearest styles

- `038` Game Boy four-shade green: this style is harsh bright cyan, magenta and white on black; `038` is four soft olive greens.
- `042` NES 8-bit tile: this style shows only black, cyan, magenta and white, with checkerboard dither for in-between tones; `042` mixes many colours on one screen, such as red, blue, green and orange.
- `040` Vector display glow: this style fills areas with solid and checker-dithered pixels; `040` draws only thin glowing lines on black and fills nothing.
