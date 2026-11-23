extends RefCounted
## Ammunition cache checks (validation builds only).
##   --rv_ammo    pickups, carry limit, empty cache, interrupted hold, captures
##   --rv_ammocp  checkpoint: cache stock + carried ammo restored; restore floor

var ap
var main
var player: Player
var m: Mission


func _init(autopilot) -> void:
	ap = autopilot
	main = ap.main
	player = ap.player
	m = main.mission


func L(s: String) -> void:
	ap.L(s)


func W(t: float) -> void:
	await ap._wait(t)


func _ammo_str() -> String:
	var r: Weapon = player.weapons[0]
	var p: Weapon = player.weapons[1]
	return "rifle %d+%d  pistol %d+%d" % [r.ammo, r.reserve, p.ammo, p.reserve]


func _set_ammo(rm: int, rr: int, pm: int, pr: int) -> void:
	player.weapons[0].ammo = rm
	player.weapons[0].reserve = rr
	player.weapons[1].ammo = pm
	player.weapons[1].reserve = pr


func _use_cache(c: M4Objects.AmmoCache, secs := 1.4) -> void:
	var front: Vector3 = c.global_transform * Vector3(0, 0, 1.25)
	ap.teleport(Vector3(front.x, 0.05, front.z), c.global_position + Vector3.UP * 0.5)
	await W(0.4)
	L("    prompt: '%s'" % c.get_prompt(player))
	player.bot_input.interact = true
	await W(secs)
	player.bot_input.interact = false
	await W(0.3)


func ammo() -> void:
	L("REVIEW ammunition caches (god mode)")
	for b in main.director.bots:
		b.set_physics_process(false)
		b.set_process(false)
		b.global_position += Vector3(0, -80, 0)
	main.hud.visible = true
	await W(4.0)
	var cs: Array = m.ex.caches
	for c in cs:
		L("  CACHE %-22s at %s stock %s  (player start: %s)" % [c.cache_name, c.global_position.snapped(Vector3.ONE * 0.1), c.stock_text(), _ammo_str()])
	var a: M4Objects.AmmoCache = cs[0]
	var bsw: M4Objects.AmmoCache = cs[1]
	var cc: M4Objects.AmmoCache = cs[2]
	# 1. Full player: nothing to take, nothing taken.
	await _use_cache(a)
	L("  1 full player at office cache: %s | stock %s -> %s" % [_ammo_str(), a.stock_text(), "OK" if a.rifle == 60 and a.pistol == 30 else "FAIL"])
	await ap.shot("ammo_01_office_full_stock")
	# 2. Low player takes the whole office cache.
	_set_ammo(30, 20, 15, 10)
	await _use_cache(a)
	var ok2: bool = player.weapons[0].reserve == 80 and player.weapons[1].reserve == 40 and a.rifle == 0 and a.pistol == 0
	L("  2 low player at office cache: %s | stock %s -> %s" % [_ammo_str(), a.stock_text(), "OK" if ok2 else "FAIL"])
	await ap.shot("ammo_02_office_emptied")
	# 3. Anti-farming: holding at the empty cache gives nothing.
	_set_ammo(30, 0, 15, 0)
	await _use_cache(a, 2.5)
	L("  3 empty cache, repeated hold: %s -> %s" % [_ammo_str(), "OK" if player.weapons[0].reserve == 0 and player.weapons[1].reserve == 0 else "FAIL"])
	# 4. Carry limit: only tops up to the starting reserve; the rest stays in the cache.
	_set_ammo(30, 140, 15, 55)
	await _use_cache(cc)
	var ok4: bool = player.weapons[0].reserve == 150 and player.weapons[1].reserve == 60 and cc.rifle == 80 and cc.pistol == 25
	L("  4 near-full player at control cache: %s | stock %s -> %s" % [_ammo_str(), cc.stock_text(), "OK" if ok4 else "FAIL"])
	await _use_cache(cc)
	L("  4b at the limit: '%s' stock %s -> %s" % [cc.get_prompt(player), cc.stock_text(), "OK" if cc.rifle == 80 and cc.pistol == 25 else "FAIL"])
	await ap.shot("ammo_03_control_partial")
	# 5. Partial: rifle short, pistol full.
	_set_ammo(30, 100, 15, 60)
	await _use_cache(bsw)
	var ok5: bool = player.weapons[0].reserve == 150 and player.weapons[1].reserve == 60 and bsw.rifle == 10 and bsw.pistol == 15
	L("  5 rifle-only top-up at switchgear cache: %s | stock %s -> %s" % [_ammo_str(), bsw.stock_text(), "OK" if ok5 else "FAIL"])
	await ap.shot("ammo_04_switchgear_partial")
	# 6. Interrupted hold gives nothing.
	_set_ammo(30, 0, 15, 0)
	var front: Vector3 = bsw.global_transform * Vector3(0, 0, 1.25)
	ap.teleport(Vector3(front.x, 0.05, front.z), bsw.global_position + Vector3.UP * 0.5)
	await W(0.4)
	player.bot_input.interact = true
	await W(0.5)
	player.bot_input.interact = false
	await W(0.4)
	L("  6 hold released at 0.5 s: %s stock %s -> %s" % [_ammo_str(), bsw.stock_text(), "OK" if player.weapons[0].reserve == 0 and bsw.rifle == 10 else "FAIL"])
	# 7. Findability in the blackout.
	m._emergency_lighting(true)
	m._blackout(true)
	ap.teleport(Vector3(26.0, 0.05, -30.5), cc.global_position + Vector3.UP * 0.6)
	await W(2.0)
	await ap.shot("ammo_05_control_cache_blackout")
	ap.teleport(Vector3(3.0, 0.05, -10.0), a.global_position + Vector3.UP * 0.6)
	await W(1.2)
	await ap.shot("ammo_06_office_cache_empty_dark")


