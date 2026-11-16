# Game format v1

The final format of a Godot game: its **repo** at the release commit and its **dataset** (`Dataset.zip`, layout
`godot-dataset-layout/v1`). It is the same for every game, desktop or mobile, whether a game session here made it or a
contractor delivered it. What the RL environment needs from a game (tasks that start from any commit, the person's
directions, the brief) is in it.

| Machine-readable | What |
|---|---|
| [game-format-v1.json](game-format-v1.json) | the rules for the repo and the dataset (this page in JSON) |
| [dataset-layout-v1.json](dataset-layout-v1.json) | the dataset's entries, names, video format, manifest keys, README sections |
| [schemas/dataset-manifest.schema.json](schemas/dataset-manifest.schema.json) | `manifest.json` |
| [schemas/workflow-row.schema.json](schemas/workflow-row.schema.json) | one row of `workflow.jsonl` (`godot-workflow/v0`) |
| [schemas/replay-report.schema.json](schemas/replay-report.schema.json) | `ReplayScripts/Verification/report.json` |
| [schemas/assets-manifest.schema.json](schemas/assets-manifest.schema.json) | the repo's `assets.manifest.json` (one format for every game) |
| [schemas/game-task.schema.json](schemas/game-task.schema.json) | one task (`GameTask`, game-task/1; probe checks: [task-probes.md](task-probes.md)) |

## Validate

```bash
python tools/validate-game.py <games>/<slug>
```
```bash
python tools/validate-game.py --dataset <path to Dataset.zip>
```

The first checks the repo and its tasks branch, then its `Dataset/` and `Dataset.zip`; the second checks a dataset
alone, the way a consumer receives it. Both run `tools/validate-dataset.ps1` (layout, sizes, sha256, videos) on
Windows. Verdict **VALID** or **INVALID** (exit 0 / 2); warnings never change it. After the verdict it prints one line
per finding: `x` an error, `!` a warning, `-` a note, then what it is about (`repo`, `repo: README`, `repo: Tasks`,
`contract`, `sound`, `mobile`, `dataset`, ...). Options: `--quick` (do not unpack the history), `--no-hash`,
`--no-layout`, `--no-zip` (skip the repo's `Dataset.zip`), `--json <file>`, `--quiet` (print only errors and
warnings), `--rules-only` (only the rules `contract`, `sound` and `mobile`, what the packager checks first). Standard
library Python 3.10+.

```bash
python tools/validate-game.py --platform <folder>
```

prints the platform of the game in that folder, one line: `desktop`, `mobile landscape` or `mobile portrait` (exit 0).
For a `Platform.json` that says anything else it prints the reason on stderr and exits 2. It reads nothing but that
file ("Platform", below).

## Package

```bash
python tools/package-dataset.py <slug>
```

