extends CanvasLayer
## Minimal tactical HUD: crosshair/hitmarkers, ammo, health, objective marker,
## interaction prompt, upload progress, damage direction and vignette, FPS.

var player: Player
var font: Font
var root: Control
var cross: Control
var ammo_lbl: Label
var reserve_lbl: Label
var weapon_lbl: Label
var mode_lbl: Label
var health_bar: ColorRect
var health_bg: ColorRect
var health_lbl: Label
var gear_lbl: Label
var obj_lbl: Label
var msg_lbl: Label
var prompt_lbl: Label
var prompt_bar: ColorRect
var prompt_bg: ColorRect
var upload_box: Control
var upload_bar: ColorRect
var upload_lbl: Label
var fps_lbl: Label
var vignette: ColorRect
var marker: Control
var nv_rect: ColorRect

var _hit_t := 0.0
var _hit_col := Color.WHITE
var _dmg_dirs: Array = []   # [angle, t]
var _dmg_flash := 0.0
var _msg_t := 0.0
var _fps_acc := 0.0
var _fps_frames := 0
var _fps_min := 999.0
var _hb_cd := 0.0

const ACCENT := Color(0.92, 0.72, 0.32)
const DIM := Color(0.85, 0.86, 0.84, 0.85)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 5
	var sf := SystemFont.new()
	sf.font_names = PackedStringArray(["Bahnschrift", "Segoe UI", "Arial"])
	sf.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
	font = sf
	root = Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_build_vignette()
	_build_nv()
	cross = Control.new()
	cross.set_anchors_preset(Control.PRESET_FULL_RECT)
	cross.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cross.draw.connect(_draw_cross)
	root.add_child(cross)
	marker = Control.new()
	marker.set_anchors_preset(Control.PRESET_FULL_RECT)
	marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	marker.draw.connect(_draw_marker)
	root.add_child(marker)
	# Bottom right: weapon block
	weapon_lbl = _label(18, DIM, Control.PRESET_BOTTOM_RIGHT, Vector2(-330, -128), HORIZONTAL_ALIGNMENT_RIGHT, 300)
	ammo_lbl = _label(54, Color(0.95, 0.95, 0.93), Control.PRESET_BOTTOM_RIGHT, Vector2(-330, -108), HORIZONTAL_ALIGNMENT_RIGHT, 200)
	reserve_lbl = _label(24, DIM, Control.PRESET_BOTTOM_RIGHT, Vector2(-122, -84), HORIZONTAL_ALIGNMENT_LEFT, 100)
	mode_lbl = _label(15, ACCENT, Control.PRESET_BOTTOM_RIGHT, Vector2(-330, -44), HORIZONTAL_ALIGNMENT_RIGHT, 300)
	# Bottom left: health
	health_bg = ColorRect.new()
	health_bg.color = Color(0, 0, 0, 0.45)
	health_bg.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	health_bg.position = Vector2(40, -60)
	health_bg.size = Vector2(260, 6)
	root.add_child(health_bg)
	health_bar = ColorRect.new()
	health_bar.color = Color(0.92, 0.92, 0.9)
	health_bar.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	health_bar.position = Vector2(40, -60)
	health_bar.size = Vector2(260, 6)
	root.add_child(health_bar)
	health_lbl = _label(30, Color(0.95, 0.95, 0.93), Control.PRESET_BOTTOM_LEFT, Vector2(40, -104), HORIZONTAL_ALIGNMENT_LEFT, 200)
	gear_lbl = _label(15, DIM, Control.PRESET_BOTTOM_LEFT, Vector2(40, -46), HORIZONTAL_ALIGNMENT_LEFT, 400)
	# Top: objective
	obj_lbl = _label(18, Color(0.95, 0.94, 0.9), Control.PRESET_CENTER_TOP, Vector2(-450, 26), HORIZONTAL_ALIGNMENT_CENTER, 900)
	msg_lbl = _label(17, ACCENT, Control.PRESET_CENTER_TOP, Vector2(-500, 92), HORIZONTAL_ALIGNMENT_CENTER, 1000)
	msg_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD
	# Interaction prompt
	prompt_lbl = _label(17, Color(0.95, 0.95, 0.92), Control.PRESET_CENTER, Vector2(-300, 70), HORIZONTAL_ALIGNMENT_CENTER, 600)
	prompt_bg = ColorRect.new()
	prompt_bg.color = Color(0, 0, 0, 0.5)
	prompt_bg.set_anchors_preset(Control.PRESET_CENTER)
	prompt_bg.position = Vector2(-90, 102)
	prompt_bg.size = Vector2(180, 4)
	root.add_child(prompt_bg)
	prompt_bar = ColorRect.new()
	prompt_bar.color = ACCENT
	prompt_bar.set_anchors_preset(Control.PRESET_CENTER)
	prompt_bar.position = Vector2(-90, 102)
	prompt_bar.size = Vector2(0, 4)
	root.add_child(prompt_bar)
	# Upload progress
	upload_box = Control.new()
	upload_box.set_anchors_preset(Control.PRESET_CENTER_TOP)
	upload_box.position = Vector2(-200, 62)
	upload_box.size = Vector2(400, 30)
	upload_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(upload_box)
	var ubg := ColorRect.new()
	ubg.color = Color(0, 0, 0, 0.5)
	ubg.size = Vector2(400, 5)
	ubg.position = Vector2(0, 22)
	upload_box.add_child(ubg)
	upload_bar = ColorRect.new()
	upload_bar.color = Color(0.45, 0.78, 1.0)
	upload_bar.size = Vector2(0, 5)
	upload_bar.position = Vector2(0, 22)
	upload_box.add_child(upload_bar)
	upload_lbl = Label.new()
	upload_lbl.add_theme_font_override("font", font)
	upload_lbl.add_theme_font_size_override("font_size", 14)
	upload_lbl.size = Vector2(400, 20)
	upload_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	upload_box.add_child(upload_lbl)
	upload_box.visible = false
	fps_lbl = _label(14, Color(0.7, 0.9, 0.7, 0.9), Control.PRESET_TOP_RIGHT, Vector2(-260, 14), HORIZONTAL_ALIGNMENT_RIGHT, 240)
	Game.objective_changed.connect(func(t, _p): obj_lbl.text = t)
	Game.message.connect(_on_message)
	Game.hack_progress.connect(_on_hack)


