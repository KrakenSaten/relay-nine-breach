# M3 skinned first-person arms: rest-pose layout, armature "FPArms", skinned mesh with cage-level
# weights (Catmull-Clark interpolates them, so deformation is smooth by construction).
# Reuses the M2 hand cage dimensions (wpn_hands) and grip frames (wpn_poses) read-only.
#
# Armature space = first-person camera space (Blender axes): origin at the eye, +Y forward, +Z up.
# The right side is authored; the left side is its exact mirror (bones get proper right-handed frames).
import math
import bmesh, bpy
from mathutils import Vector, Matrix, Quaternion
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
import wpn_lib as L
from wpn_lib import V, mat, link, apply_mods, smooth_all, MIRROR_X
import wpn_hands as H

UPPER_LEN, FORE_LEN, TWIST_AT, HAND_LEN, CLAV_LEN = 0.30, 0.26, 0.60, 0.085, 0.085
FNAME = {"index": "index", "middle": "middle", "ring": "ring", "little": "pinky"}
SIDES = ("R", "L")

# ---------------------------------------------------------------- rest pose (right side, camera space)
SHOULDER_R = V((0.190, -0.050, -0.210))
CLAV_DIR_R = V((0.80, 0.10, -0.40)).normalized()      # clavicle points from the neck base out to the shoulder
D_UPPER = V((-0.05, 0.75, -0.55)).normalized()        # upper arm forward-down-in
D_FORE = V((-0.15, 0.95, 0.05)).normalized()          # ~39 deg elbow bend at rest
HAND_DORSAL_HINT = V((0.50, 0.0, 0.85))               # palm faces down-inward (semi-pronated)

# hand rest (bind) pose: slight natural curl, relaxed thumb (design = right hand space)
REST_SPLAY = {"index": 0.070, "middle": 0.010, "ring": -0.040, "little": -0.090}
REST_FLEX = {"index": (0.12, 0.16, 0.08), "middle": (0.13, 0.18, 0.09), "ring": (0.15, 0.20, 0.10), "little": (0.17, 0.22, 0.11)}
REST_THUMB = (0.50, 0.40, -1.20, 0.15, 0.12)          # psi, phi, rho, mcp flex, ip flex


def frame3(x, y, z):
    M = Matrix.Identity(3)
    for i in range(3):
        M[i][0], M[i][1], M[i][2] = x[i], y[i], z[i]
    return M


def mat4(R, t):
    M = R.to_4x4()
    M.translation = V(t)
    return M


def rest_layout():
    """Rest frames (armature space) for the right arm. Returns dict of name -> (head, R3 with cols X,Y,Z, length)."""
    S = SHOULDER_R.copy()
    du, df = D_UPPER, D_FORE
    E = S + du * UPPER_LEN
    W = E + df * FORE_LEN
    zu = (df - du * df.dot(du)).normalized()        # bend direction (anterior)
    xu = du.cross(zu).normalized()                   # elbow hinge = local X (lateral on the right arm)
    Ru = frame3(xu, du, zu)
    Rf = frame3(xu, df, xu.cross(df).normalized())
    zh = (HAND_DORSAL_HINT - df * HAND_DORSAL_HINT.dot(df)).normalized()
    Rh = frame3(df.cross(zh).normalized(), df, zh)   # hand: Y fingers, Z back of hand, X = Y x Z
    ch = S - CLAV_DIR_R * CLAV_LEN
    zc = (V((0, 0, 1)) - CLAV_DIR_R * CLAV_DIR_R.z).normalized()
    Rc = frame3(CLAV_DIR_R.cross(zc).normalized(), CLAV_DIR_R, zc)
    lay = {"clavicle": (ch, Rc, CLAV_LEN), "upperarm": (S, Ru, UPPER_LEN), "forearm": (E, Rf, FORE_LEN),
           "forearm_twist": (E + df * FORE_LEN * TWIST_AT, Rf.copy(), FORE_LEN * (1 - TWIST_AT)),
           "hand": (W, Rh, HAND_LEN)}
    return lay


def hand_matrix_rest(side="R"):
    h, R, _ = rest_layout()["hand"]
    M = mat4(R, h)
    return mirror_frame(M) if side == "L" else M


