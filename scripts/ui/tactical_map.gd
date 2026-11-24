class_name TacticalMap
extends Control
## Plan view of Substation 9-B for the briefing. North (-Z) is up.
## A static layer (grid, rooms, galleries, machinery, walls, labels) is drawn
## once per resize and revealed by a scan sweep; an overlay redraws every
## frame for doors, routes, threat estimates, markers, highlights and the
## live operator position.

signal marker_hovered(id: String)

const C_BG := Color(0.018, 0.024, 0.028, 0.92)
const C_GRID := Color(0.42, 0.55, 0.6, 0.035)
const C_GRID_MAJOR := Color(0.42, 0.55, 0.6, 0.085)
const C_ROOM := Color(0.075, 0.095, 0.105, 0.85)
const C_ROOM_HI := Color(0.12, 0.15, 0.16, 0.95)
const C_WALL := Color(0.66, 0.74, 0.76)
const C_SOLID := Color(0.2, 0.235, 0.25)
const C_SOLID_EDGE := Color(0.32, 0.37, 0.39)
const C_LOW := Color(0.135, 0.155, 0.165)
const C_LABEL := Color(0.52, 0.6, 0.62)
const C_AMBER := Color(0.93, 0.7, 0.3)
const C_RED := Color(0.88, 0.3, 0.24)
const C_CYAN := Color(0.62, 0.86, 0.92)
const C_DIM := Color(0.36, 0.4, 0.41)

var intel := {}
var plan := {}
var font_label: Font     # tracked caps
var font_mono: Font
var font_bold: Font
var highlight := ""      # marker id (or "01"/"02" group) under focus
var reveal := 1.0        # 0..1 sweep reveal of the plan
var markers_alpha := 1.0
var review := false
var deploying := false   # insertion marker charges while the operator deploys

var _clip: Control
var _static: Control
var _overlay: Control
var _s := 1.0            # pixels per metre
var _o := Vector2.ZERO   # pixel position of the world bounds origin
var _t := 0.0
var _hover := ""


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	_clip = Control.new()
	_clip.clip_contents = true
	_clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_clip)
	_static = Control.new()
	_static.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_static.draw.connect(_draw_static)
	_clip.add_child(_static)
	_overlay = Control.new()
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.draw.connect(_draw_overlay)
	add_child(_overlay)
	resized.connect(_layout)


func setup(p_intel: Dictionary, p_plan: Dictionary) -> void:
	intel = p_intel
	plan = p_plan
	_layout()


func _layout() -> void:
	var span := Vector2(BriefingIntel.COLS, BriefingIntel.ROWS) * BriefingIntel.CELL
	var pad := Vector2(30, 26)
	var avail := size - pad * 2.0
	_s = minf(avail.x / span.x, avail.y / span.y)
	_o = (size - span * _s) * 0.5
	_static.position = Vector2.ZERO
	_static.size = size
	_clip.size = Vector2(size.x, size.y * reveal)
	_static.queue_redraw()


func w2m(p: Vector2) -> Vector2:
	return _o + (p - BriefingIntel.ORIGIN) * _s


func _process(delta: float) -> void:
	if not is_visible_in_tree():
		return
	_t += delta
	_clip.size = Vector2(size.x, size.y * reveal)
	_overlay.queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var best := ""
		var bd := 16.0
		for m in intel.get("markers", []):
			var d: float = w2m(m.pos).distance_to(event.position)
			if d < bd:
				bd = d
				best = m.id
		if best != _hover:
			_hover = best
			marker_hovered.emit(best)


