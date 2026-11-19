---
name: godot-write-tasks
description: 'How to write the tasks a Godot game ships with (Tasks/ on the repo''s orphan tasks branch, never on main, one GameTask JSON per task, 5 to about 10 per game) : the tasks branch and its worktree, the one bar every task meets (a long thread of multiple edits from the game''s real history: at least 4 hard, the rest medium, never easy or a single fix), the four kinds as where a thread comes from, picking seed.commit and seed.reference, observation-only briefs, play_scene and play_args, milestones and deterministic probe checks (pass/fail never by pixels; judges only for asked looks; one required probe per issue), validating, the no-op and oracle check on your own machine and its failures, every rule with its reason, limits, and what keeps a task gradable and unleaked. Use when a Godot game session writes, moves, checks or reviews tasks, or reads a task check''s result, and before calling a game complete.'
---

# Writing a game's tasks (Godot)

A game is complete when its repo's orphan `tasks` branch has `Tasks/`: tasks an LLM agent can be given on this game,
fair, checkable and not leaked. One file per task, `Tasks/<game>-<kind>-<slug>.json` (`kind`: `fix`, `corr`, `feat`,
`change`; the whole name in lower-case letters, digits and `-`, at most 63 characters), in the task format `GameTask`
([docs/schemas/game-task.schema.json](../../docs/schemas/game-task.schema.json), `game-task/1`; its `"engine"` is
`"godot-4.7"`), with `"name"` equal to the file stem (run and grade ids depend on it; never rename a
shipped task). At least 5 and up to about 10 per game, every one a long thread of multiple edits (section 1): a game
with fewer than 5 tasks is rejected, and a short task never fills the count: a game whose history does not hold 5 long
threads is not ready. The tasks branch is the single source: tasks are loaded as `Tasks/*.json` from the
repos' tasks branches, and the packager ships them in the dataset split into the agent's and the grader's halves
(docs/game-format.md). Write tasks with this skill and the godot-game-factory tools only, never
with another skill (AGENTS.md, "Only these skills"); for a mobile game read the godot-mobile-game skill's "Tasks on a
mobile game" with it. `<root>` and `<GGF_ROOT>` below are the machine root (`%GGF_ROOT%`); every `docs/...` and
`tools/...` path named here is in the godot-game-factory folder under it, `<GGF_ROOT>/godot-game-factory` (the links
lead there too: they work in that folder, not in an installed copy of this skill).

## 0. Where tasks live: the orphan `tasks` branch

**Task work never goes into the game's history.** Tasks live on a branch `tasks` of the game repo that shares no
history with main, checked out as a git worktree **outside** the game folder (`<root>/tasks/<slug>`). The branch holds
`Tasks/<game>-<kind>-<slug>.json`, a short `README.md` (what the branch is), and optionally `tasks-workflow.jsonl`
(one row per task written, `op:"task.write"`, `target:"Tasks/<name>.json"`; never in main's `workflow.jsonl`). Its
rows have the form of main's rows (docs/schemas/workflow-row.schema.json), with what is the task's own in `params`;
no tool reads the file.

Create the worktree once. When the branch does not exist yet (on origin either):

```bash
git -C <root>/games/<slug> worktree add --orphan -b tasks <root>/tasks/<slug>
```

With an older git that lacks `worktree add --orphan`:

```bash
git -C <root>/games/<slug> worktree add --detach <root>/tasks/<slug>
git -C <root>/tasks/<slug> checkout --orphan tasks
git -C <root>/tasks/<slug> rm -rf .
```

When the branch already exists on origin (another machine or session made it):

```bash
git -C <root>/games/<slug> fetch origin tasks
git -C <root>/games/<slug> worktree add <root>/tasks/<slug> tasks    # creates local tasks tracking origin/tasks
```

Then write the tasks in `<root>/tasks/<slug>/Tasks/`, commit there (`git -C <root>/tasks/<slug> commit`) and push
when told: `git -C <root>/tasks/<slug> push -u origin tasks` the first time, `git push` after. In that worktree on
Windows the word `tasks` also names the folder `Tasks/` (the disk ignores case), and git calls it ambiguous: write
`git log tasks --`.

- Never add `Tasks/` (or any task file) to main, never merge or cherry-pick between `tasks` and main, never point
  main's code, docs, README or `workflow.jsonl` at the tasks branch. The validator fails a repo whose main tracks
  anything under `Tasks/` or whose `tasks` branch shares history with main.
- The recording hooks and the creation replay ignore commits on the `tasks` branch, and the delivered history
  leaves it out, so committing tasks costs the game's record nothing.
- Seeds (`seed.commit`, `seed.reference`) are commits of main's history (ancestors of main's head) or of the task's
  own start branch `starts/<task name>` (section 2, "Starts on the engine"); pick them in the game checkout
  (`git -C <root>/games/<slug> log`), never on the tasks branch.

