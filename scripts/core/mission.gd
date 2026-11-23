class_name Mission
extends Node
## M4 mission flow for Substation 9-B.
##   INFILTRATE  release the control-wing lockdown (security office) and close
##               both main breakers (switchgear hall), in either order
##   UPLOAD      connect the override at relay control and defend it (40 s)
##   COMPLICATION Relay Nine rejects the override: alarm, emergency lighting,
##               D3 slams sealed, the charge-bay units wake, the core opens
##   CORE        destroy the three capacitor stacks around the relay array
##   EXTRACT     blackout; reach the dock by any route and call Freight Lift 2
##   LIFT        hold the dock until the lift arrives, then board it
## Also owns the encounter roster and checkpoints (Game.checkpoint survives
## scene reloads, so "restart from checkpoint" rebuilds the level in the
## recorded state).

signal stage_changed(stage: String)

const LIFT_TIME := 25.0
const BOARD_TIME := 2.0

var main: Node
var level: LevelBuilder
var ex: Expansion
var director: Director
var stage := "infiltrate"
var flags := {"lockdown": false, "power": 0, "upload": false, "complication": false, "caps": [false, false, false], "core": false, "lift": false}
var specs := {}          # id -> spawn spec
var bots := {}           # id -> Teslabot
var restoring := false
var _alarms: Array = []
var _motor: AudioStreamPlayer3D
var _lift_t := -1.0
var _board_t := 0.0
var _obj_t := 0.0
var _events: Array = []  # [time_left, Callable, label]
var _arc_t := 5.0


func setup(m: Node, lvl: LevelBuilder) -> void:
	main = m
	level = lvl
	ex = lvl.expansion
	_define_encounters()
	# Red beacons for the M1-M3 rooms (the expansion places its own).
	for p in [Vector3(8.0, 5.2, 0.45), Vector3(7.5, 3.25, -10.0), Vector3(7.5, 3.25, -24.0), Vector3(0.0, 3.3, -3.45),
			Vector3(9.5, 6.0, -10.0), Vector3(31.5, 6.0, -20.0), Vector3(20.0, 7.0, -25.6), Vector3(15.0, 3.3, -26.5), Vector3(27.0, 4.1, -26.5)]:
		ex.emergency(p)
	# Doors sealed by the lockdown (the console room is reachable only once released).
	for id in ["D5", "D6", "D11"]:
		level.doors[id].set_locked(true, "SEALED - CONTROL-WING LOCKDOWN")
		level.nav_block_door(id)
	level.console.powered = false
	level.console.unpowered_text = "CONSOLE UNPOWERED - CLOSE BOTH MAIN BREAKERS (SWITCHGEAR HALL)"
	level.console.connected.connect(_on_console_connected)
	level.console.completed.connect(_on_console_completed)
	ex.lockdown_panel.done.connect(_on_lockdown)
	for i in ex.breakers.size():
		ex.breakers[i].done.connect(_on_breaker.bind(i))
	for i in ex.capacitors.size():
		ex.capacitors[i].destroyed.connect(_on_capacitor.bind(i))
	ex.lift_panel.done.connect(_on_lift_called)
	restoring = Game.checkpoint.get("pending", false)
	if restoring:
		_apply_world(Game.checkpoint.flags)


# ------------------------------------------------------------------ encounters
func _spec(id: String, pos: Vector3, opts := {}) -> void:
	var s := {"pos": pos, "patrol": [], "leash": 0.0, "face": Vector3.ZERO, "dormant": false, "hunt": false}
	s.merge(opts, true)
	specs[id] = s


