"""Probes with no Godot: the measures' defaults, the probe's queries and every reducer."""

import json
import tempfile
import types
import unittest
from pathlib import Path

from helpers import NO_FIX, SEED, FakeProject, first_check, measure_of, probe, side, task_with

from task_check import check, godot, probes, tasks

WALLS = {"component": "CastlePiece", "tag": "Wall"}
TRACK = [[0.0, 0, 1.0, 0], [0.5, 0.3, 1.0, 0.4], [1.0, 0.6, 0.9, 0.8], [1.5, 0.6, -5.0, 0.8]]  # [t, x, y (up), z]


def m(**data):
    return measure_of(data)


def sampled(values, key="value"):
    return [{"t": i * 0.5, key: v} for i, v in enumerate(values)]


def objects_play(measure, rows):
    qid = probes.query_id(probes.needs(measure)[0])
    return {"measures": {qid: sampled(rows, "rows")}}


class Tasks(unittest.TestCase):
    def test_the_measures_defaults(self):
        found = m(probe="objects", select={"component": "Wall"}, field="y")
        self.assertEqual((found["of"], found["agg"]), ("count", None))
        self.assertEqual(probes.default_agg(found), "last")
        self.assertEqual(probes.default_agg(m(probe="spawns", component="Projectile", field="spawned")), "sum")
        self.assertEqual(m(probe="player", field="dist", to={"player": True})["to"]["offset"], [0, 0, 0])

    def test_a_task_play_teleport_turns_the_player_even_without_a_yaw(self):
        play = tasks.play({"name": "spot", "seconds": 8, "inputs": [{"t": 0.2, "teleport": [1, 2, 3]},
                                                                     {"t": 1, "key": "<Keyboard>/w", "press": True}]})
        self.assertEqual(play["inputs"], [{"t": 0.2, "teleport": [1.0, 2.0, 3.0], "yaw": 0.0},
                                          {"t": 1.0, "key": "<Keyboard>/w", "press": True}])
        self.assertEqual(play["every"], None)
        self.assertNotIn("scene", play, "a play without a scene opens the task's")
        self.assertNotIn("args", play, "a play without args passes the task's")

    def test_a_task_plays_scene_and_args_take_the_tasks_place_only_where_it_has_them(self):
        task = {"play_scene": "res://scenes/Town.tscn", "play_args": ["-scenario", "1"]}
        self.assertEqual(tasks.place(task, "look"), ("res://scenes/Town.tscn", ["-scenario", "1"]))
        self.assertEqual(tasks.place(task, tasks.play({"name": "a", "seconds": 5})),
                         ("res://scenes/Town.tscn", ["-scenario", "1"]))
        own = tasks.play({"name": "a", "seconds": 5, "scene": "res://scenes/Arena.tscn", "args": []})
        self.assertEqual(tasks.place(task, own), ("res://scenes/Arena.tscn", []), "an empty args is the play's own")
        first = tasks.play({"name": "a", "seconds": 5, "scene": None})
        self.assertEqual(tasks.place(task, first), (None, ["-scenario", "1"]), "scene null: the first build scene")
        self.assertEqual(tasks.place({}, "drive"), (None, []))

    def test_the_tasks_player_select_is_filled_in(self):
        self.assertIsNone(tasks.player({}))
        self.assertEqual(tasks.player({"player": {"tag": "Hero", "near": {"point": {"xyz": [0, 0, 0]}, "radius": 5}}}),
                         {"tag": "Hero", "near": {"point": {"xyz": [0.0, 0.0, 0.0]}, "radius": 5.0}})
        task_with(probe(), player={"name": "Hero*"})
        with self.assertRaises(ValueError):
            task_with(probe(), player={"near": {"point": {"player": True}, "radius": 1, "y_relative": True}})

    def test_the_checks_defaults_and_their_kinds(self):
        task = task_with(probe(), probe("b", required=False, expect={"op": ">=", "calibrate": 0.5}))
        checks = [c for _, c in tasks.checks(task)]
        self.assertEqual([(c["required"], c["weight"], c["needs"]) for c in checks], [(True, 1, []), (False, 1, [])])
        self.assertEqual([tasks.relative(c) for c in checks], [None, "calibrate"])
        self.assertEqual(tasks.gating(task), {"hero_on_ground"})

    def test_the_task_rules_beyond_the_schema_are_refused(self):
        for checks, seed, said in [
            ([probe("a", play={"name": "fire", "seconds": 10}), probe("b", play={"name": "fire", "seconds": 12})],
             SEED, "task play fire differs"),
            ([probe(expect={"op": "==", "calibrate": 0.5})], SEED, "== and != take a literal value"),
            ([probe(expect={"op": ">=", "calibrate": 0.5})], NO_FIX, "calibrates against a reference"),
        ]:
            with self.assertRaisesRegex(ValueError, said):
                task_with(*checks, seed=seed)
        for arg in ("-taskProbe", "-taskprobeseconds=99", "--headless", "--path", "--log-file", "--fixed-fps",
                    "--disable-vsync", "--audio-driver", "--quit", "--quit-after", "--script", "--import", "--editor",
                    "--main-pack", "--fullscreen", "-shots", "-shotDir"):
            with self.assertRaisesRegex(ValueError, "can't set", msg=arg):
                task_with(probe(play={"name": "fire", "seconds": 10, "args": [arg]}))
        with self.assertRaisesRegex(ValueError, "play_args can't set"):
            task_with(probe(), play_args=["--headless"])
        task_with(probe(play={"name": "fire", "seconds": 10, "args": ["-autoPlay", "-scenario", "2"]}),
                  play_scene="res://scenes/Town.tscn", play_args=["-scenario", "1"])
        task_with(probe("a", play={"name": "fire", "seconds": 10}), probe("b", play={"name": "fire", "seconds": 10}))
        task_with(probe(expect={"op": ">=", "start_times": 1.3}), seed=NO_FIX)

    def test_a_judge_check_names_its_own_plays_under_a_task_plays_rules(self):
        judge = {"kind": "judge", "name": "menu_reads", "question": "Does the upgrade menu read clearly?",
                 "required": False, "rubric": [{"key": "menu", "criterion": "The menu is on screen."}]}
        menu = {"name": "open_menu", "seconds": 6, "inputs": [{"t": 1.0, "key": "<Keyboard>/c", "press": True}]}
        plain = task_with(probe(), judge)
        self.assertNotIn("plays", plain["milestones"][0]["checks"][1], "a judge with no plays is as it was")
        task = task_with(probe(play=menu), {**judge, "plays": [menu, {"name": "second_level", "seconds": 8,
                                                                      "scene": "res://scenes/Two.tscn",
                                                                      "args": ["-scenario", "2"]}]})
        self.assertEqual(sorted(probes.task_plays(task)), ["open_menu"], "the checker plays what its probes name")
        self.assertEqual(first_check(task_with({**judge, "plays": [menu]}))["plays"], [menu])
        task_with({**judge, "plays": [{**menu, "name": f"play_{i}"} for i in range(4)]})
        for checks, said in [
            ([{**judge, "plays": [{**menu, "name": f"play_{i}"} for i in range(5)]}], "more than 4 item"),
            ([{**judge, "plays": [menu, menu]}], "names a play twice"),
            ([probe(play=menu), {**judge, "plays": [{**menu, "seconds": 9}]}], "task play open_menu differs"),
            ([{**judge, "plays": [{**menu, "seconds": 9}]}, probe(play=menu)], "task play open_menu differs"),
            ([{**judge, "plays": [menu]}, {**judge, "name": "again", "plays": [{**menu, "inputs": []}]}],
             "task play open_menu differs"),
            ([{**judge, "plays": [{**menu, "name": "look"}]}], "can't be named look"),
            ([{**judge, "plays": [{**menu, "inputs": [{"t": 6, "key": "<Keyboard>/c", "press": True}]}]}],
             "at or after its end"),
            ([{**judge, "plays": [{**menu, "args": ["-taskProbeSeconds=99"]}]}], "can't set -taskProbeSeconds"),
            ([{**judge, "plays": [{**menu, "scene": "res://scenes/../Two.tscn"}]}], 'has a "." or ".." part'),
            ([{**judge, "plays": [{**menu, "inputs": [{"t": 1, "wait": 200}, {"t": 2, "wait": 200}]}]}], "waits 400 s"),
            ([{**judge, "plays": [{**menu, "inputs": [{"t": 1, "teleport_to": {
                "tag": "Ore", "near": {"point": {"player": True}, "radius": 5, "y_min": 5, "y_max": 1}}}]}]}],
             "y_min < y_max"),
            ([{**judge, "plays": ["look"]}], "expected object"),
            ([{**judge, "plays": [{**menu, "shots": 5}]}], "unexpected key"),
        ]:
            with self.assertRaisesRegex(ValueError, said):
                task_with(*checks)

    def test_a_judge_check_with_plays_may_ask_a_run_of_screenshots(self):
        judge = {"kind": "judge", "name": "door_eases", "question": "Does the door ease open?", "required": False,
                 "rubric": [{"key": "eases", "criterion": "The door slows into its open position."}]}
        door = {"name": "open_door", "seconds": 5, "inputs": [{"t": 1.0, "key": "<Keyboard>/e", "press": True}]}
        two = [door, {**door, "name": "close_door"}]
        self.assertEqual(first_check(task_with({**judge, "plays": [door], "shots": 20}))["shots"], 20)
        task_with({**judge, "plays": two, "shots": 10})
        task_with({**judge, "plays": [{**door, "name": f"play_{i}"} for i in range(4)], "shots": 5})
        task_with({**judge, "plays": [door], "shots": 2})
        task_with({**judge, "shots": 5})
        # a probe measuring the same play every 0.1 s for its largest jump, beside the judge
        task_with(probe(play={**door, "every": 0.1}, measure={"probe": "player", "field": "y", "agg": "step"},
                        expect={"op": "<=", "value": 0.3}), {**judge, "plays": [{**door, "every": 0.1}], "shots": 20})
        for check, said in [
            ({**judge, "shots": 8}, "sets shots but names no play of its own"),
            ({**judge, "plays": two, "shots": 11}, "asks 2 plays of 11 screenshots"),
            ({**judge, "plays": [{**door, "name": f"play_{i}"} for i in range(4)], "shots": 6}, "more than a judge's 20"),
            ({**judge, "plays": [door], "shots": 1}, "1 < 2"),
            ({**judge, "plays": [door], "shots": 21}, "21 > 20"),
            ({**judge, "plays": [door], "shots": 7.5}, "expected integer"),
        ]:
            with self.assertRaisesRegex(ValueError, said):
                task_with(check)
        with self.assertRaisesRegex(ValueError, "not one of"):
            task_with(probe(measure={"probe": "player", "field": "y", "agg": "jolt"}))

    def test_a_screen_measure_takes_a_threshold_from_the_start_never_a_literal(self):
        screen = {"probe": "screen", "rect": [0.25, 0.25, 0.75, 0.75], "field": "luminance", "window": [10, 20]}
        with self.assertRaisesRegex(ValueError, "never a literal value"):
            task_with(probe(measure=screen, expect={"op": ">=", "value": 0.1}))
        task_with(probe(measure=screen, expect={"op": ">=", "calibrate": 0.5}))
        task_with(probe(measure=screen, expect={"op": ">=", "start_times": 1.3}), seed=NO_FIX)
        for bad in ({**screen, "rect": [0.5, 0, 1.2, 1]}, {**screen, "field": "brightness"}):
            with self.assertRaises(ValueError):
                task_with(probe(measure=bad, expect={"op": ">=", "calibrate": 0.5}))

