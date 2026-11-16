extends Node3D
## The sounds scene's own logic: a key starts a sound. 1 and 2 play a one-shot of 0.1 s on a player made for it and
## freed when it ends (shot_a, shot_b); 3 a tick shorter than a frame; 4 a placed sound out of earshot; 5 one beside
## the camera; 6 one on a muted bus; 7 a long one, again while it plays; 8 one whose stream has no name.

var _streams := {}


func _ready() -> void:
	for sound: Array in [["shot_a", 0.1], ["shot_b", 0.1], ["tick", 0.002], ["far", 0.3], ["close", 0.3], ["hush", 0.3],
			["long", 1.0], ["", 0.1]]:
		_streams[sound[0]] = _tone(sound[0], sound[1])
	AudioServer.add_bus()
	AudioServer.set_bus_name(AudioServer.bus_count - 1, "Mute")
	AudioServer.set_bus_mute(AudioServer.bus_count - 1, true)
	$Muted.bus = "Mute"
	$Placed.stream = _streams["far"]
	$Close.stream = _streams["close"]
	$Muted.stream = _streams["hush"]
	$Long.stream = _streams["long"]


static func _tone(name: String, seconds: float) -> AudioStreamWAV:
	var data := PackedByteArray()
	var count := int(seconds * 11025.0)
	data.resize(count * 2)
	for i in count:
		data.encode_s16(i * 2, int(sin(i * 0.5) * 12000.0))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = 11025
	stream.data = data
	stream.resource_name = name
	return stream


func _one_shot(name: String) -> void:
	var player := AudioStreamPlayer.new()
	player.stream = _streams[name]
	add_child(player)
	player.finished.connect(player.queue_free)
	player.play()


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match event.keycode:
		KEY_1: _one_shot("shot_a")
		KEY_2: _one_shot("shot_b")
		KEY_3: _one_shot("tick")
		KEY_4: $Placed.play()
		KEY_5: $Close.play()
		KEY_6: $Muted.play()
		KEY_7: $Long.play()
		KEY_8: _one_shot("")
