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
const DOCK_KIT := "res://assets/models/dock_kit.glb"
const CONTROL_KIT := "res://assets/models/control_kit.glb"

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
	_dock_m3()
	_control_m3()
	_decals_m3()
	for k in _kits.values():
		(k as Node).free()   # out-of-tree templates must not outlive the level (exit crash)
	_kits.clear()
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
	for z in spaced(r[1], r[3], 4.0, [[-13.6, -4.8], [-18.75, -17.25]]):
		kitp("wall_rib_9", Vector3(r[2], 0, z), -90)
	for z in [-6.0, -10.0, -18.0, -22.0]:
		for x in range(11, 31, 4):
			kitp("ibeam_4", Vector3(x + 0.0, r[4] - 0.17, z), 0, Vector3.ONE, false, false)
	# Dock: ribs scaled to 6 m, beams.
	r = ROOMS.dock
	var s6 := Vector3(1, 1.5, 1)
	for x in spaced(r[0], r[2], 4.0, [[6.75, 8.25], [12.0, 14.5]]):
		kitp("wall_rib_4", Vector3(x, 0, r[1]), 0, s6)
	for x in spaced(r[0], r[2], 4.0, [[9.0, 14.0], [0.6, 5.4]]):
		kitp("wall_rib_4", Vector3(x, 0, r[3]), 180, s6)
	for z in spaced(r[1], r[3], 3.5, [[9.4, 14.0], [1.05, 2.95]]):
		kitp("wall_rib_4", Vector3(r[0], 0, z), 90, s6)
	for z in spaced(r[1], r[3], 3.5, [[3.8, 5.2], [7.6, 9.0]]):
		kitp("wall_rib_4", Vector3(r[2], 0, z), -90, s6)
	for z in [3.5, 7.0, 10.5]:
		for x in [2.0, 6.0, 10.0, 14.0]:
			if z > 10.0 and x < 7.0:
				continue   # the freight-lift rig occupies this bay
			if absf(z - 7.0) < 0.1 and ResourceLoader.exists(DOCK_KIT):
				continue   # the gantry crane track replaces this beam
			kitp("ibeam_4", Vector3(x, r[4] - 0.17, z), 0, Vector3.ONE, false, false)
	# Corridor: slimmer ribs every 3 m (scaled), keeps the long run readable.
	r = ROOMS.corridor
	var s36 := Vector3(0.8, 0.9, 0.7)
	for z in spaced(r[1], r[3], 3.0, [[-9.25, -7.75], [-15.2, -13.8], [-26.2, -24.8], [-29.25, -27.75]]):
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
	for z in spaced(r[1], r[3], 3.0, [[-39.2, -37.2], [-28.75, -27.25], [-35.8, -29.4]]):   # no ribs behind the mimic board
		kitp("wall_rib_4", Vector3(r[2], 0, z), -90, s45)