func _label(size: int, col: Color, preset: int, pos: Vector2, align: int, width: float) -> Label:
	var l := Label.new()
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.set_anchors_preset(preset)
	l.position = pos
	l.size = Vector2(width, size * 1.4)
	l.horizontal_alignment = align
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(l)
	return l


func _build_vignette() -> void:
	vignette = ColorRect.new()
	vignette.set_anchors_preset(Control.PRESET_FULL_RECT)
	vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sm := ShaderMaterial.new()
	var s := Shader.new()
	s.code = """
shader_type canvas_item;
uniform float damage = 0.0;
uniform float low_hp = 0.0;
uniform float ads = 0.0;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 c = uv - 0.5;
	float r = length(c * vec2(1.6, 1.0));
	vec3 col = texture(screen_tex, uv).rgb;
	// subtle chromatic split when hurt
	float ca = 0.004 * damage;
	col.r = texture(screen_tex, uv + c * ca).r;
	col.b = texture(screen_tex, uv - c * ca).b;
	float lum = dot(col, vec3(0.299, 0.587, 0.114));
	col = mix(col, vec3(lum), low_hp * 0.55);
	float v = smoothstep(0.45, 1.05, r);
	col *= 1.0 - v * (0.35 + 0.25 * ads);
	col = mix(col, vec3(0.55, 0.05, 0.02), v * clamp(damage * 0.8 + low_hp * 0.5, 0.0, 0.85));
	COLOR = vec4(col, 1.0);
}
"""
	sm.shader = s
	vignette.material = sm
	root.add_child(vignette)


func _build_nv() -> void:
	nv_rect = ColorRect.new()
	nv_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	nv_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sm := ShaderMaterial.new()
	var s := Shader.new()
	s.code = """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float time_s = 0.0;
uniform float battery = 1.0;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 c = texture(screen_tex, uv).rgb;
	// slight blur from the intensifier tube
	c = c * 0.6 + texture(screen_tex, uv, 1.5).rgb * 0.4;
	float lum = dot(c, vec3(0.299, 0.587, 0.114));
	// gain curve: lifts darks strongly, compresses highlights (bloom-out)
	float g = 1.0 - exp(-lum * 9.0);
	g = mix(g, g * 0.75, 1.0 - battery);
	float n = hash(uv * vec2(1920.0, 1080.0) + fract(time_s * 37.0) * 91.0) - 0.5;
	g += n * 0.11;
	float scan = 0.97 + 0.03 * sin(uv.y * 900.0 + time_s * 6.0);
	vec2 cc = (uv - 0.5) * vec2(1.6, 1.0);
	float vig = 1.0 - smoothstep(0.55, 1.0, length(cc));
	vec3 col = vec3(0.32, 1.0, 0.42) * g * scan * vig;
	col += vec3(0.0, 0.03, 0.01);
	COLOR = vec4(col, 1.0);
}
"""
	sm.shader = s
	nv_rect.material = sm
	nv_rect.visible = false
	root.add_child(nv_rect)