def mirror_frame(M):
    """Mirror a proper frame across X and re-orthonormalise as right-handed (X = Y x Z)."""
    R = M.to_3x3()
    y = MIRROR_X.to_3x3() @ R.col[1]
    z = MIRROR_X.to_3x3() @ R.col[2]
    t = MIRROR_X @ M.translation.to_4d()
    return mat4(frame3(y.cross(z), y, z), t.to_3d())


def rest_hand_pose():
    fingers = {n: (H.rz(REST_SPLAY[n]), list(REST_FLEX[n])) for n in REST_SPLAY}
    thumb = (H.thumb_R0(*REST_THUMB[:3]), [0.0, REST_THUMB[3], REST_THUMB[4]])
    return {"cup": 0.0, "fingers": fingers, "thumb": thumb}


def hand_bone_frames():
    """Rest frames of finger/thumb bones in HAND space (design right hand): name -> (head, R3, length)."""
    pose = rest_hand_pose()
    out = {}
    for name, mcp, lens, w0, t0 in H.FINGERS:
        R0, flex = pose["fingers"][name]
        joints, segs, _ = H.finger_frames(mcp, R0, lens, flex)
        for k in range(3):
            out["%s_%02d" % (FNAME[name], k + 1)] = (joints[k], segs[k], lens[k])
    R0, flex = pose["thumb"]
    joints, segs, _ = H.finger_frames(H.THUMB_CMC, R0, H.THUMB_LENS, flex)
    for k in range(3):
        out["thumb_%02d" % (k + 1)] = (joints[k], segs[k], H.THUMB_LENS[k])
    return out


BONE_PARENT = {"clavicle": None, "upperarm": "clavicle", "forearm": "upperarm", "forearm_twist": "forearm", "hand": "forearm"}
for _f in ("index", "middle", "ring", "pinky", "thumb"):
    BONE_PARENT[_f + "_01"] = "hand"
    BONE_PARENT[_f + "_02"] = _f + "_01"
    BONE_PARENT[_f + "_03"] = _f + "_02"
BONE_CONNECT = {"upperarm": True, "forearm": True, "hand": True}
for _f in ("index", "middle", "ring", "pinky", "thumb"):
    BONE_CONNECT[_f + "_02"] = True
    BONE_CONNECT[_f + "_03"] = True
BONE_ORDER = ["clavicle", "upperarm", "forearm", "forearm_twist", "hand"] + \
    ["%s_%02d" % (f, k) for f in ("thumb", "index", "middle", "ring", "pinky") for k in (1, 2, 3)]


def all_bone_frames():
    """Armature-space rest frames for both sides: 'name_X' -> (head, R3, length)."""
    lay = rest_layout()
    Hm = mat4(lay["hand"][1], lay["hand"][0])
    right = dict(lay)
    for n, (h, R, ln) in hand_bone_frames().items():
        right[n] = ((Hm @ h.to_4d()).to_3d(), Hm.to_3x3() @ R, ln)
    out = {}
    for n, (h, R, ln) in right.items():
        out[n + "_R"] = (h, R, ln)
        Ml = mirror_frame(mat4(R, h))
        out[n + "_L"] = (Ml.translation.copy(), Ml.to_3x3(), ln)
    return out


# ---------------------------------------------------------------- weights
def sstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def fore_weights(s):
    """Forearm-region weights by rest distance s from the elbow (shared by every shell -> no gaps)."""
    wh = sstep(0.224, 0.272, s)
    wt = sstep(0.05, 0.20, s)
    return {"hand": wh, "forearm_twist": (1 - wh) * wt, "forearm": (1 - wh) * (1 - wt)}


def arm_weights(t, zside=0.0):
    """t = rest path length from the shoulder (forearm starts at UPPER_LEN). zside in [-1,1]: -1 olecranon
    (back of elbow) keeps the upper-arm longer, +1 inner crease hands over earlier -> less elbow collapse."""
    ce = UPPER_LEN + 0.012 * (-zside)
    wf = sstep(ce - 0.038, ce + 0.038, t)
    wc = 1.0 - sstep(-0.035, 0.050, t)
    w = {"clavicle": (1 - wf) * wc * 0.6, "upperarm": (1 - wf) * (1 - wc * 0.6)}
    for k, v in fore_weights(max(0.0, t - UPPER_LEN)).items():
        w[k] = w.get(k, 0.0) + wf * v
    return w


