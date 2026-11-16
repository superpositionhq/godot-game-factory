extends CharacterBody3D
## A foe that walks to and fro along x, 2 m a second. A hit takes what health is left at most and stops it for 0.2 s,
## with a spark below it that rises for 0.1 s and goes; a shielded one takes nothing; one out of health is dead and
## stands.

@export var health := 100
@export var dead := false
@export var shielded := false
var tint := Color(1, 1, 1)
var last_source := ""  # who hit it last
var locked: int:  # a property nothing can write
	get:
		return 7
var _spark: Node3D
var _spark_left := 0.0
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
	if _spark == null:
		_spark = Node3D.new()
		_spark.name = "Spark"
		add_child(_spark)
		_spark_left = 0.1
	return taken


func _physics_process(delta: float) -> void:
	if position.x > 8.0:
		_way = -1.0
	elif position.x < 4.0:
		_way = 1.0
	_stopped = maxf(_stopped - delta, 0.0)
	if _spark != null:
		_spark.position.y += 0.1
		_spark_left -= delta
		if _spark_left <= 0.0:
			_spark.queue_free()
			_spark = null
	velocity = Vector3.ZERO if dead or _stopped > 0.0 else Vector3(_way * 2.0, 0.0, 0.0)
	move_and_slide()
