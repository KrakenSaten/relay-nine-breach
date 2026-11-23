class_name Director
extends Node
## Squad coordinator for the Teslabots.
## - Shared knowledge: last sighting, player velocity at sighting, prediction.
## - Alert propagation and role assignment (assault / cover / flanker /
##   overwatch / pusher).
## - Attack tokens plus a windup rhythm: at most MAX_SHOOTERS charge at once and
##   charges start at least WINDUP_SPACING apart, so pressure is constant but
##   every telegraph stays readable.
## - Squad plan (2 Hz): when the player hides, one unit holds overwatch on the
##   last known position while the others push from different angles.
## - Cover scoring, LOS-avoiding flank routes, distinct search points and
##   door "stack and enter" room-entry plans.

const MAX_SHOOTERS := 3
const ALERT_RADIUS := 22.0
const WINDUP_SPACING := 0.32

var bots: Array = []
var cover_points: Array = []   # {pos, normal, peek, peek2, owner}
var doors: Array = []          # {node, center, normal, rooms: [a, b]}
var alert_level := 0.0
var _shared_pos := Vector3.ZERO
var _shared_vel := Vector3.ZERO
var _shared_t := -100.0
var _tokens: Array = []
var _last_windup := -100.0
var _world: World3D
var _nav_map: RID
var _plan_t := 0.0
var _search_claims := {}       # bot -> Vector3
var _entries := {}             # door index -> {stack: [bots], start_t, go}
var hidden_for := 0.0          # seconds the player has been out of every unit's sight while engaged


func setup(world: World3D) -> void:
	_world = world
	_nav_map = world.navigation_map
	Game.director = self
	Game.reload_heard.connect(_on_reload_heard)


func now() -> float:
	return Time.get_ticks_msec() / 1000.0


func space() -> PhysicsDirectSpaceState3D:
	return _world.direct_space_state


func register(bot: Node) -> void:
	bots.append(bot)
	bot.director = self


func alive_count() -> int:
	var n := 0
	for b in bots:
		if b.state != Teslabot.S.DEAD:
			n += 1
	return n


func engaged() -> Array:
	return bots.filter(func(b): return b.state == Teslabot.S.COMBAT)


func snap(p: Vector3) -> Vector3:
	return NavigationServer3D.map_get_closest_point(_nav_map, p)


func _ray_clear(a: Vector3, b: Vector3) -> bool:
	var q := PhysicsRayQueryParameters3D.create(a, b, 1)
	return space().intersect_ray(q).is_empty()


# ------------------------------------------------------------------ knowledge
func report_sighting(_bot: Node, pos: Vector3) -> void:
	_shared_pos = pos
	_shared_t = now()
	if Game.player:
		_shared_vel = Game.player.velocity
		_shared_vel.y = 0
	alert_level = 1.0


func shared_last_known(fallback: Vector3) -> Vector3:
	if now() - _shared_t < 8.0:
		return _shared_pos
	return fallback


func since_seen() -> float:
	return now() - _shared_t


## Where the player probably is now: last sighting extrapolated along the
## velocity they had, capped, and snapped to the navmesh.
func predicted_position() -> Vector3:
	var dt := minf(since_seen(), 2.5)
	return snap(_shared_pos + _shared_vel * dt * 0.8)


func alert(source: Node, pos: Vector3) -> void:
	alert_level = 1.0
	for b in bots:
		if b == source or b.state == Teslabot.S.DEAD:
			continue
		if b.global_position.distance_to(source.global_position) < ALERT_RADIUS:
			b.alert_to(pos)


func _on_reload_heard(pos: Vector3) -> void:
	# A reload is an opening: units that hear it push hard for a moment.
	for b in engaged():
		if b.global_position.distance_to(pos) < 14.0:
			b.push(2.6)


# ------------------------------------------------------------------ roles
func assign_role(bot: Node) -> String:
	var others := engaged().filter(func(b): return b != bot)
	var has_flanker := false
	var covers := 0
	for b in others:
		if b.role == "flanker": has_flanker = true
		if b.role == "cover": covers += 1
	if others.size() >= 1 and not has_flanker and not bot.limp > 0.0:
		return "flanker"
	if covers <= others.size() / 2:
		return "cover"
	return "assault"


