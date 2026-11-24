class_name Briefing
extends CanvasLayer
## Operation DEADBAND: the pre-mission tactical briefing, and its in-mission
## review from the pause menu. Built in code like the other menus; every
## objective, location and estimate comes from the running mission
## (BriefingIntel), and the map is the level's own plan (TacticalMap).

signal deploy_confirmed
signal request(what: String)   # "loadout", "settings", "quit", "return"

const AMBER := Color(0.93, 0.7, 0.3)
const RED := Color(0.88, 0.3, 0.24)
const CYAN := Color(0.62, 0.86, 0.92)
const INK := Color(0.91, 0.92, 0.89)
const BODY := Color(0.7, 0.74, 0.73)
const MUTED := Color(0.47, 0.52, 0.53)
const LINE := Color(0.2, 0.24, 0.26)
const PANEL_BG := Color(0.016, 0.021, 0.025, 0.8)

const SITREP := "Relay Nine, the substation's control relay, lost sync with the grid 41 hours ago and took the security network with it. Its Teslabot units have sealed the control wing. Both main breakers are open; relay control is on battery, with no uplink. The night shift got out through the crawlway. Two technicians are unaccounted for."
const PRIMARY := "Upload the manual override at relay control and return Relay Nine to operator command."
const KEYS := "WASD MOVE   SHIFT SPRINT   CTRL CROUCH   Q/E LEAN   RMB AIM   R RELOAD   B FIRE MODE   F INTERACT   V BREACH   G SHIELD   N NIGHT VISION   T LOADOUT   ESC PAUSE"

static var _seen := false          # the full reveal plays on the first briefing of a session
static var _clock0 := -1.0         # mission clock (02:40 local at the first briefing)

var main: Node
var mode := "deploy"
var busy := false
var intel := {}

var f_display: Font
var f_head: Font
var f_title: Font
var f_body: Font
var f_mono: Font
var f_label: Font
var f_bold: Font

var _root: Control
var _backdrop: ColorRect
var _fx: ColorRect
var _fade: ColorRect
var _card: Control
var _card_line: Label
var _top: Control
var _left: Control
var _center: Control
var _right: Control
var _bottom: Control
var _map: TacticalMap
var _rows_box: VBoxContainer
var _rows := {}                # id -> ObjRow
var _sec_rows: Array[Control] = []
var _chips: HBoxContainer
var _clock: Label
var _sitrep: Label
var _threat_units: Label
var _bars: Control
var _prog: Control
var _deploy: Button
var _charge: ColorRect
var _return: Button
var _side_buttons: HBoxContainer
var _tween: Tween
var _skip_ok := false
var _keys: Label
var _map_note: Label
var _user_t := -100.0          # last time the player pointed at something (pauses the idle spotlight)
var _cycle_t := 0.0
var _cycle_i := 0


func _ready() -> void:
	layer = 11
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	_fonts()
	_build()


# ------------------------------------------------------------------ fonts
func _var(weight: int, width := 100, spacing := 0) -> Font:
	var sf := SystemFont.new()
	sf.font_names = PackedStringArray(["Bahnschrift", "Segoe UI", "Arial"])
	var fv := FontVariation.new()
	fv.base_font = sf
	var ts := TextServerManager.get_primary_interface()
	fv.variation_opentype = {ts.name_to_tag("wght"): weight, ts.name_to_tag("wdth"): width}
	fv.spacing_glyph = spacing
	return fv


func _fonts() -> void:
	f_display = _var(600, 75, 3)
	f_head = _var(600, 100, 2)
	f_title = _var(600, 100, 1)
	f_bold = _var(700, 100, 0)
	f_body = _var(350, 100, 0)
	f_label = _var(500, 100, 1)
	var sm := SystemFont.new()
	sm.font_names = PackedStringArray(["Cascadia Mono", "Consolas", "Courier New"])
	var mv := FontVariation.new()
	mv.base_font = sm
	mv.spacing_glyph = 1
	f_mono = mv


func _lbl(text: String, font: Font, size: int, col: Color, wrap := false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if wrap:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return l


# ------------------------------------------------------------------ layout
func _build() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)
	_backdrop = ColorRect.new()
	_backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	_backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_backdrop.material = _shader(BACKDROP_SHADER)
	_root.add_child(_backdrop)
	var safe := MarginContainer.new()
	safe.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right"]:
		safe.add_theme_constant_override("margin_" + side, 44)
	safe.add_theme_constant_override("margin_top", 26)
	safe.add_theme_constant_override("margin_bottom", 18)
	safe.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(safe)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 14)
	vb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	safe.add_child(vb)
	_top = _top_bar()
	vb.add_child(_top)
	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 14)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(body)
	_left = _left_column()
	body.add_child(_left)
	_center = _map_panel()
	body.add_child(_center)
	_right = _right_column()
	body.add_child(_right)
	_bottom = _bottom_bar()
	vb.add_child(_bottom)
	_keys = _lbl(KEYS, f_mono, 11, Color(MUTED, 0.8))
	_keys.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(_keys)
	_fx = ColorRect.new()
	_fx.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fx.material = _shader(FX_SHADER)
	add_child(_fx)
	_card = _title_card()
	add_child(_card)
	_fade = ColorRect.new()
	_fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade.color = Color(0, 0, 0, 0)
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_fade)
	move_child(_card, -1)


