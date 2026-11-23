# Procedural sound design for BREACH. Pure Python stdlib, deterministic (seeded).
# All output is original first-party work. Run: python -I tools/synth_audio.py assets/audio
import math, random, struct, sys, os, wave

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/audio"
os.makedirs(OUT, exist_ok=True)


def zeros(sec):
    return [0.0] * int(SR * sec)


def noise(n, rnd):
    return [rnd.uniform(-1, 1) for _ in range(n)]


def lowpass(x, fc):
    a = math.exp(-2 * math.pi * fc / SR)
    y, s = [], 0.0
    for v in x:
        s = (1 - a) * v + a * s
        y.append(s)
    return y


def lowpass_sweep(x, f0, f1, tau):
    y, s = [], 0.0
    for i, v in enumerate(x):
        fc = f1 + (f0 - f1) * math.exp(-i / SR / tau)
        a = math.exp(-2 * math.pi * fc / SR)
        s = (1 - a) * v + a * s
        y.append(s)
    return y


def highpass(x, fc):
    lp = lowpass(x, fc)
    return [a - b for a, b in zip(x, lp)]


def bandpass(x, f, q):
    # RBJ biquad band-pass
    w = 2 * math.pi * f / SR
    al = math.sin(w) / (2 * q)
    b0, b1, b2 = al, 0, -al
    a0, a1, a2 = 1 + al, -2 * math.cos(w), 1 - al
    y = []
    x1 = x2 = y1 = y2 = 0.0
    for v in x:
        o = (b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, v, y1, o
        y.append(o)
    return y


def env_exp(n, attack, decay):
    out = []
    for i in range(n):
        t = i / SR
        a = min(1.0, t / attack) if attack > 0 else 1.0
        out.append(a * math.exp(-t / decay))
    return out


def mul(a, b):
    return [x * y for x, y in zip(a, b)]


def mix(*tracks):
    n = max(len(t) for t, _, _ in tracks)
    out = [0.0] * n
    for t, g, off in tracks:
        o = int(off * SR)
        for i, v in enumerate(t):
            if 0 <= i + o < n:
                out[i + o] += v * g
    return out


def pad(x, sec):
    return x + [0.0] * int(sec * SR)


def sine_sweep(n, f0, f1, tau, phase=0.0):
    out, ph = [], phase
    for i in range(n):
        f = f1 + (f0 - f1) * math.exp(-i / SR / tau)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph))
    return out


def reverb(x, wet=0.3, room=0.82, damp=0.4, tail=0.8):
    # Small Schroeder/Freeverb style reverb for indoor tails.
    x = pad(x, tail)
    combs = [1116, 1188, 1277, 1356, 1422, 1491]
    aps = [556, 441, 341]
    n = len(x)
    out = [0.0] * n
    for c in combs:
        buf = [0.0] * c
        idx, filt = 0, 0.0
        for i in range(n):
            o = buf[idx]
            filt = o * (1 - damp) + filt * damp
            buf[idx] = x[i] + filt * room
            idx = (idx + 1) % c
            out[i] += o
    for a in aps:
        buf = [0.0] * a
        idx = 0
        for i in range(n):
            b = buf[idx]
            o = -out[i] + b
            buf[idx] = out[i] + b * 0.5
            idx = (idx + 1) % a
            out[i] = o
    return [d + w * wet / len(combs) * 3 for d, w in zip(x, out)]


def normalize(x, peak=0.89):
    m = max(1e-9, max(abs(v) for v in x))
    return [v / m * peak for v in x]


def softclip(x, drive=1.5):
    return [math.tanh(v * drive) / math.tanh(drive) for v in x]


def fade_out(x, sec=0.02):
    n = int(sec * SR)
    for i in range(min(n, len(x))):
        x[-1 - i] *= i / n
    return x


def write(name, x, peak=0.89):
    x = fade_out(normalize(x, peak))
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in x))
    print("wrote", name, round(len(x) / SR, 2), "s")


