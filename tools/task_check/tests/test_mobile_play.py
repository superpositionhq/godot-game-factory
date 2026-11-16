"""A mobile game's plays in the task check (docs/task-probes.md 1.1): a copy whose game has a Platform.json is played
at the phone's size, its spec saying `size` and `touch`; a copy without one is a desktop game's, played at 960x540."""

import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts the tools folder on the path)

from task_check import godot, tasks


class FakeMachine:
    editor = Path("godot_console.exe")

    def __init__(self):
        self.specs, self.argvs = [], []

    def job(self, label, argv, cwd, timeout, gpu=False):
        argv = [str(a) for a in argv]
        self.argvs.append(argv)
        self.specs.append(json.loads(Path(argv[argv.index("-taskProbe") + 1]).read_text(encoding="utf-8")))
        return godot.Result(0, "", 1.0)


def played(platform=None):
    """(the spec, the argument list) of one play of a copy whose Platform.json holds `platform` (None: no such
    file)."""
    with tempfile.TemporaryDirectory() as tmp:
        if platform is not None:
            (Path(tmp) / "Platform.json").write_text(platform if isinstance(platform, str) else json.dumps(platform))
        machine = FakeMachine()
        godot.Project(tmp, machine, "game start").play(5, 2, 60)
        return machine.specs[0], [a.replace(str(Path(tmp)), "<copy>") for a in machine.argvs[0]]


class MobilePlay(unittest.TestCase):
    def test_a_desktop_games_play_is_launched_as_before(self):
        spec, argv = played()
        self.assertEqual(spec["size"], [960, 540])
        self.assertEqual(sorted(spec), ["every", "format", "fps", "inputs", "out", "player", "queries", "scene", "seconds",
                                        "shots", "size", "sound"])
        self.assertEqual(argv[2:], ["godot_console.exe", "--path", "<copy>", "--log-file",
                                    str(Path("<copy>") / "Logs" / "TaskProbe" / "play.log"), "--fixed-fps", "30",
                                    "--disable-vsync", "--audio-driver", "Dummy", "--", "-taskProbe",
                                    str(Path("<copy>") / "Logs" / "TaskProbe" / "play_spec.json")])

    def test_a_mobile_games_play_is_at_the_phones_size_by_touch(self):
        portrait, launched = played({"platform": "mobile", "orientation": "portrait"})
        self.assertEqual((portrait["size"], portrait["touch"]), ([1080, 1920], True))
        landscape, _ = played({"platform": "mobile", "orientation": "landscape"})
        self.assertEqual(landscape["size"], [1920, 1080])
        desktop, as_always = played()
        self.assertEqual(launched, as_always, "the command line is a desktop play's: the size is the spec's alone, "
                                              "and the renderer the project's own")
        self.assertEqual({k: v for k, v in portrait.items() if k not in ("size", "touch", "out")},
                         {k: v for k, v in desktop.items() if k not in ("size", "out")})

    def test_a_platform_file_that_says_neither_is_never_read_as_desktop(self):
        read = tasks.validator().read_platform
        for bad in ("not json", {"platform": "mobile"}, {"platform": "desktop", "orientation": "portrait"},
                    {"platform": "mobile", "orientation": "sideways"},
                    {"platform": "mobile", "orientation": "portrait", "x": 1}, ["mobile", "portrait"]):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "Platform.json").write_text(bad if isinstance(bad, str) else json.dumps(bad))
                with self.assertRaises(ValueError, msg=str(bad)):
                    read(tmp)
            with self.assertRaises(ValueError, msg=str(bad)):
                played(bad)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read(tmp))
            (Path(tmp) / "Platform.json").write_text('{"platform": "mobile", "orientation": "landscape"}')
            self.assertEqual(read(tmp), "landscape")
            self.assertEqual(godot.Project(tmp, FakeMachine(), "t").mobile(), "landscape")


if __name__ == "__main__":
    unittest.main()
