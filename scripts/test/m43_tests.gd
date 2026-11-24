extends RefCounted
## M4.3 quality-pass checks (validation builds only).
##   --rv_gunaudio  scripted firing sequence in small / medium / large / huge rooms
##                  (record with --write-movie; segment times are logged in movie seconds)
##   --rv_tour      rendered sweep of every room and route (captures)

var ap
var main
var player: Player
var m: Mission
var lv: LevelBuilder


func _init(autopilot) -> void:
	ap = autopilot
	main = ap.main
	player = ap.player
	m = main.mission
	lv = main.level


func L(s: String) -> void:
	ap.L(s)


func W(t: float) -> void:
	await ap._wait(t)


func _movie_t() -> float:
	return Engine.get_frames_drawn() / 60.0


func _refill() -> void:
	for w in player.weapons:
		w.ammo = w.stats.mag
		w.reserve = int(w.def.reserve)


func _tap(n: int, gap: float) -> void:
	for i in n:
		player.bot_input.fire = true
		await W(0.04)
		player.bot_input.fire = false
		await W(gap)


func _burst(secs: float) -> void:
	player.bot_input.fire = true
	await W(secs)
	player.bot_input.fire = false


func _to_weapon(i: int) -> void:
	if player.current != i:
		player._request_switch(i)
		await W(1.2)


func _segment(label: String) -> void:
	L("SEGMENT %.2f %s" % [_movie_t(), label])


func gunaudio() -> void:
	L("GUN AUDIO capture: robots removed; HUD on; times are movie seconds (60 fps)")
	for b in main.director.bots.duplicate():
		main.director.bots.erase(b)
		b.queue_free()
	m.bots.clear()
	m.ex.blast_door.open_now(true)
	await W(4.0)
	var spots := [
		["office (small room)", Vector3(-1.0, 0.05, -7.0), Vector3(0.0, 1.5, -12.8)],
		["corridor (medium)", Vector3(7.5, 0.05, -12.0), Vector3(7.5, 1.5, -28.0)],
		["turbine hall (large)", Vector3(20.0, 0.05, -11.5), Vector3(28.0, 2.0, -20.0)],
		["relay core (huge)", Vector3(22.0, 0.05, -45.0), Vector3(22.0, 3.0, -56.0)],
		["crawlway (metal duct)", Vector3(-4.0, 0.05, 2.0), Vector3(-10.0, 0.6, 2.0)],
	]
	for s in spots:
		player.bot_input.crouch_set = s[0].begins_with("crawl")
		ap.teleport(s[1], s[2])
		await _to_weapon(0)
		player.set_loadout({"optic": "optic_reflex", "muzzle": "flash_hider", "grip": "grip_vertical", "mag": "mag_std"})
		_refill()
		await W(1.5)
		_segment("%s | rifle | open | 3 single" % s[0])
		await _tap(3, 0.55)
		await W(0.6)
		_segment("%s | rifle | open | burst" % s[0])
		await _burst(0.7)
		await W(2.2)
		player.set_loadout({"optic": "optic_reflex", "muzzle": "suppressor", "grip": "grip_vertical", "mag": "mag_std"})
		_refill()
		await W(0.8)
		_segment("%s | rifle | suppressed | 3 single" % s[0])
		await _tap(3, 0.55)
		await W(0.6)
		_segment("%s | rifle | suppressed | burst" % s[0])
		await _burst(0.7)
		await W(2.2)
		await _to_weapon(1)
		_refill()
		await W(0.4)
		_segment("%s | pistol | 3 single" % s[0])
		await _tap(3, 0.45)
		await W(2.0)
	player.bot_input.crouch_set = false
	_segment("END")


