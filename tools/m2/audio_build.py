# Rebuild staging/audio/*.wav for BREACH from the CC0 recordings in
# staging/audio/raw/ (fetched by tools/m2/audio_fetch.py) plus the synthesis
# in tools/m2/synth_audio_v2.py.  Deterministic: same inputs -> same outputs.
#
#   python -I tools/m2/audio_build.py              # build everything + validate + SOURCES.md
#   python -I tools/m2/audio_build.py rifle_shot   # build only outputs whose name starts with ...
#   python -I tools/m2/audio_build.py --validate   # only validate the existing outputs
#
# Recordings are decoded by ffmpeg to 48 kHz float, edited and layered in
# Python, and written as 16-bit PCM WAV (mono for every positional sound,
# stereo only for ambience_* beds).  Downloads are treated as data only.
import json
import math
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import synth_audio_v2 as S  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "staging", "audio", "raw")
OUT = os.path.join(ROOT, "staging", "audio")
SR = S.SR
N = S.N

# --------------------------------------------------------------------------
# provenance tracking
# --------------------------------------------------------------------------
PROV = {}      # name -> {"sources": [(src_id, rel)], "proc": str, "synth": bool}
_CUR = [None]


def begin(name, proc, synth_layers=True):
    _CUR[0] = name
    PROV[name] = {"sources": [], "proc": proc, "synth": synth_layers}


def _note(src, rel):
    if _CUR[0] and (src, rel) not in PROV[_CUR[0]]["sources"]:
        PROV[_CUR[0]]["sources"].append((src, rel))


# --------------------------------------------------------------------------
# decoding
# --------------------------------------------------------------------------
_CH = {}


def _channels(path):
    if path not in _CH:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
        _CH[path] = int(r.stdout.strip().split(",")[0])
    return _CH[path]


