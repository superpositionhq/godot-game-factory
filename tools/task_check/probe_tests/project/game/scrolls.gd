extends Control
## The scrolls scene: lists a click scrolls (one inside another, below the frame), Controls that only clip, and
## buttons with something over them. Each press of a button prints its name; a press on what lies over a button prints
## TOOK and that one's name, so a raw click shows where the engine's GUI sends it. M shows an exclusive dialog for 30
## frames.

var _modal_frames := 0


func _ready() -> void:
	for n: Node in find_children("*", "BaseButton", true, false):
		var button := n as BaseButton
		button.pressed.connect(func() -> void: print("PRESSED ", button.name))
	for path: String in ["Lid", "Glass", "Mesh", "Shutter", "Top/Banner"]:
		var over := get_node(path) as Control
		over.gui_input.connect(func(event: InputEvent) -> void:
			var press := event as InputEventMouseButton
			if press != null and press.pressed and press.button_index == MOUSE_BUTTON_LEFT:
				print("TOOK ", over.name))


func _unhandled_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key != null and key.pressed and not key.echo and key.keycode == KEY_M and _modal_frames == 0:
		($Modal as AcceptDialog).popup_centered(Vector2i(400, 200))
		_modal_frames = 30


func _process(_delta: float) -> void:
	if _modal_frames > 0:
		_modal_frames -= 1
		if _modal_frames == 0:
			($Modal as AcceptDialog).hide()