func tour() -> void:
	main.hud.visible = false
	for b in main.director.bots.duplicate():
		main.director.bots.erase(b)
		b.queue_free()
	m.bots.clear()
	m.ex.blast_door.open_now(true)
	for id in ["D1", "D2", "D3", "D4", "D7", "D8", "D9", "D9b", "D10"]:
		lv.doors[id].target = lv.doors[id].max_open[1]
	await W(6.0)
	var shots := []
	var tag := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--tag="):
			tag = a.get_slice("=", 1) + "_"
	var V := [
		["dock_se_to_nw", Vector3(15.0, 0.05, 13.0), Vector3(2.0, 1.5, 2.0)],
		["dock_nw_to_se", Vector3(1.2, 0.05, 1.2), Vector3(14.0, 1.5, 12.0)],
		["dock_lift_to_east", Vector3(4.5, 0.05, 9.0), Vector3(15.0, 2.0, 6.0)],
		["dock_ceiling", Vector3(8.0, 0.05, 7.0), Vector3(8.0, 5.6, 3.0)],
		["corridor_south_to_north", Vector3(7.5, 0.05, -0.8), Vector3(7.5, 1.5, -29.0)],
		["corridor_north_to_south", Vector3(7.5, 0.05, -29.2), Vector3(7.5, 1.5, -1.0)],
		["corridor_ceiling", Vector3(7.5, 0.05, -15.0), Vector3(7.5, 3.4, -20.0)],
		["office_se_to_nw", Vector3(5.2, 0.05, -3.8), Vector3(-5.0, 1.2, -12.0)],
		["office_nw_to_se", Vector3(-5.0, 0.05, -11.6), Vector3(5.0, 1.2, -4.0)],
		["hall_sw_to_ne", Vector3(10.0, 0.05, -24.5), Vector3(30.0, 3.0, -3.0)],
		["hall_ne_to_sw", Vector3(31.0, 0.05, -3.0), Vector3(10.0, 3.0, -24.0)],
		["hall_east_to_west", Vector3(30.5, 0.05, -14.0), Vector3(10.0, 2.0, -14.0)],
		["hall_ceiling", Vector3(20.0, 0.05, -14.0), Vector3(20.0, 8.8, -9.0)],
		["hall_passage_shutter", Vector3(13.2, 0.05, -4.0), Vector3(13.2, 1.0, 0.0)],
		["servers_nw_to_se", Vector3(10.0, 0.05, -27.0), Vector3(20.0, 1.5, -37.0)],
		["servers_se_to_nw", Vector3(20.4, 0.05, -37.4), Vector3(10.0, 1.5, -27.0)],
		["control_sw_to_ne", Vector3(22.0, 0.05, -27.0), Vector3(32.0, 1.5, -39.0)],
		["control_ne_to_sw", Vector3(32.0, 0.05, -38.6), Vector3(22.0, 1.5, -27.0)],
		["control_ceiling", Vector3(27.0, 0.05, -33.0), Vector3(27.0, 4.4, -36.0)],
		["pump_se_to_nw", Vector3(-7.0, 0.05, -4.0), Vector3(-23.0, 2.0, -29.0)],
		["pump_sw_to_ne", Vector3(-23.0, 0.05, -4.0), Vector3(-7.0, 2.0, -29.0)],
		["pump_gallery_east_to_west", Vector3(-7.5, 4.25, -29.0), Vector3(-23.0, 1.0, -5.0)],
		["pump_ceiling", Vector3(-15.0, 0.05, -12.0), Vector3(-15.0, 8.8, -20.0)],
		["tunnel_east_to_west", Vector3(5.0, 0.05, -28.5), Vector3(-6.0, 1.2, -28.5)],
		["switchgear_sw_to_ne", Vector3(33.5, 0.05, -3.0), Vector3(49.0, 2.0, -29.0)],
		["switchgear_nw_to_se", Vector3(34.5, 0.05, -29.0), Vector3(48.0, 2.0, -4.0)],
		["switchgear_gallery_south", Vector3(49.0, 4.25, -5.0), Vector3(34.0, 1.0, -26.0)],
		["switchgear_ceiling", Vector3(41.0, 0.05, -16.0), Vector3(41.0, 9.8, -22.0)],
		["antechamber", Vector3(17.0, 0.05, -38.6), Vector3(17.0, 1.8, -44.0)],
		["core_sw_to_ne", Vector3(13.0, 0.05, -43.0), Vector3(31.0, 3.0, -61.0)],
		["core_ne_to_sw", Vector3(31.0, 0.05, -61.0), Vector3(13.0, 3.0, -43.0)],
		["core_se_to_nw", Vector3(31.0, 0.05, -43.0), Vector3(13.0, 3.0, -61.0)],
		["core_ceiling", Vector3(22.0, 0.05, -46.0), Vector3(22.0, 11.8, -52.0)],
		["door_D1_dock_side", Vector3(7.5, 0.05, 3.2), Vector3(7.5, 1.3, 0.0)],
		["door_D3_corridor_side", Vector3(6.8, 0.05, -11.0), Vector3(9.0, 1.3, -11.0)],
		["door_D3_hall_side", Vector3(11.5, 0.05, -11.0), Vector3(9.0, 1.3, -11.0)],
		["door_D4_hall_side", Vector3(14.0, 0.05, -23.0), Vector3(14.0, 1.3, -26.0)],
		["door_D7_corridor_side", Vector3(6.6, 0.05, -27.0), Vector3(9.0, 1.3, -29.0)],
		["door_D5_servers_side", Vector3(18.5, 0.05, -32.0), Vector3(21.0, 1.3, -32.0)],
		["door_D6_hall_side", Vector3(28.0, 0.05, -23.0), Vector3(28.0, 1.3, -26.0)],
		# Close-ups of the spots the geometry audit flagged
		["detail_pump_header_pipe", Vector3(-16.0, 0.05, -10.0), Vector3(-16.0, 2.0, -4.0)],
		["detail_corridor_D7_sign", Vector3(7.0, 0.05, -25.0), Vector3(8.85, 2.4, -29.0)],
		["detail_corridor_D3_sign", Vector3(7.0, 0.05, -7.0), Vector3(8.85, 2.4, -11.0)],
		["detail_hall_clerestory", Vector3(24.0, 0.05, -16.0), Vector3(31.85, 7.6, -16.0)],
		["detail_hall_cable_trays", Vector3(20.0, 0.05, -12.5), Vector3(20.0, 6.6, -8.0)],
		["detail_servers_cable_trays", Vector3(11.0, 0.05, -34.0), Vector3(16.0, 2.8, -32.5)],
		["detail_switchgear_cable_trays", Vector3(41.0, 0.05, -17.0), Vector3(41.0, 6.4, -12.5)],
		["detail_control_racks", Vector3(29.5, 0.05, -38.2), Vector3(32.5, 1.2, -38.2)],
		["detail_control_light_tile", Vector3(26.0, 0.05, -35.0), Vector3(27.0, 4.3, -37.8)],
	]
	for v in V:
		ap.teleport(v[1], v[2])
		await W(2.5)
		await ap.shot(tag + v[0])
	player.bot_input.crouch_set = true
	for v in [["crawl_east_leg", Vector3(-1.0, 0.05, 2.0), Vector3(-9.0, 0.6, 2.0)], ["crawl_north_leg", Vector3(-10.0, 0.05, 0.5), Vector3(-10.0, 0.6, -4.0)]]:
		ap.teleport(v[1], v[2])
		await W(2.5)
		await ap.shot(tag + v[0])
	player.bot_input.crouch_set = false


