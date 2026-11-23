# M3 audio for BREACH: separate weapon-mechanics one-shots, shot layers
# (bolt-carrier noise, room tails, distant shots), extra robot one-shots and
# two more ambience loops.  Builds staging/audio_m3/ from the CC0 material in
# staging/audio/raw/ plus synthesis (tools/m2/synth_audio_v2.py, extended
# below without modifying it).  Deterministic.
#
#   python -I tools/m2/audio_m3.py              # build all + validate + SOURCES.md
#   python -I tools/m2/audio_m3.py rifle_mag    # build only groups that produce matching names
#   python -I tools/m2/audio_m3.py --validate
import math
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import synth_audio_v2 as S  # noqa: E402
import audio_build as B  # noqa: E402

M3 = os.path.join(B.ROOT, "staging", "audio_m3")
S.WORK = os.path.join(M3, "_work")   # keep scratch files inside the M3 output dir
B.OUT = M3                            # B.finalize / B.validate write/read here
SR, N = S.SR, S.N
rec, snap, unit, bed, begin, out = B.rec, B.snap, B.unit, B.bed, B.begin, B.out

# Loudness hierarchy for the new families (max 100 ms RMS, dBFS); consistent
# with the M2 table in audio_build.ST_TARGET.
B.ST_TARGET = {
    "rifle_shot_dry": -10.5, "pistol_shot_dry": -12.0,
    "rifle_mag_release": -25.0, "rifle_mag_drop": -22.0, "rifle_mag_pouch": -27.0, "rifle_mag_seat": -20.0,
    "rifle_bolt_release": -19.0, "rifle_charge_pull": -22.0, "rifle_charge_release": -20.0,
    "pistol_mag_release": -24.0, "pistol_mag_seat": -21.0, "pistol_slide_rack": -20.0,
    "weapon_draw": -24.0, "weapon_holster": -25.0, "cloth_raise": -31.0, "selector_switch": -26.0,
    "rifle_mech": -21.0, "shot_distant": -22.0, "shot_tail_small": -18.5, "shot_tail_hall": -16.5,
    "robot_step_heavy": -14.5, "robot_scuff": -22.0, "robot_servo_short": -23.0, "robot_hydraulic_hiss": -23.0,
    "robot_stagger": -15.0, "robot_armor_break": -15.0, "robot_collapse": -13.0, "robot_capacitor_whine": -18.0,
}

# extra impulse responses (added to the synth module's preset table at run time)
S.IR_PRESETS["tail_small"] = dict(seed=7101, length=1.1, t60=(0.75, 0.7, 0.3), predelay=0.002, early=18, early_span=0.025, early_gain=0.9)
S.IR_PRESETS["tail_hall"] = dict(seed=7102, length=2.2, t60=(1.8, 1.5, 0.6), predelay=0.03, early=20, early_span=0.16, early_gain=0.7, fade_in=0.035)
S.IR_PRESETS["early_only"] = dict(seed=7103, length=0.12, t60=(0.25, 0.2, 0.1), predelay=0.002, early=14, early_span=0.03, early_gain=0.9)

FFSL, FF = B.FFSL, B.FF
Z0 = B.Z0
KRPG = B.KRPG
R75, RMW, RS2, THIM, STEAM, WS = B.R75, B.RMW, B.RS2, B.THIM, B.STEAM, B.WS
SG = ("oga_shotgun_reload_zer0sol", "x/shotgunsounds/ShotgunSounds/")
KUI = ("oga_kenney_ui", "x/UI_SFX_Set/")
ELEC = B.ELEC


def kr(name, **kw):
    return rec(KRPG[0], KRPG[1] + name, **kw)


def ws(name, **kw):
    return rec(WS[0], WS[1] % name, **kw)


def varispeed(x, ratio_fn):
    """Resample with a time-varying speed ratio (cubic interpolation)."""
    out = []
    p = 0.0
    L = len(x)
    while p < L - 3:
        k = int(p)
        f = p - k
        xm1 = x[k - 1] if k >= 1 else 0.0
        x0, x1, x2 = x[k], x[k + 1], x[k + 2]
        a = (-xm1 + 3 * x0 - 3 * x1 + x2) * 0.5
        b = xm1 - 2.5 * x0 + 2 * x1 - 0.5 * x2
        c = (x1 - xm1) * 0.5
        out.append(((a * f + b) * f + c) * f + x0)
        p += ratio_fn(len(out) / SR)
    return out


def env(x, pts):
    return S.mul(x, S.env_pts(len(x), pts))


def seg(x, t0, dur, fin=0.002, fout=0.02):
    return S.fade(x[N(t0): N(t0 + dur)], fin, fout)


def peak_at(x, after=0.0):
    i0 = N(after)
    return (i0 + max(range(len(x) - i0), key=lambda i: abs(x[i0 + i]))) / SR