class Queries(unittest.TestCase):
    def test_queries_are_merged_per_play_and_selection_under_stable_ids(self):
        task = task_with(
            probe("a", measure={"probe": "objects", "select": WALLS, "field": "y"}),
            probe("b", measure={"probe": "objects", "select": WALLS, "field": "prop:CameraRig.distance"}),
            probe("c", measure={"probe": "objects", "select": WALLS, "field": "count"}),
            probe("d", measure={"probe": "camera", "field": "occluded"}),
            probe("e", measure={"probe": "camera", "field": "player_on_screen"}),
            probe("f", measure={"probe": "camera", "field": "pitch"}),
            probe("g", play="drive", measure={"probe": "render", "field": "triangles", "agg": "max"},
                  expect={"op": "<=", "value": 500000}),
            probe("i", play="drive", measure={"probe": "player", "field": "dist", "to": {"object": {"name": "Kiln*"}}}),
            probe("j", play={"name": "fire", "seconds": 10}, measure={"probe": "spawns", "component": "Projectile",
                                                                        "field": "destroyed"}),
            probe("k", play={"name": "fire", "seconds": 10}, measure={"probe": "log", "pattern": "SCRIPT ERROR"}))
        plan = probes.plan(task)
        self.assertEqual(set(plan), {"look", "drive", "fire"})
        look = {q["kind"]: q for q in plan["look"]}
        self.assertEqual(len(plan["look"]), 2, "one objects query for the walls, one camera query")
        self.assertEqual(look["objects"]["fields"], ["prop:CameraRig.distance", "y"])
        self.assertEqual(look["objects"]["select"], {"component": "CastlePiece", "tag": "Wall"})
        self.assertEqual(look["camera"]["fields"], ["occluded", "player_on_screen"])
        drive = {q["kind"]: q for q in plan["drive"]}
        self.assertEqual(drive["render"], {"id": drive["render"]["id"], "kind": "render", "fields": ["triangles"]})
        self.assertEqual(drive["objects"], {"id": drive["objects"]["id"], "kind": "objects",
                                            "select": {"name": "Kiln*"}, "fields": ["x", "y", "z"]})
        self.assertEqual(plan["fire"], [{"id": plan["fire"][0]["id"], "kind": "spawns", "component": "Projectile"}])
        alone = probes.plan(task_with(probe("z", measure={"probe": "objects", "select": WALLS, "field": "hidden"})))
        self.assertEqual(alone["look"][0]["id"], look["objects"]["id"], "an id names its selection")
        self.assertEqual([q["id"] for q in plan["look"]], sorted(q["id"] for q in plan["look"]))
        self.assertEqual(probes.query_file(plan["look"]),
                         {"format": "game-probe-queries/1", "every": 0.5, "queries": plan["look"]})
        self.assertIsNone(probes.query_file([]))
        self.assertEqual(probes.plan(task_with(probe())), {"look": []}, "the track needs no query")

    def test_a_query_id_is_the_hash_of_the_query_without_its_fields(self):
        query = {"kind": "objects", "select": {"tag": "Wall"}, "fields": ["y"]}
        import hashlib
        want = "q" + hashlib.sha256(json.dumps({"kind": "objects", "select": {"tag": "Wall"}},
                                               sort_keys=True).encode()).hexdigest()[:10]
        self.assertEqual(probes.query_id(query), want)
        self.assertEqual(probes.query_id({**query, "fields": ["x", "count"]}), want)
        self.assertEqual(want, "q64b05254ef", "the same in every run and every Python")

    def test_component_types_and_names_reach_the_queries(self):
        found = probes.plan(task_with(probe(measure={"probe": "components", "select": {"component": "GPUParticles3D",
                                                                                       "name": "Rain*"},
                                                     "field": "count"})))
        self.assertTrue(any(q.get("select", {}).get("name") == "Rain*" for qs in found.values() for q in qs))


