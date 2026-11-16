extends Node
# The end of every frame: processed after the game's nodes, so the frame's hold rows and the flush of the run's files
# come after everything the bot did in it.

var owner_script: Node


func _init() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = 1000000000


func _process(_delta: float) -> void:
	owner_script._late_process()
