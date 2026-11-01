"""
Rail Bender - photoreal Blender render (original design for the Virtual Pedalboard).
Burnt-orange enamel with a rust patina, black "RAIL BENDER" in Rye, bent-railway-track emblem,
four black knurled knobs (Drive, Tone, Level, Boost), two LEDs + two chrome footswitches (Drive / Boost).
Uses pedal_render_common.py (same folder).

Writes Assets/RailBender/: railbender_face.png, railbender_knob_strip.png (8-column grid),
railbender_switch_up/down.png, railbender_led_on/off.png (shared by both switches / LEDs),
and saves Tools/Blender/railbender.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_railbender.py
Options after "--":   --quick   |   --hdri=NAME.exr   |   --rust=blooms (default) or --rust=streaks
    The renders go to Assets/RailBender (what the app builds with) AND are copied to
    Assets/_Compare/RailBender_<rust style>/ so both looks can be kept and swapped in later.

Positions MUST match Source/UI/FaceLayout.h (4 knobs, 2 footswitches). Pads MUST match RenderedFace.
"""
import bpy, math, os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib, pedal_render_common as C
importlib.reload(C)

ST = C.Settings(sys.argv)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "RailBender")
TMP = os.path.join(HERE, "_frames_railbender")
_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
RUST_STYLE = next((a.split("=", 1)[1] for a in _args if a.startswith("--rust=")), "blooms")
assert RUST_STYLE in ("blooms", "streaks"), "--rust must be blooms or streaks"
COMPARE = os.path.join(ROOT, "Assets", "_Compare", "RailBender_" + RUST_STYLE)
FONT_NAME = os.path.join(ROOT, "Assets", "Rye-Regular.ttf")
FONT_LABEL_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

W, H = 91.0, 120.0
UI_BODY_PX = 226.0
MM_PER_PX = W / UI_BODY_PX
PX_PER_MM = UI_BODY_PX / W * ST.oversample
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6

# Albedos chosen darker/more saturated than the target look (AgX + sheen lift paint a lot)
BURNT_ORANGE = (0.34, 0.068, 0.006, 1)   # AgX lifts and desaturates: keep it deep and saturated
INK_BLACK = (0.010, 0.009, 0.008, 1)
STEEL_REFERENCE_TARGET = 0.74          # same exposure basis as the other pedals

# ----------------------------------------------------------------------------- layout (= FaceLayout.h)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.19
KNOB_TOP = 0.055
KNOB_CX = [0.15 + 0.70 * i / 3 for i in range(4)]
KNOB_CY_FRAC = KNOB_TOP + (KNOB_D / H) * 0.5
LABEL_CY_FRAC = KNOB_TOP + (KNOB_D / H) + 9.5 / 298.0
NAME = (0.06, 0.355, 0.88, 0.135)
SUB = (0.06, 0.49, 0.88, 0.065)
EMBLEM = (0.38, 0.57, 0.24, 0.12)                      # two-switch layout: narrower emblem
SW_D = W * 0.19
SW_CX = [0.29, 0.71]
SW_CY_FRAC = 0.865
LED_D = 11.0 / UI_BODY_PX * W
LED_CY_FRAC = 0.745
SWITCH_LABEL_CY_FRAC = 0.675 + 0.02
def rect_center(r): return fx(r[0] + r[2] / 2), fy(r[1] + r[3] / 2)

def arc_band(cx, cy, r_in, r_out, a0, a1, n=48):
    """Annular sector (angles from vertical, clockwise) as a 2D outline in Blender coords (y up)."""
    outer = [(cx + math.sin(a0 + (a1 - a0) * i / n) * r_out, cy + math.cos(a0 + (a1 - a0) * i / n) * r_out) for i in range(n + 1)]
    inner = [(cx + math.sin(a0 + (a1 - a0) * i / n) * r_in, cy + math.cos(a0 + (a1 - a0) * i / n) * r_in) for i in range(n + 1)]
    return outer + list(reversed(inner))

def bent_rail_shapes():
    """Same geometry as drawBentRail() in PedalFaces.cpp, converted to mm and y-up."""
    ex0, ey0, ew, eh = EMBLEM[0] * W, EMBLEM[1] * H, EMBLEM[2] * W, EMBLEM[3] * H   # top-left based, mm
    R = ew * 1.05
    gauge = eh * 0.30
    cx = fx(EMBLEM[0] + EMBLEM[2] / 2)
    cy = fy(EMBLEM[1] + EMBLEM[3]) - R * 0.62           # centre below the emblem
    a0, a1 = -0.48, 0.48
    rail_w = 2.6 * MM_PER_PX
    shapes = []
    for r in (R, R - gauge):
        shapes.append(("rail", arc_band(cx, cy, r - rail_w / 2, r + rail_w / 2, a0, a1)))
    sl_w = 3.0 * MM_PER_PX
    for i in range(9):
        a = a0 + (a1 - a0) * i / 8
        r1, r2 = R - gauge * 1.35, R + gauge * 0.35
        dx, dy = math.sin(a), math.cos(a)
        px, py = math.cos(a), -math.sin(a)             # perpendicular
        h = sl_w / 2
        p1 = (cx + dx * r1, cy + dy * r1); p2 = (cx + dx * r2, cy + dy * r2)
        shapes.append(("sleeper", [(p1[0] + px * h, p1[1] + py * h), (p2[0] + px * h, p2[1] + py * h),
                                   (p2[0] - px * h, p2[1] - py * h), (p1[0] - px * h, p1[1] - py * h)]))
    return shapes

