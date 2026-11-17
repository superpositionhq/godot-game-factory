# Godot task verifier: engineering contract

The task verifier of godot-game-factory: the checker (`tools/task-check.py`, `tools/task-try.py`,
`tools/task_check/*.py`), the validator (`tools/validate-game.py`), the task schema
(`docs/schemas/game-task.schema.json`) and the probe, the GDScript addon `tools/task_check/task_probe/` that the
checker adds to its copy of a game. A change to any of them is checked against this file. It holds the terms and units
(section 1), the task format and the rules beyond the schema (section 2), how the probe reads each measure (section 3),
the plays and inputs (section 4), the files the probe and the checker exchange (section 5) and the probe addon
(section 6).

The users' documents describe the same behaviour for their readers and must agree with this file:
`docs/task-probes.md` (what each measure means, for a task's author), `docs/task-check.md` and `docs/task-try.md`. What
a field means is there; this file holds what an implementer needs beyond it.

## 1. Terms and units

| Term | Meaning |
|---|---|
| object | a Node. Its **parts** are itself and the nodes below it |
| shown | in the tree and not hidden: the nearest node at or above it that can be hidden (a `CanvasItem`, a `Node3D`) reads `is_visible_in_tree()`, and no `CanvasLayer` above it is hidden (`Find.shown`). A node that isn't shown is **inactive**: a select leaves it out unless it says `"inactive": true` |
| player | the first node the task's `player` select matches (when it matches nothing there is no player: no fallback), else the first shown node, in tree order, of the group `player` (then `Player`), else the first shown `CharacterBody3D`, else the first shown `CharacterBody2D`, else the player camera (next row); looked up again before the game's scripts and after them (`task_probe.gd` `player`, `_find_player`) |
| player camera | the window's current `Camera3D` (`Viewport.get_camera_3d`), else its current `Camera2D` (`task_probe.gd` `view`, looked up once a pass) |
| scene | the scene a play opens and the game's arguments: `play_scene` (`res://scenes/X.tscn`) and `play_args` (`["-scenario", "2"]`, after `--` on the engine's command line) |
| class | what a select's `component` names: an engine class (`MeshInstance3D`; the classes it inherits match, `Node3D` takes every 3D node), a script's `class_name`, or a script's file name without its extension (`coin` for `coin.gd`); a script that extends another matches the other's too (`Find.is_a`). A name no node can be of (no engine class, no `class_name`, no script file of the project) matches nothing and says so once (`<kind> <id>: no component type <name>`) |
| tag | a group (`Node.is_in_group`) |
| widget | a `Control` node of the game's window |
| frame | what the game's window shows, at the play's exact size (section 4). A rectangle or a point of it is in fractions 0-1 from its top left, y down |
| units | m and m/s for a 3D node. A 2D node (a `Node2D`, a `Control`) reads its global position in the engine's 2D units, y down, with z 0, and its rotation as `roll`. Limits: a near's radius up to 100,000 (its `y_min`/`y_max` within +-100,000), a teleport's `distance` and a camera point's `forward` up to 1000 |
| axes and angles | Y up, -Z forward. `pitch`, `yaw`, `roll` are a node's `global_rotation_degrees` x, y and z, normalised to (-180, 180]: yaw 0 looks along -Z and a positive yaw turns left (counter-clockwise seen from above); a positive `pitch` looks up |
| build | the scratch copy made ready to play: the engine's import, then every script loaded (section 5). There is no player build: a play runs the copy from source with the editor binary |
| play | the copy run with the editor binary and the probe, started by the checker on a Windows desktop of its own (`desk.py`): nothing on the user's screen, no keyboard or cursor taken. Its frame is 960x540 for a desktop game and the phone's size for a mobile game (1920x1080 landscape, 1080x1920 portrait: the copy's `Platform.json`) |
| engine | Godot 4.7: `project.godot` `config/features` holds `"4.7"`; task `"engine": "godot-4.7"` |
| machine | `GGF_ROOT`, `ggfroot` (`machine/lib/ggfroot.py`: `root()`, `godot_exe(console=True)`, `check_free(path, what)`), `godot-heavy.ps1` (`machine/tools/`, run as `<root>\tools\godot-heavy.ps1`) |

Forward vector from a camera row: `[-cos(pitch) * sin(yaw), sin(pitch), -cos(pitch) * cos(yaw)]` (degrees in; the
probe's own `{"camera": true}` point uses the camera's -Z axis, the same direction). "Height" is `y` (index 2 of a
`[t, x, y, z]` row).

## 2. The task format (`game-task/1`)

The task format is `docs/schemas/game-task.schema.json`. This section gives what of it an implementer needs beside the
code, the validator's rules beyond the schema (`tools/validate-game.py`) and the task check's own rules (`verdict.py`,
`probes.py`).

The task:

- `engine`: const and default `"godot-4.7"`.
- `play_scene` (string or null; `^res://[A-Za-z0-9_ /.()-]+\.(tscn|scn)$`, at most 300 characters) and `play_args` (at
  most 16 strings; default `[]`).
- `player` (optional): an object select that names the player (section 1) for every play of the task. It stays in the
  agent's half of a split task (`tools/split-tasks.py`: it names an object; it isn't an answer).
- Every check names its `kind`: required, with no default, since a check that gave only its `name` would fit several
  shapes at once (`build`, `boot`, `package`).

Plays and inputs:

- A task play: `name`, `seconds`, `every`, `inputs`, `scene`, `args` and `after`. `scene` and `args` have no default:
  a play's own key, when it is there, takes the place of the task's `play_scene` / `play_args` for that play
  (`"scene": null` opens the project's main scene). `after`: 1 to 8 names of task plays of the task (a probe's play, a
  judge's own plays); the validator refuses a name that is none (`look` and `drive` are none), a name twice, the play
  itself, a cycle, and two names of which neither runs after the other through its own `after`
  (`play_after_errors`).
- Play arguments (`play_args`, a play's `args`): each `^-?[A-Za-z0-9_.:=,/-]{1,60}$`, at most 16. They follow `--` and
  the probe's own `-taskProbe <spec>` on the command line, so the engine never reads one as its own flag: the game
  reads them with `OS.get_cmdline_user_args()`. The validator refuses the probe's own (any flag starting with
  `taskprobe`, any case) and a flag that would choose the renderer or the frame's size (`--rendering-method`,
  `--rendering-driver`, `--resolution`, `-size`).
- Inputs (section 4): `key` (key and axis rows) is a control path,
  `^<(Keyboard|Mouse|Gamepad)>/[A-Za-z0-9/]{1,40}$` (`<Keyboard>/escape` is the back button in a mobile game's
  play); a widget click's
  `widget` is a wildcard on a name, or a class name (`^[A-Za-z0-9_.*?() -]{1,120}$`); a touch's spot is `[fx, fy]` or
  `{"widget": "<name>"}` (the same pattern); `teleport_to`'s `distance` defaults to 2 m.
- Touches (`tap`, `drag`): one finger's touches are at least 0.1 s apart, from one's lift to the next one's start, and
  every touch is over by the play's end (the validator's `TOUCH_GAP`).
- The stages of a contact: `pin` (an object select, `hold` above 0 up to 120 s, `front` 0 to 1000 m or `at` a point,
  `offset`), `damage` (above 0, `to` and optionally `from`, object selects), `set` (a path of up to 6 members without
  an index, `on` an object select, `value` a boolean, a number or a string of at most 120 characters, `all`). The
  validator refuses a pin whose select says `"player": true` and one with both `front` and `at`.

Selects and points:

- `component` in every select (object select, `has`, components, widgets) and in `spawns`: a class name,
  `^[A-Za-z_][A-Za-z0-9_]{0,120}$` (what it matches: section 1).
- Object select (`Select`): `component` (the node's own class), `tag`, `name` (a wildcard on the node's whole name,
  any case), `near`, `has`, `where`, `player` (true: the player alone; false: every node but the player and the nodes
  below it), `inactive` (true lets nodes that aren't shown match). `has`: `component`, `lit`, `visible`, `near`,
  `simulating` (at least one key; `lit`, `visible`, `simulating` only `true`). `where`: 1 to 4 conditions `{"prop":
  <path>, "op": "==|!=|>|>=|<|<=", "value": <number, boolean or string>}`, every one must hold.
- Component select: `component` or `effect` or both, `name`, `owner` (an object select), `near`, `mesh`, `visible`,
  `inactive`.
- Widget select: `component`, `name`, `text` (a regular expression on its text), `visible`.
- UI select: `kind` (`text`, `box`, `image`), `text`, `rect`.
- Audio select: `sound` (a wildcard on the stream's name), `sound_class` (a wildcard on the bus's name), `owner`,
  `near`.
- A name a wildcard reads (`name`, `mesh`, `sound`, `sound_class`) may hold parentheses and spaces:
  `^[A-Za-z0-9_.*?() -]{1,120}$`.
- Points: `{"xyz": [x, y, z]}`, `{"player": true, "offset": [x, y, z]}`, `{"camera": true, "forward": m}`,
  `{"object": <object select>, "offset": [x, y, z]}`. `near`: `{"point", "radius", "y_min", "y_max", "y_relative"}`.

Measures:

- Probe kinds: `player`, `camera`, `objects`, `components`, `widgets`, `ui`, `screen`, `spawns`, `log`, `audio`,
  `render`, `world`. A check's `play` is `look`, `drive` or a task play.
- `objects` fields: the schema's pattern lists them. A Part name (`rel_yaw:`, `world_yaw:`, `world_pitch:`,
  `world_roll:`, `forward:`) is a node's name, `[A-Za-z0-9_][A-Za-z0-9_ ()-]{0,63}`; an `anim:` parameter may hold
  dots and slashes (`anim:conditions/jump`, `anim:Blend2/blend_amount`).
- `components` fields include `prop:<path>` (on the node itself); the measure takes `match` (a `prop:` string).
- `spawns`: `{"probe": "spawns", "component": "<class>", "field": "spawned|destroyed"}`.
- `audio` fields: `count`, `audible`, `volume`, `max_volume`, `level`, `started`, `started_audible`, `sounds`,
  `repeats`.
- `render`: `{"probe": "render", "field": "draw_calls|triangles|texture_mb"}`.
- `world`: `{"probe": "world", "field": "time_scale|flow|paused"}`.

