"""The pure parts of the runner, the verification and the package: identities, comparisons, the verdict, the report
schema, the settings. No engine.

    python -m unittest discover -s tools/godot-replay/tests -v
"""
import collections
import json
import os
import unittest
from unittest import mock

import helpers

import godot_replay
import package
import runner
import verify

SHA = "0123456789abcdef0123456789abcdef01234567"


def report(files=None, structure=None, windows=None):
    r = {"schema": verify.SCHEMA_ID, "game": "tiny", "final_commit": SHA, "time": "2026-01-10T10:00:00+00:00",
         "files": files or {"identical": 3, "differs": [], "missing": [], "extra": [], "ignored": ["Logs/a.log"]},
         "structure": structure or verify.verify_structure({}, {}),
         "runs": {"exit_code": {}, "step_text": {}, "runs": []},
         "windows": windows or [{"window": 1, "commit": SHA, "runs": 0, "seconds": 1.0, "content": {"adopted_uids": 2}}]}
    r["verdict"] = verify.verdict(r, collections.Counter(uid=1))
    return r


class Identity(unittest.TestCase):
    def test_file_uid(self):
        self.assertEqual(runner.file_uid("game/a.gd.uid", b"uid://cwlihr3duvehk\n"), b"uid://cwlihr3duvehk")
        self.assertEqual(runner.file_uid("a.png.import", b'[remap]\n\nimporter="texture"\nuid="uid://bkk7"\npath="x"\n'), b"uid://bkk7")
        self.assertEqual(runner.file_uid("a.tscn", b'[gd_scene load_steps=2 format=3 uid="uid://c1"]\n\n[ext_resource uid="uid://zz"]\n'), b"uid://c1")
        self.assertIsNone(runner.file_uid("a.tres", b'[gd_resource type="Gradient" format=3]\n\n[ext_resource uid="uid://zz"]\n'))
        self.assertIsNone(runner.file_uid("a.gd.uid", b"not a uid\n"))

    def test_adopt_identity(self):
        root = helpers.scratch()
        repo = root + "/tiny"
        os.makedirs(repo)
        helpers.git(repo, "init", "-q")
        helpers.write(repo, "game/a.gd.uid", "uid://commit1\n")
        helpers.write(repo, "scenes/Made.tscn", '[gd_scene format=3]\n\n[ext_resource type="Script" uid="uid://commit1" path="res://game/a.gd" id="1"]\n')
        helpers.write(repo, "scenes/Old.tscn", '[ext_resource uid="uid://replay9" id="1"]\n')
        sha = helpers.commit(repo, 0, "c")
        helpers.write(repo, "game/a.gd.uid", "uid://replay9\n")
        helpers.write(repo, "scenes/Made.tscn", helpers.read(repo, "scenes/Made.tscn").replace("commit1", "replay9"))
        ctx = runner.Ctx({"repo": repo, "project_dir": repo, "work_dir": root + "/work", "game": "tiny"})
        ctx.state["window_outputs"] = ["game/a.gd.uid", "scenes/Made.tscn", "gone.txt"]
        got = runner.adopt_identity(ctx, {"sha": sha}, runner.tree_ids(repo, sha))
        self.assertEqual(got, {"uid://replay9": "uid://commit1"})
        self.assertEqual(helpers.git(repo, "status", "--short", "--", "game", "scenes/Made.tscn"), "")
        # a file the window did not generate keeps what it says
        self.assertIn("replay9", helpers.read(repo, "scenes/Old.tscn"))

    def test_scan_and_untracked(self):
        root = helpers.scratch()
        helpers.git(root, "init", "-q")
        helpers.write(root, ".gitignore", ".godot/\n/Logs/\n")
        helpers.write(root, "a.gd", "extends Node\n")
        sha = helpers.commit(root, 0, "c")
        before = runner.scan(root)
        helpers.write(root, ".godot/cache.bin", "x")
        helpers.write(root, "Logs/run.log", "x")
        helpers.write(root, "b.gd", "extends Node\n")
        helpers.write(root, "a.gd", "extends Node2D\n")
        self.assertEqual(runner.diff_scan(before, runner.scan(root)), (["Logs/run.log", "b.gd"], ["a.gd"], []))
        self.assertEqual(runner.untracked(root, runner.tree_ids(root, sha)), (["b.gd"], ["Logs/run.log"]))

    def test_delete_paths_keeps_what_the_commit_has_and_stays_inside(self):
        root = helpers.scratch()
        for rel in ("assets/tmp.txt", "assets/keep.txt", "scratch/a/b.txt"):
            helpers.write(root + "/p", rel, "x")
        helpers.write(root, "outside.txt", "x")
        ctx = runner.Ctx({"repo": root + "/p", "project_dir": root + "/p", "work_dir": root + "/work", "game": "tiny"})
        n = runner.delete_paths(ctx, {"paths": ["assets/tmp.txt", "assets/keep.txt", "scratch", "../outside.txt", ".git"]},
                                {"assets/keep.txt"})
        self.assertEqual(n, 2)
        self.assertEqual(sorted(runner.scan(root + "/p")), ["assets/keep.txt"])
        self.assertTrue(os.path.exists(root + "/outside.txt"))