func _define_encounters() -> void:
	# --- M1-M3 garrison (unchanged positions)
	_spec("o1", Vector3(-3, 0, -8), {"patrol": [Vector3(-3, 0, -8), Vector3(3.5, 0, -8), Vector3(3.5, 0, -11.3), Vector3(-4, 0, -11.3)]})
	_spec("o2", Vector3(4.2, 0, -4.2), {"leash": 4.0, "face": Vector3(-1, 0, -0.3)})
	_spec("c1", Vector3(7.5, 0, -22), {"patrol": [Vector3(7.5, 0, -27), Vector3(7.5, 0, -12)]})
	_spec("h1", Vector3(13, 0, -11.5), {"patrol": [Vector3(13, 0, -11.5), Vector3(24.5, 0, -11.5), Vector3(24.5, 0, -4.5), Vector3(13, 0, -4.5)]})
	_spec("h2", Vector3(25, 0, -18), {"patrol": [Vector3(25, 0, -18), Vector3(12.5, 0, -18.5), Vector3(12.5, 0, -23.5), Vector3(24, 0, -23.5)]})
	_spec("h3", Vector3(28.6, 0, -9.2), {"leash": 6.0, "face": Vector3(-1, 0, 0)})
	_spec("h4", Vector3(15.5, 0, -24), {"patrol": [Vector3(15.5, 0, -24), Vector3(22, 0, -24.5)]})
	_spec("s1", Vector3(15.3, 0, -31), {"patrol": [Vector3(15.3, 0, -31), Vector3(15.3, 0, -36.6), Vector3(10, 0, -36.6), Vector3(10, 0, -27.5), Vector3(20, 0, -27.5)]})
	_spec("s2", Vector3(19.8, 0, -34), {"patrol": [Vector3(19.8, 0, -34), Vector3(10.2, 0, -34)]})
	_spec("k1", Vector3(29, 0, -35), {"patrol": [Vector3(29, 0, -35), Vector3(24, 0, -35), Vector3(24, 0, -28.5), Vector3(30, 0, -28.5)]})
	# --- M4: pump station (gallery sentry + floor patrol)
	_spec("p1", Vector3(-12.0, 4.2, -28.8), {"leash": 3.5, "face": Vector3(0, 0, 1)})
	_spec("p2", Vector3(-20.0, 0, -12.0), {"patrol": [Vector3(-20.0, 0, -12.0), Vector3(-8.4, 0, -12.0), Vector3(-8.4, 0, -23.0), Vector3(-20.0, 0, -23.0)]})
	# --- M4: switchgear hall (defensive squad holding the breakers)
	_spec("g1", Vector3(41.0, 0, -5.2), {"leash": 6.0, "face": Vector3(0, 0, -1)})
	_spec("g2", Vector3(38.5, 0, -12.5), {"leash": 5.0, "face": Vector3(-1, 0, 0)})
	_spec("g3", Vector3(49.0, 4.2, -17.0), {"leash": 4.0, "face": Vector3(-1, 0, -0.2)})
	# --- M4: dormant units in hall charge bays 04 and 06 (woken by Relay Nine)
	_spec("d1", Vector3(30.55, 0, -6.0), {"dormant": true, "face": Vector3(-1, 0, 0), "hunt": true})
	_spec("d2", Vector3(30.55, 0, -12.4), {"dormant": true, "face": Vector3(-1, 0, 0), "hunt": true})
	# --- spawned later
	_spec("u1", Vector3(10.5, 0, -36.8), {"hunt": true})          # upload: server room
	_spec("u2", Vector3(35.0, 0, -27.8), {"hunt": true})          # upload: switchgear -> D11
	_spec("u3", Vector3(30.0, 0, -20.0), {"hunt": true})          # upload: hall -> D6
	_spec("k2", Vector3(17.0, 0, -51.0), {"leash": 5.0, "face": Vector3(0, 0, 1)})    # core defence
	_spec("k3", Vector3(27.0, 0, -51.0), {"leash": 5.0, "face": Vector3(-0.3, 0, 1)})
	_spec("k4", Vector3(22.0, 0, -57.2), {"leash": 3.5, "face": Vector3(0, 0, 1)})
	_spec("x1", Vector3(44.0, 0, -17.0), {"hunt": true})          # extraction: search squad
	_spec("x2", Vector3(7.5, 0, -6.0), {"hunt": true})
	_spec("x3", Vector3(12.5, 0, 8.0), {"leash": 6.0, "face": Vector3(-1, 0, 0)})      # dock guard
	_spec("l1", Vector3(7.5, 0, -9.0), {"hunt": true})            # lift: corridor assault
	_spec("l2", Vector3(7.5, 0, -16.0), {"hunt": true})


