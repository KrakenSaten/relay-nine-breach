extends Node
## Automated verification and capture harness (not part of normal play).
##   --autotest --shots=<dir>   scripted run: captures, AI combat log, mission flow
##   --bench --shots=<dir>      fly-through frame-time benchmark for all presets
## Teleports and time skips used here are listed in the log so captures are not
## mistaken for uninterrupted play.

var main: Node
var player: Player
var out_dir := "user://captures"
var log_lines: PackedStringArray = []
var _frame_times: Array = []
var _recording := false
var _ai_counts := {"attacks": 0, "states": {}, "roles": {}, "cover_moves": 0}


func run(m: Node) -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	main = m
	player = m.player
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			out_dir = a.get_slice("=", 1)
	DirAccess.make_dir_recursive_absolute(out_dir)
	player.bot_input = {"god": true}
	Game.begin_mission()
	Game.set_objective("REACH RELAY CONTROL AND CONNECT THE OVERRIDE", main.level.console.global_position)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if "--bench" in OS.get_cmdline_user_args():
		await _bench()
	elif "--showcase" in OS.get_cmdline_user_args():
		await _showcase()
	elif "--compare" in OS.get_cmdline_user_args():
		await _compare()
	elif "--video" in OS.get_cmdline_user_args():
		await _video()
	else:
		await _autotest()
	_write_log()
	get_tree().quit()


func _process(delta: float) -> void:
	if _recording:
		_frame_times.append(delta)


func L(s: String) -> void:
	var line := "[%7.2f] %s" % [Time.get_ticks_msec() / 1000.0, s]
	log_lines.append(line)
	print(line)


func _wait(t: float) -> void:
	await get_tree().create_timer(t, true, false, true).timeout


func shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var p := out_dir.path_join(name + ".png")
	img.save_png(p)
	L("capture " + p)


func teleport(pos: Vector3, look_at_pos: Vector3) -> void:
	player.global_position = pos
	player.velocity = Vector3.ZERO
	_look(look_at_pos)
	L("TELEPORT player -> %s" % [pos])


func _look(target: Vector3) -> void:
	var cam := player.camera.global_position
	var d := target - cam
	player.rotation.y = atan2(-d.x, -d.z)
	player._pitch = asin(clampf(d.normalized().y, -1, 1))
	player._recoil_pitch = 0.0


func _bots() -> Array:
	return main.director.bots.filter(func(b): return b.state != Teslabot.S.DEAD)