class Groups:
    def __init__(self, suffix):
        self.suffix = suffix
        self.names = []
        self.idx = {}

    def i(self, bone):
        n = bone + "_" + self.suffix
        if n not in self.idx:
            self.idx[n] = len(self.names)
            self.names.append(n)
        return self.idx[n]


def _set_w(v, dl, groups, wdict):
    tot = sum(x for x in wdict.values() if x > 1e-6)
    for b, x in wdict.items():
        if x > 1e-6:
            v[dl][groups.i(b)] = x / tot


def _obj_from_bm(name, bm, groups, mats):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    for g in groups.names:
        o.vertex_groups.new(name=g)
    for m in mats:
        me.materials.append(mat(m))
    return o


def subd(o, lv):
    md = o.modifiers.new("s", "SUBSURF")
    md.levels = lv
    md.use_creases = True
    md.boundary_smooth = "ALL"
    apply_mods(o)
    smooth_all(o)
    return o


# ---------------------------------------------------------------- hand (rest pose, weighted cage)
def hand_cage_weighted(groups):
    """M2 glove cage in the rest pose (design right hand space) with per-vertex bone weights."""
    pose = rest_hand_pose()
    bm = bmesh.new()
    dl = bm.verts.layers.deform.verify()
    crease = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    fnames = [f[0] for f in H.FINGERS]
    rings = []
    for ri, (ys, xs, top, bot) in enumerate(H.PALM):
        r = [bm.verts.new((xs[k], ys[k], top[k])) for k in range(5)]
        r += [bm.verts.new((xs[k], ys[k], bot[k])) for k in range(4, -1, -1)]
        rings.append(r)
        for vi, v in enumerate(r):
            col = vi if vi < 5 else 9 - vi
            if ri <= 1:
                w = fore_weights(FORE_LEN + v.co.y)
            elif ri < 4:
                w = {"hand": 1.0}
            else:
                w = {"hand": 0.8}
                adj = [c for c in (col - 1, col) if 0 <= c < 4]
                for c in adj:
                    w[FNAME[fnames[c]] + "_01"] = 0.2 / len(adj)
            # thenar: palm verts around the thumb port follow the thumb metacarpal a little
            if ri in (1, 2) and (vi in (0, 9) or vi == 8):
                w = dict(w)
                w["thumb_01"] = 0.32 if vi in (0, 9) else 0.18
            _set_w(v, dl, groups, w)

    def face(vs, mi):
        try:
            f = bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = mi
        return f

    for r in range(4):
        a, b = rings[r], rings[r + 1]
        for k in range(10):
            if r == 1 and k == 9:
                continue
            face((a[k], a[(k + 1) % 10], b[(k + 1) % 10], b[k]), 1 if 5 <= k <= 8 else 0)
    r0 = rings[0]
    for k in range(4):
        face((r0[9 - k], r0[8 - k], r0[k + 1], r0[k]), 0)
    knuck = rings[4]

    def connect(ra, rb, mis=(0, 0, 1, 0), crease_bottom=True):
        for i in range(4):
            j = (i + 1) % 4
            face((ra[i], ra[j], rb[j], rb[i]), mis[i])
        if crease_bottom:
            for i in (2, 3):
                e = bm.edges.get((ra[i], rb[i]))
                if e:
                    e[crease] = 0.4

    info = {"fingers": {}, "thumb": None}
    for fi, (name, mcp, lens, w0, t0) in enumerate(H.FINGERS):
        b = FNAME[name]
        R0, flex = pose["fingers"][name]
        joints, segs, bis = H.finger_frames(mcp, R0, lens, flex)
        # joint rings are modelled ~6% fuller than M2: linear skinning loses volume at bent knuckles
        specs = [(joints[0], bis[0][0], w0 * 1.04, t0 * 1.06, {"hand": 0.5, b + "_01": 0.5}),
                 (joints[0] + (joints[1] - joints[0]) * 0.5, segs[0], w0 * 0.975, t0 * 0.965, {b + "_01": 1.0}),
                 (joints[1], bis[1][0], w0 * H.TAPER[1] * 1.03, t0 * H.TAPER[1] * 1.06, {b + "_01": 0.5, b + "_02": 0.5}),
                 (joints[2], bis[2][0], w0 * H.TAPER[2] * 1.03, t0 * H.TAPER[2] * 1.05, {b + "_02": 0.5, b + "_03": 0.5}),
                 (joints[2] + (joints[3] - joints[2]) * 0.62, segs[2], w0 * H.TAPER[3], t0 * H.TAPER[3] * 0.98, {b + "_03": 1.0}),
                 (joints[2] + (joints[3] - joints[2]) * 0.95, segs[2], w0 * H.TAPER[3] * 0.70, t0 * H.TAPER[3] * 0.62, {b + "_03": 1.0})]
        prev = [knuck[fi], knuck[fi + 1], knuck[9 - (fi + 1)], knuck[9 - fi]]
        for k, (c, R, w, t, wd) in enumerate(specs):
            ring = [bm.verts.new(p) for p in H._ring(c, R, w, t)]
            for v in ring:
                _set_w(v, dl, groups, wd)
            connect(prev, ring, crease_bottom=k > 0)
            prev = ring
        face(prev, 1)
        info["fingers"][name] = {"joints": joints, "segs": segs, "bis": bis,
                                 "rings": [(c, R, w, t, 1.0) for c, R, w, t, _ in specs], "w": w0, "t": t0}
    R0, flex = pose["thumb"]
    joints, segs, bis = H.finger_frames(H.THUMB_CMC, R0, H.THUMB_LENS, flex)
    port = [rings[1][0], rings[2][0], rings[2][9], rings[1][9]]
    tspecs = [(joints[0] + (joints[1] - joints[0]) * 0.42, segs[0], *H.THUMB_SIZES[0], {"hand": 0.3, "thumb_01": 0.7}),
              (joints[1], bis[1][0], H.THUMB_SIZES[1][0] * 1.03, H.THUMB_SIZES[1][1] * 1.05, {"thumb_01": 0.5, "thumb_02": 0.5}),
              (joints[2], bis[2][0], H.THUMB_SIZES[2][0] * 1.03, H.THUMB_SIZES[2][1] * 1.05, {"thumb_02": 0.5, "thumb_03": 0.5}),
              (joints[2] + (joints[3] - joints[2]) * 0.6, segs[2], *H.THUMB_SIZES[3], {"thumb_03": 1.0}),
              (joints[2] + (joints[3] - joints[2]) * 0.95, segs[2], *H.THUMB_SIZES[4], {"thumb_03": 1.0})]
    prev = port
    shift = 0
    for k, (c, R, w, t, wd) in enumerate(tspecs):
        pts = H._ring(c, R, w, t)
        if k == 0:
            best = None
            for sh in range(4):
                cand = pts[sh:] + pts[:sh]
                d = sum((cand[i] - prev[i].co).length for i in range(4))
                if best is None or d < best[0]:
                    best = (d, cand, sh)
            pts, shift = best[1], best[2]
        else:
            pts = pts[shift:] + pts[:shift]
        ring = [bm.verts.new(p) for p in pts]
        for v in ring:
            _set_w(v, dl, groups, wd)
        mis = [0, 0, 0, 0]
        mis[(2 - shift) % 4] = 1
        connect(prev, ring, mis=tuple(mis), crease_bottom=False)
        prev = ring
    face(prev, 1)
    info["thumb"] = {"joints": joints, "segs": segs, "bis": bis}
    return bm, info