class Reducers(unittest.TestCase):
    def test_the_players_fields_come_from_the_track(self):
        play = {"track": TRACK}
        self.assertEqual(probes.reduce(m(probe="player", field="y"), play), -5, "last by default")
        self.assertEqual(probes.reduce(m(probe="player", field="y", agg="min", window=[0, 1]), play), 0.9)
        self.assertEqual(probes.reduce(m(probe="player", field="x", at=[0.5, 1.4]), play), 0.6)
        self.assertAlmostEqual(probes.reduce(m(probe="player", field="speed", agg="first"), play), 1.0)
        self.assertAlmostEqual(probes.reduce(m(probe="player", field="moved", at="end"), play),
                               (0.6 ** 2 + 6.0 ** 2 + 0.8 ** 2) ** 0.5)
        self.assertEqual(probes.reduce(m(probe="player", field="dist", to={"xyz": [0, 1, 0]}, agg="first"), play), 0)
        self.assertIsNone(probes.reduce(m(probe="player", field="y", window=[5, 9]), play), "no sample in the window")
        self.assertIsNone(probes.reduce(m(probe="player", field="y"), None), "no probe file")

    def test_a_players_distance_to_an_object_reads_the_objects_query(self):
        measure = m(probe="player", field="dist", to={"object": {"name": "Kiln*"}, "offset": [0, 1, 0]}, agg="min")
        (query,) = probes.plan(task_with(probe(measure={"probe": "player", "field": "dist", "agg": "min",
                                                        "to": {"object": {"name": "Kiln*"},
                                                               "offset": [0, 1, 0]}})))["look"]
        rows = [[{"name": "Kiln_2", "x": 0.6, "y": 0, "z": 0.8}]] * 4
        play = {"track": TRACK, "measures": {query["id"]: sampled(rows, "rows")}}
        self.assertAlmostEqual(probes.reduce(measure, play), 0.1)
        play["measures"][query["id"]] = sampled([[]] * 4, "rows")
        self.assertIsNone(probes.reduce(measure, play), "no kiln, no distance")

    def test_the_cameras_fields_come_from_its_rows_and_its_query(self):
        camera = [[t, -7, 4, 0, 12.0, 5.0, 60.0] for t in (0.0, 0.5)]  # [t, x, y, z, pitch, yaw, fov]
        play = {"track": [[0.0, 0, 1, 0], [0.5, 0, 1, 0]], "camera": camera}
        self.assertAlmostEqual(probes.reduce(m(probe="camera", field="distance"), play), (7 ** 2 + 3 ** 2) ** 0.5)
        self.assertEqual(probes.reduce(m(probe="camera", field="height"), play), 3, "camera y minus player y")
        self.assertEqual(probes.reduce(m(probe="camera", field="pitch"), play), 12)
        self.assertEqual(probes.reduce(m(probe="camera", field="fov"), play), 60)
        occluded = m(probe="camera", field="occluded", agg="count")
        qid = probes.query_id(probes.needs(occluded)[0])
        play["measures"] = {qid: sampled([{"occluded": True, "player_on_screen": 1}, {"occluded": False}])}
        self.assertEqual(probes.reduce(occluded, play), 1)
        self.assertEqual(probes.reduce(m(probe="camera", field="player_on_screen", agg="all"), play), 1)

    def test_objects_combine_by_of_and_samples_by_agg(self):
        rows = [[{"name": "A", "y": 0}, {"name": "B", "y": 120.0}, {"name": "C", "y": None}],
                [{"name": "A", "y": 50}, {"name": "B", "y": 130.0}]]
        expected = {"count": [1, 2], "any": [1, 1], "all": [0, 1], "min": [0, 50], "max": [120, 130],
                    "mean": [60, 90], "sum": [120, 180], "first": [0, 50]}
        for of, values in expected.items():
            for agg, want in (("first", values[0]), ("last", values[1]), ("delta", values[1] - values[0]),
                              ("sum", sum(values)), ("max", max(values))):
                measure = m(probe="objects", select={"tag": "T"}, field="y", of=of, agg=agg)
                self.assertAlmostEqual(probes.reduce(measure, objects_play(measure, rows)), want, msg=(of, agg))
        count = m(probe="objects", select={"tag": "T"}, field="count", agg="mean")
        self.assertEqual(probes.reduce(count, objects_play(count, rows)), 2.5)
        empty = m(probe="objects", select={"tag": "T"}, field="y", of="min")
        self.assertIsNone(probes.reduce(empty, objects_play(empty, [[], []])))
        named = m(probe="objects", select={"tag": "T"}, field="prop:MeshFilter.sharedMesh.name", match="SM_Tower",
                  of="all")
        self.assertEqual(probes.reduce(named, objects_play(named, [[{"prop:MeshFilter.sharedMesh.name": "SM_Tower"},
                                                                    {"prop:MeshFilter.sharedMesh.name": "SM_Tower_B"}]])),
                         1)
        self.assertEqual(probes.reduce(named, objects_play(named, [[{"prop:MeshFilter.sharedMesh.name": "SM_Hut"}]])),
                         0)

    def test_of_defaults_to_count(self):
        """A probe that reads a field without `of` counts the rows whose value isn't 0."""
        measure = m(probe="objects", select={"tag": "T"}, field="y")
        self.assertEqual(probes.reduce(measure, objects_play(measure, [[{"y": 1.2}, {"y": 0.0}, {"y": 0.05}]])), 2)

    def test_every_agg_and_of(self):
        values = [0.0, 2.0, None, 5.0, 0.0]
        want = {"min": 0, "max": 5, "mean": 1.75, "first": 0, "last": 0, "delta": 0, "any": 1, "all": 0, "count": 2,
                "sum": 7, "range": 5, "changes": 3, "rises": 2, "falls": 1, "step": 5}
        for agg, value in want.items():
            self.assertEqual(probes.aggregate(values, agg), value, agg)
        self.assertAlmostEqual(probes.aggregate(values, "std"), 2.0463, places=4)
        self.assertIsNone(probes.aggregate([None], "sum"))
        self.assertEqual(probes.aggregate([4.0], "step"), 0, "one sample has no neighbour")
        self.assertEqual(probes.aggregate([0.0, 1.0, 2.0, 3.0], "step"), 1, "an eased move")
        self.assertEqual(probes.aggregate([0.0, 0.0, 3.0, 3.0], "step"), 3, "a snap over the same distance")
        self.assertEqual(probes.aggregate([3.0, 4.0], "all"), 1)
        self.assertEqual({of: probes.combine([3.0, 0.0, None], of) for of in
                          ("count", "any", "all", "min", "max", "mean", "sum", "first")},
                         {"count": 1, "any": 1, "all": 0, "min": 0, "max": 3, "mean": 1.5, "sum": 3, "first": 3})
        self.assertEqual((probes.combine([], "all"), probes.combine([], "count")), (0, 0))
        self.assertIsNone(probes.combine([], "max"))

    def test_widgets_spawns_and_the_log(self):
        ammo = m(probe="widgets", select={"component": "Label", "name": "AmmoText"}, field="text",
                 match=r"^\d+ / \d+$", of="any", agg="all")
        self.assertEqual(probes.reduce(ammo, objects_play(ammo, [[{"name": "AmmoText", "text": "12 / 30"}]] * 3)), 1)
        self.assertEqual(probes.reduce(ammo, objects_play(ammo, [[{"name": "AmmoText", "text": "AMMO"}]])), 0)
        shots = m(probe="spawns", component="Projectile", field="spawned", window=[1, 2])
        qid = probes.query_id(probes.needs(shots)[0])
        play = {"measures": {qid: sampled([{"spawned": n, "destroyed": 0} for n in (0, 1, 1, 4, 6, 6)])}}
        self.assertEqual(probes.reduce(shots, play), 5, "spawned in (0.5, 2] s: 3 + 2")
        self.assertEqual(probes.reduce(m(probe="spawns", component="Projectile", field="spawned"), play), 6)
        log = "SCRIPT ERROR: Invalid access\nGodot Engine v4.7.2\nSCRIPT ERROR: again\n"
        self.assertEqual(probes.reduce(m(probe="log", pattern="SCRIPT ERROR"), None, log), 2)

    def test_a_point_on_the_camera_follows_its_view(self):
        """The engine's own angles: Y is up, 0 and 0 looks along -Z, a positive pitch up, a positive yaw to the left."""
        play = {"camera": [[0.0, 0, 0, 0, 90.0, 0.0, 60.0], [0.5, 0, 0, 0, 0.0, 90.0, 60.0],
                           [1.0, 0, 0, 0, 0.0, 0.0, 60.0], [1.5, 0, 1, 0, 30.0, 0.0, 60.0]],
                "track": [[0.0, 0, 0, 0]]}
        for t, want in ((0.0, [0, 1, 0]), (0.5, [-1, 0, 0]), (1.0, [0, 0, -1]),
                        (1.5, [0, 1 + 0.5, -(3 ** 0.5) / 2])):
            found = probes.point_at(tasks.point({"camera": True, "forward": 1}), t, play)
            for a, b in zip(found, want):
                self.assertAlmostEqual(a, b, msg=t)
        self.assertEqual(probes.point_at(tasks.point({"player": True, "offset": [0, 0.5, 0]}), 0.1, play), [0, 0.5, 0])
        self.assertIsNone(probes.point_at(tasks.point({"player": True}), 3.0, play))

    def test_a_play_that_ended_before_the_window_fails_saying_when_it_ended(self):
        play = {"seconds": 6.0, "track": [[t * 0.5, 0, 1, 0] for t in range(13)]}
        self.assertEqual(probes.measured(m(probe="player", field="y", window=[10, 18]), play),
                         (None, "no samples in the window (the play ended at 6 s)"))
        self.assertEqual(probes.measured(m(probe="player", field="y", at=[15]), {"track": TRACK}),
                         (None, "no samples in the window (the play ended at 1.5 s)"))
        empty = m(probe="objects", select={"tag": "T"}, field="y", of="min")
        self.assertEqual(probes.measured(empty, objects_play(empty, [[]])),
                         (None, "no value in the window (nothing it selects was measured)"))

    def test_a_play_that_ran_without_a_player_or_a_camera_has_samples_with_no_value(self):
        """A sample that found no player is a track row [t], one that found no camera has no camera row: the play
        ran, so its measures have no value there, never "no samples"."""
        nobody = {"seconds": 20.5, "track": [[0.0333], [0.5], [1.0], [20.5]], "camera": []}
        nothing = (None, "no value in the window (nothing it selects was measured)")
        for measure in (m(probe="player", field="moved"), m(probe="player", field="y"),
                        m(probe="player", field="dist", to={"camera": True, "forward": 2}),
                        m(probe="camera", field="pitch"), m(probe="camera", field="height")):
            self.assertEqual(probes.measured(measure, nobody), nothing, measure["field"])
        self.assertEqual(probes.ended({"track": [[0.5], [1.0], [1.5]]}), 1.5, "a sample without a player is a sample")
        gaps = {"track": [[0.0, 0, 1, 0], [0.5], [1.0, 0.6, 1, 0.8]],
                "camera": [[0.0, 0, 3, 0, 10.0, 0.0, 60.0], [1.0, 0, 3, 0, 20.0, 0.0, 60.0]]}
        self.assertIsNone(probes.reduce(m(probe="player", field="x", at=[0.5]), gaps))
        self.assertAlmostEqual(probes.reduce(m(probe="player", field="speed"), gaps), 1.0, msg="over the gap")
        self.assertIsNone(probes.reduce(m(probe="camera", field="pitch", at=[0.5]), gaps))
        self.assertEqual(probes.reduce(m(probe="camera", field="pitch", agg="max"), gaps), 20.0)
        # sampled every 0.2 s, the player of the sample before is within NEAR: it is still not this sample's
        quick = {"track": [[0.0, 0, 0, 0], [0.2], [0.4, 0, 1, 0]],
                 "camera": [[t, 0, 3, 0, 10.0, 0.0, 60.0] for t in (0.0, 0.2, 0.4)]}
        for field, values in (("distance", [3.0, None, 2.0]), ("height", [3.0, None, 2.0])):
            self.assertEqual(probes.series(m(probe="camera", field=field), quick),
                             list(zip((0.0, 0.2, 0.4), values, strict=True)), field)

    def test_a_probe_with_no_value_says_what_the_probe_could_not_read(self):
        """Its own query's error only: one naming the query's kind and id, else one naming its kind alone (the probe
        writes a select's own errors so), never another query's or the play's."""
        measure = m(probe="components", select={"component": "Nowhere"}, field="y", of="max")
        qid = probes.query_id(probes.needs(measure)[0])
        found = {"format": "godot-probe/1", "ended": "time", "seconds": 20.0, "track": [[0.5, 0, 0, 0]], "camera": [],
                 "measures": {qid: [{"t": 0.5, "rows": []}]},
                 "query_errors": ["spawns: no component type Coin", "components: no component type Nowhere"]}
        value, why = probes.measured(measure, found)
        self.assertIsNone(value)
        self.assertEqual(why, "no value in the window (nothing it selects was measured); the probe said: components: "
                              "no component type Nowhere")
        found["query_errors"] = ["components qffffffffff: not this one", "components: no component type Nowhere",
                                 f"components {qid} (frame): this one"]
        self.assertTrue(probes.measured(measure, found)[1].endswith(f"; the probe said: components {qid} (frame): "
                                                                    "this one"))
        found["query_errors"] = ["spawns: no component type Coin", "components qffffffffff: not this one",
                                 "the frame couldn't be read: no"]
        self.assertEqual(probes.measured(measure, found), (None, "no value in the window (nothing it selects was "
                                                                 "measured)"), "another query's error is not quoted")

