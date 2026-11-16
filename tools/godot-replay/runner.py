"""prepare / run / status for the Godot creation replay (see docs/godot-replay.md).

The replay project is a private clone of the game repo (objects shared, Git LFS reading the game's own store), checked
out at the first commit. `run` walks the ledger's windows: the inputs from the commit, the engine's import, every
recorded step run headless with the step script as it stood then, the files a recorded shell command took away, then
the boundary: the uid:// identities of what the replay generated are given the commit's (identity, never content),
every generated file is compared with the commit's, and one no replayed step produced is taken from the commit and
listed. Resumable: work/state.json; a work/STOP file pauses it cleanly between steps.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import godot_replay

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP_SCRIPT = os.path.join(HERE, "engine", "replay_dump.gd")
SKIP_DIRS = (".git", ".godot")   # never scanned: git's own folder and the engine's import cache
NON_GAME = ("Docs/", "Dataset/", "Brief/", "Scripts/")   # folders with .gdignore: the engine never reads them
SCRIPT_ERROR = re.compile(r"SCRIPT ERROR|Parse Error|Failed to load script")
UID = re.compile(rb"uid://[a-z0-9]+")
UID_IMPORT = re.compile(rb'^uid="(uid://[a-z0-9]+)"', re.M)
UID_HEADER = re.compile(rb'^\[gd_(?:scene|resource)[^\]\n]*\buid="(uid://[a-z0-9]+)"')


def heavy_path():
    return os.path.join(godot_replay.machine_root(), "tools", "godot-heavy.ps1")


# ------------------------------------------------------------------------------------------------ helpers
def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def jdump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def jappend(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def jload(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def jlines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def git(repo, *args, check=True, binary=False, env=None, inp=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", "-c", "core.autocrlf=false"] + list(args),
                       capture_output=True, env=e, input=inp)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args[:3]), r.stderr.decode("utf-8", "replace")[-800:]))
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def ps_quote(s):
    # PowerShell reads the typographic quotes as quotes too: each is doubled
    return "'" + re.sub("(['\\u2018\\u2019\\u201a\\u201b])", r"\1\1", str(s)) + "'"


def _kill_tree(p):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False)
    else:
        p.kill()


def heavy(label, argv, log_path, cwd=None, timeout=None):
    """Run one engine process through <root>/tools/godot-heavy.ps1 (the machine-wide slots; a general slot, the engine
    is headless), or directly on a machine without it. Its output goes to log_path. Returns (exit code or None when
    stopped at `timeout` seconds, seconds)."""
    script = heavy_path()
    if os.path.isfile(script):
        cmd = ("& %s -Label %s -- %s; if ($null -eq $LASTEXITCODE) { exit 1 }; exit $LASTEXITCODE"
               % (ps_quote(script), ps_quote(label), " ".join(ps_quote(a) for a in argv)))
        full = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd]
    else:
        full = list(argv)
    t0 = time.time()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "wb") as out:
        p = subprocess.Popen(full, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=cwd,
                             creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(p)
            p.wait()
            code = None
        except BaseException:
            _kill_tree(p)   # an interrupted replay leaves no engine behind on the project
            p.wait()
            raise
    return code, round(time.time() - t0, 1)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1_file(p):
    with open(p, "rb") as f:
        data = f.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def scan(root):
    """{repo path: (size, mtime_ns)} of every file of the project (not .git/, not .godot/)."""
    out = {}
    for dp, dns, files in os.walk(root):
        if dp == root:
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in files:
            fp = os.path.join(dp, fn)
            st = os.stat(fp)
            out[os.path.relpath(fp, root).replace("\\", "/")] = (st.st_size, st.st_mtime_ns)
    return out


def diff_scan(a, b):
    added = sorted(p for p in b if p not in a)
    deleted = sorted(p for p in a if p not in b)
    changed = sorted(p for p in b if p in a and a[p] != b[p])
    return added, changed, deleted


LFS_PTR = re.compile(rb"version https://git-lfs.github.com/spec/v1\r?\noid sha256:([0-9a-f]{64})\r?\nsize (\d+)")


def tree_ids(repo, sha):
    """{path: ('lfs', sha256) | ('git', sha1)} for files of a commit (LFS pointers resolved to their oid)."""
    out = {}
    small = []
    for line in git(repo, "ls-tree", "-r", "-l", sha).splitlines():
        meta, path = line.split("\t", 1)
        mode, typ, oid, size = meta.split()
        if typ != "blob":
            continue
        out[path] = ("git", oid)
        if size != "-" and int(size) < 300:
            small.append((path, oid))
    if small:
        data = git(repo, "cat-file", "--batch", inp="\n".join(o for _, o in small).encode() + b"\n", binary=True)
        pos = 0
        for path, oid in small:
            nl = data.index(b"\n", pos)
            n = int(data[pos:nl].split()[2])
            body = data[nl + 1:nl + 1 + n]
            pos = nl + 1 + n + 1
            m = LFS_PTR.match(body)
            if m:
                out[path] = ("lfs", m.group(1).decode())
    return out


def file_matches(fp, ident):
    if not os.path.exists(fp):
        return False
    kind, oid = ident
    return (sha256_file(fp) if kind == "lfs" else git_blob_sha1_file(fp)) == oid


def untracked(proj, ids):
    """(extra, ignored): the project's files the commit does not have, split by the repo's own ignore rules."""
    extra = sorted(p for p in scan(proj) if p not in ids)
    ignored = set()
    if extra:
        out = git(proj, "check-ignore", "--stdin", inp=("\n".join(extra) + "\n").encode("utf-8"), check=False)
        ignored = set(l.strip().strip('"') for l in out.splitlines() if l.strip())
    return [p for p in extra if p not in ignored], sorted(ignored)


# ------------------------------------------------------------------------------------------------ paths
class Ctx:
    def __init__(self, cfg):
        self.cfg = cfg
        self.repo = cfg["repo"]
        self.proj = cfg["project_dir"]
        self.work = cfg["work_dir"]
        self.ledger = jload(os.path.join(self.work, "ledger.json"))
        self.state_path = os.path.join(self.work, "state.json")
        self.state = jload(self.state_path, {"window": 0, "done": [], "provenance": {}, "window_outputs": [], "commits": []})
        self.logs = os.path.join(self.work, "logs")
        self._exe = None

    @property
    def exe(self):
        if not self._exe:
            self._exe = godot_replay.godot_exe()
        return self._exe

    def save(self):
        jdump(self.state_path, self.state)

    def p(self, rel):
        return os.path.join(self.proj, rel)


# ------------------------------------------------------------------------------------------------ prepare
def clone_at(cfg, dest, sha):
    if os.path.exists(os.path.join(dest, ".git")):
        return False
    repo = cfg["repo"]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", repo, dest], check=True)
    for k, v in (("core.autocrlf", "false"), ("core.eol", "lf"), ("lfs.storage", repo.replace("\\", "/") + "/.git/lfs"),
                 ("lfs.fetchrecentalways", "false"), ("remote.origin.url", repo.replace("\\", "/"))):
        git(dest, "config", k, v)
    git(dest, "checkout", "-q", "--detach", sha, env={"GIT_LFS_SKIP_SMUDGE": "1"})
    fix_lfs_pointers_at(dest, ["."])
    return True


def sync_truth(cfg, sha):
    """The truth project (a shared clone of the game repo) at sha; True when it was cloned now."""
    t = cfg["truth_dir"]
    if clone_at(cfg, t, sha):
        return True
    if git(t, "rev-parse", "HEAD").strip() != sha:
        git(t, "checkout", "-q", "-f", "--detach", sha, env={"GIT_LFS_SKIP_SMUDGE": "1"})
        git(t, "clean", "-fdq")
        fix_lfs_pointers_at(t, ["."])
    return False


def cmd_prepare(cfg, a):
    ctx = Ctx(cfg)
    if ctx.ledger is None:
        sys.exit("run `ledger` first")
    first = ctx.ledger["first"]
    t0 = time.time()
    made = clone_at(cfg, ctx.proj, first)
    st = git(ctx.proj, "status", "--short")
    print("project %s at %s (%s, %.0f s); status: %s" % (ctx.proj, first[:10], "cloned" if made else "exists",
                                                          time.time() - t0, st.strip() or "clean"))
    if made or not ctx.state.get("commits"):
        ctx.state = {"window": 0, "done": [], "provenance": {}, "window_outputs": [], "commits": [first]}
        ctx.save()


# ------------------------------------------------------------------------------------------------ LFS, inputs
def fix_lfs_pointers_at(proj, paths, store=None):
    """Files a checkout left as Git LFS pointer text, replaced by the object from the game's LFS store (the clone's
    lfs.storage). Also happens when an earlier commit's .gitattributes does not yet mark an extension as LFS."""
    n = 0
    for rel in paths:
        root = os.path.join(proj, rel)
        files = [root] if os.path.isfile(root) else [os.path.join(dp, f) for dp, dns, fs in os.walk(root)
                                                      for f in fs if ".git" not in dp.replace("\\", "/").split("/")]
        for fp in files:
            try:
                if os.path.getsize(fp) > 1024:
                    continue
                with open(fp, "rb") as f:
                    m = LFS_PTR.match(f.read())
            except OSError:
                continue
            if not m:
                continue
            if store is None:
                store = (git(proj, "config", "--get", "lfs.storage", check=False).strip() or os.path.join(proj, ".git", "lfs"))
            oid = m.group(1).decode()
            obj = os.path.join(store, "objects", oid[:2], oid[2:4], oid)
            if not os.path.exists(obj):
                sys.exit("LFS object %s for %s is not in %s" % (oid, fp, store))
            shutil.copyfile(obj, fp)
            n += 1
    return n


