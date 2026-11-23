extends Node3D
## Bootstraps the mission: environment, level, navigation, player, Teslabots,
## HUD/menus and the objective flow (infiltrate -> hack/defend -> extract).

var level: LevelBuilder
var player: Player
var director: Director
var hud: CanvasLayer
var menus: CanvasLayer
var env: Environment
var _extract_t := 0.0
var _flicker := []
var _end_t := -1.0


func _ready() -> void:
	_setup_env()
	level = LevelBuilder.new()
	level.name = "Level"
	add_child(level)
	level.build()
	Fx.setup(self)
	level.bake_nav()
	director = Director.new()
	director.name = "Director"
	add_child(director)
	director.setup(get_world_3d())
	player = Player.new()
	player.name = "Player"
	add_child(player)
	player.global_transform = level.player_start
	hud = preload("res://scripts/ui/hud.gd").new()
	add_child(hud)
	hud.bind(player)
	menus = preload("res://scripts/ui/menus.gd").new()
	add_child(menus)
	menus.player = player
	menus.deploy.connect(_on_deploy)
	player.died.connect(func(): _end_t = 2.5)
	level.console.connected.connect(_on_console_connected)
	level.console.completed.connect(_on_console_completed)
	for l in level.find_children("*", "Light3D", true, false):
		if l.has_meta("flicker"):
			_flicker.append([l, l.light_energy, 0.0])
	Sfx.loop_2d("ambience_facility", -11.0)
	# Navigation map needs a sync before path queries are valid.
	var map := get_world_3d().navigation_map
	for i in 120:
		await get_tree().physics_frame
		if NavigationServer3D.map_get_path(map, Vector3(8, 0, 11), Vector3(27, 0, -35), true).size() > 0:
			break
	director.cover_points = level.build_cover_points()
	director.setup_doors(level.doors)
	for s in level.spawns:
		_spawn_bot(s.pos, s.patrol)
	Game.state = Game.State.BRIEFING
	if Game.autotest:
		var ap := preload("res://scripts/test/autopilot.gd").new()
		ap.name = "Autopilot"
		add_child(ap)
		ap.run(self)
	else:
		menus.open("briefing")


func _setup_env() -> void:
	var we := WorldEnvironment.new()
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.0, 0.0, 0.0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.2, 0.24, 0.3)
	env.ambient_light_energy = 0.5
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.45
	env.tonemap_white = 6.0
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_strength = 0.9
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.2
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.set_glow_level(0, 0.0)
	env.set_glow_level(1, 0.6)
	env.set_glow_level(2, 0.8)
	env.set_glow_level(3, 0.5)
	env.set_glow_level(4, 0.3)
	env.volumetric_fog_density = 0.022
	env.volumetric_fog_albedo = Color(0.76, 0.78, 0.82)
	env.volumetric_fog_anisotropy = 0.55
	env.volumetric_fog_length = 48.0
	env.volumetric_fog_detail_spread = 1.6
	env.volumetric_fog_gi_inject = 0.5
	env.volumetric_fog_ambient_inject = 0.15
	env.volumetric_fog_temporal_reprojection_enabled = true
	env.fog_light_color = Color(0.12, 0.12, 0.13)
	env.fog_density = 0.012
	env.sdfgi_use_occlusion = true
	env.sdfgi_cascades = 4
	env.sdfgi_min_cell_size = 0.15
	env.sdfgi_energy = 0.9
	env.sdfgi_bounce_feedback = 0.4
	env.ssr_fade_in = 0.1
	env.ssr_depth_tolerance = 0.3
	env.ssil_intensity = 0.8
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.06
	env.adjustment_saturation = 0.95
	we.environment = env
	add_child(we)
	var cam_attr := CameraAttributesPractical.new()
	cam_attr.auto_exposure_enabled = false
	we.camera_attributes = cam_attr
	Settings.register(env, get_viewport())


func _spawn_bot(pos: Vector3, patrol: Array) -> Teslabot:
	var b := Teslabot.new()
	var pts: Array[Vector3] = []
	for p in patrol:
		pts.append(director.snap(p))
	b.patrol_points = pts
	director.register(b)
	add_child(b)
	b.global_position = director.snap(pos) + Vector3(0, 0.05, 0)
	if not pts.is_empty():
		b.look_at(b.global_position + (pts[0] - b.global_position + Vector3(0.01, 0, 0.01)).normalized(), Vector3.UP)
	return b


func _on_deploy() -> void:
	Game.begin_mission()
	Game.set_objective("REACH RELAY CONTROL AND CONNECT THE OVERRIDE", level.console.global_position)
	Game.say("Insertion complete. Comms dark. The armory case behind you configures your carbine.", 5.0)


func _on_console_connected() -> void:
	Game.set_state(Game.State.HACK)
	Game.set_objective("DEFEND THE CONSOLE - OVERRIDE UPLOADING", level.console.global_position)
	Game.say("Relay Nine has detected the uplink. Units converging on your position.", 4.0)
	Game.emit_noise(level.console.global_position, 60.0, player)
	for b in director.bots:
		if b.state != Teslabot.S.DEAD:
			b.alert_to(level.console.global_position)
	var waves := [[0.5, Vector3(30.5, 0, -4.0)], [7.0, Vector3(10.5, 0, -36.8)], [15.0, Vector3(20.0, 0, -3.5)], [24.0, Vector3(30.0, 0, -20.0)]]
	for w in waves:
		get_tree().create_timer(w[0]).timeout.connect(_reinforce.bind(w[1]))


func _reinforce(pos: Vector3) -> void:
	if Game.state == Game.State.HACK:
		var b := _spawn_bot(pos, [])
		b.alert_to(level.console.global_position)


func _on_console_completed() -> void:
	Game.set_state(Game.State.EXTRACT)
	level.doors.D6.set_locked(false)
	Game.set_objective("EXTRACT - FREIGHT LIFT 2", level.extraction_pos)
	Game.say("Override complete. Control wing unsealed. Get to the lift.", 4.0)
	Sfx.play("extraction_alarm", -6.0)
	# Ambush: two units reposition into the dock.
	for p in [[Vector3(13.5, 0, 11.5), [Vector3(13.5, 0, 11.5), Vector3(5.5, 0, 7.5)]], [Vector3(2.5, 0, 3.0), [Vector3(2.5, 0, 3.0), Vector3(9.5, 0, 2.0)]]]:
		_spawn_bot(p[0], p[1])


func _process(delta: float) -> void:
	# Light flicker
	for f in _flicker:
		var l: Light3D = f[0]
		f[2] -= delta
		if f[2] <= 0.0:
			f[2] = randf_range(0.03, 0.4) if randf() < 0.7 else randf_range(1.0, 3.0)
			l.light_energy = f[1] * (randf_range(0.0, 0.35) if randf() < 0.45 else 1.0)
	# Extraction
	if Game.state == Game.State.EXTRACT:
		level.beacon.light_energy = 3.0 * (0.5 + 0.5 * sin(Time.get_ticks_msec() / 160.0))
		if player.alive and level.extraction_area.overlaps_body(player):
			_extract_t += delta
			Game.say("EXTRACTING... %.1f" % maxf(0.0, 4.0 - _extract_t), 0.3)
			if _extract_t >= 4.0:
				Game.set_state(Game.State.COMPLETE)
				Sfx.play("ui_hack_done", 0.0)
				_end_t = 1.0
		else:
			_extract_t = 0.0
	if _end_t > 0.0:
		_end_t -= delta
		if _end_t <= 0.0 and not Game.autotest:
			menus.open("complete" if Game.state == Game.State.COMPLETE else "failed")
