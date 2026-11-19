"""The task checker: a contractor checks their own tasks before handing them in (docs/task-check.md).

For one task (a GameTask JSON on a game repo's `tasks` branch, docs/schemas/game-task.schema.json) it builds the game at
the task's start (seed.commit) and at its reference (seed.reference, when the task has one), plays both with the task
probe addon, measures every probe, and says whether the task is VALID: the start fails it, the reference passes it,
and what must still work already works at the start.

Modules:
- tasks: reading tasks from a repo and their checks, with the schema's defaults filled in;
- probes: the probe's queries and reducing a play's samples to one number;
- verdict: thresholds (literal, calibrated, relative to the start) and the VALID/INVALID rules;
- seeds: a commit of the game materialized outside the repo, with its Git LFS objects and the probe addon;
- godot: the import and the plays from source (through the machine's godot-heavy.ps1 when it has one);
- desk: a program run on a Windows desktop of its own;
- check: one task checked end to end; cli: `python tools/task-check.py`;
- settle: a kept run decided on the writer's answers to its own judge pictures and seen crops (`--settle`);
- trial: one task tried with the contractor's own coding agent and graded (`python tools/task-try.py`,
  docs/task-try.md).

Standard library only (Python 3.12)."""

FORMAT = "task-check/1"  # the result file's format
