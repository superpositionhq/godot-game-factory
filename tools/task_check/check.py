"""One task checked end to end (docs/task-check.md).

1. The task is read and validated (tasks.problems); its start (seed.commit) and reference (seed.reference) are
   materialized into a scratch folder outside the repo, each with the task probe addon (seeds.py).
2. The start is built first (the import, then every script loaded: godot.Project.build). A start that doesn't build
   makes the task INVALID, unless a build check says it doesn't (`fails_at_start`): then not building is the start
   failing the task, and the start is never played. A build of either side that stops with no word about the game
   (twice with no script error, or at its time limit) is the run's ERROR, never a verdict (Side.build).
3. With a reference, the reference is checked as a solution would be: its checks in the task's order (a check whose
   `needs` failed isn't run and fails), build, boot, log_absent, file_exists, package and every probe against its
   threshold. A calibrated or start-relative threshold measures the start (its plays, played once) and, calibrated, the
   reference. A probe whose select (objects, widgets, components, ui) reads nothing on the reference, or whose task
   play's input didn't land there, is a task error (TASK_ERROR), as the Lab's grade makes it.
4. The start is checked on its probes (and on a `fails_at_start` build check).
5. verdict.verdict decides VALID or INVALID from the two sides' check rows. A task with no seed.reference is never
   VALID: its oracle side can't be played, so nothing shows its checks can be passed (NO_REFERENCE). A required judge
   with no play of its own (no `plays`, no `route`) is never VALID either: it is shown only the idle look and the
   drive, which never reach what its rubric asks (judged).

A run of several tasks shares one scratch copy per commit (Builds): a commit that is one task's start and another's
reference, or two tasks' start, is materialized and built once and kept until the last task that needs it is done.
The copy is the commit exactly as committed either way, so sharing it changes no result.

The plays a probe names: "look", the idle play (20 s, no input, 6 screenshots); "drive", the scripted drive (22 s:
<Keyboard>/w 1-6 s, /d 6-8 s, /w 8-13 s with a jump (/space) at 9 s, /a 13-15 s, /w 15-21 s; 8 screenshots; a mobile game's drive is
the same route by touch, MOBILE_DRIVE); a task play (its own seconds, inputs, scene, args and sampling; 2 screenshots,
or the most a judge check showing it asks). Each is played once per side, with the probe's queries for every probe it
serves, on the task's play_scene and play_args unless a task play names its own, with the task's `player` as the
player. A task play that names `after` is played once the plays it names have run on that side, a failed one too,
and starts on the saved data they left; every other play starts clean (Side._task_play). A boot check plays
boot_<seconds>s (2 screenshots, no queries). Every task's boot is a 60 s idle play and
"look" is the first 20 s of the same idle game, so when no look probe reads the log, a side that boots (the reference;
a start is never booted) plays one 60 s idle play with look's queries for both (Side.idle): the boot check reads it
whole, and look reads its first 20 s only (first_seconds), one game launch instead of two. A `package` check makes the
game's release export (godot.Project.package: its own "Windows Desktop" preset, the probe in it) and plays the exported
player for PACKAGED_SECONDS (1 screenshot) through the probe: it passes when the export left its player and the player
ran to its time with no crash (Side.package); a machine without the release export template fails it, saying so. A
`judge` check's plays are played on both sides (with its `route`, read from the reference's copy and played on each, as
the Lab plays it) and the screenshots its judge would see are saved under <name>/judge-shots/<check>/ (judges.py) for
the task's writer to score blind (`judge_shots`); a required judge holds the verdict until both sides are scored and
agree (judged). A `seen` probe (text the Lab's visual model reads from a named shot) is read by the task's writer
instead: its crops are saved under <name>/seen-shots/<check>/ (seen.py), and once the writer has answered, their answer
is the probe's measure on each side; until then the probe measures nothing, and a task with a required one
isn't VALID."""

import json
import math
import re
import time
from pathlib import Path

from . import FORMAT, godot, judges, probes, seeds, seen, tasks, verdict

DRIVE = [{"t": 1.0, "key": "<Keyboard>/w", "press": True}, {"t": 6.0, "key": "<Keyboard>/w", "press": False},
         {"t": 6.0, "key": "<Keyboard>/d", "press": True}, {"t": 8.0, "key": "<Keyboard>/d", "press": False},
         {"t": 8.0, "key": "<Keyboard>/w", "press": True}, {"t": 9.0, "key": "<Keyboard>/space", "press": True},
         {"t": 9.3, "key": "<Keyboard>/space", "press": False}, {"t": 13.0, "key": "<Keyboard>/w", "press": False},
         {"t": 13.0, "key": "<Keyboard>/a", "press": True}, {"t": 15.0, "key": "<Keyboard>/a", "press": False},
         {"t": 15.0, "key": "<Keyboard>/w", "press": True}, {"t": 21.0, "key": "<Keyboard>/w", "press": False}]
PLAYS = {"look": (20, 6, None), "drive": (22, 8, DRIVE)}  # seconds, screenshots, inputs
# A mobile game's drive (docs/task-probes.md): the same route by touch, a left thumb pushing where a virtual stick
# usually is (down at its middle, over to a side, held there) and a right thumb's tap for the jump.
STICK = [0.15, 0.75]


def _push(t, to, held):
    return {"t": t, "drag": [STICK, to], "over": 0.2, "hold": held - 0.3, "finger": 0}


MOBILE_DRIVE = [_push(1.0, [0.15, 0.6], 5.0), _push(6.0, [0.25, 0.75], 2.0), _push(8.0, [0.15, 0.6], 5.0),
                {"t": 9.0, "tap": [0.85, 0.75], "finger": 1}, _push(13.0, [0.05, 0.75], 2.0),
                _push(15.0, [0.15, 0.6], 6.0)]
JUDGES = ("judge", "code_judge")
NOT_JUDGED = "not asked: a model's check, answered by the task's writer (judge-shots)"
NO_OWN_PLAY = judges.NO_OWN_PLAY
NO_REFERENCE = verdict.NO_REFERENCE
PACKAGED_SECONDS = 20  # a package check's play of the exported player
TASK_ERROR = verdict.TASK_ERROR
SELECTING = ("objects", "widgets", "components", "ui")  # the runtime measures that read what their select matches
ROUTE_INPUTS, ROUTE_BYTES, ROUTE_SECONDS, ROUTE_SHOTS = 400, 1024 * 1024, 120, 8  # a judge's route, as the Lab reads it
SKIP = {".godot", "Build", "Logs", "android", ".git"}  # left out of file_exists
# s: a play of `seconds` samples on to seconds + OVERRUN and stops there (the probe ends a play at `t >= seconds +
# 0.5`), so a look cut from a longer play keeps that half second too
OVERRUN = 0.5