def build_hand_right(groups):
    bm, info = hand_cage_weighted(groups)
    o = _obj_from_bm("hand_R_glove", bm, groups, ["glove", "glove_palm"])
    subd(o, 2)
    parts = [o]
    bm2 = bmesh.new()
    bm2.from_mesh(o.data)
    bvh = BVHTree.FromBMesh(bm2)
    bm2.free()
    parts.append(H.knuckle_guard(bvh, info))
    for fname, fd in info["fingers"].items():
        c2, R2, w2, t2, _ = fd["rings"][1]
        parts.append(H.make_pad(bvh, "fpad_" + fname, c2, R2, w2 * 0.34, 0.0072, 0.0026, ring_n=6))
    for k, (yy, ww) in enumerate(((0.036, 0.020), (0.049, 0.024), (0.062, 0.026))):
        parts.append(H.make_pad(bvh, "backbar%d" % k, V((-0.004, yy, 0.0)), H.rz(0.06), ww, 0.0040, 0.0017, ring_n=8, pw=4.0))
    th = info["thumb"]
    parts.append(H.make_pad(bvh, "thumbpad", th["joints"][1] + (th["joints"][2] - th["joints"][1]) * 0.45, th["segs"][1],
                            0.0062, 0.0085, 0.0026, ring_n=6))
    for p in parts[1:]:
        p.data.materials.clear()
        p.data.materials.append(mat("glove_palm"))
        transfer_weights(p, o)
    return parts, info