Builds the dataset of the game at `<root>\games\<slug>` from its repo at the release commit (`--commit <rev>`, default
`HEAD`), its recording `<root>\.recording\<slug>\` and the release's player, recordings and creation replay: the
pipeline's release build (`<root>\builds\<slug>\<sha8>\`, else the repo's `Build\` from `Scripts\godot.ps1 build`),
the first valid recording of the release commit for each scenario (`<root>\recordings\<slug>\`) and
`<out>\_replay\<slug>\<sha8>\ReplayScripts\` once `READY` is beside it. It writes `<repo>\Dataset.zip` (status
`complete`) when the release has a gameplay video, the replay and its player, `<repo>\Dataset.pending.zip` (`pending`)
while the replay is missing or a mobile game's release has no APK yet, and the repo's `Dataset/` folder, which the
game session commits (with a `.gitattributes` that keeps its files byte for byte as `manifest.json` lists them: no
line-ending conversion, videos and images in Git LFS). A game without a gameplay video is rejected at upload: without
a valid recording of the release commit it packages nothing.

It scrubs every text file of the delivery, then scans: a name left in a text file or a path refuses the package (exit
2). Binary files are never changed: names found in them are listed in `<repo>\.dataset\<slug>.binary-hits.tsv`, and
one inside a string (8 or more printable characters in a row) refuses the package too; `--lenient-binaries` lists
them without refusing, to review a refusal. A pipeline build whose leak scan found anything, and a pipeline job working
on the game, refuse it as well. It checks the rules `contract`, `sound` and `mobile` first and ends with the dataset
checks of [Validate](#validate); an error in either refuses the package. It never commits and never changes the game
repo's history; its scratch and reports are in `<repo>\.dataset\`. Options: `--repo <folder>` (a game repo
elsewhere), `--commit <rev>` (`milestone`: the newest `milestone/autoplay-<n>` tag), `--version <n>`,
`--build <folder>` (a pipeline build folder or a player folder), `--replay <folder>` (the replay's package folder),
`--exclude-runs <run ids>`, `--brief <file>` and `--design <file>` (else the release commit's `Brief/brief.md` and
`Brief/design.md`), `--tasks-ref <ref>`, `--exclude-sessions <ids>`, `--recording <folder>`, `--out <folder>`,
`--lenient-binaries`, `--reviewed-hits <tsv>`, `--lfs-unpatchable-use-head`, `--no-repo-dataset`, `--no-zip`,
`--dry-run` (print what would go in, write nothing); and beside packaging `--rescan <zip or folder>` (scan a delivery
again), `--scrub-dir <folder>` and `--self-check`. Standard library Python 3.10+, `git` and `git-lfs`. What it does,
entry by entry:
[godot-pipeline.md, Dataset packager](godot-pipeline.md#dataset-packager).

## The repo

Everything needed to rebuild the game from the repo alone, tracked in git (binaries in Git LFS):

| Path | Rule |
|---|---|
| `project.godot` | the project: its name, main scene (`run/main_scene`, a committed scene), renderer, window size, autoloads and input map; `config/features` names Godot `4.7` |
| `export_presets.cfg` | the export presets: `Windows Desktop`, and `Android` in a mobile game |
| `scenes/`, `game/`, `assets/`, `addons/` | everything the game is made of: at least one scene (`.tscn`), its GDScript, its art, sound and fonts, its addons (the AutoPlay drop-in `addons/autoplay/` among them); store packs in any folder under `assets/` or `addons/` (e.g. `assets/ThirdParty/<Pack>/`), never git-ignored; **every imported file with its `.import` and every script with its `.uid`** (below) |
| `steps/` | every generator script that ran (`Scripts/godot.ps1 step`), unchanged after it ran |
| `Scripts/godot.ps1` | from the template |
| `workflow.jsonl` | the creation record, one row per operation, written when it happened (`godot-workflow/v0` rows: ids unique, `seq` strictly increasing, every `"direction"` naming an earlier `user.direction` row) |
| `README.md` | hero image + captioned gallery of 5-7 real gameplay stills, every image committed (no gameplay image is an error; fewer or more than 5-7 is a warning) |
| `Docs/screenshots/` | the README's stills (JPG, LFS) |
| `assets.manifest.json` | every external asset in `assets-manifest/v1` (below) |
| `Docs/ThirdPartyNotices.md` | credits and licences |
| `Platform.json` | a mobile game only ("Platform", below): `{"platform": "mobile", "orientation": "landscape" or "portrait"}`; a desktop game has no such file |
| `.gitattributes` | the template's: every binary type in Git LFS; Godot's text files (`.tscn`, `.tres`, `.gd`, `.gdshader`, `.gdshaderinc`, `.import`, `.uid`, `project.godot`, `.cfg`) stay plain git text. A binary type in plain git, or one of those text types in LFS, is an error; binary content under any other name in plain git is a warning |
| `.gitignore` | the template's: the engine's cache `.godot/`, `/Build/`, `/Logs/`, `/android/` (the Gradle build template the Android export installs) and `/Dataset.zip`, `/Dataset.pending.zip`, `/.dataset/` ignored; nothing the game is made of (`scenes/`, `game/`, `assets/` and `addons/` at any depth, a pack's own `Build/` or `Logs/` folder included, every `.import` and `.uid`, `steps/`, `Docs/`, `Scripts/`) |
| `Dataset/` | the dataset minus `GodotProject/`, `Build/`, `History/` and `Tasks/`, written by the packager ([Package](#package)) and committed by the game session; before the packager's first run the folder stays as the template made it |

Never tracked: `.godot/` at any depth, build output and logs at the root, the `android/` build template, compiled
translations (`*.translation`), signing keystores (`*.keystore`, `*.jks`), secrets; `Tasks/` on main (below).

**Every imported file with its `.import`, every script with its `.uid`.** Godot keeps a sidecar beside the files it
manages: `<file>.import` for a file it imports (an image, a sound, a font, a model, a translation table), holding the
file's uid and its import settings, and `<file>.uid` for a file it loads as it is and that has nowhere to keep a uid
of its own (a `.gd`, a `.gdshader`, a `.gdshaderinc`, and the formats loaded without importing: `.dds`, `.ktx`,
`.ktx2`, `.ogv`). Scenes and resources refer to files by uid. So every such tracked file has its sidecar tracked (a
file without it gets a new uid on the next import and what refers to it by uid breaks; an imported file also loses
its import settings), and every tracked sidecar has its file (one without is an orphan: delete it, or commit the
file). A `.uid` file holds one `uid://` line. What the engine skips needs no sidecar and is not looked at: a name
that starts with a dot, and everything under a folder that holds a `.gdignore` (the template's `Docs/`, `Dataset/`,
`Brief/`, `Scripts/`). [game-format-v1.json](game-format-v1.json) (`repo.sidecars`) lists the extensions.

