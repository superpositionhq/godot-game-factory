extends Node
## The task checker's probe (godot-game-factory tools/task_check): a timed, scripted play of the game for a task check.
## The game is started with the user arguments `-- -taskProbe <spec file>` (contract section 5): the frame at the
## spec's exact size, `shots` screenshots evenly over `seconds` of play time, the scripted inputs at their times, the
## player's position and the camera every `every` seconds, the spec's queries sampled with them, then probe.json in
## `out` and a clean exit. Without -taskProbe it does nothing.
##
## The play's clock is frames at a fixed rate (30 a second; the game is started with --fixed-fps 30): every frame is
## 1/30 s of play, however fast the machine renders, and it counts whether or not the game pauses itself. It starts
## once the play's scene is the current scene, and holds during a wait and while a scene is changing.

const Find := preload("find.gd")
const Inputs := preload("inputs.gd")
const Query := preload("query.gd")
const UiScan := preload("ui_scan.gd")

const SPEC_FORMAT := "godot-probe-play/1"
const QUERIES_FORMAT := "game-probe-queries/1"
const RESULT_FORMAT := "godot-probe/1"
const FLAG := "-taskprobe"
const PLAY_END := "TaskProbe: the play's time is up; what follows is the game closing"
const MAX_QUERIES := 256
const MAX_ERRORS := 50
const MAX_LOAD_FRAMES := 300  # the clock holds this long for one scene change at most
const OWN_SAVES := "^TaskProbe\\.[0-9a-f]{12}$"  # the user data folder the checker gives a scratch copy, and nothing else has
const ENGINE_FOLDERS := ["logs", "shader_cache", "vulkan"]  # the engine's own, in the user data folder: kept

var stamp := 0  ## goes up before the game's scripts and after them: what is looked up once a pass is kept by it
var fps := 30

var _spec: Dictionary = {}
var _refused := ""  # why the spec can't be played
var _kept := ""  # why the saved data was kept
var _out := ""
var _scene := ""
var _seconds := 20.0
var _every := 0.5
var _shots := 4
var _sound := false
var _size := Vector2i.ZERO
var _player_select: Variant = null
var _inputs: Inputs
var _queries: Array[Query] = []
var _measures: Dictionary = {}
var _errors: Array[String] = []
var _errors_seen: Dictionary = {}
var _errors_left_out := 0
var _track: Array = []
var _camera_rows: Array = []
var _shot_names: Array[String] = []
var _log: FileAccess

var _active := false
var _started := false
var _done := false
var _counted := false  # this frame is one of the play's clock (not one of a wait or of a scene change)
var _frames := 0
var _frames_waited := 0
var _shots_taken := 0
var _start_frames := 0
var _load_frames := 0
var _next_sample := 0.0
var _step_checked := false
var _size_said := false
var _no_frame_said := false
var _player: Node
var _view: Node
var _player_stamp := -1
var _view_stamp := -1
var _paced := false  # this frame takes 1/fps of real time
var _last_frame := 0  # when the frame before began, microseconds
var _pending_shots: Array[String] = []
var _pending_frames: Array = []  # [query, sample]


# ---------------------------------------------------------------- start


func _init() -> void:
	# at the earliest moment a script runs: the saved data is cleared before any other autoload reads it
	var args := OS.get_cmdline_user_args()
	var at := -1
	for i in args.size():
		if args[i].to_lower() == FLAG:
			at = i
			break
	if at < 0:
		return
	_active = true
	if at + 1 >= args.size():
		_refused = "no file is named"
		return
	var file := args[at + 1]
	if not FileAccess.file_exists(file):
		_refused = "%s couldn't be read: no such file" % file
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(file))
	if not (parsed is Dictionary):
		_refused = "%s couldn't be read: it isn't a JSON object" % file
	elif Find.text(parsed, "format") != SPEC_FORMAT:
		_refused = "%s couldn't be read: its format isn't %s" % [file, SPEC_FORMAT]
	else:
		_spec = parsed
		_out = Find.text(_spec, "out")
		# a play that runs after others starts on what they saved (the spec's `keep_saves`); any other starts clean
		if Find.flag(_spec, "keep_saves"):
			_kept = "the saved data is kept: the play runs after the plays that left it"
		else:
			_kept = _forget_saves()


