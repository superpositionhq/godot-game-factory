"""The probe tests' plays and what each must read (README.md). A play is plays/<name>.json, a spec without `format`,
`out` and `size`, each query with an id of its own; its check reads what the play wrote."""

import math
import re
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
    c.true("the probe loads first and the game keeps its saved data in the copy's own folder, whatever lines of the "
           "game's project.godot would stand in for the probe's", re.search(
               r"^ORDER probe_first=true user_dir=.*[/\\]TaskProbe\.[0-9a-f]{12}\s*$", found["log"], re.M),
           [line for line in found["log"].splitlines() if line.startswith("ORDER")])
    c.true("an autoload the game sets before every section still loads, after the probe",
           re.search(r"^EARLY loaded after_probe=true\s*$", found["log"], re.M),
           [line for line in found["log"].splitlines() if line.startswith("EARLY")])
    c.eq("the player", probe.get("player"), "Player")
    c.eq("the scene", probe.get("scene"), "res://scenes/Main.tscn")
    c.eq("inputs sent", probe.get("inputs_sent"), 20)
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
    c.near("an object that draws nothing (a light) has an extent of 0, never no value",
           row(found, "lamp_object", 1.0).get("extent_x"), 0.0, 1e-9)
    c.near("a component with no box of its own (a light) has an extent of 0",
           row(found, "lamp_part", 1.0).get("extent_y"), 0.0, 1e-9)
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
    c.eq("a button drawn fully transparent is not on screen to widgets, and exists with visible false",
         (rows(found, "ghost_shown", 1.0), row(found, "ghost", 1.0).get("visible")), ([], 0))
    c.eq("a click still reaches it, as a player's does", (row(found, "ghost", 5.0).get("text"),
                                                          row(found, "ghost", 6.0).get("text")), ("GHOST", "PRESSED"))
    c.true("probe.log says it was clicked", "clicked GhostButton (Button)" in found["files"].get("probe.log", b"").decode(
        "utf-8", "replace"))
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
    c.eq("each miss is a line of the play's errors", errors(found),
         ["inputs: the tap at 3.80 s missed: no visible widget matches 'Nope'",
          "inputs: the tap at 4.20 s missed: finger 2 is still down from an earlier touch"])


def check_captions(c, found):
    if not ended(c, found, 8.5):
        return
    probe = found["probe"]
    game_log = found["log"][:len(found["log"]) - len(found["output"])]  # the log file alone (its output echoes it)
    pressed = re.findall(r"^PRESSED (\w+)", game_log, re.M)
    note = found["files"].get("probe.log", b"").decode("utf-8", "replace")
    c.eq("each control the play named by its shown text is pressed once, in the order sent, and each control of the "
         "scrolled list it names, scrolled into view first when it is out of it, but the disabled one", pressed,
         ["Button2", "Start", "AgainLow", "AgainHigh", "PlayNow", "Button4", "ListTop", "PanelTop", "ListBottom",
          "PanelBottom", "Zh", "ZhLoose", "ZhTap", "ListEdge", "ListEdge", "ListBottom", "ListBottom", "ListBottom"])
    scrolled = re.findall(r"scrolled (.+?) to show (\w+) \((\w+)\) for the (click|tap) on '([^']+)'", note)
    c.eq("a click on a control out of the list's view scrolls the list to it first, the least way: one wholly out of "
         "view below or above (found off the frame too), one partly in view whose centre is out of it, a disabled "
         "button, a caption read on a button partly in view; one in view scrolls nothing",
         scrolled, [("List (ScrollContainer)", "ListBottom", "Button", "click", "ListBottom"),
                    ("List (ScrollContainer)", "PanelBottom", "Panel", "click", "PanelBottom"),
                    ("List (ScrollContainer)", "ListEdge", "Button", "click", "ListEdge"),
                    ("List (ScrollContainer)", "ListBottom", "Button", "click", "ListBottom"),
                    ("List (ScrollContainer)", "Bolted", "Button", "click", "Bolted"),
                    ("List (ScrollContainer)", "ListBottom", "Button", "click", "Bottom Row")])
    c.true("then the click lands on it, and a tap on a control the list shows scrolls nothing",
           "clicked ListBottom (Button) by name" in note and "clicked PanelBottom (Panel) by name" in note
           and "clicked ListEdge (Button) by name" in note and 'clicked ListEdge (Button) by its caption "Edge Row"' in note
           and 'clicked ListBottom (Button) by its caption "Bottom Row"' in note
           and "tap: finger 1 goes down on ListBottom (Button) by name" in note, note[-3000:])
    c.true("a click by a caption, whatever its case and spacing: probe.log says how it was found",
           'clicked Button2 (Button) by its caption "Begin Run"' in note, note[-1500:])
    c.true("a name wins over another button's caption", "clicked Start (Button) by name" in note, note[-1500:])
    c.true("a caption as written wins over one that reads it alike, with no note",
           'clicked AgainLow (Button) by its caption "Again"' in note
           and "buttons read 'Again'" not in note, note[-1500:])
    c.true("of two that read it alike (none as written), the first in reading order, noted",
           "click: 2 buttons read 'again'; took the first in reading order" in note
           and 'clicked AgainHigh (Button) by its caption "  AGAIN!"' in note, note[-1500:])
    c.true("a label on a button with no text of its own is its caption",
           'clicked PlayNow (TextureButton) by its caption "Play  Now"' in note, note[-1500:])
    c.true("a tap by a caption", 'finger 0 goes down on Button4 (Button) by its caption "Tap Me"' in note, note[-1500:])
    c.true("a button and a panel in a list's view are clicked", "clicked ListTop (Button) by name" in note
           and "clicked PanelTop (Panel) by name" in note, note[-1500:])
    c.true("a Chinese caption as written", 'clicked Zh (Button) by its caption "开始游戏"' in note, note[-1500:])
    c.true("a Chinese caption read alike: its ideographs are letters, its middle dot a gap",
           'clicked ZhLoose (Button) by its caption "设置 · 声音"' in note, note[-1500:])
    c.true("a tap by a Chinese caption", 'finger 0 goes down on ZhTap (Button) by its caption "确定"' in note,
           note[-1500:])
    nothing = "no visible control that takes a click matches it, by name, class or caption"
    c.eq("text that isn't shown, no match and an optional click with no match (the probe sends it as any; the checker "
         "leaves its miss out) are misses of no control; a click on a button shown but disabled, marked `disabled` or "
         "not, is a miss that says so (the checker reads the marked one as landed), the list's one once it is scrolled "
         "to; none of them presses anything",
         [(m["t"], m["kind"], m["target"], m["why"]) for m in probe.get("inputs_missed", [])],
         [(2.5, "click", "hidden_word", nothing), (3.0, "click", "nothing_here", nothing),
          (4.5, "click", "maybe_later", nothing),
          (5.4, "click", "Locked Door", 'a button matches it (Locked (Button) by its caption "Locked Door"), shown but '
                                       "disabled: the click does nothing"),
          (5.7, "click", "Sealed", "a button matches it (Sealed (Button) by name), shown but disabled: the click does "
                                   "nothing"),
          (6.5, "click", "Bolted", "a button matches it (Bolted (Button) by name), shown but disabled: the click does "
                                   "nothing")])
    c.eq("inputs sent (a scrolled click counts once)", probe.get("inputs_sent"), 24)