def rec(src, rel, t0=0.0, dur=None, speed=1.0, stereo=False):
    """Decode part of a raw recording to 48 kHz float.  Mono = average of
    channels.  Returns a list (mono) or [L, R] (stereo=True)."""
    path = os.path.join(RAW, src, *rel.split("/"))
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    _note(src, rel)
    ch = _channels(path)
    cmd = ["ffmpeg", "-v", "error"]
    if t0:
        cmd += ["-ss", "%.4f" % t0]
    if dur:
        cmd += ["-t", "%.4f" % (dur / speed)]
    cmd += ["-i", path]
    if stereo:
        af = "aformat=channel_layouts=stereo" if ch >= 2 else "pan=stereo|c0=c0|c1=c0"
        oc = 2
    else:
        af = "pan=mono|c0=0.5*c0+0.5*c1" if ch >= 2 else "anull"
        oc = 1
    cmd += ["-af", af + ",aresample=%d:filter_size=64" % SR, "-f", "f32le", "-ac", str(oc), "-ar", str(SR), "pipe:1"]
    r = subprocess.run(cmd, capture_output=True, check=True)
    import array
    a = array.array("f")
    a.frombytes(r.stdout[: len(r.stdout) // 4 * 4])
    if oc == 1:
        x = list(a)
        return S.resample(x, speed) if speed != 1.0 else x
    L, R = list(a[0::2]), list(a[1::2])
    if speed != 1.0:
        L, R = S.resample(L, speed), S.resample(R, speed)
    return [L, R]


def onset(x, rel_db=-24.0, start=0):
    th = S.peak(x[start:]) * S.db(rel_db)
    for i in range(start, len(x)):
        if abs(x[i]) > th:
            return i
    return start


def snap(x, rel_db=-24.0, pre=0.002, dur=None):
    """Trim leading silence so the transient starts 'pre' seconds in."""
    i = max(0, onset(x, rel_db) - N(pre))
    y = x[i:]
    return y[: N(dur)] if dur else y


def unit(x):
    return S.normalize(x, 0.0)


def bed(x, L_sec, xf=0.8, offsets=(0.0,)):
    """Seamless loop of length L_sec built from recording x: segments of x are
    chained with equal-power crossfades (starting at varied offsets), then
    the result is crossfaded tail-into-head."""
    L, X = N(L_sec), N(xf)
    stream = []
    k = 0
    while len(stream) < L + X + 1:
        off = N(offsets[k % len(offsets)]) % max(1, len(x) - 2 * X)
        seg = x[off:]
        if not stream:
            stream = list(seg)
        else:
            tail = stream[-X:]
            head = seg[:X]
            mixd = [t * math.cos(0.5 * math.pi * i / X) + h * math.sin(0.5 * math.pi * i / X) for i, (t, h) in enumerate(zip(tail, head))]
            stream = stream[:-X] + mixd + seg[X:]
        k += 1
    return S.loop_xfade(stream[: L + X], xf)


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------
PENDING = {}


def out(name, sig, peak_db, fin=0.0008, fout=0.012, loop=False):
    """Queue an output; written by finalize() after family loudness matching."""
    chans = sig if isinstance(sig[0], list) else [sig]
    if not loop:
        chans = [S.fade(c, fin, fout) for c in chans]
    PENDING[name] = (chans, peak_db)


def st_loudness(chans, win=0.1):
    """Max RMS over 100 ms windows (hop 10 ms) of the peak-normalised mix:
    a simple short-term loudness proxy for one-shot effects."""
    x = chans[0] if len(chans) == 1 else [0.5 * (a + b) for a, b in zip(*chans)]
    m = S.peak(x) or 1.0
    w, h = N(win), N(0.01)
    best = 0.0
    sq = [(v / m) ** 2 for v in x]
    acc = sum(sq[:w])
    best = acc
    for i in range(h, max(1, len(sq) - w), h):
        acc = sum(sq[i:i + w])
        best = max(best, acc)
    return math.sqrt(best / max(1, w))


# Mix hierarchy: target short-term loudness (max 100 ms RMS, dBFS) per
# family.  Each file is first normalised to its peak ceiling (the peak_db
# given to out()); if it is then louder than its target it is turned down.
# Gunshots are the loudest one-shots, UI and foley the quietest.
ST_TARGET = {
    "rifle_shot": -10.5, "pistol_shot": -12.0, "tesla_shot": -12.5, "door_breach": -12.0,
    "robot_death": -13.5, "robot_step": -15.5, "robot_hit": -16.0, "robot_weakpoint": -16.0,
    "player_hurt": -16.0, "robot_alert": -17.0, "extraction_alarm": -18.0, "tesla_charge": -18.0,
    "robot_zap": -19.0, "door_open": -19.0, "rifle_shot_suppressed": -20.0, "pistol_shot_suppressed": -21.0,
    "ricochet": -20.0, "bolt": -20.0, "impact_metal": -21.0, "heartbeat": -21.0, "robot_hydraulic": -21.0,
    "mag_in": -21.0, "pistol_slide": -21.0, "ui_objective": -21.0, "ui_hack_done": -22.0,
    "impact_concrete": -22.0, "robot_servo": -22.0, "hitmarker_kill": -22.0, "door_locked": -23.0,
    "mag_out": -23.0, "hitmarker": -24.0, "weapon_switch": -24.0, "dry_fire": -24.0,
    "step_metal": -26.0, "shell_tink": -27.0, "step_concrete": -27.0, "ads_in": -31.0, "foley_cloth": -35.0,
}


def finalize():
    """Apply the loudness hierarchy (ST_TARGET) and match variants of one
    family (name_0, name_1, ...) in short-term loudness: louder variants are
    turned down to the family median (never up, so no variant exceeds its
    peak ceiling)."""
    import re
    fams = {}
    for name in PENDING:
        fams.setdefault(re.sub(r"_\d+$", "", name), []).append(name)
    for fam, names in fams.items():
        adj = {n: 0.0 for n in names}
        loud = {n: st_loudness(PENDING[n][0]) for n in names}
        if len(names) > 1:
            med = sorted(loud.values())[len(names) // 2]
            for n in names:
                adj[n] = min(0.0, 20 * math.log10(med / loud[n]))
        if fam in ST_TARGET:
            for n in names:
                st_now = PENDING[n][1] + adj[n] + 20 * math.log10(loud[n])
                adj[n] += min(0.0, ST_TARGET[fam] - st_now)
        for n in names:
            chans, pk = PENDING[n]
            S.write_wav(os.path.join(OUT, n + ".wav"), chans, pk + adj[n], dither_seed=sum(map(ord, n)))
            print("wrote %-28s %5.2fs %-6s peak %.1f dBFS%s" % (n, len(chans[0]) / SR, "stereo" if len(chans) == 2 else "mono", pk + adj[n], " (level adj %.1f dB)" % adj[n] if adj[n] else ""))
    PENDING.clear()


# ==========================================================================
# source shortcuts
# ==========================================================================
FFSL = "oga_free_firearm_sound_library"
FF = "x/Prepared_SFX_Library/Prepared SFX Library/"
Z0 = ("oga_handgun_reload_zer0sol", "reload.wav")
KRPG = ("oga_kenney_rpg", "x/RPGsounds_Kenney/OGG/")
R75 = ("oga_75_breaking_rubberduck", "x/sfx_breaking_and_falling/")
RMW = ("oga_100_metal_wood_rubberduck", "x/100-CC0-wood-metal-SFX/")
RS2 = ("oga_100_sfx2_rubberduck", "x/sfx_100_v2/")
FANT = ("oga_fantozzi_steps", "x/Fantozzi-footsteps/Fantozzi-footsteps/flac/")
THIM = ("oga_metal_steps_thimras", "x/metal_steps_48k24b/")
DOOR = ("oga_door_set_qubodup", "x/qubodup-DoorSet/qubodup-DoorSet/flac/")
ELEC = "oga_electricity_bmaczero"
STEAM = ("oga_steam_hisses_bart", "x/steam_hisses/steam hisses - Marker #%d.wav")
WS = ("oga_workshop_bart", "x/workshop/workshop/workshop - %s.wav")


def kr(name, **kw):
    return rec(KRPG[0], KRPG[1] + name, **kw)


# ==========================================================================
# weapons
# ==========================================================================
RIFLE_SRC = [("AR-15/D_32P.wav", 0.70), ("AR-15/D_32P.wav", 5.65), ("AK-47/C_28P.wav", 0.61)]
PISTOL_SRC = [("Walther PPQ/X_39P.wav", 1.41), ("Walther PPQ/X_39P.wav", 6.44), ("Walther PPQ/X_39P.wav", 10.66)]
GUN_IR = ["concrete_room", "concrete_room_b", "concrete_room_c"]


def shot_direct(rel, t_on, length):
    """Direct sound of an outdoor near-distance shot, cut before the first
    outdoor echo (~180 ms) so the synthesized indoor tail can replace it."""
    x = rec(FFSL, FF + rel, t_on - 0.06, 0.45)
    d = snap(x, -20, 0.0015, length)
    d = S.fade(d, 0.0003, length * 0.35)
    return unit(S.hp(d, 30))


def build_gunshots():
    for k, (rel, t) in enumerate(RIFLE_SRC):
        name = "rifle_shot_%d" % k
        begin(name, "Free Firearm Sound Library near-distance shot (%s): direct sound cut at 170 ms (before the outdoor echo), summed to mono, HP 30 Hz; layered with a synthesized transient crack and faint bolt-carrier clicks; +2 dB presence at 2.6 kHz, compression, soft clip; convolved with a synthesized concrete-room IR (exponentially decaying 3-band noise + sparse early reflections, T60 ~0.8 s; wet 0.42, wet return HP 220 Hz); synthesized sub thump (120->50 Hz) added after the reverb; 7 dB into a 1.5 ms look-ahead peak limiter + light soft clip for density; peak -1 dBFS" % rel.split("/")[0])
        rnd = random.Random(100 + k)
        d = shot_direct(rel, t, 0.17)
        sub = S.thump(0.3, 120, 50, 0.018, 0.06, drive=1.4)
        crack = S.mul(S.hp(S.white(N(0.01), rnd), 3000), S.env_exp(N(0.01), 0.00002, 0.0015))
        dry = S.mix((d, 1.0, 0), (crack, 0.25, 0), (S.gun_mech(200 + k, "rifle"), 0.04, 0.003))
        dry = S.peq(dry, 2600, 0.8, 2.0)
        dry = S.softclip(unit(S.compress(dry, -18, 3.0, 0.0002, 0.05, 3)), 1.4)
        y = S.reverb(dry, GUN_IR[k], wet=0.42, wet_hp=220)
        y = S.mix((y, 1.0, 0), (sub, 0.4, 0.0005))
        y = S.softclip(S.limiter(S.gain(unit(y), S.db(7.0)), 0.95, 0.0015, 0.05), 1.2)  # density / punch
        y = S.trim_tail(y, -62)[: N(1.1)]
        out(name, S.fade(y, 0, 0.15), -1.0)
    for k, (rel, t) in enumerate(PISTOL_SRC):
        name = "pistol_shot_%d" % k
        begin(name, "Free Firearm Sound Library (Walther PPQ 9 mm) near-distance shot: direct sound cut at 140 ms (before the outdoor echo), mono, HP 30 Hz; layered with a synthesized crack and faint slide clicks; presence EQ, compression, soft clip; convolved with a synthesized concrete-room IR (wet 0.36, wet return HP 250 Hz); synthesized sub thump (160->58 Hz) added after the reverb; 6 dB into a 1.5 ms look-ahead peak limiter + light soft clip; peak -1 dBFS")
        rnd = random.Random(110 + k)
        d = shot_direct(rel, t, 0.14)
        sub = S.thump(0.25, 160, 58, 0.014, 0.045, drive=1.4)
        crack = S.mul(S.hp(S.white(N(0.01), rnd), 3500), S.env_exp(N(0.01), 0.00002, 0.0012))
        dry = S.mix((d, 1.0, 0), (crack, 0.22, 0), (S.gun_mech(210 + k, "pistol"), 0.04, 0.002))
        dry = S.peq(dry, 3000, 0.8, 1.5)
        dry = S.softclip(unit(S.compress(dry, -18, 3.0, 0.0002, 0.05, 3)), 1.3)
        y = S.reverb(dry, GUN_IR[(k + 1) % 3], wet=0.36, wet_hp=250)
        y = S.mix((y, 1.0, 0), (sub, 0.33, 0.0005))
        y = S.softclip(S.limiter(S.gain(unit(y), S.db(6.0)), 0.95, 0.0015, 0.04), 1.2)  # density / punch
        y = S.trim_tail(y, -62)[: N(0.95)]
        out(name, S.fade(y, 0, 0.14), -1.0)


def slide_slam():
    """zer0sol handgun reload: slide release slam (around 1.22-1.40 s)."""
    x = rec(*Z0, t0=1.17, dur=0.3)
    return S.hp(snap(x, -18, 0.002, 0.2), 150)


def build_suppressed():
    slam = unit(slide_slam())
    for k, (rel, t) in enumerate(RIFLE_SRC):
        name = "rifle_shot_suppressed_%d" % k
        begin(name, "Blast removed: the same Free Firearm Sound Library shot 4-pole low-passed at 650 Hz with a 30 ms envelope (body only, ~-12 dB); synthesized suppressor 'pfft' (swept noise burst), small sub thump and bolt-carrier clicks (modal resonators) layered with the real slide/bolt slam from the zer0sol handgun reload recording slowed to 0.8x (LP 7 kHz); corridor IR (wet 0.2, return HP 200 Hz); peak -5 dBFS")
        rnd = random.Random(300 + k)
        d = shot_direct(rel, t, 0.17)
        body = S.mul(S.lp4(d, 650), S.env_exp(len(d), 0.0005, 0.03))
        puff = S.noise_hit(0.15, rnd, 4200, 500, 0.006, 0.018)
        sub = S.thump(0.2, 140, 60, 0.01, 0.03)
        mech = S.gun_mech(320 + k, "rifle")
        heavy = S.lp(S.resample(slam, 0.8), 7000)
        dry = S.mix((unit(body), 0.45, 0), (puff, 0.35, 0), (sub, 0.3, 0), (mech, 0.5, 0.002), (heavy, 0.55, 0.006))
        y = S.reverb(dry, "corridor", wet=0.2, wet_hp=200)
        out(name, S.trim_tail(y, -60)[: N(0.7)], -3.0)
    for k, (rel, t) in enumerate(PISTOL_SRC):
        name = "pistol_shot_suppressed_%d" % k
        begin(name, "Blast removed: the same Free Firearm Sound Library 9 mm shot low-passed at 850 Hz with a 25 ms envelope; synthesized suppressor 'pfft' and slide clicks layered with the real slide slam from the zer0sol handgun reload recording (pitch varied per variant); corridor IR (wet 0.18, return HP 200 Hz); peak -6 dBFS")
        rnd = random.Random(330 + k)
        d = shot_direct(rel, t, 0.14)
        body = S.mul(S.lp4(d, 850), S.env_exp(len(d), 0.0005, 0.025))
        puff = S.noise_hit(0.12, rnd, 5000, 600, 0.005, 0.014)
        mech = S.gun_mech(340 + k, "pistol")
        sl = S.resample(slam, (1.0, 1.04, 0.96)[k])
        dry = S.mix((unit(body), 0.4, 0), (puff, 0.35, 0), (mech, 0.4, 0.002), (sl, 0.7, 0.004))
        y = S.reverb(dry, "corridor", wet=0.18, wet_hp=200)
        out(name, S.trim_tail(y, -60)[: N(0.6)], -4.0)


def build_handling():
    begin("mag_out", "zer0sol 'Handgun Reload' recording, 0.07-0.45 s (magazine release and drop-out), HP 180 Hz, low-mid cut; synthesized release-button click (modal) layered on the front; small-room IR (wet 0.08); peak -4 dBFS")
    x = S.hp(rec(*Z0, t0=0.06, dur=0.4), 180)
    x = S.peq(x, 350, 1.0, -3)
    btn = S.click(random.Random(311), 3600, 900, 0.005, 0.05, 0.8)
    y = S.mix((unit(x), 1.0, 0.012), (btn, 0.35, 0.0))
    out("mag_out", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -2.0)

    begin("mag_in", "zer0sol 'Handgun Reload' recording, 0.56-0.98 s (magazine insertion and seat), HP 150 Hz; synthesized low 'seat' resonance (modal 420/1150 Hz) under the main transient; small-room IR (wet 0.08); peak -6 dBFS")
    x = unit(S.hp(rec(*Z0, t0=0.55, dur=0.43), 150))
    pk = max(range(len(x)), key=lambda i: abs(x[i]))
    seat = S.strike(0.15, random.Random(321), [(420, 0.012, 1.0), (1150, 0.008, 0.6)], exc=0.0005, noise_amt=0.3)
    y = S.mix((x, 1.0, 0), (seat, 0.14, pk / SR))
    out("mag_in", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -6.0)

    begin("pistol_slide", "zer0sol 'Handgun Reload' recording, slide-release slam (1.17-1.47 s), HP 150 Hz; small-room IR (wet 0.08); peak -6 dBFS", synth_layers=False)
    y = S.reverb(slide_slam(), "small_room", wet=0.08)
    out("pistol_slide", S.trim_tail(y, -55), -6.0)

    begin("bolt", "zer0sol 'Handgun Reload' recording, full slide rack (pull + release, 1.0-1.55 s) slowed to 0.86x for a heavier rifle charging handle, HP 100 Hz; synthesized bolt-slam body (modal 560/1650/3100 Hz) under the release transient; small-room IR (wet 0.1); peak -6 dBFS")
    x = unit(S.hp(rec(*Z0, t0=1.0, dur=0.55, speed=0.86), 100))
    half = N(0.12)
    pk = half + max(range(len(x) - half), key=lambda i: abs(x[half + i]))
    slam = S.strike(0.25, random.Random(331), [(560, 0.03, 1.0), (1650, 0.02, 0.8), (3100, 0.012, 0.6)], exc=0.0004, noise_amt=0.3)
    y = S.mix((x, 1.0, 0), (slam, 0.2, pk / SR))
    out("bolt", S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -6.0)

    begin("dry_fire", "LFA 'Equipment Click' (stapler click, 2.26 s onward) as the trigger break, HP 300 Hz; synthesized hammer/striker fall (modal click 2.9 kHz + 760 Hz body) 28 ms later; peak -5 dBFS")
    trig = unit(S.hp(snap(rec("oga_equipment_click_lfa", "equipmentclick.wav", t0=2.2, dur=0.3), -20, 0.001, 0.12), 300))
    fall = S.click(random.Random(302), 2900, 760, 0.010, 0.10, 1.0)
    out("dry_fire", S.trim_tail(S.mix((trig, 0.6, 0), (fall, 1.0, 0.028)), -55), -2.0)

    begin("weapon_switch", "Kenney RPG Audio 'cloth2' (sling/cloth rustle) + 'metalLatch' (handling clack at 0.2 s), HP 120 Hz; synthesized grip impact (modal); small-room IR (wet 0.1); peak -9 dBFS")
    c = unit(S.hp(kr("cloth2.ogg"), 120))
    latch = unit(S.hp(snap(kr("metalLatch.ogg"), -20, 0.001), 200))
    grip = S.strike(0.2, random.Random(351), [(380, 0.02, 1), (1250, 0.012, 0.5), (2900, 0.006, 0.3)], exc=0.0008, noise_amt=0.5)
    y = S.mix((c, 0.55, 0), (latch, 0.8, 0.2), (grip, 0.3, 0.2))
    out("weapon_switch", S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -7.0)

    begin("ads_in", "Kenney RPG Audio 'cloth4' (short cloth movement, first 0.25 s), HP 200 Hz; synthesized light grip tick at 0.12 s; peak -16 dBFS")
    c = unit(S.hp(kr("cloth4.ogg", dur=0.3), 200))
    tick = S.click(random.Random(361), 2700, 500, 0.004, 0.05, 0.4)
    out("ads_in", S.fade(S.mix((c, 1.0, 0), (tick, 0.2, 0.12)), 0.002, 0.06), -14.0)

    for k in range(4):
        name = "shell_tink_%d" % k
        begin(name, "synthesized: brass-casing modal resonators (inharmonic tube modes ~4.3-5.6 kHz), 3-5 bounces with shrinking intervals, short roll; small-room IR; peak -14 dBFS")
        out(name, S.shell_tink(500 + k), -14.0)


# ==========================================================================
# impacts
# ==========================================================================
def build_impacts():
    metal = [(R75, "bfh1_metal_hit_03.ogg"), (RMW, "metal_hit_02.ogg"), (R75, "bfh1_metal_hit_01.ogg")]
    for k, (pk_, f) in enumerate(metal):
        name = "impact_metal_%d" % k
        begin(name, "rubberduck CC0 metal hit recording, onset-trimmed, HP 250 Hz, +3 dB at 4 kHz; layered with a synthesized bullet crack (0.8 ms HP noise) and spark crackle; small-room IR (wet 0.12); peak -5 dBFS")
        rnd = random.Random(410 + k)
        x = unit(S.hp(snap(rec(pk_[0], pk_[1] + f), -20, 0.001, 0.45), 250))
        x = S.peq(x, 4000, 1.0, 3)
        crack = S.mul(S.hp(S.white(N(0.02), rnd), 3000), S.env_exp(N(0.02), 0.00002, 0.0008))
        sp = S.crackle(0.12, rnd, 300, 40, burst_ms=(0.03, 0.3), band=(3000, 12000))
        y = S.mix((x, 1.0, 0.0008), (crack, 0.6, 0), (sp, 0.2, 0.002))
        out(name, S.trim_tail(S.reverb(y, "small_room", wet=0.12), -55), -3.0)
    rock = [(RS2, "sfx100v2_stones_01.ogg"), (R75, "bfh1_rock_hit_01.ogg"), (RS2, "sfx100v2_stones_03.ogg")]
    for k, (pk_, f) in enumerate(rock):
        name = "impact_concrete_%d" % k
        begin(name, "synthesized bullet-into-concrete layer (HP noise crack, swept low-passed body, modal debris grains, dust hiss) layered with a rubberduck CC0 stone/rock hit recording (onset-trimmed, HP 150 Hz) as debris; small-room IR (wet 0.1); peak -4 dBFS")
        x = unit(S.hp(snap(rec(pk_[0], pk_[1] + f), -20, 0.001, 0.35), 150))
        syn = S.impact_concrete(420 + k)
        y = S.mix((syn, 1.0, 0), (x, 0.5, 0.004))
        out(name, S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -1.0)
    begin("ricochet", "rubberduck CC0 metal hit 'bfh1_metal_hit_06' (onset-trimmed, HP 300 Hz) + synthesized ricochet whine (swept tone + resonant band-passed noise, 5 kHz -> 1.5 kHz); small-room IR; peak -9 dBFS")
    x = unit(S.hp(snap(rec(R75[0], R75[1] + "bfh1_metal_hit_06.ogg"), -20, 0.001, 0.35), 300))
    y = S.mix((x, 0.8, 0), (S.ricochet_whine(402), 0.5, 0.01))
    out("ricochet", S.trim_tail(S.reverb(y, "small_room", wet=0.12), -55), -9.0)


# ==========================================================================
# footsteps / foley
# ==========================================================================
STONE = ["StoneL1", "StoneR1", "StoneL2", "StoneR2", "StoneL3", "StoneR3"]


def build_steps():
    for k, s in enumerate(STONE):
        name = "step_concrete_%d" % k
        begin(name, "Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1); peak -14 dBFS", synth_layers=False)
        x = unit(S.hp(snap(rec(FANT[0], FANT[1] + "Fantozzi-%s.flac" % s), -26, 0.003, 0.4), 70))
        x = S.peq(x, 3000, 1.0, 2)
        out(name, S.trim_tail(S.reverb(x, "corridor", wet=0.1), -55), -11.0)
    for k, s in enumerate(STONE):
        name = "step_metal_%d" % k
        begin(name, "Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12); peak -13 dBFS")
        rnd = random.Random(720 + k)
        x = unit(S.hp(snap(rec(FANT[0], FANT[1] + "Fantozzi-%s.flac" % STONE[(k + 2) % 6], speed=(0.95, 1.03, 0.98, 1.05, 0.97, 1.01)[k]), -26, 0.003, 0.4), 90))
        b = rnd.uniform(170, 260)
        modes = [(b, 0.09, 1.0), (b * 2.3, 0.07, 0.6), (b * 3.9, 0.05, 0.45), (b * 6.1, 0.035, 0.3), (b * 9.4, 0.02, 0.25), (b * 13.7, 0.012, 0.2)]
        plate = unit(S.resonators(S.hp(x, 150), modes, len(x) + N(0.3)))
        clink = unit(S.hp(rec("oga_steps_leather_cloth", "x/footsteps/footsteps/" + ["step_metal.ogg", "step_metal (2).ogg", "step_metal (3).ogg", "step_metal (4).ogg"][k % 4]), 300))
        y = S.mix((x, 1.0, 0), (plate, 0.45, 0), (clink, 0.25, 0.01))
        out(name, S.trim_tail(S.reverb(y, "corridor", wet=0.12), -55), -11.0)
    for k in range(4):
        name = "foley_cloth_%d" % k
        f = ["cloth1.ogg", "cloth3.ogg", "clothBelt.ogg", "cloth2.ogg"][k]
        begin(name, "Kenney RPG Audio '%s' (CC0), HP 150 Hz, LP 9 kHz, 0.45 s max, gentle fades; peak -20 dBFS" % f, synth_layers=False)
        x = S.lp(S.hp(snap(kr(f), -30, 0.005, 0.45), 150), 9000)
        out(name, S.fade(x, 0.004, 0.08), -16.0)


# ==========================================================================
# robot / electricity
# ==========================================================================
def build_robot():
    for k in range(4):
        name = "robot_step_%d" % k
        begin(name, "Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.62-0.7x for mass, HP 40 Hz; layered with synthesized sub thump (110->34 Hz), low-passed impact noise, armour-plate modal clank, debris ticks, and bart 'steam hisses' (CC0) as the hydraulic hiss (HP 2 kHz, 0.35 s, delayed 50 ms); concrete-room IR (wet 0.2); peak -2 dBFS")
        rnd = random.Random(590 + k)
        st = unit(S.hp(snap(rec(THIM[0], THIM[1] + "metal_steps_%02d.wav" % (3 + 4 * k), speed=(0.65, 0.62, 0.7, 0.66)[k]), -20, 0.001), 40))
        h = rec(STEAM[0], STEAM[1] % (1 + k), t0=0.25, dur=0.6)
        h = S.mul(unit(S.hp(h, 2000)), S.env_exp(len(h), 0.02, 0.12))
        syn = S.robot_step_synth(590 + k)
        y = S.mix((st, 0.9, 0), (syn, 0.8, 0), (h, 0.22, 0.05))
        y = S.reverb(y, "concrete_room_b", wet=0.2)
        out(name, S.trim_tail(y, -58)[: N(1.1)], -2.0)
    drills = [("drill short 1", 0.05, 0.62), ("drill short 2", 0.04, 0.58), ("drill3", 0.12, 0.66)]
    for k, (d, t0, sp) in enumerate(drills):
        name = "robot_servo_%d" % k
        begin(name, "bart '68 Workshop Sounds' cordless-drill burst (CC0) slowed to %.2fx (heavier gear-motor whine), HP 120 Hz, 0.5 s with start/stop envelope; layered with a synthesized geared-servo layer (harmonic motor tone + gear-mesh band + brush noise + stop clunk); peak -9 dBFS" % sp)
        x = rec(WS[0], WS[1] % d, t0=t0, dur=0.5, speed=sp)
        x = unit(S.hp(x, 120))
        x = S.mul(x, S.env_pts(len(x), [(0, 0), (0.03, 1), (0.38, 0.8), (0.5, 0)]))
        syn = S.servo(560 + k, 0.45 + 0.05 * k, 130 + 25 * k, 240 + 30 * k, 13, k != 1)
        y = S.mix((x, 0.8, 0), (unit(syn), 0.45, 0))
        out(name, S.trim_tail(y, -55), -9.0)
    for k in range(3):
        name = "robot_hydraulic_%d" % k
        begin(name, "bart 'steam hisses' (CC0) segment (pressure release), HP 400 Hz with envelope, layered with synthesized hydraulic layer (valve click, pressure groan 70-95 Hz, fluid rumble, piston end-stop clunk); small-room IR; peak -8 dBFS")
        h = rec(STEAM[0], STEAM[1] % (5 - k), t0=0.15 + 0.2 * k, dur=0.6 + 0.1 * k)
        h = S.mul(unit(S.hp(h, 400)), S.env_pts(len(h), [(0, 0), (0.015, 1), (0.3, 0.7), ((len(h) - 1) / SR, 0)]))
        syn = unit(S.hydraulic(570 + k, 0.6 + 0.1 * k))
        y = S.mix((h, 0.6, 0.01), (syn, 0.8, 0))
        out(name, S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -8.0)

    begin("robot_hit", "rubberduck CC0 'metal_hit_01' (heavy metal hit, onset-trimmed, HP 120 Hz) layered with a synthesized armour-plate hit (bullet crack + 7-mode plate resonance + low thud) and spark crackle; concrete-room IR (wet 0.12); peak -3 dBFS")
    x = unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_hit_01.ogg"), -20, 0.001, 0.5), 120))
    y = S.mix((x, 0.7, 0.0005), (unit(S.robot_hit(601)), 0.8, 0))
    out("robot_hit", S.trim_tail(y, -58), -3.0)

    begin("robot_weakpoint", "BMacZero 'Electricity Sound Effects' spark.wav (real Tesla-generator spark, CC0), onset-trimmed, HP 300 Hz; layered with synthesized capacitor 'ping' (2.95 kHz glassy modes), dense crackle, arc buzz and pop; concrete-room IR (wet 0.15); peak -2 dBFS")
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.001), 300))
    y = S.mix((unit(S.robot_weakpoint(611)), 0.8, 0), (sp, 0.7, 0.003))
    out("robot_weakpoint", S.trim_tail(y, -58), -2.0)

    begin("robot_zap", "BMacZero 'continuousspark.wav' (real Tesla-generator arc pulses, CC0), HP 400 Hz, gated into a stutter; layered with synthesized mains-synchronous arc buzz bursts and crackle; small-room IR; peak -4 dBFS")
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
    syn = unit(S.robot_zap(621))
    y = S.mix((syn, 0.8, 0), (cs, 0.6, 0.0), (cs, 0.35, 0.21))
    out("robot_zap", S.trim_tail(y, -58)[: N(0.7)], -3.0)

    begin("tesla_charge", "synthesized: rising capacitor/inverter whine (260 Hz -> 3.6 kHz, beating partials), accelerating Poisson crackle, swelling mains hum and arc buzz, plus BMacZero 'continuousspark.wav' (CC0) rising underneath; small-room IR; 0.55 s; peak -4 dBFS")
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 600))
    cs2 = cs + cs + cs
    ramp = [(i / len(cs2)) ** 2 for i in range(len(cs2))]
    syn = unit(S.tesla_charge(631))
    y = S.mix((syn, 1.0, 0), (S.mul(cs2, ramp), 0.35, 0.0))
    y = S.fade(y[: N(0.6)], 0.005, 0.02)
    out("tesla_charge", y, -4.0)

    begin("tesla_shot", "BMacZero 'spark.wav' (real arc crack, CC0) onset-aligned on top of a synthesized discharge: broadband crack, dense arc crackle, 50 Hz arc buzz, sub thump (170->42 Hz) and low boom, compressed and soft-clipped; concrete-room IR (wet 0.4); peak -1.5 dBFS")
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 200))
    y = S.mix((unit(S.tesla_shot(641)), 1.0, 0), (S.reverb(sp, "concrete_room_c", wet=0.3), 0.6, 0.0))
    out("tesla_shot", S.trim_tail(y, -60)[: N(1.0)], -1.5)

    begin("robot_alert", "synthesized: three low detuned saw tones (233 Hz, 165 Hz tritone drop, then 220->150 Hz bend) ring-modulated at 31 Hz with a sub-octave, formant EQ and saturation; concrete-room IR; peak -4 dBFS")
    out("robot_alert", S.robot_alert(651), -4.0)

    begin("robot_death", "synthesized power-down whine (1.2 kHz -> 45 Hz), arc buzz and crackle, layered with BMacZero 'continuousspark.wav' (CC0) at the start, rubberduck CC0 'metal_falling_01' (metal collapse, HP 80 Hz) at 0.5 s, synthesized knee/torso impacts (sub thumps + plate modes) and debris ticks; concrete-room IR (wet 0.35); peak -1.5 dBFS")
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
    fall = unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_falling_01.ogg"), -20, 0.001, 1.2), 80))
    fall = S.fade(fall, 0, 0.3)
    y = S.mix((unit(S.robot_death(661)), 1.0, 0), (cs, 0.45, 0.0), (S.reverb(fall, "concrete_room", wet=0.3), 0.55, 0.5))
    out("robot_death", S.trim_tail(y, -60)[: N(1.8)], -1.5)

    begin("robot_idle_loop", "synthesized 2.0 s loop: 50 Hz transformer hum harmonics (whole cycles), coil whine, fan noise and ticks (crossfaded) + YCbCr 'Generator (loop)' (CC0) made into a 2.0 s seamless bed (HP 40 Hz, LP 2 kHz); peak -12 dBFS; seamless (no fades)")
    g = rec("oga_generator_loop", "loop_generator_1.mp3")
    g = S.lp(S.hp(g, 40), 2000)
    gb = bed(g, 2.0, 0.3, offsets=(0.5,))
    syn = S.robot_idle_loop(671, 2.0)
    kg = 0.35 * S.peak(syn) / max(1e-9, S.peak(gb))
    y = [a * 0.8 + b * kg for a, b in zip(syn, gb)]
    out("robot_idle_loop", y, -19.0, loop=True)

    begin("player_hurt", "BMacZero 'spark.wav' (CC0) jolt layered with synthesized arc buzz, crackle, body thump (150->48 Hz) and low noise hit; no voice; peak -4 dBFS")
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 300))
    y = S.mix((unit(S.player_hurt(901)), 1.0, 0), (sp, 0.6, 0.0))
    out("player_hurt", S.trim_tail(y, -58), -4.0)


