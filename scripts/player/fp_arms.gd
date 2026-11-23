class_name FPArms
extends Node3D
## First-person arms: rigid upper-arm / forearm / hand segments from arms.glb,
## positioned every frame by an analytic two-bone IK so the gloved hands sit on
## the weapon's hand sockets (grip, handguard, attachment grip, magazine, ...).
## Segment convention (Blender): origin at the proximal joint, extending +Y,
## which becomes Godot -Z.

const ARMS := "res://assets/models/arms.glb"
const UPPER := 0.30
const FORE := 0.26

var ok := false
var seg := {}          # name -> Node3D
var shoulder := {"R": Vector3(0.19, -0.27, 0.10), "L": Vector3(-0.17, -0.25, 0.02)}
var pole := {"R": Vector3(0.55, -0.7, 0.25), "L": Vector3(-0.6, -0.75, 0.1)}
var _hand_L_kind := "open"


func setup() -> void:
	if not ResourceLoader.exists(ARMS):
		return
	var root: Node = (load(ARMS) as PackedScene).instantiate()
	for n in ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L", "hand_L_fist"]:
		var src: Node3D = root.find_child(n, true, false)
		if src == null:
			push_warning("arms.glb missing " + n)
			continue
		var holder := Node3D.new()
		holder.name = n
		add_child(holder)
		var inst: Node3D = src.duplicate()
		inst.transform = Transform3D.IDENTITY
		holder.add_child(inst)
		MatLib.remap_scene(inst)
		var meshes: Array = inst.find_children("*", "MeshInstance3D", true, false)
		if inst is MeshInstance3D:
			meshes.append(inst)
		for mi in meshes:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mi.layers = 1 << 1
		seg[n] = holder
	root.queue_free()
	ok = seg.has("hand_R") and seg.has("fore_R") and seg.has("hand_L")


## targets: {"R": Transform3D, "L": Transform3D} in this node's parent (camera)
## space; left_kind "open" | "fist".
func solve(targets: Dictionary, left_kind: String) -> void:
	if not ok:
		return
	for side in ["R", "L"]:
		if not targets.has(side):
			continue
		var hand_t: Transform3D = targets[side]
		var hand_name = "hand_" + side
		if side == "L":
			hand_name = "hand_L_fist" if left_kind == "fist" and seg.has("hand_L_fist") else "hand_L"
			if seg.has("hand_L_fist"):
				seg.hand_L.visible = hand_name == "hand_L"
				seg.hand_L_fist.visible = hand_name == "hand_L_fist"
		seg[hand_name].transform = hand_t
		var w: Vector3 = hand_t.origin
		# Shoulder slides toward the hand if the reach is too long, so the
		# visible forearm always meets the glove (the shoulder is off-screen).
		var s: Vector3 = shoulder[side]
		var reach := (UPPER + FORE) * 0.985
		if s.distance_to(w) > reach:
			s = w + (s - w).normalized() * reach
		var d := clampf(s.distance_to(w), 0.05, reach)
		var dir := (w - s).normalized()
		var cos_a := clampf((UPPER * UPPER + d * d - FORE * FORE) / (2.0 * UPPER * d), -1.0, 1.0)
		var a := acos(cos_a)
		var pv: Vector3 = pole[side] - s
		pv -= dir * dir.dot(pv)
		if pv.length() < 0.001:
			pv = Vector3.DOWN
		pv = pv.normalized()
		var elbow := s + dir * cos(a) * UPPER + pv * sin(a) * UPPER
		# Upper-arm segments carry the elbow point on local -Y: aim it at the pole.
		_place("upper_" + side, s, elbow, -pv)
		# Forearm twist follows the hand so the cuff lines up with the glove.
		_place("fore_" + side, elbow, w, hand_t.basis.y)


func _place(n: String, from: Vector3, to: Vector3, up_hint: Vector3) -> void:
	if not seg.has(n):
		return
	var fwd := to - from
	if fwd.length() < 0.0001:
		return
	var up := up_hint
	if absf(fwd.normalized().dot(up.normalized())) > 0.98:
		up = Vector3.UP
	seg[n].transform = Transform3D(Basis.looking_at(fwd, up), from)
