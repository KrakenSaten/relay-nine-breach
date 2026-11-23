class_name Teslabot
extends CharacterBody3D
## Teslabot security unit. Perception (vision cone + light, hearing), squad
## coordination through the Director, cover/peek, flanking, telegraphed arc
## attacks, per-zone damage with functional consequences, procedural animation.

enum S { PATROL, SUSPICIOUS, INVESTIGATE, COMBAT, SEARCH, STAGGER, DEAD }

const MAX_HP := 300.0
const ZONE_MULT := {"head": 2.0, "core": 2.7, "torso": 0.85, "pelvis": 0.8, "arm_R": 0.7, "arm_L": 0.6, "leg_L": 0.65, "leg_R": 0.65}
const ZONE_HP := {"head": 70.0, "arm_R": 85.0, "leg_L": 90.0, "leg_R": 90.0, "core": 9999.0}
const SIGHT_LIT := 26.0
const SIGHT_DARK := 9.0
const SIGHT_DARK_IR := 18.0   # infrared optics once alerted
const FOV_HALF := deg_to_rad(58)
const WALK := 1.7
const RUN := 3.8
const ARC_DAMAGE := 30.0
const WINDUP := 0.48

@export var patrol_points: Array[Vector3] = []
@export var squad_name := ""
var director: Node
var state := S.PATROL
var hp := MAX_HP
var zone_hp := {}
var blinded := false
var arm_damaged := false
var limp := 0.0               # 0..1
var role := "assault"         # assault | flanker | cover | overwatch | pusher
var awareness := 0.0
var target_visible := false
var last_seen_t := -100.0
var last_known := Vector3.ZERO
var stimulus := Vector3.ZERO

var agent: NavigationAgent3D
var model: Node3D
var bones := {}
var hitboxes: Array[Area3D] = []
var eye_mats: Array = []
var core_mat: StandardMaterial3D
var tip_mat: StandardMaterial3D
var charge_light: OmniLight3D
var eye_light: SpotLight3D
var hum: AudioStreamPlayer3D

var _t := 0.0
var _think_t := 0.0
var _sense_t := 0.0
var _patrol_i := 0
var _wait := 0.0
var _phase := 0.0
var _gait_amp := 0.0
var _move_target := Vector3.ZERO
var _has_move := false
var _move_speed := WALK
var _face_dir := Vector3.FORWARD
var _aim_point := Vector3.ZERO
var _aim_blend := 0.0       # 0 lowered, 1 aiming
var _attack_t := -1.0       # >=0 during windup
var _attack_cd := 1.0
var _has_token := false
var _cover: Dictionary = {}
var _cover_phase := ""      # "", "hide", "peek"
var _cover_t := 0.0
var _search_t := 0.0
var _stagger_t := 0.0
var _flinch := Vector3.ZERO
var _recent_dmg := 0.0
var _death_t := 0.0
var _death_dir := 1.0
var _spark_t := 0.0
var _step_side := 0
var _last_step_phase := 0.0
var _stuck_t := 0.0
var _last_pos := Vector3.ZERO
var _door_cd := 0.0
var _alerted_once := false
var _servo_cd := 0.0
var _rest := {}
var _crouch_b := 0.0
## M2 combat refinement
var suppression := 0.0          # 0..1, from near misses/hits; decays
var _push_t := 0.0              # aggressive push window (e.g. player reloading)
var _push_target := Vector3.ZERO
var _entry: Dictionary = {}     # room-entry plan from the director
var _visited: Array = []        # [pos, time] search memory
var _scan_t := 0.0