class FairReadings(unittest.TestCase):
    def test_a_count_reads_every_match_past_the_rows_cap(self):
        """The probe keeps 200 rows a sample; a count of 389 is 389, not 200."""
        crates = m(probe="objects", select={"component": "Crate"}, field="count")
        qid = probes.query_id(probes.needs(crates)[0])
        rows = [{"name": f"Crate{i}", "count": 1} for i in range(200)]
        self.assertEqual(probes.reduce(crates, {"measures": {qid: [{"t": 0.0, "rows": rows, "total": 389}]}}), 389)
        self.assertEqual(probes.reduce(crates, {"measures": {qid: [{"t": 0.0, "rows": rows[:12]}]}}), 12)

    def test_of_reads_the_probes_summary_of_every_match_past_the_rows_cap(self):
        rows = [{"y": 1.0, "hidden": 0} for _ in range(200)]
        full = {"y": {"n": 389, "nonzero": 388, "sum": 400.0, "min": 0.0, "max": 9.0},
                "hidden": {"n": 389, "nonzero": 189, "sum": 189.0, "min": 0.0, "max": 1.0}}
        sample = {"t": 0.0, "rows": rows, "total": 389, "full": full}

        def read(**kw):
            measure = m(probe="objects", select={"component": "Crate"}, **kw)
            return probes.reduce(measure, {"measures": {probes.query_id(probes.needs(measure)[0]): [sample]}})

        self.assertEqual(read(field="y", of="max"), 9.0)
        self.assertEqual(read(field="y", of="min"), 0.0)
        self.assertEqual(read(field="y", of="sum"), 400.0)
        self.assertAlmostEqual(read(field="y", of="mean"), 400.0 / 389)
        self.assertEqual(read(field="hidden"), 189, "of defaults to count: the non-zero values of every match")
        self.assertEqual(read(field="hidden", of="any"), 1.0)
        self.assertEqual(read(field="y", of="all"), 0.0, "one crate sits at 0")
        self.assertEqual(read(field="y", of="first"), 1.0, "first is the first row")
        self.assertEqual(read(field="yaw", of="max"), None, "a field the summary lacks reads the rows (none here)")

    def test_values_read_through_match_or_an_angle_read_the_rows_alone(self):
        rows = [{"prop:Ore.label": "Gold", "yaw": 170.0}, {"prop:Ore.label": "Iron", "yaw": -170.0}]
        full = {"prop:Ore.label": {"n": 0, "nonzero": 0, "sum": 0.0, "min": None, "max": None},
                "yaw": {"n": 300, "nonzero": 300, "sum": 0.0, "min": -179.0, "max": 179.0}}
        for measure, want in ((m(probe="objects", select={"component": "Ore"}, field="prop:Ore.label", match="Gold"),
                               1.0),
                              (m(probe="objects", select={"component": "Ore"}, field="yaw", to_angle=180, of="max"),
                               10.0)):
            qid = probes.query_id(probes.needs(measure)[0])
            found = probes.reduce(measure, {"measures": {qid: [{"t": 0.0, "rows": rows, "total": 300, "full": full}]}})
            self.assertAlmostEqual(found, want)

    def test_screen_luminance_is_sampled_like_the_other_probes(self):
        dark = m(probe="screen", field="luminance", window=[1, 1.5], agg="mean")
        self.assertEqual(dark["rect"], [0.0, 0.0, 1.0, 1.0])
        (query,) = probes.needs(m(probe="screen", rect=[0, 0.5, 1, 1], field="luma"))
        self.assertEqual(query, {"kind": "screen", "rect": [0.0, 0.5, 1.0, 1.0]})
        qid = probes.query_id(probes.needs(dark)[0])
        frames = [{"luminance": 0.5, "luma": 0.7}, None, {"luminance": 0.1, "luma": 0.3},
                  {"luminance": 0.2, "luma": 0.4}, {"luminance": 0.9, "luma": 0.9}]
        self.assertAlmostEqual(probes.reduce(dark, {"measures": {qid: sampled(frames)}}), 0.15)

    def test_a_parts_world_rotation_reads_as_an_angle(self):
        moon = m(probe="objects", select={"tag": "Moon"}, field="world_yaw:Light", to_angle=-90, of="first")
        play = objects_play(moon, [[{"world_yaw:Light": 280.0}]])
        self.assertAlmostEqual(probes.reduce(moon, play), 10.0)
        self.assertTrue(all(tasks.is_angle(f) for f in ("world_yaw:Moon", "world_pitch:Moon", "world_roll:Moon")))
        self.assertFalse(tasks.is_angle("forward:Moon.y"))
        down = m(probe="objects", select={"tag": "Moon"}, field="forward:Light.y", of="first")
        self.assertEqual(probes.reduce(down, objects_play(down, [[{"forward:Light.y": -0.5}]])), -0.5)


LAMP = {"probe": "components", "select": {"component": "Light", "owner": {"tag": "Lamp"}}, "at": "end"}
CRATE = {"probe": "objects", "select": {"tag": "Crate"}, "at": "end"}