func _top_bar() -> Control:
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 0)
	hb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var id := VBoxContainer.new()
	id.add_theme_constant_override("separation", -2)
	id.add_child(_lbl("INCIDENT RESPONSE  //  SUBSTATION 9-B  //  132 KV", f_mono, 12, MUTED))
	id.add_child(_lbl("OPERATION DEADBAND", f_display, 42, INK))
	hb.add_child(id)
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hb.add_child(sp)
	_chips = HBoxContainer.new()
	_chips.add_theme_constant_override("separation", 26)
	_chips.alignment = BoxContainer.ALIGNMENT_END
	hb.add_child(_chips)
	var gap := Control.new()
	gap.custom_minimum_size.x = 34
	hb.add_child(gap)
	var cls := VBoxContainer.new()
	cls.add_theme_constant_override("separation", 2)
	cls.alignment = BoxContainer.ALIGNMENT_CENTER
	var tag := PanelContainer.new()
	var ts := StyleBoxFlat.new()
	ts.bg_color = Color(AMBER, 0.08)
	ts.border_color = Color(AMBER, 0.7)
	ts.set_border_width_all(1)
	ts.content_margin_left = 10
	ts.content_margin_right = 8
	ts.content_margin_top = 2
	ts.content_margin_bottom = 2
	tag.add_theme_stylebox_override("panel", ts)
	tag.add_child(_lbl("RESTRICTED  ·  SINGLE OPERATOR", f_head, 12, AMBER))
	cls.add_child(tag)
	var clk := HBoxContainer.new()
	clk.alignment = BoxContainer.ALIGNMENT_END
	clk.add_theme_constant_override("separation", 8)
	_clock = _lbl("02:40:00", f_mono, 24, INK)
	clk.add_child(_clock)
	var loc := _lbl("LOCAL", f_mono, 11, MUTED)
	loc.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	clk.add_child(loc)
	cls.add_child(clk)
	hb.add_child(cls)
	var wrap := VBoxContainer.new()
	wrap.add_theme_constant_override("separation", 10)
	wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	wrap.add_child(hb)
	var rule := Control.new()
	rule.custom_minimum_size.y = 2
	rule.draw.connect(func():
		rule.draw_line(Vector2(0, 0.5), Vector2(rule.size.x, 0.5), LINE, 1.0)
		rule.draw_line(Vector2(0, 0.5), Vector2(140, 0.5), AMBER, 2.0))
	wrap.add_child(rule)
	return wrap


func _chip(key: String, value: String, col: Color) -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 0)
	v.add_child(_lbl(key, f_mono, 10, MUTED))
	var l := _lbl(value, f_head, 14, col)
	v.add_child(l)
	return v


func _panel(inner: Control, min_w := 0.0) -> PanelContainer:
	var p := PanelContainer.new()
	var s := StyleBoxFlat.new()
	s.bg_color = PANEL_BG
	s.border_color = LINE
	s.set_border_width_all(1)
	s.content_margin_left = 22
	s.content_margin_right = 24
	s.content_margin_top = 16
	s.content_margin_bottom = 16
	p.add_theme_stylebox_override("panel", s)
	p.custom_minimum_size.x = min_w
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(inner)
	# Corner brackets on the panel's own edge (a child would sit inside the margins).
	p.draw.connect(func():
		var z := p.size
		var k := 12.0
		var col := Color(AMBER, 0.75)
		for c in [[Vector2(0, 0), 1, 1], [Vector2(z.x, 0), -1, 1], [Vector2(z.x, z.y), -1, -1], [Vector2(0, z.y), 1, -1]]:
			p.draw_line(c[0], c[0] + Vector2(k * c[1], 0), col, 2.0)
			p.draw_line(c[0], c[0] + Vector2(0, k * c[2]), col, 2.0))
	return p


func _header(title: String, note := "") -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 10)
	var tick := ColorRect.new()
	tick.color = AMBER
	tick.custom_minimum_size = Vector2(3, 12)
	tick.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(tick)
	h.add_child(_lbl(title, f_head, 13, INK))
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(sp)
	if note != "":
		var n := _lbl(note, f_mono, 10, MUTED)
		n.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(n)
	v.add_child(h)
	var line := ColorRect.new()
	line.color = LINE
	line.custom_minimum_size.y = 1
	v.add_child(line)
	return v


func _left_column() -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	v.add_child(_header("SITUATION", "SYNC LOST T+41H"))
	_sitrep = _lbl(SITREP, f_body, 16, BODY, true)
	v.add_child(_sitrep)
	v.add_child(_gap(4))
	v.add_child(_header("PRIMARY OBJECTIVE"))
	v.add_child(_lbl(PRIMARY, f_title, 17, INK, true))
	v.add_child(_gap(4))
	v.add_child(_header("TASKING", "01 AND 02 IN EITHER ORDER"))
	_rows_box = VBoxContainer.new()
	_rows_box.add_theme_constant_override("separation", 2)
	v.add_child(_rows_box)
	v.add_child(_gap(4))
	v.add_child(_header("SECONDARY", "OPTIONAL"))
	var sec := VBoxContainer.new()
	sec.add_theme_constant_override("separation", 2)
	_sec_rows.append(_row("AMMO", "", "AMMUNITION", "SECURITY OFFICE  ·  SWITCHGEAR HALL  ·  RELAY CONTROL", "Three caches. Hold F to top up; limited stock, no refill.", true))
	_sec_rows.append(_row("STM", "", "STEAM PURGE", "PUMP STATION 2  ·  VALVE BY THE EAST DOOR", "Blinds units in the pump hall for about 20 seconds.", true))
	for r in _sec_rows:
		sec.add_child(r)
	v.add_child(sec)
	return _panel(v, 470)


func _gap(h: float) -> Control:
	var c := Control.new()
	c.custom_minimum_size.y = h
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


