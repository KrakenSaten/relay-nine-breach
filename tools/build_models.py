# BREACH asset builder. Run headless:
#   blender -b --factory-startup -P tools/build_models.py -- <out_dir>
# Generates original hard-surface meshes (weapons, attachments, Teslabot, props) as .glb.
# Blender coords: X right, Y forward (becomes Godot -Z), Z up. Units: meters.
import bpy, math, sys, os
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "assets/models"
os.makedirs(OUT, exist_ok=True)

MATS = {
    # name: (base rgb, metallic, roughness, emission rgb, emission strength)
    "gunmetal": ((0.045, 0.047, 0.05), 1.0, 0.38, None, 0),
    "anodized": ((0.03, 0.032, 0.034), 0.85, 0.48, None, 0),
    "polymer": ((0.025, 0.025, 0.024), 0.0, 0.62, None, 0),
    "polymer_tan": ((0.32, 0.27, 0.19), 0.0, 0.6, None, 0),
    "rubber": ((0.015, 0.015, 0.015), 0.0, 0.85, None, 0),
    "steel": ((0.55, 0.55, 0.56), 1.0, 0.32, None, 0),
    "copper": ((0.75, 0.38, 0.2), 1.0, 0.3, None, 0),
    "glass_lens": ((0.05, 0.08, 0.07), 0.2, 0.05, None, 0),
    "reticle": ((1.0, 0.15, 0.08), 0.0, 0.5, (1.0, 0.12, 0.05), 6.0),
    "robot_paint": ((0.62, 0.3, 0.07), 0.25, 0.52, None, 0),
    "robot_bone": ((0.62, 0.6, 0.55), 0.15, 0.5, None, 0),
    "robot_dark": ((0.06, 0.062, 0.066), 0.9, 0.42, None, 0),
    "robot_joint": ((0.12, 0.12, 0.12), 1.0, 0.3, None, 0),
    "core_glow": ((0.6, 0.8, 1.0), 0.0, 0.3, (0.45, 0.75, 1.0), 9.0),
    "eye_glow": ((1.0, 0.25, 0.1), 0.0, 0.3, (1.0, 0.18, 0.05), 10.0),
    "arc_tip": ((0.7, 0.85, 1.0), 0.0, 0.3, (0.5, 0.8, 1.0), 6.0),
    "hazard": ((0.75, 0.55, 0.05), 0.1, 0.55, None, 0),
    "door_steel": ((0.22, 0.24, 0.24), 0.8, 0.5, None, 0),
    "crate_green": ((0.13, 0.17, 0.12), 0.3, 0.6, None, 0),
    "painted_grey": ((0.32, 0.33, 0.33), 0.3, 0.55, None, 0),
    "screen": ((0.02, 0.05, 0.05), 0.0, 0.2, (0.25, 0.7, 0.6), 2.5),
    "lamp_warm": ((1.0, 0.8, 0.55), 0.0, 0.4, (1.0, 0.72, 0.42), 8.0),
    "concrete": ((0.45, 0.44, 0.42), 0.0, 0.85, None, 0),
    "led_amber": ((1.0, 0.6, 0.1), 0.0, 0.4, (1.0, 0.55, 0.1), 5.0),
    "led_red": ((1.0, 0.1, 0.05), 0.0, 0.4, (1.0, 0.08, 0.04), 5.0),
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
    return m


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _finish(o, material, bevel, segs=2):
    o.data.materials.append(mat(material))
    if bevel > 0:
        md = o.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = segs
        md.limit_method = "ANGLE"
        md.angle_limit = math.radians(35)
        md.harden_normals = True
    try:
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    except Exception:
        try:
            bpy.ops.object.shade_flat()
        except Exception:
            pass
    o.select_set(False)
    return o


def box(name, loc, size, material, bevel=0.002, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=[math.radians(r) for r in rot])
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _finish(o, material, bevel)
    if parent:
        set_parent(o, parent)
    return o


def cyl(name, loc, r, depth, material, axis="Y", verts=24, bevel=0.0015, parent=None, r2=None):
    rot = {"X": (0, 90, 0), "Y": (90, 0, 0), "Z": (0, 0, 0)}[axis]
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=[math.radians(a) for a in rot])
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=depth, location=loc, rotation=[math.radians(a) for a in rot])
    o = bpy.context.active_object
    o.name = name
    _finish(o, material, bevel)
    if parent:
        set_parent(o, parent)
    return o