func _process(delta: float) -> void:
	alert_level = maxf(0.0, alert_level - delta * 0.02)
	_plan_t -= delta
	if _plan_t > 0.0:
		return
	_plan_t = 0.5
	_squad_plan()


## Fire-and-maneuver when the player breaks line of sight.
func _squad_plan() -> void:
	var eng := engaged()
	if eng.is_empty():
		hidden_for = 0.0
		return
	var any_visible := false
	for b in eng:
		if b.target_visible:
			any_visible = true
	hidden_for = 0.0 if any_visible else hidden_for + 0.5
	if hidden_for < 1.0 or eng.size() < 2:
		for b in eng:
			if b.role in ["overwatch", "pusher"] and any_visible:
				b.role = assign_role(b)
		return
	# One overwatch: the unit nearest the last known position with a clear
	# line to it holds that angle. Everyone else pushes from distinct bearings.
	var target := predicted_position()
	var ow: Node = null
	var best := INF
	for b in eng:
		var d: float = b.global_position.distance_to(target)
		if d < best and _ray_clear(b.eye_pos(), target + Vector3.UP * 1.2):
			best = d
			ow = b
	if ow == null:
		ow = eng[0]
	var k := 0
	for b in eng:
		if b == ow:
			b.role = "overwatch"
			continue
		if b.role != "pusher":
			b.role = "pusher"
			var ang := (1.2 if k % 2 == 0 else -1.2) * (1.0 + 0.4 * float(k / 2))
			b.set_push_target(_bearing_point(target, b.global_position, ang, 4.0))
			k += 1


func _bearing_point(target: Vector3, from: Vector3, ang: float, dist: float) -> Vector3:
	var to_from := from - target
	to_from.y = 0
	if to_from.length() < 0.1:
		to_from = Vector3.FORWARD
	return snap(target + to_from.normalized().rotated(Vector3.UP, ang) * dist)


# ------------------------------------------------------------------ attacks
func request_attack_token(bot: Node) -> bool:
	_tokens = _tokens.filter(func(b): return is_instance_valid(b) and b.state != Teslabot.S.DEAD)
	if bot in _tokens:
		return true
	if _tokens.size() >= MAX_SHOOTERS:
		return false
	# Stagger charge starts so telegraphs arrive as a readable rhythm.
	if now() - _last_windup < WINDUP_SPACING:
		return false
	_tokens.append(bot)
	_last_windup = now()
	return true


func release_attack_token(bot: Node) -> void:
	_tokens.erase(bot)


func on_bot_died(bot: Node) -> void:
	_tokens.erase(bot)
	release_cover(bot)
	_search_claims.erase(bot)
	for b in bots:
		if b != bot and b.state == Teslabot.S.COMBAT and b.global_position.distance_to(bot.global_position) < 15.0:
			b.suppress(bot.global_position, 0.5)   # a squadmate dropping makes them cautious
			if b.role == "assault" and randf() < 0.5:
				b.role = "cover"


## A unit got pinned: a free squadmate moves to flank (fire and maneuver).
func on_suppressed(bot: Node) -> void:
	for b in engaged():
		if b != bot and b.role in ["assault", "cover"] and b.suppression < 0.3:
			b.role = "flanker"
			return


