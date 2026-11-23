# Procedural gloved hand: low-poly cage (palm rings + finger/thumb rings) -> Catmull-Clark.
# Design space is a RIGHT hand: origin at the wrist joint, +Y toward the fingers,
# palm normal -Z (palm faces -Z), thumb on the -X side. Left hands are mirrored in X.
# Fingers are posed by a tangent-walk around a virtual grip prism (the exact cross-section of the
# real part), so pads touch the surface without guesswork; the subdivided skin is then pushed out of
# the grip (soft-tissue conform) so nothing penetrates.
import math
import bmesh, bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from m2lib import V, mat, link, smooth_all, apply_mods, MIRROR_X

# ---------------------------------------------------------------- anatomy (gloved, metres)
# palm rings: ys per column, xs per column, dorsal z, ventral z (columns = finger-port boundaries)
PALM = [
    ([-0.030] * 5, [-0.0300, -0.0150, 0.0, 0.0150, 0.0295], [0.0165, 0.0170, 0.0170, 0.0168, 0.0160], [-0.0168, -0.0170, -0.0170, -0.0168, -0.0162]),
    ([0.002] * 5, [-0.0308, -0.0155, 0.0, 0.0150, 0.0293], [0.0128, 0.0134, 0.0134, 0.0131, 0.0123], [-0.0150, -0.0155, -0.0155, -0.0152, -0.0145]),
    ([0.038] * 5, [-0.0405, -0.0200, 0.0, 0.0190, 0.0370], [0.0136, 0.0142, 0.0142, 0.0140, 0.0130], [-0.0188, -0.0172, -0.0162, -0.0166, -0.0162]),
    ([0.064] * 5, [-0.0428, -0.0210, -0.0005, 0.0195, 0.0385], [0.0128, 0.0137, 0.0137, 0.0134, 0.0124], [-0.0160, -0.0158, -0.0156, -0.0158, -0.0152]),
    ([0.0830, 0.0858, 0.0862, 0.0802, 0.0745], [-0.0423, -0.0208, 0.0, 0.0199, 0.0380], [0.0118, 0.0124, 0.0124, 0.0121, 0.0114], [-0.0126, -0.0129, -0.0129, -0.0127, -0.0120]),
]
PALM_BOTTOM = 0.0150   # nominal ventral surface depth used to seat grips

FINGERS = [
    # name, MCP joint, phalanx lengths, base width, base thickness
    ("index", V((-0.0314, 0.0935, 0.0006)), (0.0440, 0.0262, 0.0236), 0.0212, 0.0200),
    ("middle", V((-0.0104, 0.0975, 0.0008)), (0.0482, 0.0298, 0.0252), 0.0212, 0.0202),
    ("ring", V((0.0100, 0.0935, 0.0006)), (0.0452, 0.0288, 0.0242), 0.0200, 0.0194),
    ("little", V((0.0290, 0.0850, 0.0000)), (0.0362, 0.0216, 0.0222), 0.0180, 0.0176),
]
TAPER = (1.0, 0.95, 0.88, 0.80)        # width/thickness factor at MCP, PIP, DIP, tip
THUMB_CMC = V((-0.0280, 0.0150, -0.0050))
THUMB_LENS = (0.0420, 0.0330, 0.0285)
THUMB_SIZES = [(0.0300, 0.0262), (0.0228, 0.0208), (0.0212, 0.0188), (0.0200, 0.0168), (0.0140, 0.0112)]
SUBD_SHRINK = 0.93     # Catmull-Clark limit of a square ring is ~0.93 of its side


def rx(a):
    return Matrix.Rotation(a, 3, "X")


def ry(a):
    return Matrix.Rotation(a, 3, "Y")


def rz(a):
    return Matrix.Rotation(a, 3, "Z")


# ---------------------------------------------------------------- kinematics
def finger_frames(mcp, R0, lens, flex):
    """FK. Each flex curls d toward -u about the local s axis. Returns joints [MCP, PIP, DIP, tip],
    segment frames [R_prox, R_mid, R_dist] and the bisector frames at MCP/PIP/DIP."""
    joints = [V(mcp)]
    segs = []
    bis = []
    R = R0.copy()
    for L, f in zip(lens, flex):
        Rb = R @ rx(-f / 2)
        R = R @ rx(-f)
        bis.append((Rb, f))
        segs.append(R.copy())
        joints.append(joints[-1] + R.col[1] * L)
    return joints, segs, bis


def thumb_R0(psi, phi, rho):
    return rz(psi) @ rx(-phi) @ ry(rho)


