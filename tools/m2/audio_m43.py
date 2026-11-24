# M4.3 weapon audio for BREACH: new close-perspective shot layers (open rifle,
# suppressed rifle, pistol), action-cycling layers, stereo room responses and
# single wall-slap layers.
#
#   python -I tools/m2/audio_m43.py            # build everything + SOURCES.md + previews
#   python -I tools/m2/audio_m43.py --check    # re-measure the written files only
#
# Self-contained (numpy + ffmpeg for decoding).  Reads CC0 recordings from
# staging/audio/raw/<id>/ (see SOURCE.json there), writes staging/audio_m43/.
# Deterministic: every random stream is a seeded numpy Generator.
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "staging", "audio", "raw")
OUT = os.path.join(ROOT, "staging", "audio_m43")
PREV = os.path.join(OUT, "preview")
SR = 48000
C_SOUND = 343.0

FFSL = "oga_free_firearm_sound_library"
FF = "x/Prepared_SFX_Library/Prepared SFX Library/"
HG = ("oga_handgun_reload_zer0sol", "reload.wav")
SGC = ("oga_shotgun_reload_zer0sol", "x/shotgunsounds/ShotgunSounds/Shell in Chamber.mp3")
KLATCH = ("oga_kenney_rpg", "x/RPGsounds_Kenney/OGG/metalLatch.ogg")
KCLICK = ("oga_kenney_rpg", "x/RPGsounds_Kenney/OGG/metalClick.ogg")
SPRING = ("oga_100_metal_wood_rubberduck", "x/100-CC0-wood-metal-SFX/metal_spring_01.ogg")
CLINK = ("oga_metal_impact_bmaczero", "clink2.wav")


def N(sec):
    return int(round(sec * SR))


def db(v):
    return 10.0 ** (v / 20.0)


def todb(v):
    return 20.0 * math.log10(max(float(v), 1e-12))


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------
PROV = {}      # output name -> {"sources": [(src, rel)], "proc": str}
_CUR = [None]


def begin(name, proc):
    _CUR[0] = name
    PROV[name] = {"sources": [], "proc": proc}


def inherit(name, *others):
    for o in others:
        for s in PROV[o]["sources"]:
            if s not in PROV[name]["sources"]:
                PROV[name]["sources"].append(s)


_DEC = {}


