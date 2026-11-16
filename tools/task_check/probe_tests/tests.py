"""The probe tests' plays and what each must read (README.md). A play is plays/<name>.json, a spec without `format`,
`out` and `size`, each query with an id of its own; its check reads what the play wrote."""

import math
import struct


class Checks:
    """What a play's check found: (passed, what) of every check."""

    def __init__(self):
        self.done = []

    def true(self, what, passed, got=None):
        self.done.append((bool(passed), what if passed or got is None else f"{what}: got {got!r}"))

    def fail(self, what):
        self.done.append((False, what))

    def eq(self, what, got, want):
        self.done.append((got == want, what if got == want else f"{what}: got {got!r}, want {want!r}"))

    def near(self, what, got, want, within):
        ok = isinstance(got, int | float) and not isinstance(got, bool) and math.isfinite(got) and abs(got - want) <= within
        self.done.append((ok, what if ok else f"{what}: got {got!r}, want {want} +- {within}"))


def samples(found, qid):
    return ((found["probe"] or {}).get("measures") or {}).get(qid) or []


def at(found, qid, t):
    """The sample of a query nearest play time `t`."""
    return min(samples(found, qid), key=lambda s: abs(s["t"] - t), default={})


def rows(found, qid, t):
    return at(found, qid, t).get("rows") or []


def row(found, qid, t, name=None):
    return next((r for r in rows(found, qid, t) if name is None or r.get("name") == name), {})


def value(found, qid, t):
    return at(found, qid, t).get("value") or {}


def texts(found, qid, t):
    return [r.get("text") for r in rows(found, qid, t)]


def track(found, t):
    return min((found["probe"] or {}).get("track") or [[0]], key=lambda r: abs(r[0] - t))


def errors(found):
    return (found["probe"] or {}).get("query_errors") or []


