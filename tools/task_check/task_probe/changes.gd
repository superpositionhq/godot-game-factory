extends RefCounted
## changed, bounds_change, pose_change and spread of an object: its parts are the nodes in it that draw a shape (a
## GeometryInstance3D that isn't a particle effect, a 2D node with a rectangle, its own or below it), drawn or hidden.
## changed, bounds_change and pose_change read each object against the first sample this query saw it in; the first
## states are kept for the play, forgotten when the object is freed.

const Find := preload("find.gd")
const BOUNDS := 0.01  ## m: changed when a part's world box moved more
const POSE := 0.05  ## m: changed when its pose (bones, and the parts' places in the object's own space) moved more in all
const MAX_PARTS := 256
const MAX_BONES := 256
const EFFECTS := ["GPUParticles3D", "CPUParticles3D", "GPUParticles2D", "CPUParticles2D"]

var _firsts: Dictionary = {}  # object instance id -> {ref, parts: {id: state}, poses: {id: Array}}


static func is_field(f: String) -> bool:
	return f == "changed" or f == "bounds_change" or f == "pose_change"


static func parts(n: Node) -> Array[Node]:
	## the nodes in the object that draw a shape, shown or hidden, in tree order
	var found: Array[Node] = []
	for p in Find.parts(n, true):
		if found.size() >= MAX_PARTS:
			break
		if _is_part(p):
			found.append(p)
	return found


static func _is_part(p: Node) -> bool:
	for type: String in EFFECTS:
		if p.is_class(type):
			return false  # an effect spans where its particles went
	if p is GeometryInstance3D:
		return (p as GeometryInstance3D).get_aabb().size != Vector3.ZERO
	if p is Node2D and not (p is CollisionObject2D or p is CollisionShape2D or p is CollisionPolygon2D):
		return Find.own_box(p) != null
	return false


static func drawn(p: Node) -> bool:
	## shown and drawn at all: on a render layer, not faded out, not only a shadow, a multimesh with an instance
	if not Find.shown(p):
		return false
	if p is GeometryInstance3D:
		var g := p as GeometryInstance3D
		if g.layers == 0 or g.transparency >= 1.0 or g.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			return false
		if p is MultiMeshInstance3D:
			var many := (p as MultiMeshInstance3D).multimesh
			if many == null or many.instance_count == 0 or many.visible_instance_count == 0:
				return false
	return true


static func spread(list: Array[Node]) -> Variant:
	## the diagonal of the world-aligned box around its drawn parts' box centres, a skinned mesh whose skeleton carries
	## two physical bones or more (a ragdoll) by each bone's place; 0 with one, null with none
	var have := false
	var around := AABB()
	for p in list:
		if not drawn(p):
			continue
		var bodies := _bodies(p)
		var places: Array = bodies if bodies.size() >= 2 else [(Find.own_box(p) as AABB).get_center()]
		for at: Vector3 in places:
			if have:
				around = around.expand(at)
			else:
				around = AABB(at, Vector3.ZERO)
				have = true
	return around.size.length() if have else null


static func _bodies(p: Node) -> Array:
	## the places of the physical bones of a skinned mesh's skeleton, shown ones
	if not (p is MeshInstance3D) or (p as MeshInstance3D).skin == null:
		return []
	var skeleton := (p as MeshInstance3D).get_node_or_null((p as MeshInstance3D).skeleton) as Skeleton3D
	if skeleton == null:
		return []
	var found: Array = []
	for b: Node in skeleton.find_children("*", "PhysicalBone3D", true, false):
		if Find.shown(b):
			found.append((b as Node3D).global_position)
	return found


static func _state(p: Node) -> Dictionary:
	return {"drawn": drawn(p), "box": Find.own_box(p)}


static func _box_move(a: Variant, b: Variant) -> float:
	## how far the furthest face of a world box moved
	if a == null or b == null:
		return 0.0
	var lo: Vector3 = (a as AABB).position - (b as AABB).position
	var hi: Vector3 = (a as AABB).end - (b as AABB).end
	return maxf(maxf(absf(lo.x), maxf(absf(lo.y), absf(lo.z))), maxf(absf(hi.x), maxf(absf(hi.y), absf(hi.z))))


static func _poses(n: Node, list: Array[Node]) -> Dictionary:
	## its pose: every bone of each Skeleton3D in it, in the skeleton's own space, and each part's place in the
	## object's own space (so the object moving as a whole is no pose)
	var out := {}
	for p in Find.parts(n, true):
		if p is Skeleton3D:
			var skeleton := p as Skeleton3D
			var bones: Array = []
			for i in mini(skeleton.get_bone_count(), MAX_BONES):
				bones.append(skeleton.get_bone_global_pose(i).origin)
			out[p.get_instance_id()] = bones
	for p in list:
		if p == n:
			continue
		if n is Node3D and p is Node3D:
			out[p.get_instance_id()] = [(n as Node3D).global_transform.affine_inverse() * (p as Node3D).global_position]
		elif n is Node2D and p is Node2D:
			var at := (n as Node2D).global_transform.affine_inverse() * (p as Node2D).global_position
			out[p.get_instance_id()] = [Vector3(at.x, at.y, 0.0)]
	return out


func read(n: Node, list: Array[Node]) -> Dictionary:
	## {changed, bounds_change, pose_change} of an object (null where it has no value): changed when a part was hidden
	## or shown, a part drawn then is gone or a part drawn now wasn't there, a part's world box moved more than
	## BOUNDS, or its pose moved more than POSE in all (or its bones changed in number). The first sample records
	## every part and reads unchanged.
	var id := n.get_instance_id()
	var now_parts := {}
	for p in list:
		now_parts[p.get_instance_id()] = _state(p)
	var now_poses := _poses(n, list)
	var first: Variant = _firsts.get(id)
	if first == null:
		_firsts[id] = {"ref": weakref(n), "parts": now_parts, "poses": now_poses}
		return {"changed": 0.0, "bounds_change": 0.0 if not now_parts.is_empty() else null,
			"pose_change": 0.0 if not now_poses.is_empty() else null}
	var changed := false
	var compared := false
	var moved := 0.0
	for p: int in now_parts:
		var then: Variant = first["parts"].get(p)
		if then == null:
			changed = changed or now_parts[p]["drawn"]  # a part added since, drawn
			continue
		compared = true
		var by := _box_move(then["box"], now_parts[p]["box"])
		moved = maxf(moved, by)
		changed = changed or then["drawn"] != now_parts[p]["drawn"] or by > BOUNDS
	for p: int in first["parts"]:
		if first["parts"][p]["drawn"] and not now_parts.has(p):
			changed = true  # a part drawn then is gone
	var posed := false
	var pose := 0.0
	for key: int in now_poses:
		var then: Variant = first["poses"].get(key)
		if then == null:
			continue
		posed = true
		var a: Array = then
		var b: Array = now_poses[key]
		changed = changed or a.size() != b.size()
		for i in mini(a.size(), b.size()):
			pose += (a[i] as Vector3).distance_to(b[i])
	changed = changed or pose > POSE
	return {"changed": 1.0 if changed else 0.0, "bounds_change": moved if compared else null,
		"pose_change": pose if posed else null}


func end_sample() -> void:
	## the objects freed since are forgotten (their ids never come back)
	for id: int in _firsts.keys():
		if (_firsts[id]["ref"] as WeakRef).get_ref() == null:
			_firsts.erase(id)
