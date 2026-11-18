extends RefCounted
## A play's scripted inputs (contract section 4), sent at their times as the engine's own input events through
## Input.parse_input_event, so the game's _input, its controls and its input actions take them as a player's: keys,
## mouse buttons, mouse movement and the wheel, a gamepad's buttons and axes, widget clicks, touches (a tap, a long
## press, a drag, several fingers at once) and the phone's back button. A key travels the engine's own way (the game's
## _input, the control with the keyboard focus, then the game's later stages while nothing took it) and carries the
## modifiers held, as a keyboard's; a move of the cursor to a point also puts the display's own pointer there, so a
## game that reads the mouse itself finds it where the cursor went. And the grader's own stages: cursor moves,
## teleports of the player (held there for a while when asked), waits in real time, named screenshots, scene loads,
## view turns, and the stages of a contact: an object pinned at a place, a hit through the game's take_damage, a
## property set. A click or a tap on a Control that only its own scroll areas hide scrolls them to it, as a player
## would, and presses in the next frame; one on a Control something else is over presses nothing. A shot may wait for
## an event (`when`): it is taken in the first frame at or after its time in which the event's reading meets its expect.

const Find := preload("find.gd")
const UiScan := preload("ui_scan.gd")

## Input System key names (as the other factories' plays write them) that aren't the engine's own names
const KEYS := {
	"enter": KEY_ENTER, "backquote": KEY_QUOTELEFT, "quote": KEY_APOSTROPHE, "semicolon": KEY_SEMICOLON, "comma": KEY_COMMA,
	"period": KEY_PERIOD, "slash": KEY_SLASH, "backslash": KEY_BACKSLASH, "leftbracket": KEY_BRACKETLEFT,
	"rightbracket": KEY_BRACKETRIGHT, "minus": KEY_MINUS, "equals": KEY_EQUAL, "leftshift": KEY_SHIFT, "rightshift": KEY_SHIFT,
	"leftalt": KEY_ALT, "rightalt": KEY_ALT, "leftctrl": KEY_CTRL, "rightctrl": KEY_CTRL, "leftmeta": KEY_META,
	"rightmeta": KEY_META, "contextmenu": KEY_MENU, "leftarrow": KEY_LEFT, "rightarrow": KEY_RIGHT, "uparrow": KEY_UP,
	"downarrow": KEY_DOWN, "numpadenter": KEY_KP_ENTER, "numpaddivide": KEY_KP_DIVIDE, "numpadmultiply": KEY_KP_MULTIPLY,
	"numpadplus": KEY_KP_ADD, "numpadminus": KEY_KP_SUBTRACT, "numpadperiod": KEY_KP_PERIOD, "numpad0": KEY_KP_0,
	"numpad1": KEY_KP_1, "numpad2": KEY_KP_2, "numpad3": KEY_KP_3, "numpad4": KEY_KP_4, "numpad5": KEY_KP_5,
	"numpad6": KEY_KP_6, "numpad7": KEY_KP_7, "numpad8": KEY_KP_8, "numpad9": KEY_KP_9, "printscreen": KEY_PRINT,
}
## a modifier named with its side: the side a keyboard's event gives it (an action bound to that side alone takes it)
const SIDED := {
	"leftshift": KEY_LOCATION_LEFT, "rightshift": KEY_LOCATION_RIGHT, "leftctrl": KEY_LOCATION_LEFT,
	"rightctrl": KEY_LOCATION_RIGHT, "leftalt": KEY_LOCATION_LEFT, "rightalt": KEY_LOCATION_RIGHT,
	"leftmeta": KEY_LOCATION_LEFT, "rightmeta": KEY_LOCATION_RIGHT,
}
const MODIFIER_KEYS := [KEY_SHIFT, KEY_CTRL, KEY_ALT, KEY_META]
const MOUSE_BUTTONS := {
	"leftbutton": MOUSE_BUTTON_LEFT, "rightbutton": MOUSE_BUTTON_RIGHT, "middlebutton": MOUSE_BUTTON_MIDDLE,
	"forwardbutton": MOUSE_BUTTON_XBUTTON2, "backbutton": MOUSE_BUTTON_XBUTTON1,
}
const PAD_BUTTONS := {
	"buttonsouth": JOY_BUTTON_A, "buttoneast": JOY_BUTTON_B, "buttonwest": JOY_BUTTON_X, "buttonnorth": JOY_BUTTON_Y,
	"leftshoulder": JOY_BUTTON_LEFT_SHOULDER, "rightshoulder": JOY_BUTTON_RIGHT_SHOULDER, "start": JOY_BUTTON_START,
	"select": JOY_BUTTON_BACK, "leftstickpress": JOY_BUTTON_LEFT_STICK, "rightstickpress": JOY_BUTTON_RIGHT_STICK,
	"dpad/up": JOY_BUTTON_DPAD_UP, "dpad/down": JOY_BUTTON_DPAD_DOWN, "dpad/left": JOY_BUTTON_DPAD_LEFT,
	"dpad/right": JOY_BUTTON_DPAD_RIGHT,
}
## a stick's y is up-positive in a play, as the other factories write it; the engine's is down-positive
const PAD_AXES := {
	"leftstick/x": [JOY_AXIS_LEFT_X, 1.0], "leftstick/y": [JOY_AXIS_LEFT_Y, -1.0], "rightstick/x": [JOY_AXIS_RIGHT_X, 1.0],
	"rightstick/y": [JOY_AXIS_RIGHT_Y, -1.0], "lefttrigger": [JOY_AXIS_TRIGGER_LEFT, 1.0],
	"righttrigger": [JOY_AXIS_TRIGGER_RIGHT, 1.0],
}
## the control that is the phone's back button in a mobile game's play (the spec says `touch`)
const BACK := "<keyboard>/escape"
const COVERED := "covered by another control"  ## the why of a click or a tap something else takes (check.COVERED)
const NEVER := "its event never happened"  ## the why of a shot whose event didn't come in time (check.NEVER)
const UNPRESSED := "its scroll area was scrolled to it, but the play ended before the press"
const UNREAD := "its event can't be read (probe.log)"  ## a shot whose event's query or match can't be made
const PLAY_SECONDS := 300.0  ## the longest task play (the task schema's): a touch's hold and a drag's spread at most
const WARM := 0.2  ## seconds before an input's time from which its has.lit selects are looked at every frame
const LIT_WAIT := 1.0  ## seconds an input whose has.lit select waits for a part's first drawing is held back at most

var probe: Node
var rows: Array[Dictionary] = []
var sent := 0
var waiting := false  ## a wait input holds the play's clock
var touch_play := false  ## the spec says `touch`: a mobile game's play
var missed: Array = []  ## probe.json "inputs_missed": [{t, kind, target, why}]