SCROLLED_OUT = "scrolled out of its container's view: a press at its centre lands outside the view"
COVERED = "covered by another control"
NEVER = "its event never happened"
# the scrolls scene's buttons on screen once "Far Away" is scrolled to, and whether a press at the centre of each goes
# to something else (the widgets field `covered`)
COVERS = {"FarButton": 0.0, "Under": 1.0, "Veiled": 0.0, "Behind": 1.0, "Through": 1.0, "Free": 0.0, "Shut": 1.0,
          "Low": 1.0}


def covers(found, t):
    return {r["name"]: r.get("covered") for r in rows(found, "covers", t)}


def check_scrolls(c, found):
    if not ended(c, found, 8.5):
        return
    probe = found["probe"]
    game_log = found["log"][:len(found["log"]) - len(found["output"])]
    pressed = re.findall(r"^PRESSED (\w+)", game_log, re.M)
    took = re.findall(r"^TOOK (\w+)", game_log, re.M)
    note = found["files"].get("probe.log", b"").decode("utf-8", "replace")
    c.eq("pressed, in order: a button in a list inside a list (both scrolled to it), a tap's button scrolled out of the "
         "outer list's view, a button found by a caption the screen didn't show yet, a button under a see-through "
         "Control that takes no press (by the probe, then by a raw click), and a button once the dialog is gone",
         pressed, ["DeepButton", "OuterTop", "FarButton", "Veiled", "Veiled", "Free"])
    c.eq("a raw click at the centre of each button the probe found covered goes to what is over it (the engine's GUI "
         "agrees), and one while the exclusive dialog is up reaches nothing", took, ["Lid", "Glass", "Mesh", "Banner"])
    c.true("both lists scroll, the innermost first, to a button below the frame",
           "scrolled Inner (ScrollContainer), Outer (ScrollContainer) to show DeepButton (Button) for the click on "
           "'DeepButton'" in note and "clicked DeepButton (Button) by name" in note, note[-4000:])
    c.true("a tap scrolls the outer list back to its top button",
           "scrolled Outer (ScrollContainer) to show OuterTop (Button) for the tap on 'OuterTop'" in note
           and "tap: finger 0 goes down on OuterTop (Button) by name" in note, note[-4000:])
    c.true("a click by a caption the screen doesn't show yet scrolls to the button that shows it",
           "scrolled Outer (ScrollContainer) to show FarButton (Button) for the click on 'Far Away'" in note
           and 'clicked FarButton (Button) by its caption "Far Away"' in note, note[-4000:])
    c.eq("nothing else scrolls: not for a drag, nor behind a Control that only clips (alone, or round a list that could "
         "scroll to the button but not into it)", len(re.findall(r"^\S+ \[[^]]*\] scrolled ", note, re.M)), 3)
    for name, over, verb in (("Under", "Scrolls/Lid (Panel)", "clicked"), ("Behind", "Scrolls/Glass (Control)", "clicked"),
                             ("Through", "Scrolls/Mesh (Control)", "clicked"), ("Low", "Top/Banner (Panel)", "clicked"),
                             ("Free", "Scrolls/Modal (AcceptDialog)", "clicked"),
                             ("Behind", "Scrolls/Glass (Control)", "tapped")):
        c.true(f"probe.log names what is over {name} ({verb})",
               f"{name} (Button) matches '{name}', but {over} is over it: not {verb}" in note, note[-4000:])
    c.true("a disabled button something is over is covered, not shown but disabled",
           "Shut (Button) matches 'Shut', shown but disabled, and Scrolls/Shutter (Panel) is over it: not clicked" in note,
           note[-4000:])

    def out(name):
        return f"a control matches it ({name} (Button) by name), {SCROLLED_OUT}"

    c.eq("the misses: a drag on a control out of its list's view (a drag scrolls nothing), clicks and a tap on covered "
         "controls (an optional click, and a disabled click on a disabled button, too), clicks on controls a Control "
         "that only clips hides, and a click while an exclusive dialog is up",
         [(m["t"], m["kind"], m["target"], m["why"]) for m in probe.get("inputs_missed", [])],
         [(1.0, "drag", "OuterTop", out("OuterTop")), (2.5, "click", "Under", COVERED),
          (2.6, "click", "Under", COVERED), (3.0, "click", "Behind", COVERED), (3.2, "click", "Through", COVERED),
          (3.4, "click", "Low", COVERED), (3.6, "click", "Clipped", out("Clipped")),
          (3.8, "click", "Boxed", out("Boxed")), (4.0, "tap", "Behind", COVERED), (5.3, "click", "Free", COVERED),
          (7.0, "click", "Shut", COVERED)])
    c.eq("a touch's miss is a line of the play's errors, a click's isn't", errors(found),
         [f"inputs: the drag at 1.00 s missed: {out('OuterTop')}", f"inputs: the tap at 4.00 s missed: {COVERED}"])
    c.eq("inputs sent (a scrolled click or tap counts once)", probe.get("inputs_sent"), 36)
    c.eq("covered: 1 under a panel, a Control that draws nothing, one that passes the press on, a higher canvas "
         "layer's panel (a disabled button too); 0 under one that takes no press and with nothing over it",
         covers(found, 4.5), COVERS)
    c.eq("covered while the exclusive dialog is up: every button", covers(found, 5.5), {n: 1.0 for n in COVERS})
    c.eq("and once it is gone, as before", covers(found, 6.5), COVERS)


