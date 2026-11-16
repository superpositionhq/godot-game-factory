"""The task probe's tests on the real engine: play the small game in project/ with the probe, as the task checker
plays a game, and check what the probe wrote (README.md).

    python tools/task_check/probe_tests/run.py <work folder> [--godot EXE] [--rendered] [--desk] [--play NAME ...]
                                               [--once] [-v]

Without --rendered every play runs headless: everything but pixels. With it, the plays that need a drawn frame run in
a window, at a desktop game's size and at a portrait phone's."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADDON = HERE.parent / "task_probe"
DESK = HERE.parent / "desk.py"
SPEC_FORMAT = "godot-probe-play/1"
AUTOLOAD = 'TaskProbe="*res://addons/task_probe/task_probe.gd"'
PLAY_FLAGS = ["--fixed-fps", "30", "--disable-vsync", "--audio-driver", "Dummy"]
SCRIPT_ERROR = r"SCRIPT ERROR|Parse Error|Failed to load script"
SAVES = re.compile(r"^TaskProbe\.[0-9a-f]{12}$")
# how the game is set up for a run: its frame, and what its project.godot says of it
VARIANTS = {
    "desktop": {"size": [960, 540], "project": (1920, 1080), "renderer": "forward_plus"},
    "portrait": {"size": [1080, 1920], "project": (1080, 1920), "renderer": "mobile"},
}
TIMEOUT = 180

sys.path.insert(0, str(HERE))
import tests  # noqa: E402  (the plays and their checks)


def godot_exe(given):
    """The engine: --godot, else GODOT_EDITOR, else the machine's pinned one (machine/lib/ggfroot.py)."""
    if given or os.environ.get("GODOT_EDITOR"):
        return given or os.environ["GODOT_EDITOR"]
    sys.path.insert(0, str(HERE.parent.parent.parent / "machine" / "lib"))
    import ggfroot

    return str(ggfroot.godot_exe(console=True))


def saves_name(folder):
    """The user data folder of a copy, as the checker names it (seeds.saves_company)."""
    return "TaskProbe." + hashlib.sha256(os.path.abspath(str(folder)).lower().encode("utf-8")).hexdigest()[:12]


def saves_folder(name):
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / name
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / name


def prepare(work, variant):
    """A fresh copy of the game in <work>/<variant> with the probe added as the checker adds it: the addon as
    addons/task_probe/, its autoload first, a user data folder of the copy's own."""
    copy = work / variant
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(HERE / "project", copy)
    shutil.copytree(ADDON, copy / "addons" / "task_probe", ignore=shutil.ignore_patterns("*.uid", "*.import"))
    how = VARIANTS[variant]
    text = (copy / "project.godot").read_text(encoding="utf-8")
    text = text.replace("viewport_width=1920", f"viewport_width={how['project'][0]}")
    text = text.replace("viewport_height=1080", f"viewport_height={how['project'][1]}")
    text = text.replace('rendering_method="forward_plus"', f'rendering_method="{how["renderer"]}"')
    text = text.replace("[application]\n", f'[application]\n\nconfig/use_custom_user_dir=true\n'
                        f'config/custom_user_dir_name="{saves_name(copy)}"', 1)
    text = text.replace("[display]", f"[autoload]\n\n{AUTOLOAD}\n\n[display]", 1)
    (copy / "project.godot").write_text(text, encoding="utf-8", newline="\n")
    return copy


def run(argv, cwd, timeout=TIMEOUT):
    """(exit code or None when it ran out of time, output, seconds)."""
    start = time.monotonic()
    try:
        found = subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True, timeout=timeout)
        code, output = found.returncode, found.stdout + found.stderr
    except subprocess.TimeoutExpired as e:
        code, output = None, (e.stdout or b"") + (e.stderr or b"")
    return code, output.decode("utf-8", "replace"), time.monotonic() - start


