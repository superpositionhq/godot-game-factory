extends "../query.gd"
## spawns: nodes of a class (as an object select's `component`) that appeared (came into the tree, or were shown) or
## went (were freed, taken out of the tree or hidden), counted every frame since the play's clock started (contract
## section 3, "spawns"); cumulative, the checker differences them. The nodes are compared frame to frame: those there
## when the clock starts aren't spawned; a pooled node counts each time it comes and goes; one that comes and goes
## within one frame isn't seen; a scene change brings and takes its nodes.
## "value": {"spawned", "destroyed"} | null when no node can be of that class.

var _type := ""
var _before: Dictionary = {}
var _counting := false
var _spawned := 0
var _destroyed := 0


func load_query() -> void:
	_type = Find.text(def, "component")
	if _type == "":
		probe.error("%s %s: no component named" % [kind, id])
	elif not Find.names_class(_type):
		probe.error("%s %s: no component type %s" % [kind, id, _type])
		_type = ""


func frame(_dt: float) -> void:
	_count()


func _count() -> void:
	if _type == "":
		return
	var now := {}
	for n in Find.of_class(_type, false):
		now[n.get_instance_id()] = true
	if _counting:
		for key: int in now:
			if not _before.has(key):
				_spawned += 1
		for key: int in _before:
			if not now.has(key):
				_destroyed += 1
	_counting = true  # the clock's first frame: what is there already
	_before = now


func sample(_t: float, sample: Dictionary) -> void:
	if _type == "":
		sample["value"] = null
		return
	_count()  # this frame's own comings and goings (after the game's scripts) count now, not next frame
	sample["value"] = {"spawned": _spawned, "destroyed": _destroyed}
