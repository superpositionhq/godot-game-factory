# Godot engine runs, build and recording pipeline

How heavy Godot work runs on the shared machine, and the pipeline that builds a game's Windows release player (and a
mobile game's Android APK) from a commit and records AutoPlay runs of it (an in-game bot playing through injected
input, see [autoplay-contract.md](autoplay-contract.md)) as gameplay bundles ([Bundle](#bundle)); then the creation
replay in short ([godot-replay.md](godot-replay.md) has all of it), and the dataset packager. The pipeline's scripts
are `tools/godot-pipeline/` (Windows PowerShell 5.1).

> **What runs:** a game's `Scripts/godot.ps1`, the machine-wide job limiter, the recording pipeline below, the
> creation replay ([Creation replay](#creation-replay)) and the dataset packager
> ([Dataset packager](#dataset-packager)). A game is recorded once its scenario wiring and bot are in
> ([autoplay-contract.md](autoplay-contract.md)); a session sends the coordinator what is ready and the coordinator
> runs the pipeline ([Pipeline](#pipeline)). The recorder makes each scenario's gameplay video and the creation
> replay makes `ReplayScripts/`; the packager takes both, with the pipeline's release build, into a complete
> `Dataset.zip`, and nobody assembles a dataset by hand. The task checker's own plays (a scratch copy played from its
> source, on a Windows desktop of its own) are in [task-check.md](task-check.md).

| Script | Does |
|---|---|
| `build.ps1 <game> [-Commit rev] [-Force] [-NoAndroid]` | the Windows release player of a commit, from a private clone, and a mobile game's APK; row in `builds.jsonl` |
| `record.ps1 <game> -Build <dir\|latest> [-Scenario n] [-Runs k] [-Skill s] [-Seed s] [-MaxSeconds n]` | start in Movie Maker mode, encode, validate, bundle; a row per run in `runs.jsonl` |
| `pipeline.ps1 <game> [-Scenarios 1,2] [-Commit rev] [-MaxSeconds "1=300,3=900"] [-Force]` | release build, then one recorded run per scenario; row in `pipeline.jsonl` |
| `validate-run.ps1 <outputDir>` | contract check of one run's files, no video (for game sessions testing by hand) |
| `mark-invalid.ps1 <game> -Commit sha \| -RunId id -Reason text` | exclude bundles from the dataset (INVALID file, validation status `invalid`); files kept |
| `leak-scan.ps1 <dir> [-Patterns ..]` | byte search (ASCII + UTF-16) for the user name or other strings that must not ship |
| `scrub-lfs-history.py <game> [--apply]` | the account and agent names out of a game repo's own Git LFS history: patched objects, every commit repointed, archived first |
| `scrub-history.ps1 <game> [-Apply]` | the studio and tool names out of a game repo's own history: text blobs, messages, identities; archived first |
| `export-lfs-history.py <repo> <out>` | every LFS object of a history, with patched copies where one names the account (the dataset packager uses it) |
| `gameplay-mp4.ps1 <game> [-Commit sha..] [-RunId id] [-Force]` | a run's `gameplay.mp4` again from its kept movie (updates metadata/manifest) |
| `stills.ps1 <game> [-RunId id] [-Count n] [-Force]` | a run's README stills again (updates metadata/manifest) |
| `autoplay/` | the AutoPlay drop-in every game copies unchanged; `autoplay/install.ps1 -Game <game>` brings a game's copy up to date ([autoplay-contract.md](autoplay-contract.md)) |

## Paths

`%GGF_ROOT%` is the machine root: env `GGF_ROOT`, else `root` in `%USERPROFILE%\.godot-game-factory\config.json`
(written by `machine/bootstrap.ps1`), else `%USERPROFILE%\GodotWork`; `machine/lib/ggf-root.ps1` resolves it, and the
same file gives the engine (`Get-GGFGodot`: the one pinned version of `machine/godot.json`, installed self-contained in
`<root>\godot\<version>\`), `ggb` (default `<root>\_build`: the release builds' private clones), a game's platform
(`Get-GGFPlatform`) and the Android toolchain (`Get-GGFAndroid`). See [../machine/README.md](../machine/README.md).

```
%GGF_ROOT%\
  games\<slug>\                     the game repos (<org>/godot-game-<slug>; read only for the pipeline)
  games\<slug>\Logs\godot-ps1\      a game's own run logs (Scripts/godot.ps1; git-ignored)
  tasks\<slug>\                     a game's orphan tasks branch, checked out as a worktree
  tools\godot-heavy.ps1             the job limiter (+ ggf-root.ps1 beside it); its log .recording\_heavy-jobs.jsonl
  tools\ffmpeg-8.1.2\               the pinned ffmpeg (machine/get-ffmpeg.ps1)
  godot\<version>\                  the pinned engine and its export templates
  android\                          the Android toolchain (machine/get-android.ps1): JDK, SDK, keystores, Gradle home
  builds\<slug>\<short-sha>\        release build: Windows\<Project>.exe, Android\<Project>.apk (a mobile game),
                                    build_info.json, logs\
  builds\_pipeline-<slug>.lock      per-game build/record lock (holder in the .json beside it)
  recordings\<slug>\<run-id>\       bundles
  recordings\<slug>\_stills\        every bundle's stills, <run-id>_NN.jpg
  .recording\<slug>\actions.jsonl   the recording hooks' rows (machine/README.md); the pipeline never touches them
  .recording\<slug>\messages.jsonl  the same hooks' rows for every prompt and every reply of a session
  .recording\<slug>\commits.jsonl   one row per commit (the post-commit hook)
  .recording\<slug>\builds.jsonl    one row per build.ps1 run
  .recording\<slug>\runs.jsonl      one row per recorded run
  .recording\<slug>\pipeline.jsonl  one row per pipeline run
  godot-replay\<slug>\              the creation replay's isolated project and work files (godot-replay.md)
  deliverables\                     the creation replay's packages, _replay\<slug>\<sha8>\, and per game, <slug>\, the
                                    dataset packager's commit maps, audit files, package-log.jsonl and run lock
                                    (config "out", env GGF_OUT)
<ggb>\src\<slug>\                   private clone the pipeline builds from (never the game's working copy)
```

## A game's engine runs: `Scripts/godot.ps1`

Every game has `Scripts/godot.ps1` from the template; sessions use it rather than calling the engine themselves. It
finds the engine (`$env:GODOT_EDITOR`, else `ggf-root.ps1` `Get-GGFGodot`), runs every job through the limiter, writes
the log to `Logs/godot-ps1/` and prints the lines that matter (script errors, `[workflow]` rows) and the exit code.

| Mode | Runs | GPU |
|---|---|---|
| `import` | `--headless --import`, then fails on a script error in the log: this is "the project compiles" | no |
| `step -Script steps/<x>.gd -Reason "..."` | one committed generator script, headless (`--headless --script`), with its `workflow.jsonl` row (op `editor.step`, the script and the sha256 of its text as it ran) | no |
| `row -Op <op> -Target <t> -Reason "..." [-Params '<json>'] [-Direction <id>]` | one `workflow.jsonl` row for work done by hand (a scene written, a script edited, a setting changed) | no |
| `build [-Android] [-Reason "..."]` | `--headless --export-release "Windows Desktop" Build/Windows/<Project>.exe`; with `-Android` (a mobile game) also `Build/Android/<Project>.apk` when the machine has the toolchain, else the APK is skipped by name; one `build.player` row | no |
| `play [-Scenario <n>] [-Seconds 60] [-Shots <n>] [-Extra "..."] [-Tag <name>]` | the project from its source, rendered at the game's exact frame size (`-size`), with `-scenario <n>` when `-Scenario` is given; `-Shots n` saves n evenly spaced PNG frames to `Logs/godot-ps1/<tag>/`; stopped after `-Seconds` | yes |
| `autoplay [-Scenario <n>] [-MaxSeconds 120] [-Seed 0] [-Skill 1] [-Audible] [-Extra "..."]` | the built player as a recording runs it (the AutoPlay drop-in), in real time and without a movie: the bot plays scenario n for at most `-MaxSeconds`, starting at once, on a Windows desktop of its own (nothing on the screen; muted unless `-Audible`); the run's files go to `Logs/autoplay/<time>_s<n>/`, which `tools/godot-pipeline/validate-run.ps1 <folder>` checks | yes |

Keep the call shape `Scripts/godot.ps1 step -Script <path>`: the creation replay finds each generator script's runs by
it in the recorded commands ([godot-replay.md](godot-replay.md)).

Facts that cost time before:

- **A project is text.** Scenes, resources, scripts and settings are text files a session writes and commits; the
  engine is run headless only for what only it can do: the import (`.godot/`, and the `.import` and `.uid` files that
  are committed), a generator script, an export.
- **Import before export.** An export of a project that was never imported can miss resources; `build` and the
  pipeline import first.
- **`--headless` renders nothing**: no screenshots, no frames to read back, no movie.
- **A game's own arguments come after `--`** (`godot --path <project> -- -scenario 2`): what stands before it is the
  engine's, and the engine does not show its own arguments to a script.
- **The Android export** needs the toolchain (`machine/get-android.ps1`) and takes the JDK and SDK paths from the
  editor's settings, which that script writes; `machine/check.ps1` says whether it is there.
- **`play` exits 124** when it stops a game after `-Seconds`: the timeout doing its job, not a crash (read the log
  for errors). `-Extra` is split at spaces, so a value in it cannot hold a space.

## One heavy job at a time

`build.ps1` and `record.ps1` take an exclusive per-game lock on `builds\_pipeline-<slug>.lock` (an open file handle:
released by the OS if the process dies, visible across sessions and Task Scheduler), `build.ps1` for the whole build
and `record.ps1` for each run's play, and wait for it otherwise (the holder is printed): a build and a recording of
the same game share its clone and its build folder. Different games only share the machine, which the general and GPU
slots below ration. Builds and the video encoding run at below-normal priority so the game sessions' own work stays
responsive.

### Machine-wide slots

Every heavy job of every session goes through one limiter, `<root>\tools\godot-heavy.ps1` (rows in
`.recording\_heavy-jobs.jsonl`): `& <root>\tools\godot-heavy.ps1 -Label "<slug> <what>" [-Gpu] [-Low] -- <exe> <args>`.
It returns the job's exit code, or 125 when it could not run the job itself (called wrongly, `ggf-root.ps1` missing
beside it, a machine config that is not JSON, an exe that would not start).
From Git Bash, wrap it in `powershell -ExecutionPolicy Bypass -Command "& '<path>' ... ; exit \$LASTEXITCODE"`
(`powershell -File ... --` misparses `--`; without `-ExecutionPolicy Bypass` Windows' default policy refuses the
script, and with the dollar sign unescaped bash expands `$LASTEXITCODE` to nothing: either way the call returns 0
whatever the job did). The pipeline runs its jobs through this checkout's copy of the limiter
(`machine/tools/godot-heavy.ps1`, the same slots), so the pipeline and the limiter are always the same version.

Each slot is a named mutex (`machine/lib/ggf-root.ps1` `Get-GGFSlotMutexes`, `Enter-GGFSlot`). A job that is killed
before it releases its slot leaves the mutex abandoned, and the next job takes it over, so no slot leaks. The counts
are read from the config at every call, so a new `heavy_slots` / `gpu_slots` applies at once.

| Slots | Named mutexes | Taken by | Count |
|---|---|---|---|
| general | `Global\ue-heavy-slot-<n>` | every job: imports, exports, generator scripts, tests, plays, and GPU jobs too | config `heavy_slots`, else the formula |
| GPU | `Global\ue-gpu-slot-<n>` | jobs that render (the engine without `--headless`, an exported player under a `Build` or `builds` folder, a launcher that starts one of them, anything run with `-Gpu`; `--headless` in a command means no GPU slot), together with a general slot: a GPU job never holds one while waiting for the other | config `gpu_slots`, else the formula |

**The mutex names are another factory's on purpose:** a machine that runs several factories has one set of slots, so
their jobs together never overcommit the same RAM and GPU. The limiter also honours the other factories' "a recording
waits for the GPU" flags, which it reads in their roots; it writes nothing of theirs. A recording here needs no such
flag: it is one GPU job like any rendered run ([The video](#the-video)).

The formula (`ggf-root.ps1` `Get-GGFComputedSlots`, the same as the other factories'; bootstrap.ps1 writes its result
to the config, and a value set by hand stays unless `bootstrap.ps1 -Force`):

- `heavy_slots = clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))`:
  a heavy process needs about 6 GB, and 6 GB stays for the desktop and the sessions themselves.
- `gpu_slots = clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1))`, 1 without nvidia-smi:
  about 4 GB per renderer, and one general slot always stays free for imports and exports.

Dynamic guards on top of the counts:

- **VRAM guard:** a GPU job starts only while the GPU's used VRAM is under `gpu_vram_limit_mb` (default half the VRAM)
  and no other GPU job that still runs started in the last 60 s (a new renderer's VRAM shows only once it has loaded);
  otherwise it hands its slot back and looks again every 30 s (`vram_wait` rows). A recorded run therefore often
  waits a minute or two before its game starts; `record.ps1` says so and counts no time against the run while it
  waits.
- **`-Low`** (background work): one low job machine-wide; it takes a general slot only while no other job waits for
  one and another slot stays free, at below-normal priority.

`machine/check.ps1` shows the slots in effect and where each comes from.

## Recording pipeline

### Build

`build.ps1 <game> [-Commit rev] [-Force] [-NoAndroid]`:

1. Resolve `-Commit` (default `HEAD`) in the game repo; output goes to `builds\<slug>\<first 8 of sha>\`. A build that
   already succeeded for that sha is reused unless `-Force`; a rebuild deletes the old `build_info.json` first, so a
   failed one never leaves an "ok" next to a player that is gone.
2. Source: `git clone --local --no-checkout` of the game repo into `<ggb>\src\<slug>` once (`--no-hardlinks` when the
   two are on different drives), then `fetch` + `checkout --force <sha>` + `clean -ffd` (its `.godot\`, the import
   cache, is kept by name, so later builds import only what changed). LFS files are checked out as pointers
   (`GIT_LFS_SKIP_SMUDGE=1`) and copied (never hard-linked: an import that rewrote a file in the clone would change the
   game's object) from the game repo's own store (`lfs.storage`, else `.git\lfs\objects`), so nothing is downloaded and
   the game repo is only read; an object missing from the store fails the build and names the `git lfs fetch` to run.
   Uncommitted work is not built.
3. The game as the commit has it: the project's name is the file name of the "Windows Desktop" preset's `export_path`
   in `export_presets.cfg` (`Build/Windows/<Project>.exe`, as the template writes it; the slug in PascalCase without
   one), and its platform comes from `Platform.json` (`Get-GGFPlatform`: desktop, mobile landscape or mobile
   portrait).
4. `godot --headless --path <clone> --import` through the limiter: the build fails when it exits with an error or its
   log has a script error (`SCRIPT ERROR`, `Parse Error`, `Failed to load script`).
5. The release player: `godot --headless --path <clone> --export-release "Windows Desktop"
   builds\<slug>\<sha8>\Windows\<Project>.exe`, into a fresh folder. The game's data is inside the exe (the preset's
   `embed_pck`), so the player is one file.
6. A mobile game's APK: `godot --headless --path <clone> --install-android-build-template --export-release "Android"
   builds\<slug>\<sha8>\Android\<Project>.apk`, with the toolchain's environment set for this process
   (`Set-GGFAndroidEnv`: `GRADLE_USER_HOME`, `JAVA_HOME`, `ANDROID_HOME`, the debug and release keystores). The engine
   puts its Gradle build template into the clone's `android\build\` (`android\.build_version` names the engine
   version) and Gradle builds the APK. The APK is then read back with the SDK's `aapt dump badging` and held to the
   mobile contract: package `com.<project lowercase>.game`, minSdk 26, targetSdk 34, arm64-v8a alone. The result is
   `android` in the row: `status` `ok`, `skipped` (with the `reason`: `-NoAndroid`, or a machine without the Android
   toolchain) or `failed` (the export's error, or what the APK got wrong). **A build whose APK is skipped or failed is
   still an ok build**: the Windows player is what is recorded, and the packager packages a mobile game without an
   APK as pending ([Dataset packager](#dataset-packager)).
7. Leak scan of the build's files (`Windows\`, and `Android\` with an APK): a case-insensitive byte search (ASCII and
   UTF-16LE) for the Windows user name inside paths (`\<name>\`, `/<name>/`) and for superposition / game-factory /
   game_factory / gamefactory / game factory / claude / anthropic / openai (`$ForbiddenNamePatterns` in `common.ps1`),
   one read per file; hits are warned about and recorded in `leak_scan` (a build with hits can still be recorded but
   must not be handed out: the dataset packager refuses it). `leak-scan.ps1 <dir>` runs the same scan by hand. A Godot
   export compiles no path into a player, so the clone may sit under the user's folder; the scan proves it for every
   build. It reads the files as they are stored: what is compressed inside the player's pack or the APK is not
   unpacked (the game's own text is the repo validator's to check).
8. The AutoPlay drop-in's version (the `VERSION` constant of the game's `addons/autoplay/autoplay.gd`, null without
   one) goes into the row: `record.ps1` refuses a build without it.

`builds.jsonl` row and `build_info.json` (next to the player, written only for an ok build; schema `godot-build/1`):
`game`, `project`, `platform` (`desktop` | `mobile`), `orientation` (`landscape` | `portrait` | null), `commit`,
`short_sha`, `requested`, `commit_subject`, `commit_time`, `command`, `start`/`end`/`duration_s`, `status`,
`exit_code`, `error_excerpt` (first matching error lines of the failing log), `log_path`, `output_path`, `exe_path`,
`config` (`release`), `player_bytes`, `android {status, reason, apk, bytes, package, min_sdk, target_sdk, abis}` (null
for a desktop game), `autoplay_version`, `leak_scan {scanned, hits[] {file, pattern, count, example}}`,
`godot_version`, `editor`, and `steps[]` (`import`, `player`, `android`: each with its exact command line, times, exit
code and log).

Measured on a 16-thread desktop PC beside other sessions' work, for a test game of one scene: the first build from a
fresh clone 28 s (22 s of it the first import); a portrait mobile game with its APK 85 s (the Gradle build 43 s, its
Gradle home already filled).

### Record

`record.ps1 <game> -Build <dir|latest> [-Scenario n] [-Runs k] [-Skill s] [-Seed s] [-MaxSeconds n]` (also
`-WallSeconds`, `-ExtraArgs`, `-CaptureNote`, `-OnScreen`, `-KeepMovie`). The frame's size is the build's own
platform: 1920x1080, or 1080x1920 for a portrait mobile game. Per run (seed = `-Seed + i`, or random; skill =
`-Skill`, or cycling 1.0 / 0.75 / 0.5 / 0.25):

1. Start `builds\<slug>\<sha8>\Windows\<Project>.exe` through the limiter (a general and a GPU slot) with the engine's
   movie arguments and the contract's flags (autoplay-contract.md section 1): `--write-movie <bundle>\raw\movie.avi
   --fixed-fps 60 --disable-vsync --log-file <bundle>\raw\game.log -- -autoplay -size <W>x<H> -scenario <n> -seed <s>
   -skill <s> -outputDir <bundle>\raw -maxSeconds <n> -buildCommit <sha> -runId <id> -goTimeout 300`, plus
   `-ExtraArgs`. The game runs **on a Windows desktop of its own** (`tools/task_check/desk.py`): its window shows
   nothing on the screen, can never be the foreground window and cannot take the keyboard or the cursor, so the
   machine stays with whoever uses it, and the game renders as usual. `-OnScreen` shows the window on the desktop
   instead. A recording needs a session that is logged on (a scheduled task run as the interactive user, or a
   terminal on the desktop): a process started over SSH has no desktop to render on.
2. Wait for the game to start (the limiter may hold it for a slot; `game.log` appearing is the sign), then up to 180 s
   for `ready.json`, then write `go`.
3. Wait for the game to quit by itself: it writes `outcome.json` and `clock.json` after the result hold and then
   quits, and the engine ends the movie file on its way out. A game still running `-WallSeconds` after go (default
   6 x `-MaxSeconds` + 600: a movie renders at the machine's pace, not in real time) is ended with everything it
   started, and the run fails.
4. Encode the video, validate and write the bundle (below), even for failed runs. The movie file is removed once the
   video is good (`-KeepMovie` keeps it; a failed run keeps it).

### The video

**The engine writes the movie; nothing is captured from the screen.** With `--write-movie` the engine steps exactly
1/60 s per frame, and after each frame it writes the frame it rendered (the root viewport's picture) and the sound it
mixed for that frame into `raw\movie.avi`: MJPEG pictures (quality `editor/movie_writer/video_quality` of the project,
0.9 in the template) and 16-bit 48 kHz stereo PCM, one block of 800 sample frames per picture. The engine takes as long
per frame as the machine needs, so the video has every frame exactly once whatever else the machine is doing: no
dropped or repeated frames, no start-time estimate, no audio alignment, no display, no idle user. That is why a
recording here is an ordinary GPU job and needs no screen, no queue and no user away from the keyboard.

- **Frame size.** The movie's frames have the project's `display/window/size/viewport_width` x `viewport_height` (the
  engine scales a frame of another size to it), and `-size` makes the game render exactly that (autoplay-contract.md
  section 2), so a frame is never scaled. A movie of another size than the game's fails the run.
- **Which frames.** A movie frame is an engine frame, counted from 0, and every row of the run carries its engine
  frame. `gameplay.mp4` is the movie's frames from the game's `go` clock sample to its `end` sample (the end of the
  result hold): the boot and the wait for `go` are left out, so the video's time is a row's `t`.
- **Encoding** (ffmpeg, CPU only, below-normal priority; `Export-GameplayMp4` in `common.ps1`):

  ```
  ffmpeg -i raw\movie.avi -map 0:v:0
    -vf "trim=start_frame=<go>:end_frame=<end + 1>,setpts=PTS-STARTPTS,scale=in_color_matrix=bt601:in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p"
    -c:v libx264 -preset medium -crf 18 -g 120 -r 60 -fps_mode cfr
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv
    -map 0:a:0 -af "atrim=start=<go / 60>:end=<(end + 1) / 60>,asetpts=PTS-STARTPTS" -c:a aac -b:a 192k -ac 2
    -movflags +faststart gameplay.mp4
  ```

  H.264 High yuv420p at the game's exact size, 60 fps constant, BT.709 limited range (a JPEG is full-range BT.601);
  AAC 192k stereo cut at the same frames. The result is checked with ffprobe: h264 + aac, the game's size, exactly
  `end - go + 1` frames.
- **Size on disk.** The movie is about 0.2 to 0.5 MB a frame for a busy 1080p picture, so a ten-minute run is some
  10 GB until it is encoded. The engine's AVI header counts in 32 bits and goes wrong past 4 GB; ffmpeg reads such a
  file to its end all the same (measured on a 4.5 GB file in the engine's layout: all 2,900 frames read).
- **ffmpeg**: `ggf-root.ps1` `Get-GGFFfmpeg` (env `GGF_FFMPEG`, `ffmpeg` in the config, the pinned copy
  `machine/get-ffmpeg.ps1` puts in `%GGF_ROOT%\tools\`, PATH), else the winget `Gyan.FFmpeg` package.

### Measured

On a desktop PC (RTX 4080, one 3840x2160 display, in use by other sessions), the release
players of two test games (a cube that moves on W or on a touch drag, a score label, a beep per point, a strip that
shows the engine frame's number and a patch of single-pixel checks), each recorded once on a desktop of its own:

| | Result |
|---|---|
| Desktop game | window 1920x1061 (what Windows gave it), frames 1920x1080; `gameplay.mp4` H.264 High yuv420p 1920x1080, 60/1, 481 frames, 8.017 s, AAC 48 kHz stereo; 8 stills 1920x1080; rendered at 46 fps |
| Portrait mobile game | window 1080x1061, frames 1080x1920 on the Mobile renderer; `gameplay.mp4` 1080x1920, 60/1, 481 frames; 8 stills 1080x1920; rendered at 55 fps |
| Frame numbers | every frame of both movies (553 and 551) shows the number of its engine frame, and every frame of both videos the number `go + k`: no frame dropped, repeated or shifted |
| Not scaled | the single-pixel checks are intact in the movie's frames and in the stills (mean difference of neighbouring pixels 254 and 250 of 255), and exact in PNG frames (`-shots`) of the portrait game in a 540x960 window: 1080x1920, 0 of 4096 pixels off |
| Sound | each beep starts 2 to 12 ms after the `t` of the `score` row that caused it (inside that frame's block of sound) |
| Touch | a finger put down at viewport (540, 1536) reached the game at (540, 1536) in the 1080x1061 window |
| Wait | each run waited two to three minutes for the limiter's VRAM guard before its game started |

### Bundle

```
recordings\<slug>\<slug>_S<scenario>_<yyyyMMdd-HHmmss>_s<seed>\
  gameplay.mp4        the dataset's Gameplay/ file (packaged as <slug>_S<n>.mp4): H.264 at the game's exact size
                      (1920x1080, or 1080x1920 for a portrait mobile game), 60 fps constant, AAC stereo, +faststart;
                      the run from go to the end of the result hold
  inputs.jsonl        as written by the game (autoplay-contract.md section 5)
  telemetry.jsonl     as written by the game
  outcome.json        as written by the game
  metadata.json       schema godot-autoplay-bundle/v1: run_id, game, project, platform, orientation, scenario,
                      scenario_name, seed, skill, max_seconds, extra_args, capture_notes, result, score, player, build
                      {commit, short_sha, config, godot_version, path, exe, autoplay_version}, clock {source,
                      qpc_frequency, t_ns_definition, samples: the game's start / go / end}, video {file, codec, width,
                      height, fps, cfr, audio, capture "movie", source, first_frame, last_frame, time_definition,
                      command: the exact command line of the run, ffmpeg_version}, machine {cpu, gpu, os},
                      created_utc, status, stills, gameplay_mp4 {file, video, audio, audio_offset_s (0: cut at the same
                      frames), first_frame, last_frame, frames, duration_s, bytes, error}
  validation.json     run_id, status ok | warn | failed, problems, warnings, per-check details (below),
                      game_exit_code, killed
  manifest.json       schema manifest/v1: sha256 + bytes of every file in the bundle (incl. raw\ and stills\)
  stills\NN.jpg       8 evenly spaced frames (t = duration * i / 9) at the video's size, for README screenshots, runs
                      with status ok / warn only; CPU decode (-ss before -i, -frames:v 1, -q:v 2); also copied to
                      recordings\<slug>\_stills\<run_id>_NN.jpg; metadata.json `stills` lists them. A failed extraction
                      is logged and recorded in `stills.error`; it never changes the run's status.
  FAILED              only on failed runs (problems listed); failed runs are kept, never deleted
  INVALID             excluded from the dataset after the fact (reason inside), e.g. recorded from a broken build;
                      written by mark-invalid.ps1, which also sets validation.json status "invalid" and adds a
                      runs.jsonl row; files kept
  raw\                the game's outputDir: inputs.jsonl, telemetry.jsonl, outcome.json, clock.json, ready.json, go,
                      game.log (the engine's log), watchdog.json (when its watchdog fired), player.log (the limiter's
                      and the launcher's lines), movie.avi (a failed run's, or with -KeepMovie)
```

`runs.jsonl` row (schema `godot-run/v1`): `run_id`, `game`, `scenario`, `scenario_name`, `seed`, `skill`,
`build_commit`, `build_path`, `status`, `platform`, `orientation`, `width`, `height`, `result`, `score`, `duration_s`,
`start`/`end`/`wall_s`, `capture` (`movie`), `render_fps`, `problems`, `warnings`, `bundle`; `mark-invalid.ps1` adds
`{event: "invalidated", run_id, time, reason, status_before, bundle}` rows.

### Validation (per run)

| Check | Fails when | Warns when |
|---|---|---|
| outcome | missing, bad `result`, `go_timed_out` | result `abort` |
| frame | the game rendered another size than the game's (`outcome.json` `viewport`), a mobile game ran on another renderer than `mobile`, the game did not run as a 60 fps movie | |
| inputs | no `inject` rows, unparseable lines, rows without `t_ns`, `qpc` and `frame`, `t_ns` going backwards | |
| telemetry | missing `run_start`/`scenario_start`/`scenario_end`/`run_end`, unparseable lines | |
| video | no movie, no go and end clock samples, `gameplay.mp4` not written (ffmpeg failed, another size, another number of frames than `end - go + 1`), a movie of another size than the game's, a frame rate other than 60/1 | the movie's frame count differs from the game's own by more than one |
| audio | the video has no sound track | silent (max < −60 dB) |
| process | game exit code ≠ 0, ended at the wall-time limit, game gone before `outcome.json` | |
| watchdog | `watchdog.json` (the drop-in's exit watchdog ended a game that hung) | |

`validation.json` `checks.video` also has `render_fps`, the frames of the run over the machine's seconds between go
and end: how fast the machine rendered, never a reason to fail.

`validate-run.ps1 <outputDir>` checks the same files of a run made by hand (no video): every row stamped with `t_ns`,
`qpc` and `frame`, the inject rows, the four telemetry events (a note when `score` or `state` events are missing or
`error` rows are there), the outcome, the three clock samples, no `watchdog.json`; it prints PASS or FAIL with the
problems and notes and exits 1 on FAIL. The sound is checked on a recording, whose movie carries it.

### Pipeline

`pipeline.ps1 <game>` resolves the commit (default HEAD) and the scenarios (default 1..n from the newest
`milestone/autoplay-<n>` tag reachable from it, meaning "scenarios 1..n are ready"), skips scenarios that already have
a good run (status `ok`/`warn`, not invalidated) of that commit unless `-Force`, then runs `build.ps1` and `record.ps1`
once per scenario: one recorded run per scenario is enough (AGENTS.md, "Priorities"). Each step takes the game's lock
itself, and every engine run waits for its slot in the limiter, so several pipelines and the sessions' own runs sort
themselves out: there is no queue. Game sessions do not run it; they send the coordinator what is ready (commit sha,
tag, scenarios, `validate-run.ps1` result, screenshot paths), and the coordinator runs:

```
powershell -ExecutionPolicy Bypass -File %GGF_ROOT%\godot-game-factory\tools\godot-pipeline\pipeline.ps1 <game> -Scenarios 1,2
```

AutoPlay time limit: 600 s of the run's own time per run by default (the game gets `-maxSeconds`), per scenario as
`1=300,2=600,3=900` (unlisted ones keep 600; `*=700` changes the rest) or one value for every scenario; values
30..7200. The `pipeline.jsonl` row lists the limit used per scenario.

**What a recording does differently** is said with `record.ps1 ... -ExtraArgs "<flags>" -CaptureNote "<what>"`: the
note goes to the run's `metadata.json` (`extra_args`, `capture_notes`), then to the dataset's manifest
(`scenarios[].capture_notes`) and a "Recording note" line under the README's Scenarios table.

Results: `.recording\<slug>\pipeline.jsonl` (schema `godot-pipeline/v1`: commit, scenarios, the time limit per
scenario, build {status, short_sha, output, platform, orientation, android {status, reason}, autoplay_version,
leak_scan_hits}, runs[] {run_id, scenario, status, result}, status `ok` / `partial` / `failed` / `skipped`, note) and
`runs.jsonl`. The summary's `build.leak_scan_hits` lists the build's leak-scan hits (`[]` = clean); warn-only here: a
build with hits can be recorded, but the dataset packager refuses it. `pipeline.ps1` exits 1 on `failed` and `partial`.

### Machine notes and open items

- A recording needs no display of any size and no idle user; it needs a logged-on session and a GPU slot. Its sound
  never plays on the speakers (the engine mixes a movie's sound into the file).
- A recorded run takes the machine's time, not the video's: 46 to 55 frames a second were written for the test games
  above, and a heavy scene renders slower than real time without harming the video.
- **Machine-path scrub before bundles leave the machine** (an open item). Bundles carry machine paths and the user
  name: `metadata.json` (build path, exe, the command line), `raw\game.log`, `raw\player.log`. A publish step must
  rewrite or drop these and re-hash `manifest.json` before any upload; the dataset itself takes only `gameplay.mp4`
  (and a few stills when the game has no screenshot of its own).

## Creation replay

`tools/godot-replay/` rebuilds a game from its first commit by re-running, in order, what its builder ran: each
commit's files, the engine's import, and the committed generator steps (`steps/*.gd`). It then checks the result
against the game's final commit and writes the dataset's `ReplayScripts/` with `Verification/report.json`
([schemas/replay-report.schema.json](schemas/replay-report.schema.json)): the dataset is complete only with that report,
and its verdict, PASS or FAIL, is metadata ([game-format.md](game-format.md), "Complete vs pending"). It reads three
records:

| Record | What it gives the replay |
|---|---|
| git history (`games\<slug>`) | the exact files at every commit, and the committed generated files to compare against |
| `workflow.jsonl` | the row of each step run (`source.script`, `source.sha256`, `status`) |
| `.recording\<slug>\actions.jsonl` | the agent's tool calls in order: every step run (with the command line and its output), every `Write`/`Edit` (`apply_patch` under Codex) of a file, every shell command |

It also reads `.recording\<slug>\commits.jsonl` for the moment each commit was made. What makes that work is the
godot-game-session skill's rules for a history that replays: scenes and resources written as text with the agent's
file tools, generator steps committed under `steps/` and run only through `Scripts/godot.ps1 step`, relative paths,
no amend or rebase. A file the engine or a step writes (`.import`, `.uid`, a step's output) is never copied from a
commit when the replay produced it, so errors accumulate visibly instead of being reset. Every engine run of the
replay goes through the limiter, headless (a general slot, never a GPU slot).
`python tools/godot-replay/godot_replay.py release --game <slug>` makes the dataset's `ReplayScripts/` at the release
commit, in `<out>\_replay\<slug>\<sha8>\`, where the packager takes it ([Dataset packager](#dataset-packager)). The
game's settings are its `ReplayConfig.json`. Everything else is in [godot-replay.md](godot-replay.md).

## Dataset packager

`python tools/package-dataset.py <slug>` builds a game's dataset from its repo, the pipeline's release build, its recordings and its creation replay.

## Names that must not reach the games

User's rule: the names **Superposition**, **game-factory** and **godot-game-factory** (case-insensitive, incl.
`game_factory`/`gamefactory`) must not appear in a game (repo files, code, commit messages, builds, logs, in-game files,
anything passed to the game process), and agent, model and provider names stay out too (godot-game-session skill,
"Names"). Recording/workflow traces are fine and `workflow.jsonl` stays in the game repos. `templates/new-game.ps1`
refuses the names in what it writes, `tools/validate-game.py` checks a repo's tracked text for them and for the
account name, and `build.ps1`'s leak scan checks every file of a release build for them, the account name in paths and
`openai`.

- The flags the recorder passes to the game (`-autoplay -size -scenario -seed -skill -outputDir -maxSeconds
  -buildCommit -runId -goTimeout`, the engine's `--write-movie`, `--fixed-fps`, `--disable-vsync` and `--log-file`,
  autoplay-contract.md section 1) and the paths under `%GGF_ROOT%\recordings\`, `builds\` and `<ggb>\` contain none of
  the names.
- The pipeline's own files (`.recording\*.jsonl`, `build_info.json`, bundle `metadata.json`, docs) may name things
  freely.
- A game repo that names them can be cleaned in place, each tool a dry run first and archiving the original history
  before it changes anything: `tools/godot-pipeline/scrub-lfs-history.py <slug>` (the account and agent names in the
  history's LFS objects, every commit repointed: `--apply`) and `scrub-history.ps1 <slug>` (the studio and tool names
  in text blobs, messages and identities: `-Apply`). Neither pushes. The dataset packager needs neither: it delivers
  a scrubbed and patched copy.
