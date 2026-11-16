extends RefCounted
# The run: the command line, the run's files, its phases (boot, ready, go, running, the result hold, the end), the
# timing rules and the quit. Everything here runs on the main thread.
#
# Two clocks. The machine's clock stamps every row (qpc, t_ns): the engine's monotonic clock in microseconds. The
# run's own time counts the run: the time the engine has stepped, summed frame by frame. In a movie (--write-movie)
# the engine steps 1/60 s per frame however long a frame takes to render, so the run's time is frames / 60 there;
# in a run in real time it follows the machine's clock. Time limits (-maxSeconds, the result hold) are in the
# run's own time.

const Json := preload("res://addons/autoplay/autoplay_json.gd")
const Watchdog := preload("res://addons/autoplay/autoplay_watchdog.gd")

enum Phase { OFF, BOOT, WAITING_FOR_GO, RUNNING, HOLDING, DONE }

const FRAME_RATE := 60
const READY_DELAY := 1.0
const HOLD_SECONDS := 2.0
const QPC_FREQUENCY := 1000000
const RESERVED: Array[String] = ["t_ns", "qpc", "frame", "t", "event"]
const STALE: Array[String] = ["go", "ready.json", "outcome.json", "clock.json", "watchdog.json"]

var host: Node
var input: RefCounted

# --------------------------------------------------------------------------------------------- the command line

var active := false
var allow_input := false
var mute := false
var probe_play := false
var scenario := 1
var scenario_argument := 0
var seed_value := 0
var skill := 1.0
var max_seconds := 600.0
var go_timeout := 60.0
var watchdog_seconds := 120.0
var scenario_name := ""
var output_dir := ""
var build_commit := ""
var run_id := ""
var game := ""
var movie := false  # the engine writes a movie of this run (--write-movie)
var fixed_fps := 0  # the movie's frames per second; 0 without a movie
var args: PackedStringArray
var _flag_errors: Array[String] = []

# --------------------------------------------------------------------------------------------- state

var phase := Phase.OFF
var _inputs: FileAccess
var _telemetry: FileAccess
var _clock_samples: Array = []
var _watchdog: RefCounted
var _go_time := 0.0
var _go_qpc := 0
var _go_frame := 0
var _go_seen := false
var _scenario_start_time := 0.0
var _scenario_start_qpc := 0
var _scenario_start_frame := 0
var _scenario_end_time := 0.0
var _scenario_end_qpc := 0
var _scenario_end_frame := 0
var _hold_until := 0.0
var _ready_at := 0.0
var _go_deadline_usec := 0
var _next_go_poll_usec := 0
var _updates := 0
var _time := 0.0
var _tick_usec := 0
var _settings_applied := false
var _go_timed_out := false
var _score := 0.0
var _result := ""
var _extra := {}


func _init(p_host: Node) -> void:
	host = p_host
	_parse()

# --------------------------------------------------------------------------------------------- flags


func _parse() -> void:
	args = OS.get_cmdline_user_args()
	movie = OS.has_feature("movie")
	var s := value("-scenario")
	if s != "":
		if s.is_valid_int() and s.to_int() >= 1:
			scenario_argument = s.to_int()
		else:
			_flag_errors.append("-scenario %s: not a scenario number (1, 2, ...)" % s)
	scenario = scenario_argument if scenario_argument > 0 else 1
	active = flag("-autoplay")
	if not active:
		for e in _flag_errors:
			printerr("AutoPlay: " + e)
		return
	probe_play = flag("-taskProbe")
	allow_input = flag("-autoplayAllowInput")
	mute = flag("-autoplayMute")
	scenario_name = value("-scenarioName")
	seed_value = int(_number("-seed", 0.0, -2147483648.0, 2147483647.0, true))
	skill = _number("-skill", 1.0, 0.0, 1.0, false)
	max_seconds = _number("-maxSeconds", 600.0, 0.0, 86400.0, false)
	go_timeout = _number("-goTimeout", 0.0 if probe_play else 60.0, 0.0, 86400.0, false)
	watchdog_seconds = _number("-autoplayWatchdog", 120.0, 0.0, 86400.0, false)
	build_commit = value("-buildCommit")
	run_id = value("-runId")
	var dir := value("-outputDir")
	if dir == "":
		dir = "user://AutoPlay/" + Time.get_datetime_string_from_system().replace("-", "").replace(":", "").replace("T", "-")
	output_dir = ProjectSettings.globalize_path(dir).simplify_path()
	# an exported game: its exe's name; a game run from its source: the project's name
	if OS.has_feature("template"):
		game = OS.get_executable_path().get_file().get_basename()
	else:
		game = str(ProjectSettings.get_setting("application/config/name", ""))


