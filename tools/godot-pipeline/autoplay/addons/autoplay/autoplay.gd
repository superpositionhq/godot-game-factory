extends Node
## AutoPlay: the game plays itself for a recording. A game started with `-autoplay` after `--` reads the run's flags,
## ignores the real keyboard, waits for the recorder's "go" file, emits start_scenario(n), and writes the run's files:
## every input the bot injects (inputs.jsonl), the game's telemetry (telemetry.jsonl), the result (outcome.json) and
## the clock (clock.json). It quits when the run ends. The picture and the sound are the engine's own movie
## (--write-movie), which the recorder starts the game with.
##
## The game supplies three things: a start_scenario handler (load scenario n and apply its start state), the calls
## scenario_started(name) and finish_run(result, score), and the bot, a node of its own that acts only through the
## input calls below. Copy this folder into the game unchanged (addons/autoplay/) and name autoplay.gd as the autoload
## "AutoPlay": every game then writes identical files. Without -autoplay nothing here acts, so the game calls it
## unconditionally.
##
## Two flags work with or without -autoplay: `-size <W>x<H>` (the exact frame size of the run) and
## `-shots <n> -shotDir <dir> -seconds <s>` (n PNG frames over s seconds, then quit).

## The drop-in's version, written as autoplay_version in every file: it goes up when the files change shape.
const VERSION := 1

const _Run := preload("res://addons/autoplay/autoplay_run.gd")
const _Input := preload("res://addons/autoplay/autoplay_input.gd")
const _Tools := preload("res://addons/autoplay/autoplay_tools.gd")
const _Late := preload("res://addons/autoplay/autoplay_late.gd")

## Required: emitted once at go with the scenario number. Load the scenario's scene and apply its start state, past
## menus, tutorials and popups. Connect from something that exists from boot (another autoload).
signal start_scenario(n: int)

## Emitted when -maxSeconds have passed since go. A handler may compute a final score and call finish_run itself;
## otherwise the run ends with finish_run("timeout", the last set_score).
signal timeout()

var _run: RefCounted
var _input: RefCounted
var _tools: RefCounted

# --------------------------------------------------------------------------------------------- the command line

## Started with -autoplay.
var is_active: bool:
	get: return _run.active

## From "go" to finish_run: the only time the bot acts.
var is_running: bool:
	get: return _run.is_running()

## The run's scenario: -scenario <n> (1-based, the design doc's numbers), 1 without it.
var scenario: int:
	get: return _run.scenario

## -scenario <n> as given on the command line, with or without -autoplay; 0 without it. A game started with
## -scenario n alone goes straight to scenario n's start state.
var scenario_argument: int:
	get: return _run.scenario_argument

## The scenario's name: what scenario_started was given, else -scenarioName, else "".
var scenario_name: String:
	get: return _run.scenario_name

## -seed: the engine's random numbers are seeded with it at boot and again at go; seed the game's own
## RandomNumberGenerators from it. Determinism is not required.
var seed: int:
	get: return _run.seed_value

## -skill, 0..1: 0 a clumsy novice (slow reactions, noisy aim, poor choices, still trying), 1 the best the bot can do
## (a competent human; it need not win).
var skill: float:
	get: return _run.skill

## -maxSeconds: the run ends with result "timeout" this long after go, in the run's own time (0 = no limit).
var max_seconds: float:
	get: return _run.max_seconds

## The run's folder (-outputDir), "" when AutoPlay is off.
var output_dir: String:
	get: return _run.output_dir if _run.active else ""


func _init() -> void:
	_run = _Run.new(self)
	_input = _Input.new(self, _run)
	_tools = _Tools.new(self, _run)
	_run.input = _input
	process_mode = Node.PROCESS_MODE_ALWAYS  # a paused game is still a run
	process_priority = -1000000000  # before the game's nodes; autoplay_late.gd runs after them


func _enter_tree() -> void:
	_tools.enter_tree()
	_run.boot()
	var late: Node = _Late.new()
	late.name = "Late"
	late.owner_script = self
	add_child(late)


func _process(delta: float) -> void:
	_run.tick(delta)
	_run.early_update()
	_tools.update()


func _late_process() -> void:
	_run.late_update()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_run.on_quitting()
	elif what == NOTIFICATION_PREDELETE and _run != null:
		_run.input = null  # the run and its input hold each other: let them go


func _exit_tree() -> void:
	_run.on_quitting()

# --------------------------------------------------------------------------------------------- the game's side

