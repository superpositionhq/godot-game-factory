extends "../query.gd"
## objects: the nodes an object select matches, one row each (contract section 3, "objects"). Every match is read and
## summed up in the sample; the first 200 are kept as rows.
## rows: {"name", "class", <fields>...}

const Motion := preload("../motion.gd")
const Stops := preload("../stops.gd")
const Changes := preload("../changes.gd")
const PLAIN := [
	"count", "x", "y", "z", "yaw", "pitch", "roll", "scale", "extent_x", "extent_y", "extent_z", "active", "hidden",
	"collision", "speed", "spin", "simulating", "spread", "changed", "bounds_change", "pose_change", "facing_vs_velocity", "clip", "frozen", "damage_taken", "lit", "glow",
]
const PREFIXES := ["prop:", "anim:", "forward:", "rel_yaw:", "world_yaw:", "world_pitch:", "world_roll:"]
const MAX_SPIN_PARTS := 64

var _select: Dictionary = {}
var _motion := Motion.new()
var _waiting: Array = []  # [row, node]: rows whose lit waits for a part being drawn alone (the frame's end tells)
var _rows: Array = []
var _stops := Stops.new()
var _changes := Changes.new()
var _change := false  # a changed, bounds_change or pose_change field is asked


func load_query() -> void:
	known_fields(PLAIN, PREFIXES)
	_select = Find.obj(def, "select")
	Find.check(_select, "%s %s" % [kind, id])
	for f in fields:
		_change = _change or Changes.is_field(f)


func frame(dt: float) -> void:
	_motion.frame()
	_stops.frame(dt)


func sample(_t: float, sample: Dictionary) -> void:
	var rows: Array = []
	_waiting.clear()
	var asked: int = Find.pending
	var matched := Find.objects(_select)
	if Find.pending != asked:
		# a part the select must know the light of (has.lit) is drawn for the first time: who matches isn't known
		# in this sample, so it has no rows and says so (the checker reads no value, never a low count)
		sample["pending"] = true
		matched = []
	for n in matched:
		rows.append(_row(n))
	_motion.end_sample()
	_stops.end_sample()
	_changes.end_sample()
	_rows = rows
	write_rows(rows, sample)


func _row(n: Node) -> Dictionary:
	var row := {"name": String(n.name), "class": Find.class_of(n)}
	var dt: float = 1.0 / probe.fps
	var light: Variant = null
	var list: Array[Node] = []
	if _change or "spread" in fields:
		list = Changes.parts(n)
	var change: Dictionary = _changes.read(n, list) if _change else {}
	for f in fields:
		var v: Variant = null
		if f == "speed" or f == "facing_vs_velocity":
			var velocity: Variant = _motion.velocity(n, dt)
			if velocity != null and f == "speed":
				v = (velocity as Vector3).length()
			elif velocity != null and (velocity as Vector3).length() >= 0.1 and Find.forward(n) != null:
				v = rad_to_deg((Find.forward(n) as Vector3).angle_to(velocity))
		elif Changes.is_field(f):
			v = change[f]
		elif f == "spread":
			v = Changes.spread(list)
		elif f == "lit" or f == "glow":
			if light == null:
				light = Find.light_of_object(n)
				if light.get("drawing", false):
					_waiting.append([row, weakref(n)])
			v = Find.light_field(light, f, row)
		else:
			v = _field(n, f, dt)
		if v != null:
			row[f] = v
	return row


func _field(n: Node, f: String, dt: float) -> Variant:
	match f:
		"count":
			return 1.0
		"x", "y", "z":
			var at: Variant = Find.place(n)
			return null if at == null else at[f]
		"pitch", "yaw", "roll":
			var turned: Variant = Find.angles(n)
			return null if turned == null else turned[["pitch", "yaw", "roll"].find(f)]
		"scale":
			if n is Node3D:
				var s := (n as Node3D).global_basis.get_scale()
				return (absf(s.x) + absf(s.y) + absf(s.z)) / 3.0
			if n is Node2D:
				var flat := (n as Node2D).global_scale
				return (absf(flat.x) + absf(flat.y)) / 2.0
			return null
		"extent_x", "extent_y", "extent_z":
			# an object that draws nothing shown (no shown part with a box: an empty node, a light, a hidden one) reads 0,
			# an object that draws nothing has an extent of 0, never no value
			var around: Variant = Find.box(n)
			return 0.0 if around == null else (around as AABB).size[f.substr(7)] / 2.0
		"active":
			return 1.0 if Find.shown(n) else 0.0
		"hidden":
			return 1.0 if _hidden(n) else 0.0
		"collision":
			return 1.0 if Find.shown(n) and _collides(n) else 0.0
		"simulating":
			return 1.0 if Find.shown(n) and _simulates(n) else 0.0
		"spin":
			return _spin(n, dt)
		"clip":
			return _clip(n)
		"frozen":
			return _stops.longest(n)
		"damage_taken":
			return probe.damage_taken(n)
	var colon := f.find(":")
	if colon <= 0:
		return null
	var head := f.substr(0, colon)
	var rest := f.substr(colon + 1)
	match head:
		"prop":
			return Find.prop(n, rest)
		"anim":
			return _anim(n, rest)
		"forward":
			var dot := rest.rfind(".")
			var facing: Variant = Find.forward(Find.part(n, rest.substr(0, dot))) if dot > 0 else null
			return null if facing == null or not (rest.substr(dot + 1) in ["x", "y", "z"]) else facing[rest.substr(dot + 1)]
		"rel_yaw":
			var mine: Variant = Find.angles(n)
			var its: Variant = Find.angles(Find.part(n, rest))
			# a Node3D turns about Y (its yaw), a Node2D in its plane (its roll)
			var axis := 2 if n is Node2D else 1
			return null if mine == null or its == null else Find.angle(its[axis] - mine[axis])
		"world_yaw", "world_pitch", "world_roll":
			var turned: Variant = Find.angles(Find.part(n, rest))
			return null if turned == null else turned[["world_pitch", "world_yaw", "world_roll"].find(head)]
	return null


