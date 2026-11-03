"""Small-signal frequency response of the real Soldano SLO pedal (traced circuit, op-amps ideal and unclipped),
used to check that Slow Burn's valve stages keep the pedal's voicing. Usage:
    python slo_reference_response.py [gain bass mid treble presence deep]   (pot positions 0..1, deep 0/1)
Prints dB at a list of frequencies, normalised to 1 kHz."""
import sys
import numpy as np

def audio(x): return (10 ** (2 * x) - 1) / 99

def solve(elems, n, f, src=1.0, opamps=()):
    """Tiny AC MNA. elems: (a, b, Z-function). node 1 = ideal source. opamps: (p, n, out)."""
    s = 2j * np.pi * f
    N = n + 1 + len(opamps)
    A = np.zeros((N, N), complex); b = np.zeros(N, complex)
    for a, c, z in elems:
        y = 1 / z(s)
        for i, j, v in ((a, a, y), (c, c, y), (a, c, -y), (c, a, -y)):
            if i > 0 and j > 0: A[i - 1, j - 1] += v
    A[0, n] += 1; A[n, 0] += 1; b[n] = src
    for k, (p, m, o) in enumerate(opamps):
        r = n + 1 + k
        A[o - 1, r] += 1
        if p > 0: A[r, p - 1] += 1
        if m > 0: A[r, m - 1] -= 1
    x = np.linalg.solve(A, b)
    return np.concatenate([[0], x[:n]])

R = lambda v: (lambda s: v)
C = lambda v: (lambda s: 1 / (s * v))

def response(f, g=0.5, bass=0.5, mid=0.5, treble=0.5, pres=0.5, deep=0):
    ga = audio(g)
    # interstage: 1 src, 2 Y, 3 lug3, 4 wiper, 5 lug1
    v = solve([(1, 2, C(1e-9)), (2, 3, R(470e3)), (2, 3, C(2.2e-9)), (3, 4, R(500e3 * (1 - ga) + 100)),
               (3, 4, C(1e-9)), (4, 5, R(500e3 * ga + 100)), (5, 0, R(4.7e3))], 5, f)
    s = 2j * np.pi * f
    zf = lambda Rf, Cf: Rf / (1 + s * Rf * Cf)
    h = v[4]
    h *= 1 + zf(1e6, 100e-12) / (6.8e3 + 1 / (s * 1e-6))                  # IC2A
    h *= (330e3 / (330e3 + 1 / (s * 22e-9)))                               # 22n / 330k (220k into op-amp)
    h *= 1 + zf(470e3, 100e-12) / (10e3 + 1 / (s * 1e-6))                  # IC3A
    t = treble
    st = solve([(1, 2, C(470e-12)), (2, 3, R(250e3 * (1 - t) + 50)), (3, 4, R(250e3 * t + 50)), (1, 5, R(47e3)),
                (5, 4, C(22e-9)), (5, 6, C(22e-9)), (4, 7, R(1e6 * audio(bass) + 50)), (7, 6, R(25e3 * (1 - mid) + 10)),
                (6, 0, R(25e3 * mid + 10)), (1, 8, C(1e-9)), (8, 3, R(10e3)), (3, 9, R(1e6)), (9, 0, R(33e3))], 9, f)
    h *= st[9]
    els = [(3, 4, R(33e3)), (3, 4, C(22e-9)), (4, 2, R(10e3)), (2, 0, R(4.7e3)), (2, 5, C(100e-9)),
           (5, 6, R(25e3 * audio(1 - pres) + 50)), (6, 0, R(1e3)), (6, 7, C(44e-9)), (7, 0, R(220))]
    if not deep: els.append((3, 4, R(22e3)))
    pw = solve(els, 7, f, opamps=[(1, 2, 3)])
    h *= pw[3]
    o = solve([(1, 2, C(1e-6)), (2, 3, R(10e3)), (3, 4, C(22e-9)), (4, 0, R(1e3)), (3, 0, R(25e3))], 4, f)
    return h * o[3]

FREQS = [50, 80, 100, 150, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 4000, 6000, 8000, 12000]
if __name__ == "__main__":
    a = [float(x) for x in sys.argv[1:]]
    keys = ["g", "bass", "mid", "treble", "pres", "deep"]
    kw = dict(zip(keys, a))
    ref = abs(response(1000, **kw))
    print(f"absolute gain at 1 kHz (vol fully up): {20*np.log10(ref):.1f} dB")
    for fr in FREQS:
        print(f"{fr:6d} Hz {20*np.log10(abs(response(fr, **kw))/ref):7.2f} dB")
