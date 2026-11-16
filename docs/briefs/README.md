# Session briefs

The prompts that start each session of godot-game-factory (Claude Code or Codex), as reusable templates. The rules
every session follows are in the skills (`skills/`: godot-commit-always, godot-game-session, godot-desktop-game or
godot-mobile-game, godot-sound, godot-write-tasks); the briefs carry the task. The coordinator and its helper and game
sessions use the Claude desktop app's side sessions; a solo game runs in a terminal with either agent.

| File | For |
|---|---|
| [game-session.md](game-session.md) | template for a game-building session (placeholders) |
| [solo-game.md](solo-game.md) | one game with one plain `claude` or `codex` session (terminal, no desktop app, no coordinator): paste and fill |

Both start a desktop game as they are; each ends with "A mobile game", the three changes that start an Android phone
game instead.

## Spawning a game session

1. Write the game's fill-in: title, project name, pitch, brief, scenarios, story, art packs, known facts, and its
   platform (desktop, or mobile with its orientation, chosen with the person).
2. Copy the `text` block of `game-session.md`, replace every `{{PLACEHOLDER}}` (the fill-in's sections go in as
   they are), set `{{MODE}}` to `NEW` or `CONTINUE`; for a mobile game make the three changes of its "A mobile game"
   section.
3. Start the session from the coordinator with a fresh context and the title `{{GAME_TITLE}}`.
