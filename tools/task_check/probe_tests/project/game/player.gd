extends CharacterBody3D
## The player: it moves on W/A/S/D and where the virtual stick is pushed, 4 m a second.

const SPEED := 4.0
const KEYS := {"move_forward": KEY_W, "move_back": KEY_S, "move_left": KEY_A, "move_right": KEY_D}

var stick := Vector2.ZERO  # set by the virtual stick
var health := 75


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
