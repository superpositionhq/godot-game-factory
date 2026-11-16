# machine/

Everything a Windows machine needs outside this repo, kept in the repo and installed by `setup.ps1` (or its parts:
`get-godot.ps1`, `bootstrap.ps1`, `get-android.ps1`). Step-by-step setup, including the manual sign-ins:
[../docs/new-machine.md](../docs/new-machine.md).

## The machine root

All machine paths hang off one root, the "GodotWork" folder that holds `godot-game-factory\`, `godot\<version>\`,
`android\`, `games\`, `tasks\`, `builds\`, `recordings\`, `.recording\`, `deliverables\`, `asset-library\` and
`tools\`. Docs write it as `%GGF_ROOT%`. `builds\` and `recordings\` are the recording pipeline's
(`tools/godot-pipeline/`, [../docs/godot-pipeline.md](../docs/godot-pipeline.md)): release builds and the gameplay
bundles. The creation replay ([../docs/godot-replay.md](../docs/godot-replay.md)) keeps each game's isolated project
and work files in `godot-replay\<slug>\` and writes its packages to `deliverables\_replay\`; the dataset packager,
`tools/package-dataset.py`, writes its zip and scratch into the game repo's own folder and keeps each delivery's
commit map, audit files, `package-log.jsonl` and its run lock in `deliverables\<slug>\`.
`lib/ggf-root.ps1` (PowerShell, dot-source it) and `lib/ggfroot.py` (Python: `sys.path.insert(0, <repo>/machine/lib)`,
`ggfroot.root()`) resolve it in this order:

1. env `GGF_ROOT`;
2. `root` in the config file: env `GGF_CONFIG`, else `%USERPROFILE%\.godot-game-factory\config.json` (bootstrap writes it);
3. `%USERPROFILE%\GodotWork`.

The config also holds `ggb` (default `<root>\_build`: the release builds' private clones, `<ggb>\src\<slug>`;
`bootstrap.ps1 -Ggb` sets it), `checkout` (the godot-game-factory clone bootstrap ran from: the installed copies of
`ggf-root.ps1` find the repo's tools through it), `github_org` (the GitHub organisation or user that owns
godot-game-factory and the private `godot-game-<slug>` repos: `bootstrap.ps1 -Org` writes it, env `GGF_ORG` overrides
it; new-game.ps1, `-CloneGames` and check.ps1 read it), and `record_extra_projects` (default `[]`: extra top-level
folders the recording hooks treat as projects besides `games\<slug>`). Optional: `godot` (the full path of another
editor exe than the pinned one), `ffmpeg` (the full path of an `ffmpeg.exe`), `android` (`{"home": "<folder>"}`: the
Android toolchain when it is not in `<root>\android`), `out` (env `GGF_OUT`; default `<root>\deliverables`: where the
creation replay's packages go, `_replay\<slug>\<sha8>\`, GBs per game, so point it at a roomy drive; the dataset
packager writes its zip next to the game repo, or where its `--out` says, and keeps each delivery's commit map, audit
files, `package-log.jsonl` and its run lock in `<out>\<slug>\`) and `min_free_gb` (env `GGF_MIN_FREE_GB`, default 50:
the task check, the task try, the creation replay and the dataset packager refuse to start on a drive with less free).

```json
{ "root": "C:\\Users\\<name>\\GodotWork", "ggb": "C:\\Users\\<name>\\GodotWork\\_build",
  "checkout": "C:\\Users\\<name>\\GodotWork\\godot-game-factory", "github_org": "<org>", "record_extra_projects": [],
  "agents": ["claude"], "hooks_dir": "C:\\Users\\<name>\\.godot-game-factory\\hooks",
  "heavy_slots": 3, "gpu_slots": 2, "slots_auto": { "heavy_slots": 3, "gpu_slots": 2, "basis": "<hardware>" } }
