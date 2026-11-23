extends Node
## Mission state, world events (noise), room lighting state and run statistics.

signal objective_changed(text: String, target: Vector3)
signal mission_state_changed(state: int)
signal noise(pos: Vector3, radius: float, source: Node)
signal hack_progress(value: float)
signal message(text: String, seconds: float)
signal request_loadout
signal reload_heard(pos: Vector3)

enum State { BRIEFING, INFILTRATE, HACK, EXTRACT, COMPLETE, FAILED, CORE }

var state := State.BRIEFING
var player: Node = null
var director: Node = null
var objective_text := ""
var objective_pos := Vector3.ZERO
var rooms := {}            # name -> {aabb: AABB, lit: bool, lights: Array}
var stats := {}
var start_time := 0.0
var autotest := false
var emergency := false     # relay countermeasures active (red lighting, alarm)
var checkpoint := {}       # survives scene reloads; filled by Mission
var _obscured := {}        # room -> time (s) until which it is filled with steam


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	autotest = "--autotest" in OS.get_cmdline_user_args() or "--bench" in OS.get_cmdline_user_args()
	reset_stats()


func reset_stats() -> void:
	stats = {"shots": 0, "hits": 0, "kills": 0, "head_hits": 0, "core_hits": 0, "core_kills": 0, "damage_taken": 0, "time": 0.0}


func begin_mission() -> void:
	reset_stats()
	start_time = Time.get_ticks_msec() / 1000.0
	emergency = false
	_obscured.clear()
	set_state(State.INFILTRATE)


func is_active() -> bool:
	return state in [State.INFILTRATE, State.HACK, State.EXTRACT, State.CORE]


# --- Steam / smoke ----------------------------------------------------------
func obscure_room(name: String, seconds: float) -> void:
	_obscured[name] = Time.get_ticks_msec() / 1000.0 + seconds


func room_obscured(name: String) -> bool:
	return name != "" and _obscured.get(name, 0.0) > Time.get_ticks_msec() / 1000.0


func set_state(s: int) -> void:
	state = s
	mission_state_changed.emit(s)


func set_objective(text: String, pos: Vector3, quiet := false) -> void:
	var changed := text != objective_text
	objective_text = text
	objective_pos = pos
	objective_changed.emit(text, pos)
	if changed and not quiet:
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
