"""
Slow Burn - photoreal Blender render (original design for the Virtual Pedalboard).
Gloss black lacquer (clear coat, a few edge chips to bare aluminium, boot wear around the footswitch). Michael's
candle-and-sun artwork (Assets/slowburn_art.png, black background already alpha) UV-printed on the left - its
"SLOW BURN" lettering is the pedal's name. A 12AX7 stands upright in a chrome-framed window on the right: thin
glass envelope, silvered getter dome at the top, bakelite base at the bottom, dark ribbed plates, mica spacers and
glowing heaters. Cream labels, burnt-orange "12AX7 TUBE DRIVE" under the window. Six knobs in two rows
(Gain/Presence/Volume big, Bass/Middle/Treble small: black knurled skirts, gloss black caps, cream pointers),
a chrome bat-handle DEEP toggle left of the footswitch, the LED right of it. Uses pedal_render_common.py.

Writes Assets/SlowBurn/: slowburn_face.png (heaters dim), slowburn_knob_strip.png (8-column grid),
slowburn_switch_up/down.png, slowburn_led_on/off.png, slowburn_tube_on/off.png (the window, glow baked; the
plugin draws "on" while the pedal is active), slowburn_toggle_up/down.png, and saves Tools/Blender/slowburn.blend.
The knob strip is rendered once at the big-knob size; the plugin scales it down for the small knobs.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_slowburn.py
Options after "--":   --quick   |   --hdri=NAME.exr

Positions MUST match Source/UI/FaceLayout.h (6 knobs + toggle = the Slow Burn branch) and SlowBurnFace
(Source/Faces/PedalFaces.cpp). Pads MUST match RenderedFace / SlowBurnFace (tubePad, togglePad).
The layout part of this file imports without Blender (used to make placeholder images for alignment checks).
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "SlowBurn")
TMP = os.path.join(HERE, "_frames_slowburn")
ART_IMAGE = os.path.join(ROOT, "Assets", "slowburn_art.png")
FONT_LABEL_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

W, H = 91.0, 120.0
UI_BODY_PX = 226.0
UI_BODY_PX_H = 298.0
MM_PER_PX = W / UI_BODY_PX
KNOB_PAD, SWITCH_PAD, LED_PAD = 1.30, 1.35, 2.6
TUBE_PAD, TOGGLE_PAD = 1.10, 1.30                       # = SlowBurnFace::tubePad / togglePad

# Albedos darker/more saturated than the target look (AgX lifts and desaturates)
GLOSS_BLACK = (0.002, 0.002, 0.0022, 1)       # quick render 1 (0.0045, spec 0.5, coat 1.0) read charcoal, sRGB ~78
CREAM_INK = (0.86, 0.62, 0.30, 1)                      # target sRGB ~235,206,160 (the artwork's cream); AgX greys warm inks
ORANGE_INK = (0.62, 0.055, 0.008, 1)                   # target ~208,66,23 (the artwork's burnt orange)
STEEL_REFERENCE_TARGET = 0.74                          # same exposure basis as the other pedals
HEATER_ON, HEATER_OFF = 14.0, 3.0                      # heater emission strength (38 burned out to white)
GLOW_COLOUR = (1.0, 0.36, 0.07)

# ----------------------------------------------------------------------------- layout (= FaceLayout.h, 6 knobs + toggle)
def fx(f): return -W / 2 + f * W
def fy(f): return H / 2 - f * H
KNOB_D_BIG, KNOB_D_SMALL = W * 0.215, W * 0.15
KNOB_TOP = (0.045, 0.262)                               # fraction of H: top row, bottom row
KNOB_CX = [0.22, 0.50, 0.78]
KNOB_LABELS = [["GAIN", "PRESENCE", "VOLUME"], ["BASS", "MIDDLE", "TREBLE"]]
def knob_cy_frac(row): return KNOB_TOP[row] + ((KNOB_D_BIG, KNOB_D_SMALL)[row] / H) * 0.5
def label_cy_frac(row):  # label rect: knob bottom + 1 px, 13 px tall
    return KNOB_TOP[row] + (KNOB_D_BIG, KNOB_D_SMALL)[row] / H + 7.5 / UI_BODY_PX_H
ART_C, ART_WH = (0.31, 0.60), (W * 0.316, H * 0.36)    # printed artwork (2:3), mm
WIN_C, WIN_WH = (0.72, 0.60), (W * 0.20, H * 0.34)    # the valve window (upright), mm
WIN_R = min(WIN_WH) * 0.22                             # bezel corner radius
SUB_C, SUB_WH = (0.72, 0.795), (0.40, 0.030)
SW_D = W * 0.19
SW_CY_FRAC = 0.895
LED_D = 11.0 / UI_BODY_PX * W
LED_CX_FRAC, LED_CY_FRAC = 0.80, 0.895
TOG_C, TOG_WH = (0.20, 0.905), (W * 0.10, W * 0.16)
TOG_LABEL_C, TOG_LABEL_WH = (0.20, 0.812), (0.24, 0.032)
def rect_center(r): return fx(r[0] + r[2] / 2), fy(r[1] + r[3] / 2)

def rounded_rect_pts(x0, y0, x1, y1, r, n=16):
    pts = []
    corners = [(x1 - r, y1 - r, 0.0), (x1 - r, y0 + r, 0.5 * math.pi), (x0 + r, y0 + r, math.pi), (x0 + r, y1 - r, 1.5 * math.pi)]
    for cx, cy, a0 in corners:                          # clockwise from the top-right corner
        for i in range(n + 1):
            a = a0 + 0.5 * math.pi * i / n
            pts.append((cx + math.sin(a) * r, cy + math.cos(a) * r))
    return pts

def rounded_ring(x0, y0, x1, y1, r, w, n=16):
    """Outline of a rounded rectangle stroked with width w, as one polygon with a slit."""
    outer = rounded_rect_pts(x0 - w / 2, y0 - w / 2, x1 + w / 2, y1 + w / 2, r + w / 2, n)
    inner = rounded_rect_pts(x0 + w / 2, y0 + w / 2, x1 - w / 2, y1 - w / 2, max(0.01, r - w / 2), n)
    return outer + [outer[0]] + [inner[0]] + list(reversed(inner))[:-1] + [inner[0]]

def window_rect():
    cx, cy = fx(WIN_C[0]), fy(WIN_C[1])
    return cx - WIN_WH[0] / 2, cy - WIN_WH[1] / 2, cx + WIN_WH[0] / 2, cy + WIN_WH[1] / 2

# ----------------------------------------------------------------------------- materials (Blender only)
def mat_print(name, path, ref_obj):
    """Full-colour UV print on the lacquer: the image's colour and alpha, satin ink a touch rougher than the coat."""
    import bpy
    m, nt, p, g = C.new_material(name)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    g.l(tex.outputs["Color"], C.inp(p, "Base Color"))
    g.l(tex.outputs["Alpha"], C.inp(p, "Alpha"))
    co = C.body_coords(g, ref_obj)
    g.l(g.ramp(g.noise(co, 1.2, detail=6), [(0.3, 0.42), (0.7, 0.55)]), C.inp(p, "Roughness"))
    C.set_in(p, ["Specular IOR Level", "Specular"], 0.15)
    C.set_in(p, ["Coat Weight", "Clearcoat"], 0.45)          # printed under the same clear coat as the paint
    return m

