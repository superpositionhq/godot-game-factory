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
		if flag(has, "lit"):
			var light: Variant = light_of(p)
			if light == null or not light["lit"]:
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


# ---------------------------------------------------------------- what gives light (lit, glow, has.lit)

const LIT_FLOOR := 0.01  ## a source brighter than this (linear luminance) is lit: a light, a material, a drawn pixel
const EFFECTS_3D := ["GPUParticles3D", "CPUParticles3D"]
const MAX_PASSES := 8  ## the materials of one next_pass chain read at most


static func luminance(c: Color) -> float:
	## the linear Rec. 709 luminance of a colour as a material or a light holds it (sRGB)
	var l := c.srgb_to_linear()
	return 0.2126 * l.r + 0.7152 * l.g + 0.0722 * l.b


static func material_light(m: Material) -> Array:
	## [known, light, exact, kind] of what a material gives off by its own properties, whatever lights it: an unshaded
	## material its albedo colour ("unlit"), one with emission on its emission colour times its energy ("emissive"),
	## each times its albedo's alpha when it is drawn transparent; any other standard material nothing. `exact` false
	## when a texture multiplies or adds to what is read (it is taken as white: a bound). `known` false for a
	## material whose light is its shader's own code (a ShaderMaterial).
	if m == null:
		return [true, 0.0, true, ""]  # the engine's default material: shaded, no emission
	if not (m is BaseMaterial3D):
		return [false, 0.0, false, ""]
	var standard := m as BaseMaterial3D
	var fades := standard.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED
	var alpha := standard.albedo_color.a if fades else 1.0
	var plain := not (fades and standard.albedo_texture != null)  # no texture sets the alpha
	if standard.shading_mode == BaseMaterial3D.SHADING_MODE_UNSHADED:
		return [true, luminance(standard.albedo_color) * alpha, standard.albedo_texture == null, "unlit"]
	if standard.emission_enabled:
		var colour := luminance(standard.emission)
		if standard.emission_texture != null and standard.emission_operator == BaseMaterial3D.EMISSION_OP_ADD:
			colour += 1.0
		return [true, colour * standard.emission_energy_multiplier * alpha, plain and standard.emission_texture == null,
			"emissive"]
	return [true, 0.0, true, ""]


static func _with_passes(materials: Array) -> Array:
	## each material followed by its next_pass chain: a shell drawn over the mesh gives light as its base does
	var all: Array = []
	for m: Variant in materials:
		all.append(m)
		var at: Variant = m
		for i in MAX_PASSES:
			at = (at as Material).next_pass if at is Material else null
			if at == null:
				break
			all.append(at)
	return all


static func drawn_with(n: Node) -> Variant:
	## the materials a 3D part or a 3D effect draws with, each with its next passes (an Array, null for a surface
	## without one), or null for a node that is neither: a mesh instance, a multimesh instance, a CSG shape; a
	## particle effect's draw passes
	if not (n is GeometryInstance3D):
		return null
	var geometry := n as GeometryInstance3D
	var meshes: Array = []
	var extra: Array = [geometry.material_overlay] if geometry.material_overlay != null else []
	if n is MeshInstance3D:
		var instance := n as MeshInstance3D
		if instance.mesh == null:
			return null
		var found: Array = []
		for i in instance.mesh.get_surface_count():
			found.append(instance.get_active_material(i))
		return _with_passes(found + extra)
	if n is MultiMeshInstance3D:
		if (n as MultiMeshInstance3D).multimesh == null or (n as MultiMeshInstance3D).multimesh.mesh == null:
			return null
		meshes = [(n as MultiMeshInstance3D).multimesh.mesh]
	elif n is CSGShape3D:
		if geometry.material_override == null and n.get("material") == null and n is CSGMesh3D:
			meshes = [(n as CSGMesh3D).mesh]  # a CSG mesh without a material of its own draws with its mesh's
		else:
			return _with_passes([geometry.material_override if geometry.material_override != null else n.get("material")] + extra)
	elif n is GPUParticles3D:
		for i in (n as GPUParticles3D).draw_passes:
			meshes.append((n as GPUParticles3D).get_draw_pass_mesh(i))
	elif n is CPUParticles3D:
		meshes = [(n as CPUParticles3D).mesh]
	else:
		return null
	if geometry.material_override != null:
		return _with_passes([geometry.material_override] + extra)
	var materials: Array = []
	for mesh: Variant in meshes:
		if mesh is Mesh:
			for i in (mesh as Mesh).get_surface_count():
				materials.append((mesh as Mesh).surface_get_material(i))
	return _with_passes(materials + extra)


