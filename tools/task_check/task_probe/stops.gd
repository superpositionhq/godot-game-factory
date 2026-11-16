extends RefCounted
## The short stops of the nodes a query read (frozen): a hit stop of an object's own, too short for a screenshot. A
## node read in one sample is followed frame by frame from then on. A frame is one of motion when the node, a node
## below it or a bone of a skeleton in it moved or turned; a stop is a run of frames without motion between two frames
## of motion, 0.5 s at most (longer is standing still, not a stop). A sample reads the longest stop that ended since
## the previous one.

const Find := preload("find.gd")
const LONGEST := 0.5  ## seconds a stop lasts at most
const MAX_PARTS := 64
const MAX_BONES := 256
const MOVED_3D := 0.001  ## m a frame
const MOVED_2D := 0.01  ## 2D units a frame
const TURNED := 0.00175  ## how far an axis of a node's basis moves in a turn of 0.1 degrees

var _seen: Dictionary = {}  # instance id -> {ref, pose, moving, still, longest, frames}
var _read: Dictionary = {}  # instance id -> the node, read in this sample


func frame(dt: float) -> void:
	for id: int in _seen.keys():
		var e: Dictionary = _seen[id]
		var n: Node = e["ref"].get_ref()
		if n == null or not n.is_inside_tree():
			_seen.erase(id)
			continue
		var now := _pose(n)
		var moved := _differs(e["pose"], now)
		e["pose"] = now
		e["frames"] += 1
		if moved:
			if e["moving"] and e["still"] > 0 and e["still"] * dt <= LONGEST + 1e-9:
				e["longest"] = maxf(e["longest"], e["still"] * dt)
			e["moving"] = true
			e["still"] = 0
		elif e["moving"]:
			e["still"] += 1


func longest(n: Node) -> Variant:
	## seconds: the longest stop of `n` that ended since the previous sample, 0 when none did; null the first time a
	## node is read
	_read[n.get_instance_id()] = n
	var e: Variant = _seen.get(n.get_instance_id())
	return e["longest"] if e != null and e["frames"] > 0 else null


func end_sample() -> void:
	## the nodes this sample read are followed until the next one, and only those; a stop under way goes on
	var kept := {}
	for id: int in _read:
		var e: Variant = _seen.get(id)
		if e == null:
			e = {"ref": weakref(_read[id]), "pose": _pose(_read[id]), "moving": false, "still": 0, "longest": 0.0, "frames": 0}
		else:
			e["longest"] = 0.0
		kept[id] = e
	_seen = kept
	_read.clear()


static func _pose(n: Node) -> Array:
	## where the node and what is below it are: each placed node's transform (64 nodes at most) and each skeleton
	## bone's place (256 at most)
	var pose: Array = []
	var nodes: Array[Node] = [n]
	nodes.append_array(n.find_children("*", "", true, false))
	var parts := 0
	var bones := 0
	for p in nodes:
		if parts >= MAX_PARTS:
			break
		if p is Node3D:
			pose.append((p as Node3D).global_transform)
		elif p is Node2D:
			pose.append((p as Node2D).global_transform)
		elif p is Control:
			pose.append((p as Control).global_position)
		else:
			continue
		parts += 1
		if p is Skeleton3D:
			var skeleton := p as Skeleton3D
			for i in skeleton.get_bone_count():
				if bones >= MAX_BONES:
					break
				pose.append(skeleton.get_bone_global_pose(i).origin)
				bones += 1
	return pose


static func _differs(before: Array, now: Array) -> bool:
	if before.size() != now.size():
		return true
	for i in now.size():
		var a: Variant = before[i]
		var b: Variant = now[i]
		if typeof(a) != typeof(b):
			return true
		if a is Transform3D:
			if a.origin.distance_squared_to(b.origin) > MOVED_3D * MOVED_3D:
				return true
			for axis in 3:
				if a.basis[axis].distance_squared_to(b.basis[axis]) > TURNED * TURNED:
					return true
		elif a is Transform2D:
			if a.origin.distance_squared_to(b.origin) > MOVED_2D * MOVED_2D:
				return true
			if a.x.distance_squared_to(b.x) > TURNED * TURNED or a.y.distance_squared_to(b.y) > TURNED * TURNED:
				return true
		elif a is Vector3:
			if a.distance_squared_to(b) > MOVED_3D * MOVED_3D:
				return true
		elif a is Vector2:
			if a.distance_squared_to(b) > MOVED_2D * MOVED_2D:
				return true
	return false