const START_SET := ["o1", "o2", "c1", "h1", "h2", "h3", "h4", "s1", "s2", "k1", "p1", "p2", "g1", "g2", "g3", "d1", "d2"]


func spawn(id: String, pos_override = null, dormant_override = null) -> Teslabot:
	var s: Dictionary = specs[id]
	var b := Teslabot.new()
	var pts: Array[Vector3] = []
	for p in s.patrol:
		pts.append(director.snap(p))
	b.patrol_points = pts
	b.spawn_id = id
	b.dormant = s.dormant if dormant_override == null else dormant_override
	var pos: Vector3 = s.pos if pos_override == null else pos_override
	if s.leash > 0.0:
		b.post = director.snap(s.pos)
		b.leash = s.leash
		b.post_face = s.face.normalized()
	director.register(b)
	main.add_child(b)
	b.global_position = director.snap(pos) + Vector3(0, 0.05, 0)
	var face: Vector3 = s.face if s.face != Vector3.ZERO else ((pts[0] - b.global_position) if not pts.is_empty() else Vector3.FORWARD)
	face.y = 0.0
	if face.length() > 0.01:
		b.look_at(b.global_position + face.normalized() + Vector3(0.001, 0, 0.001), Vector3.UP)
		b._face_dir = face.normalized()
	bots[id] = b
	return b


func spawn_start() -> void:
	if restoring:
		_spawn_from_checkpoint()
		return
	for id in START_SET:
		spawn(id)


func _hunt(b: Teslabot, around: Vector3) -> void:
	if b and is_instance_valid(b) and b.state != Teslabot.S.DEAD:
		var off := Vector3(randf_range(-5, 5), 0, randf_range(-5, 5))
		b.alert_to(director.snap(around + off))


## Send up to `n` idle roaming units (not posted, not dormant) toward `pos`.
func _dispatch(pos: Vector3, n: int) -> int:
	var pool := []
	for b in director.bots:
		if b.state in [Teslabot.S.PATROL, Teslabot.S.SUSPICIOUS] and b.leash <= 0.0 and not b.is_dormant():
			pool.append(b)
	pool.sort_custom(func(a, c): return a.global_position.distance_to(pos) < c.global_position.distance_to(pos))
	var k := 0
	for b in pool.slice(0, n):
		_hunt(b, pos)
		k += 1
	return k


func _alive(id: String) -> bool:
	return bots.has(id) and is_instance_valid(bots[id]) and bots[id].state != Teslabot.S.DEAD


# ------------------------------------------------------------------ flow
func begin() -> void:
	_set_stage("infiltrate")
	_update_infiltrate_objective(true)
	Game.say("Insertion complete. Comms dark. The armory case behind you configures your carbine.", 5.0)
	get_tree().create_timer(5.5).timeout.connect(func():
		if stage == "infiltrate":
			Game.say("Relay control is sealed and unpowered. Lockdown panel: security office. Main breakers: switchgear hall.", 5.5))


func _set_stage(s: String) -> void:
	stage = s
	stage_changed.emit(s)


func _update_infiltrate_objective(loud := false) -> void:
	var parts := []
	parts.append("LOCKDOWN RELEASED" if flags.lockdown else "RELEASE LOCKDOWN: SECURITY OFFICE")
	parts.append("MAIN POWER %d/2: SWITCHGEAR HALL" % flags.power if flags.power < 2 else "MAIN POWER RESTORED")
	var targets := []
	if not flags.lockdown:
		targets.append(ex.lockdown_panel.global_position)
	for br in ex.breakers:
		if not br.thrown:
			targets.append(br.global_position)
	var mark := level.console.global_position
	if not targets.is_empty() and Game.player:
		var pp: Vector3 = Game.player.global_position
		targets.sort_custom(func(a, c): return a.distance_to(pp) < c.distance_to(pp))
		mark = targets[0]
	Game.set_objective("   |   ".join(parts), mark, not loud)


