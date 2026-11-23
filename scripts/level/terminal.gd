extends StaticBody3D
## Readable log terminal for environmental storytelling.

var title := "LOG"
var lines: PackedStringArray = []
var _read := false


func get_prompt(_p: Node) -> String:
	return "[F] READ " + title


func interact(_p: Node) -> void:
	Sfx.play("ui_click", -6.0)
	Game.say("\n".join(lines), 7.0)
	_read = true