# ------------------------------------------------------------------ autotest
func _autotest() -> void:
	L("AUTOTEST start, quality=%s" % Settings.PRESETS[Settings.quality])
	L("bots spawned: %d, cover points: %d" % [main.director.bots.size(), main.director.cover_points.size()])
	var nav_ok := NavigationServer3D.map_get_path(get_viewport().world_3d.navigation_map, Vector3(8, 0, 11), Vector3(27, 0, -35), true)
	L("nav path dock->control points: %d" % nav_ok.size())
	await _wait(6.0)  # let first-use shaders compile before captures
	await shot("01_dock_start")
	_look(Vector3(8, 1.6, -2))
	player.bot_input.aim = true
	await _wait(0.8)
	await shot("02_ads_reflex")
	var w := player.weapon()
	var eye: Node3D = w.model.find_child("eye", true, false)
	L("ADS debug: eye_local=%s weapon.pos=%s ads=%.2f" % [w.eye_local, w.position, w.ads])
	player.bot_input.aim = false
	# Corridor
	teleport(Vector3(7.5, 0.05, -1.5), Vector3(7.5, 1.4, -20))
	await _wait(1.5)
	await shot("03_corridor")
	Game.set_room_lit("corridor", false)
	player.toggle_nv()
	await _wait(1.0)
	await shot("03b_corridor_dark_nightvision")
	L("night vision: on=%s battery=%.2f" % [player.nv_on, player.nv_battery])
	player.toggle_nv()
	await _wait(0.3)
	await shot("03c_corridor_dark_no_nv")
	Game.set_room_lit("corridor", true)
	# Hall overview from the passage, crouched under the shutter
	teleport(Vector3(13.2, 0.05, -2.6), Vector3(22, 2.5, -14))
	await _wait(2.0)
	await shot("04_hall_overview")
	# Combat: stay in the hall and let the units engage (god mode)
	L("COMBAT phase: player exposed in hall for 14 s (god mode)")
	_track_ai(true)
	var charged := false
	var t := 0.0
	while t < 14.0:
		await _wait(0.1)
		t += 0.1
		if is_equal_approx(fmod(t, 2.0), 0.0) or absf(fmod(t, 2.0)) < 0.05:
			for b in _bots():
				var d: float = b.eye_pos().distance_to(player.get_aim_point())
				if d < 20.0:
					var to: Vector3 = player.get_aim_point() - b.eye_pos()
					var flat := Vector3(to.x, 0, to.z).normalized()
					var q := PhysicsRayQueryParameters3D.create(b.eye_pos(), player.get_aim_point(), 1)
					q.exclude = [b.get_rid()]
					var h := player.get_world_3d().direct_space_state.intersect_ray(q)
					L("  perc %s d=%.1f ang=%.0f los=%s hit=%s at %s bot=%s aw=%.2f state=%s lit=%s" % [b.name, d, rad_to_deg(b.head_forward().angle_to(flat)), h.is_empty(), (h.collider.get_child(0).shape.size if h else null), h.get("position", null), b.global_position, b.awareness, Teslabot.S.keys()[b.state], Game.is_lit(player.get_aim_point())])
		for b in _bots():
			if not charged and b._attack_t > 0.35 and b.target_visible:
				_look(b.bones.muzzle.global_position)
				charged = true
				await shot("05_bot_charging")
	_track_ai(false)
	L("AI after exposure: %s" % [_ai_summary()])
	if "--quick" in OS.get_cmdline_user_args():
		return
	# Fight back: aim at the nearest visible unit's zones and fire
	L("ENGAGE: scripted aim at visible units (zones head/torso/core)")
	var kills_before: int = Game.stats.kills
	var fired_shot := false
	for i in 6:
		var target := _nearest_visible()
		if target == null:
			break
		var zone_pt: Vector3 = target.bones.core.global_position if _behind(target) else target.bones.torso.global_position + Vector3(0, 0.35, 0)
		var tt := 0.0
		while tt < 3.0 and target.state != Teslabot.S.DEAD:
			zone_pt = target.bones.core.global_position if _behind(target) else target.bones.torso.global_position + Vector3(0, 0.35, 0)
			_look(zone_pt)
			player.bot_input.aim = true
			player.bot_input.fire = true
			await _wait(0.05)
			tt += 0.05
			if not fired_shot and tt > 0.3:
				fired_shot = true
				await shot("06_firing_ads")
			if player.weapon().ammo == 0:
				player.weapon().start_reload()
		player.bot_input.fire = false
		L("target %s -> state %s hp %.0f" % [target.name, Teslabot.S.keys()[target.state], target.hp])
		await _wait(0.3)
	player.bot_input.fire = false
	player.bot_input.aim = false
	L("kills during engage: %d (stats %s)" % [Game.stats.kills - kills_before, Game.stats])
	await _wait(0.6)
	await shot("07_after_fight")
	# Core overload demo: approach a unit from behind and shoot the capacitor
	var victim := _first_alive_far()
	if victim:
		var back: Vector3 = victim.global_position + victim.global_transform.basis.z * 3.5
		victim._stagger(3.0)
		teleport(back + Vector3(0, 0.05, 0), victim.bones.core.global_position)
		var tt2 := 0.0
		player.bot_input.fire = true
		while tt2 < 2.0 and victim.state != Teslabot.S.DEAD:
			_look(victim.bones.core.global_position)
			await _wait(0.03)
			tt2 += 0.03
		player.bot_input.fire = false
		L("core shot test: victim state=%s, core_kills=%d" % [Teslabot.S.keys()[victim.state], Game.stats.core_kills])
		await _wait(0.12)
		await shot("08_core_overload")
		await _wait(1.2)
		await shot("09_wreck")
	# Server room & control
	teleport(Vector3(13.9, 0.05, -27.0), Vector3(14.5, 1.4, -36))
	await _wait(1.5)
	await shot("10_servers")
	teleport(Vector3(27.0, 0.05, -30.0), Vector3(27.0, 1.2, -37.0))
	await _wait(1.5)
	await shot("11_control")
	# Hack flow
	teleport(Vector3(27.0, 0.05, -35.6), Vector3(27.0, 1.1, -37.0))
	player.bot_input.interact = true
	for i in 12:
		await _wait(0.2)
		L("hold: focus=%s connecting=%.2f" % [player._focus.name if player._focus else "none", main.level.console.connecting])
	player.bot_input.interact = false
	L("console uploading=%s state=%s" % [main.level.console.uploading, Game.State.keys()[Game.state]])
	await _wait(3.0)
	await shot("12_upload_defend")
	await _wait(6.0)
	L("bots alive during defense: %d, console jammed=%s" % [_bots().size(), main.level.console.jammed])
	L("TIME SKIP: console progress forced to 0.98 to verify completion flow")
	main.level.console.progress = 0.98
	await _wait(3.0)
	L("after upload: state=%s D6 locked=%s" % [Game.State.keys()[Game.state], main.level.doors.D6.locked])
	teleport(Vector3(3.0, 0.1, 11.8), Vector3(8, 1.5, 4))
	await _wait(5.0)
	L("extraction: state=%s" % Game.State.keys()[Game.state])
	await shot("13_extraction")
	# Menus
	main.menus.open("loadout")
	await _wait(0.3)
	await shot("14_loadout")
	main.menus.open("settings")
	await _wait(0.3)
	await shot("15_settings")
	main.menus.open("complete")
	await _wait(0.3)
	await shot("16_complete")
	L("AUTOTEST done. Final stats %s" % [Game.stats])


