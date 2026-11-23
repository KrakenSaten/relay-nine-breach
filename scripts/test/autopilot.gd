extends Node
## Automated verification and capture harness (not part of normal play).
##   --autotest --shots=<dir>   scripted run: captures, AI combat log, mission flow
##   --bench --shots=<dir>      fly-through frame-time benchmark for all presets
##   --m4mission / --m4cp / --m4nav / --m4ai / --m4spots / --m4video  (see m4_tests.gd)
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
	if not main.mission.restoring:
		Game.begin_mission()
		main.mission.begin()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var args := OS.get_cmdline_user_args()
	var m4 = load("res://scripts/test/m4_tests.gd").new(self)
	if "--m4mission" in args:
		await m4.mission()
	elif "--m4cp" in args:
		await m4.checkpoint_test()
		if Game.checkpoint.get("pending", false):
			return   # scene is reloading; phase B continues in the new autopilot
	elif "--m4nav" in args:
		await m4.nav()
	elif "--m4ai" in args:
		await m4.ai()
	elif "--m4spots" in args:
		await m4.spots()
	elif "--m4video" in args:
		await m4.video()
	elif "--bench" in OS.get_cmdline_user_args():
		await _bench()
	elif "--showcase" in OS.get_cmdline_user_args():
		await _showcase()
	elif "--spots" in OS.get_cmdline_user_args():
		await _spots()
	elif "--audit" in OS.get_cmdline_user_args():
		await _audit()
	elif "--aitest2" in OS.get_cmdline_user_args():
		await _aitest2()
	elif "--aitest" in OS.get_cmdline_user_args():
		await _aitest()
	elif "--botanim" in OS.get_cmdline_user_args():
		await _botanim()
	elif "--compare" in OS.get_cmdline_user_args():
		await _compare()
	elif "--video" in OS.get_cmdline_user_args():
		await _video()
	else:
		await _autotest()
	_write_log()
	get_tree().quit()


var _track_bot: Node3D = null
var _spikes: Array = []


func _process(delta: float) -> void:
	if _recording:
		_frame_times.append(delta)
	if _track_bot and is_instance_valid(_track_bot):
		var tgt: Vector3 = _track_bot.bones.pelvis.global_position + Vector3(0, 0.2, 0)
		var cur := player.camera.global_position - player.camera.global_transform.basis.z * 4.0
		_look(cur.lerp(tgt, 1.0 - exp(-6.0 * delta)))


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
func _release_checks() -> void:
	L("RELEASE build=%s debug=%s version=%s exe=%s" % [OS.has_feature("template"), OS.is_debug_build(), ProjectSettings.get_setting("application/config/version"), OS.get_executable_path()])
	L("RELEASE project dir present next to exe: %s" % FileAccess.file_exists(OS.get_executable_path().get_base_dir().path_join("project.godot")))
	L("RELEASE renderer=%s adapter=%s" % [RenderingServer.get_current_rendering_driver_name(), RenderingServer.get_video_adapter_name()])
	L("AUDIO driver=%s device=%s mix_rate=%d buses=%d" % [AudioServer.get_driver_name(), AudioServer.output_device, AudioServer.get_mix_rate(), AudioServer.bus_count])
	var names := ["rifle_shot", "rifle_shot_suppressed", "pistol_shot", "pistol_shot_suppressed", "mag_out", "mag_in", "bolt", "dry_fire", "impact_metal", "impact_concrete", "robot_step", "robot_servo", "tesla_charge", "tesla_shot", "robot_alert", "robot_death", "robot_hit", "robot_weakpoint", "door_open", "door_breach", "step_concrete", "step_metal", "foley_cloth", "ambience_facility", "ambience_hall", "ambience_servers", "electric_buzz_loop", "heartbeat", "ui_objective", "hitmarker", "alarm_loop", "blast_door_open", "breaker_close", "capacitor_hit", "capacitor_destroyed", "core_overload", "lift_call", "lift_arrive", "lift_motor_loop", "robot_wake", "relay_voice_beep", "ambience_pump", "ambience_switchgear", "ambience_core", "crawl_step", "arc_crackle"]
	var missing := []
	for n in names:
		if Sfx.stream(n) == null:
			missing.append(n)
	L("AUDIO streams checked=%d missing=%s" % [names.size(), missing])
	var vp := get_viewport()
	Settings.set_quality(0, false)
	await _wait(0.5)
	var low_scale := vp.scaling_3d_scale
	var low_sdfgi: bool = main.env.sdfgi_enabled
	Settings.set_quality(2, false)
	await _wait(0.5)
	L("SETTINGS preset switch Low->High: scale %.2f->%.2f sdfgi %s->%s taa=%s" % [low_scale, vp.scaling_3d_scale, low_sdfgi, main.env.sdfgi_enabled, vp.use_taa])