func _ready() -> void:
	add_to_group("teslabot")
	collision_layer = 1 << 2
	collision_mask = 1 | (1 << 1) | (1 << 2)
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.42
	cap.height = 2.0
	cs.shape = cap
	cs.position.y = 1.0
	add_child(cs)
	model = (load("res://assets/models/teslabot.glb") as PackedScene).instantiate()
	add_child(model)
	MatLib.remap_scene(model)
	for n in ["pelvis", "torso", "head", "core", "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "hip_L", "hip_R", "knee_L", "knee_R", "ankle_L", "ankle_R", "muzzle"]:
		bones[n] = model.find_child(n, true, false)
		if bones[n]:
			_rest[n] = bones[n].transform
	_setup_materials()
	_setup_hitboxes()
	_collect_armor()
	agent = NavigationAgent3D.new()
	agent.path_desired_distance = 0.7
	agent.target_desired_distance = 0.9
	agent.radius = 0.45
	agent.height = 2.0
	agent.path_max_distance = 3.0
	add_child(agent)
	charge_light = OmniLight3D.new()
	charge_light.light_color = Color(0.5, 0.75, 1.0)
	charge_light.omni_range = 4.0
	charge_light.light_energy = 0.0
	charge_light.shadow_enabled = false
	bones.muzzle.add_child(charge_light)
	# Optic casts a faint red cone: readable facing/awareness at a glance.
	eye_light = SpotLight3D.new()
	eye_light.light_color = Color(1.0, 0.25, 0.12)
	eye_light.light_energy = 1.2
	eye_light.spot_range = 9.0
	eye_light.spot_angle = 24.0
	eye_light.shadow_enabled = false
	eye_light.light_volumetric_fog_energy = 0.6
	bones.head.add_child(eye_light)
	eye_light.position = Vector3(0, 0.1, -0.22)
	hum = Sfx.loop_3d("robot_idle_loop", self, -14.0, 2.0)
	for z in ZONE_HP:
		zone_hp[z] = ZONE_HP[z]
	_face_dir = -global_transform.basis.z
	_last_pos = global_position
	Game.noise.connect(_on_noise)
	_attack_cd = randf_range(0.5, 1.5)
	_think_t = randf() * 0.4
	_sense_t = randf() * 0.15


func _setup_materials() -> void:
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = mi.mesh
		for i in mesh.get_surface_count():
			var m := mesh.surface_get_material(i)
			if m == null:
				continue
			match m.resource_name:
				"eye_glow":
					var em := MatLib.flat(Color(1, 0.25, 0.1), 0.0, 0.3, Color(1.0, 0.18, 0.05), 9.0).duplicate()
					mi.set_surface_override_material(i, em)
					eye_mats.append(em)
				"core_glow":
					core_mat = MatLib.flat(Color(0.6, 0.8, 1), 0.0, 0.3, Color(0.45, 0.75, 1.0), 6.0).duplicate()
					mi.set_surface_override_material(i, core_mat)
				"arc_tip":
					tip_mat = MatLib.flat(Color(0.6, 0.8, 1), 0.0, 0.3, Color(0.5, 0.8, 1.0), 2.0).duplicate()
					mi.set_surface_override_material(i, tip_mat)
				"copper":
					mi.set_surface_override_material(i, MatLib.flat(Color(0.72, 0.4, 0.22), 1.0, 0.32))


func _hitbox(zone: String, bone: String, offset: Vector3, size: Vector3) -> void:
	var a := Area3D.new()
	a.collision_layer = 1 << 3
	a.collision_mask = 0
	a.monitoring = false
	a.monitorable = true
	a.set_meta("bot", self)
	a.set_meta("zone", zone)
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = size
	cs.shape = b
	a.add_child(cs)
	bones[bone].add_child(a)
	# Bone origins are at joints in model space; offsets are model-space from the joint.
	a.position = offset
	hitboxes.append(a)


func _setup_hitboxes() -> void:
	_hitbox("head", "head", Vector3(0, 0.04, -0.07), Vector3(0.29, 0.22, 0.36))
	_hitbox("torso", "torso", Vector3(0, 0.34, -0.02), Vector3(0.62, 0.62, 0.44))
	_hitbox("core", "core", Vector3(0, 0.0, 0.05), Vector3(0.3, 0.38, 0.14))
	_hitbox("pelvis", "pelvis", Vector3(0, -0.02, 0), Vector3(0.38, 0.24, 0.26))
	_hitbox("arm_R", "elbow_R", Vector3(0, 0, -0.2), Vector3(0.17, 0.17, 0.5))
	_hitbox("arm_R", "shoulder_R", Vector3(0.02, -0.14, 0), Vector3(0.14, 0.34, 0.14))
	_hitbox("arm_L", "elbow_L", Vector3(0, 0, -0.15), Vector3(0.16, 0.2, 0.32))
	_hitbox("arm_L", "shoulder_L", Vector3(-0.02, -0.14, 0), Vector3(0.14, 0.34, 0.14))
	for s in ["L", "R"]:
		_hitbox("leg_" + s, "hip_" + s, Vector3(0.01 * (1 if s == "R" else -1), -0.21, 0), Vector3(0.16, 0.42, 0.18))
		_hitbox("leg_" + s, "knee_" + s, Vector3(0, -0.22, 0), Vector3(0.14, 0.46, 0.16))
		_hitbox("leg_" + s, "ankle_" + s, Vector3(0, -0.05, -0.05), Vector3(0.16, 0.1, 0.3))


# ------------------------------------------------------------------ perception
func eye_pos() -> Vector3:
	return bones.head.global_position + Vector3(0, 0.1, 0)


func head_forward() -> Vector3:
	var f = -bones.head.global_transform.basis.z
	f.y = 0
	return f.normalized()


func _los(from: Vector3, to: Vector3) -> bool:
	var q := PhysicsRayQueryParameters3D.create(from, to, 1)
	q.exclude = [get_rid()]
	return director.space().intersect_ray(q).is_empty()


func _sense(dt: float) -> void:
	var p: Player = Game.player
	if p == null or not p.alive:
		target_visible = false
		return
	var eye := eye_pos()
	var aim := p.get_aim_point()
	var d := eye.distance_to(aim)
	var alert: bool = state in [S.COMBAT, S.SEARCH, S.INVESTIGATE] or director.alert_level > 0.5
	var range_ := SIGHT_LIT if Game.is_lit(aim) else (SIGHT_DARK_IR if alert else SIGHT_DARK)
	if blinded:
		range_ *= 0.35
	var to := (aim - eye)
	var flat := Vector3(to.x, 0, to.z).normalized()
	var ang := head_forward().angle_to(flat)
	# Central cone, close-range peripheral vision, and a proximity sense.
	var in_cone := ang < FOV_HALF or d < 2.2 or (ang < deg_to_rad(80) and d < 10.0)
	var seen := false
	if d < range_ and in_cone:
		seen = _los(eye, aim) or _los(eye, p.get_chest_point())
	target_visible = seen
	if seen:
		var gain := 3.6 * (1.0 - d / range_) + 0.5
		if p.is_crouched():
			gain *= 0.6
		if ang > FOV_HALF * 0.6:
			gain *= 0.5
		if state in [S.COMBAT, S.SEARCH, S.INVESTIGATE] or director.alert_level > 0.5:
			gain *= 3.0
		awareness = minf(awareness + gain * dt, 1.5)
		stimulus = p.global_position
		if awareness >= 1.0:
			last_seen_t = _t
			last_known = p.global_position
			director.report_sighting(self, p.global_position)
			if state != S.COMBAT and state != S.STAGGER:
				_enter_combat()
		elif state == S.PATROL:
			_set_state(S.SUSPICIOUS)
	else:
		if state == S.PATROL or state == S.SUSPICIOUS:
			awareness = maxf(0.0, awareness - 0.15 * dt)


func _on_noise(pos: Vector3, radius: float, source: Node) -> void:
	if state == S.DEAD:
		return
	var d := global_position.distance_to(pos)
	if d > radius:
		return
	var loud := 1.0 - d / radius
	if state == S.COMBAT:
		if source == Game.player and not target_visible:
			last_known = pos
		return
	stimulus = pos
	if radius > 20.0:
		# Gunfire or a breach: go investigate immediately, high suspicion.
		awareness = maxf(awareness, 0.85)
		last_known = pos
		_set_state(S.INVESTIGATE)
	else:
		awareness = minf(awareness + 0.5 * loud + 0.1, 0.95)
		if state == S.PATROL:
			_set_state(S.SUSPICIOUS)
		elif state == S.SUSPICIOUS and awareness > 0.6:
			last_known = pos
			_set_state(S.INVESTIGATE)


func alert_to(pos: Vector3) -> void:
	# Called by the director when a squadmate spots the player.
	if state == S.DEAD or state == S.COMBAT:
		return
	last_known = pos
	stimulus = pos
	awareness = maxf(awareness, 0.9)
	_set_state(S.SEARCH)
	_search_t = 28.0
	_go(pos, RUN)


func _enter_combat() -> void:
	var first := state != S.COMBAT
	_set_state(S.COMBAT)
	if first and not _alerted_once:
		_alerted_once = true
		Sfx.play_3d("robot_alert", eye_pos(), 0.0, 0.03, 8.0)
		director.alert(self, last_known)
	role = director.assign_role(self)


func _set_state(s: int) -> void:
	if state == S.DEAD:
		return
	if s != S.COMBAT:
		_release_token()
		_cover = {}
		_cover_phase = ""
		director.release_cover(self)
	if s == S.SUSPICIOUS:
		_has_move = false
		_wait = 2.5
	if s == S.INVESTIGATE:
		_go(last_known if last_known != Vector3.ZERO else stimulus, RUN * 0.75)
		_search_t = 9.0
	state = s


# ------------------------------------------------------------------ suppression / squad hooks
## Near misses and hits pin the unit: it breaks for cover, delays or cancels a
## charge, aims worse, and learns roughly where the fire came from even when
## the shot was suppressed.
func suppress(from: Vector3, amount: float) -> void:
	if state == S.DEAD:
		return
	var before := suppression
	suppression = minf(1.0, suppression + amount)
	var guess := from + Vector3(randf_range(-2.5, 2.5), 0, randf_range(-2.5, 2.5))
	if state != S.COMBAT:
		last_known = guess
		stimulus = guess
		awareness = maxf(awareness, 0.95)
		if state in [S.PATROL, S.SUSPICIOUS, S.SEARCH]:
			_set_state(S.INVESTIGATE)
	elif not target_visible:
		last_known = guess
	if suppression > 0.55:
		if _attack_t >= 0.0 and _attack_t < WINDUP * 0.5:
			_cancel_attack()
		if role != "cover" and role != "overwatch":
			role = "cover"
			_cover = {}
		if before <= 0.55 and director:
			director.on_suppressed(self)


func push(t: float) -> void:
	if state == S.COMBAT and limp < 0.5:
		_push_t = maxf(_push_t, t)


func set_push_target(pos: Vector3) -> void:
	_push_target = pos
	_go(pos, RUN)


func visited_recently(pt: Vector3) -> bool:
	for v in _visited:
		if v[0].distance_to(pt) < 2.5 and _t - v[1] < 20.0:
			return true
	return false


# ------------------------------------------------------------------ damage
func take_damage(amount: float, zone: String, pos: Vector3, dir: Vector3, normal: Vector3, attacker: Node) -> Dictionary:
	if state == S.DEAD:
		return {"kill": false, "zone": zone}
	var mult: float = ZONE_MULT.get(zone, 1.0)
	var dmg := amount * mult
	hp -= dmg
	_recent_dmg += dmg
	var res := {"kill": false, "zone": zone, "weak": zone in ["head", "core"], "damage": dmg}
	if attacker:
		suppress(attacker.global_position, 0.22)
	if zone == "head":
		Game.stats.head_hits += 1
	if zone == "core":
		Game.stats.core_hits += 1
	Fx.impact(pos, normal, "weak" if zone == "core" or (zone == "head" and not blinded) else "robot")
	# Visible component damage: plates come off as their zone takes punishment.
	_armor_damage(zone, dmg, dir)
	# Zone damage consequences
	if zone_hp.has(zone):
		zone_hp[zone] -= amount
		if zone_hp[zone] <= 0.0:
			_break_zone(zone, pos)
	# Flinch
	var local_dir := global_transform.basis.inverse() * dir
	_flinch += Vector3(-local_dir.z * 0.25, 0, local_dir.x * 0.2) * clampf(dmg / 30.0, 0.3, 1.5)
	if zone == "core" or _recent_dmg > 45.0:
		_stagger(0.45 if zone == "core" else 0.3)
	# Being shot reveals the shooter's direction.
	if state != S.COMBAT and attacker:
		last_known = attacker.global_position
		awareness = 1.0
		_enter_combat()
	if hp <= 0.0:
		_die(dir, zone == "core")
		res.kill = true
		Game.stats.kills += 1
		if zone == "core":
			Game.stats.core_kills += 1
	return res


func _break_zone(zone: String, pos: Vector3) -> void:
	match zone:
		"head":
			if blinded:
				return
			blinded = true
			_pop_plate("head", Vector3(0, 0.3, -1).normalized(), "armor_head_1")
			for m in eye_mats:
				m.emission_energy_multiplier = 0.4
			eye_light.light_energy = 0.15
			Fx.mini_arcs(pos, 5, 0.4)
			Sfx.play_3d("robot_zap", pos, 0.0)
			Fx.smoke(pos)
		"arm_R":
			if arm_damaged:
				return
			arm_damaged = true
			Fx.mini_arcs(pos, 4, 0.35)
			Sfx.play_3d("robot_zap", pos, -2.0)
		"leg_L", "leg_R":
			if limp < 0.5:
				limp = 1.0
				Sfx.play_3d("robot_zap", pos, -2.0)
				Fx.mini_arcs(pos, 3, 0.3)


func _stagger(dur: float) -> void:
	if state == S.DEAD:
		return
	_cancel_attack()
	_stagger_t = maxf(_stagger_t, dur)


func explosion_damage(amount: float, from: Vector3) -> void:
	if state == S.DEAD:
		return
	hp -= amount
	_stagger(0.6)
	if hp <= 0.0:
		_die((global_position - from).normalized(), false)
		Game.stats.kills += 1


func _die(dir: Vector3, overload: bool) -> void:
	_cancel_attack()
	_release_token()
	director.release_cover(self)
	state = S.DEAD
	director.on_bot_died(self)
	_death_t = 0.0
	var local := global_transform.basis.inverse() * dir
	_death_dir = 1.0 if local.z < 0.0 else -1.0  # fall away from the shot
	collision_layer = 0
	collision_mask = 1
	for a in hitboxes:
		a.collision_layer = 0
	for m in eye_mats:
		m.emission_energy_multiplier = 0.0
	eye_light.visible = false
	if hum:
		hum.stop()
	Sfx.play_3d("robot_death", global_position + Vector3.UP, 2.0, 0.05, 8.0)
	for i in (6 if overload else 3):
		var zones := ["core", "torso"] if overload else ["torso", "arm_R", "arm_L", "head", "leg_L", "leg_R"]
		_pop_plate(zones[randi() % zones.size()], dir + Vector3(randf_range(-0.6, 0.6), 0.8, randf_range(-0.6, 0.6)))
	var core_pos: Vector3 = bones.core.global_position
	if overload:
		# Capacitor overload: an electrical burst that hurts everything nearby.
		Fx.overload(core_pos)
		Sfx.play_3d("tesla_shot", core_pos, 4.0, 0.0, 10.0)
		for b in get_tree().get_nodes_in_group("teslabot"):
			if b != self and b.global_position.distance_to(core_pos) < 4.5:
				var f: float = 1.0 - b.global_position.distance_to(core_pos) / 4.5
				b.explosion_damage(120.0 * f + 30.0, core_pos)
		var p: Player = Game.player
		if p and p.global_position.distance_to(core_pos) < 3.5:
			p.take_damage(35.0 * (1.0 - p.global_position.distance_to(core_pos) / 3.5) + 5.0, core_pos)
		Game.emit_noise(core_pos, 30.0, self)
	else:
		Fx.mini_arcs(core_pos, 4, 0.5)
	if core_mat:
		core_mat.emission_energy_multiplier = 0.6


# ------------------------------------------------------------------ attack
func _request_token() -> bool:
	if _has_token:
		return true
	_has_token = director.request_attack_token(self)
	return _has_token


func _release_token() -> void:
	if _has_token and director:
		director.release_attack_token(self)
	_has_token = false


func _start_attack() -> void:
	_attack_t = 0.0
	Sfx.play_3d("tesla_charge", bones.muzzle.global_position, -2.0, 0.05, 5.0)
	_aim_point = Game.player.get_chest_point()


func _cancel_attack() -> void:
	if _attack_t >= 0.0:
		_attack_t = -1.0
		_attack_cd = randf_range(0.6, 1.0)
		charge_light.light_energy = 0.0
		if tip_mat:
			tip_mat.emission_energy_multiplier = 2.0
		_release_token()


func _update_attack(dt: float) -> void:
	var p: Player = Game.player
	var windup := WINDUP * (1.35 if arm_damaged else 1.0)
	_attack_t += dt
	var k := clampf(_attack_t / windup, 0.0, 1.0)
	charge_light.light_energy = k * k * 4.0
	if tip_mat:
		tip_mat.emission_energy_multiplier = 2.0 + k * 14.0
	if randf() < dt * 14.0:
		Fx.arc(bones.muzzle.global_position, bones.muzzle.global_position + Vector3(randf_range(-0.3, 0.3), randf_range(-0.3, 0.3), randf_range(-0.3, 0.3)), 0.01, 0.05, 0, false)
	# Tracking lags behind the target: strafing during the windup can dodge.
	var track := 4.6 if not blinded else 2.0
	_aim_point = _aim_point.lerp(p.get_chest_point(), 1.0 - exp(-track * dt))
	if _attack_t >= windup:
		_fire_arc()
		_attack_t = -1.0
		charge_light.light_energy = 0.0
		if tip_mat:
			tip_mat.emission_energy_multiplier = 2.0
		_attack_cd = randf_range(0.85, 1.45) * (1.25 if arm_damaged else 1.0)
		_release_token()


func _fire_arc() -> void:
	var p: Player = Game.player
	var from: Vector3 = bones.muzzle.global_position
	var d := from.distance_to(_aim_point)
	var err := 0.05 + d * 0.012
	if arm_damaged: err += 0.25
	if blinded: err += 0.45
	err += suppression * 0.35
	var lat := Vector2(p.velocity.x, p.velocity.z).length()
	err += lat * 0.05
	var off := Vector3(randf_range(-1, 1), randf_range(-0.6, 0.8), randf_range(-1, 1)).normalized() * randf() * err
	var target := _aim_point + off
	var dir := (target - from).normalized()
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * 60.0, 1 | (1 << 1) | (1 << 2))
	q.exclude = [get_rid()]
	var hit = director.space().intersect_ray(q)
	var end := from + dir * 60.0
	if hit:
		end = hit.position
		var c: Object = hit.collider
		if c == p:
			p.take_damage(ARC_DAMAGE * randf_range(0.9, 1.1), from)
		elif c.has_method("take_hit"):
			c.take_hit(ARC_DAMAGE, hit.position, dir, hit.normal)
		elif c is Teslabot:
			c.explosion_damage(10.0, from)
		else:
			Fx.impact(hit.position, hit.normal, "metal")
			Fx.decal(hit.position, hit.normal, 0.35, true)
	Fx.arc(from, end, 0.03, 0.16, 3, true)
	Sfx.play_3d("tesla_shot", from, 1.0, 0.06, 9.0)
	Game.emit_noise(from, 18.0, self)
	_flinch += Vector3(0.12, 0, 0)


