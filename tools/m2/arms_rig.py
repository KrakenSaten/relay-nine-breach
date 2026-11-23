# BREACH M3: skinned first-person arm rig "FPArms" + finger pose library. Run headless:
#   blender -b --factory-startup -P tools/m2/arms_rig.py -- C:/AAA/Breach/staging/arms_rig
# Optional: --previews all|none|rest,poses,deform,fp,fp_handguard,fp_vgrip,fp_mag,fp_pistol
# Reads (never writes) the M2 weapons in staging/weapons for the first-person composites.
# Modules: arms_rig_build (layout, weighted mesh, armature), arms_rig_poses (grasp-solved pose library),
#          arms_rig_preview (two-bone solve + renders). Reuses wpn_* M2 modules read-only.
import sys, os, time, json, math, struct

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
from mathutils import Vector, Matrix, Quaternion
import wpn_lib as L
import arms_rig_build as B
import arms_rig_poses as RP

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(HERE, "..", "..", "staging", "arms_rig"))
PREVIEWS = "all"
for i, a in enumerate(argv):
    if a == "--previews":
        PREVIEWS = argv[i + 1]
os.makedirs(OUT, exist_ok=True)
GLB = os.path.join(OUT, "arms_rig.glb")
t0 = time.time()

# ---------------------------------------------------------------- mesh
L.reset()
gR = B.Groups("R")
parts, lay, info = B.build_arm_right(gR)
watch = B.build_watch_right(parts[0], lay, gR)
right = L.join(parts, "arm_R")
left = right.copy()
left.data = right.data.copy()
L.link(left)
left = L.join([left] + watch, "arm_L")
left.data.transform(L.MIRROR_X)
left.data.flip_normals()
left.data.update()
for g in left.vertex_groups:
    if g.name.endswith("_R"):
        g.name = g.name[:-2] + "_L"
mesh = L.join([right, left], "FPArms_mesh")
L.smooth_all(mesh)
for p in mesh.data.polygons:
    pass
L.smart_uv([mesh])

# ---------------------------------------------------------------- armature + skin
arm, frames = B.build_armature("FPArms")
mesh.parent = arm
md = mesh.modifiers.new("Armature", "ARMATURE")
md.object = arm
md.use_vertex_groups = True
missing = [g.name for g in mesh.vertex_groups if g.name not in arm.data.bones]
unused = [b.name for b in arm.data.bones if b.name not in mesh.vertex_groups]
# normalise weights (max 4 influences, sum 1) for a clean glTF skin
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh.data)
dl = bm.verts.layers.deform.verify()
maxinf = 0
for v in bm.verts:
    items = sorted(v[dl].items(), key=lambda kv: -kv[1])[:4]
    tot = sum(w for _, w in items) or 1.0
    v[dl].clear()
    for gi, w in items:
        if w / tot > 0.002:
            v[dl][gi] = w / tot
    maxinf = max(maxinf, len(items))
bm.to_mesh(mesh.data)
bm.free()
tris = L.tris(mesh)
print("[tris] FPArms_mesh", tris, "groups missing bones:", missing, "bones without weights:", unused)

# ---------------------------------------------------------------- actions (one key each, finger bones only)
arm.animation_data_create()
for name in RP.POSE_ORDER:
    side, pose = RP.pose_defs()[name]
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data.action = act
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion()
    for bn, q in RP.side_quats(side, pose).items():
        pb = arm.pose.bones[bn]
        pb.rotation_quaternion = q
        pb.keyframe_insert("rotation_quaternion", frame=0, group=bn)
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_quaternion = Quaternion()
bpy.context.view_layer.update()

# ---------------------------------------------------------------- export
for o in bpy.context.view_layer.objects:
    o.select_set(False)
bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", export_yup=True, export_apply=False,
                          export_skins=True, export_animations=True, export_animation_mode="ACTIONS",
                          export_force_sampling=False, export_optimize_animation_size=False,
                          export_optimize_animation_keep_anim_armature=False, export_reset_pose_bones=True,
                          export_rest_position_armature=True, export_def_bones=False, export_anim_slide_to_zero=False)