func _on_lockdown() -> void:
	flags.lockdown = true
	ex.set_lockdown_released()
	for id in ["D5", "D6", "D11"]:
		level.doors[id].set_locked(false)
		level.nav_unblock_door(id)
	level.rebake()
	Sfx.play("relay_voice_beep_1" if ResourceLoader.exists("res://assets/audio/relay_voice_beep_1.wav") else "ui_objective", -6.0, 0.0)
	Game.say("Control-wing lockdown released: D5, D6 and D11 unsealed. Relay Nine has noticed.", 4.0)
	var n := _dispatch(ex.lockdown_panel.global_position, 2)
	if n > 0:
		Game.emit_noise(ex.lockdown_panel.global_position, 10.0, Game.player)
	_check_infiltrate()


func _on_breaker(i: int) -> void:
	var br: M4Objects.BreakerLever = ex.breakers[i]
	br.throw_now()
	flags.power += 1
	Sfx.play_3d("breaker_close" if ResourceLoader.exists("res://assets/audio/breaker_close.wav") else "door_breach", br.global_position + Vector3.UP * 1.3, 2.0, 0.0, 10.0)
	Game.emit_noise(br.global_position, 24.0, Game.player)
	if flags.power == 1:
		Game.say("Breaker closed. Relay Nine registered the load change - units are coming to check.", 4.0)
		_dispatch(Vector3(40.0, 0, -16.0), 2)
	else:
		Sfx.play("breaker_hum_rise" if ResourceLoader.exists("res://assets/audio/breaker_hum_rise.wav") else "ui_hack_done", -6.0, 0.0)
		Game.say("Main power restored. The relay control console is live.", 4.0)
	_check_infiltrate()


func _check_infiltrate() -> void:
	if flags.lockdown and flags.power >= 2:
		level.console.powered = true
		_set_stage("upload")
		Game.set_objective("CONNECT THE OVERRIDE AT RELAY CONTROL", level.console.global_position)
		var p: Player = Game.player
		_queue(1.0, func():
			if stage == "upload":
				save_checkpoint("objectives", _safe_xform(p.global_transform)), "cp_objectives")
	else:
		_update_infiltrate_objective(true)


func _on_console_connected() -> void:
	Game.set_state(Game.State.HACK)
	Game.set_objective("DEFEND THE CONSOLE - OVERRIDE UPLOADING", level.console.global_position)
	Game.say("Relay Nine has detected the uplink. Units converging on relay control.", 4.0)
	Game.emit_noise(level.console.global_position, 60.0, Game.player)
	for b in director.bots:
		if b.state != Teslabot.S.DEAD and not b.is_dormant():
			b.alert_to(level.console.global_position)
	for w in [[1.0, "u1"], [12.0, "u2"], [22.0, "u3"]]:
		_queue(w[0], func():
			if Game.state == Game.State.HACK:
				var b := spawn(w[1])
				b.alert_to(level.console.global_position))


# ------------------------------------------------------------------ complication
func _on_console_completed() -> void:
	flags.upload = true
	_set_stage("core")
	Game.set_state(Game.State.CORE)
	if level.console.screen_light:
		level.console.screen_light.light_color = Color(1.0, 0.15, 0.08)
	Sfx.play("relay_voice_beep_2" if ResourceLoader.exists("res://assets/audio/relay_voice_beep_2.wav") else "robot_alert", -2.0, 0.0)
	Game.say("UPLOAD 100%  //  RELAY NINE: OVERRIDE REJECTED. COUNTERMEASURES ACTIVE.", 4.5)
	Game.set_objective("RELAY NINE REJECTED THE OVERRIDE", level.console.global_position)
	_emergency_lighting(true)
	_alarm(true)
	for id in ["k2", "k3", "k4"]:
		spawn(id)
	_queue(0.9, func():
		_seal_d3(false)
		level.nav_unblock("blast")
		level.rebake())
	_queue(2.0, func():
		var pp: Vector3 = Game.player.global_position
		if _alive("d1"): bots.d1.wake(pp, 0.0)
		if _alive("d2"): bots.d2.wake(pp, 0.9)
		Game.say("Charge bays 04 and 06: units coming online.", 3.0))
	_queue(3.6, func():
		ex.blast_door.open_now()
		Game.emit_noise(ex.blast_door.global_position, 18.0, null))
	_queue(5.5, func():
		Game.say("The core blast door is open. Relay Nine is exposed - destroy its three capacitor stacks.", 5.0)
		_update_core_objective(true))
	_queue(7.0, func():
		if stage == "core":
			save_checkpoint("relay core", Transform3D(Basis.looking_at(Vector3(-4.0, 0, -3.0).normalized()), Vector3(25.0, 0.05, -29.0))), "cp_core")
	flags.complication = true


