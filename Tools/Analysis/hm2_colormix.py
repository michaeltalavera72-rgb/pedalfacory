"""
HM-2 "COLOR MIX" (op-amp 3a) nodal analysis -> peaking-filter fit used by Source/Pedals/Buzzsaw.h.

Topology (Boss service notes, Dec 1983): input R54 3.3k into the + node; feedback R52 3.3k || C33 470p
from the output to the - node; VR2 (LOW) and VR3 (HIGH) 10k pots bridge the - and + nodes; each wiper
drives series resonators to the 4.5 V bias (AC ground). Each resonator is a series cap + gyrator
inductor: L = R(330) * R(82k/100k) * C, in series with 330 R.
    LOW : C35 1.5u + (R47 330, R51 100k, C30 0.068u)  -> 87 Hz
    HIGH: C28 0.15u + (R41 330, R43 82k, C27 0.0068u) -> 958 Hz
          C29 0.1u  + (R45 330, R44 100k, C26 0.0047u) -> 1.28 kHz
Result: LOW +20.1 dB @ 86 Hz, HIGH +22.2/+22.6 dB @ 958/1291 Hz, flat at centre (spec: 90 Hz, 950 Hz,
1.3 kHz, +21 dB). Run with numpy + scipy; prints the C++ tables.
"""
import numpy as np
from scipy.optimize import least_squares

R54, R52, C33, P = 3.3e3, 3.3e3, 470e-12, 10e3
def resonator(s, Cs, R1, R2, Cg): return 1/(s*Cs) + R1 + s*R1*R2*Cg

def response(f, kL, kH):
    s = 2j*np.pi*f
    ZL = resonator(s, 1.5e-6, 330, 100e3, 0.068e-6)
    ZH = 1/(1/resonator(s, 0.15e-6, 330, 82e3, 0.0068e-6) + 1/resonator(s, 0.1e-6, 330, 100e3, 0.0047e-6))
    Zf = 1/(1/R52 + s*C33); out = []
    for i in range(len(f)):
        a = max(1e-3, (1-kL)*P); b = max(1e-3, kL*P); c = max(1e-3, (1-kH)*P); d = max(1e-3, kH*P)
        A = np.zeros((4, 4), complex); B = np.zeros(4, complex)      # x = [v(-)=v(+), wiperL, wiperH, out]
        A[0] = [-1/Zf[i]-1/a-1/c, 1/a, 1/c, 1/Zf[i]]                  # - node
        A[1] = [-1/R54-1/b-1/d, 1/b, 1/d, 0]; B[1] = -1/R54           # + node
        A[2] = [1/a+1/b, -1/a-1/b-1/ZL[i], 0, 0]
        A[3] = [1/c+1/d, 0, -1/c-1/d-1/ZH[i], 0]
        out.append(np.linalg.solve(A, B)[3])
    return np.array(out)

fs = 48000
def pk(f, f0, gdb, Q):
    A = 10**(gdb/40); w0 = 2*np.pi*f0/fs; al = np.sin(w0)/(2*Q)
    b = np.array([1+al*A, -2*np.cos(w0), 1-al*A]); a = np.array([1+al/A, -2*np.cos(w0), 1-al/A])
    z = np.exp(-1j*2*np.pi*f/fs)
    return 20*np.log10(np.abs((b[0]+b[1]*z+b[2]*z*z)/(a[0]+a[1]*z+a[2]*z*z)))

if __name__ == "__main__":
    f = np.logspace(np.log10(20), np.log10(16000), 500)
    rows = []
    for k in np.linspace(0.5, 1, 11):
        rL = 20*np.log10(np.abs(response(f, k, .5))); rH = 20*np.log10(np.abs(response(f, .5, k)))
        sL = least_squares(lambda p: pk(f, p[0], p[1], p[2]) - rL, [80, max(rL.max(), .01), .8], bounds=([40, -30, .1], [200, 30, 5]))
        sH = least_squares(lambda p: pk(f, 958, p[0], p[1]) + pk(f, 1278, p[0], p[1]) - rH, [max(rH.max()/2, .01), 1], bounds=([-30, .1], [30, 8]))
        rows.append([*sL.x, *sH.x]); print(f"k={k:.2f}  L f0 {sL.x[0]:.1f} g {sL.x[1]:.2f} Q {sL.x[2]:.2f}  H g {sH.x[0]:.2f} Q {sH.x[1]:.2f}")
