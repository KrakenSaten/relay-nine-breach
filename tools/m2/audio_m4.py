# M4 audio for BREACH (mission expansion): alarm and facility machinery,
# lift, breaker, robot wake-up, capacitor / core destruction, three more
# ambience loops, arcing and duct footsteps.  Builds staging/audio_m4/ from the
# CC0 material in staging/audio/raw/ (one extra CC0 pack: bart's chain winch,
# fetched with tools/m2/audio_fetch.py) plus synthesis.  Deterministic.
#
#   python -I tools/m2/audio_m4.py            # build all + validate + SOURCES.md
#   python -I tools/m2/audio_m4.py lift_      # only groups that produce matching names
#   python -I tools/m2/audio_m4.py --validate
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import synth_audio_v2 as S  # noqa: E402
import audio_build as B  # noqa: E402
import audio_m3 as M3  # noqa: E402  (re-uses its helpers; its settings are overridden below)

M4 = os.path.join(B.ROOT, "staging", "audio_m4")
S.WORK = os.path.join(M4, "_work")
B.OUT = M4
SR, N = S.SR, S.N
rec, snap, unit, bed, begin, out = B.rec, B.snap, B.unit, B.bed, B.begin, B.out
env, seg, peak_at, varispeed = M3.env, M3.seg, M3.peak_at, M3.varispeed

# short-term loudness targets (max 100 ms RMS, dBFS), same hierarchy as M2/M3
B.ST_TARGET = {
    "alarm_loop": -17.0, "relay_voice_beep": -22.0, "blast_door_open": -15.0,
    "lift_motor_loop": -24.0, "lift_arrive": -16.0, "lift_call": -24.0,
    "breaker_close": -14.0, "breaker_hum_rise": -20.0, "robot_wake": -18.0,
    "capacitor_hit": -17.0, "capacitor_destroyed": -12.0, "core_overload": -9.0,
    "arc_crackle": -22.0, "crawl_step": -25.0,
}

S.IR_PRESETS["duct"] = dict(seed=7201, length=0.35, t60=(0.3, 0.25, 0.12), predelay=0.001, early=24, early_span=0.008, early_gain=1.2, fade_in=0.002)

RMW, R75, RS2, STEAM, WS, THIM = B.RMW, B.R75, B.RS2, B.STEAM, B.WS, B.THIM
LOOPS = ("oga_30_loops_rubberduck", "x/sfx_loops/")
KUI = M3.KUI
KI = ("oga_kenney_interface", "x/kenney_interfaceSounds/Audio/")
KSF = ("oga_kenney_scifi", "x/sci-fi_sounds/Audio/")
ELEC = B.ELEC
BRK = ("oga_circuit_breaker", "x/Circuit_Breaker/")
WINCH = ("oga_chain_winch_bart", "x/winch/winch - Marker #9.wav")


def lp_(name, **kw):
    return rec(LOOPS[0], LOOPS[1] + name, **kw)


def ws(name, **kw):
    return rec(WS[0], WS[1] % name, **kw)


def fold(ev, L_sec):
    """Wrap a longer event track into a loop of L_sec (time aliasing): an
    event's tail that runs past the end continues at the loop start."""
    n = N(L_sec)
    o = [0.0] * n
    for i, v in enumerate(ev):
        o[i % n] += v
    return o


def circ_reverb(x, name, wet, dry=1.0, wet_hp=120.0):
    """Steady-state (circular) reverb of a loop x: process three periods and
    keep the last, so the tail of the end wraps into the start.  Requires the
    IR to be shorter than two periods."""
    P = len(x)
    y = S.reverb(x + x + x, name, wet=wet, dry=dry, wet_hp=wet_hp)
    return y[2 * P: 3 * P]


def whole(f, L):
    """Nearest frequency with a whole number of cycles in L seconds."""
    return round(f * L) / L


def heavy_clunk(rnd, base=140.0, sec=0.6):
    modes = [(base, 0.12, 1.0), (base * 2.3, 0.08, 0.8), (base * 3.9, 0.06, 0.6), (base * 6.2, 0.04, 0.45), (base * 9.7, 0.025, 0.35)]
    return S.mix((S.strike(sec, rnd, modes, exc=0.0008, spread=0.03, noise_amt=0.5), 0.6, 0), (S.thump(sec, 110, 38, 0.02, 0.1, drive=1.6), 1.0, 0), (S.noise_hit(0.3, rnd, 1800, 120, 0.008, 0.04), 0.5, 0))


def _mix_st(*layers):
    return M3._mix_st(*layers)


# ==========================================================================
# alarm and announcements
# ==========================================================================
def horn(sec, f_fn, rnd):
    """Industrial horn: two slightly detuned band-limited saws (rough, beating),
    horn formants, hard saturation."""
    n = N(sec)
    a = S.sweep_tone(n, f_fn, S.saw_harm(28, 1.0))
    b = S.sweep_tone(n, lambda t: f_fn(t) * 1.028, S.saw_harm(28, 1.0))
    sub = S.sweep_tone(n, lambda t: f_fn(t) * 0.5, ((1, 1.0),))
    x = [p + 0.75 * q + 0.12 * s for p, q, s in zip(a, b, sub)]
    x = S.peq(S.peq(S.peq(S.lp(S.hp(x, 110), 4500), 560, 1.2, 8), 1450, 1.4, 9), 2600, 2.0, 5)
    return S.hp(S.softclip(unit(x), 2.6), 90)