# ------------------------------------------------------------------ geometry audit (mesh level)
var _solids: Array = []       # [AABB, String desc]
var _grid := {}               # Vector3i cell -> Array[int] solid indices
const CELL := 2.0


func _cell(p: Vector3) -> Vector3i:
	return Vector3i(floori(p.x / CELL), floori(p.y / CELL), floori(p.z / CELL))


func _index_solids() -> void:
	_solids.clear()
	_grid.clear()
	for parent in [lv, lv.nav]:
		for c in parent.get_children():
			if c is MeshInstance3D and (c as MeshInstance3D).mesh is BoxMesh and (c as MeshInstance3D).visible:
				var a: AABB = (c as MeshInstance3D).global_transform * (c as MeshInstance3D).get_aabb()
				if minf(a.size.x, minf(a.size.y, a.size.z)) < 0.1:
					continue   # overlays, stripes, wainscot skins
				var idx := _solids.size()
				_solids.append([a, "box@%s size %s" % [a.get_center().snapped(Vector3.ONE * 0.05), a.size.snapped(Vector3.ONE * 0.01)]])
				var c0 := _cell(a.position)
				var c1 := _cell(a.end)
				for x in range(c0.x, c1.x + 1):
					for y in range(c0.y, c1.y + 1):
						for z in range(c0.z, c1.z + 1):
							var k := Vector3i(x, y, z)
							if not _grid.has(k):
								_grid[k] = []
							_grid[k].append(idx)