func _seal_d3(instant: bool) -> void:
	var d: Door = level.doors.D3
	d.target = 0.0
	d.speed = 9.0
	if instant:
		d.open_angle = 0.0
	d.set_locked(true, "SEALED - RELAY COUNTERMEASURE")
	level.nav_block_door("D3")
	if not instant:
		Sfx.play_3d("door_breach", d.global_position + Vector3.UP, 4.0, 0.0, 10.0)


func _emergency_lighting(on: bool) -> void:
	Game.emergency = on
	for e in ex.emergency_lights:
		var l: OmniLight3D = e[0]
		l.visible = on
		l.light_energy = 2.4 if on else 0.0
		(e[1] as MeshInstance3D).material_override = MatLib.flat(Color(1.0, 0.2, 0.1), 0.0, 0.4, Color(1.0, 0.1, 0.04), 6.0) if on else MatLib.flat(Color(0.35, 0.05, 0.03), 0.0, 0.4)
	# Normal lighting browns out to a third.
	for r in Game.rooms:
		for n in Game.rooms[r].lights:
			if n is Light3D and is_instance_valid(n):
				if not n.has_meta("e0"):
					n.set_meta("e0", n.light_energy)
				n.light_energy = n.get_meta("e0") * (0.3 if on else 1.0)
	_refresh_probes()


## Interior reflection probes were captured under the normal lighting; capture
## them again after a lighting change so metal stops reflecting dead lamps.
func _refresh_probes() -> void:
	# A changed property marks an update-once probe dirty; stagger them so the
	# re-captures spread over ~1.5 s instead of stalling a frame.
	for rp in level.find_children("*", "ReflectionProbe", true, false):
		await get_tree().create_timer(0.12).timeout
		if is_instance_valid(rp):
			rp.position.y += 0.002 if int(rp.position.y * 1000.0) % 2 == 0 else -0.002   # moving it re-captures


func _alarm(on: bool) -> void:
	for a in _alarms:
		a.queue_free()
	_alarms.clear()
	if not on or not ResourceLoader.exists("res://assets/audio/alarm_loop.wav"):
		return
	for p in ex.alarm_points:
		var h := Node3D.new()
		level.add_child(h)
		h.global_position = p
		var pl := Sfx.loop_3d("alarm_loop", h, -9.0, 9.0)
		if pl:
			pl.max_distance = 34.0
		_alarms.append(h)


func _update_core_objective(loud := false) -> void:
	var n := 0
	var mark := ex.core_center
	var best := 1e9
	for i in ex.capacitors.size():
		if flags.caps[i]:
			n += 1
		elif Game.player:
			var d: float = ex.capacitors[i].global_position.distance_to(Game.player.global_position)
			if d < best:
				best = d
				mark = ex.capacitors[i].global_position
	Game.set_objective("DESTROY RELAY NINE: CAPACITOR STACKS %d/3" % n, mark + Vector3.UP * 0.6, not loud)


func _on_capacitor(i: int) -> void:
	flags.caps[i] = true
	var n: int = flags.caps.count(true)
	if n < 3:
		Game.say("CAPACITOR STACK DOWN - %d/3" % n, 2.5)
		_update_core_objective(true)
	else:
		_core_overload()


