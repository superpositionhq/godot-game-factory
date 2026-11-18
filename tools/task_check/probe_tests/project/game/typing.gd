extends Control
## The typing scene: where a key goes. A text field (`NameField`, a LineEdit) and a button (`Apply`) that take the
## keyboard focus when clicked, and three input actions of the game's own: jump (J), save (Ctrl+S) and dash (the left
## Shift alone: bound by its physical key and its side, as the editor binds "Left Shift"). Each key prints a STAGE line
## at every stage the engine hands it to, in order: `input` (_input), `field` or `button` (the focused control's
## gui_input), `shortcut` (_shortcut_input), `unhandled_key` (_unhandled_key_input), `unhandled` (_unhandled_input).
## The field prints TYPED and its text when it changes, the button CLICKED when pressed, _unhandled_input ACTION and
## each action a key there fires, and _process HELD when a polled state changes (Input.is_action_pressed of each
## action, Input.is_key_pressed of J).

const ACTIONS := ["jump", "save", "dash"]
const SIDES := ["", "(left)", "(right)"]  # by KeyLocation
var _held := {}


func _ready() -> void:
	var frame := get_viewport().get_visible_rect().size
	_bind("jump", KEY_J, false, KEY_LOCATION_UNSPECIFIED, false)
	_bind("save", KEY_S, true, KEY_LOCATION_UNSPECIFIED, false)
	_bind("dash", KEY_SHIFT, false, KEY_LOCATION_LEFT, true)
	var field := LineEdit.new()
	field.name = "NameField"
	field.position = frame * Vector2(0.1, 0.1)
	field.size = frame * Vector2(0.3, 0.08)
	field.text_changed.connect(func(text: String) -> void: print("TYPED ", text))
	field.gui_input.connect(_stage.bind("field"))
	add_child(field)
	var apply := Button.new()
	apply.name = "Apply"
	apply.text = "Apply"
	apply.position = frame * Vector2(0.1, 0.4)
	apply.size = frame * Vector2(0.2, 0.08)
	apply.pressed.connect(func() -> void: print("CLICKED Apply"))
	apply.gui_input.connect(_stage.bind("button"))
	add_child(apply)


static func _bind(action: String, code: Key, ctrl: bool, side: KeyLocation, physical: bool) -> void:
	if InputMap.has_action(action):
		return
	InputMap.add_action(action)
	var key := InputEventKey.new()
	if physical:
		key.physical_keycode = code
	else:
		key.keycode = code
	key.ctrl_pressed = ctrl
	key.location = side
	InputMap.action_add_event(action, key)


func _stage(event: InputEvent, stage: String) -> void:
	var key := event as InputEventKey
	if key == null:
		return
	var held := ("shift+" if key.shift_pressed else "") + ("ctrl+" if key.ctrl_pressed else "") + \
		("alt+" if key.alt_pressed else "")
	print("STAGE %s %s%s%s %s" % [stage, held, OS.get_keycode_string(key.keycode), SIDES[key.location],
		"down" if key.pressed else "up"])


func _input(event: InputEvent) -> void:
	_stage(event, "input")


func _shortcut_input(event: InputEvent) -> void:
	_stage(event, "shortcut")


func _unhandled_key_input(event: InputEvent) -> void:
	_stage(event, "unhandled_key")


func _unhandled_input(event: InputEvent) -> void:
	_stage(event, "unhandled")
	for action: String in ACTIONS:
		if event.is_action_pressed(action):
			print("ACTION ", action)


func _process(_delta: float) -> void:
	var now := {}
	for action: String in ACTIONS:
		now[action] = Input.is_action_pressed(action)
	now["key_j"] = Input.is_key_pressed(KEY_J)
	for what: String in now:
		if now[what] != _held.get(what, false):
			print("HELD %s %s" % [what, "down" if now[what] else "up"])
	_held = now
