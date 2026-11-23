extends RefCounted
## Pre-playtest review checks (validation builds only).
##   --rv_doors   every door swung both ways: leaf vs colliders and visual props;
##                interactive/dynamic objects vs the level (the static audit skips them)
##   --rv_sweep   captures of views not covered by earlier capture sets
##   --rv_edge    robots chasing a player hidden in the crawlway; units vs sealed/locked doors
##   --rv_combat  sustained firefight after the complication (frame times, spikes)
##   --rv_reload  repeated scene reloads (restart mission / restart from checkpoint), then quit mid-sequence

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


func _visual_items() -> Array:
	var items := []
	for parent in [lv, lv.nav]:
		for c in parent.get_children():
			if not (c is Node3D) or c.name == "Dynamic" or c is Light3D or c is Decal or c is NavigationRegion3D or c is StaticBody3D or c is ReflectionProbe or c is Area3D or c is FogVolume:
				continue
			if not (c as Node3D).visible:
				continue
			if c is MeshInstance3D and (c as MeshInstance3D).mesh is BoxMesh:
				continue   # walls/floors are checked through their colliders
			var aabb: AABB = lv._world_aabb(c)
			if aabb.size.length() < 0.05:
				continue
			items.append([String(c.name), aabb])
	return items


func _phys_hits(xf: Transform3D, size: Vector3, exclude: Array) -> Array:
	var shape := BoxShape3D.new()
	shape.size = size
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.transform = xf
	q.collision_mask = 1
	q.exclude = exclude
	var out := []
	for h in main.get_world_3d().direct_space_state.intersect_shape(q, 12):
		var col: Object = h.collider
		var nm: String = (col as Node).name if col is Node else "?"
		var p: Vector3 = (col as Node3D).global_position if col is Node3D else Vector3.ZERO
		out.append("%s@%s" % [nm, p.snapped(Vector3.ONE * 0.05)])
	return out


