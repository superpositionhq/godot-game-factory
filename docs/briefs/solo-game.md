# Solo game brief (plain Claude Code or Codex)

For one person building one game with one coding-agent session in a terminal, Claude Code (`claude`) or OpenAI Codex
CLI (`codex`): no desktop app, no coordinator, no other sessions. The rules are the same as for a coordinated game
session (the `godot-game-session` and `godot-commit-always` skills, installed by `machine/setup.ps1`); what the
coordinator would do (decide pushes, relay directions, hand out store packs) is done by you, the person at the
keyboard. Recordings need no screen, so the session runs the recording pipeline itself once its AutoPlay test passes
([../godot-pipeline.md](../godot-pipeline.md)); you can go on using the PC meanwhile. With the desktop app and several
games at once, start each game session from [game-session.md](game-session.md) instead.

Start: open a terminal in the machine root (`cd <root>`, e.g. `C:\Users\<name>\GodotWork`; not another
factory's root, whose `CLAUDE.md` and `AGENTS.md` load its own rules) and run one of

- `claude` (its `<root>\CLAUDE.md` loads the godot-game-factory rules), or
- `codex -s danger-full-access` (its `<root>\AGENTS.md` names the rules; the full-access sandbox is needed because
  the job limiter uses machine-wide mutexes and git / gh need the network; `codex` asks once to trust the folder),

then paste the `text` block below with the placeholders filled. Stay in this one session for the whole game where you
can (resume it with `claude --continue` or `codex resume --last`): the recording (every tool call, every prompt you
type and every reply the model writes) follows the session, and a new session is filed under the game only from its
first tool call that names the game folder. For a game that has a fill-in in
`games/` next to this file, take the pitch, scenarios and story from it; for a new game, write them in a few lines
each.

| Placeholder | From |
|---|---|
| `{{GAME_TITLE}}`, `{{SLUG}}`, `{{PROJECT}}` | the title, a lowercase slug (`island-survival`) and a PascalCase project name (`IslandSurvival`) |
| `{{PITCH}}`, `{{SCENARIOS}}`, `{{STORY}}`, `{{ART_STYLE}}`, `{{ART_PACKS}}` | `games/<slug>.md`, or your own few lines |
| `{{GGF_ROOT}}` | the machine root (e.g. `C:\Users\<name>\GodotWork`; `machine/lib/ggf-root.ps1`) |
| `{{ORG}}` | the GitHub organisation (or user) owning the repos: `github_org` in the machine config |
| `{{MODE}}` | `NEW` (no repo yet) or `CONTINUE` (repo already cloned into `{{GGF_ROOT}}\games\{{SLUG}}`) |

```text
You are the only session on this machine: build "{{GAME_TITLE}}" in Godot 4.7 (GDScript) and record how it is built.
There is no coordinator and there are no other sessions: never start, spawn or message other sessions. Whatever the
skills say to send to "the coordinator" (recording reports, push requests, asset requests, blockers), tell me
here and wait for my answer.

Read first: {{GGF_ROOT}}\godot-game-factory\AGENTS.md, README.md, docs/autoplay-contract.md, docs/godot-pipeline.md,
and the godot-game-session, godot-desktop-game, godot-commit-always and godot-sound skills
({{GGF_ROOT}}\godot-game-factory\skills\<name>\SKILL.md; installed for your agent too). They hold the rules; in short:
- use only the godot-game-factory skills (godot-commit-always, godot-game-session, godot-desktop-game, godot-sound,
  godot-write-tasks): never install, enable or invoke any other skill (personal, project, plugin, marketplace, built
  into the agent, or another factory's), even when one is offered;
- every engine, build or GPU job through {{GGF_ROOT}}\tools\godot-heavy.ps1 (the game's Scripts\godot.ps1 does it for
  you); scenes, resources and scripts are text files you write with your own file tools and commit; what only the
  engine can make comes from a committed generator script (steps/, run with Scripts\godot.ps1 step);
- premium art in one art style, from store packs, any licensed source or built from scratch (store packs: a folder
  under assets/, committed with their .import files, binaries through Git LFS, never git-ignored; the repo stays
  private), every sound through the godot-sound skill, styled UI with no plain text, story embedded in play, gentle
  camera; never the names of the toolkit or its owners inside the game;
- one workflow.jsonl row per operation at the moment you act (Scripts\godot.ps1 row; rows are never edited, except to
  remove a banned name with tools/scrub-workflow-rows.py --apply); commit after every meaningful step, every imported
  file with its .import and every script with its .uid, never end a turn with uncommitted work; LFS for every binary;
- my messages that change the game are directions: rewrite each as one or two neutral sentences and append it to
  workflow.jsonl as a user.direction row (via "direct") before acting on it (godot-commit-always skill);
- AutoPlay's goal is NOT to win: the bot only drives the game with human-like input; fix game bugs, never tune the
  bot; one AutoPlay run and one recording per scenario; the AutoPlay drop-in in addons/autoplay/ stays unchanged;
- the creation replay rebuilds the game from your commits and your recorded step runs: never amend or rebase, never
  edit a step that ran (godot-game-session skill, "Replay-friendly work");
- push only when I say.

Game: {{GAME_TITLE}} ({{SLUG}} -> {{GGF_ROOT}}\games\{{SLUG}}, project {{PROJECT}}, private GitHub repo
{{ORG}}/godot-game-{{SLUG}} for staff only: as a contractor I have no GitHub repo for the game and no access to
{{ORG}}, which is expected, so never ask me to sign in to GitHub or to request access). The brief as given, and the
design doc, story bible and status: Brief\brief.md and Brief\design.md in the game repo (create them if missing).
Mode {{MODE}}: NEW = your first tool call creates the project with
  powershell -ExecutionPolicy Bypass -File {{GGF_ROOT}}\godot-game-factory\templates\new-game.ps1 -Slug {{SLUG}} -Path {{GGF_ROOT}}\games\{{SLUG}} -Project {{PROJECT}} -Title "<title>" -Description "<one line>"
(the absolute path written out: the recording hooks match the command text; typed in Git Bash, put each Windows path
in single quotes: bash drops unquoted backslashes).
CONTINUE = your first tool call is `git -C {{GGF_ROOT}}\games\{{SLUG}} log --oneline -20`; read the design doc's
status and the last workflow.jsonl rows and carry on.

Pitch:
{{PITCH}}

Scenarios (AutoPlay contract; numbered start state + win/lose):
{{SCENARIOS}}

Story:
{{STORY}}

Art style (docs/art-styles; a style's id and name, or "pick": the tool chooses, godot-game-session skill, "Art style"):
{{ART_STYLE}}

Art to start from (store packs in {{GGF_ROOT}}\asset-library\; any licensed source or built from scratch otherwise; ask me for paid packs):
{{ART_PACKS}}

Steps:
1) create the project (new-game.ps1); 2) Brief\brief.md and Brief\design.md (design doc + story bible); 3) core loop
first, written as text and checked through Scripts\godot.ps1 import and play, committing each working step;
4) AutoPlay once scenario 1 plays end to end (docs/autoplay-contract.md): one hand test with Scripts\godot.ps1 build,
Scripts\godot.ps1 autoplay and tools/godot-pipeline/validate-run.ps1, tag milestone/autoplay-<n>, then one recording
per scenario with tools\godot-pipeline\pipeline.ps1 {{SLUG}} -Scenarios <1,2,...>, the framing check on its stills
(godot-game-session skill), then tell me; 5) content, art, UI, sound (godot-sound skill),
the Windows release player build; 6) playtest checklist, status section in the design doc, and
before calling it content-complete: 5-7 real gameplay stills in Docs/screenshots/ (JPG, LFS; from the recordings'
stills or frames of Scripts\godot.ps1 play -Shots, never invented ones) shown in the README as a hero image plus a
captioned gallery, checked on github.com after I say push; Tasks/ with at least 5 and up to about 10 tasks on the
game, at least 4 of them hard (the others may be medium, none easier), every one a long thread of
multiple edits, on the tasks branch, never on main (godot-write-tasks skill); tools/validate-game.py VALID; 7) the
release, when I say (godot-game-session skill, "Dataset"): first ensure AutoPlay, a required step
(tools/godot-pipeline/autoplay/install.ps1, every scenario wired, the bot, a passing hand test per scenario, the
milestone/autoplay-<n> tag), and only then choose the release commit and tell me its sha (no other commit until it is
packaged); record it (pipeline.ps1 {{SLUG}} -Scenarios <1,2,...> -Commit <sha>), run godot_replay.py release with
HEAD at that commit, then package-dataset.py; commit the Dataset/ it writes. Report each milestone here with the
commit sha.
```

## A mobile game

The text above starts a desktop game as it is. For a mobile game (an Android phone game, landscape or portrait,
chosen with the person before the session starts), change three things in the filled text before sending it:

1. Add ` -Platform mobile -Orientation landscape` (or `portrait`) to the `new-game.ps1` line.
2. Replace `the Windows release player build` with `the Android release APK (Scripts\godot.ps1 build -Android)`.
3. Replace `godot-desktop-game` with `godot-mobile-game` in the two places that name the skills, and add this line
   after the "Read first" paragraph:
   `This is a mobile game (Android phone, <orientation>, touch only): follow the godot-mobile-game skill with godot-game-session, in place of godot-desktop-game.`