func ammo_cp() -> void:
	var cp: Dictionary = Game.checkpoint
	var phase: int = cp.get("rv_ammo_phase", 0)
	var cs: Array = m.ex.caches
	if phase == 0:
		L("AMMO-CP phase A: take from the office cache, reach the objectives checkpoint, then use the switchgear cache and die")
		await W(3.0)
		_set_ammo(30, 30, 15, 30)
		await _use_cache(cs[0])
		m.ex.lockdown_panel.done.emit()
		m.ex.breakers[0].done.emit()
		m.ex.breakers[1].done.emit()
		await W(1.6)
		var saved := [[player.weapons[0].ammo, player.weapons[0].reserve], [player.weapons[1].ammo, player.weapons[1].reserve]]
		L("  checkpoint '%s' saved: player %s, caches %s" % [Game.checkpoint.get("name", ""), _ammo_str(), cs.map(func(c): return c.stock_text())])
		_set_ammo(30, 50, 15, 60)
		await _use_cache(cs[1])
		L("  after the checkpoint: switchgear cache %s, player %s (both must be undone by the restore)" % [cs[1].stock_text(), _ammo_str()])
		Game.checkpoint["rv_ammo_phase"] = 1
		Game.checkpoint["rv_expect"] = {"ammo": saved, "caches": [[0, 0], [60, 15], [90, 30]]}
	elif phase == 1:
		var e: Dictionary = cp.rv_expect
		await W(2.0)
		var got_c := cs.map(func(c): return [c.rifle, c.pistol])
		var got_a := [[player.weapons[0].ammo, player.weapons[0].reserve], [player.weapons[1].ammo, player.weapons[1].reserve]]
		var ok: bool = got_c == e.caches and got_a == e.ammo
		L("AMMO-CP phase B: caches %s (expect %s), player %s (expect %s) -> %s" % [got_c, e.caches, got_a, e.ammo, "PASS" if ok else "FAIL"])
		await ap.shot("ammo_cp_restored")
		L("  now saving a checkpoint with almost no ammunition (rifle 4+0, pistol 0+0)")
		_set_ammo(4, 0, 0, 0)
		m.save_checkpoint("floor test", player.global_transform)
		Game.checkpoint["rv_ammo_phase"] = 2
	else:
		await W(2.0)
		var r: Weapon = player.weapons[0]
		var p: Weapon = player.weapons[1]
		var ok3: bool = r.ammo + r.reserve >= Mission.RESTORE_MIN_RIFLE and p.ammo + p.reserve >= Mission.RESTORE_MIN_PISTOL and r.ammo == 4
		L("AMMO-CP phase C (restore floor): %s -> %s (floors rifle %d, pistol %d)" % [_ammo_str(), "PASS" if ok3 else "FAIL", Mission.RESTORE_MIN_RIFLE, Mission.RESTORE_MIN_PISTOL])
		Game.checkpoint.erase("rv_ammo_phase")
		return
	ap._write_log_named("rv_ammocp_phase%d.txt" % phase)
	player.bot_input.god = false
	player.take_damage(9999.0, player.global_position + Vector3.FORWARD)
	await W(2.5)
	main.menus._restart_checkpoint()
	Game.set_meta("rv_reload_pending", true)
