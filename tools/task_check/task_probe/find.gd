extends RefCounted
## Selects, points and `prop:` paths (contract sections 2 and 3): which nodes a select matches, where a point is, and
## the small readers every kind shares. An object is a Node; its parts are itself and its descendants. Only nodes that
## are shown match (not hidden, nor under a hidden node) unless the select says "inactive": true. Matches come in tree
## order (the root's children in order, depth first), so "the first match" is the same node in every play. A play's
## `set` stage writes a property by the path a prop: field reads (write).

const MAX_DEPTH := 3  ## a point nests this deep at most (a select inside a point inside a select)
const MAX_STEPS := 16  ## a prop: path of more steps reads nothing
const ALPHA_FLOOR := 0.004

static var probe: Node  ## the running TaskProbe autoload
static var _all: Array[Node] = []
static var _all_stamp := -1
static var _is_a: Dictionary = {}
static var _stems: Dictionary = {}
static var _stems_read := false
static var _globals: Dictionary = {}
static var _globals_read := false

const MEMBERS := {
	TYPE_VECTOR2: ["x", "y"], TYPE_VECTOR2I: ["x", "y"], TYPE_VECTOR3: ["x", "y", "z"], TYPE_VECTOR3I: ["x", "y", "z"],
	TYPE_VECTOR4: ["x", "y", "z", "w"], TYPE_VECTOR4I: ["x", "y", "z", "w"], TYPE_QUATERNION: ["x", "y", "z", "w"],
	TYPE_COLOR: ["r", "g", "b", "a"], TYPE_RECT2: ["position", "size", "end"], TYPE_RECT2I: ["position", "size", "end"],
	TYPE_AABB: ["position", "size", "end"], TYPE_TRANSFORM2D: ["x", "y", "origin"], TYPE_BASIS: ["x", "y", "z"],
	TYPE_TRANSFORM3D: ["basis", "origin"], TYPE_PLANE: ["normal", "d", "x", "y", "z"],
}


# ---------------------------------------------------------------- the spec's JSON


static func num(d: Dictionary, key: String, fallback: float = 0.0) -> float:
	var v: Variant = d.get(key)
	return float(v) if (v is float or v is int) and not is_nan(v) else fallback


static func has_num(d: Dictionary, key: String) -> bool:
	var v: Variant = d.get(key)
	return (v is float or v is int) and not is_nan(v)


static func text(d: Dictionary, key: String) -> String:
	var v: Variant = d.get(key)
	return v if v is String else ""


static func flag(d: Dictionary, key: String) -> bool:
	var v: Variant = d.get(key)
	return v is bool and v


static func obj(d: Dictionary, key: String) -> Dictionary:
	var v: Variant = d.get(key)
	return v if v is Dictionary else {}


static func numbers(v: Variant, count: int) -> Array:
	## `v` as `count` numbers, or [] when it isn't that
	if not (v is Array) or v.size() != count:
		return []
	for item: Variant in v:
		if not (item is float or item is int) or is_nan(item):
			return []
	return v


static func vec3(v: Variant) -> Vector3:
	var n := numbers(v, 3)
	return Vector3(n[0], n[1], n[2]) if n.size() == 3 else Vector3.ZERO


# ---------------------------------------------------------------- nodes


static func is_own(n: Node) -> bool:
	## the probe's own nodes are never selected
	return probe != null and (n == probe or probe.is_ancestor_of(n))


static func all_nodes() -> Array[Node]:
	## every node of the tree but the probe's own, in tree order; read once a pass
	if probe == null:
		return []
	if _all_stamp != probe.stamp:
		_all_stamp = probe.stamp
		_all = []
		for n: Node in probe.get_tree().root.find_children("*", "", true, false):
			if not is_own(n):
				_all.append(n)
	return _all