def own_play(play, project):
    """The checker's own play `play` ("look", "drive") on `project`: (seconds, screenshots, inputs); a mobile game's
    drive is by touch."""
    seconds, shots, inputs = PLAYS[play]
    mobile = getattr(project, "mobile", None)
    return seconds, shots, MOBILE_DRIVE if play == "drive" and mobile is not None and mobile() else inputs


def fatal(log):
    return bool(re.search(godot.FATAL, log or ""))


def failed(build):
    """How a build failed, for a reason: "timed out", or its exit code and first cause (the build log is the
    evidence; a bare exit code sent every reader to it)."""
    if build.timed_out:
        return "timed out"
    cause = getattr(build, "cause", None)
    return f"exit {build.exit_code}" + (f": {cause}" if cause else "")


def first_seconds(probe, seconds):
    """`probe` (a play's probe.json) as a play of only its first `seconds` would have written it: rows and samples after
    that play's last one (at seconds + OVERRUN) dropped, its length cut to them."""
    if not isinstance(probe, dict):
        return probe
    end = seconds + OVERRUN
    cut = dict(probe)
    for name in ("track", "camera"):
        rows = probe.get(name)
        if isinstance(rows, list):
            cut[name] = [r for r in rows if not (isinstance(r, list) and r and isinstance(r[0], int | float)
                                                 and r[0] > end + 1e-6)]
    if isinstance(probe.get("measures"), dict):
        cut["measures"] = {q: [s for s in samples if not (isinstance(s, dict) and isinstance(s.get("t"), int | float)
                                                          and s["t"] > end + 1e-6)] if isinstance(samples, list)
                           else samples for q, samples in probe["measures"].items()}
    length = probe.get("seconds")
    if isinstance(length, int | float) and not isinstance(length, bool) and length >= end - 1e-6:
        cut["seconds"], cut["ended"] = float(end), "time"
    return cut


class Built:
    """A scratch project shared by every task of a run whose start or reference is its commit: built at most once,
    played as often as the tasks ask (each task's plays carry its own queries)."""

    def __init__(self, project, log=print):
        self.project, self.log = project, log
        self._build = self._package = None

    def has_built(self):
        return self._build is not None

    def build(self, timeout):
        if self._build is None:
            self._build = self.project.build(timeout)
        return self._build

    def package(self, timeout):
        """The release export, made once for every task of the run that has this copy (its player is kept)."""
        if self._package is None:
            self._package = self.project.package(timeout)
        return self._package

    def __getattr__(self, name):
        return getattr(self.project, name)


class Builds:
    """The scratch copies of one run, one per commit under `scratch`, each a Built. `get` materializes and adds the
    task probe on first use; `release` deletes a copy no later task needs; `close` deletes them all."""

    def __init__(self, repo, scratch, direct=False, log=print):
        self.repo, self.scratch, self.direct, self.log = repo, Path(scratch), direct, log
        self.copies = {}  # sha -> (Built, info) or the error that refused it

    def get(self, sha, needed=()):
        """(Built, info) for commit `sha`; raises seeds.WrongEngine for a project that isn't Godot 4.7 and
        RuntimeError when the machine has no Godot. When the disk is below the machine's floor, copies other than
        `needed` (this task's commits) are deleted first."""
        if sha in self.copies:
            self.log(f"  {sha[:12]}: reusing the copy already made in this run")
        else:
            folder = self.scratch / sha[:12]
            self._room(set(needed) | {sha})
            self.log(f"  {sha[:12]}: materializing into {folder}")
            made = seeds.materialize(self.repo, sha, folder)
            try:
                seeds.add_probe(folder)
                machine = godot.Machine.for_project(folder, self.direct)
            except (seeds.WrongEngine, RuntimeError) as exc:  # (a machine without Godot) every task on it alike
                self.copies[sha] = exc
            else:
                self.copies[sha] = (Built(godot.Project(folder, machine, sha[:12]), self.log),
                                    {"files": made["files"], "lfs_linked": made["linked"],
                                     "lfs_copied": made["copied"], "engine": str(machine.editor),
                                     "slots": "godot-heavy" if machine.heavy else "direct"})
        found = self.copies[sha]
        if isinstance(found, Exception):
            raise found
        return found

    def _room(self, needed):
        try:
            godot.ggfroot.check_free(str(self.scratch), "task check")
            return
        except SystemExit:
            for sha in [s for s in self.copies if s not in needed]:
                self.log(f"  {sha[:12]}: low on disk, deleting its copy (a later task rebuilds it)")
                self.release(sha)
        godot.ggfroot.check_free(str(self.scratch), "task check")

    def release(self, sha):
        if self.copies.pop(sha, None) is not None:
            self._remove(self.scratch / sha[:12])

    def close(self):
        self.copies.clear()
        self._remove(self.scratch)

    def _remove(self, folder):
        """`folder` deleted; one that can't be (a process outside the checker holds a file of it) is said, with the
        folder to delete, and the run goes on: raised, it ended the run or hid the result it was cleaning up after."""
        try:
            seeds.remove(folder)
        except (OSError, ValueError) as exc:
            self.log(f"  couldn't delete {folder} ({exc}): delete it by hand")


