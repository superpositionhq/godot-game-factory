extends RefCounted
## The UI as widgets, ui, a widget click and a touch on a widget read it: the Control nodes of the game's window.
## A rectangle is in fractions of the frame, y down from the top, whatever anchor, container or canvas layer placed it.
## Two questions a player's press raises are answered here too: how the scroll areas a control sits in move to bring it
## into view (scroll_steps, scroll_into_view), as a player scrolls a list to an item, and whether a press at a point
## reaches a control or something over it takes the press (press_reaches, picked_at: the engine's GUI picking, redone).

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
	## the Controls a widget click and a touch on a widget choose among: shown (itself and everything above it, its
	## canvas layer too), the modulate of it and every canvas item above it above the floor, inside the frame (one of
	## no size counts). Its own self_modulate doesn't count: an invisible hit area over art is pressed like any button.
	## Clipping plays no part in the choice: the input takes the Control it would take anyway, and whether a player's
	## press can get to that one is asked of it afterwards (clipped_out).
	if not shown_anywhere(c):
		return false
	var r := box(c)
	if r.size.x <= 0.0 or r.size.y <= 0.0:
		return true
	return in_frame(c)


static func shown_anywhere(c: Control) -> bool:
	## shown (itself and everything above it, its canvas layer too), and the modulate of it and every canvas item above
	## it above the floor, wherever it lies: inside the frame or not, in its scroll area's view or not
	if not c.is_visible_in_tree():
		return false
	var above := 1.0
	var at: Node = c
	while at is CanvasItem:
		above *= (at as CanvasItem).modulate.a
		at = at.get_parent()
	return above > Find.ALPHA_FLOOR


static func clipped_out(c: Control) -> bool:
	## whether a press on it can't get to it: its centre, where a click or a touch goes, lies outside a Control above it
	## (at any depth) that clips what it holds (clip_contents, as a ScrollContainer has it), tested in that Control's
	## own rectangle as the engine tests a press, which it gives to nothing inside a clipping Control when it falls
	## outside it. A control scrolled out of its container's view is so, and so is one partly in view whose centre is
	## out of it. A click or a tap first scrolls the scroll areas that alone hide it (scroll_into_view) and asks again.
	var point := press_point(c)
	var at := c.get_parent()
	while at is Control:
		var holder := at as Control
		if holder.clip_contents:
			var local := holder.get_global_transform_with_canvas().affine_inverse() * point
			if not Rect2(Vector2.ZERO, holder.size).has_point(local):
				return true
		at = at.get_parent()
	return false


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
	## whose class does, else the first button whose shown text reads `want` (by_caption): where a touch on that widget
	## lands; null when none matches, and when the one that matches is scrolled out of its container's view
	## (clipped_out: the touch is a miss, never taken by the next match)
	var found: Array = spot_widget(want)
	return found[0] if not found.is_empty() and not clipped_out(found[0] as Control) else null


static func spot_widget(want: String) -> Array:
	## [the Control a touch on `want` lands on, how it was found ("name", "class" or 'caption "<text>"'), and the note
	## of a caption several buttons read], or [] (named)
	if want == "":
		return []
	for by_class in [false, true]:
		for c in controls():
			if (Find.is_a(c, want) if by_class else String(c.name).matchn(want)) and reachable(c) and rect(c) != null:
				return [c, "class" if by_class else "name", ""]
	return by_caption(want, false)


static func label_key(text: String) -> String:
	## a name or a caption as a click compares them when it isn't written exactly as shown, as the other engines'
	## probes do: lower case, each run of anything but letters and digits one "_", none at either end ("New
	## expedition", "new_expedition", "NEW  EXPEDITION!"); a letter of a script without case (Chinese, Japanese,
	## Korean, Thai) is a letter, so "开始 游戏" reads "开始_游戏"
	var out := ""
	var gap := false
	for ch in text.to_lower():
		if is_word(ch):
			if gap and out != "":
				out += "_"
			out += ch
			gap = false
		else:
			gap = true
	return out