class MoreFairReadings(unittest.TestCase):
    """docs/task-probes.md: lights that are off, what is on screen, what the player hears, the ground, a teleport next
    to an object, moving components, whole or broken."""

    def test_the_new_readings_refuse_what_they_cant_read(self):
        for bad in ({"probe": "components", "select": {"component": "Light"}, "field": "lumens"},
                    {"probe": "objects", "select": {"tag": "A"}, "field": "spread_x"},
                    {"probe": "audio", "select": {"sound": "Rain/*"}, "field": "count"},
                    {"probe": "audio", "field": "loudest"},
                    {"probe": "ground", "field": "height"},
                    {"probe": "ground", "xz": [0, 0], "box": [0, 0, 1, 1], "field": "height"},
                    {"probe": "ground", "xz": [0, 0], "field": "range"},
                    {"probe": "ground", "box": [0, 0, 1, 1], "field": "height"},
                    {"probe": "ground", "box": [5, 0, 1, 1], "field": "max"},
                    {"probe": "ground", "box": [0, 0, 1, 1], "grid": 64, "field": "max"},
                    {"probe": "ground", "xy": [0, 0], "field": "height"},
                    {"probe": "widgets", "select": {"name": "Warn*", "visible": False}, "field": "count"}):
            with self.assertRaises(ValueError, msg=json.dumps(bad)):
                task_with(probe(measure=bad))

    def test_lights_read_on_and_their_intensity_as_components(self):
        lamp = m(**{**LAMP, "field": "on", "of": "any", "at": None})
        (query,) = probes.needs(lamp)
        self.assertEqual(query["fields"], ["on"])
        play = objects_play(lamp, [[{"name": "L", "on": 1, "intensity": 5.0}], [{"name": "L", "on": 0,
                                                                                 "intensity": 0.0}]])
        self.assertEqual(probes.reduce(lamp, play), 0)
        bright = m(**{**LAMP, "field": "intensity", "of": "max", "at": None, "agg": "first"})
        self.assertEqual(probes.query_id(probes.needs(bright)[0]), probes.query_id(query), "one query, both fields")
        self.assertEqual(probes.reduce(bright, play), 5.0)

    def test_a_visible_widget_select_is_its_own_query(self):
        shown = m(probe="widgets", select={"name": "Warn*", "visible": True}, field="count")
        every = m(probe="widgets", select={"name": "Warn*"}, field="count")
        self.assertEqual(probes.needs(shown)[0]["select"], {"name": "Warn*", "visible": True})
        self.assertEqual(probes.needs(every)[0]["select"], {"name": "Warn*"}, "a select without it is as it was")
        self.assertNotEqual(probes.query_id(probes.needs(shown)[0]), probes.query_id(probes.needs(every)[0]))
        self.assertEqual(probes.reduce(shown, objects_play(shown, [[{"name": "WarnVisible"}]])), 1)

    def test_what_the_player_hears_reduces_from_the_audio_samples(self):
        jungle = m(probe="audio", select={"sound_class": "Jungle*", "owner": {"tag": "Zone2"}}, field="volume",
                   agg="mean")
        (query,) = probes.needs(jungle)
        self.assertEqual(query, {"kind": "audio", "select": {"sound_class": "Jungle*", "owner": {"tag": "Zone2"}}})
        self.assertEqual(probes.needs(m(probe="audio", field="count"))[0], {"kind": "audio", "select": {}})
        value = {"count": 2, "audible": 1, "volume": 0.6, "max_volume": 0.5, "level": 0.08, "loudest": "Birds"}
        qid = probes.query_id(query)
        play = {"measures": {qid: sampled([value, {**value, "volume": 0.2, "level": 0.02}])}}
        self.assertAlmostEqual(probes.reduce(jungle, play), 0.4)
        level = m(probe="audio", select={"sound_class": "Jungle*", "owner": {"tag": "Zone2"}}, field="level",
                  agg="max")
        self.assertEqual(probes.query_id(probes.needs(level)[0]), qid, "one query, every field")
        self.assertAlmostEqual(probes.reduce(level, play), 0.08)
        self.assertIsNone(probes.reduce(jungle, {"measures": {qid: sampled([None])}}),
                          "a play that measured no audio measures nothing, never 0")

    def test_a_lamp_reads_lit_whatever_lights_it(self):
        lamp = {"tag": "lamp", "has": {"lit": True}}
        lit = m(probe="objects", select=lamp, field="lit", of="all", at="end")
        (query,) = probes.needs(lit)
        self.assertEqual(query, {"kind": "objects", "select": lamp, "fields": ["lit"]})
        rows = [[{"name": "A", "lit": 0.0}, {"name": "B", "lit": 0.0}],
                [{"name": "A", "lit": 1.0, "glow_sources": "light"}, {"name": "B", "lit": 1.0, "glow_sources": "effect"}]]
        self.assertEqual(probes.reduce(lit, objects_play(lit, rows)), 1)
        glow = m(probe="objects", select=lamp, field="glow", of="sum", at="end")
        self.assertEqual(probes.query_id(probes.needs(glow)[0]), probes.query_id(query), "one query, both fields")
        bright = [[{"name": "A", "glow": 2.0}, {"name": "B", "glow_read": "unread"}]]
        self.assertEqual(probes.reduce(glow, objects_play(glow, bright)), 2, "a lamp that can't be read adds nothing")
        unread = m(probe="objects", select={"name": "B"}, field="glow", of="first")
        self.assertIsNone(probes.reduce(unread, objects_play(unread, [[{"name": "B", "glow_read": "unread"}]])))
        bulb = m(probe="components", select={"component": "Light3D", "owner": {"tag": "lamp"}}, field="glow", of="max")
        self.assertEqual(probes.needs(bulb)[0]["fields"], ["glow"])
        with self.assertRaisesRegex(ValueError, "glow depends on what a build chose"):
            task_with(probe(measure={"probe": "objects", "select": lamp, "field": "glow", "of": "first"},
                            expect={"op": ">=", "value": 2}))

    def test_the_sounds_that_start_are_counted_per_interval_and_by_name(self):
        hit = m(probe="audio", select={"near": {"point": {"xyz": [1.2, 1.0, 0]}, "radius": 0.8}}, field="started_audible",
                window=[2, 3])
        (query,) = probes.needs(hit)
        self.assertEqual(query["select"], {"near": {"point": {"xyz": [1.2, 1.0, 0.0]}, "radius": 0.8}})
        qid = probes.query_id(query)
        values = [{"started": 0, "started_audible": 0}, {"started": 1, "started_audible": 1},
                  {"started": 2, "started_audible": 1}, {"started": 0, "started_audible": 0}]
        play = {"measures": {qid: [{"t": 2.0 + i * 0.5, "value": v} for i, v in enumerate(values)]}}
        self.assertEqual(probes.reduce(hit, play), 2, "summed by default")
        self.assertEqual(probes.reduce({**hit, "field": "started"}, play), 3)
        names = m(probe="audio", field="sounds")
        nid = probes.query_id(probes.needs(names)[0])
        starts = [{"t": 1.2, "sound": "gun_b", "named": True}, {"t": 1.0, "sound": "gun_a", "named": True},
                  {"t": 1.4, "sound": "gun_b", "named": True}]
        heard = {"measures": {nid: sampled([{"starts": [], "starts_total": 0}, {"starts": starts, "starts_total": 3}])}}
        self.assertEqual(probes.reduce(names, heard), 2)
        repeats = m(probe="audio", field="repeats")
        self.assertEqual(probes.reduce(repeats, heard), 1, "in the order they started")
        self.assertEqual(probes.reduce(m(probe="audio", field="repeats", window=[0, 0.2]), heard), 0, "none started: 0")
        made = {"measures": {nid: sampled([{"starts": [{"t": 1.0, "sound": "", "named": False}], "starts_total": 1}])}}
        self.assertEqual(probes.measured(names, made)[1], "a sound that started has no name to tell it by: a stream made "
                         "in code, or one that picks or mixes other streams (a randomizer, a polyphonic stream)")
        voiced = {"measures": {qid: [{"t": 2.5, "value": {"started": 1, "started_audible": 0, "voices_unseen": True}}]}}
        self.assertEqual(probes.measured(hit, voiced), (0.0, probes.VOICES), "the detail says why nothing was seen")
        self.assertEqual(probes.measured({**hit, "field": "started"}, voiced), (1.0, probes.VOICES))
        voiced["measures"][qid][0]["value"]["count"] = 1
        self.assertEqual(probes.measured({**hit, "field": "count", "window": None}, voiced), (1.0, None))
        self.assertIsNone(probes.reduce(hit, {"measures": {qid: [{"t": 2.5, "value": None}]}}),
                          "near a point that didn't resolve: no value")
        many = {"measures": {nid: sampled([{"starts": starts, "starts_total": 70}])}}
        self.assertIsNone(probes.reduce(names, many), "more started than the probe lists")
        self.assertIsNone(probes.reduce(names, {"measures": {nid: sampled([None])}}))
        self.assertEqual(probes.measured(m(probe="audio", field="sounds", window=[30, 40]), {**heard, "seconds": 1.0})[1],
                         "no samples in the window (the play ended at 1 s)")
        for field in ("sounds", "repeats", "started_audible"):  # how many started is a fact: a literal value
            task_with(probe(measure={"probe": "audio", "field": field}, expect={"op": ">=", "value": 1}))

    def test_a_task_play_teleports_next_to_an_object(self):
        play = {"name": "ore", "seconds": 12, "inputs": [
            {"t": 1, "teleport_to": {"tag": "Ore"}},
            {"t": 3, "teleport_to": {"component": "OreChunk"}, "distance": 3.5, "offset": [0, 1, 0],
             "face": {"object": {"tag": "Tug"}}}]}
        first, second = first_check(task_with(probe(play=play, measure={"probe": "player", "field": "y"})))["play"][
            "inputs"]
        self.assertEqual(first, {"t": 1.0, "teleport_to": {"tag": "Ore"}, "distance": 2.0, "offset": [0, 0, 0]})
        self.assertEqual(second["face"], {"object": {"tag": "Tug"}, "offset": [0, 0, 0]})
        self.assertEqual((second["distance"], second["offset"]), (3.5, [0.0, 1.0, 0.0]))
        with self.assertRaises(ValueError):
            task_with(probe(play={**play, "inputs": [{"t": 1, "teleport_to": {"tag": "Ore"}, "yaw": 90}]},
                            measure={"probe": "player", "field": "y"}))

    def test_a_task_play_stages_a_contact(self):
        live = {"tag": "foe", "where": [{"prop": "dead", "op": "==", "value": False}]}
        play = {"name": "duel", "seconds": 12, "inputs": [
            {"t": 1, "set": "health", "on": {"tag": "foe"}, "value": 1, "all": True},
            {"t": 2, "pin": live, "hold": 3, "front": 1.5},
            {"t": 2, "pin": {"component": "MaintBot"}, "hold": 1, "at": {"object": {"component": "Flare"}}},
            {"t": 2.3, "key": "<Keyboard>/j", "press": True},
            {"t": 3, "damage": 20, "to": {"player": True}},
            {"t": 4, "damage": 5, "to": live, "from": {"name": "Turret"}},
            {"t": 5, "set": "Health.current", "on": {"player": True}, "value": 500}]}
        rows = first_check(task_with(probe(play=play, measure={"probe": "player", "field": "y"})))["play"]["inputs"]
        self.assertEqual(rows[1], {"t": 2.0, "pin": live, "hold": 3.0, "offset": [0.0, 0.0, 0.0], "front": 1.5})
        self.assertEqual(rows[2]["at"], {"object": {"component": "Flare"}, "offset": [0.0, 0.0, 0.0]})
        self.assertNotIn("front", rows[2])
        self.assertEqual(rows[4], {"t": 3.0, "damage": 20.0, "to": {"player": True}})
        self.assertEqual(rows[5]["from"], {"name": "Turret"})
        self.assertEqual(rows[0], {"t": 1.0, "set": "health", "on": {"tag": "foe"}, "value": 1, "all": True})
        self.assertEqual(rows[6]["all"], False)
        for bad in ({"t": 1, "pin": {"player": True}, "hold": 3},
                    {"t": 1, "pin": {"tag": "A"}, "hold": 3, "front": 1, "at": {"player": True}}):
            with self.assertRaises(ValueError):
                task_with(probe(play={**play, "inputs": [bad]}, measure={"probe": "player", "field": "y"}))

    def test_a_stage_that_didnt_land_fails_every_probe_of_its_play(self):
        """A reading of a contact that never happened is no reading: `damage_taken` 0 or a time scale of 1 would pass."""
        calm = m(probe="world", field="time_scale", agg="min")
        qid = probes.query_id(probes.needs(calm)[0])
        play = {"seconds": 8.5, "track": [[0.5, 0, 1.0, 0]], "inputs_missed": [],
                "measures": {qid: sampled([{"time_scale": 1.0, "paused": 0}])}}
        self.assertEqual(probes.measured(calm, play), (1.0, None))
        for kind, target in (("pin", '{"tag":"foe"}'), ("damage", "Post"), ("set", "health")):
            missed = {**play, "inputs_missed": [{"t": 2.0, "kind": kind, "target": target, "why": "no object matches"}]}
            self.assertEqual(probes.measured(calm, missed),
                             (None, f"a stage of the play didn't land: {kind} {target} at 2 s: no object matches"), kind)
            self.assertIsNone(probes.reduce(m(probe="player", field="y"), missed), "the play's other probes too")
            self.assertIsNone(probes.reduce(m(probe="log", pattern="hit"), missed, "hit\n"))
        for kind in ("tap", "drag", "click", "shot", "scene"):  # a touch or a click that missed is read as before
            other = {**play, "inputs_missed": [{"t": 2.0, "kind": kind, "target": "X", "why": "nothing there"}]}
            self.assertEqual(probes.measured(calm, other), (1.0, None), kind)
        duel = {"name": "duel", "seconds": 8, "inputs": [{"t": 2, "damage": 5, "to": {"tag": "foe"}}]}
        task = task_with(probe(play=duel, measure={"probe": "world", "field": "time_scale", "agg": "min"},
                               expect={"op": "==", "value": 1}))

        def answer(seconds, shots, queries):
            (query,) = queries["queries"]
            return {**play, "inputs_missed": [{"t": 2.0, "kind": "damage", "target": '{"tag":"foe"}',
                                               "why": "no object matches"}],
                    "measures": {query["id"]: sampled([{"time_scale": 1.0, "paused": 0}])}}, ""

        reference = side("reference", FakeProject(answer), task)
        grade = check.Grade(task, "reference", reference, reference, {})
        passed, detail = grade.check(first_check(task))
        self.assertFalse(passed, "the reference's miss makes the task INVALID: no reading passes it")
        self.assertIn("a stage of the play didn't land: damage", detail)

    def test_the_world_and_an_object_read_what_a_contact_leaves(self):
        slowed = m(probe="world", field="time_scale", window=[2, 4], agg="min")
        (query,) = probes.needs(slowed)
        self.assertEqual(query, {"kind": "world", "fields": ["time_scale"]})
        qid = probes.query_id(query)
        values = [{"time_scale": 1.0, "paused": 0}] * 5 + [{"time_scale": 0.05, "paused": 0}]
        self.assertEqual(probes.reduce(slowed, {"measures": {qid: sampled(values)}}), 0.05)
        paused = m(probe="world", field="paused", agg="max")
        self.assertEqual(probes.query_id(probes.needs(paused)[0]), qid, "one world query a play")
        self.assertEqual(probes.reduce(paused, {"measures": {qid: sampled(values)}}), 0)
        task = task_with(probe("a", measure={"probe": "world", "field": "time_scale", "agg": "min"}),
                         probe("b", measure={"probe": "world", "field": "paused", "agg": "max"}))
        self.assertEqual(probes.plan(task)["look"], [{"id": qid, "kind": "world", "fields": ["paused", "time_scale"]}])
        held = m(probe="world", field="flow", agg="min")
        self.assertEqual(probes.query_id(probes.needs(held)[0]), qid)
        stop = [{"time_scale": 1.0, "flow": 1.0, "paused": 0}, {"time_scale": 1.0, "flow": 0.0, "paused": 1}]
        self.assertEqual(probes.reduce(held, {"measures": {qid: sampled(stop)}}), 0, "a stop made by a pause")
        self.assertEqual(probes.reduce(m(probe="world", field="time_scale", agg="min"),
                                       {"measures": {qid: sampled(stop)}}), 1, "which slows no time")
        frozen = m(probe="objects", select={"tag": "foe"}, field="frozen", of="max", agg="max")
        self.assertEqual(probes.needs(frozen)[0]["fields"], ["frozen"])
        stops = [[{"name": "Foe"}], [{"name": "Foe", "frozen": 0.0}], [{"name": "Foe", "frozen": 0.1}]]
        self.assertAlmostEqual(probes.reduce(frozen, objects_play(frozen, stops)), 0.1)
        hurt = m(probe="objects", select={"player": True}, field="damage_taken", of="first", at="end")
        self.assertEqual(probes.reduce(hurt, objects_play(hurt, [[{"damage_taken": 0.0}], [{"damage_taken": 20.0}]])), 20)
        others = m(probe="objects", select={"component": "CharacterBody3D", "player": False, "where": [
            {"prop": "dead", "op": "==", "value": False}]}, field="count")
        self.assertEqual(probes.needs(others)[0]["select"]["player"], False)

    def test_only_a_play_that_measures_audio_says_so_in_its_spec(self):
        heard = task_with(probe(measure={"probe": "audio", "select": {"sound": "Rain*"}, "field": "count"}),
                          probe("quiet", play={"name": "quiet", "seconds": 10},
                                measure={"probe": "player", "field": "y"}))
        plays = probes.plan(heard)
        self.assertTrue(probes.hears(plays["look"]) and probes.hears(probes.query_file(plays["look"])))
        self.assertFalse(probes.hears(plays["quiet"]) or probes.hears(None))
        specs = []

        def job(label, argv, cwd, timeout, gpu=False):
            specs.append(json.loads(Path(str(argv[argv.index("-taskProbe") + 1])).read_text(encoding="utf-8")))
            return types.SimpleNamespace(exit_code=0, timed_out=False, output="", seconds=1.0, waited=0.0)

        with tempfile.TemporaryDirectory() as folder:
            project = godot.Project(folder, types.SimpleNamespace(job=job, editor="godot"), "start")
            project.play(5, 0, 60, queries=probes.query_file(plays["look"]))
            project.play(5, 0, 60)
        loud, quiet = specs
        self.assertEqual((loud["sound"], quiet["sound"]), (True, False))
        with self.assertRaisesRegex(ValueError, "can't set -taskProbeSound"):
            task_with(probe(play={"name": "x", "seconds": 5, "args": ["-taskProbeSound"]},
                            measure={"probe": "player", "field": "y"}))


