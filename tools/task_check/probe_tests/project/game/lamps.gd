extends Node3D
## The lamps scene: a lamp made each way a build may light one, dark until L turns them all on. Built in code, so
## each lamp's material is said in one place.

var _on := false


func _ready() -> void:
	var camera := Camera3D.new()
	camera.position = Vector3(0, 3, 12)
	add_child(camera)
	# a Light below it
	var by_light := _lamp("LightLamp", null)
	var bulb := OmniLight3D.new()
	bulb.name = "Bulb"
	bulb.light_energy = 2.0
	by_light.add_child(bulb)
	var red := _lamp("RedLamp", null)
	var glare := SpotLight3D.new()
	glare.name = "Bulb"
	glare.light_energy = 1.5
	glare.light_color = Color(1, 0, 0)
	red.add_child(glare)
	# a material that gives light: emission, and unshaded
	var emissive := StandardMaterial3D.new()
	emissive.emission = Color(1, 1, 1)
	emissive.emission_energy_multiplier = 3.0
	_lamp("EmissiveLamp", emissive).scale = Vector3(2, 2, 2)
	var plain := StandardMaterial3D.new()
	plain.albedo_color = Color(1, 1, 1)
	_lamp("UnshadedLamp", plain)
	# a texture on the emission: one that is white where the colour is black, one that is black where it is white
	var bright := StandardMaterial3D.new()
	bright.emission = Color(0, 0, 0)
	bright.emission_texture = _picture(Color.WHITE)
	_lamp("BrightTextureLamp", bright)
	var black := StandardMaterial3D.new()
	black.emission = Color(1, 1, 1)
	black.emission_operator = BaseMaterial3D.EMISSION_OP_MULTIPLY
	black.emission_texture = _picture(Color.BLACK)
	_lamp("BlackTextureLamp", black)
	# an effect that draws light, and one that draws smoke
	var spark := StandardMaterial3D.new()
	spark.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spark.albedo_color = Color(1, 0.8, 0.4)
	_effect("ParticleLamp", spark).emitting = false
	var soot := StandardMaterial3D.new()
	soot.albedo_color = Color(0.1, 0.1, 0.1)
	_effect("Smoke", soot)
	# what only a drawing tells: a shader of the game's own, lit by its parameter; one that stays dark; with a Light
	# beside it, the Light says
	var code := Shader.new()
	code.code = "shader_type spatial;\nuniform float power = 0.0;\nvoid fragment() { ALBEDO = vec3(0.5); EMISSION = vec3(power); }\n"
	var custom := ShaderMaterial.new()
	custom.shader = code
	_lamp("ShaderLamp", custom)
	var unlit := ShaderMaterial.new()
	unlit.shader = code
	_lamp("ShaderDark", unlit)
	var both := _lamp("ShaderAndLight", custom)
	var beside := OmniLight3D.new()
	beside.name = "Bulb"
	both.add_child(beside)
	_lamp("Plain", null)
	var hidden := _lamp("HiddenLamp", emissive.duplicate())
	(hidden.get_node("Shade") as MeshInstance3D).material_override.set("emission_enabled", true)
	hidden.visible = false
	var flat := Node2D.new()
	flat.name = "Lamp2D"
	flat.add_to_group("lamp")
	add_child(flat)
	var glow := PointLight2D.new()
	glow.name = "Bulb"
	glow.texture = GradientTexture2D.new()
	flat.add_child(glow)
	_switch(false)


static func _picture(colour: Color) -> ImageTexture:
	var image := Image.create(4, 4, false, Image.FORMAT_RGB8)
	image.fill(colour)
	return ImageTexture.create_from_image(image)


func _lamp(lamp: String, material: Material) -> Node3D:
	var node := Node3D.new()
	node.name = lamp
	node.add_to_group("lamp")
	node.position = Vector3(get_child_count() * 2.0 - 10.0, 0, 0)
	var shade := MeshInstance3D.new()
	shade.name = "Shade"
	shade.mesh = BoxMesh.new()
	shade.material_override = material
	node.add_child(shade)
	add_child(node)
	return node


func _effect(lamp: String, material: Material) -> CPUParticles3D:
	var node := Node3D.new()
	node.name = lamp
	node.add_to_group("lamp")
	node.position = Vector3(get_child_count() * 2.0 - 10.0, 0, 0)
	var sparks := CPUParticles3D.new()
	sparks.name = "Sparks"
	var quad := QuadMesh.new()
	quad.material = material
	sparks.mesh = quad
	node.add_child(sparks)
	add_child(node)
	return sparks


func _switch(on: bool) -> void:
	_on = on
	for lamp: String in ["LightLamp", "RedLamp", "ShaderAndLight", "Lamp2D"]:
		var bulb := get_node(lamp + "/Bulb")
		if bulb is Light2D:
			(bulb as Light2D).enabled = on
		else:
			(bulb as Light3D).visible = on
	($EmissiveLamp/Shade as MeshInstance3D).material_override.set("emission_enabled", on)
	($BrightTextureLamp/Shade as MeshInstance3D).material_override.set("emission_enabled", on)
	($BlackTextureLamp/Shade as MeshInstance3D).material_override.set("emission_enabled", on)
	(($ShaderLamp/Shade as MeshInstance3D).material_override as ShaderMaterial).set_shader_parameter("power", 2.0 if on else 0.0)
	($UnshadedLamp/Shade as MeshInstance3D).material_override.set(
		"shading_mode", BaseMaterial3D.SHADING_MODE_UNSHADED if on else BaseMaterial3D.SHADING_MODE_PER_PIXEL)
	($ParticleLamp/Sparks as CPUParticles3D).emitting = on


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_L:
		_switch(not _on)