class Compare(unittest.TestCase):
    def test_floats_and_uids(self):
        counts = collections.Counter()
        a = {"nodes": [{"path": ".", "props": {"position": {"args": [1.0, 2.00001], "type": "Vector2"}, "tex": "uid://abc"}}]}
        b = {"nodes": [{"path": ".", "props": {"position": {"args": [1.0, 2.0], "type": "Vector2"}, "tex": "uid://xyz"}}]}
        self.assertEqual(verify.tolerant_diff(a, b, counts), [])
        self.assertEqual(counts["uid"], 1)
        b["nodes"][0]["props"]["position"]["args"][1] = 2.5
        self.assertEqual(verify.tolerant_diff(a, b, counts), ["nodes[0].props.position.args"])

    def test_structure(self):
        rep = {"scenes": {"res://a.tscn": {"nodes": []}, "res://extra.tscn": {"nodes": []}},
               "resources": {"res://p.tres": {"class": "Gradient", "props": {"colors": [1, 0]}}},
               "imported": {"res://i.png": {"importer": "texture", "params": {"mipmaps/generate": False}}}}
        tru = {"scenes": {"res://a.tscn": {"nodes": []}, "res://gone.tscn": {"nodes": []}},
               "resources": {"res://p.tres": {"class": "Gradient", "props": {"colors": [0, 0]}}},
               "imported": {"res://i.png": {"importer": "texture", "params": {"mipmaps/generate": False}}}}
        s = verify.verify_structure(rep, tru)
        self.assertEqual(s["total"], {"same": 2, "missing": 1, "extra": 1, "differs": 1})
        self.assertEqual(s["by_kind"]["resources"], {"differs": 1})
        self.assertIn({"path": "res://p.tres", "kind": "resources", "result": "differs", "keys": ["props.colors"]}, s["diffs"])
        self.assertEqual(verify.verify_structure(tru, tru)["diffs"], [])

    def test_same_but_uids(self):
        root = helpers.scratch()
        helpers.write(root, "a.tscn", '[ext_resource uid="uid://abc" path="res://a.png"]\n')
        self.assertTrue(verify.same_but_uids(root + "/a.tscn", b'[ext_resource uid="uid://xyz" path="res://a.png"]\n'))
        self.assertFalse(verify.same_but_uids(root + "/a.tscn", b'[ext_resource uid="uid://xyz" path="res://b.png"]\n'))


