extends Node
## Material library. Builds physically based, world-space triplanar materials
## from the CC0 texture sets in assets/textures, and remaps the named
## materials exported from Blender onto textured equivalents.

const TEX := "res://assets/textures/"

var _cache := {}


func _tex(set_name: String, map: String) -> Texture2D:
	var p := TEX + set_name + "/" + map + ".jpg"
	if ResourceLoader.exists(p):
		return load(p)
	return null


## Triplanar PBR material. `scale` is texture repeats per meter.
func pbr(set_name: String, scale := 0.5, tint := Color.WHITE, metallic := 0.0, rough_mult := 1.0, key := "") -> StandardMaterial3D:
	var k := key if key != "" else "%s_%.3f_%s_%.2f_%.2f" % [set_name, scale, tint.to_html(), metallic, rough_mult]
	if _cache.has(k):
		return _cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_texture = _tex(set_name, "albedo")
	m.albedo_color = tint
	var arm := _tex(set_name, "arm")
	if arm:
		# ARM = AO (R), Roughness (G), Metal (B)
		m.roughness_texture = arm
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
		m.ao_enabled = true
		m.ao_texture = arm
		m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		m.ao_light_affect = 0.6
		if metallic > 0.0:
			m.metallic_texture = arm
			m.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
	m.roughness = rough_mult
	m.metallic = metallic
	var n := _tex(set_name, "normal")
	if n:
		m.normal_enabled = true
		m.normal_texture = n
		m.normal_scale = 1.0
	m.uv1_triplanar = true
	m.uv1_world_triplanar = not k.begins_with("fp_")   # viewmodel textures must move with the mesh
	m.uv1_scale = Vector3.ONE * scale
	m.uv1_triplanar_sharpness = 4.0
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_cache[k] = m
	return m


func flat(color: Color, metallic := 0.0, rough := 0.6, emission := Color.BLACK, energy := 0.0) -> StandardMaterial3D:
	var k := "flat_%s_%.2f_%.2f_%s_%.2f" % [color.to_html(), metallic, rough, emission.to_html(), energy]
	if _cache.has(k):
		return _cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = rough
	if energy > 0.0:
		m.emission_enabled = true
		m.emission = emission
		m.emission_energy_multiplier = energy
	_cache[k] = m
	return m


func unshaded(color: Color, additive := true) -> StandardMaterial3D:
	var k := "unshaded_%s_%s" % [color.to_html(), additive]
	if _cache.has(k):
		return _cache[k]
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = color
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if additive:
		m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.no_depth_test = false
	m.disable_receive_shadows = true
	_cache[k] = m
	return m


# --- World materials -------------------------------------------------------
func floor_concrete() -> Material: return pbr("hangar_concrete_floor", 0.25, Color(0.82, 0.84, 0.88), 0.0, 1.0, "floor")
func floor_painted() -> Material: return pbr("concrete_floor_painted", 0.3, Color(0.7, 0.74, 0.8), 0.0, 1.0, "floor_painted")
func wall_concrete() -> Material: return pbr("concrete_wall_009", 0.25, Color(0.78, 0.79, 0.8), 0.0, 1.0, "wall")
func wall_block() -> Material: return pbr("concrete_wall_004", 0.45, Color(0.72, 0.74, 0.76), 0.0, 1.0, "wall_block")
func floor_rubber() -> Material: return pbr("rubber_tiles", 0.6, Color(0.55, 0.57, 0.6), 0.0, 1.0, "floor_rubber")
func floor_epoxy() -> Material: return pbr("painted_concrete_02", 0.3, Color(0.6, 0.63, 0.66), 0.0, 1.0, "floor_epoxy")
func ceiling_tiles() -> Material: return pbr("polystyrene", 0.6, Color(0.7, 0.7, 0.68), 0.0, 1.0, "ceiling_tiles")
func wall_lower() -> Material: return pbr("green_metal_rust", 0.4, Color(0.55, 0.62, 0.55), 0.4, 1.0, "wall_lower")
func ceiling() -> Material: return pbr("corrugated_iron_02", 0.35, Color(0.45, 0.45, 0.46), 0.8, 1.0, "ceiling")
func machinery() -> Material: return pbr("blue_metal_plate", 0.35, Color(0.85, 0.95, 1.1), 0.55, 1.0, "machinery")
func diamond_plate() -> Material: return pbr("metal_plate", 0.6, Color(0.75, 0.75, 0.75), 0.9, 1.0, "diamond")
func rust_panel() -> Material: return pbr("rusty_painted_metal", 0.4, Color(0.8, 0.8, 0.8), 0.3, 1.0, "rust_panel")
func grid_panel() -> Material: return pbr("rusty_metal_grid", 0.3, Color(0.7, 0.75, 0.72), 0.5, 1.0, "grid_panel")
func steel_door() -> Material: return pbr("painted_metal_shutter", 0.6, Color(0.55, 0.57, 0.58), 0.6, 1.0, "door")
func corrugated() -> Material: return pbr("factory_wall", 0.35, Color(0.6, 0.65, 0.6), 0.6, 1.0, "corrugated")