# ------------------------------------------------------------------ movement
func _go(pos: Vector3, speed: float) -> void:
	_move_target = pos
	_move_speed = speed
	_has_move = true
	agent.target_position = pos


func _stop() -> void:
	_has_move = false


func _physics_process(dt: float) -> void:
	_t += dt
	if state == S.DEAD:
		_animate_death(dt)
		return
	if director == null:
		return
	_recent_dmg = maxf(0.0, _recent_dmg - 60.0 * dt)
	suppression = maxf(0.0, suppression - 0.3 * dt)
	_push_t = maxf(0.0, _push_t - dt)
	_attack_cd -= dt
	_door_cd -= dt
	_sense_t -= dt
	if _sense_t <= 0.0:
		_sense(0.15)
		_sense_t = 0.15
	if _stagger_t > 0.0:
		_stagger_t -= dt
		velocity.x = move_toward(velocity.x, 0, dt * 12)
		velocity.z = move_toward(velocity.z, 0, dt * 12)
	else:
		_think_t -= dt
		if _think_t <= 0.0:
			_think()
			_think_t = 0.35
		if _attack_t >= 0.0:
			_update_attack(dt)
		_steer(dt)
	if not is_on_floor():
		velocity.y -= 12.0 * dt
	else:
		velocity.y = -0.5
	move_and_slide()
	_animate(dt)
	_damage_fx(dt)


