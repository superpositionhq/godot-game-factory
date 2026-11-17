extends "../query.gd"
## ground: the lie of the land (contract section 3, "ground"): a ray straight down from 2000 m up meets the first
## physics body's shape that isn't the player's (areas never); with `select`, only shapes of the objects it matches (or
## of the nodes below them) are ground, the rest traced through. A 3D ray: 2D shapes are never met.
## `xz` [x, z] -> "value": {"height" (null when nothing was met), "hit"};
## `box` [x0, z0, x1, z1] + `grid` (2-32, default 8; corners and edges included) -> "value": {"min", "max", "mean",
## "range" (null with no hit), "hits", "points"}; null with neither.

const TOP := 2000.0
const MAX_THROUGH := 32  ## shapes a ray is traced through at most before it gives up

var _xz: PackedFloat64Array = PackedFloat64Array()
var _box: PackedFloat64Array = PackedFloat64Array()
var _grid := 8
var _select: Dictionary = {}
var _ground: Variant = null  # this sample's ground nodes (instance id -> true), or null for every body


func load_query() -> void:
	var box := Find.numbers(def.get("box"), 4)
	var xz := Find.numbers(def.get("xz"), 2)
	if box.size() == 4:
		_box = PackedFloat64Array([minf(box[0], box[2]), minf(box[1], box[3]), maxf(box[0], box[2]), maxf(box[1], box[3])])
		_grid = clampi(int(floor(Find.num(def, "grid") + 0.5)) if Find.has_num(def, "grid") else 8, 2, 32)
	elif xz.size() == 2:
		_xz = PackedFloat64Array(xz)
	else:
		probe.error("ground %s: a ground query takes xz [x, z] or box [x0, z0, x1, z1]" % id)
	_select = Find.obj(def, "select")


func sample(_t: float, sample: Dictionary) -> void:
	sample["value"] = null
	if _xz.is_empty() and _box.is_empty():
		return
	var space := _space()
	if space == null:
		return
	_ground = null
	if not _select.is_empty():
		_ground = {}
		for n in Find.objects(_select):
			_ground[n.get_instance_id()] = true
	var player: Node = probe.player()
	if _box.is_empty():
		var y: Variant = _down(space, _xz[0], _xz[1], player)
		sample["value"] = {"height": y, "hit": 1.0 if y != null else 0.0}
		return
	var hits := 0
	var low := 0.0
	var high := 0.0
	var sum := 0.0
	for i in _grid:
		for j in _grid:
			var x := _box[0] + (_box[2] - _box[0]) * i / (_grid - 1)
			var z := _box[1] + (_box[3] - _box[1]) * j / (_grid - 1)
			var y: Variant = _down(space, x, z, player)
			if y == null:
				continue
			low = y if hits == 0 else minf(low, y)
			high = y if hits == 0 else maxf(high, y)
			sum += y
			hits += 1
	sample["value"] = {"min": low if hits > 0 else null, "max": high if hits > 0 else null,
		"mean": sum / hits if hits > 0 else null, "range": high - low if hits > 0 else null,
		"hits": float(hits), "points": float(_grid * _grid)}


func _space() -> PhysicsDirectSpaceState3D:
	## the 3D physics space of the game's world: its camera's, else the window's
	var view: Node = probe.view()
	var world: World3D = (view as Camera3D).get_world_3d() if view is Camera3D else probe.get_tree().root.world_3d
	return world.direct_space_state if world != null else null


func _down(space: PhysicsDirectSpaceState3D, x: float, z: float, player: Node) -> Variant:
	## the y where the ray at (x, z) first meets ground, or null
	var ray := PhysicsRayQueryParameters3D.create(Vector3(x, TOP, z), Vector3(x, -TOP, z))
	ray.collide_with_areas = false
	var skip: Array[RID] = []
	for i in MAX_THROUGH:
		ray.exclude = skip
		var hit := space.intersect_ray(ray)
		if hit.is_empty():
			return null
		var body: Object = hit.get("collider")
		var node := body as Node
		if node != null and (_owned_by(node, player) or (_ground != null and not _is_ground(node))):
			skip.append(hit["rid"])
			continue
		return (hit["position"] as Vector3).y
	return null


func _is_ground(n: Node) -> bool:
	var at := n
	while at != null:
		if (_ground as Dictionary).has(at.get_instance_id()):
			return true
		at = at.get_parent()
	return false


static func _owned_by(n: Node, player: Node) -> bool:
	return player != null and (n == player or player.is_ancestor_of(n))