static func is_word(ch: String) -> bool:
	## a letter or a digit of any script, as label_key keeps it: a digit, a letter with case, or any character past
	## ASCII that isn't a space, a punctuation mark or a symbol (an ideograph, a kana, a hangul syllable: letters without
	## case, which the case test alone would drop)
	if ch == "":
		return false
	if ch.is_valid_int() or ch.to_upper() != ch.to_lower():
		return true
	var code := ch.unicode_at(0)
	return code >= 0x80 and not is_mark(code)


static func is_mark(code: int) -> bool:
	## a character past ASCII that is no letter: Latin-1's signs and punctuation (0x80-0xBF, the times and divide
	## signs), general and supplemental punctuation and spaces, arrows, mathematical and technical signs, boxes,
	## shapes and dingbats, CJK punctuation and the ideographic space, the katakana middle dot, the vertical, small and
	## compatibility forms, the full-width forms' punctuation, the byte order mark, and pictographs and emoji
	return (code <= 0xBF) or code == 0xD7 or code == 0xF7 \
		or (code >= 0x2000 and code <= 0x2BFF) or (code >= 0x2E00 and code <= 0x2E7F) \
		or (code >= 0x3000 and code <= 0x303F) or code == 0x30FB \
		or (code >= 0xFE10 and code <= 0xFE1F) or (code >= 0xFE30 and code <= 0xFE6F) \
		or (code >= 0xFF01 and code <= 0xFF0F) or (code >= 0xFF1A and code <= 0xFF20) \
		or (code >= 0xFF3B and code <= 0xFF40) or (code >= 0xFF5B and code <= 0xFF65) or code == 0xFEFF \
		or (code >= 0x1F000 and code <= 0x1FAFF)


static func captions(c: Control, wherever: bool = false) -> Array[String]:
	## the text a player reads on a button, shown: its own (a Button's, a LinkButton's), each Label or RichTextLabel
	## drawn below it, alone, and all of those together in order. Text that isn't shown (the button drawn see-through,
	## a hidden label) and a TextureButton's tooltip are no caption. `wherever`: the text it shows wherever it lies,
	## outside the frame or out of its scroll area's view too: what it reads once it is scrolled into view
	## (scrolled_away)
	var found: Array[String] = []
	var shows := (shown_anywhere(c) and alpha(c) > Find.ALPHA_FLOOR) if wherever else visible(c)
	var own: Variant = own_text(c) if shows and (c is Button or c is LinkButton) else null
	if own != null and own != "":
		found.append(own)
	var below: Array[String] = []
	for n: Node in c.find_children("*", "Control", true, false):
		if not (n is Label or n is RichTextLabel):
			continue
		var label := n as Control
		var reads := drawn(label)
		if wherever:
			reads = shown_anywhere(label) and alpha(label) > Find.ALPHA_FLOOR and rect(label) != null
		if reads:
			var shown: Variant = own_text(n as Control)
			if shown != null and shown != "":
				below.append(shown)
	found.append_array(below)
	if below.size() > 1:
		found.append(" ".join(below))
	return found


static func by_caption(want: String, click: bool, disabled: bool = false) -> Array:
	## [the first button in reading order (top to bottom, then left to right) a player can press whose caption reads
	## `want`, 'caption "<text>"', a note when more than one reads it], or []. A caption written exactly as `want` (any
	## script, spaces and punctuation included) wins; only when no button shows it so, one that reads it label_key alike.
	## `click`: only one that takes a click (enabled, not ignoring the mouse), as a widget click asks. `disabled`: only
	## one shown but disabled (a click's miss says so: disabled_button).
	if want == "":
		return []
	var key := label_key(want)
	var exact: Array = []
	var loose: Array = []
	for c in controls():
		if not (c is BaseButton) or not reachable(c) or rect(c) == null:
			continue
		if click and (usable(c) == 0.0 or c.mouse_filter == Control.MOUSE_FILTER_IGNORE):
			continue
		if disabled and usable(c) != 0.0:
			continue
		var as_written := ""
		var alike := ""
		for caption in captions(c):
			if caption == want:
				as_written = caption
				break
			if alike == "" and key != "" and label_key(caption) == key:
				alike = caption
		if as_written != "":
			exact.append([c, as_written])
		elif alike != "":
			loose.append([c, alike])
	var matched: Array = exact if not exact.is_empty() else loose
	if matched.is_empty():
		return []
	matched.sort_custom(func(a: Array, b: Array) -> bool:
		var ra := box(a[0] as Control)
		var rb := box(b[0] as Control)
		return ra.position.y < rb.position.y or (ra.position.y == rb.position.y and ra.position.x < rb.position.x))
	var note := ""
	if matched.size() > 1:
		note = "%d buttons read '%s'; took the first in reading order" % [matched.size(), want]
	return [matched[0][0], 'caption "%s"' % matched[0][1], note]