func _ready() -> void:
	if not _active:
		set_process(false)
		return
	if _refused != "":
		# no play can come of it: the game ends at once, not at the checker's timeout as a game left running
		printerr("TaskProbe: the play spec " + _refused)
		_done = true
		get_tree().quit(2)
		return
	_begin()


func _begin() -> void:
	Find.probe = self
	if _out == "":
		_out = ProjectSettings.globalize_path("user://TaskProbe")
	DirAccess.make_dir_recursive_absolute(_out)
	_log = FileAccess.open(_out.path_join("probe.log"), FileAccess.WRITE)
	if _kept != "":
		note(_kept)
	_seconds = clampf(Find.num(_spec, "seconds", 20.0), 1.0, 600.0)
	_every = clampf(Find.num(_spec, "every", 0.5), 0.1, 1.0)
	_shots = clampi(roundi(Find.num(_spec, "shots", 4.0)), 0, 64)
	fps = clampi(roundi(Find.num(_spec, "fps", 30.0)), 10, 240)
	_scene = Find.text(_spec, "scene")
	_sound = Find.flag(_spec, "sound")
	if _spec.get("player") is Dictionary:
		_player_select = (_spec["player"] as Dictionary).duplicate()
		_player_select.erase("player")
		Find.check(_player_select, "the play's player select")
	var size := Find.numbers(_spec.get("size"), 2)
	if size.size() == 2 and size[0] >= 16 and size[1] >= 16:
		_size = Vector2i(roundi(size[0]), roundi(size[1]))

	# before the game's scripts in every frame (the inputs), and a child after them all (the samples); the game's
	# pause never stops either
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = -(1 << 30)
	var late := Node.new()
	late.name = "Late"
	late.set_script(preload("probe_late.gd"))
	late.process_priority = 1 << 30
	add_child(late)
	RenderingServer.frame_post_draw.connect(_frame_drawn)

	if DisplayServer.get_name() != "headless":
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	pace(false)
	_keep_step()
	_fit_frame()
	_load_queries()
	_inputs = Inputs.new(self, _spec.get("inputs"), Find.flag(_spec, "touch"))
	if _scene != "" and _current_scene() != _scene:
		if ResourceLoader.exists(_scene):
			_open_scene.call_deferred()
		else:
			error("the play's scene %s isn't in the project: the game's own main scene is played" % _scene)
			_scene = ""
	note("play: %.1f s, every %.2f s, %d shot(s), %d query(ies), scene %s, frame %s" % [
		_seconds, _every, _shots, _queries.size(), _scene if _scene != "" else "(the game's own)",
		"%dx%d" % [_size.x, _size.y] if _size != Vector2i.ZERO else "(the window's)"])


func _forget_saves() -> String:
	## A fresh start every play: what an earlier play saved (user://) is gone. Only ever in the checker's scratch copy:
	## its user data folder is named "TaskProbe." and 12 hex digits, so it is that copy's alone, never a game's own.
	## Anything else (the addon copied into a real project) keeps its saved data: the line for probe.log saying so.
	var custom: bool = ProjectSettings.get_setting("application/config/use_custom_user_dir", false)
	var name: String = ProjectSettings.get_setting("application/config/custom_user_dir_name", "")
	var own := RegEx.create_from_string(OWN_SAVES)
	if not custom or own.search(name) == null:
		return "the saved data is kept: '%s' isn't the user data folder of the checker's copy" % name
	var folder := OS.get_user_data_dir()
	if folder.get_file() != name:
		return "the saved data is kept: %s isn't this copy's own folder" % folder
	var dir := DirAccess.open(folder)
	if dir == null:
		return ""
	for sub in dir.get_directories():
		if not ENGINE_FOLDERS.has(sub) and not (_out != "" and folder.path_join(sub) == _out):
			_remove(folder.path_join(sub))
	for file in dir.get_files():
		dir.remove(file)
	return ""


