extends Node3D
## The field scene: ground to trace (a floor, a hill, a roof above, an area that is no ground, a player standing at the
## origin), mesh pieces in each form a scene holds them (mesh instances, a multimesh, a grid map, a hidden one, a
## farther level of detail, an empty one), signs in the 3D world (one in view, one behind the camera, one hidden) and a
## looker that sums the mouse's motion. Built in code.

var total_x := 0.0
var total_y := 0.0
var events := 0


func _ready() -> void:
	var camera := Camera3D.new()
	camera.position = Vector3(0, 3, 10)
	camera.rotation_degrees = Vector3(-15, 0, 0)
	add_child(camera)
	# ground: a floor at y 0, a hill whose top is at y 2, a roof at y 5, an area at y 3
	_solid("Floor", Vector3(0, -0.5, 0), Vector3(20, 1, 20))
	_solid("Hill", Vector3(3, 1, 3), Vector3(3, 2, 3))
	_solid("Roof", Vector3(-3, 4.75, -3), Vector3(2, 0.5, 2))
	var area := Area3D.new()
	area.name = "Zone"
	area.position = Vector3(3, 3, -3)
	var zone := CollisionShape3D.new()
	zone.shape = BoxShape3D.new()
	area.add_child(zone)
	add_child(area)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.add_to_group("player")
	player.position = Vector3(0, 1, 0)
	var body := CollisionShape3D.new()
	body.shape = CapsuleShape3D.new()
	player.add_child(body)
	add_child(player)
	# pieces: two rocks and a hidden one, a multimesh of five trees with three drawn, a grid map of four tiles; a
	# farther level of detail and a mesh instance without a mesh are none
	var rock := BoxMesh.new()
	rock.resource_name = "rock"
	for i in 3:
		var one := MeshInstance3D.new()
		one.name = "Rock%d" % (i + 1)
		one.mesh = rock
		one.position = Vector3(-8 + i * 1.5, 0.5, 6)
		one.visible = i < 2
		add_child(one)
	var far := MeshInstance3D.new()
	far.name = "RockFar"
	far.mesh = rock
	far.visibility_range_begin = 30.0
	add_child(far)
	var empty := MeshInstance3D.new()
	empty.name = "Empty"
	add_child(empty)
	var tree := BoxMesh.new()
	tree.resource_name = "tree"
	var many := MultiMesh.new()
	many.transform_format = MultiMesh.TRANSFORM_3D
	many.mesh = tree
	many.instance_count = 5
	for i in 5:
		many.set_instance_transform(i, Transform3D(Basis(), Vector3(i * 2.0, 0.5, -6)))
	many.visible_instance_count = 3
	var trees := MultiMeshInstance3D.new()
	trees.name = "Trees"
	trees.multimesh = many
	add_child(trees)
	var tile := BoxMesh.new()
	tile.resource_name = "tile"
	var library := MeshLibrary.new()
	library.create_item(0)
	library.set_item_mesh(0, tile)
	var grid := GridMap.new()
	grid.name = "Tiles"
	grid.mesh_library = library
	grid.position = Vector3(-6, 0, -6)
	for i in 4:
		grid.set_cell_item(Vector3i(i, 0, 0), 0)
	add_child(grid)
	# signs in the 3D world
	for sign: Array in [["Sign", Vector3(0, 1.5, 0), true], ["Behind", Vector3(0, 1.5, 20), true], ["Hidden", Vector3(2, 1.5, 0), false]]:
		var label := Label3D.new()
		label.name = sign[0]
		label.text = "GATE 3" if sign[0] == "Sign" else String(sign[0]).to_upper()
		label.position = sign[1]
		label.visible = sign[2]
		add_child(label)


func _solid(part: String, at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = part
	body.position = at
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	(shape.shape as BoxShape3D).size = size
	body.add_child(shape)
	add_child(body)


func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		total_x += event.relative.x
		total_y += event.relative.y
		events += 1
