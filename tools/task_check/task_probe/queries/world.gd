extends "../query.gd"
## world: the game as a whole (contract section 3, "world"): how slow the game's time ran and whether the game was
## paused. Both are read every frame, so a hit stop that slows the game for a few frames between two samples is read
## too.
## "value": {"time_scale" (the lowest Engine.time_scale since the previous sample), "flow" (how the game went on: 0
## in a frame the tree was paused, else Engine.time_scale; the lowest since the previous sample), "paused" (1 when
## the tree was paused in a frame since then)}

var _lowest := INF
var _flow := INF
var _paused := false


func load_query() -> void:
	known_fields(["time_scale", "flow", "paused"])


func frame(_dt: float) -> void:
	_look()


func _look() -> void:
	var paused: bool = probe.get_tree().paused
	_lowest = minf(_lowest, Engine.time_scale)
	_flow = minf(_flow, 0.0 if paused else Engine.time_scale)
	_paused = _paused or paused


func sample(_t: float, sample: Dictionary) -> void:
	_look()  # what this frame's own scripts set counts now
	sample["value"] = {"time_scale": _lowest, "flow": _flow, "paused": 1.0 if _paused else 0.0}
	_lowest = INF
	_flow = INF
	_paused = false