func _core_overload() -> void:
	flags.core = true
	_set_stage("extract")
	var c := ex.core_center + Vector3.UP * 4.0
	Game.set_objective("RELAY NINE OVERLOADING - GET CLEAR", c)
	Game.say("All stacks down. The relay is overloading - get clear!", 3.0)
	Sfx.play_3d("core_overload" if ResourceLoader.exists("res://assets/audio/core_overload.wav") else "capacitor_destroyed", c, 8.0, 0.0, 30.0)
	for t in [0.0, 1.3, 2.9]:
		_queue(t, func():
			Fx.overload(c + Vector3(randf_range(-1, 1), randf_range(-2, 2), randf_range(-1, 1)))
			if ex.core_glow:
				ex.core_glow.light_energy = randf_range(2.0, 14.0)
			Fx.mini_arcs(c, 6, 3.0))
	_queue(4.3, func():
		Fx.overload(c)
		Fx.shockwave(ex.core_center + Vector3.UP * 1.0, 14.0, 0.9)
		Fx.smoke_column(ex.core_center)
		Game.emit_noise(c, 60.0, null)
		if ex.core_glow:
			ex.core_glow.visible = false
		_core_dark()
		for b in director.bots:
			if b.state != Teslabot.S.DEAD and b.global_position.distance_to(ex.core_center) < 9.0:
				b.explosion_damage(90.0, ex.core_center))
	_queue(5.0, _blackout)


func _core_dark() -> void:
	if ex.core_array == null:
		return
	var dead := MatLib.flat(Color(0.08, 0.09, 0.1), 0.6, 0.5)
	for mi in ex.core_array.find_children("*", "MeshInstance3D", true, false):
		var m: Mesh = mi.mesh
		for s in m.get_surface_count():
			var mat = mi.get_active_material(s)
			if mat is BaseMaterial3D and mat.emission_enabled:
				mi.set_surface_override_material(s, dead)
	if ex.core_array is MeshInstance3D:
		ex.core_array.material_override = dead


func _blackout(silent := false) -> void:
	for r in Game.rooms:
		if r != "dock":
			Game.set_room_lit(r, false)
	# Without the grid, only emergency beacons and the lift's own supply
	# remain: drop the ambient fill so the extraction is genuinely dark.
	if main.env:
		main.env.ambient_light_energy = 0.14
		main.env.fog_light_color = Color(0.05, 0.05, 0.055)
	_refresh_probes()
	if silent:
		return
	Game.set_state(Game.State.EXTRACT)
	_set_stage("extract")
	ex.lift_panel.active = true
	Game.say("RELAY NINE IS DOWN. The grid is collapsing - units are on battery and hunting. Get to Freight Lift 2.", 5.5)
	Game.set_objective("EXTRACT: CALL FREIGHT LIFT 2 (DOCK)", ex.lift_panel.global_position + Vector3.UP)
	var pp: Vector3 = Game.player.global_position
	for id in ["x1", "x2", "x3"]:
		var b := spawn(id)
		if specs[id].hunt:
			_hunt(b, pp)
	_dispatch(pp, 3)
	_queue(9.0, func():
		if stage == "extract":
			save_checkpoint("extraction", Transform3D(Basis(), Vector3(17.0, 0.05, -40.6))), "cp_extract")


# ------------------------------------------------------------------ lift
func _on_lift_called() -> void:
	flags.lift = true
	_set_stage("lift")
	_lift_t = LIFT_TIME
	ex.lift_panel.active = false
	Sfx.play_3d("lift_call" if ResourceLoader.exists("res://assets/audio/lift_call.wav") else "ui_hack_done", ex.lift_panel.global_position + Vector3.UP, 0.0, 0.0, 6.0)
	if ResourceLoader.exists("res://assets/audio/lift_motor_loop.wav"):
		var h := Node3D.new()
		level.add_child(h)
		h.global_position = Vector3(3.0, 4.5, 12.0)
		_motor = Sfx.loop_3d("lift_motor_loop", h, -4.0, 10.0)
	Game.say("Freight Lift 2 is on its way down. The whole facility heard that - hold the dock.", 4.0)
	Game.emit_noise(level.extraction_pos, 40.0, Game.player)
	for w in [[0.5, "l1"], [6.5, "l2"]]:
		_queue(w[0], func():
			var b := spawn(w[1])
			_hunt(b, level.extraction_pos + Vector3(4, 0, -3)))


