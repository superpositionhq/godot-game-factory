extends Node2D
## The second scene's player: it walks right, 100 units a second.


func _process(delta: float) -> void:
	position.x += 100.0 * delta
