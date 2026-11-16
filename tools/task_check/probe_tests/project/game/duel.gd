extends Node3D
## The duel scene's own logic: J is the player's blow, 10 points on every foe within 2.5 m; P pauses the game for six
## frames; O stops its time (a time scale of 0) for four.

var _stopped := 0


func _process(_delta: float) -> void:
	if _stopped > 0:
		_stopped -= 1
		if _stopped == 0:
			Engine.time_scale = 1.0


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	if event.keycode == KEY_J:
		for foe in get_tree().get_nodes_in_group("foe"):
			if foe.global_position.distance_to($Player.global_position) <= 2.5:
				foe.take_damage(10.0, $Player)
	elif event.keycode == KEY_O:
		Engine.time_scale = 0.0
		_stopped = 4
	elif event.keycode == KEY_P:
		get_tree().paused = true
		get_tree().create_timer(0.2, true, false, true).timeout.connect(func() -> void: get_tree().paused = false)