func _autotest() -> void:
	await _release_checks()
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
					L("  perc %s d=%.1f ang=%.0f los=%s hit=%s at %s bot=%s aw=%.2f state=%s lit=%s" % [b.name, d, rad_to_deg(b.head_forward().angle_to(flat)), h.is_empty(), (h.collider.name if h else null), h.get("position", null), b.global_position, b.awareness, Teslabot.S.keys()[b.state], Game.is_lit(player.get_aim_point())])
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
		# Deterministic setup: target in the open dock, facing away.
		victim.global_position = Vector3(8.0, 0.0, 6.0)
		victim.rotation = Vector3.ZERO
		await _wait(0.2)
		var back: Vector3 = victim.global_position + victim.global_transform.basis.z * 3.5
		victim._stagger(3.0)
		teleport(back + Vector3(0, 0.05, 0), victim.bones.core.global_position)
		var tt2 := 0.0
		player.bot_input.fire = true
		# M3 hit reactions shove the unit; keep re-aiming at the capacitor
		# for up to 4 s (same weapon, same damage model).
		while tt2 < 4.0 and victim.state != Teslabot.S.DEAD:
			_look(victim.bones.core.global_position)
			if player.weapon().ammo == 0:
				player.weapon().start_reload()
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
	# Hack flow (M4: lockdown + power are prerequisites; shortcut logged)
	L("SHORTCUT: M4 lockdown and breakers completed by signal (see --m4mission for the real interactions)")
	main.mission.ex.lockdown_panel.done.emit()
	main.mission.ex.breakers[0].done.emit()
	main.mission.ex.breakers[1].done.emit()
	await _wait(0.5)
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
	L("after upload: state=%s stage=%s D3 locked=%s (M4 complication)" % [Game.State.keys()[Game.state], main.mission.stage, main.level.doors.D3.locked])
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
	if _ai2_on:
		_ai2_track()
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
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--bench-presets="):
			presets = Array(arg.get_slice("=", 1).split(",")).map(func(x): return int(x))
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
			if dt > 0.02 and _recording:
				_spikes.append("%.1fms %s bots_combat=%d" % [dt * 1000.0, Fx.events, main.director.engaged().size()])
			Fx.events = {}
			player.velocity = Vector3.ZERO
			var look := b + Vector3(0, 1.4, 0) + Vector3(sin(Time.get_ticks_msec() / 900.0) * 3.0, 0, 0)
			_look(look)
			await get_tree().process_frame
		_recording = false
		L("SPIKES >20ms (%d): %s" % [_spikes.size(), _spikes.slice(0, 14)])
		_spikes.clear()
		L("PERF %s: draw_calls=%d objects=%d prims=%d process_ms=%.2f physics_ms=%.2f nav_ms=%.2f" % [Settings.PRESETS[q],
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
			Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME), Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
			Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, Performance.get_monitor(Performance.TIME_NAVIGATION_PROCESS) * 1000.0])
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


func _write_log_named(fname: String) -> void:
	var f := FileAccess.open(out_dir.path_join(fname), FileAccess.WRITE)
	if f:
		f.store_string("\n".join(log_lines))
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
		await _wait(0.3)
		L("PERF %s: process_ms=%.2f physics_ms=%.2f draw_calls=%d objects=%d nodes=%d fps=%d" % [p[0], Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME), Performance.get_monitor(Performance.OBJECT_NODE_COUNT), Engine.get_frames_per_second()])
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
	await _wait(player.weapon()._reload_len * 0.5)
	await shot("c12_reload")
	await _wait(3.0)
	player._request_switch(1)
	await _wait(1.2)
	await shot("c13_pistol")


# ------------------------------------------------------------------ AI behaviour test
var _ai2 := {"stacked": 0, "entering": 0, "suppressed": 0, "push": 0, "overwatch": 0, "pusher": 0, "flanker": 0, "cover": 0, "peek": 0, "entries_done": 0}
var _ai2_on := false
var _ai2_prev_entry := {}


