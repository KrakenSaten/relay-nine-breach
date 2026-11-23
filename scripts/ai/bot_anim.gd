class_name BotAnim
extends RefCounted
## Procedural animation for the Teslabot (M3). Drives the joint empties of
## the imported model:
## - distance-driven gait with analytic two-bone leg IK (planted stance, no
##   foot sliding), lateral stepping when strafing, step-in-place turning,
##   walk/run blend with a lower, heavier run posture;
## - pelvis bob / roll / twist, torso counter-rotation and acceleration lean;
## - spring-driven upper-body aiming (deliberate tracking, snap on attack);
## - per-zone hit impulses (springs), stagger, cover crouch;
## - gravity-driven death topple around the feet with bounce and settle;
## - ram (piston) alignment between cylinder and rod mounts.

const THIGH := 0.43
const SHIN := 0.45
const ANKLE_H := 0.10
const HIP_H := 0.98

var bot: Node              # Teslabot
var bones: Dictionary
var rest: Dictionary
var model: Node3D

var phase := 0.0
var amp := 0.0             # gait blend 0..1
var run := 0.0             # run blend 0..1
var _prev_pos := Vector3.ZERO
var _prev_yaw := 0.0
var _yaw_rate := 0.0
var _vel_s := Vector3.ZERO  # smoothed local velocity (x side, z fwd)
var _acc_lean := 0.0
var _step_flags := [false, false]
# Springs: value, velocity
var _sp := {}
# Hit impulses: bone -> [angle Vector3, angular velocity Vector3]
var _imp := {}
var _rams: Array = []      # [cyl, rod, cyl_parent, rod_parent]
var _rams_ok := false
# Death
var death_t := 0.0
var _fall_ang := 0.0
var _fall_vel := 0.0
var _fall_axis := Vector3.RIGHT
var _bounced := 0
var _death_side := 0.0


func _init(b: Node) -> void:
	bot = b
	bones = b.bones
	rest = b._rest
	model = b.model
	_prev_pos = b.global_position
	_prev_yaw = b.rotation.y
	# Ram pairs (cylinder on parent joint, rod on child joint). Only aligned
	# when the model provides mount-pivot origins (M3 model has toe/heel).
	_rams_ok = model.find_child("toe_L", true, false) != null
	for cyl in model.find_children("*_ram_cyl*", "Node3D", true, false):
		var key := String(cyl.name).split("_ram_cyl")[0]
		var rod: Node3D = model.find_child(key + "_ram_rod*", true, false)
		if rod:
			_rams.append([cyl, rod])
	for k in ["torso_yaw", "torso_pitch", "arm_pitch", "head_yaw", "head_pitch"]:
		_sp[k] = [0.0, 0.0]


# ------------------------------------------------------------------ helpers
func _spring(key: String, target: float, omega: float, dt: float) -> float:
	# Critically damped spring (semi-implicit)
	var s: Array = _sp[key]
	var x: float = s[0]
	var v: float = s[1]
	var f := omega * omega * (target - x) - 2.0 * omega * v
	v += f * dt
	x += v * dt
	s[0] = x
	s[1] = v
	return x


func _pose(n: String, euler: Vector3, pos_offset := Vector3.ZERO) -> void:
	var b: Node3D = bones.get(n)
	if b == null:
		return
	var r: Transform3D = rest[n]
	var e := euler + _imp_angle(n)
	b.transform = Transform3D(r.basis * Basis.from_euler(e), r.origin + pos_offset)


func _imp_angle(n: String) -> Vector3:
	if _imp.has(n):
		return _imp[n][0]
	return Vector3.ZERO


func impulse(bone: String, ang_vel: Vector3) -> void:
	if not _imp.has(bone):
		_imp[bone] = [Vector3.ZERO, Vector3.ZERO]
	_imp[bone][1] += ang_vel


func _update_impulses(dt: float) -> void:
	for k in _imp:
		var a: Vector3 = _imp[k][0]
		var v: Vector3 = _imp[k][1]
		# Stiff mechanical spring: fast recovery, slight overshoot.
		var w := 16.0
		v += (-w * w * a - 2.0 * 0.55 * w * v) * dt
		a += v * dt
		_imp[k][0] = a
		_imp[k][1] = v


