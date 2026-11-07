"""
Coral Tide - photoreal Blender render (Bearfoot / BJFE Sea Blue EQ + Baby Pink Booster, double-wide; Michael's artwork).
Michael's full-face artwork (Assets/coraltide_art.png, made by Tools/Art/make_coraltide_art.py from his original
image: coral reef, sea and sunset, "Coral Tide", BOOST / LEVEL / ORDER / LOW / HIGH, "TONE FLOWS FURTHER", BOOST / EQ)
UV-printed 2.6 mm inside the edge of a cream double-wide enclosure (186.8 x 149.8 mm = plugin body 464 x 372 px).
The real controls sit where the art's painted ones were: four cream "heptagon" knobs with a black pointer line (like
the art's), a chrome bat-lever ORDER toggle, a red (BOOST) and a blue (EQ) LED in dark chrome bezels, and two
satin-silver / chrome footswitches. Uses pedal_render_common.py.

Writes Assets/CoralTide/: coraltide_face.png, coraltide_knob_strip.png (8-column grid, one strip for all four knobs),
coraltide_switch_up/down.png (both footswitches), coraltide_led_on/off.png (EQ, blue), coraltide_led2_on/off.png
(BOOST, red), coraltide_toggle_up/down.png, and saves Tools/Blender/coraltide.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_coraltide.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (pedalId "ct"; fractions printed by Tools/Art/make_coraltide_art.py) and
CoralTideFace (Source/Faces/PedalFaces.cpp: togglePad). Pads MUST match RenderedFace.
The layout part of this file imports without Blender (used for alignment checks).
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "CoralTide")
TMP = os.path.join(HERE, "_frames_coraltide")
ART_IMAGE = os.path.join(ROOT, "Assets", "coraltide_art.png")

UI_BODY_PX = 464.0                         # double-wide: FaceLayout::bodyWidthFor(2)
UI_BODY_PX_H = 372.0
W, H = 91.0 * UI_BODY_PX / 226.0, 91.0 * UI_BODY_PX_H / 226.0     # 186.8 x 149.8 mm (same mm per px as every pedal)
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6
TOGGLE_PAD = 1.30                                       # = CoralTideFace::togglePad
ART_INSET = 2.6                                         # mm (= FaceLayout::artInset2 * W)

# Albedos darker than the target look (AgX lifts and desaturates). First guesses: tune from the quick render.
CREAM_PAINT = (0.62, 0.52, 0.40, 1)                    # enclosure: the art's cream margin is sRGB ~ (244, 227, 209)
KNOB_CREAM = (0.56, 0.52, 0.43, 1)                     # the art's knobs: off-white sRGB ~ (234, 228, 214)
STEEL_REFERENCE_TARGET = 0.74                          # same exposure basis as the other pedals
PRINT_SAT, PRINT_VALUE, PRINT_HUE = 1.05, 0.95, 0.5

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, pedalId "ct")
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.1280                                     # BOOST / LEVEL / LOW / HIGH (one strip for all four)
KNOB_C = [(0.1458, 0.2207), (0.3440, 0.2194), (0.6527, 0.2194), (0.8516, 0.2194)]
STRIP_KNOB = 1                                          # the strip is rendered on LEVEL (any knob: the face is a catcher)
LED_D = 13.0 / UI_BODY_PX * W
LED_EQ, LED_BOOST = (0.6300, 0.7008), (0.3681, 0.7008)  # blue = main (EQ) LED, red = second (BOOST) LED
SW_D = W * 0.1072
SW_EQ, SW_BOOST = (0.6293, 0.8146), (0.3668, 0.8146)    # images rendered once at EQ, used for both
WU = 226.0 * W / UI_BODY_PX                             # single-pedal width (FaceLayout's Wu) in mm
TOG_C, TOG_WH = (0.5000, 0.2045), (WU * 0.10, WU * 0.16)
TOGGLE_POS = (("ToggleUp", -32.0, "up"), ("ToggleDown", 32.0, "down"))
BLOOM_RED, BLOOM_BLUE = (1.0, 0.12, 0.05), (0.20, 0.45, 1.0)

# Colour grade for the lit LED images (after bloom): AgX renders a bright emissive lens pale (see Golden Haze);
# lens luminance is mapped onto the LED's colour ramp like the art: hot centre -> saturated rim.
GRADE_BLUE = [(0.00, (0.00, 0.02, 0.22)), (0.30, (0.00, 0.12, 0.85)), (0.65, (0.08, 0.38, 1.00)),
              (0.90, (0.55, 0.75, 1.00)), (1.00, (0.92, 0.96, 1.00))]   # quick 1: pastel sky blue; the art's is deep blue
GRADE_RED = [(0.00, (0.25, 0.01, 0.00)), (0.30, (0.90, 0.08, 0.03)), (0.65, (1.00, 0.35, 0.25)),
             (0.90, (1.00, 0.80, 0.72)), (1.00, (1.00, 0.97, 0.95))]

def colour_grade(path, stops, lo=0.45, hi=0.90, amount=0.85):
    import numpy as np
    a = C.load_rgba(path)
    rgb = a[..., :3]
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    t = np.clip((L - lo) / (hi - lo), 0.0, 1.0)
    xs = [st[0] for st in stops]
    ramp = np.stack([np.interp(t, xs, [st[1][i] for st in stops]) for i in range(3)], -1)
    a[..., :3] = rgb * (1.0 - amount) + ramp * amount
    C.save_rgba(a, path)

# ----------------------------------------------------------------------------- print grade (after rendering)
# Quick render 1 (2026-11-07): AgX compressed the light art hard - cream (243,227,208) came out grey (189,186,181),
# S 0.14 -> 0.04, V 0.95 -> 0.74, while the darks were right (navy within 2 %). Albedo/Hue-Sat tweaks can't fix that
# (the creams are already near albedo 1). So the face render is graded back onto the artwork: per-channel tone curves
# fitted from block means of the face render vs the art (median per luminance bin, monotone), then applied to the face
# and to every control image (same lighting / exposure: the knobs' cream plastic lands on the art's knob colour too).
# Tested on quick 1: mean error per channel 0.149 / 0.104 / 0.074 -> 0.016 / 0.009 / 0.009. LED images are graded
# separately (colour_grade).
def _cell_means(a, x0, y0, x1, y1, nx, ny):
    import numpy as np
    h, w = a.shape[:2]
    I = np.zeros((h + 1, w + 1, 3)); I[1:, 1:] = a[..., :3].cumsum(0).cumsum(1)
    xs = np.linspace(x0, x1, nx + 1).round().astype(int); ys = np.linspace(y0, y1, ny + 1).round().astype(int)
    S = (I[ys[1:, None], xs[None, 1:]] - I[ys[:-1, None], xs[None, 1:]]
         - I[ys[1:, None], xs[None, :-1]] + I[ys[:-1, None], xs[None, :-1]])
    n = ((ys[1:] - ys[:-1])[:, None] * (xs[1:] - xs[:-1])[None, :])[..., None]
    return S / n

def fit_print_grade(face_path, art_path, nx=187, ny=149, bins=24):
    import numpy as np
    face, art = C.load_rgba(face_path), C.load_rgba(art_path)          # both bottom-up: same orientation
    fh, fw = face.shape[:2]; ah, aw = art.shape[:2]
    ix, iy = ART_INSET / W * fw, ART_INSET / H * fh
    F = _cell_means(face, ix, iy, fw - ix, fh - iy, nx, ny).reshape(-1, 3)
    A = _cell_means(art, 0, 0, aw, ah, nx, ny).reshape(-1, 3)
    luts = []
    for c in range(3):
        f, t = F[:, c], A[:, c]
        edges = np.quantile(f, np.linspace(0, 1, bins + 1))
        xs, ys = [0.0], [0.0]
        for i in range(bins):
            m = (f >= edges[i]) & (f <= edges[i + 1])
            if m.sum() > 20: xs.append(float(np.median(f[m]))); ys.append(float(np.median(t[m])))
        xs.append(1.0); ys.append(min(1.0, ys[-1] + (1.0 - xs[-2])))
        ys = np.maximum.accumulate(np.array(ys))
        luts.append(np.interp(np.linspace(0, 1, 256), xs, ys))
        print(f"[pedal] print grade ch{c}: " + " ".join(f"{luts[c][i]:.3f}" for i in range(0, 256, 32)))
    return luts

def apply_print_grade(path, luts):
    import numpy as np
    a = C.load_rgba(path)
    for c in range(3):
        a[..., c] = np.interp(a[..., c], np.linspace(0, 1, 256), luts[c])
    C.save_rgba(a, path)

# ----------------------------------------------------------------------------- materials (Blender only)
def mat_led_colour(name, on, base, emit, strength):
    m, nt, p, g = C.new_material(name)
    C.set_in(p, "Base Color", base if on else tuple(x * 0.08 for x in base[:3]) + (1,))
    C.set_in(p, "Roughness", 0.06); C.set_in(p, ["Coat Weight", "Clearcoat"], 1.0)
    C.set_in(p, ["Transmission Weight", "Transmission"], 0.3)
    if on:
        C.set_in(p, ["Emission Color", "Emission"], emit)
        C.set_in(p, "Emission Strength", strength)
    return m

def mat_art(name, path, ref_obj):
    """The artwork as a UV print: full colour, satin, thin coat; alpha = the art's rounded corners."""
    import bpy
    m, nt, p, g = C.new_material(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    C.set_in(hs, "Saturation", PRINT_SAT); C.set_in(hs, "Value", PRINT_VALUE); C.set_in(hs, "Hue", PRINT_HUE)
    g.l(tex.outputs["Color"], C.inp(hs, "Color")); g.l(hs.outputs["Color"], C.inp(p, "Base Color"))
    g.l(tex.outputs["Alpha"], C.inp(p, "Alpha"))
    co = C.body_coords(g, ref_obj)
    g.l(g.ramp(g.noise(co, 1.2, detail=6), [(0.3, 0.48), (0.7, 0.62)]), C.inp(p, "Roughness"))
    C.set_in(p, ["Specular IOR Level", "Specular"], 0.10)
    C.set_in(p, ["Coat Weight", "Clearcoat"], 0.10)
    return m

def art_plane(mat):
    import bmesh
    bm = bmesh.new()
    hw, hh = W / 2 - ART_INSET, H / 2 - ART_INSET
    vs = [bm.verts.new(v) for v in ((-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): loop[uv].uv = t
    return C.mesh_obj("ArtPrint", bm, mat)

def cream_knob(name, R, mats, coll):
    """Like the art's knobs: a round skirt under a soft seven-lobed cap, a black pointer line on top."""
    import bpy, bmesh
    plastic, pointer_mat = mats
    skirt = C.cylinder(name + "Skirt", R, 3.2, verts=128, mat=plastic); C.bevel(skirt, 0.9, 4); C.smooth(skirt)
    bm = bmesh.new()
    n, Rc = 7 * 24, R * 0.80
    ring = [bm.verts.new((Rc * (1 + 0.075 * math.cos(7 * a)) * math.cos(a), Rc * (1 + 0.075 * math.cos(7 * a)) * math.sin(a), 0))
            for a in (2 * math.pi * i / n + math.pi / 2 for i in range(n))]
    f = bm.faces.new(ring)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, 8.5))
    bmesh.ops.scale(bm, verts=top, vec=(0.93, 0.93, 1.0))                     # slight taper
    bmesh.ops.translate(bm, verts=list(bm.verts), vec=(0, 0, 2.6))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cap = C.mesh_obj(name + "Cap", bm, plastic); C.bevel(cap, 1.6, 6, 40); C.smooth(cap)
    ptr = C.box(name + "Pointer", R * 0.085, R * 0.62, 0.10, center=(0, R * 0.40, 11.1 + 0.04), mat=pointer_mat)   # quick 1: too short
    C.bevel(ptr, 0.03, 2)
    pivot = bpy.data.objects.new(name + "Pivot", None); coll.objects.link(pivot)
    for o in (skirt, cap, ptr):
        o.parent = pivot; coll.objects.link(o)
    return pivot

# ----------------------------------------------------------------------------- build
def build(scene):
    import bpy
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Led2On", "Led2Off", "ToggleUp", "ToggleDown",
              "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = C.mat_powder_coat("CreamPaint", CREAM_PAINT, body, rough_base=0.50, spec=0.30, coat=0.06)
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    dark_chrome = C.mat_metal("DarkChrome", (0.30, 0.30, 0.32, 1), 0.12, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.30, 0.30, 0.31, 1), 0.30, smudges=0.1)
    knob_plastic = C.mat_plastic("KnobCream", KNOB_CREAM, rough=0.32, spec=0.40, coat=0.25, smudges=0.06)
    pointer = C.mat_simple("PointerBlack", (0.012, 0.012, 0.012, 1), rough=0.35)

    if os.path.exists(ART_IMAGE):
        o = art_plane(mat_art("ArtPrint", ART_IMAGE, body)); o.location = (0, 0, 0.005); face.objects.link(o)
    else:
        print("[pedal] WARNING: missing", ART_IMAGE)

    # LEDs: bezels on the face, lenses per state
    leds = {}
    for tag, pos, base, emit, strength in (("", LED_EQ, (0.02, 0.10, 0.90, 1), (0.04, 0.18, 1.0, 1), 0.8),
                                           ("2", LED_BOOST, (0.9, 0.03, 0.01, 1), (1.0, 0.07, 0.02, 1), 0.9)):
        lx, ly = fx(pos[0]), fy(pos[1])
        bez = C.cylinder(f"LedBezel{tag}", LED_D * 0.5 + 1.2, 1.2, mat=dark_chrome); C.bevel(bez, 0.4, 3)
        bez.location = (lx, ly, 0); face.objects.link(bez)
        for state, on in (("On", True), ("Off", False)):
            key = f"Led{tag}{state}"
            lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, mat_led_colour(f"Mat{key}", on, base, emit, strength), segs=48)
            lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)
        leds[tag] = (lx, ly)

    # one knob (the strip serves all four; the face under it is a shadow catcher)
    kx, ky = fx(KNOB_C[STRIP_KNOB][0]), fy(KNOB_C[STRIP_KNOB][1])
    pivot = cream_knob("Knob", KNOB_D * 0.5, (knob_plastic, pointer), colls["Knob"])
    pivot.location = (kx, ky, 0)

    sx, sy = fx(SW_EQ[0]), fy(SW_EQ[1])
    for key, travel in (("SwitchUp", 0.0), ("SwitchDown", -1.8)):
        c = colls[key]
        washer = C.cylinder(f"Washer{key}", SW_D * 0.56, 0.7, verts=96, mat=satin); C.bevel(washer, 0.2, 2)
        nut = C.cylinder(f"Nut{key}", SW_D * 0.5, 3.0, z0=0.7, verts=6, mat=satin); C.bevel(nut, 0.9, 3)
        nut.rotation_euler = (0, 0, math.radians(30))
        plunger = C.cylinder(f"Plunger{key}", SW_D * 0.32, 6.0 + travel, verts=96, mat=chrome)
        C.bevel(plunger, 0.8, 4); C.smooth(plunger)
        cap = C.dome(f"Dome{key}", SW_D * 0.30, 0.45, dark_chrome); cap.location = (0, 0, 6.0 + travel)
        for o in (washer, nut, plunger, cap):
            o.location = (sx, sy, o.location.z); c.objects.link(o)

    # ORDER toggle: hex nut, bushing, chrome bat lever up (B > EQ) / down (EQ > B), like Night Courier's
    tx, ty = fx(TOG_C[0]), fy(TOG_C[1])
    for key, tilt, _ in TOGGLE_POS:
        c = colls[key]
        nut = C.cylinder(f"TNut{key}", 4.1, 1.8, z0=0.5, verts=6, mat=chrome); C.bevel(nut, 0.35, 2)
        bush = C.cylinder(f"TBush{key}", 2.6, 3.4, z0=2.3, verts=48, mat=satin); C.bevel(bush, 0.3, 2)
        lever = C.cylinder(f"TLever{key}", 1.0, 9.0, verts=32, mat=chrome); C.smooth(lever)
        for v in lever.data.vertices:                                       # bat taper: thicker at the tip
            k = v.co.z / 9.0
            v.co.x *= 1.0 + 0.55 * k; v.co.y *= 1.0 + 0.55 * k
        ball = C.dome(f"TBall{key}", 1.65, 1.0, chrome, segs=32); ball.location = (0, 0, 9.0)
        piv = bpy.data.objects.new(f"TPivot{key}", None); c.objects.link(piv)
        piv.location = (tx, ty, 5.4); piv.rotation_euler = (math.radians(tilt), 0, 0)
        for o in (lever, ball):
            o.parent = piv; c.objects.link(o)
        for o in (nut, bush):
            o.location = (tx, ty, o.location.z); c.objects.link(o)

    return colls, dict(pivot=pivot, knob=(kx, ky), switch=(sx, sy), led=leds[""], led2=leds["2"], toggle=(tx, ty),
                       body=body, paint=paint, steel_ref=steel_ref)

