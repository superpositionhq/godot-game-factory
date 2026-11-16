"""verify: the replayed project against the final commit (docs/godot-replay.md, "What is checked").

  files      every tracked file: identical bytes (sha256 for LFS objects, git blob id otherwise), differs, missing; extras
  structure  dump-replay/dump.json vs dump-truth/dump.json (engine/replay_dump.gd on the replayed project and on a
             clone of the final commit): every scene's nodes, properties and connections, every resource's class and
             properties, every imported file's importer, type and settings
  runs       each replayed step run against the original: exit code, and the sha256 of the step's text its workflow
             row carries
  verdict    PASS / FAIL against the criteria below; metadata of the dataset either way
Writes work/Verification/report.json (docs/schemas/replay-report.schema.json) and report.md.

Pass criteria (all must hold):
  1. every tracked file is byte-identical to the final commit, none missing, no extra files except git-ignored ones;
  2. the two structure dumps are equal.
Known differences that are not content are normalised before comparing, counted and listed in the report (NORMALISE).
"""
import collections
import hashlib
import json
import math
import os
import re

import runner

TOL = 0.0011
SCHEMA_ID = "godot-replay.verification/v1"
KINDS = ("scenes", "resources", "imported")


def close(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-4, abs_tol=TOL)
        except (TypeError, ValueError):
            return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    return a == b