# ==========================================================================
# 1) weapon mechanics
# ==========================================================================
def build_mechanics():
    begin("rifle_mag_release", "BMacZero 'clipload2' (CC0, small latch clicks) slowed to 0.9x, HP 250 Hz; synthesized release-button click (modal) in front and a short polymer/metal friction burst (mag starting to slide); small-room IR (wet 0.08)")
    c = unit(S.hp(snap(rec("oga_gun_reload_bmaczero", "clipload2.wav", speed=0.9), -24, 0.002), 250))
    btn = S.click(random.Random(1001), 3300, 850, 0.006, 0.06, 0.8)
    fr = S.friction(0.09, random.Random(1002), 1700, 1.2, 220, 0.03)
    y = S.mix((btn, 0.5, 0), (c, 1.0, 0.012), (fr, 0.35, 0.03))
    out("rifle_mag_release", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -2.0)

    for k, f in enumerate(["bfh1_metal_falling_03.ogg", "bfh1_metal_falling_04.ogg"]):
        name = "rifle_mag_drop_%d" % k
        begin(name, "rubberduck '75 CC0 breaking/falling/hit' %s (CC0, small metal object hitting the floor and bouncing), onset-trimmed, pitch %s, HP 120 Hz, 4-pole LP 7 kHz (tames the small-object ring); synthesized low floor-contact thud under the first hit; concrete-room IR (wet 0.12)" % (f, ("0.95x", "1.05x")[k]))
        x = unit(S.lp4(S.hp(snap(rec(R75[0], R75[1] + f, speed=(0.95, 1.05)[k]), -22, 0.002), 120), 7000))
        th = S.thump(0.15, 220, 110, 0.01, 0.025)
        y = S.mix((x, 1.0, 0), (th, 0.25, 0.002))
        out(name, S.trim_tail(S.reverb(y, "concrete_room_b", wet=0.12, wet_hp=200), -55), -1.0)

    begin("rifle_mag_pouch", "Kenney RPG Audio 'beltHandle2' (leather + buckle clinks, CC0) and 'cloth3' (first 0.3 s, CC0), HP 150 Hz; synthesized light magazine rattle (two modal clicks); small-room IR (wet 0.06)")
    a = unit(S.hp(snap(kr("beltHandle2.ogg"), -28, 0.004), 150))
    cl = unit(S.hp(seg(kr("cloth3.ogg"), 0.0, 0.3, 0.005, 0.08), 150))
    rnd = random.Random(1003)
    rat = S.mix((S.click(rnd, 2600, 700, 0.005, 0.05, 0.6), 1.0, 0), (S.click(rnd, 3400, 800, 0.004, 0.05, 0.5), 0.7, 0.05))
    y = S.mix((cl, 0.55, 0), (a, 1.0, 0.05), (rat, 0.18, 0.2))
    out("rifle_mag_pouch", S.trim_tail(S.reverb(y, "small_room", wet=0.06), -55), -4.0)

    begin("rifle_mag_seat", "BMacZero 'clipload1' (CC0, magazine/clip seating thunk) as the main hit, Kenney RPG 'metalLatch' (CC0) as the catch click 6 ms later, both HP 120 Hz; synthesized low seat body (modal 380/1050 Hz, short); small-room IR (wet 0.08)")
    a = unit(S.hp(snap(rec("oga_gun_reload_bmaczero", "clipload1.wav"), -20, 0.0015), 120))
    l = unit(S.hp(snap(kr("metalLatch.ogg"), -20, 0.001), 300))
    body = S.strike(0.12, random.Random(1004), [(380, 0.012, 1.0), (1050, 0.008, 0.5)], exc=0.0005, noise_amt=0.3)
    y = S.mix((a, 1.0, 0), (l, 0.55, 0.006), (body, 0.18, 0.0015))
    out("rifle_mag_seat", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -1.0)

    begin("rifle_bolt_release", "zer0sol 'Shotgun Reload' Shell in Chamber (CC0): the action slamming closed (1.02-1.36 s) slowed to 0.92x, HP 100 Hz; synthesized bolt-catch press click 25 ms ahead and a short low slam body (modal 520/1500 Hz); small-room IR (wet 0.1)")
    x = rec(SG[0], SG[1] + "Shell in Chamber.mp3", t0=1.0, dur=0.38, speed=0.92)
    x = unit(S.hp(snap(x, -22, 0.002), 100))
    pk = peak_at(x)
    catch = S.click(random.Random(1005), 3000, 800, 0.005, 0.05, 0.7)
    slam = S.strike(0.2, random.Random(1006), [(520, 0.02, 1.0), (1500, 0.014, 0.7), (2900, 0.008, 0.5)], exc=0.0004, noise_amt=0.4)
    y = S.mix((catch, 0.35, 0), (x, 1.0, 0.025), (slam, 0.18, 0.025 + pk))
    out("rifle_bolt_release", S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -1.0)

    begin("rifle_charge_pull", "zer0sol 'Shotgun Reload' Rack (CC0): the pull-back stroke (0.60-0.78 s) slowed to 0.9x, HP 120 Hz, with the zer0sol handgun slide pull (1.04-1.17 s, 0.85x, LP 7 kHz) layered at -8 dB for the sliding ring; small-room IR (wet 0.08)")
    a = unit(S.hp(seg(rec(SG[0], SG[1] + "Rack.mp3", t0=0.58, dur=0.22, speed=0.9), 0.0, 0.22, 0.004, 0.04), 120))
    b = unit(S.lp(S.hp(seg(rec(*Z0, t0=1.03, dur=0.15, speed=0.85), 0.0, 0.16, 0.004, 0.04), 150), 7000))
    y = S.mix((a, 1.0, 0), (b, 0.4, 0.01))
    out("rifle_charge_pull", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -1.0)

    begin("rifle_charge_release", "zer0sol 'Handgun Reload' slide-release slam (CC0) slowed to 0.8x (bolt carrier running home), HP 100 Hz, LP 8 kHz; Kenney RPG 'metalLatch' (CC0) 45 ms later as the charging handle latching; small-room IR (wet 0.1)")
    s = unit(S.lp(S.resample(B.slide_slam(), 0.8), 8000))
    l = unit(S.hp(snap(kr("metalLatch.ogg"), -20, 0.001), 300))
    y = S.mix((s, 1.0, 0), (l, 0.4, 0.045))
    out("rifle_charge_release", S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -1.0)

    begin("pistol_mag_release", "zer0sol 'Handgun Reload' (CC0) 0.07-0.40 s: magazine release and the magazine sliding out, HP 180 Hz, -3 dB at 350 Hz; synthesized release-button click in front; small-room IR (wet 0.08)")
    x = S.peq(S.hp(rec(*Z0, t0=0.06, dur=0.34), 180), 350, 1.0, -3)
    btn = S.click(random.Random(1007), 3800, 950, 0.005, 0.05, 0.7)
    y = S.mix((unit(x), 1.0, 0.01), (btn, 0.35, 0))
    out("pistol_mag_release", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -2.0)

    begin("pistol_mag_seat", "zer0sol 'Handgun Reload' (CC0) 0.56-0.92 s: magazine insertion and seat, HP 150 Hz; small-room IR (wet 0.08)", synth_layers=False)
    x = unit(S.hp(rec(*Z0, t0=0.55, dur=0.38), 150))
    out("pistol_mag_seat", S.trim_tail(S.reverb(x, "small_room", wet=0.08), -55), -2.0)

    begin("pistol_slide_rack", "zer0sol 'Handgun Reload' (CC0) 1.00-1.55 s: full slide rack (pull back + release slam) at original speed, HP 120 Hz; small-room IR (wet 0.08)", synth_layers=False)
    x = unit(S.hp(rec(*Z0, t0=1.0, dur=0.55), 120))
    out("pistol_slide_rack", S.trim_tail(S.reverb(x, "small_room", wet=0.08), -55), -1.0)

    begin("weapon_draw", "Kenney RPG Audio 'drawKnife3' (sheath draw scrape, CC0) slowed to 0.85x and 'cloth1' (first 0.3 s, CC0), HP 150 Hz; zer0sol handgun-reload grip tap (CC0, the slide-release slam at -14 dB, 0.85x) and a synthesized grip rattle at the end; small-room IR (wet 0.08)")
    d = unit(S.hp(snap(kr("drawKnife3.ogg", speed=0.85), -30, 0.004), 150))
    c = unit(S.hp(seg(kr("cloth1.ogg"), 0.0, 0.3, 0.004, 0.08), 150))
    tap = unit(S.resample(B.slide_slam(), 0.85))
    rnd = random.Random(1008)
    rat = S.mix((S.click(rnd, 2400, 650, 0.006, 0.06, 0.6), 1.0, 0), (S.click(rnd, 3600, 900, 0.004, 0.05, 0.5), 0.6, 0.03))
    y = S.mix((c, 0.5, 0), (d, 1.0, 0.04), (tap, 0.2, 0.32), (rat, 0.2, 0.33))
    out("weapon_draw", S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -3.0)

    begin("weapon_holster", "Kenney RPG Audio 'cloth2' and 'beltHandle1' (CC0) as the weapon going into the holster/sling, 'dropLeather' (CC0, HP 100 Hz, -6 dB) as the seat thud at the end; small-room IR (wet 0.06)")
    c = unit(S.hp(kr("cloth2.ogg"), 150))
    b = unit(S.hp(snap(kr("beltHandle1.ogg"), -28, 0.003), 150))
    t = unit(S.hp(snap(kr("dropLeather.ogg"), -24, 0.003), 100))
    y = S.mix((c, 0.6, 0), (b, 0.8, 0.12), (t, 0.5, 0.26))
    out("weapon_holster", S.trim_tail(S.reverb(y, "small_room", wet=0.06), -55), -3.0)

    begin("cloth_raise", "Kenney RPG Audio 'cloth1' (0.05-0.40 s) layered with HaelDB 'step_lth2' (leather creak, CC0) and 'step_cloth3' (CC0), HP 180 Hz, LP 10 kHz, gentle fades", synth_layers=False)
    c = unit(seg(kr("cloth1.ogg"), 0.05, 0.35, 0.01, 0.1))
    l = unit(rec("oga_steps_leather_cloth", "x/footsteps/footsteps/step_lth2.ogg"))
    s2 = unit(rec("oga_steps_leather_cloth", "x/footsteps/footsteps/step_cloth3.ogg"))
    y = S.lp(S.hp(S.mix((c, 1.0, 0), (l, 0.35, 0.06), (s2, 0.4, 0.02)), 180), 10000)
    out("cloth_raise", S.fade(y, 0.008, 0.08), -12.0)

    begin("selector_switch", "Kenney '51 UI sound effects' switch3 (a real mechanical switch, CC0), HP 400 Hz; synthesized metal detent click (modal 3.9 kHz cluster) 2 ms after the transient; small-room IR (wet 0.06)")
    sw = unit(S.hp(snap(rec(KUI[0], KUI[1] + "switch3.wav"), -24, 0.0015), 400))
    det = S.click(random.Random(1009), 3900, 1200, 0.004, 0.04, 0.8)
    y = S.mix((sw, 1.0, 0), (det, 0.35, peak_at(sw) + 0.002))
    out("selector_switch", S.trim_tail(S.reverb(y, "small_room", wet=0.06), -55), -3.0)


