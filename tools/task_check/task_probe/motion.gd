extends RefCounted
## How fast the nodes a query read move and turn (speed, spin, facing_vs_velocity). A node read in one sample is
## followed frame by frame until the next: its turning summed every frame, so a part turning many times a second still
## reads; its speed is its own velocity when it reports one that isn't zero, else how far it moved since the previous
## sample over the time of the frames since.

const Find := preload("find.gd")

var _seen: Dictionary = {}  # instance id -> {ref, pos, quat, turned, frames}
var _read: Dictionary = {}  # instance id -> the node, read in this sample


func frame() -> void:
	for id: int in _seen.keys():
		var e: Dictionary = _seen[id]
		var n: Node = e["ref"].get_ref()
		if n == null or not n.is_inside_tree():
			_seen.erase(id)
			continue
		e["frames"] += 1
		var now: Variant = Find.turn(n)
		if now != null and e["quat"] != null:
			e["turned"] += rad_to_deg((e["quat"] as Quaternion).angle_to(now))
		e["quat"] = now


func velocity(n: Node, dt: float) -> Variant:
	## a Vector3 in units a second, or null the first time a node without a velocity of its own is seen
	_read[n.get_instance_id()] = n
	var own: Variant = Find.own_velocity(n)
	if own != null and (own as Vector3).length_squared() > 0.0:
		return own
	var e: Variant = _seen.get(n.get_instance_id())
	var at: Variant = Find.place(n)
	if e != null and e["pos"] != null and at != null and e["frames"] > 0:
		return ((at as Vector3) - (e["pos"] as Vector3)) / (e["frames"] * dt)
	return Vector3.ZERO if own != null else null


func spin(n: Node, dt: float) -> Variant:
	## degrees a second; the first time a node is seen, a rigid body's own angular speed, else null
	_read[n.get_instance_id()] = n
	var e: Variant = _seen.get(n.get_instance_id())
	if e != null and e["frames"] > 0:
		# what it turned in this frame's own scripts is not summed yet
		var now: Variant = Find.turn(n)
		var last := rad_to_deg((e["quat"] as Quaternion).angle_to(now)) if now != null and e["quat"] != null else 0.0
		return (e["turned"] + last) / (e["frames"] * dt)
	if n is RigidBody3D and not (n as RigidBody3D).freeze:
		return rad_to_deg((n as RigidBody3D).angular_velocity.length())
	if n is RigidBody2D and not (n as RigidBody2D).freeze:
		return absf(rad_to_deg((n as RigidBody2D).angular_velocity))
	return null


func end_sample() -> void:
	## the nodes this sample read are followed until the next one, and only those
	_seen.clear()
	for id: int in _read:
		var n: Node = _read[id]
		_seen[id] = {"ref": weakref(n), "pos": Find.place(n), "quat": Find.turn(n), "turned": 0.0, "frames": 0}
	_read.clear()
