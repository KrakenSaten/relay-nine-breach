# Preview renders built by re-importing the exported .glb files (validates what the game loads):
# loadouts, pistol, and first-person checks with hands placed exactly at the hand sockets and
# forearms connected to the wrists by a simple two-bone IK.
import bpy, math, os
from mathutils import Vector, Matrix
import wpn_lib as L
from wpn_lib import V
import wpn_render as RD

UPPER_LEN, FORE_LEN = 0.30, 0.26


def _load(out, files):
    L.reset()
    objs = {}
    for f in files:
        for o in RD.import_glb(os.path.join(out, f)):
            objs.setdefault(o.name, o)
    bpy.context.view_layer.update()
    return objs


def _top(objs, name):
    for o in bpy.data.objects:
        if o.parent is None and o.name.split(".")[0] == name:
            return o
    return None


def _child(root, name):
    return RD.child(root, name)


def _hide_unused_attachments(objs, keep):
    names = ("optic_reflex", "optic_prism", "suppressor", "grip_vertical", "grip_angled", "mag_std", "mag_ext", "mag_quick")
    for n in names:
        if n in keep:
            continue
        o = _top(objs, n)
        if o:
            RD.remove_tree(o)


def _hide_arms(objs, keep):
    for n in ("upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L", "hand_L_fist"):
        if n not in keep:
            o = _top(objs, n)
            if o:
                RD.remove_tree(o)


def _mount(objs, rifle, slot, att):
    a = _top(objs, att)
    s = _child(rifle, "sock_" + slot)
    RD.attach(a, s)
    if slot == "muzzle" and att == "suppressor":
        fh = _child(rifle, "flash_hider")
        if fh:
            fh.hide_render = True
    return a


def _fold_irons(rifle):
    for n, ang in (("rear_sight", -90.0), ("front_sight", 90.0)):
        o = _child(rifle, n)
        if o:
            o.rotation_mode = "XYZ"
            o.rotation_euler[0] += math.radians(ang)


def _place_hand(objs, hand, sock):
    h = _top(objs, hand)
    bpy.context.view_layer.update()
    h.matrix_world = sock.matrix_world.copy()
    return h


def _seg_matrix(origin, ydir, zhint):
    y = ydir.normalized()
    z = (zhint - y * zhint.dot(y)).normalized()
    x = y.cross(z)
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = x[i], y[i], z[i], origin[i]
    return M


def _arm(objs, side, hand_obj, shoulder, pole):
    """Two-bone IK: forearm ends at the hand origin (wrist); roll follows the hand."""
    bpy.context.view_layer.update()
    Hm = hand_obj.matrix_world
    W = Hm.translation.copy()
    hz = Hm.to_3x3().col[2].normalized()
    S = V(shoulder)
    d = W - S
    dist = d.length
    dn = d.normalized()
    if dist >= UPPER_LEN + FORE_LEN - 1e-4:
        E = W - dn * FORE_LEN
        S = E - dn * UPPER_LEN
    else:
        x = (UPPER_LEN ** 2 - FORE_LEN ** 2 + dist ** 2) / (2 * dist)
        h = math.sqrt(max(0.0, UPPER_LEN ** 2 - x * x))
        p = V(pole) - dn * V(pole).dot(dn)
        E = S + dn * x + p.normalized() * h
    fore = _top(objs, "fore_" + side)
    up = _top(objs, "upper_" + side)
    fore.matrix_world = _seg_matrix(E, W - E, hz)
    up.matrix_world = _seg_matrix(S, E - S, -V(pole))


def _fp_view(rifle_hip=(0.2, -0.21, -0.43), fov=58.0, look=(0.0, 0.16, -0.07)):
    """Eye at the in-game hip camera position (weapon root at Godot camera-space hip_pos), aimed at the
    weapon with a viewmodel-style FOV so both hands are in frame."""
    hx, hy, hz = rifle_hip
    cam = V((-hx, hz, -hy))   # Godot (x, y, z) -> Blender (x, -z, y); camera = root - offset
    return RD.fp_camera(cam, V(look) - cam, (0, 0, 1), fov), cam


def _shoulders(cam):
    return cam + V((0.18, -0.06, -0.21)), cam + V((-0.18, -0.06, -0.21))


# ---------------------------------------------------------------- weapon-only renders
def rifle_side(out, prev):
    objs = _load(out, ["rifle.glb"])
    RD.studio()
    c = V((0, 0.20, -0.03))
    cam = RD.camera((0.9, 0.20, -0.03), c, ortho=1.05)
    RD.three_point(c, cam.location)
    RD.render(os.path.join(prev, "rifle_side.png"))