func _think() -> void:
	var p: Player = Game.player
	match state:
		S.PATROL:
			if patrol_points.is_empty():
				_stop()
				return
			if not _has_move or agent.is_navigation_finished():
				if _wait > 0.0:
					_wait -= 0.35
					_stop()
				else:
					_patrol_i = (_patrol_i + 1) % patrol_points.size()
					_go(patrol_points[_patrol_i], WALK)
					_wait = randf_range(1.5, 3.5)
		S.SUSPICIOUS:
			_stop()
			_wait -= 0.35
			if awareness > 0.65:
				last_known = stimulus
				_set_state(S.INVESTIGATE)
			elif _wait <= 0.0 and awareness < 0.3:
				_set_state(S.PATROL)
		S.INVESTIGATE:
			_search_t -= 0.35
			if agent.is_navigation_finished() or _search_t < 0.0:
				_set_state(S.SEARCH)
				_search_t = 8.0
		S.SEARCH:
			_search_t -= 0.35
			if _search_t <= 0.0 and director.since_seen() > 25.0:
				awareness = 0.3
				_set_state(S.PATROL)
			elif _try_entry(last_known):
				pass
			elif not _has_move or agent.is_navigation_finished():
				# Pause and scan at each point, then move to the next distinct one.
				_scan_t -= 0.35
				if _scan_t <= 0.0:
					_visited.append([global_position, _t])
					if _visited.size() > 12:
						_visited.pop_front()
					_go(director.search_point(self), WALK * 1.6)
					_scan_t = randf_range(1.0, 2.0)
				else:
					_stop()
		S.COMBAT:
			_think_combat(p)