def check_events(c, found):
    if not ended(c, found, 4.5 + 5 / 30):  # headless: the shots wait for a drawn frame that never comes
        return
    probe = found["probe"]
    note = found["files"].get("probe.log", b"").decode("utf-8", "replace")
    # Space at 1.0 s (frame 30): the banner shows 20 frames on (frame 49), the score counts from the frame after
    seen = next((s["t"] for s in samples(found, "banner") if s.get("rows")), None)
    c.true("the samples show the banner first in the sample at or after 1.63 s, no later than one sampling step "
           f"({seen})", isinstance(seen, float) and 49 / 30 - 1e-6 <= seen < 49 / 30 + 0.1 + 1e-6)
    # the score reads n - 49 in frame n: 0.2 s after the banner's first sample (1.7 s, frame 51) is frame 57
    later = row(found, "score", (seen or 0) + 0.2).get("prop:score")
    c.eq("the score 0.2 s after that sample (what a since window [0.2, ...] reads first)", later, 8)
    for shot, at, said in (("win", "1.63", "count reads 1.0"), ("five", "1.80", "text reads 1.0"),
                           ("ten", "1.97", "prop:score reads 10.0"), ("already", "2.50", "visible reads 1.0")):
        c.true(f"the shot {shot} is taken in the frame its event comes ({at} s)",
               f"the shot {shot}'s event: {said}\n" in note and f"screenshot shot_{shot}.png at {at} s" in note,
               note[-3000:])
    c.true("no shot is taken for an event that never comes",
           "screenshot shot_lost.png" not in note and "screenshot shot_late.png" not in note, note[-3000:])
    c.eq("an event that never comes is a miss: once its `within` is over, or at the play's end",
         [(m["t"], m["kind"], m["target"], m["why"]) for m in probe.get("inputs_missed", [])],
         [(0.5, "shot_when", "lost", NEVER), (2.0, "shot_when", "late", NEVER)])
    c.true("the miss of the one with `within` comes when it is over (1.5 s), not at the play's end",
           re.search(r"^1\.53 \[[^]]*\] missed: shot_when lost at 0\.50 s", note, re.M), note[-3000:])
    c.eq("inputs sent", probe.get("inputs_sent"), 8)
    c.eq("no error but the headless frame's", [e for e in errors(found)
                                              if not e.startswith("the play's last frames weren't drawn")], [])


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
    target = row(found, "target", 2.0)
    # the walker is at x 200 when the pin lands (it walks 100 units a second from 100): ahead is its +X
    c.near("a 2D pin: ahead of the player along its +X, plus the offset", math.dist([target.get("x", 0), target.get("y", 0)],
                                                                                  [250, 210]), 0.0, 4.0)
    c.near("a 2D node isn't turned", target.get("roll"), math.degrees(0.5), 1e-3)
    c.eq("it is held there", (row(found, "target", 1.5).get("x"), row(found, "target", 1.5).get("y")),
         (target.get("x"), target.get("y")))
    c.eq("a scene input loads another scene", (probe.get("scene"), probe.get("player")), ("res://scenes/Main.tscn", "Player"))
    c.true("its text shows", "TAPS 0" in texts(found, "texts", 3.5), texts(found, "texts", 3.5))
    c.eq("a scene the project lacks", [(m["kind"], m["target"]) for m in probe.get("inputs_missed", [])],
         [("scene", "res://scenes/None.tscn")])
    c.eq("and its error", errors(found), ["the scene res://scenes/None.tscn isn't in the project: no load"])


def check_contact(c, found):
    if not ended(c, found, 8.5):
        return
    probe = found["probe"]
    foe = lambda t: row(found, "foe", t)  # noqa: E731
    # set: a property at the start, a part of a colour on every match, a class first
    c.eq("a property before it is set", foe(0.4).get("prop:health"), 100)
    c.eq("set writes it on the nearest match where holds for", foe(0.7).get("prop:health"), 30)
    c.eq("the dead one keeps its own", row(found, "corpse", 0.7).get("prop:health"), 100)
    c.eq("a colour's part, on every match", (foe(0.7).get("prop:tint.r"), row(found, "corpse", 0.7).get("prop:tint.r")), (0.5, 0.5))
    c.eq("a class first: the node below that is of it", row(found, "guard", 0.7).get("prop:foe.shielded"), 1)
    # pin: ahead of the player at its own height, facing the player, its own script running on
    c.near("the foe walks before the pin", foe(0.9).get("x"), 6.0 + 2.0 * 0.9, 0.2)
    for t in (1.1, 2.0, 2.4):
        c.near(f"pinned 2 m ahead of the player at {t} s", math.dist([foe(t).get(k, 99) for k in "xyz"], [0, 0.5, -2]), 0.0, 1e-3)
    c.near("it faces the player", abs(foe(1.1).get("yaw", 0)), 180.0, 1e-3)
    c.eq("the player's own blow lands on it", (foe(1.4).get("prop:health"), foe(1.7).get("prop:health")), (30, 20))
    c.true("released, it walks on", foe(2.9).get("x", 0) > 0.5, foe(2.9).get("x"))
    # damage: through take_damage, from the object named or the player; what it returned; its own short stop
    c.eq("no stop before the hit", [s["rows"][0].get("frozen") for s in samples(found, "foe") if 2.75 <= s["t"] <= 3.0], [0, 0, 0])
    c.eq("the first sample has no stop to read", "frozen" in foe(0.0), False)
    c.eq("a hit from a named object", (foe(3.1).get("prop:health"), foe(3.1).get("prop:last_source"), foe(3.1).get("damage_taken")),
         (19, "Post", 1))
    stops = [s["rows"][0].get("frozen", 0) for s in samples(found, "foe") if 3.05 <= s["t"] <= 3.45]
    c.near("its stop of 0.2 s is read once it ends, a spark coming and going below it meanwhile", max(stops), 0.2, 0.04)
    c.eq("and only then", sum(1 for v in stops if v), 1)
    stops = [s["rows"][0].get("frozen", 0) for s in samples(found, "foe") if 4.05 <= s["t"] <= 4.45]
    c.near("a stop of the game's time (a time scale of 0 for four frames) stops it too", max(stops), 4 / 30, 0.04)
    c.eq("a hit from the player", (foe(3.6).get("prop:health"), foe(3.6).get("prop:last_source"), foe(3.6).get("damage_taken")),
         (4, "Player", 16))
    c.eq("a hit that takes less than asked", (foe(4.7).get("prop:health"), foe(4.7).get("prop:dead"), foe(4.7).get("damage_taken")),
         (0, 1, 20))
    c.eq("a shielded one takes nothing, through the node below it", row(found, "guard", 4.8).get("damage_taken"), 0)
    c.eq("an object no stage struck has no damage to read", "damage_taken" in row(found, "post", 4.8), False)
    c.eq("a take_damage with a third argument of its own", (row(found, "dummy", 4.9).get("damage_taken"),
                                                            row(found, "dummy", 4.9).get("prop:hits")), (2, 1))
    hero = row(found, "player", 5.2)
    c.eq("the player struck, by the nearest other that can be hurt",
         (hero.get("prop:health"), hero.get("prop:last_source"), hero.get("damage_taken")), (70, "Foe", 5))
    # world: the lowest time scale, whether the game went on, and a pause, between samples too
    scale = {round(s["t"], 1): s["value"]["time_scale"] for s in samples(found, "world")}
    flow = {round(s["t"], 1): s["value"]["flow"] for s in samples(found, "world")}
    c.eq("the game runs at its pace", {(scale.get(t), flow.get(t)) for t in (1.0, 4.9, 5.3, 8.0)}, {(1, 1)})
    c.eq("a hit slows it for three frames, read in the sample after", (scale.get(5.1), flow.get(5.1)), (0.25, 0.25))
    c.eq("a stop by a time scale of 0: both read 0", (scale.get(4.1), flow.get(4.1)), (0, 0))
    paused = {round(s["t"], 1): s["value"]["paused"] for s in samples(found, "world")}
    c.eq("a pause of six frames", [t for t in sorted(paused) if paused[t]], [5.5, 5.6, 5.7])
    c.eq("a stop by a pause: the game holds, its time scale stays 1",
         {(scale.get(t), flow.get(t)) for t in (5.5, 5.6, 5.7)}, {(1, 0)})
    c.eq("a stopped time is no pause", paused.get(4.1), 0)
    # pin at a point
    c.near("pinned at a point and an offset", math.dist([row(found, "post", 6.4).get(k, 99) for k in "xyz"], [3, 1, 0]), 0.0, 1e-3)
    c.eq("every node but the player", [r["name"] for r in rows(found, "others", 1.0)], ["Corpse", "Foe", "Hurtbox"])
    c.eq("stages that didn't land", [(m["t"], m["kind"], m["target"]) for m in probe.get("inputs_missed", [])], [
        (0.6, "set", "armour"), (0.6, "set", "health"), (0.6, "set", "health"), (0.6, "set", "locked"),
        (4.8, "damage", "Lamp"), (6.5, "pin", '{"player":true}'),
        (6.5, "pin", '{"name":"Post"}'), (6.5, "damage", "Post"), (6.5, "damage", '{"name":"Nobody"}')])
    c.true("a missed stage says why", all(m.get("why") for m in probe.get("inputs_missed", [])))
    c.eq("inputs sent", probe.get("inputs_sent"), 26)
    c.eq("no error", errors(found), [])


