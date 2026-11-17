---
name: godot-write-tasks
description: 'How to write the tasks a Godot game ships with (Tasks/ on the repo''s orphan tasks branch, never on main, one GameTask JSON per task, 5 to about 10 per game) so an agent can be given them in the game-creation environment: the tasks branch and its worktree, the one bar every task meets (a long thread of multiple edits from the game''s real history: many commits, many files, several systems, at least 4 hard, the rest medium, never easy or a single fix), the four kinds as where a thread comes from, picking seed.commit (the parent of the thread''s first attempt) and seed.reference (its final accepted fix), observation-only briefs, play_scene and play_args, milestones and deterministic probe checks (pass/fail never by pixels; judges only for asked looks; one required probe per issue), validating and the background task check, limits, and what keeps a task gradable and unleaked. Use when a Godot game session writes, moves, checks or reviews tasks, or reads a task check''s result, and before calling a game complete.'
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
   counted. A thread that settled only one observable thing is rarely long enough.
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

**Where strong agents fail.** Most tasks a strong agent missed had the code written and the outcome never checked in
the running game. Prefer threads that settled these, and give each one its own probe in a play that reaches the
moment:

- **Feedback that must show in play**: a HUD readout, a marker, a sound or an effect when the event happens (a play
  that triggers the event, then `ui`, `audio`, `components`);
