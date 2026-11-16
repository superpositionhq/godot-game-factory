extends RefCounted
# JSON text of a row or a file: one line, keys in the order they were added. Vectors are arrays, a Quaternion its
# euler angles in degrees, and a number that is not finite is null (JSON has no NaN or Infinity).

const MAX_DEPTH := 16


static func text(value: Variant) -> String:
	return JSON.stringify(plain(value), "", false)


## A whole number as an int (60, not 60.0), anything else as it is.
static func number(value: float) -> Variant:
	if is_nan(value) or is_inf(value):
		return null
	if value == floorf(value) and absf(value) < 1e15:
		return int(value)
	return value


static func plain(value: Variant, depth: int = 0) -> Variant:
	if depth > MAX_DEPTH:
		return null
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return value
		TYPE_FLOAT:
			return null if is_nan(value) or is_inf(value) else value
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return String(value)
		TYPE_VECTOR2, TYPE_VECTOR2I:
			return [plain(value.x), plain(value.y)]
		TYPE_VECTOR3, TYPE_VECTOR3I:
			return [plain(value.x), plain(value.y), plain(value.z)]
		TYPE_VECTOR4, TYPE_VECTOR4I:
			return [plain(value.x), plain(value.y), plain(value.z), plain(value.w)]
		TYPE_QUATERNION:
			var e: Vector3 = value.get_euler()
			return [plain(rad_to_deg(e.x)), plain(rad_to_deg(e.y)), plain(rad_to_deg(e.z))]
		TYPE_COLOR:
			return [plain(value.r), plain(value.g), plain(value.b), plain(value.a)]
		TYPE_DICTIONARY:
			var out := {}
			for key: Variant in value:
				out[str(key)] = plain(value[key], depth + 1)
			return out
		TYPE_ARRAY, TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY, \
		TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY, \
		TYPE_PACKED_VECTOR2_ARRAY, TYPE_PACKED_VECTOR3_ARRAY, TYPE_PACKED_COLOR_ARRAY, TYPE_PACKED_VECTOR4_ARRAY:
			var list := []
			for item: Variant in value:
				list.append(plain(item, depth + 1))
			return list
	return str(value)
