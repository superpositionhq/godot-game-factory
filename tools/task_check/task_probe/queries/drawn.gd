extends "../query.gd"
## drawn: what is drawn in a place, whatever draws it (contract section 3). The place is a box: near a point, the box
## around its sphere cut to its height band; along a line, the square tube of `radius` around the segment. Every 3D
## part drawn in the game whose world box reaches the place (but one enclosing the whole place and 20 times its size: a
## sky dome, a room seen from inside) is put on render layer 20 for one frame, and the probe's own cameras, in
## SubViewports that share the game's 3D world and see layer 20 alone, draw it orthographic, each view's frustum
## exactly the place: near a point from above, below, +X and +Z (64 pixels across); along a line from two sides square
## to it (128 pixels along it). So every pixel drawn is in the place, and nothing outside it is drawn. The images are
## read when the frame is drawn (frame_drawn), the layers given back.
## "value" near a point: {"drawn", "motion", "base_r", "base_g", "base_b", "base_change", "pixels", "primitives"};
## along a line: {"drawn", "reach", "length", "pixels", "primitives"}; null when the place doesn't resolve or nothing
## can be drawn (headless, a 2D game).

const NEAR_SIZE := 64  ## pixels across each view of a place near a point
const LINE_SIZE := 128  ## pixels along each view of a line
const LINE_BINS := 128  ## the line's length read in at most this many steps, none finer than a pixel
const ENCLOSING := 20.0  ## a part around the whole place and this many times its size is left out
const CAP := 1024  ## parts one place draws at most: the first in tree order
const LAYER := 1 << 19  ## render layer 20: the parts in the place for the probe's cameras
const BACK := 0.05  ## m a camera stands back from the place's face
const NEAR_FIELDS := ["drawn", "motion", "base_r", "base_g", "base_b", "base_change", "pixels", "primitives"]
const LINE_FIELDS := ["drawn", "reach", "length", "pixels", "primitives"]

var _near: Dictionary = {}
var _line: Dictionary = {}
var _want_base := false
var _views: Array[Dictionary] = []  # {lit: SubViewport, dark: SubViewport or null, camera(s), map}
var _rig: Node
var _tagged: Array = []  # [weakref, layers before]: the parts put on layer 20 for this frame
var _shown := 0
var _pending: Dictionary = {}  # the sample whose value the frame completes
var _kind := ""  # "near", "line", "" (nothing to read)
var _place: Dictionary = {}  # this sample's place: for the reading
var _kept_before: PackedByteArray = PackedByteArray()
var _colour_before: PackedByteArray = PackedByteArray()
var _first_base: Variant = null
var _samples := 0
var _ms := 0.0


func load_query() -> void:
	_near = Find.obj(def, "near")
	_line = Find.obj(def, "line")
	if not _near.is_empty() and Find.num(_near, "radius") > 0.0:
		_kind = "near"
		known_fields(NEAR_FIELDS)
	elif _near.is_empty() and not _line.is_empty() and not Find.obj(_line, "from").is_empty() \
			and not Find.obj(_line, "to").is_empty() and Find.num(_line, "radius") > 0.0:
		_kind = "line"
		known_fields(LINE_FIELDS)
	else:
		probe.error("drawn %s: a place is `near` a point (a radius above 0) or a `line` (from, to and a radius above 0)" % id)
	for f in fields:
		_want_base = _want_base or f.begins_with("base_")


func sample(_t: float, sample: Dictionary) -> void:
	sample["value"] = null
	_pending = {}
	if _kind == "":
		return
	if DisplayServer.get_name() == "headless":
		probe.error("drawn %s: this play draws nothing (headless): drawn has no value" % id)
		return
	var cam: Node = probe.view()
	if not (cam is Camera3D):
		probe.error("drawn %s: the game shows no 3D camera (a 2D game): drawn reads the 3D world only" % id)
		return
	var started := Time.get_ticks_usec()
	var world := (cam as Camera3D).get_world_3d()
	var place: Variant = _place_near() if _kind == "near" else _place_line()
	if place == null:
		return
	_place = place
	var parts := _gather(place)
	_build(world)
	_aim(place)
	for part in parts:
		var g := part as GeometryInstance3D
		_tagged.append([weakref(g), g.layers])
		g.layers = g.layers | LAYER
	_shown = parts.size()
	for v: Dictionary in _views:
		(v["lit"] as SubViewport).render_target_update_mode = SubViewport.UPDATE_ONCE
		if v["dark"] != null:
			(v["dark"] as SubViewport).render_target_update_mode = SubViewport.UPDATE_ONCE
	_pending = sample
	_ms += (Time.get_ticks_usec() - started) / 1000.0