static func part_drawn(n: Node) -> bool:
	## whether a 3D part is drawn at all: shown, on a render layer, not faded out, not only a shadow, inside its
	## visibility range from the camera, a multimesh with an instance to draw
	var geometry := n as GeometryInstance3D
	if not shown(n) or geometry.layers == 0 or geometry.transparency >= 1.0:
		return false
	if geometry.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
		return false
	if n is MultiMeshInstance3D:
		var many := (n as MultiMeshInstance3D).multimesh
		if many == null or many.instance_count == 0 or many.visible_instance_count == 0:
			return false
	var view: Node = probe.view() if probe != null else null
	if view is Camera3D and (geometry.visibility_range_begin > 0.0 or geometry.visibility_range_end > 0.0):
		var away := (view as Camera3D).global_position.distance_to(geometry.global_transform * geometry.get_aabb().get_center())
		if geometry.visibility_range_end > 0.0 and away > geometry.visibility_range_end + geometry.visibility_range_end_margin:
			return false
		if away < geometry.visibility_range_begin - geometry.visibility_range_begin_margin:
			return false
	return true


static func light_of(n: Node) -> Variant:
	## One node as a source of light; null for a node that is no source. {"read": it could be read, "lit", "glow": how
	## much (null: lit by something whose amount isn't known), "kinds": the kinds lit, "reads": how it was read,
	## "drawing": a drawing of it is under way, the frame's end tells}.
	## - a Light3D or a Light2D: lit when it lights the game (shown, not an editor's own, not one that takes light
	##   away; a Light2D enabled, a PointLight2D with a texture) and its energy times its colour's luminance (a
	##   Light2D's times its colour's alpha) is above LIT_FLOOR; glow is that amount;
	## - a 3D part (a mesh instance, a multimesh instance, a CSG shape): lit when it is drawn (part_drawn) and its
	##   brightest material gives more than LIT_FLOOR (material_light); glow that times a quarter of the surface of
	##   its box. A mesh whose materials don't tell is drawn alone (drawn_lit): lit or dark, no glow;
	## - a 3D particle effect: lit when it is emitting, drawn and what it draws gives more than LIT_FLOOR; its glow
	##   isn't known.
	var r := {"read": true, "lit": false, "glow": 0.0, "kinds": [], "reads": []}
	if n is Light3D:
		var light := n as Light3D
		var amount := light.light_energy * luminance(light.light_color)
		if shown(n) and not light.editor_only and not light.light_negative and amount > LIT_FLOOR:
			r.merge({"lit": true, "glow": amount, "kinds": ["light"]}, true)
		return r
	if n is Light2D:
		var flat := n as Light2D
		var given := flat.energy * luminance(flat.color) * flat.color.a
		var lights := shown(n) and flat.enabled and not flat.editor_only and flat.blend_mode != Light2D.BLEND_MODE_SUB
		if n is PointLight2D and (n as PointLight2D).texture == null:
			lights = false  # a point light without a texture lights nothing
		if lights and given > LIT_FLOOR:
			r.merge({"lit": true, "glow": given, "kinds": ["light"]}, true)
		return r
	var effect := false
	for type: String in EFFECTS_3D:
		effect = effect or n.is_class(type)
	var materials: Variant = drawn_with(n)
	if materials == null:
		return null
	if not part_drawn(n) or (effect and not bool(n.get("emitting"))):
		return r  # not drawn: no light, whatever its materials
	var best := 0.0
	var sure := 0.0  # the brightest light a material gives whatever its textures
	var kind := ""
	var exact := true
	var unknown := false
	var unlit := not (materials as Array).is_empty()
	for m: Variant in materials:
		var given: Array = material_light(m)
		unknown = unknown or not given[0]
		exact = exact and given[2]
		unlit = unlit and given[3] == "unlit"
		if given[2]:
			sure = maxf(sure, given[1])
		if given[1] > best:
			best = given[1]
			kind = given[3]
	if sure <= LIT_FLOOR and (unknown or best > LIT_FLOOR) and _drawable(n) != null:
		# its properties don't tell (a shader of its own, a texture on what is read): the part is drawn alone
		var seen: Variant = drawn_lit(n, materials)
		r["drawing"] = drawing(n)
		if seen == null:
			r["read"] = false
			r["reads"] = ["unread"]
		else:
			r["reads"] = ["drawn"]
			if seen:
				r.merge({"lit": true, "glow": null, "kinds": ["unlit" if unlit else "emissive"]}, true)
		return r
	if best > LIT_FLOOR:
		var around := (n as GeometryInstance3D).get_aabb().size * (n as Node3D).global_basis.get_scale().abs()
		var quarter := (around.x * around.y + around.y * around.z + around.z * around.x) / 2.0
		var amount: Variant = null if effect else best * quarter
		r.merge({"lit": true, "glow": amount, "kinds": ["effect" if effect else kind]}, true)
	elif unknown:
		r["read"] = false
	r["reads"] = ["unread"] if not r["read"] else ["props" if exact else "bound"]
	return r