def heard(found, qid, t0, t1):
    """(started_audible, the names of the starts in order, how many players were found newly playing: `started`) of a
    query's samples after t0 up to t1."""
    picked = [s["value"] for s in samples(found, qid) if t0 < s["t"] <= t1 + 1e-6 and s["value"]]
    starts = sorted((r for v in picked for r in v["starts"]), key=lambda r: r["t"])
    return sum(v["started_audible"] for v in picked), [r["sound"] for r in starts], sum(v["started"] for v in picked)


def sound_totals(found):
    """What two plays of the sounds must agree on: every start, by name, and how many were audible."""
    return heard(found, "all", 0, 99)[:2]


def check_sounds(c, found):
    if not ended(c, found, 10.5):
        return
    every = lambda t0, t1: heard(found, "all", t0, t1)  # noqa: E731
    c.eq("nothing starts before a key", every(0, 1.0), (0, [], 0))
    c.eq("one-shots that start and end between two samples", every(1.0, 1.5), (3, ["shot_a", "shot_a", "shot_b"], 3))
    c.eq("none plays at the samples around them", [s["value"]["count"] for s in samples(found, "all") if s["t"] <= 2.0],
         [0, 0, 0, 0, 0])
    c.eq("a sound shorter than a frame", every(2.0, 2.5)[:2], (1, ["tick"]))
    c.eq("a placed sound out of earshot starts unheard", every(3.0, 3.5), (0, ["far"], 1))
    c.eq("a 3D player played again while it plays: two starts, found newly playing once", every(3.5, 4.0),
         (2, ["close", "close"], 1))
    c.eq("one on a muted bus, one on a bus that sends to it: neither is heard", every(4.0, 4.5), (0, ["hush", "muffle"], 2))
    c.eq("played again in the next frame, and again", every(5.0, 5.5), (3, ["long", "long", "long"], 1))
    last = [r for s in samples(found, "all") if 6.0 < s["t"] <= 6.5 for r in s["value"]["starts"]]
    c.eq("a stream without a name", [(r["sound"], r["named"]) for r in last], [("", False)])
    takes = [r for s in samples(found, "all") if 6.5 < s["t"] <= 7.0 for r in s["value"]["starts"]]
    c.eq("a player that picks a take, played three times while it plays: three starts, none with a name to tell it by",
         [(r["sound"], r["named"]) for r in takes], [("takes", False)] * 3)
    c.eq("a looping sound played again while it plays", every(7.5, 8.5), (2, ["hum", "hum"], 1))
    c.eq("a pause and its end start nothing; the player is found newly playing after it", every(8.5, 9.0), (0, [], 1))
    c.eq("a player of voices starts once: its voices are not seen", every(9.0, 9.5)[:2], (1, [""]))
    c.eq("and the samples say so", [bool(s["value"].get("voices_unseen")) for s in samples(found, "all") if s["t"] > 8.9],
         [False, True, True, True])
    c.eq("every start of the play, each once", every(0, 99)[:2], (16, [
        "shot_a", "shot_a", "shot_b", "tick", "far", "close", "close", "hush", "muffle", "long", "long", "long", "",
        "takes", "takes", "takes", "hum", "hum", ""]))
    c.eq("the starts a sample lists are all of them", {s["value"]["starts_total"] - len(s["value"]["starts"])
                                                      for s in samples(found, "all")}, {0})
    c.eq("selected by their stream's name", heard(found, "shots", 0, 99)[:2], (3, ["shot_a", "shot_a", "shot_b"]))
    c.eq("near a point: the sounds that start there", heard(found, "there", 0, 99), (0, ["far"], 1))
    c.eq("by their owner", heard(found, "placed", 0, 99), (0, ["far"], 1))
    c.eq("by their bus", heard(found, "muted", 0, 99), (0, ["hush"], 1))
    c.eq("by an owner above a player that frees itself, a sound shorter than a frame", heard(found, "ticks", 0, 99)[:2],
         (1, ["tick"]))
    c.eq("near a point that isn't there: no value", {s["value"] for s in samples(found, "nowhere")}, {None})
    c.eq("no error", errors(found), [])