## Two-bone sagittal leg IK. f = forward offset of ankle from hip, d = how far
## below the hip the ankle is. Returns [hip_pitch, knee_bend(neg), ankle].
func _leg_ik(f: float, d: float, toe_pitch := 0.0) -> Array:
	var D := clampf(sqrt(f * f + d * d), 0.2, THIGH + SHIN - 0.002)
	var alpha := atan2(f, d)
	var cos_k := clampf((THIGH * THIGH + SHIN * SHIN - D * D) / (2.0 * THIGH * SHIN), -1.0, 1.0)
	var kappa := PI - acos(cos_k)
	var cos_b := clampf((THIGH * THIGH + D * D - SHIN * SHIN) / (2.0 * THIGH * D), -1.0, 1.0)
	var beta := acos(cos_b)
	var hip := alpha + beta
	var knee := -kappa
	return [hip, knee, -(hip + knee) + toe_pitch]


# ------------------------------------------------------------------ main update
func update(dt: float, crouch: float, aim_yaw: float, aim_pitch: float, aiming: bool, attacking: bool, stagger: float, limp: float) -> void:
	var gp: Vector3 = bot.global_position
	var moved := gp - _prev_pos
	moved.y = 0
	_prev_pos = gp
	var dist := moved.length()
	var yaw: float = bot.rotation.y
	_yaw_rate = lerpf(_yaw_rate, wrapf(yaw - _prev_yaw, -PI, PI) / maxf(dt, 0.0001), 1.0 - exp(-10.0 * dt))
	_prev_yaw = yaw
	var basis: Basis = bot.global_transform.basis
	var lv := basis.inverse() * (moved / maxf(dt, 0.0001))
	var prev_fwd := _vel_s.z
	_vel_s = _vel_s.lerp(Vector3(lv.x, 0, -lv.z), 1.0 - exp(-8.0 * dt))
	var spd := _vel_s.length()
	var acc := (_vel_s.z - prev_fwd) / maxf(dt, 0.0001)
	_acc_lean = lerpf(_acc_lean, clampf(acc * 0.025, -0.12, 0.12), 1.0 - exp(-6.0 * dt))
	var turning := absf(_yaw_rate) > 0.9 and spd < 0.4
	amp = move_toward(amp, 1.0 if (spd > 0.08 or turning) else 0.0, dt * 3.0)
	run = move_toward(run, clampf((spd - 2.2) / 1.2, 0.0, 1.0), dt * 2.5)
	# Gait phase advances with distance travelled (planted feet).
	var stride := lerpf(0.62, 1.25, run) * (1.0 - 0.25 * limp)
	if turning:
		phase += absf(_yaw_rate) * dt * 2.2
	else:
		phase += dist / (2.0 * stride) * TAU
	phase = fposmod(phase, TAU)
	var dir2 := Vector2(_vel_s.x, _vel_s.z)
	var dir := dir2.normalized() if dir2.length() > 0.05 else Vector2(0, 1)
	var lift_h := lerpf(0.11, 0.2, run)
	var pel_drop := lerpf(0.035, 0.11, run) * amp + 0.32 * crouch
	var bob := -0.028 * amp * cos(2.0 * phase) * (1.0 + run)
	var hip_h := HIP_H - pel_drop + bob
	# Legs
	for i in 2:
		var side := "L" if i == 0 else "R"
		var ph := fposmod(phase + (0.0 if i == 0 else PI), TAU)
		var x := 0.0
		var lift := 0.0
		if ph < PI:
			x = lerpf(stride * 0.5, -stride * 0.5, ph / PI)            # stance: planted
		else:
			var u := (ph - PI) / PI
			x = lerpf(-stride * 0.5, stride * 0.5, u * u * (3.0 - 2.0 * u))  # swing
			lift = sin(u * PI) * lift_h
		if turning:
			x = 0.0
		x *= amp
		lift *= amp
		var fwd_off := x * dir.y
		var side_off := x * dir.x
		var lim := limp if side == "L" else 0.0
		var d := hip_h - (ANKLE_H + lift)
		var toe := -0.25 * sin((ph - PI)) * amp if ph >= PI else 0.0
		var sol := _leg_ik(fwd_off, maxf(d, 0.25), toe)
		var hip_roll := atan2(side_off, maxf(d, 0.3))
		_pose("hip_" + side, Vector3(sol[0], 0, hip_roll + (0.06 if side == "L" else -0.06) * crouch))
		_pose("knee_" + side, Vector3(sol[1] - 0.12 * lim, 0, 0))
		_pose("ankle_" + side, Vector3(sol[2], 0, -hip_roll))
		# Heavy footfall at stance start
		var contact := ph < 0.25
		if contact and not _step_flags[i] and amp > 0.3:
			bot._footfall(side, run)
		_step_flags[i] = contact
	# Pelvis: drop, bob, roll toward stance leg, twist with stride, limp hitch
	var pel_off := Vector3(sin(phase) * 0.02 * amp, -pel_drop + bob - 0.04 * limp * maxf(0.0, sin(phase)), 0.07 * crouch)
	var pel_rot := Vector3(0.0, 0.09 * sin(phase) * amp * (1.0 - run * 0.3), 0.045 * sin(phase) * amp)
	_pose("pelvis", pel_rot, pel_off)
	# Upper body: aim springs (deliberate tracking, snap during attack)
	var omega := 11.0 if attacking else (6.0 if aiming else 3.5)
	var ty := _spring("torso_yaw", clampf(aim_yaw, -1.05, 1.05) if aiming else 0.0, omega, dt)
	var tp := _spring("torso_pitch", clampf(aim_pitch * 0.25, -0.2, 0.2) if aiming else 0.0, omega, dt)
	var lean := 0.06 * amp + 0.12 * run + _acc_lean + 0.18 * crouch
	var t_rot := Vector3(lean + tp + sin(bot._t * 1.3) * 0.015 * (1.0 - amp), ty - pel_rot.y * 0.8, -pel_rot.z * 0.6)
	if stagger > 0.0:
		t_rot += Vector3(-0.22, sin(bot._t * 23.0) * 0.08, sin(bot._t * 31.0) * 0.07) * clampf(stagger * 2.0, 0.0, 1.0)
	_pose("torso", t_rot)
	# Arms: emitter aims (spring), port-arms when moving fast, left arm pumps on runs.
	var arm_target := lerpf(-0.75, clampf(aim_pitch, -0.9, 0.9), 1.0 if aiming else 0.0)
	if not aiming and run > 0.3:
		arm_target = -0.35
	var ap := _spring("arm_pitch", arm_target, omega + 2.0, dt)
	if attacking:
		ap += sin(bot._t * 70.0) * 0.008
	_pose("shoulder_R", Vector3(ap, 0, 0.05 * run))
	_pose("elbow_R", Vector3(-0.15 * run * (0.0 if aiming else 1.0), 0, 0))
	var swing := sin(phase) * (0.12 + 0.4 * run) * amp
	_pose("shoulder_L", Vector3(lerpf(-0.55, -0.25, 1.0 if aiming else 0.0) + swing, 0, -0.06 * run))
	_pose("elbow_L", Vector3(-0.35 * run + sin(bot._t * 0.9) * 0.03, 0, 0))
	# Head
	var hy_t := 0.0
	var hp_t := 0.0
	if aiming:
		hp_t = clampf(aim_pitch * 0.6, -0.5, 0.4)
		hy_t = clampf(aim_yaw - ty, -0.5, 0.5)
	else:
		hy_t = bot._head_scan()
	var hy := _spring("head_yaw", hy_t, 8.0, dt)
	var hp := _spring("head_pitch", hp_t, 8.0, dt)
	_pose("head", Vector3(hp, hy, 0))
	_update_impulses(dt)
	_align_rams()


