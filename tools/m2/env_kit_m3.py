# BREACH M3 environment: dock + control-room kits and procedural decals (Blender 5.3, headless).
#   blender -b --factory-startup -P tools/m2/env_kit_m3.py -- build  <out_dir>     -> dock_kit.glb, control_kit.glb, kit_stats_m3.json, SOURCES.md
#   blender -b --factory-startup -P tools/m2/env_kit_m3.py -- decals <out_dir>     -> <out_dir>/decals/*.png (+ previews/decals_sheet.png)
#   blender -b --factory-startup -P tools/m2/env_kit_m3.py -- sheet|detail ...     -> same preview modes as env_kit.py
# Reuses the M2 helper library (tools/m2/env_kit.py) read-only. Axes: X right, +Y forward, Z up, metres; "front" faces -Y.
import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(os.path.abspath(sys.argv[sys.argv.index("-P") + 1]))
sys.path.insert(0, HERE)
import env_kit as K
from env_kit import (box, cyl, torus, tube, prism, ring, bolts, cut, hazard_band, obj, fillet, rounded_rect, M, R,
                     add_box, add_cyl, add_torus, add_tube, add_ring, add_revolve, add_prism)

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

# New material names introduced in M3 (preview colours double as the glTF fallback if the game has no remap yet).
K.MATS.update({
    "wood_pallet": ((0.42, 0.33, 0.22), 0.0, 0.8, None, 0),
    "cardboard": ((0.50, 0.38, 0.24), 0.0, 0.85, None, 0),
    "diamond_plate": ((0.56, 0.57, 0.58), 1.0, 0.42, None, 0),
    "board_white": ((0.85, 0.86, 0.85), 0.0, 0.3, None, 0),
    "painted_red": ((0.55, 0.06, 0.04), 0.2, 0.5, None, 0),
})
K.WALL |= {"mimic_panel", "wall_clock", "whiteboard", "fire_hose_cabinet", "wall_cable_run_4", "rollup_door"}
K.CEIL |= {"ceiling_grid_tile", "ceiling_grid_tile_light", "gantry_beam_8"}
K.TOP |= {"dock_leveler", "cable_trench_cover"}
FONT_INFO = {}


def finish(root_name, offset, keep=(), note=""):
    """As env_kit.finish, but bevels are followed by a Weighted Normal modifier (face area, keep sharp)."""
    vl = bpy.context.view_layer
    for o in K.CUR:
        if o["bev"] > 0:
            md = o.modifiers.new("bevel", "BEVEL")
            md.width = o["bev"]
            md.segments = o["segs"]
            md.limit_method = "ANGLE"
            md.angle_limit = math.radians(o["bang"])
            md.use_clamp_overlap = True
            md.miter_outer = "MITER_ARC"
            wn = o.modifiers.new("wnormal", "WEIGHTED_NORMAL")
            wn.mode = "FACE_AREA"
            wn.weight = 50
            wn.keep_sharp = True
    bpy.ops.object.select_all(action="DESELECT")
    for o in K.CUR:
        o.select_set(True)
    vl.objects.active = K.CUR[0]
    bpy.ops.object.convert(target="MESH")
    for c in K.CUTTERS:
        bpy.data.objects.remove(c, do_unlink=True)
    K.CUTTERS.clear()
    kept = [o for o in K.CUR if o.name in keep]
    missing = set(keep) - {o.name for o in kept}
    if missing:
        raise RuntimeError("named meshes missing: %s" % missing)
    rest = [o for o in K.CUR if o.name not in keep]
    finals = list(kept)
    if rest:
        bpy.ops.object.select_all(action="DESELECT")
        for o in rest:
            o.select_set(True)
        vl.objects.active = rest[0]
        bpy.ops.object.join()
        body = vl.objects.active
        body.name = body.data.name = root_name + "_body"
        finals.append(body)
    for o in finals:
        K.smart_uv(o)
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
    K.STATS[root_name] = {"tris": sum(K.tris(o) for o in finals), "meshes": {o.name: K.tris(o) for o in finals},
                          "bbox_min": [round(x, 4) for x in lo], "bbox_max": [round(x, 4) for x in hi],
                          "size": [round(h - l, 4) for l, h in zip(lo, hi)], "note": note}
    print("built %-26s tris %6d size %s" % (root_name, K.STATS[root_name]["tris"], K.STATS[root_name]["size"]))
    K.CUR.clear()
    return root


