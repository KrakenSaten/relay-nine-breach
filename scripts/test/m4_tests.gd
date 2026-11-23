extends RefCounted
## M4 verification modes, driven by the autopilot (validation builds only).
##   --m4mission  full objective chain with real interactions (god mode)
##   --m4cp       death -> restart from checkpoint -> restored-state checks
##   --m4nav      robots physically traverse every new route
##   --m4ai       steam blinding, leash, gallery sentry, dormant/wake
##   --m4spots    still captures of the new areas
##   --m4video    scripted capture sequence for --write-movie
## Every teleport and time skip is written to the log.

var ap
var main
var player: Player
var m: Mission
var lv: LevelBuilder


func _init(autopilot) -> void:
	ap = autopilot
	main = ap.main
	player = ap.player
	m = main.mission
	lv = main.level


func L(s: String) -> void:
	ap.L(s)


func W(t: float) -> void:
	await ap._wait(t)


func shot(n: String) -> void:
	await ap.shot(n)


func hold_at(pos: Vector3, look: Vector3, secs: float) -> void:
	ap.teleport(pos, look)
	await W(0.35)
	player.bot_input.interact = true
	await W(secs)
	player.bot_input.interact = false
	await W(0.25)


func wait_bake() -> void:
	var t := 0.0
	await W(0.1)
	while lv.nav.is_baking() and t < 30.0:
		await W(0.1)
		t += 0.1
	await W(0.5)   # navigation map sync
	L("  navmesh rebake finished (waited %.1f s)" % t)


func path_info(a: Vector3, b: Vector3) -> Dictionary:
	var map: RID = main.get_world_3d().navigation_map
	var p := NavigationServer3D.map_get_path(map, a, b, true)
	if p.is_empty():
		return {"len": 0.0, "gap": 999.0, "pts": p}
	var l := 0.0
	for i in range(1, p.size()):
		l += p[i].distance_to(p[i - 1])
	return {"len": l, "gap": p[p.size() - 1].distance_to(b), "pts": p}


func fire_at(target: Vector3, secs: float, until: Callable) -> void:
	var t := 0.0
	player.bot_input.aim = true
	player.bot_input.fire = true
	while t < secs and not until.call():
		ap._look(target)
		if player.weapon().ammo == 0:
			player.weapon().start_reload()
		await W(0.05)
		t += 0.05
	player.bot_input.fire = false
	player.bot_input.aim = false


func _ids_alive() -> Array:
	var out := []
	for id in m.bots:
		if m._alive(id):
			out.append(id)
	out.sort()
	return out


func _freeze_bots(except: Array = []) -> void:
	for b in main.director.bots:
		if b in except:
			continue
		b.set_physics_process(false)
		b.global_position += Vector3(0, -60, 0)


## Remove units entirely (squad separation is horizontal, so parked units
## would still push test units around).
func _remove_bots(except: Array = []) -> void:
	for b in main.director.bots.duplicate():
		if b in except:
			continue
		main.director.bots.erase(b)
		b.queue_free()
	m.bots.clear()


