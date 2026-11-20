# Game session brief (template)

The brief the coordinator sends to start one game-building session. Fill the `{{PLACEHOLDERS}}` from the game's
fill-in file in `games/` next to this file (`docs/briefs/games/<slug>.md`; write a new fill-in for a new game first),
then start the session with a fresh context and title `{{GAME_TITLE}}`. The rules themselves live in the
`godot-game-session` and `godot-commit-always` skills, so the brief stays short and the rules stay in one place.

| Placeholder | From |
|---|---|
| `{{GAME_TITLE}}`, `{{SLUG}}`, `{{PROJECT}}`, `{{GENRE_LINE}}`, `{{PITCH}}`, `{{BRIEF}}`, `{{SCENARIOS}}`, `{{STORY}}`, `{{ART_STYLE}}`, `{{ART_PACKS}}`, `{{GAME_NOTES}}` | `games/<slug>.md` |
| `{{GGF_ROOT}}` | the machine root (`machine/lib/ggf-root.ps1`; e.g. `C:\Users\<name>\GodotWork`) |
| `{{ORG}}` | the GitHub organisation (or user) owning the repos: `github_org` in the machine config |
| `{{MACHINE}}` | one line: `<CPU, RAM, GPU + driver, display>` of this machine |
| `{{SIBLINGS}}` | the other game slugs running now |
| `{{COORDINATOR_ID}}`, `{{ASSET_SCOUT_ID}}`, `{{NOTES_DIR}}` | session ids and the shared notes folder |
| `{{MODE}}` | `NEW` (no repo yet) or `CONTINUE` (repo cloned from `{{ORG}}/godot-game-{{SLUG}}`) |