def art_plane(mat):
    import bmesh
    bm = bmesh.new()
    cx, cy, hw, hh = fx(ART_C[0]), fy(ART_C[1]), ART_WH[0] / 2, ART_WH[1] / 2
    vs = [bm.verts.new(v) for v in ((cx - hw, cy - hh, 0), (cx + hw, cy - hh, 0), (cx + hw, cy + hh, 0), (cx - hw, cy + hh, 0))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): loop[uv].uv = t
    return C.mesh_obj("ArtPrint", bm, mat)

def mat_glass(name):
    m, nt, p, g = C.new_material(name)
    C.set_in(p, "Base Color", (0.97, 0.98, 1.0, 1))
    C.set_in(p, ["Transmission Weight", "Transmission"], 1.0)
    C.set_in(p, "Roughness", 0.02); C.set_in(p, "IOR", 1.47)
    return m

def mat_emit(name, colour, strength):
    m, nt, p, g = C.new_material(name)
    C.set_in(p, "Base Color", (0.05, 0.02, 0.01, 1))
    C.set_in(p, ["Emission Color", "Emission"], colour + (1.0,))
    C.set_in(p, "Emission Strength", strength)
    return m

# ----------------------------------------------------------------------------- the valve
def valve(colls_on_off, mats, z_axis):
    """A 12AX7 lying along +x (base at -x, getter dome at +x), centred on the origin; the caller parents it to a
    pivot at the window centre turned 90 deg so it stands upright. Heaters go in the TubeOn / TubeOff collections."""
    import bpy, bmesh
    long_, short = max(WIN_WH), min(WIN_WH)
    inset = short * 0.075
    in_w, in_h = long_ - 2 * inset, short - 2 * inset
    r = in_h * 0.36                                    # glass radius
    L = in_w * 0.84                                    # glass length incl. dome
    cx, cy = in_w * 0.02, 0.0
    gx0, gx1 = cx - L / 2, cx + L / 2 - r              # cylinder part; dome beyond gx1
    parts = []

    def along_x(o):
        o.rotation_euler = (0, math.radians(90), 0); return o

    # thin glass shell (outer surface + 0.3 mm wall): a single closed surface would render as solid glass
    def lathe(name, prof, mat, wall=None):
        bm = bmesh.new()
        vs = [bm.verts.new((x, 0.0, rho)) for x, rho in prof]
        es = [bm.edges.new((a, b)) for a, b in zip(vs, vs[1:])]
        bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(1, 0, 0), steps=72, angle=2 * math.pi)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        o = C.mesh_obj(name, bm, mat); C.smooth(o)
        if wall:
            sm = o.modifiers.new("Wall", "SOLIDIFY"); sm.thickness = wall; sm.offset = -1.0
        o.location = (0.0, cy, z_axis)
        return o
    prof = [(gx0 - 0.01, 0.0), (gx0, r * 0.80), (gx0 + 0.25, r * 0.95), (gx0 + 0.9, r)]
    prof += [(gx1 + r * math.sin(a), r * math.cos(a)) for a in [math.radians(d) for d in range(0, 91, 6)]]
    parts.append(lathe("Glass", prof, mats["glass"], wall=0.3))
    gr = r - 0.34                                                       # silver getter flash inside the dome
    gprof = [(gx1 - r * 0.45, gr)] + [(gx1 + gr * math.sin(a), gr * math.cos(a)) for a in [math.radians(d) for d in range(0, 91, 6)]]
    parts.append(lathe("Getter", gprof, mats["getter"], wall=0.05))
    base = along_x(C.cylinder("Base", r * 1.05, in_w * 0.06, z0=-in_w * 0.03, verts=64, mat=mats["bakelite"]))
    base.location = (gx0 - in_w * 0.03, cy, z_axis); C.bevel(base, 0.4, 3); parts.append(base)
    for i, fx_ in enumerate((0.22, 0.49, 0.76)):                       # mica spacers
        x = gx0 + (gx1 + r - gx0) * fx_
        o = along_x(C.cylinder(f"Mica{i}", r * 0.88, 0.35, z0=-0.175, verts=48, mat=mats["mica"]))
        o.location = (x, cy, z_axis); parts.append(o)
    for i, dy in enumerate((-0.42, 0.42)):                              # support rods
        o = along_x(C.cylinder(f"Rod{i}", 0.22, L * 0.82, z0=-L * 0.41, verts=16, mat=mats["rod"]))
        o.location = (cx - r * 0.3, cy + dy * r, z_axis + r * 0.25); parts.append(o)
    pw, ph, pz = (gx1 + r - gx0) * 0.20, r * 0.62, r * 0.85
    gap = r * 0.20
    heaters = {k: [] for k in colls_on_off}
    for k, fxc in enumerate((0.36, 0.62)):                              # two triodes
        x = gx0 + (gx1 + r - gx0) * fxc
        for sgn in (-1, 1):                                             # plate halves, gap at the axis
            o = C.box(f"Plate{k}{'ab'[sgn > 0]}", pw, ph, pz,
                      center=(x, cy + sgn * (gap / 2 + ph / 2), z_axis), mat=mats["plate"])
            C.bevel(o, 0.15, 2); parts.append(o)
            for j in (1, 2):                                            # pressed ribs along each plate
                rib = C.box(f"Rib{k}{'ab'[sgn > 0]}{j}", 0.45, ph * 0.92, pz + 0.35,
                            center=(x - pw / 2 + pw * j / 3, cy + sgn * (gap / 2 + ph / 2), z_axis), mat=mats["plate"])
                parts.append(rib)
        for key in colls_on_off:
            h = along_x(C.cylinder(f"Heater{k}{key}", gap * 0.40, pw * 0.86, z0=-pw * 0.43, verts=16,
                                   mat=mats["heater_" + key]))
            h.location = (x, cy, z_axis + pz * 0.15); heaters[key].append(h)
    return parts, heaters