func _depth_in(a: AABB, p: Vector3) -> float:
	if not a.has_point(p):
		return -1.0
	var e := a.end
	return minf(minf(minf(p.x - a.position.x, e.x - p.x), minf(p.y - a.position.y, e.y - p.y)), minf(p.z - a.position.z, e.z - p.z))


func _items() -> Array:
	var out := []
	for parent in [lv, lv.nav, lv.dyn]:
		for c in parent.get_children():
			if not (c is Node3D) or c is Light3D or c is Decal or c is NavigationRegion3D or c is ReflectionProbe or c is Area3D or c is FogVolume or c is GPUParticles3D:
				continue
			if c.name == "Dynamic" or c.name == "NavRegion":
				continue
			if c is MeshInstance3D and ((c as MeshInstance3D).mesh is BoxMesh or (c as MeshInstance3D).mesh is CylinderMesh):
				continue
			var mis: Array = c.find_children("*", "MeshInstance3D", true, false)
			if c is MeshInstance3D:
				mis.append(c)
			if mis.is_empty():
				continue
			out.append([c, mis])
	return out


func _verts(mis: Array, cap: int) -> PackedVector3Array:
	var pts := PackedVector3Array()
	for mi in mis:
		if not (mi as MeshInstance3D).is_visible_in_tree() or (mi as MeshInstance3D).mesh == null:
			continue
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		if mesh is BoxMesh or mesh is CylinderMesh or mesh is ImmediateMesh:
			continue
		var xf: Transform3D = (mi as MeshInstance3D).global_transform
		for s in mesh.get_surface_count():
			var arr := mesh.surface_get_arrays(s)
			if arr.is_empty():
				continue
			var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var step := maxi(1, v.size() / cap)
			for i in range(0, v.size(), step):
				pts.append(xf * v[i])
	return pts


func _item_name(n: Node) -> String:
	var nm := String(n.name)
	if nm.begins_with("@"):
		var mis := n.find_children("*", "MeshInstance3D", true, false)
		if not mis.is_empty():
			nm = "~" + String(mis[0].name)
	return nm