var _next := 0
var _cursor := Vector2.ZERO
var _cursor_set := false
var _buttons := 0  # the mouse buttons held, as a mask
var _modifiers_down: Dictionary = {}  # a modifier key held -> the sides of it held (KeyLocation)
var _pointer_stuck_said := false  # probe.log said once that the display's pointer stayed put
var _parsed := false  # an event was handed to the engine in this frame
var _touching: Array[Dictionary] = []  # fingers on the screen
var _clicks: Array[Dictionary] = []  # widget clicks under way
var _moves: Array[Dictionary] = []  # mouse moves spread over seconds under way: {by, start, over, sent}
var _lit: Dictionary = {}  # an input row's index -> its selects that ask for a lit part
var _lit_waits: Dictionary = {}  # an input row's index -> one of its has.lit selects waits for a part's first drawing
var _hold_at := Vector3.ZERO
var _hold_until := -1.0
var _pins: Array[Dictionary] = []  # objects held at a place: {ref, at, until}
var _hits: Dictionary = {}  # the node whose take_damage a damage stage called, by instance id: {ref, sum, numbers}
var _wait_for := 0.0
var _wait_frames := 0
var _wait_start := 0
var _again: Dictionary = {}  # a click or a tap whose Control was scrolled into view: sent once more in the next frame
var _awaited: Array[Dictionary] = []  # shots waiting for their event: {name, t, until, field, of, op, value, match, query}


func _init(owner: Node, spec: Variant, touch: bool = false) -> void:
	probe = owner
	touch_play = touch
	if spec is Array:
		for item: Variant in spec:
			if item is Dictionary and _kind(item) != "":
				rows.append(item)
	# by time, rows of one time in the order the task wrote them (a stable sort; rows are few)
	for i in range(1, rows.size()):
		var row := rows[i]
		var j := i - 1
		while j >= 0 and _at(rows[j]) > _at(row):
			rows[j + 1] = rows[j]
			j -= 1
		rows[j + 1] = row


static func _at(row: Dictionary) -> float:
	return Find.num(row, "t")


static func _kind(row: Dictionary) -> String:
	## what a row asks for, tried in this order; "" for a row that is none of them (it is left out)
	if Find.text(row, "widget") != "" and Find.flag(row, "click"):
		return "click"
	if row.has("tap"):
		return "tap"
	if row.has("drag"):
		return "drag"
	if Find.numbers(row.get("cursor"), 2).size() == 2:
		return "cursor"
	if Find.numbers(row.get("move"), 2).size() == 2:
		return "move"
	if not Find.obj(row, "teleport_to").is_empty():
		return "teleport_to"
	if Find.numbers(row.get("teleport"), 3).size() == 3:
		return "teleport"
	if row.get("pin") is Dictionary:
		return "pin"
	if Find.has_num(row, "damage") and row.get("to") is Dictionary:
		return "damage"
	if row.get("set") is String and row.get("on") is Dictionary and row.has("value"):
		return "set"
	if row.get("shot") is String:
		return "shot"
	if row.get("scene") is String:
		return "scene"
	if Find.numbers(row.get("view"), 2).size() == 2:
		return "view"
	if Find.has_num(row, "wait"):
		return "wait"
	return "key" if row.get("key") is String else ""


# ---------------------------------------------------------------- the play's frames


func send(elapsed: float) -> void:
	## every input due at play time `elapsed`, then the part due by now of what is under way (a finger's path, a
	## click's release); stops at a wait (the inputs after it wait for its end), and at a click or a tap that scrolled
	## its Control into view: that one is sent once more first in the next frame, once the layout has followed, and the
	## inputs after it wait for it, so their order stays
	_step(elapsed)
	if not _again.is_empty():
		var row := _again
		_again = {}
		_send_one(row, elapsed, true)
	while _again.is_empty() and not waiting and _next < rows.size() and _at(rows[_next]) <= elapsed + 1e-9:
		var row := rows[_next]
		if _lit_waits.get(_next, false) and elapsed < _at(row) + LIT_WAIT:
			break  # who it picks isn't known before the part's first drawing is read: sent in a later frame
		_next += 1
		_send_one(row, elapsed)
		sent += 1
	_flush()


func warm(elapsed: float) -> void:
	## an input about to be sent that picks its object by its light (a select with has.lit) has that select looked at
	## in the frames before, so a part whose light only a drawing tells is drawn by the time the input is sent; one
	## still waiting for a part's first drawing when it is due is sent once it is read (at most LIT_WAIT later)
	for i in range(_next, rows.size()):
		if _at(rows[i]) > elapsed + WARM:
			break
		if not _lit.has(i):
			var found: Array = []
			Find.lit_selects(rows[i], found)
			_lit[i] = found
		var asked: int = Find.pending
		for select: Dictionary in _lit[i]:
			Find.objects(select)
		_lit_waits[i] = Find.pending != asked


func wait_tick() -> void:
	## one frame of a wait: the game runs paced to real time; the wait is over when its seconds of both real and game
	## time have passed
	_wait_frames += 1
	var game := _wait_frames / float(probe.fps)
	var real := (Time.get_ticks_msec() - _wait_start) / 1000.0
	if game < _wait_for or real < _wait_for:
		return
	waiting = false
	probe.pace(false)
	probe.note("the wait is over (%.1f s of game time, %.1f s of real time)" % [game, real])


func hold(elapsed: float) -> void:
	## a held player and every pinned object go back to their spots, still
	if elapsed < _hold_until:
		_keep(probe.player(), _hold_at)
	if _pins.is_empty():
		return
	var held: Array[Dictionary] = []
	for pin in _pins:
		var n: Node = pin["ref"].get_ref()
		if n == null or not n.is_inside_tree() or elapsed >= pin["until"]:
			continue
		held.append(pin)
		_keep(n, pin["at"])
	_pins = held


static func _keep(n: Node, spot: Vector3) -> void:
	var at: Variant = Find.place(n) if n != null else null
	if at == null:
		return
	if (at as Vector3).distance_squared_to(spot) > 1e-6:
		_place(n, spot, null)
	else:
		_still(n)


func finish() -> void:
	## the play is over: no finger and no button stays down. A click or a tap still to be sent once more after its scroll
	## is a miss (UNPRESSED), and so is every shot still waiting for its event (NEVER).
	if not _again.is_empty():
		var kind := _kind(_again)
		_miss(_again, kind, Find.text(_again, "widget") if kind == "click" else _spot_name(_again.get("tap")), UNPRESSED)
		_again = {}
	for awaited in _awaited:
		_never(awaited)
	_awaited.clear()
	for touch in _touching:
		if touch["down"]:
			_touch_event(touch["finger"], touch["last"], false)
	_touching.clear()
	_flush()


func _flush() -> void:
	# the engine hands buffered events to the game when its next frame starts; flushed here, the game's _input runs
	# now, before its scripts' _process of this frame
	if _parsed:
		Input.flush_buffered_events()
	_parsed = false


func _parse(event: InputEvent) -> void:
	Input.parse_input_event(event)
	_parsed = true


func _miss(row: Dictionary, kind: String, target: String, why: String) -> void:
	missed.append({"t": _at(row), "kind": kind, "target": target, "why": why})
	probe.note("missed: %s %s at %.2f s: %s" % [kind, target, _at(row), why])


