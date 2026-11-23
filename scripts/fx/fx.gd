extends Node
## Pooled combat effects: impact sparks/dust, decals, tracers, tesla arcs,
## light flashes and robot core overload bursts.

const SPARK_POOL := 20
const DUST_POOL := 16
const DECAL_MAX := 96

var _world: Node3D
var _sparks: Array[GPUParticles3D] = []
var _blue_sparks: Array[GPUParticles3D] = []
var _dust: Array[GPUParticles3D] = []
var _smoke: Array[GPUParticles3D] = []
var _decals: Array[Decal] = []
var _si := 0
var _bi := 0
var _di := 0
var _mi := 0
var _deci := 0
var _hole_tex: Texture2D
var _scorch_tex: Texture2D
var _soft_tex: Texture2D
var _arc_mat: StandardMaterial3D
var _arc_core_mat: StandardMaterial3D
var _tracer_mat: StandardMaterial3D


func setup(world: Node3D) -> void:
	_world = world
	_sparks.clear(); _blue_sparks.clear(); _dust.clear(); _smoke.clear(); _decals.clear()
	_soft_tex = _radial([Color(1, 1, 1, 1), Color(1, 1, 1, 0.35), Color(1, 1, 1, 0)], [0.0, 0.35, 1.0], 64)
	_hole_tex = _radial([Color(0.01, 0.01, 0.01, 1), Color(0.03, 0.03, 0.03, 0.95), Color(0.12, 0.11, 0.1, 0.5), Color(0, 0, 0, 0)], [0.0, 0.18, 0.4, 1.0], 64)
	_scorch_tex = _radial([Color(0.0, 0.0, 0.0, 0.9), Color(0.02, 0.02, 0.025, 0.6), Color(0, 0, 0, 0)], [0.0, 0.4, 1.0], 128)
	_arc_mat = MatLib.unshaded(Color(0.45, 0.68, 1.0, 0.75))
	_arc_core_mat = MatLib.unshaded(Color(0.95, 0.98, 1.0, 1.0))
	_tracer_mat = MatLib.unshaded(Color(1.0, 0.75, 0.4, 0.55))
	for i in SPARK_POOL:
		_sparks.append(_make_sparks(Color(1.0, 0.62, 0.22), 18))
		_blue_sparks.append(_make_sparks(Color(0.55, 0.8, 1.0), 26))
	for i in DUST_POOL:
		_dust.append(_make_dust(Color(0.5, 0.5, 0.49, 0.32), 8, 0.8))
		_smoke.append(_make_dust(Color(0.16, 0.16, 0.17, 0.28), 6, 1.6))


func _radial(colors: Array, offsets: Array, size: int) -> GradientTexture2D:
	var g := Gradient.new()
	g.colors = PackedColorArray(colors)
	g.offsets = PackedFloat32Array(offsets)
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = size
	t.height = size
	return t


func _make_sparks(col: Color, amount: int) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.emitting = false
	p.amount = amount
	p.lifetime = 0.55
	p.explosiveness = 0.95
	p.fixed_fps = 0
	p.local_coords = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3(0, 0, 1)
	pm.spread = 55.0
	pm.initial_velocity_min = 3.0
	pm.initial_velocity_max = 9.0
	pm.gravity = Vector3(0, -9.8, 0)
	pm.damping_min = 1.0
	pm.damping_max = 3.0
	pm.scale_min = 0.6
	pm.scale_max = 1.4
	pm.particle_flag_align_y = true
	var ramp := Gradient.new()
	ramp.colors = PackedColorArray([Color(col.r * 3.0, col.g * 3.0, col.b * 3.0, 1), Color(col.r, col.g * 0.6, col.b * 0.4, 0)])
	var rt := GradientTexture1D.new()
	rt.gradient = ramp
	pm.color_ramp = rt
	p.process_material = pm
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.006, 0.075, 0.006)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.albedo_color = Color(1, 1, 1)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mesh.material = m
	p.draw_pass_1 = mesh
	p.visibility_aabb = AABB(Vector3(-4, -4, -4), Vector3(8, 8, 8))
	_world.add_child(p)
	return p


func _make_dust(col: Color, amount: int, life: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.emitting = false
	p.amount = amount
	p.lifetime = life
	p.explosiveness = 0.9
	p.local_coords = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3(0, 0, 1)
	pm.spread = 30.0
	pm.initial_velocity_min = 0.4
	pm.initial_velocity_max = 1.8
	pm.gravity = Vector3(0, -0.4, 0)
	pm.damping_min = 2.0
	pm.damping_max = 3.0
	pm.scale_min = 0.5
	pm.scale_max = 1.2
	pm.angle_min = 0.0
	pm.angle_max = 360.0
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.35))
	sc.add_point(Vector2(1, 1.6))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var ramp := Gradient.new()
	ramp.colors = PackedColorArray([col, Color(col.r, col.g, col.b, 0)])
	var rt := GradientTexture1D.new()
	rt.gradient = ramp
	pm.color_ramp = rt
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.22, 0.22)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_texture = _soft_tex
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = 0.3
	q.material = m
	p.draw_pass_1 = q
	p.visibility_aabb = AABB(Vector3(-4, -4, -4), Vector3(8, 8, 8))
	_world.add_child(p)
	return p


