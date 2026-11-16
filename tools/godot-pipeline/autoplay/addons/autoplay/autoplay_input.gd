extends RefCounted
# The bot's input: keys, mouse buttons and movement, a gamepad, and fingers on a touch screen, each sent to the game
# as the InputEvent a real device sends (Input.parse_input_event, flushed at once). The game's actions, its _input
# handlers and its Control nodes read them exactly as they read real devices. Every change is a row of inputs.jsonl,
# with the control named as an input-system path ("<Keyboard>/w", "<Touchscreen>/touch0"). An input reaches the game
# inside the call that sends it.

const Json := preload("res://addons/autoplay/autoplay_json.gd")

enum Kind { KEY, MOUSE_BUTTON, PAD_BUTTON, TRIGGER, STICK, TOUCH, BACK }

const PAD_DEVICE := 0
const MAX_FINGERS := 10

const KEYS := {
	"space": KEY_SPACE, "enter": KEY_ENTER, "tab": KEY_TAB, "backquote": KEY_QUOTELEFT, "quote": KEY_APOSTROPHE,
	"semicolon": KEY_SEMICOLON, "comma": KEY_COMMA, "period": KEY_PERIOD, "slash": KEY_SLASH,
	"backslash": KEY_BACKSLASH, "leftBracket": KEY_BRACKETLEFT, "rightBracket": KEY_BRACKETRIGHT, "minus": KEY_MINUS,
	"equals": KEY_EQUAL, "upArrow": KEY_UP, "downArrow": KEY_DOWN, "leftArrow": KEY_LEFT, "rightArrow": KEY_RIGHT,
	"escape": KEY_ESCAPE, "backspace": KEY_BACKSPACE, "pageDown": KEY_PAGEDOWN, "pageUp": KEY_PAGEUP,
	"home": KEY_HOME, "end": KEY_END, "insert": KEY_INSERT, "delete": KEY_DELETE, "capsLock": KEY_CAPSLOCK,
	"numLock": KEY_NUMLOCK, "printScreen": KEY_PRINT, "scrollLock": KEY_SCROLLLOCK, "pause": KEY_PAUSE,
	"contextMenu": KEY_MENU, "leftShift": KEY_SHIFT, "rightShift": KEY_SHIFT, "shift": KEY_SHIFT,
	"leftCtrl": KEY_CTRL, "rightCtrl": KEY_CTRL, "ctrl": KEY_CTRL, "leftAlt": KEY_ALT, "rightAlt": KEY_ALT,
	"alt": KEY_ALT, "leftMeta": KEY_META, "rightMeta": KEY_META, "numpadEnter": KEY_KP_ENTER,
	"numpadDivide": KEY_KP_DIVIDE, "numpadMultiply": KEY_KP_MULTIPLY, "numpadPlus": KEY_KP_ADD,
	"numpadMinus": KEY_KP_SUBTRACT, "numpadPeriod": KEY_KP_PERIOD,
}

const MOUSE_BUTTONS := {
	"leftButton": MOUSE_BUTTON_LEFT, "rightButton": MOUSE_BUTTON_RIGHT, "middleButton": MOUSE_BUTTON_MIDDLE,
	"forwardButton": MOUSE_BUTTON_XBUTTON2, "backButton": MOUSE_BUTTON_XBUTTON1,
}

# the gamepad's controls by every name an input-system path gives them (the aliases a/cross, b/circle ... included)
const PAD_NAMES := {
	"buttonSouth": "buttonSouth", "a": "buttonSouth", "cross": "buttonSouth",
	"buttonEast": "buttonEast", "b": "buttonEast", "circle": "buttonEast",
	"buttonWest": "buttonWest", "x": "buttonWest", "square": "buttonWest",
	"buttonNorth": "buttonNorth", "y": "buttonNorth", "triangle": "buttonNorth",
	"leftShoulder": "leftShoulder", "rightShoulder": "rightShoulder", "start": "start", "select": "select",
	"leftStickPress": "leftStickPress", "rightStickPress": "rightStickPress",
	"dpad/up": "dpad/up", "dpad/down": "dpad/down", "dpad/left": "dpad/left", "dpad/right": "dpad/right",
	"leftTrigger": "leftTrigger", "rightTrigger": "rightTrigger", "leftStick": "leftStick", "rightStick": "rightStick",
}

