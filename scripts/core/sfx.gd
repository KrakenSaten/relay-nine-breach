extends Node
## Pooled positional and UI audio. Sounds live in res://assets/audio/<name>.wav;
## a name with numbered variants (impact_metal_0..2) is picked at random.

const DIR := "res://assets/audio/"
const POOL_3D := 40
const POOL_2D := 12
const POOL_WEAPON := 40     # the player's gunfire layers (close, mechanics, room response)
const POOL_SLAP := 12       # positional early reflections from nearby walls

var _cache := {}
var _variants := {}
var _pool3d: Array[AudioStreamPlayer3D] = []
var _pool2d: Array[AudioStreamPlayer] = []
var _i3 := 0
var _i2 := 0
var _poolw: Array[AudioStreamPlayer] = []
var _pools: Array[AudioStreamPlayer3D] = []
var _iw := 0
var _is := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_buses()
	for i in POOL_3D:
		var p := AudioStreamPlayer3D.new()
		p.unit_size = 6.0
		p.max_distance = 70.0
		p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
		p.attenuation_filter_cutoff_hz = 6000.0
		p.attenuation_filter_db = -18.0
		p.panning_strength = 1.0
		p.area_mask = 1 << 5
		add_child(p)
		_pool3d.append(p)
	for i in POOL_2D:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_pool2d.append(p)
	# Gunfire bypasses the generic room-reverb zones: the room response is an
	# authored layer chosen by room size (no doubled reverb).
	for i in POOL_WEAPON:
		var p := AudioStreamPlayer.new()
		p.bus = "Weapons"
		add_child(p)
		_poolw.append(p)
	for i in POOL_SLAP:
		var p := AudioStreamPlayer3D.new()
		p.bus = "Weapons"
		p.area_mask = 0
		p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED
		p.max_distance = 0.0
		p.panning_strength = 1.0
		p.attenuation_filter_db = 0.0
		add_child(p)
		_pools.append(p)


func stream(name: String) -> AudioStream:
	if not _variants.has(name):
		var list: Array[String] = []
		if ResourceLoader.exists(DIR + name + ".wav"):
			list.append(name)
		else:
			var i := 0
			while ResourceLoader.exists(DIR + "%s_%d.wav" % [name, i]):
				list.append("%s_%d" % [name, i])
				i += 1
		_variants[name] = list
	var vs: Array = _variants[name]
	if vs.is_empty():
		push_warning("Missing sound: " + name)
		return null
	var pick: String = vs[randi() % vs.size()]
	if not _cache.has(pick):
		_cache[pick] = load(DIR + pick + ".wav")
	return _cache[pick]


func play_3d(name: String, pos: Vector3, volume_db := 0.0, pitch_var := 0.06, unit := 6.0) -> void:
	var s := stream(name)
	if s == null:
		return
	var p := _pool3d[_i3]
	_i3 = (_i3 + 1) % POOL_3D
	p.stream = s
	p.global_position = pos
	p.volume_db = volume_db
	p.unit_size = unit
	p.pitch_scale = 1.0 + randf_range(-pitch_var, pitch_var)
	p.play()


func play(name: String, volume_db := 0.0, pitch_var := 0.04) -> void:
	var s := stream(name)
	if s == null:
		return
	var p := _pool2d[_i2]
	_i2 = (_i2 + 1) % POOL_2D
	p.stream = s
	p.volume_db = volume_db
	p.pitch_scale = 1.0 + randf_range(-pitch_var, pitch_var)
	p.play()


## One layer of the player's own gunfire (2D, Weapons bus).
func weapon_layer(name: String, volume_db := 0.0, pitch_var := 0.03) -> void:
	var s := stream(name)
	if s == null:
		return
	var p := _poolw[_iw]
	_iw = (_iw + 1) % POOL_WEAPON
	p.stream = s
	p.volume_db = volume_db
	p.pitch_scale = 1.0 + randf_range(-pitch_var, pitch_var)
	p.play()


