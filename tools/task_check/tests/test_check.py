"""A task checked end to end with fake Godot: the sides' plays and builds, calibration, the grades, a whole check's
result file; a commit materialized from a real git repo; the files and command lines a build and a play hand Godot."""

import contextlib
import copy
import gc
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from helpers import NO_FIX, FakeProject, measuring, probe, side, task_with

from task_check import check, cli, godot, probes, seeds, tasks, verdict

WALLS = {"component": "CastlePiece", "tag": "Wall"}
PROJECT = ('config_version=5\n\n[application]\n\nconfig/name="Metro Runner"\nrun/main_scene="res://scenes/Main.tscn"\n'
           'config/features=PackedStringArray("4.7", "Forward Plus")\n\n[autoload]\n\n'
           'Scenarios="*res://game/scenarios.gd"\n\n[rendering]\n\nrenderer/rendering_method="forward_plus"\n')
_probe_patch = None


def fake_probe_package(root):
    """A stand-in for tools/task_check/task_probe: its files, and a run's leftovers that never reach a copy."""
    source = Path(root) / "task_probe"
    (source / "queries").mkdir(parents=True)
    (source / "task_probe.gd").write_text("extends Node\n", encoding="utf-8")
    (source / "task_probe.gd.uid").write_text("uid://b0taskprobe\n", encoding="utf-8")
    (source / "queries" / "objects.gd").write_text("extends RefCounted\n", encoding="utf-8")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "junk.pyc").write_bytes(b"x")
    return source


def setUpModule():
    global _probe_patch
    folder = tempfile.mkdtemp()
    _probe_patch = mock.patch.object(seeds, "PROBE_SOURCE", fake_probe_package(folder))
    _probe_patch.start()
    _probe_patch.folder = folder


def tearDownModule():
    _probe_patch.stop()
    shutil.rmtree(_probe_patch.folder, ignore_errors=True)


def grade(task, mode, start, reference=None, thresholds=None):
    return check.Grade(task, mode, start, reference, {} if thresholds is None else thresholds).run()


