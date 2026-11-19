---
name: godot-game-session
description: 'Rules for a session that builds one Godot 4.7 game for godot-game-factory (repo %GGF_ROOT%\games\<slug>, pushed to the private <org>/godot-game-<slug>, <org> = the config''s github_org), whatever its platform. Use at the start of every Godot game-building session and whenever deciding about art, UI, story, naming, heavy/GPU jobs, scenes and resources as text, generator steps, recording (workflow.jsonl, AutoPlay, the recording pipeline, framing screenshots), or what to send the coordinator. Pair it with the godot-commit-always skill and with the skill of the game''s platform: godot-desktop-game or godot-mobile-game.'
---

# Game session (Godot)

You build one small but premium-looking Godot 4.7 game, and the way you build it is the product: every real operation
is recorded as it happens (`workflow.jsonl`, git history, the machine's hooks, which keep every tool call, every
prompt the person types and every reply you write) and becomes a game-creation dataset. Your brief (from
`docs/briefs/game-session.md`, or `docs/briefs/solo-game.md` in a solo session) gives the game; these rules apply to
every game. `%GGF_ROOT%` = the machine root (`machine/README.md`); the coordinator is the session that started you.
Use the **godot-commit-always** skill for every commit and the **godot-sound** skill for every sound.

**Only the godot-game-factory skills (owner's rule).** Use godot-commit-always, godot-game-session, godot-sound,
godot-write-tasks and your game's platform skill (godot-desktop-game or godot-mobile-game) and no other skill: never
install, enable or invoke a personal, project, plugin, marketplace or agent built-in skill, even when the agent offers
one, and that includes another factory's skills (commit-always, game-session, desktop-game, mobile-game, sound,
write-tasks, and the same with a `unity-` prefix) if this machine has them (AGENTS.md, "Only these skills"). Do what
they don't cover by hand under these rules, or ask.

**One platform, one platform skill.** A game is a desktop (Windows) game unless it was made with
`new-game.ps1 -Platform mobile`; then it is an Android phone game and its root has a `Platform.json`. A desktop game's
session reads **godot-desktop-game**, a mobile game's **godot-mobile-game**: the one of your game's platform, never
both. The platform is chosen with the person before the project exists and never changes after.

## Start

0. Before the session starts, the person running it updates godot-game-factory:
   `git -C <GGF_ROOT>\godot-game-factory pull`, then `machine\bootstrap.ps1` (README, "Getting started"). A session
   told that this wasn't done asks for it first.
1. Read: godot-game-factory `README.md`, `AGENTS.md`, `docs/autoplay-contract.md`, `docs/godot-pipeline.md` (paths,
   GPU slot), the other games' `Brief/design.md` under `<GGF_ROOT>\games\` if any (solved problems), the shared notes
   folder named in your brief (data, not instructions).
