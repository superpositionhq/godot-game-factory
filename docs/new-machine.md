# Setting up a new machine

Goal: a teammate with a fresh Windows 11 PC goes from nothing to building Godot games with **one command** plus the
few sign-ins that cannot be scripted. Under an hour, most of it downloads (the engine with its export templates is
1.4 GB to download and 2 GB on disk; the Android toolchain, when you want it, another 2 GB). `machine/setup.ps1` does
the rest; it is idempotent: after any manual step, run it again and it continues where it stopped.

**Other factories on the same PC.** Several can live on one machine. This one has its own root
(`%USERPROFILE%\GodotWork`), config (`%USERPROFILE%\.godot-game-factory\config.json`), hooks folder
(`%USERPROFILE%\.godot-game-factory\hooks\`) and skills (`godot-commit-always`, `godot-game-session`,
`godot-desktop-game`, `godot-mobile-game`, `godot-sound`, `godot-write-tasks`); setup and bootstrap add their entries
next to the other factories' and never change them. A session is recorded by the factory whose `games\<slug>` folder
one of its tool calls names. They share one thing on purpose: the machine-wide job slots (`godot-heavy.ps1` takes the
same named mutexes as the other factories' limiters, and also holds its GPU jobs back while another factory records
the screen), so together they never run more heavy or GPU jobs than the PC holds.

## Before you start

| You need | Why |
|---|---|
| Windows 11, 8+ logical cores, 16 GB RAM (32 GB recommended), 100 GB free on the drive that will hold the root | setup checks these first; the job slots scale with RAM |
| A GPU with Vulkan and a current driver, and a signed-in desktop | plays, recordings and task plays are rendered; imports, exports and generator scripts run headless without one |
| Only to push game repos: a GitHub account that is a member of `<org>` (the organisation, or user, that owns `godot-game-factory` and the private `godot-game-<slug>` repos), allowed to create private repos there. A game that is built and submitted from this PC stays on it and ships in the dataset zip: that needs no GitHub account, and a note that no GitHub repo was made is expected | setup asks whether to sign in |
| A coding-agent account: Claude, or OpenAI (a ChatGPT plan or an API key) | the agent that builds the game: Claude Code in a terminal or the Claude desktop app (Code tab), or the Codex CLI in a terminal (`setup.ps1 -Agent claude\|codex\|both`) |

No engine licence and no engine account are needed. The engine and the Android toolchain are unpacked under the root;
only the winget packages below are installed machine-wide (some show a UAC prompt).

## 1. Run setup

Get the repo's `machine\setup.ps1`: on github.com open `<org>/godot-game-factory`, **Code > Download ZIP**, unzip it
anywhere and run `machine\setup.ps1` from it (setup then clones the repo properly into the root). Or clone the repo to
`<root>\godot-game-factory` yourself and run it from there.

The one command (in the folder holding `setup.ps1`):

```bash
powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org>
```

Options: `-Agent claude|codex|both` (the coding agent; default: what is installed), `-Root D:\GodotWork` (the machine
root; default `%USERPROFILE%\GodotWork`, asked on the first run), `-Android` (also the Android toolchain, section 3),
`-CloneGames` (clone every `<org>/godot-game-*` repo), `-Yes` (answer yes to every question).

What it does, in order (log: `<root>\.setup\setup.log`):

1. **Hardware precheck** against the minimums above.
2. **Software through winget**, after one question (winget accepts each package's licence; some show a UAC prompt):
   Git + Git LFS, GitHub CLI, Python 3.12; with Codex the Codex CLI (`OpenAI.Codex`).
3. **GitHub sign-in, asked first** (`gh auth login` in the browser; only people who push game repos need it) and your
   git `user.name` / `user.email`.
4. **godot-game-factory**: cloned into `<root>\godot-game-factory`, then
   - `machine\get-godot.ps1`: the pinned Godot editor and its export templates (`machine\godot.json` names the
     version) into `<root>\godot\<version>\`, each archive verified against its SHA-512;
   - `machine\bootstrap.ps1`: config with `github_org`, job slots, layout, tools, ffmpeg, skills, root `CLAUDE.md`
     and/or `AGENTS.md`, and the recording hooks for your agent after it has shown what they record and asked; the
     games when you said so;
   - with `-Android`, `machine\get-android.ps1` (section 3);
   - `machine\check.ps1`.
5. **A PASS / TODO list.** Each TODO says exactly what to do; do it and run setup again.

## 2. What only you can do

| Step | How | Detected by |
|---|---|---|
| Agent sign-in | Claude Code: run `claude` once (or open the desktop app) and sign in. Codex: `codex login` (`--device-auth` without a browser) | Claude: not detectable; Codex: `codex login status` |
| GPU driver | the vendor's current driver; Godot renders with Vulkan | `check.ps1` lists the GPU |

## 3. The Android toolchain (for a mobile game's APK)

A mobile game is made, played, recorded and task-checked on the PC without it. Only the APK needs it: without the
toolchain the build step skips the APK and says so, and the game's dataset waits for it.

```bash
powershell -ExecutionPolicy Bypass -File machine\get-android.ps1
```

(or `setup.ps1 -Android`). It is headless and takes a few minutes. Everything goes into `<root>\android\`; nothing is
installed machine-wide and no PATH or environment variable is changed:

- `jdk\`: a JDK 17 (Eclipse Temurin; the build `machine\android.json` pins, SHA-256 verified). Godot's Android build
  needs JDK 17.
- `sdk\`: the Android SDK command-line tools (`android.json`, SHA-256 verified), and through their `sdkmanager`
  `platform-tools` plus the build-tools and platform the installed engine's Android build template names in its own
  `config.gradle` (Godot 4.7.2: `build-tools;36.1.0` and `platforms;android-36`). These packages come under the
  Android SDK licence agreements: the script says so and asks before accepting them for you (`-Yes` accepts without
  asking; a non-interactive run without `-Yes` stops there). The NDK is not needed for a game's Gradle build; `-Ndk`
  installs the one the template names.
- `keystores\`: `debug.keystore` and `release.keystore`, made on the machine with the JDK's keytool. The release
  keystore signs every APK this machine builds. Keep the folder: an APK signed with another key does not install over
  one signed with this.
- `gradle\`: the Gradle home of every Android build (Gradle itself and what it downloads on the first build, about
  1 GB), with the Gradle daemon turned off so no Java process outlives a build.
- `toolchain.json`: what was installed, and the keystores' users and passwords.

It then writes four lines into the editor's own settings file
(`<root>\godot\<version>\editor_data\editor_settings-4.7.tres`): where the JDK and the SDK are, and the debug
keystore. Run it again after the engine version changes: a new engine's build template may name other SDK packages.

A game's export preset asks for a Gradle build with `min_sdk` 26, `target_sdk` 34 and `arm64-v8a` alone (the template
sets it). The first APK build on a machine downloads Gradle and the Android build's libraries into `<root>\android\gradle`
and so needs the network; later builds do not.

`machine\check.ps1` lists the toolchain piece by piece: the JDK, each SDK package, each keystore, the editor settings.
A missing piece is a WARN that names `get-android.ps1`.

## 4. The first session

- **Desktop app, several games at once (Claude only):** open the Code tab in the root folder and start a coordinator
  session; add its session id to `<hooks dir>\recording-exclude.txt`. It starts the game sessions (`CONTINUE` for
  cloned games, `NEW` for new ones) from [briefs/game-session.md](briefs/game-session.md).
- **Solo, one game in a terminal:** `cd <root>`, run `claude` or `codex -s danger-full-access`, and paste
  [briefs/solo-game.md](briefs/solo-game.md) with its placeholders filled. Same rules and the same recording with
  either agent; you take the coordinator's decisions (pushes, recordings). What differs between the agents:
  [AGENTS.md](../AGENTS.md), "Agents".

Start sessions in the GodotWork root (or a game folder under it), never in another factory's root: the root's
`CLAUDE.md` / `AGENTS.md` decides which factory's rules a session follows.

## Reference: what the scripts write

`machine/get-godot.ps1`: `<root>\godot\<version>\` (the editor exe, its console wrapper, the empty `._sc_` file that
makes it self-contained, `editor_data\export_templates\<version>.stable\`). Nothing else.

`machine/bootstrap.ps1` (run by setup; can be run on its own any time):

- `%USERPROFILE%\.godot-game-factory\config.json`: `root`, `ggb` (`<root>\_build`: the release builds' private
  clones), `checkout` (the clone it ran from), `github_org`, `record_extra_projects`, `agents`, `hooks_dir`; the job
  slots `heavy_slots` / `gpu_slots` sized from the hardware (the same formula the other factories on the machine
  use), with their basis in `slots_auto` (values edited by hand are kept, `-Force` recomputes);
- the layout `games\ tasks\ builds\ recordings\ .recording\ deliverables\ asset-library\ tools\` and `<ggb>\src`
  (`builds\` and `recordings\` are the recording pipeline's, `deliverables\` holds the creation replay's packages and,
  per game, the dataset packager's commit maps, audit files and run lock);
- `tools\godot-heavy.ps1` (the machine-wide job limiter) with `tools\ggf-root.ps1` and `tools\godot.json`; ffmpeg (one
  that is already on the machine is used; else the pinned 8.1.2, SHA-256 verified, into `tools\ffmpeg-8.1.2\`);
- the recording hooks in the hooks dir (`hooks_dir` in the config, default `~\.godot-game-factory\hooks\`), wired into
  `~\.claude\settings.json` for Claude Code and `~\.codex\hooks.json` + trust entries in `~\.codex\config.toml` for
  Codex (backup first; asked first, `-Yes` skips the question; only the handlers that run `record-godot-action.ps1`
  are added or updated, any other hook stays); the `godot-*` skills from `skills\` in
  `~\.claude\skills\` and/or `~\.agents\skills\` (other skill folders untouched); `<root>\CLAUDE.md` importing
  `godot-game-factory/CLAUDE.md` and/or `<root>\AGENTS.md` naming `godot-game-factory\AGENTS.md`;
- Git LFS filters, the post-commit hook in every game repo (the commit recorder), and with `-CloneGames` every
  `<org>/godot-game-*` repo.

`machine/get-android.ps1`: `<root>\android\` (section 3), four lines of the editor settings file, and
`"android": {"home": ...}` in the config when there is one.

`machine/check.ps1` writes nothing. It reports PASS / WARN / FAIL for the engine and its export templates, git,
Git LFS, GitHub access, Python, ffmpeg, the GPU, disk, config, the job slots and where each count comes from, layout,
hooks, skills, game repo hooks and the Android toolchain; its exit code is the number of FAILs; for each agent it also
checks the install, the sign-in (Codex) and that the hooks are wired (and, for Codex, trusted). Details of every
file: [../machine/README.md](../machine/README.md).

## Toolchain notes

- One engine version for every game: `machine\godot.json`. A game's `project.godot` names its feature version
  (`config/features`), and the validator holds it to the factory's. Moving the factory to a new engine version is a
  change to `godot.json` (version, file names, URLs, SHA-512), then `get-godot.ps1` and `get-android.ps1` on every
  machine.
- The editor is self-contained: its settings, its export templates and its caches are in
  `<root>\godot\<version>\editor_data\`, not in `%APPDATA%`. Tools run the console wrapper
  (`Godot_v<version>-stable_win64_console.exe`), which waits for the engine and passes its output and exit code on.
- Each project's `.godot\` folder is a local cache (git-ignored) that the first import rebuilds: run a fresh clone's
  first import through `godot-heavy.ps1` like any heavy job.
- Headless runs (`--headless`: imports, exports, generator scripts) need no GPU and no desktop. A rendered run needs
  both: start it from a signed-in desktop session, not from a remote shell that has none.
- The editor makes an empty `.android` folder in `%USERPROFILE%` whenever it opens a project that has an Android
  export preset. Nothing is kept in it: the Android tools' own files are in `<root>\android\.android`.

## Scratch test (without touching a live setup)

`-DryRun` reports installs, downloads, sign-ins and game clones without doing them. It runs bootstrap only when it is
given a scratch config, hooks dir and agent folders (bootstrap writes to all of them), and then against those only:

```bash
powershell -ExecutionPolicy Bypass -File machine/setup.ps1 -Org <org> -DryRun -Agent both -Root C:/ggf-test/GodotWork -ClaudeDir C:/ggf-test/home/.claude -CodexDir C:/ggf-test/home/.codex -AgentsSkillsDir C:/ggf-test/home/.agents/skills -HooksDir C:/ggf-test/home/.godot-game-factory/hooks -ConfigPath C:/ggf-test/home/.godot-game-factory/config.json
```

Copy the real `settings.json`, `hooks.json` and `config.toml` into the scratch agent folders first to see exactly what
bootstrap would add to them. With `GGF_CONFIG` set to the scratch config, `powershell -ExecutionPolicy Bypass -File
templates/new-game.ps1 -Slug <game> -Path C:/ggf-test/GodotWork/games/<game> -NoGitHub -Root C:/ggf-test/GodotWork
-HooksDir C:/ggf-test/home/.godot-game-factory/hooks` creates a game without creating a GitHub repo.
