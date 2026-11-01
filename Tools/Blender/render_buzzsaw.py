"""
Buzzsaw - photoreal Blender render (original design for the Virtual Pedalboard).
Blood-red textured powder coat, bone-white lettering, circular saw-blade emblem,
four black knobs with satin aluminium caps (Level, Low, High, Dist), red LED, chrome footswitch.
Uses pedal_render_common.py (same folder).

Writes Assets/Buzzsaw/: buzzsaw_face.png, buzzsaw_knob_strip.png (8-column grid),
buzzsaw_switch_up/down.png, buzzsaw_led_on/off.png, and saves Tools/Blender/buzzsaw.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_buzzsaw.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (4-knob row). Pads MUST match RenderedFace (PedalFaces.cpp).
"""
import bpy, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib, pedal_render_common as C
importlib.reload(C)

ST = C.Settings(sys.argv)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "Buzzsaw")
TMP = os.path.join(HERE, "_frames_buzzsaw")
FONT_NAME = os.path.join(ROOT, "Assets", "MetalMania-Regular.ttf")
FONT_LABEL_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

W, H = 91.0, 120.0
UI_BODY_PX = 226.0
PX_PER_MM = UI_BODY_PX / W * ST.oversample
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6

POWDER_RED = (0.15, 0.004, 0.005, 1)       # deep blood red (AgX + sheen lift it a lot)
BONE = (0.78, 0.66, 0.44, 1)                  # warmer, aged bone
INK_BLACK = (0.010, 0.010, 0.011, 1)
# Exposure is calibrated on a brushed-steel reference plate (not on the red face), with the same
# target the Ramhorn's steel face produced, so every pedal sits in the same lighting/brightness.
STEEL_REFERENCE_TARGET = 0.74

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, 4 knobs)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.19
KNOB_TOP = 0.055
KNOB_CX = [0.15 + 0.70 * i / 3 for i in range(4)]
KNOB_CY_FRAC = KNOB_TOP + (KNOB_D / H) * 0.5
LABEL_CY_FRAC = KNOB_TOP + (KNOB_D / H) + 9.5 / 298.0
NAME = (0.06, 0.355, 0.88, 0.135)
SUB = (0.06, 0.49, 0.88, 0.065)
EMBLEM = (0.26, 0.565, 0.48, 0.135)
SW_D = W * 0.19
SW_CY_FRAC = 0.865
LED_D = 11.0 / UI_BODY_PX * W
LED_CY_FRAC = 0.74
def rect_center(r): return fx(r[0] + r[2] / 2), fy(r[1] + r[3] / 2)

def saw_outline(R, teeth=18):
    pts = []
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        a1 = a0 + 2 * math.pi * 0.62 / teeth
        for a, r in ((a0, R * 0.80), (a1, R)):
            pts.append((math.cos(a) * r, -math.sin(a) * r))     # y flipped: matches the plugin's vector emblem
    return pts