class Grades(unittest.TestCase):
    def test_a_literal_probe_passes_on_the_measured_number_and_its_queries_reach_the_probe(self):
        task = task_with(probe(), probe("walls", measure={"probe": "objects", "select": WALLS, "field": "y",
                                                          "of": "max"}, expect={"op": ">", "value": 100}),
                         probe("seen", measure={"probe": "camera", "field": "occluded", "agg": "any"},
                               expect={"op": "==", "value": 0}))
        game = FakeProject(measuring(120))
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertTrue(all(c["passed"] for c in found["checks"]), found["checks"])
        details = [c["detail"] for c in found["checks"]]
        self.assertEqual(details[0], "The hero stands on the ground. | measured 120, threshold >= 0")
        self.assertTrue(details[1].endswith("| measured 120, threshold > 100"))
        self.assertEqual(found["probes"]["walls"], {"value": 120.0, "threshold": 100.0, "start": None, "fix": None})
        (look,) = game.plays
        self.assertEqual((look["seconds"], look["shots"], look["inputs"]), (20, 6, None))
        self.assertEqual((look["scene"], look["args"], look["player"]), (None, [], None))
        self.assertEqual({q["kind"] for q in look["queries"]["queries"]}, {"objects", "camera"})

    def test_a_play_that_wrote_no_probe_fails_its_probes_saying_why(self):
        task = task_with(probe())
        found = grade(task, "reference", side("start", FakeProject(), task),
                      side("reference", FakeProject(measuring(0, crash=True)), task))
        self.assertFalse(found["checks"][0]["passed"])
        self.assertTrue(found["checks"][0]["detail"].endswith(
            "measured nothing, threshold >= 0: no samples in the window (the play wrote no probe file)"))

    def test_a_task_play_is_played_once_with_its_inputs_scene_args_and_sampling(self):
        play = {"name": "arena", "seconds": 8, "scene": "res://scenes/Arena.tscn", "args": ["-autoPlay"],
                "every": 0.25, "inputs": [{"t": 0.2, "teleport": [1, 2, 3], "yaw": 90},
                                          {"t": 1, "key": "<Mouse>/leftButton", "press": True}]}
        task = task_with(probe("a", play=play, measure={"probe": "objects", "select": WALLS, "field": "count"},
                               expect={"op": ">=", "value": 1}),
                         probe("b", play=play, measure={"probe": "log", "pattern": "Godot Engine"},
                               expect={"op": "==", "value": 1}),
                         play_scene="res://scenes/Town.tscn", play_args=["-scenario", "2"])
        game = FakeProject(measuring(5))
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertTrue(all(c["passed"] for c in found["checks"]), found["checks"])
        (played,) = game.plays
        self.assertEqual((played["seconds"], played["shots"], played["scene"], played["args"], played["every"]),
                         (8, 2, "res://scenes/Arena.tscn", ["-autoPlay"], 0.25), "the play's own scene and args")
        self.assertEqual(played["queries"]["every"], 0.25)
        self.assertEqual(played["inputs"], [{"t": 0.2, "teleport": [1.0, 2.0, 3.0], "yaw": 90.0},
                                            {"t": 1.0, "key": "<Mouse>/leftButton", "press": True}])

    def test_a_task_play_without_a_scene_or_args_plays_the_tasks(self):
        task = task_with(probe("a", play={"name": "a", "seconds": 5}),
                         probe("b", play={"name": "b", "seconds": 5, "args": []}),
                         probe("c", play={"name": "c", "seconds": 5, "scene": None}),
                         play_scene="res://scenes/Town.tscn", play_args=["-scenario", "2"])
        game = FakeProject(measuring(5))
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([(p["scene"], p["args"]) for p in game.plays],
                         [("res://scenes/Town.tscn", ["-scenario", "2"]), ("res://scenes/Town.tscn", []),
                          (None, ["-scenario", "2"])])

    def test_the_drive_plays_its_scripted_inputs_on_the_tasks_scene_with_its_player(self):
        task = task_with(probe(play="drive"), play_scene="res://scenes/Town.tscn", play_args=["-scenario", "1"],
                         player={"tag": "Player", "name": "Hero*"})
        game = FakeProject(measuring(5))
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        (drive,) = game.plays
        self.assertEqual((drive["seconds"], drive["shots"], drive["scene"], drive["args"]),
                         (22, 8, "res://scenes/Town.tscn", ["-scenario", "1"]))
        self.assertEqual(drive["inputs"], check.DRIVE)
        self.assertEqual(drive["player"], {"tag": "Player", "name": "Hero*"})
        self.assertEqual({i["key"] for i in check.DRIVE},
                         {"<Keyboard>/w", "<Keyboard>/a", "<Keyboard>/d", "<Keyboard>/space"})
        self.assertEqual(tasks.inputs(check.DRIVE), check.DRIVE, "the drive's inputs are as a task play's are sent")

    def test_a_mobile_games_drive_is_played_by_touch(self):
        task = task_with(probe(play="drive"))
        phone = FakeProject(measuring(5), platform="portrait")
        grade(task, "reference", side("start", FakeProject(), task), side("reference", phone, task))
        (drive,) = phone.plays
        self.assertEqual((drive["seconds"], drive["shots"], drive["inputs"]), (22, 8, check.MOBILE_DRIVE))
        self.assertEqual(tasks.inputs(check.MOBILE_DRIVE), check.MOBILE_DRIVE, "as a task play's touches are sent")

    def test_a_calibrated_threshold_is_made_from_the_start_and_the_reference(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        start, reference = FakeProject(measuring(-500)), FakeProject(measuring(100))
        sides, kept = (side("start", start, task), side("reference", reference, task)), {}
        ref = grade(task, "reference", *sides, kept)
        own = grade(task, "start", *sides, kept)
        self.assertEqual(ref["checks"][0]["detail"],
                         "The hero stands on the ground. | measured 100, threshold >= -200 (start -500, fix 100)")
        self.assertTrue(ref["checks"][0]["passed"])
        self.assertFalse(own["checks"][0]["passed"])
        self.assertEqual(own["probes"]["hero_on_ground"],
                         {"value": -500.0, "threshold": -200.0, "start": -500.0, "fix": 100.0})
        self.assertEqual((len(start.plays), len(reference.plays)), (1, 1), "each side played once")

    def test_a_start_and_reference_that_measure_the_same_fail_as_uncalibrated(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}),
                         probe("walls", measure={"probe": "objects", "select": WALLS, "field": "y", "of": "max"}))
        sides = (side("start", FakeProject(measuring(100)), task),
                 side("reference", FakeProject(measuring(100 + 1e-5)), task))
        found = grade(task, "reference", *sides)
        self.assertFalse(found["checks"][0]["passed"])
        self.assertTrue(found["checks"][0]["detail"].startswith(
            "uncalibrated: hero_on_ground: the start and the reference both measure 100"))
        self.assertEqual(found["probes"]["hero_on_ground"]["start"], 100.0)
        self.assertTrue(found["checks"][1]["passed"], "every other probe is still measured")

    def test_a_reference_that_measures_nothing_or_a_start_relative_start_that_measures_nothing(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        found = grade(task, "reference", side("start", FakeProject(measuring(0)), task),
                      side("reference", FakeProject(measuring(0, crash=True)), task))
        self.assertIn("the reference measured nothing", found["checks"][0]["detail"])
        relative = task_with(probe(expect={"op": ">=", "start_plus": 5}), seed=NO_FIX)
        found = grade(relative, "start", side("start", FakeProject(measuring(0, crash=True)), relative))
        self.assertIn("the start measured nothing", found["checks"][0]["detail"])

    def test_a_start_that_measures_nothing_anchors_a_calibrated_threshold_on_the_reference(self):
        task = task_with(probe(expect={"op": ">=", "calibrate": 0.5}))
        found = grade(task, "reference", side("start", FakeProject(measuring(0, crash=True)), task),
                      side("reference", FakeProject(measuring(100)), task))
        self.assertTrue(found["checks"][0]["detail"].endswith("measured 100, threshold >= 75 (start nothing, fix 100)"))

    def test_a_threshold_relative_to_the_start_needs_only_the_start(self):
        task = task_with(probe(expect={"op": ">=", "start_plus": 50}),
                         probe("twice", expect={"op": ">=", "start_times": 2}), seed=NO_FIX)
        start = FakeProject(measuring(60))
        found = grade(task, "start", side("start", start, task))
        self.assertEqual([c["passed"] for c in found["checks"]], [False, False])
        self.assertTrue(found["checks"][0]["detail"].endswith("measured 60, threshold >= 110 (start 60)"))
        self.assertEqual(len(start.plays), 1, "the start played once")

    def test_needs_and_the_checks_a_start_isnt_asked(self):
        task = task_with({"kind": "build", "name": "player_builds"},
                         {"kind": "boot", "name": "boots_clean", "seconds": 10, "needs": ["player_builds"]},
                         {"kind": "judge", "name": "looks_right", "question": "q", "required": False,
                          "rubric": [{"key": "k", "criterion": "c"}]},
                         probe(needs=["boots_clean"]))
        broken = FakeProject(measuring(5), build_exit=6)
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", broken, task))
        self.assertEqual([(c["passed"], c["detail"]) for c in found["checks"]],
                         [(False, "build failed (exit 6)"), (False, "not run: needs player_builds"),
                          (True, check.NOT_JUDGED), (False, "not run: needs boots_clean")])
        start = grade(task, "start", side("start", FakeProject(measuring(-5)), task))
        self.assertEqual([c["passed"] for c in start["checks"]], [True, True, True, False])
        self.assertEqual(start["checks"][0]["detail"], "not asked: the start is checked on its probes")

    def test_a_boot_and_its_log(self):
        task = task_with({"kind": "boot", "name": "boots_clean", "seconds": 10},
                         {"kind": "log_absent", "name": "no_errors", "pattern": "SCRIPT ERROR"},
                         probe())
        found = grade(task, "reference", side("start", FakeProject(), task),
                      side("reference", FakeProject(measuring(5)), task))
        self.assertEqual([c["detail"] for c in found["checks"][:2]],
                         ["ran 10 s with no crash or fatal error", "0 matching log line(s)"])
        crashed = grade(task, "reference", side("start", FakeProject(), task),
                        side("reference", FakeProject(measuring(5, crash=True)), task))
        self.assertEqual(crashed["checks"][0]["detail"], "crashed")

    def test_a_crash_is_the_engines_crash_lines_never_a_script_error(self):
        for line in ("CrashHandlerException: Program crashed with signal 11", "handle_crash: Program crashed with signal 11",
                     "Dumping the backtrace. Please include this when reporting the bug", "ERROR: Out of memory"):
            self.assertTrue(check.fatal(line), line)
        for line in ("SCRIPT ERROR: Invalid access to property or key 'hp' on a base object of type 'Nil'.",
                     "ERROR: Condition \"!is_inside_tree()\" is true.", "", None):
            self.assertFalse(check.fatal(line), line)

def answering(rows=None, missed=(), seconds=10):
    """A play answer whose every objects or widgets query matches `rows` in each sample and whose `inputs_missed` is
    `missed`."""

    def play(seconds_, shots, queries):
        found = {"format": "godot-probe/1", "ended": "time", "seconds": float(seconds_), "player": "Hero",
                 "inputs_sent": 2, "screenshots": [], "track": [[i * 0.5, 0.0, 0.0, 0.0] for i in range(seconds)],
                 "camera": [], "measures": {}, "inputs_missed": list(missed)}
        for q in (queries or {}).get("queries", []):
            found["measures"][q["id"]] = [{"t": i * 0.5, "rows": list(rows or [])} for i in range(seconds)]
        return found, "Godot Engine v4.7.2.stable.official\n"

    return play


def first_row(task, mode, start, reference):
    """(passed, detail) of the task's first check in a grade of `mode`."""
    row = grade(task, mode, start, reference)["checks"][0]
    return row["passed"], row["detail"]


class TaskErrors(unittest.TestCase):
    """What no version of the game can be graded by, as the Lab's grade reads it: a select that reads nothing on the
    reference, a task play whose input doesn't land on the reference."""

    def test_a_select_that_reads_nothing_on_the_reference_is_a_task_error(self):
        task = task_with(probe(measure={"probe": "objects", "select": {"name": "Lamp*"}, "field": "y", "of": "max",
                                        "agg": "max"}, expect={"op": ">=", "value": 1}))
        ref = side("reference", FakeProject(answering([])), task)
        passed, detail = first_row(task, "reference", None, ref)
        self.assertFalse(passed)
        self.assertTrue(detail.startswith("task error: "), detail)
        self.assertIn("in the reference's look, its select", detail)
        self.assertIn("the check reads nothing even on the task's own fix", detail)
        found = side("reference", FakeProject(answering([{"name": "Lamp_1", "y": 2.0}])), task)
        self.assertEqual(first_row(task, "reference", None, found)[0], True, "a select that reads something is graded")

    def test_nothing_matching_is_the_outcome_when_0_passes(self):
        gone = probe(measure={"probe": "objects", "select": {"name": "Crate*"}, "field": "count", "agg": "last"},
                     expect={"op": "==", "value": 0})
        task = task_with(gone)
        ref = side("reference", FakeProject(answering([])), task)
        self.assertEqual(first_row(task, "reference", None, ref)[0], True, "\"the crates are gone\" reads 0 of nothing")
        shown = task_with(probe(measure={"probe": "objects", "select": {"name": "Crate*"}, "field": "count",
                                         "agg": "last"}, expect={"op": ">=", "value": 1}))
        passed, detail = first_row(shown, "reference", None, side("reference", FakeProject(answering([])), shown))
        self.assertFalse(passed)
        self.assertIn("the task's own fix fails it", detail)

    def test_only_a_count_or_a_widgets_combination_reads_0_of_nothing(self):
        """As the Lab's Godot grader (probes.zero_when_none): an objects measure combined by `any` that reads nothing on
        the reference is a task error even where 0 would pass; a widgets one is "not shown"."""
        def task(kind):
            return task_with(probe(measure={"probe": kind, "select": {"name": "Crate*"},
                                            "field": "active" if kind == "objects" else "visible",
                                            "of": "any", "agg": "last"}, expect={"op": "==", "value": 0}))
        objects = task("objects")
        passed, detail = first_row(objects, "reference", None, side("reference", FakeProject(answering([])), objects))
        self.assertFalse(passed)
        self.assertTrue(detail.startswith("task error: "), detail)
        self.assertIn("the check reads nothing even on the task's own fix", detail)
        widgets = task("widgets")
        self.assertEqual(first_row(widgets, "reference", None,
                                   side("reference", FakeProject(answering([])), widgets))[0], True,
                         "a hidden control is matched by nothing: 0 of nothing")
        self.assertTrue(check.zero_when_none({"probe": "components", "field": "count"}))
        self.assertFalse(check.zero_when_none({"probe": "components", "field": "speed", "of": "sum"}))

    def test_a_ui_select_that_reads_nothing_on_the_reference_is_a_task_error(self):
        task = task_with(probe(measure={"probe": "ui", "select": {"kind": "text", "text": "LAP"}, "field": "signature",
                                        "agg": "changes"}, expect={"op": ">=", "value": 1}))
        passed, detail = first_row(task, "reference", None, side("reference", FakeProject(answering([])), task))
        self.assertFalse(passed)
        self.assertTrue(detail.startswith("task error: "), detail)
        self.assertIn("its select", detail)
        shown = side("reference", FakeProject(answering([{"kind": "text", "text": "LAP 2/3", "x": 0.1, "y": 0.1,
                                                          "w": 0.1, "h": 0.05}])), task)
        self.assertFalse(first_row(task, "reference", None, shown)[1].startswith("task error"),
                         "a select that shows something is graded")
        gone = task_with(probe(measure={"probe": "ui", "select": {"kind": "text", "text": "GAME OVER"},
                                        "field": "count", "agg": "last"}, expect={"op": "==", "value": 0}))
        self.assertEqual(first_row(gone, "reference", None, side("reference", FakeProject(answering([])), gone))[0],
                         True, "\"the banner is gone\" reads 0 of nothing")

    def test_an_input_that_doesnt_land_on_the_reference_is_a_task_error(self):
        tap = {"name": "open_menu", "seconds": 5, "inputs": [{"t": 1, "key": "<Keyboard>/m", "press": True},
                                                             {"t": 1.2, "key": "<Keyboard>/m", "press": False},
                                                             {"t": 2, "widget": "Begin", "click": True}]}
        task = task_with(probe(play=tap, measure={"probe": "player", "field": "y", "agg": "max"},
                               expect={"op": ">=", "value": 0}))
        miss = [{"t": 2.0, "kind": "click", "target": "Begin", "why": "no visible control matches it"}]
        ref = side("reference", FakeProject(answering(missed=miss)), task)
        passed, detail = first_row(task, "reference", None, ref)
        self.assertFalse(passed)
        self.assertIn("task error: ", detail)
        self.assertIn("in the reference's play open_menu, an input did not land (click Begin at 2 s", detail)
        good = side("reference", FakeProject(answering()), task)
        start = side("start", FakeProject(answering(missed=miss)), task)
        passed, detail = first_row(task, "start", start, good)
        self.assertEqual((passed, detail.split(" | ")[1]), (False, "the play's input did not land: click Begin at 2 s "
                                                                  "(no visible control matches it)"),
                         "the start's own miss is the start failing it")
        shot = [{"t": 2.0, "kind": "shot", "target": "menu", "why": "not written"}]
        self.assertTrue(first_row(task, "reference", None, side("reference", FakeProject(answering(missed=shot)), task))[0],
                        "a named screenshot not taken changes nothing the game did")

    def test_an_optional_click_that_found_nothing_to_press_is_no_miss_and_any_other_miss_still_is(self):
        """A click on what a game shows only sometimes (`optional`): when no shown Control matches it, the play went
        on and nothing missed; a click that isn't optional, or an optional one whose Control took no press, missed."""
        play = {"name": "open_menu", "seconds": 5, "inputs": [{"t": 0.5, "widget": "Confirm", "click": True,
                                                               "optional": True},
                                                              {"t": 2, "widget": "Begin", "click": True}]}
        self.assertEqual(tasks.inputs(play["inputs"]), [{"t": 0.5, "widget": "Confirm", "click": True, "optional": True},
                                                        {"t": 2.0, "widget": "Begin", "click": True}],
                         "the probe is sent the click as written")
        task = task_with(probe(play=play, measure={"probe": "player", "field": "y", "agg": "max"},
                               expect={"op": ">=", "value": 0}))
        nothing = {"t": 0.5, "kind": "click", "target": "Confirm", "why": check.NO_CONTROL}
        self.assertEqual(first_row(task, "reference", None,
                                   side("reference", FakeProject(answering(missed=[nothing])), task))[0], True)
        untaken = {"t": 0.5, "kind": "click", "target": "Confirm (Button)",
                   "why": "the click at its centre didn't press it (another control is over it, or it takes no click)"}
        good = side("reference", FakeProject(answering()), task)
        passed, detail = first_row(task, "start", side("start", FakeProject(answering(missed=[untaken])), task), good)
        self.assertFalse(passed)
        self.assertIn("the play's input did not land: click Confirm (Button) at 0.5 s", detail)
        begin = {"t": 2.0, "kind": "click", "target": "Begin", "why": check.NO_CONTROL}
        passed, detail = first_row(task, "start", side("start", FakeProject(answering(missed=[nothing, begin])), task),
                                   good)
        self.assertFalse(passed, "a click that isn't optional still misses beside one that is")
        self.assertIn("the play's input did not land: click Begin at 2 s", detail)
        self.assertNotIn("Confirm", detail)
        plain = copy.deepcopy(task)
        del plain["milestones"][-1]["checks"][0]["play"]["inputs"][0]["optional"]
        passed, detail = first_row(plain, "start", side("start", FakeProject(answering(missed=[nothing])), plain), good)
        self.assertFalse(passed)
        self.assertIn("the play's input did not land: click Confirm at 0.5 s", detail)

    def test_a_click_no_control_takes_is_made_on_its_text_shown_in_one_place(self):
        """A click no Control takes by name, class or caption is made on its text as shown (the Lab's Godot grader,
        game grader 1.18.0): the probe tries it before the NO_CONTROL miss, holds the left button TEXT_PRESS, and the
        inputs after it wait for the release; text shown in two places or more is a miss that `optional` doesn't
        excuse, since it is not check.NO_CONTROL."""
        folder = Path(check.__file__).parent / "task_probe"
        script = (folder / "inputs.gd").read_text(encoding="utf-8")
        click = script[script.index("func _click(row: Dictionary"):script.index("func _click_text(")]
        self.assertLess(click.index("if _click_text(row, want):"),
                        click.index(f'_miss(row, "click", want, "{check.NO_CONTROL}")'))
        self.assertIn("const TEXT_PRESS := 0.1", script)
        send = script[script.index("func send(elapsed: float)"):script.index("func warm(")]
        self.assertLess(send.index("_press_text(elapsed)"),
                        send.index("while _again.is_empty() and _text_click.is_empty() and not waiting"))
        finish = script[script.index("func finish()"):script.index("func _flush()")]
        self.assertIn("TEXT_UNPRESSED", finish)
        self.assertIn(f'("{check.NO_CONTROL}, and "', script, "the miss of text shown twice begins as NO_CONTROL")
        scan = (folder / "ui_scan.gd").read_text(encoding="utf-8")
        self.assertIn("static func by_shown_text(texts: Array, want: String) -> Dictionary:", scan)
        self.assertIn("overlap >= 0.5 * minf(a[\"h\"], b[\"h\"])", scan, "pieces of one line: heights overlap by half")
        self.assertIn("> 6.0 * maxf(a[\"h\"], b[\"h\"])", scan, "a gap of at most 6 of the line's heights")

        play = {"name": "open_shop", "seconds": 5, "inputs": [{"t": 1, "widget": "Shop", "click": True,
                                                               "optional": True}]}
        task = task_with(probe(play=play, measure={"probe": "player", "field": "y", "agg": "max"},
                               expect={"op": ">=", "value": 0}))
        twice = {"t": 1.0, "kind": "click", "target": "Shop",
                 "why": check.NO_CONTROL + ', and its text is shown in 2 places, not one: "Shop" at (0.200, 0.100); '
                                           '"Shop" at (0.800, 0.900)'}
        good = side("reference", FakeProject(answering()), task)
        passed, detail = first_row(task, "start", side("start", FakeProject(answering(missed=[twice])), task), good)
        self.assertFalse(passed, "an optional click on text shown twice still missed")
        self.assertIn("the play's input did not land: click Shop at 1 s", detail)

    def test_the_probe_plays_up_to_the_schemas_longest_play(self):
        """A task play lasts up to 1200 s (the schema's, the Lab game grader 1.18.0's): the probe plays a spec's seconds
        that long and holds a touch's hold and spread, a teleport's hold and a pin's hold to it."""
        root = Path(check.__file__).parents[2]
        schema = json.loads((root / "docs" / "schemas" / "game-task.schema.json").read_text(encoding="utf-8"))
        longest = schema["$defs"]["TaskPlay"]["properties"]["seconds"]["maximum"]
        self.assertEqual(longest, 1200)
        script = (Path(check.__file__).parent / "task_probe" / "inputs.gd").read_text(encoding="utf-8")
        self.assertIn(f"const PLAY_SECONDS := {longest}.0", script)
        self.assertIn('"over": clampf(Find.num(row, "over"), 0.0, PLAY_SECONDS)', script)
        self.assertIn('"hold": clampf(Find.num(row, "hold"), 0.0, PLAY_SECONDS)', script)
        for func in ("func _start_hold(", "func _pin("):
            body = script[script.index(func):]
            self.assertIn('clampf(Find.num(row, "hold"), 0.0, PLAY_SECONDS)', body[:body.index("\nfunc ", 1)], func)
        main = (Path(check.__file__).parent / "task_probe" / "task_probe.gd").read_text(encoding="utf-8")
        self.assertIn(f'clampf(Find.num(_spec, "seconds", 20.0), 1.0, {longest}.0)', main)

    def test_the_probes_words_for_a_click_that_found_nothing_are_the_checkers(self):
        """check.NO_CONTROL is what the probe's inputs.gd writes of a widget click no shown Control matches."""
        script = (Path(check.__file__).parent / "task_probe" / "inputs.gd").read_text(encoding="utf-8")
        self.assertIn(f'_miss(row, "click", want, "{check.NO_CONTROL}")', script)

    def test_a_disabled_click_on_its_disabled_button_has_landed_and_each_mark_excuses_only_its_own_miss(self):
        """A click on a button the game disables by design (`disabled`): when the probe found that button shown but
        disabled, the click landed (and did nothing). Without the mark that is a miss; so is an `optional` click on
        it, and a `disabled` click no button matched."""
        locked = {"t": 0.5, "kind": "click", "target": "Locked Door",
                  "why": 'a button matches it (Locked (Button) by its caption "Locked Door"), shown but disabled: the '
                         "click does nothing"}
        nothing = {"t": 0.5, "kind": "click", "target": "Locked Door", "why": check.NO_CONTROL}

        def play_with(**mark):
            return {"name": "pick", "seconds": 5, "inputs": [dict({"t": 0.5, "widget": "Locked Door", "click": True},
                                                                  **mark)]}
        marked = play_with(disabled=True)
        self.assertEqual(tasks.inputs(marked["inputs"]), [{"t": 0.5, "widget": "Locked Door", "click": True,
                                                           "disabled": True}], "the probe is sent the click as written")
        self.assertEqual(check.missed({"inputs_missed": [locked]}, marked), [])
        self.assertEqual(check.missed({"inputs_missed": [nothing]}, marked), [nothing],
                         "a disabled click that found no button missed")
        self.assertEqual(check.missed({"inputs_missed": [locked]}, play_with()), [locked])
        self.assertEqual(check.missed({"inputs_missed": [locked]}, play_with(optional=True)), [locked],
                         "optional excuses only a click that found nothing")
        self.assertEqual(check.missed({"inputs_missed": [dict(locked, t=1.0)]}, marked), [dict(locked, t=1.0)],
                         "only the marked click's own row")
        task = task_with(probe(play=marked, measure={"probe": "player", "field": "y", "agg": "max"},
                               expect={"op": ">=", "value": 0}))
        self.assertEqual(first_row(task, "reference", None,
                                   side("reference", FakeProject(answering(missed=[locked])), task))[0], True)
        good = side("reference", FakeProject(answering()), task)
        plain = copy.deepcopy(task)
        del plain["milestones"][-1]["checks"][0]["play"]["inputs"][0]["disabled"]
        passed, detail = first_row(plain, "start", side("start", FakeProject(answering(missed=[locked])), plain), good)
        self.assertFalse(passed)
        self.assertIn("the play's input did not land: click Locked Door at 0.5 s", detail)

    def test_the_probes_words_for_a_disabled_button_are_the_checkers(self):
        """check.DISABLED is in what the probe's inputs.gd writes of a widget click whose button is shown but
        disabled."""
        script = (Path(check.__file__).parent / "task_probe" / "inputs.gd").read_text(encoding="utf-8")
        self.assertIn(f'), {check.DISABLED}: the click does nothing"', script)

    def test_a_click_on_a_control_scrolled_out_of_view_is_a_miss_no_mark_excuses(self):
        """A click whose control is scrolled out of its container's view sent nothing: a miss, optional, disabled or
        neither, on the reference a task error. Only an optional click that found nothing at all stays excused."""
        out = {"t": 0.5, "kind": "click", "target": "Bottom",
               "why": "a control matches it (Bottom (Button) by name), scrolled out of its container's view: a press "
                      "at its centre lands outside the view"}
        nothing = dict(out, why=check.NO_CONTROL)

        def play_with(**mark):
            return {"name": "pick", "seconds": 5, "inputs": [dict({"t": 0.5, "widget": "Bottom", "click": True},
                                                                  **mark)]}
        for mark in ({}, {"optional": True}, {"disabled": True}, {"optional": True, "disabled": True}):
            self.assertEqual(check.missed({"inputs_missed": [out]}, play_with(**mark)), [out], mark)
        self.assertEqual(check.missed({"inputs_missed": [nothing]}, play_with(optional=True)), [])
        task = task_with(probe(play=play_with(optional=True), measure={"probe": "player", "field": "y", "agg": "max"},
                               expect={"op": ">=", "value": 0}))
        passed, detail = first_row(task, "reference", None,
                                   side("reference", FakeProject(answering(missed=[out])), task))
        self.assertFalse(passed)
        self.assertIn("task error: ", detail)
        self.assertIn("an input did not land (click Bottom at 0.5 s", detail)

    def test_the_probes_words_for_a_scrolled_out_control_are_the_checkers(self):
        """check.SCROLLED_OUT is in what the probe's inputs.gd writes of a click or a touch whose control is scrolled
        out of its container's view, and that why holds neither of the words the marks excuse."""
        script = (Path(check.__file__).parent / "task_probe" / "inputs.gd").read_text(encoding="utf-8")
        self.assertIn(f'), {check.SCROLLED_OUT}: a press at its centre lands ', script)
        self.assertNotEqual(check.SCROLLED_OUT, check.NO_CONTROL)
        self.assertNotIn(check.DISABLED, check.SCROLLED_OUT)


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True, check=True).stdout