func needs_frame() -> bool:
	return not _pending.is_empty()


func frame_drawn(_image: Image, sample: Dictionary) -> void:
	var started := Time.get_ticks_usec()
	for tagged: Array in _tagged:
		var g: Object = (tagged[0] as WeakRef).get_ref()
		if g != null:
			(g as GeometryInstance3D).layers = tagged[1]
	_tagged.clear()
	if _pending.is_empty():
		return
	sample["value"] = _read_near() if _kind == "near" else _read_line()
	_pending = {}
	_ms += (Time.get_ticks_usec() - started) / 1000.0
	_samples += 1
	if _samples == 1 or _samples % 10 == 0:
		probe.note("drawn %s: %.2f ms a sample over %d, %d part(s) this sample" % [id, _ms / _samples, _samples, _shown])


# ---------------------------------------------------------------- the place


func _place_near() -> Variant:
	## {box, views: [{origin, basis, width, height, near, far, size}]}: the box around the sphere cut to the band,
	## seen from above, below, +X and +Z, each frustum exactly the box
	var p: Variant = Find.point(Find.obj(_near, "point"))
	if p == null:
		return null
	var r := Find.num(_near, "radius")
	var c: Vector3 = p
	var lo := c - Vector3.ONE * r
	var hi := c + Vector3.ONE * r
	var base_y := c.y if Find.flag(_near, "y_relative") else 0.0
	if Find.has_num(_near, "y_min"):
		lo.y = maxf(lo.y, base_y + Find.num(_near, "y_min"))
	if Find.has_num(_near, "y_max"):
		hi.y = minf(hi.y, base_y + Find.num(_near, "y_max"))
	if lo.y > hi.y:
		return null
	var box := AABB(lo, hi - lo)
	var mid := box.get_center()
	var size := box.size
	var views: Array = []
	# from above, looking down (image up is -Z), and from below, looking up (image up is +Z)
	views.append(_view(mid + Vector3.UP * (size.y / 2.0 + BACK), Basis(Vector3.RIGHT, Vector3.FORWARD, Vector3.UP),
		size.x, size.z, size.y, NEAR_SIZE))
	views.append(_view(mid + Vector3.DOWN * (size.y / 2.0 + BACK), Basis(Vector3.RIGHT, Vector3.BACK, Vector3.DOWN),
		size.x, size.z, size.y, NEAR_SIZE))
	# from +X looking -X, and from +Z looking -Z
	views.append(_view(mid + Vector3.RIGHT * (size.x / 2.0 + BACK), Basis(Vector3.FORWARD, Vector3.UP, Vector3.RIGHT),
		size.z, size.y, size.x, NEAR_SIZE))
	views.append(_view(mid + Vector3.BACK * (size.z / 2.0 + BACK), Basis(Vector3.RIGHT, Vector3.UP, Vector3.BACK),
		size.x, size.y, size.z, NEAR_SIZE))
	return {"box": box, "views": views}


func _place_line() -> Variant:
	## {box, a, d, length, views}: the square tube of radius r around the segment, seen from two sides square to it
	var a: Variant = Find.point(Find.obj(_line, "from"))
	var b: Variant = Find.point(Find.obj(_line, "to"))
	if a == null or b == null:
		return null
	var length := (a as Vector3).distance_to(b)
	if length < 0.01:
		return null
	var r := Find.num(_line, "radius")
	var d: Vector3 = ((b as Vector3) - (a as Vector3)) / length
	var side := d.cross(Vector3.UP).normalized() if absf(d.y) < 0.9 else d.cross(Vector3.FORWARD).normalized()
	var other := d.cross(side).normalized()
	var mid: Vector3 = ((a as Vector3) + (b as Vector3)) / 2.0
	var views: Array = []
	for look: Vector3 in [side, other]:
		var up := other if look == side else -side
		# the camera looks along -Z of its basis: Z is -look, X along the line, Y square to both (right-handed)
		views.append(_view(mid - look * (r + BACK), Basis(d, up, -look), length + 2.0 * r, 2.0 * r, 2.0 * r, LINE_SIZE))
	var box := AABB(a, Vector3.ZERO).expand(b).grow(r)
	return {"box": box, "a": a, "d": d, "length": length, "r": r, "views": views}