# ------------------------------------------------------------------ doors + dynamic objects
func doors() -> void:
	L("REVIEW doors: each door at +100 and -100 degrees; leaf (minus 0.25 m at the hinge) vs colliders and visual props")
	for b in main.director.bots:
		b.set_physics_process(false)
		b.set_process(false)
		b.global_position += Vector3(0, -80, 0)
	await W(1.0)
	var items := _visual_items()
	var problems := 0
	for id in lv.doors:
		var d: Door = lv.doors[id]
		var was_locked := d.locked
		for sgn in [1.0, -1.0]:
			var ang: float = sgn * d.max_open[int(sgn)]
			d.target = ang
			d.open_angle = ang
			d.body.rotation.y = ang
			await main.get_tree().physics_frame
			await main.get_tree().physics_frame
			var len := d.width - 0.25
			var local := Transform3D(Basis(), Vector3(0.25 + len * 0.5, 1.05, 0.0))
			var xf: Transform3D = d.body.global_transform * local
			var hits := _phys_hits(xf, Vector3(len, 1.9, 0.07), [d.body.get_rid()])
			var leaf_aabb: AABB = d.body.global_transform * AABB(Vector3(0.25, 0.1, -0.035), Vector3(len, 1.85, 0.07))
			var vis := []
			for it in items:
				var ia: AABB = leaf_aabb.intersection(it[1])
				if ia.size.x * ia.size.y * ia.size.z > 0.003 and not String(it[0]).begins_with("door_frame"):
					vis.append("%s@%s" % [it[0], (it[1] as AABB).get_center().snapped(Vector3.ONE * 0.05)])
			var side := "+%.0f" % rad_to_deg(ang) if sgn > 0 else "%.0f" % rad_to_deg(ang)
			if hits.is_empty() and vis.is_empty():
				L("  %s %s: clear" % [id, side])
			else:
				problems += 1
				L("  %s %s: colliders %s | visual %s" % [id, side, hits, vis])
		d.target = 0.0
		d.open_angle = 0.0
		d.body.rotation.y = 0.0
		d.locked = was_locked
	L("DOORS with contacts: %d (of %d door/side cases)" % [problems, lv.doors.size() * 2])
	# Interactive / dynamic objects (absent from the static audit)
	var ex: Expansion = m.ex
	var objs := [["lockdown_panel", ex.lockdown_panel], ["breaker_A", ex.breakers[0]], ["breaker_B", ex.breakers[1]], ["lift_panel", ex.lift_panel], ["steam_valve", ex.steam_valve]]
	for i in ex.capacitors.size():
		objs.append(["capacitor_%d" % i, ex.capacitors[i]])
	for c in ex.caches:
		objs.append([c.cache_name.replace(" ", "_").to_lower(), c])
	for o in objs:
		var n: Node3D = o[1]
		var aabb: AABB = lv._world_aabb(n)
		var vis := []
		for it in items:
			var ia: AABB = aabb.intersection(it[1])
			if ia.size.x * ia.size.y * ia.size.z > 0.004:
				vis.append("%s@%s" % [it[0], (it[1] as AABB).get_center().snapped(Vector3.ONE * 0.05)])
		var hits := []
		for c in n.get_children():
			if c is CollisionShape3D:
				hits = _phys_hits(c.global_transform, (c.shape as BoxShape3D).size * 0.98, [n.get_rid()])
		L("  OBJ %-14s aabb %s..%s  visual %s  colliders %s" % [o[0], aabb.position.snapped(Vector3.ONE * 0.01), aabb.end.snapped(Vector3.ONE * 0.01), vis, hits])
	# Destroyed capacitor variants (debris reaches ~1.7 m)
	for i in ex.capacitors.size():
		ex.capacitors[i].destroy(true)
	await W(0.2)
	for i in ex.capacitors.size():
		var c: M4Objects.CapacitorStack = ex.capacitors[i]
		var aabb: AABB = lv._world_aabb(c.broken) if c.broken else AABB()
		var vis := []
		for it in items:
			var ia: AABB = aabb.intersection(it[1])
			if ia.size.x * ia.size.y * ia.size.z > 0.004:
				vis.append("%s@%s" % [it[0], (it[1] as AABB).get_center().snapped(Vector3.ONE * 0.05)])
		L("  OBJ capacitor_%d destroyed variant: visual %s" % [i, vis])
	# Blast door leaf parked open
	ex.blast_door.open_now(true)
	await main.get_tree().physics_frame
	var bd_aabb: AABB = lv._world_aabb(ex.blast_door.body)
	var vis2 := []
	for it in items:
		var ia: AABB = bd_aabb.intersection(it[1])
		if ia.size.x * ia.size.y * ia.size.z > 0.004 and not String(it[0]).begins_with("blast_door_frame"):
			vis2.append("%s@%s" % [it[0], (it[1] as AABB).get_center().snapped(Vector3.ONE * 0.05)])
	L("  OBJ blast door parked: aabb %s..%s visual %s" % [bd_aabb.position.snapped(Vector3.ONE * 0.01), bd_aabb.end.snapped(Vector3.ONE * 0.01), vis2])