def checkout_paths(ctx, sha, paths):
    """Files as commit sha has them (LFS objects from the game's store)."""
    for k in range(0, len(paths), 500):
        part = paths[k:k + 500]
        git(ctx.proj, "checkout", sha, "--pathspec-from-file=-", inp="\n".join(part).encode("utf-8"),
            env={"GIT_LFS_SKIP_SMUDGE": "1"})
        fix_lfs_pointers_at(ctx.proj, part)


def apply_inputs(ctx, w):
    """Files the builder writes as the commit has them (adds/modifies via checkout, deletes removed). Generated
    files (w["content"]) are left to the engine and the steps."""
    am = [x["path"] for x in w["inputs"] if x["status"] in "AMT"]
    dl = [x["path"] for x in w["inputs"] if x["status"] == "D"]
    if am:
        checkout_paths(ctx, w["sha"], am)
    for p in dl:
        fp = ctx.p(p)
        if os.path.exists(fp):
            os.remove(fp)
    return len(am), len(dl)


def needs_import(ctx, w):
    """True when the window changes anything the engine reads, or the project was never imported."""
    if not os.path.isdir(ctx.p(".godot")):
        return True
    return any(not x["path"].startswith(NON_GAME) and ("/" in x["path"] or x["path"] == "project.godot")
               for x in w["inputs"] + w["content"])


