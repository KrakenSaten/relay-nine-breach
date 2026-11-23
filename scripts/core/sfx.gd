extends Node
## Pooled positional and UI audio. Sounds live in res://assets/audio/<name>.wav;
## a name with numbered variants (impact_metal_0..2) is picked at random.

const DIR := "res://assets/audio/"
const POOL_3D := 40
const POOL_2D := 12

var _cache := {}
var _variants := {}
var _pool3d: Array[AudioStreamPlayer3D] = []
var _pool2d: Array[AudioStreamPlayer] = []
var _i3 := 0
var _i2 := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in POOL_3D:
		var p := AudioStreamPlayer3D.new()
		p.unit_size = 6.0
		p.max_distance = 70.0
		p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
		p.attenuation_filter_cutoff_hz = 6000.0
		p.attenuation_filter_db = -18.0
		p.panning_strength = 1.0
		add_child(p)
		_pool3d.append(p)
	for i in POOL_2D:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_pool2d.append(p)


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