# ------------------------------------------------------------------ mission chain
func mission() -> void:
	L("M4 MISSION TEST: scripted run with real interactions, god mode. Teleports between objectives are logged.")
	L("start: stage=%s D5=%s D6=%s D11=%s bots=%d (dormant %d)" % [m.stage, lv.doors.D5.locked, lv.doors.D6.locked, lv.doors.D11.locked, main.director.bots.size(), main.director.bots.filter(func(b): return b.dormant).size()])
	L("console prompt before power: '%s'" % lv.console.get_prompt(player))
	var r := path_info(Vector3(8, 0, 11), Vector3(27, 0, -35.5))
	L("nav dock->console while sealed: gap=%.1f (%s)" % [r.gap, "blocked as intended" if r.gap > 1.0 else "UNEXPECTED PATH"])
	await W(5.0)
	# --- Objective A: lockdown panel (security office)
	await hold_at(Vector3(3.6, 0.05, -11.75), Vector3(3.6, 1.4, -12.85), 3.0)
	L("LOCKDOWN: flag=%s D5=%s D6=%s D11=%s objective='%s'" % [m.flags.lockdown, lv.doors.D5.locked, lv.doors.D6.locked, lv.doors.D11.locked, Game.objective_text])
	await wait_bake()
	r = path_info(Vector3(8, 0, 11), Vector3(27, 0, -35.5))
	L("nav dock->console after release: len=%.1f gap=%.2f %s" % [r.len, r.gap, "OK" if r.gap < 1.0 else "BLOCKED"])
	await shot("m4_01_lockdown_released")
	# --- Objective B: two main breakers (switchgear hall)
	await hold_at(Vector3(41.0, 0.05, -3.35), Vector3(41.0, 1.3, -2.15), 2.2)
	L("BREAKER A: power=%d thrown=%s" % [m.flags.power, m.ex.breakers[0].thrown])
	await shot("m4_02_breaker_a")
	await hold_at(Vector3(48.75, 4.25, -20.0), Vector3(49.85, 5.5, -20.0), 2.2)
	L("BREAKER B: power=%d stage=%s console powered=%s objective='%s'" % [m.flags.power, m.stage, lv.console.powered, Game.objective_text])
	await W(1.5)
	L("checkpoint: %s" % Game.checkpoint.get("name", "none"))
	# --- Upload
	await hold_at(Vector3(27.0, 0.05, -35.6), Vector3(27.0, 1.1, -37.0), 2.4)
	L("UPLOAD: uploading=%s state=%s" % [lv.console.uploading, Game.State.keys()[Game.state]])
	await W(4.0)
	await shot("m4_03_upload_defend")
	L("TIME SKIP: console progress forced to 0.98 to reach the complication")
	lv.console.progress = 0.98
	await W(1.6)
	L("COMPLICATION: stage=%s state=%s emergency=%s alarms=%d" % [m.stage, Game.State.keys()[Game.state], Game.emergency, m._alarms.size()])
	await shot("m4_04_complication_control")
	await W(1.5)
	L("  D3 locked=%s reason='%s'  d1 dormant=%s d2 dormant=%s  core defenders=%s" % [lv.doors.D3.locked, lv.doors.D3.lock_reason, m.bots.d1.is_dormant() if m._alive("d1") else "dead", m.bots.d2.is_dormant() if m._alive("d2") else "dead", [m._alive("k2"), m._alive("k3"), m._alive("k4")]])
	await wait_bake()
	ap.teleport(Vector3(15.5, 0.05, -33.2), Vector3(15.5, 1.7, -38.0))
	await W(2.2)
	L("  blast door opened=%s" % m.ex.blast_door.opened)
	await shot("m4_05_blast_door_open")
	r = path_info(Vector3(15, 0, -31), Vector3(22, 0, -46))
	L("nav servers->core: len=%.1f gap=%.2f %s" % [r.len, r.gap, "OK" if r.gap < 1.0 else "BLOCKED"])
	r = path_info(Vector3(7.5, 0, -14), Vector3(20, 0, -11.5))
	L("nav corridor->hall with D3 sealed: len=%.1f (detour expected, direct ~13 m)" % r.len)
	await W(3.0)
	L("checkpoint: %s" % Game.checkpoint.get("name", "none"))
	# --- Core: three capacitor stacks
	var vant := [[Vector3(16.3, 0.05, -41.2), 0], [Vector3(24.0, 0.05, -44.3), 1], [Vector3(26.6, 0.05, -58.2), 2]]
	for v in vant:
		var cap: M4Objects.CapacitorStack = m.ex.capacitors[v[1]]
		var aimp := cap.global_position + Vector3(0, 1.3, 0)
		ap.teleport(v[0], aimp)
		await W(0.3)
		await fire_at(aimp, 9.0, func(): return cap.dead)
		L("  capacitor %d dead=%s caps=%s" % [v[1], cap.dead, m.flags.caps])
		if v[1] == 2:
			await W(0.4)
			await shot("m4_06_core_overload")
	await W(6.0)
	L("CORE DOWN: stage=%s state=%s hall lit=%s dock lit=%s lift panel active=%s objective='%s'" % [m.stage, Game.State.keys()[Game.state], Game.rooms.hall.lit, Game.rooms.dock.lit, m.ex.lift_panel.active, Game.objective_text])
	await shot("m4_07_core_dead")
	await W(4.0)
	L("checkpoint: %s  alive units: %s" % [Game.checkpoint.get("name", "none"), _ids_alive()])
	# --- Extraction: call the lift, hold, board
	await hold_at(Vector3(1.25, 0.05, 8.6), Vector3(0.3, 1.1, 8.6), 2.5)
	L("LIFT CALLED: stage=%s lift_t=%.1f" % [m.stage, m._lift_t])
	await W(5.0)
	await shot("m4_08_hold_the_dock")
	L("TIME SKIP: lift countdown forced to 1 s")
	m._lift_t = 1.0
	await W(1.6)
	L("LIFT ARRIVED: stage=%s objective='%s'" % [m.stage, Game.objective_text])
	ap.teleport(Vector3(3.0, 0.1, 11.8), Vector3(8.0, 1.5, 6.0))
	await W(3.0)
	L("BOARDED: state=%s stage=%s checkpoint cleared=%s" % [Game.State.keys()[Game.state], m.stage, Game.checkpoint.is_empty()])
	await shot("m4_09_extracted")
	L("M4 MISSION TEST done. stats %s, elapsed %.0f s (includes time skips)" % [Game.stats, Game.elapsed()])