def make_game(root, project=PROJECT):
    """A tiny Godot game repo: main with an LFS texture (its object in .git/lfs/objects), a Tasks/ folder that never
    reaches a copy, and a fix commit."""
    repo = Path(root) / "metro-runner"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "dev@example.invalid")
    git(repo, "config", "user.name", "dev")
    if project is not None:
        (repo / "project.godot").write_bytes(project.encode("utf-8"))
    (repo / "game").mkdir()
    (repo / "game" / "metro.gd").write_text("extends Node\n", encoding="utf-8")
    (repo / "Tasks").mkdir()
    (repo / "Tasks" / "x.json").write_text("{}", encoding="utf-8")
    data = b"a texture's bytes"
    import hashlib
    oid = hashlib.sha256(data).hexdigest()
    store = repo / ".git" / "lfs" / "objects" / oid[:2] / oid[2:4]
    store.mkdir(parents=True)
    (store / oid).write_bytes(data)
    (repo / "assets").mkdir()
    (repo / "assets" / "wall.png").write_bytes(
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(data)}\n".encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    start = git(repo, "rev-parse", "HEAD").decode().strip()
    (repo / "game" / "metro.gd").write_text("extends Node\nvar a := 1\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "fix")
    fix = git(repo, "rev-parse", "HEAD").decode().strip()
    return repo, start, fix, data


class Seeds(unittest.TestCase):
    def test_a_commit_is_materialized_with_its_lfs_objects_the_probe_and_no_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, data = make_game(tmp)
            made = seeds.materialize(repo, start, Path(tmp) / "copy")
            copy = Path(tmp) / "copy"
            self.assertEqual((copy / "assets" / "wall.png").read_bytes(), data)
            self.assertEqual((copy / "game" / "metro.gd").read_text(encoding="utf-8"), "extends Node\n")
            self.assertFalse((copy / "Tasks").exists(), "a task's answers never reach a copy")
            self.assertEqual(made["linked"] + made["copied"], 1)
            seeds.add_probe(copy)
            addon = copy / "addons" / "task_probe"
            self.assertTrue((addon / "task_probe.gd").is_file())
            self.assertTrue((addon / "queries" / "objects.gd").is_file() and (addon / "task_probe.gd.uid").is_file(),
                            "the addon's own files, .uid too")
            self.assertFalse((addon / "__pycache__").exists(), "a run's leftovers stay out")
            company = seeds.saves_company(copy)
            settings = (copy / "project.godot").read_text(encoding="utf-8")
            self.assertEqual(settings, PROJECT.replace(
                'config/features=PackedStringArray("4.7", "Forward Plus")\n',
                'config/features=PackedStringArray("4.7", "Forward Plus")\nconfig/use_custom_user_dir=true\n'
                f'config/custom_user_dir_name="{company}"\n').replace(
                '[autoload]\n\n', '[autoload]\n\nTaskProbe="*res://addons/task_probe/task_probe.gd"\n'),
                "the probe's autoload first, the copy's own user data folder, and every other line as committed")
            seeds.add_probe(copy)
            self.assertEqual((copy / "project.godot").read_text(encoding="utf-8"), settings, "added again over the first")
            seeds.remove(copy)
            self.assertTrue((repo / ".git" / "lfs" / "objects").is_dir())

    def test_what_a_tasks_agent_never_sees_never_reaches_a_copy(self):
        for path in ("Tasks/a.json", "tasks/a.json", "History/2026/x.md", "DATASET/a.bin", "Dataset.zip", "dataset.ZIP"):
            self.assertTrue(seeds.answer(path), path)
        for path in ("game/Tasks/a.json", "game/History.gd", "Datasets/a", "Dataset.zip.import", "TasksX/a"):
            self.assertFalse(seeds.answer(path), path)

    def test_an_lfs_object_is_linked_on_its_drive_and_copied_where_it_cant_be(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, _, data = make_game(tmp)
            made = seeds.materialize(repo, start, Path(tmp) / "linked")
            wall = Path("assets") / "wall.png"
            self.assertEqual((made["linked"], made["copied"]), (1, 0), "the store's own file: it costs no disk")
            self.assertEqual(os.stat(Path(tmp) / "linked" / wall).st_nlink, 2)

            def other_drive(source, target):
                raise OSError(18, "Invalid cross-device link")

            with mock.patch.object(seeds.os, "link", other_drive):
                made = seeds.materialize(repo, start, Path(tmp) / "copied")
            self.assertEqual((made["linked"], made["copied"]), (0, 1))
            self.assertEqual(((Path(tmp) / "copied" / wall).read_bytes(), os.stat(Path(tmp) / "copied" / wall).st_nlink),
                             (data, 1), "a copy of its own, never left out")

    def test_a_missing_lfs_object_and_another_engine_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, _, _ = make_game(tmp)
            shutil.rmtree(repo / ".git" / "lfs")
            with self.assertRaisesRegex(FileNotFoundError, "lfs fetch"):
                seeds.materialize(repo, start, Path(tmp) / "copy")
            for name, project in (("old", PROJECT.replace('"4.7"', '"4.3"')), ("next", PROJECT.replace('"4.7"', '"4.8"')),
                                  ("bare", "config_version=5\n"), ("none", None)):
                folder = Path(tmp) / name
                folder.mkdir()
                if project:
                    (folder / "project.godot").write_text(project, encoding="utf-8")
                with self.assertRaisesRegex(seeds.WrongEngine, "must be Godot 4.7 projects", msg=name):
                    seeds.add_probe(folder)
            self.assertEqual(seeds.engine_of(Path(tmp) / "old"), ["4.3", "Forward Plus"])
            (Path(tmp) / "ok").mkdir()
            (Path(tmp) / "ok" / "project.godot").write_text("\ufeff" + PROJECT.replace("\n", "\r\n"), encoding="utf-8")
            seeds.add_probe(Path(tmp) / "ok")
            self.assertIn('TaskProbe="*res://addons/task_probe/task_probe.gd"\nScenarios=',
                          (Path(tmp) / "ok" / "project.godot").read_text(encoding="utf-8"))

    def test_the_probes_lines_win_over_any_line_of_the_games(self):
        """The engine reads a section written twice as one, a later line of a setting winning and the autoloads loading
        in the order they first appear (Godot 4.7.2, headless: tools/task_check/probe_tests' project holds these lines
        and its keys play checks the probe loaded first, with the copy's own user data folder)."""
        company = "TaskProbe.0123456789ab"
        probe = 'TaskProbe="*res://addons/task_probe/task_probe.gd"'
        for name, extra in (
                ("a quoted key in a second [autoload]", '\n[autoload]\n\n"TaskProbe"="*res://game/fake.gd"\n'),
                ("autoload sections twice", '\n[autoload]\n\nA="*res://a.gd"\n\n[autoload]\n\nTaskProbe = "*res://b.gd"\n'),
                ("the user folder off in a second [application]",
                 '\n[application]\n\nconfig/use_custom_user_dir=false\n"config/custom_user_dir_name"="Own"\n'),
                ("a multi-line value", '\n[input]\n\njump={\n"deadzone": 0.5,\n"events": []\n}\n')):
            text = seeds.with_probe(PROJECT + extra, company)
            self.assertEqual(seeds.settings_errors(text, company), [], name)
            values = seeds.effective(text)
            self.assertEqual([k for k in values if k.startswith("autoload/")][0], "autoload/TaskProbe", name)
            self.assertEqual((values["autoload/TaskProbe"], values["application/config/use_custom_user_dir"],
                              values["application/config/custom_user_dir_name"]),
                             ('"*res://addons/task_probe/task_probe.gd"', "true", f'"{company}"'), name)
            self.assertEqual(text.count("TaskProbe="), 1, name)
            self.assertEqual(seeds.with_probe(text, company), text, f"{name}: added twice is added once")
        self.assertIn('jump={\n"deadzone": 0.5,\n"events": []\n}', seeds.with_probe(
            PROJECT + '\n[input]\n\njump={\n"deadzone": 0.5,\n"events": []\n}\n', company), "a value over lines kept whole")
        self.assertTrue(probe in seeds.with_probe(PROJECT, company))
        # a carriage return at a line's end (a file written with Windows' line ends twice over) is white space
        crlf = seeds.with_probe(PROJECT.replace("\n", "\r\n"), company)
        self.assertEqual(seeds.settings_errors(crlf, company), [])
        self.assertEqual(seeds.effective(crlf)["autoload/Scenarios"], '"*res://game/scenarios.gd"')
        # an autoload set before every section, which the engine loads first, moves in right after the probe's
        before = PROJECT.replace("config_version=5\n", 'config_version=5\nautoload/Early="*res://early.gd"\n'
                                 '"autoload/Late one"="*res://late.gd"\n')
        text = seeds.with_probe(before, company)
        self.assertEqual(seeds.settings_errors(text, company), [])
        self.assertIn('[autoload]\n\nTaskProbe="*res://addons/task_probe/task_probe.gd"\nEarly="*res://early.gd"\n'
                      '"Late one"="*res://late.gd"\nScenarios=', text)
        self.assertEqual([k for k in seeds.effective(text) if k.startswith("autoload/")],
                         ["autoload/TaskProbe", "autoload/Early", "autoload/Late one", "autoload/Scenarios"])
        self.assertEqual(seeds.with_probe(text, company), text)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "project.godot").write_text(before, encoding="utf-8")
            seeds.add_probe(tmp)
            self.assertEqual((Path(tmp) / "project.godot").read_text(encoding="utf-8"),
                             seeds.with_probe(before, seeds.saves_company(tmp)))
        # the last guard: what it finds is a bug of the edit, and says so
        with mock.patch.object(seeds, "with_probe", lambda text, company: text), tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "project.godot").write_text(PROJECT, encoding="utf-8")
            with self.assertRaisesRegex(seeds.UnsafeSettings, r"didn't win \(a bug of seeds.with_probe\): autoload/TaskProbe is not set"):
                seeds.add_probe(tmp)
        self.assertTrue(issubclass(seeds.UnsafeSettings, seeds.WrongEngine), "the task is INVALID, as for an engine")

    def test_a_project_without_autoloads_gets_the_section(self):
        bare = 'config_version=5\n\n[application]\n\nconfig/features=PackedStringArray("4.7")\n'
        self.assertEqual(seeds.set_setting(bare, "autoload", *seeds.AUTOLOAD, first=True),
                         bare + '\n[autoload]\n\nTaskProbe="*res://addons/task_probe/task_probe.gd"\n')
        own = bare + '\n[autoload]\n\nA="*res://a.gd"\nTaskProbe="*res://old.gd"\n\n[input]\n\nx={\n"a": [1]\n}\n'
        self.assertEqual(seeds.set_setting(own, "autoload", *seeds.AUTOLOAD, first=True),
                         bare + '\n[autoload]\n\nTaskProbe="*res://addons/task_probe/task_probe.gd"\nA="*res://a.gd"\n'
                         '\n[input]\n\nx={\n"a": [1]\n}\n', "a line of that name is replaced, the rest kept")
        self.assertEqual(seeds.set_setting(bare, "application", "config/name", '"X"'),
                         'config_version=5\n\n[application]\n\nconfig/features=PackedStringArray("4.7")\n'
                         'config/name="X"\n')

