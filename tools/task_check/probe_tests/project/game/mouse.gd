class_name MouseScene
extends Node3D
## The mouse scene: what a game reads of the mouse itself, each piece built in code at fractions of the frame.
## `Dial` (0.1-0.3 across and down) is a control the game draws and reads itself (game/dial.gd: _draw, _gui_input);
## `Menu` (0.6-0.8 across, 0.1-0.3 down) is a menu item painted on the canvas, which the game hit-tests itself from
## a press that no control took (_unhandled_input) and by polling the mouse every frame (Viewport.get_mouse_position,
## a canvas item's get_global_mouse_position, Input.is_mouse_button_pressed); `Pad` (centred at 0.2, 0.7) is an Area2D
## and `Block` (centred at 0.7, 0.7) a 3D body, both picked by the physics under the mouse. Every line it prints
## starts with what got it: GAME (_input), LEFTOVER (_unhandled_input), POLLED (_process), PAD, BLOCK (and DIAL).

var menu_rect := Rect2()
var _menu: Node2D
var _polled := ""
var _button_was_down := false


static func pixel(at: Vector2) -> String:
	return "%d,%d" % [roundi(at.x), roundi(at.y)]


func _ready() -> void:
	var frame := get_viewport().get_visible_rect().size
	var dial := Control.new()
	dial.name = "Dial"
	dial.set_script(preload("res://game/dial.gd"))
	dial.position = frame * Vector2(0.1, 0.1)
	dial.size = frame * Vector2(0.2, 0.2)
	add_child(dial)
	menu_rect = Rect2(frame * Vector2(0.6, 0.1), frame * Vector2(0.2, 0.2))
	_menu = Node2D.new()
	_menu.name = "Menu"
	_menu.draw.connect(func() -> void: _menu.draw_rect(menu_rect, Color(0.8, 0.6, 0.2)))
	add_child(_menu)
	_add_pad(frame)
	_add_block(frame)


func _add_pad(frame: Vector2) -> void:
	var pad := Area2D.new()
	pad.name = "Pad"
	pad.input_pickable = true
	pad.position = frame * Vector2(0.2, 0.7)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = frame * Vector2(0.2, 0.2)
	shape.shape = rect
	pad.add_child(shape)
	pad.input_event.connect(func(_viewport: Node, event: InputEvent, _shape: int) -> void: _picked("PAD", event))
	pad.mouse_entered.connect(func() -> void: print("PAD enter"))
	pad.mouse_exited.connect(func() -> void: print("PAD exit"))
	add_child(pad)


func _add_block(frame: Vector2) -> void:
	var camera := Camera3D.new()
	camera.position = Vector3(0.0, 0.0, 10.0)
	add_child(camera)
	camera.make_current()
	var block := StaticBody3D.new()
	block.name = "Block"
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(2.0, 2.0, 2.0)
	shape.shape = box
	block.add_child(shape)
	add_child(block)
	block.global_position = camera.project_position(frame * Vector2(0.7, 0.7), 10.0)
	block.input_event.connect(func(_camera: Node, event: InputEvent, _at: Vector3, _normal: Vector3, _shape: int) -> void:
		_picked("BLOCK", event))
	block.mouse_entered.connect(func() -> void: print("BLOCK enter"))
	block.mouse_exited.connect(func() -> void: print("BLOCK exit"))


func _picked(who: String, event: InputEvent) -> void:
	var press := event as InputEventMouseButton
	if press != null and press.pressed and press.button_index == MOUSE_BUTTON_LEFT:
		print("%s press at=%s" % [who, pixel(press.position)])


func _input(event: InputEvent) -> void:
	var motion := event as InputEventMouseMotion
	if motion != null:
		print("GAME motion at=%s" % pixel(motion.position))
	var press := event as InputEventMouseButton
	if press != null and press.pressed and press.button_index == MOUSE_BUTTON_LEFT:
		print("GAME press at=%s ctrl=%s" % [pixel(press.position), press.ctrl_pressed])


func _unhandled_input(event: InputEvent) -> void:
	var press := event as InputEventMouseButton
	if press != null and press.pressed and press.button_index == MOUSE_BUTTON_LEFT:
		print("LEFTOVER press at=%s menu=%s" % [pixel(press.position), menu_rect.has_point(press.position)])


func _process(_delta: float) -> void:
	var at := get_viewport().get_mouse_position()
	var said := "POLLED at=%s canvas=%s" % [pixel(at), pixel(_menu.get_global_mouse_position())]
	if said != _polled:
		_polled = said
		print(said)
	var down := Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	if down and not _button_was_down:
		print("POLLED press at=%s menu=%s" % [pixel(at), menu_rect.has_point(at)])
	_button_was_down = down
