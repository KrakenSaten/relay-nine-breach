class_name Weapon
extends Node3D
## First-person weapon: viewmodel presentation, attachments, firing, reloads.
## Lives under the player's camera; the owning Player supplies aim state.

signal fired
signal ammo_changed

var id := ""
var def: Dictionary
var stats := {}
var loadout := {}
var ammo := 0
var reserve := 0
var auto_mode := true

var player: Node   # Player
var model: Node3D
var muzzle: Node3D
var eject: Node3D
var mag_node: Node3D
var mag_rest := Transform3D.IDENTITY
var eye_local := Vector3.ZERO

var ads := 0.0
var _cooldown := 0.0
var _reload_t := -1.0
var _reload_len := 1.0
var _reload_empty := false
var _reload_loaded := false
var _reload_events := {}
var _kick := 0.0          # spring offset backwards
var _kick_v := 0.0
var _kick_rot := Vector3.ZERO
var _sway := Vector2.ZERO
var _sway_v := Vector2.ZERO
var _bob_t := 0.0
var _flash: Node3D
var _flash_light: OmniLight3D
var _flash_t := 0.0
var _shells: Array = []
var _shell_mesh: Mesh
var _equip := 1.0          # 0 = lowered, 1 = raised
var _equip_target := 1.0
var _trigger_held_last := false
var _shots_in_burst := 0
var _clip_pull := 0.0
var _strafe := 0.0
var _vert := 0.0
## World-space point the support hand reaches for (interaction), or null.
var reach_point = null
var _reach := 0.0
## M2: mechanical parts and hand choreography
var _cycle := 0.0              # bolt/slide travel 0..1 after a shot
var _parts := {}               # name -> [Node3D, rest Transform3D]

const ATT_SCENE := "res://assets/models/attachments.glb"
var _att_root: Node3D   # attachment templates (out of tree; freed in _exit_tree)


func setup(weapon_id: String, p: Node, att: Dictionary) -> void:
	id = weapon_id
	player = p
	def = WeaponDefs.WEAPONS[id]
	auto_mode = def.auto
	var scene: PackedScene = load(def.model)
	model = scene.instantiate()
	add_child(model)
	MatLib.remap_scene(model)
	for mi in model.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.layers = 1 << 1  # viewmodel layer (excluded from reflection probes / decals)
	for part in ["bolt", "slide", "charging_handle", "trigger"]:
		var pn := _find_prefixed(model, part)
		if pn:
			_parts[part] = [pn, pn.transform]
	muzzle = model.find_child("sock_muzzle", true, false)
	eject = model.find_child("sock_eject", true, false)
	_build_flash()
	_shell_mesh = CylinderMesh.new()
	_shell_mesh.top_radius = 0.0032
	_shell_mesh.bottom_radius = 0.0032
	_shell_mesh.height = 0.024
	_shell_mesh.radial_segments = 8
	_shell_mesh.material = MatLib.flat(Color(0.75, 0.55, 0.25), 1.0, 0.3)
	apply_loadout(att)
	ammo = stats.mag
	reserve = def.reserve


func apply_loadout(att: Dictionary) -> void:
	loadout = att.duplicate()
	_sock_cache.clear()
	# Remove old attachment instances
	for c in model.find_children("att_*", "Node3D", true, false):
		c.queue_free()
	if _att_root == null:
		_att_root = (load(ATT_SCENE) as PackedScene).instantiate()
	mag_node = null
	var optic_eye: Node3D = null
	for slot in def.slots:
		var att_id: String = loadout.get(slot, "")
		var sock: Node3D = model.find_child("sock_" + slot, true, false)
		if sock == null or not _att_root.has_node(att_id):
			continue
		var src: Node3D = _att_root.get_node(att_id)
		var inst: Node3D = src.duplicate()
		inst.name = "att_" + att_id
		inst.transform = Transform3D.IDENTITY
		# Attachment children were authored relative to their empty; keep offsets.
		sock.add_child(inst)
		MatLib.remap_scene(inst)
		for mi in inst.find_children("*", "MeshInstance3D", true, false):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.layers = 1 << 1
		if slot == "optic":
			optic_eye = _find_prefixed(inst, "eye")
			_add_reticle(inst, att_id)
		if slot == "mag":
			mag_node = inst
			mag_rest = inst.transform
		if slot == "muzzle" and att_id == "suppressor":
			# hide flash hider under the can
			var fh := model.find_child("flash_hider", true, false)
			if fh: fh.visible = false
		elif slot == "muzzle":
			var fh2 := model.find_child("flash_hider", true, false)
			if fh2: fh2.visible = true
	# Raise iron sights only when no optic is fitted.
	var has_optic = loadout.get("optic", "iron") != "iron" and def.slots.has("optic")
	for n in ["front_sight_folded", "rear_sight_folded"]:
		var s: Node3D = model.find_child(n, true, false)
		if s:
			s.scale = Vector3(1, 1, 1) if has_optic else Vector3(1, 3.2, 1)
	for n in ["front_sight", "rear_sight"]:
		var bs: Node3D = model.find_child(n, true, false)
		if bs and id == "rifle":
			if not bs.has_meta("rest"):
				bs.set_meta("rest", bs.transform)
			var rest: Transform3D = bs.get_meta("rest")
			# Modelled upright; fold flat when an optic is fitted.
			# Rear folds forward (-90 deg about X), front folds back (+90 deg).
			var fold := (-PI / 2 if n == "rear_sight" else PI / 2) if has_optic else 0.0
			bs.transform = rest * Transform3D(Basis(Vector3.RIGHT, fold), Vector3.ZERO)
	if mag_node == null:
		var pm := _find_prefixed(model, "mag")
		if pm and not pm.name.begins_with("mag_"):
			mag_node = pm
			mag_rest = pm.transform
	compute_stats()
	# ADS eye point in weapon-root space
	var iron: Node3D = model.find_child("sock_iron", true, false)
	if optic_eye:
		eye_local = _to_root(optic_eye)
	elif iron:
		eye_local = _to_root(iron) + Vector3(0, 0.012 if has_optic == false and id == "rifle" else 0.0, 0.26)
	if muzzle and loadout.get("muzzle", "") == "suppressor":
		_flash.position = Vector3(0, 0, -0.18)
	elif _flash:
		_flash.position = Vector3.ZERO
	ammo = mini(ammo, stats.mag) if ammo > 0 else ammo
	ammo_changed.emit()