def torus(name, loc, R, r, material, axis="Y", parent=None):
    rot = {"X": (0, 90, 0), "Y": (90, 0, 0), "Z": (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=32, minor_segments=10, location=loc, rotation=[math.radians(a) for a in rot])
    o = bpy.context.active_object
    o.name = name
    _finish(o, material, 0)
    if parent:
        set_parent(o, parent)
    return o


def empty(name, loc, parent=None):
    o = bpy.data.objects.new(name, None)
    o.location = loc
    o.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(o)
    if parent:
        set_parent(o, parent)
    return o


def set_parent(child, parent):
    bpy.context.view_layer.update()
    m = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = m


def export(fname):
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, fname), export_format="GLB", export_apply=True, export_yup=True)
    print("exported", fname)


def rail(name, y0, y1, z, parent, width=0.021):
    box(name, (0, (y0 + y1) / 2, z), (width, y1 - y0, 0.008), "anodized", 0.001, parent=parent)
    n = int((y1 - y0) / 0.01)
    for i in range(n):
        box(f"{name}_t{i}", (0, y0 + 0.005 + i * 0.01, z + 0.006), (width, 0.0055, 0.004), "anodized", 0.0006, parent=parent)


# ---------------------------------------------------------------- RIFLE
def build_rifle():
    reset()
    root = empty("Rifle", (0, 0, 0))
    box("upper", (0, 0.10, 0.012), (0.044, 0.25, 0.046), "anodized", 0.003, parent=root)
    box("lower", (0, 0.085, -0.032), (0.040, 0.2, 0.042), "anodized", 0.003, parent=root)
    box("ejection_port", (0.0225, 0.13, 0.012), (0.002, 0.07, 0.018), "gunmetal", 0.0005, parent=root)
    box("fwd_assist", (0.026, 0.05, 0.02), (0.012, 0.03, 0.014), "gunmetal", 0.002, parent=root)
    box("magwell", (0, 0.16, -0.064), (0.036, 0.066, 0.04), "anodized", 0.003, parent=root)
    box("grip", (0, 0.015, -0.088), (0.031, 0.042, 0.105), "polymer", 0.006, rot=(-18, 0, 0), parent=root)
    box("trigger_guard", (0, 0.065, -0.07), (0.012, 0.07, 0.006), "anodized", 0.001, parent=root)
    box("trigger", (0, 0.07, -0.06), (0.005, 0.006, 0.02), "gunmetal", 0.001, rot=(10, 0, 0), parent=root)
    box("selector", (-0.022, 0.035, -0.025), (0.004, 0.018, 0.008), "gunmetal", 0.001, parent=root)
    box("charging_handle", (0, -0.03, 0.03), (0.04, 0.03, 0.01), "anodized", 0.002, parent=root)
    cyl("buffer_tube", (0, -0.12, 0.0), 0.0155, 0.2, "anodized", parent=root)
    box("stock", (0, -0.21, -0.012), (0.042, 0.13, 0.07), "polymer", 0.008, parent=root)
    box("stock_cheek", (0, -0.2, 0.022), (0.036, 0.11, 0.016), "polymer", 0.006, parent=root)
    box("buttpad", (0, -0.283, -0.022), (0.044, 0.018, 0.12), "rubber", 0.006, parent=root)
    # Free-float handguard: octagon profile with cut lightening slots.
    hg = cyl("handguard", (0, 0.355, 0.006), 0.031, 0.25, "anodized", verts=8, bevel=0.003, parent=root)
    hg.rotation_euler[1] = math.radians(22.5)
    for i in range(5):
        for side in (-1, 1):
            box(f"hg_slot_{i}_{side}", (side * 0.029, 0.27 + i * 0.045, 0.006), (0.006, 0.028, 0.012), "gunmetal", 0.002, parent=root)
    rail("top_rail", -0.02, 0.48, 0.040, root)
    cyl("barrel", (0, 0.55, 0.004), 0.0095, 0.17, "gunmetal", verts=20, parent=root)
    cyl("gas_block", (0, 0.49, 0.008), 0.014, 0.02, "gunmetal", verts=20, parent=root)
    cyl("flash_hider", (0, 0.645, 0.004), 0.0125, 0.05, "gunmetal", verts=6, bevel=0.002, parent=root)
    box("front_sight_folded", (0, 0.46, 0.05), (0.014, 0.025, 0.008), "anodized", 0.001, parent=root)
    box("rear_sight_folded", (0, -0.005, 0.05), (0.018, 0.02, 0.008), "anodized", 0.001, parent=root)
    box("sling_mount", (-0.022, -0.04, -0.01), (0.006, 0.014, 0.014), "gunmetal", 0.001, parent=root)
    empty("sock_optic", (0, 0.09, 0.048), root)
    empty("sock_muzzle", (0, 0.67, 0.004), root)
    empty("sock_grip", (0, 0.38, -0.025), root)
    empty("sock_mag", (0, 0.16, -0.084), root)
    empty("sock_eject", (0.03, 0.13, 0.012), root)
    empty("sock_iron", (0, 0.0, 0.062), root)
    export("rifle.glb")