# ==========================================================================
# doors
# ==========================================================================
def build_doors():
    begin("door_open", "qubodup 'Door Open, Door Close Set' DoorOpen03 (heavy door with squeak, CC0) slowed to 0.85x, HP 40 Hz, +3 dB low shelf at 120 Hz; w.forster 'Creaky Door Hinge' (CC0, 0.6-2.0 s, slowed 0.8x, band-limited) as the hinge creak; concrete-room IR (wet 0.25); peak -4 dBFS")
    d = unit(S.hp(rec(DOOR[0], DOOR[1] + "qubodup-DoorOpen03.flac", speed=0.85), 40))
    d = S.lshelf(d, 120, 3)
    cr = rec("oga_creaky_hinge", "creaky_door_hinge.wav", t0=0.6, dur=1.4, speed=0.8)
    cr = S.mul(unit(S.lp(S.hp(cr, 250), 5000)), S.env_pts(len(cr), [(0, 0), (0.15, 1), (1.3, 0.8), ((len(cr) - 1) / SR, 0)]))
    y = S.mix((d, 1.0, 0), (cr, 0.25, 0.05))
    y = S.reverb(y, "concrete_room", wet=0.25)
    out("door_open", S.trim_tail(y, -58)[: N(2.0)], -4.0)

    begin("door_breach", "synthesized kick thump + lock burst (modal clicks) + steel-slab resonance and wall slam; layered with rubberduck CC0 'metal_slam_01' (at 5 ms) and qubodup DoorClose04 (heavy slam, CC0, at 160 ms), both HP 40 Hz; debris ticks; concrete-room IR (wet 0.35); peak -1 dBFS")
    slam = unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_slam_01.ogg"), -20, 0.001), 40))
    close = unit(S.hp(snap(rec(DOOR[0], DOOR[1] + "qubodup-DoorClose04.flac"), -20, 0.001), 40))
    syn = unit(S.door_breach_synth(701))
    y = S.mix((syn, 0.9, 0), (slam, 0.8, 0.005), (close, 0.9, 0.16))
    y = S.softclip(unit(y), 1.3)
    y = S.reverb(y, "concrete_room_c", wet=0.35)
    out("door_breach", S.trim_tail(y, -60)[: N(1.8)], -1.0)

    begin("door_locked", "Cough-E 'Door Lock Sounds' LockedDoorHandleJiggle (CC0), onset-trimmed, HP 100 Hz; small-room IR (wet 0.1); peak -8 dBFS", synth_layers=False)
    x = unit(S.hp(snap(rec("oga_door_lock_cough_e", "x/DoorLockSounds/DoorLockSounds/LockedDoorHandleJiggle.wav"), -26, 0.005), 100))
    out("door_locked", S.trim_tail(S.reverb(x, "small_room", wet=0.1), -55), -8.0)