def png_size(data):
    """(width, height) of a PNG file's bytes, and its colour type (2: RGB without alpha)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height, _, colour = struct.unpack(">IIBB", data[16:26])
    return width, height, colour


def ended(c, found, seconds, reason="time"):
    probe = found["probe"]
    c.true("the play wrote probe.json", probe is not None)
    if probe is None:
        c.true("the engine's log has no script error", "SCRIPT ERROR" not in found["log"], found["log"][-1500:])
        return False
    c.eq("exit code", found["code"], 0)
    c.eq("format", probe.get("format"), "godot-probe/1")
    c.eq("ended", probe.get("ended"), reason)
    c.near("seconds", probe.get("seconds"), seconds, 0.2)
    c.true("the engine's log has no script error", "SCRIPT ERROR" not in found["log"],
           found["log"][found["log"].find("SCRIPT ERROR"):][:600])
    c.true("probe.log is written", b"the play ended: " + reason.encode() in found["files"].get("probe.log", b""))
    return True


def check_keys(c, found):
    if not ended(c, found, 6.5 + (5 / 30 if not found["rendered"] else 0)):
        return
    probe = found["probe"]
    c.eq("the player", probe.get("player"), "Player")
    c.eq("the scene", probe.get("scene"), "res://scenes/Main.tscn")
    c.eq("inputs sent", probe.get("inputs_sent"), 19)
    c.near("the first sample is the clock's first frame", probe["track"][0][0], 1 / 30, 1e-9)
    c.eq("samples every 0.5 s to the end", len(probe["track"]), 14)
    # W held from 1 s to 3 s at 4 m a second: forward is -z
    c.near("the player stands still before the key", track(found, 1.0)[3], 0.0, 0.01)
    c.near("W moves the player forward", track(found, 3.5)[3], -8.0, 0.4)
    c.near("the player's speed while W is held", row(found, "player", 2.0).get("speed"), 4.0, 0.05)
    c.near("its speed at rest", row(found, "player", 3.5).get("speed"), 0.0, 0.01)
    c.near("the teleport places it", track(found, 4.5)[1], 3.0, 0.01)
    c.near("the teleport turns it", row(found, "player", 4.5).get("yaw"), 90.0, 0.01)
    c.near("the hold keeps it", track(found, 5.0)[3], 3.0, 0.01)
    end = track(found, 6.5)
    c.near("teleport_to puts it 2 m from the crate", math.dist(end[1:4], [-6, 0.5, -3]), 2.0, 0.05)
    c.eq("a property of the player", row(found, "player", 1.0).get("prop:health"), 75)
    c.eq("a property by its script's file name", row(found, "player", 1.0).get("prop:player.health"), 75)
    c.near("a vector's part", row(found, "player", 1.0).get("prop:position.y"), 0.5, 1e-6)
    c.eq("a class alone: it holds one", row(found, "player", 1.0).get("prop:CollisionShape3D"), 1)
    c.eq("the player collides", row(found, "player", 1.0).get("collision"), 1)
    c.near("its drawn half-height", row(found, "player", 1.0).get("extent_y"), 0.5, 1e-4)
    c.eq("its class in the row", row(found, "player", 1.0).get("class"), "player")
    # selects
    c.eq("shown crates by their group", [r["name"] for r in rows(found, "crates", 1.0)], ["Crate1", "Crate2"])
    c.eq("hidden ones with inactive", [(r["name"], r["active"], r["hidden"]) for r in rows(found, "crates_all", 1.0)],
         [("Crate1", 1, 0), ("Crate2", 1, 0), ("Crate3", 0, 1)])
    c.near("a scaled crate's extent", row(found, "wide", 1.0).get("extent_x"), 1.0, 1e-4)
    c.near("its scale", row(found, "wide", 1.0).get("scale"), 4 / 3, 1e-4)
    c.eq("near a point on an object", sorted(r["name"] for r in rows(found, "near_crate", 1.0)), ["Crate1", "Crate2"])
    c.eq("has: simulating", [(r["name"], r["simulating"], r["collision"]) for r in rows(found, "ball", 1.0)], [("Ball", 1, 1)])
    # a class by its script: class_name, and a file name
    spinner = row(found, "spinner", 2.0)
    c.eq("a component by its class_name", (spinner.get("name"), spinner.get("class"), spinner.get("owner")),
         ("Spinner", "Spinner", "Main"))
    c.near("its spin", spinner.get("spin"), 90.0, 0.5)
    c.near("the object's spin", row(found, "spin_object", 2.0).get("spin"), 90.0, 0.5)
    c.eq("its script's variable", spinner.get("prop:turns"), 1)
    c.near("its extent", spinner.get("extent_x"), 0.5, 0.21)  # a turned box is wider, world-aligned
    coins = rows(found, "coins", 2.6)
    c.eq("nodes by their script's file name, kept by where", [r["name"] for r in coins], ["Coin1", "Coin2"])
    c.eq("a dictionary's entry", coins[0].get("prop:info.kind") if coins else None, "gold")
    c.eq("an array is its size", coins[0].get("prop:info.sides") if coins else None, 2)
    c.eq("an array's element", coins[0].get("prop:info.sides[1]") if coins else None, 2)
    c.eq("where keeps none", rows(found, "dear_coins", 2.6), [])
    made = value(found, "made", 6.5)
    c.eq("spawned over the play", made.get("spawned"), 6)
    c.eq("destroyed over the play (three are kept)", made.get("destroyed"), 3)
    c.eq("live effects", [r["name"] for r in rows(found, "effects", 1.0)], ["Sparks"])
    c.eq("particle nodes and whether they emit", [(r["name"], r["active"]) for r in rows(found, "particles", 1.0)],
         [("Sparks", 1), ("Spent", 0)])
    c.eq("parts by their mesh's name", [r["name"] for r in rows(found, "boxes_by_mesh", 1.0)],
         ["Body", "Crate1", "Crate2", "Spinner"])
    many = at(found, "many", 1.0)
    c.eq("200 rows are kept of 250 matches", (len(many.get("rows", [])), many.get("total")), (200, 250))
    c.eq("and every match is summed up", many.get("full"), {"x": {"n": 250, "nonzero": 249, "sum": 31125, "min": 0, "max": 249}})
    parts = row(found, "parts", 1.0)
    c.near("a part's forward", parts.get("forward:Camera.y"), -0.5, 1e-5)
    c.near("a part's pitch, by its class", parts.get("world_pitch:Camera3D"), -30.0, 1e-3)
    c.eq("a part's yaw against its object's", parts.get("rel_yaw:Camera"), 0)
    turned = row(found, "parts", 2.0).get("world_yaw:Spinner", 0) - parts.get("world_yaw:Spinner", 0)
    c.near("a part that turns a quarter of a turn a second", (turned + 180) % 360 - 180, 90.0, 0.1)
    c.eq("a button without an icon", (row(found, "pictures", 1.0).get("has_brush"), "value" in row(found, "pictures", 1.0)), (0, False))
    # camera, lights
    cam = probe["camera"][0]
    c.near("the camera's place", math.dist(cam[1:4], [0, 6, 8]), 0.0, 1e-4)
    c.near("its pitch (down is negative)", cam[4], -30.0, 1e-3)
    c.near("its fov", cam[6], 60.0, 1e-4)
    c.eq("the player is on screen and in view", (value(found, "cam", 1.0).get("player_on_screen"), value(found, "cam", 1.0).get("occluded")),
         (1, 0))
    c.near("a view turn: the camera's pitch", probe["camera"][-1][4], -10.0, 1e-3)
    c.near("and its yaw", probe["camera"][-1][5], 45.0, 1e-3)
    c.near("the player's yaw", row(found, "player", 6.5).get("yaw"), 45.0, 1e-3)
    c.eq("lights that are on", [(r["name"], r["on"], r["intensity"]) for r in rows(found, "lights", 1.0)],
         [("Sun", 1, 1.5), ("Lamp", 0, 0)])
    # widgets and ui
    health = row(found, "health", 1.0)
    c.eq("a bar's percent and value", (health.get("percent"), health.get("value"), health.get("visible")), (0.75, 75, 1))
    c.near("its width in the frame", health.get("w"), 400 / 1920, 1e-4)
    c.eq("a label's text", row(found, "count", 1.0).get("text"), "TAPS 0")
    button = row(found, "button", 1.0)
    c.eq("a button", (button.get("name"), button.get("text"), button.get("interactable")), ("TapButton", "TAP", 1))
    c.near("its place in the frame", button.get("x", 0) + button.get("w", 0) / 2, 0.8906, 1e-3)
    c.eq("a widget click presses it", row(found, "count", 3.5).get("text"), "TAPS 1")
    c.eq("the cursor and the left button press it", row(found, "count", 4.0).get("text"), "TAPS 2")
    c.true("the wheel turns twice", "ZOOM 2" in texts(found, "texts", 2.0), texts(found, "texts", 2.0))
    c.true("a gamepad button", "PAD 0" in texts(found, "texts", 5.0), texts(found, "texts", 5.0))
    c.true("the saved data is cleared before a play", "VISITS 1" in texts(found, "texts", 1.0), texts(found, "texts", 1.0))
    c.eq("a hidden widget", (row(found, "secret", 3.5).get("visible"), row(found, "secret", 4.5).get("visible")), (0, 1))
    c.true("hidden text is not on screen", "SECRET 42" not in texts(found, "texts", 3.5))
    c.true("shown text is", "SECRET 42" in texts(found, "texts", 4.5))
    c.eq("boxes on screen", sorted(r["name"] for r in rows(found, "boxes", 1.0)), ["FireButton", "Health", "TapButton"])
    c.eq("with the panel shown", sorted(r["name"] for r in rows(found, "boxes", 4.5)),
         ["FireButton", "Health", "Secret", "TapButton"])
    c.eq("text in a rect", texts(found, "top_left", 1.0), ["TAPS 0"])
    c.eq("a ui row", {k: row(found, "texts", 1.0, "CountLabel").get(k) for k in ("class", "source", "kind", "text")},
         {"class": "Label", "source": "control", "kind": "text", "text": "TAPS 0"})
    # audio
    heard = value(found, "heard", 1.5)
    c.eq("one sound plays", (heard.get("count"), heard.get("audible"), heard.get("loudest"), heard.get("listener")),
         (1, 1, "music_loop", "Camera"))
    c.near("at its volume (-6 dB)", heard.get("volume"), 10 ** (-6 / 20), 1e-4)
    c.true("the mix is heard", (heard.get("level") or 0) > 0.01, heard.get("level"))
    c.eq("a sound that starts", sum(s["value"]["started"] for s in samples(found, "jump")), 1)
    c.eq("selected by its bus and its name", value(found, "music", 1.5).get("count"), 1)
    jump = max((s["value"] for s in samples(found, "jump")), key=lambda v: v["count"])
    # 4.47 m from the camera, unit size 4, inverse distance, max_db 3
    c.near("a placed sound's volume at the listener", jump.get("volume"), 4 / math.dist([0, 6, 4], [0, 6, 8]), 0.01)
    # the frame
    drawn = value(found, "drawn", 2.0)
    c.eq("a render sample's keys", sorted(drawn), ["draw_calls", "texture_mb", "triangles"])
    c.eq("inputs that didn't land", [(m["kind"], m["target"]) for m in probe.get("inputs_missed", [])],
         [("click", "NoSuchButton")])
    c.true("an unknown key is said", "inputs: the keyboard has no key nokey" in errors(found), errors(found))
    if found["rendered"]:
        c.eq("screenshots", probe.get("screenshots"), ["shot_00.png", "shot_end_view.png", "shot_01.png"])
    else:
        c.eq("no screenshot without a frame", probe.get("screenshots"), [])
        c.eq("no frame's brightness", at(found, "bright", 2.0).get("value", 0), None)


def check_touch(c, found):
    if not ended(c, found, 5.5):
        return
    probe = found["probe"]
    c.true("a tap on a named control presses it", "TAPS 1" in texts(found, "texts", 1.0), texts(found, "texts", 1.0))
    c.near("a drag pushes the stick over", row(found, "stick", 2.0).get("prop:stick.y"), -1.0, 1e-4)
    c.near("the player runs", row(found, "stick", 2.0).get("speed"), 4.0, 0.05)
    c.near("the finger lifts after its hold", row(found, "stick", 3.5).get("prop:stick.y"), 0.0, 1e-6)
    c.near("how far it went", track(found, 4.0)[3], -8.6, 0.4)
    c.true("a second finger's tap lands meanwhile", "FIRE 1" in texts(found, "texts", 2.0), texts(found, "texts", 2.0))
    c.true("the back button's request", "BACK 1" in texts(found, "texts", 4.0), texts(found, "texts", 4.0))
    c.true("and its key", "KEY BACK" in texts(found, "texts", 4.0), texts(found, "texts", 4.0))
    c.true("a control by its class", "FIRE 2" in texts(found, "texts", 5.5), texts(found, "texts", 5.5))
    c.eq("touches that didn't land", [(m["t"], m["kind"], m["target"]) for m in probe.get("inputs_missed", [])],
         [(3.8, "tap", "Nope"), (4.2, "tap", "0.400, 0.400")])
    c.true("a missed touch says why", all(m.get("why") for m in probe.get("inputs_missed", [])))
    c.eq("inputs sent", probe.get("inputs_sent"), 10)
    c.eq("no error", errors(found), [])


def check_second(c, found):
    if not ended(c, found, 5.5):
        return
    probe = found["probe"]
    c.true("the play's scene is opened", "SECOND SCENE" in texts(found, "texts", 1.0), texts(found, "texts", 1.0))
    c.near("a 2D player's place", track(found, 2.0)[1] - track(found, 1.0)[1], 100.0, 0.5)
    c.eq("its y and z", track(found, 2.0)[2:4], [200, 0])
    c.near("its speed", row(found, "walker", 2.0).get("speed"), 100.0, 0.5)
    c.eq("a 2D camera's row", probe["camera"][1][1:], [400, 300, 0, 0, 0, 0])
    c.eq("the 2D player is on screen", value(found, "cam", 1.0).get("player_on_screen"), 1)
    c.eq("a scene input loads another scene", (probe.get("scene"), probe.get("player")), ("res://scenes/Main.tscn", "Player"))
    c.true("its text shows", "TAPS 0" in texts(found, "texts", 3.5), texts(found, "texts", 3.5))
    c.eq("a scene the project lacks", [(m["kind"], m["target"]) for m in probe.get("inputs_missed", [])],
         [("scene", "res://scenes/None.tscn")])
    c.eq("and its error", errors(found), ["the scene res://scenes/None.tscn isn't in the project: no load"])


def check_errors(c, found):
    if not ended(c, found, 1.5):
        return
    probe = found["probe"]
    c.eq("the task's player select", probe.get("player"), "Ball")
    c.near("the track follows it", probe["track"][0][1], 6.0, 0.01)
    c.eq("query errors", errors(found), [
        "query 'a': unknown kind 'nope' (null values)",
        "objects b: no field glow",
        "objects b: no component type Lantren",
        "components c: the select names no component and no effect",
        "widgets d: the text regex ( doesn't compile",
        "spawns e: no component type Nope",
        "a query has a missing or repeated id 'e'",
        "inputs: no device for <Stick>/x",
    ])
    c.eq("an unknown kind has null values", at(found, "a", 0).get("value", 0), None)
    c.eq("an unknown class has no rows", rows(found, "b", 0), [])
    c.eq("a class that can't be has no value", at(found, "e", 0).get("value", 0), None)
    c.eq("a row that is no input is left out", probe.get("inputs_sent"), 1)
    c.eq("the player through its select", [(r["name"], r["simulating"]) for r in rows(found, "f", 0)], [("Ball", 1)])


def check_refuse(c, found):
    c.eq("exit code", found["code"], 2)
    c.eq("nothing is written", sorted(found["files"]), [])
    c.true("the log says why", "TaskProbe: the play spec" in found["log"] and "its format isn't godot-probe-play/1" in found["log"],
           found["log"][-600:])


def check_idle(c, found):
    c.eq("exit code", found["code"], 0)
    c.eq("without the flag nothing is written", (sorted(found["files"]), found["out"].exists()), ([], False))
    c.true("the engine's log has no script error", "SCRIPT ERROR" not in found["log"], found["log"][-600:])


def check_shutdown(c, found):
    if not ended(c, found, 2.0, "shutdown"):
        return
    c.true("the samples up to the quit are kept", len(found["probe"]["track"]) >= 4, len(found["probe"]["track"]))


def check_wait(c, found):
    if not ended(c, found, 2.5):
        return
    c.true("a wait takes its real time", found["seconds"] >= 1.0, found["seconds"])
    c.eq("the clock held: no sample is missing or added", [round(r[0], 2) for r in found["probe"]["track"]],
         [0.03, 0.5, 1.0, 1.5, 2.0, 2.5])
    c.true("probe.log says so", b"the wait is over" in found["files"].get("probe.log", b""))


def check_frame(c, found):
    if not ended(c, found, 3.5):
        return
    probe = found["probe"]
    width, height = found["size"]
    c.eq("screenshots", probe.get("screenshots"), ["shot_00.png", "shot_01.png", "shot_moved.png"])
    for name in probe.get("screenshots", []):
        c.eq(f"{name} is exactly the frame's size, without alpha", png_size(found["files"].get(name, b"")), (width, height, 2))
    c.eq("no error", errors(found), [])
    c.true("a tap on a named control lands", "TAPS 1" in texts(found, "texts", 1.0), texts(found, "texts", 1.0))
    c.near("the stick moves the player", track(found, 2.5)[3], -4.6, 0.5)
    drawn = value(found, "drawn", 2.0)
    c.true("draw calls are counted", (drawn.get("draw_calls") or 0) > 0, drawn)
    c.true("triangles are counted", (drawn.get("triangles") or 0) >= 12, drawn)
    c.true("texture memory is read", (drawn.get("texture_mb") or 0) > 0, drawn)
    bright = value(found, "bright", 2.0)
    c.true("the frame's brightness is read", 0.005 < (bright.get("luminance") or 0) < 1 and 0.005 < (bright.get("luma") or 0) < 1, bright)
    c.eq("at the frame's size", bright.get("size"), [width, height])
    button = row(found, "button", 1.0)
    c.near("the button's width in the frame", button.get("w"), 300 / (1920 if width > height else 1080), 1e-3)
    c.eq("the player is on screen and in view", (value(found, "cam", 1.0).get("player_on_screen"), value(found, "cam", 1.0).get("occluded")),
         (1, 0))


PLAYS = {
    "keys": {"check": check_keys},
    "touch": {"check": check_touch, "twice": True},
    "second": {"check": check_second, "twice": True},
    "errors": {"check": check_errors},
    "refuse": {"check": check_refuse, "spec": "wait", "format": "other-probe-play/1"},
    "idle": {"check": check_idle, "spec": "wait", "flag": False, "engine_args": ["--quit-after", "30"]},
    "shutdown": {"check": check_shutdown, "args": ["-quitAt", "2"]},
    "wait": {"check": check_wait},
    "frame": {"check": check_frame, "rendered": True},
}
