"""
Shared photoreal rendering library for Virtual Pedalboard pedals (Blender 4.2+ / 5.x, Cycles).

Each pedal has its own small script (e.g. render_ramhorn.py) that builds its geometry and
calls into this module for lighting, materials, wear, render settings and image output.

Realism features:
  * Studio HDRI lighting from Blender's bundled studio lights (falls back to a procedural sky)
    plus a soft key light so shadows always fall down-right like the plugin's drop shadows.
  * AgX colour management and automatic exposure (every pedal lands at the same brightness).
  * Materials with layered wear: brushed steel (anisotropic, finger smudges, fine scratches,
    worn edges, scuffing around the footswitch), satin printed ink with thickness and tiny chips,
    satin knob plastic with a glossier cap, chrome, satin hardware.
  * Parts (knobs, footswitch) are rendered over the enclosure as a shadow catcher, so they
    pick up its bounce light and reflections and cast soft contact shadows.
  * 4x plugin resolution, high sample count with denoising, LED bloom.
"""
import bpy, bmesh, math, os, sys, warnings
import numpy as np

# ----------------------------------------------------------------------------- render settings
class Settings:
    def __init__(self, argv):
        args = argv[argv.index("--") + 1:] if "--" in argv else []
        self.quick = "--quick" in args
        self.samples = 32 if self.quick else 512
        # knob frames are small, dark and denoised: 128 samples looks the same and is ~4x faster
        # (512 made the 64 knob frames ~50 of a 60-minute CPU render)
        self.knob_samples = 32 if self.quick else 128
        self.knob_frames = 16 if self.quick else 64
        self.oversample = 4                       # images are 4x the plugin's pixel size
        self.hdri = "studio.exr"
        for a in args:
            if a.startswith("--hdri="): self.hdri = a.split("=", 1)[1]
        self.target_brightness = 0.71             # mean display value of the enclosure face

def setup_scene(st):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples = st.samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.005
    s.cycles.use_denoising = True
    try: s.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.render.film_transparent = True
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    s.render.image_settings.color_depth = "8"
    set_view_transform(s)
    use_gpu(s)
    return s

def set_view_transform(s):
    for vt in ("AgX", "Filmic", "Standard"):
        try: s.view_settings.view_transform = vt; break
        except Exception: continue
    for look in ("AgX - Punchy", "AgX - High Contrast", "AgX - Medium High Contrast", "None"):
        try: s.view_settings.look = look; break
        except Exception: continue
    s.view_settings.exposure = 0.0
    print(f"[pedal] view transform: {s.view_settings.view_transform} / {s.view_settings.look}")

def use_gpu(scene):
    try: prefs = bpy.context.preferences.addons["cycles"].preferences
    except Exception: return
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices: d.use = d.type in (kind, "CPU")
                scene.cycles.device = "GPU"
                print(f"[pedal] rendering on GPU ({kind})"); return
        except Exception: continue
    print("[pedal] rendering on CPU")

# ----------------------------------------------------------------------------- node helpers
def _nodes_on(idblock):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        idblock.use_nodes = True

def set_in(node, names, value):
    for n in ([names] if isinstance(names, str) else names):
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False

def inp(node, names):
    for n in ([names] if isinstance(names, str) else names):
        if n in node.inputs: return node.inputs[n]
    return None