const PAD_BUTTONS := {
	"buttonSouth": JOY_BUTTON_A, "buttonEast": JOY_BUTTON_B, "buttonWest": JOY_BUTTON_X, "buttonNorth": JOY_BUTTON_Y,
	"leftShoulder": JOY_BUTTON_LEFT_SHOULDER, "rightShoulder": JOY_BUTTON_RIGHT_SHOULDER, "start": JOY_BUTTON_START,
	"select": JOY_BUTTON_BACK, "leftStickPress": JOY_BUTTON_LEFT_STICK, "rightStickPress": JOY_BUTTON_RIGHT_STICK,
	"dpad/up": JOY_BUTTON_DPAD_UP, "dpad/down": JOY_BUTTON_DPAD_DOWN, "dpad/left": JOY_BUTTON_DPAD_LEFT,
	"dpad/right": JOY_BUTTON_DPAD_RIGHT,
}

var host: Node
var run: RefCounted

## inject rows written: outcome.json's inputs_injected.
var injected := 0

var _held := {}  # path -> the held control
var _gestures := {}  # finger -> the tap or drag the drop-in is carrying out
var _described := {}
var _refused := {}
var _lower := {}  # each table's names in lower case -> the name as the table spells it
var _cursor := Vector2.ZERO
var _cursor_logged := false
var _button_mask := 0


func _init(p_host: Node, p_run: RefCounted) -> void:
	host = p_host
	run = p_run
	for table: Dictionary in [KEYS, MOUSE_BUTTONS, PAD_NAMES]:
		for name: String in table:
			_lower[name.to_lower()] = name

# --------------------------------------------------------------------------------------------- the controls


## The mouse at the frame's centre before go (not a row: it is not the bot's input).
func center(pos: Vector2) -> void:
	_cursor = pos


## A viewport position as the window's, where input events arrive: the root window maps it back.
func _window_xform() -> Transform2D:
	return host.get_tree().root.get_final_transform()


func _send(event: InputEvent) -> void:
	Input.parse_input_event(event)
	Input.flush_buffered_events()


func _refuse(path: String, why: String) -> Dictionary:
	if not _refused.has(path):
		_refused[path] = true
		run.error("input %s: %s" % [path, why])
	return {}


