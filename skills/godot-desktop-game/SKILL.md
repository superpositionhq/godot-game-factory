---
name: godot-desktop-game
description: 'The rules of a godot-game-factory game-building session that hold for a desktop (Windows) game only. Use with the godot-game-session skill in every session that builds a desktop game, which is every game without a Platform.json at its root. A mobile game''s session reads godot-mobile-game instead.'
---

# Desktop game (Godot)

What the **godot-game-session** skill's "Engine and content" list holds for a desktop game alone. A game is a desktop
game unless it was made with `new-game.ps1 -Platform mobile` (then its root has a `Platform.json`, and its session
reads the **godot-mobile-game** skill instead of this one).

- **Renderer: Forward+.** The template sets `rendering/renderer/rendering_method="forward_plus"`; keep it. Forward+
  has every rendering feature of the engine (clustered lights, SDFGI, VoxelGI, SSAO, SSIL, screen-space reflections,
  volumetric fog, sub-surface scattering, TAA), so the art style guide's Godot recipe applies as written; skip its "On
  the Mobile renderer" sentences. The frame is 1920x1080.
- **Played with keys, mouse and gamepad.** The game's actions are in the Input Map with keyboard and mouse events
  (and gamepad ones where the game suits a pad); the AutoPlay bot plays by keys, mouse and gamepad.
- **Quality bar:** main menu, settings (volume, window mode, mouse sensitivity), pause, save/load where it fits, HUD,
  sound, clear win/lose, a Windows x64 release player (`Scripts/godot.ps1 build`, which exports
  `Build/Windows/<Project>.exe`). Recorded and TTS voices are allowed.
- **Room for hard tasks.** A game's tasks come from its own history (godot-write-tasks skill), and strong agents miss
  what only shows when the game runs. So build these in, and work them over several rounds rather than in one commit:
  feedback for every gameplay event (a HUD readout, marker, sound or effect); visible state changes (materials,
  colours, lights, dressing); a pause menu with settings and back navigation on Escape; tuned numbers a player feels
  (ranges, detection, damage, timers). Fix each playtest issue in its own commit whose message says what the player
  saw, so the thread can be found and checked later.
