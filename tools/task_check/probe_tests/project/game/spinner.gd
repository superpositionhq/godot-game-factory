class_name Spinner
extends MeshInstance3D
## A box that turns a quarter of a turn a second.

var turns := true


func _process(delta: float) -> void:
	if turns:
		rotate_y(deg_to_rad(90.0) * delta)
