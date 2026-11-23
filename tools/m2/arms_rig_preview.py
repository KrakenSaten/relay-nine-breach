# M3 validation renders: rest pose, every pose_* action, first-person composites with the hands at the
# M2 weapon sockets (two-bone arm solve + forearm twist), and an elbow/wrist deformation stress test.
import bpy, math, os
import numpy as np
from mathutils import Vector, Matrix, Quaternion
import wpn_lib as L
from wpn_lib import V
import wpn_render as RD
import arms_rig_build as B
import arms_rig_poses as RP

STATIC = "C:/AAA/Breach/staging/weapons"
REACH = (B.UPPER_LEN + B.FORE_LEN) * 0.975


def reset_pose(ob):
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion()
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def apply_action(ob, name):
    side, pose = RP.pose_defs()[name]
    for bn, q in RP.side_quats(side, pose).items():
        pb = ob.pose.bones[bn]
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = q
    bpy.context.view_layer.update()


def roll_about(R_fore, R_hand):
    xh = R_hand.col[0]
    return math.atan2(-xh.dot(R_fore.col[2]), xh.dot(R_fore.col[0]))


def solve_arm(ob, side, hand_world, pole_hint):
    """Place clavicle/upperarm/forearm/twist/hand so the hand bone global == hand_world."""
    A = ob.matrix_world
    Ai = A.inverted()
    Mh = Ai @ hand_world
    W = Mh.translation.copy()
    Yh = Mh.to_3x3().col[1]
    rest = ob.data.bones
    clav = rest["clavicle_" + side]
    S0 = clav.tail_local.copy()
    S = S0.copy()
    d = W - S
    if d.length > REACH:
        S = W - d.normalized() * REACH
    d = W - S
    dist, dn = d.length, d.normalized()
    a, b = B.UPPER_LEN, B.FORE_LEN
    x = (a * a - b * b + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, a * a - x * x))
    ref = V((0, 0, 1)) if abs(dn.z) < 0.9 else V((1, 0, 0))
    e1 = dn.cross(ref).normalized()
    e2 = dn.cross(e1).normalized()
    sgn = 1.0 if side == "R" else -1.0
    best = None
    for k in range(144):
        th = 2 * math.pi * k / 144
        E = S + dn * x + (e1 * math.cos(th) + e2 * math.sin(th)) * h
        fdir = (W - E).normalized()
        c = math.acos(max(-1.0, min(1.0, fdir.dot(Yh)))) ** 2
        c += 4.0 * max(0.0, E.z - (S.z - 0.02)) / 0.05          # elbows hang below the shoulder
        c += 2.0 * max(0.0, -(E.x - S.x) * sgn - 0.06) / 0.05   # and do not swing across the body
        c += 0.3 * (E - (S + V(pole_hint) * 0.3)).length
        if best is None or c < best[0]:
            best = (c, E)
    E = best[1]
    yu = (E - S).normalized()
    yf = (W - E).normalized()
    zu = (yf - yu * yf.dot(yu))
    zu = zu.normalized() if zu.length > 1e-5 else rest["upperarm_" + side].matrix_local.to_3x3().col[2]
    xu = yu.cross(zu).normalized()
    Ru = B.frame3(xu, yu, zu)
    Rf = B.frame3(xu, yf, xu.cross(yf).normalized())
    pbs = ob.pose.bones
    Mc = clav.matrix_local.copy()
    Mc.translation = Mc.translation + (S - S0)
    pbs["clavicle_" + side].matrix = Mc
    bpy.context.view_layer.update()
    pbs["upperarm_" + side].matrix = B.mat4(Ru, S)
    bpy.context.view_layer.update()
    pbs["forearm_" + side].matrix = B.mat4(Rf, E)
    bpy.context.view_layer.update()
    rest_f = rest["forearm_" + side].matrix_local.to_3x3()
    rest_h = rest["hand_" + side].matrix_local.to_3x3()
    tw = roll_about(Rf, Mh.to_3x3()) - roll_about(rest_f, rest_h)
    tw = (tw + math.pi) % (2 * math.pi) - math.pi
    pbs["forearm_twist_" + side].matrix = B.mat4(Rf @ Matrix.Rotation(0.5 * tw, 3, "Y"), E + yf * B.FORE_LEN * B.TWIST_AT)
    bpy.context.view_layer.update()
    pbs["hand_" + side].matrix = Mh
    bpy.context.view_layer.update()
    got = ob.matrix_world @ pbs["hand_" + side].matrix
    err = max((got.translation - hand_world.translation).length,
              max((got.to_3x3().col[i] - hand_world.to_3x3().col[i]).length for i in range(3)))
    return {"wrist_bend_deg": math.degrees(math.acos(max(-1, min(1, yf.dot(Yh))))), "twist_deg": math.degrees(tw),
            "elbow_deg": math.degrees(math.acos(max(-1, min(1, yu.dot(yf))))), "shoulder_shift": (S - S0).length,
            "hand_err": err}


