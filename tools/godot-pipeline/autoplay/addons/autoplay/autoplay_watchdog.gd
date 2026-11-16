extends RefCounted
# The exit watchdog: ends a game that hangs during a run, so a hang cannot hold the GPU until its caller's own
# timeout, whoever started it (the recorder, a hand test). A thread of its own, independent of the main thread: the
# main thread beats once a frame, and when no frame has come for the armed number of seconds of the machine's clock
# the thread writes watchdog.json (prepared when armed) and ends the process. It is stopped before the game quits.

var _thread: Thread
var _mutex := Mutex.new()
var _limit_usec := 0  # 0 = not armed
var _beat_usec := 0
var _path := ""
var _note := ""
var _stop := false


## End the process when no frame has come for `seconds`; `reason` goes into the note.
func arm(seconds: float, reason: String, path: String) -> void:
	_mutex.lock()
	_limit_usec = int(seconds * 1000000.0)
	_beat_usec = Time.get_ticks_usec()
	_path = path
	_note = JSON.stringify({
		"schema": "autoplay-watchdog/1", "reason": reason, "armed_t_ns": _beat_usec * 1000,
		"after_s": snappedf(seconds, 0.001), "exit_code": 0,
	}, "", false) + "\n"
	_mutex.unlock()
	if _thread == null:
		_thread = Thread.new()
		_thread.start(_loop)


## Once a frame, from the main thread.
func beat() -> void:
	_mutex.lock()
	_beat_usec = Time.get_ticks_usec()
	_mutex.unlock()


## Before the game quits: the thread ends and is joined.
func stop() -> void:
	if _thread == null:
		return
	_mutex.lock()
	_stop = true
	_mutex.unlock()
	_thread.wait_to_finish()
	_thread = null


func _loop() -> void:
	while true:
		OS.delay_msec(100)
		_mutex.lock()
		var stop_now := _stop
		var late := _limit_usec > 0 and Time.get_ticks_usec() - _beat_usec >= _limit_usec
		var path := _path
		var note := _note
		_mutex.unlock()
		if stop_now:
			return
		if not late:
			continue
		var f := FileAccess.open(path, FileAccess.WRITE)
		if f != null:  # the exit matters more than the note
			f.store_string(note)
			f.close()
		OS.kill(OS.get_process_id())
		return
