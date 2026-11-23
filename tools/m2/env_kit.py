# BREACH M2 environment builder (Blender 5.3, headless). Modes:
#   blender -b --factory-startup -P tools/m2/env_kit.py -- build   <out_dir>          -> env_kit.glb, props.glb, kit_stats.json
#   blender -b --factory-startup -P tools/m2/env_kit.py -- convert <polyhaven_dir>    -> <id>/<id>.glb + stats.json
#   blender -b --factory-startup -P tools/m2/env_kit.py -- sheet   <glb> <out.png> <cols>
#   blender -b --factory-startup -P tools/m2/env_kit.py -- row     <glb> <out.png>
#   blender -b --factory-startup -P tools/m2/env_kit.py -- phsheet <polyhaven_dir> <out.png> <cols> [ids...]
# Blender axes: X right, +Y forward (Godot -Z), Z up, metres. "Front faces -Y" = the side a viewer at -Y sees.
# Material names are contract names; the game remaps them to textured materials by name.
import bpy, bmesh, math, os, sys, json, struct, tempfile, shutil
from mathutils import Vector, Matrix, Euler

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

MATS = {
    # name: (base rgb, metallic, roughness, emission rgb, emission strength)
    "concrete": ((0.50, 0.49, 0.46), 0.0, 0.88, None, 0),
    "painted_grey": ((0.40, 0.41, 0.41), 0.25, 0.55, None, 0),
    "painted_dark": ((0.075, 0.08, 0.085), 0.25, 0.55, None, 0),
    "steel": ((0.62, 0.62, 0.63), 1.0, 0.32, None, 0),
    "galvanized": ((0.58, 0.60, 0.61), 1.0, 0.48, None, 0),
    "door_steel": ((0.27, 0.29, 0.29), 0.7, 0.5, None, 0),
    "rubber": ((0.02, 0.02, 0.02), 0.0, 0.85, None, 0),
    "hazard": ((0.78, 0.56, 0.05), 0.1, 0.55, None, 0),
    "crate_green": ((0.13, 0.17, 0.12), 0.3, 0.6, None, 0),
    "robot_dark": ((0.06, 0.062, 0.066), 0.9, 0.42, None, 0),
    "copper": ((0.78, 0.40, 0.22), 1.0, 0.3, None, 0),
    "glass_lens": ((0.05, 0.08, 0.07), 0.2, 0.05, None, 0),
    "screen": ((0.02, 0.05, 0.05), 0.0, 0.2, (0.25, 0.7, 0.6), 1.5),
    "lamp_warm": ((1.0, 0.82, 0.6), 0.0, 0.4, (1.0, 0.72, 0.42), 6.0),
    "lamp_cool": ((0.9, 0.95, 1.0), 0.0, 0.4, (0.85, 0.92, 1.0), 6.0),
    "led_amber": ((1.0, 0.6, 0.1), 0.0, 0.4, (1.0, 0.55, 0.1), 5.0),
    "led_red": ((1.0, 0.1, 0.05), 0.0, 0.4, (1.0, 0.08, 0.04), 5.0),
    "led_green": ((0.2, 1.0, 0.35), 0.0, 0.4, (0.15, 1.0, 0.3), 5.0),
    "cable_black": ((0.022, 0.022, 0.024), 0.0, 0.6, None, 0),
}

CUR = []       # parts of the asset being built
CUTTERS = []   # boolean cutter objects (deleted after modifiers are applied)
STATS = {}


def mat(name):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    base, metal, rough, em, ems = MATS[name]
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*base, 1)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if em:
        b.inputs["Emission Color"].default_value = (*em, 1)
        b.inputs["Emission Strength"].default_value = ems
    if name == "glass_lens":
        b.inputs["Alpha"].default_value = 0.45
    return m


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    CUR.clear()
    CUTTERS.clear()


# ---------------------------------------------------------------- math helpers
def R(rot):
    return Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()


def M(loc=(0, 0, 0), rot=(0, 0, 0)):
    return Matrix.Translation(Vector(loc)) @ R(rot)


AX = {"X": (0, 90, 0), "Y": (90, 0, 0), "Z": (0, 0, 0)}
DIRS = {"x": (1, 0, 0), "-x": (-1, 0, 0), "y": (0, 1, 0), "-y": (0, -1, 0), "z": (0, 0, 1), "-z": (0, 0, -1)}


def _xf(bm, vs, mtx):
    bmesh.ops.transform(bm, matrix=mtx, verts=list(vs))


def _faces_of(vs):
    s = set()
    for v in vs:
        s.update(v.link_faces)
    return s


def _dir_faces(bm, d):
    v = Vector(DIRS[d])
    return [f for f in bm.faces if f.normal.dot(v) > 0.99]


def _detail(bm, grooves=(), recess=()):
    """grooves: (dir, border, width, depth) V-groove panel line; recess: (dir, border, depth) stepped panel (depth<0 raises)."""
    bm.normal_update()
    jobs = [("g", f, g) for g in grooves for f in _dir_faces(bm, g[0])]
    jobs += [("r", f, r) for r in recess for f in _dir_faces(bm, r[0])]
    for kind, f, p in jobs:
        if kind == "g":
            _, border, width, depth = p
            bmesh.ops.inset_individual(bm, faces=[f], thickness=border, depth=0.0, use_even_offset=True)
            bmesh.ops.inset_individual(bm, faces=[f], thickness=width, depth=-depth, use_even_offset=True)
            bmesh.ops.inset_individual(bm, faces=[f], thickness=0.0, depth=depth, use_even_offset=True)
        else:
            _, border, depth = p
            bmesh.ops.inset_individual(bm, faces=[f], thickness=border, depth=0.0, use_even_offset=True)
            bmesh.ops.inset_individual(bm, faces=[f], thickness=0.0, depth=-depth, use_even_offset=True)


# ---------------------------------------------------------------- bmesh primitives (add into a bm)
def add_box(bm, loc, size, rot=(0, 0, 0), pre=None):
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
    _xf(bm, vs, (pre or Matrix()) @ M(loc, rot))
    for f in _faces_of(vs):
        f.smooth = False
    return vs


def add_cyl(bm, loc, r, depth, axis="Z", verts=16, r2=None, rot=(0, 0, 0), cap=True, pre=None):
    vs = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts, radius1=r,
                               radius2=r if r2 is None else r2, depth=depth)["verts"]
    _xf(bm, vs, (pre or Matrix()) @ M(loc, rot) @ R(AX[axis]))
    for f in _faces_of(vs):
        f.smooth = len(f.verts) == 4 and verts > 6
    return vs


def add_revolve(bm, prof, verts=24, closed=True, smooth=None, cap_ends=False, loc=(0, 0, 0), axis="Z", rot=(0, 0, 0), pre=None):
    rings = []
    for (r, z) in prof:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / verts), r * math.sin(2 * math.pi * k / verts), z)) for k in range(verts)])
    n = len(prof)
    for i in range(n if closed else n - 1):
        i2 = (i + 1) % n
        for k in range(verts):
            k2 = (k + 1) % verts
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i2][k2], rings[i2][k]))
            f.smooth = True if smooth is None else smooth[i]
    if cap_ends and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    vs = [v for ring in rings for v in ring]
    _xf(bm, vs, (pre or Matrix()) @ M(loc, rot) @ R(AX[axis]))
    return vs


def add_ring(bm, loc, ri, ro, depth, axis="Z", verts=24, rot=(0, 0, 0), pre=None):
    prof = [(ri, -depth / 2), (ro, -depth / 2), (ro, depth / 2), (ri, depth / 2)]
    return add_revolve(bm, prof, verts, True, [False, True, False, True], loc=loc, axis=axis, rot=rot, pre=pre)


def add_torus(bm, loc, Rm, r, axis="Z", seg=24, mseg=8, rot=(0, 0, 0), arc=None, pre=None):
    closed = arc is None
    arc = arc or 2 * math.pi
    n = seg if closed else seg + 1
    rings = []
    for i in range(n):
        a = arc * i / seg
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for j in range(mseg):
            b = 2 * math.pi * j / mseg
            rr = Rm + r * math.cos(b)
            ring.append(bm.verts.new((rr * ca, rr * sa, r * math.sin(b))))
        rings.append(ring)
    for i in range(n if closed else n - 1):
        i2 = (i + 1) % n
        for j in range(mseg):
            j2 = (j + 1) % mseg
            f = bm.faces.new((rings[i][j], rings[i2][j], rings[i2][j2], rings[i][j2]))
            f.smooth = True
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    vs = [v for ring in rings for v in ring]
    _xf(bm, vs, (pre or Matrix()) @ M(loc, rot) @ R(AX[axis]))
    return vs


def fillet(pts, radius, n=4):
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = (p0 - p1).normalized(), (p2 - p1).normalized()
        ang = d1.angle(d2)
        if ang > math.pi - 1e-3:
            out.append(p1)
            continue
        t = min(radius / math.tan(ang / 2), (p0 - p1).length * 0.49, (p2 - p1).length * 0.49)
        a, b = p1 + d1 * t, p1 + d2 * t
        for k in range(n + 1):
            s = k / n
            out.append((1 - s) ** 2 * a + 2 * (1 - s) * s * p1 + s * s * b)
    out.append(pts[-1])
    return out


def add_tube(bm, pts, r, segs=8, caps=True):
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rings, prev = [], None
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        t.normalize()
        if prev is None:
            a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            nr = t.cross(a).normalized()
        else:
            nr = prev - t * prev.dot(t)
            nr = nr.normalized() if nr.length > 1e-6 else t.orthogonal().normalized()
        prev = nr
        bn = t.cross(nr)
        rings.append([bm.verts.new(pts[i] + (nr * math.cos(2 * math.pi * k / segs) + bn * math.sin(2 * math.pi * k / segs)) * r) for k in range(segs)])
    for i in range(n - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            f.smooth = True
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return [v for ring in rings for v in ring]


def add_prism(bm, poly, frame, w0, w1):
    O, U, V, N = [Vector(x) for x in frame]
    bot = [bm.verts.new(O + U * u + V * v + N * w0) for u, v in poly]
    top = [bm.verts.new(O + U * u + V * v + N * w1) for u, v in poly]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for i in range(len(poly)):
        j = (i + 1) % len(poly)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    return bot + top


def clip_poly(poly, u0, u1, v0, v1):
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(inter(a, b))
                out.append(b)
            elif ia:
                out.append(inter(a, b))
        return out

    def ix(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))

    def iy(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y)

    p = list(poly)
    for inside, inter in ((lambda q: q[0] >= u0, ix(u0)), (lambda q: q[0] <= u1, ix(u1)),
                          (lambda q: q[1] >= v0, iy(v0)), (lambda q: q[1] <= v1, iy(v1))):
        if not p:
            break
        p = clip(p, inside, inter)
    return p


def poly_area(p):
    return 0.5 * abs(sum(p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1] for i in range(len(p))))


def rounded_rect(w, h, r, n=4):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ---------------------------------------------------------------- objects
def obj(name, m, bm, bevel=0.0, segs=2, angle=30, recalc=True):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bevel > 0:
        for f in bm.faces:
            f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(mat(m))
    o["bev"], o["segs"], o["bang"] = bevel, segs, angle
    CUR.append(o)
    return o


def box(name, loc, size, m, bevel=0.003, rot=(0, 0, 0), segs=2, grooves=(), recess=(), angle=30, pre=None):
    bm = bmesh.new()
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
    _detail(bm, grooves, recess)
    _xf(bm, bm.verts, (pre or Matrix()) @ M(loc, rot))
    for f in bm.faces:
        f.smooth = False
    return obj(name, m, bm, bevel, segs, angle)


def cyl(name, loc, r, depth, m, axis="Z", verts=24, bevel=0.0, r2=None, rot=(0, 0, 0), segs=2, cap=True, pre=None, angle=30):
    bm = bmesh.new()
    add_cyl(bm, loc, r, depth, axis, verts, r2, rot, cap, pre)
    return obj(name, m, bm, bevel, segs, angle)


def torus(name, loc, Rm, r, m, axis="Z", seg=24, mseg=8, rot=(0, 0, 0), arc=None, pre=None):
    bm = bmesh.new()
    add_torus(bm, loc, Rm, r, axis, seg, mseg, rot, arc, pre)
    return obj(name, m, bm)


def tube(name, pts, r, m, segs=8, caps=True):
    bm = bmesh.new()
    add_tube(bm, pts, r, segs, caps)
    return obj(name, m, bm)


def prism(name, poly, frame, w0, w1, m, bevel=0.0, segs=2, angle=30):
    bm = bmesh.new()
    add_prism(bm, poly, frame, w0, w1)
    return obj(name, m, bm, bevel, segs, angle)


def ring(name, loc, ri, ro, depth, m, axis="Z", verts=24, rot=(0, 0, 0), pre=None):
    bm = bmesh.new()
    add_ring(bm, loc, ri, ro, depth, axis, verts, rot, pre)
    return obj(name, m, bm)


def bolts(name, pts, m="steel", r=0.008, h=0.006, axis="Y", verts=6, rot=(0, 0, 0), dome=False, pre=None):
    """Hex heads (verts=6) or domed screw heads (dome=True) at each point."""
    bm = bmesh.new()
    for p in pts:
        if dome:
            add_cyl(bm, p, r, h, axis, 8, r2=r * 0.55, rot=rot, pre=pre)
        else:
            add_cyl(bm, p, r, h, axis, verts, rot=rot, pre=pre)
    for f in bm.faces:
        f.smooth = False
    return obj(name, m, bm)