func _think_combat(p: Player) -> void:
	if p == null or not p.alive:
		_set_state(S.SEARCH)
		return
	var since := _t - last_seen_t
	if target_visible:
		last_known = p.global_position
	if since > 4.0:
		# Lost contact: search where the target was last known.
		_set_state(S.SEARCH)
		_search_t = 14.0
		_go(director.shared_last_known(last_known), RUN * 0.8)
		return
	var d := global_position.distance_to(p.global_position)
	# Attack decision (suppressed units hold fire unless the target is close)
	var pinned := suppression > 0.7 and d > 6.0
	if target_visible and not pinned and _attack_t < 0.0 and _attack_cd <= 0.0 and d < 30.0:
		if _request_token():
			_start_attack()
			if d > 5.0 and _push_t <= 0.0:
				_stop()
			return
	if _attack_t >= 0.0:
		return
	# Room entry when the target is in an adjacent room and out of sight
	if not target_visible and _try_entry(director.shared_last_known(last_known)):
		return
	if not _entry.is_empty():
		director.entry_done(_entry.door, self)
		_entry = {}
	# Reload/opening push: close the distance hard.
	if _push_t > 0.0:
		_go(director.snap(p.global_position if target_visible else director.predicted_position()), RUN)
		return
	match role:
		"flanker":
			if not _has_move or agent.is_navigation_finished() or randf() < 0.12:
				_go(director.flank_position(self, last_known), RUN)
			if d < 6.0 and target_visible:
				_stop()
		"cover":
			_think_cover(p)
		"overwatch":
			# Hold the angle on the last known position; reposition only if blind to it.
			if not director._ray_clear(eye_pos(), last_known + Vector3.UP * 1.2):
				if not _has_move or agent.is_navigation_finished():
					var c: Dictionary = director.find_cover(self, last_known + Vector3.UP * 1.4)
					if not c.is_empty():
						_cover = c
						_go(c.peek, RUN)
					else:
						_go(director.snap(last_known.lerp(global_position, 0.6)), WALK * 1.5)
			else:
				_stop()
		"pusher":
			if agent.is_navigation_finished() or not _has_move:
				# Arrived at the bearing: sweep into the predicted position.
				_go(director.predicted_position(), RUN * 0.8)
		_:
			# Assault: hold a preferred band; close in when the target hides.
			var pref := 9.0
			if not target_visible or d > 16.0:
				_go(director.snap(director.predicted_position()), RUN)
			elif d < 4.5:
				var away := (global_position - p.global_position).normalized()
				_go(director.snap(global_position + away * 3.0 + away.cross(Vector3.UP) * randf_range(-2, 2)), WALK * 1.4)
			elif d > pref + 3.0 or randf() < 0.3:
				# Strafe across the target's line instead of standing in the open.
				var side := (p.global_position - global_position).normalized().cross(Vector3.UP) * randf_range(-3.5, 3.5)
				_go(director.snap(global_position + side + (p.global_position - global_position).normalized() * 1.5), WALK * 1.6)


## Stack on the near side of a doorway into the target's room, wait for a
## partner (or briefly), open the door, then enter on crossing lines.
func _try_entry(target: Vector3) -> bool:
	var plan: Dictionary = director.plan_entry(self, target)
	if plan.is_empty():
		if not _entry.is_empty():
			director.entry_done(_entry.door, self)
			_entry = {}
		return false
	if _entry.is_empty() or _entry.door != plan.door:
		_entry = plan
		_entry.phase = "moving"
		_go(plan.stack, RUN * 0.9)
		return true
	_entry.t = _entry.get("t", 0.0) + 0.35
	if (_entry.phase == "moving" and _entry.t > 6.0) or (_entry.phase == "entering" and _entry.t > 4.5):
		director.entry_done(_entry.door, self)
		_entry = {}
		_visited.append([global_position, _t])
		return false
	match _entry.phase:
		"moving":
			if agent.is_navigation_finished() or global_position.distance_to(_entry.stack) < 0.9:
				_entry.phase = "stacked"
				_stop()
		"stacked":
			_stop()
			if director.entry_go(_entry.door, self):
				var dn: Node = director.door_node(_entry.door)
				if dn and not dn.is_open():
					dn.bot_open(self)
				_entry.phase = "entering"
				_entry.t = 0.0
				_go(_entry.inside, RUN)
		"entering":
			if agent.is_navigation_finished() or global_position.distance_to(_entry.inside) < 1.0:
				director.entry_done(_entry.door, self)
				_entry = {}
				_visited.append([global_position, _t])
				return false
	return true


