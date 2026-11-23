# M2 environment: fetch CC0 models and textures from Poly Haven's public API.
#   python -I tools/m2/fetch_polyhaven_m2.py [staging/env]
# Models -> <root>/polyhaven/<id>/ (glTF + its "include" files, relative paths kept)
# Textures -> <root>/textures/<id>/{albedo,normal,arm,rough,ao}.jpg (2k jpg)
# Writes <root>/polyhaven_manifest.json and <root>/SOURCES.md.
# Downloads are data only: nothing fetched here is ever executed.
import hashlib
import json
import os
import posixpath
import sys
import time
import urllib.request

API = "https://api.polyhaven.com"
UA = {"User-Agent": "asset-fetch/1.0"}
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "staging", "env"))

# id -> (texture resolution, suggested use)
MODELS = {
    "utility_box_01": ("1k", "single-door electrical distribution cabinet (corridors, turbine hall walls)"),
    "utility_box_02": ("2k", "double-door distribution cabinet; hero prop for the relay control room / turbine hall"),
    "power_box_01": ("2k", "open breaker board with exposed wiring; hero wall prop, can pair with the shootable breaker"),
    "modular_electric_cables": ("1k", "kit of wall cable runs, conduit and junction boxes"),
    "modular_industrial_pipes_01": ("2k", "pipe kit with elbows, tees and a valve wheel; hero pipe dressing"),
    "barrel_03": ("1k", "blue painted oil drum (loading dock, turbine hall clutter)"),
    "korean_fire_extinguisher_01": ("1k", "fire extinguisher on stand (note: Hangul label on the stand)"),
    "cardboard_box_01": ("1k", "taped cardboard box (storage, loading dock)"),
    "worn_metal_rack": ("1k", "worn steel shelving unit (storage, server room spares)"),
    "metal_tool_chest": ("1k", "red mechanic's tool chest (maintenance bay)"),
    "ladder_sectioned_01": ("1k", "aluminium sectioned ladder leaning on walls"),
    "industrial_wall_lamp": ("1k", "caged oval bulkhead wall lamp (corridors)"),
    "hanging_industrial_lamp": ("1k", "pendant reflector lamp (turbine hall, loading dock)"),
    "security_camera_02": ("1k", "CCTV camera on wall bracket (security coverage)"),
    "metal_office_desk": ("1k", "steel office desk (security office)"),
    "SchoolChair_01": ("1k", "steel-frame stacking chair (security office, break area)"),
    "hand_truck": ("1k", "sack truck / hand trolley (loading dock)"),
    "fire_alarm": ("1k", "fire alarm pull station (wall dressing by doors)"),
}

# id -> (intended use)
TEXTURES = {
    "concrete_wall_009": "clean light-grey formwork concrete panels with tie holes (main interior walls)",
    "concrete_wall_004": "painted concrete block wall (security office)",
    "rubber_tiles": "black rubber floor tiles (server room floor)",
    "painted_concrete_02": "grey painted / epoxy-coated industrial floor (control room, server room alternative)",
    "rusty_metal_sheet": "weathered bare / galvanised sheet steel (ducts, trays, cladding; closest Poly Haven has to galvanised flat sheet)",
    "container_side": "worn painted steel with fine scratches (robot paint; desaturate then tint in-engine)",
    "metal_plate_02": "dark worn steel plate with fine scratches (gunmetal / robot_dark)",
    "denim_fabric_05": "dark grey twill fabric (first-person sleeves)",
    "book_pattern": "olive woven cotton, canvas-like (webbing, pouches, alternative sleeve fabric)",
    "brown_leather": "matte creased leather (gloves)",
    "polystyrene": "white flat scuffed panel (ceiling tiles / acoustic panels)",
}

TEX_MAPS = {"Diffuse": "albedo.jpg", "nor_gl": "normal.jpg", "arm": "arm.jpg", "Rough": "rough.jpg", "AO": "ao.jpg"}


