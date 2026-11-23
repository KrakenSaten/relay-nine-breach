extends StaticBody3D
## Wall breaker panel. Shoot it or switch it off to black out its room:
## robots' sight range drops sharply in the dark (room-clearing opportunity).

var room := ""
var hp := 50.0
var dead := false
var led: MeshInstance3D


func get_prompt(_p: Node) -> String:
	return "" if dead else "[F] CUT POWER TO " + room.to_upper()


func interact(_p: Node) -> void:
	_kill(false)


func take_hit(dmg: float, pos: Vector3, _dir: Vector3, normal: Vector3) -> void:
	Fx.impact(pos, normal, "metal")
	if dead:
		return
	hp -= dmg
	if hp <= 0.0:
		_kill(true)


func _kill(shot: bool) -> void:
	if dead:
		return
	dead = true
	Game.set_room_lit(room, false)
	Fx.mini_arcs(global_position, 6, 0.5)
	Fx.smoke(global_position, -global_transform.basis.z)
	Sfx.play_3d("robot_zap", global_position, 2.0)
	Sfx.play_3d("robot_death", global_position, -8.0)
	Game.emit_noise(global_position, 14.0 if shot else 6.0, Game.player)
	Game.say("POWER CUT: " + room.to_upper() + " IS DARK", 2.5)
	if led:
		led.visible = false
