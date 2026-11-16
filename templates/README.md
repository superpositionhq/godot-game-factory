# templates/

## godot-game/ + new-game.ps1

Skeleton of a game repo for Godot 4 (the factory's pinned version, `machine/godot.json`; the standard build, GDScript).
`new-game.ps1` instantiates it:

```bash
powershell -ExecutionPolicy Bypass -File templates/new-game.ps1 -Slug island-survival -Path C:/Users/<you>/GodotWork/games/island-survival -Title "Island Survival" -Description "Stranded on a tropical island..."
```

It copies `godot-game/`, replacing `__PROJECT__` (PascalCase: the name of the exe and the APK; default from the
slug), `__SLUG__`, `__TITLE__`, `__DESCRIPTION__`, `__GODOT_VERSION__` and `__GODOT_FEATURE__` in names and contents;
copies the AutoPlay drop-in (`tools/godot-pipeline/autoplay/addons/autoplay/`, unchanged) into `addons/autoplay/`;
writes the first `workflow.jsonl` row (`project.create`); runs `git init -b main` + `git lfs install --local`; adds
the commit recorder to `post-commit` (`machine/install-git-hook.ps1`); runs the first import
(`Scripts/godot.ps1 import`) when the editor is installed, so the `.import` and `.uid` files the engine writes are in
the first commit (`-NoSetup` skips it); makes the first commit; and creates the private GitHub repo
`<org>/godot-game-<slug>` (`github_org` in the machine config, or `-Org`) as `origin` without pushing (`-NoGitHub`
skips that; an existing repo of that name is never linked: it may be another game's, or public). It refuses names
containing Superposition, game-factory, Claude, Anthropic or OpenAI, and titles with quotes, backslashes or line
breaks (they land in quoted strings of `project.godot` and the first scene).

`-Platform mobile -Orientation landscape|portrait` makes an Android phone game instead. The files of
`godot-game-mobile/` are laid over the skeleton: `project.godot` (the Mobile renderer, the phone's size, 1920x1080 or
1080x1920, and orientation, the touch settings, ETC2/ASTC texture import, the back button left to the game),
`export_presets.cfg` (the Android preset beside the Windows one: package `com.<project in lower case>.game`, minSdk
26, targetSdk 34, arm64 alone, a Gradle build), `game/phone.gd` (the autoload `Phone`: the call that tells the
AutoPlay drop-in the game is played by touch), a first scene with an on-screen button that reads touch, and a
`README.md` that says what the game is made for. `Platform.json` (`{"platform": "mobile", "orientation": ...}`) is
written at the root: that file is how every later tool knows the game is a mobile game; a game without it is a
desktop game. `-Orientation` is required with `-Platform mobile` and refused without it. The default, `-Platform
desktop`, creates a desktop game: `godot-game/` is the same for both.

What the skeleton carries, and why:

| File | Why |
|---|---|
| `project.godot` | the game's name, the first scene, the engine version (`config/features`), the renderer (Forward+; a mobile game: Mobile), the frame size (1920x1080; a portrait mobile game 1080x1920) with stretch mode `canvas_items` and aspect `expand`, so a frame of that size shows what a window or phone of that size shows, and the autoloads `AutoPlay` and `Scenarios` (a mobile game: `Phone` too) |
| `export_presets.cfg` | the preset `Windows Desktop` as the engine writes it: x86_64, the game's data embedded in the exe (one file), and an exclude filter that keeps what is not the game out of the player (`steps/`, `addons/task_probe/`, `*.md`, `workflow.jsonl`, the JSON files at the root). A mobile game also has the preset `Android`: a Gradle build, min SDK 26, target SDK 34, arm64-v8a alone, package `com.<project lowercase>.game` |
| `scenes/Main.tscn`, `icon.svg` | a first scene that runs and shows something: a lit block, a camera, the game's title |
| `game/scenarios.gd` | the autoload `Scenarios`, the scenario list: scenario n's scene and name, loaded from `-- -scenario <n>` and from AutoPlay's `start_scenario` (docs/autoplay-contract.md, section 6) |
| `steps/README.md` | where generator scripts go and the rules that keep them replayable |
| `Scripts/godot.ps1` | `import`, `step`, `row`, `build`, `play`, `autoplay`: the game's engine runs through the machine's job limiter, logs in `Logs/godot-ps1/`; `import` is the engine's import followed by a pass that loads every `.gd` of the project and fails on one that does not parse (the import alone parses only the scripts the editor opens); `step` and `row` write `workflow.jsonl` rows; `autoplay` is the AutoPlay hand test (docs/autoplay-contract.md, section 7) |
| `ReplayConfig.json` | the creation replay's settings for the game (docs/godot-replay.md) |
| `.gdignore` in `Brief/`, `Docs/`, `Dataset/`, `Scripts/` | an empty file that keeps the engine out of a folder: nothing there is imported or exported (briefs, README images, the dataset's videos) |
| `.gitignore` | the engine's cache (`.godot/`), root-anchored output (`/Build/`, `/Logs/`, `/android/`), local results, and secrets and keystores anywhere: everything else is committed, `*.import` and `*.uid` included |
| `.gitattributes` | `* text=auto`, Godot's text files and GDScript as LF text, every binary type in LFS case-insensitively |
| `Docs/ThirdPartyNotices.md`, `assets.manifest.json`, `Docs/screenshots/` | third-party credits; the asset manifest (`assets-manifest/v1`); README images |
| `Brief/` | where the session puts the brief (`brief.md`) and writes the design doc (`design.md`) |
| `Dataset/` | the dataset placeholder (`Gameplay/`, `Screenshots/`, `ReplayScripts/`, README) |

Not in this folder but in every new game: `addons/autoplay/`, the AutoPlay drop-in, which `new-game.ps1` copies
unchanged from `tools/godot-pipeline/autoplay/addons/autoplay/` so every game has the same one; a game made before a
change of it gets the new one with `tools/godot-pipeline/autoplay/install.ps1` (docs/autoplay-contract.md, "Getting the
drop-in").

`workflow.jsonl` conventions (schema `godot-workflow/v0`, one row per operation at the moment it happens, id prefix
per game, row ids in commit messages) are in the godot-commit-always and godot-game-session skills (`skills/`).

## godot-game-mobile/

The files a mobile game has instead of the skeleton's, and `game/phone.gd`, which only a mobile game has; never
used alone. `__ORIENTATION__` (`landscape` or `portrait`), `__PORTRAIT__` (`true` or `false`), `__PHONE_WIDTH__` and
`__PHONE_HEIGHT__` (1920x1080, or 1080x1920 for portrait), `__HANDHELD__` (`display/window/handheld/orientation`: 0
landscape, 1 portrait) and `__ANDROID_NAME__` (the project name in lower case, for the package name) are replaced
with the skeleton's placeholders. `tools/validate-game.py` holds a mobile game's `project.godot` and Android preset
to what is written here.