def load(src, rel, t0=0.0, dur=None, speed=1.0, chan=None):
    """Decode (part of) a raw recording to 48 kHz mono float64.  speed != 1
    is a true varispeed (pitch + time) done by ffmpeg's resampler.  chan=0
    takes the left microphone only (avoids comb filtering of spaced pairs)."""
    path = os.path.join(RAW, src, *rel.split("/"))
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if _CUR[0] and (src, rel) not in PROV[_CUR[0]]["sources"]:
        PROV[_CUR[0]]["sources"].append((src, rel))
    key = (path, t0, dur, speed, chan)
    if key not in _DEC:
        cmd = ["ffmpeg", "-v", "error"]
        if t0:
            cmd += ["-ss", "%.4f" % t0]
        if dur:
            cmd += ["-t", "%.4f" % dur]
        cmd += ["-i", path]
        if chan is not None:
            cmd += ["-af", "pan=mono|c0=c%d" % chan]
        cmd += ["-ac", "1", "-ar", str(int(round(SR / speed))), "-f", "f32le", "pipe:1"]
        r = subprocess.run(cmd, capture_output=True, check=True)
        _DEC[key] = np.frombuffer(r.stdout[: len(r.stdout) // 4 * 4], dtype=np.float32).astype(np.float64)
    return _DEC[key].copy()


# --------------------------------------------------------------------------
# DSP helpers (causal RBJ biquads evaluated in the frequency domain)
# --------------------------------------------------------------------------
def _H(kind, f, q, g, w):
    f = min(max(f, 5.0), SR * 0.49)
    w0 = 2.0 * math.pi * f / SR
    cs, sn = math.cos(w0), math.sin(w0)
    al = sn / (2.0 * q)
    A = 10.0 ** (g / 40.0)
    if kind == "lp":
        b = ((1 - cs) / 2, 1 - cs, (1 - cs) / 2); a = (1 + al, -2 * cs, 1 - al)
    elif kind == "hp":
        b = ((1 + cs) / 2, -(1 + cs), (1 + cs) / 2); a = (1 + al, -2 * cs, 1 - al)
    elif kind == "bp":
        b = (al, 0.0, -al); a = (1 + al, -2 * cs, 1 - al)
    elif kind == "pk":
        b = (1 + al * A, -2 * cs, 1 - al * A); a = (1 + al / A, -2 * cs, 1 - al / A)
    elif kind == "ls":
        s2 = 2 * math.sqrt(A) * al
        b = (A * ((A + 1) - (A - 1) * cs + s2), 2 * A * ((A - 1) - (A + 1) * cs), A * ((A + 1) - (A - 1) * cs - s2))
        a = ((A + 1) + (A - 1) * cs + s2, -2 * ((A - 1) + (A + 1) * cs), (A + 1) + (A - 1) * cs - s2)
    elif kind == "hs":
        s2 = 2 * math.sqrt(A) * al
        b = (A * ((A + 1) + (A - 1) * cs + s2), -2 * A * ((A - 1) + (A + 1) * cs), A * ((A + 1) + (A - 1) * cs - s2))
        a = ((A + 1) - (A - 1) * cs + s2, 2 * ((A - 1) - (A + 1) * cs), (A + 1) - (A - 1) * cs - s2)
    else:
        raise ValueError(kind)
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def filt(x, *specs):
    """Apply biquads [(kind, f, q, gain_db)] to x; same length out."""
    n = len(x)
    nfft = 1 << int(math.ceil(math.log2(n + N(0.35))))
    X = np.fft.rfft(x, nfft)
    w = 2.0 * math.pi * np.arange(len(X)) / nfft
    for s in specs:
        kind, f = s[0], s[1]
        q = s[2] if len(s) > 2 else 0.7071
        g = s[3] if len(s) > 3 else 0.0
        X = X * _H(kind, f, q, g, w)
    return np.fft.irfft(X, nfft)[:n]


def hp(x, f, q=0.7071):
    return filt(x, ("hp", f, q))


def lp(x, f, q=0.7071):
    return filt(x, ("lp", f, q))


def hp4(x, f):
    return filt(x, ("hp", f, 0.5412), ("hp", f, 1.3066))


def lp4(x, f):
    return filt(x, ("lp", f, 0.5412), ("lp", f, 1.3066))


def band(x, lo, hi):
    return lp4(hp4(x, lo), hi)


def unit(x):
    return x / max(np.abs(x).max(), 1e-12)


def tt(n):
    return np.arange(n) / SR


def env(n, tau, att=0.0003):
    t = tt(n)
    return (1.0 - np.exp(-t / att)) * np.exp(-t / tau)


def sweep(n, f0, f1, tauf, phase=0.0):
    t = tt(n)
    f = f1 + (f0 - f1) * np.exp(-t / tauf)
    return np.sin(phase + 2.0 * math.pi * np.cumsum(f) / SR)


def fade(x, fin=0.0, fout=0.0):
    y = np.array(x, dtype=np.float64, copy=True)
    a, b = min(N(fin), y.shape[-1]), min(N(fout), y.shape[-1])
    if a > 0:
        y[..., :a] *= np.linspace(0.0, 1.0, a, endpoint=False)
    if b > 0:
        y[..., -b:] *= 0.5 * (1.0 + np.cos(np.linspace(0.0, math.pi, b)))
    return y


def onset(x, rel_db=-20.0):
    th = np.abs(x).max() * db(rel_db)
    return int(np.argmax(np.abs(x) > th))


def snap(x, rel_db=-20.0, pre=0.0004, dur=None):
    i = max(0, onset(x, rel_db) - N(pre))
    y = x[i:]
    if dur:
        y = y[: N(dur)]
    return y


def mix(n, *layers):
    """layers: (signal, gain, t_offset_sec)."""
    y = np.zeros(n)
    for sig, g, t0 in layers:
        i = N(t0)
        m = min(len(sig), n - i)
        if m > 0:
            y[i:i + m] += g * sig[:m]
    return y


def limit(x, reduce_db, over_db=3.0, lag=0.00035, release_db_s=260.0):
    """Peak limiter by gain riding (no waveshaping): threshold reduce_db under
    the peak, linear-in-dB release (exact, via running maxima).  The gain
    reacts 'lag' seconds late on purpose, so the first fraction of a
    millisecond of the shot - the crack - passes at full level and stays the
    loudest thing in the file; the blast/body behind it is what gets levelled.
    A second, instant limiter over_db higher bounds that crack overshoot."""
    y = unit(x)
    need = np.maximum(0.0, 20.0 * np.log10(np.maximum(np.abs(y), 1e-9)) + reduce_db)
    i = np.arange(len(y), dtype=np.float64)
    sr_ = release_db_s / SR
    g = np.maximum.accumulate(need + i * sr_) - i * sr_
    k = N(lag)
    g = np.concatenate([np.zeros(k), g[:-k]])
    r = np.minimum(1.0, np.arange(len(g)) / max(1.0, k * 0.5))        # no gain step: reduction ramps in over lag/2
    g = np.concatenate([g[:k], g[k:] * r[: len(g) - k]])
    need2 = np.maximum(0.0, need - over_db)
    g = np.maximum(g, np.maximum.accumulate(need2 + i * sr_ * 8.0) - i * sr_ * 8.0)
    return y * 10.0 ** (-g / 20.0)


def sat(x, drive_db):
    """Density stage: 80 % of the drive as limiting (clean gain riding), the
    rest as peak-referenced tanh saturation."""
    y = unit(limit(x, 0.8 * drive_db)) * db(0.2 * drive_db)
    return np.tanh(y)


def fftconv(a, b):
    n = len(a) + len(b) - 1
    nfft = 1 << int(math.ceil(math.log2(n)))
    return np.fft.irfft(np.fft.rfft(a, nfft) * np.fft.rfft(b, nfft), nfft)[:n]


# --------------------------------------------------------------------------
# measurement (same definitions as the in-engine baseline: band energies of the
# first 250 ms relative to 400-2000 Hz; crest = peak - RMS over 400 ms)
# --------------------------------------------------------------------------
BANDS = (("sub", 40, 100), ("body", 100, 400), ("mid", 400, 2000), ("pres", 2000, 6000), ("air", 6000, 16000))


def measure(x):
    x = np.asarray(x, dtype=np.float64)
    pk_all = float(np.abs(x).max())
    if x.ndim == 2:
        x = x.mean(axis=0)
    seg = x[: N(0.25)]
    X = np.abs(np.fft.rfft(seg, 1 << 15)) ** 2
    f = np.fft.rfftfreq(1 << 15, 1.0 / SR)
    e = {nm: 10.0 * math.log10(X[(f >= lo) & (f < hi)].sum() + 1e-30) for nm, lo, hi in BANDS}
    m = {nm: e[nm] - e["mid"] for nm in e}
    s4 = x[: N(0.4)]
    pk = todb(pk_all)
    m["peak"] = pk
    m["rms400"] = todb(math.sqrt(float((s4 ** 2).sum()) / N(0.4)))
    m["rms250"] = todb(math.sqrt(float((seg ** 2).sum()) / N(0.25)))
    m["crest"] = pk - m["rms400"]
    m["crest250"] = pk - m["rms250"]
    m["len"] = len(x) / SR
    return m


def shape(x, target, crest, name="", iters=40, fixed_drive=None):
    """Tonal + density mastering towards measured targets: four broad EQ
    bands (sub 63 Hz, body 200 Hz, presence 3.5 kHz, air shelf 8 kHz) and a
    tanh drive are iterated until the *measured* band levels (rel. 400-2000 Hz,
    first 250 ms) and the crest factor of the result match the targets."""
    g = {"sub": 0.0, "body": 0.0, "pres": 0.0, "air": 0.0}
    drive = 6.0 if fixed_drive is None else fixed_drive
    y = x
    for _ in range(iters):
        y = filt(x, ("pk", 63, 0.9, g["sub"]), ("pk", 200, 0.75, g["body"]), ("pk", 3500, 0.7, g["pres"]), ("hs", 8000, 0.7071, g["air"]))
        y = sat(y, drive)
        y = unit(filt(y, ("hp", 28, 0.7071)))
        m = measure(y)
        for b in g:
            g[b] = min(18.0, max(-18.0, g[b] + 0.6 * (target[b] - m[b])))
        if fixed_drive is None:
            drive = min(24.0, max(0.0, drive + 0.7 * (m["crest"] - crest)))
    m = measure(y)
    print("   shape %-18s eq sub %+5.1f body %+5.1f pres %+5.1f air %+5.1f drive %4.1f dB -> crest %.1f" % (name, g["sub"], g["body"], g["pres"], g["air"], drive, m["crest"]))
    return y, drive


def shape_family(raws, target, crest, names):
    """Master a family of variants: the density drive of each variant is the
    one that hits the crest target, but kept within +-3.5 dB of the family
    median so no variant gets a visibly different envelope treatment; the EQ
    is matched per variant."""
    each = [shape(r, target, crest, n, iters=30)[1] for r, n in zip(raws, names)]
    srt = sorted(each)
    d = 0.5 * (srt[len(srt) // 2 - 1] + srt[len(srt) // 2])
    print("   -> family drive %.1f dB (per variant within +-3.5 dB)" % d)
    return [shape(r, target, crest, n, fixed_drive=min(d + 3.5, max(d - 3.5, e)))[0] for r, n, e in zip(raws, names, each)]


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------
WRITTEN = []


def write(name, sig, folder=None):
    x = np.atleast_2d(np.asarray(sig, dtype=np.float64))
    q = np.clip(np.round(x * 32767.0), -32767, 32767).astype("<i2")
    path = os.path.join(folder or OUT, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(q.shape[0])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(q.T.tobytes())
    if folder is None:
        WRITTEN.append(name)
    return path


def read(name, folder=None):
    with wave.open(os.path.join(folder or OUT, name + ".wav"), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32767.0
    return a.reshape(-1, ch).T, sr, sw * 8


def finish(x, peak_db=None, gain=None, fin=0.00012, fout=0.04):
    """Clean start/end, DC-free, level."""
    y = np.atleast_2d(np.array(x, dtype=np.float64))
    y = fade(y, fin, fout)
    y[..., -2:] = 0.0
    if peak_db is not None:
        y = y / np.abs(y).max() * db(peak_db)
    if gain is not None:
        y = y * gain
    return y if y.shape[0] > 1 else y[0]


# ==========================================================================
# 1-3) close shot layers
# ==========================================================================
def real_shot(rel, t_on, speed, length=0.30):
    """Direct sound of a Free Firearm Sound Library near-distance shot (left
    microphone), onset-aligned, varispeed, faded before the outdoor echo."""
    x = load(FFSL, FF + rel, max(0.0, t_on - 0.05), 0.6, speed=speed, chan=0)
    d = snap(x, -18, 0.0003, length)
    return unit(fade(hp(d, 35), 0.0001, length * 0.5))


def friedlander(n, T):
    t = tt(n)
    return np.where(t < 6 * T, (1.0 - t / T) * np.exp(-1.6 * t / T), 0.0)


def fnoise(rng, n, freqs, q):
    w = rng.standard_normal(n)
    y = np.zeros(n)
    for f, g in freqs:
        y += g * filt(w, ("bp", f, q))
    return y


RIFLE_TGT = {"sub": -5.5, "body": 1.5, "pres": -3.5, "air": -10.5}
SUPP_TGT = {"sub": -7.0, "body": 2.8, "pres": -6.8, "air": -18.0}
PISTOL_TGT = {"sub": -8.0, "body": 0.0, "pres": -2.5, "air": -9.5}
RIFLE_CREST, SUPP_CREST, PISTOL_CREST = 15.0, 15.7, 17.0

# (primary recording, onset s), optional second recording blended under it, pitch factor
RIFLE_VAR = [
    (("AR-15/D_32P.wav", 0.704), None, 1.000),
    (("AR-15/D_32P.wav", 5.647), None, 0.975),
    (("AR-15/D_32P.wav", 0.704), ("SKS/U_14P.wav", 6.755), 1.028),
    (("AR-15/D_32P.wav", 5.647), ("SKS/U_14P.wav", 10.211), 1.012),
]
PISTOL_VAR = [
    (("Walther PPQ/X_39P.wav", 1.407), None, 1.000),
    (("Walther PPQ/X_39P.wav", 6.444), None, 0.972),
    (("Walther PPQ/X_39P.wav", 10.660), None, 1.026),
    (("Walther PPQ/X_39P.wav", 6.444), ("Carl Gustav M45/G_31P.wav", 3.501), 1.014),
]


def jit(rng, amt_db=1.5):
    return db(rng.uniform(-amt_db, amt_db))


def rifle_raw(k):
    (rel, t_on), second, p = RIFLE_VAR[k]
    rng = np.random.default_rng(4300 + k)
    n = N(0.56)
    real = real_shot(rel, t_on, p)
    lay = [(real, 0.7, 0.0)]
    if second:
        lay.append((real_shot(second[0], second[1], p * 1.03), 0.4, 0.0))
    crack = unit(hp4(rng.standard_normal(n), 2200) * env(n, 0.0008 * jit(rng, 2), 0.00005))
    blast = unit(lp(friedlander(n, 0.0021 / p), 1800))
    body = sweep(n, 250 * p * rng.uniform(0.96, 1.04), 112 * p * rng.uniform(0.96, 1.04), 0.022, rng.uniform(0, 3.1)) * env(n, 0.050 * jit(rng, 1), 0.0006)
    bodyn = unit(band(rng.standard_normal(n), 110, 430) * env(n, 0.062, 0.0015))
    bark = unit(fnoise(rng, n, [(640 * p, 1.0), (1080 * p, 0.8), (1720 * p, 0.55)], 2.6) * env(n, 0.046 * jit(rng, 1), 0.0008))
    sub = sweep(n, 88 * p, 47 * p, 0.03) * env(n, 0.06, 0.002)
    gas = unit(hp4(rng.standard_normal(n), 2500) * env(n, 0.024 * jit(rng, 2), 0.0005))
    tail = unit(band(rng.standard_normal(n), 140, 2800) * env(n, 0.105, 0.012))
    lay += [(crack, 0.35 * jit(rng), 0.0), (blast, 0.45, 0.0), (body, 0.45 * jit(rng, 1), 0.0003), (bodyn, 0.45 * jit(rng), 0.0005),
            (bark, 0.65 * jit(rng), 0.0006 + rng.uniform(0, 0.0006)), (sub, 0.2, 0.0005), (gas, 0.3 * jit(rng), 0.0004), (tail, 0.14 * jit(rng, 1), 0.004)]
    return mix(n, *lay)


def supp_raw(k):
    (rel, t_on), second, p = RIFLE_VAR[k]
    rng = np.random.default_rng(4320 + k)
    n = N(0.48)
    real = real_shot(rel, t_on, p)
    if second:
        real = unit(real + 0.5 * real_shot(second[0], second[1], p * 1.03))
    # bullet's supersonic crack: the recording's own first milliseconds, high-passed
    snapx = hp4(real, 2400) * env(n=len(real), tau=0.0022, att=0.00005)
    crack = unit(hp4(rng.standard_normal(n), 3200) * env(n, 0.0006 * jit(rng, 1), 0.00005))
    # real blast texture restricted to the body band, attack softened (gas is trapped, pressure rises slower)
    tex = unit(band(real, 170, 1500) * (1.0 - np.exp(-tt(len(real)) / 0.0012)))
    fj = lambda: rng.uniform(0.95, 1.05)
    pop = sweep(n, 335 * p * fj(), 150 * p * fj(), 0.012 * fj(), rng.uniform(0, 1.0)) * env(n, 0.030 * jit(rng, 1.5), 0.0007)
    can = (np.sin(2 * math.pi * 545 * p * fj() * tt(n) + rng.uniform(0, 6.28)) * env(n, 0.012, 0.0005) + 0.6 * np.sin(2 * math.pi * 905 * p * fj() * tt(n) + rng.uniform(0, 6.28)) * env(n, 0.008, 0.0005))
    low = sweep(n, 178 * p * fj(), 104 * p * fj(), 0.03 * fj(), rng.uniform(0, 1.5)) * env(n, 0.038 * jit(rng, 1), 0.0012)
    chuff = unit(band(rng.standard_normal(n), 340, 1350) * env(n, 0.050 * jit(rng, 1.5), 0.003))
    chuff2 = unit(band(rng.standard_normal(n), 1300, 3300) * env(n, 0.021 * jit(rng, 2), 0.002))
    sub = sweep(n, 82 * p, 50 * p, 0.03) * env(n, 0.045, 0.002)
    tail = unit(band(rng.standard_normal(n), 150, 1200) * env(n, 0.09, 0.012))
    return mix(n, (unit(snapx), 0.6 * jit(rng, 1), 0.0), (crack, 0.5 * jit(rng, 1), 0.0), (tex, 0.6 * jit(rng), 0.0002), (pop, 0.62, 0.0004),
               (can, 0.25 * jit(rng), 0.0005), (low, 0.5 * jit(rng, 1), 0.0006), (chuff, 0.5 * jit(rng), 0.0015 + rng.uniform(0, 0.001)),
               (chuff2, 0.5 * jit(rng), 0.001), (sub, 0.1, 0.0006), (tail, 0.08, 0.004))


def pistol_raw(k):
    (rel, t_on), second, p = PISTOL_VAR[k]
    rng = np.random.default_rng(4340 + k)
    n = N(0.47)
    real = real_shot(rel, t_on, p, 0.26)
    lay = [(real, 0.7, 0.0)]
    if second:
        lay.append((real_shot(second[0], second[1], p * 1.05, 0.26), 0.35, 0.0))
    crack = unit(hp4(rng.standard_normal(n), 2800) * env(n, 0.0007 * jit(rng, 2), 0.00005))
    blast = unit(lp(friedlander(n, 0.0014 / p), 2600))
    body = sweep(n, 330 * p * rng.uniform(0.96, 1.04), 188 * p * rng.uniform(0.96, 1.04), 0.012, rng.uniform(0, 3.1)) * env(n, 0.033 * jit(rng, 1), 0.0005)
    bodyn = unit(band(rng.standard_normal(n), 140, 430) * env(n, 0.042, 0.001))
    bark = unit(fnoise(rng, n, [(940 * p, 1.0), (1520 * p, 0.8), (2380 * p, 0.5)], 2.4) * env(n, 0.036 * jit(rng, 1), 0.0006))
    sub = sweep(n, 112 * p, 62 * p, 0.02) * env(n, 0.048, 0.0015)
    air = unit(hp4(rng.standard_normal(n), 5200) * env(n, 0.017 * jit(rng, 2), 0.0004))
    tail = unit(band(rng.standard_normal(n), 200, 4000) * env(n, 0.08, 0.01))
    lay += [(crack, 0.45 * jit(rng), 0.0), (blast, 0.35, 0.0), (body, 0.3 * jit(rng, 1), 0.0003), (bodyn, 0.2 * jit(rng), 0.0004),
            (bark, 0.5 * jit(rng), 0.0005 + rng.uniform(0, 0.0005)), (sub, 0.08, 0.0004), (air, 0.22 * jit(rng), 0.0003), (tail, 0.12 * jit(rng, 1), 0.003)]
    return mix(n, *lay)


SHOTS = {}     # name -> float signal as written (before 16-bit rounding)


def build_shots():
    for k in range(4):
        name = "rifle_close_%d" % k
        (rel, _), second, p = RIFLE_VAR[k]
        begin(name, "Free Firearm Sound Library AR-15 near-distance shot (left mic, direct sound only, 0.30 s, varispeed x%.3f)%s as the real transient/blast texture; "
              "synthesized layers: supersonic crack (HP 2.2 kHz noise, 0.8 ms), Friedlander muzzle-blast pulse, low-mid body (250->112 Hz swept sine + 110-430 Hz noise, 50-60 ms), "
              "mid bark (formant noise 640/1080/1720 Hz, 46 ms), sub thump (88->47 Hz), gas hiss, short dry 105 ms noise tail; measured-target mastering: 4 broad EQ bands + density stage (look-ahead limiter + tanh) "
              "iterated until band levels and crest factor match the targets; HP 28 Hz; peak -1 dBFS" % (p, (" with the SKS near shot (%s) blended under it at -5 dB" % second[0].split("/")[1]) if second else ""))
        SHOTS[name] = None
    ys = shape_family([rifle_raw(k) for k in range(4)], RIFLE_TGT, RIFLE_CREST, ["rifle_close_%d" % k for k in range(4)])
    for k in range(4):
        name = "rifle_close_%d" % k
        SHOTS[name] = finish(ys[k], peak_db=-1.0, fout=0.07)
        write(name, SHOTS[name])
    ref = float(np.mean([measure(SHOTS["rifle_close_%d" % k])["rms400"] for k in range(4)]))
    for k in range(4):
        name = "rifle_supp_close_%d" % k
        p = RIFLE_VAR[k][2]
        begin(name, "NOT a filtered copy of the open shot - its own layer stack: reduced bullet crack (first 2 ms of the Free Firearm Sound Library AR-15 shot high-passed at 2.4 kHz + 0.6 ms synthesized snap), "
              "suppressor thud/pop (335->150 Hz swept sine, 30 ms; can resonances 545/905 Hz), low body (178->104 Hz, 38 ms), the recording's 170-1500 Hz blast texture with a softened 1.2 ms attack, "
              "gas chuff (340-1350 Hz noise 50 ms + 1.3-3.3 kHz noise 21 ms, 2-3 ms attack), small sub; varispeed/pitch x%.3f; measured-target mastering (EQ + limiter/tanh density stage); "
              "level set so RMS(400 ms) is 8.1 dB under the mean of rifle_close_*" % p)
        SHOTS[name] = None
    ys = shape_family([supp_raw(k) for k in range(4)], SUPP_TGT, SUPP_CREST, ["rifle_supp_close_%d" % k for k in range(4)])
    for k in range(4):
        name = "rifle_supp_close_%d" % k
        SHOTS[name] = finish(ys[k], gain=db((ref - 8.1) - measure(ys[k])["rms400"]), fout=0.07)
        write(name, SHOTS[name])
    for k in range(4):
        name = "pistol_close_%d" % k
        (rel, _), second, p = PISTOL_VAR[k]
        begin(name, "Free Firearm Sound Library Walther PPQ 9 mm near-distance shot (left mic, direct sound, varispeed x%.3f)%s; synthesized layers: crack with air (HP 2.8 kHz, 0.7 ms + HP 5.2 kHz hiss 17 ms), "
              "short Friedlander blast pulse, body (330->188 Hz swept sine 33 ms + 140-430 Hz noise), higher bark (formants 940/1520/2380 Hz, 30 ms), small sub (112->62 Hz); "
              "measured-target mastering (EQ + limiter/tanh density stage); peak -1 dBFS" % (p, " with a Carl Gustav M45 9 mm near shot blended under it at -6 dB" if second else ""))
        SHOTS[name] = None
    ys = shape_family([pistol_raw(k) for k in range(4)], PISTOL_TGT, PISTOL_CREST, ["pistol_close_%d" % k for k in range(4)])
    for k in range(4):
        name = "pistol_close_%d" % k
        SHOTS[name] = finish(ys[k], peak_db=-1.0, fout=0.07)
        write(name, SHOTS[name])


# ==========================================================================
# 4-5) action cycling
# ==========================================================================
def brass(rng, n, p):
    t = tt(n)
    y = np.zeros(n)
    for f, tau, g in ((4350, 0.014, 1.0), (5620, 0.011, 0.7), (7150, 0.008, 0.5), (9300, 0.005, 0.3)):
        y += g * np.sin(2 * math.pi * f * p * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    return y * (1.0 - np.exp(-t / 0.0002))


def clack(rng, n, p):
    """Short receiver/carrier 'clack' body under a metal impact."""
    t = tt(n)
    y = np.zeros(n)
    for f, tau, g in ((430, 0.006, 0.8), (770, 0.007, 1.0), (1160, 0.006, 0.8), (1900, 0.005, 0.6)):
        y += g * np.sin(2 * math.pi * f * p * rng.uniform(0.97, 1.03) * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    return unit(y * (1.0 - np.exp(-t / 0.0003)) + 0.3 * lp(rng.standard_normal(n), 2500) * np.exp(-t / 0.004))


def twang(rng, n, p):
    """Buffer-spring 'sproing': chirping inharmonic partials with a fast beat."""
    t = tt(n)
    y = np.zeros(n)
    for f, tau, g in ((790, 0.040, 1.0), (1470, 0.032, 0.8), (2360, 0.024, 0.6), (3550, 0.016, 0.4)):
        fi = f * p * (1.0 + 0.07 * np.exp(-t / 0.025))
        y += g * np.sin(2 * math.pi * np.cumsum(fi) / SR + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    return y * (1.0 - np.exp(-t / 0.002)) * (1.0 + 0.5 * np.sin(2 * math.pi * 58 * p * t))


def build_mech():
    for k in range(3):
        name = "rifle_mech_%d" % k
        p = (1.0, 0.965, 1.03)[k]
        dt = (0.050, 0.054, 0.047)[k]      # carrier back -> in battery
        tc = (0.108, 0.121, 0.099)[k]      # case clink
        begin(name, "bolt-carrier cycle: zer0sol 'Shotgun Reload' action impact (CC0, 1.11 s event, x%.2f) as the carrier hitting the buffer at t=0; rubberduck 'metal_spring_01' (CC0, real spring) + synthesized chirped buffer-spring twang; "
              "zer0sol 'Handgun Reload' slide slam (CC0, x%.2f) as the carrier going into battery at %d ms with Kenney 'metalLatch' (CC0) as the bolt lock; faint case-ejection clink at %d ms (BMacZero 'clink2' x2.3 + synthesized brass modes 4.3-9.3 kHz); "
              "synthesized receiver 'clack' body (modes 430-1900 Hz, 5-7 ms) under both impacts; HP 170 Hz, +1 dB 3.5 kHz, -3 dB shelf above 7 kHz (energy stays centred at 2-8 kHz, where the suppressed shot is weakest); no reverb; peak -6 dBFS" % (0.95 * p, 0.86 * p, round(dt * 1000), round(tc * 1000)))
        rng = np.random.default_rng(4360 + k)
        n = N(0.25)
        back = unit(hp(fade(snap(load(SGC[0], SGC[1], 1.10, 0.06, speed=0.95 * p), -12, 0.0003, 0.05), 0.0001, 0.025), 200))
        home = unit(hp(fade(snap(load(HG[0], HG[1], 1.16, 0.3, speed=0.86 * p), -16, 0.0003, 0.19), 0.0001, 0.08), 180))
        latch = unit(hp(fade(snap(load(KLATCH[0], KLATCH[1], speed=1.1 * p), -18, 0.0003, 0.05), 0.0001, 0.03), 900))
        spr = unit(hp4(fade(snap(load(SPRING[0], SPRING[1], speed=0.92 * p), -18, 0.0003, 0.12), 0.002, 0.06), 600))
        clk = unit(hp4(fade(snap(load(CLINK[0], CLINK[1], speed=2.3 * p), -18, 0.0003, 0.05), 0.0001, 0.03), 2500))
        y = mix(n, (back, 0.85, 0.0), (clack(rng, N(0.06), 0.92 * p), 0.3, 0.0), (clack(rng, N(0.06), p), 0.33, dt), (spr, 0.30 * jit(rng), 0.006), (unit(twang(rng, N(0.14), p)), 0.16 * jit(rng), 0.008),
                (home, 1.0, dt), (latch, 0.45 * jit(rng), dt + 0.0025), (clk, 0.13 * jit(rng), tc), (unit(brass(rng, N(0.06), p)), 0.07 * jit(rng), tc + 0.0005))
        y = filt(y, ("hp", 170, 0.7071), ("pk", 3500, 0.8, 1.0), ("hs", 7000, 0.7071, -3.0))
        y = np.tanh(unit(y) * 1.5)
        write(name, finish(y, peak_db=-6.0, fout=0.07))
    for k in range(3):
        name = "pistol_mech_%d" % k
        p = (1.0, 1.04, 0.97)[k]
        dt = (0.040, 0.037, 0.043)[k]
        tc = (0.082, 0.076, 0.090)[k]
        begin(name, "slide cycle: zer0sol 'Handgun Reload' (CC0) slide rear-stop impact (1.11 s, x%.2f) as the slide hitting its rear stop at t=0 and the slide-release slam (1.18 s, x%.2f) as the slide returning to battery at %d ms; "
              "Kenney 'metalClick' (CC0) tick; faint case clink at %d ms (BMacZero 'clink2' x2.6 + synthesized brass modes); synthesized slide 'clack' body (modes 540-2500 Hz) under both impacts; HP 220 Hz, -3 dB shelf above 7 kHz; no reverb; peak -6 dBFS" % (1.08 * p, 1.06 * p, round(dt * 1000), round(tc * 1000)))
        rng = np.random.default_rng(4380 + k)
        n = N(0.17)
        back = unit(hp(fade(snap(load(HG[0], HG[1], 1.095, 0.06, speed=1.08 * p), -8, 0.0003, 0.04), 0.0001, 0.025), 300))
        home = unit(hp(fade(snap(load(HG[0], HG[1], 1.16, 0.3, speed=1.06 * p), -16, 0.0003, 0.125), 0.0001, 0.07), 250))
        tick = unit(hp(fade(snap(load(KCLICK[0], KCLICK[1], speed=1.2 * p), -18, 0.0003, 0.03), 0.0001, 0.02), 1200))
        clk = unit(hp4(fade(snap(load(CLINK[0], CLINK[1], speed=2.6 * p), -18, 0.0003, 0.04), 0.0001, 0.025), 3000))
        y = mix(n, (back, 0.7, 0.0), (clack(rng, N(0.05), 1.25 * p), 0.25, 0.0), (clack(rng, N(0.05), 1.35 * p), 0.3, dt), (tick, 0.3 * jit(rng), 0.001), (home, 1.0, dt), (clk, 0.12 * jit(rng), tc), (unit(brass(rng, N(0.05), 1.12 * p)), 0.06 * jit(rng), tc + 0.0005))
        y = filt(y, ("hp", 220, 0.7071), ("hs", 7000, 0.7071, -3.0))
        y = np.tanh(unit(y) * 1.5)
        write(name, finish(y, peak_db=-6.0, fout=0.05))


# ==========================================================================
# 6) room responses (stereo, wet only)
# ==========================================================================
def image_er(L, src, rcv, beta, tmax, skip_floor_first=False, shelf_per_order=-1.3):
    """Image-source early reflections of a shoebox room for two ears.
    L=(Lx,Ly,Lz), beta=(x0,x1,y0,y1,z0,z1) pressure reflection factors.
    Time zero = arrival of the direct sound (which is NOT included).
    Returns stereo array and the sorted first-order delays (ms)."""
    L = np.asarray(L, float); src = np.asarray(src, float); rcv = np.asarray(rcv, float)
    d0 = float(np.linalg.norm(src - rcv))
    R = tmax * C_SOUND + d0
    rng_n = [np.arange(-int(R / (2 * L[i])) - 1, int(R / (2 * L[i])) + 2) for i in range(3)]
    nx, ny, nz = np.meshgrid(*rng_n, indexing="ij")
    n = int(tmax * SR) + 8
    nb = 7
    buck = np.zeros((2, nb, n))
    first = []
    ear_axis = np.array([1.0, 0.0, 0.0])
    ears = (rcv - 0.09 * ear_axis, rcv + 0.09 * ear_axis)
    for px in (0, 1):
        for py in (0, 1):
            for pz in (0, 1):
                ix = (1 - 2 * px) * src[0] + 2 * nx * L[0]
                iy = (1 - 2 * py) * src[1] + 2 * ny * L[1]
                iz = (1 - 2 * pz) * src[2] + 2 * nz * L[2]
                cx0, cx1 = np.abs(nx - px), np.abs(nx)
                cy0, cy1 = np.abs(ny - py), np.abs(ny)
                cz0, cz1 = np.abs(nz - pz), np.abs(nz)
                order = cx0 + cx1 + cy0 + cy1 + cz0 + cz1
                amp = (beta[0] ** cx0) * (beta[1] ** cx1) * (beta[2] ** cy0) * (beta[3] ** cy1) * (beta[4] ** cz0) * (beta[5] ** cz1)
                ok = order > 0
                if skip_floor_first:
                    ok &= ~((order == 1) & (cz0 == 1))
                for e in (0, 1):
                    dx, dy, dz = ix - ears[e][0], iy - ears[e][1], iz - ears[e][2]
                    d = np.sqrt(dx * dx + dy * dy + dz * dz)
                    m = ok & (d < R - 0.01)
                    dd = d[m]
                    side = dx[m] / dd * (1.0 if e == 1 else -1.0)
                    a = amp[m] / np.maximum(dd, 0.5) * (1.0 + 0.35 * side)
                    o = np.minimum(order[m], nb) - 1
                    pos = (dd - d0) / C_SOUND * SR
                    i0 = np.floor(pos).astype(int)
                    fr = pos - i0
                    v = (i0 >= 0) & (i0 < n - 1)
                    np.add.at(buck[e], (o[v], i0[v]), a[v] * (1 - fr[v]))
                    np.add.at(buck[e], (o[v], i0[v] + 1), a[v] * fr[v])
                    if e == 0:
                        first += list(((dd[order[m] == 1] - d0) / C_SOUND * 1000.0))
    out = np.zeros((2, n))
    for e in (0, 1):
        for o in range(nb):
            if np.any(buck[e, o]):
                out[e] += filt(buck[e, o], ("hs", 3500, 0.7071, shelf_per_order * (o + 1)))
    return out, sorted(first)


OCT = (63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)


def diffuse_tail(rng, length, rt_mid, rt_fac, t0, t_build, tilt_db_oct=-1.0):
    """Decorrelated stereo diffuse tail: independent Gaussian noise per ear,
    split into octave bands, each with its own exponential decay."""
    n = N(length)
    nfft = 1 << int(math.ceil(math.log2(n)))
    f = np.fft.rfftfreq(nfft, 1.0 / SR)
    lf = np.log2(np.maximum(f, 1.0))
    lc = np.log2(np.array(OCT, float))
    t = tt(n)
    build = np.where(t < t0, 0.0, 1.0 - np.exp(-np.maximum(t - t0, 0.0) / t_build))
    tilt = db(tilt_db_oct * np.maximum(lf - math.log2(1000.0), -3.0))
    tilt = tilt * np.where(f < 45, (f / 45.0) ** 2, 1.0)
    out = np.zeros((2, n))
    for e in (0, 1):
        X = np.fft.rfft(rng.standard_normal(n), nfft) * tilt
        for b, fc in enumerate(OCT):
            w = np.clip(1.0 - np.abs(lf - lc[b]), 0.0, 1.0)
            if b == 0:
                w = np.where(lf < lc[0], 1.0, w)
            if b == len(OCT) - 1:
                w = np.where(lf > lc[-1], 1.0, w)
            yb = np.fft.irfft(X * w, nfft)[:n]
            out[e] += yb * np.exp(-6.9078 * np.maximum(t - t0, 0.0) / (rt_mid * rt_fac[b]))
        out[e] *= build
    return out


def duct_modes(rng, n):
    """Sheet-metal panel ringing: inharmonic modes, short decays."""
    t = tt(n)
    out = np.zeros((2, n))
    f = 210.0
    while f < 5200:
        tau = rng.uniform(0.025, 0.07) * (1.0 if f > 600 else 0.7)
        g = rng.uniform(0.4, 1.0) / (1.0 + f / 2500.0)
        ph = rng.uniform(0, 6.28, 2)
        pan = rng.uniform(-0.6, 0.6)
        for e in (0, 1):
            out[e] += g * (1.0 + (pan if e else -pan)) * np.sin(2 * math.pi * f * t + ph[e]) * np.exp(-t / tau)
        f *= rng.uniform(1.09, 1.21)
    return out * (1.0 - np.exp(-t / 0.0015))


CONC = (1.22, 1.16, 1.08, 1.0, 0.96, 0.84, 0.62, 0.40, 0.26)      # RT60 factors per octave (painted concrete + air absorption)
ROOMS = {
    # dims, shooter ear positions for variants 0/1, wall betas, ER window, tail RT60(mid), tail build, tail/ER energy dB
    "small": dict(L=(3.3, 4.3, 2.6), pos=((1.35, 1.8, 1.62), (1.9, 2.5, 1.58)), beta=(0.86, 0.86, 0.84, 0.84, 0.72, 0.80), t_er=0.060, rt=0.46, fac=CONC,
                  build=0.012, ratio=0.0, skip_floor=False, tilt=-1.2, length=0.75),
    "medium": dict(L=(4.8, 15.0, 3.8), pos=((2.1, 6.0, 1.65), (2.9, 8.2, 1.6)), beta=(0.92, 0.92, 0.72, 0.72, 0.74, 0.86), t_er=0.110, rt=0.92, fac=CONC,
                   build=0.03, ratio=1.5, skip_floor=False, tilt=-1.1, length=1.35),
    "large": dict(L=(20.0, 30.0, 9.6), pos=((8.6, 11.2, 1.65), (11.0, 13.6, 1.65)), beta=(0.90, 0.90, 0.88, 0.88, 0.70, 0.90), t_er=0.26, rt=2.05, fac=CONC,
                  build=0.09, ratio=3.0, skip_floor=True, tilt=-1.3, length=2.7),
    "huge": dict(L=(26.0, 28.0, 13.7), pos=((12.2, 12.9, 1.65), (13.6, 15.0, 1.65)), beta=(0.92, 0.92, 0.91, 0.91, 0.72, 0.92), t_er=0.34, rt=2.8, fac=CONC,
                 build=0.13, ratio=3.5, skip_floor=True, tilt=-1.4, length=3.5),
    "duct": dict(L=(0.75, 7.0, 0.6), pos=((0.36, 2.6, 0.27), (0.4, 3.6, 0.3)), beta=(0.95, 0.95, 0.35, 0.35, 0.95, 0.95), t_er=0.10, rt=0.36,
                 fac=(0.5, 0.6, 0.8, 1.0, 1.05, 1.0, 0.85, 0.6, 0.4), build=0.006, ratio=-3.0, skip_floor=False, tilt=-0.3, length=0.6),
}
ROOM_INFO = {}


def rt60(ir):
    """Schroeder T20 (x3) of the 400-2000 Hz band, both ears."""
    e = np.zeros(ir.shape[1])
    for c in ir:
        nfft = 1 << int(math.ceil(math.log2(len(c))))
        X = np.fft.rfft(c, nfft)
        f = np.fft.rfftfreq(nfft, 1.0 / SR)
        X[(f < 400) | (f > 2000)] = 0
        e += np.fft.irfft(X, nfft)[: len(c)] ** 2
    s = np.cumsum(e[::-1])[::-1]
    s = 10 * np.log10(s / s[0] + 1e-20)
    i5, i25 = int(np.argmax(s < -5)), int(np.argmax(s < -25))
    return 3.0 * (i25 - i5) / SR


def make_ir(room, v):
    r = ROOMS[room]
    rng = np.random.default_rng(4400 + 10 * list(ROOMS).index(room) + v)
    ear = np.array(r["pos"][v])
    # muzzle ~0.55 m in front of and slightly below the ears (firing along +y)
    src = ear + np.array([0.06, 0.55, -0.12 if room != "duct" else -0.03])
    er, first = image_er(r["L"], src, ear, r["beta"], r["t_er"], r["skip_floor"])
    n = N(r["length"])
    ne = er.shape[1]
    win = np.ones(ne)
    a = int(ne * 0.55)
    win[a:] = 0.5 * (1 + np.cos(np.linspace(0, math.pi, ne - a)))
    ir = np.zeros((2, n))
    ir[:, :ne] = er * win
    t0 = first[0] / 1000.0
    tail = diffuse_tail(rng, r["length"], r["rt"], r["fac"], t0, r["build"], r["tilt"])
    if room == "duct":
        md = duct_modes(rng, n)
        ir += md * math.sqrt((ir ** 2).sum() / (md ** 2).sum()) * db(-1.0)
    tail *= math.sqrt((ir ** 2).sum() / (tail ** 2).sum()) * db(r["ratio"])
    ir += tail
    ROOM_INFO["%s_%d" % (room, v)] = {"first_ms": [round(float(x), 1) for x in first[:5]], "rt60_ir": round(rt60(ir), 2)}
    return ir


def build_rooms():
    for room in ROOMS:
        for v in (0, 1):
            ir = make_ir(room, v)
            info = ROOM_INFO["%s_%d" % (room, v)]
            r = ROOMS[room]
            desc = ("synthesized stereo impulse response of a %.1fx%.1fx%.1f m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption%s; "
                    "first-order reflections at %s ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 %.2f s; measured T20x3 of the IR %.2f s)%s"
                    % (r["L"][0], r["L"][1], r["L"][2], ", first-order floor bounce omitted (it merges with the dry shot)" if r["skip_floor"] else "",
                       "/".join("%.0f" % x for x in info["first_ms"]), r["rt"], info["rt60_ir"], ", plus inharmonic sheet-metal panel modes (210 Hz-5 kHz, 25-70 ms)" if room == "duct" else ""))
            gains = {}
            for kind, shot in (("", "rifle_close_%d" % v), ("_supp", "rifle_supp_close_%d" % v)):
                name = "shot_room%s_%s_%d" % (kind, room, v)
                begin(name, "wet-only room response (no direct sound): %s convolved with a %s; HP 70 Hz%s; %s" % (
                    shot, desc, "" if not kind else ", LP 6.5 kHz",
                    "peak -8 dBFS" if not kind else "level = the open-shot version's gain structure with RMS set 10 dB below shot_room_%s_%d" % (room, v)))
                inherit(name, shot)
                y = np.stack([fftconv(SHOTS[shot], ir[c])[: ir.shape[1]] for c in (0, 1)])
                y = np.stack([filt(c, ("hp", 70, 0.7071)) if not kind else filt(c, ("hp", 70, 0.7071), ("lp", 6500, 0.7071)) for c in y])
                y = fade(y, 0.0, r["length"] * 0.3)
                if not kind:
                    y = finish(y, peak_db=-8.0, fin=0.0, fout=0.02)
                    gains[room] = math.sqrt(float((y ** 2).mean()))
                else:
                    y = finish(y, gain=gains[room] * db(-10.0) / math.sqrt(float((y ** 2).mean())), fin=0.0, fout=0.02)
                write(name, y)


# ==========================================================================
# 7) single wall slaps
# ==========================================================================
def build_slaps():
    for kind, lo, hi in (("", 250, 5000), ("_supp", 250, 3600)):
        for k in range(3):
            name = "shot_slap%s_%d" % (kind, k)
            shot = ("rifle_close_%d" if not kind else "rifle_supp_close_%d") % (k + 1)
            begin(name, "one early wall reflection: %s band-limited %d-%d Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, "
                  "envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; %s" % (shot, lo, hi, "peak -6 dBFS" if not kind else "RMS 9 dB below the matching open slap (peak about -14 dBFS)"))
            inherit(name, shot)
            rng = np.random.default_rng(4500 + k + (10 if kind else 0))
            ker = np.zeros(N(0.0027))
            ker[0] = 1.0
            for _ in range(6):
                ker[rng.integers(8, len(ker))] += rng.uniform(0.25, 0.6) * rng.choice((-1.0, 1.0))
            y = fftconv(band(SHOTS[shot], lo, hi), ker)[: N(0.2)]
            y = filt(y, ("hs", 3000, 0.7071, -1.5), ("hp", 250, 0.7071))
            y = y * np.exp(-tt(len(y)) / 0.055)
            if not kind:
                y = finish(y, peak_db=-6.0, fin=0.0003, fout=0.06)
                build_slaps.ref = getattr(build_slaps, "ref", {})
                build_slaps.ref[k] = math.sqrt(float((y ** 2).mean()))
            else:
                y = finish(y, fin=0.0003, fout=0.06)
                y = y * build_slaps.ref[k] * db(-9.0) / math.sqrt(float((y ** 2).mean()))
            write(name, y)


# ==========================================================================
# validation, metrics, previews, docs
# ==========================================================================
def expected():
    names = ["%s_%d" % (f, k) for f in ("rifle_close", "rifle_supp_close", "pistol_close") for k in range(4)]
    names += ["%s_%d" % (f, k) for f in ("rifle_mech", "pistol_mech") for k in range(3)]
    names += ["shot_room%s_%s_%d" % (s, r, v) for s in ("", "_supp") for r in ROOMS for v in (0, 1)]
    names += ["shot_slap%s_%d" % (s, k) for s in ("", "_supp") for k in range(3)]
    return names


def tail_rt(x):
    """Decay time of a room layer itself (T20x3, 400-2000 Hz), informative."""
    return rt60(np.atleast_2d(x))


def check():
    rows = {}
    bad = []
    for name in expected():
        x, sr, bits = read(name)
        m = measure(x)
        st = name.startswith("shot_room")
        m.update(sr=sr, bits=bits, ch=x.shape[0], dc=float(np.abs(x.mean(axis=1)).max()), first=float(np.abs(x[:, 0]).max()), last=float(np.abs(x[:, -1]).max()),
                 clip=int((np.abs(x) >= 0.9999).sum()))
        if st:
            m["lr_corr"] = float(np.corrcoef(x[0], x[1])[0, 1])
            m["decay_rt"] = tail_rt(x)
            mono = np.abs(x).max(axis=0)
            m["onset_ms"] = 1000.0 * int(np.argmax(mono > 0.1 * mono.max())) / SR
        if sr != SR or bits != 16 or x.shape[0] != (2 if st else 1):
            bad.append("%s: format" % name)
        if m["dc"] > 0.002 or m["first"] > 0.02 or m["last"] != 0.0 or m["clip"]:
            bad.append("%s: dc %.4f first %.4f last %.4f clip %d" % (name, m["dc"], m["first"], m["last"], m["clip"]))
        if st and abs(m["lr_corr"]) > 0.6:
            bad.append("%s: L/R correlation %.2f" % (name, m["lr_corr"]))
        rows[name] = m
    ref = float(np.mean([rows["rifle_close_%d" % k]["rms400"] for k in range(4)]))
    print("\n%-22s %5s %6s %6s %6s %6s %6s %7s %6s %6s" % ("file", "len", "peak", "rms400", "crest", "sub", "body", "pres", "air", "note"))
    for name in expected():
        m = rows[name]
        note = ""
        if name.startswith("rifle_supp"):
            note = "rms %.1f dB under open" % (ref - m["rms400"])
        if "lr_corr" in m:
            note = "L/R corr %+.2f, decay T20x3 %.2f s, onset %.1f ms" % (m["lr_corr"], m["decay_rt"], m["onset_ms"])
        print("%-22s %5.2f %6.1f %6.1f %6.1f %+6.1f %+6.1f %+7.1f %+6.1f  %s" % (name, m["len"], m["peak"], m["rms400"], m["crest"], m["sub"], m["body"], m["pres"], m["air"], note))
    print("\nroom IRs:")
    for k, v in ROOM_INFO.items():
        print("  %-9s first-order reflections (ms after direct): %s   IR RT60 (T20x3, 400-2k) %.2f s" % (k, v["first_ms"], v["rt60_ir"]))
    print("\nvalidation: %s" % ("OK (%d files)" % len(rows) if not bad else "PROBLEMS:\n  " + "\n  ".join(bad)))
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump({"files": {k: {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()} for k, v in rows.items()}, "room_ir": ROOM_INFO,
                   "supp_rms400_below_open_db": {("rifle_supp_close_%d" % k): round(ref - rows["rifle_supp_close_%d" % k]["rms400"], 2) for k in range(4)}}, fh, indent=1)
    return rows, bad


def previews():
    """Audition mixes (NOT deliverables): 3 singles + a 760 RPM 8-round burst
    with mech layer and a room layer, simple unity mix, stereo."""
    os.makedirs(PREV, exist_ok=True)
    rng = np.random.default_rng(4600)

    def get(n):
        x = read(n)[0]
        return x if x.shape[0] == 2 else np.vstack([x[0], x[0]])

    def seq(shot_f, nshot, mech_f, room_f, period, slap_f=None):
        times = [0.3, 1.1, 1.9] + [2.9 + i * period for i in range(8)]
        n = N(times[-1] + 3.8)
        y = np.zeros((2, n))
        for i, t in enumerate(times):
            lay = [(get("%s_%d" % (shot_f, rng.integers(nshot))), 1.0, 0.0), (get("%s_%d" % (mech_f, rng.integers(3))), 0.7, 0.004),
                   (get("%s_%d" % (room_f, rng.integers(2))), 0.9, 0.0)]
            if slap_f:
                s = get("%s_%d" % (slap_f, rng.integers(3)))
                lay.append((s * np.array([[1.0], [0.45]]), 0.6, 0.014))
            for sig, g, dt in lay:
                a = N(t + dt)
                m = min(sig.shape[1], n - a)
                y[:, a:a + m] += g * sig[:, :m]
        return np.tanh(y * 0.8) / 0.8 * 0.9
    p760 = 60.0 / 760.0
    for nm, args in (("preview_rifle_open_medium", ("rifle_close", 4, "rifle_mech", "shot_room_medium", p760, "shot_slap")),
                     ("preview_rifle_open_large", ("rifle_close", 4, "rifle_mech", "shot_room_large", p760, None)),
                     ("preview_rifle_supp_medium", ("rifle_supp_close", 4, "rifle_mech", "shot_room_supp_medium", p760, "shot_slap_supp")),
                     ("preview_rifle_supp_large", ("rifle_supp_close", 4, "rifle_mech", "shot_room_supp_large", p760, None)),
                     ("preview_pistol_small", ("pistol_close", 4, "pistol_mech", "shot_room_small", 0.2, None))):
        write(nm, seq(*args), folder=PREV)


def spectro_sheet():
    from PIL import Image, ImageDraw
    names = expected()
    cols, cw, ch, pad, lab = 6, 300, 150, 6, 14
    rows = (len(names) + cols - 1) // cols
    W, Hh = cols * (cw + pad) + pad, rows * (ch + lab + pad) + pad + 18
    img = Image.new("RGB", (W, Hh), (16, 16, 20))
    dr = ImageDraw.Draw(img)
    dr.text((pad, 3), "BREACH M4.3 weapon audio - log-frequency spectrograms 40 Hz-20 kHz (ticks 100 Hz / 1 kHz / 10 kHz), 80 dB range, each cell = full file length", fill=(220, 220, 220))
    anchors = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66], [245, 125, 21], [250, 193, 39], [252, 255, 164]], float)
    fl = np.geomspace(40, 20000, ch)
    nf = 2048
    fb = np.fft.rfftfreq(nf, 1.0 / SR)
    for i, name in enumerate(names):
        x = read(name)[0].mean(axis=0)
        hop = max(16, int(math.ceil(len(x) / cw)))
        xp = np.concatenate([np.zeros(nf // 2), x, np.zeros(nf + hop * cw)])
        win = np.hanning(nf)
        S = np.empty((ch, cw))
        for c in range(cw):
            a = c * hop
            if a > len(x):
                S[:, c] = -200
                continue
            sp = np.abs(np.fft.rfft(xp[a:a + nf] * win)) + 1e-9
            S[:, c] = 20 * np.log10(np.interp(fl, fb, sp))
        S = np.clip((S - S.max() + 80) / 80.0, 0, 1)[::-1]
        idx = S * (len(anchors) - 1)
        i0 = np.minimum(idx.astype(int), len(anchors) - 2)
        fr = (idx - i0)[..., None]
        rgb = (anchors[i0] * (1 - fr) + anchors[i0 + 1] * fr).astype(np.uint8)
        x0 = pad + (i % cols) * (cw + pad)
        y0 = 18 + pad + (i // cols) * (ch + lab + pad)
        img.paste(Image.fromarray(rgb, "RGB"), (x0, y0 + lab))
        for ft in (100, 1000, 10000):
            yy = y0 + lab + ch - 1 - int(np.argmin(np.abs(fl - ft)))
            dr.line((x0, yy, x0 + 4, yy), fill=(255, 255, 255))
        dr.text((x0, y0 + 1), "%s  %.2fs" % (name, len(x) / SR), fill=(230, 230, 230))
    img.save(os.path.join(OUT, "preview_spectrograms.png"))


def _meta(src):
    with open(os.path.join(RAW, src, "SOURCE.json"), encoding="utf-8") as fh:
        return json.load(fh)


def write_sources(rows):
    used = sorted({s for n in expected() for s, _ in PROV[n]["sources"]})
    ref = float(np.mean([rows["rifle_close_%d" % k]["rms400"] for k in range(4)]))
    L = ["# BREACH audio M4.3 (staging/audio_m43) - weapon shot layers: sources and processing", "",
         "Rebuild: `python -I tools/m2/audio_m43.py` (no new downloads; all recordings were already in staging/audio/raw/).",
         "All recordings are CC0 1.0 (licence recorded in staging/audio/raw/<id>/SOURCE.json, verified on the asset page when fetched). Everything else is synthesized by tools/m2/audio_m43.py (first-party).",
         "Format: 16-bit PCM WAV, 48 kHz; mono except shot_room_* (stereo, decorrelated L/R). No dither (tails end in digital silence).",
         "`preview/` holds audition mixes only (not game assets). `metrics.json` holds the measurements below for every file.", "",
         "## Source assets", "", "| id (raw/ dir) | asset | author | licence | page |", "|---|---|---|---|---|"]
    for s in used:
        m = _meta(s)
        L.append("| %s | %s | %s | CC0 | %s |" % (s, m["title"], str(m["author"]).strip(), m["page"]))
    L += ["", "## Measured (first 250 ms band energies relative to 400-2000 Hz; crest = peak - RMS over 400 ms)", "",
          "| file | len s | peak dBFS | RMS400 | crest | sub | body | presence | air | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n in expected():
        m = rows[n]
        note = ""
        if n.startswith("rifle_supp"):
            note = "%.1f dB under open rifle RMS" % (ref - m["rms400"])
        if "lr_corr" in m:
            note = "L/R corr %+.2f; decay T20x3 %.2f s" % (m["lr_corr"], m["decay_rt"])
        L.append("| %s | %.2f | %.1f | %.1f | %.1f | %+.1f | %+.1f | %+.1f | %+.1f | %s |" % (n, m["len"], m["peak"], m["rms400"], m["crest"], m["sub"], m["body"], m["pres"], m["air"], note))
    L += ["", "## Room impulse responses as built", "", "| room | first-order reflections, ms after the direct sound | IR RT60 (T20x3, 400-2000 Hz) |", "|---|---|---|"]
    for k, v in ROOM_INFO.items():
        L.append("| %s | %s | %.2f s |" % (k, ", ".join("%.1f" % x for x in v["first_ms"]), v["rt60_ir"]))
    L += ["", "## Output files", ""]
    for n in expected():
        p = PROV[n]
        L.append("### %s.wav" % n)
        for s, rel in p["sources"]:
            m = _meta(s)
            inner = "/".join(rel.split("/")[2:]) if rel.startswith("x/") else rel
            L.append("- source: \"%s\" by %s, file `%s` - %s - CC0" % (m["title"], str(m["author"]).strip(), inner, m["page"]))
        if not p["sources"]:
            L.append("- source: synthesized")
        L.append("- processing: %s" % p["proc"])
        L.append("")
    with open(os.path.join(OUT, "SOURCES.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    if "--check" in argv:
        check()
        return
    build_shots()
    build_mech()
    build_rooms()
    build_slaps()
    rows, bad = check()
    write_sources(rows)
    if "--fast" not in argv:
        previews()
        spectro_sheet()
    print("wrote %d files to %s" % (len(WRITTEN), OUT))
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
