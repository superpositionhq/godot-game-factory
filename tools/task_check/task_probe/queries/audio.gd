extends "../query.gd"
## audio: what the player hears (contract section 3, docs/task-probes.md 2.15). Every AudioStreamPlayer,
## AudioStreamPlayer2D and AudioStreamPlayer3D that is playing and matches the select, at its volume at the listener:
## its own volume times, for a placed one, its attenuation at the listener's distance. Bus volumes are left out.
## `level` and `peak` are the Master bus's mixed output since the previous sample; `started`, how many players began to
## play since then.
## "value": {"count", "audible", "volume", "max_volume", "loudest", "level", "peak", "started", "listener"}

const AUDIBLE := 0.001  # a player at this volume (-60 dB) or louder is audible

## the Master bus is tapped once, whatever the queries: reading the tap empties it
static var _tap: AudioEffectCapture
static var _tap_stamp := -1
static var _squares := 0.0
static var _frames := 0
static var _peak := 0.0
static var _level_stamp := -1
static var _level: Variant = null
static var _level_peak: Variant = null

var _sound := ""
var _bus := ""
var _owner: Dictionary = {}
var _playing: Dictionary = {}
var _counting := false
var _started := 0


func load_query() -> void:
	var select := Find.obj(def, "select")
	_sound = Find.text(select, "sound")
	_bus = Find.text(select, "sound_class")
	_owner = Find.obj(select, "owner")
	Find.check(_owner, "%s %s" % [kind, id])
	if _tap == null:
		_tap = AudioEffectCapture.new()
		_tap.buffer_length = 1.0
		AudioServer.add_bus_effect(0, _tap)


func frame(_dt: float) -> void:
	if _tap_stamp != probe.stamp:
		_tap_stamp = probe.stamp
		_drain()
	_follow()


static func _drain() -> void:
	var ready := _tap.get_frames_available()
	if ready <= 0:
		return
	for pair in _tap.get_buffer(ready):
		var loud := maxf(absf(pair.x), absf(pair.y))
		_squares += (pair.x * pair.x + pair.y * pair.y) / 2.0
		_peak = maxf(_peak, loud)
	_frames += ready


func _players() -> Array[Node]:
	## the players that play and match the select, in tree order
	var found: Array[Node] = []
	var owners: Array[Node] = []
	if not _owner.is_empty():
		owners = Find.objects(_owner)
	if not _owner.is_empty() and owners.is_empty():
		return found  # an owner select that matches nothing owns nothing
	for n in Find.all_nodes():
		if not (n is AudioStreamPlayer or n is AudioStreamPlayer2D or n is AudioStreamPlayer3D) or not bool(n.get("playing")):
			continue
		if _sound != "" and not Find.resource_name(n.get("stream")).matchn(_sound):
			continue
		if _bus != "" and not String(n.get("bus")).matchn(_bus):
			continue
		if not _owner.is_empty() and not Find.owned_by(n, owners):
			continue
		found.append(n)
	return found


func _follow() -> void:
	## the players that weren't playing in the frame before and are now
	var now := {}
	for n in _players():
		now[n.get_instance_id()] = true
		if _counting and not _playing.has(n.get_instance_id()):
			_started += 1
	_counting = true
	_playing = now


func sample(_t: float, sample: Dictionary) -> void:
	if _level_stamp != probe.stamp:
		_level_stamp = probe.stamp
		_drain()
		_level = sqrt(_squares / _frames) if _frames > 0 else null
		_level_peak = _peak if _frames > 0 else null
		_squares = 0.0
		_frames = 0
		_peak = 0.0
	_follow()
	var count := 0
	var audible := 0
	var sum := 0.0
	var loudest_volume := 0.0
	var loudest: Variant = null
	for n in _players():
		var v := _at_listener(n)
		count += 1
		if v >= AUDIBLE:
			audible += 1
		sum += v
		if loudest == null or v > loudest_volume:
			loudest_volume = v
			loudest = Find.resource_name(n.get("stream"))
	sample["value"] = {
		"count": count, "audible": audible, "volume": sum, "max_volume": loudest_volume, "loudest": loudest,
		"level": _level, "peak": _level_peak, "started": _started, "listener": _listener_name(),
	}
	_started = 0


func _listener_3d() -> Node3D:
	## where 3D sound is heard: the current AudioListener3D, else the current Camera3D
	for n: Node in probe.get_tree().root.find_children("*", "AudioListener3D", true, false):
		if (n as AudioListener3D).is_current():
			return n as Node3D
	return probe.get_tree().root.get_camera_3d()


func _listener_name() -> Variant:
	var ears := _listener_3d()
	if ears != null:
		return String(ears.name)
	var flat := probe.get_tree().root.get_camera_2d()
	return String(flat.name) if flat != null else null


func _at_listener(n: Node) -> float:
	## a player's volume at the listener: its own, linear; a 3D one's times its attenuation at the listener's distance
	## (its model, unit size and max distance, capped at max_db); a 2D one's times its fall-off to max_distance from
	## the middle of the screen
	var volume := db_to_linear(float(n.get("volume_db")))
	if n is AudioStreamPlayer3D:
		var placed := n as AudioStreamPlayer3D
		var ears := _listener_3d()
		if ears == null:
			return volume
		var d := placed.global_position.distance_to(ears.global_position)
		if placed.max_distance > 0.0 and d > placed.max_distance:
			return 0.0
		var unit := maxf(placed.unit_size, 1e-6)
		var fall := 1.0
		match placed.attenuation_model:
			AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE:
				fall = 1.0 / maxf(d / unit, 1e-6)
			AudioStreamPlayer3D.ATTENUATION_INVERSE_SQUARE_DISTANCE:
				fall = 1.0 / maxf((d / unit) * (d / unit), 1e-6)
			AudioStreamPlayer3D.ATTENUATION_LOGARITHMIC:
				fall = db_to_linear(-20.0 * log(maxf(d / unit, 1e-6)))
		var heard := minf(volume * fall, db_to_linear(placed.max_db))
		if placed.max_distance > 0.0:
			heard *= maxf(0.0, 1.0 - d / placed.max_distance)
		return heard
	if n is AudioStreamPlayer2D:
		var flat := n as AudioStreamPlayer2D
		var screen := flat.get_viewport()
		var middle := screen.get_canvas_transform().affine_inverse() * (screen.get_visible_rect().size / 2.0)
		var far := flat.global_position.distance_to(middle)
		if flat.max_distance <= 0.0 or far > flat.max_distance:
			return 0.0
		return volume * pow(1.0 - far / flat.max_distance, flat.attenuation)
	return volume