class Side:
    """One side of a check ("start" or "reference"): its scratch project, built once, each play played once.
    `evidence`: where each play's probe.json, screenshots and log are kept (None: not kept)."""

    def __init__(self, name, project, task, timeout, build_timeout, evidence=None, log=print):
        self.name, self.project, self.task = name, project, task
        self.timeout, self.build_timeout = timeout, build_timeout
        self.evidence, self.log = evidence, log
        self.plan = probes.plan(task)
        self.player = tasks.player(task)
        self._build = None
        self._packaged = None  # the package check's (passed, detail), once
        self.played = {}  # play name -> godot.Played
        self.saves = []  # the plays whose saved data the copy holds now: the last that started clean, and those after it
        self.replays = {}  # play name -> what differed when it was played again for its saves (replay_note)
        self.crops = {}  # a seen check's name -> its crops on this side (seen.crops)
        self.routes = {}  # a judge's route file -> (its play or None, why none)
        self.route_from = None  # the Side whose copy a judge's route file is read from (None: this one)
        # what the writer answered for seen checks (seen.kept), set by the task check; None: no answer is read here (a
        # task try), so seen checks are not asked
        self.answers = None

    # -- the build ---------------------------------------------------------------------------------------------------

    def build(self):
        """The side's build. One with no word about the game (its `stopped`) raises godot.BuildStopped, each time it is
        asked, naming the log kept as evidence: no verdict rests on it."""
        if self._build is None:
            again = getattr(self.project, "has_built", lambda: False)()
            if not again:
                self.log(f"  {self.name}: building")
            self._build = self.project.build(self.build_timeout)
            waited = getattr(self._build, "waited", 0.0)
            done = "built" if self._build.exit_code == 0 else \
                "build STOPPED" if getattr(self._build, "stopped", None) else "build FAILED"
            self.log(f"  {self.name}: {done} ({self._build.seconds:.0f} s"
                     f"{', built earlier in this run' if again else ''}"
                     f"{f', {waited:.0f} s of it waiting for a machine slot' if waited >= 1 and not again else ''})")
            if self.evidence is not None and self._build.exit_code != 0:
                self._keep("build", {"build.log": self._build.output.encode("utf-8")})
        stopped = getattr(self._build, "stopped", None)
        if stopped:
            kept = Path(self.evidence) / self.name / "build" / "build.log" if self.evidence is not None else None
            raise godot.BuildStopped(f"{self.game()} didn't build: {stopped}" + (f"; its log: {kept}" if kept else "")
                                     + (f"; {self._build.cause}" if self._build.cause else ""))
        return self._build

    def built(self):
        return self.build().exit_code == 0

    def game(self):
        return {"start": "the game as the task started", "reference": "the reference game"}.get(
            self.name, f"the agent's game ({self.name})")

    def why_unbuilt(self):
        r = self.build()
        return f"{self.game()} didn't build ({failed(r)})"

    # -- plays ---------------------------------------------------------------------------------------------------------

    def _keep(self, name, files):
        folder = Path(self.evidence) / self.name / name
        folder.mkdir(parents=True, exist_ok=True)
        for f, data in files.items():
            (folder / f).write_bytes(data)

    def _play(self, name, seconds, shots, inputs=None, play=None, queries=None, every=None, waits=0.0, again=False,
              packaged=False):
        """A play, once per name, on the scene and args `play` (a task play, or None for the checker's own) opens;
        `waits`: the real seconds its waits add (a task play's), which its timeout gets on top. A task play that
        names `after` starts on the saved data of the plays before it; every other play starts clean (the probe
        clears the copy's saved data). `again`: played once more for the saved data it leaves; its checks keep reading
        its first play, its files are kept as <name>_again, and what differed from the first is noted (replay_note)."""
        if name not in self.played or again:
            keeps = bool(play and play.get("after"))
            self.log(f"  {self.name}: playing {name} " + ("again " if again else "")
                     + f"({seconds} s" + (f", {waits:g} s waiting" if waits else "") + ")")
            scene, args = tasks.place(self.task, play)
            before, self.saves = self.saves, []  # a play that raises leaves no saves known
            found = self.project.play(seconds, shots, self.timeout + math.ceil(waits), scene=scene, inputs=inputs,
                                      queries=queries, args=args, every=every, player=self.player, keep_saves=keeps,
                                      **({"packaged": True} if packaged else {}))
            self.saves = before + [name] if keeps else [name]
            waited = getattr(found, "waited", 0.0)
            ended = found.probe.get("ended") if isinstance(found.probe, dict) else None
            self.log(f"  {self.name}: played {name} " + ("again " if again else "") + f"in {found.seconds:.0f} s"
                     + (f" ({waited:.0f} s of it waiting for a machine slot)" if waited >= 1 else "")
                     + (f": exit {found.exit_code}{', timed out' if found.timed_out else ''}, ended {ended}"
                        if again else ""))
            if self.evidence is not None:
                # the play's spec too: probe.json keys its measures by query id, and only the spec says which id is
                # which select (two components queries of one play, both empty, couldn't be told apart)
                spec = self.project.read(f"{godot.LOGS}/{godot.SPEC}")
                self._keep(name + ("_again" if again else ""),
                           {**found.files, "play.log": found.log.encode("utf-8"),
                            "output.txt": found.output.encode("utf-8"),
                            **({godot.SPEC: spec} if spec is not None else {})})
            if again:
                differs = replay_note(name, self.played[name], found)
                if differs:
                    self.replays[name] = differs
                return found
            self.played[name] = found
        return self.played[name]

    def judge_plays(self, check):
        """{play name: (probe dict or None, {file: bytes})} of every play judge check `check` is shown on this side:
        its own task plays (the probes' own when they name the same play, which is the same play), else the idle play
        and the drive, each played whole (never the boot cut to look's seconds, whose screenshots span the boot)."""
        out = {}
        for play, _, _ in judges.plays(check):
            if play == judges.ROUTE:
                found = self.route_play(check["route"])
                if found is not None:
                    out[judges.ROUTE] = (found.probe, found.files)
                continue
            if isinstance(play, str):
                seconds, shots, inputs = own_play(play, self.project)
                p = self._play(play, seconds, shots, inputs, queries=probes.query_file(self.plan.get(play, [])))
            else:
                p = self.probe_play(play)
            out[play if isinstance(play, str) else play["name"]] = (p.probe, p.files)
        return out

    def route_play(self, path):
        """The developer's route file `path` played on this side as the Lab's grade plays a judge's route: read from
        the graded copy (`route_from`: the reference in a task check, the agent's game in a try), its inputs held to
        the Lab's limits (read_route), played for route_seconds with ROUTE_SHOTS screenshots, once. None, with why in
        `routes`, when it can't be played: then the judge is shown no route play, and nothing stands for it."""
        if path not in self.routes:
            inputs, why = read_route((self.route_from or self).project, path)
            if inputs is None:
                self.routes[path] = None, why
            else:
                seconds = route_seconds(inputs)
                self.routes[path] = self._play(judges.ROUTE, seconds, ROUTE_SHOTS, inputs), None
        return self.routes[path][0]

    def idle(self, seconds):
        """Whether the boot play of `seconds` also serves "look": look is the first part of the same idle game, so one
        play does when the boot is at least as long and no look probe reads the play's log (a log covers the whole
        play, so it can't be cut to look's seconds)."""
        return "look" in self.plan and seconds >= PLAYS["look"][0] and not any(
            tasks.play_name(c) == "look" and c["measure"]["probe"] == "log" for c in probes.probes(self.task))

    def boot(self, seconds):
        """The boot play of `seconds`: {ok, crashed, timed_out, log}."""
        if self.idle(seconds) and "look" not in self.played:
            p = self._play(f"boot_{seconds}s", seconds, PLAYS["look"][1],
                           queries=probes.query_file(self.plan["look"]))
        else:
            p = self._play(f"boot_{seconds}s", seconds, 2)
        crashed = fatal(p.log)
        return {"ok": p.probe is not None and p.probe.get("ended") == "time" and not crashed, "crashed": crashed,
                "timed_out": p.timed_out, "log": godot.during(p.log)}

    def package(self):
        """(passed, detail) of a package check on this side, once: the release export (godot.Project.package), then
        its player played for PACKAGED_SECONDS (1 screenshot) through the probe, passing when it ran to its time with
        no crash."""
        if self._packaged is None:
            if not self.built():
                self._packaged = False, f"{self.why_unbuilt()}, so it wasn't packaged"
                return self._packaged
            self.log(f"  {self.name}: making the release export")
            r = self.project.package(self.build_timeout)
            if self.evidence is not None and (r.exit_code != 0 or not r.playable):
                self._keep("package", {"package.log": r.output.encode("utf-8")})
            if getattr(r, "why", None):
                self._packaged = False, f"packaging failed: {r.why}"
            elif r.exit_code != 0 or not r.playable:
                left = ": the export left no player" if r.exit_code == 0 else ""
                self._packaged = False, ("packaging timed out" if r.timed_out
                                         else f"packaging failed (exit {r.exit_code}){left}")
            else:
                p = self._play("packaged", PACKAGED_SECONDS, 1, packaged=True)
                ok = p.probe is not None and p.probe.get("ended") == "time" and not fatal(p.log)
                self._packaged = ok, (f"packaged and ran {PACKAGED_SECONDS} s" if ok
                                      else "packaged, but the packaged game didn't run cleanly")
        return self._packaged

    def probe_play(self, play):
        """The play a probe names ("look", "drive", a task play), played once with the queries of every probe it
        serves."""
        name = play if isinstance(play, str) else play["name"]
        every = None if isinstance(play, str) else play["every"]
        queries = probes.query_file(self.plan.get(name, []), every)
        if isinstance(play, str):
            seconds, shots, inputs = own_play(play, self.project)
            booted = next((b for b in self.boots() if play == "look" and self.idle(b)
                           and f"boot_{b}s" in self.played), None)
            if booted is not None:
                p = self.played[f"boot_{booted}s"]
                return godot.Played(p.exit_code, p.timed_out, p.output, p.seconds, first_seconds(p.probe, seconds),
                                    p.log, p.files)
            return self._play(name, seconds, shots, inputs, queries=queries)
        return self._task_play(play)

    def cached(self, play):
        """The play a probe names as this side already played it, or None: never a new play (a try's reference copy is
        gone once its agent starts)."""
        name = play if isinstance(play, str) else f"play_{play['name']}"
        if name in self.played or (play == "look" and any(
                f"boot_{b}s" in self.played and self.idle(b) for b in self.boots())):
            return self.probe_play(play)
        return None

    def _task_play(self, play):
        """A task play, after the plays its `after` names (docs/task-probes.md 1.1): each of them played on this copy
        first, in order, and ended, a failed one too, so the copy's saved data is what they left and nothing else's.
        When another play ran since (it cleared the saved data), they are played again for what they save, their
        results dropped."""
        name = f"play_{play['name']}"
        if name in self.played:
            return self.played[name]
        named = tasks.task_plays(self.task)
        before = tasks.chain(self.task, play["name"])
        if before and self.saves != [f"play_{n}" for n in before]:
            for n in before:  # from the first, which starts clean: each on what those before it left
                self._run(named[n], again=f"play_{n}" in self.played)
        return self._run(play)

    def replayed(self, play):
        """What to say in the detail of a check that reads task play `play`: the plays of its chain that, played again
        for their saves, didn't end as their first play did (the saves it read may not be those their checks saw)."""
        if not isinstance(play, dict):
            return ""
        notes = [self.replays[f"play_{n}"] for n in tasks.chain(self.task, play["name"]) if f"play_{n}" in self.replays]
        return "; note: " + "; ".join(notes) if notes else ""

    def _run(self, play, again=False):
        name = play["name"]
        queries = probes.query_file(self.plan.get(name, []), play["every"])
        shots = judges.play_shots(self.task).get(name, 2)  # as the grader plays it: a judge showing it asks more
        return self._play(f"play_{name}", play["seconds"], shots, play["inputs"] or None, play=play, queries=queries,
                          every=play["every"], waits=tasks.waited(play), again=again)

    def boots(self):
        """The boot plays this task's checks run (seconds): its boot checks, and 60 s for a log_absent check."""
        found = []
        for _, check in tasks.checks(self.task):
            seconds = check.get("seconds") if check["kind"] == "boot" else 60 if check["kind"] == "log_absent" else None
            if seconds is not None and seconds not in found:
                found.append(seconds)
        return found

    def seen_crops(self, check):
        """{shot: (crop or None, why none)} of seen check `check` on this side (seen.crops): its task play, played once
        (the probes' own, after the plays its `after` names), each named shot cropped as the Lab crops it."""
        name = check["name"]
        if name not in self.crops:
            measure, play = check["measure"], check["play"]
            if not self.built():
                why = f"{self.why_unbuilt()}, so it wasn't played"
                self.crops[name] = {s: (None, why) for s in seen.shots(measure)}
            else:
                p = self.probe_play(play)
                ended = "wrote no probe file" if p.probe is None else f"ended at {probes.fmt(probes.ended(p.probe))} s"
                self.crops[name] = seen.crops(measure, p.files, lambda s: (
                    f"play {play['name']} took no shot named {s} (it {ended})"))
        return self.crops[name]

    def value(self, check):
        """(probe `check`'s number on this side, or None; why none)."""
        measure = check["measure"]
        if measure["probe"] == "seen":
            found = self.seen_crops(check)
            missing = next((why for _, why in found.values() if why), None)
            if missing:
                return None, missing
            return seen.read(check, self.name, found, (self.answers or {}).get(check["name"]))
        if not self.built():
            return None, f"{self.why_unbuilt()}, so it wasn't played"
        p = self.probe_play(check["play"])
        return probes.measured(measure, p.probe, godot.during(p.log))


