"""Settling a kept run (settle.py, `task-check.py --settle`): the writer's answers to that run's own judge pictures and
seen crops, bound to them by their hashes and file times, decided by the run's own rules; nothing is played. Godot is
faked."""

import contextlib
import io
import itertools
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import measuring, probe, task_with
from test_check import fake_probe_package, make_game
from test_judges import Shooting, judge, play
from test_seen import Played, seen_probe

from task_check import check, cli, godot, seeds, settle

TASK = "probe-task"
JUDGE = "door_looks_open"
PASSING = ({"door_open": 0, "lit": 1}, {"door_open": 1, "lit": 1})  # (start, reference)
PENDING = f"judge {JUDGE}: shots saved for start/reference, answer needed"
FIELDS = ("verdict", "reasons", "notes", "start_checks", "reference_checks", "probes")


def setUpModule():
    global _probe_patch
    folder = tempfile.mkdtemp()
    _probe_patch = mock.patch.object(seeds, "PROBE_SOURCE", fake_probe_package(folder))
    _probe_patch.start()
    _probe_patch.folder = folder


def tearDownModule():
    _probe_patch.stop()
    shutil.rmtree(_probe_patch.folder, ignore_errors=True)


class Wobbly(Shooting):
    """Shooting, but no two plays draw the same picture (a camera or a timer on the wall clock)."""

    plays_made = itertools.count()

    def play(self, *args, **kw):
        found = super().play(*args, **kw)
        n = next(self.plays_made)
        return godot.Played(found.exit_code, found.timed_out, found.output, found.seconds, found.probe, found.log,
                            {k: v + (f":{n}".encode() if k.endswith(".png") else b"") for k, v in found.files.items()})


def checked(test, projects):
    """check_task on the test's game with `projects` ({"start": project, "reference": project}) as the two sides."""
    repo, start, fix, _ = test.game
    names = {start[:12]: "start", fix[:12]: "reference"}

    def project(folder, machine, label):
        found = projects[names[Path(folder).name]]
        found.folder, found.label = Path(folder), label
        return found

    with mock.patch.object(godot, "Project", project), \
            mock.patch.object(godot.Machine, "for_project", classmethod(lambda cls, p, d=False: cls(Path(p), None))), \
            mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0):
        return check.check_task(repo, test.task, test.raw, test.root / "scratch", test.out, log=lambda *a: None)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = make_game(self.tmp.name)

    def seed(self, task):
        _, start, fix, _ = self.game
        task["seed"] = {**task["seed"], "commit": start, "reference": fix}
        self.task, self.raw = task, json.dumps(task).encode()

    @property
    def out(self):
        return self.root / "out"

    def settle(self, raw=None):
        return settle.settle(self.task, raw or self.raw, self.out)

    def refused(self, raw=None):
        with self.assertRaises(settle.Refused) as caught:
            self.settle(raw)
        return str(caught.exception)

    def answer(self, blind, start, reference):
        key = json.loads((blind / "key.json").read_text())
        mine = {"start": start, "reference": reference}
        (blind / "answers.json").write_text(json.dumps({letter: mine[side] for letter, side in key.items()}),
                                            encoding="utf-8")