def rifle_34(out, prev):
    objs = _load(out, ["rifle.glb"])
    RD.studio()
    c = V((0, 0.18, -0.02))
    camloc = V((-0.62, -0.55, 0.34))
    RD.camera(camloc, c, lens=40)
    RD.three_point(c, camloc)
    RD.render(os.path.join(prev, "rifle_threequarter.png"))


def rifle_detail(out, prev):
    objs = _load(out, ["rifle.glb"])
    RD.studio()
    c = V((0, 0.10, -0.02))
    camloc = V((0.30, 0.02, 0.10))
    RD.camera(camloc, c, lens=45)
    RD.three_point(c, camloc, 0.6)
    RD.render(os.path.join(prev, "rifle_detail.png"))


def _loadout(out, prev, fname, optic, muzzle, grip, mag, camloc=(0.62, -0.45, 0.30)):
    objs = _load(out, ["rifle.glb", "attachments.glb"])
    rifle = _top(objs, "Rifle")
    keep = [a for a in (optic, muzzle, grip, mag) if a]
    _hide_unused_attachments(objs, keep)
    if optic:
        _mount(objs, rifle, "optic", optic)
        _fold_irons(rifle)
    if muzzle:
        _mount(objs, rifle, "muzzle", muzzle)
    if grip:
        _mount(objs, rifle, "grip", grip)
    if mag:
        _mount(objs, rifle, "mag", mag)
    RD.studio()
    c = V((0, 0.22, -0.03))
    RD.camera(camloc, c, lens=38)
    RD.three_point(c, camloc)
    RD.render(os.path.join(prev, fname))


def loadout_a(out, prev):
    _loadout(out, prev, "rifle_reflex_supp_vgrip_mag.png", "optic_reflex", "suppressor", "grip_vertical", "mag_std")


def loadout_b(out, prev):
    _loadout(out, prev, "rifle_prism_agrip_extmag.png", "optic_prism", None, "grip_angled", "mag_ext", camloc=(-0.62, -0.40, 0.26))


def attachments_sheet(out, prev):
    objs = _load(out, ["attachments.glb"])
    RD.studio()
    c = V((0.53, 0.02, -0.05))
    camloc = V((0.60, -1.10, 0.36))
    RD.camera(camloc, c, lens=34)
    RD.three_point(c, camloc, 1.2)
    RD.render(os.path.join(prev, "attachments.png"))


def pistol_34(out, prev):
    objs = _load(out, ["pistol.glb"])
    RD.studio()
    c = V((0, 0.085, -0.045))
    camloc = V((0.36, 0.30, 0.10))
    RD.camera(camloc, c, lens=50)
    RD.three_point(c, camloc, 0.6)
    RD.render(os.path.join(prev, "pistol_threequarter.png"))


def pistol_side(out, prev):
    objs = _load(out, ["pistol.glb"])
    RD.studio()
    c = V((0, 0.085, -0.04))
    cam = RD.camera((-0.5, 0.085, -0.04), c, ortho=0.30)
    RD.three_point(c, cam.location, 0.6)
    RD.render(os.path.join(prev, "pistol_side.png"))