# ------------------------------------------------------------------ static layer
func _draw_static() -> void:
	var c := _static
	var span := Vector2(BriefingIntel.COLS, BriefingIntel.ROWS) * BriefingIntel.CELL
	var r := Rect2(_o, span * _s)
	c.draw_rect(r, C_BG)
	# Survey grid: 2 m minor, 10 m major, lettered columns and numbered rows.
	for i in int(span.x / 2.0) + 1:
		var x := r.position.x + i * 2.0 * _s
		c.draw_line(Vector2(x, r.position.y), Vector2(x, r.end.y), C_GRID_MAJOR if i % 5 == 0 else C_GRID, 1.0)
	for i in int(span.y / 2.0) + 1:
		var y := r.position.y + i * 2.0 * _s
		c.draw_line(Vector2(r.position.x, y), Vector2(r.end.x, y), C_GRID_MAJOR if i % 5 == 0 else C_GRID, 1.0)
	for i in BriefingIntel.COLS:
		var x := r.position.x + (i + 0.5) * BriefingIntel.CELL * _s
		c.draw_string(font_mono, Vector2(x - 4, r.position.y - 8), "ABCDEFGH"[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, C_DIM)
		c.draw_string(font_mono, Vector2(x - 4, r.end.y + 17), "ABCDEFGH"[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, C_DIM)
	for i in BriefingIntel.ROWS:
		var y := r.position.y + (i + 0.5) * BriefingIntel.CELL * _s + 4
		c.draw_string(font_mono, Vector2(r.position.x - 18, y), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, C_DIM)
		c.draw_string(font_mono, Vector2(r.end.x + 8, y), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, C_DIM)
	_frame_ticks(c, r)
	# Rooms
	for room in intel.get("rooms", []):
		var rr := Rect2(w2m(room.rect.position), room.rect.size * _s)
		c.draw_rect(rr, C_ROOM)
		if room.id == "core":
			_hatch(c, rr, Color(C_RED, 0.1), 9.0)
	for g in plan.get("galleries", []):
		var poly := _map_poly(g)
		var gr := _poly_rect(poly)
		_hatch(c, gr, Color(C_CYAN, 0.09), 6.0)
		c.draw_polyline(_closed(poly), Color(C_CYAN, 0.22), 1.0)
	for p in plan.get("low", []):
		c.draw_colored_polygon(_map_poly(p), C_LOW)
	for p in plan.get("solids", []):
		var mp := _map_poly(p)
		c.draw_colored_polygon(mp, C_SOLID)
		c.draw_polyline(_closed(mp), C_SOLID_EDGE, 1.0)
	# Walls: a faint glow pass under the crisp fill.
	for p in plan.get("walls", []):
		var mp := _map_poly(p)
		c.draw_polyline(_closed(mp), Color(C_WALL, 0.07), 4.0)
	for p in plan.get("walls", []):
		c.draw_colored_polygon(_map_poly(p), C_WALL)
	# Room names
	for room in intel.get("rooms", []):
		_room_label(c, room)
	# North arrow and scale bar
	var na := Vector2(r.end.x - 26, r.position.y + 30)
	c.draw_colored_polygon(PackedVector2Array([na + Vector2(0, -14), na + Vector2(6, 6), na + Vector2(0, 2), na + Vector2(-6, 6)]), Color(C_WALL, 0.8))
	c.draw_string(font_label, na + Vector2(-4, 22), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, C_LABEL)
	var sb := Vector2(r.position.x + 14, r.end.y - 16)
	c.draw_line(sb, sb + Vector2(10.0 * _s, 0), Color(C_WALL, 0.7), 2.0)
	for k in 3:
		c.draw_line(sb + Vector2(k * 5.0 * _s, -4 if k != 1 else -2), sb + Vector2(k * 5.0 * _s, 0), Color(C_WALL, 0.7), 1.0)
	c.draw_string(font_mono, sb + Vector2(10.0 * _s + 8, 4), "10 M", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, C_LABEL)


func _frame_ticks(c: Control, r: Rect2) -> void:
	var col := Color(C_WALL, 0.35)
	for p in [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]:
		var sx := 1.0 if p.x <= r.position.x + 1 else -1.0
		var sy := 1.0 if p.y <= r.position.y + 1 else -1.0
		c.draw_line(p, p + Vector2(18 * sx, 0), col, 1.5)
		c.draw_line(p, p + Vector2(0, 18 * sy), col, 1.5)


func _room_label(c: Control, room: Dictionary) -> void:
	var rr := Rect2(w2m(room.rect.position), room.rect.size * _s)
	var name: String = room.name
	var fs := 12
	var col := C_LABEL
	if room.id == "core":
		col = Color(C_RED, 0.75)
	if room.id == "antechamber":
		return
	var tw := font_label.get_string_size(name, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	if rr.size.y > rr.size.x * 3.0:
		# narrow and long (service corridor): along its length, clear of the tunnel and the 01 marker
		fs = 11
		tw = font_label.get_string_size(name, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		c.draw_set_transform(Vector2(rr.get_center().x + 4, rr.position.y + rr.size.y * 0.25 + tw * 0.5), -PI / 2)
		c.draw_rect(Rect2(-4, -12, tw + 8, 16), Color(C_BG, 0.9))
		c.draw_string(font_label, Vector2.ZERO, name, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
		c.draw_set_transform_matrix(Transform2D.IDENTITY)
		return
	if rr.size.x < tw + 8:
		fs = 10
		tw = font_label.get_string_size(name, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var pos := Vector2(rr.position.x + 7, rr.position.y + 16)
	if room.id in ["passage", "antechamber", "tunnel", "crawl"]:
		pos = Vector2(rr.get_center().x - tw * 0.5, rr.get_center().y + 4)
		if room.id == "passage":
			pos = Vector2(rr.end.x + 6, rr.get_center().y + 4)
	c.draw_rect(Rect2(pos + Vector2(-4, -fs), Vector2(tw + 8, fs + 5)), Color(C_BG, 0.9))
	c.draw_string(font_label, pos, name, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
	if room.id == "core":
		c.draw_string(font_mono, pos + Vector2(0, 15), "SEALED  /  NO ACCESS" if not review else "", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(C_RED, 0.6))


func _hatch(c: Control, r: Rect2, col: Color, step: float) -> void:
	var n := int((r.size.x + r.size.y) / step)
	for i in n:
		var d := i * step
		var a := Vector2(r.position.x + d, r.position.y)
		var b := Vector2(r.position.x + d - r.size.y, r.end.y)
		# clip the 45-degree line to the rectangle
		if a.x > r.end.x:
			a = Vector2(r.end.x, r.position.y + (a.x - r.end.x))
		if b.x < r.position.x:
			b = Vector2(r.position.x, r.end.y - (r.position.x - b.x))
		if a.y < b.y:
			c.draw_line(a, b, col, 1.0)


func _map_poly(p: PackedVector2Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	out.resize(p.size())
	for i in p.size():
		out[i] = w2m(p[i])
	return out


func _poly_rect(p: PackedVector2Array) -> Rect2:
	var r := Rect2(p[0], Vector2.ZERO)
	for v in p:
		r = r.expand(v)
	return r


func _closed(p: PackedVector2Array) -> PackedVector2Array:
	var out := p.duplicate()
	out.append(p[0])
	return out


# ------------------------------------------------------------------ overlay
func _draw_overlay() -> void:
	var c := _overlay
	if intel.is_empty():
		return
	var span := Vector2(BriefingIntel.COLS, BriefingIntel.ROWS) * BriefingIntel.CELL
	var r := Rect2(_o, span * _s)
	# Scan sweep: the reveal edge, then a slow idle pass.
	if reveal < 1.0:
		var y := r.position.y + r.size.y * reveal
		c.draw_rect(Rect2(r.position.x, y - 26, r.size.x, 26), Color(C_CYAN, 0.035))
		c.draw_line(Vector2(r.position.x, y), Vector2(r.end.x, y), Color(C_CYAN, 0.55), 1.5)
	else:
		var k := fmod(_t, 7.0) / 7.0
		var y := r.position.y + r.size.y * k
		c.draw_rect(Rect2(r.position.x, y - 40, r.size.x, 40), Color(C_CYAN, 0.018))
		c.draw_line(Vector2(r.position.x, y), Vector2(r.end.x, y), Color(C_CYAN, 0.07), 1.0)
	var a := markers_alpha
	if a <= 0.0:
		return
	# Doors
	for d in intel.doors:
		var p0 := w2m(d.a)
		var p1 := w2m(d.b)
		if d.get("blast", false):
			if d.sealed:
				c.draw_line(p0, p1, Color(C_RED, 0.9 * a), 4.0)
				var bw := font_mono.get_string_size("BLAST DOOR", HORIZONTAL_ALIGNMENT_LEFT, -1, 10).x
				c.draw_string(font_mono, p0 + Vector2(-bw - 8, -6), "BLAST DOOR", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(C_RED, 0.85 * a))
			continue
		if d.sealed:
			c.draw_line(p0, p1, Color(C_RED, 0.95 * a), 3.0)
			var m := (p0 + p1) * 0.5
			c.draw_string(font_mono, m + Vector2(5, -5), d.id, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(C_RED, 0.9 * a))
		else:
			c.draw_line(p0, p1, Color(0.78, 0.72, 0.6, 0.75 * a), 2.0)
	# Approach routes (marching dashes)
	for rt in intel.routes:
		var primary: bool = rt.get("primary", false)
		var col := Color(C_AMBER, 0.42 * a) if primary else Color(C_CYAN, 0.5 * a)
		_dashed(c, rt.pts, col, 1.5, 6.0 if primary else 3.0, 5.0, _t * 14.0)
		if rt.label != "":
			var at := w2m(_point_at(rt.pts, 0.5 if rt.id != "A" else 0.3)) + Vector2(9, -9)
			var bc := Color(col, minf(1.0, col.a + 0.4))
			var br := Rect2(at - Vector2(7, 7), Vector2(15, 15))
			c.draw_rect(br, Color(0.02, 0.025, 0.03, 0.9 * a))
			c.draw_rect(br, bc, false, 1.0)
			c.draw_string(font_mono, at + Vector2(-3.5, 4.5), rt.id.substr(0, 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, bc)
	# Threat estimate (pre-deployment; dimmed once the operation is under way)
	var ta := a * (0.45 if review else 1.0)
	for th in intel.threats:
		var p := w2m(th.pos)
		var dia := _diamond(p, 3.6)
		if th.dormant:
			c.draw_polyline(_closed(dia), Color(C_RED, 0.75 * ta), 1.2)
		else:
			c.draw_circle(p, 7.0, Color(C_RED, 0.08 * ta))
			c.draw_colored_polygon(dia, Color(C_RED, 0.85 * ta))
	# Markers
	var hi_ids := _hi_ids()
	for m in intel.markers:
		_marker(c, m, m.id in hi_ids, a)
	# Live operator position (review)
	if intel.get("player", Vector2.INF) != Vector2.INF:
		var p := w2m(intel.player)
		var f: Vector2 = intel.player_dir
		var sd := Vector2(-f.y, f.x)
		c.draw_circle(p, 9.0 + 2.0 * sin(_t * 4.0), Color(C_CYAN, 0.12))
		c.draw_colored_polygon(PackedVector2Array([p + f * 9.0, p - f * 5.0 + sd * 5.5, p - f * 2.0, p - f * 5.0 - sd * 5.5]), C_CYAN)
		c.draw_string(font_mono, p + Vector2(10, -8), "YOU", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, C_CYAN)


func _hi_ids() -> Array:
	var h := _hover if _hover != "" else highlight
	match h:
		"01": return ["01"]
		"02": return ["02A", "02B"]
		"03": return ["03"]
		"04": return ["04"]
		"AMMO": return ["AM1", "AM2", "AM3"]
		"": return []
	return [h]


func _marker(c: Control, m: Dictionary, hi: bool, a: float) -> void:
	var p := w2m(m.pos)
	var done: bool = m.get("done", false)
	var kind: String = m.kind
	var phase := fmod(_t * 0.42 + p.x * 0.003, 1.0)
	match kind:
		"insertion":
			var k := 1.0 + (0.35 * sin(_t * 14.0) if deploying else 0.0)
			c.draw_arc(p, 11.0 * k, 0, TAU, 32, Color(C_CYAN, 0.55 * a), 1.2)
			c.draw_colored_polygon(PackedVector2Array([p + Vector2(0, -7), p + Vector2(6, 5), p + Vector2(0, 2), p + Vector2(-6, 5)]), Color(C_CYAN, a))
			if not review or hi:
				_tag(c, p + Vector2(16, -2), m.label, m.sub, C_CYAN, a, hi)
		"objective", "extract":
			var left: bool = m.get("tag_left", false)
			var col := C_AMBER if not done else Color(C_DIM, 1.0)
			if not done:
				var ring := 8.0 + 22.0 * phase
				c.draw_arc(p, ring, 0, TAU, 40, Color(col, (1.0 - phase) * 0.55 * a), 1.2)
			var sz := 9.5 if not hi else 12.0
			var shape := _diamond(p, sz) if kind == "objective" else PackedVector2Array([p + Vector2(-sz, -sz) * 0.8, p + Vector2(sz, -sz) * 0.8, p + Vector2(sz, sz) * 0.8, p + Vector2(-sz, sz) * 0.8])
			c.draw_colored_polygon(shape, Color(0.03, 0.035, 0.04, 0.9 * a))
			c.draw_polyline(_closed(shape), Color(col, a), 2.0 if hi else 1.5)
			var num: String = m.id.substr(0, 2) if m.id != "CORE" else "!"
			c.draw_string(font_bold, p + Vector2(-7.0 if num.length() > 1 else -3, 4.0), num, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(col, a))
			if done:
				c.draw_line(p + Vector2(-12, 12), p + Vector2(12, -12), Color(C_DIM, a), 1.5)
			if hi or (kind == "extract" and not review):
				_tag(c, p + Vector2(16, -2), m.label + ("  [DONE]" if done else ""), m.sub, col, a, hi, left)
		"ammo":
			c.draw_arc(p, 5.0, 0, TAU, 20, Color(C_AMBER, (0.95 if hi else 0.6) * a), 1.4)
			c.draw_circle(p, 1.8, Color(C_AMBER, 0.8 * a))
			if hi:
				_tag(c, p + Vector2(10, -2), m.label, m.sub, C_AMBER, a, true)
		"aux":
			c.draw_arc(p, 5.5, 0, TAU, 20, Color(C_CYAN, (0.95 if hi else 0.6) * a), 1.4)
			c.draw_line(p + Vector2(-3, 0), p + Vector2(3, 0), Color(C_CYAN, 0.8 * a), 1.2)
			c.draw_line(p + Vector2(0, -3), p + Vector2(0, 3), Color(C_CYAN, 0.8 * a), 1.2)
			if hi:
				_tag(c, p + Vector2(10, -2), m.label, m.sub, C_CYAN, a, true)
	if review and intel.get("current", Vector2.INF) != Vector2.INF and m.kind in ["objective", "extract"] and not done:
		if (m.pos as Vector2).distance_to(intel.current) < 1.5:
			c.draw_arc(p, 15.0, -_t * 2.0, -_t * 2.0 + PI * 1.4, 24, Color(C_AMBER, 0.9 * a), 2.0)


func _tag(c: Control, at: Vector2, title: String, sub: String, col: Color, a: float, hi: bool, left := false) -> void:
	var fs := 12 if hi else 11
	var tw := font_label.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var sw := font_mono.get_string_size(sub, HORIZONTAL_ALIGNMENT_LEFT, -1, 10).x
	var w := maxf(tw, sw) + 14
	var flip := left or at.x + w > size.x - 8
	var o := at if not flip else at - Vector2(w + 32, 0)
	var box := Rect2(o + Vector2(0, -13), Vector2(w, 32))
	c.draw_rect(box, Color(0.02, 0.025, 0.03, (0.88 if hi else 0.7) * a))
	c.draw_rect(Rect2(box.position, Vector2(2, box.size.y)), Color(col, a))
	if hi:
		c.draw_rect(box, Color(col, 0.55 * a), false, 1.0)
	c.draw_string(font_label, o + Vector2(8, 1), title, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(col, a) if hi else Color(0.86, 0.87, 0.84, a))
	c.draw_string(font_mono, o + Vector2(8, 14), sub, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(C_LABEL, a))


func _point_at(pts: PackedVector2Array, frac: float) -> Vector2:
	var total := 0.0
	for i in pts.size() - 1:
		total += pts[i].distance_to(pts[i + 1])
	var want := total * frac
	for i in pts.size() - 1:
		var seg := pts[i].distance_to(pts[i + 1])
		if want <= seg and seg > 0.0:
			return pts[i].lerp(pts[i + 1], want / seg)
		want -= seg
	return pts[pts.size() - 1]


func _diamond(p: Vector2, s: float) -> PackedVector2Array:
	return PackedVector2Array([p + Vector2(0, -s), p + Vector2(s, 0), p + Vector2(0, s), p + Vector2(-s, 0)])


func _dashed(c: Control, pts: PackedVector2Array, col: Color, width: float, dash: float, gap: float, phase: float) -> void:
	var period := dash + gap
	var acc := -fmod(phase, period)
	for i in pts.size() - 1:
		var p0 := w2m(pts[i])
		var p1 := w2m(pts[i + 1])
		var seg := p0.distance_to(p1)
		if seg < 0.01:
			continue
		var dir := (p1 - p0) / seg
		var s := acc
		while s < seg:
			var s0 := maxf(s, 0.0)
			var s1 := minf(s + dash, seg)
			if s1 > s0:
				c.draw_line(p0 + dir * s0, p0 + dir * s1, col, width)
			s += period
		acc = s - seg
