"""The ledger: step calls found in recorded commands, files split into inputs and generated files, step texts as they
stood when a run started. No engine.

    python -m unittest discover -s tools/godot-replay/tests -v
"""
import json
import os
import unittest

import helpers
from helpers import at

import ledger
import patchfx
import shellfx

STEP = 'powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 step -Script %s -Reason "%s"'


class Calls(unittest.TestCase):
    def test_step_path(self):
        for given, want in (("steps/a.gd", "steps/a.gd"), ("res://steps/a.gd", "steps/a.gd"),
                            (".\\steps\\sub\\a.gd", "steps/sub/a.gd"), ("'steps/a.gd'", "steps/a.gd"),
                            ("steps/$s.gd", None), ("C:/x/steps/a.gd", None), ("../a.gd", None), ("steps/a.txt", None)):
            self.assertEqual(ledger.step_path(given), want, given)

    def test_find_calls(self):
        self.assertEqual(ledger.find_calls(STEP % ("steps/a.gd", "the level")),
                         [{"script": "steps/a.gd", "reason": "the level"}])
        self.assertEqual(ledger.find_calls("& .\\Scripts\\godot.ps1 step -Script steps\\a.gd")[0]["script"], "steps\\a.gd")
        self.assertEqual(ledger.find_calls("./Scripts/godot.ps1 -Mode step -Script steps/a.gd")[0]["script"], "steps/a.gd")
        for other in ("Scripts/godot.ps1 import", "Scripts/godot.ps1 build -Reason x", "echo step -Script steps/a.gd"):
            self.assertEqual(ledger.find_calls(other), [])

    def test_step_runs_cuts_the_output_per_run(self):
        cmd = "%s && %s" % (STEP % ("steps/a.gd", "one"), STEP % ("steps/b.gd", "two"))
        out = ("[workflow] tiny-0002 editor.step steps/a.gd\nexit code 0 (3 s)\n"
               "[workflow] tiny-0003 editor.step steps/b.gd (failed)\nexit code 1 (1 s)\n")
        a = {"time": at(5), "tool": "Bash", "event": "PostToolUse", "tool_use_id": "t1", "session_id": "s",
             "input": {"command": cmd}, "response": {"stdout": out}}
        runs, unreadable = ledger.step_runs([a])
        self.assertEqual([(r["script"], r["exit_code"], r["duration_s"], r["rows"]) for r in runs],
                         [("steps/a.gd", 0, 3, ["tiny-0002"]), ("steps/b.gd", 1, 1, ["tiny-0003"])])
        self.assertEqual(unreadable, [])

    def test_step_runs_in_a_loop_and_unreadable(self):
        loop = 'for s in walls floor; do ./Scripts/godot.ps1 step -Script steps/$s.gd -Reason "part"; done'
        bad = "./Scripts/godot.ps1 step -Script $(ls steps | head -1)"
        acts = [{"time": at(1), "tool": "Bash", "event": "PostToolUse", "tool_use_id": "t1", "session_id": "s",
                 "input": {"command": loop}, "response": ""},
                {"time": at(2), "tool": "Bash", "event": "PostToolUseFailure", "tool_use_id": "t2", "session_id": "s",
                 "input": {"command": bad}, "response": ""},
                {"time": at(3), "tool": "Bash", "event": "PreToolUse", "tool_use_id": "t3", "session_id": "s",
                 "input": {"command": STEP % ("steps/never.gd", "x")}, "response": ""}]
        runs, unreadable = ledger.step_runs(acts)
        self.assertEqual([r["script"] for r in runs], ["steps/walls.gd", "steps/floor.gd"])
        self.assertEqual(len(unreadable), 1)

    def test_generated_kind(self):
        self.assertEqual(ledger.generated_kind("assets/a.png.import"), "sidecar")
        self.assertEqual(ledger.generated_kind("game/a.gd.uid"), "sidecar")
        self.assertEqual(ledger.generated_kind("assets/a.tres"), "resource")
        self.assertEqual(ledger.generated_kind("assets/a.png"), None)
        self.assertEqual(ledger.generated_kind("data/level.bin", [".bin"]), "resource")