class G:
    """Tiny helper for building node graphs."""
    def __init__(self, nt): self.nt = nt
    def n(self, kind, **props):
        node = self.nt.nodes.new(kind)
        for k, v in props.items(): setattr(node, k, v)
        return node
    def l(self, a, b):
        if a is not None and b is not None: self.nt.links.new(a, b)
    def math(self, op, a, b=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): m.inputs[i].default_value = v
            else: self.l(v, m.inputs[i])
        return m.outputs[0]
    def remap(self, v, a, b, c=0.0, d=1.0):
        mr = self.n("ShaderNodeMapRange")
        for k, x in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)): mr.inputs[k].default_value = x
        self.l(v, mr.inputs["Value"]); return mr.outputs["Result"]
    def ramp(self, fac, stops):
        """stops: [(position, value_or_rgba), ...] (2+). Returns Color output."""
        r = self.n("ShaderNodeValToRGB")
        el = r.color_ramp.elements
        while len(el) < len(stops): el.new(0.5)
        for e, (p, v) in zip(el, stops):
            e.position = p
            e.color = v if isinstance(v, tuple) else (v, v, v, 1.0)
        self.l(fac, r.inputs["Fac"])
        return r.outputs["Color"]
    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0, map_scale=None, map_rot=None):
        src = vec
        if map_scale is not None or map_rot is not None:
            mp = self.n("ShaderNodeMapping")
            if map_scale is not None: mp.inputs["Scale"].default_value = map_scale
            if map_rot is not None: mp.inputs["Rotation"].default_value = map_rot
            self.l(vec, mp.inputs["Vector"]); src = mp.outputs["Vector"]
        nz = self.n("ShaderNodeTexNoise")
        set_in(nz, "Scale", scale); set_in(nz, "Detail", detail)
        set_in(nz, "Roughness", rough); set_in(nz, "Distortion", distortion)
        self.l(src, nz.inputs["Vector"])
        return nz.outputs["Fac"]
    def mixf(self, fac, a, b):
        m = self.n("ShaderNodeMix", data_type="FLOAT")
        for sock, v in ((m.inputs[0], fac), (m.inputs[2], a), (m.inputs[3], b)):
            if isinstance(v, (int, float)): sock.default_value = v
            else: self.l(v, sock)
        return m.outputs[0]
    def mixc(self, fac, a, b, blend="MIX"):
        m = self.n("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        for sock, v in ((m.inputs[0], fac), (m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(v, (int, float)): sock.default_value = v
            elif isinstance(v, tuple): sock.default_value = v
            else: self.l(v, sock)
        return m.outputs[2]

def new_material(name):
    m = bpy.data.materials.new(name)
    _nodes_on(m)
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    return m, nt, p, G(nt)

def body_coords(g, ref_obj):
    """Object-space coordinates of the enclosure (mm), shared by every material on the pedal."""
    tc = g.n("ShaderNodeTexCoord")
    if ref_obj is not None: tc.object = ref_obj
    return tc.outputs["Object"]

# ----------------------------------------------------------------------------- wear masks
def smudge_mask(g, co, amount=1.0):
    """Soft finger smudges: sparse blotches ~10-15 mm across."""
    n1 = g.noise(co, 0.07, detail=3, distortion=0.6)
    n2 = g.noise(co, 0.6, detail=6)
    blob = g.ramp(n1, [(0.66, 0.0), (0.76, 1.0)])
    tex = g.ramp(n2, [(0.35, 0.5), (0.65, 1.0)])
    return g.math("MULTIPLY", g.math("MULTIPLY", blob, tex), amount)

def scratch_mask(g, co, amount=1.0):
    """Fine random scratches in patches."""
    out = None
    for i, ang in enumerate((12, 71, 133, -38, 101)):
        f = g.noise(co, 1.6 + 0.3 * i, detail=1.5,
                    map_scale=(0.04, 3.5, 1.0), map_rot=(0, 0, math.radians(ang)))
        line = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", f, 0.5)), [(0.0, 1.0), (0.006, 0.0)])
        patch = g.ramp(g.noise(co, 0.05 + 0.01 * i, detail=2), [(0.55, 0.0), (0.66, 1.0)])
        s = g.math("MULTIPLY", line, patch)
        out = s if out is None else g.math("MAXIMUM", out, s)
    return g.math("MULTIPLY", out, amount)

def scuff_mask(g, co, center, inner=7.0, outer=26.0, amount=1.0):
    """Wear that increases near a point (e.g. around the footswitch)."""
    vm = g.n("ShaderNodeVectorMath", operation="DISTANCE")
    vm.inputs[1].default_value = (center[0], center[1], 0.0)
    g.l(co, vm.inputs[0])
    mr = g.n("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = inner; mr.inputs["From Max"].default_value = outer
    mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
    g.l(vm.outputs["Value"], mr.inputs["Value"])
    grain = g.ramp(g.noise(co, 0.35, detail=4, distortion=0.2), [(0.4, 0.2), (0.7, 1.0)])
    return g.math("MULTIPLY", g.math("MULTIPLY", mr.outputs["Result"], grain), amount)

def edge_mask(g, radius=1.2):
    """1 on rounded edges, 0 on flat faces (Cycles Bevel trick)."""
    bv = g.n("ShaderNodeBevel"); set_in(bv, "Radius", radius)
    geo = g.n("ShaderNodeNewGeometry")
    dot = g.n("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.l(bv.outputs["Normal"], dot.inputs[0]); g.l(geo.outputs["Normal"], dot.inputs[1])
    return g.ramp(dot.outputs["Value"], [(0.90, 1.0), (0.995, 0.0)])

# ----------------------------------------------------------------------------- materials
def mat_brushed_steel(ref_obj, scuff_center=None, tone=(0.62, 0.78)):
    m, nt, p, g = new_material("BrushedSteel")
    co = body_coords(g, ref_obj)
    streak = g.math("ADD",
                    g.math("MULTIPLY", g.noise(co, 4.0, detail=12, map_scale=(0.05, 2.5, 1.0)), 0.6),
                    g.math("MULTIPLY", g.noise(co, 7.0, detail=10, map_scale=(0.03, 3.0, 1.0)), 0.4))
    base = g.ramp(streak, [(0.3, (tone[0], tone[0] + 0.01, tone[0] + 0.02, 1)),
                           (0.7, (tone[1], tone[1] + 0.01, tone[1] + 0.02, 1))])
    rough = g.ramp(streak, [(0.3, 0.16), (0.7, 0.30)])
    smudge = smudge_mask(g, co, 1.0)
    scratch = scratch_mask(g, co, 1.0)
    edges = edge_mask(g, 3.0)
    scuff = scuff_mask(g, co, scuff_center) if scuff_center else None

    col = g.mixc(g.math("MULTIPLY", scratch, 0.55), base, (0.93, 0.93, 0.94, 1))
    col = g.mixc(g.math("MULTIPLY", edges, 0.12), col, (0.80, 0.80, 0.81, 1))
    r = g.math("ADD", rough, g.math("MULTIPLY", smudge, 0.05))
    r = g.mixf(g.math("MULTIPLY", scratch, 0.6), r, 0.08)
    r = g.math("ADD", r, g.math("MULTIPLY", edges, 0.5))
    if scuff is not None:
        col = g.mixc(g.math("MULTIPLY", scuff, 0.06), col, (0.55, 0.55, 0.56, 1))
        r = g.math("ADD", r, g.math("MULTIPLY", scuff, 0.04))
    g.l(col, inp(p, "Base Color"))
    g.l(g.math("MINIMUM", r, 0.9), inp(p, "Roughness"))
    set_in(p, "Metallic", 1.0)
    g.l(g.math("SUBTRACT", 0.8, g.math("MULTIPLY", smudge, 0.15)), inp(p, "Anisotropic"))
    tan = g.n("ShaderNodeTangent", direction_type="RADIAL", axis="Y")   # brushing runs left-right
    g.l(tan.outputs["Tangent"], inp(p, "Tangent"))
    return m

def mat_powder_coat(name, color, ref_obj, scuff_center=None, chip_metal=(0.70, 0.71, 0.73, 1),
                    rough_base=0.52, spec=0.30, coat=0.04):
    """Textured satin powder coat: fine orange-peel bump, slight colour variation, faint smudges,
    chipped edges showing bare aluminium, and wear near the footswitch.
    rough_base / spec / coat: defaults = Buzzsaw satin; higher roughness + less sheen = matte (Feral Hound)."""
    m, nt, p, g = new_material(name)
    co = body_coords(g, ref_obj)
    var = g.noise(co, 0.25, detail=4)
    col = g.mixc(g.math("MULTIPLY", g.ramp(var, [(0.3, 0.0), (0.7, 1.0)]), 0.18),
                 tuple(x * 0.85 for x in color[:3]) + (1.0,), tuple(min(1.0, x * 1.12) for x in color[:3]) + (1.0,))
    smudge = smudge_mask(g, co, 1.0)
    rough = g.math("ADD", rough_base, g.math("MULTIPLY", g.noise(co, 6.0, detail=8), 0.08))
    rough = g.math("SUBTRACT", rough, g.math("MULTIPLY", smudge, 0.10))        # finger grease is shinier
    # orange-peel texture
    peel = g.noise(co, 9.0, detail=6, rough=0.6)
    bump = g.n("ShaderNodeBump"); set_in(bump, "Strength", 0.12); set_in(bump, "Distance", 0.02)
    g.l(peel, inp(bump, "Height")); g.l(bump.outputs["Normal"], inp(p, "Normal"))
    set_in(p, ["Specular IOR Level", "Specular"], spec)      # less white sheen: keeps the colour saturated
    set_in(p, ["Coat Weight", "Clearcoat"], coat)
    # chips: only on worn edges (and a few near the footswitch)
    edges = edge_mask(g, 3.0)
    chipn = g.noise(co, 1.4, detail=10, distortion=0.4)
    chip = g.math("MULTIPLY", edges, g.ramp(chipn, [(0.67, 0.0), (0.70, 1.0)]))   # sparse: chips show strongly on dark paint
    if scuff_center is not None:
        sc = scuff_mask(g, co, scuff_center, inner=6.0, outer=20.0)
        col = g.mixc(g.math("MULTIPLY", sc, 0.25), col, tuple(x * 0.6 for x in color[:3]) + (1.0,))
        rough = g.math("SUBTRACT", rough, g.math("MULTIPLY", sc, 0.12))       # polished by boots
        chip = g.math("MAXIMUM", chip, g.math("MULTIPLY", sc, g.ramp(chipn, [(0.70, 0.0), (0.72, 1.0)])))
    g.l(col, inp(p, "Base Color")); g.l(rough, inp(p, "Roughness"))
    metal = nt.nodes.new("ShaderNodeBsdfPrincipled")
    set_in(metal, "Base Color", chip_metal); set_in(metal, "Metallic", 1.0); set_in(metal, "Roughness", 0.35)
    mix = nt.nodes.new("ShaderNodeMixShader"); out = nt.nodes.get("Material Output")
    g.l(chip, mix.inputs[0]); g.l(p.outputs[0], mix.inputs[1]); g.l(metal.outputs[0], mix.inputs[2])
    g.l(mix.outputs[0], out.inputs["Surface"])
    return m

def mat_metallic_paint(name, color, ref_obj, scuff_center=None, chip_metal=(0.70, 0.71, 0.73, 1),
                       metallic=0.75, coat=0.55, coat_rough=0.08, flake_scale=4.0, flake_tilt=0.35):
    """Metal-flake enamel under a clear coat: tinted metallic base with a fine sparkling flake bump,
    a smooth clear coat on top (with faint smudges), a few edge chips to bare aluminium and a dulled,
    slightly darker area of boot wear around the footswitch."""
    m, nt, p, g = new_material(name)
    co = body_coords(g, ref_obj)
    c = color[:3]
    var = g.ramp(g.noise(co, 0.12, detail=4), [(0.3, 0.0), (0.7, 1.0)])
    col = g.mixc(g.math("MULTIPLY", var, 0.25), tuple(x * 0.88 for x in c) + (1.0,), tuple(min(1.0, x * 1.10) for x in c) + (1.0,))
    # flakes: discrete ~0.25 mm Voronoi cells, each tilted randomly -> individual sparkles that catch
    # the softbox / key light at different angles (a noise bump this fine just averages out)
    vor = g.n("ShaderNodeTexVoronoi"); set_in(vor, "Scale", flake_scale)
    g.l(co, vor.inputs["Vector"])
    tilt = g.n("ShaderNodeVectorMath", operation="SUBTRACT"); g.l(vor.outputs["Color"], tilt.inputs[0])
    tilt.inputs[1].default_value = (0.5, 0.5, 0.5)
    sc = g.n("ShaderNodeVectorMath", operation="SCALE"); g.l(tilt.outputs[0], sc.inputs[0])
    set_in(sc, "Scale", flake_tilt)
    geo = g.n("ShaderNodeNewGeometry")
    add = g.n("ShaderNodeVectorMath", operation="ADD"); g.l(geo.outputs["Normal"], add.inputs[0]); g.l(sc.outputs[0], add.inputs[1])
    nrm = g.n("ShaderNodeVectorMath", operation="NORMALIZE"); g.l(add.outputs[0], nrm.inputs[0])
    g.l(nrm.outputs[0], inp(p, "Normal"))
    flakes = g.math("MULTIPLY", vor.outputs["Color"], 1.0)                     # per-flake random value
    set_in(p, "Metallic", metallic)
    g.l(g.math("ADD", 0.22, g.math("MULTIPLY", flakes, 0.16)), inp(p, "Roughness"))
    # a few flakes are brighter / more silvery
    col = g.mixc(g.ramp(flakes, [(0.80, 0.0), (0.95, 1.0)]), col, tuple(min(1.0, x * 2.2 + 0.03) for x in c) + (1.0,))
    set_in(p, ["Specular IOR Level", "Specular"], 0.35)
    # clear coat: smooth with faint orange peel and finger smudges
    set_in(p, ["Coat Weight", "Clearcoat"], coat)
    smudge = smudge_mask(g, co, 1.0)
    crough = g.math("ADD", coat_rough, g.math("MULTIPLY", smudge, 0.10))
    peel = g.noise(co, 6.0, detail=5, rough=0.6)
    cbump = g.n("ShaderNodeBump"); set_in(cbump, "Strength", 0.06); set_in(cbump, "Distance", 0.02)
    g.l(peel, inp(cbump, "Height"))
    try: g.l(cbump.outputs["Normal"], inp(p, ["Coat Normal", "Clearcoat Normal"]))
    except Exception: pass
    edges = edge_mask(g, 3.0)
    chipn = g.noise(co, 1.4, detail=10, distortion=0.4)
    chip = g.math("MULTIPLY", edges, g.ramp(chipn, [(0.69, 0.0), (0.71, 1.0)]))
    if scuff_center is not None:
        sc = scuff_mask(g, co, scuff_center, inner=6.0, outer=20.0)
        col = g.mixc(g.math("MULTIPLY", sc, 0.30), col, tuple(x * 0.65 for x in c) + (1.0,))
        crough = g.math("ADD", crough, g.math("MULTIPLY", sc, 0.25))          # coat scuffed dull by boots
        chip = g.math("MAXIMUM", chip, g.math("MULTIPLY", sc, g.ramp(chipn, [(0.71, 0.0), (0.73, 1.0)])))
    g.l(col, inp(p, "Base Color"))
    g.l(crough, inp(p, ["Coat Roughness", "Clearcoat Roughness"]))
    metal = nt.nodes.new("ShaderNodeBsdfPrincipled")
    set_in(metal, "Base Color", chip_metal); set_in(metal, "Metallic", 1.0); set_in(metal, "Roughness", 0.35)
    mix = nt.nodes.new("ShaderNodeMixShader"); out = nt.nodes.get("Material Output")
    g.l(chip, mix.inputs[0]); g.l(p.outputs[0], mix.inputs[1]); g.l(metal.outputs[0], mix.inputs[2])
    g.l(mix.outputs[0], out.inputs["Surface"])
    return m

def clear_zone_mask(g, co, zones):
    """1 everywhere except inside the given rectangles (cx, cy, half_w, half_h in object mm), where it
    fades to 0 - keeps rust and stains away from text that has to stay readable."""
    keep = None
    for cx, cy, hw, hh in zones:
        sep = g.n("ShaderNodeSeparateXYZ"); g.l(co, sep.inputs["Vector"])
        dx = g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", sep.outputs["X"], cx)), hw)
        dy = g.math("DIVIDE", g.math("ABSOLUTE", g.math("SUBTRACT", sep.outputs["Y"], cy)), hh)
        k = g.remap(g.math("MAXIMUM", dx, dy), 0.85, 1.25)       # 0 inside, soft 1 outside (clamped)
        keep = k if keep is None else g.math("MINIMUM", keep, k)
    return keep

def mat_rusty_paint(name, color, ref_obj, scuff_centers=(), rust=(0.035, 0.013, 0.005, 1),
                    style="blooms", clear_zones=()):
    """Weathered satin enamel with a real rust patina.
    Layers: mottled / sun-faded paint -> brown stain halo bleeding out around each rust area ->
    crusty rust (near-black core with bright orange grains) at the edges, in random patches and
    around the footswitches (boot wear) -> fine pitting specks over the whole face.
    style "blooms": round rust spots with ragged rims and orange flecks.
    style "streaks": long dark streaky patches (the look of the second Rail Bender preview).
    clear_zones: rectangles kept free of rust and stains (behind the name, etc.)."""
    m, nt, p, g = new_material(name)
    co = body_coords(g, ref_obj)
    c = color[:3]
    # paint: large soft mottling between a deeper and a faded tone
    var = g.ramp(g.noise(co, 0.05, detail=4, distortion=0.4), [(0.35, 0.0), (0.65, 1.0)])
    paint = g.mixc(var, tuple(x * 0.78 for x in c) + (1.0,), tuple(min(1.0, x * 1.18) for x in c) + (1.0,))
    # rust mask: edges + patches + boot wear, broken up by mid-frequency noise
    edges = edge_mask(g, 4.5)
    streaks = style == "streaks"
    if streaks:
        patches = g.ramp(g.noise(co, 0.08, detail=5, distortion=0.8), [(0.57, 0.0), (0.68, 1.0)])
    else:
        patches = g.ramp(g.noise(co, 0.06, detail=3, distortion=0.15), [(0.60, 0.0), (0.70, 1.0)])   # rounder blooms
    mask = g.math("MAXIMUM", edges, patches)
    for cen in scuff_centers:
        mask = g.math("MAXIMUM", mask, scuff_mask(g, co, cen, inner=6.0, outer=22.0))
    if clear_zones:
        mask = g.math("MULTIPLY", mask, clear_zone_mask(g, co, clear_zones))
    breakup = (g.noise(co, 1.4, detail=10, distortion=0.6) if streaks
               else g.noise(co, 2.2, detail=12, rough=0.7, distortion=0.3))             # ragged, bubbly rims
    m2 = g.math("MULTIPLY", mask, g.math("ADD", 0.35, g.math("MULTIPLY", breakup, 1.1)))
    stain = g.ramp(m2, [(0.18, 0.0), (0.50, 1.0)] if streaks else [(0.22, 0.0), (0.52, 1.0)])   # soft halo
    rmask = g.ramp(m2, [(0.48, 0.0), (0.58, 1.0)])      # the rust itself
    # fine pitting specks everywhere (tiny rust dots through the enamel)
    specks = g.ramp(g.noise(co, 3.2, detail=6), [(0.70, 0.0), (0.74, 1.0)])
    rmask = g.math("MAXIMUM", rmask, g.math("MULTIPLY", specks, 0.85))
    stained = (g.mixc(g.math("MULTIPLY", stain, 0.75), paint, (c[0] * 0.42, c[1] * 0.30, c[2] * 0.25, 1.0)) if streaks
               else g.mixc(g.math("MULTIPLY", stain, 0.85), paint, (c[0] * 0.55, c[1] * 0.42, c[2] * 0.30, 1.0)))
    grains = g.noise(co, 5.0, detail=10, rough=0.65)
    if streaks:
        rust_col = g.ramp(grains, [(0.35, rust), (0.55, (rust[0] * 3.2, rust[1] * 2.6, rust[2] * 1.6, 1.0)),
                                   (0.70, (0.26, 0.075, 0.012, 1.0))])
        g.l(g.mixc(rmask, stained, rust_col), inp(p, "Base Color"))
        return _rust_finish(g, p, co, rmask, stain, m)
    # rust: near-black core, warm brown body, scattered bright orange flecks
    core = g.ramp(m2, [(0.62, 0.0), (0.95, 1.0)])
    body = g.ramp(grains, [(0.30, (rust[0] * 3.0, rust[1] * 2.4, rust[2] * 1.6, 1.0)),
                           (0.55, (rust[0] * 4.5, rust[1] * 3.2, rust[2] * 1.8, 1.0)),
                           (0.66, (0.40, 0.12, 0.018, 1.0))])
    rust_col = g.mixc(g.math("MULTIPLY", core, 0.85), body, rust)
    g.l(g.mixc(rmask, stained, rust_col), inp(p, "Base Color"))
    return _rust_finish(g, p, co, rmask, stain, m)

def _rust_finish(g, p, co, rmask, stain, m):
    rough = g.mixf(stain, g.math("ADD", 0.50, g.math("MULTIPLY", g.noise(co, 6.0, detail=8), 0.10)), 0.68)
    g.l(g.mixf(rmask, rough, 0.92), inp(p, "Roughness"))
    set_in(p, ["Specular IOR Level", "Specular"], 0.28)
    set_in(p, ["Coat Weight", "Clearcoat"], 0.0)
    # raised, crusty rust + enamel orange-peel
    height = g.math("ADD", g.math("MULTIPLY", rmask, g.noise(co, 4.0, detail=12)), g.math("MULTIPLY", g.noise(co, 9.0, detail=6), 0.15))
    bump = g.n("ShaderNodeBump"); set_in(bump, "Strength", 0.35); set_in(bump, "Distance", 0.05)
    g.l(height, inp(bump, "Height")); g.l(bump.outputs["Normal"], inp(p, "Normal"))
    return m

def mat_ink(name, color, ref_obj, chip_amount=1.0):
    """Screen-printed ink: satin, slightly uneven, with tiny chips showing bare metal."""
    m, nt, p, g = new_material(name)
    co = body_coords(g, ref_obj)
    var = g.noise(co, 1.2, detail=6)
    c = g.mixc(g.math("MULTIPLY", g.ramp(var, [(0.3, 0.0), (0.7, 1.0)]), 0.12),
               color, tuple(min(1.0, x * 1.25) for x in color[:3]) + (1.0,))
    g.l(c, inp(p, "Base Color"))
    g.l(g.ramp(var, [(0.3, 0.72), (0.7, 0.85)]), inp(p, "Roughness"))
    set_in(p, ["Specular IOR Level", "Specular"], 0.03)
    if chip_amount > 0:
        chips = g.ramp(g.noise(co, 2.2, detail=10, distortion=0.3), [(0.735, 0.0), (0.745, 1.0)])
        metal = nt.nodes.new("ShaderNodeBsdfPrincipled")
        set_in(metal, "Base Color", (0.72, 0.73, 0.75, 1)); set_in(metal, "Metallic", 1.0)
        set_in(metal, "Roughness", 0.3)
        mix = nt.nodes.new("ShaderNodeMixShader")
        out = nt.nodes.get("Material Output")
        g.l(g.math("MULTIPLY", chips, chip_amount), mix.inputs[0])
        g.l(p.outputs[0], mix.inputs[1]); g.l(metal.outputs[0], mix.inputs[2])
        g.l(mix.outputs[0], out.inputs["Surface"])
    return m

def mat_plastic(name, color, rough=0.45, spec=0.3, coat=0.0, ref_obj=None, smudges=0.12):
    m, nt, p, g = new_material(name)
    set_in(p, "Base Color", color)
    set_in(p, ["Specular IOR Level", "Specular"], spec)
    set_in(p, ["Coat Weight", "Clearcoat"], coat)
    set_in(p, "Coat Roughness", 0.12)
    tc = g.n("ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    r = g.math("ADD", rough, g.math("MULTIPLY", smudge_mask(g, co, 1.0), smudges))
    r = g.math("ADD", r, g.math("MULTIPLY", g.noise(co, 3.0, detail=8), 0.05))
    g.l(r, inp(p, "Roughness"))
    return m

def mat_metal(name, color, rough, smudges=0.12):
    m, nt, p, g = new_material(name)
    set_in(p, "Base Color", color); set_in(p, "Metallic", 1.0)
    co = g.n("ShaderNodeTexCoord").outputs["Object"]
    r = g.math("ADD", rough, g.math("MULTIPLY", smudge_mask(g, co, 1.0), smudges))
    r = g.math("ADD", r, g.math("MULTIPLY", g.noise(co, 8.0, detail=6), 0.04))
    g.l(r, inp(p, "Roughness"))
    return m

def mat_led(name, on):
    m, nt, p, g = new_material(name)
    set_in(p, "Base Color", (0.9, 0.03, 0.01, 1) if on else (0.05, 0.003, 0.002, 1))
    set_in(p, "Roughness", 0.06); set_in(p, ["Coat Weight", "Clearcoat"], 1.0)
    set_in(p, ["Transmission Weight", "Transmission"], 0.3)
    if on:
        set_in(p, ["Emission Color", "Emission"], (1.0, 0.07, 0.02, 1))
        set_in(p, "Emission Strength", 0.9)
    return m

def mat_simple(name, color, rough=0.5, metallic=0.0, spec=0.5):
    m, nt, p, g = new_material(name)
    set_in(p, "Base Color", color); set_in(p, "Roughness", rough)
    set_in(p, "Metallic", metallic); set_in(p, ["Specular IOR Level", "Specular"], spec)
    return m

# ----------------------------------------------------------------------------- lighting
def find_hdri(name):
    roots = []
    try: roots.append(bpy.utils.system_resource("DATAFILES", path="studiolights/world"))
    except Exception: pass
    roots.append(os.path.join(os.path.dirname(bpy.app.binary_path),
                              f"{bpy.app.version[0]}.{bpy.app.version[1]}", "datafiles", "studiolights", "world"))
    for r in roots:
        if r and os.path.isdir(r):
            files = sorted(f for f in os.listdir(r) if f.lower().endswith((".exr", ".hdr")))
            print(f"[pedal] studio lights in {r}: {files}")
            for want in (name, "studio.exr", "interior.exr", "courtyard.exr"):
                if want in files: return os.path.join(r, want)
            if files: return os.path.join(r, files[0])
    return None

def world_hdri(scene, name, rotation_deg=40.0, strength=1.0):
    path = find_hdri(name)
    if path is None:
        print("[pedal] no studio HDRI found, using procedural sky"); world_procedural(scene); return
    print(f"[pedal] lighting with HDRI {path}")
    w = bpy.data.worlds.new("HDRI"); scene.world = w; _nodes_on(w)
    nt = w.node_tree; g = G(nt)
    bg = nt.nodes.get("Background")
    env = g.n("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(path)
    tc = g.n("ShaderNodeTexCoord"); mp = g.n("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rotation_deg))
    g.l(tc.outputs["Generated"], mp.inputs["Vector"]); g.l(mp.outputs["Vector"], env.inputs["Vector"])
    g.l(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength

def world_procedural(scene):
    w = bpy.data.worlds.new("Studio"); scene.world = w; _nodes_on(w)
    nt = w.node_tree; g = G(nt)
    bg = nt.nodes.get("Background")
    sep = g.n("ShaderNodeSeparateXYZ"); g.l(g.n("ShaderNodeTexCoord").outputs["Generated"], sep.inputs["Vector"])
    sky = g.ramp(g.remap(sep.outputs["Z"], -1, 1), [(0.45, (0.04, 0.04, 0.045, 1)), (0.8, (0.55, 0.56, 0.58, 1)), (1.0, (1, 1, 1, 1))])
    side = g.ramp(g.remap(sep.outputs["X"], -1, 1), [(0.5, (1, 1, 1, 1)), (1.0, (0.22, 0.22, 0.24, 1))])
    g.l(g.mixc(1.0, sky, side, blend="MULTIPLY"), bg.inputs["Color"])

def add_softbox(scene, size=320.0, height=220.0, strength=1.6, offset=(-15.0, 0.0), falloff=(0.25, 1.0)):
    """Large emissive panel above, visible only in glossy reflections (not to camera/diffuse).
    Brighter at the top-left edge and fading towards bottom-right: a gradient is what makes
    brushed metal show its grain (perfectly even light hides it)."""
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size * 0.5)
    m, nt, p, g = new_material("Softbox")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = g.n("ShaderNodeTexCoord")
    sep = g.n("ShaderNodeSeparateXYZ"); g.l(tc.outputs["Generated"], sep.inputs["Vector"])
    diag = g.math("MULTIPLY", g.math("ADD", g.math("SUBTRACT", 1.0, sep.outputs["X"]), sep.outputs["Y"]), 0.5)
    grad = g.math("ADD", falloff[0], g.math("MULTIPLY", g.math("POWER", diag, 1.5), falloff[1] - falloff[0]))
    g.l(g.math("MULTIPLY", grad, strength), em.inputs["Strength"])
    nt.links.new(em.outputs[0], nt.nodes.get("Material Output").inputs["Surface"])
    o = mesh_obj("Softbox", bm, m)
    o.location = (offset[0], offset[1], height); o.rotation_euler = (math.radians(180), 0, 0)   # facing down
    for attr, val in (("visible_camera", False), ("visible_diffuse", False), ("visible_shadow", False),
                      ("visible_transmission", False), ("visible_volume_scatter", False), ("visible_glossy", True)):
        try: setattr(o, attr, val)
        except Exception: pass
    scene.collection.objects.link(o)
    return o

def add_key_light(scene, energy=1.6, angle_deg=12.0):
    d = bpy.data.lights.new("Key", "SUN"); d.energy = energy; d.angle = math.radians(angle_deg)
    o = bpy.data.objects.new("Key", d)
    o.rotation_euler = (math.radians(-35), math.radians(8), 0)   # shadows fall down (and slightly right)
    scene.collection.objects.link(o)
    return o

# ----------------------------------------------------------------------------- geometry
def link(obj, coll):
    coll.objects.link(obj); return obj

def mesh_obj(name, bm, mat=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    if mat: me.materials.append(mat)
    return o

def cylinder(name, r, h, z0=0.0, verts=64, mat=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, z0 + h / 2))
    return mesh_obj(name, bm, mat)

def box(name, sx, sy, sz, center=(0, 0, 0), mat=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return mesh_obj(name, bm, mat)

def dome(name, r, zscale, mat=None, segs=64):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)
    bmesh.ops.scale(bm, vec=(1, 1, zscale), verts=bm.verts)
    o = mesh_obj(name, bm, mat); smooth(o); return o

def bevel(o, width, segs=4, angle=30):
    m = o.modifiers.new("Bevel", "BEVEL")
    m.width = width; m.segments = segs
    m.limit_method = "ANGLE"; m.angle_limit = math.radians(angle)
    return m

def smooth(o):
    for p in o.data.polygons: p.use_smooth = True

def enclosure(name, w, h, depth, corner, mat):
    o = box(name, w, h, depth, center=(0, 0, -depth / 2), mat=mat)
    bevel(o, corner, segs=10)
    return o

def text_obj(name, body, font, mat, rect_mm, coll, spacing=1.0, z=0.0, thickness=0.03):
    """Printed text fitted into rect_mm = (cx, cy, w, h), with a little ink thickness."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    if font: cu.font = font
    cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.space_character = spacing
    cu.extrude = thickness * 0.5
    cu.bevel_depth = thickness * 0.3
    cu.resolution_u = 24
    o = bpy.data.objects.new(name, cu); o.data.materials.append(mat)
    coll.objects.link(o)
    bpy.context.view_layer.update()
    cx, cy, w, h = rect_mm
    s = min(w / max(o.dimensions.x, 1e-6), h / max(o.dimensions.y, 1e-6))
    o.scale = (s, s, 1); o.location = (cx, cy, z + thickness * 0.5)
    return o

def flat_shape(name, pts, mat, thickness=0.03):
    """A printed shape from a 2D outline (list of (x, y))."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)],
                        vec=(0, 0, thickness))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)

def phillips_screw(name, x, y, r, angle, mat, coll, cutters):
    s = dome(name, r, 0.38, mat, segs=48); s.location = (x, y, 0)
    L, T = r * 0.62, r * 0.14                                   # arm half-length, half-width
    plus = [(T, T), (L, T), (L, -T), (T, -T), (T, -L), (-T, -L), (-T, -T), (-L, -T), (-L, T), (-T, T), (-T, L), (T, L)]
    cutter = flat_shape(name + "Cross", plus, None, thickness=2.0)
    cutter.location = (x, y, r * 0.38 - 0.45); cutter.rotation_euler = (0, 0, angle)
    cutters.objects.link(cutter)
    b = s.modifiers.new("Recess", "BOOLEAN"); b.operation = "DIFFERENCE"; b.object = cutter
    try: b.solver = "EXACT"
    except Exception: pass
    coll.objects.link(s)
    return s

def knurled_knob(name, R, height, mats, coll, ridges=90, depth=0.94):
    """Skirt with real knurling + rounded glossy cap + white pointer, parented to a pivot."""
    skirt_mat, cap_mat, pointer_mat = mats
    bm = bmesh.new()
    ring = []
    for i in range(ridges * 2):
        a = 2 * math.pi * i / (ridges * 2)
        r = R if i % 2 == 0 else R * depth
        ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0)))
    f = bm.faces.new(ring)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, height * 0.78))
    bmesh.ops.scale(bm, verts=top, vec=(0.97, 0.97, 1.0))                  # slight taper
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    skirt = mesh_obj(name + "Skirt", bm, skirt_mat); bevel(skirt, 0.35, 2, 50)
    cap = cylinder(name + "Cap", R * 0.83, height * 0.27, z0=height * 0.74, verts=128, mat=cap_mat)
    bevel(cap, R * 0.11, 6); smooth(cap)
    ptr = box(name + "Pointer", R * 0.11, R * 0.52, 0.12, center=(0, R * 0.50, height * 1.01 + 0.06), mat=pointer_mat)
    bevel(ptr, 0.04, 2)
    pivot = bpy.data.objects.new(name + "Pivot", None); coll.objects.link(pivot)
    for o in (skirt, cap, ptr):
        o.parent = pivot; coll.objects.link(o)
    return pivot

