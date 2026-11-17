extends Node3D
## The crates scene: a crate made each way a build may break one, whole until B breaks them. Built in code, so each
## crate's parts are said in one place.

const OUT := 0.5  ## seconds the pieces take to fly apart

var _broken := -1.0
var _pieces: Array[MeshInstance3D] = []
var _bodies: Array[RigidBody3D] = []


func _ready() -> void:
	var camera := Camera3D.new()
	camera.position = Vector3(0, 3, 12)
	add_child(camera)
	# one that breaks by hiding its whole mesh and showing its pieces, which fly apart
	var hide := _crate("HideCrate", -4.0)
	hide.add_child(_box("Whole", Vector3.ZERO, Vector3.ONE))
	for corner: Vector3 in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(-1, 0, 1), Vector3(1, 0, 1)]:
		var piece := _box("Piece", corner * 0.25, Vector3.ONE * 0.5)
		piece.visible = false
		hide.add_child(piece)
		_pieces.append(piece)
	# one whose break is an animation: its lid lifts and a bone of its rig with it, no physics
	var played := _crate("AnimCrate", 0.0)
	played.add_child(_box("Body", Vector3.ZERO, Vector3.ONE))
	played.add_child(_box("Lid", Vector3(0, 0.5, 0), Vector3(1, 0.1, 1)))
	var rig := Skeleton3D.new()
	rig.name = "Rig"
	rig.add_bone("root")
	rig.add_bone("lid")
	rig.set_bone_parent(1, 0)
	rig.set_bone_rest(1, Transform3D(Basis(), Vector3(0, 0.5, 0)))
	rig.reset_bone_poses()
	played.add_child(rig)
	var clip := Animation.new()
	clip.length = OUT
	var lid := clip.add_track(Animation.TYPE_VALUE)
	clip.track_set_path(lid, NodePath("Lid:position"))
	clip.track_insert_key(lid, 0.0, Vector3(0, 0.5, 0))
	clip.track_insert_key(lid, OUT, Vector3(0, 1.5, 0))
	var bone := clip.add_track(Animation.TYPE_POSITION_3D)
	clip.track_set_path(bone, NodePath("Rig:lid"))
	clip.position_track_insert_key(bone, 0.0, Vector3(0, 0.5, 0))
	clip.position_track_insert_key(bone, OUT, Vector3(0, 1.5, 0))
	var library := AnimationLibrary.new()
	library.add_animation("break", clip)
	var player := AnimationPlayer.new()
	player.name = "Player"
	player.add_animation_library("", library)
	played.add_child(player)
	# one left alone: a mesh with nothing below it
	var still := _box("StillCrate", Vector3(4, 0, 0), Vector3.ONE)
	still.add_to_group("crate")
	add_child(still)
	# one pushed whole, one freed (its debris would be spawned beside it), one that breaks into rigid bodies
	_crate("PushedCrate", 8.0).add_child(_box("Whole", Vector3.ZERO, Vector3.ONE))
	_crate("FreedCrate", 12.0).add_child(_box("Whole", Vector3.ZERO, Vector3.ONE))
	var physics := _crate("PhysicsCrate", 16.0)
	for corner: Vector3 in [Vector3(-1, 0, -1), Vector3(1, 0, -1), Vector3(-1, 0, 1), Vector3(1, 0, 1)]:
		var body := RigidBody3D.new()
		body.name = "Body"
		body.position = corner * 0.25
		body.freeze = true
		body.add_child(_box("Piece", Vector3.ZERO, Vector3.ONE * 0.5))
		var shape := CollisionShape3D.new()
		shape.shape = BoxShape3D.new()
		(shape.shape as BoxShape3D).size = Vector3.ONE * 0.5
		body.add_child(shape)
		physics.add_child(body)
		_bodies.append(body)


func _crate(crate: String, x: float) -> Node3D:
	var node := Node3D.new()
	node.name = crate
	node.position = Vector3(x, 0, 0)
	node.add_to_group("crate")
	add_child(node)
	return node


static func _box(part: String, at: Vector3, size: Vector3) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var box := MeshInstance3D.new()
	box.name = part
	box.mesh = mesh
	box.position = at
	return box


func _break() -> void:
	_broken = 0.0
	($HideCrate/Whole as Node3D).visible = false
	for piece in _pieces:
		piece.visible = true
	($AnimCrate/Player as AnimationPlayer).play("break")
	($PushedCrate as Node3D).position.x += 1.0
	$FreedCrate.queue_free()
	for body in _bodies:
		body.freeze = false
		body.linear_velocity = Vector3(signf(body.position.x), 1, signf(body.position.z)) * 3.0


func _process(delta: float) -> void:
	if _broken < 0.0:
		return
	_broken = minf(_broken + delta, OUT)
	for piece in _pieces:
		var way := Vector3(signf(piece.position.x), 0, signf(piece.position.z))
		piece.position = way * lerpf(0.25, 1.0, _broken / OUT)


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_B and _broken < 0.0:
		_break()