# The free-space floor is the machine's (its config, its disk): it decides no test here.
@mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0)
class Whole(unittest.TestCase):
    def check(self, task, projects, tmp):
        """check_task with the scratch copies made for real and Godot faked: `projects` {side: FakeProject}."""
        repo, start, fix, _ = make_game(tmp)
        task["seed"] = {**task["seed"], "commit": start}
        if "reference" in task["seed"]:
            task["seed"]["reference"] = fix
        raw = json.dumps(task).encode()

        names = {start[:12]: "start", fix[:12]: "reference"}

        def project(folder, machine, label):
            found = projects[names[Path(folder).name]]
            found.folder, found.label = Path(folder), label
            return found

        with mock.patch.object(godot, "Project", project), \
                mock.patch.object(godot.Machine, "for_project", classmethod(lambda cls, p, d=False: cls(Path(p), None))):
            return check.check_task(repo, task, raw, Path(tmp) / "scratch", Path(tmp) / "out", log=lambda *a: None)

    def test_a_valid_task_with_a_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds"},
                             {"kind": "boot", "name": "boots_clean", "seconds": 10, "needs": ["player_builds"]},
                             probe(expect={"op": ">=", "calibrate": 0.5}, needs=["boots_clean"]))
            result = self.check(task, {"start": FakeProject(measuring(-500)),
                                       "reference": FakeProject(measuring(100))}, tmp)
            self.assertEqual((result["verdict"], result["reasons"], result["notes"]), ("VALID", [], []))
            self.assertEqual(result["probes"]["hero_on_ground"]["start"], -500.0)
            self.assertEqual(result["probes"]["hero_on_ground"]["reference"], 100.0)
            self.assertEqual(result["probes"]["hero_on_ground"]["threshold"], -200.0)
            self.assertEqual(result["start"]["slots"], "direct")
            kept = json.loads((Path(tmp) / "out" / "probe-task.json").read_text(encoding="utf-8"))
            self.assertEqual(kept["verdict"], "VALID")
            self.assertTrue((Path(tmp) / "out" / "probe-task" / "start" / "look" / "probe.json").is_file())
            self.assertFalse((Path(tmp) / "scratch").exists(), "the scratch copies are deleted")

    def test_a_start_that_doesnt_build_or_already_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds"}, probe())
            result = self.check(task, {"start": FakeProject(build_exit=6), "reference": FakeProject()}, tmp)
            self.assertEqual(result["reasons"], ["start doesn't build: the game as the task started didn't build "
                                                 "(exit 6)"])
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds", "weight": 0}, probe(), seed=NO_FIX)
            result = self.check(task, {"start": FakeProject(measuring(10))}, tmp)
            self.assertEqual((result["verdict"], result["reasons"]),
                             ("INVALID", [verdict.NO_REFERENCE, "start already passes every required probe"]))

    def test_a_start_that_doesnt_build_by_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds",
                                                                        "fails_at_start": True}]},
                                         {"name": "graded", "checks": [probe(needs=["player_builds"])]}])
            start = FakeProject(measuring(-5), build_exit=6)
            result = self.check(task, {"start": start, "reference": FakeProject(measuring(5))}, tmp)
            self.assertEqual(result["verdict"], "VALID", result["reasons"])
            self.assertEqual(start.plays, [], "a start that doesn't build is never played")

    def test_a_task_with_no_reference_is_never_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds", "weight": 0}, probe(), seed=NO_FIX)
            result = self.check(task, {"start": FakeProject(measuring(-10))}, tmp)
            self.assertEqual((result["verdict"], result["reasons"]), ("INVALID", [verdict.NO_REFERENCE]),
                             "a start that fails as it should still proves nothing without the oracle side")

    def test_another_engine_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp, project=PROJECT.replace('"4.7"', '"4.3"'))
            task = task_with(probe())
            task["seed"] = {**task["seed"], "commit": start, "reference": fix}
            result = check.check_task(repo, task, b"{}", Path(tmp) / "scratch", Path(tmp) / "out", log=lambda *a: None)
            self.assertEqual(result["verdict"], "INVALID")
            self.assertTrue(result["reasons"][0].startswith("start: project.godot names Godot 4.3 in "
                                                            "config/features"), result["reasons"])

    def test_a_machine_that_cant_run_godot_is_an_error_never_a_verdict(self):
        def refused(*args, **kwargs):
            raise godot.LimiterRefused("PowerShell refused to run godot-heavy.ps1")

        task = task_with({"kind": "build", "name": "player_builds"}, probe(expect={"op": ">=", "calibrate": 0.5}))
        for side_, job in (("start", "build"), ("reference", "build"), ("reference", "play")):
            with tempfile.TemporaryDirectory() as tmp:  # the reference's jobs are rows of its grade: never failed ones
                projects = {"start": FakeProject(measuring(-500)), "reference": FakeProject(measuring(100))}
                setattr(projects[side_], job, refused)
                result = self.check(json.loads(json.dumps(task)), projects, tmp)
                self.assertEqual(result["verdict"], "ERROR", (side_, job))
                self.assertIn("godot-heavy.ps1", result["reasons"][0])

    def test_a_probe_file_the_checker_cant_read_is_the_tasks_error_not_the_end_of_the_run(self):
        """The probe writes rows as a list; a file that holds something else there (a broken or tampered one) raised
        a TypeError out of the reduction, past the task, and a run of many tasks ended in a traceback."""
        task = task_with(probe("towers", measure={"probe": "objects", "select": {"name": "Tower*"}, "field": "y",
                                                  "of": "max", "at": "end"}))

        def broken(seconds, shots, queries):
            found, log = measuring(100)(seconds, shots, queries)
            found["measures"] = {q["id"]: [{"t": 0.5, "rows": 3.5}] for q in (queries or {}).get("queries", [])}
            return found, log

        with tempfile.TemporaryDirectory() as tmp:
            result = self.check(task, {"start": FakeProject(broken), "reference": FakeProject(broken)}, tmp)
        self.assertEqual(result["verdict"], "ERROR")
        self.assertIn("the checker couldn't check it: TypeError", result["reasons"][0])

    def test_a_build_with_no_word_about_the_game_is_an_error_never_a_verdict(self):
        """Stopped twice with no script error, or killed at its time limit: a fails_at_start start too
        (it counts as not building only on the game's own failure), and the reason names the log it kept."""
        plain = task_with({"kind": "build", "name": "player_builds"}, probe())
        by_design = task_with(milestones=[{"name": "builds", "checks": [{"kind": "build", "name": "player_builds",
                                                                         "fails_at_start": True}]},
                                          {"name": "graded", "checks": [probe(needs=["player_builds"])]}])
        for task, which, answer in ((plain, "start", (1, STOPPED)), (plain, "reference", (1, STOPPED)),
                                    (by_design, "start", (1, STOPPED)), (by_design, "start", (None, ""))):
            with tempfile.TemporaryDirectory() as tmp:
                repo, start, fix, _ = make_game(tmp)
                task = {**task, "seed": {**task["seed"], "commit": start, "reference": fix}}
                machines = {start[:12]: godot_answers(GOOD), fix[:12]: godot_answers(GOOD)}
                machines[{"start": start, "reference": fix}[which][:12]] = godot_answers([answer])
                with mock.patch.object(godot, "Project", lambda folder, machine, label, real=godot.Project: real(
                        folder, machines[Path(folder).name], label)), \
                        mock.patch.object(godot.Machine, "for_project",
                                          classmethod(lambda cls, p, d=False: cls(Path(p), None))), \
                        contextlib.redirect_stderr(io.StringIO()):
                    result = check.check_task(repo, task, json.dumps(task).encode(), Path(tmp) / "scratch",
                                              Path(tmp) / "out", log=lambda *a: None)
                why = result["reasons"][0]
                self.assertEqual(result["verdict"], "ERROR", (which, answer[0], why))
                self.assertIn("BuildStopped", why)
                kept = Path(tmp) / "out" / "probe-task" / which / "build" / "build.log"
                self.assertIn(str(kept), why)
                self.assertTrue(kept.is_file(), "the log the reason names is there after the run")

    def test_a_run_builds_a_commit_its_tasks_share_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            built = {start[:12]: FakeProject(measuring(-500)), fix[:12]: FakeProject(measuring(100))}
            checks = [{"kind": "build", "name": "player_builds", "weight": 0},
                      {"kind": "boot", "name": "boots_clean", "seconds": 10, "needs": ["player_builds"], "weight": 0},
                      probe(expect={"op": ">=", "calibrate": 0.5}, needs=["boots_clean"])]
            one, two = task_with(*checks), task_with(*checks)
            for task, name in ((one, "a-fix-one"), (two, "a-fix-two")):
                task["name"], task["seed"] = name, {**task["seed"], "commit": start, "reference": fix}
            with mock.patch.object(godot, "Project", lambda folder, machine, label: built[Path(folder).name]), \
                    mock.patch.object(godot.Machine, "for_project",
                                      classmethod(lambda cls, p, d=False: cls(Path(p), None))), \
                    mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0):
                builds = check.Builds(repo, Path(tmp) / "scratch", log=lambda *a: None)
                verdicts = [check.check_task(repo, task, json.dumps(task).encode(), Path(tmp) / "unused",
                                             Path(tmp) / "out", log=lambda *a: None, builds=builds)["verdict"]
                            for task in (one, two)]
                self.assertEqual(verdicts, ["VALID", "VALID"])
                self.assertEqual([p.builds for p in built.values()], [1, 1], "each commit built once for both tasks")
                self.assertEqual(len(built[start[:12]].plays), 2, "each task plays with its own queries")
                self.assertTrue((Path(tmp) / "scratch" / start[:12]).is_dir(), "the run, not the task, deletes")
                builds.release(start)
                self.assertFalse((Path(tmp) / "scratch" / start[:12]).exists())
                builds.close()
                self.assertFalse((Path(tmp) / "scratch").exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows file sharing")
    def test_a_copy_that_cant_be_deleted_is_said_not_raised(self):
        """A file of a copy another process holds (a player that outlived an interrupt, a viewer) never ends the run
        or hides its result: the run says which folder to delete."""
        with tempfile.TemporaryDirectory() as tmp:
            said = []
            builds = check.Builds(".", Path(tmp) / "run", log=said.append)
            copy = Path(tmp) / "run" / ("a" * 12)
            (copy / "Logs").mkdir(parents=True)
            (copy / "Logs" / "play.log").write_text("held", encoding="utf-8")
            builds.copies["a" * 40] = (None, {})
            ready = Path(tmp) / "ready"
            holder = subprocess.Popen([sys.executable, "-c", "import sys, time; f = open(sys.argv[1], 'rb'); "
                                       "open(sys.argv[2], 'w').close(); time.sleep(60)", copy / "Logs" / "play.log",
                                       ready])
            try:
                while holder.poll() is None and not ready.exists():
                    time.sleep(0.05)
                with mock.patch.object(seeds, "HELD", 0.5):
                    builds.release("a" * 40)
                    builds.close()
            finally:
                holder.kill()
                holder.wait()
            told = [s for s in said if "couldn't delete" in s]
            self.assertEqual(len(told), 2, said)
            self.assertIn(str(copy), told[0])

    @unittest.skipUnless(sys.platform == "win32", "make_game's repo")
    def test_a_machine_without_godot_fails_every_task_on_its_commit_alike(self):
        def not_installed(cls, project, direct=False):
            raise RuntimeError("Godot 4.7.2 is not at C:/root/godot/4.7.2: run machine\\get-godot.ps1")

        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            runs = []
            for name in ("a-one", "a-two"):
                task = task_with(probe())
                task["name"], task["seed"] = name, {**task["seed"], "commit": start, "reference": fix}
                runs.append(task)
            with mock.patch.object(godot.Machine, "for_project", classmethod(not_installed)), \
                    mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0):
                builds = check.Builds(repo, Path(tmp) / "scratch", log=lambda *a: None)
                results = [check.check_task(repo, task, b"{}", Path(tmp) / "unused", Path(tmp) / "out",
                                            log=lambda *a: None, builds=builds) for task in runs]
                builds.close()
        self.assertEqual([r["verdict"] for r in results], ["ERROR", "ERROR"])
        self.assertTrue(all("get-godot.ps1" in r["reasons"][0] for r in results), [r["reasons"] for r in results])

    def test_an_unreadable_task_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = check.check_task(tmp, {"name": "x"}, b"{}", Path(tmp) / "s", Path(tmp) / "out",
                                      log=lambda *a: None)
            self.assertEqual(result["verdict"], "INVALID")
            self.assertTrue(result["reasons"][0].startswith("the task doesn't validate"))

    def test_a_task_that_doesnt_validate_names_no_file_outside_its_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results" / "out"
            for task in ({"name": "a/b"}, {"name": "../../escaped"}, {"name": "con?"}, {"title": "no name"},
                         {"name": 7}):
                result = check.check_task(tmp, task, b"{}", Path(tmp) / "s", out, log=lambda *a: None)
                self.assertEqual(result["verdict"], "INVALID", task)
            self.assertEqual([p.name for p in Path(tmp).rglob("*.json")], [], "no file under a name it can't have")
            check.check_task(tmp, {"name": "fine-name"}, b"{}", Path(tmp) / "s", out, log=lambda *a: None)
            self.assertTrue((out / "fine-name.json").is_file(), "a name of the schema's form has its result file")

    @unittest.skipUnless(sys.platform == "win32", "Windows file sharing")
    def test_evidence_held_open_is_the_tasks_error_not_the_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            shot = out / "probe-task" / "start" / "look" / "shot_00.png"
            shot.parent.mkdir(parents=True)
            shot.write_bytes(b"png")
            ready = Path(tmp) / "ready"
            viewer = subprocess.Popen([sys.executable, "-c", "import sys, time; f = open(sys.argv[1], 'rb'); "
                                       "open(sys.argv[2], 'w').close(); time.sleep(60)", shot, ready])
            try:
                while viewer.poll() is None and not ready.exists():
                    time.sleep(0.05)
                with mock.patch.object(seeds, "HELD", 0.5):
                    result = check.check_task(tmp, task_with(probe()), b"{}", Path(tmp) / "s", out, log=lambda *a: None)
                self.assertEqual(result["verdict"], "ERROR")
                self.assertIn("shot_00.png", result["reasons"][0])
            finally:
                viewer.kill()
                viewer.wait()