LAMPS = ["LightLamp", "RedLamp", "EmissiveLamp", "UnshadedLamp", "BrightTextureLamp", "BlackTextureLamp", "ParticleLamp",
         "Smoke", "ShaderLamp", "ShaderDark", "ShaderAndLight", "Plain", "HiddenLamp", "ShellLamp", "FadedLamp",
         "HeldLamp", "QuietLamp", "PulseLamp", "PostLamp", "PostDark", "OverrideDark", "BlueLamp", "Lamp2D"]
# what each reads when the lamps are on, where a frame is drawn; headless, DRAWN have no value
LIT = {"LightLamp": 1, "RedLamp": 1, "EmissiveLamp": 1, "UnshadedLamp": 1, "BrightTextureLamp": 1, "BlackTextureLamp": 0,
       "ParticleLamp": 1, "Smoke": 0, "ShaderLamp": 1, "ShaderDark": 0, "ShaderAndLight": 1, "Plain": 0, "HiddenLamp": 0,
       "ShellLamp": 1, "FadedLamp": 1, "HeldLamp": 0, "QuietLamp": 0, "PulseLamp": 1, "PostLamp": 1, "PostDark": 0,
       "OverrideDark": 0, "BlueLamp": 1, "Lamp2D": 1}
# the lamps whose light only a drawing tells: those with a shader of their own always, the textured ones while on
SHADERS = ["ShaderLamp", "ShaderDark", "PulseLamp", "PostLamp", "PostDark", "OverrideDark", "BlueLamp"]
DRAWN = SHADERS + ["BrightTextureLamp", "BlackTextureLamp"]


def lamps_lit(found):
    """What two plays of the lamps must agree on: which read lit, off and on."""
    return [{n: row(found, "lamps", t, n).get("lit") for n in LAMPS} for t in (1.0, 3.0, 4.0)]


def check_lamps(c, found):
    """`lit`, `glow` and `has.lit`. Headless, a part whose light only a drawing tells has no value; rendered
    (`lamps_drawn`), it is drawn alone in a room without light and reads lit or dark."""
    if not ended(c, found, 4.5):
        return
    drawn = found["rendered"]

    def lamp(t, name, field):
        return row(found, "lamps", t, name).get(field)

    c.eq("the lamps", [r["name"] for r in rows(found, "lamps", 1.0)], LAMPS)
    dark = {n: (None if n in SHADERS and not drawn else 0) for n in LAMPS}
    dark["ShaderAndLight"] = 0 if drawn else None
    c.eq("off: none is lit" + ("" if drawn else "; one with a shader of its own can't be read without a frame"),
         {n: lamp(1.0, n, "lit") for n in LAMPS}, dark)
    lit = {n: (LIT[n] if drawn or n not in DRAWN else None) for n in LAMPS}
    c.eq("on: a lamp reads lit whatever makes its light" + (
        ": a Light, an emissive or an unshaded material, a next pass, an effect, and drawn alone a shader of its own "
        "or a texture; what is hidden, faded out or never drawn doesn't"
        if drawn else "; what only a drawing tells has no value in a play that draws nothing"),
         {n: lamp(3.0, n, "lit") for n in LAMPS}, lit)
    c.near("a Light's glow: its energy times its colour's luminance", lamp(3.0, "LightLamp", "glow"), 2.0, 1e-6)
    c.near("a red one's", lamp(3.0, "RedLamp", "glow"), 1.5 * 0.2126, 1e-4)
    c.near("an emissive box of 2 m: its energy times a quarter of its surface", lamp(3.0, "EmissiveLamp", "glow"), 3 * 6.0, 1e-4)
    c.near("an unshaded box of 1 m", lamp(3.0, "UnshadedLamp", "glow"), 1.5, 1e-4)
    c.near("a next pass that gives the light", lamp(3.0, "ShellLamp", "glow"), 1.5, 1e-4)
    c.eq("a lamp faded out reads dark, faded in lit", (lamp(1.0, "FadedLamp", "glow"), lamp(3.0, "FadedLamp", "glow")), (0, 1.5))
    c.eq("a light under a hidden holder, an editor's light, a mesh on no layer and one that only casts a shadow: none lights",
         [(lamp(3.0, n, "lit"), lamp(3.0, n, "glow")) for n in ("HeldLamp", "QuietLamp")], [(0, 0), (0, 0)])
    c.eq("a part read by drawing it has no amount", ["glow" in row(found, "lamps", 3.0, n) for n in
                                                    ("BrightTextureLamp", "ShaderLamp")], [False, False])
    c.eq("an effect's amount isn't known", "glow" in row(found, "lamps", 3.0, "ParticleLamp"), False)
    if drawn:  # its shader is lit too, by an amount no drawing gives
        c.eq("a Light beside a part lit as drawn: lit, the sum not known", "glow" in row(found, "lamps", 3.0, "ShaderAndLight"),
             False)
    else:
        c.near("a Light beside what a drawing tells still says", lamp(3.0, "ShaderAndLight", "glow"), 1.0, 1e-6)
    c.near("a 2D light", lamp(3.0, "Lamp2D", "glow"), 1.0, 1e-6)
    how = "drawn" if drawn else "unread"
    read = {n: row(found, "lamps", 3.0, n).get("glow_read") for n in LAMPS}
    c.eq("how each was read", read, {**{n: "props" for n in LAMPS}, **{n: how for n in DRAWN}, "ShaderAndLight": how,
                                     "HiddenLamp": None, "Lamp2D": None})
    c.eq("what lit it", {n: row(found, "lamps", 3.0, n).get("glow_sources") for n in
                         ("LightLamp", "EmissiveLamp", "UnshadedLamp", "ShellLamp", "ParticleLamp", "Smoke", "ShaderAndLight")},
         {"LightLamp": "light", "EmissiveLamp": "emissive", "UnshadedLamp": "unlit", "ShellLamp": "emissive",
          "ParticleLamp": "effect", "Smoke": None, "ShaderAndLight": "emissive,light" if drawn else "light"})
    c.eq("has lit: none while they are off", rows(found, "lit", 1.0), [])
    for t in (3.0, 3.5, 4.0):
        c.eq(f"has lit at {t} s: the lamps that are on, one whose light changes every frame among them",
             [r["name"] for r in rows(found, "lit", t)], [n for n in LAMPS if lit[n] == 1])
    bulbs = lambda t: [(r["owner"], r["lit"], r["on"]) for r in rows(found, "bulbs", t)]  # noqa: E731
    c.eq("a Light as a component, off", bulbs(1.0), [("LightLamp", 0, 0), ("RedLamp", 0, 0), ("ShaderAndLight", 0, 0),
                                                     ("Holder", 0, 0), ("QuietLamp", 0, 1)])
    c.eq("and on", bulbs(3.0), [("LightLamp", 1, 1), ("RedLamp", 1, 1), ("ShaderAndLight", 1, 1), ("Holder", 0, 0),
                                ("QuietLamp", 0, 1)])
    shades = {r["owner"]: (r.get("lit"), r.get("glow")) for r in rows(found, "shades", 3.0)}
    c.eq("a mesh as a component", {k: shades.get(k) for k in ("LightLamp", "EmissiveLamp", "ShaderLamp", "ShaderDark")},
         {"LightLamp": (0, 0), "EmissiveLamp": (1, 18), "ShaderLamp": (1 if drawn else None, None),
          "ShaderDark": (0 if drawn else None, 0 if drawn else None)})
    c.eq("an effect as a component", [(r["owner"], r.get("lit"), "glow" in r) for r in rows(found, "effects", 3.0)],
         [("ParticleLamp", 1, False), ("Smoke", 0, True)])
    c.eq("a node that is no source has neither", [("lit" in r, "glow" in r) for r in rows(found, "others", 3.0)], [(False, False)])
    if drawn:
        first = {n: lamp(1 / 30, n, "lit") for n in SHADERS}
        c.eq("a part drawn for the first time is read in the same sample (the frame's end tells)", first,
             {n: 0 for n in SHADERS})
        c.eq("a select that waits for a first drawing has no rows in that sample, and says so",
             (at(found, "lit", 1 / 30).get("pending"), at(found, "lit", 1.0).get("pending")), (True, None))
        c.eq("a light that changes every frame reads lit in every sample", [lamp(t, "PulseLamp", "lit") for t in
                                                                           (2.5, 3.0, 3.5, 4.0, 4.5)], [1] * 5)
        c.eq("no error", errors(found), [])
        said = [line.split("] ", 1)[-1] for line in found["files"].get("probe.log", b"").decode("utf-8", "replace").splitlines()
                if "] lit: " in line]
        notes = {n: [line for line in said if line.startswith(f"lit: {n}/Shade ")] for n in DRAWN}
        c.eq("a 10 cm band on a 4 m post is seen; the same post with a dark band reads no pixel at all",
             (notes["PostLamp"][-1].rsplit(", ", 1)[-1], notes["PostDark"][-1].split(": ", 2)[-1]),
             ("lit", "0 bright pixel(s), the brightest 0 of 255, dark"))
        c.eq("a shaded material with no emission gives exactly nothing in the room",
             [notes[n][0].split(": ", 2)[-1] for n in ("ShaderDark", "OverrideDark", "BlackTextureLamp")],
             ["0 bright pixel(s), the brightest 0 of 255, dark"] * 3)
        c.true("a pulsing lamp is noted when its answer changes, not at every drawing (%d note(s))" % len(notes["PulseLamp"]),
               len(notes["PulseLamp"]) == 2, notes["PulseLamp"])
        c.true("probe.log: " + " | ".join(line for line in said if "draw call" in line or "PostLamp" in line),
               sum("draw call" in line for line in said) == 1, said)
    else:
        c.eq("a play that draws nothing says why such a part has no value", errors(found), [
            "lit: a part whose light only a drawing tells (a shader of its own, a texture on its light) has no value: "
            "this play draws nothing (headless)"])