def materialize_code(ctx, run, w):
    """Step scripts as they stood when the run started (ledger texts); absent ones removed; unknown ones keep the
    commit's text (left alone they kept whatever an earlier run of the window had)."""
    n = 0
    for p, h in (run.get("texts") or {}).items():
        with open(os.path.join(ctx.work, "blobs", h), "rb") as f:
            data = f.read()
        fp = ctx.p(p)
        cur = None
        if os.path.exists(fp):
            with open(fp, "rb") as f:
                cur = f.read()
        if cur != data:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as f:
                f.write(data)
            n += 1
    for p in run.get("absent") or []:
        if os.path.exists(ctx.p(p)):
            os.remove(ctx.p(p))
            n += 1
    if run.get("unknown"):
        put_commit_files(ctx, w["sha"], run["unknown"])
        n += len(run["unknown"])
    return n


def put_commit_files(ctx, sha, paths):
    """Files back to commit sha (the ones it has) and removed where it has none."""
    in_tree = set(git(ctx.proj, "ls-tree", "-r", "--name-only", sha).splitlines())
    have = [p for p in paths if p in in_tree]
    if have:
        checkout_paths(ctx, sha, have)
    for p in paths:
        if p not in in_tree and os.path.exists(ctx.p(p)):
            os.remove(ctx.p(p))


# ------------------------------------------------------------------------------------------------ engine runs
def engine(ctx, project, label, args, log, timeout=None):
    """One headless engine process on a project. Returns (exit code or None at the time limit, seconds)."""
    argv = [ctx.exe, "--headless", "--path", project.replace("\\", "/")] + list(args)
    return heavy("%s replay %s" % (ctx.cfg["game"], label), argv, log, cwd=project,
                 timeout=timeout or ctx.cfg.get("run_timeout_s") or None)