def _child(root, name):
    return RD.child(root, name)


def _top(name):
    for o in bpy.data.objects:
        if o.parent is None and o.name.split(".")[0] == name:
            return o
    return None


def _hide_atts(keep):
    for n in ("optic_reflex", "optic_prism", "suppressor", "grip_vertical", "grip_angled", "mag_std", "mag_ext", "mag_quick"):
        if n not in keep:
            o = _top(n)
            if o:
                RD.remove_tree(o)


def _clear_imports(keep_objs):
    for o in list(bpy.data.objects):
        if o not in keep_objs:
            bpy.data.objects.remove(o, do_unlink=True)


def render_rest(ob, mesh, prev):
    reset_pose(ob)
    ob.matrix_world = Matrix.Identity(4)
    RD.studio()
    c = V((0.0, 0.25, -0.30))
    cam = V((0.0, 0.98, 0.08))
    RD.camera(cam, c, lens=30)
    RD.three_point(c, cam, 1.0)
    RD.render(os.path.join(prev, "rest_front.png"))
    cam2 = V((0.62, -0.10, 0.10))
    RD.camera(cam2, V((0.10, 0.22, -0.30)), lens=30)
    RD.render(os.path.join(prev, "rest_side.png"))


def render_poses(ob, mesh, prev):
    """One close-up per pose (rig in rest arm position), plus a contact sheet."""
    ob.matrix_world = Matrix.Identity(4)
    files = []
    for name in RP.POSE_ORDER:
        reset_pose(ob)
        apply_action(ob, name)
        side = name[-1]
        hb = ob.data.bones["hand_" + side]
        Mh = hb.matrix_local
        c = Mh @ V((0.0, 0.085, -0.02))
        R = Mh.to_3x3()
        cam = c + R @ V((0.0 if side == "R" else 0.0, -0.02, 0.0)) + R.col[2] * 0.16 + R.col[0] * (0.16 if side == "R" else -0.16) \
            - R.col[1] * 0.02 + V((0, 0, 0.05))
        for o in [x for x in bpy.data.objects if x.type in ("LIGHT", "CAMERA")]:
            bpy.data.objects.remove(o, do_unlink=True)
        RD.studio(res=(900, 900))
        RD.camera(cam, c, lens=55)
        RD.three_point(c, cam, 0.5)
        f = os.path.join(prev, name + ".png")
        RD.render(f)
        # palm-side view as well (shows pads against the grip line)
        cam2 = c - R.col[2] * 0.17 + R.col[0] * (0.08 if side == "R" else -0.08) + R.col[1] * 0.06
        RD.camera(cam2, c, lens=55)
        f2 = os.path.join(prev, name + "_palm.png")
        RD.render(f2)
        files.append((f, f2))
    sheet(files, os.path.join(prev, "poses_sheet.png"))
    reset_pose(ob)