func hazard() -> Material:
	var k := "hazard_stripes"
	if _cache.has(k):
		return _cache[k]
	var m := ShaderMaterial.new()
	var s := Shader.new()
	s.code = """
shader_type spatial;
uniform vec4 c1 : source_color = vec4(0.78, 0.56, 0.06, 1.0);
uniform vec4 c2 : source_color = vec4(0.03, 0.03, 0.03, 1.0);
varying vec3 wp;
void vertex() { wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	float s = step(0.5, fract((wp.x + wp.z + wp.y) * 2.5));
	vec3 c = mix(c1.rgb, c2.rgb, s);
	// grime
	float g = fract(sin(dot(floor(wp.xz * 40.0), vec2(12.9898, 78.233))) * 43758.5453);
	ALBEDO = c * (0.82 + 0.18 * g);
	ROUGHNESS = 0.7;
}
"""
	m.shader = s
	_cache[k] = m
	return m


# --- Imported model remap ---------------------------------------------------
var _remap := {}


func _build_remap() -> void:
	_remap = {
		# Weapons: clean finishes; only micro roughness/normal variation.
		"gunmetal": _finish(Color(0.075, 0.077, 0.08), 0.9, 0.36, 7.0, 0.25),
		"anodized": _finish(Color(0.055, 0.057, 0.06), 0.7, 0.46, 7.0, 0.2),
		"polymer": _finish(Color(0.045, 0.045, 0.043), 0.0, 0.72, 9.0, 0.35),
		"polymer_tan": _finish(Color(0.34, 0.29, 0.21), 0.0, 0.68, 9.0, 0.35),
		"rubber": _finish(Color(0.02, 0.02, 0.02), 0.0, 0.9, 9.0, 0.3),
		"steel": _finish(Color(0.6, 0.6, 0.61), 1.0, 0.3, 5.0, 0.15),
		"glass_lens": _glass(),
		# Teslabot: worn safety paint over dark alloy.
		"robot_paint": worn_paint(Color(0.5, 0.36, 0.18)),
		"robot_bone": worn_paint(Color(0.6, 0.59, 0.55)),
		# M3 kit materials
		"wood_pallet": _finish(Color(0.5, 0.39, 0.26), 0.0, 0.82, 2.0, 0.5),
		"cardboard": _finish(Color(0.55, 0.43, 0.29), 0.0, 0.9, 3.0, 0.3),
		"diamond_plate": diamond_plate(),
		"board_white": _finish(Color(0.86, 0.87, 0.86), 0.0, 0.25, 4.0, 0.1),
		"painted_red": _finish(Color(0.55, 0.06, 0.04), 0.25, 0.5, 2.0, 0.4),
		# First-person arms
		"fabric_jacket": pbr("denim_fabric_05", 9.0, Color(0.36, 0.38, 0.33), 0.0, 1.0, "fp_jacket"),
		"glove": pbr("brown_leather", 7.0, Color(0.2, 0.2, 0.21), 0.0, 1.0, "fp_glove"),
		"glove_palm": pbr("brown_leather", 9.0, Color(0.11, 0.1, 0.1), 0.0, 0.9, "fp_glove_palm"),
		"watch": _finish(Color(0.03, 0.03, 0.03), 0.3, 0.35, 8.0, 0.2),
		"tritium": flat(Color(0.3, 1.0, 0.4), 0.0, 0.4, Color(0.25, 1.0, 0.35), 3.0),
		"ceramic": _finish(Color(0.78, 0.77, 0.72), 0.0, 0.25, 4.0, 0.15),
		"rubber_cable": _finish(Color(0.02, 0.02, 0.022), 0.0, 0.75, 6.0, 0.2),
		"glass_optic": _glass(),
		"robot_dark": _finish(Color(0.07, 0.075, 0.08), 0.85, 0.42, 1.6, 0.5),
		"robot_joint": _finish(Color(0.13, 0.13, 0.13), 1.0, 0.3, 3.0, 0.3),
		"hazard": _finish(Color(0.7, 0.52, 0.06), 0.1, 0.6, 1.6, 0.5),
		"screen": flat(Color(0.03, 0.06, 0.06), 0.0, 0.15, Color(0.25, 0.65, 0.55), 0.9),
		"lamp_warm": flat(Color(1.0, 0.85, 0.65), 0.0, 0.4, Color(1.0, 0.8, 0.55), 4.0),
		"painted_dark": _detail(Color(0.13, 0.14, 0.15), 0.4, 0.55, "metal_plate_02", 1.0),
		"galvanized": _detail(Color(0.55, 0.56, 0.57), 0.9, 0.42, "rusty_metal_sheet", 0.6),
		"cable_black": _finish(Color(0.02, 0.02, 0.02), 0.0, 0.7, 6.0, 0.2),
		"lamp_cool": flat(Color(0.95, 0.97, 1.0), 0.0, 0.3, Color(0.85, 0.92, 1.0), 5.0),
		"led_green": flat(Color(0.2, 1.0, 0.4), 0.0, 0.4, Color(0.15, 1.0, 0.35), 4.0),
		"led_red": flat(Color(1.0, 0.1, 0.05), 0.0, 0.4, Color(1.0, 0.08, 0.04), 4.0),
		"led_amber": flat(Color(1.0, 0.6, 0.1), 0.0, 0.4, Color(1.0, 0.55, 0.1), 4.0),
		# Props
		"crate_green": _detail(Color(0.17, 0.21, 0.15), 0.3, 0.62, "green_metal_rust", 0.8),
		"painted_grey": _detail(Color(0.36, 0.37, 0.37), 0.3, 0.58, "painted_metal_shutter", 0.8),
		"door_steel": _detail(Color(0.27, 0.29, 0.29), 0.7, 0.5, "painted_metal_shutter", 0.8),
		"concrete": pbr("concrete_wall_008", 0.6, Color(0.75, 0.74, 0.7), 0.0, 1.0, "barrier_concrete"),
	}


