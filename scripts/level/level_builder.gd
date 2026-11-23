class_name LevelBuilder
extends Node3D
## Builds "Substation 9-B" — the single indoor mission of the vertical slice.
## Geometry is authored in code as boxes with triplanar PBR materials plus
## Blender-built props. Static geometry sits under a NavigationRegion3D that is
## baked at load; doors live outside it so robots path through doorways.
##
## Layout (X east, -Z north, metres):
##   DOCK      x[0,16]  z[0,14]    start + extraction lift
##   CORRIDOR  x[6,9]   z[-30,0]   long service corridor
##   OFFICE    x[-6,6]  z[-13,-3]  security office (door D2)
##   PASSAGE   x[12,14.5] z[-2,0] crouch-only shutter into the hall
##   HALL      x[9,32]  z[-26,-2]  turbine hall, 9 m high
##   SERVERS   x[9,21]  z[-38,-26] server room (D4 from hall, D7 from corridor)
##   CONTROL   x[21,33] z[-40,-26] relay control (D5 from servers, D6 locked)

const T := 0.3   # wall thickness
const DOOR_W := 1.42  # industrial leaf in a 1.5 m opening (robots need the width to path)

var nav: NavigationRegion3D
var dyn: Node3D
var props_root: Node3D
var doors := {}
var cover_props: Array = []   # AABBs for cover generation
var spawns: Array = []        # {pos, yaw, patrol, group}
var console: Node3D
var player_start := Transform3D(Basis(), Vector3(8, 0.05, 11))
var extraction_pos := Vector3(3.0, 0, 11.8)
var extraction_area: Area3D
var beacon: OmniLight3D
var room_lights := {}


func build() -> void:
	props_root = (load("res://assets/models/props.glb") as PackedScene).instantiate()
	nav = NavigationRegion3D.new()
	nav.name = "NavRegion"
	add_child(nav)
	dyn = Node3D.new()
	dyn.name = "Dynamic"
	add_child(dyn)
	_rooms()
	_shell()
	_dock()
	_corridor()
	_office()
	_passage()
	_hall()
	_servers()
	_control()
	Dressing.new(self).dress()
	_lights()
	_signage()
	_audio_zones()
	_enemy_spawns()
	# Source scenes were only templates for duplication; free them now so
	# nothing out-of-tree survives until engine teardown.
	if props_root:
		props_root.free()
		props_root = null
	if _kit_root:
		_kit_root.free()
		_kit_root = null


func bake_nav() -> void:
	var nm := NavigationMesh.new()
	nm.agent_radius = 0.4
	nm.agent_height = 2.0
	nm.agent_max_climb = 0.2
	nm.agent_max_slope = 40.0
	nm.cell_size = 0.2
	nm.cell_height = 0.2
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = 1
	nm.region_min_size = 4.0
	NavigationServer3D.map_set_cell_size(get_world_3d().navigation_map, 0.2)
	NavigationServer3D.map_set_cell_height(get_world_3d().navigation_map, 0.2)
	nav.navigation_mesh = nm
	nav.bake_navigation_mesh(false)


# ------------------------------------------------------------------ helpers
func box(a: Vector3, b: Vector3, mat: Material, surface := "concrete", collide := true, parent: Node3D = null, shadows := true) -> MeshInstance3D:
	var lo := Vector3(minf(a.x, b.x), minf(a.y, b.y), minf(a.z, b.z))
	var hi := Vector3(maxf(a.x, b.x), maxf(a.y, b.y), maxf(a.z, b.z))
	var size := hi - lo
	var center := (lo + hi) / 2.0
	var p := parent if parent else nav
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	mi.position = center
	if not shadows:
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.add_child(mi)
	if collide:
		var sb := StaticBody3D.new()
		sb.collision_layer = 1
		sb.collision_mask = 0
		sb.set_meta("surface", surface)
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = size
		cs.shape = bs
		sb.add_child(cs)
		sb.position = center
		p.add_child(sb)
	return mi


func prop(name: String, pos: Vector3, yaw_deg := 0.0, cover := false, surface := "metal", collide := true, parent: Node3D = null) -> Node3D:
	var src: Node3D = props_root.get_node_or_null(name)
	if src == null:
		push_warning("missing prop " + name)
		return null
	var inst: Node3D = src.duplicate()
	var p := parent if parent else nav
	p.add_child(inst)
	# Children are stored relative to the prop's empty, so only place the root.
	inst.rotation.y = deg_to_rad(yaw_deg)
	inst.position = pos
	MatLib.remap_scene(inst)
	var aabb := _world_aabb(inst)
	if collide and aabb.size.length() > 0.01:
		var sb := StaticBody3D.new()
		sb.collision_layer = 1
		sb.collision_mask = 0
		sb.set_meta("surface", surface)
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = aabb.size
		cs.shape = bs
		sb.add_child(cs)
		p.add_child(sb)
		sb.global_position = aabb.get_center()
	if cover:
		cover_props.append(aabb)
	return inst


