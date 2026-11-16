extends Button
## The first scene's on-screen button: counts the taps it gets, so a new project shows that touch reaches the game.
## A touch reaches a Control as a mouse click (project setting emulate_mouse_from_touch), so `pressed` is all a
## button needs; _gui_input below reads the touch itself, as a control that tracks a finger does.

var taps := 0
var touches := 0


func _ready() -> void:
	pressed.connect(_on_pressed)


func _on_pressed() -> void:
	taps += 1
	text = "Taps: %d" % taps


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch and event.pressed:
		touches += 1