static func _view(origin: Vector3, basis: Basis, width: float, height: float, depth: float, across: int) -> Dictionary:
	## an orthographic view whose frustum is width x height x depth, standing BACK in front of it
	var w := across
	var h := maxi(1, int(round(across * height / maxf(width, 0.001))))
	return {"origin": origin, "basis": basis.orthonormalized(), "width": width, "height": height, "near": BACK,
		"far": BACK + depth, "size": Vector2i(w, h)}


func _gather(place: Dictionary) -> Array:
	## the 3D parts drawn in the game whose world box reaches the place, but one around the whole place and many times
	## its size; past CAP, the first in tree order
	var box: AABB = place["box"]
	var big := maxf(box.size.x, maxf(box.size.y, box.size.z))
	var found: Array = []
	for n in Find.all_nodes():
		if not (n is GeometryInstance3D) or Find.is_own(n):
			continue
		var g := n as GeometryInstance3D
		if not Find.shown(g) or g.layers == 0 or g.transparency >= 1.0 \
				or g.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			continue
		var around: Variant = world_box(g)
		if around == null:
			continue
		var world: AABB = around
		if not world.intersects(box):
			continue
		if _kind == "line" and not _crosses(world, place):
			continue
		if world.encloses(box) and minf(world.size.x, minf(world.size.y, world.size.z)) >= ENCLOSING * maxf(big, 0.01):
			continue
		found.append(g)
		if found.size() >= CAP:
			break
	return found


static func world_box(g: GeometryInstance3D) -> Variant:
	## where a part draws, in the world: its box; a GPU particle effect's visibility box, a CPU one's particles as they
	## are now; null for one with nothing to draw
	var local := g.get_aabb()
	if g is GPUParticles3D:
		local = (g as GPUParticles3D).visibility_aabb
	elif g is CPUParticles3D:
		var now: AABB = (g as CPUParticles3D).capture_aabb()
		if now.size == Vector3.ZERO:
			return null
		return now if not (g as CPUParticles3D).local_coords else g.global_transform * now
	if local.size == Vector3.ZERO:
		return null
	return g.global_transform * local


static func _crosses(world: AABB, place: Dictionary) -> bool:
	## whether a part's world box, grown by the line's radius, holds an end of the segment or meets it
	var grown := world.grow(place["r"])
	var a: Vector3 = place["a"]
	var b: Vector3 = a + (place["d"] as Vector3) * (place["length"] as float)
	return grown.has_point(a) or grown.has_point(b) or grown.intersects_segment(a, b) != null


# ---------------------------------------------------------------- the probe's cameras


func _build(world: World3D) -> void:
	## the views' SubViewports, made once (two per view with base_ fields: one lit by a white ambient light, one by none)
	var count := 4 if _kind == "near" else 2
	if _rig != null and _views.size() == count:
		for v: Dictionary in _views:
			(v["lit"] as SubViewport).world_3d = world
			if v["dark"] != null:
				(v["dark"] as SubViewport).world_3d = world
		return
	_rig = Node.new()
	_rig.name = "Drawn_" + id
	probe.add_child(_rig)
	_views.clear()
	for i in count:
		var lit := _viewport(world, Color.WHITE)
		var dark: SubViewport = _viewport(world, Color.BLACK) if _want_base and _kind == "near" else null
		_views.append({"lit": lit, "dark": dark})


func _viewport(world: World3D, ambient: Color) -> SubViewport:
	var view := SubViewport.new()
	view.world_3d = world
	view.transparent_bg = true
	view.msaa_3d = Viewport.MSAA_DISABLED
	view.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
	view.use_taa = false
	view.render_target_update_mode = SubViewport.UPDATE_DISABLED
	view.size = Vector2i(8, 8)
	var light := Environment.new()
	light.background_mode = Environment.BG_CLEAR_COLOR
	light.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	light.ambient_light_color = ambient
	light.ambient_light_energy = 1.0 if ambient != Color.BLACK else 0.0
	light.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	light.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.keep_aspect = Camera3D.KEEP_WIDTH
	camera.cull_mask = LAYER
	camera.environment = light
	view.add_child(camera)
	_rig.add_child(view)
	camera.current = true
	return view


func _aim(place: Dictionary) -> void:
	var views: Array = place["views"]
	for i in _views.size():
		var spec: Dictionary = views[i]
		for key: String in ["lit", "dark"]:
			var view: SubViewport = _views[i][key]
			if view == null:
				continue
			view.size = spec["size"]
			var camera := view.get_child(0) as Camera3D
			camera.global_transform = Transform3D(spec["basis"], spec["origin"])
			camera.size = spec["width"]
			camera.near = spec["near"]
			camera.far = spec["far"]