static func _remove(folder: String) -> void:
	var dir := DirAccess.open(folder)
	if dir == null:
		return
	dir.include_hidden = true
	for sub in dir.get_directories():
		_remove(folder.path_join(sub))
	for file in dir.get_files():
		dir.remove(file)
	DirAccess.remove_absolute(folder)


func pace(real_time: bool) -> void:
	## Real-time pacing: on during a wait and a scene change, and always in a play that measures audio (sound plays in
	## real time); else the play runs as fast as the machine renders. The engine caps no frame rate under --fixed-fps,
	## so a paced frame waits here for the wall clock (_wait_for_clock).
	_paced = real_time or _sound
	if Engine.max_fps != 0:
		Engine.max_fps = 0


func _wait_for_clock() -> void:
	var now := Time.get_ticks_usec()
	var due := _last_frame + int(1000000.0 / fps)
	if _paced and now < due:
		OS.delay_usec(due - now)
		now = due
	_last_frame = now


func _keep_step() -> void:
	## Every frame the same step of game time. Left alone, the engine lets a frame's step drift up to half a physics
	## tick either way to smooth what it shows (its physics jitter fix), so a frame's own time would not be 1/fps.
	if Engine.physics_jitter_fix != 0.0:
		Engine.physics_jitter_fix = 0.0


func _fit_frame() -> void:
	## The frame the game shows. The game is always rendered at the project's own size (its viewport width and
	## height), whatever the window is, since a window may not fit the screen and a frame of another size would lay
	## the UI out differently; a frame that is read (a screenshot, a screen sample) is scaled to the spec's size
	## (_read_frame).
	if _size == Vector2i.ZERO:
		return
	var root := get_tree().root
	var own := Vector2i(ProjectSettings.get_setting("display/window/size/viewport_width", 0),
			ProjectSettings.get_setting("display/window/size/viewport_height", 0))
	if own.x < 16 or own.y < 16:
		own = _size
	if root.content_scale_mode != Window.CONTENT_SCALE_MODE_VIEWPORT:
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
	if root.content_scale_aspect != Window.CONTENT_SCALE_ASPECT_KEEP:
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
	if root.content_scale_size != own:
		root.content_scale_size = own
	if root.content_scale_factor != 1.0:
		root.content_scale_factor = 1.0
	if not _size_said and own.x * _size.y != own.y * _size.x:
		_size_said = true
		error("the frame asked for is %dx%d and the project's is %dx%d, of another shape: frames are stretched to fit" % [
			_size.x, _size.y, own.x, own.y])


func _load_queries() -> void:
	var asked: Variant = _spec.get("queries")
	if asked == null:
		return
	if not (asked is Dictionary):
		error("the queries are not a JSON object")
		return
	var format := Find.text(asked, "format")
	if format != QUERIES_FORMAT:
		error("queries format '%s' is not %s" % [format, QUERIES_FORMAT])
		return
	if not (asked.get("queries") is Array):
		error("the queries have no queries array")
		return
	for item: Variant in asked["queries"]:
		if not (item is Dictionary):
			error("a query is not an object")
			continue
		var id := Find.text(item, "id")
		if id == "" or _measures.has(id):
			error("a query has a missing or repeated id '%s'" % id)
			continue
		if _queries.size() >= MAX_QUERIES:
			error("more than %d queries: '%s' and later ones dropped" % [MAX_QUERIES, id])
			break
		var kind := Find.text(item, "kind")
		var file := "res://addons/task_probe/queries/%s.gd" % kind
		var q: Query
		if kind.is_valid_identifier() and ResourceLoader.exists(file):
			q = (load(file) as GDScript).new()
		else:
			error("query '%s': unknown kind '%s' (null values)" % [id, kind])
			q = Query.new()
		q.id = id
		q.kind = kind
		q.def = item
		q.probe = self
		if item.get("fields") is Array:
			for f: Variant in item["fields"]:
				if f is String and f != "" and not q.fields.has(f):
					q.fields.append(f)
		q.load_query()
		_queries.append(q)
		_measures[id] = []