## Blender suffixes duplicate names (eye.001 -> eye_001); match by prefix.
func _find_prefixed(root: Node, prefix: String) -> Node3D:
	for c in root.find_children(prefix + "*", "Node3D", true, false):
		return c
	return null


func _to_root(n: Node3D) -> Vector3:
	var t := Transform3D.IDENTITY
	var cur: Node = n
	while cur != null and cur != self:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t.origin


func _add_reticle(optic: Node3D, att_id: String) -> void:
	var lens: Node3D = _find_prefixed(optic, "lens")
	if lens == null:
		lens = _find_prefixed(optic, "obj_glass")
	if lens == null:
		return
	# A small emissive dot in the lens plane. With the eye on-axis it reads as a
	# dot at the aim point; prism uses a chevron-style tiny bar pair.
	var q := QuadMesh.new()
	q.size = Vector2(0.0028, 0.0028) if att_id == "optic_reflex" else Vector2(0.0022, 0.0022)
	var g := Gradient.new()
	g.colors = PackedColorArray([Color(1, 0.25, 0.12, 1), Color(1, 0.15, 0.05, 0.9), Color(1, 0.1, 0.0, 0)])
	g.offsets = PackedFloat32Array([0.0, 0.45, 1.0])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.albedo_texture = gt
	m.albedo_color = Color(2.0, 1.0, 1.0)
	m.no_depth_test = true
	m.render_priority = 10
	q.material = m
	var mi := MeshInstance3D.new()
	mi.mesh = q
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.name = "reticle"
	optic.add_child(mi)
	var eye: Node3D = _find_prefixed(optic, "eye")
	mi.position = Vector3(eye.position.x, eye.position.y, lens.position.z + 0.003)


func compute_stats() -> void:
	stats = {
		"damage": def.damage, "rpm": def.rpm, "mag": def.mag, "reload": def.reload, "reload_empty": def.reload_empty,
		"recoil_v": def.recoil_v, "recoil_h": def.recoil_h, "recoil_recover": def.recoil_recover,
		"spread_hip": def.spread_hip, "spread_ads": def.spread_ads, "spread_move": def.spread_move,
		"ads_time": def.ads_time, "move_mult": def.move_mult, "noise": def.noise, "ads_fov": 0.86,
		"ads_sens": 1.0, "ads_move_mult": 1.0, "suppressed": false, "flash_mult": 1.0,
	}
	for slot in def.slots:
		var a: Dictionary = WeaponDefs.ATTACHMENTS.get(loadout.get(slot, ""), {})
		for k in a:
			if k in ["label", "desc"]:
				continue
			if k.ends_with("_mult") and stats.has(k.trim_suffix("_mult")):
				stats[k.trim_suffix("_mult")] *= a[k]
			elif k == "move_mult_mult":
				stats.move_mult *= a[k]
			elif k == "noise_mult":
				stats.noise *= a[k]
			else:
				stats[k] = a[k]
	if id == "pistol":
		stats.ads_fov = 0.9


