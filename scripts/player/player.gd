class_name Player
extends CharacterBody3D
## First-person operator: movement, lean, crouch, sprint, ADS, weapons,
## interaction, door breaching, deployable shield, health.

signal damaged(amount: float, from_pos: Vector3)
signal hit_confirmed(result: Dictionary)
signal died
signal interact_prompt(text: String, progress: float)
signal weapon_changed

const STAND_H := 1.75
const CROUCH_H := 1.15
const EYE_STAND := 1.62
const EYE_CROUCH := 1.08
const WALK := 4.3
const SPRINT := 6.6
const CROUCH_SPEED := 2.3
const ADS_SPEED := 2.7
const ACCEL := 55.0
const AIR_ACCEL := 8.0
const JUMP_V := 4.1
const LEAN_ANGLE := 0.24
const LEAN_SHIFT := 0.2

var health := 100.0
var alive := true
var camera: Camera3D
var lean_pivot: Node3D
var head: Node3D
var weapon_holder: Node3D
var weapons: Array[Weapon] = []
var current := 0
var loadout := WeaponDefs.DEFAULT_LOADOUT.duplicate()
var shields_left := 1
## Night vision: image intensifier with a battery (drains on, recharges off).
var nv_on := false
var nv_battery := 1.0
const NV_DRAIN := 1.0 / 75.0
const NV_RECHARGE := 1.0 / 40.0
var _nv_light: OmniLight3D
var deployed_shield: Node3D = null

var input_enabled := true
var _pitch := 0.0
var _recoil_pitch := 0.0      # accumulated recoil that auto-recovers
var _recoil_yaw_vel := 0.0
var _lean := 0.0
var _crouched := false
var _crouch_blend := 0.0
var _sprinting := false
var _aiming := false
var _look_delta := Vector2.ZERO
var _look_accum := Vector2.ZERO
var _step_dist := 0.0
var _last_damage_t := -100.0
var _shake := 0.0
var _land_dip := 0.0
var _was_on_floor := true
var _fall_speed := 0.0
var _switch_to := -1
var _focus: Node = null
var _hold_progress := 0.0
var _shape: CapsuleShape3D
var _col: CollisionShape3D
var _fov_cur := 90.0
var _lean_ray: RayCast3D
var _clip_ray: RayCast3D
var _time := 0.0
## Optional scripted input for automated captures/benchmarks.
var bot_input: Dictionary = {}


func _ready() -> void:
	add_to_group("player")
	collision_layer = 1 << 1
	collision_mask = 1
	floor_max_angle = deg_to_rad(46)
	floor_snap_length = 0.3
	_shape = CapsuleShape3D.new()
	_shape.radius = 0.32
	_shape.height = STAND_H
	_col = CollisionShape3D.new()
	_col.shape = _shape
	_col.position.y = STAND_H / 2.0
	add_child(_col)
	lean_pivot = Node3D.new()
	lean_pivot.position.y = 0.95
	add_child(lean_pivot)
	head = Node3D.new()
	head.position.y = EYE_STAND - 0.95
	lean_pivot.add_child(head)
	camera = Camera3D.new()
	camera.near = 0.02
	camera.far = 250.0
	camera.keep_aspect = Camera3D.KEEP_WIDTH   # FOV setting is horizontal, as in most PC shooters
	camera.fov = Settings.fov
	camera.current = true
	# Viewmodel lives on layer 2 so world-only effects can exclude it.
	camera.cull_mask = 0xFFFFF
	head.add_child(camera)
	weapon_holder = Node3D.new()
	camera.add_child(weapon_holder)
	_lean_ray = RayCast3D.new()
	_lean_ray.collision_mask = 1
	_lean_ray.add_exception(self)
	head.add_child(_lean_ray)
	_clip_ray = RayCast3D.new()
	_clip_ray.collision_mask = 1
	_clip_ray.target_position = Vector3(0, 0, -0.9)
	camera.add_child(_clip_ray)
	# Weak IR illuminator: only switched on with the goggles.
	_nv_light = OmniLight3D.new()
	_nv_light.light_color = Color(0.85, 0.9, 1.0)
	_nv_light.light_energy = 0.0
	_nv_light.omni_range = 14.0
	_nv_light.omni_attenuation = 1.2
	_nv_light.shadow_enabled = false
	_nv_light.light_volumetric_fog_energy = 0.0
	_nv_light.light_specular = 0.1
	camera.add_child(_nv_light)
	_nv_light.position = Vector3(0, 0.1, -0.3)
	for wid in ["rifle", "pistol"]:
		var w := Weapon.new()
		weapon_holder.add_child(w)
		w.setup(wid, self, loadout)
		w.visible = false
		weapons.append(w)
	weapons[0].visible = true
	Game.player = self


