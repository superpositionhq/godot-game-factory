"""End to end, with the engine: a small game made here commit by commit (a skeleton with a scene, a script edit, a
generator step, an imported PNG) with the recording a session would leave, replayed, verified and packaged. One
history ends PASS; one whose committed step output is not what the step writes ends FAIL, with the reason.

Needs the engine: set GODOT_EDITOR to the editor binary (skipped without it).

    python -m unittest discover -s tools/godot-replay/tests -p "test_e2e.py" -v
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import unittest
import zlib

import helpers
from helpers import at

import ledger
import verify

GODOT = os.environ.get("GODOT_EDITOR") or ""
HAVE_LFS = shutil.which("git-lfs") is not None

PROJECT = """config_version=5

[application]

config/name="Tiny"
run/main_scene="res://scenes/Main.tscn"
config/features=PackedStringArray("4.7", "Forward Plus")
"""
MAIN_TSCN = """[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://game/main.gd" id="1"]

[node name="Main" type="Node2D"]
script = ExtResource("1")
"""
STEP_V1 = """extends SceneTree


func _init() -> void:
	DirAccess.make_dir_recursive_absolute("res://assets")
	var g := Gradient.new()
	g.colors = PackedColorArray([Color.RED, Color.BLUE])
	var err := ResourceSaver.save(g, "res://assets/palette.tres")
	var f := FileAccess.open("res://assets/palette.json", FileAccess.WRITE)
	f.store_string('{"colors": 2}\\n')
	f.close()
	f = FileAccess.open("res://assets/tmp_note.txt", FileAccess.WRITE)
	f.store_string("scratch\\n")
	f.close()
	quit(err)
"""
STEP_CALL = 'powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 step -Script steps/make_palette.gd -Reason "the palette"'


def png(w, h):
    raw = b"".join(b"\x00" + b"\xff\x00\x00\xff" * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def godot(repo, *args):
    r = subprocess.run([GODOT, "--headless", "--path", repo] + list(args), capture_output=True, cwd=repo, timeout=120)
    return r.returncode


def make_game(root, tamper):
    """<root>/games/tiny and <root>/.recording/tiny, as a session on a factory machine leaves them. The engine runs
    here as it did for the builder: an import before every commit, the step once."""
    repo = root + "/games/tiny"
    os.makedirs(repo)
    helpers.git(repo, "init", "-q")
    if HAVE_LFS:
        helpers.git(repo, "lfs", "install", "--local")
    helpers.write(repo, ".gitignore", ".godot/\n/Logs/\n")
    helpers.write(repo, ".gitattributes", "*.png filter=lfs diff=lfs merge=lfs -text\n" if HAVE_LFS else "*.png binary\n")
    helpers.write(repo, "project.godot", PROJECT)
    helpers.write(repo, "scenes/Main.tscn", MAIN_TSCN)
    helpers.write(repo, "game/main.gd", "extends Node2D\n\nvar speed := 100.0\n")
    helpers.write(repo, "Scripts/.gdignore", "")
    helpers.write(repo, "workflow.jsonl", '{"id": "tiny-0001", "op": "game.create", "target": "tiny"}\n')
    godot(repo, "--import")
    helpers.commit(repo, 0, "Tiny: the skeleton")
    rec = helpers.Recording(root + "/.recording/tiny", repo)

    # 1. a script edit, a new script and the scene that uses it, written with the file tools
    rec.edit(at(1), "game/main.gd", "speed := 100.0", "speed := 240.0")
    rec.write(at(2), "game/player.gd", "extends Sprite2D\n\nvar lives := 3\n")
    rec.edit(at(3), "scenes/Main.tscn", 'script = ExtResource("1")\n',
             'script = ExtResource("1")\n\n[node name="Player" type="Sprite2D" parent="."]\nposition = Vector2(64, 32)\n')
    godot(repo, "--import")
    rec.bash(at(4), "powershell -File Scripts/godot.ps1 import", "exit code 0 (2 s)\n")
    helpers.commit(repo, 10, "Player node and speed")

    # 2. a generator step: written, run, then edited after the run (the replay must run the text it had then);
    #    the scratch file it wrote is deleted by hand
    rec.write(at(11), "steps/make_palette.gd", STEP_V1)
    godot(repo, "--script", "res://steps/make_palette.gd")
    helpers.write(repo, "workflow.jsonl", helpers.read(repo, "workflow.jsonl") + json.dumps(
        {"id": "tiny-0002", "op": "editor.step", "target": "steps/make_palette.gd", "status": "observed",
         "source": {"script": "steps/make_palette.gd", "sha256": ledger.sha256(STEP_V1.encode())}}) + "\n")
    rec.bash(at(12), STEP_CALL, "[workflow] tiny-0002 editor.step steps/make_palette.gd\nexit code 0 (1 s)\n")
    os.remove(repo + "/assets/tmp_note.txt")
    rec.bash(at(13), "rm assets/tmp_note.txt")
    rec.edit(at(14), "steps/make_palette.gd", "Color.BLUE", "Color.GREEN")
    if tamper:   # the committed output is not what the step wrote, and nothing recorded says why
        helpers.write(repo, "assets/palette.tres", helpers.read(repo, "assets/palette.tres").replace("1, 0, 0, 1", "0, 0, 0, 1"))
    godot(repo, "--import")
    helpers.commit(repo, 20, "The palette, from a step")

    # 3. an image copied in by a shell command, imported by the engine; a script renamed with its .uid, so the uid
    #    the builder's engine gave it is not the one a new file of that name gets
    helpers.write(repo, "assets/red.png", png(8, 8))
    rec.bash(at(21), "cp ../../art/red.png assets/red.png")
    for name in ("player.gd", "player.gd.uid"):
        helpers.git(repo, "mv", "game/" + name, "game/" + name.replace("player", "hero"))
    rec.bash(at(22), "git mv game/player.gd game/hero.gd && git mv game/player.gd.uid game/hero.gd.uid")
    godot(repo, "--import")
    # its import settings changed by hand in a way the recording cannot follow, then imported again; and a .import
    # left behind without its source file
    helpers.write(repo, "assets/red.png.import", helpers.read(repo, "assets/red.png.import").replace("mipmaps/generate=false", "mipmaps/generate=true"))
    rec.bash(at(23), "sed -i s/generate=false/generate=true/ assets/*.import")
    godot(repo, "--import")
    helpers.write(repo, "assets/gone.png.import", '[remap]\n\nimporter="texture"\n')
    helpers.commit(repo, 30, "A sprite image")
    return repo


def release(root):
    env = dict(os.environ, GGF_ROOT=root, GGF_OUT=root + "/deliverables", GGF_MIN_FREE_GB="1",
               GGF_CONFIG=root + "/no-config.json", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.join(helpers.TOOL, "godot_replay.py"), "release", "--game", "tiny"],
                       capture_output=True, env=env)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


@unittest.skipUnless(GODOT and os.path.isfile(GODOT), "GODOT_EDITOR is not set to the editor binary")
class Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = {}
        for name, tamper in (("pass", False), ("fail", True)):
            root = helpers.scratch("ggfr-%s-" % name)
            repo = make_game(root, tamper)
            final = helpers.git(repo, "rev-parse", "HEAD").strip()
            code, out = release(root)
            pkg = "%s/deliverables/_replay/tiny/%s" % (root, final[:8])
            cls.games[name] = {"root": root, "final": final, "code": code, "out": out, "pkg": pkg}

    def report(self, name):
        g = self.games[name]
        self.assertTrue(os.path.isfile(g["pkg"] + "/READY"), g["out"][-3000:])
        with open(g["pkg"] + "/ReplayScripts/Verification/report.json", encoding="utf-8") as f:
            return json.load(f)

    def test_pass(self):
        g, r = self.games["pass"], self.report("pass")
        self.assertEqual([(c["id"], c["pass"]) for c in r["verdict"]["criteria"]], [("files", True), ("structure", True)],
                         json.dumps(r["verdict"], indent=1))
        self.assertTrue(r["verdict"]["pass"])
        self.assertEqual(g["code"], 0, g["out"][-3000:])
        self.assertEqual(r["final_commit"], g["final"])
        self.assertEqual(verify.validate_report(r), [])
        self.assertEqual([w["window"] for w in r["windows"]], [1, 2, 3])
        self.assertEqual(r["files"]["differs"] + r["files"]["missing"] + r["files"]["extra"], [])
        # the step ran with the text it had then, wrote the same files, and nothing was taken from a commit
        self.assertEqual(r["runs"]["step_text"], {"same": 1})
        self.assertEqual(r["runs"]["exit_code"], {"same": 1})
        made = {x["path"]: x["by"] for w in r["windows"] for x in w["detail"]["exact"]}
        self.assertEqual(made.get("assets/palette.tres"), "run:R0001")
        self.assertEqual(made.get("assets/palette.json"), "run:R0001")
        self.assertTrue(made.get("assets/red.png.import", "").startswith("import:"))
        self.assertTrue(made.get("game/player.gd.uid", "").startswith("import:"))
        self.assertEqual(sorted(d["kind"] for d in r["deviations"]), ["shell_deletes"])
        self.assertEqual([w["content"]["adopted_uids"] for w in r["windows"]], [0, 0, 1])
        self.assertTrue(made.get("game/hero.gd.uid", "").startswith("import:"))
        self.assertEqual(r["structure"]["by_kind"]["scenes"], {"same": 1})
        self.assertIn("mipmaps/generate=true", helpers.read(g["root"] + "/godot-replay/tiny/tiny", "assets/red.png.import"))
        self.assertTrue(r["structure"]["by_kind"]["imported"]["same"] >= 1)

    def test_package(self):
        g = self.games["pass"]
        rs = g["pkg"] + "/ReplayScripts"
        for rel in ("README.md", "godot_replay.py", "runner.py", "ledger.py", "verify.py", "shellfx.py", "patchfx.py",
                    "package.py", "engine/replay_dump.gd", "game.json", "ledger.json", "Verification/report.md",
                    "Verification/report.json", "Verification/windows.jsonl", "Verification/dump-replay/dump.json",
                    "Verification/dump-truth/dump.json"):
            self.assertTrue(os.path.isfile(rs + "/" + rel), rel)
        self.assertTrue(os.listdir(rs + "/Blobs"))
        with open(g["pkg"] + "/verification.json", encoding="utf-8") as f:
            v = json.load(f)
        self.assertEqual((v["complete"], v["final_commit"], v["verdict"]["pass"], v["windows"]), (True, g["final"], True, {"done": 3, "total": 3}))
        with open(rs + "/game.json", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["repo"], "{root}/games/tiny")
        for dp, _, fns in os.walk(rs):   # nothing packaged names the folder the replay ran in
            for fn in fns:
                with open(os.path.join(dp, fn), "rb") as f:
                    self.assertNotIn(g["root"].encode(), f.read(), fn)

    def test_fail_is_reported_and_packaged(self):
        g, r = self.games["fail"], self.report("fail")
        self.assertFalse(r["verdict"]["pass"])
        self.assertEqual(g["code"], 0, g["out"][-3000:])   # a FAIL is packaged like a PASS
        self.assertEqual(verify.validate_report(r), [])
        files, structure = r["verdict"]["criteria"]
        self.assertEqual((files["pass"], files["failures"]), (False, ["assets/palette.tres"]))
        self.assertEqual((structure["pass"], [x[0] for x in structure["failures"]]), (False, ["res://assets/palette.tres"]))
        self.assertEqual([x["path"] for w in r["windows"] for x in w["detail"]["differs"]], ["assets/palette.tres"])
        with open(g["pkg"] + "/ReplayScripts/Verification/report.md", encoding="utf-8") as f:
            md = f.read()
        self.assertIn("## Verdict: FAIL", md)
        self.assertIn("assets/palette.tres", md)


if __name__ == "__main__":
    unittest.main()