def gunshot(seed, body_hz, crack_amt, tail, wet, suppressed=False):
    rnd = random.Random(seed)
    n = int(SR * 0.45)
    # Supersonic crack / muzzle blast: bright noise, very fast decay.
    crack = mul(highpass(noise(n, rnd), 1800), env_exp(n, 0.0002, 0.006))
    blast = mul(lowpass_sweep(noise(n, rnd), 6000, 400, 0.025), env_exp(n, 0.0005, 0.05))
    thump = mul(sine_sweep(n, body_hz * 2.2, body_hz, 0.02), env_exp(n, 0.0008, 0.07))
    mech = mul(bandpass(noise(n, rnd), 3200, 6), env_exp(n, 0.0, 0.012))
    if suppressed:
        dry = mix((crack, 0.12, 0), (lowpass(blast, 1400), 0.9, 0), (thump, 0.8, 0), (mech, 0.9, 0.004))
        dry = softclip(dry, 1.2)
    else:
        dry = mix((crack, crack_amt, 0), (blast, 1.0, 0), (thump, 1.1, 0), (mech, 0.5, 0.003))
        dry = softclip(dry, 2.4)
    return reverb(dry, wet=wet, room=0.84, damp=0.35, tail=tail)


rnd0 = random.Random(9)

# --- Weapons ---
write("rifle_shot", gunshot(1, 70, 0.9, 0.9, 0.55))
write("rifle_shot_suppressed", gunshot(2, 85, 0.1, 0.45, 0.25, True), 0.6)
write("pistol_shot", gunshot(3, 95, 0.7, 0.7, 0.45))
write("pistol_shot_suppressed", gunshot(4, 105, 0.1, 0.35, 0.2, True), 0.6)


def click(seed, f, q, dec, n_sec=0.08, amp=1.0):
    rnd = random.Random(seed)
    n = int(SR * n_sec)
    return [v * amp for v in mul(bandpass(noise(n, rnd), f, q), env_exp(n, 0.0, dec))]


write("dry_fire", mix((click(10, 2400, 4, 0.006), 1, 0), (click(11, 900, 3, 0.01), 0.5, 0.004)), 0.5)
write("mag_out", mix((click(12, 1300, 3, 0.02, 0.3), 1, 0), (click(13, 600, 2, 0.04, 0.3), 0.7, 0.05)), 0.6)
write("mag_in", mix((click(14, 1800, 5, 0.012, 0.3), 1, 0), (click(15, 700, 2, 0.03, 0.3), 0.8, 0.02), (click(16, 2600, 6, 0.008, 0.3), 0.7, 0.09)), 0.7)
write("bolt", mix((click(17, 2100, 4, 0.015, 0.35), 1, 0), (click(18, 1500, 5, 0.02, 0.35), 0.9, 0.12), (click(19, 3000, 7, 0.01, 0.35), 0.8, 0.14)), 0.7)
write("weapon_switch", mix((click(20, 1100, 2, 0.04, 0.35), 0.8, 0), (click(21, 2200, 5, 0.01, 0.35), 0.6, 0.15)), 0.5)
write("ads_in", click(22, 800, 1.5, 0.03, 0.12), 0.25)
write("shell_tink", mix(*[(mul(sine_sweep(int(SR * 0.25), f, f, 1), env_exp(int(SR * 0.25), 0, 0.05)), g, o) for f, g, o in [(4200, 1, 0), (6100, 0.5, 0), (4300, 0.5, 0.07), (6000, 0.3, 0.07)]]), 0.25)

# --- Impacts ---
def impact_metal(seed):
    rnd = random.Random(seed)
    n = int(SR * 0.5)
    hit = mul(highpass(noise(n, rnd), 2000), env_exp(n, 0, 0.008))
    ring = mix(*[(mul(sine_sweep(n, f, f * 0.98, 0.3), env_exp(n, 0, d)), g, 0) for f, g, d in [(2300 + rnd.uniform(-200, 200), 0.5, 0.12), (3700, 0.3, 0.08), (5200, 0.2, 0.05)]])
    return mix((hit, 1, 0), (ring, 0.6, 0))