UI_TEXT = {"probe": "ui", "select": {"kind": "text"}, "field": "text", "match": r"AMMO\s*\d+", "of": "any"}
# one sample's elements as the probe reads them: three texts and a panel (a hidden text is not on screen, so not a
# row); source and kind ride along for the logs
UI_ROWS = [{"text": "HP 75%", "x": 0.021, "y": 0.203, "w": 0.083, "h": 0.035, "source": "control", "kind": "text"},
           {"text": "ITEMS 7", "x": 0.021, "y": 0.278, "w": 0.05, "h": 0.015, "source": "control", "kind": "text"},
           {"text": "AMMO 30", "x": 0.042, "y": 0.225, "w": 0.106, "h": 0.033, "source": "control", "kind": "text"},
           {"text": None, "x": 0.042, "y": 0.296, "w": 0.208, "h": 0.03, "source": "control", "kind": "box"}]


class UiWhateverDrawsIt(unittest.TestCase):
    """docs/task-probes.md: one reading for what the UI shows on screen, whatever controls a build drew it with."""

    def test_text_takes_match_and_every_field_a_literal(self):
        for measure in (UI_TEXT, {**UI_TEXT, "of": "count", "select": {"text": "AMMO", "rect": [0, 0, 0.5, 0.5]}},
                        {"probe": "ui", "field": "count"},
                        {"probe": "ui", "select": {"kind": "box", "rect": [0, 0.2, 0.5, 0.4]}, "field": "count"},
                        {"probe": "ui", "select": {"kind": "image"}, "field": "count"},
                        {"probe": "ui", "select": {"text": "AMMO"}, "field": "y", "of": "first"}):
            task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        for bad, said in [({**UI_TEXT, "match": None}, "exactly when its field is text"),
                          ({"probe": "ui", "field": "count", "match": "x"}, "exactly when its field is text"),
                          ({**UI_TEXT, "match": "AMMO("}, "isn't a regular expression"),
                          ({"probe": "ui", "select": {"rect": [0.5, 0, 0.2, 1]}, "field": "count"}, "x0 < x1"),
                          ({"probe": "ui", "select": {"kind": "box", "text": "x"}, "field": "count"}, "picks text"),
                          ({"probe": "ui", "field": "source"}, "not one of"),
                          ({"probe": "ui", "field": "kind"}, "not one of"),
                          ({"probe": "ui", "select": {"kind": "line"}, "field": "count"}, ""),
                          ({"probe": "ui", "select": {"kind": "stroke"}, "field": "count"}, ""),
                          ({"probe": "ui", "select": {"source": "control"}, "field": "count"}, "")]:
            with self.assertRaisesRegex(ValueError, said, msg=json.dumps(bad)):
                task_with(probe(measure=bad))

    def test_one_query_per_select_its_fields_merged(self):
        text = m(**UI_TEXT)
        (query,) = probes.needs(text)
        self.assertEqual(query, {"kind": "ui", "select": {"kind": "text"}, "fields": ["text"]})
        count = m(probe="ui", select={"kind": "text"}, field="count")
        self.assertEqual(probes.query_id(probes.needs(count)[0]), probes.query_id(query))
        self.assertEqual(m(probe="ui", field="count")["select"], {})
        boxes = m(probe="ui", select={"kind": "box", "rect": [0, 0.2, 0.5, 0.4]}, field="count")
        self.assertNotEqual(probes.query_id(probes.needs(boxes)[0]), probes.query_id(query))

    def test_images_and_boxes_count_by_rect(self):
        # one sample of a HUD: three heart sprites (images), a panel behind them (a box) and a label
        hearts = [{"text": None, "x": 0.02 + 0.03 * i, "y": 0.02, "w": 0.025, "h": 0.04, "source": "control",
                   "kind": "image"} for i in range(3)]
        panel = {"text": None, "x": 0.01, "y": 0.01, "w": 0.2, "h": 0.06, "source": "control", "kind": "box"}
        label = {"text": "LIVES", "x": 0.12, "y": 0.02, "w": 0.06, "h": 0.03, "source": "control", "kind": "text"}
        images = m(probe="ui", select={"kind": "image", "rect": [0, 0, 0.25, 0.1]}, field="count")
        self.assertEqual(images["select"], {"kind": "image", "rect": [0, 0, 0.25, 0.1]})
        self.assertEqual(probes.reduce(images, objects_play(images, [hearts])), 3)
        every = m(probe="ui", field="count")
        self.assertEqual(probes.reduce(every, objects_play(every, [hearts + [panel, label]])), 5)

READOUT = [0.02, 0.02, 0.3, 0.12]


def text_readout(value, source="control"):
    return [{"text": f"SCORE {value}", "x": 0.05, "y": 0.04, "w": 0.01 * len(str(value)) + 0.06, "h": 0.03,
             "source": source, "kind": "text"}]


def digit_readout(digits):
    """A readout drawn as one digit sprite per digit: the sprites (images) and the text beside them."""
    sprites = [{"text": None, "x": 0.05 + 0.015 * i, "y": 0.04, "w": 0.012, "h": 0.03, "source": "control",
                "kind": "image"} for i in range(len(digits))]
    return sprites + [{"text": digits, "x": 0.05, "y": 0.04, "w": 0.015 * len(digits), "h": 0.03, "source": "control",
                       "kind": "text"}]