def read_route(project, path):
    """(inputs, None) from the developer's route file `path` of `project`'s copy, or (None, why it can't be played), as
    the Lab reads one: at most ROUTE_BYTES, a JSON list of 1 to ROUTE_INPUTS key inputs (the task schema's Key: {t,
    key, press}, the key by its control path), each before ROUTE_SECONDS - 2 s; sorted by time."""
    raw = project.read(path)
    if raw is None:
        return None, f"there is no {path} in the graded copy"
    if len(raw) > ROUTE_BYTES:
        return None, f"{path} is longer than {ROUTE_BYTES // 1024 // 1024} MiB"
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError):
        return None, f"{path} isn't valid JSON"
    if not isinstance(data, list) or not 1 <= len(data) <= ROUTE_INPUTS:
        return None, f"{path} isn't a list of 1 to {ROUTE_INPUTS} inputs"
    v = tasks.validator()
    schema = v.SCHEMAS["game-task"]
    for e in data:
        t = e.get("t") if isinstance(e, dict) else None
        if list(v.check_schema(e, schema["$defs"]["Key"], schema)) or isinstance(t, bool) \
                or not 0 <= t <= ROUTE_SECONDS - 2:
            return None, (f"{path} has an input that isn't {{t: 0-{ROUTE_SECONDS - 2} s, key: a control path such as "
                          "<Keyboard>/w, press: true/false}")
    return sorted(({"t": float(e["t"]), "key": e["key"], "press": e["press"]} for e in data), key=lambda e: e["t"]), None


