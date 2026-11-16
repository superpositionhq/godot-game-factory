extends Node3D
## A lamp whose take_damage is of another shape: no hit with (amount, source) can call it.


func take_damage(amount: float) -> float:
	return amount
