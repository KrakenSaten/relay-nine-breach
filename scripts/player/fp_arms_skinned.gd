class_name FPArmsSkinned
extends Node3D
## M3 first-person arms: skinned rig (arms_rig.glb, armature "FPArms").
## - Analytic two-bone IK per arm (clavicle -> upperarm -> forearm -> hand),
##   elbow pole outward/down, the shoulder slides along the clavicle line when
##   the reach exceeds the arm (the shoulder is off-screen).
## - forearm_twist takes 75% of the hand roll about the forearm axis.
## - Hand bones are set to the weapon sockets exactly (same frame as M2).
## - Fingers blend between authored pose actions (pose_*) per hand.
## Same solve(targets, kind) interface as the rigid FPArms.

const RIG := "res://assets/models/arms_rig.glb"
const FINGER_RATE := 14.0

var ok := false
var skel: Skeleton3D
var _b := {}                 # bone name -> idx
var _len := {}               # "R"/"L" -> [upper, fore]
var _poses := {}             # pose name -> {bone_idx: Quaternion}
var _cur := {}               # bone_idx -> Quaternion (current finger rotation)
var _finger_bones := {"R": [], "L": []}
var _clav_rest := {}         # side -> Transform3D (skeleton space, global rest)
var weapon_ref: Node = null  # Weapon (for trigger / reload state)
var player_ref: Node = null


func setup() -> void:
	if not ResourceLoader.exists(RIG):
		return
	var root: Node3D = (load(RIG) as PackedScene).instantiate()
	add_child(root)
	root.transform = Transform3D.IDENTITY
	var sks := root.find_children("*", "Skeleton3D", true, false)
	if sks.is_empty():
		return
	skel = sks[0]
	MatLib.remap_scene(root)
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.layers = 1 << 1
		mi.extra_cull_margin = 2.0   # skinned bounds change a lot in first person
	for i in skel.get_bone_count():
		_b[skel.get_bone_name(i)] = i
	for side in ["R", "L"]:
		var ua: int = _b.get("upperarm_" + side, -1)
		var fa: int = _b.get("forearm_" + side, -1)
		var hd: int = _b.get("hand_" + side, -1)
		if ua < 0 or fa < 0 or hd < 0:
			return
		var g_ua := skel.get_bone_global_rest(ua)
		var g_fa := skel.get_bone_global_rest(fa)
		var g_hd := skel.get_bone_global_rest(hd)
		_len[side] = [g_ua.origin.distance_to(g_fa.origin), g_fa.origin.distance_to(g_hd.origin)]
		_clav_rest[side] = skel.get_bone_global_rest(_b["clavicle_" + side])
		for f in ["index", "middle", "ring", "pinky", "thumb"]:
			for j in ["01", "02", "03"]:
				var n := "%s_%s_%s" % [f, j, side]
				if _b.has(n):
					_finger_bones[side].append(_b[n])
					_cur[_b[n]] = skel.get_bone_pose_rotation(_b[n])
	# Pose library from the imported actions (first key of each rotation track).
	var aps := root.find_children("*", "AnimationPlayer", true, false)
	if not aps.is_empty():
		var ap: AnimationPlayer = aps[0]
		for anim_name in ap.get_animation_list():
			var a: Animation = ap.get_animation(anim_name)
			var pose := {}
			for t in a.get_track_count():
				if a.track_get_type(t) != Animation.TYPE_ROTATION_3D or a.track_get_key_count(t) == 0:
					continue
				var bone := String(a.track_get_path(t).get_concatenated_subnames())
				if _b.has(bone):
					pose[_b[bone]] = a.track_get_key_value(t, 0)
			_poses[String(anim_name)] = pose
		ap.stop()
		ap.active = false
	ok = _poses.has("pose_grip_R") and _poses.has("pose_cup_L")


func _to_skel(t: Transform3D) -> Transform3D:
	# targets arrive in this node's parent space (weapon holder / camera)
	return (skel.global_transform.affine_inverse() * get_parent().global_transform) * t


func solve(targets: Dictionary, left_kind: String) -> void:
	if not ok:
		return
	var dt := get_physics_process_delta_time()
	for side in ["R", "L"]:
		if not targets.has(side):
			continue
		var hand_t := _to_skel(targets[side])
		_solve_arm(side, hand_t)
	_fingers(left_kind, dt)


