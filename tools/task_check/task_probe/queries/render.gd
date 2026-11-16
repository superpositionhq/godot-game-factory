extends "../query.gd"
## render: what the renderer drew (contract section 3, "render"): the readings a budget is checked by. The engine's
## counts of a frame are read every frame, the highest since the previous sample kept, so a heavy frame between two
## samples is read too.
## "value": {"draw_calls", "triangles" (null before any frame), "texture_mb" (the texture memory in use at the
## sample, MiB)}

var _draw_calls := -1
var _primitives := -1


func frame(_dt: float) -> void:
	_draw_calls = maxi(_draw_calls, RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
	_primitives = maxi(_primitives, RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))


func sample(_t: float, sample: Dictionary) -> void:
	sample["value"] = {
		"draw_calls": _draw_calls if _draw_calls >= 0 else null, "triangles": _primitives if _primitives >= 0 else null,
		"texture_mb": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED) / 1048576.0,
	}
	_draw_calls = -1
	_primitives = -1