def build_alarm():
    begin("alarm_loop", "synthesized 3.2 s seamless klaxon loop: two low industrial horn blasts per cycle (detuned saw pair ~half a semitone apart for a rough beating tone, faint sub-octave, HP 110 Hz, 560/1450/2600 Hz horn formants, hard saturation): a rising 150->166 Hz blast then a longer falling 146->116 Hz blast; circular (steady-state) convolution with a synthesized 3.5 s industrial-hall IR so the reverb tail wraps across the loop point; LP 6 kHz; loop rotated so it starts in the tail, first blast at 0.32 s")
    rnd = random.Random(2001)
    P = 3.2
    x = S.zeros(N(P))
    b1 = horn(1.0, lambda t: 150 + 16 * min(1.0, t / 0.18) - 3 * max(0.0, t - 0.5), rnd)
    b2 = horn(1.25, lambda t: 146 - 30 * max(0.0, (t - 0.15) / 1.1) ** 1.3, rnd)
    S.add_at(x, env(b1, [(0, 0), (0.06, 1), (0.86, 0.9), (1.0, 0)]), 0.02)
    S.add_at(x, env(b2, [(0, 0), (0.07, 1), (1.05, 0.85), (1.25, 0)]), 1.35)
    x = x[: N(P)]
    y = circ_reverb(x, "industrial_hall", wet=0.55, dry=0.8, wet_hp=150)
    y = S.circ(y, lambda s: S.lp(s, 6000))
    r = N(2.9)  # rotate so the loop point sits in the reverb tail between blasts
    y = y[r:] + y[:r]
    out("alarm_loop", y, -3.0, loop=True)

    specs = [
        (((0.0, 0.075, 1046.5), (0.095, 0.11, 1568.0)), 220.0, 260.0, "glitch_001.ogg", "two rising tones (C6 -> G6)"),
        (((0.0, 0.05, 1318.5), (0.065, 0.05, 1046.5), (0.13, 0.09, 1318.5)), 240.0, 200.0, "glitch_002.ogg", "three short tones (E6-C6-E6)"),
        (((0.0, 0.26, None),), 200.0, 180.0, "glitch_003.ogg", "a 35 Hz FM warble around 1.2 kHz falling at the end"),
    ]
    for k, (notes, b0, b1f, gl, what) in enumerate(specs):
        name = "relay_voice_beep_%d" % k
        begin(name, "synthesized 'system announcement' chirp (no speech): %s over a formant-filtered synthetic voice buzz (saw %d->%d Hz through moving vowel-like formants), radio band-limit 350 Hz-3.4 kHz, sample-and-hold bit-crush to 12 kHz; Kenney 'Interface Sounds' %s (CC0) as a digital squelch at the start" % (what, b0, b1f, gl))
        rnd = random.Random(2010 + k)
        total = max(t + d for t, d, _ in notes) + 0.06
        n = N(total)
        buzz = S.sweep_tone(n, lambda t: b0 + (b1f - b0) * t / total, S.saw_harm(30, 1.0))
        buzz = S.svf(buzz, lambda t: 700 + 900 * math.sin(math.pi * t / total) ** 2, 4.0, "bp")
        buzz = env(unit(buzz), [(0, 0), (0.01, 1), (total - 0.03, 0.8), (total, 0)])
        tones = S.zeros(n)
        for t0, d, f in notes:
            if f is None:
                tt = S.sweep_tone(N(d), lambda t: 1200 + 150 * math.sin(S.TAU * 35 * t) - 500 * max(0.0, t - d + 0.07) / 0.07, ((1, 1.0), (2, 0.2), (3, 0.08)))
            else:
                tt = S.tone(N(d), f, ((1, 1.0), (2, 0.25), (3, 0.1)))
            S.add_at(tones, env(tt, [(0, 0), (0.004, 1), (d - 0.012, 0.85), (d, 0)]), t0 + 0.02)
        y = S.mix((tones, 0.7, 0), (buzz, 0.35, 0.02))
        y = S.lp(S.hp(y[:n], 350), 3400)
        hold = int(SR / 12000)
        y = [y[i - i % hold] for i in range(len(y))]  # sample-and-hold
        y = S.lp(y, 5000)
        g = unit(S.hp(rec(KI[0], KI[1] + gl), 500))
        y = S.mix((y, 1.0, 0.0), (g, 0.25, 0.0))
        out(name, S.trim_tail(y, -55), -6.0)


