# NES 8-bit tile

Reference works: Super Mario Bros.; 3D Dot Game Heroes.

## References

- *Super Mario Bros.* (1985), Nintendo R&D4, video game. https://en.wikipedia.org/wiki/Super_Mario_Bros.
- *The Legend of Zelda* (1986), Nintendo R&D4, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda_(video_game)
- *3D Dot Game Heroes* (2009), Silicon Studio, video game. https://en.wikipedia.org/wiki/3D_Dot_Game_Heroes
- *Mega Man 2* (1988), Capcom, video game. https://en.wikipedia.org/wiki/Mega_Man_2
- *Shovel Knight* (2014), Yacht Club Games, video game. https://en.wikipedia.org/wiki/Shovel_Knight

## Visual definition

- **Shape language and proportions:** 16x16 px tiles and sprites. Characters are squat with large heads; scenery repeats the same few tiles. In 3D, each sprite pixel becomes a cube.
- **Line and outline:** Dark outlines or dark background separation around sprites; not on every tile.
- **Shading model:** None. Each sprite uses three colours plus transparency; highlights are single lighter pixels.
- **Palette:** `#000000` `#fcfcfc` `#f83800` `#0058f8` `#00a800` `#fca044` `#5c94fc` `#ac7c00`. Saturated console colours on a flat sky blue or black background; at most 13 to 25 colours on screen.
- **Lighting:** None. In the 3D variant, a flat directional light may shade cube faces.
- **Texture and surface:** Repeating pixel tiles: bricks, blocks, bushes, clouds built from the same shapes.
- **Atmosphere and post-processing:** 256x240 output, integer scaling, optional scanlines.
- **Camera and framing:** Side-scrolling or top-down orthographic; for the 3D cube variant, a tilted view with shallow depth of field.
- **UI and typography:** A black status strip along the top or bottom with no panel art; dialogue boxes are black with a one-tile white or blue border. Text is a chunky 8x8 px bitmap face in white capitals, and counters are fixed-width digits with leading zeros for score, coins and time. Icons are 8 or 16 px sprites such as hearts and coins, in white, red-orange `#f83800` and blue `#0058f8`.
- **VFX and motion:** Effects are sprite animations of two to four frames: a star-burst puff, a sprite that flashes when hit, blinking while invulnerable, score numbers that pop up and rise. Motion is snappy, with two- or three-frame walk cycles, instant turns and fixed jump arcs.

## Fits

- **Genres:** `platformer`, `action-adventure`, `rpg`, `top-down-shooter`, `puzzle`, `sports`
- **Moods:** playful, nostalgic, bright
- **Settings:** cartoon kingdom, overworld fields and dungeons, robot fortress

## Godot recipe

### Assets

16x16 tiles and sprites, three colours plus transparency each, built from a small set that repeats (bricks, blocks, bushes and clouds sharing shapes). Paint them in a generator script with `Image` or adapt CC0 pixel packs by remapping to the console palette. In the 3D variant, convert each sprite pixel to a cube in a generator script with `SurfaceTool` (one merged `ArrayMesh` per sprite, colour in vertex colour, saved with `ResourceSaver`). In each texture's `.import`, mipmaps off and lossless compression; sample with nearest filtering.

### Materials

2D tiles and sprites draw as `TileMapLayer` and `Sprite2D` nodes with the default canvas texture filter set to nearest in the project settings; in 3D, an unshaded `StandardMaterial3D` with alpha scissor. For the cube variant write `cube_sprite.gdshader`: `fragment()` takes the vertex colour as `ALBEDO`, and `light()` applies a fixed brightness by face direction from `NORMAL` and `LIGHT` with a `step`, so faces take two or three flat levels and stay in palette-like colours. Render modes `specular_disabled` and `shadows_disabled`; no gradients. Flash-on-hit swaps the colours to white for two frames through an `instance uniform` set from script.

### Lighting and atmosphere

None for 2D. For cubes, one `DirectionalLight3D` used as a direction only. Shadows off, flat ambient colour, no fog, no ReflectionProbe, no SSAO. Background is flat `#5c94fc` or black (the `Environment` background colour, or the default clear colour in 2D).

### Post-processing

Render into a 256x240 `SubViewport` with nearest filtering and scale by an integer factor (for a pure 2D game, a 256x240 base window with stretch mode viewport and integer scaling). Unlike the stricter retro styles, no palette-mapping pass is needed if art is authored in the palette; add one only as a guard, a `canvas_item` shader on a `ColorRect` reading `hint_screen_texture` that snaps colours to the nearest of the listed console colours. Optional scanline pass at output resolution on a `CanvasLayer` above the scaled image, darkening alternate rows by 15 to 25 percent. Tonemap `Linear`, no glow, no MSAA or screen-space anti-aliasing.

### UI and effects

A black status strip along the top or bottom with no panel art; dialogue boxes are black with a one-tile white or blue border built from 8 px tiles (a `NinePatchRect` or `StyleBoxTexture` with 8 px margins). Font: an 8x8 pixel face such as Press Start 2P imported with antialiasing off, used at 8 px or whole multiples, white capitals; counters are fixed-width digits with leading zeros for score, coins and time. Icons are 8 or 16 px sprites. Effects are two- to four-frame sprite animations (`AnimatedSprite2D` or `AnimatedSprite3D`): a star-burst puff, hit flashing, blinking during invulnerability (toggle `visible` every two frames), score numbers that pop up and rise with a `Tween`. Motion is snappy with instant turns and fixed jump arcs.

## Do / Do not

Do:

- Limit each sprite to three colours.
- Build everything on a 16 px tile grid.
- Reuse tiles and shapes.
- Snap output to a fixed console palette.

Do not:

- Do not restrict to four green or four cyan-magenta colours; that reads as `038` or `039`.
- Do not use 16-pixel textures on large cubes in a perspective world with face shading; that reads as `044`.
- Do not use detailed 16-bit sprites with bloom and depth blur; that reads as `047`.
- Do not use gradients.

## Nearest styles

- `044` Voxel block world: `044` is a perspective world of large cubes with noisy textures, three face shades and many natural greens and browns; this style is flat, unlit tiles and sprites in a few saturated console colours.
- `047` HD-2D pixel diorama: `047` puts detailed sprites in a lit 3D diorama with soft shadows, bloom, depth blur and rich colour; this style has no lighting, no glow and only a few colours.
- `039` CGA four-colour: `039` uses only black, white, cyan and magenta; this style has a wider console palette with reds, greens, blues and browns.