def route_seconds(inputs):
    """How long a route is played: 4 s past its last input, 10 s at least, ROUTE_SECONDS at most."""
    return int(min(ROUTE_SECONDS, max(10, math.ceil(max(e["t"] for e in inputs)) + 4)))


# what the probe's inputs.gd says of a widget click no shown Control matches (`_click`); a test holds the two alike
NO_CONTROL = "no visible control that takes a click matches it, by name, class or caption"
# the words its why holds for a click whose button is shown but disabled (`_click`); a test holds the two alike
DISABLED = "shown but disabled"


def missed(probe, play=None):
    """The inputs a play sent that didn't land (probe.json `inputs_missed`: a click no control took, a touch on a
    control that isn't shown, a stage that reached nothing), named screenshots left out (a shot not taken changed
    nothing the game did); [] when there are none or the play can't say. With task play `play` (its dict), less the
    clicks their own marks excuse, each only for its own reason: an `optional` click that found no shown Control to
    press (what it would press was not there, and the play went on), and a `disabled` click whose button the probe
    found shown but disabled (it landed, and did nothing, as a player's). An optional click that found its Control
    and didn't press it, or found it disabled, is still a miss; so is a disabled click no button matched."""
    rows = probe.get("inputs_missed") if isinstance(probe, dict) else None
    rows = [r for r in rows if isinstance(r, dict) and r.get("kind") != "shot"] if isinstance(rows, list) else []
    if not rows or not isinstance(play, dict):
        return rows
    marked = [(float(i["t"]), i["widget"], i.get("optional") is True, i.get("disabled") is True)
              for i in play.get("inputs") or []
              if isinstance(i, dict) and i.get("click") and (i.get("optional") is True or i.get("disabled") is True)
              and isinstance(i.get("t"), int | float) and isinstance(i.get("widget"), str)]

    def excused(r):
        why = r.get("why") if isinstance(r.get("why"), str) else ""
        return r.get("kind") == "click" and isinstance(r.get("t"), int | float) and any(
            abs(float(r["t"]) - t) < 1e-6 and r.get("target") == widget
            and ((optional and why == NO_CONTROL) or (disabled and DISABLED in why))
            for t, widget, optional, disabled in marked)

    return [r for r in rows if not excused(r)]


def missed_text(rows, limit=3):
    """Missed inputs in a line: "tap StartButton at 1 s (no visible control matches it); ..."."""
    said = [f"{r.get('kind')} {r.get('target')} at {probes.fmt(r['t']) if isinstance(r.get('t'), int | float) else '?'}"
            f" s ({str(r.get('why'))[:200]})" for r in rows[:limit]]
    return "; ".join(said) + (f"; and {len(rows) - limit} more" if len(rows) > limit else "")


def reads_nothing(measure, probe):
    """Why a selecting measure read nothing in a whole play, its window aside, or None: the probe sampled its query
    but its select matched no row in any sample, or no row it matched had a value for its field (any row is one for a
    `count`, and for a `ui` field read over everything the select picks: signature, number, clock). A `ui` sample
    after which no frame was drawn is left out. None too when the play never sampled it (the play's own failure, said
    elsewhere)."""
    (query,) = probes.needs(measure)
    samples = [s for s in (probe.get("measures") or {}).get(probes.query_id(query)) or [] if isinstance(s, dict)
               and (measure["probe"] != "ui" or isinstance(s.get("rows"), list))]
    if not samples:
        return None
    rows = [r for s in samples for r in s.get("rows") or [] if isinstance(r, dict)]
    totals = [s.get("total") for s in samples if isinstance(s.get("total"), int | float)]
    match = measure.get("match")
    whole = measure["probe"] == "ui" and measure["field"] in probes.UI_WHOLE
    if (rows or any(totals)) and (measure["field"] == "count" or whole or any(
            probes.number(r.get(measure["field"]), match) is not None for r in rows)):
        return None
    select = json.dumps(measure.get("select"), sort_keys=True)
    what = (f"its select {select} matched nothing" if not rows else
            f"nothing its select {select} matched had a value for {measure['field']}")
    return f"{what} in {len(samples)} samples"