func _ai2_track() -> void:
	for b in main.director.bots:
		if b.state == Teslabot.S.DEAD:
			continue
		var ph: String = b._entry.get("phase", "")
		if ph == "stacked": _ai2.stacked += 1
		if ph == "entering": _ai2.entering += 1
		if _ai2_prev_entry.get(b, "") == "entering" and ph == "":
			_ai2.entries_done += 1
		_ai2_prev_entry[b] = ph
		if b.suppression > 0.55: _ai2.suppressed += 1
		if b._push_t > 0.0: _ai2.push += 1
		if b.state == Teslabot.S.COMBAT and _ai2.has(b.role): _ai2[b.role] += 1
		if b._cover_phase == "peek": _ai2.peek += 1


func _aitest() -> void:
	L("AITEST: player hides in the security office; hall/corridor units are alerted by gunfire")
	_ai2_on = true
	# Office units are removed so the test measures units coming from outside.
	for b in main.director.bots:
		if Game.room_at(b.global_position + Vector3.UP) == "office":
			b.explosion_damage(9999.0, b.global_position)
	main.level.doors.D2.target = 0.0
	teleport(Vector3(-3.5, 0.05, -11.5), Vector3(6, 1.2, -8.5))
	player.bot_input.crouch_set = true
	await _wait(2.0)
	Game.emit_noise(Vector3(2.0, 0, -8.5), 60.0, player)
	main.director.report_sighting(null, Vector3(2.0, 0, -8.5))
	for b in main.director.bots:
		if b.state != Teslabot.S.DEAD:
			b.alert_to(Vector3(2.0, 0, -8.5))
	var t := 0.0
	while t < 22.0:
		await _wait(0.25)
		t += 0.25
		if is_equal_approx(fmod(t, 5.5), 0.0):
			for b in _bots():
				L("  t=%.1f %s state=%s role=%s pos=%s vis=%s cover=%s phase=%s entry=%s nav_done=%s" % [t, b.name, Teslabot.S.keys()[b.state], b.role, b.global_position.snapped(Vector3.ONE * 0.1), b.target_visible, b._cover.get("pos", "-"), b._cover_phase, b._entry.get("phase", "-"), b.agent.is_navigation_finished()])
	L("AITEST hunt (22 s): %s  D2 open=%s  god_absorbed=%.0f" % [_ai2, main.level.doors.D2.is_open(), Game.stats.get("god_absorbed", 0.0)])
	var near := 0
	for b in _bots():
		if b.global_position.distance_to(player.global_position) < 8.0:
			near += 1
	L("AITEST units within 8 m of the hidden player: %d / %d alive" % [near, _bots().size()])
	# Suppression: fire near (not at) the closest visible unit.
	var sup_before: int = _ai2.suppressed
	var target := _nearest_visible()
	if target:
		var tt := 0.0
		player.bot_input.fire = true
		while tt < 3.0:
			_look(target.bones.torso.global_position + Vector3(1.1, 0.4, 0))
			await _wait(0.05)
			tt += 0.05
			if player.weapon().ammo == 0:
				break
		player.bot_input.fire = false
		await _wait(1.0)
		L("AITEST near-miss fire: suppressed unit-frames +%d, target suppression=%.2f role=%s" % [_ai2.suppressed - sup_before, target.suppression, target.role])
	var push_before: int = _ai2.push
	player.weapon().ammo = 0
	player.weapon().start_reload()
	await _wait(1.5)
	L("AITEST reload push: push unit-frames +%d" % [_ai2.push - push_before])
	_ai2_on = false
	L("AITEST final: %s" % [_ai2])



