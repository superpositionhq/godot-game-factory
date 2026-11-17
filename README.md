# godot-game-factory

Game-**creation** data: how a game gets made, step by step, with the finished project as ground truth.

We build new 3D games in Godot 4.7 (GDScript), for the desktop (Windows, the Forward+ renderer) or for Android phones
(the Mobile renderer, touch only), and record the creation as it happens: every scene, resource and script as the text
it was written as, the engine's own steps with timestamps, code commits, every tool call, prompt and reply of the
sessions that build the game, and recorded playtests of each scenario by an in-game bot (gameplay video, game audio
and inputs). Every part of that is here ([AGENTS.md](AGENTS.md), "What is here").

**Priorities (user decision).** What ships is what matters, in this order: the game plays; the game builds (the
import without errors and the Windows release player; a mobile game is played and recorded as that player at the
phone's size, and its APK is built at release where the machine has the Android toolchain); the dataset holds the replay scripts and the git log.
The AutoPlay bot should still play like a human (human-like input, aim and camera), but bot work never blocks a
release: one recorded scenario per game (one video) that shows the game running is enough, whatever the result
(win/lose/timeout is metadata). No tuning for win rates, seed sweeps or "clean" runs, and no re-runs or re-recordings
to improve how the bot plays. No retest loops: every GPU or engine run costs the shared machine and holds up
delivery, so run the minimum once and report; re-run only when the user asks. Game-session work never blocks dataset
packaging or sharing.

## Getting started

**Before every new game, update godot-game-factory:** `git -C <GGF_ROOT>\godot-game-factory pull`, then
`powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\machine\bootstrap.ps1` so the skills your
agent reads are the new ones. The tools, task rules and validators change often; a game made with old ones can fail
the Lab's checks. A game already in progress keeps its own copies of the template's files; it gets the current
AutoPlay drop-in with one run of
`powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\autoplay\install.ps1 -Game <GGF_ROOT>\games\<slug>`
([docs/autoplay-contract.md](docs/autoplay-contract.md)).

On a fresh Windows 11 PC (8+ threads, 16 GB RAM or more, 100 GB free, a GPU with Vulkan and a current driver), with
an account for the coding agent (Claude Code, or OpenAI Codex CLI with a ChatGPT account or API key). The engine
needs no account and no licence. Contractors need no GitHub account: the game stays on the PC and ships in the
dataset zip. Only staff who push the private `godot-game-<slug>` repos need a GitHub account in `<org>` (the
organisation that owns the game repos):

1. Get `machine/setup.ps1` (Download ZIP on github.com, or `gh api`; [docs/new-machine.md](docs/new-machine.md)) and
   run the one command: `powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org>` (add `-Agent codex` or
   `-Agent both`; without it, the agents the machine has; add `-Android` on a machine that builds mobile games' APKs). It installs the
   toolchain through winget (git, the GitHub CLI, Python, and the Codex CLI for Codex), offers the GitHub sign-in
   (staff only), clones this repo into the root, puts the pinned Godot editor and its export templates into
   `<root>\godot\<version>\` (`machine/get-godot.ps1`; nothing machine-wide), runs `machine/bootstrap.ps1` (which asks
   before installing the recording hooks), with `-Android` `machine/get-android.ps1` (the JDK, the Android SDK and the
   keystores, into `<root>\android\`), and `machine/check.ps1`, and ends with a PASS / TODO list.
2. Do the TODOs only you can do (signing in to Claude Code or Codex) and run setup again until nothing is left.
3. Start the first session: solo in a terminal in the root (`claude`, or `codex -s danger-full-access`), one game with
   [docs/briefs/solo-game.md](docs/briefs/solo-game.md).

## How a game goes from idea to dataset

1. **Brief, story bible and design doc**: the game's `Brief/brief.md` (the brief as given) and `Brief/design.md`
   (pitch, systems, scenes, scenarios, art and story).
2. **New project**: `templates/new-game.ps1` creates `%GGF_ROOT%\games\<slug>` from the Godot 4.7 template, a desktop
   game or, with `-Platform mobile -Orientation landscape|portrait`, an Android phone game (`Platform.json` at its
   root): the AutoPlay drop-in (`addons/autoplay/`) and the scenario list, `ReplayConfig.json`, `Scripts/godot.ps1`,
   hooks that record every action and commit, the first import, a private GitHub repo.
3. **Build**: the session (Claude Code or Codex) follows the `godot-commit-always`, `godot-game-session` and
   `godot-sound` skills and the skill of the game's platform (`godot-desktop-game` or `godot-mobile-game`). Scenes,
   resources and scripts are text files it writes and commits; what only the engine can make comes from committed
   generator scripts (`steps/`); every action is recorded (`workflow.jsonl`, the action hooks of either agent, git
   history).
4. **AutoPlay, then the recording**: once scenario 1 plays, the game wires the drop-in and its bot
   ([docs/autoplay-contract.md](docs/autoplay-contract.md)), tests one run by hand (`Scripts/godot.ps1 autoplay`,
   `tools/godot-pipeline/validate-run.ps1`) and tags `milestone/autoplay-<n>`. The session then runs the recording
   pipeline itself (`tools/godot-pipeline/pipeline.ps1 <slug>`): the release player of the commit, one recorded run
   per scenario, one gameplay mp4 each at the game's exact size, with stills for the framing check
   ([docs/godot-pipeline.md](docs/godot-pipeline.md)). A recording needs no screen: the player writes its own frames
   and sound.
5. **Scrub and privacy**: no user names, machine paths or tool names in anything that ships (the packager's scrub rules
   and scan, the release build's leak scan; `tools/validate-game.py` checks a repo's tracked text for the names).
6. **Dataset v1**: first the session ensures AutoPlay (the drop-in current through `install.ps1`, every scenario wired,
   the bot written, each scenario's hand test passing, `milestone/autoplay-<n>` tagged; the `godot-game-session` skill,
   "Dataset"); then, at the release commit, the pipeline builds its release player (for a mobile game its APK too, where the machine has the Android toolchain)
   and records each scenario, the creation replay (`godot_replay.py release`) rebuilds the game from its history and
   makes `ReplayScripts/`, and `tools/package-dataset.py` packs the commit with the three into
   `games\<slug>\Dataset.zip` and the repo's `Dataset/` (`Dataset.pending.zip` while the replay
   is missing; without a recording it packages nothing).

## Dataset format (layout v1, all games)

Every game is delivered in **dataset layout `godot-dataset-layout/v1`** ([docs/game-format.md](docs/game-format.md)):
the creation record (`git.log`, `workflow.jsonl` with the person's directions, `ReplayScripts/`, the full git history
and the recorded sessions in `History/`), the brief and design doc, the game's tasks, the project, per-scenario gameplay
videos, README screenshots and the built player:

```
<game>/                          games\<game>\Dataset.zip (store content included; git-ignored)
  README.md
  git.log
  workflow.jsonl                 the creation's operations + user.direction rows (the person's directions)
  Brief/                         brief.md (the original brief), design.md (design doc, story bible, status)
  History/                       <game>.bundle (main up to the release, and each task's start branch) + lfs/objects/ (every LFS object) + sessions/ (every prompt, reply and tool call); not in the repo Dataset/
  Tasks/                         the game's tasks, each <name>/task.json (agent) + grader.json; from the tasks branch
  GodotProject/                  not in the repo Dataset/
  ReplayScripts/                 the creation replayed headless, with its verification report
  Gameplay/<game>_S<n>.mp4       one video per recorded scenario of the release version (one is enough), game audio included; 1920x1080, or 1080x1920 for a portrait mobile game
  Screenshots/                   the README's hero and gallery
  Build/                         the Windows release player; not in the repo Dataset/
                                 (a mobile game: also its Android APK, which its release requires)
  manifest.json                  a mobile game's says its platform and orientation
```

Each game repo keeps the same delivery in `Dataset/`, minus `GodotProject/`, `Build/`, `History/` and `Tasks/` (its
tasks live in `Tasks/` on the repo's orphan `tasks` branch, never on main). The game repo itself follows the same
format's repo rules (one `assets.manifest.json` format, every imported file committed with its `.import` and every
script with its `.uid`). Machine-readable: [docs/game-format-v1.json](docs/game-format-v1.json),
[docs/dataset-layout-v1.json](docs/dataset-layout-v1.json), [docs/schemas/](docs/schemas/). Build it with
`python tools/package-dataset.py <slug>` at the release commit, once it has its pipeline build, a valid recording and
the creation replay's package: it writes `Dataset.zip`, or `Dataset.pending.zip` while the replay is missing (a game without a gameplay video is rejected at upload: without a recording the packager refuses);
before its first run a repo's `Dataset/` stays as the template made it. Check a repo and its datasets with
`python tools/validate-game.py <repo>` (or `--dataset <zip>`); its "not packaged yet" warning is expected before the
packager's first run.

## Read first

- [docs/autoplay-contract.md](docs/autoplay-contract.md): what each game implements so a bot can play and record it
  (the AutoPlay drop-in, its install step, the hand test).
- [docs/godot-pipeline.md](docs/godot-pipeline.md): a game's engine runs (`Scripts/godot.ps1`), the machine-wide job
  slots, the build and gameplay recording pipeline (`tools/godot-pipeline/`).
- [docs/godot-replay.md](docs/godot-replay.md): the creation replay (`tools/godot-replay/`) and the rules that keep a
  game's history replayable.
- [docs/game-format.md](docs/game-format.md): the final game format (repo + Dataset.zip layout v1), the platform
  (`Platform.json`), its schemas and `tools/validate-game.py`.
- [docs/task-check.md](docs/task-check.md): checking a game's task on your own machine (`tools/task-check.py`: the
  start fails, the reference passes), and [docs/task-probes.md](docs/task-probes.md): what a task's checks can
  measure. [docs/task-try.md](docs/task-try.md) is internal: we run `tools/task-try.py` on submitted tasks to measure
  how long a strong agent takes; contractors don't run it.
- [docs/godot-pipeline.md, Dataset packager](docs/godot-pipeline.md#dataset-packager): the per-game dataset
  (`tools/package-dataset.py`) and its scrub.
- [AGENTS.md](AGENTS.md): what every session reads first (Claude Code through [CLAUDE.md](CLAUDE.md), Codex
  directly): the skills in `skills/` (godot-commit-always, godot-game-session, godot-desktop-game, godot-mobile-game,
  godot-sound, godot-write-tasks), the priorities, how the two agents differ, and the rules for agents working here
  (each with the failure behind it).
- [docs/new-machine.md](docs/new-machine.md): setting up another Windows machine (`machine/setup.ps1`, which runs
  `machine/get-godot.ps1`, `machine/bootstrap.ps1` and `machine/check.ps1`; `machine/get-android.ps1` for the APKs).
- [docs/briefs/](docs/briefs/README.md): the prompts that start a game session (solo and coordinated).

## Layout

```
tools/godot-pipeline/              release player from a commit, recorder, run checker, stills, gameplay videos; autoplay/ = the AutoPlay drop-in
tools/godot-replay/                creation replay: the game rebuilt from its history, commit by commit; ReplayScripts/ of the dataset
tools/package-dataset.py           a game's dataset: Dataset.zip (Dataset.pending.zip while a part is missing) and the repo's Dataset/
tools/validate-game.py             a game repo, its tasks or a dataset checked against the game format; the one reader of Platform.json
tools/task-check.py, task-try.py   a task checked on the engine; tried with a coding agent (internal) (task_check/)
tools/thread-stats.py              a thread's own commits counted against the task floors (git only)
tools/art-style.py                 a game's art style: picked from docs/art-styles/, written to the game as its art bible
tools/sfx.py                       sound effects for a game: search Freesound, fetch into the repo, measure (godot-sound skill)
machine/                           machine setup: setup (entry point), the pinned engine, the Android toolchain, bootstrap/check, godot-heavy limiter, recording hooks, ffmpeg
templates/                         Godot 4.7 game skeleton (desktop, and the mobile files laid over it) + new-game.ps1
skills/                            godot-commit-always, godot-game-session, godot-desktop-game, godot-mobile-game, godot-sound, godot-write-tasks (agent-neutral; bootstrap installs them for each agent)
docs/                              the contracts and formats; docs/briefs/ = session prompts; docs/art-styles/ = the 100 art style guides
```

Machine paths in docs are written `%GGF_ROOT%` (the GodotWork root: env `GGF_ROOT`, else
`%USERPROFILE%\.godot-game-factory\config.json`, else `%USERPROFILE%\GodotWork`); see
[machine/README.md](machine/README.md).

Full packages (tens of GB with the project snapshot) do not go in this repository.