# ==========================================================================
# ambience (stereo, seamless)
# ==========================================================================
def _mix_st(*layers):
    n = min(len(c[0]) for c, _ in layers)
    return [[sum(c[ch][i] * g for c, g in layers) for i in range(n)] for ch in range(2)]


def _norm_st(st):
    m = max(S.peak(st[0]), S.peak(st[1])) or 1.0
    return [[v / m for v in c] for c in st]


def build_ambience():
    L = 12.0
    begin("ambience_facility", "12 s seamless stereo loop: Longor 'Airvent Loop' (CC0) as ventilation bed (decorrelated L/R offsets, LP 5 kHz); rubberduck '100 CC0 SFX #2' loop_machine_02 (CC0) slowed 0.75x, LP 900 Hz, through a synthesized industrial-hall IR as distant machinery; synthesized room tone (filtered noise, 50 Hz hum, 29.5 Hz machine drone, reverberant metal ticks/clanks); all beds equal-power crossfaded tail-into-head; peak -14 dBFS")
    av = S.lp(rec("oga_airvent_loop", "airvent-large-loop.wav"), 5000)
    vent = [bed(av, L, 1.0, offsets=(0.0, 2.5)), bed(av, L, 1.0, offsets=(3.7, 1.2))]
    m = rec(RS2[0], RS2[1] + "sfx100v2_loop_machine_02.ogg", speed=0.75)
    m = S.lp(S.hp(m, 40), 900)
    m = S.reverb(m, "industrial_hall", wet=0.8, dry=0.3)
    mach = [bed(m, L, 1.0, offsets=(0.0, 4.0)), bed(m, L, 1.0, offsets=(5.0, 1.5))]
    syn = S.ambience_facility(801, L, True)
    y = _mix_st((_norm_st(vent), 0.55), (_norm_st(mach), 0.3), (_norm_st(syn), 0.5))
    out("ambience_facility", y, -18.0, loop=True)

    begin("ambience_hall", "12 s seamless stereo loop: synthesized turbine drone (25 Hz shaft harmonics, 425 Hz blade-pass with 0.25 Hz beating, modulated broadband roar, air) + rubberduck loop_machine_01 (CC0) slowed 0.5x and YCbCr 'Generator (loop)' (CC0) slowed 0.7x, both low-passed and sent through a synthesized 3.5 s industrial-hall IR; distant reverberant clanks; crossfaded loop; peak -13 dBFS")
    m1 = rec(RS2[0], RS2[1] + "sfx100v2_loop_machine_01.ogg", speed=0.5)
    m1 = S.reverb(S.lp(S.hp(m1, 30), 1200), "industrial_hall", wet=0.7, dry=0.5)
    g = rec("oga_generator_loop", "loop_generator_1.mp3", speed=0.7)
    g = S.reverb(S.lp(S.hp(g, 25), 600), "industrial_hall", wet=0.5, dry=0.7)
    mb = [bed(m1, L, 1.5, offsets=(0.0, 3.0)), bed(m1, L, 1.5, offsets=(6.0, 2.0))]
    gb = [bed(g, L, 1.5, offsets=(0.0, 2.0)), bed(g, L, 1.5, offsets=(4.0, 1.0))]
    syn = S.ambience_hall(811, L, True)
    y = _mix_st((_norm_st(syn), 0.6), (_norm_st(mb), 0.35), (_norm_st(gb), 0.45))
    out("ambience_hall", y, -17.0, loop=True)

    L2 = 10.0
    begin("ambience_servers", "10 s seamless stereo loop: qubodup '(defect) motor loop' GPU-fan recording (CC0, stereo, HP 80 Hz) and qubodup 'Electronic device loop' hard-disk recording (CC0, HP 150 Hz, low level) as beds; synthesized rack fans (5 detuned blade-pass tones), broadband fan noise, 50 Hz electrical hum and HDD ticks; crossfaded loop; peak -14 dBFS")
    f = rec("oga_fan_loop_qubodup", "fan_interval.wav", stereo=True)
    f = [S.hp(c, 80) for c in f]
    fan = [bed(f[0], L2, 0.6, offsets=(0.0, 1.1)), bed(f[1], L2, 0.6, offsets=(0.4, 1.7))]
    e = S.hp(rec("oga_edev_loop_qubodup", "qubodup-edev.flac"), 150)
    hdd = [bed(e, L2, 0.3, offsets=(0.0, 0.7)), bed(e, L2, 0.3, offsets=(0.9, 0.2))]
    syn = S.ambience_servers(821, L2, True)
    y = _mix_st((_norm_st(fan), 0.45), (_norm_st(hdd), 0.15), (_norm_st(syn), 0.6))
    out("ambience_servers", y, -18.0, loop=True)

    begin("electric_buzz_loop", "synthesized 2.0 s loop: fluorescent ballast buzz (100 Hz pulse train through resonant band-pass, 100 Hz harmonic series, mains-synchronous noise rasp) - all periodic with whole cycles, so the loop is sample-seamless; peak -18 dBFS")
    out("electric_buzz_loop", S.electric_buzz_loop(831, 2.0), -22.0, loop=True)