def impact_concrete(seed):
    rnd = random.Random(seed)
    n = int(SR * 0.35)
    hit = mul(lowpass_sweep(noise(n, rnd), 5000, 500, 0.01), env_exp(n, 0, 0.02))
    debris = mul(bandpass(noise(n, rnd), 3000, 2), env_exp(n, 0.01, 0.06))
    return mix((hit, 1, 0), (debris, 0.25, 0.01))


for i in range(3):
    write(f"impact_metal_{i}", impact_metal(30 + i), 0.55)
    write(f"impact_concrete_{i}", impact_concrete(40 + i), 0.5)


def ricochet(seed):
    n = int(SR * 0.4)
    rnd = random.Random(seed)
    w = mul(sine_sweep(n, 5200, 1800, 0.12), env_exp(n, 0.005, 0.09))
    return mix((w, 0.5, 0), (impact_metal(seed), 0.7, 0))


write("ricochet", ricochet(50), 0.45)


# --- Electrical / robot ---
def crackle(seed, sec, density, f=2500, decay=0.003):
    rnd = random.Random(seed)
    n = int(SR * sec)
    out = [0.0] * n
    i = 0
    while i < n:
        i += int(rnd.expovariate(density) * SR) + 1
        L = int(SR * 0.012)
        amp = rnd.uniform(0.3, 1)
        for k in range(L):
            if i + k < n:
                out[i + k] += amp * rnd.uniform(-1, 1) * math.exp(-k / SR / decay)
    return bandpass(out, f, 0.7)


def hum(sec, f, harm=6, amp_mod=0.0):
    n = int(SR * sec)
    return [sum(math.sin(2 * math.pi * f * h * i / SR) / h ** 1.2 for h in range(1, harm + 1)) * (1 + amp_mod * math.sin(2 * math.pi * 7 * i / SR)) for i in range(n)]


zap = mix((crackle(60, 0.35, 120, 3500), 1, 0), (mul(hum(0.35, 120, 8), env_exp(int(SR * 0.35), 0.002, 0.08)), 0.35, 0))
write("robot_zap", zap, 0.6)
write("robot_hit", mix((impact_metal(61), 1, 0), (crackle(62, 0.25, 160, 4000), 0.6, 0.005)), 0.7)
write("robot_weakpoint", mix((impact_metal(63), 0.8, 0), (crackle(64, 0.4, 260, 3000), 1.0, 0), (mul(sine_sweep(int(SR * 0.4), 1800, 3600, 0.05), env_exp(int(SR * 0.4), 0, 0.08)), 0.3, 0)), 0.8)


def servo(seed, sec, f0, f1):
    n = int(SR * sec)
    rnd = random.Random(seed)
    tone = []
    ph = 0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * math.sin(t * math.pi)
        ph += 2 * math.pi * f / SR
        tone.append(math.sin(ph) * 0.5 + math.sin(ph * 2.01) * 0.3 + math.sin(ph * 3.02) * 0.15)
    gr = bandpass(noise(n, rnd), f1 * 2, 2)
    env = [math.sin(math.pi * i / n) ** 0.6 for i in range(n)]
    return mul(mix((tone, 0.7, 0), (gr, 0.4, 0)), env)


write("robot_servo", servo(70, 0.35, 420, 760), 0.3)


def footstep_robot(seed):
    rnd = random.Random(seed)
    n = int(SR * 0.4)
    thud = mul(sine_sweep(n, 120, 45, 0.03), env_exp(n, 0.001, 0.06))
    clank = mul(bandpass(noise(n, rnd), 1400, 3), env_exp(n, 0, 0.03))
    hyd = mul(bandpass(noise(n, rnd), 6000, 1), env_exp(n, 0.03, 0.05))
    return mix((thud, 1, 0), (clank, 0.5, 0), (hyd, 0.15, 0.04))


