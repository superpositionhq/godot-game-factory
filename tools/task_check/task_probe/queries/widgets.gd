extends "../query.gd"
## widgets: the UI's own nodes and their state (contract section 3): the Controls of the game's window on screen (the
## visible field reads 1), every one with "visible": false in the select.
## "rows": [{"name", "class", <field>: value}] for every Control the select matches (select: component, a class of
## the Control, and with a name one above it too; name, a wildcard on its name; text, a regular expression its text
## must match; visible: false, hidden ones too).

const UiScan := preload("../ui_scan.gd")
const KNOWN := ["count", "visible", "text", "percent", "value", "interactable", "has_brush", "brush", "x", "y", "w", "h"]

var _type := ""
var _name := ""
var _text: RegEx
var _hidden_too := false
var _bad := false


func load_query() -> void:
	known_fields(KNOWN)
	var select := Find.obj(def, "select")
	_type = Find.text(select, "component")
	if _type != "" and not Find.names_class(_type):
		probe.error("widgets %s: no component type %s" % [id, _type])
	_name = Find.text(select, "name")
	var pattern := Find.text(select, "text")
	if pattern != "":
		_text = RegEx.new()
		if _text.compile(pattern, false) != OK:
			_bad = true  # matches nothing
			probe.error("widgets %s: the text regex %s doesn't compile" % [id, pattern])
	_hidden_too = select.get("visible") is bool and not select["visible"]


func sample(_t: float, sample: Dictionary) -> void:
	var rows: Array = []
	if not _bad:
		for c in UiScan.controls():
			if _name != "" and not String(c.name).matchn(_name):
				continue
			if _type != "" and not UiScan.is_a(c, _type, _name != ""):
				continue
			if not _hidden_too and not UiScan.visible(c):
				continue
			var shown: Variant = UiScan.text(c)
			if _text != null and (shown == null or _text.search(shown) == null):
				continue
			var row := {"name": String(c.name), "class": Find.class_of(c)}
			for f in fields:
				var v: Variant = _field(c, f, shown)
				if v != null:
					row[f] = v
			rows.append(row)
	write_rows(rows, sample)


static func _field(c: Control, f: String, shown: Variant) -> Variant:
	match f:
		"count":
			return 1.0
		"visible":
			return 1.0 if UiScan.visible(c) else 0.0
		"text":
			return shown
		"percent":
			return (c as Range).ratio if c is Range else null
		"value":
			if c is Range:
				return (c as Range).value
			if c is OptionButton:
				return float((c as OptionButton).selected)
			if c is BaseButton and (c as BaseButton).toggle_mode:
				return 1.0 if (c as BaseButton).button_pressed else 0.0
			if c is TabContainer:
				return float((c as TabContainer).current_tab)
			return null
		"interactable":
			return UiScan.usable(c)
		"has_brush":
			return (1.0 if UiScan.image(c) != null else 0.0) if UiScan.has_image(c) else null
		"brush":
			var picture := UiScan.image(c)
			return Find.resource_name(picture) if picture != null else null
		"x", "y", "w", "h":
			var r: Variant = UiScan.rect(c)
			return null if r == null else r[["x", "y", "w", "h"].find(f)]
	return null