def sheet(files, path, tile=300):
    rows = []
    for f, f2 in files:
        row = []
        for p in (f, f2):
            img = bpy.data.images.load(p)
            w, h = img.size
            a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
            ys = (np.arange(tile) * h / tile).astype(int)
            xs = (np.arange(tile) * w / tile).astype(int)
            row.append(a[ys][:, xs])
            bpy.data.images.remove(img)
        rows.append(np.concatenate(row, axis=1))
    # 4 poses per row -> grid of 3 rows x (4 * 2 tiles)
    per = 4
    lines = []
    for i in range(0, len(rows), per):
        chunk = rows[i:i + per]
        while len(chunk) < per:
            chunk.append(np.zeros_like(rows[0]))
        lines.append(np.concatenate(chunk, axis=1))
    grid = np.concatenate(lines[::-1], axis=0)
    H_, W_ = grid.shape[:2]
    im = bpy.data.images.new("sheet", W_, H_, alpha=True)
    im.pixels[:] = grid.ravel()
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    print("rendered", path)


def fp_composite(ob, mesh, prev, mode):
    """Rifle at the in-game hip position; hand bones placed exactly at the M2 sockets."""
    keep = [ob, mesh]
    _clear_imports(keep)
    reset_pose(ob)
    objs = RD.import_glb(os.path.join(STATIC, "rifle.glb")) + RD.import_glb(os.path.join(STATIC, "attachments.glb"))
    rifle = _top("Rifle")
    atts = ["mag_std"] + (["grip_vertical"] if mode == "vgrip" else [])
    _hide_atts(atts)
    RD.attach(_top("mag_std"), _child(rifle, "sock_mag"))
    if mode == "vgrip":
        RD.attach(_top("grip_vertical"), _child(rifle, "sock_grip"))
    bpy.context.view_layer.update()
    eye = V((-0.2, -0.43, 0.21))       # weapon at hip_pos (0.2, -0.21, -0.43) in Godot camera space
    ob.matrix_world = Matrix.Translation(eye)
    bpy.context.view_layer.update()
    apply_action(ob, "pose_grip_R")
    left = {"handguard": ("sock_hand_L", "pose_cup_L"), "vgrip": ("sock_hand_L_vgrip", "pose_fist_L"),
            "mag": ("sock_hand_L_mag", "pose_mag_L")}[mode]
    apply_action(ob, left[1])
    stats = {"R": solve_arm(ob, "R", _child(rifle, "sock_hand_R").matrix_world, (0.5, -0.1, -0.85)),
             "L": solve_arm(ob, "L", _child(rifle, left[0]).matrix_world, (-0.5, -0.1, -0.85))}
    RD.studio()
    look = V((0.0, 0.16, -0.07))
    RD.fp_camera(eye, look - eye, (0, 0, 1), 58.0)
    RD.three_point(V((0, 0.2, -0.05)), eye, 1.0)
    name = {"handguard": "fp_rifle", "vgrip": "fp_rifle_vgrip", "mag": "fp_rifle_mag"}[mode]
    RD.render(os.path.join(prev, name + ".png"))
    views = {"handguard": [("left", (-0.30, 0.40, -0.14), (0.0, 0.27, -0.04)), ("right", (0.30, 0.10, -0.12), (0.0, 0.08, -0.07)),
                           ("below", (0.10, 0.42, -0.36), (0.0, 0.25, -0.06)), ("elbows", (0.55, -0.35, -0.10), (0.0, -0.05, -0.18))],
             "vgrip": [("left", (-0.30, 0.48, -0.16), (0.0, 0.36, -0.08)), ("front", (0.10, 0.72, -0.12), (0.0, 0.38, -0.08))],
             "mag": [("left", (-0.32, 0.26, -0.16), (0.0, 0.16, -0.10)), ("front", (0.18, 0.48, -0.16), (0.0, 0.17, -0.11))]}[mode]
    for suffix, loc, tgt in views:
        RD.camera(V(loc), V(tgt), lens=40)
        RD.render(os.path.join(prev, name + "_" + suffix + ".png"))
    _clear_imports(keep)
    for o in [x for x in bpy.data.objects if x.type in ("LIGHT", "CAMERA")]:
        bpy.data.objects.remove(o, do_unlink=True)
    reset_pose(ob)
    return stats