static func disabled_button(want: String) -> Array:
	## [the first button a widget click on `want` would take but that it is disabled, and how it was found ("name",
	## "class" or 'caption "<text>"')], or []: shown where a player could press it (reachable, of some size), by its
	## name (a wildcard), else its class, else its caption (by_caption). A click on it does nothing, as a player's.
	if want == "":
		return []
	for by_class in [false, true]:
		for c in controls():
			if c is BaseButton and (c as BaseButton).disabled and reachable(c) and rect(c) != null \
					and (Find.is_a(c, want) if by_class else String(c.name).matchn(want)):
				return [c, "class" if by_class else "name"]
	var read: Array = by_caption(want, false, true)
	return [read[0], read[1]] if not read.is_empty() else []


static func to_window(at: Vector2) -> Vector2:
	## a place of the frame (its own units) as an input event names it
	return Find.probe.get_tree().root.get_final_transform() * at


static func centre(c: Control) -> Vector2:
	## its centre, as an input event names it
	return to_window(press_point(c))


static func fraction(fx: float, fy: float) -> Vector2:
	## a point of the frame in fractions, as an input event names it
	var frame := frame_size()
	return to_window(Vector2(clampf(fx, 0.0, 1.0) * frame.x, clampf(fy, 0.0, 1.0) * frame.y))


# ---------------------------------------------------------------- scrolling a control into view


static func press_point(c: Control) -> Vector2:
	## where a click or a touch on it goes, in the frame's own units: its centre
	return c.get_global_transform_with_canvas() * (c.size / 2.0)


static func scroll_steps(c: Control) -> Array:
	## how the scroll areas above `c` move to bring the point a press on it goes to (press_point) into their view, as a
	## player scrolls a list to an item: [[ScrollContainer, scroll_horizontal, scroll_vertical], ...], the innermost
	## first. Every Control above `c` that clips what it holds (clip_contents) and leaves that point out must be a
	## ScrollContainer. Each one moves the least way that shows `c` whole in its view (its rectangle less the scroll bars
	## it shows), or, for a `c` larger than that view, the way that puts `c`'s centre at the view's; only along the ways
	## it scrolls (not SCROLL_MODE_DISABLED) and no further than its scroll bars go. One further out is read with what
	## those inside it moved, so nested lists all move at once. [] when no move is needed, and when no move shows the
	## point: a Control that only clips leaves it out, an area can't move that way or that far, or the point would end
	## outside the frame. Nothing is moved here (scroll_into_view).
	var r := box(c)
	var point := press_point(c)
	var shift := Vector2.ZERO  # how far `c` has moved in the frame through the moves of the areas inside this one
	var steps: Array = []
	var at := c.get_parent()
	while at is Control:
		var holder := at as Control
		at = at.get_parent()
		if not holder.clip_contents:
			continue
		var to_local := holder.get_global_transform_with_canvas().affine_inverse()
		var own := Rect2(Vector2.ZERO, holder.size)
		if own.has_point(to_local * (point + shift)):
			continue
		var area := holder as ScrollContainer
		if area == null:
			return []  # it only clips: nothing a player does scrolls it
		var seen := to_local * Rect2(r.position + shift, r.size)
		var view := _scroll_view(area)
		var h := _scroll_value(area.get_h_scroll_bar(), area.scroll_horizontal,
			_scroll_by(seen.position.x, seen.end.x, view.position.x, view.end.x),
			area.horizontal_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED)
		var v := _scroll_value(area.get_v_scroll_bar(), area.scroll_vertical,
			_scroll_by(seen.position.y, seen.end.y, view.position.y, view.end.y),
			area.vertical_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED)
		var by := Vector2(h - area.scroll_horizontal, v - area.scroll_vertical)
		if by == Vector2.ZERO:
			return []
		# what the area holds moves back by what it scrolls, in the area's own units
		shift -= holder.get_global_transform_with_canvas().basis_xform(by)
		if not own.has_point(to_local * (point + shift)):
			return []
		steps.append([area, h, v])
	if steps.is_empty() or not Rect2(Vector2.ZERO, frame_size()).has_point(point + shift):
		return []
	return steps


