# Fetch CC0 / public-domain source recordings for the BREACH audio upgrade.
#
#   python -I tools/m2/audio_fetch.py            # fetch everything in SOURCES
#   python -I tools/m2/audio_fetch.py id1 id2    # fetch selected items
#
# Every item is downloaded into its own directory staging/audio/raw/<id>/.
# Before downloading, the asset's own page is fetched and its licence field is
# parsed; an item is refused unless that field lists CC0 (OpenGameArt) or
# CC0 / Public domain (Wikimedia Commons).  Archives are extracted into
# raw/<id>/x/ (zip via zipfile with path checks, 7z via bsdtar).  Downloads are
# treated as data only: nothing inside them is ever executed or imported.
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RAW = os.path.join(ROOT, "staging", "audio", "raw")
UA = {"User-Agent": "asset-fetch/1.0"}
BSDTAR = r"C:\Windows\System32\tar.exe"
OGA = "https://opengameart.org/content/"
F = "https://opengameart.org/sites/default/files/"

# id -> (asset page, [file urls])
SOURCES = {
    "oga_free_firearm_sound_library": (OGA + "the-free-firearm-sound-library", [F + "Prepared%20SFX%20Library.7z"]),
    "oga_handgun_reload_zer0sol": (OGA + "handgun-reload-sound-effect", [F + "reload.wav"]),
    "oga_shotgun_reload_zer0sol": (OGA + "shotgun-reload-sound-effects", [F + "shotgunsounds.zip"]),
    "oga_gun_reload_springyspringo": (OGA + "gun-reload-sounds", [F + "gunreload1.wav", F + "assaultriflereload1_0.wav", F + "shotguncock_0.wav"]),
    "oga_gun_reload_bmaczero": (OGA + "gun-reload-sound-effects", [F + "clipload2.wav", F + "clipload1.wav", F + "singlebullet1.wav"]),
    "oga_equipment_clicks_ii_lfa": (OGA + "equipment-clicks-ii", [F + "equipmentclicks.wav"]),
    "oga_equipment_click_lfa": (OGA + "equipment-click", [F + "equipmentclick.wav"]),
    "oga_10_clicks_switches": (OGA + "10-clicks-and-switches", [F + "10_clicks_and_switches.zip"]),
    "oga_metal_impact_bmaczero": (OGA + "metal-impact-sounds", [F + n for n in ["bing1.wav", "bong1.wav", "clink1_0.wav", "clink2.wav", "clink3.wav", "thud2.wav", "thud3.wav"]]),
    "oga_mechanical_bmaczero": (OGA + "mechanical-sounds", [F + n for n in ["clank1.wav", "lightclunk1.wav", "lightclunk2.wav", "rattle1.wav", "squeakyclick1.wav", "squeakyclick2.wav", "mechanical1.wav", "mechanical2.wav"]]),
    "oga_100_metal_wood_rubberduck": (OGA + "100-cc0-metal-and-wood-sfx", [F + "100-CC0-wood-metal-SFX.zip"]),
    "oga_100_sfx_rubberduck": (OGA + "100-cc0-sfx", [F + "100-CC0-SFX_0.zip"]),
    "oga_100_sfx2_rubberduck": (OGA + "100-cc0-sfx-2", [F + "sfx_100_v2.zip"]),
    "oga_75_breaking_rubberduck": (OGA + "75-cc0-breaking-falling-hit-sfx", [F + "sfx_breaking_and_falling.zip"]),
    "oga_30_loops_rubberduck": (OGA + "30-cc0-sfx-loops", [F + "sfx_loops.zip"]),
    "oga_pings_scrapes_bart": (OGA + "31-pings-and-metal-filing-sounds", [F + "pings_and_scrapes.7z"]),
    "oga_metal_clangs_bart": (OGA + "metal-clang-sounds", [F + "clangs.zip"]),
    "oga_steam_hisses_bart": (OGA + "steam-release-sounds", [F + "steam_hisses.zip"]),
    "oga_workshop_bart": (OGA + "68-workshop-sounds", [F + "workshop.7z"]),
    "oga_hits_pauliuw": (OGA + "hit-sounds", [F + "hits.7z"]),
    "oga_metal_interactions_qubodup": (OGA + "metal-interactions", [F + "metal_interactions.7z"]),
    "oga_door_set_qubodup": (OGA + "door-open-door-close-set", [F + "qubodup-DoorSet.7z"]),
    "oga_door_lock_cough_e": (OGA + "door-lock-sounds", [F + "DoorLockSounds.zip"]),
    "oga_creaky_hinge": (OGA + "creaky-door-hinge-spooky", [F + "creaky_door_hinge.wav"]),
    "oga_metal_steps_thimras": (OGA + "metal-footsteps-on-concrete", [F + "metal_steps_48k24b.7z"]),
    "oga_footsteps_subway": (OGA + "footsteps-0", [F + "0%d-footstep%s.ogg" % (i, "_0" if i == 1 else "") for i in range(1, 7)]),
    "oga_fantozzi_steps": (OGA + "fantozzis-footsteps-grasssand-stone", [F + "Fantozzi-footsteps.7z"]),
    "oga_steps_leather_cloth": (OGA + "footsteps-leather-cloth-armor", [F + "footsteps.zip"]),
    "oga_kenney_rpg": (OGA + "50-rpg-sound-effects", [F + "RPGsounds_Kenney.zip"]),
    "oga_kenney_interface": (OGA + "interface-sounds", [F + "kenney_interfaceSounds.zip"]),
    "oga_kenney_ui": (OGA + "51-ui-sound-effects-buttons-switches-and-clicks", [F + "UI_SFX_Set.zip"]),
    "oga_kenney_scifi": (OGA + "sci-fi-sounds", [F + "sci-fi_sounds.zip"]),
    "oga_electricity_bmaczero": (OGA + "electricity-sound-effects-0", [F + "continuousspark.wav", F + "spark.wav"]),
    "oga_electricity_pack_faxcorp": (OGA + "electricity-game-sound-pack", [F + n for n in ["charge.wav", "chargestart.wav", "crackleelectricityloop.wav", "powerdown.wav", "shieldhit.wav", "snaploop.wav", "hit.wav", "groundhit.wav"]]),
    "oga_circuit_breaker": (OGA + "sfx-circuit-breaker", [F + "Circuit%20Breaker.zip"]),
    "oga_airvent_loop": (OGA + "airvent-loop", [F + "airvent-large-loop.wav"]),
    "oga_edev_loop_qubodup": (OGA + "electronic-device-loop", [F + "qubodup-edev.flac"]),
    "oga_fan_loop_qubodup": (OGA + "defect-motor-loop", [F + "fan_interval.wav"]),
    "oga_generator_loop": (OGA + "generator-loop", [F + "loop_generator_1.mp3"]),
    "oga_rts_war_qubodup": (OGA + "sci-fi-rts-war-unit-sounds", [F + "qubodup-rts_warsounds_v2.7z"]),
    "oga_heartbeat_qubodup": (OGA + "heartbeat-single-sound", [F + "heartbeat.mp3_.flac"]),
    "oga_sirens_aquinn": (OGA + "sirens-and-alarm-noise", [F + "siren_0.mp3"]),
    # M4
    "oga_chain_winch_bart": (OGA + "chain-winch-sounds", [F + "winch.zip"]),
}