# ------------------------------------------------------------------ visual sweep
func sweep() -> void:
	main.hud.visible = false
	for b in main.director.bots:
		b.set_physics_process(false)
		b.set_process(false)
		b.global_position += Vector3(0, -80, 0)
	await W(6.0)
	var poses := [
		["rv01_D8_office_side", Vector3(-3.4, 0.05, -7.0), Vector3(-6.0, 1.2, -7.0), []],
		["rv02_D8_pump_side_open", Vector3(-9.2, 0.05, -7.0), Vector3(-6.0, 1.2, -7.0), ["D8"]],
		["rv03_D9_corridor_side", Vector3(7.9, 0.05, -25.8), Vector3(6.0, 1.2, -28.5), []],
		["rv04_D9b_pump_side_open", Vector3(-9.0, 0.05, -26.2), Vector3(-6.0, 1.2, -28.5), ["D9b"]],
		["rv05_D10_hall_side_open", Vector3(28.6, 0.05, -18.0), Vector3(40.0, 1.4, -18.0), ["D10"]],
		["rv06_D10_switchgear_side", Vector3(35.2, 0.05, -18.0), Vector3(32.0, 1.2, -18.0), []],
		["rv07_D11_control_side", Vector3(30.2, 0.05, -28.0), Vector3(33.0, 1.2, -28.0), []],
		["rv08_D11_switchgear_side_open", Vector3(35.8, 0.05, -28.2), Vector3(30.0, 1.4, -28.0), ["D11"]],
		["rv09_pump_gallery_walk", Vector3(-18.5, 4.25, -28.9), Vector3(-7.0, 5.0, -28.9), []],
		["rv10_pump_stair_top", Vector3(-23.1, 4.25, -27.2), Vector3(-23.1, 2.0, -19.0), []],
		["rv11_switchgear_gallery_north", Vector3(49.0, 4.25, -28.6), Vector3(49.0, 4.8, -14.0), []],
		["rv12_breaker_B", Vector3(48.95, 4.25, -21.6), Vector3(49.85, 5.5, -20.0), []],
		["rv13_antechamber_back_of_frame", Vector3(17.2, 0.05, -41.4), Vector3(15.5, 1.8, -38.0), []],
		["rv14_server_sign_duct", Vector3(12.2, 0.05, -34.0), Vector3(12.0, 2.6, -38.0), []],
		["rv15_lift_call_panel", Vector3(2.2, 0.05, 8.0), Vector3(0.15, 1.2, 8.6), []],
		["rv16_office_D8_vent", Vector3(2.4, 0.05, -6.0), Vector3(-6.0, 2.0, -6.3), []],
		["rv17_pump_crawl_mouth", Vector3(-10.0, 0.05, -6.8), Vector3(-10.0, 0.6, -3.0), []],
		["rv18_core_north_behind_dais", Vector3(22.0, 0.05, -60.6), Vector3(22.0, 3.0, -52.0), []],
		["rv19_switchgear_transformer_cage_gap", Vector3(36.0, 0.05, -23.0), Vector3(42.0, 1.5, -27.0), []],
		["rv20_tunnel_from_pump", Vector3(-9.0, 0.05, -28.5), Vector3(6.0, 1.2, -28.5), ["D9b", "D9"]],
	]
	for p in poses:
		for id in p[3]:
			lv.doors[id].target = deg_to_rad(100.0)
		ap.teleport(p[1], p[2])
		await W(1.4)
		await ap.shot(p[0])
	player.bot_input.crouch_set = true
	for p in [["rv21_crawl_corner_west", Vector3(-6.5, 0.05, 2.0), Vector3(-11.0, 0.5, 2.0)], ["rv22_crawl_corner_from_south", Vector3(-10.0, 0.05, -1.8), Vector3(-10.0, 0.55, 3.0)]]:
		ap.teleport(p[1], p[2])
		await W(1.4)
		await ap.shot(p[0])
	player.bot_input.crouch_set = false
	await W(0.6)
	m.ex.blast_door.open_now(true)
	for c in m.ex.capacitors:
		c.destroy(true)
	for p in [["rv23_blast_door_open_server_side", Vector3(16.2, 0.05, -34.2), Vector3(17.6, 1.7, -38.0)], ["rv24_capacitor_destroyed", Vector3(25.6, 0.05, -48.6), Vector3(28.5, 0.9, -47.5)],
			["rv25_capacitor_destroyed_north", Vector3(19.0, 0.05, -57.8), Vector3(22.0, 0.9, -59.5)]]:
		ap.teleport(p[1], p[2])
		await W(1.4)
		await ap.shot(p[0])


# ------------------------------------------------------------------ robot edge cases
func _stall_watch(bots: Array, secs: float, label: String) -> Dictionary:
	var last := {}
	var still := {}
	var worst := {}
	var entered_crawl := 0
	var t := 0.0
	while t < secs:
		await W(0.25)
		t += 0.25
		for b in bots:
			if not is_instance_valid(b) or b.state == Teslabot.S.DEAD:
				continue
			if Game.room_at(b.global_position + Vector3.UP) == "crawl":
				entered_crawl += 1
			var p: Vector3 = b.global_position
			if last.has(b) and p.distance_to(last[b]) < 0.05 and b._has_move and not b.agent.is_navigation_finished():
				still[b] = still.get(b, 0.0) + 0.25
				worst[b] = maxf(worst.get(b, 0.0), still[b])
			else:
				still[b] = 0.0
			last[b] = p
	var w := 0.0
	var who := ""
	for b in worst:
		if worst[b] > w:
			w = worst[b]
			who = "%s@%s" % [b.spawn_id, (b.global_position as Vector3).snapped(Vector3.ONE * 0.1)]
	L("  %s: longest blocked push %.1f s (%s), crawl entries %d" % [label, w, who, entered_crawl])
	return {"worst": w, "crawl": entered_crawl}