func _think_cover(p: Player) -> void:
	if _cover.is_empty():
		_cover = director.find_cover(self, p.get_chest_point())
		if _cover.is_empty():
			role = "assault"
			return
		_cover_phase = "hide"
		_go(_cover.pos, RUN)
		return
	if _cover_phase == "hide":
		if agent.is_navigation_finished():
			_cover_t += 0.35
			if _cover_t > randf_range(0.8, 2.0) + suppression * 2.5 and _attack_cd <= 0.2 and suppression < 0.6:
				_cover_phase = "peek"
				_cover_t = 0.0
				_go(_cover.peek, WALK * 1.6)
	elif _cover_phase == "peek":
		_cover_t += 0.35
		if _cover_t > 3.0 or (_attack_t < 0.0 and _attack_cd > 0.8 and _cover_t > 1.0):
			_cover_phase = "hide"
			_cover_t = 0.0
			_go(_cover.pos, WALK * 1.6)
	# Re-evaluate if the cover no longer protects.
	if randf() < 0.08:
		director.release_cover(self)
		_cover = {}


func _steer(dt: float) -> void:
	var desired := Vector3.ZERO
	var spd := _move_speed * (1.0 - 0.45 * limp)
	if _attack_t >= 0.0:
		spd *= 0.35
	if _has_move and not agent.is_navigation_finished():
		var nxt := agent.get_next_path_position()
		var to := nxt - global_position
		to.y = 0
		if to.length() > 0.05:
			desired = to.normalized() * spd
		_try_open_doors(desired)
	# Separation from squadmates
	for b in director.bots:
		if b == self or b.state == S.DEAD:
			continue
		var off: Vector3 = global_position - b.global_position
		off.y = 0
		var l := off.length()
		if l < 1.4 and l > 0.01:
			desired += off / l * (1.4 - l) * 2.0
	var hv := Vector3(velocity.x, 0, velocity.z)
	hv = hv.move_toward(desired, 9.0 * dt)
	velocity.x = hv.x
	velocity.z = hv.z
	# Facing: toward target in combat, else toward motion
	var face := _face_dir
	var p: Player = Game.player
	if state == S.COMBAT and p and (target_visible or _attack_t >= 0.0):
		face = (p.global_position - global_position)
	elif not _entry.is_empty() and _entry.phase == "stacked":
		face = _entry.look - global_position
	elif state == S.COMBAT and role == "overwatch":
		face = last_known - global_position
	elif state == S.SUSPICIOUS or (state == S.SEARCH and not _has_move):
		face = stimulus - global_position
	elif hv.length() > 0.3:
		face = hv
	face.y = 0
	if face.length() > 0.01:
		_face_dir = _face_dir.slerp(face.normalized(), 1.0 - exp(-4.0 * dt)).normalized() if _face_dir.dot(face.normalized()) > -0.99 else face.normalized()
		look_at(global_position + _face_dir, Vector3.UP)
	# Stuck detection: re-path
	if _has_move and hv.length() > 0.5:
		if global_position.distance_to(_last_pos) < 0.02:
			_stuck_t += dt
			if _stuck_t > 1.2:
				_stuck_t = 0.0
				_go(director.snap(global_position + Vector3(randf_range(-2, 2), 0, randf_range(-2, 2))), _move_speed)
		else:
			_stuck_t = 0.0
	_last_pos = global_position


func _try_open_doors(desired: Vector3) -> void:
	if _door_cd > 0.0 or desired.length() < 0.1:
		return
	var from := global_position + Vector3.UP * 1.0
	var q := PhysicsRayQueryParameters3D.create(from, from + desired.normalized() * 1.6, 1)
	q.exclude = [get_rid()]
	var hit = director.space().intersect_ray(q)
	if hit:
		var c: Node = hit.collider
		while c and not c.has_method("bot_open"):
			c = c.get_parent()
			if c is Window:
				c = null
		if c:
			c.bot_open(self)
			_door_cd = 1.5


