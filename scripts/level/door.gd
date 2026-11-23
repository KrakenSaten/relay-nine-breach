class_name Door
extends Node3D
## Hinged steel door. Opens away from whoever uses it. Can be kicked open
## (breach): fast, loud, and it slams robots standing behind it.
## The node origin is the hinge; the slab extends along local +X.

var locked := false
var lock_reason := "LOCKED"
var open_angle := 0.0      # current, radians
var target := 0.0
var speed := 2.2           # rad/s
var body: AnimatableBody3D
var base_yaw := 0.0
var width := 1.08
var led: MeshInstance3D
var _breach_t := 0.0


func build(props_root: Node3D, w := 1.08) -> void:
	width = w
	base_yaw = rotation.y
	body = AnimatableBody3D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	body.sync_to_physics = true
	body.set_meta("surface", "metal")
	add_child(body)
	var slab: Node3D = props_root.get_node("door_slab").duplicate()
	slab.transform = Transform3D.IDENTITY
	slab.scale = Vector3(w, 1.0, 1.0)
	body.add_child(slab)
	MatLib.remap_scene(slab)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(w - 0.04, 2.08, 0.07)
	cs.shape = bs
	cs.position = Vector3(w / 2.0, 1.05, 0)
	body.add_child(cs)
	# Lock indicator on both faces
	led = MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.05, 0.05, 0.09)
	led.mesh = bm
	led.position = Vector3(w - 0.12, 1.25, 0)
	body.add_child(led)
	_update_led()


func _update_led() -> void:
	if led:
		led.material_override = MatLib.flat(Color(1, 0.1, 0.05), 0, 0.4, Color(1, 0.08, 0.03), 6.0) if locked else MatLib.flat(Color(0.2, 1, 0.4), 0, 0.4, Color(0.15, 1.0, 0.35), 3.0)


func set_locked(v: bool, reason := "LOCKED") -> void:
	locked = v
	lock_reason = reason
	_update_led()


func is_open() -> bool:
	return absf(target) > 0.1


func _side_sign(from: Vector3) -> float:
	# Positive local Z side?
	var local := to_local(from)
	return 1.0 if local.z > 0.0 else -1.0


func get_prompt(_p: Node) -> String:
	if locked:
		return lock_reason
	return "[F] CLOSE DOOR" if is_open() else "[F] OPEN DOOR    [V] BREACH"


func interact(p: Node3D) -> void:
	if locked:
		Sfx.play_3d("door_locked", global_position + Vector3.UP, -2.0)
		return
	if is_open():
		target = 0.0
		speed = 2.0
	else:
		# Swing away from the user: user on +Z side pushes door to -Z side.
		target = -_side_sign(p.global_position) * deg_to_rad(100)
		speed = 2.0
	Sfx.play_3d("door_open", global_position + Vector3.UP, -4.0)
	Game.emit_noise(global_position, 7.0, p)


func bot_open(bot: Node3D) -> void:
	if locked or is_open():
		return
	target = -_side_sign(bot.global_position) * deg_to_rad(100)
	speed = 1.6
	Sfx.play_3d("door_open", global_position + Vector3.UP, -3.0)


func breach(p: Node3D) -> void:
	if locked:
		Sfx.play_3d("door_breach", global_position + Vector3.UP, 0.0)
		Game.say("DOOR IS SEALED - CANNOT BREACH", 2.0)
		return
	if is_open():
		return
	var side := _side_sign(p.global_position)
	target = -side * deg_to_rad(105)
	speed = 11.0
	_breach_t = 0.35
	Sfx.play_3d("door_breach", global_position + Vector3.UP, 4.0, 0.05, 8.0)
	Game.emit_noise(global_position, 28.0, p)
	Fx.smoke(global_position + global_transform.basis.x * width * 0.5 + Vector3.UP, global_transform.basis.z * -side)
	# Slam anything standing in the swing arc on the far side.
	var swing_center := global_position + global_transform.basis.x * width * 0.5 + global_transform.basis.z * (-side) * 0.6
	for b in get_tree().get_nodes_in_group("teslabot"):
		if b.state != Teslabot.S.DEAD and b.global_position.distance_to(swing_center) < 1.5:
			b.explosion_damage(45.0, global_position)
			b._stagger(1.4)
			Sfx.play_3d("impact_metal", b.global_position + Vector3.UP, 2.0)


func _physics_process(delta: float) -> void:
	_breach_t -= delta
	if not is_equal_approx(open_angle, target):
		open_angle = move_toward(open_angle, target, speed * delta)
		body.rotation.y = open_angle
		if is_equal_approx(open_angle, target) and speed > 5.0:
			Sfx.play_3d("impact_metal", global_position + Vector3.UP, -2.0)