func own_query(id: String, item: Dictionary) -> Query:
	## A query an input reads itself (a shot that waits for its event: inputs.gd watch_events), made and loaded as the
	## play's are (_load_queries) but never sampled with them nor written to `measures`; null, with an error, when its
	## kind is unknown.
	var kind := Find.text(item, "kind")
	var file := "res://addons/task_probe/queries/%s.gd" % kind
	if not kind.is_valid_identifier() or not ResourceLoader.exists(file):
		error("query '%s': unknown kind '%s'" % [id, kind])
		return null
	var q: Query = (load(file) as GDScript).new()
	q.id = id
	q.kind = kind
	q.def = item
	q.probe = self
	if item.get("fields") is Array:
		for f: Variant in item["fields"]:
			if f is String and f != "" and not q.fields.has(f):
				q.fields.append(f)
	q.load_query()
	return q


func _current_scene() -> String:
	var scene := get_tree().current_scene
	return scene.scene_file_path if scene != null else ""


func _open_scene() -> void:
	get_tree().change_scene_to_file(_scene)


# ---------------------------------------------------------------- what queries and inputs read


func elapsed() -> float:
	## play time, seconds
	return _frames / float(fps)


func player() -> Node:
	## The player (contract section 1), looked up once a pass; null when the scene has none.
	if _player_stamp != stamp:
		_player_stamp = stamp
		_player = _find_player()
	return _player if is_instance_valid(_player) else null


func _find_player() -> Node:
	if _player_select != null:
		return Find.first(_player_select)
	for group: String in ["player", "Player"]:
		for n in get_tree().get_nodes_in_group(group):
			if not Find.is_own(n) and Find.shown(n):
				return n
	for type: String in ["CharacterBody3D", "CharacterBody2D"]:
		var bodies := Find.of_class(type, false)
		if bodies.size() > 0:
			return bodies[0]
	return view()


func view() -> Node:
	## The camera the player sees through: the window's current Camera3D, else its current Camera2D.
	if _view_stamp != stamp:
		_view_stamp = stamp
		var root := get_tree().root
		_view = root.get_camera_3d()
		if _view == null:
			_view = root.get_camera_2d()
	return _view if is_instance_valid(_view) else null


func damage_taken(n: Node) -> Variant:
	## What the play's `damage` stages did to a node, as its take_damage returned it (inputs.gd).
	return _inputs.damage_taken(n) if _inputs != null else null


func error(message: String) -> void:
	## Something the probe couldn't read; goes to probe.json "query_errors" (once each, at most 50).
	if _errors_seen.has(message):
		return
	_errors_seen[message] = true
	note("error: " + message)
	if _errors.size() < MAX_ERRORS:
		_errors.append(message)
	else:
		_errors_left_out += 1


func note(message: String) -> void:
	## A line in the play's probe.log (beside probe.json), not in the game's own log.
	if _log != null:
		_log.store_line("%.2f [%.1f s] %s" % [elapsed(), Time.get_ticks_msec() / 1000.0, message])
		_log.flush()


func shot(name: String) -> bool:
	## A screenshot now, with the UI, named shot_<name>.png beside the evenly spaced ones (a `shot` input).
	var valid := RegEx.create_from_string("^[a-z_][a-z0-9_]{0,31}$")
	if valid.search(name) == null:
		error("a shot named '%s' isn't taken: a letter or _ first, then letters, digits, _" % name)
		return false
	_pending_shots.append("shot_%s.png" % name)
	note("screenshot shot_%s.png at %.2f s" % [name, elapsed()])
	return true