static func shown(n: Node) -> bool:
	## in the tree and not hidden, itself or by what it is under
	if n == null or not is_instance_valid(n) or not n.is_inside_tree():
		return false
	var at := n
	while at != null:
		if at is CanvasItem:
			return (at as CanvasItem).is_visible_in_tree()
		if at is Node3D:
			return (at as Node3D).is_visible_in_tree()
		if at is CanvasLayer and not (at as CanvasLayer).visible:
			return false
		at = at.get_parent()
	return true


static func place(n: Node) -> Variant:
	## where a node is: a Node3D's global position; a Node2D's or a Control's, in 2D units, with z 0; null for a
	## node with no place
	if n is Node3D:
		return (n as Node3D).global_position
	if n is Node2D:
		var p := (n as Node2D).global_position
		return Vector3(p.x, p.y, 0.0)
	if n is Control:
		var c := (n as Control).global_position
		return Vector3(c.x, c.y, 0.0)
	return null


static func angle(degrees: float) -> float:
	## an angle in (-180, 180]
	var a := fmod(degrees, 360.0)
	if a > 180.0:
		a -= 360.0
	if a <= -180.0:
		a += 360.0
	return a


static func angles(n: Node) -> Variant:
	## [pitch, yaw, roll] of a node's rotation in the world, degrees: a Node3D's global_rotation_degrees x, y, z; a
	## Node2D's rotation as roll; null for a node that has none
	if n is Node3D:
		var r := (n as Node3D).global_rotation_degrees
		return [angle(r.x), angle(r.y), angle(r.z)]
	if n is Node2D:
		return [0.0, 0.0, angle((n as Node2D).global_rotation_degrees)]
	return null


static func stem(path: String) -> String:
	return path.get_file().get_basename()


static func class_of(n: Node) -> String:
	## a row's class, for the logs: its script's class_name, else its script's file name, else its engine class
	var s: Script = n.get_script()
	if s != null:
		var named := String(s.get_global_name())
		if named != "":
			return named
		if s.resource_path != "":
			return stem(s.resource_path)
	return n.get_class()


static func is_a(n: Object, type: String) -> bool:
	## whether a node is of the class `type`: an engine class or one it inherits; its script's class_name, or the
	## script's file name without its extension, or those of a script it extends
	if n.is_class(type):
		return true
	var s: Script = n.get_script()
	if s == null:
		return false
	var key := "%d %s" % [s.get_instance_id(), type]
	if _is_a.has(key):
		return _is_a[key]
	var found := false
	var at := s
	while at != null and not found:
		found = String(at.get_global_name()) == type or (at.resource_path != "" and stem(at.resource_path) == type)
		at = at.get_base_script()
	_is_a[key] = found
	return found


static func names_class(type: String) -> bool:
	## whether a node can be of a class named `type`: an engine class, a script class_name, or a script file of the
	## project by that name
	if type == "":
		return false
	if ClassDB.class_exists(type):
		return true
	if not _globals_read:
		_globals_read = true
		for entry: Dictionary in ProjectSettings.get_global_class_list():
			_globals[String(entry.get("class", ""))] = true
	if _globals.has(type):
		return true
	if not _stems_read:
		_stems_read = true
		_scan("res://", 0)
	return _stems.has(type)


static func _scan(folder: String, depth: int) -> void:
	var dir := DirAccess.open(folder)
	if dir == null or depth > 12:
		return
	for sub in dir.get_directories():
		if not sub.begins_with(".") and not (folder == "res://addons/" and sub == "task_probe"):
			_scan(folder + sub + "/", depth + 1)
	for file in dir.get_files():
		# an exported project lists a script as <name>.gd.remap or <name>.gdc
		var name := file.trim_suffix(".remap")
		if name.get_extension() in ["gd", "gdc", "cs"]:
			_stems[name.get_basename()] = true