func edge() -> void:
	L("REVIEW robot edge cases (god mode)")
	await W(3.0)
	# 1. Player hides in the crawlway; nearby units are told exactly where.
	player.bot_input.crouch_set = true
	ap.teleport(Vector3(-5.0, 0.05, 2.0), Vector3(-10.0, 0.6, 2.0))
	await W(1.0)
	var near := []
	for b in main.director.bots:
		if not b.is_dormant() and b.global_position.distance_to(player.global_position) < 30.0:
			near.append(b)
			b.alert_to(player.global_position)
	Game.emit_noise(player.global_position, 30.0, player)
	L("  crawl chase: %d units alerted to the player inside the crawlway" % near.size())
	var r1 := await _stall_watch(near, 20.0, "crawl chase")
	var at_mouth := 0
	for b in near:
		if is_instance_valid(b) and b.state != Teslabot.S.DEAD:
			var dmin := minf(b.global_position.distance_to(Vector3(0.5, 0, 2.0)), b.global_position.distance_to(Vector3(-10.0, 0, -4.0)))
			if dmin < 4.0:
				at_mouth += 1
	L("  crawl chase result: units within 4 m of a crawl mouth %d, god damage absorbed %.0f" % [at_mouth, Game.stats.get("god_absorbed", 0.0)])
	await ap.shot("rv_edge_crawl_chase")
	player.bot_input.crouch_set = false
	# 2. Locked control wing: units chase a player standing inside relay control.
	ap.teleport(Vector3(27.0, 0.05, -31.0), Vector3(21.0, 1.2, -32.0))
	await W(0.5)
	var srv := []
	for b in main.director.bots:
		if not b.is_dormant() and b.state != Teslabot.S.DEAD and b.global_position.distance_to(Vector3(15, 0, -31)) < 18.0:
			srv.append(b)
			b.alert_to(player.global_position)
	L("  locked wing: %d units alerted to a player behind sealed D5/D6/D11" % srv.size())
	await _stall_watch(srv, 14.0, "locked wing")
	# 3. Release lockdown, run the complication (D3 sealed), alert corridor/office units to the hall.
	m.ex.lockdown_panel.done.emit()
	m.ex.breakers[0].done.emit()
	m.ex.breakers[1].done.emit()
	await W(1.0)
	lv.console.uploading = true
	lv.console.connected.emit()
	lv.console.progress = 0.99
	var t := 0.0
	while m.stage != "core" and t < 15.0:
		await W(0.25)
		t += 0.25
	await W(3.0)
	ap.teleport(Vector3(20.0, 0.05, -11.0), Vector3(9.0, 1.2, -11.0))
	var west := []
	for b in main.director.bots:
		if not b.is_dormant() and b.state != Teslabot.S.DEAD and b.global_position.x < 9.0:
			west.append(b)
			b.alert_to(player.global_position)
	L("  sealed D3: %d units west of the hall alerted to the hall (D3 locked=%s)" % [west.size(), lv.doors.D3.locked])
	await _stall_watch(west, 18.0, "sealed D3 detour")
	var arrived := 0
	for b in west:
		if is_instance_valid(b) and b.state != Teslabot.S.DEAD and b.global_position.x > 9.0:
			arrived += 1
	L("  sealed D3 result: %d/%d reached the hall by another route; D3 still closed=%s" % [arrived, west.size(), not lv.doors.D3.is_open()])


