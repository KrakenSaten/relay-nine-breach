extends CanvasLayer
## Pause, settings, loadout (attachments) and end-of-mission screens; hosts the
## tactical briefing (Briefing) before deployment and for review from pause.

signal deploy

var font: Font
var panel: PanelContainer
var content: VBoxContainer
var screen := ""
var player: Player
var _style: StyleBoxFlat
var _dim: ColorRect
var _center: CenterContainer
var briefing: Briefing
var ui_test := false   # validation runs that drive the real menus (--ui_flow)

const ACCENT := Color(0.92, 0.72, 0.32)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 10
	ui_test = "--ui_flow" in OS.get_cmdline_user_args()
	var sf := SystemFont.new()
	sf.font_names = PackedStringArray(["Bahnschrift", "Segoe UI", "Arial"])
	font = sf
	var dim := ColorRect.new()
	dim.name = "Dim"
	dim.color = Color(0.0, 0.0, 0.0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	_dim = dim
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	_center = center
	panel = PanelContainer.new()
	_style = StyleBoxFlat.new()
	_style.bg_color = Color(0.06, 0.065, 0.07, 0.94)
	_style.border_color = Color(0.25, 0.26, 0.27)
	_style.border_width_left = 1
	_style.border_width_top = 1
	_style.border_width_right = 1
	_style.border_width_bottom = 1
	_style.content_margin_left = 36
	_style.content_margin_right = 36
	_style.content_margin_top = 28
	_style.content_margin_bottom = 28
	panel.add_theme_stylebox_override("panel", _style)
	center.add_child(panel)
	content = VBoxContainer.new()
	content.add_theme_constant_override("separation", 10)
	content.custom_minimum_size = Vector2(760, 0)
	panel.add_child(content)
	Game.request_loadout.connect(func(): open("loadout"))
	briefing = Briefing.new()
	briefing.name = "Briefing"
	add_child(briefing)
	briefing.deploy_confirmed.connect(_deploy)
	briefing.request.connect(_on_briefing_request)
	hide_all()


func hide_all() -> void:
	screen = ""
	visible = false
	if briefing:
		briefing.dismiss()
	get_tree().paused = false
	if Game.state not in [Game.State.COMPLETE, Game.State.FAILED, Game.State.BRIEFING]:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if Game.autotest and not ui_test:
		return
	if event.is_action_pressed("pause"):
		if screen == "":
			if Game.is_active():
				open("pause")
		elif screen == "briefing_review":
			open("pause")
		elif screen in ["pause", "settings", "loadout"] and Game.state != Game.State.BRIEFING:
			if screen == "pause":
				hide_all()
			else:
				open("pause")
		elif screen in ["settings", "loadout"]:
			open("briefing")
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("loadout") and screen == "" and Game.is_active():
		open("loadout")
		get_viewport().set_input_as_handled()


func open(s: String) -> void:
	screen = s
	visible = true
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	for c in content.get_children():
		c.queue_free()
	var brief := s in ["briefing", "briefing_review"]
	_dim.visible = not brief
	_center.visible = not brief
	if brief:
		briefing.present("deploy" if s == "briefing" else "review", get_parent())
	else:
		briefing.dismiss()
	match s:
		"pause": _pause()
		"settings": _settings()
		"loadout": _loadout()
		"complete": _end(true)
		"failed": _end(false)


func _title(t: String, size := 34, col := Color(0.95, 0.94, 0.9)) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	content.add_child(l)
	return l


func _text(t: String, size := 16, col := Color(0.78, 0.79, 0.77)) -> Label:
	var l := _title(t, size, col)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD
	l.custom_minimum_size.x = 700
	return l


func _button(t: String, cb: Callable, parent: Control = null, selected := false) -> Button:
	var b := Button.new()
	b.text = t
	b.add_theme_font_override("font", font)
	b.add_theme_font_size_override("font_size", 18)
	var n := StyleBoxFlat.new()
	n.bg_color = Color(0.13, 0.135, 0.14) if not selected else Color(0.35, 0.27, 0.1)
	n.border_color = ACCENT if selected else Color(0.3, 0.3, 0.3)
	n.border_width_bottom = 2
	n.content_margin_left = 14
	n.content_margin_right = 14
	n.content_margin_top = 8
	n.content_margin_bottom = 8
	var h := n.duplicate()
	h.bg_color = Color(0.22, 0.2, 0.15)
	h.border_color = ACCENT
	b.add_theme_stylebox_override("normal", n)
	b.add_theme_stylebox_override("hover", h)
	b.add_theme_stylebox_override("pressed", h)
	b.add_theme_stylebox_override("focus", n)
	b.add_theme_color_override("font_color", Color(0.92, 0.92, 0.9))
	b.pressed.connect(func():
		Sfx.play("ui_click", -6.0)
		cb.call())
	(parent if parent else content).add_child(b)
	return b


func _spacer(h := 8) -> void:
	var c := Control.new()
	c.custom_minimum_size.y = h
	content.add_child(c)


# ---------------------------------------------------------------- screens
func _on_briefing_request(what: String) -> void:
	match what:
		"loadout": open("loadout")
		"settings": open("settings")
		"quit": get_tree().quit()
		"return": open("pause")


func _deploy() -> void:
	hide_all()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	deploy.emit()


func _pause() -> void:
	_title("PAUSED", 40)
	_text("Objective: " + Game.objective_text, 15)
	_spacer()
	_button("RESUME", hide_all)
	_button("MISSION BRIEFING", func(): open("briefing_review"))
	_button("LOADOUT", func(): open("loadout"))
	_button("SETTINGS", func(): open("settings"))
	if _has_checkpoint():
		_button("RESTART FROM CHECKPOINT - " + String(Game.checkpoint.name).to_upper(), _restart_checkpoint)
	_button("RESTART MISSION", _restart)
	_button("QUIT TO DESKTOP", func(): get_tree().quit())


func _back() -> void:
	open("briefing" if Game.state == Game.State.BRIEFING else "pause")


func _settings() -> void:
	_title("SETTINGS", 36)
	_text("GRAPHICS QUALITY", 14, ACCENT)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	content.add_child(row)
	for i in Settings.PRESETS.size():
		var q := i
		_button(Settings.PRESETS[i].to_upper(), func(): Settings.set_quality(q); open("settings"), row, Settings.quality == i)
	_text(["Low: no GI/SSR/SSAO, simple fog, 77% res + FSR2, FXAA.", "Medium: SSAO, volumetric fog, FXAA.", "High: SDFGI, SSR, SSAO, filtered volumetric fog, TAA.", "Ultra: + SSIL, 32-ray GI, larger shadow atlas, sharper fog."][Settings.quality], 13, Color(0.6, 0.62, 0.6))
	_slider("FIELD OF VIEW", 70, 110, Settings.fov, 1, func(v): Settings.fov = v)
	_slider("MOUSE SENSITIVITY", 0.5, 6.0, Settings.sensitivity * 1000.0, 0.1, func(v): Settings.sensitivity = v / 1000.0)
	_slider("RENDER SCALE %", 50, 100, Settings.render_scale * 100.0, 5, func(v): Settings.render_scale = v / 100.0; Settings.apply())
	_slider("MASTER VOLUME", 0, 100, Settings.master_volume * 100.0, 1, func(v): Settings.master_volume = v / 100.0; Settings.apply_audio())
	var row2 := HBoxContainer.new()
	row2.add_theme_constant_override("separation", 8)
	content.add_child(row2)
	_button("VSYNC: " + ("ON" if Settings.vsync else "OFF"), func(): Settings.vsync = not Settings.vsync; Settings.apply(); open("settings"), row2)
	_button("FPS COUNTER: " + ("ON" if Settings.show_fps else "OFF"), func(): Settings.show_fps = not Settings.show_fps; open("settings"), row2)
	_spacer()
	_button("BACK", func(): Settings.save_settings(); _back())


func _slider(label: String, mn: float, mx: float, val: float, step: float, cb: Callable) -> void:
	var row := HBoxContainer.new()
	content.add_child(row)
	var l := Label.new()
	l.text = label
	l.custom_minimum_size.x = 260
	l.add_theme_font_override("font", font)
	l.add_theme_color_override("font_color", Color(0.78, 0.79, 0.77))
	row.add_child(l)
	var s := HSlider.new()
	s.min_value = mn
	s.max_value = mx
	s.step = step
	s.value = val
	s.custom_minimum_size.x = 340
	s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(s)
	var v := Label.new()
	v.text = str(snappedf(val, step))
	v.custom_minimum_size.x = 60
	v.add_theme_font_override("font", font)
	row.add_child(v)
	s.value_changed.connect(func(x):
		v.text = str(snappedf(x, step))
		cb.call(x))


func _loadout() -> void:
	_title("VK-9 CARBINE  //  LOADOUT", 30)
	var l: Dictionary = player.loadout if player else WeaponDefs.DEFAULT_LOADOUT
	for slot in ["optic", "muzzle", "grip", "mag"]:
		_text(slot.to_upper(), 13, ACCENT)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 8)
		content.add_child(row)
		for att in WeaponDefs.SLOTS[slot]:
			var a: String = att
			var s: String = slot
			_button(WeaponDefs.ATTACHMENTS[a].label, _pick.bind(s, a), row, l[slot] == a)
		_text(WeaponDefs.ATTACHMENTS[l[slot]].desc, 13, Color(0.6, 0.62, 0.6))
	if player:
		var st: Dictionary = player.weapons[0].stats
		_spacer(4)
		_text("DAMAGE %.0f   RPM %.0f   MAG %d   RELOAD %.2fs   AIM %.2fs   V-RECOIL %.2f   H-RECOIL %.2f   NOISE %.0fm   ADS ZOOM %.2fx" % [
			st.damage, st.rpm, st.mag, st.reload, st.ads_time, st.recoil_v, st.recoil_h, st.noise, 0.86 / st.ads_fov], 14, Color(0.85, 0.86, 0.84))
		_text("Changes apply immediately. Magazine size changes take effect on the next reload.", 12, Color(0.5, 0.52, 0.5))
	_spacer()
	_button("BACK", _back)