static func of_class(type: String, inactive: bool) -> Array[Node]:
	## the nodes of the class `type`, in tree order; shown ones, with `inactive` hidden ones too
	var found: Array[Node] = []
	if probe == null:
		return found
	var candidates: Array[Node] = []
	if ClassDB.class_exists(type):
		candidates = probe.get_tree().root.find_children("*", type, true, false)
	else:
		candidates = all_nodes()
	for n in candidates:
		if not is_own(n) and is_a(n, type) and (inactive or shown(n)):
			found.append(n)
	return found


static func part_of_class(n: Node, type: String) -> Node:
	## the node itself when it is of the class, else the first below it that is; null when none
	if is_a(n, type):
		return n
	for c: Node in n.find_children("*", "", true, false):
		if is_a(c, type):
			return c
	return null


static func part(n: Node, name: String) -> Node:
	## a Part of an object (rel_yaw:, world_yaw:, forward:): the node itself or one below it by its name, else the
	## first of them of that class
	if name == "":
		return null
	if String(n.name) == name:
		return n
	for c: Node in n.find_children("*", "", true, false):
		if String(c.name) == name:
			return c
	return part_of_class(n, name)


static func simulates(n: Node) -> bool:
	## a rigid body the physics moves (not frozen), or a shape of one
	var body: Node = n
	if n is CollisionShape3D or n is CollisionPolygon3D or n is CollisionShape2D or n is CollisionPolygon2D:
		body = n.get_parent()
	if body is RigidBody3D:
		return not (body as RigidBody3D).freeze
	if body is RigidBody2D:
		return not (body as RigidBody2D).freeze
	return false


static func draws(n: Node) -> bool:
	## a node that is drawn: a visual 3D node or a canvas item, shown
	return (n is VisualInstance3D or n is CanvasItem) and shown(n)


static func parts(n: Node, inactive: bool) -> Array[Node]:
	## the node and what is below it; the shown ones, with `inactive` all of them
	var found: Array[Node] = []
	if inactive or shown(n):
		found.append(n)
	for c: Node in n.find_children("*", "", true, false):
		if inactive or shown(c):
			found.append(c)
	return found


# ---------------------------------------------------------------- selects


static func check(select: Dictionary, about: String, depth: int = 0) -> void:
	## a class no node can be of (in `component` or `has.component`, here or in a select inside a point), said once as
	## "<about>: no component type T"
	if select.is_empty() or depth > MAX_DEPTH or probe == null:
		return
	var has := obj(select, "has")
	for name: String in [text(select, "component"), text(has, "component")]:
		if name != "" and not names_class(name):
			probe.error("%s: no component type %s" % [about, name])
	for near: Dictionary in [obj(select, "near"), obj(has, "near")]:
		check(obj(obj(near, "point"), "object"), about, depth + 1)


static func objects(select: Dictionary, depth: int = 0) -> Array[Node]:
	## the nodes an object select matches now, in tree order
	var found: Array[Node] = []
	if probe == null:
		return found
	var near := obj(select, "near")
	var centre: Variant = null
	if not near.is_empty():
		centre = point(obj(near, "point"), depth + 1)
		if centre == null:
			return found
	var has := obj(select, "has")
	var has_near := obj(has, "near")
	var has_centre: Variant = null
	if not has_near.is_empty():
		has_centre = point(obj(has_near, "point"), depth + 1)
		if has_centre == null:
			return found
	var inactive := flag(select, "inactive")
	if flag(select, "player"):
		var who: Node = probe.player()
		if who != null and matches(who, select, centre, has_centre):
			found.append(who)
		return found
	var type := text(select, "component")
	var candidates := all_nodes()
	if type != "":
		candidates = of_class(type, inactive)
	for n in candidates:
		if matches(n, select, centre, has_centre):
			found.append(n)
	return found


static func first(select: Dictionary, depth: int = 0) -> Node:
	var found := objects(select, depth)
	return found[0] if found.size() > 0 else null