## Cable trays, pipe bundles, ducts and vents.
func _services() -> void:
	# Corridor: cable tray and pipe bundle along the length.
	for z in range(-28, 0, 4):
		kitp("cable_tray_4", Vector3(6.75, 3.0, z + 0.0), 90, Vector3.ONE, false, false)
		kitp("pipe_bundle_4", Vector3(8.58, 2.65, z + 0.0), -90, Vector3.ONE, false, false)
	# Hall: pipe bundles high on the south and north walls, duct across, trays.
	for x in range(11, 31, 4):
		kitp("pipe_bundle_4", Vector3(x + 0.0, 5.0, -2.42), 180, Vector3.ONE, false, false)
		kitp("pipe_bundle_4", Vector3(x + 0.0, 5.8, -25.58), 0, Vector3.ONE, false, false)
		kitp("duct_4", Vector3(x + 0.6, 7.6, -20.0), 0, Vector3.ONE, false, false)
		kitp("cable_tray_4", Vector3(x + 0.0, 6.6, -8.0), 0, Vector3.ONE, false, false)
	# Dock: ducts and pipes.
	for x in [9.2, 13.2]:
		kitp("duct_4", Vector3(x, 5.2, 12.0), 0, Vector3.ONE, false, false)
	for x in [2.0, 6.0, 10.0, 14.0]:
		kitp("pipe_bundle_4", Vector3(x, 3.4, 0.42), 0, Vector3.ONE, false, false)
	# Servers: overhead cable trays above each rack row, duct along the wall.
	for row in [-29.5, -32.5, -35.5]:
		for x in [12.0, 16.0, 19.0]:
			kitp("cable_tray_4", Vector3(x, 2.55, row), 0, Vector3(0.75, 1, 1), false, false)
	for x in [11.0]:
		kitp("duct_4", Vector3(x, 3.05, -37.45), 0, Vector3.ONE, false, false)
	# Control: duct + tray.
	for x in [23.0, 27.0, 31.0]:
		kitp("duct_4", Vector3(x, 3.9, -27.0), 0, Vector3.ONE, false, false)
	# Vents.
	for v in [[Vector3(3.0, 2.6, -12.85), 0], [Vector3(-5.85, 2.6, -5.4), 90], [Vector3(20.85, 2.7, -29.0), -90],
			[Vector3(15.85, 4.5, 2.0), -90], [Vector3(0.15, 4.5, 4.0), 90],
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
	ph("hand_truck", Vector3(11.9, 0, 3.0), -60)
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
	ph("security_camera_02", Vector3(8.5, 2.3, -29.75), 30, false)
	# Office
	ph("metal_office_desk", Vector3(-1.0, 0, -12.1), 0, true, true)
	ph("SchoolChair_01", Vector3(-1.2, 0, -11.2), 170)
	ph("SchoolChair_01", Vector3(1.0, 0, -6.8), 75)          # knocked aside
	ph("cardboard_box_01", Vector3(4.8, 0, -3.8), 10)
	ph("utility_box_02", Vector3(5.6, 0.7, -6.0), -90, false)
	# Hall
	ph("utility_box_02", Vector3(9.5, 0.6, -17.0), 90, false)
	ph("utility_box_01", Vector3(9.5, 0.7, -18.0), 90, false)
	ph("power_box_01", Vector3(26.0, 1.2, -2.4), 180, false)
	ph("metal_tool_chest", Vector3(23.6, 0, -6.0), 180, true, true)
	ph("modular_industrial_pipes_01", Vector3(31.6, 1.0, -22.0), -90, false)   # kit origin is mid-height
	ph("modular_electric_cables", Vector3(31.75, 3.5, -21.5), -90, false)   # clear of D10
	ph("hanging_industrial_lamp", Vector3(19.0, 7.6, -11.5), 0, false)
	ph("security_camera_02", Vector3(31.5, 6.0, -2.5), -135, false)
	# Servers
	ph("utility_box_02", Vector3(20.6, 0.7, -36.0), -90, false)
	ph("worn_metal_rack", Vector3(9.6, 0, -37.2), 90, true)
	# Control
	if not ResourceLoader.exists(DOCK_KIT):
		ph("utility_box_02", Vector3(32.6, 0.7, -31.0), -90, false)
	ph("power_box_01", Vector3(21.4, 1.3, -39.45), 90, false)
	ph("SchoolChair_01", Vector3(24.2, 0, -31.0), -100)
	ph("security_camera_02", Vector3(32.5, 3.2, -26.6), -135, false)


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
	# Kept clear of the patrol lane between the turbines.
	ph("metal_tool_chest", Vector3(29.6, 0, -13.9), 80, true)
	ph("hand_truck", Vector3(30.3, 0, -12.9), 110)



# ------------------------------------------------------------------ M3: dock, control room, decals
var _kits := {}


func k3(kit_path: String, name: String, pos: Vector3, yaw_deg := 0.0, collide := false, cover := false, scl := Vector3.ONE) -> Node3D:
	if not ResourceLoader.exists(kit_path):
		return null
	if not _kits.has(kit_path):
		_kits[kit_path] = (load(kit_path) as PackedScene).instantiate()
	var src: Node3D = _kits[kit_path].get_node_or_null(name)
	if src == null:
		push_warning("M3 kit piece missing: " + name)
		return null
	var inst: Node3D = src.duplicate()
	(b.nav if collide else b).add_child(inst)
	inst.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)).scaled(scl), pos)
	MatLib.remap_scene(inst)
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		if mi.get_aabb().size.length() < 0.4:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.visibility_range_end = 30.0
	if collide:
		var aabb := _collider(inst, "metal")
		if cover:
			b.cover_props.append(aabb)
	return inst


