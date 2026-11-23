extends Node3D
## Relay Nine uplink console. Hold F to connect, then defend the console while
## the override uploads. A robot standing at the console jams the upload.

signal connected
signal completed

const CONNECT_TIME := 2.0
const UPLOAD_TIME := 40.0

var connecting := 0.0
var uploading := false
var done := false
var progress := 0.0
var jammed := false
var screen_light: OmniLight3D
var powered := true                 # M4: needs main power (switchgear breakers)
var unpowered_text := "CONSOLE UNPOWERED"
var _tick := 0.0


func get_prompt(_p: Node) -> String:
	if done:
		return ""
	if uploading:
		return "UPLINK ACTIVE - DEFEND THE CONSOLE"
	if Game.state != Game.State.INFILTRATE:
		return ""
	if not powered:
		return unpowered_text
	return "[HOLD F] CONNECT RELAY OVERRIDE"


func hold(_p: Node, delta: float) -> float:
	if uploading or done or not powered or Game.state != Game.State.INFILTRATE:
		return 0.0
	if delta < 0.0:
		connecting = 0.0
		return 0.0
	connecting += delta
	_tick -= delta
	if _tick <= 0.0:
		_tick = 0.25
		Sfx.play("ui_hack_tick", -8.0)
	if connecting >= CONNECT_TIME:
		uploading = true
		Sfx.play("ui_hack_done", -2.0)
		connected.emit()
	return connecting / CONNECT_TIME


func _process(delta: float) -> void:
	if not uploading or done:
		return
	jammed = false
	for b in get_tree().get_nodes_in_group("teslabot"):
		if b.state != Teslabot.S.DEAD and b.global_position.distance_to(global_position) < 3.0:
			jammed = true
			break
	if not jammed:
		progress = minf(1.0, progress + delta / UPLOAD_TIME)
	Game.hack_progress.emit(progress)
	if screen_light:
		screen_light.light_energy = 1.2 + sin(Time.get_ticks_msec() / 90.0) * 0.3 if not jammed else randf_range(0.0, 1.5)
	if progress >= 1.0:
		done = true
		uploading = false
		Sfx.play("ui_hack_done", 0.0)
		completed.emit()
