extends Control
## The shown-text scene: words a click finds by their text as shown, on controls that are no buttons. A row drawn in
## three labels side by side ("1", "BUY RANK", "300 PT") on a panel (`Row`), a label on a panel (`Sign`, "Open Map"),
## a label and its shadow on a panel (`ExitPanel`, "Exit" twice, 2 px apart), "Shop" shown in two places, a label
## drawn see-through ("Ghost"), and a sign in the 3D world (`Dock`, a Label3D "DOCK 7" in front of the camera). Each
## panel prints PRESSED and RELEASED with its name and the frame when the left button goes down and up on it; a K key
## prints KEY and its frame.


func _ready() -> void:
	var frame := get_viewport().get_visible_rect().size
	var unit := frame / Vector2(1920, 1080)  # laid out in the project's 1920x1080, whatever the window
	var row := _panel("Row", Rect2(100, 100, 1000, 80), unit)
	_label(row, "Rank", "1", Rect2(20, 10, 40, 60), unit)
	_label(row, "Item", "BUY RANK", Rect2(100, 10, 300, 60), unit)
	_label(row, "Price", "300 PT", Rect2(460, 10, 200, 60), unit)
	var sign := _panel("Sign", Rect2(100, 300, 400, 80), unit)
	_label(sign, "Words", "Open Map", Rect2(20, 10, 300, 60), unit)
	var exit := _panel("ExitPanel", Rect2(100, 500, 400, 80), unit)
	_label(exit, "Shadow", "Exit", Rect2(22, 12, 200, 60), unit)
	_label(exit, "Words", "Exit", Rect2(20, 10, 200, 60), unit)
	_label(self, "ShopHigh", "Shop", Rect2(1300, 700, 300, 60), unit)
	_label(self, "ShopLow", "Shop", Rect2(1300, 900, 300, 60), unit)
	var ghost := _label(self, "Faint", "Ghost", Rect2(1300, 300, 300, 60), unit)
	ghost.self_modulate = Color(1, 1, 1, 0)
	var world := Node3D.new()
	world.name = "World"
	add_child(world)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 0, 4)
	world.add_child(camera)
	camera.make_current()
	var dock := Label3D.new()
	dock.name = "Dock"
	dock.text = "DOCK 7"
	dock.font_size = 64
	world.add_child(dock)


func _input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key != null and key.pressed and key.keycode == KEY_K:
		print("KEY K ", Engine.get_process_frames())


func _panel(name_: String, at: Rect2, unit: Vector2) -> Panel:
	var panel := Panel.new()
	panel.name = name_
	panel.position = at.position * unit
	panel.size = at.size * unit
	panel.gui_input.connect(func(event: InputEvent) -> void:
		var press := event as InputEventMouseButton
		if press != null and press.button_index == MOUSE_BUTTON_LEFT:
			print("PRESSED " if press.pressed else "RELEASED ", panel.name, " ", Engine.get_process_frames()))
	add_child(panel)
	return panel


func _label(holder: Control, name_: String, text: String, at: Rect2, unit: Vector2) -> Label:
	var label := Label.new()
	label.name = name_
	label.text = text
	label.position = at.position * unit
	label.size = at.size * unit
	holder.add_child(label)
	return label