func _send_one(row: Dictionary, elapsed: float, again: bool = false) -> void:
	## one input; `again`: a click or a tap sent once more after its Control was scrolled into view (it scrolls no more)
	match _kind(row):
		"click":
			_click(row, elapsed, again)
		"tap", "drag":
			_touch(row, elapsed, again)
		"cursor":
			var xy := Find.numbers(row.get("cursor"), 2)
			_move_cursor(UiScan.fraction(xy[0], xy[1]), Vector2.ZERO)
			probe.note("cursor to (%.3f, %.3f)" % [clampf(xy[0], 0.0, 1.0), clampf(xy[1], 0.0, 1.0)])
		"move":
			var by := Find.numbers(row.get("move"), 2)
			var over := Find.num(row, "over") if Find.has_num(row, "over") else 0.0
			if over <= 0.0:
				_move_cursor(_where(), _in_window(Vector2(by[0], by[1])))
			else:
				# from the clock when it is sent: a row sent late spreads over its seconds all the same
				_moves.append({"by": Vector2(by[0], by[1]), "start": elapsed, "over": over, "sent": Vector2.ZERO})
			probe.note("mouse moved by (%.1f, %.1f) over %.2f s" % [by[0], by[1], over])
		"teleport_to":
			_teleport_to(row, elapsed)
		"teleport":
			var player: Node = probe.player()
			if player == null or Find.place(player) == null:
				probe.note("teleport skipped (no player)")
			else:
				_place(player, Find.vec3(row.get("teleport")), Find.num(row, "yaw") if Find.has_num(row, "yaw") else null)
				_start_hold(row, player, elapsed)
		"pin":
			_pin(row, elapsed)
		"damage":
			_strike(row)
		"set":
			_write(row)
		"shot":
			if row.get("when") is Dictionary:
				_await_event(row)
			elif not probe.shot(Find.text(row, "shot")):
				_miss(row, "shot", Find.text(row, "shot"), "its name isn't a letter or _ first, then letters, digits, _")
		"scene":
			if not probe.load_scene(Find.text(row, "scene")):
				_miss(row, "scene", Find.text(row, "scene"), "the project has no such scene")
		"view":
			_view(row)
		"wait":
			waiting = true
			_wait_for = clampf(Find.num(row, "wait"), 0.0, 600.0)
			_wait_frames = 0
			_wait_start = Time.get_ticks_msec()
			probe.pace(true)
			probe.note("the play's clock holds at %.2f s for %.1f s of real time" % [elapsed, _wait_for])
		"key":
			if Find.has_num(row, "axis"):
				_control(Find.text(row, "key"), Find.num(row, "axis"), true)
			else:
				_control(Find.text(row, "key"), 1.0 if row.get("press", true) else 0.0, false)


func _step(elapsed: float) -> void:
	# fingers on the screen: the part due by now (one that went down in this frame was sent its press already)
	var down: Array[Dictionary] = []
	for touch in _touching:
		_move_touch(touch, elapsed)
		if not touch["finished"]:
			down.append(touch)
	_touching = down
	# mouse moves spread over seconds: the part due by now, as one motion of the mouse a frame
	var going: Array[Dictionary] = []
	for move in _moves:
		var share := clampf((elapsed - move["start"]) / move["over"], 0.0, 1.0)
		var due: Vector2 = move["by"] * share - move["sent"]
		if due != Vector2.ZERO:
			_move_cursor(_where(), _in_window(due))
			move["sent"] = move["sent"] + due
		if share < 1.0:
			going.append(move)
	_moves = going
	# widget clicks: the release a frame after the press, then whether the button took it
	var open: Array[Dictionary] = []
	for click in _clicks:
		click["frames"] += 1
		if click["frames"] == 1:
			_button(MOUSE_BUTTON_LEFT, false)
		if click["frames"] < 3:
			open.append(click)
		elif click["watched"] and not click["taken"][0]:
			_miss(click["row"], "click", click["label"], "the click at its centre didn't press it (another control is over it, or it takes no click)")
	_clicks = open


# ---------------------------------------------------------------- keys, buttons, axes, the cursor


func _in_window(frame_pixels: Vector2) -> Vector2:
	## a motion in the frame's pixels as the window's events give it: the game's viewport takes it back to the frame's
	return probe.get_tree().root.get_final_transform().basis_xform(frame_pixels)


func _where() -> Vector2:
	if not _cursor_set:
		_cursor = UiScan.fraction(0.5, 0.5)  # the pointer starts at the frame's centre
		_cursor_set = true
	return _cursor


func _move_cursor(to: Vector2, relative: Vector2) -> void:
	## A motion of the mouse to `to` (the window's pixels) as a display sends a player's: its relative motion
	## (`relative`, or from where the cursor was), the buttons and modifiers held, and the velocity the engine tracks.
	## A move to a point (no `relative`: a cursor input, a click's move to its control) also takes the display's own
	## pointer there, as a real mouse does, so what a game reads of the mouse itself is that point; a relative motion (a
	## move, a mouse delta) leaves it where it is.
	var from := _where()
	_cursor = to
	var motion := InputEventMouseMotion.new()
	motion.position = to
	motion.global_position = to
	motion.relative = relative if relative != Vector2.ZERO else to - from
	motion.screen_relative = motion.relative
	motion.velocity = Input.get_last_mouse_velocity()
	motion.screen_velocity = Input.get_last_mouse_screen_velocity()
	motion.button_mask = _buttons
	_held_modifiers(motion)
	_parse(motion)
	if relative == Vector2.ZERO:
		_pointer_to(to)


func _pointer_to(to: Vector2) -> void:
	## The display's own pointer to `to` (the window's pixels). With a mouse on the display, the engine reads
	## Viewport.get_mouse_position, a canvas item's get_global_mouse_position and the physics picking's hover between
	## motions from that pointer, not from the events; headless it has none and reads them from the events already. A
	## display that keeps its pointer put (a session without a desktop of its own) is said once in probe.log.
	if not DisplayServer.has_feature(DisplayServer.FEATURE_MOUSE):
		return
	Input.warp_mouse(to)
	var root: Window = probe.get_tree().root
	var asked := root.get_final_transform().affine_inverse() * to
	var reads := root.get_mouse_position()
	if reads.distance_to(asked) > 1.0 and not _pointer_stuck_said:
		_pointer_stuck_said = true
		probe.note("the display's pointer didn't follow the cursor to (%.0f, %.0f): the game reads it at (%.0f, %.0f)"
			% [asked.x, asked.y, reads.x, reads.y])


func _held_modifiers(event: InputEventWithModifiers) -> void:
	## the modifier keys held now, which a keyboard's state puts on every key and mouse event
	event.shift_pressed = _modifiers_down.has(KEY_SHIFT)
	event.ctrl_pressed = _modifiers_down.has(KEY_CTRL)
	event.alt_pressed = _modifiers_down.has(KEY_ALT)
	event.meta_pressed = _modifiers_down.has(KEY_META)


func _button(index: MouseButton, down: bool, factor: float = 1.0) -> void:
	var bit := 1 << (index - 1)
	if index <= MOUSE_BUTTON_MIDDLE or index >= MOUSE_BUTTON_XBUTTON1:
		_buttons = (_buttons | bit) if down else (_buttons & ~bit)
	var event := InputEventMouseButton.new()
	event.button_index = index
	event.pressed = down
	event.factor = factor
	event.position = _where()
	event.global_position = _where()
	event.button_mask = _buttons
	_held_modifiers(event)
	_parse(event)


