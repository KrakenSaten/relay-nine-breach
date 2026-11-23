# M3 pose library: finger/thumb poses solved against the real grip cross-sections (same virtual grips
# and hand sockets as M2), then expressed as local bone rotations relative to the bind pose.
# All solving happens in DESIGN space (right hand); left poses are mirrored: q -> (w, x, -y, -z).
import math
from functools import lru_cache
from mathutils import Vector, Matrix, Quaternion
import wpn_hands as H
import wpn_poses as P
import wpn_specs as S
from wpn_lib import V, frame_matrix, MIRROR_X, rrect
import arms_rig_build as B

FN = [f[0] for f in H.FINGERS]
FINGER = {f[0]: f for f in H.FINGERS}


def radius(name, k=1):
    return FINGER[name][4] * H.TAPER[k] * H.SUBD_SHRINK * 0.5


def close_fingers(grip, splay, names=None, limit=1.0, pad=0.0004):
    out = {}
    for name, mcp, lens, w0, t0 in H.FINGERS:
        if names and name not in names:
            continue
        sp = splay.get(name, B.REST_SPLAY[name])
        fl = H.close_finger(grip, mcp, H.rz(sp), lens, radius(name) - pad, limit=limit)
        out[name] = (sp, list(fl))
    return out


def solve_thumb(target, init, avoid, tdir=None, dir_w=3.0, pt=0.6, reg=0.05):
    def rbt(pr):
        return H.thumb_R0(pr[0], pr[1], pr[2]), [0.0, pr[3], pr[4]]

    def regt(pr):
        c = 0.0
        for i, (lo, hi) in enumerate(((-0.6, 1.4), (-0.3, 1.6), (-1.9, -0.6), (-0.15, 1.2), (-0.2, 1.4))):
            if pr[i] < lo:
                c += (lo - pr[i]) ** 2 * 80
            if pr[i] > hi:
                c += (pr[i] - hi) ** 2 * 80
        return c + sum((pr[i] - init[i]) ** 2 for i in range(5)) * reg

    def extra(joints, segs):
        c = P._penetration_cost(avoid, joints[1:], 0.0095) if avoid else 0.0
        if tdir is not None:
            c += (1.0 - (joints[3] - joints[1]).normalized().dot(tdir)) * dir_w
        return c
    pr, _ = H.solve_chain(H.THUMB_CMC, rbt, H.THUMB_LENS, target, list(init), reg=regt, pt=pt, extra=extra)
    return tuple(pr)


def solve_index(goal, nrm, sp0, straight=0.0, pt=0.42, init=None):
    name, mcp, lens, w0, t0 = FINGER["index"]

    def rb(pr):
        return H.rz(pr[0]), [pr[1], pr[2], pr[3]]

    def reg(pr):
        c = (pr[3] - 0.7 * pr[2]) ** 2 * 2.0 + (pr[0] - sp0) ** 2 * 4.0
        for f in pr[1:]:
            if f < -0.05:
                c += f * f * 50
            c += straight * f * f
        return c

    def extra(joints, segs):
        return (1.0 - segs[2].col[2].dot(nrm)) * 0.6
    pr, _ = H.solve_chain(mcp, rb, lens, goal, list(init or [sp0, 0.3, 0.6, 0.4]), reg=reg, pt=pt, extra=extra)
    return (pr[0], [pr[1], pr[2], pr[3]])


def fk_points(name, sp, fl, step=0.004):
    _, mcp, lens, w0, t0 = FINGER[name]
    joints, segs, _ = H.finger_frames(mcp, H.rz(sp), lens, fl)
    pts = []
    for a, b in zip(joints, joints[1:]):
        n = max(2, int((b - a).length / step))
        pts += [a + (b - a) * (i / n) for i in range(n + 1)]
    return pts, joints, segs


# ---------------------------------------------------------------- poses (design space)
def _trigger_goal(Ti, pull_deg=0.0):
    piv = S.R_TRIGGER_PIVOT
    pad = S.R_TRIGGER_PAD
    n = V((0, 0.96, -0.28)).normalized()
    Rr = Matrix.Rotation(math.radians(-pull_deg), 3, "X")
    pad = piv + Rr @ (pad - piv)
    n = Rr @ n
    rad = radius("index", 2)
    nh = (Ti.to_3x3() @ n).normalized()
    return Ti @ pad + nh * rad, nh


