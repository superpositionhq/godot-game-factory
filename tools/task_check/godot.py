"""Godot for the checker: prepare a scratch copy for its plays and play it with the task probe addon. A copy is played
from source with the editor binary, so there is no player build: the "build" is the import. Every job goes through
the machine's `<root>\\tools\\godot-heavy.ps1` when it has one (the machine's shared CPU/GPU slots: the timeout then
counts from when the job starts, never the wait for a slot), else runs directly. The engine is the machine's pinned
Godot, its console exe (machine/lib/ggfroot.py `godot_exe`).

- build: <godot> --headless --path <copy> --import --log-file <copy>/Logs/TaskProbe/build.log, then <godot> --headless
  --path <copy> --script <copy>/Logs/TaskProbe/scripts.gd --log-file <copy>/Logs/TaskProbe/scripts.log, which loads
  every script of the project (the import alone parses only the scripts the editor opens). It passed when both exit 0
  and neither log has a script that doesn't parse. One that fails with no word about the game (the engine stopped) is tried once
  more: see build;
- play: python desk.py <godot> --path <copy> --log-file <copy>/Logs/TaskProbe/play.log [scene] -- -taskProbe <spec>
  <play args>, in one of the limiter's GPU slots: one spec file (godot-probe-play/1) says everything about the play
  (the frame's size, seconds, screenshots, sampling, the clock's frames a second, scene, sound, player, inputs,
  queries). A desktop game is played at 960x540, a mobile game (its copy has a Platform.json) at the phone's size, by how
  it is held (MOBILE_SIZE), its spec saying `touch` too. desk.py starts the game on a Windows
  desktop of its own, so the play shows nothing on the user's screen and never takes the keyboard or the mouse
  cursor."""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import probes, seeds

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "machine" / "lib"))
import ggfroot  # noqa: E402  (godot-game-factory's machine root and Godot resolver)

SHOT_SIZE = (960, 540)  # a desktop game's frame
MOBILE_SIZE = {"landscape": (1920, 1080), "portrait": (1080, 1920)}  # a mobile game's: the phone's, by how it is held
OUTPUT_CHARS = 30_000
CAUSE_CHARS = 200  # a failed build's cause, as its reason quotes it
WRAPPER_GRACE = 60  # seconds godot-heavy.ps1 gets to release its slot once the job it runs is killed
QUEUE_POLL = 5  # seconds between looks at whether the wrapper has started its job
LOGS = "Logs/TaskProbe"  # in the copy: specs, logs and the play's folder (Logs/ is never the game's)
DESK = HERE / "desk.py"  # runs the game on its own desktop
SPEC_FORMAT = "godot-probe-play/1"
SPEC = "play_spec.json"  # in LOGS: the last play's spec
# The play's clock is frames at a fixed FPS per second, run as fast as the machine renders: only the command line can
# set that (an autoload can't), so the spec says it too. No sound reaches the machine's speakers.
FPS = 30
PLAY_FLAGS = ["--fixed-fps", str(FPS), "--disable-vsync", "--audio-driver", "Dummy"]
# A crash in a play's log. A script error the game survives isn't one: log_absent checks for those.
FATAL = r"CrashHandlerException|Program crashed with signal|Dumping the backtrace|Out of memory"
# A script error in the import's log: a build that failed with one failed on the game's code.
SCRIPT_ERROR = r"SCRIPT ERROR|Parse Error|Failed to load script"
# A script that doesn't parse or compile, as the engine logs it when the scripts pass loads it. Not every SCRIPT
# ERROR there: the game's autoloads wake in that job with no scene to play, and one may fail at run time for that alone.
LOAD_ERROR = r"SCRIPT ERROR: (?:Parse|Compile) Error|Failed to load script"
SCRIPTS_DONE = "TASKPROBE_SCRIPTS_DONE"
SCRIPT_FAILED = "TASKPROBE_SCRIPT_FAILED"
# The build's second job: every script of the project loaded once the autoloads exist (a script may name one), in
# the folders the engine reads (none with a .gdignore, none that starts with a dot). Loading a script runs none of
# it. The engine logs each one that doesn't parse (LOAD_ERROR); the pass prints SCRIPT_FAILED and the path for one
# the engine gave nothing for, then SCRIPTS_DONE and how many.
SCRIPTS_PASS = """extends SceneTree


func _initialize() -> void:
\tvar bad := 0
\tvar todo: Array[String] = ["res://"]
\twhile not todo.is_empty():
\t\tvar folder: String = todo.pop_back()
\t\tvar dir := DirAccess.open(folder)
\t\tif dir == null:
\t\t\tcontinue
\t\tfor sub in dir.get_directories():
\t\t\tvar path := folder.path_join(sub)
\t\t\tif not sub.begins_with(".") and not FileAccess.file_exists(path.path_join(".gdignore")):
\t\t\t\ttodo.append(path)
\t\tfor file in dir.get_files():
\t\t\tif file.get_extension() == "gd" and ResourceLoader.load(folder.path_join(file)) == null:
\t\t\t\tbad += 1
\t\t\t\tprint("TASKPROBE_SCRIPT_FAILED ", folder.path_join(file))
\tprint("TASKPROBE_SCRIPTS_DONE ", bad)
\tquit(1 if bad else 0)
"""


