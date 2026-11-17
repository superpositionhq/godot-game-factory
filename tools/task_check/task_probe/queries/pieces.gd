extends "../query.gd"
## pieces: placed mesh pieces, whatever form the scene holds them in (contract section 3, "pieces"): a MeshInstance3D
## whose mesh has triangles is 1, each instance of a MultiMeshInstance3D is 1, each cell of a GridMap whose item has a
## mesh is 1. A part that is a farther level of detail (a visibility range that begins above 0) is none. Nodes in the
## tree only; a hidden one is a piece that isn't drawn. Counted over every piece, never cut at a cap.
## select: component (MeshInstance3D, MultiMeshInstance3D, GridMap, GeometryInstance3D...), name (a wildcard on the
## node's name), mesh (a wildcard on its mesh's name; a GridMap cell's: its item's mesh), owner (an object select the
## node or a node above it matches), near (each piece by its own place: a node's, an instance's, a cell's).
## "value": {"count", "visible", "components", "objects", "triangles", "visible_triangles"} | null when near doesn't
## resolve or no node can be of the select's class.

var _component := ""
var _name := ""
var _mesh := ""
var _owner: Dictionary = {}
var _near: Dictionary = {}
var _unknown := false
var _triangles: Dictionary = {}  # this sample's meshes, read once each


func load_query() -> void:
	var select := Find.obj(def, "select")
	_component = Find.text(select, "component")
	_name = Find.text(select, "name")
	_mesh = Find.text(select, "mesh")
	_owner = Find.obj(select, "owner")
	_near = Find.obj(select, "near")
	if _component != "" and not Find.names_class(_component):
		probe.error("pieces %s: no component type %s" % [id, _component])
		_unknown = true


func _triangles_of(m: Mesh) -> int:
	## the triangles a mesh draws: its faces (every surface drawn as triangles)
	if m == null:
		return 0
	var key := m.get_instance_id()
	if not _triangles.has(key):
		_triangles[key] = m.get_faces().size() / 3
	return _triangles[key]


func sample(_t: float, sample: Dictionary) -> void:
	sample["value"] = null
	if _unknown:
		return
	var centre: Variant = null
	if not _near.is_empty():
		centre = Find.point(Find.obj(_near, "point"))
		if centre == null:
			return
	var owners: Variant = null
	if not _owner.is_empty():
		owners = {}
		for n in Find.objects(_owner):
			owners[n.get_instance_id()] = true
	_triangles.clear()
	var count := 0
	var visible := 0
	var tris := 0
	var visible_tris := 0
	var components := 0
	var objects := {}
	for n in Find.all_nodes():
		if Find.is_own(n) or not (n is GeometryInstance3D or n.is_class("GridMap")):
			continue
		var held: Array = []  # [[place, triangles, mesh name], ...]
		var drawn := Find.shown(n)
		var shown_count := 0
		if n is GeometryInstance3D:
			var g := n as GeometryInstance3D
			if g.visibility_range_begin > 0.0:
				continue  # a farther level of detail of what another node draws near
			held = _held(g)
			drawn = drawn and g.layers != 0 and g.transparency < 1.0 \
					and g.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		else:
			held = _held_grid(n as Node3D)
		if held.is_empty() or not _keep(n, owners):
			continue
		shown_count = held.size()
		if n is MultiMeshInstance3D:
			var limit := (n as MultiMeshInstance3D).multimesh.visible_instance_count
			shown_count = held.size() if limit < 0 else mini(limit, held.size())
		var n_here := 0
		for i in held.size():
			var piece: Array = held[i]
			if _mesh != "" and not String(piece[2]).matchn(_mesh):
				continue
			if centre != null and not Find.within(_near, centre, piece[0]):
				continue
			n_here += 1
			count += 1
			tris += piece[1]
			if drawn and i < shown_count:
				visible += 1
				visible_tris += piece[1]
		if n_here > 0:
			components += 1
			objects[n.get_instance_id()] = true
	sample["value"] = {"count": float(count), "visible": float(visible), "components": float(components),
		"objects": float(objects.size()), "triangles": float(tris), "visible_triangles": float(visible_tris)}


func _held(g: GeometryInstance3D) -> Array:
	## the pieces a node holds: [world place, triangles, mesh name] each; none for a node that holds no mesh piece
	var out: Array = []
	if g is MeshInstance3D:
		var m := (g as MeshInstance3D).mesh
		var each := _triangles_of(m)
		if each > 0:
			out.append([g.global_position, each, Find.resource_name(m)])
	elif g is MultiMeshInstance3D:
		var many := (g as MultiMeshInstance3D).multimesh
		if many == null or many.mesh == null:
			return out
		var each := _triangles_of(many.mesh)
		if each == 0:
			return out
		var name := Find.resource_name(many.mesh)
		for i in many.instance_count:
			var at: Vector3 = g.global_transform * many.get_instance_transform(i).origin \
				if many.transform_format == MultiMesh.TRANSFORM_3D else g.global_transform * Vector3.ZERO
			out.append([at, each, name])
	return out


func _held_grid(grid: Node3D) -> Array:
	## a GridMap's cells whose item has a mesh: [world place, triangles, mesh name] each
	var out: Array = []
	var library: Variant = grid.get("mesh_library")
	if library == null:
		return out
	for cell: Vector3i in grid.call("get_used_cells"):
		var item: int = grid.call("get_cell_item", cell)
		var m: Mesh = (library as MeshLibrary).get_item_mesh(item) if item >= 0 else null
		var each := _triangles_of(m)
		if each > 0:
			out.append([grid.to_global(grid.call("map_to_local", cell)), each, Find.resource_name(m)])
	return out


func _keep(n: Node, owners: Variant) -> bool:
	## the select's keys but mesh and near (each piece by its own)
	if _component != "" and not Find.is_a(n, _component):
		return false
	if _name != "" and not String(n.name).matchn(_name):
		return false
	if owners != null:
		var at: Node = n
		while at != null:
			if (owners as Dictionary).has(at.get_instance_id()):
				return true
			at = at.get_parent()
		return false
	return true