# ------------------------------------------------------------------ flanking
## Pick a flank position around `target`, preferring routes the player cannot
## see (path samples tested against the player's eye) and bearings that open a
## crossfire with squadmates.
func flank_position(bot: Node, target: Vector3) -> Vector3:
	var to_bot: Vector3 = bot.global_position - target
	to_bot.y = 0
	var dist := clampf(to_bot.length(), 5.0, 9.0)
	var eye: Vector3 = Game.player.camera.global_position if Game.player else target + Vector3.UP * 1.6
	var best: Vector3 = bot.global_position
	var best_score := -INF
	for ang in [1.4, -1.4, 0.9, -0.9, 2.2, -2.2]:
		var dir := to_bot.normalized().rotated(Vector3.UP, ang)
		var want := target + dir * dist
		var cand := snap(want)
		if cand.distance_to(want) > 2.0:
			continue
		var score := -cand.distance_to(bot.global_position) * 0.25
		# Exposure along the route
		var path := NavigationServer3D.map_get_path(_nav_map, bot.global_position, cand, true)
		if path.size() < 2:
			continue
		var exposed := 0
		var samples := mini(path.size(), 6)
		for i in samples:
			var pt: Vector3 = path[int(float(i) / samples * (path.size() - 1))]
			if _ray_clear(pt + Vector3.UP * 1.5, eye):
				exposed += 1
		score -= exposed * 2.5
		# Crossfire: reward angular separation from other engaged units
		for b in engaged():
			if b == bot:
				continue
			var a1: Vector3 = (b.global_position - target)
			a1.y = 0
			var sep := rad_to_deg(a1.normalized().angle_to(dir))
			score += clampf(sep / 30.0, 0.0, 3.0)
			if b.global_position.distance_to(cand) < 3.0:
				score -= 5.0
		if score > best_score:
			best_score = score
			best = cand
	return best


# ------------------------------------------------------------------ cover
func release_cover(bot: Node) -> void:
	for c in cover_points:
		if c.owner == bot:
			c.owner = null


## Cover scoring: protection at body AND head height (crouched), distance,
## preferred engagement band, spacing from squadmates, and being outside the
## player's current view. Returns the chosen point with the best peek side.
func find_cover(bot: Node, threat: Vector3) -> Dictionary:
	var p: Node = Game.player
	var view_fwd := Vector3.FORWARD
	if p:
		view_fwd = -p.camera.global_transform.basis.z
		view_fwd.y = 0
		view_fwd = view_fwd.normalized()
	var cands := []
	for c in cover_points:
		if c.owner != null and is_instance_valid(c.owner) and c.owner != bot:
			continue
		var d: float = c.pos.distance_to(bot.global_position)
		var td: float = c.pos.distance_to(threat)
		if d > 16.0 or td < 4.0 or td > 22.0:
			continue
		var to_threat: Vector3 = (threat - c.pos)
		to_threat.y = 0
		if to_threat.normalized().dot(-c.normal) < 0.3:
			continue
		var score := d * 1.0 + absf(td - 10.0) * 0.4
		for b in bots:
			if b != bot and b.state != Teslabot.S.DEAD and b.global_position.distance_to(c.pos) < 3.0:
				score += 6.0
		# Prefer cover the player is not looking at (flank-side cover)
		var from_player: Vector3 = c.pos - threat
		from_player.y = 0
		score += maxf(0.0, view_fwd.dot(from_player.normalized())) * 4.0
		cands.append([score, c])
	cands.sort_custom(func(a, b): return a[0] < b[0])
	var tested := 0
	for e in cands:
		if tested > 7:
			break
		tested += 1
		var c: Dictionary = e[1]
		# Must protect the body; crouched head height (1.35) should be covered too.
		if _ray_clear(c.pos + Vector3.UP * 1.0, threat):
			continue
		var head_safe := not _ray_clear(c.pos + Vector3.UP * 1.35, threat)
		if not head_safe and tested < 5:
			continue
		# Choose the peek side that actually sees the threat.
		var peek: Vector3 = c.peek
		if c.has("peek2") and not _ray_clear(c.peek + Vector3.UP * 1.7, threat) and _ray_clear(c.peek2 + Vector3.UP * 1.7, threat):
			peek = c.peek2
		c.owner = bot
		var out := c.duplicate()
		out.peek = peek
		return out
	return {}


