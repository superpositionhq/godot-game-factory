extends Control
## The captions scene: buttons a play clicks or taps by the text they show. Each press prints its button's name.


func _ready() -> void:
	for n: Node in find_children("*", "BaseButton", true, false):
		var button := n as BaseButton
		button.pressed.connect(func() -> void: print("PRESSED ", button.name))