## Flat albedo with world-independent roughness/normal breakup (object triplanar).
func _finish(color: Color, metallic: float, rough: float, scale: float, normal_strength: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = rough
	var arm := _tex("concrete_floor_painted", "arm")
	if arm:
		m.roughness_texture = arm
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
		m.roughness = rough * 1.4
	m.normal_enabled = true
	m.normal_texture = _tex("concrete_floor_painted", "normal")
	m.normal_scale = normal_strength
	m.uv1_triplanar = true
	m.uv1_scale = Vector3.ONE * scale
	return m


func _glass() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.25, 0.35, 0.32, 0.12)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.metallic = 0.6
	m.roughness = 0.04
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


func _detail(color: Color, metallic: float, rough: float, set_name: String, scale: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = rough
	var alb := _tex(set_name, "albedo")
	# Use the texture's luminance variation as wear on top of the flat colour.
	m.detail_enabled = true
	m.detail_albedo = alb
	m.detail_blend_mode = BaseMaterial3D.BLEND_MODE_MUL
	m.detail_normal = _tex(set_name, "normal")
	m.detail_uv_layer = BaseMaterial3D.DETAIL_UV_1
	m.normal_enabled = true
	m.normal_texture = _tex(set_name, "normal")
	m.normal_scale = 0.6
	var arm := _tex(set_name, "arm")
	if arm:
		m.roughness_texture = arm
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.uv1_triplanar = true
	m.uv1_scale = Vector3.ONE * scale
	m.albedo_color = color * 1.8
	return m


## Walk an imported scene and replace Blender materials with library ones.
func remap_scene(root: Node) -> void:
	if _remap.is_empty():
		_build_remap()
	var meshes: Array = root.find_children("*", "MeshInstance3D", true, false)
	if root is MeshInstance3D:
		meshes.append(root)   # top-level mesh objects (e.g. arm segments)
	for mi in meshes:
		var mesh: Mesh = mi.mesh
		if mesh == null:
			continue
		for i in mesh.get_surface_count():
			var mat := mesh.surface_get_material(i)
			if mat == null:
				continue
			var nm := mat.resource_name
			if _remap.has(nm):
				mi.set_surface_override_material(i, _remap[nm])



## Worn industrial paint over steel. Object-space triplanar sampling of the
## CC0 "container_side" scan drives luminance variation, scratches and
## chipped-to-metal patches; the paint colour is a tint so any faction
## colour works. Cheap: 3 texture fetches per projection, no extra passes.
func worn_paint(tint: Color) -> ShaderMaterial:
	var k := "worn_" + tint.to_html()
	if _cache.has(k):
		return _cache[k]
	if not _cache.has("_worn_shader"):
		var sh := Shader.new()
		sh.code = """
shader_type spatial;
uniform vec4 tint : source_color = vec4(0.5, 0.3, 0.1, 1.0);
uniform sampler2D alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D arm : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float scale = 2.2;
varying vec3 op;
varying vec3 on;
void vertex() { op = VERTEX * scale; on = abs(NORMAL); }
vec4 tri(sampler2D t) {
	vec3 w = pow(on, vec3(4.0)); w /= (w.x + w.y + w.z);
	return texture(t, op.zy) * w.x + texture(t, op.xz) * w.y + texture(t, op.xy) * w.z;
}
void fragment() {
	vec3 a = tri(alb).rgb;
	float lum = dot(a, vec3(0.299, 0.587, 0.114));
	float sat = length(a - vec3(lum));
	// Chips: where the scan departs from its dominant paint (rust/bare spots)
	float chip = smoothstep(0.30, 0.42, lum);
	vec3 paint = tint.rgb * (0.8 + 0.9 * (lum - 0.2));
	vec3 metal = vec3(0.32, 0.3, 0.28) * (0.6 + lum);
	ALBEDO = mix(paint, metal, chip * 0.75);
	vec4 r = tri(arm);
	ROUGHNESS = mix(clamp(r.g * 0.9 + 0.15, 0.35, 0.85), 0.38, chip);
	METALLIC = mix(0.15, 0.85, chip * 0.75);
	AO = r.r;
	AO_LIGHT_AFFECT = 0.5;
	NORMAL_MAP = tri(nrm).rgb;
	NORMAL_MAP_DEPTH = 0.7;
}
"""
		_cache["_worn_shader"] = sh
	var m := ShaderMaterial.new()
	m.shader = _cache["_worn_shader"]
	m.set_shader_parameter("tint", tint)
	m.set_shader_parameter("alb", _tex("concrete_floor_painted", "albedo"))
	m.set_shader_parameter("arm", _tex("concrete_floor_painted", "arm"))
	m.set_shader_parameter("nrm", _tex("concrete_floor_painted", "normal"))
	_cache[k] = m
	return m