## A control path read as one of the bot's controls; {} (and one error row per path) for anything else.
func _resolve(path: String) -> Dictionary:
	var slash := path.find("/")
	if slash < 3 or path[0] != "<" or path[slash - 1] != ">":
		return _refuse(path, "a control is <Keyboard>/<key>, <Mouse>/<button>, <Gamepad>/<control> or <Touchscreen>/touch<n>")
	var device := path.substr(1, slash - 2).to_lower()
	var rest := path.substr(slash + 1)
	var low := rest.to_lower()
	match device:
		"keyboard":
			var code := KEY_NONE
			var name := ""
			if low.length() == 1 and (low >= "a" and low <= "z" or low >= "0" and low <= "9"):
				code = low.to_upper().unicode_at(0) as Key
				name = low
			elif low.begins_with("numpad") and low.length() == 7 and low.substr(6).is_valid_int():
				code = (KEY_KP_0 + low.substr(6).to_int()) as Key
				name = low
			elif low.begins_with("f") and low.substr(1).is_valid_int() and low.substr(1).to_int() in range(1, 25):
				code = (KEY_F1 + low.substr(1).to_int() - 1) as Key
				name = low
			elif _lower.has(low) and KEYS.has(_lower[low]):
				name = _lower[low]
				code = KEYS[name]
			else:
				code = OS.find_keycode_from_string(rest)  # the engine's own name of a key ("Back", "VolumeUp")
				name = OS.get_keycode_string(code)
			if code == KEY_NONE:
				return _refuse(path, "the keyboard has no key " + rest)
			return {"path": "<Keyboard>/" + name, "kind": Kind.KEY, "code": code}
		"mouse":
			if not (_lower.has(low) and MOUSE_BUTTONS.has(_lower[low])):
				return _refuse(path, "the cursor moves with set_cursor" if low.begins_with("position")
						else "the mouse moves with mouse_delta" if low.begins_with("delta")
						else "the wheel turns with scroll" if low.begins_with("scroll")
						else "the mouse has no button " + rest)
			return {"path": "<Mouse>/" + _lower[low], "kind": Kind.MOUSE_BUTTON, "code": MOUSE_BUTTONS[_lower[low]]}
		"gamepad":
			if not (_lower.has(low) and PAD_NAMES.has(_lower[low])):
				return _refuse(path, "the gamepad has no control " + rest)
			var name: String = PAD_NAMES[_lower[low]]
			if PAD_BUTTONS.has(name):
				return {"path": "<Gamepad>/" + name, "kind": Kind.PAD_BUTTON, "code": PAD_BUTTONS[name]}
			if name.ends_with("Trigger"):
				return {"path": "<Gamepad>/" + name, "kind": Kind.TRIGGER, "left": name == "leftTrigger"}
			return {"path": "<Gamepad>/" + name, "kind": Kind.STICK, "left": name == "leftStick"}
		"touchscreen":
			if low == "back":
				return _refuse(path, "the back button is pressed with back()")
			if low.begins_with("touch") and low.substr(5).is_valid_int() and low.substr(5).to_int() in range(MAX_FINGERS):
				return {"path": "<Touchscreen>/touch%d" % low.substr(5).to_int(), "kind": Kind.TOUCH, "finger": low.substr(5).to_int()}
			return _refuse(path, "a finger is <Touchscreen>/touch0 .. touch9")
	return _refuse(path, "no device %s: the bot has <Keyboard>, <Mouse>, <Gamepad> and <Touchscreen>" % path.substr(1, slash - 2))


func _key_held(code: Key) -> bool:
	for c: Dictionary in _held.values():
		if c.kind == Kind.KEY and c.code == code:
			return true
	return false


## The events of one change of a control, sent in order.
func _apply(c: Dictionary, value: Variant) -> void:
	match c.kind:
		Kind.KEY:
			var on: bool = value != 0.0
			var ev := InputEventKey.new()
			ev.keycode = c.code
			ev.physical_keycode = c.code
			ev.key_label = c.code
			ev.pressed = on
			var shift: bool = _key_held(KEY_SHIFT) or (on and c.code == KEY_SHIFT)
			ev.shift_pressed = shift
			ev.ctrl_pressed = _key_held(KEY_CTRL) or (on and c.code == KEY_CTRL)
			ev.alt_pressed = _key_held(KEY_ALT) or (on and c.code == KEY_ALT)
			ev.meta_pressed = _key_held(KEY_META) or (on and c.code == KEY_META)
			if on and c.code >= KEY_SPACE and c.code <= KEY_ASCIITILDE:  # a printable key types its character
				var ch := char(c.code)
				ev.unicode = (ch if shift else ch.to_lower()).unicode_at(0)
			_send(ev)
		Kind.MOUSE_BUTTON:
			var on: bool = value != 0.0
			var bit := 1 << (int(c.code) - 1)
			_button_mask = (_button_mask | bit) if on else (_button_mask & ~bit)
			var ev := InputEventMouseButton.new()
			ev.button_index = c.code
			ev.pressed = on
			ev.button_mask = _button_mask
			ev.position = _window_xform() * _cursor
			ev.global_position = ev.position
			_send(ev)
		Kind.PAD_BUTTON:
			var ev := InputEventJoypadButton.new()
			ev.device = PAD_DEVICE
			ev.button_index = c.code
			ev.pressed = value != 0.0
			ev.pressure = 1.0 if ev.pressed else 0.0
			_send(ev)
		Kind.TRIGGER:
			_axis(JOY_AXIS_TRIGGER_LEFT if c.left else JOY_AXIS_TRIGGER_RIGHT, clampf(value, 0.0, 1.0))
		Kind.STICK:
			var v: Vector2 = value
			_axis(JOY_AXIS_LEFT_X if c.left else JOY_AXIS_RIGHT_X, clampf(v.x, -1.0, 1.0))
			_axis(JOY_AXIS_LEFT_Y if c.left else JOY_AXIS_RIGHT_Y, clampf(v.y, -1.0, 1.0))
		Kind.BACK:
			var ev := InputEventKey.new()
			ev.keycode = KEY_BACK
			ev.physical_keycode = KEY_BACK
			ev.pressed = value != 0.0
			if ev.pressed:  # as a phone does: the request to the scene tree, then the key
				var root := host.get_tree().root
				root.propagate_notification(Node.NOTIFICATION_WM_GO_BACK_REQUEST)
				root.go_back_requested.emit()
			_send(ev)


