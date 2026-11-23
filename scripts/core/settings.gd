extends Node
## Player preferences, input map and graphics scalability.
## Presets map to concrete renderer features; apply_to() is called whenever the
## world environment or settings change.

signal changed

const PATH := "user://settings.cfg"
const PRESETS := ["Low", "Medium", "High", "Ultra"]

var quality := 2
var fov := 90.0
var sensitivity := 0.0022
var ads_sens_mult := 0.8
var master_volume := 0.85
var vsync := false
var fps_limit := 0
var show_fps := true
var render_scale := 1.0

var _env: Environment
var _viewport: Viewport


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_input()
	load_settings()


func _setup_input() -> void:
	var keys := {
		"move_forward": [KEY_W], "move_back": [KEY_S], "move_left": [KEY_A], "move_right": [KEY_D],
		"sprint": [KEY_SHIFT], "crouch": [KEY_CTRL, KEY_C], "jump": [KEY_SPACE],
		"lean_left": [KEY_Q], "lean_right": [KEY_E], "interact": [KEY_F], "reload": [KEY_R],
		"weapon_1": [KEY_1], "weapon_2": [KEY_2], "fire_mode": [KEY_B], "kick": [KEY_V],
		"deploy": [KEY_G], "loadout": [KEY_T], "pause": [KEY_ESCAPE, KEY_P],
		"toggle_fps": [KEY_F3], "night_vision": [KEY_N],
	}
	for action in keys:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for k in keys[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = k
			InputMap.action_add_event(action, ev)
	for pair in [["fire", MOUSE_BUTTON_LEFT], ["aim", MOUSE_BUTTON_RIGHT]]:
		if not InputMap.has_action(pair[0]):
			InputMap.add_action(pair[0])
		var mb := InputEventMouseButton.new()
		mb.button_index = pair[1]
		InputMap.action_add_event(pair[0], mb)
	for pair in [["weapon_next", MOUSE_BUTTON_WHEEL_DOWN], ["weapon_prev", MOUSE_BUTTON_WHEEL_UP]]:
		if not InputMap.has_action(pair[0]):
			InputMap.add_action(pair[0])
		var mw := InputEventMouseButton.new()
		mw.button_index = pair[1]
		InputMap.action_add_event(pair[0], mw)


func load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) == OK:
		quality = cfg.get_value("gfx", "quality", quality)
		fov = cfg.get_value("view", "fov", fov)
		sensitivity = cfg.get_value("input", "sensitivity", sensitivity)
		master_volume = cfg.get_value("audio", "master", master_volume)
		vsync = cfg.get_value("gfx", "vsync", vsync)
		render_scale = cfg.get_value("gfx", "render_scale", render_scale)
		show_fps = cfg.get_value("view", "show_fps", show_fps)
	# Command-line override for benchmarks: -- --quality=0..3
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--quality="):
			quality = clampi(int(a.get_slice("=", 1)), 0, 3)
	apply_audio()


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("gfx", "quality", quality)
	cfg.set_value("gfx", "vsync", vsync)
	cfg.set_value("gfx", "render_scale", render_scale)
	cfg.set_value("view", "fov", fov)
	cfg.set_value("view", "show_fps", show_fps)
	cfg.set_value("input", "sensitivity", sensitivity)
	cfg.set_value("audio", "master", master_volume)
	cfg.save(PATH)


func apply_audio() -> void:
	AudioServer.set_bus_volume_db(0, linear_to_db(maxf(master_volume, 0.0001)))


func register(env: Environment, vp: Viewport) -> void:
	_env = env
	_viewport = vp
	apply()


func set_quality(q: int, persist := true) -> void:
	quality = clampi(q, 0, 3)
	apply()
	if persist:
		save_settings()


func apply() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if vsync else DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = fps_limit
	apply_audio()
	if _env == null or _viewport == null:
		changed.emit()
		return
	var q := quality
	var e := _env
	# Ambient occlusion and indirect light
	e.ssao_enabled = q >= 1
	e.ssao_radius = 1.2
	e.ssao_intensity = 2.2
	e.ssil_enabled = q >= 3
	e.ssr_enabled = q >= 2
	e.ssr_max_steps = 48 if q >= 3 else 32
	e.sdfgi_enabled = q >= 2
	e.glow_enabled = true
	e.volumetric_fog_enabled = q >= 1
	e.fog_enabled = q == 0
	RenderingServer.environment_set_volumetric_fog_volume_size(64 if q >= 3 else 48, 64)
	RenderingServer.environment_set_volumetric_fog_filter_active(q >= 2)
	RenderingServer.environment_set_ssao_quality(
		[RenderingServer.ENV_SSAO_QUALITY_VERY_LOW, RenderingServer.ENV_SSAO_QUALITY_LOW, RenderingServer.ENV_SSAO_QUALITY_MEDIUM, RenderingServer.ENV_SSAO_QUALITY_HIGH][q],
		q < 3, 0.5, 2, 50, 300)
	RenderingServer.environment_set_sdfgi_ray_count(RenderingServer.ENV_SDFGI_RAY_COUNT_32 if q >= 3 else RenderingServer.ENV_SDFGI_RAY_COUNT_16)
	# Shadows
	var shadow_size: int = [2048, 4096, 4096, 8192][q]
	RenderingServer.positional_soft_shadow_filter_set_quality(
		[RenderingServer.SHADOW_QUALITY_HARD, RenderingServer.SHADOW_QUALITY_SOFT_VERY_LOW, RenderingServer.SHADOW_QUALITY_SOFT_LOW, RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM][q])
	_viewport.positional_shadow_atlas_size = shadow_size
	# Anti-aliasing and resolution
	_viewport.msaa_3d = Viewport.MSAA_DISABLED
	_viewport.use_taa = q >= 2
	_viewport.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA if q < 2 else Viewport.SCREEN_SPACE_AA_DISABLED
	var scale := render_scale
	if q == 0:
		scale = minf(scale, 0.77)
	_viewport.scaling_3d_scale = scale
	_viewport.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2 if scale < 0.99 else Viewport.SCALING_3D_MODE_BILINEAR
	_viewport.mesh_lod_threshold = [4.0, 2.0, 1.0, 1.0][q]
	changed.emit()