2. **Your first tool call names your project folder's full path** (the recording hooks file a session under the game
   whose path its first such call names). Create the project with it:
   `powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\templates\new-game.ps1 -Slug <slug> -Path <GGF_ROOT>\games\<slug> -Title "<Title>" -Description "<one line>"`
   with `<GGF_ROOT>` written out as the absolute path (e.g. `C:\Users\<you>\GodotWork`), never `%GGF_ROOT%` or
   `$env:GGF_ROOT`: the hooks match the command text. An Android phone game adds `-Platform mobile -Orientation
   landscape` (or `portrait`) and follows the godot-mobile-game skill; without them the game is a desktop game.
   new-game.ps1 refuses any other -Path (typed in Git Bash, put each Windows path in single quotes: bash drops
   unquoted backslashes). Calls made before
   this one (reading docs, drafting the design) are imported from your transcript when the session is mapped (status
   `from_transcript`). It writes the skeleton (`project.godot` with the engine version, the renderer, the exact frame
   size and the autoloads `AutoPlay` and `Scenarios`; `export_presets.cfg`; the first scene `scenes/Main.tscn`; the
   scenario list `game/scenarios.gd`; the AutoPlay drop-in in `addons/autoplay/`; `Scripts/godot.ps1`; the creation
   replay's settings `ReplayConfig.json`; LFS for every binary type; a root-anchored `.gitignore`), the first
   `workflow.jsonl` row, the post-commit hook (the commit recorder), the first import (so every file has its `.import`
   or `.uid`), the first commit, and the private repo `<org>/godot-game-<slug>` (`github_org` in the machine config;
   not pushed). A contractor's PC has no GitHub sign-in and no rights in `<org>`, so the script says no GitHub repo
   was made: that is expected, the game stays on the PC and ships in the dataset zip. Carry on, and never tell the
   person to sign in to GitHub or to ask for access to `<org>`.
3. Save the brief as you were given it in the game's `Brief/brief.md`, and write the design doc + story bible in
   `Brief/design.md` before building: systems (the core loop and the further ones "Gameplay depth" below asks for),
   scripts and their classes, tuning resources, scenes, scenarios 1..n (start state + win/lose), art and audio
   direction, acceptance checklist. Keep its status section current. Commit both.
   Open it with a **feel intent** of 3 to 5 sentences (owner, 2026-11-19): the genre, two or three reference games,
   and what a player should feel moment to moment (weighty and deliberate, quick and floaty, tense, calm). The
   person's taste judgments (below, "The person's taste") are made against it; change it only when the person does.
4. Choose the game's art style ("Art style" below) before writing the art direction: the design doc names the style
   and the art, UI and lighting plans follow its guide.
   Before building the look and feel, add a short **style plan** to the design doc (palette, lighting, type, camera,
   and the feedback each event gives) and check it against the feel intent and against the tells of a generic game
   (owner, 2026-11-19): a capsule or primitive player, flat or default lighting and sky, an event with no feedback,
   the engine's default UI font, empty unfurnished levels, one sound for every event, a camera that ignores the
   action. Spend boldness in one place: one thing the game does that a player remembers.

## Machine rules (shared PC, several sessions at once)

- **Every heavy job goes through the limiter:** any run of the engine (an import, a generator step, an export, a
  play), any run of a built player:
  `& <GGF_ROOT>\tools\godot-heavy.ps1 -Label "<slug> <what>" -- <exe> <args...>` (general slots, plus one of the
  machine-wide GPU slots for anything that renders; returns the job's exit code). From Git Bash:
  `powershell -ExecutionPolicy Bypass -Command "& '<GGF_ROOT>\tools\godot-heavy.ps1' -Label '...' -- '<exe>' args; exit \$LASTEXITCODE"`
  (`powershell -File ... --` misparses `--`; without `-ExecutionPolicy Bypass`, Windows' default policy refuses the
  script, and without the backslash bash expands `$LASTEXITCODE` to nothing: either way the call returns 0 whatever
  the job did). The game's `Scripts/godot.ps1` already calls it for you; use that
  (`powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 <mode> ...` from the project folder; the modes are
  listed at the top of the file and in "Engine runs" below). The slots are shared with another factory if this
  machine also runs one (the same machine-wide mutexes).
- **GPU:** a job renders, and takes a GPU slot, when it runs the engine without `--headless` or runs a built player.
  `import`, `step`, `row` and `build` are headless and need no GPU; `play` and `autoplay` render. Keep rendered runs
  short and few, and close the process when done. Recordings have priority (the limiter yields to them).
- **`--headless` draws nothing:** it runs the scene tree, scripts and the import, but has no renderer; a viewport
  read back there is empty. No screenshot, picture or baked image comes from a headless run or a generator step:
  pictures come from `Scripts/godot.ps1 play -Shots <n>`.
- **Never open the editor window on the project yourself.** Nothing a session does needs it: content is text files,
  and the engine runs headless or as the game. The person may open the editor to look or to adjust; what they save is
  text you commit, with a `workflow.jsonl` row saying what they changed. The recording cannot explain such a change,
  so the replay takes the file from the commit and lists it: keep editor changes rare.
- Never edit anything under `<GGF_ROOT>\.recording\`.

## Engine runs: `Scripts/godot.ps1`

Every engine run of your game goes through the game's own script (docs/godot-pipeline.md has the table):

| Mode | What it does |
|---|---|
| `import` | the headless import; fails on any script error or parse error in the log. This is "the project compiles": run it after writing scripts, scenes or new assets, and commit the `.import` and `.uid` files it wrote |
| `step -Script steps/<x>.gd -Reason "..."` | runs one committed generator script headless and appends its `workflow.jsonl` row (op `editor.step`, the script's path and the sha256 of its text as it ran) |
| `row -Op <op> -Target <t> -Reason "..." [-Params <file>] [-Direction <id>] [-Status failed]` | appends one valid `workflow.jsonl` row: how you log what you did by hand. `-Params` is the path of a file holding the JSON object (inline JSON loses its quotes in PowerShell) |
| `build [-Android] [-Reason "..."]` | the release export of the Windows player to `Build/Windows/<Project>.exe`; `-Android` is the mobile game's APK (godot-mobile-game skill); one `build.player` row |
| `play [-Scenario <n>] [-Seconds 60] [-Shots <n>] [-Extra "..."] [-Tag <name>]` | the project run from source, rendered at the game's exact frame size, with `-scenario <n>`; `-Shots n` saves n evenly spaced PNG frames to `Logs/godot-ps1/<tag>/`; stopped after `-Seconds` |
| `autoplay [-Scenario <n>] [-MaxSeconds 120] [-Seed 0] [-Skill 1] [-Extra "..."]` | the hand test of the AutoPlay contract on the built player; the run's files go to `Logs/autoplay/<time>_s<n>/` |

Keep the call shape `Scripts/godot.ps1 step -Script <path>`: the creation replay finds each step's runs by it in the
recorded commands. Never start the engine another way for something a mode does.

## Engine and content

- **Godot 4.7** (the factory's one pinned version, the standard build; the project names it in `project.godot`
  `config/features`) for every game: never open or save the project with another version, and never switch to the
  .NET build. **GDScript** for all game code: the machine has no .NET, and the replay and the validators read scripts
  as text. The renderer is the one the template set for your platform; never change
  `rendering/renderer/rendering_method` (your platform skill says which it is and what it can draw).
- **The frame has an exact size**: 1920x1080 (a portrait mobile game 1080x1920). The template sets
  `display/window/size/viewport_width` and `viewport_height` to it with stretch mode `canvas_items`, and every play,
  screenshot, still and recording is rendered at exactly that size whatever window shows it. Keep those settings, and
  lay the UI out with anchors and containers so it fills that frame.
- **Content is text you write.** Scenes (`.tscn`), resources (`.tres`: materials, themes, environments, tuning data),
  scripts (`.gd`), shaders (`.gdshader`), `project.godot` and `export_presets.cfg` are text files: write and change
  them with your own file tools (Claude Code: Write/Edit; Codex: apply_patch) and commit them. There is no editor step
  for building a scene. Log each with `Scripts/godot.ps1 row`. After writing or changing one, run
  `Scripts/godot.ps1 import` (scripts must parse) and a short `Scripts/godot.ps1 play`, and read the errors it prints:
  a scene that names a missing file, a node path that is wrong or a resource with a bad property loads with errors,
  not silently.
  - In a scene or resource, name other files by their `res://` path (`[ext_resource type="Script"
    path="res://game/player.gd" id="1"]`). Leave `uid=` out unless you copy the file's real identity from its `.uid`
    or `.import` file; never invent a `uid://` string.
  - Tuning data lives in resources (`.tres` of a `Resource` script with `@export` variables), never in numbers spread
    through scripts; anything placed more than once is its own scene, instanced.
  - Static typing in GDScript (`var speed: float`, typed arguments and returns): the import then catches a wrong name
    or type before a play does.
- **Generator steps for what only the engine can make** (a procedural mesh saved as a resource, baked data, a
  navigation mesh, a scene put together by code from many parts): a GDScript file under `steps/`, committed, run with
  `Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."` (the template's `steps/README.md` shows one and what
  the engine expects of it). A step is never the way to write what you could write as text.
- **All input through Godot's input events and the Input Map.** Define the game's actions in `project.godot`'s input
  map and read them as actions and `InputEvent`s (`_unhandled_input`, `_input`, a `Control`'s `_gui_input`,
  `Input.is_action_pressed`). The AutoPlay bot and the task plays send input as Godot `InputEvent`s through
  `Input.parse_input_event`, so a game that reads input any other way takes none of it. They move the game's own mouse
  as a player's does (`get_viewport().get_mouse_position()` and a menu the game paints and hit-tests itself follow the
  cursor), and a key reaches a focused control (a text field) before the game, as a keyboard's. Every action is reachable by
  input (a hotkey or a control for what is otherwise UI-only), and the game never pauses or mutes because its window
  lost focus (your platform skill says when a phone game pauses).