func _map_panel() -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	var tick := ColorRect.new()
	tick.color = AMBER
	tick.custom_minimum_size = Vector2(3, 12)
	tick.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(tick)
	h.add_child(_lbl("TACTICAL OVERVIEW", f_head, 13, INK))
	var sub := _lbl("SUBSTATION 9-B  ·  SITE PLAN, GROUND LEVEL  ·  GALLERIES HATCHED", f_mono, 10, MUTED)
	sub.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(sub)
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(sp)
	_map_note = _lbl("GRID 10 M  ·  NORTH UP", f_mono, 10, Color(CYAN, 0.8))
	_map_note.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(_map_note)
	v.add_child(h)
	_map = TacticalMap.new()
	_map.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_map.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_map.font_label = f_label
	_map.font_mono = f_mono
	_map.font_bold = f_bold
	_map.marker_hovered.connect(_on_map_hover)
	v.add_child(_map)
	v.add_child(_legend())
	var p := _panel(v)
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return p


func _legend() -> Control:
	var c := Control.new()
	c.custom_minimum_size.y = 18
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.draw.connect(func():
		var x := 4.0
		var y := 9.0
		var items := [["obj", "OBJECTIVE"], ["ext", "EXTRACTION"], ["ins", "INSERTION"], ["hos", "HOSTILE, LAST KNOWN"], ["dor", "DORMANT"], ["sea", "SEALED"], ["rte", "ROUTE"], ["gal", "GALLERY"]]
		for it in items:
			var p := Vector2(x + 6, y)
			match it[0]:
				"obj":
					c.draw_polyline(PackedVector2Array([p + Vector2(0, -5), p + Vector2(5, 0), p + Vector2(0, 5), p + Vector2(-5, 0), p + Vector2(0, -5)]), AMBER, 1.5)
				"ext":
					c.draw_rect(Rect2(p - Vector2(4, 4), Vector2(8, 8)), AMBER, false, 1.5)
				"ins":
					c.draw_colored_polygon(PackedVector2Array([p + Vector2(0, -5), p + Vector2(4.5, 4), p + Vector2(0, 1.5), p + Vector2(-4.5, 4)]), CYAN)
				"hos":
					c.draw_colored_polygon(PackedVector2Array([p + Vector2(0, -3.5), p + Vector2(3.5, 0), p + Vector2(0, 3.5), p + Vector2(-3.5, 0)]), RED)
				"dor":
					c.draw_polyline(PackedVector2Array([p + Vector2(0, -3.5), p + Vector2(3.5, 0), p + Vector2(0, 3.5), p + Vector2(-3.5, 0), p + Vector2(0, -3.5)]), RED, 1.2)
				"sea":
					c.draw_line(p - Vector2(6, 0), p + Vector2(6, 0), RED, 3.0)
				"rte":
					for k in 3:
						c.draw_line(p + Vector2(-7 + k * 5, 0), p + Vector2(-4 + k * 5, 0), CYAN, 1.5)
				"gal":
					for k in 3:
						c.draw_line(p + Vector2(-5 + k * 4, 5), p + Vector2(-1 + k * 4, -5), Color(CYAN, 0.5), 1.0)
			c.draw_string(f_mono, Vector2(x + 18, y + 4), it[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 10, MUTED)
			x += 30 + f_mono.get_string_size(it[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 10).x)
	return c


func _right_column() -> Control:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 9)
	var hh := _header("THREAT ASSESSMENT", "PRE-DEPLOYMENT ESTIMATE")
	v.add_child(hh)
	var lvl := HBoxContainer.new()
	lvl.add_theme_constant_override("separation", 12)
	lvl.add_child(_lbl("THREAT", f_mono, 11, MUTED))
	var seg := Control.new()
	seg.custom_minimum_size = Vector2(130, 14)
	seg.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	seg.draw.connect(func():
		for i in 5:
			var r := Rect2(i * 26, 2, 22, 9)
			if i < 4:
				seg.draw_rect(r, Color(RED, 0.35 + 0.13 * i))
			else:
				seg.draw_rect(r, Color(RED, 0.5), false, 1.0))
	lvl.add_child(seg)
	lvl.add_child(_lbl("HIGH", f_head, 14, RED))
	v.add_child(lvl)
	var uh := HBoxContainer.new()
	uh.add_child(_lbl("TESLABOT SECURITY UNITS", f_title, 15, INK))
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	uh.add_child(sp)
	_threat_units = _lbl("", f_mono, 12, Color(RED, 0.95))
	uh.add_child(_threat_units)
	v.add_child(uh)
	_bars = Control.new()
	_bars.custom_minimum_size.y = 7 * 17
	_bars.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bars.draw.connect(_draw_bars)
	v.add_child(_bars)
	for t in ["Every arc discharge is telegraphed by a blue charge glow. Move while it builds.",
			"The rear capacitor stack overloads under fire. A destroyed optic blinds the unit.",
			"They hear gunfire through walls. A room's breaker panel kills its lights; units lose sight range until they switch to infrared."]:
		v.add_child(_bullet(t, RED))
	var rn := HBoxContainer.new()
	rn.add_theme_constant_override("separation", 10)
	var rl := _lbl("RELAY NINE", f_head, 12, AMBER)
	rl.custom_minimum_size.x = 92
	rn.add_child(rl)
	rn.add_child(_lbl("Commands every unit and watches the grid. Breaker load changes and the uplink will draw them. It will not take the override quietly.", f_body, 14, BODY, true))
	v.add_child(rn)
	v.add_child(_gap(2))
	v.add_child(_header("FACILITY INTEL"))
	for r in [["A", "SERVICE CORRIDOR C", "Direct to the office and the turbine hall. Patrolled."],
			["B", "SHUTTER", "Dock to turbine hall. Crouch only; units cannot path through it."],
			["C", "CRAWLWAY", "Dock to pump station. Crouch only; units cannot follow."]]:
		v.add_child(_route_row(r[0], r[1], r[2]))
	for t in ["Turbine hall: 9 m high, machinery for hard cover. Charge bays 04 and 06 hold dormant units.",
			"Relay Nine core: south of the data centre, behind a sealed blast door.",
			"Insertion at the loading dock. The armory case there configures your carbine."]:
		v.add_child(_bullet(t, CYAN))
	return _panel(v, 430)


func _bullet(text: String, col: Color) -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 10)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var dot := Control.new()
	dot.custom_minimum_size = Vector2(6, 16)
	dot.draw.connect(func(): dot.draw_rect(Rect2(0, 7, 5, 2), col))
	h.add_child(dot)
	h.add_child(_lbl(text, f_body, 14, BODY, true))
	return h