class Judged(Base):
    def setUp(self):
        super().setUp()
        self.seed(task_with(probe(expect={"op": ">=", "calibrate": 0.5}), judge(reference=True, plays=[play()])))

    def run_check(self, kind=Shooting):
        return checked(self, {"start": kind(measuring(-500), folder="start"),
                              "reference": kind(measuring(100), folder="reference")})

    def blind(self):
        return self.out / TASK / "judge-shots" / JUDGE / "blind"

    def score(self, start, reference):
        self.answer(self.blind(), start, reference)

    def test_it_settles_to_the_verdict_the_two_run_flow_gives(self):
        self.run_check()
        self.score(*PASSING)
        twice = self.run_check()  # pictures byte for byte the same: the scores carry over
        self.assertEqual(twice["verdict"], "VALID", twice["reasons"])
        first = self.run_check(Wobbly)  # a run whose pictures differ: the scores are dropped, its own are written
        self.assertEqual(first["reasons"], [PENDING])
        self.score(*PASSING)
        settled = self.settle()
        for field in FIELDS:
            self.assertEqual(settled[field], twice[field], field)
        self.assertEqual(settled["judges"][JUDGE]["answered"], twice["judges"][JUDGE]["answered"])
        self.assertEqual(settled["judges"][JUDGE]["folder"], f"{TASK}/judge-shots/{JUDGE}/")
        self.assertEqual((settled["settled"]["run_verdict"], settled["settled"]["run_reasons"]), ("INVALID", [PENDING]))
        self.assertEqual(json.loads((self.out / f"{TASK}.json").read_text())["verdict"], "VALID", "written")
        self.assertEqual(self.settle()["verdict"], "VALID", "a settled result settles again from the run it keeps")

    def test_pictures_that_differ_every_run_drop_the_scores_but_settle_on_their_own_run(self):
        self.run_check(Wobbly)
        self.score(*PASSING)
        again = self.run_check(Wobbly)
        self.assertEqual(again["reasons"], [PENDING])
        self.assertEqual(self.refused(), f"judge {JUDGE}: blind/answers.json (the writer's answers) is missing "
                                         f"({self.blind() / 'answers.json'})")
        self.score(*PASSING)
        self.assertEqual((self.settle()["verdict"], self.settle()["reasons"]), ("VALID", []))

    def test_a_failing_reference_score_is_still_invalid(self):
        self.run_check(Wobbly)
        self.score({"door_open": 0, "lit": 1}, {"door_open": 0.4, "lit": 1})
        settled = self.settle()
        self.assertEqual((settled["verdict"], settled["reasons"]),
                         ("INVALID", [f"reference fails judge {JUDGE} as you scored it (weighted 0.80, required item(s) "
                                      "below 0.5: door_open)"]))
        self.score({"door_open": 0.5, "lit": 0}, {"door_open": 1, "lit": 1})
        self.assertEqual(self.settle()["reasons"],
                         [f"start already meets a required item of judge {JUDGE} as you scored it (weighted 0.17)"])

    def test_a_changed_picture_is_refused(self):
        self.run_check()
        self.score(*PASSING)
        picture = sorted(p for p in (self.blind() / "A").iterdir() if p.suffix == ".png")[0]
        picture.write_bytes(b"another picture")
        self.assertIn(f"blind/A/{picture.name} isn't the", self.refused())

    def test_a_side_picture_and_its_listed_hash_changed_together_is_refused(self):
        self.run_check()
        self.score(*PASSING)
        base = self.blind().parent
        listed = json.loads((base / "pictures.json").read_text())
        name = sorted(listed["reference"])[0]
        (base / "reference" / name).write_bytes(b"x")
        listed["reference"][name] = settle._sha(b"x")
        (base / "pictures.json").write_text(json.dumps(listed))
        self.assertIn("pictures.json isn't the one the run saved", self.refused())

    def test_a_changed_key_is_refused(self):
        self.run_check()
        self.score(*PASSING)
        key = json.loads((self.blind() / "key.json").read_text())
        (self.blind() / "key.json").write_text(json.dumps({"A": key["B"], "B": key["A"]}))
        self.assertIn("key.json isn't the one the run saved", self.refused())

    def test_a_key_swapped_in_a_run_saved_before_the_record_is_refused_by_its_pictures(self):
        self.run_check()
        self.score(*PASSING)
        result = json.loads((self.out / f"{TASK}.json").read_text())
        del result["judges"][JUDGE]["bound"]  # as a run of an older checker saved it
        stamp = os.stat(self.out / f"{TASK}.json").st_mtime_ns
        (self.out / f"{TASK}.json").write_text(json.dumps(result))
        os.utime(self.out / f"{TASK}.json", ns=(stamp, stamp))
        self.assertEqual(self.settle()["verdict"], "VALID")
        result = json.loads((self.out / f"{TASK}.json").read_text())["settled"]["run"]
        (self.out / f"{TASK}.json").write_text(json.dumps(result))
        os.utime(self.out / f"{TASK}.json", ns=(stamp, stamp))
        key = json.loads((self.blind() / "key.json").read_text())
        (self.blind() / "key.json").write_text(json.dumps({"A": key["B"], "B": key["A"]}))
        os.utime(self.blind() / "key.json", ns=(stamp - 1, stamp - 1))
        self.assertIn("isn't the", self.refused())

    def test_a_changed_task_is_refused(self):
        self.run_check()
        self.score(*PASSING)
        self.assertEqual(self.refused(self.raw + b"\n"),
                         "the task file isn't the one the run checked (its sha256 differs from the run's task_sha256)")

    def test_missing_answers_are_refused(self):
        self.run_check()
        self.assertIn("blind/answers.json (the writer's answers) is missing", self.refused())
        (self.blind() / "answers.json").write_text(json.dumps({"A": PASSING[0]}))
        self.assertIn("answers no B", self.refused())
        (self.blind() / "answers.json").write_text(json.dumps({"A": PASSING[0], "B": {"door_open": 1}}))
        self.assertIn("B: a side's answer scores every rubric item", self.refused())

    def test_answers_older_than_the_pictures_or_files_written_after_the_run_are_refused(self):
        self.run_check()
        self.score(*PASSING)
        early = os.stat(self.blind() / "key.json").st_mtime_ns - 10 ** 9
        os.utime(self.blind() / "answers.json", ns=(early, early))
        self.assertIn("is older than the pictures it answers", self.refused())
        self.score(*PASSING)
        late = os.stat(self.out / f"{TASK}.json").st_mtime_ns + 10 ** 9
        picture = sorted((self.blind().parent / "start").iterdir())[0]
        os.utime(picture, ns=(late, late))
        self.assertIn(f"start/{picture.name} was written after the run wrote its result", self.refused())

    def test_no_kept_run_an_error_run_or_a_row_the_checker_couldnt_run_is_refused(self):
        self.assertIn("no kept run", self.refused())
        self.run_check()
        self.score(*PASSING)
        result = json.loads((self.out / f"{TASK}.json").read_text())
        stamp = os.stat(self.out / f"{TASK}.json").st_mtime_ns

        def kept(run):
            (self.out / f"{TASK}.json").write_text(json.dumps(run))
            os.utime(self.out / f"{TASK}.json", ns=(stamp, stamp))

        kept({**result, "verdict": "ERROR"})
        self.assertIn("the run's verdict is ERROR", self.refused())
        kept({**result, "start_checks": [], "reference_checks": [], "reasons": ["start doesn't build: ..."]})
        self.assertIn("the run stopped before it graded the start", self.refused())
        rows = [dict(r, detail="the checker failed (OSError: gone)") for r in result["start_checks"]]
        kept({**result, "start_checks": rows})
        self.assertIn("the run has a row the checker couldn't run (start hero_on_ground)", self.refused())

    def test_a_required_judge_the_run_never_played_is_refused(self):
        repo, start, fix, _ = self.game
        with mock.patch.object(godot, "Project", lambda folder, m, label: Shooting(measuring(-500), folder=folder)), \
                mock.patch.object(godot.Machine, "for_project",
                                  classmethod(lambda cls, p, d=False: cls(Path(p), None))), \
                mock.patch.object(godot.ggfroot, "check_free", lambda *a: 100.0):
            check.check_task(repo, self.task, self.raw, self.root / "scratch", self.out, log=lambda *a: None,
                             judge_shots=False)
        self.assertEqual(self.refused(), f"judge {JUDGE}: the run saved no pictures of it (--no-judge-shots?)")

    def test_the_cli_settles_and_plays_nothing(self):
        self.run_check(Wobbly)
        self.score(*PASSING)
        path = self.root / f"{TASK}.json"
        path.write_bytes(self.raw)
        printed = io.StringIO()
        with mock.patch.object(godot, "Project", side_effect=AssertionError("played")), \
                contextlib.redirect_stdout(printed):
            code = cli.main([str(self.game[0]), "--task", str(path), "--out", str(self.out), "--settle"])
        self.assertEqual((code, printed.getvalue()), (0, f"VALID   {TASK}\n"))
        (self.blind() / "answers.json").unlink()
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = cli.main([str(self.game[0]), "--task", str(path), "--out", str(self.out), "--settle"])
        self.assertEqual((code, printed.getvalue().split(" (")[0]),
                         (1, f"REFUSED {TASK}: judge {JUDGE}: blind/answers.json"))


