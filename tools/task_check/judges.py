"""A `judge` check's screenshots, saved for a person or a local session to look at (docs/task-probes.md, 3.2).

Nothing here asks a model. The task check and the task try play each judge check's plays on their sides (check.Side,
the same plays the probes use) and save the screenshots the cloud's judge would be shown, so whoever runs the check
looks at them and answers the rubric:

- a judge with its own `plays` is shown each play's `shots` evenly spaced screenshots (taken at seconds x (i + 0.5) / N
  by the probe; a play another judge asks more of is played with the most asked, and `shots` of them are picked
  evenly through), and every screenshot its `shot` inputs take by name, in the order taken;
- a judge with no plays is shown the shared idle play ("look", 20 s, 6 screenshots) and the drive (22 s, 8) on the
  task's play_scene; a required one with no `route` either keeps the task from VALID (NO_OWN_PLAY, check.judged),
  since those never reach what a rubric asks;
- an item the pictures don't show scores 0 (UNSEEN): cannot be seen is a fail, never a pass, and ask.md says so;
- a judge with a `route` is also shown the developer's route file played by the checker as the Lab plays it (read from
  the graded copy: the reference in a task check, the agent's game in a try; 8 screenshots; check.Side.route_play),
  after its other plays; a route that can't be played (no such file, not a route) is said in the notes and shows
  nothing, and nothing stands for it;
- a judge is shown 20 screenshots of a side at most.

`save` writes them under <folder>/<check>/<side>/<play>_<nn>.png with <folder>/<check>/ask.md (the brief, the question,
the rubric, what each picture is); with `blind`, a copy of two sides under blind/A and blind/B whose mapping is
blind/key.json, so the looker can answer before knowing which side is which: the copy holds only the pictures both
sides have, and each side's own pictures and notes are in sides.md, never in the blind ask.md.

The task's writer scores the rubric into blind/answers.json, {"A": {item key: 0 to 1, ...}, "B": {...}}; a later task
check reads it (`kept`, `scored`) while the pictures it was given for are the same (pictures.json: each picture's
sha256), and a required judge holds the task's verdict until both sides are scored as the Lab's judge would have to
score them (check.check_task)."""

import hashlib
import json
import random
import re
import shutil
from pathlib import Path

from . import tasks

JUDGE_IMAGES = 20  # a judge check's screenshots of one side at most (the grader's own limit)
PLAY_SHOTS = 5  # a judge's screenshots of each of its own plays unless its `shots` says
SHARED = {"look": ("idle play, 20 s, no input", 20, 6), "drive": ("scripted drive, 22 s", 22, 8)}
EVEN_SHOT = re.compile(r"^shot_\d{2,3}\.png$")  # an evenly spaced screenshot; any other is one a `shot` input took
PASS, REQUIRED = 0.6, 0.5  # the judge's pass mark: weighted score at least PASS, no required item below REQUIRED
PENDING = "shots saved for {sides}, answer needed"
ANSWERED = "scored in blind/answers.json"
ANSWERS = "answers.json"  # under blind/
ROUTE = "route"  # the developer's route's play, as a judge's play name
NO_OWN_PLAY = ("no play of its own (no `plays`, no `route`): it is shown only the idle look and the drive, which never "
               "press the task's keys or leave a title screen, so it can't see what its rubric asks; give it plays "
               "that show each item at its moment")
UNSEEN = ("An item the pictures don't show (its moment isn't on screen, its subject is off view, hidden or not reached) "
          "scores 0 on that side: cannot be seen is a fail, never a pass. On the reference that means its plays must "
          "be fixed to show it, never the item eased.")


def judge(c):
    """A `judge` check with its defaults: `plays` (task plays with theirs), `shots`, `before`, `reference`, `route`."""
    out = dict(c)
    out["plays"] = [tasks.play(p) for p in c.get("plays") or []]
    out.setdefault("shots", PLAY_SHOTS)
    out.setdefault("before", False)
    out.setdefault("reference", False)
    out.setdefault("route", None)
    out["rubric"] = [{"key": i["key"], "criterion": i["criterion"], "required": bool(i.get("required", False)),
                      "weight": int(i.get("weight", 1))} for i in c.get("rubric") or []]
    return out


