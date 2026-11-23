# BREACH M2 weapon + first-person arm generator (original, procedural). Run headless:
#   blender -b --factory-startup -P tools/m2/weapons.py -- C:/AAA/Breach/staging/weapons
# Optional flags after the output dir:
#   --only rifle,attachments,pistol,arms   build a subset
#   --previews all|none|name1,name2         which preview renders to make (default all)
# Deterministic: no randomness; re-running overwrites the same files (byte-identical .glb).
# Modules (all in tools/m2, prefixed wpn_ to stay clear of other generators in this folder):
#   wpn_lib (materials, bmesh builders, booleans, bevel/weighted normals, UVs, export, glTF name fix)
#   wpn_parts (Picatinny, screws, QD cups, knurl)   wpn_specs (shared grip/handguard/mag dimensions)
#   wpn_rifle / wpn_attachments / wpn_pistol / wpn_arms (assets)
#   wpn_hands (subdivision-cage gloved hand + grasp-closing finger solver)
#   wpn_poses (hand poses vs virtual grips -> hand sockets; m2_rig_notes.json)
#   wpn_render / wpn_previews (studio lighting, re-imports the .glb files for validation renders)
import sys, os, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy
import wpn_lib as L

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv and not argv[0].startswith("--") else os.path.join(HERE, "..", "..", "staging", "weapons"))
ONLY = None
PREVIEWS = "all"
for i, a in enumerate(argv):
    if a == "--only":
        ONLY = set(argv[i + 1].split(","))
    if a == "--previews":
        PREVIEWS = argv[i + 1]
os.makedirs(OUT, exist_ok=True)
PREV = os.path.join(OUT, "previews")

STATS = {}


def want(name):
    return ONLY is None or name in ONLY


def finalize_and_export(fname, root_objs, fix_names=()):
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    L.smart_uv(meshes)
    total = 0
    per = {}
    for o in meshes:
        t = L.tris(o)
        total += t
        per[o.name] = t
    roots = {}
    for o in meshes:
        r = o
        while r.parent is not None:
            r = r.parent
        roots[r.name] = roots.get(r.name, 0) + per[o.name]
    STATS[fname] = (total, per, roots)
    L.export_glb(os.path.join(OUT, fname), fix_names)
    print(f"[tris] {fname}: {total}")
    for k, v in sorted(per.items(), key=lambda kv: -kv[1]):
        print(f"    {k:28s} {v}")


def build_rifle():
    import wpn_rifle as R
    import wpn_poses as poses
    L.reset()
    root, objs = R.build(poses.rifle_hand_sockets())
    finalize_and_export("rifle.glb", objs)


def build_attachments():
    import wpn_attachments as A
    L.reset()
    A.build()
    finalize_and_export("attachments.glb", None, fix_names=("eye", "hand_L", "lens", "obj_glass"))


def build_pistol():
    import wpn_pistol as P
    L.reset()
    P.build()
    finalize_and_export("pistol.glb", None)


def build_arms():
    import wpn_arms as AR
    L.reset()
    AR.build()
    finalize_and_export("arms.glb", None)


t0 = time.time()
if want("rifle"):
    build_rifle()
if want("attachments"):
    build_attachments()
if want("pistol"):
    build_pistol()
if want("arms"):
    build_arms()
if ONLY is None:
    import json, wpn_poses as poses
    with open(os.path.join(OUT, "m2_rig_notes.json"), "w") as fh:
        json.dump(poses.rig_notes(), fh, indent=1)
print("build time %.1fs" % (time.time() - t0))

if PREVIEWS != "none":
    import wpn_previews as previews
    previews.run(OUT, PREV, PREVIEWS)

print("=== TRIANGLES ===")
for k, (t, per, roots) in STATS.items():
    print(f"{k}: {t}")
    for r, n in sorted(roots.items()):
        print(f"    root {r:16s} {n}")
if L.BOOL_LOG:
    print("boolean fallbacks:", L.BOOL_LOG)
print("ALL DONE %.1fs" % (time.time() - t0))