# ---------------------------------------------------------------- virtual grip
class Grip:
    """Prism: 2D convex shape (u, v) extruded along a, placed by frame F (columns u, v, a, point)."""

    def __init__(self, F, shape):
        self.F = F
        self.Fi = F.inverted()
        self.shape = [V((p[0], p[1])) for p in shape]
        n = len(self.shape)
        # outward normals of the polygon edges (CCW or CW handled by centroid test)
        c = sum(self.shape, V((0, 0))) / n
        self.edges = []
        for i in range(n):
            a, b = self.shape[i], self.shape[(i + 1) % n]
            e = b - a
            nn = V((e.y, -e.x)).normalized()
            if nn.dot(a - c) < 0:
                nn = -nn
            self.edges.append((a, b, nn))
        self.center2 = c

    def local(self, p):
        q = self.Fi @ V(p)
        return V((q.x, q.y)), q.z

    def signed_dist(self, p):
        """Signed distance from p to the prism surface (negative inside) and outward 2D normal."""
        q2, _ = self.local(p)
        best = None
        inside = True
        for a, b, nn in self.edges:
            if (q2 - a).dot(nn) > 0:
                inside = False
        for a, b, nn in self.edges:
            e = b - a
            t = max(0.0, min(1.0, (q2 - a).dot(e) / e.length_squared))
            cp = a + e * t
            d = (q2 - cp).length
            if best is None or d < best[0]:
                best = (d, cp)
        d, cp = best
        n2 = (q2 - cp).normalized() if d > 1e-9 else self.edges[0][2]
        if inside:
            d = -d
            n2 = -n2
        return d, n2

    def push_out(self, p, margin):
        d, n2 = self.signed_dist(p)
        if d >= margin:
            return p, d
        q = self.Fi @ V(p)
        q2 = V((q.x, q.y)) + n2 * (margin - d)
        return self.F @ V((q2.x, q2.y, q.z)), d

    def section_points(self, origin, s_axis, d0, u0, radius, ring=8):
        """Cross-section of the prism in the finger plane (normal s_axis through origin), dilated by
        radius, returned as 2D points (along d0, along u0)."""
        a = self.F.col[2].to_3d().normalized()
        uu = self.F.col[0].to_3d()
        vv = self.F.col[1].to_3d()
        P = self.F.col[3].to_3d()
        den = a.dot(s_axis)
        pts = []
        if abs(den) < 1e-4:
            return pts
        for sp in self.shape:
            base = P + uu * sp.x + vv * sp.y
            t = (origin - base).dot(s_axis) / den
            Q = base + a * t
            rel = Q - origin
            x2, y2 = rel.dot(d0), rel.dot(u0)
            for k in range(ring):
                ang = 2 * math.pi * k / ring
                pts.append(V((x2 + radius * math.cos(ang), y2 + radius * math.sin(ang))))
        return pts


def wrap_finger(grip, mcp, R0, lens, radius, flex_default=(0.25, 0.25, 0.2), flex_max=(1.65, 1.85, 1.45),
                hyper=0.12, tip_extra=0.0):
    """Tangent-walk: each phalanx turns until it just touches the dilated grip section."""
    s_axis = R0.col[0]
    d0 = R0.col[1]
    u0 = R0.col[2]
    cloud = grip.section_points(V(mcp), s_axis, d0, u0, radius)
    pos = V((0.0, 0.0))
    beta = 0.0
    flex = []
    for k, L in enumerate(lens):
        best = None
        for q in cloud:
            r = q - pos
            dist = r.length
            if dist > L + radius * 0.5 or dist < 1e-6:
                continue
            th = math.atan2(r.y, r.x)
            dl = (th - beta + math.pi) % (2 * math.pi) - math.pi
            if dl < -flex_max[k] - 0.6 or dl > hyper + 0.6:
                continue
            if best is None or dl > best:
                best = dl
        want = best if best is not None else -flex_default[k]
        want = max(-flex_max[k], min(hyper, want))
        f = -want
        if k == len(lens) - 1:
            f += tip_extra
        flex.append(f)
        beta -= f
        pos = pos + V((math.cos(beta), math.sin(beta))) * L
    return flex