# ==========================================================================
# doors, lift, breaker
# ==========================================================================
def build_machinery():
    begin("blast_door_open", "heavy hydraulic blast door, 3.6 s: three locking-bolt retractions (rubberduck 'metal_slam_01' (CC0), BMacZero 'clank1' (CC0), rubberduck 'metal_hit_04' (CC0), each over a synthesized low modal clunk + sub thump), bart 'steam hisses' Marker #2 (CC0) as the hydraulic release, then the slide: rubberduck '30 CC0 SFX loops' rolling.ogg (CC0, slowed 0.45x, looped) + loop machine_11 (CC0, 0.7x, LP 800 Hz) + bart workshop 'dragging metal' (CC0, 0.6x, LP 2.5 kHz) + synthesized sub rumble, all with a ramp-up/ramp-down envelope; end-stop clunk; concrete-room IR (wet 0.3)")
    rnd = random.Random(2101)
    T = 3.6
    y = S.zeros(N(T + 0.5))
    bolts = [unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_slam_01.ogg", speed=0.8), -20, 0.001), 40)),
             unit(S.hp(snap(rec("oga_mechanical_bmaczero", "clank1.wav", speed=0.75), -20, 0.001), 40)),
             unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_hit_04.ogg", speed=0.7), -20, 0.001), 40))]
    for i, (t, bsrc) in enumerate(zip((0.0, 0.2, 0.42), bolts)):
        S.add_at(y, bsrc, t, 0.55)
        S.add_at(y, heavy_clunk(rnd, rnd.uniform(120, 170)), t, 0.7)
    h = rec(STEAM[0], STEAM[1] % 2, t0=0.1, dur=1.3)
    h = env(unit(S.hp(h, 600)), [(0, 0), (0.01, 1), (0.4, 0.8), (1.3, 0)])
    S.add_at(y, h, 0.55, 0.45)
    slide_t0, slide_d = 0.75, 2.55
    rl = unit(S.hp(lp_("rolling.ogg", speed=0.45), 30))
    rl = bed(rl, slide_d, 0.3, offsets=(0.0, 0.5))
    mo = unit(S.lp(lp_("machine_11.ogg", speed=0.7), 800))[: N(slide_d)]
    dr = unit(S.lp(ws("dragging metal", t0=3.45, dur=1.6, speed=0.6), 2500))[: N(slide_d)]
    rum = unit(S.lp(S.brown(N(slide_d), rnd, 0.995), 120))
    sl = S.mix((rl, 0.8, 0), (mo, 0.45, 0), (dr, 0.25, 0), (rum, 0.6, 0))
    sl = env(sl[: N(slide_d)], [(0, 0), (0.35, 1), (slide_d - 0.5, 0.9), (slide_d, 0)])
    S.add_at(y, sl, slide_t0, 0.8)
    S.add_at(y, heavy_clunk(rnd, 110, 0.8), slide_t0 + slide_d - 0.08, 0.9)
    S.add_at(y, unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_slam_01.ogg", speed=0.65), -20, 0.001), 40)), slide_t0 + slide_d - 0.08, 0.45)
    y = S.reverb(y, "concrete_room_c", wet=0.3)
    out("blast_door_open", S.fade(S.trim_tail(y, -60)[: N(4.0)], 0.001, 0.3), -1.0)

    L = 4.0
    begin("lift_motor_loop", "4.0 s seamless loop: synthesized freight-lift motor (50 Hz mains harmonics, rotor whine 412.5 Hz + slot harmonic, whole cycles over the loop, slight periodic load swell) + rubberduck '30 CC0 SFX loops' machine_11 (CC0, 0.8x, LP 1.5 kHz) and bart 'Chain winch sounds' Marker #9 (CC0, 0.8x, LP 3 kHz, low level) as cable/chain run, both made into seamless beds by equal-power crossfades; circular LP 6 kHz")
    rnd = random.Random(2110)
    n = N(L)
    hum = S.mains_hum(n, 50.0)
    whine = S.tone(n, whole(412.5, L), ((1, 1.0), (2, 0.35), (3.0, 0.1)))
    swell = [1.0 + 0.08 * math.sin(S.TAU * i / n) for i in range(n)]
    mot = S.mul(S.mix((S.circ(hum, lambda s: S.lp(s, 600)), 1.0, 0), (whine, 0.08, 0)), swell)
    m11 = bed(S.lp(lp_("machine_11.ogg", speed=0.8), 1500), L, 0.5, offsets=(0.0, 1.3))
    wch = rec(*WINCH, t0=0.4, dur=1.8, speed=0.8)
    wch = bed(S.lp(S.hp(wch, 120), 3000), L, 0.4, offsets=(0.0, 0.7))
    y = S.mix((unit(mot), 0.7, 0), (unit(m11), 0.6, 0), (unit(wch), 0.2, 0))[:n]
    y = S.circ(y, lambda s: S.lp(s, 6000))
    out("lift_motor_loop", y, -6.0, loop=True)

    begin("lift_arrive", "heavy lift arriving, ~2.4 s: the lift-motor layers (synthesized motor + rubberduck machine_11 + bart chain winch, CC0) varispeed-decelerating to a stop over 1.1 s, a heavy stop clunk (BMacZero 'clank1' (CC0) slowed 0.7x over a synthesized low clunk + sub thump) at 1.1 s, a gate rattle at 1.35 s (BMacZero 'rattle1' + bart workshop 'metal clatter', CC0); concrete-room IR (wet 0.25)")
    B._note(LOOPS[0], LOOPS[1] + "machine_11.ogg")
    B._note(*WINCH)
    rnd = random.Random(2120)
    run = S.mix((unit(mot), 0.7, 0), (unit(m11), 0.6, 0), (unit(wch), 0.25, 0))
    run = run + run
    dec = varispeed(run, lambda t: max(0.25, 1.0 - 0.7 * (t / 1.1) ** 1.5))[: N(1.25)]
    dec = env(dec, [(0, 0.0), (0.08, 1), (0.9, 0.8), (1.25, 0)])
    y = S.zeros(N(2.6))
    S.add_at(y, unit(dec), 0.0, 0.45)
    S.add_at(y, heavy_clunk(rnd, 125, 0.7), 1.1, 1.0)
    S.add_at(y, unit(S.hp(snap(rec("oga_mechanical_bmaczero", "clank1.wav", speed=0.7), -20, 0.001), 40)), 1.1, 0.5)
    S.add_at(y, unit(S.hp(rec("oga_mechanical_bmaczero", "rattle1.wav"), 150)), 1.35, 0.45)
    S.add_at(y, unit(S.hp(snap(ws("metal clatter"), -20, 0.002), 150)), 1.38, 0.4)
    y = S.reverb(y, "concrete_room", wet=0.25)
    out("lift_arrive", S.fade(S.trim_tail(y, -60)[: N(2.6)], 0.002, 0.25), -1.0)

    begin("lift_call", "qubodup 'Metal Interactions' metal_button_press2 (CC0), HP 150 Hz; relay clunk 0.22 s later: CleytonKauffman 'SFX - Circuit breaker' switch off (CC0) slowed 0.75x over a synthesized small low clunk (modal 180/420 Hz); small-room IR (wet 0.1)")
    rnd = random.Random(2130)
    bt = unit(S.hp(snap(rec("oga_metal_interactions_qubodup", "x/metal_interactions/metal_interactions/metal_button_press2.wav"), -24, 0.002), 150))
    rl = unit(S.hp(snap(rec(BRK[0], BRK[1] + "switch off.wav", speed=0.75), -24, 0.002), 120))
    ck = S.strike(0.2, rnd, [(180, 0.04, 1.0), (420, 0.025, 0.6), (1100, 0.012, 0.3)], exc=0.0008, noise_amt=0.4)
    y = S.mix((bt, 1.0, 0), (rl, 0.8, 0.22), (ck, 0.35, 0.22))
    out("lift_call", S.trim_tail(S.reverb(y, "small_room", wet=0.1), -55), -3.0)

    begin("breaker_close", "large main breaker closing: CleytonKauffman 'SFX - Circuit breaker' switch on (CC0) slowed 0.6x (lever throw), rubberduck 'metal_slam_01' (CC0) as the lever slamming home, BMacZero 'spark.wav' (real arc, CC0) as the arc snap; synthesized crack, 60 ms mains-synchronous arc buzz, sub thump; concrete-room IR (wet 0.25)")
    rnd = random.Random(2140)
    lev = unit(S.hp(snap(rec(BRK[0], BRK[1] + "switch on.wav", speed=0.6), -24, 0.002), 80))
    pk = peak_at(lev)
    sl = unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_slam_01.ogg"), -20, 0.001), 40))
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 200))
    crack = S.mul(S.hp(S.white(N(0.02), rnd), 1500), S.env_exp(N(0.02), 0.00002, 0.0015))
    bz = S.mul(S.arc_buzz(0.08, rnd, 50, 6, 2800), S.env_exp(N(0.08), 0.001, 0.03))
    th = S.thump(0.4, 110, 40, 0.02, 0.09, drive=1.6)
    y = S.mix((lev, 0.6, 0), (sl, 0.9, pk), (th, 0.7, pk), (crack, 0.7, pk + 0.003), (sp, 0.8, pk + 0.003), (bz, 0.5, pk + 0.004))
    out("breaker_close", S.trim_tail(S.reverb(y, "concrete_room_b", wet=0.25), -58)[: N(1.4)], -1.0)

    begin("breaker_hum_rise", "synthesized transformer energizing, 1.5 s: inrush thump, 50 Hz mains hum with 100 Hz dominant and harmonics up to 600 Hz rising in level and richness (higher harmonics arrive later), mains-synchronous magnetostriction rasp (gated noise, BP 1.8 kHz) rising; ends at full level with a short fade")
    rnd = random.Random(2150)
    T = 1.5
    n = N(T)
    hum = S.zeros(n)
    for h, a, lag in ((2, 1.0, 0.0), (1, 0.35, 0.0), (4, 0.45, 0.15), (6, 0.3, 0.3), (3, 0.2, 0.2), (8, 0.18, 0.45), (12, 0.08, 0.6)):
        part = S.tone(n, 50.0 * h, ((1, 1.0),), phase=rnd.uniform(0, S.TAU))
        e = [max(0.0, min(1.0, (i / SR - lag) / (T - lag))) ** 0.8 for i in range(n)]
        hum = [v + a * p * q for v, p, q in zip(hum, part, e)]
    rasp = S.mul(S.arc_buzz(T, rnd, 50, 14, 1800, 0.7, 0.02), [(i / n) ** 1.6 for i in range(n)])
    inrush = S.thump(0.4, 90, 45, 0.03, 0.12)
    y = S.mix((unit(hum), 1.0, 0), (unit(rasp), 0.12, 0), (inrush, 0.5, 0))
    out("breaker_hum_rise", S.fade(y[:n], 0.003, 0.04), -3.0)