class UiSignature(unittest.TestCase):
    """docs/task-probes.md: whether what a ui select shows updates, however it is drawn."""

    def changes(self, rows, agg="changes", **extra):
        measure = m(probe="ui", select={"rect": READOUT}, field="signature", agg=agg, **extra)
        return probes.reduce(measure, objects_play(measure, rows))

    def test_takes_agg_changes_any_all_or_count(self):
        measure = {"probe": "ui", "select": {"rect": READOUT}, "field": "signature", "window": [2, 10],
                   "agg": "changes"}
        task_with(probe(measure=measure, expect={"op": ">=", "value": 1}))
        for agg in ("any", "all", "count"):
            task_with(probe(measure={**measure, "agg": agg}, expect={"op": ">=", "value": 1}))
        for agg in (None, "last", "max", "delta", "range"):
            with self.assertRaisesRegex(ValueError, "signature", msg=str(agg)):
                task_with(probe(measure={**measure, "agg": agg}))
        with self.assertRaisesRegex(ValueError, "exactly when its field is text"):
            task_with(probe(measure={**measure, "match": "x"}))
        (query,) = probes.needs(m(**measure))
        self.assertEqual(query, {"kind": "ui", "select": {"rect": READOUT}, "fields": ["h", "text", "w", "x", "y"]})
        count = m(probe="ui", select={"rect": READOUT}, field="count")
        self.assertEqual(probes.query_id(probes.needs(count)[0]), probes.query_id(query), "one select, one reading")

    def test_a_text_readout_changing_counts(self):
        rows = [text_readout(v) for v in (0, 0, 12, 12, 25, 140, 140)]
        self.assertEqual(self.changes(rows), 3)
        self.assertEqual(self.changes(rows, window=[0, 1.5]), 1)

    def test_a_static_readout_never_changes(self):
        still = text_readout(120)
        self.assertEqual(self.changes([still] * 8), 0)
        jitter = [[{**still[0], "x": 0.05 + d}] for d in (0, 0.0001, -0.0001, 0.0002)]
        self.assertEqual(self.changes(jitter), 0, "geometry is read to 0.002 of the viewport")
        restyled = [still, [{**still[0], "source": "control"}], [{**still[0], "name": "Other"}]]
        self.assertEqual(self.changes(restyled), 0, "how a build drew it is not what it shows")
        reordered = [text_readout(1) + digit_readout("1"), digit_readout("1") + text_readout(1)]
        self.assertEqual(self.changes(reordered), 0, "the elements are a set")

    def test_nothing_shown_reads_zero(self):
        rows = [[], text_readout(5), [], None]
        self.assertEqual(self.changes(rows, agg="count"), 1, "samples showing something")
        self.assertEqual(self.changes(rows, agg="all"), 0)
        self.assertEqual(self.changes(rows, agg="any"), 1)
        self.assertEqual(self.changes(rows), 2, "appearing and going are changes; no frame drawn is no value")


SPOT = {"point": {"xyz": [1, 0.5, 0]}, "radius": 3}
SPOT_SENT = {"point": {"xyz": [1.0, 0.5, 0.0]}, "radius": 3.0}
BEAM = {"from": {"player": True, "offset": [0, 0.6, 0]}, "to": {"camera": True, "forward": 30}, "radius": 0.4}


def number_rows(*texts):
    """Text elements of one sample, given right to left so reading order must be restored."""
    return [{"text": t, "x": 0.05 + 0.1 * i, "y": 0.04, "w": 0.08, "h": 0.03, "source": "control", "kind": "text"}
            for i, t in enumerate(texts)][::-1]


class OutcomeReadings(unittest.TestCase):
    """docs/task-probes.md: what is drawn in a place, how fast a part spins, live effects, which way a number or a
    clock on screen moved, an object a player can shove, a height band, a held teleport and a wait in real time."""

    def test_spin_is_a_field_of_components_and_objects_and_never_a_literal(self):
        fan = {"probe": "components", "select": {"component": "Renderer", "near": SPOT}, "field": "spin",
               "of": "max", "agg": "mean"}
        for measure in (fan, {"probe": "objects", "select": {"tag": "Fan"}, "field": "spin", "at": "end"}):
            with self.assertRaisesRegex(ValueError, "never a literal value"):
                task_with(probe(measure=measure, expect={"op": ">=", "value": 90}))
            task_with(probe(measure=measure, expect={"op": ">=", "calibrate": 0.5}))
        turning = m(**fan)
        rows = [[{"name": "Blade", "spin": None}], [{"name": "Blade", "spin": 360.0}, {"name": "Hub", "spin": 0.0}],
                [{"name": "Blade", "spin": 720.0}]]
        self.assertEqual(probes.reduce(turning, objects_play(turning, rows)), 540)

    def test_a_components_select_takes_live_effects_with_or_without_a_component(self):
        live = {"probe": "components", "select": {"effect": True, "near": SPOT}, "field": "count", "at": "end"}
        task_with(probe(measure=live, expect={"op": "<=", "value": 3}),
                  probe("b", measure={**live, "select": {"component": "GPUParticles3D", "effect": True}}))
        (query,) = probes.needs(m(**live))
        self.assertEqual(query["select"], {"effect": True, "near": SPOT_SENT})
        for bad in ({"near": SPOT}, {"effect": False}):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(measure={**live, "select": bad}))

    def shown(self, field, samples, agg="last", **extra):
        measure = m(probe="ui", select={"kind": "text", "rect": READOUT}, field=field, agg=agg, **extra)
        return probes.reduce(measure, objects_play(measure, samples))

    def test_ui_number_reads_the_first_number_shown_in_reading_order(self):
        self.assertEqual(self.shown("number", [number_rows("SCORE", "3,450")]), 3450)
        self.assertEqual(self.shown("number", [number_rows("x3", "120")]), 3, "the first in reading order")
        self.assertEqual(self.shown("number", [number_rows("TEMP -12.5")]), -12.5)
        self.assertEqual(self.shown("number", [number_rows("LAP 2-3")]), 2, "a dash between numbers is no sign")
        self.assertIsNone(self.shown("number", [number_rows("READY")]))
        (query,) = probes.needs(m(probe="ui", select={"kind": "text", "rect": READOUT}, field="number"))
        signature = m(probe="ui", select={"kind": "text", "rect": READOUT}, field="signature", agg="changes")
        self.assertEqual(query, probes.needs(signature)[0], "one select, one query")
        with self.assertRaisesRegex(ValueError, "exactly when its field is text"):
            task_with(probe(measure={"probe": "ui", "select": {"rect": READOUT}, "field": "number", "match": "x"}))

    def test_ui_number_tells_which_way_it_moved(self):
        scores = [number_rows(f"SCORE {v}") for v in (0, 0, 10, 25, 25, 0, 5)] + [None]
        self.assertEqual(self.shown("number", scores, agg="rises"), 3)
        self.assertEqual(self.shown("number", scores, agg="falls"), 1, "a reset is a fall")
        self.assertEqual(self.shown("number", scores, agg="changes"), 4)
        task_with(probe(measure={"probe": "ui", "select": {"kind": "text", "rect": READOUT}, "field": "number",
                                 "window": [2, 10], "agg": "falls"}, expect={"op": "==", "value": 0}))

    def test_ui_clock_reads_a_timer_as_seconds_through_a_pause_and_a_retry(self):
        self.assertEqual(self.shown("clock", [number_rows("TIME 1:05.5")]), 65.5)
        self.assertEqual(self.shown("clock", [number_rows("1:02:03")]), 3723)
        self.assertEqual(self.shown("clock", [number_rows("12.5s")]), 12.5, "a plain number is seconds")
        run = [number_rows(f"0:{s:02d}") for s in (1, 2, 3)] + [number_rows("0:03")] * 4 + \
            [number_rows(f"0:{s:02d}") for s in (0, 1)]
        self.assertEqual(self.shown("clock", run, agg="range", window=[1.0, 3.0]), 0, "held through the pause")
        self.assertEqual(self.shown("clock", run, agg="falls"), 1, "reset on the retry")

    def test_has_finds_an_object_by_what_it_can_do(self):
        shovable = {"has": {"simulating": True, "near": {"point": {"player": True}, "radius": 20}}}
        play = {"name": "shove", "seconds": 10, "inputs": [{"t": 1, "teleport_to": shovable, "distance": 1.5}]}
        task = task_with(probe(play=play, measure={"probe": "objects", "select": shovable, "field": "x", "at": "end"}))
        self.assertTrue(probes.plan(task)["shove"][0]["select"]["has"]["simulating"])
        with self.assertRaises(ValueError):
            task_with(probe(measure={"probe": "objects", "select": {"has": {"simulating": False}}, "field": "count"}))
        with self.assertRaisesRegex(ValueError, 'unexpected key "movable"', msg="a built player keeps no Static flag"):
            task_with(probe(measure={"probe": "objects", "select": {"has": {"movable": True}}, "field": "count"}))

    def test_near_takes_a_height_band_wherever_it_works(self):
        band = {"point": {"xyz": [0, 0, 0]}, "radius": 5, "y_min": 1, "y_max": 3}
        rel = {"point": {"player": True}, "radius": 5, "y_min": -0.5, "y_relative": True}
        task = task_with(
            probe("a", measure={"probe": "objects", "select": {"near": band}, "field": "count"}),
            probe("b", measure={"probe": "components", "select": {"component": "Light", "near": rel},
                                "field": "count"}),
            probe("c", measure={"probe": "objects", "select": {"tag": "Lamp", "near": band}, "field": "count"}))
        sent = [json.dumps(q, sort_keys=True) for q in probes.plan(task)["look"]]
        self.assertEqual(sum('"y_max": 3.0, "y_min": 1.0' in q for q in sent), 2)
        self.assertEqual(sum('"y_relative": true' in q for q in sent), 1)
        plain = m(probe="objects", select={"near": SPOT}, field="count")
        self.assertEqual(probes.needs(plain)[0]["select"], {"near": SPOT_SENT}, "a near without a band as before")
        for bad in ({**band, "y_min": 3}, {"point": {"player": True}, "radius": 1, "y_relative": True},
                    {**band, "z_min": 1}):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(measure={"probe": "objects", "select": {"near": bad}, "field": "count"}))

    def test_a_teleport_holds_and_a_play_waits_in_real_time(self):
        play = {"name": "tour", "seconds": 60, "inputs": [
            {"t": 1, "teleport": [0, 1, 0], "hold": 5}, {"t": 2, "teleport_to": {"tag": "Pad"}, "hold": 3},
            {"t": 4, "key": "<Keyboard>/enter", "press": True}, {"t": 8, "wait": 90}, {"t": 20, "wait": 30}]}
        task = task_with(probe(play=play, measure={"probe": "player", "field": "y"}))
        sent = first_check(task)["play"]
        self.assertEqual(tasks.waited(sent), 120)
        self.assertEqual(sent["inputs"][0], {"t": 1.0, "teleport": [0.0, 1.0, 0.0], "yaw": 0.0, "hold": 5.0})
        self.assertEqual(sent["inputs"][3], {"t": 8.0, "wait": 90.0})
        self.assertEqual(tasks.play({"name": "tp", "seconds": 9, "inputs": [{"t": 1, "teleport": [0, 0, 0]}]})["inputs"],
                         [{"t": 1.0, "teleport": [0.0, 0.0, 0.0], "yaw": 0.0}], "sent as before")
        for bad in ([{"t": 1, "wait": 200}, {"t": 2, "wait": 150}], [{"t": 1, "wait": 0}], [{"t": 1, "wait": 301}],
                    [{"t": 1, "teleport": [0, 0, 0], "hold": 0}], [{"t": 1, "teleport": [0, 0, 0], "hold": 121}]):
            with self.assertRaises(ValueError, msg=str(bad)):
                task_with(probe(play={**play, "inputs": bad}, measure={"probe": "player", "field": "y"}))

    def test_inputs_are_input_system_control_paths(self):
        play = {"name": "keys", "seconds": 10, "inputs": [
            {"t": 1, "key": "<Keyboard>/leftShift", "press": True}, {"t": 2, "key": "<Mouse>/leftButton", "press": True},
            {"t": 3, "key": "<Gamepad>/buttonSouth", "press": False}, {"t": 4, "key": "<Mouse>/delta/x", "axis": 4},
            {"t": 5, "key": "<Gamepad>/leftStick/x", "axis": -1}, {"t": 6, "cursor": [0.5, 0.25]},
            {"t": 7, "widget": "RetryButton", "click": True}]}
        sent = first_check(task_with(probe(play=play, measure={"probe": "player", "field": "y"})))["play"]["inputs"]
        self.assertEqual(sent[3], {"t": 4.0, "key": "<Mouse>/delta/x", "axis": 4.0})
        self.assertEqual(sent[5], {"t": 6.0, "cursor": [0.5, 0.25]})
        self.assertEqual(sent[6], {"t": 7.0, "widget": "RetryButton", "click": True})
        for key in ("W", "LeftMouseButton", "<Joystick>/trigger", "<Keyboard>/"):
            with self.assertRaises(ValueError, msg=key):
                task_with(probe(play={**play, "inputs": [{"t": 1, "key": key, "press": True}]},
                                measure={"probe": "player", "field": "y"}))