func _build_flash() -> void:
	_flash = Node3D.new()
	var parent: Node3D = muzzle if muzzle else model
	parent.add_child(_flash)
	var g := Gradient.new()
	g.colors = PackedColorArray([Color(1, 0.95, 0.8, 1), Color(1, 0.6, 0.2, 0.8), Color(1, 0.35, 0.05, 0)])
	g.offsets = PackedFloat32Array([0.0, 0.25, 1.0])
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.albedo_texture = _flash_texture(randi())
	m.albedo_color = Color(1.6, 1.3, 1.0)
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	_flash_mat = m
	# Side-on petals (long) and a front-facing star
	for i in 3:
		var q := QuadMesh.new()
		q.size = Vector2(0.07, 0.2)
		q.material = m
		var mi := MeshInstance3D.new()
		mi.mesh = q
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.rotation = Vector3(PI / 2, 0, i * PI / 3)
		mi.position = Vector3(0, 0, -0.09)
		_flash.add_child(mi)
	var front := QuadMesh.new()
	front.size = Vector2(0.13, 0.13)
	front.material = m
	var fm := MeshInstance3D.new()
	fm.mesh = front
	fm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	fm.position = Vector3(0, 0, -0.02)
	_flash.add_child(fm)
	_flash.visible = false
	_flash_light = OmniLight3D.new()
	_flash_light.light_color = Color(1.0, 0.72, 0.4)
	_flash_light.omni_range = 7.0
	_flash_light.light_energy = 0.0
	_flash_light.shadow_enabled = false
	_flash_light.light_volumetric_fog_energy = 3.0
	parent.add_child(_flash_light)
	_flash_light.position = Vector3(0, 0, -0.15)


# ---------------------------------------------------------------- state
func is_reloading() -> bool:
	return _reload_t >= 0.0


func can_fire() -> bool:
	return _cooldown <= 0.0 and not is_reloading() and _equip > 0.95


func ads_fov() -> float:
	return stats.ads_fov


func set_equipped(on: bool) -> void:
	_equip_target = 1.0 if on else 0.0
	if not on:
		cancel_reload()


func is_lowered() -> bool:
	return _equip < 0.05


func start_reload() -> void:
	if is_reloading() or reserve <= 0 or _equip < 0.9:
		return
	if ammo >= stats.mag:
		return
	_reload_empty = ammo == 0
	var mult: float = stats.reload / def.reload
	_reload_len = (def.reload_empty if _reload_empty else def.reload) * mult
	_reload_t = 0.0
	_reload_loaded = false
	_reload_events = {}
	# Reloading is audible to nearby units, who use it as an opening.
	Game.emit_noise(player.global_position, 8.0, player)
	Game.reload_heard.emit(player.global_position)


func cancel_reload() -> void:
	if is_reloading() and not _reload_loaded:
		_reload_t = -1.0
		if mag_node:
			mag_node.transform = mag_rest
			mag_node.visible = true


func _finish_load() -> void:
	var chamber := 1 if not _reload_empty else 0
	var need = stats.mag + chamber - ammo
	var take := mini(need, reserve)
	ammo += take
	reserve -= take
	_reload_loaded = true
	ammo_changed.emit()


func toggle_fire_mode() -> void:
	if def.auto:
		auto_mode = not auto_mode
		_play_first(["selector_switch", "ui_click"], -6.0)
		ammo_changed.emit()


## Called every physics frame by the player while the trigger is held.
func trigger(held: bool, delta: float) -> void:
	_cooldown -= delta
	var pressed := held and not _trigger_held_last
	_trigger_held_last = held
	if not held:
		_shots_in_burst = 0
		return
	if not can_fire():
		return
	if not auto_mode and not pressed:
		return
	if ammo <= 0:
		if pressed:
			Sfx.play("dry_fire", -4.0)
			start_reload()
		_cooldown = 0.25
		return
	_shoot()
	_cooldown = 60.0 / stats.rpm


