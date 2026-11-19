---
name: godot-mobile-game
description: 'The rules of a godot-game-factory game-building session that hold for a mobile (Android phone) game only. Use with the godot-game-session skill in every session that builds a game made with new-game.ps1 -Platform mobile (its root has a Platform.json), and with the godot-write-tasks skill when writing that game''s tasks. A desktop game''s session reads godot-desktop-game instead.'
---

# Mobile game (Godot)

Your game is an Android phone game, landscape or portrait, played by touch. Everything in the **godot-game-session**
skill holds; this skill is what holds for a mobile game alone, and it takes the place of the **godot-desktop-game**
skill, which you do not read. Where a shared rule names a keyboard, a mouse, Escape, a 1920x1080 window or a Windows
player as the product, the rule here is the one that applies.

## Start

- Create the project with `new-game.ps1 ... -Platform mobile -Orientation landscape` (or `portrait`), as the
  godot-game-session skill's Start says, with those two switches added. The orientation is chosen with the person
  before the project exists and never changes after.
- It writes `Platform.json` at the root (`{"platform": "mobile", "orientation": "..."}`) and lays the mobile files
  over the skeleton: a mobile game's `project.godot`, the `Android` preset in `export_presets.cfg`, `game/phone.gd`
  (the autoload `Phone`, which tells the AutoPlay drop-in the game is a phone game) and a first scene with a touch
  button. **Never edit or delete `Platform.json` or `game/phone.gd`**: every later tool reads the platform from that
  file alone, and a file that says anything else is an error, never read as a desktop game.
- **Keep the mobile settings as they came**: the validators hold the project, the APK and the dataset to them
  (`tools/validate-game.py`, rule `mobile`):
  - `project.godot`: the Mobile renderer (`rendering/renderer/rendering_method="mobile"`, and
    `rendering_method.mobile`), `rendering/textures/vram_compression/import_etc2_astc=true` (the texture formats a
    phone reads), the frame size 1920x1080 (landscape) or 1080x1920 (portrait) with stretch mode `canvas_items`,
    `display/window/handheld/orientation` (0 landscape, 1 portrait), `application/config/quit_on_go_back=false` (the
    back button is the game's to handle), `input_devices/pointing/emulate_mouse_from_touch=true` and
    `emulate_touch_from_mouse=false`.
  - the `Android` export preset: package name `com.<project in lower case>.game`, minSdk 26, targetSdk 34, arm64
    alone, a Gradle build (`gradle_build/use_gradle_build=true`: only a Gradle build takes the SDK levels).
- Android only. No iOS target, no tablet-only layout.

## Rendering

- **One renderer everywhere.** The game is drawn with Godot's Mobile renderer (Vulkan), on the phone and on this PC
  alike: every play, screenshot, recording and task play of the game uses it, because the project says so. Never pass
  `--rendering-method` or `--rendering-driver` to a run, and never switch the project to Forward+ "to see it
  properly": the Windows player would then draw what the phone does not.
- **What the Mobile renderer does not have** (Godot 4.7; all of these are Forward+ only): SDFGI, VoxelGI,
  screen-space indirect lighting (SSIL), screen-space ambient occlusion (SSAO), screen-space reflections, volumetric
  fog (so no `FogVolume` either), TAA and FSR2, sub-surface scattering, the normal-roughness buffer in shaders
  (`hint_normal_roughness_texture`), and PCSS soft shadows for directional lights. Never turn them on and never build
  a look that depends on them: on the Mobile renderer they draw nothing.
- **Its limits.** A mesh is lit by at most 8 `OmniLight3D` and 8 `SpotLight3D` (256 of each in a view) and at most 8
  `ReflectionProbe`s: split a large mesh that many lights reach, and keep lights few and local. Colour is rendered in
  a 10-bit buffer with less range than Forward+'s (the engine's "medium dynamic range, low precision"): very bright
  emission and wide glow clip or band sooner, so keep bright values moderate and look at the result.
