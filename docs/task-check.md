# Task check: check your own tasks

A task (a GameTask JSON in `Tasks/` on the game repo's orphan `tasks` branch, schema
[schemas/game-task.schema.json](schemas/game-task.schema.json)) is only useful when its checks tell a broken game from a
fixed one. The task checker proves that on your machine before you hand the task in: it builds the game at the task's
start (`seed.commit`) and at its reference (`seed.reference`, the change that solves it), plays both with the task
probe addon, measures every probe, and says **VALID** or **INVALID** with the reasons. It checks the two cases the Lab
checks before any agent is given the task, by the same rules: the **no-op** (the start, left untouched, graded as if
an agent had handed it in: it must fail the task and earn nothing) and the **oracle** (the reference graded the same
way: it must pass every required check). The skill that writes tasks walks through both step by step
(godot-write-tasks, "The no-op and the oracle, on your own machine").

```powershell
python tools\task-check.py %GGF_ROOT%\games\<slug> --task <task-name>
python tools\task-check.py %GGF_ROOT%\games\<slug> --task <one> --task <two>
python tools\task-check.py %GGF_ROOT%\games\<slug> --all
python tools\task-check.py %GGF_ROOT%\games\<slug> --task %GGF_ROOT%\tasks\<slug>\Tasks\<task-name>.json
```

Run it from the godot-game-factory folder (`%GGF_ROOT%\godot-game-factory`, where `%GGF_ROOT%` is the machine root,
`%USERPROFILE%\GodotWork` by default). A task is read from the repo's `tasks` branch by name (its file name in
`Tasks/` without `.json`); give the path of a `.json` file instead to check a task you haven't committed yet.

**Check a game's tasks in one run** (`--all`, or several `--task`). The run makes one scratch copy per commit and
builds it once, so a commit that is one task's start and another's reference, or two tasks' start, costs one build;
each copy is deleted after the last task that needs it (or when the disk runs below the floor, then rebuilt if a later
task needs it). A shared copy is the commit exactly as committed, so sharing changes no result. A run of many tasks
takes a while, so start it where it can run on its own and come back; a game session starts it as its own process
(godot-write-tasks skill, section 5). Two runs at once on one game each get their own scratch folder, but share
`<out>` unless each is given its own `--out`: they rewrite each other's progress files, and a task checked by both
loses its evidence to the other. `<out>\progress.txt` (and `progress.json`) is rewritten after every task: how many
are done, each one's verdict and minutes, and which is running; it says `finished` at the end. Progress lines carry
the time of day, and each build and play logs how long it took.

Without `--task` or `--all` it lists the tasks on the branch. Each task prints one line, and the exit code is 0 only
when every task is VALID (1 otherwise; 2 for a usage error, when nothing ran):

```
VALID   metro-runner-corr-cell-and-dead-meter
INVALID island-survival-fix-hut-door: start already passes every required probe
```

