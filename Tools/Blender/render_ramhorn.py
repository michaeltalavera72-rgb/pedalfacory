"""
Ramhorn Fuzz - photoreal Blender render (original design for the Virtual Pedalboard).
Uses pedal_render_common.py (same folder) for lighting, materials, wear and output.

Writes Assets/Ramhorn/:
    ramhorn_face.png          enclosure + printing + screws + LED bezel
    ramhorn_knob_strip.png    knob frames in an 8-column grid, left->right, top->bottom (-135..+135 deg)
    ramhorn_switch_up.png / ramhorn_switch_down.png
    ramhorn_led_on.png (with glow) / ramhorn_led_off.png
and saves Tools/Blender/ramhorn.blend for hand tweaking.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_ramhorn.py
Options after "--":   --quick          fast preview (16 knob frames, 32 samples)
                      --hdri=NAME.exr  pick another of Blender's studio lights

Positions MUST match Source/UI/FaceLayout.h. Pad factors MUST match RamhornFace (PedalFaces.cpp).
"""
import bpy, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib, pedal_render_common as C
importlib.reload(C)

ST = C.Settings(sys.argv)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "Ramhorn")
TMP = os.path.join(HERE, "_frames")
FONT_NAME = os.path.join(ROOT, "Assets", "AlfaSlabOne-Regular.ttf")
FONT_LABEL_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

# Body in mm; aspect = plugin pedal body (226 x 372 px)
W, H = 91.0, 91.0 * 372.0 / 226.0          # = plugin pedal body 226 x 372 px (v28; was 120 mm / 298 px)
UI_BODY_PX = 226.0
PX_PER_MM = UI_BODY_PX / W * ST.oversample
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6

INK_CHARCOAL = (0.012, 0.013, 0.015, 1)
INK_AMBER = (0.75, 0.30, 0.03, 1)
INK_AMBER_DARK = (0.30, 0.10, 0.01, 1)

# ----------------------------------------------------------------------------- layout (= FaceLayout.h)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.255
KNOB_TOP = 0.055
KNOB_CX = [0.19, 0.50, 0.81]
KNOB_CY_FRAC = KNOB_TOP + (KNOB_D / H) * 0.5
LABEL_CY_FRAC = KNOB_TOP + (KNOB_D / H) + 9.5 / 372.0
NAME = (0.06, 0.355, 0.88, 0.135)
SUB = (0.06, 0.49, 0.88, 0.065)
EMBLEM = (0.26, 0.565, 0.48, 0.135)
SW_D = W * 0.19
SW_CY_FRAC = 0.865
LED_D = 11.0 / UI_BODY_PX * W
LED_CY_FRAC = 0.74
def rect_center(r): return fx(r[0] + r[2] / 2), fy(r[1] + r[3] / 2)

def horn_outline(R, turns=1.6, n=160):
    t_max = turns * 2 * math.pi
    outer, inner = [], []
    for i in range(n + 1):
        u = i / n; t = u * t_max
        r = R * (0.10 + 0.90 * u); w = R * (0.04 + 0.36 * u * u)
        c, s = math.cos(t), math.sin(t)
        outer.append((c * (r + w / 2), s * (r + w / 2)))
        inner.append((c * max(0.0, r - w / 2), s * max(0.0, r - w / 2)))
    return outer + list(reversed(inner))