class Seen(Base):
    def setUp(self):
        super().setUp()
        self.seed(task_with(probe(expect={"op": ">=", "calibrate": 0.5}), seen_probe()))

    def run_check(self, seeds_=(1, 2)):
        return checked(self, {"start": Played(seeds_[0], measuring(-500), folder="start"),
                              "reference": Played(seeds_[1], measuring(100), folder="reference")})

    def blind(self):
        return self.out / TASK / "seen-shots" / "combo_shows" / "blind"

    def test_a_seen_probe_settles_as_the_next_check_reads_it(self):
        self.run_check()
        self.answer(self.blind(), ["COMBO x0"], ["COMBO x3"])
        twice = self.run_check()
        self.assertEqual(twice["verdict"], "VALID", twice["reasons"])
        self.run_check((7, 8))  # other crops: the answers are dropped
        self.answer(self.blind(), ["COMBO x0"], ["COMBO x3"])
        settled = self.settle()
        for field in FIELDS:
            self.assertEqual(settled[field], twice[field], field)
        self.answer(self.blind(), ["COMBO x3"], ["COMBO x3"])
        settled = self.settle()
        again = self.run_check((7, 8))  # the same crops: the answers carry over to a check of its own
        self.assertEqual(settled["verdict"], "INVALID")
        for field in FIELDS:
            self.assertEqual(settled[field], again[field], field)

    def test_a_crop_that_changed_is_refused(self):
        self.run_check()
        self.answer(self.blind(), ["COMBO x0"], ["COMBO x3"])
        (self.blind().parent / "start" / "combo.png").write_bytes(b"x")
        self.assertIn("start/combo.png changed since the run saved it", self.refused())

    def test_an_answer_of_the_wrong_shape_is_refused(self):
        self.run_check()
        self.answer(self.blind(), "COMBO x0", ["COMBO x3"])
        self.assertIn("a shot's answer is a list of lines", self.refused())


class SeenUnbuilt(Base):
    """A start that doesn't build by design is never played: its seen probe measures nothing there, as in the run."""

    def setUp(self):
        super().setUp()
        self.seed(task_with(milestones=[
            {"name": "builds", "checks": [{"kind": "build", "name": "player_builds", "fails_at_start": True}]},
            {"name": "graded", "checks": [seen_probe(needs=["player_builds"])]}]))

    def run_check(self, seed=2):
        return checked(self, {"start": Played(1, measuring(-5), folder="start", build_exit=6),
                              "reference": Played(seed, measuring(5), folder="reference")})

    def test_it_settles_as_the_next_check_reads_it(self):
        blind = self.out / TASK / "seen-shots" / "combo_shows" / "blind"
        self.run_check()
        self.assertEqual(json.loads((blind / "key.json").read_text()), {"A": "reference"})
        self.answer(blind, None, ["COMBO x3"])
        twice = self.run_check()
        self.run_check(9)
        self.answer(blind, None, ["COMBO x3"])
        settled = self.settle()
        for field in FIELDS:
            self.assertEqual(settled[field], twice[field], field)
        self.assertEqual(settled["verdict"], "VALID", settled["reasons"])


if __name__ == "__main__":
    unittest.main()