func _solve_arm(side: String, hand_t: Transform3D) -> void:
	var clav: int = _b["clavicle_" + side]
	var ua: int = _b["upperarm_" + side]
	var fa: int = _b["forearm_" + side]
	var tw: int = _b.get("forearm_twist_" + side, -1)
	var hd: int = _b["hand_" + side]
	var lens: Array = _len[side]
	var l1: float = lens[0]
	var l2: float = lens[1]
	var reach := (l1 + l2) * 0.985
	var cl_rest: Transform3D = _clav_rest[side]
	var ua_rest_local := skel.get_bone_rest(ua)
	var shoulder := (cl_rest * ua_rest_local).origin
	var w := hand_t.origin
	# Slide the clavicle (off-screen) toward the hand when out of reach.
	var cl_t := cl_rest
	if shoulder.distance_to(w) > reach:
		var new_sh := w + (shoulder - w).normalized() * reach
		cl_t.origin += new_sh - shoulder
		shoulder = new_sh
	skel.set_bone_global_pose(clav, cl_t)
	var d := clampf(shoulder.distance_to(w), 0.05, reach)
	var dir := (w - shoulder).normalized()
	var cos_a := clampf((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0)
	var a := acos(cos_a)
	# Elbow pole: out to the side and down, slightly back.
	var pole := Vector3(0.55 if side == "R" else -0.55, -0.75, 0.2)
	var pv := pole - dir * dir.dot(pole)
	if pv.length() < 0.001:
		pv = Vector3.DOWN
	pv = pv.normalized()
	var elbow := shoulder + dir * cos(a) * l1 + pv * sin(a) * l1
	# Bend-plane normal = shared hinge (bone X); keep its sign consistent with rest.
	var u_dir := (elbow - shoulder).normalized()
	var f_dir := (w - elbow).normalized()
	var hinge := u_dir.cross(f_dir)
	if hinge.length() < 0.0001:
		hinge = (cl_t * ua_rest_local).basis.x
	hinge = hinge.normalized()
	var rest_x := (cl_rest * ua_rest_local).basis.x.normalized()
	if hinge.dot(rest_x) < 0.0:
		hinge = -hinge
	var ub := Basis(hinge, u_dir, hinge.cross(u_dir).normalized())
	ub = Basis(ub.x, ub.y, ub.x.cross(ub.y)).orthonormalized()
	skel.set_bone_global_pose(ua, Transform3D(ub, shoulder))
	var fb := Basis(hinge, f_dir, hinge.cross(f_dir)).orthonormalized()
	skel.set_bone_global_pose(fa, Transform3D(fb, elbow))
	# Twist bone: 75% of the hand's roll about the forearm axis.
	if tw >= 0:
		var hx := hand_t.basis.x - f_dir * f_dir.dot(hand_t.basis.x)
		var roll := 0.0
		if hx.length() > 0.001:
			roll = fb.x.signed_angle_to(hx.normalized(), f_dir)
		var tw_rest_local := skel.get_bone_rest(tw)
		var tw_pos := (Transform3D(fb, elbow) * tw_rest_local).origin
		skel.set_bone_global_pose(tw, Transform3D(fb.rotated(f_dir, roll * 0.75), tw_pos))
	skel.set_bone_global_pose(hd, hand_t)


func _pose_for(side: String, left_kind: String) -> String:
	var w: Node = weapon_ref
	if side == "R":
		if w == null:
			return "pose_grip_R"
		if w.is_reloading() or (player_ref and player_ref._sprinting):
			return "pose_indexoff_R"
		if w._trigger_held_last and w.ammo > 0:
			return "pose_trigger_R"
		return "pose_grip_R"
	match left_kind:
		"point":
			return "pose_point_L"
		"fist":
			if w and w.is_reloading():
				return "pose_mag_L"
			return "pose_fist_L"
	if w and w.id == "pistol":
		return "pose_pistol_support_L"
	return "pose_cup_L"


func _fingers(left_kind: String, dt: float) -> void:
	var k := 1.0 - exp(-FINGER_RATE * dt)
	for side in ["R", "L"]:
		var pname := _pose_for(side, left_kind)
		var pose: Dictionary = _poses.get(pname, {})
		for bi in _finger_bones[side]:
			if not pose.has(bi):
				continue
			var q: Quaternion = (_cur[bi] as Quaternion).slerp(pose[bi], k)
			_cur[bi] = q
			skel.set_bone_pose_rotation(bi, q)
