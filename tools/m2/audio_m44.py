"""BREACH M4.4 ambience polish: bass-coherent stereo beds.

Why: the ambience_* loops were assembled from independently synthesised L/R
channels (separate noise seeds) and from time-offset copies of the same
recording per channel. Their bass is therefore uncorrelated between the two
channels (and partly phase-inverted in ambience_hall). Real room tone is
almost fully coherent at the two ears below ~300 Hz (the ears are 18 cm apart
and the wavelengths are metres long), so the beds sounded hollow: a phasey,
"hole in the middle" low end on headphones, and partly cancelling bass on
speakers.

What: per file, on the whole loop as one circular FFT (the loop seam stays
sample-exact), in mid/side form, each 1/6-octave band below 1.2 kHz gets at
least the diffuse-field coherence of two points 18 cm apart (sin(kd)/kd,
1.0 at DC, 0 from ~950 Hz). Band power is kept, so the tonal balance and the
level do not change; above ~950 Hz nothing changes. Mono files are skipped.

usage: python -I tools/m2/audio_m44.py [--report]
The untouched v0.4.3 beds are kept in staging/audio_m44/orig/ on the first run;
every run processes those originals, so the script is repeatable.
"""
import os, sys, wave, json, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUD = os.path.join(ROOT, "assets", "audio")
STG = os.path.join(ROOT, "staging", "audio_m44")
ORIG = os.path.join(STG, "orig")
NAMES = ["ambience_facility", "ambience_dock", "ambience_hall", "ambience_servers", "ambience_control",
         "ambience_pump", "ambience_switchgear", "ambience_core"]
D_EARS = 0.18
C_AIR = 343.0
F_TOP = 1200.0
MAX_MID_GAIN_DB = 9.0
EDGES = [20, 60, 120, 250, 500, 1000, 2000, 4000]


def load(p):
    w = wave.open(p)
    sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64).reshape(-1, ch) / 32768.0
    return sr, x


def save(p, sr, x):
    y = np.clip(np.round(x * 32768.0), -32768, 32767).astype(np.int16)
    w = wave.open(p, "wb")
    w.setnchannels(y.shape[1])
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(y.tobytes())
    w.close()


def target_coherence(f):
    kd = 2 * np.pi * np.maximum(f, 1e-6) * D_EARS / C_AIR
    g = np.sin(kd) / kd
    g[kd >= np.pi] = 0.0
    return np.clip(g, 0.0, 1.0)


def band_coh(X, fr, a, b):
    k = (fr >= a) & (fr < b)
    L, R = X[0][k], X[1][k]
    return float(np.real(np.sum(L * np.conj(R))) / np.sqrt(np.sum(abs(L) ** 2) * np.sum(abs(R) ** 2) + 1e-30))


def process(x, sr):
    n = len(x)
    L = np.fft.rfft(x[:, 0])
    R = np.fft.rfft(x[:, 1])
    fr = np.fft.rfftfreq(n, 1 / sr)
    M = (L + R) / np.sqrt(2)
    S = (L - R) / np.sqrt(2)
    # Mid and side power per bin, smoothed over a 1/6-octave window around it.
    cm = np.concatenate([[0.0], np.cumsum(abs(M) ** 2)])
    cs = np.concatenate([[0.0], np.cumsum(abs(S) ** 2)])
    df = fr[1]
    lo = np.clip(np.floor(fr * 2 ** (-1 / 12) / df).astype(int), 0, len(fr) - 1)
    hi = np.clip(np.ceil(fr * 2 ** (1 / 12) / df).astype(int) + 1, 1, len(fr))
    pm = cm[hi] - cm[lo]
    ps = cs[hi] - cs[lo]
    tot = pm + ps
    ok = (pm > 1e-30) & (tot > 1e-30)
    coh = np.where(ok, (pm - ps) / np.maximum(tot, 1e-30), 1.0)
    tgt = np.maximum(coh, target_coherence(fr))
    GM = np.where(ok, np.minimum(np.sqrt((1 + tgt) / 2 * tot / np.maximum(pm, 1e-30)), 10 ** (MAX_MID_GAIN_DB / 20)), 1.0)
    GS = np.where(ps > 1e-30, np.sqrt((1 - tgt) / 2 * tot / np.maximum(ps, 1e-30)), 1.0)
    # Above F_TOP both gains return to 1 over half an octave.
    fade = np.clip((np.log(F_TOP * 2 ** 0.5) - np.log(np.maximum(fr, 1.0))) / np.log(2 ** 0.5), 0.0, 1.0)
    GM = 1 + (GM - 1) * fade
    GS = 1 + (GS - 1) * fade
    M2, S2 = M * GM, S * GS
    L2 = (M2 + S2) / np.sqrt(2)
    R2 = (M2 - S2) / np.sqrt(2)
    y = np.stack([np.fft.irfft(L2, n), np.fft.irfft(R2, n)], axis=1)
    return y, fr, (L, R), (L2, R2)


def main():
    os.makedirs(ORIG, exist_ok=True)
    report = {}
    for name in NAMES:
        dst = os.path.join(AUD, name + ".wav")
        src = os.path.join(ORIG, name + ".wav")
        if not os.path.exists(src):
            shutil.copy2(dst, src)
        sr, x = load(src)
        if x.shape[1] != 2:
            print(name, "mono - skipped")
            continue
        y, fr, before, after = process(x, sr)
        peak0, peak1 = np.abs(x).max(), np.abs(y).max()
        if peak1 > peak0:          # keep the original peak (no clipping, same headroom)
            y *= peak0 / peak1
        save(dst, sr, y)
        rms0 = 10 * np.log10(np.mean(x ** 2))
        rms1 = 10 * np.log10(np.mean(y ** 2))
        cb = [round(band_coh(before, fr, a, b), 2) for a, b in zip(EDGES, EDGES[1:])]
        ca = [round(band_coh(after, fr, a, b), 2) for a, b in zip(EDGES, EDGES[1:])]
        report[name] = {"rms_before": round(rms0, 2), "rms_after": round(rms1, 2),
                        "peak_before": round(20 * np.log10(peak0), 2), "peak_after": round(20 * np.log10(np.abs(y).max()), 2),
                        "coh_before": cb, "coh_after": ca}
        print(f"{name:22s} rms {rms0:6.2f} -> {rms1:6.2f} dB   coherence 20-60..2k-4k  {cb}  ->  {ca}")
    json.dump({"bands_hz": list(zip(EDGES, EDGES[1:])), "files": report}, open(os.path.join(STG, "metrics.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