# ------------------------------------------------------------------ robot animation capture
func _botanim() -> void:
	L("BOTANIM: walk, run, turn, hits, stagger, death (scripted drive)")
	main.hud.visible = false
	for b in main.director.bots:
		b.set_physics_process(false)
		b.global_position += Vector3(0, -50, 0)
	var bot: Teslabot = main.director.bots[0]
	bot.set_physics_process(true)
	bot.debug_drive = true
	bot.global_position = Vector3(2.6, 0.05, 8.3)
	bot.state = Teslabot.S.PATROL
	teleport(Vector3(6.3, 0.05, 12.6), Vector3(6.3, 1.1, 8.3))
	player.weapons[0].visible = false
	player.arms.visible = false
	_track_bot = bot
	await _wait(1.0)
	bot._go(Vector3(9.6, 0, 8.3), Teslabot.WALK)
	for i in 7:
		await _wait(1.0)
		L("  walk t=%d pos=%s vel=%.2f nav_done=%s next=%s" % [i, bot.global_position.snapped(Vector3.ONE * 0.1), Vector3(bot.velocity.x, 0, bot.velocity.z).length(), bot.agent.is_navigation_finished(), bot.agent.get_next_path_position().snapped(Vector3.ONE * 0.1)])
	bot._go(Vector3(2.8, 0, 8.6), Teslabot.RUN)
	await _wait(3.4)
	bot._stop()
	await _wait(0.6)
	for d in [Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(-1, 0, 0.3)]:
		bot.debug_face = d
		await _wait(0.9)
	bot.debug_face = (player.global_position - bot.global_position).normalized()
	bot.state = Teslabot.S.COMBAT
	bot.target_visible = true
	await _wait(0.8)
	var dir := (bot.global_position - player.global_position).normalized()
	for z in ["torso", "head", "arm_R", "leg_L"]:
		bot.take_damage(12.0, z, bot.bones.torso.global_position, dir, -dir, null)
		await _wait(0.55)
	bot.take_damage(60.0, "torso", bot.bones.torso.global_position, dir, -dir, null)
	await _wait(1.4)
	bot.take_damage(900.0, "torso", bot.bones.torso.global_position, dir, -dir, null)
	await _wait(3.0)
	L("BOTANIM done: state=%s" % Teslabot.S.keys()[bot.state])


# ------------------------------------------------------------------ overwatch trigger test
func _aitest2() -> void:
	L("AITEST2: engage >=2 units in the hall, then break line of sight")
	for b in main.director.bots:
		if Game.room_at(b.global_position + Vector3.UP) != "hall":
			b.set_physics_process(false)
			b.global_position += Vector3(0, -50, 0)
			b.state = Teslabot.S.DEAD
	teleport(Vector3(13.2, 0.05, -2.6), Vector3(22, 1.5, -11))
	var t := 0.0
	while t < 20.0:
		await _wait(0.25)
		t += 0.25
		var eng: Array = main.director.engaged()
		if eng.size() >= 2:
			break
	L("  engaged units: %d after %.1f s" % [main.director.engaged().size(), t])
	# Break line of sight completely: into the corridor behind closed D3.
	main.level.doors.D3.target = 0.0
	main.level.doors.D3.open_angle = 0.0
	main.level.doors.D3.body.rotation.y = 0.0
	teleport(Vector3(7.5, 0.05, -14.5), Vector3(7.5, 1.4, -25))
	var roles := {}
	for i in 24:
		await _wait(0.5)
		var line := []
		for b in main.director.engaged():
			roles[b.role] = roles.get(b.role, 0) + 1
			line.append("%s/%s%s" % [b.role, "V" if b.target_visible else "-", "" if b._has_move else "(hold)"])
		if i % 4 == 0:
			L("  t+%.1f hidden_for=%.1f engaged=%d %s" % [(i + 1) * 0.5, main.director.hidden_for, main.director.engaged().size(), line])
	L("AITEST2 role samples while hidden: %s" % [roles])