def get(url, binary=False):
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            return data if binary else data.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 3)


def page_info(url):
    h = get(url)
    info = {"page": url}
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    info["title"] = html.unescape(t.group(1)).replace("| OpenGameArt.org", "").strip() if t else ""
    if "opengameart.org" in url:
        a = re.search(r'field-name-author-submitter.*?<div class="field-item even">(.*?)</div>', h, re.S)
        txt = html.unescape(re.sub(r"<[^>]+>", " ", a.group(1))) if a else ""
        info["author"] = re.sub(r"\s+", " ", txt).strip()
        info["licenses"] = re.findall(r"class=['\"]license-name['\"]>([^<]*)<", h)
        info["ok"] = "CC0" in info["licenses"]
    else:
        lic = re.findall(r'class="licensetpl_short"[^>]*>([^<]*)<', h)
        info["licenses"] = lic
        info["author"] = ""
        info["ok"] = any(re.search(r"^(CC0|Public domain|PD)", x, re.I) for x in lic)
    return info


def safe_unzip(path, dest):
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            name = m.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/") or ":" in name:
                print("  skip unsafe member", name)
                continue
            target = os.path.join(dest, *name.split("/"))
            if m.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(m) as src, open(target, "wb") as dst:
                dst.write(src.read())


def fetch(item):
    page, files = SOURCES[item]
    d = os.path.join(RAW, item)
    info = page_info(page)
    print(item, "|", info["title"], "|", info["author"], "|", info["licenses"])
    if not info["ok"]:
        print("  REFUSED: licence field does not list CC0 / PD")
        return None
    os.makedirs(d, exist_ok=True)
    got = []
    for u in files:
        fn = urllib.parse.unquote(u.rsplit("/", 1)[1]).replace(" ", "_")
        p = os.path.join(d, fn)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            data = get(u, binary=True)
            with open(p, "wb") as fh:
                fh.write(data)
        got.append({"url": u, "file": fn, "bytes": os.path.getsize(p)})
        low = fn.lower()
        if low.endswith((".zip", ".7z")):
            x = os.path.join(d, "x", os.path.splitext(fn)[0])
            if not os.path.isdir(x):
                os.makedirs(x, exist_ok=True)
                if low.endswith(".zip"):
                    safe_unzip(p, x)
                else:
                    subprocess.run([BSDTAR, "-xf", p, "-C", x], check=True)
    info["files"] = got
    info["fetched"] = time.strftime("%Y-%m-%d")
    with open(os.path.join(d, "SOURCE.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)
    return info


if __name__ == "__main__":
    ids = sys.argv[1:] or list(SOURCES)
    for i in ids:
        try:
            fetch(i)
        except Exception as e:  # noqa: BLE001
            print("  ERROR", i, e)
        time.sleep(0.5)