def check_lamps_reach(c, found):
    """An input that picks its object by its light, in a play that reads nothing else: the part is drawn in the
    frames before the input is sent."""
    if not ended(c, found, 3.5):
        return
    c.eq("no stage and no teleport missed", found["probe"].get("inputs_missed"), [])
    log = found["files"].get("probe.log", b"").decode("utf-8", "replace")
    c.true("the player goes to the lamp a shader lights", "teleported next to ShaderLamp" in log, log[-600:])
    c.true("and not before the lamps are on", "teleport_to skipped (no object matches)" in log, log[-600:])
    c.near("it stands 2 m from it", math.dist(track(found, 3.0)[1:4], [8.0, 0.0, 0.0]), 2.0, 0.05)


def check_crates(c, found):
    """A crate broken by hiding its whole mesh and showing its pieces, one broken by an animation of its lid and a
    bone of its rig, one left alone: changed, bounds_change, pose_change and spread."""
    if not ended(c, found, 4.5):
        return

    def crate(t, name, field):
        return row(found, "crates", t, name).get(field)

    names = ("HideCrate", "AnimCrate", "StillCrate")
    c.eq("the crates", [r["name"] for r in rows(found, "crates", 1.0)], list(names) + ["PushedCrate", "FreedCrate",
                                                                                        "PhysicsCrate"])
    c.eq("whole: none changed", [crate(t, n, "changed") for t in (1 / 30, 1.0) for n in names], [0] * 6)
    c.eq("whole: no part moved; a mesh with nothing below it has no pose",
         [(crate(1.0, n, "bounds_change"), crate(1.0, n, "pose_change")) for n in names], [(0, 0), (0, 0), (0, None)])
    c.eq("broken: hidden for pieces and played as an animation both read changed; the one left alone doesn't",
         [crate(3.0, n, "changed") for n in names], [1, 1, 0])
    c.near("the pieces flew 0.75 m apart: the furthest face of a part moved that far", crate(3.0, "HideCrate", "bounds_change"),
           0.75, 1e-4)
    c.near("the lid lifted 1 m", crate(3.0, "AnimCrate", "bounds_change"), 1.0, 1e-4)
    c.near("its pose: the lid's place in the crate and the rig's bone, 1 m each", crate(3.0, "AnimCrate", "pose_change"),
           2.0, 1e-4)
    c.near("the pieces' places in the crate", crate(3.0, "HideCrate", "pose_change"), 4 * 0.75 * math.sqrt(2), 1e-3)
    c.eq("spread whole: one drawn part, two, one", [crate(1.0, n, "spread") for n in names], [0, 0.5, 0])
    c.near("spread broken: the pieces' centres 2 m apart each way", crate(3.0, "HideCrate", "spread"), math.sqrt(8), 1e-4)
    c.near("and the lid 1.5 m above the body", crate(3.0, "AnimCrate", "spread"), 1.5, 1e-4)
    c.eq("a crate pushed whole reads changed, its spread unchanged",
         (crate(3.0, "PushedCrate", "changed"), crate(3.0, "PushedCrate", "spread")), (1, 0))
    c.eq("a crate freed has no row: changed can't see it go, count can",
         ([r["name"] for r in rows(found, "crates", 3.0)].count("FreedCrate"), len(rows(found, "freed", 1.0)),
          len(rows(found, "freed", 3.0))), (0, 1, 0))
    c.eq("a crate broken into rigid bodies: whole, it neither simulates nor changed",
         (crate(1.0, "PhysicsCrate", "simulating"), crate(1.0, "PhysicsCrate", "changed")), (0, 0))
    c.eq("broken, it simulates and changed", (crate(3.0, "PhysicsCrate", "simulating"), crate(3.0, "PhysicsCrate", "changed")),
         (1, 1))
    c.near("its pieces' layout, whole", crate(1.0, "PhysicsCrate", "spread"), math.sqrt(0.5), 1e-4)
    c.true("and spread apart once broken (%s m)" % crate(3.0, "PhysicsCrate", "spread"),
           (crate(3.0, "PhysicsCrate", "spread") or 0) > 3.0)
    c.eq("no error", errors(found), [])