## A flag's value among the game's own arguments: the next argument, unless that is another flag ("-5" is a value).
func value(name: String) -> String:
	return value_in(args, name)


func flag(name: String) -> bool:
	return flag_in(args, name)


static func value_in(list: PackedStringArray, name: String) -> String:
	for i in range(list.size() - 1):
		if list[i].nocasecmp_to(name) != 0:
			continue
		var v := list[i + 1]
		if v.length() > 1 and v[0] == "-" and not v.substr(1, 1).is_valid_int() and v[1] != ".":
			return ""
		return v
	return ""


static func flag_in(list: PackedStringArray, name: String) -> bool:
	for a in list:
		if a.nocasecmp_to(name) == 0:
			return true
	return false


func _number(name: String, fallback: float, low: float, high: float, integer: bool) -> float:
	var s := value(name)
	if s == "":
		return fallback
	if not (s.is_valid_int() if integer else s.is_valid_float()):
		_flag_errors.append("%s %s: not a number%s; %s is used" % [name, s, " from %d to %d" % [low, high] if integer else "", Json.number(fallback)])
		return fallback
	var v := s.to_float()
	if v < low or v > high:
		_flag_errors.append("%s %s: outside %s..%s, held to it" % [name, s, Json.number(low), Json.number(high)])
		v = clampf(v, low, high)
	return v

# --------------------------------------------------------------------------------------------- the clocks


## The machine's clock: microseconds on the engine's monotonic clock (qpc; t_ns is this times 1000).
static func qpc() -> int:
	return Time.get_ticks_usec()


## The run's own time in seconds (see the top of this file).
func now() -> float:
	return _time


## Once a frame, first of all, with the frame's delta: the run's own time moves on by what the engine stepped. The
## delta carries the game's time scale, which is taken out again (a slow-motion effect does not slow the run's
## clock); a game that stops time altogether gets the machine's clock for those frames.
func tick(delta: float) -> void:
	var q := qpc()
	var scale := Engine.time_scale
	if scale > 0.0:
		_time += delta / scale
		if movie and fixed_fps == 0 and delta > 0.0:
			fixed_fps = roundi(scale / delta)
	elif _tick_usec > 0:
		_time += (q - _tick_usec) / 1000000.0
	_tick_usec = q


func is_running() -> bool:
	return phase == Phase.RUNNING


## A clock.json sample: the machine's clock read before and after the UTC wall clock.
func _sample(label: String) -> Dictionary:
	var before := qpc()
	var unix := Time.get_unix_time_from_system()
	var after := qpc()
	var whole := int(floor(unix))
	return {
		"label": label, "qpc": before, "qpc_after": after, "t_ns": before * 1000, "unix_ns": int(unix * 1000000000.0),
		"utc": "%s.%03dZ" % [Time.get_datetime_string_from_unix_time(whole), int((unix - whole) * 1000.0)],
		"frame": Engine.get_process_frames(),
	}

# --------------------------------------------------------------------------------------------- boot


## When the autoload enters the tree, before the first scene's nodes are ready.
func boot() -> void:
	if not active or phase != Phase.OFF:
		return
	var made := DirAccess.make_dir_recursive_absolute(output_dir)
	if made == OK:
		for name in STALE:  # an earlier run's handshake in the same folder would start this one at once
			if FileAccess.file_exists(output_dir.path_join(name)):
				DirAccess.remove_absolute(output_dir.path_join(name))
		_inputs = FileAccess.open(output_dir.path_join("inputs.jsonl"), FileAccess.WRITE)
		_telemetry = FileAccess.open(output_dir.path_join("telemetry.jsonl"), FileAccess.WRITE)
	if _inputs == null or _telemetry == null:
		printerr("AutoPlay: the run's folder %s cannot be written: quitting" % output_dir)
		phase = Phase.DONE
		host.get_tree().quit(1)  # no run can come of it: at once, not after the recorder's wait for ready.json
		return
	phase = Phase.BOOT
	input_row(_header(stamp().merged({"type": "header", "schema": "autoplay-inputs/2"})))
	_telemetry_row(_header(_event("header").merged({"schema": "autoplay-telemetry/2"})))
	for e in _flag_errors:
		error(e)
	_clock_samples.append(_sample("start"))
	seed(seed_value)
	if not probe_play:
		_apply_timing()
	if mute and not movie:  # a movie's sound goes to its file, never to the speakers
		AudioServer.set_bus_mute(0, true)
	_watchdog = Watchdog.new()
	print("AutoPlay: scenario %d seed %d skill %s max %s s; the run's files in %s" % [scenario, seed_value, Json.number(skill), Json.number(max_seconds), output_dir])


