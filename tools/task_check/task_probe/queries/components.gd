extends "../query.gd"
## components: the nodes of a class, one row each (contract section 3, "components"): the parts of an object, by what
## they are rather than by a name, so effects and parts that are no object of their own count too.
## select: component (a class: the class, the ones it inherits and its script's match), effect (true: live particle
## effects only), name (wildcard on its name), owner (an object select it or a node above it matches), near (its
## place), mesh (wildcard on its mesh's name), visible (true: drawn only), inactive (true: hidden ones too).
## rows: {"name", "class", "owner" (its parent's name), <fields>...}

const Motion := preload("../motion.gd")
const PLAIN := [
	"count", "active", "visible", "x", "y", "z", "speed", "spin", "extent_x", "extent_y", "extent_z", "simulating",
	"intensity", "on", "world_yaw", "world_pitch", "lit", "glow",
]
const EFFECTS := ["GPUParticles3D", "CPUParticles3D", "GPUParticles2D", "CPUParticles2D"]

var _type := ""
var _effect := false
var _visible_only := false
var _inactive := false
var _broken := false
var _name := ""
var _mesh := ""
var _owner: Dictionary = {}
var _near: Dictionary = {}
var _motion := Motion.new()
var _waiting: Array = []  # [row, node]: rows whose lit waits for a part being drawn alone (the frame's end tells)
var _rows: Array = []


func load_query() -> void:
	known_fields(PLAIN, ["prop:"])
	var s := Find.obj(def, "select")
	_type = Find.text(s, "component")
	_effect = Find.flag(s, "effect")
	_visible_only = Find.flag(s, "visible")
	_inactive = Find.flag(s, "inactive")
	_name = Find.text(s, "name")
	_mesh = Find.text(s, "mesh")
	_owner = Find.obj(s, "owner")
	Find.check(_owner, "%s %s" % [kind, id])
	_near = Find.obj(s, "near")
	if _type != "" and not Find.names_class(_type):
		probe.error("%s %s: no component type %s" % [kind, id, _type])
		_broken = true
	elif _type == "" and not _effect:
		probe.error("%s %s: the select names no component and no effect" % [kind, id])
		_broken = true


func frame(_dt: float) -> void:
	Find.light_tick()
	_motion.frame()


func sample(_t: float, sample: Dictionary) -> void:
	var rows: Array = []
	_waiting.clear()
	if not _broken:
		for n in _match():
			rows.append(_row(n))
	_motion.end_sample()
	_rows = rows
	write_rows(rows, sample)


func _match() -> Array[Node]:
	var found: Array[Node] = []
	var centre: Variant = null
	if not _near.is_empty():
		centre = Find.point(Find.obj(_near, "point"))
		if centre == null:
			return found
	var owners: Array[Node] = []
	if not _owner.is_empty():
		owners = Find.objects(_owner)
	var candidates: Array[Node] = []
	if _type != "":
		candidates = Find.of_class(_type, _inactive)
	else:
		for n in Find.all_nodes():
			if _is_effect(n) and (_inactive or Find.shown(n)):
				candidates.append(n)
	for n in candidates:
		if _name != "" and not String(n.name).matchn(_name):
			continue
		if not _near.is_empty() and not Find.within(_near, centre, Find.place(n)):
			continue
		if _mesh != "" and not _mesh_name(n).matchn(_mesh):
			continue
		if _visible_only and not _visible(n):
			continue
		if _effect and not _live(n):
			continue
		if not _owner.is_empty() and not Find.owned_by(n, owners):
			continue
		found.append(n)
	return found


static func _is_effect(n: Node) -> bool:
	for type: String in EFFECTS:
		if n.is_class(type):
			return true
	return false


static func _live(n: Node) -> bool:
	## a particle effect that is emitting and shown
	return _is_effect(n) and bool(n.get("emitting")) and Find.shown(n)


static func _mesh_name(n: Node) -> String:
	if n is MeshInstance3D:
		return Find.resource_name((n as MeshInstance3D).mesh)
	if n is MeshInstance2D:
		return Find.resource_name((n as MeshInstance2D).mesh)
	if n is MultiMeshInstance3D and (n as MultiMeshInstance3D).multimesh != null:
		return Find.resource_name((n as MultiMeshInstance3D).multimesh.mesh)
	return ""


static func _visible(n: Node) -> bool:
	## shown: a node that draws is drawn, any other is not under a hidden node
	return Find.shown(n)


static func _active(n: Node) -> bool:
	## shown and doing what it does: a particle effect emitting, a sound playing, an animation playing, a collision
	## shape on, a light on
	if not Find.shown(n):
		return false
	if _is_effect(n):
		return bool(n.get("emitting"))
	if n is AudioStreamPlayer or n is AudioStreamPlayer2D or n is AudioStreamPlayer3D:
		return bool(n.get("playing"))
	if n is AnimationPlayer:
		return (n as AnimationPlayer).is_playing()
	if n is CollisionShape3D or n is CollisionPolygon3D or n is CollisionShape2D or n is CollisionPolygon2D:
		return not bool(n.get("disabled"))
	if n is Light3D or n is Light2D:
		return _on(n)
	return true


static func _on(n: Node) -> bool:
	## a light that lights the scene: shown, of an energy above 0
	if n is Light3D:
		return Find.shown(n) and (n as Light3D).light_energy > 0.0
	if n is Light2D:
		return Find.shown(n) and (n as Light2D).enabled and (n as Light2D).energy > 0.0
	return false


func _row(n: Node) -> Dictionary:
	var parent := n.get_parent()
	var row := {"name": String(n.name), "class": Find.class_of(n), "owner": String(parent.name) if parent != null else ""}
	var dt: float = 1.0 / probe.fps
	for f in fields:
		var v: Variant = null
		match f:
			"count":
				v = 1.0
			"active":
				v = 1.0 if _active(n) else 0.0
			"visible":
				v = 1.0 if _visible(n) else 0.0
			"x", "y", "z":
				var at: Variant = Find.place(n)
				if at != null:
					v = at[f]
			"speed":
				var velocity: Variant = _motion.velocity(n, dt)
				if velocity != null:
					v = (velocity as Vector3).length()
			"spin":
				v = _motion.spin(n, dt)
			"world_yaw", "world_pitch":
				var turned: Variant = Find.angles(n)
				if turned != null:
					v = turned[1 if f == "world_yaw" else 0]
			"extent_x", "extent_y", "extent_z":
				var around: Variant = Find.own_box(n)
				if around != null:
					v = (around as AABB).size[f.substr(7)] / 2.0
			"simulating":
				v = 1.0 if Find.shown(n) and Find.simulates(n) else 0.0
			"intensity":
				if n is Light3D:
					v = (n as Light3D).light_energy
				elif n is Light2D:
					v = (n as Light2D).energy
			"on":
				if n is Light3D or n is Light2D:
					v = 1.0 if _on(n) else 0.0
			"lit", "glow":
				var light: Variant = Find.light_of(n)
				if light != null and light.get("drawing", false) and (_waiting.is_empty() or _waiting[-1][0] != row):
					_waiting.append([row, weakref(n)])
				v = Find.light_field(light, f, row)
			_:
				v = Find.own_prop(n, f.substr(5))
		if v != null:
			row[f] = v
	return row


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
		var light: Variant = Find.light_of(n)
		for f in fields:
			if f == "lit" or f == "glow":
				var v: Variant = Find.light_field(light, f, row)
				if v != null:
					row[f] = v
	_waiting.clear()
	write_rows(_rows, sample)