# ------------------------------------------------------------------ heavy combat
func combat() -> void:
	L("REVIEW heavy combat (preset %s): complication state, all units alerted to relay control, scripted firing for 40 s" % Settings.PRESETS[Settings.quality])
	m.ex.lockdown_panel.done.emit()
	m.ex.breakers[0].done.emit()
	m.ex.breakers[1].done.emit()
	await W(1.0)
	ap.teleport(Vector3(26.0, 0.05, -29.6), Vector3(21.0, 1.2, -32.0))
	lv.console.uploading = true
	lv.console.connected.emit()
	await W(8.0)
	lv.console.progress = 0.99
	await W(4.0)
	for b in main.director.bots:
		if b.state != Teslabot.S.DEAD:
			if b.is_dormant():
				b.wake(player.global_position)
			b.alert_to(player.global_position)
	await W(3.0)
	var frames := []
	var spikes := []
	var t := 0.0
	var last_us := Time.get_ticks_usec()
	var kills0: int = Game.stats.kills
	Fx.events = {}
	ap.hitch_log = false
	player.bot_input.aim = true
	while t < 40.0:
		await main.get_tree().process_frame
		var now := Time.get_ticks_usec()
		var ft := (now - last_us) / 1e6
		last_us = now
		t += ft
		frames.append(ft)
		if ft > 0.033:
			spikes.append("%.0fms engaged=%d debris=%d %s" % [ft * 1000.0, main.director.engaged().size(), Teslabot._debris.size(), Fx.events])
		Fx.events = {}
		var tgt: Node = ap._nearest_visible()
		if tgt:
			ap._look(tgt.bones.torso.global_position + Vector3(0, 0.3, 0))
			player.bot_input.fire = true
		else:
			player.bot_input.fire = false
		if player.weapon().ammo == 0:
			player.weapon().start_reload()
	player.bot_input.fire = false
	player.bot_input.aim = false
	frames.sort()
	var n := frames.size()
	var sum := 0.0
	for f in frames:
		sum += f
	var k := maxi(1, n / 100)
	var worst := 0.0
	for i in k:
		worst += frames[n - 1 - i]
	L("COMBAT: frames=%d avg %.1f FPS, p95 %.1f ms, p99 %.1f ms, 1%% low %.1f FPS, frames >33 ms: %d, kills %d, alive %d, debris %d" % [n, n / sum, frames[int(n * 0.95)] * 1000.0, frames[int(n * 0.99)] * 1000.0, k / worst, spikes.size(), Game.stats.kills - kills0, ap._bots().size(), Teslabot._debris.size()])
	for s in spikes.slice(0, 10):
		L("  spike " + s)
	await ap.shot("rv_combat_end")


# ------------------------------------------------------------------ reload stress
func reload() -> void:
	var n: int = Game.get_meta("rv_reloads", 0)
	Game.set_meta("rv_reloads", n + 1)
	var mem := Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0
	L("RELOAD cycle %d: static mem %.0f MB, objects %d, nodes %d, resources %d, orphan nodes %d, stage=%s restoring=%s" % [n, mem,
		Performance.get_monitor(Performance.OBJECT_COUNT), Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT), Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT), m.stage, m.restoring])
	ap._write_log_named("rv_reload_%d.txt" % n)
	await W(4.0)
	if n >= 6:
		# Last cycle: start the complication and quit in the middle of it.
		m.ex.lockdown_panel.done.emit()
		m.ex.breakers[0].done.emit()
		m.ex.breakers[1].done.emit()
		lv.console.uploading = true
		lv.console.connected.emit()
		lv.console.progress = 0.995
		var t := 0.0
		while m.stage != "core" and t < 10.0:
			await W(0.2)
			t += 0.2
		await W(1.5)
		L("RELOAD final: quitting mid-complication (stage=%s, events pending=%d, alarms=%d)" % [m.stage, m._events.size(), m._alarms.size()])
		return
	if n % 2 == 1:
		m.ex.lockdown_panel.done.emit()
		m.ex.breakers[0].done.emit()
		m.ex.breakers[1].done.emit()
		await W(1.6)
		L("RELOAD: restart from checkpoint '%s'" % Game.checkpoint.get("name", "none"))
		main.menus._restart_checkpoint()
	else:
		L("RELOAD: restart mission")
		main.menus._restart()
	Game.set_meta("rv_reload_pending", true)


func _blast_state(tag: String) -> void:
	var bd: M4Objects.BlastDoor = m.ex.blast_door
	var mesh_x := 0.0
	var mis := bd.body.find_children("*", "MeshInstance3D", true, false)
	if not mis.is_empty():
		mesh_x = lv._world_aabb(bd.body).get_center().x
	var q := PhysicsRayQueryParameters3D.create(Vector3(15.5, 1.5, -36.8), Vector3(15.5, 1.5, -39.6), 1)
	var hit: Dictionary = main.get_world_3d().direct_space_state.intersect_ray(q)
	var blocked := "free"
	if hit:
		blocked = "BLOCKED by %s" % (hit.collider as Node).name
	L("  BLAST %s: opened=%s body.position=%s mesh centre x=%.2f ray through opening: %s" % [tag, bd.opened, bd.body.position.snapped(Vector3.ONE * 0.01), mesh_x, blocked])


