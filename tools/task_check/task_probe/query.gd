extends RefCounted
## A query: one of the checker's measures, sampled with the track. One script per kind in queries/, named after the
## kind (queries/objects.gd), so adding a kind touches no other file.

const Find := preload("find.gd")
const MAX_ROWS := 200

var id := ""
var kind := ""
var def: Dictionary = {}  ## the query as the checker wrote it (contract section 5): its select, rect and so on
var fields: Array[String] = []  ## the fields the task's probes read of it (empty for a count)
var probe: Node


func load_query() -> void:
	## once, after def and fields are set: read the select; a bad definition is said with probe.error
	pass


func frame(_dt: float) -> void:
	## every frame of the play, its clock running or held (speed, spin, spawns, render)
	pass


func sample(_t: float, sample: Dictionary) -> void:
	## one sample at play time t: fill "rows" (write_rows) or "value"; a query the probe can't run (an unknown kind)
	## has null values
	sample["value"] = null


func needs_frame() -> bool:
	## whether the sample is completed from the frame drawn right after it (frame_drawn)
	return false


func frame_drawn(_image: Image, _sample: Dictionary) -> void:
	pass


func reads(field: String) -> bool:
	return fields.has(field)


func known_fields(plain: Array, prefixes: Array = []) -> void:
	## leaves out the fields this kind doesn't have, each said once as "<kind> <id>: no field F"
	var kept: Array[String] = []
	for f in fields:
		var known := plain.has(f)
		for p: String in prefixes:
			known = known or (f.length() > p.length() and f.begins_with(p))
		if known:
			kept.append(f)
		else:
			probe.error("%s %s: no field %s" % [kind, id, f])
	fields = kept


func write_rows(rows: Array, sample: Dictionary) -> void:
	## the rows of one selection sample: at most 200 kept, every match counted, and each field's numbers summed up over
	## every match ("total" and "full", written when more matched than the rows hold: every field asked for, in the
	## order asked)
	if rows.size() <= MAX_ROWS:
		sample["rows"] = rows
		return
	sample["rows"] = rows.slice(0, MAX_ROWS)
	sample["total"] = rows.size()
	var full := {}
	for f in fields:
		var n := 0
		var nonzero := 0
		var sum := 0.0
		var low := 0.0
		var high := 0.0
		for row: Dictionary in rows:
			var v: Variant = row.get(f)
			if not (v is float or v is int) or is_nan(v) or is_inf(v):
				continue
			low = minf(low, v) if n > 0 else float(v)
			high = maxf(high, v) if n > 0 else float(v)
			sum += v
			if v != 0:
				nonzero += 1
			n += 1
		full[f] = {"n": n, "nonzero": nonzero, "sum": sum, "min": low if n > 0 else null, "max": high if n > 0 else null}
	sample["full"] = full
