class_name Dressing
extends RefCounted
## M2 set dressing for Substation 9-B. Places the modular kit (env_kit.glb),
## replacement props and CC0 Poly Haven models into the rooms built by
## LevelBuilder. Gameplay geometry (walls, cover, navmesh) stays in the
## builder; dressing is mostly non-blocking detail and only collides where
## the player could otherwise walk through it.
##
## Kit convention: Blender front -Y becomes Godot +Z, so a wall piece whose
## interior normal is n uses yaw = atan2(n.x, n.z).

const KIT := "res://assets/models/env_kit.glb"
const PH := "res://assets/models/ph/%s.glb"

var b: LevelBuilder
var kit: Node3D
var _ph := {}
var ok := false

# Room interiors: [x0, z0, x1, z1, height]
const ROOMS := {
	"dock": [0.15, 0.15, 15.85, 13.85, 6.0],
	"corridor": [6.15, -29.85, 8.85, -0.15, 3.6],
	"office": [-5.85, -12.85, 5.85, -3.15, 3.6],
	"hall": [9.15, -25.85, 31.85, -2.15, 9.0],
	"servers": [9.15, -37.85, 20.85, -26.15, 3.6],
	"control": [21.15, -39.85, 32.85, -26.15, 4.5],
}


func _init(builder: LevelBuilder) -> void:
	b = builder
	if ResourceLoader.exists(KIT):
		kit = (load(KIT) as PackedScene).instantiate()
		ok = true


func kitp(name: String, pos: Vector3, yaw_deg := 0.0, scl := Vector3.ONE, collide := false, shadows := true) -> Node3D:
	if not ok:
		return null
	var src: Node3D = kit.get_node_or_null(name)
	if src == null:
		push_warning("kit piece missing: " + name)
		return null
	var inst: Node3D = src.duplicate()
	(b.nav if collide else b).add_child(inst)
	inst.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)).scaled(scl), pos)
	MatLib.remap_scene(inst)
	if not shadows:
		for mi in inst.find_children("*", "MeshInstance3D", true, false):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if collide:
		_collider(inst, "metal")
	return inst


func ph(id: String, pos: Vector3, yaw_deg := 0.0, collide := true, cover := false, scl := 1.0) -> Node3D:
	var path := PH % id
	if not ResourceLoader.exists(path):
		return null
	if not _ph.has(id):
		_ph[id] = load(path)
	var inst: Node3D = (_ph[id] as PackedScene).instantiate()
	(b.nav if collide else b).add_child(inst)
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		mi.visibility_range_end = 32.0
		if mi.get_aabb().size.length() < 0.5:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	inst.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)).scaled(Vector3.ONE * scl), pos)
	if collide:
		var aabb := _collider(inst, "metal")
		if cover:
			b.cover_props.append(aabb)
	return inst


func _collider(inst: Node3D, surface: String) -> AABB:
	var aabb := b._world_aabb(inst)
	if aabb.size.length() < 0.05:
		return aabb
	var sb := StaticBody3D.new()
	sb.collision_layer = 1
	sb.collision_mask = 0
	sb.set_meta("surface", surface)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = aabb.size
	cs.shape = bs
	sb.add_child(cs)
	b.nav.add_child(sb)
	sb.global_position = aabb.get_center()
	return aabb


static func yaw_for(n: Vector3) -> float:
	return rad_to_deg(atan2(n.x, n.z))


## Positions along [a, b] every `step`, skipping `gaps` ([[lo, hi], ...]).
static func spaced(a: float, bnd: float, step: float, gaps: Array, margin := 0.9) -> Array:
	var out := []
	var x := a + step * 0.5
	while x < bnd:
		var blocked := false
		for g in gaps:
			if x > g[0] - margin and x < g[1] + margin:
				blocked = true
		if not blocked:
			out.append(x)
		x += step
	return out


# ------------------------------------------------------------------ main
func dress() -> void:
	if not ok:
		return
	_architecture()
	_services()
	_doors()
	_props()
	_storytelling()
	kit.free()
	kit = null