# ----------------------------------------------------------------------------- build
def build(scene):
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(0.5), fy(SW_CY_FRAC)
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    steel = C.mat_brushed_steel(body, scuff_center=(sx, sy))
    body.data.materials.append(steel)
    face.objects.link(body)

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.62, 0.63, 0.65, 1), 0.26, smudges=0.1)
    screw_metal = C.mat_metal("ScrewMetal", (0.80, 0.80, 0.82, 1), 0.22, smudges=0.05)
    charcoal = C.mat_ink("InkCharcoal", INK_CHARCOAL, body)
    amber = C.mat_ink("InkAmber", INK_AMBER, body)
    amber_dark = C.mat_ink("InkAmberDark", INK_AMBER_DARK, body)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.008, 0.008, 0.009, 1), rough=0.58, spec=0.18, smudges=0.06)
    knob_cap = C.mat_plastic("KnobCap", (0.008, 0.008, 0.009, 1), rough=0.38, spec=0.25, coat=0.15, smudges=0.08)
    pointer = C.mat_simple("PointerPaint", (0.88, 0.86, 0.80, 1), rough=0.45)

    # screws
    inset = 9.0 / UI_BODY_PX * W
    for i, (ax, ay) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        C.phillips_screw(f"Screw{i}", ax * (W / 2 - inset), ay * (H / 2 - inset), 1.7,
                         [0.3, 1.1, 0.8, 0.1][i], screw_metal, face, colls["Cutters"])

    # printing
    name_font = bpy.data.fonts.load(FONT_NAME) if os.path.exists(FONT_NAME) else None
    label_font = next((bpy.data.fonts.load(p) for p in FONT_LABEL_CANDIDATES if os.path.exists(p)), None)
    ncx, ncy = rect_center(NAME)
    nw, nh = NAME[2] * W, NAME[3] * H * 0.95
    C.text_obj("NameShadow", "RAMHORN", name_font, amber, (ncx + 0.8, ncy - 0.8, nw, nh), face, z=0.0)
    C.text_obj("Name", "RAMHORN", name_font, charcoal, (ncx, ncy, nw, nh), face, z=0.02)
    scx, scy = rect_center(SUB)
    C.text_obj("Sub", "FUZZ", name_font, amber_dark, (scx, scy, SUB[2] * W * 0.36, SUB[3] * H * 0.9), face, spacing=1.9)
    rule_len = SUB[2] * W * 0.5 - SUB[2] * W * 0.19 - 10 / UI_BODY_PX * W
    for side in (-1, 1):
        r = C.box(f"Rule{side}", rule_len, 0.6, 0.03, mat=charcoal)
        r.location = (scx + side * (SUB[2] * W * 0.19 + 4 / UI_BODY_PX * W + rule_len / 2), scy, 0.015)
        face.objects.link(r)
    for i, (label, cxf) in enumerate(zip(["VOLUME", "TONE", "SUSTAIN"], KNOB_CX)):
        C.text_obj(f"Label{i}", label, label_font, charcoal,
                   (fx(cxf), fy(LABEL_CY_FRAC), KNOB_D * 1.4, 13.0 / 372.0 * H * 0.75), face, spacing=1.05)

    # emblem: ram's horns (roots meet at top centre) + diamond
    ecx, ecy = rect_center(EMBLEM)
    R = EMBLEM[3] * H * 0.5
    gap = EMBLEM[2] * W * 0.27
    outline = horn_outline(R)
    for side in (-1, 1):
        for layer, mat, dz, off in [("Shadow", amber, 0.0, (0.6, -0.6)), ("Ink", charcoal, 0.02, (0, 0))]:
            o = C.flat_shape(f"Horn{layer}{side}", outline, mat)
            o.location = (ecx + side * gap + off[0], ecy + off[1], dz)
            o.rotation_euler = (0, 0, math.radians(234) * (1 if side < 0 else -1))
            o.scale = (1 if side < 0 else -1, -1, 1)
            face.objects.link(o)
    ds = R * 0.32
    d = C.flat_shape("Diamond", [(0, ds), (ds * 0.7, 0), (0, -ds), (-ds * 0.7, 0)], amber)
    d.location = (ecx, ecy, 0.02); face.objects.link(d)

    # LED bezel + lenses
    lx, ly = fx(0.5), fy(LED_CY_FRAC)
    bez = C.cylinder("LedBezel", LED_D * 0.5 + 1.2, 1.2, mat=chrome); C.bevel(bez, 0.4, 3)
    bez.location = (lx, ly, 0); face.objects.link(bez)
    for key, on in (("LedOn", True), ("LedOff", False)):
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, C.mat_led(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    # knob (rendered once at knob 0's position; the same filmstrip serves all three)
    kx, ky = fx(KNOB_CX[0]), fy(KNOB_CY_FRAC)
    pivot = C.knurled_knob("Knob", KNOB_D * 0.5, 12.2, (knob_skirt, knob_cap, pointer), colls["Knob"])
    pivot.location = (kx, ky, 0)

    # footswitch: washer, hex nut, plunger with domed chrome cap
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

    return colls, dict(pivot=pivot, knob=(kx, ky), switch=(sx, sy), led=(lx, ly))

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

    # consistent brightness for every pedal
    C.auto_exposure(scene, render_face, ST.target_brightness, os.path.join(TMP, "exposure_probe.png"))

    # 1. face
    render_face(os.path.join(OUT, "ramhorn_face.png"))

    # parts are rendered over the enclosure acting as a shadow catcher:
    # they get its bounce light and reflections, and only their own shadows end up in the image
    C.set_catcher(face_objs, True)

    # 2. knob filmstrip
    C.show_only([colls["Face"], colls["Knob"]], groups)
    kx, ky = P["knob"]
    cam.frame(kx, ky, KNOB_D * KNOB_PAD, KNOB_D * KNOB_PAD)
    paths = []
    scene.cycles.samples = ST.knob_samples
    for i in range(ST.knob_frames):
        pos = i / (ST.knob_frames - 1)
        angle = math.radians(-135.0 + pos * 270.0)                 # clockwise from 12 o'clock
        P["pivot"].rotation_euler = (0, 0, -angle)
        p = os.path.join(TMP, f"knob_{i:03d}.png"); C.render_to(scene, p); paths.append(p)
    C.stack_grid(paths, os.path.join(OUT, "ramhorn_knob_strip.png"))
    scene.cycles.samples = ST.samples

    # 3. footswitch
    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "ramhorn_switch_up.png"), ("SwitchDown", "ramhorn_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    # 4. LED lens (+ baked glow when lit)
    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "ramhorn_led_on.png"), ("LedOff", "ramhorn_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "ramhorn_led_on.png"))

    # leave the whole pedal visible and save the scene
    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    for c in groups: c.hide_render = c in (colls["SwitchDown"], colls["LedOff"])
    for c in (colls["SwitchDown"], colls["LedOff"]): c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "ramhorn.blend"))
    print("[pedal] done")

main()