def log_text(log):
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def import_project(ctx, project, label):
    """`godot --headless --import`: the engine writes .godot/ and the .import and .uid sidecars it finds missing."""
    log = os.path.join(ctx.logs, label + ".log")
    code, secs = engine(ctx, project, label, ["--import"], log)
    return {"exit_code": code, "seconds": secs, "log": os.path.relpath(log, ctx.work).replace("\\", "/"),
            "script_errors": bool(SCRIPT_ERROR.search(log_text(log)))}


def run_step(ctx, run):
    """One recorded step run, headless: `--script res://<script>`, as Scripts/godot.ps1 step runs it."""
    log = os.path.join(ctx.logs, "runs", "%s_%s.log" % (run["id"], os.path.splitext(os.path.basename(run["script"]))[0]))
    code, secs = engine(ctx, ctx.proj, "%s %s" % (run["id"], os.path.basename(run["script"])),
                        ["--script", "res://" + run["script"]], log)
    return code, secs, log


def dump(ctx, project, out, label):
    """Structure dump (engine/replay_dump.gd) of a project into out/dump.json. Returns (exit code, seconds, file)."""
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    dest = os.path.join(out, "dump.json")
    code, secs = engine(ctx, project, label, ["--script", DUMP_SCRIPT.replace("\\", "/"), "--", dest.replace("\\", "/")],
                        os.path.join(ctx.logs, label + ".log"))
    return code, secs, dest


def delete_paths(ctx, step, tree):
    """Files and folders a recorded shell command deleted or moved away, removed from the replay's own files. Paths
    the window's commit has are left: they are the commit's at the boundary."""
    n = 0
    root = os.path.normcase(os.path.normpath(ctx.proj)) + os.sep
    for rel in step["paths"]:
        rel = rel.strip("/")
        p = os.path.normpath(ctx.p(rel))
        if not os.path.normcase(p).startswith(root) or rel.split("/")[0] == ".git":
            continue
        if rel in tree or any(t.startswith(rel + "/") for t in tree):
            continue
        if os.path.isdir(p):
            shutil.rmtree(p)
            n += 1
        elif os.path.exists(p):
            os.remove(p)
            n += 1
    return n


def note_outputs(ctx, before, after, tag):
    added, changed, deleted = diff_scan(before, after)
    prov = ctx.state["provenance"]
    outs = ctx.state.setdefault("window_outputs", [])
    for p in added + changed:
        prov[p] = tag
        if p not in outs:
            outs.append(p)
    for p in deleted:
        prov.pop(p, None)
    return {"added": added, "changed": changed, "deleted": deleted}


# ------------------------------------------------------------------------------------------------ boundary
def file_uid(path, data):
    """The uid:// identity a generated file carries: a .uid file's text, a .import file's uid line, the uid in a text
    scene's or resource's header. None when it has none."""
    data = data or b""
    if path.endswith(".uid"):
        m = UID.fullmatch(data.strip())
        return m.group(0) if m else None
    m = (UID_IMPORT if path.endswith(".import") else UID_HEADER).search(data)
    return m.group(1) if m else None


def adopt_identity(ctx, w, ids):
    """The uid:// identities of the files the replay generated in this window (the engine makes a random one on every
    machine) become the ones the commit has at the same paths, in those files and in every other file the window
    generated that refers to them. Identity, never content. Returns {replay uid: commit uid}."""
    outs = [p for p in ctx.state.get("window_outputs") or [] if os.path.isfile(ctx.p(p))]
    mapping = {}
    for p in outs:
        if p not in ids or ids[p][0] != "git" or os.path.getsize(ctx.p(p)) > 4 << 20:
            continue
        with open(ctx.p(p), "rb") as f:
            have = file_uid(p, f.read())
        if not have:
            continue
        want = file_uid(p, git(ctx.proj, "show", "%s:%s" % (w["sha"], p), binary=True, check=False))
        if want and want != have:
            mapping[have] = want
    if not mapping:
        return {}
    rx = re.compile(b"(%s)(?![a-z0-9])" % b"|".join(re.escape(k) for k in mapping))
    for p in outs:
        fp = ctx.p(p)
        if os.path.getsize(fp) > 64 << 20:
            continue
        with open(fp, "rb") as f:
            data = f.read()
        if b"\0" in data[:8000]:
            continue   # binary
        new = rx.sub(lambda m: mapping[m.group(1)], data)
        if new != data:
            with open(fp, "wb") as f:
                f.write(new)
    return {k.decode(): v.decode() for k, v in mapping.items()}