# ----------------------------------------------------------------------------- build
def build(scene):
    import bpy
    colls = {k: bpy.data.collections.new(k) for k in
             ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff", "TubeOn", "TubeOff",
              "ToggleUp", "ToggleDown", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    face = colls["Face"]

    sx, sy = fx(0.5), fy(SW_CY_FRAC)
    body = C.enclosure("Enclosure", W, H, 30.0, 3.5, None)
    paint = C.mat_powder_coat("GlossBlack", GLOSS_BLACK, body, scuff_center=(sx, sy),
                              rough_base=0.45, spec=0.12, coat=0.45)   # clear coat over black (1.0 + spec 0.5 = grey)
    body.data.materials.append(paint)
    face.objects.link(body)
    steel_ref = C.mat_brushed_steel(body, scuff_center=None)        # exposure reference only

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    satin = C.mat_metal("SatinMetal", (0.62, 0.63, 0.65, 1), 0.26, smudges=0.1)
    screw_metal = C.mat_metal("ScrewMetal", (0.74, 0.74, 0.76, 1), 0.25, smudges=0.06)
    cream = C.mat_ink("InkCream", CREAM_INK, body, chip_amount=0.35)
    orange = C.mat_ink("InkOrange", ORANGE_INK, body, chip_amount=0.35)
    knob_skirt = C.mat_plastic("KnobSkirt", (0.008, 0.008, 0.009, 1), rough=0.45, spec=0.3, smudges=0.06)
    knob_cap = C.mat_plastic("KnobCapGloss", (0.006, 0.006, 0.007, 1), rough=0.18, spec=0.45, coat=0.6, smudges=0.05)
    pointer = C.mat_simple("PointerCream", CREAM_INK, rough=0.45)
    recess = C.mat_simple("Recess", (0.022, 0.017, 0.012, 1), rough=0.8, spec=0.2)
    vmats = dict(glass=mat_glass("Glass"), getter=C.mat_metal("Getter", (0.80, 0.80, 0.82, 1), 0.04, smudges=0.0),
                 bakelite=C.mat_plastic("Bakelite", (0.02, 0.012, 0.008, 1), rough=0.35, spec=0.4, smudges=0.0),
                 mica=C.mat_simple("Mica", (0.55, 0.50, 0.42, 1), rough=0.6),
                 rod=C.mat_metal("Rod", (0.6, 0.6, 0.62, 1), 0.3, smudges=0.0),
                 plate=C.mat_metal("Plate", (0.07, 0.068, 0.066, 1), 0.48, smudges=0.0),
                 heater_TubeOn=mat_emit("HeaterOn", GLOW_COLOUR, HEATER_ON),
                 heater_TubeOff=mat_emit("HeaterOff", GLOW_COLOUR, HEATER_OFF))

    inset = 9.0 / UI_BODY_PX * W
    for i, (ax, ay) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        C.phillips_screw(f"Screw{i}", ax * (W / 2 - inset), ay * (H / 2 - inset), 1.7,
                         [0.3, 1.0, 0.6, 1.4][i], screw_metal, face, colls["Cutters"])

    # window: hole through the lid, dark recess, chrome bezel
    x0, y0, x1, y1 = window_rect()
    win_in = min(WIN_WH) * 0.075
    depth = 14.0
    hole = C.flat_shape("WindowHole", rounded_rect_pts(x0 + win_in, y0 + win_in, x1 - win_in, y1 - win_in, WIN_R * 0.7),
                        None, thickness=depth + 2.0)
    hole.location = (0, 0, -depth); colls["Cutters"].objects.link(hole)
    b = body.modifiers.new("Window", "BOOLEAN"); b.operation = "DIFFERENCE"; b.object = hole
    try: b.solver = "EXACT"
    except Exception: pass
    floor = C.box("RecessFloor", WIN_WH[0] - 2 * win_in, WIN_WH[1] - 2 * win_in, 0.5,
                  center=((x0 + x1) / 2, (y0 + y1) / 2, -depth + 0.85), mat=recess)
    face.objects.link(floor)
    bezel = C.flat_shape("Bezel", rounded_rect_pts(x0, y0, x1, y1, WIN_R), chrome, thickness=1.6)
    cut = C.flat_shape("BezelCut", rounded_rect_pts(x0 + win_in, y0 + win_in, x1 - win_in, y1 - win_in, WIN_R * 0.7),
                       None, thickness=6.0)
    cut.location = (0, 0, -2.0); colls["Cutters"].objects.link(cut)
    bb = bezel.modifiers.new("Open", "BOOLEAN"); bb.operation = "DIFFERENCE"; bb.object = cut
    try: bb.solver = "EXACT"
    except Exception: pass
    C.bevel(bezel, 0.45, 3, 40); C.smooth(bezel)
    face.objects.link(bezel)
    parts, heaters = valve(("TubeOn", "TubeOff"), vmats, z_axis=-depth * 0.48)
    vpiv = bpy.data.objects.new("ValvePivot", None); face.objects.link(vpiv)
    vpiv.location = ((x0 + x1) / 2, (y0 + y1) / 2, 0.0)
    vpiv.rotation_euler = (0, 0, math.radians(90))                     # +x (getter dome) points up
    for o in parts: face.objects.link(o); o.parent = vpiv
    for key, hs in heaters.items():
        for o in hs: colls[key].objects.link(o); o.parent = vpiv

    # printing: the artwork (UV print), cream labels, orange subtitle
    label_font = next((bpy.data.fonts.load(p) for p in FONT_LABEL_CANDIDATES if os.path.exists(p)), None)
    if os.path.exists(ART_IMAGE):
        o = art_plane(mat_print("ArtPrint", ART_IMAGE, body)); o.location = (0, 0, 0.005); face.objects.link(o)
    C.text_obj("Sub", "12AX7 TUBE DRIVE", label_font, orange,
               (fx(SUB_C[0]), fy(SUB_C[1]), SUB_WH[0] * W * 0.86, SUB_WH[1] * H * 0.75), face, spacing=1.2)
    C.text_obj("DeepLabel", "DEEP", label_font, cream,
               (fx(TOG_LABEL_C[0]), fy(TOG_LABEL_C[1]), TOG_LABEL_WH[0] * W * 0.6, TOG_LABEL_WH[1] * H * 0.75), face, spacing=1.2)
    for row in range(2):
        for i, (label, cxf) in enumerate(zip(KNOB_LABELS[row], KNOB_CX)):
            C.text_obj(f"Label{row}{i}", label, label_font, cream,
                       (fx(cxf), fy(label_cy_frac(row)), W * 0.24, 13.0 / UI_BODY_PX_H * H * 0.75), face, spacing=1.05)

    # LED
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

    # DEEP mini toggle: washer, hex nut, threaded bushing, chrome bat lever tilted up (ON) or down
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
                       window=((x0 + x1) / 2, (y0 + y1) / 2), body=body, paint=paint, steel_ref=steel_ref)

