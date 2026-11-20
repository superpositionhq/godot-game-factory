# Godot creation replay

Rebuilds one of our Godot games from its first commit by re-running, in order, what its builder ran: each commit's
files, the engine's import, and the generator steps that wrote what only the engine can make. The replay then checks
the result against the game's final commit. It produces the dataset's `ReplayScripts/` with
`Verification/report.json` ([game-format.md](game-format.md), "Complete vs pending";
[schemas/replay-report.schema.json](schemas/replay-report.schema.json)). The replay is required for a complete dataset;
its verdict, PASS or FAIL, is metadata.

Tool: `tools/godot-replay/` (`godot_replay.py`, Python 3.10+, standard library only; one engine-side script,
`tools/godot-replay/engine/replay_dump.gd`). Per-game settings live in the game's own repo as
`<root>/games/<slug>/ReplayConfig.json` (the template has it); a game without one replays with the defaults
(section 4). `godot_replay.py <command> --game <slug>` loads them; `--game` also takes a game repo folder, or a
settings file (for example a delivered `ReplayScripts/game.json`). Per-game results belong in the game's own docs, not
here.

## 1. How our Godot games are built

A Godot game is text files in git, and three records cover how a session made them:

- **Text the session writes**: scenes and resources (`.tscn`, `.tres`), GDScript, shaders, `project.godot`,
  `export_presets.cfg`, written with the agent's file tools and committed; source art and sound beside them.
- **What the engine writes**: beside every file it imports a `.import` file (the import settings and the file's
  `uid://` identity), beside every script and shader a `.uid` file. `Scripts/godot.ps1 import`
  (`godot --headless --import`) makes them, and they are committed.
