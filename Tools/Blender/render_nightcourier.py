"""
Night Courier - photoreal Blender render (based on the EarthQuaker Devices Dispatch Master; Michael's artwork).
Michael's full-face artwork (Assets/nightcourier_art.png, made by Tools/Art/make_nightcourier_art.py: the hooded
courier above the moonlit river city, every control label, "NIGHT COURIER", "DELAY / REVERB", "SOUND TRAVELS
FURTHER AT NIGHT") UV-printed 2.6 mm inside the edge of a matte black enclosure. The painted controls were
painted out of the art; the real ones are rendered where they were: six black knurled knobs with black-metal caps
and white pointers (one strip at the big size; the plugin scales it for MOD / TONE), a chrome bat-handle 3-way
DELAY / REVERB / BOTH toggle (up / centre / down), a cool-white LED in a dark chrome bezel and a satin-silver /
chrome BYPASS footswitch. Uses pedal_render_common.py.

Writes Assets/NightCourier/: nightcourier_face.png, nightcourier_knob_strip.png (8-column grid),
nightcourier_switch_up/down.png, nightcourier_led_on/off.png, nightcourier_toggle_up/centre/down.png, and saves
Tools/Blender/nightcourier.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_nightcourier.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (pedalId "nc" branch; fractions printed by
Tools/Art/make_nightcourier_art.py) and NightCourierFace (Source/Faces/PedalFaces.cpp). Pads MUST match
RenderedFace / NightCourierFace (togglePad).
The layout part of this file imports without Blender (used for alignment checks).
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "NightCourier")
TMP = os.path.join(HERE, "_frames_nightcourier")
ART_IMAGE = os.path.join(ROOT, "Assets", "nightcourier_art.png")

W, H = 91.0, 91.0 * 372.0 / 226.0          # = plugin pedal body 226 x 372 px
UI_BODY_PX = 226.0
UI_BODY_PX_H = 372.0
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6
TOGGLE_PAD = 1.30                                       # = NightCourierFace::togglePad
ART_INSET = 2.6                                         # mm (= FaceLayout::artInset * W)

# Albedos darker than the target look (AgX lifts and desaturates)
MATTE_BLACK = (0.008, 0.008, 0.0085, 1)                # matte powder (Feral Hound: 0.007; 0.011 read charcoal)
STEEL_REFERENCE_TARGET = 0.74                          # same exposure basis as the other pedals
PRINT_SAT, PRINT_VALUE = 0.85, 0.88                    # quick 1 (0.90 / 0.86, = Thunderhead): ~5 deg too blue (creams read
PRINT_WARM = (1.0, 0.95, 0.87, 1)                      # neutral grey, blues over-saturated), blacks lifted 15 -> 18.
PRINT_CONTRAST = 0.0                                   # quick 2 (0.95 / 0.92, warm (1,.96,.90), contrast 0.12): hue right but
                                                       # contrast acts on linear values: 27 % too dark, blues s .35-.43

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, pedalId "nc")
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.1537                                     # TIME / REPEATS / MIX / REVERB; MOD / TONE = W * 0.1353 (same frames, scaled)
KNOB_C = [(0.1546, 0.1837), (0.3801, 0.1825), (0.6209, 0.1825), (0.8515, 0.1825)]
SMALL_D = W * 0.1353
SMALL_C = [(0.2366, 0.3456), (0.7644, 0.3456)]
LED_D = 11.0 / UI_BODY_PX * W
LED_C = (0.1618, 0.7553)
SW_D = W * 0.165                                        # = FaceLayout (smaller than standard: BYPASS is printed below)
SW_C = (0.1598, 0.8332)
TOG_C, TOG_WH = (0.5010, 0.3817), (W * 0.10, W * 0.16)
TOGGLE_POS = (("ToggleUp", -32.0, "up"), ("ToggleCentre", 0.0, "centre"), ("ToggleDown", 32.0, "down"))
LED_BLOOM = (0.62, 0.80, 1.0)                           # cool white-blue glow, like the art's LED

def mat_led_cool(name, on):
    """Steel-blue glass lens like the art's LED. quick 1 (emission (0.55,0.75,1) x 0.7) burnt out to a flat white disc:
    a weaker glow keeps the blue glass and its reflections visible."""
    m, nt, p, g = C.new_material(name)
    C.set_in(p, "Base Color", (0.18, 0.32, 0.52, 1) if on else (0.02, 0.025, 0.035, 1))
    C.set_in(p, "Roughness", 0.05); C.set_in(p, ["Coat Weight", "Clearcoat"], 1.0)
    C.set_in(p, ["Transmission Weight", "Transmission"], 0.3)
    if on:
        C.set_in(p, ["Emission Color", "Emission"], (0.40, 0.62, 1.0, 1))
        C.set_in(p, "Emission Strength", 0.16)               # quick 2 (0.25): pale flat blue-white
    return m

# ----------------------------------------------------------------------------- materials (Blender only)
def mat_art(name, path, ref_obj):
    """The artwork as a UV print: full colour, satin, thin coat; worn a little with the enclosure's noise."""
    import bpy
    m, nt, p, g = C.new_material(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    C.set_in(hs, "Saturation", PRINT_SAT); C.set_in(hs, "Value", PRINT_VALUE)
    g.l(tex.outputs["Color"], C.inp(hs, "Color"))
    warm = g.mixc(1.0, hs.outputs["Color"], PRINT_WARM, blend="MULTIPLY")
    bc = nt.nodes.new("ShaderNodeBrightContrast"); C.set_in(bc, "Contrast", PRINT_CONTRAST)
    g.l(warm, C.inp(bc, "Color")); g.l(bc.outputs["Color"], C.inp(p, "Base Color"))
    co = C.body_coords(g, ref_obj)
    g.l(g.ramp(g.noise(co, 1.2, detail=6), [(0.3, 0.50), (0.7, 0.66)]), C.inp(p, "Roughness"))
    C.set_in(p, ["Specular IOR Level", "Specular"], 0.10)
    C.set_in(p, ["Coat Weight", "Clearcoat"], 0.08)
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

# ----------------------------------------------------------------------------- build
def build(scene):
    import bpy
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "ToggleUp", "ToggleCentre", "ToggleDown", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(SW_C[0]), fy(SW_C[1])
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = C.mat_powder_coat("MatteBlack", MATTE_BLACK, body, scuff_center=(sx, sy), rough_base=0.70, spec=0.22, coat=0.03)
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    dark_chrome = C.mat_metal("DarkChrome", (0.30, 0.30, 0.32, 1), 0.12, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.30, 0.30, 0.31, 1), 0.30, smudges=0.1)   # art = light satin silver (0.30 read light grey on Gatekeeper)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.006, 0.006, 0.007, 1), rough=0.40, spec=0.35, smudges=0.06)
    knob_cap = C.mat_metal("KnobCapBlackMetal", (0.045, 0.045, 0.048, 1), 0.18, smudges=0.04)   # quick 1 (0.035 / 0.22) flat matte, quick 2 (0.10 / 0.26) mid grey
    pointer = C.mat_simple("PointerWhite", (0.80, 0.80, 0.80, 1), rough=0.4)

    if os.path.exists(ART_IMAGE):
        o = art_plane(mat_art("ArtPrint", ART_IMAGE, body)); o.location = (0, 0, 0.005); face.objects.link(o)
    else:
        print("[pedal] WARNING: missing", ART_IMAGE)

    # LED (dark chrome bezel, like the art)
    lx, ly = fx(LED_C[0]), fy(LED_C[1])
    bez = C.cylinder("LedBezel", LED_D * 0.5 + 1.2, 1.2, mat=dark_chrome); C.bevel(bez, 0.4, 3)
    bez.location = (lx, ly, 0); face.objects.link(bez)
    for key, on in (("LedOn", True), ("LedOff", False)):
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, mat_led_cool(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    # one knob (TIME position); the plugin uses the same frames for every knob (scaled down for MOD / TONE)
    kx, ky = fx(KNOB_C[0][0]), fy(KNOB_C[0][1])
    pivot = C.knurled_knob("Knob", KNOB_D * 0.5, 12.0, (knob_skirt, knob_cap, pointer), colls["Knob"])
    pivot.location = (kx, ky, 0)

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

    # DELAY / REVERB / BOTH 3-way toggle: washer, hex nut, threaded bushing, chrome bat lever up / centre / down
    tx, ty = fx(TOG_C[0]), fy(TOG_C[1])
    for key, tilt, _ in TOGGLE_POS:
        c = colls[key]
        # no washer: quick 1 + 2 rendered it (satin, then dark chrome) as a big light-grey disc; the art has none
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

    return colls, dict(pivot=pivot, knob=(kx, ky), switch=(sx, sy), led=(lx, ly), toggle=(tx, ty),
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
    groups = [colls[k] for k in ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "ToggleUp", "ToggleCentre", "ToggleDown")]
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

    render_face(os.path.join(OUT, "nightcourier_face.png"))

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
    C.stack_grid(paths, os.path.join(OUT, "nightcourier_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "nightcourier_switch_up.png"), ("SwitchDown", "nightcourier_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    tx, ty = P["toggle"]
    cam.frame(tx, ty, TOG_WH[0] * TOGGLE_PAD, TOG_WH[1] * TOGGLE_PAD)
    for key, fname in ((k, f"nightcourier_toggle_{n}.png") for k, _, n in TOGGLE_POS):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.80, outer=0.98)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "nightcourier_led_on.png"), ("LedOff", "nightcourier_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "nightcourier_led_on.png"), colour=LED_BLOOM)

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    hidden = (colls["SwitchDown"], colls["LedOff"], colls["ToggleUp"], colls["ToggleCentre"])
    for c in groups: c.hide_render = c in hidden
    for c in hidden: c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "nightcourier.blend"))
    print("[pedal] done")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