def rising(log="Godot Engine v4.7.2.stable.official\n"):
    """A play answer whose player rises 0.1 m a second, for the play's whole length (as the probe samples it: on to
    half a second past its seconds)."""

    def play(seconds, shots, queries):
        last = seconds + check.OVERRUN
        return {"format": "godot-probe/1", "ended": "time", "seconds": last, "scene": None, "inputs_sent": 0,
                "screenshots": [], "track": [[i * 0.5, 0.0, i * 0.05, 0.0] for i in range(int(last * 2) + 1)],
                "camera": [], "measures": {}}, log

    return play


class IdlePlay(unittest.TestCase):
    BOOT = {"kind": "boot", "name": "boots_clean", "seconds": 60, "weight": 0}

    def test_the_60_s_boot_serves_look_and_look_sees_only_its_first_20_s(self):
        task = task_with(self.BOOT, probe("highest", measure={"probe": "player", "field": "y", "agg": "max"},
                                          expect={"op": ">=", "value": 0}, needs=["boots_clean"]))
        game = FakeProject(rising())
        found = grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertTrue(all(c["passed"] for c in found["checks"]), found["checks"])
        self.assertEqual([(p["seconds"], p["shots"]) for p in game.plays], [(60, 6)], "one launch for both")
        self.assertAlmostEqual(found["probes"]["highest"]["value"], 2.05,
                               msg="the highest point a 20 s look sees (its samples run to 20.5 s), not 3")

    def test_a_look_probe_reading_the_log_keeps_its_own_play(self):
        task = task_with(self.BOOT, probe("no_warnings", measure={"probe": "log", "pattern": "Warning"},
                                          expect={"op": "==", "value": 0}, needs=["boots_clean"]))
        game = FakeProject(rising())
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([p["seconds"] for p in game.plays], [60, 20], "a log covers the whole play")

    def test_a_boot_shorter_than_look_keeps_its_own_play(self):
        task = task_with({**self.BOOT, "seconds": 10}, probe(needs=["boots_clean"]))
        game = FakeProject(rising())
        grade(task, "reference", side("start", FakeProject(), task), side("reference", game, task))
        self.assertEqual([p["seconds"] for p in game.plays], [10, 20])

    def test_a_play_logs_its_time_and_the_wait_for_a_slot(self):
        task = task_with(probe())
        game = FakeProject(rising())
        game.play = lambda *a, **k: godot.Played(0, False, "", 95.0, None, "", {}, 40.0)
        said = []
        check.Side("reference", game, task, 60, 60, None, said.append).probe_play("look")
        self.assertEqual(said, ["  reference: playing look (20 s)",
                                "  reference: played look in 95 s (40 s of it waiting for a machine slot)"])

    def test_first_seconds_cuts_rows_samples_and_length(self):
        times = [1 / 30] + [0.5 * i for i in range(1, 122)]  # a 60 s play's samples as the probe takes them: to 60.5 s
        probe_ = {"seconds": 60.533, "ended": "time", "track": [[t, 0, 1, 0] for t in times], "camera": [],
                  "measures": {"q": [{"t": t, "value": 1} for t in times]}}
        cut = check.first_seconds(probe_, 20)
        look = [t for t in times if t <= 20.5]  # a 20 s look's
        self.assertEqual((cut["seconds"], cut["ended"]), (20.5, "time"))
        self.assertEqual([r[0] for r in cut["track"]], look)
        self.assertEqual([s["t"] for s in cut["measures"]["q"]], look, "its last sample, its \"end\", is a look's")
        self.assertEqual(probe_["seconds"], 60.533, "the boot's own probe is left whole")
        quit_ = check.first_seconds({"seconds": 12.0, "ended": "shutdown", "track": []}, 20)
        self.assertEqual((quit_["seconds"], quit_["ended"]), (12.0, "shutdown"), "a play that ended early stays so")


class FakeMachine:
    """Records each job and answers it with `answer(argv, cwd)` (writing what Godot would), exit code `code` (None:
    killed at its timeout)."""

    def __init__(self, editor="C:/root/godot/4.7.2/Godot_v4.7.2-stable_win64_console.exe", answer=None, code=0):
        self.editor, self.answer, self.code, self.jobs = Path(editor), answer, code, []

    def job(self, label, argv, cwd, timeout, gpu=False):
        argv = [str(a) for a in argv]
        self.jobs.append({"label": label, "argv": argv, "cwd": Path(cwd), "timeout": timeout, "gpu": gpu})
        output = self.answer(argv, Path(cwd)) if self.answer else ""
        return godot.Result(self.code, output or "", 1.0, self.code is None)


def after(argv, flag):
    return argv[argv.index(flag) + 1]


# The engine stopped during an import with no word about the game's scripts.
STOPPED = ("Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org\n"
           "ERROR: Unable to open file: res://.godot/imported/wall.png-0123456789abcdef.ctex.\n"
           "   at: _load_data (scene/resources/compressed_texture.cpp:41)\n")
# A script that doesn't parse, as the engine logs it when the script is loaded.
COMPILED = ("Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org\n"
            "SCRIPT ERROR: Parse Error: Identifier \"coins\" not declared in the current scope.\n"
            "          at: GDScript::reload (res://game/coin.gd:12)\n"
            "ERROR: Failed to load script \"res://game/coin.gd\" with error \"Parse error\".\n"
            "   at: load (modules/gdscript/gdscript_resource_format.cpp:46)\n")
CAUSE = "Parse Error: Identifier \"coins\" not declared in the current scope. at GDScript::reload (res://game/coin.gd:12)"
IMPORTED = "Godot Engine v4.7.2.stable.official.ed1daf0bf - https://godotengine.org\n[ DONE ] first_scan_filesystem\n"
LOADED = f"{godot.SCRIPTS_DONE} 0\n"
UNLOADED = COMPILED + f"{godot.SCRIPT_FAILED} res://game/coin.gd\n{godot.SCRIPTS_DONE} 1\n"
GOOD = [(0, IMPORTED)]


def godot_answers(imports, scripts=((0, LOADED),)):
    """A FakeMachine whose Godot answers each import from `imports` and each scripts pass from `scripts`, lists of
    (exit code (None: killed at its timeout), its log), each repeating its last."""
    left = {"--import": list(imports), "--script": list(scripts)}

    def answer(argv, cwd):
        answers = left["--import" if "--import" in argv else "--script"]
        machine.code, log = answers.pop(0) if len(answers) > 1 else answers[0]
        Path(after(argv, "--log-file")).write_text(log, encoding="utf-8")
        return ""

    machine = FakeMachine(answer=answer)
    return machine


def building(imports, folder, scripts=((0, LOADED),)):
    """(the build's Result, its machine, what it printed) for those answers."""
    machine = godot_answers(imports, scripts)
    with contextlib.redirect_stderr(io.StringIO()) as printed:
        found = godot.Project(folder, machine, "game start").build(60)
    return found, machine, printed.getvalue()


def playing(tmp, wrote='{"format": "godot-probe/1", "ended": "time"}'):
    """A FakeMachine whose play writes `wrote` as its probe.json, and the specs it was handed."""
    specs = []

    def answer(argv, cwd):
        spec = json.loads(Path(after(argv, "-taskProbe")).read_text(encoding="utf-8"))
        specs.append(spec)
        (Path(spec["out"]) / "probe.json").write_text(wrote, encoding="utf-8")
        return ""

    return FakeMachine(answer=answer), specs