# ---------------------------------------------------------------- sleeve along the bent arm
def path_point(t, lay):
    """Centre and ring frame (X, Z) at rest path length t (shoulder -> elbow -> wrist), with the
    cross-section rolling from the forearm frame to the hand frame toward the wrist."""
    S, Ru, _ = lay["upperarm"]
    E, Rf, _ = lay["forearm"]
    Rh = lay["hand"][1]
    du, df = Ru.col[1], Rf.col[1]
    if t <= UPPER_LEN - 0.03:
        return S + du * t, Ru
    if t >= UPPER_LEN + 0.03:
        s = t - UPPER_LEN
        roll = _roll_to_hand(Rf, Rh) * sstep(0.0, FORE_LEN, s)
        return E + df * s, Rf @ H.ry(roll)
    a = (t - (UPPER_LEN - 0.03)) / 0.06
    p0, p2 = E - du * 0.03, E + df * 0.03
    p = p0 * (1 - a) ** 2 + E * 2 * a * (1 - a) + p2 * a * a
    q = Ru.to_quaternion().slerp(Rf.to_quaternion(), a)
    return p, q.to_matrix()


def _roll_to_hand(Rf, Rh):
    """Angle phi about the forearm's local +Y so that (Rf @ ry(phi)) has its X along the hand's X."""
    xh = Rh.col[0]
    return math.atan2(-xh.dot(Rf.col[2]), xh.dot(Rf.col[0]))


def _hash(i, j, k=0):
    n = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791)
    n = (n ^ (n >> 13)) * 1274126177
    return ((n & 0xFFFF) / 32767.5) - 1.0


def loft_weighted(name, stations, groups, lay, material, nv=14, wrinkle=0.0, seam_at=None, cap0=True, cap1=True,
                  inner=None, seed=0, pw=2.3):
    """stations: (t, hx, hz, zoff). Weights from arm_weights(t, zside) per vertex."""
    bm = bmesh.new()
    dl = bm.verts.layers.deform.verify()
    crease = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    rings = []
    allst = [(st, False) for st in stations] + [((t, hx, hz, zo), True) for (t, hx, hz, zo) in (inner or [])]
    for si, ((t, hx, hz, zo), is_inner) in enumerate(allst):
        c, R = path_point(t, lay)
        X, Z = R.col[0], R.col[2]
        ring = []
        for i in range(nv):
            a = 2 * math.pi * i / nv
            ca, sa = math.cos(a), math.sin(a)
            x = hx * math.copysign(abs(ca) ** (2 / pw), ca)
            z = hz * math.copysign(abs(sa) ** (2 / pw), sa)
            r = 1.0
            if wrinkle and not is_inner and 0 < si < len(stations) - 1:
                r += wrinkle * (0.6 * math.sin(3 * a + si * 1.7 + seed) + 0.4 * _hash(si, i, seed))
            if seam_at is not None and i == seam_at and not is_inner:
                r += 0.0012 / max(hx, hz)
            v = bm.verts.new(c + X * x * r + Z * (z * r + zo))
            _set_w(v, dl, groups, arm_weights(t, sa))
            ring.append(v)
        rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(nv):
            j = (i + 1) % nv
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
        if seam_at is not None and k < len(stations) - 1:
            e = bm.edges.get((rings[k][seam_at], rings[k + 1][seam_at]))
            if e:
                e[crease] = 0.7
    if not inner:
        if cap0:
            bm.faces.new(rings[0][::-1])
        if cap1:
            bm.faces.new(rings[-1])
    return _obj_from_bm(name, bm, groups, [material])