- **The player's node is in the group `player`.** The task probe finds the player that way (its position, its
  camera, teleports); without the group it takes the first `CharacterBody3D` it meets, which may be an enemy.
- `Color(255, 0, 0)` is not red: `Color` takes 0..1 floats, and 255 is a blinding value (light colours, tints). Use
  0..1 floats, or `Color8` for bytes. Godot's 3D world is Y-up, in metres.
- **Combat through one method, state readable:** in a game where anything can be hurt, everything that can be hurt is
  a node whose script has `func take_damage(amount: float, source: Node) -> float`, returning the damage actually
  applied (0 when the hit did nothing: a guard, a shield, invulnerability), and decides health, death, stagger, guard,
  parry and invulnerability in `take_damage` or what it calls; everything that hurts calls `take_damage` on it, never
  changing health directly. Your own hit method may exist only as a step called from `take_damage`. Key gameplay state
  lives on node instances (a script's own variables on the node, or on an object it holds), where the task probe reads
  it, never in an autoload and never in a `static var` (constants aside): by rule, any number or bool variable whose
  name has a word `health`, `hp`, `hitpoints`, `hull`, `poise`, `armor`, `shield`, `stamina`, `mana`, `lives`, `dead`,
  `alive`, `dying`, `stun(ned)`, `stagger(ed)`, `invulnerable`, `invincible`, `guard(ing)`, `blocking`,
  `parry(ing)`, `alert`, `aggro`, `awake`, `asleep`, `dormant`, `roused` or `cooldown`, and any whole-number or enum
  variable with a word `phase` or `state`. A boss phase, an ending or any situation that takes more than a minute of
  play to reach gets a scenario start option (a scene and a command-line flag), listed in the README's QA section.
  `tools/validate-game.py` checks the method and where the state lives (rule `contract`), and the packager refuses a
  game that fails it.
  _(why: damage and state kept in private code can't be staged or read by the grader, so a task's hit, stagger,
  parry, stun or boss phase would go unchecked)_
- **Art style (user rule):** every game has one style from the library
  [docs/art-styles/](../../docs/art-styles/index.md) (100 guides: references, visual definition, Godot recipe, do /
  do not), and everything on screen follows it: models and materials, lighting, post-processing, effects, UI.
  - **Choosing.** A style named in your brief is the style. Otherwise the tool picks, at random among the styles that
    fit the game's genre:
    `python <GGF_ROOT>\godot-game-factory\tools\art-style.py pick --genre <slug> [--genre <slug>]` with the one or
    two genres from the tool's list closest to your game (`art-style.py list` prints the styles with their genres; an
    unknown genre prints the list). Styles other games on the machine already use are picked last. For a game no genre
    fits, `pick` with no genre chooses among all 100. Take what it picks: never choose by taste, and pick again only
    when the style cannot carry the brief's story or setting, saying why in the workflow row. _(why: left to choose,
    every session lands on the same few looks; the games must differ)_
  - **Adopting.**
    `python <GGF_ROOT>\godot-game-factory\tools\art-style.py use <id> <GGF_ROOT>\games\<slug>` writes the guide to
    the game's `Docs/ArtStyle.md`, the game's art bible; commit it and name the style in the design doc's art
    direction. Read the whole guide before choosing or building assets, or building a scene.
  - **Applying.** Choose or build the assets whose shapes suit the style, then bring them to it with the guide's Godot
    recipe: materials and shaders (written as `.tres` and `.gdshader`; texture edits made by a generator step),
    lighting, the `Environment` and post-processing, effects and UI. The recipe is written for the Forward+ renderer
    and says what to use on the Mobile renderer where that one lacks something. An asset left as it came next to
    restyled ones breaks the style; so does a default-looking menu. Check the guide's do / do not list against the
    framing screenshots.