def check_field(c, found):
    """ground, pieces, a sign in the 3D world as ui text, and a mouse move spread over a second."""
    if not ended(c, found, 4.5):
        return
    g = lambda q, f: value(found, q, 1.0).get(f)  # noqa: E731
    c.eq("the ground at the origin, the player standing there traced through", (g("origin", "height"), g("origin", "hit")), (0, 1))
    c.eq("on the hill, under the roof, the floor under the roof when only it is ground, and nothing far away",
         (g("hill", "height"), g("roof", "height"), g("under_roof", "height"), g("nowhere", "height"), g("nowhere", "hit")),
         (2, 5, 0, None, 0))
    c.eq("over a box on a 5 x 5 grid: min, max, range, hits, points",
         tuple(g("rise", k) for k in ("min", "max", "range", "hits", "points")), (0, 2, 2, 25, 25))
    c.near("and the mean", g("rise", "mean"), 9 * 2 / 25, 1e-6)
    csg = g("csg", "triangles") or 0
    c.eq("a root CSG shape is one piece (its inner shape none), of its result's triangles (%s)" % csg,
         (g("csg", "count"), csg > 12), (1, True))
    c.eq("pieces: 3 rocks (one hidden), the 3 trees a multimesh draws of its 5 slots, 2 of a multimesh that draws all, "
         "none of one that draws none, 5 grid map tiles (one turned), a CSG shape; a farther level of detail and an "
         "empty mesh none", tuple(g("pieces", k) for k in ("count", "visible", "components", "objects", "triangles",
                                                           "visible_triangles")),
         (14, 13, 7, 7, 156 + csg, 144 + csg))
    c.eq("by mesh name", (g("rocks", "count"), g("rocks", "visible")), (3, 2))
    c.eq("by class: the multimeshes' drawn instances", (g("trees", "count"), g("trees", "visible")), (5, 5))
    if found["rendered"]:
        c.eq("near a point, each piece by its own place: two trees and two tiles", g("near_trees", "count"), 4)
    else:  # a play that draws nothing holds no multimesh's instance places (the rendering server keeps them)
        c.eq("near a point, each piece by its own place: two tiles (headless, a multimesh's instances have no place)",
             g("near_trees", "count"), 2)
    c.eq("under an owner", g("owned", "count"), 5)
    c.eq("the ground on a crate that is a rigid body, and the floor under it when only the floor is ground",
         (g("crate", "height"), g("under_crate", "height")), (1, 0))
    c.eq("a class no node can be: no value, and why", (value(found, "nothing", 1.0), "pieces nothing: no component type "
                                                       "NoSuchThing" in errors(found)), ({}, True))
    c.eq("a sign in the 3D world is ui text; one behind the camera and a hidden one aren't",
         [(r.get("source"), r.get("name"), r.get("text")) for r in rows(found, "signs", 1.0)],
         [("label3d", "Sign", "GATE 3"), ("label3d", "Facing", "EXIT"), ("label3d", "Turned", "EXIT")])
    facing, turned = row(found, "signs", 1.0, "Facing"), row(found, "signs", 1.0, "Turned")
    c.true("a billboard sign on a node turned side on reads as wide as one on a plain node (%s, %s)"
           % (turned.get("w"), facing.get("w")), (turned.get("w") or 0) > 0.01 and
           abs((turned.get("w") or 0) - (facing.get("w") or 0)) < 0.1 * (facing.get("w") or 1)
           and abs((turned.get("h") or 0) - (facing.get("h") or 0)) < 0.1 * (facing.get("h") or 1))
    size = found.get("size") or [960, 540]
    aspect = (facing.get("w") or 0) * size[0] / max((facing.get("h") or 1) * size[1], 1e-9)
    c.near("a billboard sign's face is its text's, as EXIT is drawn without a billboard: 0.33 x 0.225 m", aspect,
           0.33 / 0.225, 0.1)
    c.eq("a select of boxes, or of a rect no sign is in, takes no sign", (rows(found, "boxes", 1.0),
                                                                         rows(found, "corner", 1.0)), ([], []))
    sign = row(found, "signs", 1.0)
    c.true("its place on screen: in the middle across, above the middle (%s, %s)" % (sign.get("x"), sign.get("y")),
           0.3 < (sign.get("x") or 0) < 0.5 and 0.0 < (sign.get("y") or 0) < 0.6)
    moved = lambda t, f: row(found, "looker", t).get(f)  # noqa: E731
    c.true("a move spread over a second is half done half way (%s of 300)" % moved(1.5, "prop:total_x"),
           120 <= (moved(1.5, "prop:total_x") or 0) <= 180)
    c.near("and whole after it", moved(3.0, "prop:total_x"), 300, 0.01)
    c.near("with a move at once beside it", moved(3.0, "prop:total_y"), -50, 0.01)
    c.true("in many motions, one a frame (%s)" % moved(3.0, "prop:events"), (moved(3.0, "prop:events") or 0) >= 25)


PLACES = ("spinner", "glowing", "empty", "sparks", "still", "band", "beam", "around", "unseen", "torch", "thin", "crowd",
          "single")