# ==========================================================================
# 2) shot layers
# ==========================================================================
def rifle_core(k):
    """The pre-reverb rifle chain of audio_build.build_gunshots (variant k)."""
    rel, t = B.RIFLE_SRC[k]
    rnd = random.Random(100 + k)
    d = B.shot_direct(rel, t, 0.17)
    crack = S.mul(S.hp(S.white(N(0.01), rnd), 3000), S.env_exp(N(0.01), 0.00002, 0.0015))
    dry = S.mix((d, 1.0, 0), (crack, 0.25, 0), (S.gun_mech(200 + k, "rifle"), 0.04, 0.003))
    dry = S.peq(dry, 2600, 0.8, 2.0)
    return S.softclip(unit(S.compress(dry, -18, 3.0, 0.0002, 0.05, 3)), 1.4)


def pistol_core(k):
    rel, t = B.PISTOL_SRC[k]
    rnd = random.Random(110 + k)
    d = B.shot_direct(rel, t, 0.14)
    crack = S.mul(S.hp(S.white(N(0.01), rnd), 3500), S.env_exp(N(0.01), 0.00002, 0.0012))
    dry = S.mix((d, 1.0, 0), (crack, 0.22, 0), (S.gun_mech(210 + k, "pistol"), 0.04, 0.002))
    dry = S.peq(dry, 3000, 0.8, 1.5)
    return S.softclip(unit(S.compress(dry, -18, 3.0, 0.0002, 0.05, 3)), 1.3)


def _master(y, drive_db):
    return S.softclip(S.limiter(S.gain(unit(y), S.db(drive_db)), 0.95, 0.0015, 0.05), 1.2)


def spring_twang(seed, sec=0.14):
    """AR buffer-spring 'sproing': two inharmonic spring modes with a slight
    downward glide and 70 Hz flutter, excited by the carrier impact."""
    rnd = random.Random(seed)
    n = N(sec)
    f0 = rnd.uniform(1050, 1250)
    t1 = S.sweep_tone(n, lambda t: f0 * (1 - 0.06 * t / sec) * (1 + 0.01 * math.sin(S.TAU * 70 * t)), ((1, 1.0), (2.73, 0.45), (4.1, 0.2)))
    nz = S.bp(S.white(n, rnd), f0 * 2.2, 3)
    return S.mul([a + 0.3 * b for a, b in zip(t1, nz)], S.env_exp(n, 0.001, 0.03))


