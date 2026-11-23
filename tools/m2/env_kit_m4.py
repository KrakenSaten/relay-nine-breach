# BREACH M4 mission-expansion kit: structure, pump station, switchgear hall, relay core (Blender 5.3, headless).
#   blender -b --factory-startup -P tools/m2/env_kit_m4.py -- build    <out_dir>   -> m4_kit.glb, kit_stats_m4.json, SOURCES.md
#   blender -b --factory-startup -P tools/m2/env_kit_m4.py -- previews <out_dir>   -> previews/*.png (area sheets + close-ups)
# Reuses tools/m2/env_kit.py and env_kit_m3.py read-only. X right, +Y forward, Z up, metres; "front" faces -Y.
import bpy, bmesh, math, os, sys, json, struct, re, tempfile, shutil
from mathutils import Vector, Matrix

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(os.path.abspath(sys.argv[sys.argv.index("-P") + 1]))
sys.path.insert(0, HERE)
import env_kit as K
import env_kit_m3 as M3
from env_kit import (box, cyl, torus, tube, prism, ring, bolts, cut, hazard_band, obj, fillet, M, R,
                     add_box, add_cyl, add_torus, add_tube, add_ring, add_revolve, add_prism)
finish, text_obj, lattice, gauge = M3.finish, M3.text_obj, M3.lattice, M3.gauge

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

K.MATS.update({
    "core_glow": ((0.6, 0.8, 1.0), 0.0, 0.3, (0.45, 0.75, 1.0), 7.0),   # existing game material (M1 Teslabot)
    "ceramic": ((0.40, 0.21, 0.11), 0.0, 0.16, None, 0),               # NEW: glazed porcelain insulators
})
K.WALL |= {"valve_wheel_station", "main_breaker_lever"}
K.CEIL |= {"core_bus_bar_4"}
K.TOP |= {"grate_floor_2", "water_channel_4", "catwalk_4"}

AREAS = {
    "structure": ["catwalk_4", "catwalk_rail_4", "stair_flight", "blast_door", "blast_door_frame", "crawl_duct_2", "grate_floor_2"],
    "pump_station": ["cooling_pump", "pipe_manifold_8", "valve_wheel_station", "water_channel_4", "pump_control_panel"],
    "switchgear": ["transformer_unit", "switchgear_lineup_4", "main_breaker_lever", "hv_cage_4"],
    "relay_core": ["relay_core_array", "capacitor_stack", "capacitor_stack_destroyed", "core_bus_bar_4"],
}
PIVOTS = {}


# ---------------------------------------------------------------- helpers
def grating(name, x0, x1, y0, y1, ztop, bars="X", pitch=0.034, depth=0.03, cross=0.1, m="galvanized"):
    """Open steel grating panel. Bearing bars (on edge) run along `bars`; every bar top is exactly at ztop."""
    bm = bmesh.new()
    if bars == "X":
        n = max(1, int(round((y1 - y0) / pitch)))
        for i in range(n + 1):
            add_box(bm, ((x0 + x1) / 2, y0 + (y1 - y0) * i / n, ztop - depth / 2), (x1 - x0, 0.004, depth))
        nc = max(1, int(round((x1 - x0) / cross)))
        for j in range(1, nc):
            add_box(bm, (x0 + (x1 - x0) * j / nc, (y0 + y1) / 2, ztop - 0.004), (0.005, y1 - y0, 0.008))
        for x in (x0 + 0.0025, x1 - 0.0025):
            add_box(bm, (x, (y0 + y1) / 2, ztop - depth / 2), (0.005, y1 - y0, depth))
    else:
        n = max(1, int(round((x1 - x0) / pitch)))
        for i in range(n + 1):
            add_box(bm, (x0 + (x1 - x0) * i / n, (y0 + y1) / 2, ztop - depth / 2), (0.004, y1 - y0, depth))
        nc = max(1, int(round((y1 - y0) / cross)))
        for j in range(1, nc):
            add_box(bm, ((x0 + x1) / 2, y0 + (y1 - y0) * j / nc, ztop - 0.004), (x1 - x0, 0.005, 0.008))
        for y in (y0 + 0.0025, y1 - 0.0025):
            add_box(bm, ((x0 + x1) / 2, y, ztop - depth / 2), (x1 - x0, 0.005, depth))
    return obj(name, m, bm)


def shed_profile(z0, z1, core, big, small, pitch):
    """Insulator contour: core cylinder with thin discs whose top slopes down to a rounded drip rim (alternating big/small)."""
    pts = [(core, z0)]
    z = z0 + pitch * 0.7
    k = 0
    while z + pitch * 0.4 < z1:
        rad = big if k % 2 == 0 else small
        drop = 0.18 * (rad - core)
        pts += [(core, z - 0.004), (rad * 0.96, z - drop - 0.004), (rad, z - drop), (rad * 0.97, z - drop + 0.006), (core, z + 0.012)]
        z += pitch
        k += 1
    pts.append((core, z1))
    sm = [abs(pts[i + 1][1] - pts[i][1]) > abs(pts[i + 1][0] - pts[i][0]) for i in range(len(pts) - 1)]
    return pts, sm


def insulator(bm, loc, z0, z1, core, big, small, pitch, segs=12, axis="Z", pre=None):
    prof, sm = shed_profile(z0, z1, core, big, small, pitch)
    add_revolve(bm, prof, segs, closed=False, smooth=sm, cap_ends=True, loc=loc, axis=axis, pre=pre)


def caged_lamp(prefix, pre, s=1.0):
    """Small caged bulkhead lamp hanging from a ceiling point (pre = matrix at the mount, -Z down). Glass mesh named 'globe'."""
    cyl(prefix + "_plate", (0, 0, -0.008 * s), 0.08 * s, 0.016 * s, "painted_dark", "Z", 24, bevel=0.002, pre=pre)
    cyl(prefix + "_housing", (0, 0, -0.03 * s), 0.064 * s, 0.03 * s, "painted_dark", "Z", 24, r2=0.072 * s, bevel=0.002, pre=pre)
    bm = bmesh.new()
    r = 0.05 * s
    vs = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=r)["verts"]
    for v in vs:
        if v.co.z > 0:
            xy = Vector((v.co.x, v.co.y))
            if xy.length > 1e-6:
                xy = xy.normalized() * r
            v.co = Vector((xy.x, xy.y, 0.035 * s * v.co.z / r))
    bmesh.ops.transform(bm, matrix=pre @ Matrix.Translation((0, 0, -0.08 * s)), verts=vs)
    for f in bm.faces:
        f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    obj("globe", "lamp_warm", bm)
    bm = bmesh.new()
    for k in range(6):
        a = 2 * math.pi * (k + 0.5) / 6
        prof = [(0.064, -0.042), (0.061, -0.06), (0.06, -0.095), (0.05, -0.124), (0.028, -0.142), (0.011, -0.15)]
        pts = [pre @ Vector((rr * s * math.cos(a), rr * s * math.sin(a), z * s)) for rr, z in prof]
        add_tube(bm, fillet(pts, 0.015 * s, 3), 0.003 * s, 5)
    add_torus(bm, (0, 0, -0.09 * s), 0.06 * s, 0.003 * s, "Z", 24, 5, pre=pre)
    add_torus(bm, (0, 0, -0.042 * s), 0.064 * s, 0.0035 * s, "Z", 24, 5, pre=pre)
    add_cyl(bm, (0, 0, -0.152 * s), 0.013 * s, 0.01 * s, "Z", 10, pre=pre)
    obj(prefix + "_cage", "painted_dark", bm)


def set_pivot(name, pivot):
    """Move an object's origin to `pivot` (root-local), keeping the mesh in place."""
    o = bpy.data.objects[name]
    o.data.transform(Matrix.Translation(-Vector(pivot)))
    o.location = pivot


def rename_glb_nodes(path, bases):
    """Blender forbids duplicate object names; restore e.g. 'screen.001' -> 'screen' in the exported GLB (separate subtrees)."""
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, total = struct.unpack_from("<III", data, 0)
    clen, ctype = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + clen].decode("utf-8"))
    rest = data[20 + clen:]
    pat = re.compile(r"^(%s)\.\d{3}$" % "|".join(bases))
    n = 0
    for node in js.get("nodes", []):
        mt = pat.match(node.get("name", ""))
        if mt:
            node["name"] = mt.group(1)
            n += 1
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    out = struct.pack("<III", magic, ver, 12 + 8 + len(jb) + len(rest)) + struct.pack("<II", len(jb), ctype) + jb + rest
    with open(path, "wb") as f:
        f.write(out)
    print("renamed %d duplicate node names" % n)


# ================================================================= STRUCTURE
def s_catwalk(off):
    # 4 m x 2 m grated catwalk along X. Walking surface: Z=0 over X -2..2, Y -1..1 (grating |Y|<=0.935, stringer top flanges 0.936..1.0).
    for i in range(4):
        x0 = -2.0 + i + 0.003
        grating("cw_grating", x0, x0 + 0.994, -0.935, 0.935, 0.0, bars="X")
    for x in (-1.5, -0.5, 0.5, 1.5):
        box("cw_crossmember", (x, 0, -0.09), (0.06, 1.872, 0.12), "galvanized", 0.002)
    for x in (-2.0 + 0.03, 2.0 - 0.03):
        box("cw_end_member", (x, 0, -0.09), (0.06, 1.872, 0.12), "galvanized", 0.002)
    for s in (-1, 1):
        prof = [(0.936, 0.0), (1.0, 0.0), (1.0, -0.01), (0.944, -0.01), (0.944, -0.18), (1.0, -0.18), (1.0, -0.19), (0.936, -0.19)]
        prism("cw_stringer", [(s * y, z) for y, z in prof], ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -2.0, 2.0, "galvanized")
        bolts("cw_splice_bolts", [(x, s * 0.947, z) for x in (-1.96, -1.9, 1.9, 1.96) for z in (-0.06, -0.13)], "steel", 0.009, 0.008, "Y")
        bolts("cw_clip_bolts", [(x, s * 0.931, -0.06) for x in (-1.5, -0.5, 0.5, 1.5)], "steel", 0.008, 0.008, "Y")
    return finish("catwalk_4", off, note="origin deck-top centre; walking surface Z=0 over X +-2.0, Y +-1.0")


def s_catwalk_rail(off):
    # 4 m safety railing along X, 1.1 m; origin bottom centre (mounting surface). Toe board on the -Y (walkway) side.
    for x in (-1.97, 0.0, 1.97):
        box("cr_post", (x, 0, 0.55), (0.05, 0.05, 1.08), "hazard", 0.003, segs=1)
        box("cr_base", (x, 0, 0.005), (0.12, 0.1, 0.01), "galvanized", 0.002)
        bolts("cr_anchor", [(x + dx, 0, 0.015) for dx in (-0.04, 0.04)], "steel", 0.009, 0.01, "Z")
        for z in (1.0787, 0.55):
            cyl("cr_fitting", (x, 0, z), 0.03, 0.07, "galvanized", "X", 16, bevel=0.003)
    for z in (1.0787, 0.55):
        cyl("cr_rail", (0, 0, z), 0.0213, 4.0, "hazard", "X", 16)
    box("cr_toeboard", (0, -0.031, 0.075), (4.0, 0.006, 0.15), "galvanized", 0.001)
    for x in (-1.97, 0.0, 1.97):
        box("cr_toe_clamp", (x, -0.03, 0.075), (0.05, 0.012, 0.08), "galvanized", 0.002)
    return finish("catwalk_rail_4", off, note="origin bottom centre; top rail top Z 1.1; toe board on -Y side")


