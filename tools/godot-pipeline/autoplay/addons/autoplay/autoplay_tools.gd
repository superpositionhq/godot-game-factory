extends RefCounted
# Two flags any run may carry, with or without -autoplay:
#
#   -size <W>x<H>                           the exact frame size of the run. The root window scales its content in
#                                           "viewport" mode at that size and keeps the aspect, so every frame the
#                                           game renders is W x H pixels whatever the window is (a 1080x1920 frame on
#                                           a screen that cannot hold such a window).
#   -shots <n> -shotDir <dir> -seconds <s>  n PNG frames, 01.png .. evenly spaced over s seconds (at s * k / (n + 1)),
#                                           then the game quits with exit code 0. Under -autoplay the seconds count
#                                           from go and the run ends as a run does.

var host: Node
var run: RefCounted

var _shots := 0
var _shot_dir := ""
var _seconds := 10.0
var _taken := 0
var _saving := false
var _asked_frame := 0
var _start := -1.0
var _done := false


func _init(p_host: Node, p_run: RefCounted) -> void:
	host = p_host
	run = p_run


func enter_tree() -> void:
	var size: String = run.value("-size")
	if size != "":
		var parts := size.to_lower().split("x")
		if parts.size() == 2 and parts[0].is_valid_int() and parts[1].is_valid_int() and parts[0].to_int() > 0 and parts[1].to_int() > 0:
			var root := host.get_tree().root
			root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
			root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
			root.content_scale_size = Vector2i(parts[0].to_int(), parts[1].to_int())
		else:
			printerr("AutoPlay: -size %s: not <width>x<height>" % size)
	var n: String = run.value("-shots")
	if n == "":
		return
	if not n.is_valid_int() or n.to_int() < 1:
		printerr("AutoPlay: -shots %s: not a number of frames" % n)
		return
	_shots = n.to_int()
	var s: String = run.value("-seconds")
	if s.is_valid_float() and s.to_float() > 0.0:
		_seconds = s.to_float()
	var dir: String = run.value("-shotDir")
	_shot_dir = ProjectSettings.globalize_path(dir if dir != "" else "user://shots").simplify_path()
	if DirAccess.make_dir_recursive_absolute(_shot_dir) != OK:
		printerr("AutoPlay: -shotDir %s cannot be made" % _shot_dir)
		_shots = 0


## Every frame, after the run's own update.
func update() -> void:
	if _shots == 0 or _done:
		return
	if run.active and not run.is_running() and _start < 0.0:
		return  # under -autoplay the shots span the run, from go
	if _start < 0.0:
		_start = run.now()
	var elapsed: float = run.now() - _start
	if _saving and Engine.get_process_frames() > _asked_frame + 1:
		# no frame was drawn (a headless run): the shot is reported missing and the run goes on
		RenderingServer.frame_post_draw.disconnect(_save)
		_save()
	if not _saving and _taken < _shots and elapsed >= _seconds * (_taken + 1) / (_shots + 1):
		_saving = true
		_asked_frame = Engine.get_process_frames()
		RenderingServer.frame_post_draw.connect(_save, CONNECT_ONE_SHOT)
	if _taken >= _shots and elapsed >= _seconds:
		_done = true
		if not run.active:
			host.get_tree().quit(0)


## After the frame is drawn: the root viewport's picture, as the game rendered it.
func _save() -> void:
	_saving = false
	_taken += 1
	var path := _shot_dir.path_join(("%02d.png" if _shots < 100 else "%03d.png") % _taken)
	var texture := host.get_tree().root.get_texture()
	var image := texture.get_image() if texture != null else null
	if image == null or image.is_empty():
		printerr("AutoPlay: no picture for %s (a headless run draws nothing)" % path)
		return
	var err := image.save_png(path)
	if err != OK:
		printerr("AutoPlay: %s could not be written (error %d)" % [path, err])
	else:
		print("AutoPlay: shot %s (%dx%d)" % [path, image.get_width(), image.get_height()])
