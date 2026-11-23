extends StaticBody3D
## Armory case at the insertion point: opens the attachment loadout screen.


func get_prompt(_p: Node) -> String:
	return "[F] ARMORY - CONFIGURE WEAPON"


func interact(_p: Node) -> void:
	Sfx.play("weapon_switch", -4.0)
	Game.request_loadout.emit()