class Angles(unittest.TestCase):
    def test_angles_aggregates_and_the_new_query_kinds_reduce(self):
        self.assertEqual([probes.normal(a) for a in (270, -270, 180, -180, 540, 0)], [-90, 90, 180, 180, 180, 0])
        camera = {"camera": [[0.0, 0, 0, 0, 0.0, 270.0, 60.0], [0.5, 0, 0, 0, 0.0, -100.0, 60.0]]}
        self.assertEqual(probes.reduce(m(probe="camera", field="yaw", agg="first"), camera), -90)
        self.assertAlmostEqual(probes.reduce(m(probe="camera", field="yaw", to_angle=-90, agg="max"), camera), 10)
        turret = m(probe="objects", select={"tag": "Tank"}, field="rel_yaw:Turret", to_angle=180, of="max")
        self.assertEqual(probes.reduce(turret, objects_play(turret, [[{"rel_yaw:Turret": -170},
                                                                      {"rel_yaw:Turret": 175}]])), 10)
        self.assertEqual(probes.aggregate([1.0, 3.0, 3.0, 5.0], "range"), 4)
        self.assertAlmostEqual(probes.aggregate([1.0, 3.0, 3.0, 5.0], "std"), 2 ** 0.5)
        self.assertEqual(probes.aggregate([1.0, 1.0, 0.0, 0.0, 1.0, None], "changes"), 2)
        torches = m(probe="components", select={"component": "GPUParticles3D", "owner": {"tag": "Torch"}},
                    field="active", of="count")
        self.assertEqual(probes.reduce(torches, objects_play(torches, [[{"active": True}, {"active": False},
                                                                        {"active": 1}]])), 2)
        hint = m(probe="widgets", select={"component": "Label", "text": "^Press E"}, field="y", of="max")
        self.assertEqual(probes.reduce(hint, objects_play(hint, [[{"y": 0.9}, {"y": 0.4}]])), 0.9)

    def test_a_property_that_holds_an_angle_takes_to_angle(self):
        live = m(probe="objects", select={"component": "TrackGrid"}, field="prop:TrackGrid.straightYaw", to_angle=90)
        self.assertEqual((probes.angled(live, 450.0), probes.angled(live, -270.0), probes.angled(live, 0.0)),
                         (0.0, 0.0, 90.0))
        self.assertEqual(probes.angled(live, 270.0), 180.0)
        self.assertEqual(probes.angled(live, -90.0), 180.0)
        plain = m(probe="objects", select={"component": "TrackGrid"}, field="prop:TrackGrid.straightYaw")
        self.assertEqual(probes.angled(plain, 450.0), 450.0, "a property is an angle only with to_angle")

    def test_to_axis_folds_a_direction_and_its_opposite_into_one_axis(self):
        axis = m(probe="objects", select={"component": "TrackGrid"}, field="prop:TrackGrid.straightYaw", to_axis=90)
        self.assertEqual({probes.angled(axis, a) for a in (90.0, -90.0, 270.0)}, {0.0})
        self.assertEqual((probes.angled(axis, 0.0), probes.angled(axis, 180.0), probes.angled(axis, 45.0)),
                         (90.0, 90.0, 45.0))


if __name__ == "__main__":
    unittest.main()


class ComponentWorldTurn(unittest.TestCase):
    """docs/task-probes.md: components fields world_yaw and world_pitch read a part picked by where or what
    it is, as angles; objects' world_yaw:<Part> reads as before."""

    NEAR = {"point": {"xyz": [12, 3, 0]}, "radius": 4}

    def comp(self, **data):
        return m(probe="components", select={"component": "MeshInstance3D", "near": self.NEAR}, **data)

    def test_yaw_and_pitch_read_from_a_sample_and_wrap(self):
        yaw = self.comp(field="world_yaw", of="first")
        self.assertEqual(probes.needs(yaw)[0]["fields"], ["world_yaw"])
        self.assertEqual(probes.reduce(yaw, objects_play(yaw, [[{"world_yaw": 87.5, "world_pitch": 12.0}]])), 87.5)
        self.assertEqual(probes.reduce(yaw, objects_play(yaw, [[{"world_yaw": 270.0}]])), -90.0)
        lift = self.comp(field="world_pitch", of="min")
        self.assertEqual(probes.reduce(lift, objects_play(lift, [[{"world_pitch": 12.0}, {"world_pitch": 20.0}]])), 12.0)

    def test_near_with_of_and_agg_reads_the_worst_part_against_a_bearing(self):
        rows = [[{"world_yaw": 0.0}, {"world_yaw": 10.0}], [{"world_yaw": -95.0}, {"world_yaw": 265.0}],
                [{"world_yaw": 179.0}, {"world_yaw": -84.0}]]
        facing = self.comp(field="world_yaw", to_angle=-90, of="max")
        self.assertAlmostEqual(probes.reduce(facing, objects_play(facing, rows[:2])), 5.0)
        self.assertAlmostEqual(probes.reduce(facing, objects_play(facing, rows)), 91.0)
        held = self.comp(field="world_yaw", to_angle=-90, of="max", agg="min", window=[0, 0.5])
        self.assertAlmostEqual(probes.reduce(held, objects_play(held, rows)), 5.0)
        axis = self.comp(field="world_yaw", to_axis=90, of="first")
        self.assertAlmostEqual(probes.reduce(axis, objects_play(axis, [[{"world_yaw": -84.0}]])), 6.0)

    def test_the_named_objects_field_still_reads(self):
        named = m(probe="objects", select={"tag": "Tank"}, field="world_yaw:Gun", to_angle=-90, of="first")
        self.assertAlmostEqual(probes.reduce(named, objects_play(named, [[{"world_yaw:Gun": 275.0}]])), 5.0)


class ToursInOneLaunch(unittest.TestCase):
    """docs/task-probes.md: a task play tours several places and scenes in one launch (scene loads, view
    turns, named shots), so the grader's pictures come from the task, not from views the game lists."""

    TOUR = {"name": "tour", "seconds": 30, "inputs": [
        {"t": 1, "teleport_to": {"tag": "Kiosk"}, "distance": 3}, {"t": 1.5, "view": [-15, 90]},
        {"t": 2, "shot": "kiosk"}, {"t": 4, "scene": "res://scenes/Yard.tscn"}, {"t": 12, "shot": "yard"}]}

    def test_a_tour_is_a_task_play_and_its_inputs_reach_the_probe_as_written(self):
        task_with(probe(play=self.TOUR))
        self.assertEqual(tasks.inputs(self.TOUR["inputs"])[1:], [
            {"t": 1.5, "view": [-15.0, 90.0]}, {"t": 2.0, "shot": "kiosk"},
            {"t": 4.0, "scene": "res://scenes/Yard.tscn"}, {"t": 12.0, "shot": "yard"}])

    def test_shots_views_and_scenes_refuse_what_the_probe_cant_take(self):
        def play(*extra):
            return {**self.TOUR, "inputs": self.TOUR["inputs"] + list(extra)}
        for bad, said in [(play({"t": 20, "shot": "kiosk"}), "names a shot twice"),
                          (play({"t": 20, "view": [95, 0]}), "pitch -89 to 89"),
                          (play({"t": 20, "shot": "12"}), ""),
                          (play({"t": 20, "scene": "scenes/Yard.tscn"}), "")]:
            with self.assertRaisesRegex(ValueError, said, msg=json.dumps(bad["inputs"][-1])):
                task_with(probe(play=bad))

    def test_a_judge_counts_its_plays_named_shots_in_its_twenty(self):
        def judge(plays, shots=5):
            return {"kind": "judge", "name": "looks", "required": False, "question": "Does it read?",
                    "rubric": [{"key": "reads", "criterion": "It reads."}], "plays": plays, "shots": shots}
        task_with(probe(), judge([self.TOUR], shots=18))
        with self.assertRaisesRegex(ValueError, "and 2 named ones"):
            task_with(probe(), judge([self.TOUR], shots=19))