def s_stair(off):
    # Steel stair rising 4.2 over 7.0 along +Y, 1.2 wide; origin bottom-front centre.
    # 21 risers of 0.2; tread i (1..20): top Z = 0.2*i, nosing (front edge) Y = 7/21*i -> nosings lie exactly on Z = 0.6*Y.
    rz, gy = 0.2, 7.0 / 21
    th = math.degrees(math.atan2(4.2, 7.0))
    tb_y, tb_k, tb_g, tb_p = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    bl = []
    for i in range(1, 21):
        z, y = i * rz, i * gy
        add_box(tb_y, (0, y + 0.02, z - 0.0125), (1.16, 0.04, 0.025))
        for k in range(8):
            add_box(tb_g, (0, y + 0.055 + k * 0.035, z - 0.0125), (1.16, 0.004, 0.025))
        for x in (-0.4, 0.0, 0.4):
            add_box(tb_g, (x, y + 0.17, z - 0.004), (0.005, 0.26, 0.008))
        for s in (-1, 1):
            add_box(tb_p, (s * 0.585, y + 0.15, z - 0.03), (0.01, 0.3, 0.06))
            bl.append((s * 0.6, y + 0.15, z - 0.03))
    obj("st_nosings", "hazard", tb_y)
    obj("st_treads", "galvanized", tb_g)
    obj("st_tread_plates", "galvanized", tb_p)
    bolts("st_bolts", bl, "steel", 0.009, 0.008, "X")
    poly = [(-0.1, 0.0), (0.4667, 0.0), (7.0, 3.92), (7.0, 4.2), (6.9, 4.2)]
    for s in (-1, 1):
        x = s * 0.596
        prism("st_stringer", poly, ((x - 0.006, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), 0.0, 0.012, "galvanized", 0.002, 1)
        xf = s * (0.602 + 0.0375)
        for (ya, za), (yb, zb) in (((-0.1, 0.0), (6.9, 4.2)), ((0.4667, 0.0), (7.0, 3.92))):
            L = math.hypot(yb - ya, zb - za)
            box("st_flange", (xf, (ya + yb) / 2, (za + zb) / 2 + (-0.005 if za == 0.0 and ya < 0 else 0.005)), (0.075, L, 0.01), "galvanized", 0.0015, rot=(th, 0, 0))
        # Railing: posts and rails 1.01 above the nosing line, horizontal extensions at both ends
        xr = s * 0.66
        for yp in (-0.05, 1.4, 2.85, 4.3, 5.75):
            z0 = max(0.0, 0.6 * yp + 0.06)
            box("st_post", (xr, yp, (z0 + 0.6 * max(yp, 0) + 1.01) / 2), (0.05, 0.05, 0.6 * max(yp, 0) + 1.01 - z0), "hazard", 0.003, segs=1)
        box("st_post_top", (xr, 7.25, 4.2 + 0.505), (0.05, 0.05, 1.01), "hazard", 0.003, segs=1)
        box("st_post_top_base", (xr, 7.25, 4.205), (0.12, 0.12, 0.01), "galvanized", 0.002)
        for dz in (1.01, 0.53):
            pts = fillet([(xr, -0.25, dz), (xr, 0.0, dz), (xr, 7.0, 4.2 + dz), (xr, 7.35, 4.2 + dz)], 0.15, 4)
            tube("st_rail", pts, 0.0213, "hazard", 12)
    return finish("stair_flight", off, note="origin bottom-front centre; nosings on Z=0.6*Y; treads 1.16 wide")


def s_blast_door(off):
    # Sliding blast door leaf 2.4 (X) x 3.2 (Z) x 0.3 (Y); origin bottom centre; leading (hazard) edge at -X; rams on the +Y face.
    leaf = box("bd_leaf", (0, 0, 1.6), (2.4, 0.3, 3.2), "door_steel", 0.01, segs=2, recess=(("-y", 0.18, 0.04), ("y", 0.18, 0.03)))
    cut(leaf, lambda bm: [add_box(bm, (0, 0, 2.3), (0.5, 0.6, 0.09))] + [add_box(bm, (x, 0, 0.06), (0.3, 0.2, 0.14)) for x in (-0.8, 0.8)])
    ang = math.degrees(math.atan2(2.7, 2.0))
    for sgn in (-1, 1):
        box("bd_brace", (0, -0.1275, 1.6), (3.36, 0.035, 0.12), "door_steel", 0.004, rot=(0, -sgn * ang, 0))
    box("bd_brace_h", (0, -0.1275, 1.6), (2.04, 0.035, 0.12), "door_steel", 0.004)
    box("bd_glass", (0, -0.02, 2.3), (0.5, 0.08, 0.09), "glass_lens", 0.0)
    for loc, size in (((0, -0.165, 2.36), (0.62, 0.03, 0.04)), ((0, -0.165, 2.24), (0.62, 0.03, 0.04)),
                      ((-0.29, -0.165, 2.3), (0.04, 0.03, 0.16)), ((0.29, -0.165, 2.3), (0.04, 0.03, 0.16))):
        box("bd_slot_bezel", loc, size, "steel", 0.003)
    for z in (2.42, 2.18):
        box("bd_shutter_rail", (0.3, -0.185, z), (1.2, 0.012, 0.02), "steel", 0.002)
    box("bd_shutter", (0.62, -0.195, 2.3), (0.52, 0.012, 0.2), "steel", 0.003)
    bpts = []
    for i in range(8):
        x = -0.85 + i * 0.27
        bpts += [(x, -0.152, 0.09), (x, -0.152, 3.11)]
    for i in range(11):
        z = 0.35 + i * 0.27
        bpts += [(1.11, -0.152, z), (-1.11, -0.152, z)]
    bolts("bd_rim_bolts", bpts, "steel", 0.016, 0.014, "Y", dome=True)
    hazard_band("bd_edge_hz", ((-1.2, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0)), -0.15, 0.15, 0.0, 3.2, sw=0.12)
    hazard_band("bd_face_hz", ((0, -0.15, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), -1.2, -1.04, 0.0, 3.2, sw=0.12)
    tube("bd_grab", fillet([(-0.9, -0.15, 0.95), (-0.9, -0.23, 0.95), (-0.9, -0.23, 1.6), (-0.9, -0.15, 1.6)], 0.04), 0.02, "steel", 10)
    for x in (-0.8, 0.8):
        cyl("bd_roller", (x, 0, 0.07), 0.07, 0.08, "painted_dark", "Y", 20, bevel=0.004)
        cyl("bd_axle", (x, 0, 0.07), 0.02, 0.2, "steel", "Y", 10)
    # Back face: hydraulic locking rams, dogs through the leading edge, manifold, hoses
    for z in (0.5, 2.75):
        cyl("bd_ram_barrel", (0.35, 0.235, z), 0.075, 1.0, "painted_dark", "X", 20, bevel=0.006)
        cyl("bd_ram_cap", (0.87, 0.235, z), 0.09, 0.05, "painted_dark", "X", 20, bevel=0.004)
        cyl("bd_ram_rod", (-0.45, 0.235, z), 0.035, 0.6, "steel", "X", 14)
        box("bd_clevis", (-0.78, 0.235, z), (0.08, 0.09, 0.1), "painted_dark", 0.006)
        box("bd_dog", (-1.0, 0.2, z), (0.44, 0.1, 0.16), "steel", 0.008)
        box("bd_dog_tip", (-1.235, 0.2, z), (0.07, 0.09, 0.14), "steel", 0.01)
        for x in (0.0, 0.7):
            box("bd_ram_bracket", (x, 0.18, z), (0.1, 0.06, 0.22), "painted_dark", 0.004)
        hazard_band("bd_dog_hz", ((0, 0.2505, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), -1.2, -0.85, z - 0.07, z + 0.07, sw=0.05)
    box("bd_manifold", (0.6, 0.21, 1.6), (0.3, 0.12, 0.25), "painted_dark", 0.01)
    cyl("bd_accumulator", (0.95, 0.24, 1.6), 0.08, 0.5, "painted_red", "Z", 16, bevel=0.03, segs=3)
    bm = bmesh.new()
    for z, x in ((0.5, 0.82), (2.75, 0.82), (0.5, -0.1), (2.75, -0.1)):
        add_tube(bm, fillet([(x, 0.3, z), (x, 0.32, (z + 1.6) / 2), (0.6, 0.29, 1.6)], 0.15), 0.014, 8)
    obj("bd_hoses", "cable_black", bm)
    text_obj("bd_stencil", "B-9", "board_white", (0.75, -0.1105, 2.95), 0.18)
    return finish("blast_door", off, note="origin bottom centre; leaf X +-1.2, Z 0..3.2, Y +-0.15 (rams to +0.31)")


def s_blast_door_frame(off):
    # Steel surround for a 2.6 x 3.4 opening in a 0.3 m wall; clear opening 2.3 x 3.15; sliding track on -Y, leaf parks at +X.
    for sx in (-1, 1):
        box("bf_jamb", (sx * 1.225, 0, 1.7), (0.15, 0.3, 3.4), "door_steel", 0.004, segs=1)
        hazard_band("bf_reveal_hz", ((sx * 1.15, 0, 0), (0, 1, 0), (0, 0, 1), (-sx, 0, 0)), -0.15, 0.15, 0.0, 2.2, sw=0.12)
        for sy in (-1, 1):
            box("bf_trim", (sx * 1.4, sy * 0.19, 1.75), (0.2, 0.08, 3.5), "door_steel", 0.006, segs=2)
        u0, u1 = sorted((sx * 1.3, sx * 1.5))
        hazard_band("bf_trim_hz", ((0, -0.2305, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), u0 + 0.01, u1 - 0.01, 0.0, 3.4, sw=0.12)
    box("bf_header", (0, 0, 3.275), (2.6, 0.3, 0.25), "door_steel", 0.004, segs=1)
    for sy in (-1, 1):
        box("bf_head_trim", (0, sy * 0.19, 3.6), (3.0, 0.08, 0.2), "door_steel", 0.006, segs=2)
    bolts("bf_trim_bolts", [(sx * 1.45, -0.231, z) for sx in (-1, 1) for z in (0.3, 1.1, 1.9, 2.7, 3.4)], "steel", 0.014, 0.01, "Y", dome=True)
    box("bf_track", (1.25, -0.42, 3.36), (5.5, 0.18, 0.2), "painted_dark", 0.006, segs=1, recess=(("-z", 0.04, 0.12),))
    for x in (-1.0, 0.25, 1.5, 2.75, 3.85):
        box("bf_track_bracket", (x, -0.29, 3.36), (0.12, 0.12, 0.16), "painted_dark", 0.004)
    for x in (-1.45, 3.95):
        box("bf_end_stop", (x, -0.42, 3.2), (0.1, 0.16, 0.14), "hazard", 0.008)
    box("bf_floor_rail", (1.25, -0.315, 0.005), (5.5, 0.06, 0.01), "steel", 0.002)
    for z in (0.5, 2.75):
        box("bf_lock_rx", (-1.36, -0.25, z), (0.14, 0.12, 0.24), "painted_dark", 0.008)
        box("bf_lock_slot", (-1.36, -0.311, z), (0.08, 0.002, 0.16), "cable_black", 0.0)
    box("bf_sign", (0.2, -0.2325, 3.6), (1.0, 0.005, 0.16), "hazard", 0.002)
    text_obj("bf_sign_txt", "BLAST DOOR", "painted_dark", (0.2, -0.2352, 3.6), 0.1)
    cyl("bf_beacon_base", (-0.75, -0.25, 3.6), 0.05, 0.04, "painted_dark", "Y", 16)
    cyl("bf_beacon", (-0.75, -0.3, 3.6), 0.045, 0.07, "led_amber", "Y", 16, r2=0.035, bevel=0.008)
    # Hydraulic power unit on the +Y wall face
    box("bf_hpu_tank", (1.9, 0.33, 0.45), (0.7, 0.3, 0.6), "painted_dark", 0.01, segs=2)
    cyl("bf_hpu_motor", (1.75, 0.33, 0.95), 0.12, 0.35, "painted_grey", "Z", 20, bevel=0.006)
    box("bf_hpu_valves", (2.1, 0.3, 0.86), (0.22, 0.16, 0.18), "painted_dark", 0.006)
    bm = bmesh.new()
    for i in range(3):
        add_tube(bm, fillet([(2.0 + i * 0.05, 0.3, 0.95), (2.0 + i * 0.05, 0.3, 1.4), (1.5, 0.18, 2.4)], 0.2), 0.013, 8)
    obj("bf_hpu_hoses", "cable_black", bm)
    return finish("blast_door_frame", off, note="origin bottom centre of opening; opening X +-1.3, Z 0..3.4; clear 2.3 x 3.15")


def s_crawl_duct(off):
    # Walk-in maintenance duct, 2 m along +Y; interior 1.9 W x 1.15 H; floor top Z=0; origin floor centre of near end (Y=0).
    L, hw, H = 2.0, 0.95, 1.15
    box("cd_floor", (0, L / 2, -0.005), (2 * hw, L, 0.01), "diamond_plate", 0.001)
    box("cd_floor_seam", (0, L / 2, -0.0002), (2 * hw, 0.004, 0.0004), "painted_dark", 0.0)
    box("cd_bottom", (0, L / 2, -0.03), (2 * hw + 0.06, L, 0.02), "galvanized", 0.0)
    fr = ((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    for s in (-1, 1):
        pts = []
        for k in range(5):
            b = k * 0.23
            pts += [(0.0, b), (0.0, b + 0.07), (0.025, b + 0.1), (0.025, b + 0.13), (0.0, b + 0.16)]
        pts.append((0.0, H + 0.03))
        prof = [(s * (hw + u), v) for u, v in pts] + [(s * (hw + u + 0.003), v) for u, v in reversed(pts)]
        prism("cd_wall", prof, fr, 0.0, L, "galvanized")
    pts = []
    for k in range(8):
        b = -hw - 0.03 + k * 0.24
        pts += [(b, 0.0), (b + 0.08, 0.0), (b + 0.11, 0.025), (b + 0.14, 0.025), (b + 0.17, 0.0)]
    pts.append((hw + 0.03, 0.0))
    prof = [(u, H + v) for u, v in pts] + [(u, H + v + 0.003) for u, v in reversed(pts)]
    prism("cd_ceiling", prof, fr, 0.0, L, "galvanized")
    for sx in (-1, 1):
        box("cd_corner", (sx * (hw - 0.015), L / 2, H - 0.015), (0.03, L, 0.03), "galvanized", 0.0015)
    for y, d in ((0.006, 0.012), (L - 0.006, 0.012), (L / 2, 0.03)):
        for loc, size in (((-hw - 0.06, y, H / 2), (0.06, d, H + 0.18)), ((hw + 0.06, y, H / 2), (0.06, d, H + 0.18)),
                          ((0, y, H + 0.06), (2 * hw + 0.18, d, 0.06)), ((0, y, -0.06), (2 * hw + 0.18, d, 0.06))):
            box("cd_flange", loc, size, "galvanized", 0.002)
    bolts("cd_flange_bolts", [(sx * (hw + 0.065), y, z) for sx in (-1, 1) for y in (0.012, L - 0.012) for z in (0.2, 0.6, 1.0)], "steel", 0.01, 0.01, "Y")
    caged_lamp("cd_lamp", Matrix.Translation((0, L / 2, H)), 1.0)
    tube("cd_conduit", [(-0.82, 0.0, H - 0.04), (-0.82, L, H - 0.04)], 0.012, "galvanized", 8)
    box("cd_jbox", (-0.82, L / 2, H - 0.05), (0.08, 0.08, 0.05), "galvanized", 0.003)
    tube("cd_lamp_feed", [(-0.78, L / 2, H - 0.04), (-0.08, L / 2, H - 0.012)], 0.008, "galvanized", 6)
    return finish("crawl_duct_2", off, keep=("globe",), note="origin floor centre of near end; walking surface Z=0, X +-0.95, Y 0..2")


def s_grate_floor(off):
    # 2 x 2 floor grate over a 1.6 m wide channel along Y; origin top centre (grating top Z=0).
    for y0 in (-0.997, 0.003):
        grating("gf_grating", -0.997, 0.997, y0, y0 + 0.994, 0.0, bars="X")
    for s in (-1, 1):
        box("gf_frame_x", (s * 1.01, 0, -0.025), (0.02, 2.04, 0.05), "galvanized", 0.001)
        box("gf_frame_y", (0, s * 1.01, -0.025), (2.0, 0.02, 0.05), "galvanized", 0.001)
        box("gf_wall", (s * 0.9, 0, -0.33), (0.2, 2.0, 0.6), "concrete", 0.01, segs=1)
        box("gf_ledge", (s * 0.79, 0, -0.04), (0.03, 2.0, 0.02), "galvanized", 0.001)
    box("gf_channel_floor", (0, 0, -0.62), (1.6, 2.0, 0.04), "concrete", 0.0)
    box("gf_water", (0, 0, -0.5), (1.6, 2.0, 0.002), "glass_lens", 0.0)
    cyl("gf_pipe", (0.35, 0, -0.38), 0.12, 2.0, "painted_grey", "Y", 24)
    for y in (-0.6, 0.6):
        box("gf_pipe_saddle", (0.35, y, -0.53), (0.2, 0.06, 0.06), "painted_dark", 0.003)
    return finish("grate_floor_2", off, note="origin top centre; grating top Z=0 over X,Y +-1.0; channel to Z -0.64")


# ================================================================= PUMP STATION
def p_cooling_pump(off):
    # Horizontal end-suction centrifugal pump + motor on a skid ~4.5 x 1.4 x 2.1; origin bottom centre of the skid; motor at +X.
    I = [(-0.1, 0.0), (0.1, 0.0), (0.1, 0.016), (0.008, 0.016), (0.008, 0.234), (0.1, 0.234), (0.1, 0.25), (-0.1, 0.25), (-0.1, 0.234), (-0.008, 0.234), (-0.008, 0.016), (-0.1, 0.016)]
    for s in (-1, 1):
        prism("cp_skid_rail", [(y + s * 0.55, z) for y, z in I], ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -1.85, 2.25, "painted_dark", 0.002, 1)
        bolts("cp_anchor", [(x, s * 0.55 + dy, 0.262) for x in (-1.7, -0.6, 0.6, 2.1) for dy in (-0.06, 0.06)], "steel", 0.014, 0.024, "Z")
    for x in (-1.75, -0.6, 0.5, 2.15):
        box("cp_cross", (x, 0, 0.125), (0.1, 1.0, 0.2), "painted_dark", 0.003)
    box("cp_deck", (0.0, 0, 0.255), (0.8, 1.2, 0.01), "diamond_plate", 0.002)
    # Motor
    MC = Vector((1.15, 0, 0.92))
    cyl("cp_motor", tuple(MC), 0.5, 1.5, "crate_green", "X", 40, bevel=0.01, segs=2)
    bm = bmesh.new()
    for k in range(32):
        a = 2 * math.pi * (k + 0.5) / 32
        if a < 0.5 or a > 2 * math.pi - 0.5:
            continue
        add_box(bm, (MC.x, 0.525 * math.sin(a), MC.z + 0.525 * math.cos(a)), (1.4, 0.012, 0.05), rot=(-math.degrees(a), 0, 0))
    obj("cp_motor_fins", "crate_green", bm)
    for x in (0.38, 1.92):
        cyl("cp_endshield", (x, 0, MC.z), 0.47, 0.08, "crate_green", "X", 40, bevel=0.01)
    cyl("cp_fan_cowl", (2.1, 0, MC.z), 0.48, 0.28, "crate_green", "X", 40, bevel=0.012, segs=2)
    bm = bmesh.new()
    for rr in (0.12, 0.22, 0.32, 0.42):
        add_torus(bm, (2.245, 0, MC.z), rr, 0.008, "X", 32, 5)
    for k in range(8):
        a = math.pi * k / 4
        add_box(bm, (2.245, 0.21 * math.sin(a), MC.z + 0.21 * math.cos(a)), (0.012, 0.012, 0.42), rot=(-math.degrees(a), 0, 0))
    obj("cp_cowl_grille", "painted_dark", bm)
    for x in (0.55, 1.75):
        for s in (-1, 1):
            box("cp_motor_foot", (x, s * 0.33, 0.37), (0.22, 0.14, 0.26), "crate_green", 0.008)
    box("cp_tbox", (1.0, -0.12, 1.5), (0.42, 0.36, 0.26), "crate_green", 0.012, segs=2, recess=(("z", 0.03, -0.006),))
    cyl("cp_tbox_gland", (1.0, -0.31, 1.45), 0.04, 0.04, "steel", "Y", 8)
    tube("cp_motor_conduit", fillet([(1.0, -0.33, 1.45), (1.0, -0.62, 1.45), (1.0, -0.62, 0.3), (1.2, -0.62, -0.05)], 0.12), 0.035, "galvanized", 10)
    for x in (0.75, 1.55):
        torus("cp_lift_eye", (x, 0, 1.46), 0.045, 0.012, "steel", "X", 16, 6)
    box("cp_motor_plate", (2.1, -0.484, MC.z), (0.2, 0.006, 0.12), "galvanized", 0.001)
    text_obj("cp_motor_plate_txt", "450 kW  6.6 kV", "painted_dark", (2.1, -0.4875, MC.z), 0.02)
    # Coupling guard and bearing frame
    cyl("cp_guard", (0.15, 0, MC.z), 0.24, 0.42, "hazard", "X", 24, bevel=0.01, segs=2)
    bm = bmesh.new()
    for k in range(5):
        add_box(bm, (0.0 + k * 0.075, -0.24, MC.z), (0.035, 0.01, 0.2))
    obj("cp_guard_slots", "painted_dark", bm)
    for s in (-1, 1):
        box("cp_guard_foot", (0.15, s * 0.18, 0.5), (0.3, 0.04, 0.5), "hazard", 0.004)
    cyl("cp_bearing_frame", (-0.4, 0, MC.z), 0.17, 0.5, "painted_grey", "X", 24, bevel=0.008)
    box("cp_bearing_foot", (-0.4, 0, 0.5), (0.4, 0.5, 0.5), "painted_grey", 0.008, segs=1)
    cyl("cp_oiler", (-0.3, 0.0, 1.13), 0.03, 0.08, "glass_lens", "Z", 12)
    # Volute casing (spiral sweep) around the pump axis
    C = Vector((-1.05, 0, MC.z))
    cyl("cp_casing_core", tuple(C), 0.44, 0.34, "painted_grey", "X", 32, bevel=0.01)
    bm = bmesh.new()
    rings = []
    Kn, segs = 40, 14
    for k in range(Kn + 1):
        t = k / Kn
        thv = 2 * math.pi * 0.93 * t
        radial = Vector((0, math.sin(thv), math.cos(thv)))
        Rc, rr = 0.4 + 0.18 * t, 0.1 + 0.13 * t
        cen = C + radial * Rc
        rings.append([bm.verts.new(cen + radial * (rr * math.cos(2 * math.pi * j / segs)) + Vector((1, 0, 0)) * (rr * 1.15 * math.sin(2 * math.pi * j / segs))) for j in range(segs)])
    for k in range(Kn):
        for j in range(segs):
            j2 = (j + 1) % segs
            f = bm.faces.new((rings[k][j], rings[k][j2], rings[k + 1][j2], rings[k + 1][j]))
            f.smooth = True
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    obj("cp_volute", "painted_grey", bm)
    tend = 2 * math.pi * 0.93
    dend = C + Vector((0, math.sin(tend), math.cos(tend))) * 0.58
    cyl("cp_feet_casing", (C.x, 0, 0.42), 0.15, 0.4, "painted_grey", "Z", 16)
    box("cp_casing_foot", (C.x, 0, 0.3), (0.4, 0.6, 0.1), "painted_grey", 0.006)
    # Suction (axial, -X) and discharge (riser) pipes, both turning down into the floor
    tube("cp_suction", fillet([(C.x - 0.15, 0, C.z), (-2.05, 0, C.z), (-2.05, 0, -0.12)], 0.35, 6), 0.2, "painted_grey", 20)
    tube("cp_discharge", fillet([(dend.x, dend.y, dend.z - 0.05), (dend.x, dend.y, 1.95), (-2.05, -0.45, 1.95), (-2.05, -0.45, -0.12)], 0.3, 6), 0.15, "painted_grey", 18)
    bm = bmesh.new()
    flanges = [((-1.55, 0, C.z), "X", 0.32, 0.2), ((dend.x, dend.y, 1.5), "Z", 0.26, 0.15), ((-2.05, 0, 0.03), "Z", 0.32, 0.2), ((-2.05, -0.45, 0.03), "Z", 0.26, 0.15)]
    nuts = {"X": [], "Z": []}
    for loc, ax, ro, rp in flanges:
        add_cyl(bm, loc, ro, 0.045, ax, 32)
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            rb = (ro + rp) / 2
            p = Vector(loc) + (Vector((0, rb * math.sin(a), rb * math.cos(a))) if ax == "X" else Vector((rb * math.cos(a), rb * math.sin(a), 0)))
            nuts[ax] += [tuple(p + Vector((0.03, 0, 0) if ax == "X" else (0, 0, 0.03))), tuple(p - Vector((0.03, 0, 0) if ax == "X" else (0, 0, 0.03)))]
    obj("cp_flanges", "painted_grey", bm, 0.003, 1)
    bolts("cp_flange_nuts_x", nuts["X"], "steel", 0.018, 0.014, "X")
    bolts("cp_flange_nuts_z", nuts["Z"], "steel", 0.018, 0.014, "Z")
    # Butterfly valve with gear operator on the discharge run
    vx = -1.55
    cyl("cp_valve_body", (vx, -0.33, 1.95), 0.22, 0.12, "painted_dark", "X", 24, bevel=0.006, rot=(0, 0, -11))
    box("cp_valve_gearbox", (vx, -0.33, 2.22), (0.16, 0.16, 0.14), "painted_dark", 0.01)
    torus("cp_valve_wheel", (vx, -0.48, 2.22), 0.12, 0.012, "painted_red", "Y", 20, 6)
    cyl("cp_valve_stem", (vx, -0.43, 2.22), 0.015, 0.1, "steel", "Y", 8)
    face, ticks, needle, bez = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    gauge(face, ticks, needle, bez, Matrix.Translation((dend.x, dend.y - 0.17, 0)), 0.0, 1.72, 0.06, 0.55)
    obj("cp_g_bez", "painted_dark", bez)
    obj("cp_g_face", "board_white", face)
    obj("cp_g_ticks", "painted_dark", ticks)
    obj("cp_g_needle", "painted_red", needle)
    tube("cp_g_nipple", [(dend.x, dend.y - 0.14, 1.72), (dend.x, dend.y - 0.17 + 0.0, 1.72)], 0.012, "steel", 8)
    box("cp_pump_plate", (C.x, -0.36, 0.56), (0.3, 0.006, 0.12), "galvanized", 0.001)
    text_obj("cp_pump_plate_txt", "CW PUMP 2", "painted_dark", (C.x, -0.3635, 0.56), 0.04)
    prism("cp_rot_arrow", [(-0.04, 0.0), (0.04, 0.0), (0.0, 0.07)], ((C.x - 0.18, 0, C.z + 0.3), (0, 1, 0), (0, 0, 1), (-1, 0, 0)), 0.0, 0.004, "painted_red")
    return finish("cooling_pump", off, note="origin bottom centre of skid; motor at +X; pipes enter the floor at X -2.05")


def p_manifold(off):
    # 8 m cooling-water header (dia 0.5) along X with 3 valved branch drops; origin at the centre on the pipe axis.
    cyl("pm_header", (0, 0, 0), 0.25, 8.0, "painted_grey", "X", 24)
    bm = bmesh.new()
    nx, nz = [], []
    for s in (-1, 1):
        add_cyl(bm, (s * 3.98, 0, 0), 0.36, 0.04, "X", 24)
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            nx.append((s * 3.95, 0.31 * math.sin(a), 0.31 * math.cos(a)))
    for x in (-2.5, 0.0, 2.5):
        add_cyl(bm, (x, 0, -0.27), 0.19, 0.06, "Z", 24)
        for z in (-0.68, -0.92, -1.58):
            add_cyl(bm, (x, 0, z), 0.24, 0.04, "Z", 20)
            for k in range(6):
                a = 2 * math.pi * (k + 0.5) / 6
                nz.append((x + 0.2 * math.cos(a), 0.2 * math.sin(a), z + 0.03))
    obj("pm_flanges", "painted_grey", bm, 0.002, 1)
    bolts("pm_nuts_x", nx, "steel", 0.02, 0.016, "X")
    bolts("pm_nuts_z", nz, "steel", 0.016, 0.014, "Z")
    for x in (-2.5, 0.0, 2.5):
        cyl("pm_branch_a", (x, 0, -0.47), 0.15, 0.4, "painted_grey", "Z", 16)
        cyl("pm_branch_b", (x, 0, -1.25), 0.15, 0.66, "painted_grey", "Z", 16)
        cyl("pm_valve_body", (x, 0, -0.8), 0.21, 0.2, "painted_dark", "Z", 20, bevel=0.01, segs=1)
        cyl("pm_bonnet", (x, -0.27, -0.8), 0.09, 0.3, "painted_dark", "Y", 12, bevel=0.006, segs=1)
        cyl("pm_stem", (x, -0.48, -0.8), 0.018, 0.16, "steel", "Y", 8)
        torus("pm_wheel", (x, -0.56, -0.8), 0.2, 0.014, "painted_red", "Y", 20, 5)
        bm = bmesh.new()
        for k in range(5):
            a = 2 * math.pi * k / 5
            add_box(bm, (x + 0.1 * math.cos(a), -0.56, -0.8 + 0.1 * math.sin(a)), (0.2, 0.012, 0.016), rot=(0, -math.degrees(a), 0))
        add_cyl(bm, (x, -0.56, -0.8), 0.03, 0.04, "Y", 12)
        obj("pm_spokes", "painted_red", bm)
        box("pm_tag", (x + 0.12, -0.36, -0.95), (0.08, 0.003, 0.05), "galvanized", 0.0)
    for x in (-1.25, 1.25):
        ring("pm_hanger_band", (x, 0, 0), 0.25, 0.262, 0.05, "galvanized", "X", 24)
        for s in (-1, 1):
            cyl("pm_hanger_rod", (x, s * 0.29, 0.62), 0.012, 1.24, "steel", "Z", 8)
            box("pm_hanger_ear", (x, s * 0.275, 0.0), (0.05, 0.04, 0.06), "galvanized", 0.003)
        box("pm_beam_clamp", (x, 0, 1.24), (0.14, 0.7, 0.06), "painted_dark", 0.004)
    ring("pm_id_band", (-3.2, 0, 0), 0.25, 0.2515, 0.12, "hazard", "X", 24)
    ring("pm_id_band2", (3.2, 0, 0), 0.25, 0.2515, 0.12, "hazard", "X", 24)
    prism("pm_flow_arrow", [(-0.12, -0.05), (0.06, -0.05), (0.06, -0.09), (0.16, 0.0), (0.06, 0.09), (0.06, 0.05), (-0.12, 0.05)],
          ((-2.8, -0.2505, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, 0.003, "painted_dark")
    return finish("pipe_manifold_8", off, note="origin centre on the pipe axis; branch flanges at Z -1.58 (X -2.5, 0, 2.5)")


def p_valve_station(off):
    # Wall valve station: U-pipe out of the wall, gate valve with rising stem and 0.6 m handwheel, gauge; back-face origin.
    tube("vs_pipe", fillet([(-1.0, 0.05, 0), (-1.0, -0.3, 0), (1.0, -0.3, 0), (1.0, 0.05, 0)], 0.18, 6), 0.1, "painted_grey", 16)
    for x in (-1.0, 1.0):
        ring("vs_escutcheon", (x, -0.005, 0), 0.1, 0.16, 0.01, "steel", "Y", 24)
    bm = bmesh.new()
    nx = []
    for x in (-0.19, 0.19):
        add_cyl(bm, (x, -0.3, 0), 0.2, 0.035, "X", 24)
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            nx.append((x + (0.025 if x > 0 else -0.025), -0.3 + 0.16 * math.sin(a), 0.16 * math.cos(a)))
    obj("vs_flanges", "painted_grey", bm, 0.002, 1)
    bolts("vs_nuts", nx, "steel", 0.015, 0.012, "X")
    cyl("vs_body", (0, -0.3, 0), 0.18, 0.34, "painted_dark", "X", 24, bevel=0.012)
    cyl("vs_bonnet", (0, -0.55, 0), 0.1, 0.22, "painted_dark", "Y", 20, bevel=0.008)
    for s in (-1, 1):
        box("vs_yoke", (s * 0.07, -0.74, 0), (0.025, 0.2, 0.04), "painted_dark", 0.005)
    box("vs_yoke_top", (0, -0.84, 0), (0.18, 0.03, 0.06), "painted_dark", 0.006)
    cyl("vs_stem", (0, -0.86, 0), 0.02, 0.32, "steel", "Y", 10)
    torus("vs_wheel", (0, -0.9, 0), 0.3, 0.022, "painted_red", "Y", 32, 8)
    bm = bmesh.new()
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        add_box(bm, (0.15 * math.cos(a), -0.9, 0.15 * math.sin(a)), (0.3, 0.016, 0.022), rot=(0, -math.degrees(a), 0))
    add_cyl(bm, (0, -0.9, 0), 0.05, 0.05, "Y", 16)
    obj("vs_spokes", "painted_red", bm)
    cyl("vs_knob", (0.3 * math.cos(0.3), -0.95, 0.3 * math.sin(0.3)), 0.02, 0.1, "painted_dark", "Y", 10)
    cyl("vs_nipple", (0.5, -0.3, 0.17), 0.015, 0.14, "steel", "Z", 8)
    box("vs_gauge_tee", (0.5, -0.3, 0.25), (0.04, 0.04, 0.04), "steel", 0.003)
    face, ticks, needle, bez = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    gauge(face, ticks, needle, bez, Matrix.Translation((0, -0.33, 0)), 0.5, 0.34, 0.075, 0.62)
    obj("vs_g_bez", "painted_dark", bez)
    obj("vs_g_face", "board_white", face)
    obj("vs_g_ticks", "painted_dark", ticks)
    obj("vs_g_needle", "painted_red", needle)
    for x in (-0.65, 0.65):
        box("vs_bracket", (x, -0.15, -0.13), (0.05, 0.3, 0.05), "galvanized", 0.002)
        ring("vs_clamp", (x, -0.3, 0), 0.1, 0.108, 0.04, "galvanized", "X", 20)
        box("vs_wallplate", (x, -0.005, -0.13), (0.1, 0.01, 0.14), "galvanized", 0.002)
    tube("vs_tag_chain", [(0.07, -0.74, -0.03), (0.09, -0.75, -0.16)], 0.003, "steel", 4)
    cyl("vs_tag", (0.09, -0.75, -0.2), 0.04, 0.003, "galvanized", "Y", 16)
    text_obj("vs_tag_txt", "V-9B", "painted_dark", (0.09, -0.7525, -0.2), 0.018)
    return finish("valve_wheel_station", off, note="back-face origin on wall plane, valve centre height; handwheel at Y -0.9")


def p_water_channel(off):
    # 4 m sunken cooling-water channel (1.0 wide, 0.8 deep) along X with grating cover and hazard edges; origin top centre.
    for i in range(4):
        x0 = -2.0 + i + 0.003
        grating("wc_grating", x0, x0 + 0.994, -0.5, 0.5, 0.0, bars="Y")
    for s in (-1, 1):
        box("wc_wall", (0, s * 0.6, -0.42), (4.0, 0.2, 0.84), "concrete", 0.006, segs=1)
        box("wc_nosing", (0, s * 0.51, -0.025), (4.0, 0.02, 0.05), "galvanized", 0.001)
        box("wc_ledge", (0, s * 0.49, -0.04), (4.0, 0.02, 0.02), "galvanized", 0.0)
        v0, v1 = sorted((s * 0.53, s * 0.68))
        hazard_band("wc_edge_hz", ((0, 0, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), -2.0, 2.0, v0, v1, sw=0.1)
    box("wc_floor", (0, 0, -0.82), (4.0, 1.0, 0.04), "concrete", 0.0)
    box("wc_water", (0, 0, -0.56), (4.0, 1.0, 0.002), "glass_lens", 0.0)
    box("wc_silt", (0, 0, -0.79), (4.0, 1.0, 0.02), "painted_dark", 0.0)
    cyl("wc_pipe", (0, 0.25, -0.42), 0.1, 4.0, "painted_grey", "X", 20)
    for x in (-1.2, 1.2):
        box("wc_pipe_bracket", (x, 0.25, -0.55), (0.06, 0.24, 0.06), "galvanized", 0.002)
        ring("wc_pipe_clamp", (x, 0.25, -0.42), 0.1, 0.107, 0.04, "galvanized", "X", 20)
    return finish("water_channel_4", off, note="origin top centre; grating top Z=0 over Y +-0.5; hazard bands on the floor to Y +-0.68")


def p_control_panel(off):
    # Free-standing pump control panel 0.8 x 0.45 x 1.94; origin bottom centre; front -Y. Status HMI mesh named 'screen'.
    box("pc_plinth", (0, 0, 0.05), (0.76, 0.42, 0.1), "painted_dark", 0.003)
    box("pc_body", (0, 0, 1.0), (0.8, 0.45, 1.8), "painted_grey", 0.006, segs=1, grooves=(("x", 0.04, 0.004, 0.002), ("-x", 0.04, 0.004, 0.002)))
    box("pc_door", (0, -0.231, 1.0), (0.76, 0.012, 1.72), "painted_grey", 0.004, segs=1, recess=(("-y", 0.03, -0.003),))
    box("pc_hood", (0, -0.02, 1.92), (0.86, 0.52, 0.04), "painted_grey", 0.004)
    F = -0.2405
    face, ticks, needle, bez = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    for i, x in enumerate((-0.22, 0.0, 0.22)):
        gauge(face, ticks, needle, bez, Matrix.Translation((0, F, 0)), x, 1.58, 0.07, 0.3 + 0.2 * i)
    obj("pc_g_bez", "painted_dark", bez)
    obj("pc_g_face", "board_white", face)
    obj("pc_g_ticks", "painted_dark", ticks)
    obj("pc_g_needle", "painted_red", needle)
    box("pc_hmi_bezel", (0, F - 0.004, 1.32), (0.36, 0.008, 0.24), "painted_dark", 0.004)
    scr = box("screen", (0, F - 0.0085, 1.33), (0.3, 0.002, 0.18), "screen", 0.0)
    for i, m in enumerate(("led_green", "led_green", "led_amber", "led_red", "led_amber")):
        x = -0.24 + i * 0.12
        cyl("pc_lamp_collar", (x, F - 0.004, 1.13), 0.016, 0.008, "steel", "Y", 16)
        cyl("pc_lamp", (x, F - 0.01, 1.13), 0.011, 0.008, m, "Y", 16)
        box("pc_lamp_tag", (x, F - 0.0015, 1.085), (0.08, 0.003, 0.022), "galvanized", 0.0)
    for i, x in enumerate((-0.24, -0.12, 0.0)):
        cyl("pc_sel_skirt", (x, F - 0.0015, 0.98), 0.025, 0.003, "galvanized", "Y", 20)
        cyl("pc_sel", (x, F - 0.012, 0.98), 0.018, 0.02, "painted_dark", "Y", 16, bevel=0.002)
        box("pc_sel_ptr", (x, F - 0.023, 0.98), (0.006, 0.004, 0.03), "painted_dark", 0.0, rot=(0, (i - 1) * 40, 0))
    cyl("pc_key", (0.12, F - 0.008, 0.98), 0.016, 0.012, "steel", "Y", 16)
    cyl("pc_start", (-0.2, F - 0.01, 0.84), 0.022, 0.016, "led_green", "Y", 16, bevel=0.003)
    cyl("pc_stop", (-0.08, F - 0.01, 0.84), 0.022, 0.016, "painted_red", "Y", 16, bevel=0.003)
    cyl("pc_estop_collar", (0.22, F - 0.006, 0.84), 0.045, 0.012, "hazard", "Y", 24)
    cyl("pc_estop", (0.22, F - 0.025, 0.84), 0.034, 0.03, "painted_red", "Y", 24, r2=0.028, bevel=0.006)
    box("pc_title", (0, F - 0.002, 1.79), (0.4, 0.004, 0.07), "board_white", 0.001)
    text_obj("pc_title_txt", "CW PUMP 2", "painted_dark", (0, F - 0.0045, 1.79), 0.04)
    box("pc_handle", (0.33, F - 0.015, 1.0), (0.025, 0.02, 0.16), "painted_dark", 0.006, segs=2)
    for z in (0.35, 1.6):
        cyl("pc_hinge", (-0.383, -0.235, z), 0.008, 0.07, "steel", "Z", 12)
    bm = bmesh.new()
    for i in range(8):
        add_box(bm, (0, F - 0.0012, 0.25 + i * 0.035), (0.5, 0.003, 0.012))
    obj("pc_louvres", "painted_dark", bm)
    for x in (-0.2, 0.2):
        cyl("pc_conduit", (x, 0.12, 0.0), 0.025, 0.2, "galvanized", "Z", 12)
    return finish("pump_control_panel", off, keep=(scr.name,), note="origin bottom centre; front -Y")


# ================================================================= SWITCHGEAR HALL
def w_transformer(off):
    # 132/33 kV power transformer ~3.7 (X) x 2.5 (Y) x 4.2 (Z); origin bottom centre. HV bushings (ceramic) on top.
    I = [(-0.1, 0.0), (0.1, 0.0), (0.1, 0.016), (0.008, 0.016), (0.008, 0.234), (0.1, 0.234), (0.1, 0.25), (-0.1, 0.25), (-0.1, 0.234), (-0.008, 0.234), (-0.008, 0.016), (-0.1, 0.016)]
    for s in (-1, 1):
        prism("tr_skid", [(y + s * 0.45, z) for y, z in I], ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -1.6, 1.6, "painted_dark", 0.002, 1)
        for x in (-1.55, 1.55):
            box("tr_jack_pad", (x, s * 0.45, 0.28), (0.12, 0.25, 0.06), "painted_dark", 0.004)
    box("tr_tank", (0, 0, 1.45), (3.0, 1.3, 2.4), "painted_grey", 0.012, segs=1)
    box("tr_cover", (0, 0, 2.68), (3.1, 1.4, 0.06), "painted_grey", 0.006, segs=1)
    bp = [(x, y, 2.715) for x in [-1.5 + i * 0.25 for i in range(13)] for y in (-0.66, 0.66)] + [(x, y, 2.715) for x in (-1.5, 1.5) for y in (-0.4, -0.13, 0.13, 0.4)]
    bolts("tr_cover_bolts", bp, "steel", 0.016, 0.014, "Z")
    for sx in (-1, 1):
        for y in (-0.45, 0.0, 0.45):
            box("tr_end_rib", (sx * 1.53, y, 1.45), (0.06, 0.08, 2.3), "painted_grey", 0.004)
    # Radiator banks on both long sides
    fins = bmesh.new()
    hdr = bmesh.new()
    for s in (-1, 1):
        yb = s * 0.95
        for xb in (-1.08, -0.36, 0.36, 1.08):
            for k in range(15):
                add_box(fins, (xb - 0.315 + k * 0.045, yb, 1.4), (0.008, 0.52, 1.7))
            for z in (0.5, 2.3):
                add_cyl(hdr, (xb, yb, z), 0.05, 0.72, "X", 16)
                add_cyl(hdr, (xb, s * 0.8, z), 0.05, 0.3, "Y", 16)
                add_cyl(hdr, (xb, s * 0.7, z), 0.075, 0.06, "Y", 16)
    obj("tr_fins", "painted_grey", fins)
    obj("tr_headers", "painted_grey", hdr)
    # HV bushings with turrets, terminals
    ins = bmesh.new()
    for x in (-0.7, 0.0, 0.7):
        cyl("tr_turret", (x, -0.3, 2.81), 0.18, 0.2, "painted_grey", "Z", 24, bevel=0.006)
        cyl("tr_bush_flange", (x, -0.3, 2.93), 0.15, 0.04, "painted_grey", "Z", 24, bevel=0.004)
        insulator(ins, (x, -0.3, 0), 2.95, 3.98, 0.075, 0.17, 0.13, 0.09, 16)
        cyl("tr_bush_cap", (x, -0.3, 4.02), 0.08, 0.08, "steel", "Z", 20, bevel=0.01)
        cyl("tr_terminal", (x, -0.3, 4.1), 0.03, 0.1, "copper", "Z", 12)
        box("tr_term_pad", (x, -0.3, 4.16), (0.1, 0.012, 0.08), "copper", 0.003)
    obj("tr_bushings", "ceramic", ins)
    # Conservator, Buchholz pipe, oil gauge, breather
    bm = bmesh.new()
    add_revolve(bm, [(0.002, -0.8), (0.14, -0.79), (0.24, -0.765), (0.29, -0.72), (0.3, -0.68), (0.3, 0.68), (0.29, 0.72), (0.24, 0.765), (0.14, 0.79), (0.002, 0.8)],
                32, closed=False, cap_ends=True, loc=(0.55, 0.38, 3.45), axis="X")
    obj("tr_conservator", "painted_grey", bm)
    for x in (-0.13, 1.23):
        ring("tr_cons_band", (0.55 + x - 0.55 + 0.0, 0.38, 3.45), 0.3, 0.31, 0.04, "painted_grey", "X", 32)
    for x in (0.05, 1.05):
        box("tr_cons_leg", (x, 0.38, 3.0), (0.08, 0.3, 0.6), "painted_dark", 0.004)
    tube("tr_buchholz_pipe", fillet([(0.2, 0.38, 3.15), (0.2, 0.38, 2.95), (0.2, 0.2, 2.75)], 0.08), 0.04, "painted_grey", 12)
    box("tr_buchholz", (0.2, 0.33, 2.98), (0.14, 0.14, 0.12), "painted_dark", 0.008)
    cyl("tr_oil_gauge", (1.31, 0.38, 3.45), 0.12, 0.04, "painted_dark", "X", 24, bevel=0.004)
    cyl("tr_oil_face", (1.333, 0.38, 3.45), 0.1, 0.004, "board_white", "X", 24)
    box("tr_oil_needle", (1.336, 0.38, 3.48), (0.002, 0.008, 0.07), "painted_red", 0.0, rot=(30, 0, 0))
    tube("tr_breather_pipe", fillet([(1.2, 0.6, 3.4), (1.6, 0.6, 3.4), (1.6, 0.6, 2.2)], 0.08), 0.02, "painted_grey", 8)
    cyl("tr_breather", (1.6, 0.6, 2.05), 0.07, 0.25, "glass_lens", "Z", 16)
    for z in (1.92, 2.18):
        cyl("tr_breather_cap", (1.6, 0.6, z), 0.075, 0.03, "copper", "Z", 16)
    # LV cable box (-X) with cables into the floor; tap changer (+X) with warning plate; ladder
    box("tr_cablebox", (-1.68, 0, 1.6), (0.36, 1.0, 1.0), "painted_grey", 0.01, segs=1, recess=(("-x", 0.05, -0.006),))
    bolts("tr_cablebox_bolts", [(-1.865, y, z) for y in (-0.44, 0.0, 0.44) for z in (1.15, 2.05)], "steel", 0.014, 0.01, "X")
    bm = bmesh.new()
    for i, y in enumerate((-0.33, -0.11, 0.11, 0.33)):
        add_cyl(bm, (-1.68, y, 1.07), 0.06, 0.06, "Z", 8)
        add_tube(bm, fillet([(-1.68, y, 1.05), (-1.68, y, 0.35), (-1.85, y, 0.1), (-1.85, y, -0.1)], 0.15), 0.045, 10)
    obj("tr_lv_cables", "cable_black", bm)
    box("tr_tapchanger", (1.68, 0.0, 1.4), (0.36, 0.8, 1.2), "painted_grey", 0.01, segs=1, recess=(("x", 0.05, -0.006),))
    box("tr_tc_handle", (1.875, 0.3, 1.4), (0.02, 0.025, 0.15), "painted_dark", 0.006)
    fr = ((1.876, 0, 1.55), (0, -1, 0), (0, 0, 1), (1, 0, 0))
    prism("tr_warn_plate", [(-0.25, -0.17), (0.25, -0.17), (0.25, 0.17), (-0.25, 0.17)], fr, 0.0, 0.004, "hazard")
    h3 = math.sqrt(3)
    prism("tr_warn_tri", [(-0.07, 0.0), (0.07, 0.0), (0.0, 0.07 * h3)], ((1.876, 0, 1.6), (0, -1, 0), (0, 0, 1), (1, 0, 0)), 0.004, 0.006, "painted_dark")
    text_obj("tr_warn_txt", "DANGER 132 kV", "painted_dark", (1.8805, 0.0, 1.45), 0.06, rot=(90, 0, 90))
    box("tr_rating", (-1.502, 0.35, 2.3), (0.004, 0.3, 0.2), "galvanized", 0.001)
    text_obj("tr_rating_txt", "60 MVA 132/33 kV", "painted_dark", (-1.5045, 0.35, 2.3), 0.022, rot=(90, 0, -90))
    for x in (-1.55, 1.55):
        box("tr_earth_strap", (x, -0.66, 0.15), (0.04, 0.006, 0.3), "copper", 0.001)
    bm = bmesh.new()
    for s in (-1, 1):
        add_box(bm, (1.96, s * 0.2, 1.4), (0.04, 0.02, 2.6))
    for i in range(9):
        add_cyl(bm, (1.96, 0, 0.35 + i * 0.28), 0.012, 0.4, "Y", 8)
    obj("tr_ladder", "galvanized", bm)
    return finish("transformer_unit", off, note="origin bottom centre; bushings along X at Y -0.3; LV cable box -X, tap changer +X")


def w_switchgear(off):
    # 4 m MV switchgear lineup: 5 panels x 0.8, 1.2 deep, 2.3 high; origin bottom centre; front -Y. Status screen 'screen' on panel 3.
    F = -0.6
    leds = {"led_green": bmesh.new(), "led_red": bmesh.new(), "led_amber": bmesh.new()}
    disp, mim, dark = bmesh.new(), bmesh.new(), bmesh.new()
    for i in range(5):
        xc = -1.6 + 0.8 * i
        box("sg_body", (xc, 0, 1.15), (0.796, 1.2, 2.3), "painted_grey", 0.004, segs=1)
        box("sg_plinth", (xc, 0, 0.05), (0.78, 1.15, 0.1), "painted_dark", 0.003)
        box("sg_vent", (xc, 0.2, 2.33), (0.78, 0.6, 0.06), "painted_grey", 0.004)
        box("sg_lv_door", (xc, F - 0.006, 1.925), (0.76, 0.012, 0.53), "painted_grey", 0.003, recess=(("-y", 0.025, -0.002),))
        box("sg_cb_door", (xc, F - 0.006, 1.075), (0.76, 0.012, 0.63), "painted_grey", 0.003, recess=(("-y", 0.025, -0.002),))
        box("sg_cable_door", (xc, F - 0.006, 0.4), (0.76, 0.012, 0.58), "painted_grey", 0.003)
        for z, h in ((1.925, 0.4), (1.075, 0.5), (0.4, 0.45)):
            box("sg_handle", (xc + 0.31, F - 0.022, z), (0.025, 0.02, 0.12), "painted_dark", 0.006, segs=2)
        # LV compartment: protection relay with display, LEDs, selector switches, nameplate
        add_box(dark, (xc - 0.12, F - 0.016, 1.98), (0.24, 0.02, 0.28))
        add_box(disp, (xc - 0.12, F - 0.0265, 2.03), (0.14, 0.002, 0.08))
        for k, m in enumerate(("led_green", "led_red" if i == 3 else "led_green", "led_amber" if i in (1, 3) else "led_green")):
            add_cyl(leds[m], (xc - 0.2 + k * 0.04, F - 0.027, 1.92), 0.007, 0.004, "Y", 10)
        for k in range(2):
            add_cyl(dark, (xc + 0.12 + k * 0.1, F - 0.02, 1.98), 0.02, 0.02, "Y", 14)
        box("sg_nameplate", (xc, F - 0.0135, 2.15), (0.2, 0.003, 0.05), "board_white", 0.0)
        text_obj("sg_name_txt", "F0%d" % (i + 1), "painted_dark", (xc, F - 0.0155, 2.15), 0.035)
        # Mimic strip: bus across all panels, drop to breaker symbol + status LED
        add_box(mim, (xc, F - 0.0015, 1.6), (0.8, 0.003, 0.014))
        add_box(mim, (xc, F - 0.0015, 1.53), (0.01, 0.003, 0.14))
        add_box(mim, (xc, F - 0.003, 1.45), (0.04, 0.006, 0.04))
        add_cyl(leds["led_red" if i == 3 else "led_green"], (xc, F - 0.007, 1.45), 0.008, 0.004, "Y", 10)
        # Breaker compartment: viewing window, ON/OFF buttons, spring indicator, racking socket
        box("sg_window_frame", (xc - 0.1, F - 0.015, 1.18), (0.29, 0.008, 0.19), "painted_dark", 0.003)
        box("sg_window", (xc - 0.1, F - 0.0195, 1.18), (0.25, 0.002, 0.15), "glass_lens", 0.0)
        box("sg_breaker_inside", (xc - 0.1, F + 0.05, 1.18), (0.25, 0.08, 0.15), "painted_dark", 0.0)
        cyl("sg_btn_on", (xc + 0.15, F - 0.018, 1.2), 0.018, 0.012, "painted_red", "Y", 14, bevel=0.002)
        cyl("sg_btn_off", (xc + 0.15, F - 0.018, 1.13), 0.018, 0.012, "painted_dark", "Y", 14, bevel=0.002)
        box("sg_spring_ind", (xc + 0.24, F - 0.014, 1.2), (0.03, 0.004, 0.02), "hazard", 0.0)
        cyl("sg_racking", (xc, F - 0.016, 0.88), 0.022, 0.01, "painted_dark", "Y", 14)
        bm = bmesh.new()
        for k in range(7):
            add_box(bm, (xc, F - 0.0125, 0.22 + k * 0.035), (0.5, 0.003, 0.012))
        obj("sg_louvres", "painted_dark", bm)
    obj("sg_relays", "painted_dark", dark)
    obj("sg_relay_displays", "screen", disp)
    obj("sg_mimic", "painted_dark", mim)
    for m, bm in leds.items():
        obj("sg_leds_" + m, m, bm)
    box("sg_screen_bezel", (0.0, F - 0.014, 1.74), (0.3, 0.006, 0.17), "painted_dark", 0.003)
    scr = box("screen", (0.0, F - 0.0175, 1.74), (0.26, 0.002, 0.13), "screen", 0.0)
    return finish("switchgear_lineup_4", off, keep=(scr.name,), note="origin bottom centre; front -Y; X +-2.0, Y +-0.6, Z 0..2.36")


def w_main_breaker(off):
    # Large wall breaker; back-face origin (wall plane Y=0, Z=0 at housing centre). Lever object 'lever' pivots at (0.39,-0.33,0).
    box("mb_housing", (0, -0.175, 0), (0.6, 0.35, 0.9), "painted_grey", 0.01, segs=2)
    box("mb_door", (0, -0.355, 0), (0.56, 0.012, 0.86), "painted_grey", 0.004, recess=(("-y", 0.04, -0.003),))
    for z in (-0.3, 0.3):
        cyl("mb_hinge", (-0.292, -0.358, z), 0.008, 0.07, "steel", "Z", 12)
    h3 = math.sqrt(3)
    fr = ((0, -0.3615, 0.26), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    prism("mb_warn_border", [(-0.075, -0.075 * h3 / 3), (0.075, -0.075 * h3 / 3), (0, 0.15 * h3 / 3)], fr, 0.0, 0.001, "painted_dark")
    prism("mb_warn", [(-0.06, -0.06 * h3 / 3), (0.06, -0.06 * h3 / 3), (0, 0.12 * h3 / 3)], fr, 0.001, 0.002, "hazard")
    box("mb_plate", (0, -0.3625, 0.1), (0.36, 0.003, 0.06), "board_white", 0.0)
    text_obj("mb_plate_txt", "MAIN BREAKER", "painted_dark", (0, -0.3645, 0.1), 0.032)
    face, ticks, needle, bez = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    gauge(face, ticks, needle, bez, Matrix.Translation((0, -0.361, 0)), 0.0, -0.08, 0.06, 0.4)
    obj("mb_g_bez", "painted_dark", bez)
    obj("mb_g_face", "board_white", face)
    obj("mb_g_ticks", "painted_dark", ticks)
    obj("mb_g_needle", "painted_red", needle)
    for x, nm, m in ((-0.12, "lamp_on", "led_green"), (0.12, "lamp_off", "led_red")):
        cyl("mb_lamp_collar_" + nm, (x, -0.364, -0.26), 0.022, 0.01, "steel", "Y", 16)
        cyl(nm, (x, -0.371, -0.26), 0.016, 0.012, m, "Y", 16, bevel=0.003)
        box("mb_lamp_tag_" + nm, (x, -0.3625, -0.32), (0.09, 0.003, 0.025), "galvanized", 0.0)
    text_obj("mb_tag_on", "ON", "painted_dark", (-0.12, -0.3645, -0.32), 0.016)
    text_obj("mb_tag_off", "OFF", "painted_dark", (0.12, -0.3645, -0.32), 0.016)
    # Lever bracket and quadrant (fixed)
    P = Vector((0.39, -0.33, 0.0))
    box("mb_boss", (0.33, P.y, P.z), (0.06, 0.12, 0.14), "painted_dark", 0.006)
    q = [(0.0, 0.0)] + [(0.2 * math.sin(math.radians(a)), 0.2 * math.cos(math.radians(a))) for a in range(-50, 51, 10)]
    prism("mb_quadrant", [(-u, v) for u, v in q], ((0.355, P.y, P.z), (0, 1, 0), (0, 0, 1), (1, 0, 0)), 0.0, 0.005, "hazard")
    text_obj("mb_q_on", "I", "painted_dark", (0.3605, P.y - 0.13, P.z + 0.15), 0.04, rot=(90, 0, 90))
    text_obj("mb_q_off", "O", "painted_dark", (0.3605, P.y + 0.13, P.z + 0.15), 0.04, rot=(90, 0, 90))
    # Lever (separate object, neutral pose pointing up; +45 deg about X leans toward the viewer = ON)
    bm = bmesh.new()
    add_cyl(bm, tuple(P), 0.05, 0.06, "X", 20)
    add_box(bm, tuple(P + Vector((0, 0, 0.2))), (0.035, 0.05, 0.36))
    obj("lever", "painted_red", bm, 0.006, 2)
    cyl("mb_grip_tmp", tuple(P + Vector((0, 0, 0.385))), 0.028, 0.16, "rubber", "X", 16, bevel=0.006)
    for c in ("top", "bottom"):
        z = 0.48 if c == "top" else -0.48
        cyl("mb_conduit_" + c, (0.15, -0.17, z + (0.06 if z > 0 else -0.06)), 0.03, 0.12, "galvanized", "Z", 12)
    root = finish("main_breaker_lever", off, keep=("lever", "mb_grip_tmp", "lamp_on", "lamp_off"), note="back-face origin; lever pivot (0.39,-0.33,0), axis X")
    # Merge the grip into the lever object, then move the lever origin to the pivot.
    vl = bpy.context.view_layer
    bpy.ops.object.select_all(action="DESELECT")
    lv, gp = bpy.data.objects["lever"], bpy.data.objects["mb_grip_tmp"]
    gp.select_set(True)
    lv.select_set(True)
    vl.objects.active = lv
    bpy.ops.object.join()
    K.STATS["main_breaker_lever"]["meshes"] = {o.name: K.tris(o) for o in root.children}
    set_pivot("lever", tuple(P))
    PIVOTS["lever"] = tuple(round(c, 4) for c in P)
    return root


def w_hv_cage(off):
    # 4 m mesh HV safety cage panel with a 0.97 m gate (hinged at X 0.03) and HIGH VOLTAGE signs; origin bottom centre; front -Y.
    for x in (-1.97, 0.0, 1.03, 1.97):
        box("hv_post", (x, 0, 1.1), (0.06, 0.06, 2.2), "painted_grey", 0.003, segs=1)
        box("hv_foot", (x, 0, 0.005), (0.16, 0.12, 0.01), "galvanized", 0.002)
    for x0, x1 in ((-1.94, -0.03), (1.06, 1.94)):
        for loc, size in ((((x0 + x1) / 2, 0, 2.17), (x1 - x0, 0.04, 0.04)), (((x0 + x1) / 2, 0, 0.12), (x1 - x0, 0.04, 0.04))):
            box("hv_rail", loc, size, "painted_grey", 0.002, segs=1)
        lattice("hv_mesh", "galvanized", x0, x1, 0.14, 2.15, 0.0, 0.06, 0.004)
        box("hv_kick", ((x0 + x1) / 2, -0.022, 0.07), (x1 - x0, 0.004, 0.1), "galvanized", 0.001)
    gx0, gx1 = 0.06, 1.0
    for loc, size in ((((gx0 + gx1) / 2, -0.005, 2.12), (gx1 - gx0, 0.035, 0.035)), (((gx0 + gx1) / 2, -0.005, 0.12), (gx1 - gx0, 0.035, 0.035)),
                      ((gx0 + 0.0175, -0.005, 1.12), (0.035, 0.035, 2.0)), ((gx1 - 0.0175, -0.005, 1.12), (0.035, 0.035, 2.0))):
        box("hv_gate_frame", loc, size, "painted_grey", 0.002, segs=1)
    lattice("hv_gate_mesh", "galvanized", gx0 + 0.035, gx1 - 0.035, 0.14, 2.1, -0.005, 0.06, 0.004)
    for z in (0.4, 1.8):
        cyl("hv_hinge", (0.03, -0.005, z), 0.014, 0.1, "steel", "Z", 12)
    box("hv_lock_box", (0.97, -0.04, 1.1), (0.06, 0.05, 0.14), "painted_dark", 0.006)
    torus("hv_padlock_shackle", (0.97, -0.07, 1.02), 0.02, 0.004, "steel", "Y", 12, 5, arc=math.pi)
    box("hv_padlock", (0.97, -0.07, 0.995), (0.05, 0.02, 0.045), "painted_red", 0.006)
    h3 = math.sqrt(3)
    for x in (-1.0, 1.5):
        box("hv_sign", (x, -0.028, 1.55), (0.42, 0.004, 0.36), "board_white", 0.002)
        fr = ((x, -0.0305, 1.62), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        prism("hv_sign_tri_k", [(-0.09, -0.09 * h3 / 3), (0.09, -0.09 * h3 / 3), (0, 0.18 * h3 / 3)], fr, 0.0, 0.001, "painted_dark")
        prism("hv_sign_tri_y", [(-0.075, -0.075 * h3 / 3), (0.075, -0.075 * h3 / 3), (0, 0.15 * h3 / 3)], fr, 0.001, 0.002, "hazard")
        bolt = [(0.006, 0.032), (-0.012, 0.0), (0.0, 0.0), (-0.008, -0.028), (0.014, 0.008), (0.002, 0.008)]
        prism("hv_sign_bolt", [(u, v - 0.004) for u, v in bolt], fr, 0.002, 0.003, "painted_dark")
        text_obj("hv_sign_txt", "HIGH VOLTAGE", "painted_red", (x, -0.0305, 1.44), 0.045)
        bolts("hv_sign_ties", [(x + sx * 0.18, -0.031, 1.55 + sz * 0.15) for sx in (-1, 1) for sz in (-1, 1)], "steel", 0.005, 0.003, "Y", dome=True)
    return finish("hv_cage_4", off, note="origin bottom centre; panel plane Y=0; gate X 0.03..1.0; height 2.2")


# ================================================================= RELAY CORE
def r_core_array(off):
    # Tesla relay column ~7 m on a 6 m dais (top surface exactly Z 0.6); origin dais floor centre.
    cyl("ra_dais", (0, 0, 0.295), 3.0, 0.59, "painted_dark", "Z", 72, bevel=0.01, segs=1)
    cyl("ra_deck", (0, 0, 0.595), 2.85, 0.01, "diamond_plate", "Z", 72)
    bmy, bmk = bmesh.new(), bmesh.new()
    n = 72
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        poly = [(2.85 * math.cos(a0), 2.85 * math.sin(a0)), (3.0 * math.cos(a0), 3.0 * math.sin(a0)), (3.0 * math.cos(a1), 3.0 * math.sin(a1)), (2.85 * math.cos(a1), 2.85 * math.sin(a1))]
        add_prism(bmy if k % 2 == 0 else bmk, poly, ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 0.59, 0.6)
    obj("ra_rim_y", "hazard", bmy)
    obj("ra_rim_k", "painted_dark", bmk)
    glow = bmesh.new()
    for k in range(24):
        a = 2 * math.pi * (k + 0.5) / 24
        add_box(glow, (3.001 * math.cos(a), 3.001 * math.sin(a), 0.3), (0.012, 0.06, 0.38), rot=(0, 0, math.degrees(a)))
    # Base plinth (octagon) with glow slits, primary coil on ceramic posts
    cyl("ra_plinth", (0, 0, 0.8), 0.95, 0.4, "painted_dark", "Z", 8, bevel=0.01, segs=1, rot=(0, 0, 22.5))
    for k in range(8):
        a = 2 * math.pi * k / 8
        add_box(glow, (0.878 * math.cos(a), 0.878 * math.sin(a), 0.8), (0.006, 0.05, 0.26), rot=(0, 0, math.degrees(a)))
    ins = bmesh.new()
    for k in range(6):
        a = 2 * math.pi * k / 6
        insulator(ins, (1.15 * math.cos(a), 1.15 * math.sin(a), 0), 0.6, 0.78, 0.03, 0.06, 0.05, 0.05, 10)
    pts = [(1.15 * math.cos(2 * math.pi * t / 24), 1.15 * math.sin(2 * math.pi * t / 24), 0.8 + 0.22 * t / 72) for t in range(73)]
    tube("ra_primary", pts, 0.035, "copper", 8)
    for a in (0.0, math.pi):
        box("ra_primary_lead", (1.35 * math.cos(a), 1.35 * math.sin(a), 0.7), (0.4, 0.06, 0.012), "copper", 0.002, rot=(0, 0, math.degrees(a)))
    # Secondary: former, copper body, helical winding, end rings
    cyl("ra_former", (0, 0, 2.75), 0.42, 3.5, "painted_dark", "Z", 32)
    cyl("ra_secondary", (0, 0, 2.75), 0.445, 3.3, "copper", "Z", 40)
    per = 12
    pts = [(0.457 * math.cos(2 * math.pi * t / per), 0.457 * math.sin(2 * math.pi * t / per), 1.1 + 3.3 * t / (28 * per)) for t in range(28 * per + 1)]
    tube("ra_winding", pts, 0.012, "copper", 4)
    for z in (1.08, 4.42):
        torus("ra_winding_ring", (0, 0, z), 0.47, 0.03, "copper", "Z", 32, 6)
    # Insulator stacks + maintenance ring with railing + ladder
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        x, y = 1.6 * math.cos(a), 1.6 * math.sin(a)
        box("ra_stack_base", (x, y, 0.675), (0.26, 0.26, 0.15), "painted_dark", 0.006)
        insulator(ins, (x, y, 0), 0.75, 3.33, 0.065, 0.17, 0.13, 0.24, 10)
        cyl("ra_stack_cap", (x, y, 3.36), 0.11, 0.06, "steel", "Z", 12, bevel=0.006)
    obj("ra_insulators", "ceramic", ins)
    bm = bmesh.new()
    for k in range(64):
        a = 2 * math.pi * k / 64
        add_box(bm, (1.25 * math.cos(a), 1.25 * math.sin(a), 3.385), (1.0, 0.005, 0.03), rot=(0, 0, math.degrees(a)))
    obj("ra_ring_grating", "galvanized", bm)
    ring("ra_ring_inner", (0, 0, 3.38), 0.74, 0.76, 0.04, "galvanized", "Z", 48)
    ring("ra_ring_toe", (0, 0, 3.44), 1.74, 1.76, 0.16, "hazard", "Z", 48)
    bm = bmesh.new()
    for k in range(12):
        a = 2 * math.pi * k / 12
        add_cyl(bm, (1.72 * math.cos(a), 1.72 * math.sin(a), 3.92), 0.02, 1.06, "Z", 8)
    obj("ra_ring_posts", "hazard", bm)
    for z in (4.45, 3.92):
        torus("ra_ring_rail", (0, 0, z), 1.72, 0.021, "hazard", "Z", 48, 6)
    bm = bmesh.new()
    for s in (-1, 1):
        add_box(bm, (1.9, s * 0.2, 2.0), (0.04, 0.02, 2.8))
    for i in range(9):
        add_cyl(bm, (1.9, 0, 0.9 + i * 0.3), 0.012, 0.4, "Y", 8)
    obj("ra_ladder", "galvanized", bm)
    # Relay head: glowing core inside ceramic rod cage
    for z in (4.53, 5.57):
        cyl("ra_head_plate", (0, 0, z), 0.56, 0.06, "painted_dark", "Z", 32, bevel=0.008)
    add_cyl(glow, (0, 0, 5.05), 0.22, 0.98, "Z", 20)
    bm = bmesh.new()
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        add_cyl(bm, (0.45 * math.cos(a), 0.45 * math.sin(a), 5.05), 0.035, 0.98, "Z", 8)
    obj("ra_head_rods", "ceramic", bm)
    for k in range(6):
        a = 2 * math.pi * k / 6
        add_box(glow, (0.3 * math.cos(a), 0.3 * math.sin(a), 5.05), (0.02, 0.02, 0.9), rot=(0, 0, math.degrees(a)))
    obj("ra_core_glow", "core_glow", glow)
    # Toroidal top load
    cyl("ra_neck", (0, 0, 5.75), 0.25, 0.3, "galvanized", "Z", 24, bevel=0.01)
    torus("ra_toroid_big", (0, 0, 6.15), 0.85, 0.28, "steel", "Z", 40, 12)
    torus("ra_toroid_small", (0, 0, 6.62), 0.55, 0.2, "steel", "Z", 32, 10)
    bm = bmesh.new()
    add_revolve(bm, [(0.6, 6.15), (0.58, 6.5)] + [(max(0.002, 0.36 * math.cos(math.pi / 2 * k / 6)), 6.75 + 0.25 * math.sin(math.pi / 2 * k / 6)) for k in range(7)], 32, closed=False, cap_ends=True)
    obj("ra_topload_core", "steel", bm)
    # Cable trunks: drop from the plinth into the deck, run under it, and leave through the dais wall into the floor
    # (the walkable deck between r 1.0 and 2.85 stays clear apart from the stack bases and the ladder).
    bm = bmesh.new()
    clamps = bmesh.new()
    for k in range(6):
        a = 2 * math.pi * (k + 0.25) / 6
        ca, sa = math.cos(a), math.sin(a)
        add_tube(bm, fillet([(0.9 * ca, 0.9 * sa, 0.86), (1.0 * ca, 1.0 * sa, 0.8), (1.06 * ca, 1.06 * sa, 0.45)], 0.08, 3), 0.09, 10)
        add_tube(bm, fillet([(r_ * ca, r_ * sa, z) for r_, z in ((2.9, 0.32), (3.2, 0.32), (3.4, 0.1), (3.42, -0.1))], 0.18, 4), 0.09, 10)
        add_ring(clamps, (3.04 * ca, 3.04 * sa, 0.32), 0.09, 0.105, 0.06, "X", 12, rot=(0, 0, math.degrees(a)))
        add_box(clamps, (3.005 * ca, 3.005 * sa, 0.32), (0.012, 0.26, 0.26), rot=(0, 0, math.degrees(a)))
    obj("ra_trunks", "cable_black", bm)
    obj("ra_trunk_glands", "galvanized", clamps)
    return finish("relay_core_array", off, note="origin dais floor centre; dais top Z 0.6 (radius 3.0); column top ~Z 7.0")


def capacitor_common(prefix, destroyed):
    box(prefix + "_base", (0, 0, 0.075), (1.2, 1.2, 0.15), "painted_dark", 0.008, segs=1)
    bolts(prefix + "_anchors", [(sx * 0.52, sy * 0.52, 0.16) for sx in (-1, 1) for sy in (-1, 1)], "steel", 0.016, 0.02, "Z")
    for sx in (-1, 1):
        for sy in (-1, 1):
            rot = (8, -5, 0) if (destroyed and sx > 0 and sy < 0) else (0, 0, 0)
            box(prefix + "_post", (sx * 0.56, sy * 0.56, 1.325), (0.06, 0.06, 2.35), "painted_dark", 0.003, segs=1, rot=rot)


def r_capacitor(off):
    # Destructible capacitor tower 1.2 x 1.2 x 2.6 (+ top bushing); origin bottom centre. Glowing cells mesh named 'cells'.
    capacitor_common("cs", False)
    for loc, size in (((0, 0, 2.525), (1.2, 1.2, 0.05)), ((0, 0, 2.575), (1.1, 1.1, 0.05))):
        box("cs_top", loc, size, "painted_dark", 0.006, segs=1)
    cells, cans, links = bmesh.new(), bmesh.new(), bmesh.new()
    for k in range(5):
        z = 0.2 + k * 0.45
        box("cs_deck", (0, 0, z), (0.92, 0.92, 0.03), "painted_grey", 0.003)
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * 0.22, sy * 0.22
                add_cyl(cans, (x, y, z + 0.195), 0.16, 0.36, "Z", 16)
                add_ring(cells, (x, y, z + 0.2), 0.16, 0.166, 0.045, "Z", 16)
                add_cyl(links, (x + sx * 0.05, y, z + 0.4), 0.018, 0.03, "Z", 8)
        add_cyl(cells, (0, 0, z + 0.2), 0.07, 0.34, "Z", 12)
        add_box(links, (0, 0.22, z + 0.42), (0.5, 0.04, 0.008))
        add_box(links, (0, -0.22, z + 0.42), (0.5, 0.04, 0.008))
    obj("cs_cans", "painted_grey", cans)
    obj("cs_links", "copper", links)
    obj("cells", "core_glow", cells)
    for sx in (-1, 1):
        lattice("cs_cage_x", "galvanized", -0.53, 0.53, 0.18, 2.48, sx * 0.585, 0.1, 0.004, axis="Y")
    for sy in (-1, 1):
        lattice("cs_cage_y", "galvanized", -0.53, 0.53, 0.18, 2.48, sy * 0.585, 0.1, 0.004, axis="X")
    ins = bmesh.new()
    insulator(ins, (0, 0, 0), 2.6, 2.86, 0.05, 0.11, 0.085, 0.07, 14)
    obj("cs_bushing", "ceramic", ins)
    cyl("cs_terminal", (0, 0, 2.89), 0.04, 0.06, "copper", "Z", 12)
    h3 = math.sqrt(3)
    fr = ((0, -0.592, 1.9), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    prism("cs_warn_k", [(-0.1, -0.1 * h3 / 3), (0.1, -0.1 * h3 / 3), (0, 0.2 * h3 / 3)], fr, 0.0, 0.002, "painted_dark")
    prism("cs_warn_y", [(-0.083, -0.083 * h3 / 3), (0.083, -0.083 * h3 / 3), (0, 0.166 * h3 / 3)], fr, 0.002, 0.004, "hazard")
    return finish("capacitor_stack", off, keep=("cells",), note="origin bottom centre; body Z 0..2.6, bushing to 2.92")


def r_capacitor_destroyed(off):
    # Destroyed variant: split cans, collapsed upper tiers, burnt, torn cage, debris; no glow. Origin bottom centre.
    capacitor_common("cd", True)
    burnt, cans, debris = bmesh.new(), bmesh.new(), bmesh.new()
    seed = [7]

    def rnd():
        seed[0] = (seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return seed[0] / 0x7FFFFFFF

    def split_can(bm, loc, rot, h=0.36):
        vs = bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=False, segments=16, radius1=0.16, radius2=0.16, depth=h)["verts"]
        for v in vs:
            if v.co.z > 0:
                v.co.z -= rnd() * 0.12
                v.co.x *= 1.0 + rnd() * 0.25
                v.co.y *= 1.0 + rnd() * 0.25
        bot = [v for v in vs if v.co.z < 0]
        bot.sort(key=lambda v: math.atan2(v.co.y, v.co.x))
        bm.faces.new(bot)
        bmesh.ops.transform(bm, matrix=M(loc, rot), verts=vs)
    for k in range(5):
        z = 0.2 + k * 0.45
        tilt = (0, 0, 0) if k < 3 else ((14, -9, 12) if k == 3 else (28, 15, -20))
        dx = 0 if k < 3 else (0.05 if k == 3 else 0.16)
        zz = z if k < 4 else z - 0.12
        box("cd_deck", (dx, 0, zz), (0.92, 0.92, 0.03), "robot_dark", 0.003, rot=tilt)
        for sx in (-1, 1):
            for sy in (-1, 1):
                if k == 4 and sx > 0:
                    continue
                p = M((dx, 0, zz), tilt) @ Vector((sx * 0.22, sy * 0.22, 0.195))
                if (k + sx + sy) % 3 == 0:
                    split_can(burnt, tuple(p), tilt)
                else:
                    add_cyl(cans, tuple(p), 0.16, 0.36, "Z", 16, rot=tilt)
                add_cyl(burnt, tuple(M((dx, 0, zz), tilt) @ Vector((sx * 0.22, sy * 0.22, 0.2))), 0.162, 0.045, "Z", 16, rot=tilt)
        add_cyl(burnt, tuple(M((dx, 0, zz), tilt) @ Vector((0, 0, 0.2))), 0.07, 0.34, "Z", 12, rot=tilt)
    for p, r_ in (((0.75, -0.5, 0.16), (90, 0, 30)), ((-0.8, 0.6, 0.16), (90, 0, -60))):
        split_can(burnt, p, r_)
    for i in range(14):
        a = rnd() * 2 * math.pi
        rr = 0.7 + rnd() * 0.5
        add_box(debris, (rr * math.cos(a), rr * math.sin(a), 0.015), (0.05 + rnd() * 0.12, 0.03 + rnd() * 0.08, 0.02 + rnd() * 0.02), rot=(rnd() * 30, rnd() * 30, rnd() * 180))
    obj("cd_cans_burnt", "robot_dark", burnt)
    obj("cd_cans", "painted_dark", cans)
    obj("cd_debris", "robot_dark", debris)
    lattice("cd_cage_back", "galvanized", -0.53, 0.53, 0.18, 2.48, 0.585, 0.08, 0.004, axis="X")
    lattice("cd_cage_left", "galvanized", -0.53, 0.53, 0.18, 2.48, -0.585, 0.08, 0.004, axis="Y")
    bm = bmesh.new()
    for i in range(14):
        x = -0.52 + i * 0.08
        ln = 0.6 + 0.9 * ((i * 37) % 11) / 11
        add_box(bm, (x, -0.6 - 0.12 * ln / 1.5, 0.18 + ln / 2), (0.004, 0.004, ln), rot=(-14, 0, 0))
    for j in range(6):
        add_box(bm, (0, -0.62 - 0.02 * j, 0.22 + j * 0.16), (1.06 - j * 0.12, 0.004, 0.004))
    obj("cd_cage_torn", "galvanized", bm)
    box("cd_top_plate", (0.35, 0.95, 0.04), (1.1, 1.1, 0.05), "robot_dark", 0.006, rot=(8, -6, 25))
    return finish("capacitor_stack_destroyed", off, note="origin bottom centre; debris to ~1.5 m radius; no emissive cells")


def r_bus_bar(off):
    # Overhead copper bus (3 bars, 4 m along X) on suspension insulators; origin at the centre bar centroid.
    bm = bmesh.new()
    for y in (-0.3, 0.0, 0.3):
        add_box(bm, (0, y, 0), (4.0, 0.012, 0.12))
        for s in (-1, 1):
            add_box(bm, (s * 1.96, y + 0.012, 0), (0.08, 0.012, 0.12))
    obj("bb_bars", "copper", bm, 0.0015, 1)
    bolts("bb_splice_bolts", [(s * 1.96 + dx, y + 0.02, dz) for s in (-1, 1) for y in (-0.3, 0.0, 0.3) for dx in (-0.02, 0.02) for dz in (-0.03, 0.03)], "steel", 0.008, 0.008, "Y")
    ins = bmesh.new()
    for x in (-1.0, 1.0):
        box("bb_strut", (x, 0, 0.92), (0.042, 0.9, 0.042), "galvanized", 0.0015, recess=(("-z", 0.008, 0.03),))
        for s in (-1, 1):
            cyl("bb_rod", (x, s * 0.42, 1.2), 0.008, 0.6, "steel", "Z", 8)
        for y in (-0.3, 0.0, 0.3):
            insulator(ins, (x, y, 0), 0.16, 0.86, 0.035, 0.09, 0.07, 0.11, 12)
            box("bb_clamp", (x, y, 0.1), (0.07, 0.05, 0.11), "galvanized", 0.004)
            cyl("bb_cap", (x, y, 0.88), 0.045, 0.04, "galvanized", "Z", 12)
    obj("bb_insulators", "ceramic", ins)
    return finish("core_bus_bar_4", off, note="origin centre bar centroid; bars X +-2.0 at Y -0.3/0/0.3; hangers to Z +1.5")


# ================================================================= build / previews
LAYOUT = [
    (s_catwalk, (0, 0, 0)), (s_catwalk_rail, (5, 0, 0)), (s_stair, (9, 0, 0)), (s_blast_door, (12.5, 0, 0)),
    (s_blast_door_frame, (16.5, 0, 0)), (s_crawl_duct, (23, 0, 0)), (s_grate_floor, (26, 0, 0)),
    (p_cooling_pump, (31, 0, 0)), (p_manifold, (39, 0, 0)), (p_valve_station, (45, 0, 0)), (p_water_channel, (49, 0, 0)),
    (p_control_panel, (52.5, 0, 0)), (w_transformer, (57, 0, 0)), (w_switchgear, (62, 0, 0)), (w_main_breaker, (65.5, 0, 0)),
    (w_hv_cage, (69, 0, 0)), (r_core_array, (76, 0, 0)), (r_capacitor, (81, 0, 0)), (r_capacitor_destroyed, (83.5, 0, 0)),
    (r_bus_bar, (87.5, 0, 0)),
]


def write_sources(out_dir):
    font = M3.FONT_INFO.get("font", ("Bfont Regular", "<builtin>"))
    L = ["# M4 sources", "",
         "All of `staging/env_m4/` is first-party and project-owned, generated by `tools/m2/env_kit_m4.py` (which reuses",
         "`tools/m2/env_kit.py` and `tools/m2/env_kit_m3.py` read-only). No files were downloaded for M4.", "",
         "- Geometry: procedural modelling in Blender 5.3 (bmesh, booleans, bevel + weighted normals, Smart UV Project).",
         "- Lettering: flat text meshes from Blender's built-in text font `%s` (`%s`), distributed with Blender under a permissive font licence." % font,
         "- Materials referenced by name only (the game remaps them). New name in M4: `ceramic` (glazed porcelain insulators).",
         "  `core_glow` is the existing game material from the M1 Teslabot.", ""]
    with open(os.path.join(out_dir, "SOURCES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    K.reset()
    for fn, off in LAYOUT:
        fn(off)
    path = os.path.join(out_dir, "m4_kit.glb")
    K.export(path)
    rename_glb_nodes(path, ["screen", "globe", "lever", "lamp_on", "lamp_off", "cells"])
    K.STATS["_pivots"] = PIVOTS
    with open(os.path.join(out_dir, "kit_stats_m4.json"), "w", encoding="utf-8") as f:
        json.dump(K.STATS, f, indent=1)
    write_sources(out_dir)


def sheet_subset(glb, out, cols, names, tile_res=(640, 560)):
    K.reset()
    bpy.ops.import_scene.gltf(filepath=glb)
    roots = {o.name: o for o in bpy.context.scene.objects if o.parent is None}
    cam, planes, txt = K.studio(tile_res)
    tmp = tempfile.mkdtemp(prefix="m4sheet_")
    tiles = []
    for i, nm in enumerate(names):
        r = roots[nm]
        for o in roots.values():
            for x in [o] + list(o.children_recursive):
                x.hide_render = o is not r
        group = [r] + list(r.children_recursive)
        lo, hi = K.bounds(group)
        sz = hi - lo
        K.frame(cam, planes, txt, group, "%s  %.2f x %.2f x %.2f m" % (nm, sz.x, sz.y, sz.z), K.kind_of(nm), tile_res)
        p = os.path.join(tmp, "t%02d.png" % i)
        K.render_to(p)
        tiles.append(p)
    K.compose(tiles, cols, tile_res, out)
    shutil.rmtree(tmp, ignore_errors=True)


def previews(out_dir):
    glb = os.path.join(out_dir, "m4_kit.glb")
    pdir = os.path.join(out_dir, "previews")
    os.makedirs(pdir, exist_ok=True)
    for area, names in AREAS.items():
        sheet_subset(glb, os.path.join(pdir, "%s_sheet.png" % area), 4, names)
    K.detail_glb(glb, os.path.join(pdir, "closeups_hero.png"), 4, [
        "transformer_unit@-0.8,-1,0.55@0.75", "transformer_unit@0.6,-0.4,0.8@0.45@0.85",
        "relay_core_array@-0.6,-1,0.35@0.8", "relay_core_array@-0.4,-1,0.15@0.45@0.4",
        "cooling_pump@-0.8,-1,0.5@0.75", "cooling_pump@0.7,-0.9,0.5@0.45@0.4",
        "stair_flight@-1,-0.35,0.25@0.8", "stair_flight@-1,0.1,0.15@0.35@0.25"])


def verify(out_dir):
    """Numerically check the walking surfaces in the exported GLB (root-local coordinates)."""
    K.reset()
    bpy.ops.import_scene.gltf(filepath=os.path.join(out_dir, "m4_kit.glb"))
    roots = {o.name: o for o in bpy.context.scene.objects if o.parent is None}

    def verts(root):
        inv = root.matrix_world.inverted()
        out = []
        for o in root.children_recursive:
            if o.type == "MESH":
                mw = inv @ o.matrix_world
                out += [mw @ v.co for v in o.data.vertices]
        return out
    res = {}
    v = verts(roots["stair_flight"])
    tread = [p for p in v if abs(p.x) < 0.581 and p.z > 0.05]
    above = max(p.z - 0.6 * p.y for p in tread)
    nos = []
    for i in range(1, 21):
        y, z = 7.0 / 21 * i, 0.2 * i
        hit = [p for p in tread if abs(p.y - y) < 1e-4 and abs(p.z - z) < 1e-4]
        nos.append(len(hit) > 0)
    res["stair_flight"] = {"max_height_above_pitch_line_for_tread_geometry": round(above, 6), "nosings_on_line": sum(nos), "of": 20}
    v = verts(roots["catwalk_4"])
    deck = [p for p in v if abs(p.x) <= 2.0001 and abs(p.y) <= 1.0001]
    res["catwalk_4"] = {"max_z": round(max(p.z for p in deck), 6), "x_range": [round(min(p.x for p in deck), 4), round(max(p.x for p in deck), 4)],
                        "y_range": [round(min(p.y for p in deck), 4), round(max(p.y for p in deck), 4)]}
    v = verts(roots["crawl_duct_2"])
    fl = [p for p in v if abs(p.x) <= 0.951 and -0.001 <= p.y <= 2.001 and -0.02 < p.z < 0.05]
    ce = [p for p in v if abs(p.x) < 0.75 and p.z > 1.0 and abs(p.y - 1.0) > 0.3]
    res["crawl_duct_2"] = {"floor_max_z": round(max(p.z for p in fl), 6), "ceiling_inner_min_z": round(min(p.z for p in ce), 4)}
    v = verts(roots["grate_floor_2"])
    res["grate_floor_2"] = {"max_z": round(max(p.z for p in v), 6)}
    v = verts(roots["relay_core_array"])
    dais = [p for p in v if 2.0 < Vector((p.x, p.y)).length <= 3.0 and 0.55 < p.z < 0.9 and abs(math.atan2(p.y, p.x)) > 0.25]
    res["relay_core_array"] = {"dais_top_z_annulus_r2_to_3": round(max(p.z for p in dais), 6)}
    v = verts(roots["water_channel_4"])
    g = [p for p in v if abs(p.y) <= 0.5]
    res["water_channel_4"] = {"grating_top_z": round(max(p.z for p in g), 6)}
    print("VERIFY", json.dumps(res))
    with open(os.path.join(out_dir, "walk_surface_check.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    mode = ARGV[0] if ARGV else "build"
    if mode == "build":
        build(ARGV[1] if len(ARGV) > 1 else "staging/env_m4")
    elif mode == "previews":
        previews(ARGV[1] if len(ARGV) > 1 else "staging/env_m4")
    elif mode == "verify":
        verify(ARGV[1] if len(ARGV) > 1 else "staging/env_m4")
    elif mode == "detail":
        K.detail_glb(ARGV[1], ARGV[2], int(ARGV[3]), ARGV[4:])
    print("ALL DONE")