static func _scroll_view(area: ScrollContainer) -> Rect2:
	## the part of a ScrollContainer's own rectangle what it holds shows in: less the scroll bars it shows
	var view := Rect2(Vector2.ZERO, area.size)
	var side := area.get_v_scroll_bar()
	if side.visible:
		view.size.x -= side.size.x
		if area.is_layout_rtl():
			view.position.x += side.size.x
	var under := area.get_h_scroll_bar()
	if under.visible:
		view.size.y -= under.size.y
	return view


static func _scroll_by(lo: float, hi: float, view_lo: float, view_hi: float) -> float:
	## how far the content scrolls along one way so that [lo, hi] shows in [view_lo, view_hi]: 0 when it shows whole;
	## else the least move that shows it whole, or one that centres it when it is larger than the view
	if hi - lo > view_hi - view_lo:
		return (lo + hi) / 2.0 - (view_lo + view_hi) / 2.0
	if lo < view_lo:
		return lo - view_lo
	if hi > view_hi:
		return hi - view_hi
	return 0.0


static func _scroll_value(bar: ScrollBar, now: int, by: float, scrolls: bool) -> int:
	## a scroll value moved `by`, kept where its scroll bar can go (its least, to its content less its page); `now`
	## when the area doesn't scroll that way
	if not scrolls or is_zero_approx(by):
		return now
	var most := maxf(bar.min_value, bar.max_value - bar.page)
	return roundi(clampf(now + by, bar.min_value, most))


static func scroll_into_view(c: Control) -> String:
	## the scroll areas above `c` set as scroll_steps says, each as its own scroll bar would set it; the layout follows
	## when the frame ends, so a press on `c` is made in the next frame. What moved, for probe.log ("Inner
	## (ScrollContainer), Outer (ScrollContainer)"), or "" when nothing can show it (nothing moved)
	var moved := PackedStringArray()
	for step: Array in scroll_steps(c):
		var area: ScrollContainer = step[0]
		area.scroll_horizontal = step[1]
		area.scroll_vertical = step[2]
		moved.append("%s (%s)" % [area.name, Find.class_of(area)])
	return ", ".join(moved)


static func scrolled_away(want: String, click: bool) -> Array:
	## [the first Control a click (`click`) or a tap on `want` would take but for the scroll areas it lies in, how it was
	## found ("name", "class" or 'caption "<text>"')], or []: shown wherever it lies (outside the frame too) and of some
	## size, by its name (a wildcard), else its class, else a button whose caption, read wherever it lies, is `want` as
	## written, else reads it label_key alike; for a click, one that takes a click (enabled, not ignoring the mouse) or
	## a button shown but disabled (its click, once scrolled to, says so); only one scroll_steps can show. Asked only
	## when nothing on screen matches.
	if want == "":
		return []
	for by_class in [false, true]:
		for c in controls():
			if (Find.is_a(c, want) if by_class else String(c.name).matchn(want)) and _can_scroll_to(c, click):
				return [c, "class" if by_class else "name"]
	var key := label_key(want)
	var alike: Array = []
	for c in controls():
		if not (c is BaseButton) or not shown_anywhere(c) or rect(c) == null:
			continue
		var loose := ""
		for caption in captions(c, true):
			if caption == want and _can_scroll_to(c, click):
				return [c, 'caption "%s"' % caption]
			if loose == "" and key != "" and label_key(caption) == key:
				loose = caption
		if loose != "":
			alike.append([c, loose])
	for found: Array in alike:
		if _can_scroll_to(found[0] as Control, click):
			return [found[0], 'caption "%s"' % found[1]]
	return []