# ------------------------------------------------------------------ checkpoint restore
func checkpoint_test() -> void:
	var cp: Dictionary = Game.checkpoint
	if cp.has("test_expect"):
		await _cp_phase_b(cp)
		return
	L("CHECKPOINT TEST phase A: reach the relay-core checkpoint, then die")
	await W(3.0)
	L("SHORTCUT: objectives completed by emitting the station signals (interaction itself is covered by --m4mission)")
	m.ex.lockdown_panel.done.emit()
	m.ex.breakers[0].done.emit()
	m.ex.breakers[1].done.emit()
	await W(1.5)
	L("  checkpoint after objectives: %s" % Game.checkpoint.get("name", "none"))
	# Kill two garrison units before the next checkpoint: they must stay dead.
	for id in ["h1", "c1"]:
		if m._alive(id):
			m.bots[id].take_damage(9999.0, "torso", m.bots[id].global_position, Vector3.FORWARD, Vector3.UP, player)
	lv.console.uploading = true
	lv.console.connected.emit()
	await W(1.0)
	L("SHORTCUT: console progress forced to 0.98")
	lv.console.progress = 0.98
	await W(5.5)
	m.ex.capacitors[0].destroy()
	await W(3.0)
	L("  checkpoint now: %s stage=%s caps=%s" % [Game.checkpoint.get("name", "none"), Game.checkpoint.get("stage", ""), Game.checkpoint.get("flags", {}).get("caps", [])])
	var expect := {"stage": Game.checkpoint.stage, "alive": Game.checkpoint.bots.map(func(e): return e.id), "kills": Game.checkpoint.stats.kills, "respawn": Game.checkpoint.respawn.origin}
	expect.alive.sort()
	Game.checkpoint["test_expect"] = expect
	L("  expected after restore: %s" % [expect])
	player.bot_input.god = false
	player.take_damage(9999.0, player.global_position + Vector3.FORWARD)
	await W(3.0)
	L("  player alive=%s state=%s" % [player.alive, Game.State.keys()[Game.state]])
	main.menus.open("failed")
	await W(0.4)
	await shot("m4_cp_failed_screen")
	main.menus.hide_all()
	ap._write_log_named("m4cp_phaseA_log.txt")
	L("restarting from checkpoint (scene reload)")
	main.menus._restart_checkpoint()


