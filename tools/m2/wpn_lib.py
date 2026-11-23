# M2 shared helpers: materials, bmesh builders, booleans, bevel/normal finishing,
# joining, UVs, empties, glTF export. Imported by tools/m2/weapons.py.
# Blender coords: X right, +Y forward (barrel), Z up, metres.
import bpy, bmesh, math, os, re, json, struct
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

V = Vector
X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))

MATS = {
    # name: (base rgb (linear), metallic, roughness, emission rgb, emission strength)
    "gunmetal": ((0.045, 0.047, 0.05), 1.0, 0.36, None, 0),
    "anodized": ((0.032, 0.034, 0.036), 0.85, 0.46, None, 0),
    "polymer": ((0.026, 0.026, 0.025), 0.0, 0.64, None, 0),
    "polymer_tan": ((0.30, 0.25, 0.17), 0.0, 0.62, None, 0),
    "rubber": ((0.016, 0.016, 0.016), 0.0, 0.86, None, 0),
    "steel": ((0.52, 0.52, 0.53), 1.0, 0.3, None, 0),
    "copper": ((0.72, 0.42, 0.2), 1.0, 0.3, None, 0),
    "glass_lens": ((0.04, 0.07, 0.065), 0.3, 0.04, None, 0),
    "fabric_jacket": ((0.056, 0.060, 0.046), 0.0, 0.86, None, 0),
    "glove": ((0.036, 0.036, 0.038), 0.0, 0.74, None, 0),
    "glove_palm": ((0.017, 0.0155, 0.014), 0.0, 0.52, None, 0),
    "watch": ((0.012, 0.012, 0.012), 0.3, 0.38, None, 0),
    "tritium": ((0.35, 1.0, 0.4), 0.0, 0.3, (0.35, 1.0, 0.42), 3.0),
}


def mat(name):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    base, metal, rough, em, ems = MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if em:
        for key in ("Emission Color", "Emission"):
            if key in b.inputs:
                b.inputs[key].default_value = (*em, 1)
                break
        b.inputs["Emission Strength"].default_value = ems
    m.diffuse_color = (*base, 1)
    return m


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def link(o, coll=None):
    (coll or bpy.context.scene.collection).objects.link(o)
    return o


