# AutoPlay contract (Godot, v1)

> **The AutoPlay drop-in is here (v1):** `tools/godot-pipeline/autoplay/addons/autoplay/`, copied unchanged into every
> game as `addons/autoplay/` and named as the autoload `AutoPlay` ([Getting the drop-in](#getting-the-drop-in)). A game
> implements its side (section 6), tests one scenario by hand (section 7) and tags `milestone/autoplay-<n>`. The
> recorder and the run checker (`tools/godot-pipeline/validate-run.ps1`) are the recording pipeline's
> ([godot-pipeline.md](godot-pipeline.md)); a session that has reached its milestone records the scenarios itself
> ([Pipeline](godot-pipeline.md#pipeline)).

**Scenario** = a defined start state plus a win/lose condition, numbered 1..n in the game's design doc and named by the
game. It may be a level, a chapter, a race stage or an open-world start setup. A run plays exactly one scenario from
its start state until it is won, lost or times out.

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and the recording request.

**Priorities (user decision).** What ships is what matters, in this order: the game plays; the game builds (the
Windows release player, and for a mobile game the Android APK); the dataset holds the replay scripts and the git log.
The AutoPlay bot should still play like a human (human-like input, aim and camera), but bot work never blocks a
release: one recording per scenario that shows the game running is enough, whatever the result (win/lose/timeout is
metadata). No tuning for win rates, seed sweeps or "clean" runs, and no re-runs or re-recordings to improve how the bot
plays. No retest loops: every rendered run costs the shared machine and holds up delivery, so run the minimum once and
report; re-run only when the user asks. Game-session work never blocks dataset packaging or sharing.

Every game implements this once its first scenario is playable. The recording pipeline then builds the release player,
starts it with the flags below in the engine's Movie Maker mode (the engine writes every frame it renders and the sound
it mixes) and turns each run into a gameplay bundle (`gameplay.mp4`, `inputs.jsonl`, `telemetry.jsonl`, `outcome.json`,
`metadata.json`, `validation.json`, `manifest.json`, `stills/`; see [godot-pipeline.md, Bundle](godot-pipeline.md#bundle)).

The game plays itself: an in-game **bot** reads game state and acts **only by injecting input**: the drop-in sends the
`InputEvent`s a real keyboard, mouse, gamepad or touch screen sends (`Input.parse_input_event`), so the game's input
actions, its `_input` handlers and its `Control` nodes read them exactly as they read real devices, and the drop-in
logs every injected input. Nothing uses OS-level input (`SendInput`), and the bot never calls gameplay code to act.

Use the drop-in unchanged, so all games write identical files. Your game supplies three things: a `start_scenario`
handler (set up scenario n), the calls `scenario_started(name)` and `finish_run(result, score)`, and the bot.

## Getting the drop-in

The drop-in is the folder `tools/godot-pipeline/autoplay/addons/autoplay/`: GDScript files with their `.uid` files
(fixed, so every game has the same drop-in, and copying it again keeps them). `autoplay.gd` is the autoload; the other
scripts are its parts. It needs nothing but the engine, holds no editor code and runs in an exported player and in a
game run from its source.

- **A new game** (`templates/new-game.ps1`) has it from its first commit, in `addons/autoplay/`, with the autoload line
  `AutoPlay="*res://addons/autoplay/autoplay.gd"` in `project.godot` (before the game's own autoloads) and the
  template's scenario list `game/scenarios.gd` (section 6), which already calls it.
- **Every game when the drop-in changes** (a new `autoplay_version`, or a fix): after pulling godot-game-factory, run
  once

  ```
  powershell -ExecutionPolicy Bypass -File <root>\godot-game-factory\tools\godot-pipeline\autoplay\install.ps1 -Game <root>\games\<slug>
  ```

  It copies the drop-in unchanged into `addons/autoplay/` (only the files that differ), writes one `workflow.jsonl`
  row (op `autoplay.install`: the version, the files written with their sha256) and makes one commit of exactly those
  files. It refuses while `addons/autoplay` or `workflow.jsonl` have uncommitted changes (commit first), touches
  nothing else, and leaves the rest of the game's work as it was, staged or not; files in `addons/autoplay` that are
  not the drop-in's are left alone and named (keep the game's own code out of that folder). On an up-to-date game it
  changes nothing. `-DryRun` says what would change. It wires nothing: the autoload line and the game's side
  (section 6) are the game's.

## 1. Command line

The recorder starts the release player like this (the flags after `--` are read by the drop-in, `-scenario` by the
game too; the ones before it are the engine's):

```
<Game>.exe --write-movie <outputDir>\movie.avi --fixed-fps 60 --disable-vsync --log-file <outputDir>\game.log --
           -autoplay -size <W>x<H> -scenario <n> -seed <s> -skill <0..1> -outputDir <abs dir> -maxSeconds <n>
           -buildCommit <sha> -runId <id> -goTimeout 300
```

The game's flags come after `--`: the engine passes on what follows it untouched (`OS.get_cmdline_user_args()`). They
are one dash, the value as the next argument, any case. A value that does not read (a seed that is no integer, a skill
outside 0..1) is held to its range or replaced by the default, with an `error` telemetry row saying so.

**Recording builds are release players** (`Scripts/godot.ps1 build`, the release export template).

| Flag | Meaning | Default |
|---|---|---|
| `-autoplay` | enable AutoPlay | off |
| `-scenario <n>` | scenario number, 1-based, as listed in the design doc; read by the game itself, with or without `-autoplay` (`AutoPlay.scenario_argument`) | 1 |
| `-seed <s>` | integer seed for the bot's RNG and the game's randomness (the engine's global generator is seeded with it at boot and again at go; seed your own `RandomNumberGenerator`s from `AutoPlay.seed`). Determinism is not required | 0 |
| `-skill <0..1>` | bot skill: 0 = clumsy novice (slow reactions, noisy aim, poor choices, still trying), 1 = best the bot can do (a competent human; it need not win). Interpolate reaction time, aim/steering noise, decision quality. Document what it does in the design doc | 1 |
| `-outputDir <dir>` | absolute directory for the run's files (created if missing) | `user://AutoPlay/<yyyyMMdd-HHmmss>` |
| `-maxSeconds <n>` | hard limit from go, in the run's own time (section 2); the run ends with result `timeout`; 0 = no limit | 600 |
| `-buildCommit <sha>` | echoed into every header and outcome.json | empty |
| `-runId <id>` | echoed into every header and outcome.json | empty |
| `-scenarioName <text>` | the scenario's name in the files until the game calls `scenario_started(name)` | empty |
| `-goTimeout <s>` | how long to wait for the pipeline's `go` file, on the machine's clock; `0` starts at once (testing by hand) | 60 |
| `-autoplayMute` | a run in real time: the speakers get silence (hand tests on a shared machine). A movie's sound goes to its file and never to the speakers | off |
| `-autoplayAllowInput` | debugging only: the window takes the keyboard as usual and the drop-in leaves the cursor to the game | off |
| `-autoplayWatchdog <s>` | exit watchdog: the process is ended when no frame has come for `<s>` seconds during a run (section 3, step 8); 0 = off | 120 |

Two flags work with or without `-autoplay`, for every tool of the factory that runs a game:

| Flag | Meaning |
|---|---|
| `-size <W>x<H>` | the exact frame size of the run (section 2) |
| `-shots <n> -shotDir <dir> -seconds <s>` | n PNG frames of the game, `01.png` .. in `<dir>`, evenly spaced over s seconds (at `s * k / (n + 1)`), then the game quits with exit code 0. Under `-autoplay` the seconds count from go and the run ends as a run does. Defaults: 10 seconds, `user://shots` |

In a task check's play (a game started with `-taskProbe`, [task-probes.md](task-probes.md)) a task's `play_args` may
hold `-autoplay`: the bot then plays while the probe watches. The probe owns the window and the frame rate there, so
the drop-in leaves both alone, and `-goTimeout` defaults to 0.

## 2. Frame, time and input (enforced by the drop-in)

- **Exact frame size.** With `-size <W>x<H>` the root window scales its content in viewport mode at that size and
  keeps the aspect (`content_scale_mode = VIEWPORT`, `content_scale_size = (W, H)`, `content_scale_aspect = KEEP`), so
  the game renders exactly W x H pixels whatever the window is: 1920x1080 for a desktop game and a landscape phone
  game, 1080x1920 for a portrait one, on a screen that cannot hold such a window too (measured: windows that Windows
  held to 1920x1061 and 1080x1061, and one of 540x960, gave frames of 1920x1080 and 1080x1920, pixel for pixel, and a
  touch arrived at the viewport pixel it was sent to). The size never comes from the window. A game's
  `display/window/size/viewport_width` and `viewport_height` are the same size, with stretch mode `canvas_items`, so
  such a frame is what a window or a phone of that size shows.
- **A movie is written by the engine, not captured from the screen.** The recorder starts the game with
  `--write-movie`: the engine then steps exactly 1/60 s per frame, writes every frame it renders and the sound it
  mixes for that frame, and takes as long per frame as the machine needs. The video has no dropped and no repeated
  frame, picture and sound are in step to the sample, and nothing depends on the machine's load, its display or who
  is using it. The movie's frames have the project's viewport size (the engine scales anything else to it), which is
  why that setting and `-size` agree.
- **Two clocks.** The machine's clock stamps every row (section 5). **The run's own time** counts the run: the time
  the engine has stepped, summed frame by frame (the frame's delta with the game's `Engine.time_scale` taken out, so
  a slow-motion effect does not slow the run's clock). In a movie it is `frames / 60`, the video's time; in a run in
  real time (a hand test) it follows the machine's clock. `-maxSeconds`, the result hold and a tap's or a drag's
  seconds are in the run's own time; `-goTimeout` and the watchdog are on the machine's clock.
- **Vsync off; 60 fps cap in real time**: the drop-in turns vsync off at boot and keeps it off, so frame pacing never
  depends on the monitor, and in a run that is not a movie it holds `Engine.max_fps` at 60.
- **Never pause or mute on focus loss.** A recorded game's window is never the foreground window. The game's
  handlers of `NOTIFICATION_APPLICATION_FOCUS_OUT`, `NOTIFICATION_WM_WINDOW_FOCUS_OUT` and (a mobile game)
  `NOTIFICATION_APPLICATION_PAUSED` must not pause, open a menu or mute while `AutoPlay.is_active`.
- **Real input is kept away where the engine allows it**: the window is set to never take the keyboard focus
  (`WINDOW_FLAG_NO_FOCUS`), a captured or confined mouse mode is set back every frame (`CAPTURED` and
  `CONFINED_HIDDEN` to `HIDDEN`, `CONFINED` to `VISIBLE`: a game that turns the camera only while the mouse is
  captured reads `AutoPlay.is_active` too), and a recording runs on a Windows desktop of its own, which no real
  keyboard or mouse reaches. A real mouse over a window shown on the screen, and a real gamepad, still reach the game.

## 3. Run flow

1. Boot into the normal first scene. The drop-in (the autoload, in the tree before the first scene) parses the flags,
   opens the files, writes the `start` clock sample and sets the frame size.
2. After the first rendered frame it sets the window's rules, waits 1 s, writes `outputDir/ready.json` and emits
   telemetry `autoplay_ready`.
3. The pipeline creates `outputDir/go`. (No `go` within `-goTimeout` → start anyway, `go_timed_out: true`.) The
   drop-in looks for it every 50 ms. A `go`, `ready.json`, `outcome.json`, `clock.json` or `watchdog.json` left in
   `outputDir` by an earlier run is deleted at boot.
4. On go: clock sample `go`, the engine's random numbers seeded again, telemetry `run_start`, then the signal
   **`start_scenario(n)`** is emitted: the game's handler loads the scenario's scene and applies its start state. Skip
   menus, tutorials and popups in AutoPlay. Nothing connected to the signal ends the run at once with result `error`
   (telemetry `error` says why).
5. When gameplay begins, the game calls **`AutoPlay.scenario_started(name)`** (telemetry `scenario_start`, with the
   scenario's name, e.g. "First Night") and the bot starts. The bot acts only while `AutoPlay.is_running` (from go to
   `finish_run`). The first call of a run marks the scenario's start; a later one (after an in-run restart) only adds a
   row. A call before go or after `finish_run` is ignored.
6. The game emits telemetry as things happen (section 5) and calls `AutoPlay.set_score` when the score changes.
7. The run ends with **`AutoPlay.finish_run(result, score, extra)`**: `win`, `lose`, `abort` (bot stuck, the game's
   call), or `timeout`, called by the drop-in when `maxSeconds` of the run's time have passed since go (connect to
   `AutoPlay.timeout` to compute a final score and call `finish_run` yourself; otherwise the last `set_score` is the
   score). `error` is the result of a run that could not start its scenario (no handler, a scenario the game does not
   have). Held inputs are released (logged), telemetry `scenario_end`. A restart inside a run ("caught → checkpoint")
   is **not** the end of the run.
8. The drop-in keeps the result screen up 2 s, writes `outcome.json` and `clock.json` (its `end` sample), telemetry
   `run_end`, closes every file and then **quits the game itself, exit code 0** (`get_tree().quit(0)`: the engine
   ends its movie file on the way out, so the frame of the quit is the movie's last). A game that quits on its own
   during a run (the game quit, the window was closed) writes what it has the same way: `release` rows for the
   controls still held, telemetry `run_aborted` and `clock.json`, no `outcome.json` (but `outcome.json` too when the
   run had ended and only its result hold was left). The recorder ends a game that is still running `-WallSeconds`
   after go and marks the run failed. The drop-in's **exit watchdog** (a thread of its own, any caller: recorder, test
   scripts) ends a process that hangs during a run: no frame for `-autoplayWatchdog` seconds of the machine's clock
   between go and the end → it writes `outputDir/watchdog.json` (`autoplay-watchdog/1`: `reason` `run`) and ends the
   process (exit code 0, as the engine's `OS.kill` gives; the file is the sign). The recorder fails such a run. A
   crash ends the process with its exception code and leaves the files as far as they got: every row line whole (rows
   reach the disk every frame), no `outcome.json`.

## 4. Input rules

- The bot acts **only** through the drop-in, and only while `AutoPlay.is_running`:
  `AutoPlay.hold(control)` / `AutoPlay.hold(control, value)` and `AutoPlay.release(control)` for keys, buttons,
  triggers and sticks (`"<Keyboard>/w"`, `"<Keyboard>/space"`, `"<Mouse>/leftButton"`, `"<Gamepad>/buttonSouth"`,
  `"<Gamepad>/dpad/up"`, `"<Gamepad>/rightTrigger"` with 0..1, `"<Gamepad>/leftStick"` with a `Vector2`),
  `AutoPlay.release_all()`, `AutoPlay.mouse_delta(Vector2)` for look (viewport pixels of one frame; call it every
  frame the bot turns), `AutoPlay.scroll(y)`, `AutoPlay.set_cursor(pos)` for pointing, and for a touch screen
  `AutoPlay.touch_down(finger, pos)`, `touch_move(finger, pos)`, `touch_up(finger)`, `tap(pos, hold_s, finger)`,
  `drag(points, over_s, hold_s, finger)` and `back()`. Never call gameplay methods to act (no `spawn_tower()`, no
  teleporting, no setting velocity), and never send input events yourself (they would not be logged). Reading game
  state directly is fine.
- **A desktop game's bot plays by keys, mouse and gamepad; a mobile game's bot plays by touch only**, as its players
  do.
- A control path is written as an input-system path, so `inputs.jsonl` reads alike across engines: `<Keyboard>/` and a
  key (`a`..`z`, `0`..`9`, `space`, `enter`, `escape`, `tab`, `backspace`, `leftShift`, `leftCtrl`, `leftAlt`,
  `upArrow`, `downArrow`, `leftArrow`, `rightArrow`, `f1`..`f12`, `numpad0`..`numpad9`, `comma`, `period`, `slash`,
  `minus`, `equals` ..., or the engine's own name of a key, as `OS.get_keycode_string` gives it); `<Mouse>/`
  `leftButton`, `rightButton`, `middleButton`, `forwardButton`, `backButton`; `<Gamepad>/` `buttonSouth`,
  `buttonEast`, `buttonWest`, `buttonNorth` (or their aliases `a`, `b`, `x`, `y`, `cross`, `circle`, `square`,
  `triangle`), `leftShoulder`, `rightShoulder`, `leftTrigger`, `rightTrigger`, `start`, `select`, `leftStickPress`,
  `rightStickPress`, `dpad/up|down|left|right`, `leftStick`, `rightStick`; `<Touchscreen>/touch0` .. `touch9` (a
  finger) and `<Touchscreen>/back`. Any other path does nothing and writes one `error` telemetry row per path.
- **Positions and directions are Godot's own**: a position is in viewport pixels, origin top left (what
  `get_viewport().get_mouse_position()` and an event's `position` read), x right and y down; a mouse delta and a
  stick are x right, y down too.
- A held control stays down until released (`hold` with 0, or `Vector2.ZERO` for a stick, releases it too); the
  drop-in logs `down`, `hold` (once per frame while it is held, with the current value) and `up`.
- **Touch.** `touch_down` / `touch_move` / `touch_up` are one finger's contact, sent as `InputEventScreenTouch` and
  `InputEventScreenDrag` with the finger as `index`; a held finger is logged like a held control, its value the
  position. `tap(pos, hold_s := 0.0, finger := 0)` puts a finger down and lifts it the next frame, or after `hold_s`
  seconds (a long press, a button kept down). `drag(points, over_s, hold_s := 0.0, finger := 0)` puts it down at the
  first point, moves it through the others evenly over `over_s` seconds, keeps it at the last for `hold_s` seconds,
  then lifts it: a swipe, a slider, a virtual stick pushed over and held there. The drop-in carries a tap or a drag
  out by itself, frame by frame; taps and drags of different fingers overlap (two thumbs), and a new touch of a finger
  ends that finger's earlier one. With `input_devices/pointing/emulate_mouse_from_touch` on (the template's setting),
  a touch presses the `Control` under it as on a phone.
- **The back button.** `back()` is Android's back button: the go-back request a phone sends
  (`NOTIFICATION_WM_GO_BACK_REQUEST` to every node, and the root window's `go_back_requested`), then the key
  `KEY_BACK` down for one frame. It is logged as `<Touchscreen>/back`.
- The gamepad is device 0. A game that shows button prompts for the device last used switches them when the bot first
  uses a gamepad control.
- Every decision the bot needs must be reachable by input. If something is only reachable by clicking UI (build
  panels, upgrade buttons), point and click with `set_cursor` + `<Mouse>/leftButton`, or tap it (`Control` nodes see
  both), or add an input action for it.
- **Cursor-based picking**: the game reads the pointer from the events it gets or from
  `get_viewport().get_mouse_position()`; in AutoPlay that is the bot's cursor, and the video shows no system cursor:
  draw a visible cursor at it so the video shows where the bot points.
- An input reaches the game inside the call that sends it: the drop-in flushes the event at once, so the game's
  `_input` handlers run before `hold` returns and `Input.is_action_pressed` is true from then on. A row's `frame` is
  the frame the game saw the input in.

## 5. Files in outputDir

All JSON is UTF-8 without a BOM, LF line ends; `*.jsonl` has one object per line. Every row carries the same stamp:

- `qpc`: the machine's clock, the engine's monotonic clock in microseconds (`Time.get_ticks_usec()`, on Windows the
  performance counter counted from the engine's start); `qpc_frequency` is 1000000;
- `t_ns`: `qpc * 1e9 / qpc_frequency`, the same reading in ns;
- `frame`: `Engine.get_process_frames()`, the engine frame, counted from 0. In a movie this is the movie's frame
  number: what the game drew in frame f is the movie's frame f (measured over every frame of a run);
- `t`: the run's own time in seconds since go (section 2), `null` before go. In a recording `t` is the video's time:
  `gameplay.mp4` starts at go, so a row with `t` 3.2 is 3.2 s into the video.

Rows reach the disk at the end of every frame; `ready.json`, `outcome.json` and `clock.json` are written whole and
then renamed into place, so whoever waits for one never reads half of it.

### `inputs.jsonl` (written by the drop-in)

```json
{"t_ns":176876000,"qpc":176876,"frame":0,"t":null,"type":"header","schema":"autoplay-inputs/2","autoplay_version":1,"engine":"godot","game":"TideFinal","run_id":"r1","scenario":1,"scenario_name":"","seed":7,"skill":0.6,"max_seconds":60,"qpc_frequency":1000000,"build_commit":"abc1234"}
{"t_ns":...,"qpc":...,"frame":92,"t":0.5,"type":"control_info","key":"<Keyboard>/w","actions":["move_forward"]}
{"t_ns":...,"qpc":...,"frame":92,"t":0.5,"type":"inject","key":"<Keyboard>/w","value":1,"edge":"down"}
{"t_ns":...,"qpc":...,"frame":93,"t":0.516667,"type":"inject","key":"<Keyboard>/w","value":1,"edge":"hold"}
{"t_ns":...,"qpc":...,"frame":254,"t":3.2,"type":"inject","key":"<Mouse>/delta","value":[12.0,-3.0],"edge":"impulse"}
{"t_ns":...,"qpc":...,"frame":242,"t":3.0,"type":"cursor","key":"<Mouse>/position","value":[960.0,540.0]}
{"t_ns":...,"qpc":...,"frame":254,"t":3.2,"type":"inject","key":"<Gamepad>/leftStick","value":[0.5,-1.0],"edge":"down"}
{"t_ns":...,"qpc":...,"frame":92,"t":0.5,"type":"inject","key":"<Touchscreen>/touch0","value":[540.0,1536.0],"edge":"down"}
{"t_ns":...,"qpc":...,"frame":93,"t":0.516667,"type":"inject","key":"<Touchscreen>/touch0","value":[540.0,1526.4],"edge":"hold"}
{"t_ns":...,"qpc":...,"frame":184,"t":2.033333,"type":"inject","key":"<Touchscreen>/touch0","value":[540.0,672.0],"edge":"up"}
{"t_ns":...,"qpc":...,"frame":332,"t":4.5,"type":"inject","key":"<Touchscreen>/back","value":1,"edge":"down"}
{"t_ns":...,"qpc":...,"frame":422,"t":6.0,"type":"release","key":"<Keyboard>/w","value":0,"edge":"up"}
```

`type`: `header` | `control_info` (the bot's first use of a control: the game's input actions it drives, as the
`InputMap` names them) | `inject` (`edge` = `down` when a control is pressed or a finger put down, `hold` once per
frame while it is held (written at the end of the frame, or at once when its value changes: a finger that moved), `up`
when it is released, `impulse` for a mouse delta or scroll, which last one frame) | `release` (an `up` the drop-in
writes itself for a control still held when the run ends) | `cursor` (a `set_cursor` that moved the pointer). `key` is
the control's path in its canonical spelling (`<Gamepad>/a` is logged as `<Gamepad>/buttonSouth`); `value` is what the
bot put into the control (1/0 for a key or button, 0..1 for a trigger, `[x, y]` for a stick, a mouse delta, a scroll, a
position or a finger; a finger's `up` carries where it was lifted).

### `telemetry.jsonl` (drop-in rows + your game's rows)

```json
{"t_ns":...,"qpc":...,"frame":62,"t":0.0,"event":"scenario_start","scenario":1,"scenario_name":"Tide Run","scene":"res://scenes/Arena.tscn"}
{"t_ns":...,"qpc":...,"frame":122,"t":1.0,"event":"score","score":1,"delta":1,"reason":"progress"}
{"t_ns":...,"qpc":...,"frame":1874,"t":30.2,"event":"guard_state","guard":"Guard_2","from":"patrol","to":"suspicious"}
```

Written by the drop-in: `header` (the same fields as inputs.jsonl's, `schema` `autoplay-telemetry/2`),
`autoplay_ready` {`window` [w, h], `viewport` [w, h]: the frame's size, `fullscreen_mode`, `renderer`, `vsync_mode`,
`target_fps`, `fixed_fps`, `movie`}, `run_start` {`scenario`, `seed`, `skill`, `go_timed_out`}, `scenario_start`
{`scenario`, `scenario_name`, `scene`: the current scene's file}, `scenario_end` {`result`, `score`, `extra`},
`run_end`, `run_aborted` {`phase`: `boot`, `waiting_for_go` or `running`}, `error` {`message`}. Written by the game
with `AutoPlay.telemetry(event, fields)` (a dictionary: strings, numbers, bools, `Vector2`/`Vector3` as arrays, a
`Quaternion` as its euler angles `[pitch, yaw, roll]` in degrees, arrays and dictionaries of those; the keys `t_ns`,
`qpc`, `frame`, `t` and `event` are the drop-in's and are left out), from boot to the end of the run: on every game,
`score` {score, delta, reason} on every change, `state` at 10 Hz {player position `[x, y, z]` m (Y up), rotation
`[pitch, yaw, roll]`, velocity, plus the game's own numbers} and `restart` {reason} for in-run restarts; add the
genre's own events (waves, checkpoints, laps, detections...) freely.

### `outcome.json` (drop-in; your part is the arguments of `finish_run`)

```json
{"schema":"autoplay-outcome/2","autoplay_version":1,"engine":"godot","game":"TideFinal","run_id":"ok","scenario":1,"scenario_name":"Tide Run",
 "seed":7,"skill":0.6,"max_seconds":60,"qpc_frequency":1000000,"build_commit":"abc1234","result":"win","score":21,
 "duration_s":6.0,"run_duration_s":6.0,"go_qpc":6761118,"scenario_start_qpc":6761417,"scenario_end_qpc":14673096,
 "frames":360,"inputs_injected":216,"go_timed_out":false,"build_config":"release","engine_version":"4.7.2-stable",
 "renderer":"forward_plus","viewport":[1920,1080],"fixed_fps":60,"movie":true,"go_frame":72,"scenario_start_frame":72,
 "scenario_end_frame":432,"end_frame":552,"extra":{"time_s":6.02,"reached_goal":true}}
```

`game` = the player's exe name (`<Game>.exe`; the project's name for a game run from its source); `duration_s` =
scenario_start → scenario_end and `run_duration_s` = go → scenario_end, both in the run's own time; `frames` = frames
from scenario_start to scenario_end; `scenario_start_qpc` and `scenario_start_frame` are null (and `duration_s`,
`frames` count from go) when the game never called `scenario_started`; `inputs_injected` = the `inject` rows of
inputs.jsonl; `build_config` = `release` or `debug`; `renderer` = the rendering method the game ran on
(`forward_plus`, `mobile`, `gl_compatibility`); `viewport` = the frame's size; `movie` and `fixed_fps` = whether the
engine wrote a movie, and its frames per second (0 without one); `go_frame`, `scenario_start_frame`,
`scenario_end_frame`, `end_frame` = the engine frames of those moments (the recorder cuts the movie at `go` and
`end`). Put game-specific results in `extra` (stars, lap times, times spotted, shots used).

### `clock.json` (drop-in)

```json
{"schema":"autoplay-clock/2","scenario":1,"scenario_name":"Tide Run","qpc_frequency":1000000,"t_ns_definition":"qpc * 1e9 / qpc_frequency","fixed_fps":60,
 "samples":[{"label":"start","qpc":3423273,"qpc_after":3423277,"t_ns":3423273000,"unix_ns":1794817336525000192,"utc":"2026-11-16T08:22:16.525Z","frame":0}, "go", "end"]}
```

Each sample pairs the machine's clock (read before and after) with UTC wall time and the engine frame. A run that
ended early has the samples it reached (`start`, ..., `end`).

### `ready.json`, `go`, `game.log`, `watchdog.json`, the movie

`ready.json` {`pid`, `title`, `window` [w, h], `viewport` [w, h], `fullscreen_mode`, `scenario`, `scenario_name`,
`autoplay_version`, `t_ns`, `qpc`, `frame`, `t`}; `go` (any content) from the pipeline; `game.log`, the engine's log
(`--log-file`), where the drop-in's own lines start with `AutoPlay:`; `watchdog.json` only from the exit watchdog;
`movie.avi`, the engine's movie when the recorder asked for one. Kept in the raw run directory, not part of the
dataset bundle. The drop-in writes no sound file: a recording's sound is the movie's.

## 6. The game's side

Before this, a game already starts every scenario from `-scenario <n>` alone (past menus, tutorials and popups),
never pauses or mutes on focus loss (section 2) and has every action reachable by input (section 4); its design doc
and the README's Scenarios table list scenarios 1..n (name, start state, win/lose).

**A game made from the template** has the autoload `Scenarios` (`game/scenarios.gd`): fill in `SCENES` (scenario n's
scene at index n - 1) and `NAMES`. It already loads scenario n from `-scenario <n>` and from AutoPlay's
`start_scenario`, and finishes a run that names a scenario it does not have with result `error`. The scenario's code
then does the rest:

```gdscript
# When gameplay begins in the loaded scene (Scenarios.current says which scenario; 0 in normal play):
Scenarios.started()                                  # AutoPlay.scenario_started(<its name>): the bot starts

# When it ends:
AutoPlay.finish_run("win", score, {"stars": 2})
```

`AutoPlay.is_active`, `scenario_argument`, `scenario`, `scenario_name`, `seed`, `skill`, `max_seconds` and
`output_dir` can be read from anywhere at any time (the command line is read when the autoload is made, before any
other autoload). Outside AutoPlay every call does nothing, so the game's code calls them unconditionally.

The bot is the game's own node, added when the scenario starts in AutoPlay, acting only while `AutoPlay.is_running`,
reading game state and calling the input API of section 4, scaled by `AutoPlay.skill` and human-like: eased camera
turns (no snapping), reaction delays, aim noise, no jump spam; on a mobile game, taps and drags on the game's own
controls. It counts its time from the `delta` of `_process`, which is the run's time.

## 7. Testing by hand and declaring readiness

1. Build the player: `Scripts/godot.ps1 build`.
2. Run one scenario as a recording would:
   `Scripts/godot.ps1 autoplay -Scenario 1 [-MaxSeconds 120] [-Seed 0] [-Skill 1]`. It starts the built player with
   the contract's flags plus `-goTimeout 0` (no recorder, so no `go` file; the run starts at once and
   `go_timed_out` is true) and `-autoplayMute`, through the limiter (a GPU slot), on a Windows desktop of its own:
   nothing shows on the screen and the keyboard, the cursor and the speakers stay with whoever uses the machine
   (`-Audible` lets the sound play). It runs in real time and writes no movie. The run's files go to
   `Logs/autoplay/<time>_s<n>/`, and the mode prints a summary of them.
3. Check the run's files: every file of section 5 present and well formed, `inputs.jsonl` has injected input,
   `telemetry.jsonl` has `scenario_start` and `scenario_end`, `outcome.json` has a result and no `error` rows say
   something is wrong. The recording pipeline's run checker checks the same folder and must say PASS:
   `powershell -ExecutionPolicy Bypass -File <root>\godot-game-factory\tools\godot-pipeline\validate-run.ps1 <the run's folder>`
   ([godot-pipeline.md](godot-pipeline.md#validation-per-run); `go_timed_out` is only a note in a hand test). The
   sound is checked on the recording, whose movie carries it. The bot plays like a human, but its score never holds
   up a release.
4. When scenario 1 passes, commit and tag it `milestone/autoplay-1` (later: `milestone/autoplay-<n>` = scenarios 1..n
   work; the pipeline records scenarios 1..n of the newest such tag reachable from the commit), take the
   framing-gate screenshots (godot-game-session skill) and record the scenarios yourself:
   `powershell -ExecutionPolicy Bypass -File <root>\godot-game-factory\tools\godot-pipeline\pipeline.ps1 <slug> -Scenarios <n,...>`
   ([godot-pipeline.md](godot-pipeline.md#pipeline)). A recording does not need the screen, so it waits for nobody;
   the game's lock and the limiter keep runs apart. One run per scenario, never again to improve how the bot plays.
   A coordinated session then reports the result to the coordinator (the commit, the tag, the scenarios, the bundle
   paths).

Changes to this contract go through the coordinating session; the drop-in's version (`autoplay_version`, 1) goes up
when the files change shape, and every game then runs `install.ps1` again. The files are `autoplay-inputs/2`,
`autoplay-telemetry/2`, `autoplay-outcome/2`, `autoplay-clock/2` and `autoplay-watchdog/1`, with `"engine": "godot"`
in every header.

## Naming rule (game side)

The names **Superposition**, **game-factory** and **godot-game-factory** (case-insensitive, including `game_factory` /
`gamefactory`) must not appear anywhere in a game: repo files, code, comments, settings, scripts, commit messages,
builds, logs, in-game files, or anything passed to the game process; agent, model and provider names stay out too (the
godot-game-session skill's "Names"). Everything else stays as it is: recording and workflow traces are fine and
`workflow.jsonl` stays in the repo. The drop-in follows this: its files, its rows and the commit and row `install.ps1`
writes name none of them. Words like recording, dataset, pipeline, workflow row ids in commit messages and
`workflow.jsonl` are fine.
