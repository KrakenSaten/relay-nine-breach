class_name BriefingIntel
extends RefCounted
## Facility plan and mission intel for the briefing map, read from the built
## level rather than authored twice: the static collision boxes (walls,
## machinery, galleries), Game.rooms, the doors, the mission objects and the
## encounter roster.

const NAMES := {
	"dock": "LOADING DOCK", "corridor": "SERVICE CORRIDOR C", "office": "SECURITY OFFICE 9-B",
	"passage": "SHUTTER", "hall": "TURBINE HALL", "servers": "DATA CENTRE", "control": "RELAY CONTROL",
	"pump": "PUMP STATION 2", "tunnel": "SERVICE TUNNEL S-2", "crawl": "CRAWLWAY",
	"switchgear": "SWITCHGEAR HALL", "antechamber": "ANTECHAMBER", "core": "RELAY NINE CORE",
}
## World XZ bounds of the map (metres): 8 x 8 grid squares of 10 m.
const ORIGIN := Vector2(-26.0, -64.0)
const CELL := 10.0
const COLS := 8
const ROWS := 8

static var _plan := {}   # the facility geometry never changes, so it survives scene reloads


## Footprints of the static collision boxes, classified for drawing.
static func plan(level: LevelBuilder) -> Dictionary:
	if not _plan.is_empty():
		return _plan
	var walls: Array[PackedVector2Array] = []
	var solids: Array[PackedVector2Array] = []
	var low: Array[PackedVector2Array] = []
	var galleries: Array[PackedVector2Array] = []
	for sb in level.find_children("*", "StaticBody3D", true, false):
		for cs in sb.get_children():
			if not (cs is CollisionShape3D) or not (cs.shape is BoxShape3D):
				continue
			var t: Transform3D = cs.global_transform
			var h: Vector3 = (cs.shape as BoxShape3D).size * 0.5
			var ext_y := absf(t.basis.x.y) * h.x + absf(t.basis.y.y) * h.y + absf(t.basis.z.y) * h.z
			var y0 := t.origin.y - ext_y
			var y1 := t.origin.y + ext_y
			var c := Vector2(t.origin.x, t.origin.z)
			var ax := Vector2(t.basis.x.x, t.basis.x.z) * h.x
			var az := Vector2(t.basis.z.x, t.basis.z.z) * h.z
			if absf(t.basis.y.normalized().y) < 0.99:   # tilted box (ramps, stairs): its xz bounding rectangle
				var ay := Vector2(t.basis.y.x, t.basis.y.z) * h.y
				var e := Vector2(absf(ax.x) + absf(ay.x) + absf(az.x), absf(ax.y) + absf(ay.y) + absf(az.y))
				ax = Vector2(e.x, 0)
				az = Vector2(0, e.y)
			var poly := PackedVector2Array([c - ax - az, c + ax - az, c + ax + az, c - ax + az])
			var w := ax.length() * 2.0
			var d := az.length() * 2.0
			var thin := minf(w, d)
			var tall := y1 - y0
			if y1 < 0.1 or y0 > 6.0:
				continue                                  # floors, roofs
			if y0 > 3.3 and y0 < 5.2 and tall < 0.6 and w * d > 3.0:
				var r := Game.room_at(Vector3(c.x, 1.0, c.y))
				if r != "" and Game.rooms[r].aabb.size.y >= 9.0:
					galleries.append(poly)                # upper walkways in the tall halls (not low ceilings)
			elif y0 < 0.5 and thin <= 0.45 and tall >= 1.1 and maxf(w, d) >= 0.3:
				walls.append(poly)
			elif y0 < 1.0 and y1 > 1.6:
				(walls if tall >= 2.4 and thin <= 0.7 else solids).append(poly)
			elif y0 < 0.3 and y1 > 0.5:
				low.append(poly)
	_plan = {"walls": walls, "solids": solids, "low": low, "galleries": galleries}
	return _plan


static func grid_ref(p: Vector2) -> String:
	var cx := clampi(int(floor((p.x - ORIGIN.x) / CELL)), 0, COLS - 1)
	var cy := clampi(int(floor((p.y - ORIGIN.y) / CELL)), 0, ROWS - 1)
	return "%s%d" % ["ABCDEFGH"[cx], cy + 1]


static func xz(v: Vector3) -> Vector2:
	return Vector2(v.x, v.z)


