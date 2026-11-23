# First-person arms: jacket sleeves, softshell forearms with glove gauntlets, watch, three posed hands.
# Every segment: origin at its proximal joint, extends along +Y. Right-side design; *_L are mirrored.
# Segment axes: +Y distal, +Z dorsal (back of forearm / back of hand), -X thumb side for the RIGHT arm
# (+X for the left). Upper arm: +X lateral (outer) on the right arm, -Z olecranon side.
import math
import bmesh, bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import wpn_lib as L
from wpn_lib import V, mat, link, apply_mods, smooth_all, join, MIRROR_X, empty, set_parent
import wpn_hands as H
import wpn_poses as P


def _h(i, j, k=0):
    """Deterministic hash noise in [-1, 1]."""
    n = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791)
    n = (n ^ (n >> 13)) * 1274126177
    return ((n & 0xFFFF) / 32767.5) - 1.0


def sleeve_loft(name, stations, nv=16, material="fabric_jacket", wrinkle=0.0, seam_at=None, seam_h=0.0012,
                open_end=False, inner=None, seed=0, mats=None):
    """Loft of superelliptic rings. stations: (y, hx, hz, zoff). Optional seam ridge at angle seam_at."""
    bm = bmesh.new()
    crease = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    rings = []
    for si, (y, hx, hz, zo) in enumerate(stations):
        ring = []
        for i in range(nv):
            t = 2 * math.pi * i / nv
            c, s = math.cos(t), math.sin(t)
            pw = 2.3
            x = hx * math.copysign(abs(c) ** (2 / pw), c)
            z = hz * math.copysign(abs(s) ** (2 / pw), s)
            r = 1.0
            if wrinkle and 0 < si < len(stations) - 1:
                r += wrinkle * (0.6 * math.sin(3 * t + si * 1.7 + seed) + 0.4 * _h(si, i, seed))
            if seam_at is not None and i == seam_at:
                r += seam_h / max(hx, hz)
            ring.append(bm.verts.new((x * r, y, z * r + zo)))
        rings.append(ring)
    if inner:
        for (y, hx, hz, zo) in inner:
            ring = []
            for i in range(nv):
                t = 2 * math.pi * i / nv
                c, s = math.cos(t), math.sin(t)
                x = hx * math.copysign(abs(c) ** (2 / 2.3), c)
                z = hz * math.copysign(abs(s) ** (2 / 2.3), s)
                ring.append(bm.verts.new((x, y, z + zo)))
            rings.append(ring)
    for k in range(len(rings) - 1):
        for i in range(nv):
            j = (i + 1) % nv
            f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            if mats:
                f.material_index = mats(k, i)
        if seam_at is not None and k < len(stations) - 1:
            e = bm.edges.get((rings[k][seam_at], rings[k + 1][seam_at]))
            if e:
                e[crease] = 0.7
    if not inner:
        bm.faces.new(rings[0][::-1])
        if not open_end:
            bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    me.materials.append(mat(material))
    return o


def subd(o, lv=1):
    md = o.modifiers.new("s", "SUBSURF")
    md.levels = lv
    md.use_creases = True
    apply_mods(o)
    smooth_all(o)
    return o


def pillow(name, base, s, d, u, ws, ls, h, material, n=12, pw=3.2, lv=1, taper=0.82):
    bm = bmesh.new()
    rings = []
    for hz, sc in ((0.0, 1.0), (h * 0.6, 1.0), (h, taper)):
        ring = []
        for i in range(n):
            t = 2 * math.pi * (i + 0.5) / n
            c, sn = math.cos(t), math.sin(t)
            x = ws * sc * math.copysign(abs(c) ** (2 / pw), c)
            y = ls * sc * math.copysign(abs(sn) ** (2 / pw), sn)
            ring.append(bm.verts.new(base + s * x + d * y + u * hz))
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
    return subd(o, lv)


def surface_point(obj, origin, direction):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    hit = t.ray_cast(V(origin), V(direction).normalized(), 1.0)
    return hit[0] if hit[0] is not None else V(origin)