# ----------------------------------------------------------------------------- post
def window_mask(a):
    """Alpha = the bezel's rounded rectangle (antialiased); the crop is TUBE_PAD x the window."""
    import numpy as np
    h, w = a.shape[:2]
    ppmm = w / (WIN_WH[0] * TUBE_PAD)
    yy, xx = np.mgrid[0:h, 0:w]
    x = (xx + 0.5 - w / 2) / ppmm; y = (yy + 0.5 - h / 2) / ppmm
    hx, hy = WIN_WH[0] / 2 - WIN_R, WIN_WH[1] / 2 - WIN_R
    dx = np.maximum(np.abs(x) - hx, 0); dy = np.maximum(np.abs(y) - hy, 0)
    d = np.hypot(dx, dy) - WIN_R + 0.15                 # mm outside the bezel edge (+ a hair of shadow)
    a[..., 3] *= np.clip(0.5 - d * ppmm, 0.0, 1.0)
    return a

def heater_glow(a, strength=1.5):
    """Warm bloom around the glowing heaters, inside the window only."""
    import numpy as np
    hot = np.clip((a[..., 0] - a[..., 2]) - 0.35, 0, None) * a[..., 3]
    glow = np.clip(C._blur(hot, max(a.shape[:2]) * 0.035) * strength * 3.0, 0, 0.85)
    for i, c in enumerate(GLOW_COLOUR):
        a[..., i] = a[..., i] * (1 - glow) + c * glow
    return a