def build_shot_layers():
    for k in range(3):
        name = "rifle_mech_%d" % k
        begin(name, "bolt-carrier cycle heard close to the gun: zer0sol 'Handgun Reload' slide-release slam (CC0) slowed to %.2fx as the carrier hitting the buffer, the same slam at %.2fx 42-48 ms later as the carrier returning to battery, Kenney RPG 'metalClick' (CC0) transient; synthesized buffer-spring twang and modal clicks; small-room IR (wet 0.08)" % ((0.82, 0.78, 0.86)[k], (0.95, 0.9, 1.0)[k]))
        rnd = random.Random(1100 + k)
        slam = unit(B.slide_slam())
        back = S.fade(S.resample(slam, (0.82, 0.78, 0.86)[k])[: N(0.09)], 0.0005, 0.03)
        home = S.fade(S.resample(slam, (0.95, 0.9, 1.0)[k])[: N(0.12)], 0.0005, 0.04)
        mc = unit(S.hp(snap(kr("metalClick.ogg"), -20, 0.0005, 0.06), 400))
        syn = S.gun_mech(1110 + k, "rifle")
        tw = spring_twang(1120 + k)
        dt = (0.042, 0.048, 0.044)[k]
        y = S.mix((back, 0.8, 0), (mc, 0.3, 0.002), (syn, 0.35, 0.0), (tw, 0.12, 0.008), (home, 1.0, dt))
        out(name, S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55)[: N(0.4)], -2.0)

    # Room tails: wet-only renders of the rifle shot through new IRs.  Their
    # level is set relative to rifle_shot_dry_* (short-term loudness 8 dB
    # under the shot for the small room, 6 dB under for the hall), so the
    # game can play a tail at 0 dB together with a dry shot.
    for name, irn, L, desc in (
            ("shot_tail_small", "tail_small", 0.9, "small concrete room IR: 18 dense early reflections within 25 ms, 3-band decay T60 0.75/0.7/0.3 s"),
            ("shot_tail_hall", "tail_hall", 1.5, "large hall IR: 30 ms pre-delay, 20 early reflections over 160 ms plus discrete slap echoes at 85 and 190 ms, 3-band decay T60 1.8/1.5/0.6 s")):
        begin(name, "wet-only indoor reflection tail: the Free Firearm Sound Library AR-15 near shot chain (same as rifle_shot_0 without its baked tail) convolved with a synthesized %s; wet return HP 200 Hz, LP 9 kHz; %.1f s with a 0.3 s fade; level set relative to rifle_shot_dry_* (play both at 0 dB)" % (desc, L))
        core = rifle_core(0)
        ir_sig = S.ir(irn)
        if irn == "tail_hall":
            ir_sig = list(ir_sig)
            for t_e, g in ((0.085, 0.05), (0.19, 0.03)):
                i = N(t_e)
                for dd, h in enumerate((0.3, 1.0, 0.7, 0.35, 0.15)):
                    ir_sig[i + dd] += g * h
            ir_sig = S.lp(ir_sig, 8000)
        y = S.convolve(core, ir_sig, irn + "_m3")
        y = S.lp(S.hp(y, 200), 9000)
        out(name, S.fade(y[: N(L)], 0.0, 0.3), -1.0, fin=0.0)

    for k, t in enumerate((0.55, 3.91)):
        name = "shot_distant_%d" % k
        begin(name, "Free Firearm Sound Library AR-15 *mid-distance* recording (D_24P, shot %d, CC0) with its natural outdoor echoes, 4-pole LP 1.6 kHz, HP 50 Hz, +3 dB low shelf at 150 Hz, transient softened (compressor), through the synthesized large-hall IR (wet 0.5); 1.6 s with fade-out" % (k + 1))
        x = rec(FFSL, FF + "AR-15/D_24P.wav", t0=t - 0.05, dur=1.8)
        x = snap(x, -20, 0.003)[: N(1.6)]
        x = S.lshelf(S.hp(S.lp4(x, 1600), 50), 150, 3)
        x = S.compress(unit(x), -14, 3, 0.003, 0.08, 0)
        y = S.reverb(x, "tail_hall", wet=0.5, wet_hp=80)
        out(name, S.fade(y[: N(1.6)], 0.002, 0.4), -6.0)

    for k in range(3):
        name = "rifle_shot_dry_%d" % k
        begin(name, "OPTIONAL EXTRA (for use with shot_tail_*): rifle_shot_%d without the baked room tail - same Free Firearm Sound Library chain, only a 120 ms early-reflection IR (wet 0.3), synthesized sub thump, look-ahead limiter" % k)
        core = rifle_core(k)
        y = S.reverb(core, "early_only", wet=0.3, wet_hp=200)
        y = S.mix((y, 1.0, 0), (S.thump(0.3, 120, 50, 0.018, 0.06, drive=1.4), 0.4, 0.0005))
        out(name, S.trim_tail(_master(y, 7.0), -60)[: N(0.45)], -1.0)
    for k in range(3):
        name = "pistol_shot_dry_%d" % k
        begin(name, "OPTIONAL EXTRA (for use with shot_tail_*): pistol_shot_%d without the baked room tail - same Free Firearm Sound Library chain, 120 ms early-reflection IR (wet 0.28), sub thump, limiter" % k)
        core = pistol_core(k)
        y = S.reverb(core, "early_only", wet=0.28, wet_hp=250)
        y = S.mix((y, 1.0, 0), (S.thump(0.25, 160, 58, 0.014, 0.045, drive=1.4), 0.33, 0.0005))
        out(name, S.trim_tail(_master(y, 6.0), -60)[: N(0.4)], -1.0)


# ==========================================================================
# 3) robot
# ==========================================================================
def capacitor_whine(seed=1301, sec=1.2):
    rnd = random.Random(seed)
    n = N(sec)
    f = lambda t: 380.0 * (14.0 ** ((t / sec) ** 1.6))
    jit = [0.0] * n
    j = 0.0
    for i in range(n):  # growing pitch instability
        if i % 240 == 0:
            j = (rnd.random() - 0.5) * 0.012 * (i / n) ** 2
        jit[i] = j
    ph = ph2 = 0.0
    w = [0.0] * n
    for i in range(n):
        t = i / SR
        fi = f(t) * (1 + jit[i] + 0.003 * math.sin(S.TAU * 41 * t))
        ph += S.TAU * fi / SR
        ph2 += S.TAU * fi * 1.007 / SR
        a = (t / sec) ** 1.3
        w[i] = a * (math.sin(ph) + 0.35 * math.sin(2 * ph) + 0.2 * math.sin(3.01 * ph) + 0.6 * math.sin(ph2))
    coil = S.sweep_tone(n, lambda t: f(t) * 2.76, ((1, 1.0),))
    coil = S.mul(coil, [(i / n) ** 3 for i in range(n)])
    hum = S.mul(S.lp(S.mains_hum(n, 50), 900), [(i / n) ** 1.5 for i in range(n)])
    cr = S.mul(S.crackle(sec, rnd, 8, 1400, amp_pow=2.0, band=(1800, 11000)), [0.15 + 0.85 * (i / n) ** 2.5 for i in range(n)])
    bz = S.mul(S.arc_buzz(sec, rnd, 50, 10, 3200), [(i / n) ** 4 for i in range(n)])
    y = S.mix((w, 0.45, 0), (coil, 0.12, 0), (hum, 0.1, 0), (cr, 0.8, 0), (bz, 0.35, 0))
    return S.fade(S.hp(y, 70), 0.02, 0.008)