## Everything the briefing shows about the operation, from the live mission.
static func gather(main: Node) -> Dictionary:
	var level: LevelBuilder = main.level
	var mission: Mission = main.mission
	var ex: Expansion = level.expansion
	var rooms := []
	for id in Game.rooms:
		var a: AABB = Game.rooms[id].aabb
		rooms.append({"id": id, "name": NAMES.get(id, id.to_upper()), "rect": Rect2(a.position.x, a.position.z, a.size.x, a.size.z)})
	var doors := []
	for id in level.doors:
		var d: Door = level.doors[id]
		var dir := d.global_transform.basis.x
		var a := xz(d.global_position)
		doors.append({"id": id, "a": a, "b": a + Vector2(dir.x, dir.z).normalized() * d.width, "sealed": d.locked})
	var blast := xz(ex.blast_door.global_position)
	doors.append({"id": "BLAST", "a": blast - Vector2(1.5, 0), "b": blast + Vector2(1.5, 0),
		"sealed": not mission.flags.complication, "blast": true})
	var f: Dictionary = mission.flags
	var markers := [
		{"id": "INS", "kind": "insertion", "pos": xz(level.player_start.origin), "label": "INSERTION", "sub": "LOADING DOCK"},
		{"id": "01", "kind": "objective", "pos": xz(ex.lockdown_panel.global_position), "label": "LOCKDOWN PANEL", "sub": "SECURITY OFFICE 9-B", "done": f.lockdown},
		{"id": "02A", "kind": "objective", "pos": xz(ex.breakers[0].global_position), "label": "BREAKER A", "sub": "SOUTH WALL", "done": f.power >= 1},
		{"id": "02B", "kind": "objective", "pos": xz(ex.breakers[1].global_position), "label": "BREAKER B", "sub": "EAST GALLERY  +%.1f M" % ex.breakers[1].global_position.y, "done": f.power >= 2},
		{"id": "03", "kind": "objective", "pos": xz(level.console.global_position), "label": "OVERRIDE CONSOLE", "sub": "RELAY CONTROL", "done": f.upload},
		{"id": "04", "kind": "extract", "pos": xz(ex.lift_panel.global_position), "label": "FREIGHT LIFT 2", "sub": "EXTRACTION", "done": Game.state == Game.State.COMPLETE, "tag_left": true},
		{"id": "STM", "kind": "aux", "pos": xz(ex.steam_valve.global_position), "label": "STEAM PURGE", "sub": "VALVE, EAST DOOR"},
	]
	for i in ex.caches.size():
		markers.append({"id": "AM%d" % (i + 1), "kind": "ammo", "pos": xz(ex.caches[i].global_position), "label": "AMMUNITION", "sub": "LIMITED STOCK"})
	if f.complication:
		markers.append({"id": "CORE", "kind": "objective", "pos": xz(ex.core_center), "label": "CAPACITOR STACKS", "sub": "RELAY NINE CORE", "done": f.core})
	# Pre-deployment estimate: the start roster at its posts and patrol starts.
	var threats := []
	var counts := {}
	for id in Mission.START_SET:
		var s: Dictionary = mission.specs[id]
		threats.append({"pos": xz(s.pos), "dormant": s.dormant})
		var r := Game.room_at(s.pos + Vector3.UP * 0.5)
		if not counts.has(r):
			counts[r] = [0, 0]
		counts[r][1 if s.dormant else 0] += 1
	var routes := [
		{"id": "B", "label": "B  SHUTTER", "pts": PackedVector2Array([Vector2(13.25, 4.0), Vector2(13.25, -1.0), Vector2(13.6, -5.5)])},
		{"id": "C", "label": "C  CRAWLWAY", "pts": PackedVector2Array([Vector2(3.0, 6.5), Vector2(0.4, 2.0), Vector2(-10.0, 2.0), Vector2(-10.0, -3.0), Vector2(-11.5, -6.0)])},
	]
	var nav: RID = main.get_world_3d().navigation_map
	var start := level.player_start.origin
	for tgt in [["A", ex.lockdown_panel.global_position + Vector3(0, 0, 1.0)], ["A2", ex.breakers[0].global_position + Vector3(0, 0, -1.0)]]:
		var path := NavigationServer3D.map_get_path(nav, start, tgt[1], true)
		if path.size() > 1:
			var pts := PackedVector2Array()
			for p in path:
				pts.append(xz(p))
			routes.append({"id": tgt[0], "label": "A  SERVICE CORRIDOR C" if tgt[0] == "A" else "", "pts": pts, "primary": true})
	var player_pos := Vector2.INF
	var player_dir := Vector2.ZERO
	if Game.player and Game.is_active():
		player_pos = xz(Game.player.global_position)
		var fwd: Vector3 = -Game.player.global_transform.basis.z
		player_dir = Vector2(fwd.x, fwd.z).normalized()
	return {"rooms": rooms, "doors": doors, "markers": markers, "threats": threats, "counts": counts, "routes": routes,
		"player": player_pos, "player_dir": player_dir, "current": xz(Game.objective_pos) if Game.is_active() else Vector2.INF}