@lru_cache(maxsize=None)
def pose_defs():
    poses = {}
    # ---- right hand on the pistol grip (rifle and pistol share the grip-relative geometry)
    dR = P.hand_R_def()
    Ti = dR["T"].inverted()
    splay_R = {"index": 0.02, "middle": 0.02, "ring": 0.04, "little": 0.07}
    base = close_fingers(dR["grip"], splay_R, names=("middle", "ring", "little"))
    thumb_R = tuple(dR["pose"]["thumb_params"])
    for pname, pull in (("pose_grip_R", 0.0), ("pose_trigger_R", 13.0)):
        g, nrm = _trigger_goal(Ti, pull)
        f = dict(base)
        f["index"] = solve_index(g, nrm, 0.02)
        poses[pname] = ("R", {"fingers": f, "thumb": thumb_R})
    # index straight along the receiver side above the trigger guard (trigger discipline)
    side = V((0.0145, 0.104, -0.0305))
    goal = Ti @ side + (Ti.to_3x3() @ V((1, 0, 0))).normalized() * radius("index", 2)
    f = dict(base)
    f["index"] = solve_index(goal, (Ti.to_3x3() @ V((1, 0, 0))).normalized(), 0.02, straight=0.6, pt=0.55,
                             init=[0.0, 0.05, 0.1, 0.05])
    poses["pose_indexoff_R"] = ("R", {"fingers": f, "thumb": thumb_R})
    # ---- left support cup on the handguard
    dL = P.hand_L_def()
    poses["pose_cup_L"] = ("L", {"fingers": close_fingers(dL["grip"], {"index": 0.06, "middle": 0.01, "ring": -0.03, "little": -0.07}, pad=-0.0009),
                                 "thumb": tuple(dL["pose"]["thumb_params"])})
    # ---- fist on the 27 mm vertical grip
    dF = P.hand_fist_def()
    splay_F = {"index": -0.02, "middle": 0.02, "ring": 0.05, "little": 0.09}
    poses["pose_fist_L"] = ("L", {"fingers": close_fingers(dF["grip"], splay_F), "thumb": tuple(dF["pose"]["thumb_params"])})
    # ---- rifle magazine body (rounded 22.6 x 60 mm section at the reload-grab height)
    import wpn_attachments as BA
    Lm = BA.MAGS["mag_std"][0]
    s = BA.MAG_HAND_S
    c, t, n = BA.mag_path(Lm, s)
    grow = 0.0018 * (s / Lm)
    hw, hd = S.MAG_W / 2, S.MAG_D / 2 + grow
    Fr = frame_matrix(c + n * (grow * 0.6), V((1, 0, 0)), n)
    Tm = BA.mag_hand_local("mag_std")
    to_d = MIRROR_X @ Tm.inverted()
    mag_grip = H.Grip(to_d @ Fr, rrect(2 * hw, 2 * hd, 0.0042, 3))
    thumb_t = to_d @ (c + n * (hd * 0.15) + V((hw + 0.0090, 0, 0.004)))
    tdir = (to_d.to_3x3() @ (t * -1 + n * 0.25).normalized()).normalized()
    poses["pose_mag_L"] = ("L", {"fingers": close_fingers(mag_grip, splay_F),
                                 "thumb": solve_thumb(thumb_t, dF["pose"]["thumb_params"], [mag_grip], tdir, 2.0, pt=0.62)})
    # ---- pistol support: close onto the shooting hand's fist envelope around the pistol grip
    import wpn_pistol as BP
    socks = P.pistol_hand_sockets(BP.mag_matrix())
    TR, TL = socks["sock_hand_R"], socks["sock_hand_L"]
    P0 = S.PG_TOP + S.PG_AXIS * 0.06
    pts = []
    rf = poses["pose_grip_R"][1]["fingers"]
    for name in FN:
        sp, fl = rf[name]
        cl, _, _ = fk_points(name, sp, fl)
        r = radius(name, 1) + 0.0010
        for p in cl:
            q = TR @ p
            for k in range(8):
                a = 2 * math.pi * k / 8
                pts.append(((q - P0).dot(V((1, 0, 0))) + r * math.cos(a), (q - P0).dot(S.PG_FWD) + r * math.sin(a)))
    for x in (-0.035, -0.01, 0.015, 0.038):
        for y in (0.035, 0.06, 0.085):
            q = TR @ V((x, y, 0.0135))
            pts.append(((q - P0).dot(V((1, 0, 0))), (q - P0).dot(S.PG_FWD)))
    hwp, frp, bkp = S.pg_station(0.06)
    pts += S.grip_ring2d(hwp, frp, bkp, 24)
    env = P.hull2(pts)
    Fr = frame_matrix(P0, V((1, 0, 0)), S.PG_FWD)
    to_d = MIRROR_X @ TL.inverted()
    env_grip = H.Grip(to_d @ Fr, env)
    th_t = to_d @ V((-0.0125 - 0.0090, 0.066, -0.0215))
    th_dir = (to_d.to_3x3() @ V((0, 1, -0.05)).normalized()).normalized()
    poses["pose_pistol_support_L"] = ("L", {"fingers": close_fingers(env_grip, {"index": 0.05, "middle": 0.02, "ring": -0.01, "little": -0.04}),
                                            "thumb": solve_thumb(th_t, dL["pose"]["thumb_params"], [env_grip], th_dir, 3.0)})
    # ---- point: index extended, the rest curled loosely onto a thin rod in the palm, thumb over the middle finger
    rod = [(0.0075 * math.cos(2 * math.pi * i / 16), 0.0075 * math.sin(2 * math.pi * i / 16)) for i in range(16)]
    Frod = P.design_frame(rod, gamma_deg=14.0, front_y=0.082, squeeze=0.0)
    rod_grip = H.Grip(Frod, rod)
    f = close_fingers(rod_grip, {"middle": 0.02, "ring": 0.03, "little": 0.06}, names=("middle", "ring", "little"))
    f["index"] = (0.03, [0.03, 0.06, 0.03])
    _, mj, ms = fk_points("middle", *f["middle"])
    tgt = mj[1] + (mj[2] - mj[1]) * 0.45 + ms[1].col[2] * (radius("middle", 1) + 0.0090) - ms[1].col[0] * 0.006
    poses["pose_point_L"] = ("L", {"fingers": f, "thumb": solve_thumb(tgt, (0.55, 0.85, -1.35, 0.30, 0.30), [], None, 0.0, pt=0.6)})
    # ---- relaxed and open (both sides)
    relaxed = {"index": (0.22, 0.30, 0.16), "middle": (0.28, 0.36, 0.20), "ring": (0.33, 0.40, 0.22), "little": (0.38, 0.44, 0.24)}
    for side in ("R", "L"):
        poses["pose_relaxed_" + side] = (side, {"fingers": {n: (B.REST_SPLAY[n], list(relaxed[n])) for n in FN},
                                                "thumb": (0.45, 0.50, -1.25, 0.22, 0.20)})
        poses["pose_open_" + side] = (side, {"fingers": {"index": (0.11, [-0.04, 0.02, 0.0]), "middle": (0.015, [-0.04, 0.02, 0.0]),
                                                        "ring": (-0.065, [-0.04, 0.02, 0.0]), "little": (-0.14, [-0.04, 0.02, 0.0])},
                                            "thumb": (0.90, 0.12, -0.95, 0.0, 0.02)})
    return poses