class Poly2:
    """Convex polygon in a finger plane with a signed distance."""

    def __init__(self, pts):
        pts = [V((p[0], p[1])) for p in pts]
        c = sum(pts, V((0, 0))) / max(1, len(pts))
        pts.sort(key=lambda p: math.atan2(p.y - c.y, p.x - c.x))
        self.pts = pts
        self.c = c

    def sd(self, q):
        inside = True
        best = 1e9
        n = len(self.pts)
        for i in range(n):
            a, b = self.pts[i], self.pts[(i + 1) % n]
            e = b - a
            nn = V((e.y, -e.x))
            if nn.dot(a - self.c) < 0:
                nn = -nn
            if (q - a).dot(nn) > 0:
                inside = False
            t = max(0.0, min(1.0, (q - a).dot(e) / max(1e-12, e.length_squared)))
            best = min(best, (q - (a + e * t)).length)
        return -best if inside else best


def grip_section(grip, origin, s_axis, d0, u0):
    a = grip.F.col[2].to_3d().normalized()
    uu = grip.F.col[0].to_3d()
    vv = grip.F.col[1].to_3d()
    P = grip.F.col[3].to_3d()
    den = a.dot(s_axis)
    pts = []
    for sp in grip.shape:
        base = P + uu * sp.x + vv * sp.y
        t = (origin - base).dot(s_axis) / den
        rel = base + a * t - origin
        pts.append((rel.dot(d0), rel.dot(u0)))
    return Poly2(pts)


def close_finger(grip, mcp, R0, lens, radius, weights=(1.0, 1.15, 0.8), maxes=(1.55, 1.85, 1.35), step=0.02,
                 start=(0.0, 0.0, 0.0), limit=1.0):
    """Grasp closing: all joints curl together; a joint freezes once its phalanx (or anything distal
    of it) touches the grip, distal joints keep curling - like a real hand closing on a handle."""
    poly = grip_section(grip, V(mcp), R0.col[0], R0.col[1], R0.col[2])

    def pts_of(fl):
        pos = V((0.0, 0.0))
        beta = 0.0
        out = []
        for L, f in zip(lens, fl):
            beta -= f
            d = V((math.cos(beta), math.sin(beta)))
            seg = [pos + d * (L * t) for t in (0.2, 0.45, 0.7, 0.95)]
            out.append(seg)
            pos = pos + d * L
        return out

    def hit(fl):
        segs = pts_of(fl)
        for k, seg in enumerate(segs):
            for q in seg:
                if poly.sd(q) < radius * (0.92 if k == len(segs) - 1 else 1.0):
                    return k
        return -1

    fl = list(start)
    frozen = [False, False, False]
    mx = [m * limit for m in maxes]
    for _ in range(400):
        moved = False
        for j in range(3):
            if frozen[j] or fl[j] >= mx[j]:
                continue
            trial = list(fl)
            trial[j] = min(mx[j], fl[j] + step * weights[j])
            k = hit(trial)
            if k >= 0 and k >= j:
                # this joint's motion makes phalanx k touch: freeze it (and its proximal joints)
                for jj in range(j + 1):
                    frozen[jj] = True
                continue
            fl = trial
            moved = True
        if not moved:
            break
    return fl


def solve_chain(mcp, R_base_fn, lens, target, params0, steps=(0.2, 0.1, 0.05, 0.02, 0.01, 0.005), reg=None, pt=0.5, extra=None):
    """Coordinate descent: params -> (R0, flex list); minimises distance of the point at fraction pt
    along the last phalanx to target, plus regularisation."""
    def cost(pr):
        R0, flex = R_base_fn(pr)
        joints, segs, _ = finger_frames(mcp, R0, lens, flex)
        p = joints[-2] + (joints[-1] - joints[-2]) * pt
        c = (p - target).length_squared * 1e4
        if reg:
            c += reg(pr)
        if extra:
            c += extra(joints, segs)
        return c
    pr = list(params0)
    best = cost(pr)
    for st in steps:
        improved = True
        it = 0
        while improved and it < 60:
            improved = False
            it += 1
            for i in range(len(pr)):
                for sgn in (1, -1):
                    trial = list(pr)
                    trial[i] += sgn * st
                    c = cost(trial)
                    if c < best - 1e-12:
                        best, pr, improved = c, trial, True
    return pr, best


# ---------------------------------------------------------------- cage
def _ring(center, R, w, t, ustretch=1.0):
    s, u = R.col[0], R.col[2]
    hw, ht = w / 2, t / 2 * ustretch
    return [center - s * hw + u * ht, center + s * hw + u * ht, center + s * hw - u * ht, center - s * hw - u * ht]


