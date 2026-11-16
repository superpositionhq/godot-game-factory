extends Node
## The play loop's late half: after every script of the game in a frame (the probe's own node runs before them all),
## so a sample reads the frame's own state.


func _process(_delta: float) -> void:
	get_parent().late()