def build_robot():
    for k in range(4):
        name = "robot_step_heavy_%d" % k
        begin(name, "running footfall: Thimras 'metal footsteps on concrete' step (CC0) slowed to %.2fx, HP 40 Hz; synthesized sub thump (125->32 Hz, drive), low-passed impact noise and armour clank (from robot_step), bart 'steam hisses' (CC0) as a short 0.15 s pressure pfft, debris ticks; concrete-room IR (wet 0.16)" % (0.58, 0.61, 0.6, 0.63)[k])
        rnd = random.Random(1200 + k)
        st = unit(S.hp(snap(rec(THIM[0], THIM[1] + "metal_steps_%02d.wav" % (5 + 5 * k), speed=(0.58, 0.61, 0.6, 0.63)[k]), -20, 0.001), 40))
        h = rec(STEAM[0], STEAM[1] % (1 + (k + 2) % 5), t0=0.3, dur=0.25)
        h = S.mul(unit(S.hp(h, 2500)), S.env_exp(len(h), 0.005, 0.05))
        sub = S.thump(0.45, 125, 32, 0.02, 0.13, drive=2.0)
        syn = S.robot_step_synth(1210 + k)
        y = S.mix((st, 1.0, 0), (syn, 0.6, 0), (sub, 0.6, 0), (h, 0.12, 0.03))
        y = S.reverb(y, "concrete_room_b", wet=0.16)
        out(name, S.trim_tail(y, -58)[: N(0.8)], -1.0)

    scr = [("scrape5", 0.9, 0.7), ("scrape4", 1.0, 0.65), ("dragging metal", 3.45, 0.72)]
    for k, (f, t0, sp) in enumerate(scr):
        name = "robot_scuff_%d" % k
        begin(name, "bart '68 Workshop Sounds' '%s' (CC0, metal scraping), %.2f s of source from %.2f s slowed to %.2fx (0.6 s) for weight, HP 60 Hz, LP 7 kHz, swell/decay envelope; synthesized low friction rumble (low-passed brown noise) and grit crackle; concrete-room IR (wet 0.12)" % (f, 0.6 * sp, t0, sp))
        rnd = random.Random(1220 + k)
        x = ws(f, t0=t0, dur=0.5, speed=sp)[: N(0.6)]
        x = env(unit(S.lp(S.hp(x, 60), 7000)), [(0, 0), (0.04, 1), (0.3, 0.8), ((len(x) - 1) / SR, 0)])
        n = len(x)
        rum = env(unit(S.lp(S.brown(n, rnd, 0.99), 180)), [(0, 0), (0.05, 1), ((n - 1) / SR, 0)])
        gr = S.crackle(n / SR, rnd, 250, burst_ms=(0.03, 0.3), band=(2500, 9000))
        y = S.mix((x, 1.0, 0), (rum, 0.35, 0), (gr, 0.12, 0))
        out(name, S.trim_tail(S.reverb(y, "concrete_room_b", wet=0.12), -55), -3.0)

    drills = [("drill1", 0.2, 0.75, 0.2), ("drill2", 0.15, 0.7, 0.26), ("drill4", 0.0, 0.8, 0.18), ("drill5", 0.0, 0.72, 0.3)]
    for k, (d, t0, sp, L) in enumerate(drills):
        name = "robot_servo_short_%d" % k
        begin(name, "bart '68 Workshop Sounds' '%s' (CC0) motor burst slowed to %.2fx, HP 120 Hz, %.2f s with fast rise/fall; layered with a short synthesized geared-servo whir (harmonic motor tone + gear-mesh band + stop tick)" % (d, sp, L))
        x = unit(S.hp(snap(ws(d, t0=t0, dur=L + 0.2, speed=sp), -24, 0.003), 120))[: N(L)]
        x = env(x, [(0, 0), (0.012, 1), (L * 0.6, 0.85), (L, 0)])
        syn = unit(S.servo(1230 + k, L, (150, 170, 140, 160)[k], (300, 340, 280, 260)[k], 13, k % 2 == 0))
        y = S.mix((x, 0.8, 0), (syn, 0.5, 0))
        out(name, S.trim_tail(y, -55), -6.0)

    for k, (m, t0, L) in enumerate(((1, 0.1, 0.5), (3, 0.4, 0.65), (4, 0.2, 0.45))):
        name = "robot_hydraulic_hiss_%d" % k
        begin(name, "bart 'steam hisses' Marker #%d (CC0) %.2f s segment, HP 500 Hz, sharp attack and exponential release; synthesized valve click at the start; small-room IR (wet 0.08)" % (m, L))
        h = rec(STEAM[0], STEAM[1] % m, t0=t0, dur=L)
        h = env(unit(S.hp(h, 500)), [(0, 0), (0.008, 1), (L * 0.35, 0.75), (L, 0)])
        v = S.click(random.Random(1240 + k), 1900, 420, 0.008, 0.06, 0.8)
        y = S.mix((v, 0.3, 0), (h, 1.0, 0.004))
        out(name, S.trim_tail(S.reverb(y, "small_room", wet=0.08), -55), -6.0)

    begin("robot_stagger", "rubberduck '100 CC0 metal and wood' metal_hit_04 (CC0, heavy clank), HP 80 Hz, with a synthesized armour-plate hit underneath; 'servo protest': bart cordless-drill recording (CC0) varispeed-strained (0.48-0.7x with stutter) plus a synthesized low geared servo with grinding AM; sub thump; concrete-room IR (wet 0.18)")
    rnd = random.Random(1250)
    cl = unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_hit_04.ogg"), -20, 0.001, 0.5), 80))
    pl = unit(S.plate_hit(1251, 330))
    dr = unit(S.hp(snap(ws("drill2", t0=0.15, dur=0.8), -24, 0.003), 120))
    prot = varispeed(dr, lambda t: 0.48 + 0.22 * math.sin(math.pi * min(1.0, t / 0.5)) + 0.04 * math.sin(S.TAU * 11 * t))[: N(0.55)]
    prot = env(unit(prot), [(0, 0), (0.03, 1), (0.4, 0.7), (0.55, 0)])
    sv = unit(S.servo(1252, 0.5, 90, 150, 17, False))
    grind = S.tone(len(sv), 23.0)
    sv = [v * (0.6 + 0.4 * abs(g)) for v, g in zip(sv, grind)]
    sub = S.thump(0.4, 110, 38, 0.02, 0.1, drive=1.6)
    y = S.mix((cl, 0.9, 0), (pl, 0.5, 0), (sub, 0.6, 0), (prot, 0.45, 0.09), (sv, 0.3, 0.1))
    out("robot_stagger", S.trim_tail(S.reverb(y, "concrete_room", wet=0.18), -58)[: N(1.1)], -1.0)

    brk = [("metal_sheet_03.ogg", "bfh1_metal_falling_02.ogg", 0.32), ("metal_sheet_06.ogg", "bfh1_metal_falling_03.ogg", 0.28), ("metal_sheet_01.ogg", "bfh1_metal_falling_04.ogg", 0.36)]
    for k, (sh, fall, tf) in enumerate(brk):
        name = "robot_armor_break_%d" % k
        begin(name, "plate tearing off: synthesized bolt-shear crack (strong modal click + HP noise) and spark crackle, bart workshop 'scrape5' (CC0) sped up 1.5x as the tear (0.12 s), rubberduck '%s' (CC0, sheet-metal bend/wobble, HP 100 Hz) and rubberduck '%s' (CC0) at %.2f s as the plate hitting the floor; concrete-room IR (wet 0.2)" % (sh, fall, tf))
        rnd = random.Random(1260 + k)
        shear = S.mix((S.click(rnd, 2400, 700, 0.02, 0.15, 1.0), 1.0, 0), (S.mul(S.hp(S.white(N(0.02), rnd), 2500), S.env_exp(N(0.02), 0.00002, 0.002)), 0.8, 0))
        tear = unit(S.hp(seg(ws("scrape5", t0=1.0, dur=0.3, speed=1.5), 0.0, 0.12, 0.003, 0.04), 300))
        sheet = unit(S.hp(snap(rec(RMW[0], RMW[1] + sh), -20, 0.001), 100))
        fl = unit(S.hp(snap(rec(R75[0], R75[1] + fall), -20, 0.001), 80))
        sp = S.crackle(0.25, rnd, 1200, 60, burst_ms=(0.03, 0.4), band=(2500, 12000))
        y = S.mix((shear, 0.7, 0), (sp, 0.25, 0.002), (tear, 0.6, 0.01), (sheet, 0.9, 0.02), (fl, 0.6, tf))
        out(name, S.trim_tail(S.reverb(y, "concrete_room", wet=0.2), -58)[: N(1.3)], -1.0)

    col = [("rmw", "metal_falling_01.ogg", (0.0, 0.3)), ("ws", "loud clatter", (0.0, 0.24))]
    for k, (src, f, hits) in enumerate(col):
        name = "robot_collapse_%d" % k
        what = "rubberduck '100 CC0 metal and wood' metal_falling_01" if src == "rmw" else "bart '68 Workshop Sounds' 'loud clatter'"
        begin(name, "heavy body hitting the floor: %s (CC0, metal crash/clatter, HP 60 Hz) with bart 'Metal clang sounds' Marker #8 (CC0, first 0.8 s, slowed 0.7x) under the first hit; synthesized impacts (sub thumps 95->28 Hz, low-passed impact noise, plate modes) at %.2f and %.2f s, settling debris ticks; concrete-room IR (wet 0.3)" % (what, hits[0], hits[1]))
        rnd = random.Random(1270 + k)
        x = rec(RMW[0], RMW[1] + f) if src == "rmw" else ws(f)
        x = unit(S.hp(snap(x, -20, 0.002), 60))[: N(1.4)]
        x = S.fade(x, 0.001, 0.3)
        clang = unit(S.hp(seg(rec("oga_metal_clangs_bart", "x/clangs/clang - Marker #8.wav", dur=0.6, speed=0.7), 0.0, 0.8, 0.001, 0.3), 60))
        y = S.mix((x, 0.8, 0.0), (clang, 0.35, hits[0]))
        for t, g in zip(hits, (1.0, 0.75)):
            S.add_at(y, S.thump(0.6, 95, 28, 0.03, 0.22, drive=1.8), t, g)
            S.add_at(y, S.noise_hit(0.3, rnd, 1400, 100, 0.01, 0.06), t, 0.6 * g)
            b = rnd.uniform(160, 230)
            S.add_at(y, S.strike(0.6, rnd, [(b, 0.14, 1.0), (b * 2.6, 0.1, 0.8), (b * 4.3, 0.07, 0.6), (b * 7.1, 0.045, 0.45)], exc=0.0006, spread=0.03, noise_amt=0.4), t + 0.003, 0.4 * g)
        for _ in range(10):
            S.add_at(y, S.click(rnd, rnd.uniform(1800, 5000), 600, 0.008, 0.06, 0.8), rnd.uniform(0.4, 1.1), rnd.uniform(0.04, 0.12))
        out(name, S.trim_tail(S.reverb(y, "concrete_room", wet=0.3), -60)[: N(1.8)], -1.0)

    begin("robot_capacitor_whine", "synthesized 1.2 s overload: rising capacitor/inverter whine (380 Hz -> 5.3 kHz, beating partials, growing pitch instability), coil overtone, swelling 50 Hz hum, accelerating crackle and arc buzz; BMacZero 'continuousspark.wav' (real Tesla-generator arcs, CC0) repeated and swelling over the last 0.6 s; ends abruptly (8 ms) for the overload burst; small-room IR (wet 0.12)")
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 500))
    cs3 = cs + cs + cs
    cs3 = S.mul(cs3, [(i / len(cs3)) ** 2 for i in range(len(cs3))])
    y = S.mix((unit(capacitor_whine()), 1.0, 0), (cs3, 0.35, 1.2 - len(cs3) / SR))
    y = S.reverb(y, "small_room", wet=0.12)[: N(1.2)]
    out("robot_capacitor_whine", S.fade(y, 0.02, 0.008), -3.0, fout=0.008)