## Vsync off, so frame pacing never depends on the monitor, and a 60 fps cap when the run is in real time.
func _apply_timing() -> void:
	if DisplayServer.window_get_vsync_mode() != DisplayServer.VSYNC_DISABLED:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	if not movie and Engine.max_fps != FRAME_RATE:
		Engine.max_fps = FRAME_RATE

# --------------------------------------------------------------------------------------------- every frame


## Before the game's nodes (the autoload's _process, lowest priority value).
func early_update() -> void:
	if phase == Phase.OFF or phase == Phase.DONE:
		return
	_watchdog.beat()
	_enforce()
	match phase:
		Phase.BOOT:
			_boot_frame()
		Phase.WAITING_FOR_GO:
			var q := qpc()
			if q >= _next_go_poll_usec:
				_next_go_poll_usec = q + 50000
				var go := FileAccess.file_exists(output_dir.path_join("go"))
				if go or q >= _go_deadline_usec:
					_begin_run(not go)
		Phase.RUNNING:
			input.update()
			if max_seconds > 0.0 and now() - _go_time >= max_seconds:
				_time_up()
		Phase.HOLDING:
			if now() >= _hold_until:
				_export()
				_end()
				host.get_tree().quit(0)


## After the game's nodes (autoplay_late.gd, highest priority value).
func late_update() -> void:
	if phase == Phase.OFF or phase == Phase.DONE:
		return
	input.late_update()
	if _inputs != null:
		_inputs.flush()
	if _telemetry != null:
		_telemetry.flush()


## The timing and input rules, every frame: a game that changes them gets them back.
func _enforce() -> void:
	if not allow_input:
		# never trap the cursor of the person using the machine
		match Input.mouse_mode:
			Input.MOUSE_MODE_CAPTURED, Input.MOUSE_MODE_CONFINED_HIDDEN:
				Input.mouse_mode = Input.MOUSE_MODE_HIDDEN
			Input.MOUSE_MODE_CONFINED:
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if not probe_play:  # a task check's play: its probe owns the window and the frame rate
		_apply_timing()


## After the first rendered frame: the window's rules, 1 s to settle, then ready.json.
func _boot_frame() -> void:
	if not _settings_applied:
		_updates += 1
		if _updates < 2:  # this frame's _process comes after the first frame was drawn
			return
		_settings_applied = true
		if not probe_play:
			if DisplayServer.window_get_mode() != DisplayServer.WINDOW_MODE_WINDOWED:
				DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
			if not allow_input:
				# a window that never takes the keyboard: the person using the machine keeps typing where they were
				DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, true)
		_ready_at = now() + READY_DELAY
		return
	if now() < _ready_at:
		return
	var window := DisplayServer.window_get_size()
	var viewport := Vector2i(host.get_tree().root.get_visible_rect().size)
	var mode := _window_mode()
	var ready := {
		"pid": OS.get_process_id(), "title": str(ProjectSettings.get_setting("application/config/name", "")),
		"window": window, "viewport": viewport, "fullscreen_mode": mode, "scenario": scenario,
		"scenario_name": scenario_name, "autoplay_version": host.VERSION,
	}
	ready.merge(stamp())
	if not _write_file("ready.json", Json.text(ready) + "\n"):
		error("ready.json could not be written")
	_telemetry_row(_event("autoplay_ready").merged({
		"window": window, "viewport": viewport, "fullscreen_mode": mode,
		"renderer": RenderingServer.get_current_rendering_method(), "vsync_mode": DisplayServer.window_get_vsync_mode(),
		"target_fps": Engine.max_fps, "fixed_fps": fixed_fps, "movie": movie,
	}))
	input.center(Vector2(viewport) / 2.0)
	phase = Phase.WAITING_FOR_GO
	_go_deadline_usec = qpc() + int(go_timeout * 1000000.0)
	_next_go_poll_usec = 0
	print("AutoPlay: ready (window %dx%d, frame %dx%d); waiting up to %s s for the go file" % [window.x, window.y, viewport.x, viewport.y, Json.number(go_timeout)])