func _world_aabb(n: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for mi in n.find_children("*", "MeshInstance3D", true, false):
		var a: AABB = mi.global_transform * mi.get_aabb()
		if first:
			out = a
			first = false
		else:
			out = out.merge(a)
	return out


## Wall along X at fixed z, from x0 to x1, with door/arch openings [[a, b, top]].
func wall_x(z: float, x0: float, x1: float, h: float, openings := [], upper: Material = null, lower: Material = null) -> void:
	var segs := _split(x0, x1, openings)
	for s in segs:
		_wall_piece(Vector3(s[0], 0, z - T / 2), Vector3(s[1], h, z + T / 2), true, upper, lower)
	for o in openings:
		_wall_piece(Vector3(o[0], o[2], z - T / 2), Vector3(o[1], h, z + T / 2), true, upper, null)
		_frame(Vector3(o[0], 0, z), Vector3(o[1], o[2], z), true)


func wall_z(x: float, z0: float, z1: float, h: float, openings := [], upper: Material = null, lower: Material = null) -> void:
	var segs := _split(z0, z1, openings)
	for s in segs:
		_wall_piece(Vector3(x - T / 2, 0, s[0]), Vector3(x + T / 2, h, s[1]), false, upper, lower)
	for o in openings:
		_wall_piece(Vector3(x - T / 2, o[2], o[0]), Vector3(x + T / 2, h, o[1]), false, upper, null)
		_frame(Vector3(x, 0, o[0]), Vector3(x, o[2], o[1]), false)


func _split(a: float, b: float, openings: Array) -> Array:
	var segs := []
	var cur := a
	var ops := openings.duplicate()
	ops.sort_custom(func(p, q): return p[0] < q[0])
	for o in ops:
		if o[0] > cur:
			segs.append([cur, o[0]])
		cur = maxf(cur, o[1])
	if cur < b:
		segs.append([cur, b])
	return segs


func _wall_piece(a: Vector3, b: Vector3, along_x: bool, upper: Material, lower: Material) -> void:
	box(a, b, upper if upper else MatLib.wall_concrete())
	if b.y - a.y > 1.4 and a.y < 0.1:
		# Industrial wainscot band + cap rail, both faces.
		var pad := 0.025
		var lo := Vector3(a.x - (0 if along_x else pad), 0, a.z - (pad if along_x else 0))
		var hi := Vector3(b.x + (0 if along_x else pad), 1.15, b.z + (pad if along_x else 0))
		box(lo, hi, lower if lower else MatLib.wall_lower(), "metal", false)
		box(Vector3(lo.x - (0 if along_x else 0.02), 1.15, lo.z - (0.02 if along_x else 0)), Vector3(hi.x + (0 if along_x else 0.02), 1.21, hi.z + (0.02 if along_x else 0)), MatLib.flat(Color(0.08, 0.085, 0.09), 0.8, 0.4), "metal", false)


func _frame(a: Vector3, b: Vector3, along_x: bool) -> void:
	# Steel door/arch frame: two jambs and a header. Door openings (2.2 m)
	# get the M2 kit frame from Dressing instead; only floor stripes here.
	var m := MatLib.flat(Color(0.11, 0.115, 0.12), 0.85, 0.42)
	var d := T / 2 + 0.04
	if absf(b.y - 2.2) < 0.01 and ResourceLoader.exists("res://assets/models/env_kit.glb"):
		if along_x:
			_floor_stripe(Vector3(a.x, 0.005, a.z - 0.9), Vector3(b.x, 0.012, a.z - 0.75))
			_floor_stripe(Vector3(a.x, 0.005, a.z + 0.75), Vector3(b.x, 0.012, a.z + 0.9))
		else:
			_floor_stripe(Vector3(a.x - 0.9, 0.005, a.z), Vector3(a.x - 0.75, 0.012, b.z))
			_floor_stripe(Vector3(a.x + 0.75, 0.005, a.z), Vector3(a.x + 0.9, 0.012, b.z))
		return
	if along_x:
		box(Vector3(a.x - 0.08, 0, a.z - d), Vector3(a.x, b.y + 0.08, a.z + d), m, "metal")
		box(Vector3(b.x, 0, a.z - d), Vector3(b.x + 0.08, b.y + 0.08, a.z + d), m, "metal")
		box(Vector3(a.x - 0.08, b.y, a.z - d), Vector3(b.x + 0.08, b.y + 0.1, a.z + d), m, "metal", false)
		_floor_stripe(Vector3(a.x, 0.005, a.z - 0.9), Vector3(b.x, 0.012, a.z - 0.75))
		_floor_stripe(Vector3(a.x, 0.005, a.z + 0.75), Vector3(b.x, 0.012, a.z + 0.9))
	else:
		box(Vector3(a.x - d, 0, a.z - 0.08), Vector3(a.x + d, b.y + 0.08, a.z), m, "metal")
		box(Vector3(a.x - d, 0, b.z), Vector3(a.x + d, b.y + 0.08, b.z + 0.08), m, "metal")
		box(Vector3(a.x - d, b.y, a.z - 0.08), Vector3(a.x + d, b.y + 0.1, b.z + 0.08), m, "metal", false)
		_floor_stripe(Vector3(a.x - 0.9, 0.005, a.z), Vector3(a.x - 0.75, 0.012, b.z))
		_floor_stripe(Vector3(a.x + 0.75, 0.005, a.z), Vector3(a.x + 0.9, 0.012, b.z))


func _floor_stripe(a: Vector3, b: Vector3) -> void:
	box(a, b, MatLib.hazard(), "concrete", false, null, false)


func ceiling(x0: float, z0: float, x1: float, z1: float, y: float, mat: Material = null) -> void:
	box(Vector3(x0, y, z0), Vector3(x1, y + 0.3, z1), mat if mat else MatLib.ceiling(), "metal", true)


func floor_overlay(x0: float, z0: float, x1: float, z1: float, mat: Material) -> void:
	box(Vector3(x0, 0.0, z0), Vector3(x1, 0.012, z1), mat, "concrete", false, null, false)


func make_door(id: String, hinge: Vector3, along_x: bool, locked := false) -> Door:
	var d := Door.new()
	d.name = "Door_" + id
	dyn.add_child(d)
	d.position = hinge
	d.rotation.y = 0.0 if along_x else -PI / 2
	d.build(props_root, DOOR_W)
	d.set_locked(locked)
	doors[id] = d
	return d


func light_spot(pos: Vector3, color: Color, energy: float, rng: float, angle: float, shadow: bool, room: String, dir := Vector3.DOWN, fixture := "highbay") -> SpotLight3D:
	var l := SpotLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.spot_range = rng
	l.spot_angle = angle
	l.spot_angle_attenuation = 0.8
	l.shadow_enabled = shadow
	l.shadow_blur = 1.5
	l.light_volumetric_fog_energy = 1.4
	l.light_size = 0.15
	l.distance_fade_enabled = true
	l.distance_fade_begin = 40.0
	l.distance_fade_length = 10.0
	add_child(l)
	l.position = pos
	if dir != Vector3.DOWN:
		l.look_at(pos + dir, Vector3.UP if absf(dir.normalized().y) < 0.95 else Vector3.FORWARD)
	else:
		l.rotation = Vector3(-PI / 2, 0, 0)
	_register_light(room, l)
	if fixture in ["highbay", "strip"] and _kit_fixture(fixture, pos, room):
		return l
	if fixture == "highbay":
		var f := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.09
		cm.bottom_radius = 0.38
		cm.height = 0.32
		f.mesh = cm
		f.material_override = MatLib.flat(Color(0.1, 0.1, 0.1), 0.8, 0.45)
		f.position = pos + Vector3(0, 0.18, 0)
		add_child(f)
		var disc := MeshInstance3D.new()
		var dm := CylinderMesh.new()
		dm.top_radius = 0.34
		dm.bottom_radius = 0.34
		dm.height = 0.02
		disc.mesh = dm
		disc.material_override = MatLib.flat(color, 0.0, 0.3, color, 6.0)
		disc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		disc.position = pos + Vector3(0, 0.02, 0)
		add_child(disc)
		_register_light(room, disc)
	elif fixture == "strip":
		var s := MeshInstance3D.new()
		var sm := BoxMesh.new()
		sm.size = Vector3(1.3, 0.05, 0.18)
		s.mesh = sm
		s.material_override = MatLib.flat(Color(0.9, 0.95, 1.0), 0.0, 0.3, color, 5.0)
		s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		s.position = pos + Vector3(0, 0.03, 0)
		add_child(s)
		_register_light(room, s)
		var hous := MeshInstance3D.new()
		var hm := BoxMesh.new()
		hm.size = Vector3(1.4, 0.08, 0.26)
		hous.mesh = hm
		hous.material_override = MatLib.flat(Color(0.2, 0.2, 0.2), 0.6, 0.5)
		hous.position = pos + Vector3(0, 0.09, 0)
		add_child(hous)
	return l


func light_omni(pos: Vector3, color: Color, energy: float, rng: float, shadow: bool, room: String, fixture := true) -> OmniLight3D:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = rng
	l.omni_attenuation = 1.4
	l.shadow_enabled = shadow
	l.light_volumetric_fog_energy = 1.0
	l.distance_fade_enabled = true
	l.distance_fade_begin = 35.0
	l.distance_fade_length = 8.0
	add_child(l)
	l.position = pos
	_register_light(room, l)
	if fixture:
		var lamp := prop("lamp", pos + Vector3(0, 0.12, 0), 0.0, false, "metal", false, self)
		if lamp:
			for mi in lamp.find_children("*", "MeshInstance3D", true, false):
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			_register_light(room, lamp.find_child("globe", true, false))
	return l


func _register_light(room: String, n: Node) -> void:
	if room == "" or n == null:
		return
	if Game.rooms.has(room):
		Game.rooms[room].lights.append(n)


func breaker(room: String, pos: Vector3, yaw_deg: float) -> void:
	var b := preload("res://scripts/level/breaker.gd").new()
	b.room = room
	b.collision_layer = 1
	b.set_meta("surface", "metal")
	dyn.add_child(b)
	b.position = pos
	b.rotation.y = deg_to_rad(yaw_deg)
	var vis := prop("breaker", Vector3.ZERO, 0.0, false, "metal", false, b)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(0.6, 0.8, 0.22)
	cs.shape = bs
	b.add_child(cs)
	b.led = vis.find_child("led", true, false) if vis else null
	var lbl := Label3D.new()
	lbl.text = "BREAKER " + room.to_upper()
	lbl.font_size = 22
	lbl.pixel_size = 0.0025
	lbl.modulate = Color(0.85, 0.85, 0.8)
	lbl.shaded = true
	lbl.position = Vector3(0, 0.5, -0.11)
	lbl.rotation.y = PI
	b.add_child(lbl)


func terminal(pos: Vector3, yaw_deg: float, title: String, lines: PackedStringArray) -> void:
	var t := preload("res://scripts/level/terminal.gd").new()
	t.title = title
	t.lines = lines
	t.collision_layer = 1
	dyn.add_child(t)
	t.position = pos
	t.rotation.y = deg_to_rad(yaw_deg)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(0.6, 0.4, 0.15)
	cs.shape = bs
	cs.position = Vector3(0, 0.2, 0)
	t.add_child(cs)
	var scr := MeshInstance3D.new()
	var sm := BoxMesh.new()
	sm.size = Vector3(0.55, 0.36, 0.06)
	scr.mesh = sm
	scr.material_override = MatLib.flat(Color(0.02, 0.05, 0.05), 0.0, 0.2, Color(0.3, 0.75, 0.6), 1.8)
	scr.position = Vector3(0, 0.2, 0)
	t.add_child(scr)
	var lbl := Label3D.new()
	lbl.text = title + "\n> _"
	lbl.font_size = 18
	lbl.pixel_size = 0.0022
	lbl.modulate = Color(0.55, 1.0, 0.8)
	lbl.position = Vector3(0, 0.22, -0.035)
	lbl.rotation.y = PI
	t.add_child(lbl)


func place_sign(text: String, pos: Vector3, yaw_deg: float, size := 64, color := Color(0.85, 0.84, 0.8), px := 0.004) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.font_size = size
	l.pixel_size = px
	l.modulate = color
	l.shaded = true
	l.double_sided = false
	l.outline_size = 0
	l.position = pos
	l.rotation.y = deg_to_rad(yaw_deg)
	add_child(l)
	return l


# ------------------------------------------------------------------ rooms
func _rooms() -> void:
	Game.rooms.clear()
	Game.add_room("dock", AABB(Vector3(0, -1, 0), Vector3(16, 8, 14)))
	Game.add_room("corridor", AABB(Vector3(6, -1, -30), Vector3(3, 6, 30)))
	Game.add_room("office", AABB(Vector3(-6, -1, -13), Vector3(12, 6, 10)))
	Game.add_room("passage", AABB(Vector3(12, -1, -2), Vector3(2.5, 6, 2)))
	Game.add_room("hall", AABB(Vector3(9, -1, -26), Vector3(23, 11, 24)))
	Game.add_room("servers", AABB(Vector3(9, -1, -38), Vector3(12, 6, 12)))
	Game.add_room("control", AABB(Vector3(21, -1, -40), Vector3(12, 7, 14)))


func _shell() -> void:
	# Base slab under everything
	box(Vector3(-7, -0.4, -41), Vector3(34, 0, 15), MatLib.floor_concrete(), "concrete")
	# DOCK
	wall_x(14, 0, 16, 6.3)
	wall_z(0, 0, 14, 6.3)
	wall_z(16, 0, 14, 6.3)
	wall_x(0, 0, 16, 6.3, [[6.75, 8.25, 2.2], [12.0, 14.5, 3.0]])
	ceiling(0, 0, 16, 14, 6.0)
	# CORRIDOR
	wall_z(6, -30, 0, 3.9, [[-9.25, -7.75, 2.2]])
	wall_z(9, -30, -26, 4.0, [[-29.75, -28.25, 2.2]])
	wall_z(9, -26, -2, 9.3, [[-11.75, -10.25, 2.2]])
	wall_z(9, -2, 0, 6.3)
	wall_x(-30, 6, 9, 3.9)
	ceiling(6, -30, 9, 0, 3.6)
	# OFFICE
	wall_z(-6, -13, -3, 3.9, [], MatLib.wall_block())
	wall_x(-13, -6, 6, 3.9, [], MatLib.wall_block())
	wall_x(-3, -6, 6, 3.9, [], MatLib.wall_block())
	ceiling(-6, -13, 6, -3, 3.6, MatLib.ceiling_tiles())
	# PASSAGE (crouch shutter)
	wall_z(12, -2, 0, 3.3)
	wall_z(14.5, -2, 0, 3.3)
	ceiling(12, -2, 14.5, 0, 3.0)
	# HALL
	wall_x(-2, 9, 32, 9.3, [[12.0, 14.5, 3.0]], MatLib.wall_concrete())
	wall_z(32, -26, -2, 9.3, [], MatLib.grid_panel())
	wall_x(-26, 9, 33, 9.3, [[13.25, 14.75, 2.2], [27.25, 28.75, 2.2]])
	ceiling(9, -26, 32, -2, 9.0)
	# SERVERS
	wall_z(9, -38, -30, 4.0)
	wall_x(-38, 9, 21, 4.0)
	wall_z(21, -40, -26, 4.8, [[-32.75, -31.25, 2.2]])
	ceiling(9, -38, 21, -26, 3.6, MatLib.flat(Color(0.3, 0.31, 0.32), 0.5, 0.6))
	# CONTROL
	wall_x(-40, 21, 33, 4.8)
	wall_z(33, -40, -26, 4.8)
	ceiling(21, -40, 33, -26, 4.5)
	# Doors
	make_door("D1", Vector3(6.79, 0, 0), true)
	make_door("D2", Vector3(6, 0, -9.21), false)
	make_door("D3", Vector3(9, 0, -11.71), false)
	make_door("D4", Vector3(13.29, 0, -26), true)
	make_door("D5", Vector3(21, 0, -32.71), false)
	make_door("D6", Vector3(27.29, 0, -26), true, true)
	doors.D6.set_locked(true, "SEALED - RELAY LOCKDOWN")
	make_door("D7", Vector3(9, 0, -29.71), false)


func _dock() -> void:
	floor_overlay(0.2, 0.2, 15.8, 13.8, MatLib.floor_painted())
	# Lift platform with hazard edge (extraction)
	var m3 := ResourceLoader.exists("res://assets/models/dock_kit.glb")
	# Lift deck (walkable). With the M3 kit the freight_lift model is the visual.
	box(Vector3(1.0, 0, 10.0), Vector3(5.0, 0.08, 13.6), MatLib.diamond_plate(), "metal").visible = not m3
	if not m3:
		box(Vector3(1.0, 0.0, 9.85), Vector3(5.0, 0.085, 10.0), MatLib.hazard(), "metal", false)
		box(Vector3(0.3, 2.6, 9.7), Vector3(0.6, 6.0, 9.9), MatLib.flat(Color(0.08, 0.08, 0.08), 0.8, 0.4), "metal")
	box(Vector3(0.6, 0, 9.6), Vector3(0.75, 1.1, 13.6), MatLib.flat(Color(0.7, 0.55, 0.05), 0.4, 0.5), "metal").visible = not m3
	place_sign("FREIGHT LIFT 2\nEXTRACTION", Vector3(0.17, 3.2, 11.8), 90, 72, Color(0.85, 0.7, 0.2))
	# Roll-up bay door (closed) on south wall
	if not m3:
		box(Vector3(9.0, 0, 13.75), Vector3(14.0, 4.5, 13.85), MatLib.corrugated(), "metal")
		box(Vector3(8.8, 4.5, 13.7), Vector3(14.2, 4.9, 13.85), MatLib.flat(Color(0.1, 0.1, 0.1), 0.8, 0.4), "metal")
	place_sign("BAY 2", Vector3(11.5, 5.3, 13.83), 180, 120, Color(0.85, 0.84, 0.8))
	# Cover and clutter
	prop("crate", Vector3(4.0, 0, 5.0), 0, true)
	prop("crate", Vector3(4.0, 0.8, 5.0), 8, false)
	prop("crate", Vector3(11.5, 0, 6.0), 90, true)
	prop("barrier", Vector3(8.0, 0, 3.5), 0, true, "concrete")
	prop("barrel", Vector3(14.6, 0, 2.0), 0, true)
	prop("barrel", Vector3(14.9, 0, 2.9), 0, false)
	prop("barrel", Vector3(1.3, 0, 1.4), 0, true)
	if not m3:
		prop("locker", Vector3(15.6, 0, 8.0), -90, false)
		prop("locker", Vector3(15.6, 0, 8.6), -90, false)
	# Armory case (loadout)
	var case := prop("crate", Vector3(10.5, 0, 10.5), 90, true)
	var arm := preload("res://scripts/level/armory.gd").new()
	arm.collision_layer = 1
	dyn.add_child(arm)
	arm.position = Vector3(10.5, 0.4, 10.5)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(0.9, 0.9, 1.3)
	cs.shape = bs
	arm.add_child(cs)
	place_sign("ARMORY", Vector3(9.89, 0.55, 10.5), -90, 48, Color(0.9, 0.9, 0.85), 0.003)
	# Extraction trigger
	extraction_area = Area3D.new()
	extraction_area.collision_layer = 0
	extraction_area.collision_mask = 1 << 1
	var es := CollisionShape3D.new()
	var eb := BoxShape3D.new()
	eb.size = Vector3(4.0, 3.0, 3.6)
	es.shape = eb
	extraction_area.add_child(es)
	dyn.add_child(extraction_area)
	extraction_area.position = Vector3(3.0, 1.5, 11.8)
	# Pipes along the north wall
	if not m3:
		prop("pipe", Vector3(3.0, 5.2, 0.5), 90, false, "metal", false)
		prop("pipe", Vector3(10.0, 5.2, 0.5), 90, false, "metal", false)
	terminal(Vector3(15.7, 1.3, 3.4), 90, "SHIFT LOG 2207", PackedStringArray([
		"SHIFT LOG 22:07 - Relay Nine sync fault. Security units",
		"rejected manual override and sealed the control wing.",
		"Two techs missing. Do NOT approach the Tesla units."]))


func _corridor() -> void:
	floor_overlay(6.15, -29.85, 8.85, -0.15, MatLib.diamond_plate())
	# Cable tray + pipes along ceiling
	box(Vector3(6.2, 3.2, -29.8), Vector3(6.6, 3.28, -0.2), MatLib.flat(Color(0.25, 0.25, 0.25), 0.8, 0.5), "metal", false)
	if not ResourceLoader.exists("res://assets/models/env_kit.glb"):
		for z in [-4.0, -8.0, -16.0, -24.0]:
			prop("pipe", Vector3(8.6, 3.25, z), 0, false, "metal", false)
	# Obstacles break the long sightline
	prop("locker", Vector3(8.6, 0, -14.5), -90, true)
	prop("crate", Vector3(6.85, 0, -19.5), 90, true)
	prop("barrel", Vector3(8.45, 0, -23.7), 0, false)   # between corridor ribs
	prop("locker", Vector3(6.4, 0, -25.5), 90, true)
	place_sign("SERVICE CORRIDOR C", Vector3(7.5, 2.7, -0.17), 180, 40)
	place_sign("SECURITY", Vector3(6.17, 2.5, -8.5), 90, 40)
	place_sign("TURBINE HALL", Vector3(8.83, 2.5, -11.0), -90, 40)
	place_sign("DATA CENTRE", Vector3(8.83, 2.5, -29.0), -90, 40)
	breaker("corridor", Vector3(6.25, 1.5, -2.0), 90)


func _office() -> void:
	floor_overlay(-5.85, -12.85, 5.85, -3.15, MatLib.pbr("concrete_floor_painted", 0.5, Color(0.5, 0.52, 0.55), 0.0, 1.0, "office_floor"))
	prop("desk", Vector3(-2.5, 0, -10.0), 0, true)
	prop("desk", Vector3(1.5, 0, -10.0), 0, true)
	prop("desk", Vector3(-2.5, 0, -6.0), 180, true)
	prop("desk", Vector3(2.0, 0, -5.5), 200, false)  # shoved aside: struggle
	prop("locker", Vector3(-5.6, 0, -12.0), 90, false)
	prop("locker", Vector3(-5.6, 0, -11.4), 90, false)
	prop("locker", Vector3(-5.6, 0, -10.8), 90, false)
	prop("server_rack", Vector3(5.3, 0, -12.2), -90, true)
	# Toppled locker
	var tl := prop("locker", Vector3(-4.2, 0.25, -5.0), 0, false, "metal", false)
	if tl: tl.rotation = Vector3(0, 0.4, PI / 2)
	box(Vector3(-5.0, 0, -5.4), Vector3(-3.1, 0.5, -4.6), MatLib.flat(Color(0, 0, 0, 0)), "metal", true).visible = false
	terminal(Vector3(1.5, 0.95, -9.85), 180, "SEC LOG", PackedStringArray([
		"SEC-4: Units T-04 through T-11 re-tasked by RELAY NINE.",
		"Weak point: rear capacitor stack. Optic cluster blinds them.",
		"They hear gunfire through walls. Kill the lights if you can."]))
	breaker("office", Vector3(-5.75, 1.5, -4.0), 90)
	place_sign("SECURITY OFFICE 9-B", Vector3(0, 2.8, -12.83), 0, 52)
	# Wall map
	box(Vector3(-2.0, 1.3, -12.84), Vector3(1.0, 2.4, -12.8), MatLib.flat(Color(0.75, 0.72, 0.62), 0.0, 0.8), "concrete", false)
	place_sign("SITE PLAN", Vector3(-0.5, 2.25, -12.78), 0, 28, Color(0.15, 0.15, 0.15))


func _passage() -> void:
	floor_overlay(12.15, -1.85, 14.35, -0.15, MatLib.diamond_plate())
	# Jammed shutter: crouch under it (robots cannot path here).
	box(Vector3(12.0, 1.15, -1.1), Vector3(14.5, 3.0, -0.9), MatLib.corrugated(), "metal")
	box(Vector3(12.0, 1.1, -1.12), Vector3(14.5, 1.18, -0.88), MatLib.hazard(), "metal", false)
	place_sign("CAUTION - SHUTTER JAMMED", Vector3(13.25, 1.6, -0.88), 0, 30, Color(0.9, 0.75, 0.2), 0.0035)


func _hall() -> void:
	floor_overlay(9.15, -25.85, 31.85, -2.15, MatLib.floor_painted())
	# Turbine housings: large machinery blocks (hard cover)
	for z in [-8.0, -15.0]:
		var x0 := 15.0
		_turbine(x0, z)
		cover_props.append(AABB(Vector3(x0, 0, z - 1.6), Vector3(8.0, 3.2, 3.2)))
		place_sign("TURBINE %s" % ("T1" if z == -8.0 else "T2"), Vector3(x0 + 4.0, 1.3, z + 1.52), 0, 64, Color(0.12, 0.12, 0.12))
	# Transformer block in the NE corner
	box(Vector3(26.0, 0, -24.5), Vector3(30.0, 3.5, -20.5), MatLib.rust_panel(), "metal")
	cover_props.append(AABB(Vector3(26, 0, -24.5), Vector3(4, 3.5, 4)))
	place_sign("DANGER 11kV", Vector3(28.0, 2.6, -20.48), 0, 70, Color(0.95, 0.8, 0.2))
	# Low cover scattered
	prop("barrier", Vector3(12.5, 0, -5.5), 0, true, "concrete")
	prop("barrier", Vector3(28.0, 0, -5.0), 90, true, "concrete")
	prop("barrier", Vector3(12.0, 0, -19.5), 90, true, "concrete")
	prop("crate", Vector3(25.5, 0, -12.0), 0, true)
	prop("crate", Vector3(26.8, 0, -12.0), 0, false)
	prop("crate", Vector3(19.0, 0, -22.5), 90, true)
	prop("crate", Vector3(19.0, 0.8, -22.5), 80, false)
	prop("barrel", Vector3(30.8, 0, -16.0), 0, true)
	prop("barrel", Vector3(30.5, 0, -15.2), 0, false)
	prop("barrel", Vector3(10.0, 0, -24.8), 0, false)
	# Robot charging docks along east wall (environmental storytelling)
	for i in 3:
		var z := -6.0 - i * 3.2
		box(Vector3(31.2, 0, z - 1.0), Vector3(31.85, 3.0, z + 1.0), MatLib.flat(Color(0.12, 0.12, 0.13), 0.8, 0.45), "metal")
		box(Vector3(31.15, 2.3, z - 0.2), Vector3(31.2, 2.5, z + 0.2), MatLib.flat(Color(0.3, 0.7, 1.0), 0.0, 0.3, Color(0.3, 0.7, 1.0), 3.0 if i != 1 else 0.0), "metal", false)
		place_sign("CHARGE BAY %02d" % (i + 4), Vector3(31.18, 2.75, z), -90, 26)
	# Deactivated unit slumped in bay 05
	var dead := (load("res://assets/models/teslabot.glb") as PackedScene).instantiate()
	add_child(dead)
	MatLib.remap_scene(dead)
	dead.position = Vector3(30.6, 0, -9.2)
	dead.rotation.y = PI / 2
	# Powered-down unit docked upright in its bay (head drooped, optics dark),
	# feet measured onto the floor.
	var dead_aabb := _world_aabb(dead)
	dead.position.y -= dead_aabb.position.y
	var dh: Node3D = dead.find_child("head", true, false)
	if dh: dh.rotation = Vector3(0.45, 0.25, 0)
	for mi in dead.find_children("eye*", "MeshInstance3D", true, false):
		mi.visible = false
	# Overhead crane beam + pipes + hanging chain
	box(Vector3(9.2, 7.6, -14.0), Vector3(31.8, 8.2, -13.4), MatLib.flat(Color(0.65, 0.5, 0.08), 0.5, 0.5), "metal", false)
	box(Vector3(20.0, 7.0, -14.2), Vector3(21.2, 7.6, -13.2), MatLib.flat(Color(0.1, 0.1, 0.1), 0.8, 0.4), "metal", false)
	box(Vector3(20.55, 3.2, -13.75), Vector3(20.65, 7.0, -13.65), MatLib.flat(Color(0.2, 0.2, 0.2), 1.0, 0.35), "metal", false)
	for x in [12.0, 22.0]:
		prop("pipe", Vector3(x, 8.4, -3.0), 90, false, "metal", false)
		prop("pipe", Vector3(x + 4.0, 8.4, -3.0), 90, false, "metal", false)
	# Pillars
	for x in [9.6, 31.4]:
		for z in [-13.7]:
			box(Vector3(x - 0.35, 0, z - 0.35), Vector3(x + 0.35, 9.0, z + 0.35), MatLib.wall_concrete(), "concrete")
	breaker("hall", Vector3(9.3, 1.5, -20.0), 90)
	place_sign("TURBINE HALL - SUBSTATION 9-B", Vector3(20.5, 7.0, -2.17), 180, 96, Color(0.82, 0.8, 0.74), 0.006)
	place_sign("RELAY CONTROL", Vector3(28.0, 3.0, -25.83), 180, 48, Color(0.9, 0.3, 0.2))
	place_sign("DATA CENTRE", Vector3(14.0, 3.0, -25.83), 180, 48)


func _servers() -> void:
	floor_overlay(9.15, -37.85, 20.85, -26.15, MatLib.floor_rubber())
	for row in [-29.5, -32.5, -35.5]:
		for i in 6:
			var x := 10.9 + i * 0.66
			if row == -32.5 and i == 2:
				continue  # gap for a cross-aisle
			prop("server_rack", Vector3(x, 0, row), 0 if row != -35.5 else 180, false)
		for i in 5:
			var x := 16.2 + i * 0.66
			prop("server_rack", Vector3(x, 0, row), 0 if row != -35.5 else 180, false)
		cover_props.append(AABB(Vector3(10.6, 0, row - 0.5), Vector3(4.0, 2.0, 1.0)))
		cover_props.append(AABB(Vector3(15.9, 0, row - 0.5), Vector3(3.3, 2.0, 1.0)))
	breaker("servers", Vector3(20.75, 1.5, -27.0), -90)
	place_sign("RELAY CONTROL ->", Vector3(20.83, 2.6, -32.0), -90, 40, Color(0.9, 0.3, 0.2))


func _control() -> void:
	floor_overlay(21.15, -39.85, 32.85, -26.15, MatLib.floor_epoxy())
	# Relay console objective
	console = preload("res://scripts/level/relay_console.gd").new()
	console.name = "RelayConsole"
	dyn.add_child(console)
	console.position = Vector3(27.0, 0, -37.0)
	var vis := prop("relay_console", Vector3.ZERO, 0, false, "metal", false, console)
	var sb := StaticBody3D.new()
	sb.collision_layer = 1
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(1.5, 1.6, 0.8)
	cs.shape = bs
	cs.position = Vector3(0, 0.8, 0)
	sb.add_child(cs)
	sb.set_meta("surface", "metal")
	console.add_child(sb)
	cover_props.append(AABB(Vector3(26.25, 0, -37.4), Vector3(1.5, 1.0, 0.8)))
	var sl := OmniLight3D.new()
	sl.light_color = Color(0.35, 0.85, 0.7)
	sl.light_energy = 1.0
	sl.omni_range = 4.0
	console.add_child(sl)
	sl.position = Vector3(0, 1.4, 0.6)
	console.screen_light = sl
	# Desks and monitors
	prop("desk", Vector3(23.5, 0, -32.0), 90, true)
	prop("desk", Vector3(30.5, 0, -32.0), -90, true)
	prop("server_rack", Vector3(32.5, 0, -38.5), -90, false)
	prop("server_rack", Vector3(32.5, 0, -37.8), -90, false)
	prop("barrier", Vector3(27.0, 0, -29.0), 0, true, "concrete")
	# Wall screen
	box(Vector3(24.0, 1.8, -39.84), Vector3(30.0, 3.8, -39.8), MatLib.flat(Color(0.02, 0.03, 0.04), 0.0, 0.15, Color(0.2, 0.45, 0.6), 0.22), "metal", false)
	place_sign("RELAY NINE // SYNC FAULT", Vector3(27.0, 3.3, -39.78), 0, 64, Color(0.9, 0.35, 0.25))
	place_sign("SECURITY OVERRIDE: AUTONOMOUS", Vector3(27.0, 2.6, -39.78), 0, 40, Color(0.6, 0.8, 0.9))
	terminal(Vector3(23.5, 0.95, -32.0), -90, "RELAY 9", PackedStringArray([
		"RELAY NINE: Sync lost 41h. Units obey the relay, not people.",
		"Uplink override requires 40s of uninterrupted upload.",
		"Expect units to converge on the console during transfer."]))
	breaker("control", Vector3(32.75, 1.5, -28.0), -90)


func _lights() -> void:
	var warm := Color(1.0, 0.86, 0.7)
	var sodium := Color(1.0, 0.8, 0.6)
	var cool := Color(0.82, 0.9, 1.0)
	var moon := Color(0.55, 0.68, 0.95)
	# DOCK
	light_spot(Vector3(4, 5.7, 4), sodium, 11.0, 10.0, 60, true, "dock")
	light_spot(Vector3(12, 5.7, 4), sodium, 11.0, 10.0, 60, false, "dock")
	light_spot(Vector3(6.6, 5.7, 11.5), cool, 8.0, 10.0, 60, false, "dock")   # clear of the lift rig
	light_spot(Vector3(12, 5.7, 10), sodium, 11.0, 10.0, 60, true, "dock")
	light_omni(Vector3(8, 2.5, 7), Color(0.75, 0.82, 1.0), 0.8, 12.0, false, "dock", false)
	light_spot(Vector3(8, 5.6, 3.0), warm, 2.5, 9.0, 70, false, "dock", Vector3(0, -0.75, -1).normalized(), "")
	beacon = light_omni(Vector3(0.9, 3.0, 9.7), Color(1.0, 0.25, 0.1), 0.0, 8.0, false, "", false)
	# CORRIDOR
	for i in 5:
		var z := -3.0 - i * 6.0
		var l := light_omni(Vector3(7.5, 3.3, z), warm, 2.2, 6.5, i % 2 == 0, "corridor")
		if i == 3:
			l.set_meta("flicker", true)
	# OFFICE
	light_spot(Vector3(-2, 3.5, -8), cool, 6.0, 6.5, 78, true, "office", Vector3.DOWN, "strip")
	light_omni(Vector3(0.0, 2.4, -8.0), Color(0.8, 0.86, 0.95), 0.6, 9.0, false, "office", false)
	light_spot(Vector3(3, 3.5, -8), cool, 4.0, 6.0, 75, false, "office", Vector3.DOWN, "strip")
	light_omni(Vector3(1.5, 1.2, -10.2), Color(0.3, 0.8, 0.65), 0.4, 2.5, false, "", false)
	# PASSAGE
	light_omni(Vector3(13.25, 2.8, -0.4), warm, 1.5, 4.0, false, "passage")
	# HALL: high bays with volumetric shafts, plus cold light through upper slits
	var hb := [Vector3(12, 8.4, -5), Vector3(19, 8.4, -4), Vector3(27, 8.4, -9), Vector3(12, 8.4, -17), Vector3(23, 8.4, -19), Vector3(29, 8.4, -23)]
	for i in hb.size():
		var l := light_spot(hb[i], sodium, 19.0, 15.0, 44, i % 2 == 0, "hall")
		if i == 4:
			l.set_meta("flicker", true)
	light_spot(Vector3(31.6, 8.0, -12.0), moon, 9.0, 26.0, 18, true, "", Vector3(-1.0, -0.75, 0.15).normalized(), "")
	light_spot(Vector3(31.6, 8.0, -20.0), moon, 7.0, 26.0, 16, false, "", Vector3(-1.0, -0.8, -0.1).normalized(), "")
	for z in [-12.0, -20.0]:
		box(Vector3(31.82, 7.4, z - 1.2), Vector3(31.86, 8.6, z + 1.2), MatLib.flat(moon, 0.0, 0.3, moon, 3.0), "concrete", false, null, false)
	light_omni(Vector3(15.0, 2.4, -8.0), Color(1.0, 0.55, 0.1), 0.9, 3.0, false, "hall", false)
	light_omni(Vector3(15.0, 2.4, -15.0), Color(1.0, 0.55, 0.1), 0.9, 3.0, false, "hall", false)
	# SERVERS: cold strips + rack glow
	for z in [-28.0, -31.0, -34.0, -36.6]:
		light_spot(Vector3(15.0, 3.5, z), cool, 3.0, 5.0, 80, z == -31.0 or z == -37.0, "servers", Vector3.DOWN, "strip")
	light_omni(Vector3(12.5, 1.0, -31.0), Color(0.3, 0.5, 1.0), 0.5, 4.0, false, "servers", false)
	light_omni(Vector3(18.0, 1.0, -34.0), Color(0.3, 0.5, 1.0), 0.5, 4.0, false, "servers", false)
	# CONTROL
	var cfix := "" if ResourceLoader.exists("res://assets/models/dock_kit.glb") else "strip"
	light_spot(Vector3(24.6, 4.25, -33.0), cool, 6.5, 7.0, 78, true, "control", Vector3.DOWN, cfix)
	light_spot(Vector3(27.0, 4.25, -37.8), cool, 5.0, 6.0, 75, false, "control", Vector3.DOWN, cfix)
	light_spot(Vector3(27.0, 4.25, -28.2), cool, 4.0, 6.0, 75, false, "control", Vector3.DOWN, cfix)
	light_spot(Vector3(29.4, 4.25, -33.0), cool, 6.5, 7.0, 78, false, "control", Vector3.DOWN, cfix)
	# Workstation glow from the operator screens
	light_omni(Vector3(27.0, 1.3, -33.6), Color(0.45, 0.75, 0.85), 0.7, 3.5, false, "control", false)
	_reflection_probes()
	light_omni(Vector3(32.5, 3.8, -27.0), Color(1.0, 0.15, 0.08), 1.2, 6.0, false, "control", false)


func _signage() -> void:
	place_sign("RELAY NINE", Vector3(8.0, 4.6, 0.17), 0, 96, Color(0.75, 0.74, 0.7), 0.006)
	place_sign("SUBSTATION 9-B / AUTHORIZED PERSONNEL ONLY", Vector3(8.0, 3.9, 0.17), 0, 36)
	place_sign("NO UNESCORTED ACCESS BEYOND THIS POINT", Vector3(13.25, 3.3, 0.17), 0, 26, Color(0.9, 0.75, 0.2))
	# Painted floor arrows (as flat labels)
	var a := place_sign("TO RELAY CONTROL", Vector3(7.5, 0.02, -6.0), 0, 64, Color(0.75, 0.62, 0.15), 0.004)
	a.rotation = Vector3(-PI / 2, 0, 0)


func _enemy_spawns() -> void:
	# pos, patrol points, group
	spawns = [
		{"pos": Vector3(-3.0, 0, -8.0), "patrol": [Vector3(-3, 0, -8), Vector3(3.5, 0, -8), Vector3(3.5, 0, -11.5), Vector3(-4, 0, -11.5)], "group": "office"},
		{"pos": Vector3(4.2, 0, -4.2), "patrol": [], "group": "office"},
		{"pos": Vector3(7.5, 0, -22.0), "patrol": [Vector3(7.5, 0, -27), Vector3(7.5, 0, -12)], "group": "corridor"},
		{"pos": Vector3(13.0, 0, -11.5), "patrol": [Vector3(13, 0, -11.5), Vector3(24.5, 0, -11.5), Vector3(24.5, 0, -4.5), Vector3(13, 0, -4.5)], "group": "hall"},
		{"pos": Vector3(25.0, 0, -18.0), "patrol": [Vector3(25, 0, -18), Vector3(12.5, 0, -18.5), Vector3(12.5, 0, -23.5), Vector3(24, 0, -23.5)], "group": "hall"},
		{"pos": Vector3(29.0, 0, -8.0), "patrol": [], "group": "hall"},
		{"pos": Vector3(15.5, 0, -24.0), "patrol": [Vector3(15.5, 0, -24), Vector3(22, 0, -24.5)], "group": "hall"},
		{"pos": Vector3(15.3, 0, -31.0), "patrol": [Vector3(15.3, 0, -31), Vector3(15.3, 0, -37), Vector3(10, 0, -37), Vector3(10, 0, -27.5), Vector3(20, 0, -27.5)], "group": "servers"},
		{"pos": Vector3(19.8, 0, -34.0), "patrol": [Vector3(19.8, 0, -34), Vector3(10.2, 0, -34)], "group": "servers"},
		{"pos": Vector3(29.0, 0, -35.0), "patrol": [Vector3(29, 0, -35), Vector3(24, 0, -35), Vector3(24, 0, -28.5), Vector3(30, 0, -28.5)], "group": "control"},
	]


## Cover points: around each cover AABB, one per face side, offset outward.
func build_cover_points() -> Array:
	var pts := []
	for aabb in cover_props:
		var c: Vector3 = aabb.get_center()
		var hx: float = aabb.size.x / 2.0
		var hz: float = aabb.size.z / 2.0
		var faces := [[Vector3(1, 0, 0), hx, hz], [Vector3(-1, 0, 0), hx, hz], [Vector3(0, 0, 1), hz, hx], [Vector3(0, 0, -1), hz, hx]]
		for f in faces:
			var n: Vector3 = f[0]
			var t := Vector3(-n.z, 0, n.x)
			var along: float = f[2]
			var steps := maxi(1, int(along * 2.0 / 1.6))
			for i in steps:
				var off := (float(i) + 0.5) / steps * 2.0 - 1.0
				var pos: Vector3 = c + n * (f[1] + 0.75) + t * off * along * 0.8
				pos.y = 0
				var side := 1.0 if off >= 0.0 else -1.0
				var peek: Vector3 = c + n * (f[1] + 0.6) + t * side * (along + 0.9)
				peek.y = 0
				var peek2: Vector3 = c + n * (f[1] + 0.6) - t * side * (along + 0.9)
				peek2.y = 0
				var sp := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, pos)
				var spk := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, peek)
				if sp.distance_to(pos) > 0.6 or spk.distance_to(peek) > 0.8:
					continue
				var spk2 := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, peek2)
				var e := {"pos": sp, "normal": n, "peek": spk, "owner": null}
				if spk2.distance_to(peek2) < 0.8:
					e["peek2"] = spk2
				pts.append(e)
	return pts