func _axis(axis: JoyAxis, value: float) -> void:
	var ev := InputEventJoypadMotion.new()
	ev.device = PAD_DEVICE
	ev.axis = axis
	ev.axis_value = value
	_send(ev)


## An event like the one the control sends, to ask the InputMap which actions it drives.
func _probe_event(c: Dictionary) -> InputEvent:
	match c.kind:
		Kind.KEY:
			var ev := InputEventKey.new()
			ev.keycode = c.code
			ev.physical_keycode = c.code
			ev.pressed = true
			return ev
		Kind.MOUSE_BUTTON:
			var ev := InputEventMouseButton.new()
			ev.button_index = c.code
			ev.pressed = true
			return ev
		Kind.PAD_BUTTON:
			var ev := InputEventJoypadButton.new()
			ev.device = PAD_DEVICE
			ev.button_index = c.code
			ev.pressed = true
			return ev
		Kind.TRIGGER:
			var ev := InputEventJoypadMotion.new()
			ev.device = PAD_DEVICE
			ev.axis = JOY_AXIS_TRIGGER_LEFT if c.left else JOY_AXIS_TRIGGER_RIGHT
			ev.axis_value = 1.0
			return ev
	return null


## The first time the bot uses a control: a control_info row with the game's input actions it drives.
func _describe(c: Dictionary) -> void:
	if _described.has(c.path):
		return
	_described[c.path] = true
	var actions: Array[String] = []
	var events: Array[InputEvent] = []
	if c.kind == Kind.STICK:
		for axis: JoyAxis in ([JOY_AXIS_LEFT_X, JOY_AXIS_LEFT_Y] if c.left else [JOY_AXIS_RIGHT_X, JOY_AXIS_RIGHT_Y]):
			for side: float in [-1.0, 1.0]:
				var ev := InputEventJoypadMotion.new()
				ev.device = PAD_DEVICE
				ev.axis = axis
				ev.axis_value = side
				events.append(ev)
	elif c.kind == Kind.BACK:
		var ev := InputEventKey.new()
		ev.keycode = KEY_BACK
		ev.physical_keycode = KEY_BACK
		ev.pressed = true
		events.append(ev)
	else:
		var ev := _probe_event(c)
		if ev != null:
			events.append(ev)
	for action: StringName in InputMap.get_actions():
		for ev in events:
			if InputMap.event_is_action(ev, action) and not actions.has(String(action)):
				actions.append(String(action))
	var row: Dictionary = run.stamp()
	row.merge({"type": "control_info", "key": c.path, "actions": actions})
	run.input_row(row)