func _behind(b: Node) -> bool:
	var to_p: Vector3 = player.global_position - b.global_position
	return to_p.normalized().dot(-b.global_transform.basis.z) < -0.3


func _nearest_visible() -> Node:
	var best: Node = null
	var bd := INF
	for b in _bots():
		var d: float = b.global_position.distance_to(player.global_position)
		var q := PhysicsRayQueryParameters3D.create(player.camera.global_position, b.bones.torso.global_position + Vector3(0, 0.35, 0), 1)
		if player.get_world_3d().direct_space_state.intersect_ray(q).is_empty() and d < bd:
			bd = d
			best = b
	return best


func _first_alive_far() -> Node:
	for b in _bots():
		if b.global_position.distance_to(player.global_position) > 6.0:
			return b
	return null


var _prev_states := {}


func _track_ai(on: bool) -> void:
	if on:
		set_meta("track", true)
	else:
		remove_meta("track")


func _physics_process(_d: float) -> void:
	if not has_meta("track"):
		return
	for b in main.director.bots:
		var s: String = Teslabot.S.keys()[b.state]
		if _prev_states.get(b, "") != s:
			_ai_counts.states[s] = _ai_counts.states.get(s, 0) + 1
			_prev_states[b] = s
		if b._attack_t > 0.0 and b._attack_t < 0.02:
			_ai_counts.attacks += 1
		if b.state == Teslabot.S.COMBAT:
			_ai_counts.roles[b.role] = _ai_counts.roles.get(b.role, 0) + 1
		if b._cover_phase == "peek":
			_ai_counts.cover_moves += 1