## Wall ribs (pilasters) and ceiling beams: the structural rhythm.
func _architecture() -> void:
	# Hall: 9 m ribs on every wall, I-beams across the roof.
	var r: Array = ROOMS.hall
	for x in spaced(r[0], r[2], 4.0, [[12.0, 14.5], [13.25, 14.75], [27.25, 28.75]]):
		kitp("wall_rib_9", Vector3(x, 0, r[3]), 180)
		kitp("wall_rib_9", Vector3(x, 0, r[1]), 0)
	for z in spaced(r[1], r[3], 4.0, [[-11.75, -10.25], [-13.0, -5.0]]):
		kitp("wall_rib_9", Vector3(r[0], 0, z), 90)
	for z in spaced(r[1], r[3], 4.0, [[-13.6, -4.8]]):
		kitp("wall_rib_9", Vector3(r[2], 0, z), -90)
	for z in [-6.0, -10.0, -18.0, -22.0]:
		for x in range(11, 31, 4):
			kitp("ibeam_4", Vector3(x + 0.0, r[4] - 0.17, z), 0, Vector3.ONE, false, false)
	# Dock: ribs scaled to 6 m, beams.
	r = ROOMS.dock
	var s6 := Vector3(1, 1.5, 1)
	for x in spaced(r[0], r[2], 4.0, [[6.75, 8.25], [12.0, 14.5]]):
		kitp("wall_rib_4", Vector3(x, 0, r[1]), 0, s6)
	for x in spaced(r[0], r[2], 4.0, [[9.0, 14.0]]):
		kitp("wall_rib_4", Vector3(x, 0, r[3]), 180, s6)
	for z in spaced(r[1], r[3], 3.5, [[9.4, 14.0]]):
		kitp("wall_rib_4", Vector3(r[0], 0, z), 90, s6)
	for z in spaced(r[1], r[3], 3.5, [[3.8, 5.2], [7.6, 9.0]]):
		kitp("wall_rib_4", Vector3(r[2], 0, z), -90, s6)
	for z in [3.5, 7.0, 10.5]:
		for x in [2.0, 6.0, 10.0, 14.0]:
			kitp("ibeam_4", Vector3(x, r[4] - 0.17, z), 0, Vector3.ONE, false, false)
	# Corridor: slimmer ribs every 3 m (scaled), keeps the long run readable.
	r = ROOMS.corridor
	var s36 := Vector3(0.8, 0.9, 0.7)
	for z in spaced(r[1], r[3], 3.0, [[-9.25, -7.75], [-15.2, -13.8], [-26.2, -24.8]]):
		kitp("wall_rib_4", Vector3(r[0], 0, z), 90, s36)
	for z in spaced(r[1], r[3], 3.0, [[-11.75, -10.25], [-29.75, -28.25], [-15.0, -14.0]]):
		kitp("wall_rib_4", Vector3(r[2], 0, z), -90, s36)
	# Control: ribs, I-beams.
	r = ROOMS.control
	var s45 := Vector3(1, 1.125, 1)
	for x in spaced(r[0], r[2], 3.0, [[23.6, 30.4]]):
		kitp("wall_rib_4", Vector3(x, 0, r[1]), 0, s45)
	for z in spaced(r[1], r[3], 3.0, [[-32.75, -31.25]]):
		kitp("wall_rib_4", Vector3(r[0], 0, z), 90, s45)
	for z in spaced(r[1], r[3], 3.0, [[-39.2, -37.2], [-28.6, -27.4]]):
		kitp("wall_rib_4", Vector3(r[2], 0, z), -90, s45)