class Grade:
    """The checks of one side as a solution's grade would run them. `mode` "reference": every check but judges, of the
    reference or of `side` (an agent's game, task-try.py); "start": its probes and a
    `fails_at_start` build check. Thresholds are shared between the grades (`thresholds`)."""

    def __init__(self, task, mode, start, reference, thresholds, side=None):
        self.task, self.mode, self.start, self.reference = task, mode, start, reference
        self.side = side or (reference if mode == "reference" else start)  # `side`: an agent's game graded as a solution
        self.thresholds = thresholds
        self.measured = {}

    def threshold(self, check):
        if check["name"] not in self.thresholds:
            try:
                self.thresholds[check["name"]] = verdict.make_threshold(
                    check, lambda: self.start.value(check),
                    lambda: self.reference.value(check) if self.reference else (None, "the task has no reference"))
            except verdict.Uncalibrated as exc:
                self.thresholds[check["name"]] = exc
        found = self.thresholds[check["name"]]
        if isinstance(found, verdict.Uncalibrated):
            raise found
        return found

    def probe_check(self, check):
        try:
            limit, start, fix = self.threshold(check)
        except verdict.Uncalibrated as exc:
            value, _ = self.side.value(check)
            self.measured[check["name"]] = {"value": value, "threshold": None, "start": exc.start, "fix": exc.fix}
            return False, f"uncalibrated: {exc}"
        value, why = self.side.value(check)
        self.measured[check["name"]] = {"value": value, "threshold": limit, "start": start, "fix": fix}
        if self.mode == "reference":
            broken = self.unreadable(check, limit)
            if broken:
                return False, f"{TASK_ERROR}: {check['describe']} | {broken}"
        landed = self.landing(check["play"])
        if landed:
            broken, said = landed
            return False, f"{TASK_ERROR}: {check['describe']} | {broken}" if broken else f"{check['describe']} | {said}"
        passed = value is not None and verdict.passes(value, check["expect"]["op"], limit)
        return passed, verdict.describe(check, value, limit, start, fix, why)

    def unreadable(self, check, limit):
        """Why no version of the game can pass probe `check`, or None: its select (objects, widgets, components, ui) reads
        nothing in the reference's play of it, a play that ran to its end: no row matched in any sample, or none had a
        value for its field. A measure that reads 0 of nothing (a count, or `of` count, any, all or sum) is not refused
        when 0 passes its threshold `limit`: there nothing matching is the outcome."""
        measure, ref = check["measure"], self.reference
        if ref is None or measure["probe"] not in SELECTING or not ref.built():
            return None
        played = ref.cached(check["play"])
        found = played.probe if played is not None else None
        if not isinstance(found, dict) or found.get("ended") != "time":
            return None
        why = reads_nothing(measure, found)
        zero = measure["field"] == "count" or measure.get("of") in ("count", "any", "all", "sum")
        if why is None or (zero and limit is not None and verdict.passes(0.0, check["expect"]["op"], limit)):
            return None
        name = tasks.play_name(check)
        said = "the task's own fix fails it" if zero else "the check reads nothing even on the task's own fix"
        return f"in the reference's {name if name in ('look', 'drive') else 'play ' + name}, {why}: {said}"

    def landing(self, play):
        """None when task play `play`'s inputs all landed in this side's play (or `play` is look or drive, or it
        wasn't played); else (why it is a task error, or None; the detail when it isn't): an input that didn't land is
        the task's error when the reference's play missed one too (its own fix can't be driven by its play), else this
        side's fail, as the Lab's grade reads it. An `optional` click that found nothing to press, and a `disabled` click
        whose button is shown but disabled, is no miss (missed)."""
        if isinstance(play, str) or not self.side.built():
            return None
        rows = missed(self.side.probe_play(play).probe, play)
        if not rows:
            return None
        ref = self.reference
        if ref is not None and ref.built():
            played = None if ref is self.side else ref.cached(play)
            theirs = rows if ref is self.side else missed(played.probe if played is not None else None, play)
            if theirs:
                return (f"in the reference's play {play['name']}, an input did not land ({missed_text(theirs)}): the "
                        "task's own fix can't be driven by its play"), None
        return None, f"the play's input did not land: {missed_text(rows)}"

    def check(self, check):
        kind = check["kind"]
        if kind in JUDGES:
            return True, NOT_JUDGED
        if seen.is_seen(check) and self.side.answers is None:
            return True, seen.NOT_READ
        if self.mode == "start":
            if kind == "build" and check["fails_at_start"]:
                return (True, "the start built") if self.start.built() else (False, self.start.why_unbuilt())
            if kind != "probe":
                return True, "not asked: the start is checked on its probes"
            return self.probe_check(check)
        side = self.side
        if kind == "build":
            r = side.build()
            return r.exit_code == 0, "built" if r.exit_code == 0 else f"build failed ({failed(r)})"
        if kind == "boot":
            if not side.built():
                return False, f"{side.why_unbuilt()}, so it wasn't played"
            p = side.boot(check["seconds"])
            if p["ok"]:
                return True, f"ran {check['seconds']} s with no crash or fatal error"
            return False, "crashed" if p["crashed"] else ("timed out" if p["timed_out"] else "didn't finish its run")
        if kind == "log_absent":
            if not side.built():
                return False, f"{side.why_unbuilt()}, so it wasn't played"
            hits = [line for line in side.boot(60)["log"].splitlines() if re.search(check["pattern"], line)]
            return not hits, f"{len(hits)} matching log line(s)" + (f": {hits[0][:200]}" if hits else "")
        if kind == "file_exists":
            root = side.project.folder
            found = [p for p in root.glob(check["glob"]) if p.is_file()
                     and not SKIP.intersection(p.relative_to(root).parts)]
            return len(found) >= check["min_count"], f"{len(found)} file(s) match"
        if kind == "package":
            return side.package()
        if kind == "probe":
            return self.probe_check(check)
        raise ValueError(f"no check kind {kind}")

    def run(self):
        """{"checks": [{name, kind, passed, required, detail, group}], "probes": {name: {value, threshold, start,
        fix}}}."""
        rows, passed = [], {}
        for group, check in tasks.checks(self.task):
            missing = [n for n in check["needs"] if not passed.get(n)]
            if missing:
                ok, detail = False, f"not run: needs {missing[0]}"
            else:
                try:
                    ok, detail = self.check(check)
                    if check["kind"] == "probe":
                        detail = str(detail) + self.side.replayed(check["play"])
                except godot.MachineError:
                    raise  # the machine can't run Godot (its limiter, no desktop): no verdict on the game
                except (OSError, RuntimeError, ValueError) as exc:
                    ok, detail = False, f"the checker failed ({type(exc).__name__}: {str(exc)[:200]})"
            passed[check["name"]] = bool(ok)
            rows.append({"name": check["name"], "kind": check["kind"], "passed": bool(ok),
                         "required": check["required"], "weight": check["weight"], "detail": str(detail)[:700],
                         "group": group})
        return {"checks": rows, "probes": self.measured}