def play(godot, copy, name, test, variant, rendered, desk):
    """One play of `copy`: the spec written, the game run, what it wrote read back."""
    logs = copy / "Logs" / "TaskProbe"
    out = logs / "play"
    if out.exists():
        shutil.rmtree(out)
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / "play.log"
    log.unlink(missing_ok=True)
    spec = json.loads((HERE / "plays" / f"{test.get('spec', name)}.json").read_text(encoding="utf-8"))
    queries = spec.pop("queries", [])
    spec = {"format": test.get("format", SPEC_FORMAT), "out": out.as_posix(), "size": VARIANTS[variant]["size"],
            "sound": any(q.get("kind") == "audio" for q in queries), "player": None, **spec,
            "queries": {"format": "game-probe-queries/1", "every": spec.get("every", 0.5), "queries": queries}}
    asked = logs / "play_spec.json"
    asked.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    argv = [godot, *([] if rendered else ["--headless"]), "--path", copy, "--log-file", log, *PLAY_FLAGS,
            *test.get("engine_args", [])]
    argv += ["--", *(["-taskProbe", asked] if test.get("flag", True) else []), *test.get("args", [])]
    if desk:
        argv = [sys.executable, DESK, *argv]
    code, output, seconds = run(argv, copy)
    files = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()} if out.is_dir() else {}
    probe = None
    if "probe.json" in files:
        probe = json.loads(files["probe.json"].decode("utf-8"))
    kept = copy / "Logs" / "ProbeTests" / name
    if kept.exists():
        shutil.rmtree(kept)
    kept.mkdir(parents=True)
    for file, data in files.items():
        (kept / file).write_bytes(data)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    (kept / "play.log").write_text(text + "\n" + output, encoding="utf-8")
    shutil.copy(asked, kept / "play_spec.json")
    return {"code": code, "output": output, "seconds": seconds, "probe": probe, "files": files, "log": text + output,
            "spec": spec, "size": VARIANTS[variant]["size"], "rendered": rendered, "out": out}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("work", type=Path, help="a scratch folder the run may fill and empty")
    parser.add_argument("--godot", help="the engine (default: GODOT_EDITOR, else the machine's pinned Godot)")
    parser.add_argument("--rendered", action="store_true", help="the plays that need a drawn frame, in a window")
    parser.add_argument("--desk", action="store_true", help="start each play on a Windows desktop of its own (desk.py)")
    parser.add_argument("--play", action="append", help="only these plays")
    parser.add_argument("--once", action="store_true", help="no second play of the plays that must read the same twice")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every check")
    args = parser.parse_args()
    godot = godot_exe(args.godot)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    print(f"probe tests in {work} (addon: {ADDON})")
    failed = 0
    for variant in (("desktop", "portrait") if args.rendered else ("desktop",)):
        copy = prepare(work, variant)
        code, output, seconds = run([godot, "--headless", "--path", copy, "--import"], copy)
        wrong = re.search(SCRIPT_ERROR, output)
        print(f"{'ok  ' if code == 0 and not wrong else 'FAIL'}  import ({variant})  {seconds:.0f} s")
        if code != 0 or wrong:
            print(output[-3000:])
            return 1
        for name, test in tests.PLAYS.items():
            if (args.play and name not in args.play) or bool(test.get("rendered")) != args.rendered:
                continue
            found = play(godot, copy, name, test, variant, args.rendered, args.desk)
            checks = tests.Checks()
            if found["code"] is None:
                checks.fail(f"the play ran out of time ({TIMEOUT} s)")
            test["check"](checks, found)
            same = ""
            if test.get("twice") and not args.once and found["probe"] is not None:
                again = play(godot, copy, name, test, variant, args.rendered, args.desk)
                same = "  same twice" if again["files"].get("probe.json") == found["files"].get("probe.json") else ""
                if not same:
                    checks.fail("a second play wrote another probe.json")
            bad = [c for c in checks.done if not c[0]]
            failed += len(bad)
            print(f"{'FAIL' if bad else 'PASS'}  {variant}.{name:<12} {len(checks.done)} checks"
                  f"{f', {len(bad)} failed' if bad else ''}{same}  {found['seconds']:.0f} s")
            for ok, what in checks.done:
                if not ok or args.verbose:
                    print(f"      {'ok  ' if ok else 'FAIL'} {what}")
        folder = saves_folder(saves_name(copy))
        if SAVES.match(folder.name) and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)  # what the plays saved outside the copy
    print("all passed" if not failed else f"{failed} check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
