extends Node3D
## A training dummy whose take_damage has a third argument with a default: (amount, source) still calls it.

var hits := 0


func take_damage(amount: float, _source: Node, _critical := false) -> float:
	hits += 1
	return amount