static func matches(n: Node, select: Dictionary, centre: Variant, has_centre: Variant) -> bool:
	## whether `n` matches every key of an object select (`centre`, `has_centre`: its near's and its has.near's
	## points, resolved)
	if n == null or not is_instance_valid(n) or not n.is_inside_tree():
		return false
	var inactive := flag(select, "inactive")
	if not inactive and not shown(n):
		return false
	if select.get("player") is bool and not select["player"]:  # "player": false: anything but the player
		var who: Node = probe.player() if probe != null else null
		if who != null and (n == who or who.is_ancestor_of(n)):
			return false
	var name := text(select, "name")
	if name != "" and not String(n.name).matchn(name):
		return false
	var tag := text(select, "tag")
	if tag != "" and not n.is_in_group(tag):
		return false
	var type := text(select, "component")
	if type != "" and not is_a(n, type):
		return false
	var near := obj(select, "near")
	if not near.is_empty() and not within(near, centre, place(n)):
		return false
	var where: Variant = select.get("where")
	if where is Array:
		for condition: Variant in where:
			if not (condition is Dictionary) or not holds(n, condition):
				return false
	var has := obj(select, "has")
	if not has.is_empty() and not carries(n, has, has_centre, inactive):
		return false
	return true


static func within(near: Dictionary, centre: Variant, at: Variant) -> bool:
	## whether the place `at` is within a near's radius of `centre` and inside its height band
	if centre == null or at == null:
		return false
	var c: Vector3 = centre
	var p: Vector3 = at
	var radius := num(near, "radius")
	if p.distance_squared_to(c) > radius * radius:
		return false
	var y := p.y - c.y if flag(near, "y_relative") else p.y
	if has_num(near, "y_min") and y < num(near, "y_min"):
		return false
	if has_num(near, "y_max") and y > num(near, "y_max"):
		return false
	return true


static func carries(n: Node, has: Dictionary, centre: Variant, inactive: bool) -> bool:
	## has: the node or one below it matches every key given
	var type := text(has, "component")
	var near := obj(has, "near")
	for p in parts(n, inactive):
		if is_own(p):
			continue
		if type != "" and not is_a(p, type):
			continue
		if not near.is_empty() and not within(near, centre, place(p)):
			continue
		if flag(has, "visible") and not draws(p):
			continue
		if flag(has, "simulating") and not simulates(p):
			continue
		return true
	return false


static func holds(n: Node, condition: Dictionary) -> bool:
	## where: a property of the node (the path a prop: field reads) compared with a value; one that doesn't resolve
	## doesn't match
	var got: Variant = prop(n, text(condition, "prop"))
	var want: Variant = condition.get("value")
	var op := text(condition, "op")
	if got == null or want == null:
		return false
	if want is String:
		if not (got is String):
			return false
		return got == want if op == "==" else got != want if op == "!=" else false
	if got is String:
		return false
	var a: float = got
	var b: float = (1.0 if want else 0.0) if want is bool else float(want)
	match op:
		"==": return is_equal_approx(a, b)
		"!=": return not is_equal_approx(a, b)
		">": return a > b
		">=": return a >= b
		"<": return a < b
		"<=": return a <= b
	return false


static func owned_by(n: Node, owners: Array[Node]) -> bool:
	## whether `n` or a node above it is one of `owners`
	var at := n
	while at != null:
		if owners.has(at):
			return true
		at = at.get_parent()
	return false


# ---------------------------------------------------------------- points