func _key(code: Key, down: bool, side: KeyLocation = KEY_LOCATION_UNSPECIFIED) -> void:
	## A key as a keyboard sends it: its code, a modifier's side (`side`), the modifiers held (a modifier's own press
	## among them, its release not), and the character it types (a letter in capitals while Shift is held; other keys
	## as they are). It never repeats while held. The engine routes it as a keyboard's: the game's _input, the control
	## with the keyboard focus (a text field takes a typed key), then _shortcut_input, _unhandled_key_input and
	## _unhandled_input while nothing has taken it; Input's polled state follows every key, taken or not.
	if MODIFIER_KEYS.has(code):
		var sides: Array = _modifiers_down.get(code, [])
		if down:
			if not sides.has(side):
				sides.append(side)
		else:
			sides.erase(side)
		if sides.is_empty():
			_modifiers_down.erase(code)
		else:
			_modifiers_down[code] = sides
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.key_label = code
	event.location = side
	_held_modifiers(event)
	if code >= KEY_SPACE and code <= KEY_ASCIITILDE:
		var typed := String.chr(code)
		typed = typed.to_upper() if event.shift_pressed else typed.to_lower()
		event.unicode = typed.unicode_at(0)
	event.pressed = down
	_parse(event)


func _control(path: String, value: float, is_axis: bool) -> void:
	## a control's value: a key or a button pressed or released, or an axis set
	if touch_play and path.to_lower() == BACK:
		# a phone has no Escape key: in a mobile game's play the control is the phone's back button, sent as it
		# reaches a game: the window's request (which quits a game that left quit_on_go_back on, as on a phone), its
		# notification down the tree, and the key
		if value != 0.0:
			var root: Window = probe.get_tree().root
			root.go_back_requested.emit()
			if probe.is_inside_tree():
				root.propagate_notification(Node.NOTIFICATION_WM_GO_BACK_REQUEST)
		_key(KEY_BACK, value != 0.0)
		return
	var slash := path.find("/")
	if slash < 0:
		probe.error("inputs: no control " + path)
		return
	var device := path.substr(0, slash)
	var control := path.substr(slash + 1)
	var lower := control.to_lower()
	if device == "<Keyboard>":
		var code: Key = KEYS.get(lower, KEY_NONE)
		if code == KEY_NONE:
			code = OS.find_keycode_from_string(control)
		if code == KEY_NONE:
			probe.error("inputs: the keyboard has no key " + control)
			return
		_key(code, value != 0.0, SIDED.get(lower, KEY_LOCATION_UNSPECIFIED))
	elif device == "<Mouse>":
		if MOUSE_BUTTONS.has(lower):
			_button(MOUSE_BUTTONS[lower], value != 0.0)
		elif lower == "delta/x" or lower == "delta/y":
			var by := Vector2(value, 0.0) if lower == "delta/x" else Vector2(0.0, value)
			_move_cursor(_where(), by)
		elif lower == "scroll/x" or lower == "scroll/y":
			# a wheel turned by so many notches, each a press and a release of the wheel's own button
			var up := MOUSE_BUTTON_WHEEL_UP if lower == "scroll/y" else MOUSE_BUTTON_WHEEL_RIGHT
			var down := MOUSE_BUTTON_WHEEL_DOWN if lower == "scroll/y" else MOUSE_BUTTON_WHEEL_LEFT
			for i in clampi(roundi(absf(value)), 1, 20) if value != 0.0 else 0:
				_button(up if value > 0.0 else down, true)
				_button(up if value > 0.0 else down, false)
		else:
			probe.error("inputs: the mouse has no control " + control)
	elif device == "<Gamepad>":
		if PAD_BUTTONS.has(lower) and not is_axis:
			var press := InputEventJoypadButton.new()
			press.device = 0
			press.button_index = PAD_BUTTONS[lower]
			press.pressed = value != 0.0
			press.pressure = 1.0 if value != 0.0 else 0.0
			_parse(press)
		elif PAD_AXES.has(lower):
			var turn := InputEventJoypadMotion.new()
			turn.device = 0
			turn.axis = PAD_AXES[lower][0]
			turn.axis_value = clampf(value * PAD_AXES[lower][1], -1.0, 1.0)
			_parse(turn)
		else:
			probe.error("inputs: the gamepad has no control " + control)
	else:
		probe.error("inputs: no device for " + path)


func _click(row: Dictionary, _elapsed: float, again: bool = false) -> void:
	## a click on a widget: the mouse moved to its centre, the left button pressed, and let go in the next frame
	## (`widget`: a Control's name or class, else the shown caption of a button, UiScan.by_caption: a name or a class
	## wins over a caption, a caption as written over one alike; a matching button shown but disabled is a miss that
	## says so, UiScan.disabled_button). The control is chosen as if nothing clipped it. When the one chosen is scrolled
	## out of its container's view (UiScan.clipped_out) and its own scroll areas alone hide it, they scroll to it
	## (UiScan.scroll_into_view) and the click is made once more in the next frame (`again`: it scrolls no more); when
	## nothing can show it, or it is still out of view, nothing is sent and the click is a miss that says so
	## (scrolled_out), whatever its marks. When no Control matches on screen, one the scroll areas it lies in alone hide
	## is scrolled to (UiScan.scrolled_away). When a press at its centre would go to something else (UiScan.press_reaches),
	## nothing is sent and the click is a miss, COVERED, whatever its marks.
	var want := Find.text(row, "widget")
	var found: Control = null
	var how := ""
	for c in UiScan.controls():
		if (String(c.name).matchn(want) or Find.is_a(c, want)) and UiScan.reachable(c) and UiScan.rect(c) != null \
				and UiScan.usable(c) != 0.0 and c.mouse_filter != Control.MOUSE_FILTER_IGNORE:
			found = c
			how = "name" if String(c.name).matchn(want) else "class"
			break
	if found == null:
		var read: Array = UiScan.by_caption(want, true)
		if not read.is_empty():
			found = read[0]
			how = read[1]
			if read[2] != "":
				probe.note("click: " + read[2])
	if found == null:
		# a button the game disabled, shown: the click does nothing, as a player's, and the miss says so (a click marked
		# `disabled` has landed on it, the grader's plays.DISABLED; any other is a miss)
		var off: Array = UiScan.disabled_button(want)
		if not off.is_empty():
			var shown: Control = off[0]
			var by: String = off[1]
			if UiScan.clipped_out(shown):
				if not again and _scroll_to(row, shown, "click", want):
					return
				_miss(row, "click", want, scrolled_out(shown, by))
				return
			var lid := _over(shown)
			if lid != "":
				probe.note("%s (%s) matches '%s', shown but disabled, and %s is over it: not clicked"
					% [shown.name, Find.class_of(shown), want, lid])
				_miss(row, "click", want, COVERED)
				return
			_miss(row, "click", want, "a button matches it (%s (%s) by %s), shown but disabled: the click does nothing"
				% [shown.name, Find.class_of(shown), "its " + by if by.begins_with("caption") else by])
			return
		if not again:
			# nothing on screen matches: one only its scroll areas hide is scrolled to, as a player scrolls a list to
			# it, and the click is made once more in the next frame
			var away: Array = UiScan.scrolled_away(want, true)
			if not away.is_empty() and _scroll_to(row, away[0] as Control, "click", want):
				return
		_miss(row, "click", want, "no visible control that takes a click matches it, by name, class or caption")
		return
	if UiScan.clipped_out(found):
		# its centre is outside the view of a container above it: its own scroll areas scroll to it when they alone hide
		# it; otherwise (a Control that only clips, or still out of view once scrolled) a press there reaches nothing in
		# that view, so nothing is sent, and neither `optional` nor `disabled` excuses the miss
		if not again and _scroll_to(row, found, "click", want):
			return
		_miss(row, "click", want, scrolled_out(found, how))
		return
	var over := _over(found)
	if over != "":
		# a player's press at its centre goes to what is over it: nothing is sent, and no mark excuses the miss
		probe.note("%s (%s) matches '%s', but %s is over it: not clicked" % [found.name, Find.class_of(found), want, over])
		_miss(row, "click", want, COVERED)
		return
	var label := "%s (%s)" % [found.name, Find.class_of(found)]
	var taken := [false]
	var watched := found is BaseButton
	if watched:
		var mark := func() -> void: taken[0] = true
		(found as BaseButton).pressed.connect(mark, CONNECT_ONE_SHOT)
	_move_cursor(UiScan.centre(found), Vector2.ZERO)
	_button(MOUSE_BUTTON_LEFT, true)
	_clicks.append({"row": row, "label": label, "frames": 0, "watched": watched, "taken": taken})
	probe.note("clicked %s by %s" % [label, "its " + how if how.begins_with("caption") else how])


