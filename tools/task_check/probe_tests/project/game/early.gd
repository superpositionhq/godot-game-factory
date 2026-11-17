extends Node
## A game autoload set before every section of project.godot (`autoload/Early=...`), which the engine would load first:
## says that it loaded, and whether the probe loaded before it.


func _ready() -> void:
	var probe := get_parent().get_node_or_null("TaskProbe")
	print("EARLY loaded after_probe=%s" % [probe != null and probe.get_index() < get_index()])