def transfer_weights(target, source, k=4):
    """Copy smooth weights from the nearest source vertices (inverse-distance blend)."""
    kd = KDTree(len(source.data.vertices))
    for v in source.data.vertices:
        kd.insert(v.co, v.index)
    kd.balance()
    sg = {g.index: g.name for g in source.vertex_groups}
    for g in source.vertex_groups:
        if g.name not in target.vertex_groups:
            target.vertex_groups.new(name=g.name)
    tg = {g.name: g for g in target.vertex_groups}
    for v in target.data.vertices:
        acc = {}
        tot = 0.0
        for co, idx, dist in kd.find_n(v.co, k):
            wgt = 1.0 / max(1e-5, dist) ** 2
            tot += wgt
            for ge in source.data.vertices[idx].groups:
                acc[sg[ge.group]] = acc.get(sg[ge.group], 0.0) + ge.weight * wgt
        for name, x in acc.items():
            if x / tot > 1e-4:
                tg[name].add([v.index], x / tot, "REPLACE")


def pillow_at(name, obj, origin, direction, s, d, ws, ls, h, material, n=10, pw=3.2, taper=0.82, lv=1, sink=0.0015):
    bmo = bmesh.new()
    bmo.from_mesh(obj.data)
    bvh = BVHTree.FromBMesh(bmo)
    bmo.free()
    hit = bvh.ray_cast(V(origin), V(direction).normalized(), 1.0)
    base = hit[0] if hit[0] is not None else V(origin)
    u = -V(direction).normalized()
    base = base - u * sink
    bm = bmesh.new()
    rings = []
    for hz, sc in ((0.0, 1.0), (h * 0.6, 1.0), (h, taper)):
        ring = []
        for i in range(n):
            t = 2 * math.pi * (i + 0.5) / n
            c, sn = math.cos(t), math.sin(t)
            ring.append(bm.verts.new(base + s * (ws * sc * math.copysign(abs(c) ** (2 / pw), c)) +
                                     d * (ls * sc * math.copysign(abs(sn) ** (2 / pw), sn)) + u * hz))
        rings.append(ring)
    for k in range(2):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    me.materials.append(mat(material))
    if lv:
        subd(o, lv)
    transfer_weights(o, obj)
    return o


