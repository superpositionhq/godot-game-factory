"""Ledger: what the builder of a game ran, window by window, from three records.

  git history          the commits on the first-parent chain up to the final commit (the windows' boundaries)
  actions.jsonl        the agent's tool calls: step runs (command lines), Write/Edit of files, apply_patch,
                       Antigravity's own tools (as_claude), shell commands
  workflow.jsonl       the row each step run logged (source.script, source.sha256) at the final commit

Output (work/ledger.json, schema godot-replay.ledger/v1):
  windows[]   one per commit: sha, parent, time, subject, inputs (files the builder writes: everything the recording
              shows written, and every file that is not of a generated kind), content (generated files: .import and
              .uid sidecars and engine resources the commit adds or changes without a recorded write), runs[] (step
              runs in order, each with the text of every step script the window changes as it stood when the run
              started), shell[] (files a recorded shell command deleted or moved away), reconstruction checks at the
              boundary
  blobs       sha256 -> file text, stored by the caller in work/blobs/
"""
import collections
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess

import patchfx
import shellfx

SCHEMA = "godot-replay.ledger/v1"

# What the engine writes beside a file it imports or scans.
SIDECAR_EXT = (".import", ".uid")
# Engine resources: a step saves them (ResourceSaver), a session writes them as text with its file tools.
RESOURCE_EXT = (".tscn", ".tres", ".scn", ".res", ".mesh", ".material", ".anim", ".theme", ".fontdata", ".multimesh",
                ".occ", ".lmbake")
TEXT_EXT = SIDECAR_EXT + (".tscn", ".tres", ".gd", ".gdshader", ".gdshaderinc", ".godot", ".cfg", ".json", ".md",
                          ".txt", ".ps1", ".psm1", ".py", ".sh", ".bat", ".cmd", ".csv", ".tsv", ".xml", ".yaml",
                          ".yml", ".svg", ".gitignore", ".gitattributes", ".gdignore")
STEPS_DIR = "steps/"


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def git(repo, *args, binary=False):
    out = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off"] + list(args), capture_output=True, check=True)
    return out.stdout if binary else out.stdout.decode("utf-8")


def parse_time(s):
    return datetime.datetime.fromisoformat(s)


def norm_text(b):
    """Text as stored in git (LF); texts are compared and replayed with LF line ends."""
    return b.replace(b"\r\n", b"\n")


def generated_kind(path, extra_ext=()):
    """'sidecar' for what the engine writes beside a file (.import, .uid), 'resource' for an engine resource (a step
    may have saved it), None for every other file."""
    p = path.lower()
    if p.endswith(SIDECAR_EXT):
        return "sidecar"
    if p.endswith(RESOURCE_EXT + tuple(e.lower() for e in extra_ext)):
        return "resource"
    return None


def is_code(path):
    """Step scripts: a run's script is the text it had when the run started."""
    return path.startswith(STEPS_DIR) and path.lower().endswith(".gd")


# ----------------------------------------------------------------------------------------------- commits
def first_parent_chain(repo, final, recorded=None):
    """The commits up to final, oldest first. "time" is the commit's own time (whole seconds); "order", what the
    recorded tool calls are compared with, is the moment the post-commit recorder wrote the commit (commits.jsonl
    recorded_at, milliseconds, just after the commit), else the end of the commit's second: a call recorded in the same
    second as the commit that followed it was taken for one made after it."""
    rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H%x09%P%x09%cI%x09%s", final).splitlines()
    out = []
    for r in rows:
        sha, parents, ctime, subject = r.split("\t", 3)
        order = (recorded or {}).get(sha)
        if not order or not (parse_time(ctime) <= parse_time(order) <= parse_time(ctime) + datetime.timedelta(minutes=10)):
            order = (parse_time(ctime) + datetime.timedelta(milliseconds=999)).isoformat(timespec="milliseconds")
        out.append({"sha": sha, "parents": parents.split(), "time": ctime, "order": order, "subject": subject})
    return out


