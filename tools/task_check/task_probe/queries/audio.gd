extends "../query.gd"
## audio: what the player hears (contract section 3, docs/task-probes.md 2.16). Every AudioStreamPlayer,
## AudioStreamPlayer2D and AudioStreamPlayer3D that is playing and matches the select, at its volume at the listener:
## its own volume times, for a placed one, its attenuation at the listener's distance. Bus volumes are left out.
## `level` and `peak` are the Master bus's mixed output since the previous sample; `started`, how many matching players
## were found playing that weren't the frame before. The sounds that start are watched every frame, whatever the
## samples, by the playback each play() makes: a player that begins to play, one played again while it plays, and one
## that began and ended between two frames (its `finished` signal tells); `started_audible` counts those audible as
## they started and `starts` lists them all by their stream's name.
## "value": {"count", "audible", "volume", "max_volume", "loudest", "level", "peak", "started", "started_audible",
## "starts": [{"t", "sound", "named"}], "starts_total", "listener", "voices_unseen" (true, only when a matching
## player's stream plays voices of its own)}; null when the select's `near` point didn't resolve

const AUDIBLE := 0.001  # a player at this volume (-60 dB) or louder is audible
const MAX_STARTS := 64  # the starts a sample lists at most
const IDLE_PASSES := 4  # passes without sound after which a player's `finished` is no longer waited for

## the Master bus is tapped once, whatever the queries: reading the tap empties it
static var _tap: AudioEffectCapture
static var _tap_stamp := -1
static var _squares := 0.0
static var _frames := 0
static var _peak := 0.0
static var _level_stamp := -1
static var _level: Variant = null
static var _level_peak: Variant = null

## the players are watched once, whatever the queries: every start of the play, in order
static var _watching := false
static var _watch_stamp := -1
static var _known: Dictionary = {}  # instance id -> {ref, playback, open, idle}
static var _events: Array[Dictionary] = []  # {t, sound, named, bus, line, place, audible}

var _sound := ""
var _bus := ""
var _owner: Dictionary = {}
var _near: Dictionary = {}
var _next := 0  # the first start this query hasn't looked at
var _playing: Dictionary = {}
var _counting := false
var _started := 0
var _lost := false  # the near's point didn't resolve at a look since the previous sample
var _voices := false  # a matching player played a stream whose voices can't be seen
var _started_audible := 0
var _starts: Array = []
var _starts_total := 0


func load_query() -> void:
	var select := Find.obj(def, "select")
	_sound = Find.text(select, "sound")
	_bus = Find.text(select, "sound_class")
	_owner = Find.obj(select, "owner")
	_near = Find.obj(select, "near")
	Find.check(_owner, "%s %s" % [kind, id])
	Find.check(Find.obj(Find.obj(_near, "point"), "object"), "%s %s" % [kind, id])
	if _tap == null:
		_tap = AudioEffectCapture.new()
		_tap.buffer_length = 1.0
		AudioServer.add_bus_effect(0, _tap)


func frame(_dt: float) -> void:
	if _tap_stamp != probe.stamp:
		_tap_stamp = probe.stamp
		_drain()
	_follow()


static func _is_player(n: Node) -> bool:
	return n is AudioStreamPlayer or n is AudioStreamPlayer2D or n is AudioStreamPlayer3D


static func _meet(n: Node) -> void:
	## a player the watch didn't know: its `finished` signal tells of a sound no frame saw playing
	if not _is_player(n) or Find.is_own(n) or _known.has(n.get_instance_id()):
		return
	var id := n.get_instance_id()
	_known[id] = {"ref": weakref(n), "playback": 0, "open": false, "idle": 0}
	n.connect("finished", _ended.bind(id))


static func _ended(id: int) -> void:
	var e: Variant = _known.get(id)
	if e == null:
		return
	var n: Node = e["ref"].get_ref()
	if not e["open"] and n != null:
		_note(n)  # it began and ended between two looks
	e["open"] = false
	e["playback"] = 0


static func _playback(n: Node) -> int:
	## which playback a player plays: every play() makes a new one, a pause keeps it; 0 when it plays nothing
	if not n.is_inside_tree() or not bool(n.call("has_stream_playback")):
		return 0
	var playback: Variant = n.call("get_stream_playback")
	return (playback as Object).get_instance_id() if playback is Object and is_instance_valid(playback) else 0


static func _watch() -> void:
	## once a pass: which players began to play since the pass before
	var probe: Node = Find.probe
	if probe == null or _watch_stamp == probe.stamp:
		return
	_watch_stamp = probe.stamp
	var first := not _watching
	if first:
		_watching = true
		probe.get_tree().node_added.connect(_meet)
		for n in Find.all_nodes():
			_meet(n)
	for id: int in _known.keys():
		var e: Dictionary = _known[id]
		var n: Node = e["ref"].get_ref()
		if n == null:
			_known.erase(id)
			continue
		var playback := _playback(n)
		if playback != 0:
			# those playing when the watch begins were not started in the play
			if not first and playback != e["playback"]:
				_note(n)
			e["open"] = true
			e["idle"] = 0
			e["playback"] = playback
		else:
			e["idle"] += 1
			if e["idle"] > IDLE_PASSES:
				e["open"] = false  # stopped without ending: no `finished` comes
				e["playback"] = 0