Options: `--keep` keeps the scratch copies (to look at one or rerun a play by hand), not what their plays left
outside them (a play starts from clean saved data anyway), `--out DIR` puts the results elsewhere, `--scratch DIR`
puts the copies elsewhere, `--direct` runs Godot without the machine's job slots, `--timeout S` (a play, plus the
real seconds of its waits; by default a play gets its own seconds and 300 s more, as the Lab's grader gives it, with
no other floor) and `--build-timeout S` (default 1800, the Lab's; a release export gets twice it). A task play
lasts up to 1200 s of play time (the Lab game grader 1.18.0's), and a play runs on its fixed clock as fast as the
machine renders: a long play that needs more than 300 s past its own seconds on the Lab's machine is stopped there.
`--settle` plays nothing: it settles each named task's kept run in `<out>` on the answers you wrote for that run's own
pictures ("Settling a run", below).

## Requirements

- Windows with the factory's Godot (4.7, the version `machine/godot.json` names), found through the machine config
  (the environment variable `GODOT_EDITOR`, else `godot` in `%USERPROFILE%\.godot-game-factory\config.json`, else
  `<root>\godot\<version>\`; [new-machine.md](new-machine.md)). A machine without it is an ERROR saying what installs
  it. Every start and reference must be a Godot 4.7 project as committed (`project.godot` names `"4.7"` in
  `config/features`): the checker never upgrades, ports or patches a game, and refuses any other version.
- A desktop session with a graphics card: a play is the real game, drawn. The checker starts it on a Windows desktop
  of its own, so it needs an interactive session (not a service).
- Python 3.12 (standard library only), git and Git LFS. The checker reads the game's files straight from its git objects
  and its local LFS store, so the LFS objects of both commits must be there: `git -C <repo> lfs fetch origin <commit>`
  when it says one is missing.
- Disk: each task needs up to two copies of the game plus their `.godot/` folders (the imported assets), deleted after
  the last task of the run that needs them. The copies go on the repo's own drive (its resolved path, junctions
  followed), so LFS files are hardlinks of the repo's own objects and cost no disk; `--scratch` on another drive makes
  them copies. It refuses to start below the machine's free-space floor (`min_free_gb` in the machine config, else
  50 GB; the environment variable `GGF_MIN_FREE_GB` overrides both), and a run that falls below it stops once it has
  deleted every copy the current task doesn't need.
- Time: two builds and a few plays per task. A build is an import of the copy (seconds for a small game, minutes for
  one with many or large assets) and a start of the engine that loads every script. A commit shared by several tasks
  of one run is built once. A 20 s play takes a few seconds of real time (one that measures audio takes its own
  seconds). Every build and play goes through `<root>\tools\godot-heavy.ps1` when the machine has it (plays with
  `-Gpu`), so checks share the machine's job slots with everything else; its timeouts count from when a job starts,
  not the wait for a slot. A job waits for its slot as long as the machine's slots are taken; the job's progress line
  then says how long it waited. The checker starts that script itself, from any shell; if PowerShell still refuses to
  run it (an execution policy your organisation set), each task's line is an ERROR that says so: pass `--direct`.

## What it does

1. Reads the task from the `tasks` branch (else `origin/tasks`) and validates it like
   [tools/validate-game.py](../tools/validate-game.py) does (the schema and the task format's own rules; the
   validator's long-thread bar is the validator's alone); a task that doesn't validate is INVALID.
2. Materializes the start and the reference into a scratch folder outside the repo, on its drive (default
   `<root>\.task-check\` when the machine root is on the repo's drive, else a `.task-check` folder beside the folder
   that holds the repo; each copy in a `<run>\<commit>` folder under it): every file of that commit exactly as
   committed, LFS files hardlinked from the repo's store (copied across drives), without `Tasks/`, `History/`,
   `Dataset/` or `Dataset.zip`. The task probe is added as `addons/task_probe/`, with three lines in the copy's
   `project.godot`: the probe's autoload (`TaskProbe`, first in `[autoload]`) and a user data folder of the copy's own
   (`config/use_custom_user_dir`, `config/custom_user_dir_name="TaskProbe.<hash>"`), so a play's saved data
   (`user://`) is never the real game's, nor the other side's. A line of the game's own that sets one of those three
   settings is taken out, and an autoload the game sets before every section moves in after the probe's, so the engine
   reads the probe's and loads it first; no shape of the file is refused. Nothing else is added or changed, and nothing
   comes from another commit (no patch). Your checkout is never touched.
3. Builds the start. There is no player build: a copy is played from source with the editor binary, and its build is
   what makes it ready for that, two headless jobs: the import (`godot --headless --path <copy> --import`, which writes
   the copy's `.godot/`), then a start of the engine that loads every script of the project (the import alone parses
   only the scripts the editor opens). The build passes when both exit 0 and neither log has a script error (`SCRIPT
   ERROR`, `Parse Error`, `Failed to load script`). A start that doesn't build makes the task INVALID, unless its
   build check says so (`"fails_at_start": true`: making it build is the task); then the start failing to build is the
   start failing the task, and it is never played.
4. Checks the reference as if it were a solution (the oracle): the task's checks in order (a check whose `needs`
   failed doesn't run and fails: `not run: needs X`): build, boot (a play of `seconds` that must run to its end
   without a crash: a log line matching `CrashHandlerException`, `Program crashed with signal`, `Dumping the
   backtrace` or `Out of memory`), `log_absent`, `file_exists` (the copy's files, without `.godot`, `Build`, `Logs`,
   `android` and `.git`), `package` (the game's release export made and booted, below), and every probe against its
   threshold. A probe no version of the game could pass is a **task error** (below).
5. Checks the start on its probes, and on every other check that carries weight (the no-op: the Lab scores a no-op on
   every check, so a weighted `log_absent`, `file_exists` or `package` check is run on the start too).
6. Writes the result and deletes the scratch copies (unless `--keep`) and, kept or not, what their plays left outside
   them: each copy's own user data folder, `%APPDATA%\TaskProbe.<hash>`, and nothing else.

### The plays

Each play is the copy run from source (`godot --path <copy> [scene] -- -taskProbe <spec> <play args>`) **on a
Windows desktop of its own** (`tools/task_check/desk.py`: nothing shows on your screen, and the play can't take your
keyboard or mouse) on a fixed 30 fps clock, on the task's `play_scene` (a `res://` scene path) with its `play_args` (or
the task play's own `scene` and `args`), with the task probe sampling every 0.5 s (a task play's `every`). Each play
is played once per side, with the measures of every probe that names it. A play with an `audio` measure is paced to
real time and every other play runs as fast as the machine renders.

Plays run in the order the task's checks first ask for them, except that a task play with `after` runs once every
play it names has run on the same side, a failed one too, and starts on the saved data they left
([task-probes.md](task-probes.md), section 1.1). Every other play starts clean (a play may say so with
`"fresh": true`, never beside `after`): the checker deletes the copy's user
data folder before it, and the probe empties `user://` as the game starts. When another play ran between a play and
the plays it names, those are played again first for their saves (`playing play_<name> again` in the log; their
files are kept as `play_<name>_again`, their checks keep their first play's result, and a replay that ended
otherwise than the first is noted in the detail of the reader's checks).

**The frame.** A desktop game is played at 960x540. A mobile game (its copy has a `Platform.json`) is played at the
phone's size, 1920x1080 or 1080x1920, by touch ([task-probes.md](task-probes.md), section 1.1), with the renderer its
project names (the Mobile renderer). The size is the frame's, whatever the window is (a portrait frame is taller than the screen):
the probe renders the game at the size its project is laid out for and scales the frames it reads to the play's
size, so a 960x540 frame shows what a 1920x1080 window shows. No play is heard: the engine runs with its dummy
audio driver, and the mix is still measured. A task never chooses a renderer or a size.

| `play` | What |
|---|---|
| `"look"` | 20 s, no input, 6 screenshots |
| `"drive"` | 22 s, 8 screenshots: `<Keyboard>/w` 1-6 s, `<Keyboard>/d` 6-8 s, `<Keyboard>/w` 8-13 s with `<Keyboard>/space` at 9-9.3 s, `<Keyboard>/a` 13-15 s, `<Keyboard>/w` 15-21 s. A mobile game is driven by touch on the same route: a left thumb's drag from where a virtual stick usually is (0.15, 0.75 of the screen) up, right, up, left and up again, each held, and a right thumb's tap at (0.85, 0.75) at 9 s |
| `{"name": ..., "seconds": ..., "inputs": [...]}` | a task play: keys, axes, widget clicks, cursor moves, taps and drags, teleports, teleports next to an object and waits at their times, its own `scene`, `args` and `every`; 2 screenshots |
| a boot check | `seconds` of play, no input, 2 screenshots; `log_absent` reads a 60 s boot's log |

A boot is the same idle game as `"look"`, only longer, so on the side that boots (the reference; a start is never
booted) one 60 s idle play with look's queries and screenshots serves both: the boot check reads all of it and
`"look"` reads only what a 20 s play samples (its first 20.5 s: a play samples on to half a second past its length),
exactly what a 20 s play would have measured. That saves a game launch per task. A
look probe that reads the log (`"probe": "log"`) keeps its own 20 s play, because a log covers the whole play. The kept
files are then under `boot_60s\`, not `look\`. Each play's progress line says how long it took, and how much of that
it waited for a machine slot (`godot-heavy.ps1`).

### Thresholds

- `{"op": ">=", "value": 1}`: a literal.
- `{"op": ">=", "calibrate": 0.5}`: `s + 0.5 * (r - s)` between the start's measure `s` and the reference's `r`.
  If the start measured nothing (its play crashed, often the bug itself; or nothing the measure selects is there yet,
  the usual case in a task that adds it), the threshold is `r` moved a quarter of `|r|` off the passing side
  (`r - 0.25 * |r|` for `>`/`>=`, `r + 0.25 * |r|` for `<`/`<=`; an `r` of 0 gives no margin: uncalibrated). If the
  reference measured nothing, or both sides measure the same, the probe fails as **uncalibrated**.
- `{"op": ">=", "start_times": 1.3}` / `{"op": ">=", "start_plus": 5}`: `s * 1.3` / `s + 5` from the start (for an
  outcome the reference is only one fair way of reaching, or a task with no reference: [task-probes.md](task-probes.md)).
  A start that measured nothing leaves no threshold (uncalibrated).

## VALID and INVALID

A task is **VALID** when all of this holds:

- the task has a reference (`seed.reference`): a task with no reference is never VALID, since its oracle side can't
  be played and nothing shows its checks can be passed (below);
- the start builds, or doesn't build exactly when a build check says `fails_at_start`;
- **the oracle passes**: with a reference, the reference passes every **required** check of every kind the check
  runs: build, boot, `log_absent`, `file_exists`, `package` and every required probe. Its checks with
  `"required": false` are notes. A `package` check asks one thing: the game's release export builds and boots. The
  checker makes the export from the game's own `Windows Desktop` preset (a preset of its own, `TaskProbe package`,
  made from it with the probe addon put in; the game's `export_presets.cfg` is put back byte for byte after it),
  plays the exported player for 20 s through the probe (one screenshot), and passes it only when the export left its
  player and the player ran to its time with no crash. A mobile game's is the same desktop export, played at the
  phone's size; no APK is made. A machine without the release export template fails the check, saying so
  (`machine\get-godot.ps1` installs the templates): it never passes a step it can't run. **The Lab's export is a
  Linux one**: its grader runs on Linux, so it makes a preset of its own, platform `Linux`, from the same `Windows
  Desktop` preset (its export filter and files, include and exclude filters, custom features, script export mode and
  texture formats; the pck embedded, x86_64) and plays that player. What only a Windows export has passes here and
  fails there: a GDExtension or native library with no Linux build, code or settings tied to the `windows` feature
  tag or `OS.get_name()`, a path written with backslashes or in another letter case than the file's (Linux file names
  are case-sensitive, in every play, not only the export). Keep a packaged game free of those;
- **the no-op fails**: the start fails every required probe outside `still_works` (or doesn't build by design): each
  is one issue of the thread, and one the start already passes rewards no work. A required check of `"weight": 0` is
  a guard wherever it sits (it rewards nothing), so the start may pass it; that lets a task hold more guards than
  `still_works`' 32. A required probe of weight 0 is a guard, not an outcome: `tools/validate-game.py` doesn't count
  it toward a task's 3 required outcome probes. At least one of the probes the start fails is not a `seen` probe: a
  seen probe is a visual check a model reads, never the outcome that shows the bug;
- every required probe in the `still_works` milestone already passes at the start. What must keep working has to work
  before the change, or the probe is broken and would fail every correct solution. A still-works probe the start has
  no samples for (its play crashed or ended early, which is often the task's own bug) doesn't count against it; one
  that finds nothing to measure in a start that ran does;
- a no-op scores zero: no check the start passes carries weight, so build, boot and `still_works` checks take
  `"weight": 0` (`tools/validate-game.py` refuses a task where one doesn't), and so does any other check true of the
  start, as the Lab scores a no-op on every check: a `log_absent`, `file_exists` or `package` check (the task check
  runs one that carries weight on the start), a probe, a `"required": false` one too, and a `judge` the start passes
  as you scored it (one that carries weight and isn't scored on the start keeps the task from VALID: what a no-op
  earns can't be told). A `code_judge` earns a no-op nothing: the Lab's has no change to review;
- every probe has a threshold, required or not: one that can't be calibrated (`uncalibrated`) stops the Lab's check of
  the task, whichever probe it is;
- no probe that carries weight, outside `still_works`, reads the same on the start and the reference, whatever its
  threshold (a literal too): it measures nothing the change moves, so it is uncalibrated, never a pass. A still-works
  probe and a required probe of weight 0 (a guard) read the same on purpose. For a calibrated threshold the Lab's
  grader refuses it too; for a literal or one relative to the start the refusal is **local only** (the Lab's grader
  grades it as it measures);
- no check is a **task error**: a probe whose select (`objects`, `widgets`, `components`, `ui`) reads nothing in the
  reference's play, a play that ran to its end (unless the measure reads 0 of nothing and 0 passes: "the crates are
  gone", for a `count`, or a `widgets` measure's `of` `count`, `any`, `all` or `sum`, as the Lab's grader has it; a
  `ui` select is refused here only, **local only**: the Lab's grader doesn't refuse it), or a task play one of whose
  inputs didn't land on the reference (`inputs_missed`, a named screenshot, an
  `optional` click that found nothing on screen and a `disabled` click on its button shown disabled aside; a click or
  a touch on a control still out of its container's view, or on one something else is over (`covered by another
  control`), and a shot whose event never came (`shot_when`), are never set aside). A probe whose `since` event never
  comes on the reference has no value there: uncalibrated when its threshold is calibrated or relative to the start,
  a fail when it is a literal.
  No version of the game can be graded by such a check;
- every required `judge` names a play of its own (`plays`, or a `route`; **local only**: the Lab's grader judges one
  with neither on the idle play and the drive), is scored by you on both sides, and the reference passes it (below);
  every required `seen` probe is read by you on both sides (below);
- no `code_judge` is required (**local only**: the Lab's grader runs a required one; a model reads the change in the
  Lab and nothing here can, so code review stays a `"required": false` quality check).

The rules marked local only are stricter than the Lab's grader: a task they refuse may still be graded in the Lab,
but never one they let through that the Lab refuses. Never read one as the Lab's behaviour.

A play input that didn't land on the start (a click on a control the start doesn't show) fails that side's check of
the play: the start failing it. Read the start's `probe.log` all the same: a start that fails only because its play
never reached the moment shows nothing about the bug.

A `judge` check is scored by you. The check plays its plays on the start and on the reference (its own `plays`, else
`look` and `drive`, which never press a task's keys or leave a title screen: a required judge with neither `plays`
nor a `route` keeps the task from being VALID whatever its scores, `judge <check>: no play of its own ...`, and
`tools/validate-game.py` refuses it; a play a probe names is the same play, played once, with the most screenshots a judge showing it
asks; with a `route`, the route too, read from each side's own copy as the Lab reads it from the copy it grades) and
saves the screenshots the cloud's judge would be shown ([task-probes.md](task-probes.md), section 3.2) under
`<task>\judge-shots\<check>\`: `start\` and `reference\` (`<play>_<nn>.png`, in the order taken; for a judge that
compares, also `BEFORE_<play>_<nn>.png` and `REFERENCE_<play>_<nn>.png`, the start's and the reference's plays the
Lab's judge sees beside that side, with no cap of 20 and no route on the REFERENCE side; and `readings.md`, the
position track and camera the Lab's judge prompt states), `ask.md` (the brief, the question, the rubric and what each
picture is),
`pictures.json` (each picture's sha256) and a blind copy, `blind\A\` and `blind\B\`, whose sides are in
`blind\key.json` (one side alone, `blind\A\`, when the start isn't played). Until you score it, a required judge keeps
the task from being VALID: its line says `judge <check>: shots saved for start/reference, answer needed`. To score:

1. Open `ask.md`, then look at `blind\A\` and `blind\B\` and score every rubric item of each from 0 to 1, as if
   each were the developer's game, before opening `blind\key.json` and `sides.md`. An item the pictures don't show
   (its moment isn't on screen, its subject is off view, hidden or never reached) scores 0 on that side: cannot be
   seen is a fail, never a pass. On the reference that means the plays must be fixed to show it, never the item eased. The blind folders hold only the
   pictures both sides have and the same names in each; each side's own count and notes (a play cut short, a route
   that couldn't be played) are in `sides.md`, read with the key.
2. Write the scores into `blind\answers.json`, one object per letter, every rubric item:

   ```json
   {"A": {"door_open": 0.0, "lit": 1.0}, "B": {"door_open": 1.0, "lit": 1.0}}
   ```

3. Check the task again. The checker scores each side by the Lab judge's pass mark (a weighted score of at least 0.6
   and no required item below 0.5). The reference must pass. On the start, every required `asked_` item of the look
   judge (`looks_as_asked`, a look the brief asks for) is below 0.5 and every required `keep_` item (a look that must
   stay as it was) at least 0.5; a look judge of `keep_` items only, in `still_works`, passes there. A judge of a task
   written before the look judges were merged keeps its old rule: one in `still_works` passes on the start, any other
   has every required item below 0.5. The line then says
   `judge <check>: scored in blind/answers.json`. If a side doesn't come out as it must, fix the rubric or the plays
   (never by easing what the task asks) and check again.

Scores stand while the pictures they were given for are the same (`pictures.json`); a side whose pictures changed
(another commit, a play that changed) is asked again, with a note. A game whose pictures are never byte for byte the
same from one run to the next (a camera, a countdown or an effect on the wall clock or on unseeded randomness) drops
them on every check: score the run's own pictures and settle that run instead of checking again (`--settle`,
"Settling a run" below). `--no-judge-shots` skips the judge plays, so a task with a required judge can't be VALID in
that run.

A judge's `route` (a project file of key inputs `[{t, key, press}]`) is read from each side's own copy, as the Lab
reads it from the copy it grades (the start's when it grades the no-op, the reference's for the oracle, the agent's
game in a try), held to the Lab's limits (1 MiB, 1 to 400 inputs, each a key by its control path at 0 to 118 s), and
played on that side for 4 s past its last input (10 s at least, 120 s at most), 8 screenshots, after the judge's other
plays; a judge is shown 20 screenshots of a side at most (unless it compares: then every one, in panels), so a route
after 20 others shows nothing. For a judge that compares, BEFORE plays the graded side's route on the start, and
REFERENCE shows none, as in the Lab. A route that can't be played (that copy has no such file, or it isn't a route) is
said in the notes, `<side>: the route <file> was NOT played: <why>`, and the judge is shown no route: score only what
the pictures show, and nothing stands in for it. So a route the reference adds is not shown on the start, as the
Lab's no-op shows none.

A `seen` probe ([task-probes.md](task-probes.md) section 2.22) is read by you too, since the check asks no model. Its
task play is played on the start and on the reference (once, with the other probes of that play), and each named shot
it reads is saved under `<task>\seen-shots\<check>\` as the Lab's model would get it: `start\` and `reference\`
(`<shot>.png`, cropped to the probe's `rect`, or the whole frame without one), `ask.md` (the Lab's prompt, what the
probe reads, what each picture is), `crops.json` (each crop's sha256) and a blind copy, `blind\A\` and `blind\B\`,
whose sides are in `blind\key.json`. The crops are at the shot's own pixels: the Lab also scales them up (`ask.md`
says how much), which the checker can't do without an image library. Until it is answered, the probe measures nothing
on either side, the task's line says `seen <check>: crops saved for start/reference, answer needed`, and a task with
a required `seen` probe is not VALID. To answer:

1. Before opening `blind\key.json`, copy every line of text you can read in each crop of `blind\A\` and `blind\B\`,
   top to bottom, exactly as shown (`?` for a character you can't read for sure, `[]` when there is no text), into
   `blind\answers.json`:

   ```json
   {"A": ["COMBO x3"], "B": ["COMBO"]}
   ```

   For a probe that reads a list of shots, give each shot's lines by its name:
   `{"A": {"before": ["12"], "after": ["15"]}, "B": {"before": ["12"], "after": ["12"]}}`.
2. Check the task again. The checker reads the answer with the Lab's own reduction (the `match`, the first number, the
   first time; the `agg` over a list of shots) and uses the values as the start's and the reference's measures, so
   the probe decides VALID or INVALID like any other. A reference whose answer gives nothing the probe reads is
   INVALID, as the Lab makes it a task error. The line then says `seen <check>: read from blind/answers.json`.

The folder is kept from one check to the next, and an answer stands while its crop is the same (`crops.json`); a
crop that changed (another commit, a play that changed) drops that side's answer, with a note, and a run whose crops
differ on every check is settled on the answers to its own crops (`--settle`, "Settling a run" below). A start that doesn't
build by design is never played: only the reference is saved, as `blind\A\`. In the Lab the model must read the start
and the reference the same 3 times out of 3, which this check can't show: a crop you can read only with a `?`, or
only at full zoom, may not.

### Settling a run

`python tools\task-check.py %GGF_ROOT%\games\<slug> --task <name> --settle` (`--out DIR` when the run used one; the
task by name or by the same `.json` file the run checked) plays nothing. It takes the task's kept run,
`<out>\<task>.json` and its folder, and decides it on the answers written into each judge's and `seen` probe's
`blind\answers.json` for that run's own pictures, by the same rules a check that reads them applies: the same pass
mark, the same start and reference rules, the same no-op score, a `seen` probe's threshold and pass made from the
answered values as a check makes them. Every other row of the run (its probes, builds, boots, thresholds) stands as
the run wrote it. It prints the task's verdict line and writes the final result over `<task>.json`, with the run's
own result and what it checked under `settled`. It refuses, and writes nothing (`REFUSED <task>: why`), when:

- there is no kept run, or the run is no verdict (an `ERROR`, a task that didn't validate, a run that stopped before
  it graded the start, a row the checker couldn't run): check the task again;
- the task file isn't the one the run checked (its sha256 differs from the run's `task_sha256`);
- any picture or crop differs from the sha256 its `pictures.json` or `crops.json` lists, a side's folder holds a
  picture more or less than the run saved, the blind copy holds a file more or less than both sides share or one that
  isn't the file of the side the key names, or `pictures.json`, `crops.json` or `blind\key.json` isn't the file the
  run saved (the result records their sha256 as `bound`; a run of an older checker has no record, and is bound by the
  rest);
- any picture, list or key (or a judge's `readings.md`) was written after the run wrote its result, or
  `blind\answers.json` is older than the pictures and the key it answers (each answer is for that run's pictures);
- an answer is missing or can't be read (every letter of the key, every rubric item, each shot's lines) for a
  required check, or for an optional one whose answers file is there;
- a check that needs a `seen` probe was never graded the way the answer now grades that probe (only a check again can).

Score blind as always: before opening the key. A settle can't see when the key was opened; it records the file times
it saw (`settled.answers`: when the answers, the newest picture and the key were written, and the key's last read as
the file system keeps it). A settled result settles again from the run it keeps; checking the task again replaces it.

A task with no reference is never VALID: its first reason is `no seed.reference: the oracle side can't be played,
...`. The check still plays its start and holds it to the start's rules (it must build, fail every required probe
outside `still_works` and pass its still-works probes, and every required probe needs a threshold it can make), so the
reasons that follow say what the start does. Every task has a reference (godot-write-tasks section 1;
`tools/validate-game.py` rejects one without): a task whose thread has no accepted end can't be validated at all.

## Results

- One line per task on the console: the verdict (`VALID`, `INVALID`, or `ERROR` when the checker couldn't check it),
  the task, and its reasons joined by `; `. Progress goes to stderr.
- `<repo>\.task-checks\<task>.json` (format `task-check/1`; `--out` moves the folder; a task file that isn't JSON gets
  none, only its console line and its row in `progress.json`):
  - `verdict`, `reasons` (why INVALID or ERROR), `notes` (the reference's failures that don't decide, written
    `reference fails X (<kind>): <detail>`); a reason or note carries at most 160 characters of a check's detail, the
    whole of it is in that check's row;
  - `start` and `reference`: the side's `commit`, whether it `built`, and how its copy was made (`files`,
    `lfs_linked`, `lfs_copied`, `engine`: the Godot exe used, `slots`: `godot-heavy` or `direct`);
  - `probes`: an object keyed by each probe check's name: its milestone (`group`), `required`, `op`, `expect`, the
    `start` and `reference` measures (null where that side measured nothing, which is not a measured 0), the
    `threshold` (null when uncalibrated), and whether each side passed (`start_passed`, `reference_passed`);
  - `start_checks`, `reference_checks`: a list with every check's row on each side, in the task's order (`name`,
    `kind`, `group`, `required`, `weight`, `passed` and a `detail`). A probe's detail is its `describe`, then
    `| measured V, threshold OP T`, with what the start and the reference measured when the threshold came from them,
    and why it has no value: `... | measured 0, threshold >= 89.9957 (start 0, fix 179.991)`, `... | measured nothing,
    threshold >= 1: no value in the window (...)`; a probe left without a threshold reads `uncalibrated: X: ...`
    instead. A detail starting `not asked` is a check that side doesn't run (judges on either side, which you score
    in their `judge-shots` folder; on the start, everything but its probes and a `fails_at_start` build check): it
    shows as passed and counts for nothing. A package check's detail is `packaged and ran 20 s` when it passed, else
    `packaging failed ...` or `packaged, but the packaged game didn't run cleanly`. A detail
    starting `task error:` is a check no version of the game can be graded by (VALID and INVALID);
  - `task_sha256` (the SHA-256 of the task file as the run read it: the file as committed on the `tasks` branch, or
    the `.json` given by path; a checkout with other line endings hashes differently), `task`, `game`, `at` (when,
    UTC), `seconds` (how long the check took) and `evidence` (the task's folder of play files, below).
- `<repo>\.task-checks\<task>\<side>\<play>\` (`<side>` is `start` or `reference`): a folder per play, named `look`,
  `drive`, `play_<name>` for a task play, or `boot_<seconds>s` for a boot (on the reference it also serves `look`).
  The result doesn't name a check's play: it is the check's `play` in the task file. Each holds `probe.json`
  (below), `play_spec.json` (what the play was given: the frame's size, its seconds, scene and inputs, and its queries
  with their ids, kinds and selects; a `look` that a boot served has its queries in the boot's), `probe.log` (the
  probe's own lines: where each teleport put the player, each click, touch, wait and error), the screenshots
  `shot_00.png`, `shot_01.png`, ... (PNGs of the frame, UI included, evenly over the play), `play.log` (the game's own
  log) and `output.txt` (what the play's job printed, the machine slot's waits among it; empty when it printed
  nothing, as under `--direct`). `build\build.log` is the engine's log of a build that failed. Read these when a value
  surprises you. Checking a task again replaces its folder.
- A play's `probe.json` holds, per sample time: in `track` a row `[t, x, y, z]`, the player's position (`[t]` alone
  while the play has no player); in `camera` a row `[t, x, y, z, pitch, yaw, fov]`; in `measures` the samples of
  every query the play's probes asked; and `query_errors`, the lines of what the probe couldn't read (only when
  there are some). `inputs_sent` counts the play's input rows as they were sent, and `inputs_missed` lists those that
  found nothing to act on (a tap on a control that isn't on screen). A key of `measures` is a query's id, `q` and ten
  hex digits made from what the query selects (its kind with its select or rect), so a query has the same id in every
  play and on both sides, and probes that read other fields of one selection share one query. The file doesn't name
  the checks: `play_spec.json` beside it gives each id's kind and select, which you match with the check's measure in
  the task file. A sample holds either `rows` (one per node, widget or element matched, with its `name` and the fields
  asked for) or a `value` with the kind's own keys ([task-probes.md](task-probes.md), under each kind). A `spawns`
  sample holds running totals since the play started; the checker reads each sample's rise over the one before.
- `<repo>\.task-checks\<task>\judge-shots\<check>\`: each judge check's pictures to score (VALID and INVALID
  above); the result's `judges` lists them, each `answer needed` or `scored in blind/answers.json` with each side's
  result (`answered`) and `bound`, the sha256 of its `pictures.json` and `blind\key.json` as the run saved them.
- `<repo>\.task-checks\<task>\seen-shots\<check>\`: each `seen` probe's crops to answer (above); the result's `seen`
  lists them, each `answer needed` or `read from blind/answers.json`, with `bound` the same way (`crops.json`). A
  settled result (`--settle`) also has `settled`: when, the run's own verdict, reasons and result (`run`), when the
  run's result was written, and per check the answers' sha256 and the file times seen.
- `<out>\progress.txt`: `task check: D of T task(s) done, started HH:MM, M min so far` (`, finished` at the end), each
  finished task's console line with its minutes (`(18 min)`) and a line per judge check waiting for an answer, and
  `checking <task>, then N more`. `progress.json` (format `task-check-progress/1`) holds the same: `started` and
  `updated` (seconds since 1970), `tasks` (in order), `done` (each finished task's `task`, `verdict`, `reasons`,
  `seconds`, `judges_pending` and `seen_pending`) and `finished`.
- `.task-checks\` is git-ignored: when the game's `.gitignore` doesn't name it, the checker adds it to the repo's own
  `.git\info\exclude`. Never commit results.

## Common reasons and fixes

An entry in code font is the line as the checker prints it (`X` a check's name, `N` a number, `...` the rest). A line
that says its own fix (`fetch it, or fix the task`, `pass --direct`, `name one with --task NAME`) has no entry: do
what it says.

**`start already passes every required probe`** (or **`start already passes required probe X`**, for some of them).
The bug doesn't show in what the probes measure.
- The play never reaches the situation: the idle `look` stands at the spawn, the `drive` walks a fixed pattern. Write a
  task play that gets there: a `teleport` input (`{"t": 0.2, "teleport": [x, y, z], "yaw": 90}` places the player,
  in metres, y up; take the coordinates from the scene file, or from the `track` in a play's `probe.json`), its own
  `scene` (`res://scenes/Arena.tscn`) and `args` (`["-scenario", "2"]`), and the inputs that trigger the bug.
- The measure is the wrong one: compare the start's and the reference's `probe.json` samples for the field you read
  and pick one that differs.

**`uncalibrated: ... the start and the reference both measure N`.** The measures are equal on both sides, so there is
nothing to put a threshold between: the probe doesn't see the change. Measure something the fix changes (a
different field, window or play), or use a literal value when the fact is a count or a boolean. A probe that isn't
required and can't be calibrated is a reason too (`X has no threshold: ...`, below). `uncalibrated: X: the reference
measured nothing (...)` (or `the start measured nothing (...)`, for a threshold relative to the start or with a
reference that measured 0): read the reason in brackets as below. In a task with no reference, a required probe the
start leaves uncalibrated reads **`X has no threshold: uncalibrated: ...`**: no solution could pass it.

**`X reads the same on the start and the reference (N): uncalibrated, never a pass: ...`.** A probe that carries
weight, outside `still_works`, measured the same value on both sides, whatever its threshold (a literal too, local
only: the Lab's grader refuses only a calibrated one): it measures nothing the change moves, so it decides nothing between doing nothing and the fix. Compare both sides'
samples in `probe.json` and read what the change moves (another field, select, play or window: a widget hidden on both
sides, a property that stays empty, a select that reads the wrong node), never a looser threshold.

**`no seed.reference: the oracle side can't be played, ...`.** A task with no reference can't be validated: nothing
shows its checks can be passed. Give it the thread's accepted end as `seed.reference` (godot-write-tasks section 2);
the reasons after this line say what the start does.

**`judge X: no play of its own (no `plays`, no `route`): ...`.** A required judge shown only the idle `look` and the
`drive` never sees what its rubric asks (they never press the task's keys or leave a title screen), and an item that
can't be seen scores 0, so it is never VALID whatever its scores (local only: the Lab's grader judges it on what
those two plays show). Give it `plays` of its own that show each item at its
moment ([task-probes.md](task-probes.md), section 3.2).

**`no samples in the window (the play ended at N s)`.** The play ended before the window: the window or `at` lies past
the play's `seconds`, or the game crashed or quit (see the play's log). **`the play wrote no probe file`**: the game
never got to play (a crash at load: see the play's `play.log` and `output.txt`), or the play was stopped at
its timeout (its seconds and 300 s, or `--timeout`) before its end (its progress line then shows it took that long).

**`no value in the window (nothing it selects was measured)`.** The selection matched nothing, or nothing it matched
has that field, or a `player` or `camera` measure's play never found the player or the camera (name the player with
the task's `player` select: [task-probes.md](task-probes.md)). A `name` wildcard takes every whole name it fits
(`Projectile*` takes a `ProjectileSpawner` too), so select the things themselves by their class, script or group.
`; the probe said: ...` quotes the line of the play's `query_errors` about this measure's own query (what the probe
couldn't read; it starts with the query's kind, and its id when it is about that query alone); a line with the kind
alone can be another query's of that kind in the same play. The `rows` in the play's `probe.json` show what was found,
and `probe.log` beside it what the probe did (a `teleport_to` that found nothing, a widget click or a tap that
matched no control).

**`a stage of the play didn't land: <kind> <target> at N s: ...`.** A `pin`, a `damage` or a `set` of the probe's play
reached nothing (no object matched, the one matched has no `take_damage`, no property took the value), so whatever
the play read is of a contact that never happened and no probe of that play has a value on that side
([task-probes.md](task-probes.md), section 1.4). On the reference, fix the stage: its select names what the start
and the reference both have, and the play's `probe.log` says what each stage reached. On the start alone it is the
start failing the check.

**`of` defaults to `count`.** For `objects`, `components`, `widgets` and `ui` measures, `of` combines the selected
rows of one sample, and without it a field like `y` counts the rows whose value isn't 0 instead of reading the value.
Set `"of": "first"`, `"max"`, `"min"` or `"mean"` when you mean the value. "First" is the first in tree order, which
an edit to the scene between the start and the reference can change: narrow the select (name, group, `near`) so it
picks the node you mean on both sides.

**More than 200 matches.** The probe keeps at most 200 rows a sample in `probe.json`, but reads every match: the
sample's `total` is how many matched and `full` sums up every match's numeric value of each field (`n`, `nonzero`,
`sum`, `min`, `max`). `count` reads `total`, and `of` (`count`, `any`, `all`, `sum`, `min`, `max`, `mean`) reads
`full`, so neither stops at 200. Only `"of": "first"` and values read through `match`, `to_angle` or `to_axis` read the
200 rows alone.

**Angles.** Angle fields (`yaw`, `pitch`, `roll` and the others task-probes.md lists) are normalised to (-180, 180],
so a raw yaw jumps from 180 to -180 and `mean` or `delta` across the wrap mean nothing. Use `"to_angle": 90` (the
shortest distance to 90 degrees, 0-180) or `"to_axis": 90` (the distance to that axis, 0-90: a direction and its
opposite are one axis), with the threshold on that distance.

**A mobile game's drive moves nothing.** The drive pushes where a virtual stick usually is (the lower left of the
screen) and taps the lower right. A game whose controls are elsewhere needs its own task play: `tap` and `drag`
inputs on its controls by node name (`{"t": 1, "tap": {"widget": "FireButton"}}`). A touch that found no control is in
the play's `query_errors` and `inputs_missed` (`probe.json`) and in `probe.log`.

**`reference fails X: task error: ... in the reference's <play>, its select {...} matched nothing in N samples: the
check reads nothing even on the task's own fix`** (an `objects`, `widgets`, `components` or `ui` select) (`X on the reference: task error: ...` for a probe that isn't
required; `nothing its select ... matched had a value for F`, or `... : the task's own fix fails it` for a count). The probe's select finds nothing in the reference's play, a play that ran
to its end, so no build can pass it: the select names something the reference doesn't have, or the play never
reaches it. Select by what the thing does or carries (`has`, `near`, a group or class the start has), read the rows
in the reference's `probe.json`, and check that the play reaches the place.

**`... task error: ... in the reference's play P, an input did not land (<kind> <target> at N s (...)): the task's own
fix can't be driven by its play`.** A click found no control, a touch no widget, a stage nothing to act on, on the
reference itself: the play can't drive the task's own fix, so every probe of that play is the task's error. Drive the
play by what the reference shows at that moment: the control's on-screen text the instruction quotes, a wait for the
scene to change, a stage on something the start and the reference both have (`probe.log` says what each input hit).
`covered by another control`: a dialog, a popup or an overlay is over the control (`probe.log` names it); close it
first with the player's own input (its button, the key the game closes it with). `scrolled out of its container's
view`: the control is hidden by more than its own list (a Control that only clips, a list that can't move that far);
a list it sits in scrolls by itself. `its event never happened` (`shot_when`): the shot's `when` never held on the
reference within its `within`: read what the event's measure selects in the reference's play.
**`its event never happened (...)`** in a probe's detail: the measure's `since` never came in that play, so the probe
has no value; on the reference, read what the event selects there.
**`the play's input did not land: ...`** in a start row is the start failing that check: read the start's `probe.log`
to see whether the bug, or a play that only fits the reference, made it miss.

**`X has no threshold: uncalibrated: ...`** for a probe that isn't required. The Lab's check stops on any probe it
can't calibrate, so this is a reason too: give it a measure the change moves, a literal, or drop it.

**`reference fails X: packaging failed ...`.** A required `package` check whose release export wasn't made: `(exit N)`
is the engine's failure (its log is kept as `reference/package/package.log`), `: the export left no player` an export
that wrote nothing, `: ... no preset named "Windows Desktop"` a game without its release preset, and `: this machine
has no ... release export template` the machine's own lack (`machine\get-godot.ps1`). **`reference fails X: packaged,
but the packaged game didn't run cleanly`**: the exported player crashed or stopped before its 20 s; its play is kept
as `reference/packaged/`.

**`judge X: shots saved for start/reference, answer needed`** (or **`judge X: not played (--no-judge-shots), answer
needed`**). A required judge isn't scored yet: score it (VALID and INVALID), then check again. **`reference fails judge
X as you scored it (...)`**: the reference doesn't show what the rubric asks in the pictures; fix the plays so the
pictures reach the moment (or the game, so the asked thing appears on screen), never the item: it keeps the
instruction's words, and is never dropped, pointed elsewhere or loosened. **`start already meets
a required item of judge X as you scored it (...)`**: the unchanged game already looks as asked, so the item doesn't
see the change. **`start fails still-works judge X as you scored it (...)`**: what must still look as it did doesn't
at the start: the item or its plays are wrong.

**`no required probe outside still_works but seen ones: ...`.** The start fails only `seen` probes. A seen probe is a
visual check, never the outcome: add a required probe of what the thread changed (godot-write-tasks skill, section 5).

**`X is a required code_judge: ...`.** Make it `"required": false` (code review is a quality check): no check here
can run it (local only: the Lab's grader runs a required one).

**`start fails still-works X`.** The game works at the start, so a still-works probe that fails there is broken: it
doesn't find the HUD, the node or the value it looks for. Fix the probe (see the play's `probe.json`), never the
threshold.

**`reference fails X`.** The oracle fails: the check or the reference is wrong. For a probe: the reference doesn't do what the probe asks (a threshold on the wrong side: check `op`), or
the reference's play doesn't reach the situation either. The play's folder (`.task-checks\<task>\reference\<play>\`,
see "Results") tells which: its screenshots, the `track` in `probe.json`, and `probe.log`, which says where each
teleport put the player and what each click or touch hit. A `teleport_to` goes next to the match nearest the player,
so a select that also matches another node can take the player there instead: select the things themselves.
`reference fails boots_clean: crashed` means the reference crashes in a plain boot (`didn't finish its run`: it
stopped before its `seconds`; `timed out`: it ran past its timeout). `reference fails X: build failed (exit N: ...)`
means the reference doesn't build as committed; every check that `needs` it then fails `not run: needs X`, and so on
down the chain. The reason names the first cause and `reference\build\build.log` holds the rest, as for `start doesn't
build` below. For a required `log_absent` (`N matching log line(s): ...`) or `file_exists` (`0 file(s) match`): the
reference itself fails it, so no solution like the reference can pass: fix its pattern or glob, or make it
`"required": false` with `"weight": 0`.

**`start doesn't build`.** The start's scripts don't parse on Godot 4.7 as committed, or its import fails. The reason
itself names the first cause after the exit code (`didn't build (exit 1: ...)`), in one line of at most 200
characters: the log's first script error with the place it names (`Parse Error: ... at GDScript::reload
(res://game/hero.gd:12)`). `start\build\build.log` holds the import's log and the script load's: read its `SCRIPT
ERROR` lines first. Pick a start that builds, or, when making it build is the task, set `"fails_at_start": true` on
the build check (then no threshold may be relative to the start). `didn't build (timed out)` is a build that logged a
script error and then ran past `--build-timeout`. A build that stops with no word about the game is no verdict: see
the ERROR entry `... didn't build: Godot stopped twice ...` below.

**`start: project.godot names Godot ... in config/features: a task's commits must be Godot 4.7 projects as
committed`** (or `reference: ...`). That commit was made on another Godot, and the checker never upgrades a project.
Pick a start and a reference from the part of the game's history made on 4.7.

**`... LFS object(s) ... aren't in ...'s local store`** (an ERROR line, not a verdict): fetch them,
`git -C <repo> lfs fetch origin <commit>`, and run again.

**`ERROR   <task>: the checker couldn't check it: ...`.** The checker itself failed on that task, so the line says
nothing about the task; the run goes on with the next one, and the exit code is 1. The rest of the line says why: a
missing LFS object (above), a machine without Godot, PowerShell refusing `godot-heavy.ps1`, a build that stopped (next
entry), a game that couldn't be started on a desktop of its own, a `Platform.json` that says neither landscape nor
portrait, a disk error. Fix that and run again. One check's row reading `the checker failed (...)` is the same for
that check alone.

**`... didn't build: Godot stopped twice (exit N) with no script error: ...`** (or **`Godot was stopped at the
build's time limit (N s) ...`**; an ERROR line). The build failed without a word about the game: no script error in
its log, so the engine stopped, or the build ran into `--build-timeout`. The checker tries a build that stops this
way once more (the progress line `build stopped (exit N) with no script error, retry 1`); stopped again, or stopped
at the time limit (never tried again), it is the machine's failure, not the game's, and the task has no verdict. The
line names the kept log (`<side>\build\build.log`). Run the check again; when it stops the same way every time, read
that log for what stopped.

**A Python traceback that ends the run.** A fault of the checker's own while it checks a task is that task's ERROR
(`the checker couldn't check it: <its type>: ...`) and the run goes on, so a traceback means it failed outside any
task's check (reading the machine config, say). The tasks it finished keep their results, `progress.txt` names the
one it was checking, and the scratch copies are deleted (unless `--keep`). Report it with the traceback, and check
the remaining tasks with `--task`.

**`couldn't delete <folder> (...): delete it by hand`** (a progress line). A file of a scratch copy is held by a
process outside the checker (a game that outlived an interrupt, a viewer); the run goes on. Close what holds it and
delete the folder.

**`a no-op scores N, not 0: give X "weight": 0, or drop them`.** Those checks already pass at the start (`still_works`
probes, probes that aren't required, a weighted `log_absent`, `file_exists` or `package` check, a weighted judge you
scored as passing on the start), so a run that changes nothing would score `N` (the weighted share of checks
passed). Give each `"weight": 0` (a required one still gates), or drop it.

**`no required probe outside still_works to check the start with`.** Nothing is left to show the start failing: every
required probe is in `still_works`, or none is required. Add a required probe outside `still_works` for each issue of
the thread (godot-write-tasks skill, section 5).

**`start builds, though X says it doesn't (fails_at_start)`.** The start built, though its build check says making it
build is the task. Drop `fails_at_start`, or pick the commit where the build broke.

**`the task doesn't validate: ...`.** The task breaks its schema or a rule of the task format (up to five problems,
worded as `tools/validate-game.py` words them for the task; `... is not JSON (...)`: the file doesn't even parse). Fix
the task file and check it again. The validator checks more than this: the long-thread bar and the no-op weights of
each task, and on its `repo:` lines the game repo itself. Those never change a task check's verdict, but a game is
delivered only with the validator's VALID too ([game-format.md](game-format.md)).

**`... the game couldn't be started on a desktop of its own (desk.py: ...)`** (an ERROR line). `desk.py` itself
failed before the game ran: it makes a Windows desktop for the play, and a session with no interactive window
station (a service, some remote shells) can't. The machine's fault, never a verdict on the game: run the check from an
interactive session.

**`task check: only N GB free on C: (floor 50 GB; GGF_MIN_FREE_GB / min_free_gb). ...`** (exit code 1). The scratch
copies' drive is below the machine's floor ("Requirements"): the run didn't start, or stopped after the tasks it had
finished. Free space on that drive, or pass `--scratch` on a drive with room (its LFS files are then copies).
