extends StaticBody3D
## Deployable ballistic shield (G). Stops bullets and tesla arcs until it is
## destroyed. Can be picked back up with F.

var hp := 260.0
var _mat: StandardMaterial3D


func _ready() -> void:
	collision_layer = 1
	collision_mask = 0
	set_meta("surface", "metal")
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(1.05, 1.05, 0.08)
	cs.shape = bs
	cs.position = Vector3(0, 0.55, 0)
	add_child(cs)
	var plate := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(1.05, 1.0, 0.05)
	plate.mesh = bm
	plate.material_override = MatLib.steel_door()
	plate.position = Vector3(0, 0.57, 0)
	add_child(plate)
	var port := MeshInstance3D.new()
	var pm := BoxMesh.new()
	pm.size = Vector3(0.3, 0.08, 0.06)
	port.mesh = pm
	port.material_override = MatLib.flat(Color(0.05, 0.08, 0.08), 0.2, 0.05)
	port.position = Vector3(0, 0.85, 0)
	add_child(port)
	for x in [-0.4, 0.4]:
		var leg := MeshInstance3D.new()
		var lm := BoxMesh.new()
		lm.size = Vector3(0.06, 0.04, 0.45)
		leg.mesh = lm
		leg.material_override = MatLib.flat(Color(0.05, 0.05, 0.05), 0.8, 0.4)
		leg.position = Vector3(x, 0.03, 0.18)
		add_child(leg)
	var stripe := MeshInstance3D.new()
	var sm := BoxMesh.new()
	sm.size = Vector3(1.0, 0.06, 0.052)
	stripe.mesh = sm
	stripe.material_override = MatLib.hazard()
	stripe.position = Vector3(0, 1.02, 0)
	add_child(stripe)


func get_prompt(_p: Node) -> String:
	return "[F] PICK UP SHIELD (%d%%)" % int(hp / 260.0 * 100.0)


func interact(p: Node) -> void:
	p.pick_up_shield()
	Sfx.play("weapon_switch", -4.0)
	queue_free()


func take_hit(dmg: float, pos: Vector3, _dir: Vector3, normal: Vector3) -> void:
	Fx.impact(pos, normal, "shield")
	hp -= dmg
	if hp <= 0.0:
		Fx.smoke(global_position + Vector3.UP * 0.5)
		Fx.mini_arcs(global_position + Vector3.UP * 0.5, 4, 0.6)
		Sfx.play_3d("door_breach", global_position, 0.0)
		Game.say("SHIELD DESTROYED", 1.5)
		queue_free()
