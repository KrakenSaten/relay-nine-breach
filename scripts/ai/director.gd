class_name Director
extends Node
## Squad coordinator: shared knowledge, alert propagation, attack tokens
## (limits simultaneous shooters so CQB stays lethal but readable), role
## assignment (assault / cover / flanker) and cover-point selection.

const MAX_SHOOTERS := 3
const ALERT_RADIUS := 22.0

var bots: Array = []
var cover_points: Array = []   # {pos, normal, peek, owner}
var alert_level := 0.0
var _shared_pos := Vector3.ZERO
var _shared_t := -100.0
var _tokens: Array = []
var _world: World3D
var _nav_map: RID


func setup(world: World3D) -> void:
	_world = world
	_nav_map = world.navigation_map
	Game.director = self


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


func _process(delta: float) -> void:
	alert_level = maxf(0.0, alert_level - delta * 0.02)


func snap(p: Vector3) -> Vector3:
	return NavigationServer3D.map_get_closest_point(_nav_map, p)


func report_sighting(bot: Node, pos: Vector3) -> void:
	_shared_pos = pos
	_shared_t = Time.get_ticks_msec() / 1000.0
	alert_level = 1.0


func shared_last_known(fallback: Vector3) -> Vector3:
	if Time.get_ticks_msec() / 1000.0 - _shared_t < 6.0:
		return _shared_pos
	return fallback


func alert(source: Node, pos: Vector3) -> void:
	alert_level = 1.0
	for b in bots:
		if b == source or b.state == Teslabot.S.DEAD:
			continue
		if b.global_position.distance_to(source.global_position) < ALERT_RADIUS:
			b.alert_to(pos)


func assign_role(bot: Node) -> String:
	var engaged := 0
	var has_flanker := false
	var covers := 0
	for b in bots:
		if b.state == Teslabot.S.COMBAT and b != bot:
			engaged += 1
			if b.role == "flanker": has_flanker = true
			if b.role == "cover": covers += 1
	if engaged >= 1 and not has_flanker and not bot.limp > 0.0:
		return "flanker"
	if covers <= engaged / 2:
		return "cover"
	return "assault"


func request_attack_token(bot: Node) -> bool:
	_tokens = _tokens.filter(func(b): return is_instance_valid(b) and b.state != Teslabot.S.DEAD)
	if bot in _tokens:
		return true
	if _tokens.size() < MAX_SHOOTERS:
		_tokens.append(bot)
		return true
	return false


func release_attack_token(bot: Node) -> void:
	_tokens.erase(bot)


func on_bot_died(bot: Node) -> void:
	_tokens.erase(bot)
	release_cover(bot)
	# A squadmate going down pushes others to reposition.
	for b in bots:
		if b != bot and b.state == Teslabot.S.COMBAT and b.global_position.distance_to(bot.global_position) < 15.0:
			if b.role == "assault" and randf() < 0.5:
				b.role = "cover"


func flank_position(bot: Node, target: Vector3) -> Vector3:
	var to_bot: Vector3 = bot.global_position - target
	to_bot.y = 0
	var dist := clampf(to_bot.length(), 5.0, 9.0)
	var best = bot.global_position
	var best_score := -INF
	for ang in [1.4, -1.4, 0.9, -0.9, 2.2, -2.2]:
		var dir := to_bot.normalized().rotated(Vector3.UP, ang)
		var cand := snap(target + dir * dist)
		if cand.distance_to(target + dir * dist) > 2.0:
			continue
		# Prefer positions not occupied by squadmates and with a path.
		var score := -cand.distance_to(bot.global_position) * 0.3
		for b in bots:
			if b != bot and b.state != Teslabot.S.DEAD and b.global_position.distance_to(cand) < 3.0:
				score -= 5.0
		if score > best_score:
			best_score = score
			best = cand
	return best


func release_cover(bot: Node) -> void:
	for c in cover_points:
		if c.owner == bot:
			c.owner = null


func find_cover(bot: Node, threat: Vector3) -> Dictionary:
	var cands := []
	for c in cover_points:
		if c.owner != null and is_instance_valid(c.owner) and c.owner != bot:
			continue
		var d: float = c.pos.distance_to(bot.global_position)
		var td: float = c.pos.distance_to(threat)
		if d > 16.0 or td < 4.0 or td > 22.0:
			continue
		# The cover must face the threat.
		var to_threat: Vector3 = (threat - c.pos)
		to_threat.y = 0
		if to_threat.normalized().dot(-c.normal) < 0.3:
			continue
		cands.append([d + td * 0.2, c])
	cands.sort_custom(func(a, b): return a[0] < b[0])
	var tested := 0
	for e in cands:
		if tested > 6:
			break
		tested += 1
		var c: Dictionary = e[1]
		var hide_eye: Vector3 = c.pos + Vector3.UP * 1.0
		var q := PhysicsRayQueryParameters3D.create(hide_eye, threat, 1)
		if space().intersect_ray(q).is_empty():
			continue  # not actually protected at body height
		c.owner = bot
		return c
	return {}