func _route_row(letter: String, name: String, text: String) -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 10)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var badge := PanelContainer.new()
	var s := StyleBoxFlat.new()
	s.bg_color = Color(CYAN, 0.08)
	s.border_color = Color(CYAN, 0.55)
	s.set_border_width_all(1)
	s.content_margin_left = 6
	s.content_margin_right = 5
	badge.add_theme_stylebox_override("panel", s)
	badge.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	badge.add_child(_lbl(letter, f_mono, 12, CYAN))
	h.add_child(badge)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", -1)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_child(_lbl(name, f_head, 12, INK))
	v.add_child(_lbl(text, f_body, 14, BODY, true))
	h.add_child(v)
	return h


func _draw_bars() -> void:
	var counts: Dictionary = intel.get("counts", {})
	var list := []
	for r in counts:
		list.append([r, counts[r][0], counts[r][1]])
	list.sort_custom(func(a, b): return a[1] + a[2] > b[1] + b[2])
	var y := 12.0
	for e in list.slice(0, 7):
		var name: String = BriefingIntel.NAMES.get(e[0], str(e[0]).to_upper())
		_bars.draw_string(f_label, Vector2(0, y), name, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, BODY)
		var x := 170.0
		for i in e[1]:
			_bars.draw_rect(Rect2(x, y - 8, 12, 7), Color(RED, 0.85))
			x += 15
		for i in e[2]:
			_bars.draw_rect(Rect2(x, y - 8, 12, 7), Color(RED, 0.8), false, 1.0)
			x += 15
		var n := "%d" % e[1] + (" +%d DORMANT" % e[2] if e[2] > 0 else "")
		_bars.draw_string(f_mono, Vector2(x + 6, y), n, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, MUTED)
		y += 17


func _bottom_bar() -> Control:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	h.custom_minimum_size.y = 84
	_prog = Control.new()
	_prog.custom_minimum_size.y = 62
	_prog.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_prog.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prog.draw.connect(_draw_progression)
	var pp := _panel(_prog)
	var ps: StyleBoxFlat = pp.get_theme_stylebox("panel")
	ps.content_margin_top = 10
	ps.content_margin_bottom = 8
	pp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(pp)
	_side_buttons = HBoxContainer.new()
	_side_buttons.add_theme_constant_override("separation", 8)
	_side_buttons.add_child(_ghost("LOADOUT", func(): request.emit("loadout")))
	_side_buttons.add_child(_ghost("SETTINGS", func(): request.emit("settings")))
	_side_buttons.add_child(_ghost("QUIT", func(): request.emit("quit")))
	h.add_child(_side_buttons)
	_deploy = _primary_button("DEPLOY", "ENTER")
	_deploy.pressed.connect(start_deploy)
	h.add_child(_deploy)
	_charge = ColorRect.new()
	_charge.color = Color(1, 1, 1, 0.28)
	_charge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_charge.size = Vector2(0, 0)
	_deploy.add_child(_charge)
	_return = _primary_button("RETURN", "ESC")
	_return.pressed.connect(func(): request.emit("return"))
	h.add_child(_return)
	return h