class Texts(unittest.TestCase):
    def test_patch(self):
        ops = patchfx.parse("*** Begin Patch\n*** Update File: a.gd\n@@\n-var a = 1\n+var a = 2\n*** End Patch\n")
        self.assertEqual(patchfx.apply_update("extends Node\nvar a = 1\n", ops[0][2]["hunks"]), "extends Node\nvar a = 2\n")
        self.assertIsNone(patchfx.apply_update("extends Node\n", ops[0][2]["hunks"]))

    def test_heredoc_is_not_a_command(self):
        text, bodies = shellfx.protect_heredocs("cat > steps/a.gd <<'EOF'\nScripts/godot.ps1 step -Script steps/x.gd\nEOF\necho done")
        self.assertNotIn("godot.ps1", text)
        self.assertEqual(shellfx.segments("a && b; c | d"), ["a", "b", "c", "d"])

    def test_content_ops(self):
        a = {"tool": "Bash", "cwd": "C:/w/games/tiny", "input": {"command": "rm assets/tmp.txt && mv a.tres b.tres && rm -rf $OUT"}}
        ops, skipped = shellfx.content_ops(a, "C:/w/games/tiny", lambda p: True)
        self.assertEqual([(o["op"], o["src"]) for o in ops], [("delete", ["assets/tmp.txt"]), ("move", ["a.tres"])])


class Build(unittest.TestCase):
    """One small history: a skeleton, a window of recorded writes, a window with a step run that is committed by the
    same command, and a file the recording does not explain."""

    @classmethod
    def setUpClass(cls):
        cls.root = helpers.scratch()
        repo = cls.repo = cls.root + "/games/tiny"
        os.makedirs(repo)
        helpers.git(repo, "init", "-q")
        helpers.write(repo, "project.godot", "config_version=5\n")
        helpers.write(repo, "scenes/Main.tscn", "[gd_scene format=3]\n\n[node name=\"Main\" type=\"Node2D\"]\n")
        helpers.write(repo, "assets/icon.png", b"\x89PNG one")
        helpers.write(repo, "assets/icon.png.import", "[remap]\nuid=\"uid://aaa1\"\n[params]\nloop=false\n")
        helpers.write(repo, "workflow.jsonl", '{"id": "tiny-0001", "op": "game.create"}\n')
        helpers.commit(repo, 0, "skeleton")
        rec = cls.rec = helpers.Recording(cls.root + "/.recording/tiny", repo)
        # window 1: a scene edited, a script written (its .uid comes from the engine), an import setting edited
        rec.edit(at(1), "scenes/Main.tscn", 'type="Node2D"]\n', 'type="Node2D"]\n\n[node name="Hud" type="Label" parent="."]\n')
        rec.write(at(2), "game/main.gd", "extends Node2D\n")
        helpers.write(repo, "game/main.gd.uid", "uid://bbb2\n")
        rec.edit(at(3), "assets/icon.png.import", "loop=false", "loop=true")
        helpers.commit(repo, 10, "the hud")
        # window 2: a step written, run and committed by one command, then edited (the edit belongs to window 3)
        rec.write(at(11), "steps/make.gd", "extends SceneTree\n# v1\n")
        helpers.write(repo, "assets/palette.tres", "[gd_resource type=\"Gradient\" format=3]\n")
        helpers.write(repo, "steps/make.gd.uid", "uid://ccc3\n")
        helpers.write(repo, "workflow.jsonl", helpers.read(repo, "workflow.jsonl") +
                      '{"id": "tiny-0002", "op": "editor.step", "source": {"script": "steps/make.gd", "sha256": "%s"}}\n'
                      % ledger.sha256(b"extends SceneTree\n# v1\n"))
        helpers.commit(repo, 20, "the palette")
        rec.bash(at(20, 2), (STEP % ("steps/make.gd", "palette")) + " && git add -A && git commit -m 'the palette'",
                 "[workflow] tiny-0002 editor.step steps/make.gd\nexit code 0 (2 s)\n")
        # window 3: the step edited after it ran, a file deleted by the shell, a resource nothing explains
        rec.edit(at(21), "steps/make.gd", "# v1", "# v2")
        rec.bash(at(22), "rm assets/tmp_note.txt")
        helpers.write(repo, "assets/mystery.tres", "[gd_resource type=\"Gradient\" format=3]\n")
        helpers.write(repo, "assets/orphan.wav.import", "[remap]\n")
        cls.final = helpers.commit(repo, 30, "later")
        cls.led, cls.blobs = ledger.build({"game": "tiny", "repo": repo, "recording": cls.root + "/.recording/tiny",
                                           "final": "HEAD", "work_dir": cls.root + "/work"})

    def paths(self, w, key):
        return sorted(x["path"] for x in self.led["windows"][w][key])

    def test_windows(self):
        self.assertEqual(self.led["final"], self.final)
        self.assertEqual(self.led["counts"]["windows"], 3)
        self.assertEqual([w["subject"] for w in self.led["windows"]], ["skeleton", "the hud", "the palette", "later"])

    def test_recorded_writes_are_inputs(self):
        self.assertEqual(self.paths(1, "inputs"), ["assets/icon.png.import", "game/main.gd", "scenes/Main.tscn"])
        self.assertEqual(self.paths(1, "content"), ["game/main.gd.uid"])
        self.assertTrue(all(x.get("written") for x in self.led["windows"][1]["inputs"]))
        self.assertTrue(all(c["match"] for c in self.led["windows"][1]["reconstruction"]))

    def test_run_lands_before_the_commit_its_command_made(self):
        w = self.led["windows"][2]
        self.assertEqual([(r["script"], r["exit_code"], r["script_version"]) for r in w["runs"]],
                         [("steps/make.gd", 0, "reconstructed")])
        r = w["runs"][0]
        self.assertEqual(self.blobs[r["texts"]["steps/make.gd"]], b"extends SceneTree\n# v1\n")
        self.assertEqual(r["row_sha256"], r["texts"]["steps/make.gd"])
        self.assertEqual(self.paths(2, "content"), ["assets/palette.tres", "steps/make.gd.uid"])
        self.assertEqual(self.paths(2, "inputs"), ["steps/make.gd", "workflow.jsonl"])
        self.assertEqual([x.get("written", False) for x in w["inputs"]], [True, False])

    def test_later_window(self):
        w = self.led["windows"][3]
        self.assertEqual(w["runs"], [])
        self.assertEqual([s["paths"] for s in w["shell"]], [["assets/tmp_note.txt"]])
        self.assertEqual(self.paths(3, "content"), ["assets/mystery.tres"])
        self.assertEqual(self.paths(3, "inputs"), ["assets/orphan.wav.import", "steps/make.gd"])


