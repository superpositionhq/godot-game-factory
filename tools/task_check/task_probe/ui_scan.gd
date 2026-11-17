extends RefCounted
## The UI as widgets, ui, a widget click and a touch on a widget read it: the Control nodes of the game's window.
## A rectangle is in fractions of the frame, y down from the top, whatever anchor, container or canvas layer placed it.

const Find := preload("find.gd")


static func controls() -> Array[Control]:
	## every Control of the game's window, hidden ones too, in tree order
	var found: Array[Control] = []
	if Find.probe == null:
		return found
	var root := Find.probe.get_tree().root
	for n: Node in root.find_children("*", "Control", true, false):
		var c := n as Control
		if c != null and not Find.is_own(c) and c.get_viewport() == root:
			found.append(c)
	return found


static func frame_size() -> Vector2:
	## the size Controls are laid out in: the frame, before any stretch to the window
	return Find.probe.get_tree().root.get_visible_rect().size


static func box(c: Control) -> Rect2:
	## its rectangle in the frame's own units (a turned one: the box around it)
	return c.get_global_transform_with_canvas() * Rect2(Vector2.ZERO, c.size)


static func rect(c: Control) -> Variant:
	## [x, y, w, h] in fractions of the frame, or null for a Control of no size
	var frame := frame_size()
	var r := box(c)
	if frame.x <= 0.0 or frame.y <= 0.0 or r.size.x <= 0.0 or r.size.y <= 0.0:
		return null
	return [r.position.x / frame.x, r.position.y / frame.y, r.size.x / frame.x, r.size.y / frame.y]


static func alpha(c: CanvasItem) -> float:
	## the opacity it is drawn with: its own and that of every canvas item above it
	var a := c.self_modulate.a
	var at: Node = c
	while at is CanvasItem:
		a *= (at as CanvasItem).modulate.a
		at = at.get_parent()
	return a


static func in_frame(c: Control) -> bool:
	return Rect2(Vector2.ZERO, frame_size()).intersects(box(c))


static func visible(c: Control) -> bool:
	## on screen, as a widget: shown (itself and everything above it, its canvas layer too), drawn with an opacity above
	## the floor (its own self_modulate and the modulate of it and every canvas item above it), inside the frame, and
	## not wholly outside a Control above it that clips what it holds. One of no size counts as shown (a container
	## that only holds others); one covered by another Control does too.
	if not c.is_visible_in_tree() or alpha(c) <= Find.ALPHA_FLOOR:
		return false
	var r := box(c)
	if r.size.x <= 0.0 or r.size.y <= 0.0:
		return true
	if not in_frame(c):
		return false
	var at := c.get_parent()
	while at is Control:
		if (at as Control).clip_contents and not box(at as Control).intersects(r):
			return false
		at = at.get_parent()
	return true


static func reachable(c: Control) -> bool:
	## where an input may land, as a player presses it: shown (itself and everything above it, its canvas layer too),
	## the modulate of it and every canvas item above it above the floor, inside the frame (one of no size counts).
	## Its own self_modulate and clipping don't count: an invisible hit area over art is pressed like any button.
	if not c.is_visible_in_tree():
		return false
	var above := 1.0
	var at: Node = c
	while at is CanvasItem:
		above *= (at as CanvasItem).modulate.a
		at = at.get_parent()
	if above <= Find.ALPHA_FLOOR:
		return false
	var r := box(c)
	if r.size.x <= 0.0 or r.size.y <= 0.0:
		return true
	return in_frame(c)


static func drawn(c: Control) -> bool:
	## on screen and of some size: what ui reads
	var r := box(c)
	return r.size.x > 0.0 and r.size.y > 0.0 and visible(c)