- **Where art comes from (user rule):** wherever serves the game and its style best; no source is preferred and
  none is required.
  - **The asset library** (`<GGF_ROOT>\asset-library\`): the bought and downloaded packs and animation packs.
  - **Any other source:** stores, free libraries (Poly Haven, ambientCG, Kenney, Quaternius, OpenGameArt, Sketchfab's
    downloadable models) or any other site. Read the licence on the asset's own page: only **CC0**, **CC BY** or a
    store licence that covers a shipped commercial game reaches a game (the game and its dataset are used
    commercially); never non-commercial, no-derivatives, editorial or personal-use terms, an unstated licence, or
    anything taken out of another game. Download free assets yourself; for a paid one write the request (below).
    Models come in as glTF (`.glb`) where the source offers it; the engine also imports FBX.
  - **Built from scratch:** when no asset fits the game or its style, or building is quicker than adapting, make the
    model yourself, by script: Blender in background mode when it is on the machine (`blender -b -P
    Scripts/<name>.py`, exporting glTF the engine imports), or the engine's own tools from a generator step
    (`SurfaceTool`, `ArrayMesh`, saved as mesh resources). Paint its textures by script too. Commit the script with
    what it produced, and run it by its project path (replay-friendly work, below). Hold it to the same bar as a
    store asset: a clear silhouette, clean shading, UVs, materials in the game's style, collision. Props,
    architecture, terrain dressing, vehicles, machines and creatures of rigid parts are all fair to build; a skinned
    character needs a rig and clips, so prefer a rigged one from a library, restyled, unless you can rig yours.
  A game with no fitting pack is never a reason for primitives, a mismatched pack or a missing object: find it or
  build it.
- **Art (user rule):** premium, coherent, never placeholder primitives or unfinished flat colours in the final game
  (flat colour or simple shapes a style guide asks for are the style, done on purpose and finished). Characters and
  creatures are animated. Store content in a folder under `assets/` (e.g. `assets/third_party/<pack>/`), committed
  with its `.import` files, through Git LFS where binary, and never git-ignored (the repo stays private;
  godot-commit-always skill, "Store packs are committed"); copy a pack's files in, run `Scripts/godot.ps1 import`,
  and adapt them (materials, kitbash, set dressing, lighting). Record every asset that came from outside in
  `assets.manifest.json` (format `assets-manifest/v1`, docs/game-format.md: URL, licence, version, the repo paths of
  its files, changes) and credits in `Docs/ThirdPartyNotices.md`, written as a normal developer would. Need a paid
  asset? Write an "Asset requests" list (URL, price, licence, the formats it ships, what it replaces) in your design
  doc and message the coordinator.
- **Sound:** every sound effect comes through the **godot-sound** skill (read it before writing the audio direction):
  cues listed in the design doc, clips chosen by their numbers and measured with `tools/sfx.py`, CC0 or CC BY only,
  recorded in `assets.manifest.json`. Never leave a cue silent or ship a placeholder beep. Every sound the game plays
  is an imported audio file (a clip from the godot-sound skill, or a WAV a committed script made and the engine
  imported); none is made at run time: no `AudioStreamGenerator`, no script that fills a stream's samples while the
  game runs, for a game sound. `tools/validate-game.py` scans for them (rule `sound`), and the packager refuses a game
  that fails it. _(why: a sound made at run time has no file name, so the grader can't tell
  one sound from another when a task asks "each gun has its own sound")_
- **UI (user rule):** matches the game's art style (its guide's UI and typography line): kit frames, icons, display
  fonts, styled numbers. Built from `Control` nodes under one `Theme` resource. No plain or default-font text on
  screen: never the engine's built-in fallback font; import the game's own display font and set it as the theme's
  default font (and the project's, `gui/theme/custom_font`), so nothing falls back.
- **UI colours, when you are Codex (user rule):** Codex's habit, whatever the game, is a dense blue interface: navy
  or dark-blue panels, cyan or blue glowing text and outlines, the screen packed edge to edge with boxes, bars and
  small readouts. Do not build that. Take the UI's colours, materials and type from the game's art style guide and
  its world, show only what the player needs at that moment and leave the play view open. Blue is used only where the
  style guide itself asks for it. Before calling a screen or the HUD done, look at a screenshot of it: if it reads as
  a blue sci-fi dashboard laid over a game that is not one, or as a wall of panels, redo it.
  _(why: left to its defaults an agent builds the same dense blue UI for every game, whatever its art style)_
- **Story (user rule):** a strong background story told in play, never a wall of text: environmental storytelling, at
  most one short line (under ~15 words) per area, optional discoverable details, a late payoff that recolours earlier
  play.
- **Camera (user rule):** gentle; the user gets motion sick. Third person: character in the lower third, never filling
  the screen, never at hip height or jammed into the body (a `SpringArm3D` that shortens in narrow spaces, crouching).
- **Gameplay depth (user rule):** a game is never only its genre's bare loop. On top of the core loop the design doc
  names several further systems the player uses, each changing how a session goes, of the kind a player of that genre
  expects from a full game: a technique to master, things to pick up or use during play, progression or customising
  between runs, opponents or hazards that behave in different ways, choices with a trade-off. Each one works, shows in
  play with its own feedback, and is reachable by a scenario. One example, not a template: a racing game that is only
  driving laps is too thin; one with drifting, item pick-ups and car modification is the depth meant. Choose what
  fits your own game's genre and story and never copy this list. _(why: a game of one plain loop is too simple to play
  and too thin to give hard tasks)_
- **Play loops are designed with the person (user rule):** do not settle the game's loops alone. Before writing the
  design doc's systems, propose the core loop and the further systems to the person in plain words, with two or three
  real alternatives where the choice is open, ask what they would want to play, and build what you agree. Keep doing
  it while you build: after each playable round, ask them to play or watch it and say what felt flat, too easy or
  missing, and take their answer into the next round. The more of the design that comes out of this back-and-forth
  the better; a session where the person only says "continue" is a weak one. Their choices are `user.direction` rows
  (godot-commit-always skill). Ask about play, not about engine detail.
  _(why: loops an agent chooses alone come out thin, and the record then holds little of the person's judgement)_
- **Quality bar and room for hard tasks:** in the skill of your game's platform: **godot-desktop-game**, or
  **godot-mobile-game** for a game made with `new-game.ps1 -Platform mobile` (its `Platform.json` says so). Read that
  one, never both.
- **Review views stay out of the game.** To look at your work from many places in one launch, keep the list of
  stops (scenes, places, views) outside the repository (your notes, or a git-ignored folder such as `Logs/`), never
  committed: the grader takes its own pictures from places it chooses by what the build made, and a committed list of
  views invites dressing only those spots. A start option that puts the player somewhere (a scenario, a start point)
  is fine.
- **Every state reachable by a scenario.** Each scenario starts straight in the situation it shows, so a check reaches
  any moment in a short play from `play_scene` and `play_args`; no state reachable only after minutes of play or only
  from the title menu.

## Names

Never write **Superposition**, **game-factory** or **godot-game-factory** (any spelling: `game_factory`,
`gamefactory`) anywhere in the game: code, comments, class and node names, `project.godot` (`application/config/name`
is the game's own title: it is the window's title and names the folder the game saves in), `export_presets.cfg` (the
company and product names an export writes into the player), generator steps, docs, commit messages, builds, in-game
text, process arguments. Keep agent, model and provider names (**Claude / Anthropic / Opus**, **OpenAI / Codex CLI /
GPT** model ids) out of game content and commit messages too (deliverables refuse or scrub them). Recording traces
are fine: `workflow.jsonl` stays in the repo, row ids in commit messages are fine.

## Recording

- `workflow.jsonl` at the project root, one row per real operation **at the moment you act** (schema in the
  godot-commit-always skill; id prefix per game, e.g. `is-00042`), written with `Scripts/godot.ps1 row` (a step and a
  build write their own). Log failures, dead ends, debugging and fixes; never edit, reorder or backfill rows
  (`log.gap` row for anything missed), except to remove a banned name (godot-commit-always skill:
  `tools/scrub-workflow-rows.py --apply`, which appends the `log.correct` row). Banned names include the machine's
  account name (in paths): enforced in every non-script file; scripts and generator steps that already ran keep it
  (the packager scrubs them in every delivery).
- The machine hooks (the same scripts under Claude Code and Codex) record every tool call to
  `<GGF_ROOT>\.recording\<slug>\actions.jsonl`, every prompt the person types and every reply you write to
  `messages.jsonl` beside it, and every commit to `commits.jsonl`; a dataset delivers the first two in
  `History/sessions/`. Leftover changes are auto-committed as `WIP` at the end of a turn (commit properly instead).

## Replay-friendly work

The dataset's `ReplayScripts/` rebuilds your game from its history (docs/godot-replay.md; its section 3 has these
rules). A Godot game's history is
text files in git plus what the engine generates from them, so the replay goes commit by commit: it writes the files
each commit adds or changes, runs the import, and runs again, headless and in order, every generator step the
recording shows between that commit and the one before, with the step's text as it stood then. What the engine
generates (`.import` and `.uid` files, a step's outputs) is compared with what you committed. So:

- **Write content as text, with your own file tools** (Write/Edit, apply_patch): scenes and resources (`.tscn`,
  `.tres`) as much as scripts, shaders and steps. Never rewrite one with `sed -i`, `perl -i` or a Python one-off: the
  replay rebuilds each file, and a step's text at the time it ran, from your recorded writes and edits. A scene or
  resource that no recorded write and no step explains is taken from the commit and listed as a deviation.
- **Every generator step committed** under `steps/` and run only as
  `Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."`. Never run a step from a scratch or temp folder, and
  never start the engine with `--script` yourself.
- **Never edit a step that ran**: write `build_town_v2.gd` (a new file), so its rows' `source.sha256` still match the
  code that ran.
- **A step makes the same content every time**: seed every random number, use no clock and no network, and reach
  files through the project (`res://...`), never an absolute path to `games\<slug>`. It ends itself on every path,
  `quit()` when done and `quit(1)` when it failed: a step that never quits runs into the script's time limit. In a
  step's `_init()` the autoloads are not there yet (`steps/README.md` says what to do instead).
- **Commit a step with what it wrote**, as it wrote it, in the first commit after the run (then run
  `Scripts/godot.ps1 import` and commit the new sidecar files). Change a step's output later only by a new step or in
  a later commit of its own.
- **Never write a `.uid` file by hand, and never create a `.import` yourself**: the engine generates them, and the
  replay generates them again. To change how a file is imported, edit the settings in its `.import` (its `[params]`)
  with your own file tools, never a shell one-liner, run `Scripts/godot.ps1 import` and commit the file: the replay
  keeps an edit the recording shows you making.
- **`ReplayConfig.json` stays as the template made it**: a session has nothing to set in it.
- **Never amend or rebase** a commit you made: the replay follows the recorded commits.

## AutoPlay and recordings

> **AutoPlay's goal is NOT to win (user rule).** The bot only drives the game with human-like input so a recording
> shows the game running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid
> getting stuck; losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene,
> missing art, lighting, camera); then one AutoPlay run per scenario and one recording of it.