## Cable trays, pipe bundles, ducts and vents.
func _services() -> void:
	# Corridor: cable tray and pipe bundle along the length.
	for z in range(-28, 0, 4):
		kitp("cable_tray_4", Vector3(6.75, 3.0, z + 0.0), 90, Vector3.ONE, false, false)
		kitp("pipe_bundle_4", Vector3(8.85, 2.65, z + 0.0), -90, Vector3.ONE, false, false)
	# Hall: pipe bundles high on the south and north walls, duct across, trays.
	for x in range(11, 31, 4):
		kitp("pipe_bundle_4", Vector3(x + 0.0, 5.0, -2.15), 180, Vector3.ONE, false, false)
		kitp("pipe_bundle_4", Vector3(x + 0.0, 5.8, -25.85), 0, Vector3.ONE, false, false)
		kitp("duct_4", Vector3(x + 0.0, 7.6, -20.0), 0, Vector3.ONE, false, false)
		kitp("cable_tray_4", Vector3(x + 0.0, 6.6, -8.0), 0, Vector3.ONE, false, false)
	# Dock: ducts and pipes.
	for x in [2.0, 6.0, 10.0, 14.0]:
		kitp("duct_4", Vector3(x, 5.2, 12.0), 0, Vector3.ONE, false, false)
		kitp("pipe_bundle_4", Vector3(x, 3.4, 0.15), 0, Vector3.ONE, false, false)
	# Servers: overhead cable trays above each rack row, duct along the wall.
	for row in [-29.5, -32.5, -35.5]:
		for x in [12.0, 16.0, 19.0]:
			kitp("cable_tray_4", Vector3(x, 2.55, row), 0, Vector3(0.75, 1, 1), false, false)
	for x in [11.0, 15.0, 19.0]:
		kitp("duct_4", Vector3(x, 3.05, -37.3), 0, Vector3.ONE, false, false)
	# Control: duct + tray.
	for x in [23.0, 27.0, 31.0]:
		kitp("duct_4", Vector3(x, 3.9, -27.0), 0, Vector3.ONE, false, false)
	# Vents.
	for v in [[Vector3(3.0, 2.6, -12.85), 0], [Vector3(-5.85, 2.6, -7.0), 90], [Vector3(20.85, 2.7, -29.0), -90],
			[Vector3(32.85, 3.2, -35.0), -90], [Vector3(15.85, 4.5, 6.0), -90], [Vector3(0.15, 4.5, 4.0), 90],
			[Vector3(8.85, 2.4, -20.0), -90], [Vector3(6.15, 2.4, -17.0), 90]]:
		kitp("vent_grille", v[0], v[1], Vector3.ONE, false, false)
	# Floor drains.
	for p in [Vector3(4.0, 0.0, 8.0), Vector3(12.0, 0.0, -11.5), Vector3(24.5, 0.0, -11.5), Vector3(7.5, 0.0, -18.0)]:
		kitp("floor_drain", p + Vector3(0, 0.012, 0), 0, Vector3.ONE, false, false)
	# Handrails around the turbines.
	for z in [-8.0, -15.0]:
		for x in [16.0, 18.1, 20.2, 22.3]:
			kitp("handrail_2", Vector3(x, 0, z + 2.3), 0, Vector3.ONE, true)


## Steel door frames, keypads and emergency lights at every door.
func _doors() -> void:
	for id in b.doors:
		var d: Door = b.doors[id]
		var along_x: bool = absf(d.global_transform.basis.x.x) > 0.5
		var center: Vector3 = d.global_position + d.global_transform.basis.x * (d.width * 0.5)
		center.y = 0
		kitp("door_frame", center, 0.0 if along_x else 90.0)
		var n: Vector3 = d.global_transform.basis.z
		var t: Vector3 = d.global_transform.basis.x
		for side in [1.0, -1.0]:
			var face = center + n * side * 0.16
			kitp("keypad", face + t * 0.98 + Vector3(0, 1.3, 0), yaw_for(n * side), Vector3.ONE, false, false)
			kitp("emergency_light", face + Vector3(0, 2.45, 0), yaw_for(n * side), Vector3.ONE, false, false)