func geo() -> void:
	L("GEO AUDIT (mesh vertices vs structure, floating, holes, light leaks, coplanar faces)")
	for b in main.director.bots.duplicate():
		main.director.bots.erase(b)
		b.queue_free()
	m.bots.clear()
	m.ex.blast_door.open_now(true)
	await W(1.0)
	_index_solids()
	L("  structural boxes: %d" % _solids.size())
	var items := _items()
	L("  items: %d" % items.size())
	# --- A. penetration
	var pen := []
	var aabbs := {}
	for it in items:
		var pts := _verts(it[1], 400)
		if pts.is_empty():
			continue
		var bb := AABB(pts[0], Vector3.ZERO)
		for p in pts:
			bb = bb.expand(p)
		aabbs[it[0]] = bb
		var deep := 0
		var maxd := 0.0
		var where := ""
		for p in pts:
			var k := _cell(p)
			if not _grid.has(k):
				continue
			for si in _grid[k]:
				var d := _depth_in(_solids[si][0], p)
				if d > 0.04:
					deep += 1
					if d > maxd:
						maxd = d
						where = _solids[si][1]
		var frac := float(deep) / pts.size()
		if (frac > 0.04 and maxd > 0.04) or maxd > 0.15:
			pen.append([maxd * frac, "  PEN %-28s @%s  %.0f%% of %d verts inside, max depth %.2f m in %s" % [_item_name(it[0]), bb.get_center().snapped(Vector3.ONE * 0.05), frac * 100.0, pts.size(), maxd, where]])
	pen.sort_custom(func(a, b): return a[0] > b[0])
	L("A. PENETRATION candidates: %d" % pen.size())
	for p in pen.slice(0, 80):
		L(p[1])
	# --- B. floating
	var space: PhysicsDirectSpaceState3D = main.get_world_3d().direct_space_state
	var flo := []
	for it in items:
		if not aabbs.has(it[0]):
			continue
		var bb: AABB = aabbs[it[0]]
		if bb.size.y > 4.0 or bb.position.y < 0.03 or bb.position.y > 2.5:
			continue
		var cx := bb.get_center()
		# hung from above? (ray up from the top)
		var qu := PhysicsRayQueryParameters3D.create(Vector3(cx.x, bb.end.y - 0.02, cx.z), Vector3(cx.x, bb.end.y + 0.15, cx.z), 1)
		if not space.intersect_ray(qu).is_empty():
			continue
		# mounted on a wall? (structural box within 6 cm horizontally, overlapping in height)
		var near_wall := false
		var grown := bb.grow(0.06)
		for si in range(_solids.size()):
			var sa: AABB = _solids[si][0]
			if sa.size.y > 1.0 and sa.intersects(grown.abs()) and not sa.intersects(bb.grow(-0.02)):
				near_wall = true
				break
		if near_wall:
			continue
		# supported by another item?
		var supported := false
		for other in aabbs:
			if other == it[0]:
				continue
			var ob: AABB = aabbs[other]
			if absf(ob.end.y - bb.position.y) < 0.05 and ob.position.x < bb.end.x and ob.end.x > bb.position.x and ob.position.z < bb.end.z and ob.end.z > bb.position.z:
				supported = true
				break
		if supported:
			continue
		var qd := PhysicsRayQueryParameters3D.create(Vector3(cx.x, bb.position.y + 0.02, cx.z), Vector3(cx.x, bb.position.y - 3.0, cx.z), 1)
		var hd: Dictionary = space.intersect_ray(qd)
		var gap: float = bb.position.y - (hd.position.y if hd else 0.0)
		if gap > 0.03:
			flo.append("  FLOAT %-28s @%s bottom %.2f, surface below %.2f (gap %.2f)" % [_item_name(it[0]), cx.snapped(Vector3.ONE * 0.05), bb.position.y, (hd.position.y if hd else -9.0), gap])
	L("B. FLOATING candidates: %d" % flo.size())
	for f in flo.slice(0, 60):
		L(f)
	# --- C. holes: rays escaping each room into the void
	var dirs := []
	var n := 96
	for i in n:
		var yv := 1.0 - (i + 0.5) / n * 2.0
		var r := sqrt(1.0 - yv * yv)
		var th := i * 2.399963
		dirs.append(Vector3(cos(th) * r, yv, sin(th) * r))
	var holes := 0
	for room in Game.rooms:
		var a: AABB = Game.rooms[room].aabb
		var c := a.get_center()
		var pts2 := [Vector3(c.x, 1.6, c.z), Vector3(c.x, minf(a.end.y - 0.6, 1.6 + a.size.y * 0.4), c.z)]
		for sp in pts2:
			var esc := []
			for d in dirs:
				var q := PhysicsRayQueryParameters3D.create(sp, sp + d * 160.0, 1)
				if space.intersect_ray(q).is_empty():
					esc.append(d)
			if not esc.is_empty():
				holes += esc.size()
				L("  HOLE %-12s from %s: %d/%d rays escape, e.g. dir %s" % [room, sp.snapped(Vector3.ONE * 0.1), esc.size(), n, (esc[0] as Vector3).snapped(Vector3.ONE * 0.01)])
	L("C. ESCAPING rays total: %d" % holes)
	# --- D. light leaks through walls (non-shadowed lights)
	var leaks := []
	for l in lv.find_children("*", "Light3D", true, false):
		var light := l as Light3D
		if light.shadow_enabled or light is DirectionalLight3D:
			continue
		var rng: float = light.omni_range if light is OmniLight3D else (light as SpotLight3D).spot_range
		var en := light.light_energy if light.light_energy > 0.0 else 2.4
		var lp := light.global_position
		var home := Game.room_at(lp)
		for room in Game.rooms:
			if room == home:
				continue
			var ra: AABB = Game.rooms[room].aabb
			var cp := Vector3(clampf(lp.x, ra.position.x + 0.2, ra.end.x - 0.2), clampf(lp.y, ra.position.y + 1.2, ra.end.y - 0.3), clampf(lp.z, ra.position.z + 0.2, ra.end.z - 0.2))
			var d := lp.distance_to(cp)
			if d > rng * 0.85:
				continue
			if light is SpotLight3D:
				var fwd := -light.global_transform.basis.z
				if fwd.angle_to(cp - lp) > deg_to_rad((light as SpotLight3D).spot_angle):
					continue
			var q := PhysicsRayQueryParameters3D.create(lp, cp, 1)
			var h: Dictionary = space.intersect_ray(q)
			if h.is_empty():
				continue   # line of sight: legitimate spill through an opening
			var k := pow(1.0 - d / rng, 2.0) * en
			if k > 0.12:
				leaks.append([k, "  LEAK %-14s light@%s (energy %.1f, range %.1f, room %s) reaches %s through a wall at %.1f m, est %.2f" % [light.get_class(), lp.snapped(Vector3.ONE * 0.05), en, rng, home, room, d, k]])
	leaks.sort_custom(func(a, b): return a[0] > b[0])
	L("D. LIGHT LEAK candidates: %d" % leaks.size())
	for k in leaks.slice(0, 40):
		L(k[1])
	# --- E. coplanar visible faces with different materials (z-fighting)
	var faces := {}
	var boxes := []
	for parent in [lv, lv.nav]:
		for c in parent.get_children():
			if c is MeshInstance3D and (c as MeshInstance3D).mesh is BoxMesh and (c as MeshInstance3D).visible:
				boxes.append(c)
	for bi in boxes.size():
		var mi: MeshInstance3D = boxes[bi]
		var a: AABB = mi.global_transform * mi.get_aabb()
		for ax in 3:
			for sgn in [-1, 1]:
				var coord: float = a.end[ax] if sgn > 0 else a.position[ax]
				if ax == 1 and (coord <= 0.001 or coord > 2.9):
					continue   # bottoms resting on the floor, tops at ceiling level: never seen
				var key := "%d:%d:%d" % [ax, sgn, roundi(coord * 1000.0)]
				if not faces.has(key):
					faces[key] = []
				faces[key].append([bi, a])
	var zf := []
	for key in faces:
		var lst: Array = faces[key]
		if lst.size() < 2:
			continue
		var ax := int(String(key).get_slice(":", 0))
		var u := (ax + 1) % 3
		var v := (ax + 2) % 3
		for i in lst.size():
			for j in range(i + 1, lst.size()):
				var A: AABB = lst[i][1]
				var B: AABB = lst[j][1]
				var ou := minf(A.end[u], B.end[u]) - maxf(A.position[u], B.position[u])
				var ov := minf(A.end[v], B.end[v]) - maxf(A.position[v], B.position[v])
				if ou <= 0.02 or ov <= 0.02:
					continue
				var ma = boxes[lst[i][0]].material_override
				var mb = boxes[lst[j][0]].material_override
				if ma == mb:
					continue
				zf.append([ou * ov, "  ZFIGHT face %s area %.2f m2 between box@%s and box@%s" % [key, ou * ov, A.get_center().snapped(Vector3.ONE * 0.05), B.get_center().snapped(Vector3.ONE * 0.05)]])
	zf.sort_custom(func(a, b): return a[0] > b[0])
	L("E. COPLANAR different-material faces: %d" % zf.size())
	for z in zf.slice(0, 200):
		L(z[1])