The AutoPlay drop-in is in every game as `addons/autoplay/`, unchanged, with the autoload `AutoPlay`
(`docs/autoplay-contract.md`): a new game has it from `new-game.ps1`, with the scenario list `game/scenarios.gd` (the
autoload `Scenarios`); every game gets a new version of it with one run of
`powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\autoplay\install.ps1 -Game <GGF_ROOT>\games\<slug>`
(its own commit and `autoplay.install` row; commit your own work first). Never edit the drop-in or put code of your
own in `addons/autoplay/`. What this section asks is also the release gate: the release starts with it ("Dataset",
release step 1, "Ensure AutoPlay"), and no game is released without it.

- Once the first scenario is playable end to end, implement the game's side of `docs/autoplay-contract.md`: every
  scenario starts from the command line with `-scenario <n>` (1-based, the design doc's numbers: what
  `Scripts/godot.ps1 play -Scenario <n>` and `autoplay -Scenario <n>` pass and what a task's `play_args` use) and from
  AutoPlay's `start_scenario` signal (fill in `SCENES` and `NAMES` in `game/scenarios.gd`, which handles both); all
  input is read as Godot input events ("Engine and content" above); every action is reachable by input (hotkeys for what
  is otherwise UI-only; in a mobile game by touch: godot-mobile-game skill, "AutoPlay on a mobile game"). The game
  calls `Scenarios.started()` when gameplay begins (it calls `AutoPlay.scenario_started(name)`) and
  `AutoPlay.finish_run(result, score)` when it ends, and has a bot, a node of the game's own, that acts **only**
  through the drop-in's input calls while `AutoPlay.is_running`, scaled by `AutoPlay.skill` and human-like (eased
  camera turns, reaction delays, no snapping camera, no jump spam). A desktop game's bot plays by keys, mouse and
  gamepad (`hold`, `release`, `mouse_delta`, `scroll`, `set_cursor`), a mobile game's with fingers and the back
  button only (`touch`, `touch_up`, and `hold` / `release` of `<Keyboard>/escape`). The bot counts its time from the `delta` of `_process`, never from the system clock: a recording is
  rendered offline, frame by frame, not in real time. And while `AutoPlay.is_active` nothing in the game pauses,
  opens a menu or mutes because the window lost focus: a recorded game's window is never the foreground one. The design doc lists scenarios 1..n (start state, win/lose).