## Call when the scenario's gameplay begins (its scene loaded, the player has control or the countdown starts), with
## the scenario's name ("First Night"): telemetry scenario_start; the bot starts now. The first call of a run marks the
## start; one after an in-run restart only adds a telemetry row.
func scenario_started(scenario_title: String) -> void:
	_run.scenario_started(scenario_title)


## Keep the score current: a run that times out ends with it.
func set_score(score: float) -> void:
	_run.set_score(score)


## End the run: result "win", "lose" or "abort" (the bot is stuck: the game's call); "timeout" comes from the
## drop-in, "error" from a run that could not start its scenario. `extra` holds the game's own results (stars, lap
## times, times spotted) for outcome.json. Held inputs are released; the result stays on screen 2 s, then the files
## are finished and the game quits. A restart inside a run is not the end of the run.
func finish_run(result: String, score: float = 0.0, extra: Dictionary = {}) -> void:
	_run.finish_run(result, score, extra)


## One telemetry row: the event's name and its fields (strings, numbers, bools, Vector2/3 as [x, y, z], a Quaternion
## as its euler angles [pitch, yaw, roll] in degrees, arrays and dictionaries of those). Every game writes "score"
## {score, delta, reason} on every change, "state" at 10 Hz {position [x, y, z] m, rotation [pitch, yaw, roll],
## velocity, and its own numbers} and "restart" {reason}; add the genre's own events freely. Written from boot to the
## end of the run; the keys t_ns, qpc, frame, t and event are the drop-in's.
func telemetry(event: String, fields: Dictionary = {}) -> void:
	_run.game_telemetry(event, fields)

# --------------------------------------------------------------------------------------------- the bot's input

## Press a key or button and keep it down until release: "<Keyboard>/w", "<Keyboard>/space", "<Mouse>/leftButton",
## "<Gamepad>/buttonSouth", "<Gamepad>/dpad/up"; a trigger takes 0..1 ("<Gamepad>/rightTrigger", 0.6), a stick a
## Vector2 ("<Gamepad>/leftStick", x right, y down, each -1..1). A value of 0 releases it. Only while is_running.
func hold(control: String, value: Variant = 1.0) -> void:
	_input.hold(control, value)


## Let go of a control held with hold.
func release(control: String) -> void:
	_input.release(control)


## Let go of every held control and every finger.
func release_all() -> void:
	_input.release_all(false)


## Move the mouse by this many viewport pixels for one frame (look; x right, y down); call it every frame the bot
## turns.
func mouse_delta(delta: Vector2) -> void:
	_input.mouse_delta(delta)


## Turn the mouse wheel for one frame (y: forward is positive).
func scroll(y: float, x: float = 0.0) -> void:
	_input.scroll(Vector2(x, y))


## Point the mouse at a viewport position (pixels, origin top left); a following hold/release of
## "<Mouse>/leftButton" clicks there. The video shows no system cursor: draw a visible cursor at
## get_viewport().get_mouse_position() so it shows where the bot points.
func set_cursor(viewport_position: Vector2) -> void:
	_input.set_cursor(viewport_position)

# --------------------------------------------------------------------------------------------- touch

## Put finger `finger` (0..9) down at a viewport position (pixels, origin top left).
func touch_down(finger: int, pos: Vector2) -> void:
	_input.touch_down(finger, pos)


## Move a finger that is down.
func touch_move(finger: int, pos: Vector2) -> void:
	_input.touch_move(finger, pos)


## Lift a finger.
func touch_up(finger: int) -> void:
	_input.touch_up(finger)


## A finger put down at `pos` and lifted the next frame, or after `hold_s` seconds (a long press, a button kept
## down). The drop-in lifts it; taps and drags of different fingers may overlap.
func tap(pos: Vector2, hold_s: float = 0.0, finger: int = 0) -> void:
	_input.tap(pos, hold_s, finger)


## A finger put down at the first of `points`, moved through the others evenly over `over_s` seconds, kept at the
## last for `hold_s` seconds, then lifted: a swipe, a slider, a virtual stick pushed over and held there.
func drag(points: Array, over_s: float, hold_s: float = 0.0, finger: int = 0) -> void:
	_input.drag(points, over_s, hold_s, finger)


## The Android back button: the go-back request a phone sends (NOTIFICATION_WM_GO_BACK_REQUEST) and its key
## (KEY_BACK), pressed for one frame.
func back() -> void:
	_input.back()