# ---------------------------------------------------------------- first-person checks
def _fp_scene(out, mode):
    objs = _load(out, ["rifle.glb", "attachments.glb", "arms.glb"])
    rifle = _top(objs, "Rifle")
    keep = ["mag_std"]
    if mode == "vgrip":
        keep.append("grip_vertical")
    if mode == "agrip":
        keep.append("grip_angled")
    _hide_unused_attachments(objs, keep)
    _mount(objs, rifle, "mag", "mag_std")
    if mode == "vgrip":
        _mount(objs, rifle, "grip", "grip_vertical")
    if mode == "agrip":
        _mount(objs, rifle, "grip", "grip_angled")
    hr = _place_hand(objs, "hand_R", _child(rifle, "sock_hand_R"))
    if mode == "agrip":
        hl = _place_hand(objs, "hand_L", _child(rifle, "sock_hand_L_agrip"))
        _hide_arms(objs, ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L"])
    elif mode == "handguard":
        hl = _place_hand(objs, "hand_L", _child(rifle, "sock_hand_L"))
        _hide_arms(objs, ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L"])
    elif mode == "vgrip":
        hl = _place_hand(objs, "hand_L_fist", _child(rifle, "sock_hand_L_vgrip"))
        _hide_arms(objs, ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L_fist"])
    else:
        hl = _place_hand(objs, "hand_L_fist", _child(rifle, "sock_hand_L_mag"))
        _hide_arms(objs, ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L_fist"])
    return objs, rifle, hr, hl


def _fp_render(objs, hr, hl, prev, name, checks):
    cam, camp = _fp_view()
    sR, sL = _shoulders(camp)
    _arm(objs, "R", hr, sR, V((0.6, 0.0, -0.8)))
    _arm(objs, "L", hl, sL, V((-0.5, 0.0, -0.9)))
    RD.studio()
    RD.three_point(V((0, 0.2, -0.05)), camp, 1.0)
    RD.render(os.path.join(prev, name + ".png"))
    for suffix, loc, tgt, lens in checks:
        RD.camera(loc, tgt, lens=lens)
        RD.render(os.path.join(prev, name + "_" + suffix + ".png"))


def fp_rifle(out, prev):
    objs, rifle, hr, hl = _fp_scene(out, "handguard")
    _fp_render(objs, hr, hl, prev, "fp_rifle", [
        ("left", V((-0.30, 0.38, -0.16)), V((0.0, 0.25, -0.04)), 40),
        ("right", V((0.30, 0.10, -0.12)), V((0.0, 0.10, -0.07)), 40),
        ("below", V((0.10, 0.42, -0.36)), V((0.0, 0.25, -0.05)), 40)])


def fp_rifle_vgrip(out, prev):
    objs, rifle, hr, hl = _fp_scene(out, "vgrip")
    _fp_render(objs, hr, hl, prev, "fp_rifle_vgrip", [
        ("left", V((-0.30, 0.48, -0.16)), V((0.0, 0.36, -0.07)), 40),
        ("front", V((0.10, 0.72, -0.12)), V((0.0, 0.38, -0.07)), 40)])


def fp_rifle_agrip(out, prev):
    objs, rifle, hr, hl = _fp_scene(out, "agrip")
    _fp_render(objs, hr, hl, prev, "fp_rifle_agrip", [
        ("left", V((-0.30, 0.46, -0.16)), V((0.0, 0.33, -0.05)), 40),
        ("below", V((0.10, 0.48, -0.36)), V((0.0, 0.33, -0.05)), 40)])


def fp_rifle_mag(out, prev):
    objs, rifle, hr, hl = _fp_scene(out, "mag")
    _fp_render(objs, hr, hl, prev, "fp_rifle_mag", [
        ("left", V((-0.32, 0.26, -0.16)), V((0.0, 0.16, -0.10)), 40),
        ("front", V((0.18, 0.48, -0.16)), V((0.0, 0.17, -0.11)), 40)])


def fp_pistol(out, prev):
    objs = _load(out, ["pistol.glb", "arms.glb"])
    pistol = _top(objs, "Pistol")
    _hide_arms(objs, ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L"])
    hr = _place_hand(objs, "hand_R", _child(pistol, "sock_hand_R"))
    hl = _place_hand(objs, "hand_L", _child(pistol, "sock_hand_L"))
    cam, camp = _fp_view((0.16, -0.16, -0.38), look=(0.0, 0.07, -0.06))
    sR, sL = _shoulders(camp)
    _arm(objs, "R", hr, sR, V((0.6, 0.0, -0.8)))
    _arm(objs, "L", hl, sL, V((-0.6, 0.0, -0.8)))
    RD.studio()
    RD.three_point(V((0, 0.1, -0.05)), camp, 1.0)
    RD.render(os.path.join(prev, "fp_pistol.png"))
    for suffix, loc, tgt in (("left", V((-0.30, 0.20, -0.10)), V((0.0, 0.06, -0.07))),
                             ("right", V((0.30, 0.16, -0.08)), V((0.0, 0.06, -0.07))),
                             ("front", V((0.08, 0.42, -0.06)), V((0.0, 0.05, -0.07)))):
        RD.camera(loc, tgt, lens=40)
        RD.render(os.path.join(prev, "fp_pistol_" + suffix + ".png"))


def hands_sheet(out, prev):
    import wpn_poses as poses, wpn_hands as H
    objs = _load(out, ["arms.glb"])
    _hide_arms(objs, ["hand_R", "hand_L", "hand_L_fist"])
    RD.studio()
    xs = {"hand_R": -0.16, "hand_L": 0.0, "hand_L_fist": 0.16}
    for n, x in xs.items():
        o = _top(objs, n)
        o.matrix_world = Matrix.Translation(V((x, 0, 0)))
    c = V((0, 0.06, 0.0))
    camloc = V((0.05, -0.30, 0.42))
    RD.camera(camloc, c, lens=45)
    RD.three_point(c, camloc, 0.7)
    RD.render(os.path.join(prev, "hands_top.png"))
    RD.camera(V((0.05, 0.25, -0.40)), c, lens=45)
    RD.render(os.path.join(prev, "hands_palm.png"))


def arms_sheet(out, prev):
    objs = _load(out, ["arms.glb"])
    RD.studio()
    c = V((0.52, 0.13, 0.0))
    camloc = V((0.52, -0.95, 0.85))
    RD.camera(camloc, c, lens=35)
    RD.three_point(c, camloc, 1.2)
    RD.render(os.path.join(prev, "arms.png"))


def _section(prev, name, loc, tgt, clip, ortho):
    cam = RD.camera(loc, tgt, ortho=ortho)
    cam.data.clip_start = clip
    RD.render(os.path.join(prev, "debug", name + ".png"))


def sections(out, prev):
    """Diagnostic slices through each hold (camera near-clip cuts the scene at the hand)."""
    objs, rifle, hr, hl = _fp_scene(out, "handguard")
    RD.studio(res=(900, 900))
    RD.three_point(V((0, 0.3, 0)), V((0.0, 0.9, 0.2)), 1.0)
    for dy in (0.0, 0.02, 0.04):
        y = 0.30 + dy
        _section(prev, "sec_handguard_%02d" % int(dy * 100), V((0, 0.9, 0.0)), V((0, y, 0.0)), 0.9 - y, 0.16)
    _section(prev, "sec_grip_R", V((0, 0.62, -0.08)), V((0, 0.03, -0.08)), 0.62 - 0.04, 0.14)
    objs, rifle, hr, hl = _fp_scene(out, "vgrip")
    RD.studio(res=(900, 900))
    RD.three_point(V((0, 0.38, -0.08)), V((0.0, 0.38, 0.6)), 1.0)
    cam = RD.camera(V((0, 0.38, 0.6)), V((0, 0.38, -0.08)), ortho=0.16, up=(0, 1, 0))
    cam.data.clip_start = 0.6 + 0.085
    RD.render(os.path.join(prev, "debug", "sec_vgrip.png"))
    objs, rifle, hr, hl = _fp_scene(out, "mag")
    RD.studio(res=(900, 900))
    cam = RD.camera(V((0, 0.17, 0.6)), V((0, 0.175, -0.10)), ortho=0.16)
    cam.data.clip_start = 0.6 + 0.095
    RD.three_point(V((0, 0.17, -0.1)), V((0, 0.17, 0.6)), 1.0)
    RD.render(os.path.join(prev, "debug", "sec_mag.png"))
    objs = _load(out, ["pistol.glb", "arms.glb"])
    pistol = _top(objs, "Pistol")
    _hide_arms(objs, ["upper_R", "upper_L", "fore_R", "fore_L", "hand_R", "hand_L"])
    _place_hand(objs, "hand_R", _child(pistol, "sock_hand_R"))
    _place_hand(objs, "hand_L", _child(pistol, "sock_hand_L"))
    RD.studio(res=(900, 900))
    RD.three_point(V((0, 0.03, -0.07)), V((0, 0.03, 0.5)), 1.0)
    import wpn_specs as S
    for k, ss in enumerate((0.03, 0.06)):
        p = S.PG_TOP + S.PG_AXIS * ss
        loc = p - S.PG_AXIS * 0.5
        cam = RD.camera(loc, p, ortho=0.16)
        cam.data.clip_start = 0.5
        RD.render(os.path.join(prev, "debug", "sec_pistol_%d.png" % k))


ALL = {
    "rifle_side": rifle_side,
    "rifle_34": rifle_34,
    "rifle_detail": rifle_detail,
    "loadout_a": loadout_a,
    "loadout_b": loadout_b,
    "attachments": attachments_sheet,
    "pistol_34": pistol_34,
    "pistol_side": pistol_side,
    "hands": hands_sheet,
    "arms": arms_sheet,
    "fp_rifle": fp_rifle,
    "fp_rifle_vgrip": fp_rifle_vgrip,
    "fp_rifle_mag": fp_rifle_mag,
    "fp_rifle_agrip": fp_rifle_agrip,
    "fp_pistol": fp_pistol,
    "sections": sections,
}


def run(out, prev, which):
    names = list(ALL) if which == "all" else which.split(",")
    for n in names:
        if n in ALL:
            try:
                ALL[n](out, prev)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print("PREVIEW FAILED", n, e)