func _window_mode() -> String:
	match DisplayServer.window_get_mode():
		DisplayServer.WINDOW_MODE_WINDOWED: return "Windowed"
		DisplayServer.WINDOW_MODE_MINIMIZED: return "Minimized"
		DisplayServer.WINDOW_MODE_MAXIMIZED: return "Maximized"
		DisplayServer.WINDOW_MODE_FULLSCREEN: return "FullScreenWindow"
		DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN: return "ExclusiveFullScreen"
	return ""

# --------------------------------------------------------------------------------------------- the run


func _begin_run(timed_out: bool) -> void:
	_go_timed_out = timed_out
	_go_seen = true
	_go_time = now()
	_go_qpc = qpc()
	_go_frame = Engine.get_process_frames()
	_clock_samples.append(_sample("go"))
	seed(seed_value)
	if watchdog_seconds > 0.0:
		_watchdog.arm(watchdog_seconds, "run", output_dir.path_join("watchdog.json"))
	phase = Phase.RUNNING
	_telemetry_row(_event("run_start").merged({"scenario": scenario, "seed": seed_value, "skill": Json.number(skill), "go_timed_out": timed_out}))
	print("AutoPlay: go%s; start_scenario(%d)" % [" (no go file: started at the timeout)" if timed_out else "", scenario])
	if host.start_scenario.get_connections().is_empty():
		error("the game connected nothing to AutoPlay.start_scenario")
		finish_run("error", 0.0, {"reason": "no start_scenario handler"})
		return
	host.start_scenario.emit(scenario)


func scenario_started(name: String) -> void:
	if not active:
		return
	if phase != Phase.RUNNING:
		push_warning("AutoPlay: scenario_started is only taken between go and finish_run")
		return
	if name != "":
		scenario_name = name
	if _scenario_start_qpc == 0:
		_scenario_start_time = now()
		_scenario_start_qpc = qpc()
		_scenario_start_frame = Engine.get_process_frames()
	var scene := host.get_tree().current_scene
	_telemetry_row(_event("scenario_start").merged({
		"scenario": scenario, "scenario_name": scenario_name, "scene": scene.scene_file_path if scene != null else "",
	}))
	print("AutoPlay: scenario started: " + scenario_name)


func set_score(value: float) -> void:
	if active:
		_score = value


func finish_run(result: String, final_score: float, extra: Dictionary) -> void:
	if not active or phase != Phase.RUNNING:
		return
	_scenario_end_time = now()
	_scenario_end_qpc = qpc()
	_scenario_end_frame = Engine.get_process_frames()
	_result = result
	_score = final_score
	_extra = extra
	phase = Phase.HOLDING  # the bot's calls stop here; the drop-in's own release rows follow
	input.release_all(true)
	_telemetry_row(_event("scenario_end").merged({"result": _result, "score": Json.number(_score), "extra": _extra}))
	_hold_until = now() + HOLD_SECONDS  # the result screen stays on the video
	print("AutoPlay: the run ended: %s, score %s" % [_result, Json.number(_score)])


func _time_up() -> void:
	host.timeout.emit()
	if phase == Phase.RUNNING:
		finish_run("timeout", _score, {})


## After the result hold: outcome.json.
func _export() -> void:
	var started := _scenario_start_qpc != 0
	var from_time := _scenario_start_time if started else _go_time
	var o := _header({"schema": "autoplay-outcome/2"})
	o.merge({
		"result": _result, "score": Json.number(_score),
		"duration_s": snappedf(_scenario_end_time - from_time, 0.000001),
		"run_duration_s": snappedf(_scenario_end_time - _go_time, 0.000001),
		"go_qpc": _go_qpc, "scenario_start_qpc": _scenario_start_qpc if started else null,
		"scenario_end_qpc": _scenario_end_qpc,
		"frames": _scenario_end_frame - (_scenario_start_frame if started else _go_frame),
		"inputs_injected": input.injected, "go_timed_out": _go_timed_out,
		"build_config": "debug" if OS.is_debug_build() else "release",
		"engine_version": "%d.%d.%d-%s" % [Engine.get_version_info().major, Engine.get_version_info().minor, Engine.get_version_info().patch, Engine.get_version_info().status],
		"renderer": RenderingServer.get_current_rendering_method(),
		"viewport": Vector2i(host.get_tree().root.get_visible_rect().size),
		"fixed_fps": fixed_fps, "movie": movie, "go_frame": _go_frame,
		"scenario_start_frame": _scenario_start_frame if started else null, "scenario_end_frame": _scenario_end_frame,
		"end_frame": Engine.get_process_frames(), "extra": _extra,
	})
	if not _write_file("outcome.json", Json.text(o) + "\n"):
		error("outcome.json could not be written")