static func point(p: Dictionary, depth: int = 0) -> Variant:
	## {"xyz": [x, y, z]}, {"player": true, "offset": [...]}, {"camera": true, "forward": m} or {"object": <select>,
	## "offset": [...]} (the first match), tried in that order: a Vector3, or null when it doesn't resolve now or lies
	## deeper than MAX_DEPTH
	if p.is_empty() or depth > MAX_DEPTH or probe == null:
		return null
	var offset := vec3(p.get("offset"))
	if numbers(p.get("xyz"), 3).size() == 3:
		return vec3(p.get("xyz"))
	if flag(p, "player"):
		var at: Variant = place(probe.player()) if probe.player() != null else null
		return null if at == null else at + offset
	if flag(p, "camera"):
		var view: Node = probe.view()
		if view == null:
			return null
		if view is Camera3D:
			var cam := view as Camera3D
			return cam.global_position - cam.global_basis.z.normalized() * num(p, "forward")
		return camera_place(view)
	var select := obj(p, "object")
	if select.is_empty():
		return null
	var found := first(select, depth + 1)
	var there: Variant = place(found) if found != null else null
	return null if there == null else there + offset


static func camera_place(view: Node) -> Variant:
	## where a camera is: a Camera3D's position; a Camera2D's centre of the screen, in 2D units, with z 0
	if view is Camera3D:
		return (view as Camera3D).global_position
	if view is Camera2D:
		var c := (view as Camera2D).get_screen_center_position()
		return Vector3(c.x, c.y, 0.0)
	return null


# ---------------------------------------------------------------- prop: paths


static func plain(value: Variant) -> Variant:
	## a read value as the checker takes it: numbers and booleans as numbers (NaN and infinities no value), a string
	## as it is (read through `match`), an object 1 when set and 0 when not, an array or a dictionary its size; a
	## vector or a colour without its part, or anything else, no value
	match typeof(value):
		TYPE_NIL:
			return 0.0
		TYPE_BOOL:
			return 1.0 if value else 0.0
		TYPE_INT:
			return float(value)
		TYPE_FLOAT:
			return null if is_nan(value) or is_inf(value) else value
		TYPE_STRING, TYPE_STRING_NAME, TYPE_NODE_PATH:
			return String(value)
		TYPE_OBJECT:
			return 1.0 if is_instance_valid(value) else 0.0
		TYPE_ARRAY, TYPE_DICTIONARY:
			return float(value.size())
	if typeof(value) >= TYPE_PACKED_BYTE_ARRAY:
		return float(value.size())
	return null


static func read(root: Variant, steps: PackedStringArray) -> Array:
	## [found, value] of a path (member[i].member...) read from `root`: a node's or a resource's properties and its
	## script's variables, a dictionary's entry by its key, an array's element, a vector's or a colour's part
	var value: Variant = root
	for token in steps:
		if value == null or (value is Object and not is_instance_valid(value)):
			return [false, null]
		var name := token
		var index := -1
		var open := token.find("[")
		if open >= 0:
			if open == 0 or not token.ends_with("]") or not token.substr(open + 1, token.length() - open - 2).is_valid_int():
				return [false, null]
			name = token.substr(0, open)
			index = token.substr(open + 1, token.length() - open - 2).to_int()
		if name == "":
			return [false, null]
		if value is Object:
			if not (name in value):
				return [false, null]
			value = value.get(name)
		elif value is Dictionary:
			if value.has(name):
				value = value[name]
			elif value.has(StringName(name)):
				value = value[StringName(name)]
			elif name.is_valid_int() and value.has(name.to_int()):
				value = value[name.to_int()]
			else:
				return [false, null]
		elif MEMBERS.has(typeof(value)) and name in MEMBERS[typeof(value)]:
			value = value[name]
		else:
			return [false, null]
		if open >= 0:
			var is_list := value is Array or typeof(value) >= TYPE_PACKED_BYTE_ARRAY
			if not is_list or index < 0 or index >= value.size():
				return [false, null]
			value = value[index]
	return [true, value]


