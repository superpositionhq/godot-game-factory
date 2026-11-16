extends Node
## The game's scenarios, numbered 1..n as the design doc and the README's Scenarios table number them: scenario n's
## scene and name, and how a scenario starts. This script is the autoload "Scenarios".
##   - Started with `-- -scenario <n>` (and no -autoplay), the game goes straight to scenario n: past menus, tutorials
##     and popups, into its start state.
##   - In AutoPlay (`-- -autoplay -scenario <n>`, the AutoPlay drop-in in addons/autoplay/), the first scene loads as
##     usual and the drop-in emits start_scenario(n) at the recorder's go.
## Fill in SCENES and NAMES as scenarios are made. The scenario's own code applies its start state (Scenarios.current
## says which scenario it is, 0 in normal play), calls Scenarios.started() when gameplay begins, and
## AutoPlay.finish_run("win" or "lose", score) when it ends; the bot is the game's own node, acting only through
## AutoPlay's input calls while AutoPlay.is_running.

## Scenario n's scene at index n - 1, e.g. "res://scenes/Harbor.tscn". One scene may serve several scenarios.
const SCENES: Array[String] = []

## Scenario n's name at index n - 1, as the design doc names it, e.g. "First Night".
const NAMES: Array[String] = []

## The scenario being played, 0 in normal play from the menus.
var current := 0


func _ready() -> void:
	AutoPlay.start_scenario.connect(load_scenario)
	if not AutoPlay.is_active and AutoPlay.scenario_argument > 0:
		# deferred: the first scene is not in the tree yet when an autoload becomes ready
		load_scenario.call_deferred(AutoPlay.scenario_argument)


## Loads scenario n's scene (the scene's own code then applies its start state).
func load_scenario(n: int) -> void:
	if n < 1 or n > SCENES.size() or SCENES[n - 1].is_empty():
		var why := "no scene for scenario %d: Scenarios.SCENES lists %d" % [n, SCENES.size()]
		push_error(why)
		AutoPlay.finish_run("error", 0.0, {"reason": why})
		return
	current = n
	get_tree().change_scene_to_file(SCENES[n - 1])


## Call when the scenario's gameplay begins (the player has control, or the countdown starts): in AutoPlay this is the
## scenario's start, and the bot starts.
func started() -> void:
	AutoPlay.scenario_started(NAMES[current - 1] if current >= 1 and current <= NAMES.size() else "")
