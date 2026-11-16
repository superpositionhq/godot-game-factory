"""Godot creation replay: rebuild a game from its first commit by re-running what its builder ran.

  python godot_replay.py ledger  --game <game> [-v]                 windows, step runs, script texts -> work/ledger.json
  python godot_replay.py prepare --game ...                         isolated project at the first commit
  python godot_replay.py run     --game ... [--until <window>]      execute the plan (resumable; work/STOP pauses it)
  python godot_replay.py verify  --game ...                         final state vs the final commit (truth clone, dumps)
  python godot_replay.py status  --game ...
  python godot_replay.py package --game ... [--force]               <out>/_replay/<game>/<sha8>/ (READY when verified)
  python godot_replay.py release --game ... [--force]               ledger, prepare, run, verify, package
  python godot_replay.py clean   --game ... [--yes]                 free the disk of a packaged replay

See docs/godot-replay.md. Every engine process is headless and runs through <root>/tools/godot-heavy.ps1 when the
machine has it (machine root: machine/lib/ggfroot.py). --game is a game slug (<root>/games/<slug>), a game repo
folder, or a settings file (the repo's ReplayConfig.json, or a delivered ReplayScripts/game.json). A game without a
ReplayConfig.json replays with the defaults (DEFAULTS below, derived from the repo). Settings may use {root} (the
machine root) and {home} (the user profile).
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "machine", "lib"))

SETTINGS_FILE = "ReplayConfig.json"

# The settings a game gets when its repo has no ReplayConfig.json (the template's file holds the same values).
DEFAULTS = {
    "final": "HEAD",
    # an engine run that lasts longer is stopped and counted as failed (a step script that never quits)
    "run_timeout_s": 3600,
    # more file extensions the engine or a step writes (beside .import, .uid and the resource types of ledger.py)
    "content_ext": [],
}


def _ggfroot():
    try:
        import ggfroot
        return ggfroot
    except ImportError:   # a delivered ReplayScripts/ outside the tool checkout: env GGF_ROOT or ~/GodotWork
        return None


def machine_root():
    m = _ggfroot()
    r = m.root() if m else (os.environ.get("GGF_ROOT") or os.path.join(os.path.expanduser("~"), "GodotWork"))
    return r.replace("\\", "/")


def out_root():
    """Where packages go: env GGF_OUT, config "out", else <root>/deliverables (machine/lib/ggfroot.py out())."""
    m = _ggfroot()
    if m:
        return m.out().replace("\\", "/")
    return (os.environ.get("GGF_OUT") or machine_root() + "/deliverables").replace("\\", "/")


def godot_exe():
    """The engine: env GODOT_EDITOR, else the factory's pinned console exe (machine/lib/ggfroot.py godot_exe)."""
    exe = os.environ.get("GODOT_EDITOR")
    m = _ggfroot()
    if not exe and m:
        exe = m.godot_exe(console=True)
    if not exe or not os.path.isfile(exe):
        sys.exit("no Godot engine: set GODOT_EDITOR to the editor binary, or install the factory's engine "
                 "(machine/get-godot.ps1)")
    return exe.replace("\\", "/")