# ----------------------------------------------------------------------------- build
def build(scene):
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    switches = [(fx(cx), fy(SW_CY_FRAC)) for cx in SW_CX]
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    # keep the rust off the area behind "RAIL BENDER" so the name stays readable
    name_zone = (fx(0.5), fy(0.4225), W * 0.40, H * 0.055)
    paint = C.mat_rusty_paint("RustyOrange", BURNT_ORANGE, body, scuff_centers=switches,
                              style=RUST_STYLE, clear_zones=[name_zone])
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.62, 0.63, 0.65, 1), 0.26, smudges=0.1)
    screw_metal = C.mat_metal("ScrewMetal", (0.70, 0.68, 0.64, 1), 0.30, smudges=0.08)   # slightly aged
    ink = C.mat_ink("InkBlack", INK_BLACK, body, chip_amount=0.6)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.008, 0.008, 0.009, 1), rough=0.58, spec=0.18, smudges=0.06)
    knob_cap = C.mat_plastic("KnobCap", (0.008, 0.008, 0.009, 1), rough=0.38, spec=0.25, coat=0.15, smudges=0.08)
    pointer = C.mat_simple("PointerCream", (0.80, 0.74, 0.60, 1), rough=0.45)

    inset = 9.0 / UI_BODY_PX * W
    for i, (ax, ay) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        C.phillips_screw(f"Screw{i}", ax * (W / 2 - inset), ay * (H / 2 - inset), 1.7,
                         [0.3, 1.1, 0.8, 0.1][i], screw_metal, face, colls["Cutters"])

    name_font = bpy.data.fonts.load(FONT_NAME) if os.path.exists(FONT_NAME) else None
    label_font = next((bpy.data.fonts.load(p) for p in FONT_LABEL_CANDIDATES if os.path.exists(p)), None)
    ncx, ncy = rect_center(NAME)
    C.text_obj("Name", "RAIL BENDER", name_font, ink, (ncx, ncy, NAME[2] * W * 0.86, NAME[3] * H * 0.72), face)
    scx, scy = rect_center(SUB)
    C.text_obj("Sub", "OVERDRIVE", label_font, ink, (scx, scy, SUB[2] * W * 0.62, SUB[3] * H * 0.62), face, spacing=1.6)
    for i, (label, cxf) in enumerate(zip(["DRIVE", "TONE", "LEVEL", "BOOST"], KNOB_CX)):
        C.text_obj(f"Label{i}", label, label_font, ink,
                   (fx(cxf), fy(LABEL_CY_FRAC), KNOB_D * 1.15, 13.0 / 298.0 * H * 0.7), face, spacing=1.05)
    for i, (label, cxf) in enumerate(zip(["DRIVE", "BOOST"], SW_CX)):
        C.text_obj(f"SwitchLabel{i}", label, label_font, ink,
                   (fx(cxf), fy(SWITCH_LABEL_CY_FRAC), W * 0.15, H * 0.04 * 0.7), face, spacing=1.05)
    for i, (kind, pts) in enumerate(bent_rail_shapes()):
        o = C.flat_shape(f"Rail{kind}{i}", pts, ink); o.location = (0, 0, 0.01); face.objects.link(o)

    for i, cxf in enumerate(SW_CX):
        lx, ly = fx(cxf), fy(LED_CY_FRAC)
        bez = C.cylinder(f"LedBezel{i}", LED_D * 0.5 + 1.2, 1.2, mat=chrome); C.bevel(bez, 0.4, 3)
        bez.location = (lx, ly, 0); face.objects.link(bez)
    lx, ly = fx(SW_CX[0]), fy(LED_CY_FRAC)                   # lens rendered once, used for both LEDs
    for key, on in (("LedOn", True), ("LedOff", False)):
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, C.mat_led(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    kx, ky = fx(KNOB_CX[0]), fy(KNOB_CY_FRAC)
    pivot = C.knurled_knob("Knob", KNOB_D * 0.5, 11.0, (knob_skirt, knob_cap, pointer), colls["Knob"])
    pivot.location = (kx, ky, 0)

    sx, sy = switches[0]                                     # footswitch rendered once, used for both
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

    render_face(os.path.join(OUT, "railbender_face.png"))

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
    C.stack_grid(paths, os.path.join(OUT, "railbender_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "railbender_switch_up.png"), ("SwitchDown", "railbender_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "railbender_led_on.png"), ("LedOff", "railbender_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "railbender_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    for c in groups: c.hide_render = c in (colls["SwitchDown"], colls["LedOff"])
    for c in (colls["SwitchDown"], colls["LedOff"]): c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "railbender.blend"))
    os.makedirs(COMPARE, exist_ok=True)
    for fn in os.listdir(OUT):
        if fn.startswith("railbender_") and fn.endswith(".png"):
            shutil.copy2(os.path.join(OUT, fn), os.path.join(COMPARE, fn))
    print("[pedal] done  (rust style: %s, copy kept in %s)" % (RUST_STYLE, COMPARE))

main()