The validator's rules beyond the schema include:

- a screen rect has x0 < x1 and y0 < y1; a player measure's `dist` has its `to`; a measure sets `to_angle` or
  `to_axis`, not both, and `window` or `at`, not both;
- every regular expression of a measure compiles (`match`, a log's `pattern`, a select's `text`), so none can stop the
  task check;
- the task's `player` select names no `player` and no point on the player (it says which node the player is);
- a project path (the task's `play_scene`, a task play's `scene`) has no `.` or `..` part and no empty one;
- an audio measure's `sounds` or `repeats` takes no `agg` (`AUDIO_NAMED`);
- a drawn measure takes `near` or `line`, one of them, and the fields of that one (`DRAWN_NEAR`, `DRAWN_LINE`); a
  ground measure takes `xz` or `box`, one of them, and the fields of that one (`GROUND_POINT`, `GROUND_BOX`), a box
  with x0 < x1 and z0 < z1;
- a task play's mouse `move` ends within the play (`t` + `over` at most its `seconds`);
- a play that takes a `render` measure takes no reading that can make the probe draw: no `drawn` measure, no objects
  or components measure of `lit` or `glow` and no select with `has.lit`, in its measures or its inputs, and the task's `player`
  select has no `has.lit` when any play takes one (`captures`, `render_errors`);
- a warning, never an error, when a `teleport_to`, a `pin`, a `damage`'s `to`, a `set`'s `on` without `all`, an
  object point or an `"of": "first"` measure takes its one object by a wildcard name and nothing else: a spawner, a
  pool or a parent named like the things fits too;
- a required probe's play names nothing only the reference has in a `teleport_to` or a stage's select (`pin`, `to`,
  `from`, `on`), as in its measure (`probe_names`).

