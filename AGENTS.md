# AGENTS.md — godot-game-factory: instructions for every session

This repo coordinates coding-agent sessions (Claude Code, OpenAI Codex CLI or Google Antigravity) that build Godot 4.7
games, for the desktop (Windows) or for Android phones (`%GGF_ROOT%\games\<slug>`, private `<org>/godot-game-<slug>`
repos, `<org>` = `github_org` in the machine config) and turn them into game-creation datasets. `%GGF_ROOT%` is the
machine root (env `GGF_ROOT`, else `%USERPROFILE%\.godot-game-factory\config.json`, else `%USERPROFILE%\GodotWork`); see
[machine/README.md](machine/README.md). Claude Code reads this file through [CLAUDE.md](CLAUDE.md); Codex and
Antigravity read it directly (and through `<root>\AGENTS.md`).

**Before every new game, update godot-game-factory:** `git -C <GGF_ROOT>\godot-game-factory pull`, then
`powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\machine\bootstrap.ps1` so the skills your
agent reads are the new ones. The tools, task rules and validators change often; a game made with old ones can fail
the Lab's checks. A game already in progress keeps its own copies of the template's files; it gets the current
AutoPlay drop-in with one run of
`powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\autoplay\install.ps1 -Game <GGF_ROOT>\games\<slug>`
(its own commit; [docs/autoplay-contract.md](docs/autoplay-contract.md)). Every release starts by running it again to
ensure AutoPlay, a required step (godot-game-session skill, "Dataset", release step 1).