static func _can_scroll_to(c: Control, click: bool) -> bool:
	if not shown_anywhere(c) or rect(c) == null:
		return false
	if click:
		var takes := usable(c) != 0.0 and c.mouse_filter != Control.MOUSE_FILTER_IGNORE
		if not takes and not (c is BaseButton and (c as BaseButton).disabled):
			return false
	return not scroll_steps(c).is_empty()


# ---------------------------------------------------------------- what a press reaches


static func press_reaches(c: Control, at: Vector2) -> Array:
	## whether a press at `at` (the frame's own units) comes to `c`, as the engine's GUI hands a mouse button or a touch
	## to a Control: [0, ""] when it does (the Control the GUI picks there is `c`, or one below `c` whose press climbs
	## to it: none on the way stops it with MOUSE_FILTER_STOP); [1, what] when something else takes it ("parent/name
	## (class)"): another Control picked there (one drawn over it, a higher canvas layer's, a sibling of any mouse
	## filter but IGNORE, a scroll bar), a shown embedded window (a dialog, a popup) that holds the point, or a shown
	## exclusive one wherever it is (it takes all input from the window below); [-1, ""] when that can't be told: `c`
	## takes no press itself (its mouse filter IGNORE, or turned off by a mouse_behavior_recursive above it), or nothing
	## is picked there. What it can't see: a Control on the way up that accepts the press itself, a game's _input that
	## marks the press handled first, a native _has_point (a TextureButton's click mask: its rectangle is read), a
	## press outside an open popup that only closes it, title bars, windows that aren't embedded, and what is inside a
	## SubViewportContainer.
	if _mouse_filter(c) == Control.MOUSE_FILTER_IGNORE:
		return [-1, ""]
	var root: Window = Find.probe.get_tree().root
	var window := _window_at(root, at, c)
	if window != null:
		return [1, _what(window)]
	var hit := picked_at(root, at)
	if hit == null:
		return [-1, ""]
	if _press_climbs(hit, c):
		return [0, ""]
	return [1, _what(hit)]


static func covered(c: Control) -> Variant:
	## the widgets field `covered`: 1 when a press at its centre goes to something else first (press_reaches), 0 when
	## it comes to it; null when that can't be told: it isn't on screen (visible), has no size, its centre lies outside a
	## Control above it that clips (clipped_out) or outside the frame, it takes no press, or nothing is picked there
	if not visible(c) or rect(c) == null or clipped_out(c):
		return null
	var at := press_point(c)
	if not Rect2(Vector2.ZERO, frame_size()).has_point(at):
		return null
	var read: Array = press_reaches(c, at)
	return null if read[0] < 0 else float(read[0])