func _ghost(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(128, 0)
	b.add_theme_font_override("font", f_head)
	b.add_theme_font_size_override("font_size", 14)
	var n := StyleBoxFlat.new()
	n.bg_color = Color(0.03, 0.036, 0.04, 0.85)
	n.border_color = LINE
	n.set_border_width_all(1)
	var hv := n.duplicate()
	hv.bg_color = Color(AMBER, 0.08)
	hv.border_color = Color(AMBER, 0.8)
	var fc := hv.duplicate()
	fc.draw_center = false
	b.add_theme_stylebox_override("normal", n)
	b.add_theme_stylebox_override("hover", hv)
	b.add_theme_stylebox_override("pressed", hv)
	b.add_theme_stylebox_override("focus", fc)
	b.add_theme_color_override("font_color", BODY)
	b.add_theme_color_override("font_hover_color", INK)
	b.add_theme_color_override("font_focus_color", INK)
	b.pressed.connect(func():
		Sfx.play("ui_click", -8.0)
		cb.call())
	b.focus_entered.connect(_tick)
	return b


func _primary_button(text: String, key: String) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(300, 0)
	b.add_theme_font_override("font", f_display)
	b.add_theme_font_size_override("font_size", 30)
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	var n := StyleBoxFlat.new()
	n.bg_color = Color(0.86, 0.64, 0.26)
	n.border_color = Color(1.0, 0.86, 0.55)
	n.border_width_top = 1
	n.content_margin_left = 26
	var hv := n.duplicate()
	hv.bg_color = Color(0.96, 0.74, 0.32)
	var fc := StyleBoxFlat.new()
	fc.draw_center = false
	fc.border_color = Color(1, 0.93, 0.78)
	fc.set_border_width_all(2)
	fc.expand_margin_left = 3
	fc.expand_margin_right = 3
	fc.expand_margin_top = 3
	fc.expand_margin_bottom = 3
	b.add_theme_stylebox_override("normal", n)
	b.add_theme_stylebox_override("hover", hv)
	b.add_theme_stylebox_override("pressed", hv)
	b.add_theme_stylebox_override("disabled", n)
	b.add_theme_stylebox_override("focus", fc)
	for c in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_disabled_color"]:
		b.add_theme_color_override(c, Color(0.05, 0.045, 0.035))
	var k := _lbl(key, f_mono, 11, Color(0.05, 0.045, 0.035, 0.75))
	k.anchor_left = 1.0
	k.anchor_right = 1.0
	k.anchor_top = 0.5
	k.anchor_bottom = 0.5
	k.offset_left = -92
	k.offset_right = -40
	k.offset_top = -8
	k.offset_bottom = 8
	k.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	b.add_child(k)
	var ar := Control.new()
	ar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ar.set_anchors_preset(Control.PRESET_FULL_RECT)
	ar.draw.connect(func():
		var cy := ar.size.y * 0.5
		var x0 := ar.size.x - 26.0
		for i in 2:
			var x := x0 + i * 8.0
			ar.draw_polyline(PackedVector2Array([Vector2(x - 5, cy - 7), Vector2(x, cy), Vector2(x - 5, cy + 7)]), Color(0.05, 0.045, 0.035, 0.85), 2.0))
	b.add_child(ar)
	return b


func _title_card() -> Control:
	var cc := CenterContainer.new()
	cc.set_anchors_preset(Control.PRESET_FULL_RECT)
	cc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cc.modulate.a = 0.0
	cc.visible = false
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	var top := _lbl("SUBSTATION 9-B  ·  LOADING DOCK", f_mono, 13, MUTED)
	top.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(top)
	var t := _lbl("OPERATION DEADBAND", f_display, 60, INK)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t)
	var rule := Control.new()
	rule.custom_minimum_size = Vector2(520, 2)
	rule.draw.connect(func():
		rule.draw_line(Vector2(0, 1), Vector2(rule.size.x, 1), Color(LINE, 1.0), 1.0)
		rule.draw_line(Vector2(rule.size.x * 0.5 - 40, 1), Vector2(rule.size.x * 0.5 + 40, 1), AMBER, 2.0))
	v.add_child(rule)
	_card_line = _lbl("", f_mono, 13, Color(AMBER, 0.9))
	_card_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_card_line)
	cc.add_child(v)
	return cc


# ------------------------------------------------------------------ rows
class ObjRow extends PanelContainer:
	signal hovered(id: String)
	var id := ""
	var normal: StyleBoxFlat
	var active: StyleBoxFlat

	func _init() -> void:
		focus_mode = Control.FOCUS_ALL
		mouse_filter = Control.MOUSE_FILTER_STOP
		mouse_entered.connect(func(): _mark(true))
		mouse_exited.connect(func(): _mark(has_focus()))
		focus_entered.connect(func(): _mark(true))
		focus_exited.connect(func(): _mark(false))

	func _mark(on: bool) -> void:
		add_theme_stylebox_override("panel", active if on else normal)
		if on:
			hovered.emit(id)
		elif not has_focus():
			hovered.emit("")

	func _gui_input(e: InputEvent) -> void:
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			grab_focus()


func _row(id: String, num: String, title: String, sub: String, detail: String, small := false, status := "", status_col := MUTED) -> ObjRow:
	var r := ObjRow.new()
	r.id = id
	r.normal = StyleBoxFlat.new()
	r.normal.bg_color = Color(0, 0, 0, 0)
	r.normal.border_color = Color(LINE, 1.0)
	r.normal.border_width_left = 2
	r.normal.content_margin_left = 12
	r.normal.content_margin_right = 8
	r.normal.content_margin_top = 6 if not small else 4
	r.normal.content_margin_bottom = 6 if not small else 4
	r.active = r.normal.duplicate()
	r.active.bg_color = Color(AMBER, 0.07)
	r.active.border_color = AMBER
	r.add_theme_stylebox_override("panel", r.normal)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if num != "":
		var n := _lbl(num, f_display, 26, MUTED if status in ["PENDING", "COMPLETE"] else (RED if status == "REJECTED" else AMBER))
		n.custom_minimum_size.x = 34
		n.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		h.add_child(n)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 0)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var th := HBoxContainer.new()
	th.mouse_filter = Control.MOUSE_FILTER_IGNORE
	th.add_child(_lbl(title, f_title, 15 if small else 17, INK))
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sp.mouse_filter = Control.MOUSE_FILTER_IGNORE
	th.add_child(sp)
	if status != "":
		th.add_child(_lbl(status, f_mono, 11, status_col))
	v.add_child(th)
	v.add_child(_lbl(sub, f_mono, 10, MUTED))
	v.add_child(_lbl(detail, f_body, 14, BODY, true))
	h.add_child(v)
	r.add_child(h)
	r.hovered.connect(_on_row_hover)
	return r