```

### The engine

One Godot version for the whole factory, named in one place: `godot.json` (`version`, `flavor`, `feature`, `exe`,
`console_exe`, `templates`, the download `urls` and their `sha512`). `get-godot.ps1` puts the editor and its export
templates in `<root>\godot\<version>\`, self-contained: an empty `._sc_` file beside the exe makes the editor keep its
settings in `editor_data\` there and its export templates in `editor_data\export_templates\<templates>\`, so nothing
goes to `%APPDATA%` and nothing is installed machine-wide. `Get-GGFGodot` (`ggfroot.godot_exe()`) gives the exe:
env `GODOT_EDITOR`, else `godot` in the config, else the pinned one; `Get-GGFGodot -Console`
(`godot_exe(console=True)`, the Python default) gives the console wrapper beside it, which waits for the engine and
passes its output and exit code on. Tools run the console wrapper. A missing exe gives `$null` and a warning naming
`get-godot.ps1` (`ggfroot.py` exits with that message).

A game's platform has one reader, `tools/validate-game.py` (`read_platform`). PowerShell tools ask it through
`Get-GGFPlatform -Folder <game>`, which runs `python <checkout>\tools\validate-game.py --platform <folder>` (it prints one JSON line) and returns
`@{ platform; orientation; width; height }`: `desktop` 1920x1080, `mobile` `landscape` 1920x1080 or `mobile`
`portrait` 1080x1920. A bad `Platform.json` is an error, never read as desktop.

ffmpeg: `Get-GGFFfmpeg` / `Get-GGFFfprobe` (`ggfroot.ffmpeg()`) give env `GGF_FFMPEG`, else `ffmpeg` in the config,
else the pinned copy `get-ffmpeg.ps1` downloads to `<root>\tools\ffmpeg-8.1.2\`, else the one on PATH.

### The Android toolchain

A mobile game's APK is built by Godot's Gradle build, which needs a JDK, the Android SDK and two keystores.
`get-android.ps1` puts all of it in one folder, `<root>\android\` (config `android.home`), and installs nothing
machine-wide:

| Path | What |
|---|---|
| `jdk\` | the JDK `android.json` pins (Eclipse Temurin 17, SHA-256 verified) |
| `sdk\` | the Android SDK: the command-line tools `android.json` pins, `platform-tools`, and the build-tools and platform the installed engine's own Android build template names (`buildTools` and `compileSdk` in `config.gradle` of the export templates' `android_source.zip`; for 4.7.2: `build-tools;36.1.0`, `platforms;android-36`). The NDK only with `-Ndk`: a game's Gradle build works without it |
| `keystores\` | `debug.keystore` (alias `androiddebugkey`, password `android`) and `release.keystore` (alias `release`, a random password), made on the machine with the JDK's keytool. The release keystore signs every APK this machine builds: keep the folder |
| `gradle\` | `GRADLE_USER_HOME` of every Android build; its `gradle.properties` turns the Gradle daemon off, so no Java process outlives an export |
| `.android\` | `ANDROID_USER_HOME`: what the Android tools would otherwise keep in `%USERPROFILE%\.android` |
| `toolchain.json` | what was installed: the engine version, the SDK packages, the keystores' users and passwords |

It also writes four lines into the self-contained editor's settings
(`<root>\godot\<version>\editor_data\editor_settings-4.7.tres`): `export/android/java_sdk_path`,
`export/android/android_sdk_path`, `export/android/debug_keystore` and `export/android/debug_keystore_pass`. An export
reads the JDK and the SDK from there.

`Get-GGFAndroid` (`ggfroot.android()`) returns the toolchain, or `$null` (`None`) when any piece is missing: `home`,
`jdk`, `java`, `keytool`, `sdk`, `gradle_home`, `godot`, `build_tools`, `compile_sdk`, `ndk`, `debug_keystore` and
`release_keystore` (each `path`, `user`, `password`). A tool that exports an APK calls `Set-GGFAndroidEnv`
(`ggfroot.android_env()`) first: it sets, for that process only, `GRADLE_USER_HOME`, `JAVA_HOME`, `ANDROID_HOME`,
`ANDROID_USER_HOME`, `ANDROID_PREFS_ROOT` and the keystores as Godot reads them from the environment
(`GODOT_ANDROID_KEYSTORE_DEBUG_PATH` / `_USER` / `_PASSWORD` and `GODOT_ANDROID_KEYSTORE_RELEASE_PATH` / `_USER` /
`_PASSWORD`), and returns the same object or `$null`. A machine without the toolchain still makes, plays, records and
task-checks mobile games; only the APK step is skipped, and the tool says so by name.

The editor makes an empty `.android` folder in `%USERPROFILE%` whenever it opens a project that has an Android export
preset; nothing is kept in it.

### Job slots

Job slots (godot-heavy.ps1, docs/godot-pipeline.md "Machine-wide slots"):

| Key | Meaning | Without it |
|---|---|---|
| `heavy_slots` | general slots: imports, exports, generator scripts (GPU jobs hold one too) | `clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))` |
| `gpu_slots` | concurrent rendering jobs | `clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1))`, 1 without nvidia-smi |
| `gpu_vram_limit_mb` | a GPU job starts only while less VRAM than this is in use | half the GPU's VRAM |
| `slots_auto` | written by bootstrap.ps1: the computed values and the hardware they came from | |

bootstrap.ps1 writes the computed `heavy_slots` / `gpu_slots` (and `slots_auto`); a value that differs from
`slots_auto` was set by hand and stays unless `bootstrap.ps1 -Force`. check.ps1 shows the slots in effect and their
source (config set by hand, config from bootstrap, or computed at run time). The formula lives in
`lib/ggf-root.ps1` (`Get-GGFComputedSlots`) and `lib/ggfroot.py` (`computed_slots`).

### Next to other factories

A PC may also run other factories (roots `%USERPROFILE%\Work` and `%USERPROFILE%\UnityWork`, configs
`%USERPROFILE%\.game-factory\` and `%USERPROFILE%\.unity-game-factory\`). Each keeps its own root, config, hooks
folder, session map and skills, and each one's bootstrap adds its hook entries next to the others' in
`~\.claude\settings.json` / `~\.codex\hooks.json` without touching them (ours run `record-godot-action.ps1`, theirs
`record-action.ps1` and `record-unity-action.ps1`). A session is recorded by the factory whose `games\<slug>` (or
extra project) one of its tool calls names, and from then on every call of it is recorded there (see Recording
below); for every other session this factory's hook ends at once. Nothing of another factory is ever written. What
they share on purpose:

- **Job slots.** `godot-heavy.ps1` takes the same machine-wide mutexes as the other factories' limiters
  (`Global\ue-heavy-slot-<n>`, `Global\ue-gpu-slot-<n>`, `Global\ue-heavy-low-slot`), so the jobs of all draw from
  one set of slots. All use the same slot formula; if the configs set different counts, each limiter enforces its own
  count over the shared mutexes, so keep them equal.
- **Their recordings.** The other factories record the screen, and a recording of theirs takes every GPU slot.
  `godot-heavy.ps1` holds back its GPU jobs while another factory's `builds\_queue\_recording-wants-gpu` flag is
  fresh, and reads their job logs for waiting jobs and recent GPU starts (`Get-GGFOtherFactoryRoots` finds each root
  the way that factory does: its environment variable, its config file, else its default folder when that holds its
  clone). This factory's own recordings are written by the engine frame by frame and need no screen: they take one
  GPU slot like any rendered run, and write no flag.

## Files

| Path | Installed to | What |
|---|---|---|
| `setup.ps1` | | the one entry point for a clean PC: hardware precheck, winget installs (Git, Git LFS, gh, Python, the Codex CLI with Codex), gh sign-in (asked) + git identity, the godot-game-factory clone, then `get-godot.ps1`, `bootstrap.ps1`, with `-Android` `get-android.ps1`, and `check.ps1`; PASS/TODO list, log `<root>\.setup\setup.log` |
| `godot.json` | `<root>\tools\` | the pinned engine: version, exe names, export templates' folder, download URLs, SHA-512 |
| `get-godot.ps1` | `<root>\godot\<version>\` | downloads the editor and the export templates godot.json names, verifies SHA-512, unpacks them self-contained; a part that is there is left alone |
| `android.json` | | the pinned JDK and Android command-line tools: URLs, SHA-256 |
| `get-android.ps1` | `<root>\android\` | the Android toolchain (above) and the editor settings an export reads; asks before accepting the Android SDK licence agreements (`-Yes` accepts) |
| `bootstrap.ps1` | | idempotent setup: config + layout, tools, ffmpeg, hooks + each agent's settings merge (`-Agent claude\|codex\|both`; prints what the hooks record and asks first; `-Yes` skips the question), the `godot-*` skills, root CLAUDE.md / AGENTS.md, LFS, gh, game repo hooks (`-CloneGames`) |
| `check.ps1` | | read-only PASS/WARN/FAIL report: the engine and its export templates, git, Git LFS, gh, Python, ffmpeg, disk, the job slots and where each count comes from, hooks, agents, skills, and the Android toolchain (`Android toolchain (mobile games)`; a missing piece is a WARN: mobile games still work, except the APK) |
| `get-ffmpeg.ps1` | `<root>\tools\ffmpeg-8.1.2\` | uses an ffmpeg that is already there (the config's, PATH); else downloads gyan.dev ffmpeg 8.1.2 full_build .7z, verifies SHA-256 `0fff1889...7059`, unpacks |
| `lib/ggf-root.ps1` | `<root>\tools\`, the hooks dir | root/config resolver (also `Get-GGFHooksDir`, `Get-GGFAgents`, `Get-GGFGodot`, `Get-GGFPlatform`, `Get-GGFAndroid`, `Set-GGFAndroidEnv`, `Get-GGFFfmpeg`, the slot mutexes), dot-sourced by every script |
| `lib/ggfroot.py` | | the same for Python tools (`root`, `ggb`, `org`, `engine`, `godot_exe`, `android`, `android_env`, `ffmpeg`, `computed_slots`, `slot_plan`, `out`, `check_free`) |
| `lib/codex-hooks.ps1` | | Codex hook trust: the `[hooks.state]` entries Codex needs in `config.toml` before it runs a hook (bootstrap writes ours, check compares) |
| `tools/godot-heavy.ps1` | `<root>\tools\godot-heavy.ps1` | machine-wide job limiter: `heavy_slots` general slots + `gpu_slots` GPU slots, one named mutex per slot (shared with other factories, see above: a killed job leaks none; VRAM guard), counts from the config or the hardware formula above, `-Low` for background work, GPU auto-detected (the Godot exe without `--headless`, an exported player under a `Build` or `builds` folder, also behind a launcher; `-Gpu` forces it, `--headless` always rules it out), log `.recording\_heavy-jobs.jsonl`. Installed next to a copy of `lib\ggf-root.ps1` |
| `hooks/record-godot-action.ps1` | the hooks dir | the agent hook (Claude Code: PostToolUse / PostToolUseFailure / Stop, and UserPromptSubmit / SessionEnd with `-Messages`; Codex: PostToolUse / Stop, and UserPromptSubmit / SessionEnd with `-Messages`, all with `-Agent codex`): every tool call of a game session to `.recording\<project>\actions.jsonl` (earlier calls backfilled from the transcript, see Recording), every prompt the person typed and every reply the model wrote to `.recording\<project>\messages.jsonl` (read from the transcript); Stop auto-commits leftovers as `WIP` (none while conflicts are unresolved or HEAD is detached) |
| `hooks/record-godot-commit.ps1` | the hooks dir | called by each game repo's post-commit hook: `.recording\<repo>\commits.jsonl` |
| `hooks/settings-hooks.json` | merged into `~\.claude\settings.json` | Claude Code: the five hook entries (PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit, SessionEnd; `{{HOOKS_DIR}}` filled in) |
| `hooks/codex-hooks.json` | merged into `~\.codex\hooks.json` | Codex: the four hook entries (PostToolUse, Stop, UserPromptSubmit, SessionEnd; `{{HOOKS_DIR}}` filled in), trusted in `~\.codex\config.toml` |
| `hooks/recording-exclude.txt` | the hooks dir (once) | session ids never recorded (the coordinator) |
| `install-git-hook.ps1` | `<game>\.git\hooks\post-commit` | appends the commit recorder's line after Git LFS's own lines (before another tool's final `exit` or `exec`); warns when the recorder isn't in the hooks dir or another tool's hook can end before it. bootstrap.ps1 runs it for every game under `<root>\games` |
| `tests/test-recording.ps1` | | the recording hook and the reasoning-summary settings on made-up transcripts in a scratch folder of its own (`-Scratch`, else `<clone>\.local\tests\`): whole tool results, the cut at 1,000,000 characters, picture markers, a saved command output, a session of no game of this root leaving nothing, `thinking` rows of both agents, `-Backfill`, `config.toml`: `powershell -NoProfile -ExecutionPolicy Bypass -File machine\tests\test-recording.ps1`; exit code = failed checks |

The hooks dir is `hooks_dir` in the config, default `~\.godot-game-factory\hooks\`. One copy serves both agents.
`recording-sessions.json` (session id -> project map) is runtime state: bootstrap creates it empty next to the hooks
and never overwrites it. The hook keeps two more state files there: `recording-backfill.json` (the sessions whose
earlier tool calls were imported) and `recording-messages.json` (transcript file -> bytes read, for `messages.jsonl`).

The recording pipeline (`tools/godot-pipeline/`, [../docs/godot-pipeline.md](../docs/godot-pipeline.md)), the creation
replay (`tools/godot-replay/`, [../docs/godot-replay.md](../docs/godot-replay.md)) and the task checker
(`tools/task-check.py`, [../docs/task-check.md](../docs/task-check.md)) run their engine jobs through
`godot-heavy.ps1`'s slots like every other heavy job. The dataset packager (`tools/package-dataset.py`,
[../docs/godot-pipeline.md](../docs/godot-pipeline.md#dataset-packager)) reads a game's `actions.jsonl` and
`messages.jsonl` into the dataset's `History/sessions/`.

### Recording

- **Mapping.** A session is filed under a project the first time a tool call's input (command, file path, cwd) names
  `<root>\games\<slug>` (or an extra project) as an absolute path, in any spelling (`C:\...`, `C:/...`, `/c/...`),
  starting a word: `D:/backup/c/...` or a path glued to an option (`git -C/c/...`) does not count.
  Variables such as `%GGF_ROOT%` are seen unexpanded and do not count. `templates/new-game.ps1` therefore requires the
  written-out `-Path <root>\games\<slug>`, and that call maps a new game's session.
- **Other sessions.** The hook runs for every session of the agent on the Windows account. A call that neither comes
  from a session mapped here nor names a path under this root's `games\` ends before its JSON is parsed and without
  taking the recording mutex, so sessions of other factories and sessions of no factory pay only the start of
  PowerShell.
- **Backfill.** At that first mapping the hook imports the session's earlier tool calls (reading docs, drafting the
  design) from its transcript (`transcript_path` in the hook input; Claude Code: plus `<session>\subagents\*.jsonl`
  beside it; Codex: the rollout file's completed shell, file-change and MCP items, shell calls as `Bash` with the
  command, file changes as `apply_patch` with `input.changes` since the rollout keeps no patch text). They
  are written in order, just before the mapping call's own row, with `"status": "from_transcript"` and the transcript's
  times (`time` = the call, `result_time` = its result). Only calls with a result, logged under this session id and no
  older than the transcript file are imported (a fork's copied context predates the file). Each session is backfilled
  once (`recording-backfill.json` next to the hooks: count, transcript, imported tool_use_ids), and a call imported this
  way is never written again by its own live hook.
- **A session mapped without its backfill:** `powershell -ExecutionPolicy Bypass -File
  <hooks dir>\record-godot-action.ps1 -Backfill <session id> [-TranscriptPath <file>] [-Agent codex]` inserts the rows
  before that session's first row in `actions.jsonl` (finds the transcript under `~\.claude\projects\`, or
  `~\.codex\sessions\` with `-Agent codex`, when not given); a second run does nothing. The same call also imports
  that session's messages.
- Live rows carry no `status`; every row of a backfill carries `from_transcript`, so the two are never confused.
- **Messages.** Every prompt the person typed, every reply the model wrote and every reasoning summary the agent saved
  goes to `<root>\.recording\<project>\messages.jsonl`, one row each: `time`, `project`, `session_id`, `agent`, `role`
  (`user`, `assistant` or `thinking`), `message_id`, `text`, and where they apply `model`, `images` (pictures attached
  to a prompt), `mid_turn` (a prompt typed while the model was working), `phase` (Codex) and `subagent` (a Claude Code
  subagent's transcript, where `user` is the prompt the session gave it). They are read from the session's transcript,
  never from the hook input, so each is written once, with the transcript's own id and time. Every `Stop`, and the
  `UserPromptSubmit` and `SessionEnd` hooks (which call the script with `-Messages` and write no `actions.jsonl` row),
  read what the transcript gained since the last read (`recording-messages.json` next to the hooks: transcript file ->
  bytes read), so a session mapped late gets its earlier messages too. A `thinking` row is a reasoning summary the
  agent saved for a turn (`redacted` true and no text when the agent saved it without readable text);
  `machine/bootstrap.ps1` turns the summaries on for both agents (Claude Code `showThinkingSummaries` and
  `alwaysThinkingEnabled` in `settings.json`; Codex `model_reasoning_summary = "detailed"` and
  `hide_agent_reasoning = false` in `config.toml`) and `machine/check.ps1` checks them; a Codex model that gives no
  summaries leaves only the textless rows. Not recorded here: tool calls and results (`actions.jsonl` has them, each
  call with its whole result, up to 1,000,000 characters, `response_chars` and `response_truncated` on a longer one; a
  picture or other binary payload as a short marker), text the agent tool puts into a turn itself (meta rows,
  compaction summaries, background-task notices, API error notices) and a fork's copied context.
- **`record-godot-action.ps1 -Backfill all`** imports the messages of every mapped session whose transcript is still on
  this machine (either agent), and nothing else. It reads each transcript from its start, adds what is not yet in
  `messages.jsonl` and puts that session's rows back in the transcript's order. A transcript written while the agent's
  summary setting was off holds no summary text: those rows come out `redacted`.
  The summary is what the agent saved: Claude Code's `thinking` blocks, Codex's `summary_text` and, where the rollout
  holds it as plain text, its `raw_content`. A long command output that Claude Code cut in the
  result and saved to a file (`persistedOutputPath`) is read from that file while it is there.
- Row schemas: `actions.jsonl` rows carry `"schema": "agent-action/v0"`, `messages.jsonl` rows
  `"schema": "agent-message/v0"`, `commits.jsonl` rows `"schema": "commit/v0"`.
- Every row carries `agent` (`claude` or `codex`). Codex rows differ in two ways: file edits are `apply_patch` rows
  (`input.command` = the patch), and there is no `PostToolUseFailure` (a failed call is a `PostToolUse` whose
  response shows the exit code).
- Nothing is recorded while `GGF_NO_RECORDING` (or another factory's `UGF_NO_RECORDING` / `GF_NO_RECORDING`) is set:
  a task try's agent is not a game session.
- **Codex hook trust.** Codex runs a hook from `hooks.json` only after it is trusted (a hash of the hook in
  `config.toml` `[hooks.state."<hooks.json>:<event>:<group>:<handler>"]`); an untrusted or edited hook is skipped
  without a word. bootstrap.ps1 writes the entries for the record-godot-action.ps1 hooks (`lib/codex-hooks.ps1`),
  check.ps1 compares them, and `/hooks` inside Codex shows (and can set) the same state.

Installed copies are plain copies: after changing a file here, run `bootstrap.ps1` again (it backs up what it
replaces under `_backup\<time>\`). `check.ps1` reports installed copies that differ from the repo.