static func _bytes(view: SubViewport) -> PackedByteArray:
	## the view's pixels, RGBA8 as drawn (sRGB); empty when it wasn't drawn
	var image := view.get_texture().get_image()
	if image == null or image.is_empty():
		return PackedByteArray()
	if image.is_compressed():
		image.decompress()
	image.convert(Image.FORMAT_RGBA8)
	return image.get_data()


# ---------------------------------------------------------------- reading


func _read_near() -> Variant:
	var views: Array = _place["views"]
	var kept := PackedByteArray()
	var colour := PackedByteArray()
	var pixels := 0
	var opaque := 0
	var sum := Vector3.ZERO
	for i in _views.size():
		var size: Vector2i = views[i]["size"]
		var lit := _bytes(_views[i]["lit"])
		if lit.size() != size.x * size.y * 4:
			return null  # not drawn
		var dark := PackedByteArray()
		if _views[i]["dark"] != null:
			dark = _bytes(_views[i]["dark"])
			if dark.size() != lit.size():
				return null
		for at in size.x * size.y:
			var alpha := lit[at * 4 + 3]
			var on := alpha > 0
			kept.append(1 if on else 0)
			for ch in 3:
				colour.append(lit[at * 4 + ch] if on else 0)
			if not on:
				continue
			pixels += 1
			if alpha == 255 and not dark.is_empty():
				# the white-lit colour less the unlit one: what the white ambient light brought out of the surface,
				# its own colour (its emission and the game's lights cancel out)
				var a := Color8(lit[at * 4], lit[at * 4 + 1], lit[at * 4 + 2]).srgb_to_linear()
				var b := Color8(dark[at * 4], dark[at * 4 + 1], dark[at * 4 + 2]).srgb_to_linear()
				sum += Vector3(a.r - b.r, a.g - b.g, a.b - b.b)
				opaque += 1
	var value := {"drawn": 1.0 if pixels > 0 else 0.0, "pixels": float(pixels), "primitives": float(_shown)}
	# motion: of the pixels in the place now or at the previous sample, the share that changed (covered or not, or a
	# channel by more than one 8-bit step)
	if _kept_before.size() == kept.size():
		var union := 0
		var changed := 0
		for i in kept.size():
			if kept[i] == 0 and _kept_before[i] == 0:
				continue
			union += 1
			if kept[i] != _kept_before[i] or absi(colour[i * 3] - _colour_before[i * 3]) > 1 \
					or absi(colour[i * 3 + 1] - _colour_before[i * 3 + 1]) > 1 \
					or absi(colour[i * 3 + 2] - _colour_before[i * 3 + 2]) > 1:
				changed += 1
		value["motion"] = float(changed) / union if union > 0 else 0.0
	else:
		value["motion"] = null
	_kept_before = kept
	_colour_before = colour
	for key: String in ["base_r", "base_g", "base_b", "base_change"]:
		value[key] = null
	if _want_base and opaque > 0:
		var mean := sum / opaque
		value["base_r"] = mean.x
		value["base_g"] = mean.y
		value["base_b"] = mean.z
		if _first_base == null:
			_first_base = mean
		value["base_change"] = mean.distance_to(_first_base)
	return value


func _read_line() -> Variant:
	var views: Array = _place["views"]
	var length: float = _place["length"]
	var r: float = _place["r"]
	var width := length + 2.0 * r
	var steps := clampi(int(floor(length / maxf(length / LINE_BINS, width / LINE_SIZE))), 1, LINE_BINS)
	var bins := PackedByteArray()
	bins.resize(steps)
	var reach := -1.0
	var pixels := 0
	for i in _views.size():
		var size: Vector2i = views[i]["size"]
		var lit := _bytes(_views[i]["lit"])
		if lit.size() != size.x * size.y * 4:
			return null
		for y in size.y:
			for x in size.x:
				if lit[(y * size.x + x) * 4 + 3] == 0:
					continue
				# how far along the line this column is, from `from`
				var t := (x + 0.5) / size.x * width - r
				if t < 0.0 or t > length:
					continue
				pixels += 1
				reach = maxf(reach, t)
				bins[clampi(int(floor(t / length * steps)), 0, steps - 1)] = 1
	var covered := bins.count(1)
	return {"drawn": 1.0 if pixels > 0 else 0.0, "reach": reach if pixels > 0 else null,
		"length": covered * length / steps, "pixels": float(pixels), "primitives": float(_shown)}