- **A look change**: colours, materials, dressing, HUD art (a `looks_as_asked` rubric item beside what a probe can
  read of it: `screen` relative to the start, a node's own properties, the `ui`);
- **Menu, pause and back flows**: Escape or the back button closes what it opened and returns where it came from (a
  task play with the keys or touches, then `ui`);
- **A tuned outcome judged in play**: seen or not seen at a distance, holds or breaks under load, passable, winnable
  (a teleport to the spot, then the outcome);
- **Many small requirements in one span**: one probe each, so a single dropped item shows.

Threads that strong agents solve in minutes: one system's logic, a feature whose outcome the code alone shows, a brief
that points at the system. Hiding the list of problems (a brief that reports the symptoms a player meets, not a
checklist) lengthens a run without changing what it misses.

**Finding threads.** Walk the history for clusters: `git log --stat` around a feature, runs of commits on the same
files (`git log --format=%h -- <path>` piled up in a short window), several `user.direction` rows on one topic
(the workflow rows' `"direction"` links), fixes followed by "still", "again", "regressed" or a revert, a renderer or
project-settings change that broke a system and the commits that mended it. Read the whole span before picking
its ends.

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
- Describe the controls the player needs; the harness tells the agent which scene QA plays (`play_scene`).
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
   say `"required": false`, and the task check only notes a `log_absent` the reference fails: read its notes, since
   no solution like the reference could pass one (docs/task-check.md).
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
judge in `still_works` the same way. A judge is shown screenshots of the idle `look` and the `drive` on the task's
start scene and nothing else, unless the check names its own plays. When what must be seen appears only after a
task-specific key, in another scenario or scene, or past a title screen, give the check `plays`: up to 4 task plays
that reach that state (when a probe's play already does, reuse it under its name, written identically):

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
state is on screen at those moments. A play also runs on the task's start (`"before": true`) and on the reference
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
  `<Gamepad>/buttonSouth`; on a mobile game `<Keyboard>/escape` is the phone's back button), mouse movement, the wheel, the cursor, a click
  on a control by its node name, a touch (`tap`, `drag`: below, and docs/task-probes.md section 1.3), a teleport of the player (to a point, or
  `teleport_to` the node a select matches), a wait in real time, a named screenshot (`shot`), a scene load, a view
  turn, and the stages of a contact (`pin`, `damage`, `set`: "A contact ask is staged" below, and
  docs/task-probes.md section 1.4). docs/task-probes.md has each one's form.
- **A play that reads what another play writes names it in `after`. Never rely on the checker's order.** A task play
  that reads a save (a level reached, a profile filled in) lists the plays that write it:
  `"after": ["writes_save"]`, by their names. On each side they run, and end, first, and the reader starts on the
  saved data they left; every other play starts with none. A writer that failed still counts as run, so the failure
  shows in the reader's checks. Of two writers, one names the other in its own `after`. A writer saves during its
  play, or when the game is closed (`NOTIFICATION_WM_CLOSE_REQUEST`, `_exit_tree`): a play ends that way
  (docs/task-probes.md, 1.1).
- **Touches.** `{"t": 2.0, "tap": <spot>, "hold": s, "finger": n}` puts a finger down at the spot and lifts it (after
  `hold` seconds: a long press, a button kept down); `{"t": 2.0, "drag": [<spot>, <spot>, ...], "over": s, "hold": s,
  "finger": n}` moves it through the spots over `over` seconds and keeps it at the last for `hold` (a swipe, a
  slider, a virtual stick pushed over and held). A spot is a point of the screen `[fx, fy]` in fractions from its top
  left, or `{"widget": "<node name>"}`: the centre of the first visible `Control` of that name (a wildcard) or class.
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
    and place; `match` for a text);
  - `screen`: the frame's mean luminance, never a literal threshold;
  - `audio`: the players that play and how loud the listener hears them, the mix's level, and the sounds that
    start, however short (`started_audible`, and by their streams' names `sounds` and `repeats`);
  - `spawns`: nodes of a class appearing and going;
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
probe that names something the start lacks and the reference has. **Test the outcome a player
sees, never the implementation**: another valid fix must
pass ("the hero stands on ground", "the stone breaks the wall piece it hits", "the lap count shows the lap the boat is
on", not "spawn_height is 0.92" or "the function was changed"). `describe` says the assertion in plain
words; it is shown in the grade, never to the agent.

**Everything a required probe or its play relies on is in the instruction or exists at the start commit**: node,
class, group, property and scene names, exact strings and regular expressions, coordinates, input sequences. The
instruction never names how a build stores things ("Hints, never answers", below), so what the thread creates is read
by what the player sees:

- **Prefer what the player sees.** On-screen text through `ui` with a loose `match` (any case, any spacing, `\d+`
  for a number); nodes by a group or class the start has, by what they carry (`has`) or where they are (`near`); a
  place reached by `teleport_to` or `pin` on a node, never raw coordinates; a control by its name at the start.
  Never match an exact string the instruction doesn't quote, and never a run of keys that only works on the
  reference's layout (a menu walked by counting presses).
- **"Shown" means on screen.** `ui` and `widgets` read what is on screen, so a check that something is shown, or no
  longer shown, passes the same on a build that hides a widget as on one that removes it. Write `"visible": false` in
  a widgets select only when the check means the widget exists while hidden.
- **Ask the second-solution question of every check**: would a correct solution that names things otherwise, lays
  the scene out otherwise, or hides instead of removes still pass? If not, move the check to what the player sees. Check names are unique and `needs` only names earlier checks;
calibrated probes, `code_judge` and `"reference": true` judges need `seed.reference`.

A task is valid only when it passes the task check: its start fails the task and its reference fix imports, boots and
passes every required probe, and every required `still_works` probe already passes at the start. **Every check is
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

**The check asks no model, so you answer the judges.** For every `judge` check it plays the check's plays on the start
and on the reference and saves the screenshots the cloud's judge would be shown under
`.task-checks\<task>\judge-shots\<check>\` (`start\`, `reference\`, and a blind copy in `blind\A\` and `blind\B\`
whose sides are in `blind\key.json`), with `ask.md` holding the brief, the question and the rubric; `progress.txt` says
`judge <check>: shots saved for start/reference, answer needed`. Before you call a task with a required judge VALID,
look at the pictures yourself, blind: score every rubric item for A and for B from 0 to 1 first, then open the key
and `sides.md` (each side's own picture count and notes; the blind folders hold only the pictures both sides have).
The start must fail every required rubric item (below 0.5) and the reference must pass every one; if either doesn't,
reword the item or fix the plays so the pictures show the state, never by asking less of the solution. Write both
sides' scores in the task's notes (its `tasks-workflow.jsonl` row).

### Every ask has a check

Before the game is packaged, read each task you wrote, its instruction against its checks, yourself; no tool or
reviewer does this for you. Lab reviews every task the same way at submission and sends the game back when an ask has
no check at all, naming the task and the sentence. Fix what you find in the task before it is packed:

- **Go through the instruction sentence by sentence.** The game's description, the controls line and the art line are
  context, and so are a bug report's symptom, cause and steps to reproduce; they ask nothing. What should now be
  different is an ask (in a bug report, the expected behaviour); what must stay as it is is a keep.
- **Every ask has a check that would fail if that ask alone were not done**: a required probe for each key, direction,
  scenario or case it lists; a number it states held on both sides; a look-and-feel ask as a required
  `looks_as_asked` rubric item in the ask's own words, with the check's own `plays` when the state must be reached
  first; motion as a probe sampled every 0.1 s with `agg` `step`, or a required judge with a run of `shots`.
- **A keep that names a thing** ("the boss bar still starts full") has a required `still_works` check reading that
  thing; a bare "everything else keeps working" is covered by any required `still_works` check.
- **Never cover an ask with an optional probe, a `build` or `boot` check, or a `"required": false` quality check alone.**
- **A contact ask is staged, never left out.** An ask that shows only after a contact (a blow landing, getting hit,
  a stun, the last foe of a group falling) is never dropped because "no fixed play guarantees the contact": `pin`
  the foe or the target ahead of the player and press the task's own attack key or touch; `set` a health the start
  names, only to set the fight up; `damage` for a hit taken at a known moment, through the game's own
  `take_damage`; `where` to pick the live ones (docs/task-probes.md, section 1.4). Read the result
  deterministically: a state change in a probe one sentence explains (a `prop:` of the node holding health, state
  or phase, `damage_taken`); a hit stop by `frozen` of the one struck, or by `world` `flow` when the ask is
  about the whole game (`time_scale` when it says time slows), never a judge (no screenshot shows it) and never
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
  _(failure: tasks were reworked by writing the check's read target into the ticket, which hands the solver the
  answer)_
- **A sound ask** is checked by a sound starting when the event happens: `audio` `started_audible` in a window
  right after the event (a margin of one sample at each end), picked by `owner` or `sound_class` where the start
  has them; `sounds` or `repeats` (by the stream's file name) when the ticket asks for distinct sounds, "each gun
  has its own sound". Use `near` only when the ticket itself asks for a sound placed in the world: most sounds play
  on a plain `AudioStreamPlayer`, which is near nothing, and a fair solution would fail. `repeats` cannot grade a
  build that picks its takes with an `AudioStreamRandomizer` (no value there), and a game with a polyphonic sound
  manager is graded by `level`: its voices are not seen to start. A fade or music is read by `audible`, `volume`
  or `level`, since `started_audible` is judged as the sound starts. What the sound is, how it sounds, is never
  checked. Games import every sound (godot-game-session skill), so every sound has a file name.
- **Nothing is asked that the grader cannot run.** Saving across sessions can be checked: a play that names the
  play that saved in `after` starts on its saved data. What a sound sounds like, how an exported build behaves and
  the frame rate on given hardware cannot: never write them as asks.
- **An ask that cannot be checked fairly** comes out: rewrite the instruction so it no longer asks for it, rather than
  ship an ask nothing checks. The instruction stays plain prose, never fields.

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

## 8. Pitfalls already hit

| pitfall | rule |
|---|---|
| checks or log patterns shown in the brief | the agent gets the brief only |
| an ask that shows only after a blow or a hit left without a check, since no fixed play is sure to reach the foe | stage the contact (`pin`, `damage`, `set`) and read the window right after it (section 5, "A contact ask is staged") |
| an ask in the brief that no check reads, so Lab sends the game back | read each task against its checks before packing (section 5, "Every ask has a check") |
| a model judge misread screenshots and failed a correct fix (or passed a wrong one) | required probes for what can be measured; only the brief's own looks in a required judge (`looks_as_asked`, still-looks in `still_works`), each item concrete and decidable from the screenshots; every other judge `"required": false` |
| a judge was shown only the title screen, or never the state a task's own key opens | the `judge` check names its own `plays` that reach it (section 5) |
| five stills couldn't show whether a move eased or feet slid | a number: a probe sampled every 0.1 s with `agg` `step`; only seen: a `looks_as_asked` item with a short play and `shots` (section 5) |
| a fix made only in a scene or a resource failed a code review | the cause is checked by its measured effect (a probe), never by reading the diff |
| a pixel threshold moved between GPUs | the frame's luminance (`screen`) only calibrated or relative to the start, never a literal |
| a hidden panel still counted as shown | a hidden node (or one under a hidden node) matches no select unless it says `"inactive": true`; `ui` and `widgets` read only what is on screen (`"visible": false` in a widgets select takes hidden ones too) |
| a sound judged by its player node existing, not by what the player hears | `audio`: the players playing at their volume at the listener, and the mix's `level`; volumes and level calibrated or relative to the start |
| a play that reads a save ran on clean saved data and read nothing (a later level not yet unlocked, an empty profile) | the reading play names its writers in `after`; every other play starts clean (docs/task-probes.md, 1.1) |
| a teleport to fixed coordinates missed what each build placed itself | `teleport_to` an object select (nearest match), facing it or a point |
| a `teleport_to` by a `name` wildcard (`Coin*`) went to the `CoinSpawner` beside the player, not to a coin | a select takes every node that fits, and `teleport_to` the nearest: select the instances by their own class or whole name when the start has them too, by what they carry (`has`) when the task adds them, and read `probe.log` in the reference's play |
| a select by class or group also matched the scene's other nodes, or named the class the reference happened to use | select by what the node carries (`has`), `near` a point, or a property (`where`) |
| `"of": "first"` over a broad select read another node on the reference (the scene was edited) | matches come in tree order, which a scene edit can change: select by name, group or `near` |
| a value read with the default `of` came back as a count | a measure that reads a value (a position, a `prop:`, a text match, a percent) needs `"of": "first"` or another value reducer |
| a menu that runs on real time never reached its later pages in a play | a task-play input `{"t": ..., "wait": seconds}`: the play's clock holds while the game runs on in real time |
| a main scene set up what the play needed, and the play opened `play_scene` instead | start such a game through its own `play_args` with `play_scene` null (section 4) |
| a template game's task named the scenario's scene in `play_scene` and the scene loaded twice | `play_args` alone, `play_scene` null: the `Scenarios` autoload loads the scene |
| a touch named a control by a name that differed in the other orientation, or by the default `Button2` | controls have names of their own (godot-mobile-game skill); tap by `{"widget": "<name>"}` |
| a second touch of the same finger began before the first had lifted and missed on every run | 0.1 s between one finger's touches, or give the second touch another `finger` |
| a budget read in a play that also toured, clicked and took other readings | a `render` check gets a task play of its own |
| a mobile game's play asked for a key or the mouse | touches and the back button (`<Keyboard>/escape`) only |
| a probe that isn't required but passes at the start carried weight | every check the start passes takes `"weight": 0`, a `"required": false` probe too |
| a probe that tests the reference's implementation ("spawn_height = 0.92") | measure the outcome; another valid fix must pass |
| the brief said "scenario 1" but the task had no `-scenario 1` | `play_args` (and `play_scene` where needed) always set and checked at the seed |
| a break read where these fields don't see it: a shader or material dissolve, a mesh swapped for one with the same box, a 2D part faded by `modulate`, debris made only of particles | read what changes there: a `prop:` the start names, the frame, the effect (docs/task-probes.md, section 5) |
| a control or class name guessed | read the names from the code and scenes at `seed.commit` |
| a probe matched an exact on-screen string, or a play walked a menu by counting key presses, that only the reference's layout gives | a loose `match` on what `ui` reads, a click or touch on a control the start names; never a string the instruction doesn't quote |
| a "no longer shown" check read a widget the build had hidden, not removed | `ui` and `widgets` read what is on screen; `"visible": false` only when the check means "exists while hidden" (section 5) |
| a check written without running the game: a guessed threshold, a window that missed the event, a judge asked for what the reference never shows | run every check on both sides and read what it measured before submitting (section 5) |
| an ask the reference never does, or does where no play reaches | the reference does every ask, in a place a play can reach |
| a probe named a class, group or scene only the reference had, so a fair build that named it otherwise read as absent | select what the thread creates by what it does or where it is; the validator refuses a reference-only name |
| a run wrote the feature but never ran the game to see it, and the task had no probe of the moment | a play that triggers each piece of feedback, and a probe of what the player sees then |
| a judge's pictures came from views the game itself lists, so a build could dress only those spots | the task's own tour: scene loads, `teleport_to` what the build made, view turns, named `shot` inputs; never a view list from the game's files |
| quoting the person | write from context |
| a reference that crashed | the reference must import and run |
| tasks solved in minutes: one cause, one place, the brief named the system | only long threads of multiple edits, compound probes, observation-only briefs (section 1) |
| a chain split into two short tasks | one task from before the first attempt to the fix that held |
| a bug that never shows in the grader's plays | a scenario or a task play that triggers the moment |
| a brief rejected by a content filter (injury wording) | neutral technical words: mesh, bones, pose, hit, reaction |
| a reverted file kept its newer `.import` or `.uid` | a file and its sidecar always move together |

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