func _scroll_to(row: Dictionary, c: Control, kind: String, want: String) -> bool:
	## a click or a tap on `c`, which only its scroll areas hide: they scroll to it (UiScan.scroll_into_view) and the
	## input is sent once more in the next frame (_again); false when nothing can show it (nothing moved)
	var moved := UiScan.scroll_into_view(c)
	if moved == "":
		return false
	probe.note("scrolled %s to show %s (%s) for the %s on '%s'" % [moved, c.name, Find.class_of(c), kind, want])
	_again = row
	return true


static func _over(c: Control) -> String:
	## what a press at `c`'s centre goes to instead of it (UiScan.press_reaches); "" when it comes to `c` or that can't
	## be told
	var read: Array = UiScan.press_reaches(c, UiScan.press_point(c))
	return read[1] if read[0] == 1 else ""


static func scrolled_out(c: Control, by: String) -> String:
	## the why of a click or a touch whose control is scrolled out of its container's view (UiScan.clipped_out); `by`:
	## how it was found, "name", "class" or 'caption "<text>"'. The words "scrolled out of its container's view" are
	## the checker's check.SCROLLED_OUT.
	return "a control matches it (%s (%s) by %s), scrolled out of its container's view: a press at its centre lands " \
		% [c.name, Find.class_of(c), "its " + by if by.begins_with("caption") else by] + "outside the view"


# ---------------------------------------------------------------- touches


func _spot(value: Variant) -> Variant:
	## where a touch's spot is, as an input event names it: a point of the frame [fx, fy], or a widget's centre
	var xy := Find.numbers(value, 2)
	if xy.size() == 2:
		return UiScan.fraction(xy[0], xy[1])
	if value is Dictionary:
		var found := UiScan.named(Find.text(value, "widget"))
		if found != null:
			return UiScan.centre(found)
	return null


static func _spot_name(value: Variant) -> String:
	if value is Dictionary:
		return Find.text(value, "widget")
	var xy := Find.numbers(value, 2)
	return "%.3f, %.3f" % [xy[0], xy[1]] if xy.size() == 2 else str(value)


static func _no_spot(value: Variant) -> String:
	## why a spot has no place: its widget is scrolled out of its container's view (as a click's), or none matches
	if value is Dictionary:
		var found: Array = UiScan.spot_widget(Find.text(value, "widget"))
		if not found.is_empty() and UiScan.clipped_out(found[0] as Control):
			return scrolled_out(found[0] as Control, found[1])
	return "no visible widget matches '%s'" % _spot_name(value)


func _miss_touch(row: Dictionary, kind: String, target: String, why: String) -> void:
	## a touch that can't be made: a row of inputs_missed and one line of the play's query_errors; nothing is touched
	_miss(row, kind, target, why)
	probe.error("inputs: the %s at %.2f s missed: %s" % [kind, _at(row), why])


static func _spot_label(value: Variant) -> String:
	## what a finger goes down on, for probe.log: the point, or the widget found, its class and how it was found (by
	## name, class or caption, and a caption several buttons read)
	if value is Dictionary:
		var found: Array = UiScan.spot_widget(Find.text(value, "widget"))
		if found.is_empty():
			return Find.text(value, "widget")
		var c: Control = found[0]
		return "%s (%s) by %s%s" % [c.name, c.get_class(), "its " + found[1] if found[1].begins_with("caption") else found[1],
			"; " + found[2] if found[2] != "" else ""]
	return "(%s)" % _spot_name(value)


func _touch(row: Dictionary, elapsed: float, again: bool = false) -> void:
	## a finger going down: its spots are found now (a widget's centre as it is laid out at this moment), then it is
	## sent a part each frame until it lifts. A tap on a widget that only its own scroll areas hide scrolls them to it
	## and is made once more in the next frame (`again`), as a click is; one on a widget something else is over
	## (UiScan.press_reaches) is a miss, COVERED. A drag scrolls nothing and is not asked what is over its widget: its
	## spots are taken as they are.
	var drag := row.has("drag")
	var kind := "drag" if drag else "tap"
	var spots: Array = row.get("drag") if drag and row.get("drag") is Array else [row.get("tap")]
	var finger := roundi(Find.num(row, "finger"))
	if spots.size() < (2 if drag else 1) or spots.size() > 16:
		_miss_touch(row, kind, "its spots", "it names no spots")
		return
	if finger < 0 or finger > 9:
		_miss_touch(row, kind, "finger %d" % finger, "finger %d (a finger is 0 to 9)" % finger)
		return
	for touch in _touching:
		if touch["finger"] == finger and not touch["finished"]:
			_miss_touch(row, kind, _spot_name(spots[0]), "finger %d is still down from an earlier touch" % finger)
			return
	var on_widget := not drag and spots[0] is Dictionary
	if on_widget and not again:
		var want := Find.text(spots[0], "widget")
		var seen: Array = UiScan.spot_widget(want)
		var hidden: Control = null
		if not seen.is_empty():
			if UiScan.clipped_out(seen[0] as Control):
				hidden = seen[0]
		else:
			var away: Array = UiScan.scrolled_away(want, false)
			if not away.is_empty():
				hidden = away[0]
		if hidden != null and _scroll_to(row, hidden, "tap", want):
			return
	var points: Array[Vector2] = []
	for spot: Variant in spots:
		var at: Variant = _spot(spot)
		if at == null:
			_miss_touch(row, kind, _spot_name(spot), _no_spot(spot))
			return
		points.append(at)
	if on_widget:
		var tapped := UiScan.named(Find.text(spots[0], "widget"))
		var over := _over(tapped) if tapped != null else ""
		if over != "":
			probe.note("%s (%s) matches '%s', but %s is over it: not tapped"
				% [tapped.name, Find.class_of(tapped), _spot_name(spots[0]), over])
			_miss_touch(row, kind, _spot_name(spots[0]), COVERED)
			return
	var touch := {
		"kind": kind, "finger": finger, "points": points, "start": elapsed, "last": points[0], "down": true, "finished": false,
		"over": clampf(Find.num(row, "over"), 0.0, PLAY_SECONDS) if drag else 0.0,
		"hold": clampf(Find.num(row, "hold"), 0.0, PLAY_SECONDS),
	}
	_touching.append(touch)
	_touch_event(finger, points[0], true)
	probe.note("%s: finger %d goes down on %s" % [kind, finger, _spot_label(spots[0])])