func _shoot() -> void:
	ammo -= 1
	_shots_in_burst += 1
	Game.stats.shots += 1
	var cam: Camera3D = player.camera
	var spread: float = lerpf(stats.spread_hip, stats.spread_ads, ads)
	spread += player.movement_spread() * stats.spread_move * (1.0 - ads * 0.7)
	if _shots_in_burst > 3:
		spread += minf(_shots_in_burst - 3, 8) * 0.12 * (1.0 - ads * 0.6)
	var dir := -cam.global_transform.basis.z
	var r := sqrt(randf()) * deg_to_rad(spread) * 0.5
	var a := randf() * TAU
	dir = dir.rotated(cam.global_transform.basis.x, sin(a) * r).rotated(cam.global_transform.basis.y, cos(a) * r).normalized()
	var from := cam.global_position
	var to := from + dir * 200.0
	var q := PhysicsRayQueryParameters3D.create(from, to, 1 | (1 << 3))
	q.collide_with_areas = true
	q.collide_with_bodies = true
	q.exclude = [player.get_rid()]
	var hit = player.get_world_3d().direct_space_state.intersect_ray(q)
	var muzzle_pos := muzzle.global_position if muzzle else global_position
	var end_pt: Vector3 = hit.position if hit else to
	_suppress_near(from, end_pt, hit.get("collider", null) if hit else null)
	if hit:
		var col: Object = hit.collider
		var dist := from.distance_to(hit.position)
		var dmg: float = stats.damage
		if dist > def.falloff_start:
			dmg *= lerpf(1.0, def.falloff_min, clampf((dist - def.falloff_start) / 30.0, 0.0, 1.0))
		if col is Area3D and col.has_meta("bot"):
			var bot = col.get_meta("bot")
			if is_instance_valid(bot):
				var res: Dictionary = bot.take_damage(dmg, col.get_meta("zone"), hit.position, dir, hit.normal, player)
				Game.stats.hits += 1
				player.on_hit_confirmed(res)
		elif col.has_method("take_hit"):
			col.take_hit(dmg, hit.position, dir, hit.normal)
		else:
			var surf: String = col.get_meta("surface", "concrete") if col is Object else "concrete"
			Fx.impact(hit.position, hit.normal, surf)
		if randf() < 0.45:
			Fx.tracer(muzzle_pos + dir * 0.5, hit.position)
	# Presentation
	var supp: bool = stats.suppressed
	_shot_audio(supp)
	Game.emit_noise(player.global_position, stats.noise, player)
	_flash_t = 0.035 if not supp else 0.02
	_flash.visible = stats.flash_mult > 0.5
	_flash.rotation.z = randf() * TAU
	if _flash_mat and _flash_variants.size() > 0:
		_flash_mat.albedo_texture = _flash_variants[randi() % _flash_variants.size()]
	_flash.scale = Vector3.ONE * randf_range(0.8, 1.2)
	_flash_light.light_energy = 3.5 * stats.flash_mult
	_cycle = 1.0
	_kick_v += def.kick_back * 38.0 * (1.0 - ads * 0.35)
	_kick_rot += Vector3(deg_to_rad(randf_range(2.0, 3.5)), deg_to_rad(randf_range(-1.0, 1.0)), deg_to_rad(randf_range(-2.5, 1.5))) * (1.0 - ads * 0.6)
	_kick_v += randf_range(-0.05, 0.05)
	player.apply_recoil(stats.recoil_v, randf_range(-stats.recoil_h, stats.recoil_h * 1.2))
	_eject_shell()
	if randf() < 0.5:
		Fx.smoke(muzzle_pos, -player.camera.global_transform.basis.z)
	if ammo == 0:
		Sfx.play("dry_fire", -14.0)
	fired.emit()
	ammo_changed.emit()


## Rounds passing close to a unit (or impacting near it) suppress it.
func _suppress_near(from: Vector3, to: Vector3, hit_col: Object) -> void:
	var hit_bot: Object = null
	if hit_col and hit_col.has_meta("bot"):
		hit_bot = hit_col.get_meta("bot")
	var seg := to - from
	var len2 := seg.length_squared()
	for b in get_tree().get_nodes_in_group("teslabot"):
		if b == hit_bot or b.state == Teslabot.S.DEAD:
			continue
		var c: Vector3 = b.global_position + Vector3.UP * 1.3
		var t := clampf((c - from).dot(seg) / maxf(len2, 0.001), 0.0, 1.0)
		var dist := c.distance_to(from + seg * t)
		if dist < 1.8:
			b.suppress(player.global_position, 0.35 * (1.0 - dist / 1.8) + 0.12)


func _eject_shell() -> void:
	if eject == null:
		return
	var mi := MeshInstance3D.new()
	mi.mesh = _shell_mesh
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	get_tree().current_scene.add_child(mi)
	mi.global_position = eject.global_position
	var b = player.camera.global_transform.basis
	var vel = b.x * randf_range(2.0, 3.2) + b.y * randf_range(1.2, 2.0) + b.z * randf_range(-0.3, 0.4) + player.velocity
	_shells.append({"n": mi, "v": vel, "t": 0.0, "spin": Vector3(randf_range(-20, 20), randf_range(-20, 20), randf_range(-20, 20)), "tink": false})