# ---------------------------------------------------------------- lit, where only drawing tells

const DRAWN_BYTE := int(LIT_FLOOR * 255.0)  ## a pixel whose linear luminance is above this of 255 (LIT_FLOOR in 8 bits) in a room without light is lit
const DRAWN_SIZE := 128  ## pixels a side of each view
const DRAWN_VIEWS := [Vector3(1.0, 0.6, 0.8), Vector3(-0.8, 0.5, -1.0), Vector3(0.2, -1.0, 0.3)]

static var _drawn: Dictionary = {}  # part instance id -> {ref, sign, lit (null until first drawn), rig, next}
static var _drew := 0  # parts whose views the last frame drew
static var _calls_before := 0
static var _calls_said := false
static var _headless_said := false
static var pending := 0  ## goes up whenever a part is asked for whose first drawing isn't read yet


static func can_draw() -> bool:
	return DisplayServer.get_name() != "headless"


static func _drawable(n: Node) -> Mesh:
	## the mesh a part is drawn alone with: a mesh instance's, a multimesh instance's; null for any other part
	if n is MeshInstance3D:
		return (n as MeshInstance3D).mesh
	if n is MultiMeshInstance3D and (n as MultiMeshInstance3D).multimesh != null:
		return (n as MultiMeshInstance3D).multimesh.mesh
	return null


static func _signature(n: Node, materials: Array) -> int:
	## what the part's own light depends on: its mesh and, of each material and its next passes, what gives light (a
	## shader's every parameter); another signature means it is drawn again when next asked for
	var said: Array = [_drawable(n).get_instance_id()]
	for m: Variant in materials:
		if m is BaseMaterial3D:
			var standard := m as BaseMaterial3D
			said.append_array([
				standard.get_instance_id(), standard.shading_mode, standard.albedo_color, standard.transparency,
				standard.emission_enabled, standard.emission, standard.emission_energy_multiplier,
				standard.emission_operator, _identity(standard.albedo_texture), _identity(standard.emission_texture)])
		elif m is ShaderMaterial and (m as ShaderMaterial).shader != null:
			var custom := m as ShaderMaterial
			said.append_array([custom.get_instance_id(), custom.shader.get_instance_id(), hash(custom.shader.code)])
			for uniform: Dictionary in custom.shader.get_shader_uniform_list():
				said.append(_identity(custom.get_shader_parameter(uniform["name"])))
		else:
			said.append(_identity(m))
	for property: Dictionary in n.get_property_list():
		if String(property["name"]).begins_with("instance_shader_parameters/"):
			said.append(_identity(n.get(property["name"])))
	return hash(said)


static func _identity(value: Variant) -> Variant:
	return (value as Object).get_instance_id() if value is Object and is_instance_valid(value) else value


