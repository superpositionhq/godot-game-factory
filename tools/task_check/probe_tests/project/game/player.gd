extends CharacterBody3D
## The player: it moves on W/A/S/D and where the virtual stick is pushed, 4 m a second. A hit slows the game to a
## quarter of its pace for three frames.

const SPEED := 4.0
const KEYS := {"move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D}

var stick := Vector2.ZERO  # set by the virtual stick
var health := 75
var last_source := ""  # who hit it last
var _slow := 0  # frames the game still runs slowly after a hit


func _ready() -> void:
	for action: String in KEYS:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
			var key := InputEventKey.new()
			key.physical_keycode = KEYS[action]
			InputMap.action_add_event(action, key)


func _physics_process(_delta: float) -> void:
	var push := Input.get_vector("move_left", "move_right", "move_forward", "move_back") + stick
	velocity = Vector3(push.x, 0.0, push.y).limit_length(1.0) * SPEED
	move_and_slide()


func take_damage(amount: float, source: Node) -> float:
	health -= roundi(amount)
	last_source = String(source.name) if source != null else ""
	Engine.time_scale = 0.25
	_slow = 3
	return amount


func _process(_delta: float) -> void:
	if _slow > 0:
		_slow -= 1
		if _slow == 0:
			Engine.time_scale = 1.0