func bind(p: Player) -> void:
	player = p
	p.damaged.connect(_on_damaged)
	p.hit_confirmed.connect(_on_hit)
	p.interact_prompt.connect(_on_prompt)


func _on_message(t: String, secs: float) -> void:
	msg_lbl.text = t
	_msg_t = secs


func _on_hack(v: float) -> void:
	upload_box.visible = v < 1.0 and Game.state == Game.State.HACK
	upload_bar.size.x = 400.0 * v
	var c: Node = get_tree().current_scene.find_child("RelayConsole", true, false)
	var jam: bool = c != null and c.jammed
	upload_lbl.text = ("UPLINK JAMMED - CLEAR THE CONSOLE" if jam else "RELAY OVERRIDE UPLOAD  %d%%" % int(v * 100))
	upload_lbl.add_theme_color_override("font_color", Color(1, 0.35, 0.25) if jam else Color(0.7, 0.88, 1.0))
	upload_bar.color = Color(1, 0.35, 0.25) if jam else Color(0.45, 0.78, 1.0)


func _on_damaged(amount: float, from_pos: Vector3) -> void:
	_dmg_flash = minf(1.0, _dmg_flash + amount / 30.0)
	var cam := player.camera
	var local := cam.global_transform.basis.inverse() * (from_pos - cam.global_position)
	var ang := atan2(local.x, -local.z)
	_dmg_dirs.append([ang, 1.2])


func _on_hit(res: Dictionary) -> void:
	_hit_t = 0.18 if not res.kill else 0.35
	_hit_col = Color(1, 0.3, 0.2) if res.kill else (Color(0.5, 0.8, 1.0) if res.get("weak", false) else Color.WHITE)
	Sfx.play("hitmarker_kill" if res.kill else "hitmarker", -6.0 if res.kill else -10.0, 0.05)


func _on_prompt(t: String, progress: float) -> void:
	prompt_lbl.text = t
	prompt_bar.size.x = 180.0 * progress
	prompt_bg.visible = progress > 0.0
	prompt_bar.visible = progress > 0.0


func _process(delta: float) -> void:
	# FPS
	_fps_acc += delta
	_fps_frames += 1
	if delta > 0.0:
		_fps_min = minf(_fps_min, 1.0 / delta)
	if _fps_acc >= 0.5:
		fps_lbl.text = "%d FPS  (%.1f ms, min %d)  %s" % [_fps_frames / _fps_acc, _fps_acc / _fps_frames * 1000.0, _fps_min, Settings.PRESETS[Settings.quality].to_upper()]
		_fps_acc = 0.0
		_fps_frames = 0
		_fps_min = 999.0
	fps_lbl.visible = Settings.show_fps
	if Input.is_action_just_pressed("toggle_fps"):
		Settings.show_fps = not Settings.show_fps
	if player == null:
		return
	var w := player.weapon()
	weapon_lbl.text = w.def.name
	ammo_lbl.text = str(w.ammo)
	ammo_lbl.add_theme_color_override("font_color", Color(1, 0.4, 0.3) if w.ammo <= int(w.stats.mag * 0.2) else Color(0.95, 0.95, 0.93))
	reserve_lbl.text = "/ %d" % w.reserve
	var mode := "AUTO" if w.auto_mode else "SEMI"
	if w.is_reloading():
		mode = "RELOADING"
	var att := ""
	if w.id == "rifle":
		var parts := []
		for slot in ["optic", "muzzle", "grip", "mag"]:
			parts.append(WeaponDefs.ATTACHMENTS[w.loadout[slot]].label)
		att = "   " + " | ".join(parts)
	mode_lbl.text = mode + att if w.id == "rifle" else mode
	mode_lbl.position.x = -730 if w.id == "rifle" else -330
	mode_lbl.size.x = 700 if w.id == "rifle" else 300
	var hp := player.health
	health_lbl.text = str(int(ceil(hp)))
	health_bar.size.x = 260.0 * hp / 100.0
	health_bar.color = Color(1, 0.3, 0.22) if hp < 35 else Color(0.92, 0.92, 0.9)
	var stance := "CROUCHED" if player.is_crouched() else "STANDING"
	gear_lbl.text = "%s    SHIELD x%d [G]    BREACH [V]    NV %d%% [N]%s" % [stance, player.shields_left, int(player.nv_battery * 100.0), " ON" if player.nv_on else ""]
	nv_rect.visible = player.nv_on
	if player.nv_on:
		var nm: ShaderMaterial = nv_rect.material
		nm.set_shader_parameter("time_s", Time.get_ticks_msec() / 1000.0)
		nm.set_shader_parameter("battery", player.nv_battery)
	# Messages
	if _msg_t > 0.0:
		_msg_t -= delta
		msg_lbl.modulate.a = clampf(_msg_t, 0.0, 1.0)
	else:
		msg_lbl.text = ""
	# Damage
	_dmg_flash = move_toward(_dmg_flash, 0.0, delta * 1.5)
	for d in _dmg_dirs:
		d[1] -= delta
	_dmg_dirs = _dmg_dirs.filter(func(d): return d[1] > 0.0)
	var low := clampf((40.0 - hp) / 40.0, 0.0, 1.0) if player.alive else 1.0
	var sm: ShaderMaterial = vignette.material
	sm.set_shader_parameter("damage", _dmg_flash)
	sm.set_shader_parameter("low_hp", low)
	sm.set_shader_parameter("ads", w.ads)
	_hb_cd -= delta
	if low > 0.4 and player.alive and _hb_cd <= 0.0:
		Sfx.play("heartbeat", -6.0 + low * 4.0, 0.0)
		_hb_cd = 1.1 - low * 0.35
	_hit_t -= delta
	cross.queue_redraw()
	marker.queue_redraw()