# ------------------------------------------------------------------ audio zones
const ROOM_AUDIO := {
	"dock": ["Rev_Dock", "ambience_dock", Vector3(8, 3, 7), -12.0],
	"corridor": ["Rev_Small", "ambience_facility", Vector3(7.5, 2.5, -15), -18.0],
	"office": ["Rev_Small", "electric_buzz_loop", Vector3(0.5, 3.2, -8), -22.0],
	"passage": ["Rev_Small", "", Vector3.ZERO, 0.0],
	"hall": ["Rev_Hall", "ambience_hall", Vector3(20, 4, -14), -10.0],
	"servers": ["Rev_Servers", "ambience_servers", Vector3(15, 1.5, -32), -12.0],
	"control": ["Rev_Small", "ambience_control", Vector3(27, 3.0, -33), -13.0],
}


func _audio_zones() -> void:
	for room in ROOM_AUDIO:
		if not Game.rooms.has(room):
			continue
		var cfg: Array = ROOM_AUDIO[room]
		var aabb: AABB = Game.rooms[room].aabb
		var a := Area3D.new()
		a.name = "Reverb_" + room
		a.collision_layer = 1 << 5   # audio-only layer; rays never test it
		a.collision_mask = 0
		a.monitoring = false
		a.reverb_bus_enabled = true
		a.reverb_bus_name = cfg[0]
		a.reverb_bus_amount = 1.0
		a.reverb_bus_uniformity = 0.6
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = aabb.size
		cs.shape = bs
		a.add_child(cs)
		add_child(a)
		a.global_position = aabb.get_center()
		if cfg[1] != "" and ResourceLoader.exists("res://assets/audio/%s.wav" % cfg[1]):
			var holder := Node3D.new()
			add_child(holder)
			holder.global_position = cfg[2]
			var p := Sfx.loop_3d(cfg[1], holder, cfg[3], 14.0)
			if p:
				p.max_distance = maxf(aabb.size.x, aabb.size.z) * 0.9
				p.attenuation_filter_cutoff_hz = 9000.0



