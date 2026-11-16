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
	write_rows(rows, sample)