func _ai_summary() -> String:
	return "state entries %s | attack windups %d | role-frames %s | peek-frames %d | player damage absorbed (god) %d" % [_ai_counts.states, _ai_counts.attacks, _ai_counts.roles, _ai_counts.cover_moves, Game.stats.damage_taken]


# ------------------------------------------------------------------ benchmark
func _bench() -> void:
	var path := [Vector3(8, 0.05, 11), Vector3(7.5, 0.05, 1.0), Vector3(7.5, 0.05, -10.5), Vector3(10.5, 0.05, -11.0), Vector3(20, 0.05, -11.5), Vector3(26, 0.05, -18), Vector3(14, 0.05, -24.5), Vector3(14, 0.05, -28), Vector3(15.3, 0.05, -33.5), Vector3(20, 0.05, -32), Vector3(27, 0.05, -33)]
	for d in main.level.doors.values():
		if not d.locked:
			d.target = deg_to_rad(95)
	var res := []
	var presets := [0, 1, 2, 3]
	var original := Settings.quality
	for q in presets:
		Settings.set_quality(q, false)
		await _wait(2.5)
		_frame_times.clear()
		_recording = true
		var total := 0.0
		for i in path.size() - 1:
			total += path[i].distance_to(path[i + 1])
		var speed := total / 24.0
		var pos := 0.0
		var seg := 0
		var segpos := 0.0
		while seg < path.size() - 1:
			var dt := get_process_delta_time()
			segpos += speed * dt
			var a: Vector3 = path[seg]
			var b: Vector3 = path[seg + 1]
			var len := a.distance_to(b)
			if segpos >= len:
				segpos -= len
				seg += 1
				continue
			player.global_position = a.lerp(b, segpos / len)
			player.velocity = Vector3.ZERO
			var look := b + Vector3(0, 1.4, 0) + Vector3(sin(Time.get_ticks_msec() / 900.0) * 3.0, 0, 0)
			_look(look)
			await get_tree().process_frame
		_recording = false
		var ft: Array = _frame_times.duplicate()
		ft.sort()
		var n := ft.size()
		var sum := 0.0
		for f in ft:
			sum += f
		var avg_ms := sum / n * 1000.0
		var p95: float = ft[int(n * 0.95)] * 1000.0
		var p99: float = ft[int(n * 0.99)] * 1000.0
		var worst1 := 0.0
		var k := maxi(1, int(n * 0.01))
		for i in k:
			worst1 += ft[n - 1 - i]
		var low1 := 1.0 / (worst1 / k)
		var r := {"preset": Settings.PRESETS[q], "frames": n, "avg_fps": 1000.0 / avg_ms, "avg_ms": avg_ms, "p95_ms": p95, "p99_ms": p99, "1pct_low_fps": low1}
		res.append(r)
		L("BENCH %s" % [r])
		await shot("bench_%d_%s" % [q, Settings.PRESETS[q]])
	Settings.set_quality(original, false)
	var f := FileAccess.open(out_dir.path_join("bench.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(res, "  "))
	f.close()


func _write_log() -> void:
	var name := "bench_log.txt" if "--bench" in OS.get_cmdline_user_args() else "autotest_log.txt"
	var f := FileAccess.open(out_dir.path_join(name), FileAccess.WRITE)
	f.store_string("\n".join(log_lines))
	f.close()


# ------------------------------------------------------------------ showcase
func _showcase() -> void:
	# Freeze AI, stage one unit under dock lights, capture from several angles.
	for b in main.director.bots:
		b.set_physics_process(false)
	var bot: Teslabot = main.director.bots[0]
	bot.global_position = Vector3(8.0, 0.0, 6.0)
	bot.rotation = Vector3(0, 0, 0)
	bot.awareness = 1.0
	bot.state = Teslabot.S.COMBAT
	bot._aim_blend = 1.0
	await _wait(0.2)
	var views := [["s01_bot_front", Vector3(8.0, 0.05, 2.6), 0.0], ["s02_bot_three_quarter", Vector3(10.4, 0.05, 3.6), 0.0], ["s03_bot_back_core", Vector3(8.6, 0.05, 9.0), 0.0]]
	for v in views:
		teleport(v[1], bot.global_position + Vector3(0, 1.3, 0))
		await _wait(1.0)
		await shot(v[0])
	# Charge telegraph
	teleport(Vector3(9.5, 0.05, 2.8), bot.global_position + Vector3(0, 1.3, 0))
	bot.set_physics_process(true)
	player.bot_input.god = true
	bot.target_visible = true
	bot.last_seen_t = bot._t
	bot._start_attack()
	await _wait(0.45)
	await shot("s04_bot_charge")
	await _wait(0.2)
	await shot("s05_bot_arc")
	bot.set_physics_process(false)
	# Weapon presentation
	teleport(Vector3(12.0, 0.05, 8.0), Vector3(12.0, 1.0, 4.0))
	await _wait(0.8)
	await shot("s06_rifle_hip")
	player.bot_input.aim = true
	await _wait(0.6)
	await shot("s07_rifle_ads_reflex")
	L("ADS dbg: aiming=%s ads=%.2f pos=%s eye=%s equip=%.2f reload=%s sprint=%s" % [player._aiming, player.weapon().ads, player.weapon().position, player.weapon().eye_local, player.weapon()._equip, player.weapon().is_reloading(), player._sprinting])
	player.bot_input.aim = false
	var lo: Dictionary = player.loadout.duplicate()
	lo.optic = "optic_prism"; lo.muzzle = "suppressor"; lo.grip = "grip_angled"; lo.mag = "mag_ext"
	player.set_loadout(lo)
	await _wait(0.5)
	await shot("s08_rifle_alt_loadout")
	player.bot_input.aim = true
	await _wait(0.6)
	await shot("s09_rifle_ads_prism")
	player.bot_input.aim = false
	player.weapon().ammo = 0
	player.weapon().start_reload()
	await _wait(0.9)
	await shot("s10_reload")
	player._request_switch(1)
	await _wait(1.0)
	await shot("s11_pistol")
	# Damage states: blind + core overload close-up
	bot.set_physics_process(true)
	teleport(Vector3(8.0, 0.05, 2.8), bot.global_position + Vector3(0, 1.6, 0))
	bot.take_damage(80.0, "head", bot.bones.head.global_position, Vector3(0, 0, 1), Vector3(0, 0, -1), player)
	bot.take_damage(90.0, "arm_R", bot.bones.elbow_R.global_position, Vector3(0, 0, 1), Vector3(0, 0, -1), player)
	await _wait(0.6)
	await shot("s12_bot_damaged")
	teleport(Vector3(8.0, 0.05, 9.0), bot.global_position + Vector3(0, 1.4, 0))
	bot.take_damage(500.0, "core", bot.bones.core.global_position, Vector3(0, 0, -1), Vector3(0, 0, 1), player)
	await _wait(0.1)
	await shot("s13_overload")
	await _wait(1.6)
	await shot("s14_wreck")


# ------------------------------------------------------------------ video
## Scripted combat clip for --write-movie. God mode; aim is scripted
## (look-at with a little lag), movement uses the normal controller.
func _video() -> void:
	L("VIDEO: scripted combat in the turbine hall (god mode, scripted aim)")
	for b in main.director.bots:
		if b.global_position.distance_to(Vector3(20, 0, -14)) > 16.0:
			b.set_physics_process(false)
	teleport(Vector3(9.9, 0.05, -11.0), Vector3(20, 1.5, -11))
	main.level.doors.D3.target = deg_to_rad(95)
	await _wait(1.5)
	var t := 0.0
	var strafe := 1.0
	var aim_pt := player.camera.global_position + -player.camera.global_transform.basis.z * 10.0
	while t < 15.0:
		var dt := get_process_delta_time()
		t += dt
		var target := _nearest_visible()
		var charging := false
		for b in _bots():
			if b._attack_t > 0.15 and b.target_visible:
				charging = true
		# Strafe while a unit is charging, otherwise hold and shoot.
		player.bot_input.move = Vector2(strafe, 0) if charging else Vector2.ZERO
		if charging and randf() < dt * 0.8:
			strafe = -strafe
		if target:
			var want: Vector3 = target.bones.torso.global_position + Vector3(0, 0.3, 0)
			if target.blinded == false and randf() < 0.3:
				want = target.bones.head.global_position + Vector3(0, 0.1, 0)
			aim_pt = aim_pt.lerp(want, 1.0 - exp(-7.0 * dt))
			_look(aim_pt)
			player.bot_input.aim = true
			player.bot_input.fire = not charging or randf() < 0.5
		else:
			player.bot_input.fire = false
			player.bot_input.aim = false
		if player.weapon().ammo == 0:
			player.weapon().start_reload()
		await get_tree().process_frame
	player.bot_input = {"god": true}
	L("VIDEO done: kills=%d shots=%d hits=%d god_absorbed=%s" % [Game.stats.kills, Game.stats.shots, Game.stats.hits, Game.stats.get("god_absorbed", 0)])


# ------------------------------------------------------------------ compare
## Fixed camera poses for M1/M2 before-after comparison. AI frozen.
func _compare() -> void:
	for b in main.director.bots:
		b.set_physics_process(false)
		b.global_position += Vector3(0, -50, 0)  # park out of view
	var bot: Teslabot = main.director.bots[0]
	bot.global_position = Vector3(8.0, 0.0, 6.0)
	bot.rotation = Vector3.ZERO
	bot.state = Teslabot.S.COMBAT
	bot._aim_blend = 1.0
	bot.awareness = 1.0
	bot.set_physics_process(true)
	bot.director = null  # keeps _physics_process from thinking; animation pose stays
	await _wait(6.0)
	var poses := [
		["c01_dock", Vector3(8, 0.05, 11), Vector3(8, 1.6, -2)],
		["c02_corridor", Vector3(7.5, 0.05, -1.5), Vector3(7.5, 1.4, -20)],
		["c03_hall", Vector3(13.2, 0.05, -2.6), Vector3(22, 2.5, -14)],
		["c04_hall_deep", Vector3(28.0, 0.05, -4.0), Vector3(14, 2.0, -20)],
		["c05_servers", Vector3(13.9, 0.05, -27.0), Vector3(14.5, 1.4, -36)],
		["c06_control", Vector3(27.0, 0.05, -29.0), Vector3(27.0, 1.2, -37.0)],
		["c07_office", Vector3(5.0, 0.05, -4.0), Vector3(-4, 1.2, -11)],
		["c08_robot_front", Vector3(8.0, 0.05, 3.2), Vector3(8, 1.4, 6)],
		["c09_robot_back", Vector3(8.6, 0.05, 8.8), Vector3(8, 1.4, 6)],
	]
	for p in poses:
		teleport(p[1], p[2])
		await _wait(1.2)
		await shot(p[0])
	teleport(Vector3(12.0, 0.05, 8.0), Vector3(12.0, 1.0, 4.0))
	await _wait(1.0)
	await shot("c10_weapon_hip")
	player.bot_input.aim = true
	await _wait(1.0)
	await shot("c11_weapon_ads")
	player.bot_input.aim = false
	await _wait(0.6)
	player.weapon().ammo = 0
	player.weapon().start_reload()
	await _wait(player.weapon()._reload_len * 0.4)
	await shot("c12_reload")
	await _wait(3.0)
	player._request_switch(1)
	await _wait(1.2)
	await shot("c13_pistol")
