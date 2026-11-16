extends "../query.gd"
## screen: the mean brightness of the frame as displayed, over a rect (contract section 3): the frame drawn right
## after the sample, after post-processing and tone mapping, with the UI on it.
## "value": {"luminance" (mean linear Rec. 709 luminance of the displayed pixels, sRGB decoded, 0-1), "luma" (mean
## Rec. 709 luma of the encoded values, 0-1), "pixels" (how many were read), "size": [w, h]} | null when no frame was
## drawn (the play ended first, or it draws nothing).

const MAX_PIXELS := 65536  # a larger rect is read on an even lattice of its pixels

static var _linear := PackedFloat64Array()

var _rect: Array = [0.0, 0.0, 1.0, 1.0]  # [x0, y0, x1, y1] in fractions of the frame, y down


func load_query() -> void:
	var given := Find.numbers(def.get("rect"), 4)
	if given.size() == 4:
		_rect = [clampf(given[0], 0.0, 1.0), clampf(given[1], 0.0, 1.0), clampf(given[2], 0.0, 1.0), clampf(given[3], 0.0, 1.0)]
	if _linear.is_empty():
		_linear.resize(256)
		for i in 256:
			var c := i / 255.0
			_linear[i] = c / 12.92 if c <= 0.04045 else pow((c + 0.055) / 1.055, 2.4)


func needs_frame() -> bool:
	return true


func sample(_t: float, sample: Dictionary) -> void:
	sample["value"] = null  # filled in from the frame drawn next; null if none comes


func frame_drawn(image: Image, sample: Dictionary) -> void:
	if image == null or image.get_width() <= 0 or image.get_height() <= 0:
		return
	var width := image.get_width()
	var height := image.get_height()
	# the pixels the rect covers: whole pixels, rounded out, at least one each way
	var x0 := clampi(floori(minf(_rect[0], _rect[2]) * width), 0, width - 1)
	var y0 := clampi(floori(minf(_rect[1], _rect[3]) * height), 0, height - 1)
	var x1 := clampi(ceili(maxf(_rect[0], _rect[2]) * width), x0 + 1, width)
	var y1 := clampi(ceili(maxf(_rect[1], _rect[3]) * height), y0 + 1, height)
	var part := image.get_region(Rect2i(x0, y0, x1 - x0, y1 - y0))
	var every := ceili(sqrt(float(part.get_width() * part.get_height()) / MAX_PIXELS))
	if every > 1:
		part.resize(maxi(1, part.get_width() / every), maxi(1, part.get_height() / every), Image.INTERPOLATE_NEAREST)
	var data := part.get_data()  # RGB8: three bytes a pixel
	var red := 0.0
	var green := 0.0
	var blue := 0.0
	var red_lit := 0.0
	var green_lit := 0.0
	var blue_lit := 0.0
	var i := 0
	var end := data.size() - 2
	while i < end:
		var r := data[i]
		var g := data[i + 1]
		var b := data[i + 2]
		red += r
		green += g
		blue += b
		red_lit += _linear[r]
		green_lit += _linear[g]
		blue_lit += _linear[b]
		i += 3
	var count := float(part.get_width() * part.get_height())
	sample["value"] = {
		"luminance": (0.2126 * red_lit + 0.7152 * green_lit + 0.0722 * blue_lit) / count,
		"luma": (0.2126 * red + 0.7152 * green + 0.0722 * blue) / (255.0 * count),
		"pixels": count, "size": [width, height],
	}
