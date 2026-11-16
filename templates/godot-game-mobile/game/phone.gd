extends Node
## This game is an Android phone game, held in __ORIENTATION__ for good and played by touch (Platform.json at the repo
## root says so to every tool). On the PC it is played, pictured and recorded at the phone's size,
## __PHONE_WIDTH__x__PHONE_HEIGHT__, with the Mobile renderer, as project.godot sets both.
## This autoload tells the AutoPlay drop-in the game is a phone game: in its runs the bot plays with fingers
## (AutoPlay.touch, AutoPlay.touch_up) and the back button ("<Keyboard>/escape", which the drop-in sends as Android's
## go-back request) and nothing else.
## Keep this file as it is.

const PORTRAIT := __PORTRAIT__


func _enter_tree() -> void:
	AutoPlay.phone(PORTRAIT)