def build_arm_right(groups):
    """Right arm skin in armature space: sleeve, elbow/shoulder details, gauntlet, strap, glove."""
    lay = rest_layout()
    S, Ru, _ = lay["upperarm"]
    E, Rf, _ = lay["forearm"]
    W, Rh, _ = lay["hand"]
    U = UPPER_LEN
    sleeve_st = [(-0.035, 0.0590, 0.0570, 0.0), (0.000, 0.0585, 0.0565, 0.0), (0.050, 0.0575, 0.0550, 0.0),
                 (0.100, 0.0560, 0.0530, 0.0), (0.150, 0.0545, 0.0510, -0.001), (0.200, 0.0525, 0.0495, -0.001),
                 (0.240, 0.0512, 0.0482, -0.0012), (0.265, 0.0510, 0.0480, -0.0015), (0.282, 0.0505, 0.0475, -0.0018),
                 (U, 0.0498, 0.0470, -0.0020), (U + 0.018, 0.0490, 0.0458, -0.0015), (U + 0.036, 0.0478, 0.0440, -0.0005),
                 (U + 0.060, 0.0466, 0.0420, 0.0), (U + 0.090, 0.0448, 0.0395, 0.0), (U + 0.112, 0.0430, 0.0372, 0.0),
                 (U + 0.128, 0.0418, 0.0360, 0.0), (U + 0.139, 0.0402, 0.0344, 0.0), (U + 0.150, 0.0410, 0.0350, 0.0),
                 (U + 0.161, 0.0392, 0.0333, 0.0), (U + 0.173, 0.0398, 0.0337, 0.0), (U + 0.187, 0.0402, 0.0340, 0.0),
                 (U + 0.204, 0.0402, 0.0340, 0.0), (U + 0.208, 0.0380, 0.0320, 0.0)]
    sl = loft_weighted("sleeve_R", sleeve_st, groups, lay, "fabric_jacket", nv=14, wrinkle=0.026, seam_at=10, seed=5,
                       cap1=False)
    subd(sl, 1)
    parts = [sl]
    # shoulder pocket + flap + ID patch on the lateral side (+X), elbow patch on the olecranon side (-Z)
    c, R = path_point(0.095, lay)
    X, Y, Z = R.col[0], R.col[1], R.col[2]
    parts.append(pillow_at("pocket", sl, c + X * 0.2, -X, Z, Y, 0.026, 0.040, 0.0065, "fabric_jacket", n=12))
    c2, _ = path_point(0.128, lay)
    parts.append(pillow_at("pocket_flap", sl, c2 + X * 0.2, -X, Z, Y, 0.027, 0.012, 0.0072, "fabric_jacket", n=12, sink=0.0))
    c3, _ = path_point(0.088, lay)
    parts.append(pillow_at("patch", sl, c3 + X * 0.2, -X, Z, Y, 0.019, 0.024, 0.0080, "glove_palm", n=12, pw=4.0, sink=-0.0002))
    ce, Re = path_point(U - 0.010, lay)
    parts.append(pillow_at("elbow_patch", sl, ce - Re.col[2] * 0.2, Re.col[2], Re.col[0], Re.col[1], 0.034, 0.030, 0.0032,
                           "fabric_jacket", n=12))
    cc, Rc = path_point(U + 0.196, lay)
    parts.append(pillow_at("cuff_tab", sl, cc + Rc.col[0] * 0.2, -Rc.col[0], Rc.col[2], Rc.col[1], 0.0105, 0.0095, 0.0028,
                           "fabric_jacket", n=8))
    # glove gauntlet (open shell with inner lip), wrist strap and pull tab
    g_st = [(U + 0.192, 0.0345, 0.0288, 0.0), (U + 0.206, 0.0372, 0.0312, 0.0), (U + 0.230, 0.0362, 0.0292, 0.0),
            (U + 0.252, 0.0350, 0.0272, 0.0), (U + 0.264, 0.0338, 0.0260, 0.0)]
    g_in = [(U + 0.2655, 0.0322, 0.0244, 0.0), (U + 0.252, 0.0326, 0.0246, 0.0)]
    g = loft_weighted("gauntlet_R", g_st, groups, lay, "glove", nv=14, inner=g_in)
    subd(g, 1)
    parts.append(g)
    s_st = [(U + 0.214, 0.0376, 0.0310, 0.0), (U + 0.2165, 0.0386, 0.0320, 0.0), (U + 0.2305, 0.0378, 0.0306, 0.0),
            (U + 0.233, 0.0366, 0.0296, 0.0)]
    st = loft_weighted("strap_R", s_st, groups, lay, "glove_palm", nv=14)
    subd(st, 1)
    parts.append(st)
    ct, Rt = path_point(U + 0.2235, lay)
    parts.append(pillow_at("strap_tab", st, ct + Rt.col[2] * 0.2 + Rt.col[0] * 0.012, -Rt.col[2], Rt.col[0], Rt.col[1],
                           0.0085, 0.0095, 0.0042, "glove_palm", n=8))
    # glove: M2 cage in rest pose, placed by the hand bone rest frame
    hand_parts, info = build_hand_right(groups)
    Hm = mat4(Rh, W)
    for p in hand_parts:
        p.data.transform(Hm)
        p.data.update()
    parts += hand_parts
    return parts, lay, info


