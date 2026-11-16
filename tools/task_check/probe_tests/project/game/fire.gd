extends Panel
## A touch button: it counts every finger that goes down on it, whichever finger (a Button node presses for the first
## finger alone).

var fires := 0


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch and event.pressed:
		fires += 1
		$Text.text = "FIRE %d" % fires