- **What it has**, and what a mobile look is built from: baked lightmaps (`LightmapGI`), `ReflectionProbe`, depth and
  height fog, glow, tonemapping and adjustments, MSAA, FXAA and SMAA, decals, light projector textures, depth-of-field
  blur, the screen and depth textures in shaders, GPU particles. Light with baked or few simple dynamic lights; put
  contact shadow and bounce light into the bake or the textures.
- The art style still decides the look (godot-game-session, "Art style"): follow the guide's Godot recipe and, where
  it has one, its "On the Mobile renderer" sentence. Check every material in a play: one written for a Forward+
  feature can come out black or flat.
- **Look at the game as a phone draws it.** On this PC the game is played at the phone's size: 1920x1080 (landscape)
  or 1080x1920 (portrait). `Scripts/godot.ps1 play` runs the project with the Mobile renderer at exactly that size,
  whatever the PC's screen is; `-Shots <n>` saves frames of that size. Every screenshot you judge the game by, the
  framing screenshots and the README stills come from such a play or from a recording's stills, never from the
  editor's view at another size.
- **Budgets, for a mid-range phone, in any view the player can reach:** at most **500,000 triangles** drawn, at most
  **700 draw calls**, at most **1 GB of textures** in memory. Design to them from the first scene: fewer, merged and
  instanced meshes (`MultiMeshInstance3D`), texture sizes chosen on purpose, few translucent layers, few dynamic
  lights and shadow casters (each shadowed light draws the scene again). The engine's frame totals include the 2D
  canvas, so the HUD's and the touch controls' draws count toward the 700.
- **How to read them.** The engine counts them itself: `Performance.get_monitor()` with
  `Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME`, `RENDER_TOTAL_DRAW_CALLS_IN_FRAME` and `RENDER_TEXTURE_MEM_USED`
  (bytes), the same numbers `RenderingServer.get_rendering_info()` gives. Log them from a git-ignored debug flag of
  your own in a `Scripts/godot.ps1 play` at the busiest views and compare with the budgets; a headless run renders
  nothing and reads zero. A task may measure them (godot-write-tasks, the `render` reading: `draw_calls`,
  `triangles`, `texture_mb`, docs/task-probes.md section 2.20): the two counts are the highest over the frames since
  the previous sample, the texture memory is read at the sample.

## Touch

- **Touch only.** Everything the player does is done with fingers on the screen: on-screen buttons, a virtual stick,
  taps, drags and swipes on the world. Nothing in the game is reachable only by a key, a mouse button, mouse movement
  or a gamepad.
- **Controls are `Control` nodes with names of their own** (`FireButton`, `MoveStick`, `PauseButton`; never the
  default `Button2`), laid out in the UI scene: a `Button` or `TextureButton` for a press, a stick as a `Control`
  that tracks a finger (the engine's `VirtualJoystick`, or one of your own). A task taps a control by its node name,
  and a name that differs between landscape and portrait builds or changes between commits breaks it. Never a
  `TouchScreenButton`: it is not a `Control`.
- **Read touches as the engine sends them:** `InputEventScreenTouch` (a finger down or up, with its `index` and
  `position`) and `InputEventScreenDrag` (a finger moving), in a control's `_gui_input` for what the control owns and
  in `_unhandled_input` for touches on the world. Track fingers by `index`, so a stick held with one thumb and a
  button tapped with the other both work. **A `Button`'s `pressed` signal fires for the first finger down only**:
  the engine makes its mouse click from that finger alone (`emulate_mouse_from_touch`), so a `Button` tapped while
  another finger holds the stick does nothing. That is fine for a menu, never for play: a control used during play
  (jump, fire, dash) reads `InputEventScreenTouch` (and `InputEventScreenDrag`) itself in `_gui_input`, for any
  finger, as the template's `game/touch_button.gd` does: a second finger never reaches a plain `Button`. The task check's own drive
  holds the stick with one finger and taps at the lower right with a second. The AutoPlay bot and the task plays send these same
  events, so a game that reads the mouse position or polls the keyboard takes none of their input.
- **The back button.** Android's back button reaches the game as `NOTIFICATION_WM_GO_BACK_REQUEST` (handle it in
  `_notification` of a node that is always in the tree). It does what Escape does on a desktop game: it opens the
  pause menu in play, closes what is open, and goes back one screen in menus. It never quits without asking. The
  template sets `application/config/quit_on_go_back=false` so the engine leaves it to the game; keep that. To the
  factory's tools the back button is `<Keyboard>/escape` (the bot's `AutoPlay.hold` / `release`, a task's key): in a
  mobile game's run they send that control as the phone sends its back button, the go-back request.