def boundary(ctx, w):
    """Window check against the commit: the builder's files back to the commit, identity adopted, every generated
    file identical, differing (kept as the replay made it) or taken from the commit when no step of the window
    produced it."""
    prov = ctx.state["provenance"]
    outs = set(ctx.state.get("window_outputs") or [])
    by_run = set(p for p in outs if str(prov.get(p, "")).startswith("run:"))
    res = {"fallback": [], "exact": [], "differs": [], "adopted_uids": 0}
    # a file a step of this window wrote and the recording shows no write of is generated, whatever its kind
    generated = list(w["content"]) + [dict(x, kind="step output") for x in w["inputs"]
                                      if x["status"] in "AMT" and x["path"] in by_run and not x.get("written")]
    gen_paths = set(x["path"] for x in generated)
    back = [x["path"] for x in w["inputs"] if x["path"] not in gen_paths]
    for r in w["runs"]:
        back += [p for p in list(r.get("texts") or {}) + list(r.get("absent") or []) + list(r.get("unknown") or [])
                 if p not in back and p not in gen_paths]
    if back:
        put_commit_files(ctx, w["sha"], back)
    ids = tree_ids(ctx.proj, w["sha"])
    res["adopted_uids"] = len(adopt_identity(ctx, w, ids))
    for x in generated:
        p = x["path"]
        fp = ctx.p(p)
        src = prov.get(p, "")
        if os.path.exists(fp) and p in outs and file_matches(fp, ids[p]):
            res["exact"].append({"path": p, "by": src})
        elif os.path.exists(fp) and p in outs:
            res["differs"].append({"path": p, "by": src})
        else:
            checkout_paths(ctx, w["sha"], [p])
            prov[p] = "fallback:" + w["sha"][:10]
            res["fallback"].append({"path": p, "reason": "no step of the window produced it and the recording shows "
                                                       "no write of it (%s)" % x.get("kind", "generated")})
    have = scan(ctx.proj)
    res["missing"] = sorted(p for p in ids if p not in have)
    res["extra"] = untracked(ctx.proj, ids)[0]
    ctx.state["window_outputs"] = []
    return res