func _cp_phase_b(cp: Dictionary) -> void:
	var e: Dictionary = cp.test_expect
	L("CHECKPOINT TEST phase B: scene reloaded from checkpoint '%s'" % cp.name)
	await W(2.0)
	var alive := _ids_alive()
	var ok_alive: bool = alive == e.alive
	L("  stage=%s (expect %s) state=%s" % [m.stage, e.stage, Game.State.keys()[Game.state]])
	L("  D3 locked=%s blast door open=%s emergency=%s D5 locked=%s console done=%s" % [lv.doors.D3.locked, m.ex.blast_door.opened, Game.emergency, lv.doors.D5.locked, lv.console.done])
	L("  capacitors dead=%s flags=%s" % [m.ex.capacitors.map(func(c): return c.dead), m.flags.caps])
	L("  units alive=%s match=%s" % [alive, ok_alive])
	if not ok_alive:
		L("  expected units=%s" % [e.alive])
	L("  dormant left=%s  kills=%d (expect %d)  player at %s (respawn %s) alive=%s" % [main.director.bots.filter(func(b): return b.is_dormant()).size(), Game.stats.kills, e.kills, player.global_position.snapped(Vector3.ONE * 0.01), e.respawn, player.alive])
	var r := path_info(Vector3(15, 0, -31), Vector3(22, 0, -46))
	L("  nav servers->core after restore: gap=%.2f %s" % [r.gap, "OK" if r.gap < 1.0 else "BLOCKED"])
	await shot("m4_cp_restored")
	var pass_all: bool = m.stage == e.stage and ok_alive and lv.doors.D3.locked and m.ex.blast_door.opened and m.ex.capacitors[0].dead and not m.ex.capacitors[1].dead and Game.stats.kills == e.kills and player.alive
	L("CHECKPOINT RESTORE %s" % ("PASS" if pass_all else "FAIL"))
	Game.checkpoint.erase("test_expect")


# ------------------------------------------------------------------ navigation
func nav() -> void:
	L("M4 NAV TEST: late-game topology (lockdown released, blast door open); test units drive each route")
	m.ex.lockdown_panel.done.emit()
	lv.nav_unblock("blast")
	m.ex.blast_door.open_now(true)
	lv.rebake()
	await wait_bake()
	_remove_bots()
	await W(0.2)
	var routes := [
		["corridor->D2->office->D8->pump", Vector3(7.5, 0, -20), Vector3(-15, 0, -11)],
		["corridor N->D9->tunnel->D9b->pump", Vector3(7.5, 0, -28.4), Vector3(-12, 0, -25.5)],
		["pump floor->stair->gallery", Vector3(-15, 0, -23), Vector3(-12, 4.2, -28.8)],
		["gallery->stair->pump floor (over channel)", Vector3(-20, 4.2, -28.8), Vector3(-15, 0, -6.0)],
		["pump->D8->office", Vector3(-10, 0, -10), Vector3(0, 0, -8)],
		["office->D2->corridor->D1->dock", Vector3(0, 0, -8), Vector3(6, 0, 8)],
		["hall->D10->switchgear", Vector3(20, 0, -18), Vector3(40, 0, -18)],
		["switchgear floor->stair->gallery", Vector3(40, 0, -7), Vector3(49, 4.2, -21.5)],
		["switchgear->D11->control", Vector3(36, 0, -27.5), Vector3(27, 0, -30)],
		["servers->blast door->core", Vector3(15, 0, -32), Vector3(22, 0, -46)],
		["core: around the dais", Vector3(16, 0, -50), Vector3(28, 0, -58)],
		["core->servers->D7->corridor->dock", Vector3(22, 0, -46), Vector3(8, 0, 6)],
	]
	var passed := 0
	for r in routes:
		var info := path_info(r[1], r[2])
		var b := Teslabot.new()
		main.director.register(b)
		main.add_child(b)
		b.global_position = main.director.snap(r[1]) + Vector3(0, 0.05, 0)
		b.debug_drive = true
		await W(0.3)
		b._go(main.director.snap(r[2]), Teslabot.RUN)
		var limit: float = info.len / Teslabot.RUN * 2.2 + 6.0
		var t := 0.0
		var best := INF
		var still := 0.0
		var worst_still := 0.0
		var last := b.global_position
		var stall_at := Vector3.ZERO
		while t < limit:
			await W(0.25)
			t += 0.25
			var d: float = b.global_position.distance_to(main.director.snap(r[2]))
			best = minf(best, d)
			if b.global_position.distance_to(last) < 0.15:
				still += 0.25
				if still >= worst_still:
					stall_at = b.global_position
				worst_still = maxf(worst_still, still)
			else:
				still = 0.0
			last = b.global_position
			if d < 1.2:
				break
		var ok := best < 1.2
		passed += 1 if ok else 0
		L("  ROUTE %-42s path=%5.1f m gap=%.2f  robot %s in %.1f s (closest %.2f m, longest stall %.1f s%s)" % [r[0], info.len, info.gap, "ARRIVED" if ok else "FAILED", t, best, worst_still, (" at %s" % stall_at.snapped(Vector3.ONE * 0.1)) if worst_still > 1.0 else ""])
		if not ok:
			ap.teleport(b.global_position + Vector3(0, 0.05, 2.5), b.global_position + Vector3(0, 1.2, 0))
			await W(0.5)
			await shot("navfail_" + str(routes.find(r)))
		b.queue_free()
		main.director.bots.erase(b)
		await W(0.2)
	L("ROUTES %d/%d traversed" % [passed, routes.size()])
	# The crawlway must stay player-only.
	var cr := path_info(Vector3(1.5, 0, 2.0), Vector3(-10, 0, -5))
	var through := false
	for p in cr.pts:
		if Game.room_at(p + Vector3.UP * 0.5) == "crawl":
			through = true
	L("  crawlway dock->pump: robot path length %.1f m (straight line 13 m), passes through crawl=%s -> %s" % [cr.len, through, "OK (units cannot use it)" if not through else "FAIL"])
	# Patrol points and posts on the navmesh
	var off := 0
	for id in m.specs:
		var s: Dictionary = m.specs[id]
		for p in [s.pos] + s.patrol:
			if main.director.snap(p).distance_to(p) > 0.8:
				off += 1
				L("  off-mesh point %s %s -> %s" % [id, p, main.director.snap(p)])
	L("  spawn/patrol points off the navmesh: %d" % off)