def judges(task):
    """The task's `judge` checks (not code or actions judges), in order, with their defaults."""
    return [judge(c) for _, c in tasks.checks(task) if c["kind"] == "judge"]


def play_shots(task):
    """{task play name: the evenly spaced screenshots taken of it}: the most any judge check naming it asks, so one
    play serves each (and the probes that name it)."""
    found = {}
    for c in judges(task):
        for p in c["plays"]:
            found[p["name"]] = max(found.get(p["name"], 0), c["shots"])
    return found


def plays(check):
    """What a judge check is shown of a side, in order: [(play, label, shots)], `play` "look", "drive" or a task play,
    `shots` how many of its evenly spaced screenshots (None: every one taken)."""
    if check["plays"]:
        found = [(p, f"task play {p['name']}, {p['seconds']} s", check["shots"]) for p in check["plays"]]
    else:
        found = [(name, label, None) for name, (label, _, _) in SHARED.items()]
    if check.get("route"):
        found.append((ROUTE, f"the developer's route {check['route']}, played by the checker", None))
    return found


def spread(items, count):
    """`count` of `items`, evenly through them and in their order (all of them when there are no more)."""
    items = list(items)
    if count is None or len(items) <= count:
        return items
    return [items[min(len(items) - 1, int((i + 0.5) * len(items) / count))] for i in range(count)]


def even_times(seconds, count):
    """When the probe takes a play's `count` evenly spaced screenshots: at seconds x (i + 0.5) / count."""
    return [round(seconds * (i + 0.5) / count, 2) for i in range(count)]


def taken(probe, files):
    """A play's screenshots by name, in the order taken, each once and only those it wrote: the probe's list, else the
    PNG files it left (sorted)."""
    names = (probe or {}).get("screenshots") if isinstance(probe, dict) else None
    if not isinstance(names, list):
        names = sorted(n for n in files if n.lower().endswith(".png"))
    return [n for n in dict.fromkeys(n for n in names if isinstance(n, str)) if n in files]


def chosen(names, shots):
    """The screenshots of one play a judge is shown: `shots` of the evenly spaced ones (shot_NN.png), evenly through
    them, and every named one, in the order taken."""
    even = [n for n in names if EVEN_SHOT.fullmatch(n)]
    keep = set(spread(even, shots)) | {n for n in names if n not in even}
    return [n for n in names if n in keep]


def selection(check, played):
    """[(play name, label, [(file name in the play, saved name)])] of one side, 20 screenshots at most in all.
    `played`: {play name: (probe dict or None, {file: bytes})} of the plays made (a missing play shows nothing)."""
    out, left = [], JUDGE_IMAGES
    for play, label, shots in plays(check):
        name = play if isinstance(play, str) else play["name"]
        probe, files = played.get(name, (None, {}))
        picked = chosen(taken(probe, files), shots)[:left]
        left -= len(picked)
        out.append((name, label, [(n, f"{name}_{i + 1:02d}.png") for i, n in enumerate(picked)]))
    return out


def named(file):
    """A named screenshot's name (shot_<name>.png), or None for an evenly spaced one."""
    return None if EVEN_SHOT.fullmatch(file) else file[len("shot_"):-len(".png")] if file.startswith("shot_") else file


def blind_key(sides, rng=None):
    """{"A": side, "B": side} for two sides, in an order the looker can't guess."""
    order = list(sides)
    (rng or random.SystemRandom()).shuffle(order)
    return dict(zip("AB", order))