**Tasks live on the orphan `tasks` branch, never on main.** The same repo has a branch `tasks` that shares no history
with main: `Tasks/<game>-<kind>-<slug>.json` (one task each in the task format `GameTask`,
[schemas/game-task.schema.json](schemas/game-task.schema.json), `"engine": "godot-4.7"`; at least 5 and up to about
10 per game, every one a long thread of multiple edits; written with the `godot-write-tasks` skill), a short
`README.md`, optionally `tasks-workflow.jsonl`. It is checked out as a git worktree outside the game folder (e.g.
`<root>/tasks/<slug>`), committed and pushed there. Task work never enters the game's history: main never tracks
`Tasks/` and never references the tasks branch, the recording hooks ignore commits on it, and the delivered history
leaves it out. Seeds (`seed.commit`, `seed.reference`) point at commits of main's history, or of the task's own start
branch `starts/<task name>`.

**Combat contract.** In a game where anything can be hurt, what can be hurt is a node whose script has `func
take_damage(amount: float, source: Node) -> float` (returning the damage actually applied), and every hit calls it; a
hit method of the game's own (`apply_damage`, `take_hit`, ...) may exist only as a step called from `take_damage`.
Key gameplay state (a number or bool named with a word of health, hp, hitpoints, hull, poise, armor, shield, stamina,
mana, lives, dead, alive, dying, stun, stagger, invulnerable, invincible, guard, blocking, parry, alert, aggro, awake,
asleep, dormant, roused or cooldown; a whole number or enum named with phase or state) lives on node instances in the
scene, never in a `static var` and never in an autoload, because a task's probes read state on the scene's nodes; a
situation that takes more than a minute of play to reach has a scenario start option. Every sound the game plays is an
imported audio file (a clip, or a WAV a committed step script made), never made at run time (no
`AudioStreamGenerator`, no `AudioStreamWAV.new()` filled by code), so each sound has a name a probe can read. The
validator checks the first two (rule `contract`) and the last (rule `sound`) as errors on the game's own GDScript and
scenes (the AutoPlay drop-in, the task probe and `steps/` aside), and `tools/package-dataset.py` refuses a game that
fails them (`validate-game.py <repo> --rules-only` runs just these and rule `mobile`). A game in progress is brought
up to them before it is packaged.