# ------------------------------------------------------------------ encounter behaviour
func ai() -> void:
	L("M4 AI TEST: steam blinding, leash, gallery sentry, dormant units")
	await W(4.0)
	var p2: Teslabot = m.bots.p2
	var keep := [p2, m.bots.g1, m.bots.p1, m.bots.d1]
	_freeze_bots(keep)
	# --- steam: same unit, same distance, with and without steam
	p2.patrol_points = []
	p2.global_position = main.director.snap(Vector3(-15, 0, -11.5))
	ap.teleport(Vector3(-15, 0.05, -4.8), p2.global_position + Vector3(0, 1.5, 0))
	p2.debug_face = Vector3(0, 0, 1)
	p2.awareness = 0.0
	p2._set_state(Teslabot.S.PATROL)
	await W(2.0)
	L("  steam OFF: p2 awareness=%.2f state=%s visible=%s" % [p2.awareness, Teslabot.S.keys()[p2.state], p2.target_visible])
	p2.awareness = 0.0
	p2._set_state(Teslabot.S.PATROL)
	main.director.alert_level = 0.0
	ap.teleport(Vector3(-6.9, 0.05, -18.5), Vector3(-6.15, 1.4, -18.5))
	await W(0.3)
	player.bot_input.interact = true
	await W(1.5)
	player.bot_input.interact = false
	L("  steam valve used: pump obscured=%s" % Game.room_obscured("pump"))
	p2.awareness = 0.0
	p2._set_state(Teslabot.S.PATROL)
	ap.teleport(Vector3(-15, 0.05, -4.8), p2.global_position + Vector3(0, 1.5, 0))
	await W(2.0)
	L("  steam ON:  p2 awareness=%.2f state=%s visible=%s" % [p2.awareness, Teslabot.S.keys()[p2.state], p2.target_visible])
	await shot("m4_ai_steam")
	p2.debug_face = Vector3.ZERO
	# --- leash: a posted unit alerted far away stays near its post
	var g1: Teslabot = m.bots.g1
	ap.teleport(Vector3(-20, 0.05, -20), Vector3(-15, 1, -20))
	g1.alert_to(Vector3(20, 0, -10))
	var far := 0.0
	for i in 40:
		await W(0.25)
		far = maxf(far, Vector2(g1.global_position.x - g1.post.x, g1.global_position.z - g1.post.z).length())
	L("  leash: g1 alerted to the hall (~22 m away): max distance from post %.1f m (leash %.1f) state=%s -> %s" % [far, g1.leash, Teslabot.S.keys()[g1.state], "OK" if far <= g1.leash + 0.8 else "FAIL"])
	# --- sentry stays on the gallery
	var p1: Teslabot = m.bots.p1
	p1.alert_to(Vector3(-15, 0, -8))
	var min_y := 99.0
	for i in 32:
		await W(0.25)
		min_y = minf(min_y, p1.global_position.y)
	L("  sentry: p1 alerted to the pump floor: min height %.2f m (gallery 4.2) -> %s" % [min_y, "OK" if min_y > 3.5 else "FAIL"])
	# --- dormant ignores noise, then wakes
	var d1: Teslabot = m.bots.d1
	Game.emit_noise(d1.global_position, 30.0, player)
	await W(2.0)
	L("  dormant: after gunfire-level noise at 0 m: dormant=%s state=%s" % [d1.is_dormant(), Teslabot.S.keys()[d1.state]])
	ap.teleport(Vector3(25.0, 0.05, -6.5), d1.bones.head.global_position)
	await W(0.5)
	d1.wake(player.global_position)
	await W(0.9)
	await shot("m4_ai_wake")
	await W(2.5)
	L("  woken: dormant=%s state=%s awareness=%.2f" % [d1.is_dormant(), Teslabot.S.keys()[d1.state], d1.awareness])