# ---------------------------------------------------------------- segments
def upper_arm(name):
    st = [(0.000, 0.058, 0.056, 0.0), (0.050, 0.0575, 0.0550, 0.0), (0.100, 0.0560, 0.0530, 0.0), (0.150, 0.0545, 0.0510, -0.001),
          (0.200, 0.0525, 0.0495, -0.001), (0.240, 0.0510, 0.0480, -0.001), (0.270, 0.0515, 0.0485, -0.0015),
          (0.290, 0.0505, 0.0478, -0.0015), (0.305, 0.0490, 0.0465, -0.0012), (0.314, 0.0470, 0.0445, -0.001)]
    o = sleeve_loft(name, st, nv=16, wrinkle=0.018, seam_at=12, seed=3)
    subd(o, 1)
    parts = [o]
    # shoulder pocket (lateral, +X) with flap and an ID/IR patch block
    p = surface_point(o, (0.2, 0.095, 0.004), (-1, 0, 0))
    parts.append(pillow("pocket", p - V((0.002, 0, 0)), V((0, 0, 1)), V((0, 1, 0)), V((1, 0, 0)), 0.026, 0.040, 0.0065, "fabric_jacket", n=12))
    parts.append(pillow("pocket_flap", p + V((0.0035, 0.033, 0.0)), V((0, 0, 1)), V((0, 1, 0)), V((1, 0, 0)).lerp(V((0, -0.2, 0)), 0.0),
                        0.027, 0.012, 0.0045, "fabric_jacket", n=12))
    parts.append(pillow("patch", p + V((0.0062, -0.006, 0.0)), V((0, 0, 1)), V((0, 1, 0)), V((1, 0, 0)), 0.019, 0.024, 0.0018, "rubber", n=12, pw=4.0))
    # elbow reinforcement panel (olecranon side, -Z)
    pe = surface_point(o, (0.0, 0.282, -0.2), (0, 0, 1))
    parts.append(pillow("elbow_patch", pe + V((0, 0, 0.002)), V((1, 0, 0)), V((0, 1, 0)), V((0, 0, -1)), 0.036, 0.028, 0.0035, "fabric_jacket", n=12))
    return join(parts, name)


def forearm(name, watch=False):
    # softshell pushed up the forearm: bunched folds toward the cuff
    st = [(0.000, 0.0455, 0.0425, 0.0), (0.030, 0.0465, 0.0430, 0.001), (0.070, 0.0452, 0.0405, 0.001), (0.105, 0.0428, 0.0374, 0.0),
          (0.125, 0.0418, 0.0362, 0.0), (0.138, 0.0402, 0.0346, 0.0), (0.150, 0.0410, 0.0352, 0.0), (0.160, 0.0392, 0.0334, 0.0),
          (0.172, 0.0398, 0.0338, 0.0), (0.186, 0.0402, 0.0340, 0.0), (0.204, 0.0402, 0.0340, 0.0), (0.208, 0.0380, 0.0320, 0.0)]
    sl = sleeve_loft(name, st, nv=16, wrinkle=0.030, seam_at=12, seed=7)
    subd(sl, 1)
    parts = [sl]
    # cuff tab (velcro adjuster on the ulnar side)
    pc = surface_point(sl, (0.2, 0.196, -0.006), (-1, 0, 0))
    parts.append(pillow("cuff_tab", pc, V((0, 0, 1)), V((0, 1, 0)), V((1, 0, 0)), 0.0105, 0.0095, 0.0028, "fabric_jacket", n=8))
    # glove gauntlet: open shell with an inner lip
    gst = [(0.192, 0.0345, 0.0288, 0.0), (0.206, 0.0372, 0.0312, 0.0), (0.230, 0.0362, 0.0292, 0.0), (0.252, 0.0350, 0.0272, 0.0),
           (0.264, 0.0338, 0.0260, 0.0)]
    inner = [(0.2655, 0.0322, 0.0244, 0.0), (0.252, 0.0326, 0.0246, 0.0)]
    g = sleeve_loft(name + "_gauntlet", gst, nv=14, material="glove", inner=inner)
    subd(g, 1)
    parts.append(g)
    # wrist strap band + pull tab
    sst = [(0.214, 0.0376, 0.0310, 0.0), (0.2165, 0.0386, 0.0320, 0.0), (0.2305, 0.0378, 0.0306, 0.0), (0.233, 0.0366, 0.0296, 0.0)]
    s = sleeve_loft(name + "_strap", sst, nv=14, material="glove_palm")
    subd(s, 1)
    parts.append(s)
    pt = surface_point(s, (0.2, 0.2235, 0.012), (-1, 0, 0))
    parts.append(pillow("strap_tab", pt, V((0, 0, 1)), V((0, 1, 0)), V((1, 0, 0)), 0.0085, 0.0095, 0.0042, "rubber", n=8))
    if watch:
        parts += _watch(sl, 0.170)
    return join(parts, name)