print("exported", GLB)


# ---------------------------------------------------------------- deterministic animation block
def canonical_animations(js, binc):
    """The exporter emits channels in hash-dependent order. Rebuild all animation accessors/bufferViews at the end
    of the buffer, animations sorted by name and channels by (bone, path), so reruns are byte-identical."""
    import numpy as np
    anims = js.get("animations", [])
    if not anims:
        return binc
    acc_ids = sorted({s[k] for a in anims for s in a["samplers"] for k in ("input", "output")})
    first_acc = acc_ids[0]
    assert acc_ids == list(range(first_acc, len(js["accessors"]))), "animation accessors are not trailing"
    bv_ids = sorted({js["accessors"][i]["bufferView"] for i in acc_ids})
    first_bv = bv_ids[0]
    assert bv_ids == list(range(first_bv, len(js["bufferViews"]))), "animation bufferViews are not trailing"
    cut = min(js["bufferViews"][i].get("byteOffset", 0) for i in bv_ids)
    ncomp = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}

    def read(ai):
        a = js["accessors"][ai]
        bv = js["bufferViews"][a["bufferView"]]
        st = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        n = a["count"] * ncomp[a["type"]]
        return a["type"], np.frombuffer(bytes(binc[st:st + n * 4]), dtype="<f4").copy()
    nodes = js["nodes"]
    items = []
    for a in anims:
        chans = []
        for ch in a["channels"]:
            s = a["samplers"][ch["sampler"]]
            chans.append((nodes[ch["target"]["node"]]["name"], ch["target"]["path"], ch["target"]["node"],
                          read(s["input"]), read(s["output"]), s.get("interpolation", "LINEAR")))
        chans.sort(key=lambda c: (c[0], c[1]))
        items.append((a["name"], chans))
    items.sort(key=lambda it: it[0])
    js["accessors"] = js["accessors"][:first_acc]
    js["bufferViews"] = js["bufferViews"][:first_bv]
    out = bytearray(binc[:cut])

    def put(typ, arr, with_minmax):
        while len(out) % 4:
            out.append(0)
        off = len(out)
        out.extend(arr.astype("<f4").tobytes())
        js["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": arr.size * 4})
        acc = {"bufferView": len(js["bufferViews"]) - 1, "componentType": 5126, "count": arr.size // ncomp[typ], "type": typ}
        if with_minmax:
            acc["min"] = [float(arr.min())]
            acc["max"] = [float(arr.max())]
        js["accessors"].append(acc)
        return len(js["accessors"]) - 1
    new = []
    for name, chans in items:
        samplers, channels = [], []
        for bone, path, node, (ti, tv), (vt, vv), interp in chans:
            ia = put(ti, tv, True)
            oa = put(vt, vv, False)
            samplers.append({"input": ia, "output": oa, "interpolation": interp})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})
        new.append({"name": name, "channels": channels, "samplers": samplers})
    js["animations"] = new
    while len(out) % 4:
        out.append(0)
    js["buffers"][0]["byteLength"] = len(out)
    return out