# ==========================================================================
# robot wake, capacitors, core
# ==========================================================================
def build_power():
    begin("robot_wake", "dormant robot powering up, 2.0 s: relay clicks (Kenney '51 UI sound effects' switch18 and switch16, CC0; CleytonKauffman circuit breaker switch off at -8 dB, CC0), a swelling 50 Hz power hum, rising servo whine (bart workshop 'drill5' (CC0) varispeed 0.35x -> 0.85x plus a synthesized rising geared servo), an optic hum (synthesized 880 -> 1320 Hz tone with 12 Hz tremolo and a focus chirp at 1.45 s), two servo twitch clicks; concrete-room IR (wet 0.15)")
    rnd = random.Random(2201)
    T = 2.0
    y = S.zeros(N(T + 0.4))
    S.add_at(y, unit(S.hp(snap(rec(KUI[0], KUI[1] + "switch18.wav"), -24, 0.002), 300)), 0.0, 0.35)
    S.add_at(y, unit(S.hp(snap(rec(BRK[0], BRK[1] + "switch off.wav"), -24, 0.002), 200)), 0.05, 0.3)
    S.add_at(y, unit(S.hp(snap(rec(KUI[0], KUI[1] + "switch16.wav"), -24, 0.002), 300)), 0.16, 0.3)
    n = N(T)
    hum = S.mul(S.lp(S.mains_hum(n, 50.0), 700), [min(1.0, max(0.0, (i / SR - 0.2) / 0.8)) for i in range(n)])
    S.add_at(y, unit(hum), 0.0, 0.18)
    dr = unit(S.hp(snap(ws("drill5", dur=2.0), -24, 0.003), 120))
    sv = varispeed(dr, lambda t: 0.35 + 0.5 * min(1.0, t / 1.1) ** 1.3)[: N(1.4)]
    sv = env(unit(sv), [(0, 0), (0.15, 0.7), (1.1, 1.0), (1.4, 0)])
    S.add_at(y, sv, 0.3, 0.45)
    syn = unit(S.servo(2202, 1.2, 70, 260, 13, True))
    S.add_at(y, syn, 0.35, 0.25)
    n2 = N(1.2)
    opt = S.sweep_tone(n2, lambda t: 880 + 440 * min(1.0, t / 0.6) ** 2, ((1, 1.0), (2, 0.15), (3, 0.05)))
    trem = S.tone(n2, 12.0)
    opt = [v * (0.75 + 0.25 * tr) for v, tr in zip(opt, trem)]
    opt = env(opt, [(0, 0), (0.15, 0.6), (0.6, 1.0), (1.2, 0.9)])
    S.add_at(y, opt, 0.8, 0.07)
    chirp = env(S.sweep_tone(N(0.09), lambda t: 1500 + 9000 * t, ((1, 1.0),)), [(0, 0), (0.005, 1), (0.09, 0)])
    S.add_at(y, chirp, 1.45, 0.06)
    for t in (1.22, 1.7):
        S.add_at(y, S.click(rnd, 2600, 600, 0.008, 0.06, 0.7), t, 0.25)
    y = S.reverb(y[: N(T)], "concrete_room_b", wet=0.15)
    out("robot_wake", S.fade(y[: N(T + 0.2)], 0.002, 0.2), -2.0)

    hits = [("bfh1_glass_hit_01.ogg", (RMW, "metal_hit_03.ogg")), ("bfh1_glass_hit_02.ogg", (RMW, "metal_hit_05.ogg")), ("bfh1_glass_breaking_02.ogg", (R75, "bfh1_metal_hit_02.ogg"))]
    for k, (gf, (mp, mf)) in enumerate(hits):
        name = "capacitor_hit_%d" % k
        begin(name, "bullet on a capacitor stack: rubberduck '%s' (CC0, glass) and '%s' (CC0, metal), onset-trimmed, HP 250 Hz; synthesized dense crackle burst, discharge buzz and a 3.4 kHz glassy ping%s; concrete-room IR (wet 0.12)" % (gf, mf, "; BMacZero 'spark.wav' (CC0)" if k == 2 else ""))
        rnd = random.Random(2210 + k)
        g = unit(S.hp(snap(rec(R75[0], R75[1] + gf), -20, 0.001, 0.45), 250))
        m = unit(S.hp(snap(rec(mp[0], mp[1] + mf), -20, 0.001, 0.45), 250))
        cr = S.mul(S.crackle(0.35, rnd, 2500, 150, amp_pow=1.5, band=(1500, 12000)), S.env_exp(N(0.35), 0.0005, 0.08))
        bz = S.mul(S.arc_buzz(0.15, rnd, 50, 6, 3000), S.env_exp(N(0.15), 0.001, 0.04))
        ping = S.strike(0.4, rnd, [(3400, 0.09, 1.0), (6900, 0.05, 0.4), (1700, 0.05, 0.3)], exc=0.0002, noise_amt=0.2)
        y = S.mix((g, 0.8, 0), (m, 0.6, 0.0005), (cr, 0.7, 0.002), (bz, 0.35, 0.004), (ping, 0.25, 0.001))
        if k == 2:
            S.add_at(y, unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 300)), 0.003, 0.5)
        out(name, S.trim_tail(S.reverb(y, "concrete_room_b", wet=0.12), -58)[: N(0.8)], -1.0)

    begin("capacitor_destroyed", "capacitor bank failing, 2.5 s: crack (rubberduck 'bfh1_glass_breaking_01' + 'metal_hit_02', CC0), burst (Kenney 'Sci-Fi Sounds' explosionCrunch_000 and lowFrequency_explosion_001, CC0), electrical roar (synthesized dense arc crackle + 50 Hz arc buzz + BMacZero 'continuousspark.wav' (CC0) repeated, decaying over 1.8 s with stutters), falling debris (rubberduck 'bfh1_glass_falling_02' and 'bfh1_metal_falling_04', CC0); concrete-room IR (wet 0.3), compression")
    rnd = random.Random(2230)
    T = 2.5
    y = S.zeros(N(T + 0.5))
    S.add_at(y, unit(S.hp(snap(rec(R75[0], R75[1] + "bfh1_glass_breaking_01.ogg"), -20, 0.001), 200)), 0.0, 0.7)
    S.add_at(y, unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_hit_02.ogg"), -20, 0.001), 200)), 0.0, 0.5)
    S.add_at(y, unit(snap(rec(KSF[0], KSF[1] + "explosionCrunch_000.ogg"), -20, 0.002)), 0.04, 0.9)
    S.add_at(y, unit(snap(rec(KSF[0], KSF[1] + "lowFrequency_explosion_001.ogg"), -20, 0.002)), 0.04, 0.7)
    n = N(1.9)
    roar = S.mix((S.crackle(1.9, rnd, 3500, 300, amp_pow=1.5, band=(900, 12000)), 1.0, 0), (S.arc_buzz(1.9, rnd, 50, 5, 2400, 0.7), 0.6, 0))
    stut = [1.0 if (math.sin(S.TAU * 7 * i / SR) > -0.3 or i < N(0.4)) else 0.25 for i in range(n)]
    roar = S.mul(S.mul(roar[:n], stut), S.env_pts(n, [(0, 0), (0.03, 1), (0.6, 0.7), (1.9, 0)]))
    S.add_at(y, unit(roar), 0.05, 0.55)
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
    for t in (0.1, 0.35, 0.6, 0.9):
        S.add_at(y, cs, t, 0.35 * (1.0 - t))
    S.add_at(y, unit(S.hp(snap(rec(R75[0], R75[1] + "bfh1_glass_falling_02.ogg"), -24, 0.002), 300)), 0.55, 0.25)
    S.add_at(y, unit(S.hp(snap(rec(R75[0], R75[1] + "bfh1_metal_falling_04.ogg"), -24, 0.002), 150)), 0.8, 0.3)
    S.add_at(y, S.thump(0.6, 90, 30, 0.03, 0.2, drive=2.0), 0.04, 0.7)
    y = S.compress(unit(y), -14, 3, 0.002, 0.1, 0)
    y = S.reverb(y, "concrete_room_c", wet=0.3)
    out("capacitor_destroyed", S.fade(S.trim_tail(y, -60)[: N(T + 0.3)], 0.001, 0.4), -1.0)

    begin("core_overload", "finale multi-stage discharge, 5.0 s: (1) synthesized 1.4 s capacitor overload whine (from audio_m3) with BMacZero arc recordings (CC0); (2) first discharge at 1.4 s - synthesized tesla-style crack/thump + BMacZero 'spark.wav' + Kenney 'Sci-Fi Sounds' lowFrequency_explosion_001 (CC0) - followed by an electrical roar; (3) second, bigger discharge at 2.4 s with Kenney explosionCrunch_002 (CC0); (4) a fast 0.8 s re-charge whine; (5) the final burst at 3.3 s: Kenney lowFrequency_explosion_000 + explosionCrunch_000 (CC0), rubberduck 'bfh1_glass_breaking_03' and 'metal_falling_02' debris (CC0), dense crackle; whole mix compressed, sent through the synthesized 3.5 s industrial-hall IR (wet 0.35), then 6 dB into a look-ahead limiter")
    rnd = random.Random(2240)
    T = 5.0
    y = S.zeros(N(T + 1.0))
    w1 = unit(M3.capacitor_whine(2241, 1.4))
    S.add_at(y, w1, 0.0, 0.45)
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
    for t in (0.7, 0.95, 1.15):
        S.add_at(y, cs, t, 0.2)
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 200))
    lfe1 = unit(snap(rec(KSF[0], KSF[1] + "lowFrequency_explosion_001.ogg"), -20, 0.002))
    d1 = unit(S.tesla_shot(2242))
    S.add_at(y, d1, 1.4, 0.6)
    S.add_at(y, sp, 1.4, 0.5)
    S.add_at(y, lfe1, 1.4, 0.5)
    n = N(1.0)
    roar = S.mix((S.crackle(1.0, rnd, 3000, 800, amp_pow=1.5, band=(900, 12000)), 1.0, 0), (S.arc_buzz(1.0, rnd, 50, 5, 2400, 0.7), 0.7, 0))
    S.add_at(y, unit(env(roar[:n], [(0, 0), (0.05, 1), (0.8, 0.8), (1.0, 0.3)])), 1.45, 0.3)
    S.add_at(y, unit(S.tesla_shot(2243)), 2.4, 0.75)
    S.add_at(y, unit(snap(rec(KSF[0], KSF[1] + "explosionCrunch_002.ogg"), -20, 0.002)), 2.4, 0.6)
    S.add_at(y, sp, 2.4, 0.5)
    w2 = unit(M3.capacitor_whine(2244, 0.8))
    S.add_at(y, w2, 2.5, 0.45)
    n3 = N(1.7)
    S.add_at(y, unit(env(S.crackle(1.7, rnd, 1500, 40, amp_pow=1.6, band=(900, 12000)), [(0, 0), (0.02, 1), (1.7, 0)])), 2.45, 0.3)
    t3 = 3.3
    S.add_at(y, unit(snap(rec(KSF[0], KSF[1] + "lowFrequency_explosion_000.ogg"), -20, 0.002)), t3, 1.0)
    S.add_at(y, unit(snap(rec(KSF[0], KSF[1] + "explosionCrunch_000.ogg"), -20, 0.002)), t3, 0.8)
    S.add_at(y, unit(S.tesla_shot(2245)), t3, 0.7)
    S.add_at(y, sp, t3, 0.5)
    S.add_at(y, S.thump(1.0, 80, 24, 0.04, 0.35, drive=2.2), t3, 0.9)
    S.add_at(y, unit(S.hp(snap(rec(R75[0], R75[1] + "bfh1_glass_breaking_03.ogg"), -24, 0.002), 300)), t3 + 0.25, 0.25)
    S.add_at(y, unit(S.hp(snap(rec(RMW[0], RMW[1] + "metal_falling_02.ogg"), -24, 0.002), 100)), t3 + 0.45, 0.3)
    y = S.compress(unit(y[: N(T)]), -16, 3, 0.002, 0.15, 0)
    y = S.reverb(y, "industrial_hall", wet=0.35, wet_hp=60)
    y = S.softclip(S.limiter(S.gain(unit(y), S.db(6.0)), 0.95, 0.002, 0.08), 1.2)
    out("core_overload", S.fade(y[: N(T)], 0.002, 0.6), -1.0)

    arcs = [(0.35, "continuousspark"), (0.55, "spark"), (0.75, "synth")]
    for k, (d, kind) in enumerate(arcs):
        name = "arc_crackle_%d" % k
        src = {"continuousspark": "BMacZero 'continuousspark.wav' (real Tesla-generator arc pulses, CC0), HP 400 Hz, two bursts", "spark": "BMacZero 'spark.wav' (real arc, CC0), HP 300 Hz", "synth": "BMacZero 'continuousspark.wav' (CC0) at the start"}[kind]
        begin(name, "short transformer arcing, %.2f s: %s, layered with synthesized Poisson crackle and stuttering mains-synchronous arc buzz; small-room IR (wet 0.12)" % (d, src))
        rnd = random.Random(2260 + k)
        n = N(d)
        cr = S.crackle(d, rnd, (1800, 1200, 2200)[k], (600, 200, 900)[k], amp_pow=1.7, band=(1200, 12000))
        bz = S.arc_buzz(d, rnd, 50, 6, rnd.uniform(2200, 3400))
        fst = rnd.uniform(6, 11)
        st_ = [1.0 if math.sin(S.TAU * fst * i / SR) > -0.2 else 0.2 for i in range(n)]
        syn = S.mul(S.mix((cr, 1.0, 0), (bz, 0.6, 0))[:n], S.mul(st_, S.env_pts(n, [(0, 0), (0.003, 1), (d * 0.6, 0.7), (d, 0)])))
        y = [v for v in unit(syn)]
        if kind == "continuousspark":
            cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
            y = S.mix((y, 0.6, 0), (cs, 0.8, 0.0), (cs, 0.5, 0.15))
        elif kind == "spark":
            sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 300))
            y = S.mix((y, 0.6, 0), (sp, 0.9, 0.0))
        else:
            cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
            y = S.mix((y, 0.9, 0), (cs, 0.4, 0.0))
        out(name, S.trim_tail(S.reverb(y, "small_room", wet=0.12), -55)[: N(d + 0.1)], -2.0)