# ------------------------------------------------------------------ targeted look + pick
## --rv_look --views="name@x,y,z@tx,ty,tz@px,py;px,py|name2@..."
## Captures each view; for every screen pixel listed, logs the meshes whose
## bounds the pixel's ray crosses (nearest first) to identify what is seen.
func _v3(s: String) -> Vector3:
	var c := s.split(",")
	return Vector3(float(c[0]), float(c[1]), float(c[2]))


func _prep_static() -> void:
	main.hud.visible = false
	for bt in main.director.bots.duplicate():
		main.director.bots.erase(bt)
		bt.queue_free()
	m.bots.clear()
	m.ex.blast_door.open_now(true)
	for id in ["D1", "D2", "D3", "D4", "D7", "D8", "D9", "D9b", "D10"]:
		lv.doors[id].target = lv.doors[id].max_open[1]
	if "--emergency" in OS.get_cmdline_user_args():
		m._emergency_lighting(true)
	await W(5.0)


func look() -> void:
	await _prep_static()
	var spec := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--views="):
			spec = a.substr(8)
	for item in spec.split("|", false):
		var parts := item.split("@")
		ap.teleport(_v3(parts[1]), _v3(parts[2]))
		if parts[0].begins_with("crouch_"):
			player.bot_input.crouch_set = true
		await W(1.2)
		await ap.shot(parts[0])
		if parts.size() > 3:
			for pxs in parts[3].split(";", false):
				var xy := pxs.split(",")
				_pick(Vector2(float(xy[0]), float(xy[1])), parts[0])
		player.bot_input.crouch_set = false