func _rebuild_rows() -> void:
	for c in _rows_box.get_children():
		c.queue_free()
	_rows.clear()
	var f: Dictionary = main.mission.flags
	var stage: String = main.mission.stage
	var m := {}
	for mk in intel.markers:
		m[mk.id] = mk
	var g := func(id: String) -> String: return BriefingIntel.grid_ref(m[id].pos) if m.has(id) else ""
	var st := func(done: bool, active: bool, text_active := "ACTIVE") -> Array:
		if mode != "review":
			return ["", MUTED]
		if done:
			return ["COMPLETE", Color(CYAN, 0.9)]
		return [text_active, AMBER] if active else ["PENDING", MUTED]
	var infil: bool = stage == "infiltrate"
	var rows := [
		["01", "01", "RELEASE THE LOCKDOWN", "SECURITY OFFICE 9-B  ·  GRID %s" % g.call("01"), "Hold the lockdown panel. Unseals D5, D6 and D11 into the control wing.", st.call(f.lockdown, infil)],
		["02", "02", "RESTORE MAIN POWER", "SWITCHGEAR HALL  ·  GRID %s / %s" % [g.call("02A"), g.call("02B")], "Close breaker A on the south wall and breaker B on the east gallery.", st.call(f.power >= 2, infil, "%d/2 CLOSED" % f.power)],
		["03", "03", "UPLOAD THE OVERRIDE", "RELAY CONTROL  ·  GRID %s" % g.call("03"), "Needs 01 and 02. Connect at the console and keep it clear for the 40-second upload.", st.call(f.upload, stage == "upload", "UPLOADING" if Game.state == Game.State.HACK else "ACTIVE")],
	]
	if f.complication:
		rows[2][5] = ["REJECTED", RED] if mode == "review" else rows[2][5]
		rows.append(["CORE", "!", "DESTROY RELAY NINE", "RELAY NINE CORE  ·  GRID %s  ·  FIELD UPDATE" % g.call("CORE"), "The override was rejected. Destroy the three capacitor stacks around the relay array.", st.call(f.core, stage == "core", "%d/3 STACKS" % f.caps.count(true))])
	rows.append(["04", "04", "EXTRACT", "FREIGHT LIFT 2  ·  LOADING DOCK  ·  GRID %s" % g.call("04"), "Call the lift and hold the dock until it arrives.", st.call(Game.state == Game.State.COMPLETE, stage in ["extract", "lift", "board"])])
	for r in rows:
		var row := _row(r[0], r[1], r[2], r[3], r[4], false, r[5][0], r[5][1])
		_rows_box.add_child(row)
		_rows[r[0]] = row


# ------------------------------------------------------------------ progression strip
func _draw_progression() -> void:
	var c := _prog
	if main == null:
		return
	var f: Dictionary = main.mission.flags
	var review := mode == "review"
	var nodes := [["INS", "INSERTION", "LOADING DOCK"], ["01", "LOCKDOWN", "SECURITY OFFICE"], ["02", "MAIN POWER", "SWITCHGEAR HALL"],
		["03", "OVERRIDE", "40 S UPLOAD"]]
	if review and f.complication:
		nodes.append(["CORE", "RELAY NINE", "CAPACITOR STACKS"])
	nodes.append(["04", "EXTRACT", "FREIGHT LIFT 2"])
	var done := {"INS": true, "01": f.lockdown, "02": f.power >= 2, "03": f.upload, "CORE": f.core, "04": Game.state == Game.State.COMPLETE}
	if not review:
		done = {}
	c.draw_string(f_mono, Vector2(0, 9), "MISSION PROGRESSION", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, MUTED)
	var y := 28.0
	var x0 := 6.0
	var step := (c.size.x - 150.0 - x0) / float(nodes.size() - 1)
	var pts := []
	for k in nodes.size():
		pts.append(Vector2(x0 + k * step, y))
	var t := Time.get_ticks_msec() / 1000.0
	for k in nodes.size() - 1:
		var a: Vector2 = pts[k] + Vector2(10, 0)
		var b: Vector2 = pts[k + 1] - Vector2(10, 0)
		if done.get(nodes[k][0], false) and done.get(nodes[k + 1][0], false) or (review and done.get(nodes[k][0], false) and _is_current(nodes[k + 1][0])):
			c.draw_line(a, b, Color(AMBER, 0.7), 1.5)
		else:
			var x := a.x
			while x < b.x:
				c.draw_line(Vector2(x, y), Vector2(minf(x + 6.0, b.x), y), Color(MUTED, 0.55), 1.0)
				x += 10.0
	# 01 and 02 may be done in either order.
	var i1 := 1
	var i2 := 2
	var bl: Vector2 = pts[i1] + Vector2(-4, -13)
	var brr: Vector2 = pts[i2] + Vector2(4, -13)
	c.draw_line(bl, brr, Color(MUTED, 0.7), 1.0)
	c.draw_line(bl, bl + Vector2(0, 4), Color(MUTED, 0.7), 1.0)
	c.draw_line(brr, brr + Vector2(0, 4), Color(MUTED, 0.7), 1.0)
	var eo := "EITHER ORDER"
	var ew := f_mono.get_string_size(eo, HORIZONTAL_ALIGNMENT_LEFT, -1, 9).x
	var mid := (bl.x + brr.x) * 0.5
	c.draw_rect(Rect2(mid - ew * 0.5 - 6, bl.y - 7, ew + 12, 12), Color(PANEL_BG, 1.0))
	c.draw_string(f_mono, Vector2(mid - ew * 0.5, bl.y + 3), eo, HORIZONTAL_ALIGNMENT_LEFT, -1, 9, MUTED)
	for k in nodes.size():
		var n: Array = nodes[k]
		var p: Vector2 = pts[k]
		var d: bool = done.get(n[0], false)
		var current: bool = (not review and n[0] == "INS") or (review and not d and _is_current(n[0]))
		var col := CYAN if n[0] == "INS" else (Color(CYAN, 0.85) if d else (AMBER if (current or not review) else MUTED))
		var s := 6.5
		var dia := PackedVector2Array([p + Vector2(0, -s), p + Vector2(s, 0), p + Vector2(0, s), p + Vector2(-s, 0)])
		if d or n[0] == "INS":
			c.draw_colored_polygon(dia, col)
		else:
			c.draw_colored_polygon(dia, Color(0.02, 0.025, 0.03, 1.0))
			c.draw_polyline(dia + PackedVector2Array([dia[0]]), col, 1.5)
		if current:
			var ph := fmod(t * 0.8, 1.0)
			c.draw_arc(p, 9.0 + ph * 9.0, 0, TAU, 24, Color(col, 0.55 * (1.0 - ph)), 1.2)
		var title: String = (n[0] + "  " if n[0].is_valid_int() else "") + n[1]
		c.draw_string(f_label, p + Vector2(-6, 24), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(MUTED, 1.0) if d else INK)
		c.draw_string(f_mono, p + Vector2(-6, 37), n[2] + ("  ·  DONE" if d and review else ""), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, MUTED)