static func _hidden(n: Node) -> bool:
	## it isn't shown, or it has nodes that draw and none of them is shown
	if not Find.shown(n):
		return true
	var draws := false
	for p in Find.parts(n, true):
		if p is VisualInstance3D or (p is CanvasItem and p != n):
			draws = true
			if Find.shown(p):
				return false
	return draws and not (n is CanvasItem)


static func _collides(n: Node) -> bool:
	## a physics body (not an area) in it has a shape that is on
	for p in Find.parts(n, false):
		var on := false
		if p is CollisionShape3D:
			on = not (p as CollisionShape3D).disabled
		elif p is CollisionPolygon3D:
			on = not (p as CollisionPolygon3D).disabled
		elif p is CollisionShape2D:
			on = not (p as CollisionShape2D).disabled
		elif p is CollisionPolygon2D:
			on = not (p as CollisionPolygon2D).disabled
		if on and (p.get_parent() is PhysicsBody3D or p.get_parent() is PhysicsBody2D):
			return true
	return false


static func _simulates(n: Node) -> bool:
	for p in Find.parts(n, false):
		if (p is RigidBody3D or p is RigidBody2D) and Find.simulates(p):
			return true
	return false


func _spin(n: Node, dt: float) -> Variant:
	## the fastest of the node and the nodes it draws with
	var best: Variant = _motion.spin(n, dt)
	var seen := 0
	for p in Find.parts(n, true):
		if p == n or not (p is VisualInstance3D or p is Node2D):
			continue
		seen += 1
		if seen > MAX_SPIN_PARTS:
			break
		var v: Variant = _motion.spin(p, dt)
		if v != null and (best == null or v > best):
			best = v
	return best


static func _clip(n: Node) -> Variant:
	## the animation that plays: an AnimationPlayer's, else an animated sprite's, else an AnimationTree's state
	for p in Find.parts(n, false):
		if p is AnimationPlayer and (p as AnimationPlayer).is_playing():
			return String((p as AnimationPlayer).current_animation)
	for p in Find.parts(n, false):
		if (p is AnimatedSprite2D or p is AnimatedSprite3D) and p.call("is_playing"):
			return String(p.get("animation"))
	for p in Find.parts(n, false):
		if p is AnimationTree and (p as AnimationTree).active:
			var playback: Variant = p.get("parameters/playback")
			if playback is AnimationNodeStateMachinePlayback:
				return String((playback as AnimationNodeStateMachinePlayback).get_current_node())
	return null


static func _anim(n: Node, parameter: String) -> Variant:
	## a parameter of its AnimationTree (parameters/<name>): numbers and booleans as numbers
	for p in Find.parts(n, false):
		if p is AnimationTree:
			var path := "parameters/" + parameter
			if not (path in p):
				return null
			var v: Variant = p.get(path)
			return Find.plain(v) if v is bool or v is int or v is float else null
	return null


func needs_frame() -> bool:
	return not _waiting.is_empty()


func frame_drawn(_image: Image, sample: Dictionary) -> void:
	## the parts drawn alone in this frame are read, and the rows that waited for them get their lit
	Find.light_collect()
	for waiting: Array in _waiting:
		var n: Node = (waiting[1] as WeakRef).get_ref()
		if n == null:
			continue
		var row: Dictionary = waiting[0]
		var light: Variant = Find.light_of_object(n)
		for f in fields:
			if f == "lit" or f == "glow":
				var v: Variant = Find.light_field(light, f, row)
				if v != null:
					row[f] = v
	_waiting.clear()
	write_rows(_rows, sample)