static func own_text(c: Control) -> Variant:
	## the text a Control shows of its own, as shown (tags stripped, a typewriter reveal honoured); null for one that
	## shows none
	if c is Label:
		var label := c as Label
		var all := label.text
		return all.substr(0, label.visible_characters) if label.visible_characters >= 0 else all
	if c is RichTextLabel:
		var rich := c as RichTextLabel
		var parsed := rich.get_parsed_text()
		return parsed.substr(0, rich.visible_characters) if rich.visible_characters >= 0 else parsed
	if c is LineEdit:
		return (c as LineEdit).text
	if c is TextEdit:
		return (c as TextEdit).text
	if c is Button:
		return (c as Button).text
	if c is LinkButton:
		return (c as LinkButton).text
	return null


static func text(c: Control) -> Variant:
	## a widget's text: its own; a button with none reads the first label below it
	var own: Variant = own_text(c)
	if c is BaseButton and (own == null or own == ""):
		for n: Node in c.find_children("*", "Control", true, false):
			var below: Variant = own_text(n as Control) if n is Label or n is RichTextLabel else null
			if below != null and below != "":
				return below
	return own


static func image(c: Control) -> Texture2D:
	## the picture a Control shows; null for one that shows none
	if c is TextureRect:
		return (c as TextureRect).texture
	if c is NinePatchRect:
		return (c as NinePatchRect).texture
	if c is TextureButton:
		return (c as TextureButton).texture_normal
	if c is TextureProgressBar:
		var bar := c as TextureProgressBar
		return bar.texture_progress if bar.texture_progress != null else bar.texture_under
	if c is Button:
		return (c as Button).icon
	return null


static func has_image(c: Control) -> bool:
	return c is TextureRect or c is NinePatchRect or c is TextureButton or c is TextureProgressBar or c is Button


static func kinds(c: Control) -> Array[String]:
	## what a Control draws, as ui rows: "text", "image", "box"; none for one that draws nothing of its own (a
	## container, a bare Control)
	var found: Array[String] = []
	if c is ColorRect or c is Panel or c is PanelContainer or c is BaseButton or c is Range or c is LineEdit or c is TextEdit \
			or c is ItemList or c is Tree or c is TabBar or c is TabContainer:
		if not (c is TextureButton) and not (c is TextureProgressBar) and not (c is Button and (c as Button).flat):
			found.append("box")
	if image(c) != null:
		found.append("image")
	var shown: Variant = own_text(c)
	if shown != null and shown.strip_edges() != "":
		found.append("text")
	return found


static func is_a(c: Control, type: String, with_above: bool) -> bool:
	## a widget select's `component`: the Control's class; with a name in the select, a class of a Control above too
	if Find.is_a(c, type):
		return true
	if with_above:
		var at := c.get_parent()
		while at is Control:
			if Find.is_a(at, type):
				return true
			at = at.get_parent()
	return false


static func usable(c: Control) -> Variant:
	## 1 when a player can use it, 0 when it is disabled; null for a Control that is never used
	if c is BaseButton:
		return 0.0 if (c as BaseButton).disabled else 1.0
	if c is LineEdit:
		return 1.0 if (c as LineEdit).editable else 0.0
	if c is TextEdit:
		return 1.0 if (c as TextEdit).editable else 0.0
	if c is Slider:
		return 1.0 if (c as Slider).editable else 0.0
	return null


static func named(want: String) -> Control:
	## the first Control a player can press (reachable) of some size whose name (a wildcard) matches, else the first
	## whose class does: where a touch on that widget lands
	if want == "":
		return null
	for by_class in [false, true]:
		for c in controls():
			if (Find.is_a(c, want) if by_class else String(c.name).matchn(want)) and reachable(c) and rect(c) != null:
				return c
	return null


static func to_window(at: Vector2) -> Vector2:
	## a place of the frame (its own units) as an input event names it
	return Find.probe.get_tree().root.get_final_transform() * at


static func centre(c: Control) -> Vector2:
	## its centre, as an input event names it
	return to_window(c.get_global_transform_with_canvas() * (c.size / 2.0))


static func fraction(fx: float, fy: float) -> Vector2:
	## a point of the frame in fractions, as an input event names it
	var frame := frame_size()
	return to_window(Vector2(clampf(fx, 0.0, 1.0) * frame.x, clampf(fy, 0.0, 1.0) * frame.y))
