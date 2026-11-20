---
name: godot-commit-always
description: 'Commit discipline for every godot-game-factory session (game builders, helpers, coordinator). Use whenever you change files in a Godot game repo or in godot-game-factory, before ending any turn, and when deciding what may be committed or pushed. Covers commit cadence, messages, workflow.jsonl rows, .import and .uid files, LFS, what never to commit, push policy and the WIP auto-commit hook.'
---

# Commit always (Godot)

The git history is the product: a game's `git.log` and `workflow.jsonl` are the creation record the dataset is built
from, and uncommitted work is invisible to the coordinator, the recording pipeline, the creation replay and the
packager (they all build from commits).
The user's standing rule: **every session commits its work continuously.**

## When

- After every meaningful step: a system parses and runs, a scene or resource is written and loads, a generator step
  ran and changed content, an asset set is imported, a bug is fixed and verified, a doc section is written, a tool
  change passes its test. At least every ~15 minutes of active work.
- Before anything risky (a mass rename or move of files, a renderer or project-settings change, `git lfs migrate`, a
  long build).
- **Never end a turn with uncommitted work of yours.** Last step of every turn: `git status`, commit what is yours,
  then report the sha.

## Which repo, which files

- **Game session:** your game repo (`%GGF_ROOT%\games\<slug>`): `git add -A` is fine there, it is yours alone. A game
  session changes nothing in godot-game-factory.
- **Helper / coordinator:** godot-game-factory is one checkout shared by several sessions. Stage explicit paths only
  (`git add <paths>`, `git commit -- <paths>`), never `git add -A` / `git commit -a`, never commit another session's
  changes. If someone else has uncommitted edits in a file you must change, commit only your change (write your
  version of the blob into the index with `git hash-object -w` + `git update-index --cacheinfo`, or ask them first).

## Message

- Subject: what changed, imperative, specific (`Add frost tower slow stacking and its tuning resource`), under ~72
  chars.
- Body: why, how it was verified (import/play/build result), anything left open.
- Game repos: end with the workflow rows the commit covers: `workflow: td-00412..td-00431`. A commit that acts on a
  human direction also names it: `Direction: td-00398 (<the direction in a few words>)`.
- Game repos: no AI attribution trailers or footers (`Co-Authored-By: <agent> ...`, `Generated with <tool>`) and never
  the names Superposition, game-factory or godot-game-factory: commit messages ship in the dataset's `git.log`. Agent,
  model and provider names (Claude, Anthropic, Opus, OpenAI, Codex CLI, GPT model ids, Google Antigravity, Gemini model
  ids) stay out too; deliverables block or scrub them. godot-game-factory commits follow the normal attribution rules.

## workflow.jsonl (game repos)

- Rows are written **when the operation happens**, not at commit time (schema `godot-workflow/v0`: `schema, id, seq,
  time` (ISO 8601 ms + offset), `actor:"agent", op, target, params, reason` (intent at that moment),
  `reason_source:"agent_note", status` (`observed`/`failed`/`reverted`), `source {script, sha256, commit}`).
- A game's content is text you write with your file tools, so most rows are yours to write:
  `powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 row -Op <op> -Target <t> -Reason "..." [-Params <file>] [-Direction <id>] [-Status failed]`
  appends one valid row with the next id and `seq` (`-Op scene.write -Target scenes/Harbor.tscn`). `-Params` takes
  the path of a file that holds the JSON object (a git-ignored one, e.g. under `Logs/`): JSON typed inline loses its
  quotes when PowerShell passes it on. One row per
  operation (a scene written, a script added, a setting changed, an asset brought in), at the moment you do it, not
  one per commit. `Scripts/godot.ps1 step` and `build` write their own rows.
- Commit `workflow.jsonl` together with the work it describes; the row ids go in the message. Many games also log an
  `op:"vcs.commit"` row (sha, subject, files) right after committing; it rides along in the next commit.
- Never edit, delete, reorder or backfill rows. Missed something: one `op:"log.gap"`, `status:"unrecorded"` row saying
  what and when. Failed attempts get rows too.