# ==========================================================================
# player / UI
# ==========================================================================
def build_ui():
    begin("heartbeat", "Independent.nu 'Heartbeat (single sound)' via qubodup (CC0), 0.1-1.0 s (one lub-dub), LP 400 Hz, HP 25 Hz, fade-out; peak -8 dBFS", synth_layers=False)
    x = S.hp(S.lp(rec("oga_heartbeat_qubodup", "heartbeat.mp3_.flac", t0=0.1, dur=0.9), 400), 25)
    out("heartbeat", S.fade(x, 0.005, 0.25), -8.0)

    begin("extraction_alarm", "synthesized two-tone industrial klaxon (587/440 Hz detuned saw stacks, horn formant EQ, saturation, slight vibrato), two cycles, concrete-room IR; peak -6 dBFS")
    out("extraction_alarm", S.extraction_alarm(981), -6.0)

    begin("hitmarker", "synthesized: crisp modal click (detuned partial clusters around 4.6 kHz), short metallic 2.9 kHz ping and a high-passed noise tsk, light compression")
    out("hitmarker", S.hitmarker(961), -3.0)
    begin("hitmarker_kill", "synthesized: double modal tick (35 ms apart), ringing 2.35 kHz ping, small thump and noise tsk, light compression")
    out("hitmarker_kill", S.hitmarker_kill(971), -2.0)

    KI = ("oga_kenney_interface", "x/kenney_interfaceSounds/Audio/")
    begin("ui_click", "Kenney 'Interface Sounds' click_001 (CC0), onset-trimmed; peak -10 dBFS", synth_layers=False)
    out("ui_click", S.trim_tail(snap(rec(KI[0], KI[1] + "click_001.ogg"), -30, 0.001), -55), -10.0)
    begin("ui_objective", "Kenney 'Interface Sounds' confirmation_001 (CC0), small-room IR (wet 0.15); peak -12 dBFS", synth_layers=False)
    out("ui_objective", S.trim_tail(S.reverb(snap(rec(KI[0], KI[1] + "confirmation_001.ogg"), -30, 0.001), "small_room", wet=0.15), -55), -12.0)
    begin("ui_hack_tick", "Kenney 'Interface Sounds' tick_004 (CC0), onset-trimmed; peak -14 dBFS", synth_layers=False)
    out("ui_hack_tick", S.trim_tail(snap(rec(KI[0], KI[1] + "tick_004.ogg"), -30, 0.001), -55), -14.0)
    begin("ui_hack_done", "Kenney 'Interface Sounds' confirmation_002 (CC0), small-room IR (wet 0.15); peak -12 dBFS", synth_layers=False)
    out("ui_hack_done", S.trim_tail(S.reverb(snap(rec(KI[0], KI[1] + "confirmation_002.ogg"), -30, 0.001), "small_room", wet=0.15), -55), -12.0)