func _align_rams() -> void:
	if not _rams_ok:
		return
	for pr in _rams:
		var cyl: Node3D = pr[0]
		var rod: Node3D = pr[1]
		if not is_instance_valid(cyl) or not is_instance_valid(rod) or not cyl.is_visible_in_tree():
			continue
		var a := cyl.global_position
		var b := rod.global_position
		if a.distance_squared_to(b) < 0.0001:
			continue
		var up: Vector3 = cyl.get_parent().global_transform.basis.x
		if absf((b - a).normalized().dot(up.normalized())) > 0.97:
			up = Vector3.UP
		cyl.look_at(b, up)
		rod.look_at(a, up)


## Zone hit -> spring impulse (direction in bot-local space).
func hit(zone: String, local_dir: Vector3, strength: float) -> void:
	var s := clampf(strength, 0.3, 2.0)
	var push := Vector3(-local_dir.z, 0, local_dir.x)
	match zone:
		"head":
			impulse("head", Vector3(push.x * 9.0, randf_range(-4, 4), push.z * 7.0) * s)
		"arm_R":
			impulse("shoulder_R", Vector3(push.x * 7.0 + 3.0, 0, push.z * 5.0) * s)
		"arm_L":
			impulse("shoulder_L", Vector3(push.x * 7.0, 0, push.z * 5.0) * s)
		"leg_L", "leg_R":
			var sd: String = zone.substr(4)
			impulse("knee_" + sd, Vector3(-6.0, 0, 0) * s)
			impulse("hip_" + sd, Vector3(-3.0, 0, push.z * 2.0) * s)
			impulse("pelvis", Vector3(0, 0, (2.5 if sd == "L" else -2.5)) * s)
		"core":
			impulse("torso", Vector3(5.0, 0, push.z * 3.0) * s)    # shoved forward from behind
		_:
			impulse("torso", Vector3(push.x * 4.5, randf_range(-1.5, 1.5), push.z * 4.0) * s)