# ----------------------------------------------------------------------------- camera / output
class Camera:
    def __init__(self, scene, px_per_mm):
        cam = bpy.data.cameras.new("Cam"); cam.type = "ORTHO"; cam.clip_end = 1000
        self.obj = bpy.data.objects.new("Cam", cam); scene.collection.objects.link(self.obj)
        scene.camera = self.obj; self.scene = scene; self.ppmm = px_per_mm
    def frame(self, cx, cy, w_mm, h_mm):
        self.obj.location = (cx, cy, 200)
        self.obj.data.ortho_scale = max(w_mm, h_mm)
        r = self.scene.render
        r.resolution_x = max(1, round(w_mm * self.ppmm)); r.resolution_y = max(1, round(h_mm * self.ppmm))

def show_only(colls, all_colls):
    for c in all_colls: c.hide_render = c not in colls

def set_catcher(objs, on):
    for o in objs:
        if o.type in ("MESH", "FONT", "CURVE"): o.is_shadow_catcher = on

def render_to(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"[pedal] wrote {path}")

def load_rgba(path):
    img = bpy.data.images.load(path); w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)

def save_rgba(a, path):
    h, w = a.shape[:2]
    out = bpy.data.images.new("out", width=w, height=h, alpha=True)
    out.pixels.foreach_set(np.ascontiguousarray(a, dtype=np.float32).ravel())
    out.filepath_raw = path; out.file_format = "PNG"; out.save()
    bpy.data.images.remove(out)

