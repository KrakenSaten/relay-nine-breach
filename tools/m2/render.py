# Preview rendering: neutral studio (three-point + soft environment), glb re-import helpers.
import bpy, math, os
from mathutils import Vector, Matrix
from m2lib import reset, V


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    return new


def find(objs, name):
    """Exact name first, then Blender-suffixed duplicates (name.001)."""
    for o in objs:
        if o.name == name:
            return o
    for o in objs:
        if o.name.split(".")[0] == name:
            return o
    return None


def child(obj, prefix):
    for c in obj.children_recursive:
        if c.name.split(".")[0] == prefix:
            return c
    return None


def attach(att, sock):
    """Parent an attachment empty to a socket with an identity transform (what the game does)."""
    att.parent = sock
    att.matrix_parent_inverse = Matrix.Identity(4)
    att.matrix_basis = Matrix.Identity(4)


def remove_tree(o):
    for c in list(o.children_recursive) + [o]:
        bpy.data.objects.remove(c, do_unlink=True)


def studio(res=(1600, 900), samples=48, bg=0.16):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    try:
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_shadows = True
        sc.eevee.use_raytracing = False
    except Exception:
        pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    w = bpy.data.worlds.new("studio")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bgn = nt.nodes.get("Background")
    # soft vertical gradient environment
    tex = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (bg * 0.55, bg * 0.56, bg * 0.6, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (bg * 1.6, bg * 1.6, bg * 1.65, 1)
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = -1.0
    mapr.inputs["From Max"].default_value = 1.0
    nt.links.new(tex.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
    nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bgn.inputs["Color"])
    bgn.inputs["Strength"].default_value = 1.0


def light(name, loc, target, energy, size=0.6, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = V(loc)
    d = V(target) - V(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return o


def three_point(center, cam_loc, scale=1.0):
    """Key from camera-left/above, fill from camera-right/below, rim from behind."""
    c = V(center)
    fwd = (c - V(cam_loc)).normalized()
    up = V((0, 0, 1))
    right = fwd.cross(up).normalized()
    up2 = right.cross(fwd).normalized()
    d = 1.4 * scale
    light("key", c - fwd * d * 0.8 - right * d * 0.7 + up2 * d * 0.8, c, 55 * scale * scale, 1.2 * scale, (1.0, 0.97, 0.92))
    light("fill", c - fwd * d * 0.9 + right * d * 0.9 - up2 * d * 0.15, c, 16 * scale * scale, 1.6 * scale, (0.9, 0.95, 1.0))
    light("rim", c + fwd * d * 0.9 + up2 * d * 0.9 - right * d * 0.2, c, 60 * scale * scale, 0.8 * scale, (1.0, 1.0, 1.0))
    light("top", c + up * d * 1.2, c, 14 * scale * scale, 2.4 * scale)


def camera(loc, target, lens=50.0, ortho=None, sensor=36.0, up=(0, 0, 1)):
    cd = bpy.data.cameras.new("cam")
    o = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = V(loc)
    d = V(target) - V(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cd.clip_start = 0.005
    cd.clip_end = 50
    cd.sensor_width = sensor
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    bpy.context.scene.camera = o
    return o


def fp_camera(loc, fwd, up, hfov_deg=90.0):
    cd = bpy.data.cameras.new("fpcam")
    o = bpy.data.objects.new("fpcam", cd)
    bpy.context.scene.collection.objects.link(o)
    f = V(fwd).normalized()
    u = V(up)
    r = f.cross(u).normalized()
    u = r.cross(f).normalized()
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = r[i], u[i], -f[i], loc[i]
    o.matrix_world = M
    cd.sensor_fit = "HORIZONTAL"
    cd.angle = math.radians(hfov_deg)
    cd.clip_start = 0.01
    bpy.context.scene.camera = o
    return o


def render(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("rendered", path)