def recorded_commits(recording):
    """sha -> recorded_at of the post-commit recorder's rows (commits.jsonl)."""
    out = {}
    p = os.path.join(recording, "commits.jsonl")
    if os.path.isfile(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("sha") and r.get("recorded_at"):
                    out.setdefault(r["sha"], r["recorded_at"])
    return out


def changed_paths(repo, parent, sha):
    """[(status, path)] of sha against its first parent (renames as delete + add)."""
    if parent is None:
        names = git(repo, "ls-tree", "-r", "--name-only", sha).splitlines()
        return [("A", p) for p in names]
    out = []
    for line in git(repo, "diff", "--no-renames", "--name-status", parent, sha).splitlines():
        st, p = line.split("\t", 1)
        out.append((st[0], p))
    return out


def blob_at(repo, sha, path):
    try:
        return git(repo, "show", "%s:%s" % (sha, path), binary=True)
    except subprocess.CalledProcessError:
        return None


# ----------------------------------------------------------------------------------------------- actions
# "exit code N (S s)": the last line Scripts/godot.ps1 prints
EXIT_RE = re.compile(r"(?<!: )exit code (-?\d+)(?: \((\d+) s\))?")
ROW_RE = re.compile(r"\[workflow\] ([A-Za-z0-9]+-\d+) ")
STEP_CALL = re.compile(r"(?i)godot\.ps1")

# a shell command that exited non-zero still ran: its file edits and step runs happened
RAN_EVENTS = ("PostToolUse", "PostToolUseFailure")
SHELL_TOOLS = ("Bash", "PowerShell")


def _param_expand(val, op, pat):
    """${v%%pat} ${v%pat} ${v##pat} ${v#pat} with glob patterns."""
    n = len(val)
    if op == "%%":
        return next((val[:i] for i in range(0, n + 1) if fnmatch.fnmatchcase(val[i:], pat)), val)
    if op == "%":
        return next((val[:i] for i in range(n, -1, -1) if fnmatch.fnmatchcase(val[i:], pat)), val)
    if op == "##":
        return next((val[i:] for i in range(n, -1, -1) if fnmatch.fnmatchcase(val[:i], pat)), val)
    return next((val[i:] for i in range(0, n + 1) if fnmatch.fnmatchcase(val[:i], pat)), val)


def subst_var(text, var, val):
    v = re.escape(var)
    text = re.sub(r"\$\{" + v + r"(%%|%|##|#)([^}]*)\}", lambda m: _param_expand(val, m.group(1), m.group(2)), text)
    return re.sub(r"\$(?:\{" + v + r"\}|" + v + r"\b)", lambda m: val, text)


def expand_loops(cmd):
    """`for v in a "b c" d; do ... $v ...; done` (one line or several) or PowerShell `foreach ($v in "a", "b") { ... }`
    around step runs: [(command text with one value, lo, hi, posmap)], one per value. Copy k > 0 repeats the text
    around the loop: only its loop body counts (lo..hi), so runs outside the loop are not found twice. posmap maps a
    position back to the original command (iteration k's body inside the loop's span, in iteration order)."""
    m = re.search(r"\bfor (\w+) in ([^;\n]+?)\s*(?:;|\n)\s*do\b(.*?)(?:;|\n)\s*done\b", cmd, re.S)
    if m:
        try:
            values = shlex.split(m.group(2), posix=True)
        except ValueError:
            values = m.group(2).split()
    else:
        m = re.search(r"\bforeach\s*\(\s*\$(\w+)\s+in\s+([^)]+)\)\s*\{(.*?)\}", cmd, re.S | re.I)
        if not m:
            return [(cmd, 0, len(cmd), lambda p: p)]
        values = [v.strip().strip("'\"") for v in m.group(2).split(",") if v.strip()]
    var, body = m.group(1), m.group(3)
    if not values or not STEP_CALL.search(body):
        return [(cmd, 0, len(cmd), lambda p: p)]
    n, lo0, hi0 = len(values), m.start(), m.end()

    def mapper(k, blen):
        def f(p):
            if p < lo0:
                return p
            if p < lo0 + blen:
                return lo0 + (k + (p - lo0) / max(blen, 1)) / n * (hi0 - lo0)
            return p - (lo0 + blen) + hi0
        return f
    res = []
    for k, v in enumerate(values):
        b = subst_var(body, var, v)
        c = cmd[:lo0] + b + cmd[hi0:]
        res.append((c, 0, len(c), mapper(k, len(b))) if k == 0 else (c, lo0, lo0 + len(b), mapper(k, len(b))))
    return res


# NAME=literal at the start of a simple command (not after && / ||: conditional)
ASSIGN_RE = re.compile(r"(?:^|[;\n(]|\bdo\b|\bthen\b)[ \t]*(?:export[ \t]+)?([A-Za-z_]\w*)="
                       r"(\"[^\"$`]*\"|'[^']*'|[^\s;&|)$`'\"]*)(?=[\s;&|)]|$)")


def subst_assigned(cmd, pos, text):
    """$NAME in text, for a NAME the command assigned a literal value before pos (the last such assignment)."""
    vals = {}
    for m in ASSIGN_RE.finditer(cmd[:pos]):
        vals[m.group(1)] = m.group(2).strip("\"'")
    for k in sorted(vals, key=len, reverse=True):
        text = subst_var(text, k, vals[k])
    return text


def _tokens(seg):
    """Words of a simple command, quotes removed, backslashes kept (Windows paths: .\\Scripts\\godot.ps1)."""
    try:
        lx = shlex.shlex(seg, posix=True)
        lx.whitespace_split = True
        lx.escape = ""
        lx.commenters = ""
        return list(lx)
    except ValueError:
        return seg.split()


def _opts(toks):
    """PowerShell-style options after a script call: {name lower: value or True}."""
    out, i = {}, 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("-") and len(t) > 1 and not re.match(r"^-\d", t):
            name = t[1:].split(":", 1)[0].lower()
            if ":" in t:
                out[name] = t.split(":", 1)[1]
            elif i + 1 < len(toks) and not toks[i + 1].startswith("-"):
                out[name] = toks[i + 1]
                i += 1
            else:
                out[name] = True
        i += 1
    return out


def _base(tok):
    return os.path.basename(tok.strip("'\"").replace("\\", "/")).lower()


def step_path(value):
    """The -Script value of a step call as a repo path (steps/make_level.gd); None when it is not a readable .gd
    path (a variable the command does not set, a path outside the project)."""
    p = str(value or "").strip("'\"").replace("\\", "/")
    if p.startswith("res://"):
        p = p[len("res://"):]
    while p.startswith("./"):
        p = p[2:]
    if not p.lower().endswith(".gd") or "$" in p or p.startswith(("/", "..")) or re.match(r"^[A-Za-z]:", p):
        return None
    return p


def find_calls(seg):
    """The step runs one simple command starts: [{script (as written), reason}] for
    `Scripts/godot.ps1 step -Script <path> -Reason "..."`. The other modes (import, row, build, play, autoplay) write
    nothing the replay re-runs by itself."""
    toks = _tokens(seg)
    for i, t in enumerate(toks):
        if _base(t) != "godot.ps1":
            continue
        rest = toks[i + 1:]
        mode = None
        if rest and rest[0].lower() == "-mode" and len(rest) > 1:
            mode, rest = rest[1].lower(), rest[2:]
        elif rest and not rest[0].startswith("-"):
            mode, rest = rest[0].lower(), rest[1:]
        if mode != "step":
            return []
        o = _opts(rest)
        return [{"script": o.get("script") if isinstance(o.get("script"), str) else "",
                 "reason": o.get("reason") if isinstance(o.get("reason"), str) else None}]
    return []


def step_runs(actions):
    """Step runs found in shell commands, in order. Each: time (end of the tool call), approximate start, script,
    reason, exit code / duration when the output says so, the workflow row ids it printed. Also the step calls whose
    script cannot be read."""
    runs, unreadable = [], []
    prev_by_session = {}   # tool calls are sequential within a session; other sessions' rows interleave in actions.jsonl
    for a in actions:
        sid = a.get("session_id")
        prev, prev_by_session[sid] = prev_by_session.get(sid), a["time"]
        if a.get("tool") not in SHELL_TOOLS or a.get("event") not in RAN_EVENTS:
            continue
        cmd = (a.get("input") or {}).get("command", "")
        if not isinstance(cmd, str) or not cmd:
            continue
        # heredoc bodies are file contents (e.g. a wrapper script being written), not commands; loops are expanded
        # first, so a run written as `for s in a b; do ./Scripts/godot.ps1 step -Script steps/$s.gd; done` is found
        text = shellfx.protect_heredocs(cmd)[0]
        if not STEP_CALL.search(text):
            continue
        found = []
        for c, lo_k, hi_k, posmap in expand_loops(text):
            for pos, seg in shellfx.segments(c, positions=True):
                if not (lo_k <= pos < hi_k):
                    continue
                for call in find_calls(seg):
                    script = step_path(subst_assigned(c, pos, call["script"]))
                    if not script:
                        unreadable.append({"time": a["time"], "tool_use_id": a.get("tool_use_id"), "command": seg[:300]})
                        continue
                    found.append((posmap(pos), dict(call, script=script)))
        if not found:
            continue
        found.sort(key=lambda x: x[0])
        resp = shellfx.response_text(a)
        # the output, cut per run: Scripts/godot.ps1 ends each run with "exit code N (S s)"
        exits = [(m.group(1), m.group(2), m.end()) for m in EXIT_RE.finditer(resp)]
        cut = 0
        for k, (pos, call) in enumerate(found):
            ex = exits[k] if len(exits) == len(found) else None
            end = ex[2] if ex else (len(resp) if k == len(found) - 1 else None)
            rows_out = [x.group(1) for x in ROW_RE.finditer(resp, cut, end)] if end is not None else []
            if end is not None:
                cut = end
            dur = int(ex[1]) if ex and ex[1] else None
            start = (parse_time(a["time"]) - datetime.timedelta(seconds=dur)).isoformat(timespec="milliseconds") if dur is not None else a["time"]
            runs.append({"time": a["time"], "start": start, "after": prev, "action_tool_use_id": a.get("tool_use_id"),
                         "pos": pos, "command": cmd, "event": a.get("event"),
                         "script": call["script"], "reason": call.get("reason"),
                         "exit_code": int(ex[0]) if ex else None, "duration_s": dur, "rows": rows_out})
    return runs, unreadable


def repo_rel(path, repo_abs):
    p = shellfx.win_path(path.replace("\\", "/"))
    root = repo_abs.replace("\\", "/").rstrip("/") + "/"
    if p.lower().startswith(root.lower()):
        return p[len(root):]
    return None


# Antigravity's rows (agent "antigravity") keep its own tool names and arguments. Those whose effect is known are read as
# Claude Code's: run_command (CommandLine) as Bash, write_file (Path, Content) as Write, or as "Append" with Append
# set (the content added to the file's end; a new file when there is none), edit_file (Path, Target, Replacement,
# AllowMultiple) as Edit. Any other of its tools that writes a file it names (write_to_file, replace_file_content, ...)
# becomes "Unreplayed": the ledger cannot replay it, so the file is unknown until the next boundary, as after an Edit
# whose old text is not there.
WRITES = re.compile(r"(?i)write|replace|edit|delete|move|rename")
PATH_ARGS = ("Path", "TargetFile", "AbsolutePath", "File", "FilePath")


def as_claude(a):
    """`a` (an actions.jsonl row) as the ledger reads it: an Antigravity row in Claude Code's shape where it can be."""
    if a.get("agent") != "antigravity":
        return a
    inp = a.get("input") or {}
    tool = a.get("tool")
    if tool == "run_command" and isinstance(inp.get("CommandLine"), str):
        return dict(a, tool="Bash", input=dict(inp, command=inp["CommandLine"]))
    if tool == "write_file" and isinstance(inp.get("Path"), str) and isinstance(inp.get("Content"), str):
        return dict(a, tool="Append" if inp.get("Append") else "Write",
                    input={"file_path": inp["Path"], "content": inp["Content"]})
    if tool == "edit_file" and isinstance(inp.get("Path"), str) and isinstance(inp.get("Target"), str) \
            and isinstance(inp.get("Replacement"), str):
        return dict(a, tool="Edit", input={"file_path": inp["Path"], "old_string": inp["Target"],
                                           "new_string": inp["Replacement"],
                                           "replace_all": bool(inp.get("AllowMultiple"))})
    path = next((inp[k] for k in PATH_ARGS if isinstance(inp.get(k), str)), None)
    if path and WRITES.search(tool or ""):
        return dict(a, tool="Unreplayed", input={"file_path": path, "tool": tool})
    return a


ABSENT = object()  # sentinel: the file does not exist yet


class FileStates:
    """Text of repo files as the agent's Write/Edit calls and shell edits left them. None = unknown."""

    ABSENT = None  # set below

    def __init__(self, repo, start_sha):
        self.repo = repo
        self.base_sha = start_sha
        self.state = {}       # path -> bytes | None (unknown) | ABSENT
        self.touched = set()  # paths written or edited since the last boundary
        self.how = {}         # path -> last kind of write
        self.tracked = None   # paths reported at boundaries (set by the caller)
        self.mismatch = {}    # sha256 -> reconstructed text that did not match its commit

    def get(self, path):
        """Current text; ABSENT when the file does not exist yet, None when unknown."""
        if path not in self.state:
            b = blob_at(self.repo, self.base_sha, path)
            self.state[path] = norm_text(b) if b is not None else ABSENT
        return self.state[path]

    def write(self, path, content):
        self.state[path] = norm_text(content.encode("utf-8"))
        self.touched.add(path)

    def edit(self, path, old, new, replace_all):
        cur = self.get(path)
        self.touched.add(path)
        if cur is None or cur is ABSENT:
            self.state[path] = None
            return False
        o, n = norm_text(old.encode("utf-8")), norm_text(new.encode("utf-8"))
        if o not in cur:
            self.state[path] = None
            return False
        self.state[path] = cur.replace(o, n) if replace_all else cur.replace(o, n, 1)
        return True

    def put(self, path, content, how):
        if content is not None and content is not ABSENT:
            content = norm_text(content)
        self.state[path] = content
        self.touched.add(path)
        self.how[path] = how

    def boundary(self, sha):
        """Compare what the recorded edits left with the commit, then reset to the commit. Returns (checks, the paths
        the recording shows written since the last boundary)."""
        checks = []
        for p in sorted(self.touched):
            if self.tracked is not None and p not in self.tracked:
                continue
            st = self.state.get(p)
            b = blob_at(self.repo, sha, p)
            blob = norm_text(b) if b is not None else None
            c = {"path": p, "reconstructed": st is not None, "how": self.how.get(p),
                 "match": st is not None and (st == blob if blob is not None else st is ABSENT)}
            if not c["match"] and isinstance(st, bytes):
                c["sha256"] = sha256(st)
                self.mismatch[c["sha256"]] = st
            checks.append(c)
        written = set(self.touched)
        self.state = {}
        self.touched = set()
        self.how = {}
        self.base_sha = sha
        return checks, written


FileStates.ABSENT = ABSENT


# ----------------------------------------------------------------------------------------------- build
def build(cfg):
    repo = cfg["repo"]
    repo_abs = os.path.abspath(repo).replace("\\", "/")
    final = git(repo, "rev-parse", cfg["final"]).strip()
    chain = first_parent_chain(repo, final, recorded_commits(cfg["recording"]))
    path = os.path.join(cfg["recording"], "actions.jsonl")
    actions = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        actions.append(as_claude(json.loads(line)))
                    except ValueError:
                        pass
    actions.sort(key=lambda a: a["time"])
    t_final = parse_time(chain[-1]["order"])
    actions = [a for a in actions if parse_time(a["time"]) <= t_final + datetime.timedelta(seconds=60)]
    wf_rows = [json.loads(l) for l in git(repo, "show", "%s:workflow.jsonl" % final).splitlines() if l.strip()] \
        if blob_at(repo, final, "workflow.jsonl") is not None else []
    rows_by_id = {r.get("id"): r for r in wf_rows}

    runs, unreadable = step_runs(actions)

    # windows by commit time (the first commit has no window: it is the starting point)
    extra_ext = cfg.get("content_ext", [])
    windows = []
    for i, c in enumerate(chain):
        parent = chain[i - 1]["sha"] if i else None
        ch = changed_paths(repo, parent, c["sha"])
        windows.append({
            "index": i, "sha": c["sha"], "parent": parent, "time": c["time"], "order": c["order"], "subject": c["subject"],
            "merge_parents": c["parents"][1:], "changed": ch,
            "inputs": [{"status": s, "path": p} for s, p in ch] if not i else [], "content": [],
            "code_changed": sorted(p for s, p in ch if is_code(p)),
            "runs": [], "shell": [], "shell_unreadable": [], "reconstruction": [],
            "events": collections.Counter(),
        })

    # walk actions in time order: file states, runs (with step texts), shell deletes
    fs = FileStates(repo, chain[0]["sha"])
    blobs = {}
    tracked = set(p for w in windows for _, p in w["changed"]
                  if p.lower().endswith(TEXT_EXT) and p != "workflow.jsonl")
    sandbox = shellfx.Sandbox(repo_abs, os.path.join(cfg["work_dir"], "sandbox") if cfg.get("work_dir") else None)
    fs.tracked = tracked
    aux = {}  # helper files the agent wrote outside the repo (absolute path -> text)
    run_by_tool = collections.defaultdict(list)
    for r in runs:
        run_by_tool[r["action_tool_use_id"]].append(r)
    cur_w = 1
    run_seq = 0

    def close(k):
        """The boundary of window k: the recorded writes against the commit, and what the commit changes split into
        inputs and generated files (a generated kind the recording shows no write of)."""
        w = windows[k]
        w["reconstruction"], written = fs.boundary(w["sha"])
        for s, p in w["changed"]:
            kind = generated_kind(p, extra_ext)
            if kind and p.lower().endswith(".import") and blob_at(repo, w["sha"], p[:-len(".import")]) is None:
                kind = None   # an orphan: no source file for the engine to import, so the commit's file as it is
            if kind and s != "D" and p not in written:
                w["content"].append({"status": s, "path": p, "kind": kind})
            else:
                w["inputs"].append({"status": s, "path": p, **({"written": True} if p in written else {})})

    def close_until(t):
        nonlocal cur_w
        while cur_w < len(windows) and parse_time(windows[cur_w]["order"]) < parse_time(t):
            close(cur_w)
            cur_w += 1

    def close_through(k):
        nonlocal cur_w
        while cur_w <= k and cur_w < len(windows):
            close(cur_w)
            cur_w += 1

    commit_rx = re.compile(r"\bgit\b(?:\s+-c\s+\S+)*\s+commit\b")

    def add_run(w, r):
        """One run in window w, with the step texts it started with."""
        nonlocal run_seq
        run_seq += 1
        # every step script the window changes that the builder wrote in it (the recorded Write/Edit/patch/shell
        # edits), as it stood when the run started. One the window changes without a recorded write was changed
        # outside the recording: it keeps the commit's text.
        texts, unknown, absent = {}, [], []
        for p in w["code_changed"]:
            if p not in fs.touched:
                continue
            st = fs.get(p)
            if st is None:
                unknown.append(p)
            elif st is ABSENT:
                absent.append(p)
            else:
                h = sha256(st)
                blobs[h] = st
                texts[p] = h
        script = r["script"]
        rr = dict(r, id="R%04d" % run_seq, window=w["index"], texts=texts, unknown=unknown, absent=absent)
        if script in texts:
            rr["script_version"] = "reconstructed"
        elif script in unknown or script in absent:
            rr["script_version"] = "unknown_use_commit"
        elif script in w["code_changed"]:
            rr["script_version"] = "commit_text"   # changed in the window without a recorded write
        else:
            rr["script_version"] = "unchanged"
        # the sha256 the step's workflow row carries (the script text as the builder ran it), for the report
        shas = [(rows_by_id[i].get("source") or {}).get("sha256") for i in r["rows"] if i in rows_by_id]
        rr["row_sha256"] = next((s for s in shas if s), None)
        w["runs"].append(rr)

    for a in actions:
        # A command with `git commit` in it did its work around its own commits: close only the windows whose commits
        # came before the command started (after the session's previous tool call), so its edits and runs land in the
        # window the next commit closes. A run that comes after n of the command's own commits in the command text
        # lands after the n-th of them.
        tool = a.get("tool")
        cmd_text = (a.get("input") or {}).get("command", "") if tool in SHELL_TOOLS else ""
        cmd_text = cmd_text if isinstance(cmd_text, str) else ""
        prot = shellfx.protect_heredocs(cmd_text)[0] if cmd_text else ""
        ops, unread = (shellfx.content_ops(a, repo_abs, lambda p: not p.startswith(".git"))
                       if cmd_text and a.get("event") in RAN_EVENTS else ([], []))
        # a copy leaves nothing to take away: what it wrote is the commit's, an input
        ops = [o for o in ops if o["op"] in ("delete", "move")]
        unread = [u for u in unread if _base(u["command"].split()[0]) in shellfx.MOVE + shellfx.DELETE]
        my_runs = run_by_tool.get(a.get("tool_use_id"), [])
        cmd_commit_pos, cmd_windows = [], []
        if (my_runs or ops) and "git commit" in cmd_text:
            first = my_runs[0] if my_runs else {}
            t_start = first.get("after") or first.get("start") or a["time"]
            close_until(t_start)
            cmd_commit_pos = [m.start() for m in commit_rx.finditer(prot)]
            cmd_windows = [k for k in range(cur_w, len(windows))
                           if parse_time(t_start) <= parse_time(windows[k]["order"]) <= parse_time(a["time"])]
            # more commits in that span than the command makes: the earlier ones are not its own (the end-of-turn WIP
            # commit between two turns), so they close before its work
            extra = len(cmd_windows) - len(cmd_commit_pos)
            if extra > 0:
                close_through(cmd_windows[extra - 1])
                cmd_windows = cmd_windows[extra:]
        else:
            close_until(a["time"])
        if cur_w >= len(windows):
            break
        w = windows[cur_w]
        if a.get("event") != "PostToolUse" and not (tool in SHELL_TOOLS and a.get("event") in RAN_EVENTS):
            continue
        inp = a.get("input") or {}
        if tool in SHELL_TOOLS and cmd_text:
            fx = []
            shellfx.apply_command(a, fs, sandbox, tracked, fx, aux)
            if fx:
                w["events"]["shell_edits"] += len(fx)
                for e in fx:
                    if e[0].endswith("failed"):
                        w["events"]["shell_edit_failed"] += 1
        if tool == "Write" and not repo_rel(inp.get("file_path", ""), repo_abs):
            aux[shellfx._abs(inp.get("file_path", ""))] = inp.get("content", "")
        if tool == "Write":
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                fs.write(p, inp.get("content", ""))
                w["events"]["write"] += 1
        elif tool == "Edit":
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                ok = fs.edit(p, inp.get("old_string", ""), inp.get("new_string", ""), inp.get("replace_all", False))
                w["events"]["edit" if ok else "edit_unapplied"] += 1
        elif tool == "MultiEdit":
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                for e in inp.get("edits") or []:
                    ok = fs.edit(p, e.get("old_string", ""), e.get("new_string", ""), e.get("replace_all", False))
                    w["events"]["edit" if ok else "edit_unapplied"] += 1
        elif tool == "Append":   # Antigravity's write_file with Append (as_claude)
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                cur = fs.get(p)
                if cur is ABSENT:
                    fs.write(p, inp.get("content", ""))
                elif cur is None:
                    fs.put(p, None, "append")
                else:
                    fs.write(p, cur.decode("utf-8", "replace") + inp.get("content", ""))
                w["events"]["write"] += 1
        elif tool == "Unreplayed":   # an Antigravity file tool the ledger cannot replay (as_claude)
            p = repo_rel(inp.get("file_path", ""), repo_abs)
            if p:
                fs.put(p, None, inp.get("tool") or "unreplayed")
                w["events"]["unreplayed"] += 1
        elif tool == "apply_patch" and isinstance(inp.get("command"), str):
            # one patch adds, deletes, updates or moves files (patchfx.py); a patch that does not parse or a hunk that
            # does not apply leaves the file unknown, like an Edit whose old text is not there
            try:
                pops = patchfx.parse(inp["command"])
            except ValueError:
                pops = None
                w["events"]["patch_unparsed"] += 1
            for op, ppath, data in pops or []:
                full = patchfx.resolve(ppath, a.get("cwd") or "")
                p = repo_rel(full, repo_abs)
                if op == "add":
                    if p:
                        fs.write(p, data)
                        w["events"]["patch"] += 1
                    else:
                        aux[full] = data
                elif op == "delete" and p:
                    fs.put(p, ABSENT, "apply_patch")
                    w["events"]["patch"] += 1
                elif op == "update" and p:
                    cur = fs.get(p)
                    new = patchfx.apply_update(cur.decode("utf-8", "replace"), data["hunks"]) if isinstance(cur, bytes) else None
                    dest = repo_rel(patchfx.resolve(data["move"], a.get("cwd") or ""), repo_abs) if data["move"] else p
                    if new is None:
                        fs.put(p, None, "apply_patch")
                        w["events"]["patch_unapplied"] += 1
                        continue
                    if dest != p:
                        fs.put(p, ABSENT, "apply_patch")
                    if dest:
                        fs.write(dest, new)
                    w["events"]["patch"] += 1
        elif tool == "apply_patch" and isinstance(inp.get("changes"), dict):
            # a session imported from its transcript keeps the changes, not the patch text: the files become unknown
            for ppath in inp["changes"]:
                p = repo_rel(patchfx.resolve(ppath, a.get("cwd") or ""), repo_abs)
                if p:
                    fs.put(p, None, "apply_patch_changes")
                    w["events"]["patch_unknown"] += 1
        if tool in SHELL_TOOLS:
            # items of this command in their order: runs (texts as of before the command's own later writes) and the
            # files the command deleted or moved away
            items = [("run", r.get("pos") or 0, r) for r in my_runs] + [("op", o["pos"], o) for o in ops]
            for u in unread:
                w["shell_unreadable"].append(dict(u, time=a["time"]))
            items.sort(key=lambda x: x[1])
            for kind, pos, item in items:
                if cmd_windows and cmd_commit_pos:
                    n = sum(1 for p in cmd_commit_pos if p < pos)
                    if n:
                        close_through(cmd_windows[min(n, len(cmd_windows)) - 1])
                        if cur_w >= len(windows):
                            continue   # after the last commit: not part of the replayed history
                        w = windows[cur_w]
                if kind == "run":
                    add_run(w, item)
                else:
                    w["shell"].append({"op": "delete", "paths": item["src"], "time": a["time"], "pos": pos,
                                       "id": "S%s_%d" % ((a.get("tool_use_id") or "x")[-8:], pos),
                                       "command": cmd_text[max(0, pos - 20):pos + 200]})
    close_until("9999-12-31T00:00:00+00:00")
    sandbox.close()
    blobs.update(fs.mismatch)

    all_runs = [r for w in windows for r in w["runs"]]
    for w in windows:
        w["events"] = dict(w["events"])
        del w["changed"]
    return {"schema": SCHEMA, "game": cfg["game"], "final": final, "first": chain[0]["sha"],
            "windows": windows, "unreadable_steps": unreadable, "counts": {
                "windows": len(windows) - 1, "runs": len(all_runs),
                "script_version": dict(collections.Counter(r["script_version"] for r in all_runs)),
                "runs_with_unknown_code": sum(1 for r in all_runs if r["unknown"]),
                "generated_files": sum(len(w["content"]) for w in windows),
                "shell_steps": sum(len(w["shell"]) for w in windows),
                "reconstruction_checks": sum(len(w["reconstruction"]) for w in windows),
                "reconstruction_match": sum(1 for w in windows for c in w["reconstruction"] if c["match"]),
                "reconstruction_unknown": sum(1 for w in windows for c in w["reconstruction"] if not c["reconstructed"]),
            }}, blobs
