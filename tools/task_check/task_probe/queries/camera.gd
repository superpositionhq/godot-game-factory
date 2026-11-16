extends "../query.gd"
## camera: the player's camera against the player (contract section 3, "camera"). The checker reads occluded and
## player_on_screen from here; distance, height, pitch, yaw and fov it computes from the probe's camera and track rows,
## and they are here too.
## "value": {"pitch", "yaw", "fov", "distance", "height", "occluded", "player_on_screen"} (the player's fields null
## without a player) | null without a camera.

const PLAIN := ["distance", "height", "pitch", "yaw", "fov", "occluded", "player_on_screen"]


func load_query() -> void:
	known_fields(PLAIN)


func sample(_t: float, sample: Dictionary) -> void:
	var view: Node = probe.view()
	var eye: Variant = Find.camera_place(view) if view != null else null
	if eye == null:
		sample["value"] = null
		return
	var turned: Array = Find.angles(view) if view is Camera3D else [0.0, 0.0, 0.0]
	var fov := 0.0
	if view is Camera3D and (view as Camera3D).projection == Camera3D.PROJECTION_PERSPECTIVE:
		fov = (view as Camera3D).fov
	var value := {"pitch": turned[0], "yaw": turned[1], "fov": fov, "distance": null, "height": null, "occluded": null,
			"player_on_screen": null}
	sample["value"] = value
	var player: Node = probe.player()
	var at: Variant = Find.place(player) if player != null else null
	if at == null:
		return
	var centre: Vector3 = Find.centre(player)
	value["distance"] = (eye as Vector3).distance_to(at)
	value["height"] = eye.y - at.y
	if view is Camera3D:
		var cam := view as Camera3D
		value["occluded"] = 1.0 if _occluded(cam, player, centre) else 0.0
		var on := not cam.is_position_behind(centre)
		if on:
			var spot := cam.unproject_position(centre)
			on = Rect2(Vector2.ZERO, cam.get_viewport().get_visible_rect().size).has_point(spot)
		value["player_on_screen"] = 1.0 if on else 0.0
	else:
		# a 2D camera sees a rectangle of the plane: nothing stands between it and the player
		var canvas: Camera2D = view
		var seen := canvas.get_viewport().get_visible_rect().size / canvas.zoom
		var corner := canvas.get_screen_center_position() - seen / 2.0
		value["occluded"] = 0.0
		value["player_on_screen"] = 1.0 if Rect2(corner, seen).has_point(Vector2(centre.x, centre.y)) else 0.0


static func _occluded(cam: Camera3D, player: Node, to: Vector3) -> bool:
	## a physics body between the camera and the player's centre that is neither the player's nor the camera's own
	## (areas aside)
	var from := cam.global_position
	if from.distance_squared_to(to) < 1e-8 or cam.get_world_3d() == null:
		return false
	var space := cam.get_world_3d().direct_space_state
	if space == null:
		return false
	var ask := PhysicsRayQueryParameters3D.create(from, to)
	var skipped: Array[RID] = []
	for i in 32:
		ask.exclude = skipped
		var hit := space.intersect_ray(ask)
		if hit.is_empty():
			return false
		var body: Variant = hit.get("collider")
		if not (body is Node) or not (body == player or player.is_ancestor_of(body) or body == cam or cam.is_ancestor_of(body)):
			return true
		skipped.append(hit["rid"])
	return false