for i in range(3):
    write(f"robot_step_{i}", footstep_robot(80 + i), 0.55)

# Tesla discharge: the Teslabot's primary weapon. Sharp arc + thunder body.
def tesla_shot(seed):
    rnd = random.Random(seed)
    n = int(SR * 0.5)
    arc = mul(crackle(seed, 0.5, 900, 3800, 0.0015), env_exp(n, 0.0005, 0.07))
    body = mul(lowpass_sweep(noise(n, rnd), 4000, 200, 0.04), env_exp(n, 0.001, 0.08))
    buzz = mul(hum(0.5, 180, 10), env_exp(n, 0.001, 0.05))
    dry = softclip(mix((arc, 1.2, 0), (body, 0.9, 0), (buzz, 0.4, 0)), 2)
    return reverb(dry, 0.4, 0.82, 0.4, 0.6)


write("tesla_shot", tesla_shot(90), 0.75)


def charge(sec):
    n = int(SR * sec)
    ph = 0
    out = []
    for i in range(n):
        t = i / n
        f = 300 + 2400 * t ** 1.8
        ph += 2 * math.pi * f / SR
        out.append((math.sin(ph) + 0.3 * math.sin(ph * 1.5)) * t)
    return mix((out, 0.6, 0), (crackle(91, sec, 40 + 0, 3000), 0.5, 0))


write("tesla_charge", charge(0.55), 0.45)


def alert():
    out = []
    for k, f in enumerate([880, 660, 990]):
        n = int(SR * 0.09)
        out += [math.copysign(1, math.sin(2 * math.pi * f * i / SR)) * 0.4 * math.exp(-i / SR / 0.06) for i in range(n)]
    return lowpass(reverb(out, 0.3, 0.8, 0.3, 0.4), 5000)


write("robot_alert", alert(), 0.45)


def robot_death():
    n = int(SR * 1.6)
    ph = 0
    whine = []
    for i in range(n):
        t = i / SR
        f = 900 * math.exp(-t / 0.5) + 40
        ph += 2 * math.pi * f / SR
        whine.append(math.sin(ph) * math.exp(-t / 0.9))
    return mix((whine, 0.4, 0), (crackle(95, 1.0, 300, 3000), 0.9, 0), (impact_metal(96), 0.8, 0.0), (footstep_robot(97), 1.0, 0.55), (impact_metal(98), 0.5, 0.6), (footstep_robot(99), 0.8, 0.8))


write("robot_death", reverb(robot_death(), 0.35, 0.83, 0.4, 0.6), 0.85)
write("robot_idle_loop", mix((hum(2.0, 60, 5, 0.2), 0.5, 0), (crackle(100, 2.0, 6, 3000), 0.3, 0)), 0.18)

# --- Player / world ---
def footstep(seed, f=900):
    rnd = random.Random(seed)
    n = int(SR * 0.18)
    a = mul(lowpass(noise(n, rnd), f), env_exp(n, 0.002, 0.02))
    b = mul(bandpass(noise(n, rnd), 3500, 1.5), env_exp(n, 0.01, 0.015))
    return mix((a, 1, 0), (b, 0.3, 0.015))


for i in range(4):
    write(f"step_concrete_{i}", footstep(110 + i), 0.35)
    write(f"step_metal_{i}", mix((footstep(120 + i, 700), 1, 0), (impact_metal(130 + i), 0.12, 0)), 0.35)