def build_attachments():
    reset()
    # Reflex sight
    r = empty("optic_reflex", (0, 0, 0))
    box("base", (0, 0, 0.008), (0.03, 0.05, 0.014), "anodized", 0.002, parent=r)
    box("hood_l", (-0.015, 0.012, 0.03), (0.004, 0.026, 0.036), "anodized", 0.0015, parent=r)
    box("hood_r", (0.015, 0.012, 0.03), (0.004, 0.026, 0.036), "anodized", 0.0015, parent=r)
    box("hood_t", (0, 0.012, 0.049), (0.034, 0.026, 0.004), "anodized", 0.0015, parent=r)
    box("lens", (0, 0.02, 0.031), (0.026, 0.002, 0.032), "glass_lens", 0, parent=r)
    box("emitter", (0, -0.008, 0.017), (0.008, 0.008, 0.006), "gunmetal", 0.001, parent=r)
    box("knob", (0.019, -0.008, 0.012), (0.006, 0.012, 0.012), "gunmetal", 0.001, parent=r)
    empty("eye", (0, -0.30, 0.031), r)
    # 2x prism optic
    p = empty("optic_prism", (0.2, 0, 0))
    box("base", (0.2, 0, 0.008), (0.032, 0.07, 0.014), "anodized", 0.002, parent=p)
    box("body", (0.2, 0.0, 0.038), (0.038, 0.06, 0.046), "anodized", 0.004, parent=p)
    cyl("objective", (0.2, 0.045, 0.04), 0.019, 0.035, "anodized", parent=p)
    cyl("ocular", (0.2, -0.043, 0.04), 0.017, 0.03, "anodized", parent=p)
    cyl("obj_glass", (0.2, 0.063, 0.04), 0.016, 0.002, "glass_lens", bevel=0, parent=p)
    cyl("ocu_ring", (0.2, -0.059, 0.04), 0.0175, 0.004, "rubber", parent=p)
    box("turret", (0.2 + 0.022, 0.0, 0.04), (0.008, 0.018, 0.018), "gunmetal", 0.002, parent=p)
    empty("eye", (0.2, -0.16, 0.04), p)
    # Suppressor
    s = empty("suppressor", (0.4, 0, 0))
    cyl("can", (0.4, 0.09, 0), 0.0205, 0.17, "anodized", verts=32, bevel=0.003, parent=s)
    cyl("mount", (0.4, 0.005, 0), 0.016, 0.02, "gunmetal", verts=24, parent=s)
    cyl("cap", (0.4, 0.176, 0), 0.019, 0.006, "gunmetal", verts=32, parent=s)
    # Vertical grip
    g = empty("grip_vertical", (0.6, 0, 0))
    box("clamp", (0.6, 0, -0.005), (0.026, 0.04, 0.012), "anodized", 0.002, parent=g)
    cyl("handle", (0.6, 0.0, -0.05), 0.0135, 0.08, "polymer", axis="Z", parent=g)
    cyl("cap", (0.6, 0.0, -0.091), 0.0145, 0.006, "rubber", axis="Z", parent=g)
    # Angled grip
    a = empty("grip_angled", (0.8, 0, 0))
    box("clamp", (0.8, 0, -0.005), (0.026, 0.06, 0.012), "anodized", 0.002, parent=a)
    box("wedge", (0.8, -0.005, -0.022), (0.024, 0.06, 0.026), "polymer", 0.008, rot=(-25, 0, 0), parent=a)
    # Magazines (origin at the top of the magazine, i.e. at magwell socket)
    for name, length, mt, x in (("mag_std", 0.17, "polymer", 1.0), ("mag_ext", 0.24, "polymer", 1.2), ("mag_quick", 0.15, "polymer_tan", 1.4)):
        m = empty(name, (x, 0, 0))
        box("body", (x, 0.004, -length / 2), (0.024, 0.062, length), mt, 0.004, rot=(10, 0, 0), parent=m)
        box("floor", (x, 0.004 + math.sin(math.radians(10)) * length, -length - 0.004), (0.028, 0.068, 0.01), "polymer", 0.003, rot=(10, 0, 0), parent=m)
        for i in range(int(length / 0.03)):
            box(f"rib{i}", (x + 0.0125, 0.005 + i * 0.005, -0.02 - i * 0.03), (0.002, 0.05, 0.004), mt, 0.0008, rot=(10, 0, 0), parent=m)
        if name == "mag_quick":
            box("pull_loop", (x, 0.004 + math.sin(math.radians(10)) * length, -length - 0.025), (0.012, 0.04, 0.03), "rubber", 0.004, parent=m)
    export("attachments.glb")