func blast() -> void:
	L("REVIEW blast door: instant open (checkpoint restore path) and animated open (complication path)")
	for b in main.director.bots:
		b.set_physics_process(false)
		b.set_process(false)
		b.global_position += Vector3(0, -80, 0)
	main.hud.visible = false
	await W(4.0)
	await _blast_state("closed")
	ap.teleport(Vector3(15.25, 0.05, -34.0), Vector3(15.5, 1.6, -38.0))
	await W(1.0)
	await ap.shot("rv_blast_closed")
	m.ex.blast_door.open_now(false)
	for t in [0.5, 1.5, 3.0, 4.5]:
		await W(t if t == 0.5 else 1.5)
		await _blast_state("animated t~%.1f" % t)
	await ap.shot("rv_blast_open_animated")
	ap.teleport(Vector3(17.2, 0.05, -41.4), Vector3(15.5, 1.6, -38.0))
	await W(1.0)
	await ap.shot("rv_blast_open_from_antechamber")
	# Fresh instance of the instant path: reset and open instantly.
	var bd: M4Objects.BlastDoor = m.ex.blast_door
	bd.opened = false
	bd.body.position = bd._rest
	await main.get_tree().physics_frame
	await main.get_tree().physics_frame
	await _blast_state("reset")
	bd.open_now(true)
	await main.get_tree().physics_frame
	await _blast_state("instant +1 tick")
	await W(0.5)
	await _blast_state("instant +0.5 s")


# ------------------------------------------------------------------ extraction checkpoint restore
func cp_extract() -> void:
	var cp: Dictionary = Game.checkpoint
	if cp.has("rv_expect"):
		L("CP-EXTRACT phase B: restored from '%s' (stage %s)" % [cp.name, m.stage])
		await W(8.0)   # past the 5 s blackout delay of a (re-)run overload
		var xs := []
		for b in main.director.bots:
			if b.state != Teslabot.S.DEAD and String(b.spawn_id).begins_with("x"):
				xs.append(b.spawn_id)
		xs.sort()
		L("  extraction units alive: %s (expected at most %s)" % [xs, cp.rv_expect.x])
		L("  total units %d (expected %d), stage %s, state %s, lift panel active %s" % [main.director.bots.size(), cp.rv_expect.n, m.stage, Game.State.keys()[Game.state], m.ex.lift_panel.active])
		var ok: bool = xs.size() <= (cp.rv_expect.x as Array).size() and main.director.bots.size() == cp.rv_expect.n and m.stage == "extract"
		L("CP-EXTRACT RESTORE %s" % ("PASS" if ok else "FAIL"))
		Game.checkpoint.erase("rv_expect")
		return
	L("CP-EXTRACT phase A: core destroyed -> extraction checkpoint -> die")
	await W(3.0)
	m.ex.lockdown_panel.done.emit()
	m.ex.breakers[0].done.emit()
	m.ex.breakers[1].done.emit()
	await W(1.2)
	lv.console.uploading = true
	lv.console.connected.emit()
	lv.console.progress = 0.995
	var t := 0.0
	while m.stage != "core" and t < 15.0:
		await W(0.25)
		t += 0.25
	await W(4.0)
	for c in m.ex.capacitors:
		c.destroy()
	t = 0.0
	while Game.checkpoint.get("name", "") != "extraction" and t < 25.0:
		await W(0.25)
		t += 0.25
	var xs := []
	for e in Game.checkpoint.get("bots", []):
		if String(e.id).begins_with("x"):
			xs.append(e.id)
	Game.checkpoint["rv_expect"] = {"x": xs, "n": Game.checkpoint.get("bots", []).size()}
	L("  checkpoint '%s' saved, units in it %d, x-units %s" % [Game.checkpoint.get("name", ""), Game.checkpoint.get("bots", []).size(), xs])
	player.bot_input.god = false
	player.take_damage(9999.0, player.global_position + Vector3.FORWARD)
	await W(2.5)
	ap._write_log_named("rv_cpx_phaseA.txt")
	main.menus._restart_checkpoint()
	Game.set_meta("rv_reload_pending", true)


# ------------------------------------------------------------------ door traffic
func _drive(pos: Vector3, to: Vector3) -> Teslabot:
	var b := Teslabot.new()
	main.director.register(b)
	main.add_child(b)
	b.global_position = main.director.snap(pos) + Vector3(0, 0.05, 0)
	b.debug_drive = true
	b.set_meta("dest", main.director.snap(to))
	return b


