extends "../query.gd"
## ui: what the UI shows on screen (contract section 3). Every element on screen at the sample: each Control that is
## drawn gives a row for what it draws (text: a Label's, a RichTextLabel's, a button's or a text field's text; image:
## a TextureRect's, a NinePatchRect's, a TextureButton's or a TextureProgressBar's picture, a button's icon; box: a
## ColorRect, a Panel, a button, a bar, a slider, a text field). The select alone decides, so every measure on it
## counts and reads the same elements.
## "rows": [{"name", "class", "source", "kind", <field>: value}] (fields count, text, x, y, w, h)

const UiScan := preload("../ui_scan.gd")
const KNOWN := ["count", "text", "x", "y", "w", "h"]

var _kind := ""
var _text: RegEx
var _bad := false
var _rect: Array = []


func load_query() -> void:
	known_fields(KNOWN)
	var select := Find.obj(def, "select")
	_kind = Find.text(select, "kind")
	if _kind != "" and not (_kind in ["text", "box", "image"]):
		probe.error("ui %s: no element kind %s (text, box, image)" % [id, _kind])
	var pattern := Find.text(select, "text")
	if pattern != "":
		_text = RegEx.new()
		if _text.compile(pattern, false) != OK:
			_bad = true  # matches nothing
			probe.error("ui %s: the text regex %s doesn't compile" % [id, pattern])
	_rect = Find.numbers(select.get("rect"), 4)


func sample(_t: float, sample: Dictionary) -> void:
	var rows: Array = []
	if not _bad:
		for c in UiScan.controls():
			if not UiScan.drawn(c):
				continue
			var r: Variant = UiScan.rect(c)
			if r == null:
				continue
			if _rect.size() == 4:
				var cx: float = r[0] + r[2] / 2.0
				var cy: float = r[1] + r[3] / 2.0
				if cx < minf(_rect[0], _rect[2]) or cx > maxf(_rect[0], _rect[2]) or cy < minf(_rect[1], _rect[3]) \
						or cy > maxf(_rect[1], _rect[3]):
					continue
			for element in UiScan.kinds(c):
				if (_kind != "" and element != _kind) or (_text != null and element != "text"):
					continue
				var shown: String = UiScan.own_text(c) if element == "text" else ""
				if _text != null and _text.search(shown) == null:
					continue
				var row := {"name": String(c.name), "class": Find.class_of(c), "source": "control", "kind": element}
				for f in fields:
					if f == "count":
						row[f] = 1.0
					elif f == "text":
						if element == "text":
							row[f] = shown
					else:
						row[f] = r[["x", "y", "w", "h"].find(f)]
				rows.append(row)
		if _kind == "" or _kind == "text":
			_labels_3d(rows)
	write_rows(rows, sample)


static func label_corners(label: Label3D, camera: Camera3D) -> Array[Vector3]:
	## the four corners of a Label3D's text as it is drawn: its own box's face, turned to the camera as its billboard
	## mode turns it (enabled and particles: the camera's right and up; fixed Y: up kept, right square to the view),
	## its scale kept, and with fixed_size grown with its distance as its shader grows it (perspective: the depth of
	## its place in the camera's view; orthogonal: half the camera's size)
	var box := label.get_aabb()
	if label.billboard != BaseMaterial3D.BILLBOARD_DISABLED:
		# a billboard's own box is grown to hold it turned every way: its face is its text's size about the box's centre
		var font: Font = label.font if label.font != null else ThemeDB.fallback_font
		var wrap := label.width if label.autowrap_mode != TextServer.AUTOWRAP_OFF else -1.0
		var size := font.get_multiline_string_size(label.text, label.horizontal_alignment, wrap, label.font_size) \
			* label.pixel_size  # as its box is without a billboard (measured: EXIT 0.33 x 0.225 m both ways)
		var middle := box.get_center()
		box = AABB(Vector3(middle.x - size.x / 2.0, middle.y - size.y / 2.0, middle.z), Vector3(size.x, size.y, 0.0))
	var basis := label.global_basis
	var right := basis.x
	var up := basis.y
	var view := camera.global_basis
	match label.billboard:
		BaseMaterial3D.BILLBOARD_ENABLED, BaseMaterial3D.BILLBOARD_PARTICLES:
			right = view.x.normalized() * basis.x.length()
			up = view.y.normalized() * basis.y.length()
		BaseMaterial3D.BILLBOARD_FIXED_Y:
			right = Vector3.UP.cross(view.z).normalized() * basis.x.length()
			up = Vector3.UP * basis.y.length()
	var grow := 1.0
	if label.fixed_size:
		if camera.projection == Camera3D.PROJECTION_ORTHOGONAL:
			grow = camera.size / 2.0
		else:
			grow = maxf(-(camera.global_transform.affine_inverse() * label.global_position).z, 0.0)
	var corners: Array[Vector3] = []
	for x: float in [box.position.x, box.end.x]:
		for y: float in [box.position.y, box.end.y]:
			corners.append(label.global_position + (right * x + up * y) * grow)
	return corners


func _labels_3d(rows: Array) -> void:
	## the Label3Ds the game's camera shows: each a text row (source label3d), its rectangle the box around its own box
	## as the camera projects it; one behind the camera, outside the frame, hidden, faded out or blank isn't read
	var cam: Node = probe.view()
	if not (cam is Camera3D):
		return
	var camera := cam as Camera3D
	var frame := UiScan.frame_size()
	if frame.x <= 0.0 or frame.y <= 0.0:
		return
	for n in Find.of_class("Label3D", false):
		var label := n as Label3D
		if Find.is_own(label) or not Find.shown(label) or label.layers & camera.cull_mask == 0:
			continue
		if label.modulate.a <= Find.ALPHA_FLOOR or label.text.strip_edges() == "":
			continue
		if camera.is_position_behind(label.global_position):
			continue
		var have := false
		var lo := Vector2.ZERO
		var hi := Vector2.ZERO
		for corner: Vector3 in label_corners(label, camera):
			if camera.is_position_behind(corner):
				continue  # a corner past the camera's plane: the rest still place it
			var at := camera.unproject_position(corner)
			lo = at if not have else lo.min(at)
			hi = at if not have else hi.max(at)
			have = true
		if not have or not Rect2(Vector2.ZERO, frame).intersects(Rect2(lo, hi - lo)):
			continue
		var r := [lo.x / frame.x, lo.y / frame.y, (hi.x - lo.x) / frame.x, (hi.y - lo.y) / frame.y]
		if _rect.size() == 4:
			var cx: float = r[0] + r[2] / 2.0
			var cy: float = r[1] + r[3] / 2.0
			if cx < minf(_rect[0], _rect[2]) or cx > maxf(_rect[0], _rect[2]) or cy < minf(_rect[1], _rect[3]) \
					or cy > maxf(_rect[1], _rect[3]):
				continue
		var shown := label.text
		if _text != null and _text.search(shown) == null:
			continue
		var row := {"name": String(label.name), "class": Find.class_of(label), "source": "label3d", "kind": "text"}
		for f in fields:
			if f == "count":
				row[f] = 1.0
			elif f == "text":
				row[f] = shown
			else:
				row[f] = r[["x", "y", "w", "h"].find(f)]
		rows.append(row)
