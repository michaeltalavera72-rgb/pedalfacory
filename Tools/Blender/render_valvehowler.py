"""
Valve Howler - photoreal Blender render (original design for the Virtual Pedalboard).
Metallic jade-green flake paint under a clear coat, cream lettering ("VALVE HOWLER" in Poppins Bold
Italic), a thin cream pinstripe panel, a vacuum-tube emblem with an amber filament and "howl" waves,
three black knurled knobs (Drive, Tone, Level), one LED and one chrome footswitch.
Uses pedal_render_common.py (same folder).

Writes Assets/ValveHowler/: valvehowler_face.png, valvehowler_knob_strip.png (8-column grid),
valvehowler_switch_up/down.png, valvehowler_led_on/off.png, and saves Tools/Blender/valvehowler.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_valvehowler.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (3 knobs, 1 footswitch) and the emblem/panel geometry
in ValveHowlerFace (Source/Faces/PedalFaces.cpp). Pads MUST match RenderedFace.
"""
import bpy, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib, pedal_render_common as C
importlib.reload(C)

ST = C.Settings(sys.argv)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "ValveHowler")
TMP = os.path.join(HERE, "_frames_valvehowler")
FONT_NAME = os.path.join(ROOT, "Assets", "Poppins-BoldItalic.ttf")
FONT_LABEL_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

W, H = 91.0, 91.0 * 372.0 / 226.0          # = plugin pedal body 226 x 372 px (v28; was 120 mm / 298 px)
UI_BODY_PX = 226.0
UI_BODY_PX_H = 372.0
MM_PER_PX = W / UI_BODY_PX
PX_PER_MM = UI_BODY_PX / W * ST.oversample
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6

# Albedos chosen darker/more saturated than the target look (AgX + sheen + clear coat lift paint a lot)
JADE = (0.004, 0.095, 0.042, 1)    # metallic: base colour tints the reflections, keep it deep
CREAM_INK = (0.86, 0.64, 0.32, 1)  # AgX greys warm inks: push the saturation
AMBER_INK = (0.95, 0.36, 0.015, 1)
STEEL_REFERENCE_TARGET = 0.74          # same exposure basis as the other pedals

# ----------------------------------------------------------------------------- layout (= FaceLayout.h)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.255
KNOB_TOP = 0.055
KNOB_CX = [0.19, 0.50, 0.81]
KNOB_CY_FRAC = KNOB_TOP + (KNOB_D / H) * 0.5
LABEL_CY_FRAC = KNOB_TOP + (KNOB_D / H) + 9.5 / UI_BODY_PX_H
NAME = (0.06, 0.355, 0.88, 0.135)
SUB = (0.06, 0.49, 0.88, 0.065)
EMBLEM = (0.26, 0.565, 0.48, 0.135)
PANEL = (0.07, 0.335, 0.86, 0.612)                    # = ValveHowlerFace::panelRect (runs to the bottom edge)
SW_D = W * 0.19
SW_CY_FRAC = 0.865
LED_D = 11.0 / UI_BODY_PX * W
LED_CY_FRAC = 0.74
def rect_center(r): return fx(r[0] + r[2] / 2), fy(r[1] + r[3] / 2)

# ----------------------------------------------------------------------------- printed shapes (y up, mm)
def arc_band(cx, cy, r_in, r_out, a0, a1, n=48):
    """Annular sector (angles from vertical, clockwise) as a 2D outline in Blender coords (y up)."""
    outer = [(cx + math.sin(a0 + (a1 - a0) * i / n) * r_out, cy + math.cos(a0 + (a1 - a0) * i / n) * r_out) for i in range(n + 1)]
    inner = [(cx + math.sin(a0 + (a1 - a0) * i / n) * r_in, cy + math.cos(a0 + (a1 - a0) * i / n) * r_in) for i in range(n + 1)]
    return outer + list(reversed(inner))