# ==========================================================================
# duct footsteps
# ==========================================================================
def build_crawl():
    sheets = ["metal_sheet_05.ogg", "metal_sheet_04.ogg", "metal_sheet_02.ogg", "metal_sheet_01.ogg"]
    steps = ["StoneL1", "StoneR2", "StoneL3", "StoneR1"]
    for k in range(4):
        name = "crawl_step_%d" % k
        begin(name, "cramped duct step: Fantozzi 'Stone' footstep (CC0, %s, pitch varied) used as excitation for a synthesized thin sheet-metal duct resonator bank (7 modes 140-1500 Hz) plus the dry step, rubberduck '%s' (CC0, sheet metal flex, HP 120 Hz) at -6 dB, two small rattle clicks; synthesized duct IR (24 dense reflections within 8 ms, T60 0.25 s)" % (steps[k], sheets[k]))
        rnd = random.Random(2301 + k)
        x = unit(S.hp(snap(rec(B.FANT[0], B.FANT[1] + "Fantozzi-%s.flac" % steps[k], speed=(0.96, 1.04, 1.0, 0.93)[k]), -26, 0.003, 0.3), 90))
        b = rnd.uniform(135, 165)
        modes = [(b, 0.16, 1.0), (b * 2.07, 0.12, 0.8), (b * 3.2, 0.1, 0.6), (b * 4.5, 0.08, 0.5), (b * 6.6, 0.05, 0.4), (b * 8.3, 0.035, 0.3), (b * 10.9, 0.025, 0.25)]
        duct = unit(S.resonators(S.hp(x, 100), modes, len(x) + N(0.35)))
        sh = unit(S.hp(snap(rec(RMW[0], RMW[1] + sheets[k]), -20, 0.001, 0.35), 120))
        rat = S.mix((S.click(rnd, rnd.uniform(2500, 4000), 700, 0.004, 0.04, 0.6), 1.0, 0), (S.click(rnd, rnd.uniform(2500, 4000), 700, 0.004, 0.04, 0.6), 0.7, rnd.uniform(0.04, 0.09)))
        y = S.mix((x, 0.8, 0), (duct, 0.6, 0), (sh, 0.5, 0.004), (rat, 0.12, 0.02))
        y = S.reverb(y, "duct", wet=0.35, wet_hp=100)
        out(name, S.trim_tail(y, -55)[: N(0.7)], -6.0)