func _move_touch(touch: Dictionary, elapsed: float) -> void:
	## one finger's part due by now: a move when its place changed, up once its path and its hold are over (never in
	## the frame it went down, so a tap is a press in one frame and a release in the next)
	var since: float = elapsed - touch["start"]
	var points: Array[Vector2] = touch["points"]
	var over: float = touch["over"]
	var to := points[points.size() - 1]
	if points.size() > 1 and over > 0.0 and since < over:
		var along := clampf(since / over, 0.0, 1.0) * (points.size() - 1)
		var i := mini(floori(along), points.size() - 2)
		to = points[i].lerp(points[i + 1], along - i)
	var last: Vector2 = touch["last"]
	if not to.is_equal_approx(last):
		var move := InputEventScreenDrag.new()
		move.index = touch["finger"]
		move.position = to
		move.relative = to - last
		move.screen_relative = to - last
		move.velocity = (to - last) * probe.fps
		move.screen_velocity = move.velocity
		_parse(move)
		touch["last"] = to
	if since >= (over if points.size() > 1 else 0.0) + touch["hold"] - 1e-9:
		_touch_event(touch["finger"], to, false)
		touch["finished"] = true
		probe.note("%s: finger %d lifts at pixel (%.0f, %.0f) after %.2f s" % [touch["kind"], touch["finger"], to.x, to.y, since])