def cut(target, build):
    """Boolean DIFFERENCE (exact). build(bm) fills the cutter mesh; applied before the bevel."""
    bm = bmesh.new()
    build(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(target.name + "_cutter")
    bm.to_mesh(me)
    bm.free()
    c = bpy.data.objects.new(target.name + "_cutter", me)
    bpy.context.scene.collection.objects.link(c)
    c.hide_render = True
    md = target.modifiers.new("cut", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.solver = "EXACT"
    md.use_self = True
    md.use_hole_tolerant = True
    md.object = c
    CUTTERS.append(c)
    return c


def hazard_band(name, frame, u0, u1, v0, v1, w0=0.0, w=0.0015, sw=0.07, slant=1.0):
    """Diagonal yellow/black safety stripes clipped to a rectangle in a (O, U, V, N) frame."""
    bmy, bmk = bmesh.new(), bmesh.new()
    h = v1 - v0
    k = math.floor((u0 - h * slant) / sw) - 1
    while k * sw < u1 + sw:
        s = k * sw
        poly = [(s, v0), (s + sw, v0), (s + sw + h * slant, v1), (s + h * slant, v1)]
        c = clip_poly(poly, u0, u1, v0, v1)
        if len(c) >= 3 and poly_area(c) > 1e-7:
            add_prism(bmy if k % 2 == 0 else bmk, c, frame, w0, w0 + w)
        k += 1
    obj(name + "_y", "hazard", bmy)
    obj(name + "_k", "painted_dark", bmk)


def smart_uv(o):
    vl = bpy.context.view_layer
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    vl.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")
    o.select_set(False)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def finish(root_name, offset, keep=(), note=""):
    """Apply booleans+bevels, join everything except the `keep` meshes, smart-UV each mesh, parent under an
    empty named root_name (origin = asset origin), then move the root to its layout offset."""
    vl = bpy.context.view_layer
    for o in CUR:
        if o["bev"] > 0:
            md = o.modifiers.new("bevel", "BEVEL")
            md.width = o["bev"]
            md.segments = o["segs"]
            md.limit_method = "ANGLE"
            md.angle_limit = math.radians(o["bang"])
            md.harden_normals = True
            md.use_clamp_overlap = True
            md.miter_outer = "MITER_ARC"
    bpy.ops.object.select_all(action="DESELECT")
    for o in CUR:
        o.select_set(True)
    vl.objects.active = CUR[0]
    bpy.ops.object.convert(target="MESH")
    for c in CUTTERS:
        bpy.data.objects.remove(c, do_unlink=True)
    CUTTERS.clear()
    kept = [o for o in CUR if o.name in keep]
    missing = set(keep) - {o.name for o in kept}
    if missing:
        raise RuntimeError("named meshes missing: %s" % missing)
    rest = [o for o in CUR if o.name not in keep]
    finals = list(kept)
    if rest:
        bpy.ops.object.select_all(action="DESELECT")
        for o in rest:
            o.select_set(True)
        vl.objects.active = rest[0]
        bpy.ops.object.join()
        body = vl.objects.active
        body.name = root_name + "_body"
        body.data.name = root_name + "_body"
        finals.append(body)
    for o in finals:
        smart_uv(o)
    root = bpy.data.objects.new(root_name, None)
    root.empty_display_size = 0.1
    bpy.context.scene.collection.objects.link(root)
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in finals:
        o.parent = root
        for v in o.data.vertices:
            lo = Vector(map(min, lo, v.co))
            hi = Vector(map(max, hi, v.co))
    root.location = offset
    bpy.context.view_layer.update()
    STATS[root_name] = {
        "tris": sum(tris(o) for o in finals),
        "meshes": {o.name: tris(o) for o in finals},
        "bbox_min": [round(x, 4) for x in lo], "bbox_max": [round(x, 4) for x in hi],
        "size": [round(h - l, 4) for l, h in zip(lo, hi)], "note": note,
    }
    print("built %-26s tris %6d size %s" % (root_name, STATS[root_name]["tris"], STATS[root_name]["size"]))
    CUR.clear()
    return root


def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True, export_yup=True,
                              export_animations=False)
    print("exported", path)


# ================================================================= PROPS (replace M1 props.glb)
def p_crate(off):
    # Military equipment case, origin bottom centre, 1.2 x 0.8 x 0.8.
    box("cr_base", (0, 0, 0.2925), (1.16, 0.76, 0.525), "crate_green", 0.02, segs=3,
        recess=(("-y", 0.07, 0.008), ("y", 0.07, 0.008), ("x", 0.06, 0.006), ("-x", 0.06, 0.006)))
    box("cr_seal", (0, 0, 0.5625), (1.15, 0.75, 0.016), "rubber", 0.003)
    box("cr_lid", (0, 0, 0.685), (1.16, 0.76, 0.23), "crate_green", 0.02, segs=3,
        recess=(("z", 0.09, 0.01),), grooves=(("-y", 0.05, 0.004, 0.003), ("y", 0.05, 0.004, 0.003)))
    for y in (-0.25, 0.25):
        box("cr_skid", (0, y, 0.015), (1.0, 0.08, 0.03), "rubber", 0.006)
    rv = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.065, 0.735):
                box("cr_corner", (sx * 0.535, sy * 0.335, z), (0.13, 0.13, 0.13), "galvanized", 0.018, segs=3)
                rv += [(sx * 0.535, sy * 0.401, z), (sx * 0.601, sy * 0.335, z)]
    bolts("cr_corner_rivets", [p for p in rv if abs(p[1]) > 0.4], "steel", 0.009, 0.006, "Y", dome=True)
    bolts("cr_corner_rivets_x", [p for p in rv if abs(p[0]) > 0.6], "steel", 0.009, 0.006, "X", dome=True)
    # Front latches straddling the seam
    for x in (-0.33, 0.33):
        box("cr_latch_base", (x, -0.386, 0.50), (0.10, 0.012, 0.09), "steel", 0.003)
        box("cr_latch_lever", (x, -0.397, 0.556), (0.08, 0.012, 0.11), "steel", 0.004)
        box("cr_latch_catch", (x, -0.386, 0.62), (0.07, 0.012, 0.04), "steel", 0.003)
        cyl("cr_latch_pin", (x, -0.398, 0.505), 0.008, 0.094, "steel", "X", 12)
        bolts("cr_latch_rivets", [(x - 0.035, -0.393, 0.475), (x + 0.035, -0.393, 0.475), (x - 0.025, -0.393, 0.63), (x + 0.025, -0.393, 0.63)], "steel", 0.006, 0.004, "Y", dome=True)
    # Rear hinges
    for x in (-0.4, 0.0, 0.4):
        cyl("cr_hinge_knuckle", (x, 0.393, 0.567), 0.014, 0.14, "steel", "X", 16, bevel=0.002)
        box("cr_hinge_leaf_a", (x, 0.386, 0.53), (0.14, 0.008, 0.05), "steel", 0.002)
        box("cr_hinge_leaf_b", (x, 0.386, 0.605), (0.14, 0.008, 0.05), "steel", 0.002)
        bolts("cr_hinge_rivets", [(x + dx, 0.391, z) for dx in (-0.045, 0.045) for z in (0.52, 0.615)], "steel", 0.006, 0.004, "Y", dome=True)
    # Folding side handles
    for sx in (-1, 1):
        x = sx * 0.586
        box("cr_handle_plate", (sx * 0.584, 0, 0.43), (0.008, 0.24, 0.08), "steel", 0.002)
        for y in (-0.09, 0.09):
            cyl("cr_handle_pivot", (sx * 0.591, y, 0.44), 0.013, 0.008, "steel", "X", 12)
        tube("cr_handle_bar", fillet([(sx * 0.592, -0.09, 0.44), (sx * 0.592, -0.09, 0.35), (sx * 0.592, 0.09, 0.35), (sx * 0.592, 0.09, 0.44)], 0.025), 0.007, "steel")
        cyl("cr_handle_grip", (sx * 0.592, 0, 0.35), 0.0095, 0.12, "rubber", "Y", 12, bevel=0.002)
    # Stencil / ID plates and pressure valve
    box("cr_stencil_plate", (0, -0.384, 0.30), (0.34, 0.006, 0.13), "galvanized", 0.002)
    bolts("cr_stencil_rivets", [(sx * 0.155, -0.388, z) for sx in (-1, 1) for z in (0.25, 0.35)], "steel", 0.006, 0.004, "Y", dome=True)
    box("cr_data_plate", (-0.05, -0.383, 0.70), (0.16, 0.005, 0.06), "galvanized", 0.0015)
    cyl("cr_valve", (0.17, -0.388, 0.70), 0.022, 0.014, "painted_dark", "Y", 12, bevel=0.002)
    cyl("cr_valve_cap", (0.17, -0.397, 0.70), 0.012, 0.008, "steel", "Y", 6)
    return finish("crate", off, note="origin bottom centre")