def get_json(path):
    req = urllib.request.Request(API + path, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_join(base, rel):
    rel = rel.replace("\\", "/")
    norm = posixpath.normpath(rel)
    if norm.startswith("/") or norm.startswith("..") or ":" in norm:
        raise ValueError("unsafe path in API listing: %r" % rel)
    out = os.path.abspath(os.path.join(base, *norm.split("/")))
    if not out.startswith(os.path.abspath(base) + os.sep):
        raise ValueError("path escapes asset dir: %r" % rel)
    return out


def download(url, dest, md5=None):
    if not url.startswith("https://dl.polyhaven.org/"):
        raise ValueError("unexpected download host: %s" % url)
    if os.path.exists(dest) and (md5 is None or md5_of(dest) == md5):
        return "cached"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(dest + ".part", dest)
            if md5 and md5_of(dest) != md5:
                raise IOError("md5 mismatch for %s" % url)
            return "ok"
        except Exception as e:  # retry transient failures
            print("  retry", attempt + 1, url, e)
            time.sleep(2)
    raise IOError("failed: %s" % url)


def fetch_models(manifest):
    base = os.path.join(ROOT, "polyhaven")
    for mid, (res, use) in MODELS.items():
        info = get_json("/info/" + mid)
        files = get_json("/files/" + mid)
        entry = files["gltf"][res]["gltf"]
        d = os.path.join(base, mid)
        os.makedirs(d, exist_ok=True)
        got = []
        main_name = posixpath.basename(entry["url"])
        download(entry["url"], safe_join(d, main_name), entry.get("md5"))
        got.append({"file": main_name, "url": entry["url"], "size": entry.get("size")})
        for rel, inc in sorted(entry.get("include", {}).items()):
            download(inc["url"], safe_join(d, rel), inc.get("md5"))
            got.append({"file": rel, "url": inc["url"], "size": inc.get("size")})
        manifest["models"][mid] = {
            "name": info.get("name"), "authors": info.get("authors", {}), "resolution": res, "use": use,
            "page": "https://polyhaven.com/a/" + mid, "files": got,
            "api_dimensions_mm": info.get("dimensions"), "api_polycount": info.get("polycount"),
        }
        print("model", mid, res, len(got), "files")


def fetch_textures(manifest):
    base = os.path.join(ROOT, "textures")
    for tid, use in TEXTURES.items():
        info = get_json("/info/" + tid)
        files = get_json("/files/" + tid)
        d = os.path.join(base, tid)
        os.makedirs(d, exist_ok=True)
        got = []
        for key, fname in TEX_MAPS.items():
            # Some fabrics ship colour variants (col1, col2, ...) instead of a single Diffuse map.
            if key == "Diffuse" and key not in files:
                key = next((k for k in sorted(files) if k.startswith("col")), key)
            if key not in files or "2k" not in files[key] or "jpg" not in files[key]["2k"]:
                print("  missing map", tid, key)
                continue
            e = files[key]["2k"]["jpg"]
            download(e["url"], os.path.join(d, fname), e.get("md5"))
            got.append({"file": fname, "url": e["url"], "size": e.get("size")})
        manifest["textures"][tid] = {
            "name": info.get("name"), "authors": info.get("authors", {}), "use": use,
            "page": "https://polyhaven.com/a/" + tid, "files": got,
            "api_dimensions_mm": info.get("dimensions"),
        }
        print("texture", tid, len(got), "maps")


def authors_str(a):
    return ", ".join("%s (%s)" % (k, v) for k, v in a.items()) if a else "n/a"


def write_sources(manifest):
    stats = {}
    sp = os.path.join(ROOT, "polyhaven", "stats.json")  # written by `env_kit.py -- convert`
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            stats = json.load(f)
    L = ["# M2 environment sources", "",
         "All downloaded assets below come from [Poly Haven](https://polyhaven.com) via its public API",
         "(`https://api.polyhaven.com`) and are licensed **CC0 1.0** (public domain). Fetched by",
         "`tools/m2/fetch_polyhaven_m2.py`. First-party meshes (`env_kit.glb`, `props.glb`) are generated by",
         "`tools/m2/env_kit.py` and are project-owned.", "",
         "## Models (`polyhaven/<id>/`)", ""]
    for mid, m in manifest["models"].items():
        L.append("### %s (`%s`)" % (m["name"], mid))
        L.append("- URL: %s" % m["page"])
        L.append("- License: CC0 1.0")
        L.append("- Author: %s" % authors_str(m["authors"]))
        L.append("- Textures: %s; converted to `polyhaven/%s/%s.glb` (textures embedded)" % (m["resolution"], mid, mid))
        s = stats.get(mid)
        if s:
            L.append("- Measured in Blender: %.3f x %.3f x %.3f m (X x Y x Z, Z up), %d triangles" % (tuple(s["size"]) + (s["tris"],)))
        L.append("- Files:")
        for f in m["files"]:
            L.append("  - `%s` <- %s" % (f["file"], f["url"]))
        L.append("")
    L += ["## Textures (`textures/<id>/`, 2k jpg)", "",
          "Map naming: Diffuse -> albedo.jpg, nor_gl -> normal.jpg (OpenGL), arm -> arm.jpg (AO/Rough/Metal), Rough -> rough.jpg, AO -> ao.jpg.", ""]
    for tid, t in manifest["textures"].items():
        L.append("### %s (`%s`)" % (t["name"], tid))
        L.append("- URL: %s" % t["page"])
        L.append("- License: CC0 1.0")
        L.append("- Author: %s" % authors_str(t["authors"]))
        L.append("- Use: %s" % t["use"])
        L.append("- Files:")
        for f in t["files"]:
            L.append("  - `%s` <- %s" % (f["file"], f["url"]))
        L.append("")
    with open(os.path.join(ROOT, "SOURCES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    os.makedirs(ROOT, exist_ok=True)
    manifest = {"source": "Poly Haven (https://polyhaven.com)", "license": "CC0 1.0", "models": {}, "textures": {}}
    fetch_models(manifest)
    fetch_textures(manifest)
    with open(os.path.join(ROOT, "polyhaven_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    write_sources(manifest)
    print("DONE", ROOT)


if __name__ == "__main__":
    main()
