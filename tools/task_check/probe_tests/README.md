# The probe's tests on the real engine

`tools/task_check/task_probe/` runs inside a running game, so only the engine can tell whether a measure reads what it
says. These tests play a small game with the addon the way the task checker plays one, and check every value. A field
that no play here checks is not tested.

## Running them

```
python tools/task_check/probe_tests/run.py <work folder> [--godot EXE] [--rendered] [--desk] [--play NAME ...] [--once] [-v]
```

`<work folder>` is a scratch folder the run may fill and empty: it copies the game there, never plays it in place.
The engine is `--godot`, else `GODOT_EDITOR`, else the machine's pinned Godot (`machine/lib/ggfroot.py`).

The run:

1. copies `project/` to `<work folder>/desktop` and adds the probe as the checker adds it (`seeds.add_probe`): the
   addon as `addons/task_probe/`, its autoload first in `project.godot`, a user data folder of the copy's own. The
   project's `project.godot` holds lines a game may hold that would stand in for the probe's (a second `[autoload]`
   with a quoted `"TaskProbe"`, a second `[application]` that turns the user folder off, an autoload set before every
   section), and game autoloads (`game/order.gd`, `game/early.gd`) that print whether the probe loaded before them and
   where the game keeps its saved data: `keys` checks that the probe loaded first, the game's autoloads after it, and
   the copy's own user data folder;
2. imports the copy (`--headless --import`), which must log no script error;
3. runs each play as the checker runs one (`--fixed-fps 30 --disable-vsync --audio-driver Dummy`, the spec after
   `-- -taskProbe`), headless;
4. checks what each play wrote, plays `touch`, `second`, `contact` and `sounds` a second time (the second must write
   the same probe.json as the first; `sounds`, paced to real time, must list the same starts), prints one line per
   play and exits with 0 when everything passed.

```
probe tests in /w/probe (addon: .../tools/task_check/task_probe)
ok    import (desktop)  2 s
PASS  desktop.keys         91 checks  7 s
PASS  desktop.touch        20 checks  same twice  0 s
FAIL  desktop.second       17 checks, 1 failed  0 s
      FAIL its speed: got 80.0, want 100.0 +- 0.5
...
```