GROUPS = [build_gunshots, build_suppressed, build_handling, build_impacts, build_steps, build_robot, build_doors, build_ambience, build_ui]


# ==========================================================================
# validation and SOURCES.md
# ==========================================================================
STEREO_OK = ("ambience_", "ui_")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_sample:format=duration", "-of", "json", path], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    v = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-i", path, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    mean = maxv = None
    for line in v.stderr.splitlines():
        if "mean_volume" in line:
            mean = float(line.split(":")[1].split()[0])
        if "max_volume" in line:
            maxv = float(line.split(":")[1].split()[0])
    return s["codec_name"], int(s["sample_rate"]), int(s["channels"]), float(j["format"]["duration"]), maxv, mean


def loop_seam(path):
    """Compare the end->start junction with typical sample deltas and the
    RMS of the last/first 50 ms."""
    import array
    import wave
    with wave.open(path) as w:
        ch = w.getnchannels()
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
    worst = 0.0
    rms_d = 0.0
    for c in range(ch):
        x = a[c::ch]
        d = sorted(abs(x[i + 1] - x[i]) for i in range(len(x) - 1))
        j = abs(x[0] - x[-1])
        # percentile of the end->start step among all sample-to-sample steps
        import bisect
        worst = max(worst, 100.0 * bisect.bisect_left(d, j) / len(d))
        k = N(0.05)
        r1 = (sum(v * v for v in x[-k:]) / k) ** 0.5
        r2 = (sum(v * v for v in x[:k]) / k) ** 0.5
        rms_d = max(rms_d, abs(20 * math.log10((r1 + 1e-9) / (r2 + 1e-9))))
    return worst, rms_d