def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def segment(p1, p2, w):
    """A straight stroke of width w from p1 to p2 (square ends extended by w/2, like a mitred joint)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]; L = math.hypot(dx, dy) or 1e-6
    ux, uy = dx / L, dy / L; nx, ny = -uy * w / 2, ux * w / 2
    a = (p1[0] - ux * w / 2, p1[1] - uy * w / 2); b = (p2[0] + ux * w / 2, p2[1] + uy * w / 2)
    return [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]

def rounded_ring(x0, y0, x1, y1, r, w, n=16):
    """Outline of a rounded rectangle stroked with width w, as one polygon with a slit."""
    def contour(inset):
        rr = max(0.01, r - inset); pts = []
        corners = [(x1 - r, y1 - r, 0.0), (x1 - r, y0 + r, 0.5 * math.pi), (x0 + r, y0 + r, math.pi), (x0 + r, y1 - r, 1.5 * math.pi)]
        for cx, cy, a0 in corners:                      # clockwise from the top-right corner
            for i in range(n + 1):
                a = a0 + 0.5 * math.pi * i / n
                pts.append((cx + math.sin(a) * rr, cy + math.cos(a) * rr))
        return pts
    outer, inner = contour(-w / 2), contour(w / 2)
    return outer + [outer[0]] + [inner[0]] + list(reversed(inner)) [:-1] + [inner[0]]

def valve_shapes():
    """Same geometry as drawValveEmblem() in PedalFaces.cpp (ink parts and the amber filament)."""
    h = EMBLEM[3] * H                                  # emblem height in mm
    top = fy(EMBLEM[1]); cx = fx(EMBLEM[0] + EMBLEM[2] / 2)
    gw, baseH = h * 0.50, h * 0.18
    st = max(1.2 * MM_PER_PX, h * 0.045)
    gl_bot = top - (h - baseH)
    ink, amber = [], []
    dome_c = top - gw / 2
    ink.append(arc_band(cx, dome_c, gw / 2 - st / 2, gw / 2 + st / 2, -math.pi / 2, math.pi / 2))
    ink.append(rect_pts(cx - gw / 2 - st / 2, gl_bot, cx - gw / 2 + st / 2, dome_c))
    ink.append(rect_pts(cx + gw / 2 - st / 2, gl_bot, cx + gw / 2 + st / 2, dome_c))
    ink.append(rect_pts(cx - gw * 0.42, gl_bot - baseH * 0.62, cx + gw * 0.42, gl_bot))     # base
    for i in range(3):                                                                     # pins
        px = cx - gw * 0.42 + gw * 0.84 * (0.25 + 0.25 * i)
        ink.append(rect_pts(px - st * 0.35, top - h, px + st * 0.35, gl_bot - baseH * 0.62))
    pw = st * 0.7                                                                          # plate
    glass_h = h - baseH
    px0, px1 = cx - gw * 0.24, cx + gw * 0.24
    py1 = top - gw * 0.45; py0 = py1 - glass_h * 0.48
    for a, b in (((px0, py1), (px1, py1)), ((px1, py1), (px1, py0)), ((px1, py0), (px0, py0)), ((px0, py0), (px0, py1))):
        ink.append(segment(a, b, pw))
    fy0 = py0 + (py1 - py0) * 0.15; fy1 = py1 - (py1 - py0) * 0.25                          # filament
    pts = [(cx - gw * 0.12, gl_bot + h * 0.02), (cx - gw * 0.12, fy0)]
    for i in range(4):
        pts.append((cx + (gw * 0.12 if i % 2 == 0 else -gw * 0.12), fy0 + (fy1 - fy0) * (i + 1) / 4))
    for a, b in zip(pts, pts[1:]):
        amber.append(segment(a, b, st * 0.8))
    wc = top - glass_h / 2                                                                 # howl waves
    for side in (-1, 1):
        for i in range(3):
            r = h * (0.36 + 0.16 * i) + gw / 2; w = st * (1.0 - 0.15 * i)
            mid = side * math.pi / 2
            ink.append(arc_band(cx, wc, r - w / 2, r + w / 2, mid - 0.50, mid + 0.50))
    return ink, amber

def panel_shape():
    x0, y1 = fx(PANEL[0]), fy(PANEL[1]); x1, y0 = fx(PANEL[0] + PANEL[2]), fy(PANEL[1] + PANEL[3])
    return rounded_ring(x0, y0, x1, y1, W * 0.035, 1.4 * MM_PER_PX)

# ----------------------------------------------------------------------------- build
def build(scene):
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(0.5), fy(SW_CY_FRAC)
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = C.mat_metallic_paint("JadeMetallic", JADE, body, scuff_center=(sx, sy))
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.62, 0.63, 0.65, 1), 0.26, smudges=0.1)
    screw_metal = C.mat_metal("ScrewMetal", (0.74, 0.74, 0.76, 1), 0.25, smudges=0.06)
    ink = C.mat_ink("InkCream", CREAM_INK, body, chip_amount=0.35)
    amber = C.mat_ink("InkAmber", AMBER_INK, body, chip_amount=0.2)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.008, 0.008, 0.009, 1), rough=0.58, spec=0.18, smudges=0.06)
    knob_cap = C.mat_plastic("KnobCap", (0.008, 0.008, 0.009, 1), rough=0.38, spec=0.25, coat=0.15, smudges=0.08)
    pointer = C.mat_simple("PointerCream", (0.80, 0.74, 0.60, 1), rough=0.45)

    inset = 9.0 / UI_BODY_PX * W
    for i, (ax, ay) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        C.phillips_screw(f"Screw{i}", ax * (W / 2 - inset), ay * (H / 2 - inset), 1.7,
                         [0.5, 1.3, 0.2, 0.9][i], screw_metal, face, colls["Cutters"])

    name_font = bpy.data.fonts.load(FONT_NAME) if os.path.exists(FONT_NAME) else None
    label_font = next((bpy.data.fonts.load(p) for p in FONT_LABEL_CANDIDATES if os.path.exists(p)), None)
    ncx, ncy = rect_center(NAME)
    C.text_obj("Name", "VALVE HOWLER", name_font, ink, (ncx, ncy, NAME[2] * W * 0.80, NAME[3] * H * 0.62), face)
    scx, scy = rect_center(SUB)
    C.text_obj("Sub", "OVERDRIVE", label_font, ink, (scx, scy, SUB[2] * W * 0.62, SUB[3] * H * 0.62), face, spacing=1.6)
    for i, (label, cxf) in enumerate(zip(["DRIVE", "TONE", "LEVEL"], KNOB_CX)):
        C.text_obj(f"Label{i}", label, label_font, ink,
                   (fx(cxf), fy(LABEL_CY_FRAC), KNOB_D * 1.4, 13.0 / UI_BODY_PX_H * H * 0.75), face, spacing=1.05)
    o = C.flat_shape("Panel", panel_shape(), ink); o.location = (0, 0, 0.01); face.objects.link(o)
    ink_parts, amber_parts = valve_shapes()
    for i, pts in enumerate(ink_parts):
        # each overlapping printed part gets its own tiny height: no z-fighting where strokes meet
        o = C.flat_shape(f"Valve{i}", pts, ink); o.location = (0, 0, 0.01 + 0.002 * i); face.objects.link(o)
    for i, pts in enumerate(amber_parts):
        o = C.flat_shape(f"Filament{i}", pts, amber); o.location = (0, 0, 0.08 + 0.002 * i); face.objects.link(o)

    lx, ly = fx(0.5), fy(LED_CY_FRAC)
    bez = C.cylinder("LedBezel", LED_D * 0.5 + 1.2, 1.2, mat=chrome); C.bevel(bez, 0.4, 3)
    bez.location = (lx, ly, 0); face.objects.link(bez)
    for key, on in (("LedOn", True), ("LedOff", False)):
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, C.mat_led(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    kx, ky = fx(KNOB_CX[0]), fy(KNOB_CY_FRAC)
    pivot = C.knurled_knob("Knob", KNOB_D * 0.5, 12.2, (knob_skirt, knob_cap, pointer), colls["Knob"])
    pivot.location = (kx, ky, 0)

    for key, travel in (("SwitchUp", 0.0), ("SwitchDown", -1.8)):
        c = colls[key]
        washer = C.cylinder(f"Washer{key}", SW_D * 0.56, 0.7, verts=96, mat=satin); C.bevel(washer, 0.2, 2)
        nut = C.cylinder(f"Nut{key}", SW_D * 0.5, 3.0, z0=0.7, verts=6, mat=satin); C.bevel(nut, 0.9, 3)
        nut.rotation_euler = (0, 0, math.radians(30))
        plunger = C.cylinder(f"Plunger{key}", SW_D * 0.32, 6.0 + travel, verts=96, mat=chrome)
        C.bevel(plunger, 0.8, 4); C.smooth(plunger)
        cap = C.dome(f"Dome{key}", SW_D * 0.30, 0.45, chrome); cap.location = (0, 0, 6.0 + travel)
        for o in (washer, nut, plunger, cap):
            o.location = (sx, sy, o.location.z); c.objects.link(o)

    return colls, dict(pivot=pivot, knob=(kx, ky), switch=(sx, sy), led=(lx, ly),
                       body=body, paint=paint, steel_ref=steel_ref)

# ----------------------------------------------------------------------------- render
def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    scene = C.setup_scene(ST)
    C.world_hdri(scene, ST.hdri, rotation_deg=40.0)
    C.add_key_light(scene)
    C.add_softbox(scene)
    colls, P = build(scene)
    cam = C.Camera(scene, PX_PER_MM)
    groups = [colls[k] for k in ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff")]
    face_objs = list(colls["Face"].objects)

    def render_face(path):
        C.set_catcher(face_objs, False)
        C.show_only([colls["Face"]], groups)
        cam.frame(0, 0, W, H)
        C.render_to(scene, path)

    def render_reference(path):
        body = P["body"]
        body.data.materials[0] = P["steel_ref"]
        hidden = [o for o in face_objs if o is not body]
        for o in hidden: o.hide_render = True
        try: render_face(path)
        finally:
            for o in hidden: o.hide_render = False
            body.data.materials[0] = P["paint"]

    C.auto_exposure(scene, render_reference, STEEL_REFERENCE_TARGET, os.path.join(TMP, "exposure_probe.png"))

    render_face(os.path.join(OUT, "valvehowler_face.png"))

    C.set_catcher(face_objs, True)
    C.show_only([colls["Face"], colls["Knob"]], groups)
    kx, ky = P["knob"]
    cam.frame(kx, ky, KNOB_D * KNOB_PAD, KNOB_D * KNOB_PAD)
    paths = []
    scene.cycles.samples = ST.knob_samples
    for i in range(ST.knob_frames):
        pos = i / (ST.knob_frames - 1)
        angle = math.radians(-135.0 + pos * 270.0)
        P["pivot"].rotation_euler = (0, 0, -angle)
        p = os.path.join(TMP, f"knob_{i:03d}.png"); C.render_to(scene, p); paths.append(p)
    C.stack_grid(paths, os.path.join(OUT, "valvehowler_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "valvehowler_switch_up.png"), ("SwitchDown", "valvehowler_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "valvehowler_led_on.png"), ("LedOff", "valvehowler_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "valvehowler_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    for c in groups: c.hide_render = c in (colls["SwitchDown"], colls["LedOff"])
    for c in (colls["SwitchDown"], colls["LedOff"]): c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "valvehowler.blend"))
    print("[pedal] done")

main()