func load_scene(path: String) -> bool:
	## The play opens another scene (a `scene` input), as the game's own change_scene_to_file does.
	if not ResourceLoader.exists(path):
		error("the scene %s isn't in the project: no load" % path)
		return false
	get_tree().change_scene_to_file(path)
	note("scene %s loads at %.2f s" % [path, elapsed()])
	return true


# ---------------------------------------------------------------- the frame, before the game's scripts


func _loading() -> bool:
	## Whether the clock holds this frame for a scene that is changing (there is no current scene meanwhile). One
	## change holds it for MAX_LOAD_FRAMES at most: a game that keeps no current scene must still be played.
	if get_tree().current_scene != null:
		_load_frames = 0
		return false
	if _load_frames < MAX_LOAD_FRAMES:
		_load_frames += 1
		return true
	if _load_frames == MAX_LOAD_FRAMES:
		_load_frames += 1
		note("no scene has been the current one for %d frames: the play's clock goes on" % MAX_LOAD_FRAMES)
	return false


func _process(delta: float) -> void:
	stamp += 1
	_counted = false
	if _done:
		return
	_keep_step()
	_wait_for_clock()
	var loading := _loading()
	if not _started:
		# the play's scene must be the one in play before the clock starts
		if _scene != "" and _current_scene() != _scene:
			_start_frames += 1
			if _start_frames < 600:
				return
			error("the play's scene %s didn't become the current scene: playing %s" % [_scene, _current_scene()])
			_scene = ""
		if loading:
			return
		_started = true
		note("the play's clock starts in " + _current_scene())
	if not _step_checked and Engine.time_scale == 1.0 and _frames >= 3:
		_step_checked = true
		if absf(delta - 1.0 / fps) > 1e-4:
			error("the game isn't run with --fixed-fps %d (a frame took %.4f s of its time): the play's clock is its frames, not the game's own time" % [fps, delta])
	Find.light_tick()
	_inputs.warm(elapsed())
	_inputs.hold(elapsed())
	if _inputs.waiting:
		pace(true)  # whatever frame rate the game asked for meanwhile
		_inputs.wait_tick()
		_frame_queries()
		return
	if loading:
		pace(true)
		_frame_queries()
		return
	pace(false)
	_frames += 1
	_counted = true
	_frame_queries()
	_inputs.send(elapsed())


func _frame_queries() -> void:
	for q in _queries:
		q.frame(1.0 / fps)


# ---------------------------------------------------------------- the frame, after the game's scripts


func late() -> void:
	stamp += 1
	if _done or not _started:
		return
	if (Engine.get_process_frames() & 15) == 0:
		_fit_frame()
	_inputs.hold(elapsed())  # after every frame's game logic, the clock running or not: a hold lasts through a wait
	if not _counted:
		return  # a frame of a wait or of a scene change: the clock stands still
	var t := elapsed()
	_inputs.watch_events(t)  # a shot whose event came in this frame is taken at its end
	if t >= _next_sample - 1e-9:
		_next_sample += _every
		_take_sample(t)
	if _shots > 0 and _shots_taken < _shots and t >= _seconds * (_shots_taken + 0.5) / _shots:
		_pending_shots.append("shot_%02d.png" % _shots_taken)
		_shots_taken += 1
	if t >= _seconds + 0.5:
		# a sample that reads the frame drawn after it waits for that frame (a few frames at most)
		if (_pending_frames.size() > 0 or _pending_shots.size() > 0) and _frames_waited < 5:
			_frames_waited += 1
			return
		_finish("time")


func _take_sample(t: float) -> void:
	var who := player()
	var at: Variant = Find.place(who) if who != null else null
	_track.append([t, at.x, at.y, at.z] if at != null else [t])
	var cam := view()
	var eye: Variant = Find.camera_place(cam) if cam != null else null
	if eye != null:
		var turned: Array = Find.angles(cam) if cam is Camera3D else [0.0, 0.0, 0.0]
		var fov := 0.0
		if cam is Camera3D and (cam as Camera3D).projection == Camera3D.PROJECTION_PERSPECTIVE:
			fov = (cam as Camera3D).fov
		_camera_rows.append([t, eye.x, eye.y, eye.z, turned[0], turned[1], fov])
	for q in _queries:
		var sample := {"t": t}
		q.sample(t, sample)
		_measures[q.id].append(sample)
		if q.needs_frame():
			_pending_frames.append([q, sample])