# ----------------------------------------------------------------------------- build
def build(scene):
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(0.5), fy(SW_CY_FRAC)
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    powder = C.mat_powder_coat("PowderRed", POWDER_RED, body, scuff_center=(sx, sy))
    body.data.materials.append(powder)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)       # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.62, 0.63, 0.65, 1), 0.26, smudges=0.1)
    screw_metal = C.mat_metal("ScrewMetal", (0.80, 0.80, 0.82, 1), 0.22, smudges=0.05)
    bone = C.mat_ink("InkBone", BONE, body)
    black_ink = C.mat_ink("InkBlack", INK_BLACK, body, chip_amount=0.0)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.008, 0.008, 0.009, 1), rough=0.58, spec=0.18, smudges=0.06)
    knob_cap = C.mat_metal("KnobCapAlu", (0.55, 0.55, 0.57, 1), 0.34, smudges=0.06)
    pointer = C.mat_simple("PointerBlack", (0.01, 0.01, 0.01, 1), rough=0.5, spec=0.2)

    inset = 9.0 / UI_BODY_PX * W
    for i, (ax, ay) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        C.phillips_screw(f"Screw{i}", ax * (W / 2 - inset), ay * (H / 2 - inset), 1.7,
                         [0.3, 1.1, 0.8, 0.1][i], screw_metal, face, colls["Cutters"])

    name_font = bpy.data.fonts.load(FONT_NAME) if os.path.exists(FONT_NAME) else None
    label_font = next((bpy.data.fonts.load(p) for p in FONT_LABEL_CANDIDATES if os.path.exists(p)), None)
    ncx, ncy = rect_center(NAME)
    nw, nh = NAME[2] * W * 0.85, NAME[3] * H * 1.0
    C.text_obj("NameShadow", "BUZZSAW", name_font, black_ink, (ncx + 0.6, ncy - 0.6, nw, nh), face, z=0.0)
    C.text_obj("Name", "BUZZSAW", name_font, bone, (ncx, ncy, nw, nh), face, z=0.02)
    scx, scy = rect_center(SUB)
    C.text_obj("Sub", "DISTORTION", label_font, bone, (scx, scy, SUB[2] * W * 0.62, SUB[3] * H * 0.62), face, spacing=1.6)
    for i, (label, cxf) in enumerate(zip(["LEVEL", "LOW", "HIGH", "DIST"], KNOB_CX)):
        C.text_obj(f"Label{i}", label, label_font, bone,
                   (fx(cxf), fy(LABEL_CY_FRAC), KNOB_D * 1.15, 13.0 / 298.0 * H * 0.7), face, spacing=1.05)

    # saw-blade emblem (+ black drop shadow) and a red "hole" in the middle
    ecx, ecy = rect_center(EMBLEM)
    R = EMBLEM[3] * H * 0.5
    for layer, mat, dz, off in [("Shadow", black_ink, 0.0, (0.5, -0.5)), ("Ink", bone, 0.02, (0, 0))]:
        o = C.flat_shape(f"Blade{layer}", saw_outline(R), mat)
        o.location = (ecx + off[0], ecy + off[1], dz); face.objects.link(o)
    hole = C.cylinder("BladeHole", R * 0.22, 0.03, z0=0.03, verts=64, mat=powder)
    hole.location = (ecx, ecy, 0); face.objects.link(hole)

    lx, ly = fx(0.5), fy(LED_CY_FRAC)
    bez = C.cylinder("LedBezel", LED_D * 0.5 + 1.2, 1.2, mat=chrome); C.bevel(bez, 0.4, 3)
    bez.location = (lx, ly, 0); face.objects.link(bez)
    for key, on in (("LedOn", True), ("LedOff", False)):
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, C.mat_led(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    kx, ky = fx(KNOB_CX[0]), fy(KNOB_CY_FRAC)
    pivot = C.knurled_knob("Knob", KNOB_D * 0.5, 11.0, (knob_skirt, knob_cap, pointer), colls["Knob"])
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
                       body=body, powder=powder, steel_ref=steel_ref)

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
        """Bare enclosure in brushed steel: same exposure basis as the Ramhorn."""
        body = P["body"]
        body.data.materials[0] = P["steel_ref"]
        hidden = [o for o in face_objs if o is not body]
        for o in hidden: o.hide_render = True
        try: render_face(path)
        finally:
            for o in hidden: o.hide_render = False
            body.data.materials[0] = P["powder"]

    C.auto_exposure(scene, render_reference, STEEL_REFERENCE_TARGET, os.path.join(TMP, "exposure_probe.png"))

    render_face(os.path.join(OUT, "buzzsaw_face.png"))

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
    C.stack_grid(paths, os.path.join(OUT, "buzzsaw_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "buzzsaw_switch_up.png"), ("SwitchDown", "buzzsaw_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "buzzsaw_led_on.png"), ("LedOff", "buzzsaw_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "buzzsaw_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    for c in groups: c.hide_render = c in (colls["SwitchDown"], colls["LedOff"])
    for c in (colls["SwitchDown"], colls["LedOff"]): c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "buzzsaw.blend"))
    print("[pedal] done")

main()