func _fire(p: GPUParticles3D, pos: Vector3, normal: Vector3) -> void:
	p.global_position = pos
	var up := Vector3.UP if absf(normal.dot(Vector3.UP)) < 0.95 else Vector3.RIGHT
	p.global_transform.basis = Basis.looking_at(-normal, up)
	p.restart()
	p.emitting = true


func flash(pos: Vector3, color: Color, energy := 2.0, rng := 4.0, dur := 0.06, shadow := false) -> void:
	if _world == null:
		return
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = rng
	l.shadow_enabled = shadow
	l.light_volumetric_fog_energy = 2.0
	_world.add_child(l)
	l.global_position = pos
	var t := l.create_tween()
	t.tween_property(l, "light_energy", 0.0, dur)
	t.tween_callback(l.queue_free)


func decal(pos: Vector3, normal: Vector3, size := 0.09, scorch := false) -> void:
	var d: Decal
	if _decals.size() < DECAL_MAX:
		d = Decal.new()
		d.cull_mask = 1
		d.upper_fade = 0.2
		d.lower_fade = 0.2
		_world.add_child(d)
		_decals.append(d)
	else:
		d = _decals[_deci]
		_deci = (_deci + 1) % DECAL_MAX
	d.texture_albedo = _scorch_tex if scorch else _hole_tex
	d.size = Vector3(size, 0.06, size)
	d.global_position = pos
	var up := normal
	var fwd := Vector3.FORWARD if absf(up.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT
	var x := fwd.cross(up).normalized()
	d.global_transform.basis = Basis(x, up, x.cross(up)).rotated(up, randf() * TAU)
	d.modulate = Color(1, 1, 1, 1)


## kind: "metal", "concrete", "robot", "weak", "shield"
func impact(pos: Vector3, normal: Vector3, kind: String) -> void:
	if _world == null:
		return
	match kind:
		"concrete":
			_fire(_dust[_di], pos + normal * 0.02, normal); _di = (_di + 1) % DUST_POOL
			_fire(_sparks[_si], pos, normal); _si = (_si + 1) % SPARK_POOL
			decal(pos, normal, 0.08)
			Sfx.play_3d("impact_concrete", pos, -4.0)
		"metal", "shield":
			_fire(_sparks[_si], pos, normal); _si = (_si + 1) % SPARK_POOL
			flash(pos + normal * 0.1, Color(1, 0.6, 0.3), 1.2, 2.0, 0.05)
			decal(pos, normal, 0.06)
			Sfx.play_3d("impact_metal", pos, -3.0)
			if randf() < 0.25:
				Sfx.play_3d("ricochet", pos, -6.0, 0.15)
		"robot":
			_fire(_sparks[_si], pos, normal); _si = (_si + 1) % SPARK_POOL
			if randf() < 0.5:
				_fire(_blue_sparks[_bi], pos, normal); _bi = (_bi + 1) % SPARK_POOL
			flash(pos + normal * 0.1, Color(1, 0.7, 0.4), 1.5, 2.5, 0.05)
			Sfx.play_3d("robot_hit", pos, -2.0)
		"weak":
			_fire(_blue_sparks[_bi], pos, normal); _bi = (_bi + 1) % SPARK_POOL
			_fire(_sparks[_si], pos, normal); _si = (_si + 1) % SPARK_POOL
			flash(pos + normal * 0.1, Color(0.5, 0.75, 1.0), 4.0, 4.0, 0.1)
			mini_arcs(pos, 3, 0.5)
			Sfx.play_3d("robot_weakpoint", pos, 0.0)


func smoke(pos: Vector3, normal := Vector3.UP) -> void:
	_fire(_smoke[_mi], pos, normal); _mi = (_mi + 1) % DUST_POOL


func tracer(from: Vector3, to: Vector3) -> void:
	var len := from.distance_to(to)
	if len < 1.5:
		return
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.004
	cm.bottom_radius = 0.004
	cm.height = minf(len, 4.0)
	cm.radial_segments = 4
	cm.rings = 1
	cm.material = _tracer_mat
	mi.mesh = cm
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_world.add_child(mi)
	var dir := (to - from).normalized()
	var start := from + dir * cm.height * 0.5
	mi.global_position = start
	mi.global_transform.basis = _basis_y(dir)
	var t := mi.create_tween()
	t.tween_property(mi, "global_position", to - dir * cm.height * 0.5, len / 350.0)
	t.tween_callback(mi.queue_free)


func _basis_y(dir: Vector3) -> Basis:
	var y := dir.normalized()
	var ref := Vector3.UP if absf(y.dot(Vector3.UP)) < 0.95 else Vector3.RIGHT
	var x := ref.cross(y).normalized()
	return Basis(x, y, x.cross(y))


## Jagged lightning between two points, built as camera-facing ribbons.
func arc(from: Vector3, to: Vector3, width := 0.035, dur := 0.14, branches := 2, light := true) -> void:
	if _world == null:
		return
	var mi := MeshInstance3D.new()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var im := ImmediateMesh.new()
	mi.mesh = im
	_world.add_child(mi)
	_build_bolt(im, from, to, width, branches)
	if light:
		flash(to, Color(0.55, 0.75, 1.0), 3.0, 5.0, dur * 1.5)
		flash(from, Color(0.55, 0.75, 1.0), 2.5, 4.0, dur * 1.5)
	var t := mi.create_tween()
	t.tween_interval(dur * 0.45)
	t.tween_callback(func(): if is_instance_valid(mi): _build_bolt(im, from, to, width * 0.8, branches))
	t.tween_interval(dur * 0.55)
	t.tween_callback(mi.queue_free)


func mini_arcs(center: Vector3, count: int, radius: float) -> void:
	for i in count:
		var a := center + Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)).normalized() * radius
		arc(center, a, 0.012, 0.09, 0, false)