def diff_keys(a, b, prefix=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(prefix + k)
            elif not close(a[k], b[k]):
                if isinstance(a[k], dict) and isinstance(b[k], dict):
                    out += diff_keys(a[k], b[k], prefix + k + ".")
                elif (isinstance(a[k], list) and isinstance(b[k], list) and len(a[k]) == len(b[k])
                      and any(isinstance(x, dict) for x in a[k])):
                    # nodes of a scene: the element and the field inside it
                    for i, (x, y) in enumerate(zip(a[k], b[k])):
                        if not close(x, y):
                            out += diff_keys(x, y, "%s%s[%d]." % (prefix, k, i)) if isinstance(x, dict) and isinstance(y, dict) \
                                else ["%s%s[%d]" % (prefix, k, i)]
                else:
                    out.append(prefix + k)
    elif not close(a, b):
        out.append(prefix.rstrip(".") or "value")
    return out


# Known non-content differences, normalised before comparing (each counted in the report):
NORMALISE = [
    ("uid", "uid:// strings (the engine makes a random one for every new file on every machine; what a reference "
            "points at is compared by its path)",
     lambda s: re.sub(r"uid://[a-z0-9]+", "uid://<uid>", s)),
]


def norm_with(obj, rules):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    for _, _, f in rules:
        s = f(s)
    return json.loads(s)


def tolerant_diff(a, b, counts):
    """diff_keys after the known non-content differences are taken out; counts[rule] += 1 for each rule that removed
    a difference."""
    dk = diff_keys(a, b)
    if not dk:
        return []
    na, nb = norm_with(a, NORMALISE), norm_with(b, NORMALISE)
    rest = diff_keys(na, nb)
    if len(rest) < len(dk):
        for rid, _, f in NORMALISE:   # attribute to the first rule that alone removes some difference
            if len(diff_keys(norm_with(a, [(rid, "", f)]), norm_with(b, [(rid, "", f)]))) < len(dk):
                counts[rid] += 1
                break
    return rest


# ------------------------------------------------------------------------------------------------ files
def verify_files(ctx, final, counts):
    """Every tracked file of the final commit against the replay project, byte for byte. A text file that differs
    only in uid:// strings counts as identical (counts["uid"])."""
    ids = runner.tree_ids(ctx.proj, final)
    have = runner.scan(ctx.proj)
    res = {"identical": 0, "differs": [], "missing": []}
    for p, ident in ids.items():
        fp = os.path.join(ctx.proj, p)
        if p not in have:
            res["missing"].append(p)
        elif runner.file_matches(fp, ident):
            res["identical"] += 1
        elif ident[0] == "git" and same_but_uids(fp, runner.git(ctx.proj, "show", "%s:%s" % (final, p), binary=True)):
            res["identical"] += 1
            counts["uid"] += 1
        else:
            res["differs"].append(p)
    res["extra"], res["ignored"] = runner.untracked(ctx.proj, ids)
    return res


def same_but_uids(fp, blob):
    with open(fp, "rb") as f:
        data = f.read()
    if b"\0" in data[:8000] or b"\0" in blob[:8000]:
        return False
    return runner.UID.sub(b"uid://<uid>", data) == runner.UID.sub(b"uid://<uid>", blob)


# ------------------------------------------------------------------------------------------------ structure
def verify_structure(rep, tru, counts=None):
    """The two structure dumps, entry by entry: {total, by_kind, diffs}."""
    counts = counts if counts is not None else collections.Counter()
    by_kind = {}
    diffs = []
    for kind in KINDS:
        a, b = rep.get(kind) or {}, tru.get(kind) or {}
        c = collections.Counter()
        for k, t in b.items():
            if k not in a:
                c["missing"] += 1
                diffs.append({"path": k, "kind": kind, "result": "missing"})
                continue
            dk = tolerant_diff(a[k], t, counts)
            if dk:
                c["differs"] += 1
                diffs.append({"path": k, "kind": kind, "result": "differs", "keys": dk[:20]})
            else:
                c["same"] += 1
        for k in a:
            if k not in b:
                c["extra"] += 1
                diffs.append({"path": k, "kind": kind, "result": "extra"})
        by_kind[kind] = dict(c)
    total = collections.Counter()
    for c in by_kind.values():
        total.update(c)
    return {"total": dict(total), "by_kind": by_kind, "diffs": diffs}


def make_dumps(ctx, final):
    """The truth clone at the final commit, imported, and the structure dump of both projects. Returns the two dump
    files, or None with the reason."""
    runner.sync_truth(ctx.cfg, final)
    truth = ctx.cfg["truth_dir"]
    runner.import_project(ctx, truth, "truth_import")
    if not os.path.isdir(os.path.join(ctx.proj, ".godot")):
        runner.import_project(ctx, ctx.proj, "replay_import")
    out = []
    for which, proj in (("truth", truth), ("replay", ctx.proj)):
        code, secs, dest = runner.dump(ctx, proj, os.path.join(ctx.work, "dump-" + which), "dump_" + which)
        d = runner.jload(dest, None) if os.path.exists(dest) else None
        if code != 0 or not d or not d.get("done"):
            return None, "the %s dump did not finish (exit %s; work/logs/dump_%s.log)" % (which, code, which)
        out.append(d)
    return (out[1], out[0]), None


# ------------------------------------------------------------------------------------------------ runs
def verify_runs(ctx, ledger):
    """Each replayed step run against the original: the exit code, and the step text (the sha256 the builder's
    workflow row carries against the text the replay ran)."""
    log = {x.get("run"): x for x in runner.jlines(os.path.join(ctx.work, "runs.jsonl")) if x.get("kind") == "run"}
    out, exits, texts = [], collections.Counter(), collections.Counter()
    for w in ledger["windows"]:
        for r in w["runs"]:
            x = log.get(r["id"]) or {}
            h = (r.get("texts") or {}).get(r["script"])
            if not h:
                b = runner.git(ctx.repo, "show", "%s:%s" % (w["sha"], r["script"]), binary=True, check=False)
                h = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest() if b else None
            text = "not_logged" if not r.get("row_sha256") else ("same" if r["row_sha256"] == h else "differs")
            ex = "not_recorded" if r.get("exit_code") is None else ("same" if r["exit_code"] == x.get("exit_code") else "differs")
            exits[ex] += 1
            texts[text] += 1
            out.append({"run": r["id"], "window": w["index"], "script": r["script"], "exit_code": x.get("exit_code"),
                        "exit_code_original": r.get("exit_code"), "exit": ex, "step_text": text})
    return {"exit_code": dict(exits), "step_text": dict(texts), "runs": out}


# ------------------------------------------------------------------------------------------------ verdict
def verdict(report, counts):
    f = report["files"]
    crit = [{"id": "files", "text": "every tracked file byte-identical to the final commit; none missing; no extra "
                                    "files except git-ignored ones",
             "pass": not f["differs"] and not f["missing"] and not f["extra"],
             "result": "%d identical, %d differ, %d missing; %d extra (%d more git-ignored)" % (
                 f["identical"], len(f["differs"]), len(f["missing"]), len(f["extra"]), len(f["ignored"])),
             "failures": (f["differs"] + f["missing"] + f["extra"])[:50]}]
    s = report["structure"]
    if s.get("diffs") is not None:
        t = s["total"]
        crit.append({"id": "structure", "text": "the structure dumps of the replayed project and of the final commit "
                                                "are equal: scenes, resources, import settings",
                     "pass": not s["diffs"], "result": "%d same, %d differ, %d missing, %d extra" % (
                         t.get("same", 0), t.get("differs", 0), t.get("missing", 0), t.get("extra", 0)),
                     "failures": [[d["path"], d["result"], d.get("keys")] for d in s["diffs"]][:50]})
    else:
        crit.append({"id": "structure", "text": "structure dumps of replay and truth", "pass": False,
                     "result": "no structure dumps", "failures": [s.get("note", "")]})
    adopted = sum((w.get("content") or {}).get("adopted_uids", 0) for w in report.get("windows", []))
    exclusions = [
        {"id": NORMALISE[0][0], "what": NORMALISE[0][1], "count": counts.get("uid", 0)},
        {"id": "uids_adopted", "what": "uid:// identities of files the replay generated, given the ones the commit has "
                                       "at the same paths at each boundary (identity, not content)", "count": adopted},
        {"id": "git_ignored_extra_files", "what": "files in the replay project its .gitignore leaves out",
         "count": len(f["ignored"]), "items": f["ignored"][:200]},
    ]
    runs = report.get("runs", {})
    return {"pass": all(c["pass"] for c in crit), "criteria": crit, "exclusions": exclusions,
            "informational": {"exit_code_per_run": runs.get("exit_code", {}), "step_text_per_run": runs.get("step_text", {}),
                              "note": "the comparison of runs is informational: the verdict is about what they left"}}


# ------------------------------------------------------------------------------------------------ report
def deviations(ctx, report):
    """Every place the replay departs from the raw recording: what, which runs/items, which commit, why."""
    led = ctx.ledger
    runs = [dict(r, _w=w) for w in led["windows"] for r in w["runs"]]
    out = []

    def add(kind, what, items, reason=None):
        if items:
            out.append({"kind": kind, "what": what, "items": items, **({"reason": reason} if reason else {})})

    if not os.path.isfile(os.path.join(ctx.cfg["recording"], "actions.jsonl")):
        add("no_recording", "the game has no recorded actions: no step run is known, and every generated file is taken "
            "from its commit", [{"recording": "actions.jsonl"}])
    add("commit_text_unrebuildable", "step text the recording could not rebuild (an edit it cannot follow, or one made "
        "outside the recording): the window's commit text is used",
        [{"script": r["script"], "window": r["_w"]["index"], "commit": r["_w"]["sha"], "run": r["id"]}
         for r in runs if r.get("script_version") in ("unknown_use_commit", "commit_text")])
    add("unreadable_steps", "step calls in the recording whose script the replay cannot read (a variable the command "
        "does not set, a path outside the project): not replayed",
        [{"time": u.get("time"), "command": u.get("command")} for u in led.get("unreadable_steps", [])])
    add("shell_deletes", "files a recorded shell command deleted or moved away, removed from the replay's own files at "
        "the same point", [{"window": w["index"], "paths": s["paths"]} for w in led["windows"] for s in w["shell"]])
    add("shell_not_followed", "recorded shell copies, moves and deletes the replay cannot read (a path outside the "
        "repo, a wildcard or a variable): not replayed",
        [{"window": w["index"], "command": s.get("command")} for w in led["windows"] for s in w.get("shell_unreadable", [])])
    log = runner.jlines(os.path.join(ctx.work, "runs.jsonl"))
    add("runs_timed_out", "engine runs stopped at the run time limit (settings run_timeout_s)",
        [{"step": x.get("step"), "script": x.get("script"), "seconds": x.get("seconds")} for x in log if x.get("timed_out")])
    add("exit_code_differs", "step runs that ended with another exit code than the builder's run",
        [{"run": x["run"], "script": x["script"], "exit_code": x["exit_code"], "original": x["exit_code_original"]}
         for x in (report.get("runs") or {}).get("runs", []) if x["exit"] == "differs"])
    add("reconstruction_mismatch", "files the recorded writes and edits rebuild to another text than the commit has (an "
        "edit the recording does not hold, or a recording that does not match the history): a step ran with the "
        "rebuilt text, the window ended with the commit's",
        [{"window": w["index"], "commit": w["sha"][:10], "path": c["path"]} for w in led["windows"]
         for c in w.get("reconstruction", []) if c.get("reconstructed") and not c.get("match")])
    add("content_from_commit", "generated files the commit added or changed that no replayed step produced, taken from "
        "the commit at the window's end (a change in the editor, a hand edit outside the recording, a step that is "
        "not recorded)",
        [{"window": w["window"], "commit": w["commit"][:10], "files": [x["path"] for x in (w.get("detail") or {}).get("fallback", [])]}
         for w in report.get("windows") or [] if w["content"].get("fallback")])
    return out


def validate_report(report, schema_path=None):
    """The report against docs/schemas/replay-report.schema.json (the subset of JSON Schema it uses): a list of
    problems, empty when valid. Without the schema file (a delivered ReplayScripts/), nothing is checked."""
    schema_path = schema_path or os.path.join(os.path.dirname(os.path.dirname(runner.HERE)), "docs", "schemas", "replay-report.schema.json")
    if not os.path.isfile(schema_path):
        return []
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    problems = []

    def check(v, s, where):
        t = s.get("type")
        types = t if isinstance(t, list) else [t] if t else []
        pytypes = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}
        if types and not any(isinstance(v, pytypes[x]) and not (x in ("integer", "number") and isinstance(v, bool)) for x in types):
            problems.append("%s: not %s" % (where, "/".join(types)))
            return
        if "const" in s and v != s["const"]:
            problems.append("%s: not %r" % (where, s["const"]))
        if "pattern" in s and isinstance(v, str) and not re.search(s["pattern"], v):
            problems.append("%s: does not match %s" % (where, s["pattern"]))
        if "minLength" in s and isinstance(v, str) and len(v) < s["minLength"]:
            problems.append("%s: too short" % where)
        if "minimum" in s and isinstance(v, (int, float)) and v < s["minimum"]:
            problems.append("%s: below %s" % (where, s["minimum"]))
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    problems.append("%s: no %s" % (where, k))
            for k, sub in (s.get("properties") or {}).items():
                if k in v:
                    check(v[k], sub, where + "." + k)
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                problems.append("%s: fewer than %d items" % (where, s["minItems"]))
            if "items" in s:
                for i, x in enumerate(v):
                    check(x, s["items"], "%s[%d]" % (where, i))
    check(report, schema, "report")
    return problems