func _traffic(label: String, door: Door, units: Array, secs: float) -> void:
	await W(0.3)
	for b in units:
		b._go(b.get_meta("dest"), Teslabot.WALK * 1.6)
	var flips := 0
	var last_t: float = door.target
	var t := 0.0
	var done := {}
	while t < secs and done.size() < units.size():
		await W(0.1)
		t += 0.1
		if not is_equal_approx(door.target, last_t):
			if signf(door.target) != signf(last_t) and absf(last_t) > 0.1:
				flips += 1
			last_t = door.target
		for b in units:
			if not done.has(b) and b.global_position.distance_to(b.get_meta("dest")) < 1.2:
				done[b] = t
	L("  TRAFFIC %-34s arrived %d/%d in %.1f s, door side flips %d" % [label, done.size(), units.size(), t, flips])
	for b in units:
		main.director.bots.erase(b)
		b.queue_free()
	door.target = 0.0
	await W(1.5)


func traffic() -> void:
	L("REVIEW door traffic: single crossing, two units opposite ways, three-unit file (test units, no AI)")
	for b in main.director.bots.duplicate():
		main.director.bots.erase(b)
		b.queue_free()
	m.bots.clear()
	ap.teleport(Vector3(20, 0.05, -14), Vector3(20, 1, -20))
	await W(2.0)
	var d2: Door = lv.doors.D2
	await _traffic("D2 single (corridor->office)", d2, [_drive(Vector3(7.5, 0, -12.5), Vector3(0, 0, -8))], 14.0)
	await _traffic("D2 opposite pair", d2, [_drive(Vector3(7.5, 0, -12.5), Vector3(0, 0, -8)), _drive(Vector3(1.0, 0, -7.0), Vector3(7.5, 0, -4.0))], 16.0)
	await _traffic("D2 file of three (corridor->office)", d2, [_drive(Vector3(7.5, 0, -12.0), Vector3(-1, 0, -9)), _drive(Vector3(7.5, 0, -14.0), Vector3(0, 0, -6)), _drive(Vector3(7.5, 0, -16.0), Vector3(1, 0, -10.5))], 18.0)
	var d10: Door = lv.doors.D10
	await _traffic("D10 opposite pair", d10, [_drive(Vector3(26.0, 0, -18.0), Vector3(38.0, 0, -19.0)), _drive(Vector3(38.0, 0, -19.5), Vector3(25.0, 0, -18.5))], 16.0)


func fixshots() -> void:
	main.hud.visible = false
	for b in main.director.bots:
		b.set_physics_process(false)
		b.set_process(false)
		b.global_position += Vector3(0, -80, 0)
	await W(5.0)
	var d1: Door = lv.doors.D1
	d1.target = -d1.max_open[-1]
	L("D1 swing limits: +%.0f / -%.0f deg; D7: +%.0f / -%.0f" % [rad_to_deg(d1.max_open[1]), rad_to_deg(d1.max_open[-1]), rad_to_deg(lv.doors.D7.max_open[1]), rad_to_deg(lv.doors.D7.max_open[-1])])
	await W(1.5)
	for p in [["fx_D1_open_into_dock_forklift", Vector3(9.5, 0.05, 3.2), Vector3(6.2, 1.0, 1.4)], ["fx_D1_open_top_view", Vector3(8.6, 2.6, 3.6), Vector3(6.4, 0.6, 1.0)],
			["fx_lift_panel_label", Vector3(1.6, 0.05, 8.6), Vector3(0.4, 1.6, 8.6)]]:
		ap.teleport(p[1], p[2])
		await W(1.2)
		await ap.shot(p[0])
	var d7: Door = lv.doors.D7
	d7.target = -d7.max_open[-1]
	ap.teleport(Vector3(7.2, 0.05, -26.0), Vector3(8.2, 1.2, -29.7))
	await W(1.5)
	await ap.shot("fx_D7_open_into_corridor")
	m.ex.blast_door.open_now(true)
	ap.teleport(Vector3(15.3, 0.05, -36.7), Vector3(20.5, 1.6, -37.7))
	await W(1.5)
	await ap.shot("fx_blast_leaf_parked")