func _is_current(id: String) -> bool:
	var st: String = main.mission.stage
	match id:
		"01", "02": return st == "infiltrate"
		"03": return st == "upload"
		"CORE": return st == "core"
		"04": return st in ["extract", "lift", "board"]
	return false


# ------------------------------------------------------------------ present / dismiss
func present(p_mode: String, p_main: Node) -> void:
	main = p_main
	mode = p_mode
	busy = false
	intel = BriefingIntel.gather(main)
	_map.review = mode == "review"
	_map.deploying = false
	_map.highlight = ""
	_map.setup(intel, BriefingIntel.plan(main.level))
	_rebuild_rows()
	_refresh_chips()
	var counts: Dictionary = intel.counts
	var act := 0
	var dor := 0
	for r in counts:
		act += counts[r][0]
		dor += counts[r][1]
	_threat_units.text = "%d ACTIVE  ·  %d DORMANT" % [act, dor]
	_bars.queue_redraw()
	_prog.queue_redraw()
	_side_buttons.visible = mode == "deploy"
	_deploy.visible = mode == "deploy"
	_deploy.disabled = false
	_deploy.text = "DEPLOY"
	_charge.size = Vector2(0, 0)
	_return.visible = mode == "review"
	_root.visible = true
	_fade.color.a = 0.0
	_card.visible = false
	visible = true
	if _clock0 < 0.0:
		_clock0 = Time.get_ticks_msec() / 1000.0
	_wire_focus()
	_map_note.text = "LIVE POSITION  ·  GRID 10 M" if mode == "review" else "GRID 10 M  ·  NORTH UP"
	_user_t = -100.0
	_cycle_t = 2.2
	_cycle_i = 0
	_set_hud(false)
	_reveal(not _seen and mode == "deploy")
	_seen = true
	(_deploy if mode == "deploy" else _return).grab_focus.call_deferred()


## Up/Down walk the tasking and secondary rows, then the DEPLOY (or RETURN) button.
func _wire_focus() -> void:
	var order: Array[Control] = []
	for r in _rows.values():
		order.append(r)
	order.append_array(_sec_rows)
	var last: Control = _deploy if mode == "deploy" else _return
	for i in order.size():
		var c := order[i]
		c.focus_neighbor_top = c.get_path_to(order[i - 1]) if i > 0 else NodePath()
		c.focus_neighbor_bottom = c.get_path_to(order[i + 1] if i < order.size() - 1 else last)
		c.focus_neighbor_right = c.get_path_to(last)
		c.focus_neighbor_left = c.get_path_to(c)
	last.focus_neighbor_top = last.get_path_to(order[order.size() - 1])
	var ghosts := _side_buttons.get_children()
	if mode == "deploy":
		last.focus_neighbor_left = last.get_path_to(ghosts[ghosts.size() - 1])
		for i in ghosts.size():
			var g: Control = ghosts[i]
			g.focus_neighbor_top = g.get_path_to(order[order.size() - 1])
			g.focus_neighbor_right = g.get_path_to(ghosts[i + 1] if i < ghosts.size() - 1 else last)
			g.focus_neighbor_left = g.get_path_to(ghosts[i - 1] if i > 0 else g)


func dismiss() -> void:
	if busy:
		return
	if visible:
		_set_hud(true)
	visible = false


func _set_hud(on: bool) -> void:
	if main and main.hud:
		main.hud.visible = on


func _refresh_chips() -> void:
	for c in _chips.get_children():
		c.queue_free()
	var f: Dictionary = main.mission.flags
	var review := mode == "review"
	_chips.add_child(_chip("RELAY NINE", "SYNC LOST  ·  41 H" if not f.core else "DESTROYED", RED if not f.core else CYAN))
	var p: int = f.power
	_chips.add_child(_chip("MAIN BREAKERS", "OPEN" if p == 0 else ("%d/2 CLOSED" % p if p < 2 else "CLOSED"), RED if p == 0 else (AMBER if p < 2 else CYAN)))
	_chips.add_child(_chip("CONTROL WING", "RELEASED" if f.lockdown else "SEALED", CYAN if f.lockdown else RED))
	_chips.add_child(_chip("COMMS", "DARK" if review else "DARK ON INSERTION", MUTED))


func _reveal(full: bool) -> void:
	if _tween:
		_tween.kill()
	var parts := [_top, _left, _center, _right, _bottom, _keys]
	_tween = create_tween().set_parallel(true)
	if not full:
		for p in parts:
			p.modulate.a = 0.0
			_tween.tween_property(p, "modulate:a", 1.0, 0.22)
		_map.reveal = 1.0
		_map.markers_alpha = 1.0
		_sitrep.visible_ratio = 1.0
		return
	Sfx.play("ui_objective", -14.0, 0.0)
	var delays := [0.0, 0.15, 0.25, 0.35, 0.55, 0.7]
	for i in parts.size():
		parts[i].modulate.a = 0.0
		_tween.tween_property(parts[i], "modulate:a", 1.0, 0.4).set_delay(delays[i]).set_trans(Tween.TRANS_SINE)
	_map.reveal = 0.0
	_map.markers_alpha = 0.0
	_sitrep.visible_ratio = 0.0
	_tween.tween_property(_map, "reveal", 1.0, 1.25).set_delay(0.45).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_tween.tween_property(_map, "markers_alpha", 1.0, 0.45).set_delay(1.55)
	_tween.tween_property(_sitrep, "visible_ratio", 1.0, 1.3).set_delay(0.45)
	_tween.tween_callback(func(): Sfx.play("ui_hack_tick", -16.0, 0.0)).set_delay(1.6)


