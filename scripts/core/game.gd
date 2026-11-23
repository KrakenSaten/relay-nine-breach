extends Node
## Mission state, world events (noise), room lighting state and run statistics.

signal objective_changed(text: String, target: Vector3)
signal mission_state_changed(state: int)
signal noise(pos: Vector3, radius: float, source: Node)
signal hack_progress(value: float)
signal message(text: String, seconds: float)
signal request_loadout

enum State { BRIEFING, INFILTRATE, HACK, EXTRACT, COMPLETE, FAILED }

var state := State.BRIEFING
var player: Node = null
var director: Node = null
var objective_text := ""
var objective_pos := Vector3.ZERO
var rooms := {}            # name -> {aabb: AABB, lit: bool, lights: Array}
var stats := {}
var start_time := 0.0
var autotest := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	autotest = "--autotest" in OS.get_cmdline_user_args() or "--bench" in OS.get_cmdline_user_args()
	reset_stats()


func reset_stats() -> void:
	stats = {"shots": 0, "hits": 0, "kills": 0, "head_hits": 0, "core_hits": 0, "core_kills": 0, "damage_taken": 0, "time": 0.0}


func begin_mission() -> void:
	reset_stats()
	start_time = Time.get_ticks_msec() / 1000.0
	set_state(State.INFILTRATE)


func set_state(s: int) -> void:
	state = s
	mission_state_changed.emit(s)


func set_objective(text: String, pos: Vector3) -> void:
	objective_text = text
	objective_pos = pos
	objective_changed.emit(text, pos)
	Sfx.play("ui_objective", -6.0, 0.0)


func elapsed() -> float:
	return Time.get_ticks_msec() / 1000.0 - start_time


func emit_noise(pos: Vector3, radius: float, source: Node = null) -> void:
	noise.emit(pos, radius, source)


func say(text: String, seconds := 3.0) -> void:
	message.emit(text, seconds)


# --- Rooms -----------------------------------------------------------------
func add_room(name: String, aabb: AABB) -> void:
	rooms[name] = {"aabb": aabb, "lit": true, "lights": []}


func room_at(p: Vector3) -> String:
	for n in rooms:
		if rooms[n].aabb.has_point(p):
			return n
	return ""


func is_lit(p: Vector3) -> bool:
	var r := room_at(p)
	return r == "" or rooms[r].lit


func set_room_lit(name: String, lit: bool) -> void:
	if not rooms.has(name):
		return
	rooms[name].lit = lit
	for l in rooms[name].lights:
		if is_instance_valid(l):
			l.visible = lit