## The run's last files: clock.json, telemetry run_end, the rows closed. The caller then quits the game.
func _end() -> void:
	_clock_samples.append(_sample("end"))
	_write_clock()
	_telemetry_row(_event("run_end"))
	_close_files()
	phase = Phase.DONE
	_watchdog.stop()
	print("AutoPlay: the run's files are written; the game quits")


## The game quits on its own (the game quit, the window was closed): a run that ended keeps its files; one that had
## not ended keeps what it has, with telemetry run_aborted.
func on_quitting() -> void:
	match phase:
		Phase.HOLDING:
			_export()
			_end()
		Phase.BOOT, Phase.WAITING_FOR_GO, Phase.RUNNING:
			var was := phase
			input.release_all(true)  # release rows for what the bot still held
			_telemetry_row(_event("run_aborted").merged({"phase": _phase_name(was)}))
			_clock_samples.append(_sample("end"))
			_write_clock()
			_close_files()
			phase = Phase.DONE
			_watchdog.stop()


func _phase_name(p: Phase) -> String:
	match p:
		Phase.WAITING_FOR_GO: return "waiting_for_go"
		Phase.RUNNING: return "running"
		Phase.HOLDING: return "holding"
	return "boot"

# --------------------------------------------------------------------------------------------- the files


## The fields every header and outcome.json carry.
func _header(row: Dictionary) -> Dictionary:
	row.merge({
		"autoplay_version": host.VERSION, "engine": "godot", "game": game, "run_id": run_id, "scenario": scenario,
		"scenario_name": scenario_name, "seed": seed_value, "skill": Json.number(skill),
		"max_seconds": Json.number(max_seconds), "qpc_frequency": QPC_FREQUENCY, "build_commit": build_commit,
	})
	return row


## A row's start: the stamp every row carries (t_ns, qpc, frame, t).
func stamp() -> Dictionary:
	var q := qpc()
	return {
		"t_ns": q * 1000, "qpc": q, "frame": Engine.get_process_frames(),
		"t": snappedf(now() - _go_time, 0.000001) if _go_seen else null,
	}


func _event(name: String) -> Dictionary:
	var row := stamp()
	row["event"] = name
	return row


func input_row(row: Dictionary) -> void:
	if _inputs != null:
		_inputs.store_string(Json.text(row) + "\n")


func _telemetry_row(row: Dictionary) -> void:
	if _telemetry != null:
		_telemetry.store_string(Json.text(row) + "\n")


func game_telemetry(name: String, fields: Dictionary) -> void:
	if not active or _telemetry == null or name == "":
		return
	var row := _event(name)
	for key: Variant in fields:
		if not RESERVED.has(str(key)):
			row[str(key)] = fields[key]
	_telemetry_row(row)


## A telemetry error row and the log's line.
func error(message: String) -> void:
	printerr("AutoPlay: " + message)
	if _telemetry != null:
		_telemetry_row(_event("error").merged({"message": message}))


func _write_clock() -> void:
	var c := {
		"schema": "autoplay-clock/2", "scenario": scenario, "scenario_name": scenario_name,
		"qpc_frequency": QPC_FREQUENCY, "t_ns_definition": "qpc * 1e9 / qpc_frequency", "fixed_fps": fixed_fps,
		"samples": _clock_samples,
	}
	if not _write_file("clock.json", Json.text(c) + "\n"):
		error("clock.json could not be written")


## Written whole, then renamed into place: whoever waits for the file never reads half of it.
func _write_file(name: String, text: String) -> bool:
	var path := output_dir.path_join(name)
	var part := path + ".part"
	var f := FileAccess.open(part, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(text)
	f.close()
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(path)
	return DirAccess.rename_absolute(part, path) == OK


func _close_files() -> void:
	if _inputs != null:
		_inputs.close()
	if _telemetry != null:
		_telemetry.close()
	_inputs = null
	_telemetry = null
