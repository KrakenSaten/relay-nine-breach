# Hand poses (solved against virtual grips) and the hand sockets derived from them.
# A pose pairs a DESIGN frame in right-hand space (where the hand expects the grip) with a WEAPON
# frame (the same grip on the real part). socket = F_weapon * F_design^-1, so the hand mesh origin
# placed at the socket wraps the real part. Left hands are mirrored right hands: their design frame
# is mirrored (M F M) and the real cross-section is mirrored in u before posing.
import math
from functools import lru_cache
from mathutils import Vector, Matrix
import specs as S
import hands as H
from m2lib import V, frame_matrix, MIRROR_X


def hull2(pts):
    pts = sorted(set((round(p[0], 7), round(p[1], 7)) for p in pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def design_frame(shape, gamma_deg, front_y, px=-0.0104, squeeze=0.0006):
    """Hand-space grip frame: u = -Z (palm -> grip), a oblique by gamma in the palm plane."""
    g = math.radians(gamma_deg)
    u = V((0, 0, -1))
    v = V((math.sin(g), math.cos(g), 0))
    umin = min(p[0] for p in shape)
    vmax = max(p[1] for p in shape)
    pz = -H.PALM_BOTTOM + umin + squeeze
    py = front_y - vmax / math.cos(g)
    return frame_matrix(V((px, py, pz)), u, v)


def to_uv(points3, F):
    Fi = F.inverted()
    out = []
    for p in points3:
        q = Fi @ V(p)
        out.append((q.x, q.y))
    return out


def socket_matrix(F_w, F_h, left):
    if left:
        F_h = MIRROR_X @ F_h @ MIRROR_X
    return F_w @ F_h.inverted()


# ---------------------------------------------------------------- weapon-side grips
def rifle_grip_frame(s_mid=0.056):
    P = S.RG_TOP + S.RG_AXIS * s_mid
    F = frame_matrix(P, -V((1, 0, 0)), S.RG_FWD)
    hw, fr, bk = S.rg_station(s_mid)
    shape = [(-x, f) for x, f in S.grip_ring2d(hw, fr, bk, 32)]
    return F, shape


def handguard_frame(y=S.HAND_L_Y, beta_deg=35.0):
    zc = 0.5 * (S.RAIL_Z0 + S.HG_BOTTOM)
    b = math.radians(beta_deg)
    u = V((-math.sin(b), 0, -math.cos(b)))     # toward the palm (left hand: palm side is +u)
    v = V((math.cos(b), 0, -math.sin(b)))
    F = frame_matrix(V((0, y, zc)), u, v)
    pts = [(x, y, z) for x, z in S.HG_OUT] + [(sx * 0.0097, y, S.RAIL_TOP) for sx in (-1, 1)] + \
          [(sx * 0.0106, y, S.RAIL_TOP - 0.0011) for sx in (-1, 1)]
    real = to_uv(pts, F)
    design = hull2([(-a, b2) for a, b2 in real])
    return F, design


def vgrip_frame(delta_deg=38.0):
    d = math.radians(delta_deg)
    u = V((-math.cos(d), -math.sin(d), 0))
    v = V((-math.sin(d), math.cos(d), 0))
    F = frame_matrix(V((0, 0, S.VG_HAND_Z)), u, v)
    return F


def circle_shape(r, n=32):
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---------------------------------------------------------------- pose solving
def _finger_radius(t0, k=0):
    return t0 * H.TAPER[k] * H.SUBD_SHRINK * 0.5


def _cupped(p, cup):
    return H._cup(p, cup)


def _penetration_cost(grips, joints, radius, weight=2e5):
    c = 0.0
    pts = []
    for a, b in zip(joints, joints[1:]):
        for t in (0.0, 0.33, 0.66):
            pts.append(a + (b - a) * t)
    pts.append(joints[-1])
    for g in grips:
        for p in pts:
            d, _ = g.signed_dist(p)
            if d < radius:
                c += (radius - d) ** 2 * weight
    return c


def solve_hand(pose_def):
    """pose_def keys: grip (H.Grip), cup, splay{}, wrap{} (bool per finger), fk{} (flex per finger),
    index_target (hand-space point, normal) optional, thumb_target (point) + thumb init."""
    grip = pose_def["grip"]
    cup = pose_def.get("cup", 0.0)
    fingers = {}
    for name, mcp, lens, w0, t0 in H.FINGERS:
        sp = pose_def["splay"].get(name, 0.0)
        R0 = H.rz(sp)
        mcp_c = _cupped(mcp, cup)
        if name == "index" and pose_def.get("index_target"):
            tgt, nrm = pose_def["index_target"]
            rad = _finger_radius(t0, 2)
            goal = tgt + nrm * rad

            def rb(pr):
                return H.rz(pr[0]), [pr[1], pr[2], pr[3]]

            def reg(pr):
                c = (pr[3] - 0.7 * pr[2]) ** 2 * 2.0 + (pr[0] - sp) ** 2 * 4.0
                for f in pr[1:]:
                    if f < 0:
                        c += f * f * 50
                return c

            def extra(joints, segs):
                u = segs[2].col[2]
                return (1.0 - u.dot(nrm)) * 0.6

            pr, cst = H.solve_chain(mcp_c, rb, lens, goal, [sp, 0.3, 0.6, 0.4], reg=reg, pt=0.42, extra=extra)
            fingers[name] = (H.rz(pr[0]), [pr[1], pr[2], pr[3]])
            continue
        fx = pose_def.get("fk", {}).get(name)
        if fx is not None:
            fingers[name] = (R0, list(fx))
            continue
        rad = _finger_radius(t0, 1) * pose_def.get("rad_scale", 1.0) - 0.0004
        flex = H.close_finger(grip, mcp_c, R0, lens, rad, limit=pose_def.get("curl_limit", 1.0),
                              start=pose_def.get("curl_start", (0.0, 0.0, 0.0)))
        bias = pose_def.get("flex_bias", {}).get(name)
        if bias:
            flex = [f + b for f, b in zip(flex, bias)]
        fingers[name] = (R0, flex)
    # thumb
    tt = pose_def["thumb"]
    th_grips = tt.get("avoid", [grip])
    th_rad = 0.0095

    def rbt(pr):
        return H.thumb_R0(pr[0], pr[1], pr[2]), [0.0, pr[3], pr[4]]

    def regt(pr):
        c = 0.0
        for i, (lo, hi) in enumerate(((-0.6, 1.4), (-0.3, 1.6), (-1.9, -0.6), (-0.15, 1.2), (-0.2, 1.4))):
            if pr[i] < lo:
                c += (lo - pr[i]) ** 2 * 80
            if pr[i] > hi:
                c += (pr[i] - hi) ** 2 * 80
        c += sum((pr[i] - tt["init"][i]) ** 2 for i in range(5)) * tt.get("reg", 0.05)
        return c

    def extrat(joints, segs):
        return _penetration_cost(th_grips, joints[1:], th_rad)

    pr, cst = H.solve_chain(H.THUMB_CMC, rbt, H.THUMB_LENS, tt["target"], tt["init"], reg=regt, pt=tt.get("pt", 0.6), extra=extrat)
    thumb = (H.thumb_R0(pr[0], pr[1], pr[2]), [0.0, pr[3], pr[4]])
    return {"cup": cup, "fingers": fingers, "thumb": thumb, "thumb_params": pr}


# ---------------------------------------------------------------- the three hands
@lru_cache(maxsize=None)
def hand_R_def():
    Fw, shape = rifle_grip_frame()
    Fh = design_frame(shape, gamma_deg=24.0, front_y=0.100)
    grip = H.Grip(Fh, shape)
    T = socket_matrix(Fw, Fh, False)
    Ti = T.inverted()
    # trigger pad target (rifle space -> hand space)
    pad = S.R_TRIGGER_PAD
    n_w = V((0, 0.96, -0.28)).normalized()
    tgt = Ti @ pad
    nrm = (Ti.to_3x3() @ n_w).normalized()
    # thumb: along the left side of the lower, pointing forward under the selector
    th_w = V((-0.0262, 0.024, -0.031))
    pose = {
        "grip": grip, "cup": 0.55,
        "splay": {"index": 0.02, "middle": 0.02, "ring": 0.04, "little": 0.07},
        "index_target": (tgt, nrm),
        "flex_default": (0.3, 0.4, 0.3),
        "thumb": {"target": Ti @ th_w, "init": [0.55, 0.65, -1.25, 0.25, 0.25], "pt": 0.55,
                  "avoid": [grip]},
    }
    return {"Fw": Fw, "Fh": Fh, "shape": shape, "grip": grip, "T": T, "pose": solve_hand(pose)}


@lru_cache(maxsize=None)
def hand_L_def():
    Fw, shape = handguard_frame()
    Fh = design_frame(shape, gamma_deg=30.0, front_y=0.094)
    grip = H.Grip(Fh, shape)
    T = socket_matrix(Fw, Fh, True)
    # thumb over the top-left of the handguard, pointing forward (real space -> mirrored design space)
    th_w = V((-0.0205, S.HAND_L_Y + 0.060, 0.0335))
    th_h = MIRROR_X @ (T.inverted() @ th_w)
    pose = {
        "grip": grip, "cup": 0.30,
        "splay": {"index": 0.06, "middle": 0.01, "ring": -0.03, "little": -0.07},
        "flex_default": (0.15, 0.25, 0.2),
        "thumb": {"target": th_h, "init": [0.35, 0.35, -1.0, 0.1, 0.15], "pt": 0.6, "avoid": [grip], "reg": 0.02},
    }
    return {"Fw": Fw, "Fh": Fh, "shape": shape, "grip": grip, "T": T, "pose": solve_hand(pose)}


@lru_cache(maxsize=None)
def hand_fist_def():
    shape = circle_shape(S.VG_R)
    Fh = design_frame(shape, gamma_deg=16.0, front_y=0.098, squeeze=0.0008)
    grip = H.Grip(Fh, shape)
    # thumb wraps over the index/middle on the far side: ride on a cylinder grown by finger thickness
    big = H.Grip(Fh, circle_shape(S.VG_R + 0.0175))
    # target: far side of the cylinder, ahead of the index plane
    th = Fh @ V((0.018, 0.019, -0.006))
    pose = {
        "grip": grip, "cup": 0.85,
        "splay": {"index": -0.02, "middle": 0.02, "ring": 0.05, "little": 0.09},
        "flex_default": (0.6, 0.6, 0.4),
        "thumb": {"target": th, "init": [0.6, 0.9, -1.35, 0.35, 0.35], "pt": 0.6, "avoid": [big]},
    }
    return {"Fh": Fh, "shape": shape, "grip": grip, "pose": solve_hand(pose)}


# ---------------------------------------------------------------- sockets
def vgrip_hand_matrix():
    """hand_L_fist transform in grip_vertical space."""
    d = hand_fist_def()
    return socket_matrix(vgrip_frame(), d["Fh"], True)


def agrip_hand_matrix():
    """hand_L (open support hand) in grip_angled space: palm under the handguard, web against the
    angled face. Expressed relative to the grip origin (rail contact point on sock_grip)."""
    d = hand_L_def()
    # same handguard hold, moved so the web of the hand meets the grip's rear face
    Fw, _ = handguard_frame(y=S.SOCK_GRIP.y - 0.050)
    T = socket_matrix(Fw, d["Fh"], True)
    return Matrix.Translation(-S.SOCK_GRIP) @ T


def mag_hand_matrix(front_y, z, half_w):
    """hand_L_fist on a magazine body (mag space; the mag hangs along -Z)."""
    d = hand_fist_def()
    u = V((-1, 0, 0))
    v = V((0, 1, 0))
    P = V((-half_w + S.VG_R - 0.0004, front_y - S.VG_R + 0.0012, z))
    return socket_matrix(frame_matrix(P, u, v), d["Fh"], True)


def rifle_hand_sockets():
    r = hand_R_def()
    l = hand_L_def()
    out = {
        "sock_hand_R": r["T"],
        "sock_hand_L": l["T"],
        "sock_hand_L_vgrip": Matrix.Translation(S.SOCK_GRIP) @ vgrip_hand_matrix(),
        "sock_hand_L_agrip": Matrix.Translation(S.SOCK_GRIP) @ agrip_hand_matrix(),
    }
    import build_attachments as BA
    out["sock_hand_L_mag"] = Matrix.Translation(S.MAG_TOP) @ BA.mag_hand_local("mag_std")
    return out