No tool, vendor or owner names anywhere in the repo's text: Superposition, godot-game-factory and "game factory" in
any other spelling (`gamefactory`, `game_factory`), Claude, Anthropic, OpenAI (the validator scans tracked text files;
the packager scans binaries too and refuses a delivery whose binaries carry a name in their strings, but it never
changes a binary, so keep the names out of binary files yourself: `tools/godot-pipeline/scrub-import-paths.py`
takes them out of binary assets, byte for byte). The build machine's account name (machine paths carry it) counts
too: the validator reads it at run time and enforces it everywhere except in scripts that already ran (`Scripts/`,
`steps/`, and `.ps1`/`.psm1`/`.py`/`.sh`/`.bat`/`.cmd` files anywhere), which stay unchanged: the packager scrubs
them in every delivery. That includes `workflow.jsonl`: it is append-only except that a row naming a banned term is
edited in place to a neutral word or placeholder, nothing else changed, with one `log.correct` row appended (`params
{rows, what}`) and the edited rows named in the commit message: `python tools/scrub-workflow-rows.py <repo>` (dry
run), then `--apply`.

**Store content.** Store packs may sit in any folder under `assets/` (or, for an addon, `addons/`): what matters is
that every file the game uses is committed, so a clone opens and builds the game. The repo stays private.
`assets.manifest.json` lists each external asset once:

```json
{ "schema": "assets-manifest/v1", "project": "MyGame", "assets": [
  { "name": "Modular Warehouse", "source": "Kenney", "url": "https://kenney.nl/assets/...",
    "licence": "CC0 1.0", "version": "2.1", "store": false,
    "files": ["assets/ThirdParty/Warehouse/"], "used_for": "level kit", "changes": "materials re-tinted" } ] }
```

Every asset needs an https `url` (its listing or source page), except one made in-house by the studio (e.g. the
studio's own earlier project): that one has `"origin": "studio"` and a short `description` (what it is, where it comes
from inside the studio) instead of a url.

`files` are repo paths under `assets/` or `addons/`; one ending in `/` stands for every file under it. Each must be
committed (repo check) and be inside `GodotProject/` of `Dataset.zip` (dataset check). Content made by the game's own
code or steps is not listed.

## Platform

A game is a desktop (Windows) game unless its root has `Platform.json`, written by `templates/new-game.ps1 -Platform
mobile -Orientation landscape|portrait` when the project is created and never edited after. That file makes it a
mobile game: an Android phone game held one way, played by touch (the `godot-mobile-game` skill). Every tool reads the
platform from it through one reader, `tools/validate-game.py` `read_platform` (PowerShell tools through
`validate-game.py --platform <folder>`); no other code parses the file. A file that says anything else is an error,
never read as a desktop game.

The platform decides the size every play, screenshot, still and video of the game has: 1920x1080 for a desktop game
and a mobile game held landscape, 1080x1920 for one held portrait. A mobile game is played on the PC with the Mobile
renderer at that size, by touch events; its `Build/` in the dataset is the Android APK.

The validator's rule `mobile` holds a mobile game's settings to the file. A key a file leaves out is read as Godot
4.7's own default (the editor drops a setting put back to its default), never as wrong.