def _how(played):
    """How a play ended, for comparing two plays of one play: (how it ended, timed out, the inputs that missed)."""
    probe = played.probe if isinstance(played.probe, dict) else {}
    missed = [(m.get("t"), m.get("kind"), m.get("target")) for m in probe.get("inputs_missed") or []
              if isinstance(m, dict)]
    return probe.get("ended"), bool(played.timed_out), missed


def replay_note(name, first, again):
    """What differed when play `name` was played again for its saved data, in words, or None: how it ended, whether it
    timed out, which inputs missed."""
    a, b = _how(first), _how(again)
    if a == b:
        return None
    said = []
    if a[0] != b[0]:
        said.append(f"it ended {b[0]} (first: {a[0]})")
    if a[1] != b[1]:
        said.append("it timed out" if b[1] else "it did not time out as the first did")
    if a[2] != b[2]:
        said.append(f"{len(b[2])} input(s) missed (first: {len(a[2])})")
    return f"{name}, played again for its saved data, did not go as its first play: " + ", ".join(said)


def valid_name(name):
    """Whether `name` is a task name as the schema has it (so it can name a result file and an evidence folder)."""
    pattern = tasks.validator().SCHEMAS["game-task"]["properties"]["name"]["pattern"]
    return isinstance(name, str) and re.fullmatch(pattern, name) is not None


def start_unbuilt(task, why):
    """The start's grade when it doesn't build and the task says so: that build check failed, nothing else run."""
    group, build = next((g, c) for g, c in tasks.checks(task) if c["kind"] == "build" and c["fails_at_start"])
    return {"checks": [{"name": build["name"], "kind": "build", "passed": False, "required": build["required"],
                        "weight": build["weight"], "detail": str(why)[:700], "group": group}], "probes": {}}


def save_judge_shots(task, sides, folder, where="", blind=False, log=print, rng=None, held=None):
    """Play every `judge` check's plays on `sides` ({folder name: Side}, a side that didn't build left out with a note)
    and save the screenshots its judge would see under <folder>/<check>/ (judges.save), with the blind copy when
    `blind` and the scores `held` (judges.kept) still stand for. Nothing is asked of a model: {check: record}, each
    "answer needed" until scored, its `folder` named as `where` (the folder's place in the results) and the check's
    name. A route that couldn't be played is said in the notes: the judge is shown no route there."""
    out = {}
    for found in judges.judges(task):
        played, notes = {}, []
        for label, side in sides.items():
            try:
                if not side.built():
                    notes.append(f"{label}: no screenshots, {side.why_unbuilt()}")
                    continue
                played[label] = side.judge_plays(found)
                if found["route"] and side.routes.get(found["route"], (None, None))[0] is None:
                    notes.append(f"{label}: the route {found['route']} was NOT played: "
                                 f"{side.routes[found['route']][1]}; the judge is shown no route, and nothing stands "
                                 "for it")
            except Exception as exc:  # a play the checker couldn't make: said in ask.md, never the task's error
                notes.append(f"{label}: the plays failed ({type(exc).__name__}: {str(exc)[:200]})")
        record = judges.save(task, found, played, folder, blind=blind, notes=notes, rng=rng,
                             held=(held or {}).get(found["name"]))
        record["folder"] = f"{where}{found['name']}/"
        log(f"  {judges.line(found['name'], record)}")
        out[found["name"]] = record
    return out


def judged(task, records, played=True):
    """Why the task's required `judge` checks keep it from being VALID, from the writer's scores (save_judge_shots'
    records): every one scored on every side shown, the reference passing it, and the start passing a judge of what
    still looks as it did (in still_works) or scoring every required item below judges.REQUIRED on any other. A judge
    is a required check like any other, so a task isn't VALID on scores nobody gave. A required judge with no play of
    its own (no `plays`, no `route`) never passes here, whatever its scores: it is shown only the idle look and the
    drive, which never press a task's keys or leave a title screen."""
    out = []
    for group, c in tasks.checks(task):
        if c["kind"] != "judge" or not c["required"]:
            continue
        if not c.get("plays") and not c.get("route"):
            out.append(f"judge {c['name']}: {NO_OWN_PLAY}")
        found = (records or {}).get(c["name"])
        if not played or found is None:
            out.append(f"judge {c['name']}: not played (--no-judge-shots), answer needed")
            continue
        if found["status"] != judges.ANSWERED:
            out.append(f"judge {c['name']}: {found['status']}")
            continue
        ref, own = found["answered"].get("reference"), found["answered"].get("start")
        if ref is not None and not ref["passed"]:
            out.append(f"reference fails judge {c['name']} as you scored it ({ref['why']})")
        if own is not None and group == tasks.STILL_WORKS and not own["passed"]:
            out.append(f"start fails still-works judge {c['name']} as you scored it ({own['why']})")
        elif own is not None and group != tasks.STILL_WORKS and not own["low"]:
            out.append(f"start already meets a required item of judge {c['name']} as you scored it ({own['why']})")
    return out


def save_seen_shots(task, sides, folder, where="", held=None, log=print, rng=None):
    """Save every `seen` check's crops of `sides` ({folder name: Side}, a side that didn't build noted) under
    <folder>/<check>/ (seen.save), each with its blind copy and the answers `held` (seen.kept) still stand for:
    {check: record}, its `folder` named as `where` and the check's name."""
    out = {}
    for found in seen.checks(task):
        crops, notes = {}, []
        for label, side in sides.items():
            try:
                crops[label] = side.seen_crops(found)
            except godot.MachineError:
                raise  # the machine can't run Godot: no verdict on the game
            except (OSError, RuntimeError, ValueError) as exc:
                notes.append(f"{label}: the play failed ({type(exc).__name__}: {str(exc)[:200]})")
        record = seen.save(task, found, crops, folder, (held or {}).get(found["name"]), rng, notes)
        record["folder"] = f"{where}{found['name']}/"
        log(f"  {seen.line(found['name'], record)}")
        out[found["name"]] = record
    return out