# ==========================================================================
# 4) ambience (stereo, seamless)
# ==========================================================================
def wind(sec, rnd, xf=None):
    """Wind through a large opening: noise through a band-pass whose centre
    and level follow periodic gust curves (periodic over 'sec'), plus a
    faint resonant whistle.  Filtered circularly, so it loops seamlessly."""
    n = N(sec)
    g = S.slow_mod(n, rnd, sec, (1, 2, 3, 5), 0.55)
    gl = S.slow_mod(n, rnd, sec, (2, 3, 4), 0.35)
    fc = [380 + 260 * (v - 0.45) for v in g]
    x = S.white(n, rnd)
    body = S.circ(x, lambda s: S.svf(s, lambda t: fc[int(t * SR) % n], 0.9, "bp"))
    body = [v * max(0.0, a) ** 1.5 for v, a in zip(body, g)]
    whis = S.circ(S.white(n, rnd), lambda s: S.svf(s, lambda t: 1.6 * fc[int(t * SR) % n] + 520, 14.0, "bp"))
    whis = [v * max(0.0, a - 0.9) ** 2 for v, a in zip(whis, gl)]
    low = S.circ(S.white(n, rnd), lambda s: S.lp(S.lp(s, 90), 90))
    low = [v * max(0.0, a) for v, a in zip(low, g)]
    return [0.6 * b + 0.25 * w + 2.0 * l for b, w, l in zip(body, whis, low)]