# ------------------------------------------------------------------ captures
func spots() -> void:
	main.hud.visible = false
	for b in main.director.bots:
		b.set_physics_process(false)
	await W(6.0)
	var lit := [
		["m4s_01_pump_from_gallery", Vector3(-7.2, 4.25, -28.9), Vector3(-17.5, 0.5, -12.0)],
		["m4s_02_pump_floor_stair", Vector3(-8.6, 0.05, -9.2), Vector3(-21.0, 3.2, -27.0)],
		["m4s_03_pump_channel", Vector3(-22.6, 0.05, -10.2), Vector3(-9.0, 0.2, -7.6)],
		["m4s_06_tunnel", Vector3(4.6, 0.05, -28.5), Vector3(-6.0, 1.2, -28.5)],
		["m4s_07_switchgear_from_gallery", Vector3(49.0, 4.25, -5.5), Vector3(37.0, 1.0, -22.0)],
		["m4s_08_switchgear_aisle", Vector3(33.6, 0.05, -12.5), Vector3(44.0, 1.2, -12.5)],
		["m4s_09_transformers", Vector3(42.0, 0.05, -17.5), Vector3(42.0, 2.6, -27.0)],
		["m4s_10_breaker_a", Vector3(40.0, 0.05, -4.3), Vector3(41.0, 1.3, -2.15)],
		["m4s_11_office_lockdown_panel", Vector3(3.0, 0.05, -10.3), Vector3(3.6, 1.4, -12.85)],
		["m4s_12_dock_crawl_mouth", Vector3(4.2, 0.05, 3.4), Vector3(0.0, 0.7, 2.0)],
		["m4s_13_blast_door_closed", Vector3(15.5, 0.05, -33.0), Vector3(15.5, 1.8, -38.0)],
	]
	for p in lit:
		ap.teleport(p[1], p[2])
		await W(1.4)
		await shot(p[0])
	player.bot_input.crouch_set = true
	for p in [["m4s_04_crawlway", Vector3(-1.5, 0.05, 2.0), Vector3(-10.0, 0.55, 2.0)], ["m4s_05_crawl_exit", Vector3(-10.0, 0.05, 0.4), Vector3(-10.0, 0.5, -8.0)]]:
		ap.teleport(p[1], p[2])
		await W(1.4)
		await shot(p[0])
	player.bot_input.crouch_set = false
	await W(0.6)
	m.ex.blast_door.open_now(true)
	for p in [["m4s_14_core_from_antechamber", Vector3(17.0, 0.05, -40.8), Vector3(22.0, 3.2, -52.0)],
			["m4s_15_core_corner", Vector3(30.2, 0.05, -60.2), Vector3(20.0, 3.0, -48.0)],
			["m4s_16_core_capacitor", Vector3(18.6, 0.05, -45.0), Vector3(15.5, 1.4, -47.5)]]:
		ap.teleport(p[1], p[2])
		await W(1.4)
		await shot(p[0])
	m._emergency_lighting(true)
	for p in [["m4s_17_emergency_hall", Vector3(13.0, 0.05, -4.0), Vector3(28.0, 2.0, -12.0)], ["m4s_18_emergency_pump", Vector3(-7.5, 0.05, -25.5), Vector3(-18.0, 1.5, -12.0)]]:
		ap.teleport(p[1], p[2])
		await W(1.6)
		await shot(p[0])
	for c in m.ex.capacitors:
		c.destroy(true)
	m.ex.core_glow.visible = false
	m._core_dark()
	m._blackout(true)
	ap.teleport(Vector3(18.6, 0.05, -45.0), Vector3(22.0, 2.0, -52.0))
	await W(1.6)
	await shot("m4s_19_core_dead_dark")
	player.toggle_nv()
	await W(1.0)
	await shot("m4s_20_core_dead_nv")
	ap.teleport(Vector3(20.0, 0.05, -20.0), Vector3(30.0, 1.2, -9.0))
	await W(1.2)
	await shot("m4s_21_hall_blackout_nv")
	player.toggle_nv()


