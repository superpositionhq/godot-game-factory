extends RefCounted
## The short stops of the nodes a query read (frozen): a hit stop of an object's own, too short for a screenshot. A
## node read in one sample is followed frame by frame from then on: itself, the placed nodes below it at that moment
## and the bones of the skeletons among them. A frame is one of motion when one of them moved or turned; a stop is a
## run of frames without motion between two frames of motion, 0.5 s at most (longer is standing still, not a stop).
## What comes to be below the node later (a hit spark, a damage number) is not followed, and a part that goes is left
## out from then on: neither is motion. A sample reads the longest stop that ended since the previous one.

const Find := preload("find.gd")
const LONGEST := 0.5  ## seconds a stop lasts at most
const MAX_PARTS := 64
const MAX_BONES := 256
const MOVED_3D := 0.001  ## m a frame
const MOVED_2D := 0.01  ## 2D units a frame
const TURNED := 0.00175  ## how far an axis of a node's basis moves in a turn of 0.1 degrees

var _seen: Dictionary = {}  # instance id -> {ref, parts, pose, moving, still, longest, frames}
var _read: Dictionary = {}  # instance id -> the node, read in this sample


func frame(dt: float) -> void:
	for id: int in _seen.keys():
		var e: Dictionary = _seen[id]
		var n: Node = e["ref"].get_ref()
		if n == null or not n.is_inside_tree():
			_seen.erase(id)
			continue
		var now := _pose(e["parts"])
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
			var parts := _parts(_read[id])
			e = {"ref": weakref(_read[id]), "parts": parts, "pose": _pose(parts), "moving": false, "still": 0,
				"longest": 0.0, "frames": 0}
		else:
			e["longest"] = 0.0
		kept[id] = e
	_seen = kept
	_read.clear()


static func _parts(n: Node) -> Array:
	## the node and the placed nodes below it now (64 at most), as weak references
	var parts: Array = [weakref(n)]
	for p: Node in n.find_children("*", "", true, false):
		if parts.size() >= MAX_PARTS:
			break
		if p is Node3D or p is Node2D or p is Control:
			parts.append(weakref(p))
	return parts


static func _pose(parts: Array) -> Array:
	## where each part is: [its transform (a Control: its place), its bones' places when it is a skeleton], or null
	## for a part that is gone
	var pose: Array = []
	var bones := 0
	for ref: WeakRef in parts:
		var p: Node = ref.get_ref()
		if p == null or not p.is_inside_tree():
			pose.append(null)
			continue
		var at: Variant = null
		if p is Node3D:
			at = (p as Node3D).global_transform
		elif p is Node2D:
			at = (p as Node2D).global_transform
		elif p is Control:
			at = (p as Control).global_position
		var places: Array = []
		if p is Skeleton3D:
			var skeleton := p as Skeleton3D
			for i in skeleton.get_bone_count():
				if bones >= MAX_BONES:
					break
				places.append(skeleton.get_bone_global_pose(i).origin)
				bones += 1
		pose.append([at, places])
	return pose


static func _differs(before: Array, now: Array) -> bool:
	## whether a part that is there in both moved or turned, or a bone of it moved; a part that came back or went,
	## and a skeleton whose bones changed in number, are no motion
	for i in mini(before.size(), now.size()):
		if before[i] == null or now[i] == null:
			continue
		if _moved(before[i][0], now[i][0]):
			return true
		var old: Array = before[i][1]
		var new: Array = now[i][1]
		if old.size() != new.size():
			continue
		for b in new.size():
			if (old[b] as Vector3).distance_squared_to(new[b]) > MOVED_3D * MOVED_3D:
				return true
	return false


static func _moved(a: Variant, b: Variant) -> bool:
	if typeof(a) != typeof(b):
		return false
	if a is Transform3D:
		if a.origin.distance_squared_to(b.origin) > MOVED_3D * MOVED_3D:
			return true
		for axis in 3:
			if a.basis[axis].distance_squared_to(b.basis[axis]) > TURNED * TURNED:
				return true
	elif a is Transform2D:
		if a.origin.distance_squared_to(b.origin) > MOVED_2D * MOVED_2D:
			return true
		return a.x.distance_squared_to(b.x) > TURNED * TURNED or a.y.distance_squared_to(b.y) > TURNED * TURNED
	elif a is Vector2:
		return a.distance_squared_to(b) > MOVED_2D * MOVED_2D
	return false
