# __TITLE__

__DESCRIPTION__

<!-- PLACEHOLDER, replace before the game is content-complete: 5-7 real gameplay stills in Docs/screenshots/ (jpg,
     in Git LFS, from the stills of the game's validated recordings or the framing-gate screenshots), shown here as a
     hero image plus a captioned gallery, e.g.
       ![<title>](Docs/screenshots/hero.jpg)
       | ![](Docs/screenshots/<name>.jpg) | ![](Docs/screenshots/<name>.jpg) |
       |---|---|
       | <what it shows> | <what it shows> |
     Link only files that are committed, and check on github.com that every image renders. -->

## Play

- Engine: Godot __GODOT_VERSION__ (standard build, GDScript).
- Open the folder with that editor version (`project.godot`), or run the built `__PROJECT__.exe` from a release build.
- Controls: _fill in_.

## Scenarios

| # | Name | Start state | Win / lose |
|---|---|---|---|
| 1 | _fill in_ | | |

## Project layout

| Path | What |
|---|---|
| `project.godot`, `export_presets.cfg` | project settings (name, first scene, renderer, frame size, autoloads, input map) and the export presets |
| `scenes/` | the game's scenes; `Main.tscn` is the first one |
| `game/` | gameplay GDScript, with `scenarios.gd`: the scenario list (scenario n's scene and name) |
| `assets/` | art, sound and fonts, each imported file with its `.import`; a pack made by others in a folder of its own |
| `addons/autoplay/` | the AutoPlay drop-in, unchanged: scripted play by an in-game bot for the gameplay recordings |
| `steps/` | every generator script that was run to build content, kept unchanged |
| `Scripts/godot.ps1` | the game's engine runs: import, generator steps, workflow rows, player build, plays, AutoPlay runs |
| `workflow.jsonl` | one row per engine/code operation, written as it happened |
| `ReplayConfig.json` | the settings of the creation replay, which rebuilds the project from its history |
| `assets.manifest.json`, `Docs/ThirdPartyNotices.md` | third-party assets: source, licence, files used, changes |
| `Brief/` | the brief the game was made from and its design doc |
| `Dataset/` | the built dataset (git log, creation record, brief, gameplay videos, replay scripts, screenshots), written by the dataset packager |