# ------------------------------------------------------------------ video
func video() -> void:
	L("M4 VIDEO: scripted capture sequence (god mode). Cuts are teleports; time skips are logged.")
	main.hud.visible = true
	await W(5.0)
	# 1. Crawlway from the dock into the pump station (walked, crouched)
	ap.teleport(Vector3(1.6, 0.05, 2.0), Vector3(-10.0, 0.6, 2.0))
	player.bot_input.crouch_set = true
	await W(0.8)
	player.bot_input.move = Vector2(0, -1)
	var t := 0.0
	while player.global_position.x > -9.9 and t < 8.0:
		ap._look(Vector3(-12.0, 0.6, 2.0))
		await W(0.05)
		t += 0.05
	t = 0.0
	while player.global_position.z > -4.2 and t < 6.0:
		ap._look(player.camera.global_position + Vector3(0, -0.05, -5.0))
		await W(0.05)
		t += 0.05
	player.bot_input.move = Vector2.ZERO
	player.bot_input.crouch_set = false
	await W(1.0)
	# 2. Steam purge
	await hold_at(Vector3(-6.9, 0.05, -18.5), Vector3(-6.15, 1.4, -18.5), 1.5)
	ap._look(Vector3(-15.0, 1.6, -16.0))
	await W(4.5)
	# 3. Breaker B on the switchgear gallery
	L("CUT: switchgear gallery")
	m.ex.lockdown_panel.done.emit()
	m.ex.breakers[0].done.emit()
	await hold_at(Vector3(48.75, 4.25, -20.0), Vector3(49.85, 5.5, -20.0), 2.0)
	ap._look(Vector3(40.0, 1.0, -14.0))
	await W(2.5)
	# 4. Upload -> complication
	L("CUT: relay control; TIME SKIP: console progress forced to 0.97")
	await hold_at(Vector3(27.0, 0.05, -34.8), Vector3(27.0, 1.1, -37.0), 2.4)
	lv.console.progress = 0.97
	await W(2.6)
	ap.teleport(Vector3(15.5, 0.05, -33.4), Vector3(15.5, 1.7, -38.0))
	L("CUT: server room, blast door")
	await W(4.5)
	# 5. Core: two stacks pre-destroyed (logged), shoot the last
	L("CUT: core; TIME SKIP: capacitor stacks 1 and 2 destroyed by script")
	m.ex.capacitors[0].destroy()
	m.ex.capacitors[1].destroy()
	ap.teleport(Vector3(26.6, 0.05, -57.6), Vector3(22.0, 1.3, -59.5))
	await W(0.6)
	var cap: M4Objects.CapacitorStack = m.ex.capacitors[2]
	await fire_at(cap.global_position + Vector3(0, 1.3, 0), 9.0, func(): return cap.dead)
	ap._look(m.ex.core_center + Vector3(0, 4.0, 0))
	await W(6.5)
	# 6. Lift
	L("CUT: dock; TIME SKIP: lift countdown forced to 3 s")
	await hold_at(Vector3(1.25, 0.05, 8.6), Vector3(0.3, 1.1, 8.6), 2.5)
	m._lift_t = 3.0
	ap._look(Vector3(3.0, 2.0, 12.0))
	await W(3.8)
	ap.teleport(Vector3(3.0, 0.1, 11.4), Vector3(8.0, 1.5, 4.0))
	await W(3.0)
	L("VIDEO done: state=%s" % Game.State.keys()[Game.state])
