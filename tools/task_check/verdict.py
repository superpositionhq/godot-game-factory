"""The task check's rules: a probe's threshold and whether a value passes it, and whether a task is VALID.

Thresholds (a probe's `expect`):
- a literal (`value`): as written;
- calibrated (`calibrate: f`): s + f * (r - s) from the start's value s and the reference's r, both measured by this
  check. A start that measured nothing anchors on the reference alone: r moved MARGIN of |r| toward the start's side
  (below r for > and >=, above it for < and <=). A reference that measured nothing, a start and reference that
  measure the same, or a reference of 0 for a start that measured nothing (a share of nothing is no margin) leave no
  threshold: the probe fails as uncalibrated;
- relative to the start (`start_times: f`, `start_plus: d`): s * f or s + d; a start that measured nothing leaves no
  threshold.

A task is VALID when (the no-op case: the start, untouched, must fail the task; the oracle case: the reference must pass
every required check, as the Lab's own no-op and oracle check of a task holds them)
- the start builds, unless the task says it doesn't (a build check's `fails_at_start`: making it build is the task):
  then the start must not build, and that is the start failing the task (it is never played);
- with a reference: the reference passes every required check of every kind it is checked on (build, boot,
  log_absent, file_exists, package, every required probe); its checks that aren't required are notes, never decisive.
  A `package` check fails on every side (no grader packages a Godot game: check.NO_PACKAGE), so a required one makes
  the task INVALID;
- the start fails every required probe outside still_works (or doesn't build by design), and at least one of those is
  not a `seen` probe: a seen probe is a visual check a model reads, never the outcome that shows the bug;
- without a reference: the start fails every required probe outside still_works (or doesn't build by design);
- every probe the task names, required or not, has a threshold: the Lab's check stops on a probe it can't calibrate
  (`uncalibrated`), whichever it is;
- no check of either side is a task error (check.TASK_ERROR: a probe whose selector reads nothing even on the
  reference, a task play whose input didn't land on the reference): no version of the game can be graded by it;
- either way, every required probe of the task's `still_works` milestone already passes at the start: what still works
  must hold there, or the probe is broken and would fail every correct solution. A still-works probe the start has no
  samples for (its play crashed or ended early: the task's own bug) is no sign of a broken probe; one that finds
  nothing to measure in a start that ran is;
- a required check of weight 0 outside still_works that the start passes is a guard, not refused (it rewards
  nothing; a task may hold more guards than still_works' 32);
- a no-op scores zero: no check the start passes carries weight. The cloud's score is the weighted
  share of checks passed, so build, boot and still-works checks and anything else true of the start take `"weight": 0`;
- no required `code_judge`: a model reads the change in the Lab and nothing here can, so code review stays a quality
  check (`"required": false`).
Judges' screenshots and seen probes' crops are answered by the task's writer (check.check_task holds the verdict until
every required one is answered and agrees)."""

import math

from . import probes, tasks

JUDGES = ("judge", "code_judge")
SEEN_ONLY = ("no required probe outside still_works but seen ones: a seen probe is a visual check a model reads, never "
             "the outcome that shows the start failing the task")
TASK_ERROR = "task error"  # a check's detail starts so when no version of the game can be graded by it (the Lab's word)
MARGIN = 0.25  # a calibrated threshold whose start measured nothing: the reference's value, this share toward the start


class Uncalibrated(Exception):
    """A probe whose threshold can't be made (a start and reference measuring the same; a side that must be measured
    measuring nothing; a reference of 0 to anchor on): the task can't be graded by it. `start`, `fix`: what each side
    measured."""

    def __init__(self, message, start=None, fix=None):
        super().__init__(message)
        self.start, self.fix = start, fix


def threshold(expect, start=None, fix=None):
    """A probe's threshold from its expect: the literal, s + f * (r - s), s * f or s + d."""
    if "value" in expect:
        return float(expect["value"])
    if "calibrate" in expect:
        if start is None:
            return fix - MARGIN * abs(fix) if expect["op"] in (">", ">=") else fix + MARGIN * abs(fix)
        return start + expect["calibrate"] * (fix - start)
    if "start_times" in expect:
        return start * expect["start_times"]
    return start + expect["start_plus"]


def same(a, b):
    """Whether a start and a reference measure the same (within 1e-6 relative): nothing to calibrate between them."""
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)


def passes(value, op, limit):
    if op in ("==", "!="):
        equal = math.isclose(value, limit, rel_tol=1e-9, abs_tol=1e-9)
        return equal if op == "==" else not equal
    return {">": value > limit, ">=": value >= limit, "<": value < limit, "<=": value <= limit}[op]


def make_threshold(check, start_value, fix_value):
    """(threshold, start value, fix value) of probe `check` from its sides' measures (each `(value, why)` or a callable
    giving it, called only when the threshold needs that side). Raises Uncalibrated."""
    expect, relative = check["expect"], tasks.relative(check)
    if relative is None:
        return float(expect["value"]), None, None
    start, why = start_value() if callable(start_value) else start_value
    if start is None and relative == "start":
        raise Uncalibrated(f"{check['name']}: the start measured nothing ({why}), and the threshold is relative to it",
                           start)
    fix = None
    if relative == "calibrate":
        fix, fix_why = fix_value() if callable(fix_value) else fix_value
        if fix is None:
            raise Uncalibrated(f"{check['name']}: the reference measured nothing ({fix_why})", start, fix)
        if start is not None and same(start, fix):
            raise Uncalibrated(f"{check['name']}: the start and the reference both measure {probes.fmt(start)}, so "
                               "there is no threshold between them", start, fix)
        if start is None and same(fix, 0.0):  # the anchor's MARGIN of nothing is no margin
            raise Uncalibrated(f"{check['name']}: the start measured nothing ({why}) and the reference measured 0, so "
                               "there is no threshold", start, fix)
    return threshold(expect, start, fix), start, fix