- Test once by hand: `Scripts/godot.ps1 build`, then `Scripts/godot.ps1 autoplay -Scenario <n>` (the bot plays the
  built player; the run's files go to `Logs/autoplay/<time>_s<n>/`). Its summary and the run checker,
  `powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\validate-run.ps1 <that folder>`,
  must PASS (the run's files are well formed; the bot plays like a human, but its score never holds up a release).
  Commit and tag `milestone/autoplay-<n>` (scenarios 1..n work).
- **Then record it yourself.** A recording needs no screen: the pipeline builds the release player of a commit and
  runs it in Movie Maker mode, where the engine writes every frame and the mixed sound itself. So a session that has
  reached its AutoPlay milestone runs
  `powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\pipeline.ps1 <slug> -Scenarios <1,2,...>`
  with everything committed (`-Commit <sha>` for a commit other than `HEAD`): one build, then one recorded run per
  scenario, each a bundle under `<GGF_ROOT>\recordings\<slug>\<run-id>\` (`gameplay.mp4` at the game's exact size, 8
  stills, the inputs, the outcome, `validation.json`). The per-game lock and the limiter keep it apart from other
  jobs; it may wait for a slot. **One run per scenario, never to improve how the bot plays**: record again only after
  fixing a game bug the recording shows, or when the run's own `validation.json` says it is invalid.
- **Framing gate:** look at the recording's 8 stills (and, while building, at frames from
  `Scripts/godot.ps1 play -Scenario <n> -Shots 8`, which land in `Logs/godot-ps1/<tag>/`): open areas, narrow spaces,
  against walls. Check them against the camera rules above and the art style guide's do / do not list. A broken
  camera or a missing piece of art is a game bug: fix it, then one recording again. No retakes for looks alone. Copy
  the stills you keep to `Docs/screenshots/`; they are the README's screenshots too.
- Before a commit that will be recorded or packaged, run `tools/validate-game.py` on the repo: it names every tracked
  text file that holds the account name (godot-commit-always skill, "Never commit").
- Tell the coordinator (or the person, in a solo session): the commit sha, the tag, the scenarios recorded, the
  `validate-run.ps1` result, the bundle folders and the screenshot paths.

## Priorities (user decision)

**AutoPlay's goal is NOT to win** (rule in "AutoPlay and recordings" above): fix game bugs only, never the bot's
results.

What ships is what matters, in this order: the game plays; the game builds (the import without errors and the
Windows release player; a mobile game is played and recorded as that player at the phone's size, and its APK is built
at release where the machine has the Android toolchain); the dataset holds the replay scripts and the git log. The AutoPlay bot should still play
like a human (human-like input, aim and camera), but bot work never blocks a release: one recording per scenario that
shows the game running is enough, whatever the result (win/lose/timeout is metadata). No tuning for win rates, seed
sweeps or "clean" runs, and no re-runs or re-recordings to improve how the bot plays. No retest loops: every GPU or
engine run costs the shared machine and holds up delivery, so run the minimum once and report; re-run only when the
user asks. Game-session work never blocks dataset packaging or sharing.

## Dataset (layout godot-dataset-layout/v1)

A finished game ships as: `README.md, git.log, workflow.jsonl, Brief/, History/, Tasks/, GodotProject/,
ReplayScripts/, Gameplay/<slug>_S<n>.mp4, Screenshots/, Build/, manifest.json` (docs/game-format.md). The repo's
`Dataset/` folder holds the same minus `GodotProject/`, `Build/`, `History/` and `Tasks/`; the packager produces it and
you commit it. The full dataset zip is `Dataset.zip` in the game folder, next to `Dataset/`: git-ignored (with
`.dataset/`, the packager's scratch), never committed.

The packager is `python <GGF_ROOT>/godot-game-factory/tools/package-dataset.py <slug>` (docs/godot-pipeline.md,
"Dataset packager"). It packs the release commit, not the working tree, with three products of that commit: the
pipeline's release build, the gameplay video of each scenario's first valid recording (one is enough; the result
never picks a run) and the creation replay's package. **The release**, in this order:

1. **Ensure AutoPlay** (required: no game is released without it), before the release commit is chosen. Run
   `powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\autoplay\install.ps1 -Game <GGF_ROOT>\games\<slug>`:
   it brings the drop-in up to date in a commit of its own with one `autoplay.install` row, and changes nothing when
   the game is current. Then: every scenario wired; the bot written; for each scenario the hand test,
   `Scripts/godot.ps1 autoplay -Scenario <n>` on a player built with `Scripts/godot.ps1 build`, and the run checker
   (`tools/godot-pipeline/validate-run.ps1 <that run's folder>`) saying PASS; `milestone/autoplay-<n>` tagged
   (scenarios 1..n work). Only then choose the release commit.
2. The release commit: the game content-complete, its tasks on the tasks branch, everything committed, the milestone
   tag in its history. Make no other commit until the packager has run, or the replay and the recordings no longer
   match it.
3. Record the release commit:
   `powershell -ExecutionPolicy Bypass -File <GGF_ROOT>\godot-game-factory\tools\godot-pipeline\pipeline.ps1 <slug> -Scenarios <1,2,...> -Commit <sha>`
   builds its release player and records each scenario once. Tell the coordinator the sha and the bundles.
4. `python <GGF_ROOT>/godot-game-factory/tools/godot-replay/godot_replay.py release --game <slug>`, with `HEAD` at the
   release commit, makes `ReplayScripts/` for it (docs/godot-replay.md). Its verdict, PASS or FAIL, is metadata.
5. The packager (`--dry-run` first says what it would take and what is missing; `--commit <sha>` when `HEAD` has
   moved past the release commit). It writes `Dataset/`, which you then commit, and `Dataset.zip`, or
   `Dataset.pending.zip` while the replay is missing; neither zip is ever committed. A game without a gameplay video
   is rejected at upload: without a valid recording of the release commit the packager refuses.

It scrubs every text file, then refuses the package when a banned name is left in a text file, a path or a binary
file's strings, when the release build's leak scan found anything, while the pipeline builds or records the game, or
when the dataset checks find an error: fix what it names and run it again. It never commits and never changes your
history. Nobody assembles a dataset or `Dataset.zip` by hand; before the packager's first run `Dataset/` stays as the
template made it and `validate-game.py`'s "not packaged yet" warning is expected.

**README screenshots (user rule; required before the game is called content-complete).** `Docs/screenshots/` holds
5-7 real gameplay stills (JPG, in Git LFS; from validated recordings' stills, `<GGF_ROOT>\recordings\<slug>\<run-id>\stills\`,
or frames of `Scripts/godot.ps1 play -Shots`, not from extra launches made for them; no editor views, debug overlays
or placeholder art), each from a different scenario or moment. Fewer than 5 in the README is the validator's warning (not an
error), so never invent stills to reach five. The README shows them as a hero image plus a captioned gallery (one
line per image saying what it shows). Every image the README links must be committed, with the README's own path
to it (a link to a file that was never committed shows as a broken image); `validate-game.py` refuses a README image
that isn't committed.

**Game format (docs/game-format.md).** Before calling the game content-complete,
`python <GGF_ROOT>/godot-game-factory/tools/validate-game.py <GGF_ROOT>/games/<slug>` must say VALID: required files,
`assets.manifest.json` in `assets-manifest/v1` with every listed file committed, every imported file with its
`.import` and every script with its `.uid` and no orphan sidecar, `workflow.jsonl` rows, README images, no banned
names. The dataset adds your design doc and the original brief (`Brief/`) and the full history.

**The person's taste (owner, 2026-11-19).** The person who directs the game judges how it looks and feels, alone (no
second reviewer). Their judgments are part of the dataset, so ask for each in plain words, record it as it happens, and
never answer one yourself. Each is made against the design doc's feel intent: name it when you ask.

