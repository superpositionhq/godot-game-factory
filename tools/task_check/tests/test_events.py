"""Events with no Godot: a measure's `since` (its window counted from the first sample whose reading meets the event's
expect), a shot's `when` as the play spec hands it to the probe, and the misses the probe writes for a press something
else takes (COVERED) and a shot whose event never came (NEVER), as the checker reads them."""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import FakeProject, probe, side, task_with

from task_check import check, godot, probes, tasks

GATE = {"probe": "objects", "select": {"name": "Gate"}, "field": "count"}
OPENS = {"measure": GATE, "expect": {"op": ">=", "value": 1}}


def gate_play(opens_at=None, seconds=10, every=0.5):
    """A play answer: the player's height is the play time (y = t), and the objects query of the gate matches one row
    from `opens_at` on (None: never)."""

    def play(seconds_, shots, queries):
        times = [round(i * every, 6) for i in range(int(seconds / every))]
        found = {"format": "godot-probe/1", "ended": "time", "seconds": float(seconds_), "player": "Hero",
                 "inputs_sent": 0, "screenshots": [], "track": [[t, 0.0, t, 0.0] for t in times], "camera": [],
                 "measures": {}, "inputs_missed": []}
        for q in (queries or {}).get("queries", []):
            found["measures"][q["id"]] = [
                {"t": t, "rows": [{"name": "Gate"}] if opens_at is not None and t >= opens_at - 1e-9 else []}
                for t in times]
        return found, "Godot Engine v4.7.2.stable.official\n"

    return play


def climbed(window=None, at=None, agg="delta", within=None, op=">=", value=1):
    """A player measure of its height read from the gate's opening on."""
    since = {"measure": GATE, "expect": {"op": op, "value": value}}
    if within is not None:
        since["within"] = within
    m = {"probe": "player", "field": "y", "agg": agg, "since": since}
    if window is not None:
        m["window"] = window
    if at is not None:
        m["at"] = at
    return tasks.measure(m)


def probe_json(opens_at, seconds=10):
    task = task_with(probe(measure=dict(GATE)))
    return gate_play(opens_at, seconds)(seconds, 0, probes.query_file(probes.plan(task)["look"]))[0]


class Since(unittest.TestCase):
    def test_an_event_has_its_defaults(self):
        found = tasks.event({"measure": GATE, "expect": {"op": ">=", "value": 1}})
        self.assertEqual((found["within"], found["expect"]), (None, {"op": ">=", "value": 1.0}))
        self.assertEqual(found["measure"]["of"], "count")
        self.assertNotIn("since", tasks.measure({"probe": "player", "field": "y"}), "kept only where set")

    def test_the_play_samples_the_events_measure_beside_the_checks_own(self):
        task = task_with(probe(measure={"probe": "player", "field": "y", "since": OPENS}))
        (query,) = probes.plan(task)["look"]
        self.assertEqual((query["kind"], query["select"]), ("objects", {"name": "Gate"}))

    def test_the_event_is_the_first_sample_that_meets_its_expect(self):
        self.assertEqual(probes.event_time(climbed()["since"], probe_json(2.2)), (2.5, None),
                         "known to the play's sampling step")
        self.assertEqual(probes.event_time(climbed(within=2.5)["since"], probe_json(2.2)), (2.5, None))
        self.assertEqual(probes.event_time(climbed(within=2.0)["since"], probe_json(2.2)),
                         (None, "its event never happened (its objects count never read >= 1 in the play's first 2 s)"))
        self.assertEqual(probes.event_time(climbed()["since"], probe_json(None)),
                         (None, "its event never happened (its objects count never read >= 1)"))

    def test_window_and_at_count_from_the_event(self):
        found = probe_json(3.0)
        self.assertEqual(probes.measured(climbed(window=[0, 1]), found), (1.0, None), "y from 3 to 4")
        self.assertEqual(probes.measured(climbed(window=[1, 2], agg="first"), found), (4.0, None))
        self.assertEqual(probes.measured(climbed(at=[0.5], agg="last"), found), (3.5, None))
        self.assertEqual(probes.measured(climbed(agg="first"), found), (3.0, None), "by default, from the event on")
        self.assertEqual(probes.measured(climbed(at="end", agg="last"), found), (9.5, None))
        self.assertEqual(probes.measured(climbed(window=[0, 1]), probe_json(9.5))[0], 0.0, "one sample in the window")

    def test_a_measure_whose_event_never_came_reads_nothing(self):
        self.assertEqual(probes.measured(climbed(window=[0, 1]), probe_json(None)),
                         (None, "its event never happened (its objects count never read >= 1)"))

    def test_a_graded_play_whose_event_never_comes_fails_the_check(self):
        task = task_with(probe(measure={"probe": "player", "field": "y", "since": OPENS, "window": [0, 1],
                                        "agg": "delta"}, expect={"op": ">=", "value": 0.5}))
        found = check.Grade(task, "start", side("start", FakeProject(gate_play(None)), task), None, {}).run()
        row = found["checks"][0]
        self.assertFalse(row["passed"])
        self.assertIn("its event never happened", row["detail"])
        found = check.Grade(task, "start", side("start", FakeProject(gate_play(3.0)), task), None, {}).run()
        self.assertTrue(found["checks"][0]["passed"], found["checks"][0])

    def test_a_reference_whose_event_never_comes_leaves_a_calibrated_check_uncalibrated(self):
        task = task_with(probe(measure={"probe": "player", "field": "y", "since": OPENS, "window": [0, 1],
                                        "agg": "delta"}, expect={"op": ">=", "calibrate": 0.5}))
        start = side("start", FakeProject(gate_play(3.0)), task)
        reference = side("reference", FakeProject(gate_play(None)), task)
        row = check.Grade(task, "reference", start, reference, {}).run()["checks"][0]
        self.assertFalse(row["passed"])
        self.assertIn("uncalibrated", row["detail"])
        self.assertIn("its event never happened", row["detail"])