def _cup(p, cup):
    """Palm cupping: outer columns and knuckles curl toward the palm side (-Z)."""
    if cup == 0:
        return V(p)
    x, y, z = p
    yy = max(0.0, min(1.0, (y + 0.01) / 0.095))
    k = ((x + 0.006) / 0.040) ** 2
    dz = -cup * 0.0085 * k * (0.35 + 0.65 * yy)
    # little-finger side metacarpals flex more (palmar arch)
    if x > 0:
        dz -= cup * 0.010 * (x / 0.04) * yy * yy
    return V((x, y, z + dz))


def build_cage(pose):
    """Returns (bmesh, info). pose: dict with 'cup', 'fingers' {name: (R0, flex)}, 'thumb' (R0, flex)."""
    bm = bmesh.new()
    cup = pose.get("cup", 0.0)
    crease = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    rings = []
    for ys, xs, top, bot in PALM:
        r = [bm.verts.new(_cup((xs[k], ys[k], top[k]), cup)) for k in range(5)]
        r += [bm.verts.new(_cup((xs[k], ys[k], bot[k]), cup)) for k in range(4, -1, -1)]
        rings.append(r)

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
                continue   # thumb port
            mi = 1 if 5 <= k <= 8 else 0
            face((a[k], a[(k + 1) % 10], b[(k + 1) % 10], b[k]), mi)
    r0 = rings[0]
    for k in range(4):   # wrist cap
        face((r0[9 - k], r0[8 - k], r0[k + 1], r0[k]), 0)
    info = {"fingers": {}, "thumb": None}
    knuck = rings[4]

    def connect(ra, rb, mis=(0, 0, 1, 0), crease_bottom=True):
        for i in range(4):
            j = (i + 1) % 4
            face((ra[i], ra[j], rb[j], rb[i]), mis[i])
        if crease_bottom:
            for i in (2, 3):
                e = bm.edges.get((ra[i], rb[i]))
                if e:
                    e[crease] = 0.45

    for fi, (name, mcp, lens, w0, t0) in enumerate(FINGERS):
        R0, flex = pose["fingers"][name]
        mcp_c = _cup(mcp, cup)
        joints, segs, bis = finger_frames(mcp_c, R0, lens, flex)
        port = [knuck[fi], knuck[fi + 1], knuck[9 - (fi + 1)], knuck[9 - fi]]
        specs = []
        Rb, f = bis[0]
        specs.append((joints[0], Rb, w0 * TAPER[0], t0 * TAPER[0], 1.0 / max(0.55, math.cos(f / 2))))
        specs.append((joints[0] + (joints[1] - joints[0]) * 0.5, segs[0], w0 * 0.975, t0 * 0.965, 1.0))
        Rb, f = bis[1]
        specs.append((joints[1], Rb, w0 * TAPER[1], t0 * TAPER[1], 1.0 / max(0.55, math.cos(f / 2))))
        Rb, f = bis[2]
        specs.append((joints[2], Rb, w0 * TAPER[2], t0 * TAPER[2], 1.0 / max(0.55, math.cos(f / 2))))
        specs.append((joints[2] + (joints[3] - joints[2]) * 0.62, segs[2], w0 * TAPER[3], t0 * TAPER[3] * 0.98, 1.0))
        specs.append((joints[2] + (joints[3] - joints[2]) * 0.95, segs[2], w0 * TAPER[3] * 0.70, t0 * TAPER[3] * 0.62, 1.0))
        prev = port
        rr = []
        for k, (c, R, w, t, us) in enumerate(specs):
            ring = [bm.verts.new(p) for p in _ring(c, R, w, t, us)]
            connect(prev, ring, crease_bottom=k > 0)
            prev = ring
            rr.append(ring)
        face(prev, 1)
        info["fingers"][name] = {"joints": joints, "segs": segs, "bis": bis, "rings": specs, "w": w0, "t": t0}
    # thumb
    R0, flex = pose["thumb"]
    joints, segs, bis = finger_frames(THUMB_CMC, R0, THUMB_LENS, flex)
    port = [rings[1][0], rings[2][0], rings[2][9], rings[1][9]]
    specs = []
    specs.append((joints[0] + (joints[1] - joints[0]) * 0.42, segs[0], *THUMB_SIZES[0], 1.0))
    Rb, f = bis[1]
    specs.append((joints[1], Rb, *THUMB_SIZES[1], 1.0 / max(0.55, math.cos(f / 2))))
    Rb, f = bis[2]
    specs.append((joints[2], Rb, *THUMB_SIZES[2], 1.0 / max(0.55, math.cos(f / 2))))
    specs.append((joints[2] + (joints[3] - joints[2]) * 0.6, segs[2], *THUMB_SIZES[3], 1.0))
    specs.append((joints[2] + (joints[3] - joints[2]) * 0.95, segs[2], *THUMB_SIZES[4], 1.0))
    prev = port
    for k, (c, R, w, t, us) in enumerate(specs):
        pts = _ring(c, R, w, t, us)
        if k == 0:
            # rotate the first ring to best match the port corners (no twist)
            best = None
            for sh in range(4):
                cand = pts[sh:] + pts[:sh]
                d = sum((cand[i] - prev[i].co).length for i in range(4))
                if best is None or d < best[0]:
                    best = (d, cand, sh)
            pts = best[1]
            shift = best[2]
        else:
            pts = pts[shift:] + pts[:shift]
        ring = [bm.verts.new(p) for p in pts]
        mis = [0, 0, 0, 0]
        mis[(2 - shift) % 4] = 1
        connect(prev, ring, mis=tuple(mis), crease_bottom=False)
        prev = ring
    face(prev, 1)
    info["thumb"] = {"joints": joints, "segs": segs, "bis": bis}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm, info