func _logged(c: Dictionary, value: Variant) -> Variant:
	match c.kind:
		Kind.STICK, Kind.TOUCH:
			return value
		Kind.TRIGGER:
			return Json.number(clampf(value, 0.0, 1.0))
	return 1 if value != 0.0 else 0


func _row(type: String, c: Dictionary, value: Variant, edge: String) -> void:
	var row: Dictionary = run.stamp()
	row.merge({"type": type, "key": c.path, "value": _logged(c, value), "edge": edge})
	run.input_row(row)
	if type == "inject":
		injected += 1


func _is_zero(c: Dictionary, value: Variant) -> bool:
	if c.kind == Kind.STICK:
		return value is Vector2 and value == Vector2.ZERO
	return (value is float or value is int) and value == 0.0

# --------------------------------------------------------------------------------------------- the bot's calls


func hold(control: String, value: Variant) -> void:
	if not run.is_running():
		return
	var c := _resolve(control)
	if c.is_empty():
		return
	if c.kind == Kind.TOUCH:
		if value is Vector2:
			touch_down(c.finger, value)
		else:
			_refuse(control, "a finger takes a Vector2: where it is on the screen")
		return
	if c.kind == Kind.STICK and not value is Vector2:
		_refuse(control, c.path + " takes a Vector2")
		return
	if c.kind != Kind.STICK:
		if value is bool:
			value = 1.0 if value else 0.0
		if not (value is float or value is int):
			_refuse(control, c.path + " takes a number")
			return
		value = float(value)
	if _is_zero(c, value):
		release(c.path)
		return
	var h: Dictionary = _held.get(c.path, {})
	if not h.is_empty() and h.value == value:
		return  # as it is: the frame's hold row says so
	_describe(c)
	var edge := "down" if h.is_empty() else "hold"
	if h.is_empty():
		h = c
		_held[c.path] = h
	h.value = value
	h.frame = Engine.get_process_frames()
	_apply(h, value)
	_row("inject", h, value, edge)


func release(control: String) -> void:
	if not run.is_running():
		return
	var h: Dictionary = _held.get(control, {})
	if h.is_empty():
		# the bot may name it another way ("<keyboard>/W"): read it as a control first
		var c := _resolve(control)
		if c.is_empty():
			return
		h = _held.get(c.path, {})
		if h.is_empty():
			return
	_let_go(h, "inject")


func _let_go(h: Dictionary, type: String) -> void:
	_held.erase(h.path)
	if h.kind == Kind.TOUCH:
		_gestures.erase(h.finger)
		var ev := InputEventScreenTouch.new()
		ev.index = h.finger
		ev.position = _window_xform() * (h.value as Vector2)
		ev.pressed = false
		_send(ev)
		_row(type, h, h.value, "up")
		return
	var zero: Variant = Vector2.ZERO if h.kind == Kind.STICK else 0.0
	_apply(h, zero)
	_row(type, h, zero, "up")


## Every held control let go: inject rows ("up") from the bot, release rows at the run's end.
func release_all(at_end: bool) -> void:
	if not at_end and not run.is_running():
		return
	for h: Dictionary in _held.values().duplicate():
		_let_go(h, "release" if at_end else "inject")
	_gestures.clear()


func mouse_delta(delta: Vector2) -> void:
	if not run.is_running() or delta == Vector2.ZERO:
		return
	var xf := _window_xform()
	var ev := InputEventMouseMotion.new()
	ev.position = xf * _cursor
	ev.global_position = ev.position
	ev.relative = xf.basis_xform(delta)
	ev.screen_relative = ev.relative
	ev.button_mask = _button_mask
	_send(ev)
	_impulse("<Mouse>/delta", delta, [])