def st_dbfs(path):
    """Max 100 ms RMS (dBFS) of the file - short-term loudness proxy."""
    import array
    import wave
    with wave.open(path) as w:
        ch = w.getnchannels()
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
    x = [sum(a[i:i + ch]) / (ch * 32768.0) for i in range(0, len(a), ch)]
    w_, h = N(0.1), N(0.01)
    sq = [v * v for v in x]
    best = sum(sq[:w_])
    for i in range(h, max(1, len(sq) - w_), h):
        best = max(best, sum(sq[i:i + w_]))
    return 10 * math.log10(best / w_ + 1e-12)


def validate():
    rows = []
    bad = []
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".wav"):
            continue
        p = os.path.join(OUT, f)
        codec, sr, ch, dur, mx, mean = probe(p)
        name = f[:-4]
        ok = codec == "pcm_s16le" and sr in (44100, 48000) and (ch == 1 or name.startswith(STEREO_OK))
        seam = ""
        if name.startswith("ambience_") or name.endswith("_loop"):
            w, r = loop_seam(p)
            seam = "seam step at P%.0f of in-file sample steps, edge RMS diff %.1f dB" % (w, r)
        rows.append((name, codec, sr, ch, dur, mx, mean, st_dbfs(p), seam))
        if not ok:
            bad.append(name)
    print("%-28s %-9s %6s %2s %6s %7s %7s %7s  %s" % ("name", "codec", "sr", "ch", "dur", "peak", "mean", "st100", "loop"))
    for r in rows:
        print("%-28s %-9s %6d %2d %6.2f %7.1f %7.1f %7.1f  %s" % r)
    print("format problems:", bad or "none")
    return rows


