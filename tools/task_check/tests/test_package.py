"""The package check: the game's release export made from its own "Windows Desktop" preset with the probe in it, the
game's export_presets.cfg put back byte for byte, the exported player played through the probe, and a machine
without the release export template failing the check, never passing it. Fake Godot only."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakeProject, measuring, probe, side, task_with
from test_check import FakeMachine, after

from task_check import check, godot, package, seeds, verdict

# the factory's desktop template's preset (templates/godot-game/export_presets.cfg), shortened
PRESETS = """[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter="Docs/*, Dataset/*, addons/task_probe/*, *.md, Platform.json"
export_path="Build/Windows/Yard.exe"
script_export_mode=2

[preset.0.options]

binary_format/embed_pck=true
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
application/modify_resources=true
"""
VERSION = godot.ggfroot.engine()["templates"]
PLATFORM, TEMPLATE, PLAYER = package.target()


def editor_in(tmp, templates=True):
    """A self-contained editor in `tmp` (its `._sc_` beside it), with the release export template or without it."""
    folder = Path(tmp) / "godot"
    folder.mkdir()
    (folder / "._sc_").write_bytes(b"")
    if templates:
        found = folder / "editor_data" / "export_templates" / VERSION
        found.mkdir(parents=True)
        (found / TEMPLATE).write_bytes(b"template")
    return folder / "Godot_console.exe"


def copy_in(tmp, presets=PRESETS.encode("utf-8"), platform=None):
    """A scratch copy with the probe addon in it, and the game's presets (None: none) and Platform.json."""
    copy = Path(tmp) / "copy"
    (copy / seeds.PROBE / "queries").mkdir(parents=True)
    (copy / seeds.PROBE / "task_probe.gd").write_text("extends Node\n", encoding="utf-8")
    (copy / seeds.PROBE / "queries" / "objects.gd").write_text("extends RefCounted\n", encoding="utf-8")
    if presets is not None:
        (copy / package.PRESETS_FILE).write_bytes(presets)
    if platform:
        (copy / "Platform.json").write_text(json.dumps({"platform": "mobile", "orientation": platform}),
                                            encoding="utf-8")
    return copy


def exporting(log="", code=0, leaves=True, seen=None):
    """A FakeMachine whose export keeps the presets it read in `seen`, leaves the player and writes its log, and whose
    play writes a probe that ran to its time."""

    def answer(argv, cwd):
        if "--export-release" in argv:
            if seen is not None:
                seen.append((Path(cwd) / package.PRESETS_FILE).read_text(encoding="utf-8"))
            if leaves:
                Path(argv[-1]).write_bytes(b"player")
            Path(after(argv, "--log-file")).write_text(log, encoding="utf-8")
            machine.code = code
            return ""
        machine.code = 0
        spec = json.loads(Path(after(argv, "-taskProbe")).read_text(encoding="utf-8"))
        (Path(spec["out"]) / "probe.json").write_text(json.dumps({"format": "godot-probe/1", "ended": "time"}),
                                                      encoding="utf-8")
        return ""

    machine = FakeMachine(answer=answer)
    return machine


class Derive(unittest.TestCase):
    def test_the_release_preset_is_derived_with_the_probe_in_it_and_the_games_presets_kept(self):
        derived = package.derive(PRESETS, seeds.PROBE, ["task_probe.gd", "queries/objects.gd"], windows=True)
        self.assertTrue(derived.startswith(PRESETS.rstrip("\n")), "the game's own presets as they were")
        added = derived[len(PRESETS.rstrip("\n")):]
        for line in ("[preset.1]", f'name="{package.PRESET}"', 'platform="Windows Desktop"', "runnable=false",
                     'export_filter="all_resources"', "script_export_mode=2", "dedicated_server=false",
                     f'include_filter="{seeds.PROBE}/*"', 'exclude_filter="Docs/*, Dataset/*, *.md, Platform.json"',
                     "encrypt_pck=false", "[preset.1.options]", "texture_format/s3tc_bptc=true",
                     "binary_format/embed_pck=true", 'binary_format/architecture="x86_64"',
                     "application/modify_resources=false", "codesign/enable=false"):
            self.assertIn(line, added.splitlines(), line)
        linux = package.derive(PRESETS, seeds.PROBE, ["task_probe.gd"], windows=False)
        self.assertIn('platform="Linux"', linux)
        self.assertNotIn("codesign/enable", linux[len(PRESETS.rstrip("\n")):])

    def test_only_the_exclude_patterns_that_would_leave_a_probe_file_out_are_dropped(self):
        text = PRESETS.replace('exclude_filter="Docs/*, Dataset/*, addons/task_probe/*, *.md, Platform.json"',
                               'exclude_filter="addons/*, *.gd, Docs/*"').replace('include_filter=""',
                                                                                  'include_filter="data/*.json"')
        derived = package.derive(text, seeds.PROBE, ["task_probe.gd"], windows=True)
        self.assertIn(f'include_filter="data/*.json, {seeds.PROBE}/*"', derived)
        self.assertIn('exclude_filter="Docs/*"', derived)

    def test_a_game_with_no_release_preset_has_nothing_to_export(self):
        with self.assertRaisesRegex(package.NoRelease, "no export_presets.cfg"):
            package.derive(None, seeds.PROBE, [])
        with self.assertRaisesRegex(package.NoRelease, 'no preset named "Windows Desktop"'):
            package.derive(PRESETS.replace("Windows Desktop", "Web"), seeds.PROBE, [])


class Templates(unittest.TestCase):
    def test_the_templates_are_found_where_the_engine_reads_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            editor = editor_in(tmp)
            self.assertEqual(package.templates(editor, VERSION), editor.parent / "editor_data" / "export_templates"
                             / VERSION, "beside a self-contained editor")
            self.assertIsNone(package.missing_template(editor, VERSION))
            loose = Path(tmp) / "loose" / "godot.exe"
            self.assertEqual(package.templates(loose, VERSION, windows=True, env={"APPDATA": "/A"}),
                             Path("/A") / "Godot" / "export_templates" / VERSION)
            self.assertEqual(package.templates(loose, VERSION, windows=False, env={"XDG_DATA_HOME": "/X"}),
                             Path("/X") / "godot" / "export_templates" / VERSION)

    def test_a_machine_without_the_release_template_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            why = package.missing_template(editor_in(tmp, templates=False), VERSION)
            self.assertIn(f"no {VERSION} release export template ({TEMPLATE}", why)
            self.assertIn("the check fails", why)


class Export(unittest.TestCase):
    def test_the_export_makes_the_player_from_the_derived_preset_and_puts_the_presets_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = ("﻿" + PRESETS.replace("\n", "\r\n")).encode("utf-8")  # a BOM and CRLF, put back as they were
            copy, seen = copy_in(tmp, original), []
            machine = exporting(seen=seen)
            machine.editor = editor_in(tmp)
            project = godot.Project(copy, machine, "t")
            found = project.package(600)
            self.assertEqual((found.exit_code, found.playable, found.why), (0, True, None))
            self.assertEqual((copy / package.PRESETS_FILE).read_bytes(), original, "the game's presets, byte for byte")
            (job,) = machine.jobs
            argv = job["argv"]
            self.assertEqual(argv[:4], [str(machine.editor), "--headless", "--path", str(copy)])
            self.assertEqual(argv[-3:], ["--export-release", package.PRESET,
                                         str(copy / godot.LOGS / "package" / PLAYER)])
            self.assertEqual(Path(after(argv, "--log-file")), copy / godot.LOGS / "package.log")
            self.assertIn(f'name="{package.PRESET}"', seen[0])
            self.assertIn(f'include_filter="{seeds.PROBE}/*"', seen[0])
            self.assertEqual(project.player, copy / godot.LOGS / "package" / PLAYER)

    def test_an_export_that_failed_or_left_no_player_is_no_package_and_the_presets_are_put_back(self):
        for machine, why in ((exporting(code=1, leaves=False), "exit 1"),
                             (exporting(log='ERROR: Project export for preset "TaskProbe package" failed.\n'), "logged"),
                             (exporting(leaves=False), "no player")):
            with tempfile.TemporaryDirectory() as tmp:
                copy = copy_in(tmp)
                machine.editor = editor_in(tmp)
                project = godot.Project(copy, machine, "t")
                found = project.package(600)
                self.assertFalse(found.playable, why)
                self.assertEqual(found.exit_code, 0 if why == "no player" else 1, why)
                self.assertEqual((copy / package.PRESETS_FILE).read_bytes(), PRESETS.encode(), why)
                with self.assertRaisesRegex(ValueError, "no packaged player"):
                    project.play(20, 1, 60, packaged=True)

    def test_the_presets_are_put_back_when_the_export_itself_breaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = copy_in(tmp)
            machine = FakeMachine(answer=lambda argv, cwd: (_ for _ in ()).throw(KeyboardInterrupt()))
            machine.editor = editor_in(tmp)
            with self.assertRaises(KeyboardInterrupt):
                godot.Project(copy, machine, "t").package(600)
            self.assertEqual((copy / package.PRESETS_FILE).read_bytes(), PRESETS.encode())

    def test_nothing_is_exported_without_a_release_preset_or_a_release_template(self):
        for presets, templates, said in ((None, True, "no export_presets.cfg"),
                                         (PRESETS.replace("Windows Desktop", "Web").encode(), True,
                                          'no preset named "Windows Desktop"'),
                                         (PRESETS.encode(), False, "release export template")):
            with tempfile.TemporaryDirectory() as tmp:
                copy = copy_in(tmp, presets)
                machine = exporting()
                machine.editor = editor_in(tmp, templates)
                found = godot.Project(copy, machine, "t").package(600)
                self.assertEqual((found.exit_code, found.playable), (1, False), said)
                self.assertIn(said, found.why)
                self.assertEqual(machine.jobs, [], "nothing run")
                if presets is not None:
                    self.assertEqual((copy / package.PRESETS_FILE).read_bytes(), presets, said)

    def test_the_player_is_played_through_the_probe_and_a_mobile_games_at_the_phones_size(self):
        for held, size in ((None, [960, 540]), ("portrait", [1080, 1920]), ("landscape", [1920, 1080])):
            with tempfile.TemporaryDirectory() as tmp:
                copy = copy_in(tmp, platform=held)
                machine = exporting()
                machine.editor = editor_in(tmp)
                project = godot.Project(copy, machine, "t")
                with mock.patch.object(seeds, "forget_saves", lambda folder: None):
                    project.package(600)
                    found = project.play(20, 1, 60, packaged=True)
                argv = machine.jobs[-1]["argv"]
                self.assertEqual(argv[2:4], [str(copy / godot.LOGS / "package" / PLAYER), "--log-file"])
                self.assertNotIn("--path", argv)
                self.assertNotIn(str(machine.editor), argv)
                spec = json.loads((copy / godot.LOGS / godot.SPEC).read_text(encoding="utf-8"))
                self.assertEqual((spec["size"], spec.get("touch", False)), (size, held is not None), held)
                self.assertEqual(found.probe["ended"], "time")


def grade_package(project, task):
    return check.Grade(task, "reference", None, side("reference", project, task), {}).check(
        {"kind": "package", "name": "packs"})


PACKAGE_TASK = task_with(probe(), {"kind": "package", "name": "packs", "weight": 0})


class Checked(unittest.TestCase):
    def test_an_export_that_boots_for_its_time_passes(self):
        project = FakeProject(measuring(0))
        self.assertEqual(grade_package(project, PACKAGE_TASK), (True, "packaged and ran 20 s"))
        (played,) = project.plays
        self.assertEqual((played["seconds"], played["shots"], played.get("packaged")),
                         (check.PACKAGED_SECONDS, 1, True))

    def test_every_other_outcome_fails_saying_why(self):
        for packaged, answer, detail in (
                (godot.Packaged(1, "", 1.0), measuring(0), "packaging failed (exit 1)"),
                (godot.Packaged(0, "", 1.0), measuring(0), "packaging failed (exit 0): the export left no player"),
                (godot.Packaged(None, "", 600.0, timed_out=True), measuring(0), "packaging timed out"),
                (godot.Packaged(1, "", 0.0, why="no release template here"), measuring(0),
                 "packaging failed: no release template here"),
                (None, measuring(0, crash=True), "packaged, but the packaged game didn't run cleanly"),
                (None, measuring(0, seconds=5), None)):
            project = FakeProject(answer, packaged=packaged)
            if detail is None:  # a play that ended early
                project.answer = lambda s, shots, q: ({"format": "godot-probe/1", "ended": "shutdown"}, "")
                detail = "packaged, but the packaged game didn't run cleanly"
            self.assertEqual(grade_package(project, PACKAGE_TASK), (False, detail))
            self.assertEqual(project.plays != [], packaged is None, detail)

    def test_an_unbuilt_game_is_not_packaged_and_the_start_is_not_asked(self):
        self.assertEqual(grade_package(FakeProject(build_exit=1), PACKAGE_TASK)[0], False)
        start = check.Grade(PACKAGE_TASK, "start", side("start", FakeProject(), PACKAGE_TASK), None, {})
        self.assertEqual(start.check({"kind": "package", "name": "packs"}),
                         (True, "not asked: the start is checked on its probes"))

    def test_a_required_package_check_decides_as_any_required_check(self):
        task = task_with(probe(), {"kind": "package", "name": "packs", "weight": 0})
        start = check.Grade(task, "start", side("start", FakeProject(measuring(-5)), task), None, {}).run()
        for packaged, valid in ((None, True), (godot.Packaged(1, "", 0.0, why="no release template here"), False)):
            reference = side("reference", FakeProject(measuring(0), packaged=packaged), task)
            found = check.Grade(task, "reference", side("start", FakeProject(measuring(-5)), task), reference,
                                {}).run()
            ok, why, _ = verdict.verdict(task, found, start)
            self.assertEqual(ok, valid, why)
            if not valid:
                self.assertEqual(why, ["reference fails packs: packaging failed: no release template here"])


if __name__ == "__main__":
    unittest.main()