func scroll(amount: Vector2) -> void:
	if not run.is_running() or amount == Vector2.ZERO:
		return
	var buttons: Array[MouseButton] = []
	if amount.y != 0.0:
		buttons.append(MOUSE_BUTTON_WHEEL_UP if amount.y > 0.0 else MOUSE_BUTTON_WHEEL_DOWN)
	if amount.x != 0.0:
		buttons.append(MOUSE_BUTTON_WHEEL_RIGHT if amount.x > 0.0 else MOUSE_BUTTON_WHEEL_LEFT)
	var probes: Array[InputEvent] = []
	for button in buttons:
		for pressed: bool in [true, false]:
			var ev := InputEventMouseButton.new()
			ev.button_index = button
			ev.pressed = pressed
			ev.factor = absf(amount.y if button in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] else amount.x)
			ev.button_mask = _button_mask
			ev.position = _window_xform() * _cursor
			ev.global_position = ev.position
			if pressed:
				probes.append(ev.duplicate())
			_send(ev)
	_impulse("<Mouse>/scroll", amount, probes)


func _impulse(path: String, value: Vector2, probes: Array[InputEvent]) -> void:
	if not _described.has(path):
		_described[path] = true
		var actions: Array[String] = []
		for action: StringName in InputMap.get_actions():
			for ev in probes:
				if InputMap.event_is_action(ev, action) and not actions.has(String(action)):
					actions.append(String(action))
		var info: Dictionary = run.stamp()
		info.merge({"type": "control_info", "key": path, "actions": actions})
		run.input_row(info)
	var row: Dictionary = run.stamp()
	row.merge({"type": "inject", "key": path, "value": value, "edge": "impulse"})
	run.input_row(row)
	injected += 1


func set_cursor(pos: Vector2) -> void:
	if not run.is_running():
		return
	if _cursor_logged and pos.distance_squared_to(_cursor) < 1e-4:
		return
	var xf := _window_xform()
	var ev := InputEventMouseMotion.new()
	ev.position = xf * pos
	ev.global_position = ev.position
	ev.relative = xf.basis_xform(pos - _cursor)
	ev.screen_relative = ev.relative
	ev.button_mask = _button_mask
	_cursor = pos
	_cursor_logged = true
	_send(ev)
	var row: Dictionary = run.stamp()
	row.merge({"type": "cursor", "key": "<Mouse>/position", "value": pos})
	run.input_row(row)

# --------------------------------------------------------------------------------------------- touch


func _finger(finger: int) -> Dictionary:
	if finger < 0 or finger >= MAX_FINGERS:
		_refuse("<Touchscreen>/touch%d" % finger, "a finger is 0..%d" % (MAX_FINGERS - 1))
		return {}
	return {"path": "<Touchscreen>/touch%d" % finger, "kind": Kind.TOUCH, "finger": finger}


func touch_down(finger: int, pos: Vector2) -> void:
	if not run.is_running():
		return
	var c := _finger(finger)
	if c.is_empty():
		return
	if _held.has(c.path):
		touch_move(finger, pos)
		return
	_describe(c)
	c.value = pos
	c.frame = Engine.get_process_frames()
	_held[c.path] = c
	var ev := InputEventScreenTouch.new()
	ev.index = finger
	ev.position = _window_xform() * pos
	ev.pressed = true
	_send(ev)
	_row("inject", c, pos, "down")


func touch_move(finger: int, pos: Vector2) -> void:
	if not run.is_running():
		return
	var h: Dictionary = _held.get("<Touchscreen>/touch%d" % finger, {})
	if h.is_empty() or (h.value as Vector2) == pos:
		return
	var xf := _window_xform()
	var ev := InputEventScreenDrag.new()
	ev.index = finger
	ev.position = xf * pos
	ev.relative = xf.basis_xform(pos - (h.value as Vector2))
	ev.screen_relative = ev.relative
	ev.velocity = ev.relative * float(run.fixed_fps if run.fixed_fps > 0 else run.FRAME_RATE)
	ev.screen_velocity = ev.velocity
	ev.pressure = 1.0
	h.value = pos
	h.frame = Engine.get_process_frames()
	_send(ev)
	_row("inject", h, pos, "hold")


