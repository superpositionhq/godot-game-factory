extends Node3D
## The places scene, for what is drawn in a place: a red box that spins, a blue box that glows green, an empty place
## with a wall just outside it, a particle effect, a grey box that stays still, and a beam 4 m long; around them all a
## sky dome, a sun and a yellow ambient light the probe's views must not take. Built in code.


func _ready() -> void:
	var camera := Camera3D.new()
	camera.position = Vector3(0, 4, 16)
	camera.rotation_degrees = Vector3(-15, 0, 0)
	add_child(camera)
	var sun := DirectionalLight3D.new()
	sun.light_energy = 0.5
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.shadow_enabled = true
	add_child(sun)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color(1, 1, 0)
	add_child(world)
	# a red box that spins; a blue box that glows green (its glow is no base colour)
	var spinner := _box("Spinner", Vector3(-6, 0, 0), Vector3.ONE, _colour(Color(0.6, 0.05, 0.05)))
	spinner.set_script(load("res://game/spinner.gd"))
	spinner.set_process(true)  # a script given after the node is ready isn't processed until told
	var glowing := _colour(Color(0.05, 0.05, 0.6))
	glowing.emission_enabled = true
	glowing.emission = Color(0, 1, 0)
	glowing.emission_energy_multiplier = 2.0
	_box("Glowing", Vector3(-3, 0, 0), Vector3.ONE, glowing)
	# nothing in the place at the origin; a wall just outside its box, behind it
	_box("Wall", Vector3(0, 0, -1.6), Vector3(3, 3, 0.2), _colour(Color(0.9, 0.9, 0.9)))
	# a particle effect at (3, 0, 0)
	var sparks := GPUParticles3D.new()
	sparks.name = "Sparks"
	sparks.position = Vector3(3, 0, 0)
	sparks.amount = 64
	sparks.lifetime = 0.6
	sparks.visibility_aabb = AABB(Vector3(-1, -1, -1), Vector3(2, 2, 2))
	var process := ParticleProcessMaterial.new()
	process.direction = Vector3(0, 1, 0)
	process.spread = 60.0
	process.initial_velocity_min = 0.5
	process.initial_velocity_max = 1.0
	process.gravity = Vector3.ZERO
	sparks.process_material = process
	var quad := QuadMesh.new()
	quad.size = Vector2(0.15, 0.15)
	var spark := StandardMaterial3D.new()
	spark.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	spark.albedo_color = Color(1, 0.8, 0.3)
	spark.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	quad.material = spark
	sparks.draw_pass_1 = quad
	add_child(sparks)
	# a grey box that stays still
	_box("Still", Vector3(6, 0, 0), Vector3.ONE, _colour(Color(0.5, 0.5, 0.5)))
	# a beam from x 0 to 4 at z 10
	_box("Beam", Vector3(2, 0, 10), Vector3(4, 0.1, 0.1), _colour(Color(1, 1, 1)))
	# a sky dome around everything
	var dome := MeshInstance3D.new()
	dome.name = "Dome"
	var sphere := SphereMesh.new()
	sphere.radius = 400.0
	sphere.height = 800.0
	sphere.flip_faces = true
	dome.mesh = sphere
	dome.material_override = _colour(Color(0.2, 0.3, 0.6))
	add_child(dome)


static func _colour(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 1.0
	return m


func _box(part: String, at: Vector3, size: Vector3, material: Material) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var box := MeshInstance3D.new()
	box.name = part
	box.mesh = mesh
	box.position = at
	box.material_override = material
	add_child(box)
	return box