# ------------------------------------------------------------------ 2D profiles
def circle2(r, n, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


def rrect(w, h, r, seg=3, cx=0.0, cy=0.0, rs=None):
    """Rounded rectangle, CCW. rs = per-corner radii (top-right, top-left, bottom-left, bottom-right)."""
    rs = rs or (r, r, r, r)
    hw, hh = w / 2, h / 2
    corners = [(hw, hh, 0), (-hw, hh, 90), (-hw, -hh, 180), (hw, -hh, 270)]
    pts = []
    for (x, y, a), rr in zip(corners, rs):
        rr = min(rr, hw, hh)
        if rr <= 1e-7:
            pts.append((cx + x, cy + y))
            continue
        ccx = x - math.copysign(rr, x)
        ccy = y - math.copysign(rr, y)
        for k in range(seg + 1):
            t = math.radians(a + 90 * k / seg)
            pts.append((cx + ccx + rr * math.cos(t), cy + ccy + rr * math.sin(t)))
    return pts


def stadium(L, W, seg=4, cx=0.0, cy=0.0):
    """Slot outline, long axis along the first coordinate."""
    r = W / 2
    pts = []
    for k in range(seg + 1):
        t = -math.pi / 2 + math.pi * k / seg
        pts.append((cx + (L / 2 - r) + r * math.cos(t), cy + r * math.sin(t)))
    for k in range(seg + 1):
        t = math.pi / 2 + math.pi * k / seg
        pts.append((cx - (L / 2 - r) + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def ngon2(r, n, a0=0.0, cx=0.0, cy=0.0):
    return circle2(r, n, cx, cy, a0)


# profile axes: (U, V, A): profile (u, v) lives in the U/V plane, extrusion along A
AX = {"X": (Y, Z, X), "Y": (X, Z, Y), "Z": (X, Y, Z)}


def perp_basis(a):
    a = V(a).normalized()
    ref = Z if abs(a.z) < 0.9 else X
    u = a.cross(ref).normalized()
    w = a.cross(u).normalized()
    return u, w


class MB:
    """Small bmesh builder. All coordinates are final object-space coordinates."""

    def __init__(self):
        self.bm = bmesh.new()

    def v(self, p):
        return self.bm.verts.new(V(p))

    def face(self, vs, mat_index=0):
        try:
            f = self.bm.faces.new(vs)
            f.material_index = mat_index
            return f
        except ValueError:
            return None

    def prism(self, poly, axis="Y", a0=0.0, a1=0.1, off=(0, 0, 0), basis=None, mi=0):
        U, Vv, A = basis if basis else AX[axis]
        o = V(off)
        b = [self.v(o + U * p[0] + Vv * p[1] + A * a0) for p in poly]
        t = [self.v(o + U * p[0] + Vv * p[1] + A * a1) for p in poly]
        self.face(b[::-1], mi)
        self.face(t, mi)
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            self.face((b[i], b[j], t[j], t[i]), mi)
        return self

    def tube(self, outer, inner, axis="Y", a0=0.0, a1=0.1, off=(0, 0, 0), mi=0):
        U, Vv, A = AX[axis]
        o = V(off)
        rings = []
        for prof, a in ((outer, a0), (outer, a1), (inner, a1), (inner, a0)):
            rings.append([self.v(o + U * p[0] + Vv * p[1] + A * a) for p in prof])
        n = len(outer)
        for k in range(4):
            r0, r1 = rings[k], rings[(k + 1) % 4]
            for i in range(n):
                j = (i + 1) % n
                self.face((r0[i], r0[j], r1[j], r1[i]), mi)
        return self

    def lathe(self, prof, axis="Y", n=24, off=(0, 0, 0), phase=0.0, mi=0, cap0=True, cap1=True, axis_vec=None):
        """Revolve [(r, a)] around an axis through off. r == 0 makes a pole."""
        if axis_vec is not None:
            A = V(axis_vec).normalized()
            U, W = perp_basis(A)
        else:
            U, W, A = AX[axis]
        o = V(off)
        rings = []
        for r, a in prof:
            if r < 1e-8:
                rings.append([self.v(o + A * a)])
            else:
                rings.append([self.v(o + A * a + (U * math.cos(phase + 2 * math.pi * i / n) + W * math.sin(phase + 2 * math.pi * i / n)) * r) for i in range(n)])
        for k in range(len(rings) - 1):
            ra, rb = rings[k], rings[k + 1]
            if len(ra) == 1 and len(rb) == 1:
                continue
            if len(ra) == 1:
                for i in range(n):
                    self.face((ra[0], rb[i], rb[(i + 1) % n]), mi)
            elif len(rb) == 1:
                for i in range(n):
                    self.face((ra[i], ra[(i + 1) % n], rb[0]), mi)
            else:
                for i in range(n):
                    j = (i + 1) % n
                    self.face((ra[i], ra[j], rb[j], rb[i]), mi)
        if cap0 and len(rings[0]) > 1:
            self.face(rings[0][::-1], mi)
        if cap1 and len(rings[-1]) > 1:
            self.face(rings[-1], mi)
        return self

    def loft(self, rings, cap0=True, cap1=True, mi=0, mis=None):
        vs = [[self.v(p) for p in ring] for ring in rings]
        n = len(rings[0])
        for k in range(len(vs) - 1):
            for i in range(n):
                j = (i + 1) % n
                self.face((vs[k][i], vs[k][j], vs[k + 1][j], vs[k + 1][i]), mis[k][i] if mis else mi)
        if cap0:
            self.face(vs[0][::-1], mi)
        if cap1:
            self.face(vs[-1], mi)
        return vs

    def box(self, c, size, rot=None, mi=0):
        c = V(c)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        R = rot.to_matrix() if hasattr(rot, "to_matrix") else (rot if rot is not None else Matrix.Identity(3))
        pts = [c + R @ V((sx * hx, sy * hy, sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        vs = [self.v(p) for p in pts]
        idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for f in idx:
            self.face([vs[i] for i in f], mi)
        return self

    def box_mm(self, lo, hi, mi=0):
        lo, hi = V(lo), V(hi)
        return self.box((lo + hi) / 2, hi - lo, mi=mi)

    def cyl(self, c, r, depth, axis="Y", n=24, r2=None, mi=0):
        U, W, A = AX[axis]
        r2 = r if r2 is None else r2
        return self.lathe([(r, -depth / 2), (r2, depth / 2)], axis, n, c, mi=mi)

    def cyl_between(self, a, b, r, n=16, r2=None, mi=0):
        a, b = V(a), V(b)
        d = b - a
        r2 = r if r2 is None else r2
        return self.lathe([(r, 0.0), (r2, d.length)], n=n, off=a, axis_vec=d, mi=mi)

    def obj(self, name, material=None, mats=None):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-7)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        o = bpy.data.objects.new(name, me)
        link(o)
        for m in (mats or ([material] if material else [])):
            me.materials.append(mat(m))
        return o


# ------------------------------------------------------------------ object ops
def apply_mods(o):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, preserve_all_data_layers=True, depsgraph=dg)
    old = o.data
    nm = old.name
    o.modifiers.clear()
    o.data = me
    bpy.data.meshes.remove(old)
    me.name = nm
    return o


def delete(o):
    me = o.data if o.type == "MESH" else None
    bpy.data.objects.remove(o, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def _bbox(o):
    if not o.data.vertices:
        return None
    xs = [v.co for v in o.data.vertices]
    return (V((min(p.x for p in xs), min(p.y for p in xs), min(p.z for p in xs))),
            V((max(p.x for p in xs), max(p.y for p in xs), max(p.z for p in xs))))


def _sane(o, ref_lo, ref_hi, tol=0.002):
    bb = _bbox(o)
    if bb is None or not o.data.polygons:
        return False
    lo, hi = bb
    return all(lo[i] >= ref_lo[i] - tol and hi[i] <= ref_hi[i] + tol for i in range(3))


BOOL_LOG = []


def boolean(target, cutter, op="DIFFERENCE", solver="EXACT", self_inter=True):
    """Apply a boolean immediately. Falls back to other solvers if the result is empty or explodes."""
    if cutter is None:
        return target
    if isinstance(cutter, MB):
        if len(cutter.bm.verts) == 0:
            cutter.bm.free()
            return target
        cutter = cutter.obj("_cutter")
    lo, hi = _bbox(target)
    if op == "UNION":
        clo, chi = _bbox(cutter)
        lo = V((min(lo[i], clo[i]) for i in range(3)))
        hi = V((max(hi[i], chi[i]) for i in range(3)))
    backup = target.data.copy()
    ok = False
    for sv in [solver] + [s for s in ("EXACT", "MANIFOLD", "FLOAT") if s != solver]:
        md = target.modifiers.new("bool", "BOOLEAN")
        md.operation = op
        md.solver = sv
        md.object = cutter
        if sv == "EXACT":
            md.use_self = self_inter
        try:
            apply_mods(target)
        except Exception as e:
            print("boolean error", target.name, sv, e)
            target.modifiers.clear()
        if _sane(target, lo, hi):
            ok = True
            if sv != solver:
                BOOL_LOG.append((target.name, sv))
            break
        old = target.data
        target.data = backup.copy()
        bpy.data.meshes.remove(old)
    if not ok:
        BOOL_LOG.append((target.name, "FAILED"))
        print("WARNING boolean failed on", target.name)
    bpy.data.meshes.remove(backup)
    delete(cutter)
    return target


def union_parts(base, extra, solver="EXACT"):
    return boolean(base, extra, "UNION", solver, self_inter=True)


def sharp_by_angle(o, angle=30.0):
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < lim
        else:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()


def finish(o, bevel=0.0006, segs=2, angle=30.0, wn=True, profile=0.5, clamp=True):
    """Angle-limited bevel (harden normals) + weighted normals, applied. Retries smaller if it explodes."""
    sharp_by_angle(o, angle)
    lo, hi = _bbox(o)
    backup = o.data.copy()
    for w in (bevel, bevel * 0.5, 0.0):
        if w > 0:
            md = o.modifiers.new("bevel", "BEVEL")
            md.width = w
            md.segments = segs
            md.limit_method = "ANGLE"
            md.angle_limit = math.radians(angle)
            md.use_clamp_overlap = clamp
            md.harden_normals = True
            md.profile = profile
            md.miter_outer = "MITER_ARC"
        if wn:
            md = o.modifiers.new("wn", "WEIGHTED_NORMAL")
            md.keep_sharp = True
            md.mode = "FACE_AREA"
            md.weight = 50
        apply_mods(o)
        if _sane(o, lo, hi, 0.0005):
            break
        print("WARNING bevel exploded on", o.name, "width", w)
        old = o.data
        o.data = backup.copy()
        bpy.data.meshes.remove(old)
    bpy.data.meshes.remove(backup)
    return o


def smooth_all(o):
    for p in o.data.polygons:
        p.use_smooth = True


def subsurf(o, levels=2, crease=True):
    md = o.modifiers.new("subd", "SUBSURF")
    md.levels = levels
    md.render_levels = levels
    md.use_creases = crease
    md.boundary_smooth = "ALL"
    apply_mods(o)
    smooth_all(o)
    return o


def xform(o, M):
    o.data.transform(M)
    o.data.update()
    return o


def rot_about(o, pivot, axis, deg):
    p = V(pivot)
    M = Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p)
    return xform(o, M)


def set_origin(o, p):
    """Mesh built in final coordinates -> move the object origin to p without moving geometry."""
    p = V(p)
    o.data.transform(Matrix.Translation(-p))
    o.matrix_world = Matrix.Translation(p)
    return o


def join(objs, name=None):
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    o = objs[0]
    if name:
        o.name = name
        o.data.name = name
    return o


def empty(name, M=None, parent=None, size=0.02, loc=None):
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = size
    o.empty_display_type = "ARROWS"
    link(o)
    if loc is not None:
        M = Matrix.Translation(V(loc))
    if M is not None:
        o.matrix_world = M
    if parent is not None:
        set_parent(o, parent)
    return o


def set_parent(child, parent):
    # Lesson from M1: update the view layer before reading matrix_world, or empties export at the origin.
    bpy.context.view_layer.update()
    m = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = m
    bpy.context.view_layer.update()


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons) if o.type == "MESH" else 0


def smart_uv(objs):
    meshes = [o for o in objs if o.type == "MESH" and len(o.data.polygons)]
    if not meshes:
        return
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.003, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in meshes:
        o.select_set(False)


def export_glb(path, fix_names=()):
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True, export_yup=True)
    if fix_names:
        fix_glb_names(path, set(fix_names))
    print("exported", path)


def fix_glb_names(path, bases):
    """Blender forces unique object names (eye, eye.001...). glTF and Godot allow equal names under
    different parents, so strip the numeric suffix from the listed node names."""
    data = open(path, "rb").read()
    magic, ver, length = struct.unpack_from("<III", data, 0)
    off = 12
    chunks = []
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        off += 8
        chunks.append([ctype, data[off:off + clen]])
        off += clen
    js = json.loads(chunks[0][1].decode("utf-8"))
    for n in js.get("nodes", []):
        m = re.match(r"^(.*)\.\d{3}$", n.get("name", ""))
        if m and m.group(1) in bases:
            n["name"] = m.group(1)
    raw = json.dumps(js, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    chunks[0][1] = raw
    body = b"".join(struct.pack("<II", len(c[1]), c[0]) + c[1] for c in chunks)
    open(path, "wb").write(struct.pack("<III", magic, ver, 12 + len(body)) + body)


def frame_matrix(point, u, v):
    """Right-handed frame with columns (u, v, a=u x v) at point."""
    u = V(u).normalized()
    v = V(v)
    v = (v - u * v.dot(u)).normalized()
    a = u.cross(v)
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = u[i], v[i], a[i], point[i]
    return M


MIRROR_X = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))


def bvh_of(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t