func get_aim_point() -> Vector3:
	return camera.global_position + Vector3(0, -0.15, 0)


func get_chest_point() -> Vector3:
	return camera.global_position + Vector3(0, -0.55 + _crouch_blend * 0.25, 0)


func weapon() -> Weapon:
	return weapons[current]


func is_crouched() -> bool:
	return _crouched


func movement_spread() -> float:
	var h := Vector2(velocity.x, velocity.z).length()
	var s := clampf(h / WALK, 0.0, 1.5)
	if not is_on_floor():
		s += 1.5
	if _crouched:
		s *= 0.6
	return s


func apply_recoil(v: float, h: float) -> void:
	var m := 1.0
	if _crouched:
		m = 0.82
	_pitch += deg_to_rad(v * m)
	_recoil_pitch += deg_to_rad(v * m)
	_recoil_yaw_vel += deg_to_rad(h * m) * 40.0
	_shake = minf(_shake + 0.15, 0.6)


func on_hit_confirmed(res: Dictionary) -> void:
	hit_confirmed.emit(res)


func set_loadout(l: Dictionary) -> void:
	loadout = l.duplicate()
	weapons[0].apply_loadout(loadout)
	weapon_changed.emit()


# ------------------------------------------------------------------ input
func _unhandled_input(event: InputEvent) -> void:
	if not alive or not input_enabled or Game.autotest:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var sens := Settings.sensitivity
		if _aiming:
			sens *= Settings.ads_sens_mult * weapon().stats.get("ads_sens", 1.0) * (weapon().stats.ads_fov / 0.86)
		_look_accum += event.relative
		rotate_y(-event.relative.x * sens)
		_pitch = clampf(_pitch - event.relative.y * sens, deg_to_rad(-88), deg_to_rad(88))
		# Pulling down against recoil consumes the recovery budget.
		if event.relative.y > 0.0:
			_recoil_pitch = maxf(0.0, _recoil_pitch - event.relative.y * sens)
	elif event.is_action_pressed("weapon_1"):
		_request_switch(0)
	elif event.is_action_pressed("weapon_2"):
		_request_switch(1)
	elif event.is_action_pressed("weapon_next") or event.is_action_pressed("weapon_prev"):
		_request_switch(1 - current)
	elif event.is_action_pressed("reload"):
		weapon().start_reload()
	elif event.is_action_pressed("fire_mode"):
		weapon().toggle_fire_mode()
	elif event.is_action_pressed("crouch"):
		_toggle_crouch()
	elif event.is_action_pressed("kick"):
		_kick()
	elif event.is_action_pressed("deploy"):
		_deploy_shield()
	elif event.is_action_pressed("night_vision"):
		toggle_nv()


func _act(name: String) -> bool:
	if bot_input.has(name):
		return bot_input[name]
	return input_enabled and not Game.autotest and Input.is_action_pressed(name)


func _move_vec() -> Vector2:
	if bot_input.has("move"):
		return bot_input.move
	if not input_enabled or Game.autotest:
		return Vector2.ZERO
	return Input.get_vector("move_left", "move_right", "move_forward", "move_back")


func _request_switch(i: int) -> void:
	if i == current or _switch_to != -1:
		return
	_switch_to = i
	weapon().set_equipped(false)
	Sfx.play("weapon_switch", -6.0)


func _toggle_crouch() -> void:
	if _crouched:
		if _can_stand():
			_crouched = false
	else:
		_crouched = true
		_sprinting = false