static func drawing(n: Node) -> bool:
	## whether a drawing of the part is under way (the frame's end reads it)
	var e: Variant = _drawn.get(n.get_instance_id())
	return e != null and e["rig"] != null and is_instance_valid(e["rig"])


static func drawn_lit(n: Node, materials: Array) -> Variant:
	## Whether a mesh part gives light of its own, as drawn alone in a room without light: true, false, or null while
	## its first drawing isn't read yet (it is by the frame's end: light_collect) or in a play that draws nothing. A
	## part is drawn only when it is asked for and what its light depends on changed since its last drawing
	## (_signature); until the new drawing is read the answer stays the last one.
	if not can_draw():
		if not _headless_said and probe != null:
			_headless_said = true
			probe.error("lit: a part whose light only a drawing tells (a shader of its own, a texture on its light) has no value: this play draws nothing (headless)")
		return null
	var id := n.get_instance_id()
	var sign := _signature(n, materials)
	var e: Variant = _drawn.get(id)
	if e == null:
		e = {"ref": weakref(n), "sign": 0, "lit": null, "rig": null, "next": 0}
		_drawn[id] = e
	if not drawing(n) and (e["lit"] == null or e["sign"] != sign):
		e["rig"] = _room(n)
		e["next"] = sign
	if e["lit"] == null:
		pending += 1
	return e["lit"]


static func _room(n: Node) -> Node:
	## the part's mesh with its materials alone in a world of its own, black and without light, seen from three sides
	var mesh := _drawable(n)
	var rig := Node.new()
	rig.name = "LitRoom%d" % n.get_instance_id()
	var world := World3D.new()
	var dark := Environment.new()
	dark.background_mode = Environment.BG_COLOR
	dark.background_color = Color.BLACK
	dark.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	dark.ambient_light_color = Color.BLACK
	dark.ambient_light_energy = 0.0
	dark.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	world.environment = dark
	var box := mesh.get_aabb()
	var centre := box.get_center()
	var radius := maxf(box.size.length() / 2.0, 0.001)
	for i in DRAWN_VIEWS.size():
		var view := SubViewport.new()
		view.size = Vector2i(DRAWN_SIZE, DRAWN_SIZE)
		view.world_3d = world
		view.render_target_update_mode = SubViewport.UPDATE_ONCE
		var from: Vector3 = (DRAWN_VIEWS[i] as Vector3).normalized()
		var camera := Camera3D.new()
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		camera.size = radius * 2.2
		camera.near = radius * 0.1
		camera.far = radius * 6.0
		camera.transform = Transform3D(Basis.looking_at(-from, Vector3.RIGHT if absf(from.y) > 0.9 else Vector3.UP), centre + from * radius * 3.0)
		camera.current = true
		view.add_child(camera)
		if i == 0:
			var copy := MeshInstance3D.new()
			copy.mesh = mesh
			var part := n as GeometryInstance3D
			copy.material_override = part.material_override
			copy.material_overlay = part.material_overlay
			if n is MeshInstance3D:
				for surface in mesh.get_surface_count():
					copy.set_surface_override_material(surface, (n as MeshInstance3D).get_surface_override_material(surface))
			for property: Dictionary in n.get_property_list():
				if String(property["name"]).begins_with("instance_shader_parameters/"):
					copy.set(property["name"], n.get(property["name"]))
			view.add_child(copy)
		rig.add_child(view)
	probe.add_child(rig)
	return rig


static func light_collect() -> void:
	## the rooms a frame has drawn are read: each part lit when a pixel of a view has a linear luminance above the floor
	var read := 0
	for id: int in _drawn.keys():
		var e: Dictionary = _drawn[id]
		if e["rig"] == null or not is_instance_valid(e["rig"]):
			continue
		var bright := 0
		var brightest := 0
		var seen := true
		for view: Node in (e["rig"] as Node).get_children():
			var image := (view as SubViewport).get_texture().get_image()
			if image == null or image.is_empty():
				seen = false
				break
			image.srgb_to_linear()  # the frame holds sRGB colours; L8 then weighs the linear ones as luminance does
			image.convert(Image.FORMAT_L8)
			var bytes := image.get_data()
			if bytes.count(0) == bytes.size():
				continue  # black all over
			for b in bytes:
				brightest = maxi(brightest, b)
				if b > DRAWN_BYTE:
					bright += 1
		if not seen:
			continue  # not drawn yet: read at the next look
		var lit := bright >= 1
		var changed: bool = e["lit"] == null or e["lit"] != lit
		e["lit"] = lit
		e["sign"] = e["next"]
		(e["rig"] as Node).queue_free()
		e["rig"] = null
		read += 1
		if changed:
			var n: Node = e["ref"].get_ref()
			var named := "a part" if n == null else "%s/%s" % [n.get_parent().name, n.name] if n.get_parent() != null else String(n.name)
			probe.note("lit: %s drawn alone in a room without light: %d bright pixel(s), the brightest %d of 255, %s" % [
				named, bright, brightest, "lit" if lit else "dark"])
	_drew += read