func touch_up(finger: int) -> void:
	if not run.is_running():
		return
	var h: Dictionary = _held.get("<Touchscreen>/touch%d" % finger, {})
	if not h.is_empty():
		_let_go(h, "inject")


func tap(pos: Vector2, hold_s: float, finger: int) -> void:
	drag([pos], 0.0, hold_s, finger)


func drag(points: Array, over_s: float, hold_s: float, finger: int) -> void:
	if not run.is_running() or points.is_empty() or _finger(finger).is_empty():
		return
	var path: Array[Vector2] = []
	for p: Variant in points:
		if not p is Vector2:
			_refuse("<Touchscreen>/touch%d" % finger, "a drag's points are Vector2 viewport positions")
			return
		path.append(p)
	touch_up(finger)  # a finger carries one touch at a time
	var lengths: Array[float] = [0.0]
	for i in range(1, path.size()):
		lengths.append(lengths[i - 1] + path[i - 1].distance_to(path[i]))
	touch_down(finger, path[0])
	_gestures[finger] = {
		"points": path, "lengths": lengths, "over": maxf(over_s, 0.0), "hold": maxf(hold_s, 0.0),
		"start": run.now(), "frame": Engine.get_process_frames(),
		"arrived": 0.0 if path.size() == 1 else -1.0,  # a tap is at its spot from the start
	}


func back() -> void:
	if not run.is_running():
		return
	var c := {"path": "<Touchscreen>/back", "kind": Kind.BACK}
	if _held.has(c.path):
		return
	_describe(c)
	c.value = 1.0
	c.frame = Engine.get_process_frames()
	c.until = c.frame + 1
	_held[c.path] = c
	_apply(c, 1.0)
	_row("inject", c, 1.0, "down")

# --------------------------------------------------------------------------------------------- every frame


## The start of every frame of the run: the taps and drags under way move on, and the back button comes up.
func update() -> void:
	var frame := Engine.get_process_frames()
	var back_held: Dictionary = _held.get("<Touchscreen>/back", {})
	if not back_held.is_empty() and frame >= back_held.until:
		_let_go(back_held, "inject")
	for finger: int in _gestures.keys():
		var g: Dictionary = _gestures.get(finger, {})
		if g.is_empty() or frame <= g.frame:
			continue
		var elapsed: float = run.now() - g.start
		var points: Array[Vector2] = g.points
		var lengths: Array[float] = g.lengths
		if g.arrived < 0.0:
			var u := 1.0 if g.over <= 0.0 else clampf(elapsed / g.over, 0.0, 1.0)
			touch_move(finger, _along(points, lengths, u))
			if u >= 1.0:
				g.arrived = elapsed
				if points.size() > 1:
					continue  # the game sees the last spot for a frame before the finger lifts
		if g.arrived >= 0.0 and elapsed - g.arrived >= g.hold:
			touch_up(finger)


## The point a share `u` of the way along a path.
func _along(points: Array[Vector2], lengths: Array[float], u: float) -> Vector2:
	var total := lengths[lengths.size() - 1]
	if points.size() == 1 or total <= 0.0:
		return points[points.size() - 1]
	var d := u * total
	for i in range(1, points.size()):
		if d <= lengths[i]:
			var span := lengths[i] - lengths[i - 1]
			return points[i - 1].lerp(points[i], 0.0 if span <= 0.0 else (d - lengths[i - 1]) / span)
	return points[points.size() - 1]


## The end of every frame of the run: a hold row for each control held through it.
func late_update() -> void:
	if _held.is_empty() or not run.is_running():
		return
	var frame := Engine.get_process_frames()
	for h: Dictionary in _held.values():
		if h.frame >= frame:
			continue
		h.frame = frame
		_row("inject", h, h.value, "hold")