class ShotWhen(unittest.TestCase):
    WHEN = {"measure": {"probe": "widgets", "select": {"name": "Banner"}, "field": "count"},
            "expect": {"op": ">=", "value": 1}, "within": 3}

    def test_a_shots_when_is_kept_as_an_event(self):
        (row,) = tasks.inputs([{"t": 1, "shot": "win", "when": self.WHEN}])
        self.assertEqual(row["when"]["within"], 3.0)
        self.assertEqual(tasks.inputs([{"t": 1, "shot": "plain"}]), [{"t": 1.0, "shot": "plain"}])

    def test_the_probe_is_handed_the_query_it_reads_every_frame(self):
        inputs = tasks.inputs([{"t": 1, "shot": "win", "when": self.WHEN},
                               {"t": 2, "shot": "text", "when": {
                                   "measure": {"probe": "ui", "select": {"kind": "text"}, "field": "text",
                                               "match": "^SCORE 5$"}, "expect": {"op": ">=", "value": 1}}},
                               {"t": 3, "key": "<Keyboard>/w", "press": True}])
        win, text, key = probes.probe_inputs(inputs)
        query = {"kind": "widgets", "select": {"name": "Banner"}, "fields": []}
        self.assertEqual(win["when"], {"query": {"id": probes.query_id(query), **query}, "field": "count",
                                       "of": "count", "match": None, "op": ">=", "value": 1.0, "within": 3.0})
        self.assertEqual((text["when"]["field"], text["when"]["match"], text["when"]["query"]["fields"]),
                         ("text", "^SCORE 5$", ["text"]))
        self.assertNotIn("within", text["when"])
        self.assertEqual(key, {"t": 3.0, "key": "<Keyboard>/w", "press": True})
        self.assertEqual(probes.probe_inputs(probes.probe_inputs(inputs)), [win, text, key], "made once")

    def test_the_play_spec_says_it_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = []

            class Machine:
                editor = Path("godot_console.exe")
                heavy = False

                def job(self, label, argv, cwd, timeout, gpu=False):
                    spec = json.loads(Path(argv[argv.index("-taskProbe") + 1]).read_text(encoding="utf-8"))
                    specs.append(spec)
                    return godot.Result(0, "", 1.0)

            godot.Project(tmp, Machine(), "t").play(5, 2, 60, inputs=tasks.inputs([{"t": 1, "shot": "win",
                                                                                     "when": self.WHEN}]))
            self.assertEqual(specs[0]["inputs"][0]["when"]["query"]["kind"], "widgets")

    def test_a_shot_whose_event_never_came_is_a_missed_input(self):
        never = {"t": 1.0, "kind": "shot_when", "target": "win", "why": check.NEVER}
        play = {"name": "p", "seconds": 5, "inputs": [{"t": 1.0, "shot": "win", "when": self.WHEN}]}
        self.assertEqual(check.missed({"inputs_missed": [never]}, play), [never])
        self.assertEqual(check.missed({"inputs_missed": [dict(never, kind="shot", why="its name isn't ...")]}, play),
                         [], "a shot's bad name changes nothing the game did")


class Covered(unittest.TestCase):
    def test_a_click_or_a_tap_something_else_takes_is_a_miss_no_mark_excuses(self):
        for kind, mark in (("click", {}), ("click", {"optional": True}), ("click", {"disabled": True}), ("tap", {})):
            row = {"t": 0.5, "kind": kind, "target": "Buy", "why": check.COVERED}
            spot = {"widget": "Buy", "click": True, **mark} if kind == "click" else {"tap": {"widget": "Buy"}}
            play = {"name": "shop", "seconds": 5, "inputs": [{"t": 0.5, **spot}]}
            self.assertEqual(check.missed({"inputs_missed": [row]}, play), [row], (kind, mark))

    def test_the_probes_words_are_the_checkers(self):
        folder = Path(check.__file__).parent / "task_probe"
        script = (folder / "inputs.gd").read_text(encoding="utf-8")
        self.assertIn(f'const COVERED := "{check.COVERED}"', script)
        self.assertIn(f'const NEVER := "{check.NEVER}"', script)
        self.assertEqual(check.NEVER, "its event never happened")
        self.assertNotIn(check.DISABLED, check.COVERED)
        self.assertNotEqual(check.COVERED, check.NO_CONTROL)
        self.assertIn('"covered"', (folder / "queries" / "widgets.gd").read_text(encoding="utf-8"))

    def test_a_scrolled_click_says_why_it_ended_unpressed(self):
        """A click whose scroll area was scrolled to it in the play's last frame never presses: its own miss."""
        script = (Path(check.__file__).parent / "task_probe" / "inputs.gd").read_text(encoding="utf-8")
        self.assertIn('"its scroll area was scrolled to it, but the play ended before the press"', script)


if __name__ == "__main__":
    unittest.main()
