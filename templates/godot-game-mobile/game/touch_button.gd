extends Button
## The first scene's on-screen button: counts the taps it gets, so a new project shows that touch reaches the game.
## It reads the touches themselves in _gui_input, for any finger: the click a touch is also turned into (project
## setting emulate_mouse_from_touch) comes from the first finger alone, so a control that relies on `pressed` never
## sees a second finger that goes down while another is held.

var taps := 0
## The fingers that are down on this button, by index.
var fingers := {}


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed:
			fingers[event.index] = true
		elif fingers.erase(event.index):
			taps += 1
			text = "Taps: %d" % taps