Fields whose threshold is never a literal (calibrated or relative to the start only; the validator's `NEVER_LITERAL`):
objects `spread`, `bounds_change`, `pose_change`, `glow`, `spin`; components `intensity`, `extent_*`, `glow`, `spin`;
pieces `triangles`, `visible_triangles`; ground `range`; drawn (all but `drawn`); `screen` (all); audio `volume`, `max_volume`, `level`. A `render` field takes a literal: a budget is a number of its
own. Objects `spread`, `bounds_change` and `pose_change` and drawn `base_change` are calibrated only, never relative
to the start (`CALIBRATE_ONLY`): they read 0 at the start in the usual case.

Six of the task check's rules, each closing a case that would otherwise read wrongly:

- a play with an `inputs_missed` row of kind `pin`, `damage` or `set` has no value for any of its probes, the log's
  too: "a stage of the play didn't land: <kind> <target> at <t> s: <why>", the first such row
  (`probes.unstaged`, `STAGES`). A probe that reads `damage_taken` 0 or a time scale of 1 would otherwise pass on a
  contact that never happened. Rows of other kinds (a touch, a click, a shot, a scene) change nothing;
- a still-works probe is excused only when its start play has no samples ("no samples in the window": the play
  crashed, ended early or wrote no probe file); one that finds nothing to measure in a start that ran counts against
  the task (`verdict.verdict`);
- a check without a reference needs a threshold for every required probe, still-works ones too: an uncalibrated one is
  a reason, "<name> has no threshold: <detail>" (`verdict.verdict`);
- a calibrated threshold anchored on the reference alone (the start measured nothing) needs a reference other than 0
  (`verdict.make_threshold`);
- "no value in the window (nothing it selects was measured); the probe said: <error>" quotes only an error about that
  measure's own query (a `query_errors` line starting `<kind> <id>:`, `<kind> <id> (` or `<kind>: `), never another
  query's (`probes._own_errors`);
- a sample without the player (a `[t]` track row) or without a camera row has no value for the player's and the
  camera's own fields, so a play that ran but never found them fails "no value in the window", not "no samples"
  (`probes.series`).

A `file_exists` glob leaves out the engine's and the checker's folders (`.godot`, `Build`, `Logs`, `android`, `.git`;
`check.SKIP`).

## 3. Measures

What each field means, for a task's author, is `docs/task-probes.md` section 2, and this section doesn't repeat it.
It says, kind by kind, where the probe reads the measure (the script, its constants) and what it writes for the logs
beyond the fields. The reduction (`window`, `at`, `agg`, `of`, `match`, `to_angle`, `to_axis`; every match counted
past the 200 rows through the sample's `total` and `full`) is the checker's (`probes.py`).

- **Selects and rows** (`find.gd`, `query.gd` `write_rows`). Matches come in tree order, as the engine lists the tree
  (`Node.find_children`, depth first): the root's children in order, so the autoloads first, then the current scene;
  the same in every play. The nodes are listed once a pass (`Find.all_nodes`, kept by the probe's `stamp`), so a search
  an input makes never serves the samples. The probe's own nodes (the autoload and what is under it) are never
  selected (`Find.is_own`). An object select's `component` is the node's own class; a `has` takes the node and every
  node below it (the shown ones; all of them with `inactive`). Points nest as deep as `Find.MAX_DEPTH` (3: two object
  selects inside a select's points, the second without a point of its own); a point tries its forms in this order:
  `xyz`, `player`, `camera`, `object`. Every match is read; `write_rows` keeps the first 200 as rows and, when more
  matched, writes `total` and `full`, an entry for every field asked for, in the order asked. A select that matches
  nothing writes an empty `rows` (no `total`, no error): the checker reads a `count` of 0 and no value for any other
  field. Every row has `name` (the node's) and `class`, for the logs: its script's `class_name`, else its script's
  file name without the extension, else its engine class (`Find.class_of`); a components row also has `owner`, its
  parent's name. A field with no value is left out of its row.
- **prop:** (`Find.prop`, `Find.read`, `Find.plain`): a path of members, each a node's or a resource's property or a
  variable of its script (`name in object`, then `Object.get`), a dictionary's entry by its key (a string, a
  StringName or a whole number), a vector's, colour's, rectangle's or transform's part by its own name (`.x`, `.r`,
  `.origin`), `[i]` an element of an array. On an object, `prop:<Class>.<member>` reads the node itself when it is of
  that class, else the first node below it that is; a path that names no class the node is or holds is read on the
  node itself; `prop:<Class>` alone is 1 when the node is or holds one, no value when not. A path of more than 16
  steps reads nothing. The value as the checker takes it (`Find.plain`): numbers and booleans as numbers, a string (a
  StringName, a NodePath) as a string, an object 1 when set and still alive and 0 when not (`null` is 0), an array, a
  packed array or a dictionary its size; anything else (a vector or a colour without its part) no value. A step that
  stops at `null` before the path's end has no value.
- **player**, **camera**: the checker computes every field but two from the track rows `[t, x, y, z]` (the player's
  place, `Find.place`; `[t]` without a player) and the camera rows `[t, x, y, z, pitch, yaw, fov]` of the player
  camera the probe writes every sample (`probes.series`). `fov` is a `Camera3D`'s field of view in degrees (the
  vertical one with the engine's default `keep_aspect`), 0 for an orthogonal or a frustum camera. A `Camera2D`'s row
  is its screen's centre (`get_screen_center_position`) with z, pitch, yaw and fov 0. A player `dist` to an
  `{"object": ...}` point reads an `objects` query of that select's `x`, `y`, `z`. `occluded` and `player_on_screen`
  come from a `camera` query (`queries/camera.gd`; its value repeats the row's fields): a ray of the 3D physics space
  (`direct_space_state.intersect_ray`, bodies only, areas never) from the camera to the player's centre, the player's
  bodies and those under the camera skipped (up to 32 of them); the centre projected into the frame, in front of the
  camera. With a `Camera2D`: `occluded` 0, and `player_on_screen` 1 when the centre is inside the rectangle the
  camera shows. The player's centre is the centre of the box around what it draws (`Find.box`), else its place.
- **objects** (`queries/objects.gd`):
  - `extent_*`: half the world-aligned box around what the node and the nodes below it draw, the shown ones
    (`Find.box`, `Find.own_box`): a `VisualInstance3D`'s `get_aabb()` in the world (a light aside), a 2D node's
    `get_rect()` (a sprite), a `Control`'s rectangle. No value when it draws nothing;
  - `hidden`: 1 when it isn't shown, or it has nodes that draw and none of them is shown; `collision`: 1 when a
    `PhysicsBody3D` or `PhysicsBody2D` in it (an area never) has a `CollisionShape` or `CollisionPolygon` that isn't
    disabled, 0 when it isn't shown; `simulating`: a `RigidBody3D` or `RigidBody2D` in it that isn't frozen;
  - `speed` (`motion.gd`): the node's own velocity when it reports one that isn't zero (a `CharacterBody`'s
    `velocity`, a rigid body's `linear_velocity` when it isn't frozen), else its displacement since the query's
    previous sample over the game time between them, a wait's frames counted;
  - `spin` (`motion.gd`): each node a sample read is followed frame by frame until the next sample (the angle between
    its rotations of two frames, summed), so a part turning many times a second still reads; an object reads the
    fastest of itself and the nodes below it that draw (64 at most); a first sample has a rigid body's own angular
    speed, or no value;
  - a **Part** (`rel_yaw:`, `world_yaw:`/`world_pitch:`/`world_roll:`, `forward:`): `Find.part`, the node itself or a
    node below it of exactly that name, else the first of them of that class. `forward:` is the node's -Z axis in
    the world (a 2D node's +X); `rel_yaw:` the part's yaw less the object's (in 2D, their rolls);
  - `anim:<Parameter>` and `clip`: `anim:` reads `parameters/<Parameter>` of the first `AnimationTree` in the object
    (a number or a boolean; anything else no value); `clip` is the current animation of the first `AnimationPlayer` in
    it that is playing, else of the first playing `AnimatedSprite2D` or `AnimatedSprite3D`, else the current state
    of an active `AnimationTree` whose root is a state machine (`parameters/playback`);
  - `frozen` (`stops.gd`): each node a sample read is followed frame by frame from then on, through later samples
    (a stop under way when a sample falls goes on). Its parts are itself and the placed nodes below it when it is
    first read (`Node3D`, `Node2D`, `Control`; `MAX_PARTS` 64, kept as weak references); its pose is each part's
    global transform (a `Control`'s global position) and the place of every bone of a `Skeleton3D` among them
    (`get_bone_global_pose`, `MAX_BONES` 256). A frame is one of motion when a part's place moved more than
    `MOVED_3D` (0.001 m; `MOVED_2D` 0.01 units), an axis of its basis more than `TURNED` (0.00175: a turn of 0.1
    degrees) or a bone more than `MOVED_3D`. A node that comes to be below it later is no part; a part that is
    freed or out of the tree, and a skeleton whose bones change in number, are skipped: none is motion. A node
    dropped from a sample's rows (hidden, without `inactive`) is no longer followed, and starts anew when it is
    read again. A run of frames without motion
    after a frame of motion, ended by one, of `LONGEST` (0.5 s) at most, is a stop; the sample has the longest that
    ended since the previous sample, 0 when none, and no value the first time the node is read. The pose is
    compared before the game's scripts of a frame, so a frame's motion counts in the next;
  - `spread`, `changed`, `bounds_change`, `pose_change` (`changes.gd`): the object's parts are the nodes in it,
    itself or below it, shown or hidden (`Find.parts` with `inactive`, `MAX_PARTS` 256), that are a
    `GeometryInstance3D` whose `get_aabb()` isn't empty or a 2D node (not a collision object or shape) with an
    `own_box`, never a particle node; drawn (`Changes.drawn`): `Find.shown`, `layers` not 0, `transparency` below 1,
    not `SHADOW_CASTING_SETTING_SHADOWS_ONLY`, a multimesh with `instance_count` and `visible_instance_count` not 0.
    A part's box is `Find.own_box`. `spread`: the diagonal of the `AABB` around the centres of the drawn parts' boxes,
    a skinned `MeshInstance3D` (a `skin`) whose `skeleton` holds two shown `PhysicalBone3D`s or more counted by
    their global positions instead. The other three: each object against the query's first sample of it (kept by
    instance id, forgotten once the object is freed): a part's state is whether it is drawn and its world box; the
    pose is each `Skeleton3D` in it (its bones' `get_bone_global_pose` origins, `MAX_BONES` 256) and each part other
    than the object itself (its global position in the object's own space, 3D or 2D). `changed`: a part's drawn
    state differs, a part drawn then is gone or a part not there then is drawn, a part's box moved more than
    `BOUNDS` (0.01 m: the largest move of any face), a skeleton's bone count differs, or the pose's summed distance
    is above `POSE` (0.05 m); the first sample reads 0. `bounds_change`: the largest face move over the parts
    compared (0 on the first sample, no value without a part); `pose_change`: the summed distance (no value without
    a skeleton or a part below the object). The first sample is per query and instance id: with a `where` or `near`
    select an object is first seen when it first matches, mid-play, and a pooled object hidden and shown again keeps
    its old first sample; a freed object has no row and its first sample is dropped. Units are the game's: metres in
    3D, pixels in 2D, a skeleton's own space for its bones;
  - `damage_taken` (`inputs.gd` `damage_taken`): the sum of what `take_damage` returned for the play's `damage`
    stages on the node or on a node below it; no value when none struck it, or when a call returned no number.
- **components** (`queries/components.gd`): the nodes of the class, or with `effect` alone every particle node
  (`GPUParticles3D`, `CPUParticles3D`, `GPUParticles2D`, `CPUParticles2D`); `effect: true` keeps those that are
  emitting and shown. `mesh` reads a `MeshInstance3D`'s, a `MeshInstance2D`'s or a `MultiMeshInstance3D`'s mesh by
  its resource name, else its file's name without the extension (`Find.resource_name`; a mesh saved inside a scene
  has neither). A field reads the node itself: `extent_*` its own box (`Find.own_box`, a `CollisionShape`'s shape
  too); `simulating` a rigid body that isn't frozen, or a shape of one; `intensity` a `Light3D`'s `light_energy` or
  a `Light2D`'s `energy`, `on` that it is shown and its energy is above 0 (a `Light2D` also enabled); `active` shown
  and, by its class, emitting, playing, not disabled or on.
- **lit, glow, has.lit** (`find.gd` `light_of`, `light_of_object`, `material_light`, `drawn_with`, `part_drawn`): read
  from the nodes' own properties, and for a mesh whose properties don't tell by drawing it alone. One floor,
  `LIT_FLOOR` (0.01, a linear luminance), holds for a light's amount, a material's light and a drawn pixel. One node
  as a source (`light_of`; null for any other node): a `Light3D` (shown, not `editor_only`, not `light_negative`,
  `light_energy` times the luminance of `light_color` above the floor: that product is its glow) or a `Light2D` (also
  `enabled`, not `editor_only`, not `BLEND_MODE_SUB`, a `PointLight2D` with a `texture`; `energy` times the luminance
  of `color` times its alpha); a 3D part (a `MeshInstance3D` with a mesh: each surface's `get_active_material` and its
  `material_overlay`; a `MultiMeshInstance3D` or a particle effect: its `material_override`, else its meshes' surface
  materials; a `CSGShape3D`: its override, else its `material`, else, a `CSGMesh3D`, its mesh's surface materials),
  each material followed by its `next_pass` chain (`MAX_PASSES`, 8, at most), or a 3D effect (`GPUParticles3D`,
  `CPUParticles3D`), dark when it isn't drawn (`part_drawn`: not shown, `layers` 0, `transparency` 1,
  `SHADOW_CASTING_SETTING_SHADOWS_ONLY`, the distance from the probe's camera to its box's centre outside its
  visibility range, a multimesh with `instance_count` or `visible_instance_count` 0) or, an effect, it isn't
  `emitting`. A material's light (`material_light`): a `BaseMaterial3D` that is unshaded gives the luminance of
  `albedo_color` (`unlit`; a bound when it has an albedo texture); else with `emission_enabled` the luminance of
  `emission` (plus 1 when an emission texture is added: `EMISSION_OP_ADD`) times `emission_energy_multiplier`
  (`emissive`; a bound with an emission texture); either times `albedo_color.a` when its `transparency` isn't
  disabled (a bound with an albedo texture); else 0; no material is the engine's default, 0; any other material class
  is unknown. Luminance is linear Rec. 709 of the colour made linear (`Find.luminance`). The brightest material above
  the floor lights the part: glow is that times a quarter of the surface of `get_aabb()` scaled by the node's global
  scale; an effect's glow is null. A mesh instance or a multimesh instance whose properties don't tell (no material
  that gives light whatever its textures, and an unknown material or a bound above the floor) is drawn alone
  (`drawn_lit`, `_room`): its mesh with the part's `material_override`, `material_overlay`, surface override
  materials and instance shader parameters, at the origin, in a `World3D` of its own whose environment has a black
  background, no ambient and no reflected light, seen by three orthogonal cameras (`DRAWN_VIEWS`) fitted to the
  mesh's box, each in a `SubViewport` of `DRAWN_SIZE` (128) pixels a side that updates once. The rooms a frame drew
  are read at `RenderingServer.frame_post_draw` by the queries that wait for them (`needs_frame`, `frame_drawn`, as
  `screen`) or in the next frame (`light_collect`, from `light_tick`, which the probe's `_process` calls once a
  frame): each view's image made linear (`Image.srgb_to_linear`) and converted to `FORMAT_L8` (Rec. 709 weights),
  lit when one byte is above `DRAWN_BYTE` (2: the floor in 8 bits); `glow_read` `drawn`, glow null when lit. A part
  is drawn only when a reading asks for it (a row's field, a select's `has.lit`) and its signature (`_signature`: the
  mesh, each material's and next pass's light-giving properties, a shader's code and every parameter, the instance
  shader parameters) differs from its last drawing's; until the new drawing is read the part keeps its last answer.
  A part whose first drawing isn't read yet is unread: `Find.pending` counts the askings, and a sample whose select
  asked for one has no rows and `"pending": true` (the checker reads no value, `probes.series`). An input row with a
  `has.lit` select has the select looked at every frame from `WARM` (0.2 s) before its time (`Inputs.warm`), and is
  held back while one of them waits for a first drawing, `LIT_WAIT` (1 s) at most. A play that draws nothing
  (`--headless`) leaves such a part unread and says so once in `query_errors` (`lit: a part whose light only a drawing
  tells ... has no value: this play draws nothing (headless)`). `probe.log` notes a drawing whose answer changed
  (`lit: Lamp/Shade drawn alone in a room without light: <n> bright pixel(s), the brightest <b> of 255, lit`) and,
  once, the draw calls of the first frame that drew parts alone. Measured on the factory PC, on Forward+ and on the
  Mobile renderer alike: a shader that emits, a white emission texture and a shader whose light changes every frame
  read 21548 bright pixels of 49152, a pure blue emission 21548 (the brightest 18 of 255), a 10 cm glowing band on a
  4 m post 47; the same shader with its emission at 0, a black emission texture, the post's dark band and a
  two-surface glowing mesh under a dark override read no pixel above 0. The frame that draws n parts has 3 n
  more draw calls in `RenderingServer.get_rendering_info`'s totals, so the validator keeps these readings out of a
  `render` measure's play and refuses a task whose `player` select has `has.lit` alongside a `render` measure
  (`captures`, `render_errors`). The Compatibility renderer is not measured. A CSG shape or an effect with an unknown
  material and no lit one is unread. An object (`light_of_object`) sums the sources of itself and every node below
  it: lit when one is, glow their sum (null when a lit one has none), no value when a source is unread and none is
  lit. A row holds `glow_sources` (the kinds lit, joined by commas) and `glow_read` (`props`, `drawn`, `bound`,
  `unread`) when it has any. `has.lit` keeps a part whose `light_of` is lit.
- **widgets** (`queries/widgets.gd`, `ui_scan.gd`): the `Control`s of the game's window (`UiScan.controls`: a
  `Control` in a `SubViewport` is not the window's) that are on screen (`UiScan.visible`), every one when the select
  says `"visible": false`. The checker leaves `"visible": true` out of a select (the default: one query with the
  select that says nothing) and gives a measure of the `visible` field whose select says nothing `"visible": false`,
  so it reads hidden widgets as 0 (`probes.widget_select`). `component` is the Control's class; with a
  `name`, the class of a Control above it matches too (the row keeps its own class). A rectangle is the Control's
  `size` through `get_global_transform_with_canvas()` (its canvas layer and the 2D camera applied), over the frame's
  own size (`Viewport.get_visible_rect`), so it is in fractions of the frame whatever stretches the frame to the
  window. `visible` (`UiScan.visible`): `is_visible_in_tree()` (a hidden canvas layer included), its own
  `self_modulate` alpha times the `modulate` alphas down to it above 0.004 (`Find.ALPHA_FLOOR`, `UiScan.alpha`),
  inside the frame, and not wholly outside a `clip_contents` Control above it; a Control of no size counts as on
  screen, and another Control covering it is not looked at. A widget click and a touch on a widget find their
  Control by `UiScan.reachable` instead: shown and the `modulate` alphas above the floor, inside the frame (a
  Control of no size counts), its own `self_modulate` and clipping not counted, so an invisible hit area a player
  presses is pressed. How text is read: task-probes.md 2.6.
- **pieces** (`queries/pieces.gd`): over every node in the tree (`Find.all_nodes`, not the probe's own): a
  `MeshInstance3D` whose mesh has faces (`Mesh.get_faces().size() / 3` triangles, read once a mesh a sample) is one
  piece at its global position; a `MultiMeshInstance3D` is one piece an instance it draws (the first
  `visible_instance_count`, all `instance_count` at -1) at its global transform times
  `get_instance_transform(i).origin`; a `GridMap` is one piece a used cell whose item's mesh
  (`mesh_library.get_item_mesh`) has triangles, at `to_global(map_to_local(cell))`; a `CSGShape3D` that
  `is_root_shape()` is one piece of its `get_meshes()`' triangles (a CSG shape inside another is none). Triangles: an
  `ArrayMesh`'s `PRIMITIVE_TRIANGLES` surfaces, `surface_get_array_index_len` / 3 (`surface_get_array_len` / 3
  without an index), read every sample; any other mesh `get_faces().size() / 3`, kept by instance id for the play. A `GeometryInstance3D` whose `visibility_range_begin` is above 0 is skipped (a
  farther level of detail). Drawn: `Find.shown`, and a `GeometryInstance3D` with `layers` not 0, `transparency` below
  1, not shadows-only. `component` is `Find.is_a`, `name` and `mesh` (`Find.resource_name`) wildcards, `owner` the
  node or a node above it among `Find.objects(owner)`, `near` `Find.within` by each piece's place. The value:
  `count`, `visible`, `components` and `objects` (the nodes that hold a counted piece), `triangles`,
  `visible_triangles`; null when `near` doesn't resolve or `component` names no class (said once). With a dummy
  rendering server (`--headless`) `get_instance_transform` reads the identity, so every instance stands at its
  multimesh's own place.
- **ground** (`queries/ground.gd`): the game camera's `World3D` (else the window's) `direct_space_state` (null when
  physics runs on a thread of its own: no value, said once in `query_errors`); a
  `PhysicsRayQueryParameters3D` from (x, 2000, z) to (x, -2000, z), `collide_with_areas` false; a hit on the player
  or a node below it, or with `select` on a node that neither the select's matches nor a node below them is, is
  added to `exclude` and the ray cast again (`MAX_THROUGH`, 32, at most). `xz`: `height` (the hit's y, null with
  none) and `hit`; `box` (sorted to x0 < x1, z0 < z1) on a `grid` x `grid` lattice (rounded, 2-32): `min`, `max`,
  `mean`, `range`, `hits`, `points`. Read at the sample, after the game's scripts of that frame.
- **ui** (`queries/ui.gd`, `ui_scan.gd`): the elements on screen at the sample, a row for each thing a drawn Control
  draws (`UiScan.kinds`, in this order: `box`, `image`, `text`). Drawn (`UiScan.drawn`): visible as above and of
  some size. Then, when the select takes text, each `Label3D` the game's camera (`probe.view()`, a `Camera3D`) shows:
  `Find.shown`, `layers` meeting the camera's `cull_mask`, `modulate` alpha above the floor, text not blank, its
  global position not `is_position_behind` the camera, the rectangle around its corners' `unproject_position` (those
  in front of the camera) meeting the frame; that rectangle in fractions of the frame is its `x`, `y`, `w`, `h`,
  `source` `label3d`, `kind` `text`. Its corners (`label_corners`): `get_aabb()`'s x and y extents from its global
  position along its basis's x and y (a billboard's own box is a cube of its longest side on 4.7.2, so its face is
  instead its text's size, `get_multiline_string_size` times `pixel_size`, about that box's centre: the same as its box
  without a billboard, measured with EXIT, 0.33 x 0.225 m); with `billboard` enabled or particles along the camera's x and y (the basis's
  scale kept), fixed Y along `UP.cross(camera z)` and `UP`; with `fixed_size` times its depth in the camera's view
  (orthogonal: half the camera's `size`), as its shader grows it. What stands in front of it isn't looked at. Rows carry `source` (`control`, `label3d`)
  and `kind`. What a script draws itself (`_draw`, a `draw_string`) is no element: the engine keeps no list of it. `signature`, `number` and `clock` are computed by the checker from the rows
  (`probes.ui_signature`, `ui_number`, `ui_clock`).
- **screen** (`queries/screen.gd`): the frame as displayed, read back once it is drawn (`RenderingServer`'s
  `frame_post_draw`, the root viewport's texture), every UI on it included, over `rect`: whole pixels, rounded out.
  A rect of more than 65,536 pixels is read on an even lattice of its pixels (every n-th each way, the same ones in
  every play). The value: `luminance`, `luma`, `pixels` (how many were read), `size`. A play that draws no frame
  (`--headless`) has a null value.
- **spawns** (`queries/spawns.gd`): every frame of the play, a wait's frames included, the shown nodes of the class
  are compared with the frame before: one there now and not then is spawned (added to the tree, shown, or in a scene
  changed to during the play), one gone is destroyed (freed, taken out of the tree or hidden), so a pooled node reused
  by hiding and showing counts each time; one that comes and goes within one frame isn't seen. The counts are
  cumulative from the clock's start (what is there then isn't counted) and the checker differences them per sample
  (`probes.series`).
- **audio** (`queries/audio.gd`): every `AudioStreamPlayer`, `AudioStreamPlayer2D` and `AudioStreamPlayer3D` whose
  `playing` is true (and matching the select), in tree order, at its volume at the listener: `db_to_linear(volume_db)`,
  times for a 3D one its attenuation at the distance to the current `AudioListener3D`, else to the current
  `Camera3D` (by its `attenuation_model` over `unit_size`, capped at `max_db`, times `1 - distance / max_distance`
  when it has a max distance, 0 beyond it), and for a 2D one `(1 - distance / max_distance) ^ attenuation` from the
  middle of the screen. Bus volumes are left out. `level` and `peak` are the RMS and the peak of the Master bus since
  the previous sample, from an `AudioEffectCapture` the probe adds to that bus when a play has an audio query
  (drained every frame, shared by every audio query); null when no audio was mixed since. A select's `near` keeps a
  2D or 3D player whose place is within it (`Find.within`), never an `AudioStreamPlayer`. The value also holds
  `loudest` (the loudest player's stream name) and `listener` (its node's name).
  `started` counts the matching players whose `playing` is true and wasn't the pass before, since the previous
  sample (one played again while it plays isn't counted; one a pause held counts when it plays on).
  The sounds that start are watched once for every audio query (`_watch`, each pass of every frame, a wait's too):
  the probe knows every player node (those in the tree at its first look, then each the tree's `node_added` brings)
  and connects its `finished` signal. A start is noted (`_note`) when the playback a player plays
  (`get_stream_playback()`, asked only when `has_stream_playback()`) is another object than the pass before: every
  `play()` makes a new one, and a pause (`stream_paused`, a paused tree) keeps it; or when its `finished` comes and
  no pass saw that sound play (`_ended`; a player that stopped without ending is no longer waited for after
  `IDLE_PASSES`, 4, passes without a playback). Players playing at the first look are not noted; two `play()`
  calls between two passes are one start. A start holds the play time, the stream's name (`Find.resource_name`),
  whether that names the sound (not for a stream without a name, nor for one that picks or mixes others:
  `_holds_others`, an `AudioStreamRandomizer`, `AudioStreamPolyphonic`, `AudioStreamPlaylist`,
  `AudioStreamInteractive` or `AudioStreamSynchronized`), the bus, the ids of the player and of the nodes above it
  (so an `owner` select matches a player that is freed by then), the place (a 2D or 3D player's) and whether it was
  audible: its volume at the listener times the gain of its bus and of every bus on the way to Master (`_bus_gain`;
  0 when one is muted) at `AUDIBLE` or more. Each query takes the starts its select matches, in order (`_follow`:
  the stream's name, the bus, an owner among those ids, the place within `near`), and a sample holds those since
  the previous one: `started_audible`, `starts` (the first `MAX_STARTS`, 64, as `{"t", "sound", "named"}`) and
  `starts_total`. `sounds` and `repeats` are the checker's (`probes._heard_names`): over the samples picked, the
  starts by their time; no value when a sample lists fewer than started or a start's name doesn't name its sound.
  A sample holds `voices_unseen` true when a matching player was playing an `AudioStreamPolyphonic` or an
  `AudioStreamGenerator` since the previous one (`_voiced`): the checker then adds "those starts are not seen, read
  `level`" to a reading of `started`, `started_audible`, `sounds` or `repeats` (`probes._unseen_voices`). A select
  whose `near` point didn't resolve at a look since the previous sample gives a null value.
  A play that measures audio is paced to real time (the spec's `sound`); no play is heard, since the checker starts
  every play with `--audio-driver Dummy`, under which the engine still mixes.
- **drawn** (`queries/drawn.gd`): the place is a box: near a point, the `AABB` around its sphere cut to its height
  band (`Find.point`, `y_min`, `y_max`, `y_relative`); along a line, the square tube of `radius` around the segment.
  The game's camera (`_game_camera`): `probe.view()` when it is a `Camera3D`, else the current `Camera3D` of a
  `SubViewport` of the game's own that updates. The parts: every `GeometryInstance3D` of the game (`Find.all_nodes`,
  not the probe's own) that is `Find.shown`, has `layers` meeting the camera's `cull_mask`, `transparency` below 1 and
  isn't `SHADOW_CASTING_SETTING_SHADOWS_ONLY`, whose world box (`world_box`: `get_aabb()` in the world; a
  `GPUParticles3D`'s `visibility_aabb`; a `CPUParticles3D`'s `capture_aabb()`, its emitter's place when that is
  empty, grown by its mesh's box) intersects the place (along a line, grown by the radius, also holds an end of the
  segment or meets it). More than `CAP` (1024): no value, said once in `query_errors`. In the sample each part gets
  render layer 32 (`LAYER`, bit 31) added to its `layers` (remembered: whether it had the bit), and every `Light3D`
  has bit 31 taken out of its `light_cull_mask` and `shadow_caster_mask` (remembered the same way); when the frame is
  drawn (`frame_drawn`) the bit is cleared from a part that hadn't it and put back in a light that had it, so two
  places over one part, or two samples before one frame, leave every mask as it was. On 4.7.2 the bit is kept
  (`layers` holds 32 bits), a `Camera3D`'s, a `Decal`'s and a `ReflectionProbe`'s default masks are 0xFFFFF (20
  bits), a light's `light_cull_mask` and `shadow_caster_mask` 0xFFFFFFFF. The query's SubViewports (`world_3d` the
  game camera's world, `transparent_bg`, no MSAA, screen-space AA or TAA) render once (`UPDATE_ONCE`) through a
  `Camera3D` each, orthographic, `keep_aspect` `KEEP_WIDTH`, `cull_mask` layer 32 alone, its `environment` a clear
  background, a white ambient colour (energy 1; for the second, `base_` view, black and 0), reflected light off, a
  linear tonemapper, its `attributes` a new `CameraAttributesPractical` (exposure 1, no auto-exposure, no depth of
  field) and its `compositor` an empty `Compositor`, so the world's own are left out. The game's lights don't reach
  these views: a camera's `cull_mask` culls lights by their `layers` (measured with an `OmniLight3D` whose energy
  changes every frame: `motion` 0). Each camera's frustum is exactly the place: near a point 4 views (from above,
  below, +X, +Z), `NEAR_SIZE` (64) pixels across; along a line 2 views square to it, `LINE_ACROSS` (16) pixels across
  the tube at least, `LINE_SIZE` (128) to `LINE_MAX` (4096) along it; the camera stands `BACK` (0.05 m) before the
  place's face, `near` `BACK` and `far` `BACK` plus its depth. Each view's image is read as RGBA8: a pixel is drawn
  where its alpha is above 0. `motion`: of the pixels drawn now or at the previous sample, the share whose drawn
  state or a channel byte changed by more than 1; `base_r|g|b`: over the pixels of alpha 255, the white-lit view's
  colour less the unlit one's, made linear (`srgb_to_linear`), averaged; `base_change`: its distance from the first
  base colour the query read. Along a line, a drawn pixel's column is its distance along the line (`t` from `from`);
  `reach` the largest `t` within the segment, `length` the steps of the segment (`LINE_BINS` at most, none finer
  than a column) that hold one. `pixels` and `primitives` are always in the value. No value: a place that doesn't
  resolve, `--headless`, no 3D camera, more than `CAP` parts, each said once in `query_errors` as `drawn <id>: ...`.
  `probe.log` notes the time a sample takes on the CPU (the first sample and every tenth). Measured on the factory
  PC, on Forward+ and on the Mobile renderer alike, under a sun, a yellow ambient light and a world exposure of 4
  with auto-exposure: a red box (albedo 0.6, 0.05, 0.05) reads base 0.3186, 0.0040, 0.0040 (its albedo made
  linear), a blue box glowing green reads green 0, an empty place with a wall just outside its box and a sky dome
  around it reads 0 pixels, a still box motion 0 (under a flickering light too), a turning box 0.30, particles 0.36
  to 0.41, a beam from 1 m to 5 m along a line reach 4.96 and length 3.98, a beam 5 cm thick along a 30 m line reach
  20.975 in two plays, a black wall on a layer the camera leaves out drawn 0 and nowhere in the frame, a place of
  1100 parts no value, one CPU particle drawn; 2.5 ms a sample near a point, 5 ms with `base_`, 0.7 ms along a line.
  The Compatibility renderer is not measured.
- **render** (`queries/render.gd`): `RenderingServer.get_rendering_info` read every frame for the frame drawn before
  it, `RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME` and `RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME`, the highest since
  the previous sample kept (null before any frame); `RENDERING_INFO_TEXTURE_MEM_USED` at the sample, in MiB.
  Measured on the factory PC (Vulkan, both renderers): the totals are the 3D scene's draws, its shadow
  passes' and the 2D canvas's summed, so the UI counts (a box 12 primitives and 1 draw call; a label of 13 glyphs and
  a rectangle 28 primitives and 2 draw calls); the texture memory holds the engine's own render targets and default
  textures, 10 to 19 MiB before a game adds anything; a `--headless` play reads 0.
- **world** (`queries/world.gd`): `Engine.time_scale` and `SceneTree.paused` read every frame before the game's
  scripts and once more at the sample, after them; the value is `time_scale`, the lowest `Engine.time_scale` read since the
  previous sample, `flow`, the lowest of the same reads with a read of a paused tree counted as 0, and `paused`, 1
  when a read found the tree paused. A value its
  scripts set in the sample's own frame is in that sample and, while it lasts, in the next.
- **log**: the lines of the play's log (`--log-file`, kept whole as `play.log`) that match, read by the checker up
  to the play's end (`godot.during`): the probe prints `godot.PLAY_END` (`TaskProbe: the play's time is up; what
  follows is the game closing`) into the log before it tells the game it is closing, and a `log` probe and a
  `log_absent` check read the lines before it; a log without the line (the game quit by itself, crashed or was
  stopped) is read whole. A crash is looked for in the whole log (`check.fatal`), as before.

## 4. Plays and inputs

The checker's plays (`check.PLAYS`, `check.DRIVE`): `look`, 20 s idle, 6 screenshots; `drive`, 22 s, 8 screenshots:
`<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with `<Keyboard>/space` 9-9.3 s, `<Keyboard>/a`
13-15 s, `<Keyboard>/w` 15-21 s; on a mobile game the drive is `check.MOBILE_DRIVE`, the same route by touch (a left
thumb's drags from `[0.15, 0.75]`, a tap at `[0.85, 0.75]` at 9 s; `check.own_play`). A task play: 2 screenshots. A boot check: `seconds` idle, 2 screenshots. Samples every 0.5 s (a task play's
`every`, 0.1-1.0). `play_args` apply to every play; a task play's `args` key replaces them, its `scene` key the
`play_scene` (`tasks.place`).

The frame (`task_probe.gd` `_fit_frame`, `_read_frame`; the spec's `size`). The game is always rendered at the
project's own size (`display/window/size/viewport_width` and `viewport_height`), whatever the window is: the root
window's `content_scale_mode` is set to `VIEWPORT`, its `content_scale_size` to the project's size and its
`content_scale_aspect` to `KEEP`, so the root viewport's texture is exactly that size, a portrait frame taller than
the screen is still drawn whole, and the UI is laid out as the game shows it (a `content_scale_size` other than the
project's would lay the 2D canvas out for that other size). The probe sets this again every 16 frames. A frame that
is read (a screenshot, a `screen` sample) is scaled to the spec's `size` (`Image.resize`, Lanczos) when the two
differ: a desktop game of 1920x1080 is rendered at 1920x1080 and read at 960x540; a mobile game's spec is its own
size, so nothing is scaled. Points and rectangles are fractions of the frame, so they are the same either way;
`render` counts what was drawn at the project's size. A spec size of another shape than the project's is a
`query_errors` line, and the frames are stretched to it. Without a `size` the probe changes nothing. Measured on the
factory PC, on `desk.py`'s desktop: screenshots of exactly 960x540 (from a 1920x1080 project) and of exactly
1080x1920 on a 1920x1080 screen.

The play's clock (`task_probe.gd`) is frames at a fixed rate: play time is frames / 30 (the spec's `fps`). The engine
steps the game by 1/30 s a frame because the checker starts it with `--fixed-fps 30` (an engine flag: no script can
set it, and `OS.get_cmdline_args()` doesn't show it), and the probe keeps `Engine.physics_jitter_fix` at 0, without
which the engine lets a frame's step drift by up to half a physics tick. A play started without the flag is said in
`query_errors` (`the game isn't run with --fixed-fps 30 ...`). Under `--fixed-fps` the engine caps no frame rate, so
a play runs as fast as the machine renders; where it must keep real time (a play that measures audio, the spec's
`sound`; a `wait`; a scene change) the probe waits out the rest of each 1/30 s itself (`_wait_for_clock`). The clock
starts when the play's scene is the current scene (after 600 frames without it, a `query_errors` line, and it starts
in the scene that plays), holds during a `wait` and while there is no current scene (a change of scene; for at most
300 frames), and counts on when the game pauses the tree or sets `Engine.time_scale` 0 (the probe's nodes process
always). The queries' `frame` runs in every frame, a wait's too (`speed`, `spin`, `spawns`, `render`, `audio`).

The scene. The checker passes the play's scene to the engine as its scene argument, so the project's main scene
never loads. A spec whose `scene` is not the scene that runs (a play started without that argument) is changed to on
the first frame (`change_scene_to_file`, deferred): the main scene's nodes have then had `_ready`. A `scene` the
project lacks: a `query_errors` line, and the game's own scene plays.

Saved data. Every play starts from clean saved data: `seeds.add_probe` gives the copy a user data folder of its own
(`application/config/use_custom_user_dir`, `custom_user_dir_name` `TaskProbe.<12 hex>`), and the probe empties
`user://` when the game starts, in its `_init`, before any other autoload wakes (`_forget_saves`: only when the name
is exactly `TaskProbe.` and 12 hex digits and the folder is that name's; the engine's own `logs`, `shader_cache` and
`vulkan` folders are kept; anything else keeps its saved data and `probe.log` says why). The checker deletes the
folder before every play too (`godot.Project.play`, `seeds.forget_saves`) and with the copy (section 5).

Plays after others (`check.Side._task_play`, `tasks.chain`). A play's start depends on its own `after` alone. One
that names none always starts clean. One that names some starts on exactly the saves of its chain: the plays it
names and the plays those name, each after its own, in order (a play named twice runs once, where it is first
needed), a failed one counting as run. The side keeps which plays' saves the copy holds now (`Side.saves`: the last
play that started clean and those played after it with `keep_saves`); when they aren't exactly the chain, the chain
is played again from its first play, which starts clean (`_run(again=True)` for one played before: its first result
stays the one its checks read, its files are kept as `<name>_again`, and `replay_note` says in the detail of the
reader's checks when it ended otherwise, timed out otherwise or missed other inputs than the first). A play with
`after` is played with `keep_saves`: the checker deletes nothing before it and its spec holds `"keep_saves": true`,
on which the probe leaves `user://` as it is (`probe.log`: `the saved data is kept: the play runs after the plays
that left it`). When a play's time is up the probe, in this order, has taken the last sample and screenshot, writes
probe.json, closes probe.log, prints the play's end into the game's log (`PLAY_END`), sends
`NOTIFICATION_WM_CLOSE_REQUEST` down the tree and asks the engine to quit: a game that saves when it is closed has
saved for the play after it, and what it prints meanwhile is read by no check (section 3, "log").

A frame has two passes, each raising the probe's `stamp`: before the game's scripts (the autoload, process priority
-2^30: a held player and the pinned objects put back, the inputs) and after them (its child `Late`, priority 2^30:
a held player and the pinned objects put back again, the samples, the screenshots, the end). Physics ticks of a
frame run before both. What is looked up once a pass (the player, the camera, the list of nodes) is kept by the stamp. The frame as drawn (a screenshot, a `screen`
sample) is read at `RenderingServer.frame_post_draw` of the same frame.

Inputs (`inputs.gd`) reach the game as the engine's own input events through `Input.parse_input_event`, and the
probe flushes them at once (`Input.flush_buffered_events`), so the game's `_input`, its Controls and its input
actions take an input in the frame of its time, before its scripts' `_process` of that frame (its `_physics_process`
of that frame has run). Rows of one time go in the order the task wrote them. A row is tried as a widget click
(`click` true and a `widget`), a `tap`, a `drag`, a cursor move, a teleport_to, a teleport, a pin, a damage, a set, a
shot, a scene load, a view turn, a wait, then a key or axis, in that order; a row that is none of them is left out
and not counted in `inputs_sent`, and a row without `t` is sent at 0. An unknown control is a `query_errors` line (`inputs: the keyboard
has no key <x>`, `inputs: the mouse has no control <x>`, `inputs: the gamepad has no control <x>`, `inputs: no
control <path>`, `inputs: no device for <path>`), never a stop. An input that didn't land is a row of `inputs_missed`
(section 5).

- key: `{"t", "key": "<Keyboard>/w", "press": true|false}`. `<Keyboard>/`: an `InputEventKey` with `keycode`,
  `physical_keycode` and `key_label` set (an action bound either way matches), by the key's Input System name as the
  other factories' plays write it (`inputs.gd` `KEYS`: `enter`, `leftShift`, `upArrow`, `numpad1`, ...) or the
  engine's own name (`OS.find_keycode_from_string`: `w`, `space`, `escape`, `f2`, `up`, `shift`), any case; left and
  right modifiers are one key. `<Mouse>/`: `leftButton`, `rightButton`, `middleButton`, `forwardButton`, `backButton`,
  an `InputEventMouseButton` at the cursor. `<Gamepad>/`: `buttonSouth` (the engine's `JOY_BUTTON_A`), `buttonEast`,
  `buttonWest`, `buttonNorth`, `leftShoulder`, `rightShoulder`, `start`, `select`, `leftStickPress`,
  `rightStickPress`, `dpad/up` and the other three, an `InputEventJoypadButton` of device 0. `<Keyboard>/escape` in a
  play whose spec says `touch` (a mobile game's) is the phone's back button instead of the Escape key: a press
  emits the root window's `go_back_requested` and sends `NOTIFICATION_WM_GO_BACK_REQUEST` down the tree, as a phone's
  back button does (so a game that left `application/config/quit_on_go_back` on quits, as on a phone), then the key
  `KEY_BACK`; a release is the key's release.
- axis: `{"t", "key": "<Mouse>/delta/x", "axis": 4.0}`. `<Mouse>/delta/x|y`: one `InputEventMouseMotion` whose
  `relative` is that many pixels (y down, the engine's own). `<Mouse>/scroll/y|x`: that many notches of the wheel
  (rounded, 1 to 20), each a press and a release of `MOUSE_BUTTON_WHEEL_UP` (a positive value) or `WHEEL_DOWN`
  (`WHEEL_RIGHT`, `WHEEL_LEFT`). `<Gamepad>/leftStick/x|y`, `rightStick/x|y`, `leftTrigger`, `rightTrigger`: an
  `InputEventJoypadMotion`, -1 to 1, which keeps its value until set again; a stick's y is up-positive in a play, as
  the other factories write it (the engine's `JOY_AXIS_LEFT_Y` gets the value negated).
- widget click: `{"t", "widget": "RetryButton", "click": true}`: the first Control in tree order that is visible (the
  `widgets` state), of some size, not disabled and not ignoring the mouse, whose name (a wildcard) or class matches.
  The mouse moves to its centre, the left button goes down, and up in the next frame: real events, so a Control drawn
  over it takes them instead. For a `BaseButton` the probe listens for its `pressed` signal: when it hasn't fired two
  frames after the release, the click is a row of `inputs_missed`. `probe.log` names the widget clicked and its class
  (`clicked PushButton (Button)`).
- cursor: `{"t", "cursor": [fx, fy]}` (fractions of the frame, clamped to 0-1): an `InputEventMouseMotion` to that
  point (the cursor starts at the frame's centre); a following `<Mouse>/leftButton` press and release clicks there.
  An event's position is the point in the frame's own units through the root window's `get_final_transform()`, which
  holds whatever stretches the frame to the window (`UiScan.to_window`).
- move: `{"t", "move": [dx, dy], "over": s}`: without `over` one `InputEventMouseMotion` whose `relative` is
  [dx, dy] in the frame's pixels, through the root window's `get_final_transform()` (`basis_xform`) so the game's
  viewport gives it back in the frame's pixels; with `over`, in every frame from `t` the part due by then
  (`(elapsed - sent) / over` of it, `sent` the clock when the row was sent, less what was sent), until all of it was. The event's position is the cursor's,
  which doesn't move. Played headless at 960x540, a move of [300, 0] over 1 s reads 300 summed in the game's `_input`
  over 30 events, 150 half way.
- tap, drag: `{"t": 2.0, "tap": [0.5, 0.25], "finger": 1, "hold": 0.5}`, `{"t": 3.0, "drag": [{"widget":
  "MoveStick"}, [0.2, 0.6]], "finger": 0, "over": 0.3, "hold": 2.0}` (the checker writes `finger`, 0 when unset;
  `hold` and `over` only when set; `_touch`, `_move_touch`). The spots are resolved when the finger goes down: a
  point `[fx, fy]` (fractions of the frame, y down), or `{"widget": name}`, the centre of the first visible Control
  of some size whose name (a wildcard) matches, else the first whose class does (`UiScan.named`). The finger goes down with an `InputEventScreenTouch` (`index` the finger), moves with
  `InputEventScreenDrag` events (a drag's path walked evenly over `over` seconds, at once without it), and lifts once
  its path and its `hold` are over, never in the frame it went down. Fingers 0 to 9 may be down together. With
  `input_devices/pointing/emulate_mouse_from_touch` on (the engine's default, and a mobile game's setting) the engine
  makes mouse events of the first finger down alone, so a `Button` node presses for that finger only; a Control that
  reads `InputEventScreenTouch` itself (`_gui_input`) takes any finger. At the play's end every finger still down is
  lifted. A miss (a finger outside 0-9, a widget not on screen, a finger still down, a drag without 2 to 16 spots) is one
  `query_errors` line, `inputs: the tap at 2.00 s missed: no visible widget matches 'FireButton'`, and a row of
  `inputs_missed`, and nothing is sent; `probe.log` names what each finger went down on and where it lifted.
- teleport: `{"t", "teleport": [x, y, z], "yaw": deg, "hold": s}`; teleport_to: `{"t", "teleport_to": <object select>,
  "distance": 2.0, "offset": [x, y, z], "face": <Point>, "hold": s}`. The probe sets the player's `global_position`
  (a 2D player's x and y), with no free-spot search and no snap to the ground, tells the physics server for a rigid
  body, resets the node's physics interpolation and stills its velocity (`_place`, `_still`). `yaw` turns a 3D
  player (the checker writes 0 when unset). teleport_to takes the match nearest the player, the player and the nodes
  below it left out; the spot is `distance` from the target along the level line toward the player (when the player
  is right above it, on the side the target's back is to, its +Z; a 2D target: along the line toward the player in
  the plane), plus `offset`; it faces `face`, else the target (it keeps its yaw when what it faces is within a
  centimetre on the level; a 2D player isn't turned). `hold`: for that many seconds of play time the player is put
  back at the spot and stilled before the game's scripts and again after them, through waits.
  `probe.log` says where each went (`teleported next to <name>: asked (...) yaw ..., now at (...)`, `teleport_to
  skipped (no object matches)`).
- pin: `{"t", "pin": <object select>, "hold": s, "offset": [x, y, z], "front": m | "at": <Point>}` (the checker
  writes `offset`, 0 when unset; `front` and `at` only when set; `_pin`). The target is the match nearest the player
  that has a place, the player and the nodes below it left out (`_nearest`: of two as near, the first in tree order;
  without a player, the first match). With `front`: the player's place plus `front` m along the player's forward
  (`Find.forward`: its -Z, flattened to the level; a 2D node's +X) plus `offset`, at the target's own y plus the
  offset's y (a 2D target: the whole point); with `at`: the point plus `offset`; with neither: where it is. Set
  there, a 3D target is turned to face the player (its yaw alone; kept when the player is within a centimetre on
  the level). It is placed and stilled as a teleport places the player (`_place`, `_still`) and, for `hold` seconds
  of play time, put back and stilled before the game's scripts and again after them, through waits (`hold`, with
  the held player); its rotation stays free. A second pin of the same node takes the first one's place. Misses: no
  object with a place matches, `front` without a player, an `at` that doesn't resolve.
- damage: `{"t", "damage": points, "to": <object select>, "from": <object select>}` (`from` only when set;
  `_strike`). The target is the match of `to` nearest the player; the method is `take_damage` of the target, else
  of the first node below it that has one (`_hurt`), and must take the two arguments (`_takes_two`, from
  `Object.get_method_list`: at most two arguments without a default, and at least two in all). The source is the
  match of `from` nearest the target (the target and the nodes below it left out); without `from`, the player, or, when the target is the player, a node above or below
  it, or the play has no player, the node with a `take_damage` nearest the target that is neither the target nor
  the player (`_other_hurt`; `null` when there is none). The call is `take_damage(amount, source)`, made with the
  inputs, before the game's scripts of the frame; what it returns is summed by the node whose method it is
  (`damage_taken`); the node's id and the names for `probe.log` are taken before the call, since the hit may free
  it. Misses: no match of `to`, no method, a method of another shape, no match of `from`.
- set: `{"t", "set": "<path>", "on": <object select>, "value": v, "all": bool}` (`_write`, `Find.write`): on the
  match nearest the player, or on every match with `all`. The path is resolved as a `prop:` path is (a class first:
  the node itself when it is of it, else the first node below it that is; else on the node itself), without an
  index. The last member is written with `Object.set` (its setter runs), a dictionary's entry by its key, or a
  vector's, a colour's or a transform's part, which is written back through the property that holds it. The value
  takes the type the property holds (`Find._fit`): a number or a boolean onto a boolean, an integer (rounded) or a
  float, a string onto a string or a StringName; a property that holds `null` takes any of them; anything else
  takes nothing. After `Object.set` the property is read back: one that reads as before, when another value was
  written, took nothing (a read-only one). Misses: no match, or no matched object the write lands on.
- shot: `{"t", "shot": "<name>"}`: `shot_<name>.png` of that frame. scene: `{"t", "scene": "res://..."}`:
  `change_scene_to_file`; a scene the project lacks is a `query_errors` line and a miss. view: `{"t", "view": [pitch,
  yaw]}`: a 3D player's yaw and the `Camera3D`'s rotation set once (pitch clamped to +-89).
- wait: `{"t", "wait": s}`: the play's clock holds while the game runs paced to real time, until `wait` seconds of
  both real and game time have passed; the inputs after it wait for its end. The frame it starts in takes its sample
  first.

## 5. Files the probe and the checker exchange

The checker hands the game one play spec; the game writes `probe.json` (`godot-probe/1`), `probe.log` and the
screenshots. The checker's files of a copy are under `<copy>/Logs/TaskProbe/` (`godot.LOGS`; it holds a `.gdignore`,
so the engine imports nothing there), each made fresh before its job.

**The play spec** (`<copy>/Logs/TaskProbe/play_spec.json`, written by `godot.Project.play`, read by `task_probe.gd`
`_init`). A task play with three queries as `probes.plan` makes them:

```json
{"format": "godot-probe-play/1", "out": "C:/tc/38e8bcd7/ff49e5194fe4/Logs/TaskProbe/play", "size": [960, 540],
 "seconds": 8, "shots": 2, "every": 0.5, "scene": "res://scenes/Yard.tscn", "sound": false, "player": null,
 "inputs": [{"t": 2.0, "wait": 2.0}, {"t": 4.0, "key": "<Keyboard>/space", "press": true},
            {"t": 4.3, "key": "<Keyboard>/space", "press": false},
            {"t": 5.0, "tap": {"widget": "FireButton"}, "finger": 0}],
 "queries": {"format": "game-probe-queries/1", "every": 0.5, "queries": [
   {"id": "q0515f1b44e", "kind": "ui", "select": {"kind": "text", "rect": [0.0, 0.0, 0.4, 0.09]},
    "fields": ["h", "text", "w", "x", "y"]},
   {"id": "q2af780091d", "kind": "objects", "select": {"name": "Lamp_3"}, "fields": ["prop:lit"]},
   {"id": "qe2fd69dd75", "kind": "widgets", "select": {"component": "ProgressBar", "name": "FuelBar"},
    "fields": ["percent"]}]}}
```

- What varies: `out` (the copy's), `size` (the size frames are read at: 960x540, or a mobile game's phone size,
  `[1080, 1920]` or `[1920, 1080]`: the copy has a `Platform.json`, read by `godot.Project.mobile` through the
  validator's `read_platform`), `touch` (true, in a mobile game's spec only), `keep_saves` (true, and only there, for a
  task play that names `after`: section 4), the play's `seconds`,
  `shots`, `every`, `scene` (null: the project's main scene), the task's `player` select (null: the probe finds the
  player, section 1), its `inputs` with the checker's defaults filled in (`tasks.inputs`), `sound` (true when a query
  is `audio`) and the queries.
- The probe reads `out` (default: `user://TaskProbe`), `size` (two numbers of 16 or more; without it the probe leaves the frame as the game has it), `touch` (the play is a phone's: `<Keyboard>/escape` is its back button), `keep_saves` (true: `user://` is left as it is), `seconds` (clamped to 1-600; default 20), `every` (0.1-1.0; 0.5), `shots` (0-64; 4),
  `fps` (10-240; 30: the rate the clock counts frames at, the one the command line's `--fixed-fps` gives), `scene`,
  `sound`, `player` (its own `player` key ignored), `inputs` and `queries.queries`; the queries' `every` rides along
  unread. A play without queries has an empty list.
- A query holds `id`, `kind`, its kind's keys and `fields`: `objects`, `components`, `widgets`, `ui` take `select` and
  `fields`; `camera`, `render` and `world` `fields`; `spawns` `component`; `screen` `rect`; `audio` `select`
  (`probes.needs`).
  `fields` is the sorted union of what the play's probes read of it (`[]` for a count). Its id is `"q"` and the first
  10 hex digits of the sha256 of `json.dumps(<the query without its id and fields>, sort_keys=True)`
  (`probes.query_id`), so probes reading other fields of one selection share it; the queries are merged per play and
  sorted by id (`probes.plan`). The probe takes any id (the probe tests name theirs) and at most 256 queries.

**probe.json** (written by the probe into `out` when the play ends, UTF-8 without a BOM, compact; read by
`godot.Project.play`, then `probes.py`). The start of a play's file, spaced out here:

```json
{"format": "godot-probe/1", "ended": "time", "seconds": 8.5, "scene": "res://scenes/Yard.tscn",
 "player": "Keeper", "inputs_sent": 4, "inputs_missed": [], "screenshots": ["shot_00.png", "shot_01.png"],
 "track": [[0.03333333333333333, 3.8, 0.08, -14.0], [0.5, 3.8, 0.08, -14.0]],
 "camera": [[0.03333333333333333, 10.3, 3.28, -14.0, -10.46, 90.0, 55.0], [0.5, 10.3, 3.28, -14.0, -10.46, 90.0, 55.0]],
 "measures": {
  "q0515f1b44e": [{"t": 0.03333333333333333, "rows": [{"name": "ScoreText", "class": "Label", "source": "control",
                   "kind": "text", "h": 0.0648, "text": "SCORE 100", "w": 0.2708, "x": 0.0208, "y": 0.0278}]}],
  "q2af780091d": [{"t": 0.03333333333333333, "rows": [{"name": "Lamp_3", "class": "Lamp", "prop:lit": 1.0}]}],
  "qe2fd69dd75": [{"t": 0.03333333333333333, "rows": [{"name": "FuelBar", "class": "ProgressBar",
                   "percent": 0.15}]}]}}
```

- `ended`: `time` (the clock passed its seconds + 0.5) or `shutdown` (the game quit first: the probe's node left the
  tree). `seconds`: the play time at the end, its seconds + 0.5 plus the frames (at most 5) a last sample or
  screenshot waits for its frame. `scene`: the current scene's path at the end; `player`: the player's name then, or
  null.
- `screenshots`: the PNG files written, in the order taken, each exactly the spec's `size`, of the frame as
  displayed, UI included, without alpha (RGB8): `shot_00.png` and on at the middle of each of `shots` equal parts of
  the play, and `shot_<name>.png` for a `shot` input. Only files written are listed: a play that draws no frame
  (`--headless`) lists none.
- `inputs_sent`: how many input rows were sent. `inputs_missed` (always there): a row `{"t", "kind", "target", "why"}`
  for each input that didn't land: `tap` and `drag` (a spot whose widget isn't on screen, a finger still down, a bad
  finger or path), `click` (no visible control that takes a click matches, or a button that didn't press), `shot` (a
  bad name), `scene` (a scene the project lacks), `pin`, `damage` and `set` (a stage nothing took; `target` is the
  select as JSON, the node's name once one matched, or a set's path).
- Samples fall on frames: the first at 1/30 s (the clock's first frame), then every `every` s, on the frame that
  reaches it. Every sample adds a `track` row, `[t, x, y, z]` (the player's place) or `[t]` while there is no player
  (no value there for the checker), and a `camera` row `[t, x, y, z, pitch, yaw, fov]` when there is a player camera
  (a sample without one has no value for the camera's fields).
- `measures` (only when the spec has queries): each query's id and its samples, one per sample time, each with its `t`:
  `rows` for `objects`, `components`, `widgets` and `ui` (at most 200; when more matched, also `total`, how many, and
  `full`, an entry for every field asked for, in the order asked: its `n`, `nonzero`, `sum`, `min` and `max` over
  every match's number, `n` 0 and `min` and `max` null for a field no match has a number for), or `value`, an object
  or null, for the others. A `screen` sample whose frame never came has a null value. An `objects` or `components`
  sample whose select waits for a part's first drawing (`has.lit`) has empty `rows` and `"pending": true`: no value
  for any field, a `count` too.
- `query_errors` (only when there was one): each line once, at most 50, then `<n> more in probe.log`. A query's own:
  `<kind> <id>: <message>` (`components q3c1d2e4f5a: no component type Lantren`, `objects <id>: no field glow`,
  `components <id>: the select names no component and no effect`, `widgets <id>: the text regex ( doesn't compile`,
  `ui <id>: no element kind <k> (text, box, image)`, `spawns <id>: no component named`). The loop's own: `the queries
  are not a JSON object`, `queries format '<f>' is not game-probe-queries/1`, `the queries have no queries array`, `a
  query is not an object`, `a query has a missing or repeated id '<id>'`, `more than 256 queries: '<id>' and later
  ones dropped`, `query '<id>': unknown kind '<kind>' (null values)` (such a query is sampled with a null `value`);
  and `the play's scene <scene> isn't in the project: the game's own main scene is played`, `the play's scene <scene>
  didn't become the current scene: playing <path>`, `the scene <path> isn't in the project: no load`, `the game isn't
  run with --fixed-fps <n> ...`, `the frame asked for is <W>x<H> and the project's is <w>x<h>, of another shape:
  frames are stretched to fit`, `the play's last frames weren't drawn ...: <n> screenshot(s) and <n> sample(s) are without their frame`,
  `a shot named '<name>' isn't taken: ...`, `a screenshot couldn't be written: <file>`, `inputs: ...`.
- Numbers are written so that each reads back as the same double (`JSON.stringify` with full precision); NaN and
  infinities are written null. Keys keep the order above.
- GDScript has no exceptions: a script error inside the probe stops that one call and the engine writes it into the
  game's log as `SCRIPT ERROR` with a path under `res://addons/task_probe/`. The probe's code checks every value it
  reads for that reason; such a line in `play.log` is the probe's bug, never the game's.

**probe.log** (beside it in `out`): the probe's own lines, each with the play time and the real time since the game
started: the start, the clock's start, waits, teleports, holds, pins, staged hits and what each returned, sets, clicks, cursor moves, touches going down and lifting (where, in the window's own units),
misses (`missed: ...`), errors (`error: ...`), saved data kept, and the end. The game's own log is `play.log`. One of
the probe tests' plays:

```
0.00 [0.2 s] play: 5.0 s, every 0.50 s, 0 shot(s), 2 query(ies), scene (the game's own), frame 960x540
0.00 [0.2 s] the play's clock starts in res://scenes/Main.tscn
0.50 [0.2 s] tap: finger 0 goes down on TapButton (Button)
0.53 [0.2 s] tap: finger 0 lifts at pixel (1710, 920) after 0.03 s
3.80 [0.2 s] missed: tap Nope at 3.80 s: no visible widget matches 'Nope'
3.80 [0.2 s] error: inputs: the tap at 3.80 s missed: no visible widget matches 'Nope'
5.50 [0.2 s] the play ended: time
```

**The play's command line** (`godot.Project.play`; one command, in the copy):

```
python tools\task_check\desk.py <godot console exe> --path <copy> --log-file <copy>\Logs\TaskProbe\play.log
    --fixed-fps 30 --disable-vsync --audio-driver Dummy [<scene>] -- -taskProbe <copy>\Logs\TaskProbe\play_spec.json
    <play args...>
```

It runs with the checker's own Python and the machine's pinned Godot (`ggfroot.godot_exe(console=True)`), through
`godot-heavy.ps1 -Label "task-check play <commit[:12]>" -Gpu` when the machine has the limiter (a GPU slot), with a
timeout of `--timeout` plus the play's waits, counted from when the job starts. The engine's own flags come before
`--`: `--fixed-fps 30` (the clock's step, section 4), `--disable-vsync` (no wait for the screen), `--audio-driver
Dummy` (no play is heard; the mix is still measured), `<scene>` (the play's scene, when it has one). What follows
`--` is the game's: the probe's `-taskProbe <spec>` (any case), then the task's play arguments. The checker never
passes `--rendering-method` or a window size: a game is drawn with the renderer its project names, at its project's
own size. `desk.py` starts the game on a Windows desktop of its own (`WinSta0\TaskProbe`, made when it isn't there),
in a job object that kills it and everything it started when `desk.py` goes, and exits with the game's exit code: 0
when the play ended (once probe.json, the screenshots and probe.log are written and closed, the probe asks the engine
to quit with code 0), 2 when the play spec can't be read (missing, not a JSON object, another `format`: `TaskProbe:
the play spec <file> couldn't be read: <why>` in `play.log`, and the game quits at once). A game that quits by itself
first ends the play there with its own exit code (`ended` `shutdown`). What the play wrote into `out` is read back,
then the folder deleted; the checker keeps those files and the play's spec as the play's evidence, since only the
spec says which query id is which select.

**The build** (`godot.Project.build`; two commands, in the copy):

```
<godot console exe> --headless --path <copy> --log-file <copy>\Logs\TaskProbe\build.log --import
<godot console exe> --headless --path <copy> --log-file <copy>\Logs\TaskProbe\scripts.log
    --script <copy>\Logs\TaskProbe\scripts.gd
```

The import writes `.godot/` (emptied first); the scripts pass loads every `.gd` file of the project in the folders
the engine reads, since the import alone parses only the scripts it opens. The build passed when both exit 0 and
neither log has a script error (`godot.SCRIPT_ERROR`, `LOAD_ERROR`: `SCRIPT ERROR`, `Parse Error`, `Failed to load
script`; the engine exits 0 from an import that logged one). One that fails with no word about the game is tried
once more; stopped again, it is the machine's error and the task reads ERROR, never a verdict (`check.Side.build`).

**The scratch copy** (`seeds.py`): `<scratch>/<run tag>/<commit[:12]>`, where `--scratch` defaults to the machine
root's `.task-check` when it is on the repo's drive, else a `.task-check` beside the repo's parent folder
(`cli.default_scratch`; never inside the repo).

- The commit as committed, read from the repo's git objects and its local Git LFS store (`seeds.materialize`): each LFS
  file a hardlink of its object on the repo's volume, else a copy. Never written: `Tasks/`, `History/`, `Dataset/`,
  `Dataset.zip` at the root, in any case.
- The probe added (`seeds.add_probe`): the addon's folder as `addons/task_probe/`, and three lines in the copy's
  `project.godot`: `TaskProbe="*res://addons/task_probe/task_probe.gd"` first in `[autoload]` (so its `_ready` and
  its frame come before the game's own autoloads'), and `config/use_custom_user_dir=true` with
  `config/custom_user_dir_name="TaskProbe.<the first 12 hex digits of the sha256 of the copy's folder, lower-cased>"`
  in `[application]` (`seeds.saves_company`). The engine reads a section written twice as one, a later line of a
  setting winning and the autoloads loading in the order they first appear, so every line of the game's that sets one
  of those three settings, in any section or form (a quoted key, a second `[autoload]` or `[application]`), is taken
  out first, and an autoload the game sets before every section (`autoload/<name>=...`, which the engine would load
  first) moves into that `[autoload]` right after the probe's line, with its value and in its order
  (`seeds.with_probe`): the engine then reads the probe's values and loads the probe first, and every autoload of the
  game's still loads. No shape of `project.godot` is refused; `seeds.settings_errors` checks the result as the engine
  reads it, and what it finds (`seeds.UnsafeSettings`) is a bug of the edit.
- Refused (`seeds.WrongEngine`, the task INVALID) when `project.godot`'s `config/features` doesn't name 4.7.
- Deleted with what its plays left outside it (`seeds.forget_saves`, names of the form `TaskProbe.<12 hex>` alone):
  the copy's user data folder, `%APPDATA%\TaskProbe.<hash>`.

**Results**: `task-check/1` (`<out>/<task>.json`), `task-check-progress/1` (`progress.json`) and `task-try/1`
(`check.check_task`, `cli.write_progress`, `trial.try_task`).

A crash in a play: the game's log matches `godot.FATAL`. A script error the game survives is not a crash:
`log_absent` checks for those.

## 6. The probe addon (`tools/task_check/task_probe/` -> `addons/task_probe/`)

GDScript, no editor plugin, no `class_name` of its own (a game's names stay the game's): each script reaches the
others by `preload`. The checker copies the folder into the copy as it is (section 5); it holds no `.uid` and no
`.import` files, which the engine makes in the copy. A game's export presets leave `addons/task_probe/*` out. The
autoload does nothing unless the game's user arguments have `-taskProbe`: its `_init` returns at once and its `_ready`
stops its processing.

| File | What it holds |
|---|---|
| `task_probe.gd` | the autoload: the spec, the frame, the play loop's first half (before the game's scripts), the samples, the screenshots, the end |
| `probe_late.gd` | the loop's late half, a child node that runs after the game's scripts |
| `inputs.gd` | the scripted inputs, the stages of a contact among them |
| `find.gd` | selects, points, classes, `prop:` paths and the readers several kinds share |
| `ui_scan.gd` | the UI as widgets, ui, a widget click and a touch read it |
| `motion.gd` | speed and spin between samples |
| `stops.gd` | an object's short stops between samples (`frozen`) |
| `changes.gd` | an object's parts against its first sample (`changed`, `bounds_change`, `pose_change`) and their `spread` |
| `query.gd` | a query's base and the rows of a sample |
| `queries/objects.gd` | `objects` |
| `queries/components.gd` | `components` |
| `queries/camera.gd` | `camera` |
| `queries/widgets.gd` | `widgets` |
| `queries/ui.gd` | `ui` |
| `queries/screen.gd` | `screen` |
| `queries/spawns.gd` | `spawns` |
| `queries/audio.gd` | `audio` |
| `queries/pieces.gd` | `pieces` |
| `queries/ground.gd` | `ground` |
| `queries/drawn.gd` | `drawn` |
| `queries/render.gd` | `render` |
| `queries/world.gd` | `world` |

- Each query kind is one script, `queries/<kind>.gd`, extending `query.gd` and loaded by its kind's name when a play
  starts, so a new kind touches no other file.
- A query never stops the play: anything unknown (a class, a member, a widget, a kind) gives empty rows or null values
  and a `query_errors` line.
- `probe_tests/` (beside the addon; never copied into a game): the probe's regression run on the real engine.
  `run.py <work folder>` copies its small game (`probe_tests/project/`), adds the addon as the checker does, imports
  it and runs each play (`plays/<name>.json`: section 5's spec without `format`, `out` and `size`, each query with an
  id of its own), checks every value (`tests.py`) and prints a pass/fail table (`probe_tests/README.md`). Headless
  it covers everything but pixels; `--rendered` runs the plays that need a drawn frame, at a desktop game's size and
  at a portrait phone's.