static func picked_at(root: Window, at: Vector2) -> Control:
	## the Control the window's GUI gives a press at `at`, picked as the engine picks it: its root Controls (no Control
	## above them through canvas items, or set top level) by canvas layer, then tree order, the last first, each one
	## shown; in each, its children the last first (internal ones too: a ScrollContainer's scroll bars), a Control that
	## clips only when the point is in it, a top-level child left for its own turn; the first Control whose mouse filter
	## isn't IGNORE and that holds the point (its script's _has_point when it has one, else its rectangle). z_index plays
	## no part, as in the engine's picking. Null when none does.
	var roots: Array = []
	var order := 0
	for n: Node in root.find_children("*", "Control", true, false):
		var c := n as Control
		if Find.is_own(c) or c.get_viewport() != root or not _gui_root(c):
			continue
		var layer := c.get_canvas_layer_node()
		roots.append([layer.layer if layer != null else 0, order, c])
		order += 1
	roots.sort_custom(func(a: Array, b: Array) -> bool: return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	for i in range(roots.size() - 1, -1, -1):
		var top: Control = roots[i][2]
		if not top.is_visible_in_tree():
			continue
		var found := _pick_below(top, at)
		if found != null:
			return found
	return null


static func _gui_root(c: Control) -> bool:
	## whether the GUI picks from `c` as one of its roots: set top level, or no Control above it through canvas items (a
	## Node2D between counts as the way up; a node that is no canvas item ends it)
	var at: Node = c
	while not (at as CanvasItem).is_set_as_top_level():
		var parent := at.get_parent()
		if not (parent is CanvasItem):
			return true
		if parent is Control:
			return false
		at = parent
	return true


static func _pick_below(item: CanvasItem, at: Vector2) -> Control:
	if not item.visible:
		return null
	var xform := item.get_global_transform_with_canvas()
	if is_zero_approx(xform.determinant()):
		return null
	var local := xform.affine_inverse() * at
	var c := item as Control
	if c == null or not c.clip_contents or _holds_point(c, local):
		for i in range(item.get_child_count(true) - 1, -1, -1):
			var child := item.get_child(i, true) as CanvasItem
			if child == null or child.is_set_as_top_level():
				continue
			var found := _pick_below(child, at)
			if found != null:
				return found
	if c == null or _mouse_filter(c) == Control.MOUSE_FILTER_IGNORE:
		return null
	return c if _holds_point(c, local) else null


static func _holds_point(c: Control, local: Vector2) -> bool:
	## whether a point in its own rectangle's units is in it: its script's _has_point when it has one, else its rectangle
	if c.get_script() != null and c.has_method("_has_point"):
		return bool(c.call("_has_point", local))
	return Rect2(Vector2.ZERO, c.size).has_point(local)


static func _mouse_filter(c: Control) -> int:
	## the mouse filter the GUI picks by: its own, but IGNORE when a mouse_behavior_recursive set on it, or on the
	## nearest Control above it that sets one, turns the mouse off (read by name: an engine without it reads nothing)
	var at: Node = c
	while at is Control:
		var behaviour: Variant = at.get("mouse_behavior_recursive")
		if behaviour is int and behaviour != 0:  # 0: inherited
			if behaviour == 1:  # disabled
				return Control.MOUSE_FILTER_IGNORE
			break
		at = at.get_parent()
	return c.mouse_filter


static func _press_climbs(hit: Control, c: Control) -> bool:
	## whether a press the GUI gives `hit` comes to `c` as it climbs: `hit` is `c`, or below it, and none on the way up
	## stops it (MOUSE_FILTER_STOP) or is set top level
	var at: Node = hit
	while at is CanvasItem:
		if at == c:
			return true
		if at is Control and _mouse_filter(at as Control) == Control.MOUSE_FILTER_STOP:
			return false
		if (at as CanvasItem).is_set_as_top_level():
			return false
		at = at.get_parent()
	return false


static func _window_at(root: Window, at: Vector2, c: Control) -> Window:
	## an embedded window that takes a press at `at` before the window's own Controls: of the shown ones that don't let
	## the mouse through (and don't hold `c`), the last that holds the point or is exclusive
	var found: Window = null
	for n: Node in root.find_children("*", "Window", true, false):
		var w := n as Window
		if Find.is_own(w) or not w.visible or not w.is_embedded() or w.mouse_passthrough or w.is_ancestor_of(c):
			continue
		if w.exclusive or Rect2(Vector2(w.position), Vector2(w.size)).has_point(at):
			found = w
	return found


static func _what(n: Node) -> String:
	## what a press reached, for probe.log: "parent/name (class)", or "name (class)" with no parent
	var parent := n.get_parent()
	return "%s%s (%s)" % ["%s/" % parent.name if parent != null else "", n.name, Find.class_of(n)]