# ------------------------------------------------------------------------------------------------ run
def cmd_run(cfg, a):
    ctx = Ctx(cfg)
    led = ctx.ledger
    if led is None or not os.path.isdir(os.path.join(ctx.proj, ".git")):
        sys.exit("run `ledger` and `prepare` first")
    wins = led["windows"]
    done_shas = ctx.state.get("commits") or []
    if done_shas != [w["sha"] for w in wins[:len(done_shas)]]:
        sys.exit("the game's history is not the one already replayed (an amend or a rebase): remove %s and replay again"
                 % cfg["work_root"])
    last = a.until if getattr(a, "until", None) is not None else len(wins) - 1
    runs_log = os.path.join(ctx.work, "runs.jsonl")
    win_log = os.path.join(ctx.work, "windows.jsonl")
    for i in range(ctx.state["window"] + 1, last + 1):
        w = wins[i]
        t_w = time.time()
        print("== window %02d %s %s" % (i, w["sha"][:7], w["subject"][:70]), flush=True)

        def once(sid, fn):
            if sid not in ctx.state["done"]:
                fn()
                ctx.state["done"].append(sid)
                ctx.save()

        def do_inputs():
            n_am, n_d = apply_inputs(ctx, w)
            print("   inputs: %d written, %d deleted; %d generated file(s) left to the engine and the steps"
                  % (n_am, n_d, len(w["content"])), flush=True)

        def do_import(sid):
            before = scan(ctx.proj)
            rec = import_project(ctx, ctx.proj, sid)
            outs = note_outputs(ctx, before, scan(ctx.proj), "import:" + sid)
            jappend(runs_log, dict(rec, window=i, commit=w["sha"], kind="import", step=sid, time=now(),
                                   timed_out=rec["exit_code"] is None, outputs=outs))
            print("   import: exit %s %4.0f s  +%d ~%d -%d%s" % (rec["exit_code"], rec["seconds"], len(outs["added"]),
                  len(outs["changed"]), len(outs["deleted"]), "  script errors in the log" if rec["script_errors"] else ""), flush=True)

        once("w%02d.inputs" % i, do_inputs)
        if needs_import(ctx, w):
            once("w%02d.import" % i, lambda: do_import("w%02d.import" % i))
        # order of the recorded tool calls (each call's end time), then position inside the call
        steps = [("run", (r["time"], r.get("pos", -1), k), r) for k, r in enumerate(w["runs"])] + \
                [("shell", (s["time"], s.get("pos", -1), 0), s) for s in w["shell"]]
        steps.sort(key=lambda s: s[1])
        tree = None
        for kind, t, s in steps:
            sid = "w%02d.%s.%s" % (i, kind, s["id"])
            if sid in ctx.state["done"]:
                continue
            # Clean pause between steps (no engine running): create work/STOP; delete it and run again to resume.
            if os.path.exists(os.path.join(ctx.work, "STOP")):
                print("   STOP file found: paused before %s (state saved; delete work/STOP and run again to resume)" % sid, flush=True)
                return 3
            rec = {"window": i, "commit": w["sha"], "kind": kind, "step": sid, "time_original": t[0], "start": now()}
            before = scan(ctx.proj)
            if kind == "shell":
                if tree is None:
                    tree = set(git(ctx.proj, "ls-tree", "-r", "--name-only", w["sha"]).splitlines())
                rec["paths"] = s["paths"]
                rec["files"] = delete_paths(ctx, s, tree)
                note_outputs(ctx, before, scan(ctx.proj), "shell:" + sid)
            else:
                r = s
                rec.update({"run": r["id"], "script": r["script"], "exit_code_original": r.get("exit_code"),
                            "version": r["script_version"], "materialized": materialize_code(ctx, r, w)})
                before = scan(ctx.proj)   # the step script as it stood then is an input, not an output of the run
                code, secs, log = run_step(ctx, r)
                outs = note_outputs(ctx, before, scan(ctx.proj), "run:" + r["id"])
                rec.update({"exit_code": code, "timed_out": code is None, "seconds": secs,
                            "log": os.path.relpath(log, ctx.work).replace("\\", "/"),
                            "script_errors": bool(SCRIPT_ERROR.search(log_text(log))), "outputs": outs})
                print("   %s %-40s exit %s (orig %s) %5.0f s  +%d ~%d -%d" % (
                    r["id"], r["script"][-40:], code, r.get("exit_code"), secs,
                    len(outs["added"]), len(outs["changed"]), len(outs["deleted"])), flush=True)
            rec["end"] = now()
            jappend(runs_log, rec)
            ctx.state["done"].append(sid)
            ctx.save()
        # what the steps wrote gets its sidecars from the engine, as it did for the builder
        if any(str(ctx.state["provenance"].get(p, "")).startswith("run:") for p in ctx.state.get("window_outputs") or []):
            once("w%02d.import2" % i, lambda: do_import("w%02d.import2" % i))
        res = boundary(ctx, w)
        summ = {"window": i, "commit": w["sha"], "subject": w["subject"], "time": now(), "seconds": round(time.time() - t_w, 1),
                "runs": len(w["runs"]), "reconstruction": {"checks": len(w["reconstruction"]),
                                                           "match": sum(1 for c in w["reconstruction"] if c["match"])},
                "content": {k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}, "detail": res}
        jappend(win_log, summ)
        print("   boundary: generated %s" % json.dumps(summ["content"]), flush=True)
        ctx.state["window"] = i
        ctx.state["commits"] = [x["sha"] for x in wins[:i + 1]]
        ctx.state["done"] = []
        ctx.save()
    return 0


def cmd_status(cfg, a):
    ctx = Ctx(cfg)
    print(json.dumps({k: v for k, v in ctx.state.items() if k not in ("provenance", "window_outputs", "commits")}, indent=1))
    kinds = {}
    for v in ctx.state.get("provenance", {}).values():
        k = v.split(":")[0]
        kinds[k] = kinds.get(k, 0) + 1
    print("provenance:", kinds)