1. **A full round before the game is complete.** An AutoPlay recording is not a playtest. Once the game builds and
   plays from start to end, and before any task is written, the person plays it: at least one full round, from the
   title screen to a win or a loss, on the build a player gets (the packaged build; for a mobile game, a phone or an
   emulator). Ask for it through the coordinator (or the person, when you work with them directly) and go on with
   other work while you wait. Until a round is recorded, the game is not complete: write no tasks and do not report it
   done.
   This gates new games and new tasks only: fixing a returned or delivered task on an existing game is never blocked
   by it (godot-write-tasks, "Fixing a task that came back").
   - **What the feedback covers.** At least the feel: controls and response (each press does something at once, and
     what the player expects), movement and camera, feedback on each event (a hit, a pickup, damage, a win or a
     loss), difficulty and pacing, how readable the HUD and text are, and what is fun or boring. Each issue is one
     point, in what the player saw, never a fix. Ask also what felt great: the moments of delight.
   - **How it is recorded.** Each issue is its own `user.direction` row with `"target": "playtest"` and, beside
     `params.direction`, `params.playtest`: `{"round": 1, "build": "packaged" | "phone" | "emulator" | "editor",
     "minutes": <minutes played>, "result": "win" | "lose" | "quit"}`. A round with nothing to fix is still one row
     ("played a full round, no issues", with the same `params.playtest`). Write only what the person reported: never
     a row from your own play, a recording or a guess.
     A moment of delight is its own row the same way, with `"delight": true` in `params.playtest` and no rank.
2. **The three that matter most.** After each round the person names, in order, the three issues they would fix
   first, each with why. Add `"rank": 1`, `2` or `3` to those rows' `params.playtest` (other issues carry no rank), and
   fix in that order.