## CC0 Poly Haven props: equipment that makes the rooms read as a real site.
func _props() -> void:
	# Dock: logistics.
	ph("hand_truck", Vector3(13.6, 0, 4.2), -60)
	ph("barrel_03", Vector3(13.8, 0, 2.6), 0, true, true)
	ph("cardboard_box_01", Vector3(2.4, 0, 6.0), 15)
	ph("cardboard_box_01", Vector3(2.8, 0, 6.5), -20)
	ph("cardboard_box_01", Vector3(2.6, 0.34, 6.2), 40)
	ph("worn_metal_rack", Vector3(15.5, 0, 11.2), -90, true, true)
	ph("hanging_industrial_lamp", Vector3(3.5, 4.64, 9.0), 0, false)
	ph("security_camera_02", Vector3(15.7, 4.2, 0.4), -135, false)
	ph("ladder_sectioned_01", Vector3(0.45, 0, 7.0), 90)
	# Corridor
	ph("utility_box_01", Vector3(6.35, 0.9, -5.5), 90, false)
	ph("fire_alarm", Vector3(6.17, 1.4, -10.0), 90, false)
	ph("industrial_wall_lamp", Vector3(8.82, 2.2, -21.0), -90, false)
	ph("security_camera_02", Vector3(8.6, 3.2, -29.5), 30, false)
	# Office
	ph("metal_office_desk", Vector3(-1.0, 0, -12.1), 0, true, true)
	ph("SchoolChair_01", Vector3(-1.2, 0, -11.2), 170)
	ph("SchoolChair_01", Vector3(1.0, 0, -6.8), 75)          # knocked aside
	ph("cardboard_box_01", Vector3(4.8, 0, -3.8), 10)
	ph("utility_box_02", Vector3(5.6, 0.7, -6.0), -90, false)
	# Hall
	ph("utility_box_02", Vector3(9.5, 0.6, -16.0), 90, false)
	ph("utility_box_01", Vector3(9.5, 0.7, -18.0), 90, false)
	ph("power_box_01", Vector3(26.0, 1.2, -2.4), 180, false)
	ph("metal_tool_chest", Vector3(23.6, 0, -6.0), 180, true, true)
	ph("modular_industrial_pipes_01", Vector3(31.6, 0.0, -22.0), -90, false)
	ph("modular_electric_cables", Vector3(31.75, 3.5, -16.0), -90, false)
	ph("hanging_industrial_lamp", Vector3(19.0, 7.6, -11.5), 0, false)
	ph("security_camera_02", Vector3(31.5, 6.0, -2.5), -135, false)
	# Servers
	ph("utility_box_02", Vector3(20.6, 0.7, -36.0), -90, false)
	ph("worn_metal_rack", Vector3(9.6, 0, -37.2), 90, true)
	# Control
	ph("utility_box_02", Vector3(32.6, 0.7, -31.0), -90, false)
	ph("power_box_01", Vector3(21.4, 1.3, -38.5), 90, false)
	ph("SchoolChair_01", Vector3(24.2, 0, -31.0), -100)
	ph("security_camera_02", Vector3(32.5, 3.8, -26.6), -135, false)


## Story beats: a scorched breach in the hall, cut cables sparking, an
## abandoned maintenance spot.
func _storytelling() -> void:
	# Scorch marks where a technician's cart was hit by an arc.
	for p in [[Vector3(18.5, 0.0, -11.8), 2.6], [Vector3(9.16, 1.6, -15.0), 1.6], [Vector3(17.0, 0.0, -29.8), 1.4], [Vector3(26.5, 0.0, -33.5), 2.0]]:
		var d := Decal.new()
		d.texture_albedo = Fx._radial([Color(0.0, 0.0, 0.0, 0.85), Color(0.03, 0.025, 0.02, 0.55), Color(0, 0, 0, 0)], [0.0, 0.45, 1.0], 128)
		d.size = Vector3(p[1], 0.4, p[1])
		b.add_child(d)
		d.global_position = p[0]
		if p[0].y > 0.5:
			d.rotation = Vector3(0, 0, -PI / 2)
	ph("metal_tool_chest", Vector3(18.2, 0, -11.2), 35, true)
	ph("hand_truck", Vector3(19.4, 0, -12.2), 110)