func _touch_event(finger: int, at: Vector2, down: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = finger
	event.position = at
	event.pressed = down
	_parse(event)


# ---------------------------------------------------------------- shots that wait for an event


func _await_event(row: Dictionary) -> void:
	## a `shot` input with `when` (the checker writes it {"query", "field", "of", "match", "op", "value", "within"}):
	## from its time it waits for its event, `within` seconds at most when it says (else to the play's end), reading its
	## own query (made as the play's are, TaskProbe.own_query) every frame of the clock (watch_events). One whose query
	## or match can't be made is a miss at once (UNREAD).
	var when := Find.obj(row, "when")
	var name := Find.text(row, "shot")
	var field := Find.text(when, "field")
	var of := Find.text(when, "of")
	var op := Find.text(when, "op")
	var waits := {
		"name": name, "t": _at(row), "field": field if field != "" else "count", "of": of if of != "" else "count",
		"op": op if op != "" else ">=", "value": Find.num(when, "value", 1.0), "match": null, "query": null,
		"until": _at(row) + Find.num(when, "within") if Find.has_num(when, "within") else INF,
	}
	var pattern := Find.text(when, "match")
	if pattern != "":
		var re := RegEx.new()
		if re.compile(pattern, false) != OK:
			probe.error("inputs: the shot %s's event: the match regex %s doesn't compile" % [name, pattern])
			_miss(row, "shot_when", name, UNREAD)
			return
		waits["match"] = re
	waits["query"] = probe.own_query("when_" + name, Find.obj(when, "query"))
	if waits["query"] == null:
		_miss(row, "shot_when", name, UNREAD)
		return
	_awaited.append(waits)
	probe.note("the shot %s waits for its event (%s %s %s) %s" % [name, waits["field"], waits["op"], waits["value"],
		"until %.2f s" % waits["until"] if Find.has_num(when, "within") else "until the play's end"])


func watch_events(elapsed: float) -> void:
	## after the game logic of a frame of the play's clock: a shot whose event's reading meets its expect now is taken in
	## this frame (at its end, as drawn); one whose time is up without it is a miss (NEVER)
	if _awaited.is_empty():
		return
	var still: Array[Dictionary] = []
	for waits in _awaited:
		var read: Variant = _event_reading(waits, elapsed)
		if read != null and _meets(read, waits["op"], waits["value"]):
			probe.note("the shot %s's event: %s reads %s" % [waits["name"], waits["field"], read])
			if not probe.shot(waits["name"]):
				missed.append({"t": waits["t"], "kind": "shot", "target": waits["name"],
					"why": "its name isn't a letter or _ first, then letters, digits, _"})
		elif elapsed > float(waits["until"]) + 1e-9:
			_never(waits)
		else:
			still.append(waits)
	_awaited = still


func _never(waits: Dictionary) -> void:
	missed.append({"t": waits["t"], "kind": "shot_when", "target": waits["name"], "why": NEVER})
	probe.note("missed: shot_when %s at %.2f s: %s" % [waits["name"], waits["t"], NEVER])


static func _event_reading(waits: Dictionary, elapsed: float) -> Variant:
	## the event's reading now, as the checker reduces one sample of its measure (probes.series): a count, how many its
	## query matched; any other field each row's number (a boolean 1 or 0, a string 1 or 0 by `match`, others left out)
	## combined by `of`, or, when more matched than the rows hold, from the sample's summary of every match. Null when
	## nothing gives a value.
	var sample := {"t": elapsed}
	waits["query"].sample(elapsed, sample)
	if sample.get("pending", false) or not (sample.get("rows") is Array):
		return null
	var rows: Array = sample["rows"]
	var total := float(rows.size())
	if Find.has_num(sample, "total") and Find.num(sample, "total") > rows.size():
		total = Find.num(sample, "total")
	var field: String = waits["field"]
	var of: String = waits["of"]
	if field == "count":
		return total
	if total > rows.size() and waits["match"] == null and of != "first":
		var summed: Variant = _from_summary(Find.obj(Find.obj(sample, "full"), field), of)
		if not (summed is bool):
			return summed
	var values: Array[float] = []
	for item: Variant in rows:
		if not (item is Dictionary) or not (item as Dictionary).has(field):
			continue
		var v: Variant = item[field]
		if v is bool:
			values.append(1.0 if v else 0.0)
		elif (v is float or v is int) and not is_nan(float(v)) and not is_inf(float(v)):
			values.append(float(v))
		elif v is String and waits["match"] != null:
			values.append(1.0 if (waits["match"] as RegEx).search(v) != null else 0.0)
	return _combined(values, of)


static func _from_summary(full: Dictionary, of: String) -> Variant:
	## `of` over every match from a sample's summary of one field (n, nonzero, sum, min, max); false when the summary
	## lacks a count (the rows are read instead, as the checker's probes.every_match does)
	if not (Find.has_num(full, "n") and Find.has_num(full, "nonzero") and Find.has_num(full, "sum")):
		return false
	var n := Find.num(full, "n")
	var nonzero := Find.num(full, "nonzero")
	var sum := Find.num(full, "sum")
	match of:
		"count":
			return nonzero
		"any":
			return 1.0 if nonzero > 0.0 else 0.0
		"all":
			return 1.0 if n > 0.0 and nonzero == n else 0.0
		"sum":
			return sum
	if n == 0.0:
		return null
	if of == "mean":
		return sum / n
	return Find.num(full, of) if Find.has_num(full, of) else null  # min, max


static func _combined(values: Array[float], of: String) -> Variant:
	## one sample's row values combined by `of`, as the checker's probes.combine
	match of:
		"count":
			return float(values.filter(func(v: float) -> bool: return v != 0.0).size())
		"any":
			return 1.0 if values.any(func(v: float) -> bool: return v != 0.0) else 0.0
		"all":
			return 1.0 if not values.is_empty() and values.all(func(v: float) -> bool: return v != 0.0) else 0.0
		"sum":
			var sum := 0.0
			for v in values:
				sum += v
			return sum
	if values.is_empty():
		return null
	match of:
		"min":
			return values.min()
		"max":
			return values.max()
		"mean":
			var whole := 0.0
			for v in values:
				whole += v
			return whole / values.size()
	return values[0]  # first


static func _meets(value: float, op: String, limit: float) -> bool:
	## a reading against its expect, as the checker compares one (== and != within 1e-9, as probes.holds)
	var same := absf(value - limit) <= maxf(1e-9, 1e-9 * maxf(absf(value), absf(limit)))
	match op:
		">":
			return value > limit
		">=":
			return value >= limit
		"<":
			return value < limit
		"<=":
			return value <= limit
		"==":
			return same
		"!=":
			return not same
	return false


# ---------------------------------------------------------------- teleports


func _start_hold(row: Dictionary, player: Node, elapsed: float) -> void:
	var seconds := clampf(Find.num(row, "hold"), 0.0, 600.0)
	if seconds <= 0.0:
		return
	_hold_at = Find.place(player)
	_hold_until = elapsed + seconds
	probe.note("holding the player at (%.2f, %.2f, %.2f) for %.1f s" % [_hold_at.x, _hold_at.y, _hold_at.z, seconds])


func _teleport_to(row: Dictionary, elapsed: float) -> void:
	var player: Node = probe.player()
	var here: Variant = Find.place(player) if player != null else null
	if here == null:
		probe.note("teleport_to skipped (no player)")
		return
	var select := Find.obj(row, "teleport_to")
	Find.check(select, "inputs: teleport_to")
	var target: Node = null
	var best := INF
	for n in Find.objects(select):
		var at: Variant = Find.place(n)
		if at == null or n == player or player.is_ancestor_of(n):
			continue
		var d := (at as Vector3).distance_squared_to(here)
		if d < best:
			best = d
			target = n
	if target == null:
		probe.note("teleport_to skipped (no object matches)")
		return
	var there: Vector3 = Find.place(target)
	var flat := target is Node2D or target is Control  # a 2D game has no level line: the side is in its plane
	var side: Vector3 = (here as Vector3) - there
	if not flat:
		side.y = 0.0
	if side.length_squared() < 1e-6 and target is Node3D:
		side = (target as Node3D).global_basis.z  # the player is right above it: the side its back is to
		side.y = 0.0
	side = (Vector3.LEFT if flat else Vector3.BACK) if side.length_squared() < 1e-6 else side.normalized()
	var spot := there + side * clampf(Find.num(row, "distance", 2.0), 0.0, 1000.0) + Find.vec3(row.get("offset"))
	var face := there
	var faced: Variant = Find.point(Find.obj(row, "face")) if not Find.obj(row, "face").is_empty() else null
	if faced != null:
		face = faced
	var look := face - spot
	var yaw: Variant = null
	# nothing to face within a centimetre on the level: it keeps its own yaw
	if not flat and look.x * look.x + look.z * look.z > 1e-4:
		yaw = rad_to_deg(atan2(-look.x, -look.z))
	_place(player, spot, yaw)
	var now: Vector3 = Find.place(player)
	probe.note("teleported next to %s: asked (%.2f, %.2f, %.2f) yaw %s, now at (%.2f, %.2f, %.2f)" % [
		target.name, spot.x, spot.y, spot.z, "%.1f" % yaw if yaw != null else "kept", now.x, now.y, now.z])
	_start_hold(row, player, elapsed)


# ---------------------------------------------------------------- the stages of a contact


func _nearest(select: Dictionary, about: String, around: Node, skip: Node, placed: bool = false) -> Node:
	## the match of an object select nearest to `around` (of two as near, the first in tree order; the first match
	## when `around` has no place), `skip` and the nodes below it left out; with `placed`, only a node with a place
	Find.check(select, about)
	var here: Variant = Find.place(around) if around != null else null
	var found: Node = null
	var best := INF
	for n in Find.objects(select):
		if skip != null and (n == skip or skip.is_ancestor_of(n)):
			continue
		var at: Variant = Find.place(n)
		if placed and at == null:
			continue
		var d := (at as Vector3).distance_squared_to(here) if at != null and here != null else 1e30
		if found == null or d < best:
			best = d
			found = n
	return found


static func _said(select: Dictionary) -> String:
	## a select as a miss names it
	return JSON.stringify(select)


func _pin(row: Dictionary, elapsed: float) -> void:
	## an object held at a place while its own scripts run on: first set ahead of the player or at a point, when
	## asked, facing the player
	var select := Find.obj(row, "pin")
	var player: Node = probe.player()
	var target := _nearest(select, "inputs: pin", player, player, true)
	if target == null:
		_miss(row, "pin", _said(select), "no object with a place matches (the player is never pinned)")
		return
	var spot: Vector3 = Find.place(target)
	var here: Variant = Find.place(player) if player != null else null
	var flat := target is Node2D or target is Control
	var offset := Find.vec3(row.get("offset"))
	var moved := false
	if Find.has_num(row, "front"):
		if here == null:
			_miss(row, "pin", _said(select), "the play has no player to set it in front of")
			return
		var ahead: Variant = Find.forward(player)
		if ahead == null:
			ahead = Vector3.RIGHT if flat else Vector3.FORWARD
		var along: Vector3 = ahead
		if not flat:
			along.y = 0.0
		along = (Vector3.RIGHT if flat else Vector3.FORWARD) if along.length_squared() < 1e-6 else along.normalized()
		var to: Vector3 = (here as Vector3) + along * clampf(Find.num(row, "front"), 0.0, 1000.0) + offset
		if not flat:
			to.y = spot.y + offset.y  # at its own height
		spot = to
		moved = true
	elif row.get("at") is Dictionary:
		var point: Variant = Find.point(row["at"])
		if point == null:
			_miss(row, "pin", _said(select), "its `at` point doesn't resolve")
			return
		spot = (point as Vector3) + offset
		moved = true
	var yaw: Variant = null
	if moved and here != null and not flat:
		var look: Vector3 = (here as Vector3) - spot
		if look.x * look.x + look.z * look.z > 1e-4:
			yaw = rad_to_deg(atan2(-look.x, -look.z))
	_place(target, spot, yaw)
	var seconds := clampf(Find.num(row, "hold"), 0.0, 600.0)
	var held: Array[Dictionary] = []
	for pin in _pins:
		if pin["ref"].get_ref() != target:
			held.append(pin)
	held.append({"ref": weakref(target), "at": spot, "until": elapsed + seconds})
	_pins = held
	probe.note("pinned %s at (%.2f, %.2f, %.2f)%s for %.1f s" % [
		target.name, spot.x, spot.y, spot.z, " yaw %.1f" % yaw if yaw != null else "", seconds])


static func _hurt(n: Node) -> Node:
	## the node whose take_damage a hit on `n` calls: itself, else the first node below it that has the method
	if n.has_method("take_damage"):
		return n
	for c: Node in n.find_children("*", "", true, false):
		if c.has_method("take_damage"):
			return c
	return null


func _strike(row: Dictionary) -> void:
	## a hit through the game's own damage method, take_damage(amount, source); what it returns is the node's
	## damage_taken
	var select := Find.obj(row, "to")
	var player: Node = probe.player()
	var target := _nearest(select, "inputs: damage", player, null)
	if target == null:
		_miss(row, "damage", _said(select), "no object matches")
		return
	var hurt := _hurt(target)
	if hurt == null:
		_miss(row, "damage", String(target.name), "neither it nor a node below it has a take_damage method")
		return
	if not _takes_two(hurt):
		_miss(row, "damage", String(target.name), "its take_damage can't be called with (amount, source)")
		return
	var source: Node = player
	if row.get("from") is Dictionary:
		source = _nearest(row["from"], "inputs: damage", target, target)
		if source == null:
			_miss(row, "damage", _said(row["from"]), "no object matches its `from`")
			return
	elif player == null or target == player or player.is_ancestor_of(target) or target.is_ancestor_of(player):
		source = _other_hurt(target, player)  # the player is the one struck: by the nearest other thing that can be hurt
	var amount := Find.num(row, "damage")
	# what the log and the sum need of the nodes is taken before the call: the hit may free them
	var id := hurt.get_instance_id()
	var said := "damage %s to %s (take_damage of %s) from %s" % [
		amount, target.name, hurt.name, source.name if source != null else "nothing"]
	if not _hits.has(id):
		_hits[id] = {"ref": weakref(hurt), "sum": 0.0, "numbers": true}
	var got: Variant = hurt.call("take_damage", amount, source)
	if (got is float or got is int) and not is_nan(got):
		_hits[id]["sum"] += float(got)
	else:
		_hits[id]["numbers"] = false
	probe.note("%s: it returned %s" % [said, got])


static func _takes_two(hurt: Node) -> bool:
	## whether take_damage can be called with (amount, source): at most two arguments without a default, and room
	## for two (take_damage(amount, source, crit := false) is)
	for method: Dictionary in hurt.get_method_list():
		if method.get("name") == "take_damage":
			var total: int = (method.get("args") as Array).size()
			var optional: int = (method.get("default_args") as Array).size()
			return total - optional <= 2 and total >= 2
	return false


func _other_hurt(target: Node, player: Node) -> Node:
	## the node with a take_damage method nearest to `target` that is neither it nor the player (nor below either)
	var here: Variant = Find.place(target)
	var found: Node = null
	var best := INF
	for n in Find.all_nodes():
		if not n.has_method("take_damage") or n == target or target.is_ancestor_of(n) or n.is_ancestor_of(target):
			continue
		if player != null and (n == player or player.is_ancestor_of(n) or n.is_ancestor_of(player)):
			continue
		var at: Variant = Find.place(n)
		var d := (at as Vector3).distance_squared_to(here) if at != null and here != null else 1e30
		if found == null or d < best:
			best = d
			found = n
	return found


func damage_taken(n: Node) -> Variant:
	## what the take_damage of `n`, or of a node below it, returned for the play's damage stages so far, summed; null
	## when none struck it, or a call returned no number
	var sum := 0.0
	var struck := false
	for id: int in _hits:
		var hurt: Node = _hits[id]["ref"].get_ref()
		if hurt == null or not (hurt == n or n.is_ancestor_of(hurt)):
			continue
		if not _hits[id]["numbers"]:
			return null
		struck = true
		sum += _hits[id]["sum"]
	return sum if struck else null


func _write(row: Dictionary) -> void:
	## a property written on the nearest match, or on every match with `all`
	var select := Find.obj(row, "on")
	var path := Find.text(row, "set")
	var targets: Array[Node] = []
	if Find.flag(row, "all"):
		Find.check(select, "inputs: set")
		targets = Find.objects(select)
	else:
		var one := _nearest(select, "inputs: set", probe.player(), null)
		if one != null:
			targets.append(one)
	if targets.is_empty():
		_miss(row, "set", path, "no object matches %s" % _said(select))
		return
	var took := 0
	for n in targets:
		if Find.write(n, path, row.get("value")):
			took += 1
	if took == 0:
		_miss(row, "set", path, "no matched object has a property %s that takes %s" % [path, JSON.stringify(row.get("value"))])
		return
	probe.note("set %s to %s on %d of %d object(s)" % [path, JSON.stringify(row.get("value")), took, targets.size()])


func _view(row: Dictionary) -> void:
	## the player turns to the yaw and the camera to the pitch and yaw, once: a camera rig that sets its own rotation
	## every frame may turn it back
	var pitch_yaw := Find.numbers(row.get("view"), 2)
	var pitch := clampf(pitch_yaw[0], -89.0, 89.0)
	var yaw: float = pitch_yaw[1]
	var player: Node = probe.player()
	if player is Node3D:
		var turned := (player as Node3D).global_rotation_degrees
		(player as Node3D).global_rotation_degrees = Vector3(turned.x, yaw, turned.z)
	var view: Node = probe.view()
	if view is Camera3D:
		(view as Camera3D).global_rotation_degrees = Vector3(pitch, yaw, 0.0)
	probe.note("view turned to pitch %.1f yaw %.1f%s" % [pitch, yaw, "" if view is Camera3D else " (no 3D camera)"])


static func _place(player: Node, position: Vector3, yaw: Variant) -> void:
	## the player at `position`, facing `yaw` when given, standing still
	if player is Node3D:
		var body := player as Node3D
		body.global_position = position
		if yaw != null:
			var turned := body.global_rotation_degrees
			body.global_rotation_degrees = Vector3(turned.x, yaw, turned.z)
		if body is RigidBody3D:  # a rigid body's place is the physics server's: tell it too
			PhysicsServer3D.body_set_state((body as RigidBody3D).get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM, body.global_transform)
		body.reset_physics_interpolation()
	elif player is Node2D:
		var flat := player as Node2D
		flat.global_position = Vector2(position.x, position.y)
		if flat is RigidBody2D:
			PhysicsServer2D.body_set_state((flat as RigidBody2D).get_rid(), PhysicsServer2D.BODY_STATE_TRANSFORM, flat.global_transform)
		flat.reset_physics_interpolation()
	elif player is Control:
		(player as Control).global_position = Vector2(position.x, position.y)
	_still(player)


static func _still(player: Node) -> void:
	if player is CharacterBody3D:
		(player as CharacterBody3D).velocity = Vector3.ZERO
	elif player is RigidBody3D:
		(player as RigidBody3D).linear_velocity = Vector3.ZERO
		(player as RigidBody3D).angular_velocity = Vector3.ZERO
	elif player is CharacterBody2D:
		(player as CharacterBody2D).velocity = Vector2.ZERO
	elif player is RigidBody2D:
		(player as RigidBody2D).linear_velocity = Vector2.ZERO
		(player as RigidBody2D).angular_velocity = 0.0