var _kit_root: Node3D


## M2 light fixtures from env_kit.glb; their emissive parts follow room power.
func _kit_fixture(kind: String, pos: Vector3, room: String) -> bool:
	if _kit_root == null:
		if not ResourceLoader.exists("res://assets/models/env_kit.glb"):
			return false
		_kit_root = (load("res://assets/models/env_kit.glb") as PackedScene).instantiate()
	var src: Node3D = _kit_root.get_node_or_null("highbay" if kind == "highbay" else "troffer")
	if src == null:
		return false
	var f: Node3D = src.duplicate()
	add_child(f)
	# High-bay origin is its hook (bulb ~0.49 below); troffer origin is the ceiling plane.
	f.position = pos + (Vector3(0, 0.47, 0) if kind == "highbay" else Vector3(0, 0.08, 0))
	MatLib.remap_scene(f)
	for mi in f.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for nm in ["lamp_bulb", "light_panel"]:
		var e: Node = f.find_child(nm + "*", true, false)
		if e:
			_register_light(room, e)
	return true



## Horizontal generator set: concrete plinth, ribbed cylindrical stator housing
## with flanges, bearing pedestals, exciter cabinet, cooling duct to the roof.
## Collision stays the simple 8 x 3.2 x 3.2 block used for cover.
func _turbine(x0: float, z: float) -> void:
	var dark := MatLib.flat(Color(0.09, 0.095, 0.1), 0.85, 0.4)
	var steel := MatLib.flat(Color(0.42, 0.43, 0.44), 1.0, 0.33)
	var paint := MatLib.machinery()
	# Invisible collider (gameplay block)
	var col := box(Vector3(x0, 0, z - 1.6), Vector3(x0 + 8.0, 3.2, z + 1.6), paint, "metal")
	col.visible = false
	box(Vector3(x0 - 0.3, 0, z - 1.75), Vector3(x0 + 8.3, 0.45, z + 1.75), MatLib.pbr("concrete_wall_009", 0.6, Color(0.7, 0.7, 0.68), 0.0, 1.0, "plinth"), "concrete", false)
	# Hazard edge band on the plinth (edges only)
	for zz in [z - 1.77, z + 1.62]:
		box(Vector3(x0 - 0.32, 0.45, zz), Vector3(x0 + 8.32, 0.47, zz + 0.15), MatLib.hazard(), "concrete", false, null, false)
	# Stator housing
	_cyl(Vector3(x0 + 4.0, 1.95, z), 1.42, 6.6, paint, 48)
	for i in 7:
		_cyl(Vector3(x0 + 0.9 + i * 1.03, 1.95, z), 1.5, 0.14, dark, 48)
	# Cooling ribs along the top
	for i in 9:
		box(Vector3(x0 + 1.0 + i * 0.68, 3.25, z - 0.55), Vector3(x0 + 1.12 + i * 0.68, 3.45, z + 0.55), dark, "metal", false)
	# End bells + shaft + bearing pedestals
	_cyl(Vector3(x0 + 0.45, 1.95, z), 1.15, 0.5, dark, 40)
	_cyl(Vector3(x0 + 7.55, 1.95, z), 1.15, 0.5, dark, 40)
	_cyl(Vector3(x0 - 0.15, 1.95, z), 0.28, 0.9, steel, 24)
	for px in [x0 - 0.25, x0 + 8.15]:
		box(Vector3(px - 0.25, 0.45, z - 0.55), Vector3(px + 0.25, 1.7, z + 0.55), dark, "metal", false)
	# Exciter cabinet at the west end
	box(Vector3(x0 - 0.75, 0.45, z - 0.9), Vector3(x0 - 0.3, 2.6, z + 0.9), MatLib.pbr("blue_metal_plate", 0.5, Color(0.5, 0.56, 0.62), 0.5, 1.0, "exciter"), "metal", false)
	box(Vector3(x0 - 0.78, 2.1, z - 0.4), Vector3(x0 - 0.74, 2.3, z - 0.2), MatLib.flat(Color(1, 0.6, 0.1), 0.0, 0.4, Color(1, 0.55, 0.1), 4.0), "metal", false, null, false)
	# Cooling duct up into the roof
	box(Vector3(x0 + 2.0, 3.3, z - 0.45), Vector3(x0 + 2.9, 9.0, z + 0.45), MatLib.pbr("rusty_metal_sheet", 0.5, Color(0.6, 0.62, 0.64), 0.8, 1.0, "duct_steel"), "metal", false)
	for y in [4.5, 6.0, 7.5]:
		box(Vector3(x0 + 1.95, y, z - 0.5), Vector3(x0 + 2.95, y + 0.08, z + 0.5), dark, "metal", false)
	# Nameplate band
	box(Vector3(x0 + 2.8, 1.1, z + 1.46), Vector3(x0 + 5.2, 1.5, z + 1.5), MatLib.flat(Color(0.75, 0.74, 0.7), 0.6, 0.4), "metal", false)


