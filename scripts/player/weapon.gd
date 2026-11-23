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

const ATT_SCENE := "res://assets/models/attachments.glb"
static var _att_root: Node3D


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
	m.albedo_texture = t
	m.albedo_color = Color(1.6, 1.3, 1.0)
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
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
		Sfx.play("ui_click", -8.0)
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
	Sfx.play(def.shot_sound_supp if supp else def.shot_sound, -1.0 if not supp else -4.0, 0.05)
	Game.emit_noise(player.global_position, stats.noise, player)
	_flash_t = 0.035 if not supp else 0.02
	_flash.visible = stats.flash_mult > 0.5
	_flash.rotation.z = randf() * TAU
	_flash.scale = Vector3.ONE * randf_range(0.8, 1.2)
	_flash_light.light_energy = 3.5 * stats.flash_mult
	_kick_v += def.kick_back * 38.0 * (1.0 - ads * 0.35)
	_kick_rot += Vector3(deg_to_rad(randf_range(2.0, 3.5)), deg_to_rad(randf_range(-1.0, 1.0)), deg_to_rad(randf_range(-2.0, 2.0))) * (1.0 - ads * 0.6)
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
	# Equip pose
	var lowered := 1.0 - _equip
	pos += Vector3(0.0, -0.25, 0.05) * lowered
	rot += Vector3(-0.9, 0.2, 0.0) * lowered
	# Wall proximity: pull weapon back instead of clipping
	pos.z += _clip_pull
	rot.x += _clip_pull * 3.0
	position = pos
	rotation = rot
	_update_shells(delta)


var _sprint_blend := 0.0


func update_clip(dist_to_wall: float) -> void:
	var want := clampf(0.75 - dist_to_wall, 0.0, 0.35)
	_clip_pull = lerpf(_clip_pull, want, 0.25)


func _reload_pose(t: float) -> Array:
	var e := sin(clampf(t, 0.0, 1.0) * PI)
	var p := Vector3(-0.03, -0.06, 0.04) * e
	var r := Vector3(0.25, 0.25, 0.55) * e
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
	if t >= out_t and not _reload_events.has("out"):
		_reload_events.out = true
		Sfx.play("mag_out", -4.0)
	if t >= in_t and not _reload_events.has("in"):
		_reload_events["in"] = true
		Sfx.play("mag_in", -3.0)
		_finish_load()
	if _reload_empty and t >= 0.76 and not _reload_events.has("bolt"):
		_reload_events.bolt = true
		Sfx.play("bolt", -3.0)
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