static func _voiced(stream: Variant) -> bool:
	## a stream that plays voices of its own inside one playback, which nothing lists
	return stream is AudioStreamPolyphonic or stream is AudioStreamGenerator


static func _holds_others(stream: Variant) -> bool:
	## a stream that picks or mixes other streams: its own name says nothing of the sound that plays
	if not (stream is AudioStream):
		return false
	for type: String in ["AudioStreamRandomizer", "AudioStreamPolyphonic", "AudioStreamPlaylist", "AudioStreamInteractive",
			"AudioStreamSynchronized"]:
		if (stream as AudioStream).is_class(type):
			return true
	return false


static func _note(n: Node) -> void:
	var stream: Variant = n.get("stream")
	var name := Find.resource_name(stream)
	var line: Array[int] = []  # the player and the nodes above it: an owner select matches one of them
	var at := n
	while at != null:
		line.append(at.get_instance_id())
		at = at.get_parent()
	_events.append({
		"t": Find.probe.elapsed(), "sound": name, "named": name != "" and not _holds_others(stream),
		"bus": String(n.get("bus")), "line": line,
		"place": Find.place(n) if n is AudioStreamPlayer2D or n is AudioStreamPlayer3D else null,
		"audible": _at_listener(n) * _bus_gain(String(n.get("bus"))) >= AUDIBLE,
	})


static func _bus_gain(bus: String) -> float:
	## the gain of a bus and of those it sends to, down to Master; 0 when one of them is muted
	var index := maxi(AudioServer.get_bus_index(bus), 0)
	var gain := 1.0
	for i in 16:
		if AudioServer.is_bus_mute(index):
			return 0.0
		gain *= db_to_linear(AudioServer.get_bus_volume_db(index))
		if index == 0:
			break
		index = maxi(AudioServer.get_bus_index(AudioServer.get_bus_send(index)), 0)
	return gain


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
	var centre: Variant = Find.point(Find.obj(_near, "point")) if not _near.is_empty() else null
	if not _near.is_empty() and centre == null:
		_lost = true
	for n in Find.all_nodes():
		if not _is_player(n) or not bool(n.get("playing")):
			continue
		if not _near.is_empty() and not (not (n is AudioStreamPlayer) and Find.within(_near, centre, Find.place(n))):
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
	## the players that weren't playing in the frame before and are now (`started`), then the starts since this query
	## last looked that its select matches
	var now := {}
	for n in _players():
		now[n.get_instance_id()] = true
		if _counting and not _playing.has(n.get_instance_id()):
			_started += 1
		if _voiced(n.get("stream")):
			_voices = true
	_counting = true
	_playing = now
	_watch()
	if _next >= _events.size():
		return
	var owners := {}
	if not _owner.is_empty():
		for o in Find.objects(_owner):
			owners[o.get_instance_id()] = true
	var centre: Variant = Find.point(Find.obj(_near, "point")) if not _near.is_empty() else null
	if not _near.is_empty() and centre == null:
		_lost = true
	while _next < _events.size():
		var e := _events[_next]
		_next += 1
		if _sound != "" and not String(e["sound"]).matchn(_sound):
			continue
		if _bus != "" and not String(e["bus"]).matchn(_bus):
			continue
		if not _owner.is_empty():
			var owned := false
			for id: int in e["line"]:
				owned = owned or owners.has(id)
			if not owned:
				continue
		if not _near.is_empty() and not Find.within(_near, centre, e["place"]):
			continue
		_starts_total += 1
		if e["audible"]:
			_started_audible += 1
		if _starts.size() < MAX_STARTS:
			_starts.append({"t": e["t"], "sound": e["sound"], "named": e["named"]})


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
		"level": _level, "peak": _level_peak, "started": _started, "started_audible": _started_audible,
		"starts": _starts, "starts_total": _starts_total, "listener": _listener_name(),
	}
	if _voices:
		sample["value"]["voices_unseen"] = true
	if _lost:
		sample["value"] = null  # near a point that wasn't there: nothing can be said of what plays near it
	_started = 0
	_started_audible = 0
	_starts = []
	_starts_total = 0
	_lost = false
	_voices = false


static func _listener_3d() -> Node3D:
	## where 3D sound is heard: the current AudioListener3D, else the current Camera3D
	var root: Window = Find.probe.get_tree().root
	for n: Node in root.find_children("*", "AudioListener3D", true, false):
		if (n as AudioListener3D).is_current():
			return n as Node3D
	return root.get_camera_3d()


func _listener_name() -> Variant:
	var ears := _listener_3d()
	if ears != null:
		return String(ears.name)
	var flat := probe.get_tree().root.get_camera_2d()
	return String(flat.name) if flat != null else null


static func _at_listener(n: Node) -> float:
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