Check every task after committing it on the tasks branch:
`python <GGF_ROOT>/godot-game-factory/tools/validate-game.py <GGF_ROOT>/games/<slug>` (it reads the committed `tasks`
branch, else `origin/tasks`, through git: schema, the format's extra rules, name = file name, seed commits on main or
the task's `starts/<name>` branch and on Godot 4.7, the branch an orphan, nothing under `Tasks/` on main). It
prints one line per finding (`x` an error, `!` a warning, `-` a note): its `repo: Tasks` lines are about your tasks
(a task with nothing wrong has no line of its own: the note `N task(s) on tasks` counts those it read and checked);
its other `repo:` lines (the README, `.import` and `.uid` files, LFS, the manifest), its `contract`, `sound` and
`mobile` lines and its `dataset` and `layout` lines are about the game repo, not a task: they never change a task check's verdict, but a game is delivered only when the
validator says VALID. Commit tasks as you go, like any work (godot-commit-always skill), but on the tasks branch only.
Then run the task check on all of them in one background run (section 5, `tools/task-check.py`): only VALID tasks
ship, so fix or remove every INVALID one before the game is packaged.

## 1. The bar: long threads of multiple edits, nothing else

**The only tasks that meet our requirements are long threads of multiple edits.** A long task keeps one clean run of
a strong agent working about 25 minutes or more. That length is a guide, not a requirement: what counts is that a
strong agent can't solve it easily. You judge this in the session from the thread itself (section 6); we measure it
on every submitted task. A task is a stretch of the game's real history where its own sessions needed many commits,
several attempts or several rounds of directions, touching many files across several systems, before the outcome
held. Strong agents finish a single fix, one cause in one place, in minutes, however long it took in the game; such a
task is worthless to us and never ships, not even as an "easy" one. A task is `"difficulty": "hard"`, with
the tag `long-thread`. A game needs at least 4 hard tasks; the others may be medium (what a task that names no
difficulty is), none easier. Four is the floor, not a target: pick threads that make every task hard, and call a task
medium only when its thread is.

A thread qualifies only when all of these hold (the validator enforces the numbers, section 6):

1. **Many edits.** From `seed.commit` to `seed.reference`, at least 4 commits change the game itself (`scenes/`,
   `game/`, `assets/`, `project.godot` and the game's own addons under `addons/`; not the AutoPlay drop-in, `steps/`,
   `Scripts/`, `Docs/`, `Brief/`, `Dataset/`, `export_presets.cfg`, `workflow.jsonl` or the manifests), and the
   reference changes at least 5 game files against the start (a generator step under `steps/` is the creation's
   record and a `.import` or `.uid` follows its file: neither is a game file), with at least 100 code lines added
   plus removed (any code file of the repo: GDScript, shaders (`.gdshader`, `.gdshaderinc`), scripts such as `.ps1`
   or `.py`, generator steps included; not under `Dataset/`, `Docs/` or a `third_party/` folder, so store packs' own
   code doesn't count). Status, docs and `workflow.jsonl` commits don't count. Assets and binary files don't count as
   code lines (scenes and resources neither, even though they are text).
2. **Several systems.** The change spans at least two of: config (`project.godot`), an addon (anything under
   `addons/`), GDScript code (`.gd`), scenes (`.tscn`, `.scn`), materials (shaders `.gdshader` and `.gdshaderinc`,
   `.material`, and textures: `.png`, `.jpg`, `.svg`, `.webp`, `.tga`, `.bmp`, `.exr`, `.hdr`, `.dds`, `.ktx`), data
   (`.tres`, `.res`, `.json`, `.csv`, `.txt`, `.cfg`), other assets (anything else: models, sounds, fonts). The
   validator counts them over the game files of item 1 (so a generator step is no system), by path and extension. A
   long thread confined to one function is a short task in disguise.
3. **Several outcomes.** At least 3 required outcome probes, one per issue the thread settled, so partial work earns
   partial credit (a compound ticket). A required probe of weight 0 is a guard, not an outcome: it gates, and isn't
   counted. Neither is a `seen` probe: a model reads it, as a judge's pictures. A thread that settled only one observable thing is rarely long enough.
4. **The first attempt didn't hold, or the cause is far from the symptom.** The thread had a fix that was undone,
   complained about again ("still too low") or broke something else; or the symptom shows in one system and the cause
   sits in another (a HUD symptom from a tuning resource, a camera symptom from collision layers, a fault only in the
   exported player, an intermittent or timing bug, a regression from an earlier change).
5. **Checkable by the grader.** Every required outcome is measurable in the grader's own plays: a scenario
   (`play_scene` and `play_args` at the seed) that triggers the moment, or a task play whose scripted inputs reach it
   (keys, mouse buttons, mouse movement and the cursor, clicks on a control, teleports, and touches: `tap` and
   `drag`, docs/task-probes.md section 1.3). The plays send Godot input events: a game that reads its input another
   way takes none of them. A mobile game (its root has a `Platform.json`) is played at the phone's size and driven by
   touch: the godot-mobile-game skill, "Tasks on a mobile game". A thread no probe can measure is
   not a task. One issue of a compound thread that no probe can measure fairly stays in the brief and gets a
   required `looks_as_asked` rubric item (section 5), never one of the required probes.

**Never make a task easier (permanent).** After a task is first written (committed on the tasks branch), these are
banned if they lower the bar:
widening a threshold or window, making a required probe optional, removing a probe, removing a requirement from the
brief or narrowing what it asks. A plainly broken probe may be fixed only so that it asks at least as much as the
brief. Otherwise drop the whole task and say so; fewer tasks is an acceptable result.

The four kinds say where the thread comes from; each is a long thread, never one commit. The kind is `seed.kind`,
and the file's name carries its short form: `fix` for `bug_fix`, `corr` for `correction`, `feat` for `feature`,
`change` for `change`:

| kind | the thread | `seed.commit` | `seed.reference` |
|---|---|---|---|
| `bug_fix` | a bug the game's sessions fixed over several attempts or commits | the parent of the first attempt | the final fix that held |
| `correction` | a person's direction (`user.direction` rows) that took several rounds or follow-ups to satisfy | the last commit before the first direction | the commit that answered the last round |
| `feature` | a mechanic the game itself built over a span of commits (code, scenes, input, HUD) | the parent of the span's first commit | the span's last commit, once it played |
| `change` | a look or content pass built over a span (lighting plus environment plus materials, a camera rework, a HUD restyle) | the parent of the span's first commit | the span's last commit |

`seed.reference` is always set: a task without the game's own accepted end of the thread is not a task. Merge, don't
split: a chain whose first fix didn't hold is one task, not two; a direction with several issues fixed in several
commits is one compound task with a probe per issue; neighbouring fixes of the same system in the same stretch belong
together. A separate thread in the same stretch (another system, other issues) is its own task, even over the same
commits (section 2), when its own commits meet the floors; threads that are each too short on their own are merged
into one compound task or dropped (section 2, "Measure the thread on its own commits").

Not a task: a single fix or a single commit, a one-setting change, a bug with one cause in one file, status chatter,
process rules, questions, praise, a fix that is only a re-import of assets the start does not have, a sweeping pass
resting on a pack imported later, anything whose outcome neither play nor code can show. If a game's history has fewer
than 10 qualifying threads, ship fewer tasks.

**What makes a thread hard for an agent.** An agent writes code readily and rarely checks the outcome in the running
game, so what only shows in play is where it falls short. Prefer threads that settled these, and give each one its own
probe in a play that reaches the moment:

- **Feedback that must show in play**: a HUD readout, a marker, a sound or an effect when the event happens (a play
  that triggers the event, then `ui`, `audio`, `components`);
- **A look change**: colours, materials, dressing, HUD art (a `looks_as_asked` rubric item beside what a probe can
  read of it: `screen` relative to the start, a node's own properties, the `ui`);
- **Menu, pause and back flows**: Escape or the back button closes what it opened and returns where it came from (a
  task play with the keys or touches, then `ui`);
- **A tuned outcome judged in play**: seen or not seen at a distance, holds or breaks under load, passable, winnable
  (a teleport to the spot, then the outcome);
- **Many small requirements in one span**: one probe each, so a single dropped item shows.

Threads an agent solves in minutes: one system's logic, a feature whose outcome the code alone shows, a brief that
points at the system. Hiding the list of problems (a brief that reports the symptoms a player meets, not a
checklist) lengthens a run without changing what it misses.

**Finding threads.** Walk the history for clusters: `git log --stat` around a feature, runs of commits on the same
files (`git log --format=%h -- <path>` piled up in a short window), several `user.direction` rows on one topic
(the workflow rows' `"direction"` links), fixes followed by "still", "again", "regressed" or a revert, a renderer or
project-settings change that broke a system and the commits that mended it. Read the whole span before picking
its ends.
Playtest rows (`"target": "playtest"`) and the commits that answer them are the first place to look: what a
person felt while playing is what strong agents miss.

**Taste threads (owner, 2026-11-19).** A thread that settled how the game looks or feels (playtest issues, a choice
between two versions, a look or feel direction) is a taste thread. The person who directed the game picks which
candidate threads are taste threads and writes or approves each one's brief in a playtester's words (section 3 still
holds: observations only, nothing quoted from chat). The brief opens with the game's feel intent from the design doc,
so "better" has a direction; those sentences are context, like the game's description, and ask for nothing. Its
reference is a commit the person's verdict called better: a fix they judged same or worse is no reference, so extend
the thread to the round they called better, or drop it. A game made before these rules has no verdict rows: its
taste threads take their reference as any other thread does (section 2).
What the design doc's keep list holds must still hold, so a solution that spoils it fails: a keep line a still frame
can show goes to the `still_works` look judge, and a keep line about feel gets a `still_works` probe of what the
player meets. A feel probe's threshold comes from this game's own start and the reference the person approved (as
the threshold rules above say for its kind of ask), or from a number the brief states, never from the starting
numbers in the game-session skill: each game is judged by its own feel, so the games don't all drift toward one.

**Fixed framings for look judges (owner, 2026-11-19).** A judge compares sides like for like, so its plays show each
asked look from fixed framings, the same on the start, the reference and the agent's build: for a 3D game, from above
the area (layout, overlap), at eye level (looks), and from the player's own view during the action (feel), as far as
the play's inputs can stage them (a view or teleport onto something the start has; where no input reaches a framing,
use the nearest one that does); for a 2D or
2.5D game, the whole play area, a close-up of the subject, and the player's view during the action. Reach each
framing through something the start already has (an actor, a tag, a control the instruction names), never through
raw coordinates of the reference's level. A judge item asks only what its sentence asks, so extra features, effects or
decoration earn nothing, and still frames cannot show how controls feel: write a feel ask as a probe of what the
player meets (the game-session skill's feel words point at what to measure), and a judge item only for what a frame
can show.

## 2. Picking the commits

### Starts on the engine

The checker plays a start exactly as committed, with the factory's pinned engine: it never upgrades, patches or
rewrites a game, and a start must be a Godot 4.7 project (its `project.godot` names the version; the validator
checks it). Its "build" is the import: it passes when the import ends without a script error. So `seed.commit` and
`seed.reference` must both import and run as they are. When a thread's real start can't be used as it is (an
unrelated later fix is needed for its scripts to parse), give it a made start:

- **B** = main's head. **S** (`seed.commit`) = B with the thread's change taken back out of the game itself,
  re-created by hand where later work moved the code: the issue must really be back, and S must still import. Every
  other path of S (`workflow.jsonl`, `Scripts/`, `steps/`, `Docs/`, `README.md`, manifests) is exactly as at the old
  pre-fix commit, so nothing in the start records or regenerates the fix. **R** (`seed.reference`) = a child of S
  whose tree is B's (`git commit-tree <B^{tree}> -p S -m "<message>"`; without `-m` it waits for a message on its
  input, or makes R with none).
- Both live on the branch `starts/<task name>` (pointing at R), pushed with the game; the dataset ships main and
  every `starts/` branch, so the delivered history holds them.
- Scenes and resources are text: one may go back to its pre-fix version when no later commit changed it, or with the
  later changes kept and only the fix taken out by hand; a binary asset only if no later commit changed it; otherwise
  re-create the issue in code or settings, or pick another task. Keep every `.import` and `.uid` with its file.
- For a thread, "the change" is the whole thread: S takes every commit of it back out, not only the last one, and the
  thread's commits on main (its count and files) are what qualify it; note them in the task's `tasks-workflow.jsonl`
  row (in its `params`, `"thread"`: first and last commit of main).

- **Read the code at `seed.commit`** and confirm the issue is there (the reference diff's removed lines, or a search).
- **The thread's real ends are often not the commits that say so**: a descriptive commit may touch only
  `workflow.jsonl` while the code is in the WIP commit before it. Use `git show --stat` around that time and the
  workflow rows that link the direction (`"direction"`). Start before the first attempt (the earliest, when the
  thread settled several issues), so the agent faces every issue the thread settled, and end at the commit after
  which no more work on it followed.
- **The reference must import and run**: the grader plays it beside the agent's result. If the last fix crashed until
  a later commit, extend the thread to the later one.
- **Chains and splits merge**: a person complained again after a fix ("still too low"): one task from before the first
  fix to the last. A direction with several issues fixed in separate commits: one compound task, one required probe
  per issue.
- **Spans may overlap; issues may not.** Two tasks may share commits, overlap or nest: one task's start or reference
  may be another's, and a long feature span may contain a shorter thread that settled different issues. Different
  threads that ran at the same time (a camera rework during a HUD pass) are separate tasks over the same commits. What
  never repeats is an issue: two tasks never test the same outcome, so dedupe against the game's existing tasks by
  issue (their briefs and required probes), not by commits. Merging still wins over splitting one thread into short
  tasks (section 1).
- **Measure the thread on its own commits.** The validator measures everything from `seed.commit` to `seed.reference`,
  so a short thread inside another thread's stretch can pass the floors on the other thread's work. Which commits are
  the thread's own is your call (the commits that answer its directions or work on its issues); list them and count
  them: `python <GGF_ROOT>/godot-game-factory/tools/thread-stats.py <GGF_ROOT>/games/<slug> <commit> <commit> ...
  --span <seed.commit>..<seed.reference>` (git only, seconds). Its `thread` line adds up each listed commit's own
  changes (a line two of them touch counts twice), its `span` line is the reference against the start, which is what
  the validator holds to the floors; so the thread's code lines can be more than the span's. A thread whose own
  commits are below the floors (section 6) is too short, whatever the span says: extend it, merge it with its
  neighbouring issues, or drop it. When you tell the person a task is ready, give its own line from the tool
  (commits, files, code lines, systems).
- Asset-only fixes are fine (the agent can make the same change in the scene or resource text, or by code); drop one
  only when its outcome cannot be seen.

## 3. The instruction (the brief)

Write it from the context, never by quoting a person: no quotes, typos, capitals, profanity, "the owner said" or chat
wording. The reader is a capable developer who has never seen the game.

**Every brief is only an observation**: what a player or QA sees, in plain words, for every issue the thread settled.
It names no cause, no place to look, no file, system, script, node, scene or asset, and no mechanism ("the
camera feels jammed against the ship", not "the spring arm collides with the water layer"). It never says how many
changes are needed or that the issues are related. Leave out the play_scene line, which the harness adds after the
brief ("QA plays the game from the scene ..., with the arguments ..."; with `play_scene` null, the arguments alone).
An issue that shows only once another is fixed (a first fix that didn't hold: the lamp that never lights hides how
dim it is lit) can't be reported as seen at the start: say what is expected there in the item that hides it (how a
lit lamp looks), and give it its own probe.

- **bug_fix**: a QA bug report listing each symptom: what happens, how to reproduce it, what is expected. Code
  identifiers only inside a quoted script error line from the game's log, which is what a log shows.
- **correction**: what is wrong and how a player sees it, item by item, then the wanted outcome.
- **feature / change**: a producer's ticket: what and why, how the player uses it (which key, or which touch on a
  mobile game), the behaviours and looks wanted, what must still work. Close with the art bar: the project's own
  assets and engine features, no primitive placeholder shapes, no debug text.
- Describe the controls the player needs; the harness tells the agent which scene QA plays (`play_scene`). Where the
  game starts on a title screen or a menu, say how a player gets in (the start control, by the text it shows), or
  state the scene QA plays from (section 4).
- **Say what QA's plays do to the game, where it matters**, in the instruction's note on how QA played it: a play
  steps the game at a fixed 30 frames a second (`delta` 1/30), faster than real time, but a play that listens for
  sound, which runs at real time; it may put the player at a spot or set up a contact (a foe held in front, a hit
  through the game's damage method); it ends by closing the window, as a player does; every play starts with no
  saved data but one that runs after the plays that saved it. Game logic driven by the wall clock, or state that doesn't follow a
  player put elsewhere, behaves differently under these: say so where the task touches it, and give the checks
  windows that allow for it (section 5).
- Never name the studio, its pipeline or its tools. Never describe the fix or any step of the thread.

## 4. `play_scene` and `play_args`

The game's main scene is usually a title menu that simulated input cannot be trusted to leave, so a task needs a
start that goes straight to the gameplay where the issue shows: `play_args`, the game's own command-line arguments
that pick its scenario (`"play_args": ["-scenario", "2"]`), and `play_scene`, the scene a play opens instead of the
project's main scene (a project path, `"play_scene": "res://scenes/Harbor.tscn"`), or null.

- **A game made from the template starts its scenario itself**: its `Scenarios` autoload reads `-scenario <n>` and
  loads that scenario's scene. So its tasks set `play_args` and leave `play_scene` null. Named in `play_scene` as
  well, the scenario's scene would load a second time.
- Name a `play_scene` only for a scene no scenario loads. The project's main scene then doesn't run; its autoloads
  do (they load before any scene), so what the game sets up in an autoload exists in the play and what it sets up in
  the main scene does not.
- Read the game's command-line and scenario handling at `seed.commit` and check that the scene and the scenario
  exist there and at `seed.reference`. Every grader play uses them (boots, idle and drive, and a judge's own plays:
  its route, its before and reference plays). What a play does to the game, and the rules for the arguments (their
  form, the flags a task can't set), are in docs/task-probes.md. A play never chooses a renderer or a frame size.
- **A play does what a player must do to reach the state it probes.** Where the start scene is a title screen or a
  menu, every play that checks something in the level first gets past it as a player does: it clicks the start
  control by the text the instruction quotes (`{"t": 0.5, "widget": "begin_run", "click": true}` clicks a button
  reading "Begin Run", whatever its node is called; a touch on `{"widget": "begin_run"}` on a mobile game) and gives
  the game time to change scene. A control's node name serves too when the control exists at `seed.commit`, never a
  name only the reference has. Or the instruction states the scene QA plays (`play_scene`, or the `play_args` that
  start it). Never a shortcut only the reference has (a flag, a debug key, a scene the fix added).
- Check in the task check's screenshots and `track` that the reference's plays really start where the issue shows.

The plays also need to know which node is the player (for `player` measures, teleports, a `near` around the
player). The probe takes a shown node in the group `player`, else the first `CharacterBody3D` (or
`CharacterBody2D`), else the camera. Where that finds the wrong node, or none worth the name, set the task's
top-level `player`, an object select that names it for every play (`"player": {"name": "Boat"}`):
docs/task-probes.md.

## 5. Milestones and checks: deterministic probes decide

**Pass/fail is decided by checks the grader computes itself:** `build`, `boot`, `log_absent` and **`probe`** checks, and
nothing is graded from pixel statistics of the game's frames except the frame's mean luminance (`screen`), whose
threshold is always calibrated or relative to the start. Two judges are required: `looks_as_asked`, whose rubric
items are the brief's own look-and-feel asks, and one in `still_works` of what must still look as it did (below).
Every other judge (`judge`, `code_judge`: taste, readability, code review) stays a `"required": false` quality check.
Nothing in a task reads the agent's tool calls: a task is graded on the game's outcome alone. A task still needs
required probes the grader decides without a judge (section 6). The probe language, every play, measure and
threshold with the rules that gate a task, is the task author's contract
[docs/task-probes.md](../../docs/task-probes.md), checked by the schema
[docs/schemas/game-task.schema.json](../../docs/schemas/game-task.schema.json) and `tools/validate-game.py`. Never
use an input, a measure or a field that docs/task-probes.md doesn't list.

Each milestone is a reward group; a run that gets part of the way earns part of the reward. A task holds 1 to 8
milestones and a milestone 1 to 32 checks; their names are lower-case letters, digits and `_` (a milestone's at most
32 characters, a check's 48). **A no-op scores zero (permanent):** the score is the weighted share of checks passed,
so every check the start already passes takes `"weight": 0`: `builds`, `boots`, all of `still_works`, any
`log_absent` or `file_exists` true of the start, and any probe the start already passes, required or not. They still
gate: a run must pass the required ones to be solved.
`validate-game.py` refuses a weighted `build`, `boot` or `still_works` check, and the task check a weighted probe the
start passes; nothing checks a `log_absent` or `file_exists` outside `still_works`, so their `"weight": 0` is yours to
set. The usual order:

1. `builds`: `build` (`project_builds`: the project imports and every script parses).
2. `boots`: `boot` 60 s (`boots_clean`: the game runs 60 s without a crash), `needs` the build. A script error the
   game survives is not a crash; a `log_absent` check catches those. It is required like any check that doesn't
   say `"required": false`, so a required `log_absent` the reference fails makes the task INVALID: no solution like
   the reference could pass it (docs/task-check.md).
3. `fixed` (bug_fix, correction) / `done` (feature, change): `probe` checks of the reported outcomes, `required`,
   `needs` `boots_clean`: at least 3, one per issue the thread settled (split them over several milestones, e.g.
   `fixed_hud`, `fixed_camera`, when the issues are separable). Each one fails at the start for the reported reason
   and passes on the reference. The required `looks_as_asked` judge goes here when the brief asks for a look.
4. `still_works`: probes that what must keep working still does (the player still moves, the HUD still shows, the
   scene still loads its scenario), and a required judge with `"before": true` for what must still look as it did.
5. `quality` (optional, never required): a `judge` for taste items no probe can capture ("reads as a castle",
   readability of text over the scene), and a `code_judge` for code quality. A
   judge is written
   `{"name": ..., "kind": "code_judge", "question": ..., "rubric": [{"key": ..., "criterion": ...}]}` with
   `"required": false`; a `judge` (of the game, from screenshots and frames of the grader's own play) may also set
   `"before": true` to be shown the start beside the result, and `route`, `reference`, `plays` and `shots` (the task
   schema's `Judge` says what each does).

**Every look-and-feel ask in the brief gets a required `looks_as_asked` rubric item** (such an ask gates the task:
checks thinner than the brief let a run pass without the look). Go through the brief ask by ask: what a probe can
measure gets a probe; what only an eye can tell (reads
clearly, fits the style, looks like the thing it is meant to be) gets its own rubric item, `"required": true`, in one
required `judge` named `looks_as_asked`, with `"before": true` and `"reference": true` when the seed has a reference.
A judge can misread screenshots, so word each item concretely, decidable from the screenshots alone, so the unchanged
game scores 0 on it and any solution that meets the brief scores 1. What must still look as it did goes in a required
judge in `still_works` the same way. **Every judge names plays of its own** (`plays`: up to 4 task plays) that show
each of its rubric items at the moment it can be seen: past a title screen, after the task's own key, in its scenario
or scene (when a probe's play already reaches it, reuse it under its name, written identically); a judge without them
sees only the idle `look` and the `drive` of the start scene. One subject per judge; no rubric item about "every
screen" unless its plays open every screen; no empty criterion such as "shows what the ticket asks":

```json
{"name": "looks_as_asked", "kind": "judge", "required": true, "needs": ["boots_clean"], "before": true,
 "reference": true,
 "question": "With the upgrade menu open, does it read the way the request asks?",
 "rubric": [{"key": "costs_legible", "criterion": "Each upgrade's cost is legible against the panel behind it.",
             "required": true}],
 "plays": [{"name": "open_upgrades", "seconds": 10,
            "inputs": [{"t": 0.5, "key": "<Keyboard>/u", "press": true},
                       {"t": 0.7, "key": "<Keyboard>/u", "press": false}]}]}
```

The judge is shown 5 screenshots of each play, at 10, 30, 50, 70 and 90% of its `seconds`: time the inputs so the
state is on screen at those moments. A window or a frame is in play time, which runs faster than the wall clock
(section 3): time it from what the plays recorded, never from real seconds. A play also runs on the task's start (`"before": true`) and on the reference
(`"reference": true`), so it must run there too; a key that does nothing at the start is fine
([docs/task-probes.md](../../docs/task-probes.md)).

**Motion is asked two ways.** Motion that is a number (eases instead of snapping, gentle, no sudden moves) is a probe:
a task play with `"every": 0.1` and a field over the window of the move, with `"agg": "step"` for the largest jump
between two samples ([docs/task-probes.md](../../docs/task-probes.md)). Motion that can only be seen
(feet that slide, a trail) is a `looks_as_asked` item with a short play and many `shots` (2-20 of each play, plays
times shots 20 at most): a 5 s play with `"shots": 20` is a frame every 0.25 s, screenshot i of N at `seconds` x (i +
0.5) / N.

A probe names one measurement and its threshold:

```json
{"name": "hero_on_ground", "kind": "probe", "required": true, "weight": 3, "needs": ["boots_clean"],
 "describe": "After the scenario starts, the hero stays on the ground near the west kiln tower instead of falling through the town.",
 "play": "look",
 "measure": {"probe": "player", "field": "y", "window": [3, 18], "agg": "min"},
 "expect": {"op": ">=", "calibrate": 0.5}}
```

Godot's 3D world is Y-up and in metres, with -Z forward: height is `y`, distances are m, speeds m/s; a positive pitch
looks up and a positive yaw turns left.

- `play`: `look` (20 s idle), `drive` (22 s: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with
  `<Keyboard>/space` at 9 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s; on a mobile game the same route by
  touch), or a task play `{"name": ..., "seconds": ..., "inputs": [...]}` when the outcome needs other input or
  another start. A task play's inputs, each at its time `t`: a key or button
  (`{"t": 1.0, "key": "<Keyboard>/f2", "press": true}`, later `"press": false`; `<Mouse>/leftButton`,
  `<Gamepad>/buttonSouth`; on a mobile game `<Keyboard>/escape` is the phone's back button), mouse movement (a `move` spread over seconds for a look around), the wheel, the cursor, a click
  on a control by its node name, a touch (`tap`, `drag`: below, and docs/task-probes.md section 1.3), a teleport of the player (to a point, or
  `teleport_to` the node a select matches), a wait in real time, a named screenshot (`shot`), a scene load, a view
  turn, and the stages of a contact (`pin`, `damage`, `set`: "A contact ask is staged" below, and
  docs/task-probes.md section 1.4). docs/task-probes.md has each one's form.
- **A play may run up to 1200 s; keep it as short as what it measures allows.** A play's `seconds` and every time
  in it (an input's `t`, a `hold`, a move's or a drag's `over`, a measure's `at`, an event's `within`) go up to
  1200 s, so a moment a player reaches only after a long uninterrupted play (a later wave, a long build-up, a day's
  end, a run past five minutes) can be reached by playing to it.
  Every second is played on both sides of every check that names the play, so start the play where its moment is
  (`play_scene`, `play_args`, a scene load) and end it soon after what it reads.
- **A cursor move then a press clicks what the game itself draws there.** The cursor is the game's own mouse: a
  `cursor` input and a `<Mouse>/leftButton` press and release reach the game's `_input`, a control it draws itself, its
  `_unhandled_input` and the physics picking at that point, and what the game polls (`get_mouse_position`) is there.
  So a menu or a HUD the game paints on the canvas and hit-tests itself, which no widget click can find, is driven by
  a cursor input onto it and a press, as a player clicks it. Aim it at a place every build keeps (the instruction's
  layout, or where the start draws it); a `Control` is still clicked by its caption or name.
- **A key goes to the focused control first.** As on a keyboard, a key reaches the game's `_input`, then the control
  that has the keyboard focus, and the game's later stages (`_unhandled_input`, where most games read their actions)
  only when that control doesn't take it. A text field a click focused takes every typed key, so the game's action
  on that key doesn't fire while it has the focus. A play that must drive the game after typing into a field first
  leaves the field by the player's own input (a click on the next control, the key the game closes it with), never
  by a key the field would type.
- **A play that reads what another play writes names it in `after`. Never rely on the checker's order.** A task play
  that reads a save (a level reached, a profile filled in) lists the plays that write it:
  `"after": ["writes_save"]`, by their names. On each side they run, and end, first, and the reader starts on the
  saved data they left; every other play starts with none. A writer that failed still counts as run, so the failure
  shows in the reader's checks. Of two writers, one names the other in its own `after`. A writer saves during its
  play, or when the game is closed (`NOTIFICATION_WM_CLOSE_REQUEST`, `_exit_tree`): a play ends that way
  (docs/task-probes.md, 1.1).
- **A play never relies on state it doesn't make.** Each play starts from a fresh save: an existing save, a filled
  profile, an expired timer or an unlocked level is there only when the play makes it with a player's own steps, when
  the plays its `after` names made it, or when the instruction states it and how QA's play reaches it.
- **A first launch may say `"fresh": true`, never beside `after`.** Every play without `after` already starts with
  the game's saved data cleared; `fresh` says so for a play the instruction sets on a first launch, so a reader sees
  the play's start without knowing the checker. A play starts either clean or on what others saved, never both.
- **A play keeps its own preconditions true.** No input on the frame the game resets a state (a key at a
  scenario's, a scene's or a shift's start lands while it resets: send it a few seconds in). A teleport moves the
  player alone: never teleport past what the game moves with the player or holds it to (a carried object, a tether,
  a signal's range, any limit the instruction gives); walk or drive there instead.
- **A play never repeats an action that already happened.** A second click on Continue or Retry after the first
  worked finds no button (it is gone) and is a miss in `inputs_missed`: each click once, while its control is there.
- **A click scrolls its own list.** A click or a tap on a control that only the lists it sits in hide (scroll
  containers, at any depth of nesting: a list in a list, a row below the frame) scrolls those lists the least way
  that shows it, as a player scrolls to an item, and presses it in the next frame. So never script the scrolling for
  it: no wheel turns, drags or keys before a click whose only purpose is to bring its control into view (they are
  timing you guess, and a build that lays the list out otherwise needs other ones). A control hidden any other way
  is still a miss that says it is "scrolled out of its container's view", whatever `optional` or `disabled` say: one
  behind a container that clips without scrolling, one a list can't scroll far enough to show. A drag scrolls
  nothing: drag on what is in view. Scroll with the player's own input only when the scrolling is itself what the
  task asks about.
- **A covered control can't be clicked.** A click or a tap lands only where a player's pointer at the control's
  centre would reach it: under a dialog, a popup, a tooltip, a fade or any overlay that takes the mouse, it is a
  miss that says "covered by another control", whatever `optional` or `disabled` say, and `probe.log` names what is
  over it. Close the dialog, popup or overlay first with the player's own input (its button, the key the game closes
  it with), or wait for it to go, then press the control. A see-through overlay that ignores the mouse covers
  nothing. The `widgets` field `covered` reads whether a control is covered, for a check that a button can be
  pressed where it shows.
- **An optional click is for a control that appears only in some states**, never to hide a click that should land.
  `"optional": true` on a widget click is for a control the game shows only sometimes (a confirmation that appears
  only when something exists): when nothing on screen matches it, the play goes on. A miss is how a play says it
  never reached its moment, so a click the play needs stays required: a play that makes the state itself clicks its
  control as required, and a matched control that takes no press, is still out of its container's view, or is
  covered, is a miss either way.
- **A control is named by the words the player sees, in the game's own language.** A widget click or a tap on a
  widget may give a button's caption exactly as the screen shows it (`{"widget": "开始游戏", "click": true}`), spaces
  and punctuation included: that is how a player finds it, and any build that keeps the words keeps the click. A
  caption written exactly wins; only when no button shows it so does one that reads the same with case, spaces and
  punctuation aside take it, so write it as shown when two buttons read alike.
- **A click names a control by the words shown on it, even when the control is not a button** (a menu row the game
  builds of its own labels, a label over a hit area, a `Label3D` sign). A click no Control takes by name, class or
  caption is made on its text as shown, as a player clicks the words they see: the pointer goes there and the left
  button goes down and up (the Lab's Godot grader does the same). Exactly one place on screen may read those words,
  because a click on words shown twice can't tell which one the player meant: the click is then a miss that names
  both places, whatever `optional` says, so name the control by words only it shows (a row's words read joined left
  to right count, "1 BUY RANK 300 PT"). Text a script draws itself with `draw_string` is not read: click it with a
  `cursor` input and a press.
- **Mark a click `"disabled": true` only where the instruction says the control must be disabled.** A click on a
  button shown but disabled presses nothing and is a miss, as a player's click there does nothing; `disabled` is for a
  button the game locks by design (a choice the instruction says stays locked), and its click lands when that button
  is shown disabled. A miss is how a play learns its control was not usable, so a click the play needs to press is
  never marked; `optional` never covers a disabled button either.
- **A window is timed from the event it measures.** Where the moment depends on the game (a boss that appears after
  a load, a door that opens when its animation ends, a score shown when a round is over), tie the window to that
  event with `since`: `"since": {"measure": <what shows the event>, "expect": {"op": ">=", "value": 1}, "within":
  20}` counts the measure's `window` and `at` from the first sample in which the event's reading meets its expect,
  so a build or a machine that gets there a little later is read at the same moment of the event; one where it
  never comes reads nothing, and fails. Otherwise time it from the input that sets the event off, with a margin for
  how long the reference took (read in its samples), never a fixed second picked without looking where the event
  fell.
- **A judge's picture is taken when the thing is on screen.** A `shot` input may say `when` (the same event form):
  the picture is taken in the first frame at or after its `t` in which the event holds, so a judge or a `seen` probe
  sees the banner, the dialog or the score itself rather than a second guessed around it. Its measure is one the
  probe reads every frame (`ui` count or text, `widgets` count or visible, `objects` count, a position, `active`,
  `hidden` or a `prop:`); an event that never comes is a missed input, so give it a `within` that covers the slowest
  build you mean to accept.
- **Touches.** `{"t": 2.0, "tap": <spot>, "hold": s, "finger": n}` puts a finger down at the spot and lifts it (after
  `hold` seconds: a long press, a button kept down); `{"t": 2.0, "drag": [<spot>, <spot>, ...], "over": s, "hold": s,
  "finger": n}` moves it through the spots over `over` seconds and keeps it at the last for `hold` (a swipe, a
  slider, a virtual stick pushed over and held). A spot is a point of the screen `[fx, fy]` in fractions from its top
  left, or `{"widget": "<node name>"}`: the centre of the first visible `Control` of that name (a wildcard) or class,
  else of the button whose shown text is it as written (`{"widget": "确定"}`), else reads it alike (`{"widget":
  "tap_me"}` for a button reading "Tap Me").
  Name the control where you can: its place differs between landscape and portrait, its name does not. Touches of
  different fingers may overlap; one finger's touches are at least 0.1 s apart and over by the play's end (the
  validator refuses otherwise); a touch whose control isn't on screen is a miss the play reports, and nothing is
  touched. A mobile game's plays use touches and the back button (the key `<Keyboard>/escape`), never another key,
  the mouse or a gamepad.
- `measure.probe`, one of:
  - `player`: the player's track (x, y, z, speed, how far it moved);
  - `camera`: the player's camera against the player (distance, height, pitch, yaw, fov, occluded, player on screen);
  - `objects`: nodes, selected by `name` (a wildcard), `tag` (a group), `component` (an engine class, a script's
    `class_name` or its file name), `near` a point, `where` (a property's value) or `has` (what it carries): how
    many, where, shown or hidden, and a variable of the node's own by `prop:` (`prop:health`, `prop:position.y`;
    `prop:<Class>.<member>` reads it on a node of that class below the matched one); after a staged contact, its
    own short stop (`frozen`) and what a staged hit did (`damage_taken`); whether it changed since the start
    (`changed`: 1 when a crate breaks by hiding its mesh and showing pieces, by an animation or by physics, and as
    well when it moves, turns or scales whole, idles or gains a drawing child: gate "it broke" only on an object the
    play never moves, or with `spread` or `simulating`; a crate a build frees has no row, so read its `count` beside
    `changed`, never "still whole" from `changed` alone) and how far its pieces lie apart or moved (`spread`,
    `bounds_change`, `pose_change`, in the game's units, calibrated only); whether it gives light (`lit`) and how
    much (`glow`, never a literal threshold), whatever lights it: a light node, an emissive or an unshaded
    material, a shader of the game's own, a particle effect. Gate "the lamp is on" with `lit`, never by counting
    its light nodes: another build lights it without one. Read `glow` only where the ask is about how bright: it
    has no value for a lamp an effect, a texture or a shader of the game's own lights. In a game drawn unshaded
    every mesh reads lit, on or off: gate on the property that switches the lamp there. Read a count or `"of":
    "all"` over a `has.lit` select at the end or after a settle window, never at the first sample or right after a
    switch (a part drawn for the first time gives that sample no value). Neither goes in a play that reads a
    `render` budget (the probe may draw a part alone to read it);
  - `components`: the nodes of a class wherever they sit (lights, particle effects, mesh instances, audio players),
    by what they are rather than by a name;
  - `widgets`: a `Control`'s own state on screen (visible, text, a bar's percent, a slider's value);
  - `ui`: what the UI shows on screen, element by element (the text, pictures and boxes that are drawn, their count
    and place; `match` for a text). It reads the text of Controls and of `Label3D`s only, never text a script draws
    in `_draw`, a shader draws or a texture holds. You can't know how a solver will draw text the thread creates, so
    a check of new text reads it with `seen` (below) or reads the state behind it, never `ui` text alone;
  - `seen`: text the visual checks' model reads from a named shot of the check's own task play (docs/task-probes.md
    2.22). **Read text from the game's UI first** (`ui`, `widgets`): `seen` only for text nothing else gives, drawn
    by a script, a shader or a texture. Give it a loose `rect` or none, and take the shot at a still moment (a clock
    ticks). It is a visual check: the task still needs a required probe besides it, and the task check saves its
    crops for you to read blind;
  - `screen`: the frame's mean luminance, never a literal threshold;
  - `audio`: the players that play and how loud the listener hears them, the mix's level, and the sounds that
    start, however short (`started_audible`, and by their streams' names `sounds` and `repeats`);
  - `spawns`: nodes of a class appearing and going;
  - `pieces`: how many mesh pieces are placed, however the scene holds them (a mesh instance, each instance of a
    multimesh, each grid map cell), drawn or not, and their triangles (never a literal threshold): "the forest is
    dense" reads the same whether a build placed 300 trees or one multimesh of 300;
  - `ground`: the ground's height at a point, or its relief over a box (`range`, never a literal threshold), traced
    down through what isn't ground;
  - `drawn`: what is drawn in a place of the 3D world or along a line, whatever draws it (a mesh, particles, a
    material that pans): whether anything is (`drawn`, a literal), how much of it moves (`motion`), its base colour
    (`base_r|g|b`, `base_change`), how far a beam reaches and how much of a line it covers (`reach`, `length`); every
    field but `drawn` calibrated or relative to the start. Keep the place tight and the player out of it. It needs a
    drawn frame, so a play that reads a `render` budget takes none (docs/task-probes.md section 2.19);
  - `log`: a line in the play's log;
  - `render`: what the renderer drew, against a budget: draw calls, triangles, texture memory (`draw_calls` and
    `triangles`, the highest over the frames since the previous sample, and `texture_mb` at the sample;
    docs/task-probes.md section 2.20). A literal threshold is allowed, since a budget is a
    number of its own (`{"op": "<=", "value": 700}`). Give a budget check a task play of its own that goes to the
    view and reads nothing else;
  - `world`: the game as a whole, each over the frames since the previous sample: the lowest `Engine.time_scale`
    (`time_scale`: "time slows"), whether the game went on (`flow`: below 1 when its time slowed or stopped or the
    tree was paused, "the game holds") and whether it was paused (`paused`), docs/task-probes.md section 2.21.
  Each kind's fields, defaults and limits are in docs/task-probes.md.
- `expect`: a literal (`{"op": ">=", "value": 1}`) for facts (counts, booleans), or
  `{"op": ">=", "calibrate": 0.5}` for continuous quantities: the grader measures the start and the reference in the
  grading environment and puts the threshold that fraction of the way from start to fix; `op` points to the fix's side.
  Where the reference is only one fair way of reaching the outcome (most features and changes: how fast a new thing
  spins, how loud it is), a calibrated threshold would hold every solution to the reference's own tuning: set it
  relative to the start instead, `{"op": ">=", "start_plus": 30}` or `"start_times"` (docs/task-probes.md). Such a
  threshold needs a value at the start, and what the task adds isn't there yet: measure over what the start has too,
  not over the new things alone, which leave a required probe without a threshold and the task INVALID.

Write probes from the game's own code at `seed.commit`: the real classes, groups, node names, `res://` scene paths
and `Control` names. **Never a name only the reference has** (a class, group, node, scene or asset the thread itself
created): another fair build names it otherwise and reads as absent. Select what the thread creates by
what it does or where it is (`has`, `near`, `ui` with a `rect` or text); `validate-game.py` refuses a required
probe that names something the start lacks and the reference has. **Select by what the thing is, never by where the
old one was**: no `near` around the start's place for something the task asks to move (a camera that must stand
further back leaves the sphere around its old place); `near` only around a place the task doesn't change. **Test the
outcome a player sees, never the implementation**: another valid fix must
pass ("the hero stands on ground", "the stone breaks the wall piece it hits", "the lap count shows the lap the boat is
on", not "spawn_height is 0.92" or "the function was changed"). Measure the effect the player sees, never one way of
building it: not a global (`world` `time_scale` for "the game runs at double speed": a build may speed its own clock;
read how far or how fast the thing goes), not a node's position relative to its parent (`prop:position` changes when
a fix re-parents the node; `x`, `y`, `z` are in the world), not the root's turn when a part below it does the moving
(read the part that moves), and never a count of samples standing in for a count of events (`spawns`,
`started_audible`, a counter the start shows). `describe` says the assertion in plain
words; it is shown in the grade, never to the agent.

**Everything a required probe or its play relies on is in the instruction or exists at the start commit**: node,
class, group, property and scene names, exact strings and regular expressions, coordinates, input sequences. The
instruction never names how a build stores things ("Hints, never answers", below), so what the thread creates is read
by what the player sees:

- **Prefer what the player sees.** On-screen text through `ui` with a loose `match` (any case, any spacing, `\d+`
  for a number); nodes by a group or class the start has, by what they carry (`has`) or where they are (`near`); a
  place reached by `teleport_to` or `pin` on a node, never raw coordinates; a control by the text it shows (a caption
  the instruction quotes) or by its name at the start.
  Never match an exact string the instruction doesn't quote, and never a run of keys that only works on the
  reference's layout (a menu walked by counting presses).
- **"Shown" means on screen.** `ui` and `widgets` read what is on screen, as a player sees it: shown itself and by
  every parent and canvas layer above it, not transparent, inside the frame and not scrolled out of a container's
  view. A node's own `visible` alone is no proof: a hidden parent hides it. So a check that something is shown, or no
  longer shown, passes the same on a build that hides a widget as on one that removes it. Write `"visible": false` in
  a widgets select only when the check means the widget exists while hidden.
- **Ask the second-solution question of every check**: would a correct solution that names things otherwise, lays
  the scene out otherwise, or hides instead of removes still pass? If not, move the check to what the player sees. Check names are unique and `needs` only names earlier checks;
calibrated probes, `code_judge` and `"reference": true` judges need `seed.reference`.

A task is valid only when it passes the task check: the untouched start (the no-op) fails the task and earns nothing,
the reference (the oracle) passes every required check, and every required `still_works` probe already passes at the
start (below, "The no-op and the oracle, on your own machine"). **Every check is
run before it is submitted, on both sides, and you read the measurement**: it fails at the start, passes on the
reference, the play's inputs landed (`inputs_missed` empty, `probe.log`), the probe matched something (its rows),
and the judge's frames show the moment. A threshold comes from the instruction, from the start or from calibration,
never a number picked because the reference passes it. **The reference does everything the instruction asks**, in a
place a play can reach; where it doesn't, the task needs another reference. Write the probes per
[docs/task-probes.md](../../docs/task-probes.md), then check the game's tasks **together, in one background run** (one
run prepares a commit several tasks share once, and the person can leave it running and come back). Write and commit
every task first, then start the check as its own process so it outlives your turn and no tool timeout cuts it short
(PowerShell, under either agent):

```powershell
Start-Process python -WindowStyle Hidden -WorkingDirectory <GGF_ROOT>\godot-game-factory `
  -ArgumentList 'tools\task-check.py', '<GGF_ROOT>\games\<slug>', '--all' `
  -RedirectStandardOutput <GGF_ROOT>\games\<slug>\.task-checks\run.out `
  -RedirectStandardError <GGF_ROOT>\games\<slug>\.task-checks\run.log
```

Create `.task-checks` first if it doesn't exist. Tell the person it is running and that they can leave it
(docs/task-check.md says what a run costs). Read `<GGF_ROOT>\games\<slug>\.task-checks\progress.txt` to see where it
stands (rewritten after every task; it says `finished` at the end); never start a second run of the same game while
one is going. A recheck of the tasks you fixed takes `--task <name>` once per task instead of `--all`.
`--task <path>/Tasks/<name>.json` checks a file not committed yet ([docs/task-check.md](../../docs/task-check.md)).
The check makes a copy of each start and reference with the probe addon, imports it, and plays it from source on a
Windows desktop of its own (nothing on the person's screen), a desktop game at 960x540 and a mobile game at the
phone's size, and writes VALID or INVALID per task with the reasons and the measured values. **A task ships only when
the task check says VALID**; for INVALID, fix the task, never the threshold toward what the start happens to measure.

**The check asks no model, so you score the judges.** For every `judge` check it plays the check's plays on the start
and on the reference (and its `route`, read from the reference's copy, as the Lab plays it) and saves the screenshots
the cloud's judge would be shown under `.task-checks\<task>\judge-shots\<check>\` (`start\`, `reference\`, and a
blind copy in `blind\A\` and `blind\B\` whose sides are in `blind\key.json`), with `ask.md` holding the brief, the
question and the rubric. Look at the pictures blind: score every rubric item for A and for B from 0 to 1 into
`blind\answers.json` before you open the key and `sides.md`, then check the task again. An item the pictures don't
show (its moment isn't on screen, its subject is off view, hidden or never reached) scores 0 on that side: cannot be
seen is a fail, never a pass. A required judge keeps the task from being VALID until both sides are scored; the reference must pass it, and the start must score every required
item below 0.5 (a `still_works` judge of what still looks as it did must pass at the start too). If a side doesn't,
reword the item or fix the plays so the pictures show the state, never by asking less of the solution
([docs/task-check.md](../../docs/task-check.md), "VALID and INVALID").

### The no-op and the oracle, on your own machine

Before any agent gets a task, the Lab runs two scripted cases of it, and the task check runs both on your machine by
the same rules:

- **The no-op** is the start (`seed.commit`) left untouched and graded as if an agent had handed it in. It must
  **fail**: it fails every required outcome probe (a `seen` probe is never the one that shows it), it earns nothing
  (every check it passes has `"weight": 0`), and it passes every required `still_works` probe.
- **The oracle** is the reference (`seed.reference`) graded the same way. It must **pass every required check** of
  every kind (build, boot, `log_absent`, `file_exists`, every probe, every judge as you score it), and no check of
  either side may be a task error (a check no version of the game can be graded by).

**A task is not finished until both are right**: the no-op fails and the oracle passes, on your machine, after the
task's last edit. Run the oracle side yourself before you submit: a reference that fails its own check with a real
reading (a threshold past what the reference does), or doesn't do what the instruction says, is the task's fault, and
a task with no reference can't be validated at all (the task check never calls it VALID). **Both right is not valid
yet**: a task that passes the no-op and oracle check still fails review when a sentence of its instruction has no
check that decides it ("Every ask has a check", below). Step by step:

1. **Validate the format** after committing on the tasks branch:
   `python <GGF_ROOT>\godot-game-factory\tools\validate-game.py <GGF_ROOT>\games\<slug>`. Fix every `repo: Tasks`
   error first: the task check refuses a task that doesn't validate.
2. **Run the check**, from `<GGF_ROOT>\godot-game-factory`: every task in one background run (the `Start-Process`
   command above), or one task, `python tools\task-check.py <GGF_ROOT>\games\<slug> --task <name>` (repeat `--task`
   for several; a path to a `.json` file checks a task not committed yet). It builds the start and the reference once
   each, plays both with the probe addon and grades the start as the no-op and the reference as the oracle.
3. **Follow it** in `<GGF_ROOT>\games\<slug>\.task-checks\progress.txt` until it says `finished`. Each task gets one
   line, `VALID <name>` or `INVALID <name>: <reasons>` (`ERROR` when the checker couldn't check it); the exit code is 0
   only when every task is VALID.
4. **Read the task's result**, `.task-checks\<name>.json`: `verdict`, `reasons` (why INVALID, one line each), `notes`
   (the oracle's failures that decide nothing: checks that aren't required), `probes` (each probe's `start` and
   `reference` measure, its `threshold`, `start_passed` and `reference_passed`), and `start_checks` /
   `reference_checks` (every check's row on each side, with its `detail`). Then the evidence of each play,
   `.task-checks\<name>\start\<play>\` and `reference\<play>\`: `probe.json` (the samples and `inputs_missed`),
   `probe.log` (what each teleport, click, touch and stage reached), the screenshots `shot_NN.png` and `play.log`
   ([docs/task-check.md](../../docs/task-check.md), "Results").
5. **Answer what the check can't**: every `judge` (`judge-shots\`, above) and every `seen` probe (`seen-shots\`,
   [docs/task-check.md](../../docs/task-check.md), "VALID and INVALID"), blind first. A required one decides nothing
   until both sides are answered.
6. **Fix and run again** each task that isn't VALID (`--task <name>`), and run again every task you changed after its
   last VALID check, however small the change. Never make the task easier to get there (section 1).

What each verdict means:

| verdict | meaning |
|---|---|
| `VALID` | the task has a reference, the no-op fails and earns nothing, the still-works probes pass at the start, the oracle passes every required check, every probe has a threshold and no weighted one reads the same on both sides, no task error, every required judge has plays of its own, every required judge and `seen` probe answered and agreeing |
| `INVALID` | one of those doesn't hold: `reasons` says which; the task doesn't ship as it is |
| `ERROR` | the checker couldn't check it (a commit not fetched, LFS objects missing, no Godot, no desktop of its own): fix that and run again; it says nothing about the task |

What each failure means and what to do (the exact lines and more fixes: [docs/task-check.md](../../docs/task-check.md),
"Common reasons and fixes"):

| the check says | it means | do this |
|---|---|---|
| `start already passes every required probe`, `start already passes required probe X` | the no-op passes: the checks don't detect the change (the play never reaches the moment, or the measure doesn't see the issue) | compare both sides' `probe.json` for that measure; give the probe a play that reaches the moment and a measure the change moves |
| `a no-op scores N, not 0: give X "weight": 0` | doing nothing earns reward | give the named checks `"weight": 0` (builds, boots, still-works, anything true at the start) |
| `start fails still-works X` | the probe is broken: what still works fails where it works | fix the probe's select, play or window, never the threshold |
| `reference fails X: ...` | the oracle fails a required check: the check or the reference is wrong | read the reference's row and play: a threshold on the wrong side (`op`), a play that doesn't reach the state, a `log_absent` pattern or `file_exists` glob the reference itself fails, or a reference that doesn't do the ask (pick another reference, or take the ask out of the instruction) |
| `uncalibrated: ... the reference measured nothing`, `... task error: ... reads nothing even on the task's own fix` | a reference that measures nothing: the select finds nothing there, so no build can pass | select by what the thing does or carries, or by names the start has; read the rows in the reference's `probe.json` and check the play reaches the place |
| `uncalibrated: ... both measure N`, `X has no threshold: ...` | start and reference read the same: nothing to put a threshold between (any probe, required or not, stops the Lab's check) | measure something the change moves, or a literal for a count or a boolean; or drop an optional probe |
| `X reads the same on the start and the reference (N): uncalibrated, never a pass` | a weighted probe that measures nothing the change moves, whatever its threshold | compare both sides' samples; read what the change moves (field, select, play, window), never a looser threshold |
| `no seed.reference: the oracle side can't be played ...` | a task with no reference can't be validated | give it the thread's accepted end as `seed.reference` (section 2) |
| `judge X: no play of its own ...` | a required judge shown only the idle look and the drive, which never reach what it asks | give it `plays` that show each item at its moment |
| `seen X: crops saved ..., answer needed`, `judge X: shots saved ..., answer needed` | the check can't decide it without you | answer it blind (step 5), then check again |
| `no samples in the window (the play ended at N s)`, `a stage of the play didn't land`, `... an input did not land ...` | a play that never reaches its moment: it ended early, a stage found nothing, a click or touch found no control | read `probe.log` and `inputs_missed`; drive the play as a player would (the start control by the text the instruction quotes, a wait for the scene, a stage on something both sides have) |
| a value just past its threshold, `... did not go as its first play`, a crop you can read only with a `?` | an unsteady reading: a window at the edge of the event, a sample at a moment that moves, text that changes while the shot is taken | read the samples, not only the reduced value; move the window into the steady part of the event, read a quantity with a clear gap between the sides, take the shot at a still moment; never ease what the instruction asks |
| `reference fails X: packaging failed ...`, `... packaged, but the packaged game didn't run cleanly` | the release export wasn't made (the engine's error, no `Windows Desktop` preset, or a machine without the release export template), or its player crashed or stopped before its time | read `reference/package/package.log` or the `packaged` play's log; fix the game's `Windows Desktop` preset or the crash; install the templates with `machine\get-godot.ps1` |
| a judge's or a `seen` probe's picture doesn't show what its rubric asks (the reference's own picture included) | the play doesn't produce that picture: it ends before the moment, the shot is taken too early or too late, or the game never puts the asked thing on screen | rewrite the play, its inputs and its shot moments, until it produces that picture every time (a `shot` with `when` where the moment moves between builds); or edit the game so the asked thing really appears on screen; never drop the check, point it at something else, or loosen its rubric |
| `<side>: the route X was NOT played: ...` (a judge's notes) | the judge's route file isn't in the reference, or isn't a route | score only what the pictures show; nothing stands in for the route |
| `X is a required code_judge`, `no required probe outside still_works but seen ones` | a check nothing here can run, or no outcome probe for the start to fail | make code review `"required": false`; add a required probe of the outcome |

### Every ask has a check

Before the game is packaged, read each task you wrote, its instruction against its checks, yourself; no tool or
reviewer does this for you. Lab reviews every task the same way at submission and sends the game back when an ask has
no check at all, naming the task and the sentence. Lab may repair a check itself, without sending the game back, where
the instruction already says what the check needs: it restages a play with the steps the instruction gives a player,
moves a window or a judge's frames to the moment the plays recorded, retargets a select to what the instruction names,
clicks the start control by the text the instruction quotes (or waits, or plays from the scene the instruction
states), reads from the screen a property that came back empty, and removes a click repeated after its
action already happened. The check's measure and threshold stay as written. Fix
what you find in the task before it is packed:

- **Go through the instruction sentence by sentence, the title too** (the solver is given both). The game's
  description, the controls line and the art line are context, and so are a bug report's cause and steps to
  reproduce; they ask nothing. A sentence that would be equally true in every task of the game is context. What
  should now be different is an ask; what must stay as it is is a keep.
- **In a bug report, the expected behaviour is the ask only when it is as broad as the symptom.** With no "expected"
  sentence, or a narrower one, the symptom's no longer happening, under the reported conditions, is the ask and needs
  a check.
- **A check covers an ask by what it reads**: its select, field, window, threshold and play. Its `describe` is a
  label; one that claims more than the measure reads covers nothing more. Write each ask's check plainly its own: its
  `describe` or rubric item in the ask's own words, its play reaching the moment the ask is about.
- **An ask about time or many cases needs checks that match it.** "Stays until", "never", "for as long as",
  "whatever the player does" need a window over that span (one instant covers it only in part); in a bug report such
  words mean under the reported conditions, so the play runs past the moment the symptom showed. "Every" or "each"
  means each case listed gets a check of its own.
- **Every ask has a check that would fail if that ask alone were not done**: a required probe for each key, direction,
  scenario or case it lists; a number it states held on both sides; a look-and-feel ask as a required
  `looks_as_asked` rubric item in the ask's own words, with the check's own `plays` when the state must be reached
  first; motion as a probe sampled every 0.1 s with `agg` `step`, or a required judge with a run of `shots`.
- **A keep that names a thing** ("the boss bar still starts full") has a required `still_works` check reading that
  thing; a bare "everything else keeps working" is covered by any required `still_works` check.
- **Never cover an ask with an optional probe, a `build`, `boot` or `package` check, or a `"required": false` quality
  check alone.**
- **A rubric item asks exactly what its sentence asks**, in the sentence's own words: never more (a quality, a
  colour, a count the sentence doesn't name), never something else. A judge asking more fails fair solutions; one
  asking something else leaves the sentence unchecked.
- **A look described by a list of items** gets those items named in the `looks_as_asked` rubric, an item each where
  the instruction asks for each on its own: a judge asked only about the whole look passes a build that leaves one
  out.
- **A check is never tied to the reference.** Ask of each required check: would a correct solution that names its new
  things otherwise, lays its scene out otherwise, words on-screen text otherwise where the instruction doesn't quote
  it, or hides a thing where the reference removed it (or the reverse), still pass? A name, text, place or input
  sequence only the reference has, and the instruction doesn't give, ties it: move the check to what the player sees.
  So are a click or a tap at fixed screen coordinates on a control (click it by its caption or name), a teleport to
  where the reference put something (`teleport_to` the thing), and a count of the parts one build is made of (its
  nodes, lights, meshes, scripts): drive by the player's controls, measure the outcome.
- **A contact ask is staged, never left out.** An ask that shows only after a contact (a blow landing, getting hit,
  a stun, the last foe of a group falling) is never dropped because "no fixed play guarantees the contact": `pin`
  the foe or the target ahead of the player and press the task's own attack key or touch; `set` a health the start
  names, only to set the fight up; `damage` for a hit taken at a known moment, through the game's own
  `take_damage`; `where` to pick the live ones (docs/task-probes.md, section 1.4). Read the result
  deterministically: a state change in a probe one sentence explains (a `prop:` of the node holding health, state
  or phase, `damage_taken`); a hit stop by `frozen` of the one struck ("the one struck freezes"), by `world` `flow`
  only when the ticket itself says the whole game holds, and `time_scale` only when it says time slows, never a judge (no screenshot shows it) and never
  paired with `paused` == 0 unless the ask says so (a build may stop by pausing the tree); a stagger, a knock-back
  or an interrupted action by the animation that plays (`clip`, `anim:`), the node unable to move with the move
  key held, then moving again, or its distance from the attacker, never a judge. What
  it looks like (sparks, colours, glow, readability) goes to the required visual judge on named frames across the
  contact. Names come from the start commit; `set` and `where` only on members the task does not ask to change. A
  target the build invents is pinned as the nearest body that draws near the player; where that is not surely the
  target, list the ask as not testable. A stage that took nothing fails every probe of its play (the task check
  says "a stage of the play didn't land"): read the fix's `inputs_missed` and `probe.log`.
- **Hints, never answers.** An instruction may hint, in the ticket's own words, at what a player
  must see, hear or meet, or what must exist in the world, and may say that hits go through the game's damage
  method. It never says how the build names or stores it: no class, variable, function, group, node, asset or file
  name, nothing that is really the check's read target dictated to the solver. Names a check uses come from the
  start commit.
  - Good: "Every blow that lands throws sparks and a short pause." "A training post stands in the yard to practise
    on." "Hits reach her through the game's damage method."
  - Refused: "Add a node called TrainingPost to the yard." "Keep the enemy's health in a variable called health."
    "Put each generator in the group generators so QA can find it."
  _(why: a name the check reads, written into the ticket, hands the solver the answer; when only such a name would
  make a check work, move the check to what the player sees)_
- **A sound ask** is checked by a sound starting when the event happens: `audio` `started_audible` in a window
  right after the event (a margin of one sample at each end), picked by `owner` or `sound_class` where the start
  has them; `sounds` or `repeats` (by the stream's file name) when the ticket asks for distinct sounds, "each gun
  has its own sound". Use `near` only when the ticket itself asks for a sound placed in the world: most sounds play
  on a plain `AudioStreamPlayer`, which is near nothing, and a fair solution would fail. `repeats` cannot grade a
  build that picks its takes with an `AudioStreamRandomizer` (no value there), and a game with a polyphonic sound
  manager is graded by `level`: its voices are not seen to start. A fade or music is read by `audible`, `volume`
  or `level`, since `started_audible` is judged as the sound starts. What the sound is, how it sounds, is never
  checked. Games import every sound (godot-game-session skill), so every sound has a file name.
- **An ask about how the work is built or documented needs no check** ("fix it at its cause", "keep the figures in a
  data table", "add it to the README"): no check of the game's outcome can decide it. Anything about what the player
  sees, hears or can do is never such an ask, however it is worded.
- **Exactly five kinds of sentence need no check**, because the grader cannot run them: an exported or packaged
  build's own behaviour; given screen sizes or resolutions (the size itself: what must be visible on screen still
  needs a check); a frame rate or performance on given hardware; how a sound sounds; a statement of what the task does
  not add or change. Everything else stays an ask, however hard to check: a value the running game holds, a timing, a
  random or rare event, something a play must set up first, something saved and found again (a play that names the
  play that saved in `after` starts on its saved data). When in doubt, it is an ask.
- **A sentence no check can verify as written is reworded, never left unchecked**: say instead what the reference
  demonstrably does and a check can decide, so the task asks as much as before ("every exit stays reachable" becomes
  the exits a play walks through). A sentence that can be checked is never dropped. The instruction stays plain
  prose, never fields.
- **A `still_works` probe never calibrates.** What still works reads the same on the start and the reference, so a
  calibrated threshold has nothing to sit between: use a literal, or a threshold relative to the start.
- **A check's name says what it decides** (`hud_shows_ammo`, not `check3`): the result files and every reader of the
  task go by it.

### When a picture doesn't show what is asked

A visual check (a judge, a `seen` probe) that fails because its picture doesn't show what its rubric asks is fixed at
the picture, never at the check:

- **Rewrite the play so it reliably produces that picture.** Change its inputs and its shot moments until the asked
  thing is on screen in the shots, on the start and on the reference, run after run. Where the moment moves between
  builds or machines, take the shot when the thing is there (`when`), not at a fixed second.
- **Editing the game is allowed too**, when the asked thing never really appears on screen: make the game show it
  and commit that as any other work; the task's reference is then a commit that has the change.
- **Never drop the check, repurpose it or loosen its rubric.** A rubric item that the instruction's own words decide
  keeps those words: no "wording may vary" against an instruction that names the wording, no "or similar", no item
  quietly pointed at something easier to photograph. A loosened check passes builds that don't do what was asked, so
  the task stops measuring its own instruction.

### Fixing a task that came back

When tasks are returned for a fix:

- **Start from the task files as returned.** They are the current version; an older copy in the session or on the
  `tasks` branch may lack changes made since, and a fix written on it silently undoes them. Put the returned files in
  place first, then edit.
- **Touch only the tasks listed.** A change to any other task ships unreviewed and unasked for.
- **Write a note of what changed and why**, per task, in plain sentences: the check or play changed, what it was,
  what it is now, and the reason. Whoever takes the fix reads the note against the files; a fix without one has to be
  rediscovered by comparing them.
- Every rule of this skill holds for a fix as for a new task: nothing gets easier, and the task check says VALID
  after the last edit.

## 6. Difficulty, limits and what the validator enforces

- `difficulty` is `hard`; a game needs at least 4 `hard` tasks, the others may be `medium`, none easier (a task that
  names no difficulty counts as medium; four is the floor, so aim every task at hard), and `tags` hold `long-thread`.
  It is your own estimate of the thread; our runs of the task decide its difficulty (last item below).
- `limits`: 400 turns, 480 min, 150 USD, 1800 s tool timeout unless the task needs more; a long thread needs room.
- `tools/validate-game.py` fails a game with fewer than 5 tasks or fewer than 4 `hard` ones, and a task that is
  `easy`, has no `seed.reference`, has fewer than 3 required probes of weight above 0
  outside `still_works` (a required probe of weight 0 is a guard, not an outcome), or whose reference changes fewer than 5 game files, fewer than 100 code lines or fewer than 2
  systems against its start; for a seed on main it also fails fewer than 4 game-changing commits from `seed.commit` to
  `seed.reference`, and any required probe that names a class, group, scene or asset the reference has
  and the start doesn't (section 5). These are floors, not targets: pick the longest threads the history has. It also
  refuses a task without the `long-thread` tag, a weighted check a no-op passes (section 5), a touch that breaks the
  touch rules, a mobile game's play that chooses a renderer or a size, and anything against the format rules of
  section 0.
- **Judge difficulty in the session; never run the task with another agent** (a try takes long and slows contractors
  down). Don't run `tools/task-try.py` or start a fresh Claude Code or Codex session on a
  task. Before committing, review each task against section 1 here, with the person: would a strong agent given only
  the brief and the start solve it easily (25 minutes is a guide, not a cut-off)? It would when the brief points at
  one place, the issues share one obvious cause, or the reference diff is mostly one file or one system. If so, extend
  the thread back to an earlier attempt, merge it with its neighbouring issues, or drop it. Tell the person which
  tasks you judged long enough and why, in a line each. We try every submitted task with a strong agent and measure
  its time; that grade decides.

Probes may measure the cause's effect directly, since the agent never sees them.

Wording: neutral and technical, for the game's people and creatures as for the rest. Describe meshes, bones, poses,
hits and reactions. Never use gore, injury or body-horror words ("crumpled body", "cut neck"); a cloud content
filter rejects such briefs and rubrics.

## 7. What must never reach the agent

The agent sees only the brief and the game at `seed.commit` (a commit of main, so without the tasks branch) as a fresh
repository without history, `Tasks/`, `History/` or `Dataset/` (the harness rule: those hold every task's checks and
the reference fixes). The grader's half (`milestones`: probes, rubrics, questions, `log_absent` patterns; and
`seed.reference`) never reaches it. So:

- the instruction holds nothing of the grader's half and does not describe the fix;
- nothing else at `seed.commit` should spell out the answer (a design-doc "known issues" line naming the cause, a
  comment saying how to fix it): if it does, pick another seed or another task;
- never point the game's code, docs or README at `Tasks/` or the tasks branch.

## 8. Every rule, with its reason

The rules a task is written and checked by, each in one line with why it holds. The sections above say how; this is
the list to go through before a task is committed. Rules tell how to write and check a task; none of them gives a
task's solution.

**The task**

| rule | why |
|---|---|
| Every task is a long thread of multiple edits from the game's real history, never a single fix or a single commit | a task an agent finishes in minutes measures nothing |
| A game ships at least 5 tasks, at least 4 of them `hard`, the others `medium`, none `easy`; every task carries the `long-thread` tag | the bar is what a strong agent can't solve easily, and the floor is checked per game |
| At least 3 required outcome probes per task, outside `still_works`, each of weight above 0 and none a `seen` probe | each issue of the thread is graded on its own, so partial work earns partial credit |
| `seed.reference` is always the game's own accepted end of the thread, and it does every ask, in a place a play can reach | the checks are proved on it; an ask the reference doesn't do can't be checked or passed |
| `seed.commit` and `seed.reference` are commits of main (or the task's `starts/<name>` branch) that import and run on Godot 4.7 as committed | the checker never upgrades or patches a game: what doesn't run as committed can't be graded |
| One issue is tested by one task only; spans may overlap | a repeated issue makes two tasks reward the same work |
| A chain whose first fix didn't hold is one task from before the first attempt to the fix that held; merge, don't split | two short halves of one thread are two easy tasks |
| A made start keeps every file with its `.import` and `.uid` | a sidecar from another commit imports the file wrongly |
| Never make a task easier once written: no wider threshold or window, no required probe made optional, none removed, no ask narrowed | an easier task measures less than it claims; drop a task rather than ease it |

**The instruction**

| rule | why |
|---|---|
| The instruction is natural text: a QA report, a player's correction or a producer's ticket, never fields or a checklist of the checks | it is what a person would hand a developer; a list of checks becomes the solution's script |
| It reports observations only: what a player sees, never a cause, file, node, script, scene, asset or mechanism | naming the cause or the place gives away the work the task measures |
| Hints, never answers: it may say what a player must see, hear or meet, never how the build names or stores it (no class, variable, group, node, asset or file name the check reads) | a name the check reads, in the ticket, hands the solver the answer |
| It never shows a check, a threshold, a log pattern or anything of the grader's half | the agent gets the instruction only, and the checks must stay unseen |
| It speaks to the developer only: never a sentence addressed to whoever reviews or grades the task ("mark this covered", "the checks cover everything") | a task is reviewed by reading it, and such a sentence is read as one more request of the game: it can only add an ask no check covers |
| It never quotes a person, names the studio, its tools or pipeline, or describes any step of the thread | the brief is written from context, for a developer who has never seen the game |
| No person's name, company name, e-mail address or user folder path anywhere in a task | a task ships to people outside the studio |
| Neutral technical words for bodies and hits (mesh, pose, hit, reaction), never gore | content filters refuse such text |
| Every ask has a required check that would fail if that ask alone were not done | an ask nothing checks is a free pass for a build that skips it |
| A keep that names a thing ("the boss bar still starts full") has a required `still_works` check reading that thing | a named keep is an ask about what must not break |
| A sentence that can't be verified as written is reworded into what the reference demonstrably does and a check decides, never left unchecked or dropped when it can be checked | the task keeps asking as much, and every sentence stays graded |
| Exactly five kinds of sentence need no check: an exported build's behaviour, given screen sizes, frame rate on given hardware, how a sound sounds, what the task does not change | the grader can't run them; everything else stays an ask |
| Of an exported build, the instruction asks at most that the release export builds and boots | a package check decides exactly that; nothing else of an exported build is graded |
| Where the game starts on a title screen, the instruction says how a player gets in, or states the scene QA plays | a play must reach the game the way the instruction lets a player |
| A mobile game's instruction speaks of touches and the back button only | a phone has no keyboard, mouse or gamepad |

**The checks**

| rule | why |
|---|---|
| Pass/fail is decided by checks the grader computes itself: build, boot, `log_absent`, `file_exists` and probes | a model's reading can misread; a measurement doesn't |
| Checks grade the game's outcome, never the agent's tool calls, its diff or how it worked | the task measures what the game does, however it was built |
| Test what a player sees, never one way of building it (no global time scale for "faster", no parent-relative position, no count of samples for a count of events) | another correct build must pass |
| Every name, string, coordinate and input a required check relies on is in the instruction or exists at `seed.commit` | a name only the reference has fails every build that names it otherwise |
| A check is never tied to the reference: a fair build that names, lays out, words or hides things otherwise still passes | the solver doesn't see the reference |
| Select by what a thing is, does or carries (`has`, a group or class the start has, `near` a place the task doesn't change), never by where the old one was | a thing the task moves leaves a select aimed at its old place |
| A select takes every node that fits (`Coin*` takes `CoinSpawner` too): select the things themselves by class, group or whole name, and check in the reference's `probe.log` what it reached | a wildcard or a broad select reads, or teleports to, the wrong node |
| `"of": "first"` only over a select narrow enough to pick one node on both sides | matches come in tree order, which a scene edit changes |
| A hidden node matches no select unless it says `"inactive": true` | hidden and gone read alike otherwise |
| A break is read by what changes there (a `prop:` the start names, `changed`, `spread`, `simulating`, the frame) | a dissolve, a swapped mesh or particle debris is invisible to fields that read a whole object |
| `ui` and `widgets` read what is on screen; `"visible": false` only when the check means "exists while hidden" | a build may hide or remove, and both are "not shown" |
| "Shown" is what is on screen, parents included: a node's own `visible` with a hidden parent is not shown | a widget under a hidden panel reads as there while the player sees nothing |
| Text is read from the game's UI first (`ui`, `widgets`); `seen` only for text drawn by a script, a shader or a texture | a node's text is exact; a model's reading of a picture is not |
| A `seen` probe is a visual check, never an outcome: it doesn't count toward the outcome probes, and the start must fail a probe that isn't `seen` | a model's reading can't be the deterministic proof that the start fails |
| A threshold comes from the instruction, from the start or from calibration, never from what the reference happens to pass | a number fitted to one build fails another correct one |
| Where the reference is only one fair way to the outcome, the threshold is relative to the start (`start_times`, `start_plus`), not calibrated | calibration holds every solution to the reference's own tuning |
| `screen` and other pixel readings are never literal: calibrated or relative to the start | pixels differ between GPUs and drivers |
| A `still_works` probe never calibrates: a literal or relative to the start | what still works reads the same on both sides, so calibration has nothing to sit between |
| Every probe has a threshold the start and the reference can make, required or not | a probe that can't be calibrated stops the task's check |
| A probe that carries weight reads differently on the start and the reference, whatever its threshold | the same reading on both sides measures nothing the change moves: uncalibrated, never a pass |
| A value-reading measure names its `of` (`first`, `max`, ...) | `of` defaults to a count |
| A motion that is a number is a probe sampled every 0.1 s with `agg` `step`; a motion that can only be seen is a judge item with many `shots` | five stills can't show an ease or a slide |
| A sound ask is checked by a sound starting when the event happens (`started_audible`, `sounds`, `repeats`), never by how it sounds | how a sound sounds is outside what the grader can decide |
| A contact ask is staged (`pin`, `damage`, `set`) and its result read right after it, never left out | no fixed play is sure to bring a foe within reach |
| Every check the start passes carries `"weight": 0` (builds, boots, `still_works`, anything true of the start) | a no-op must score zero |
| Only the brief's own look-and-feel asks are a required judge (`looks_as_asked`, and a `still_works` judge of what must still look as it did); every other judge is `"required": false` | a judge can misread pictures; required checks must be decided reliably |
| A rubric item is concrete and decidable from the pictures: the start scores 0 on it and any solution meeting the brief scores 1 | a vague item passes or fails on the judge's mood |
| A rubric item asks exactly what its sentence asks, in its words, never more and never something else | a stricter item fails fair solutions; a different one leaves the sentence unchecked |
| An item the pictures don't show scores 0: cannot be seen is a fail | a judge that can't see its subject must never pass it |
| Every judge names plays of its own that show each item at its moment; one subject per judge (a required one without them is refused) | the shared idle play and drive never leave a title screen or press a task's keys |
| A judge's views are the task's own tour (scene loads, `teleport_to` what the build made, view turns, named `shot` inputs), never a view list from the game's files | a build could dress only the spots it lists |
| A look described by a list gets one rubric item per item the instruction asks for on its own | a judge of the whole look passes a build missing one |
| A `code_judge` is never required | a model reads code review, and no check before submission can run it |
| A `package` check asks one thing: the game's release export (its `Windows Desktop` preset) builds, and its player runs 20 s with no crash | that is all a shipped build is graded on, by the same export and play on every machine that checks it; a machine that can't make the export fails the check, never passes it |
| A check's name says what it decides | the result files and every reader of the task go by it |

**The plays**

| rule | why |
|---|---|
| A play does what a player must do to reach the state it probes: the start control by the text the instruction quotes, a wait for the scene | a play that never reaches the moment measures nothing |
| A play lasts up to 1200 s, every time in it too; keep it as short as what it measures allows | a late moment can be played to, and every second is played on both sides of every check |
| A menu or HUD the game paints itself is clicked by a cursor input onto it and a press | the cursor is the game's own mouse, as a player's is; no widget click finds what isn't a Control |
| After typing into a field, a play leaves it by the player's own input before driving the game | a key goes to the focused control first, and a field takes every key it would type |
| No shortcut only the reference has (a flag, a debug key, a scene the fix added) | the start and other builds don't have it |
| `play_args` (and `play_scene` where needed) are always set, and checked to exist at both seeds | every grader play starts from them |
| A place is reached by `teleport_to` or `pin` on a node, never raw coordinates of something a build places | each build places things itself |
| A menu that runs on real time is waited for with a `wait` input | a play's clock runs faster than real time |
| Every check is run on both sides before the task is submitted, and what it measured is read | a guessed threshold or a window that misses the event shows only in the readings |
| A play that reads what another play saved names that play in `after` | every other play starts with no saved data |
| No input on the frame the game resets a state; no teleport past what moves with the player or a limit the instruction gives | the input is lost, or the player arrives without what the moment needs |
| Each action once, while its control is there | a second click on a control that is gone is a miss |
| A click or a tap goes to a control by its caption or name, never fixed screen coordinates | another build lays the screen out otherwise |
| A caption is written exactly as the screen shows it, in the game's own language | it is the words a player finds the control by |
| A click on words that aren't a button's names words shown in one place only | the click is made on the one place that reads them, and words shown twice are a miss |
| A click is marked `disabled` only where the instruction says its control must be disabled | a click on a disabled button does nothing, and the miss says the play's control was not usable |
| A first-launch play may say `"fresh": true`, never with `after` | it states the clean start every play without `after` has |
| A click or a tap on a control only its lists hide scrolls them and lands: never script scrolling for it; a control hidden any other way (a container that clips without scrolling, a list that can't show it), and a drag's control out of view, is a miss whatever `optional` or `disabled` say | a player scrolls a list to what they want, but can't press what nothing brings into view; scripted scrolling is guessed timing another build's layout breaks |
| A control under a dialog, popup or overlay is never clicked or tapped: close it first with the player's own input | the press goes to what is over the control, as a player's would, whatever `optional` or `disabled` say |
| A window whose moment the game decides is tied to it with `since`; a judge's or a `seen` picture of such a moment is taken with `when` | a fixed second misses an event a build or a machine reaches a little later, and a picture taken early shows nothing to judge |
| A click on a control shown only in some states is `optional`, or made in a play that makes that state | every required click must land |
| A play relies on no state it doesn't make: a save, a profile, an expired timer come from its own steps, its `after` plays or the instruction | every play starts from a fresh save |
| A window is timed from the input that sets its event off, with a margin read from the reference's samples | a fixed second misses an event that falls a little later |
| Every input of a task play lands on the reference (`inputs_missed` empty, an optional click that found nothing and a disabled click on its disabled button aside) | an input that misses on the task's own fix makes the task ungradable |
| A budget (`render`) is read in a task play of its own that goes to the view and reads nothing else | other readings and inputs change what is drawn |
| A template game's task sets `play_args` and leaves `play_scene` null; `play_scene` only for a scene no scenario loads | naming the scenario's scene too loads it twice |
| One finger's touches are at least 0.1 s apart; controls are touched by name | a touch that begins before the last lifts misses; a place differs between orientations, a name doesn't |

**The check of the task**

| rule | why |
|---|---|
| The no-op (the untouched start) fails every required outcome probe and earns nothing | a task the unchanged game already passes rewards no work |
| The oracle (the reference) passes every required check, of every kind | a required check the reference fails is one no solution like it can pass |
| Every required `still_works` probe passes at the start | a still-works probe that fails where the game works is broken and would fail every solution |
| No check is a task error: no select that reads nothing (or only empty values) on the reference, no task play whose input misses there | no version of the game could be graded by such a check |
| The task has a reference, and you run its oracle side before submitting | a task with no reference, or one whose reference fails its own checks, can't be validated |
| Passing the no-op and oracle check is not enough: every sentence of the instruction has a check that decides it | a sentence no check decides passes every build that skips it, whatever the two checks say |
| Required judges and `seen` probes are answered blind, from the pictures the check saves, before the task is called finished | the check asks no model, so your blind answer stands in for it |
| A visual check whose picture doesn't show what is asked is fixed by rewriting its play (inputs, shot moments, a `when` shot where the moment moves) or by editing the game so the thing appears; the check and its rubric are never dropped, repurposed or loosened | the picture was wrong, not the ask: a looser check passes builds that don't do what the instruction says |
| A rubric keeps the wording the instruction names: no "wording may vary" against a named wording | the instruction is what the agent is told; a rubric that accepts something else grades a different task |
| A fix of a returned task starts from the files as returned, touches only the tasks listed, and comes with a note of what changed and why | the returned files are the current version, other tasks were not asked for, and a change nobody described has to be found again by comparing files |
| A task ships only when the task check says VALID after its last edit, however small the edit | a check passed before an edit proves nothing about the task after it |
| Judge a task's difficulty in the session; never run it with another agent | a try takes long; every submitted task is tried and measured anyway |

## 9. Examples

One whole task, to show the file format and the probe style only. Its game and its commits are made up, so it has
never passed the task check: copy its shape, never its names or thresholds.

```json
{
  "name": "harbor-run-corr-chase-camera-and-lap-count",
  "title": "The chase camera crowds the boat and the lap count never changes",
  "instruction": "QA played scenario 2 (the harbor circuit; W and S throttle, A and D steer) and reports three things.\n1. The camera rides so close behind the boat that the course ahead can hardly be seen. It should sit well back and above the boat.\n2. In turns the quay and the moored boats cut off the view of the boat. The boat should stay in clear view all the way round.\n3. The lap count at the top of the screen stays at LAP 1/3 after the boat rounds the last buoy. It should show the lap the boat is on.\nSteering, throttle and the rest of the HUD must keep working as they do now.",
  "engine": "godot-4.7",
  "seed": {"game": "harbor-run", "kind": "correction",
           "commit": "1111111111111111111111111111111111111111",
           "reference": "2222222222222222222222222222222222222222"},
  "play_scene": null,
  "play_args": ["-scenario", "2"],
  "difficulty": "hard",
  "tags": ["long-thread"],
  "limits": {"max_turns": 400, "max_minutes": 480, "max_usd": 150, "tool_timeout_seconds": 1800},
  "milestones": [
    {"name": "builds", "checks": [
      {"name": "project_builds", "kind": "build", "weight": 0}]},
    {"name": "boots", "checks": [
      {"name": "boots_clean", "kind": "boot", "seconds": 60, "weight": 0, "needs": ["project_builds"]},
      {"name": "no_script_errors", "kind": "log_absent", "pattern": "SCRIPT ERROR", "weight": 0, "needs": ["boots_clean"]}]},
    {"name": "fixed", "checks": [
      {"name": "camera_back_from_boat", "kind": "probe", "weight": 3, "needs": ["boots_clean"],
       "describe": "While the boat is driven, the camera stays well back from it instead of riding just behind it.",
       "play": "drive",
       "measure": {"probe": "camera", "field": "distance", "window": [8, 21], "agg": "mean"},
       "expect": {"op": ">=", "calibrate": 0.5}},
      {"name": "boat_stays_in_view", "kind": "probe", "weight": 2, "needs": ["boots_clean"],
       "describe": "Through the whole drive nothing stands between the camera and the boat.",
       "play": "drive",
       "measure": {"probe": "camera", "field": "occluded", "window": [2, 21], "agg": "max"},
       "expect": {"op": "<=", "value": 0}},
      {"name": "lap_count_updates", "kind": "probe", "weight": 3, "needs": ["boots_clean"],
       "describe": "After the boat is put beside the last buoy and driven on past it, the HUD shows lap 2 of 3.",
       "play": {"name": "round_last_buoy", "seconds": 12,
                "inputs": [{"t": 2, "teleport_to": {"name": "Buoy3"}, "distance": 4, "hold": 1},
                           {"t": 4, "key": "<Keyboard>/w", "press": true},
                           {"t": 9, "key": "<Keyboard>/w", "press": false}]},
       "measure": {"probe": "ui", "select": {"kind": "text"}, "field": "text", "match": "LAP\\s*2/3", "of": "any",
                   "at": "end"},
       "expect": {"op": ">=", "value": 1}}]},
    {"name": "still_works", "checks": [
      {"name": "boat_still_moves", "kind": "probe", "weight": 0, "needs": ["boots_clean"],
       "describe": "The boat still travels under the drive's keys.",
       "play": "drive",
       "measure": {"probe": "player", "field": "moved", "agg": "max"},
       "expect": {"op": ">=", "value": 5}}]}
  ]
}
```

`builds`, `boots` and `still_works` carry `"weight": 0` because the start already passes them; the three probes of
`fixed`, one per issue of the brief, carry the weight. The game is a template game, so `play_args` alone start its
scenario. The task play reaches its spot with `teleport_to` a node by its whole name, then drives on. `limits` are
written out: left out, the schema's lower defaults apply. The optional `quality` milestone is left out.