func _cyl(center: Vector3, r: float, length: float, mat: Material, segs := 32) -> void:
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = r
	cm.bottom_radius = r
	cm.height = length
	cm.radial_segments = segs
	cm.rings = 1
	mi.mesh = cm
	mi.material_override = mat
	mi.rotation = Vector3(0, 0, PI / 2)   # axis along X
	nav.add_child(mi)
	mi.position = center



## One interior reflection probe per room (updated once): metal weapons,
## robots and props reflect their actual surroundings instead of the sky.
func _reflection_probes() -> void:
	for name in Game.rooms:
		var aabb: AABB = Game.rooms[name].aabb
		var rp := ReflectionProbe.new()
		rp.update_mode = ReflectionProbe.UPDATE_ONCE
		rp.interior = true
		rp.box_projection = true
		rp.enable_shadows = false
		rp.size = Vector3(aabb.size.x, minf(aabb.size.y, 10.0), aabb.size.z)
		rp.ambient_mode = ReflectionProbe.AMBIENT_ENVIRONMENT
		rp.cull_mask = 1
		rp.max_distance = 40.0
		add_child(rp)
		var c := aabb.get_center()
		rp.global_position = Vector3(c.x, 1.7, c.z)
		rp.origin_offset = Vector3(0, c.y - 1.7, 0)