func _dock_m3() -> void:
	if not ResourceLoader.exists(DOCK_KIT):
		return
	# Freight lift (extraction) - gate faces into the dock (north).
	k3(DOCK_KIT, "freight_lift", Vector3(3.0, 0.0, 11.8), 180)
	# Roll-up bay door on the south wall, leveler in front of it.
	k3(DOCK_KIT, "rollup_door", Vector3(11.5, 0.0, 13.85), 180)
	k3(DOCK_KIT, "dock_leveler", Vector3(11.5, 0.012, 12.55), 180)
	for x in [9.25, 13.75]:
		k3(DOCK_KIT, "floor_bollard", Vector3(x, 0, 12.9), 0, true)
	# 20 ft container along the east wall (hard cover, landmark).
	k3(DOCK_KIT, "container_20ft", Vector3(14.35, 0.0, 7.6), 0, true, true)
	# Forklift parked by the bay, pallets and stock.
	k3(DOCK_KIT, "forklift", Vector3(5.9, 0.0, 2.4), 200, true, true)   # parked in the open bay area, clear of container and spawn
	k3(DOCK_KIT, "wheel_chock", Vector3(6.4, 0.0, 1.0), 200)
	k3(DOCK_KIT, "pallet_stack", Vector3(6.6, 0.0, 12.9), 4, true, true)
	k3(DOCK_KIT, "pallet_boxes", Vector3(5.5, 0.0, 6.5), -8, true, true)
	k3(DOCK_KIT, "pallet", Vector3(6.3, 0.0, 9.0), 22, false)
	# Overhead crane and services.
	k3(DOCK_KIT, "gantry_beam_8", Vector3(8.0, 5.55, 7.0), 0)   # runs on its own track; the z=7 roof beam is omitted
	k3(DOCK_KIT, "cable_reel", Vector3(10.2, 0.0, 1.0), 90, true)
	for x in [2.0, 10.0]:
		k3(DOCK_KIT, "wall_cable_run_4", Vector3(x, 2.2, 0.42), 0)   # stands off the wall ribs
	k3(DOCK_KIT, "fire_hose_cabinet", Vector3(0.15, 1.25, 3.65), 90)   # between wall ribs (z 1.9 / 5.4)


func _control_m3() -> void:
	if not ResourceLoader.exists(CONTROL_KIT):
		return
	# Operator desk facing the relay console and the wall display.
	k3(CONTROL_KIT, "control_desk_3", Vector3(27.0, 0.0, -32.8), 0, true, true)
	for x in [25.6, 27.0, 28.4]:
		k3(CONTROL_KIT, "office_chair", Vector3(x, 0.0, -31.9), 180 + randf_range(-25, 25))
	# Mimic board along the east wall: the room's landmark.
	k3(CONTROL_KIT, "mimic_panel", Vector3(32.85, 2.35, -32.6), -90)
	# Instrument racks and relay cabinets.
	k3(CONTROL_KIT, "instrument_rack", Vector3(21.45, 0.0, -37.25), 90, true)
	k3(CONTROL_KIT, "instrument_rack", Vector3(21.45, 0.0, -36.45), 90, true)
	k3(CONTROL_KIT, "relay_cabinet", Vector3(23.5, 0.0, -39.5), 0, true)
	k3(CONTROL_KIT, "relay_cabinet", Vector3(30.65, 0.0, -39.5), 0, true)
	k3(CONTROL_KIT, "emergency_stop", Vector3(28.7, 0.0, -35.9), 0, true)
	k3(CONTROL_KIT, "wall_clock", Vector3(24.0, 3.3, -26.15), 180)
	k3(CONTROL_KIT, "whiteboard", Vector3(30.8, 1.7, -26.15), 180)
	for z in [-34.6, -30.4]:
		k3(CONTROL_KIT, "cable_trench_cover", Vector3(24.0, 0.012, z), 90)
	# Suspended ceiling grid (one MultiMesh for plain tiles; light tiles at the fixtures).
	var src: Node3D = (_kits[CONTROL_KIT] as Node3D).get_node_or_null("ceiling_grid_tile")
	var tile_mesh: Mesh = null
	if src:
		for mi in src.find_children("*", "MeshInstance3D", true, false) + ([src] if src is MeshInstance3D else []):
			tile_mesh = (mi as MeshInstance3D).mesh
			break
	var lights := [Vector2(24.6, -33.0), Vector2(29.4, -33.0), Vector2(27.0, -37.8), Vector2(27.0, -28.2)]
	if tile_mesh:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = tile_mesh
		var xs := []
		var x := 21.75
		while x < 32.9:
			var z := -39.45
			while z < -26.2:
				var near_light := false
				for lp in lights:
					if absf(lp.x - x) < 0.61 and absf(lp.y - z) < 0.61:
						near_light = true
				if not near_light:
					xs.append(Vector3(x, 4.3, z))
				z += 1.2
			x += 1.2
		mm.instance_count = xs.size()
		for i in xs.size():
			mm.set_instance_transform(i, Transform3D(Basis(), xs[i]))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = MatLib.flat(Color(0.78, 0.78, 0.76), 0.0, 0.85)
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		b.add_child(mmi)
	for lp in lights:
		var lt := k3(CONTROL_KIT, "ceiling_grid_tile_light", Vector3(lp.x, 4.3, lp.y), 0)
		if lt:
			var e: Node = lt.find_child("light_panel*", true, false)
			if e:
				b._register_light("control", e)