def build_pistol():
    reset()
    root = empty("Pistol", (0, 0, 0))
    box("slide", (0, 0.09, 0.004), (0.028, 0.19, 0.03), "gunmetal", 0.003, parent=root)
    for i in range(7):
        box(f"serr{i}", (0, 0.005 + i * 0.006, 0.004), (0.0295, 0.0025, 0.024), "anodized", 0.0005, parent=root)
    box("ejection", (0.0142, 0.11, 0.009), (0.001, 0.04, 0.012), "anodized", 0, parent=root)
    box("frame", (0, 0.085, -0.022), (0.026, 0.17, 0.022), "polymer", 0.003, parent=root)
    box("rail", (0, 0.15, -0.035), (0.02, 0.05, 0.008), "polymer", 0.002, parent=root)
    box("grip", (0, 0.008, -0.075), (0.03, 0.05, 0.105), "polymer", 0.006, rot=(-14, 0, 0), parent=root)
    box("trigger_guard", (0, 0.07, -0.045), (0.012, 0.055, 0.006), "polymer", 0.002, parent=root)
    box("trigger", (0, 0.06, -0.036), (0.005, 0.006, 0.018), "gunmetal", 0.001, rot=(10, 0, 0), parent=root)
    cyl("barrel_tip", (0, 0.186, 0.006), 0.0065, 0.006, "anodized", parent=root)
    box("front_sight", (0, 0.175, 0.023), (0.004, 0.006, 0.008), "anodized", 0.0005, parent=root)
    box("rear_sight", (0, 0.008, 0.022), (0.022, 0.008, 0.008), "anodized", 0.001, parent=root)
    box("dot_f", (0, 0.172, 0.025), (0.002, 0.001, 0.002), "led_amber", 0, parent=root)
    box("mag_base", (0, -0.007, -0.13), (0.03, 0.045, 0.01), "polymer", 0.002, rot=(-14, 0, 0), parent=root)
    empty("sock_muzzle", (0, 0.19, 0.006), root)
    empty("sock_iron", (0, 0.0, 0.028), root)
    empty("sock_eject", (0.02, 0.11, 0.01), root)
    export("pistol.glb")