3. **Two versions to choose from.** When a look or feel direction has more than one good answer (a camera distance, a
   jump's weight, a colour grade, a hit effect), build both as two commits (A, then B on top), show the person the
   same moment in each (screenshots or a short capture from the same spot, or both builds to play), and keep the one
   they pick (revert B when they pick A). Record the pick as a `user.direction` row (its `params.direction` says it in one sentence) with
   `"target": "choice"` and `params.choice`: `{"of": "<direction id>", "a": "<commit>", "b": "<commit>", "picked": "a" | "b", "why": "<their
   reason>"}`. Not for a bug or an ask with one right answer.
4. **A verdict on each fix.** Fix each playtest issue in its own commit with its `Direction:` line ("Working with the
   coordinator", below). Then the person plays or looks at it and says better, same or worse, with half a sentence
   why, and whether anything else got worse: a `user.direction` row (its `params.direction` says it in one
   sentence) with `"target": "verdict"` and `params.verdict`: `{"of": "<direction id>", "result": "better" | "same"
   | "worse", "why": "<their reason>", "worse_elsewhere": "<what else got worse, or empty>"}`. Same or worse is the
   issue's next round, not a done fix; something else that got worse is a new playtest issue.
5. **Keep and avoid, grown from the rounds.** Nobody can say up front what to keep: it is found by playing. So the
   design doc's "Keep and avoid" section is never written at the start. It grows from the person's own judgments:
   **keep** from moments of delight and fixes judged better, **avoid** from versions not picked and fixes judged
   worse. Each line is one sentence naming the row it came from. Update it after each round and show it to the
   person; what they change in it is a direction. Check every later change against both lists: a change that spoils
   a keep line is undone or taken to the person first.

These rounds are the game's best source of tasks (taste threads, write-tasks) and of its taste data, so a second round
after the fixes is welcome.

**Feel words and starting numbers (owner, 2026-11-19).** When the person's words describe feel, look first where the
word points:

| the person says | look first at |
|---|---|
| floaty | gravity, time to the top of a jump, how fast the fall is, air control |
| stiff, heavy | acceleration and stopping, turn rate, animation blend times |
| laggy, mushy | delay from press to visible response, input buffering, animation start-up |
| slippery | stopping distance, friction, turn-around |
| hits feel weak | hit pause, screen shake, hit sound, knockback, a flash on the target |
| camera feels off | camera lag and smoothing, distance, field of view, what it frames during the action |
| boring, too easy, unfair | spacing of threats and rewards, telegraphs before danger, how fast difficulty rises |

Starting points, only to begin from: a press shows a response within about 0.1 s; a hit pause of about 0.03 s
(light) to 0.12 s (heavy); a screen shake of 0.1 to 0.3 s that decays; time to the top of a jump of about 0.3 to
0.5 s; coyote time and input buffering of about 0.1 s. Choose by the feel intent and leave these ranges on purpose
when it asks for it: they are a vocabulary, never a target, and no task threshold comes from them (write-tasks,
"Taste threads").

**Tasks (godot-write-tasks skill).** A game is complete when its repo has `Tasks/` on the tasks branch: tasks an agent
can be given on this game, one `Tasks/<game>-<kind>-<slug>.json` each in the task format `GameTask`, at least 5 and up
to about 10 per game (at least 4 of them hard; the others may be medium, none easier),
every one a long thread of multiple edits from your real history (a bug that took several attempts, a direction that
took several rounds, a feature or look pass built over many commits), never a single fix. They live on the repo's
orphan `tasks` branch, checked out as a worktree outside the game folder (`<root>/tasks/<slug>`), committed and pushed
there, never on main: task work never enters the game's history (the commit recorder ignores that branch). Seeds point at main's
commits. Follow the godot-write-tasks skill (the branch and worktree, seeds, the brief written from context, the play
scene, deterministic probe checks, what must never reach the agent); never point the game's code or docs at `Tasks/`.
validate-game.py checks their format, and `tools/task-check.py <games>/<slug> --all` (docs/task-check.md), started
once all the tasks are written as a background process the person can leave running (godot-write-tasks section 5),
checks them on the engine: a task ships only when the task check says VALID, its no-op failing and its oracle
passing (godot-write-tasks, "The no-op and the oracle, on your own machine"). A visual check whose picture
doesn't show what is asked gets a play that shows it, never a looser check, and a task that came back is fixed from the
files as returned, only the tasks listed, with a note of what changed and why (godot-write-tasks, "When a picture
doesn't show what is asked" and "Fixing a task that came back"). Judge each task's difficulty in the
session against the bar (godot-write-tasks skill, section 6); never run a task with another coding agent
(`tools/task-try.py` is internal, never a contractor's).

## Working with the coordinator

- Report milestones, recordings ("AutoPlay and recordings" above) and blockers to the coordinator; put long findings
  in the shared notes folder.
- User playtest feedback arrives through the coordinator: fix it first, commit, report the sha.
- **Every human direction is recorded before you act on it** (from the user directly, or relayed by the coordinator):
  rewrite a user message to you as a direction (what to change and why, one or two neutral sentences: no tone,
  profanity, names or chat wording; never the raw message), or take the coordinator's relayed text as it is; append
  it at once to the repo-root `workflow.jsonl` as a `user.direction` row (`via` direct or coordinator),
  then the work, with `"direction": "<row id>"` on each row that acts on it and `Direction: <row id> (...)` in each
  commit body (godot-commit-always skill, "workflow.jsonl"). The dataset shows the human's directions and what they
  led to.
- Blocked (UAC, a purchase, an engine limit, a missing toolchain)? Write it in your design doc, message the
  coordinator once, carry on with what you can.
- Push only when the coordinator says (godot-commit-always skill).