def ag(row):
    """A row as Antigravity's hook leaves it: its own tool name and arguments, agent "antigravity"."""
    return dict(row, agent="antigravity")


class AsClaude(unittest.TestCase):
    def test_known_tools_are_read_as_claude_codes(self):
        bash = ledger.as_claude(ag({"tool": "run_command", "input": {"CommandLine": "godot.ps1 step", "Cwd": "C:/w"}}))
        self.assertEqual((bash["tool"], bash["input"]["command"], bash["input"]["Cwd"]),
                         ("Bash", "godot.ps1 step", "C:/w"))
        w = ledger.as_claude(ag({"tool": "write_file", "input": {"Path": "C:/w/a.gd", "Content": "x\n"}}))
        self.assertEqual((w["tool"], w["input"]), ("Write", {"file_path": "C:/w/a.gd", "content": "x\n"}))
        e = ledger.as_claude(ag({"tool": "edit_file", "input": {"Path": "C:/w/a.gd", "Target": "x", "Replacement": "y",
                                                               "AllowMultiple": True}}))
        self.assertEqual((e["tool"], e["input"]), ("Edit", {"file_path": "C:/w/a.gd", "old_string": "x",
                                                           "new_string": "y", "replace_all": True}))
        a = ledger.as_claude(ag({"tool": "write_file", "input": {"Path": "C:/w/a.gd", "Content": "z", "Append": True}}))
        self.assertEqual((a["tool"], a["input"]), ("Append", {"file_path": "C:/w/a.gd", "content": "z"}))

    def test_another_file_tool_is_unreplayed_and_other_rows_stay(self):
        r = ledger.as_claude(ag({"tool": "replace_file_content", "input": {"TargetFile": "C:/w/b.gd"}}))
        self.assertEqual((r["tool"], r["input"]["file_path"]), ("Unreplayed", "C:/w/b.gd"))
        for row in (ag({"tool": "read_file", "input": {"Path": "C:/w/a.gd"}}),
                    {"agent": "codex", "tool": "run_command", "input": {"CommandLine": "dir"}}):
            self.assertIs(ledger.as_claude(row), row)