def check_free(path, what):
    """Stop before a disk-heavy step when the drive is below the free-space floor (env GGF_MIN_FREE_GB, default 50)."""
    m = _ggfroot()
    if m:
        return m.check_free(path, what)
    import shutil
    p = os.path.abspath(path)
    while not os.path.exists(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    free, floor = shutil.disk_usage(p).free / 2 ** 30, float(os.environ.get("GGF_MIN_FREE_GB") or 50)
    if free < floor:
        sys.exit("%s: only %.1f GB free (floor %.0f GB, GGF_MIN_FREE_GB)" % (what, free, floor))
    return free


def expand(v, root):
    """{root} and {home} expanded."""
    if isinstance(v, str):
        return v.replace("{root}", root).replace("{home}", os.path.expanduser("~").replace("\\", "/"))
    if isinstance(v, list):
        return [expand(x, root) for x in v]
    if isinstance(v, dict):
        return {k: expand(x, root) for k, x in v.items()}
    return v


# Packaged copies of recorded data (ReplayScripts: ledger, step texts, settings, reports) name the build machine's
# per-session folders; those names are noise for a reader and identify the session. They become neutral names.
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SESSION_PATH_RULES = [
    # Temp/<tool>/<project-dir>/<session uuid>[/scratch-pad] -> Temp/session[/scratch]
    ("session_temp", re.compile(r"(?i)(?P<head>AppData(?P<s>[\\/]{1,2})Local(?P=s)Temp(?P=s))[^\\/\s'\"]+(?P=s)"
                                r"[^\\/\s'\"]+(?P=s)(?:%s|[0-9a-f]{8}(?:-[0-9a-f]{0,12}){0,4}(?=[\"']|\\\"|$))"
                                r"(?P<pad>(?P=s)scratc[h]pad(?![\w-]))?" % _UUID),
     lambda m: m.group("head") + "session" + ((m.group("s") + "scratch") if m.group("pad") else "")),
    ("session_id", re.compile(r"\blocal[_]%s\b" % _UUID), lambda m: "session"),
]


def neutral_session_paths(text, session_ids=()):
    """(new text, {rule: count}) with the build machine's session folders and ids replaced, and the recording's own
    session ids wherever they still stand alone. Other uuids are content and stay."""
    counts = {}
    for rid, rx, f in SESSION_PATH_RULES:
        text, n = rx.subn(f, text)
        if n:
            counts[rid] = n
    if session_ids:
        rx = re.compile(r"(?i)\b(?:%s)\b" % "|".join(re.escape(s) for s in session_ids))
        text, n = rx.subn("session", text)
        if n:
            counts["session_uuid"] = n
    return text, counts


def recording_session_ids(cfg):
    """The session ids in a game's recording (actions.jsonl session_id): the ids neutral_session_paths replaces."""
    ids = set()
    p = os.path.join(cfg.get("recording", ""), "actions.jsonl")
    if os.path.isfile(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.search(r'"session_id"\s*:\s*"([^"]+)"', line)
                if m:
                    ids.add(m.group(1).lower())
    return sorted(i for i in ids if re.fullmatch(_UUID, i))


def under_root(path, root):
    """path written with {root} when it lies under the machine root, so settings name no machine path."""
    p, r = path.replace("\\", "/").rstrip("/"), root.replace("\\", "/").rstrip("/")
    return "{root}" + p[len(r):] if p.lower().startswith(r.lower() + "/") else p


def default_settings(repo):
    """The settings of a game repo that has no ReplayConfig.json: DEFAULTS, the slug from the folder name, the
    recording and work folders under the machine root."""
    root = machine_root()
    slug = os.path.basename(os.path.abspath(repo).rstrip("\\/"))
    raw = {"game": slug, "repo": under_root(os.path.abspath(repo), root), "recording": "{root}/.recording/" + slug,
           "work_root": "{root}/godot-replay/" + slug}
    raw.update({k: v for k, v in DEFAULTS.items() if k not in raw})
    return raw


def resolve_cfg(game):
    """(settings file or None, repo folder or None) for --game: a settings file (its "repo" names the repo); a repo
    folder or a slug under <root>/games (that folder is the repo, with its ReplayConfig.json if it has one, else the
    defaults)."""
    for cand in (game, os.path.join(HERE, game)):
        if os.path.isfile(cand):
            return os.path.abspath(cand), None
    repo = game if os.path.isdir(os.path.join(game, ".git")) else os.path.join(machine_root(), "games", game)
    if os.path.isdir(os.path.join(repo, ".git")):
        p = os.path.join(repo, SETTINGS_FILE)
        return (os.path.abspath(p) if os.path.isfile(p) else None), os.path.abspath(repo)
    raise SystemExit("no replay settings for %r: expected a game repo %s, a repo folder or a settings file" % (game, repo))


def load_cfg(game):
    path, repo = resolve_cfg(game)
    root = machine_root()
    if path:
        with open(path, encoding="utf-8-sig") as f:
            raw = json.load(f)
        raw = dict({k: v for k, v in DEFAULTS.items()}, **raw)   # a key the file leaves out takes its default
        if repo:
            # the repo given is the repo, whatever its settings file says: a copy of a game elsewhere carries the
            # game's ReplayConfig.json, whose "repo" names the original
            raw["repo"] = under_root(repo, root)
    else:
        raw = default_settings(repo)
    if repo and os.path.normcase(os.path.abspath(repo).rstrip("\\/")) != os.path.normcase(
            os.path.join(os.path.abspath(root), "games", os.path.basename(os.path.abspath(repo).rstrip("\\/")))):
        # a repo that is not this root's game of that name (a copy, a clone elsewhere): a work folder of its own, never
        # the game's (the settings it carries name the game's)
        import hashlib
        tag = hashlib.sha1(os.path.normcase(os.path.abspath(repo)).encode("utf-8")).hexdigest()[:8]
        raw["work_root"] = "{root}/godot-replay/_other/%s-%s" % (os.path.basename(os.path.abspath(repo).rstrip("\\/")), tag)
    if "repo" not in raw or "game" not in raw:
        here = os.path.dirname(path)
        raw.setdefault("game", os.path.basename(here))
        raw.setdefault("repo", under_root(here, root))
    raw.setdefault("recording", "{root}/.recording/" + raw["game"])
    raw.setdefault("work_root", "{root}/godot-replay/" + raw["game"])
    cfg = expand(raw, root)
    cfg["_raw"] = raw
    cfg["root"] = root
    cfg["_path"] = path
    w = cfg["work_root"]
    name = os.path.basename(os.path.abspath(cfg["repo"]).rstrip("\\/"))
    cfg.setdefault("project_dir", os.path.join(w, name))
    cfg.setdefault("truth_dir", os.path.join(w, "truth", name))
    cfg.setdefault("work_dir", os.path.join(w, "work"))
    return cfg   # nothing is created here: each command makes the folders it writes to


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def save_ledger(cfg, led, blobs):
    bd = os.path.join(cfg["work_dir"], "blobs")
    os.makedirs(bd, exist_ok=True)
    for h, b in blobs.items():
        p = os.path.join(bd, h)
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.write(b)
    write_json(os.path.join(cfg["work_dir"], "ledger.json"), led)


def cmd_ledger(cfg, a):
    import ledger
    led, blobs = ledger.build(cfg)
    save_ledger(cfg, led, blobs)
    print(json.dumps(led["counts"], indent=1))
    if a.verbose:
        for w in led["windows"][1:]:
            print("== %02d %s %s %s" % (w["index"], w["sha"][:7], w["time"][11:19], w["subject"][:70]))
            print("   inputs %d, generated %d, events %s, reconstruction %d/%d" % (
                len(w["inputs"]), len(w["content"]), w["events"],
                sum(1 for c in w["reconstruction"] if c["match"]), len(w["reconstruction"])))
            for s in w["shell"]:
                print("   delete", s["paths"], s["time"][11:19])
            for r in w["runs"]:
                print("   %s %s %-44s %-18s ec=%s unknown=%s" % (
                    r["id"], r["time"][11:19], r["script"][-44:], r["script_version"], r["exit_code"],
                    ",".join(os.path.basename(u) for u in r["unknown"])))


def cmd_release(cfg, a):
    """ledger, prepare, run, verify, package in one go. The verdict is metadata: a FAIL is packaged like a PASS
    (READY), with its report saying why."""
    import package
    import runner
    import verify
    final = runner.git(cfg["repo"], "rev-parse", cfg["final"]).strip()
    cfg = dict(cfg, final=final)
    cmd_ledger(cfg, a)
    runner.cmd_prepare(cfg, a)
    a.until = None
    code = runner.cmd_run(cfg, a)
    if code:
        raise SystemExit("release: the replay did not reach %s (paused or stopped): see %s" % (final[:8], cfg["work_dir"]))
    v = verify.cmd_verify(cfg, a)
    print("release: verification %s; packaging ReplayScripts/ with its report" % ("PASS" if v == 0 else "FAIL"))
    return package.cmd_package(cfg, a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command")
    ap.add_argument("--game", required=True)
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--until", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_cfg(a.game)
    fn = globals().get("cmd_" + a.command)
    if fn is None:
        import importlib
        for mod in ("runner", "verify", "package"):
            fn = getattr(importlib.import_module(mod), "cmd_" + a.command, None)
            if fn:
                break
    if fn is None:
        ap.error("unknown command " + a.command)
    # disk-heavy steps refuse to start on a nearly full drive (a disk that filled mid-run corrupts a replay)
    if a.command in ("prepare", "run", "verify", "release"):
        check_free(cfg["work_root"], "godot_replay " + a.command)
    elif a.command == "package":
        check_free(out_root(), "godot_replay package")
    return fn(cfg, a)


if __name__ == "__main__":
    sys.exit(main() or 0)