@dataclass
class Result:
    exit_code: int | None  # None: killed at its timeout
    output: str
    seconds: float
    timed_out: bool = False
    waited: float = 0.0  # of `seconds`, waiting for a godot-heavy.ps1 slot before the job started
    cause: str | None = None  # a failed build's first cause, one line (_cause)
    stopped: str | None = None  # a failed build with no word about the game: how it stopped (Project.build)


@dataclass
class Played:
    exit_code: int | None
    timed_out: bool
    output: str
    seconds: float
    probe: dict | None  # the probe's probe.json; None when it wrote none (the game didn't get there)
    log: str
    files: dict = field(default_factory=dict)  # what the play wrote (probe.json, screenshots) by name
    waited: float = 0.0  # of `seconds`, waiting for a machine slot


def cut(text, limit=OUTPUT_CHARS):
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} characters left out] ...\n{text[-half:]}"


def _kill_tree(pid):
    if os.name != "nt":  # (the factory's machines are Windows; elsewhere the process alone)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        return
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)


def _children(pid):
    """{parent pid: [child pids]} of every process (one CIM query)."""
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                          "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId) "
                          "$($_.Name)\" }"], capture_output=True, text=True, check=False).stdout
    children, names = {}, {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
            names[int(parts[0])] = parts[2] if len(parts) > 2 else ""
    return children, names


def _descendants(pid):
    children, _ = _children(pid)
    found, todo = [], list(children.get(pid, []))
    while todo:
        child = todo.pop()
        if child != pid and child not in found:
            found.append(child)
            todo += children.get(child, [])
    return list(reversed(found))


def _job_started(pid, name):
    """Whether godot-heavy.ps1's wrapper `pid` has started its job: a child process named `name`, the job's own
    executable. Not any child: while it waits for a slot the limiter runs helpers of its own (nvidia-smi for its VRAM
    guard), and one taken for the job started its timeout during the wait."""
    children, names = _children(pid)
    return any(names.get(c, "").strip().lower() == name.lower() for c in children.get(pid, []))


def run(argv, cwd, timeout, wrapper=None, clock=time.monotonic):
    """Run `argv` in `cwd`; its output, cut. Killed with its children after `timeout` seconds, or at once when the wait
    is interrupted; `wrapper`: `argv` is godot-heavy.ps1's and `wrapper` the file name of its job's executable, so
    `timeout` counts from when its job starts, only the job is killed, and the wrapper gets WRAPPER_GRACE seconds to
    release its slot."""
    started = clock()
    proc = subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    chunks = []
    reader = threading.Thread(target=lambda: chunks.append(proc.stdout.read()), daemon=True)
    reader.start()
    job = None if wrapper else started
    looked = started  # the last look that found no job yet
    timed_out = False
    try:
        while True:
            try:
                proc.wait(timeout=QUEUE_POLL if job is None else max(0.05, min(QUEUE_POLL, timeout - (clock() - job))))
                break
            except subprocess.TimeoutExpired:
                if job is None:
                    if _job_started(proc.pid, wrapper):
                        job = clock()
                    else:
                        looked = clock()
                    continue
                if clock() - job < timeout:
                    continue
                timed_out = True
                if wrapper:
                    for child in _descendants(proc.pid):
                        subprocess.run(["taskkill", "/F", "/PID", str(child)], capture_output=True, check=False)
                    try:
                        proc.wait(timeout=WRAPPER_GRACE)
                    except subprocess.TimeoutExpired:
                        _kill_tree(proc.pid)
                        proc.wait()
                else:
                    _kill_tree(proc.pid)
                    proc.wait()
                break
    except BaseException:
        # Ctrl+C (or any error) while waiting: the job is in a process group of its own, so the interrupt never
        # reached it; it would go on building into a copy being deleted, or playing where nobody sees it.
        _kill_tree(proc.pid)
        proc.wait()
        raise
    finally:
        reader.join(timeout=30)
        if not reader.is_alive():  # closing the pipe under a read that still waits would block until the read returns
            proc.stdout.close()
    text = (b"".join(chunks)).decode("utf-8", errors="replace").replace("\r\n", "\n")
    # a job seen start within its first look: ~0; one that came and went between two looks (a short play): at least
    # until the last look that didn't find it, else its wait read as its own time
    waited = (job if job is not None else looked) - started if wrapper else 0.0
    return Result(None if timed_out else proc.returncode, cut(text), round(clock() - started, 3), timed_out,
                  round(waited, 3))


class MachineError(RuntimeError):
    """The machine can't run Godot's jobs: the run's error, never a verdict on the game."""


class LimiterRefused(MachineError):
    """The machine's job limiter couldn't be started at all."""


class BuildStopped(MachineError):
    """A build with no word about the game: stopped twice with no script error, or stopped at its time limit."""


class NoDesktop(MachineError):
    """desk.py couldn't start the game on a desktop of its own: the game never ran."""


def _ps_quote(value):
    # PowerShell reads the typographic quotes as quotes too: each is doubled (a folder named O’Brien broke every job)
    return "'" + re.sub("(['‘’‚‛])", r"\1\1", str(value)) + "'"


@dataclass
class Machine:
    """Where Godot is and how jobs run: `editor` (the machine's Godot console exe), `heavy` (the slot limiter, or None
    to run directly)."""

    editor: Path
    heavy: Path | None

    @classmethod
    def for_project(cls, project, direct=False):
        """The machine for a scratch copy. Raises RuntimeError saying what to install when the machine has no Godot."""
        try:
            editor = Path(ggfroot.godot_exe(console=True))
        except SystemExit as exc:  # ggfroot exits, as a command line would; the checker reports it per task
            raise RuntimeError(str(exc)) from None
        heavy = Path(ggfroot.root()) / "tools" / "godot-heavy.ps1"
        return cls(editor=editor, heavy=None if direct or not heavy.is_file() else heavy)

    def job(self, label, argv, cwd, timeout, gpu=False):
        """`argv` as one Godot job: through godot-heavy.ps1 when the machine has it (in a GPU slot too when `gpu`),
        else directly. The limiter is the machine's own installed script, started the way the skills start the
        machine's scripts (-ExecutionPolicy Bypass): a plain `powershell` started from another shell runs no script
        on a default Windows. A limiter PowerShell still refuses to load (a policy the organisation set) raises
        LimiterRefused: that is the machine's fault, never a game that doesn't build."""
        if self.heavy is None:
            return run([str(a) for a in argv], cwd, timeout)
        command = (f"& {_ps_quote(self.heavy)} -Label {_ps_quote(label)}{' -Gpu' if gpu else ''} -- "
                   + " ".join(_ps_quote(a) for a in argv)
                   + "; if ($null -eq $LASTEXITCODE) { exit 1 }; exit $LASTEXITCODE")
        found = run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                    cwd, timeout, wrapper=Path(str(argv[0])).name)
        if found.exit_code and ("cannot be loaded" in found.output or "not digitally signed" in found.output):
            raise LimiterRefused("PowerShell refused to run godot-heavy.ps1 (an execution policy set for this machine): "
                                 "pass --direct to run without the machine's job slots. " + found.output.strip()[:300])
        return found


