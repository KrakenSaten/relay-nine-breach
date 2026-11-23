# Relay Nine: BREACH -- M2 enemy robot ("Teslabot", WARDEN-pattern relay security unit).
#
# Headless, deterministic build (no external assets, fixed RNG seed):
#   blender -b --factory-startup -P tools/m2/teslabot.py -- C:/AAA/Breach/staging/teslabot [--no-render] [--fast]
# Writes <out>/teslabot.glb, <out>/teslabot_report.json, <out>/teslabot_m2.blend and <out>/previews/*.png
#
# Blender axes: X right, robot faces +Y, Z up, metres. glTF is exported Y-up with modifiers applied.
# Joint/empty contract is identical to tools/build_models.py:build_teslabot (M1).
# Damage contract: detachable plates are separate objects "armor_<zone>_<n>" (origin at their own centre),
# machinery under them is "internal_<zone>_*", parented to the same joint empty.
import bpy, bmesh, math, os, sys, json, random, time
from mathutils import Vector, Matrix

V = Vector
X, Y, Z = V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FLAGS = {a for a in ARGS if a.startswith("--")}
POSARGS = [a for a in ARGS if not a.startswith("--")]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(POSARGS[0]) if POSARGS else os.path.normpath(os.path.join(HERE, "..", "..", "staging", "teslabot"))
PREV = os.path.join(OUT, "previews")
FAST = "--fast" in FLAGS
NO_RENDER = "--no-render" in FLAGS
RNG = random.Random(9071)
T0 = time.time()

# ------------------------------------------------------------------ materials
MATS = {
    # name: (base linear rgb, metallic, roughness, emission rgb, emission strength, coat)
    "robot_paint": ((0.200, 0.100, 0.035), 0.12, 0.62, None, 0.0, 0.0),  # worn, desaturated safety ochre
    "robot_bone": ((0.26, 0.25, 0.215), 0.05, 0.62, None, 0.0, 0.0),      # off-white panels
    "robot_dark": ((0.032, 0.034, 0.037), 0.85, 0.42, None, 0.0, 0.0),   # gunmetal frame
    "robot_joint": ((0.012, 0.012, 0.013), 0.80, 0.32, None, 0.0, 0.0),  # black anodized actuators
    "steel": ((0.55, 0.55, 0.56), 1.00, 0.22, None, 0.0, 0.0),
    "copper": ((0.70, 0.36, 0.20), 1.00, 0.30, None, 0.0, 0.0),
    "ceramic": ((0.62, 0.59, 0.52), 0.00, 0.25, None, 0.0, 0.6),
    "rubber_cable": ((0.012, 0.012, 0.012), 0.00, 0.72, None, 0.0, 0.0),
    "core_glow": ((0.55, 0.78, 1.00), 0.00, 0.30, (0.50, 0.75, 1.00), 6.0, 0.0),
    "eye_glow": ((0.25, 0.02, 0.005), 0.00, 0.30, (1.00, 0.10, 0.012), 1.8, 0.0),
    "arc_tip": ((0.70, 0.88, 1.00), 0.00, 0.30, (0.50, 0.80, 1.00), 5.0, 0.0),
    "hazard": ((0.42, 0.28, 0.015), 0.05, 0.55, None, 0.0, 0.0),
    "led_amber": ((1.00, 0.50, 0.10), 0.00, 0.40, (1.00, 0.45, 0.06), 4.0, 0.0),
    "glass_optic": ((0.010, 0.013, 0.016), 0.00, 0.04, None, 0.0, 0.0),
}
EMISSIVE = {"core_glow", "eye_glow", "arc_tip", "led_amber"}
SPECULAR = {"robot_paint": 0.3, "robot_bone": 0.3, "rubber_cable": 0.25, "hazard": 0.3}  # matte, chalky-free paint


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    base, metal, rough, em, ems, coat = MATS[name]
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if name in SPECULAR:
        b.inputs["Specular IOR Level"].default_value = SPECULAR[name]
    if coat > 0 and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.06
    if em:
        b.inputs["Emission Color"].default_value = (*em, 1.0)
        b.inputs["Emission Strength"].default_value = ems
    m.diffuse_color = (*base, 1.0)
    m.metallic = metal
    m.roughness = rough
    return m


# ------------------------------------------------------------------ small math helpers
def nrm(v):
    return V(v).normalized()


def basis_from(axis):
    a = nrm(axis)
    ref = Z if abs(a.z) < 0.9 else X
    u = a.cross(ref).normalized()
    v = a.cross(u).normalized()
    return a, u, v