# ---------------------------------------------------------------- presentation
func update_view(delta: float, aiming: bool, sprinting: bool, move_speed: float, look_delta: Vector2, crouched: bool, grounded: bool) -> void:
	# Equip state
	_equip = move_toward(_equip, _equip_target, delta / 0.22)
	# ADS
	var ads_target := 1.0 if aiming and not is_reloading() and not sprinting and _equip > 0.9 else 0.0
	ads = move_toward(ads, ads_target, delta / maxf(stats.ads_time, 0.05))
	var ads_e := ads * ads * (3.0 - 2.0 * ads)
	# Reload progress
	if is_reloading():
		_reload_t += delta / _reload_len
		_reload_step()
		if _reload_t >= 1.0:
			_reload_t = -1.0
			if not _reload_loaded:
				_finish_load()
	# Muzzle flash
	if _flash_t > 0.0:
		_flash_t -= delta
		if _flash_t <= 0.0:
			_flash.visible = false
	_flash_light.light_energy = move_toward(_flash_light.light_energy, 0.0, delta * 90.0)
	# Kick spring
	var k := 260.0
	var damp := 22.0
	_kick_v += (-k * _kick - damp * _kick_v) * delta
	_kick += _kick_v * delta
	_kick_rot = _kick_rot.lerp(Vector3.ZERO, 1.0 - exp(-14.0 * delta))
	# Mouse sway (lags behind look direction)
	var sway_target := -look_delta * 0.0009 * (1.0 - ads_e * 0.8)
	sway_target = sway_target.limit_length(0.05)
	_sway_v += ((sway_target - _sway) * 140.0 - _sway_v * 16.0) * delta
	_sway += _sway_v * delta
	# Bob
	var spd := clampf(move_speed / 4.5, 0.0, 1.6) if grounded else 0.0
	_bob_t += delta * (6.5 + spd * 4.0) * (1.0 if spd > 0.05 else 0.0)
	var bob_amt := spd * (1.0 - ads_e * 0.85) * (0.6 if crouched else 1.0)
	var bob := Vector3(sin(_bob_t) * 0.011, -absf(cos(_bob_t)) * 0.009, 0.0) * bob_amt
	# Idle breathing
	var t := Time.get_ticks_msec() / 1000.0
	var breathe := Vector3(sin(t * 1.1) * 0.0012, sin(t * 2.2) * 0.0015, 0) * (1.0 - ads_e * 0.7)
	# Positions
	var hip: Vector3 = def.hip_pos
	var ads_pos := -eye_local
	var pos := hip.lerp(ads_pos, ads_e) + bob + breathe
	pos += Vector3(_sway.x, _sway.y, 0)
	pos.z += _kick
	var rot := Vector3(_sway.y * 2.5, _sway.x * 2.5, _sway.x * 3.0) + _kick_rot
	# Sprint pose
	var sp := 1.0 if sprinting and not is_reloading() else 0.0
	_sprint_blend = move_toward(_sprint_blend, sp, delta * 6.0)
	var spe := _sprint_blend * _sprint_blend * (3.0 - 2.0 * _sprint_blend)
	pos += Vector3(-0.04, -0.05, 0.03) * spe
	rot += def.sprint_rot * spe
	rot.z += sin(_bob_t * 0.5) * 0.04 * spe
	# Reload pose
	if is_reloading():
		var r := _reload_pose(_reload_t)
		pos += r[0]
		rot += r[1]
	# Equip pose: draw rises with a little overshoot, holster drops away.
	var e_in := _equip
	var c1 := 1.70158
	var back := 1.0 + (c1 + 1.0) * pow(e_in - 1.0, 3.0) + c1 * pow(e_in - 1.0, 2.0) if _equip_target > 0.5 else e_in * e_in
	var lowered := 1.0 - back
	pos += Vector3(0.05, -0.28, 0.06) * lowered
	rot += Vector3(-1.0, 0.35, -0.25) * lowered
	# Movement-dependent motion: lean into strafes, dip on landing, float on jumps.
	var lv: Vector3 = player.camera.global_transform.basis.inverse() * player.velocity
	_strafe = lerpf(_strafe, clampf(lv.x / 4.3, -1.0, 1.0), 1.0 - exp(-8.0 * delta))
	_vert = lerpf(_vert, clampf(lv.y / 5.0, -1.0, 1.0), 1.0 - exp(-10.0 * delta))
	var ads_k := 1.0 - ads_e * 0.75
	rot.z += -_strafe * 0.07 * ads_k
	pos.x += -_strafe * 0.008 * ads_k
	pos.y += -_vert * 0.012 * ads_k - player._land_dip * 0.35
	rot.x += _vert * 0.03 * ads_k
	# Wall proximity: pull weapon back instead of clipping
	pos.z += _clip_pull
	rot.x += _clip_pull * 3.0
	position = pos
	rotation = rot
	_animate_parts(delta)
	_update_shells(delta)


var _sprint_blend := 0.0


func update_clip(dist_to_wall: float) -> void:
	var want := clampf(0.75 - dist_to_wall, 0.0, 0.35)
	_clip_pull = lerpf(_clip_pull, want, 0.25)


func _reload_pose(t: float) -> Array:
	var e := sin(clampf(t, 0.0, 1.0) * PI)
	# Bring the rifle toward centre and cant it so the magwell faces the
	# camera; the left hand works the magazine (see _reload_left).
	var p := Vector3(-0.06, 0.1, 0.08) * e
	var r := Vector3(0.1, 0.12, -0.5) * e
	if id == "pistol":
		r = Vector3(0.35, 0.1, 0.6) * e
	if _reload_empty and t > 0.7 and t < 0.9:
		var b := sin((t - 0.7) / 0.2 * PI)
		p += Vector3(0.0, 0.0, 0.03) * b
		r += Vector3(-0.1, 0.0, -0.15) * b
	return [p, r]