Skills (one source, [skills/](skills/); `machine/bootstrap.ps1` copies them to `~\.claude\skills\` for Claude Code,
`~\.agents\skills\` for Codex and `~\.gemini\config\skills\` for Antigravity; read the `SKILL.md` named here before
the work it covers, whichever agent you are). They carry a `godot-` prefix so they install next to another factory's
skills on a machine that also runs one:

- **godot-commit-always** ([skills/godot-commit-always/SKILL.md](skills/godot-commit-always/SKILL.md)): every session.
  Commit after every meaningful step, never end a turn with uncommitted work, every imported file with its `.import`
  and every script with its `.uid`, LFS for binaries, push only when the coordinator says.
- **godot-game-session** ([skills/godot-game-session/SKILL.md](skills/godot-game-session/SKILL.md)): sessions that
  build a game, whatever its platform (art style, art, UI, story, naming, godot-heavy/GPU, scenes and resources as
  text, generator steps, workflow.jsonl, AutoPlay, the recording pipeline, framing screenshots, dataset).
- **godot-desktop-game** ([skills/godot-desktop-game/SKILL.md](skills/godot-desktop-game/SKILL.md)): sessions that
  build a desktop game, with godot-game-session (the Forward+ renderer, the desktop quality bar and what to build in
  for hard tasks). Every game is a desktop game unless it was made with `new-game.ps1 -Platform mobile`.
- **godot-mobile-game** ([skills/godot-mobile-game/SKILL.md](skills/godot-mobile-game/SKILL.md)): sessions that build
  or write tasks for a mobile game (an Android phone game: its root has a `Platform.json`), with godot-game-session,
  in place of godot-desktop-game (one renderer and its budgets, touch controls, the back button, the bot's fingers,
  the APK, touch task plays).
- **godot-sound** ([skills/godot-sound/SKILL.md](skills/godot-sound/SKILL.md)): sessions that build a game, whenever
  it needs sound (the design doc's audio direction, every UI, player, combat, world or ambience sound): finding,
  choosing and importing sound effects through `tools/sfx.py`.
- **godot-write-tasks** ([skills/godot-write-tasks/SKILL.md](skills/godot-write-tasks/SKILL.md)): sessions that write,
  move or review a game's tasks (the orphan `tasks` branch, never on main; at least 5 and up to about 10 per game,
  every one a long thread of multiple edits from the real history, never a single fix, at least 4 of them hard: the
  others may be medium, none easier; seed and reference commits, observation-only briefs, milestones with
  deterministic probe checks).

**Only these skills (owner's rule).** Contractors and every agent session working for godot-game-factory use the six
skills above (of godot-desktop-game and godot-mobile-game, the one of the game's platform, never both) and no others.
Never install, enable or invoke any other skill: not the person's own personal or project skills, not a plugin's or a
marketplace's skills, not the skills bundled with the agent (Claude Code's built-in skills and slash-command skills,
Codex's system skills, Antigravity's built-in skills), and not another factory's skills (`commit-always`,
`game-session`, `desktop-game`, `mobile-game`, `sound`, `write-tasks`, `unity-commit-always`, `unity-game-session`,
`unity-sound`, `unity-write-tasks`) even when the machine has them installed. A skill the agent offers by name or
description that is not one of them is ignored. Work no skill here covers is done by hand under these rules, or asked
about (the coordinator, or the person in a solo session). _(why: the recorded sessions are the dataset, so how a game
gets made must follow these rules only; another skill brings instructions and habits nobody here reviewed into the
creation record, and another factory's skills give answers for another engine to Godot questions)_

Session briefs: [docs/briefs/](docs/briefs/README.md). New machine: [docs/new-machine.md](docs/new-machine.md).
Pipeline: [docs/godot-pipeline.md](docs/godot-pipeline.md). AutoPlay:
[docs/autoplay-contract.md](docs/autoplay-contract.md). Creation replay: [docs/godot-replay.md](docs/godot-replay.md).

**Priorities (user decision).** What ships is what matters, in this order: the game plays; the game builds (the
import without errors and the Windows release player; a mobile game is played and recorded as that player at the
phone's size, and its APK is built at release where the machine has the Android toolchain); the dataset holds the replay scripts and the git log.
The AutoPlay bot should still play like a human (human-like input, aim and camera), but bot work never blocks a
release: one recorded scenario per game (one video) that shows the game running is enough, whatever the result
(win/lose/timeout is metadata). No tuning for win rates, seed sweeps or "clean" runs, and no re-runs or re-recordings
to improve how the bot plays. No retest loops: every GPU or engine run costs the shared machine and holds up
delivery, so run the minimum once and report; re-run only when the user asks. Game-session work never blocks dataset
packaging or sharing.

**AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording shows
the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid getting
stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene, missing art,
lighting, camera); then one AutoPlay run per scenario and one recording of it. A recording needs no screen (the
release player writes its own frames and sound), so a session that has reached its AutoPlay
milestone runs `tools/godot-pipeline/pipeline.ps1 <slug>` itself, one run per scenario, never to improve the bot
([docs/godot-pipeline.md](docs/godot-pipeline.md)). Every game has the AutoPlay drop-in in `addons/autoplay/`,
unchanged (new games from `templates/new-game.ps1`; a new version through
`tools/godot-pipeline/autoplay/install.ps1`). Once scenario 1 plays, wire it and write the bot
([docs/autoplay-contract.md](docs/autoplay-contract.md)), test once with `Scripts/godot.ps1 autoplay` and the run
checker, tag `milestone/autoplay-<n>`, record, and report to the coordinator (godot-game-session skill). No game is
released before AutoPlay is ensured: the current drop-in, every scenario wired, the bot, a passing hand test per
scenario and the milestone tag (godot-game-session skill, "Dataset", release step 1).

**Dataset.** Each game's full dataset is `games\<slug>\Dataset.zip`: the same name everywhere, git-ignored
(`/Dataset.zip`, `/Dataset.pending.zip`, `/.dataset/`), produced by the packager, never committed. The committed
`Dataset\` is the same minus `GodotProject/`, `Build/`, `History/` and `Tasks/`. The packager is
`python tools/package-dataset.py <slug>` ([docs/godot-pipeline.md](docs/godot-pipeline.md#dataset-packager)). It packs
the release commit with three products of it: the pipeline's release build (for a mobile game the APK beside the Windows player, when the build made one), the gameplay
video of each scenario's first valid recording of that commit (`Gameplay/`) and the creation replay's package
(`ReplayScripts/`, made by `python tools/godot-replay/godot_replay.py release --game <slug>`,
[docs/godot-replay.md](docs/godot-replay.md)). With a video and the replay it writes `Dataset.zip` (a FAIL verdict
too); while the replay is missing it writes `Dataset.pending.zip` and lists what
is pending; without a video it refuses (a game without a gameplay video is rejected at upload). The release steps are
in the godot-game-session skill ("Dataset"). Before its first run a game's `Dataset\` stays as the template made it,
and nobody assembles a dataset by hand.

This checkout is shared by several sessions at once: stage explicit paths only and never commit another session's
changes.

## What is here

| Part | Where to read |
|---|---|
| skills (`skills/`) | the six `SKILL.md` files named above |
| machine setup, the pinned engine, the Android toolchain, recording hooks, job limiter (`machine/`) | [machine/README.md](machine/README.md), [docs/new-machine.md](docs/new-machine.md) |
| game template (desktop and mobile) + `new-game.ps1` (`templates/`) | [templates/README.md](templates/README.md) |
| art style library and its tool, sound tool (`docs/art-styles/`, `tools/art-style.py`, `tools/sfx.py`) | the godot-game-session and godot-sound skills |
| game format: the repo and dataset rules, their schemas, `validate-game.py`, `validate-dataset.ps1`, `split-tasks.py`, `scrub-workflow-rows.py`, `thread-stats.py` | [docs/game-format.md](docs/game-format.md) |
| task verifier: the task schema, the probe addon, `task-check.py`, `task-try.py` (`tools/task_check/`) | [docs/task-check.md](docs/task-check.md), [docs/task-probes.md](docs/task-probes.md), [docs/task-try.md](docs/task-try.md) |
| AutoPlay drop-in (`tools/godot-pipeline/autoplay/`, `install.ps1`, `Scripts/godot.ps1 autoplay`) | [docs/autoplay-contract.md](docs/autoplay-contract.md) |
| recording pipeline: release build from a commit, recorder, run checker, stills, gameplay videos (`tools/godot-pipeline/`) | [docs/godot-pipeline.md](docs/godot-pipeline.md) |
| creation replay (`tools/godot-replay/`) | [docs/godot-replay.md](docs/godot-replay.md) |
| dataset packager (`tools/package-dataset.py`) | [docs/godot-pipeline.md](docs/godot-pipeline.md#dataset-packager) |

When a tool here fails or a machine lacks one, report it and carry on with what you can. Never stand in for a tool by
hand or with another factory's tool.

## Agents

All three agents run the same skills, the same recording hooks and the same workflow; what differs:

| | Claude Code | Codex CLI | Antigravity |
|---|---|---|---|
| start | `claude` in `<root>` (reads `<root>\CLAUDE.md`) | `codex -s danger-full-access` in `<root>` (reads `<root>\AGENTS.md`) | `agy` in `<root>` (reads `<root>\AGENTS.md`), or `<root>` opened in the Antigravity App or IDE |
| skills | `~\.claude\skills\godot-*` (also offered by name) | `~\.agents\skills\godot-*` (`$<name>` or `/skills`; also offered by description) | `~\.gemini\config\skills\godot-*` (offered by description) |
| recording hooks | `~\.claude\settings.json`: PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit, SessionEnd | `~\.codex\hooks.json`: PostToolUse, Stop, UserPromptSubmit, SessionEnd (trusted in `config.toml`; `/hooks` shows them) | `~\.gemini\config\hooks.json`: PostToolUse, Stop (the hook `godot-game-factory-recording`; `/hooks` shows it) |
| file edits in `actions.jsonl` | `Write` / `Edit` rows | `apply_patch` rows (the patch text) | its own tool rows (`write_file`, `edit_file`, `replace_file_content`, ...) with their arguments |
| permissions | as set in Claude Code (asks before commands by default) | `codex -s danger-full-access`: the default workspace sandbox blocks what game sessions need (the machine-wide job-slot mutexes, `git push` / `gh`) | as set in Antigravity (asks before commands by default); keep its terminal sandbox off (no `agy --sandbox`): like Codex's workspace sandbox, it blocks what game sessions need |
| transcript (backfill) | `~\.claude\projects\…\<session>.jsonl` | `~\.codex\sessions\YYYY\MM\DD\rollout-…-<session>.jsonl` | `~\.gemini\antigravity-cli\brain\<conversation>\.system_generated\logs\transcript_full.jsonl` (App: `antigravity`, IDE: `antigravity-ide` in place of `antigravity-cli`) |

Under Codex, the shell tool is recorded as `Bash` whatever shell ran the command. Under Antigravity, a tool call's row
is written once its result reaches the transcript (at the next tool call, or at the end of the turn), and the shell
tool is `run_command` (`input.CommandLine`). Read a skill by opening its `SKILL.md` when the task matches, even if the
agent did not offer it. Every agent's hooks also store every prompt the person typed, every reply the model wrote and
every reasoning summary the agent saved (`messages.jsonl`, read from the session's transcript; `machine/bootstrap.ps1`
turns the summaries on in Claude Code's and Codex's settings), and each tool call with its whole result
(`actions.jsonl`); a dataset carries them in `History/sessions/`. The person's directions are still
`user.direction` rows that the session writes itself (godot-commit-always skill).

Commands with Windows paths in these docs are written as PowerShell reads them. Typed in Git Bash (the shell of Claude
Code's Bash tool on Windows), put each Windows path in single quotes: bash drops unquoted backslashes, so
`C:\Users\<you>\GodotWork` arrives as `C:Users<you>GodotWork` and the command fails.

## Rules

Rules for agents working in this repository. Each rule says what goes wrong without it. Background is in `docs/`;
keep this section to rules.

### Data

- Never commit a full package, a project snapshot, `git.log` with asset diffs, or package zips here; only
  tools and docs. _(failure: a package is tens of GB, far past GitHub's 100 MB file limit)_
- Never commit a game's files, a store pack or anything from a game repo here. _(failure: game repos are private
  because the store licences of their assets require it; this repository holds tools and docs only)_
- Step reasons are the builder's own narration or notes, or the commit message; never write them with a
  model. _(failure: reasons written after the fact make a package a reconstruction rather
  than a record)_
- Anonymize authors as `dev_NN` and run the leak scan (real names, e-mails, `C:\Users\…`, `/Users/…`, `/home/…`)
  over every text file of a package before calling it done (`tools/package-dataset.py` does both, and refuses a
  package with a name left in a text file or a path: never make a package another way). _(failure: commit metadata
  and asset files can carry real names and machine paths)_