static func light_tick() -> void:
	## once a frame, before the game's scripts (the probe's own frame): the rooms the frame before drew are read, and
	## the parts that are gone are forgotten
	if probe == null or _drawn.is_empty():
		return
	var calls := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	if _drew > 0 and not _calls_said:
		_calls_said = true
		probe.note("lit: the frame that drew %d part(s) alone had %d draw call(s) in all (the frame before it: %d)" % [
			_drew, calls, _calls_before])
	_drew = 0
	_calls_before = calls
	light_collect()
	for id: int in _drawn.keys():
		var e: Dictionary = _drawn[id]
		var n: Node = e["ref"].get_ref()
		if n == null or not n.is_inside_tree():
			if e["rig"] != null and is_instance_valid(e["rig"]):
				(e["rig"] as Node).queue_free()
			_drawn.erase(id)


static func lit_selects(value: Variant, found: Array) -> void:
	## every object select inside `value` (a play's input row, a select) that asks for a lit part (has.lit)
	if value is Dictionary:
		if flag(obj(value, "has"), "lit"):
			found.append(value)
		for key: Variant in value:
			lit_selects(value[key], found)
	elif value is Array:
		for item: Variant in value:
			lit_selects(item, found)


static func light_of_object(n: Node) -> Dictionary:
	## An object's light: its sources summed, itself and the nodes below it. One with nothing that gives light reads
	## dark; one with a source that couldn't be read has no value ("read" false) unless another source is lit.
	var total := {"read": true, "lit": false, "glow": 0.0, "kinds": [], "reads": []}
	var unread := false
	var under_way := false  # a part of it is being drawn: the frame's end tells
	var nodes: Array[Node] = [n]
	nodes.append_array(n.find_children("*", "", true, false))
	for p in nodes:
		var r: Variant = light_of(p)
		if r == null:
			continue
		unread = unread or not r["read"]
		under_way = under_way or r.get("drawing", false)
		total["lit"] = total["lit"] or r["lit"]
		if r["lit"]:
			total["glow"] = null if total["glow"] == null or r["glow"] == null else total["glow"] + r["glow"]
		for key: String in ["kinds", "reads"]:
			for word: String in r[key]:
				if not total[key].has(word):
					total[key].append(word)
	total["read"] = total["lit"] or not unread
	total["drawing"] = under_way
	return total


static func light_field(reading: Variant, field: String, row: Dictionary) -> Variant:
	## `lit` or `glow` of a reading (light_of, light_of_object), and its notes in the row for the logs: glow_sources,
	## the kinds lit, and glow_read, how it was read
	if reading == null:
		return null
	row.erase("glow_sources")
	if not reading["kinds"].is_empty():
		row["glow_sources"] = ",".join(PackedStringArray(reading["kinds"]))
	if not reading["reads"].is_empty():
		row["glow_read"] = ",".join(PackedStringArray(reading["reads"]))
	if not reading["read"]:
		return null
	if field == "lit":
		return 1.0 if reading["lit"] else 0.0
	return reading["glow"]


static func resource_name(r: Resource) -> String:
	## a resource's name: the one it was given, else its file's name without the extension; "" when it has neither
	if r == null:
		return ""
	if r.resource_name != "":
		return r.resource_name
	return stem(r.resource_path) if r.resource_path != "" and r.resource_path.find("::") < 0 else ""