def p_barrel(off):
    # 200 l steel drum: radius 0.29 (incl. chimes/hoops), height 0.88, origin bottom centre.
    cyl("br_body", (0, 0, 0.435), 0.278, 0.84, "painted_grey", "Z", 48)
    for z in (0.014, 0.866):
        torus("br_chime", (0, 0, z), 0.278, 0.012, "painted_grey", "Z", 48, 8)
    for zc in (0.29, 0.59):
        torus("br_hoop", (0, 0, zc), 0.279, 0.0105, "painted_grey", "Z", 48, 8)
        for dz in (-0.032, 0.032):
            torus("br_swage", (0, 0, zc + dz), 0.277, 0.006, "painted_grey", "Z", 48, 6)
    torus("br_lid_ring", (0, 0, 0.856), 0.2, 0.004, "painted_grey", "Z", 40, 6)
    box("br_seam", (0, 0.2785, 0.44), (0.008, 0.004, 0.82), "painted_grey", 0.0)
    # Bungs
    ring("br_bung_flange", (0.165, 0.0, 0.857), 0.03, 0.042, 0.006, "steel", "Z", 16)
    cyl("br_bung", (0.165, 0.0, 0.863), 0.033, 0.016, "steel", "Z", 8, bevel=0.002)
    bm = bmesh.new()
    add_box(bm, (0.165, 0, 0.874), (0.05, 0.008, 0.008))
    add_box(bm, (0.165, 0, 0.874), (0.008, 0.05, 0.008))
    obj("br_bung_rib", "steel", bm)
    ring("br_vent_flange", (-0.17, 0.03, 0.857), 0.018, 0.027, 0.005, "steel", "Z", 12)
    cyl("br_vent_bung", (-0.17, 0.03, 0.862), 0.02, 0.012, "steel", "Z", 6)
    # Hazard diamond label wrapped onto the drum (front, -Y)
    for nm, d, rad, m in (("br_label_border", 0.096, 0.2788, "painted_dark"), ("br_label", 0.084, 0.2796, "hazard")):
        bm = bmesh.new()
        n = 8
        grid = [[None] * (n + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            for j in range(n + 1):
                a, b = -1 + 2 * i / n, -1 + 2 * j / n
                u, v = (a - b) * d / 2, (a + b) * d / 2
                th = u / rad
                grid[i][j] = bm.verts.new((rad * math.sin(th), -rad * math.cos(th), 0.445 + v))
        for i in range(n):
            for j in range(n):
                bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        if bm.faces[0].normal.y > 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        for f in bm.faces:
            f.smooth = True
        obj(nm, m, bm, recalc=False)
    return finish("barrel", off, note="origin bottom centre")


def p_server_rack(off):
    # 19" network/server cabinet 0.6 W x 1.0 D x 2.0 H, origin bottom centre, front (door) faces -Y.
    box("sr_plinth", (0, 0, 0.04), (0.56, 0.96, 0.08), "robot_dark", 0.004)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("sr_post", (sx * 0.28, sy * 0.48, 1.02), (0.04, 0.04, 1.88), "robot_dark", 0.003, segs=1)
        box("sr_rail_low", (sx * 0.28, 0, 0.1), (0.04, 0.92, 0.04), "robot_dark", 0.003)
    top = box("sr_top", (0, 0, 1.98), (0.6, 1.0, 0.04), "robot_dark", 0.005, segs=1, grooves=(("z", 0.04, 0.004, 0.003),))
    cut(top, lambda bm: add_box(bm, (0, 0.3, 1.98), (0.32, 0.08, 0.1)))
    box("sr_brush", (0, 0.3, 1.975), (0.33, 0.09, 0.02), "rubber", 0.0)
    for sy in (-1, 1):
        box("sr_rail_top", (0, sy * 0.48, 1.94), (0.52, 0.04, 0.04), "robot_dark", 0.003)
    # Side panels (two per side) with vent slots cut in the upper rear
    for sx in (-1, 1):
        for zc in (0.565, 1.495):
            p = box("sr_side", (sx * 0.292, 0, zc), (0.016, 0.92, 0.925), "robot_dark", 0.004, segs=1,
                    grooves=(("x" if sx > 0 else "-x", 0.035, 0.004, 0.002),))
            box("sr_side_latch", (sx * 0.301, 0.0, zc + 0.41), (0.004, 0.08, 0.025), "steel", 0.001)
            if zc > 1:
                cut(p, lambda bm, sx=sx: [add_box(bm, (sx * 0.292, 0.30, 1.30 + i * 0.03), (0.05, 0.22, 0.01)) for i in range(10)])
    # Front perforated door (hinged on the left), frame + lattice
    door = box("sr_door", (0, -0.49, 1.02), (0.56, 0.02, 1.84), "robot_dark", 0.004, segs=1)
    cut(door, lambda bm: add_box(bm, (0, -0.49, 1.02), (0.47, 0.1, 1.70)))
    bm = bmesh.new()
    nx, nz = 26, 92
    for i in range(nx + 1):
        add_box(bm, (-0.235 + 0.47 * i / nx, -0.4885, 1.02), (0.0045, 0.003, 1.70))
    for j in range(nz + 1):
        add_box(bm, (0, -0.4875, 0.17 + 1.70 * j / nz), (0.47, 0.002, 0.0045))
    obj("sr_door_mesh", "robot_dark", bm)
    box("sr_handle_base", (0.2575, -0.503, 1.05), (0.03, 0.008, 0.17), "steel", 0.002)
    box("sr_handle", (0.2575, -0.513, 1.07), (0.022, 0.012, 0.12), "robot_dark", 0.004)
    cyl("sr_lock", (0.2575, -0.509, 0.98), 0.008, 0.012, "steel", "Y", 12)
    for z in (0.3, 1.02, 1.74):
        cyl("sr_hinge", (-0.283, -0.497, z), 0.008, 0.07, "steel", "Z", 12)
    # 19" rails
    for sx in (-1, 1):
        box("sr_19rail", (sx * 0.236, -0.455, 1.02), (0.022, 0.02, 1.8), "galvanized", 0.001)
        box("sr_19rail_r", (sx * 0.236, 0.43, 1.02), (0.022, 0.02, 1.8), "galvanized", 0.001)
    # Equipment
    U = 0.04445
    stack = [("ups", 3), ("blank", 1), ("srv", 2), ("srv", 2), ("srv", 2), ("blank", 1), ("srv", 2), ("srv", 1), ("srv", 1),
             ("blank", 2), ("storage", 3), ("blank", 1), ("switch", 1), ("patch", 1), ("cableman", 1), ("switch", 1), ("patch", 1),
             ("blank", 2), ("srv", 1), ("srv", 1)]
    bg, ba, bdark = bmesh.new(), bmesh.new(), bmesh.new()
    bgrey, bbody, bplate, bsteel = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    screws, psu_pts, data_pts = [], [], []
    z = 0.16
    unit_z = []
    rng = 7
    for kind, h in stack:
        hh = h * U
        zc = z + hh / 2
        if kind != "cableman":
            add_box(bbody, (0, -0.10, zc), (0.44, 0.72, hh - 0.003))
        add_box(bplate if kind in ("srv", "storage", "ups", "switch") else bdark, (0, -0.468, zc), (0.482, 0.006, hh - 0.002))
        screws += [(-0.236, -0.472, zc), (0.236, -0.472, zc)]
        unit_z.append(zc)
        if kind in ("srv", "storage", "ups", "switch"):
            for px in ((0.115, 0.185) if kind != "switch" else (0.185,)):
                add_box(bgrey, (px, 0.262, zc), (0.064, 0.004, hh - 0.008))
                add_box(bsteel, (px - 0.022, 0.268, zc), (0.006, 0.01, min(hh - 0.014, 0.05)))
                add_box(bg, (px + 0.024, 0.2645, zc + hh / 2 - 0.01), (0.004, 0.002, 0.004))
                psu_pts.append((px, zc))
            for q in range(5 if kind != "ups" else 3):
                add_box(bdark, (-0.17 + q * 0.026, 0.2625, zc), (0.016, 0.004, 0.012))
            if kind in ("srv", "storage", "switch"):
                data_pts.append(zc)
        if kind == "srv":
            rows, cols = (2, 6) if h == 2 else (1, 8)
            bw = 0.36 / cols
            for r_ in range(rows):
                for c_ in range(cols):
                    bx = -0.21 + bw * (c_ + 0.5)
                    bz = z + 0.004 + (hh - 0.008) * (r_ + 0.5) / rows
                    add_box(bgrey, (bx, -0.4725, bz), (bw - 0.004, 0.003, (hh - 0.008) / rows - 0.004))
                    rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
                    add_box(ba if rng % 7 == 0 else bg, (bx + bw / 2 - 0.008, -0.4745, bz - (hh - 0.008) / rows / 2 + 0.006), (0.004, 0.002, 0.003))
            add_box(bg, (0.19, -0.4725, zc + 0.008), (0.005, 0.003, 0.005))
            add_box(ba, (0.205, -0.4725, zc + 0.008), (0.005, 0.003, 0.005))
            add_cyl(bdark, (0.2, -0.473, zc - 0.008), 0.005, 0.004, "Y", 10)
        elif kind == "storage":
            for r_ in range(3):
                for c_ in range(4):
                    bx = -0.18 + c_ * 0.105
                    bz = z + 0.022 + r_ * U
                    add_box(bgrey, (bx, -0.4725, bz), (0.098, 0.003, U - 0.006))
                    add_box(bg if (r_ + c_) % 5 else ba, (bx + 0.04, -0.4745, bz), (0.004, 0.002, 0.004))
        elif kind in ("switch", "patch"):
            for r_ in range(2):
                for c_ in range(12):
                    px = -0.17 + c_ * 0.026 + (0.012 if c_ >= 6 else 0)
                    pz = zc + (r_ - 0.5) * 0.016
                    add_box(bdark if kind == "switch" else bgrey, (px, -0.4722, pz), (0.013, 0.003, 0.0105))
                    if kind == "switch":
                        add_box(bg if (c_ + r_) % 3 else ba, (px - 0.004, -0.4738, pz + 0.0065), (0.003, 0.002, 0.002))
            if kind == "switch":
                add_box(bg, (0.2, -0.4725, zc), (0.006, 0.003, 0.006))
        elif kind == "ups":
            add_box(bdark, (0.12, -0.4725, zc + 0.02), (0.07, 0.003, 0.035))
            for i in range(3):
                add_cyl(bgrey, (0.06 + i * 0.022, -0.4725, zc - 0.03), 0.006, 0.004, "Y", 10)
            add_box(bg, (0.2, -0.4725, zc + 0.03), (0.006, 0.003, 0.006))
            add_box(ba, (0.2, -0.4725, zc + 0.015), (0.006, 0.003, 0.006))
            for i in range(9):
                add_box(bdark, (-0.18 + i * 0.022, -0.4722, zc), (0.012, 0.003, 0.09))
        elif kind == "cableman":
            for i in range(5):
                add_torus(bdark, (-0.16 + i * 0.08, -0.48, zc), 0.014, 0.003, "Z", 8, 5, arc=math.pi, rot=(0, 0, 180))
        z += hh
    obj("sr_units_body", "robot_dark", bbody)
    obj("sr_units_plates", "painted_dark", bplate)
    obj("sr_units_dark", "robot_dark", bdark)
    obj("sr_units_bays", "painted_grey", bgrey)
    obj("server_rack_leds_green", "led_green", bg)
    obj("server_rack_leds_amber", "led_amber", ba)
    obj("sr_rear_handles", "steel", bsteel)
    bolts("sr_rack_screws", screws, "steel", 0.0045, 0.004, "Y", 6)
    # Front patch cords between patch panels and switches
    pz = [unit_z[i] for i, (k, _) in enumerate(stack) if k in ("patch", "switch")]
    bm = bmesh.new()
    for i in range(6):
        x0 = -0.17 + i * 0.052
        add_tube(bm, fillet([(x0, -0.474, pz[1]), (x0, -0.485, pz[1] - 0.01), (x0 + 0.01, -0.485, pz[0] + 0.01), (x0 + 0.01, -0.474, pz[0])], 0.008), 0.0025, 6)
    obj("sr_patch_cords", "cable_black", bm)
    # Rear: cable managers, PDU, bundles, lacing bars
    for sx in (-1, 1):
        box("sr_cm_channel", (sx * 0.255, 0.445, 1.03), (0.03, 0.05, 1.76), "painted_dark", 0.002)
        bm = bmesh.new()
        for i in range(22):
            add_box(bm, (sx * 0.233, 0.468, 0.2 + i * 0.08), (0.016, 0.01, 0.03))
        obj("sr_cm_fingers", "painted_dark", bm)
    box("sr_pdu", (0.17, 0.468, 1.0), (0.055, 0.035, 1.5), "painted_dark", 0.003)
    bm = bmesh.new()
    for i in range(16):
        add_box(bm, (0.17, 0.4485, 0.32 + i * 0.09), (0.028, 0.004, 0.022))
    obj("sr_pdu_outlets", "robot_dark", bm)
    box("sr_pdu_display", (0.17, 0.4485, 1.7), (0.03, 0.003, 0.015), "screen", 0.0)
    bm = bmesh.new()
    for k in range(6):
        for sx in (-1, 1):
            xb = sx * 0.2 + ((k % 3) - 1) * 0.013
            yb = 0.425 + (k // 3 - 0.5) * 0.013
            pts = [(xb, yb, 1.99)]
            zz = 1.9
            while zz > 0.25:
                pts.append((xb + 0.004 * math.sin(zz * 9 + k), yb, zz))
                zz -= 0.2
            add_tube(bm, pts, 0.0065 if k < 2 else 0.0045, 6)
    for zc in data_pts:
        for q in range(2):
            x = -0.17 + q * 0.026
            add_tube(bm, fillet([(x, 0.266, zc), (x, 0.31, zc), (-0.2 + q * 0.012, 0.40, zc + 0.01), (-0.2 + q * 0.012, 0.425, zc + 0.07)], 0.025, 2), 0.0035, 6)
    bp = bmesh.new()
    for px, zc in psu_pts:
        oz = min((0.32 + i * 0.09 for i in range(16)), key=lambda q: abs(q - zc))
        add_tube(bp, fillet([(px, 0.266, zc), (px, 0.32, zc), (0.17, 0.41, oz), (0.17, 0.446, oz)], 0.025, 2), 0.004, 6)
        add_box(bp, (0.17, 0.444, oz), (0.02, 0.012, 0.016))
    obj("sr_cables", "cable_black", bm)
    obj("sr_power_cords", "cable_black", bp)
    bm = bmesh.new()
    for sx in (-1, 1):
        for zc in (0.45, 0.85, 1.25, 1.65):
            add_ring(bm, (sx * 0.2, 0.431, zc), 0.022, 0.026, 0.02, "Z", 12)
    obj("sr_velcro", "rubber", bm)
    for zc in (0.6, 1.2, 1.8):
        box("sr_lacing", (-0.05, 0.47, zc), (0.42, 0.006, 0.02), "galvanized", 0.001)
    return finish("server_rack", off, keep=("server_rack_leds_green", "server_rack_leds_amber"),
                  note="origin bottom centre, door faces -Y")


def p_relay_console(off):
    # Relay control desk, operator side -Y, origin bottom centre. Base 1.4 x ~0.73 x 0.9; bezel to ~1.65; relay tower right rear.
    th = math.atan2(0.125, 0.41)
    thd = math.degrees(th)
    A = Vector((0, -0.35, 0.875))
    t = Vector((0, math.cos(th), math.sin(th)))
    n = Vector((0, -math.sin(th), math.cos(th)))

    def S(u, s, h):
        return tuple(A + Vector((u, 0, 0)) + t * s + n * h)

    prof = [(-0.35, 0.10), (0.35, 0.10), (0.35, 1.0), (0.06, 1.0), (-0.35, 0.875)]
    body = prism("rc_body", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -0.7, 0.7, "painted_grey", 0.006, 2)
    box("rc_plinth", (0, 0.03, 0.05), (1.36, 0.62, 0.1), "robot_dark", 0.004)
    # Side covers, rear panel, front doors with louvres
    for sx in (-1, 1):
        box("rc_side_cover", (sx * 0.703, 0.0, 0.48), (0.006, 0.6, 0.66), "painted_grey", 0.002, recess=(("x" if sx > 0 else "-x", 0.03, -0.002),))
        bolts("rc_side_bolts", [(sx * 0.707, y, z) for y in (-0.27, 0.27) for z in (0.18, 0.78)], "steel", 0.006, 0.004, "X", dome=True)
    box("rc_rear_panel", (0, 0.356, 0.55), (1.3, 0.012, 0.8), "painted_grey", 0.003, grooves=(("y", 0.04, 0.004, 0.002),))
    bm = bmesh.new()
    for i in range(8):
        add_box(bm, (0, 0.364, 0.7 + i * 0.025), (0.5, 0.004, 0.012), rot=(-30, 0, 0))
    obj("rc_rear_louvres", "painted_dark", bm)
    for sx in (-1, 1):
        box("rc_door", (sx * 0.335, -0.356, 0.48), (0.63, 0.012, 0.66), "painted_grey", 0.004, recess=(("-y", 0.04, 0.004),))
        cyl("rc_door_latch", (sx * 0.06, -0.366, 0.62), 0.016, 0.012, "steel", "Y", 16, bevel=0.002)
        box("rc_door_latch_lever", (sx * 0.06, -0.375, 0.60), (0.014, 0.01, 0.05), "painted_dark", 0.003)
        box("rc_louvre_back", (sx * 0.335, -0.3605, 0.25), (0.4, 0.002, 0.11), "painted_dark", 0.0)
        bm = bmesh.new()
        for i in range(5):
            add_box(bm, (sx * 0.335, -0.368, 0.205 + i * 0.022), (0.4, 0.004, 0.02), rot=(35, 0, 0))
        obj("rc_louvres", "painted_grey", bm)
    cut(body, lambda bm: [add_box(bm, (sx * 0.335, -0.35, 0.25), (0.4, 0.04, 0.11)) for sx in (-1, 1)])
    cyl("rc_armrest", (0, -0.365, 0.868), 0.026, 1.42, "rubber", "X", 16, bevel=0.004)
    # Sloped control panel
    L = (Vector((0, 0.06, 1.0)) - A).length
    box("rc_panel", S(0, L / 2, 0.006), (1.36, L - 0.03, 0.012), "painted_dark", 0.003, rot=(thd, 0, 0),
        grooves=(("z", 0.025, 0.003, 0.002),))
    # Mimic bus diagram
    bm = bmesh.new()
    add_box(bm, S(-0.4, 0.33, 0.0135), (0.48, 0.006, 0.003), rot=(thd, 0, 0))
    for i in range(5):
        u = -0.6 + i * 0.1
        add_box(bm, S(u, 0.285, 0.0135), (0.006, 0.09, 0.003), rot=(thd, 0, 0))
        add_box(bm, S(u, 0.285, 0.0145), (0.024, 0.024, 0.004), rot=(thd, 0, 0))
    obj("rc_mimic", "painted_grey", bm)
    bmg, bmr, bma = bmesh.new(), bmesh.new(), bmesh.new()
    for i in range(5):
        add_box(bmg if i % 3 else bmr, S(-0.6 + i * 0.1, 0.285, 0.0168), (0.012, 0.012, 0.002), rot=(thd, 0, 0))
    # Toggle switches with label plates
    for i in range(6):
        u = -0.62 + i * 0.075
        cyl("rc_toggle_nut", S(u, 0.13, 0.016), 0.011, 0.008, "steel", "Z", 6, rot=(thd, 0, 0))
        cyl("rc_toggle_lever", S(u, 0.13 + (0.008 if i % 2 else -0.008), 0.032), 0.0028, 0.03, "steel", "Z", 8, rot=(thd + (20 if i % 2 else -20), 0, 0))
        box("rc_toggle_label", S(u, 0.075, 0.013), (0.05, 0.022, 0.002), "galvanized", 0.0, rot=(thd, 0, 0))
    # Key switches
    for u in (-0.12, -0.04):
        cyl("rc_key_body", S(u, 0.13, 0.018), 0.017, 0.012, "steel", "Z", 20, bevel=0.002, rot=(thd, 0, 0))
        box("rc_key_blade", S(u, 0.13, 0.03), (0.004, 0.0025, 0.016), "steel", 0.0, rot=(thd, 0, 0))
        box("rc_key_bow", S(u, 0.13, 0.044), (0.018, 0.003, 0.014), "steel", 0.002, rot=(thd, 0, 0))
    # Rotary selectors
    for i, u in enumerate((0.07, 0.17, 0.27)):
        cyl("rc_knob_skirt", S(u, 0.12, 0.0135), 0.026, 0.003, "galvanized", "Z", 24, rot=(thd, 0, 0))
        cyl("rc_knob", S(u, 0.12, 0.025), 0.018, 0.02, "painted_dark", "Z", 20, bevel=0.002, rot=(thd, 0, 0))
        box("rc_knob_pointer", S(u, 0.12, 0.036), (0.006, 0.03, 0.006), "painted_dark", 0.001, rot=(thd, 0, 35 * (i - 1)))
    # Illuminated pushbuttons
    for i, u in enumerate((0.04, 0.1, 0.16, 0.22, 0.28)):
        cyl("rc_pb_collar", S(u, 0.29, 0.015), 0.014, 0.006, "steel", "Z", 16, rot=(thd, 0, 0))
        add_cyl((bmg, bmr, bma, bmg, bma)[i], S(u, 0.29, 0.023), 0.0105, 0.012, "Z", 16, rot=(thd, 0, 0))
    # Emergency stop
    cyl("rc_estop_collar", S(0.52, 0.2, 0.017), 0.038, 0.01, "hazard", "Z", 24, bevel=0.002, rot=(thd, 0, 0))
    add_cyl(bmr, S(0.52, 0.2, 0.036), 0.029, 0.028, "Z", 24, r2=0.024, rot=(thd, 0, 0))
    # Upright bezel (tilted back 10 deg), screen, gauges, pilot lights
    Mb = Matrix.Translation((0, 0.075, 1.0)) @ R((-10, 0, 0))
    xc = -0.23
    box("rc_bezel", (xc, 0.08, 0.31), (0.94, 0.16, 0.62), "painted_dark", 0.008, pre=Mb, grooves=(("x", 0.03, 0.003, 0.002), ("-x", 0.03, 0.003, 0.002)))
    box("rc_hood", (xc, -0.03, 0.635), (0.97, 0.22, 0.03), "painted_dark", 0.006, pre=Mb)
    for x in (xc - 0.47, xc + 0.47):
        box("rc_hood_cheek", (x, -0.06, 0.6), (0.012, 0.16, 0.07), "painted_dark", 0.003, pre=Mb)
    sb = bmesh.new()
    add_box(sb, (xc, -0.006, 0.36), (0.82, 0.012, 0.03 + 0.40), pre=Mb)
    obj("rc_screen_surround", "robot_dark", sb, 0.003)
    box("screen", (xc, -0.0125, 0.36), (0.78, 0.002, 0.40), "screen", 0.0, pre=Mb)
    bolts("rc_screen_screws", [(xc + sx * 0.395, -0.013, 0.36 + sz * 0.2) for sx in (-1, 1) for sz in (-1, 1)], "steel", 0.006, 0.004, "Y", dome=True, pre=Mb)
    for i in range(3):
        gx = xc - 0.33 + i * 0.13
        cyl("rc_gauge_bezel", (gx, -0.008, 0.085), 0.042, 0.016, "steel", "Y", 24, bevel=0.002, pre=Mb)
        cyl("rc_gauge_face", (gx, -0.0165, 0.085), 0.035, 0.002, "painted_grey", "Y", 24, pre=Mb)
        bm = bmesh.new()
        for k in range(9):
            a = math.radians(-135 + 270 * k / 8)
            add_box(bm, (gx + 0.029 * math.sin(a), -0.018, 0.085 + 0.029 * math.cos(a)), (0.0015, 0.001, 0.006), rot=(0, math.degrees(a), 0), pre=Mb)
        a = math.radians(-60 + 50 * i)
        add_box(bm, (gx + 0.012 * math.sin(a), -0.019, 0.085 + 0.012 * math.cos(a)), (0.002, 0.001, 0.026), rot=(0, math.degrees(a), 0), pre=Mb)
        add_cyl(bm, (gx, -0.019, 0.085), 0.004, 0.002, "Y", 8, pre=Mb)
        obj("rc_gauge_marks", "painted_dark", bm)
    for i in range(5):
        gx = xc + 0.08 + i * 0.07
        cyl("rc_pilot_collar", (gx, -0.006, 0.085), 0.016, 0.01, "steel", "Y", 16, pre=Mb)
        add_cyl((bmg, bma, bmr, bmg, bma)[i], (gx, -0.012, 0.085), 0.011, 0.008, "Y", 16, pre=Mb)
    box("rc_tag_strip", (xc + 0.22, -0.002, 0.03), (0.36, 0.004, 0.02), "galvanized", 0.0, pre=Mb)
    obj("rc_leds_green", "led_green", bmg)
    obj("rc_leds_red", "led_red", bmr)
    obj("rc_leds_amber", "led_amber", bma)
    # Relay tower (right rear)
    tx, ty = 0.49, 0.205
    box("rc_tower_plinth", (tx, ty, 1.02), (0.38, 0.26, 0.04), "painted_dark", 0.004)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("rc_tower_post", (tx + sx * 0.172, ty + sy * 0.112, 1.385), (0.024, 0.024, 0.69), "robot_dark", 0.002)
    for z in (1.255, 1.505):
        box("rc_tower_shelf", (tx, ty, z), (0.36, 0.24, 0.01), "galvanized", 0.001)
    box("rc_tower_cap", (tx, ty, 1.745), (0.38, 0.26, 0.03), "painted_dark", 0.004)
    cyl("rc_beacon_base", (tx, ty, 1.765), 0.035, 0.012, "painted_dark", "Z", 20)
    cyl("rc_beacon", (tx, ty, 1.785), 0.028, 0.03, "led_amber", "Z", 20, bevel=0.004)

    def coil(cx, cy, z0, z1, rc, turns):
        cyl("rc_coil_core", (cx, cy, (z0 + z1) / 2), rc - 0.012, z1 - z0, "painted_dark", "Z", 16)
        for z in (z0 + 0.006, z1 - 0.006):
            cyl("rc_coil_flange", (cx, cy, z), rc + 0.014, 0.012, "painted_dark", "Z", 20, bevel=0.002)
        per = 12
        pts = [(cx + rc * math.cos(2 * math.pi * k / per), cy + rc * math.sin(2 * math.pi * k / per),
                z0 + 0.016 + (z1 - z0 - 0.032) * k / (turns * per)) for k in range(turns * per + 1)]
        tube("rc_coil_winding", pts, 0.0048, "copper", 6)
        for sx in (-1, 1):
            box("rc_coil_terminal", (cx + sx * 0.02, cy + rc + 0.01, z1 + 0.01), (0.008, 0.02, 0.02), "copper", 0.001)

    coil(tx - 0.085, ty, 1.04, 1.245, 0.045, 13)
    coil(tx + 0.085, ty, 1.04, 1.245, 0.045, 13)
    coil(tx, ty - 0.01, 1.51, 1.62, 0.055, 7)
    for i in range(2):
        box("rc_contactor", (tx - 0.09 + i * 0.18, ty, 1.31 + 0.06), (0.07, 0.09, 0.12), "painted_dark", 0.006, grooves=(("-y", 0.012, 0.003, 0.002),))
        box("rc_contactor_face", (tx - 0.09 + i * 0.18, ty - 0.046, 1.39), (0.04, 0.002, 0.03), "galvanized", 0.0)
    bm = bmesh.new()
    for i in range(3):
        add_box(bm, (tx - 0.08 + i * 0.08, ty + 0.11, 1.38), (0.028, 0.006, 0.66))
    obj("rc_busbars", "copper", bm)
    bm = bmesh.new()
    for i in range(3):
        for z in (1.12, 1.62):
            add_cyl(bm, (tx - 0.08 + i * 0.08, ty + 0.095, z), 0.011, 0.026, "Y", 12)
    obj("rc_insulators", "painted_grey", bm)
    bm = bmesh.new()
    for i, (a, b) in enumerate((((tx - 0.105, ty + 0.06, 1.255), (tx - 0.08, ty + 0.105, 1.3)), ((tx + 0.105, ty + 0.06, 1.255), (tx + 0.08, ty + 0.105, 1.34)),
                                ((tx - 0.02, ty + 0.06, 1.63), (tx, ty + 0.105, 1.6)))):
        mid = ((a[0] + b[0]) / 2, a[1] + 0.02, max(a[2], b[2]) + 0.04)
        add_tube(bm, fillet([a, (a[0], a[1], mid[2]), (b[0], b[1] - 0.02, mid[2]), b], 0.02), 0.0045, 6)
    for i in range(3):
        x = tx - 0.12 + i * 0.03
        add_tube(bm, fillet([(x, ty + 0.12, 1.04), (x, ty + 0.12, 1.0), (x, 0.34, 0.96), (x, 0.34, 0.8)], 0.03), 0.008, 8)
    obj("rc_tower_cables", "cable_black", bm)
    return finish("relay_console", off, keep=("screen",), note="origin bottom centre, operator side -Y")


def p_door_slab(off):
    # Heavy steel leaf: hinge edge at X=0 (origin, bottom), extends +X to 1.42, height 2.08, thickness 0.06, centred on Y=0.
    W, H, T = 1.42, 2.08, 0.06
    slab = box("ds_slab", (0.012 + (W - 0.012) / 2, 0, H / 2), (W - 0.012, T, H), "door_steel", 0.004,
               grooves=(("-y", 0.035, 0.004, 0.0025), ("y", 0.035, 0.004, 0.0025)))
    wx, wz, ww, wh = 0.71, 1.55, 0.30, 0.60
    cut(slab, lambda bm: add_box(bm, (wx, 0, wz), (ww, 0.2, wh)))
    box("ds_glass", (wx, 0, wz), (ww + 0.01, 0.008, wh + 0.01), "glass_lens", 0.0)
    bm = bmesh.new()
    sp = 0.026
    for sgn in (1, -1):
        c = -2.0
        while c < 2.0:
            # lines x - x0 = sgn * (z - z0) + c, clipped to the opening
            pts = []
            for z in (wz - wh / 2, wz + wh / 2):
                pts.append((wx + c + sgn * (z - wz), z))
            for x in (wx - ww / 2, wx + ww / 2):
                pts.append((x, wz + (x - wx - c) / sgn))
            inside = [p for p in pts if wx - ww / 2 - 1e-6 <= p[0] <= wx + ww / 2 + 1e-6 and wz - wh / 2 - 1e-6 <= p[1] <= wz + wh / 2 + 1e-6]
            inside = sorted(set((round(p[0], 6), round(p[1], 6)) for p in inside))
            if len(inside) >= 2:
                (x0, z0), (x1, z1) = inside[0], inside[-1]
                ln = math.hypot(x1 - x0, z1 - z0)
                if ln > 0.01:
                    add_box(bm, ((x0 + x1) / 2, 0, (z0 + z1) / 2), (ln, 0.0012, 0.0012), rot=(0, -45 * sgn, 0))
            c += sp
    obj("ds_wire", "steel", bm)
    for s in (-1, 1):
        y = s * T / 2
        # Glazing beads
        for loc, size in (((wx, 0, wz + wh / 2 + 0.015), (ww + 0.06, 0, 0.03)), ((wx, 0, wz - wh / 2 - 0.015), (ww + 0.06, 0, 0.03)),
                          ((wx - ww / 2 - 0.015, 0, wz), (0.03, 0, wh)), ((wx + ww / 2 + 0.015, 0, wz), (0.03, 0, wh))):
            box("ds_bead", (loc[0], y + s * 0.006, loc[2]), (size[0], 0.012, size[2]), "door_steel", 0.003)
        bolts("ds_bead_screws", [(wx + dx, y + s * 0.0125, wz + dz) for dx, dz in ((-0.165, -0.2), (-0.165, 0.2), (0.165, -0.2), (0.165, 0.2), (0, 0.315), (0, -0.315))], "steel", 0.004, 0.003, "Y", dome=True)
        # Kick plate
        box("ds_kick", (0.716, y + s * 0.0025, 0.14), (1.34, 0.005, 0.26), "steel", 0.001)
        bolts("ds_kick_screws", [(0.08 + i * 0.212, y + s * 0.0058, z) for i in range(7) for z in (0.03, 0.25)], "steel", 0.004, 0.003, "Y", dome=True)
        # Push plate
        box("ds_push", (1.27, y + s * 0.002, 1.36), (0.11, 0.004, 0.32), "steel", 0.001)
        bolts("ds_push_screws", [(1.27 + dx, y + s * 0.0045, 1.36 + dz) for dx in (-0.04, 0.04) for dz in (-0.14, 0.14)], "steel", 0.004, 0.003, "Y", dome=True)
        # Lever handle with safety return, lock cylinder
        cyl("ds_rose", (1.30, y + s * 0.004, 1.0), 0.033, 0.008, "steel", "Y", 24, bevel=0.002)
        cyl("ds_spindle", (1.30, y + s * 0.018, 1.0), 0.01, 0.025, "steel", "Y", 12)
        box("ds_lever", (1.24, y + s * 0.034, 1.0), (0.14, 0.016, 0.022), "steel", 0.005, segs=3)
        box("ds_lever_return", (1.177, y + s * 0.024, 1.0), (0.018, 0.034, 0.022), "steel", 0.005, segs=3)
        cyl("ds_lock_rose", (1.30, y + s * 0.004, 0.91), 0.02, 0.008, "steel", "Y", 20, bevel=0.002)
        box("ds_keyway", (1.30, y + s * 0.0085, 0.91), (0.003, 0.002, 0.014), "painted_dark", 0.0)
        # Hazard stripe band above the kick plate
        hazard_band("ds_hazard", ((0, y, 0), (1, 0, 0), (0, 0, 1), (0, s, 0)), 0.05, 1.37, 0.30, 0.40, w0=0.0002, sw=0.08)
    # Hinge knuckles at x ~ 0
    for z in (0.25, 1.04, 1.83):
        cyl("ds_knuckle", (0.0, 0.0, z), 0.0135, 0.115, "steel", "Z", 16, bevel=0.002)
        cyl("ds_pin_cap", (0.0, 0.0, z + 0.06), 0.009, 0.006, "steel", "Z", 12)
        box("ds_leaf", (0.007, 0, z), (0.012, 0.032, 0.1), "steel", 0.001)
    # Latch edge
    box("ds_faceplate", (W + 0.001, 0, 1.0), (0.003, 0.026, 0.22), "steel", 0.0)
    box("ds_latch", (W + 0.007, 0, 1.0), (0.012, 0.012, 0.026), "steel", 0.002)
    # Overhead closer on the +Y face near the hinge
    yc = T / 2
    box("ds_closer", (0.30, yc + 0.027, 1.955), (0.27, 0.05, 0.058), "galvanized", 0.01, segs=3)
    for x in (0.165, 0.435):
        cyl("ds_closer_cap", (x, yc + 0.027, 1.955), 0.024, 0.008, "painted_dark", "X", 16)
    box("ds_closer_plate", (0.30, yc + 0.002, 1.955), (0.33, 0.004, 0.08), "painted_dark", 0.001)
    cyl("ds_pinion", (0.40, yc + 0.057, 1.955), 0.013, 0.012, "steel", "Y", 12)
    box("ds_arm_main", (0.29, yc + 0.064, 1.97), (0.24, 0.008, 0.02), "steel", 0.003)
    cyl("ds_arm_elbow", (0.17, yc + 0.069, 1.975), 0.01, 0.018, "steel", "Y", 12)
    box("ds_arm_fore", (0.27, yc + 0.074, 1.985), (0.2, 0.006, 0.016), "steel", 0.003)
    bolts("ds_closer_screws", [(0.15 + i * 0.1, yc + 0.0045, z) for i in range(4) for z in (1.925, 1.985)], "steel", 0.004, 0.003, "Y", dome=True)
    return finish("door_slab", off, note="origin hinge edge bottom; +X width 1.42")


def p_lamp(off):
    # Caged bulkhead lamp; origin at the ceiling mounting plate (Z=0), hangs down ~0.2.
    cyl("lp_plate", (0, 0, -0.008), 0.10, 0.016, "painted_dark", "Z", 32, bevel=0.003)
    bolts("lp_screws", [(0.08 * math.cos(a), 0.08 * math.sin(a), -0.018) for a in (0.5, 2.6, 4.7)], "steel", 0.007, 0.005, "Z", dome=True, rot=(180, 0, 0))
    cyl("lp_housing", (0, 0, -0.0355), 0.078, 0.039, "painted_dark", "Z", 32, r2=0.088, bevel=0.003)
    torus("lp_gasket", (0, 0, -0.056), 0.068, 0.0045, "rubber", "Z", 32, 6)
    cyl("lp_conduit_boss", (0.085, 0, -0.035), 0.013, 0.024, "painted_dark", "X", 12, bevel=0.002)
    cyl("lp_conduit_plug", (0.098, 0, -0.035), 0.009, 0.006, "steel", "X", 6)
    bm = bmesh.new()
    r = 0.062
    vs = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)["verts"]
    for v in vs:
        if v.co.z > 0:
            xy = Vector((v.co.x, v.co.y))
            if xy.length > 1e-6:
                xy = xy.normalized() * r
            v.co = Vector((xy.x, xy.y, 0.044 * v.co.z / r))
    _xf(bm, vs, Matrix.Translation((0, 0, -0.1)))
    for f in bm.faces:
        f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    obj("globe", "lamp_warm", bm)
    bm = bmesh.new()
    for k in range(6):
        a = 2 * math.pi * (k + 0.5) / 6
        ca, sa = math.cos(a), math.sin(a)
        prof = [(0.08, -0.05), (0.076, -0.075), (0.074, -0.12), (0.062, -0.155), (0.035, -0.178), (0.014, -0.186)]
        add_tube(bm, fillet([(rr * ca, rr * sa, z) for rr, z in prof], 0.02, 3), 0.0035, 6)
    add_torus(bm, (0, 0, -0.11), 0.0745, 0.0035, "Z", 32, 6)
    add_torus(bm, (0, 0, -0.165), 0.05, 0.0035, "Z", 24, 6)
    add_torus(bm, (0, 0, -0.052), 0.08, 0.004, "Z", 32, 6)
    obj("lp_cage", "painted_dark", bm)
    cyl("lp_cage_boss", (0, 0, -0.19), 0.016, 0.012, "painted_dark", "Z", 12, bevel=0.002)
    return finish("lamp", off, keep=("globe",), note="origin at ceiling plate; hangs to -0.196")


def p_barrier(off):
    # Concrete jersey barrier 2.0 x 0.6 x 1.0, origin bottom centre.
    prof = [(-0.30, 0.0), (0.30, 0.0), (0.30, 0.075), (0.145, 0.30), (0.098, 0.975), (0.075, 1.0), (-0.075, 1.0), (-0.098, 0.975), (-0.145, 0.30), (-0.30, 0.075)]
    b = prism("bj_body", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -1.0, 1.0, "concrete", 0.01, 2, angle=20)

    def cutters(bm):
        add_box(bm, (0, 0, 0.05), (0.42, 0.8, 0.10))                       # forklift / drainage slot
        for sx in (-1, 1):
            add_box(bm, (sx * 1.0, 0, 0.52), (0.08, 0.1, 0.8))             # end keyway
        add_box(bm, (0.62, 0.07, 1.0), (0.05, 0.05, 0.05), rot=(35, 20, 10))  # edge chips
        add_box(bm, (-0.38, -0.09, 0.985), (0.04, 0.04, 0.04), rot=(15, 40, 0))
        add_box(bm, (-1.0, -0.29, 0.03), (0.06, 0.06, 0.06), rot=(20, 30, 45))
        add_box(bm, (0.95, 0.30, 0.07), (0.05, 0.05, 0.05), rot=(45, 10, 30))
    cut(b, cutters)
    for x in (-0.55, 0.55):
        tube("bj_loop", [(x - 0.05 * math.cos(math.pi * k / 10), 0, 0.985 + 0.06 * math.sin(math.pi * k / 10)) for k in range(11)], 0.009, "steel", 8)
    for sy in (-1, 1):
        for x in (-0.7, 0.7):
            y = sy * 0.113
            box("bj_reflector_housing", (x, y + sy * 0.004, 0.82), (0.09, 0.008, 0.055), "painted_dark", 0.002, rot=(sy * -4, 0, 0))
            box("bj_reflector", (x, y + sy * 0.0095, 0.82), (0.075, 0.004, 0.042), "hazard", 0.001, rot=(sy * -4, 0, 0))
            bolts("bj_reflector_bolts", [(x + dx, y + sy * 0.009, 0.82) for dx in (-0.04, 0.04)], "steel", 0.004, 0.004, "Y", dome=True)
    return finish("barrier", off, note="origin bottom centre")


def p_locker(off):
    # Steel locker 0.5 x 0.5 x 1.9, origin bottom centre, door faces -Y.
    box("lk_carcass", (0, 0.0075, 0.99), (0.5, 0.485, 1.82), "painted_grey", 0.004,
        recess=(("x", 0.04, 0.003), ("-x", 0.04, 0.003), ("z", 0.03, 0.002)))
    box("lk_plinth", (0, 0.02, 0.04), (0.46, 0.44, 0.08), "painted_dark", 0.003)
    # Door: gridded slab so a dent can be pressed in
    bm = bmesh.new()
    x0, x1, z0, z1, yf, yb = -0.23, 0.23, 0.10, 1.84, -0.25, -0.235
    nx, nz = 16, 48
    F = [[bm.verts.new((x0 + (x1 - x0) * i / nx, yf, z0 + (z1 - z0) * j / nz)) for j in range(nz + 1)] for i in range(nx + 1)]
    B = [[bm.verts.new((x0 + (x1 - x0) * i / nx, yb, z0 + (z1 - z0) * j / nz)) for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            bm.faces.new((F[i][j], F[i + 1][j], F[i + 1][j + 1], F[i][j + 1]))
            bm.faces.new((B[i][j], B[i][j + 1], B[i + 1][j + 1], B[i + 1][j]))
    for i in range(nx):
        bm.faces.new((F[i][0], B[i][0], B[i + 1][0], F[i + 1][0]))
        bm.faces.new((F[i][nz], F[i + 1][nz], B[i + 1][nz], B[i][nz]))
    for j in range(nz):
        bm.faces.new((F[0][j], F[0][j + 1], B[0][j + 1], B[0][j]))
        bm.faces.new((F[nx][j], B[nx][j], B[nx][j + 1], F[nx][j + 1]))
    cx, cz, rad, dep = -0.06, 0.72, 0.15, 0.02
    for v in bm.verts:
        d = math.hypot(v.co.x - cx, (v.co.z - cz) * 0.8)
        if d < rad:
            v.co.y += dep * (1 - (d / rad) ** 2) ** 2
    door = obj("lk_door", "painted_grey", bm, 0.003)

    def slots(bm):
        for z in [1.56 + i * 0.036 for i in range(6)] + [0.18 + i * 0.036 for i in range(4)]:
            add_box(bm, (0, -0.24, z), (0.26, 0.06, 0.012))
    cut(door, slots)
    box("lk_slot_backing", (0, -0.2338, 1.25), (0.3, 0.002, 1.25), "painted_dark", 0.0)
    bm = bmesh.new()
    for z in [1.56 + i * 0.036 for i in range(6)] + [0.18 + i * 0.036 for i in range(4)]:
        add_box(bm, (0, -0.2545, z + 0.006), (0.27, 0.003, 0.022), rot=(38, 0, 0))
    obj("lk_louvres", "painted_grey", bm, 0.001)
    box("lk_handle_cup", (0.17, -0.2525, 1.0), (0.05, 0.006, 0.13), "steel", 0.003)
    box("lk_handle", (0.17, -0.262, 1.025), (0.03, 0.014, 0.08), "steel", 0.004, segs=3)
    box("lk_hasp", (0.17, -0.265, 0.935), (0.012, 0.02, 0.03), "steel", 0.002)
    box("lk_number_plate", (0, -0.2522, 1.47), (0.085, 0.003, 0.042), "galvanized", 0.001)
    bolts("lk_number_rivets", [(-0.036, -0.2545, 1.47), (0.036, -0.2545, 1.47)], "steel", 0.0035, 0.003, "Y", dome=True)
    for z in (0.3, 0.97, 1.64):
        cyl("lk_hinge", (-0.237, -0.248, z), 0.006, 0.06, "steel", "Z", 12)
    box("lk_top_lip", (0, -0.244, 1.888), (0.5, 0.012, 0.024), "painted_grey", 0.003)
    return finish("locker", off, note="origin bottom centre, door faces -Y")


def p_desk(off):
    # Steel office desk 1.6 x 0.8 x 0.76 with monitor (monitor_scr), keyboard, phone, drawer pedestal. Origin bottom centre, user at -Y.
    box("dk_top", (0, 0, 0.745), (1.6, 0.8, 0.03), "painted_grey", 0.003)
    for loc, size in (((0, -0.402, 0.745), (1.608, 0.004, 0.032)), ((0, 0.402, 0.745), (1.608, 0.004, 0.032)),
                      ((-0.802, 0, 0.745), (0.004, 0.8, 0.032)), ((0.802, 0, 0.745), (0.004, 0.8, 0.032))):
        box("dk_edge", loc, size, "rubber", 0.001)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("dk_leg", (sx * 0.76, sy * 0.355, 0.365), (0.05, 0.05, 0.71), "painted_dark", 0.004)
            cyl("dk_foot", (sx * 0.76, sy * 0.355, 0.006), 0.02, 0.012, "rubber", "Z", 12)
        box("dk_side_rail", (sx * 0.76, 0, 0.705), (0.04, 0.66, 0.03), "painted_dark", 0.003)
    box("dk_front_rail", (0, -0.355, 0.705), (1.47, 0.03, 0.03), "painted_dark", 0.003)
    box("dk_modesty", (0, 0.37, 0.48), (1.47, 0.012, 0.4), "painted_grey", 0.002, grooves=(("y", 0.03, 0.003, 0.002), ("-y", 0.03, 0.003, 0.002)))
    # Drawer pedestal
    box("dk_pedestal", (0.48, 0.0, 0.38), (0.42, 0.66, 0.62), "painted_grey", 0.004)
    for z, h in ((0.585, 0.17), (0.41, 0.17), (0.17, 0.30)):
        box("dk_drawer", (0.48, -0.336, z), (0.40, 0.014, h - 0.008), "painted_grey", 0.003)
        box("dk_pull", (0.48, -0.354, z + h / 2 - 0.035), (0.14, 0.01, 0.012), "steel", 0.003)
        for dx in (-0.06, 0.06):
            box("dk_pull_post", (0.48 + dx, -0.347, z + h / 2 - 0.035), (0.01, 0.012, 0.01), "steel", 0.001)
    cyl("dk_lock", (0.64, -0.344, 0.645), 0.008, 0.006, "steel", "Y", 12)
    # Monitor
    box("dk_mon_base", (0.12, 0.18, 0.766), (0.22, 0.17, 0.012), "painted_dark", 0.004)
    box("dk_mon_neck", (0.12, 0.235, 0.9), (0.05, 0.022, 0.26), "painted_dark", 0.004)
    box("dk_mon_body", (0.12, 0.2, 1.03), (0.56, 0.036, 0.34), "painted_dark", 0.006)
    box("dk_mon_back", (0.12, 0.225, 1.02), (0.3, 0.03, 0.2), "painted_dark", 0.012, segs=3)
    box("monitor_scr", (0.12, 0.1815, 1.04), (0.52, 0.002, 0.29), "screen", 0.0)
    box("dk_mon_led", (0.36, 0.181, 0.873), (0.005, 0.002, 0.003), "led_green", 0.0)
    # Keyboard and mouse
    box("dk_kb", (0.1, -0.2, 0.769), (0.44, 0.145, 0.018), "painted_grey", 0.004, rot=(4, 0, 0))
    bm = bmesh.new()
    for r_ in range(5):
        for c_ in range(15):
            add_box(bm, (0.1 - 0.196 + c_ * 0.028, -0.252 + r_ * 0.026, 0.779 + r_ * 0.0018), (0.022, 0.021, 0.008), rot=(4, 0, 0))
    add_box(bm, (0.1, -0.278, 0.7775), (0.16, 0.021, 0.008), rot=(4, 0, 0))
    obj("dk_keys", "painted_dark", bm)
    box("dk_mouse", (0.43, -0.2, 0.774), (0.06, 0.1, 0.03), "painted_dark", 0.012, segs=3)
    # Desk phone with coiled cord
    box("dk_phone", (-0.52, 0.12, 0.785), (0.2, 0.18, 0.05), "painted_dark", 0.01, rot=(8, 0, 0), segs=3)
    box("dk_handset", (-0.52, 0.17, 0.822), (0.21, 0.05, 0.036), "painted_dark", 0.014, rot=(8, 0, 0), segs=3)
    bm = bmesh.new()
    for r_ in range(4):
        for c_ in range(3):
            add_box(bm, (-0.55 + c_ * 0.024, 0.06 + r_ * 0.02, 0.808 + r_ * 0.0028), (0.018, 0.015, 0.006), rot=(8, 0, 0))
    obj("dk_phone_keys", "painted_grey", bm)
    pts = [(-0.63 - 0.012 * math.sin(k * 0.8), 0.17 + 0.012 * math.cos(k * 0.8), 0.81 - k * 0.0015) for k in range(30)]
    tube("dk_phone_cord", pts, 0.0022, "cable_black", 6)
    # Monitor cable through grommet
    ring("dk_grommet", (0.12, 0.33, 0.762), 0.022, 0.032, 0.006, "galvanized", "Z", 20)
    tube("dk_mon_cable", fillet([(0.12, 0.242, 0.93), (0.12, 0.29, 0.86), (0.12, 0.33, 0.78), (0.12, 0.33, 0.6), (0.14, 0.39, 0.3), (0.16, 0.39, 0.0)], 0.06), 0.004, "cable_black")
    return finish("desk", off, keep=("monitor_scr",), note="origin bottom centre, user side -Y")


def p_pipe(off):
    # 4 m process pipe along Y, radius 0.1, origin at centre; flanged joints every 1.5 m; wall brackets toward +X (wall plane X=+0.25).
    cyl("pp_pipe", (0, 0, 0), 0.1, 4.0, "painted_grey", "Y", 32)
    for y in (-1.5, 0.0, 1.5):
        for s in (-1, 1):
            cyl("pp_flange", (0, y + s * 0.0135, 0), 0.165, 0.025, "painted_grey", "Y", 32, bevel=0.003)
            cyl("pp_hub", (0, y + s * 0.048, 0), 0.12 if s < 0 else 0.1, 0.045, "painted_grey", "Y", 32, r2=0.1 if s < 0 else 0.12, bevel=0.002)
        cyl("pp_gasket", (0, y, 0), 0.15, 0.002, "rubber", "Y", 32)
        bm = bmesh.new()
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            p = (0.138 * math.cos(a), y, 0.138 * math.sin(a))
            add_cyl(bm, p, 0.008, 0.092, "Y", 8)
            for s in (-1, 1):
                add_cyl(bm, (p[0], y + s * 0.033, p[2]), 0.014, 0.012, "Y", 6, rot=(0, math.degrees(a), 0))
        obj("pp_bolts", "steel", bm)
    ring("pp_id_band", (0, -0.75, 0), 0.1, 0.1015, 0.08, "hazard", "Y", 32)
    for yb in (-0.75 + 0.25, 0.75):
        ring("pp_clamp", (0, yb, 0), 0.1, 0.108, 0.04, "galvanized", "Y", 32)
        box("pp_clamp_ears", (0.125, yb, 0), (0.04, 0.04, 0.034), "galvanized", 0.002)
        cyl("pp_clamp_bolt", (0.125, yb, 0), 0.006, 0.06, "steel", "Z", 8)
        bolts("pp_clamp_nuts", [(0.125, yb, 0.022), (0.125, yb, -0.022)], "steel", 0.01, 0.008, "Z")
        box("pp_arm", (0.19, yb, 0), (0.1, 0.04, 0.04), "galvanized", 0.002)
        box("pp_wall_plate", (0.245, yb, 0), (0.01, 0.12, 0.16), "galvanized", 0.002)
        bolts("pp_anchor_nuts", [(0.236, yb, 0.055), (0.236, yb, -0.055)], "steel", 0.011, 0.01, "X")
        bolts("pp_anchor_studs", [(0.226, yb, 0.055), (0.226, yb, -0.055)], "steel", 0.006, 0.014, "X", verts=8)
    return finish("pipe", off, note="origin at pipe centre; run along Y; brackets to wall at +X 0.25")


def p_breaker(off):
    # Wall breaker panel 0.6 W x 0.2 D x 0.8 H, origin at centre, front -Y (wall behind at +Y 0.1).
    box("bk_body", (0, 0.01, 0), (0.6, 0.18, 0.8), "painted_grey", 0.008)
    box("bk_gasket", (0, -0.0805, 0), (0.575, 0.003, 0.775), "rubber", 0.0)
    box("bk_door", (0, -0.089, 0), (0.57, 0.016, 0.77), "painted_grey", 0.005, recess=(("-y", 0.045, -0.003),))
    for z in (-0.25, 0.25):
        cyl("bk_hinge", (-0.292, -0.09, z), 0.007, 0.07, "steel", "Z", 12)
    box("bk_latch_plate", (0.24, -0.1, 0.02), (0.04, 0.004, 0.12), "steel", 0.002)
    box("bk_latch", (0.24, -0.11, 0.005), (0.026, 0.016, 0.09), "painted_dark", 0.005, segs=3)
    cyl("bk_lock", (0.24, -0.103, 0.095), 0.008, 0.008, "steel", "Y", 12)
    fr = ((0, -0.1, 0.24), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    h3 = math.sqrt(3)
    tri = lambda s: [(-s / 2, -s * h3 / 6), (s / 2, -s * h3 / 6), (0, s * h3 / 3)]
    prism("bk_warn_border", tri(0.15), fr, 0.0, 0.001, "painted_dark")
    prism("bk_warn", tri(0.12), fr, 0.001, 0.002, "hazard")
    bolt = [(0.006, 0.032), (-0.012, -0.0), (0.0, -0.0), (-0.008, -0.028), (0.014, 0.008), (0.002, 0.008)]
    prism("bk_warn_bolt", [(u, v - 0.004) for u, v in bolt], fr, 0.002, 0.003, "painted_dark")
    box("bk_lever_plate", (0.13, -0.099, -0.22), (0.13, 0.003, 0.13), "hazard", 0.001)
    cyl("bk_lever_hub", (0.13, -0.106, -0.22), 0.028, 0.012, "painted_dark", "Y", 20, bevel=0.002)
    box("bk_lever", (0.13, -0.118, -0.17), (0.032, 0.016, 0.12), "painted_dark", 0.006, segs=3)
    cyl("bk_lever_grip", (0.13, -0.118, -0.11), 0.018, 0.04, "rubber", "Z", 12, bevel=0.003)
    cyl("bk_led_bezel", (0.20, -0.1, 0.30), 0.016, 0.006, "steel", "Y", 16)
    cyl("led", (0.20, -0.104, 0.30), 0.011, 0.008, "led_amber", "Y", 16, bevel=0.002)
    box("bk_data_plate", (-0.13, -0.0985, -0.22), (0.15, 0.002, 0.065), "galvanized", 0.0)
    bolts("bk_data_rivets", [(-0.13 + dx, -0.1, -0.22 + dz) for dx in (-0.065, 0.065) for dz in (-0.022, 0.022)], "steel", 0.003, 0.003, "Y", dome=True)
    for x in (-0.15, 0.15):
        cyl("bk_gland", (x, 0.02, -0.41), 0.02, 0.022, "steel", "Z", 6)
        cyl("bk_conduit", (x, 0.02, -0.45), 0.014, 0.06, "galvanized", "Z", 16)
    for sz in (-1, 1):
        for x in (-0.22, 0.22):
            box("bk_ear", (x, 0.095, sz * 0.415), (0.06, 0.01, 0.03), "galvanized", 0.002)
    return finish("breaker", off, keep=("led",), note="origin centre, front -Y")


# ================================================================= ENV KIT
def k_wall_rib(name, H, off):
    # Concrete pilaster 0.4 wide, protrudes 0.25 from the wall plane (Y=0) toward -Y, height H. Origin bottom centre on the wall plane.
    core = box("wr_core", (0, -0.125, H / 2), (0.4, 0.25, H), "concrete", 0.02, segs=1, angle=30)

    def cutters(bm):
        z = 0.3
        while z < H - 0.1:
            for x in (-0.1, 0.1):
                add_cyl(bm, (x, -0.25, z), 0.0125, 0.05, "Y", 10)
            z += 0.6
        z = 2.4
        while z < H - 0.2:
            add_box(bm, (0, -0.25, z), (0.44, 0.012, 0.012))
            for sx in (-1, 1):
                add_box(bm, (sx * 0.2, -0.13, z), (0.012, 0.25, 0.012))
            z += 2.4
    cut(core, cutters)
    for sx in (-1, 1):
        box("wr_guard_f", (sx * 0.162, -0.2545, 0.66), (0.086, 0.006, 1.2), "galvanized", 0.001)
        box("wr_guard_s", (sx * 0.2045, -0.212, 0.66), (0.006, 0.086, 1.2), "galvanized", 0.001)
        hazard_band("wr_hz_f", ((0, -0.2575, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.12 if sx > 0 else -0.205, 0.205 if sx > 0 else -0.12, 0.08, 1.24, sw=0.07)
        hazard_band("wr_hz_s", ((sx * 0.2075, 0, 0), (0, 1, 0), (0, 0, 1), (sx, 0, 0)), -0.255, -0.17, 0.08, 1.24, sw=0.07)
        bolts("wr_guard_bolts", [(sx * 0.15, -0.2595, z) for z in (0.2, 0.66, 1.12)], "steel", 0.007, 0.006, "Y", dome=True)
        bolts("wr_guard_bolts_s", [(sx * 0.2095, -0.19, z) for z in (0.2, 0.66, 1.12)], "steel", 0.007, 0.006, "X", dome=True)
    box("wr_bearing", (0, -0.13, H - 0.01), (0.36, 0.22, 0.02), "painted_dark", 0.002)
    bolts("wr_bearing_bolts", [(sx * 0.14, -0.13 + sy * 0.08, H + 0.004) for sx in (-1, 1) for sy in (-1, 1)], "steel", 0.012, 0.012, "Z")
    return finish(name, off, note="origin bottom centre on the wall plane; protrudes to Y=-0.25")


def k_ibeam(off):
    # IPE300-style I-beam, 4 m along X, 0.3 deep. Origin at the section centroid, mid-length.
    h, b, tw, tf, r = 0.3, 0.15, 0.0071, 0.0107, 0.015
    yi, zi = tw / 2, h / 2 - tf

    def arc(cy, cz, a0, a1, n=4):
        return [(cy + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cz + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
    prof = [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, -zi)]
    prof += arc(yi + r, -zi + r, 270, 180)
    prof += arc(yi + r, zi - r, 180, 90)
    prof += [(b / 2, zi), (b / 2, h / 2), (-b / 2, h / 2), (-b / 2, zi)]
    prof += arc(-yi - r, zi - r, 90, 0)
    prof += arc(-yi - r, -zi + r, 360, 270)
    prof += [(-b / 2, -zi)]
    prism("ib_beam", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -2.0, 2.0, "painted_grey", 0.0015, 1, angle=40)
    for x in (-1.0, 0.0, 1.0):
        for s in (-1, 1):
            box("ib_stiffener", (x, s * (yi + 0.034), 0), (0.01, 0.068, 2 * zi), "painted_grey", 0.001)
    for s in (-1, 1):
        x = s * 1.9925
        box("ib_endplate", (x, 0, 0), (0.015, 0.17, 0.34), "painted_grey", 0.002)
        pts = [(x - s * 0.0115, y, z) for y in (-0.045, 0.045) for z in (-0.155, -0.06, 0.06, 0.155)]
        bolts("ib_nuts", pts, "steel", 0.012, 0.008, "X")
        bolts("ib_washers", [(x - s * 0.0085, y, z) for _, y, z in pts], "steel", 0.015, 0.002, "X", verts=12)
    return finish("ibeam_4", off, note="origin centroid; X -2..2, Y +-0.075, Z +-0.15")


def k_cable_tray(off):
    # 4 m ladder cable tray along X with a cable bundle; origin on the centre-line at the underside of the side rails.
    for s in (-1, 1):
        prof = [(0.18, 0), (0.203, 0), (0.203, 0.1), (0.18, 0.1), (0.18, 0.097), (0.2, 0.097), (0.2, 0.003), (0.18, 0.003)]
        prof = [(s * y, z) for y, z in prof]
        prism("ct_rail", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -2.0, 2.0, "galvanized")
        for x in (-1.97, 1.97):
            box("ct_splice", (x, s * 0.2045, 0.05), (0.06, 0.003, 0.08), "galvanized", 0.001)
            bolts("ct_splice_bolts", [(x + dx, s * 0.207, z) for dx in (-0.018, 0.018) for z in (0.03, 0.07)], "steel", 0.006, 0.005, "Y")
    bm = bmesh.new()
    for i in range(16):
        add_box(bm, (-1.875 + i * 0.25, 0, 0.0115), (0.03, 0.362, 0.017))
    obj("ct_rungs", "galvanized", bm, 0.0015, 1)
    cables = [(-0.15, 0.016, 0.0), (-0.115, 0.016, 1.3), (-0.08, 0.016, 2.1), (-0.135, 0.009, 0.7), (-0.1, 0.01, 2.8),
              (-0.06, 0.012, 3.6), (0.06, 0.011, 0.4), (0.085, 0.011, 1.9), (0.11, 0.009, 4.4), (0.135, 0.008, 5.1)]
    stackz = {3: 0.052, 4: 0.054, 5: 0.022}
    bm = bmesh.new()
    for i, (y0, r, ph) in enumerate(cables):
        z = stackz.get(i, 0.02) + r
        pts = [(x, y0 + 0.006 * math.sin(math.pi * x + ph), z + 0.002 * math.sin(math.pi * 2 * x + ph)) for x in [-2.0 + 0.2 * k for k in range(21)]]
        add_tube(bm, pts, r, 8, caps=True)
    obj("ct_cables", "cable_black", bm)
    bm = bmesh.new()
    for x in (-1.5, -0.5, 0.5, 1.5):
        add_ring(bm, (x, -0.112, 0.05), 0.058, 0.061, 0.006, "X", 16)
        add_box(bm, (x, -0.112, 0.112), (0.006, 0.012, 0.01))
    obj("ct_ties", "cable_black", bm)
    for x in (-1.0, 1.0):
        box("ct_strut", (x, 0, -0.021), (0.042, 0.58, 0.042), "galvanized", 0.0015)
        for s in (-1, 1):
            cyl("ct_rod", (x, s * 0.27, 0.28), 0.005, 0.64, "steel", "Z", 8)
            bolts("ct_rod_nuts", [(x, s * 0.27, -0.046), (x, s * 0.27, 0.004)], "steel", 0.009, 0.008, "Z")
            box("ct_clip", (x, s * 0.212, 0.006), (0.03, 0.02, 0.012), "galvanized", 0.001)
    return finish("cable_tray_4", off, note="origin centre-line at rail underside; rods to Z=+0.6")


def k_pipe_bundle(off):
    # Three service pipes along X on strut uprights; origin at X centre, wall plane (Y=0), bottom of the struts. Pipes in front (-Y).
    pipes = [(0.12, 0.075, -0.13, "galvanized"), (0.36, 0.06, -0.115, "painted_grey"), (0.56, 0.025, -0.08, "copper")]
    for x in (-1.5, 0.0, 1.5):
        box("pb_strut", (x, -0.021, 0.35), (0.042, 0.042, 0.7), "galvanized", 0.0015, recess=(("-y", 0.008, 0.03),))
        bolts("pb_anchor", [(x, -0.012, 0.03), (x, -0.012, 0.67)], "steel", 0.01, 0.008, "Y")
        for z, r, y, m in pipes:
            ring("pb_clamp", (x, y, z), r, r + 0.006, 0.03, "galvanized", "X", 20)
            box("pb_clamp_neck", (x, (-0.042 + y + r + 0.006) / 2, z), (0.03, abs(-0.042 - (y + r + 0.006)) + 0.004, 0.02), "galvanized", 0.001)
            bolts("pb_clamp_bolt", [(x, -0.046, z)], "steel", 0.008, 0.008, "Y")
    for z, r, y, m in pipes:
        cyl("pb_pipe", (0, y, z), r, 4.0, m, "X", 24 if r > 0.03 else 16)
        for s in (-1, 1):
            ring("pb_coupling", (s * 1.9875, y, z), r, r + (0.01 if m != "copper" else 0.003), 0.025, "painted_dark" if m != "copper" else "copper", "X", 24)
            if m != "copper":
                box("pb_coupling_lug", (s * 1.9875, y, z + r + 0.014), (0.022, 0.03, 0.016), "painted_dark", 0.002)
    return finish("pipe_bundle_4", off, note="origin X centre, wall plane, strut bottom; pipes at Z 0.12/0.36/0.56")


def k_duct(off):
    # Rectangular galvanised duct 0.6 (Y) x 0.4 (Z), 4 m along X, flanged every 1 m; origin at duct centroid.
    bm = bmesh.new()
    hy, hz, bulge = 0.3, 0.2, 0.007
    for i in range(4):
        xa, xb = -2.0 + i, -1.0 + i
        for (ax, sgn) in (("z", 1), ("z", -1), ("y", 1), ("y", -1)):
            if ax == "z":
                c = [(xa, -hy, sgn * hz), (xb, -hy, sgn * hz), (xb, hy, sgn * hz), (xa, hy, sgn * hz)]
                ctr = ((xa + xb) / 2, 0, sgn * (hz + bulge))
            else:
                c = [(xa, sgn * hy, -hz), (xb, sgn * hy, -hz), (xb, sgn * hy, hz), (xa, sgn * hy, hz)]
                ctr = ((xa + xb) / 2, sgn * (hy + bulge), 0)
            vs = [bm.verts.new(p) for p in c]
            cv = bm.verts.new(ctr)
            for k in range(4):
                bm.faces.new((vs[k], vs[(k + 1) % 4], cv))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    obj("du_body", "galvanized", bm)

    def flange(x, half=None):
        offs = (-0.0085, 0.0085) if half is None else (half,)
        for o in offs:
            for loc, size in (((0, 0, hz + 0.0175), (0.013, 2 * hy + 0.07, 0.035)), ((0, 0, -hz - 0.0175), (0.013, 2 * hy + 0.07, 0.035)),
                              ((0, -hy - 0.0175, 0), (0.013, 0.035, 2 * hz)), ((0, hy + 0.0175, 0), (0.013, 0.035, 2 * hz))):
                box("du_flange", (x + o, loc[1], loc[2]), size, "galvanized", 0.0015)
        if half is None:
            for loc, size in (((0, 0, hz + 0.016), (0.004, 2 * hy + 0.06, 0.03)), ((0, 0, -hz - 0.016), (0.004, 2 * hy + 0.06, 0.03)),
                              ((0, -hy - 0.016, 0), (0.004, 0.03, 2 * hz)), ((0, hy + 0.016, 0), (0.004, 0.03, 2 * hz))):
                box("du_gasket", (x, loc[1], loc[2]), size, "rubber", 0.0)
        pts = [(x, sy * (hy + 0.022), sz * (hz + 0.022)) for sy in (-1, 1) for sz in (-1, 1)]
        bolts("du_corner_bolts", pts, "steel", 0.008, 0.032 if half is None else 0.016, "X")
    for x in (-1.0, 0.0, 1.0):
        flange(x)
    flange(-2.0, 0.0065)
    flange(2.0, -0.0065)
    for x in (-1.5, 1.5):
        box("du_strut", (x, 0, -hz - 0.021), (0.042, 0.78, 0.042), "galvanized", 0.0015)
        for s in (-1, 1):
            cyl("du_rod", (x, s * 0.36, 0.19), 0.005, 0.82, "steel", "Z", 8)
            bolts("du_rod_nuts", [(x, s * 0.36, -hz - 0.046), (x, s * 0.36, -hz + 0.004)], "steel", 0.009, 0.008, "Z")
    return finish("duct_4", off, note="origin at duct centroid; hanger rods to Z=+0.6")


def k_vent_grille(off):
    # 0.6 x 0.4 wall grille, front -Y; origin at the back-face centre (wall plane Y=0).
    fr = box("vg_frame", (0, -0.006, 0), (0.6, 0.012, 0.4), "painted_grey", 0.003)
    cut(fr, lambda bm: add_box(bm, (0, 0, 0), (0.52, 0.1, 0.32)))
    for loc, size in (((0, 0.05, 0.161), (0.52, 0.1, 0.002)), ((0, 0.05, -0.161), (0.52, 0.1, 0.002)),
                      ((-0.261, 0.05, 0), (0.002, 0.1, 0.32)), ((0.261, 0.05, 0), (0.002, 0.1, 0.32)), ((0, 0.1, 0), (0.52, 0.002, 0.32))):
        box("vg_sleeve", loc, size, "painted_dark", 0.0)
    bm = bmesh.new()
    for i in range(8):
        add_box(bm, (0, -0.004, -0.14 + i * 0.04), (0.52, 0.042, 0.002), rot=(40, 0, 0))
    obj("vg_blades", "painted_grey", bm, 0.0008, 1)
    box("vg_mullion", (0, -0.006, 0), (0.008, 0.016, 0.32), "painted_grey", 0.001)
    bolts("vg_screws", [(sx * 0.28, -0.013, sz * 0.18) for sx in (-1, 1) for sz in (-1, 1)], "steel", 0.006, 0.004, "Y", dome=True)
    return finish("vent_grille", off, note="origin back-face centre on wall plane; front -Y")


def k_troffer(off):
    # Surface-mounted fluorescent fixture 1.2 x 0.3; origin at top centre (ceiling plane), hangs to -0.07.
    hs = box("tf_housing", (0, 0, -0.035), (1.2, 0.3, 0.07), "painted_grey", 0.004)
    cut(hs, lambda bm: add_box(bm, (0, 0, -0.07), (1.14, 0.24, 0.03)))
    box("light_panel", (0, 0, -0.0565), (1.13, 0.23, 0.004), "lamp_cool", 0.0)
    bm = bmesh.new()
    for x in (-0.38, 0.0, 0.38):
        add_box(bm, (x, 0, -0.065), (0.012, 0.24, 0.012))
    add_box(bm, (0, 0, -0.066), (1.14, 0.008, 0.008))
    obj("tf_louvre", "painted_grey", bm, 0.001)
    for sx in (-1, 1):
        box("tf_endcap", (sx * 0.597, 0, -0.035), (0.01, 0.304, 0.072), "painted_grey", 0.003)
    bolts("tf_screws", [(sx * 0.585, sy * 0.135, -0.071) for sx in (-1, 1) for sy in (-1, 1)], "steel", 0.005, 0.003, "Z", dome=True, rot=(180, 0, 0))
    return finish("troffer", off, keep=("light_panel",), note="origin top centre (ceiling plane)")


def k_highbay(off):
    # Industrial high-bay reflector lamp; origin at the top of the hook eye; reflector dia 0.45.
    torus("hb_eye", (0, 0, -0.022), 0.018, 0.0045, "steel", "Y", 16, 6)
    cyl("hb_eye_shank", (0, 0, -0.05), 0.006, 0.03, "steel", "Z", 8)
    cyl("hb_cap", (0, 0, -0.0725), 0.11, 0.025, "painted_dark", "Z", 32, r2=0.045, bevel=0.003)
    cyl("hb_driver", (0, 0, -0.145), 0.11, 0.12, "painted_dark", "Z", 32, bevel=0.005)
    bm = bmesh.new()
    for k in range(36):
        a = 360 * k / 36
        add_box(bm, (0.122 * math.cos(math.radians(a)), 0.122 * math.sin(math.radians(a)), -0.145), (0.028, 0.0025, 0.112), rot=(0, 0, a))
    obj("hb_fins", "painted_dark", bm)
    cyl("hb_gland", (0.06, 0, -0.06), 0.012, 0.02, "steel", "Z", 6)
    tube("hb_cord", fillet([(0.06, 0, -0.05), (0.06, 0, 0.02), (0.1, 0, 0.12)], 0.05), 0.005, "cable_black")
    cyl("hb_neck", (0, 0, -0.218), 0.075, 0.026, "galvanized", "Z", 32, bevel=0.002)
    outer = [(0.072 + 0.153 * (k / 10) ** 0.8, -0.23 - 0.25 * k / 10) for k in range(11)]
    inner = [(r - 0.004, z + 0.002) for r, z in reversed(outer)]
    prof = outer + [(0.229, -0.483), (0.23, -0.489), (0.224, -0.486)] + inner
    bm = bmesh.new()
    add_revolve(bm, prof, 48, closed=True)
    obj("hb_reflector", "galvanized", bm)
    cyl("hb_socket", (0, 0, -0.245), 0.022, 0.035, "galvanized", "Z", 16)
    bm = bmesh.new()
    prof = [(0.004, -0.262)] + [(0.052 * math.sin(math.pi * k / 12) + 0.012 * (1 - k / 12), -0.262 - 0.17 * (1 - math.cos(math.pi * k / 12)) / 2) for k in range(1, 12)] + [(0.004, -0.432)]
    add_revolve(bm, prof, 24, closed=False, cap_ends=True)
    obj("lamp_bulb", "lamp_warm", bm)
    return finish("highbay", off, keep=("lamp_bulb",), note="origin top of hook eye; reflector bottom at Z=-0.49")


def k_emergency_light(off):
    # Wall emergency light box with red lens; origin at the back-face centre (wall plane), front -Y.
    box("el_housing", (0, -0.035, 0), (0.30, 0.07, 0.11), "painted_grey", 0.008, segs=3, recess=(("-y", 0.03, 0.004),))
    box("emergency_lens", (0, -0.0695, 0.005), (0.225, 0.008, 0.042), "led_red", 0.003)
    cyl("el_status_led", (0.115, -0.0705, -0.036), 0.0045, 0.004, "led_green", "Y", 12)
    cyl("el_test_button", (0.095, -0.0705, -0.036), 0.006, 0.004, "painted_dark", "Y", 12)
    bolts("el_screws", [(sx * 0.13, -0.0705, sz * 0.04) for sx in (-1, 1) for sz in (-1, 1)], "steel", 0.0045, 0.003, "Y", dome=True)
    cyl("el_gland", (-0.1, -0.035, 0.062), 0.012, 0.016, "steel", "Z", 6)
    cyl("el_conduit", (-0.1, -0.035, 0.12), 0.0095, 0.1, "galvanized", "Z", 12)
    return finish("emergency_light", off, keep=("emergency_lens",), note="origin back-face centre on wall plane; front -Y")


def k_junction_box(off):
    # Galvanised junction box with conduit stubs; origin at the back-face centre (wall plane), front -Y.
    box("jb_body", (0, -0.04, 0), (0.2, 0.08, 0.2), "galvanized", 0.004)
    box("jb_lid", (0, -0.084, 0), (0.21, 0.008, 0.21), "galvanized", 0.003, recess=(("-y", 0.025, -0.003),))
    bolts("jb_lid_screws", [(sx * 0.09, -0.0885, sz * 0.09) for sx in (-1, 1) for sz in (-1, 1)], "steel", 0.006, 0.004, "Y", dome=True)
    for sz in (-1, 1):
        cyl("jb_gland", (0.04, -0.04, sz * 0.108), 0.017, 0.016, "steel", "Z", 6)
        cyl("jb_locknut", (0.04, -0.04, sz * 0.12), 0.019, 0.006, "steel", "Z", 8)
        cyl("jb_conduit", (0.04, -0.04, sz * 0.2), 0.012, 0.16, "galvanized", "Z", 16)
        box("jb_ear", (0, -0.002, sz * 0.115), (0.05, 0.004, 0.03), "galvanized", 0.001)
        bolts("jb_ear_screw", [(0, -0.0045, sz * 0.118)], "steel", 0.005, 0.003, "Y", dome=True)
    cyl("jb_gland_side", (-0.108, -0.04, 0.0), 0.017, 0.016, "steel", "X", 6)
    cyl("jb_conduit_side", (-0.18, -0.04, 0.0), 0.012, 0.14, "galvanized", "X", 16)
    fr = ((0, -0.0885, 0.0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    h3 = math.sqrt(3)
    prism("jb_warn_border", [(-0.03, -0.03 * h3 / 3), (0.03, -0.03 * h3 / 3), (0, 0.06 * h3 / 3)], fr, 0.0, 0.0008, "painted_dark")
    prism("jb_warn", [(-0.024, -0.024 * h3 / 3), (0.024, -0.024 * h3 / 3), (0, 0.048 * h3 / 3)], fr, 0.0008, 0.0016, "hazard")
    return finish("junction_box", off, note="origin back-face centre on wall plane; front -Y")


def k_keypad(off):
    # Door access keypad; origin at the back-face centre (wall plane), front -Y.
    box("kp_backbox", (0, -0.008, 0), (0.09, 0.016, 0.16), "painted_dark", 0.003)
    box("kp_face", (0, -0.02, 0), (0.084, 0.008, 0.154), "steel", 0.004, recess=(("-y", 0.008, 0.0015),))
    bm = bmesh.new()
    for r_ in range(4):
        for c_ in range(3):
            add_box(bm, (-0.022 + c_ * 0.022, -0.0245, 0.012 - r_ * 0.02), (0.017, 0.004, 0.014))
    obj("kp_keys", "painted_dark", bm, 0.0015, 2)
    box("kp_display", (0, -0.0232, 0.05), (0.05, 0.002, 0.018), "screen", 0.0)
    box("kp_reader", (0, -0.0232, -0.068), (0.06, 0.002, 0.012), "painted_dark", 0.0)
    cyl("keypad_led_red", (-0.012, -0.0235, 0.068), 0.0032, 0.003, "led_red", "Y", 12)
    cyl("keypad_led_green", (0.012, -0.0235, 0.068), 0.0032, 0.003, "led_green", "Y", 12)
    bolts("kp_tamper", [(0, -0.0245, 0.0745), (0, -0.0245, -0.0745)], "steel", 0.003, 0.002, "Y", verts=6)
    return finish("keypad", off, keep=("keypad_led_red", "keypad_led_green"), note="origin back-face centre on wall plane; front -Y")


def k_handrail(off):
    # 2 m guard rail section along X, 1.1 high; origin bottom centre (floor).
    r = 0.0213
    for x in (-0.97, 0.97):
        cyl("hr_post", (x, 0, 0.555), r, 1.09, "hazard", "Z", 16)
        box("hr_base", (x, 0, 0.005), (0.12, 0.12, 0.01), "galvanized", 0.002)
        bolts("hr_anchors", [(x + dx, dy, 0.014) for dx in (-0.042, 0.042) for dy in (-0.042, 0.042)], "steel", 0.008, 0.008, "Z")
        for z in (1.1, 0.55):
            cyl("hr_tee", (x, 0, z), 0.03, 0.07, "galvanized", "X", 16, bevel=0.003)
            cyl("hr_tee_v", (x, 0, z - 0.03), 0.03, 0.04, "galvanized", "Z", 16, bevel=0.003)
            bolts("hr_grub", [(x, -0.032, z)], "steel", 0.006, 0.006, "Y")
        box("hr_toe_clamp", (x, -0.028, 0.06), (0.05, 0.016, 0.08), "galvanized", 0.002)
    for z in (1.1, 0.55):
        cyl("hr_rail", (0, 0, z), r, 2.0, "hazard", "X", 16)
    box("hr_toeboard", (0, -0.038, 0.06), (2.0, 0.004, 0.1), "galvanized", 0.001)
    return finish("handrail_2", off, note="origin bottom centre; posts at X +-0.97")


def k_floor_drain(off):
    # 0.32 square floor drain; origin at the floor surface centre (grate top +0.002, frame top +0.004).
    fr = box("fd_frame", (0, 0, -0.006), (0.32, 0.32, 0.02), "galvanized", 0.002)
    cut(fr, lambda bm: add_box(bm, (0, 0, 0), (0.27, 0.27, 0.1)))
    bm = bmesh.new()
    for i in range(11):
        add_box(bm, (-0.125 + i * 0.025, 0, -0.006), (0.008, 0.27, 0.016))
    for y in (-0.07, 0.07):
        add_box(bm, (0, y, -0.01), (0.27, 0.008, 0.012))
    obj("fd_grate", "steel", bm, 0.001, 1)
    box("fd_sump", (0, 0, -0.1), (0.27, 0.27, 0.16), "painted_dark", 0.0)
    return finish("floor_drain", off, note="origin floor-surface centre; sump to Z=-0.18")


def k_sign_plate(off):
    # Blank 0.6 x 0.3 sign plate for text overlays; origin at back-face centre (wall plane); face at Y=-0.004.
    prism("sp_plate", rounded_rect(0.6, 0.3, 0.018), ((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, 0.004, "painted_grey", 0.0012, 2)
    bolts("sp_screws", [(sx * 0.272, -0.0055, sz * 0.122) for sx in (-1, 1) for sz in (-1, 1)], "steel", 0.0065, 0.003, "Y", dome=True)
    return finish("sign_plate", off, note="origin back-face centre; overlay text at Y<=-0.006")


def k_door_frame(off):
    # Heavy steel frame for a 1.5 W x 2.2 H opening (X +-0.75) in a 0.3 m wall (Y +-0.15); origin bottom centre of the opening.
    hw, Hh, T = 0.75, 2.2, 0.15
    for sx in (-1, 1):
        box("df_jamb", (sx * (hw + 0.003), 0, Hh / 2), (0.006, 2 * T, Hh), "door_steel", 0.0015)
    box("df_head", (0, 0, Hh + 0.003), (2 * hw + 0.012, 2 * T, 0.006), "door_steel", 0.0015)
    for sy in (-1, 1):
        y = sy * (T + 0.006)
        for sx in (-1, 1):
            box("df_trim", (sx * (hw + 0.05), y, (Hh + 0.1) / 2), (0.1, 0.012, Hh + 0.1), "door_steel", 0.003)
            box("df_trim_return", (sx * (hw + 0.003), sy * (T + 0.003), Hh / 2), (0.006, 0.006, Hh), "door_steel", 0.0)
            hazard_band("df_hz", ((0, sy * (T + 0.012), 0), (1, 0, 0), (0, 0, 1), (0, sy, 0)),
                        min(sx * hw, sx * (hw + 0.1)) + 0.006, max(sx * hw, sx * (hw + 0.1)) - 0.006, 0.0, Hh, sw=0.1)
            bolts("df_trim_bolts", [(sx * (hw + 0.05), sy * (T + 0.0135), z) for z in (0.25, 1.1, 1.95)], "steel", 0.007, 0.004, "Y", dome=True)
        box("df_head_trim", (0, y, Hh + 0.05), (2 * hw + 0.2, 0.012, 0.1), "door_steel", 0.003)
        bolts("df_head_bolts", [(x, sy * (T + 0.0135), Hh + 0.05) for x in (-0.5, 0.0, 0.5)], "steel", 0.007, 0.004, "Y", dome=True)
    box("df_closer_plate", (-0.55, T + 0.015, Hh + 0.05), (0.26, 0.006, 0.07), "painted_dark", 0.001)
    for z in (0.26, 1.05, 1.84):
        box("df_hinge_rx", (-hw + 0.004, 0, z), (0.006, 0.04, 0.12), "steel", 0.001)
        bolts("df_hinge_screws", [(-hw + 0.007, 0, z + dz) for dz in (-0.04, 0.0, 0.04)], "steel", 0.004, 0.003, "X", dome=True)
    box("df_strike", (hw - 0.004, 0, 1.0), (0.006, 0.035, 0.2), "steel", 0.001)
    box("df_strike_hole", (hw - 0.0075, 0, 1.0), (0.002, 0.014, 0.03), "painted_dark", 0.0)
    box("df_threshold", (0, 0, 0.005), (2 * hw, 2 * T, 0.01), "steel", 0.002, grooves=(("z", 0.02, 0.003, 0.0015),))
    bm = bmesh.new()
    for i in range(9):
        add_box(bm, (0, -0.12 + i * 0.03, 0.0105), (2 * hw - 0.06, 0.006, 0.002))
    obj("df_threshold_ribs", "steel", bm)
    return finish("door_frame", off, note="origin bottom centre of opening; opening X +-0.75, Z 0..2.2, wall Y +-0.15")


# ================================================================= build
def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    reset()
    p_crate((0, 0, 0))
    p_barrel((2, 0, 0))
    p_server_rack((4, 0, 0))
    p_relay_console((6, 0, 0))
    p_door_slab((8, 0, 0))
    p_lamp((10, 0, 0))
    p_barrier((12, 0, 0))
    p_locker((14, 0, 0))
    p_desk((16, 0, 0))
    p_pipe((18, 0, 0))
    p_breaker((20, 0, 0))
    export(os.path.join(out_dir, "props.glb"))
    reset()
    k_wall_rib("wall_rib_4", 4.0, (0, 0, 0))
    k_wall_rib("wall_rib_9", 9.0, (1.2, 0, 0))
    k_ibeam((4.2, 0, 0))
    k_cable_tray((9.2, 0, 0))
    k_pipe_bundle((14.2, 0, 0))
    k_duct((19.2, 0, 0))
    k_vent_grille((22.2, 0, 0))
    k_troffer((23.7, 0, 0))
    k_highbay((25.2, 0, 0))
    k_emergency_light((26.4, 0, 0))
    k_junction_box((27.3, 0, 0))
    k_keypad((28.0, 0, 0))
    k_handrail((29.8, 0, 0))
    k_floor_drain((31.4, 0, 0))
    k_sign_plate((32.4, 0, 0))
    k_door_frame((34.4, 0, 0))
    export(os.path.join(out_dir, "env_kit.glb"))
    with open(os.path.join(out_dir, "kit_stats.json"), "w", encoding="utf-8") as f:
        json.dump(STATS, f, indent=1)


# ================================================================= Poly Haven conversion
def glb_json(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, length = struct.unpack_from("<III", data, 0)
    clen, ctype = struct.unpack_from("<II", data, 12)
    return json.loads(data[20:20 + clen].decode("utf-8"))


def measure(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        mw = eo.matrix_world
        for v in me.vertices:
            w = mw @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        eo.to_mesh_clear()
    return n, lo, hi


def convert(ph_dir):
    stats = {}
    for mid in sorted(os.listdir(ph_dir)):
        d = os.path.join(ph_dir, mid)
        gl = [f for f in os.listdir(d) if f.endswith(".gltf")] if os.path.isdir(d) else []
        if not gl:
            continue
        src = os.path.join(d, gl[0])
        reset()
        bpy.ops.import_scene.gltf(filepath=src)
        bpy.context.view_layer.update()
        sc = bpy.context.scene
        meshes = [o for o in sc.objects if o.type == "MESH"]
        rigged = any(o.type == "ARMATURE" for o in sc.objects)
        n_in, lo, hi = measure(meshes)
        # Bake any rig deformation / bone parenting into static meshes, flatten under one root named after the asset.
        if any(len(o.modifiers) for o in meshes):
            bpy.ops.object.select_all(action="DESELECT")
            for o in meshes:
                o.select_set(True)
            bpy.context.view_layer.objects.active = meshes[0]
            bpy.ops.object.make_single_user(object=True, obdata=True)
            bpy.ops.object.convert(target="MESH")
        bpy.context.view_layer.update()
        for o in meshes:
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
            o.vertex_groups.clear()
        for o in [o for o in sc.objects if o.type != "MESH"]:
            bpy.data.objects.remove(o, do_unlink=True)
        root = bpy.data.objects.new(mid, None)
        sc.collection.objects.link(root)
        for o in meshes:
            o.parent = root
        bpy.context.view_layer.update()
        n_out, lo2, hi2 = measure(meshes)
        out = os.path.join(d, mid + ".glb")
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_apply=True, export_yup=True,
                                  export_animations=False, export_skins=False, export_image_format="AUTO")
        with open(src, encoding="utf-8") as f:
            sj = json.load(f)
        oj = glb_json(out)
        imgs = oj.get("images", [])

        def tex_slots(js):
            n = 0
            for m in js.get("materials", []):
                pbr = m.get("pbrMetallicRoughness", {})
                n += sum(1 for k in ("baseColorTexture", "metallicRoughnessTexture") if k in pbr)
                n += sum(1 for k in ("normalTexture", "occlusionTexture", "emissiveTexture") if k in m)
            return n
        # Re-import to confirm Blender sees packed, decodable images.
        reset()
        bpy.ops.import_scene.gltf(filepath=out)
        ok_imgs = sum(1 for im in bpy.data.images if im.packed_file is not None and im.size[0] > 0)
        stats[mid] = {
            "size": [round(h - l, 3) for l, h in zip(lo, hi)], "tris": n_in, "tris_glb": n_out, "rigged_baked": rigged,
            "src_images": len(sj.get("images", [])), "glb_images": len(imgs), "glb_images_embedded": sum(1 for i in imgs if "bufferView" in i),
            "src_tex_slots": tex_slots(sj), "glb_tex_slots": tex_slots(oj), "reimport_images_ok": ok_imgs,
            "glb_mb": round(os.path.getsize(out) / 1e6, 2), "materials": len(oj.get("materials", [])),
        }
        print("converted", mid, stats[mid])
    with open(os.path.join(ph_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)


# ================================================================= previews
WALL = {"vent_grille", "emergency_light", "junction_box", "keypad", "sign_plate", "breaker", "wall_rib_4", "wall_rib_9",
        "pipe_bundle_4", "utility_box_01", "utility_box_02", "power_box_01", "fire_alarm", "industrial_wall_lamp", "modular_electric_cables"}
CEIL = {"lamp", "troffer", "highbay", "hanging_industrial_lamp"}
TOP = {"floor_drain"}
LABELS = []


def studio(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 48
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("studio")
    sc.world = w
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.21, 0.215, 0.22, 1)
    bg.inputs["Strength"].default_value = 0.7
    for name, energy, rot, ang in (("key", 3.2, (52, 0, -38), 6), ("fill", 0.9, (65, 0, 70), 20), ("rim", 2.2, (-60, 0, 20), 4), ("under", 0.4, (180, 0, 0), 30)):
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy = energy
        ld.angle = math.radians(ang)
        lo = bpy.data.objects.new(name, ld)
        lo.rotation_euler = [math.radians(a) for a in rot]
        sc.collection.objects.link(lo)
    gm = bpy.data.materials.new("_ground")
    gb = gm.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = (0.16, 0.16, 0.165, 1)
    gb.inputs["Roughness"].default_value = 0.85
    planes = {}
    for nm in ("_floor", "_wall", "_ceil"):
        me = bpy.data.meshes.new(nm)
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(gm)
        o = bpy.data.objects.new(nm, me)
        sc.collection.objects.link(o)
        planes[nm] = o
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 50
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    lm = bpy.data.materials.new("_label")
    lb = lm.node_tree.nodes.get("Principled BSDF")
    lb.inputs["Base Color"].default_value = (0, 0, 0, 1)
    lb.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    lb.inputs["Emission Strength"].default_value = 1.0
    cu = bpy.data.curves.new("_label", "FONT")
    cu.materials.append(lm)
    txt = bpy.data.objects.new("_label", cu)
    sc.collection.objects.link(txt)
    txt.parent = cam
    return cam, planes, txt


def bounds(objs):
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def frame(cam, planes, txt, objs, label, kind, res, dir_override=None):
    bpy.context.view_layer.update()
    lo, hi = bounds(objs)
    c = (lo + hi) / 2
    rad = max((hi - lo).length / 2, 0.05)
    d = Vector(dir_override or {"ceil": (-0.55, -1.0, -0.5), "top": (-0.3, -0.7, 1.3)}.get(kind, (-0.75, -1.0, 0.55))).normalized()
    fov = 2 * math.atan(18 / 50 * min(1.0, res[1] / res[0]))
    dist = rad / math.sin(fov / 2) * 1.02
    cam.location = c + d * dist
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_start = dist * 0.002
    cam.data.clip_end = dist * 10
    big = max(rad * 6, 2.0)
    fl, wl, cl = planes["_floor"], planes["_wall"], planes["_ceil"]
    fl.hide_render = kind == "ceil"
    fl.location = (c.x, c.y, lo.z - 0.0005)
    fl.scale = (big, big, 1)
    wl.hide_render = kind != "wall"
    wl.location = (c.x, hi.y + 0.0005, c.z)
    wl.rotation_euler = (math.radians(90), 0, 0)
    wl.scale = (big, big, 1)
    cl.hide_render = kind != "ceil"
    cl.location = (c.x, c.y, hi.z + 0.0005)
    cl.scale = (big, big, 1)
    dt = dist * 0.05
    wf = dt * 36 / 50
    hf = wf * res[1] / res[0]
    txt.data.body = label
    txt.data.size = hf * 0.06
    txt.location = (-wf * 0.47, -hf * 0.45, -dt)
    txt.rotation_euler = (0, 0, 0)


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def compose(tiles, cols, tile_res, out):
    rows = (len(tiles) + cols - 1) // cols
    import numpy as np
    W, H = cols * tile_res[0], rows * tile_res[1]
    sheet = np.zeros((H, W, 4), dtype=np.float32)
    sheet[..., 3] = 1.0
    sheet[..., :3] = 0.08
    for i, p in enumerate(tiles):
        im = bpy.data.images.load(p)
        px = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
        im.pixels.foreach_get(px)
        px = px.reshape(im.size[1], im.size[0], 4)
        r, c = divmod(i, cols)
        y0 = H - (r + 1) * tile_res[1]
        sheet[y0:y0 + im.size[1], c * tile_res[0]:c * tile_res[0] + im.size[0]] = px
        bpy.data.images.remove(im)
    img = bpy.data.images.new("sheet", W, H, alpha=False)
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    print("wrote", out)


def kind_of(name):
    return "ceil" if name in CEIL else "top" if name in TOP else "wall" if name in WALL else "floor"


def sheet_glb(glb, out, cols, tile_res=(640, 560)):
    reset()
    bpy.ops.import_scene.gltf(filepath=glb)
    roots = [o for o in bpy.context.scene.objects if o.parent is None]
    cam, planes, txt = studio(tile_res)
    tmp = tempfile.mkdtemp(prefix="envkit_")
    tiles = []
    for i, r in enumerate(roots):
        group = [r] + list(r.children_recursive)
        for o in roots:
            for x in [o] + list(o.children_recursive):
                x.hide_render = o is not r
        lo, hi = bounds(group)
        sz = hi - lo
        label = "%s  %.2f x %.2f x %.2f m" % (r.name, sz.x, sz.y, sz.z)
        frame(cam, planes, txt, group, label, kind_of(r.name), tile_res)
        p = os.path.join(tmp, "t%02d.png" % i)
        render_to(p)
        tiles.append(p)
    compose(tiles, cols, tile_res, out)
    shutil.rmtree(tmp, ignore_errors=True)


def row_glb(glb, out, res=(2400, 760)):
    reset()
    bpy.ops.import_scene.gltf(filepath=glb)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    cam, planes, txt = studio(res)
    d = Vector((-0.12, -1.0, 0.3)).normalized()
    frame(cam, planes, txt, objs, os.path.basename(glb), "floor", res, dir_override=tuple(d))
    lo, hi = bounds(objs)
    c = (lo + hi) / 2
    hf = math.atan(18 / 50)                       # horizontal half-FOV (sensor fit: width)
    vf = math.atan(18 / 50 * res[1] / res[0])     # vertical half-FOV
    dist = max((hi.x - lo.x) / 2 / math.tan(hf), (hi.z - lo.z) / 2 / math.tan(vf)) * 1.08 + (hi.y - lo.y) / 2
    cam.location = c + d * dist
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = dist * 10
    dt = cam.data.clip_start * 25
    wf = dt * 36 / 50
    txt.data.size = wf * res[1] / res[0] * 0.06
    txt.location = (-wf * 0.47, -wf * res[1] / res[0] * 0.45, -dt)
    render_to(out)


def detail_glb(glb, out, cols, specs, tile_res=(640, 560)):
    """Close-ups: each spec is name@dx,dy,dz[@zoom[@zfrac]] (view direction, zoom < 1 moves closer, zfrac = focus height 0..1)."""
    reset()
    bpy.ops.import_scene.gltf(filepath=glb)
    roots = {o.name: o for o in bpy.context.scene.objects if o.parent is None}
    cam, planes, txt = studio(tile_res)
    tmp = tempfile.mkdtemp(prefix="detail_")
    tiles = []
    for i, spec in enumerate(specs):
        parts = spec.split("@")
        r = roots[parts[0]]
        d = [float(x) for x in parts[1].split(",")]
        zoom = float(parts[2]) if len(parts) > 2 else 1.0
        for o in roots.values():
            for x in [o] + list(o.children_recursive):
                x.hide_render = o is not r
        group = [r] + list(r.children_recursive)
        frame(cam, planes, txt, group, parts[0], kind_of(parts[0]), tile_res, dir_override=d)
        lo, hi = bounds(group)
        c = (lo + hi) / 2
        off = cam.location - c
        if len(parts) > 3:
            c.z = lo.z + (hi.z - lo.z) * float(parts[3])
        cam.location = c + off * zoom
        p = os.path.join(tmp, "d%02d.png" % i)
        render_to(p)
        tiles.append(p)
    compose(tiles, cols, tile_res, out)
    shutil.rmtree(tmp, ignore_errors=True)


def phsheet(ph_dir, out, cols, ids, tile_res=(640, 560)):
    reset()
    cam, planes, txt = studio(tile_res)
    ids = ids or sorted(i for i in os.listdir(ph_dir) if os.path.exists(os.path.join(ph_dir, i, i + ".glb")))
    tmp = tempfile.mkdtemp(prefix="phsheet_")
    tiles = []
    for i, mid in enumerate(ids):
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=os.path.join(ph_dir, mid, mid + ".glb"))
        group = [o for o in bpy.context.scene.objects if o not in before]
        lo, hi = bounds(group)
        sz = hi - lo
        frame(cam, planes, txt, group, "%s  %.2f x %.2f x %.2f m" % (mid, sz.x, sz.y, sz.z), kind_of(mid), tile_res)
        p = os.path.join(tmp, "t%02d.png" % i)
        render_to(p)
        tiles.append(p)
        for o in group:
            bpy.data.objects.remove(o, do_unlink=True)
    compose(tiles, cols, tile_res, out)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    mode = ARGV[0] if ARGV else "build"
    if mode == "build":
        build(ARGV[1] if len(ARGV) > 1 else "staging/env")
    elif mode == "convert":
        convert(ARGV[1])
    elif mode == "sheet":
        sheet_glb(ARGV[1], ARGV[2], int(ARGV[3]) if len(ARGV) > 3 else 4)
    elif mode == "row":
        row_glb(ARGV[1], ARGV[2])
    elif mode == "detail":
        detail_glb(ARGV[1], ARGV[2], int(ARGV[3]), ARGV[4:])
    elif mode == "phsheet":
        phsheet(ARGV[1], ARGV[2], int(ARGV[3]), ARGV[4:])
    print("ALL DONE")