POSE_ORDER = ["pose_grip_R", "pose_trigger_R", "pose_indexoff_R", "pose_cup_L", "pose_fist_L", "pose_mag_L",
              "pose_pistol_support_L", "pose_point_L", "pose_relaxed_R", "pose_relaxed_L", "pose_open_R", "pose_open_L"]


def local_quats(pose):
    """Bone-local rotations (pose basis) relative to the bind pose, design (right) space."""
    out = {}
    for name in FN:
        b = B.FNAME[name]
        sp_r, fr = B.REST_SPLAY[name], B.REST_FLEX[name]
        sp, fl = pose["fingers"][name]
        Rr0 = H.rz(sp_r) @ H.rx(-fr[0])
        Rp0 = H.rz(sp) @ H.rx(-fl[0])
        out[b + "_01"] = (Rr0.inverted() @ Rp0).to_quaternion()
        out[b + "_02"] = H.rx(fr[1] - fl[1]).to_quaternion()
        out[b + "_03"] = H.rx(fr[2] - fl[2]).to_quaternion()
    psi, phi, rho, mcp, ip = pose["thumb"]
    rp = B.REST_THUMB
    out["thumb_01"] = (H.thumb_R0(*rp[:3]).inverted() @ H.thumb_R0(psi, phi, rho)).to_quaternion()
    out["thumb_02"] = H.rx(rp[3] - mcp).to_quaternion()
    out["thumb_03"] = H.rx(rp[4] - ip).to_quaternion()
    return out


def side_quats(side, pose):
    q = local_quats(pose)
    if side == "R":
        return {k + "_R": v for k, v in q.items()}
    return {k + "_L": Quaternion((v.w, v.x, -v.y, -v.z)) for k, v in q.items()}