# ---------------------------------------------------------------- the frame as drawn


func _frame_drawn() -> void:
	if _done or (_pending_shots.is_empty() and _pending_frames.is_empty()):
		return
	var image := _read_frame()
	if image != null:
		for name in _pending_shots:
			if image.save_png(_out.path_join(name)) == OK:
				_shot_names.append(name)
			else:
				error("a screenshot couldn't be written: " + name)
	_pending_shots.clear()
	for pending: Array in _pending_frames:
		(pending[0] as Query).frame_drawn(image, pending[1])
	_pending_frames.clear()


func _read_frame() -> Image:
	## The frame as displayed, UI included, without alpha, scaled to the spec's size.
	if DisplayServer.get_name() == "headless":
		return null
	var image := get_tree().root.get_texture().get_image()
	if image == null or image.is_empty():
		return null
	if image.is_compressed():
		image.decompress()
	image.convert(Image.FORMAT_RGB8)
	if _size != Vector2i.ZERO and image.get_size() != _size:
		image.resize(_size.x, _size.y, Image.INTERPOLATE_LANCZOS)
	return image


# ---------------------------------------------------------------- the end


func _exit_tree() -> void:
	if _active and _refused == "" and not _done:
		_finish("shutdown", false)  # the game quit first, through its own shutdown


func _finish(reason: String, quit: bool = true) -> void:
	_done = true
	if _inputs != null:
		_inputs.finish()
	if (_pending_shots.size() > 0 or _pending_frames.size() > 0) and not _no_frame_said:
		_no_frame_said = true
		error("the play's last frames weren't drawn%s: %d screenshot(s) and %d sample(s) are without their frame" % [
			" (it draws nothing: headless)" if DisplayServer.get_name() == "headless" else "",
			_pending_shots.size(), _pending_frames.size()])
	var who := player() if is_inside_tree() else null
	var result := {
		"format": RESULT_FORMAT, "ended": reason, "seconds": elapsed(), "scene": _current_scene() if is_inside_tree() else "",
		"player": String(who.name) if who != null else null, "inputs_sent": _inputs.sent if _inputs != null else 0,
		"inputs_missed": _inputs.missed if _inputs != null else [], "screenshots": _shot_names, "track": _track,
		"camera": _camera_rows,
	}
	if _queries.size() > 0:
		result["measures"] = _measures
	if _errors.size() > 0:
		var said: Array = _errors.duplicate()
		if _errors_left_out > 0:
			said.append("%d more in probe.log" % _errors_left_out)
		result["query_errors"] = said
	var file := FileAccess.open(_out.path_join("probe.json"), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(_clean(result), "", false, true))
		file.close()
	else:
		note("probe.json couldn't be written")
	note("the play ended: " + reason)
	if _log != null:
		_log.close()
		_log = null
	if quit:
		# the play ends as a window closed by its player does: the game is told first (what it saves on
		# NOTIFICATION_WM_CLOSE_REQUEST is there for a play that runs after this one), then the tree exits. The line
		# before it marks the play's end in the game's log: what the game prints from here on is read by no check
		print(PLAY_END)
		get_tree().root.propagate_notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
		get_tree().quit(0)


static func _clean(value: Variant) -> Variant:
	## JSON has no NaN and no infinity: null
	if value is float:
		return null if is_nan(value) or is_inf(value) else value
	if value is Array:
		var list: Array = []
		for item: Variant in value:
			list.append(_clean(item))
		return list
	if value is Dictionary:
		var map := {}
		for key: Variant in value:
			map[key] = _clean(value[key])
		return map
	return value