static func prop(n: Node, path: String) -> Variant:
	## prop:<Class>.<member>[.<sub>] or prop:<member> on an object, without the "prop:": the node itself when it is of
	## that class, else the first below it that is; a path that names no class is read on the node itself; a class
	## alone is 1 when the node is or holds one. Null when it doesn't resolve.
	if n == null or path == "":
		return null
	var steps := path.split(".")
	if steps.size() > MAX_STEPS:
		return null
	if steps.size() > 1 and steps[0].find("[") < 0:
		var holder := part_of_class(n, steps[0])
		if holder != null:
			var found := read(holder, steps.slice(1))
			if found[0]:
				return plain(found[1])
	var own := read(n, steps)
	if own[0]:
		return plain(own[1])
	if steps.size() == 1 and part_of_class(n, path) != null:
		return 1.0
	return null


static func own_prop(n: Node, path: String) -> Variant:
	## prop:<path> on a node itself (a components row)
	if n == null or path == "":
		return null
	var steps := path.split(".")
	if steps.size() > MAX_STEPS:
		return null
	var found := read(n, steps)
	return plain(found[1]) if found[0] else null


static func write(n: Node, path: String, value: Variant) -> bool:
	## a `set` stage: the property a prop: path names (<Class>.<member>[.<sub>] or <member>[.<sub>], no array index)
	## written with `value`, as the type it holds: a number or a boolean onto a number or a boolean, a string onto a
	## string. A part of a vector or a colour (position.y) is written through the vector. False when the path names
	## no property, or one that can't take the value.
	if n == null or path == "" or path.find("[") >= 0:
		return false
	var steps := path.split(".")
	if steps.size() > MAX_STEPS:
		return false
	if steps.size() > 1:
		var holder := part_of_class(n, steps[0])
		if holder != null and _put(holder, steps, 1, value)[0]:
			return true
	return _put(n, steps, 0, value)[0]


static func _put(holder: Variant, steps: PackedStringArray, i: int, value: Variant) -> Array:
	## [written, the holder as it is now]: step `i` of a path written on `holder`. A vector, a colour or a transform
	## is a value, so the one written is handed back for its own holder to store
	if holder == null or (holder is Object and not is_instance_valid(holder)):
		return [false, holder]
	var name := steps[i]
	var key: Variant = name
	var current: Variant = null
	if holder is Object:
		if not (name in holder):
			return [false, holder]
		current = holder.get(name)
	elif holder is Dictionary:
		if holder.has(StringName(name)) and not holder.has(name):
			key = StringName(name)
		elif not holder.has(name) and name.is_valid_int() and holder.has(name.to_int()):
			key = name.to_int()
		elif not holder.has(name):
			return [false, holder]
		current = holder[key]
	elif MEMBERS.has(typeof(holder)) and name in MEMBERS[typeof(holder)]:
		current = holder[name]
	else:
		return [false, holder]
	var next: Variant = null
	if i == steps.size() - 1:
		var fitted := _fit(value, current)
		if not fitted[0]:
			return [false, holder]
		next = fitted[1]
	else:
		var inner := _put(current, steps, i + 1, value)
		if not inner[0]:
			return [false, holder]
		if current is Object or current is Dictionary:
			return [true, holder]  # written in place: nothing to store back
		next = inner[1]
	if holder is Object:
		holder.set(name, next)
		# a property that takes nothing (read-only, of another type) stays as it was: no write
		if _same(holder.get(name), current) and not _same(next, current):
			return [false, holder]
	elif holder is Dictionary:
		holder[key] = next
	else:
		holder[name] = next
	return [true, holder]


static func _same(a: Variant, b: Variant) -> bool:
	return typeof(a) == typeof(b) and a == b


static func _fit(value: Variant, current: Variant) -> Array:
	## [fits, the value as the property's own type]: a number or a boolean for a number or a boolean, a string for a
	## string; a property that holds nothing yet takes any of them
	var number := value is bool or value is int or value is float
	var as_float := (1.0 if value else 0.0) if value is bool else (float(value) if number else 0.0)
	match typeof(current):
		TYPE_NIL:
			return [number or value is String, value]
		TYPE_BOOL:
			return [number, as_float != 0.0]
		TYPE_INT:
			return [number, roundi(as_float)]
		TYPE_FLOAT:
			return [number, as_float]
		TYPE_STRING:
			return [value is String, value]
		TYPE_STRING_NAME:
			return [value is String, StringName(value) if value is String else value]
	return [false, value]


