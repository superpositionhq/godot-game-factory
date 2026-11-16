extends CharacterBody3D
## A foe that walks to and fro along x, 2 m a second. A hit takes what health is left at most and stops it for 0.2 s;
## a shielded one takes nothing; one out of health is dead and stands.

@export var health := 100
@export var dead := false
@export var shielded := false
var tint := Color(1, 1, 1)
var last_source := ""  # who hit it last
var _way := 1.0
var _stopped := 0.0


func take_damage(amount: float, source: Node) -> float:
	last_source = String(source.name) if source != null else ""
	if dead or shielded:
		return 0.0
	var taken := minf(amount, health)
	health -= roundi(taken)
	dead = health <= 0
	_stopped = 0.2
	return taken


func _physics_process(delta: float) -> void:
	if position.x > 8.0:
		_way = -1.0
	elif position.x < 4.0:
		_way = 1.0
	_stopped = maxf(_stopped - delta, 0.0)
	velocity = Vector3.ZERO if dead or _stopped > 0.0 else Vector3(_way * 2.0, 0.0, 0.0)
	move_and_slide()
