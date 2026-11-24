class_name Expansion
extends RefCounted
## M4 facility expansion, joined to the M1-M3 substation:
##   PUMP STATION  x[-24,-6]  z[-30,-3]   two levels (north gallery), steam purge
##   TUNNEL        x[-6,6]    z[-30,-27]  corridor north end (D9) <-> pump (D9b)
##   CRAWLWAY      dock west wall -> pump station (crouch only; units cannot path)
##   SWITCHGEAR    x[32,50]   z[-30,-2]   transformer bays, east gallery, 2 main breakers
##   ANTECHAMBER   x[14,20]   z[-42,-38]  behind the blast door in the server room
##   RELAY CORE    x[12,32]   z[-62,-42]  the relay array and its capacitor stacks
## Geometry is collision-accurate boxes (navmesh source); hero props come from
## m4_kit.glb (Blender front -Y = Godot +Z) with primitive fallbacks.

const KIT := "res://assets/models/m4_kit.glb"
const ENV_KIT := "res://assets/models/env_kit.glb"
const GALLERY_Y := 4.2
const CRAWL_H := 1.25            # crawlway clear height (player crouch capsule is 1.15)
const DUCT_H := 1.15             # kit duct interior height (scaled up to CRAWL_H)
const BLAST_X := 15.5            # blast door opening centre (server-room north wall)

var b: LevelBuilder
var kit: Node3D
var env: Node3D   # M2 structural kit (ribs, beams, trays, pipes)
# Mission objects (read by Mission)
var lockdown_panel: M4Objects.HoldStation
var lockdown_label: Label3D
var lockdown_screen: MeshInstance3D
var breakers: Array = []
var capacitors: Array = []
var blast_door: M4Objects.BlastDoor
var steam_valve: M4Objects.SteamValve
var lift_panel: M4Objects.HoldStation
var caches: Array = []   # M4Objects.AmmoCache, in mission order
var core_center := Vector3(22.0, 0.0, -52.0)
var core_glow: OmniLight3D
var core_array: Node3D
var emergency_lights: Array = []   # [OmniLight3D, MeshInstance3D]
var alarm_points: Array = [Vector3(20.0, 6.0, -14.0), Vector3(7.5, 3.0, -15.0), Vector3(15.0, 3.0, -32.0), Vector3(41.0, 7.0, -16.0), Vector3(-15.0, 6.0, -16.0), Vector3(8.0, 4.5, 7.0)]


func _init(builder: LevelBuilder) -> void:
	b = builder
	if ResourceLoader.exists(KIT):
		kit = (load(KIT) as PackedScene).instantiate()
	if ResourceLoader.exists(ENV_KIT):
		env = (load(ENV_KIT) as PackedScene).instantiate()


func build() -> void:
	_rooms()
	_slabs()
	_pump_station()
	_tunnel_and_crawl()
	_switchgear()
	_core()
	_office_panel()
	_lift_panel()
	_ammo_caches()
	_structure()
	if kit:
		kit.free()   # out-of-tree templates must not outlive the level
		kit = null
	if env:
		env.free()
		env = null


# ------------------------------------------------------------------ helpers
func has_kit(name: String) -> bool:
	return kit != null and kit.get_node_or_null(name) != null


func kp(name: String, pos: Vector3, yaw := 0.0, collide := false, cover := false, parent: Node3D = null, scl := Vector3.ONE) -> Node3D:
	if kit == null:
		return null
	var src: Node3D = kit.get_node_or_null(name)
	if src == null:
		push_warning("m4 kit piece missing: " + name)
		return null
	var inst: Node3D = src.duplicate()
	var p: Node3D = parent if parent else (b.nav if collide else b)
	p.add_child(inst)
	inst.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(yaw)).scaled(scl), pos)
	MatLib.remap_scene(inst)
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		if mi.get_aabb().size.length() < 0.4:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.visibility_range_end = 30.0
	if collide:
		var aabb := b._world_aabb(inst)
		var sb := StaticBody3D.new()
		sb.collision_layer = 1
		sb.collision_mask = 0
		sb.set_meta("surface", "metal")
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = aabb.size
		cs.shape = bs
		sb.add_child(cs)
		b.nav.add_child(sb)
		sb.global_position = aabb.get_center()
		if cover:
			b.cover_props.append(aabb)
	return inst


func ek(name: String, pos: Vector3, yaw: float, scl := Vector3.ONE) -> void:
	if env == null or env.get_node_or_null(name) == null:
		return
	var inst: Node3D = env.get_node(name).duplicate()
	b.add_child(inst)
	inst.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(yaw)).scaled(scl), pos)
	MatLib.remap_scene(inst)
	if name != "wall_rib_9":
		for mi in inst.find_children("*", "MeshInstance3D", true, false):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


## Pilasters every 4 m (skipping openings and fixtures): the same structural
## rhythm as the M1-M3 halls. `gaps` keys n/s/w/e select the walls.
func _ribs(x0: float, z0: float, x1: float, z1: float, h: float, gaps: Dictionary) -> void:
	var s := Vector3(1.0, h / 9.0, 1.0)
	if gaps.has("n"):
		for x in Dressing.spaced(x0, x1, 4.0, gaps.n):
			ek("wall_rib_9", Vector3(x, 0, z0), 0.0, s)
	if gaps.has("s"):
		for x in Dressing.spaced(x0, x1, 4.0, gaps.s):
			ek("wall_rib_9", Vector3(x, 0, z1), 180.0, s)
	if gaps.has("w"):
		for z in Dressing.spaced(z0, z1, 4.0, gaps.w):
			ek("wall_rib_9", Vector3(x0, 0, z), 90.0, s)
	if gaps.has("e"):
		for z in Dressing.spaced(z0, z1, 4.0, gaps.e):
			ek("wall_rib_9", Vector3(x1, 0, z), -90.0, s)


func _structure() -> void:
	# Pump station (no ribs behind the gallery, the stair or the wall fixtures)
	_ribs(-23.85, -29.85, -6.15, -3.15, 9.0, {
		"w": [[-29.9, -18.4], [-13.3, -10.7], [-15.9, -15.1], [-4.9, -3.9]],
		"s": [[-11.2, -8.8]],
		"e": [[-29.9, -27.4], [-22.6, -21.4], [-19.8, -17.2], [-7.9, -6.1], [-9.9, -9.3]]})
	for z in [-9.0, -15.0, -21.0]:
		for x in [-21.0, -17.0, -13.0, -9.0]:
			ek("ibeam_4", Vector3(x, 8.83, z), 0.0)
	for x in [-20.0, -16.0, -12.0, -8.0]:
		ek("pipe_bundle_4", Vector3(x, 6.6, -29.85), 0.0)
	# Switchgear hall (the gallery runs along the east wall: no ribs there)
	_ribs(32.15, -29.85, 49.85, -2.15, 10.0, {
		"n": [[47.4, 50.0], [33.0, 34.5]],
		"s": [[40.2, 41.8], [46.0, 50.0]],
		"w": [[-30.0, -25.6], [-19.0, -17.0], [-7.6, -6.4], [-21.9, -21.1]]})
	for z in [-4.5, -11.0, -15.5, -23.0, -27.5]:
		for x in [34.0, 38.0, 42.0, 46.0]:
			ek("ibeam_4", Vector3(x, 9.83, z), 0.0)
	for x in [36.0, 40.0, 44.0]:
		ek("cable_tray_4", Vector3(x, 6.4, -12.5), 0.0)
		if env != null and env.get_node_or_null("cable_tray_4") != null:
			b.drop_rods(Vector3(x, 6.4, -12.5), 0.0, 1.0, 10.0)
		ek("pipe_bundle_4", Vector3(x, 7.2, -2.42), 180.0)   # stands off the ribs
	# Relay core
	_ribs(12.15, -61.85, 31.85, -42.15, 12.0, {
		"n": [[20.0, 24.0]],
		"s": [[13.9, 20.1]],
		"w": [[-52.6, -51.4]],
		"e": [[-52.6, -51.4]]})
	for z in [-48.5, -55.5]:
		for x in [14.0, 18.0, 22.0, 26.0, 30.0]:
			ek("ibeam_4", Vector3(x, 11.83, z), 0.0)
	# Service tunnel
	for x in [-2.0, 2.0]:
		ek("pipe_bundle_4", Vector3(x, 2.3, -29.85), 0.0)
		ek("cable_tray_4", Vector3(x, 2.75, -27.55), 0.0)