func _pick(slot: String, att: String) -> void:
	if player:
		var nl: Dictionary = player.loadout.duplicate()
		nl[slot] = att
		player.set_loadout(nl)
	open("loadout")


func _restart() -> void:
	Game.checkpoint = {}
	get_tree().paused = false
	get_tree().reload_current_scene()


func _restart_checkpoint() -> void:
	Game.checkpoint.pending = true
	get_tree().paused = false
	get_tree().reload_current_scene()


func _has_checkpoint() -> bool:
	return Game.checkpoint.has("name") and Game.state != Game.State.COMPLETE


func _end(win: bool) -> void:
	var s := Game.stats
	_title("MISSION COMPLETE" if win else "OPERATOR DOWN", 44, ACCENT if win else Color(1, 0.35, 0.25))
	_text("Relay Nine destroyed. Extraction on Freight Lift 2 confirmed." if win else "The Teslabots hold Substation 9-B.", 17)
	_spacer()
	var acc = 0.0 if s.shots == 0 else float(s.hits) / s.shots * 100.0
	_text("TIME  %d:%02d      KILLS  %d      ACCURACY  %.0f%%      CORE OVERLOADS  %d      OPTIC HITS  %d      DAMAGE TAKEN  %d" % [
		int(Game.elapsed()) / 60, int(Game.elapsed()) % 60, s.kills, acc, s.core_kills, s.head_hits, s.damage_taken], 15, Color(0.85, 0.86, 0.84))
	_spacer()
	if not win and _has_checkpoint():
		_button("RESTART FROM CHECKPOINT - " + String(Game.checkpoint.name).to_upper(), _restart_checkpoint, null, true)
	_button("RESTART MISSION", _restart)
	_button("QUIT TO DESKTOP", func(): get_tree().quit())