def probe_values(task, reference, start):
    """{probe: {group, required, op, expect, start, reference, threshold, start_passed, reference_passed}} from the two
    grades' measures."""

    def passed(grade, name):
        return next((r["passed"] for r in (grade or {}).get("checks", []) if r["name"] == name), None)

    out = {}
    for group, check in tasks.checks(task):
        if check["kind"] != "probe":
            continue
        name = check["name"]
        ref = ((reference or {}).get("probes") or {}).get(name) or {}
        own = ((start or {}).get("probes") or {}).get(name) or {}
        out[name] = {"group": group, "required": check["required"], "op": check["expect"]["op"],
                     "expect": check["expect"], "start": own.get("value", ref.get("start")),
                     "reference": ref.get("value") if reference else None,
                     "threshold": ref.get("threshold", own.get("threshold")),
                     "start_passed": passed(start, name), "reference_passed": passed(reference, name) if reference
                     else None}
    return out


def check_task(repo, task, raw, scratch, out_dir, keep=False, direct=False, timeout=1800, build_timeout=3600,
               log=print, clock=time.time, builds=None, judge_shots=True):
    """Check one task (a dict read from `repo`'s tasks branch, its file's bytes `raw`): its result (written to
    <out_dir>/<name>.json, its plays' files under <out_dir>/<name>/). `builds`: a run's shared copies (Builds), which
    the run deletes; without it the task gets its own under `scratch`, deleted when it is done unless `keep`.
    `judge_shots`: each `judge` check's screenshots of the start and the reference saved under
    <out_dir>/<name>/judge-shots/ for a person to answer (the verdict never waits on them). Each `seen` check's crops
    are saved under <out_dir>/<name>/seen-shots/, and the answers an earlier check's folder holds are read first."""
    started = clock()
    name = task.get("name", "?")
    result = {"format": FORMAT, "task": name, "game": (task.get("seed") or {}).get("game"),
              "task_sha256": tasks.digest(raw), "verdict": None, "reasons": [], "notes": [], "start": None,
              "reference": None, "probes": {}, "start_checks": [], "reference_checks": [], "judges": {},
              "seen": {}, "evidence": f"{name}/", "at": None, "seconds": None}
    sides = {}

    def finish(state, reasons, notes=()):
        result.update(verdict=state, reasons=list(reasons), notes=list(notes), seconds=round(clock() - started, 1),
                      at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        if valid_name(name):  # a task that doesn't validate may be named a/b, ../x or nothing: no file of its own then
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    found = tasks.problems(task)
    if found:
        return finish("INVALID", [f"the task doesn't validate: {p}" for p in found[:5]])
    seed = task["seed"]
    evidence = Path(out_dir) / name
    held = seen.kept(evidence / "seen-shots")  # the writer's answers outlive the evidence they were given for
    scores = judges.kept(evidence / "judge-shots")
    own = builds is None
    if own:
        builds = Builds(repo, scratch, direct, log)
    try:
        seeds.remove(evidence)  # (an earlier check's files another program holds: this task's error, not the run's)
        shas = {}
        for side, commit in (("start", seed["commit"]), ("reference", seed.get("reference"))):
            if commit is None:
                continue
            try:
                shas[side] = seeds.resolve(repo, commit)
            except RuntimeError:
                return finish("INVALID", [f"seed.{'commit' if side == 'start' else 'reference'} {commit[:12]} isn't a "
                                          f"commit of {Path(repo).name} (fetch it, or fix the task)"])
        for side, sha in shas.items():
            try:
                project, info = builds.get(sha, shas.values())
            except seeds.WrongEngine as exc:
                return finish("INVALID", [f"{side}: {exc}"])
            sides[side] = Side(side, project, task, timeout, build_timeout, evidence, log)
            sides[side].answers = held
            result[side] = {"commit": sha, **info}
        start, reference = sides["start"], sides.get("reference")
        for made in sides.values():  # a judge's route is read from the graded copy: the oracle's, the reference
            made.route_from = reference or start
        build = tasks.fails_at_start(task)
        if not start.built():
            result["start"]["built"] = False
            if build is None:
                return finish("INVALID", [f"start doesn't build: {start.why_unbuilt()}"])
        else:
            result["start"]["built"] = True
        thresholds = {}
        ref_grade = None
        if reference is not None:
            ref_grade = Grade(task, "reference", start, reference, thresholds).run()
            result["reference"]["built"] = reference.built()
        if build is not None and not start.built():
            start_grade = start_unbuilt(task, start.why_unbuilt())
        else:
            start_grade = Grade(task, "start", start, reference, thresholds).run()
        valid, why, notes = verdict.verdict(task, ref_grade, start_grade)
        if reference is None:  # the start's rows still tell the writer what it does, but nothing proves the checks
            valid, why = False, [NO_REFERENCE] + list(why)
        if judges.judges(task):
            if judge_shots:
                shown = {label: s for label, s in (("start", start), ("reference", reference)) if s is not None}
                result["judges"] = save_judge_shots(task, shown, evidence / "judge-shots", f"{name}/judge-shots/",
                                                    blind=True, log=log, held=scores)
                notes += [judges.line(n, r) for n, r in result["judges"].items()]
            found = judged(task, result["judges"], judge_shots)
            valid, why = valid and not found, list(why) + found
        if seen.checks(task):  # a start that doesn't build by design is never played, so it has nothing to read
            shown = {label: s for label, s in (("start", start), ("reference", reference)) if s is not None
                     and not (label == "start" and build is not None and not start.built())}
            result["seen"] = save_seen_shots(task, shown, evidence / "seen-shots", f"{name}/seen-shots/", held, log=log)
            notes += [seen.line(n, r) for n, r in result["seen"].items()]
            # a required seen check gates as a probe does, so the task isn't VALID until both sides are answered (an
            # unanswered start would otherwise read as the start failing it)
            waiting = [seen.line(c["name"], result["seen"][c["name"]]) for c in seen.checks(task)
                       if c["required"] and result["seen"][c["name"]]["status"] != seen.ANSWERED]
            valid, why = valid and not waiting, list(why) + waiting
        result.update(probes=probe_values(task, ref_grade, start_grade), start_checks=start_grade["checks"],
                      reference_checks=ref_grade["checks"] if ref_grade else [])
        return finish("VALID" if valid else "INVALID", why, notes)
    except Exception as exc:  # any error of the checker's own: this task's ERROR, never the end of a run of many
        return finish("ERROR", [f"the checker couldn't check it: {type(exc).__name__}: {str(exc)[:400]}"])
    finally:
        if own and not keep:
            builds.close()
