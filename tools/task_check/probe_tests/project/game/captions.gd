extends Control
## The captions scene: buttons a play clicks or taps by the text they show, and a list scrolled so its lower rows are
## out of its view. Each press prints its button's name; a click on a panel of the list prints the panel's.


func _ready() -> void:
	for n: Node in find_children("*", "BaseButton", true, false):
		var button := n as BaseButton
		button.pressed.connect(func() -> void: print("PRESSED ", button.name))
	for n: Node in find_children("Panel*", "Panel", true, false):
		var panel := n as Panel
		panel.gui_input.connect(func(event: InputEvent) -> void:
			var press := event as InputEventMouseButton
			if press != null and press.pressed and press.button_index == MOUSE_BUTTON_LEFT:
				print("PRESSED ", panel.name))