func _draw_cross() -> void:
	if player == null or not player.alive:
		return
	var w := player.weapon()
	var c := cross.size / 2.0
	var vis := 1.0 - clampf(w.ads * 2.0, 0.0, 1.0)
	if w._sprint_blend > 0.5:
		vis = 0.0
	if vis > 0.01:
		var spread: float = lerpf(w.stats.spread_hip, w.stats.spread_ads, w.ads) + player.movement_spread() * w.stats.spread_move
		var px := tan(deg_to_rad(spread * 0.5)) / tan(deg_to_rad(player.camera.fov * 0.5)) * cross.size.y * 0.5 + 6.0
		var col := Color(1, 1, 1, 0.85 * vis)
		var sh := Color(0, 0, 0, 0.5 * vis)
		for d in [Vector2.RIGHT, Vector2.LEFT, Vector2.UP, Vector2.DOWN]:
			cross.draw_line(c + d * px + Vector2(1, 1), c + d * (px + 9) + Vector2(1, 1), sh, 2.0)
			cross.draw_line(c + d * px, c + d * (px + 9), col, 2.0)
		cross.draw_circle(c, 1.5, col)
	if _hit_t > 0.0:
		var a := clampf(_hit_t / 0.18, 0.0, 1.0)
		var col2 := Color(_hit_col.r, _hit_col.g, _hit_col.b, a)
		for d in [Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1)]:
			cross.draw_line(c + d * 7, c + d * 15, col2, 2.0)
	# Damage direction arcs
	for d in _dmg_dirs:
		var ang: float = d[0] - PI / 2
		var a2 := clampf(d[1], 0.0, 1.0)
		cross.draw_arc(c, 150, ang - 0.28, ang + 0.28, 16, Color(1, 0.25, 0.15, 0.85 * a2), 5.0)


func _draw_marker() -> void:
	if player == null or Game.objective_text == "" or Game.state in [Game.State.COMPLETE, Game.State.FAILED, Game.State.BRIEFING]:
		return
	var cam := player.camera
	var p := Game.objective_pos + Vector3(0, 1.2, 0)
	var dist := cam.global_position.distance_to(p)
	var behind := cam.is_position_behind(p)
	var sp := cam.unproject_position(p)
	var sz := marker.size
	var margin := 60.0
	if behind:
		sp = sz - sp
		sp.y = sz.y - margin
	sp.x = clampf(sp.x, margin, sz.x - margin)
	sp.y = clampf(sp.y, margin, sz.y - margin)
	var ads := player.weapon().ads
	var alpha := 0.9 - ads * 0.6
	var col := Color(ACCENT.r, ACCENT.g, ACCENT.b, alpha)
	var pts := PackedVector2Array([sp + Vector2(0, -8), sp + Vector2(8, 0), sp + Vector2(0, 8), sp + Vector2(-8, 0), sp + Vector2(0, -8)])
	marker.draw_polyline(pts, col, 2.0)
	marker.draw_string(font, sp + Vector2(-30, 26), "%dm" % int(dist), HORIZONTAL_ALIGNMENT_CENTER, 60, 13, col)