def describe(check, value, limit, start, fix, why=None):
    """A probe's detail: "<describe> | measured X, threshold OP Y (start S, fix R): why none"."""
    detail = f"{check['describe']} | measured {probes.fmt(value)}, threshold {check['expect']['op']} {probes.fmt(limit)}"
    if fix is not None:
        detail += f" (start {probes.fmt(start)}, fix {probes.fmt(fix)})"
    elif start is not None:
        detail += f" (start {probes.fmt(start)})"
    return detail + (f": {why}" if why else "")


def noop_score(task, start):
    """(score, names): what doing nothing earns, the weighted share of the deterministic checks the start passes, and
    the passed checks that carry weight. Judges aren't measured here (`detail` "not asked")."""
    weights = {c["name"]: c["weight"] for _, c in tasks.checks(task) if c["kind"] not in JUDGES}
    total = sum(weights.values())
    names = [c["name"] for c in start["checks"]
             if c["name"] in weights and c["passed"] and weights[c["name"]] > 0
             and not str(c["detail"]).startswith("not asked")]
    return (round(sum(weights[n] for n in names) / total, 3) if total else 0.0), names


def verdict(task, reference, start):
    """(valid, why, notes) from the reference's and the start's check rows ({"checks": [{name, kind, passed,
    detail}]}). `reference` None: a start-only check."""
    why, notes = [], []
    every = {c["name"]: (group, c) for group, c in tasks.checks(task)}
    required = tasks.gating(task)
    still = tasks.still_works(task)
    build = tasks.fails_at_start(task)
    seen = {n for n, (_, c) in every.items() if c["kind"] == "probe" and c["measure"]["probe"] == "seen"}
    broken = [c for c in start["checks"] if build is not None and c["name"] == build["name"]
              and not str(c["detail"]).startswith("not asked")]
    if any(c["passed"] for c in broken):
        why.append(f"start builds, though {build['name']} says it doesn't (fails_at_start)")
    for c in start["checks"]:
        detail = str(c["detail"])
        if c["name"] in still and not c["passed"] and not detail.startswith("not asked") \
                and "no samples in the window" not in detail:  # a crash the task fixes leaves nothing to measure
            why.append(f"start fails still-works {c['name']}: {detail[:160]}")
    told = set()  # checks a reason already names
    if reference is not None:
        for c in reference["checks"]:
            if c["passed"]:
                continue
            spec = every.get(c["name"], (None, {}))[1]
            if c["kind"] in ("build", "boot") or c["name"] in required or spec.get("required", True):
                why.append(f"reference fails {c['name']}: {str(c['detail'])[:160]}")
                told.add(c["name"])
            elif not str(c["detail"]).startswith(("uncalibrated", TASK_ERROR)):  # those are reasons below
                notes.append(f"reference fails {c['name']} ({c['kind']}): {str(c['detail'])[:160]}")
    for side, rows in (("reference", reference), ("start", start)):
        for c in (rows or {}).get("checks", []):
            detail = str(c["detail"])
            if c["name"] in told:
                continue
            if detail.startswith("uncalibrated"):  # the Lab's check stops on it, required or not
                why.append(f"{c['name']} has no threshold: {detail[:160]}")
                told.add(c["name"])
            elif detail.startswith(TASK_ERROR):
                why.append(f"{c['name']} on the {side}: {detail[:160]}")
                told.add(c["name"])
    why.extend(f"{n} is a required code_judge: a model reads the change in the Lab and no check here can, so make it "
               "\"required\": false (code review is a quality check)" for n, (_, c) in every.items()
               if c["kind"] == "code_judge" and c.get("required", True))
    earned, names = noop_score(task, start)
    told = (required - still) | ({build["name"]} if build is not None else set())  # those have their own reasons below
    if earned and set(names) - told:
        why.append(f"a no-op scores {earned}, not 0: give {', '.join(n for n in names if n not in told)} "
                   "\"weight\": 0, or drop them")
    if reference is None and broken:  # a start-only check's gate: the start doesn't build by design
        return not why, why, notes
    gates = [c for c in start["checks"] if c["name"] in required and c["name"] not in still] + broken
    if not gates:
        why.append("no required probe outside still_works to check the start with")
    elif all(c["passed"] for c in gates):
        why.append("start already passes every required probe")
    elif not broken and not [c for c in gates if c["name"] not in seen]:
        why.append(SEEN_ONLY)
    else:  # every outcome is one issue of the thread: one the start already has rewards no work
        # (godot-write-tasks section 5)
        # A required check of weight 0 rewards nothing, so one the start passes is a guard wherever it sits (a task
        # with more guards than still_works holds): it gates, never pays, and is not refused for passing at the start.
        weight = {c["name"]: c["weight"] for _, c in tasks.checks(task)}
        why.extend(f"start already passes required probe {c['name']}" for c in gates
                   if c["passed"] and c not in broken and weight.get(c["name"], 1) > 0)
    return not why, why, notes