def rotz(v, deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z") @ V(v)


def mx(v, s):
    return V((v[0] * s, v[1], v[2]))


def cpoly(x0, y0, x1, y1, c=(0.0, 0.0, 0.0, 0.0)):
    """Rectangle with per-corner chamfers (bl, br, tr, tl), CCW."""
    lim = 0.49 * min(x1 - x0, y1 - y0)
    bl, br, tr, tl = [min(ci, lim) for ci in c]
    p = []
    p += [(x0, y0 + bl), (x0 + bl, y0)] if bl > 0 else [(x0, y0)]
    p += [(x1 - br, y0), (x1, y0 + br)] if br > 0 else [(x1, y0)]
    p += [(x1, y1 - tr), (x1 - tr, y1)] if tr > 0 else [(x1, y1)]
    p += [(x0 + tl, y1), (x0, y1 - tl)] if tl > 0 else [(x0, y1)]
    return p


def crect(w, h, c=0.0, cx=0.0, cy=0.0):
    return cpoly(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, (c, c, c, c))


def sec(center, ex, ey, pts):
    c, ex, ey = V(center), V(ex), V(ey)
    return [c + ex * x + ey * y for x, y in pts]


def poly_area(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2


def inset(poly, d):
    """Offset a (mostly convex) polygon inward by d."""
    o = 1.0 if poly_area(poly) > 0 else -1.0
    n = len(poly)
    lines = []
    for i in range(n):
        p, q = V(poly[i]), V(poly[(i + 1) % n])
        e = (q - p).normalized()
        nin = V((-e.y, e.x)) * o
        lines.append((p + nin * d, e))
    out = []
    for i in range(n):
        p1, e1 = lines[i - 1]
        p2, e2 = lines[i]
        den = e1.x * e2.y - e1.y * e2.x
        if abs(den) < 1e-9:
            out.append(tuple(p2))
            continue
        t = ((p2.x - p1.x) * e2.y - (p2.y - p1.y) * e2.x) / den
        out.append(tuple(p1 + e1 * t))
    return out


def chips(poly, specs):
    """Cut small irregular notches into plate edges: specs = [(edge_index, t, width, depth)]."""
    poly = list(poly)
    o = 1.0 if poly_area(poly) > 0 else -1.0
    for i, t, w, d in sorted(specs, key=lambda s: -s[0]):
        n = len(poly)
        p, q = V(poly[i]), V(poly[(i + 1) % n])
        e = q - p
        L = e.length
        dd = e / L
        nin = V((-dd.y, dd.x)) * o
        tw = w / L
        a = p + e * (t - tw / 2)
        m1 = p + e * (t - tw * 0.12) + nin * d
        m2 = p + e * (t + tw * 0.22) + nin * d * 0.55
        b = p + e * (t + tw / 2)
        poly = poly[:i + 1] + [tuple(a), tuple(m1), tuple(m2), tuple(b)] + poly[i + 1:]
    return poly


def bend(x, y, z, rs, rt):
    if rs:
        a = x / rs
        r = rs + z
        x, z = r * math.sin(a), r * math.cos(a) - rs
    if rt:
        a = y / rt
        r = rt + z
        y, z = r * math.sin(a), r * math.cos(a) - rt
    return x, y, z


def fold(x, z, folds):
    """Pressed-steel fold: piecewise-linear bend of local x (with thickness offset z).
    folds = [(position, angle_deg)], positive angle bends away from the plate normal (convex).
    A fold at position 0 bends both halves (V / prow shape)."""
    if not folds:
        return x, z
    if abs(x) < 1e-7:
        for pos, a in folds:
            if pos == 0.0:
                return 0.0, z / math.cos(math.radians(a))
    if x >= 0:
        fl = sorted((p, math.radians(a)) for p, a in folds if p >= 0)
        sgn = 1.0
    else:
        fl = sorted(((-p, math.radians(a)) for p, a in folds if p <= 0))
        sgn = -1.0
    ax = abs(x)
    px = pz = ang = cur = 0.0
    for p, a in fl:
        if ax < p - 1e-7:
            break
        px += math.cos(ang) * (p - cur)
        pz -= math.sin(ang) * (p - cur)
        if abs(ax - p) <= 1e-7:
            mid = ang + a / 2
            k = 1.0 / math.cos(a / 2)
            return sgn * (px + math.sin(mid) * z * k), pz + math.cos(mid) * z * k
        cur = p
        ang += a
    rem = ax - cur
    bx = px + math.cos(ang) * rem
    bz = pz - math.sin(ang) * rem
    return sgn * (bx + math.sin(ang) * z), bz + math.cos(ang) * z


class PF:
    """Plate frame: maps plate-local (x, y, w) to world space with optional cylindrical bends (rs, rt)
    or pressed folds along x (fx)."""

    def __init__(self, origin, ex, ey, out, rs=None, rt=None, fx=()):
        ex = nrm(ex)
        ey = V(ey)
        ey = (ey - ex * ey.dot(ex)).normalized()
        ez = ex.cross(ey)
        if ez.dot(V(out)) < 0:
            ez = -ez
        self.o, self.ex, self.ey, self.ez, self.rs, self.rt = V(origin), ex, ey, ez, rs, rt
        self.fx = list(fx)

    def pt(self, x, y, w=0.0):
        if self.fx:
            x, z = fold(x, w, self.fx)
            x, y, z = bend(x, y, z, None, self.rt)
        else:
            x, y, z = bend(x, y, w, self.rs, self.rt)
        return self.o + self.ex * x + self.ey * y + self.ez * z

    def normal(self, x, y):
        return (self.pt(x, y, 0.01) - self.pt(x, y, 0.0)).normalized()

    def tangents(self, x, y):
        d = 0.002
        return ((self.pt(x + d, y) - self.pt(x - d, y)).normalized(),
                (self.pt(x, y + d) - self.pt(x, y - d)).normalized())

    def find(self, target, axes=(0, 2)):
        """Plate-local (x, y) whose surface point matches two world coordinates (default world x, z)."""
        u = v = 0.0
        for _ in range(30):
            p = self.pt(u, v)
            e0, e1 = target[0] - p[axes[0]], target[1] - p[axes[1]]
            if abs(e0) + abs(e1) < 1e-8:
                break
            d = 1e-4
            pu, pv = self.pt(u + d, v), self.pt(u, v + d)
            j00, j01 = (pu[axes[0]] - p[axes[0]]) / d, (pv[axes[0]] - p[axes[0]]) / d
            j10, j11 = (pu[axes[1]] - p[axes[1]]) / d, (pv[axes[1]] - p[axes[1]]) / d
            det = j00 * j11 - j01 * j10
            if abs(det) < 1e-12:
                break
            u += (j11 * e0 - j01 * e1) / det
            v += (-j10 * e0 + j00 * e1) / det
        return u, v


SEG7 = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
        "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}

# ------------------------------------------------------------------ scene registries
REG = []        # (object, parent empty name)
CUTTERS = []    # boolean cutter objects, deleted after modifiers are applied
E, EW = {}, {}  # joint empties, world positions

JOINTS = [
    ("Teslabot", None, (0, 0, 0)),
    ("pelvis", "Teslabot", (0, 0, 1.02)),
    ("torso", "pelvis", (0, 0, 1.12)),
    ("head", "torso", (0, 0.02, 1.78)),
    ("core", "torso", (0, -0.27, 1.5)),
    ("shoulder_R", "torso", (0.36, 0, 1.62)),
    ("elbow_R", "shoulder_R", (0.38, 0, 1.32)),
    ("muzzle", "elbow_R", (0.38, 0.53, 1.32)),
    ("shoulder_L", "torso", (-0.36, 0, 1.62)),
    ("elbow_L", "shoulder_L", (-0.38, 0, 1.32)),
    ("hip_R", "pelvis", (0.15, 0, 0.98)),
    ("knee_R", "hip_R", (0.16, 0, 0.55)),
    ("ankle_R", "knee_R", (0.16, 0, 0.10)),
    ("hip_L", "pelvis", (-0.15, 0, 0.98)),
    ("knee_L", "hip_L", (-0.16, 0, 0.55)),
    ("ankle_L", "knee_L", (-0.16, 0, 0.10)),
]


def recenter(ob):
    me = ob.data
    if not me.vertices:
        return
    cs = [v.co for v in me.vertices]
    mn = V((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mxv = V((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    c = (mn + mxv) / 2
    me.transform(Matrix.Translation(-c))
    ob.location = ob.location + c


# ------------------------------------------------------------------ mesh builder
class Part:
    """Accumulates world-space primitives into one bmesh; done() makes a mesh object with bevel/boolean mods."""

    def __init__(self, name, parent, mat="robot_dark"):
        self.name, self.parent, self.default = name, parent, mat
        self.bm = bmesh.new()
        self.nb = self.bm.faces.layers.int.new("nobev")
        self.mats = []

    def mi(self, m):
        m = m or self.default
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def add(self, verts, faces, mat=None, bevel=True):
        bm = self.bm
        vs = [bm.verts.new(V(v)) for v in verts]
        idx = self.mi(mat)
        flag = 0 if bevel else 1
        for f in faces:
            try:
                face = bm.faces.new([vs[i] for i in f])
            except ValueError:
                continue
            face.material_index = idx
            face[self.nb] = flag
        return self

    def add_bm(self, src, mat=None, bevel=True):
        src.verts.index_update()
        return self.add([v.co.copy() for v in src.verts], [[v.index for v in f.verts] for f in src.faces], mat, bevel)

    # --- primitives
    def loft(self, sections, mat=None, bevel=True, caps=True):
        n = len(sections[0])
        verts = [p for s in sections for p in s]
        faces = []
        for i in range(len(sections) - 1):
            for j in range(n):
                faces.append((i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j))
        if caps:
            faces.append(tuple(reversed(range(n))))
            last = (len(sections) - 1) * n
            faces.append(tuple(range(last, last + n)))
        return self.add(verts, faces, mat, bevel)

    def obox(self, c, ex, ey, ez, size, mat=None, bevel=True):
        c, ex, ey, ez = V(c), nrm(ex), nrm(ey), nrm(ez)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        s0 = [c - ez * hz + ex * x + ey * y for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        s1 = [c + ez * hz + ex * x + ey * y for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        return self.loft([s0, s1], mat, bevel)

    def box(self, c, size, mat=None, bevel=True, rot=(0, 0, 0)):
        R = Matrix.Rotation(math.radians(rot[2]), 3, "Z") @ Matrix.Rotation(math.radians(rot[1]), 3, "Y") @ Matrix.Rotation(math.radians(rot[0]), 3, "X")
        return self.obox(c, R @ X, R @ Y, R @ Z, size, mat, bevel)

    def cyl(self, p0, p1, r0, r1=None, n=16, mat=None, bevel=True, caps=True, phase=0.0):
        r1 = r0 if r1 is None else r1
        a, u, v = basis_from(V(p1) - V(p0))

        def ring(c, r):
            return [V(c) + (u * math.cos(phase + 2 * math.pi * k / n) + v * math.sin(phase + 2 * math.pi * k / n)) * r for k in range(n)]
        return self.loft([ring(p0, r0), ring(p1, r1)], mat, bevel, caps)

    def lathe(self, p0, axis, profile, n=16, mat=None, bevel=True):
        a, u, v = basis_from(axis)
        secs = [[V(p0) + a * d + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * r for k in range(n)] for d, r in profile]
        return self.loft(secs, mat, bevel)

    def tube(self, p0, p1, ro, ri, n=16, mat=None, bevel=True):
        a, u, v = basis_from(V(p1) - V(p0))

        def ring(c, r):
            return [V(c) + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * r for k in range(n)]
        verts = ring(p0, ro) + ring(p1, ro) + ring(p0, ri) + ring(p1, ri)
        faces = []
        for k in range(n):
            j = (k + 1) % n
            faces += [(k, j, n + j, n + k), (2 * n + k, 3 * n + k, 3 * n + j, 2 * n + j),
                      (k, 2 * n + k, 2 * n + j, j), (n + k, n + j, 3 * n + j, 3 * n + k)]
        return self.add(verts, faces, mat, bevel)

    def torus(self, c, axis, R, r, nu=18, nv=6, mat=None, bevel=False):
        a, u, v = basis_from(axis)
        verts = []
        for i in range(nu):
            t = 2 * math.pi * i / nu
            d = u * math.cos(t) + v * math.sin(t)
            for j in range(nv):
                p = 2 * math.pi * j / nv
                verts.append(V(c) + d * (R + r * math.cos(p)) + a * (r * math.sin(p)))
        faces = [(i * nv + j, i * nv + (j + 1) % nv, ((i + 1) % nu) * nv + (j + 1) % nv, ((i + 1) % nu) * nv + j)
                 for i in range(nu) for j in range(nv)]
        return self.add(verts, faces, mat, bevel)

    def dome(self, c, axis, r, h, n=16, rings=3, mat=None, bevel=False):
        a, u, v = basis_from(axis)
        R = (r * r + h * h) / (2 * h)
        tmax = math.asin(min(1.0, r / R))
        secs = []
        for i in range(rings):
            th = tmax * (1 - i / rings)
            rr = R * math.sin(th)
            hh = R * math.cos(th) - (R - h)
            secs.append([V(c) + a * hh + (u * math.cos(2 * math.pi * k / n) + v * math.sin(2 * math.pi * k / n)) * rr for k in range(n)])
        return self.loft(secs, mat, bevel)

    def prism(self, pts, origin, ex, ey, ez, d0, d1, mat=None, bevel=True, scale1=1.0):
        o, ex, ey, ez = V(origin), V(ex), V(ey), V(ez)
        s0 = [o + ex * x + ey * y + ez * d0 for x, y in pts]
        s1 = [o + (ex * x + ey * y) * scale1 + ez * d1 for x, y in pts]
        return self.loft([s0, s1], mat, bevel)

    def plate(self, F, outline, th, mat=None, cuts=(3, 3), lift=0.0, dents=(), bevel=True):
        tmp = bmesh.new()
        n = len(outline)
        top = [tmp.verts.new((x, y, lift)) for x, y in outline]
        bot = [tmp.verts.new((x, y, lift - th)) for x, y in outline]
        tmp.faces.new(top)
        tmp.faces.new(bot[::-1])
        for i in range(n):
            j = (i + 1) % n
            tmp.faces.new((top[i], top[j], bot[j], bot[i]))
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        planes = []
        for axis, cnt, lo, hi in ((0, cuts[0], min(xs), max(xs)), (1, cuts[1], min(ys), max(ys))):
            for k in range(1, cnt + 1):
                planes.append((axis, lo + (hi - lo) * k / (cnt + 1)))
        for dx, dy, r, d in dents:
            planes += [(0, dx - r * 0.5), (0, dx + r * 0.5), (1, dy - r * 0.5), (1, dy + r * 0.5)]
        for pos, a in F.fx:
            if min(xs) < pos < max(xs):
                planes.append((0, pos))
        for axis, cpos in planes:
            co = [0.0, 0.0, 0.0]
            no = [0.0, 0.0, 0.0]
            co[axis] = cpos
            no[axis] = 1.0
            bmesh.ops.bisect_plane(tmp, geom=tmp.verts[:] + tmp.edges[:] + tmp.faces[:], dist=1e-6, plane_co=co, plane_no=no)
        ng = [f for f in tmp.faces if len(f.verts) > 4]
        if ng:
            bmesh.ops.triangulate(tmp, faces=ng)
        for vt in tmp.verts:
            x, y, z = vt.co
            for dx, dy, r, d in dents:
                z -= d * math.exp(-((x - dx) ** 2 + (y - dy) ** 2) / (r * r))
            vt.co = F.pt(x, y, z)
        self.add_bm(tmp, mat, bevel)
        tmp.free()
        return self

    # --- details
    def bolt(self, c, n, r=0.0065, h=0.005, mat="robot_joint"):
        n, c = nrm(n), V(c)
        a, u, v = basis_from(n)
        ph = RNG.random()
        secs = [[c + n * d + (u * math.cos(ph + k * math.pi / 3) + v * math.sin(ph + k * math.pi / 3)) * rr for k in range(6)]
                for d, rr in ((-0.002, r), (h * 0.55, r), (h, r * 0.7))]
        return self.loft(secs, mat, bevel=False)

    def bolts(self, F, pts, w, r=0.0065, mat="robot_joint"):
        for x, y in pts:
            self.bolt(F.pt(x, y, w), F.normal(x, y), r, mat=mat)
        return self

    def bead(self, pts, up, r=0.0032, step=0.018, mat="robot_dark"):
        """Weld seam: rippled flattened bead along a polyline."""
        pts = [V(p) for p in pts]
        up = nrm(up)
        smp = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            k = max(2, int((b - a).length / (step * 0.5)))
            smp += [a + (b - a) * (j / k) for j in range(k)]
        smp.append(pts[-1])
        secs = []
        for i, p in enumerate(smp):
            t = (smp[min(i + 1, len(smp) - 1)] - smp[max(i - 1, 0)]).normalized()
            side = t.cross(up).normalized()
            u2 = side.cross(t).normalized()
            rr = r * (1.0 if i % 2 == 0 else 0.78)
            if i in (0, len(smp) - 1):
                rr *= 0.5
            secs.append([p + side * (math.cos(2 * math.pi * k / 5) * rr) + u2 * (math.sin(2 * math.pi * k / 5) * rr * 0.6) for k in range(5)])
        return self.loft(secs, mat, bevel=False)

    def panel(self, F, outline, w, mat="robot_dark", th=0.0015, cuts=(0, 0)):
        return self.plate(F, outline, th, mat, cuts=cuts, lift=w + th, bevel=False)

    def stencil(self, F, text, x, y, h, w, mat="robot_bone", right=(1.0, 0.0), upref=Z):
        rx, ry = right
        L = math.hypot(rx, ry)
        rx, ry = rx / L, ry / L
        ux, uy = -ry, rx
        tx, ty = F.tangents(x, y)
        n = F.normal(x, y)
        Rw, Uw = tx * rx + ty * ry, tx * ux + ty * uy
        if Uw.dot(V(upref)) < 0:
            ux, uy, Uw = -ux, -uy, -Uw
        if Rw.cross(Uw).dot(n) < 0:
            rx, ry = -rx, -ry
        cw, gap, th, g = h * 0.56, h * 0.30, h * 0.16, h * 0.07
        total = (cw + gap) * len(text) - gap
        for ci, ch in enumerate(text):
            x0 = -total / 2 + ci * (cw + gap)
            segs = {"a": (x0 + g, h - th, x0 + cw - g, h), "d": (x0 + g, 0, x0 + cw - g, th),
                    "g": (x0 + g, (h - th) / 2, x0 + cw - g, (h + th) / 2),
                    "f": (x0, h / 2 + g * 0.5, x0 + th, h - g), "e": (x0, g, x0 + th, h / 2 - g * 0.5),
                    "b": (x0 + cw - th, h / 2 + g * 0.5, x0 + cw, h - g), "c": (x0 + cw - th, g, x0 + cw, h / 2 - g * 0.5)}
            for sname in SEG7.get(ch, ""):
                a0, b0, a1, b1 = segs[sname]
                b0, b1 = b0 - h / 2, b1 - h / 2
                ol = [(x + rx * p + ux * q, y + ry * p + uy * q) for p, q in ((a0, b0), (a1, b0), (a1, b1), (a0, b1))]
                self.plate(F, ol, 0.0012, mat, cuts=(0, 0), lift=w + 0.0012, bevel=False)
        return self

    def hazard(self, F, x0, x1, y0, y1, w, along="x"):
        """Yellow/black chevron strip conforming to plate F (local rect)."""
        self.plate(F, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 0.0012, "robot_joint",
                   cuts=(4, 0) if along == "x" else (0, 4), lift=w + 0.0012, bevel=False)
        length, width = (x1 - x0, y1 - y0) if along == "x" else (y1 - y0, x1 - x0)
        n = max(2, int(round(length / (width * 1.3))))
        pitch = length / n
        slant = width * 0.7
        for i in range(-1, n + 1):
            a = i * pitch
            quad = [(a, 0.0), (a + pitch * 0.5, 0.0), (a + pitch * 0.5 + slant, width), (a + slant, width)]
            q2 = []
            for p, q in quad:
                p = min(max(p, 0.0), length)
                if not q2 or abs(q2[-1][0] - p) > 1e-5 or abs(q2[-1][1] - q) > 1e-5:
                    q2.append((p, q))
            if len(q2) > 2 and abs(q2[0][0] - q2[-1][0]) < 1e-5 and abs(q2[0][1] - q2[-1][1]) < 1e-5:
                q2.pop()
            if len(q2) < 3 or abs(poly_area(q2)) < 1e-6:
                continue
            loc = [(x0 + p, y0 + q) if along == "x" else (x0 + q, y0 + p) for p, q in q2]
            self.plate(F, loc, 0.0012, "hazard", cuts=(0, 0), lift=w + 0.0024, bevel=False)
        return self

    # --- finish
    def _mesh(self, angle):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.normal_update()
        bw = bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")
        lim = math.radians(angle)
        for e in bm.edges:
            lf = e.link_faces
            ok = len(lf) == 2 and lf[0][self.nb] == 0 and lf[1][self.nb] == 0 and e.calc_face_angle(0.0) > lim
            e[bw] = 1.0 if ok else 0.0
        bm.faces.layers.int.remove(self.nb)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(get_mat(m))
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        recenter(ob)
        return ob

    def done(self, bevel=0.004, segs=2, angle=30.0, cutters=()):
        assert self.name not in bpy.data.objects, "duplicate object name " + self.name
        if self.name.startswith("internal_"):
            bevel = 0  # only seen once a plate is shot off; keep them cheap
        ob = self._mesh(angle)
        if bevel > 0:
            md = ob.modifiers.new("bevel", "BEVEL")
            md.limit_method = "WEIGHT"
            md.width = bevel
            md.segments = segs
            md.use_clamp_overlap = True
            md.harden_normals = False
            md.miter_outer = "MITER_ARC"
        for c in cutters:
            md = ob.modifiers.new("cut", "BOOLEAN")
            md.operation = "DIFFERENCE"
            md.solver = "EXACT"
            md.use_self = True
            md.object = c
        REG.append((ob, self.parent))
        return ob

    def done_cutter(self):
        ob = self._mesh(0)
        ob.hide_render = True
        ob.hide_viewport = True
        CUTTERS.append(ob)
        return ob


def curve_tube(name, parent, pts, r, mat="rubber_cable", res_u=4, bev_res=1, poly=False):
    """Cable: NURBS (or poly) curve with round bevel, converted to a mesh object."""
    assert name not in bpy.data.objects, "duplicate object name " + name
    cu = bpy.data.curves.new(name + "_cu", "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = res_u
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = r
    cu.bevel_resolution = bev_res
    cu.use_fill_caps = True
    cu.twist_mode = "MINIMUM"
    sp = cu.splines.new("POLY" if poly else "NURBS")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1.0)
    if not poly:
        sp.order_u = min(4, len(pts))
        sp.use_endpoint_u = True
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.name = name
    me.materials.clear()
    me.materials.append(get_mat(mat))
    for p in me.polygons:
        p.material_index = 0
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    recenter(ob)
    REG.append((ob, parent))
    return ob


def path_frames(pts):
    n = len(pts)
    T = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    N0 = T[0].cross(Z)
    if N0.length < 1e-4:
        N0 = T[0].cross(X)
    N = [N0.normalized()]
    for i in range(1, n):
        q = T[i - 1].rotation_difference(T[i])
        N.append((q @ N[-1]).normalized())
    B = [T[i].cross(N[i]) for i in range(n)]
    return N, B


def cable_bundle(name, parent, ctrl, radii, spread, phase=0.0, mat="rubber_cable", mats=None):
    ctrl = [V(p) for p in ctrl]
    N, B = path_frames(ctrl)
    k = len(radii)
    obs = []
    for ci, r in enumerate(radii):
        ang = phase + 2 * math.pi * ci / k
        pts = [p + (N[i] * math.cos(ang) + B[i] * math.sin(ang)) * (spread if k > 1 else 0.0) for i, p in enumerate(ctrl)]
        obs.append(curve_tube(f"{name}_{ci + 1}", parent, pts, r, mats[ci] if mats else mat))
    return obs


# ------------------------------------------------------------------ joints
def build_empties():
    for name, parent, loc in JOINTS:
        o = bpy.data.objects.new(name, None)
        o.empty_display_size = 0.05
        o.empty_display_type = "PLAIN_AXES"
        bpy.context.scene.collection.objects.link(o)
        EW[name] = V(loc)
        if parent:
            o.parent = E[parent]
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.location = V(loc) - EW[parent]
        else:
            o.location = V(loc)
        E[name] = o
    bpy.context.view_layer.update()


# =================================================================== BODY
def build_pelvis():
    p = Part("pelvis_frame", "pelvis", "robot_dark")
    p.loft([sec((0, -0.01, 0.86), X, Y, crect(0.11, 0.12, 0.03)),
            sec((0, 0.0, 0.95), X, Y, crect(0.19, 0.22, 0.05)),
            sec((0, 0.0, 1.05), X, Y, crect(0.22, 0.25, 0.06)),
            sec((0, -0.01, 1.10), X, Y, crect(0.20, 0.21, 0.05))])
    p.loft([sec((x, -0.005, 1.082), Y, Z, crect(0.15, 0.05, 0.015)) for x in (-0.282, 0.282)])
    arc = [(0.07 * math.cos(math.radians(a)), 0.98 + 0.07 * math.sin(math.radians(a))) for a in range(0, -181, -30)]
    yoke = [(-0.07, 1.10), (0.07, 1.10)] + arc
    for s in (1, -1):
        p.prism(yoke, (s * 0.262, 0, 0), Y, Z, X, -0.011, 0.011)
        p.bead([(s * 0.12, 0.07, 1.058), (s * 0.12, -0.08, 1.058)], Z)
    p.bead([(-0.10, 0.126, 1.03), (0.10, 0.126, 1.03)], Y)
    p.done(0.006, 1)

    g = Part("pelvis_guard", "pelvis", "robot_paint")
    F = PF((0, 0.145, 0.972), X, (0, -0.25, 1), Y, fx=[(0.0, 22)])
    ol = [(-0.082, 0.082), (0.082, 0.082), (0.094, 0.0), (0.048, -0.085), (-0.048, -0.085), (-0.094, 0.0)]
    g.plate(F, chips(ol, [(2, 0.5, 0.02, 0.006)]), 0.024, cuts=(0, 1))
    g.plate(F, inset(ol, 0.022), 0.01, "robot_bone", cuts=(0, 1), lift=0.01)
    g.bolts(F, [(-0.058, 0.058), (0.058, 0.058)], 0.01)
    F2 = PF((0, -0.14, 0.99), X, (0, 0.2, 1), -Y, fx=[(0.05, 30), (-0.05, 30)])
    g.plate(F2, crect(0.18, 0.13, 0.035), 0.022, "robot_dark", cuts=(0, 1))
    g.bolts(F2, [(-0.035, 0.045), (0.035, 0.045), (-0.035, -0.045), (0.035, -0.045)], 0.0)
    for s in (1, -1):  # hip tassets
        Ft = PF((s * 0.318, 0.0, 0.998), Y, (s * 0.28, 0, 1), (s, 0, 0), fx=[(0.055, 34), (-0.055, 34)])
        olt = chips(cpoly(-0.115, -0.088, 0.115, 0.07, (0.035, 0.035, 0.02, 0.02)), [(1, 0.5, 0.02, 0.006)])
        g.plate(Ft, olt, 0.022, cuts=(0, 1))
        g.bolts(Ft, [(-0.03, 0.045), (0.03, 0.045)], 0.0, r=0.0055)
    g.done(0.004, 1)

    w = Part("waist_bearing", "pelvis", "robot_joint")
    w.cyl((0, 0, 1.10), (0, 0, 1.135), 0.125, n=22)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        w.bolt((0.105 * math.cos(a), 0.105 * math.sin(a), 1.135), Z, 0.006, mat="robot_dark")
    w.done(0.003, 1)


def build_waist():
    w = Part("waist_turntable", "torso", "robot_dark")
    w.cyl((0, 0, 1.135), (0, 0, 1.165), 0.115, n=22)
    w.cyl((0, 0, 1.165), (0, 0, 1.18), 0.092, 0.082, n=22, mat="robot_joint")
    for i in range(4):
        w.box((0, -0.055, 1.198 + i * 0.026), (0.10 - 0.006 * i, 0.085, 0.017))
    w.cyl((0, -0.01, 1.17), (0, -0.01, 1.29), 0.026, n=14, mat="steel")
    w.cyl((-0.072, 0.012, 1.226), (0.072, 0.012, 1.226), 0.04, n=14, mat="robot_joint")
    for sx in (-1, 1):
        w.cyl((sx * 0.072, 0.012, 1.226), (sx * 0.082, 0.012, 1.226), 0.03, n=14)
    w.done(0.003, 1)

    a = Part("waist_actuators", "torso", "robot_joint")
    for sx in (1, -1):
        for sy in (1, -1):
            b = V((sx * 0.085, sy * 0.07, 1.175))
            t = V((sx * 0.135, sy * 0.098, 1.31))
            d = t - b
            a.cyl(b, b + d * 0.58, 0.02, n=10)
            a.cyl(b + d * 0.56, b + d * 0.6, 0.0235, n=10, mat="robot_dark")
            a.cyl(b + d * 0.45, t, 0.0105, n=8, mat="steel")
            a.cyl(b - X * 0.018, b + X * 0.018, 0.014, n=8, mat="robot_dark")
            a.cyl(t - X * 0.016, t + X * 0.016, 0.013, n=8, mat="robot_dark")
    a.done(0)

    for i, x in enumerate((-0.03, 0.0, 0.03)):
        led = Part(f"led_waist_{i + 1}", "torso", "led_amber")
        led.box((x, 0.1155, 1.150), (0.014, 0.004, 0.008), bevel=False)
        led.done(0)


def pec_frame(s):
    ex = V((s * math.cos(math.radians(16)), -math.sin(math.radians(16)), 0))
    ey = V((0, -math.sin(math.radians(10)), math.cos(math.radians(10))))
    return PF((s * 0.15, 0.228, 1.59), ex, ey, Y, rt=0.9, fx=[(0.085, 34)])


def build_chest():
    f = Part("chest_frame", "torso", "robot_dark")
    f.loft([sec((0, -0.01, 1.265), X, Y, crect(0.28, 0.22, 0.05)),
            sec((0, 0.0, 1.36), X, Y, crect(0.46, 0.32, 0.07)),
            sec((0, 0.0, 1.56), X, Y, crect(0.58, 0.36, 0.08)),
            sec((0, -0.025, 1.70), X, Y, crect(0.55, 0.33, 0.08)),
            sec((0, -0.05, 1.765), X, Y, crect(0.40, 0.24, 0.06))])
    f.cyl((0, 0.02, 1.75), (0, 0.02, 1.772), 0.072, n=18, mat="robot_joint")
    for s in (1, -1):
        f.bead([(s * 0.288, -0.10, 1.585), (s * 0.29, 0.0, 1.585), (s * 0.288, 0.10, 1.585)], (s, 0, 0))
    f.bead([(-0.2, -0.183, 1.40), (0.2, -0.183, 1.40)], -Y)
    f.done(0.007, 1)

    s_ = Part("shoulder_sockets", "torso", "robot_joint")
    for s in (1, -1):
        s_.tube((s * 0.262, 0, 1.62), (s * 0.305, 0, 1.62), 0.098, 0.05, n=18)
        for k in range(6):
            a = 2 * math.pi * k / 6 + 0.3
            s_.bolt((s * 0.305, 0.076 * math.cos(a), 1.62 + 0.076 * math.sin(a)), (s, 0, 0), 0.006, mat="robot_dark")
    s_.done(0.003, 1)

    # pectoral plates (armor_torso_1 = right, 2 = left): pressed, folded back at the flank
    pec_ol = [(-0.095, -0.115), (-0.06, -0.15), (0.0, -0.15), (0.15, -0.035), (0.15, 0.09), (0.10, 0.135), (-0.095, 0.135)]
    for s, idx in ((1, 1), (-1, 2)):
        F = pec_frame(s)
        pl = Part(f"armor_torso_{idx}", "torso", "robot_paint")
        ol = chips(pec_ol, [(3, 0.4, 0.024, 0.007), (5, 0.6, 0.02, 0.006)] if s > 0 else [(2, 0.3, 0.022, 0.007), (4, 0.5, 0.02, 0.006)])
        pl.plate(F, ol, 0.03, cuts=(2, 3), dents=[(0.03, 0.03, 0.035, 0.006)] if s > 0 else [(-0.02, -0.07, 0.03, 0.005)])
        band = [(-0.095, 0.06), (0.15, 0.06), (0.15, 0.09), (0.10, 0.135), (-0.095, 0.135)]
        pl.plate(F, band, 0.013, cuts=(2, 1), lift=0.013)
        pl.bolts(F, [(-0.075, 0.097), (0.0, 0.097), (0.075, 0.097)], 0.013)
        pl.bolts(F, [(0.125, -0.02), (-0.07, -0.125)], 0.0)
        if s > 0:
            pl.panel(F, cpoly(-0.06, -0.02, 0.0, 0.02, (0.004,) * 4), 0.0, "robot_bone", 0.0015)
            pl.stencil(F, "9", -0.03, 0.0, 0.026, 0.0015, "robot_dark")
        pl.done(0.004, 1)
        it = Part(f"internal_torso_cells_{'R' if s > 0 else 'L'}", "torso", "robot_joint")
        for z in (1.50, 1.565, 1.63, 1.69):
            it.cyl((s * 0.075, 0.168, z), (s * 0.21, 0.168, z), 0.021, n=10)
            it.cyl((s * 0.21, 0.168, z), (s * 0.22, 0.168, z), 0.013, n=8, mat="copper")
            it.cyl((s * 0.065, 0.168, z), (s * 0.075, 0.168, z), 0.013, n=8, mat="copper")
        it.box((s * 0.14, 0.188, 1.595), (0.022, 0.012, 0.24), "robot_dark")
        it.box((s * 0.215, 0.17, 1.595), (0.012, 0.018, 0.22), "copper")
        it.cyl((s * 0.10, 0.19, 1.47), (s * 0.18, 0.19, 1.72), 0.007, n=8, mat="rubber_cable")
        it.done(0.002, 1)

    # sternum keel (armor_torso_3)
    k = Part("armor_torso_3", "torso", "robot_dark")
    nf = V((0, math.cos(math.radians(10)), math.sin(math.radians(10))))
    keel = [(-0.05, -0.016), (0.05, -0.016), (0.044, 0.012), (0.0, 0.032), (-0.044, 0.012)]
    secs = []
    for z, sc in ((1.40, 0.75), (1.47, 1.0), (1.64, 1.0), (1.72, 0.7)):
        y = 0.228 - (z - 1.59) * 0.176
        secs.append(sec((0, y, z), X, nf, [(px * sc, py) for px, py in keel]))
    k.loft(secs)
    for z in (1.48, 1.57, 1.66):
        y = 0.228 - (z - 1.59) * 0.176
        k.bolt(V((0, y, z)) + nf * 0.032, nf, 0.0055)
    k.done(0.004, 1)
    m = Part("internal_torso_manifold", "torso", "robot_joint")
    for x in (-0.03, 0.0, 0.03):
        m.cyl((x, 0.19, 1.42), (x, 0.17, 1.72), 0.009, n=8, mat="copper" if x == 0 else "steel")
    m.box((0, 0.185, 1.57), (0.09, 0.02, 0.05), "robot_dark")
    m.done(0.0015, 1)

    # abdomen lames (armor_torso_4)
    ab = Part("armor_torso_4", "torso", "robot_paint")
    Fa = PF((0, 0.186, 1.395), X, (0, 0.1, 1), Y, fx=[(0.10, 30), (-0.10, 30)])
    ola = chips(cpoly(-0.165, -0.04, 0.165, 0.04, (0.04, 0.04, 0.015, 0.015)), [(0, 0.3, 0.02, 0.006)])
    ab.plate(Fa, ola, 0.022, cuts=(0, 1))
    Fb = PF((0, 0.152, 1.312), X, (0, 0.63, 1), Y, fx=[(0.08, 30), (-0.08, 30)])
    ab.plate(Fb, cpoly(-0.13, -0.035, 0.13, 0.035, (0.035, 0.035, 0.012, 0.012)), 0.02, cuts=(0, 1))
    ab.bolts(Fa, [(-0.13, 0.0), (0.13, 0.0)], 0.0)
    ab.bolts(Fb, [(-0.10, 0.0), (0.10, 0.0)], 0.0)
    ab.done(0.004, 1)
    ia = Part("internal_torso_abdomen", "torso", "robot_joint")
    for x in (-0.09, -0.03, 0.03, 0.09):
        ia.cyl((x, 0.135, 1.29), (x * 1.15, 0.162, 1.43), 0.009, n=8, mat="rubber_cable")
    ia.cyl((-0.15, 0.158, 1.37), (0.15, 0.158, 1.37), 0.012, n=10, mat="steel")
    ia.box((0, 0.15, 1.33), (0.10, 0.03, 0.05), "robot_dark")
    ia.done(0.0015, 1)

    # side plates (armor_torso_5 = right, 6 = left) + radiators below
    for s, idx in ((1, 5), (-1, 6)):
        F = PF((s * 0.284, -0.01, 1.462), Y, (s * 0.3, 0, 1), (s, 0, 0), fx=[(0.07, 30), (-0.08, 30)])
        sp = Part(f"armor_torso_{idx}", "torso", "robot_dark")
        ol = chips(cpoly(-0.135, -0.085, 0.125, 0.085, (0.04, 0.03, 0.03, 0.04)), [(4, 0.5, 0.02, 0.006)])
        sp.plate(F, ol, 0.022, cuts=(0, 1))
        for j in range(4):
            sp.panel(F, cpoly(-0.06, -0.045 + j * 0.024, 0.05, -0.035 + j * 0.024, (0.004,) * 4), 0.0, "robot_joint", 0.002)
        sp.bolts(F, [(-0.10, 0.06), (0.09, 0.06), (-0.10, -0.06), (0.09, -0.06)], 0.0)
        sp.done(0.004, 1)
        r = Part(f"internal_torso_radiator_{'R' if s > 0 else 'L'}", "torso", "robot_dark")
        for j in range(9):
            r.box((s * 0.262, -0.01, 1.39 + j * 0.017), (0.03, 0.20, 0.004), bevel=False)
        r.cyl((s * 0.275, -0.12, 1.38), (s * 0.275, -0.12, 1.54), 0.008, n=8, mat="copper")
        r.cyl((s * 0.275, 0.10, 1.38), (s * 0.275, 0.10, 1.54), 0.008, n=8, mat="copper")
        r.done(0)

    # yoke (trapezius armour) + rear collar: the head sits low between them
    y = Part("torso_yoke", "torso", "robot_paint")
    for s in (1, -1):
        F = PF((s * 0.20, -0.06, 1.818), (s, 0, -0.40), Y, Z, fx=[(-0.04, -14)])
        ol = cpoly(-0.085, -0.14, 0.085, 0.10, (0.03, 0.02, 0.02, 0.05))
        y.plate(F, ol, 0.03, cuts=(0, 1))
        y.bolts(F, [(-0.06, -0.11), (-0.06, 0.07), (0.06, -0.11), (0.06, 0.07)], 0.0)
    Fc = PF((0, -0.142, 1.80), X, (0, -0.3, 1), -Y, fx=[(0.07, 32), (-0.07, 32)])
    y.plate(Fc, cpoly(-0.13, -0.07, 0.13, 0.075, (0.02, 0.02, 0.04, 0.04)), 0.026, "robot_dark", cuts=(0, 1))
    y.bolts(Fc, [(-0.05, 0.05), (0.05, 0.05)], 0.0)
    y.done(0.005, 1)

    # upper-back heat sinks
    hs = Part("torso_heatsinks", "torso", "robot_dark")
    for s in (1, -1):
        hs.box((s * 0.24, -0.198, 1.565), (0.09, 0.02, 0.30))
        for j in range(12):
            hs.box((s * 0.24, -0.232, 1.43 + j * 0.0245), (0.084, 0.05, 0.0045), bevel=False)
        hs.cyl((s * 0.285, -0.215, 1.41), (s * 0.285, -0.215, 1.72), 0.007, n=8, mat="copper")
    hs.done(0.003, 1)


def build_core():
    cp = "core"
    m = Part("core_mount", cp, "robot_dark")
    m.prism(crect(0.32, 0.48, 0.05), (0, 0, 1.515), X, Z, Y, -0.245, -0.17)
    m.bead([(0.163, -0.176, 1.42), (0.163, -0.176, 1.62)], (1, -1, 0))
    m.prism(crect(0.31, 0.15, 0.035, 0, -0.315), (0, 0, 0), X, Y, Z, 1.665, 1.70)
    m.prism(crect(0.31, 0.15, 0.035, 0, -0.315), (0, 0, 0), X, Y, Z, 1.30, 1.335)
    for x in (-0.14, 0.14):
        for yy in (-0.385, -0.25):
            m.cyl((x, yy, 1.335), (x, yy, 1.665), 0.0085, n=8, mat="robot_joint")
    for z in (1.43, 1.57):
        m.cyl((-0.14, -0.392, z), (0.14, -0.392, z), 0.0055, n=8, mat="robot_joint")
    m.done(0.004, 1)

    # copper coil columns on ceramic formers with ribbed insulator stacks
    for s, lab in ((1, "R"), (-1, "L")):
        c = V((s * 0.085, -0.315, 0))
        pts = []
        turns, per = 11, 8
        for i in range(turns * per + 1):
            t = i / per
            a = 2 * math.pi * t * s
            pts.append((c.x + 0.035 * math.cos(a), c.y + 0.035 * math.sin(a), 1.374 + 0.252 * i / (turns * per)))
        curve_tube(f"core_coil_{lab}", cp, pts, 0.006, "copper", res_u=1, poly=True)
        ins = Part(f"core_insulators_{lab}", cp, "ceramic")
        ins.cyl((c.x, c.y, 1.36), (c.x, c.y, 1.64), 0.024, n=10)
        rib = [(0.0, 0.03), (0.006, 0.03), (0.007, 0.040), (0.012, 0.040), (0.013, 0.031), (0.019, 0.031), (0.02, 0.038), (0.025, 0.038), (0.026, 0.028), (0.032, 0.028)]
        ins.lathe((c.x, c.y, 1.335), Z, rib, n=12)
        ins.lathe((c.x, c.y, 1.665), -Z, rib, n=12)
        ins.done(0.0)
    g = Part("core_glow", cp, "core_glow")
    g.cyl((0, -0.315, 1.372), (0, -0.315, 1.628), 0.032, n=16, bevel=False)
    g.done(0)
    el = Part("core_electrodes", cp, "copper")
    for z0, z1 in ((1.335, 1.372), (1.628, 1.665)):
        el.cyl((0, -0.315, z0), (0, -0.315, z1), 0.042, n=16)
        el.tube((0, -0.315, (z0 + z1) / 2 - 0.006), (0, -0.315, (z0 + z1) / 2 + 0.006), 0.05, 0.03, n=16, mat="ceramic")
    for s in (1, -1):
        el.box((s * 0.045, -0.315, 1.652), (0.07, 0.016, 0.006))
        el.box((s * 0.045, -0.315, 1.348), (0.07, 0.016, 0.006))
    el.done(0)
    for i, x in enumerate((-0.10, 0.10)):
        led = Part(f"led_core_{i + 1}", cp, "led_amber")
        led.box((x, -0.392, 1.318), (0.016, 0.004, 0.008), bevel=False)
        led.done(0)

    # armoured side shrouds (armor_core_1 = right, 2 = left); core stays exposed from behind
    for s, idx in ((1, 1), (-1, 2)):
        F = PF((s * 0.174, -0.30, 1.50), Y, Z, (s, 0, 0), fx=[(-0.045, 34), (-0.09, 30), (0.06, 30)])
        sh = Part(f"armor_core_{idx}", cp, "robot_paint")
        ol = cpoly(-0.12, -0.205, 0.075, 0.205, (0.10, 0.02, 0.02, 0.06))
        ol = chips(ol, [(1, 0.6, 0.02, 0.006), (5, 0.4, 0.02, 0.006)])
        sh.plate(F, ol, 0.022, cuts=(0, 2))
        sh.hazard(F, -0.04, -0.015, -0.17, 0.17, 0.0, along="y")
        for j in range(3):
            sh.panel(F, cpoly(-0.005, 0.07 + j * 0.026, 0.05, 0.082 + j * 0.026, (0.004,) * 4), 0.0, "robot_joint", 0.002)
        sh.bolts(F, [(0.04, 0.18), (0.04, -0.18), (-0.03, 0.18), (-0.03, -0.18), (0.04, 0.0)], 0.0)
        sh.done(0.004, 1)
        cb = Part(f"internal_core_capbank_{'R' if s > 0 else 'L'}", cp, "robot_dark")
        for yy in (-0.37, -0.32, -0.27):
            cb.cyl((s * 0.143, yy, 1.345), (s * 0.143, yy, 1.62), 0.02, n=10)
            cb.cyl((s * 0.143, yy, 1.62), (s * 0.143, yy, 1.635), 0.012, n=8, mat="copper")
        cb.box((s * 0.143, -0.32, 1.64), (0.014, 0.12, 0.006), "copper")
        cb.done(0.002, 1)

    # top hood (armor_core_3) between ceramic bushings
    F = PF((0, -0.31, 1.722), X, (0, 1, 0.25), Z, fx=[(0.035, 30), (-0.035, 30)])
    hd = Part("armor_core_3", cp, "robot_paint")
    hd.plate(F, chips(crect(0.15, 0.19, 0.035), [(2, 0.5, 0.02, 0.005)]), 0.024, cuts=(0, 1))
    hd.stencil(F, "9", 0.0, -0.02, 0.05, 0.0, "robot_bone", right=(1, 0), upref=Y)
    hd.bolts(F, [(-0.05, 0.075), (0.05, 0.075), (-0.05, -0.075), (0.05, -0.075)], 0.0)
    hd.done(0.004, 1)
    tb = Part("internal_core_terminal", cp, "copper")
    tb.box((0, -0.31, 1.705), (0.10, 0.12, 0.012), "robot_joint")
    for x in (-0.03, 0.0, 0.03):
        tb.cyl((x, -0.36, 1.71), (x, -0.26, 1.71), 0.006, n=8)
    tb.done(0.0015, 1)

    # bottom skirt (armor_core_4)
    F = PF((0, -0.33, 1.282), X, (0, -1, -0.5), (0, -0.5, -1), fx=[(0.09, 30), (-0.09, 30)])
    bs = Part("armor_core_4", cp, "robot_paint")
    bs.plate(F, chips(crect(0.30, 0.12, 0.035), [(1, 0.5, 0.025, 0.007)]), 0.022, cuts=(0, 1))
    bs.hazard(F, -0.085, 0.085, 0.035, 0.05, 0.0)
    bs.bolts(F, [(-0.06, -0.03), (0.06, -0.03)], 0.0)
    bs.done(0.004, 1)
    jb = Part("internal_core_junction", cp, "robot_joint")
    jb.box((0, -0.27, 1.285), (0.16, 0.06, 0.03), "robot_dark")
    for x in (-0.05, 0.0, 0.05):
        jb.cyl((x, -0.30, 1.285), (x * 1.4, -0.36, 1.30), 0.008, n=8, mat="rubber_cable")
    jb.done(0.0015, 1)

    # ceramic HV bushings on top of the capacitor stack
    for s, lab in ((1, "R"), (-1, "L")):
        b = Part(f"core_bushing_{lab}", cp, "ceramic")
        base = V((s * 0.115, -0.30, 1.70))
        ax = V((s * 0.22, -0.20, 1.0)).normalized()
        prof = [(0.0, 0.03), (0.012, 0.03)]
        d = 0.012
        for i in range(6):
            prof += [(d + 0.002, 0.033), (d + 0.010, 0.033), (d + 0.012, 0.018), (d + 0.026, 0.018)]
            d += 0.026
        prof += [(d + 0.004, 0.016)]
        b.lathe(base, ax, prof, n=12)
        b.cyl(base - ax * 0.01, base + ax * 0.012, 0.038, n=12, mat="robot_dark")
        tip = base + ax * (d + 0.004)
        b.cyl(tip, tip + ax * 0.022, 0.02, n=12, mat="copper")
        b.torus(tip + ax * 0.03, ax, 0.024, 0.007, 14, 6, mat="copper")
        b.done(0.0)


LENSES = [("eye_main", (0.032, 1.815), 0.024), ("eye_aux_upper", (-0.034, 1.838), 0.011), ("eye_aux_lower", (-0.052, 1.804), 0.011)]
HEAD_OFF = V((0.0, 0.006, -0.03))  # head geometry is authored high, then dropped/forwarded as a block


def build_head():
    hp = "head"
    n = Part("head_neck", hp, "robot_joint")
    n.cyl((0, 0.02, 1.70), (0, 0.02, 1.79), 0.046, n=14)
    n.tube((0, 0.02, 1.762), (0, 0.02, 1.78), 0.06, 0.04, n=16, mat="robot_dark")
    for sx in (-1, 1):
        n.cyl((sx * 0.05, 0.06, 1.70), (sx * 0.042, 0.09, 1.775), 0.009, n=8, mat="steel")
    n.done(0.002, 1)

    f = Part("head_frame", hp, "robot_dark")
    f.loft([sec((0, -0.078, 1.838), X, Z, crect(0.18, 0.105, 0.03)),
            sec((0, 0.03, 1.8395), X, Z, crect(0.235, 0.125, 0.04)),
            sec((0, 0.165, 1.818), X, Z, crect(0.20, 0.105, 0.035))])
    for j in range(4):
        f.box((0, -0.083, 1.806 + j * 0.016), (0.12, 0.014, 0.006), "robot_joint", bevel=False)
    f.done(0.005, 1)

    Ff = PF((0, 0.252, 1.815), X, (0, -0.1, 1), Y, fx=[(0.0, 26), (0.075, 32), (-0.075, 32)])
    # sensor block with lens barrels and a shattered LIDAR window (exposed when the face plate is lost)
    sb = Part("internal_head_sensor_block", hp, "robot_joint")
    sb.box((0, 0.172, 1.816), (0.19, 0.028, 0.095), "robot_dark")
    lens_fronts = {}
    for nm, (lx, lz), r in LENSES:
        u, v = Ff.find((lx, lz))
        c = Ff.pt(u, v, 0.0)
        yf = c.y - 0.013
        lens_fronts[nm] = (u, v, c, yf)
        nn = 18 if r > 0.02 else 12
        sb.cyl((lx, 0.18, lz), (lx, yf, lz), r, n=nn)
        sb.tube((lx, yf - 0.004, lz), (lx, yf + 0.001, lz), r * 1.0, r * 0.76, n=nn, mat="glass_optic", bevel=False)
    gx, gz = 6, 3
    x0, x1, z0, z1 = -0.092, 0.092, 1.772, 1.862
    grid = {}
    for i in range(gx + 1):
        for j in range(gz + 1):
            jx = 0 if i in (0, gx) else RNG.uniform(-0.35, 0.35) * (x1 - x0) / gx
            jz = 0 if j in (0, gz) else RNG.uniform(-0.35, 0.35) * (z1 - z0) / gz
            grid[i, j] = (x0 + (x1 - x0) * i / gx + jx, z0 + (z1 - z0) * j / gz + jz)
    for i in range(gx):
        for j in range(gz):
            quad = [V(grid[i, j]), V(grid[i + 1, j]), V(grid[i + 1, j + 1]), V(grid[i, j + 1])]
            cen = sum(quad, V((0, 0))) / 4
            quad = [cen + (q - cen) * 0.88 for q in quad]
            tilt = RNG.uniform(-0.004, 0.004)
            vs = [V((q.x, 0.1885 + tilt * (k % 2), q.y)) for k, q in enumerate(quad)]
            sb.add(vs + [v + V((0, -0.002, 0)) for v in vs],
                   [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], "glass_optic", bevel=False)
    for x in (-0.075, 0.075):
        sb.cyl((x, 0.19, 1.762), (x * 0.6, 0.195, 1.79), 0.0045, n=6, mat="rubber_cable", bevel=False)
    sb.done(0.002, 1)

    for nm, (lx, lz), r in LENSES:
        u, v, c, yf = lens_fronts[nm]
        e = Part(nm, hp, "eye_glow")
        e.dome((lx, yf, lz), Y, r * 0.8, r * 0.3, n=18 if r > 0.02 else 12, rings=3)
        e.done(0)

    # face plate (armor_head_1): dark prow-shaped mask; lens apertures are boolean cuts with bezels
    fp = Part("armor_head_1", hp, "robot_dark")
    fol = [(-0.12, 0.035), (-0.06, 0.048), (0.06, 0.048), (0.12, 0.035), (0.12, -0.012), (0.07, -0.05),
           (0.022, -0.064), (-0.022, -0.064), (-0.07, -0.05), (-0.12, -0.012)]
    fp.plate(Ff, chips(fol, [(4, 0.5, 0.012, 0.004)]), 0.02, cuts=(0, 2))
    cut_objs = []
    for nm, (lx, lz), r in LENSES:
        u, v, c, yf = lens_fronts[nm]
        nn = Ff.normal(u, v)
        rh = r + 0.0025
        ring = 0.009 if r > 0.02 else 0.005
        fp.tube(c - nn * 0.005, c + nn * 0.006, rh + ring, rh + 0.0004, n=16 if r > 0.02 else 10, mat="robot_joint")
        ct = Part("cut_" + nm, None)
        ct.cyl(c - nn * 0.05, c + nn * 0.05, rh, n=16 if r > 0.02 else 10)
        cut_objs.append(ct.done_cutter())
    for j in range(3):
        fp.panel(Ff, cpoly(-0.04, -0.05 + j * 0.0105, 0.04, -0.045 + j * 0.0105, (0.002,) * 4), 0.0, "robot_joint", 0.002)
    fp.panel(Ff, cpoly(0.082, -0.03, 0.11, 0.03, (0.004,) * 4), 0.0, "robot_paint", 0.0012)
    fp.bolts(Ff, [(-0.105, 0.025), (0.105, 0.03), (-0.09, -0.025), (0.09, -0.025)], 0.0, r=0.0045)
    fp.done(0.003, 1, cutters=cut_objs)

    # crown (armor_head_2): heavy brow that overhangs the optics
    Fc = PF((0, 0.055, 1.928), X, (0, 1, -0.16), Z, rt=1.2, fx=[(0.07, 34), (-0.07, 34)])
    cr = Part("armor_head_2", hp, "robot_paint")
    col = [(-0.12, -0.13), (0.12, -0.13), (0.14, -0.09), (0.14, 0.10), (0.08, 0.176), (0.0, 0.198),
           (-0.08, 0.176), (-0.14, 0.10), (-0.14, -0.09)]
    cr.plate(Fc, chips(col, [(3, 0.5, 0.02, 0.006), (7, 0.4, 0.018, 0.005)]), 0.026, cuts=(2, 3), dents=[(0.04, 0.02, 0.03, 0.005)])
    cr.plate(Fc, cpoly(-0.028, -0.115, 0.028, 0.15, (0.01, 0.01, 0.02, 0.02)), 0.012, cuts=(0, 3), lift=0.012)
    cr.bolts(Fc, [(-0.1, -0.1), (0.1, -0.1), (-0.11, 0.08), (0.11, 0.08)], 0.0)
    cr.done(0.004, 2)
    ic = Part("internal_head_crown", hp, "robot_joint")
    ic.box((0, 0.02, 1.902), (0.12, 0.12, 0.012), "robot_dark")
    for x in (-0.045, 0.045):
        ic.cyl((x, -0.05, 1.906), (x, 0.13, 1.90), 0.007, n=8, mat="copper")
    ic.done(0.0015, 1)

    # cheek plates (armor_head_3 = right, 4 = left)
    for s, idx in ((1, 3), (-1, 4)):
        F = PF((s * 0.124, 0.06, 1.812), Y, (-s * 0.3, 0, 1), (s, 0, 0), fx=[(0.075, 32)])
        ch = Part(f"armor_head_{idx}", hp, "robot_bone")
        ol = [(-0.12, -0.03), (0.07, -0.05), (0.13, -0.018), (0.125, 0.035), (0.05, 0.055), (-0.12, 0.045)]
        ch.plate(F, chips(ol, [(0, 0.5, 0.016, 0.005)]), 0.02, cuts=(1, 1))
        for j in range(3):
            ch.panel(F, cpoly(-0.08, -0.012 + j * 0.014, 0.02, -0.004 + j * 0.014, (0.003,) * 4), 0.0, "robot_joint", 0.002)
        ch.bolts(F, [(-0.105, 0.032), (-0.105, -0.018), (0.05, 0.035)], 0.0, r=0.0045)
        ch.done(0.0035, 1)
        si = Part(f"internal_head_side_{'R' if s > 0 else 'L'}", hp, "robot_joint")
        si.cyl((s * 0.105, 0.06, 1.81), (s * 0.118, 0.06, 1.81), 0.032, n=14)
        si.cyl((s * 0.112, -0.01, 1.79), (s * 0.112, 0.15, 1.84), 0.005, n=6, mat="rubber_cable")
        si.box((s * 0.108, 0.13, 1.79), (0.02, 0.03, 0.03), "copper")
        si.done(0.0015, 1)

    # sensor mast and whip antenna (frame mounted)
    sm = Part("head_sensor_mast", hp, "robot_joint")
    sm.box((0.075, -0.082, 1.88), (0.03, 0.03, 0.04), "robot_dark")
    sm.cyl((0.075, -0.09, 1.88), (0.075, -0.09, 2.0), 0.0085, n=8)
    sm.loft([sec((0.075, -0.095, 2.015), X, Z, crect(0.042, 0.03, 0.008)), sec((0.075, -0.04, 2.015), X, Z, crect(0.036, 0.024, 0.007))], "robot_dark")
    sm.cyl((0.075, -0.04, 2.015), (0.075, -0.036, 2.015), 0.008, n=10, mat="glass_optic", bevel=False)
    sm.done(0.002, 1)
    led = Part("led_head_mast", hp, "led_amber")
    led.box((0.0975, -0.065, 2.015), (0.003, 0.012, 0.006), bevel=False)
    led.done(0)
    an = Part("head_antenna", hp, "robot_joint")
    an.cyl((-0.08, -0.075, 1.86), (-0.08, -0.075, 1.90), 0.01, n=8, mat="robot_dark")
    an.cyl((-0.08, -0.075, 1.90), (-0.086, -0.115, 2.105), 0.0035, n=6)
    an.cyl((-0.086, -0.115, 2.105), (-0.0862, -0.116, 2.112), 0.006, n=8)
    an.done(0.0)
    cable_bundle("head_cable", hp, [(0.0, -0.04, 1.80), (0.0, -0.085, 1.775), (0.0, -0.115, 1.74), (0.0, -0.135, 1.71)], (0.006, 0.006), 0.022)


def build_arm(s):
    lab = "R" if s > 0 else "L"
    sh, el = f"shoulder_{lab}", f"elbow_{lab}"
    d = Part(f"arm_{lab}_shoulder_drum", sh, "robot_joint")
    d.cyl((s * 0.305, 0, 1.62), (s * 0.445, 0, 1.62), 0.082, n=18)
    for x in (0.33, 0.42):
        d.tube((s * (x - 0.006), 0, 1.62), (s * (x + 0.006), 0, 1.62), 0.087, 0.07, n=18, mat="robot_dark", bevel=False)
    d.cyl((s * 0.445, 0, 1.62), (s * 0.458, 0, 1.62), 0.06, n=18, mat="robot_dark")
    for k in range(6):
        a = 2 * math.pi * k / 6
        d.bolt((s * 0.458, 0.045 * math.cos(a), 1.62 + 0.045 * math.sin(a)), (s, 0, 0), 0.0055, mat="steel")
    d.done(0.003, 1)

    u = Part(f"arm_{lab}_upper_frame", sh, "robot_dark")
    u.loft([sec((s * 0.372, 0, 1.60), X, Y, crect(0.12, 0.15, 0.03)),
            sec((s * 0.375, 0, 1.50), X, Y, crect(0.13, 0.155, 0.035)),
            sec((s * 0.378, 0, 1.425), X, Y, crect(0.115, 0.125, 0.03))])
    arc = [(0.055 * math.cos(math.radians(a)), 1.32 + 0.055 * math.sin(math.radians(a))) for a in range(0, -181, -30)]
    fork = [(-0.055, 1.445), (0.055, 1.445)] + arc
    for xf in (0.309, 0.451):
        u.prism(fork, (s * xf, 0, 0), Y, Z, X, -0.009, 0.009)
    u.bead([(s * 0.318, -0.05, 1.44), (s * 0.318, 0.05, 1.44)], (-s, 0, 0))
    u.done(0.004, 1)
    rc = Part(f"arm_{lab}_ram_cyl", sh, "robot_joint")
    rc.cyl((s * 0.378, -0.088, 1.585), (s * 0.378, -0.091, 1.425), 0.021, n=12)
    rc.cyl((s * 0.378, -0.091, 1.44), (s * 0.378, -0.0912, 1.425), 0.025, n=12, mat="robot_dark")
    rc.box((s * 0.378, -0.08, 1.595), (0.03, 0.03, 0.03), "robot_dark")
    rc.done(0.002, 1)
    rr = Part(f"arm_{lab}_ram_rod", el, "steel")
    rr.cyl((s * 0.378, -0.091, 1.45), (s * 0.378, -0.095, 1.292), 0.0105, n=10)
    rr.cyl((s * 0.358, -0.095, 1.286), (s * 0.398, -0.095, 1.286), 0.013, n=10, mat="robot_dark")
    rr.done(0.0015, 1)

    # pauldron (armor_arm_X_1): pressed and folded steel shell, layered ridge plate
    F = PF((s * 0.34, -0.03, 1.868), (s, 0, 0), (0, 1, -0.10), Z, rt=1.1, fx=[(-0.05, -32), (0.075, 36), (0.165, 52)])
    pa = Part(f"armor_arm_{lab}_1", sh, "robot_paint")
    ol = [(-0.115, -0.14), (-0.065, -0.19), (0.22, -0.19), (0.31, -0.11), (0.31, 0.0), (0.14, 0.165), (-0.095, 0.165), (-0.115, 0.145)]
    ol = chips(ol, [(1, 0.5, 0.025, 0.007), (4, 0.4, 0.02, 0.006), (5, 0.6, 0.02, 0.006)])
    pa.plate(F, ol, 0.028, cuts=(0, 2), dents=[(0.11, 0.03 * s, 0.035, 0.007)])
    lay = cpoly(0.01, -0.16, 0.15, 0.135, (0.02, 0.02, 0.03, 0.02))
    pa.plate(F, lay, 0.014, cuts=(0, 2), lift=0.014)
    pa.bolts(F, [(0.04, -0.14), (0.12, -0.14), (0.04, 0.115), (0.12, 0.11)], 0.014)
    pa.stencil(F, "07", 0.24, -0.045, 0.05, 0.0, "robot_bone", right=(0, 1))
    if s < 0:
        pa.hazard(F, 0.0, 0.07, 0.137, 0.153, 0.0)
    pa.done(0.004, 2)
    led = Part(f"led_shoulder_{lab}", sh, "led_amber")
    led.box((s * 0.40, 0.0835, 1.62), (0.012, 0.004, 0.012), bevel=False)
    led.done(0)
    it = Part(f"internal_arm_{lab}_shoulder", sh, "robot_joint")
    it.cyl((s * 0.37, -0.12, 1.715), (s * 0.37, 0.10, 1.715), 0.036, n=14)
    it.cyl((s * 0.37, -0.13, 1.715), (s * 0.37, -0.12, 1.715), 0.03, n=14, mat="robot_dark")
    it.box((s * 0.33, 0.0, 1.75), (0.06, 0.08, 0.05), "robot_dark")
    it.cyl((s * 0.30, -0.08, 1.74), (s * 0.44, 0.06, 1.75), 0.007, n=8, mat="rubber_cable")
    it.box((s * 0.43, -0.05, 1.70), (0.02, 0.06, 0.05), "copper")
    it.done(0.002, 1)
    pm = Part(f"arm_{lab}_pauldron_mount", sh, "robot_dark")  # struts carrying the pauldron over the drum
    for yy, ztop in ((-0.12, 1.838), (0.085, 1.824)):
        pm.box((s * 0.372, yy, (1.69 + ztop) / 2), (0.10, 0.02, ztop - 1.69))
        pm.bolt((s * 0.372, yy + (0.011 if yy > 0 else -0.011), 1.79), (0, 1 if yy > 0 else -1, 0), 0.006)
    pm.done(0.003, 1)

    # upper-arm plate (armor_arm_X_2)
    F = PF((s * 0.468, 0.0, 1.512), Y, (s * 0.12, 0, 1), (s, 0, 0), fx=[(0.045, 32), (-0.045, 32)])
    up = Part(f"armor_arm_{lab}_2", sh, "robot_bone")
    ol = chips(cpoly(-0.085, -0.08, 0.085, 0.095, (0.02, 0.03, 0.035, 0.03)), [(1, 0.5, 0.02, 0.006)])
    up.plate(F, ol, 0.022, cuts=(0, 1))
    up.panel(F, cpoly(-0.035, -0.05, 0.03, -0.02, (0.004,) * 4), 0.0, "robot_dark", 0.0015)
    up.bolts(F, [(-0.03, 0.075), (0.03, 0.075), (-0.03, -0.065), (0.03, -0.065)], 0.0, r=0.0055)
    up.done(0.004, 1)
    iu = Part(f"internal_arm_{lab}_upper", sh, "robot_joint")
    iu.box((s * 0.442, 0.0, 1.51), (0.02, 0.10, 0.13))
    iu.cyl((s * 0.448, 0.035, 1.44), (s * 0.448, 0.035, 1.59), 0.008, n=8, mat="rubber_cable")
    iu.cyl((s * 0.448, -0.035, 1.44), (s * 0.448, -0.035, 1.59), 0.006, n=8, mat="copper")
    iu.done(0.0015, 1)

    h = Part(f"arm_{lab}_elbow_hub", el, "robot_joint")
    h.cyl((s * 0.318, 0, 1.32), (s * 0.442, 0, 1.32), 0.056, n=18)
    for x0, x1 in ((0.29, 0.30), (0.46, 0.47)):
        h.cyl((s * x0, 0, 1.32), (s * x1, 0, 1.32), 0.034, n=14, mat="robot_dark")
    h.done(0.003, 1)


def forearm_housing(s, name, front):
    lab = "R" if s > 0 else "L"
    el = f"elbow_{lab}"
    cx = s * 0.38
    hsg = Part(name, el, "robot_dark")
    if front < 0.2:
        hsg.loft([sec((cx, 0.035, 1.322), X, Z, crect(0.115, 0.12, 0.03)),
                  sec((cx, 0.075, 1.325), X, Z, crect(0.124, 0.155, 0.04)),
                  sec((cx, 0.155, 1.325), X, Z, crect(0.124, 0.155, 0.04)),
                  sec((cx, front, 1.322), X, Z, crect(0.105, 0.125, 0.035))])
    else:
        hsg.loft([sec((cx, 0.035, 1.322), X, Z, crect(0.115, 0.125, 0.03)),
                  sec((cx, 0.08, 1.325), X, Z, crect(0.124, 0.17, 0.04)),
                  sec((cx, 0.20, 1.322), X, Z, crect(0.124, 0.16, 0.04)),
                  sec((cx, front, 1.32), X, Z, crect(0.105, 0.125, 0.035))])
    hsg.loft([sec((cx, -0.13, 1.272), X, Z, crect(0.075, 0.055, 0.015)),
              sec((cx, -0.04, 1.268), X, Z, crect(0.09, 0.07, 0.02)),
              sec((cx, 0.05, 1.28), X, Z, crect(0.10, 0.09, 0.025))])
    hsg.cyl((cx - 0.025, -0.095, 1.286), (cx + 0.025, -0.095, 1.286), 0.012, n=10, mat="robot_joint")
    hsg.bead([(cx - s * 0.062, 0.06, 1.39), (cx - s * 0.062, front - 0.02, 1.39)], (-s, 0, 1))
    return hsg


def build_projector():
    """Right forearm: arc projector."""
    el = "elbow_R"
    cx, cz = 0.38, 1.32
    hsg = forearm_housing(1, "arm_R_projector_housing", 0.19)
    hsg.done(0.005, 1)
    led = Part("led_arm_R", el, "led_amber")
    led.box((0.3165, 0.13, 1.35), (0.004, 0.016, 0.007), bevel=False)
    led.done(0)

    F = PF((cx, 0.125, 1.425), X, Y, Z, fx=[(0.035, 30), (-0.035, 30)])
    tp = Part("armor_arm_R_3", el, "robot_paint")
    tp.plate(F, chips(cpoly(-0.07, -0.058, 0.07, 0.058, (0.015, 0.015, 0.03, 0.03)), [(0, 0.4, 0.02, 0.005)]), 0.02, cuts=(0, 1))
    tp.hazard(F, -0.03, 0.03, 0.026, 0.042, 0.0)
    tp.bolts(F, [(-0.05, -0.043), (0.05, -0.043), (-0.05, 0.012), (0.05, 0.012)], 0.0, r=0.005)
    tp.done(0.004, 1)
    ic = Part("internal_arm_R_capacitor", el, "robot_joint")
    for x in (-0.028, 0.028):
        ic.cyl((cx + x, 0.075, 1.401), (cx + x, 0.175, 1.401), 0.012, n=10)
        ic.cyl((cx + x, 0.175, 1.401), (cx + x, 0.181, 1.401), 0.007, n=8, mat="copper")
    ic.box((cx, 0.08, 1.405), (0.08, 0.008, 0.006), "copper")
    ic.done(0.0015, 1)

    F = PF((0.465, 0.125, 1.322), Y, Z, X, fx=[(0.035, 30), (-0.035, 30)])
    sp = Part("armor_arm_R_4", el, "robot_paint")
    sp.plate(F, chips(cpoly(-0.058, -0.068, 0.06, 0.07, (0.02, 0.03, 0.03, 0.015)), [(5, 0.5, 0.02, 0.005)]), 0.02, cuts=(0, 1))
    sp.stencil(F, "9", 0.0, 0.012, 0.05, 0.0, "robot_bone", right=(1, 0))
    sp.bolts(F, [(-0.045, 0.055), (0.045, 0.055), (-0.045, -0.055), (0.045, -0.055)], 0.0, r=0.005)
    sp.done(0.004, 1)
    isd = Part("internal_arm_R_side", el, "copper")
    for z in (1.29, 1.35):
        isd.cyl((0.447, 0.07, z), (0.447, 0.185, z), 0.006, n=8)
    isd.cyl((0.447, 0.07, 1.32), (0.447, 0.185, 1.32), 0.008, n=8, mat="rubber_cable")
    isd.done(0.0)

    # barrel: copper coil rings, ceramic discs, finned cooling shroud, emitter head with three electrodes
    b = Part("arm_R_arc_barrel", el, "robot_dark")
    c = V((cx, 0, cz))
    b.cyl(c + Y * 0.19, c + Y * 0.455, 0.032, n=14)
    b.tube(c + Y * 0.185, c + Y * 0.212, 0.075, 0.03, n=20, mat="robot_joint")
    sect = [(0.090 * math.cos(math.radians(a)), 0.090 * math.sin(math.radians(a))) for a in range(15, 166, 15)]
    sect += [(0.080 * math.cos(math.radians(a)), 0.080 * math.sin(math.radians(a))) for a in range(165, 14, -15)]
    b.prism(sect, c, X, Z, Y, 0.205, 0.405)
    for a in (45, 67, 90, 113, 135):
        ra = math.radians(a)
        dvec = V((math.cos(ra), 0, math.sin(ra)))
        tvec = V((-math.sin(ra), 0, math.cos(ra)))
        b.obox(c + dvec * 0.101 + Y * 0.305, tvec, Y, dvec, (0.0045, 0.18, 0.024), bevel=False)
    for a in (225, 315):
        ra = math.radians(a)
        dvec = V((math.cos(ra), 0, math.sin(ra)))
        b.cyl(c + dvec * 0.072 + Y * 0.20, c + dvec * 0.072 + Y * 0.41, 0.006, n=8, mat="steel")
    b.lathe(c + Y * 0.40, Y, [(0.0, 0.035), (0.0, 0.074), (0.03, 0.07), (0.045, 0.056), (0.052, 0.05), (0.052, 0.03)], n=18, mat="robot_joint")
    b.done(0.003, 1)
    co = Part("arm_R_arc_coils", el, "copper")
    for i in range(5):
        co.torus(c + Y * (0.228 + i * 0.038), Y, 0.053, 0.0115, 16, 6)
    co.cyl(c + Y * 0.455, c + Y * 0.492, 0.008, n=10)
    for a in (90, 210, 330):
        ra = math.radians(a)
        dvec = V((math.cos(ra), 0, math.sin(ra)))
        co.cyl(c + dvec * 0.0275 + Y * 0.518, c + dvec * 0.026 + Y * 0.53, 0.006, n=8)
    co.done(0.0)
    ce = Part("arm_R_arc_insulators", el, "ceramic")
    for i in range(4):
        y0 = 0.241 + i * 0.038
        ce.tube(c + Y * y0, c + Y * (y0 + 0.012), 0.07, 0.032, n=20)
    ce.tube(c + Y * 0.452, c + Y * 0.463, 0.042, 0.012, n=16)
    ce.done(0)
    pr = Part("arm_R_arc_prongs", el, "robot_dark")
    for a in (90, 210, 330):
        ra = math.radians(a)
        dvec = V((math.cos(ra), 0, math.sin(ra)))
        tvec = V((-math.sin(ra), 0, math.cos(ra)))
        p0 = c + dvec * 0.048 + Y * 0.448
        p1 = c + dvec * 0.028 + Y * 0.518
        dd = (p1 - p0).normalized()
        upv = tvec.cross(dd).normalized()
        pr.loft([sec(p0, tvec, upv, crect(0.017, 0.015, 0.004)), sec(p1, tvec, upv, crect(0.012, 0.01, 0.003))])
    pr.done(0.002, 1)
    t = Part("arc_tip", el, "arc_tip")
    t.lathe(c + Y * 0.49, Y, [(0.0, 0.002), (0.004, 0.012), (0.012, 0.0175), (0.022, 0.0175), (0.030, 0.012), (0.034, 0.002)], n=14, bevel=False)
    t.done(0)


def build_claw_arm():
    """Left forearm: heavy housing, riot guard, three-finger manipulator."""
    el = "elbow_L"
    cx = -0.38
    hsg = forearm_housing(-1, "arm_L_forearm_housing", 0.245)
    for yb in (0.10, 0.20):
        hsg.box((-0.455, yb, 1.32), (0.03, 0.03, 0.05), "robot_joint")
    hsg.done(0.005, 1)

    F = PF((-0.484, 0.125, 1.32), Y, (0.10, 0, 1), (-1, 0, 0), rt=0.9, fx=[(0.13, 30), (-0.11, 18)])
    rg = Part("armor_arm_L_3", el, "robot_paint")
    ol = [(-0.165, -0.10), (-0.125, -0.165), (0.14, -0.165), (0.20, -0.105), (0.20, 0.115), (0.15, 0.17), (0.0, 0.17), (-0.05, 0.095), (-0.165, 0.08)]
    olc = chips(ol, [(2, 0.4, 0.025, 0.008), (5, 0.5, 0.02, 0.007), (0, 0.5, 0.02, 0.006)])
    rg.plate(F, olc, 0.03, cuts=(1, 3), dents=[(0.05, 0.02, 0.035, 0.007)])
    rg.plate(F, inset(ol, 0.03), 0.012, cuts=(1, 3), lift=0.012)
    rg.hazard(F, 0.142, 0.172, -0.10, 0.09, 0.012, along="y")
    rg.stencil(F, "09", -0.02, 0.0, 0.07, 0.012, "robot_bone", right=(1, 0))
    rg.bolts(F, [(-0.125, -0.12), (0.10, -0.125), (0.10, 0.125), (-0.03, 0.135), (-0.125, 0.045)], 0.012)
    rg.done(0.005, 1)
    gm = Part("internal_arm_L_guard_mount", el, "robot_joint")
    gm.cyl((-0.452, 0.03, 1.32), (-0.452, 0.27, 1.32), 0.013, n=10)
    for yb in (0.06, 0.24):
        gm.cyl((-0.45, yb, 1.25), (-0.45, yb + 0.02, 1.40), 0.007, n=8, mat="steel")
    gm.done(0.0015, 1)

    F = PF((cx, 0.155, 1.43), X, Y, Z, fx=[(0.035, 30), (-0.035, 30)])
    tp = Part("armor_arm_L_4", el, "robot_bone")
    tp.plate(F, chips(cpoly(-0.066, -0.085, 0.066, 0.085, (0.015, 0.015, 0.03, 0.03)), [(0, 0.6, 0.02, 0.005)]), 0.02, cuts=(0, 1))
    tp.panel(F, cpoly(-0.025, -0.06, 0.025, -0.035, (0.004,) * 4), 0.0, "robot_dark", 0.0015)
    tp.bolts(F, [(-0.05, -0.07), (0.05, -0.07), (-0.05, 0.06), (0.05, 0.06)], 0.0, r=0.005)
    tp.done(0.004, 1)
    ih = Part("internal_arm_L_hydraulics", el, "steel")
    for x in (-0.03, 0.03):
        ih.cyl((cx + x, 0.07, 1.406), (cx + x, 0.25, 1.406), 0.006, n=8)
    ih.box((cx, 0.12, 1.405), (0.09, 0.04, 0.012), "robot_joint")
    ih.done(0.0015, 1)

    W = V((cx, 0.0, 1.32))
    w = Part("arm_L_claw_wrist", el, "robot_joint")
    w.cyl(W + Y * 0.245, W + Y * 0.282, 0.052, n=18)
    w.tube(W + Y * 0.25, W + Y * 0.262, 0.058, 0.04, n=18, mat="robot_dark")
    w.loft([sec(W + Y * 0.28, X, Z, crect(0.10, 0.10, 0.028)), sec(W + Y * 0.325, X, Z, crect(0.088, 0.088, 0.024))], "robot_dark")
    w.done(0.003, 1)
    fingers = [("f1", -58.0, (0.064, 0.056, 0.05)), ("f2", 58.0, (0.064, 0.056, 0.05)), ("f3", 180.0, (0.056, 0.05, 0.044))]
    for fname, ang, lens in fingers:
        a = math.radians(ang)
        r = V((math.sin(a), 0, math.cos(a)))
        hinge = Y.cross(r).normalized()
        p = W + Y * 0.322 + r * 0.03
        dirs = (math.radians(28), math.radians(-6), math.radians(-44))
        widths = ((0.026, 0.023), (0.022, 0.02), (0.019, 0.004))
        for si in range(3):
            L, ad, (w0, w1) = lens[si], dirs[si], widths[si]
            dv = (Y * math.cos(ad) + r * math.sin(ad)).normalized()
            q = p + dv * L
            upv = hinge.cross(dv).normalized()
            seg = Part(f"arm_L_claw_{fname}_seg{si + 1}", el, "robot_dark" if si < 2 else "robot_joint")
            seg.cyl(p - hinge * 0.016, p + hinge * 0.016, 0.0105, n=10, mat="steel")
            a0 = p + dv * 0.006
            a1 = q - dv * (0.004 if si < 2 else 0.0)
            if si < 2:
                seg.loft([sec(a0, hinge, upv, crect(w0, w0 * 0.92, 0.005)), sec(a0.lerp(a1, 0.5), hinge, upv, crect(w0 * 1.06, w0, 0.005)),
                          sec(a1, hinge, upv, crect(w1, w1 * 0.9, 0.004))])
            else:
                seg.loft([sec(a0, hinge, upv, crect(w0, w0 * 0.92, 0.005)), sec(a0.lerp(a1, 0.55), hinge, upv, crect(w0 * 0.82, w0 * 0.7, 0.004)),
                          sec(a1, hinge, upv, crect(0.004, 0.003, 0.0008))])
                seg.loft([sec(a0.lerp(a1, 0.2) - upv * 0.004, hinge, upv, crect(0.006, 0.01, 0.001)),
                          sec(a1 - upv * 0.001, hinge, upv, crect(0.002, 0.003, 0.0004))], "steel", bevel=False)
            seg.done(0.0015, 1)
            p = q


def build_leg(s):
    lab = "R" if s > 0 else "L"
    hip, knee, ank = f"hip_{lab}", f"knee_{lab}", f"ankle_{lab}"
    cx = s * 0.16

    d = Part(f"leg_{lab}_hip_drum", hip, "robot_joint")
    d.cyl((s * 0.095, 0, 0.98), (s * 0.24, 0, 0.98), 0.072, n=20)
    d.tube((s * 0.17, 0, 0.98), (s * 0.182, 0, 0.98), 0.077, 0.06, n=20, mat="robot_dark")
    d.done(0.003, 1)

    t = Part(f"leg_{lab}_thigh_frame", hip, "robot_dark")
    t.loft([sec((s * 0.165, -0.005, 0.95), X, Y, crect(0.14, 0.16, 0.035)),
            sec((s * 0.168, 0.012, 0.86), X, Y, crect(0.19, 0.22, 0.05)),
            sec((s * 0.165, 0.008, 0.72), X, Y, crect(0.18, 0.21, 0.05)),
            sec((s * 0.16, 0.0, 0.615), X, Y, crect(0.13, 0.14, 0.03))])
    t.box((cx, -0.118, 0.915), (0.12, 0.03, 0.03), "robot_joint")
    t.bead([(s * 0.262, -0.06, 0.86), (s * 0.262, 0.07, 0.86)], (s, 0, 0))
    t.done(0.006, 1)
    rc = Part(f"leg_{lab}_knee_ram_cyl", hip, "robot_joint")
    rd = Part(f"leg_{lab}_knee_ram_rod", knee, "steel")
    for ox in (-0.038, 0.038):
        x = cx + ox
        rc.cyl((x, -0.122, 0.91), (x, -0.122, 0.60), 0.022, n=12)
        rc.cyl((x, -0.122, 0.62), (x, -0.122, 0.60), 0.026, n=12, mat="robot_dark")
        rd.cyl((x, -0.122, 0.64), (x, -0.128, 0.37), 0.0105, n=10)
    rd.cyl((cx - 0.052, -0.128, 0.37), (cx + 0.052, -0.128, 0.37), 0.013, n=10, mat="robot_dark")
    rc.done(0.002, 1)
    rd.done(0.0015, 1)

    # thigh front plate (armor_leg_X_1)
    F = PF((s * 0.168, 0.15, 0.79), (s, 0, 0), (0, -0.2, 1), Y, rt=0.8, fx=[(0.05, 36), (-0.05, 36)])
    tf = Part(f"armor_leg_{lab}_1", hip, "robot_paint")
    ol = [(0.0, -0.13), (0.10, -0.075), (0.115, 0.11), (0.085, 0.15), (-0.085, 0.15), (-0.115, 0.11), (-0.10, -0.075)]
    tf.plate(F, chips(ol, [(1, 0.6, 0.02, 0.006), (4, 0.4, 0.02, 0.006)]), 0.028, cuts=(0, 3),
             dents=[(0.02, -0.06, 0.03, 0.006)] if s > 0 else [(-0.03, 0.05, 0.03, 0.005)])
    tf.plate(F, inset(ol, 0.022), 0.012, cuts=(0, 3), lift=0.012)
    tf.bolts(F, [(-0.035, 0.12), (0.035, 0.12), (0.0, -0.085)], 0.012)
    tf.done(0.004, 1)
    it = Part(f"internal_leg_{lab}_thigh", hip, "robot_joint")
    it.cyl((cx, 0.10, 0.92), (cx, 0.10, 0.70), 0.026, n=12)
    it.cyl((cx, 0.10, 0.71), (cx, 0.10, 0.63), 0.012, n=10, mat="steel")
    it.box((cx, 0.09, 0.93), (0.11, 0.04, 0.04), "robot_dark")
    for ox in (-0.06, 0.06):
        it.cyl((cx + ox, 0.10, 0.66), (cx + ox * 0.8, 0.105, 0.90), 0.006, n=8, mat="rubber_cable")
    it.done(0.0015, 1)

    # outer thigh plate (armor_leg_X_2)
    F = PF((s * 0.288, 0.01, 0.765), Y, Z, (s, 0, 0), fx=[(0.06, 30), (-0.05, 30)])
    to = Part(f"armor_leg_{lab}_2", hip, "robot_dark")
    to.plate(F, chips(cpoly(-0.095, -0.12, 0.105, 0.095, (0.03, 0.04, 0.03, 0.02)), [(3, 0.5, 0.02, 0.006)]), 0.022, cuts=(0, 1))
    to.panel(F, cpoly(-0.04, 0.02, 0.05, 0.06, (0.005,) * 4), 0.0, "robot_bone", 0.0015)
    to.stencil(F, "2" if s > 0 else "3", 0.005, -0.04, 0.045, 0.0, "robot_bone", right=(1, 0))
    to.bolts(F, [(-0.03, 0.075), (0.04, 0.075), (-0.03, -0.10), (0.04, -0.10)], 0.0, r=0.0055)
    to.done(0.004, 1)
    ih = Part(f"internal_leg_{lab}_hipservo", hip, "robot_joint")
    ih.cyl((s * 0.255, 0.0, 0.79), (s * 0.268, 0.0, 0.79), 0.05, n=14)
    ih.cyl((s * 0.262, -0.07, 0.70), (s * 0.262, 0.06, 0.85), 0.007, n=8, mat="rubber_cable")
    ih.box((s * 0.26, 0.05, 0.70), (0.015, 0.05, 0.06), "copper")
    ih.done(0.0015, 1)

    # knee
    k = Part(f"leg_{lab}_knee_drum", knee, "robot_joint")
    k.cyl((s * 0.08, 0, 0.55), (s * 0.24, 0, 0.55), 0.064, n=18)
    for x0, x1 in ((0.07, 0.08), (0.24, 0.25)):
        k.cyl((s * x0, 0, 0.55), (s * x1, 0, 0.55), 0.046, n=14, mat="robot_dark")
    k.done(0.003, 1)
    kc = Part(f"armor_leg_{lab}_3", knee, "robot_dark")
    prof = [(0.04, 0.652), (0.14, 0.622), (0.198, 0.545), (0.168, 0.452), (0.092, 0.426), (0.06, 0.50)]
    kc.prism(prof, (cx, 0, 0), Y, Z, X, -0.076, 0.076, scale1=1.0)
    kc.prism([(0.145, 0.61), (0.183, 0.548), (0.16, 0.472), (0.146, 0.494), (0.163, 0.548)], (cx, 0, 0), Y, Z, X, -0.03, 0.03, "robot_paint")
    for ox in (-0.078, 0.078):
        kc.bolt((cx + ox, 0.10, 0.53), (1 if ox > 0 else -1, 0, 0), 0.006)
    kc.done(0.005, 1)
    ik = Part(f"internal_leg_{lab}_knee", knee, "robot_joint")
    ik.cyl((cx - 0.06, 0.07, 0.53), (cx + 0.06, 0.07, 0.53), 0.033, n=14)
    ik.box((cx, 0.075, 0.48), (0.06, 0.04, 0.05), "robot_dark")
    ik.cyl((cx - 0.03, 0.09, 0.60), (cx - 0.03, 0.095, 0.47), 0.006, n=8, mat="rubber_cable")
    ik.done(0.0015, 1)

    # shin frame with a rearward hock: suggests a reverse-knee silhouette while the joints stay in line
    sh = Part(f"leg_{lab}_shin_frame", knee, "robot_dark")
    sh.loft([sec((cx, 0.0, 0.515), X, Y, crect(0.13, 0.15, 0.035)),
             sec((cx, -0.04, 0.40), X, Y, crect(0.14, 0.20, 0.045)),
             sec((cx, -0.055, 0.29), X, Y, crect(0.13, 0.18, 0.04)),
             sec((cx, -0.02, 0.17), X, Y, crect(0.105, 0.12, 0.03)),
             sec((cx, -0.01, 0.125), X, Y, crect(0.095, 0.10, 0.025))])
    sh.loft([sec((cx, -0.135, 0.452), X, Y, crect(0.11, 0.04, 0.012)),
             sec((cx, -0.195, 0.34), X, Y, crect(0.125, 0.11, 0.03)),
             sec((cx, -0.185, 0.25), X, Y, crect(0.10, 0.09, 0.025)),
             sec((cx, -0.115, 0.185), X, Y, crect(0.075, 0.03, 0.01))], "robot_joint")
    sh.box((cx, -0.128, 0.372), (0.12, 0.03, 0.03))
    sh.bead([(cx - s * 0.07, -0.10, 0.45), (cx - s * 0.07, -0.12, 0.25)], (-s, 0, 0))
    sh.done(0.006, 1)
    ac = Part(f"leg_{lab}_ankle_ram_cyl", knee, "robot_joint")
    ac.cyl((cx, -0.225, 0.33), (cx, -0.185, 0.18), 0.019, n=12)
    ac.cyl((cx, -0.228, 0.345), (cx, -0.225, 0.33), 0.015, n=10, mat="robot_dark")
    ac.done(0.002, 1)
    ar = Part(f"leg_{lab}_ankle_ram_rod", ank, "steel")
    ar.cyl((cx, -0.19, 0.20), (cx, -0.15, 0.085), 0.009, n=10)
    ar.cyl((cx - 0.02, -0.15, 0.082), (cx + 0.02, -0.15, 0.082), 0.012, n=10, mat="robot_dark")
    ar.done(0.0015, 1)

    # shin guard (armor_leg_X_4): raked blade
    F = PF((cx, 0.112, 0.335), (s, 0, 0), (0, 0.30, 1), Y, rt=0.9, fx=[(0.0, 22), (0.04, 30), (-0.04, 30)])
    sg = Part(f"armor_leg_{lab}_4", knee, "robot_paint")
    ol = [(-0.025, -0.2), (0.025, -0.2), (0.048, -0.13), (0.068, 0.12), (0.052, 0.17), (-0.052, 0.17), (-0.068, 0.12), (-0.048, -0.13)]
    sg.plate(F, chips(ol, [(2, 0.5, 0.02, 0.006), (6, 0.3, 0.02, 0.006)]), 0.026, cuts=(0, 4),
             dents=[(0.0, 0.0, 0.03, 0.006)] if s < 0 else [(0.0, 0.07, 0.03, 0.005)])
    sg.bolts(F, [(-0.05, 0.13), (0.05, 0.13), (-0.035, -0.14), (0.035, -0.14)], 0.0, r=0.0055)
    sg.done(0.004, 1)
    isn = Part(f"internal_leg_{lab}_shin", knee, "steel")
    for ox in (-0.03, 0.03):
        isn.cyl((cx + ox, 0.058, 0.50), (cx + ox, 0.035, 0.17), 0.006, n=8)
    isn.cyl((cx, 0.062, 0.49), (cx, 0.04, 0.18), 0.008, n=8, mat="rubber_cable")
    for z in (0.42, 0.30):
        isn.box((cx, 0.05 - (0.42 - z) * 0.12, z), (0.09, 0.02, 0.012), "robot_joint")
    isn.done(0.0015, 1)

    # ankle + foot
    ft = Part(f"leg_{lab}_foot", ank, "robot_dark")
    ft.cyl((cx - 0.075, 0, 0.10), (cx + 0.075, 0, 0.10), 0.048, n=16, mat="robot_joint")
    ft.loft([sec((cx, -0.155, 0.045), X, Z, crect(0.15, 0.065, 0.02)),
             sec((cx, -0.05, 0.07), X, Z, crect(0.20, 0.115, 0.035)),
             sec((cx, 0.07, 0.058), X, Z, crect(0.23, 0.09, 0.03)),
             sec((cx, 0.13, 0.045), X, Z, crect(0.22, 0.065, 0.02))])
    ft.prism(cpoly(-0.12, -0.20, 0.12, 0.17, (0.03, 0.03, 0.045, 0.045)), (cx, 0, 0), X, Y, Z, 0.0, 0.016, "robot_joint")
    ft.loft([sec((cx, -0.15, 0.04), X, Z, crect(0.12, 0.05, 0.015)), sec((cx, -0.235, 0.025), X, Z, crect(0.08, 0.03, 0.008))])
    side = [(-0.06, 0.03), (0.07, 0.03), (0.06, 0.10), (0.0, 0.158), (-0.05, 0.125)]
    for ox in (-0.087, 0.087):
        ft.prism(side, (cx + ox, 0, 0), Y, Z, X, -0.008, 0.008)
        ft.bolt((cx + ox + (0.009 if ox > 0 else -0.009), 0, 0.10), (1 if ox > 0 else -1, 0, 0), 0.007, mat="steel")
    ft.done(0.005, 1)
    toes = Part(f"leg_{lab}_toes", ank, "robot_paint")
    for off, spl in ((-0.058, -7.0), (0.058, 9.0)):
        o = V((cx + s * off, 0.205, 0.066))
        ex = rotz(X * s, spl * s)
        ey = rotz(V((0, 1, -0.5)), spl * s)
        F = PF(o, ex, ey, (0, 0.3, 1), fx=[(0.025, 30), (-0.025, 30)])
        toes.plate(F, chips([(-0.05, -0.075), (0.05, -0.075), (0.05, 0.03), (0.012, 0.085), (-0.012, 0.085), (-0.05, 0.03)], [(1, 0.5, 0.015, 0.005)]), 0.028, cuts=(0, 1))
        toes.bolts(F, [(0.0, -0.05)], 0.0, r=0.005)
        toes.obox(o + rotz(V((0, 0.072, -0.046)), spl * s), ex, rotz(Y, spl * s), Z, (0.085, 0.045, 0.036), "robot_joint")
    toes.done(0.004, 1)

    cable_bundle(f"leg_{lab}_cable", hip, [(s * 0.075, -0.10, 1.03), (s * 0.095, -0.11, 0.95), (s * 0.10, -0.10, 0.82), (s * 0.095, -0.08, 0.70)], (0.009,), 0.0)


def build_cables():
    # back unit -> arms (split at the joints so each piece follows its own empty)
    for s, lab in ((1, "R"), (-1, "L")):
        cable_bundle(f"cable_arm_{lab}_feed_a", "torso",
                     [(s * 0.12, -0.25, 1.69), (s * 0.19, -0.235, 1.765), (s * 0.28, -0.18, 1.775), (s * 0.33, -0.13, 1.70), (s * 0.335, -0.105, 1.63)],
                     (0.013, 0.010), 0.016, phase=0.4)
        cable_bundle(f"cable_arm_{lab}_feed_b", f"shoulder_{lab}",
                     [(s * 0.335, -0.105, 1.63), (s * 0.33, -0.10, 1.52), (s * 0.338, -0.105, 1.40), (s * 0.36, -0.125, 1.30), (s * 0.38, -0.14, 1.272)],
                     (0.013, 0.010), 0.016, phase=0.4)
    cl = Part("cable_clamps", "torso", "robot_joint")
    for s in (1, -1):
        cl.cyl((s * 0.112, -0.252, 1.69), (s * 0.135, -0.248, 1.69), 0.024, n=10)
        cl.tube((s * 0.286, -0.175, 1.77), (s * 0.30, -0.165, 1.77), 0.03, 0.018, n=10, mat="robot_dark")
    cl.done(0)
    for s, lab in ((1, "R"), (-1, "L")):
        cc = Part(f"cable_clamps_arm_{lab}", f"shoulder_{lab}", "robot_dark")
        cc.tube((s * 0.33, -0.10, 1.53), (s * 0.33, -0.10, 1.51), 0.03, 0.017, n=10)
        cc.box((s * 0.345, -0.088, 1.52), (0.02, 0.012, 0.03))
        cc.done(0.002, 1)
        cf = Part(f"cable_inlet_arm_{lab}", f"elbow_{lab}", "robot_joint")
        cf.cyl((s * 0.38, -0.145, 1.272), (s * 0.38, -0.125, 1.272), 0.024, n=10)
        cf.done(0.002, 1)
    cable_bundle("cable_waist_R", "torso", [(0.07, 0.07, 1.29), (0.12, 0.10, 1.23), (0.10, 0.09, 1.17), (0.07, 0.05, 1.16)], (0.009, 0.008, 0.007), 0.012)
    cable_bundle("cable_waist_L", "torso", [(-0.07, -0.06, 1.29), (-0.12, -0.09, 1.23), (-0.10, -0.08, 1.17), (-0.07, -0.04, 1.16)], (0.009, 0.008), 0.012)


# =================================================================== PIPELINE
def apply_geometry_mods():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    pending = []
    for ob, _ in REG:
        if ob.modifiers:
            pending.append((ob, bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)))
    for ob, me in pending:
        old = ob.data
        ob.modifiers.clear()
        ob.data = me
        bpy.data.meshes.remove(old)
        me.name = ob.name
        me.validate(clean_customdata=False)
    for c in CUTTERS:
        me = c.data
        bpy.data.objects.remove(c, do_unlink=True)
        bpy.data.meshes.remove(me)
    for ob, _ in REG:
        me = ob.data
        for an in ("bevel_weight_edge", "nobev"):
            a = me.attributes.get(an)
            if a:
                me.attributes.remove(a)
        recenter(ob)


def smart_uv(objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.0015, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        o.select_set(False)


def shade(objs):
    lim = math.radians(60.0)
    for o in objs:
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0.0) <= lim
        bm.to_mesh(me)
        bm.free()
        wn = o.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
        wn.mode = "FACE_AREA"
        wn.weight = 50
        wn.keep_sharp = True


def parent_all():
    for ob, pname in REG:
        wl = ob.location.copy()
        ob.parent = E[pname]
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = wl - EW[pname]
    bpy.context.view_layer.update()
    for ob, pname in REG:
        assert (ob.matrix_world.translation - (ob.location + EW[pname])).length < 1e-5, ob.name


def tri_count(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)


def world_bounds(objs):
    mn = V((1e9, 1e9, 1e9))
    mxv = V((-1e9, -1e9, -1e9))
    for o in objs:
        M = o.matrix_world
        for v in o.data.vertices:
            w = M @ v.co
            mn = V((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
            mxv = V((max(mxv.x, w.x), max(mxv.y, w.y), max(mxv.z, w.z)))
    return mn, mxv


# =================================================================== PREVIEWS
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    try:
        sc.eevee.taa_render_samples = 24 if FAST else 64
        sc.eevee.use_raytracing = True
        sc.eevee.use_shadows = True
    except Exception as ex:
        print("eevee setting skipped:", ex)
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.view_settings.view_transform = "AgX"
        for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Base Contrast"):
            try:
                sc.view_settings.look = look
                break
            except Exception:
                pass
    except Exception as ex:
        print("color management skipped:", ex)
    world = bpy.data.worlds.new("preview_world")
    sc.world = world
    bg = world.node_tree.nodes.get("Background") if world.node_tree else None
    if bg is None:
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.0025, 0.0028, 0.0035, 1)
    bg.inputs[1].default_value = 1.0
    # floor
    fm = bpy.data.materials.new("preview_floor")
    fb = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fb.inputs["Base Color"].default_value = (0.008, 0.008, 0.009, 1)
    fb.inputs["Roughness"].default_value = 0.8
    me = bpy.data.meshes.new("preview_floor")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=12)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(fm)
    fl = bpy.data.objects.new("preview_floor", me)
    sc.collection.objects.link(fl)
    cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    lights = {}
    for nm in ("key", "fill", "rimL", "rimR"):
        ld = bpy.data.lights.new("pv_" + nm, "AREA")
        lo = bpy.data.objects.new("pv_" + nm, ld)
        sc.collection.objects.link(lo)
        lights[nm] = lo
    return cam, lights, fl


def aim(ob, target):
    d = V(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def rig(lights, cam_loc, target, scale=1.0, dim=1.0):
    t = V(target)
    f = t - V(cam_loc)
    f.z = 0
    f.normalize()
    r = f.cross(Z).normalized()
    spec = {
        "key": (t - f * 2.2 * scale + r * 2.0 * scale + Z * 2.0 * scale, 240, (1.0, 0.95, 0.90), 1.0),
        "fill": (t - f * 2.6 * scale - r * 2.4 * scale + Z * 0.4 * scale, 30, (0.60, 0.72, 1.0), 2.0),
        "rimL": (t + f * 2.4 * scale - r * 1.7 * scale + Z * 1.7 * scale, 520, (0.70, 0.82, 1.0), 0.6),
        "rimR": (t + f * 2.2 * scale + r * 1.9 * scale + Z * 1.2 * scale, 300, (1.0, 0.82, 0.62), 0.6),
    }
    for nm, (pos, energy, col, size) in spec.items():
        lo = lights[nm]
        lo.location = pos
        aim(lo, t)
        lo.data.energy = energy * scale * scale * dim
        lo.data.color = col
        lo.data.size = size * scale


def shot(path, cam, lights, cam_loc, target, lens=50, res=(1000, 1400), scale=1.0, dim=1.0):
    sc = bpy.context.scene
    cam.location = V(cam_loc)
    aim(cam, target)
    cam.data.lens = lens
    cam.data.clip_start = 0.05
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 50 if FAST else 100
    rig(lights, cam_loc, target, scale, dim)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path, round(time.time() - T0, 1), "s")


def render_previews(mesh_objs):
    os.makedirs(PREV, exist_ok=True)
    cam, lights, floor = setup_render()
    tgt = (0, 0, 1.05)
    full = (1000, 1400)
    shot(os.path.join(PREV, "01_front.png"), cam, lights, (0.0, 4.6, 1.2), tgt, 50, full)
    shot(os.path.join(PREV, "02_back.png"), cam, lights, (0.0, -4.6, 1.35), tgt, 50, full)
    shot(os.path.join(PREV, "03_three_quarter.png"), cam, lights, (2.9, 3.5, 1.6), tgt, 50, full)
    shot(os.path.join(PREV, "04_side.png"), cam, lights, (4.6, 0.0, 1.15), tgt, 50, full)
    shot(os.path.join(PREV, "05_head_closeup.png"), cam, lights, (0.36, 0.86, 1.97), (0.0, 0.1, 1.84), 55, (1200, 900), scale=0.45)
    shot(os.path.join(PREV, "06_back_three_quarter.png"), cam, lights, (-2.6, -3.4, 1.75), (0, -0.1, 1.15), 50, full)
    # damaged: every armour plate removed
    armor = [o for o in mesh_objs if o.name.startswith("armor_")]
    for o in armor:
        o.hide_render = True
    shot(os.path.join(PREV, "07_damaged_front.png"), cam, lights, (2.6, 3.4, 1.55), tgt, 50, full)
    shot(os.path.join(PREV, "08_damaged_back.png"), cam, lights, (-2.6, -3.4, 1.7), tgt, 50, full)
    shot(os.path.join(PREV, "09_damaged_head.png"), cam, lights, (0.36, 0.86, 1.97), (0.0, 0.1, 1.84), 55, (1200, 900), scale=0.45)
    for o in armor:
        o.hide_render = False
    # combat pose
    E["shoulder_R"].rotation_euler.x = math.radians(25)
    E["torso"].rotation_euler.z = math.radians(20)
    E["hip_L"].rotation_euler.x = math.radians(24)
    E["knee_L"].rotation_euler.x = math.radians(-42)
    E["ankle_L"].rotation_euler.x = math.radians(16)
    bpy.context.view_layer.update()
    shot(os.path.join(PREV, "10_combat_pose.png"), cam, lights, (1.9, 3.7, 1.45), (0, 0.1, 1.1), 50, full)
    shot(os.path.join(PREV, "11_combat_pose_side.png"), cam, lights, (4.4, 1.2, 1.25), (0, 0.1, 1.08), 50, full)
    for nm in ("shoulder_R", "torso", "hip_L", "knee_L", "ankle_L"):
        E[nm].rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    # dark-room readability at 15 m (dim lights, emissives carry it)
    shot(os.path.join(PREV, "12_dark_15m.png"), cam, lights, (1.2, 15.0, 1.6), (0, 0, 1.1), 50, (1280, 720), dim=0.15)
    # flat silhouette (black on white) from the side and front
    sc = bpy.context.scene
    blk = bpy.data.materials.new("sil_black")
    bb = next(n for n in blk.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bb.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bb.inputs["Roughness"].default_value = 1.0
    bb.inputs["Specular IOR Level"].default_value = 0.0
    sc.view_layers[0].material_override = blk
    floor.hide_render = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (1, 1, 1, 1)
    vt = sc.view_settings.view_transform
    sc.view_settings.view_transform = "Standard"
    for lo in lights.values():
        lo.hide_render = True
    shot(os.path.join(PREV, "13_silhouette_side.png"), cam, lights, (4.6, 0.0, 1.15), tgt, 50, full)
    shot(os.path.join(PREV, "14_silhouette_front.png"), cam, lights, (0.0, 4.6, 1.15), tgt, 50, full)
    sc.view_layers[0].material_override = None
    sc.view_settings.view_transform = vt
    floor.hide_render = False
    bg.inputs[0].default_value = (0.0025, 0.0028, 0.0035, 1)
    for lo in lights.values():
        lo.hide_render = False


# =================================================================== MAIN
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(OUT, exist_ok=True)
    for m in MATS:
        get_mat(m)
    build_empties()
    build_pelvis()
    build_waist()
    build_chest()
    build_core()
    n0, c0 = len(REG), len(CUTTERS)
    build_head()
    for ob, _ in REG[n0:]:  # head housing sits low and forward between the shoulders
        ob.location += HEAD_OFF
    for c in CUTTERS[c0:]:
        c.location += HEAD_OFF
    for s in (1, -1):
        build_arm(s)
    build_projector()
    build_claw_arm()
    for s in (1, -1):
        build_leg(s)
    build_cables()
    print("built", len(REG), "mesh objects", round(time.time() - T0, 1), "s")

    apply_geometry_mods()
    objs = [o for o, _ in REG]
    print("modifiers applied", round(time.time() - T0, 1), "s")
    smart_uv(objs)
    print("uv done", round(time.time() - T0, 1), "s")
    shade(objs)
    parent_all()

    # ---- validation
    bpy.context.view_layer.update()
    tris = tri_count(objs)
    mn, mxv = world_bounds(objs)
    joints = {n: [round(c, 4) for c in E[n].matrix_world.translation] for n, _, _ in JOINTS}
    for n, _, loc in JOINTS:
        assert (E[n].matrix_world.translation - V(loc)).length < 1e-6, n
    armor = {}
    for o in objs:
        if o.name.startswith("armor_"):
            zone = o.name[len("armor_"):].rsplit("_", 1)[0]
            armor.setdefault(zone, []).append(o.name)
    internal = {}
    for o in objs:
        if o.name.startswith("internal_"):
            zone = next((z for z in armor if o.name.startswith("internal_" + z + "_")), "?")
            internal.setdefault(zone, []).append(o.name)
    emissive = sorted(o.name for o in objs if any(m and m.name in EMISSIVE for m in o.data.materials))
    unparented = [o.name for o in objs if o.parent is None]
    mats_used = sorted({m.name for o in objs for m in o.data.materials if m})
    report = {
        "triangles": tris, "mesh_objects": len(objs),
        "bounds_min": [round(c, 3) for c in mn], "bounds_max": [round(c, 3) for c in mxv],
        "height": round(mxv.z - mn.z, 3), "width": round(mxv.x - mn.x, 3), "depth": round(mxv.y - mn.y, 3),
        "joints": joints, "armor": {k: sorted(v) for k, v in sorted(armor.items())},
        "internal": {k: sorted(v) for k, v in sorted(internal.items())},
        "emissive": emissive, "materials": mats_used, "unparented": unparented,
        "parents": {o.name: o.parent.name for o in objs},
    }
    for o in objs:
        if o.name.startswith("armor_"):
            c = sum((V(b) for b in o.bound_box), V()) / 8
            assert c.length < 1e-4, ("armor origin not centred", o.name, c)
    def group_bounds(pred):
        g = [o for o in objs if pred(o)]
        a, b = world_bounds(g)
        return {"min": [round(c, 3) for c in a], "max": [round(c, 3) for c in b],
                "centre": [round((x + y) / 2, 3) for x, y in zip(a, b)], "size": [round(y - x, 3) for x, y in zip(a, b)]}
    report["head_bounds"] = group_bounds(lambda o: o.parent.name == "head" and not o.name.startswith(("head_antenna", "head_sensor_mast", "led_head", "head_cable", "head_neck")))
    report["core_stack_bounds"] = group_bounds(lambda o: o.parent.name == "core" and o.name.startswith(("core_glow", "core_coil", "core_insulators", "core_electrodes")))
    with open(os.path.join(OUT, "teslabot_report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print("TRIANGLES", tris, "OBJECTS", len(objs), "HEIGHT", report["height"], "WIDTH", report["width"], "DEPTH", report["depth"])
    print("ARMOR", json.dumps(report["armor"]))
    print("EMISSIVE", emissive)
    print("UNPARENTED", unparented)
    print("HEAD", report["head_bounds"])
    print("CORE", report["core_stack_bounds"])

    # ---- export (rest pose, before any preview objects exist)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    glb = os.path.join(OUT, "teslabot.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True, export_yup=True)
    print("exported", glb, round(time.time() - T0, 1), "s")
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backups in staging
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "teslabot_m2.blend"), compress=True)

    if not NO_RENDER:
        render_previews(objs)
    print("DONE", round(time.time() - T0, 1), "s")


main()