func _process(delta: float) -> void:
	# Scripted events
	var i := 0
	while i < _events.size():
		var e: Array = _events[i]
		e[0] -= delta
		if e[0] <= 0.0:
			_events.remove_at(i)
			if Game.autotest:
				print("[mission] event %s fired at %.2f" % [e[2], Time.get_ticks_msec() / 1000.0])
			e[1].call()
		else:
			i += 1
	_arc_t -= delta
	if _arc_t <= 0.0:
		_arc_t = randf_range(3.5, 8.0)
		_ambient_arc()
	if Game.emergency:
		# Beacons pulse (rotating-beacon rhythm, offset per light).
		var tt := Time.get_ticks_msec() / 1000.0
		for k in ex.emergency_lights.size():
			var l: OmniLight3D = ex.emergency_lights[k][0]
			l.light_energy = 2.4 + 1.8 * sin(tt * 3.4 + k * 0.9)
	if not Game.is_active() or Game.player == null:
		return
	_obj_t -= delta
	if _obj_t <= 0.0:
		_obj_t = 1.0
		if stage == "infiltrate":
			_update_infiltrate_objective()
		elif stage == "core" and flags.complication and Game.objective_text.begins_with("DESTROY"):
			_update_core_objective()
	if stage == "lift" and _lift_t > 0.0:
		var prev := ceili(_lift_t)
		_lift_t -= delta
		if ceili(_lift_t) != prev:
			Game.set_objective("HOLD THE DOCK - LIFT ARRIVING 0:%02d" % maxi(0, ceili(_lift_t)), level.extraction_pos, true)
		if _lift_t <= 0.0:
			_lift_arrived()
	if stage == "board":
		level.beacon.light_energy = 3.0 * (0.5 + 0.5 * sin(Time.get_ticks_msec() / 160.0))
		var p: Player = Game.player
		if p.alive and level.extraction_area.overlaps_body(p):
			_board_t += delta
			Game.say("BOARDING... %.1f" % maxf(0.0, BOARD_TIME - _board_t), 0.3)
			if _board_t >= BOARD_TIME:
				_set_stage("done")
				Game.set_state(Game.State.COMPLETE)
				Sfx.play("ui_hack_done", 0.0)
				Game.checkpoint = {}
				main._end_t = 1.5
		else:
			_board_t = 0.0


func _lift_arrived() -> void:
	_set_stage("board")
	if _motor:
		_motor.get_parent().queue_free()
		_motor = null
	Sfx.play_3d("lift_arrive" if ResourceLoader.exists("res://assets/audio/lift_arrive.wav") else "door_open", Vector3(3.0, 1.5, 12.0), 4.0, 0.0, 12.0)
	Game.set_objective("BOARD FREIGHT LIFT 2", level.extraction_pos)
	Game.say("Lift is down - get on!", 3.0)


## Live equipment arcs now and then: the energised transformers (once main
## power is back) and the relay array (until it is destroyed). Only when the
## player is near enough to see or hear it.
func _ambient_arc() -> void:
	var p: Player = Game.player
	if p == null:
		return
	var spots := []
	if flags.power >= 2:
		for x in [39.6, 44.2]:
			spots.append([Vector3(x - 0.6 + randf() * 1.2, 4.3, -27.6), Vector3(x + randf_range(-1.5, 1.5), 6.0, -28.4)])
	if not flags.core:
		var c := ex.core_center
		var a := randf() * TAU
		spots.append([c + Vector3(0, 6.6, 0), c + Vector3(cos(a) * 3.2, 9.6, sin(a) * 3.2)])
	for sp in spots:
		if sp[0].distance_to(p.global_position) < 26.0:
			Fx.arc(sp[0], sp[1], 0.03, 0.12, 2, true)
			Sfx.play_3d("arc_crackle" if ResourceLoader.exists("res://assets/audio/arc_crackle_0.wav") else "tesla_shot", sp[0], -4.0, 0.1, 6.0)
			return


func _queue(t: float, cb: Callable, label := "") -> void:
	_events.append([t, cb, label if label != "" else "%.1fs" % t])
	if Game.autotest:
		print("[mission] queued %s at %.2f (+%.1f s)" % [label, Time.get_ticks_msec() / 1000.0, t])