def fp_pistol(ob, mesh, prev):
    keep = [ob, mesh]
    _clear_imports(keep)
    reset_pose(ob)
    RD.import_glb(os.path.join(STATIC, "pistol.glb"))
    pistol = _top("Pistol")
    eye = V((-0.16, -0.38, 0.16))
    ob.matrix_world = Matrix.Translation(eye)
    bpy.context.view_layer.update()
    apply_action(ob, "pose_grip_R")
    apply_action(ob, "pose_pistol_support_L")
    stats = {"R": solve_arm(ob, "R", _child(pistol, "sock_hand_R").matrix_world, (0.5, -0.1, -0.85)),
             "L": solve_arm(ob, "L", _child(pistol, "sock_hand_L").matrix_world, (-0.5, -0.1, -0.85))}
    RD.studio()
    look = V((0.0, 0.07, -0.06))
    RD.fp_camera(eye, look - eye, (0, 0, 1), 58.0)
    RD.three_point(V((0, 0.1, -0.05)), eye, 1.0)
    RD.render(os.path.join(prev, "fp_pistol.png"))
    for suffix, loc, tgt in (("left", (-0.30, 0.20, -0.10), (0.0, 0.06, -0.07)), ("right", (0.30, 0.16, -0.08), (0.0, 0.06, -0.07))):
        RD.camera(V(loc), V(tgt), lens=40)
        RD.render(os.path.join(prev, "fp_pistol_" + suffix + ".png"))
    _clear_imports(keep)
    for o in [x for x in bpy.data.objects if x.type in ("LIGHT", "CAMERA")]:
        bpy.data.objects.remove(o, do_unlink=True)
    reset_pose(ob)
    return stats


def deform_test(ob, mesh, prev):
    """Stress test: 115 deg elbow, wrist flexed 45 deg + rolled 80 deg with half the roll on the twist bone."""
    ob.matrix_world = Matrix.Identity(4)
    reset_pose(ob)
    for side, sg in (("R", 1), ("L", -1)):
        pbs = ob.pose.bones
        pbs["forearm_" + side].rotation_quaternion = Quaternion(V((1, 0, 0)), math.radians(76))
        pbs["hand_" + side].rotation_quaternion = Quaternion(V((0, 1, 0)), math.radians(80 * sg)) @ Quaternion(V((1, 0, 0)), math.radians(-45))
        pbs["forearm_twist_" + side].rotation_quaternion = Quaternion(V((0, 1, 0)), math.radians(40 * sg))
    apply_action(ob, "pose_relaxed_R")
    apply_action(ob, "pose_relaxed_L")
    RD.studio()
    c = V((0.12, 0.10, -0.25))
    for suffix, cam in (("a", V((0.70, 0.25, 0.05))), ("b", V((0.45, 0.65, -0.55)))):
        for o in [x for x in bpy.data.objects if x.type in ("LIGHT", "CAMERA")]:
            bpy.data.objects.remove(o, do_unlink=True)
        RD.studio()
        RD.camera(cam, c, lens=35)
        RD.three_point(c, cam, 1.0)
        RD.render(os.path.join(prev, "deform_elbow_wrist_%s.png" % suffix))
    reset_pose(ob)


def run_all(ob, mesh, prev, which="all"):
    os.makedirs(prev, exist_ok=True)
    stats = {}
    want = (lambda n: True) if which == "all" else (lambda n: n in which.split(","))
    if want("rest"):
        render_rest(ob, mesh, prev)
    if want("poses"):
        render_poses(ob, mesh, prev)
    if want("deform"):
        deform_test(ob, mesh, prev)
    for mode in ("handguard", "vgrip", "mag"):
        if want("fp_" + mode) or want("fp"):
            stats["fp_" + mode] = fp_composite(ob, mesh, prev, mode)
    if want("fp_pistol") or want("fp"):
        stats["fp_pistol"] = fp_pistol(ob, mesh, prev)
    return stats
