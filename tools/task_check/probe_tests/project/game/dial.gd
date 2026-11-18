extends Control
## A control the game draws (_draw) and reads the mouse in (_gui_input) itself, with no Button behind it: it prints
## each mouse motion and left press it gets, at the event's position (the control's own units) and its global one.


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.2, 0.5, 0.8))


func _gui_input(event: InputEvent) -> void:
	var motion := event as InputEventMouseMotion
	if motion != null:
		print("DIAL motion at=%s window=%s" % [MouseScene.pixel(motion.position), MouseScene.pixel(motion.global_position)])
	var press := event as InputEventMouseButton
	if press != null and press.pressed and press.button_index == MOUSE_BUTTON_LEFT:
		print("DIAL press at=%s window=%s" % [MouseScene.pixel(press.position), MouseScene.pixel(press.global_position)])