func _pick(px: Vector2, label: String) -> void:
	var cam: Camera3D = player.camera
	var vs := player.get_viewport().get_visible_rect().size
	var p := px * vs / Vector2(1920, 1080)
	var o := cam.project_ray_origin(p)
	var d := cam.project_ray_normal(p)
	var hits := []
	for n in player.get_tree().root.find_children("*", "GeometryInstance3D", true, false):
		var gi := n as GeometryInstance3D
		if not gi.is_visible_in_tree() or player.is_ancestor_of(gi):
			continue
		if not (gi is MeshInstance3D or gi is MultiMeshInstance3D):
			continue
		var ab: AABB = gi.global_transform * gi.get_aabb()
		var hit = ab.intersects_segment(o, o + d * 40.0)
		if hit == null and ab.has_point(o):
			hit = o
		if hit != null:
			hits.append([o.distance_to(hit), gi, ab])
	hits.sort_custom(func(a, b): return a[0] < b[0])
	var space := player.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(o, o + d * 40.0)
	q.exclude = [player.get_rid()]
	var rh: Dictionary = space.intersect_ray(q)
	L("PICK %s px %s ray-hit %s" % [label, px, (str(rh.position) + " " + str(rh.collider.get_path())) if not rh.is_empty() else "-"])
	for h in hits.slice(0, 7):
		var gi: GeometryInstance3D = h[1]
		L("   d %5.2f  %-28s %s  aabb %s..%s" % [h[0], _item_name(gi.get_parent()) + "/" + String(gi.name), str(gi.get_path()).right(70), h[2].position, h[2].end])


