# Procedural sound design for BREACH, version 2.  Pure Python stdlib plus the
# ffmpeg binary (used only for fast FFT convolution with synthesized impulse
# responses).  Everything here is deterministic: every random source is a
# seeded random.Random instance.  All output is original first-party work.
#
# Compared with tools/synth_audio.py this version uses:
#   * RBJ biquads and a TPT state-variable filter with time-varying cutoff,
#   * modal synthesis (banks of two-pole resonators excited by short noise
#     bursts) for clicks, latches, brass casings, armour plates and clanks,
#   * layered transients (crack + body + sub thump) with separate envelopes,
#   * Poisson-cluster crackle and mains-synchronous arc buzz for electricity,
#   * convolution reverb with synthesized impulse responses (sparse early
#     reflections + exponentially decaying noise with frequency-dependent
#     decay), convolved through ffmpeg's afir filter,
#   * seamless loops: periodic parts are generated with whole cycles over the
#     loop length, aperiodic parts are equal-power crossfaded tail-into-head.
#
# Standalone use (writes the fully synthesized set):
#   python -I tools/m2/synth_audio_v2.py staging/audio
import array
import math
import os
import random
import subprocess
import sys
import wave

SR = 48000
TAU = 2.0 * math.pi
_HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(_HERE, "..", "..", "staging", "audio", "_work")


def N(sec):
    return max(0, int(round(sec * SR)))


# --------------------------------------------------------------------------
# generators
# --------------------------------------------------------------------------
def zeros(n):
    return [0.0] * n


def white(n, rnd):
    r = rnd.random
    return [2.0 * r() - 1.0 for _ in range(n)]