func _reload_step() -> void:
	var t := _reload_t
	var out_t := 0.18
	var in_t := 0.55 if _reload_empty else 0.62
	var pistol := id == "pistol"
	# M3 timeline, synced to the left-hand choreography in _reload_left().
	_rl_event("release", 0.13, "pistol_mag_release" if pistol else "rifle_mag_release", "mag_out", -2.0)
	if _reload_empty:
		_rl_event("drop", 0.34, "rifle_mag_drop", "", -4.0)          # empty mag hits the floor
	else:
		_rl_event("pocket", 0.34, "rifle_mag_pouch", "", -4.0)       # partial mag stowed
	_rl_event("pouch", 0.42, "rifle_mag_pouch", "", -6.0)
	if t >= in_t and not _reload_events.has("in"):
		_reload_events["in"] = true
		if not _play_first(["pistol_mag_seat" if pistol else "rifle_mag_seat", "mag_in"], -2.0):
			pass
		_finish_load()
	if _reload_empty:
		if pistol:
			_rl_event("slide", 0.8, "pistol_slide_rack", "bolt", -2.0)
		else:
			_rl_event("charge", 0.74, "rifle_charge_pull", "bolt", -2.0)
			_rl_event("charge_rel", 0.81, "rifle_charge_release", "", -1.0)
	# Magazine motion: drop out, hidden, come back up.
	if mag_node:
		var drop := Vector3.ZERO
		if t < out_t:
			drop = Vector3.ZERO
		elif t < out_t + 0.12:
			drop = Vector3(0, -0.35, 0.05) * ((t - out_t) / 0.12)
		elif t < in_t - 0.15:
			drop = Vector3(0, -0.35, 0.05)
		elif t < in_t:
			drop = Vector3(0, -0.25, 0.08) * (1.0 - (t - (in_t - 0.15)) / 0.15)
		mag_node.transform = mag_rest.translated_local(drop)


func _update_shells(delta: float) -> void:
	for i in range(_shells.size() - 1, -1, -1):
		var s: Dictionary = _shells[i]
		var n: MeshInstance3D = s.n
		s.t += delta
		s.v.y -= 9.8 * delta
		n.global_position += s.v * delta
		n.rotation += s.spin * delta
		if not s.tink and s.t > 0.45:
			s.tink = true
			Sfx.play_3d("shell_tink", n.global_position, -10.0, 0.2)
		if s.t > 0.8:
			n.queue_free()
			_shells.remove_at(i)



# ---------------------------------------------------------------- M2: mechanism
func _animate_parts(delta: float) -> void:
	# Bolt carrier / slide: snap back on the shot, spring forward. The pistol
	# slide locks back on an empty magazine until the reload chambers a round.
	var locked := id == "pistol" and ammo == 0 and not (is_reloading() and _reload_loaded)
	if locked:
		_cycle = 1.0
	else:
		_cycle = move_toward(_cycle, 0.0, delta / (60.0 / stats.rpm * 0.8))
	var travel := _cycle * _cycle
	if _parts.has("bolt"):
		var b: Array = _parts.bolt
		b[0].transform = (b[1] as Transform3D).translated(Vector3(0, 0, 0.075 * travel))
	if _parts.has("slide"):
		var sl: Array = _parts.slide
		sl[0].transform = (sl[1] as Transform3D).translated(Vector3(0, 0, 0.032 * travel))
	if _parts.has("trigger"):
		var tr: Array = _parts.trigger
		var pull := 1.0 if (_trigger_held_last and ammo > 0) else 0.0
		tr[0].transform = (tr[1] as Transform3D).rotated_local(Vector3.RIGHT, -0.25 * pull)
	if _parts.has("charging_handle"):
		var ch: Array = _parts.charging_handle
		var pull_ch := 0.0
		if is_reloading() and _reload_empty and id == "rifle":
			pull_ch = clampf(1.0 - absf(_reload_t - 0.78) / 0.05, 0.0, 1.0)
		ch[0].transform = (ch[1] as Transform3D).translated(Vector3(0, 0, 0.07 * pull_ch))