func _process(delta: float) -> void:
	if not visible:
		return
	# Idle spotlight: walk the map through the tasks until the player points at something.
	var idle := Time.get_ticks_msec() / 1000.0 - _user_t > 4.0 and not (get_viewport().gui_get_focus_owner() is ObjRow)
	if mode == "deploy" and not busy and _map.reveal >= 1.0 and idle:
		_cycle_t -= delta
		if _cycle_t <= 0.0:
			_cycle_t = 2.8
			_map.highlight = ["01", "02", "03", "04"][_cycle_i % 4]
			_cycle_i += 1
	var t := Time.get_ticks_msec() / 1000.0
	if _fx.material:
		(_fx.material as ShaderMaterial).set_shader_parameter("time_s", t)
	var secs := int(2 * 3600 + 40 * 60 + (t - _clock0))
	_clock.text = "%02d:%02d:%02d" % [(secs / 3600) % 24, (secs / 60) % 60, secs % 60]
	if _prog.is_visible_in_tree():
		_prog.queue_redraw()


# ------------------------------------------------------------------ interaction
func _on_row_hover(id: String) -> void:
	_map.highlight = id
	if id != "":
		_user_t = Time.get_ticks_msec() / 1000.0
		_tick()


func _on_map_hover(id: String) -> void:
	if id != "":
		_user_t = Time.get_ticks_msec() / 1000.0
	var group := id
	if id.begins_with("02"):
		group = "02"
	elif id.begins_with("AM"):
		group = "AMMO"
	for r in _rows.values():
		r.add_theme_stylebox_override("panel", r.active if r.id == group else r.normal)


func _tick() -> void:
	if visible and not busy:
		Sfx.play("ui_hack_tick", -22.0, 0.05)


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if busy:
		if _skip_ok and (event is InputEventKey or event is InputEventMouseButton) and event.is_pressed():
			_skip_card()
			get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			if mode == "deploy":
				start_deploy()
			else:
				request.emit("return")
			get_viewport().set_input_as_handled()


## DEPLOY: authorise, cut to black, title card, then the game fades in.
func start_deploy() -> void:
	if busy or mode != "deploy" or not visible:
		return
	busy = true
	_deploy.disabled = true
	_deploy.text = "AUTHORISING"
	_map.deploying = true
	_map.highlight = "INS"
	Sfx.play("ui_hack_done", -9.0, 0.0)
	if _tween:
		_tween.kill()
	_charge.position = Vector2.ZERO
	_charge.size = Vector2(0, _deploy.size.y)
	var secs := int(2 * 3600 + 40 * 60 + (Time.get_ticks_msec() / 1000.0 - _clock0))
	_card_line.text = "%02d:%02d LOCAL  ·  COMMS DARK" % [(secs / 3600) % 24, (secs / 60) % 60]
	_tween = create_tween()
	_tween.tween_property(_charge, "size:x", _deploy.size.x, 0.7).set_trans(Tween.TRANS_SINE)
	_tween.tween_callback(func(): _deploy.text = "DEPLOYING")
	_tween.tween_property(_fade, "color:a", 1.0, 0.42).set_trans(Tween.TRANS_SINE)
	_tween.tween_callback(func():
		_root.visible = false
		_card.visible = true
		_skip_ok = true)
	_tween.tween_property(_card, "modulate:a", 1.0, 0.4)
	_tween.tween_interval(1.0)
	_tween.tween_property(_card, "modulate:a", 0.0, 0.35)
	_tween.tween_callback(_go)
	_tween.tween_property(_fade, "color:a", 0.0, 0.9).set_trans(Tween.TRANS_SINE)
	_tween.tween_callback(_finish)


func _skip_card() -> void:
	_skip_ok = false
	if _tween:
		_tween.kill()
	_card.modulate.a = 0.0
	_go()
	_tween = create_tween()
	_tween.tween_property(_fade, "color:a", 0.0, 0.45)
	_tween.tween_callback(_finish)


func _go() -> void:
	_skip_ok = false
	_card.visible = false
	_set_hud(true)
	deploy_confirmed.emit()


func _finish() -> void:
	busy = false
	visible = false
	_fade.color.a = 0.0


func _shader(code: String) -> ShaderMaterial:
	var s := Shader.new()
	s.code = code
	var m := ShaderMaterial.new()
	m.shader = s
	return m


const BACKDROP_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
void fragment() {
	vec3 c = textureLod(screen_tex, SCREEN_UV, 4.5).rgb;
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(vec3(l), c, 0.3) * 0.32;
	c = mix(c, vec3(0.010, 0.015, 0.019), 0.5);
	vec2 d = UV - 0.5;
	float v = smoothstep(0.95, 0.2, length(d * vec2(1.0, 1.3)));
	c *= mix(0.45, 1.0, v);
	COLOR = vec4(c, 0.985);
}
"""

const FX_SHADER := """
shader_type canvas_item;
uniform float time_s = 0.0;
float h(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	vec2 px = floor(FRAGCOORD.xy);
	float n = h(px + floor(time_s * 24.0) * vec2(17.0, 31.0));
	bool dark = mod(px.y, 3.0) < 1.0;
	COLOR = dark ? vec4(0.0, 0.0, 0.0, 0.07) : vec4(vec3(n), 0.022);
}
"""
