"""
Coral Tide reference: exact small-signal AC nodal analysis of the two Bearfoot / BJFE circuits it models
(schematics "Bearfoot _ BJFE - Sea Blue Q.pdf" and "Bearfoot _ BJFE - Baby Pink Boost.pdf").
JFETs = transconductance gm (0.6 mS, the value the model's Idss / Vp were fitted to at the traced bias points).

    python Tools/Analysis/bjfe_dual.py

Prints gain in dB at 30 ... 10k Hz for the Sea Blue EQ (VOLUME full, TREBLE / BASS combinations; the source
Coral Tide's EQ section is compared against) and for the Baby Pink boost (BOOST 0..1 with a reverse-log "C" taper,
and switched off = buffer). Source/Pedals/CoralTide.h must match these within ~0.5 dB.
"""
import numpy as np

GM = 0.6e-3
FREQS = [30, 60, 100, 200, 400, 800, 1600, 3200, 6400, 10000]
POT = 50e3


def a_taper(p, b=81.0):
    """'A' (log) pot: fraction of the resistance between lug 1 and the wiper; 10 % at noon."""
    return (b ** p - 1.0) / (b - 1.0)


def solve(els, n, f, inp=1):
    """Nodal analysis. els: ('R', a, b, ohms) | ('C', a, b, farads) | ('G', d, s, g, s, gm) (JFET drain d, source s,
    gate g: current gm * (vg - vs) flows from d to s). Node 0 = ground; node `inp` driven by a 1 V source."""
    s = 2j * np.pi * f
    Y = np.zeros((n + 1, n + 1), complex)

    def add(a, b, y):
        Y[a, a] += y; Y[b, b] += y; Y[a, b] -= y; Y[b, a] -= y

    for e in els:
        if e[0] == 'R':
            add(e[1], e[2], 1.0 / e[3])
        elif e[0] == 'C':
            add(e[1], e[2], s * e[3])
        else:
            _, d, src, g, s2, gm = e
            Y[d, g] += gm; Y[d, s2] -= gm; Y[src, g] -= gm; Y[src, s2] += gm
    big = 1e3
    Y[inp, inp] += big
    I = np.zeros(n + 1, complex); I[inp] = big
    v = np.linalg.solve(Y[1:, 1:], I[1:])
    return np.concatenate([[0], v])


def sea_blue(treble, bass):
    """Nodes: 1 in, 2 R10/C7, 3 gate1, 4 drain1, 5 source1, 6 C6/R8, 7 A, 8 TREBLE lug3, 9 TREBLE lug1,
    10 output node (TREBLE wiper = Q2 gate), 11 BASS lug3, 12 BASS wiper, 13 BASS lug1, 14 drain2, 15 source2, 16 VOLUME top."""
    tr = treble * POT
    lower = a_taper(bass) * POT
    m = lambda r: max(r, 1.0)
    return [('R', 1, 0, 1e6), ('R', 1, 2, 14.7e3), ('C', 2, 3, 22e-9), ('R', 3, 0, 1e6),
            ('R', 4, 0, 14.7e3), ('C', 4, 0, 1e-9), ('R', 5, 0, 14.7e3), ('C', 5, 6, 22e-6), ('R', 6, 0, 1e3),
            ('G', 4, 5, 3, 5, GM),
            ('C', 4, 7, 470e-9), ('C', 7, 8, 4.7e-9), ('R', 7, 8, 47e3),
            ('R', 8, 10, m(POT - tr)), ('R', 10, 9, m(tr)), ('C', 9, 0, 22e-9),
            ('R', 7, 11, 5.6e3), ('R', 11, 12, m(POT - lower)), ('C', 11, 12, 22e-9),
            ('R', 12, 13, m(lower)), ('C', 12, 13, 220e-9), ('R', 13, 0, 1e3),
            ('R', 12, 10, 5.6e3), ('R', 10, 0, 1e6),
            ('R', 14, 0, 14.7e3), ('C', 14, 0, 1e-9), ('R', 15, 0, 14.7e3), ('C', 15, 0, 1e-6), ('G', 14, 15, 10, 15, GM),
            ('C', 14, 16, 1e-6), ('R', 16, 0, POT)], 16, 16


def baby_pink(boost, engaged=True):
    """Nodes: 1 in, 2 C1/R2, 3 gate, 4 drain, 5 source, 6 C4/R6, 7 BOOST lug3, 8 out."""
    rsec = max(a_taper(1.0 - boost) * POT, 1.0)              # 'C' (reverse log): clockwise = less resistance
    els = [('R', 1, 0, 2e6), ('C', 1, 2, 47e-9), ('R', 2, 3, 14.7e3), ('R', 3, 0, 2e6),
           ('R', 4, 0, 14.7e3), ('C', 4, 5, 100e-12), ('R', 5, 0, 12e3), ('G', 4, 5, 3, 5, GM),
           ('C', 5, 6, 22e-6), ('R', 6, 7, 1e3), ('R', 7, 0, rsec if engaged else POT + 150e3),
           ('C', 4, 8, 1e-6), ('R', 8, 0, 150e3)]
    return els, 8, 8


def row(spec):
    els, n, out = spec
    return [20 * np.log10(abs(solve(els, n, f)[out])) for f in FREQS]


if __name__ == '__main__':
    print('Hz            ' + ''.join('%7d' % f for f in FREQS))
    for t, b in [(0.5, 0.5), (0, 0.5), (1, 0.5), (0.5, 0), (0.5, 1), (0, 0), (1, 1)]:
        print('EQ  T%.1f B%.1f ' % (t, b) + ''.join('%7.1f' % x for x in row(sea_blue(t, b))))
    for bo in [0, 0.25, 0.5, 0.75, 1.0]:
        print('BOOST %.2f    ' % bo + ''.join('%7.1f' % x for x in row(baby_pink(bo))))
    print('BOOST off     ' + ''.join('%7.1f' % x for x in row(baby_pink(0, False))))