# ----------------------------------------------------------------------------- render
def main():
    import bpy
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    scene = C.setup_scene(ST)
    scene.cycles.transmission_bounces = 12; scene.cycles.max_bounces = 16      # glass envelope
    C.world_hdri(scene, ST.hdri, rotation_deg=40.0)
    C.add_key_light(scene)
    C.add_softbox(scene)
    colls, P = build(scene)
    cam = C.Camera(scene, UI_BODY_PX / W * ST.oversample)
    groups = [colls[k] for k in ("Face", "Knob", "SwitchUp", "SwitchDown", "LedOn", "LedOff",
                                 "TubeOn", "TubeOff", "ToggleUp", "ToggleDown")]
    face_objs = list(colls["Face"].objects)

    def render_face(path):
        C.set_catcher(face_objs, False)
        C.show_only([colls["Face"], colls["TubeOff"]], groups)
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

    render_face(os.path.join(OUT, "slowburn_face.png"))

    # the valve window, heaters on / dim (face visible: same light, reflections and glass refraction)
    wx, wy = P["window"]
    cam.frame(wx, wy, WIN_WH[0] * TUBE_PAD, WIN_WH[1] * TUBE_PAD)
    for key, fname in (("TubeOn", "slowburn_tube_on.png"), ("TubeOff", "slowburn_tube_off.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        path = os.path.join(OUT, fname)
        C.render_to(scene, path)
        a = window_mask(C.load_rgba(path))
        if key == "TubeOn": a = heater_glow(a)
        C.save_rgba(a, path)

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
    C.stack_grid(paths, os.path.join(OUT, "slowburn_knob_strip.png"))
    scene.cycles.samples = ST.samples

    sx, sy = P["switch"]
    cam.frame(sx, sy, SW_D * SWITCH_PAD, SW_D * SWITCH_PAD)
    for key, fname in (("SwitchUp", "slowburn_switch_up.png"), ("SwitchDown", "slowburn_switch_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.78, outer=0.97)

    tx, ty = P["toggle"]
    cam.frame(tx, ty, TOG_WH[0] * TOGGLE_PAD, TOG_WH[1] * TOGGLE_PAD)
    for key, fname in (("ToggleUp", "slowburn_toggle_up.png"), ("ToggleDown", "slowburn_toggle_down.png")):
        C.show_only([colls["Face"], colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
        C.post_fade(os.path.join(OUT, fname), inner=0.80, outer=0.98)

    lx, ly = P["led"]
    cam.frame(lx, ly, LED_D * LED_PAD, LED_D * LED_PAD)
    C.set_catcher(face_objs, False)
    for key, fname in (("LedOn", "slowburn_led_on.png"), ("LedOff", "slowburn_led_off.png")):
        C.show_only([colls[key]], groups)
        C.render_to(scene, os.path.join(OUT, fname))
    C.bloom(os.path.join(OUT, "slowburn_led_on.png"))

    C.set_catcher(face_objs, False)
    P["pivot"].rotation_euler = (0, 0, 0)
    hidden = (colls["SwitchDown"], colls["LedOff"], colls["TubeOff"], colls["ToggleUp"])
    for c in groups: c.hide_render = c in hidden
    for c in hidden: c.hide_viewport = True
    cam.frame(0, 0, W, H)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "slowburn.blend"))
    print("[pedal] done")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