def _watch(sleeve, y):
    """Tactical watch on the VENTRAL side (-Z, inside of the wrist) so it faces the shooter."""
    parts = []
    base = surface_point(sleeve, (0.0, y, -0.2), (0, 0, 1))
    u = V((0, 0, -1))
    s = V((1, 0, 0))
    d = V((0, 1, 0))
    # strap band around the sleeve
    bst = [(y - 0.0105, 0.0398, 0.0345, 0.0), (y - 0.009, 0.0410, 0.0357, 0.0), (y + 0.009, 0.0410, 0.0357, 0.0), (y + 0.0105, 0.0398, 0.0345, 0.0)]
    b = sleeve_loft("watch_band", bst, nv=14, material="watch")
    subd(b, 1)
    parts.append(b)
    case = pillow("watch_case", base + u * 0.0015, s, d, u, 0.0185, 0.0195, 0.0095, "watch", n=12, pw=3.4, taper=0.92)
    parts.append(case)
    top = base + u * (0.0015 + 0.0095)
    # bezel ring
    m = L.MB()
    m.lathe([(0.0158, -0.0004), (0.0172, -0.0004), (0.0172, 0.0016), (0.0160, 0.0024), (0.0128, 0.0024), (0.0128, 0.0004)], n=18, off=top, axis_vec=u)
    bz = m.obj("watch_bezel", "watch")
    L.finish(bz, 0.0, 1, 40)
    parts.append(bz)
    m = L.MB()
    m.lathe([(0.0128, 0.0), (0.0128, 0.0012), (0.0, 0.0016)], n=18, off=top, axis_vec=u)
    parts.append(m.obj("watch_crystal", "glass_lens"))
    for sx in (-1, 1):   # pushers
        m = L.MB()
        for dy in (-0.008, 0.008):
            m.lathe([(0.0022, 0.0), (0.0022, 0.0032), (0.0016, 0.0038), (0.0, 0.0038)], n=8, off=base + u * 0.006 + s * sx * 0.0175 + d * dy, axis_vec=s * sx)
        parts.append(m.obj("watch_push", "watch"))
    return parts


# ---------------------------------------------------------------- hands
def hand_R():
    d = P.hand_R_def()
    o, info = H.build_hand("hand_R", d["pose"], grips=[d["grip"]])
    return o


def hand_L():
    d = P.hand_L_def()
    o, info = H.build_hand("hand_L", d["pose"], grips=[d["grip"]], mirror=True)
    return o


def hand_L_fist():
    d = P.hand_fist_def()
    o, info = H.build_hand("hand_L_fist", d["pose"], grips=[d["grip"]], mirror=True)
    return o


def build():
    objs = []
    layout = [("upper_R", lambda: upper_arm("upper_R"), False), ("upper_L", lambda: upper_arm("upper_L"), True),
              ("fore_R", lambda: forearm("fore_R"), False), ("fore_L", lambda: forearm("fore_L", watch=True), True)]
    x = 0.0
    for name, fn, mirror in layout:
        o = fn()
        if mirror:
            o.data.transform(MIRROR_X)
            o.data.flip_normals()
            o.data.update()
        o.name = name
        o.data.name = name
        o.location = (x, 0, 0)
        x += 0.18
        objs.append(o)
    for fn in (hand_R, hand_L, hand_L_fist):
        o = fn()
        o.location = (x, 0, 0)
        x += 0.15
        objs.append(o)
    return objs