# ---------------------------------------------------------------- TESLABOT
def build_teslabot():
    reset()
    root = empty("Teslabot", (0, 0, 0))
    pelvis = empty("pelvis", (0, 0, 1.02), root)
    box("pelvis_block", (0, 0, 1.02), (0.44, 0.26, 0.2), "robot_dark", 0.02, parent=pelvis)
    box("pelvis_skirt", (0, 0.1, 0.96), (0.3, 0.04, 0.14), "robot_paint", 0.015, rot=(-10, 0, 0), parent=pelvis)
    torso = empty("torso", (0, 0, 1.12), pelvis)
    cyl("abdomen", (0, 0, 1.17), 0.17, 0.18, "robot_joint", axis="Z", verts=16, parent=torso)
    for i in range(3):
        torus(f"abd_ring{i}", (0, 0, 1.12 + i * 0.05), 0.135, 0.012, "robot_dark", axis="Z", parent=torso)
    box("chest_core", (0, -0.02, 1.47), (0.5, 0.36, 0.46), "robot_dark", 0.03, parent=torso)
    box("chest_plate", (0, 0.17, 1.5), (0.56, 0.06, 0.4), "robot_paint", 0.025, rot=(8, 0, 0), parent=torso)
    box("chest_plate_low", (0, 0.15, 1.27), (0.42, 0.05, 0.14), "robot_paint", 0.02, rot=(-12, 0, 0), parent=torso)
    box("chest_stripe", (0.18, 0.205, 1.55), (0.06, 0.005, 0.22), "hazard", 0.002, rot=(8, 0, 0), parent=torso)
    box("chest_id", (-0.16, 0.204, 1.6), (0.1, 0.004, 0.04), "robot_bone", 0.002, rot=(8, 0, 0), parent=torso)
    for side in (-1, 1):
        box(f"side_armor_{side}", (side * 0.27, 0, 1.45), (0.06, 0.32, 0.36), "robot_paint", 0.02, parent=torso)
        box(f"vent_{side}", (side * 0.302, -0.05, 1.42), (0.006, 0.12, 0.16), "robot_joint", 0.002, parent=torso)
    box("collar", (0, 0, 1.72), (0.34, 0.3, 0.06), "robot_dark", 0.02, parent=torso)
    # Status LED strips: keep the silhouette readable in dark rooms.
    for side in (-1, 1):
        box(f"status_led_{side}", (side * 0.2, 0.2, 1.36), (0.08, 0.006, 0.012), "led_amber", 0, rot=(-12, 0, 0), parent=torso)
        box(f"shoulder_led_{side}", (side * 0.39, 0.13, 1.69), (0.012, 0.006, 0.06), "led_amber", 0, parent=torso)
    # Back-mounted tesla capacitor: the meaningful weak point.
    core = empty("core", (0, -0.27, 1.5), torso)
    box("core_housing", (0, -0.24, 1.5), (0.3, 0.1, 0.38), "robot_dark", 0.02, parent=core)
    for side in (-1, 1):
        cyl(f"coil_post_{side}", (side * 0.08, -0.31, 1.5), 0.035, 0.3, "robot_joint", axis="Z", verts=16, parent=core)
        for i in range(6):
            torus(f"coil_{side}_{i}", (side * 0.08, -0.31, 1.39 + i * 0.045), 0.045, 0.01, "copper", axis="Z", parent=core)
    cyl("core_glow", (0, -0.31, 1.5), 0.028, 0.26, "core_glow", axis="Z", verts=16, bevel=0, parent=core)
    box("core_cage", (0, -0.355, 1.5), (0.26, 0.01, 0.3), "robot_joint", 0.002, parent=core)
    # Head: low wedge with a single horizontal optic slit.
    head = empty("head", (0, 0.02, 1.78), torso)
    cyl("neck", (0, 0.02, 1.79), 0.06, 0.1, "robot_joint", axis="Z", verts=12, parent=head)
    box("head_shell", (0, 0.04, 1.89), (0.24, 0.3, 0.16), "robot_bone", 0.03, parent=head)
    box("head_brow", (0, 0.15, 1.935), (0.25, 0.1, 0.05), "robot_paint", 0.015, rot=(12, 0, 0), parent=head)
    box("visor", (0, 0.19, 1.88), (0.2, 0.012, 0.05), "robot_dark", 0.004, parent=head)
    box("eye", (0, 0.197, 1.88), (0.15, 0.004, 0.014), "eye_glow", 0, parent=head)
    box("antenna", (0.09, -0.08, 1.99), (0.01, 0.01, 0.08), "robot_joint", 0.002, parent=head)
    for side in (-1, 1):
        box(f"ear_{side}", (side * 0.13, 0.02, 1.88), (0.03, 0.12, 0.1), "robot_dark", 0.01, parent=head)
    # Arms. Shoulder empties; upper arms hang, forearms point forward (+Y) at rest.
    for side, label in ((1, "R"), (-1, "L")):
        sh = empty(f"shoulder_{label}", (side * 0.36, 0, 1.62), torso)
        cyl(f"sh_joint_{label}", (side * 0.36, 0, 1.62), 0.085, 0.12, "robot_joint", axis="X", verts=16, parent=sh)
        box(f"pauldron_{label}", (side * 0.39, 0, 1.68), (0.17, 0.26, 0.12), "robot_paint", 0.03, rot=(0, side * -12, 0), parent=sh)
        box(f"upper_arm_{label}", (side * 0.39, 0, 1.46), (0.14, 0.15, 0.28), "robot_dark", 0.015, parent=sh)
        el = empty(f"elbow_{label}", (side * 0.38, 0, 1.32), sh)
        cyl(f"el_joint_{label}", (side * 0.38, 0, 1.32), 0.06, 0.12, "robot_joint", axis="X", verts=16, parent=el)
        if label == "R":
            # Arc projector arm.
            cyl("emitter_body", (side * 0.38, 0.2, 1.32), 0.075, 0.34, "robot_dark", verts=20, bevel=0.006, parent=el)
            box("emitter_top", (side * 0.38, 0.17, 1.4), (0.08, 0.26, 0.04), "robot_paint", 0.012, parent=el)
            for i in range(4):
                torus(f"em_coil{i}", (side * 0.38, 0.3 + i * 0.04, 1.32), 0.07, 0.012, "copper", parent=el)
            cyl("emitter_nozzle", (side * 0.38, 0.47, 1.32), 0.045, 0.06, "robot_joint", verts=16, r2=0.035, parent=el)
            cyl("arc_tip", (side * 0.38, 0.505, 1.32), 0.022, 0.02, "arc_tip", verts=12, bevel=0, parent=el)
            empty("muzzle", (side * 0.38, 0.53, 1.32), el)
        else:
            box("forearm_L", (side * 0.38, 0.14, 1.32), (0.1, 0.26, 0.11), "robot_dark", 0.015, parent=el)
            box("guard_L", (side * 0.43, 0.15, 1.33), (0.04, 0.3, 0.2), "robot_paint", 0.02, parent=el)
            for i, dx in enumerate((-0.03, 0.0, 0.03)):
                box(f"claw{i}", (side * 0.38 + dx, 0.3, 1.31), (0.02, 0.08, 0.03), "robot_joint", 0.006, rot=(-15, 0, 0), parent=el)
    # Legs: hip -> knee -> ankle.
    for side, label in ((1, "R"), (-1, "L")):
        hip = empty(f"hip_{label}", (side * 0.15, 0, 0.98), pelvis)
        cyl(f"hip_joint_{label}", (side * 0.15, 0, 0.98), 0.07, 0.12, "robot_joint", axis="X", verts=16, parent=hip)
        box(f"thigh_{label}", (side * 0.17, 0, 0.77), (0.18, 0.2, 0.38), "robot_dark", 0.02, parent=hip)
        box(f"thigh_plate_{label}", (side * 0.17, 0.1, 0.8), (0.17, 0.05, 0.3), "robot_paint", 0.015, parent=hip)
        knee = empty(f"knee_{label}", (side * 0.16, 0.0, 0.55), hip)
        cyl(f"knee_joint_{label}", (side * 0.16, 0, 0.55), 0.06, 0.13, "robot_joint", axis="X", verts=16, parent=knee)
        box(f"knee_cap_{label}", (side * 0.16, 0.09, 0.56), (0.16, 0.08, 0.15), "robot_paint", 0.02, parent=knee)
        box(f"shin_{label}", (side * 0.16, -0.01, 0.33), (0.16, 0.18, 0.4), "robot_dark", 0.02, parent=knee)
        cyl(f"piston_{label}", (side * 0.16, -0.11, 0.36), 0.02, 0.3, "steel", axis="Z", verts=12, parent=knee)
        box(f"shin_guard_{label}", (side * 0.16, 0.085, 0.36), (0.15, 0.04, 0.3), "robot_paint", 0.012, rot=(-6, 0, 0), parent=knee)
        ankle = empty(f"ankle_{label}", (side * 0.16, 0, 0.1), knee)
        box(f"foot_{label}", (side * 0.16, 0.05, 0.05), (0.2, 0.36, 0.1), "robot_dark", 0.02, parent=ankle)
        box(f"toe_{label}", (side * 0.16, 0.19, 0.04), (0.15, 0.06, 0.06), "robot_paint", 0.015, parent=ankle)
    export("teslabot.glb")