# ==========================================================================
# ambience (stereo, seamless)
# ==========================================================================
def drip(rnd):
    n = N(0.15)
    f0 = rnd.uniform(900, 1600)
    t = S.sweep_tone(n, lambda tt: f0 * (1 + 1.3 * min(1.0, tt / 0.018)), ((1, 1.0), (2.1, 0.1)))
    return S.mul(t, S.env_exp(n, 0.0004, 0.03))


def build_ambience():
    L = 12.0
    begin("ambience_pump", "12 s seamless stereo loop of a large pump room: rubberduck '100 CC0 SFX #2' loop_water_01 / loop_water_03 (CC0, water flow, LP 7 kHz) as L/R-decorrelated beds, rubberduck '30 CC0 SFX loops' pump_01 (CC0, 0.7x, LP 2.5 kHz) as the pump, synthesized pump drone (29.5 Hz harmonics with a 1.5 Hz pumping pulse, whole cycles over the loop); synthesized water drips through the industrial-hall IR, time-wrapped across the loop point; beds equal-power crossfaded")
    w1 = S.lp(rec(RS2[0], RS2[1] + "sfx100v2_loop_water_01.ogg"), 7000)
    w3 = S.lp(rec(RS2[0], RS2[1] + "sfx100v2_loop_water_03.ogg"), 7000)
    pm = S.lp(lp_("pump_01.ogg", speed=0.7), 2500)
    chans = []
    for ch in range(2):
        rnd = random.Random(2401 + 13 * ch)
        n = N(L)
        wa = bed(w1 if ch == 0 else w3, L, 1.0, offsets=((0.0, 2.0), (1.0, 3.5))[ch])
        wb = bed(w3 if ch == 0 else w1, L, 1.0, offsets=((4.0, 0.5), (2.5, 5.0))[ch])
        pb = bed(pm, L, 0.6, offsets=((0.0, 1.5), (0.8, 2.2))[ch])
        dr = S.tone(n, whole(29.5, L), ((1, 1.0), (2, 0.6), (3, 0.4), (4, 0.2), (6, 0.1)))
        pulse = [0.7 + 0.3 * max(0.0, math.sin(S.TAU * whole(1.5, L) * i / SR)) ** 2 for i in range(n)]
        dr = S.circ(S.mul(dr, pulse), lambda s: S.lp(s, 300))
        ev = S.zeros(N(L + 3.5))
        for _ in range(9):
            S.add_at(ev, drip(rnd), rnd.uniform(0.0, L), rnd.uniform(0.3, 1.0))
        ev = fold(S.reverb(ev, "industrial_hall", wet=0.8, dry=0.5), L)
        chans.append((unit(wa), unit(wb), unit(pb), unit(dr), unit(ev)))
    st = lambda i: [chans[0][i], chans[1][i]]
    y = _mix_st((st(0), 0.45), (st(1), 0.3), (st(2), 0.4), (st(3), 0.35), (st(4), 0.25))
    out("ambience_pump", y, -18.0, loop=True)

    L2 = 10.0
    begin("ambience_switchgear", "10 s seamless stereo loop of a switchgear room: synthesized transformer hum (100 Hz dominant with 50/150/200/300/400/600 Hz, slow periodic drift, whole cycles), mains-synchronous magnetostriction rasp (gated noise, circular filtering), qubodup '(defect) motor loop' fan recording (CC0, stereo, LP 4 kHz) and qubodup 'Electronic device loop' (CC0, low level) as cooling fans; two faint arc ticks (BMacZero 'spark.wav', CC0) through a small-room IR, time-wrapped; beds crossfaded")
    f = rec("oga_fan_loop_qubodup", "fan_interval.wav", stereo=True)
    f = [S.lp(S.hp(c, 70), 4000) for c in f]
    e = S.hp(rec("oga_edev_loop_qubodup", "qubodup-edev.flac"), 150)
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 400))
    chans = []
    for ch in range(2):
        rnd = random.Random(2501 + 7 * ch)
        n = N(L2)
        hum = S.mains_hum(n, 50.0, ((2, 1.0), (1, 0.3), (3, 0.25), (4, 0.5), (6, 0.35), (8, 0.15), (12, 0.08)))
        hum = S.mul(S.circ(hum, lambda s: S.lp(s, 1500)), S.slow_mod(n, rnd, L2, (1, 2), 0.1))
        ras = S.mul(S.white(n, rnd), [abs(math.sin(math.pi * 100 * i / SR)) ** 14 for i in range(n)])
        ras = S.circ(ras, lambda s: S.bp(s, 2000, 0.8))
        fan = bed(f[ch], L2, 0.6, offsets=((0.0, 1.1), (0.4, 1.7))[ch])
        hdd = bed(e, L2, 0.3, offsets=((0.0, 0.7), (0.9, 0.2))[ch])
        ev = S.zeros(N(L2 + 0.6))
        for t in ((3.1, 8.4), (5.7, 9.6))[ch]:
            S.add_at(ev, sp, t, rnd.uniform(0.5, 1.0))
        ev = fold(S.reverb(ev, "small_room", wet=0.3), L2)
        chans.append((unit(hum), unit(ras), unit(fan), unit(hdd), unit(ev)))
    st = lambda i: [chans[0][i], chans[1][i]]
    y = _mix_st((st(0), 0.55), (st(1), 0.06), (st(2), 0.35), (st(3), 0.08), (st(4), 0.08))
    out("ambience_switchgear", y, -21.5, loop=True)

    L3 = 16.0
    begin("ambience_core", "16 s seamless stereo loop: synthesized deep resonant drone (detuned low partials ~36.7/37.1 Hz beating, 51.9 Hz tritone, 55 and 73.5 Hz, all with whole cycles over the loop), slowly sweeping high-Q resonant noise (periodic centre 90-320 Hz), metallic resonances at 233/331 Hz with periodic swells, 'breathing' sub modulation; occasional arcs (BMacZero 'spark.wav' and 'continuousspark.wav', CC0, with synthesized crackle) through the 3.5 s industrial-hall IR, time-wrapped across the loop point")
    sp = unit(S.hp(snap(rec(ELEC, "spark.wav"), -20, 0.0005), 300))
    cs = unit(S.hp(rec(ELEC, "continuousspark.wav"), 400))
    chans = []
    for ch in range(2):
        rnd = random.Random(2601 + 19 * ch)
        n = N(L3)
        parts = [(36.6875, 1.0), (37.125, 0.9), (51.875, 0.35), (55.0, 0.5), (73.5, 0.3), (110.0 + ch * 0.0625, 0.12)]
        dr = S.zeros(n)
        for fq, a in parts:
            t_ = S.tone(n, whole(fq, L3), ((1, 1.0), (2, 0.3)), phase=rnd.uniform(0, S.TAU))
            dr = [v + a * w for v, w in zip(dr, t_)]
        breath = S.slow_mod(n, rnd, L3, (1, 2), 0.3)
        dr = S.mul(S.circ(dr, lambda s: S.lp(s, 400)), breath)
        sw = S.slow_mod(n, rnd, L3, (1, 3), 0.6)
        fc = [90 + 230 * (v - 0.4) / 1.2 for v in sw]
        res = S.circ(S.white(n, rnd), lambda s: S.svf(s, lambda t: max(60.0, fc[int(t * SR) % n]), 12.0, "bp"))
        met = S.zeros(n)
        for fq, cyc in ((233.0, (1, 2)), (331.0, (2, 3))):
            r = S.circ(S.white(n, rnd), lambda s, fq=fq: S.bp(s, whole(fq, L3), 60.0))
            met = [v + w * max(0.0, m - 1.0) ** 2 for v, w, m in zip(met, r, S.slow_mod(n, rnd, L3, cyc, 0.8))]
        ev = S.zeros(N(L3 + 3.5))
        for t in ((2.7, 9.4, 13.8), (5.2, 11.6))[ch]:
            arc = S.mix((sp, 0.8, 0), (cs, 0.6, 0.05), (S.crackle(0.4, rnd, 1500, 100, band=(1200, 11000)), 0.5, 0))
            S.add_at(ev, arc, t, rnd.uniform(0.5, 1.0))
        ev = fold(S.reverb(ev, "industrial_hall", wet=1.0, dry=0.3), L3)
        chans.append((unit(dr), unit(res), unit(met), unit(ev)))
    st = lambda i: [chans[0][i], chans[1][i]]
    y = _mix_st((st(0), 0.6), (st(1), 0.3), (st(2), 0.2), (st(3), 0.22))
    out("ambience_core", y, -19.0, loop=True)