| File | Setting | Must be |
|---|---|---|
| `project.godot` | `rendering/renderer/rendering_method`, `rendering_method.mobile` | `"mobile"` (the Mobile renderer on the PC and on the phone; never the desktop renderer `forward_plus`) |
| | `rendering/textures/vram_compression/import_etc2_astc` | `true` (an Android build needs its textures as ETC2/ASTC) |
| | `display/window/size/viewport_width` x `viewport_height` | 1920x1080 (landscape) or 1080x1920 (portrait) |
| | `display/window/handheld/orientation` | a landscape setting (0, 2, 4) or a portrait setting (1, 3, 5) as `Platform.json` says; never 6, which follows the sensor either way |
| | `application/config/quit_on_go_back` | `false` (the back button is the game's to handle) |
| `export_presets.cfg`, the preset named `Android` | `platform` | `"Android"` |
| | `gradle_build/use_gradle_build` | `true` (only a Gradle build takes the SDK levels) |
| | `architectures/arm64-v8a`; `armeabi-v7a`, `x86`, `x86_64` | `true`; `false` (arm64 alone) |
| | `gradle_build/min_sdk`, `gradle_build/target_sdk` | at least 26, at least 34 (left empty they are the engine's own, 29 and 36) |
| | `package/unique_name` | `com.<name>.game`, lower case |

A mobile game's tasks never choose a renderer or a size: `--rendering-method`, `--rendering-driver`, `--resolution`,
`-size` and `--write-movie` in a task's `play_args` or a task play's `args` are errors, because the task check
launches a mobile game with the Mobile renderer at the phone's size. Nothing here changes for a desktop game.

## The dataset (`godot-dataset-layout/v1`)

`<repo>\Dataset.zip`, one top folder `<game>/`, made by the packager ([Package](#package);
[godot-pipeline.md, Dataset packager](godot-pipeline.md#dataset-packager) says what it does; `Dataset.pending.zip`
while an entry is missing, see "Complete vs pending" below):

| Entry | In the repo's `Dataset/` | What |
|---|---|---|
| `README.md` | yes | the game, how to play, open, replay and restore it; sections in the order of the layout file |
| `git.log` | yes | every commit up to the release, oldest first: message, `dev_NN` authors, dates, full text diff; binaries as path + sha256 |
| `workflow.jsonl` | yes | the creation record; **the person's directions are `user.direction` rows**, written by the session (the prompts and replies themselves are in `History/sessions/`) |
| `Brief/` | yes | `brief.md`, the brief as given; `design.md`, the design doc with story bible and status |
| `History/` | no | `<game>.bundle` (the release commit's history as `refs/heads/main` and each task's start branch as `refs/heads/starts/<task>`, nothing else: the tasks branch is never in it), `lfs/objects/<aa>/<bb>/<sha256>` (every Git LFS object of every commit of the bundle) and `sessions/` (the creation sessions as recorded: `messages.jsonl`, `actions.jsonl`; below) |
| `Tasks/` | no | the game's tasks, each split: `Tasks/<name>/task.json` (the agent's part) and `Tasks/<name>/grader.json` (milestones, `seed.reference`), plus a generated `README.md` (`tools/split-tasks.py`) |
| `GodotProject/` | no | the project at the release commit (`project.godot`, `export_presets.cfg`, scenes, scripts and assets with every `.import` and `.uid`; no `.godot/`: the first open rebuilds it), store content included; a mobile game's `Platform.json` at its root |
| `ReplayScripts/` | yes | the creation replayed headless, with `Verification/report.json` (required for complete; its verdict PASS or FAIL is metadata) |
| `Gameplay/<game>_S<n>.mp4` | yes | at least one scenario video of the release version (one recorded scenario is enough; videos of other scenarios already recorded may be included), h264 + aac at the game's size: 1920x1080, or 1080x1920 for a mobile game held portrait |
| `Screenshots/` | yes | the README's images |
| `Build/` | no | a desktop game: the Windows release player (x64), `<Project>.exe`; a mobile game: the Android APK `<Project>.apk` (arm64, min SDK 26) and no Windows player |
| `manifest.json` | yes | metadata, `platform` and `orientation`, `history`, `brief`, `tasks`, `build`, and path / bytes / sha256 of every file except the content-addressed `History/lfs/objects/` |

`manifest.json` says what the game is: `platform` (`desktop` or `mobile`) and `orientation` (`landscape`, `portrait`,
null for a desktop game), which the validator holds equal to `GodotProject/Platform.json` (no file: a desktop game),
and `build`: a desktop game's names its player (`exe`), a mobile game's its APK (`apk`, with its `bytes`, `package`,
`min_sdk`, `target_sdk` and `abis`) and never a Windows player.

**The history is rewritten for delivery** (the game repos are not changed): authors and committers become `dev_NN`,
agent trailer lines go, the scrub rules apply to every message and text blob. Commit ids therefore differ from the
private repo; the dataset uses the delivered ids everywhere (`manifest.json` `commit`, `git.log`, `ReplayScripts/`,
the tasks' seeds), and the packager keeps the old -> new map, never in the package, in
`<out>\<slug>\<slug>_<sha8>.commit-map.tsv`, one per delivered release (`<sha8>`: the delivered release commit's;
`<out>`: env `GGF_OUT`, config `out`, else `<root>\deliverables`), and in its scratch folder
(`<repo>\.dataset\<slug>.commit-map.tsv`, emptied by the next run). Restore a commit:

```bash
git clone History/<game>.bundle <game>
```

then copy `History/lfs` into `<game>/.git/lfs`, `git lfs install --local`, `git checkout <commit>`, `git lfs checkout`.

**The sessions.** `History/sessions/` holds the creation sessions as the build machine's hooks recorded them, one JSON
row per line, in two files. `messages.jsonl` has every prompt the person typed, every reply the model wrote and every
reasoning summary the agent saved: `time`, `project`, `session_id`, `agent`, `role` (`user`, `assistant` or
`thinking`), `message_id`, `text`, and where they apply `model`, `images` (pictures attached to a prompt), `mid_turn`
(a prompt typed while the model was working), `phase`, `subagent`. `actions.jsonl` has every tool call with its input
and its whole result (up to 1,000,000 characters, `response_chars` and `response_truncated` on a longer one; a picture
or other binary payload as a short marker). In `messages.jsonl`, a `thinking` row is a reasoning summary the agent
saved for a turn (`redacted` true and no text when the agent saved it without readable text). Not in either: text the
agent tool put into a turn itself. The rows go up to the release commit; the sessions that packaged the dataset and
those named with `--exclude-sessions` are left out; each session is named `session_NN`, the same in both files, so
`session_id` and `time` tie a reply to its tool calls; the text is scrubbed like every other text file of the
delivery. `manifest.json` counts the rows (`history.sessions`: `messages` and `actions`, each with `file` and
`rows`). Both files are optional, and the validator reports what it finds here as warnings and notes, never errors.
The `user.direction` rows of `workflow.jsonl` stay as they are.

**Tasks.** A game is complete when its repo's orphan `tasks` branch has `Tasks/`: tasks an agent can be given on
this game (a bug fix from its history, a correction from a person's direction, a feature, a look or content change),
in the task format (`GameTask`, game-task/1), one file per task named `<game>-<kind>-<slug>.json` with `name` equal to
the file name. A game has at least 5 and up to about 10: with fewer than 5 it is rejected. The tasks branch is
the single source: tasks are loaded as `Tasks/*.json` from the repos' tasks branches. How to write them: the
`godot-write-tasks` skill. The validator reads the tasks from `tasks` (else `origin/tasks`) and checks each against
[schemas/game-task.schema.json](schemas/game-task.schema.json) (the task format; probe checks:
[task-probes.md](task-probes.md)) and the rules the schema cannot express (probe rules, play arguments, touches that
end inside their play and leave a finger up 0.1 s before it goes down again, thresholds that are never literal, the
no-op rule), that its seed is on this game and its seed commits are ancestors of main's head or of the task's own
start branch `starts/<task name>` and Godot `4.7` projects as committed (`project.godot`'s `config/features`), that
the branch shares no history with main, and that main tracks nothing under `Tasks/`. At least 4 of a game's tasks are
`hard`; the others may be `medium` (what a task that names no difficulty is), none easier. It also holds each task to
the bar of a long thread: tagged `long-thread`, with `seed.reference`, at least 3 required outcome probes outside
`still_works`, and from start to reference at least 5 game files (`scenes/`, `game/`, `assets/`, `addons/` but the
AutoPlay drop-in and the task probe, and `project.godot`; a step script, an `.import` or a `.uid` is not one), 100
code lines and 2 systems, and for a seed on main 4 commits that change the game (`tools/validate-game.py` holds the
numbers).

In a dataset (`godot-dataset-layout/v1`) the packager copies the tasks from the tip of the tasks branch, maps each
seed's commits through the history rewrite, scrubs them, and splits each into `Tasks/<name>/task.json` (what the agent
may see: name, title, instruction, engine, seed without its reference, `play_scene`, `play_args`, `player`, asset
packs, difficulty, tags, limits) and `Tasks/<name>/grader.json` (the grader's half: `milestones` with their probes,
rubrics, judge and code-judge questions and log patterns, and `seed.reference`); merging the two gives the task.
`Tasks/README.md` explains it. The validator checks the split, that each merged task is valid on this game, and that
its seeds are commits of `History/`.

**The harness rule.** An agent given a task starts from a history-less snapshot of the game at `seed.commit`, with
`Tasks/`, `History/` and `Dataset/` removed (every task's answers are in them, and the reference fixes are in the
history); it sees only the brief and that snapshot. The grader's half never reaches the agent.

**Complete vs pending.** `status` is `complete` when every entry is there, `ReplayScripts/` with its
`Verification/report.json` included; `pending` while an entry is missing and listed in `pending` (the zip is then
`Dataset.pending.zip`): `ReplayScripts/` while the creation replay is missing, and `Build/` while a mobile game's
release has no APK (the build machine had no Android toolchain: `machine/get-android.ps1` installs it, then
`tools/godot-pipeline/build.ps1 <slug> -Force` and package again). A desktop game's `Build/` is never pending. A game
without a gameplay video is rejected at upload: a delivered zip that lists `Gameplay/` as pending is an error, and the
packager refuses a release without a recording. The replay is required but need not pass: a FAIL verdict is metadata,
like a gameplay run's result: manifest `replay_verification.pass` false (equal to the report's `verdict.pass`) and the
README says FAIL. The packager writes the complete `Dataset.zip` once the release has a gameplay video, its replay and
its player ([Package](#package)).

## For a contractor

Deliver the repo (private, with Git LFS) with the content below, then package it ([Package](#package)): the packager
builds the dataset from the repo, so don't assemble a `Dataset.zip` by hand.

1. The repo rules above, every imported file with its `.import` and every script with its `.uid`;
   `assets.manifest.json` in `assets-manifest/v1`; a mobile game made with `new-game.ps1 -Platform mobile`, its
   `Platform.json` never edited.
2. `workflow.jsonl` from the first operation, with every direction you were given as a `user.direction` row
   (neutral wording, what and why) before the work it caused, and `"direction": "<id>"` on the rows that act on it.
3. `Brief/brief.md` (the brief you were given) and `Brief/design.md` (your design doc).
4. Your game's tasks in `Tasks/` on an orphan `tasks` branch of the repo, never on main (at least 5 and up to
   about 10 per game, at least 4 of them hard, the others may be medium; the `godot-write-tasks` skill), each seeded
   on commits of main's history (or its own `starts/<task>` branch).
5. `python tools/validate-game.py <repo>` VALID. Its warning "Dataset/ has no manifest.json: not packaged yet" is
   expected only before the packager's first run.
6. A release player (`tools/godot-pipeline/build.ps1 <slug>`, or `Scripts/godot.ps1 build` into `Build/`; a mobile
   game's with its APK), a recording of the release commit (`tools/godot-pipeline/pipeline.ps1 <slug>`:
   [godot-pipeline.md, Pipeline](godot-pipeline.md#pipeline)) and its creation replay
   (`python tools/godot-replay/godot_replay.py release --game <slug>`): a complete `Dataset.zip` needs all three. Then
   `python tools/package-dataset.py <slug>` (`--repo <repo>` when the repo is not `<root>/games/<slug>`). It runs the
   dataset checks itself and refuses on an error. Commit the `Dataset/` folder it writes; `Dataset.zip`
   (`Dataset.pending.zip` while an entry is missing), written next to it, is never committed: deliver it beside the
   repo. A game without a gameplay video is rejected at upload: without a recording of the release commit the packager
   refuses.

Your agent sessions use only the godot-game-factory skills (`godot-commit-always`, `godot-game-session`,
`godot-desktop-game` or `godot-mobile-game` by the game's platform, `godot-sound`, `godot-write-tasks`, installed by
`machine/bootstrap.ps1`): never install, enable or invoke any other skill, whether your own personal or project
skills, a plugin's or marketplace's, or one bundled with the agent (AGENTS.md, "Only these skills"). The recorded
sessions are the dataset (every tool call, every prompt you type and every reply the model writes is recorded and
delivered in `History/sessions/`), so the game is made under these rules alone.