def _mix_st(*layers):
    n = min(len(c[0]) for c, _ in layers)
    return [[sum(c[ch][i] * gg for c, gg in layers) for i in range(n)] for ch in range(2)]


def _norm_st(st):
    m = max(S.peak(st[0]), S.peak(st[1])) or 1.0
    return [[v / m for v in c] for c in st]


def build_ambience():
    L = 12.0
    begin("ambience_dock", "12 s seamless stereo loop of a large loading bay: synthesized wind through the bay door (band-passed noise with periodic gust curves, resonant whistle, low buffeting; circular filtering), rubberduck '100 CC0 SFX #2' air_01 (CC0, slowed 0.8x, LP 3 kHz) as wind texture bed, Longor 'Airvent Loop' (CC0, LP 1.5 kHz) as ventilation hum with a quiet synthesized 50 Hz mains hum; occasional metal ticks (synthesized modal ticks) and one distant creak (w.forster 'Creaky Door Hinge', CC0, 0.6x, LP 2 kHz) through the 3.5 s industrial-hall IR; beds equal-power crossfaded, events wrapped tail-into-head")
    chans = []
    air = S.lp(rec(RS2[0], RS2[1] + "sfx100v2_air_01.ogg", speed=0.8), 3000)
    av = S.lp(rec("oga_airvent_loop", "airvent-large-loop.wav"), 1500)
    cr = rec("oga_creaky_hinge", "creaky_door_hinge.wav", t0=0.6, dur=1.2, speed=0.6)
    cr = env(unit(S.lp(S.hp(cr, 200), 2000)), [(0, 0), (0.2, 1), (1.6, 0.7), ((len(cr) - 1) / SR, 0)])
    for ch in range(2):
        rnd = random.Random(1401 + 31 * ch)
        n = N(L)
        wd = wind(L, rnd)
        airb = bed(air, L, 0.6, offsets=((0.0, 0.9), (0.5, 1.3))[ch])
        vent = bed(av, L, 1.0, offsets=((0.0, 2.5), (3.7, 1.2))[ch])
        hum = S.circ(S.mains_hum(n, 50), lambda s: S.lp(s, 400))
        ev = S.zeros(N(L + 4.0))
        for _ in range(5):
            S.add_at(ev, S.click(rnd, rnd.uniform(1600, 3800), rnd.uniform(400, 800), rnd.uniform(0.01, 0.03), 0.15, 0.7), rnd.uniform(0.2, L), rnd.uniform(0.3, 0.7))
        S.add_at(ev, cr, (4.5, 9.0)[ch], 0.12)
        ev = S.lp(S.reverb(ev, "industrial_hall", wet=1.0, dry=0.15), 6000)[: N(L + 3.5)]
        ev = S.loop_xfade(ev, 3.5)
        chans.append((unit(wd), unit(airb), unit(vent), unit(hum), unit(ev)))
    st = lambda i: [chans[0][i], chans[1][i]]
    y = _mix_st((st(0), 0.55), (st(1), 0.18), (st(2), 0.4), (st(3), 0.03), (st(4), 0.35))
    out("ambience_dock", y, -18.0, loop=True)

    L2 = 10.0
    begin("ambience_control", "10 s seamless stereo loop of a control room: synthesized equipment hum (50 Hz mains harmonics with 100 Hz transformer buzz, slow periodic level drift, faint 2.2 kHz electronics whine), qubodup '(defect) motor loop' GPU-fan recording (CC0, LP 2.5 kHz, low level) as the soft fan, synthesized pink-noise room tone; occasional relay clicks from CleytonKauffman 'SFX - Circuit breaker' switch on/off (CC0) and Kenney '51 UI sound effects' switch16/switch18 (CC0), HP 300 Hz, through a small-room IR; beds crossfaded, events wrapped tail-into-head")
    f = rec("oga_fan_loop_qubodup", "fan_interval.wav", stereo=True)
    f = [S.lp(S.hp(c, 80), 2500) for c in f]
    relays = [unit(S.hp(snap(rec("oga_circuit_breaker", "x/Circuit_Breaker/switch on.wav"), -24, 0.002, 0.3), 300)),
              unit(S.hp(snap(rec("oga_circuit_breaker", "x/Circuit_Breaker/switch off.wav"), -24, 0.002, 0.3), 300)),
              unit(S.hp(snap(rec(KUI[0], KUI[1] + "switch16.wav"), -24, 0.002), 300)),
              unit(S.hp(snap(rec(KUI[0], KUI[1] + "switch18.wav"), -24, 0.002), 300))]
    chans = []
    for ch in range(2):
        rnd = random.Random(1501 + 17 * ch)
        n = N(L2)
        hum = S.mains_hum(n, 50, ((2, 1.0), (1, 0.35), (4, 0.4), (6, 0.25), (3, 0.2), (8, 0.12), (10, 0.06)))
        hum = S.mul(S.circ(hum, lambda s: S.lp(s, 1200)), S.slow_mod(n, rnd, L2, (1, 2), 0.12))
        whine = S.tone(n, round(2200 * L2) / L2 + ch * 0.0, ((1, 1.0),))
        room = S.circ(S.pink(n, rnd), lambda s: S.lp(S.hp(s, 60), 5000))
        fan = bed(f[ch], L2, 0.6, offsets=((0.0, 1.1), (0.4, 1.7))[ch])
        ev = S.zeros(N(L2 + 0.8))
        times = ((1.3, 4.6, 7.9), (2.4, 6.1, 9.2))[ch]
        for i, t in enumerate(times):
            S.add_at(ev, relays[(i + 2 * ch) % 4], t, rnd.uniform(0.5, 1.0))
        ev = S.reverb(ev, "small_room", wet=0.3)[: N(L2 + 0.6)]
        ev = S.loop_xfade(ev, 0.6)
        chans.append((unit(hum), unit(whine), unit(room), unit(fan), unit(ev)))
    st = lambda i: [chans[0][i], chans[1][i]]
    y = _mix_st((st(0), 0.5), (st(1), 0.012), (st(2), 0.25), (st(3), 0.3), (st(4), 0.35))
    out("ambience_control", y, -21.0, loop=True)