class Verdict(unittest.TestCase):
    def test_pass_and_schema(self):
        r = report()
        self.assertTrue(r["verdict"]["pass"])
        self.assertEqual([c["id"] for c in r["verdict"]["criteria"]], ["files", "structure"])
        self.assertEqual({e["id"]: e["count"] for e in r["verdict"]["exclusions"]},
                         {"uid": 1, "uids_adopted": 2, "git_ignored_extra_files": 1})
        self.assertEqual(verify.validate_report(r), [])
        self.assertIn("## Verdict: PASS", verify.render_md(dict(r, deviations=[])))

    def test_each_criterion_fails_alone(self):
        for files in ({"identical": 2, "differs": ["a.tres"], "missing": [], "extra": [], "ignored": []},
                      {"identical": 2, "differs": [], "missing": ["a.tres"], "extra": [], "ignored": []},
                      {"identical": 2, "differs": [], "missing": [], "extra": ["new.txt"], "ignored": []}):
            v = report(files=files)["verdict"]
            self.assertEqual((v["pass"], v["criteria"][0]["pass"], v["criteria"][1]["pass"]), (False, False, True))
        v = report(structure=verify.verify_structure({"scenes": {}}, {"scenes": {"res://a.tscn": {}}}))["verdict"]
        self.assertEqual((v["pass"], v["criteria"][0]["pass"], v["criteria"][1]["pass"]), (False, True, False))
        v = report(structure={"total": {}, "note": "the truth dump did not finish"})["verdict"]
        self.assertFalse(v["pass"])

    def test_schema_refuses(self):
        r = report()
        bad = dict(r, final_commit="abc", windows=[{"window": 0, "commit": SHA}])
        del bad["structure"]
        self.assertEqual(sorted(p.split(":")[0] for p in verify.validate_report(bad)),
                         ["report", "report.final_commit", "report.windows[0].window"])

    def test_the_keys_the_packager_reads(self):
        v = report()["verdict"]
        self.assertIsInstance(v["pass"], bool)
        for c in v["criteria"]:
            self.assertEqual(sorted(k for k in c if k != "failures"), ["id", "pass", "result", "text"])
        for e in v["exclusions"]:
            self.assertLessEqual({"id", "what", "count"}, set(e))


class Settings(unittest.TestCase):
    def test_defaults_and_template(self):
        root = helpers.scratch()
        repo = root + "/games/my-game"
        os.makedirs(repo + "/.git")
        with mock.patch.dict(os.environ, {"GGF_ROOT": root}):
            cfg = godot_replay.load_cfg("my-game")
            self.assertEqual((cfg["game"], cfg["final"], cfg["run_timeout_s"]), ("my-game", "HEAD", 3600))
            self.assertEqual(cfg["_raw"]["repo"], "{root}/games/my-game")
            self.assertEqual(cfg["recording"], root + "/.recording/my-game")
            self.assertEqual(cfg["project_dir"].replace("\\", "/"), root + "/godot-replay/my-game/my-game")
            with open(os.path.join(helpers.REPO, "templates", "godot-game", "ReplayConfig.json"), encoding="utf-8") as f:
                text = f.read()
            helpers.write(repo, "ReplayConfig.json", text.replace("__SLUG__", "my-game"))
            self.assertEqual({k: v for k, v in godot_replay.load_cfg("my-game").items() if not k.startswith("_")},
                             {k: v for k, v in cfg.items() if not k.startswith("_")})
            # a copy of the game elsewhere replays in a work folder of its own
            other = root + "/copies/my-game"
            os.makedirs(other + "/.git")
            self.assertIn("/godot-replay/_other/my-game-", godot_replay.load_cfg(other)["work_root"])

    def test_session_names(self):
        sid = "0f8fad5b-d9cb-469f-a165-70867728950e"
        text, counts = godot_replay.neutral_session_paths(
            "C:\\\\Users\\\\x\\\\AppData\\\\Local\\\\Temp\\\\tool\\\\proj\\\\%s\\\\scratchpad\\\\a.py and %s" % (sid, sid), [sid])
        self.assertNotIn(sid, text)
        self.assertIn("Temp\\\\session\\\\scratch\\\\a.py", text)
        self.assertEqual(package.total_windows({"windows": [{}, {}, {}]}), 2)


if __name__ == "__main__":
    unittest.main()