# ------------------------------------------------------------------ animation
func _animate(dt: float) -> void:
	var hv := Vector3(velocity.x, 0, velocity.z)
	var spd := hv.length()
	var fwd_speed := hv.dot(-global_transform.basis.z)
	_gait_amp = lerpf(_gait_amp, clampf(spd / 2.2, 0.0, 1.0), 1.0 - exp(-6.0 * dt))
	_phase += dt * (2.0 + spd * 2.1) * (1.0 if _gait_amp > 0.05 else 0.0)
	var a := _gait_amp
	var dirsign := 1.0 if fwd_speed >= -0.2 else -1.0
	var limp_l := 1.0 - 0.5 * limp
	var sL := sin(_phase) * dirsign
	var sR := sin(_phase + PI) * dirsign
	# Crouch behind cover while hiding (hitboxes follow the bones).
	var want_crouch := 1.0 if (state == S.COMBAT and role == "cover" and _cover_phase == "hide" and spd < 0.6) else 0.0
	_crouch_b = move_toward(_crouch_b, want_crouch, dt * 3.0)
	var c := _crouch_b * _crouch_b * (3.0 - 2.0 * _crouch_b)
	_bone_rot("hip_L", Vector3(sL * 0.5 * a * limp_l + 1.0 * c, 0, 0))
	_bone_rot("hip_R", Vector3(sR * 0.5 * a + 0.9 * c, 0, 0))
	_bone_rot("knee_L", Vector3(-maxf(0.0, cos(_phase)) * 0.8 * a - 0.08 - 1.7 * c, 0, 0))
	_bone_rot("knee_R", Vector3(-maxf(0.0, cos(_phase + PI)) * 0.8 * a - 0.08 - 1.5 * c, 0, 0))
	_bone_rot("ankle_L", Vector3(-sL * 0.2 * a + 0.7 * c, 0, 0))
	_bone_rot("ankle_R", Vector3(-sR * 0.2 * a + 0.6 * c, 0, 0))
	# Footstep sounds on gait extremes
	var step_phase := fposmod(_phase, PI)
	if a > 0.25 and step_phase < _last_step_phase:
		Sfx.play_3d("robot_step", global_position, -6.0 + a * 4.0, 0.08, 4.0)
		_step_side = 1 - _step_side
	_last_step_phase = step_phase
	# Pelvis bob, sway and limp hitch
	var pel: Node3D = bones.pelvis
	var bob := absf(sin(_phase)) * 0.05 * a
	pel.position = _rest.pelvis.origin + Vector3(sin(_phase) * 0.025 * a, -bob - 0.03 * limp * absf(sin(_phase * 0.5)) - 0.32 * c, 0.07 * c)
	# Upper body: twist towards the aim target independently of the legs.
	var aim_target := Vector3.ZERO
	var aiming := false
	var p: Player = Game.player
	if p and state == S.COMBAT and (target_visible or _attack_t >= 0.0):
		aiming = true
		aim_target = _aim_point if _attack_t >= 0.0 else p.get_chest_point()
	_aim_blend = move_toward(_aim_blend, 1.0 if aiming or state == S.COMBAT else 0.0, dt * 3.0)
	var torso_yaw := 0.0
	var aim_pitch := 0.0
	if aiming:
		var local = global_transform.basis.inverse() * (aim_target - bones.torso.global_position)
		torso_yaw = clampf(atan2(-local.x, -local.z), -1.0, 1.0)
		aim_pitch = atan2(local.y + 0.3, Vector2(local.x, local.z).length())
	_flinch = _flinch.lerp(Vector3.ZERO, 1.0 - exp(-7.0 * dt))
	var idle := sin(_t * 1.3) * 0.02
	var t_rot := Vector3(0.08 * a + _flinch.x + idle, torso_yaw * _aim_blend, sin(_phase) * 0.04 * a + _flinch.z)
	if _stagger_t > 0.0:
		t_rot += Vector3(-0.25, 0, sin(_t * 30.0) * 0.06)
	_bone_rot("torso", t_rot)
	# Head scanning when idle / searching; tracking when engaged.
	var head_yaw := 0.0
	var head_pitch := 0.0
	if state in [S.PATROL, S.SEARCH, S.SUSPICIOUS, S.INVESTIGATE]:
		head_yaw = sin(_t * (0.6 if state == S.PATROL else 1.4)) * (0.5 if state == S.PATROL else 0.8)
		if state == S.SUSPICIOUS:
			var ls := global_transform.basis.inverse() * (stimulus - global_position)
			head_yaw = clampf(atan2(-ls.x, -ls.z), -0.9, 0.9)
	elif aiming:
		head_pitch = clampf(aim_pitch * 0.6, -0.5, 0.4)
	_bone_rot("head", Vector3(head_pitch, head_yaw, 0))
	# Arms: emitter raised to aim in combat, lowered otherwise.
	var arm_pitch := lerpf(-0.75, clampf(aim_pitch, -0.9, 0.9), _aim_blend)
	if _attack_t >= 0.0:
		arm_pitch += sin(_t * 60.0) * 0.01
	_bone_rot("shoulder_R", Vector3(arm_pitch + _flinch.x * 0.5, 0, 0))
	_bone_rot("shoulder_L", Vector3(lerpf(-0.6, -0.3, _aim_blend) + sin(_phase) * 0.15 * a, 0, 0))
	_bone_rot("elbow_L", Vector3(sin(_t * 0.9) * 0.05, 0, 0))
	# Eye brightness follows awareness (readable alert state).
	if not blinded:
		var e := 5.0 + 10.0 * clampf(awareness, 0.0, 1.0)
		if state == S.COMBAT:
			e = 16.0
		for m in eye_mats:
			m.emission_energy_multiplier = e
		eye_light.light_energy = 0.4 + clampf(awareness, 0.0, 1.0) * 0.9
	# Servo whine when turning quickly or starting to move
	_servo_cd -= dt
	if _servo_cd <= 0.0 and absf(torso_yaw) > 0.5 and _aim_blend > 0.5:
		Sfx.play_3d("robot_servo", bones.torso.global_position, -10.0, 0.15, 3.0)
		_servo_cd = 1.5


func _bone_rot(n: String, r: Vector3) -> void:
	var b: Node3D = bones.get(n)
	if b == null:
		return
	var rest: Transform3D = _rest[n]
	b.transform = Transform3D(rest.basis * Basis.from_euler(r), b.position if n == "pelvis" else rest.origin)


func _animate_death(dt: float) -> void:
	_death_t += dt
	var t := _death_t
	var k1 := clampf(t / 0.45, 0.0, 1.0)
	var k2 := clampf((t - 0.35) / 0.65, 0.0, 1.0)
	k2 = k2 * k2
	_bone_rot("knee_L", Vector3(-1.3 * k1, 0, 0))
	_bone_rot("knee_R", Vector3(-1.1 * k1, 0, 0))
	_bone_rot("hip_L", Vector3(0.9 * k1, 0, 0))
	_bone_rot("hip_R", Vector3(0.7 * k1, 0, 0.1))
	_bone_rot("torso", Vector3(0.4 * k1 * _death_dir, 0, 0.1))
	_bone_rot("head", Vector3(0.5 * k1, 0.3, 0))
	_bone_rot("shoulder_R", Vector3(-1.2 * k1, 0, 0.2))
	_bone_rot("shoulder_L", Vector3(-1.0 * k1, 0, -0.2))
	var pel: Node3D = bones.pelvis
	var base: Transform3D = _rest.pelvis
	var drop := lerpf(0.0, -0.55, k1)
	var fall := Basis.from_euler(Vector3(-1.35 * k2 * _death_dir, 0, 0.15 * k2))
	pel.transform = Transform3D(base.basis * fall, base.origin + Vector3(0, drop - 0.25 * k2, 0.5 * k2 * _death_dir))
	if not is_on_floor():
		velocity.y -= 12.0 * dt
	velocity.x = move_toward(velocity.x, 0, dt * 6)
	velocity.z = move_toward(velocity.z, 0, dt * 6)
	move_and_slide()
	# Residual sparks from the wreck for a while
	if t < 20.0:
		_spark_t -= dt
		if _spark_t <= 0.0:
			_spark_t = randf_range(1.2, 3.5)
			var c: Vector3 = bones.core.global_position
			Fx.mini_arcs(c, 2, 0.3)
			Sfx.play_3d("robot_zap", c, -10.0, 0.2, 3.0)
	if core_mat:
		core_mat.emission_energy_multiplier = maxf(0.0, 0.6 - t * 0.05) * (0.5 + 0.5 * sin(t * 23.0))