def _read_json(path):
    """A JSON object from `path`, or None (no file, not JSON, not an object)."""
    try:
        found = json.loads(Path(path).read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def _read_text(path):
    try:
        return Path(path).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def _cause(log):
    """A failed build's first cause in one line, for its reason (the log stays the evidence): the log's first script
    error as the engine prints it, with the place its next line names (`SCRIPT ERROR: Parse Error: ... at:
    GDScript::reload (res://game/hero.gd:12)`), else the first script the scripts pass couldn't load, else None."""
    found = None
    line = re.search(r"^.*SCRIPT ERROR:\s*(.*)$\n?(?:\s*at:\s*(.*)$)?", log, re.M)
    if line:
        found = line.group(1).strip() + (f" at {line.group(2).strip()}" if line.group(2) else "")
    for pattern in (r"^.*(?:Parse Error|Failed to load script).*$", rf"^{SCRIPT_FAILED} .*$"):
        line = None if found else re.search(pattern, log, re.M)
        found = found or (line.group(0).strip() if line else None)
    return found if found is None or len(found) <= CAUSE_CHARS else found[:CAUSE_CHARS - 3] + "..."


def _fresh(path):
    """`path` (a file) gone and its folder there: what a job writes is never an earlier job's."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seeds.remove(path)
    return path


class Project:
    """A scratch copy of the game (seeds.materialize + add_probe) the checker builds and plays."""

    def __init__(self, folder, machine, label):
        self.folder, self.machine, self.label = Path(folder), machine, label

    def logs(self):
        return self.folder / LOGS

    def mobile(self):
        """How the copy's game is held when it is a mobile game ("landscape", "portrait"), or None for a desktop game:
        the copy's own Platform.json, as the game had it at this commit (tools/validate-game.py read_platform)."""
        from . import tasks

        return tasks.validator().read_platform(self.folder)

    def _headless(self, what, timeout, log, *args):
        """One headless engine job on the copy, its log read whole: (Result, output and log)."""
        argv = [self.machine.editor, "--headless", "--path", self.folder, "--log-file", log, *args]
        found = self.machine.job(f"task-check {what} {self.label}", argv, self.folder, timeout)
        return found, (found.output + "\n" if found.output.strip() else "") + _read_text(log)

    def _build_once(self, timeout):
        """The import, then the scripts pass when the import passed: (exit code, output, seconds, waited, timed out,
        whether a script error was logged)."""
        logs = self.logs()
        _fresh(logs / ".gdignore").write_bytes(b"")  # the engine never imports what the checker keeps there
        found, output = self._headless("build", timeout, _fresh(logs / "build.log"), "--import")
        code, erred = found.exit_code, bool(re.search(SCRIPT_ERROR, output))
        seconds, waited, timed_out = found.seconds, found.waited, found.timed_out
        if code == 0 and not erred:
            asked = _fresh(logs / "scripts.gd")
            asked.write_text(SCRIPTS_PASS, encoding="utf-8")
            found, said = self._headless("scripts", timeout, _fresh(logs / "scripts.log"), "--script", asked)
            output += "\n" + said
            seconds, waited, timed_out = seconds + found.seconds, waited + found.waited, found.timed_out
            done = re.search(rf"^{SCRIPTS_DONE} (\d+)\s*$", said, re.M)
            erred = bool(re.search(rf"{LOAD_ERROR}|^{SCRIPT_FAILED} ", said, re.M)) or \
                (done is not None and done.group(1) != "0")
            code = found.exit_code
            if code == 0 and done is None:
                output += "\n[task-check] Godot exited 0 but the scripts pass didn't finish\n"
                code = 1
        if code == 0 and erred:
            code = 1  # the engine exits 0 from an import that logged a script error
        return code, output, seconds, waited, timed_out, erred

    def build(self, timeout):
        """The copy made ready to play: the import (the engine writes .godot/), then every script loaded. A Result; it
        passed when both jobs exited 0 and logged no script error (anything else has a non-zero exit code); `output`
        holds both logs. A failure with a word about the game, a script error in a log (read whole: the output keeps
        only its ends), comes back as it is. One with none is no evidence about the game (the engine stopped): it is
        tried once more, and says so in its output; stopped again, or stopped at its time limit (never tried again),
        its `stopped` says how, and no verdict rests on it (check.Side.build)."""
        retried, spent = "", (0.0, 0.0)
        while True:
            seeds.remove(self.folder / ".godot")  # a fresh import: never an older one's leftovers
            code, output, seconds, waited, timed_out, erred = self._build_once(timeout)
            cause = _cause(output) if code not in (0, None) else None
            silent = code != 0 and not erred
            if not silent or timed_out or retried:
                break
            retried = f"its first try stopped (exit {code}) with no script error"
            spent = (seconds, waited)
            print(f"  {self.label}: build stopped (exit {code}) with no script error, retry 1", file=sys.stderr,
                  flush=True)
        stopped = None
        if silent:
            stopped = (f"Godot was stopped at the build's time limit ({timeout} s) with no script error: a limit of "
                       "the run's own, no evidence about the game" if timed_out
                       else f"Godot stopped twice (exit {code}) with no script error: the engine or the machine, no "
                       "evidence about the game")
        head = f"[task-check] build retried once: {retried}\n" if retried else ""
        return Result(code, cut(head + output), round(seconds + spent[0], 3), timed_out,
                      round(waited + spent[1], 3), cause, stopped)

    def play(self, seconds, shots, timeout, scene=None, inputs=None, queries=None, args=(), every=None, player=None):
        """The game run from source for `seconds` of game time through the probe: on its own desktop, a frame of
        960x540 (a mobile game: the phone's size), a fixed 30 fps, `shots` screenshots, `inputs` sent at their times,
        `queries` (probes.query_file) sampled every `every` s, `scene` opened (None: the project's main scene),
        `player` (an object select, or None: the probe finds the player) as the player, `args` after the spec on the
        command line; a Played. The play starts from clean saved data (seeds.forget_saves)."""
        logs = self.logs()
        out = logs / "play"
        seeds.remove(out)  # what an earlier play wrote is never this one's
        out.mkdir(parents=True)
        log_path = _fresh(logs / "play.log")
        every = every or probes.EVERY
        mobile = self.mobile()
        spec = {"format": SPEC_FORMAT, "out": out.as_posix(), "size": list(MOBILE_SIZE[mobile] if mobile else SHOT_SIZE),
                "seconds": seconds, "shots": shots, "every": every, "fps": FPS, "scene": scene,
                "sound": probes.hears(queries),
                "player": player, "inputs": list(inputs or []),
                "queries": queries or {"format": probes.QUERIES_FORMAT, "every": every, "queries": []}}
        if mobile:  # a phone's play: <Keyboard>/escape is its back button (a desktop game's spec has no such key)
            spec["touch"] = True
        asked = _fresh(logs / SPEC)  # beside the play's folder, so it isn't one of the files the play wrote
        asked.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        seeds.forget_saves(self.folder)
        argv = [sys.executable, DESK, self.machine.editor, "--path", self.folder, "--log-file", log_path, *PLAY_FLAGS,
                *([scene] if scene else []), "--", "-taskProbe", asked, *args]
        found = self.machine.job(f"task-check play {self.label}", argv, self.folder, timeout, gpu=True)
        files = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()} if out.is_dir() else {}
        probe = None
        if "probe.json" in files:
            try:
                probe = json.loads(files["probe.json"].decode("utf-8-sig"))
            except ValueError:
                probe = None
        log = _read_text(log_path)
        shutil.rmtree(out, ignore_errors=True)
        # desk.py's own failure (no window station to make a desktop on, say), in its own words: the game's output
        # isn't read, so the line is never the game's. Read as a play that wrote no probe file, it failed the reference.
        said = re.search(r"^desk\.py: .*$", found.output or "", re.M)
        if said and found.exit_code not in (0, None) and "probe.json" not in files:
            raise NoDesktop(f"the game couldn't be started on a desktop of its own ({said.group(0).strip()}): the "
                            "machine's fault, no evidence about the game")
        return Played(found.exit_code, found.timed_out, found.output, found.seconds,
                      probe if isinstance(probe, dict) else None, log, files, found.waited)

    def read(self, relative):
        path = self.folder / relative
        return path.read_bytes() if path.is_file() else None
