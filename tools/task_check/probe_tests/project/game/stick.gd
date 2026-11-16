extends Control
## A virtual stick: the finger that goes down on it pushes the player the way it is dragged.

@export var player: NodePath

var _finger := -1
var _origin := Vector2.ZERO


func _input(event: InputEvent) -> void:
	var body := get_node(player)
	if event is InputEventScreenTouch:
		if event.pressed and _finger < 0 and get_global_rect().has_point(event.position):
			_finger = event.index
			_origin = event.position
		elif not event.pressed and event.index == _finger:
			_finger = -1
			body.stick = Vector2.ZERO
	elif event is InputEventScreenDrag and event.index == _finger:
		body.stick = ((event.position - _origin) / 100.0).limit_length(1.0)