GROUPS = [build_alarm, build_machinery, build_power, build_crawl, build_ambience]


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
            body += ["- source: (not built by this script)", ""]
            continue
        if p["sources"]:
            n_rec += 1
            for s, rel in p["sources"]:
                m = B._src_meta(s)
                inner = "/".join(rel.split("/")[2:]) if rel.startswith("x/") else rel
                body.append("- source: \"%s\" by %s, file `%s` - %s (download %s) - licence CC0" % (m["title"], B._author(m), inner, m["page"], B._file_url(m, rel)))
            if p["synth"]:
                body.append("- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)")
            else:
                n_pure += 1
        else:
            n_syn += 1
            body.append("- source: synthesized (tools/m2/synth_audio_v2.py and tools/m2/audio_m4.py)")
        body.append("- processing: %s" % p["proc"])
        body.append("")
    head = ["# BREACH audio M4 (staging/audio_m4) - sources and processing", "",
            "Rebuild: `python -I tools/m2/audio_fetch.py oga_chain_winch_bart` (the only new download; all other sources were already in staging/audio/raw/), then `python -I tools/m2/audio_m4.py`.",
            "All recordings are CC0 1.0 (licence verified on each asset's OpenGameArt page, stored in raw/<id>/SOURCE.json). Everything else is synthesized, first-party work of this project.",
            "",
            "Format: 16-bit PCM WAV, 48 kHz; mono for all positional sounds, stereo only for ambience_* loops (alarm_loop and lift_motor_loop are mono, positional).",
            "Summary: %d outputs use CC0 recordings (%d edited recordings only, %d layered with synthesis); %d are fully synthesized." % (n_rec, n_pure, n_rec - n_pure, n_syn),
            "",
            "Loudness (max 100 ms RMS, same hierarchy as M2/M3): core_overload -9 (finale, loudest set piece, still under the player's rifle peak), capacitor_destroyed -12, "
            "breaker_close -14, blast_door_open -15, lift_arrive -16, alarm_loop -17, capacitor_hit -17, robot_wake -18, breaker_hum_rise -20, relay_voice_beep -22, "
            "arc_crackle -22, lift_call / lift_motor_loop -24, crawl_step -25; ambience loops about -31 dBFS mean like the M2/M3 beds. Loops are steady-state "
            "(circular reverb/filters, whole-cycle tones, crossfaded beds, time-wrapped events) and checked for a seamless end-to-start join.",
            "",
            "## Source assets", "", "| id (raw/ dir) | asset | author | licence | page |", "|---|---|---|---|---|"]
    for s in used:
        m = B._src_meta(s)
        lic = "CC0" if m["licenses"] == ["CC0"] else "CC0 (dual-licensed: %s; used under CC0)" % " / ".join(m["licenses"])
        head.append("| %s | %s | %s | %s | %s |" % (s, m["title"], B._author(m), lic, m["page"]))
    head += ["", "## Output files", ""]
    with open(os.path.join(M4, "SOURCES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(head + body) + "\n")
    print("SOURCES.md: %d with recordings (%d pure), %d fully synthesized" % (n_rec, n_pure, n_syn))


def main(argv):
    if "--validate" in argv:
        B.validate()
        return
    sel = [a for a in argv if not a.startswith("-")]
    os.makedirs(M4, exist_ok=True)
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