# ---------------------------------------------------------------- PROPS
def build_props():
    reset()
    # Steel equipment crate (1.2 x 0.8 x 0.8)
    c = empty("crate", (0, 0, 0))
    box("body", (0, 0, 0.4), (1.2, 0.8, 0.8), "crate_green", 0.02, parent=c)
    for x in (-0.5, 0.5):
        box(f"band{x}", (x, 0, 0.4), (0.06, 0.82, 0.82), "steel", 0.008, parent=c)
    box("lid_edge", (0, 0, 0.78), (1.22, 0.82, 0.04), "crate_green", 0.01, parent=c)
    box("stencil", (0, -0.401, 0.45), (0.5, 0.004, 0.12), "robot_bone", 0, parent=c)
    for x in (-0.25, 0.25):
        box(f"latch{x}", (x, -0.41, 0.7), (0.08, 0.02, 0.06), "steel", 0.004, parent=c)
    # Drum
    d = empty("barrel", (2, 0, 0))
    cyl("drum", (2, 0, 0.44), 0.29, 0.88, "painted_grey", axis="Z", verts=32, bevel=0.01, parent=d)
    for z in (0.02, 0.3, 0.6, 0.86):
        torus(f"rib{z}", (2, 0, z), 0.29, 0.012, "painted_grey", axis="Z", parent=d)
    box("hazard_band", (2, -0.29, 0.5), (0.2, 0.01, 0.12), "hazard", 0, parent=d)
    # Server rack (0.6 x 1.0 x 2.0)
    s = empty("server_rack", (4, 0, 0))
    box("frame", (4, 0, 1.0), (0.62, 1.0, 2.0), "robot_dark", 0.01, parent=s)
    box("front", (4, -0.505, 1.0), (0.56, 0.01, 1.9), "gunmetal", 0.004, parent=s)
    for i in range(14):
        z = 0.15 + i * 0.125
        box(f"unit{i}", (4, -0.512, z), (0.5, 0.008, 0.1), "anodized", 0.002, parent=s)
        box(f"led{i}", (4 + 0.2, -0.517, z + 0.02), (0.012, 0.004, 0.008), "led_amber" if i % 3 else "led_red", 0, parent=s)
    # Relay console (objective)
    k = empty("relay_console", (6, 0, 0))
    box("base", (6, 0, 0.45), (1.4, 0.7, 0.9), "painted_grey", 0.015, parent=k)
    box("console_desk", (6, -0.15, 0.95), (1.45, 0.6, 0.08), "robot_dark", 0.01, rot=(-15, 0, 0), parent=k)
    box("screen_frame", (6, 0.15, 1.35), (1.2, 0.08, 0.6), "robot_dark", 0.01, rot=(-10, 0, 0), parent=k)
    box("screen", (6, 0.105, 1.35), (1.1, 0.01, 0.5), "screen", 0, rot=(-10, 0, 0), parent=k)
    for i in range(10):
        box(f"key{i}", (6 - 0.45 + i * 0.1, -0.25, 1.0), (0.06, 0.06, 0.02), "led_amber" if i in (2, 7) else "anodized", 0.003, rot=(-15, 0, 0), parent=k)
    box("relay_tower", (6 + 0.6, 0.2, 1.2), (0.16, 0.16, 0.6), "robot_dark", 0.01, parent=k)
    for i in range(5):
        torus(f"relay_coil{i}", (6 + 0.6, 0.2, 1.55 + i * 0.05), 0.07, 0.012, "copper", axis="Z", parent=k)
    # Steel door slab: 1.0 x 0.07 x 2.1, hinge edge at x=0 (origin), opens about Z.
    door = empty("door_slab", (8, 0, 0))
    box("slab", (8.5, 0, 1.05), (0.98, 0.06, 2.08), "door_steel", 0.008, parent=door)
    box("frame_win", (8.5, 0, 1.55), (0.36, 0.07, 0.44), "gunmetal", 0.006, parent=door)
    box("window", (8.5, 0, 1.55), (0.3, 0.072, 0.38), "glass_lens", 0, parent=door)
    box("kick_plate", (8.5, 0, 0.15), (0.94, 0.066, 0.25), "steel", 0.004, parent=door)
    box("handle_f", (8.88, -0.06, 1.0), (0.14, 0.03, 0.03), "steel", 0.006, parent=door)
    box("handle_b", (8.88, 0.06, 1.0), (0.14, 0.03, 0.03), "steel", 0.006, parent=door)
    box("hazard_stripe", (8.5, -0.032, 1.95), (0.9, 0.004, 0.08), "hazard", 0, parent=door)
    # Caged bulkhead lamp
    l = empty("lamp", (10, 0, 0))
    box("plate", (10, 0, 0.02), (0.22, 0.22, 0.04), "robot_dark", 0.005, parent=l)
    cyl("globe", (10, 0, -0.06), 0.07, 0.12, "lamp_warm", axis="Z", verts=20, bevel=0, parent=l)
    for a in range(4):
        ang = a * math.pi / 2
        box(f"cage{a}", (10 + math.cos(ang) * 0.08, math.sin(ang) * 0.08, -0.06), (0.008, 0.008, 0.14), "robot_dark", 0, parent=l)
    torus("cage_ring", (10, 0, -0.12), 0.08, 0.005, "robot_dark", axis="Z", parent=l)
    # Jersey barrier (low cover, 2.0 long)
    j = empty("barrier", (12, 0, 0))
    box("base", (12, 0, 0.2), (2.0, 0.6, 0.4), "concrete", 0.02, parent=j)
    box("top", (12, 0, 0.7), (2.0, 0.22, 0.6), "concrete", 0.02, parent=j)
    box("hazard", (12, -0.112, 0.85), (1.9, 0.004, 0.1), "hazard", 0, parent=j)
    # Locker
    lk = empty("locker", (14, 0, 0))
    box("body", (14, 0, 0.95), (0.5, 0.5, 1.9), "painted_grey", 0.01, parent=lk)
    box("door", (14, -0.252, 0.95), (0.46, 0.01, 1.8), "painted_grey", 0.004, parent=lk)
    for i in range(5):
        box(f"vent{i}", (14, -0.258, 1.55 + i * 0.04), (0.3, 0.004, 0.012), "robot_dark", 0, parent=lk)
    # Desk
    dk = empty("desk", (16, 0, 0))
    box("top", (16, 0, 0.74), (1.6, 0.8, 0.04), "painted_grey", 0.006, parent=dk)
    for x in (-0.75, 0.75):
        box(f"leg{x}", (16 + x, 0, 0.36), (0.06, 0.74, 0.72), "robot_dark", 0.006, parent=dk)
    box("monitor", (16.2, 0.2, 1.0), (0.55, 0.04, 0.34), "robot_dark", 0.006, parent=dk)
    box("monitor_scr", (16.2, 0.178, 1.0), (0.5, 0.004, 0.29), "screen", 0, parent=dk)
    # Pipe run segment (4 m along Y)
    pp = empty("pipe", (18, 0, 0))
    cyl("pipe", (18, 0, 0), 0.1, 4.0, "painted_grey", verts=20, bevel=0, parent=pp)
    for y in (-1.5, 0, 1.5):
        cyl(f"flange{y}", (18, y, 0), 0.13, 0.05, "robot_dark", verts=20, parent=pp)
    # Breaker panel (wall-mounted power box; shootable to kill lights)
    bp = empty("breaker", (20, 0, 0))
    box("box", (20, 0, 0), (0.6, 0.2, 0.8), "painted_grey", 0.01, parent=bp)
    box("hazard", (20, -0.101, 0.3), (0.5, 0.004, 0.08), "hazard", 0, parent=bp)
    box("led", (20 + 0.2, -0.102, 0.2), (0.03, 0.004, 0.03), "led_amber", 0, parent=bp)
    export("props.glb")


build_rifle()
build_attachments()
build_pistol()
build_teslabot()
build_props()
print("ALL DONE")