- **One exception (user rule): banned names.** A row that contains a banned name (studio/org name, the tool repos'
  names, agent/tool/provider names, the account name or machine paths with it, e-mail addresses) is edited in place to
  remove it, with a neutral word or placeholder and nothing else in the row changed; then one correction row is
  appended (`op:"log.correct"`, `params {rows: [ids], what: "removed banned names"}`), and the commit message names the
  edited rows. `python <GGF_ROOT>/godot-game-factory/tools/scrub-workflow-rows.py <repo>` does exactly this (dry run
  first, then `--apply`; it prints the commit message line). Write new rows without such names in the first place
  (relative paths, neutral words). The account name is enforced in every non-script file (workflow.jsonl, configs,
  `ReplayConfig.json`, docs, data); scripts and generator steps that already ran keep it (never edited; the packager
  scrubs them in every delivery), new ones use `res://` and relative paths.
- Every generator step that ran stays in `steps/` unchanged (a new step in a new file instead of overwriting), so
  `source.script` + `source.sha256` point at the real code.
- **Human directions (user rule: "not direct user messages, more like user directions"; "you should rewrite that and
  save to the workflow.jsonl").** Whoever receives a user message REWRITES it as a direction: what to change and why,
  one or two neutral sentences, without tone, profanity, names or chat wording (a game session for a message to it;
  the coordinator before relaying, sending the rewritten text ready to log). The rewritten direction is SAVED at once,
  before any action, by appending it to the game repo's own `workflow.jsonl` (the file at the repo root: the live
  source the packager copies, scrubbed, into `Dataset/workflow.jsonl`; never edit `Dataset/workflow.jsonl` by hand).
  A relayed direction is appended as the coordinator worded it, with `via: "coordinator"`. The raw message is never
  stored anywhere in the repo (the machine's hooks keep every prompt as typed, and every reply, in the recording's
  `messages.jsonl`, and the dataset delivers them in `History/sessions/`). The row:
  `actor:"user"`, `op:"user.direction"`, `target` the area (`camera`, `lighting`, `art`, `ui`, `audio`, `story`,
  `design`, `bot`, `build`, `process`...), `params: {direction: "<one or two sentences: what the human directed and
  why, in neutral wording, no names, not a quote of the message>", via: "direct" | "coordinator"}`,
  `reason_source:"user_direction"`, `status:"observed"` (`Scripts/godot.ps1 row -Op user.direction` writes it as the
  user's row). Every later row that acts on it carries `"direction": "<that row id>"` (`row -Direction <id>`), and
  each commit that acts on it names it in the body (`Direction: dk-00412 (camera further back in narrow spaces)`), so
  the dataset's `git.log` links each change to its cause. One row per direction, not per message; a direction that
  changes an earlier one gets a new row saying so.

## What to commit

Everything needed to rebuild the game from the repo alone: `project.godot`, `export_presets.cfg`, `scenes/`, `game/`,
`assets/` **with every `.import` file**, every script and shader **with its `.uid` file**, `addons/`, `steps/`,
`Scripts/`, `workflow.jsonl`, `ReplayConfig.json`, `assets.manifest.json`, `Platform.json` (a mobile game), `Brief/`,
`Docs/` (ThirdPartyNotices, screenshots), `README.md`, `Dataset/` (as the packager writes it, its gameplay videos,
replay scripts and `.gitattributes` included). Nothing stays git-ignored except the engine's cache (`.godot/`), build
output and logs, and the local dataset zip with its scratch (`/Dataset.zip`, `/Dataset.pending.zip`, `/.dataset/`).

**Every imported file with its `.import`, every script with its `.uid` (Godot rule).** The engine writes a sidecar
beside each file it knows: `<file>.import` beside a texture, a model, a sound or a font (its import settings and its
`uid://` identity) and `<file>.uid` beside a `.gd` or `.gdshader` (its identity). Scenes and resources may refer to a
file by that identity. A file committed without its sidecar gets a new identity at the next import, on another
machine or in the replay, and a sidecar committed without its file is an orphan: `tools/validate-game.py` fails a repo
for either. So: run `Scripts/godot.ps1 import` after adding files and commit what it wrote with them; never write or
edit a `.uid` by hand and never invent a `uid://` string; move and rename a file together with its sidecar (`git mv`
of both) and fix every `res://` path that names it in the text files that use it; delete them together. After any
batch of new files check `git status` for a file without its sidecar or a sidecar without its file. Scenes, resources,
scripts, shaders and settings are text (`.tscn`, `.tres`, `.gd`, `.gdshader`, `project.godot`, `export_presets.cfg`):
keep them text (never save a scene as `.scn` or a resource as `.res` when it could be `.tscn` or `.tres`), so every
change is a diff the history shows.

**Store packs are committed, the repo stays private (user rule).** Every store pack or other bought or downloaded
pack the game uses is committed (a folder under `assets/`, e.g. `assets/third_party/<pack>/`, with its `.import`
files, its binaries through Git LFS) and listed in `assets.manifest.json` (one format for every game:
`assets-manifest/v1`, docs/game-format.md): never git-ignore store content (no `.gitignore` entry, no "download it
yourself" step), so a clone builds the game. The licences allow that only in a private repo: game repos are never made
public, forked to a public place or shared outside the org, and store files are never uploaded anywhere else.

**Binaries go through Git LFS.** `.gitattributes` from `templates/godot-game` covers every binary type (textures,
models, audio, video, fonts, the engine's binary resources `.res`, `.scn`, `.mesh`...); the text types (`.tscn`,
`.tres`, `.gd`, `.gdshader`, `.import`, `.uid`, `project.godot`, `.cfg`) stay plain git text. Before the first commit
of a new binary type, add its pattern; check with `git check-attr filter -- <file>` (must say `lfs`). A binary
committed outside LFS means `git lfs migrate` later, which rewrites history and changes every sha that recordings and
briefs refer to. A large resource a generator step saves in binary (a baked mesh, a navigation mesh, lightmap data)
gets its LFS pattern before its first commit.

## Never commit

- The engine's cache and build output: `.godot/`, `Build/`, `Logs/`, `android/` (the Gradle build template the Android
  export installs), `*.translation`; the template's `.gitignore` has them.
- Anything under `%GGF_ROOT%\.recording\` (hook-owned; never edit it either), `recordings\`, `builds\`, `deliverables\`.
- A game's tasks on main: `Tasks/` lives on the repo's orphan `tasks` branch, committed and pushed from its own
  worktree outside the game folder (godot-write-tasks skill); task work never enters the game's history.
- Secrets: tokens, cookies, signed download URLs, `.env` files, keystores (`*.keystore`, `*.jks`) and their
  passwords, store or account credentials, credentials of any kind.
- In godot-game-factory: packages, project snapshots, package zips, `git.log` exports with asset diffs, the engine,
  ffmpeg or other downloaded binaries (the `machine/get-*.ps1` scripts fetch them), recordings.
- In game repos: the names Superposition / game-factory / godot-game-factory anywhere (code, comments,
  `project.godot`, `export_presets.cfg`, generator steps, docs). The user's absolute profile path where avoidable
  (`tools/validate-game.py` names every tracked text file that holds the account name: run it before a commit that
  will be recorded or packaged; the coordinator asks for it).

## The replay rebuilds from your commits (game repos)

The creation replay rebuilds the game commit by commit from its first one: it writes each commit's files, runs the
import, and runs again every generator step the recording shows between two commits (docs/godot-replay.md). So commit
a step together with what it wrote, in the first commit after its run, and never amend or rebase a commit you already
made: the recorded commits are the ones the replay follows (the godot-game-session skill, "Replay-friendly work").

## Push policy

- **Never push unless the coordinator says so** (or the user, in your own session). The coordinator reviews first
  (untracked files, ignored dirs, non-LFS blobs, LFS coverage, missing `.import` and `.uid` files), then tells you to
  push.
- When told: `git push origin main --follow-tags`, then verify `git ls-remote origin main` matches `git rev-parse HEAD`
  and `git lfs push origin main --dry-run` lists nothing left.
- Game repos live at `<org>/godot-game-<slug>` (private; `<org>` = `github_org` in the machine config). Never
  force-push. Never rewrite pushed history except a coordinator-ordered scrub or LFS migration.

## The WIP auto-commit

The Stop hook (`record-godot-action.ps1 -Stop`, wired into Claude Code, Codex and Antigravity alike) commits leftover
changes in a game repo as `WIP` at the end of every turn, except while conflicts are unresolved or HEAD is detached (a
merge, a rebase, a bisect under way): finish those and commit yourself.
It is a safety net so nothing is lost, not a way of working: a `WIP` commit carries no reason and no row ids, and it
reads as sloppy in the dataset's `git.log`. If one of yours appears, say in your next commit's body what the WIP
commit contained. Don't squash or amend it away; the history is the record. The hook does not cover
godot-game-factory: helpers and the coordinator must commit there themselves.