## A positional early reflection (heard from the wall's direction).
func weapon_slap(name: String, pos: Vector3, volume_db: float) -> void:
	var s := stream(name)
	if s == null:
		return
	var p := _pools[_is]
	_is = (_is + 1) % POOL_SLAP
	p.stream = s
	p.global_position = pos
	p.volume_db = volume_db
	p.pitch_scale = 1.0 + randf_range(-0.03, 0.03)
	p.play()


## Looping emitter attached to a node (ambience, robot hum).
func loop_3d(name: String, parent: Node3D, volume_db := -6.0, unit := 3.0) -> AudioStreamPlayer3D:
	var s := stream(name)
	if s == null:
		return null
	s = s.duplicate()
	if s is AudioStreamWAV:
		s.loop_mode = AudioStreamWAV.LOOP_FORWARD
		s.loop_end = int(s.get_length() * s.mix_rate)
	var p := AudioStreamPlayer3D.new()
	p.stream = s
	p.volume_db = volume_db
	p.unit_size = unit
	p.max_distance = 30.0
	p.autoplay = true
	p.area_mask = 1 << 5
	parent.add_child(p)
	return p


func loop_2d(name: String, volume_db := -10.0) -> AudioStreamPlayer:
	var s := stream(name)
	if s == null:
		return null
	s = s.duplicate()
	if s is AudioStreamWAV:
		s.loop_mode = AudioStreamWAV.LOOP_FORWARD
		s.loop_end = int(s.get_length() * s.mix_rate)
	var p := AudioStreamPlayer.new()
	p.stream = s
	p.volume_db = volume_db
	add_child(p)
	p.play()
	return p



# ---------------------------------------------------------------- M2 spatial audio
## Reverb buses used by per-room Area3D reverb zones (see LevelBuilder).
const REVERBS := {
	"Rev_Small": {"room": 0.38, "damp": 0.55, "wet": 0.22, "pre": 12.0, "spread": 0.8},
	"Rev_Hall": {"room": 0.92, "damp": 0.32, "wet": 0.34, "pre": 55.0, "spread": 1.0},
	"Rev_Servers": {"room": 0.45, "damp": 0.75, "wet": 0.18, "pre": 10.0, "spread": 0.7},
	"Rev_Dock": {"room": 0.75, "damp": 0.4, "wet": 0.28, "pre": 35.0, "spread": 1.0},
}


func _setup_buses() -> void:
	if AudioServer.get_bus_index("Weapons") == -1:
		AudioServer.add_bus()
		var wi := AudioServer.bus_count - 1
		AudioServer.set_bus_name(wi, "Weapons")
		AudioServer.set_bus_send(wi, "Master")
	for name in REVERBS:
		if AudioServer.get_bus_index(name) != -1:
			continue
		AudioServer.add_bus()
		var i := AudioServer.bus_count - 1
		AudioServer.set_bus_name(i, name)
		AudioServer.set_bus_send(i, "Master")
		var r := AudioEffectReverb.new()
		var c: Dictionary = REVERBS[name]
		r.room_size = c.room
		r.damping = c.damp
		r.wet = c.wet
		r.dry = 0.0
		r.predelay_msec = c.pre
		r.spread = c.spread
		r.hipass = 0.15
		AudioServer.add_bus_effect(i, r)
	# Gentle master limiter: dense firefights must not clip.
	if AudioServer.get_bus_effect_count(0) == 0:
		var lim := AudioEffectHardLimiter.new()
		lim.ceiling_db = -0.5
		AudioServer.add_bus_effect(0, lim)


## A one-shot at the listener (player weapon, foley). Played as 3D so room
## reverb zones apply, with zero distance attenuation.
func play_local(name: String, volume_db := 0.0, pitch_var := 0.04) -> void:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		play(name, volume_db, pitch_var)
		return
	play_3d(name, cam.global_position + Vector3(0, -0.1, 0), volume_db + 2.0, pitch_var, 40.0)