- **Sized for a thumb.** Controls a finger must hit are large and apart from each other, inside the screen's safe
  area (away from the edges, the camera cut-out and the system gesture bar): read
  `DisplayServer.get_display_safe_area()` and keep every control inside that rectangle, with a margin of your own on
  top, and never under where the hands rest. Text is readable at phone size: judge it in a frame of
  `Scripts/godot.ps1 play -Shots` shown at the size of a phone screen, not full size on a monitor.
- **One orientation.** The layout is built for the game's orientation alone and fills it; no screen assumes the
  other.
- **Pause when the app leaves the foreground** (a call, the home button) and come back to the pause menu: the engine
  sends `NOTIFICATION_APPLICATION_PAUSED` when Android puts the app in the background, and
  `NOTIFICATION_APPLICATION_FOCUS_OUT` when it loses focus. Pause on the first; treat a focus loss the same only on
  the phone itself (`OS.has_feature("android")`). On this PC the game's window is often not the focused one (a
  recording, a task play, a session's own run), and a game that paused there would record its pause menu. And
  never pause, open a menu or mute from any of these while `AutoPlay.is_active` (docs/autoplay-contract.md).

## Quality bar

- **Quality bar:** main menu, settings (volume, touch sensitivity where the game has a look or aim control), pause on
  the back button, save/load where it fits, HUD, sound, clear win/lose, a Windows x64 release player of the game at
  the phone's size (what is played and recorded here) and, at release, its Android APK (arm64), which the pipeline
  builds. Recorded and TTS voices are allowed.
- **Room for hard tasks.** A game's tasks come from its own history (godot-write-tasks skill), and strong agents miss
  what only shows when the game runs. So build these in, and work them over several rounds rather than in one commit:
  feedback for every gameplay event (a HUD readout, marker, sound or effect); visible state changes (materials,
  colours, lights, dressing); a pause menu with settings and back navigation on the back button; touch controls whose
  size, place and response a player feels; tuned numbers a player feels (ranges, detection, damage, timers); views
  that stay inside the budgets. Fix each playtest issue in its own commit whose message says what the player saw, so
  the thread can be found and checked later.

## AutoPlay on a mobile game

- `game/phone.gd` tells the AutoPlay drop-in the game is a phone game (`AutoPlay.phone`): `AutoPlay.is_phone` is
  true, and a run's `ready.json` says how the phone is held.
- **The bot plays with fingers.** It acts only through `AutoPlay.touch(finger, position)` and
  `AutoPlay.touch_up(finger)` (a tap is a touch in one frame and its lift in a later one; a virtual stick is a finger
  put down on it and moved; two thumbs are fingers 0 and 1) and `AutoPlay.hold` / `release` of `<Keyboard>/escape`,
  the back button. The drop-in refuses every other key, the mouse and the gamepad in a phone game's run
  (docs/autoplay-contract.md, section 4). Positions are pixels of the game's frame from its top left; find a
  control's place from the node itself (`get_global_rect().get_center()`), never from a number written for one
  screen size.
