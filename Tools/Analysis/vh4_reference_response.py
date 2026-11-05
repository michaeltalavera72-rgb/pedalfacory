"""Small-signal frequency response of the Diezel VH4 pedal (schematics/Diezel/Diezel-VH4-Pedal.pdf, EAGLE trace
2017), op-amps ideal and unclipped, clipping diodes off. Used to check Thunderhead's linear voicing.

Pots are off-sheet in the trace; values from the PedalPCB "Valhalla" clone parts list: GAIN A250k (rheostat to
ground at IC2A "+"), TREBLE B250k, BASS A1M, MIDDLE B25k (Marshall-style stack), VOLUME A10k, PRESENCE C25k,
DEEP C25k (rheostats, CW = 0 ohm).

Usage:
    python vh4_reference_response.py [gain bass mid treble pres deep vol amp]   (pots 0..1, amp 1 = AMP out, 0 = DIRECT)
Prints the absolute gain at 1 kHz and dB at a list of frequencies relative to 1 kHz."""
import sys
import numpy as np


def audio(x): return (10 ** (2 * x) - 1) / 99


def solve(elems, n, f, src=1.0, opamps=()):
    """Tiny AC MNA. elems: (a, b, Z-function). node 1 = ideal source. opamps: (p, n, out) nullors."""
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


def noninv(f, Rf, Cf, Rg, Cg):
    s = 2j * np.pi * f
    zf = Rf / (1 + s * Rf * Cf)
    return 1 + zf / (Rg + 1 / (s * Cg))


def sections(f, g=0.5, bass=0.5, mid=0.5, treble=0.5, pres=0.5, deep=0.5, vol=1.0, amp=1):
    """Returns the transfer of each block (for comparing with the C++ blocks one by one)."""
    out = {}
    # input: 22n into 1M || 1M || 100p, then the IC1A follower, 1u / 100k into IC1B "+"
    v = solve([(1, 2, C(22e-9)), (2, 0, R(1e6)), (2, 0, R(1e6)), (2, 0, C(100e-12))], 2, f)
    s = 2j * np.pi * f
    out["input"] = v[2] * (100e3 / (100e3 + 1 / (s * 1e-6)))
    out["ic1b"] = noninv(f, 220e3, 100e-12, 10e3, 1e-6)
    # interstage: 1 = IC1B out, 2 = C7/R8 node, 3 = R10 node, 4 = IC2A "+"
    rg = 250e3 * audio(g) + 50
    v = solve([(1, 2, C(22e-9)), (2, 0, R(470e3)), (2, 3, C(2.2e-9)), (2, 3, R(680e3)), (3, 0, R(220e3)),
               (3, 4, R(220e3)), (4, 0, R(rg))], 4, f)
    out["inter"] = v[4]
    out["ic2a"] = noninv(f, 1e6, 47e-12, 10e3, 2.2e-6)
    # C11 4n7 -> R15 100k (diodes off) -> R16 470k to ground (R17 into IC2B "+" = open)
    v = solve([(1, 2, C(4.7e-9)), (2, 3, R(100e3)), (3, 0, R(470e3))], 3, f)
    out["diodes"] = v[3]
    out["ic2b"] = noninv(f, 220e3, 100e-12, 10e3, 2.2e-6)
    # tone stack: 1 = IC2B out, 2 = treble lug 3, 3 = treble wiper, 4 = treble lug 1 / bass top (BASS3),
    # 5 = slope node, 6 = MID3 (bass bottom / mid top), 7 = IC3A "+"
    t = treble
    v = solve([(1, 2, C(560e-12)), (2, 3, R(250e3 * (1 - t) + 50)), (3, 4, R(250e3 * t + 50)),
               (1, 5, R(39e3)), (5, 4, C(22e-9)), (5, 6, C(22e-9)),
               (4, 6, R(1e6 * audio(bass) + 50)), (6, 0, R(25e3 * mid + 10)),
               (3, 7, R(1.5e6)), (7, 0, R(100e3))], 7, f)
    out["stack"] = v[7]
    # IC3A: 1 = "+", 2 = "-", 3 = out, 4 = R32/C20, 5 = C18/R28, 6 = R28/deep pot, 7 = DEEP1 (gyrator),
    # 8 = IC3B out, 9 = IC3B "+", 10 = C17/R26, 11 = R26/presence pot
    rdeep = 25e3 * audio(1 - deep) + 50
    rpres = 25e3 * audio(1 - pres) + 50
    v = solve([(2, 3, R(10e3)), (2, 3, C(1e-9)), (2, 4, R(4.7e3)), (4, 0, C(10e-6)),
               (2, 5, C(2.2e-6)), (5, 6, R(1e3)), (6, 7, R(rdeep)),
               (7, 8, R(47)), (7, 9, C(330e-9)), (9, 0, R(56e3)),
               (2, 10, C(1e-6)), (10, 11, R(110)), (11, 0, R(rpres))], 11, f, opamps=[(1, 2, 3), (9, 8, 8)])
    out["ic3a"] = v[3]
    # output: 1 = IC3A out, 2 = C22/R34, 3 = vol lug 3, 4 = wiper, 5 = OUT
    va = 10e3 * audio(vol)
    v = solve([(1, 2, C(10e-6)), (2, 3, R(1e3)), (3, 4, R(10e3 - va + 1)), (4, 0, R(va + 1)),
               (4, 5, R(150e3)), (5, 0, R(100e3)), (5, 0, C(2.2e-9))], 5, f)
    out["output"] = v[5] if amp else v[4]
    return out


def response(f, **kw):
    h = 1.0
    for v in sections(f, **kw).values(): h = h * v
    return h


FREQS = [30, 50, 80, 100, 115, 150, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 4000, 6000, 8000, 12000]
if __name__ == "__main__":
    a = [float(x) for x in sys.argv[1:]]
    keys = ["g", "bass", "mid", "treble", "pres", "deep", "vol", "amp"]
    kw = dict(zip(keys, a))
    ref = abs(response(1000, **kw))
    print(f"absolute small-signal gain at 1 kHz: {20*np.log10(ref):.1f} dB")
    for fr in FREQS:
        print(f"{fr:6d} Hz {20*np.log10(abs(response(fr, **kw))/ref):7.2f} dB")
    print("per block at 1 kHz:", {k: round(20*np.log10(abs(v)), 1) for k, v in sections(1000, **kw).items()})