def _src_meta(src):
    p = os.path.join(RAW, src, "SOURCE.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _file_url(meta, rel):
    files = meta.get("files", [])
    if rel.startswith("x/"):
        stem = rel.split("/")[1]
        for f in files:
            if os.path.splitext(f["file"])[0] == stem:
                return f["url"]
    for f in files:
        if f["file"] == rel.replace(" ", "_"):
            return f["url"]
    return files[0]["url"] if files else ""


def _author(m):
    a = re.sub(r"\s+\)", ")", m["author"]).replace("|", "/")
    if "@" in a:  # an e-mail shown as user name on OGA: keep only the name part
        a = a.split("@")[0] + " (OpenGameArt user)"
    return a


def write_sources(rows):
    names = [r[0] for r in rows]
    by_dur = {r[0]: r for r in rows}
    lines = ["# BREACH audio (staging/audio) - sources and processing", "",
             "Rebuild: `python -I tools/m2/audio_fetch.py` (downloads + licence check into staging/audio/raw/<id>/), then `python -I tools/m2/audio_build.py`.",
             "All recordings are CC0 1.0 (licence verified on each asset's own OpenGameArt page; the licence field is re-parsed by audio_fetch.py and stored in raw/<id>/SOURCE.json). "
             "Everything else is synthesized (tools/m2/synth_audio_v2.py), first-party work of this project. No CC-BY / CC-BY-SA / unclear material is used.",
             "",
             "Format: 16-bit PCM WAV, 48 kHz; mono for all positional sounds, stereo only for ambience_* beds.",
             "",
             "## Source assets", "",
             "| id (raw/ dir) | asset | author | licence | page |", "|---|---|---|---|---|"]
    used = sorted({s for n in names for s, _ in PROV.get(n, {}).get("sources", [])})
    for s in used:
        m = _src_meta(s)
        lic = "CC0" if m["licenses"] == ["CC0"] else "CC0 (dual-licensed: %s; used under CC0)" % " / ".join(m["licenses"])
        lines.append("| %s | %s | %s | %s | %s |" % (s, m["title"], _author(m), lic, m["page"]))
    lines += ["", "## Loudness and loop checks", "",
              "Every one-shot is normalised to a peak ceiling and then turned down to a per-family short-term loudness target "
              "(max 100 ms RMS, dBFS): rifle -10.5, pistol -12 (peak-limited at -13), tesla_shot -12.5, door_breach -12, robot_death -13.5, "
              "robot_step -15.5, robot hits -16, suppressed shots -20/-21, handling -20..-24, impacts -21/-22, footsteps -26/-27, "
              "shell tinks -27, ads_in -31, cloth -35; UI ticks/clicks sit at -29..-35 and UI chimes at -21/-22. Variants of a family "
              "are matched to the family median. Loops (ambience_*, robot_idle_loop, electric_buzz_loop) have no fades: recorded beds "
              "are equal-power crossfaded tail-into-head, synthesized periodic layers use whole cycles over the loop length and circular "
              "(steady-state) filtering; the end-to-start sample step is checked to lie inside the normal distribution of in-file steps.",
              "",
              "## Searched but not used / not found", "",
              "- No CC0/PD recordings of suppressed gunshots, rifle charging handles, robot servos/hydraulics, fluorescent-light buzz, "
              "klaxons or shell casings were found; these are hybrids of CC0 recordings and synthesis, or fully synthesized.",
              "- OpenGameArt 'Iron Door' and 'Electric Buzz' (themightyglider) and 'Machine shutting down' (Cough-E) were skipped: they are "
              "derivatives of Freesound/other recordings whose own licence could not be verified.",
              "- A Wikimedia Commons audio search returned mostly speech/pronunciation files; its few gunshot files were not needed "
              "(the CC0 Free Firearm Sound Library is far better) and were not used. Freesound (login) and Kenney.nl (no scriptable "
              "download) were not used directly; Kenney packs were taken from Kenney's own CC0 uploads on OpenGameArt."]
    lines += ["", "## Output files", ""]
    n_rec = n_syn = n_pure = 0
    for n in names:
        p = PROV.get(n)
        r = by_dur[n]
        lines.append("### %s.wav" % n)
        lines.append("- format: 16-bit PCM, %d Hz, %s, %.2f s; peak %.1f dBFS, mean %.1f dBFS, max 100 ms RMS %.1f dBFS%s" % (r[2], "stereo" if r[3] == 2 else "mono", r[4], r[5], r[6], r[7], ("; " + r[8]) if r[8] else ""))
        if not p:
            lines.append("- source: (not built by this script)")
            continue
        if p["sources"]:
            n_rec += 1
            for s, rel in p["sources"]:
                m = _src_meta(s)
                lic = "CC0"
                inner = "/".join(rel.split("/")[2:]) if rel.startswith("x/") else rel
                lines.append("- source: \"%s\" by %s, file `%s` - %s (download %s) - licence %s" % (m["title"], _author(m), inner, m["page"], _file_url(m, rel), lic))
            if p["synth"]:
                lines.append("- plus synthesized layers (tools/m2/synth_audio_v2.py)")
            else:
                n_pure += 1
        else:
            n_syn += 1
            lines.append("- source: synthesized (tools/m2/synth_audio_v2.py)")
        import re
        lines.append("- processing: %s" % re.sub(r";? ?peak -?[0-9.]+ dBFS", "", p["proc"]).rstrip("; "))
        lines.append("")
    lines.insert(6, "Summary: %d outputs use CC0 recordings (%d edited recordings only, %d recordings layered with synthesis); %d are fully synthesized (tools/m2/synth_audio_v2.py)." % (n_rec, n_pure, n_rec - n_pure, n_syn))
    with open(os.path.join(OUT, "SOURCES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("SOURCES.md: %d with recordings, %d fully synthesized" % (n_rec, n_syn))


def main(argv):
    if "--validate" in argv:
        validate()
        return
    sel = [a for a in argv if not a.startswith("-")]
    os.makedirs(OUT, exist_ok=True)
    for g in GROUPS:
        if sel:
            # run a group only if one of its outputs matches the selection
            src = g.__code__.co_consts
            if not any(isinstance(c, str) and any(c.startswith(s) for s in sel) for c in src):
                continue
        t0 = time.time()
        g()
        print("[%s] %.1f s" % (g.__name__, time.time() - t0), flush=True)
    finalize()
    rows = validate()
    if not sel:
        write_sources(rows)
        work = S.WORK
        if os.path.isdir(work):
            for f in os.listdir(work):
                os.remove(os.path.join(work, f))
            os.rmdir(work)


if __name__ == "__main__":
    main(sys.argv[1:])
