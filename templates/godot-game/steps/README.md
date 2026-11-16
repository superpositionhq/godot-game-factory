# Generator steps

A scene, a resource, a script or a setting is a text file: write it with your file tools and commit it. A step is
for what only the engine can make: a procedural mesh saved as a resource, baked data, a navigation mesh, a scene put
together by code from many parts. Each is a GDScript file here, run headless with

    powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."

(`godot --headless --script res://steps/<name>.gd` through the machine's heavy-job limiter). The run appends one
`workflow.jsonl` row (op `editor.step`) whose `source.script` and `source.sha256` are the script as it ran. Keep
every step that was run, unchanged: write a new one (`build_harbor_v2.gd`) instead of editing one that already ran,
so each row still points at the real code.

The creation replay runs these steps again to rebuild the project from its history, so, from the first step on:

- commit every step you run, here, together with what it wrote (and every new file's `.import` or `.uid`);
- reach files through the project (`res://scenes/Harbor.tscn`), never an absolute path to this folder;
- a step makes the same content from the same inputs every time: seed every random number, no clock, no network;
- a step ends itself on every path: `quit()` when it is done, `quit(1)` when it failed (after `push_error` with the
  reason), so the run's exit code and the row's status say so. A script error does not end a headless run: a step
  that hits one before its `quit()` (a `FileAccess.open` into a missing folder returns null, and the next call on it
  fails) runs on until `godot.ps1` stops it after `-TimeoutSeconds` (default 600) with a failed row. Check what a
  call returns before using it;
- a step draws nothing: `--headless` has no renderer, and a viewport read back there is empty. Screenshots come from
  `Scripts/godot.ps1 play -Shots <n>`.

What the engine does that a step must allow for:

- a step script extends `SceneTree` and works in `_init()`. The main scene is never loaded, and in `_init()` the
  autoloads are not there yet: a game script that names one (`AutoPlay`, `Scenarios`) does not compile when loaded
  from `_init()` ("Identifier not found"). A step that needs such a script or a scene that uses it does its work in
  the first `_process(delta)` call instead, where the autoloads are in the tree, and calls `quit()` there;
- a node goes into a saved scene only when its `owner` is the scene's root: set `owner` on every node added by code
  before `PackedScene.pack()`, or the saved scene holds the root alone, with no warning;
- `ResourceSaver.save` and `DirAccess.make_dir_recursive_absolute` return an error code and print nothing: check it,
  and make the folder before saving into it;
- a file a step writes gets its `.import` or `.uid` at the next import: run `Scripts/godot.ps1 import` after the step
  and commit what it made.

A step looks like this, run with `Scripts/godot.ps1 step -Script steps/build_harbor.gd -Reason "..."`:

```gdscript
extends SceneTree


func _init() -> void:
	var root := Node3D.new()
	root.name = "Harbor"
	for i in 4:
		var pier := MeshInstance3D.new()
		pier.name = "Pier%d" % (i + 1)
		pier.mesh = BoxMesh.new()
		pier.position = Vector3(i * 6.0, 0.0, 0.0)
		root.add_child(pier)
		pier.owner = root   # without an owner the node is not saved
	var scene := PackedScene.new()
	var err := scene.pack(root)
	if err == OK:
		DirAccess.make_dir_recursive_absolute("res://scenes")
		err = ResourceSaver.save(scene, "res://scenes/Harbor.tscn")
	root.free()
	if err != OK:
		push_error("the scene was not saved: %s" % error_string(err))
		quit(1)
		return
	print("saved res://scenes/Harbor.tscn with 4 piers")
	quit()
```