# ------------------------------------------------------------------ checkpoints
func _safe_xform(t: Transform3D) -> Transform3D:
	var p := director.snap(t.origin) + Vector3(0, 0.05, 0)
	var f := -t.basis.z
	f.y = 0.0
	return Transform3D(Basis.looking_at(f.normalized() if f.length() > 0.01 else Vector3.FORWARD, Vector3.UP), p)


func save_checkpoint(cp_name: String, respawn: Transform3D) -> void:
	var p: Player = Game.player
	if p == null or not p.alive or not Game.is_active():
		return
	var bl := []
	for id in bots:
		var b: Teslabot = bots[id]
		if is_instance_valid(b) and b.state != Teslabot.S.DEAD:
			bl.append({"id": id, "pos": b.global_position, "dormant": b.dormant})
	Game.checkpoint = {"name": cp_name, "stage": stage, "flags": flags.duplicate(true), "respawn": respawn,
		"loadout": p.loadout.duplicate(), "bots": bl, "stats": Game.stats.duplicate(), "elapsed": Game.elapsed(),
		"state": Game.state, "pending": false}
	Game.say("CHECKPOINT - " + cp_name.to_upper(), 2.0)


## World state that must exist before the navmesh bake (doors, blast door, lights).
func _apply_world(f: Dictionary) -> void:
	flags = f.duplicate(true)
	if flags.lockdown:
		ex.set_lockdown_released()
		ex.lockdown_panel._done = true
		for id in ["D5", "D6", "D11"]:
			level.doors[id].set_locked(false)
			level.nav_unblock_door(id)
	for i in flags.power:
		ex.breakers[i].throw_now(true)
	if flags.lockdown and flags.power >= 2:
		level.console.powered = true
	if flags.upload:
		level.console.done = true
		level.console.progress = 1.0
		if level.console.screen_light:
			level.console.screen_light.light_color = Color(1.0, 0.15, 0.08)
	if flags.complication:
		_seal_d3(true)
		level.nav_unblock("blast")
		ex.blast_door.open_now(true)
		_emergency_lighting(true)
	for i in ex.capacitors.size():
		if flags.caps[i]:
			ex.capacitors[i].destroy(true)
	if flags.core:
		if ex.core_glow:
			ex.core_glow.visible = false
		_core_dark()
		_blackout(true)


func _spawn_from_checkpoint() -> void:
	var cp: Dictionary = Game.checkpoint
	var respawn: Transform3D = cp.respawn
	for e in cp.bots:
		var id: String = e.id
		var pos: Vector3 = e.pos
		if pos.distance_to(respawn.origin) < 12.0:
			pos = specs[id].pos   # no unit waiting on top of the respawn point
		var b := spawn(id, pos, e.dormant)
		b._sense_t = 3.0       # a moment of grace after the respawn
		if specs[id].hunt and not e.dormant:
			_hunt(b, respawn.origin)


## Called by main after the player exists (checkpoint restore).
func resume() -> void:
	var cp: Dictionary = Game.checkpoint
	Game.begin_mission()
	Game.stats = cp.stats.duplicate()
	Game.start_time -= cp.elapsed
	if flags.complication:
		_emergency_lighting(true)   # re-applies to lights registered after setup
		_alarm(true)
	Game.set_state(cp.state)
	var p: Player = Game.player
	p.global_transform = cp.respawn
	p.set_loadout(cp.loadout)
	stage = cp.stage
	match stage:
		"upload":
			Game.set_objective("CONNECT THE OVERRIDE AT RELAY CONTROL", level.console.global_position, true)
		"core":
			_update_core_objective(true)
		"extract":
			ex.lift_panel.active = true
			Game.set_objective("EXTRACT: CALL FREIGHT LIFT 2 (DOCK)", ex.lift_panel.global_position + Vector3.UP, true)
		_:
			_update_infiltrate_objective(true)
	Game.checkpoint.pending = false
	Game.say("RESTARTED FROM CHECKPOINT - " + String(cp.name).to_upper(), 3.0)
	stage_changed.emit(stage)