def build_watch_right(sleeve, lay, groups):
    """Watch on the inner (ventral, -Z of the rolled wrist frame) side, authored on the right arm and
    mirrored onto the left forearm."""
    U = UPPER_LEN
    t = U + 0.170
    c, R = path_point(t, lay)
    X, Y, Z = R.col[0], R.col[1], R.col[2]
    parts = []
    bst = [(t - 0.0105, 0.0398, 0.0345, 0.0), (t - 0.009, 0.0410, 0.0357, 0.0), (t + 0.009, 0.0410, 0.0357, 0.0),
           (t + 0.0105, 0.0398, 0.0345, 0.0)]
    band = loft_weighted("watch_band", bst, groups, lay, "watch", nv=14)
    subd(band, 1)
    parts.append(band)
    case = pillow_at("watch_case", sleeve, c - Z * 0.2, Z, X, Y, 0.0185, 0.0195, 0.0095, "watch", n=12, pw=3.4, taper=0.92,
                     sink=-0.0012)
    parts.append(case)
    bmo = bmesh.new()
    bmo.from_mesh(sleeve.data)
    bvh = BVHTree.FromBMesh(bmo)
    bmo.free()
    hit = bvh.ray_cast(c - Z * 0.2, Z, 1.0)
    top = hit[0] - Z * (0.0012 + 0.0095)
    u = -Z
    m = L.MB()
    m.lathe([(0.0158, -0.0004), (0.0172, -0.0004), (0.0172, 0.0016), (0.0160, 0.0024), (0.0128, 0.0024), (0.0128, 0.0004),
             (0.0, 0.0004)], n=18, off=top, axis_vec=u)
    bz = m.obj("watch_bezel", "watch")
    m = L.MB()
    m.lathe([(0.0128, 0.0), (0.0128, 0.0012), (0.0, 0.0016)], n=18, off=top, axis_vec=u)
    cr = m.obj("watch_crystal", "watch")
    parts += [bz, cr]
    for sx in (-1, 1):
        m = L.MB()
        for dy in (-0.008, 0.008):
            m.lathe([(0.0022, 0.0), (0.0022, 0.0032), (0.0016, 0.0038), (0.0, 0.0038)], n=8,
                    off=top - u * 0.0045 + X * sx * 0.0175 + Y * dy, axis_vec=X * sx)
        parts.append(m.obj("watch_push", "watch"))
    for p in parts[2:]:
        L.sharp_by_angle(p, 40)
        transfer_weights(p, sleeve)
    return parts


# ---------------------------------------------------------------- armature
def build_armature(name="FPArms"):
    frames = all_bone_frames()
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for side in SIDES:
        for b in BONE_ORDER:
            n = b + "_" + side
            h, R, ln = frames[n]
            eb = arm.edit_bones.new(n)
            eb.head = h
            eb.tail = h + R.col[1] * ln
            eb.align_roll(R.col[2])
            p = BONE_PARENT[b]
            if p:
                eb.parent = arm.edit_bones[p + "_" + side]
                eb.use_connect = BONE_CONNECT.get(b, False) and (eb.parent.tail - eb.head).length < 1e-6
            eb.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)
    return ob, frames


def bone_doc(ob, frames):
    """Rest roll/axes of every bone (armature space) and the deviation from the intended frames."""
    out = {}
    worst = 0.0
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    rolls = {eb.name: eb.roll for eb in ob.data.edit_bones}
    bpy.ops.object.mode_set(mode="OBJECT")
    for b in ob.data.bones:
        M = b.matrix_local
        R = M.to_3x3()
        h, Rt, ln = frames[b.name]
        dev = max((M.translation - h).length, max((R.col[i] - Rt.col[i]).length for i in range(3)))
        worst = max(worst, dev)
        out[b.name] = {"parent": b.parent.name if b.parent else None, "connected": b.use_connect,
                       "head": [round(x, 6) for x in b.head_local], "tail": [round(x, 6) for x in b.tail_local],
                       "length": round(b.length, 6), "roll_rad": round(rolls[b.name], 6),
                       "x_axis": [round(x, 6) for x in R.col[0]], "y_axis": [round(x, 6) for x in R.col[1]],
                       "z_axis": [round(x, 6) for x in R.col[2]], "frame_dev": dev}
    return out, worst