func _can_stand() -> bool:
	var q := PhysicsShapeQueryParameters3D.new()
	var s := CapsuleShape3D.new()
	s.radius = _shape.radius - 0.02
	s.height = STAND_H
	q.shape = s
	q.transform = Transform3D(Basis(), global_position + Vector3(0, STAND_H / 2.0 + 0.02, 0))
	q.collision_mask = 1
	q.exclude = [get_rid()]
	return get_world_3d().direct_space_state.intersect_shape(q, 1).is_empty()


# ------------------------------------------------------------------ update
func _physics_process(delta: float) -> void:
	_time += delta
	if not alive:
		_death_cam(delta)
		return
	var w := weapon()
	# Switching
	if _switch_to != -1 and w.is_lowered():
		w.visible = false
		current = _switch_to
		_switch_to = -1
		w = weapon()
		w.visible = true
		w._equip = 0.0
		w.set_equipped(true)
		weapon_changed.emit()
	# Stance
	var mv := _move_vec()
	_aiming = _act("aim") and alive
	var want_sprint := _act("sprint") and mv.y < -0.3 and not _aiming and is_on_floor()
	if want_sprint and _crouched and _can_stand():
		_crouched = false
	_sprinting = want_sprint and not _crouched
	if _sprinting and w.is_reloading() and w._reload_t < 0.3:
		w.cancel_reload()
	if bot_input.has("crouch_set") and bot_input.crouch_set != _crouched:
		_toggle_crouch()
	_crouch_blend = move_toward(_crouch_blend, 1.0 if _crouched else 0.0, delta * 7.0)
	var h := lerpf(STAND_H, CROUCH_H, _crouch_blend)
	_shape.height = h
	_col.position.y = h / 2.0
	var eye := lerpf(EYE_STAND, EYE_CROUCH, _crouch_blend)
	# Movement
	var speed := WALK
	if _sprinting:
		speed = SPRINT
	elif _crouched:
		speed = CROUCH_SPEED
	if _aiming:
		speed = minf(speed, ADS_SPEED * w.stats.get("ads_move_mult", 1.0))
	speed *= w.stats.move_mult
	if absf(_lean) > 0.3:
		speed = minf(speed, 3.0)
	var wish := (global_transform.basis * Vector3(mv.x, 0, mv.y))
	wish.y = 0
	wish = wish.limit_length(1.0) * speed
	var hv := Vector3(velocity.x, 0, velocity.z)
	var acc := ACCEL if is_on_floor() else AIR_ACCEL
	if wish.length() < 0.01 and is_on_floor():
		acc = ACCEL * 1.3
	hv = hv.move_toward(wish, acc * delta)
	velocity.x = hv.x
	velocity.z = hv.z
	if not is_on_floor():
		velocity.y -= 12.0 * delta
		_fall_speed = maxf(_fall_speed, -velocity.y)
	elif _act("jump") and not _crouched:
		velocity.y = JUMP_V
	move_and_slide()
	# Landing
	if is_on_floor() and not _was_on_floor:
		_land_dip = clampf(_fall_speed * 0.012, 0.01, 0.08)
		_footstep(true)
		_fall_speed = 0.0
	_was_on_floor = is_on_floor()
	_land_dip = move_toward(_land_dip, 0.0, delta * 0.4)
	# Footsteps
	var hs := Vector2(velocity.x, velocity.z).length()
	if is_on_floor() and hs > 0.5:
		_step_dist += hs * delta
		var stride := 2.4 if _sprinting else (1.4 if _crouched else 1.9)
		if _step_dist > stride:
			_step_dist = 0.0
			_footstep(false)
	# Lean
	var lean_in := 0.0
	if _act("lean_left"): lean_in -= 1.0
	if _act("lean_right"): lean_in += 1.0
	if _sprinting: lean_in = 0.0
	var max_lean := _lean_limit(signf(lean_in)) if lean_in != 0.0 else 1.0
	_lean = move_toward(_lean, lean_in * max_lean, delta * 5.5)
	lean_pivot.rotation.z = -_lean * LEAN_ANGLE
	lean_pivot.position.x = _lean * LEAN_SHIFT
	lean_pivot.position.y = lerpf(0.95, 0.6, _crouch_blend)
	head.position.y = eye - lean_pivot.position.y - _land_dip
	# Recoil recovery and yaw kick
	var rec := deg_to_rad(w.stats.recoil_recover) * delta
	var r := minf(rec, _recoil_pitch)
	if not (_act("fire") and w.can_fire() and w.ammo > 0) or w._cooldown > 0.12:
		_pitch -= r
		_recoil_pitch -= r
	rotate_y(-_recoil_yaw_vel * delta)
	_recoil_yaw_vel = lerpf(_recoil_yaw_vel, 0.0, 1.0 - exp(-25.0 * delta))
	if bot_input.has("look"):
		var lk: Vector2 = bot_input.look
		rotate_y(-lk.x * delta)
		_pitch = clampf(_pitch - lk.y * delta, -1.4, 1.4)
	head.rotation.x = _pitch
	# Camera shake / bob roll
	_shake = move_toward(_shake, 0.0, delta * 2.0)
	camera.rotation.z = sin(_time * 47.0) * 0.012 * _shake
	camera.rotation.x = sin(_time * 53.0) * 0.008 * _shake
	camera.h_offset = 0
	# FOV
	var target_fov := Settings.fov
	if w.ads > 0.0:
		target_fov = lerpf(Settings.fov, Settings.fov * w.ads_fov(), w.ads * w.ads * (3.0 - 2.0 * w.ads))
	if _sprinting:
		target_fov += 4.0
	_fov_cur = lerpf(_fov_cur, target_fov, 1.0 - exp(-18.0 * delta))
	camera.fov = _fov_cur
	# Weapon
	if _sprinting:
		w.trigger(false, delta)
	else:
		w.trigger(_act("fire"), delta)
	_clip_ray.force_raycast_update()
	var wall_d := 1.0
	if _clip_ray.is_colliding():
		wall_d = camera.global_position.distance_to(_clip_ray.get_collision_point())
	w.update_clip(wall_d)
	_look_delta = _look_accum
	_look_accum = Vector2.ZERO
	w.update_view(delta, _aiming, _sprinting, hs, _look_delta / maxf(delta * 60.0, 0.001), _crouched, is_on_floor())
	# Interaction
	_update_interact(delta)
	# Night vision battery
	if nv_on:
		nv_battery = maxf(0.0, nv_battery - NV_DRAIN * delta)
		if nv_battery <= 0.0:
			toggle_nv()
			Game.say("NIGHT VISION BATTERY DEPLETED", 2.0)
	else:
		nv_battery = minf(1.0, nv_battery + NV_RECHARGE * delta)
	# Regen
	if _time - _last_damage_t > 6.0 and health < 100.0:
		health = minf(100.0, health + 7.0 * delta)