func _yaw_of(dir: Vector3) -> float:
	return rad_to_deg(atan2(dir.x, dir.z))


## Walkable ramp collider from a (bottom) to c (top), width w; top face on
## a-c. Handrail-height side walls make the stair enterable only at its ends
## (units otherwise tried to step onto the ramp from the side).
func ramp(a: Vector3, c: Vector3, w: float, sides := true) -> void:
	_slanted(a, c, Vector3(w, 0.12, (c - a).length()), Vector3(0, -0.06, 0))
	if sides:
		for sx in [-1.0, 1.0]:
			_slanted(a, c, Vector3(0.08, 1.0, (c - a).length()), Vector3(sx * (w * 0.5 + 0.04), 0.5, 0))


func _slanted(a: Vector3, c: Vector3, size: Vector3, local_off: Vector3) -> void:
	var sb := StaticBody3D.new()
	sb.collision_layer = 1
	sb.collision_mask = 0
	sb.set_meta("surface", "metal")
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	sb.add_child(cs)
	b.nav.add_child(sb)
	sb.global_position = (a + c) * 0.5
	sb.look_at(sb.global_position + (c - a), Vector3.UP)
	sb.global_position += sb.global_transform.basis * local_off


## Visible stair when the kit piece is missing: treads along the ramp line.
func fallback_stair(a: Vector3, c: Vector3, w: float) -> void:
	var n := int(round((c.y - a.y) / 0.21))
	var steel := MatLib.diamond_plate()
	for i in n:
		var p0 := a.lerp(c, float(i) / n)
		var p1 := a.lerp(c, float(i + 1) / n)
		b.box(Vector3(p0.x - w * 0.5, p1.y - 0.05, minf(p0.z, p1.z)), Vector3(p0.x + w * 0.5, p1.y, maxf(p0.z, p1.z)), steel, "metal", false)


func catwalk(lo: Vector3, hi: Vector3) -> void:
	# Deck collider (top at GALLERY_Y) + kit grating, else a visible plate.
	var deck := b.box(Vector3(lo.x, GALLERY_Y - 0.1, lo.z), Vector3(hi.x, GALLERY_Y, hi.z), MatLib.diamond_plate(), "metal")
	var dx := hi.x - lo.x
	var dz := hi.z - lo.z
	var along_x := dx >= dz
	var length := dx if along_x else dz
	var width := dz if along_x else dx
	if has_kit("catwalk_4"):
		deck.visible = false
		var n := maxi(1, int(round(length / 4.0)))
		for i in n:
			var t := (i + 0.5) / n
			var c := Vector3(lerpf(lo.x, hi.x, t) if along_x else (lo.x + hi.x) * 0.5, GALLERY_Y, (lo.z + hi.z) * 0.5 if along_x else lerpf(lo.z, hi.z, t))
			kp("catwalk_4", c, 0.0 if along_x else 90.0, false, false, null, Vector3(length / (4.0 * n), 1.0, width / 2.0))
	else:
		var dark := MatLib.flat(Color(0.1, 0.1, 0.11), 0.85, 0.45)
		if along_x:
			b.box(Vector3(lo.x, GALLERY_Y - 0.3, lo.z), Vector3(hi.x, GALLERY_Y - 0.1, lo.z + 0.12), dark, "metal", false)
			b.box(Vector3(lo.x, GALLERY_Y - 0.3, hi.z - 0.12), Vector3(hi.x, GALLERY_Y - 0.1, hi.z), dark, "metal", false)
		else:
			b.box(Vector3(lo.x, GALLERY_Y - 0.3, lo.z), Vector3(lo.x + 0.12, GALLERY_Y - 0.1, hi.z), dark, "metal", false)
			b.box(Vector3(hi.x - 0.12, GALLERY_Y - 0.3, lo.z), Vector3(hi.x, GALLERY_Y - 0.1, hi.z), dark, "metal", false)


## Safety railing along a straight edge at gallery height. `walk` points to
## the walkway side (the kit's toe board faces it).
func railing(a: Vector3, c: Vector3, walk: Vector3) -> void:
	var lo := Vector3(minf(a.x, c.x) - 0.03, GALLERY_Y, minf(a.z, c.z) - 0.03)
	var hi := Vector3(maxf(a.x, c.x) + 0.03, GALLERY_Y + 1.1, maxf(a.z, c.z) + 0.03)
	var col := b.box(lo, hi, MatLib.flat(Color(0.7, 0.55, 0.06), 0.4, 0.5), "metal")
	if not has_kit("catwalk_rail_4"):
		return
	col.visible = false
	var along_x := absf(c.x - a.x) > absf(c.z - a.z)
	var length := absf(c.x - a.x) if along_x else absf(c.z - a.z)
	var n := maxi(1, int(round(length / 4.0)))
	for i in n:
		var p := a.lerp(c, (i + 0.5) / n)
		kp("catwalk_rail_4", Vector3(p.x, GALLERY_Y, p.z), _yaw_of(walk), false, false, null, Vector3(length / (4.0 * n), 1.0, 1.0))


func light_room(room: String, pts: Array, color: Color, energy: float, rng: float, angle: float, fog := 1.4, also_shadowed := []) -> void:
	for i in pts.size():
		var l := b.light_spot(pts[i], color, energy, rng, angle, i % 2 == 0 or i in also_shadowed, room, Vector3.DOWN, "highbay")
		l.light_volumetric_fog_energy = fog


## Bulkhead lamp on a wall bracket: the lamp hangs from a short steel arm and
## plate instead of floating in front of the wall. `n` points into the room.
func wall_lamp(wall_pt: Vector3, n: Vector3, color: Color, energy: float, rng: float, room: String, shadow := false) -> void:
	var pos := wall_pt + n * 0.24
	var lo := b.light_omni(pos, color, energy, rng, shadow, room)
	lo.omni_shadow_mode = OmniLight3D.SHADOW_DUAL_PARABOLOID
	var steel := MatLib.flat(Color(0.13, 0.135, 0.14), 0.8, 0.45)
	var t := Vector3(-n.z, 0, n.x)
	var top := pos.y + 0.12
	b.box(wall_pt + Vector3(0, top, 0) - Vector3(0, pos.y, 0) - t * 0.02, pos + Vector3(0, 0.16, 0) + n * 0.03 + t * 0.02, steel, "metal", false, null, false)
	b.box(wall_pt + Vector3(0, top - pos.y - 0.08, 0) - t * 0.06, wall_pt + Vector3(0, top - pos.y + 0.1, 0) + t * 0.06 + n * 0.02, steel, "metal", false, null, false)