def check_places(c, found):
    """What is drawn in a place: headless, no value and the reason; drawn, what each place holds."""
    if not ended(c, found, 3.5):
        return
    drawn = found["rendered"]
    if not drawn:
        c.eq("a play that draws nothing has no value", [value(found, q, 1.0) for q in PLACES], [{}] * len(PLACES))
        c.eq("and says why, once a place", sorted(e.split(": ", 1)[1] for e in errors(found) if e.startswith("drawn ")),
             ["this play draws nothing (headless): drawn has no value"] * len(PLACES))
        return
    c.eq("only the crowded place says why it has no value", errors(found),
         ["drawn crowd: more than 1024 parts reach the place: no value (keep the place tighter)"])
    at = {q: value(found, q, 2.0) for q in PLACES}
    c.eq("drawn in each place: a box, a box, nothing (a wall outside it, a sky dome around all), particles, a box, "
         "nothing above the still box's top, a beam, a box again, nothing the camera leaves out, a lit box, a thin "
         "beam, no value past 1024 parts, one CPU particle", [at[q].get("drawn") for q in PLACES],
         [1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, None, 1])
    c.eq("two places over one part give its layers back as they were", sorted({r.get("prop:layers") for s in
                                                                               samples(found, "layers") for r in s.get("rows") or []}), [1])
    c.true("a wall the camera leaves out never shows in the frame (%s)" % value(found, "frame", 2.0).get("luminance"),
           (value(found, "frame", 2.0).get("luminance") or 0) > 0.02)
    c.eq("a still box under a light that flickers every frame: no motion, no base change",
         [(value(found, "torch", t).get("motion"), value(found, "torch", t).get("base_change")) for t in (1.0, 2.0, 3.0)],
         [(0, 0)] * 3)
    c.near("a beam 5 cm thick reaches 21 m along a 30 m line", at["thin"].get("reach"), 21.0, 0.1)
    c.near("a world exposure and auto-exposure leave the base colour as it is", at["spinner"].get("base_r"), 0.3186, 0.01)
    c.eq("the first sample has no motion", value(found, "spinner", 1 / 30).get("motion", "absent"), None)
    c.true("a box that spins moves (%s), one that stays still doesn't (%s)" % (at["spinner"].get("motion"),
                                                                               at["still"].get("motion")),
           (at["spinner"].get("motion") or 0) > 0.05 and at["still"].get("motion") == 0)
    c.true("particles move (%s)" % at["sparks"].get("motion"), (at["sparks"].get("motion") or 0) > 0.05)
    red = [at["spinner"].get(k) for k in ("base_r", "base_g", "base_b")]
    c.true("a red box's base colour is red whatever lights it (%s)" % red,
           None not in red and red[0] > 0.2 and red[0] > 3 * red[1] and red[0] > 3 * red[2])
    c.true("and stays it as it turns (%s)" % at["spinner"].get("base_change"), at["spinner"].get("base_change") is not None and at["spinner"].get("base_change") < 0.05)
    blue = [at["glowing"].get(k) for k in ("base_r", "base_g", "base_b")]
    c.true("a blue box that glows green reads blue: its glow is no base colour (%s)" % blue,
           None not in blue and blue[2] > 0.2 and blue[2] > 3 * blue[1])
    c.near("a beam from 1 m to 5 m along the line reaches 5 m", at["beam"].get("reach"), 5.0, 0.25)
    c.near("and 4 m of it is drawn", at["beam"].get("length"), 4.0, 0.4)
    c.true("probe.log says what a place costs", "ms a sample" in found["files"].get("probe.log", b"").decode(
        "utf-8", "replace"))


def places_same(found):
    """What two drawn plays of the places must agree on: a thin beam's reach, and what each place holds."""
    return [value(found, "thin", t).get("reach") for t in (1.0, 2.0, 3.0)] + \
        [value(found, q, 2.0).get("drawn") for q in PLACES]


def check_errors(c, found):
    if not ended(c, found, 1.5):
        return
    probe = found["probe"]
    c.eq("the task's player select", probe.get("player"), "Ball")
    c.near("the track follows it", probe["track"][0][1], 6.0, 0.01)
    c.eq("query errors", errors(found), [
        "query 'a': unknown kind 'nope' (null values)",
        "objects b: no field sheen",
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


def check_kept(c, found):
    if not ended(c, found, 2.5):
        return
    c.true("a play that keeps the saved data finds what the play before it saved (the game's second start on it), "
           "what it saved when it was told to close too", "VISITS 2 CLOSED" in texts(found, "texts", 1.0),
           texts(found, "texts", 1.0))
    c.true("probe.log says so", b"the saved data is kept: the play runs after the plays that left it" in found["files"].get("probe.log", b""))


def check_fresh(c, found):
    if not ended(c, found, 2.5):
        return
    log = found["log"]
    end = log.find("TaskProbe: the play's time is up; what follows is the game closing")
    c.true("the game's log marks the play's end before the game is told to close", 0 <= end < log.find("closing: the game saves"),
           log[-400:])
    c.true("a play that doesn't starts clean, whatever the play before it saved", "VISITS 1" in texts(found, "texts", 1.0),
           texts(found, "texts", 1.0))


def check_frame(c, found):
    if not ended(c, found, 3.5):
        return
    probe = found["probe"]
    width, height = found["size"]
    c.eq("screenshots: one taken when its event came (the tap's count shown), the evenly spaced ones, a named one",
         probe.get("screenshots"), ["shot_tapped.png", "shot_00.png", "shot_01.png", "shot_moved.png"])
    note = found["files"].get("probe.log", b"").decode("utf-8", "replace")
    c.true("the shot that waits for its event is taken in the frame the tap's count shows",
           re.search(r"the shot tapped's event: text reads 1\.0\n.*screenshot shot_tapped\.png at 0\.[56]\d s", note),
           note[-2000:])
    c.eq("one whose event doesn't come within its time is a miss",
         [(m["t"], m["kind"], m["target"], m["why"]) for m in probe.get("inputs_missed", [])],
         [(2.6, "shot_when", "never", NEVER)])
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
    "touch_drawn": {"check": check_touch, "spec": "touch", "rendered": True},
    "second": {"check": check_second, "twice": True},
    "captions": {"check": check_captions},
    "scrolls": {"check": check_scrolls},
    "events": {"check": check_events},
    "contact": {"check": check_contact, "twice": True},
    "sounds": {"check": check_sounds, "twice": True, "same": sound_totals},
    "lamps": {"check": check_lamps, "twice": True},
    "crates": {"check": check_crates, "twice": True},
    "field": {"check": check_field, "twice": True},
    "field_drawn": {"check": check_field, "spec": "field", "rendered": True},
    "places": {"check": check_places},
    "places_drawn": {"check": check_places, "spec": "places", "rendered": True, "twice": True, "same": places_same},
    "lamps_drawn": {"check": check_lamps, "spec": "lamps", "rendered": True, "twice": True, "same": lamps_lit},
    "lamps_reach": {"check": check_lamps_reach, "rendered": True},
    "errors": {"check": check_errors},
    "refuse": {"check": check_refuse, "spec": "wait", "format": "other-probe-play/1"},
    "idle": {"check": check_idle, "spec": "wait", "flag": False, "engine_args": ["--quit-after", "30"]},
    "shutdown": {"check": check_shutdown, "args": ["-quitAt", "2"]},
    "wait": {"check": check_wait},
    "kept": {"check": check_kept, "first": "wait"},
    "fresh": {"check": check_fresh, "first": "wait"},
    "frame": {"check": check_frame, "rendered": True},
}