func _lean_limit(dir: float) -> float:
	# Prevent leaning the camera through walls.
	_lean_ray.position = Vector3.ZERO
	_lean_ray.global_position = global_position + Vector3(0, head.global_position.y - global_position.y, 0)
	_lean_ray.target_position = _lean_ray.global_transform.basis.inverse() * (global_transform.basis.x * dir * 0.6)
	_lean_ray.force_raycast_update()
	if _lean_ray.is_colliding():
		var d := _lean_ray.global_position.distance_to(_lean_ray.get_collision_point())
		return clampf((d - 0.22) / 0.38, 0.0, 1.0)
	return 1.0


func _footstep(land: bool) -> void:
	var on_metal := false
	var col := get_last_slide_collision()
	if col and col.get_collider() and col.get_collider().get_meta("surface", "") == "metal":
		on_metal = true
	var vol := -14.0
	var radius := 5.0
	if _sprinting:
		vol = -8.0
		radius = 12.0
	elif _crouched:
		vol = -22.0
		radius = 1.5
	if land:
		vol = -6.0
		radius = 9.0
	Sfx.play_3d("step_metal" if on_metal else "step_concrete", global_position, vol, 0.1, 3.0)
	Game.emit_noise(global_position, radius, self)


func _update_interact(delta: float) -> void:
	var q := PhysicsRayQueryParameters3D.create(camera.global_position, camera.global_position - camera.global_transform.basis.z * 2.4, 1 | (1 << 4))
	q.collide_with_areas = true
	q.exclude = [get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	var target: Node = null
	if hit:
		var c: Node = hit.collider
		while c and not c.has_method("get_prompt"):
			c = c.get_parent()
			if c == get_tree().current_scene:
				c = null
		target = c
	if target != _focus:
		_hold_progress = 0.0
		_focus = target
	if _focus == null:
		interact_prompt.emit("", 0.0)
		return
	var prompt: String = _focus.get_prompt(self)
	if prompt == "":
		interact_prompt.emit("", 0.0)
		return
	var holding := _act("interact")
	if _focus.has_method("hold"):
		if holding:
			_hold_progress = _focus.hold(self, delta)
		else:
			_focus.hold(self, -1.0)
		interact_prompt.emit(prompt, _hold_progress)
	else:
		if (holding and not _interact_was) or (bot_input.get("interact_tap", false)):
			_focus.interact(self)
		interact_prompt.emit(prompt, 0.0)
	_interact_was = holding


var _interact_was := false


func _kick() -> void:
	var q := PhysicsRayQueryParameters3D.create(camera.global_position, camera.global_position - camera.global_transform.basis.z * 2.0, 1)
	q.exclude = [get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit:
		var c: Node = hit.collider
		while c and not c.has_method("breach"):
			c = c.get_parent()
			if c == get_tree().current_scene:
				c = null
		if c:
			c.breach(self)
			_shake = 0.6
			_land_dip = 0.05
			return
	Sfx.play("weapon_switch", -10.0)


func _deploy_shield() -> void:
	if shields_left <= 0 or not is_on_floor():
		Game.say("NO SHIELD AVAILABLE", 1.5)
		return
	var fwd := -global_transform.basis.z
	fwd.y = 0
	fwd = fwd.normalized()
	var pos := global_position + fwd * 1.0
	# Check space
	var q := PhysicsRayQueryParameters3D.create(global_position + Vector3(0, 0.6, 0), pos + Vector3(0, 0.6, 0) + fwd * 0.3, 1)
	q.exclude = [get_rid()]
	if get_world_3d().direct_space_state.intersect_ray(q):
		Game.say("NOT ENOUGH SPACE", 1.5)
		return
	var s := preload("res://scripts/level/deploy_shield.gd").new()
	get_tree().current_scene.add_child(s)
	s.global_position = pos
	s.look_at(pos - fwd, Vector3.UP)
	shields_left -= 1
	Sfx.play_3d("door_breach", pos, -12.0)
	Game.emit_noise(pos, 6.0, self)


func toggle_nv() -> void:
	if not nv_on and nv_battery < 0.08:
		Game.say("NIGHT VISION RECHARGING", 1.5)
		return
	nv_on = not nv_on
	_nv_light.light_energy = 0.45 if nv_on else 0.0
	Sfx.play("ads_in", -2.0, 0.0)
	Sfx.play("ui_hack_tick", -12.0 if nv_on else -16.0, 0.0)


func pick_up_shield() -> void:
	shields_left += 1


func take_damage(amount: float, from_pos: Vector3) -> void:
	if not alive:
		return
	if Game.autotest and bot_input.get("god", false):
		Game.stats["god_absorbed"] = Game.stats.get("god_absorbed", 0.0) + amount
		damaged.emit(amount, from_pos)
		return
	health -= amount
	_last_damage_t = _time
	Game.stats.damage_taken += amount
	_shake = minf(_shake + 0.5, 1.0)
	damaged.emit(amount, from_pos)
	Sfx.play("player_hurt", -3.0)
	# Hit flinch
	_pitch += deg_to_rad(randf_range(0.8, 1.8))
	rotate_y(deg_to_rad(randf_range(-1.2, 1.2)))
	if health <= 0.0:
		health = 0.0
		alive = false
		weapon().visible = false
		died.emit()
		Game.set_state(Game.State.FAILED)


func _death_cam(delta: float) -> void:
	velocity.y -= 12.0 * delta
	velocity.x = lerpf(velocity.x, 0, delta * 4)
	velocity.z = lerpf(velocity.z, 0, delta * 4)
	move_and_slide()
	head.position.y = move_toward(head.position.y, -0.55, delta * 1.6)
	camera.rotation.z = move_toward(camera.rotation.z, 0.9, delta * 1.4)