- **Generator steps**: GDScript files under `steps/`, run headless with
  `Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."` (`godot --headless --script res://steps/<name>.gd`
  through the machine's limiter), for what only the engine can make: a procedural mesh, baked data, a scene put
  together by code. Each run appends one `workflow.jsonl` row (op `editor.step`) with the step's file
  (`source.script`) and the sha256 of its text as it ran (`source.sha256`).

| Record | What it gives the replay |
|---|---|
| git history (`games\<slug>`) | the exact files at every commit, and the committed generated files to compare against |
| `workflow.jsonl` | the row of each step run (`source.script`, `source.sha256`, `status`) |
| `.recording\<slug>\actions.jsonl` | the agent's tool calls in order: every step run (with the command line and its output), every `Write`/`Edit` (`apply_patch`) of a file, every shell command |

The replay also reads `.recording\<slug>\commits.jsonl` (the post-commit recorder's rows) for the moment each commit
was made: a commit's own time has whole seconds only.

## 2. Replay design

### 2.1 The replay unit

The unit is the **window**: the work between two consecutive commits on the first-parent chain, closed by the commit.
A window's steps come from the ledger (`godot_replay.py ledger`), in the order they happened.

What the replay writes from the commits and what it makes itself:

- **Generated files** are what the engine and the steps write: every `.import` and `.uid` file, and every engine
  resource (`.tscn`, `.tres`, `.scn`, `.res`, `.mesh`, `.material`, `.anim`, `.theme`, `.fontdata`, `.multimesh`,
  `.occ`, `.lmbake`; settings `content_ext` adds extensions) that a commit adds or changes **without a recorded
  write** in its window. A file of any other kind that a step of the window wrote, again without a recorded write,
  counts as generated too. A generated file is never copied from a commit when the replay produced it, so errors
  accumulate visibly instead of being reset.
- **Inputs** are everything else: every file the recording shows the session writing (a `Write`, an `Edit`, an
  `apply_patch`, a shell edit or copy the replay can follow), whatever its kind, and every file that is not of a
  generated kind (scripts, settings, source art, `workflow.jsonl`, docs). A `.import` whose source file the commit
  does not have is an orphan the commit owns: an input, taken as it is.

| Step | Source | What the replay does |
|---|---|---|
| `inputs.apply` | commit tree | writes every input the commit adds or changes; deletes what it deletes |
| `import settings` | commit tree | a `.import` file is part input, part generated: its importer and its `[params]` section are the session's choices (loop mode, mono, compression, set by editing the file and importing again), the rest (`[remap]`, `[deps]`, the uid) is the engine's. Before the import the replay writes the commit's importer and `[params]` into each `.import` the window adds or changes (a stub when the file is not there yet); the engine then writes the file whole |
| `engine.import` | the engine | `godot --headless --path <project> --import` when the window changes anything the engine reads, and once more after the window's steps when they wrote files: the engine writes the `.import` and `.uid` files it finds missing |
| `editor.step` | `actions.jsonl` command lines | re-runs the step headless in the replay project, `godot --headless --path <project> --script res://<script>`, with the step's text as it stood when the builder ran it (section 2.6) |
| `shell delete` | `actions.jsonl` | a file a recorded command deleted or moved away (`rm`, `mv`, `Remove-Item`, `Move-Item`) is removed from the replay's own files at the same point, unless the window's commit has it |
| `boundary` | commit | checks the window (section 2.4): identity, generated files, fallbacks; then makes the replay project's inputs equal to the commit |

The step run it recognises in a recorded command is `Scripts/godot.ps1 step -Script <path>` (also with `-Mode step`,
through `powershell -File`, and inside a `for` or `foreach` loop with the path built from the loop variable). The
other modes of `godot.ps1` (`import`, `row`, `build`, `play`, `autoplay`) are not replayed one by one: the replay
imports where a window needs it, and the rest writes nothing the game is made of. The exit code of each run and the
workflow row it printed (`[workflow] <id> ...`) come from the recorded output. A step call whose script the replay
cannot read (a variable the command does not set, a path outside the project) is listed and not replayed. The replay
never commits.

### 2.2 Preparing the isolated project

`godot_replay.py prepare` creates `%GGF_ROOT%\godot-replay\<game>\` (settings `work_root`) with:

- `<slug>/`: the replay project, a `git clone --shared --no-checkout` of the game repo, Git LFS reading the game's own
  object store (`lfs.storage`; nothing downloaded), checked out at the **first commit** (the template's skeleton). The
  game repo itself is only read.
- `work/`: ledger, state, blobs (step texts), logs, dumps, results.
- `truth/<slug>/`: the same clone at the final commit, which `verify` makes, imports and dumps as the reference.

A repo that is not the root's game of its name (a copy, a clone elsewhere) gets a work folder of its own,
`<root>\godot-replay\_other\<name>-<id>`.

### 2.3 Running

`godot_replay.py run` executes the plan, resumable (`work/state.json`; a `work/STOP` file pauses it between steps).
Every engine process goes through `<root>\tools\godot-heavy.ps1` (a machine without it runs the engine directly), and
every one is headless: a general slot, never a GPU slot. The engine is the factory's pinned one
(`machine/lib/ggfroot.py`; env `GODOT_EDITOR` names another binary). A run that lasts longer than `run_timeout_s`
(default 3600) is stopped and counted as failed: a step whose script hits an error before its `quit()` never ends by
itself. Each engine run is logged under `work/logs/`, and `work/runs.jsonl` has one row per import, step run and
shell delete with the files it added, changed and deleted. If the game's history is no longer the one already
replayed (an amend, a rebase), `run` stops and says to remove the work folder and replay again.

### 2.4 What is checked

Per window (`work/windows.jsonl`):

1. **Reconstruction**: every file rebuilt from the recorded writes and edits matches the commit's text at the boundary
   (one that does not is listed in the report, `reconstruction_mismatch`).
2. **Identity**: the engine makes its own `uid://` for a new file, so the uid of a file the replay generated (a `.uid`
   file's text, a `.import` file's `uid=` line, the `uid=` in the header of a text scene or resource) becomes the one
   the commit has at the same path, in that file and in every other file the window generated that refers to it.
   Identity, never content (`uids_adopted`).
3. **Generated files**: every generated file the commit adds or changes is identical, differs (kept as the replay made
   it) or, when no step of the window produced it, is taken from the commit (`fallback`, with the reason; listed as
   the deviation `content_from_commit`); the set of files in the project against the commit (`missing`, `extra`).

At the end (`godot_replay.py verify`, against the final commit):

1. **Files**: every tracked file is byte-identical to the final commit.
2. **Structure**: `engine/replay_dump.gd` runs headless on the replayed project and on `truth/`
   (`godot --headless --path <project> --script <replay_dump.gd> -- <out.json>`), and the two dumps are compared. The
   dump walks the project, leaving out `.godot/`, `addons/task_probe/` and every folder that carries `.gdignore`, and
   writes:
   - every scene (`.tscn`, `.scn`): each node in file order with its path, class or instanced scene, groups, script
     path and the properties the file stores (those that differ from the class default), and the signal connections.
     Nothing is instantiated, so no game script runs;
   - every resource (`.tres`, `.res`): class, script path and stored properties; a sub-resource as class and
     properties, an external resource as its path;
   - every imported file (one with a `.import`): importer, resource type and import settings.
   Floats are rounded to 4 decimals and compared with a tolerance of 0.0011; a packed array longer than 16 items is
   its size and sha256.
3. **Verdict** (`report.json` `verdict`, top of `report.md`): PASS only when (a) `files`: every tracked file is
   byte-identical, none missing, and no extra files except git-ignored ones; (b) `structure`: the two dumps are equal.
   Known non-content differences are normalised first and counted in `verdict.exclusions` (a list of
   `{id, what, count}`): `uid` (text files and dump values that differ only in `uid://` strings; what a reference
   points at is compared by its path), `uids_adopted` (the identities adopted at the boundaries),
   `git_ignored_extra_files`. The comparison of each run with its original (exit code; the sha256 of the step's text in
   its workflow row against the text the replay ran) is informational.

`report.json` follows [schemas/replay-report.schema.json](schemas/replay-report.schema.json) (the tool checks it when
it writes it); `deviations` lists every place the replay departs from the raw recording, with the reason, and
`report.md` says the same for people.

### 2.5 ReplayScripts

`godot_replay.py package --game <game>` assembles it in `<out>\_replay\<game>\<final sha8>\` (`<out>`: env `GGF_OUT`,
config `out`, else `%GGF_ROOT%\deliverables`), unscrubbed:

```
ReplayScripts/
  README.md                       how to replay, what is observed vs verified, results, deviations
  godot_replay.py, runner.py, ledger.py, verify.py, shellfx.py, patchfx.py, package.py
                                  the tooling as it ran (it works outside the tool checkout: GGF_ROOT or ~/GodotWork,
                                  the engine from GODOT_EDITOR)
  engine/replay_dump.gd
  game.json                       the game's replay settings ({root} placeholders, no machine paths)
  ledger.json                     windows, step runs, texts (from history + actions)
  Blobs/                          step texts by sha256
  Verification/
    report.md, report.json        files, structure, runs, verdict, deviations
    windows.jsonl                 per-window checks
    dump-replay/dump.json, dump-truth/dump.json   the JSON structure dumps of both projects
verification.json                 summary for the packager: parts present, windows, verdict
READY                             written last, when every window was replayed and verified (PASS or FAIL)
```

`--force` assembles an incomplete copy without `READY` (for checks only). The build machine's session folders and
session ids in the copied records become neutral names.

`godot_replay.py release --game <slug>` does all of it for the settings' `final` (`HEAD` by default): `ledger`,
`prepare`, `run`, `verify`, `package`. A FAIL is packaged like a PASS: the verdict is metadata.

Disk: `prepare`, `run`, `verify` and `release` refuse to start when the work drive has less than `min_free_gb` (env
`GGF_MIN_FREE_GB`, default 50 GB) free, `package` likewise for `<out>`. Once `READY` exists,
`godot_replay.py clean --game <game>` lists the replay project, the truth project and the bulky work files and removes
them with `--yes`; the ledger, state and report stay.

### 2.6 A step's text as it stood when it ran

The window's inputs are the commit's, but a step that ran before a later edit of its script ran with the earlier
text. The ledger records, per run, every step script the builder wrote in the window as it stood at the run's start,
rebuilt by re-applying the recorded writes and edits from the previous commit's text (`texts`; `absent` for one not
written yet; `unknown` for one the recording cannot rebuild, which keeps the commit's text and is listed as the
deviation `commit_text_unrebuildable`). The runner writes those texts before the run and puts the commit's files back
at the boundary.

## 3. Rules for game sessions

A session keeps these so its history replays (godot-game-session skill):

- **Scenes and resources are text, written with the agent's own file tools** (Claude Code: Write/Edit; Codex:
  apply_patch; Antigravity: write_file/edit_file, which the ledger reads as Write/Edit; a file another of its tools
  writes is one the replay takes from the commit). The recording then holds each write, and the file is an input. A `sed
  -i`, a Python rewrite or a change made in the editor's window leaves a file the recording cannot explain: the replay
  takes it from the commit and lists it.
- **Every generator step committed under `steps/` and run only through**
  `Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."`, never by calling the engine directly and never from a
  scratch folder. The replay finds step runs by that call shape.
- **A step that ran is not edited**: write a new one (`build_harbor_v2.gd`), so each row's `source.sha256` still names
  the code that ran.
- **Relative paths only**: a step reaches files through the project (`res://...`), never an absolute path to
  `games\<slug>`.
- **A step makes the same files from the same inputs every time**: seed every random number, no clock, no network.
  It ends itself with `quit()`, and with `quit(1)` when it failed.
- **Import options are set in the file's `.import`**: edit its `[params]` section, run `Scripts/godot.ps1 import`
  and commit the file. The replay gives the engine the same settings.
- **Commit what the engine wrote with what caused it**: run `Scripts/godot.ps1 import` after adding a file or
  running a step, and commit the `.import` and `.uid` files in the same commit.
- **No amend, no rebase**: the windows are the commits on the first-parent chain, and the recording is matched to
  them by time.

## 4. Settings (ReplayConfig.json)

| Key | Default | What |
|---|---|---|
| `game`, `repo`, `recording`, `work_root` | from the repo | slug, game repo, its recording, the replay's folders (`{root}` = machine root) |
| `final` | `HEAD` | the commit `verify`, `package` and `release` take |
| `run_timeout_s` | `3600` | the longest an engine run may last |
| `content_ext` | `[]` | more file extensions that count as generated kinds (section 2.1) |

## 5. Packager integration

A dataset's `ReplayScripts/` is `<out>\_replay\<game>\<release sha8>\ReplayScripts\` (the release commit's id before
the history is rewritten for delivery), complete once `READY` is beside it; `godot_replay.py release --game <slug>`
makes it. What the dataset takes from it: the folder itself, copied, scrubbed like every other text file of the
delivery and with its commit ids mapped to the delivered history (so `report.json` `final_commit` equals the manifest's
`commit`), and the manifest's `replay_verification` from `ReplayScripts/Verification/report.json` (`verdict.pass`,
`verdict.criteria` with their `result`, `verdict.exclusions` as `{id, what, count}`; `report`:
`ReplayScripts/Verification/report.md`). The packager (`tools/package-dataset.py`) takes it from there
([godot-pipeline.md, Dataset packager](godot-pipeline.md#dataset-packager)); without `READY` a dataset lists
`ReplayScripts/` as pending. The replay is required but need not pass: a FAIL is packaged as metadata (manifest
`replay_verification.pass` false, the README says FAIL), and the dataset is complete with it as with a PASS
([game-format.md](game-format.md), "Complete vs pending").
