# Task probes: the contract for `probe` checks

How a task author writes the checks that decide whether a game task passes. It goes with the task format
([schemas/game-task.schema.json](schemas/game-task.schema.json), `GameTask`, game-task/1) and the `godot-write-tasks`
skill ([skills/godot-write-tasks/SKILL.md](../skills/godot-write-tasks/SKILL.md)), and `tools/validate-game.py` checks
every rule below that can be checked without running the game.

**Pass/fail is deterministic.** A task passes or fails only on checks the checker computes from the running game or
from the project: `build`, `boot`, `log_absent` and `probe`. A model judge never decides pass/fail, and nothing is
graded from pixel statistics of the game's frames except one: the frame's mean luminance (`screen`, section 2.15),
whose threshold is always calibrated or relative to the start, so the same machine measures both sides. Judges
(`judge`, `code_judge`) stay as **non-gating** quality checks (`"required": false`). Nothing in a task reads the
agent's tool calls: a task is graded on the game's outcome alone.

Words used here:
- **the start**: the game at the task's `seed.commit`, as the agent receives it;
- **the fix**: the developers' own solution, `seed.reference` (for a feature or a change, their own implementation of
  it; `tools/validate-game.py` refuses a task without one);
- **the checker**: what prepares, plays and measures a game for a task, the same way for the start, the fix and an
  agent's result;
- **the task check**: what makes a task valid before any agent is given it (section 4);
- **an object**: a node. Its **parts** are itself and the nodes below it. A node is **shown** when it is in the tree
  and neither it nor anything above it is hidden (`visible` off); only shown nodes are selected unless a select says
  `"inactive": true`;
- **a class**: what a select's `component` names: an engine class (`MeshInstance3D`, `CharacterBody3D`; the classes it
  inherits match, so `Node3D` takes every 3D node), a script's `class_name`, or a script's file name without its
  extension (`coin` for `coin.gd`); a script that extends another matches the other's too;
- **the player**: the first node the task's `player` select matches (an object select, section 2.4), when the task
  has one; then nothing else is tried, so a select that matches nothing leaves the play without a player. Else the
  first shown node of the group `player` (or `Player`), else the first shown `CharacterBody3D`, else the first
  shown `CharacterBody2D` (of several, the first in tree order, the same in every play: section 2.1), else the
  camera below. Where that could find the wrong node (two in the group, say), name it with the task's `player`;
- **the camera**: the window's current `Camera3D`, else its current `Camera2D`;
- **the frame**: what the game's window shows. A rectangle or a point of it is written in fractions 0-1 from its top
  left, y down, so it reads the same at every size.

Units are the engine's: metres, metres per second, degrees. Y is up and -Z is forward. `pitch`, `yaw` and `roll` are
a node's rotation in the world, its `global_rotation_degrees` x, y and z (a child's `rotation_degrees` in a scene
file is relative to its parent instead), normalised to (-180, 180]: yaw 0 looks along -Z and a positive yaw turns
left; a positive `pitch` looks up. A 2D node (a `Node2D`, a `Control`) reads its global position in the engine's 2D
units, y down, as `x` and `y` with `z` 0, and its rotation as `roll`.

## 1. The check

```json
{
  "name": "hero_on_ground",
  "kind": "probe",
  "required": true,
  "weight": 3,
  "needs": ["boots_clean"],
  "describe": "Two seconds after the scenario starts, the hero stands on ground near the west kiln tower instead of falling under the town.",
  "play": "look",
  "measure": { "probe": "player", "field": "y", "window": [3, 18], "agg": "min" },
  "expect": { "op": ">=", "calibrate": 0.5 }
}
```

- `describe` (required, at most 400 characters): the assertion in plain English, shown in the grade (never to the
  agent).
- `play`: where the measurement is taken (section 1.1).
- `measure`: what to measure (section 2). Every measure reduces to **one number** (booleans are 0/1).
- `expect`: the threshold that number is compared with (section 1.2).

What a required probe and its play rely on is either in the instruction or at the start commit: a node, class,
group, property or scene name, an exact string or regular expression, a coordinate, a run of inputs. A name the
thread creates, a text the instruction doesn't quote, a point where the reference placed something, keys that only
work on the reference's layout: a correct solution made another way reads as absent. So read what the player sees:

- on-screen text through `ui` with a loose `match` (`(?i)` for any case, `\s*` between words, `\d+` for a number),
  never an exact string the instruction doesn't quote;
- nodes by a group or class the start has, or by what they carry (`has`) or where they are (`near`);
- a place by `teleport_to` or `pin` on a node, never by raw coordinates of something a build places itself;
- a control by its name at the start, or a touch on what is drawn there.

Ask of each check: would a correct solution that names things otherwise, lays the scene out otherwise, or hides a
thing instead of removing it still pass? If not, move the probe to what the player sees.

### 1.1 Plays

- `"look"`: the checker's idle play of the task's `play_scene`: 20 s, no input, sampled every 0.5 s.
- `"drive"`: the checker's scripted drive of `play_scene`: 22 s, `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s,
  `<Keyboard>/w` 8-13 s with a jump (`<Keyboard>/space`) at 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s;
  sampled every 0.5 s.
  On a mobile game (its `Platform.json`) the same route by touch: a left thumb down at the lower left of the screen
  (`[0.15, 0.75]`) pushed up, right, up, left, up at those times and held there, and a tap at the lower right
  (`[0.85, 0.75]`) at 9 s.
- **A mobile game's plays** (every one: the checker's own and a task's) run at the phone's size, 1920x1080 for a game
  held in landscape and 1080x1920 for one held upright, drawn with the renderer the game's project names. The checker
  reads that from the copy's `Platform.json` ([game-format.md](game-format.md), "Platform"); a desktop game's plays
  are 960x540. Nothing in a task says or changes it. The size holds on any display: it is the frame's, whatever the
  window is (a phone held upright is taller than most screens), since the probe sets the frame's size itself.
- A **task play**, when the outcome needs other input or another start:
  ```json
  {"name": "aim_left", "seconds": 12, "every": 0.5,
   "scene": "res://scenes/Level2.tscn", "args": ["-scenario", "2", "-devmenu", "2:quest=bull,6:fell"],
   "inputs": [{"t": 0.2, "teleport": [12.0, 1.8, -3.4], "yaw": 90},
              {"t": 1.0, "key": "<Keyboard>/w", "press": true}, {"t": 3.0, "key": "<Keyboard>/w", "press": false},
              {"t": 4.0, "key": "<Mouse>/delta/x", "axis": -40.0},
              {"t": 6.0, "cursor": [0.5, 0.6]}, {"t": 6.1, "key": "<Mouse>/leftButton", "press": true},
              {"t": 6.2, "key": "<Mouse>/leftButton", "press": false},
              {"t": 8.0, "widget": "RetryButton", "click": true}]}
  ```
  - `name`: lowercase letters, digits and `_`, at most 32, and not `look` or `drive`. A check can't point at another
    check's play by its name: every check that reads a task play carries the whole play, and plays with the same name
    in one task must be identical (the play then runs once per side for all of them).
  - `seconds`: a whole number, 5-120. No input at or after the end.
  - `every`: the sampling step, 0.1-1.0 s (default 0.5). A play samples on the first frame at or after each step, from
    1/30 s to its `seconds` plus 0.5, so a step that isn't a whole number of frames alternates (0.25 s: 0.267, 0.5,
    0.767, 1.0, ...): keep window edges off the exact moment something happens.
  - `scene` (optional): the scene this play opens instead of the task's `play_scene` (`null`: the project's main
    scene). Like `play_scene`, it is the scene's own path in the project (`res://scenes/Arena.tscn`): the validator
    refuses one with a `.` or `..` part or an empty part (`//`, or a `/` at its end).
  - `args` (optional): the game's command-line arguments for this play instead of the task's `play_args` (`[]`:
    none), at most 16, each `^-?[A-Za-z0-9_.:=,/-]{1,60}$`. An element starting with `-` and a letter is a flag
    (`-scenario`, `-devmenu`); anything else is a value (`2`, `2:quest=bull,6:fell`). They reach the game as its user
    arguments (`OS.get_cmdline_user_args()`, what follows `--` on the engine's command line), after the probe's own.
    Never the probe's own (any flag starting with `taskprobe`, any case), and never one that would choose the
    renderer or the frame's size (`--rendering-method`, `--rendering-driver`, `--resolution`, `-size`);
    `tools/validate-game.py` lists what it refuses.
  - `after` (optional): the task plays that run, and end, before this one on each side:
    `{"name": "reads_save", "seconds": 10, "after": ["writes_save"]}` (1 to 8 names). Names are task plays of the
    same task (a probe's play or a judge's own `plays`), never `look` or `drive`, never the play itself, never a
    cycle; `tools/validate-game.py` refuses each. **A play that reads what another play writes names it in `after`.
    Never rely on the checker's order:** without `after`, a side's plays run in the order its checks first ask for
    them, which is not the order the task lists them in and can change. A play that failed or was cut short still
    counts as run: the plays after it run anyway and read whatever it left, so the failure shows in their own checks.
    A play with `after` starts on the saved data left by the plays it names and the plays those name, in order, and
    on nothing else's (see "Saved data" below). When it names two, one of them runs after the other through its own
    `after` (listed in either order), or the validator refuses the task: a play without `after` clears the saved data
    when it starts. A play ends as a window its player closes does: the game gets
    `NOTIFICATION_WM_CLOSE_REQUEST`, then the tree exits (`_exit_tree`), so what a writer saves there is saved; what
    it would save only later (a deferred call, a thread) may not be, so a writer is best made to save during its
    play.
  - `inputs` (at most 400; a play with none leaves the key out), each at time `t` (seconds of play, 0-120). They reach
    the game as the engine's own input events (`InputEventKey`, `InputEventMouseButton`, `InputEventMouseMotion`,
    `InputEventJoypadButton`, `InputEventJoypadMotion`, `InputEventScreenTouch`, `InputEventScreenDrag`), so the
    game's `_input` and `_unhandled_input`, its Controls and its input actions (`Input.is_action_pressed`) take them
    as a player's. One sent at `t` is delivered in the frame of `t`, before the game's `_process` of that frame; its
    `_physics_process` reads it from the next frame.
    - a key: `{"t": 1.0, "key": "<Keyboard>/w", "press": true}` and later `"press": false`. `key` is a control path,
      `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$`, written as the other factories' plays write it, so a route
      reads alike across engines: a key of `<Keyboard>/` by its Input System name (`w`, `space`, `enter`, `leftShift`,
      `f2`, `escape`, `upArrow`, `numpad1`) or by the engine's own name (`up`, `shift`, `pageup`), any case (left and
      right modifiers are one key); on `<Mouse>/`, `leftButton`, `rightButton`, `middleButton`, `forwardButton`,
      `backButton`; on `<Gamepad>/`, `buttonSouth` (the engine's A), `buttonEast`, `buttonWest`, `buttonNorth`,
      `leftShoulder`, `rightShoulder`, `start`, `select`, `leftStickPress`, `rightStickPress`, `dpad/up`, `dpad/down`,
      `dpad/left`, `dpad/right`. A key event carries the key as both `keycode` and `physical_keycode`, so an action
      bound either way takes it. Any other control is a line in the play's `query_errors`, and nothing is pressed. In
      a mobile game's play `<Keyboard>/escape` is the phone's back button (section 1.3);
    - an axis event: `{"t": 2.0, "key": "<Mouse>/delta/x", "axis": 40.0}` (`axis` -1000 to 1000), on `<Mouse>/`
      `delta/x`, `delta/y`, `scroll/x`, `scroll/y` or `<Gamepad>/` `leftStick/x`, `leftStick/y`, `rightStick/x`,
      `rightStick/y`, `leftTrigger`, `rightTrigger`. A mouse delta is one mouse movement of that many pixels
      (`InputEventMouseMotion.relative`; y down); a scroll is that many notches of the wheel (a positive `scroll/y`
      turns it up), each a press and a release of the wheel's own button; a stick or a trigger keeps its value (-1
      to 1) until set again, and a stick's y is up-positive (see the lessons on mouse axes in section 5);
    - a widget click: `{"t": 6.0, "widget": "RetryButton", "click": true}` clicks the first visible (as the `widgets`
      field reads it, so a fully transparent button counts) Control that takes a click (not disabled, not ignoring
      the mouse) whose name (a wildcard) or class matches, as a player's click presses it: the mouse moves to its
      centre, the left button goes down and, a frame later, up. They are real mouse events, so a Control drawn over
      it takes them instead, as it would a player's. The play's `probe.log` names what it clicked and its class:
      `clicked RetryButton (Button)`. No match, or a button that didn't press: nothing else happens, and the click is
      listed in `probe.json` `inputs_missed`;
    - the cursor: `{"t": 1.0, "cursor": [0.5, 0.6]}` moves the mouse to a point of the frame (fractions 0-1, y down
      from the top; it starts at the centre); a following `<Mouse>/leftButton` press and release clicks there;
    - a teleport: `{"t": 0.2, "teleport": [x, y, z], "yaw": 90}` puts the player's own position (its origin) at that
      point (m), facing `yaw` (degrees; 0 when left out: a teleport always turns a 3D player), at once: the game's
      scripts of that frame already find the player there. It is the way to reach a test spot. The probe doesn't
      move it to the ground or out of a body afterwards: take the point from where the player stands in a play (the
      `track` of its `probe.json`). A 2D player goes to `x`, `y` and isn't turned;
    - a teleport next to an object: `{"t": 0.2, "teleport_to": <object select>, "distance": 2.0, "offset": [x, y, z],
      "face": <Point>}` places the player `distance` m (default 2; 0 to 1000) from the object the select matches
      nearest to the player, position to position (the player and the nodes below it left out; of two as near, the
      first in tree order), on the player's side (behind the object, on the side its back is to, when the player
      stands right above it) and level with it, plus `offset` (default none), facing `face` (a point, section 2.13)
      or else that object (with nothing to face within a centimetre on the ground, it keeps its own yaw). The way to
      reach a spot each build chooses itself (the ore a fix placed, a door it moved).
      **Level is origin to origin**: the player's own position goes to the height of the object's position plus
      `offset`'s y, and nothing then moves it to the ground or out of a body (next to a coin hovering 0.8 m up,
      `"offset": [0, -0.8, 0]` puts a player whose origin is at its feet on the ground). The offset is the task's,
      the same for every build: where each build chooses the height (a thing the task adds), no offset fits them
      all, so leave it out when the game takes a player level with the thing. **A select matches every node that
      fits it, and the nearest wins**: `{"name": "Coin*"}` also takes a `CoinSpawner`, and a player standing beside
      the spawner goes there; select the things themselves, by their exact name or their own class where the start
      has them too, and by what they carry (`has`) where the task adds them, since another solution would name them
      otherwise (section 2.4). No match: nothing happens. The play's `probe.log` says what each one did,
      `teleported next to <name>: asked (x, y, z) yaw <degrees>, now at (x, y, z)` or
      `teleport_to skipped (no object matches)`: check it in the fix's play;
    - holding the player there: `"hold": 5` on a `teleport` or `teleport_to` (seconds, up to 120) puts the player back
      at the spot (its position; its view stays free) for that many seconds of play, before the game's scripts of
      every frame and again after them, so a camera that follows the player frames the spot; a hold lasts through a
      `wait`. For a game that sets its player's place every frame, which would otherwise undo a teleport at once.
      Without `hold`, a teleport places the player once;
    - a wait in real time: `{"t": 8.0, "wait": 30}` (seconds, more than 0). Plays run on a fixed 30 fps clock as fast
      as the machine renders, so what runs on the wall clock (a timer on `Time.get_ticks_msec()` or the system
      clock, a web request) sees less real time than the play's seconds. At `t` the play's clock holds while the game
      keeps running, paced to real time, until `wait` real seconds and `wait` seconds of game time have both passed;
      nothing is sampled, sent or screenshot meanwhile; then the play goes on from `t`. A play's waits add at most
      300 s in all, and its timeout grows by them; `seconds`, windows and `at` stay in play time, within 120 s;
    - a named screenshot: `{"t": 6.0, "shot": "pause_menu"}` (a letter or `_` first, then letters, digits, `_`; up to
      32) takes `shot_pause_menu.png` at that moment, with the UI, beside the evenly spaced ones. Each name once in a
      play, 20 at most. A picture never passes or fails anything by itself: it is for a judge (section 3.2) and for
      whoever reviews a run;
    - a scene load: `{"t": 10.0, "scene": "res://scenes/Yard.tscn"}` changes to that scene of the project, as the
      game's own `change_scene_to_file` does; the play's clock stands still while it changes;
    - a view turn: `{"t": 10.5, "view": [-15, 90]}` turns the player to the yaw and the camera to that pitch and
      yaw in degrees (pitch -89 to 89, a negative one looks down), once: a camera rig that sets its own rotation
      every frame turns it back, so place the player with `teleport_to` and `face` where that matters;
    - a touch: `{"t": 1.0, "tap": [0.5, 0.6]}` or `{"t": 2.0, "drag": [{"widget": "MoveStick"}, [0.2, 0.6]], "over":
      0.3, "hold": 2.0}`, a finger on the screen (section 1.3);
    - a stage of a contact: `pin` (an object held ahead of the player or at a point), `damage` (a hit through the
      game's `take_damage`), `set` (a property written), section 1.4.

  With these, one launch tours several places and scenes and pictures each: scene, teleport (or `teleport_to` what
  the build placed), turn, shot. **The grader's tour lives in the task**, which the agent never sees, so a build can't
  dress only the spots that are photographed. Place shots by what the build made (`teleport_to`), not by a list of
  views kept in the game itself.
  - A play that measures audio (an `audio` measure, section 2.16) runs paced to real time, so its sounds keep time
    with the game; every other play runs as fast as the machine renders. No play is heard on the machine.

Every play of the game, the checker's own (look, drive, a boot check's) and a task play alike:

- **The scene.** It opens the task's `play_scene`, with the task's `play_args` among the game's arguments
  (`"play_scene": "res://scenes/Harbor.tscn"`, `"play_args": ["-scenario", "2"]`; `play_args` hold at most 16
  items, under the same rules as a task play's `args`), unless a task play has its own `scene` or `args` key. With
  `play_scene` null, the project's main scene plays.
- **The project's main scene** doesn't run when the play opens another one: the engine starts the play's scene in its
  place. The game's autoloads run in every play, whatever scene opens. A game that needs its main scene to run first
  (a boot scene that sets things up and changes scene itself) is started through its own `play_args`
  (`["-scenario", "2"]`) with `play_scene` null.
- **The frame.** The game is drawn at its project's own size, whatever the machine's screen, so its UI is laid out
  as the game shows it. A desktop game's frames are read at 960x540 (its screenshots and `screen` samples are the
  full frame scaled down); a mobile game's at its phone's size, 1920x1080 or 1080x1920. Screenshots are exactly
  that size.
- **The clock.** A play runs at a fixed 30 frames a second (play time is frames / 30, and every `t`, `window` and `at`
  is play time), as fast as the machine renders. Every frame steps the game by 1/30 s: `delta` in `_process` is
  1/30 and two physics ticks run a frame (at the engine's default 60). The clock starts at 0 when the play's scene is
  the current scene, **holds while a scene is changing** (while there is no current scene; for at most 300 frames)
  and during a `wait`, and keeps counting when the game pauses itself (`get_tree().paused`, `Engine.time_scale` 0).
  The wall clock (`Time.get_ticks_msec()`, `Time.get_unix_time_from_system()`) doesn't follow it: a 20 s play takes
  a few seconds of it, a different number every time, so whatever a game drives by it hardly advances in a play and
  differs between two plays. Give it real time with a `wait`.
- **Saved data.** Every play starts from clean saved data, but a task play that names `after`: that one starts on
  what the plays it names and the plays those name saved, in order, and only that (when another play ran since they
  did, the checker plays them once more first, for their saves alone; their checks keep reading their first play,
  the replay's files are kept as `<play>_again`, and a replay that ended otherwise than the first is noted in the
  reader's checks). What is cleared is the game's `user://` folder, and nothing else: a file a game writes anywhere
  else (beside its project, in a folder of the system's) is not. The checker's copy of the game has a user data
  folder of its own (`user://` is `TaskProbe.<hash>`, never the real game's), which the probe empties when a play
  starts clean, before any autoload of the game wakes. The two sides never share saved data.
- **Focus.** The game runs on a Windows desktop of its own ([task-check.md](task-check.md), "The plays"): nothing
  shows on the user's screen, and the play takes neither the keyboard nor the cursor.
- **No build.** The checker plays the commit from its source with the editor binary, after the engine's import and
  a pass that loads every script (task-check.md, "What it does").
- **The end.** When the play's time is up, in this order: the last sample and the last screenshot are taken, the
  probe writes its files, marks the play's end in the game's log, tells the game it is being closed
  (`NOTIFICATION_WM_CLOSE_REQUEST`, as a player closing the window does) and asks the engine to quit. So nothing
  the game does or prints while it closes reaches a sample, a `log` measure or a `log_absent` check. A game that quits
  by itself ends the play there (`"ended": "shutdown"` in its `probe.json`), with the samples taken until then. A
  crash while the game closes still fails a `boot` check: it reads the whole log.

### 1.2 Thresholds (`expect`)

`op` is one of `>`, `>=`, `<`, `<=`, `==`, `!=`. The threshold is one of:

- **A literal value**, `{"op": ">=", "value": 1}`: for facts that don't depend on the scene (counts, booleans). `==`
  and `!=` take literals only (they compare within 1e-9). `op` says on which side the fix lies: a reading that is 0 at
  the start and 1 at the fix (a `match`, `visible`) takes `">="` with 1; the validator can't tell an `op` on the
  wrong side, only the task check does (`start already passes ...`).
- **Calibrated**, `{"op": ">=", "calibrate": 0.5}` with `0 < f < 1`: for continuous quantities. The checker measures
  the start (`s`) and the fix (`r`) in its own environment and sets the threshold `s + f * (r - s)`; `op` says on which
  side the fix lies (`>`/`>=` when `r > s`). `f` places the threshold between the two: 0.5 halfway; nearer 0, a
  solution that moves the value less than the fix did still passes; nearer 1, it must reach nearly as far as the
  fix. Needs `seed.reference`. A required calibrated check whose start and fix
  measure the same (within 1e-6 relative) makes the task invalid. Calibrated thresholds are kept by the checker, never
  written into the task.
- **Relative to the start**, for an outcome the fix is only one fair way of reaching (most features and changes), or a
  task with no fix: `{"op": ">=", "start_times": 1.3}` (threshold `s * 1.3`) or `{"op": ">=", "start_plus": 5}`
  (threshold `s + 5`), measured on the start. It needs a value at the start: a measure that selects only what the
  task adds measures nothing there and is left without a threshold (below), so select what the start has too (the
  fastest spin among every drawn object has a value at the start, 0 where nothing turns; the spin of the new things
  alone has none).

Where the number depends on what a build chose, the threshold is calibrated or relative to the start, never a literal
value, and `tools/validate-game.py` refuses a literal: `objects` `glow` and `spin`; `components` `intensity`,
`extent_*`, `glow` and `spin`; every `screen` field; `audio` `volume`, `max_volume` and `level`. Each section says
why. A `render` field takes a literal: a budget is a number of its own (section 2.20).

When the start can't be measured (its play ended before the window, or nothing the measure selects is there yet, as
in a task that adds it), a calibrated threshold anchors on the fix alone: `r - 0.25 * |r|` for `>`/`>=`,
`r + 0.25 * |r|` for `<`/`<=` (a fix of 0 leaves no threshold, as a quarter of nothing is no margin). When the fix
can't be measured, or the start of a `start_times`/`start_plus` check can't, the task is invalid for that check if
it is required. A probe left without a threshold, this way or by a start and fix that measure the same, fails as
`uncalibrated` on every side; one that isn't required is only a note (section 4).

### 1.3 Touches

A task play may touch the screen as a phone's player does. Two inputs, each with a `finger` (the touch index, 0 to 9,
0 unless said):

- a tap, `{"t": 1.0, "tap": [0.5, 0.6], "hold": 0.5, "finger": 1}`: the finger goes down at the spot `tap` and lifts
  the next frame, or after `hold` seconds (a long press, a button kept down).
- a drag, `{"t": 2.0, "drag": [{"widget": "MoveStick"}, [0.2, 0.6]], "over": 0.3, "hold": 2.0, "finger": 0}` (2 to 16
  spots): the finger goes down at the first spot, moves through the others evenly over `over` seconds (at once
  without it), stays at the last for `hold` seconds, then lifts: a swipe, a slider, a virtual stick pushed over and
  held there.

A spot is a point of the screen `[fx, fy]` in fractions 0-1 from its top left, or `{"widget": "MoveStick"}`: the centre
of the first visible, laid-out widget of that name (a wildcard) or type, whatever its kind (a button, a stick, a
panel): a `Control` node, found as a `widgets` select finds one (section 2.6), by its node name first, then by its
class. Name the widget where you can: its place differs between landscape and portrait, its name does not. A
widget's spot is where it is when the finger goes down.

Touches of different fingers may overlap in time (a stick held while a button is tapped, two fingers pinching). One
finger's touches are at least 0.1 s apart, from one's lift to the next one's start, and every touch is over by the
play's end: the validator refuses a task that asks otherwise. They reach the game as `InputEventScreenTouch` and
`InputEventScreenDrag`, as a touch screen's do: a Control takes them in `_gui_input`, the game in `_input`. The
engine also makes mouse events of the first finger down (`emulate_mouse_from_touch`, which a mobile game keeps on),
and that is what presses a `Button` node: **a `Button` presses for the first finger down alone**, while a control
that reads the touch events itself takes any finger. So tap a `Button` with a finger that is alone on the screen, and
expect a button meant to be pressed beside a held stick to read touches itself. A touch that can't be made is a
miss: a line in the play's `query_errors` (`inputs: the tap at 2.00 s missed: no visible widget matches
'FireButton'`; a finger still down from an earlier touch; a finger outside 0-9) and a row of `probe.json`
`inputs_missed` (kind `tap` or `drag`, with why), and nothing is touched.

Android's back button is the key `<Keyboard>/escape`: `{"t": 3.0, "key": "<Keyboard>/escape", "press": true}` and its
release. In a mobile game's play the press reaches the game as the phone sends it, the window's `go_back_requested`
signal and `NOTIFICATION_WM_GO_BACK_REQUEST`, then the key `KEY_BACK`; a game that left
`application/config/quit_on_go_back` on quits at it, as on a phone. In a desktop game's play it is the Escape key. A
desktop game takes touches too when it reads them, so they are allowed in any task; a mobile game is played by touch,
so its tasks' plays drive it with touches and the back button, never with another key, the mouse or a gamepad.

### 1.4 Staging a contact, and reading it

An ask that only shows after a blow, a shot, a hit taken or a foe falling is checked by making the contact happen at a
time the play knows, then reading what changed. Names come from the task's start commit, never from the instruction.

**Stage it.** A stage that lands on nothing is a miss in `inputs_missed`, and every probe of that play then has no
value on that side, whatever it read ("a stage of the play didn't land: ..."): the check fails there, and the task is
invalid when the fix's play misses.

- `{"t": 2.0, "pin": <object select>, "hold": 3, "front": 1.5, "offset": [x, y, z]}` or, in place of `front`,
  `"at": <Point>`: the match nearest the player (never the player or a node below it; of two as near, the first in
  tree order) is held at its place for `hold` seconds (up to 120) while its own scripts, animation and attacks run
  on: it is put back and its velocity stilled before the game's scripts of every frame and again after them, as a
  held player is (section 1.1), and it still turns, swings and blocks. First it is set `front` m (0 to 1000) ahead
  of the player along the way the player faces (its -Z on the level; a 2D player's +X), at its own height (its y is
  kept: use `at` with the player's point where the ground differs), or `at` a point (section 2.13), plus `offset`,
  and turned to face the player (a 2D node isn't turned). Ahead is the way the player's own node points: many
  players turn only a mesh below them, or flip a sprite, and their node keeps pointing one way, so check where the
  fix's `probe.log` says the pin went, and use `at` with a point where the node doesn't turn. Without `front` and
  `at` it is held where it is. The
  player's own blow or shot, by the task's keys or touches, then lands on it. One of `front` and `at`, not both; a
  pin lasts through a `wait`. A target the build invents has no name the start knows: `{"player": false,
  "component": "CollisionObject3D", "has": {"visible": true}, "near": {"point": {"player": true}, "radius": 6}}`
  is the nearest body that draws near the player; a floor or a wall is one too, so where the nearest is not surely
  the target, the ask is not testable.
- `{"t": 3.0, "damage": 20, "to": <object select>, "from": <object select>}`: a hit through the game's own damage
  method, `take_damage(amount: float, source: Node) -> float`, which every game under the combat rule has on what
  can be hurt ([game-format.md](game-format.md)). `to` takes the match nearest the player (`{"player": true}`: the
  player), and the method is the node's own, else that of the first node below it that has one. `source` is the
  match of `from` nearest the one struck; without `from` it is the player, or, when the player is the one struck,
  the nearest other node that has a `take_damage` (nothing when there is none). The method is called with those
  two arguments; one with more is fine when the others have defaults (`take_damage(amount, source, critical :=
  false)`). What it returns is read back as `damage_taken` (below). No match, a match without the method, or a
  method that can't be called with the two: a miss.
- `{"t": 1.0, "set": "<property path>", "on": <object select>, "value": v, "all": true}`: a property the start
  names, written to set a fight up (a foe's health at 1, so one blow fells it through the game's own death; the
  player's own high, so a staged fight can't end the play), never to decide what the check reads. The path is the
  one a `prop:` field reads (section 2.4), without an array index: `health`, `Health.current`, `position.y`. `on`
  takes the match nearest the player, or every match with `"all": true`. A number or a boolean goes onto a number
  or a boolean, a string onto a string; an enum takes its number. The property's setter runs, as when the game
  writes it. No match, or no matched object with such a property that takes the value (one that reads as before
  after the write, a read-only one, is none): a miss.
- `where` in any object select (section 2.4) keeps the ones a property picks (only foes not dead, a bay's own
  group), and `"player": false` anything but the player. `set` and `where` name only members the task does not ask
  to change.

Without a player in the play, "nearest the player" is the first match in tree order, and a pin `front` is a miss.
The play's `probe.log` says what each stage did: `pinned Foe at (x, y, z) yaw <degrees> for 3.0 s`, `damage 20.0 to
Foe (take_damage of Foe) from Player: it returned 20.0`, `set health to 1.0 on 3 of 3 object(s)`: check it in the
fix's play.

**Read it deterministically**, in a probe one sentence explains:

- a thing gone or there (an `objects` `count`, `hidden`), a state or property the start names (`prop:`);
- a sound that started (`audio` `started_audible` in a window right after the contact, section 2.16);
- **a hit stop** (0.05 to 0.1 s: no screenshot shows it), by the wording of the ask. "The one struck freezes for
  an instant": `objects` `frozen` of it (section 2.4), `"agg": "max"` over a tight window right after the contact.
  It reads the stop however a build makes it: the object's own script holding it, the tree paused, or the game's
  time stopped. "The game holds for an instant": `world` `flow` (section 2.21) with `"agg": "min"` below 1 in that
  window, which a slowed game, a stopped one and a paused tree all read. "Time slows": `world` `time_scale` with
  `"agg": "min"` below 1, the engine's own value. Add a second `world` probe only for what the ask itself says:
  "the rest of the fight plays on" is `flow` `min` == 1; "without pausing the game" is `paused` `max` == 0. Never
  pair a stop with `paused` == 0 otherwise: a build that makes its hit stop by pausing the tree is a fair one. Never read `frozen` on an object a pin or a teleport holds. The start's play must read
  no stop;
- **a stagger, a knock-back or an interrupted action** (behaviour, not looks): the animation that plays in a short
  window after the hit and not before it (`clip` with `match`, an `anim:` parameter); the object unable to act (the
  move key held through the window: its `speed`, or the player's `moved`, near 0, then moving again after it); a
  staggered state the start names; a knock-back as its place moving away from the attacker (`dist` rising);
- `objects` `damage_taken`: what a staged hit did, as the game's `take_damage` returned it (a guard or a shield
  that takes nothing reads 0; an object no stage struck has no value).

**What it looks like** (sparks, colours, glow, readability) goes to the required `looks_as_asked` judge, with its own
play staged the same way and named `shot` frames a few hundredths of a second apart across the contact. A pose may be
an extra rubric item, never the only check of a behaviour.

## 2. Measures

Which measure answers which question (each section has its fields, defaults and limits):

| To check | Measure |
|---|---|
| where the player is, how far it moved, how fast | `player` (2.2) |
| where the camera sits, whether the player is in view or hidden from it | `camera` (2.3) |
| an object: there or not, where, its state (`prop:`, `anim:`), how fast it moves or turns, whether it gives light (`lit`: a lamp, whatever lights it) | `objects` (2.4) |
| one part of an object: a light that is on, a live effect, a mesh, a part that spins | `components` (2.5) |
| one UI widget's own state: a bar's value, a toggle, a picture | `widgets` (2.6) |
| how many objects appeared or went | `spawns` (2.9) |
| a line in the game's log | `log` (2.10) |
| how bright the frame looks on screen | `screen` (2.15) |
| what plays, how loud at the listener, a sound that starts | `audio` (2.16) |
| what the HUD or a menu shows: text, a number, a clock, whether it updates | `ui` (2.18) |
| what the renderer drew, against a budget: draw calls, triangles, texture memory | `render` (2.20) |
| the game as a whole: how slow its time ran, whether it went on, whether it was paused | `world` (2.21) |
| what a blow, a shot or a hit taken did: a short stop, the damage a staged hit did | `objects` `frozen`, `damage_taken` (2.4), with the contact staged (1.4) |

How a play gets there (keys, clicks, teleports, waits): section 1.1; touches: section 1.3; a contact made to happen
(`pin`, `damage`, `set`): section 1.4. Literal or calibrated:
section 1.2. Points and `near`: section 2.13. Why a probe has no value: section 3.

### 2.1 Common fields

- `window`: `[t0, t1]` seconds of play time (ends inclusive), or `at`: `[t, ...]` (at most 40 times, each 0-120; the
  sample nearest each time, when one is within 0.26 s of it) or `"end"` (the last sample); not both. Default: the
  whole play.
- `agg`: how the samples reduce to one number: `min`, `max`, `mean`, `first`, `last`, `delta` (last minus first),
  `any` (1 if any sample is non-zero), `all` (1 if every sample is non-zero), `count` (number of non-zero samples),
  `sum`, `range` (max minus min), `std` (standard deviation), `changes` (how many times the value changes between
  consecutive samples), `rises` and `falls` (how many samples read more, or less, than the sample before: which way a
  value moved, a score that only rises reads `falls` 0, a reset reads as a fall), `step` (the largest change, up or
  down, between two samples next to each other: 0 for one sample). Default `last` (`sum` for `spawns`).
- How a thing moves, as a number ("eases instead of snapping", "gentle", "no sudden moves"): a task play with
  `"every": 0.1` and `"agg": "step"` over the window of the move. A door that snaps 90 degrees open reads a `step`
  of 90; one that turns open over a second reads 10 to 15, by its easing. `max` of a speed tells how fast, `step`
  how abruptly.
- `of` (`objects`, `components`, `widgets`, `ui`): how the selected objects, parts, widgets or UI elements combine
  within one sample: `count` (how many match and have a non-zero value), `any`, `all`, `min`, `max`, `mean`, `sum`,
  `first`. **Default `count`.** A measure that reads a value (a position, an extent, a `prop:`, a text match, a
  percent) needs `"of": "first"` or another value reducer, or it counts instead of reading. With `"field": "count"`,
  `of` is ignored. Nodes match in tree order: the root's children in order (the autoloads, then the scene), each
  followed by what is below it, as the scene dock lists a running game. That order is the same in every play of one
  commit, but the fix may change the scene: select the one you mean (by name, group or `near`) rather than take the
  first of a broad select.
- **Every match counts, past 200.** The probe keeps at most 200 rows a sample in `probe.json` but reads every match:
  `"field": "count"` is the whole selection's size, and `of` (`count`, `any`, `all`, `min`, `max`, `mean`, `sum`) reads
  every match's value from the probe's summary of them (the sample's `total` and `full`). Only `"of": "first"` and
  values read through `match`, `to_angle` or `to_axis` read the first 200 rows alone.
- `to_angle` / `to_axis` (angle fields only: `yaw`, `pitch`, `roll`, `rel_yaw:<Part>`,
  `world_yaw:`/`world_pitch:`/`world_roll:<Part>`, `components`' `world_yaw` and `world_pitch`, and a `prop:` that holds
  an angle): angles are normalised to
  (-180, 180]. `"to_angle": -90` turns the field into its shortest absolute angular distance to that angle, 0-180 (so
  270 and -90 are the same). `"to_axis": 90` turns it into the distance to that axis, 0-90: a direction and its
  opposite are one axis (a straight road piece turned 90 or -90). One or the other, not both.
- `match` (string values: text, names, an animation's name, a picture's name): a regular expression, searched for
  anywhere in the string (`^...$` to match all of it); the value is 1 when it matches, 0 when not. A string without
  `match` has no value. Two engines read a task's regular expressions: the checker's Python reads `match` and a `log`
  or `log_absent` `pattern`, the probe's (the engine's `RegEx`, PCRE2) a select's `text`; the validator checks each
  as Python reads it. Write what both read alike (literals, character classes, `^` and `$`, `|`, groups,
  quantifiers): a form only one of them knows in a select's `text` passes the validator and matches nothing in the
  play (`query_errors`: "the text regex ... doesn't compile").

Rows with no value are skipped by `of`: `count`, `any`, `sum` and `all` of none are 0, the others have no value.
Samples with no value are skipped by `agg`, and a window where no sample has a value has no value, whatever the `agg`.
A probe whose measure has no value fails, with the reason in its detail (section 3). A query that names something the
probe can't find (a kind, a class in any select, a field), or whose regex doesn't compile, gives empty rows or no
value and one line in the play's `query_errors` (each line once; past 50 lines the list ends with `<n> more in
probe.log`); it never stops the play. A select that matches nothing (no rows), or a `prop:` member an object doesn't
have (no value), writes no line.

### 2.2 `player`: the player

`{"probe": "player", "field": "x|y|z|speed|moved", ...}`, sampled through the play: the player's position (its
node's global position, so its origin). `speed` in m/s between samples; `moved` = distance from the first sample (m).
`"field": "dist", "to": <Point>`: distance to a point (section 2.13).

### 2.3 `camera`: the player's camera

`{"probe": "camera", "field": "distance|height|pitch|yaw|fov|occluded|player_on_screen", ...}`: `distance` (m) from
the camera to the player's position (its origin, as `player` reads it, not its centre); `height` = the camera's y
minus that position's y (m); `pitch`, `yaw` (degrees, of the camera's rotation in the world: a camera looking down
has a negative pitch); `fov` its field of view in degrees (0 for an orthogonal camera); `occluded` = 1 when a ray
from the camera to the player's centre hits a physics body (areas, the player's own bodies and bodies under the
camera itself are ignored); `player_on_screen` = 1 when the player's centre projects inside the frame, in front of
the camera. The player's centre: the centre of the box around what it draws, else its position.

With a `Camera2D`: the camera's place is the centre of what it shows, `pitch`, `yaw` and `fov` read 0, `occluded` 0,
and `player_on_screen` is 1 when the player's centre is inside the rectangle the camera shows.

### 2.4 `objects`: nodes in the scene

```json
{"probe": "objects",
 "select": {"component": "CastlePiece", "tag": "wall", "name": "Tower*", "near": {"point": {"xyz": [0, 0, 0]}, "radius": 50}},
 "field": "y", "at": "end", "of": "first", "agg": "last"}
```

- `select`: every key given must match. By default only shown nodes match.
  - `component`: the node's own class (a class of a node below it is found with `has`, below): an engine class
    (`MeshInstance3D`, `RigidBody3D`, `Area3D`; the classes it inherits match, so `PhysicsBody3D` takes every body),
    a script's `class_name` (`CastlePiece`), or a script's file name without its extension (`castle_piece` for
    `castle_piece.gd`); a script that extends another matches the other's names too. A name no node can have (a typo,
    a script only the fix adds, read on the start) matches nothing, and the play's `query_errors` says
    `objects <id>: no component type <T>` (for a `has` `component` too).
  - `tag`: a group the node is in (`add_to_group`, or the scene file's `groups`); a group nothing is in matches
    nothing, with no `query_errors` line. `name`: a wildcard on the node's whole name (`*` any run of characters,
    `?` one character, any case). Every node whose name fits matches: `Coin*` takes a `CoinSpawner` or a `CoinPool`
    as well as the coins, and a select that picks one match (`teleport_to`, a point, `"of": "first"`) may pick the
    spawner. To pick the things themselves, select them by their own class (`"component": "Coin"`), their group or
    their full name: a node added at run time beside others of its name is named by the engine (`Coin2`,
    `@Node3D@12`), so a name the code doesn't set itself is no name to select by.
  - `near`: its position (its origin) within `radius` m of a point. `{"player": true}`: the player;
    `"player": false`: anything but the player and the nodes below it (the foes among every `CharacterBody3D`).
  - `where`: `[{"prop": "<path>", "op": "==", "value": v}, ...]` (1 to 4): a property of the node, the path a `prop:`
    field reads, compared with a number, a boolean or a string (a string takes `==` and `!=`); every condition must
    hold, and a node whose property doesn't resolve doesn't match. Only foes not dead, a bay's own crates:
    `{"tag": "foe", "where": [{"prop": "dead", "op": "==", "value": false}]}`. Name only members the task doesn't
    ask to change, or another solution fails for its names.
  - `has`: a part the object carries, `{"has": {"component": ..., "visible": true, "near": {"point": <Point>,
    "radius": m}}}`: the object matches when at least one of its parts (the node itself or a node below it; the shown
    ones, all of them when the select says `"inactive": true`) matches every key given. `component` is the part's
    class, as a `components` select names it; `lit: true` keeps a part that gives off light, as the components `lit`
    field reads it (a light that is on, a mesh that gives light by its materials or as drawn alone, a live effect that
    draws light: section 2.5); `visible: true` keeps a node that draws (a 3D visual node, a 2D canvas item) and is
    shown; `near` measures from the part's own place, not the object's; `"simulating": true` keeps a `RigidBody3D` or
    `RigidBody2D` that isn't frozen (or a collision shape of one). At least one key, and only `true` for `lit`,
    `visible` and `simulating`. The way to select by what an object does ("an object that gives light", "an object
    with a drawn mesh near here", "an object a player can shove") rather than by the class or name a build gave it:
    `{"teleport_to": {"has": {"simulating": true, "near": ...}}}` reaches the nearest object a player can shove,
    whichever nodes a build used. It works in every object select: these, other measures' (`owner`), points (section
    2.13) and `teleport_to` (section 1.1). Because a part may be a node below, a node that holds others (the scene's
    root, a spawner that parents what it spawns, a pool) matches whatever one of its children matches: keep it out
    with a `component` the node itself must be (`{"component": "MeshInstance3D", "has": {...}}`), a `name`, a `near`
    or a height band (section 2.13).
  - `inactive: true`: nodes that aren't shown match too (they read `active` 0).
- `field`:
  - `count`: the selection's size (`of` ignored);
  - `x`, `y`, `z` (m), `yaw`, `pitch`, `roll` (degrees), `scale` (the mean of the absolute scale's axes, in the
    world);
  - `extent_x`, `extent_y`, `extent_z`: **the world-aligned half-size of what the object draws** (m): the box around
    the shown nodes in it that draw, each by its own bounds (a mesh, a sprite, a Control's rectangle; lights and
    plain `Node3D`s have none). No value when the object draws nothing. World-aligned, so a rotated object's extent
    mixes its own axes (an object turned 90 degrees reports its width as `extent_z`);
  - `active` (1 when it is shown); `hidden` (1 when it isn't shown, or it has nodes that draw and none of them is
    shown); `collision` (a physics body in it, never an area, has a collision shape or polygon that isn't disabled;
    0 when the object isn't shown); `speed` (m/s): its own velocity when it reports one that isn't zero (a
    `CharacterBody`'s `velocity`, a `RigidBody`'s that isn't frozen), else how far it moved since the previous sample
    over the time of the frames since (1/30 s each, a wait's among them: the play's clock holds then, the game runs
    on). One with such a velocity at rest reads 0 on its first sample; one without has no value the first time it is
    seen;
  - `spin` (deg/s): how fast the object turns, the fastest of itself and the nodes it draws with (64 of them at
    most), each read as a part's `spin` (section 2.5). **Its threshold is calibrated or relative to the start, never
    a literal value**;
  - `simulating`: 1 when the object is, or holds, a `RigidBody3D` or `RigidBody2D` that isn't frozen (pieces that
    broke loose, a ragdoll);
  - `prop:<Class>.<member>[.<sub>]` or `prop:<member>`: a property of a node or a variable of its script, whether or
    not it is exported. With a class first (as `component` names one), the node itself when it is of that class, else
    the first node below it that is (`prop:Health.current`, `prop:RigidBody3D.mass`, `prop:Light3D.light_energy`);
    without one, the node itself (`prop:visible`, `prop:position.y`, `prop:hp`); `prop:<Class>` alone is 1 when the
    object is or holds a node of that class and has no value when not (`prop:CollisionShape3D`). Numbers and
    booleans as numbers, an enum as its number, an object (a node, a resource) as 1 when set and 0 when not,
    strings through `match`; an array or a dictionary without an index gives its size, `[i]` an array's element
    (`prop:Inventory.items[0]`); a dictionary's entry by its key (`prop:Inventory.counts.coins`); a vector's `.x`,
    `.y`, `.z`, a colour's `.r`, `.g`, `.b`, `.a`, a transform's `.origin`: a vector or a colour read without its
    part has no value (`prop:velocity` none, `prop:velocity.y` a number). A property with a getter runs it at each
    read: name a variable, or a getter without side effects. A path of more than 16 steps reads nothing;
  - `rel_yaw:<Part>`: the part's yaw in the world minus the object's (turning the whole object doesn't change it);
  - `world_yaw:<Part>`, `world_pitch:<Part>`, `world_roll:<Part>`: the part's own rotation in the world (degrees),
    whether its object or the part itself turned; `forward:<Part>.x|y|z`: its forward unit vector in the world (its
    -Z axis). For a light this is the way its light travels: a directional light pointing down has a negative
    `world_pitch` and a negative `forward:<Part>.y`. A **Part** is the object itself or a node below it, by its
    node name, else the first of them of that class (`world_pitch:DirectionalLight3D`, `forward:Sun.y`);
  - `facing_vs_velocity`: degrees between the object's forward and its velocity (0 when it moves forward; no value
    under 0.1 m/s);
  - `anim:<Parameter>`: a parameter of the first `AnimationTree` in the object, `parameters/<Parameter>` (a blend
    amount, a condition: `anim:conditions/jump`, `anim:Blend2/blend_amount`): numbers as numbers, booleans as 1/0;
    `clip`: the name of the animation that plays, through `match`: the current animation of the first
    `AnimationPlayer` in the object that is playing, else of a playing `AnimatedSprite2D` or `AnimatedSprite3D`, else
    the current state of an `AnimationTree` whose root is a state machine. Read an AI's state with `anim:`, `clip`
    or a `prop:` of the node that holds it;
  - `lit`: 1 when the object gives off light, whatever made it: a light in it is on, a mesh in it is drawn with a
    material that gives light, or an effect in it is live and draws light (each as the components `lit` field reads
    one source, section 2.5; the object's sources are itself and the nodes below it). **This is the way to check
    for light**: a lamp lit by a `Light3D`, one drawn with an emissive or an unshaded material and one a particle
    effect lights read the same. Takes a literal;
  - `glow`: how much light, one amount summed over its lit sources so either kind compares: a light's energy times
    its colour's luminance, a mesh's brightest material's light times a quarter of the surface of its box (section
    2.5). **Its threshold is calibrated or relative to the start, never a literal value.** An object lit by an
    effect, or by a part that had to be drawn alone to be read (a shader of its own, a texture on its light), has
    no `glow`: gate on `lit`. Neither `lit` nor `glow` has a value while a part of it can't be read and no other
    source is lit. A row with `lit` or `glow` also carries
    `glow_sources`, the kinds lit (`light`, `emissive`, `unlit`, `effect`), and `glow_read`, how its parts were
    read (`props`: from their materials' properties; `drawn`: drawn alone in a room without light; `bound`: with a
    texture taken as white; `unread`: a part couldn't be read), for the logs; neither is a field to measure;
  - `frozen` (seconds): the object's own short stop, a hit stop too short for a screenshot: the longest stop that
    ended since the previous sample, 0 when none did. The probe follows the object frame by frame from the first
    sample that reads it (which has no value): the node itself, the nodes below it at that moment (64 at most)
    and the bones of the `Skeleton3D`s among them. A frame is one of motion when one of those moved 1 mm (a 2D
    node 0.01 units) or turned 0.1 degrees; a stop is a run of frames without motion between two frames of motion,
    0.5 s at most (longer is standing still). So it reads an object that moves or animates before and after the
    stop; an `AnimatedSprite`'s frames are no motion. What comes to be below the object afterwards (a hit spark, a
    damage number parented to it) is not followed, and a node below it that is freed is left out from then on:
    neither breaks a stop. A node that was below it from the start and moves during the stop does (a mesh that
    shakes while its body holds): the stop then reads shorter, or 0. A game whose time is stopped or whose tree is
    paused stops the object too, and reads here. Read it with `"agg": "max"` over a tight window after the contact,
    in a play sampled every 0.1 s; never on an object a pin or a teleport holds (it is put back every frame). An
    object that blinks by hiding itself when hit drops out of a select while hidden, and is followed anew when it
    shows again: select it with `"inactive": true`;
  - `damage_taken`: what the object's `take_damage`, or that of a node below it, returned for the play's `damage`
    stages so far (section 1.4), summed: no value before any struck it, or when a call returned no number. In a
    game under the combat rule `take_damage` returns the damage actually applied, so this is what a staged hit
    did. A hit the game itself deals (the player's own blow) is not counted: read the state it changes.

A row (in `probe.json`, for the logs) holds the node's `name` and a `class`: its script's `class_name`, else its
script's file name, else its engine class.

### 2.5 `components`: the parts of the scene

`{"probe": "components", "select": {"component": "GPUParticles3D", "owner": <object select>, "near": ...}, "field":
"count|active|visible|...", ...}`: nodes of a class (particle effects, sound players, lights, meshes, the moving
parts of an object), wherever they are in the tree, optionally under an owner (the node the `owner` select matches,
or one below it) and near a point, so a part that is no object of its own is read by what it is. `component` names
a class as an object select's does (section 2.4): `Light3D` takes every light, `VisualInstance3D` everything drawn
in 3D; a name no node can have matches nothing, and the play's `query_errors` says
`components <id>: no component type <T>` (for an `owner` select's `component` too).
`"name": "<wildcard>"` keeps the nodes whose name matches (as an object select's `name`),
`"mesh": "<wildcard>"` those whose mesh's name matches (a `MeshInstance3D`'s, a `MeshInstance2D`'s or a
`MultiMeshInstance3D`'s mesh: the resource's own name, else its file's name without the extension; a mesh saved
inside a scene has neither), and `"visible": true` only those shown, so one part, a lamp's bulb, can be picked out.
Nodes that aren't shown are left out unless the select says `"inactive": true`. `"effect": true` keeps only live
particle effects, with or without `component`: a `GPUParticles3D`, `CPUParticles3D`, `GPUParticles2D` or
`CPUParticles2D` that is emitting and shown; a one-shot effect that has finished not at all. With `near` and `count`,
how many effects play at a spot: read before and after a restart (an input of a task play), it catches effects that
pile up. A select names its `component`, or `effect`, or both.
A row (in `probe.json`, for the logs) holds the node's `name`, its `class` and `owner`, its parent's name (`owner` is
not the node the `owner` select matched).

- `field`: `count`; `active` (shown and doing what it does: particles emitting, a sound player or an
  `AnimationPlayer` playing, a collision shape not disabled, a light on; any other node: shown); `visible` (1 when
  it is shown);
- `x`, `y`, `z` (m) and `speed` (m/s) of the node, as objects have them (section 2.4). Cars that are parts of one
  road object read here;
- `spin` (deg/s): how fast the node turns in the world, from its rotation read every frame and summed since the
  previous sample (so a part turning many times a second still reads); the first time it is seen, a rigid body's own
  angular speed, else no value then. Any part near a point: select `MeshInstance3D` with `near`; each part of one
  object: select by `owner`. No name is needed. A turn drawn by a skeleton's bones or by a shader reads 0 here;
- `world_yaw`, `world_pitch` (degrees, normalised to (-180, 180]): the node's own rotation in the world (as an
  object's `world_yaw:<Part>` reads a part), whether it or a parent turned, for a part picked by where or what it is
  rather than by a name. Angles: `to_angle` / `to_axis` turn each node's value into its distance to a bearing before
  `of` combines them, so `"of": "max"` is the one furthest off. A part near a point turned to face -90:
  `{"probe": "components", "select": {"component": "MeshInstance3D", "near": {"point": {"xyz": [x, y, z]},
  "radius": r}}, "field": "world_yaw", "to_angle": -90, "of": "max"}` with `<=` a tolerance;
- `extent_x`, `extent_y`, `extent_z` (the world-aligned half-size of what the node itself draws or, for a collision
  shape, of its shape, m) and `simulating` (a rigid body that isn't frozen, or a collision shape of one);
- `intensity` (a `Light3D`'s `light_energy`, a `Light2D`'s `energy`) and `on` (1 when the light lights the scene:
  shown, of an energy above 0; a `Light2D` also enabled). A lamp switched off by energy 0 or by hiding the light
  reads 0 when the select says `"inactive": true`; without it, a hidden light is no longer selected (no row: `count`
  drops, `"of": "max"` has no value). No value for a node that is no light. They see lights only: use them when a
  task really needs a light node, else `lit` and `glow`;
- `lit` and `glow`: whether one source gives off light and how much, read from what the engine holds of it, and
  for a part whose light its properties don't tell, by drawing it alone (below). No value for a node that is no
  source.
  - One floor holds for every source: a luminance of 0.01 (linear), for a light's amount, a material's light and a
    drawn pixel alike.
  - **A light** (`Light3D`, `Light2D`): `lit` when it lights the game (shown, not an editor's own light, not one that
    takes light away: `light_negative` or a subtracting 2D light; a `Light2D` also enabled, a `PointLight2D` with a
    texture) and its energy times its colour's linear luminance (a `Light2D`'s also times its colour's alpha) is
    above the floor; `glow` is that amount.
  - **A 3D part** (a `MeshInstance3D`, a `MultiMeshInstance3D`, a CSG shape): dark when it isn't drawn: hidden (it
    or a node above it), on no render layer, faded out by its `transparency`, casting only a shadow, outside its
    visibility range from the camera, a multimesh with no instance to draw. Else it is read **from its materials'
    properties** where they tell, each material with the passes drawn over it (`next_pass`): a standard material
    with emission on gives its emission colour times its emission energy, an unshaded one its albedo colour, each
    times its albedo's alpha when it is drawn transparent (a lamp switched off by fading reads dark), any other
    standard material nothing; `lit` when the brightest gives more than the floor, and `glow` is that light times a
    quarter of the surface of the part's box in m2, scaled (what a glowing surface that size gives every way).
    `glow_read` is `props`. A CSG mesh without a material of its own is read by its mesh's materials.
  - **Where the properties don't tell**, the part is **drawn alone**: a material that isn't a standard one (a
    `ShaderMaterial`, a next pass among them: its light is its shader's own code), or a standard material with a
    texture on what is read (an emission texture may be black where the mesh shows, or bright where the colour is
    black), and no other material of the part that surely gives light. The probe draws the part's mesh with its own
    materials in a room of its own with no light at all (black background, no ambient or reflected light), from
    three sides, 128 x 128 pixels each: whatever shows there is the part's own light. `lit` when one pixel is
    brighter than the floor, so a small glowing patch on a large mesh counts (a shaded material that gives no light
    draws no pixel above black there); `glow_read` is `drawn`, and the part has **no `glow`** (a yes or a no is
    what such a drawing gives on every renderer; an amount is not). The mesh is drawn as it rests: a skinned mesh
    without its pose, a shader that reads the world around it or the time without them. A part is drawn again only
    when a reading asks for it and what its light depends on (its mesh, a material, a shader parameter) changed
    since its last drawing; until the new drawing is read, the part keeps its last answer, so a lamp whose light
    changes every frame reads as it was a frame before, and a shader that changes its light by time alone reads as
    it was when last drawn. The first drawing of a part is read when its frame is drawn: a sample's `lit` or `glow`
    of it is completed then, but a select's `has.lit` can't wait, so **a sample whose select waits for a first
    drawing has no value** (no rows, `"pending": true` in it: not a count of 0). An input whose select has
    `has.lit` has the parts drawn in the frames just before it, and waits for a first drawing up to 1 s. The play's
    `probe.log` says what a drawing found when its answer changes (`lit: Lamp/Shade drawn alone in a room without
    light: 21548 bright pixel(s), the brightest 255 of 255, lit`).
  - **A 3D effect** (`GPUParticles3D`, `CPUParticles3D`): `lit` when it is emitting, shown and what it draws (its
    draw passes' or its mesh's materials) gives light by its materials' properties, a texture taken as white
    (`glow_read` `bound`), so a spark effect reads lit and smoke drawn with a shaded material doesn't. It has no
    `glow`, and one drawn with a shader of its own can't be read (`glow_read` `unread`, no value): an effect isn't
    drawn alone, since its particles are its state of the moment. A CSG shape isn't either: a texture on its light
    is taken as white, a shader of its own is unread.
  - Not read as sources: a sprite, a label or a decal in 3D, and everything a 2D game draws but its `Light2D`s
    (in 2D every picture is drawn at its own brightness, so none says "lit"): read a lamp drawn that way by a
    property the start names, or by the frame's brightness (`screen`, section 2.15).
  - **Gate "the lamp is on" with `lit`; read `glow` only where the ask is about how bright.** A part read from
    its properties counts its brightest material over its whole box, so a lamp post with a small glowing bulb reads
    the post's size: compare a `glow` with itself, calibrated or relative to the start, or select the bulb by
    `mesh` or by its name. `glow` has no value for a lamp an effect, a texture or a shader of its own lights.
  - **In a game drawn unshaded, every mesh reads lit**, on or off (an unshaded material shows its colour whatever
    lights it), and so does unshaded smoke: don't gate on `lit` there; read the property that switches the lamp.
  - **A count or `"of": "all"` over a `has.lit` select is read at the end or after a settle window**, never at the
    first sample or the sample right after a switch: a part drawn for the first time gives that sample no value,
    and a part whose light just changed reads its last drawing until the new one is read.
  - These readings can make the probe draw, and what it draws is in the frame's `render` counts (3 draw calls a
    part drawn, in the frame it is drawn): a play that takes a `render` measure takes none of them (section 2.20).
- `prop:<path>`: a property of the node itself or a variable of its script, as an object's `prop:` reads it
  (`{"component": "AudioStreamPlayer3D"}` with `prop:pitch_scale`);
- **`intensity`, `extent_*`, `glow` and `spin` thresholds are calibrated or relative to the start, never a literal
  value**; `on`, `lit`, `simulating`, positions and speeds take a literal.

### 2.6 `widgets`: the UI's own nodes

`{"probe": "widgets", "select": {"component": "Label", "name": "AmmoText"}, "field": "text", "match":
"AMMO\\s*\\d+", "of": "any"}`.

- What is searched: the `Control` nodes of the game's window that are on screen (below; a Control drawn into a
  `SubViewport` is not the window's), every one with `"visible": false` in the select. A row's `class` is the
  node's, as an object's.
- `select`: `component` (the Control's class: `Button`, `Label`, `ProgressBar`, `TextureRect`, a game's own script;
  the classes it inherits match, so `BaseButton` takes every kind of button and `Range` every bar and slider; with a
  `name`, the class of a Control above it matches too: `{"component": "PauseMenu", "name": "Resume*"}` finds the
  Resume button inside the node whose script is `PauseMenu`, and the row keeps its own class), `name` (a wildcard on
  the node's name), `text` (a regular expression its text must match), `visible` (below). A `component` no node can have
  matches nothing, and the play's `query_errors` says `widgets <id>: no component type <T>`.
- **To check what a HUD shows, use `ui` (section 2.18).** `widgets` reads a named widget's own state, so it sees a
  HUD only when a build made it with that node; a HUD another build made of other nodes, or drew itself, reads as
  absent.
- **A select reads the widgets on screen**: those the `visible` field reads 1 for. On screen is shown (itself and
  everything above it, its canvas layer too), not transparent (its own `self_modulate` and the `modulate` of it and
  of the nodes above it, an alpha above 0.004), inside the frame, and not wholly outside a Control above it that
  clips what it holds (an item scrolled out of a scroll container's view). A Control of no size counts as on screen
  (a container that only holds others), and so does one another Control covers. So `count` counts what the game
  shows (a warning bar's shown messages, not the ones it keeps hidden), and a "no longer shown" check passes on a
  widget a build hides as on one it removes. A fully transparent Control (an invisible hit area over art, its
  `self_modulate` alpha 0) reads as not shown here, while a click or a touch still reaches it (section 1.1): inputs
  land on what a player can press.
- `"visible": false` in the select keeps the hidden widgets too: the widget exists, shown or not. Write it only when
  the check means that. `"visible": true` is the default. A measure of the `visible` field whose select says neither
  takes hidden widgets too, so `visible` can read 0 (`"of": "first"`, `== 0`: the widget is there and hidden).
  A disabled button is visible: whether it can be pressed is `interactable`.
- `field`: `count`; `visible`; `text` (a `Label`'s, a `Button`'s or a `LinkButton`'s text, a `RichTextLabel`'s with
  its tags stripped, a `LineEdit`'s or `TextEdit`'s what was typed, not its placeholder; a typewriter reveal
  (`visible_characters`) honoured; a button with no text of its own reads the first label below it; with `match`);
  `percent` (0-1: a `Range`'s share, so a `ProgressBar`'s, a `Slider`'s, a `TextureProgressBar`'s, a `ScrollBar`'s);
  `value` (a `Range`'s value, a toggle button's or a `CheckBox`'s 1/0, an `OptionButton`'s selected index, a
  `TabContainer`'s current tab); `interactable` (1 when a button isn't disabled, a text field or a slider is
  editable; no value for another widget); `has_brush` (1 when a `TextureRect`'s, a `NinePatchRect`'s, a
  `TextureButton`'s or a `TextureProgressBar`'s texture, or a `Button`'s icon, is set; no value for another widget);
  `brush` (that texture's name, its file's without the extension, with `match`); `x`, `y`, `w`, `h` (the widget's
  rectangle in fractions of the frame 0-1, **y down from the top**, whatever anchor, container or canvas layer
  placed it, as laid out at the sample: a change of layout a container makes in that frame shows from the next
  sample; no value for a widget of no size).

### 2.9 `spawns`: objects appearing and disappearing

`{"probe": "spawns", "component": "Projectile", "field": "spawned|destroyed", "window": [0, 22]}`: how many nodes
of that class appeared or disappeared in each sample's interval; the default `agg` is `sum` (the count in the
window).

- `spawned`: a node of the class came to be shown (added to the tree, shown again, or in a scene changed to during
  the play); `destroyed`: one was freed, taken out of the tree or hidden. The probe compares every frame with the one
  before.
- Where the task itself adds the things, no class is sure to sit once per thing in every solution: count instead
  how often the number of objects that carry what the brief asks for rises, an `objects` `count` over a `has` select
  with `"agg": "rises"` (section 2.1).
- Nodes already there when the play's clock starts are not counted as spawned.
- Pooled nodes reused by hiding and showing count as new ones do: a pooled projectile that is hidden and reused
  counts each time it comes and goes.
- What counts is each node of the class, named as an object select's `component` (section 2.4: a class that
  inherits it counts). Name a class that sits once per thing (the coin's own script), not one its children also are
  (`MeshInstance3D`), or each child counts too.
- A node that appears and goes within one frame is not seen.
- A class the build doesn't have (one a feature adds, at the start) gives no value, not 0, and the play's
  `query_errors` says `spawns <id>: no component type <T>`.
- In a play's `probe.json` a sample holds the running totals since the play started (`spawned` 1, 1, 2, ...); the
  checker reads each sample's rise over the one before, so don't add the samples up yourself.

### 2.10 `log`: the play's log

`{"probe": "log", "pattern": "Scenario \\d+ started", "field": "count"}`: lines of the play's log (`print` output,
warnings, script errors and the engine's own lines) that match, during the play: the log of the game's run from
its start-up to the end of the play's time (a `log` measure takes no `window`, `at` or `agg`). What the game
prints after that, while it is told it is closing and while it exits, is read by no `log` measure and no
`log_absent` check: the probe marks the play's end in the log first. A game that quits by itself has no such mark,
and its whole log is read.

### 2.13 Points

`{"xyz": [12.0, 1.5, -3.0]}`, `{"player": true, "offset": [0, 1.6, 0]}` (the player's position plus `offset`),
`{"camera": true, "forward": 30}` (`forward` m ahead of the camera along its view; a 2D camera: the centre of what
it shows), or `{"object": {"name": "Lamp_1"}, "offset": [0, 4.5, 0]}` (the first match's position plus `offset`;
section 2.1 says which is first). `offset` defaults to `[0, 0, 0]` and `forward` to 0. A point is found again at every
sample; one that doesn't resolve then (no player or camera yet, nothing matched) makes what uses it read nothing: a
`near` around it matches nothing.

A `near` is `{"point": <Point>, "radius": m}`, and may also hold a height band: `"y_min"` and/or `"y_max"` (m, world
y; with `"y_relative": true`, offsets from the point's y). Wherever `near` works (object selects, `has`,
`components`), a thing then matches only when its place's y is within the band too: the lamp on the ceiling, not
the one on the floor below it. `y_min < y_max`; `y_relative` goes with one of them.

### 2.15 `screen`: what the player sees, after post-processing

```json
{"probe": "screen", "rect": [0.25, 0.25, 0.75, 0.75], "field": "luminance", "window": [10, 20], "agg": "mean"}
```

The mean brightness of the frame the game's window displays, sampled with the play like every other probe: after
the environment's effects and tonemapping (exposure, adjustments, glow, fog, ambient occlusion), so "the cave is too
dark to see" or "the night is too bright" is measured on what reaches the screen.

- `rect`: `[x0, y0, x1, y1]` in fractions of the frame 0-1, y down from the top, x0 < x1 and y0 < y1 (default
  `[0, 0, 1, 1]`, the whole frame), read as whole pixels, rounded out (at least one pixel each way); a rect of more
  than 65,536 pixels is read on an even lattice of its pixels, the same ones in every play. The frame is read **as
  displayed, UI included**: keep the rect on the scene the task is about and off the HUD. What the HUD shows is
  `ui` (section 2.18), not luminance.
- `field`: `luminance`, the mean linear Rec. 709 luminance of the displayed pixels (sRGB decoded, 0-1); `luma`, the
  mean Rec. 709 luma of the encoded values (0-1, closer to perceived brightness).
- What is read: the frame drawn right after each sample (the sample's own frame, read once it is drawn: no play time
  passes in between). No value when no frame is drawn. The value also holds `pixels` (how many were read) and
  `size` (the frame's width and height), for the logs.
- **The threshold is calibrated or relative to the start, never a literal value** (`tools/validate-game.py` refuses
  one): the numbers depend on the GPU, the driver, the renderer and the frame's size, so they compare only within
  one machine's plays. A fade-in, a teleport or a scene's own exposure animation takes time to settle: put the
  window after it.

### 2.16 `audio`: what the player hears

```json
{"probe": "audio", "select": {"sound": "amb_jungle*", "sound_class": "Ambience", "owner": {"tag": "zone2"}},
 "field": "volume", "window": [4, 8], "agg": "mean"}
```

The sound players playing: every `AudioStreamPlayer`, `AudioStreamPlayer2D` and `AudioStreamPlayer3D` node whose
sound is playing, wherever it is in the tree, so a player a script makes for one sound reads as well as one placed
in the scene.

- `select` (optional; none: every player playing): `sound` a wildcard on the stream's name (the stream resource's
  own name, else its file's name without the extension: `amb_jungle_01` for `amb_jungle_01.ogg`; a stream made in
  code, or a copy of one, has no name unless the code gives it one), `sound_class` a wildcard on the name of the bus
  the player plays on (`Master`, `Music`, `SFX`: that bus's own name), `owner` an object select: the player is a
  matching node or under one (as a components `owner`, section 2.5), `near` a point and radius (section 2.13): a
  placed player (`AudioStreamPlayer2D`, `AudioStreamPlayer3D`) within it, where it plays, or for the fields of the
  sounds that start where it started; a plain `AudioStreamPlayer` has no place and is near nothing.
- Each player reads its **volume at the listener**: its own volume (`volume_db`, as a linear gain), times for a
  placed one its fall-off with distance. An `AudioStreamPlayer3D`: by its attenuation model over its unit size at
  its distance from the listener (the current `AudioListener3D`, else the current `Camera3D`), never louder than
  its `max_db`, fading to 0 at its max distance when it has one. An `AudioStreamPlayer2D`: by its distance from the
  middle of the screen up to its max distance, with its attenuation exponent. Bus volumes are left out (a bus's
  volume changes `level`, never `volume`).
- `field`: `count` (how many players), `audible` (how many at 0.001, -60 dB, or louder), `volume` (their volumes'
  sum), `max_volume` (the loudest), `level` (the RMS of the Master bus's mixed output since the previous sample,
  buses and effects included: everything the player would hear, whatever plays it). `count`, `audible`, `volume`
  and `max_volume` are of the players playing at the sample itself, so a sound shorter than the time between two
  samples can fall between them: read `level`, or the sounds that start (next item), which cover the whole time
  since the previous sample. A sample before which nothing was mixed (a play's first sample can be one) has no
  `level`, while silence reads 0.
- `started`: how many matching players were found playing that weren't the frame before, in each sample's interval
  (summed over the window by default). A player played again while it still plays isn't counted, one that plays
  for less than a frame can be missed, and a player the game's pause held counts again when the pause ends: for "a
  sound starts when the event happens", read `started_audible`.
- The sounds that **start**, every one however short, watched every frame whatever the samples. Every `play()` of a
  player is one start: a player that begins to play (one a script makes for a single shot and frees when it ends
  too), one played again while it still plays (a pooled player retriggered, a looping stream, a `play()` from
  another position), and one that began and ended between two frames. A pause and its end start nothing, nor does a
  seek.
  - `started_audible`: how many sounds started audible at the listener in each sample's interval: its volume at the
    listener times the gain of its bus and of the buses that one sends to, at 0.001 or louder; none of those buses
    muted; a placed one within its max distance. Summed over the window by default (`"agg": "sum"`). It is judged
    as the sound starts: a sound that starts silent and fades in, and music that changes its volume, are read by
    `audible`, `volume` or `level`.
  - `sounds`: how many differently named streams started in the window; `repeats`: how often a sound started right
    after a start of the same stream. They read the names of the streams that started, in the order they started,
    over the samples the `window` or `at` picks, and take no `agg` (the validator refuses one). A stream's name is
    its file's (`sound`, above): a game's sounds are imported files, so each has one. There is no value, never a
    wrong count, when a stream that started has no name of its own sound: one made in code, or one that picks or
    mixes other streams (an `AudioStreamRandomizer`, an `AudioStreamPolyphonic`, a playlist, an interactive or a
    synchronized stream), whose take the engine doesn't tell; or when more than 64 started in one sample's
    interval. So `repeats` grades "never the same take twice" only in a build that plays its takes as streams of
    their own; it cannot grade one that uses a randomizer.
  - A sound ask reads "a sound starts when the event happens": `started_audible` in a window right after the
    event, picked by `owner` or `sound_class` where the start has them. A start falls in the sample after it:
    leave a margin of one `every` at each end of the window. Use `near` only when the ticket itself asks for a
    sound placed in the world: most sounds play on a plain `AudioStreamPlayer`, in 3D games too, and that is near
    nothing. What the sound is, how it sounds, is never checked.
  - Not seen: what starts inside a player that already plays, a voice of an `AudioStreamPolyphonic` started through
    its playback's `play_stream` or frames pushed into an `AudioStreamGenerator`. The engine tells of neither. A
    sample says when a matching player plays such a stream, and a check that reads the sounds that start then says
    "... those starts are not seen, read `level`": a game with a polyphonic sound manager is graded by `level`.
    Two `play()` calls of one player within one frame are one start, and a player started and stopped again within
    one frame is none.
  - A sound already playing when the play's clock starts is not a start.
- A `near` whose point doesn't resolve (the object it names isn't there) gives no value, never 0.
- The sample's value also holds `loudest` (the loudest player's stream name), `peak` and `listener` (its node's
  name), for the logs.
- **A `volume`, `max_volume` or `level` threshold is calibrated or relative to the start, never a literal value**: how
  loud depends on the sounds a build chose. `count`, `audible`, `started`, `started_audible`, `sounds` and `repeats`
  take a literal. Compare places by their own plays or windows: teleport into each zone (section 1.1) and read the
  zone's sound there.
- No play is heard on the machine: the checker starts every play with the engine's dummy audio driver, which mixes
  the sound as always and plays it nowhere. A play with an `audio` measure is paced to real time (still 30 fps), so
  a sound lasts as long in play time as on a clock. Every other play runs as fast as the machine renders, often many
  times faster than real time, and a sound, which plays in real time, then lasts many times longer in play time:
  read sound only in a play with an `audio` measure.

### 2.18 `ui`: what the UI shows on screen

```json
{"probe": "ui", "select": {"kind": "text"}, "field": "text", "match": "AMMO\\s*\\d+", "of": "any", "at": "end"}
{"probe": "ui", "select": {"kind": "box", "rect": [0, 0.8, 1, 1]}, "field": "count", "window": [5, 10], "agg": "min"}
{"probe": "ui", "select": {"rect": [0.02, 0.02, 0.3, 0.12]}, "field": "signature", "window": [5, 15], "agg": "changes"}
```

One reading for the UI on screen, whichever nodes a build made it of: a score in a `Label`, in a `RichTextLabel` or
on a `Button` reads the same text. **This is the way to check what a HUD or menu shows**; `widgets` (section 2.6)
stays for a widget's own state (a bar's percent, a picture).

- What is read: the elements on screen at each sample, from the Controls of the game's window. Only what is drawn:
  a hidden Control, one under a hidden node or canvas layer, one faded out (its `modulate`, that of a node above
  it, or its own `self_modulate`, at an alpha of 0.004 or less), one of no size or entirely off the frame, one
  wholly outside a Control above it that clips its contents (an item scrolled out of a scroll container), and a
  blank text, are not read.
- Each thing a drawn Control draws is one row: its text (a `Label`'s, a `RichTextLabel`'s, a `Button`'s, a
  `LinkButton`'s, a `LineEdit`'s, a `TextEdit`'s) is `text`; its picture (a `TextureRect`'s, a `NinePatchRect`'s, a
  `TextureButton`'s or a `TextureProgressBar`'s texture, a `Button`'s icon) is `image`; a `ColorRect`, a `Panel`, a
  `PanelContainer`, a button that isn't flat, a bar, a slider, a text field, a list, a tree or a tab bar is `box`. A
  Control can be two rows: a `Button` gives a `box` row and a `text` row. A container that only lays out its
  children and a bare `Control` draw nothing and are no row. Text is read as shown: a `RichTextLabel`'s tags
  stripped, a typewriter reveal (`visible_characters`) honoured. Rows come in tree order.
- `select` (optional; default every element): `kind` (`text`, `box`, `image`); `text` (a regular expression the
  element's text must match; text elements only, so with `kind` `text` or none); `rect` `[x0, y0, x1, y1]` in
  fractions of the frame, y down from the top, x0 < x1 and y0 < y1 (the element's centre inside).
- `field`: `count` (one per element); `text` (the string shown, with `match`: a `ui` measure takes `match` when its
  field is `text`, and only then); `x`, `y`, `w`, `h` (the element's rectangle in fractions of the frame 0-1, y
  down); `signature` (whether what the select shows updates, below); `number` and `clock` (the number or time it
  shows, below). `of` combines the elements, as for widgets: `"field": "text", "match": ..., "of": "any"` is 1 when
  some element shows matching text, `"of": "count"` how many do.
- Whether a readout updates: `"field": "signature"` is one value a sample for everything the `select` picks: each
  element's `kind`, `text` and rectangle (`x`, `y`, `w`, `h` rounded to 0.002 of the frame), taken as a set, and how
  many matched. It is 0 when the select picks nothing, otherwise a number that means nothing but itself; names and
  the order of the rows are left out. Read it with `"agg": "changes"`: how many samples (every 0.5 s) show something
  other than the sample before. A text readout whose string changes counts; a readout that stays the same reads 0.
  Appearing or going (to or from 0) is a change.
  - A signature takes `agg` `changes`, `any`, `all` or `count` (`all`: something shown in every sample; `count`:
    samples showing something), nothing else, so it always names one (the default `last` is refused). `of` is ignored.
  - A literal threshold on a count of changes is valid, but a calibrated or start-relative threshold is the safer
    choice: a readout that also moves, blinks or animates changes for reasons of its own, and one that updates more
    slowly than the samples changes less often. Keep the `rect` on the readout alone, with a margin, and the
    `window` where its value is known to change.
  - Limits: geometry right at a 0.002 step can flip between samples on sub-pixel motion; a change that changes back
    before the next sample is not seen.
- Which way a number on screen moved: `"field": "number"` is the first number the select's text elements show in
  one sample, in reading order (top to bottom, a line within 0.01 of the frame's height; left to right): digits with
  a decimal point and comma thousands (`3,450` is 3450), negative when a minus stands before it after no letter or
  digit (`LAP 2-3` reads 2). Its text comes from every text element the select picks, so the select is best
  `{"kind": "text", "rect": [0.01, 0.01, 0.4, 0.09]}` around the readout alone. No number shown: no value. Read it
  with `rises`, `falls` (section 2.1), `changes`, `range` or `max`: a score that only rises reads `falls` 0 over its
  window; a reset reads as a fall.
- A clock on screen as a clock: `"field": "clock"` is the first time shown, in seconds: `h:mm:ss` or `m:ss` (a
  fraction after `.` or `,` added), else the first number, as seconds. A timer that holds through a pause reads
  `range` 0 over the pause's window; one that resets on a retry reads a fall there (a count-down: a rise).
- `number` and `clock` share the signature's query (one select, one reading), take any `agg` and a literal (what is
  shown is a fact), ignore `of` and take no `match`.
- Each row also carries `source` (`control`) and `kind`, for the logs; they are not fields a check reads.
- Limits: what a script draws itself (a `_draw` with `draw_string` or `draw_rect`, a shader) is no element, since
  the engine keeps no list of it, and neither is text in the 3D scene (a `Label3D`, a `TextMesh`). Where a readout
  is drawn that way, read the value behind it with a `prop:` (section 2.4), or grade another outcome of the same
  issue.

### 2.20 `render`: what the renderer drew

`{"probe": "render", "field": "draw_calls" | "triangles" | "texture_mb"}`: the readings a budget is checked by.
`draw_calls` and `triangles` are the engine's counts of a frame (the totals its own monitors show: the 3D scene, its
shadow passes and the 2D canvas, so the UI's draws are among them), the highest over the frames since the previous
sample; `texture_mb` is the texture memory in use at the sample, in MiB. A literal threshold is allowed, since a
budget is a number of its own: `{"op": "<=", "value": 700}`.

- `triangles` counts the primitives drawn: a mesh's triangles once for each pass that draws them (a mesh that casts a
  shadow counts again in the shadow pass), two for each glyph and each rectangle of the UI.
- `texture_mb` holds the engine's own render targets and default textures too: some 10 to 20 MiB before a game adds
  anything, more at a larger frame. A play draws the game at its project's own size, so a mobile game's budget is
  read at its phone's size.
- The counts are of everything the renderer drew in the frame, the probe's own drawings among them: a `lit` or
  `glow` reading, or a select with `has.lit`, may draw a part alone (section 2.5), 3 draw calls each. So **a play
  that takes a `render` measure takes none of those**, in its measures or its inputs, and the task's `player`
  select has no `has.lit` (it is looked at in every play); `tools/validate-game.py` refuses a task where one does.
  Give the budget check a play of its own.
- The first sample of a play, before any frame was drawn, has no counts. A reachable view is reached with the
  play's inputs (teleports, a scenario's `args`): give a budget check a play that goes where the game is heaviest,
  and read `"agg": "max"`.

### 2.21 `world`: the game as a whole

`{"probe": "world", "field": "time_scale" | "flow" | "paused"}`, each read over the frames since the previous
sample, so a stop of a few frames shows even between samples:

- `time_scale`: the lowest `Engine.time_scale`, the engine's own value ("time slows"; 1 when it ran at its pace). A
  paused tree doesn't change it;
- `flow`: how the game went on, the lowest of 0 in a frame the tree was paused and `Engine.time_scale` otherwise. A
  hit stop reads below 1 here whether a build slows the game, stops its time or pauses the tree ("the game holds");
- `paused`: 1 when the game was paused (`get_tree().paused`) in any of them ("Escape pauses the game"; `== 0` for
  "without pausing").

All take a literal. The play's clock counts on through either (section 1.1), so a window right after the contact holds
the stop.

## 3. What gates, and how a probe fails

- **At least one required probe.** Every task has at least one `probe` check with `"required": true` (the default);
  the validator refuses a task without one. Every bug fix and correction has at least one required probe that the start
  fails for the reported reason and the fix passes.
- **`still_works` probes already pass at the start.** A required probe in the `still_works` milestone (the player
  still moves, the HUD still shows, the scene still loads its scenario) must pass on the start: what still works must
  already work there, or the probe itself is broken and would fail every correct solution. (A still-works probe the
  start has no samples for, because its play crashed or ended early on the very bug the task fixes, doesn't count
  against it; one that finds nothing to measure in a start that ran does.)
- **No samples, no pass.** When a play ends early or a measure has no samples in its window (the game quit, crashed or
  never reached that time), the probe fails with
  "no samples in the window (the play ended at X s)" or "no samples in the window (the play wrote no probe file)";
  when samples exist but nothing selected has a value (nothing matched, the play found no player or no camera, the
  field had nothing to read), it fails with
  "no value in the window (nothing it selects was measured)", followed by "; the probe said: " and the probe's first
  error about that measure's own query, when it logged one (the play's `probe.json` holds them all in
  `query_errors`). The usual reasons a select matched nothing, and where to look: [task-check.md](task-check.md),
  "Common reasons and fixes", under "no value in the window".
- **An input that didn't land is listed.** A play's `probe.json` names every input that reached nothing in
  `inputs_missed` (a touch whose widget isn't on screen, a click no control took, a scene the project lacks, a
  stage of a contact nothing took: section 1.4): read it in the fix's play before trusting what the play measured.
  A missed stage of a contact (`pin`, `damage`, `set`) fails every probe of its play on that side, with "a stage of
  the play didn't land: <kind> <target> at <t> s: <why>": what the play read is of a contact that never happened.
- **`needs`** names only earlier checks; check names are unique in the task.

### 3.1 A start that doesn't load: `fails_at_start`

When making the start run is the task (a script of it doesn't parse, so the project doesn't load), mark its build
check:

```json
{"name": "scripts_load", "kind": "build", "fails_at_start": true}
```

The start is then never played, so nothing in the task may need it played: **no start-relative thresholds**
(`calibrate`, `start_times`, `start_plus`; use literal values) and **no judges comparing with the start**
(`"before": true`). The task check requires the start not to build; a start that builds makes the task invalid.

### 3.2 A judge check's own plays: `plays` and `shots`

A `judge` check asks a question, rubric item by rubric item, over screenshots the grader takes itself. Left alone it
is shown the two plays every task shares, the idle `look` and the `drive` of `play_scene`: they never press a task's
own keys, open another scene or leave a title screen. When what the rubric asks about shows only after one of those,
the check names up to 4 task plays (section 1.1) in `plays`, and its screenshots are taken in those plays instead:

```json
{"name": "upgrade_menu_reads", "kind": "judge", "required": false, "needs": ["boots_clean"], "before": true,
 "question": "With the upgrade menu open, does it read the way the request asks?",
 "rubric": [{"key": "costs_legible", "criterion": "Each upgrade's cost is legible against the panel behind it."}],
 "plays": [{"name": "open_upgrades", "seconds": 10,
            "inputs": [{"t": 0.5, "key": "<Keyboard>/u", "press": true},
                       {"t": 0.7, "key": "<Keyboard>/u", "press": false}]}]}
```

- Each is a task play under the rules of section 1.1. Its name appears once in the check; a play with the name of
  another check's play (a probe's or another judge's) must be identical to it, and is then played once and serves both.
- The judge is shown 5 screenshots of each play, taken at 10, 30, 50, 70 and 90% of its `seconds` (a 10 s play: 1, 3,
  5, 7 and 9 s). Time the inputs so that what is judged is on screen at those moments.
- Each play is played on every side the check shows: the agent's game, the start with `"before": true`, the fix with
  `"reference": true`. So it must run on the start as well; an input that does nothing there is fine.
- `shots` (2-20, default 5; only on a check with `plays`): how many screenshots of each play the judge is shown,
  evenly over it: screenshot i of N at `seconds` x (i + 0.5) / N. The check's plays times its `shots` are 20 at most
  (one play of 20, two of 10, four of 5). A short play with many is a run of frames in which motion shows: a 5 s play
  with `"shots": 20` is a frame every 0.25 s. A play two checks name is played once, with the most either asks.
- Motion that is a number (how fast, how abruptly, how far) is a probe's to measure, not a judge's: a field over a
  window, `step` on a play sampled every 0.1 s (section 2.1), `spin`. Motion that can only be seen (feet that slide
  over the ground, a trail behind a blade) is a judge's, with a short play and many `shots`.
- A play's named shots (`shot` inputs, section 1.1) are shown too, every one, in the order taken, beside its `shots`
  evenly spaced ones; the check's plays times its `shots`, plus their named shots, are 20 at most.
- A check without `plays` is shown `look` and `drive`, as before.

The task check asks no model. It plays each `judge` check's plays on the start and on the reference and saves the
screenshots the judge would be shown: its `shots` evenly spaced ones of each play and every named one, 20 at most, or
the 6 of `look` and the 8 of `drive` for a check without `plays` (the developer's `route` isn't played locally). They
go under `<task>\judge-shots\<check>\start\` and `reference\`, named `<play>_<nn>.png` in the order taken, with
`ask.md` (the brief, the question, the rubric, what each picture is) and a blind copy: `blind\A\` and `blind\B\` hold
the pictures both sides have, and `blind\key.json` says which side each is. Each side's own picture count and notes
are in `sides.md`, opened with the key. A play a probe names is the same play and is played once.

Look at them yourself before calling a task with a required judge VALID, blind: score every rubric item for A and for
B first, then open the key. The start must fail every required rubric item and the reference must pass every one.
Write both sides' answers in the task's notes (its `tasks-workflow.jsonl` row). A task try saves the same for the
agent's game (`agent\`) under `<task>\run<N>\judge-shots\`: answer its judges the same way before calling the task
too easy or held. `tools/validate-game.py` checks the rules of a judge's plays.

## 4. The task check

Before any agent is given a task, the checker grades the start and the fix with every probe
([task-check.md](task-check.md)). A task is valid when:

- the start builds (unless the task says it doesn't, section 3.1: then it must not);
- the fix builds, boots and passes every required probe (its other checks only add notes: a `log_absent` or
  `file_exists` it fails, a probe that isn't required);
- the start fails every required probe outside `still_works`, of which there is at least one (or the `fails_at_start`
  build check);
- a no-op scores zero: no check the start passes carries weight, so build, boot and `still_works` checks take
  `"weight": 0`, as does any other check true of the start, a `log_absent` or `file_exists` check or a probe,
  `"required": false` ones included (the score is the weighted share of checks passed);
- every required `still_works` probe passes at the start;
- every required calibrated probe measures differently on the start and the fix (one that isn't required and can't
  be calibrated fails as a note, never making the task invalid);
- every required `judge` check, answered by the task's writer from the screenshots the check saves (section 3.2),
  fails on the start and passes on the fix, item by item.

Run every check before the task is submitted, on both sides, and read what it measured: it fails on the start and
passes on the fix, the play's inputs landed (`inputs_missed` empty, `probe.log`), the select matched something (the
rows), and a judge's frames show the moment asked about. A threshold comes from the instruction, from the start or
from calibration (section 1.2), never a number picked because the fix passes it. The fix does everything the instruction asks, in a place a play reaches.

A task with no fix is checked on its start alone: the start builds, fails every required probe outside `still_works`
(thresholds literal or relative to the start) and passes its still-works probes. Only a draft has no fix: the
validator refuses a task without `seed.reference`. A task that fails the task check is not run; a run on an invalid
task is void.

## 5. Lessons

- **Mouse axes go through the game's own scale.** An axis event's value is not degrees: `<Mouse>/delta/x` is a mouse
  movement in pixels, and the game's look sensitivity scales it. A play that assumes `"axis": 90` turns the camera 90
  degrees barely moves it. Read the game's look scale at the seed and size the axis values (or send several events)
  so the camera really turns, then measure the turn.
- **A game reads keys in more than one way.** A key input is an event with the key as both `keycode` and
  `physical_keycode`: an input action bound to that key, `Input.is_key_pressed` and `_input` all take it. A game
  that reads a key no control path names (a scancode of its own, a second keyboard) is not driven: check the game's
  input code at the seed before writing a task play.
- **A `Button` presses for one finger.** The engine presses a `Button` node through the mouse it emulates from the
  first finger down. A tap on a `Button` while another finger holds a stick presses nothing: tap it when no other
  finger is down, or expect such a button to read touch events itself (section 1.3).
- **Check that a play really reaches the situation.** A probe of a moment the play never reaches measures nothing
  useful. Teleport to the spot (`teleport` input), use a scenario (`scene`/`args`) that starts there, and check on
  the fix that the play gets there before trusting its threshold: the fix's `probe.json` holds the player's `track`
  and its `inputs_missed`, and its `probe.log` names what each `teleport_to` reached.
- **The main scene doesn't run before `play_scene`.** A play that opens another scene never loads the project's main
  scene (section 1.1): what a boot scene sets up is missing there, though the autoloads run. Such a game is started
  through its own `play_args` with `play_scene` null.
- **A measure that reads the same on the start and the fix can't gate.** If both sides give the same value, the probe
  doesn't see the bug (a required calibrated one makes the task invalid outright). Pick a measure the fix actually
  changes.
- **Calibrate thresholds between the start and the fix.** Use `calibrate` (or literal values that sit clearly between
  what the start and the fix measure), never a threshold guessed from the fix alone: another valid fix must pass and
  the start must fail.
- **Angles compare as angles.** Yaw, pitch and roll wrap at 180; comparing raw values fails across the wrap (179 and
  -179 are 2 degrees apart). Use `to_angle` (a direction) or `to_axis` (an axis, either way along it).
- **Angles are the engine's.** A camera that looks down has a negative pitch, and a positive yaw turns left: read an
  angle off the fix's play (its `probe.json` camera rows are `[t, x, y, z, pitch, yaw, fov]`) rather than work it
  out.
- **Value-reading measures need a reducer.** `of` defaults to `count`; to read an object's or a widget's value write
  `"of": "first"` (or `min`, `max`, `mean`, ...).
- **Test the outcome a player sees, never the implementation.** "The hero stands on ground", not "spawn_height is
  0.92"; another valid fix must pass.
- **Read names from the game.** Classes, script names, groups, node and Control names and scene paths come from the
  code and scenes at `seed.commit` and `seed.reference`, never guessed. A wildcard takes in every name it fits
  (`Coin*` matches `CoinSpawner` too), and a node the code adds without naming it gets a name of the engine's:
  select the objects you mean, by their class or group, and check in the fix's play what a select reached.
- **Hidden is not gone from the tree.** A node switched off by hiding it is still in the tree: a select without
  `"inactive": true` no longer finds it, one with it reads its `active` 0. A light switched off by energy 0 is still
  shown: read its `on`.
- **A lamp need not be a light node.** A build may light a lamp with a `Light3D`, with an emissive or an unshaded
  material and no light at all, with a shader of its own, or with a particle effect: read `lit` of the lamp, which
  sees them all, not `count` or `on` of its lights; `glow`, calibrated or relative to the start, only where the ask
  is about how bright, and never in a play that also reads a `render` budget.
- **A broken object still draws.** A crate broken into pieces may keep every piece drawn and in its group, so
  `count` and `visible` can't see it go: read `simulating` of the crate, or the pieces' `speed`.
- **A HUD need not be one kind of node.** A build may show its score in a `Label`, a `RichTextLabel` or a `Button`:
  check what it shows with `ui` (text with `match`, counts by `kind` and `rect`), which reads them all the same;
  `widgets` sees only the widget it names.
- **Brightness on screen goes through calibration.** A `screen` threshold is always calibrated between the start and
  the fix (or relative to the start), and its window starts after the scene has settled (a fade-in, a teleport).
- **The screen includes the UI.** A `screen` rect over the HUD measures the HUD: keep it on the scene.
- **A sound made in code has no name.** A stream a script builds, or a copy of a stream, has no file behind it, so
  no `sound` select finds it: read `level` (calibrated or relative to the start) in a play that hears it, select
  its player by `owner`, or count it with `started_audible`; `sounds` and `repeats` have no value for it.
- **A contact is staged, never waited for.** No fixed play is sure to bring a foe within reach: `pin` it ahead of
  the player and press the task's own attack key, or `damage` the one struck at a time the play knows, then read
  the window right after it (section 1.4). Check the fix's `probe.log` and `inputs_missed` for what each stage
  reached.
- **A budget is read where the game is heaviest.** A `render` reading is of the frames a play drew: teleport to the
  view the budget is about and read `max` over a window there, in a play of its own.