## --rv_wallgap: wall-mounted items (not standing on anything, not hung from
## above) whose back is not touching the nearest wall.
func wallgap() -> void:
	await _prep_static()
	var space: PhysicsDirectSpaceState3D = main.get_world_3d().direct_space_state
	var n := 0
	for it in _items():
		var bb := AABB()
		var first := true
		for mi in it[1]:
			var g := mi as MeshInstance3D
			if not g.is_visible_in_tree() or g.mesh == null:
				continue
			var a: AABB = (g.global_transform * g.get_aabb()).abs()
			bb = a if first else bb.merge(a)
			first = false
		if first or bb.size.y > 2.5 or bb.position.y < 0.3:
			continue
		var cx := bb.get_center()
		var qd := PhysicsRayQueryParameters3D.create(Vector3(cx.x, bb.position.y + 0.02, cx.z), Vector3(cx.x, bb.position.y - 0.06, cx.z), 1)
		if not space.intersect_ray(qd).is_empty():
			continue
		var qu := PhysicsRayQueryParameters3D.create(Vector3(cx.x, bb.end.y - 0.02, cx.z), Vector3(cx.x, bb.end.y + 0.15, cx.z), 1)
		if not space.intersect_ray(qu).is_empty():
			continue
		var best := 9.0
		var bdir := Vector3.ZERO
		for d in [Vector3.RIGHT, Vector3.LEFT, Vector3.FORWARD, Vector3.BACK]:
			var half: float = absf(bb.size.dot(d)) * 0.5
			for h in [0.25, 0.5, 0.75]:
				var o := Vector3(cx.x, bb.position.y + bb.size.y * h, cx.z)
				var q := PhysicsRayQueryParameters3D.create(o, o + d * (half + 0.6), 1)
				var r: Dictionary = space.intersect_ray(q)
				if r.is_empty():
					continue
				var gap: float = o.distance_to(r.position) - half
				if gap < best:
					best = gap
					bdir = d
		if best > 0.025 and best < 0.6:
			n += 1
			L("  WALLGAP %-30s @%s gap %.3f m toward %s  aabb %s..%s" % [_item_name(it[0]), cx.snapped(Vector3.ONE * 0.01), best, bdir, bb.position.snapped(Vector3.ONE * 0.001), bb.end.snapped(Vector3.ONE * 0.001)])
	L("WALLGAP items: %d" % n)


## --rv_crawl: the crouched player drives through the crawlway both ways
## (dock -> pump and back) on its own physics, after the M4.3 frame changes.
func _drive(target: Vector3, timeout: float, axis: String, past: float, label: String) -> bool:
	var t := 0.0
	var last := player.global_position
	var stall := 0.0
	var worst := 0.0
	while t < timeout:
		ap._look(Vector3(target.x, player.camera.global_position.y, target.z))
		player.bot_input.move = Vector2(0, -1)
		await W(0.1)
		t += 0.1
		var p := player.global_position
		if p.distance_to(last) < 0.02:
			stall += 0.1
			worst = maxf(worst, stall)
		else:
			stall = 0.0
		last = p
		var v: float = p.x if axis == "x" else p.z
		if (past < 0.0 and v <= past) or (past >= 0.0 and v >= past):
			player.bot_input.move = Vector2.ZERO
			L("  CRAWL %-34s reached %s=%.2f in %.1f s (longest stall %.1f s) PASS" % [label, axis, v, t, worst])
			return true
	player.bot_input.move = Vector2.ZERO
	L("  CRAWL %-34s FAIL: stuck at %s after %.1f s (longest stall %.1f s)" % [label, player.global_position.snapped(Vector3.ONE * 0.01), t, worst])
	return false


func crawl() -> void:
	await _prep_static()
	L("CRAWLWAY player traversal (crouched, scripted input, real collisions)")
	var ok := true
	ap.teleport(Vector3(1.5, 0.05, 2.0), Vector3(-9.0, 0.6, 2.0))
	player.bot_input.crouch_set = true
	await W(0.8)
	ok = await _drive(Vector3(-10.0, 0.6, 2.0), 15.0, "x", -9.6, "dock mouth -> corner (E-W leg)") and ok
	ok = await _drive(Vector3(-10.0, 0.6, -6.0), 10.0, "z", -4.0, "corner -> pump mouth (N-S leg)") and ok
	ok = await _drive(Vector3(-10.0, 0.6, 3.0), 10.0, "z", 1.6, "pump mouth -> corner (reverse)") and ok
	ok = await _drive(Vector3(2.0, 0.6, 2.0), 15.0, "x", 0.6, "corner -> dock mouth (reverse)") and ok
	player.bot_input.crouch_set = false
	L("CRAWLWAY traversal: %s" % ("PASS" if ok else "FAIL"))
