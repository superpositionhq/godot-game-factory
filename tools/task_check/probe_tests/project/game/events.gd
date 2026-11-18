extends Control
## The events scene: 20 frames after Space its banner shows, and from the next frame on its score counts up by one a
## frame (the label reads "SCORE <n>").

var score := 0
var _wait := 0


func _input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key != null and key.pressed and key.keycode == KEY_SPACE and _wait == 0 and not $Banner.visible:
		_wait = 20


func _process(_delta: float) -> void:
	if $Banner.visible:
		score += 1
		$Score.text = "SCORE %d" % score
	elif _wait > 0:
		_wait -= 1
		if _wait == 0:
			$Banner.show()