class BuildAntigravity(unittest.TestCase):
    """The same kind of history made by Antigravity: its writes, edits and appends reconstruct the commit, its step run
    is found in run_command, and a file another of its tools wrote is unknown."""

    @classmethod
    def setUpClass(cls):
        cls.root = helpers.scratch()
        repo = cls.repo = cls.root + "/games/tiny"
        os.makedirs(repo)
        helpers.git(repo, "init", "-q")
        helpers.write(repo, "project.godot", "config_version=5\n")
        helpers.write(repo, "workflow.jsonl", '{"id": "tiny-0001", "op": "game.create"}\n')
        helpers.commit(repo, 0, "skeleton")
        rec = helpers.Recording(cls.root + "/.recording/tiny", repo)
        full = lambda rel: repo + "/" + rel
        # window 1: a script written, edited and appended to; another file written by a tool the ledger cannot replay
        helpers.write(repo, "game/main.gd", "extends Node2D\nvar a = 2\n# end\n")
        rec.row(at(1), "write_file", {"Path": full("game/main.gd"), "Content": "extends Node2D\nvar a = 1\n"})
        rec.row(at(2), "edit_file", {"Path": full("game/main.gd"), "Target": "a = 1", "Replacement": "a = 2"})
        rec.row(at(3), "write_file", {"Path": full("game/main.gd"), "Content": "# end\n", "Append": True})
        helpers.write(repo, "game/other.gd", "extends Node\n")
        rec.row(at(4), "replace_file_content", {"TargetFile": full("game/other.gd"), "ReplacementChunks": []})
        helpers.commit(repo, 10, "the script")
        # window 2: a step written and run through run_command
        helpers.write(repo, "steps/make.gd", "extends SceneTree\n# v1\n")
        rec.row(at(11), "write_file", {"Path": full("steps/make.gd"), "Content": "extends SceneTree\n# v1\n"})
        helpers.write(repo, "workflow.jsonl", helpers.read(repo, "workflow.jsonl") +
                      '{"id": "tiny-0002", "op": "editor.step", "source": {"script": "steps/make.gd", "sha256": "%s"}}\n'
                      % ledger.sha256(b"extends SceneTree\n# v1\n"))
        rec.row(at(12), "run_command", {"CommandLine": STEP % ("steps/make.gd", "palette")},
                "Command exited with code 0.\n[workflow] tiny-0002 editor.step steps/make.gd\nexit code 0 (2 s)\n")
        helpers.commit(repo, 20, "the step")
        with open(cls.root + "/.recording/tiny/actions.jsonl", encoding="utf-8") as f:
            rows = [ag(json.loads(l)) for l in f if l.strip()]
        with open(cls.root + "/.recording/tiny/actions.jsonl", "w", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        cls.led, cls.blobs = ledger.build({"game": "tiny", "repo": repo, "recording": cls.root + "/.recording/tiny",
                                           "final": "HEAD", "work_dir": cls.root + "/work"})

    def test_writes_edits_and_appends_reconstruct_the_commit(self):
        checks = {c["path"]: c for c in self.led["windows"][1]["reconstruction"]}
        self.assertTrue(checks["game/main.gd"]["match"], checks["game/main.gd"])
        self.assertEqual(self.led["windows"][1]["events"]["unreplayed"], 1)

    def test_the_step_run_is_found_in_run_command(self):
        w = self.led["windows"][2]
        self.assertEqual([(r["script"], r["exit_code"]) for r in w["runs"]], [("steps/make.gd", 0)])
        self.assertEqual(self.blobs[w["runs"][0]["texts"]["steps/make.gd"]], b"extends SceneTree\n# v1\n")


if __name__ == "__main__":
    unittest.main()
