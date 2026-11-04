"""
Gatekeeper - photoreal Blender render (noise gate based on the Boss NF-1; Michael's artwork).
Michael's full-face artwork (Assets/gatekeeper_art.png, made by Tools/Art/make_gatekeeper_art.py from his
original image: the enthroned gatekeeper, iron gate, two hounds, "GATEKEEPER / NOISE GATE", THRESHOLD / RELEASE,
HARD / SOFT, "SILENCE PROTECTS THE HEAVY") UV-printed edge to edge, 2.6 mm inside the edge of a worn black
enclosure. The painted knobs, LED and footswitch were painted out of the art; the real ones are rendered exactly
where they were: two black knurled knobs with dark brushed-metal caps and white pointers, the red LED in a dark
chrome bezel, a satin/chrome footswitch, and a chrome bat-handle HARD/SOFT mini toggle left of the footswitch.
Uses pedal_render_common.py.

Writes Assets/Gatekeeper/: gatekeeper_face.png, gatekeeper_knob_strip.png (8-column grid),
gatekeeper_switch_up/down.png, gatekeeper_led_on/off.png, gatekeeper_toggle_up/down.png, and saves
Tools/Blender/gatekeeper.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_gatekeeper.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (2 knobs + toggle = the Gatekeeper branch) and GatekeeperFace
(Source/Faces/PedalFaces.cpp). Pads MUST match RenderedFace / GatekeeperFace (togglePad).
The layout part of this file imports without Blender (used for alignment checks).
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "Gatekeeper")
TMP = os.path.join(HERE, "_frames_gatekeeper")
ART_IMAGE = os.path.join(ROOT, "Assets", "gatekeeper_art.png")

W, H = 91.0, 91.0 * 372.0 / 226.0          # = plugin pedal body 226 x 372 px
UI_BODY_PX = 226.0
UI_BODY_PX_H = 372.0
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6
TOGGLE_PAD = 1.30                                       # = GatekeeperFace::togglePad
ART_INSET = 2.6                                         # mm (= FaceLayout::artInset * W)

# Albedos darker than the target look (AgX lifts and desaturates)
WORN_BLACK = (0.006, 0.006, 0.0065, 1)
STEEL_REFERENCE_TARGET = 0.74                          # same exposure basis as the other pedals
PRINT_SAT, PRINT_VALUE = 1.35, 0.86                    # quick 1 (1.15/1.22) ~25 % too bright; quick 2 (1.30/0.98) ~15 %

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, 2 knobs + toggle)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.235
KNOB_C = [(0.1787, 0.1223), (0.8246, 0.1223)]           # THRESHOLD, RELEASE
LED_D = 11.0 / UI_BODY_PX * W
LED_C = (0.50, 0.7217)
SW_D = W * 0.19
SW_C = (0.50, 0.8148)
TOG_C, TOG_WH = (0.23, 0.8148), (W * 0.10, W * 0.16)

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
    g.l(tex.outputs["Color"], C.inp(hs, "Color")); g.l(hs.outputs["Color"], C.inp(p, "Base Color"))
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
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "ToggleUp", "ToggleDown", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(SW_C[0]), fy(SW_C[1])
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = C.mat_powder_coat("WornBlack", WORN_BLACK, body, scuff_center=(sx, sy), rough_base=0.62, spec=0.25, coat=0.05)
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    dark_chrome = C.mat_metal("DarkChrome", (0.30, 0.30, 0.32, 1), 0.12, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.12, 0.12, 0.13, 1), 0.32, smudges=0.1)   # quick 1 (0.62) white, quick 2 (0.30) light grey; art = gunmetal
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
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, C.mat_led(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    # one knob (THRESHOLD position); the plugin uses the same frames for RELEASE
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

    # HARD/SOFT mini toggle: washer, hex nut, threaded bushing, chrome bat lever up (HARD) or down (SOFT)
    tx, ty = fx(TOG_C[0]), fy(TOG_C[1])
    for key, tilt in (("ToggleUp", -32.0), ("ToggleDown", 32.0)):
        c = colls[key]
        washer = C.cylinder(f"TWasher{key}", 4.6, 0.5, verts=64, mat=satin)
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
        for o in (washer, nut, bush):
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
    groups = [colls[k] for k in ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "ToggleUp", "ToggleDown")]
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

    render_face(os.path.join(OUT, "gatekeeper_face.png"))

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
    C.stack_grid(paths, os.path.join(OUT, "gatekeeper_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "gatekeeper_switch_up.png"), ("SwitchDown", "gatekeeper_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    tx, ty = P["toggle"]
    cam.frame(tx, ty, TOG_WH[0] * TOGGLE_PAD, TOG_WH[1] * TOGGLE_PAD)
    for key, fname in (("ToggleUp", "gatekeeper_toggle_up.png"), ("ToggleDown", "gatekeeper_toggle_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.80, outer=0.98)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "gatekeeper_led_on.png"), ("LedOff", "gatekeeper_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "gatekeeper_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    hidden = (colls["SwitchDown"], colls["LedOff"], colls["ToggleDown"])
    for c in groups: c.hide_render = c in hidden
    for c in hidden: c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "gatekeeper.blend"))
    print("[pedal] done")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