# ---------------------------------------------------------------- joint convention fix
def fix_joint_convention(path):
    """The exporter keeps bone axis labels (joint global = C*R), but every M2 object/socket node is C*R*C^-1.
    Re-express every joint as G' = G*C^-1 so 'hand bone global := socket global' is exact in Godot.
    Children locals become C*L*C^-1, inverse binds C*IBM, animated rotations C*q*C^-1. Rest skin is unchanged."""
    import numpy as np
    d = open(path, "rb").read()
    jl = struct.unpack_from("<I", d, 12)[0]
    js = json.loads(d[20:20 + jl])
    off = 20 + jl
    bl, btype = struct.unpack_from("<II", d, off)
    binc = bytearray(d[off + 8: off + 8 + bl])
    nodes = js["nodes"]
    skin = js["skins"][0]
    joints = set(skin["joints"])
    qC = Quaternion(Vector((1, 0, 0)), math.radians(-90.0))          # C = Rx(-90): (x, y, z) -> (x, z, -y)
    qCi = qC.inverted()
    Cm = qC.to_matrix()
    par = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            par[c] = i
    for j in joints:
        n = nodes[j]
        r = n.get("rotation", [0, 0, 0, 1])
        q = Quaternion((r[3], r[0], r[1], r[2]))
        t = Vector(n.get("translation", [0, 0, 0]))
        if par.get(j) in joints:
            q2 = qC @ q @ qCi
            t2 = Cm @ t
        else:
            q2 = q @ qCi
            t2 = t
        n["rotation"] = [q2.x, q2.y, q2.z, q2.w]
        n["translation"] = [t2.x, t2.y, t2.z]

    def acc_view(ai):
        a = js["accessors"][ai]
        bv = js["bufferViews"][a["bufferView"]]
        assert a["componentType"] == 5126
        start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        ncomp = {"SCALAR": 1, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
        return start, a["count"], ncomp
    start, cnt, nc = acc_view(skin["inverseBindMatrices"])
    arr = np.frombuffer(bytes(binc[start:start + cnt * nc * 4]), dtype="<f4").reshape(cnt, 4, 4).copy()
    C4 = np.eye(4, dtype=np.float64)
    C4[:3, :3] = np.array(Cm)
    for k in range(cnt):
        M = arr[k].T.astype(np.float64)           # column-major -> row-major
        arr[k] = (C4 @ M).T.astype("<f4")
    binc[start:start + cnt * nc * 4] = arr.astype("<f4").tobytes()
    done = set()
    for a in js.get("animations", []):
        for ch in a["channels"]:
            if ch["target"]["path"] not in ("rotation", "translation"):
                continue
            node = ch["target"]["node"]
            smp = a["samplers"][ch["sampler"]]
            key = (smp["output"], ch["target"]["path"])
            if key in done:
                continue
            done.add(key)
            start, cnt, nc = acc_view(smp["output"])
            vals = np.frombuffer(bytes(binc[start:start + cnt * nc * 4]), dtype="<f4").reshape(cnt, nc).copy()
            for k in range(cnt):
                if ch["target"]["path"] == "rotation":
                    q = Quaternion((vals[k][3], vals[k][0], vals[k][1], vals[k][2]))
                    q = (qC @ q @ qCi) if par.get(node) in joints else (q @ qCi)
                    vals[k] = [q.x, q.y, q.z, q.w]
                elif par.get(node) in joints:
                    vals[k] = list(Cm @ Vector(vals[k]))
            binc[start:start + cnt * nc * 4] = vals.astype("<f4").tobytes()
    binc = canonical_animations(js, binc)
    raw = json.dumps(js, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    body = struct.pack("<II", len(raw), 0x4E4F534A) + raw + struct.pack("<II", len(binc), btype) + bytes(binc)
    open(path, "wb").write(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)


fix_joint_convention(GLB)


# ---------------------------------------------------------------- verify the GLB
def load_glb(p):
    d = open(p, "rb").read()
    jl = struct.unpack_from("<I", d, 12)[0]
    js = json.loads(d[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack_from("<I", d, off)[0]
    return js, d[off + 8: off + 8 + bl]


def node_mat(n):
    if "matrix" in n:
        m = n["matrix"]
        return Matrix([m[0:4], m[4:8], m[8:12], m[12:16]]).transposed()
    t = n.get("translation", [0, 0, 0])
    r = n.get("rotation", [0, 0, 0, 1])
    s = n.get("scale", [1, 1, 1])
    return Matrix.Translation(t) @ Quaternion((r[3], r[0], r[1], r[2])).to_matrix().to_4x4() @ Matrix.Diagonal((s[0], s[1], s[2], 1))


js, binchunk = load_glb(GLB)
nodes = js["nodes"]
parent = {}
for i, n in enumerate(nodes):
    for c in n.get("children", []):
        parent[c] = i


def gmat(i):
    M = node_mat(nodes[i])
    while i in parent:
        i = parent[i]
        M = node_mat(nodes[i]) @ M
    return M


C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))     # Blender -> glTF (Y up)
names = {n.get("name"): i for i, n in enumerate(nodes)}
frame_dev_gltf = {}
for side in ("R", "L"):
    want = C @ (arm.matrix_world @ B.mat4(frames["hand_" + side][1], frames["hand_" + side][0])) @ C.inverted()
    got = gmat(names["hand_" + side])
    frame_dev_gltf[side] = max(abs(got[r][c] - want[r][c]) for r in range(4) for c in range(4))
# end-to-end: put hand_R's joint at the rifle's sock_hand_R (as Godot would) and compare skinned hand points
# with where the M2 hand_R mesh would be (sock global * C * q for hand-space points q)
rj, _ = load_glb(os.path.join("C:/AAA/Breach/staging/weapons", "rifle.glb"))
rnodes = rj["nodes"]
rpar = {}
for i, n in enumerate(rnodes):
    for c in n.get("children", []):
        rpar[c] = i


def rgmat(i):
    M = node_mat(rnodes[i])
    while i in rpar:
        i = rpar[i]
        M = node_mat(rnodes[i]) @ M
    return M


Gs = rgmat([i for i, n in enumerate(rnodes) if n.get("name") == "sock_hand_R"][0])
Gr = gmat(names["hand_R"])
Hb = arm.matrix_world @ B.mat4(frames["hand_R"][1], frames["hand_R"][0])
socket_dev = 0.0
for qh in (Vector((0, 0, 0)), Vector((-0.0314, 0.0935, 0.0006)), Vector((0.029, 0.085, 0.0)), Vector((0.0, 0.05, 0.013))):
    v_rest = C @ (Hb @ qh)                                   # glTF rest vertex
    v_new = Gs @ Gr.inverted() @ v_rest                       # skinned with joint := socket
    v_m2 = Gs @ (C @ qh)                                      # M2 hand mesh vertex at the socket
    socket_dev = max(socket_dev, (v_new - v_m2).length)
frame_dev_gltf["socket_roundtrip_m"] = socket_dev
anims = {}
for a in js.get("animations", []):
    tgt = sorted({nodes[ch["target"]["node"]]["name"] + "." + ch["target"]["path"] for ch in a["channels"]})
    anims[a["name"]] = tgt
skin = js["skins"][0]
joint_names = [nodes[j]["name"] for j in skin["joints"]]
suffixed = [n for n in joint_names if "." in n]
print("glTF hand frame deviation (max abs matrix element):", frame_dev_gltf)
print("animations:", {k: len(v) for k, v in anims.items()})

# ---------------------------------------------------------------- optional socket recommendation
# The approved M2 vertical-grip hand frame (delta 38 deg) points the left hand forward-LEFT, which costs 75-100 deg of
# wrist deviation for an arm coming from the left shoulder. A delta of 0 (palm flat on the grip's left side) keeps the
# same fist and contact but cuts that to ~40 deg. Not applied (M2 files untouched); offered as data.
import wpn_poses as WP
import wpn_specs as WS
_vg = WP.socket_matrix(WP.vgrip_frame(0.0), WP.hand_fist_def()["Fh"], True)


def _mout(M):
    q = M.to_quaternion()
    return {"pos": [round(x, 5) for x in M.translation], "quat_wxyz": [round(x, 5) for x in q]}


REC = {"grip_vertical.hand_L (grip space, delta=0)": _mout(_vg),
       "sock_hand_L_vgrip (rifle space, delta=0)": _mout(Matrix.Translation(WS.SOCK_GRIP) @ _vg)}

# ---------------------------------------------------------------- bone documentation
doc, blender_dev = B.bone_doc(arm, frames)
pose_info = {}
for name in RP.POSE_ORDER:
    side, pose = RP.pose_defs()[name]
    pose_info[name] = {"side": side,
                       "fingers_splay_flex_deg": {k: [round(math.degrees(v[0]), 2), [round(math.degrees(f), 1) for f in v[1]]]
                                                  for k, v in pose["fingers"].items()},
                       "thumb_psi_phi_rho_mcp_ip_deg": [round(math.degrees(x), 1) for x in pose["thumb"]],
                       "glTF_channels": anims.get(name, [])}
notes = {
    "armature": "FPArms (one armature, both arms). Armature space = first-person camera space: origin at the eye, "
                "Blender +Y forward, +Z up (Godot: x, y=z, z=-y).",
    "hand_frame_contract": "hand_X rest: head at the wrist, +Y along the fingers, +Z back of the hand, palm toward -Z "
                           "(X = Y x Z: little-finger side on hand_R, thumb side on hand_L) == M2 hand mesh frame. "
                           "Set the hand bone global transform to sock_hand_R / sock_hand_L / sock_hand_L_vgrip / "
                           "sock_hand_L_agrip / sock_hand_L_mag or an attachment's hand_L empty, no offset.",
    "hand_frame_max_deviation": {"blender_bone_vs_design": blender_dev, "gltf_joint_vs_expected": frame_dev_gltf},
    "conventions": {
        "elbow": "upperarm/forearm hinge = local +X on both bones; elbow FLEXION = +rotation of forearm_X about its local +X "
                 "(both sides). Rest elbow bend %.1f deg." % math.degrees(B.D_UPPER.angle(B.D_FORE)),
        "fingers": "finger/thumb bones: +Y along the phalanx, +Z dorsal (nail side); FLEXION (curl) = -rotation about local +X "
                   "on both sides; abduction = rotation about local +Z.",
        "twist": "forearm_twist_X sits at 60% of the forearm (child of forearm_X, same axes). Drive it with ~0.75x the hand's "
                 "roll about the forearm's +Y relative to the rest roll (forearm_twist local rotation about +Y); hand_X is a "
                 "child of forearm_X (not of the twist bone). Skin weights hand over forearm->twist between 5 and 20 cm from "
                 "the elbow and twist->hand across the wrist (22.4-27.2 cm), so up to ~+-120 deg of roll stays clean.",
        "ik": "two-bone solve: shoulder = clavicle tail, upperarm 0.30, forearm 0.26; choose the elbow on the IK circle to "
              "hang below the shoulder and to minimise wrist deviation/twist (see tools/m2/arms_rig_preview.solve_arm).",
        "clavicle": "root-level per side; tail = shoulder joint. Translate it (e.g. forward) when a socket is beyond reach "
                    "(upperarm 0.30 + forearm 0.26).",
        "left_side": "exact mirror of the right: positions x -> -x; each bone keeps a right-handed frame with the same "
                     "+Y/+Z meaning, so +X is lateral on the right arm and medial on the left arm.",
        "actions": "one keyframe (frame 0) per action, rotation channels on that side's finger and thumb bones only; "
                   "apply on top of any arm pose."},
    "recommended_socket_overrides": REC,
    "reach_note": "With the game's rifle hip_pos (0.2, -0.21, -0.43) the support-hand socket is ~0.73 m from the eye and "
                  "out of reach of a 0.56 m arm from a shoulder at (+-0.19, -0.05, -0.21); the previews therefore use a "
                  "shouldered low-ready eye at rifle-space (-0.19, -0.23, 0.18). At hip_pos the left clavicle would need "
                  "~0.3 m of forward protraction (or bring the weapon ~0.2 m closer).",
    "triangles": tris, "max_influences": maxinf, "skin_joints": len(joint_names), "suffixed_joint_names": suffixed,
    "bones": doc, "poses": pose_info,
}
with open(os.path.join(OUT, "arms_rig_bones.json"), "w") as fh:
    json.dump(notes, fh, indent=1)
print("blender hand frame deviation:", blender_dev)
print("build+export %.1fs" % (time.time() - t0))

# ---------------------------------------------------------------- previews
if PREVIEWS != "none":
    import arms_rig_preview as PV
    stats = PV.run_all(arm, mesh, os.path.join(OUT, "previews"), PREVIEWS)
    for k, v in stats.items():
        print("solve", k, {s: {kk: round(vv, 4) for kk, vv in d.items()} for s, d in v.items()})
print("ALL DONE %.1fs" % (time.time() - t0))
