extends Node3D
## The lamps scene: a lamp made each way a build may light one, dark until L turns them all on. Built in code, so
## each lamp's material is said in one place.

var _on := false
var _pulse: ShaderMaterial
var _age := 0.0


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
	# a shell drawn over the mesh (a next pass) that gives the light; a lamp switched by fading its unshaded
	# material in and out; a light under a hidden holder; and what is there but never drawn
	var shell := StandardMaterial3D.new()
	shell.emission = Color(1, 1, 1)
	var under := StandardMaterial3D.new()
	under.next_pass = shell
	_lamp("ShellLamp", under)
	var fading := StandardMaterial3D.new()
	fading.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	fading.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	fading.albedo_color = Color(1, 1, 1, 0)
	_lamp("FadedLamp", fading)
	var held := _lamp("HeldLamp", null)
	var holder := Node3D.new()
	holder.name = "Holder"
	holder.visible = false
	held.add_child(holder)
	var kept := OmniLight3D.new()
	kept.name = "Bulb"
	holder.add_child(kept)
	var glowing := StandardMaterial3D.new()
	glowing.emission_enabled = true
	glowing.emission = Color(1, 1, 1)
	var quiet := _lamp("QuietLamp", null)
	var tool_light := OmniLight3D.new()
	tool_light.name = "ToolLight"
	tool_light.editor_only = true
	quiet.add_child(tool_light)
	var layerless := MeshInstance3D.new()
	layerless.name = "NoLayer"
	layerless.mesh = BoxMesh.new()
	layerless.material_override = glowing
	layerless.layers = 0
	quiet.add_child(layerless)
	var shadow := MeshInstance3D.new()
	shadow.name = "ShadowOnly"
	shadow.mesh = BoxMesh.new()
	shadow.material_override = glowing
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	quiet.add_child(shadow)
	# drawn alone: a shader whose light pulses every frame; a 4 m post with a 10 cm band that glows, and one whose
	# band stays dark; a mesh of two glowing surfaces under an override that is dark
	_pulse = ShaderMaterial.new()
	_pulse.shader = code
	_lamp("PulseLamp", _pulse)
	var banded := Shader.new()
	banded.code = "shader_type spatial;\nuniform float power = 0.0;\nvarying float height;\nvoid vertex() { height = VERTEX.y; }\nvoid fragment() { ALBEDO = vec3(0.5); EMISSION = vec3(power * step(abs(height - 1.0), 0.05)); }\n"
	for post: String in ["PostLamp", "PostDark"]:
		var band := ShaderMaterial.new()
		band.shader = banded
		var tall := BoxMesh.new()
		tall.size = Vector3(0.2, 4.0, 0.2)
		(_lamp(post, band).get_node("Shade") as MeshInstance3D).mesh = tall
	var two := ArrayMesh.new()
	for i in 2:
		two.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, BoxMesh.new().get_mesh_arrays())
		two.surface_set_material(i, glowing)
	var covered := ShaderMaterial.new()
	covered.shader = code
	(_lamp("OverrideDark", covered).get_node("Shade") as MeshInstance3D).mesh = two
	# drawn alone, a shader that gives pure blue light: the least luminous colour, well above the floor
	var blue := Shader.new()
	blue.code = "shader_type spatial;\nuniform float power = 0.0;\nvoid fragment() { ALBEDO = vec3(0.0); EMISSION = vec3(0.0, 0.0, power); }\n"
	var deep := ShaderMaterial.new()
	deep.shader = blue
	_lamp("BlueLamp", deep)
	# a player, for a play that goes to a lamp by its light
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.add_to_group("player")
	player.position = Vector3(0, 0, 30)
	add_child(player)
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
	(($ShellLamp/Shade as MeshInstance3D).material_override.next_pass as StandardMaterial3D).emission_enabled = on
	(($FadedLamp/Shade as MeshInstance3D).material_override as StandardMaterial3D).albedo_color = Color(1, 1, 1, 1.0 if on else 0.0)
	(($PostLamp/Shade as MeshInstance3D).material_override as ShaderMaterial).set_shader_parameter("power", 2.0 if on else 0.0)
	(($BlueLamp/Shade as MeshInstance3D).material_override as ShaderMaterial).set_shader_parameter("power", 1.0 if on else 0.0)
	if not on:
		_pulse.set_shader_parameter("power", 0.0)


func _process(delta: float) -> void:
	# the pulsing lamp's light changes every frame while it is on, never down to dark
	_age += delta
	if _on:
		_pulse.set_shader_parameter("power", 1.5 + sin(_age * 20.0))


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_L:
		_switch(not _on)