## Transform of `n` in this weapon's parent space (the weapon holder).
func _xf(n: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = n
	while cur != null and cur != self:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return transform * t


var _sock_cache := {}


func _sock_xf(names: Array) -> Variant:
	for nm in names:
		if not _sock_cache.has(nm):
			_sock_cache[nm] = _find_prefixed(model, nm)
		var n: Node3D = _sock_cache[nm]
		if n and is_instance_valid(n):
			return _xf(n)
	return null


## Hand IK targets for FPArms, in the weapon-holder (camera) space.
func hand_targets() -> Dictionary:
	var r = _sock_xf(["sock_hand_R"])
	if r == null:
		return {}
	var out := {"R": r, "kind": "open"}
	var l = null
	var grip_id: String = loadout.get("grip", "none") if id == "rifle" else "none"
	if grip_id != "none":
		if not _sock_cache.has("grip_" + grip_id):
			var gn := model.find_child("att_" + grip_id, true, false)
			_sock_cache["grip_" + grip_id] = _find_prefixed(gn, "hand_L") if gn else null
		var gh: Node3D = _sock_cache["grip_" + grip_id]
		if gh and is_instance_valid(gh):
			l = _xf(gh)
		if l == null:
			l = _sock_xf(["sock_hand_L_vgrip" if grip_id == "grip_vertical" else "sock_hand_L_agrip"])
		out.kind = "fist" if grip_id == "grip_vertical" else "open"
	if l == null:
		l = _sock_xf(["sock_hand_L"])
	if l == null:
		out.L = r
		return out
	if is_reloading():
		var res := _reload_left(l)
		l = res[0]
		if res[1] != "":
			out.kind = res[1]
	# Contextual interaction: the support hand leaves the weapon to press.
	_reach = move_toward(_reach, 1.0 if reach_point != null and not is_reloading() else 0.0, get_physics_process_delta_time() * 4.0)
	if _reach > 0.0 and reach_point != null:
		var cam_t: Transform3D = player.camera.global_transform
		var holder_space: Vector3 = (cam_t.affine_inverse() * (reach_point as Vector3))
		var press := Transform3D(Basis.looking_at(holder_space.normalized(), Vector3.UP) * Basis(Vector3.RIGHT, -PI / 2), holder_space - holder_space.normalized() * 0.17)
		l = (l as Transform3D).interpolate_with(press, _reach * _reach * (3.0 - 2.0 * _reach))
		out.kind = "point"
	out.L = l
	return out


func _mag_hand_xf() -> Variant:
	if mag_node:
		# Dictionary cache (Object.set_meta(null) would delete the key).
		var key := "maghand_%d" % mag_node.get_instance_id()
		if not _sock_cache.has(key):
			_sock_cache[key] = _find_prefixed(mag_node, "hand_L")
		var mh: Node3D = _sock_cache[key]
		if mh and is_instance_valid(mh):
			return _xf(mh)
	return _sock_xf(["sock_hand_L_mag"])


static func _ease(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


## Left-hand reload choreography: support -> magazine -> pouch -> new
## magazine into the well -> (charging handle if empty) -> support.
func _reload_left(support: Transform3D) -> Array:
	var t := _reload_t
	var mag_v = _mag_hand_xf()
	if mag_v == null:
		return [support, ""]
	var mag: Transform3D = mag_v
	var pouch := Transform3D(mag.basis, Vector3(-0.2, -0.55, -0.1))
	var in_t := 0.55 if _reload_empty else 0.62
	if t < 0.14:
		return [support.interpolate_with(mag, _ease(t / 0.14)), "fist"]
	if t < 0.30:
		return [mag, "fist"]
	if t < 0.40:
		return [mag.interpolate_with(pouch, _ease((t - 0.30) / 0.10)), "fist"]
	if t < in_t - 0.15:
		return [pouch.interpolate_with(mag, _ease((t - 0.40) / maxf(in_t - 0.55, 0.01))), "fist"]
	if t < in_t + 0.04:
		return [mag, "fist"]
	if _reload_empty and id == "rifle" and _parts.has("charging_handle"):
		var ch: Transform3D = _xf(_parts.charging_handle[0])
		var hand_ch := Transform3D(support.basis, ch.origin + Vector3(-0.02, 0.05, 0.06))
		if t < 0.72:
			return [mag.interpolate_with(hand_ch, _ease((t - in_t - 0.04) / maxf(0.72 - in_t - 0.04, 0.01))), "fist"]
		if t < 0.84:
			return [hand_ch, "fist"]
		return [hand_ch.interpolate_with(support, _ease((t - 0.84) / 0.16)), ""]
	var back_start := in_t + 0.04
	return [mag.interpolate_with(support, _ease((t - back_start) / maxf(0.95 - back_start, 0.01))), ""]



func _exit_tree() -> void:
	if _att_root and is_instance_valid(_att_root):
		_att_root.free()
		_att_root = null



# ---------------------------------------------------------------- M3 audio helpers
static func _has_snd(n: String) -> bool:
	return ResourceLoader.exists("res://assets/audio/%s.wav" % n) or ResourceLoader.exists("res://assets/audio/%s_0.wav" % n)


func _play_first(names: Array, vol: float) -> bool:
	for n in names:
		if n != "" and _has_snd(n):
			Sfx.play_local(n, vol, 0.04)
			return true
	return false


func _rl_event(key: String, at: float, snd: String, fallback: String, vol: float) -> void:
	if _reload_t >= at and not _reload_events.has(key):
		_reload_events[key] = true
		_play_first([snd, fallback], vol)


## Room size class -> authored room response (shot_room_<class>).
const ROOM_CLASS := {"office": "small", "tunnel": "small", "antechamber": "small", "passage": "small", "crawl": "duct",
	"corridor": "medium", "servers": "medium", "control": "medium",
	"hall": "large", "dock": "large", "pump": "large", "switchgear": "large", "core": "huge"}
## Layer levels (dB). Close layers are mastered to -1 dBFS peak.
const LV_CLOSE := -3.0
const LV_SUPP := -3.0
const LV_PISTOL := -4.0
const LV_MECH_OPEN := -9.0
const LV_MECH_SUPP := -7.0
const LV_MECH_PISTOL := -10.0
const LV_ROOM := -1.0
const LV_SLAP := -4.0
var _last_shot_t := -10.0
var _burst_n := 0


## Gunshot (M4.3): close signature + mechanical action + the authored response
## of the room size the player is in, plus delayed early reflections from
## nearby walls, positioned at the walls.
func _shot_audio(supp: bool) -> void:
	if not _has_snd("rifle_close"):
		_shot_audio_m3(supp)
		return
	var now := Time.get_ticks_msec() / 1000.0
	_burst_n = _burst_n + 1 if now - _last_shot_t < 0.2 else 0
	_last_shot_t = now
	var rifle := id == "rifle"
	var room := Game.room_at(player.global_position + Vector3.UP)
	var cls: String = ROOM_CLASS.get(room, "medium")
	if rifle:
		Sfx.weapon_layer("rifle_supp_close" if supp else "rifle_close", LV_SUPP if supp else LV_CLOSE, 0.025)
		Sfx.weapon_layer("rifle_mech", LV_MECH_SUPP if supp else LV_MECH_OPEN, 0.04)
	else:
		Sfx.weapon_layer("pistol_close", LV_PISTOL, 0.025)
		Sfx.weapon_layer("pistol_mech", LV_MECH_PISTOL, 0.04)
	# Sustained fire: the room keeps ringing, so each new tail is a little lower.
	var tail_db := LV_ROOM - minf(6.0, _burst_n * 0.8)
	Sfx.weapon_layer("shot_room_%s%s" % ["supp_" if supp else "", cls], tail_db, 0.02)
	_wall_slaps(supp, cls)


## Early reflections from walls within 14 m (left, right, behind, ahead,
## ceiling): delayed by the real path length and played from the wall.
func _wall_slaps(supp: bool, cls: String) -> void:
	if cls in ["large", "huge"] and _burst_n > 0:
		return   # the hall layers carry their own slapback during bursts
	var cam: Camera3D = player.camera
	var o := cam.global_position
	var b := cam.global_transform.basis
	var space: PhysicsDirectSpaceState3D = player.get_world_3d().direct_space_state
	var dirs := [b.x, -b.x, b.z, -b.z, Vector3.UP]
	var n := 0
	for d in dirs:
		var dd: Vector3 = d
		dd.y = 0.0 if d != Vector3.UP else 1.0
		dd = dd.normalized()
		var q := PhysicsRayQueryParameters3D.create(o, o + dd * 14.0, 1)
		q.exclude = [player.get_rid()]
		var h: Dictionary = space.intersect_ray(q)
		if h.is_empty():
			continue
		var dist: float = o.distance_to(h.position)
		if dist < 0.6:
			continue
		var delay := 2.0 * dist / 343.0
		var vol := LV_SLAP - 20.0 * log(maxf(dist, 1.0) * 2.0) / log(10.0) + 6.0
		var pos: Vector3 = h.position
		var snd := "shot_slap_supp" if supp else "shot_slap"
		get_tree().create_timer(delay, false).timeout.connect(func(): Sfx.weapon_slap(snd, pos, vol))
		n += 1
		if n >= 4:
			break


## M3 layering, kept as a fallback when the M4.3 layers are absent.
func _shot_audio_m3(supp: bool) -> void:
	var base: String = def.shot_sound_supp if supp else def.shot_sound
	if not supp and _has_snd(base.replace("_shot", "_shot_dry")):
		Sfx.play_local(base.replace("_shot", "_shot_dry"), -1.0, 0.05)
		var room := Game.room_at(player.global_position + Vector3.UP)
		var tail := "shot_tail_hall" if room in ["hall", "dock"] else "shot_tail_small"
		if _has_snd(tail):
			Sfx.play_local(tail, -2.0 if id == "rifle" else -5.0, 0.03)
	else:
		Sfx.play_local(base, -1.0 if not supp else -4.0, 0.05)
	if id == "rifle" and _has_snd("rifle_mech"):
		Sfx.play_local("rifle_mech", -9.0 if not supp else -5.0, 0.06)



# ---------------------------------------------------------------- M3 muzzle flash
var _flash_mat: StandardMaterial3D
static var _flash_variants: Array[ImageTexture] = []


## Procedural petal/star flash textures (3 variants, built once): a hot core,
## irregular prongs and soft falloff, so consecutive shots never look stamped.
static func _flash_texture(seed_: int) -> ImageTexture:
	if _flash_variants.is_empty():
		for v in 3:
			var rng := RandomNumberGenerator.new()
			rng.seed = 7919 * (v + 1)
			var n := 128
			var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
			var prongs := rng.randi_range(5, 7)
			var phase := rng.randf() * TAU
			var lens := []
			for k in prongs:
				lens.append(rng.randf_range(0.55, 1.0))
			for y in n:
				for x in n:
					var dx := (x - n * 0.5) / (n * 0.5)
					var dy := (y - n * 0.5) / (n * 0.5)
					var r := sqrt(dx * dx + dy * dy)
					var a := atan2(dy, dx) + phase
					var sector := fposmod(a, TAU) / TAU * prongs
					var idx := int(sector) % prongs
					var f := fposmod(sector, 1.0)
					var prong: float = pow(maxf(0.0, cos((f - 0.5) * PI)), 6.0) * lens[idx]
					var core := exp(-r * r * 22.0)
					var arm := prong * exp(-r * 2.4) * smoothstep(1.0, 0.2, r)
					var vv := clampf(core * 1.2 + arm * 0.9, 0.0, 1.0)
					img.set_pixel(x, y, Color(1.0, 0.75 + 0.25 * core, 0.45 + 0.55 * core, vv))
			_flash_variants.append(ImageTexture.create_from_image(img))
	return _flash_variants[seed_ % _flash_variants.size()]