class Plays(unittest.TestCase):
    def test_a_long_play_gets_its_own_seconds_and_the_margin_to_run(self):
        """A task play may last 1200 s: a play's timeout is its seconds and check.PLAY_MARGIN plus its waits, as the
        Lab's Godot grader times it (no 1800 s floor); --timeout, when given, takes its place."""
        timeouts = []

        class Timed(FakeProject):
            def play(self, seconds, shots, timeout, **kw):
                timeouts.append(timeout)
                return super().play(seconds, shots, timeout, **kw)

        played = side("reference", Timed(), task_with(probe()))
        played.timeout = None  # no --timeout: the Lab's
        played._play("play_longest", 1200, 1, waits=30.5)
        played._play("play_short", 20, 1, waits=2)
        played._play("play_plain", 20, 1)
        played.timeout = 60  # --timeout 60
        played._play("play_given", 1200, 1, waits=2)
        self.assertEqual(timeouts, [1200 + check.PLAY_MARGIN + 31, 20 + check.PLAY_MARGIN + 2,
                                    20 + check.PLAY_MARGIN, 60 + 2])

    def test_the_build_and_export_limits_are_the_labs(self):
        """A build may run 1800 s by default and a release export twice its build's limit, as the Lab's grader."""
        self.assertEqual(check.BUILD_TIMEOUT, 1800)
        import inspect
        self.assertEqual(inspect.signature(check.check_task).parameters["build_timeout"].default, 1800)
        self.assertIsNone(inspect.signature(check.check_task).parameters["timeout"].default)

    def test_a_play_hands_the_game_its_spec_and_the_play_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = []

            def answer(argv, cwd):
                spec = json.loads(Path(after(argv, "-taskProbe")).read_text(encoding="utf-8"))
                specs.append(spec)
                out = Path(spec["out"])
                (out / "probe.json").write_text(json.dumps({"format": "godot-probe/1", "ended": "time"}),
                                                encoding="utf-8")
                (out / "shot_00.png").write_bytes(b"png")
                Path(after(argv, "--log-file")).write_bytes(b"Godot Engine\r\nCrashHandlerException: Program crashed\r\n")
                return "game output"

            machine = FakeMachine(answer=answer)
            project = godot.Project(tmp, machine, "t")
            asked = probes.query_file(probes.plan(task_with(probe(measure={
                "probe": "objects", "select": {"name": "Tower_1"}, "field": "y", "of": "max"})))["look"], 0.25)
            inputs = [{"t": 1.0, "key": "<Keyboard>/w", "press": True}]
            found = project.play(5, 2, 60, scene="res://scenes/L.tscn", inputs=inputs, queries=asked,
                                 args=["-scenario", "1"], every=0.25, player={"tag": "Hero"})
            (job,) = machine.jobs
            argv = job["argv"]
            self.assertEqual((Path(argv[0]), Path(argv[1])), (Path(sys.executable), godot.DESK),
                             "started through desk.py: on a desktop of its own")
            self.assertEqual(argv[2:5], [str(machine.editor), "--path", str(Path(tmp))], "the copy run from source")
            self.assertEqual(Path(after(argv, "--log-file")), Path(tmp) / "Logs" / "TaskProbe" / "play.log")
            self.assertEqual(argv[7:12], ["--fixed-fps", "30", "--disable-vsync", "--audio-driver", "Dummy"])
            self.assertEqual(argv[12:15], ["res://scenes/L.tscn", "--", "-taskProbe"], "the scene, then the game's own")
            self.assertEqual(Path(argv[15]), Path(tmp) / "Logs" / "TaskProbe" / "play_spec.json")
            self.assertEqual(argv[16:], ["-scenario", "1"], "the play's args after the spec")
            self.assertNotIn("--headless", argv)
            self.assertEqual((job["cwd"], job["gpu"]), (Path(tmp), True), "in the copy, in a GPU slot")
            spec = specs[0]
            self.assertEqual(spec, {"format": "godot-probe-play/1", "out": (Path(tmp) / "Logs/TaskProbe/play").as_posix(),
                                    "size": [960, 540], "seconds": 5, "shots": 2, "every": 0.25, "fps": 30,
                                    "scene": "res://scenes/L.tscn", "sound": False, "player": {"tag": "Hero"},
                                    "inputs": inputs, "queries": asked})
            self.assertEqual(found.probe, {"format": "godot-probe/1", "ended": "time"})
            self.assertEqual(set(found.files), {"probe.json", "shot_00.png"}, "the spec isn't one of the play's files")
            self.assertEqual((found.log, found.output),
                             ("Godot Engine\nCrashHandlerException: Program crashed\n", "game output"))
            self.assertTrue(check.fatal(found.log))
            self.assertFalse((Path(tmp) / "Logs" / "TaskProbe" / "play").exists(), "the play's folder is cleared")
            project.play(5, 0, 60)
            self.assertEqual({k: specs[1][k] for k in ("scene", "player", "inputs", "every", "sound")},
                             {"scene": None, "player": None, "inputs": [], "every": 0.5, "sound": False})
            self.assertEqual(specs[1]["queries"], {"format": "game-probe-queries/1", "every": 0.5, "queries": []})
            self.assertEqual(machine.jobs[1]["argv"][12:14], ["--", "-taskProbe"], "no scene: the project's own")

    def test_a_play_starts_from_clean_saved_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            forgotten = []
            machine, _ = playing(tmp)
            machine.answer = (lambda real: lambda argv, cwd: forgotten.append("played") or real(argv, cwd))(machine.answer)
            with mock.patch.object(seeds, "forget_saves", lambda folder: forgotten.append(Path(folder))):
                godot.Project(tmp, machine, "t").play(5, 0, 60)
            self.assertEqual(forgotten, [Path(tmp), "played"], "the copy's own saves, before the game starts")

    def test_a_plays_evidence_holds_its_spec_so_a_query_id_names_its_select(self):
        task = task_with(probe("tower", measure={"probe": "objects", "select": {"name": "Tower_1"}, "field": "y",
                                                 "at": "end"}),
                         probe("bar", measure={"probe": "widgets", "select": {"name": "FuelBar"}, "field": "count",
                                               "agg": "max"}))
        with tempfile.TemporaryDirectory() as tmp:
            machine, _ = playing(tmp)
            evidence = Path(tmp) / "out" / "probe-task"
            start = check.Side("start", godot.Project(Path(tmp) / "copy", machine, "t"), task, 60, 60, evidence,
                               lambda *a: None)
            start._play("look", 20, 6, queries=probes.query_file(start.plan["look"]))
            kept = json.loads((evidence / "start" / "look" / "play_spec.json").read_text(encoding="utf-8"))
            self.assertEqual({q["id"]: (q["kind"], q["select"]) for q in kept["queries"]["queries"]},
                             {q["id"]: (q["kind"], q["select"]) for q in start.plan["look"]})
            self.assertEqual(sorted(q["kind"] for q in kept["queries"]["queries"]), ["objects", "widgets"])
            self.assertTrue((evidence / "start" / "look" / "probe.json").is_file())

    def test_a_game_desk_py_couldnt_start_is_the_machines_error_never_a_play_with_no_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            refused = "desk.py: [WinError 5] CreateDesktopW TaskProbe: Access is denied"
            project = godot.Project(tmp, FakeMachine(answer=lambda argv, cwd: refused, code=1), "t")
            with self.assertRaises(godot.NoDesktop) as raised:
                project.play(5, 2, 60)
            self.assertIn(refused, str(raised.exception))
            self.assertIn("no evidence about the game", str(raised.exception))
            self.assertTrue(issubclass(godot.NoDesktop, godot.MachineError), "check_task reports it as ERROR")
            # a game that started and exited 1 without a probe file is the game's: a play with no samples
            crashed = godot.Project(tmp, FakeMachine(answer=lambda argv, cwd: "", code=1), "t").play(5, 2, 60)
            self.assertEqual((crashed.exit_code, crashed.probe), (1, None))

    @unittest.skipUnless(sys.platform == "win32", "Windows file sharing")
    def test_a_play_after_a_killed_one_waits_for_its_files_and_never_reads_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, ready = Path(tmp) / "Logs" / "TaskProbe" / "play", Path(tmp) / "ready"

            def killed_play(seconds):
                """The last play's files, its game (killed at its timeout) holding its log for `seconds` as it
                exits."""
                out.mkdir(parents=True, exist_ok=True)
                (out / "probe.json").write_text('{"format": "godot-probe/1", "ended": "time", "stale": 1}',
                                                encoding="utf-8")
                (out / "probe.log").write_text("the killed play's", encoding="utf-8")
                ready.unlink(missing_ok=True)
                held = subprocess.Popen([sys.executable, "-c", "import sys, time; f = open(sys.argv[1], 'rb'); "
                                         "open(sys.argv[2], 'w').close(); time.sleep(float(sys.argv[3]))",
                                         out / "probe.log", ready, str(seconds)])
                while held.poll() is None and not ready.exists():
                    time.sleep(0.05)
                return held

            machine, _ = playing(tmp)
            project = godot.Project(tmp, machine, "t")
            dying = killed_play(2)
            try:
                found = project.play(5, 0, 60)
            finally:
                dying.wait()
            self.assertEqual(found.probe, {"format": "godot-probe/1", "ended": "time"}, "this play's, not the last's")
            stuck = killed_play(60)
            try:
                with mock.patch.object(seeds, "HELD", 0.5), self.assertRaisesRegex(OSError, "probe.log"):
                    project.play(5, 0, 60)  # the checker's error, naming the file; never a play over its leftovers
            finally:
                stuck.kill()
                stuck.wait()

    def test_a_build_imports_the_copy_then_loads_every_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".godot").mkdir()
            (Path(tmp) / ".godot" / "old.cfg").write_text("an earlier import's", encoding="utf-8")
            found, machine, _ = building(GOOD, tmp)
            first, second = (j["argv"] for j in machine.jobs)
            logs = Path(tmp) / "Logs" / "TaskProbe"
            self.assertEqual(first[:4], [str(machine.editor), "--headless", "--path", str(Path(tmp))])
            self.assertEqual((first[4], Path(first[5]), first[6:]), ("--log-file", logs / "build.log", ["--import"]))
            self.assertEqual((second[:4], Path(second[5])), (first[:4], logs / "scripts.log"))
            self.assertEqual((second[6], Path(second[7])), ("--script", logs / "scripts.gd"))
            self.assertEqual((logs / "scripts.gd").read_text(encoding="utf-8"), godot.SCRIPTS_PASS)
            self.assertIn("extends SceneTree", godot.SCRIPTS_PASS)
            self.assertTrue((logs / ".gdignore").is_file(), "the engine never imports the checker's own files")
            self.assertFalse((Path(tmp) / ".godot" / "old.cfg").exists(), "a fresh import")
            self.assertEqual([(j["cwd"], j["gpu"], j["label"]) for j in machine.jobs],
                             [(Path(tmp), False, "task-check build game start"),
                              (Path(tmp), False, "task-check scripts game start")])
            self.assertEqual((found.exit_code, found.cause, found.stopped), (0, None, None))
            self.assertIn("first_scan_filesystem", found.output, "the logs are the build's output")
            self.assertEqual(found.seconds, 2.0, "both jobs' time")

    def test_a_script_error_fails_the_build_whatever_the_engine_exits_with(self):
        cases = [  # (the import's answer, the scripts pass's): the engine exits 0 from an import that logged an error
            ((0, COMPILED), (0, LOADED)), ((1, COMPILED), (0, LOADED)), ((0, IMPORTED), (1, UNLOADED)),
            ((0, IMPORTED), (0, UNLOADED)), ((0, IMPORTED), (0, COMPILED + LOADED)),
            ((0, IMPORTED), (1, f"{godot.SCRIPT_FAILED} res://game/coin.gd\n{godot.SCRIPTS_DONE} 1\n")),
        ]
        for imported, loaded in cases:
            with tempfile.TemporaryDirectory() as tmp:
                found, machine, printed = building([imported], tmp, [loaded])
            self.assertEqual((found.exit_code, found.stopped, printed), (1, None, ""), (imported, loaded))
            self.assertEqual(len(machine.jobs), 1 if imported[1] == COMPILED else 2, "no scripts pass after a failed import")
        self.assertEqual(found.cause, f"{godot.SCRIPT_FAILED} res://game/coin.gd", "the script that didn't load")
        woke = "SCRIPT ERROR: Invalid access to property or key 'hp' on a base object of type 'Nil'.\n" + LOADED
        with tempfile.TemporaryDirectory() as tmp:
            found, _, _ = building(GOOD, tmp, [(0, woke)])
        self.assertEqual(found.exit_code, 0, "an autoload that fails at run time with no scene to play still parses")
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            unfinished = godot.Project(tmp, godot_answers(GOOD, [(0, "Godot Engine\n")]), "t").build(60)
        self.assertEqual(unfinished.exit_code, 1)
        self.assertIn("the scripts pass didn't finish", unfinished.output)
        self.assertTrue(unfinished.stopped, "no word about the game: the machine's")

    def test_a_failed_builds_reason_names_its_first_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = task_with({"kind": "build", "name": "player_builds"}, probe())
            project = godot.Project(tmp, godot_answers([(0, COMPILED)]), "t")
            why = check.Side("reference", project, task, 60, 60, None, lambda *a: None).why_unbuilt()
            self.assertEqual(why, f"the reference game didn't build (exit 1: {CAUSE})")
            row = grade(task, "reference", side("start", FakeProject(), task), side("reference", project, task))
            self.assertEqual(row["checks"][0]["detail"], f"build failed (exit 1: {CAUSE})")
            long = COMPILED.replace("res://game/coin.gd:12", "res://game/" + "deep/" * 60 + "coin.gd:12")
            cut = godot.Project(tmp, godot_answers([(0, long)]), "t").build(60).cause
            self.assertEqual((len(cut), cut[-3:]), (godot.CAUSE_CHARS, "..."), "one short clause")
            bare = godot.Project(tmp, godot_answers([(0, 'ERROR: Failed to load script "res://a.gd" with error')]),
                                 "t").build(60)
            self.assertEqual(bare.cause, 'ERROR: Failed to load script "res://a.gd" with error')

    def test_a_job_goes_through_the_limiter_a_play_in_its_gpu_slot(self):
        seen = []
        with mock.patch.object(godot, "run", lambda argv, cwd, timeout, wrapper=False: seen.append(argv) or
                               godot.Result(0, "", 1.0)):
            machine = godot.Machine(Path("C:/G/godot.exe"), Path("C:/Work/tools/godot-heavy.ps1"))
            machine.job("task-check play x", ["python", "desk.py", "-taskProbe", "C:/c/it's.json"], ".", 60, gpu=True)
            machine.job("task-check build x", ["C:/G/godot.exe", "--headless"], ".", 60)
            godot.Machine(Path("C:/G/godot.exe"), None).job("direct", [Path("C:/G/godot.exe"), "--import"], ".", 60)
        play, build, direct = seen
        self.assertEqual(play[:6], ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                    "-Command"])
        self.assertIn("-Label 'task-check play x' -Gpu -- 'python' 'desk.py' '-taskProbe' 'C:/c/it''s.json'", play[6])
        self.assertNotIn("-Gpu", build[6])
        self.assertEqual(direct, [str(Path("C:/G/godot.exe")), "--import"])

    def test_a_machine_without_godot_is_an_error_not_an_exit(self):
        def missing_godot(console=True):
            raise SystemExit("Godot 4.7.2 is not at C:/root/godot/4.7.2/godot.exe: run machine\\get-godot.ps1")

        with mock.patch.object(godot.ggfroot, "godot_exe", missing_godot):
            with self.assertRaisesRegex(RuntimeError, "run machine.get-godot.ps1"):
                godot.Machine.for_project(".")

    def test_the_machine_finds_godot_and_the_limiter(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tools").mkdir()
            (Path(tmp) / "tools" / "godot-heavy.ps1").write_text("", encoding="utf-8")
            asked = []
            with mock.patch.object(godot.ggfroot, "godot_exe", lambda console=True: asked.append(console) or
                                   "C:/G/godot_console.exe"), \
                    mock.patch.object(godot.ggfroot, "root", lambda: tmp):
                found = godot.Machine.for_project(".")
                self.assertEqual((found.editor, found.heavy), (Path("C:/G/godot_console.exe"),
                                                               Path(tmp) / "tools" / "godot-heavy.ps1"))
                self.assertEqual(asked, [True], "the console exe: it waits and passes the exit code on")
                self.assertIsNone(godot.Machine.for_project(".", direct=True).heavy)


class Retries(unittest.TestCase):
    """A build that fails with no word about the game, no script error in its logs, is tried once more; stopped again,
    or at its time limit, it is the run's error, never a verdict on the game."""

    def test_a_clean_build_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            found, machine, printed = building(GOOD, tmp)
        self.assertEqual((found.exit_code, found.stopped, len(machine.jobs), printed), (0, None, 2, ""))

    def test_a_build_stopped_without_a_word_tries_again_and_isnt_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            found, machine, printed = building([(1, STOPPED), (0, IMPORTED)], tmp)
        self.assertEqual((found.exit_code, found.stopped, len(machine.jobs)), (0, None, 3))
        self.assertEqual(printed, "  game start: build stopped (exit 1) with no script error, retry 1\n")
        head = found.output.splitlines()[0]
        self.assertEqual(head, "[task-check] build retried once: its first try stopped (exit 1) with no script error")

    def test_a_failure_by_the_game_counts_at_once(self):
        long = "Loaded asset\n" * 2000 + COMPILED + "Reimporting\n" * 2000
        self.assertNotIn("SCRIPT ERROR", godot.cut(long), "a script error the kept output leaves out")
        for imports, scripts in (([(1, COMPILED)], [(0, LOADED)]), ([(0, long)], [(0, LOADED)]),
                                 ([(0, IMPORTED)], [(1, UNLOADED)])):
            with tempfile.TemporaryDirectory() as tmp:
                found, machine, printed = building(imports + [(0, IMPORTED)], tmp, scripts + [(0, LOADED)])
            self.assertEqual((found.exit_code, found.stopped, printed), (1, None, ""), imports[0][1][:40])

    def test_a_failure_by_the_game_after_a_retry_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            found, machine, _ = building([(1, STOPPED), (1, COMPILED)], tmp)
        self.assertEqual((found.exit_code, found.stopped, len(machine.jobs)), (1, None, 2))
        self.assertEqual(found.cause, CAUSE)
        self.assertTrue(found.output.startswith("[task-check] build retried once"))

    def test_it_gives_up_after_one_retry_and_its_side_is_no_verdict(self):
        task = task_with({"kind": "build", "name": "player_builds"}, probe())
        with tempfile.TemporaryDirectory() as tmp:
            machine, said = godot_answers([(1, STOPPED)]), []
            evidence = Path(tmp) / "out" / "probe-task"
            reference = check.Side("reference", godot.Project(Path(tmp) / "copy", machine, "game reference"), task,
                                   60, 60, evidence, said.append)
            with self.assertRaises(godot.BuildStopped) as raised, contextlib.redirect_stderr(io.StringIO()):
                reference.built()
            why, kept = str(raised.exception), evidence / "reference" / "build" / "build.log"
            self.assertTrue(why.startswith("the reference game didn't build: Godot stopped twice (exit 1)"), why)
            self.assertIn("no evidence about the game", why)
            self.assertIn(f"its log: {kept}", why)
            self.assertIn("Unable to open file", kept.read_text(encoding="utf-8"), "kept before the error leaves")
            self.assertIn("  reference: build STOPPED (2 s)", said, "both tries' time")
            with self.assertRaises(godot.BuildStopped):  # a later check of the same side: the same error, no new try
                reference.why_unbuilt()
            self.assertEqual(len(machine.jobs), 2)
        self.assertTrue(issubclass(godot.BuildStopped, godot.MachineError))

    def test_a_build_killed_at_its_timeout_isnt_tried_again_and_is_no_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            found, machine, printed = building([(None, "Importing assets\n")], tmp)
        self.assertEqual((found.exit_code, found.timed_out, len(machine.jobs), printed), (None, True, 1, ""))
        self.assertTrue(found.stopped.startswith("Godot was stopped at the build's time limit (60 s)"), found.stopped)


class Cli(unittest.TestCase):
    def test_the_results_folder_is_git_ignored_in_the_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            cli.ignore_results(repo, repo / ".task-checks")
            self.assertEqual(subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", ".task-checks/a.json"])
                             .returncode, 0)
            self.assertEqual(git(repo, "status", "--porcelain"), b"", "no tracked file changed")
            exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
            cli.ignore_results(repo, repo / ".task-checks")
            self.assertEqual((repo / ".git" / "info" / "exclude").read_text(encoding="utf-8"), exclude, "once")

    def test_a_task_file_not_committed_yet_is_checked_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "metro-runner-fix-x.json"
            path.write_text(json.dumps({**task_with(probe()), "name": "metro-runner-fix-x"}), encoding="utf-8")
            seen = []

            def fake(repo_, task, raw, scratch, out, **kw):
                seen.append(task["name"])
                return {"task": task["name"], "verdict": "VALID", "reasons": []}

            with mock.patch.object(check, "check_task", fake), \
                    mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                code = cli.main([str(repo), "--task", str(path), "--scratch", str(Path(tmp) / "s")])
            self.assertEqual((code, seen), (0, ["metro-runner-fix-x"]))
            self.assertEqual(out.getvalue(), "VALID   metro-runner-fix-x\n")

    def test_a_run_deletes_a_shared_copy_after_its_last_task_and_writes_its_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, start, fix, _ = make_game(tmp)
            paths, released, progress = [], [], []
            for name, seed in (("g-fix-one", {"commit": start, "reference": fix}),
                               ("g-fix-two", {"commit": fix, "reference": fix})):
                path = Path(tmp) / f"{name}.json"
                task = task_with(probe())
                path.write_text(json.dumps({**task, "name": name, "seed": {**task["seed"], **seed}}),
                                encoding="utf-8")
                paths.append(str(path))
            out = Path(tmp) / "out"

            def fake(repo_, task, raw, scratch, out_, **kw):
                progress.append((out / "progress.txt").read_text(encoding="utf-8"))
                return {"task": task["name"], "verdict": "VALID", "reasons": [], "seconds": 60}

            with mock.patch.object(check, "check_task", fake), \
                    mock.patch.object(check.Builds, "release", lambda self, sha: released.append(sha)), \
                    mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main([str(repo), "--task", paths[0], "--task", paths[1], "--scratch",
                                 str(Path(tmp) / "s"), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(released, [start, fix], "start after task one; fix, shared, only after task two")
            self.assertIn("0 of 2 task(s) done", progress[0])
            self.assertIn("checking g-fix-two", progress[1])
            final = (out / "progress.txt").read_text(encoding="utf-8")
            self.assertIn("2 of 2 task(s) done", final)
            self.assertIn("finished", final)
            self.assertIn("VALID   g-fix-one  (1 min)", final)
            self.assertTrue(json.loads((out / "progress.json").read_text(encoding="utf-8"))["finished"])

    def test_kept_copies_keep_nothing_of_theirs_outside_them(self):
        """With --keep the copies stay, but not their plays' saved data (each copy's own user data folder): deleting a
        kept copy by hand would never take it, and every play starts from clean saved data anyway."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "metro-runner-fix-x.json"
            path.write_text(json.dumps({**task_with(probe()), "name": "metro-runner-fix-x"}), encoding="utf-8")
            copies, forgotten = [], []

            def fake(repo_, task, raw, scratch, out, **kw):
                copy = Path(scratch) / ("0" * 12)
                copy.mkdir(parents=True)
                (copy / "project.godot").write_text(PROJECT, encoding="utf-8")
                copies.append(copy)
                return {"task": task["name"], "verdict": "VALID", "reasons": []}

            with mock.patch.object(check, "check_task", fake), mock.patch.object(seeds, "forget_saves", forgotten.append), \
                    mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main([str(repo), "--task", str(path), "--scratch", str(Path(tmp) / "s"), "--keep"])
            self.assertEqual(forgotten, copies)
            self.assertTrue(copies[0].is_dir(), "the copy itself is kept")

    def test_two_runs_at_once_on_one_repo_have_folders_of_their_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = make_game(tmp)
            path = Path(tmp) / "metro-runner-fix-x.json"
            path.write_text(json.dumps({**task_with(probe()), "name": "metro-runner-fix-x"}), encoding="utf-8")
            scratches = []

            class Recorded:
                def __init__(self, repo_, scratch, direct, log):
                    scratches.append(Path(scratch))

                def release(self, sha):
                    pass

                def close(self):
                    pass

            with mock.patch.object(check, "check_task", lambda *a, **k: {"task": "x", "verdict": "VALID", "reasons": []}), \
                    mock.patch.object(check, "Builds", Recorded), \
                    mock.patch.object(cli.time, "time", lambda: 1700000000.0), \
                    mock.patch.object(cli.os, "getpid", itertools.count(4100).__next__), \
                    mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                for _ in range(2):  # two processes started in one tick of the clock (15.6 ms on Windows)
                    cli.main([str(repo), "--task", str(path), "--scratch", str(Path(tmp) / "s")])
            self.assertEqual(len(set(scratches)), 2, "one folder each: the first to end deleted the other's copies")

    def test_the_default_scratch_is_on_the_repos_own_drive(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repos" / "metro-runner"
            repo.mkdir(parents=True)
            drive = os.path.splitdrive(os.path.realpath(tmp))[0]
            self.assertEqual(cli.default_scratch(repo, root=Path(tmp) / "root"),
                             Path(os.path.realpath(tmp)) / "root" / ".task-check", "the machine root when it is there")
            if sys.platform != "win32":
                return  # one volume tree: no other drive to be on
            other = "Z:" if drive.upper() != "Z:" else "Y:"
            self.assertEqual(cli.default_scratch(repo, root=other + "\\Work"),
                             Path(os.path.realpath(tmp)) / ".task-check", "else beside the repos' folder")
            link = Path(tmp) / "games"
            if subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(Path(tmp) / "repos")],
                              capture_output=True).returncode == 0:
                self.assertEqual(cli.default_scratch(link / "metro-runner", root=other + "\\Work"),
                                 Path(os.path.realpath(tmp)) / ".task-check", "a junction is followed")

    def test_one_line_per_task(self):
        self.assertEqual(cli.line({"task": "a", "verdict": "VALID", "reasons": []}), "VALID   a")
        self.assertEqual(cli.line({"task": "b", "verdict": "INVALID", "reasons": ["x", "y"]}), "INVALID b: x; y")


class SavedData(unittest.TestCase):
    def test_a_copys_saves_go_under_a_name_of_its_own(self):
        name = seeds.saves_company("C:/Scratch/ABC123")
        self.assertRegex(name, r"^TaskProbe\.[0-9a-f]{12}$")
        self.assertEqual(name, seeds.saves_company(r"c:\scratch\abc123" if os.name == "nt" else "c:/scratch/abc123"))
        self.assertNotEqual(name, seeds.saves_company("C:/Scratch/ABC124"))

    def test_removing_a_folder_forgets_the_saves_of_the_projects_in_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "run" / "copy"
            project.mkdir(parents=True)
            (project / "project.godot").write_text(PROJECT, encoding="utf-8")
            forgotten = []
            with mock.patch.object(seeds, "forget_saves", forgotten.append):
                seeds.remove(Path(tmp) / "run")
            self.assertEqual(forgotten, [project])
            self.assertFalse((Path(tmp) / "run").exists())

    def test_remove_refuses_what_is_never_a_folder_of_the_checkers_own(self):
        home, here = os.path.expanduser("~"), os.getcwd()
        for path in ("", ".", "..", "/" if os.name != "nt" else "C:\\", here, os.path.dirname(here), home,
                     os.path.dirname(home)):
            self.assertIsNotNone(seeds.refused(path), path)  # (never handed to remove() here: it would delete them)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(seeds.refused(Path(tmp) / "scratch" / "run"))
            canary = Path(tmp) / "canary.txt"
            canary.write_text("the folder the checker was started in", encoding="utf-8")
            with contextlib.chdir(tmp):
                for path in ("", ".", Path("")):
                    with self.assertRaisesRegex(ValueError, "won't delete"):
                        seeds.remove(path)
            self.assertTrue(canary.is_file())

    @unittest.skipUnless(sys.platform == "win32", "junctions")
    def test_remove_takes_a_link_as_the_link(self):
        import _winapi

        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside"
            (outside / "sub").mkdir(parents=True)
            (outside / "sub" / "keep.txt").write_text("not the checker's", encoding="utf-8")
            live, dangling, gone = Path(tmp) / "live", Path(tmp) / "dangling", Path(tmp) / "gone"
            _winapi.CreateJunction(str(outside), str(live))
            gone.mkdir()
            _winapi.CreateJunction(str(gone), str(dangling))
            gone.rmdir()
            folder = Path(tmp) / "copy"
            folder.mkdir()
            _winapi.CreateJunction(str(outside), str(folder / "inside"))
            for path in (live, dangling, folder):
                seeds.remove(path)
                self.assertFalse(os.path.lexists(path), path)
            self.assertTrue((outside / "sub" / "keep.txt").is_file(), "never what a link points at")

    def test_forgetting_a_copy_deletes_its_own_user_data_folder_and_nothing_beside_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "AppData" / "Roaming"
            project, other = Path(tmp) / "copy", Path(tmp) / "other copy"
            own, neighbour = parent / seeds.saves_company(project), parent / seeds.saves_company(other)
            for folder in (own / "saves", neighbour, parent / "Godot" / "app_userdata" / "Metro Runner"):
                folder.mkdir(parents=True)
                (folder / "saved.bin").write_bytes(b"x")
            with mock.patch.object(seeds, "_saves_parent", lambda: str(parent)):
                seeds.forget_saves(project)
            self.assertEqual(sorted(p.name for p in parent.iterdir()), sorted(["Godot", neighbour.name]),
                             "the copy's, not the other's, never the real game's")
            for nowhere in (None, "", "relative"):  # no folder to look in, or not an absolute one: nothing is deleted
                with mock.patch.object(seeds, "_saves_parent", lambda: nowhere), contextlib.chdir(parent):
                    (parent / "relative" / neighbour.name).mkdir(parents=True, exist_ok=True)
                    seeds.forget_saves(other)
                self.assertTrue(neighbour.is_dir() and (parent / "relative" / neighbour.name).is_dir())

    def test_only_a_name_of_the_copys_form_is_ever_deleted(self):
        deleted = []
        with mock.patch.object(seeds, "_saves_parent", lambda: os.path.abspath(os.sep + "AppData")), \
                mock.patch.object(seeds.shutil, "rmtree", lambda path, **kw: deleted.append(path)):
            for path in ("", ".", "..", os.sep, "a/../../b", "TaskProbe.0123456789ab", "C:\\tc\\x\\"):
                seeds.forget_saves(path)
        self.assertEqual(len(deleted), 7)
        for path in deleted:
            self.assertRegex(os.path.basename(path), r"^TaskProbe\.[0-9a-f]{12}$")
            self.assertEqual(os.path.dirname(path), os.path.abspath(os.sep + "AppData"))
        with mock.patch.object(seeds, "saves_company", lambda project: "..\\Godot"), \
                mock.patch.object(seeds, "_saves_parent", lambda: os.path.abspath(os.sep + "AppData")), \
                mock.patch.object(seeds.shutil, "rmtree", lambda path, **kw: deleted.append(path)):
            seeds.forget_saves("x")
        self.assertEqual(len(deleted), 7, "any other name is left alone")


class Limiter(unittest.TestCase):
    def test_a_limiter_that_cant_be_started_is_an_error_not_a_failed_build(self):
        refused = "& : File C:\\Work\\tools\\godot-heavy.ps1 cannot be loaded because running scripts is disabled"
        with mock.patch.object(godot, "run", lambda argv, cwd, timeout, wrapper=False: godot.Result(1, refused, 0.1)):
            machine = godot.Machine(Path("C:/G/godot.exe"), Path("C:/Work/tools/godot-heavy.ps1"))
            with self.assertRaises(godot.LimiterRefused) as raised:
                machine.job("task-check build x", ["C:/G/godot.exe", "--headless"], ".", 60)
        self.assertIn("--direct", str(raised.exception))
        self.assertTrue(issubclass(godot.LimiterRefused, RuntimeError), "check_task reports it as ERROR")

    @unittest.skipUnless(sys.platform == "win32", "PowerShell")
    def test_every_value_reaches_the_limiter_as_it_is(self):
        """PowerShell reads the typographic quotes as quotes too: a user folder named O\u2019Brien broke every job."""
        for value in ("C:\\Users\\O'Brien\\x.json", "C:\\Users\\O\u2019Brien\\x.json", "a\u2018b\u201ac\u201bd ''e $x"):
            got = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
                                  "& { param($a) [Console]::Out.Write($a) } " + godot._ps_quote(value)],
                                 capture_output=True)
            self.assertEqual(got.stdout.decode("utf-8", errors="replace"), value, got.stderr.decode(errors="replace"))


# A stand-in player: writes its pid and its parent's (desk.py's) to argv[1], then sleeps argv[2] seconds.
PLAYER = ("import json, os, sys, time\n"
          "with open(sys.argv[1] + '.tmp', 'w') as f:\n"
          "    json.dump({'pid': os.getpid(), 'parent': os.getppid()}, f)\n"
          "os.replace(sys.argv[1] + '.tmp', sys.argv[1])\n"
          "time.sleep(float(sys.argv[2]))\n")
# A stand-in for godot-heavy.ps1: it waits STAND_IN_WAIT seconds for a slot with a helper of its own running all the
# while (the real one runs nvidia-smi as it waits), then starts its job as the real one does, releases its slot however
# the job ends (STAND_IN_RELEASED: the file that says so) and exits with its code; STAND_IN_EXIT: it gives up without
# starting its job.
LIMITER = """[CmdletBinding(PositionalBinding = $false)]
param([string]$Label, [switch]$Gpu, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Command)
if ($Command.Count -and $Command[0] -eq '--') { $Command = $Command[1..($Command.Count - 1)] }
& ping -n ([int]$env:STAND_IN_WAIT + 1) 127.0.0.1 | Out-Null
if ($env:STAND_IN_EXIT) { exit [int]$env:STAND_IN_EXIT }
$code = 1
try {
  $psi = New-Object Diagnostics.ProcessStartInfo $Command[0], ((@($Command | Select-Object -Skip 1) | ForEach-Object { '"' + $_ + '"' }) -join ' ')
  $psi.UseShellExecute = $false
  $proc = [Diagnostics.Process]::Start($psi)
  $proc.WaitForExit()
  $code = $proc.ExitCode
} finally {
  if ($env:STAND_IN_RELEASED) { Set-Content -LiteralPath $env:STAND_IN_RELEASED -Value released }
}
exit $code
"""


def alive(pid, seconds=5.0):
    """Whether process `pid` still runs after up to `seconds` (a killed process takes a moment to go). Never os.kill:
    on Windows it terminates the process."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    end = time.monotonic() + seconds
    while True:
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = wintypes.DWORD()
        running = kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259  # STILL_ACTIVE
        kernel32.CloseHandle(handle)
        if not running:
            return False
        if time.monotonic() > end:
            return True
        time.sleep(0.1)


@unittest.skipUnless(sys.platform == "win32", "Windows processes")
class Jobs(unittest.TestCase):
    """godot.run on real processes: a stand-in limiter, and a stand-in player started through desk.py."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "player.py").write_text(PLAYER, encoding="utf-8")
        (self.tmp / "godot-heavy.ps1").write_text(LIMITER, encoding="utf-8")
        self.direct = godot.Machine(Path("C:/G/godot.exe"), None)
        self.limited = godot.Machine(Path("C:/G/godot.exe"), self.tmp / "godot-heavy.ps1")
        self.pids = []

    def tearDown(self):
        for pid in self.pids:  # a failed test leaves nothing running
            if alive(pid, 0):
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def play(self, seconds):
        """The argv of a play (desk.py and the stand-in player) and the file its player writes its pids to."""
        info = self.tmp / f"player{len(self.pids)}.json"
        return [sys.executable, godot.DESK, sys.executable, self.tmp / "player.py", info, str(seconds)], info

    def ran(self, info):
        found = json.loads(info.read_text(encoding="utf-8"))
        self.pids += [found["pid"], found["parent"]]
        return found["pid"], found["parent"]

    def test_the_wait_for_a_slot_isnt_the_jobs_time(self):
        # (any look at the process tree during the wait, a PowerShell query of up to a few seconds on a busy machine,
        # finds the limiter's helper: taken for the job, it started the 6 s during the wait)
        with mock.patch.object(godot, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_WAIT": "6"}):
            found = self.limited.job("t", [sys.executable, "-c", "import time; time.sleep(3)"], self.tmp, 6)
        self.assertEqual((found.exit_code, found.timed_out), (0, False), "its 6 s count from the job's start")
        self.assertGreater(found.waited, 6, "the limiter's wait, its own helper's run included")

    def test_a_limiter_that_never_starts_its_job_still_ends(self):
        with mock.patch.object(godot, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_EXIT": "2"}):
            found = self.limited.job("t", [sys.executable, "-c", "import time; time.sleep(60)"], self.tmp, 60)
        self.assertEqual((found.exit_code, found.timed_out), (2, False))
        self.assertLessEqual(found.waited, found.seconds, "all of it a wait")

    def test_a_job_that_comes_and_goes_between_two_looks_still_shows_its_wait(self):
        with mock.patch.object(godot, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_WAIT": "6"}):
            found = self.limited.job("t", [sys.executable, "-c", "pass"], self.tmp, 60)
        self.assertEqual(found.exit_code, 0)
        self.assertGreater(found.waited, 6, "the limiter's wait, though no look found the job: never its own time")

    def test_a_timeout_kills_the_job_and_the_player_desk_py_started(self):
        run = godot.run
        for machine in (self.direct, self.limited):
            argv, info = self.play(60)
            released, leaps = self.tmp / f"released{len(self.pids)}", itertools.count()

            def clock():  # once the player runs, every look at the clock finds the job's time up
                return time.monotonic() + (1000 * next(leaps) if info.exists() else 0)

            with mock.patch.object(godot, "QUEUE_POLL", 0.5), mock.patch.object(godot, "run", lambda *a, **k: run(
                    *a, clock=clock, **k)), mock.patch.dict(os.environ, {"STAND_IN_RELEASED": str(released)}):
                found = machine.job("t", argv, self.tmp, 60, gpu=True)
            player, desk_py = self.ran(info)
            self.assertEqual((found.exit_code, found.timed_out), (None, True))
            self.assertFalse(alive(player), "the player")
            self.assertFalse(alive(desk_py), "desk.py")
            self.assertEqual(released.is_file(), machine is self.limited, "the limiter got its grace to release")

    def test_an_interrupt_kills_the_job_and_the_player_desk_py_started(self):
        run = godot.run
        for machine in (self.direct, self.limited):
            argv, info = self.play(60)

            def clock():  # Ctrl+C once the player runs
                if info.exists():
                    raise KeyboardInterrupt
                return time.monotonic()

            with mock.patch.object(godot, "QUEUE_POLL", 0.5), mock.patch.dict(os.environ, {"STAND_IN_WAIT": "0"}), \
                    mock.patch.object(godot, "run", lambda *a, **k: run(*a, clock=clock, **k)), \
                    warnings.catch_warnings(record=True) as warned:
                warnings.simplefilter("always", ResourceWarning)
                with self.assertRaises(KeyboardInterrupt):
                    machine.job("t", argv, self.tmp, 120, gpu=True)
                gc.collect()
            player, desk_py = self.ran(info)
            self.assertFalse(alive(player), "the player")
            self.assertFalse(alive(desk_py), "desk.py")
            self.assertEqual([str(w.message) for w in warned if w.category is ResourceWarning], [],
                             "the job's output pipe closed too")


@unittest.skipUnless(sys.platform == "win32", "Windows desktops")
class Desk(unittest.TestCase):
    """desk.py with real stand-in players."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(suffix=" with space"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def desk(self, *argv, **kw):
        return subprocess.run([sys.executable, godot.DESK, *[str(a) for a in argv]], capture_output=True, text=True,
                              **kw)

    def test_it_exits_with_the_players_exit_code(self):
        self.assertEqual(self.desk(sys.executable, "-c", "import sys; sys.exit(7)").returncode, 7)
        crashed = self.desk(sys.executable, "-c", "import ctypes; ctypes.windll.kernel32.ExitProcess(0xC0000005)")
        self.assertEqual(crashed.returncode, 0xC0000005, "an NTSTATUS, as Windows gives it")

    def test_the_player_gets_its_arguments_folder_and_environment(self):
        show = self.tmp / "show args.py"
        show.write_text("import json, os, sys\njson.dump({'argv': sys.argv[1:-1], 'cwd': os.getcwd(), "
                        "'marker': os.environ.get('DESK_MARKER')}, open(sys.argv[-1], 'w'))\n", encoding="utf-8")
        args = ["plain", "with space", 'with "quotes"', "trailing\\", "trailing space\\", "", "-x=C:\\a b\\"]
        work = self.tmp / "build folder"
        work.mkdir()
        out = self.tmp / "seen.json"
        self.desk(sys.executable, show, *args, out, cwd=work, env={**os.environ, "DESK_MARKER": "x"})
        seen = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(seen, {"argv": args, "cwd": str(work), "marker": "x"},
                         "quoted by the Windows rules (subprocess.list2cmdline); desk.py's folder and environment")

    def test_a_call_that_fails_is_named_with_windows_reason(self):
        found = self.desk(self.tmp / "no such.exe")
        self.assertEqual(found.returncode, 1)
        self.assertIn("desk.py: [WinError 2] CreateProcessW", found.stderr)
        self.assertIn("cannot find the file", found.stderr)

    def test_a_player_never_outlives_desk_py(self):
        info = self.tmp / "player.json"
        (self.tmp / "player.py").write_text(PLAYER, encoding="utf-8")
        started = subprocess.Popen([sys.executable, godot.DESK, sys.executable, self.tmp / "player.py", info, "60"])
        try:
            for _ in range(200):
                if info.exists():
                    break
                time.sleep(0.1)
            player = json.loads(info.read_text(encoding="utf-8"))["pid"]
            subprocess.run(["taskkill", "/F", "/PID", str(started.pid)], capture_output=True)  # desk.py alone
            started.wait()
            self.assertFalse(alive(player), "the job object takes the player with desk.py")
        finally:
            if info.exists() and alive(json.loads(info.read_text(encoding="utf-8"))["pid"], 0):
                subprocess.run(["taskkill", "/F", "/PID", str(json.loads(info.read_text())["pid"])],
                               capture_output=True)

    def test_two_plays_share_the_desktop_and_leave_nothing_behind(self):
        import ctypes

        from task_check import desk

        outs = [self.tmp / f"{i}.json" for i in range(2)]
        both = [subprocess.Popen([sys.executable, godot.DESK, sys.executable, "-c",
                                  f"import json, time; time.sleep(1); json.dump(1, open(r'{o}', 'w'))"]) for o in outs]
        self.assertEqual([p.wait() for p in both], [0, 0])
        self.assertTrue(all(o.is_file() for o in outs))
        kernel32, user32 = ctypes.WinDLL("kernel32"), ctypes.WinDLL("user32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        user32.OpenDesktopW.restype = ctypes.c_void_p
        user32.OpenDesktopW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]

        def handles():
            count = ctypes.c_uint32()
            kernel32.GetProcessHandleCount(kernel32.GetCurrentProcess(), ctypes.byref(count))
            return count.value

        name = f"TaskProbeTest{os.getpid()}"  # a desktop of the test's own: real plays may be on TaskProbe now
        desk.run([sys.executable, "-c", "pass"], name)  # the first call loads what it needs once
        before = handles()
        self.assertEqual(desk.run([sys.executable, "-c", "import sys; sys.exit(3)"], name), 3)
        with self.assertRaisesRegex(OSError, "CreateProcessW"):
            desk.run([self.tmp / "no such.exe"], name)
        self.assertEqual(handles(), before, "every handle closed, on success and on failure")
        left = user32.OpenDesktopW(name, 0, False, 0x0001)
        if left:
            user32.CloseDesktop(left)
        self.assertFalse(left, "the desktop goes with its last play")


if __name__ == "__main__":
    unittest.main()