GROUPS = [build_mechanics, build_shot_layers, build_robot, build_ambience]


def write_sources(rows):
    names = [r[0] for r in rows]
    by = {r[0]: r for r in rows}
    used = sorted({s for n in names for s, _ in B.PROV.get(n, {}).get("sources", [])})
    n_rec = n_syn = n_pure = 0
    body = []
    for n in names:
        p = B.PROV.get(n)
        r = by[n]
        body.append("### %s.wav" % n)
        body.append("- format: 16-bit PCM, %d Hz, %s, %.2f s; peak %.1f dBFS, mean %.1f dBFS, max 100 ms RMS %.1f dBFS%s" % (r[2], "stereo" if r[3] == 2 else "mono", r[4], r[5], r[6], r[7], ("; " + r[8]) if r[8] else ""))
        if not p:
            body.append("- source: (not built by this script)")
            body.append("")
            continue
        if p["sources"]:
            n_rec += 1
            for s, rel in p["sources"]:
                m = B._src_meta(s)
                inner = "/".join(rel.split("/")[2:]) if rel.startswith("x/") else rel
                body.append("- source: \"%s\" by %s, file `%s` - %s (download %s) - licence CC0" % (m["title"], B._author(m), inner, m["page"], B._file_url(m, rel)))
            if p["synth"]:
                body.append("- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)")
            else:
                n_pure += 1
        else:
            n_syn += 1
            body.append("- source: synthesized (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)")
        body.append("- processing: %s" % p["proc"])
        body.append("")
    head = ["# BREACH audio M3 (staging/audio_m3) - sources and processing", "",
            "Rebuild: `python -I tools/m2/audio_m3.py` (uses the CC0 downloads already in staging/audio/raw/; no new downloads were needed).",
            "All recordings are CC0 1.0 (licence verified on each asset's OpenGameArt page, stored in raw/<id>/SOURCE.json). Everything else is synthesized, first-party work of this project.",
            "",
            "Format: 16-bit PCM WAV, 48 kHz; mono for all positional sounds, stereo only for ambience_* loops.",
            "Summary: %d outputs use CC0 recordings (%d edited recordings only, %d layered with synthesis); %d are fully synthesized." % (n_rec, n_pure, n_rec - n_pure, n_syn),
            "",
            "Loudness: one-shots follow the same short-term loudness hierarchy as M2 (max 100 ms RMS): weapon mechanics -19..-27, cloth_raise -31, "
            "rifle_mech -21 (meant to sit under a shot), shot_distant -22, robot_collapse -13, robot_step_heavy -14.5, robot_stagger/armor_break -15, "
            "robot_capacitor_whine -18, robot servos/hiss/scuff -22/-23. shot_tail_small -18.5 and shot_tail_hall -16.5, i.e. 8 / 6 dB under rifle_shot_dry_* "
            "(play both at 0 dB). rifle_shot_dry_* / pistol_shot_dry_* are optional extras matching rifle_shot_* / pistol_shot_* levels. "
            "Ambience loops sit at about -31 dBFS mean like the M2 beds and are checked for a seamless end-to-start join.",
            "",
            "## Source assets", "", "| id (raw/ dir) | asset | author | licence | page |", "|---|---|---|---|---|"]
    for s in used:
        m = B._src_meta(s)
        lic = "CC0" if m["licenses"] == ["CC0"] else "CC0 (dual-licensed: %s; used under CC0)" % " / ".join(m["licenses"])
        head.append("| %s | %s | %s | %s | %s |" % (s, m["title"], B._author(m), lic, m["page"]))
    head += ["", "## Output files", ""]
    with open(os.path.join(M3, "SOURCES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(head + body) + "\n")
    print("SOURCES.md: %d with recordings (%d pure), %d fully synthesized" % (n_rec, n_pure, n_syn))


def main(argv):
    if "--validate" in argv:
        B.validate()
        return
    sel = [a for a in argv if not a.startswith("-")]
    os.makedirs(M3, exist_ok=True)
    for g in GROUPS:
        if sel:
            consts = g.__code__.co_consts
            if not any(isinstance(c, str) and any(c.startswith(s) for s in sel) for c in consts):
                continue
        t0 = time.time()
        g()
        print("[%s] %.1f s" % (g.__name__, time.time() - t0), flush=True)
    B.finalize()
    rows = B.validate()
    if not sel:
        write_sources(rows)
    if os.path.isdir(S.WORK):
        for f in os.listdir(S.WORK):
            os.remove(os.path.join(S.WORK, f))
        os.rmdir(S.WORK)


if __name__ == "__main__":
    main(sys.argv[1:])