func _damage_fx(dt: float) -> void:
	var frac := hp / MAX_HP
	_spark_t -= dt
	if _spark_t > 0.0:
		return
	if frac < 0.5 or blinded or arm_damaged or limp > 0.0:
		_spark_t = randf_range(0.4, 1.4) * (0.5 + frac)
		var where: Vector3 = bones.torso.global_position + Vector3(0, 0.4, 0)
		if blinded and randf() < 0.5:
			where = bones.head.global_position + Vector3(0, 0.1, 0)
		elif arm_damaged and randf() < 0.5:
			where = bones.elbow_R.global_position
		elif limp > 0.0 and randf() < 0.5:
			where = bones.knee_L.global_position
		Fx.mini_arcs(where, 2, 0.25)
		if randf() < 0.4:
			Sfx.play_3d("robot_zap", where, -12.0, 0.2, 3.0)
		if frac < 0.35 and randf() < 0.4:
			Fx.smoke(where)
		if blinded:
			for m in eye_mats:
				m.emission_energy_multiplier = randf_range(0.0, 2.0)
	else:
		_spark_t = 0.5



# ------------------------------------------------------------------ armour plates
## armor_<zone>_<n> nodes from the M2 model; each zone sheds plates in order
## as accumulated damage crosses thresholds, revealing internal_* machinery.
const ARMOR_BUDGET := {"head": 60.0, "torso": 170.0, "core": 50.0, "arm_R": 80.0, "arm_L": 70.0, "leg_L": 85.0, "leg_R": 85.0}
var _armor := {}       # zone -> Array[Node3D] (remaining)
var _armor_n := {}     # zone -> initial count
var _armor_dmg := {}   # zone -> accumulated damage


func _collect_armor() -> void:
	for n in model.find_children("armor_*", "Node3D", true, false):
		var parts: PackedStringArray = String(n.name).split("_")
		if parts.size() < 3:
			continue
		var zone := parts[1] if parts.size() == 3 else parts[1] + "_" + parts[2]
		if not _armor.has(zone):
			_armor[zone] = []
		# Only top-level armour pieces (not meshes nested inside another plate)
		if n.get_parent() and String(n.get_parent().name).begins_with("armor_"):
			continue
		_armor[zone].append(n)
	for z in _armor:
		_armor_n[z] = _armor[z].size()
		_armor_dmg[z] = 0.0


func _armor_damage(zone: String, dmg: float, dir: Vector3) -> void:
	var z := zone
	if z == "pelvis":
		z = "torso"
	if not _armor.has(z) or _armor[z].is_empty():
		return
	_armor_dmg[z] += dmg
	var n: int = _armor_n[z]
	var step: float = ARMOR_BUDGET.get(z, 80.0) / float(n + 1)
	var should_be_gone := int(_armor_dmg[z] / step)
	while n - _armor[z].size() < should_be_gone and not _armor[z].is_empty():
		_pop_plate(z, dir + Vector3(0, 0.5, 0))


func _pop_plate(zone: String, dir: Vector3, preferred := "") -> void:
	if not _armor.has(zone) or _armor[zone].is_empty():
		return
	var plate: Node3D = null
	for p in _armor[zone]:
		if preferred != "" and String(p.name).begins_with(preferred):
			plate = p
	if plate == null:
		plate = _armor[zone][randi() % _armor[zone].size()]
	_armor[zone].erase(plate)
	if not is_instance_valid(plate) or not plate.is_visible_in_tree():
		return
	var xf := plate.global_transform
	var rb := RigidBody3D.new()
	rb.collision_layer = 0
	rb.collision_mask = 1
	rb.mass = 4.0
	var piece: Node3D = plate.duplicate()
	plate.visible = false
	get_tree().current_scene.add_child(rb)
	rb.global_transform = xf
	rb.add_child(piece)
	piece.transform = Transform3D.IDENTITY
	var aabb := AABB()
	var first := true
	for mi in piece.find_children("*", "MeshInstance3D", true, true) + ([piece] if piece is MeshInstance3D else []):
		var a: AABB = (mi as MeshInstance3D).get_aabb()
		if mi != piece:
			a = (mi as Node3D).transform * a
		aabb = a if first else aabb.merge(a)
		first = false
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = aabb.size.max(Vector3.ONE * 0.04)
	cs.shape = bs
	cs.position = aabb.get_center()
	rb.add_child(cs)
	var d := dir.normalized() if dir.length() > 0.01 else Vector3.UP
	rb.linear_velocity = velocity + d * randf_range(2.0, 4.0) + Vector3.UP * randf_range(1.0, 2.5)
	rb.angular_velocity = Vector3(randf_range(-8, 8), randf_range(-8, 8), randf_range(-8, 8))
	Fx.mini_arcs(xf.origin, 2, 0.25)
	Sfx.play_3d("impact_metal", xf.origin, -2.0, 0.1, 4.0)
	# Debris settles, then is cleaned up.
	var t := rb.create_tween()
	t.tween_interval(6.0)
	t.tween_callback(func(): if is_instance_valid(rb): rb.freeze = true)
	t.tween_interval(24.0)
	t.tween_callback(rb.queue_free)