def make_pad(bm_target_obj_bvh, name, center, R, ws, ls, h, mi_mat="rubber", ring_n=8, sink=0.0006, pw=3.0):
    """Pillow pad seated on the glove surface (raycast along -u)."""
    s, d, u = R.col[0], R.col[1], R.col[2]
    hit = bm_target_obj_bvh.ray_cast(center + u * 0.04, -u, 0.08)
    if hit[0] is None:
        base = center
    else:
        base = hit[0] - u * sink
    bm = bmesh.new()
    rings = []
    for hz, sc in ((0.0, 1.0), (h * 0.55, 1.0), (h, 0.78)):
        ring = []
        for i in range(ring_n):
            t = 2 * math.pi * (i + 0.5) / ring_n
            c, sn = math.cos(t), math.sin(t)
            x = ws * sc * math.copysign(abs(c) ** (2 / pw), c)
            y = ls * sc * math.copysign(abs(sn) ** (2 / pw), sn)
            ring.append(bm.verts.new(base + s * x + d * y + u * hz))
        rings.append(ring)
    for k in range(2):
        for i in range(ring_n):
            j = (i + 1) % ring_n
            bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    me.materials.append(mat(mi_mat))
    md = o.modifiers.new("s", "SUBSURF")
    md.levels = 1
    apply_mods(o)
    smooth_all(o)
    return o


def build_hand(name, pose, grips=(), mirror=False, margin=0.0005, pads=True):
    """Build the hand mesh object. grips: Grip objects in design space used for conform."""
    bm, info = build_cage(pose)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    me.materials.append(mat("glove"))
    me.materials.append(mat("glove_palm"))
    md = o.modifiers.new("subd", "SUBSURF")
    md.levels = 2
    md.use_creases = True
    apply_mods(o)
    smooth_all(o)
    # soft-tissue conform: push skin out of the virtual grips
    if grips:
        for v in o.data.vertices:
            p = v.co.copy()
            for g in grips:
                p, _ = g.push_out(p, margin)
            v.co = p
        o.data.update()
    parts = [o]
    if pads:
        bm2 = bmesh.new()
        bm2.from_mesh(o.data)
        bvh = BVHTree.FromBMesh(bm2)
        bm2.free()
        for fname, fd in info["fingers"].items():
            c, Rb, w, t, us = fd["rings"][0]
            parts.append(make_pad(bvh, "knuckle_" + fname, c, Rb, w * 0.40, 0.0062, 0.0042))
            c2, R2, w2, t2, _ = fd["rings"][1]
            parts.append(make_pad(bvh, "fpad_" + fname, c2, R2, w2 * 0.33, 0.0068, 0.0028))
        # back-of-hand plate
        Rh = Matrix.Identity(3)
        parts.append(make_pad(bvh, "backplate", _cup(V((-0.006, 0.050, 0.0)), pose.get("cup", 0.0)), Rh, 0.024, 0.017, 0.0030, ring_n=12))
        th = info["thumb"]
        parts.append(make_pad(bvh, "thumbpad", th["joints"][1] + (th["joints"][2] - th["joints"][1]) * 0.45, th["segs"][1], 0.0062, 0.0085, 0.0026))
    from m2lib import join
    o = join(parts, name)
    if mirror:
        o.data.transform(MIRROR_X)
        o.data.flip_normals()
        o.data.update()
    smooth_all(o)
    return o, info