# ---------------------------------------------------------------- what a node draws and does


static func box(n: Node) -> Variant:
	## the world-aligned box around what a node and the nodes below it draw (the shown ones): an AABB, in 2D with no
	## depth; null when it draws nothing
	var have := false
	var all := AABB()
	for p in parts(n, false):
		var one: Variant = own_box(p)
		if one == null:
			continue
		all = all.merge(one) if have else one
		have = true
	return all if have else null


static func own_box(n: Node) -> Variant:
	## the world-aligned box of what one node draws or collides with; null for a node with none
	if n is VisualInstance3D and not (n is Light3D):
		var local := (n as VisualInstance3D).get_aabb()
		if local.size == Vector3.ZERO:
			return null
		return (n as VisualInstance3D).global_transform * local
	if n is CollisionShape3D and (n as CollisionShape3D).shape != null:
		var shape := (n as CollisionShape3D).shape.get_debug_mesh()
		return (n as CollisionShape3D).global_transform * shape.get_aabb() if shape != null else null
	var rect: Variant = null
	if n is Control:
		rect = (n as Control).get_global_rect()
	elif n is CollisionShape2D and (n as CollisionShape2D).shape != null:
		rect = (n as CollisionShape2D).global_transform * (n as CollisionShape2D).shape.get_rect()
	elif n is Node2D and n.has_method("get_rect"):
		var r: Variant = n.call("get_rect")
		if r is Rect2:
			rect = (n as Node2D).global_transform * (r as Rect2)
	if rect == null or (rect as Rect2).size == Vector2.ZERO:
		return null
	var r2: Rect2 = rect
	return AABB(Vector3(r2.position.x, r2.position.y, 0.0), Vector3(r2.size.x, r2.size.y, 0.0))


static func centre(n: Node) -> Variant:
	## the centre of what a node draws, else its place
	var around: Variant = box(n)
	return (around as AABB).get_center() if around != null else place(n)


static func own_velocity(n: Node) -> Variant:
	## the velocity a body reports: a CharacterBody's, a RigidBody's that isn't frozen; null for any other node
	if n is CharacterBody3D:
		return (n as CharacterBody3D).velocity
	if n is RigidBody3D and not (n as RigidBody3D).freeze:
		return (n as RigidBody3D).linear_velocity
	if n is CharacterBody2D:
		var v := (n as CharacterBody2D).velocity
		return Vector3(v.x, v.y, 0.0)
	if n is RigidBody2D and not (n as RigidBody2D).freeze:
		var w := (n as RigidBody2D).linear_velocity
		return Vector3(w.x, w.y, 0.0)
	return null


static func turn(n: Node) -> Variant:
	## a node's rotation in the world as a quaternion; null for a node that has none
	if n is Node3D:
		return (n as Node3D).global_basis.orthonormalized().get_rotation_quaternion()
	if n is Node2D:
		return Quaternion(Vector3.BACK, (n as Node2D).global_rotation)
	return null


static func forward(n: Node) -> Variant:
	## the way a node faces in the world, a unit vector: a Node3D's -Z, a Node2D's +X; null for any other node
	if n is Node3D:
		return -(n as Node3D).global_basis.z.normalized()
	if n is Node2D:
		var x := (n as Node2D).global_transform.x.normalized()
		return Vector3(x.x, x.y, 0.0)
	return null


static func resource_name(r: Resource) -> String:
	## a resource's name: the one it was given, else its file's name without the extension; "" when it has neither
	if r == null:
		return ""
	if r.resource_name != "":
		return r.resource_name
	return stem(r.resource_path) if r.resource_path != "" and r.resource_path.find("::") < 0 else ""
