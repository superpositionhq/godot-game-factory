# Scripts

`godot.ps1` runs the engine for this game through the machine's heavy-job limiter: the import (`import`, which is
also "the project compiles"), generator steps (`step`), a `workflow.jsonl` row for work done by hand (`row`), the
player build (`build`, with `-Android` the APK of a mobile game too), rendered runs of the project (`play`) and AutoPlay
runs of the built player (`autoplay`: the bot plays one scenario on a Windows desktop of its own, and its files go to
`Logs/autoplay/`). The modes are listed at the top of the file; logs go to `Logs/godot-ps1/`.

Generator steps are GDScript files under `steps/` (see the README there), run with
`Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."`. Keep this call shape: the creation replay recognises
it in the recorded command.

The empty `.gdignore` in this folder keeps the engine from scanning it.
