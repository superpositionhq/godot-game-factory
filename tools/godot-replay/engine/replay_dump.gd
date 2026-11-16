extends SceneTree
## Structure dump of a Godot project for the creation replay (docs/godot-replay.md, "What is checked").
##
##   godot --headless --path <project> --script <this file> -- <out.json>
##
## Walks the project (not .godot/, not addons/task_probe/, not a folder that carries .gdignore) and writes one JSON
## file with sorted keys:
##   scenes     every .tscn/.scn: its nodes in file order (path, class or instanced scene, groups, the properties the
##              file stores, which are the ones that differ from the class default) and its signal connections
##   resources  every .tres/.res: class and stored properties; a sub-resource as class + properties, an external
##              resource as its path
##   imported   every file with a .import beside it: importer, resource type and import settings
## Floats are rounded to 4 decimals. A file that does not load is listed with "error". Nothing is instantiated, so no
## game script runs.

const SKIP_DIRS := [".godot", ".git", "addons/task_probe"]
const SCENE_EXT := ["tscn", "scn"]
const RESOURCE_EXT := ["tres", "res"]
const MAX_DEPTH := 12

var _seen := {}


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("replay_dump: no output file given (-- <out.json>)")
		quit(2)
		return
	var out := {"schema": "godot-replay.dump/v1", "engine": Engine.get_version_info()["string"],
		"scenes": {}, "resources": {}, "imported": {}}
	var files: Array[String] = []
	_walk("res://", files)
	files.sort()
	for path in files:
		var ext := path.get_extension().to_lower()
		if ext in SCENE_EXT:
			out["scenes"][path] = _scene(path)
		elif ext in RESOURCE_EXT:
			out["resources"][path] = _resource_file(path)
		elif ext == "import":
			out["imported"][path.trim_suffix(".import")] = _import_file(path)
	out["done"] = true
	var f := FileAccess.open(args[0], FileAccess.WRITE)
	if f == null:
		printerr("replay_dump: cannot write ", args[0])
		quit(2)
		return
	f.store_string(JSON.stringify(out, " ", true) + "\n")
	f.close()
	print("replay_dump: %d scenes, %d resources, %d imported -> %s" % [
		out["scenes"].size(), out["resources"].size(), out["imported"].size(), args[0]])
	quit(0)


func _walk(dir: String, files: Array[String]) -> void:
	var d := DirAccess.open(dir)
	if d == null:
		return
	d.include_hidden = true
	if d.file_exists(".gdignore"):
		return
	for name in d.get_files():
		files.append(dir.path_join(name))
	for name in d.get_directories():
		var sub := dir.path_join(name)
		if sub.trim_prefix("res://") in SKIP_DIRS:
			continue
		_walk(sub, files)


func _scene(path: String) -> Dictionary:
	var ps := ResourceLoader.load(path, "PackedScene") as PackedScene
	if ps == null:
		return {"error": "does not load"}
	var st := ps.get_state()
	var nodes := []
	for i in st.get_node_count():
		var n := {"path": str(st.get_node_path(i)), "name": str(st.get_node_name(i)), "class": str(st.get_node_type(i))}
		var inst := st.get_node_instance(i)
		if inst != null:
			n["instance"] = inst.resource_path
		var groups := Array(st.get_node_groups(i)).map(func(g): return str(g))
		if not groups.is_empty():
			groups.sort()
			n["groups"] = groups
		var props := {}
		for k in st.get_node_property_count(i):
			var pname := str(st.get_node_property_name(i, k))
			if pname == "script":
				var s = st.get_node_property_value(i, k)
				n["script"] = s.resource_path if s is Resource else str(s)
			else:
				props[pname] = _value(st.get_node_property_value(i, k), 0)
		n["props"] = props
		nodes.append(n)
	var conns := []
	for i in st.get_connection_count():
		conns.append({"signal": str(st.get_connection_signal(i)), "from": str(st.get_connection_source(i)),
			"to": str(st.get_connection_target(i)), "method": str(st.get_connection_method(i)),
			"flags": st.get_connection_flags(i)})
	return {"nodes": nodes, "connections": conns}


func _resource_file(path: String) -> Dictionary:
	var r := ResourceLoader.load(path)
	if r == null:
		return {"error": "does not load"}
	_seen = {}
	return _resource(r, 0)


func _resource(r: Resource, depth: int) -> Dictionary:
	var out := {"class": r.get_class(), "props": {}}
	if _seen.has(r) or depth > MAX_DEPTH:
		out["props"] = "<seen>"
		return out
	_seen[r] = true
	var s = r.get_script()
	if s is Resource:
		out["script"] = s.resource_path
	for p in r.get_property_list():
		if not (p["usage"] & PROPERTY_USAGE_STORAGE):
			continue
		if p["name"] in ["script", "resource_path", "resource_local_to_scene", "resource_scene_unique_id"]:
			continue
		out["props"][p["name"]] = _value(r.get(p["name"]), depth + 1)
	_seen.erase(r)
	return out


## A value as stable JSON: floats rounded, an external resource as its path, a sub-resource as class + properties,
## packed arrays as their size and sha256, engine types through JSON.from_native.
func _value(v: Variant, depth: int) -> Variant:
	match typeof(v):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return v
		TYPE_FLOAT:
			return _round(v)
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return str(v)
		TYPE_OBJECT:
			if v == null:
				return null
			if v is Resource:
				var rp: String = v.resource_path
				if rp != "" and not rp.contains("::"):
					return rp
				return _resource(v, depth)
			return {"object": v.get_class()}
		TYPE_ARRAY:
			return (v as Array).map(func(x): return _value(x, depth))
		TYPE_DICTIONARY:
			var d := {}
			for k in v:
				d[str(_value(k, depth))] = _value(v[k], depth)
			return d
		TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, \
		TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY, TYPE_PACKED_VECTOR2_ARRAY, TYPE_PACKED_VECTOR3_ARRAY, \
		TYPE_PACKED_COLOR_ARRAY, TYPE_PACKED_VECTOR4_ARRAY:
			if v.size() <= 16:
				return _rounded(JSON.from_native(v))
			var h := HashingContext.new()
			h.start(HashingContext.HASH_SHA256)
			h.update(var_to_bytes(v))
			return {"packed": type_string(typeof(v)), "size": v.size(), "sha256": h.finish().hex_encode()}
		TYPE_RID, TYPE_CALLABLE, TYPE_SIGNAL:
			return type_string(typeof(v))
	return _rounded(JSON.from_native(v))


func _rounded(v: Variant) -> Variant:
	match typeof(v):
		TYPE_FLOAT:
			return _round(v)
		TYPE_ARRAY:
			return (v as Array).map(func(x): return _rounded(x))
		TYPE_DICTIONARY:
			var d := {}
			for k in v:
				d[k] = _rounded(v[k])
			return d
	return v


func _round(x: float) -> Variant:
	if is_nan(x) or is_inf(x):
		return str(x)
	return snappedf(x, 0.0001)


func _import_file(path: String) -> Dictionary:
	var cf := ConfigFile.new()
	if cf.load(path) != OK:
		return {"error": "does not load"}
	var params := {}
	if cf.has_section("params"):
		for k in cf.get_section_keys("params"):
			params[k] = _value(cf.get_value("params", k), 0)
	return {"importer": str(cf.get_value("remap", "importer", "")), "type": str(cf.get_value("remap", "type", "")),
		"params": params}