def cmd_verify(cfg, a):
    ctx = runner.Ctx(cfg)
    led = ctx.ledger
    if led is None or ctx.state.get("window", 0) < len(led["windows"]) - 1:
        raise SystemExit("verify: the replay has not reached the final commit (run `run` first)")
    final = led["final"]
    vdir = os.path.join(ctx.work, "Verification")
    os.makedirs(vdir, exist_ok=True)
    counts = collections.Counter()
    report = {"schema": SCHEMA_ID, "game": cfg["game"], "final_commit": final, "time": runner.now()}
    report["files"] = verify_files(ctx, final, counts)
    dumps, why = make_dumps(ctx, final)
    report["structure"] = verify_structure(dumps[0], dumps[1], counts) if dumps else {"total": {}, "note": why}
    report["runs"] = verify_runs(ctx, led)
    report["windows"] = runner.jlines(os.path.join(ctx.work, "windows.jsonl"))
    report["verdict"] = verdict(report, counts)
    report["deviations"] = deviations(ctx, report)
    problems = validate_report(report)
    if problems:
        print("report.json does not match docs/schemas/replay-report.schema.json: %s" % "; ".join(problems[:10]))
    runner.jdump(os.path.join(vdir, "report.json"), report)
    md = render_md(report)
    with open(os.path.join(vdir, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    print(md[:6000])
    print("VERDICT: %s" % ("PASS" if report["verdict"]["pass"] else "FAIL"))
    return 0 if report["verdict"]["pass"] else 1


def render_deviations(devs):
    """Markdown: every place the replay departs from the raw recording (also used by package.py's README)."""
    L = ["## Deviations from the recording", ""]
    if not devs:
        return L + ["None: every step was replayed from the recording as recorded.", ""]
    L += ["Everything below is done by a rule of the replay rather than straight from the recorded actions; each entry",
          "says why.", ""]
    for d in devs:
        L.append("### %s (%d)" % (d["kind"], len(d["items"])))
        L += ["", d["what"] + (". Why: " + d["reason"] if d.get("reason") else "."), ""]
        for it in d["items"][:60]:
            if isinstance(it, dict):
                L.append("- " + "; ".join("%s: %s" % (k, ", ".join(map(str, v)) if isinstance(v, list) else
                                                      (v[:12] if k == "commit" and isinstance(v, str) else v))
                                          for k, v in it.items() if v not in (None, "", [])))
            else:
                L.append("- %s" % it)
        if len(d["items"]) > 60:
            L.append("- ... %d more (report.json)" % (len(d["items"]) - 60))
        L.append("")
    return L


def render_md(r):
    L = ["# Replay verification: %s at %s" % (r["game"], r["final_commit"][:10]), ""]
    v = r["verdict"]
    L += ["## Verdict: %s" % ("PASS" if v["pass"] else "FAIL"), "", "| criterion | result | pass |", "|---|---|---|"]
    for c in v["criteria"]:
        L.append("| %s | %s | %s |" % (c["text"], c["result"], "yes" if c["pass"] else "**no**"))
    for c in [c for c in v["criteria"] if not c["pass"] and c.get("failures")]:
        L += ["", "Why %s fails (first %d):" % (c["id"], min(len(c["failures"]), 12)), ""]
        L += ["- %s" % (json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x) for x in c["failures"][:12]]
    L += ["", "Known differences that are not content (normalised or not compared):", ""]
    for e in v["exclusions"]:
        L.append("- %s: %s (%d)" % (e["id"], e["what"], e["count"]))
    L.append("")
    L += render_deviations(r.get("deviations") or [])
    f = r["files"]
    L += ["## Files against the final commit", "",
          "Identical: %d; differs: %d; missing: %d; extra: %d (and %d git-ignored)." % (
              f["identical"], len(f["differs"]), len(f["missing"]), len(f["extra"]), len(f["ignored"])), ""]
    s = r["structure"]
    if s.get("diffs") is not None:
        L += ["## Structure dump", "", "| kind | same | differs | missing | extra |", "|---|---:|---:|---:|---:|"]
        for k, x in s["by_kind"].items():
            L.append("| %s | %d | %d | %d | %d |" % (k, x.get("same", 0), x.get("differs", 0), x.get("missing", 0), x.get("extra", 0)))
        L.append("")
    rr = r["runs"]
    L += ["## Step runs replayed vs original", "",
          "Exit code: " + (", ".join("%s %d" % kv for kv in sorted(rr["exit_code"].items())) or "no runs") + ".",
          "Step text (the sha256 each workflow row carries): " + (", ".join("%s %d" % kv for kv in sorted(rr["step_text"].items())) or "no runs") + ".", ""]
    if r["windows"]:
        L += ["## Windows", "", "| # | commit | runs | seconds | from commit | identical | differs | missing | extra | uids adopted |",
              "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for w in r["windows"]:
            c = w["content"]
            L.append("| %d | %s | %d | %.0f | %d | %d | %d | %d | %d | %d |" % (
                w["window"], w["commit"][:7], w["runs"], w["seconds"], c.get("fallback", 0), c.get("exact", 0),
                c.get("differs", 0), c.get("missing", 0), c.get("extra", 0), c.get("adopted_uids", 0)))
    return "\n".join(L) + "\n"