def door(sec, seed):
    rnd = random.Random(seed)
    n = int(SR * sec)
    creak = []
    ph = 0
    for i in range(n):
        t = i / n
        f = 180 + 90 * math.sin(t * 9) + rnd.uniform(-10, 10)
        ph += 2 * math.pi * f / SR
        creak.append((math.sin(ph) + 0.5 * math.sin(3 * ph)) * math.sin(math.pi * t))
    rumble = mul(lowpass(noise(n, rnd), 300), [math.sin(math.pi * i / n) for i in range(n)])
    return mix((creak, 0.25, 0), (rumble, 1, 0), (footstep_robot(seed + 1), 0.8, sec - 0.15))


write("door_open", reverb(door(0.9, 140), 0.3, 0.8, 0.4, 0.5), 0.6)
write("door_breach", reverb(mix((footstep_robot(150), 1.5, 0), (impact_metal(151), 1, 0), (impact_concrete(152), 1, 0.01), (door(0.4, 153), 0.6, 0.02)), 0.4, 0.84, 0.35, 0.8), 0.9)
write("door_locked", mix((click(160, 900, 3, 0.03, 0.2), 1, 0), (click(161, 600, 3, 0.03, 0.2), 1, 0.08)), 0.4)

def beep(freqs, dur=0.08, gap=0.03, vol=0.5):
    out = []
    for f in freqs:
        n = int(SR * dur)
        out += [math.sin(2 * math.pi * f * i / SR) * vol * min(1, i / 200) * min(1, (n - i) / 400) for i in range(n)]
        out += [0.0] * int(SR * gap)
    return out


write("ui_objective", reverb(beep([660, 990, 1320], 0.09), 0.3, 0.8, 0.3, 0.4), 0.4)
write("ui_hack_tick", beep([1500], 0.03, 0.0), 0.2)
write("ui_hack_done", reverb(beep([880, 1175, 1760], 0.12), 0.3, 0.8, 0.3, 0.5), 0.45)
write("ui_click", beep([1200], 0.025, 0), 0.2)
write("hitmarker", mix((click(170, 4000, 6, 0.006, 0.06), 1, 0)), 0.35)
write("hitmarker_kill", mix((click(171, 3000, 6, 0.01, 0.12), 1, 0), (beep([1800], 0.05, 0, 0.3), 0.5, 0.0)), 0.4)


def player_hurt(seed):
    rnd = random.Random(seed)
    n = int(SR * 0.5)
    zz = mul(crackle(seed, 0.5, 500, 2500, 0.002), env_exp(n, 0.001, 0.1))
    th = mul(sine_sweep(n, 160, 60, 0.05), env_exp(n, 0.001, 0.1))
    return mix((zz, 0.8, 0), (th, 1, 0))


write("player_hurt", player_hurt(180), 0.6)


def heartbeat():
    out = zeros(0.9)
    for off, a in [(0.0, 1.0), (0.22, 0.7)]:
        n = int(SR * 0.2)
        b = mul(sine_sweep(n, 70, 40, 0.04), env_exp(n, 0.005, 0.05))
        for i, v in enumerate(b):
            out[int(off * SR) + i] += v * a
    return out


write("heartbeat", heartbeat(), 0.5)


def ambience():
    sec = 8.0
    n = int(SR * sec)
    rnd = random.Random(200)
    # Industrial room tone: loopable mains hum + ventilation air + distant clanks.
    vent = lowpass(noise(n, rnd), 500)
    h = hum(sec, 50, 6)
    out = mix((vent, 1.6, 0), (h, 0.05, 0))
    for k in range(5):
        t = rnd.uniform(0.5, sec - 1.5)
        out = mix((out, 1, 0), (lowpass(impact_metal(210 + k), 1200), 0.05, t))
    # Crossfade for seamless loop
    L = int(SR * 0.5)
    for i in range(L):
        a = i / L
        out[i] = out[i] * a + out[n - L + i] * (1 - a)
    return out[: n - L]


write("ambience_facility", ambience(), 0.3)
write("extraction_alarm", reverb(beep([740, 0, 740, 0], 0.25, 0.05, 0.5), 0.4, 0.85, 0.3, 0.8), 0.35)
print("done")