def text_obj(name, s, m, loc, size, rot=(90, 0, 0), extrude=0.0, align="CENTER", offset=0.0):
    """Flat painted lettering (filled glyph faces, Blender built-in font). Default rot faces -Y, reading along +X."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = s
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.extrude = extrude
    cu.offset = offset
    cu.resolution_u = 4
    FONT_INFO.setdefault("font", (cu.font.name if cu.font else "builtin", cu.font.filepath if cu.font else "<builtin>"))
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    vl = bpy.context.view_layer
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    vl.objects.active = o
    bpy.ops.object.convert(target="MESH")
    o = vl.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    o.data.materials.clear()
    o.data.materials.append(K.mat(m))
    for p in o.data.polygons:
        p.use_smooth = False
    o["bev"], o["segs"], o["bang"] = 0.0, 1, 30
    o.select_set(False)
    K.CUR.append(o)
    return o


def lattice(name, m, x0, x1, z0, z1, y, pitch, t=0.005, axis="X"):
    """Welded wire mesh panel in the XZ plane (axis X) or YZ plane (axis Y)."""
    bm = bmesh.new()
    nx = max(1, int(round((x1 - x0) / pitch)))
    nz = max(1, int(round((z1 - z0) / pitch)))
    for i in range(nx + 1):
        u = x0 + (x1 - x0) * i / nx
        add_box(bm, (u, y, (z0 + z1) / 2) if axis == "X" else (y, u, (z0 + z1) / 2), (t, t, z1 - z0))
    for j in range(nz + 1):
        z = z0 + (z1 - z0) * j / nz
        add_box(bm, ((x0 + x1) / 2, y + t * 0.6, z) if axis == "X" else (y + t * 0.6, (x0 + x1) / 2, z),
                (x1 - x0, t, t) if axis == "X" else (t, x1 - x0, t))
    return obj(name, m, bm)


def chain_links(bm, pts, R_=0.011, r=0.0028, pitch=0.026):
    """Alternating oval links along a polyline (for hand chains)."""
    pts = [Vector(p) for p in pts]
    seglen = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seglen)
    n = int(total / pitch)
    k = 0
    for i in range(n):
        s = i * pitch
        j, acc = 0, 0.0
        while j < len(seglen) - 1 and acc + seglen[j] < s:
            acc += seglen[j]
            j += 1
        t = (pts[j + 1] - pts[j]).normalized()
        p = pts[j] + t * (s - acc)
        a = t.cross(Vector((1, 0, 0)))
        if a.length < 1e-3:
            a = t.cross(Vector((0, 1, 0)))
        a.normalize()
        if k % 2:
            a = t.cross(a).normalized()
        v = a.cross(t)
        mtx = Matrix(((t.x * 1.5, v.x, a.x, p.x), (t.y * 1.5, v.y, a.y, p.y), (t.z * 1.5, v.z, a.z, p.z), (0, 0, 0, 1)))
        add_torus(bm, (0, 0, 0), R_, r, "Z", 6, 3, pre=mtx)
        k += 1


# ================================================================= DOCK KIT
def d_freight_lift(off):
    # Freight lift platform 4.0 (X) x 3.6 (Y); origin bottom centre; sliding gate on the front (-Y); guide columns to 6 m at the rear.
    box("fl_frame", (0, 0, 0.06), (4.0, 3.6, 0.12), "painted_dark", 0.006, segs=1)
    box("fl_deck", (0, 0, 0.125), (3.92, 3.52, 0.01), "diamond_plate", 0.002, segs=1)
    box("fl_nosing", (0, -1.74, 0.133), (3.9, 0.06, 0.006), "steel", 0.001)
    hazard_band("fl_edge_hz", ((0, -1.8, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), -2.0, 2.0, 0.0, 0.12, sw=0.1)
    # Guard rails (sides +-X, rear +Y) with mesh infill and toe boards
    for sx in (-1, 1):
        x = sx * 1.955
        for y in (-1.6, -0.5, 0.6):
            box("fl_post", (x, y, 0.615), (0.05, 0.05, 0.97), "hazard", 0.003, segs=1)
        box("fl_toprail", (x, 0.0, 1.1), (0.05, 3.25, 0.05), "hazard", 0.003, segs=1)
        box("fl_toe", (x, 0.0, 0.205), (0.006, 3.25, 0.15), "galvanized", 0.001)
        lattice("fl_mesh", "galvanized", -1.6, 1.55, 0.28, 1.075, x, 0.08, 0.005, axis="Y")
    for x in (-0.6, 0.6):
        box("fl_post_r", (x, 1.735, 0.615), (0.05, 0.05, 0.97), "hazard", 0.003, segs=1)
    box("fl_toprail_r", (0, 1.735, 1.1), (3.52, 0.05, 0.05), "hazard", 0.003, segs=1)
    box("fl_toe_r", (0, 1.735, 0.205), (3.52, 0.006, 0.15), "galvanized", 0.001)
    lattice("fl_mesh_r", "galvanized", -1.75, 1.75, 0.28, 1.075, 1.735, 0.08, 0.005, axis="X")
    box("fl_sign", (0, 1.705, 0.82), (0.62, 0.004, 0.28), "board_white", 0.001)
    text_obj("fl_sign_t1", "LIFT 2", "painted_dark", (0, 1.7015, 0.86), 0.1)
    text_obj("fl_sign_t2", "MAX 2000 KG", "painted_dark", (0, 1.7015, 0.74), 0.05)
    # Guide columns with T-rails, header and sheaves
    for sx in (-1, 1):
        x = sx * 1.88
        box("fl_column", (x, 1.68, 3.0), (0.24, 0.24, 6.0), "painted_grey", 0.004, segs=1)
        box("fl_col_base", (x, 1.68, 0.01), (0.32, 0.32, 0.02), "painted_dark", 0.002)
        bolts("fl_col_anchors", [(x + dx, 1.68 + dy, 0.026) for dx in (-0.13, 0.13) for dy in (-0.13, 0.13)], "steel", 0.014, 0.014, "Z")
        box("fl_trail_flange", (sx * 1.754, 1.68, 3.0), (0.012, 0.09, 5.9), "steel", 0.0)
        box("fl_trail_blade", (sx * 1.73, 1.68, 3.0), (0.036, 0.016, 5.9), "steel", 0.0)
        for z in (1.0, 2.5, 4.0, 5.5):
            box("fl_trail_bracket", (sx * 1.765, 1.68, z), (0.03, 0.16, 0.08), "painted_dark", 0.002)
        box("fl_limit_switch", (x, 1.545, 2.6), (0.08, 0.03, 0.12), "painted_dark", 0.004)
    box("fl_header", (0, 1.68, 5.925), (4.0, 0.24, 0.15), "painted_grey", 0.004, segs=1)
    for sx in (-1, 1):
        x = sx * 1.2
        cyl("fl_sheave", (x, 1.68, 5.70), 0.12, 0.05, "painted_dark", "X", 24, bevel=0.004)
        for s in (-1, 1):
            box("fl_sheave_cheek", (x + s * 0.04, 1.68, 5.75), (0.012, 0.28, 0.2), "painted_grey", 0.002)
        bm = bmesh.new()
        for dx in (-0.012, 0.012):
            add_tube(bm, [(x + dx, 1.56, 2.46), (x + dx, 1.56, 5.70)], 0.006, 6, caps=True)
            arc = [(x + dx, 1.68 - 0.12 * math.cos(math.pi * k / 8), 5.70 + 0.12 * math.sin(math.pi * k / 8)) for k in range(9)]
            add_tube(bm, arc + [(x + dx, 1.80, 5.2)], 0.006, 6, caps=True)
        obj("fl_ropes", "steel", bm)
        box("fl_hitch", (x, 1.80, 5.15), (0.08, 0.06, 0.12), "painted_dark", 0.004)
    # Carriage sling: stiles, crosshead, guide shoes, braces
    for sx in (-1, 1):
        box("fl_stile", (sx * 1.66, 1.56, 1.29), (0.12, 0.1, 2.34), "painted_dark", 0.004, segs=1)
        for z in (0.35, 2.25):
            box("fl_shoe", (sx * 1.735, 1.65, z), (0.06, 0.12, 0.14), "steel", 0.004)
        tube("fl_brace", [(sx * 1.62, 1.52, 2.15), (sx * 1.85, 0.4, 0.14)], 0.025, "painted_dark", 8)
    box("fl_crosshead", (0, 1.56, 2.36), (3.44, 0.12, 0.2), "painted_dark", 0.004, segs=1)
    hazard_band("fl_xh_hz", ((0, 1.4995, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), -1.7, 1.7, 2.27, 2.45, sw=0.1)
    bolts("fl_rope_sockets", [(sx * 1.2 + dx, 1.56, 2.475) for sx in (-1, 1) for dx in (-0.012, 0.012)], "steel", 0.014, 0.03, "Z", verts=8)
    # Front sliding gate: posts, top track, two telescopic mesh leaves
    for sx in (-1, 1):
        box("fl_gate_post", (sx * 1.97, -1.76, 1.065), (0.06, 0.06, 1.87), "hazard", 0.003, segs=1)
    box("fl_track", (0, -1.77, 2.0), (4.0, 0.1, 0.08), "painted_dark", 0.003, segs=1, recess=(("-z", 0.012, 0.05),))
    for x0, x1, y in ((-1.9, 0.05, -1.735), (-0.05, 1.9, -1.795)):
        xc, w = (x0 + x1) / 2, x1 - x0
        for loc, size in (((xc, y, 1.94), (w, 0.035, 0.035)), ((xc, y, 0.17), (w, 0.035, 0.035)),
                          ((x0 + 0.0175, y, 1.055), (0.035, 0.035, 1.77)), ((x1 - 0.0175, y, 1.055), (0.035, 0.035, 1.77))):
            box("fl_leaf_frame", loc, size, "painted_dark", 0.002, segs=1)
        lattice("fl_leaf_mesh", "galvanized", x0 + 0.035, x1 - 0.035, 0.19, 1.92, y, 0.06, 0.004)
        for x in (x0 + 0.15, x1 - 0.15):
            cyl("fl_roller", (x, y, 1.99), 0.026, 0.02, "steel", "Y", 12)
    box("fl_gate_handle", (1.7, -1.83, 1.1), (0.025, 0.025, 0.45), "steel", 0.006, segs=2)
    # Control post with buttons, key switch and beacon (inside the front-right corner)
    box("fl_cpost", (1.72, -1.45, 0.72), (0.08, 0.08, 1.18), "painted_dark", 0.003, segs=1)
    box("fl_cbox", (1.72, -1.45, 1.42), (0.2, 0.12, 0.3), "hazard", 0.012, segs=2)
    for i, m in enumerate(("led_green", "board_white")):
        cyl("fl_btn_collar", (1.67 + i * 0.1, -1.513, 1.48), 0.02, 0.008, "painted_dark", "Y", 16)
        cyl("fl_btn", (1.67 + i * 0.1, -1.52, 1.48), 0.014, 0.012, m, "Y", 16, bevel=0.002)
    cyl("fl_stop_collar", (1.72, -1.513, 1.36), 0.03, 0.008, "hazard", "Y", 20)
    cyl("fl_stop", (1.72, -1.527, 1.36), 0.026, 0.024, "painted_red", "Y", 20, r2=0.022, bevel=0.003)
    cyl("fl_key", (1.79, -1.513, 1.36), 0.012, 0.008, "steel", "Y", 12)
    cyl("fl_beacon_pole", (1.72, -1.45, 1.67), 0.015, 0.2, "painted_dark", "Z", 12)
    cyl("fl_beacon_base", (1.72, -1.45, 1.775), 0.045, 0.02, "painted_dark", "Z", 20)
    bm = bmesh.new()
    prof = [(max(0.0005, 0.04 * math.cos(math.pi / 2 * k / 6)), 1.785 + 0.075 * math.sin(math.pi / 2 * k / 6)) for k in range(7)]
    add_revolve(bm, prof, 20, closed=False, cap_ends=True, loc=(1.72, -1.45, 0))
    obj("fl_beacon", "led_amber", bm)
    tube("fl_ctrl_cable", fillet([(1.72, -1.41, 0.3), (1.72, -1.38, 0.14), (1.72, 1.3, 0.14), (1.82, 1.56, 0.14)], 0.05), 0.012, "cable_black", 8)
    return finish("freight_lift", off, note="origin bottom centre; gate side -Y; columns/header to Z 6.0")


def d_rollup_door(off):
    # Roll-up bay door for a 5.0 x 4.5 opening, mounted on the -Y face of the wall (wall plane Y=0). Origin bottom centre.
    hw = 2.5
    pitch = 0.0745
    n = 60
    bm = bmesh.new()
    outer = [(-0.004 - 0.013 * math.sin(math.pi * k / 6), 0.0745 * k / 6) for k in range(7)]
    inner = [(y + 0.0018, z) for y, z in reversed(outer)]
    prof = outer + inner
    for i in range(n):
        z0 = 0.06 + i * pitch
        add_prism(bm, [(y, z + z0) for y, z in prof], ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -hw - 0.06, hw + 0.06)
    obj("rd_slats", "galvanized", bm)
    zv = 0.06 + 22 * pitch
    for x in (-1.75, -1.05, -0.35, 0.35, 1.05, 1.75):
        box("rd_vision_frame", (x, -0.0175, zv + 0.037), (0.25, 0.004, 0.058), "painted_dark", 0.001)
        box("rd_vision_glass", (x, -0.0195, zv + 0.037), (0.21, 0.003, 0.036), "glass_lens", 0.0)
    box("rd_bottom_bar", (0, -0.03, 0.033), (2 * hw + 0.06, 0.05, 0.06), "painted_dark", 0.004, segs=1)
    box("rd_seal", (0, -0.03, 0.004), (2 * hw, 0.036, 0.008), "rubber", 0.0)
    for x in (-1.2, 1.2):
        tube("rd_lift_handle", fillet([(x - 0.08, -0.055, 0.04), (x - 0.08, -0.09, 0.04), (x + 0.08, -0.09, 0.04), (x + 0.08, -0.055, 0.04)], 0.02), 0.009, "steel", 8)
    box("rd_lock_body", (-2.2, -0.06, 0.04), (0.12, 0.02, 0.04), "steel", 0.003)
    cyl("rd_lock_bolt", (-2.29, -0.06, 0.04), 0.008, 0.08, "steel", "X", 10)
    for sx in (-1, 1):
        prof = [(2.5, -0.005), (2.62, -0.005), (2.62, -0.105), (2.5, -0.105), (2.5, -0.095), (2.61, -0.095), (2.61, -0.015), (2.5, -0.015)]
        prof = [(sx * x, y) for x, y in prof]
        prism("rd_guide", prof, ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 0.0, 4.72, "galvanized")
        box("rd_wall_angle", (sx * 2.67, -0.003, 2.36), (0.1, 0.006, 4.72), "galvanized", 0.001)
        bolts("rd_wall_bolts", [(sx * 2.68, -0.008, 0.3 + i * 0.6) for i in range(8)], "steel", 0.01, 0.008, "Y")
        u0, u1 = sorted((sx * 2.5, sx * 2.62))
        hazard_band("rd_guide_hz", ((0, -0.105, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), u0, u1, 0.0, 1.5, sw=0.09)
    hood = [(0, 4.55), (-0.42, 4.55), (-0.58, 4.68), (-0.62, 4.9), (-0.58, 5.1), (-0.45, 5.22), (0, 5.25)]
    prism("rd_hood", hood, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -2.75, 2.75, "galvanized", 0.003, 1, angle=20)
    for sx in (-1, 1):
        prism("rd_hood_end", [(y - 0.01 if y < 0 else y, z) for y, z in hood], ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), sx * 2.75, sx * 2.765, "painted_dark")
    # Gear motor and chain hoist (right end)
    box("rd_gearbox", (2.92, -0.32, 4.9), (0.3, 0.26, 0.3), "painted_dark", 0.01, segs=2)
    cyl("rd_motor", (2.92, -0.6, 4.92), 0.11, 0.3, "painted_grey", "Y", 24, bevel=0.004)
    bm = bmesh.new()
    for k in range(12):
        a = 2 * math.pi * k / 12
        add_box(bm, (2.92 + 0.118 * math.cos(a), -0.6, 4.92 + 0.118 * math.sin(a)), (0.016, 0.26, 0.004), rot=(0, -math.degrees(a), 0))
    obj("rd_motor_fins", "painted_grey", bm)
    cyl("rd_fan_cover", (2.92, -0.775, 4.92), 0.105, 0.05, "painted_dark", "Y", 24, bevel=0.004)
    box("rd_terminal_box", (2.92, -0.58, 5.06), (0.1, 0.12, 0.05), "painted_grey", 0.004)
    cyl("rd_sprocket", (3.12, -0.32, 4.9), 0.16, 0.03, "painted_dark", "X", 32, bevel=0.003)
    cyl("rd_sprocket_hub", (3.12, -0.32, 4.9), 0.05, 0.06, "steel", "X", 16)
    bm = bmesh.new()
    loop = [(3.12, -0.16, 4.9), (3.12, -0.16, 1.25)] + [(3.12, -0.32 + 0.16 * math.cos(math.pi * k / 8), 1.25 - 0.16 * math.sin(math.pi * k / 8)) for k in range(1, 8)] + [(3.12, -0.48, 1.25), (3.12, -0.48, 4.9)]
    chain_links(bm, loop, pitch=0.03)
    obj("rd_chain", "steel", bm)
    tube("rd_conduit", fillet([(2.92, -0.6, 5.08), (2.92, -0.6, 5.2), (3.22, -0.6, 5.2), (3.22, -0.04, 5.2), (3.22, -0.04, 1.55)], 0.06), 0.012, "galvanized", 8)
    box("rd_station", (3.22, -0.045, 1.45), (0.12, 0.08, 0.2), "painted_grey", 0.008)
    for i, m in enumerate(("led_green", "painted_red", "painted_dark")):
        cyl("rd_station_btn", (3.22, -0.09, 1.51 - i * 0.055), 0.014, 0.01, m, "Y", 16, bevel=0.002)
    return finish("rollup_door", off, note="origin bottom centre of 5.0 x 4.5 opening; wall plane Y=0; hardware on -Y")


def d_dock_leveler(off):
    # Dock leveler 2.0 (X) x 2.5 (Y) incl. hinged lip at -Y; origin top centre at floor level.
    box("dl_deck", (0, 0.2, -0.0125), (1.96, 2.1, 0.025), "diamond_plate", 0.003, segs=1)
    th = 4.0
    lip_c = Vector((0, -1.05, -0.008 - 0.2 * math.sin(math.radians(th))))
    box("dl_lip", tuple(lip_c), (1.96, 0.4, 0.016), "diamond_plate", 0.004, segs=2, rot=(th, 0, 0))
    bm = bmesh.new()
    for i in range(12):
        x = -0.9 + i * (1.8 / 11)
        add_cyl(bm, (x, -0.85, -0.022), 0.017, 0.12, "X", 12)
    obj("dl_knuckles", "painted_dark", bm)
    cyl("dl_pin", (0, -0.85, -0.022), 0.007, 1.96, "steel", "X", 8)
    for sx in (-1, 1):
        box("dl_curb", (sx * 1.03, 0.2, -0.03), (0.06, 2.16, 0.06), "galvanized", 0.002)
        hazard_band("dl_side_hz", ((0, 0, 0.0002), (1, 0, 0), (0, 1, 0), (0, 0, 1)), *sorted((sx * 0.98, sx * 0.86)), -0.82, 1.22, sw=0.1)
    box("dl_curb_back", (0, 1.31, -0.03), (2.12, 0.06, 0.06), "galvanized", 0.002)
    box("dl_pit", (0, 0.2, -0.11), (2.0, 2.2, 0.02), "painted_dark", 0.0)
    nl = Vector((0, -math.sin(math.radians(th)), math.cos(math.radians(th))))
    vl_ = Vector((0, math.cos(math.radians(th)), math.sin(math.radians(th))))
    hazard_band("dl_lip_hz", (tuple(lip_c + nl * 0.008), (1, 0, 0), tuple(vl_), tuple(nl)), -0.98, 0.98, -0.2, -0.1, w0=0.0002, sw=0.1)
    bolts("dl_deck_bolts", [(sx * 0.9, y, 0.002) for sx in (-1, 1) for y in (-0.7, 0.2, 1.1)], "steel", 0.01, 0.004, "Z", dome=True)
    return finish("dock_leveler", off, note="origin top centre at floor level; lip at -Y; pit to Z -0.12")


def d_container(off):
    # ISO 20 ft container 2.44 (X) x 6.06 (Y) x 2.59 (Z); origin bottom centre; doors at -Y.
    P = "crate_green"
    W, L, H = 2.44, 6.06, 2.59
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("ct_post", (sx * 1.15, sy * 2.96, 1.295), (0.14, 0.14, 2.354), P, 0.004, segs=1)
            for z in (0.059, H - 0.059):
                box("ct_casting", (sx * 1.131, sy * 2.949, z), (0.178, 0.162, 0.118), "painted_dark", 0.004, segs=1)
                bm = bmesh.new()
                add_box(bm, (sx * 1.2205, sy * 2.949, z), (0.002, 0.065, 0.04))
                add_box(bm, (sx * 1.131, sy * 3.0305, z), (0.06, 0.002, 0.04))
                add_box(bm, (sx * 1.131, sy * 2.949, z + (0.0595 if z > 1 else -0.0595)), (0.06, 0.1, 0.002))
                obj("ct_casting_holes", "cable_black", bm)
        box("ct_rail_bottom", (sx * 1.17, 0, 0.08), (0.1, 5.78, 0.16), P, 0.003, segs=1)
        box("ct_rail_top", (sx * 1.19, 0, 2.53), (0.06, 5.78, 0.12), P, 0.003, segs=1)
        for y in (-1.025, 1.025):
            box("ct_pocket_frame", (sx * 1.205, y, 0.075), (0.03, 0.42, 0.15), P, 0.003, segs=1)
            box("ct_pocket_hole", (sx * 1.2215, y, 0.075), (0.002, 0.36, 0.115), "cable_black", 0.0)
        # Corrugated side wall
        p = 5.76 / 21
        pts = []
        for k in range(21):
            b = -2.88 + k * p
            pts += [(b, 0.0), (b + 0.068, 0.0), (b + 0.137, -0.036), (b + 0.205, -0.036)]
        pts.append((2.88, 0.0))
        prof = pts + [(u, v - 0.003) for u, v in reversed(pts)]
        prism("ct_side", prof, ((sx * 1.2, 0, 0), (0, 1, 0), (sx, 0, 0), (0, 0, 1)), 0.16, 2.47, P)
        for y in (-2.55, 2.55):
            box("ct_vent", (sx * 1.205, y, 2.32), (0.012, 0.16, 0.1), P, 0.003)
            bm = bmesh.new()
            for i in range(4):
                add_box(bm, (sx * 1.2115, y, 2.29 + i * 0.02), (0.002, 0.13, 0.008))
            obj("ct_vent_slots", "cable_black", bm)
    box("ct_patch", (1.2025, -0.8, 0.95), (0.003, 0.62, 0.5), "painted_dark", 0.0)
    box("ct_patch2", (-1.2025, 1.4, 1.7), (0.003, 0.4, 0.35), "painted_dark", 0.0)
    # Closed end wall (+Y)
    p = 2.3 / 8
    pts = []
    for k in range(8):
        b = -1.15 + k * p
        pts += [(b, 0.0), (b + 0.07, 0.0), (b + 0.14, -0.03), (b + 0.21, -0.03)]
    pts.append((1.15, 0.0))
    prof = pts + [(u, v - 0.003) for u, v in reversed(pts)]
    prism("ct_endwall", prof, ((0, 3.0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), 0.16, 2.47, P)
    box("ct_end_rail_top", (0, 2.99, 2.53), (2.3, 0.08, 0.12), P, 0.003, segs=1)
    box("ct_end_rail_bot", (0, 2.99, 0.08), (2.3, 0.1, 0.16), P, 0.003, segs=1)
    # Roof (shallow corrugation)
    pts = []
    for k in range(12):
        b = -2.88 + k * 0.48
        pts += [(b, 0.0), (b + 0.12, 0.0), (b + 0.24, -0.018), (b + 0.36, -0.018)]
    pts.append((2.88, 0.0))
    prof = pts + [(u, v - 0.003) for u, v in reversed(pts)]
    prism("ct_roof", prof, ((0, 0, 2.575), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -1.16, 1.16, P)
    box("ct_underframe", (0, 0, 0.1), (2.3, 5.8, 0.04), "painted_dark", 0.0)
    # Door end (-Y): header, sill, two leaves with ribs, locking bars, handles, hinges
    box("ct_door_header", (0, -2.99, 2.5), (2.3, 0.12, 0.18), P, 0.004, segs=1)
    box("ct_door_sill", (0, -2.99, 0.085), (2.3, 0.12, 0.17), P, 0.004, segs=1)
    yd = -3.0
    for sd in (-1, 1):
        xc = sd * 0.572
        box("ct_door_leaf", (xc, yd + 0.015, 1.295), (1.14, 0.03, 2.25), P, 0.004, segs=1)
        for i in range(4):
            box("ct_door_rib", (xc + (i - 1.5) * 0.24, yd - 0.004, 1.295), (0.12, 0.012, 1.95), P, 0.004, segs=1)
        for z in (0.28, 2.31):
            box("ct_door_band", (xc, yd - 0.003, z), (1.12, 0.01, 0.1), P, 0.003, segs=1)
        for bx in (xc - sd * 0.17, xc + sd * 0.33):
            cyl("ct_lockbar", (bx, yd - 0.03, 1.29), 0.015, 2.2, "galvanized", "Z", 12)
            for z in (0.6, 1.5, 2.05):
                box("ct_bar_guide", (bx, yd - 0.022, z), (0.07, 0.03, 0.04), "galvanized", 0.003)
            for z in (0.17, 2.41):
                box("ct_cam_keeper", (bx, yd - 0.035, z), (0.08, 0.05, 0.06), "painted_dark", 0.004)
            hx = bx - sd * 0.165
            box("ct_handle", (hx, yd - 0.055, 1.1), (0.33, 0.022, 0.026), "galvanized", 0.006, segs=2)
            box("ct_handle_hub", (bx, yd - 0.045, 1.1), (0.05, 0.04, 0.06), "galvanized", 0.004)
            box("ct_retainer", (bx - sd * 0.31, yd - 0.035, 1.1), (0.04, 0.04, 0.08), "painted_dark", 0.004)
        for z in (0.35, 0.95, 1.6, 2.2):
            box("ct_hinge_blade", (sd * 1.08, yd - 0.008, z), (0.14, 0.014, 0.05), "galvanized", 0.003)
            cyl("ct_hinge_pin", (sd * 1.165, yd - 0.01, z), 0.013, 0.07, "galvanized", "Z", 12)
    box("ct_overlap", (0.01, yd - 0.012, 1.295), (0.05, 0.022, 2.2), P, 0.003)
    box("ct_csc_plate", (-0.85, yd - 0.004, 0.8), (0.22, 0.004, 0.13), "galvanized", 0.001)
    bolts("ct_csc_rivets", [(-0.85 + dx, yd - 0.007, 0.8 + dz) for dx in (-0.1, 0.1) for dz in (-0.055, 0.055)], "steel", 0.004, 0.003, "Y", dome=True)
    # Stencils (white paint)
    tz = yd - 0.0105
    text_obj("ct_txt_code", "RNXU 220714 2", "board_white", (0.57, tz, 2.13), 0.1)
    text_obj("ct_txt_type", "22G1", "board_white", (0.33, tz, 1.98), 0.1)
    text_obj("ct_txt_gross", "MAX.GROSS 30480 KG", "board_white", (-0.57, tz, 2.13), 0.038)
    text_obj("ct_txt_tare", "TARE 2200 KG", "board_white", (-0.57, tz, 2.07), 0.038)
    text_obj("ct_txt_side_p", "RNXU 220714 2", "board_white", (1.2025, 1.5, 2.2), 0.24, rot=(90, 0, 90))
    text_obj("ct_txt_side_n", "RNXU 220714 2", "board_white", (-1.2025, -1.5, 2.2), 0.24, rot=(90, 0, -90))
    return finish("container_20ft", off, note="origin bottom centre; doors at -Y")


def pallet_bm(bm, pre, seed=0, nails=None):
    rng = (seed * 7919 + 13) % 1000 / 1000.0
    j = lambda k: ((rng * 9301 + k * 49297) % 233280) / 233280.0 - 0.5
    T = 0.022
    for i, (y, w) in enumerate(((-0.3275, 0.145), (-0.1625, 0.1), (0.0, 0.145), (0.1625, 0.1), (0.3275, 0.145))):
        add_box(bm, (j(i) * 0.006, y + j(i + 9) * 0.004, 0.133), (1.2, w - 0.004, T), rot=(0, 0, j(i + 3) * 0.6), pre=pre)
        if nails is not None:
            for x in (-0.5275, 0.0, 0.5275):
                for dy in (-w / 4, w / 4):
                    nails.append(pre @ Vector((x, y + dy, 0.1445)))
    for i, x in enumerate((-0.5275, 0.0, 0.5275)):
        add_box(bm, (x, j(i + 20) * 0.004, 0.111), (0.145, 0.8, T), pre=pre)
        for y, w in ((-0.3275, 0.145), (0.0, 0.145), (0.3275, 0.145)):
            add_box(bm, (x, y, 0.061), (0.145 if i != 1 else 0.145, 0.1 if y else 0.145, 0.078), pre=pre)
    for i, (y, w) in enumerate(((-0.3275, 0.1), (0.0, 0.145), (0.3275, 0.1))):
        add_box(bm, (0, y, 0.011), (1.2, w, T), rot=(0, 0, j(i + 30) * 0.4), pre=pre)


def d_pallet(off):
    # EUR-style wooden pallet 1.2 (X) x 0.8 (Y) x 0.144; origin bottom centre.
    bm = bmesh.new()
    nails = []
    pallet_bm(bm, Matrix(), 1, nails)
    p = obj("pl_wood", "wood_pallet", bm, 0.003, 1)
    cut(p, lambda b: add_box(b, (0.6, 0.3275, 0.144), (0.05, 0.05, 0.03), rot=(30, 20, 40)))
    bolts("pl_nails", nails, "steel", 0.004, 0.002, "Z", verts=6)
    return finish("pallet", off, note="origin bottom centre")


def d_pallet_stack(off):
    # Stack of 6 empty pallets (slightly misaligned); origin bottom centre.
    for i in range(6):
        bm = bmesh.new()
        a = ((i * 37) % 11 - 5) * 0.5
        mtx = M((((i * 53) % 7 - 3) * 0.006, ((i * 29) % 5 - 2) * 0.006, i * 0.144), (0, 0, a))
        pallet_bm(bm, mtx, i + 3)
        obj("ps_wood", "wood_pallet", bm, 0.003, 1)
    return finish("pallet_stack", off, note="origin bottom centre; 6 pallets, height 0.864")


def d_pallet_boxes(off):
    # Pallet with three layers of cardboard boxes, corner boards and strapping; origin bottom centre.
    bm = bmesh.new()
    pallet_bm(bm, Matrix(), 5)
    obj("pb_pallet", "wood_pallet", bm, 0.003, 1)
    k = 0
    for layer in range(3):
        z = 0.144 + layer * 0.282 + 0.14
        for ix in range(3):
            for iy in range(2):
                k += 1
                jx = ((k * 37) % 9 - 4) * 0.002
                jr = ((k * 13) % 7 - 3) * 0.35
                x, y = -0.4 + ix * 0.4 + jx, -0.2 + iy * 0.4
                box("pb_box", (x, y, z), (0.395, 0.395, 0.28), "cardboard", 0.004, segs=1, rot=(0, 0, jr))
                box("pb_tape", (x, y, z + 0.1405), (0.395, 0.05, 0.001), "board_white", 0.0, rot=(0, 0, jr))
                if iy == 0 and (k % 3):
                    box("pb_label", (x + 0.06, y - 0.1985, z + 0.03), (0.12, 0.001, 0.08), "board_white", 0.0)
    top = 0.144 + 3 * 0.282
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("pb_corner_a", (sx * 0.595, sy * 0.375, (0.144 + top) / 2), (0.008, 0.05, top - 0.15), "cardboard", 0.001)
            box("pb_corner_b", (sx * 0.575, sy * 0.395, (0.144 + top) / 2), (0.05, 0.008, top - 0.15), "cardboard", 0.001)
    bm = bmesh.new()
    for x in (-0.3, 0.3):
        add_box(bm, (x, 0, top + 0.002), (0.016, 0.81, 0.002))
        for sy in (-1, 1):
            add_box(bm, (x, sy * 0.402, (0.12 + top) / 2), (0.016, 0.002, top - 0.12))
    obj("pb_straps", "painted_dark", bm)
    return finish("pallet_boxes", off, note="origin bottom centre; stack top at Z %.3f" % (top + 0.003))


def d_forklift(off):
    # Electric counterbalance forklift ~1.2 (X) x 2.44 (Y) x 2.16 (Z); forks toward -Y; origin bottom centre.
    def wheel(nm, x, y, r, w, nlug):
        zc = r + 0.011  # tread lugs touch the floor
        cyl(nm + "_tire", (x, y, zc), r, w, "rubber", "X", 32, bevel=0.025, segs=2)
        cyl(nm + "_rim", (x, y, zc), r * 0.62, w + 0.01, "painted_grey", "X", 24, bevel=0.006)
        cyl(nm + "_hub", (x, y, zc), r * 0.25, w + 0.02, "steel", "X", 12)
        s = 1 if x > 0 else -1
        bolts(nm + "_nuts", [(x + s * (w / 2 + 0.012), y + r * 0.17 * math.cos(2 * math.pi * k / 6), zc + r * 0.17 * math.sin(2 * math.pi * k / 6)) for k in range(6)], "steel", 0.012, 0.012, "X")
        bm = bmesh.new()
        for k in range(nlug):
            a = 2 * math.pi * k / nlug
            add_box(bm, (x, y + (r + 0.004) * math.sin(a), zc + (r + 0.004) * math.cos(a)), (w * 0.85, 0.035, 0.014), rot=(-math.degrees(a), 0, 0))
        obj(nm + "_tread", "rubber", bm)
    for sx in (-1, 1):
        wheel("fk_front", sx * 0.47, -0.35, 0.29, 0.2, 22)
        wheel("fk_rear", sx * 0.43, 0.62, 0.21, 0.16, 16)
        torus("fk_arch", (sx * 0.47, -0.35, 0.301), 0.335, 0.02, "rubber", "X", 16, 6, rot=(90, 0, 0), arc=math.pi)
    box("fk_chassis", (0, 0.1, 0.32), (0.84, 1.24, 0.36), "painted_dark", 0.01, segs=1)
    box("fk_body", (0, 0.12, 0.56), (1.12, 1.32, 0.14), "hazard", 0.02, segs=2)
    box("fk_hood", (0, 0.24, 0.8), (1.0, 0.62, 0.36), "hazard", 0.03, segs=3, grooves=(("x", 0.04, 0.004, 0.003), ("-x", 0.04, 0.004, 0.003)))
    box("fk_cowl", (0, -0.43, 0.92), (1.0, 0.2, 0.6), "hazard", 0.03, segs=3)
    box("fk_floor", (0, -0.21, 0.635), (0.9, 0.26, 0.012), "diamond_plate", 0.002)
    for sx in (-1, 1):
        box("fk_step", (sx * 0.56, -0.2, 0.42), (0.08, 0.3, 0.025), "diamond_plate", 0.003)
    cprof = [(0.52, 0.15), (0.86, 0.15), (0.93, 0.3), (0.93, 0.86), (0.86, 1.02), (0.52, 1.02)]
    prism("fk_counterweight", cprof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -0.56, 0.56, "painted_dark", 0.02, 2, angle=25)
    hazard_band("fk_cw_hz", ((0, 0.93, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0)), -0.5, 0.5, 0.4, 0.5, sw=0.08)
    for sx in (-1, 1):
        box("fk_taillight", (sx * 0.42, 0.932, 0.75), (0.1, 0.006, 0.05), "led_red", 0.002)
    box("fk_hitch", (0, 0.95, 0.24), (0.12, 0.06, 0.08), "steel", 0.006)
    # Seat, steering, dash, levers
    box("fk_seat_base", (0, 0.22, 1.0), (0.4, 0.38, 0.04), "painted_dark", 0.004)
    box("fk_seat", (0, 0.2, 1.06), (0.48, 0.45, 0.1), "rubber", 0.04, segs=3)
    box("fk_backrest", (0, 0.43, 1.32), (0.46, 0.08, 0.42), "rubber", 0.035, segs=3, rot=(-10, 0, 0))
    for sx in (-1, 1):
        box("fk_hip_rest", (sx * 0.25, 0.25, 1.17), (0.05, 0.25, 0.12), "rubber", 0.02, segs=2)
    cyl("fk_column", (0, -0.31, 1.13), 0.03, 0.32, "painted_dark", "Z", 12, rot=(-30, 0, 0))
    torus("fk_wheel", (0, -0.235, 1.268), 0.165, 0.016, "rubber", "Z", 32, 8, rot=(-30, 0, 0))
    bm = bmesh.new()
    pre = M((0, -0.235, 1.268), (-30, 0, 0))
    for a in (90, 210, 330):
        add_box(bm, (0.08 * math.cos(math.radians(a)), 0.08 * math.sin(math.radians(a)), 0), (0.16, 0.025, 0.012), rot=(0, 0, a), pre=pre)
    add_cyl(bm, (0, 0, 0.01), 0.04, 0.03, "Z", 16, pre=pre)
    add_cyl(bm, (0.12, -0.1, 0.04), 0.014, 0.06, "Z", 12, pre=pre)
    obj("fk_wheel_spokes", "painted_dark", bm)
    box("fk_display", (-0.2, -0.33, 1.15), (0.14, 0.004, 0.09), "screen", 0.0, rot=(25, 0, 0))
    for i, m in enumerate(("painted_dark", "hazard", "painted_red")):
        x = 0.26 + i * 0.05
        cyl("fk_lever", (x, -0.36, 1.27), 0.007, 0.2, "painted_dark", "Z", 8, rot=(-12, 0, 0))
        cyl("fk_lever_knob", (x, -0.34, 1.37), 0.018, 0.04, m, "Z", 12, bevel=0.006)
    # Overhead guard
    bm = bmesh.new()
    for sx in (-1, 1):
        add_tube(bm, [(sx * 0.47, -0.47, 1.1), (sx * 0.47, -0.36, 2.08)], 0.03, 8)
        add_tube(bm, [(sx * 0.47, 0.72, 1.0), (sx * 0.47, 0.64, 2.08)], 0.03, 8)
        add_tube(bm, [(sx * 0.47, -0.39, 2.08), (sx * 0.47, 0.67, 2.08)], 0.028, 8)
    for y in (-0.36, 0.64):
        add_tube(bm, [(-0.5, y, 2.08), (0.5, y, 2.08)], 0.028, 8)
    for i in range(7):
        add_box(bm, (0, -0.25 + i * 0.135, 2.095), (0.92, 0.06, 0.014))
    obj("fk_guard", "painted_dark", bm, 0.0)
    tube("fk_grab", fillet([(-0.495, -0.44, 1.15), (-0.53, -0.44, 1.2), (-0.53, -0.38, 1.75), (-0.495, -0.37, 1.8)], 0.04), 0.014, "steel", 8)
    for sx in (-1, 1):
        box("fk_worklight", (sx * 0.47, -0.43, 1.93), (0.09, 0.07, 0.08), "painted_dark", 0.008)
        box("fk_worklight_lens", (sx * 0.47, -0.467, 1.93), (0.07, 0.004, 0.06), "lamp_warm", 0.002)
    cyl("fk_beacon_base", (0, 0.55, 2.115), 0.045, 0.02, "painted_dark", "Z", 16)
    cyl("fk_beacon", (0, 0.55, 2.14), 0.04, 0.04, "led_amber", "Z", 16, r2=0.032, bevel=0.006)
    box("fk_mirror", (-0.56, -0.38, 1.85), (0.1, 0.012, 0.07), "glass_lens", 0.004)
    tube("fk_mirror_arm", [(-0.5, -0.38, 1.8), (-0.56, -0.38, 1.84)], 0.006, "painted_dark", 6)
    # Mast, lift cylinder, chains
    for sx in (-1, 1):
        box("fk_mast_outer", (sx * 0.34, -0.62, 1.05), (0.07, 0.12, 1.9), "painted_dark", 0.004, segs=1, grooves=(("-y", 0.02, 0.004, 0.003),))
        box("fk_mast_inner", (sx * 0.27, -0.63, 1.1), (0.06, 0.09, 1.88), "painted_dark", 0.004, segs=1)
        tube("fk_tilt_cyl", [(sx * 0.42, -0.47, 0.62), (sx * 0.38, -0.58, 0.95)], 0.034, "painted_dark", 10)
        tube("fk_tilt_rod", [(sx * 0.38, -0.58, 0.95), (sx * 0.37, -0.6, 1.05)], 0.016, "steel", 8)
    box("fk_mast_top", (0, -0.62, 1.98), (0.76, 0.1, 0.06), "painted_dark", 0.004)
    box("fk_mast_bot", (0, -0.62, 0.18), (0.76, 0.1, 0.08), "painted_dark", 0.004)
    cyl("fk_lift_cyl", (0, -0.58, 0.95), 0.045, 1.6, "painted_dark", "Z", 16)
    cyl("fk_lift_rod", (0, -0.58, 1.85), 0.025, 0.2, "steel", "Z", 12)
    cyl("fk_chain_sheave", (0, -0.61, 1.95), 0.06, 0.2, "steel", "X", 16)
    bm = bmesh.new()
    for x in (-0.08, 0.08):
        for y in (-0.665, -0.555):
            for i in range(45):
                z = 0.62 + i * 0.03
                add_box(bm, (x + (0.006 if i % 2 else -0.006), y, z), (0.004, 0.022, 0.034))
    obj("fk_chains", "steel", bm)
    bm = bmesh.new()
    for x in (-0.15, 0.15):
        add_tube(bm, fillet([(x, -0.5, 0.6), (x, -0.56, 0.9), (x, -0.6, 1.4), (x, -0.66, 1.0), (x * 0.8, -0.7, 0.62)], 0.1), 0.011, 8)
    obj("fk_hoses", "cable_black", bm)
    # Carriage, load backrest, forks
    for z in (0.28, 0.54):
        box("fk_carriage_bar", (0, -0.71, z), (0.92, 0.05, 0.1), "painted_dark", 0.004, segs=1)
    bm = bmesh.new()
    for x in (-0.44, -0.26, -0.09, 0.09, 0.26, 0.44):
        add_box(bm, (x, -0.715, 0.92), (0.03, 0.03, 0.66))
    add_box(bm, (0, -0.715, 1.25), (0.92, 0.035, 0.035))
    obj("fk_backrest_grid", "painted_dark", bm)
    for x in (-0.28, 0.28):
        box("fk_fork_shank", (x, -0.755, 0.33), (0.1, 0.045, 0.62), "painted_dark", 0.004, segs=1)
        box("fk_fork_hook", (x, -0.735, 0.6), (0.1, 0.06, 0.04), "painted_dark", 0.004)
        prism("fk_fork_blade", [(-0.735, 0.0), (-1.46, 0.0), (-1.52, 0.012), (-1.52, 0.02), (-1.4, 0.045), (-0.735, 0.045)],
              ((x, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -0.05, 0.05, "painted_dark", 0.003, 1, angle=20)
    return finish("forklift", off, note="origin bottom centre; forks toward -Y")


def d_gantry(off):
    # Single-girder overhead crane, 8 m bridge along X; origin at the girder centroid.
    h, b, tw, tf = 0.6, 0.3, 0.012, 0.022
    prof = [(-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, -h / 2 + tf), (tw / 2, -h / 2 + tf), (tw / 2, h / 2 - tf), (b / 2, h / 2 - tf),
            (b / 2, h / 2), (-b / 2, h / 2), (-b / 2, h / 2 - tf), (-tw / 2, h / 2 - tf), (-tw / 2, -h / 2 + tf), (-b / 2, -h / 2 + tf)]
    prism("gb_girder", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -3.9, 3.9, "hazard", 0.003, 1, angle=40)
    bm = bmesh.new()
    for x in [-3.5 + i for i in range(8)]:
        for s in (-1, 1):
            add_box(bm, (x, s * (tw / 2 + 0.065), 0), (0.012, 0.13, h - 2 * tf))
    obj("gb_stiffeners", "hazard", bm)
    for sx in (-1, 1):
        box("gb_endtruck", (sx * 3.95, 0, -0.46), (0.32, 2.4, 0.32), "hazard", 0.01, segs=1, grooves=(("x", 0.03, 0.004, 0.003), ("-x", 0.03, 0.004, 0.003)))
        box("gb_end_plate", (sx * 3.92, 0, -0.15), (0.06, 0.4, 0.3), "hazard", 0.003)
        bolts("gb_end_bolts", [(sx * 3.885, y, z) for y in (-0.15, 0.15) for z in (-0.25, -0.05)], "steel", 0.014, 0.01, "X")
        for y in (-0.95, 0.95):
            cyl("gb_wheel", (sx * 3.95, y, -0.62), 0.15, 0.08, "painted_dark", "X", 24, bevel=0.004)
            cyl("gb_bumper", (sx * 3.95, y * 1.3, -0.46), 0.06, 0.1, "rubber", "Y", 16, bevel=0.01)
    box("gb_drive_box", (4.17, 0.95, -0.46), (0.14, 0.24, 0.22), "painted_dark", 0.008)
    cyl("gb_drive_motor", (4.17, 0.95, -0.24), 0.07, 0.2, "painted_grey", "Z", 16, bevel=0.004)
    # Trolley on the bottom flange, hoist, ropes, hook block
    tx = 1.0
    for s in (-1, 1):
        box("gb_trolley_side", (tx, s * 0.19, -0.33), (0.5, 0.02, 0.26), "painted_dark", 0.004, segs=1)
        for dx in (-0.16, 0.16):
            cyl("gb_trolley_wheel", (tx + dx, s * 0.1, -0.27), 0.04, 0.03, "steel", "Y", 12)
    cyl("gb_drum", (tx, 0, -0.62), 0.17, 0.66, "hazard", "X", 24, bevel=0.006)
    cyl("gb_hoist_motor", (tx + 0.48, 0, -0.62), 0.13, 0.3, "painted_grey", "X", 20, bevel=0.005)
    box("gb_gearbox", (tx - 0.42, 0, -0.62), (0.18, 0.3, 0.32), "painted_dark", 0.01)
    box("gb_hoist_frame", (tx, 0, -0.44), (0.7, 0.36, 0.06), "painted_dark", 0.003)
    bm = bmesh.new()
    for dx in (-0.04, 0.04):
        add_tube(bm, [(tx + dx, 0, -0.79), (tx + dx, 0, -1.93)], 0.008, 6)
    obj("gb_ropes", "steel", bm)
    box("gb_hookblock", (tx, 0, -2.05), (0.14, 0.26, 0.28), "hazard", 0.012, segs=2)
    for s in (-1, 1):
        hazard_band("gb_hb_hz", ((0, s * 0.131, 0), (1, 0, 0), (0, 0, 1), (0, s, 0)), tx - 0.065, tx + 0.065, -2.18, -1.92, sw=0.05)
    cyl("gb_hook_shank", (tx, 0, -2.24), 0.03, 0.1, "steel", "Z", 12)
    tube("gb_hook", fillet([(tx, 0, -2.29), (tx, 0, -2.42), (tx, 0.03, -2.5), (tx, 0.1, -2.5), (tx, 0.14, -2.43), (tx, 0.13, -2.37)], 0.05, 5), 0.026, "steel", 10)
    box("gb_latch", (tx, 0.075, -2.35), (0.012, 0.11, 0.008), "steel", 0.001, rot=(28, 0, 0))
    tube("gb_pendant_cable", [(tx + 0.3, -0.12, -0.5), (tx + 0.3, -0.12, -1.95)], 0.008, "cable_black", 6)
    box("gb_pendant", (tx + 0.3, -0.12, -2.08), (0.08, 0.07, 0.24), "painted_dark", 0.012, segs=2)
    for i in range(4):
        cyl("gb_pendant_btn", (tx + 0.3, -0.158, -2.0 - i * 0.045), 0.012, 0.008, "board_white" if i < 3 else "painted_red", "Y", 12)
    box("gb_festoon_rail", (0, 0.17, 0.32), (7.8, 0.04, 0.03), "galvanized", 0.002)
    bm = bmesh.new()
    for k in range(5):
        x0 = 2.2 + k * 0.2
        add_tube(bm, [(x0 + 0.1 - 0.1 * math.cos(math.pi * t / 8), 0.17, 0.3 - 0.35 * math.sin(math.pi * t / 8)) for t in range(9)], 0.008, 6)
    obj("gb_festoon", "cable_black", bm)
    for s in (-1, 1):
        box("gb_swl_plate", (0, s * (tw / 2 + 0.002), 0), (0.8, 0.004, 0.36), "board_white", 0.001)
        text_obj("gb_swl_txt", "SWL 5 t", "painted_dark", (0, s * (tw / 2 + 0.0045), 0), 0.17, rot=(90, 0, 0 if s < 0 else 180))
    return finish("gantry_beam_8", off, note="origin girder centroid; span X +-4.0; hook down to Z -2.5")


def d_cable_reel(off):
    # Wooden cable drum, axis along X, flange dia 1.0; origin bottom centre.
    zc = 0.5
    for sx in (-1, 1):
        cyl("cr_flange", (sx * 0.32, 0, zc), 0.5, 0.05, "wood_pallet", "X", 40, bevel=0.006, segs=1)
        bm = bmesh.new()
        for dz in (-0.3, -0.1, 0.1, 0.3):
            ln = 2 * math.sqrt(0.5 ** 2 - dz ** 2) - 0.02
            add_box(bm, (sx * 0.3455, 0, zc + dz), (0.002, ln, 0.006))
        obj("cr_plank_seams", "painted_dark", bm)
        ring("cr_hub", (sx * 0.347, 0, zc), 0.05, 0.11, 0.006, "steel", "X", 20)
        bolts("cr_tie_nuts", [(sx * 0.351, 0.3 * math.cos(2 * math.pi * k / 6), zc + 0.3 * math.sin(2 * math.pi * k / 6)) for k in range(6)], "steel", 0.016, 0.012, "X")
    cyl("cr_core", (0, 0, zc), 0.36, 0.59, "cable_black", "X", 32)
    bm = bmesh.new()
    for i in range(11):
        add_torus(bm, (-0.27 + i * 0.054, 0, zc), 0.372, 0.027, "X", 32, 6)
    obj("cr_turns", "cable_black", bm)
    bm = bmesh.new()
    for k in range(6):
        a = 2 * math.pi * k / 6
        add_cyl(bm, (0, 0.3 * math.cos(a), zc + 0.3 * math.sin(a)), 0.01, 0.7, "X", 8)
    obj("cr_tie_rods", "steel", bm)
    tube("cr_tail", fillet([(0.25, -0.12, zc + 0.385), (0.25, -0.45, zc + 0.3), (0.3, -0.62, 0.15), (0.35, -0.75, 0.032), (0.5, -1.4, 0.032)], 0.12), 0.03, "cable_black", 10)
    box("cr_label", (0.3455, 0.0, zc + 0.2), (0.002, 0.2, 0.12), "board_white", 0.0)
    return finish("cable_reel", off, note="origin bottom centre; axis X; tail runs to Y -1.4")


def d_wall_cable_run(off):
    # Heavy cable run along X on cantilever brackets; origin X centre, wall plane (Y=0), Z=0 at the lower arm top.
    for x in (-1.5, -0.5, 0.5, 1.5):
        box("wc_upright", (x, -0.021, 0.12), (0.042, 0.042, 0.5), "galvanized", 0.0015, recess=(("-y", 0.008, 0.03),))
        for z in (0.0, 0.25):
            box("wc_arm", (x, -0.2, z - 0.021), (0.042, 0.36, 0.042), "galvanized", 0.0015)
        tube("wc_brace", [(x, -0.045, -0.12), (x, -0.27, -0.045)], 0.01, "galvanized", 8)
        bolts("wc_anchor", [(x, -0.0435, -0.08), (x, -0.0435, 0.33)], "steel", 0.011, 0.008, "Y")
    bm = bmesh.new()
    cl = bmesh.new()
    for z0, ys, r in ((0.0, (-0.07, -0.15, -0.23, -0.31), 0.035), (0.25, (-0.08, -0.16, -0.24), 0.028)):
        for y in ys:
            pts = [(-2.0 + 0.2 * k, y, z0 + r - 0.02 * math.cos(math.pi * (-2.0 + 0.2 * k)) ** 2) for k in range(21)]
            add_tube(bm, pts, r, 8, caps=True)
            for x in (-1.5, -0.5, 0.5, 1.5):
                add_ring(cl, (x, y, z0 + r), r, r + 0.006, 0.03, "X", 10)
    obj("wc_cables", "cable_black", bm)
    obj("wc_cleats", "galvanized", cl)
    return finish("wall_cable_run_4", off, note="origin X centre, wall plane, lower arm top; X +-2.0")


def d_fire_hose_cabinet(off):
    # Wall fire-hose reel cabinet 0.7 x 0.25 x 0.8 with sign above; origin back-face centre (wall plane), front -Y.
    box("fh_back", (0, -0.01, 0), (0.7, 0.02, 0.8), "painted_red", 0.003, segs=1)
    for sx in (-1, 1):
        box("fh_side", (sx * 0.34, -0.12, 0), (0.02, 0.24, 0.8), "painted_red", 0.004, segs=2)
        box("fh_topbot", (0, -0.12, sx * 0.39), (0.7, 0.24, 0.02), "painted_red", 0.004, segs=2)
    door = box("fh_door", (0, -0.25, 0), (0.68, 0.02, 0.78), "painted_red", 0.004, segs=1)
    cut(door, lambda b: add_box(b, (0, -0.25, 0.02), (0.54, 0.1, 0.6)))
    box("fh_glass", (0, -0.248, 0.02), (0.55, 0.004, 0.61), "glass_lens", 0.0)
    box("fh_handle", (0.3, -0.268, 0.0), (0.02, 0.02, 0.14), "steel", 0.005)
    for z in (-0.3, 0.3):
        cyl("fh_hinge", (-0.343, -0.255, z), 0.008, 0.06, "steel", "Z", 12)
    cyl("fh_drum", (0, -0.1, 0.02), 0.12, 0.1, "galvanized", "Y", 24, bevel=0.004)
    for y in (-0.04, -0.16):
        cyl("fh_drum_flange", (0, y, 0.02), 0.3, 0.008, "painted_red", "Y", 32, bevel=0.002)
    pts = []
    for k in range(4 * 24 + 1):
        a = 2 * math.pi * k / 24
        r = 0.135 + 0.145 * k / 96
        pts.append((r * math.cos(a), -0.1 + 0.012 * math.sin(a * 0.5), 0.02 + r * math.sin(a)))
    tube("fh_hose", pts, 0.018, "painted_red", 8)
    cyl("fh_valve", (-0.25, -0.12, 0.3), 0.025, 0.08, "copper", "Y", 12)
    torus("fh_valve_wheel", (-0.25, -0.17, 0.3), 0.045, 0.006, "painted_red", "Y", 16, 6)
    tube("fh_nozzle", [(0.26, -0.12, -0.15), (0.26, -0.12, -0.32)], 0.016, "copper", 10)
    box("fh_sign", (0, -0.004, 0.55), (0.5, 0.008, 0.12), "board_white", 0.002)
    text_obj("fh_sign_txt", "FIRE HOSE", "painted_red", (0, -0.0088, 0.55), 0.07)
    return finish("fire_hose_cabinet", off, note="origin back-face centre (cabinet), wall plane; sign above to Z +0.61")


def d_bollard(off):
    # Steel pipe bollard dia 0.168 x 1.1 with domed cap; origin bottom centre.
    box("bo_base", (0, 0, 0.01), (0.3, 0.3, 0.02), "painted_dark", 0.003)
    bolts("bo_anchors", [(sx * 0.11, sy * 0.11, 0.028) for sx in (-1, 1) for sy in (-1, 1)], "steel", 0.016, 0.016, "Z")
    cyl("bo_pipe", (0, 0, 0.56), 0.084, 1.08, "hazard", "Z", 32)
    bm = bmesh.new()
    add_revolve(bm, [(0.084 * math.cos(math.pi / 2 * k / 6), 1.1 + 0.05 * math.sin(math.pi / 2 * k / 6)) for k in range(7)] + [(0.001, 1.15)], 32, closed=False, cap_ends=False)
    obj("bo_cap", "hazard", bm)
    for z in (0.62, 0.86):
        cyl("bo_band", (0, 0, z), 0.0848, 0.1, "painted_dark", "Z", 32)
    return finish("floor_bollard", off, note="origin bottom centre; height 1.15")


def d_wheel_chock(off):
    # Rubber wheel chock, concave tyre face toward -Y; origin bottom centre.
    prof = [(0.1, 0.0), (0.1, 0.17), (0.075, 0.2)]
    for k in range(1, 9):
        t = k / 9
        prof.append((0.075 - 0.225 * t, 0.2 * (1 - t) - 0.06 * math.sin(math.pi * t)))
    prof.append((-0.15, 0.0))
    prism("wk_body", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -0.11, 0.11, "rubber", 0.008, 2, angle=20)
    bm = bmesh.new()
    for k in range(2, 8):
        t = k / 9
        y, z = 0.075 - 0.225 * t, 0.2 * (1 - t) - 0.06 * math.sin(math.pi * t)
        add_box(bm, (0, y - 0.004, z + 0.004), (0.2, 0.012, 0.012), rot=(-40, 0, 0))
    obj("wk_ribs", "rubber", bm)
    tube("wk_handle", fillet([(-0.06, 0.1, 0.06), (-0.06, 0.15, 0.08), (0.06, 0.15, 0.08), (0.06, 0.1, 0.06)], 0.02), 0.008, "steel", 8)
    for sx in (-1, 1):
        box("wk_reflector", (sx * 0.111, 0.02, 0.07), (0.002, 0.1, 0.03), "hazard", 0.0)
    return finish("wheel_chock", off, note="origin bottom centre; tyre face -Y")


# ================================================================= CONTROL KIT
def keyboard(bm_base, bm_keys, pre, x, y, z):
    add_box(bm_base, (x, y, z), (0.44, 0.15, 0.016), rot=(3, 0, 0), pre=pre)
    for r_ in range(5):
        for c_ in range(14):
            add_box(bm_keys, (x - 0.195 + c_ * 0.03, y - 0.055 + r_ * 0.026, z + 0.012 + r_ * 0.0014), (0.024, 0.021, 0.008), rot=(3, 0, 0), pre=pre)


def c_control_desk(off):
    # Segmented 3-station operator desk ~3.5 (X) x 1.1 (Y) x 1.2 (Z); operators sit at -Y; origin floor, X centre, centre-station centre-line.
    a = 15.0
    segs = [(Matrix(), 3), (M((-0.6 - 0.6 * math.cos(math.radians(a)), -0.6 * math.sin(math.radians(a)), 0), (0, 0, a)), 2),
            (M((0.6 + 0.6 * math.cos(math.radians(a)), -0.6 * math.sin(math.radians(a)), 0), (0, 0, -a)), 2)]
    sn = 0
    kb_base, kb_keys = bmesh.new(), bmesh.new()
    ann_dark, ann_g, ann_a, ann_r = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    mt = 0.4 * math.tan(math.radians(a / 2))   # mitre offset so adjacent tops meet on the joint bisector
    tops = [[(-0.6 + mt, -0.4), (0.6 - mt, -0.4), (0.6 + mt, 0.4), (-0.6 - mt, 0.4)],
            [(-0.6, -0.4), (0.6 - mt, -0.4), (0.6 + mt, 0.4), (-0.6, 0.4)],
            [(-0.6 + mt, -0.4), (0.6, -0.4), (0.6, 0.4), (-0.6 - mt, 0.4)]]
    for si, (P, nmon) in enumerate(segs):
        tp = tops[si]
        fr = (tuple(P @ Vector((0, 0, 0))), tuple(P.to_3x3() @ Vector((1, 0, 0))), tuple(P.to_3x3() @ Vector((0, 1, 0))), (0, 0, 1))
        prism("cd_top", tp, fr, 0.72, 0.75, "painted_grey", 0.003, 1)
        x0, x1 = tp[0][0], tp[1][0]
        cyl("cd_nose", ((x0 + x1) / 2, -0.405, 0.73), 0.022, x1 - x0, "rubber", "X", 12, pre=P)
        box("cd_riser_cab", (0, 0.29, 0.36), (1.12, 0.2, 0.72), "painted_dark", 0.004, segs=1, pre=P, grooves=(("-y", 0.04, 0.004, 0.002),))
        for sx in (-1, 1):
            box("cd_leg", (sx * 0.55, -0.32, 0.36), (0.05, 0.05, 0.72), "painted_dark", 0.003, segs=1, pre=P)
        box("cd_footrail", (0, -0.32, 0.12), (1.05, 0.03, 0.03), "painted_dark", 0.002, pre=P)
        Pr = P @ M((0, 0.33, 0.84), (-25, 0, 0))
        box("cd_ann_riser", (0, 0, 0), (1.1, 0.14, 0.18), "painted_dark", 0.004, segs=1, pre=Pr)
        for r_ in range(2):
            for c_ in range(12):
                k = (si * 31 + r_ * 7 + c_ * 3) % 17
                tgt = ann_r if k == 0 else ann_a if k in (3, 9) else ann_g if k in (5, 12, 14) else ann_dark
                add_box(tgt, (-0.4675 + c_ * 0.085, -0.072, 0.03 - r_ * 0.05), (0.075, 0.004, 0.04), pre=Pr)
        # Monitors
        xs = [-0.51, 0.0, 0.51] if nmon == 3 else [-0.26, 0.26]
        for sx in (-1, 1):
            cyl("cd_pole", (sx * 0.45, 0.37, 0.92), 0.02, 0.36, "painted_dark", "Z", 12, pre=P)
        cyl("cd_mon_bar", (0, 0.37, 1.05), 0.015, 1.0 if nmon == 3 else 0.7, "painted_dark", "X", 10, pre=P)
        for i, x in enumerate(xs):
            sn += 1
            yaw = 0 if abs(x) < 0.01 else (-12 if x < 0 else 12) * (1 if nmon == 3 else 0.7)
            Pm = P @ M((x, 0.3 - (0.03 if abs(x) > 0.01 else 0), 1.07), (0, 0, -yaw))
            box("cd_mon_body", (0, 0, 0), (0.5, 0.035, 0.3), "painted_dark", 0.006, pre=Pm)
            box("cd_mon_back", (0, 0.03, -0.01), (0.22, 0.03, 0.16), "painted_dark", 0.01, segs=2, pre=Pm)
            box("screen_%d" % sn, (0, -0.0185, 0.008), (0.48, 0.002, 0.27), "screen", 0.0, pre=Pm)
            box("cd_mon_arm", (0, 0.055, -0.01), (0.03, 0.05, 0.03), "painted_dark", 0.002, pre=Pm)
        keyboard(kb_base, kb_keys, P, 0.0, -0.15, 0.758)
        box("cd_mouse", (0.32, -0.15, 0.762), (0.06, 0.1, 0.026), "painted_dark", 0.011, segs=3, pre=P)
        if si != 0:
            box("cd_phone", (-0.42 if si == 1 else 0.42, 0.05, 0.775), (0.2, 0.18, 0.05), "painted_dark", 0.01, segs=2, rot=(8, 0, 0), pre=P)
            box("cd_handset", (-0.42 if si == 1 else 0.42, 0.1, 0.81), (0.21, 0.05, 0.036), "painted_dark", 0.013, segs=2, rot=(8, 0, 0), pre=P)
        ring("cd_grommet", (0.0, 0.2, 0.751), 0.022, 0.032, 0.004, "galvanized", "Z", 16, pre=P)
    obj("cd_kb_base", "painted_dark", kb_base)
    obj("cd_kb_keys", "painted_grey", kb_keys)
    obj("cd_ann_dark", "painted_dark", ann_dark)
    obj("cd_ann_green", "led_green", ann_g)
    obj("cd_ann_amber", "led_amber", ann_a)
    obj("cd_ann_red", "led_red", ann_r)
    # PA gooseneck microphone, mug, clipboard
    cyl("cd_mic_base", (-0.33, 0.05, 0.762), 0.05, 0.024, "painted_dark", "Z", 20, bevel=0.004)
    tube("cd_mic_neck", fillet([(-0.33, 0.05, 0.77), (-0.33, 0.05, 0.9), (-0.3, -0.02, 1.0), (-0.27, -0.08, 0.99)], 0.06, 5), 0.006, "painted_dark", 8)
    cyl("cd_mic_head", (-0.265, -0.1, 0.985), 0.014, 0.05, "painted_dark", "Y", 12, rot=(-15, 0, 0))
    P1 = segs[1][0]
    cyl("cd_mug", (0.3, 0.1, 0.8), 0.04, 0.1, "board_white", "Z", 20, pre=P1)
    torus("cd_mug_handle", (0.345, 0.1, 0.8), 0.025, 0.006, "board_white", "Y", 12, 6, arc=math.pi, rot=(0, -90, 0), pre=P1)
    P2 = segs[2][0]
    box("cd_clipboard", (-0.35, 0.02, 0.754), (0.23, 0.32, 0.006), "painted_dark", 0.002, rot=(0, 0, 8), pre=P2)
    box("cd_paper", (-0.35, 0.01, 0.758), (0.21, 0.29, 0.002), "board_white", 0.0, rot=(0, 0, 8), pre=P2)
    return finish("control_desk_3", off, keep=tuple("screen_%d" % i for i in range(1, sn + 1)), note="origin floor, X centre, centre-station centre-line; operators at -Y")


def c_mimic_panel(off):
    # 6 x 2 m mimic (single-line diagram) board; origin back-face centre on the wall plane; front -Y.
    F = -0.0405
    box("mp_board", (0, -0.02, 0), (6.0, 0.04, 2.0), "painted_grey", 0.004, segs=1)
    for loc, size in (((0, -0.035, 0.975), (6.0, 0.07, 0.05)), ((0, -0.035, -0.975), (6.0, 0.07, 0.05)),
                      ((-2.975, -0.035, 0), (0.05, 0.07, 1.9)), ((2.975, -0.035, 0), (0.05, 0.07, 1.9))):
        box("mp_frame", loc, size, "painted_dark", 0.004, segs=1)
    bm = bmesh.new()
    for i in range(23):
        add_box(bm, (-2.75 + i * 0.25, F - 0.0004, 0), (0.002, 0.001, 1.9))
    for j in range(7):
        add_box(bm, (0, F - 0.0004, -0.75 + j * 0.25), (5.9, 0.001, 0.002))
    obj("mp_tile_joints", "painted_dark", bm)
    buses = {"copper": bmesh.new(), "painted_dark": bmesh.new()}
    brk, ledg, ledr, leda, rings, tags = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    yb = F - 0.003

    def line(m, x0, z0, x1, z1, w):
        add_box(buses[m], ((x0 + x1) / 2, yb, (z0 + z1) / 2), (abs(x1 - x0) + w, 0.006, abs(z1 - z0) + w))

    def breaker(x, z, closed=True):
        add_box(brk, (x, F - 0.007, z), (0.075, 0.014, 0.075))
        add_cyl(ledg if closed else ledr, (x, F - 0.0155, z), 0.016, 0.006, "Y", 16)
        add_box(tags, (x + 0.09, F - 0.002, z), (0.07, 0.003, 0.03))

    def disconnector(m, x, z):
        add_box(buses[m], (x + 0.02, yb, z), (0.012, 0.006, 0.09), rot=(0, 30, 0))

    def arrow(m, x, z):
        add_prism(buses[m], [(-0.035, 0.03), (0.035, 0.03), (0.0, -0.03)], ((x, 0, z), (1, 0, 0), (0, 0, 1), (0, -1, 0)), -F, -F + 0.006)

    line("copper", -2.4, 0.45, 2.4, 0.45, 0.035)
    for x in (-1.8, 0.0, 1.8):
        line("copper", x, 0.45, x, 0.66, 0.02)
        line("copper", x, 0.74, x, 0.8, 0.02)
        disconnector("copper", x, 0.70)
        arrow("copper", x, 0.83)
        breaker(x, 0.56, x != 1.8)
    line("painted_dark", -2.5, -0.32, -0.08, -0.32, 0.035)
    line("painted_dark", 0.08, -0.32, 2.5, -0.32, 0.035)
    breaker(0.0, -0.32, True)
    for x in (-1.0, 1.0):
        line("copper", x, 0.45, x, 0.21, 0.02)
        breaker(x, 0.33, True)
        add_torus(rings, (x, F - 0.004, 0.14), 0.07, 0.007, "Y", 24, 6)
        add_torus(rings, (x, F - 0.004, 0.04), 0.07, 0.007, "Y", 24, 6)
        line("painted_dark", x, -0.03, x, -0.32, 0.02)
        breaker(x, -0.17, x < 0)
    for i, x in enumerate((-2.25, -1.5, -0.6, 0.6, 1.5, 2.25)):
        line("painted_dark", x, -0.32, x, -0.8, 0.02)
        breaker(x, -0.48, i not in (2, 4))
        add_torus(rings, (x, F - 0.004, -0.63), 0.03, 0.005, "Y", 16, 6)
        arrow("painted_dark", x, -0.84)
    for i in range(8):
        add_cyl(leda if i % 3 else ledr, (1.0 + i * 0.12, F - 0.004, -0.92), 0.018, 0.008, "Y", 16)
    obj("mp_bus_hv", "copper", buses["copper"])
    obj("mp_bus_mv", "painted_dark", buses["painted_dark"])
    obj("mp_breakers", "painted_dark", brk, 0.002, 1)
    obj("mp_rings", "painted_dark", rings)
    obj("mp_tags", "galvanized", tags)
    obj("mp_lamps_green", "led_green", ledg)
    obj("mp_lamps_red", "led_red", ledr)
    obj("mp_lamps_amber", "led_amber", leda)
    # Analog meters (left/right columns)
    face, needle, ticks, bez = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        for j, z in enumerate((0.55, 0.15, -0.25)):
            x = sx * 2.75
            add_box(bez, (x, F - 0.015, z), (0.17, 0.03, 0.17))
            add_box(face, (x, F - 0.031, z), (0.14, 0.002, 0.14))
            for k in range(9):
                a = math.radians(-50 + 100 * k / 8)
                add_box(ticks, (x + 0.06 * math.sin(a), F - 0.0325, z - 0.03 + 0.06 * math.cos(a)), (0.002, 0.001, 0.012), rot=(0, math.degrees(a), 0))
            a = math.radians(-35 + 25 * (j + (sx > 0)))
            add_box(needle, (x + 0.03 * math.sin(a), F - 0.0335, z - 0.03 + 0.03 * math.cos(a)), (0.002, 0.001, 0.065), rot=(0, math.degrees(a), 0))
    obj("mp_meter_bezels", "painted_dark", bez, 0.004, 2)
    obj("mp_meter_faces", "board_white", face)
    obj("mp_meter_ticks", "painted_dark", ticks)
    obj("mp_meter_needles", "painted_red", needle)
    for x, s in ((-0.9, "RELAY NINE SUBSTATION"), (0.9, "132 kV / 33 kV")):
        box("mp_title", (x, F - 0.002, 0.88), (1.2, 0.004, 0.11), "board_white", 0.001)
        text_obj("mp_title_txt", s, "painted_dark", (x, F - 0.0048, 0.88), 0.06)
    text_obj("mp_lbl_hv", "132 kV BUS", "painted_dark", (-2.15, F - 0.0012, 0.53), 0.04)
    text_obj("mp_lbl_mv", "33 kV BUS", "painted_dark", (-2.2, F - 0.0012, -0.24), 0.04)
    return finish("mimic_panel", off, note="origin back-face centre on wall plane; X +-3.0, Z +-1.0; front -Y")


def gauge(face, ticks, needle, bez, pre, x, z, r, val):
    add_cyl(bez, (x, -0.008, z), r + 0.01, 0.016, "Y", 24, pre=pre)
    add_cyl(face, (x, -0.0165, z), r, 0.002, "Y", 24, pre=pre)
    for k in range(9):
        a = math.radians(-135 + 270 * k / 8)
        add_box(ticks, (x + r * 0.82 * math.sin(a), -0.018, z + r * 0.82 * math.cos(a)), (0.0018, 0.001, r * 0.18), rot=(0, math.degrees(a), 0), pre=pre)
    a = math.radians(-135 + 270 * val)
    add_box(needle, (x + r * 0.35 * math.sin(a), -0.019, z + r * 0.35 * math.cos(a)), (0.002, 0.001, r * 0.75), rot=(0, math.degrees(a), 0), pre=pre)


def c_instrument_rack(off):
    # Instrument rack 0.8 x 0.6 x 2.0: gauges, chart recorders, switches; origin bottom centre; front -Y.
    box("ir_body", (0, 0.03, 1.04), (0.8, 0.54, 1.92), "painted_grey", 0.006, segs=1, grooves=(("x", 0.04, 0.004, 0.002), ("-x", 0.04, 0.004, 0.002), ("z", 0.05, 0.004, 0.002)))
    box("ir_plinth", (0, 0.03, 0.04), (0.76, 0.5, 0.08), "painted_dark", 0.003)
    for sx in (-1, 1):
        torus("ir_lift_eye", (sx * 0.3, 0.03, 2.02), 0.025, 0.006, "steel", "Y", 12, 6)
    P = M((0, -0.24, 0))
    face, ticks, needle, bez = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    screws = []
    for z0, z1 in ((1.55, 1.95), (1.05, 1.5), (0.75, 1.0), (0.12, 0.7)):
        box("ir_panel", (0, -0.245, (z0 + z1) / 2), (0.76, 0.01, z1 - z0 - 0.006), "painted_grey", 0.002, segs=1)
        screws += [(sx * 0.36, -0.2515, z) for sx in (-1, 1) for z in (z0 + 0.02, z1 - 0.02)]
    for r_ in range(2):
        for c_ in range(3):
            gauge(face, ticks, needle, bez, Matrix.Translation((0, -0.25, 0)), -0.24 + c_ * 0.24, 1.85 - r_ * 0.2, 0.06, 0.2 + 0.25 * ((r_ * 3 + c_) % 3))
    obj("ir_gauge_bezels", "painted_dark", bez)
    obj("ir_gauge_faces", "board_white", face)
    obj("ir_gauge_ticks", "painted_dark", ticks)
    obj("ir_gauge_needles", "painted_red", needle)
    trace = bmesh.new()
    for sx in (-1, 1):
        x = sx * 0.19
        box("ir_rec_body", (x, -0.265, 1.28), (0.34, 0.03, 0.38), "painted_dark", 0.006)
        box("ir_rec_paper", (x, -0.281, 1.3), (0.28, 0.002, 0.24), "board_white", 0.0)
        box("ir_rec_glass", (x, -0.284, 1.3), (0.3, 0.003, 0.26), "glass_lens", 0.0)
        for g in range(3):
            pts = [(x - 0.13 + 0.26 * k / 20, -0.2825, 1.25 + g * 0.04 + 0.025 * math.sin(k * 1.05 + g * 2 + sx) * math.sin(k * 0.2 + g)) for k in range(21)]
            for p0, p1 in zip(pts[:-1], pts[1:]):
                mid = ((p0[0] + p1[0]) / 2, p0[1], (p0[2] + p1[2]) / 2)
                ln = math.hypot(p1[0] - p0[0], p1[2] - p0[2])
                ang = math.degrees(math.atan2(p1[2] - p0[2], p1[0] - p0[0]))
                add_box(trace, mid, (ln + 0.001, 0.0005, 0.0015), rot=(0, -ang, 0))
        box("ir_rec_lcd", (x, -0.281, 1.13), (0.1, 0.002, 0.03), "screen", 0.0)
        for i in range(3):
            cyl("ir_rec_btn", (x + 0.08 + i * 0.025, -0.282, 1.13), 0.007, 0.006, "painted_grey", "Y", 10)
    obj("ir_traces", "painted_red", trace)
    for i in range(6):
        x = -0.3 + i * 0.12
        cyl("ir_sel_skirt", (x, -0.2515, 0.9), 0.024, 0.003, "galvanized", "Y", 20)
        cyl("ir_sel_knob", (x, -0.262, 0.9), 0.017, 0.02, "painted_dark", "Y", 16, bevel=0.002)
        box("ir_sel_pointer", (x, -0.273, 0.9), (0.005, 0.004, 0.028), "painted_dark", 0.0, rot=(0, (i % 3 - 1) * 40, 0))
        cyl("ir_lamp", (x, -0.256, 0.82), 0.011, 0.012, ("led_green", "led_amber", "led_green", "led_red", "led_green", "led_amber")[i], "Y", 16)
        box("ir_tag", (x, -0.2515, 0.965), (0.08, 0.003, 0.02), "galvanized", 0.0)
    bm = bmesh.new()
    for i in range(10):
        add_box(bm, (0, -0.2515, 0.25 + i * 0.04), (0.5, 0.003, 0.012))
    obj("ir_louvres", "painted_dark", bm)
    bolts("ir_screws", screws, "steel", 0.006, 0.003, "Y", dome=True)
    return finish("instrument_rack", off, note="origin bottom centre; front -Y")


def c_relay_cabinet(off):
    # Protection relay cabinet 1.2 x 0.6 x 2.2 with glass doors; origin bottom centre; front -Y.
    G = "painted_grey"
    box("rc_back", (0, 0.29, 1.1), (1.2, 0.02, 2.2), G, 0.004, segs=1)
    for sx in (-1, 1):
        box("rc_side", (sx * 0.59, 0, 1.1), (0.02, 0.6, 2.2), G, 0.004, segs=1, grooves=(("x" if sx > 0 else "-x", 0.04, 0.004, 0.002),))
    box("rc_top", (0, 0, 2.19), (1.2, 0.6, 0.02), G, 0.004, segs=1)
    box("rc_plinth", (0, 0, 0.05), (1.16, 0.56, 0.1), "painted_dark", 0.003)
    box("rc_floor", (0, 0, 0.11), (1.16, 0.56, 0.02), G, 0.0)
    box("rc_plate", (0, 0.275, 1.15), (1.1, 0.01, 1.95), "galvanized", 0.0)
    for sx in (-1, 1):
        d = box("rc_door", (sx * 0.29, -0.29, 1.14), (0.58, 0.02, 2.06), G, 0.004, segs=1)
        cut(d, lambda b, sx=sx: add_box(b, (sx * 0.29, -0.29, 1.16), (0.46, 0.1, 1.84)))
        box("rc_glass", (sx * 0.29, -0.288, 1.16), (0.47, 0.004, 1.85), "glass_lens", 0.0)
        box("rc_handle", (sx * 0.035, -0.31, 1.14), (0.025, 0.02, 0.18), "painted_dark", 0.006, segs=2)
        cyl("rc_lock", (sx * 0.035, -0.305, 1.27), 0.008, 0.01, "steel", "Y", 12)
        for z in (0.35, 1.14, 1.93):
            cyl("rc_hinge", (sx * 0.585, -0.295, z), 0.008, 0.07, "steel", "Z", 12)
        box("rc_door_tag", (sx * 0.29, -0.3015, 2.12), (0.16, 0.003, 0.04), "board_white", 0.0)
        text_obj("rc_tag_txt", "=RP1" if sx < 0 else "=RP2", "painted_dark", (sx * 0.29, -0.3035, 2.12), 0.025)
    # Interior: DIN rails, relays, IEDs, terminal blocks, trunking, wiring
    rails, body_d, body_g, leds_g, leds_r, scr = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    duct = bmesh.new()
    wires = bmesh.new()
    rowz = (1.85, 1.55, 1.25, 0.95, 0.65)
    for ri, z in enumerate(rowz):
        add_box(rails, (0, 0.265, z), (1.05, 0.008, 0.035))
        add_box(duct, (0, 0.24, z - 0.15), (1.05, 0.06, 0.06))
        if ri == 0:
            for x in (-0.33, 0.0, 0.33):
                add_box(body_d, (x, 0.2, z), (0.2, 0.12, 0.22))
                add_box(scr, (x, 0.139, z + 0.04), (0.12, 0.002, 0.06))
                for i in range(4):
                    add_cyl(leds_g if i else leds_r, (x - 0.07, 0.139, z - 0.03 - i * 0.02), 0.004, 0.003, "Y", 8)
                for i in range(5):
                    add_box(body_g, (x - 0.02 + i * 0.025, 0.138, z - 0.07), (0.016, 0.004, 0.012))
        elif ri == 3:
            for i in range(80):
                add_box(body_g, (-0.5 + i * 0.0126, 0.235, z), (0.0105, 0.05, 0.055))
        else:
            x = -0.5
            k = 0
            while x < 0.48:
                w = (0.0225, 0.045, 0.0225, 0.0675)[k % 4]
                add_box(body_d if k % 3 else body_g, (x + w / 2, 0.22, z), (w - 0.002, 0.08, 0.09))
                add_cyl(leds_r if (k + ri) % 7 == 0 else leds_g, (x + w / 2, 0.179, z + 0.03), 0.0035, 0.003, "Y", 8)
                if k % 2 == 0:
                    add_tube(wires, [(x + w / 2, 0.21, z - 0.045), (x + w / 2, 0.215, z - 0.09), (x + w / 2 + 0.01, 0.23, z - 0.12)], 0.0025, 5, caps=True)
                x += w
                k += 1
    for sx in (-1, 1):
        add_box(duct, (sx * 0.52, 0.24, 1.25), (0.06, 0.06, 1.6))
    obj("rc_rails", "galvanized", rails)
    obj("rc_relays_dark", "painted_dark", body_d)
    obj("rc_relays_grey", "painted_grey", body_g)
    obj("rc_relay_leds_green", "led_green", leds_g)
    obj("rc_relay_leds_red", "led_red", leds_r)
    obj("rc_ied_screens", "screen", scr)
    obj("rc_trunking", "painted_grey", duct, 0.002, 1)
    obj("rc_wires", "cable_black", wires)
    box("rc_light", (0, 0.2, 2.15), (0.8, 0.03, 0.02), "lamp_cool", 0.0)
    for sx in (-1, 1):
        box("rc_filter", (sx * 0.29, -0.3015, 0.2), (0.2, 0.003, 0.15), "painted_dark", 0.0)
    return finish("relay_cabinet", off, note="origin bottom centre; front (glass doors) -Y")


def c_ceiling_tile(name, light, off):
    # 1.2 x 1.2 lay-in ceiling module with half T-bars on each edge; origin at the grid's visible bottom plane, tile centre.
    for sx in (-1, 1):
        box("cg_flange_x", (sx * 0.594, 0, 0.0015), (0.012, 1.2, 0.003), "painted_grey", 0.0)
        box("cg_web_x", (sx * 0.599, 0, 0.018), (0.002, 1.2, 0.03), "painted_grey", 0.0)
        box("cg_flange_y", (0, sx * 0.594, 0.0015), (1.176, 0.012, 0.003), "painted_grey", 0.0)
        box("cg_web_y", (0, sx * 0.599, 0.018), (1.196, 0.002, 0.03), "painted_grey", 0.0)
    if not light:
        box("cg_tile", (0, 0, 0.0125), (1.186, 1.186, 0.019), "board_white", 0.002, segs=1, recess=(("-z", 0.02, -0.006),))
        keep = ()
    else:
        for sy in (-1, 1):
            box("cg_tile_strip", (0, sy * 0.444, 0.0125), (1.186, 0.298, 0.019), "board_white", 0.002, segs=1)
        box("cg_panel_frame", (0, 0, 0.012), (1.186, 0.59, 0.02), "painted_grey", 0.002, segs=1)
        box("light_panel", (0, 0, 0.0005), (1.15, 0.555, 0.004), "lamp_cool", 0.0)
        box("cg_driver", (0.3, 0, 0.04), (0.25, 0.12, 0.035), "galvanized", 0.003)
        keep = ("light_panel",)
    return finish(name, off, keep=keep, note="origin grid bottom plane, tile centre; tiles 1.2 m")


def c_trench_cover(off):
    # Cable trench cover 0.6 (X) x 2.0 (Y), two checker plates in an angle frame; origin top centre at floor level.
    for sy in (-1, 1):
        p = box("tc_plate", (0, sy * 0.4985, -0.004), (0.56, 0.993, 0.008), "diamond_plate", 0.002, segs=1)
        cut(p, lambda b, sy=sy: [add_box(b, (x, sy * (0.4985 + 0.38), -0.004), (0.08, 0.025, 0.05)) for x in (-0.15, 0.15)])
        bolts("tc_screws", [(sx * 0.25, sy * 0.4985 + dy, 0.0005) for sx in (-1, 1) for dy in (-0.43, 0.43)], "steel", 0.008, 0.002, "Z", dome=True)
    for sx in (-1, 1):
        box("tc_frame_x", (sx * 0.3, 0, -0.025), (0.04, 2.04, 0.05), "galvanized", 0.002)
        box("tc_frame_y", (0, sx * 1.0, -0.025), (0.56, 0.04, 0.05), "galvanized", 0.002)
    box("tc_void", (0, 0, -0.3), (0.56, 1.96, 0.02), "painted_dark", 0.0)
    return finish("cable_trench_cover", off, note="origin top centre at floor level; trench void to Z -0.31")


def c_office_chair(off):
    # Task chair; seat faces -Y; origin bottom centre.
    cyl("oc_hub", (0, 0, 0.1), 0.05, 0.06, "painted_dark", "Z", 16, bevel=0.006)
    for k in range(5):
        a = math.radians(90 + 72 * k)
        ca, sa = math.cos(a), math.sin(a)
        box("oc_leg", (0.17 * ca, 0.17 * sa, 0.085), (0.27, 0.045, 0.035), "painted_dark", 0.008, segs=2, rot=(0, 6, math.degrees(a)))
        box("oc_caster_fork", (0.31 * ca, 0.31 * sa, 0.055), (0.03, 0.03, 0.04), "painted_dark", 0.004)
        for s in (-1, 1):
            cyl("oc_caster", (0.31 * ca + s * 0.014 * -sa, 0.31 * sa + s * 0.014 * ca, 0.026), 0.025, 0.012, "rubber", "X", 16, rot=(0, 0, math.degrees(a)))
    cyl("oc_shroud", (0, 0, 0.21), 0.035, 0.16, "painted_dark", "Z", 16)
    cyl("oc_gaslift", (0, 0, 0.33), 0.022, 0.12, "steel", "Z", 16)
    box("oc_mech", (0, 0.0, 0.415), (0.22, 0.24, 0.05), "painted_dark", 0.008)
    box("oc_lever", (0.15, -0.05, 0.41), (0.1, 0.015, 0.012), "painted_dark", 0.004)
    box("oc_seat", (0, -0.02, 0.475), (0.48, 0.48, 0.08), "rubber", 0.035, segs=3)
    box("oc_spine", (0, 0.24, 0.57), (0.06, 0.03, 0.3), "painted_dark", 0.01, rot=(-8, 0, 0))
    box("oc_back", (0, 0.275, 0.85), (0.44, 0.07, 0.5), "rubber", 0.03, segs=3, rot=(-8, 0, 0))
    for sx in (-1, 1):
        box("oc_arm_post", (sx * 0.26, 0.02, 0.58), (0.03, 0.06, 0.2), "painted_dark", 0.006)
        box("oc_arm_pad", (sx * 0.26, 0.0, 0.69), (0.07, 0.25, 0.03), "rubber", 0.012, segs=2)
    return finish("office_chair", off, note="origin bottom centre; seat front -Y")


def c_wall_clock(off):
    # 0.33 m wall clock (10:08); origin back-face centre on wall plane; front -Y.
    ring("wk_rim", (0, -0.025, 0), 0.15, 0.165, 0.05, "painted_dark", "Y", 48)
    cyl("wk_back", (0, -0.005, 0), 0.15, 0.01, "painted_dark", "Y", 48)
    cyl("wk_face", (0, -0.03, 0), 0.15, 0.002, "board_white", "Y", 48)
    bm = bmesh.new()
    for k in range(60):
        a = 2 * math.pi * k / 60
        big = k % 5 == 0
        add_box(bm, (0.132 * math.sin(a), -0.0315, 0.132 * math.cos(a)), (0.005 if big else 0.0018, 0.001, 0.02 if big else 0.008), rot=(0, math.degrees(a), 0))
    for a, ln, w in ((math.radians(304), 0.075, 0.008), (math.radians(48), 0.115, 0.006)):
        add_box(bm, (ln / 2 * 0.8 * math.sin(a), -0.033, ln / 2 * 0.8 * math.cos(a)), (w, 0.0015, ln), rot=(0, math.degrees(a), 0))
    add_cyl(bm, (0, -0.0345, 0), 0.008, 0.003, "Y", 16)
    obj("wk_marks", "painted_dark", bm)
    a = math.radians(200)
    box("wk_second", (0.05 * math.sin(a), -0.0355, 0.05 * math.cos(a)), (0.0018, 0.001, 0.14), "painted_red", 0.0, rot=(0, math.degrees(a), 0))
    cyl("wk_glass", (0, -0.046, 0), 0.151, 0.003, "glass_lens", "Y", 48)
    text_obj("wk_brand", "RELAY NINE", "painted_dark", (0, -0.0312, 0.055), 0.012, extrude=0.0002)
    return finish("wall_clock", off, note="origin back-face centre on wall plane; dia 0.33")


def c_whiteboard(off):
    # 1.8 x 1.2 whiteboard with tray, markers, eraser, notes; origin back-face centre on the wall plane; front -Y.
    box("wb_board", (0, -0.008, 0), (1.78, 0.012, 1.18), "board_white", 0.001)
    for loc, size in (((0, -0.012, 0.6), (1.82, 0.022, 0.025)), ((0, -0.012, -0.6), (1.82, 0.022, 0.025)),
                      ((-0.9, -0.012, 0), (0.025, 0.022, 1.18)), ((0.9, -0.012, 0), (0.025, 0.022, 1.18))):
        box("wb_frame", loc, size, "galvanized", 0.006, segs=2)
    for sx in (-1, 1):
        for sz in (-1, 1):
            box("wb_corner", (sx * 0.905, -0.0125, sz * 0.605), (0.04, 0.025, 0.04), "painted_dark", 0.01, segs=2)
    prof = [(0, -0.63), (-0.07, -0.63), (-0.07, -0.605), (-0.064, -0.605), (-0.064, -0.624), (-0.006, -0.624), (-0.006, -0.612), (0, -0.612)]
    prism("wb_tray", prof, ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), -0.4, 0.4, "galvanized", 0.0)
    for i, (x, cap) in enumerate(((-0.25, "painted_dark"), (-0.1, "painted_red"), (0.02, "painted_dark"), (0.14, "cable_black"))):
        cyl("wb_marker", (x, -0.035 - (i % 2) * 0.015, -0.614), 0.009, 0.11, "board_white", "X", 12, rot=(0, 0, (i - 1.5) * 6))
        cyl("wb_cap", (x + 0.07, -0.035 - (i % 2) * 0.015, -0.614), 0.0095, 0.03, cap, "X", 12, rot=(0, 0, (i - 1.5) * 6))
    box("wb_eraser", (0.3, -0.035, -0.606), (0.14, 0.05, 0.025), "painted_dark", 0.006, segs=2)
    box("wb_felt", (0.3, -0.035, -0.62), (0.135, 0.045, 0.006), "rubber", 0.0)
    # Notes: sketch of a feeder, scribbles, block-capital marker text
    sk_d, sk_r = bmesh.new(), bmesh.new()
    S = -0.0142
    add_tube(sk_d, [(-0.75, S, 0.35), (-0.15, S, 0.35)], 0.0018, 5)
    for x in (-0.6, -0.4, -0.25):
        add_tube(sk_d, [(x, S, 0.35), (x, S, 0.1)], 0.0018, 5)
        add_tube(sk_d, [(x - 0.025, S, 0.22), (x + 0.025, S, 0.22), (x + 0.025, S, 0.27), (x - 0.025, S, 0.27), (x - 0.025, S, 0.22)], 0.0018, 5)
    add_tube(sk_r, [(-0.4 + 0.07 * math.cos(2 * math.pi * k / 20), S - 0.0003, 0.245 + 0.06 * math.sin(2 * math.pi * k / 20)) for k in range(22)], 0.002, 5)
    for j in range(5):
        y0 = -0.05 - j * 0.07
        pts = [(-0.75 + 0.018 * k, S, y0 + 0.008 * math.sin(k * 2.5 + j) + 0.004 * math.sin(k * 6.1)) for k in range(int(20 + 8 * ((j * 7) % 4)))]
        add_tube(sk_d, pts, 0.0014, 4)
    obj("wb_sketch", "painted_dark", sk_d)
    obj("wb_circle", "painted_red", sk_r)
    text_obj("wb_txt1", "SYNC FAULT 22:07", "painted_dark", (0.35, -0.0146, 0.38), 0.06, extrude=0.0002)
    text_obj("wb_txt2", "DO NOT RESET 9-B", "painted_red", (0.35, -0.0146, 0.28), 0.06, extrude=0.0002)
    text_obj("wb_txt3", "LIFT 2 - OUT OF SERVICE", "painted_dark", (0.35, -0.0146, 0.18), 0.045, extrude=0.0002)
    box("wb_sheet", (0.62, -0.0145, -0.2), (0.21, 0.001, 0.297), "cardboard", 0.0, rot=(0, 4, 0))
    for x, z in ((0.55, -0.07), (0.69, -0.06)):
        cyl("wb_magnet", (x, -0.019, z), 0.012, 0.008, "painted_red", "Y", 16, bevel=0.002)
    return finish("whiteboard", off, note="origin back-face centre on wall plane; 1.8 x 1.2")


def c_estop(off):
    # Emergency-stop pedestal ~1.17 high; button faces -Y; origin bottom centre.
    box("es_base", (0, 0, 0.01), (0.3, 0.3, 0.02), "painted_dark", 0.003)
    bolts("es_anchors", [(sx * 0.11, sy * 0.11, 0.028) for sx in (-1, 1) for sy in (-1, 1)], "steel", 0.014, 0.014, "Z")
    box("es_post", (0, 0, 0.5), (0.08, 0.08, 0.96), "hazard", 0.004, segs=1)
    for z in (0.3, 0.5, 0.7):
        box("es_band", (0, 0, z), (0.0815, 0.0815, 0.06), "painted_dark", 0.0)
    Pe = M((0, 0, 1.05), (-20, 0, 0))
    box("es_box", (0, 0, 0), (0.16, 0.12, 0.16), "hazard", 0.01, segs=2, pre=Pe)
    ring("es_guard", (0, -0.075, 0.015), 0.042, 0.052, 0.03, "painted_dark", "Y", 24, pre=Pe)
    cyl("es_collar", (0, -0.066, 0.015), 0.03, 0.012, "painted_dark", "Y", 20, pre=Pe)
    bm = bmesh.new()
    add_revolve(bm, [(0.001, 0.098), (0.014, 0.0975), (0.026, 0.094), (0.032, 0.086), (0.033, 0.078), (0.03, 0.072), (0.02, 0.072)], 24, closed=False, cap_ends=True, axis="Y", pre=Pe @ Matrix.Translation((0, 0, 0.015)))
    obj("es_mushroom", "painted_red", bm)
    box("es_label", (0, -0.0615, -0.058), (0.13, 0.002, 0.03), "board_white", 0.0, pre=Pe)
    text_obj("es_label_txt", "EMERGENCY STOP", "painted_dark", tuple(Pe @ Vector((0, -0.0632, -0.058))), 0.0115, rot=(70, 0, 0), extrude=0.0002)
    cyl("es_conduit", (0.0, 0.06, 0.06), 0.012, 0.1, "galvanized", "Z", 12)
    return finish("emergency_stop", off, note="origin bottom centre; button faces -Y")


# ================================================================= build
def write_sources(out_dir):
    font = FONT_INFO.get("font", ("builtin", "<builtin>"))
    L = ["# M3 environment sources", "",
         "Everything in `staging/env_m3/` is first-party and project-owned, generated by `tools/m2/env_kit_m3.py`",
         "(which reuses the helper library in `tools/m2/env_kit.py`). No files were downloaded for M3.", "",
         "| Output | How it was made | License |", "| --- | --- | --- |",
         "| `dock_kit.glb`, `control_kit.glb` | Procedural hard-surface modelling in Blender 5.3 (bmesh primitives, booleans, bevel + weighted normals, Smart UV Project) | Project-owned |",
         "| Painted lettering on the container, signs, mimic board, whiteboard, clock, e-stop | Blender text objects converted to flat meshes, using Blender's built-in text font `%s` (`%s`), distributed with Blender under a permissive font licence | Project-owned geometry |" % font,
         "| `decals/*.png` | Procedural numpy generation inside Blender (value noise, strokes, distance fields); stencil glyphs rasterised from the same built-in font. No third-party images | Project-owned; free to release as CC0 |", "",
         "## Decals (1024 x 1024 PNG, straight alpha)", "",
         "oil_stain_1, oil_stain_2, grime_streak_1 (grey), grime_streak_2 (rust), floor_scuffs_1, cracks_1 + cracks_1_normal (OpenGL normal, Non-Color),",
         "scorch_1, puddle_1 + puddle_1_rough (greyscale roughness hint, Non-Color), tire_marks_1, footprints_dust_1,",
         "stencil_no_step, stencil_high_voltage, stencil_9b, stencil_lift_2 (white stencil lettering with bridges, on transparent).", "",
         "## Material names added in M3", "",
         "`wood_pallet` (requested), plus `cardboard`, `diamond_plate`, `board_white`, `painted_red`. Until the game remaps them,",
         "Godot falls back to the glTF preview material embedded in the .glb.", ""]
    with open(os.path.join(out_dir, "SOURCES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    K.reset()
    d_freight_lift((0, 0, 0))
    d_rollup_door((7.5, 0, 0))
    d_dock_leveler((12.0, 0, 0))
    d_container((15.5, 0, 0))
    d_pallet((18.6, 0, 0))
    d_pallet_stack((20.1, 0, 0))
    d_pallet_boxes((21.6, 0, 0))
    d_forklift((24.0, 0, 0))
    d_gantry((30.0, 0, 0))
    d_cable_reel((35.5, 0, 0))
    d_wall_cable_run((39.0, 0, 0))
    d_fire_hose_cabinet((42.0, 0, 0))
    d_bollard((43.2, 0, 0))
    d_wheel_chock((44.0, 0, 0))
    K.export(os.path.join(out_dir, "dock_kit.glb"))
    K.reset()
    c_control_desk((0, 0, 0))
    c_mimic_panel((6.0, 0, 0))
    c_instrument_rack((10.5, 0, 0))
    c_relay_cabinet((12.0, 0, 0))
    c_ceiling_tile("ceiling_grid_tile", False, (14.0, 0, 0))
    c_ceiling_tile("ceiling_grid_tile_light", True, (15.5, 0, 0))
    c_trench_cover((17.0, 0, 0))
    c_office_chair((18.5, 0, 0))
    c_wall_clock((19.5, 0, 0))
    c_whiteboard((21.5, 0, 0))
    c_estop((23.5, 0, 0))
    K.export(os.path.join(out_dir, "control_kit.glb"))
    with open(os.path.join(out_dir, "kit_stats_m3.json"), "w", encoding="utf-8") as f:
        json.dump(K.STATS, f, indent=1)
    write_sources(out_dir)


# ================================================================= DECALS (procedural, numpy inside Blender)
def decals(out_dir):
    import numpy as np
    N = 1024
    ddir = os.path.join(out_dir, "decals")
    os.makedirs(ddir, exist_ok=True)
    YY, XX = np.mgrid[0:N, 0:N].astype(np.float32)

    def smooth(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0, 1)
        return t * t * (3 - 2 * t)

    def vnoise(h, w, cy, cx, r):
        g = r.random((cy + 2, cx + 2)).astype(np.float32)
        yy = np.arange(h) * cy / h
        xx = np.arange(w) * cx / w
        iy, ix = yy.astype(int), xx.astype(int)
        fy, fx = yy - iy, xx - ix
        fy, fx = (fy * fy * (3 - 2 * fy))[:, None], (fx * fx * (3 - 2 * fx))[None, :]
        g00, g01 = g[np.ix_(iy, ix)], g[np.ix_(iy, ix + 1)]
        g10, g11 = g[np.ix_(iy + 1, ix)], g[np.ix_(iy + 1, ix + 1)]
        return (g00 * (1 - fx) + g01 * fx) * (1 - fy) + (g10 * (1 - fx) + g11 * fx) * fy

    def fbm(r, cells=4, octaves=5, cy=None, gain=0.5):
        s, a, tot = 0, 1.0, 0
        for o in range(octaves):
            c = cells * 2 ** o
            s = s + a * vnoise(N, N, (cy or cells) * 2 ** o, c, r)
            tot += a
            a *= gain
        return s / tot

    def blur(a, rad):
        rad = int(rad)
        if rad < 1:
            return a
        for _ in range(3):
            for ax in (0, 1):
                pad = [(rad + 1, rad) if i == ax else (0, 0) for i in range(2)]
                c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
                n = a.shape[ax]
                a = (np.take(c, np.arange(2 * rad + 1, n + 2 * rad + 1), axis=ax) - np.take(c, np.arange(0, n), axis=ax)) / (2 * rad + 1)
        return a

    def seg(mask, p0, p1, r, val=1.0, soft=1.0):
        x0 = int(max(0, min(p0[0], p1[0]) - r - 2))
        x1 = int(min(N, max(p0[0], p1[0]) + r + 3))
        y0 = int(max(0, min(p0[1], p1[1]) - r - 2))
        y1 = int(min(N, max(p0[1], p1[1]) + r + 3))
        if x1 <= x0 or y1 <= y0:
            return
        X, Y = XX[y0:y1, x0:x1], YY[y0:y1, x0:x1]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((X - p0[0]) * dx + (Y - p0[1]) * dy) / L2, 0, 1)
        d = np.hypot(X - (p0[0] + t * dx), Y - (p0[1] + t * dy))
        cov = np.clip((r - d) / soft + 0.5, 0, 1) * val
        np.maximum(mask[y0:y1, x0:x1], cov, out=mask[y0:y1, x0:x1])

    def ellipse(mask, cx, cy, rx, ry, ang=0.0, val=1.0, soft=1.2):
        R_ = max(rx, ry) + 3
        x0, x1 = int(max(0, cx - R_)), int(min(N, cx + R_ + 1))
        y0, y1 = int(max(0, cy - R_)), int(min(N, cy + R_ + 1))
        if x1 <= x0 or y1 <= y0:
            return
        X, Y = XX[y0:y1, x0:x1] - cx, YY[y0:y1, x0:x1] - cy
        c, s = math.cos(ang), math.sin(ang)
        u, v = X * c + Y * s, -X * s + Y * c
        d = np.sqrt((u / rx) ** 2 + (v / ry) ** 2)
        cov = np.clip((1 - d) * min(rx, ry) / soft + 0.5, 0, 1) * val
        np.maximum(mask[y0:y1, x0:x1], cov, out=mask[y0:y1, x0:x1])

    def vignette(margin=0.08):
        e = np.minimum(np.minimum(XX, N - 1 - XX), np.minimum(YY, N - 1 - YY)) / N
        return smooth(0.0, margin, e)

    def save(name, rgb, a, noncolor=False):
        rgba = np.zeros((N, N, 4), dtype=np.float32)
        rgba[..., :3] = np.clip(rgb, 0, 1) if rgb.ndim == 3 else np.clip(rgb, 0, 1)[..., None]
        rgba[..., 3] = np.clip(a, 0, 1)
        img = bpy.data.images.new(name, N, N, alpha=True)
        if noncolor:
            img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(np.flipud(rgba).ravel())
        p = os.path.join(ddir, name + ".png")
        img.filepath_raw = p
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
        OUT.append((name, rgba))
        print("decal", p)

    def col(r, g, b):
        return np.ones((N, N, 3), dtype=np.float32) * np.array([r, g, b], dtype=np.float32)

    OUT = []

    def blob(seed, R_, elong=1.0, rough=0.5):
        r = np.random.default_rng(seed)
        cx, cy = N / 2 + r.uniform(-30, 30), N / 2 + r.uniform(-30, 30)
        ang = r.uniform(0, math.pi)
        X, Y = XX - cx, YY - cy
        u = X * math.cos(ang) + Y * math.sin(ang)
        v = (-X * math.sin(ang) + Y * math.cos(ang)) * elong
        n1 = fbm(r, 3, 5)
        dd = np.hypot(u, v) / (1 + rough * (n1 - 0.5) * 2)
        m = 1 - smooth(R_ * 0.96, R_ * 1.0, dd)
        drops = np.zeros((N, N), np.float32)
        for k in range(int(r.integers(6, 14))):
            a = r.uniform(0, 2 * math.pi)
            d = R_ * r.uniform(0.95, 1.35)
            rr = r.uniform(5, 26)
            ellipse(drops, cx + d * math.cos(a), cy + d * math.sin(a) / elong, rr, rr * r.uniform(0.6, 1.0), r.uniform(0, 3))
        ring_ = np.exp(-(((R_ - dd) / R_) / 0.035) ** 2) * m
        return np.maximum(m, drops), ring_, r

    # oil stains
    for i, (seed, R_, el) in enumerate(((11, 300, 1.0), (23, 260, 1.7)), 1):
        m, ring_, r = blob(seed, R_, el, 0.55)
        n2, n3 = fbm(r, 6, 4), fbm(r, 12, 3)
        halo = blur(m, 18) * (1 - m) * 0.35 * (0.5 + n2)
        a = np.clip(m * (0.3 + 0.55 * n2) + 0.4 * ring_ + halo, 0, 0.95) * vignette(0.04)
        rgb = col(0.05, 0.04, 0.03) * (0.75 + 0.5 * n3)[..., None] * (1 - 0.4 * ring_)[..., None]
        save("oil_stain_%d" % i, rgb, a)
    # grime streaks (vertical, start at top)
    for i, (seed, rust) in enumerate(((31, False), (37, True)), 1):
        r = np.random.default_rng(seed)
        cols = vnoise(1, N, 1, 70, r)[0] * 0.55 + vnoise(1, N, 1, 220, r)[0] * 0.45
        if rust:
            cols = np.zeros(N, np.float32)
            for k in range(7):
                c = r.uniform(80, N - 80)
                cols = np.maximum(cols, np.exp(-((np.arange(N) - c) / r.uniform(8, 22)) ** 2) * r.uniform(0.6, 1.0))
        length = 0.3 + 0.65 * vnoise(1, N, 1, 18, r)[0]
        y = YY / N
        fall = np.clip(1 - y / length[None, :], 0, 1) ** 0.7
        top = smooth(0.0, 0.02, y) * (1 - smooth(0.04, 0.16, y))
        brk = vnoise(N, N, 6, 60, r) * 0.6 + vnoise(N, N, 24, 160, r) * 0.4
        streak = (smooth(0.4, 0.8, cols) if not rust else cols)[None, :] * fall
        a = np.clip(streak * (0.45 + 0.75 * brk) * (1.1 if rust else 0.95) + (0 if rust else 0.6) * top * (0.4 + 0.6 * brk), 0, 0.9)
        a = blur(a, 1) * smooth(0.0, 0.06, np.minimum(XX, N - 1 - XX) / N) * (1 - smooth(0.93, 1.0, y))
        rgb = col(0.3, 0.14, 0.05) if rust else col(0.11, 0.1, 0.085)
        save("grime_streak_%d" % i, rgb * (0.8 + 0.4 * brk)[..., None], a)
    # floor scuffs
    r = np.random.default_rng(41)
    m = np.zeros((N, N), np.float32)
    for k in range(80):
        cx, cy = r.uniform(120, N - 120), r.uniform(120, N - 120)
        rad = r.uniform(40, 320)
        a0 = r.uniform(0, 2 * math.pi)
        sw = r.uniform(0.15, 0.9) * (1 if r.random() < 0.5 else -1)
        w = r.uniform(1.0, 5.0)
        val = r.uniform(0.3, 0.85)
        n = 16
        pts = [(cx + rad * math.cos(a0 + sw * t / n), cy + rad * math.sin(a0 + sw * t / n)) for t in range(n + 1)]
        for t in range(n):
            seg(m, pts[t], pts[t + 1], max(0.6, w * math.sin(math.pi * (t + 0.5) / n)), val)
    smudge = np.zeros((N, N), np.float32)
    for k in range(10):
        ellipse(smudge, r.uniform(200, N - 200), r.uniform(200, N - 200), r.uniform(40, 120), r.uniform(10, 30), r.uniform(0, 3), r.uniform(0.15, 0.35))
    smudge = blur(smudge, 12)
    n1 = fbm(r, 8, 4)
    a = np.clip((m + smudge) * (0.55 + 0.45 * n1), 0, 0.85) * (1 - smooth(0.36, 0.5, np.hypot(XX - N / 2, YY - N / 2) / N))
    save("floor_scuffs_1", col(0.035, 0.035, 0.035), a)
    # cracks + normal
    r = np.random.default_rng(53)
    m = np.zeros((N, N), np.float32)

    def crack(x, y, h, w, depth=0):
        steps = 0
        while 0 < x < N and 0 < y < N and w > 0.55 and steps < 400:
            h += r.normal(0, 0.28)
            nx, ny = x + 6 * math.cos(h), y + 6 * math.sin(h)
            seg(m, (x, y), (nx, ny), w, 1.0, 0.8)
            x, y = nx, ny
            w *= 0.993
            steps += 1
            if depth < 3 and r.random() < 0.035:
                crack(x, y, h + r.choice((-1, 1)) * r.uniform(0.5, 1.2), w * 0.6, depth + 1)
    crack(60, 520, 0.0, 4.0)
    crack(500, 40, 1.57, 3.0)
    crack(980, 760, 3.3, 2.5)
    spall = smooth(0.25, 0.6, blur(m, 5) * 3) * smooth(0.55, 0.75, fbm(r, 16, 3))
    dirt = blur(m, 10) * 2
    v = 1 - smooth(0.38, 0.5, np.hypot(XX - N / 2, YY - N / 2) / N)
    a = np.clip(m * 0.95 + spall * 0.4 + dirt * 0.25, 0, 1) * v
    save("cracks_1", col(0.05, 0.045, 0.04), a)
    h = -(blur(m, 1) * 1.0 + spall * 0.35)
    gy, gx = np.gradient(h)
    k = 6.0
    nrm = np.stack([-gx * k, gy * k, np.ones_like(h)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    save("cracks_1_normal", nrm * 0.5 + 0.5, np.clip(a * 1.5, 0, 1), noncolor=True)
    # scorch
    r = np.random.default_rng(61)
    X, Y = XX - N / 2, YY - N / 2
    d = np.hypot(X, Y) / (N * 0.4)
    ang = (np.arctan2(Y, X) + math.pi) / (2 * math.pi)
    q = r.random(96)
    rays = np.interp(ang, np.linspace(0, 1, 97), np.append(q, q[0])).astype(np.float32)
    n1 = fbm(r, 5, 5)
    dd = d * (1 - 0.45 * (rays - 0.5) * d) * (1 + 0.3 * (n1 - 0.5))
    dd = dd * (1 + 0.9 * (fbm(r, 2, 4) - 0.5))
    core = 1 - smooth(0.2, 0.7, dd)
    outer = 1 - smooth(0.55, 1.05, dd)
    spk = np.zeros((N, N), np.float32)
    for k in range(160):
        a0 = r.uniform(0, 2 * math.pi)
        rr = N * 0.4 * r.uniform(0.6, 1.15)
        ellipse(spk, N / 2 + rr * math.cos(a0), N / 2 + rr * math.sin(a0), r.uniform(1.5, 5), r.uniform(1.5, 4), 0, r.uniform(0.2, 0.6))
    a = np.clip(0.95 * core + 0.65 * outer * (0.45 + 0.55 * fbm(r, 10, 3)) + spk * 0.6, 0, 1) * vignette(0.03)
    t = smooth(0.1, 0.9, dd)[..., None]
    ash = smooth(0.55, 0.8, fbm(r, 9, 4))[..., None] * (1 - t)
    rgb = col(0.02, 0.018, 0.016) * (1 - t) + col(0.2, 0.12, 0.06) * t
    rgb = rgb * (1 - ash) + col(0.16, 0.155, 0.15) * ash
    save("scorch_1", rgb, a)
    # puddle + roughness hint
    m, ring_, r = blob(71, 330, 1.3, 0.35)
    m = blur(m, 2)
    a = np.clip(m * 0.5 + ring_ * 0.3, 0, 0.85) * vignette(0.03)
    save("puddle_1", col(0.02, 0.022, 0.026), a)
    save("puddle_1_rough", np.clip(1 - m * 0.94, 0, 1), np.clip(m * 1.2, 0, 1), noncolor=True)
    # tire marks
    r = np.random.default_rng(83)
    P = [Vector((-120, 870)), Vector((380, 860)), Vector((640, 150)), Vector((1150, 160))]
    path = [((1 - t) ** 3) * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t * t * P[2] + t ** 3 * P[3] for t in [i / 200 for i in range(201)]]
    acc = np.zeros((N, N), np.float32)
    for off_ in (-160, 160):
        best = np.full((N, N), 1e9, np.float32)
        S = np.zeros((N, N), np.float32)
        U = np.zeros((N, N), np.float32)
        s0 = 0.0
        hw = 52
        for p0, p1 in zip(path[:-1], path[1:]):
            tdir = (p1 - p0).normalized()
            nrm_ = Vector((-tdir.y, tdir.x))
            q0, q1 = p0 + nrm_ * off_, p1 + nrm_ * off_
            L = (q1 - q0).length
            x0, x1 = int(max(0, min(q0.x, q1.x) - hw - 2)), int(min(N, max(q0.x, q1.x) + hw + 3))
            y0, y1 = int(max(0, min(q0.y, q1.y) - hw - 2)), int(min(N, max(q0.y, q1.y) + hw + 3))
            if x1 > x0 and y1 > y0:
                Xs, Ys = XX[y0:y1, x0:x1] - q0.x, YY[y0:y1, x0:x1] - q0.y
                tt = np.clip((Xs * tdir.x + Ys * tdir.y) / max(L, 1e-6), 0, 1)
                uu = Xs * nrm_.x + Ys * nrm_.y
                dist = np.hypot(Xs - tt * (q1.x - q0.x), Ys - tt * (q1.y - q0.y))
                sel = dist < best[y0:y1, x0:x1]
                best[y0:y1, x0:x1] = np.where(sel, dist, best[y0:y1, x0:x1])
                S[y0:y1, x0:x1] = np.where(sel, s0 + tt * L, S[y0:y1, x0:x1])
                U[y0:y1, x0:x1] = np.where(sel, uu, U[y0:y1, x0:x1])
            s0 += L
        inside = 1 - smooth(hw - 5, hw, best)
        ph = (S + 0.7 * np.abs(U)) / 24.0
        f = ph - np.floor(ph)
        lug = smooth(0.3, 0.4, f) * (1 - smooth(0.72, 0.82, f))
        groove = smooth(3, 6, np.abs(U))
        along = smooth(0, 220, S) * (1 - smooth(s0 - 300, s0, S))
        acc = np.maximum(acc, inside * (0.3 + 0.6 * lug * groove) * along)
    a = np.clip(acc * (0.45 + 0.55 * fbm(r, 6, 4)), 0, 0.9) * vignette(0.03)
    save("tire_marks_1", col(0.03, 0.03, 0.03), a)
    # dusty boot prints
    r = np.random.default_rng(97)
    m = np.zeros((N, N), np.float32)
    start, end = Vector((150, 930)), Vector((880, 80))
    hd = (end - start).normalized()
    side = Vector((-hd.y, hd.x))
    heading = math.atan2(hd.y, hd.x)
    nprint = 5
    for i in range(nprint):
        c = start + hd * (i * (end - start).length / (nprint - 0.6)) + side * (55 if i % 2 else -55)
        fade = 1.0 - 0.13 * i
        Rb = 110
        x0, x1 = int(max(0, c.x - Rb)), int(min(N, c.x + Rb))
        y0, y1 = int(max(0, c.y - Rb)), int(min(N, c.y + Rb))
        X, Y = XX[y0:y1, x0:x1] - c.x, YY[y0:y1, x0:x1] - c.y
        u = X * math.cos(heading) + Y * math.sin(heading)
        v = -X * math.sin(heading) + Y * math.cos(heading)
        if i % 2:
            v = -v
        u, v = u / 1.35, v / 1.35
        fore = 1 - np.sqrt(((u - 24) / 40) ** 2 + ((v - 3) / 23) ** 2)
        heel = 1 - np.sqrt(((u + 40) / 22) ** 2 + (v / 19) ** 2)
        waist = 1 - np.sqrt(((u + 8) / 36) ** 2 + (v / 16) ** 2)
        shape = np.clip(np.maximum(np.maximum(fore, heel), waist) * 18, 0, 1)
        f1 = (u + np.abs(v) * 0.8) / 9.0
        lug_f = (f1 - np.floor(f1)) < 0.55
        g1, g2 = u / 8.0, v / 8.0
        lug_h = ((g1 - np.floor(g1)) < 0.6) & ((g2 - np.floor(g2)) < 0.6)
        lug = np.where(u > -18, lug_f, lug_h).astype(np.float32)
        pr = shape * (0.35 + 0.65 * lug) * fade
        np.maximum(m[y0:y1, x0:x1], pr, out=m[y0:y1, x0:x1])
    a = np.clip(m * (0.45 + 0.55 * fbm(r, 14, 3)), 0, 1) * 0.8 * vignette(0.03)
    save("footprints_dust_1", col(0.74, 0.72, 0.68), a)
    # stencils
    for s, nm in (("NO STEP", "stencil_no_step"), ("HIGH VOLTAGE", "stencil_high_voltage"), ("9-B", "stencil_9b"), ("LIFT 2", "stencil_lift_2")):
        mask = text_mask(s, N, np)
        r = np.random.default_rng(len(s) * 101)
        wear = 1 - 0.55 * smooth(0.7, 0.78, fbm(r, 12, 4)) - 0.35 * smooth(0.74, 0.82, fbm(r, 48, 2))
        over = blur(mask, 5) * 0.18 * (0.5 + fbm(r, 30, 2))
        a = np.clip(blur(mask, 0) * wear * 0.95 + over, 0, 1)
        save(nm, col(0.93, 0.93, 0.9), a)
    decal_sheet(OUT, out_dir, np)


def text_mask(s, N, np):
    """Rasterise text with Blender's built-in font, add stencil bridges across enclosed counters. Returns N x N mask (top-down)."""
    cu = bpy.data.curves.new("_stencil", "FONT")
    cu.body = s
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.offset = 0.035
    cu.space_character = 1.12
    FONT_INFO.setdefault("font", (cu.font.name if cu.font else "builtin", cu.font.filepath if cu.font else "<builtin>"))
    o = bpy.data.objects.new("_stencil", cu)
    bpy.context.scene.collection.objects.link(o)
    o.scale = (0.82, 1.0, 1.0)
    vl = bpy.context.view_layer
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    vl.objects.active = o
    bpy.ops.object.convert(target="MESH")
    o = vl.objects.active
    me = o.data
    me.calc_loop_triangles()
    sx = o.scale.x
    vs = np.array([(v.co.x * sx, v.co.y) for v in me.vertices], dtype=np.float32)
    tris_ = np.array([t.vertices[:] for t in me.loop_triangles], dtype=np.int64)
    lo, hi = vs.min(0), vs.max(0)
    sc = min(0.86 * N / (hi[0] - lo[0]), 0.42 * N / (hi[1] - lo[1]))
    cx, cy = (lo + hi) / 2
    px = (vs[:, 0] - cx) * sc + N / 2
    py = N / 2 - (vs[:, 1] - cy) * sc
    SS = 3
    mask = np.zeros((N * SS, N * SS), np.float32)
    PX, PY = px * SS, py * SS
    for a_, b_, c_ in tris_:
        xs, ys = PX[[a_, b_, c_]], PY[[a_, b_, c_]]
        x0, x1 = int(max(0, xs.min())), int(min(N * SS, xs.max() + 1))
        y0, y1 = int(max(0, ys.min())), int(min(N * SS, ys.max() + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
        (ax, bx, cx2), (ay, by, cy2) = xs, ys
        d = (by - cy2) * (ax - cx2) + (cx2 - bx) * (ay - cy2)
        if abs(d) < 1e-9:
            continue
        l1 = ((by - cy2) * (gx - cx2) + (cx2 - bx) * (gy - cy2)) / d
        l2 = ((cy2 - ay) * (gx - cx2) + (ax - cx2) * (gy - cy2)) / d
        ins = (l1 >= -1e-4) & (l2 >= -1e-4) & (l1 + l2 <= 1 + 1e-4)
        mask[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1], ins.astype(np.float32))
    bpy.data.objects.remove(o, do_unlink=True)
    m = mask.reshape(N, SS, N, SS).mean(axis=(1, 3))
    # Stencil bridges: find enclosed counters (background not reachable from the border) at 1/2 res.
    h = N // 2
    ink = m.reshape(h, 2, h, 2).mean(axis=(1, 3)) > 0.5
    bg = ~ink
    reach = np.zeros_like(bg)
    reach[0, :] = bg[0, :]
    reach[-1, :] = bg[-1, :]
    reach[:, 0] = bg[:, 0]
    reach[:, -1] = bg[:, -1]
    for _ in range(2000):
        nr = reach.copy()
        nr[1:, :] |= reach[:-1, :]
        nr[:-1, :] |= reach[1:, :]
        nr[:, 1:] |= reach[:, :-1]
        nr[:, :-1] |= reach[:, 1:]
        nr &= bg
        if (nr == reach).all():
            break
        reach = nr
    holes = bg & ~reach
    lab = np.zeros(holes.shape, np.int32)
    nlab = 0
    rem = holes.copy()
    regions = []
    while rem.any():
        ys, xs = np.nonzero(rem)
        reg = np.zeros_like(rem)
        reg[ys[0], xs[0]] = True
        for _ in range(2000):
            nr = reg.copy()
            nr[1:, :] |= reg[:-1, :]
            nr[:-1, :] |= reg[1:, :]
            nr[:, 1:] |= reg[:, :-1]
            nr[:, :-1] |= reg[:, 1:]
            nr &= rem
            if (nr == reg).all():
                break
            reg = nr
        rem &= ~reg
        ys, xs = np.nonzero(reg)
        if len(ys) > 30:
            regions.append((int(xs.mean()) * 2, int(ys.min()) * 2, int(ys.max()) * 2))
    bw = max(3, int(0.018 * N))
    for hx, ytop, ybot in regions:
        c0, c1 = max(0, hx - bw // 2), min(N, hx + bw // 2 + 1)
        col_ink = m[:, hx] > 0.5
        y = ytop - 1
        while y > 0 and not col_ink[y]:
            y -= 1
        y_end = y
        while y_end > 0 and col_ink[y_end]:
            y_end -= 1
        m[y_end:ytop, c0:c1] = 0
        y = ybot + 1
        while y < N - 1 and not col_ink[y]:
            y += 1
        y_end = y
        while y_end < N - 1 and col_ink[y_end]:
            y_end += 1
        m[ybot:y_end + 1, c0:c1] = 0
    return m


def decal_sheet(out, out_dir, np):
    """Composite every decal over the project's hangar concrete floor albedo for review."""
    T = 512
    cols = 4
    rows = (len(out) + cols - 1) // cols
    sheet = np.zeros((rows * T, cols * T, 4), np.float32)
    sheet[..., 3] = 1
    bgp = os.path.join(HERE, "..", "..", "assets", "textures", "hangar_concrete_floor", "albedo.jpg")
    bgt = None
    if os.path.exists(bgp):
        im = bpy.data.images.load(os.path.abspath(bgp))
        w, h = im.size
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        px = np.flipud(px.reshape(h, w, 4))
        step = max(1, w // T)
        bgt = px[:T * step:step, :T * step:step, :3][:T, :T]
        bpy.data.images.remove(im)
    for i, (name, rgba) in enumerate(out):
        N = rgba.shape[0]
        s = N // T
        d = rgba[:T * s, :T * s].reshape(T, s, T, s, 4).mean(axis=(1, 3))
        base = bgt.copy() if bgt is not None else np.full((T, T, 3), 0.45, np.float32)
        if name.endswith("_normal") or name.endswith("_rough"):
            tile = d[..., :3] * d[..., 3:4] + base * 0.3 * (1 - d[..., 3:4])
        else:
            tile = d[..., :3] * d[..., 3:4] + base * (1 - d[..., 3:4])
        r_, c_ = divmod(i, cols)
        sheet[r_ * T:(r_ + 1) * T, c_ * T:(c_ + 1) * T, :3] = tile
    pdir = os.path.join(out_dir, "previews")
    os.makedirs(pdir, exist_ok=True)
    img = bpy.data.images.new("decal_sheet", cols * T, rows * T, alpha=False)
    img.pixels.foreach_set(np.flipud(sheet).ravel())
    img.filepath_raw = os.path.join(pdir, "decals_sheet.png")
    img.file_format = "PNG"
    img.save()
    print("wrote decals_sheet.png  order:", [n for n, _ in out])


if __name__ == "__main__":
    mode = ARGV[0] if ARGV else "build"
    if mode == "build":
        build(ARGV[1] if len(ARGV) > 1 else "staging/env_m3")
    elif mode == "decals":
        decals(ARGV[1] if len(ARGV) > 1 else "staging/env_m3")
    elif mode == "sheet":
        K.sheet_glb(ARGV[1], ARGV[2], int(ARGV[3]) if len(ARGV) > 3 else 4)
    elif mode == "detail":
        K.detail_glb(ARGV[1], ARGV[2], int(ARGV[3]), ARGV[4:])
    elif mode == "row":
        K.row_glb(ARGV[1], ARGV[2])
    print("ALL DONE")