- The hand test and the recording are the same commands as a desktop game's (`Scripts/godot.ps1 autoplay`,
  `pipeline.ps1`); the video is 1920x1080 or 1080x1920.

## Tasks on a mobile game (with the godot-write-tasks skill)

- A mobile game's tasks are played with the Mobile renderer at the phone's size (1920x1080 or 1080x1920), as a
  phone's play; the task check does this itself from `Platform.json`. A task's play never chooses a renderer or a
  size in its arguments (`--rendering-method`, `--rendering-driver`, `--resolution`, `-size`): the validator refuses
  them.
- **Drive the game by touch.** A play's inputs use `tap` and `drag` (docs/task-probes.md section 1.3): a spot on the
  screen as fractions of its width and height, or a widget by name (`{"widget": "FireButton"}`: the centre of the
  first visible `Control` of that node name); `hold` for a held touch, `finger` for a second finger. The back button
  is the key `<Keyboard>/escape`. Touch a control by its name or the caption it shows, never by a spot of the
  screen: a caption written exactly as the screen shows it, in the game's own language (`{"widget": "确定"}`), is
  the words a player finds it by. Its place differs between landscape and portrait and between builds; a spot only where no control is (a
  virtual stick's area, the open playfield). The checker's own `drive` play is by touch on a mobile game: a left thumb at the
  lower left pushed along the route, a tap at the lower right. A brief written for a mobile game never asks for a
  key or a mouse. A touch whose control isn't on screen is a miss (`inputs_missed`): on the reference it makes the
  task INVALID (its own fix can't be driven by the play), on the start it fails that play's checks. A tap on a control
  that only the lists it sits in hide scrolls them to it and lands, as a player's thumb scrolls to it, so never
  script a swipe just to bring a control into view; a control hidden any other way, and a drag's control out of view,
  is a miss (godot-write-tasks, "A click scrolls its own list"). A tap on a control under a dialog, a popup or an
  overlay is a miss that says it is covered: close it first with the player's own touch (godot-write-tasks, "A
  covered control can't be clicked"). A play may run up to 1200 s, and a touch's `hold` and a drag's `over` go up
  to 1200 s too, so a stick can be held through a long run; keep each play as short as what it measures allows, since
  every second is played on both sides of every check. Read both sides'
  `probe.log` in the no-op and oracle check (godot-write-tasks, "The no-op and the oracle, on your own machine").
- Good mobile threads to look for in your history: a control that was too small or badly placed and took rounds to
  fix, a layout broken in the game's orientation, a view over a budget brought back under it (the `render` reading
  with a literal threshold, `{"op": "<=", "value": 700}`, in a play of its own that takes the player to the view and
  reads nothing else), the back button's behaviour, the pause on leaving the app.

## Build, recording and dataset

- You build and test the Windows player (`Scripts/godot.ps1 build`): it is what this PC plays and records.
  `Scripts/godot.ps1 build -Android` also exports the APK, `Build/Android/<Project>.apk`, when the machine has the
  Android toolchain (`machine/get-android.ps1` installs it; `machine/check.ps1` reports it,
  docs/new-machine.md says how). The release pipeline builds the same player from the release commit and, on a
  machine with the toolchain, the APK; it reads the APK back and refuses one that is not arm64 alone, at the SDK
  levels and with the package name above. On a machine without the Android toolchain the APK step is skipped and
  says so: that is not a failure of your game, and everything else (plays, AutoPlay, recordings, the task check)
  works without it; only the release needs the APK, and the packager refuses a mobile game without one. Never install Android tools yourself or change the preset to get an APK; tell the coordinator
  (or the person) that the machine lacks the toolchain.
- The scenario videos are recorded from the Windows player at the phone's size. The dataset's manifest says
  `"platform": {"kind": "mobile", "orientation": "..."}`, and its `Build/` holds the Windows player and the APK.
- `tools/validate-game.py` reads `Platform.json` and holds a mobile game to this skill's project settings (rule
  `mobile`).