def pink(n, rnd):
    # Paul Kellet's refined pink filter.
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    out = [0.0] * n
    r = rnd.random
    for i in range(n):
        w = 2.0 * r() - 1.0
        b0 = 0.99886 * b0 + w * 0.0555179
        b1 = 0.99332 * b1 + w * 0.0750759
        b2 = 0.96900 * b2 + w * 0.1538520
        b3 = 0.86650 * b3 + w * 0.3104856
        b4 = 0.55000 * b4 + w * 0.5329522
        b5 = -0.7616 * b5 - w * 0.0168980
        out[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11
        b6 = w * 0.115926
    return out


def brown(n, rnd, leak=0.995):
    out = [0.0] * n
    s = 0.0
    r = rnd.random
    for i in range(n):
        s = s * leak + (2.0 * r() - 1.0) * 0.1
        out[i] = s
    return out


def sweep_tone(n, f_of_t, harmonics=((1, 1.0),), phase=0.0):
    """Additive oscillator; f_of_t(t) gives the fundamental in Hz."""
    out = [0.0] * n
    ph = phase
    nyq = SR * 0.45
    for i in range(n):
        f = f_of_t(i / SR)
        ph += TAU * f / SR
        s = 0.0
        for h, a in harmonics:
            if f * h < nyq:
                s += a * math.sin(ph * h)
        out[i] = s
    return out


def tone(n, f, harmonics=((1, 1.0),), phase=0.0):
    return sweep_tone(n, lambda t: f, harmonics, phase)


def saw_harm(k=12, tilt=1.0):
    return tuple((h, ((-1) ** (h + 1)) / h ** tilt) for h in range(1, k + 1))


def square_harm(k=12):
    return tuple((h, 1.0 / h) for h in range(1, 2 * k, 2))


# --------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------
def _coeffs(kind, f, q, g):
    f = min(max(f, 5.0), SR * 0.49)
    w = TAU * f / SR
    cw, sw = math.cos(w), math.sin(w)
    al = sw / (2.0 * q)
    A = 10.0 ** (g / 40.0)
    if kind == "lp":
        b0, b1, b2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2
        a0, a1, a2 = 1 + al, -2 * cw, 1 - al
    elif kind == "hp":
        b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
        a0, a1, a2 = 1 + al, -2 * cw, 1 - al
    elif kind == "bp":
        b0, b1, b2 = al, 0.0, -al
        a0, a1, a2 = 1 + al, -2 * cw, 1 - al
    elif kind == "peak":
        b0, b1, b2 = 1 + al * A, -2 * cw, 1 - al * A
        a0, a1, a2 = 1 + al / A, -2 * cw, 1 - al / A
    elif kind == "ls":
        sa = 2 * math.sqrt(A) * al
        b0 = A * ((A + 1) - (A - 1) * cw + sa)
        b1 = 2 * A * ((A - 1) - (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - sa)
        a0 = (A + 1) + (A - 1) * cw + sa
        a1 = -2 * ((A - 1) + (A + 1) * cw)
        a2 = (A + 1) + (A - 1) * cw - sa
    elif kind == "hs":
        sa = 2 * math.sqrt(A) * al
        b0 = A * ((A + 1) + (A - 1) * cw + sa)
        b1 = -2 * A * ((A - 1) + (A + 1) * cw)
        b2 = A * ((A + 1) + (A - 1) * cw - sa)
        a0 = (A + 1) - (A - 1) * cw + sa
        a1 = 2 * ((A - 1) - (A + 1) * cw)
        a2 = (A + 1) - (A - 1) * cw - sa
    else:
        raise ValueError(kind)
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def biquad(x, kind, f, q=0.7071, g=0.0):
    b0, b1, b2, a1, a2 = _coeffs(kind, f, q, g)
    y = [0.0] * len(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o
        y[i] = o
    return y


def lp(x, f, q=0.7071):
    return biquad(x, "lp", f, q)


def hp(x, f, q=0.7071):
    return biquad(x, "hp", f, q)


def bp(x, f, q=1.0):
    return biquad(x, "bp", f, q)


def peq(x, f, q, g):
    return biquad(x, "peak", f, q, g)


def lshelf(x, f, g):
    return biquad(x, "ls", f, 0.7071, g)


def hshelf(x, f, g):
    return biquad(x, "hs", f, 0.7071, g)


def lp4(x, f):
    return lp(lp(x, f, 0.541), f, 1.307)


def hp4(x, f):
    return hp(hp(x, f, 0.541), f, 1.307)


def svf(x, f_of_t, q=0.7071, mode="lp", block=16):
    """TPT state-variable filter with a time-varying cutoff."""
    k = 1.0 / q
    ic1 = ic2 = 0.0
    y = [0.0] * len(x)
    a1 = a2 = a3 = 0.0
    for i, v0 in enumerate(x):
        if i % block == 0:
            f = min(max(f_of_t(i / SR), 10.0), SR * 0.45)
            g = math.tan(math.pi * f / SR)
            a1 = 1.0 / (1.0 + g * (g + k))
            a2 = g * a1
            a3 = g * a2
        v3 = v0 - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        if mode == "lp":
            y[i] = v2
        elif mode == "bp":
            y[i] = v1 * k
        else:
            y[i] = v0 - k * v1 - v2
    return y


def onepole_lp(x, f):
    a = math.exp(-TAU * f / SR)
    s = 0.0
    y = [0.0] * len(x)
    for i, v in enumerate(x):
        s = (1 - a) * v + a * s
        y[i] = s
    return y


def env_follow(x, f=30.0):
    return onepole_lp([abs(v) for v in x], f)


# --------------------------------------------------------------------------
# envelopes and utilities
# --------------------------------------------------------------------------
def env_exp(n, attack, decay, hold=0.0):
    out = [0.0] * n
    ia = attack * SR
    ih = hold * SR
    k = 1.0 / (decay * SR)
    for i in range(n):
        if i < ia:
            a = math.sin(0.5 * math.pi * i / ia) ** 2
        elif i < ia + ih:
            a = 1.0
        else:
            a = math.exp(-(i - ia - ih) * k)
        out[i] = a
    return out


def env_pts(n, pts):
    """Piecewise-linear envelope; pts = [(t_sec, value), ...]."""
    out = [0.0] * n
    j = 0
    for i in range(n):
        t = i / SR
        while j < len(pts) - 2 and t > pts[j + 1][0]:
            j += 1
        t0, v0 = pts[j]
        t1, v1 = pts[min(j + 1, len(pts) - 1)]
        if t <= t0:
            out[i] = v0
        elif t >= t1:
            out[i] = v1
        else:
            out[i] = v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return out


def mul(a, b):
    return [x * y for x, y in zip(a, b)]


def gain(x, g):
    return [v * g for v in x]


def db(v):
    return 10 ** (v / 20.0)


def add_at(dst, src, t, g=1.0):
    o = int(round(t * SR))
    need = o + len(src)
    if need > len(dst):
        dst.extend([0.0] * (need - len(dst)))
    for i, v in enumerate(src):
        if o + i >= 0:
            dst[o + i] += v * g
    return dst


def mix(*layers, length=None):
    """layers: (signal, gain, offset_sec)."""
    out = [0.0] * (length or 0)
    for sig, g, off in layers:
        add_at(out, sig, off, g)
    if length:
        del out[length:]
    return out


def pad(x, sec):
    return x + [0.0] * N(sec)


def peak(x):
    return max((abs(v) for v in x), default=0.0)


def rms(x):
    return math.sqrt(sum(v * v for v in x) / max(1, len(x)))


def normalize(x, peak_db=-1.0):
    m = peak(x)
    if m <= 1e-12:
        return list(x)
    g = db(peak_db) / m
    return [v * g for v in x]


def softclip(x, drive=1.5):
    t = math.tanh(drive)
    return [math.tanh(v * drive) / t for v in x]


def fade(x, fin=0.0, fout=0.01):
    x = list(x)
    n = len(x)
    a = min(n, N(fin))
    for i in range(a):
        x[i] *= math.sin(0.5 * math.pi * i / a) ** 2
    b = min(n, N(fout))
    for i in range(b):
        x[n - 1 - i] *= math.sin(0.5 * math.pi * i / b) ** 2
    return x


def trim_tail(x, thresh_db=-60.0, keep=0.02):
    th = peak(x) * db(thresh_db)
    end = len(x)
    while end > 1 and abs(x[end - 1]) < th:
        end -= 1
    return x[: min(len(x), end + N(keep))]


def dc_block(x):
    return hp(x, 20.0, 0.7071)


def resample(x, ratio):
    """Change speed by 'ratio' (>1 = higher pitch, shorter). Cubic interp."""
    n = int(len(x) / ratio)
    out = [0.0] * n
    L = len(x)
    for i in range(n):
        p = i * ratio
        k = int(p)
        f = p - k
        xm1 = x[k - 1] if k >= 1 else 0.0
        x0 = x[k] if k < L else 0.0
        x1 = x[k + 1] if k + 1 < L else 0.0
        x2 = x[k + 2] if k + 2 < L else 0.0
        a = (-xm1 + 3 * x0 - 3 * x1 + x2) * 0.5
        b = xm1 - 2.5 * x0 + 2 * x1 - 0.5 * x2
        c = (x1 - xm1) * 0.5
        out[i] = ((a * f + b) * f + c) * f + x0
    return out


def compress(x, thresh_db=-18.0, ratio=4.0, attack=0.002, release=0.08, makeup_db=0.0, knee_db=6.0):
    th = thresh_db
    ga = math.exp(-1.0 / (attack * SR))
    gr = math.exp(-1.0 / (release * SR))
    env = 0.0
    mk = db(makeup_db)
    out = [0.0] * len(x)
    for i, v in enumerate(x):
        a = abs(v)
        env = ga * env + (1 - ga) * a if a > env else gr * env + (1 - gr) * a
        lv = 20 * math.log10(env + 1e-9)
        over = lv - th
        if over <= -knee_db / 2:
            red = 0.0
        elif over < knee_db / 2:
            red = (1 / ratio - 1) * (over + knee_db / 2) ** 2 / (2 * knee_db)
        else:
            red = (1 / ratio - 1) * over
        out[i] = v * db(red) * mk
    return out


def circ(x, fn):
    """Apply a (causal, IIR) filter function circularly: filter two copies
    back to back and keep the second, i.e. the steady-state periodic
    response.  A loop processed this way has no warm-up transient at its
    start and joins its end sample-seamlessly."""
    y = fn(list(x) + list(x))
    return y[len(x):]


def limiter(x, ceiling=1.0, look=0.0015, release=0.04):
    """Look-ahead peak limiter: the gain needed to keep |x| <= ceiling is
    taken as a running minimum over the look-ahead window (so the gain is
    already down when the transient arrives) and released exponentially."""
    from collections import deque
    n = len(x)
    L = max(1, N(look))
    req = [min(1.0, ceiling / abs(v)) if v != 0.0 else 1.0 for v in x] + [1.0] * L
    rel = math.exp(-1.0 / (release * SR))
    out = [0.0] * n
    dq = deque()
    g = 1.0
    for j in range(min(L, len(req))):
        while dq and req[dq[-1]] >= req[j]:
            dq.pop()
        dq.append(j)
    for i in range(n):
        j = i + L
        if j < len(req):
            while dq and req[dq[-1]] >= req[j]:
                dq.pop()
            dq.append(j)
        while dq[0] < i:
            dq.popleft()
        target = req[dq[0]]
        g = target if target < g else target + (g - target) * rel
        out[i] = x[i] * g
    return out


def loop_xfade(x, xf_sec, equal_power=True):
    """Return len(x)-xf samples that loop seamlessly: the last xf samples are
    crossfaded into the start."""
    X = N(xf_sec)
    L = len(x) - X
    out = list(x[:L])
    for i in range(X):
        a = i / X
        if equal_power:
            gi, go = math.sin(0.5 * math.pi * a), math.cos(0.5 * math.pi * a)
        else:
            gi, go = a, 1 - a
        out[i] = x[i] * gi + x[L + i] * go
    return out


# --------------------------------------------------------------------------
# modal synthesis / resonant bursts
# --------------------------------------------------------------------------
def resonators(exc, modes, n=None):
    """Bank of two-pole resonators.  modes = [(freq, decay_sec, gain), ...]."""
    n = n or len(exc)
    out = [0.0] * n
    ex = exc + [0.0] * (n - len(exc)) if len(exc) < n else exc[:n]
    for f, dec, g in modes:
        if f >= SR * 0.45:
            continue
        w = TAU * f / SR
        r = math.exp(-1.0 / (dec * SR))
        c1 = 2 * r * math.cos(w)
        c2 = -r * r
        b = g * math.sin(w)
        y1 = y2 = 0.0
        for i in range(n):
            y = b * ex[i] + c1 * y1 + c2 * y2
            y2, y1 = y1, y
            out[i] += y
    return out


def burst(n, rnd, dur=0.0008, color_hp=0.0):
    """Short exponentially decaying noise burst used as an excitation."""
    e = env_exp(n, 0.00005, max(dur, 0.00005))
    x = mul(white(n, rnd), e)
    if color_hp:
        x = hp(x, color_hp)
    return x


def strike(sec, rnd, modes, exc=0.0006, spread=0.0, noise_amt=0.15, noise_dec=0.003, hp_f=0.0):
    """Struck object: noise burst through resonator bank plus a bit of the
    raw contact noise.  'spread' detunes modes randomly (fractional)."""
    n = N(sec)
    m = [(f * (1 + rnd.uniform(-spread, spread)), d, g) for f, d, g in modes]
    e = burst(n, rnd, exc)
    y = resonators(e, m, n)
    contact = mul(white(n, rnd), env_exp(n, 0.00005, noise_dec))
    y = [a + b * noise_amt for a, b in zip(y, contact)]
    if hp_f:
        y = hp(y, hp_f)
    return fade(y, 0, min(0.02, sec * 0.25))


def click(rnd, f=3000.0, body=900.0, dec=0.008, sec=0.06, bright=1.0, q_spread=0.08):
    """Mechanical click: two or three bright metal modes plus a damped body."""
    # Clusters of slightly detuned partials (real parts are not single
    # modes) give a dense, beating, noisy click instead of pure pings.
    modes = []
    for base, d, g in ((f, dec, 1.0), (f * 1.73, dec * 0.6, 0.7), (f * 2.61, dec * 0.4, 0.5), (f * 3.45, dec * 0.3, 0.3)):
        for _ in range(3):
            modes.append((base * (1 + rnd.uniform(-q_spread, q_spread)), d * rnd.uniform(0.45, 1.0), g * bright * rnd.uniform(0.3, 0.7)))
    modes.append((body * (1 + rnd.uniform(-0.05, 0.05)), dec * 0.9, 0.6))
    modes.append((body * 1.62, dec * 0.6, 0.3))
    return strike(sec, rnd, modes, exc=0.0005, spread=0.0, noise_amt=1.0, noise_dec=0.0015, hp_f=150)


def friction(sec, rnd, f=1800.0, q=1.2, grain=180.0, dec=None, att=0.01):
    """Sliding metal/polymer friction: band-passed noise with granular AM."""
    n = N(sec)
    g = onepole_lp([abs(v) for v in white(n, rnd)], grain)
    m = peak(g) or 1.0
    g = [0.25 + 0.75 * (v / m) ** 1.5 for v in g]
    x = mul(bp(white(n, rnd), f, q), g)
    if dec:
        x = mul(x, env_exp(n, att, dec))
    else:
        x = mul(x, env_pts(n, [(0, 0), (att, 1), (sec * 0.7, 0.8), (sec, 0)]))
    return x


def thump(sec, f0, f1, tau_f, decay, attack=0.0008, drive=1.0):
    """Sub/low punch: exponential pitch drop sine with its own envelope."""
    n = N(sec)
    x = sweep_tone(n, lambda t: f1 + (f0 - f1) * math.exp(-t / tau_f), ((1, 1.0), (2, 0.18)))
    x = mul(x, env_exp(n, attack, decay))
    return softclip(x, drive) if drive > 1.0 else x


def noise_hit(sec, rnd, f0, f1, tau, decay, attack=0.0003, q=0.7):
    n = N(sec)
    x = svf(white(n, rnd), lambda t: f1 + (f0 - f1) * math.exp(-t / tau), q, "lp")
    return mul(x, env_exp(n, attack, decay))


# --------------------------------------------------------------------------
# electricity
# --------------------------------------------------------------------------
def crackle(sec, rnd, rate=200.0, rate_end=None, amp_pow=2.5, burst_ms=(0.05, 1.2), band=(1500, 9000), cluster=0.35):
    """Poisson-cluster crackle.  Each event is a tiny noise burst; events can
    spawn a short cluster (like an arc re-striking)."""
    n = N(sec)
    out = [0.0] * n
    t = 0.0
    r = rnd
    while t < sec:
        rt = rate if rate_end is None else rate + (rate_end - rate) * (t / sec)
        t += r.expovariate(max(rt, 1e-3))
        if t >= sec:
            break
        amp = r.random() ** amp_pow
        k = 1 + (int(r.expovariate(1 / 3.0)) if r.random() < cluster else 0)
        tt = t
        for _ in range(k):
            L = r.uniform(*burst_ms) / 1000.0
            i0 = int(tt * SR)
            m = int(L * SR * 5) + 2
            dk = 1.0 / max(1.0, L * SR)
            for j in range(m):
                if i0 + j >= n:
                    break
                out[i0 + j] += amp * (2 * r.random() - 1) * math.exp(-j * dk)
            tt += r.uniform(0.0002, 0.003)
            amp *= r.uniform(0.4, 1.0)
    y = hp(out, band[0], 0.6)
    y = lp(y, band[1], 0.6)
    return y


def arc_buzz(sec, rnd, mains=50.0, sharp=10, f=3200.0, q=0.9, jitter=0.15):
    """High-voltage arc rasp: noise gated by a mains-synchronous pulse."""
    n = N(sec)
    w = white(n, rnd)
    out = [0.0] * n
    ph = 0.0
    jj = 0.0
    for i in range(n):
        if i % 64 == 0:
            jj = 1.0 + jitter * (rnd.random() - 0.5)
        ph += TAU * mains * 2 * jj / SR
        g = abs(math.sin(ph * 0.5)) ** sharp
        out[i] = w[i] * g
    y = bp(out, f, q)
    y2 = bp(out, f * 2.3, q)
    return [a + 0.6 * b for a, b in zip(y, y2)]


def mains_hum(n, f=50.0, harm=((2, 1.0), (4, 0.45), (6, 0.25), (1, 0.2), (3, 0.15), (8, 0.1))):
    return tone(n, f, harm)


# --------------------------------------------------------------------------
# reverb: synthesized impulse responses + ffmpeg FFT convolution
# --------------------------------------------------------------------------
def make_ir(seed, length=1.0, t60=(0.9, 0.75, 0.35), predelay=0.004, early=12, early_span=0.045, early_gain=0.6, fade_in=0.012):
    """Exponentially decaying noise IR with three bands of decay (low <400 Hz,
    mid, high >4 kHz) and a sparse set of early reflections."""
    rnd = random.Random(seed)
    n = N(length)
    w1, w2, w3 = white(n, rnd), white(n, rnd), white(n, rnd)
    lo = lp4(w1, 400)
    hi = hp4(w3, 4000)
    mid = hp(lp(w2, 4000), 400)
    out = [0.0] * n
    pd = N(predelay)
    fi = max(1, N(fade_in))
    k = [6.9078 / (t * SR) for t in t60]
    for i in range(n):
        j = i - pd
        if j < 0:
            continue
        ramp = min(1.0, j / fi) ** 1.5
        out[i] = ramp * (lo[i] * 0.9 * math.exp(-j * k[0]) + mid[i] * math.exp(-j * k[1]) + hi[i] * 0.8 * math.exp(-j * k[2]))
    s = math.sqrt(sum(v * v for v in out)) or 1.0
    out = [v / s for v in out]
    # early reflections (concrete walls/floor): sparse, slightly smeared taps
    er = [0.0] * n
    for e in range(early):
        t = predelay * 0.5 + rnd.uniform(0.002, early_span) * (e + 1) / early
        g = early_gain * (1 - 0.6 * e / early) * (1 if rnd.random() < 0.5 else -1) * rnd.uniform(0.5, 1.0)
        i = N(t)
        for d, h in enumerate((0.35, 1.0, 0.6, 0.25, 0.1)):
            if i + d < n:
                er[i + d] += g * h
    er = lp(er, 7000)
    out = [a + b * 0.08 for a, b in zip(out, er)]
    return fade(out, 0, 0.05)


_IR_CACHE = {}

IR_PRESETS = {
    # name: kwargs for make_ir
    "concrete_room": dict(seed=7001, length=1.1, t60=(0.85, 0.8, 0.35), predelay=0.006, early=14, early_span=0.05),
    "concrete_room_b": dict(seed=7002, length=1.1, t60=(0.8, 0.75, 0.32), predelay=0.008, early=14, early_span=0.06),
    "concrete_room_c": dict(seed=7003, length=1.2, t60=(0.9, 0.85, 0.38), predelay=0.005, early=12, early_span=0.045),
    "corridor": dict(seed=7010, length=0.6, t60=(0.55, 0.45, 0.2), predelay=0.003, early=10, early_span=0.025),
    "small_room": dict(seed=7020, length=0.45, t60=(0.4, 0.3, 0.15), predelay=0.002, early=8, early_span=0.015),
    "industrial_hall": dict(seed=7030, length=3.5, t60=(3.2, 2.4, 0.9), predelay=0.02, early=16, early_span=0.12, fade_in=0.04),
}


def ir(name):
    if name not in _IR_CACHE:
        _IR_CACHE[name] = make_ir(**IR_PRESETS[name])
    return _IR_CACHE[name]


def _ffmpeg():
    return os.environ.get("FFMPEG", "ffmpeg")


def write_f32(path, x, ch=1):
    with wave.open(path, "wb") as w:  # 16-bit is enough for an IR file
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        m = peak(x) or 1.0
        a = array.array("h", (int(max(-1.0, min(1.0, v / m)) * 32767) for v in x))
        w.writeframes(a.tobytes())
    return m


def convolve(x, ir_sig, tag="ir"):
    """FFT convolution through ffmpeg afir.  Returns len(x)+len(ir) samples."""
    os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, "ir_%s_%d.wav" % (tag, len(ir_sig)))
    scale = peak(ir_sig) or 1.0
    if not os.path.exists(p):
        write_f32(p, ir_sig)
    src = array.array("f", x + [0.0] * (len(ir_sig) + 64))
    cmd = [_ffmpeg(), "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0",
           "-i", p, "-filter_complex", "[0:a][1:a]afir=dry=1:wet=1:gtype=none:irnorm=-1:irgain=1:maxir=10[o]",
           "-map", "[o]", "-f", "f32le", "-ar", str(SR), "-ac", "1", "pipe:1"]
    r = subprocess.run(cmd, input=src.tobytes(), capture_output=True, check=True)
    y = array.array("f")
    y.frombytes(r.stdout[: len(r.stdout) // 4 * 4])
    # the IR file was written peak-normalised; restore the original scale
    return [v * scale for v in y][: len(x) + len(ir_sig)]


def reverb(x, name="concrete_room", wet=0.3, dry=1.0, predelay=0.0, wet_hp=120.0):
    """dry*x + wet*(x conv IR).  The wet return is high-passed (wet_hp) so
    low-frequency energy does not smear into a boomy tail."""
    i = ir(name)
    y = convolve(x, i, name)
    if wet_hp:
        y = hp(y, wet_hp)
    out = [0.0] * len(y)
    d = N(predelay)
    for k in range(len(x)):
        out[k] += x[k] * dry
    for k in range(len(y) - d):
        out[k + d] += y[k] * wet
    return out


# --------------------------------------------------------------------------
# WAV output
# --------------------------------------------------------------------------
def write_wav(path, chans, peak_db=None, dither_seed=1):
    """chans: list of channel sample lists (1 = mono, 2 = stereo).  Optional
    peak normalisation (applied jointly to all channels).  TPDF dither."""
    if not isinstance(chans[0], list):
        chans = [chans]
    n = min(len(c) for c in chans)
    if peak_db is not None:
        m = max(peak(c) for c in chans) or 1.0
        g = db(peak_db) / m
        chans = [[v * g for v in c[:n]] for c in chans]
    rnd = random.Random(dither_seed)
    a = array.array("h", bytes(2 * n * len(chans)))
    nc = len(chans)
    for ci, c in enumerate(chans):
        for i in range(n):
            v = c[i] * 32767.0 + (rnd.random() - rnd.random())
            v = 32767 if v > 32767 else (-32768 if v < -32768 else int(round(v)))
            a[i * nc + ci] = v
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(nc)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(a.tobytes())


# ==========================================================================
# sound designs
# ==========================================================================
def gun_mech(seed, kind="rifle"):
    """Action noise of a firing weapon (bolt carrier / slide cycling)."""
    rnd = random.Random(seed)
    if kind == "rifle":
        a = click(rnd, 2600 * rnd.uniform(0.95, 1.05), 700, 0.010, 0.12, 1.0)
        b = click(rnd, 3400 * rnd.uniform(0.95, 1.05), 520, 0.014, 0.14, 0.9)
        sl = friction(0.05, rnd, 2200, 1.5, 400, 0.02)
        spring = resonators(burst(N(0.12), rnd, 0.001), [(1180, 0.018, 0.25), (2950, 0.01, 0.15)])
        return mix((a, 1.0, 0.0), (sl, 0.5, 0.004), (b, 0.9, 0.032), (spring, 0.6, 0.034))
    a = click(rnd, 3100 * rnd.uniform(0.95, 1.05), 820, 0.009, 0.1, 1.0)
    b = click(rnd, 2300 * rnd.uniform(0.95, 1.05), 600, 0.012, 0.12, 1.0)
    return mix((a, 1.0, 0.0), (b, 0.8, 0.022))


def gunshot_synth(seed, kind="rifle", suppressed=False):
    """Fallback fully-synthesized gunshot with an indoor concrete tail."""
    rnd = random.Random(seed)
    sec = 0.4
    n = N(sec)
    rifle = kind == "rifle"
    crack = mul(hp(white(n, rnd), 2500), env_exp(n, 0.00003, 0.0025 if rifle else 0.0018))
    blast = noise_hit(sec, rnd, 9000, 280, 0.012, 0.045 if rifle else 0.035)
    body = noise_hit(sec, rnd, 1800, 120, 0.03, 0.07 if rifle else 0.05)
    sub = thump(sec, 140 if rifle else 180, 48 if rifle else 62, 0.018, 0.09 if rifle else 0.065, drive=1.6)
    mech = gun_mech(seed + 1, kind)
    if suppressed:
        puff = noise_hit(sec, rnd, 2600, 300, 0.01, 0.03)
        dry = mix((crack, 0.05, 0), (puff, 0.8, 0), (lp(body, 900), 0.6, 0), (sub, 0.35, 0), (mech, 1.1, 0.0015))
        dry = softclip(dry, 1.3)
        out = reverb(dry, "concrete_room_b", wet=0.12)
    else:
        dry = mix((crack, 1.3, 0), (blast, 1.0, 0), (body, 0.9, 0), (sub, 1.3, 0), (mech, 0.25, 0.002))
        dry = softclip(compress(dry, -14, 3, 0.0005, 0.05, 4), 1.8)
        out = reverb(dry, "concrete_room", wet=0.55)
    return trim_tail(fade(out, 0, 0.08), -62)


# ---------------------------------------------------------------- weapon foley
def dry_fire(seed=301):
    rnd = random.Random(seed)
    trig = click(rnd, 4200, 1100, 0.004, 0.05, 0.7)
    fall = click(rnd, 2900, 760, 0.010, 0.10, 1.0)
    return mix((trig, 0.55, 0.0), (fall, 1.0, 0.028))


def mag_out(seed=311):
    rnd = random.Random(seed)
    btn = click(rnd, 3600, 900, 0.005, 0.05, 0.8)
    rel = click(rnd, 2100, 480, 0.012, 0.12, 1.0)
    slide = friction(0.16, rnd, 1500, 1.0, 120)
    rattle = mix(*[(click(rnd, rnd.uniform(2500, 5200), 700, 0.004, 0.04, 0.6), rnd.uniform(0.2, 0.5), 0.13 + k * rnd.uniform(0.012, 0.03)) for k in range(3)])
    return mix((btn, 0.6, 0.0), (rel, 1.0, 0.018), (slide, 0.5, 0.025), (rattle, 1.0, 0.0))


def mag_in(seed=321):
    rnd = random.Random(seed)
    slide = friction(0.12, rnd, 1300, 1.0, 150)
    seat = strike(0.18, rnd, [(420, 0.02, 1.0), (1150, 0.012, 0.6), (2800, 0.008, 0.5), (4700, 0.005, 0.3)], exc=0.0005, noise_amt=0.6)
    latch = click(rnd, 3300, 900, 0.007, 0.08, 1.0)
    return mix((slide, 0.45, 0.0), (seat, 1.0, 0.11), (latch, 0.8, 0.118))


def bolt_pull(seed=331):
    rnd = random.Random(seed)
    grab = click(rnd, 2500, 650, 0.006, 0.06, 0.5)
    back = friction(0.11, rnd, 2000, 1.4, 260)
    stop = click(rnd, 2200, 520, 0.014, 0.12, 1.0)
    fwd = friction(0.04, rnd, 2400, 1.4, 400, 0.02)
    slam = strike(0.25, rnd, [(560, 0.03, 1.0), (1650, 0.02, 0.8), (3100, 0.012, 0.7), (5200, 0.006, 0.4)], exc=0.0004, noise_amt=0.6)
    lock = click(rnd, 3800, 1000, 0.006, 0.06, 0.8)
    return mix((grab, 0.5, 0.0), (back, 0.55, 0.01), (stop, 0.9, 0.12), (fwd, 0.5, 0.25), (slam, 1.0, 0.285), (lock, 0.6, 0.297))


def pistol_slide(seed=341):
    rnd = random.Random(seed)
    lever = click(rnd, 3500, 900, 0.005, 0.05, 0.6)
    run = friction(0.03, rnd, 2600, 1.5, 500, 0.015)
    slam = strike(0.3, rnd, [(720, 0.035, 1.0), (1900, 0.025, 0.8), (3600, 0.014, 0.7), (6100, 0.007, 0.4)], exc=0.0003, noise_amt=0.7)
    return mix((lever, 0.6, 0.0), (run, 0.5, 0.012), (slam, 1.0, 0.03))


def cloth(sec, rnd, f=900.0, amt=1.0):
    n = N(sec)
    g = onepole_lp([abs(v) for v in white(n, rnd)], 25)
    m = peak(g) or 1
    g = [(v / m) ** 2 for v in g]
    x = mul(bp(pink(n, rnd), f, 0.5), g)
    x = mul(hp(x, 300), env_pts(n, [(0, 0), (sec * 0.2, 1), (sec * 0.7, 0.7), (sec, 0)]))
    return gain(x, amt)


def weapon_switch(seed=351):
    rnd = random.Random(seed)
    c = cloth(0.32, rnd, 1100)
    rattle = mix(*[(click(rnd, rnd.uniform(1800, 4200), 600, 0.006, 0.05, 0.6), rnd.uniform(0.15, 0.4), 0.03 + rnd.uniform(0, 0.18)) for _ in range(4)])
    grip = strike(0.2, rnd, [(380, 0.02, 1), (1250, 0.012, 0.5), (2900, 0.006, 0.3)], exc=0.0008, noise_amt=0.5)
    return mix((c, 0.7, 0.0), (rattle, 1.0, 0.0), (grip, 0.9, 0.24))


def ads_in(seed=361):
    rnd = random.Random(seed)
    c = cloth(0.2, rnd, 1400)
    t = click(rnd, 2700, 500, 0.004, 0.05, 0.4)
    return mix((c, 1.0, 0.0), (t, 0.35, 0.12))


def shell_tink(seed):
    """Brass casing on concrete: inharmonic tube modes, 2-4 bounces, roll."""
    rnd = random.Random(seed)
    base = rnd.uniform(4300, 5600)
    modes = [(base, 0.06, 1.0), (base * 1.62, 0.04, 0.7), (base * 2.21, 0.03, 0.5), (base * 2.83, 0.02, 0.3), (base * 0.43, 0.02, 0.2)]
    out = zeros(N(0.6))
    t, a = 0.0, 1.0
    for b in range(rnd.randint(3, 5)):
        s = strike(0.25, rnd, modes, exc=0.0002, spread=0.01, noise_amt=0.25, noise_dec=0.0006, hp_f=1500)
        add_at(out, s, t, a)
        t += rnd.uniform(0.05, 0.11) * (0.75 ** b)
        a *= rnd.uniform(0.35, 0.6)
    roll = mul(bp(white(N(0.12), rnd), base * 0.9, 6), env_exp(N(0.12), 0.01, 0.04))
    add_at(out, roll, t, 0.08)
    return trim_tail(reverb(out, "small_room", wet=0.15), -55)


# ---------------------------------------------------------------- impacts
def impact_metal(seed):
    rnd = random.Random(seed)
    crack = mul(hp(white(N(0.02), rnd), 3000), env_exp(N(0.02), 0.00002, 0.0012))
    base = rnd.uniform(900, 1500)
    plate = strike(0.5, rnd, [(base, 0.12, 0.7), (base * 1.47, 0.09, 0.6), (base * 2.09, 0.07, 0.5), (base * 2.98, 0.05, 0.4), (base * 4.1, 0.03, 0.35), (base * 0.52, 0.06, 0.4)], exc=0.0002, spread=0.03, noise_amt=0.4, noise_dec=0.002)
    sp = crackle(0.12, rnd, 300, 40, burst_ms=(0.03, 0.3), band=(3000, 12000))
    return mix((crack, 1.0, 0), (plate, 0.8, 0.0005), (sp, 0.35, 0.002))


def impact_concrete(seed):
    rnd = random.Random(seed)
    crack = mul(hp(white(N(0.02), rnd), 2000), env_exp(N(0.02), 0.00002, 0.0015))
    body = noise_hit(0.15, rnd, 5000, 400, 0.008, 0.02)
    deb = zeros(N(0.4))
    t = 0.01
    for _ in range(rnd.randint(8, 14)):
        g = strike(0.03, rnd, [(rnd.uniform(2500, 7000), 0.004, 1.0), (rnd.uniform(1200, 2500), 0.006, 0.5)], exc=0.0002, noise_amt=0.6)
        add_at(deb, g, t, rnd.uniform(0.05, 0.25) * math.exp(-t / 0.12))
        t += rnd.expovariate(60)
    dust = mul(bp(white(N(0.3), rnd), 3500, 0.8), env_exp(N(0.3), 0.01, 0.08))
    return mix((crack, 0.9, 0), (body, 1.0, 0), (deb, 1.0, 0), (dust, 0.12, 0.01))


def ricochet_whine(seed, sec=0.5):
    rnd = random.Random(seed)
    n = N(sec)
    f0, f1 = rnd.uniform(4200, 5200), rnd.uniform(1300, 1800)
    w = sweep_tone(n, lambda t: f1 + (f0 - f1) * math.exp(-t / 0.18) + 40 * math.sin(TAU * 31 * t), ((1, 1.0), (2, 0.15)))
    nb = svf(white(n, rnd), lambda t: f1 + (f0 - f1) * math.exp(-t / 0.18), 12, "bp")
    e = env_pts(n, [(0, 0), (0.01, 1), (0.08, 0.7), (sec, 0)])
    return mul([a * 0.6 + b * 0.8 for a, b in zip(w, nb)], e)


def ricochet(seed=401):
    return mix((impact_metal(seed), 0.9, 0), (ricochet_whine(seed + 1), 0.55, 0.012))


# ---------------------------------------------------------------- footsteps
def step_concrete_synth(seed):
    rnd = random.Random(seed)
    heel = noise_hit(0.12, rnd, 2500, 200, 0.006, 0.018)
    sole = mul(bp(white(N(0.1), rnd), 2800, 0.9), env_exp(N(0.1), 0.004, 0.015))
    grit = crackle(0.08, rnd, 600, burst_ms=(0.02, 0.2), band=(3000, 10000))
    return mix((heel, 1.0, 0), (sole, 0.5, 0.035), (grit, 0.2, 0.03))


def metal_plate_resp(seed, sec=0.35):
    rnd = random.Random(seed)
    b = rnd.uniform(170, 260)
    return strike(sec, rnd, [(b, 0.09, 1.0), (b * 2.3, 0.07, 0.6), (b * 3.9, 0.05, 0.45), (b * 6.1, 0.035, 0.3), (b * 9.4, 0.02, 0.25), (b * 13.7, 0.012, 0.2)], exc=0.001, spread=0.02, noise_amt=0.2, noise_dec=0.004)


# ---------------------------------------------------------------- robot
def servo(seed, sec=0.45, f_lo=140.0, f_hi=260.0, teeth=13, up=True):
    """Geared DC servo: harmonic motor whine, gear-mesh band, brush noise,
    start/stop transients."""
    rnd = random.Random(seed)
    n = N(sec)
    ra = 0.07
    def f(t):
        if t < ra:
            x = t / ra
            return f_lo * 0.3 + (f_lo - f_lo * 0.3) * x
        x = min(1.0, (t - ra) / max(0.01, sec - ra - 0.06))
        base = f_lo + (f_hi - f_lo) * (math.sin(math.pi * x * 0.5) if up else 1 - math.sin(math.pi * x * 0.5))
        if t > sec - 0.06:
            base *= 1 - 0.6 * (t - (sec - 0.06)) / 0.06
        return base
    motor = sweep_tone(n, f, ((1, 1.0), (2, 0.55), (3, 0.4), (4, 0.18), (5, 0.12), (6, 0.08)))
    mesh = sweep_tone(n, lambda t: f(t) * teeth, ((1, 1.0), (2, 0.3)))
    am = sweep_tone(n, f, ((1, 1.0),))
    mesh = [m * (0.6 + 0.4 * a) for m, a in zip(mesh, am)]
    brush = mul(bp(white(n, rnd), 5200, 0.8), [0.5 + 0.5 * abs(a) for a in am])
    e = env_pts(n, [(0, 0), (0.02, 0.8), (0.07, 1.0), (sec - 0.05, 0.9), (sec, 0)])
    body = mix((motor, 0.55, 0), (mesh, 0.22, 0), (brush, 0.12, 0))
    body = mul(peq(lp(body, 7000), f_hi * 2, 1.5, 4), e)
    start = click(rnd, 2600, 600, 0.006, 0.06, 0.5)
    stop = strike(0.12, rnd, [(500, 0.02, 1.0), (1700, 0.01, 0.5), (3300, 0.006, 0.4)], exc=0.0005, noise_amt=0.5)
    return mix((body, 1.0, 0), (start, 0.25, 0), (stop, 0.45, sec - 0.03))


def hiss(sec, rnd, f=4500.0, q=0.7, att=0.012, dec=0.12, hold=0.0):
    n = N(sec)
    x = bp(white(n, rnd), f, q)
    x = [a + 0.4 * b for a, b in zip(x, hp(white(n, rnd), 7000))]
    flutter = onepole_lp([abs(v) for v in white(n, rnd)], 60)
    m = peak(flutter) or 1
    x = [v * (0.7 + 0.3 * fl / m) for v, fl in zip(x, flutter)]
    return mul(x, env_exp(n, att, dec, hold))


def hydraulic(seed, sec=0.7):
    rnd = random.Random(seed)
    valve = click(rnd, 1900, 420, 0.01, 0.08, 0.8)
    h = hiss(sec, rnd, rnd.uniform(3200, 5200), 0.6, 0.015, 0.16, hold=sec * 0.25)
    n = N(sec)
    groan = sweep_tone(n, lambda t: 70 + 25 * math.exp(-t / 0.2) + 6 * math.sin(TAU * 9 * t), ((1, 1.0), (2, 0.6), (3, 0.4), (5, 0.2)))
    groan = mul(lp(groan, 600), env_pts(n, [(0, 0), (0.05, 1), (sec * 0.7, 0.6), (sec, 0)]))
    fluid = mul(lp(brown(n, rnd, 0.98), 300), env_pts(n, [(0, 0), (0.05, 1), (sec, 0)]))
    clunk = strike(0.25, rnd, [(160, 0.06, 1.0), (430, 0.03, 0.6), (980, 0.02, 0.4), (2100, 0.01, 0.3)], exc=0.001, noise_amt=0.3)
    return mix((valve, 0.5, 0), (h, 0.55, 0.01), (groan, 0.35, 0.02), (fluid, 0.5, 0.02), (clunk, 0.9, sec - 0.12))


def robot_step_synth(seed):
    rnd = random.Random(seed)
    sub = thump(0.5, 110, 34, 0.025, 0.16, drive=1.8)
    impact = noise_hit(0.3, rnd, 1600, 120, 0.01, 0.05)
    b = rnd.uniform(240, 320)
    clank = strike(0.45, rnd, [(b, 0.09, 1.0), (b * 2.71, 0.06, 0.8), (b * 4.4, 0.05, 0.6), (b * 6.9, 0.03, 0.5), (b * 10.3, 0.02, 0.35)], exc=0.0006, spread=0.03, noise_amt=0.4, noise_dec=0.003)
    h = hiss(0.35, rnd, 5200, 0.8, 0.02, 0.1)
    deb = zeros(N(0.3))
    for _ in range(6):
        add_at(deb, click(rnd, rnd.uniform(2500, 6000), 800, 0.004, 0.04, 0.6), rnd.uniform(0.02, 0.2), rnd.uniform(0.05, 0.15))
    return mix((sub, 1.0, 0), (impact, 0.8, 0), (clank, 0.55, 0.002), (h, 0.25, 0.05), (deb, 0.5, 0))


def plate_hit(seed, base=520.0):
    rnd = random.Random(seed)
    crack = mul(hp(white(N(0.02), rnd), 2500), env_exp(N(0.02), 0.00002, 0.0015))
    # thick armour: dense, fairly damped modes (a clank, not a bell)
    modes = []
    for f, d, g in ((base, 0.12, 1.0), (base * 1.59, 0.09, 0.8), (base * 2.14, 0.07, 0.7), (base * 2.92, 0.05, 0.55), (base * 4.03, 0.035, 0.45), (base * 5.4, 0.025, 0.35), (base * 7.7, 0.015, 0.3)):
        modes.append((f, d, g))
        modes.append((f * rnd.uniform(1.01, 1.04), d * 0.7, g * 0.5))
    plate = strike(0.6, rnd, modes, exc=0.0004, spread=0.01, noise_amt=0.45)
    thud = thump(0.3, 180, 80, 0.02, 0.05)
    return mix((crack, 0.9, 0), (plate, 0.75, 0.0003), (thud, 0.5, 0))


def robot_hit(seed=601):
    rnd = random.Random(seed)
    sp = crackle(0.15, rnd, 900, 50, burst_ms=(0.03, 0.4), band=(2500, 12000))
    return reverb(mix((plate_hit(seed, 480), 1.0, 0), (sp, 0.35, 0.004)), "concrete_room_b", wet=0.12)


def robot_weakpoint(seed=611):
    rnd = random.Random(seed)
    ping = strike(0.6, rnd, [(2950, 0.2, 1.0), (5910, 0.12, 0.4), (8320, 0.06, 0.25), (1480, 0.08, 0.3)], exc=0.0002, noise_amt=0.2)
    cr = crackle(0.45, rnd, 1500, 120, amp_pow=1.8, burst_ms=(0.05, 1.5), band=(1200, 11000))
    cr = mul(cr, env_exp(len(cr), 0.001, 0.15))
    bz = mul(arc_buzz(0.3, rnd, 50, 8, 2600), env_exp(N(0.3), 0.002, 0.08))
    pop = thump(0.2, 260, 90, 0.01, 0.04)
    dry = mix((plate_hit(seed + 1, 610), 0.5, 0), (ping, 0.55, 0.002), (cr, 0.9, 0.0), (bz, 0.45, 0.01), (pop, 0.6, 0))
    return reverb(dry, "concrete_room_b", wet=0.15)


def robot_zap(seed=621):
    rnd = random.Random(seed)
    out = zeros(N(0.5))
    t = 0.0
    for k in range(rnd.randint(3, 5)):
        d = rnd.uniform(0.03, 0.09)
        b = mul(arc_buzz(d, rnd, 50, 6, rnd.uniform(2200, 3600)), env_pts(N(d), [(0, 0), (0.002, 1), (d * 0.6, 0.8), (d, 0)]))
        c = crackle(d, rnd, 2500, burst_ms=(0.05, 0.8), band=(1500, 12000))
        add_at(out, mix((b, 0.8, 0), (c, 0.7, 0)), t, rnd.uniform(0.6, 1.0) * (0.85 ** k))
        t += d + rnd.uniform(0.005, 0.04)
    pop = thump(0.15, 200, 70, 0.01, 0.03)
    add_at(out, pop, 0, 0.5)
    return reverb(trim_tail(out, -60), "small_room", wet=0.2)


def tesla_charge(seed=631, sec=0.55):
    rnd = random.Random(seed)
    n = N(sec)
    f = lambda t: 260 * (14.0 ** ((t / sec) ** 1.25))
    whine = sweep_tone(n, lambda t: f(t) * (1 + 0.004 * math.sin(TAU * 37 * t)), ((1, 1.0), (2, 0.3), (3, 0.22), (5, 0.08)))
    beat = sweep_tone(n, lambda t: f(t) * 1.012, ((1, 1.0),))
    e = [((i / n) ** 1.4) for i in range(n)]
    whine = mul([a + 0.5 * b for a, b in zip(whine, beat)], e)
    cr = crackle(sec, rnd, 25, 900, amp_pow=2.0, band=(1800, 11000))
    cr = mul(cr, [0.2 + 0.8 * (i / n) ** 2 for i in range(n)])
    hum = mul(mains_hum(n, 50), [(i / n) ** 2 for i in range(n)])
    bz = mul(arc_buzz(sec, rnd, 50, 12, 3000), [(i / n) ** 3 for i in range(n)])
    dry = mix((whine, 0.5, 0), (cr, 0.9, 0), (lp(hum, 900), 0.25, 0), (bz, 0.4, 0))
    dry = fade(dry, 0.01, 0.012)
    return reverb(dry, "small_room", wet=0.18)


def tesla_shot(seed=641):
    rnd = random.Random(seed)
    sec = 0.5
    n = N(sec)
    crack = mul(hp(white(n, rnd), 1200), env_exp(n, 0.00002, 0.0022))
    snap = crackle(0.04, rnd, 25000, amp_pow=1.0, burst_ms=(0.02, 0.3), band=(800, 14000))
    arc = mul(crackle(sec, rnd, 4000, 200, amp_pow=1.6, band=(900, 12000)), env_exp(n, 0.0005, 0.07))
    bz = mul(arc_buzz(sec, rnd, 50, 6, 2400, 0.8), env_exp(n, 0.001, 0.09))
    sub = thump(sec, 170, 45, 0.02, 0.085, drive=1.6)
    boom = noise_hit(sec, rnd, 3000, 150, 0.015, 0.05)
    dry = mix((crack, 1.2, 0), (snap, 1.0, 0), (arc, 0.9, 0.001), (bz, 0.5, 0.003), (sub, 1.2, 0), (boom, 0.8, 0))
    dry = softclip(compress(dry, -12, 3, 0.0005, 0.06, 3), 1.6)
    return trim_tail(fade(reverb(dry, "concrete_room_c", wet=0.4), 0, 0.06), -60)


def robot_alert(seed=651):
    """Three low, detuned, ring-modulated tones: falling tritone, then a
    longer bent tone.  Menacing rather than cute."""
    rnd = random.Random(seed)
    out = zeros(N(0.75))
    seq = [(0.0, 0.14, 233.1, 233.1), (0.17, 0.14, 164.8, 164.8), (0.34, 0.3, 220.0, 150.0)]
    for t0, d, fa, fb in seq:
        n = N(d)
        fr = lambda t, fa=fa, fb=fb, d=d: fa + (fb - fa) * min(1.0, max(0.0, (t - d * 0.35) / (d * 0.65)))
        a = sweep_tone(n, fr, saw_harm(14, 1.1))
        b = sweep_tone(n, lambda t: fr(t) * 1.008, saw_harm(14, 1.1))
        sub = sweep_tone(n, lambda t: fr(t) * 0.5, ((1, 1.0),))
        rm = tone(n, 31.0)
        x = [(p + q) * (0.7 + 0.3 * r) + 0.5 * s for p, q, r, s in zip(a, b, rm, sub)]
        x = peq(peq(lp(x, 3200), 900, 1.2, 6), 2300, 2, 4)
        x = softclip(x, 2.2)
        x = mul(x, env_pts(n, [(0, 0), (0.004, 1), (d - 0.03, 0.9), (d, 0)]))
        add_at(out, x, t0)
    return trim_tail(reverb(out, "concrete_room", wet=0.25), -60)


def robot_death(seed=661):
    rnd = random.Random(seed)
    sec = 1.65
    n = N(sec)
    f = lambda t: 45 + 1150 * math.exp(-t / 0.38)
    whine = sweep_tone(n, lambda t: f(t) * (1 + 0.02 * math.sin(TAU * 13 * t)), ((1, 1.0), (2, 0.4), (3, 0.3), (4, 0.12)))
    whine = mul(whine, env_pts(n, [(0, 0), (0.02, 1), (0.6, 0.6), (1.3, 0.0), (sec, 0)]))
    cr = crackle(1.0, rnd, 1800, 30, amp_pow=1.8, band=(1200, 11000))
    bz = mul(arc_buzz(0.35, rnd, 50, 6, 2800), env_exp(N(0.35), 0.002, 0.12))
    out = mix((whine, 0.35, 0), (cr, 0.8, 0), (bz, 0.6, 0.0))
    # collapse: knees (0.55 s), torso (0.82 s), settling rattle
    for t, g, s in ((0.55, 1.0, 1), (0.82, 0.8, 2), (1.05, 0.35, 3)):
        add_at(out, thump(0.5, 95, 30, 0.03, 0.2, drive=1.8), t, g)
        add_at(out, noise_hit(0.3, rnd, 1400, 100, 0.01, 0.06), t, 0.7 * g)
        b = rnd.uniform(180, 260)
        add_at(out, strike(0.6, rnd, [(b, 0.15, 1.0), (b * 2.6, 0.1, 0.8), (b * 4.3, 0.08, 0.6), (b * 7.1, 0.05, 0.45), (b * 11.2, 0.03, 0.3)], exc=0.0006, spread=0.03, noise_amt=0.4), t + 0.003, 0.6 * g)
    for _ in range(14):
        t = rnd.uniform(0.6, 1.35)
        add_at(out, click(rnd, rnd.uniform(1800, 5000), 600, 0.008, 0.06, 0.8), t, rnd.uniform(0.05, 0.2))
    return trim_tail(fade(reverb(out, "concrete_room", wet=0.35), 0, 0.1), -60)


def robot_idle_loop(seed=671, sec=2.0):
    rnd = random.Random(seed)
    n = N(sec)
    # periodic parts: whole cycles over the loop length (50 Hz -> 100 cycles)
    hum = mains_hum(n, 50)
    wob = [0.85 + 0.15 * math.sin(TAU * (1.0 / sec) * i / SR) for i in range(n)]
    hum = mul(circ(hum, lambda s: lp(s, 1200)), wob)
    coil = tone(n, round(2150.0 * sec) / sec, ((1, 1.0), (2, 0.2)))
    # aperiodic parts: crossfaded
    m = N(sec + 0.4)
    fan = bp(pink(m, rnd), 700, 0.6)
    fan_am = tone(m, 23.0)
    fan = [v * (0.85 + 0.15 * a) for v, a in zip(fan, fan_am)]
    tick = zeros(m)
    for _ in range(3):
        add_at(tick, click(rnd, rnd.uniform(1500, 3000), 500, 0.006, 0.05, 0.6), rnd.uniform(0.1, sec), 0.1)
    ap = loop_xfade([a + b for a, b in zip(fan, tick)], 0.4)
    out = [h * 0.5 + c * 0.012 + a * 0.6 for h, c, a in zip(hum, coil, ap)]
    return out


# ---------------------------------------------------------------- doors
def door_breach_synth(seed=701):
    rnd = random.Random(seed)
    kick = thump(0.5, 120, 45, 0.02, 0.12, drive=2.0)
    kick_n = noise_hit(0.3, rnd, 2500, 150, 0.008, 0.04)
    lock = mix((click(rnd, 3200, 900, 0.02, 0.2, 1.0), 1.0, 0), (click(rnd, 4700, 1300, 0.015, 0.15, 1.0), 0.7, 0.004))
    b = 110
    slab = strike(1.0, rnd, [(b, 0.35, 1.0), (b * 2.4, 0.25, 0.8), (b * 4.1, 0.18, 0.6), (b * 6.6, 0.12, 0.5), (b * 9.8, 0.08, 0.4), (b * 14.3, 0.05, 0.3)], exc=0.001, spread=0.02, noise_amt=0.3)
    slam = thump(0.5, 90, 35, 0.03, 0.15, drive=2.0)
    out = mix((kick, 1.0, 0), (kick_n, 0.8, 0), (lock, 0.6, 0.004), (slab, 0.6, 0.006), (slam, 0.9, 0.16), (slab, 0.35, 0.16))
    for _ in range(10):
        add_at(out, click(rnd, rnd.uniform(2000, 6000), 700, 0.006, 0.05, 0.6), rnd.uniform(0.05, 0.5), rnd.uniform(0.05, 0.15))
    return out


# ---------------------------------------------------------------- ambience
def _periodic_noise(sec, rnd, f_lo, f_hi, xf=1.0, kind="pink"):
    m = N(sec + xf)
    x = pink(m, rnd) if kind == "pink" else white(m, rnd)
    x = bp(x, math.sqrt(f_lo * f_hi), max(0.3, math.sqrt(f_lo * f_hi) / (f_hi - f_lo)))
    return loop_xfade(x, xf)


def slow_mod(n, rnd, sec, cycles=(1, 2, 3), depth=0.25):
    """Smooth random modulation that is periodic over 'sec'."""
    comps = [(c, rnd.uniform(0, TAU), rnd.uniform(0.3, 1.0)) for c in cycles]
    tot = sum(a for _, _, a in comps)
    return [1.0 + depth * sum(a * math.sin(TAU * c * i / n + p) for c, p, a in comps) / tot for i in range(n)]


def ambience_facility(seed=801, sec=12.0, stereo=True):
    out = []
    for ch in range(2 if stereo else 1):
        rnd = random.Random(seed + 17 * ch)
        n = N(sec)
        vent = _periodic_noise(sec, rnd, 150, 1800)
        vent = mul(vent, slow_mod(n, rnd, sec, (1, 3, 5), 0.18))
        air = _periodic_noise(sec, rnd, 1800, 6000, kind="white")
        rumble = circ(_periodic_noise(sec, rnd, 25, 120), lambda s: lp(s, 160))
        hum = mul(mains_hum(n, 50), slow_mod(n, rnd, sec, (1, 2), 0.2))
        mach = tone(n, 29.5, ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)))  # 29.5*12 = 354 cycles
        ticks = zeros(N(sec + 1.0))
        for k in range(7):
            t = rnd.uniform(0.3, sec)
            add_at(ticks, click(rnd, rnd.uniform(1800, 4200), rnd.uniform(400, 800), rnd.uniform(0.01, 0.03), 0.15, 0.7), t, rnd.uniform(0.25, 0.6))
        clank = zeros(N(sec + 1.0))
        for k in range(2):
            b = rnd.uniform(150, 260)
            add_at(clank, strike(0.8, rnd, [(b, 0.3, 1.0), (b * 2.7, 0.2, 0.7), (b * 4.6, 0.12, 0.5)], exc=0.001, noise_amt=0.3), rnd.uniform(1.0, sec), 0.12)
        ev = lp(reverb([a + b for a, b in zip(ticks, clank)], "industrial_hall", wet=1.0, dry=0.25), 6000)
        ev = loop_xfade(ev[: N(sec + 1.0)], 1.0)
        hum_f = circ(hum, lambda s: lp(s, 600))
        mach_f = circ(mach, lambda s: lp(s, 300))
        x = [0.55 * v + 0.06 * a + 0.9 * r + 0.012 * h + 0.05 * m + 0.6 * e for v, a, r, h, m, e in zip(vent, air, rumble, hum_f, mach_f, ev)]
        out.append(x)
    return out


def ambience_hall(seed=811, sec=12.0, stereo=True):
    out = []
    for ch in range(2 if stereo else 1):
        rnd = random.Random(seed + 29 * ch)
        n = N(sec)
        # turbine drone: shaft 25 Hz (300 cycles / 12 s) and blade-pass partials
        shaft = tone(n, 25.0, ((1, 1.0), (2, 0.7), (3, 0.5), (4, 0.3), (6, 0.2), (8, 0.12)))
        blade = tone(n, 25.0 * 17, ((1, 1.0), (2, 0.25)))
        beat = tone(n, 25.0 * 17 + 0.25, ((1, 1.0),))  # 0.25 Hz beating, 3 cycles/12 s
        blade = [a + b for a, b in zip(blade, beat)]
        mod = slow_mod(n, rnd, sec, (1, 2, 4), 0.2)
        roar = mul(_periodic_noise(sec, rnd, 40, 700), mod)
        air = _periodic_noise(sec, rnd, 700, 4000)
        ev = zeros(N(sec + 3.5))
        for k in range(3):
            b = rnd.uniform(120, 220)
            add_at(ev, strike(1.0, rnd, [(b, 0.4, 1.0), (b * 2.5, 0.25, 0.6), (b * 4.2, 0.15, 0.4)], exc=0.001, noise_amt=0.3), rnd.uniform(0.5, sec), 0.1)
        ev = reverb(ev, "industrial_hall", wet=1.0, dry=0.1)[: N(sec + 3.0)]
        ev = loop_xfade(ev, 3.0)
        x = [0.06 * s + 0.012 * b + 0.8 * r + 0.18 * a + 0.5 * e for s, b, r, a, e in zip(circ(shaft, lambda s_: lp(s_, 400)), blade, roar, air, ev)]
        out.append(circ(x, lambda s_: lp(s_, 8000)))
    return out


def ambience_servers(seed=821, sec=10.0, stereo=True):
    out = []
    for ch in range(2 if stereo else 1):
        rnd = random.Random(seed + 41 * ch)
        n = N(sec)
        fans = [0.0] * n
        for k in range(5):
            bpf = round(rnd.uniform(180, 330) * sec) / sec  # whole cycles per loop
            ft = tone(n, bpf, ((1, 1.0), (2, 0.35), (3, 0.15)))
            fans = [a + b * rnd.uniform(0.3, 0.6) for a, b in zip(fans, ft)]
        wh = _periodic_noise(sec, rnd, 400, 5000)
        hiss_ = _periodic_noise(sec, rnd, 5000, 12000, kind="white")
        hum = mains_hum(n, 50)
        ticks = zeros(N(sec + 0.5))
        for k in range(18):
            t = rnd.uniform(0.0, sec)
            add_at(ticks, click(rnd, rnd.uniform(3000, 6000), 900, 0.002, 0.02, 0.5), t, rnd.uniform(0.01, 0.04))
        ticks = loop_xfade(ticks, 0.5)
        x = [0.004 * f + 0.6 * w + 0.15 * h + 0.02 * m + t for f, w, h, m, t in zip(fans, wh, hiss_, circ(hum, lambda s_: lp(s_, 800)), ticks)]
        out.append(x)
    return out


def electric_buzz_loop(seed=831, sec=2.0):
    """Fluorescent ballast buzz: 100 Hz rasp (whole cycles), flicker ticks."""
    rnd = random.Random(seed)
    n = N(sec)
    pulse = [0.0] * n
    period = SR / 100.0
    for i in range(n):
        ph = (i % period) / period
        pulse[i] = math.exp(-ph * 30.0) - 0.033
    ras = mul(white(n, rnd), [abs(math.sin(math.pi * 100 * i / SR)) ** 16 for i in range(n)])
    tone_ = tone(n, 100.0, ((1, 1.0), (2, 0.5), (3, 0.6), (4, 0.3), (5, 0.35), (7, 0.2), (9, 0.12)))
    x = [0.45 * p + 0.25 * t + 0.3 * r for p, t, r in zip(circ(pulse, lambda s: bp(s, 1800, 0.7)), tone_, circ(ras, lambda s: bp(s, 3500, 0.8)))]
    return circ(x, lambda s: lp(hp(s, 80), 9000))


# ---------------------------------------------------------------- player/UI
def player_hurt(seed=901):
    rnd = random.Random(seed)
    sec = 0.5
    n = N(sec)
    bz = mul(arc_buzz(sec, rnd, 50, 6, 2600), env_exp(n, 0.001, 0.08))
    cr = mul(crackle(sec, rnd, 2500, 100, band=(1500, 10000)), env_exp(n, 0.001, 0.07))
    th = thump(sec, 150, 48, 0.03, 0.12, drive=1.5)
    body = noise_hit(sec, rnd, 900, 100, 0.02, 0.06)
    return mix((bz, 0.8, 0), (cr, 0.6, 0), (th, 1.0, 0.004), (body, 0.6, 0.004))


def heartbeat_synth(seed=911):
    rnd = random.Random(seed)
    out = zeros(N(0.95))
    for t, g, f0 in ((0.0, 1.0, 62), (0.24, 0.65, 55)):
        th = thump(0.25, f0 * 1.6, f0 * 0.7, 0.03, 0.06, attack=0.006)
        nb = mul(lp(white(N(0.25), rnd), 120), env_exp(N(0.25), 0.005, 0.04))
        add_at(out, mix((th, 1.0, 0), (nb, 1.5, 0)), t, g)
    return lp(out, 300)


def beep_tone(sec, f, harm=((1, 1.0), (2, 0.12), (3, 0.05)), att=0.003, dec=None):
    n = N(sec)
    x = tone(n, f, harm)
    e = env_exp(n, att, dec) if dec else env_pts(n, [(0, 0), (att, 1), (sec - 0.01, 0.8), (sec, 0)])
    return mul(x, e)


def ui_objective(seed=921):
    out = zeros(N(0.6))
    for t, f in ((0.0, 659.25), (0.09, 987.77), (0.18, 1318.5)):
        add_at(out, beep_tone(0.35, f, ((1, 1.0), (2, 0.25), (3, 0.1), (4.02, 0.06)), 0.002, 0.12), t, 0.7)
    return trim_tail(reverb(out, "small_room", wet=0.25), -60)


def ui_hack_done(seed=931):
    out = zeros(N(0.7))
    for t, f in ((0.0, 880.0), (0.08, 1174.66), (0.16, 1760.0)):
        add_at(out, beep_tone(0.4, f, ((1, 1.0), (2, 0.3), (3, 0.12)), 0.002, 0.14), t, 0.7)
    return trim_tail(reverb(out, "small_room", wet=0.25), -60)


def ui_hack_tick(seed=941):
    rnd = random.Random(seed)
    t = beep_tone(0.03, 1500, ((1, 1.0), (3, 0.2)), 0.001, 0.008)
    c = click(rnd, 4200, 1200, 0.002, 0.02, 0.5)
    return mix((t, 0.8, 0), (c, 0.3, 0))


def ui_click(seed=951):
    rnd = random.Random(seed)
    return mix((click(rnd, 3800, 1100, 0.003, 0.03, 0.8), 1.0, 0), (beep_tone(0.025, 1200, ((1, 1.0),), 0.001, 0.006), 0.3, 0))


def hitmarker(seed=961):
    """Crisp confirmation tick: bright modal click + short metallic ping +
    a 'tsk' of high-passed noise; ~80 ms."""
    rnd = random.Random(seed)
    a = click(rnd, 4600, 2100, 0.008, 0.08, 1.0)
    ping = beep_tone(0.08, 2900, ((1, 1.0), (1.51, 0.35), (2.33, 0.2)), 0.0005, 0.022)
    tsk = mul(hp(white(N(0.05), rnd), 3500), env_exp(N(0.05), 0.0003, 0.008))
    return compress(mix((a, 1.0, 0), (ping, 0.45, 0), (tsk, 0.35, 0)), -14, 3, 0.0005, 0.03, 3)


def hitmarker_kill(seed=971):
    """Heavier double tick with a ringing ping and a small thump."""
    rnd = random.Random(seed)
    a = click(rnd, 3900, 1600, 0.009, 0.1, 1.0)
    b = click(rnd, 4400, 1800, 0.008, 0.1, 1.0)
    ping = beep_tone(0.22, 2350, ((1, 1.0), (2.76, 0.3), (5.4, 0.12)), 0.0005, 0.06)
    t = thump(0.12, 180, 90, 0.01, 0.035)
    tsk = mul(hp(white(N(0.06), rnd), 3000), env_exp(N(0.06), 0.0003, 0.01))
    y = mix((a, 1.0, 0), (b, 0.8, 0.035), (ping, 0.5, 0.004), (t, 0.5, 0), (tsk, 0.3, 0))
    return compress(y, -14, 3, 0.0005, 0.04, 3)


def extraction_alarm(seed=981):
    """Industrial two-tone klaxon (two cycles), with a concrete room tail."""
    out = zeros(N(2.2))
    for k in range(2):
        for j, f in enumerate((587.3, 440.0)):
            t0 = k * 0.9 + j * 0.42
            n = N(0.4)
            a = sweep_tone(n, lambda t, f=f: f * (1 + 0.006 * math.sin(TAU * 6 * t)), saw_harm(16, 1.0))
            b = tone(n, f * 1.006, saw_harm(16, 1.0))
            x = [p + 0.7 * q for p, q in zip(a, b)]
            x = peq(peq(lp(x, 4000), 1100, 1.5, 8), 2600, 2, 5)
            x = mul(softclip(x, 1.6), env_pts(n, [(0, 0), (0.01, 1), (0.37, 0.9), (0.4, 0)]))
            add_at(out, x, t0)
    return trim_tail(reverb(out, "concrete_room", wet=0.35), -60)


# ==========================================================================
# standalone: write the fully synthesized set
# ==========================================================================
def build_all(outdir):
    jobs = {
        "dry_fire": (dry_fire(), -8), "mag_out": (mag_out(), -7), "mag_in": (mag_in(), -6),
        "bolt": (bolt_pull(), -6), "pistol_slide": (pistol_slide(), -6), "weapon_switch": (weapon_switch(), -9),
        "ads_in": (ads_in(), -16), "ricochet": (ricochet(), -5), "robot_hit": (robot_hit(), -3),
        "robot_weakpoint": (robot_weakpoint(), -2), "robot_zap": (robot_zap(), -4), "tesla_charge": (tesla_charge(), -4),
        "tesla_shot": (tesla_shot(), -1.5), "robot_alert": (robot_alert(), -4), "robot_death": (robot_death(), -1.5),
        "robot_idle_loop": (robot_idle_loop(), -12), "player_hurt": (player_hurt(), -4), "heartbeat": (heartbeat_synth(), -8),
        "ui_click": (ui_click(), -16), "ui_objective": (ui_objective(), -12), "ui_hack_tick": (ui_hack_tick(), -18),
        "ui_hack_done": (ui_hack_done(), -12), "hitmarker": (hitmarker(), -10), "hitmarker_kill": (hitmarker_kill(), -8),
        "extraction_alarm": (extraction_alarm(), -6), "electric_buzz_loop": (electric_buzz_loop(), -16),
        "door_breach": (door_breach_synth(), -1.5),
    }
    for k in range(4):
        jobs["shell_tink_%d" % k] = (shell_tink(500 + k), -14)
    for k in range(3):
        jobs["impact_metal_%d" % k] = (impact_metal(410 + k), -5)
        jobs["impact_concrete_%d" % k] = (impact_concrete(420 + k), -6)
        jobs["robot_servo_%d" % k] = (servo(560 + k, 0.4 + 0.08 * k, 130 + 25 * k, 240 + 30 * k, 13, k != 1), -9)
        jobs["robot_hydraulic_%d" % k] = (hydraulic(570 + k, 0.6 + 0.1 * k), -8)
        jobs["rifle_shot_%d" % k] = (gunshot_synth(100 + k, "rifle"), -1)
        jobs["pistol_shot_%d" % k] = (gunshot_synth(110 + k, "pistol"), -1)
        jobs["rifle_shot_suppressed_%d" % k] = (gunshot_synth(120 + k, "rifle", True), -5)
        jobs["pistol_shot_suppressed_%d" % k] = (gunshot_synth(130 + k, "pistol", True), -6)
    for k in range(4):
        jobs["robot_step_%d" % k] = (reverb(robot_step_synth(590 + k), "concrete_room_b", 0.2), -2)
    for k in range(6):
        jobs["step_concrete_%d" % k] = (step_concrete_synth(700 + k), -14)
    for name, (sig, pk) in jobs.items():
        write_wav(os.path.join(outdir, name + ".wav"), fade(sig, 0.0, 0.01), pk)
        print("synth", name)
    for name, fn, pk in (("ambience_facility", ambience_facility, -12), ("ambience_hall", ambience_hall, -12), ("ambience_servers", ambience_servers, -14)):
        write_wav(os.path.join(outdir, name + ".wav"), fn(), pk)
        print("synth", name)


if __name__ == "__main__":
    build_all(sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "..", "..", "staging", "audio", "_synth_preview"))