```text
Background (from the session that started this one):
godot-game-factory ({{GGF_ROOT}}\godot-game-factory: read CLAUDE.md, README.md, AGENTS.md,
docs/autoplay-contract.md, docs/godot-pipeline.md) produces game-CREATION data: how a game is
built step by step, recorded as it happens (every tool call, every prompt a person types to you and every reply you
write), packaged as a dataset (layout godot-dataset-layout/v1: Dataset/ committed in the game repo, the full
Dataset.zip git-ignored next to it). Other sessions are building Godot games right now in
{{GGF_ROOT}}\games\<slug> ({{SIBLINGS}}); read their Brief/design.md for conventions and solved
problems. The asset-scout session ({{ASSET_SCOUT_ID}}) keeps the asset library in {{GGF_ROOT}}\asset-library\ and hands
each game its packs. Everything shares one Windows PC ({{MACHINE}}). I am the coordinator ({{COORDINATOR_ID}}): I own
the GPU slots, review your commits and tell you when to push.

Rules: follow the godot-game-session, godot-desktop-game, godot-commit-always and godot-sound skills (installed in
~\.claude\skills\, ~\.agents\skills\ or ~\.gemini\config\skills\, source godot-game-factory/skills/), and no other
skill: never install, enable or invoke a personal, project, plugin, marketplace or agent built-in skill, nor another factory's skills. In short:
every heavy or GPU job through {{GGF_ROOT}}\tools\godot-heavy.ps1 (the game's Scripts\godot.ps1 does it for you);
scenes, resources and scripts are text files you write with your own file tools and commit (.tscn, .tres, .gd), and
what only the engine can make comes from a committed generator script (steps/, run with Scripts\godot.ps1 step);
premium art in one art style, from the asset library, any licensed source or built from scratch, every sound through
the godot-sound skill, styled UI with no plain text, story embedded in play, gentle camera; never the names
Superposition, game-factory or godot-game-factory anywhere in the game; one workflow.jsonl row per operation at the
moment you act (Scripts\godot.ps1 row; rows never edited, except to remove a banned name with
tools/scrub-workflow-rows.py --apply); commit after every meaningful step, every imported file with its .import and
every script with its .uid, and never end a turn with uncommitted work; LFS for every binary; commit the store packs
you use (a folder under assets/, binaries through LFS, never git-ignored; the repo stays private, never public or
shared outside the org); push only when I say. Your game's full dataset is
{{GGF_ROOT}}\games\{{SLUG}}\Dataset.zip, made by the packager (python tools/package-dataset.py {{SLUG}} in
godot-game-factory) from the release commit, its pipeline build and recordings and its creation replay
(godot-game-session skill, "Dataset"); until its first run Dataset/ stays as the template made it: keep
/Dataset.zip, /Dataset.pending.zip and /.dataset/ in your .gitignore and never commit them; Dataset/ you commit.
The creation replay rebuilds your game from its commits and your recorded step runs (godot-game-session skill,
"Replay-friendly work"): never amend or rebase, never edit a step that ran.
Blockers: write them in your design doc, message me once, carry on.
AUTOPLAY'S GOAL IS NOT TO WIN. The bot only drives the game with human-like input so a recording shows the game
running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid getting stuck;
losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene, missing art,
lighting, camera); then one AutoPlay run per scenario and one recording of it.
Human directions (from the user, or relayed by me) are recorded before you act on them: rewrite a user message to you
as a direction (what and why, one or two neutral sentences, no names or chat wording; never the raw message), or take
my relayed text as it is, and append it at once to your repo-root workflow.jsonl as a user.direction row; then
"direction": "<row id>" on the rows and "Direction: <row id>" in the commits that act on it (godot-commit-always skill).

Task:
Build "{{GAME_TITLE}}", {{GENRE_LINE}}, in Godot 4.7 (GDScript), recording its creation as you go.

Slug and location: {{SLUG}} -> {{GGF_ROOT}}\games\{{SLUG}} (project {{PROJECT}}, its own git repo, private
GitHub repo {{ORG}}/godot-game-{{SLUG}}). The brief as given, and the design doc, story bible and status:
Brief\brief.md and Brief\design.md in the game repo.
Mode {{MODE}}: NEW = your first tool call creates the project with
  powershell -ExecutionPolicy Bypass -File {{GGF_ROOT}}\godot-game-factory\templates\new-game.ps1 -Slug {{SLUG}} -Path {{GGF_ROOT}}\games\{{SLUG}} -Project {{PROJECT}} -Title "<title>" -Description "<one line>"
(the absolute path written out, as here: the recording hooks match the command text; new-game.ps1 refuses any other
-Path; typed in Git Bash, put each Windows path in single quotes: bash drops unquoted backslashes)
CONTINUE = the repo is already cloned there: your first tool call is `git -C {{GGF_ROOT}}\games\{{SLUG}} log --oneline -20`;
read the design doc's status section and the last workflow.jsonl rows, then carry on from where it stopped (new rows
continue the existing id sequence).

Pitch:
{{PITCH}}

Brief:
{{BRIEF}}

What ships is what matters, in this order: the game plays; the game builds (the import without errors and the Windows
release player); the dataset holds the replay scripts and the git log. The AutoPlay bot should still play like a human
(human-like input, aim and camera), but bot work never blocks a release: one recording per scenario that shows the
game running is enough, whatever the result (win/lose/timeout is metadata). No tuning for win rates, seed sweeps or
"clean" runs, and no re-runs or re-recordings to improve how the bot plays. No retest loops: every GPU or engine run
costs the shared machine and holds up delivery, so run the minimum once and report; re-run only when the user asks.
Game-session work never blocks dataset packaging or sharing.

Scenarios (AutoPlay contract; numbered start state + win/lose):
{{SCENARIOS}}

Story:
{{STORY}}

Art style (docs/art-styles; a style's id and name, or "pick": the tool chooses, godot-game-session skill, "Art style"):
{{ART_STYLE}}

Art to start from (paths under {{GGF_ROOT}}\asset-library\):
{{ART_PACKS}}

Known facts about this game:
{{GAME_NOTES}}

Steps:
1) Create the project and repo (new-game.ps1), workflow.jsonl from the very first operation.
2) Brief\brief.md (the brief above, as given) and Brief\design.md: design doc + story bible (systems, scripts and
   classes, tuning resources, scene plan, scenarios, AI, art/audio/UI direction with the list of sound cues,
   acceptance checklist).
3) Build the core loop first: write scenes, resources and scripts as text, check them with Scripts\godot.ps1 import
   (scripts parse) and a short Scripts\godot.ps1 play as you go; commit each working step.
4) AutoPlay once scenario 1 is playable end to end (docs/autoplay-contract.md: the drop-in in addons/autoplay/ stays
   unchanged; every scenario starts with -scenario <n> and from AutoPlay's start_scenario signal
   (game/scenarios.gd); the bot acts only through the drop-in's input calls, Skill-scaled, human-like camera); one
   hand test with Scripts\godot.ps1 build, Scripts\godot.ps1 autoplay and validate-run.ps1 (well-formed files; the
   bot plays like a human, but its score never holds up a release); tag milestone/autoplay-<n>; then record it
   yourself, one run per scenario: tools\godot-pipeline\pipeline.ps1 {{SLUG}} -Scenarios <1,2,...> (it needs no
   screen), check the framing on the recording's stills (godot-game-session skill, "AutoPlay and recordings") and
   message me (commit sha, tag, scenarios recorded, the validate-run result, the bundle folders, screenshot paths).
   The bot does NOT need to win, finish, resupply or avoid getting stuck: never tune or re-test it for results; fix
   only game bugs, then one run per scenario.
5) Expand content, art, UI and story to the quality bar (menus, settings, pause, save/load where it fits, HUD, sound
   through the godot-sound skill, the Windows release player build).
6) Finish with a playtest checklist pass and a status section in the design doc (what works, what's left, built vs
   store assets, stats: workflow rows, commits, hours). Before calling the game content-complete: Docs/screenshots/
   holds 5-7 real gameplay stills (JPG, Git LFS; from the recordings' stills or frames of Scripts\godot.ps1 play
   -Shots, never invented ones), the README shows them as a hero image plus a captioned gallery, and
   after the push every image renders on the github.com repo page (godot-game-session skill, "README screenshots");
   and Tasks/ on the repo's orphan tasks branch (its own worktree, never on main) holds the game's tasks, up to about
   10, every one a long thread of multiple edits (godot-write-tasks skill); and tools/validate-game.py on your repo
   says VALID (docs/game-format.md). Report back with a short summary and the commit sha when done or blocked.
7) The release, when I say (godot-game-session skill, "Dataset"): first ensure AutoPlay, a required step
   (tools/godot-pipeline/autoplay/install.ps1, every scenario wired, the bot, a passing hand test per scenario, the
   milestone/autoplay-<n> tag), and only then choose the release commit and tell me its sha (no other commit until it
   is packaged); record it (pipeline.ps1 {{SLUG}} -Scenarios <1,2,...> -Commit <sha>), run godot_replay.py release
   with HEAD at that commit, then package-dataset.py; commit the Dataset/ it writes and report whether it made
   Dataset.zip or Dataset.pending.zip (and what it lists as missing).

Shared notes folder for this group of sessions (outside the repo; read siblings' notes there, leave hand-over notes
or large findings there instead of pasting them into messages): {{NOTES_DIR}}
```

## A mobile game

The text above starts a desktop game as it is. For a mobile game (an Android phone game, landscape or portrait,
chosen with the person before the session starts), change three things in the filled text before sending it:

1. Add ` -Platform mobile -Orientation landscape` (or `portrait`) to the `new-game.ps1` line.
2. Replace `the Windows release player build` with `the Windows release player build at the phone's size (the APK is built at release)`.
3. Add this line after the paragraph that names the skills to follow:
   `This is a mobile game (Android phone, <orientation>, touch only): follow the godot-mobile-game skill with godot-game-session, in place of godot-desktop-game.`