def blind_copy(base, sides, rng=None, key=None):
    """The blind copy of two side folders under `base` (<base>/<side>/): blind/A and blind/B, whose sides are in
    blind/key.json; `key` ({"A": side, "B": side}) keeps an earlier copy's letters, else they are drawn (blind_key).
    (key, notes)."""
    key, notes = key or blind_key(sides, rng), []
    # Only pictures both sides have go in: a side with fewer (a play cut short) would be told apart by its count.
    both = set.intersection(*({p.name for p in (base / side).iterdir()} for side in sides))
    for side in sides:
        only = sorted({p.name for p in (base / side).iterdir()} - both)
        if only:
            notes.append(f"{side}: {len(only)} picture(s) the other side lacks, left out of the blind copy "
                         f"({', '.join(only)})")
    for letter, side in key.items():
        (base / "blind" / letter).mkdir(parents=True)
        for name in sorted(both):
            shutil.copy2(base / side / name, base / "blind" / letter / name)
    (base / "blind" / "key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return key, notes


def ask_text(task, check, sides, notes=(), blind=False, saved=None):
    """ask.md: the brief, the question, the rubric, the plays and their pictures, how to answer."""
    rubric = "\n".join(f"| {i['key']} | {'yes' if i['required'] else 'no'} | {i['weight']} | "
                       f"{i['criterion'].replace('|', '/')} |" for i in check["rubric"])
    lines = [f"# Judge check {check['name']}", "",
             f"{'Required' if check.get('required', True) else 'Optional'} check, weight {check.get('weight', 1)}.",
             "", "## The brief", "", task.get("instruction", "").strip(), "", "## The question", "",
             check["question"].strip(), "", "## The rubric", "",
             f"Score each item from 0 (not at all) to 1 (fully) from what the pictures show. {UNSEEN} A side passes "
             f"when its weighted score is at least {PASS} and no required item is below {REQUIRED}.", "",
             "| key | required | weight | criterion |", "| --- | --- | --- | --- |", rubric, "",
             "## The pictures", ""]
    if not check["plays"] and not check["route"]:
        lines += [f"This judge has {NO_OWN_PLAY}" + (": the task isn't VALID until it has." if check.get("required", True)
                                                    else "."), ""]
    for play, label, shots in plays(check):
        name = play if isinstance(play, str) else play["name"]
        if play == ROUTE:
            lines.append(f"- `{name}_NN.png`: {label}: the presses and releases its file lists, 8 evenly spaced "
                         "screenshots, after the other plays (none when it couldn't be played: see the notes).")
            continue
        if isinstance(play, str):
            _, seconds, count = SHARED[play]
            what = f"every one of its {count} screenshots, at {', '.join(f'{t:g}' for t in even_times(seconds, count))} s"
        else:
            inputs = play["inputs"]
            names = [i["shot"] for i in inputs if "shot" in i]
            what = (f"{len(inputs)} scripted input(s)" if inputs else "no input") \
                + (f", scene {play['scene']}" if play.get("scene") else "") \
                + (f", args {' '.join(play['args'])}" if play.get("args") else "") \
                + f"; {shots} evenly spaced screenshots, about one every {play['seconds'] / shots:.2g} s" \
                + (f", and the named ones: {', '.join(names)}" if names else "")
        lines.append(f"- `{name}_NN.png`: {label}: {what}.")
    lines += ["", "Each side's folder holds the pictures in time order, play by play."]
    if blind:  # a side's picture count or its notes would tell a blind scorer which side is which
        lines.append("Which pictures each side has, and any side's notes, are in `sides.md`: open it with the key.")
    else:
        lines += side_lines(saved)
    if check["before"] or check["reference"]:
        shown = [x for x, on in (("the start as BEFORE", check["before"]), ("the reference as REFERENCE",
                                                                             check["reference"])) if on]
        lines += ["", f"In the cloud the judge is also shown {' and '.join(shown)}, beside the developer's game, the "
                      "same plays at the same moments."]
    if check["route"]:
        lines += ["", f"The route file `{check['route']}` is read from the graded copy (the reference here) and played "
                      "on each side shown, as the Lab plays it. Where it couldn't be played the notes say why, and the "
                      "judge sees no route: score only what the pictures show."]
    lines += ["", "## How to answer", ""]
    if blind:
        lines += ["`blind/A/` and `blind/B/` hold the pictures both of two side folders have; which is which is in "
                  "`blind/key.json`. Score every rubric item for A and for B first, each as if it were the developer's "
                  "game, then open the key.", ""]
    if blind:
        example = "{" + ", ".join(f'"{i["key"]}": 0.0' for i in check["rubric"]) + "}"
        letters = "A" if len(sides) == 1 else "A and B"
        lines += [f"Write the scores into `blind/{ANSWERS}`, one object per letter ({letters}), every rubric item "
                  "from 0 to 1:", "", "```json",
                  "{" + ", ".join(f'"{x}": {example}' for x in ("A", "B")[:len(sides)]) + "}", "```", "",
                  "Then check the task again: it reads the scores while the pictures stay the same "
                  "(`pictures.json`); pictures that changed need new scores."]
    if set(sides) >= {"start", "reference"}:
        lines += ["", "A required judge holds the task's verdict until both sides are scored. The reference must pass "
                  f"(weighted score at least {PASS}, no required item below {REQUIRED}). A judge of what still looks as "
                  "it did (in `still_works`) must pass on the start too; any other required judge must have every "
                  "required item below 0.5 on the start. Never ease an item to make it so: reword it so the "
                  "pictures decide it, or fix the plays."]
    elif "reference" in sides:
        lines += ["", "A required judge holds the task's verdict until the reference is scored, and it must pass."]
    elif "agent" in sides:
        lines += ["Score the agent's game the same way, before calling the task too easy or held: the try's own "
                  "number leaves judges out."]
    if notes and not blind:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    return "\n".join(lines).rstrip() + "\n"


def side_lines(saved):
    """One line per side: its pictures, by file name and what each is."""
    lines = []
    for side, rows in (saved or {}).items():
        files = [f"{s} ({'named ' + named(f) if named(f) else f})" for _, _, picked in rows for f, s in picked]
        lines.append(f"- `{side}/`: {len(files)} picture(s)" + (": " + ", ".join(files) if files else ""))
    return lines


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig")), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as exc:
        return None, f"{Path(path).name} can't be read ({type(exc).__name__}: {str(exc)[:120]})"


def kept(folder):
    """What an earlier task check's judge-shots folder holds, read before the folder is made again: {check: {"key":
    {letter: side}, "sides": {side: {"scores": its answer or None, "pictures": {name: sha256}}}, "problem": why the
    answers can't be read, or None, "raw": that file's bytes, kept as written}}."""
    out, folder = {}, Path(folder)
    if not folder.is_dir():
        return out
    for base in sorted(p for p in folder.iterdir() if p.is_dir()):
        key, _ = _json(base / "blind" / "key.json")
        if not (isinstance(key, dict) and key and set(key) <= {"A", "B"}):
            continue
        answers, problem = _json(base / "blind" / ANSWERS)
        if answers is not None and not isinstance(answers, dict):
            answers, problem = None, 'it is {"A": {...}, "B": {...}}'
        try:
            raw = (base / "blind" / ANSWERS).read_bytes() if problem else None
        except OSError:
            raw = None
        made, _ = _json(base / "pictures.json")
        out[base.name] = {"key": key, "problem": problem, "raw": raw,
                          "sides": {side: {"scores": (answers or {}).get(letter),
                                           "pictures": (made or {}).get(side) if isinstance(made, dict) else None}
                                    for letter, side in key.items()}}
    return out


def scored(check, scores):
    """(passed, why) of one side's scores ({item key: 0 to 1}) by the Lab judge's pass mark: the weighted score at
    least PASS and no required item below REQUIRED. ValueError when they aren't a score of every item."""
    keys = [i["key"] for i in check["rubric"]]
    if not isinstance(scores, dict) or sorted(scores) != sorted(keys) or not all(
            isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1 for v in scores.values()):
        raise ValueError(f"a side's answer scores every rubric item ({', '.join(keys)}) from 0 to 1")
    total = sum(i["weight"] for i in check["rubric"]) or 1
    value = sum(i["weight"] * scores[i["key"]] for i in check["rubric"]) / total
    low = [i["key"] for i in check["rubric"] if i["required"] and scores[i["key"]] < REQUIRED]
    why = f"weighted {value:.2f}" + (f", required item(s) below {REQUIRED}: {', '.join(low)}" if low else "")
    return value >= PASS and not low, why


def save(task, check, played, folder, blind=False, notes=(), rng=None, held=None):
    """Save judge check `check`'s screenshots of each side under <folder>/<check>/: `played` {side: {play name: (probe,
    files)}}. With `blind`, the blind copy (of one or two sides), keeping `held`'s letters (kept()[check]) and carrying
    over each side's scores whose pictures are unchanged. Its record: {"sides": {side: [saved names]}, "blind":
    whether there is a blind copy (its key stays in its folder), "answered": {side: {"passed", "why", "low"}}, "notes",
    "status"}."""
    base = Path(folder) / check["name"]
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    saved, notes = {}, list(notes)
    for side, made in played.items():
        rows = selection(check, made)
        saved[side] = rows
        (base / side).mkdir()
        for name, _, picked in rows:
            files = made.get(name, (None, {}))[1]
            for f, s in picked:
                (base / side / s).write_bytes(files[f])
            if name not in made:
                notes.append(f"{side}: {name} wasn't played")
            elif not picked:
                notes.append(f"{side}: {name} took no screenshots")
    pictures = {side: {f.name: digest(f.read_bytes()) for f in sorted((base / side).iterdir())} for side in saved}
    (base / "pictures.json").write_text(json.dumps(pictures, indent=2) + "\n", encoding="utf-8")
    key, answered = None, {}
    if blind and saved and all(pictures.values()):
        old = (held or {}).get("key")
        key, more = blind_copy(base, list(saved), rng, old if old and sorted(old.values()) == sorted(saved) else None)
        notes += more
        sides = (held or {}).get("sides") or {}
        answers = {}
        for letter, side in key.items():
            scores = (sides.get(side) or {}).get("scores")
            if scores is None:
                continue
            if (sides.get(side) or {}).get("pictures") != pictures[side]:
                notes.append(f"{side}: its pictures changed since they were scored, so its scores were dropped")
                continue
            answers[letter] = scores
            try:
                passed, why = scored(check, scores)
            except ValueError as exc:
                notes.append(f"blind/{ANSWERS}: {exc}")
                continue
            answered[side] = {"passed": passed, "why": why,
                              "low": all(scores[i["key"]] < REQUIRED for i in check["rubric"] if i["required"])}
        if answers:
            (base / "blind" / ANSWERS).write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
        elif (held or {}).get("raw") and key == old:  # an answer file that can't be read stays as written, to fix
            (base / "blind" / ANSWERS).write_bytes(held["raw"])
            notes.append(f"blind/{ANSWERS}: {held['problem']}")
    (base / "ask.md").write_text(ask_text(task, check, list(saved), notes, key is not None, saved), encoding="utf-8")
    if key is not None:  # what would unblind the scorer, kept beside the key
        (base / "sides.md").write_text("\n".join(["# Each side's pictures", ""] + side_lines(saved)
                                                 + (["", "## Notes", ""] + [f"- {n}" for n in notes] if notes else []))
                                       + "\n", encoding="utf-8")
    done = bool(saved) and sorted(answered) == sorted(saved)
    return {"sides": {s: [n for _, _, p in rows for _, n in p] for s, rows in saved.items()},
            "blind": key is not None, "answered": answered, "notes": notes,
            "status": ANSWERED if done else PENDING.format(sides="/".join(saved) or "no side")}


def line(name, record):
    """The line a run prints and keeps for one judge check."""
    return f"judge {name}: {record['status']}"
