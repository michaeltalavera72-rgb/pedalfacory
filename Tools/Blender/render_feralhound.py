"""
Feral Hound - photoreal Blender render (original design for the Virtual Pedalboard).
Matte black powder coat (edge chips show bare aluminium, boot wear around the footswitch), a full-colour
UV-printed snarling hound in the lower half (Assets/feralhound_dog.png, Michael's artwork, background already
alpha), blood-red ink ("FERAL HOUND" in Black Ops One across the hound's ears over a black knock-out outline,
"DISTORTION" left of the footswitch, knob labels), six knobs in two rows (Gain/Filter/Level big,
Fat/Soft/Hard small: black knurled skirts, satin aluminium caps, red pointers), the LED right of the footswitch.
Uses pedal_render_common.py (same folder).

Writes Assets/FeralHound/: feralhound_face.png, feralhound_knob_strip.png (8-column grid),
feralhound_switch_up/down.png, feralhound_led_on/off.png, and saves Tools/Blender/feralhound.blend.
The knob strip is rendered once at the big-knob size; the plugin scales it down for the small knobs.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_feralhound.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (6 knobs = two rows of three, 1 footswitch) and
FeralHoundFace (Source/Faces/PedalFaces.cpp). Pads MUST match RenderedFace.
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "FeralHound")
TMP = os.path.join(HERE, "_frames_feralhound")
FONT_NAME = os.path.join(ROOT, "Assets", "BlackOpsOne-Regular.ttf")
DOG_IMAGE = os.path.join(ROOT, "Assets", "feralhound_dog.png")
FONT_LABEL_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

W, H = 91.0, 91.0 * 372.0 / 226.0          # = plugin pedal body 226 x 372 px (v28; was 120 mm / 298 px)
UI_BODY_PX = 226.0
UI_BODY_PX_H = 372.0
MM_PER_PX = W / UI_BODY_PX
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6

# Albedos darker/more saturated than the target look (AgX lifts and desaturates)
MATTE_BLACK = (0.007, 0.007, 0.0072, 1)     # first quick render (0.011) came out charcoal, sRGB ~31,33,36
BLOOD_INK = (0.50, 0.010, 0.014, 1)
STEEL_REFERENCE_TARGET = 0.74          # same exposure basis as the other pedals

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, 6 knobs)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D_BIG, KNOB_D_SMALL = W * 0.215, W * 0.15
KNOB_TOP = (0.045, 0.262)                               # fraction of H: top row, bottom row
KNOB_CX = [0.22, 0.50, 0.78]
KNOB_LABELS = [["GAIN", "FILTER", "LEVEL"], ["FAT", "SOFT", "HARD"]]
def knob_cy_frac(row): return KNOB_TOP[row] + ((KNOB_D_BIG, KNOB_D_SMALL)[row] / H) * 0.5
def label_cy_frac(row):  # label rect: knob bottom + 1 px, 13 px tall
    return KNOB_TOP[row] + (KNOB_D_BIG, KNOB_D_SMALL)[row] / H + 7.5 / UI_BODY_PX_H
NAME = (0.06, 0.425, 0.88, 0.10)
SUB_C = (0.205, 0.905)                                   # centre; rect 0.30 W x 0.04 H
SUB_WH = (0.30, 0.04)
DOG_C = (0.5, 0.64)                                      # centre; square, 0.66 W on a side
DOG_SIZE = W * 0.66
SW_D = W * 0.19
SW_CY_FRAC = 0.905
LED_D = 11.0 / UI_BODY_PX * W
LED_CX_FRAC, LED_CY_FRAC = 0.80, 0.905
def rect_center(r): return fx(r[0] + r[2] / 2), fy(r[1] + r[3] / 2)

# ----------------------------------------------------------------------------- printed hound (UV print)
def mat_print(name, path, ref_obj):
    """Full-colour UV print on the powder coat: the image's colour and alpha, a satin-matte ink surface
    a touch smoother than the paint, faint wear in the ink."""
    import bpy
    m, nt, p, g = C.new_material(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    g.l(tex.outputs["Color"], C.inp(p, "Base Color"))
    g.l(tex.outputs["Alpha"], C.inp(p, "Alpha"))
    co = C.body_coords(g, ref_obj)
    g.l(g.ramp(g.noise(co, 1.2, detail=6), [(0.3, 0.55), (0.7, 0.68)]), C.inp(p, "Roughness"))
    C.set_in(p, ["Specular IOR Level", "Specular"], 0.12)
    return m

def dog_plane(mat):
    import bpy, bmesh
    bm = bmesh.new()
    cx, cy, r = fx(DOG_C[0]), fy(DOG_C[1]), DOG_SIZE / 2
    vs = [bm.verts.new(v) for v in ((cx - r, cy - r, 0), (cx + r, cy - r, 0), (cx + r, cy + r, 0), (cx - r, cy + r, 0))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): loop[uv].uv = t
    return C.mesh_obj("HoundPrint", bm, mat)

# ----------------------------------------------------------------------------- build
def build(scene):
    import bpy
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(0.5), fy(SW_CY_FRAC)
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = C.mat_powder_coat("MatteBlack", MATTE_BLACK, body, scuff_center=(sx, sy),
                              rough_base=0.70, spec=0.22, coat=0.0)
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.62, 0.63, 0.65, 1), 0.26, smudges=0.1)
    screw_metal = C.mat_metal("ScrewMetal", (0.74, 0.74, 0.76, 1), 0.25, smudges=0.06)
    ink = C.mat_ink("InkBlood", BLOOD_INK, body, chip_amount=0.5)
    black_ink = C.mat_ink("InkBlack", (0.004, 0.004, 0.004, 1), body, chip_amount=0.0)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.008, 0.008, 0.009, 1), rough=0.58, spec=0.18, smudges=0.06)
    knob_cap = C.mat_metal("KnobCapAlu", (0.40, 0.40, 0.42, 1), 0.38, smudges=0.06)   # 0.55 read almost white on black
    pointer = C.mat_simple("PointerRed", (0.55, 0.012, 0.015, 1), rough=0.45)

    inset = 9.0 / UI_BODY_PX * W
    for i, (ax, ay) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        C.phillips_screw(f"Screw{i}", ax * (W / 2 - inset), ay * (H / 2 - inset), 1.7,
                         [0.7, 0.1, 1.1, 0.4][i], screw_metal, face, colls["Cutters"])

    name_font = bpy.data.fonts.load(FONT_NAME) if os.path.exists(FONT_NAME) else None
    label_font = next((bpy.data.fonts.load(p) for p in FONT_LABEL_CANDIDATES if os.path.exists(p)), None)
    ncx, ncy = rect_center(NAME)
    # the hound: printed first (lowest), then the black knock-out outline, then the red name on top
    if os.path.exists(DOG_IMAGE):
        o = dog_plane(mat_print("HoundPrint", DOG_IMAGE, body)); o.location = (0, 0, 0.005); face.objects.link(o)
    name_rect = (ncx, ncy, NAME[2] * W * 0.84, NAME[3] * H * 0.70)
    outline = C.text_obj("NameOutline", "FERAL HOUND", name_font, black_ink, name_rect, face, z=0.02)
    outline.data.offset = 0.30 / outline.scale.x                   # ~0.3 mm fatter than the red letters
    C.text_obj("Name", "FERAL HOUND", name_font, ink, name_rect, face, z=0.05)
    C.text_obj("Sub", "DISTORTION", label_font, ink,
               (fx(SUB_C[0]), fy(SUB_C[1]), SUB_WH[0] * W * 0.90, SUB_WH[1] * H * 0.62), face, spacing=1.15)
    for row in range(2):
        for i, (label, cxf) in enumerate(zip(KNOB_LABELS[row], KNOB_CX)):
            C.text_obj(f"Label{row}{i}", label, label_font, ink,
                       (fx(cxf), fy(label_cy_frac(row)), W * 0.24, 13.0 / UI_BODY_PX_H * H * 0.75), face, spacing=1.05)
    lx, ly = fx(LED_CX_FRAC), fy(LED_CY_FRAC)
    bez = C.cylinder("LedBezel", LED_D * 0.5 + 1.2, 1.2, mat=chrome); C.bevel(bez, 0.4, 3)
    bez.location = (lx, ly, 0); face.objects.link(bez)
    for key, on in (("LedOn", True), ("LedOff", False)):
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, C.mat_led(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    # one knob, rendered at the big size (top-left position); the plugin scales the frames for the small row
    kx, ky = fx(KNOB_CX[0]), fy(knob_cy_frac(0))
    pivot = C.knurled_knob("Knob", KNOB_D_BIG * 0.5, 11.0, (knob_skirt, knob_cap, pointer), colls["Knob"])
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
    import bpy
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    scene = C.setup_scene(ST)
    C.world_hdri(scene, ST.hdri, rotation_deg=40.0)
    C.add_key_light(scene)
    C.add_softbox(scene)
    colls, P = build(scene)
    cam = C.Camera(scene, UI_BODY_PX / W * ST.oversample)
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

    render_face(os.path.join(OUT, "feralhound_face.png"))

    C.set_catcher(face_objs, True)
    C.show_only([colls["Face"], colls["Knob"]], groups)
    kx, ky = P["knob"]
    cam.frame(kx, ky, KNOB_D_BIG * KNOB_PAD, KNOB_D_BIG * KNOB_PAD)
    paths = []
    scene.cycles.samples = ST.knob_samples
    for i in range(ST.knob_frames):
        pos = i / (ST.knob_frames - 1)
        angle = math.radians(-135.0 + pos * 270.0)
        P["pivot"].rotation_euler = (0, 0, -angle)
        p = os.path.join(TMP, f"knob_{i:03d}.png"); C.render_to(scene, p); paths.append(p)
    C.stack_grid(paths, os.path.join(OUT, "feralhound_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "feralhound_switch_up.png"), ("SwitchDown", "feralhound_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "feralhound_led_on.png"), ("LedOff", "feralhound_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "feralhound_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    for c in groups: c.hide_render = c in (colls["SwitchDown"], colls["LedOff"])
    for c in (colls["SwitchDown"], colls["LedOff"]): c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "feralhound.blend"))
    print("[pedal] done")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
