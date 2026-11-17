extends Node
## The game's own autoload, in the project's first [autoload]: says whether the probe loaded before it and where the
## game keeps its saved data (the probe tests' project.godot also holds lines that would stand in for the probe's).


func _ready() -> void:
	print("ORDER probe_first=%s user_dir=%s" % [get_parent().get_child(0).name == "TaskProbe", OS.get_user_data_dir()])
