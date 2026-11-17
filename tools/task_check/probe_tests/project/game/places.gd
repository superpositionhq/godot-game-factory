extends Node3D
## The places scene, for what is drawn in a place: a red box that spins, a blue box that glows green, an empty place
## with a wall just outside it, a particle effect, a grey box that stays still, and a beam 4 m long; around them all a
## sky dome, a sun, a yellow ambient light and an exposure the probe's views must not take. Also: a black wall on a
## layer the camera leaves out, a still box under a flickering light, a beam 5 cm thick and 20 m long, 1100 small
## boxes in one place, a CPU particle effect of one particle.

var _torch: OmniLight3D


func _ready() -> void:
	var camera := Camera3D.new()
	camera.position = Vector3(0, 4, 16)
	camera.rotation_degrees = Vector3(-15, 0, 0)
	camera.cull_mask = camera.cull_mask & ~2  # it leaves out layer 2
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
	var exposure := CameraAttributesPractical.new()
	exposure.exposure_multiplier = 4.0
	exposure.auto_exposure_enabled = true
	world.camera_attributes = exposure
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
	# a black wall filling the view, on a layer the camera leaves out: never seen (the frame would go black), never drawn
	var black := StandardMaterial3D.new()
	black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	black.albedo_color = Color.BLACK
	var unseen := _box("Unseen", Vector3(0, 2, 12), Vector3(40, 40, 0.1), black)
	unseen.layers = 2
	# a still box under a light that flickers every frame
	_box("Lit", Vector3(9, 0, 0), Vector3.ONE, _colour(Color(0.5, 0.5, 0.5)))
	_torch = OmniLight3D.new()
	_torch.position = Vector3(9, 1.2, 0.8)
	_torch.omni_range = 3.0
	add_child(_torch)
	# a beam 5 cm thick from x 0 to 20 at z 20
	_box("Thin", Vector3(10, 0, 20), Vector3(20, 0.05, 0.05), _colour(Color(1, 1, 1)))
	# 1100 small boxes in one place
	var crowd := Node3D.new()
	crowd.name = "Crowd"
	crowd.position = Vector3(12, 0, 0)
	add_child(crowd)
	var small := BoxMesh.new()
	small.size = Vector3.ONE * 0.05
	for i in 1100:
		var one := MeshInstance3D.new()
		one.mesh = small
		one.position = Vector3((i % 10) * 0.1 - 0.45, (i / 10 % 10) * 0.1 - 0.45, (i / 100) * 0.08 - 0.4)
		crowd.add_child(one)
	# one CPU particle that stays where it starts
	var single := CPUParticles3D.new()
	single.name = "Single"
	single.position = Vector3(15, 0, 0)
	single.amount = 1
	single.lifetime = 10.0
	single.gravity = Vector3.ZERO
	single.initial_velocity_min = 0.0
	single.initial_velocity_max = 0.0
	single.spread = 0.0
	var dot := QuadMesh.new()
	dot.size = Vector2(0.3, 0.3)
	dot.material = spark
	single.mesh = dot
	add_child(single)


func _process(_delta: float) -> void:
	_torch.light_energy = randf_range(0.0, 4.0)


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