func _bolt_points(from: Vector3, to: Vector3, segs: int, jitter: float) -> PackedVector3Array:
	var pts := PackedVector3Array()
	var dir := to - from
	var len := dir.length()
	var side := dir.cross(Vector3.UP).normalized()
	if side.length() < 0.1:
		side = Vector3.RIGHT
	var up := side.cross(dir.normalized()).normalized()
	for i in segs + 1:
		var f := float(i) / segs
		var p := from + dir * f
		if i > 0 and i < segs:
			var env := sin(f * PI)
			p += (side * randf_range(-1, 1) + up * randf_range(-1, 1)) * jitter * len * env
		pts.append(p)
	return pts


func _build_bolt(im: ImmediateMesh, from: Vector3, to: Vector3, width: float, branches: int) -> void:
	im.clear_surfaces()
	var cam := get_viewport().get_camera_3d()
	var eye := cam.global_position if cam else Vector3.ZERO
	var segs := clampi(int(from.distance_to(to) * 4.0), 4, 40)
	var main := _bolt_points(from, to, segs, 0.06)
	var strips: Array = [[main, width, _arc_mat], [main, width * 0.35, _arc_core_mat]]
	for b in branches:
		var k := randi_range(1, main.size() - 2)
		var start := main[k]
		var end := start + (to - from).normalized().rotated(Vector3.UP, randf_range(-1.2, 1.2)) * randf_range(0.4, 1.2) + Vector3(0, randf_range(-0.5, 0.3), 0)
		strips.append([_bolt_points(start, end, 5, 0.12), width * 0.5, _arc_mat])
	for s in strips:
		var pts: PackedVector3Array = s[0]
		var w: float = s[1]
		im.surface_begin(Mesh.PRIMITIVE_TRIANGLES, s[2])
		for i in pts.size() - 1:
			var a := pts[i]
			var b2 := pts[i + 1]
			var seg_dir := (b2 - a).normalized()
			var to_eye := (eye - a).normalized()
			var off := seg_dir.cross(to_eye).normalized() * w * 0.5
			im.surface_add_vertex(a - off); im.surface_add_vertex(a + off); im.surface_add_vertex(b2 + off)
			im.surface_add_vertex(a - off); im.surface_add_vertex(b2 + off); im.surface_add_vertex(b2 - off)
		im.surface_end()


func overload(pos: Vector3) -> void:
	flash(pos, Color(0.55, 0.78, 1.0), 12.0, 10.0, 0.45, true)
	for i in 3:
		_fire(_blue_sparks[_bi], pos, Vector3(randf_range(-1, 1), randf_range(0, 1), randf_range(-1, 1)).normalized()); _bi = (_bi + 1) % SPARK_POOL
	for i in 6:
		var d := Vector3(randf_range(-1, 1), randf_range(-0.6, 0.8), randf_range(-1, 1)).normalized()
		arc(pos, pos + d * randf_range(0.8, 1.8), 0.012, 0.2, 1, false)
	smoke(pos)
	decal(Vector3(pos.x, 0.0, pos.z), Vector3.UP, 2.2, true)



## Fire every effect once (briefing screen) so pipelines compile before play.
func warmup(pos: Vector3, normal: Vector3) -> void:
	for k in ["concrete", "metal", "robot", "weak", "shield"]:
		impact(pos, normal, k)
	arc(pos, pos + Vector3(0.5, 0.3, 0), 0.02, 0.1, 1, true)
	tracer(pos + Vector3(0, 0, 3), pos)
	smoke(pos, normal)
	overload(pos)
	flash(pos, Color(1, 0.7, 0.4), 1.0, 2.0, 0.05, true)



## Ground dust kicked up by heavy footfalls and collapsing bodies.
func dust_puff(pos: Vector3, scale := 1.0) -> void:
	if _dust.is_empty():
		return
	var p := _dust[_di]
	_di = (_di + 1) % DUST_POOL
	_fire(p, pos, Vector3.UP)
	p.scale = Vector3.ONE * scale