# ----------------------------------------------------------------------------- render
def main():
    import bpy
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    scene = C.setup_scene(ST)
    C.world_hdri(scene, ST.hdri, rotation_deg=40.0)
    C.add_key_light(scene)
    C.add_softbox(scene, size=480.0)                                    # double-wide: a wider softbox
    colls, P = build(scene)
    cam = C.Camera(scene, UI_BODY_PX / W * ST.oversample)
    groups = [colls[k] for k in ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Led2On", "Led2Off",
                                 "ToggleUp", "ToggleDown")]
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

    render_face(os.path.join(OUT, "coraltide_face.png"))

    art_objs = [o for o in face_objs if o.name.startswith("ArtPrint")]
    for o in art_objs: o.hide_render = True                           # quick 1: a pale ghost of the lettering in the
    C.set_catcher(face_objs, True)                                    # knob frames - catch shadows on the paint only
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
    C.stack_grid(paths, os.path.join(OUT, "coraltide_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "coraltide_switch_up.png"), ("SwitchDown", "coraltide_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    tx, ty = P["toggle"]
    cam.frame(tx, ty, TOG_WH[0] * TOGGLE_PAD, TOG_WH[1] * TOGGLE_PAD)
    for key, fname in ((k, f"coraltide_toggle_{n}.png") for k, _, n in TOGGLE_POS):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.80, outer=0.98)

    for o in art_objs: o.hide_render = False
    C.set_catcher(face_objs, False)
    for tag, keyOn, keyOff, bloom, grade in (("", "LedOn", "LedOff", BLOOM_BLUE, GRADE_BLUE),
                                             ("2", "Led2On", "Led2Off", BLOOM_RED, GRADE_RED)):
        lx, ly = P["led" + tag]
        cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
        for key, state in ((keyOn, "on"), (keyOff, "off")):
            C.show_only([colls[key]], groups)
            C.render_to(scene, os.path.join(OUT, f"coraltide_led{tag}_{state}.png"))
        on = os.path.join(OUT, f"coraltide_led{tag}_on.png")
        C.bloom(on, colour=bloom)
        colour_grade(on, grade)

    luts = fit_print_grade(os.path.join(OUT, "coraltide_face.png"), ART_IMAGE)
    for f in ("coraltide_face.png", "coraltide_knob_strip.png", "coraltide_switch_up.png", "coraltide_switch_down.png",
              "coraltide_toggle_up.png", "coraltide_toggle_down.png"):
        apply_print_grade(os.path.join(OUT, f), luts)

    P["pivot"].rotation_euler = (0, 0, 0)
    hidden = (colls["SwitchDown"], colls["LedOff"], colls["Led2Off"], colls["ToggleUp"])
    for c in groups: c.hide_render = c in hidden
    for c in hidden: c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "coraltide.blend"))
    print("[pedal] done")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