## A straight brace between two points (visual only).
func _brace(a: Vector3, c: Vector3, w: float, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(w, w, a.distance_to(c))
	mi.mesh = bm
	mi.material_override = mat
	b.add_child(mi)
	mi.transform = Transform3D(Basis.looking_at((c - a).normalized(), Vector3.UP), (a + c) * 0.5)


## Red emergency beacon: dark until Mission switches emergency lighting on.
func emergency(pos: Vector3) -> void:
	var l := OmniLight3D.new()
	l.light_color = Color(1.0, 0.1, 0.04)
	l.light_energy = 0.0
	l.omni_range = 9.0
	l.omni_attenuation = 1.2
	l.shadow_enabled = false
	l.light_volumetric_fog_energy = 1.5
	l.visible = false
	b.add_child(l)
	l.position = pos
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.07
	cm.bottom_radius = 0.09
	cm.height = 0.16
	mi.mesh = cm
	mi.material_override = MatLib.flat(Color(0.35, 0.05, 0.03), 0.0, 0.4)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	b.add_child(mi)
	mi.position = pos + Vector3(0, 0.1, 0)
	emergency_lights.append([l, mi])


func _station_box(parent: Node3D, size: Vector3, offset: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	mi.position = offset
	parent.add_child(mi)
	return mi


func _station(prompt: String, hold: float, pos: Vector3, yaw: float, size: Vector3, offset: Vector3, parent: Node3D = null) -> M4Objects.HoldStation:
	var h := M4Objects.HoldStation.new()
	h.prompt = prompt
	h.hold_time = hold
	(parent if parent else b.dyn).add_child(h)
	h.global_position = pos
	h.rotation.y = deg_to_rad(yaw)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	cs.position = offset
	h.add_child(cs)
	return h


func _hidden_collider(lo: Vector3, hi: Vector3) -> void:
	b.box(lo, hi, MatLib.flat(Color(0, 0, 0)), "metal").visible = false


# ------------------------------------------------------------------ rooms
func _rooms() -> void:
	Game.add_room("pump", AABB(Vector3(-24, -1, -30), Vector3(18, 11, 27)))
	Game.add_room("tunnel", AABB(Vector3(-6, -1, -30), Vector3(12, 5, 3)))
	Game.add_room("crawl", AABB(Vector3(-11.2, -1, -3), Vector3(11.2, 3, 6.2)))
	Game.add_room("switchgear", AABB(Vector3(32.1, -1, -30), Vector3(18, 12, 28)))
	Game.add_room("antechamber", AABB(Vector3(14, -1, -42), Vector3(6, 5, 4)))
	Game.add_room("core", AABB(Vector3(12, -1, -62), Vector3(20, 14, 20)))


func _slabs() -> void:
	var f := MatLib.floor_concrete()
	# The M1 base slab covers x[-7,34] z[-41,15]; these do not overlap it. The
	# pump slab leaves a trench for the covered water channel (z -8.7..-7.3).
	b.box(Vector3(-25, -0.4, -31), Vector3(-7, 0, -8.7), f, "concrete")
	b.box(Vector3(-25, -0.4, -7.3), Vector3(-7, 0, 4), f, "concrete")
	b.box(Vector3(-25, -0.4, -8.7), Vector3(-23, 0, -7.3), f, "concrete")
	b.box(Vector3(34, -0.4, -31), Vector3(51, 0, -1), f, "concrete")
	b.box(Vector3(11, -0.4, -63), Vector3(33, 0, -41), f, "concrete")


# ------------------------------------------------------------------ pump station
func _pump_station() -> void:
	var H := 9.3
	var pf := MatLib.pbr("concrete_floor_painted", 0.35, Color(0.6, 0.66, 0.68), 0.0, 1.0, "pump_floor")
	b.floor_overlay(-23.85, -29.85, -6.15, -8.7, pf)
	b.floor_overlay(-23.85, -7.3, -6.15, -3.15, pf)
	b.floor_overlay(-23.85, -8.7, -23.0, -7.3, pf)
	b.floor_overlay(-7.0, -8.7, -6.15, -7.3, pf)
	b.wall_x(-30, -24, -6, H)
	b.wall_z(-24, -30, -3, H)
	b.wall_x(-3, -24, -6, H, [[-10.95, -9.05, CRAWL_H]])                   # crawlway mouth
	b.wall_z(-6, -30, -13, H, [[-29.25, -27.75, 2.2]])                      # tunnel door D9b
	b.box(Vector3(-6.15, 3.9, -13), Vector3(-5.85, H, -3), MatLib.wall_concrete())   # above the office wall
	b.ceiling(-24, -30, -6, -3, 9.0)
	b.make_door("D9b", Vector3(-6, 0, -29.21), false)
	b.make_door("D8", Vector3(-6, 0, -7.71), false)                          # security office (opening in LevelBuilder._shell)
	# North gallery + landing; the stair rises along the west wall.
	catwalk(Vector3(-23.85, 0, -29.85), Vector3(-6.15, 0, -27.8))
	catwalk(Vector3(-23.85, 0, -27.8), Vector3(-22.0, 0, -26.0))
	railing(Vector3(-22.0, 0, -27.8), Vector3(-6.2, 0, -27.8), Vector3(0, 0, -1))
	railing(Vector3(-22.0, 0, -27.8), Vector3(-22.0, 0, -26.05), Vector3(-1, 0, 0))
	railing(Vector3(-22.35, 0, -26.0), Vector3(-22.0, 0, -26.0), Vector3(0, 0, -1))
	var s_bot := Vector3(-23.1, 0.0, -19.0)   # handrails (x +-0.72) clear of the west wall
	var s_top := Vector3(-23.1, GALLERY_Y, -26.0)
	ramp(s_bot, s_top, 1.2)
	if kp("stair_flight", s_bot, 0.0) == null:
		fallback_stair(s_bot, s_top, 1.2)
	# Three cooling pumps on skids, motors north (hard cover block).
	for x in [-16.5, -14.0, -11.5]:
		if kp("cooling_pump", Vector3(x, 0, -17.0), 90.0, true, true) == null:
			b._cyl(Vector3(x, 1.0, -17.0), 0.7, 1.4, MatLib.machinery(), 32)
			b.box(Vector3(x - 0.7, 0, -19.3), Vector3(x + 0.7, 2.0, -14.7), MatLib.machinery(), "metal").visible = false
			b.cover_props.append(AABB(Vector3(x - 0.7, 0, -19.3), Vector3(1.4, 2.0, 4.6)))
	# Header pipe along the south side: drops into the floor (half cover).
	kp("pipe_manifold_8", Vector3(-16.0, 1.6, -5.0), 0.0, true, true)
	# Its hanger rods end in beam clamps at 2.87 m: carry them on two
	# cantilever channels with knee braces from the south wall.
	if has_kit("pipe_manifold_8"):
		for ex in [-20.006, -11.994]:
			var cap := MeshInstance3D.new()
			var capm := CylinderMesh.new()
			capm.top_radius = 0.355
			capm.bottom_radius = 0.355
			capm.height = 0.012
			capm.radial_segments = 32
			cap.mesh = capm
			cap.material_override = MatLib.flat(Color(0.52, 0.54, 0.55), 0.45, 0.5)
			b.add_child(cap)
			cap.position = Vector3(ex, 1.6, -5.0)
			cap.rotation = Vector3(0, 0, PI / 2)
		var chan := MatLib.flat(Color(0.16, 0.17, 0.18), 0.75, 0.5)
		for hx in [-17.25, -14.75]:
			b.box(Vector3(hx - 0.05, 2.87, -5.42), Vector3(hx + 0.05, 2.99, -3.15), chan, "metal", false, null, false)
			b.box(Vector3(hx - 0.09, 2.2, -3.17), Vector3(hx + 0.09, 3.06, -3.15), chan, "metal", false, null, false)
			_brace(Vector3(hx, 2.3, -3.17), Vector3(hx, 2.88, -4.3), 0.06, chan)
	# Covered water channel (walkable grating over the trench)
	for x in [-21.0, -17.0, -13.0, -9.0]:
		kp("water_channel_4", Vector3(x, 0.0, -8.0), 0.0)
	_hidden_collider(Vector3(-23.0, -0.06, -8.7), Vector3(-7.0, 0.0, -7.3))
	if not has_kit("water_channel_4"):
		b.box(Vector3(-23.0, -0.5, -8.7), Vector3(-7.0, -0.06, -7.3), MatLib.flat(Color(0.05, 0.07, 0.08), 0.2, 0.08), "concrete", false)
		b.box(Vector3(-23.0, -0.02, -8.7), Vector3(-7.0, 0.0, -7.3), MatLib.diamond_plate(), "metal", false)
	kp("pump_control_panel", Vector3(-6.45, 0, -22.0), -90.0, true, true)
	kp("valve_wheel_station", Vector3(-23.85, 1.4, -12.0), 90.0, true)
	# Cover on the gallery and the floor
	b.prop("crate", Vector3(-6.95, GALLERY_Y, -29.2), 0, true)   # dead-end cover; keeps the gallery walkable
	b.prop("crate", Vector3(-20.5, 0, -11.0), 15, true)
	b.prop("barrier", Vector3(-11.5, 0, -24.5), 0, true, "concrete")
	b.prop("barrel", Vector3(-7.0, 0, -12.5), 0, true)
	b.prop("locker", Vector3(-23.6, 0, -4.4), 90, false)
	# Steam purge valve: a tactical option that blinds the units in this hall.
	steam_valve = M4Objects.SteamValve.new()
	steam_valve.prompt = "[HOLD F] STEAM PURGE - BLINDS UNITS IN THE PUMP HALL"
	steam_valve.hold_time = 1.2
	steam_valve.once = false
	steam_valve.room = "pump"
	steam_valve.center = Vector3(-15.0, 0, -16.5)
	b.nav.add_child(steam_valve)   # protrudes 0.9 m: part of the navmesh source
	steam_valve.global_position = Vector3(-6.15, 0.0, -18.5)
	steam_valve.rotation.y = deg_to_rad(-90.0)
	var vcs := CollisionShape3D.new()
	var vbs := BoxShape3D.new()
	vbs.size = Vector3(1.6, 0.9, 0.95)
	vcs.shape = vbs
	vcs.position = Vector3(0, 1.4, 0.47)
	steam_valve.add_child(vcs)
	if kp("valve_wheel_station", Vector3(0, 1.4, 0), 0.0, false, false, steam_valve) == null:
		_station_box(steam_valve, Vector3(0.6, 0.6, 0.2), Vector3(0, 1.4, 0.1), MatLib.flat(Color(0.55, 0.1, 0.06), 0.5, 0.5))
	var fv := FogVolume.new()
	fv.size = Vector3(17.6, 7.0, 26.5)
	var fm := FogMaterial.new()
	fm.density = 0.0
	fm.albedo = Color(0.85, 0.87, 0.88)
	fm.edge_fade = 0.25
	fv.material = fm
	b.add_child(fv)
	fv.global_position = Vector3(-15.0, 3.5, -16.5)
	fv.visible = false
	steam_valve.volume = fv
	steam_valve.done.connect(_on_steam)
	# Lighting: sodium high bays, gallery lamps, cold bounce off the water.
	light_room("pump", [Vector3(-19, 8.4, -8), Vector3(-11, 8.4, -8), Vector3(-19, 8.4, -16), Vector3(-11, 8.4, -16), Vector3(-19, 8.4, -23), Vector3(-11, 8.4, -23)], Color(1.0, 0.8, 0.6), 17.0, 14.0, 54)
	for p in [Vector3(-23.5, 3.2, -8.0), Vector3(-23.5, 3.2, -16.8), Vector3(-6.5, 3.2, -11.0), Vector3(-6.5, 3.2, -24.5)]:
		b.light_omni(p, Color(1.0, 0.84, 0.62), 1.3, 7.5, false, "pump")
	for x in [-20.0, -14.0, -8.0]:
		b.light_omni(Vector3(x, GALLERY_Y + 2.4, -29.4), Color(1.0, 0.86, 0.7), 1.6, 6.0, false, "pump")
	b.light_omni(Vector3(-15.0, 0.8, -8.0), Color(0.4, 0.6, 0.75), 0.7, 8.0, false, "pump", false)
	emergency(Vector3(-6.5, 2.6, -26.5))
	emergency(Vector3(-23.5, 2.6, -14.0))
	emergency(Vector3(-15.0, GALLERY_Y + 2.6, -29.6))
	b.breaker("pump", Vector3(-23.75, 1.5, -15.5), 90)
	b.place_sign("PUMP STATION 2 - COOLING WATER", Vector3(-15.0, 7.2, -29.83), 0, 90, Color(0.82, 0.8, 0.74), 0.006)
	b.place_sign("CAUTION: SCALDING STEAM", Vector3(-6.17, 2.5, -18.5), -90, 30, Color(0.9, 0.75, 0.2))
	b.place_sign("SECURITY", Vector3(-6.17, 2.6, -9.6), -90, 36)
	b.terminal(Vector3(-21.0, GALLERY_Y + 1.3, -29.78), 180, "PUMP LOG", PackedStringArray([
		"PUMP 2-B: flow loss since the relay sync fault.",
		"Night shift sealed the office and left through the crawlway.",
		"If units come in, purge steam from the valve by the east door."]))


func _on_steam() -> void:
	Game.obscure_room("pump", 22.0)
	steam_valve.cooldown = 45.0
	Sfx.play_3d("robot_hydraulic_hiss" if ResourceLoader.exists("res://assets/audio/robot_hydraulic_hiss_0.wav") else "door_breach", steam_valve.global_position + Vector3.UP * 1.4, 6.0, 0.0, 14.0)
	Game.emit_noise(steam_valve.global_position, 14.0, Game.player)
	Game.say("STEAM PURGE: pump hall visibility near zero for about 20 s", 3.0)


func _tunnel_and_crawl() -> void:
	# Service tunnel: corridor north end (D9) <-> pump station (D9b)
	b.floor_overlay(-5.85, -29.85, 5.85, -27.15, MatLib.diamond_plate())
	b.wall_x(-30, -6, 6, 3.6)
	b.wall_x(-27, -6, 6, 3.6)
	b.ceiling(-6, -30, 6, -27, 3.3)
	b.make_door("D9", Vector3(6, 0, -29.21), false)
	for x in [-3.0, 2.5]:
		b.light_omni(Vector3(x, 2.95, -28.5), Color(1.0, 0.86, 0.7), 1.4, 5.0, false, "tunnel")
	emergency(Vector3(0.0, 2.7, -27.3))
	b.place_sign("SERVICE TUNNEL S-2 / PUMP STN", Vector3(6.17, 2.75, -28.5), 90, 32)
	b.prop("crate", Vector3(-1.5, 0, -29.3), 0, true)
	# Crawlway: dock west wall -> pump station. 1.25 m clear: crouch only, and
	# too low for the navmesh, so units cannot follow.
	var low := MatLib.flat(Color(0.2, 0.21, 0.22), 0.6, 0.6)
	var kit_duct := has_kit("crawl_duct_2")
	var walls := [
		# [lo, hi, covered by a kit duct section]
		[Vector3(-9.05, 0, 0.8), Vector3(0.0, CRAWL_H, 1.05), true],        # E-W leg, south wall
		[Vector3(-8.0, 0, 2.95), Vector3(0.0, CRAWL_H, 3.2), true],         # E-W leg, north wall
		[Vector3(-11.2, 0, 2.95), Vector3(-8.0, CRAWL_H, 3.2), false],      # corner, north wall
		[Vector3(-11.2, 0, 1.05), Vector3(-10.95, CRAWL_H, 3.2), false],    # corner, west wall
		[Vector3(-9.05, 0, 0.8), Vector3(-8.0, CRAWL_H, 1.05), false],      # corner, south wall stub
		[Vector3(-11.2, 0, -2.85), Vector3(-10.95, CRAWL_H, 1.05), true],   # N-S leg, west wall
		[Vector3(-9.05, 0, -2.85), Vector3(-8.8, CRAWL_H, 0.8), true],      # N-S leg, east wall
		[Vector3(-8.0, CRAWL_H, 0.8), Vector3(0.0, CRAWL_H + 0.3, 3.2), true],       # E-W ceiling
		[Vector3(-11.2, CRAWL_H, 0.8), Vector3(-8.0, CRAWL_H + 0.3, 3.2), false],    # corner ceiling
		[Vector3(-11.2, CRAWL_H, -2.85), Vector3(-8.8, CRAWL_H + 0.3, 0.8), true],   # N-S ceiling
	]
	for w in walls:
		var mi := b.box(w[0], w[1], low, "metal")
		if kit_duct and w[2]:
			mi.visible = false
	b.floor_overlay(-11.0, 1.05, 0.0, 2.95, MatLib.diamond_plate())
	b.floor_overlay(-10.95, -2.85, -9.05, 1.05, MatLib.diamond_plate())
	if kit_duct:
		var s := Vector3(1.0, CRAWL_H / DUCT_H, 1.0)
		for i in 4:
			kp("crawl_duct_2", Vector3(-i * 2.0, 0, 2.0), 90.0, false, false, null, s)
		for i in 2:
			kp("crawl_duct_2", Vector3(-10.0, 0, 1.05 - i * 2.0), 0.0, false, false, null, s)
		# Dark cavity behind the slatted duct walls (visual only)
		var cav := MatLib.flat(Color(0.05, 0.05, 0.055), 0.0, 0.9)
		b.box(Vector3(-8.0, 0, 0.5), Vector3(0.0, 1.6, 0.7), cav, "concrete", false)
		b.box(Vector3(-8.0, 0, 3.3), Vector3(0.0, 1.6, 3.5), cav, "concrete", false)
		b.box(Vector3(-8.0, 1.5, 0.5), Vector3(0.0, 1.7, 3.5), cav, "concrete", false)
		b.box(Vector3(-11.5, 0, -2.85), Vector3(-11.3, 1.6, 0.8), cav, "concrete", false)
		b.box(Vector3(-8.7, 0, -2.85), Vector3(-8.5, 1.6, 0.5), cav, "concrete", false)
		b.box(Vector3(-11.5, 1.5, -2.85), Vector3(-8.5, 1.7, 0.8), cav, "concrete", false)
	for p in [Vector3(-4.0, 1.0, 2.0), Vector3(-10.0, 1.0, 2.0), Vector3(-10.0, 1.0, -1.5)]:
		b.light_omni(p, Color(1.0, 0.8, 0.55), 0.2, 2.8, false, "crawl", false)
	b.place_sign("MAINTENANCE CRAWLWAY - PUMP STN", Vector3(0.17, 1.62, 2.0), 90, 30, Color(0.9, 0.75, 0.2), 0.0035)


# ------------------------------------------------------------------ switchgear hall
func _switchgear() -> void:
	var H := 10.3
	b.floor_overlay(32.15, -25.85, 49.85, -2.15, MatLib.floor_epoxy())
	b.floor_overlay(33.15, -29.85, 49.85, -25.85, MatLib.floor_epoxy())
	b.wall_x(-30, 33, 50, H)
	b.wall_z(50, -30, -2, H)
	b.wall_x(-2, 32, 50, H)
	b.box(Vector3(31.85, 9.3, -26.15), Vector3(32.15, H, -2), MatLib.wall_concrete())    # above the hall east wall
	b.box(Vector3(32.85, 4.8, -30), Vector3(33.15, H, -26), MatLib.wall_concrete())      # above the control east wall
	b.ceiling(32, -30, 50, -2, 10.0)
	b.make_door("D10", Vector3(32, 0, -18.71), false)
	b.make_door("D11", Vector3(33, 0, -28.71), false)
	# Transformer bays along the north wall: the landmark and hard cover.
	for x in [39.6, 44.2]:
		if kp("transformer_unit", Vector3(x, 0, -27.3), 0.0, true, true) == null:
			b.box(Vector3(x - 1.9, 0, -28.5), Vector3(x + 1.95, 4.2, -26.1), MatLib.rust_panel(), "metal")
			b.cover_props.append(AABB(Vector3(x - 1.9, 0, -28.5), Vector3(3.85, 4.2, 2.4)))
		kp("hv_cage_4", Vector3(x, 0, -24.9), 0.0, true)
	# Switchgear line-ups: two facing rows form an aisle (cover both ways).
	for x in [36.5, 40.5]:
		for row in [[-15.0, 0.0], [-10.0, 180.0]]:
			if has_kit("switchgear_lineup_4"):
				_lineup_rear(x, row[0] + (-0.6 if row[1] == 0.0 else 0.6), -1.0 if row[1] == 0.0 else 1.0, "AB"[0 if x < 38.0 else 1] + ("1" if row[1] == 0.0 else "2"))
			if kp("switchgear_lineup_4", Vector3(x, 0, row[0]), row[1], true, true) == null:
				b.box(Vector3(x - 2.0, 0, row[0] - 0.6), Vector3(x + 2.0, 2.3, row[0] + 0.6), MatLib.machinery(), "metal")
				b.cover_props.append(AABB(Vector3(x - 2.0, 0, row[0] - 0.6), Vector3(4.0, 2.3, 1.2)))
	b.prop("barrier", Vector3(44.5, 0, -19.0), 90, true, "concrete")
	b.prop("crate", Vector3(36.0, 0, -5.0), 0, true)
	b.prop("crate", Vector3(36.0, 0.8, -5.0), 12, false)
	b.prop("crate", Vector3(44.0, 0, -6.5), 30, true)
	# East gallery + landing; the stair rises north from the south end.
	catwalk(Vector3(48.0, 0, -29.85), Vector3(49.85, 0, -4.0))
	catwalk(Vector3(46.6, 0, -14.0), Vector3(48.0, 0, -12.0))
	railing(Vector3(48.0, 0, -29.8), Vector3(48.0, 0, -14.0), Vector3(1, 0, 0))
	railing(Vector3(48.0, 0, -12.0), Vector3(48.0, 0, -4.05), Vector3(1, 0, 0))
	railing(Vector3(46.6, 0, -14.0), Vector3(48.0, 0, -14.0), Vector3(0, 0, 1))
	railing(Vector3(46.6, 0, -14.0), Vector3(46.6, 0, -12.6), Vector3(1, 0, 0))
	railing(Vector3(48.0, 0, -4.0), Vector3(49.8, 0, -4.0), Vector3(0, 0, -1))
	var s_bot := Vector3(47.2, 0.0, -5.0)
	var s_top := Vector3(47.2, GALLERY_Y, -12.0)
	ramp(s_bot, s_top, 1.2)
	if kp("stair_flight", s_bot, 0.0) == null:
		fallback_stair(s_bot, s_top, 1.2)
	b.prop("crate", Vector3(49.1, GALLERY_Y, -25.5), 90, true)
	# Main breakers: A on the floor by the south wall, B up on the gallery.
	breakers.append(_breaker_station(Vector3(41.0, 0.0, -2.15), 180.0, "A"))
	breakers.append(_breaker_station(Vector3(49.85, GALLERY_Y, -20.0), -90.0, "B"))
	# Lights: cool high bays, amber beacons over the transformers.
	light_room("switchgear", [Vector3(37, 9.4, -8), Vector3(44, 9.4, -8), Vector3(37, 9.4, -19), Vector3(44, 9.4, -19)], Color(0.85, 0.9, 1.0), 15.0, 14.0, 46)
	for x in [39.6, 44.2]:
		b.light_omni(Vector3(x, 5.0, -25.6), Color(1.0, 0.55, 0.15), 0.9, 4.0, false, "switchgear", false)
	b.light_omni(Vector3(49.0, GALLERY_Y + 2.5, -16.0), Color(1.0, 0.86, 0.7), 1.2, 6.0, false, "switchgear")
	emergency(Vector3(32.6, 2.8, -16.0))
	emergency(Vector3(49.6, 2.8, -5.0))
	emergency(Vector3(40.5, 3.0, -12.5))
	b.breaker("switchgear", Vector3(32.25, 1.5, -21.5), 90)
	b.place_sign("SWITCHGEAR HALL 9-B / 132 kV", Vector3(41.0, 7.5, -2.17), 180, 96, Color(0.82, 0.8, 0.74), 0.006)
	b.place_sign("DANGER - HIGH VOLTAGE", Vector3(42.0, 5.6, -29.83), 0, 60, Color(0.95, 0.8, 0.2), 0.005)
	b.terminal(Vector3(32.19, 1.3, -7.0), -90, "GRID LOG", PackedStringArray([
		"Relay Nine opened both main breakers at 22:09.",
		"Relay control is on battery: no power, no uplink.",
		"Breaker A by the south wall, B up on the east gallery."]))


## Rear face of a 4 m switchgear line-up (the kit back is a plain louvred
## sheet that read as a blockout): cubicle doors, handles, plinth, IDs, warnings.
func _lineup_rear(x: float, zb: float, s: float, id: String) -> void:
	var dark := MatLib.flat(Color(0.05, 0.055, 0.06), 0.5, 0.5)
	var plate := MatLib.flat(Color(0.85, 0.66, 0.08), 0.1, 0.55)
	var z0 := zb + s * 0.001
	b.box(Vector3(x - 2.0, 0.0, z0), Vector3(x + 2.0, 0.1, zb + s * 0.012), dark, "metal", false, null, false)
	for k in 5:
		var cx := x - 1.6 + k * 0.8
		if k > 0:
			b.box(Vector3(cx - 0.41, 0.1, z0), Vector3(cx - 0.39, 2.25, zb + s * 0.009), dark, "metal", false, null, false)
		b.box(Vector3(cx + 0.27, 1.05, z0), Vector3(cx + 0.3, 1.25, zb + s * 0.03), dark, "metal", false, null, false)
		b.box(Vector3(cx - 0.08, 1.52, z0), Vector3(cx + 0.08, 1.66, zb + s * 0.004), plate, "metal", false, null, false)
		var w := b.place_sign("DANGER\n11 kV", Vector3(cx, 1.59, zb + s * 0.006), 0.0 if s > 0 else 180.0, 14, Color(0.08, 0.06, 0.02), 0.0028)
		b.place_sign("SG-%s-%d  REAR" % [id, k + 1], Vector3(cx, 2.08, zb + s * 0.006), 0.0 if s > 0 else 180.0, 16, Color(0.75, 0.76, 0.74), 0.0028)


func _breaker_station(pos: Vector3, yaw: float, label: String) -> M4Objects.BreakerLever:
	var s := M4Objects.BreakerLever.new()
	s.prompt = "[HOLD F] CLOSE MAIN BREAKER " + label
	s.hold_time = 1.6
	b.dyn.add_child(s)
	s.global_position = pos
	s.rotation.y = deg_to_rad(yaw)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(0.9, 1.1, 0.4)
	cs.shape = bs
	cs.position = Vector3(0, 1.3, 0.2)
	s.add_child(cs)
	var vis := kp("main_breaker_lever", Vector3(0, 1.3, 0), 0.0, false, false, s)
	if vis:
		s.lever = vis.find_child("lever", true, false)
		s.lamp_on = vis.find_child("lamp_on", true, false)
		s.lamp_off = vis.find_child("lamp_off", true, false)
		if s.lamp_on:
			s.lamp_on.visible = false
	else:
		_station_box(s, Vector3(0.6, 0.9, 0.3), Vector3(0, 1.3, 0.15), MatLib.flat(Color(0.3, 0.32, 0.32), 0.5, 0.5))
		var piv := Node3D.new()
		piv.position = Vector3(0.39, 1.3, 0.33)
		s.add_child(piv)
		_station_box(piv, Vector3(0.08, 0.5, 0.08), Vector3(0, 0.22, 0), MatLib.flat(Color(0.7, 0.1, 0.05), 0.3, 0.5))
		s.lever = piv
	var lbl := Label3D.new()
	lbl.text = "MAIN BREAKER " + label
	lbl.font_size = 40
	lbl.pixel_size = 0.004
	lbl.shaded = true
	lbl.modulate = Color(0.9, 0.85, 0.7)
	lbl.position = Vector3(0, 2.05, 0.05)
	s.add_child(lbl)
	return s


# ------------------------------------------------------------------ relay core
func _core() -> void:
	var H := 12.3
	b.floor_overlay(12.15, -61.85, 31.85, -42.15, MatLib.pbr("metal_plate_02", 0.5, Color(0.5, 0.52, 0.55), 0.35, 1.1, "core_floor"))
	b.wall_x(-42, 12, 32, H, [[14.15, 19.85, 4.0]])
	b.wall_x(-62, 12, 32, H)
	b.wall_z(12, -62, -42, H)
	b.wall_z(32, -62, -42, H)
	b.ceiling(12, -62, 32, -42, 12.0, MatLib.flat(Color(0.12, 0.12, 0.13), 0.7, 0.5))
	# Antechamber between the server room and the core
	b.floor_overlay(14.15, -41.85, 19.85, -38.15, MatLib.diamond_plate())
	b.wall_z(14, -42, -38, 4.3)
	b.wall_z(20, -42, -38, 4.3)
	b.ceiling(14, -42, 20, -38, 4.0)
	# Blast door in the server-room north wall (opening cut in LevelBuilder).
	# The leaf runs on the frame's front track (server side) and parks east.
	blast_door = M4Objects.BlastDoor.new()
	blast_door.name = "BlastDoor"
	b.dyn.add_child(blast_door)
	blast_door.global_position = Vector3(BLAST_X, 0, -38.0)
	var leaf: Node3D = null
	if has_kit("blast_door"):
		leaf = kit.get_node("blast_door").duplicate()
		MatLib.remap_scene(leaf)
		leaf.transform = Transform3D.IDENTITY
	else:
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(2.4, 3.2, 0.3)
		mi.mesh = bm
		mi.material_override = MatLib.steel_door()
		mi.position = Vector3(0, 1.6, 0)
		leaf = mi
	blast_door.setup(leaf, Vector3(2.4, 3.2, 0.3), Vector3(0, 0, 0.315))
	blast_door.slide = Vector3(2.75, 0, 0)
	kp("blast_door_frame", Vector3(BLAST_X, 0, -38.0), 0.0)
	# Frame jamb linings narrow the 2.6 m opening to 2.3 m clear.
	_hidden_collider(Vector3(BLAST_X - 1.3, 0, -38.2), Vector3(BLAST_X - 1.15, 3.4, -37.8))
	_hidden_collider(Vector3(BLAST_X + 1.15, 0, -38.2), Vector3(BLAST_X + 1.3, 3.4, -37.8))
	_hidden_collider(Vector3(BLAST_X - 1.3, 3.15, -38.2), Vector3(BLAST_X + 1.3, 3.4, -37.8))
	b.nav_block("blast", Vector3(BLAST_X, 1.2, -38.0), Vector3(2.8, 2.4, 0.6))
	b.nav_block("blast_parked", Vector3(BLAST_X + 2.75, 1.2, -37.7), Vector3(2.5, 2.4, 0.4))   # open leaf parks here
	b.place_sign("RELAY NINE CORE", Vector3(11.6, 2.5, -37.83), 0, 40, Color(0.9, 0.3, 0.2), 0.004)
	b.place_sign("NO ENTRY", Vector3(11.6, 2.15, -37.83), 0, 30, Color(0.9, 0.75, 0.2), 0.004)
	# Dais + array (the antagonist's heart). The dais is fenced by insulator
	# stacks and the maintenance ring, so it is an obstacle, not a platform.
	var c := core_center
	core_array = kp("relay_core_array", c, 0.0)
	if core_array == null:
		var col := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.7
		cm.bottom_radius = 0.9
		cm.height = 6.4
		col.mesh = cm
		col.material_override = MatLib.flat(Color(0.45, 0.25, 0.12), 1.0, 0.35, Color(0.3, 0.6, 1.0), 0.6)
		b.add_child(col)
		col.position = c + Vector3(0, 3.8, 0)
		core_array = col
		var dais := MeshInstance3D.new()
		var dm := CylinderMesh.new()
		dm.top_radius = 3.0
		dm.bottom_radius = 3.1
		dm.height = 0.6
		dm.radial_segments = 48
		dais.mesh = dm
		dais.material_override = MatLib.flat(Color(0.16, 0.17, 0.18), 0.8, 0.4)
		b.add_child(dais)
		dais.position = c + Vector3(0, 0.3, 0)
	var dcol := StaticBody3D.new()
	dcol.collision_layer = 1
	dcol.collision_mask = 0
	dcol.set_meta("surface", "metal")
	var dcs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = 3.1
	cyl.height = 1.8
	dcs.shape = cyl
	dcol.add_child(dcs)
	b.nav.add_child(dcol)
	dcol.global_position = c + Vector3(0, 0.9, 0)
	_hidden_collider(c + Vector3(-1.1, 0, -1.1), c + Vector3(1.1, 7.0, 1.1))
	b.cover_props.append(AABB(c + Vector3(-3.0, 0, -3.0), Vector3(6.0, 2.0, 6.0)))
	# Capacitor stacks: the objectives
	for p in [Vector3(15.5, 0, -47.5), Vector3(28.5, 0, -47.5), Vector3(22.0, 0, -59.5)]:
		capacitors.append(_capacitor(p))
	# Defensive cover ring
	b.prop("barrier", Vector3(19.5, 0, -45.6), 0, true, "concrete")
	b.prop("barrier", Vector3(25.5, 0, -45.6), 0, true, "concrete")
	b.prop("barrier", Vector3(16.2, 0, -54.5), 90, true, "concrete")
	b.prop("barrier", Vector3(27.8, 0, -54.5), 90, true, "concrete")
	b.prop("crate", Vector3(13.6, 0, -60.4), 0, true)
	b.prop("crate", Vector3(30.4, 0, -43.6), 90, true)
	for x in [16.0, 20.0, 24.0, 28.0]:
		kp("core_bus_bar_4", Vector3(x, 10.5, -52.0), 0.0)
	# Lighting: cold rim lights + the core's own glow
	light_room("core", [Vector3(15, 11.4, -45), Vector3(29, 11.4, -45), Vector3(15, 11.4, -59), Vector3(29, 11.4, -59)], Color(0.7, 0.8, 1.0), 6.0, 14.0, 40)
	core_glow = OmniLight3D.new()
	core_glow.light_color = Color(0.45, 0.7, 1.0)
	core_glow.light_energy = 6.0
	core_glow.omni_range = 16.0
	core_glow.shadow_enabled = true
	core_glow.light_volumetric_fog_energy = 1.6
	core_glow.name = "CoreGlow"
	b.add_child(core_glow)
	core_glow.global_position = c + Vector3(0, 5.0, 0)
	b.light_omni(Vector3(17.0, 3.4, -40.0), Color(1.0, 0.86, 0.7), 1.0, 6.0, false, "antechamber")
	emergency(Vector3(17.0, 3.4, -41.6))
	emergency(Vector3(12.4, 3.2, -52.0))
	emergency(Vector3(31.6, 3.2, -52.0))
	b.place_sign("RELAY NINE", Vector3(22.0, 9.5, -61.83), 0, 160, Color(0.75, 0.74, 0.7), 0.008)


func _capacitor(p: Vector3) -> M4Objects.CapacitorStack:
	var s := M4Objects.CapacitorStack.new()
	b.nav.add_child(s)   # static: part of the navmesh source
	s.global_position = p
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(1.2, 2.6, 1.2)
	cs.shape = bs
	cs.position = Vector3(0, 1.3, 0)
	s.add_child(cs)
	var intact := kp("capacitor_stack", Vector3.ZERO, 0.0, false, false, s)
	var broken := kp("capacitor_stack_destroyed", Vector3.ZERO, 0.0, false, false, s)
	if intact == null:
		intact = _station_box(s, Vector3(1.1, 2.5, 1.1), Vector3(0, 1.25, 0), MatLib.flat(Color(0.3, 0.5, 0.7), 0.3, 0.4, Color(0.4, 0.7, 1.0), 2.0))
	s.intact = intact
	if broken:
		broken.visible = false
		s.broken = broken
	var l := OmniLight3D.new()
	l.light_color = Color(0.45, 0.7, 1.0)
	l.light_energy = 2.0
	l.omni_range = 5.0
	s.add_child(l)
	l.position = Vector3(0, 1.8, 0)
	s.glow = l
	b.cover_props.append(AABB(p + Vector3(-0.6, 0, -0.6), Vector3(1.2, 2.6, 1.2)))
	return s


# ------------------------------------------------------------------ office + dock stations
func _office_panel() -> void:
	# Control-wing lockdown panel on the security office north wall.
	lockdown_panel = _station("[HOLD F] RELEASE CONTROL-WING LOCKDOWN", 2.5, Vector3(3.6, 0.0, -12.85), 0.0, Vector3(0.9, 0.8, 0.2), Vector3(0, 1.35, 0.1))
	var dark := MatLib.flat(Color(0.12, 0.13, 0.14), 0.6, 0.45)
	_station_box(lockdown_panel, Vector3(0.9, 0.75, 0.1), Vector3(0, 1.35, 0.05), dark)
	lockdown_screen = _station_box(lockdown_panel, Vector3(0.62, 0.36, 0.02), Vector3(0, 1.45, 0.11), MatLib.flat(Color(0.05, 0.01, 0.01), 0.0, 0.3, Color(1.0, 0.15, 0.08), 1.6))
	lockdown_label = Label3D.new()
	lockdown_label.text = "CONTROL WING\nLOCKDOWN ENGAGED"
	lockdown_label.font_size = 22
	lockdown_label.pixel_size = 0.0028
	lockdown_label.modulate = Color(1.0, 0.75, 0.7)
	lockdown_label.position = Vector3(0, 1.45, 0.125)
	lockdown_panel.add_child(lockdown_label)
	b.place_sign("SECURITY LOCKDOWN", Vector3(3.6, 1.92, -12.83), 0, 24, Color(0.85, 0.84, 0.8), 0.003)


## Three limited ammunition caches along the mission (tunable stock):
##   security office (lockdown objective), switchgear hall (power objective),
##   relay control (upload defence; last stop before the relay core).
const CACHE_STOCK := {"office": [60, 30], "switchgear": [60, 15], "control": [90, 30]}


func _ammo_caches() -> void:
	caches.append(_ammo_cache("SECURITY AMMO CACHE", Vector3(1.7, 0, -12.4), 0.0, CACHE_STOCK.office))
	caches.append(_ammo_cache("SWITCHGEAR AMMO CACHE", Vector3(36.2, 0, -2.6), 180.0, CACHE_STOCK.switchgear))
	caches.append(_ammo_cache("CONTROL AMMO CACHE", Vector3(23.2, 0, -26.6), 180.0, CACHE_STOCK.control))


func _ammo_cache(cache_name: String, pos: Vector3, yaw: float, stock: Array) -> M4Objects.AmmoCache:
	var c := M4Objects.AmmoCache.new()
	c.cache_name = cache_name
	c.rifle = stock[0]
	c.pistol = stock[1]
	c.rifle_max = stock[0]
	c.pistol_max = stock[1]
	c.prompt = "[HOLD F] TAKE AMMUNITION"
	c.hold_time = 1.0
	b.nav.add_child(c)   # floor obstacle: part of the navmesh source
	c.global_position = pos
	c.rotation.y = deg_to_rad(yaw)
	# Same green case as the dock armory, read back in local space.
	var crate := b.prop("crate", Vector3.ZERO, 0.0, false, "metal", false, c)
	var world := b._world_aabb(crate) if crate else AABB(pos + Vector3(-0.5, 0, -0.4), Vector3(1.0, 0.8, 0.8))
	var la: AABB = c.global_transform.affine_inverse() * world
	b.cover_props.append(world)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = la.size
	cs.shape = bs
	cs.position = la.get_center()
	c.add_child(cs)
	var top := la.end.y
	var front := la.end.z
	var half_w := la.size.x * 0.5
	# Ammo cans on top: they disappear as the stock runs down.
	var olive := MatLib.flat(Color(0.2, 0.24, 0.14), 0.3, 0.6)
	for i in 3:
		var x := (i - 1) * minf(0.3, half_w * 0.62)
		var can := _station_box(c, Vector3(0.26, 0.17, 0.15), Vector3(x, top + 0.085, la.get_center().z + (0.05 if i == 1 else -0.06)), olive)
		_station_box(can, Vector3(0.262, 0.03, 0.152), Vector3(0, 0.03, 0), MatLib.hazard())
		c.cans.append(can)
	# Stencil, status lamp, stock readout, a faint green glow (findable in the blackout).
	var sten := Label3D.new()
	sten.text = "AMMUNITION"
	sten.font_size = 44
	sten.pixel_size = 0.0022
	sten.modulate = Color(0.95, 0.8, 0.2)
	sten.shaded = true
	sten.double_sided = false
	sten.position = Vector3(0, top * 0.55, front + 0.012)
	c.add_child(sten)
	c.lamp = _station_box(c, Vector3(0.07, 0.05, 0.02), Vector3(half_w * 0.72, top * 0.78, front + 0.01), MatLib.flat(Color(0.2, 1.0, 0.35)))
	c.readout = Label3D.new()
	c.readout.font_size = 30
	c.readout.pixel_size = 0.0015
	c.readout.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
	c.readout.position = Vector3(0, top + 0.32, la.get_center().z)
	c.add_child(c.readout)
	c.glow = OmniLight3D.new()
	c.glow.light_color = Color(0.45, 1.0, 0.55)
	c.glow.light_energy = 0.3
	c.glow.omni_range = 2.0
	c.glow.shadow_enabled = false
	c.add_child(c.glow)
	c.glow.position = Vector3(0, top + 0.35, front + 0.25)
	c.refresh()
	return c


func set_lockdown_released() -> void:
	lockdown_label.text = "CONTROL WING\nLOCKDOWN RELEASED"
	lockdown_label.modulate = Color(0.6, 1.0, 0.7)
	lockdown_screen.material_override = MatLib.flat(Color(0.01, 0.05, 0.02), 0.0, 0.3, Color(0.2, 1.0, 0.4), 1.4)


func _lift_panel() -> void:
	lift_panel = _station("[HOLD F] CALL FREIGHT LIFT 2", 2.0, Vector3(0.15, 0.0, 8.6), 90.0, Vector3(0.86, 2.0, 0.55), Vector3(0, 1.0, 0.28))
	lift_panel.active = false
	var vis := kp("pump_control_panel", Vector3(0, 0, 0.28), 0.0, false, false, lift_panel)
	if vis == null:
		_station_box(lift_panel, Vector3(0.6, 1.3, 0.35), Vector3(0, 0.65, 0.2), MatLib.flat(Color(0.75, 0.6, 0.1), 0.4, 0.5))
	else:
		# The kit panel's (merged) nameplate reads "CW PUMP 2": cover it with a
		# blank plate and re-title it.
		_station_box(lift_panel, Vector3(0.46, 0.095, 0.008), Vector3(0, 1.79, 0.28 + 0.264), MatLib.flat(Color(0.86, 0.87, 0.86), 0.0, 0.4))
		var lbl := Label3D.new()
		lbl.text = "FREIGHT LIFT 2"
		lbl.font_size = 28
		lbl.pixel_size = 0.0017
		lbl.modulate = Color(0.12, 0.12, 0.13)
		lbl.outline_size = 0
		lbl.shaded = true
		lbl.position = Vector3(0, 1.79, 0.28 + 0.27)
		lift_panel.add_child(lbl)
	b.place_sign("FREIGHT LIFT 2 - CALL", Vector3(0.17, 2.3, 8.6), 90, 28, Color(0.9, 0.75, 0.2), 0.0035)