# ------------------------------------------------------------------ search
## Distinct search points per unit around the predicted position: the
## prediction itself first, then cover points (players hide behind cover).
func search_point(bot: Node) -> Vector3:
	var center = predicted_position() if since_seen() < 15.0 else bot.last_known
	var cands: Array = [center]
	var room := Game.room_at(center + Vector3.UP)
	for c in cover_points:
		if c.pos.distance_to(center) < 11.0 and Game.room_at(c.pos + Vector3.UP) == room:
			cands.append(c.pos - c.normal * 0.0)
	var best: Vector3 = center + Vector3(randf_range(-5, 5), 0, randf_range(-5, 5))
	var best_s := INF
	for pt in cands:
		var s: float = pt.distance_to(center) * 0.5 + pt.distance_to(bot.global_position) * 0.2 + randf() * 2.0
		for other in _search_claims:
			if other != bot and is_instance_valid(other) and _search_claims[other].distance_to(pt) < 3.0:
				s += 8.0
		if bot.visited_recently(pt):
			s += 10.0
		if s < best_s:
			best_s = s
			best = pt
	best = snap(best)
	_search_claims[bot] = best
	return best


# ------------------------------------------------------------------ room entry
func setup_doors(door_nodes: Dictionary) -> void:
	doors.clear()
	for id in door_nodes:
		var d: Node3D = door_nodes[id]
		var center: Vector3 = d.global_position + d.global_transform.basis.x * (d.width * 0.5)
		var n: Vector3 = d.global_transform.basis.z
		n.y = 0
		n = n.normalized()
		var ra := Game.room_at(center + n * 1.5 + Vector3.UP)
		var rb := Game.room_at(center - n * 1.5 + Vector3.UP)
		doors.append({"node": d, "center": center, "normal": n, "rooms": [ra, rb], "id": id})


## If `bot` is near a doorway that leads into the room containing `target`,
## return an entry plan: stack outside on one side, then enter crossing.
func plan_entry(bot: Node, target: Vector3) -> Dictionary:
	var my_room := Game.room_at(bot.global_position + Vector3.UP)
	var t_room := Game.room_at(target + Vector3.UP)
	if my_room == "" or t_room == "" or my_room == t_room:
		return {}
	for i in doors.size():
		var dd: Dictionary = doors[i]
		if dd.node.locked:
			continue
		var rooms: Array = dd.rooms
		if not (my_room in rooms and t_room in rooms):
			continue
		var c: Vector3 = dd.center
		if bot.global_position.distance_to(c) > 8.0:
			continue
		# Which side is the bot on?
		var side := 1.0 if (bot.global_position - c).dot(dd.normal) > 0.0 else -1.0
		var out_n: Vector3 = dd.normal * side   # points to the bot's side
		var lat := out_n.cross(Vector3.UP).normalized()
		if not _entries.has(i):
			_entries[i] = {"stack": [], "start": now()}
		var e: Dictionary = _entries[i]
		e.stack = e.stack.filter(func(b): return is_instance_valid(b) and b.state != Teslabot.S.DEAD)
		if not bot in e.stack:
			e.stack.append(bot)
		var slot: int = e.stack.find(bot)
		var lat_sign := 1.0 if slot % 2 == 0 else -1.0
		return {
			"door": i,
			"stack": snap(c + out_n * 2.2 + lat * 1.1 * lat_sign),
			"inside": snap(c - out_n * 2.6 + lat * 1.6 * lat_sign),
			"slot": slot,
			"look": c - out_n * 4.0,
		}
	return {}


## Entry may begin once two units are stacked or the first has waited 2.5 s.
func entry_go(door_i: int, bot: Node) -> bool:
	if not _entries.has(door_i):
		return true
	var e: Dictionary = _entries[door_i]
	var ready := 0
	for b in e.stack:
		if is_instance_valid(b) and b._entry.get("phase", "") == "stacked":
			ready += 1
	var slot: int = e.stack.find(bot)
	var waited := now() - float(e.start)
	if ready >= 2 or waited > 2.5 or e.stack.size() == 1 and waited > 1.5:
		# Second unit follows the first by a beat.
		return slot <= 0 or waited > 0.6 + slot * 0.7
	return false


func entry_done(door_i: int, bot: Node) -> void:
	if _entries.has(door_i):
		var e: Dictionary = _entries[door_i]
		e.stack.erase(bot)
		if e.stack.is_empty():
			_entries.erase(door_i)


func door_node(door_i: int) -> Node:
	return doors[door_i].node
