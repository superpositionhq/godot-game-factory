extends Node3D
## The scene's own logic: what a tap, the wheel, the back button and a key do, a coin made every second.

const Coin := preload("res://game/coin.gd")

var taps := 0
var zoom := 0
var backs := 0
var _clock := 0.0
var _made := 0
var _quit_at := -1.0
var _age := 0.0


func _ready() -> void:
	$HUD/TapButton.pressed.connect(_tapped)
	var loop: AudioStreamWAV = $Music.stream.duplicate()
	loop.loop_mode = AudioStreamWAV.LOOP_FORWARD
	loop.loop_end = 2205
	loop.resource_name = "music_loop"
	$Music.stream = loop
	$Music.play()
	# how many times the game was started on this saved data
	var visits := FileAccess.get_file_as_string("user://visits.txt").to_int() + 1 if FileAccess.file_exists("user://visits.txt") else 1
	var saved := FileAccess.open("user://visits.txt", FileAccess.WRITE)
	saved.store_string(str(visits))
	saved.close()
	# and whether the game was told it was closing the time before (it saves that only then)
	$HUD/VisitsLabel.text = "VISITS %d%s" % [visits, " CLOSED" if FileAccess.file_exists("user://closed.txt") else ""]
	for i in 250:  # more nodes than a sample keeps rows of
		var one := Node3D.new()
		one.position.x = i
		one.add_to_group("many")
		$Many.add_child(one)
	var args := OS.get_cmdline_user_args()
	var at := args.find("-quitAt")
	if at >= 0 and at + 1 < args.size():
		_quit_at = args[at + 1].to_float()


func _tapped() -> void:
	taps += 1
	$HUD/CountLabel.text = "TAPS %d" % taps


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_GO_BACK_REQUEST and is_node_ready():
		backs += 1
		$HUD/BackLabel.text = "BACK %d" % backs
	elif what == NOTIFICATION_WM_CLOSE_REQUEST:
		var saved := FileAccess.open("user://closed.txt", FileAccess.WRITE)
		saved.store_string("closed")
		saved.close()


func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			zoom += 1
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			zoom -= 1
		$HUD/ZoomLabel.text = "ZOOM %d" % zoom
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE:
			$Jump.play()
		elif event.keycode == KEY_ESCAPE:
			$HUD/Secret.visible = not $HUD/Secret.visible
		elif event.keycode == KEY_BACK:
			$HUD/KeyLabel.text = "KEY BACK"
	elif event is InputEventJoypadButton and event.pressed:
		$HUD/KeyLabel.text = "PAD %d" % event.button_index


func _process(delta: float) -> void:
	_age += delta
	if _quit_at >= 0.0 and _age >= _quit_at:
		get_tree().quit()
	_clock += delta
	if _clock >= 1.0:
		_clock -= 1.0
		_made += 1
		var coin := Node3D.new()
		coin.set_script(Coin)
		coin.name = "Coin%d" % _made
		coin.position = Vector3(-4.0 + _made, 0.5, -6.0)
		$Coins.add_child(coin)
		if $Coins.get_child_count() > 3:
			$Coins.get_child(0).queue_free()