def fade_edges(a, inner=0.80, outer=0.97):
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx + 0.5) / w - 0.5, (yy + 0.5) / h - 0.5) * 2.0
    t = np.clip((r - inner) / (outer - inner), 0.0, 1.0)
    a[..., 3] *= 1.0 - t * t * (3 - 2 * t)
    return a

def post_fade(path, inner=0.80, outer=0.97):
    save_rgba(fade_edges(load_rgba(path), inner, outer), path)

def _blur(x, radius):
    k = max(1, int(radius))
    for axis in (0, 1):
        for _ in range(3):                                   # 3 box blurs ~ gaussian
            c = np.cumsum(np.pad(x, [(k + 1, k) if i == axis else (0, 0) for i in range(x.ndim)], mode="edge"), axis=axis)
            x = (np.take(c, range(2 * k + 1, c.shape[axis]), axis=axis) - np.take(c, range(0, c.shape[axis] - 2 * k - 1), axis=axis)) / (2 * k + 1)
    return x

def bloom(path, strength=0.9, radius_frac=0.08, colour=(1.0, 0.12, 0.05)):
    """Soft glow around an emissive part (LED) baked into a transparent PNG."""
    a = load_rgba(path)
    lum = a[..., 0] * a[..., 3]
    glow = _blur(np.clip(lum - 0.6, 0, None), a.shape[1] * radius_frac) * strength * 2.5
    glow = np.clip(glow, 0, 1)
    out = a.copy()
    ga = glow * (1 - a[..., 3])                                  # glow only where the LED isn't
    for i, c in enumerate(colour):
        out[..., i] = (a[..., i] * a[..., 3] + c * ga) / np.maximum(a[..., 3] + ga, 1e-6)
    out[..., 3] = np.clip(a[..., 3] + ga, 0, 1)
    save_rgba(out, path)

