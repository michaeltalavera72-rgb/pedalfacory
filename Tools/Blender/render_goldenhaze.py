"""
Golden Haze - photoreal Blender render (based on the Earthquake Devices Acapulco Gold; Michael's artwork).
Michael's full-face artwork (Assets/goldenhaze_art.png, made by Tools/Art/make_goldenhaze_art.py from his original
image: the golden sun and swirling haze over the mountains, "Golden Haze", "VOLUME", and the bottom line
"POWER AMP - DISTORTION - HIGHER GROUND") UV-printed edge to edge, 2.6 mm inside the edge of a worn gold
enclosure. The template's three painted knobs were painted out (the circuit has one knob); the real VOLUME knob,
LED and footswitch sit where the art's TONE knob, LED and footswitch were: a black knurled knob with a machined
black-metal cap and white pointer, an amber LED in a dark chrome bezel (like the art), a satin-silver/chrome
footswitch. Uses pedal_render_common.py.

Writes Assets/GoldenHaze/: goldenhaze_face.png, goldenhaze_knob_strip.png (8-column grid),
goldenhaze_switch_up/down.png, goldenhaze_led_on/off.png, and saves Tools/Blender/goldenhaze.blend.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_goldenhaze.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (numKnobs == 1 = the Golden Haze branch; fractions printed by
Tools/Art/make_goldenhaze_art.py) and GoldenHazeFace (Source/Faces/PedalFaces.cpp). Pads MUST match RenderedFace.
The layout part of this file imports without Blender (used for alignment checks).
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "GoldenHaze")
TMP = os.path.join(HERE, "_frames_goldenhaze")
ART_IMAGE = os.path.join(ROOT, "Assets", "goldenhaze_art.png")

W, H = 91.0, 91.0 * 372.0 / 226.0          # = plugin pedal body 226 x 372 px
UI_BODY_PX = 226.0
UI_BODY_PX_H = 372.0
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6
ART_INSET = 2.6                                         # mm (= FaceLayout::artInset * W)

# Albedos darker than the target look (AgX lifts and desaturates)
BRASS_BRIGHT = (0.62, 0.31, 0.05, 1)                  # aged brass enclosure: polished/worn areas ...
BRASS_TARNISH = (0.10, 0.055, 0.02, 1)                # ... and dark tarnish (quick 1: flat (0.30,0.19,0.045) metal read olive and
                                                      # even; quick 2: (0.55,0.32,0.07)/(0.11,0.07,0.025) patchy but still olive)
STEEL_REFERENCE_TARGET = 0.74                          # same exposure basis as the other pedals
PRINT_SAT, PRINT_VALUE, PRINT_HUE = 1.12, 1.00, 0.492   # quick 1 (1.25 / 0.86 / 0.5): mids ~10 % dark, S +6 %, hue +3 deg;
                                                         # quick 2 (1.12 / 0.96): hue exact, S +3 %, mids 3-5 % dark

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, 1 knob)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D = W * 0.2261                                     # VOLUME, on the art's painted (centre) knob
KNOB_C = (0.5000, 0.1573)
LED_D = 11.0 / UI_BODY_PX * W
LED_C = (0.6963, 0.8413)
SW_D = W * 0.19
SW_C = (0.4979, 0.8385)
LED_BLOOM = (1.0, 0.55, 0.08)                          # amber glow, like the art's LED

def mat_led_amber(name, on):
    """Amber LED like the art's: white-hot centre fading to saturated yellow-amber at the rim (radial emission).
    quick 1 (uniform (1, 0.45, 0.04) x 0.9) burnt out to pale peach; quick 2 (uniform (1, 0.30, 0) x 0.55) read salmon."""
    m, nt, p, g = C.new_material(name)
    C.set_in(p, "Base Color", (0.90, 0.45, 0.02, 1) if on else (0.07, 0.035, 0.003, 1))
    C.set_in(p, "Roughness", 0.06); C.set_in(p, ["Coat Weight", "Clearcoat"], 1.0)
    C.set_in(p, ["Transmission Weight", "Transmission"], 0.3)
    if on:
        tc = g.n("ShaderNodeTexCoord")
        flat = g.n("ShaderNodeVectorMath", operation="MULTIPLY"); flat.inputs[1].default_value = (1.0, 1.0, 0.0)
        g.l(tc.outputs["Object"], flat.inputs[0])
        ln = g.n("ShaderNodeVectorMath", operation="LENGTH"); g.l(flat.outputs[0], ln.inputs[0])
        t = g.remap(ln.outputs["Value"], 0.0, LED_D * 0.5, 1.0, 0.0)          # 1 = centre, 0 = rim
        hot = g.math("POWER", t, 2.2)
        col = g.mixc(hot, (1.0, 0.50, 0.0, 1), (1.0, 0.86, 0.55, 1))
        g.l(col, C.inp(p, ["Emission Color", "Emission"]))
        g.l(g.math("ADD", 0.30, g.math("MULTIPLY", hot, 3.0)), C.inp(p, "Emission Strength"))
    return m

# Amber colour grade for the lit LED image (after bloom). Cycles + AgX render any bright emissive lens as a pale
# cream (quick 3: lens luminance 0.69-0.88 everywhere), so the lens luminance is mapped onto an amber ramp like the
# art's LED: white-hot centre -> yellow -> amber rim. Tuned on quick 3's led_on.png (Tools: PIL preview).
LED_GRADE_STOPS = [(0.00, (0.30, 0.10, 0.00)), (0.30, (0.95, 0.55, 0.04)), (0.60, (1.00, 0.76, 0.15)),
                   (0.85, (1.00, 0.93, 0.62)), (1.00, (1.00, 1.00, 0.95))]

def amber_grade(path, lo=0.60, hi=0.90, amount=0.9):
    import numpy as np
    a = C.load_rgba(path)
    rgb = a[..., :3]
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    t = np.clip((L - lo) / (hi - lo), 0.0, 1.0)
    xs = [st[0] for st in LED_GRADE_STOPS]
    ramp = np.stack([np.interp(t, xs, [st[1][i] for st in LED_GRADE_STOPS]) for i in range(3)], -1)
    a[..., :3] = rgb * (1.0 - amount) + ramp * amount
    C.save_rgba(a, path)

def mat_aged_brass(name, ref_obj):
    """Worn gold/brass enclosure like the art's rim: patchy dark tarnish over brass, brighter where edges are worn."""
    m, nt, p, g = C.new_material(name)
    co = C.body_coords(g, ref_obj)
    tarnish = g.ramp(g.noise(co, 0.35, detail=8, distortion=0.3), [(0.45, 0.0), (0.70, 1.0)])
    col = g.mixc(tarnish, BRASS_BRIGHT, BRASS_TARNISH)
    worn = g.math("MULTIPLY", C.edge_mask(g, 2.0), 0.6)
    col = g.mixc(worn, col, (0.70, 0.40, 0.08, 1))
    g.l(col, C.inp(p, "Base Color"))
    C.set_in(p, "Metallic", 1.0)
    rough = g.math("ADD", 0.30, g.math("MULTIPLY", tarnish, 0.30))
    rough = g.math("ADD", rough, g.math("MULTIPLY", g.noise(co, 8.0, detail=6), 0.06))
    g.l(rough, C.inp(p, "Roughness"))
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
    C.set_in(hs, "Saturation", PRINT_SAT); C.set_in(hs, "Value", PRINT_VALUE); C.set_in(hs, "Hue", PRINT_HUE)
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
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(SW_C[0]), fy(SW_C[1])
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = mat_aged_brass("AgedBrass", body)
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
        lens = C.dome(f"Lens{key}", LED_D * 0.5, 0.55, mat_led_amber(f"Led{key}", on), segs=48)
        lens.location = (lx, ly, 1.2); colls[key].objects.link(lens)

    # the VOLUME knob
    kx, ky = fx(KNOB_C[0]), fy(KNOB_C[1])
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

    render_face(os.path.join(OUT, "goldenhaze_face.png"))

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
    C.stack_grid(paths, os.path.join(OUT, "goldenhaze_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "goldenhaze_switch_up.png"), ("SwitchDown", "goldenhaze_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "goldenhaze_led_on.png"), ("LedOff", "goldenhaze_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "goldenhaze_led_on.png"), colour=LED_BLOOM)
    amber_grade(os.path.join(OUT, "goldenhaze_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    hidden = (colls["SwitchDown"], colls["LedOff"])
    for c in groups: c.hide_render = c in hidden
    for c in hidden: c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "goldenhaze.blend"))
    print("[pedal] done")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