# ------------------------------------------------------------------ environment audit
## Lists placed props (top-level nodes with meshes) whose world AABBs
## intersect walls or other props, float above / sink into the floor, and
## checks key navigation routes.
func _audit() -> void:
	var lvl: Node3D = main.level
	var items := []   # [name, aabb, is_struct]
	for parent in [lvl, lvl.nav]:
		for c in parent.get_children():
			if not (c is Node3D) or c.name == "Dynamic" or c is Light3D or c is Decal or c is NavigationRegion3D or c is StaticBody3D or c is ReflectionProbe or c is Area3D:
				continue
			if not (c as Node3D).visible:
				continue
			var aabb: AABB = lvl._world_aabb(c)
			if aabb.size.length() < 0.05:
				continue
			var is_box: bool = c is MeshInstance3D and (c as MeshInstance3D).mesh is BoxMesh
			var nm: String = c.name if not is_box else "box"
			items.append([nm, aabb, is_box])
	L("AUDIT items: %d" % items.size())
	# Prop vs prop / prop vs wall-box overlaps (skip floors/ceilings/huge boxes)
	var hits := []
	for i in items.size():
		var a: Array = items[i]
		if a[2]:
			continue
		for j in items.size():
			if i == j:
				continue
			var b: Array = items[j]
			if not b[2] and j < i:
				continue
			var bb: AABB = b[1]
			if b[2] and (bb.size.y < 0.06 or bb.size.x * bb.size.z > 60.0):
				continue   # floor overlays, slabs, ceilings
			var ia: AABB = (a[1] as AABB).intersection(bb)
			var vol := ia.size.x * ia.size.y * ia.size.z
			if vol > 0.004:
				hits.append([vol, "%s @%s  x  %s @%s  vol=%.3f" % [a[0], (a[1] as AABB).get_center().snapped(Vector3.ONE * 0.05), b[0], bb.get_center().snapped(Vector3.ONE * 0.05), vol]])
	hits.sort_custom(func(x, y): return x[0] > y[0])
	for h in hits.slice(0, 70):
		L("  OVERLAP " + h[1])
	# Floating / sunk props (not wall- or ceiling-mounted by intent)
	for it in items:
		if it[2]:
			continue
		var bb: AABB = it[1]
		if bb.position.y < -0.06 and bb.end.y < 2.0:
			L("  SUNK %s @%s bottom=%.2f" % [it[0], bb.get_center().snapped(Vector3.ONE * 0.05), bb.position.y])
		elif bb.position.y > 0.04 and bb.position.y < 0.6 and bb.size.y < 2.5:
			L("  FLOAT? %s @%s bottom=%.2f" % [it[0], bb.get_center().snapped(Vector3.ONE * 0.05), bb.position.y])
	# Navigation: key routes and patrol points
	var map := get_viewport().world_3d.navigation_map
	var routes := [["dock->console", Vector3(8, 0, 11), Vector3(27, 0, -35.5)], ["dock->office", Vector3(8, 0, 11), Vector3(-2, 0, -8)],
		["hall->servers", Vector3(20, 0, -11.5), Vector3(15.3, 0, -33)], ["corridor->control", Vector3(7.5, 0, -20), Vector3(27, 0, -29)],
		["control->lift", Vector3(27, 0, -29), Vector3(3, 0, 11.5)], ["corridor->pump", Vector3(7.5, 0, -20), Vector3(-15, 0, -11)],
		["hall->switchgear", Vector3(20, 0, -18), Vector3(40, 0, -18)], ["pump gallery", Vector3(-15, 0, -23), Vector3(-12, 4.2, -28.8)],
		["switchgear gallery", Vector3(40, 0, -7), Vector3(49, 4.2, -21.5)]]
	for r in routes:
		var path := NavigationServer3D.map_get_path(map, r[1], r[2], true)
		var endd: float = path[path.size() - 1].distance_to(r[2]) if path.size() > 0 else 999.0
		L("  NAV %s points=%d end_gap=%.2f %s" % [r[0], path.size(), endd, "OK" if endd < 1.0 else "BLOCKED"])
	for id in main.mission.specs:
		var s: Dictionary = main.mission.specs[id]
		for pp in s.patrol + [s.pos]:
			var sp := NavigationServer3D.map_get_closest_point(map, pp)
			if sp.distance_to(pp) > 0.8:
				L("  NAV patrol point off-mesh %s -> %s" % [pp, sp])


# ------------------------------------------------------------------ fix verification spots
func _spots() -> void:
	main.hud.visible = false
	player.weapons[0].visible = false
	player.arms.visible = false
	for b in main.director.bots:
		b.set_physics_process(false)
		b.global_position += Vector3(0, -50, 0)
	await _wait(5.0)
	var poses := [
		["v1_hose_cabinet", Vector3(3.2, 0.05, 4.0), Vector3(0.15, 1.2, 4.4)],
		["v2_dock_container_forklift", Vector3(7.5, 0.05, 6.0), Vector3(12.5, 1.2, 9.0)],
		["v3_dock_lift_overhead", Vector3(9.5, 0.05, 6.5), Vector3(3.0, 4.2, 11.5)],
		["v4_corridor_pipes", Vector3(7.4, 0.05, -5.5), Vector3(8.8, 2.8, -12.0)],
		["v5_control_mimic_racks", Vector3(25.0, 0.05, -30.5), Vector3(31.5, 2.0, -36.0)],
		["v6_slumped_unit", Vector3(27.6, 0.05, -9.5), Vector3(30.6, 0.6, -9.2)],
	]
	for p in poses:
		teleport(p[1], p[2])
		await _wait(1.2)
		await shot(p[0])