func stagger(local_dir: Vector3) -> void:
	var push := Vector3(-local_dir.z, 0, local_dir.x)
	impulse("torso", Vector3(push.x * 9.0, randf_range(-3, 3), push.z * 7.0))
	impulse("shoulder_R", Vector3(-6.0, 0, 3.0))
	impulse("shoulder_L", Vector3(-5.0, 0, -3.0))
	impulse("head", Vector3(push.x * 8.0, randf_range(-5, 5), 0))


# ------------------------------------------------------------------ death
func start_death(dir_local: Vector3, overload: bool) -> void:
	death_t = 0.0
	_fall_ang = 0.0
	_fall_vel = 0.4 + (1.2 if overload else 0.0)
	# Topple away from the killing shot, with a random sideways component.
	var fall_dir := Vector3(dir_local.x, 0, dir_local.z)
	if fall_dir.length() < 0.1:
		fall_dir = Vector3(0, 0, 1)
	fall_dir = (fall_dir.normalized() + Vector3(randf_range(-0.35, 0.35), 0, 0)).normalized()
	_fall_axis = Vector3.UP.cross(fall_dir).normalized()
	_death_side = randf_range(-1, 1)


func update_death(dt: float) -> void:
	death_t += dt
	var t := death_t
	# 1) knees buckle and the body sags (0 - 0.4 s)
	var k1 := clampf(t / 0.4, 0.0, 1.0)
	k1 = k1 * k1 * (3.0 - 2.0 * k1)
	# 2) topple: gravity torque about the feet once the sag starts
	if t > 0.25:
		var torque := 9.8 / 1.1 * sin(clampf(_fall_ang, 0.05, 1.6))
		_fall_vel += torque * dt
		_fall_ang += _fall_vel * dt
		if _fall_ang > 1.42:
			_fall_ang = 1.42
			if _fall_vel > 0.8 and _bounced < 2:
				_fall_vel = -_fall_vel * 0.28
				_bounced += 1
				bot._ground_impact(_bounced)
			else:
				_fall_vel = 0.0
	var settle := clampf((t - 0.6) / 0.6, 0.0, 1.0)
	_pose("knee_L", Vector3(-1.25 * k1 + 0.5 * settle, 0, 0))
	_pose("knee_R", Vector3(-1.05 * k1 + 0.4 * settle, 0, 0))
	_pose("hip_L", Vector3(0.8 * k1 - 0.3 * settle, 0, 0.12 * _death_side))
	_pose("hip_R", Vector3(0.65 * k1 - 0.2 * settle, 0, -0.08))
	_pose("ankle_L", Vector3(0.4 * k1, 0, 0))
	_pose("ankle_R", Vector3(0.35 * k1, 0, 0))
	_pose("pelvis", Vector3.ZERO, Vector3(0, -0.42 * k1, 0))
	_pose("torso", Vector3(0.35 * k1, 0.25 * _death_side, 0.15 * _death_side))
	_pose("head", Vector3(0.55 * k1, 0.4 * _death_side, 0))
	# Arms swing out with the fall, then lie
	var f := clampf(_fall_ang / 1.42, 0.0, 1.0)
	_pose("shoulder_R", Vector3(-0.9 * k1 - 0.9 * f, 0, 0.35 * f))
	_pose("shoulder_L", Vector3(-0.7 * k1 - 1.0 * f, 0, -0.4 * f))
	_pose("elbow_L", Vector3(-0.6 * f, 0, 0))
	# Whole model rotates about a pivot at the feet (fall direction side).
	var pivot := Vector3(0, 0, 0)
	var rot := Basis(_fall_axis, _fall_ang)
	model.transform = Transform3D(rot, pivot - rot * pivot + Vector3(0, -0.05 * f, 0))
	_update_impulses(dt)