`--play` runs some plays, `--once` leaves out the second play, `-v` prints every check. What each play wrote is kept in
`<work folder>/<variant>/Logs/ProbeTests/<play>/` (probe.json, probe.log, the screenshots, the game's log, the spec).

Headless, the engine runs the scene tree, the scripts, the input events, the physics and the audio mix, but draws
nothing: a headless play writes no screenshot, a `screen` sample has no value and `render` reads 0. `--rendered` runs
the plays that need a drawn frame instead (`frame`, `lamps_drawn`, `lamps_reach`, `places_drawn`, `field_drawn`), in a window, twice over: as a desktop game (`desktop`: a
1920x1080 project read at 960x540) and as a portrait phone game (`portrait`: a 1080x1920 project on the Mobile
renderer played at 1080x1920, whatever the screen). It needs a GPU and a desktop; `--desk` starts each play on a
Windows desktop of its own (`../desk.py`), as the checker does, so nothing shows on the screen.

## The game (`project/`)

One scene, `scenes/Main.tscn`, with something for every measure and input, `scenes/Second.tscn`, a 2D scene, and
`scenes/Duel.tscn`, a fight to stage: a `Player` whose `take_damage` slows the game for three frames, a `Foe`
(`game/foe.gd`) that walks to and fro and stops for 0.2 s when hit, a spark coming and going below it, a dead
`Corpse`, a `Guard` whose `take_damage` is on a node below it, a `Dummy` whose `take_damage` has a third argument, a
`Lamp` whose `take_damage` has one, and a `Post` that takes no damage; `game/duel.gd` gives the player a blow (J), a
pause (P) and a stop of the game's time (O).
`scenes/Sounds.tscn` (`game/sounds.gd`) starts a sound for each of its keys and pauses the game for six frames on P.

| Node | What it is for |
|---|---|
| `Player` (`game/player.gd`, group `player`) | a `CharacterBody3D` that moves 4 m/s on W/A/S/D (input actions) and where the virtual stick is pushed |
| `Camera`, `Sun`, `Lamp` | the camera (at 0, 6, 8, pitched -30), a light that is on and one of energy 0 |
| `Crates/Crate1..3` (group `crate`) | three boxes, the second scaled, the third hidden |
| `Spinner` (`game/spinner.gd`, `class_name Spinner`) | a box that turns 90 degrees a second |
| `Ball` | a rigid body |
| `Sparks`, `Spent` | a particle effect that emits and one that doesn't |
| `Many` | 250 nodes of the group `many`, made at the start: more than a sample keeps rows of |
| `Coins` (`game/main.gd`, `game/coin.gd`) | a coin made every second, three kept: a script without a `class_name` |
| `Music`, `Jump` | a looping sound (a stream named in code) and a placed one-shot sound Space plays |
| `HUD/CountLabel`, `ZoomLabel`, `BackLabel`, `KeyLabel`, `VisitsLabel` | what a tap, the wheel, the back button, a key or a gamepad button did; how many times the game started on its saved data |
| `HUD/Health`, `HUD/Secret` | a bar at 75%; a hidden panel Escape shows |
| `HUD/TapButton` | a `Button`: it counts presses (the mouse, or the first finger) |
| `HUD/GhostButton` | a `Button` drawn fully transparent (`self_modulate` alpha 0): not on screen to `widgets`, pressed by a click all the same |
| `HUD/FireButton` (`game/fire.gd`) | a panel that reads touch events itself: it counts any finger |
| `HUD/MoveStick` (`game/stick.gd`) | a virtual stick |

`main.gd` also quits the game at the time `-quitAt <seconds>` names (the `shutdown` play).

## The plays (`plays/<name>.json`, checked in `tests.py`)

A play file is a spec as the checker writes it (CONTRACT.md section 5) without `format`, `out` and `size`, each query
with an id of its own.

| Play | What it proves |
|---|---|
| `keys` | keys through an input action, the wheel, a widget click, the cursor and the left button, a gamepad button, a teleport with a hold, `teleport_to`, a view turn; every kind's fields on the scene above: object selects (group, name, class, `near`, `has`, `where`, `inactive`), `prop:` paths, parts, speed and spin, extents, 200 rows of 250 with `total` and `full`, components (class, `effect`, `mesh`, lights), spawns, the camera, widgets, ui, audio (count, volume at the listener, level, `started`, selects by name, bus and owner), render's keys; the saved data cleared; an unknown key and a click that finds nothing |
| `touch` | a tap on a named Control, a drag that holds the stick over, a second finger's tap meanwhile, `<Keyboard>/escape` as the phone's back button (the spec says `touch`), a Control by its class, and the misses: a widget that isn't there, a finger still down |
| `touch_drawn` (`--rendered`) | the same play with a frame, on both layouts: the stick stands at 0.135 of the frame's width, so the drag to `[0.135, 0.6]` pushes it straight up on the desktop's and the portrait phone's alike |
| `captions` | a widget click and a tap by the caption a button shows (`scenes/Captions.tscn`): a button named `Button2` reading "Begin Run" clicked by `begin_run`, a button named `Start` clicked by name though another reads "Start", two reading "Again" (the upper one, noted), a label on a `TextureButton` as its caption, a tap by caption, a button and a panel in a scrolled list's view; the misses: a caption drawn see-through, no match, a button and a panel scrolled out of the list's view (their centre outside it), an `optional` click with no match (sent as any click) |
| `second` | the spec's `scene` opened, a 2D player and a 2D camera, a 2D node pinned ahead of the player, a `scene` input, a scene the project lacks |
| `contact` | a contact staged and read: `set` (a property on the nearest match a `where` picks, a colour's part on every match, a class first), `pin` (`front` of the player at its own height and facing it, held while the player's own blow lands; `at` a point), `damage` (from a named object, from the player, onto the player, through a node below, a method with a third argument), `damage_taken` (none for an object no stage struck), `frozen` (none before the hit, 0.2 s after it with a child spawned and freed meanwhile, a stop of the game's time), `world` (the game slowed for three frames, its time stopped for four, a pause of six), `"player": false`, and every stage's miss |
| `sounds` | the sounds that start: one-shots on players made and freed between two samples, one shorter than a frame, a player played again while it plays (in the next frame too; a 3D one; a looping stream; one whose stream picks a take), a pause and its end (no start), a placed one out of earshot, one on a muted bus and one on a bus that sends to it (not audible), a stream without a name, a player of voices (the samples' `voices_unseen`); `started` on its own rule beside them; selects by name, bus, owner (of a player freed by then) and `near` (a point that isn't there: no value); two plays agree on every start |
| `lamps` | `lit`, `glow` and `has.lit` (`scenes/Lamps.tscn`, built in `game/lamps.gd`): a lamp lit by a light, a coloured one, an emissive and an unshaded material, an emissive next pass, a particle effect (lit, no glow), smoke (not lit), a hidden lamp, an unshaded lamp faded to alpha 0, a light under a hidden holder, an editor's light, a mesh on no render layer and one that only casts a shadow, a 2D light; each off and on; lights, meshes and effects as components; headless, the lamps whose light only a drawing tells (a shader of the game's own, a texture on the emission) have no value, and the play says why |
| `lamps_drawn` (`--rendered`) | the same play with a frame, played twice for the same answers: a shader that emits, a white emission texture, a shader whose light changes every frame (lit in every sample and through `has.lit`), a 10 cm glowing band on a 4 m post and a pure blue shader read lit; the same shader with its emission off, a black emission texture, the post with a dark band and a two-surface glowing mesh under a dark override read dark, each drawn alone, the dark ones with no pixel above black; the first sample is completed by its frame and a `has.lit` select's first sample has no value; `probe.log` notes a drawing when its answer changes and the frame's draw calls once |
| `lamps_reach` (`--rendered`) | a `teleport_to` with `has.lit` on a shader lamp in a play with no query: skipped while the lamp is off, next to it once on |
| `crates` | `changed`, `bounds_change`, `pose_change` and `spread` (`scenes/Crates.tscn`, built in `game/crates.gd`): a crate that breaks on B by hiding its whole mesh and showing pieces that fly 0.75 m apart, one that plays a break animation (its lid and a bone of its rig lift 1 m), one left alone, one pushed 1 m whole (changed, its spread the same), one freed (no row, its count 0), one that breaks into rigid bodies (simulating, spread grows); whole and broken; played twice for the same readings |
| `field` | `ground` and `pieces` (`scenes/Field.tscn`, built in `game/field.gd`): the ground at a point with the player on it, on a hill, under a roof and through it with a select, nowhere, over a box; the ground on a crate that is a rigid body; pieces of mesh instances (one hidden), multimeshes drawing some, all and none of their slots, a grid map with a turned cell, a CSG shape with one inside it, a farther level of detail and an empty mesh, by class, mesh, owner and near (headless, a multimesh's instances stand at its own place); a `Label3D` in view as ui text, one behind the camera and a hidden one not, billboards on a turned node and a plain one alike, none in a select of boxes or of a corner; a mouse move spread over a second (half done half way) and one at once |
| `field_drawn` (`--rendered`) | the same with a frame: the multimesh's instances by their own places |
| `places` | `drawn` headless (`scenes/Places.tscn`, built in `game/places.gd`): no value, and the reason once a place |
| `places_drawn` (`--rendered`) | `drawn` with a frame: a red box that turns (moves; its base colour red, the sun and a yellow ambient light left out), a blue box that glows green (reads blue), an empty place with a wall just outside it and a sky dome around all (0), particles (move), a still box (motion 0), the same box's place above its top (0), a beam 4 m long along a line (reach and length), a second place over the turning box (its layers given back as they were), a black wall on a layer the camera leaves out (drawn 0, the frame not black), a still box under a light that flickers every frame (motion 0), a beam 5 cm thick along a 30 m line (the same reach in two plays), 1100 small boxes in one place (no value, and why), one CPU particle (drawn); under a world exposure and auto-exposure the base colours are the same |
| `errors` | every `query_errors` line a bad query gives, the task's `player` select, a row that is no input |
| `refuse` | a spec of another format: exit code 2, nothing written |
| `idle` | without `-taskProbe` the addon does nothing |
| `shutdown` | a game that quits by itself: `ended` `shutdown`, the samples kept |
| `wait` | a `wait` takes its real time and the clock holds |
| `kept` | a spec that says `keep_saves`: the play starts on what the play before it saved, what it saved when it was told to close too (`wait` is played first) |
| `fresh` | any other play starts clean, whatever the play before it saved |
| `frame` (`--rendered`) | screenshots of exactly the frame's size without alpha, a tap on a named Control landing, `screen` and `render` with values, at 960x540 and at 1080x1920 |

Not covered by a play: `clip` and `anim:`, a 2D game's `extent_*`, `rel_yaw:` and audio fall-off, a 2D player `near`
a point, `has` `visible`,
`facing_vs_velocity`, a widget's `percent` of a slider and its `brush`, a mouse `delta`, a gamepad axis, `face` of a
`teleport_to`.