GRID_COLS = 8   # knob frames are laid out 8 per row (keeps images under GPU texture limits)

def stack_grid(paths, out_path, cols=GRID_COLS, fade=True):
    """Frames left->right, top->bottom in a grid of `cols` columns (square frames)."""
    frames = [fade_edges(load_rgba(p)) if fade else load_rgba(p) for p in paths]
    fh, fw = frames[0].shape[:2]
    rows = (len(frames) + cols - 1) // cols
    grid = np.zeros((rows * fh, cols * fw, 4), dtype=np.float32)
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        y0 = (rows - 1 - r) * fh                               # Blender rows are bottom-up
        grid[y0:y0 + fh, c * fw:(c + 1) * fw] = f
    save_rgba(grid, out_path)
    print(f"[pedal] wrote {out_path}  ({len(frames)} frames, {cols}x{rows} grid of {fw}x{fh})")

def auto_exposure(scene, render_fn, target, tmp_path, iterations=3):
    """Adjust exposure so the enclosure face lands at `target` mean display brightness."""
    keep = (scene.cycles.samples, scene.render.resolution_percentage)
    scene.cycles.samples = 24; scene.render.resolution_percentage = 25
    for i in range(iterations):
        render_fn(tmp_path)
        a = load_rgba(tmp_path)
        m = a[..., 3] > 0.99
        mean = float(a[..., :3][m].mean()) if m.any() else target
        step = max(-3.0, min(3.0, 1.8 * math.log2(target / max(mean, 1e-4))))
        print(f"[pedal] exposure pass {i + 1}: mean {mean:.3f} -> adjust {step:+.2f} stops")
        if abs(step) < 0.05: break
        scene.view_settings.exposure += step
    scene.cycles.samples, scene.render.resolution_percentage = keep
    print(f"[pedal] exposure set to {scene.view_settings.exposure:+.2f}")