## Wear and story decals (generated CC0 textures).
func _decals_m3() -> void:
	if not ResourceLoader.exists("res://assets/decals/oil_stain_1.png"):
		return
	# Floors: [texture, position, size, yaw]
	var floor := [
		["oil_stain_1", Vector3(5.5, 0, 2.0), 2.2, 20], ["oil_stain_2", Vector3(11.8, 0, 11.6), 1.6, 70],
		["tire_marks_1", Vector3(7.2, 0, 4.2), 4.0, 30], ["floor_scuffs_1", Vector3(6.5, 0, 6.0), 3.0, 0],
		["footprints_dust_1", Vector3(7.5, 0, 2.5), 2.0, 0], ["stencil_lift_2", Vector3(3.0, 0.09, 9.4), 1.6, 0],
		["cracks_1", Vector3(13.0, 0, 3.5), 2.5, 45], ["puddle_1", Vector3(1.6, 0, 3.2), 1.8, 10],
		["floor_scuffs_1", Vector3(20.0, 0, -11.5), 3.5, 90], ["oil_stain_2", Vector3(19.5, 0, -6.2), 1.4, 0],
		["cracks_1", Vector3(25.0, 0, -18.0), 3.0, 10], ["puddle_1", Vector3(11.0, 0, -23.5), 2.2, 60],
		["footprints_dust_1", Vector3(7.5, 0, -16.0), 1.8, 90], ["floor_scuffs_1", Vector3(27.0, 0, -30.0), 2.5, 0],
		["oil_stain_1", Vector3(14.5, 0, -31.0), 1.2, 0], ["stencil_no_step", Vector3(11.5, 0.02, 12.4), 1.2, 180],
	]
	for f in floor:
		_decal(f[0], f[1] + Vector3(0, 0.05, 0), Vector3.UP, f[2], f[3])
	# Walls: grime streaks running down from the ceiling / fixtures, stencils
	var walls := [
		["grime_streak_1", Vector3(4.0, 3.5, 0.15), Vector3(0, 0, 1), 2.5], ["grime_streak_2", Vector3(15.85, 3.0, 2.5), Vector3(-1, 0, 0), 2.5],
		["grime_streak_1", Vector3(0.15, 3.0, 3.0), Vector3(1, 0, 0), 3.0], ["grime_streak_2", Vector3(16.0, 6.5, -2.15), Vector3(0, 0, -1), 4.0],
		["grime_streak_1", Vector3(24.0, 6.0, -25.85), Vector3(0, 0, 1), 4.0], ["grime_streak_1", Vector3(31.85, 5.5, -18.0), Vector3(-1, 0, 0), 4.0],
		["grime_streak_2", Vector3(6.15, 2.6, -20.0), Vector3(1, 0, 0), 2.0], ["grime_streak_1", Vector3(8.85, 2.6, -6.0), Vector3(-1, 0, 0), 2.0],
		["stencil_9b", Vector3(16.0, 5.0, -25.85), Vector3(0, 0, 1), 2.4], ["stencil_high_voltage", Vector3(28.0, 1.7, -20.45), Vector3(0, 0, 1), 1.2],
		["stencil_9b", Vector3(0.15, 4.3, 7.0), Vector3(1, 0, 0), 1.6],
	]
	for w in walls:
		_decal(w[0], w[1], w[2], w[3], 0.0)


func _decal(tex: String, pos: Vector3, normal: Vector3, size: float, yaw_deg: float) -> void:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/decals/%s.png" % tex)
	if tex == "cracks_1":
		d.texture_normal = load("res://assets/decals/cracks_1_normal.png")
	d.size = Vector3(size, 0.25, size)
	d.cull_mask = 1
	d.upper_fade = 0.3
	d.lower_fade = 0.3
	d.distance_fade_enabled = true
	d.distance_fade_begin = 35.0
	d.distance_fade_length = 8.0
	b.add_child(d)
	d.global_position = pos
	var up := normal.normalized()
	var ref := Vector3.FORWARD if absf(up.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT
	if absf(up.y) < 0.5:
		ref = Vector3.UP   # walls: keep the texture's top edge up
	var x := ref.cross(up).normalized()
	var basis := Basis(x, up, x.cross(up))
	if absf(up.y) > 0.5:
		basis = basis.rotated(up, deg_to_rad(yaw_deg))
	d.global_transform.basis = basis
