"""ZOPPIKO scene builder.

Builds an episode from a JSON file: the Pad (a floating island in a pastel sky), props with physical motion
(drops, bounces, arcs, presses), Zop and Piko driven by the character engine, camera shots and shakes,
character squash and stretch, and a list of timed events for the sound mix.

    python3 zk/render.py storyboards/P01_the_button/scene.json              # full render (resumes if stopped)
    python3 zk/render.py <scene.json> --preview                             # half resolution, 4 samples
    python3 zk/render.py <scene.json> --budget 3000                         # stop after 3000 s, rerun to resume
    python3 zk/render.py <scene.json> --stills 0.2,1.5,4.8                  # storyboard frames only
    python3 zk/render.py <scene.json> --bake-only                           # build + events.json, no render

Format: documentation/SCENE_FORMAT.md
"""
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'engine'))

import bpy                                                     # noqa: E402
import bmesh                                                   # noqa: E402
from mathutils import Vector, Euler                           # noqa: E402

from cartoon_character import config as C                     # noqa: E402
from cartoon_character.automation import scene as S           # noqa: E402
from cartoon_character.automation import scene_json as SJ     # noqa: E402
from cartoon_character.automation.controller import Character  # noqa: E402
from cartoon_character.animation import motion_library as ML  # noqa: E402


def floor_idle(ctx, duration=1.0, dizzy=True):
    """ZOPPIKO extra motion: stays sitting on the floor (after a fall), head swaying if dazed."""
    m = ML.Motion('floor_idle', duration, 'comedy', start='floor', end='floor', description='sits on the floor, dazed')
    ML._floor_pose(m, 0.0, ctx, head=(5, 0, 0))
    n = max(2, int(duration / 0.2))
    for k in range(n + 1):
        t = duration * k / n; ang = k * 1.6
        if dizzy:
            m.pose(t, {'head': (6 + 7 * math.sin(ang), 8 * math.cos(ang), 7 * math.sin(ang + 0.6)), 'neck': (3, 3 * math.cos(ang), 0)})
    return m

FPS = C.FPS
CHAR_VARIANT = {'Zop': 'zop', 'Piko': 'piko'}
LAST_MARKS = {}

# ------------------------------------------------------------------ colours
PAL = dict(zop='#FF9466', piko='#7FB2FF', yellow='#FFB23F', teal='#1C8C8C', navy='#1F2C52', cream='#FFF1DC',
           coral='#FF6F3C', red='#E63946', white='#FFFFFF', grass='#9FDC8C', grass_dark='#86C977', soil='#C99A6B',
           soil_dark='#A97C52', banana='#FFD23F', banana_dark='#E8B92A', tip='#5A3D22', cookie='#D9A066',
           chip='#4A2F1C', steel='#B8C0CC', cloud='#FFFFFF')


def col(c):
    return PAL.get(c, c)


def lin(h):
    return S._hex_lin(col(h))


def material(name, color, rough=0.6, emit=0.0, spec=0.3):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*lin(color), 1)
    b.inputs['Roughness'].default_value = rough
    try:
        b.inputs['Specular IOR Level'].default_value = spec
    except Exception:
        pass
    if emit:
        b.inputs['Emission Color'].default_value = (*lin(color), 1)
        b.inputs['Emission Strength'].default_value = emit
    return m


def mesh_object(name, bm, mat, coll, smooth=True, parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    if isinstance(mat, (list, tuple)):
        for m in mat:
            me.materials.append(m)
    else:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, coll, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    coll.objects.link(e)
    e.location = loc
    if parent is not None:
        e.parent = parent
    return e


PT_LIBRARY = '/home/claude/pippo_assets'


def library():
    """the shared asset library (Pippo e Tumbo kit: Poly Haven, ambientCG, Kenney; CC0)."""
    if PT_LIBRARY not in sys.path:
        sys.path.insert(0, PT_LIBRARY)
    import pt_assets
    return pt_assets


def sky_photo(sc, path, strength=1.8, rotation=0.0, ambient=0.55, amb_color='#CFE0FF'):
    """the camera sees a real sky photo (equirectangular HDRI); the characters are lit by the ZOPPIKO daylight,
    so they look the same in every episode whatever the sky."""
    w = bpy.data.worlds.new('ZK_SkyPhoto'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; N = nt.nodes; L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputWorld'); tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value[2] = math.radians(rotation)
    env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(path, check_existing=True)
    bg = N.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    amb = N.new('ShaderNodeBackground'); amb.inputs['Strength'].default_value = ambient
    amb.inputs['Color'].default_value = (*lin(amb_color), 1)
    lp = N.new('ShaderNodeLightPath'); mix = N.new('ShaderNodeMixShader')
    L.new(tc.outputs['Generated'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], env.inputs['Vector'])
    hsv = N.new('ShaderNodeHueSaturation'); hsv.inputs['Saturation'].default_value = 1.3
    L.new(env.outputs['Color'], hsv.inputs['Color']); L.new(hsv.outputs['Color'], bg.inputs['Color'])
    L.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    L.new(amb.outputs['Background'], mix.inputs[1]); L.new(bg.outputs['Background'], mix.inputs[2])
    L.new(mix.outputs['Shader'], out.inputs['Surface'])
    return w


def hdri_rotation(A, aid, sun_azimuth=-38.0):
    """rotation (degrees) that puts the brightest point of the sky photo (the sun) at the wanted azimuth:
    0 = behind the camera, negative = front left (same convention as daylight())."""
    v = A.scarica(aid)
    path = A.percorso(v['file_1k']) if v.get('file_1k') else None
    if not path or not os.path.exists(path):
        return 0.0
    import numpy as np
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[..., :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    row, col = np.unravel_index(int(np.argmax(lum)), lum.shape)
    u = (col + 0.5) / w
    phi_img = math.pi - 2 * math.pi * u                      # Blender equirectangular: u = (pi - atan2(y, x)) / 2pi
    az = math.radians(sun_azimuth)
    phi_want = math.atan2(-math.cos(az), math.sin(az))       # direction from the subject toward the sun
    rot = math.degrees(phi_img - phi_want)
    print('hdri %s: sun at u=%.3f, elevation %.0f deg, rotation %.0f' % (aid, u, ((row + 0.5) / h - 0.5) * 180, rot))
    return rot


# ------------------------------------------------------------------ the Pad and the sky
def sky_world(sc, horizon='#FFE6C4', zenith='#8CC4FF', ambient=0.55, amb_color='#CFE0FF', strength=1.8):
    """the camera sees a soft vertical gradient; lighting uses a dim neutral colour (like the engine's studio)."""
    w = bpy.data.worlds.new('ZK_Sky'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; N = nt.nodes; L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputWorld')
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    rng = N.new('ShaderNodeMapRange')
    rng.inputs['From Min'].default_value = -0.10
    rng.inputs['From Max'].default_value = 0.55
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*lin(horizon), 1)
    ramp.color_ramp.elements[1].color = (*lin(zenith), 1)
    bg_sky = N.new('ShaderNodeBackground'); bg_sky.inputs['Strength'].default_value = strength
    bg_amb = N.new('ShaderNodeBackground'); bg_amb.inputs['Strength'].default_value = ambient
    bg_amb.inputs['Color'].default_value = (*lin(amb_color), 1)
    lp = N.new('ShaderNodeLightPath')
    mix = N.new('ShaderNodeMixShader')
    L.new(tc.outputs['Generated'], sep.inputs['Vector'])
    L.new(sep.outputs['Z'], rng.inputs['Value'])
    L.new(rng.outputs['Result'], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], bg_sky.inputs['Color'])
    L.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    L.new(bg_amb.outputs['Background'], mix.inputs[1])
    L.new(bg_sky.outputs['Background'], mix.inputs[2])
    L.new(mix.outputs['Shader'], out.inputs['Surface'])
    return w


def pad(coll, radius=3.2, grass='grass', soil='soil'):
    """the island: flat lawn on top (z = 0), a rounded rim and a rocky cone underneath."""
    prof = []
    rim = 0.10
    for i in range(12):                                     # lawn from the centre to the rim
        prof.append((radius - rim) * i / 11.0)
    pts = [(r, 0.0) for r in prof]
    for k in range(1, 7):                                   # rounded rim
        a = math.pi / 2 * k / 6
        pts.append((radius - rim + rim * math.sin(a), -rim + rim * math.cos(a)))
    for (r, z) in ((radius - 0.02, -0.24), (radius * 0.86, -0.55), (radius * 0.62, -0.95), (radius * 0.38, -1.35),
                   (radius * 0.16, -1.75), (0.0, -2.05)):   # soil cone
        pts.append((r, z))
    bm = bmesh.new()
    seg = 96
    rings = []
    for (r, z) in pts:
        ring = []
        for s in range(seg):
            a = 2 * math.pi * s / seg
            wob = 1.0 + (0.03 * math.sin(5 * a) + 0.02 * math.sin(11 * a + 1.3)) * (1 if z < -0.2 else 0)
            ring.append(bm.verts.new((r * wob * math.cos(a), r * wob * math.sin(a), z)))
        rings.append(ring)
    for j in range(len(rings) - 1):
        for s in range(seg):
            a, b = rings[j][s], rings[j][(s + 1) % seg]
            c, d = rings[j + 1][(s + 1) % seg], rings[j + 1][s]
            try:
                f = bm.faces.new((a, b, c, d))
            except ValueError:
                continue
            f.material_index = 0 if (a.co.z + c.co.z) / 2 > -0.13 else 1
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object('ZK_Pad', bm, [material('ZK_grass', grass, 0.9, spec=0.1), material('ZK_soil', soil, 0.95, spec=0.05)], coll)
    return ob


def tufts(coll, radius=3.2, n=46, seed=3):
    """small flowers near the rim: scale and charm, never near the action."""
    rnd = random.Random(seed)
    mats = [material('ZK_flower_%d' % i, c, 0.7) for i, c in enumerate(('#FFFFFF', '#FFD23F', '#FF8FB1', '#B9A4FF'))]
    centre = material('ZK_flower_c', '#FFB23F', 0.7)
    for i in range(n):
        a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(radius * 0.72, radius * 0.95)
        x, y = r * math.cos(a), r * math.sin(a)
        if y < -1.2 and abs(x) < 1.6:                        # keep the front of the stage clean
            continue
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=5, radius=0.028)
        for v in bm.verts:
            v.co.z *= 0.45
        f = mesh_object('ZK_flower%d' % i, bm, mats[i % 4], coll)
        f.location = (x, y, 0.012)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.011)
        c = mesh_object('ZK_flowerc%d' % i, bm, centre, coll, parent=f)
        c.location = (0, 0, 0.012)


def clouds(coll, spec=None):
    spec = spec or [(-3.6, 14.0, 3.6, 1.5), (2.8, 16.0, 4.6, 1.8), (6.5, 18.0, 2.4, 1.4), (-7.0, 17.0, 1.2, 1.6),
                    (0.4, 20.0, 6.4, 2.0), (-2.5, 12.0, -2.4, 1.3), (4.2, 13.0, -3.2, 1.5)]
    m = bpy.data.materials.new('ZK_cloud'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (1, 1, 1, 1); em.inputs['Strength'].default_value = 2.6
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], o.inputs['Surface'])
    rnd = random.Random(7)
    for i, (x, y, z, s) in enumerate(spec):
        bm = bmesh.new()
        for k in range(5):
            r = s * rnd.uniform(0.35, 0.6)
            t = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
            dx = (k - 2) * s * 0.42 + rnd.uniform(-0.1, 0.1) * s
            dz = rnd.uniform(0.0, 0.25) * s - abs(k - 2) * 0.12 * s
            for v in t['verts']:
                v.co += Vector((dx, 0, dz))
        for v in bm.verts:
            v.co.y *= 0.55
        ob = mesh_object('ZK_cloud%d' % i, bm, m, coll)
        ob.location = (x, y, z)


# ------------------------------------------------------------------ props
def _sphere(bm, r, seg=24, rings=14, center=(0, 0, 0), scale=(1, 1, 1)):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in res['verts']:
        v.co = Vector((v.co.x * scale[0] + center[0], v.co.y * scale[1] + center[1], v.co.z * scale[2] + center[2]))
    return res['verts']


def _cyl(bm, r, h, z0=0.0, seg=32, r2=None):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    for v in res['verts']:
        v.co.z += z0 + h / 2
    return res['verts']


def beachball_material(name, colors):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N['Principled BSDF']; b.inputs['Roughness'].default_value = 0.35
    tc = N.new('ShaderNodeTexCoord'); gr = N.new('ShaderNodeTexGradient'); gr.gradient_type = 'RADIAL'
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    els[0].position = 0.0; els[0].color = (*lin(colors[0]), 1)
    els[1].position = 1.0 / len(colors); els[1].color = (*lin(colors[1]), 1)
    for i in range(2, len(colors)):
        e = els.new(i / len(colors)); e.color = (*lin(colors[i]), 1)
    L.new(tc.outputs['Object'], gr.inputs['Vector'])
    L.new(gr.outputs['Fac'], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], b.inputs['Base Color'])
    return m


def make_prop(spec, coll):
    """returns (root object, parts dict). The root's origin sits on the ground contact point."""
    name = spec['name']; kind = spec.get('type', 'box'); s = spec.get('size', 1.0)
    parts = {}
    if kind == 'button':
        root = empty(name, coll)
        cr = spec.get('cap', 0.13) / 0.13
        bm = bmesh.new(); _cyl(bm, 0.12 * s * cr, 0.03 * s, 0.0); _cyl(bm, 0.06 * s * cr, 0.40 * s, 0.03 * s)
        _cyl(bm, 0.125 * s * cr, 0.035 * s, 0.43 * s)
        mesh_object(name + '_base', bm, material(name + '_steel', spec.get('base', 'navy'), 0.45), coll, parent=root)
        bm = bmesh.new(); _sphere(bm, spec.get('cap', 0.13) * s, scale=(1, 1, 0.42), center=(0, 0, 0.0))
        cap = mesh_object(name + '_cap', bm, material(name + '_red', spec.get('color', 'red'), 0.25, spec=0.6), coll, parent=root)
        cap.location = (0, 0, 0.465 * s)
        parts['cap'] = cap
    elif kind == 'beachball':
        r = spec.get('radius', 0.34)
        bm = bmesh.new(); _sphere(bm, r, 48, 24, center=(0, 0, r))
        root = mesh_object(name, bm, beachball_material(name + '_mat', spec.get('colors', ['red', 'white', 'yellow', 'white', 'teal', 'white'])), coll)
    elif kind == 'cookie':
        r = spec.get('radius', 0.17); h = spec.get('height', 0.055)
        bm = bmesh.new(); _cyl(bm, r, h, 0.0, 40)
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges if len(e.link_faces) == 2 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6],
                        offset=h * 0.35, segments=3, affect='EDGES')
        root = mesh_object(name, bm, material(name + '_dough', spec.get('color', 'cookie'), 0.8), coll)
        rnd = random.Random(11)
        chips = bmesh.new()
        for k in range(14):
            a = rnd.uniform(0, 2 * math.pi); rr = r * math.sqrt(rnd.uniform(0.02, 0.7))
            for z in (h + 0.002, -0.002):
                _sphere(chips, 0.018, 8, 5, center=(rr * math.cos(a), rr * math.sin(a), z), scale=(1, 1, 0.5))
        mesh_object(name + '_chips', chips, material(name + '_chip', 'chip', 0.6), coll, parent=root)
    elif kind == 'banana':
        L_ = spec.get('length', 0.30); R = spec.get('radius', 0.035)
        bm = bmesh.new(); n = 16; seg = 10; rings = []
        for i in range(n + 1):
            t = i / n; ang = (t - 0.5) * math.radians(80)
            cx = math.sin(ang) * L_ * 0.75; cz = (1 - math.cos(ang)) * L_ * 0.75
            rr = R * (0.35 + 0.65 * math.sin(math.pi * min(1, max(0, (t * 1.08 - 0.04))) ** 0.8))
            ring = []
            for k in range(seg):                             # ring perpendicular to the curved centre line
                a = 2 * math.pi * k / seg
                ring.append(bm.verts.new((cx - rr * math.cos(a) * math.sin(ang), rr * math.sin(a),
                                          R + cz + rr * math.cos(a) * math.cos(ang))))
            rings.append(ring)
        for j in range(n):
            for k in range(seg):
                bm.faces.new((rings[j][k], rings[j][(k + 1) % seg], rings[j + 1][(k + 1) % seg], rings[j + 1][k]))
        bm.faces.new(list(reversed(rings[0]))); bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        root = mesh_object(name, bm, material(name + '_skin', spec.get('color', 'banana'), 0.5), coll)
        tips = bmesh.new()
        for i in (0, n):
            t = i / n; ang = (t - 0.5) * math.radians(80)
            _sphere(tips, R * 0.42, 8, 6, center=(math.sin(ang) * L_ * 0.75, 0, R + (1 - math.cos(ang)) * L_ * 0.75))
        mesh_object(name + '_tips', tips, material(name + '_tip', 'tip', 0.7), coll, parent=root)
    elif kind == 'peel':
        root = empty(name, coll)
        bm = bmesh.new(); _sphere(bm, 0.032, 12, 8, center=(0, 0, 0.018), scale=(1, 1, 0.65))
        for k in range(4):
            a = math.radians(45 + 90 * k + (k % 2) * 14)
            ln = 0.115 + 0.02 * (k % 2)
            vs = _sphere(bm, 1.0, 12, 8)
            for v in vs:                                     # long flat petal along its own x axis, then rotated
                x, y, z = v.co.x * ln * 0.5, v.co.y * 0.03, v.co.z * 0.008
                x += ln * 0.5
                v.co = Vector((x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z + 0.008 + 0.010 * max(0, x / ln - 0.6)))
        mesh_object(name + '_peel', bm, material(name + '_mat', spec.get('color', 'banana'), 0.55), coll, parent=root)
    elif kind == 'sphere':
        r = spec.get('radius', 0.08)
        bm = bmesh.new(); _sphere(bm, r, center=(0, 0, r))
        root = mesh_object(name, bm, material(name + '_mat', spec.get('color', 'red'), spec.get('roughness', 0.45)), coll)
    elif kind == 'cylinder':
        bm = bmesh.new(); _cyl(bm, spec.get('radius', 0.08), spec.get('height', 0.2))
        root = mesh_object(name, bm, material(name + '_mat', spec.get('color', 'red'), spec.get('roughness', 0.45)), coll)
    else:                                                    # box, origin at the bottom centre
        sx, sy, sz = spec.get('dims', (0.3, 0.3, 0.3))
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= sx; v.co.y *= sy; v.co.z = v.co.z * sz + sz / 2
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(sx, sy, sz) * 0.08, segments=3, affect='EDGES')
        root = mesh_object(name, bm, material(name + '_mat', spec.get('color', 'yellow'), spec.get('roughness', 0.5)), coll)
    return root, parts


# ------------------------------------------------------------------ prop motion (sampled per frame)
class Track:
    """position / rotation (deg) / scale over time, built from segments, plus the events they produce."""

    def __init__(self, spec):
        self.segs = sorted(spec.get('motion', []), key=lambda s: s['t'])
        p0 = spec.get('location', (0, 0, 0))
        self.p0 = Vector(p0); self.r0 = Vector(spec.get('rotation', (0, 0, 0))); self.s0 = spec.get('scale', 1.0)
        self.events = []
        self.cache = {}
        self._plan()

    def _plan(self):
        """precompute each segment's start state and the events (landings, presses...)."""
        p, r = self.p0.copy(), self.r0.copy()
        self.plan = []
        for seg in self.segs:
            t = seg['t']
            if 'at' in seg:
                p = Vector(seg['at']); r = Vector(seg.get('rot', r))
                self.plan.append(('at', t, dict(p=p.copy(), r=r.copy())))
            elif 'drop' in seg:
                d = seg['drop']; to = Vector(d.get('to', p)); h = d.get('h', 3.0); g = d.get('g', 14.0)
                tf = math.sqrt(2 * h / g)
                bounce = d.get('bounce', 0.10); e = math.sqrt(max(bounce, 1e-6) / h)
                times = [t + tf]; heights = [h]; v = math.sqrt(2 * g * h); tt = t + tf
                for k in range(d.get('bounces', 2)):
                    v *= e; hb = v * v / (2 * g)
                    if hb < 0.004:
                        break
                    tt += 2 * v / g; times.append(tt); heights.append(hb)
                self.plan.append(('drop', t, dict(to=to, h=h, g=g, tf=tf, times=times, e=e, spin=Vector(d.get('spin', (0, 0, 0))),
                                                  r=Vector(d.get('rot', r)), squash=d.get('squash', 0.28))))
                for i, ti in enumerate(times):
                    self.events.append(dict(t=round(ti, 3), kind='land', strength=1.0 if i == 0 else 0.35 * (0.5 ** (i - 1)),
                                            sound=d.get('sound', 'thud') if i == 0 else 'tap'))
                self.events.append(dict(t=round(t, 3), kind='fall_start', dur=round(tf, 3), sound=d.get('fall_sound', 'whistle')))
                p = to.copy(); r = Vector(d.get('rot', r))
            elif 'fly' in seg:
                d = seg['fly']; a = Vector(d.get('from', p)); b = Vector(d['to'])
                self.plan.append(('fly', t, dict(a=a, b=b, dur=d.get('dur', 0.6), arc=d.get('arc', 0.3),
                                                 spin=Vector(d.get('spin', (0, 0, 0))), r=r.copy())))
                if d.get('land', True):
                    self.events.append(dict(t=round(t + d.get('dur', 0.6), 3), kind='land', strength=d.get('strength', 0.6),
                                            sound=d.get('sound', 'thud')))
                p = b.copy(); r = r + Vector(d.get('spin', (0, 0, 0))) * d.get('dur', 0.6)
            elif 'ballistic' in seg:
                d = seg['ballistic']
                self.plan.append(('ballistic', t, dict(a=Vector(d.get('from', p)), v=Vector(d['v']), g=d.get('g', 12.0),
                                                       spin=Vector(d.get('spin', (0, 0, 0))), r=r.copy())))
            elif 'roll' in seg:                              # rolls on its edge along a straight line
                d = seg['roll']; a = Vector(d.get('from', p)); b = Vector(d['to'])
                self.plan.append(('roll', t, dict(a=a, b=b, dur=d.get('dur', 1.0), radius=d.get('radius', 0.17),
                                                  ease=d.get('ease', 'in'), r=r.copy(), axis=d.get('axis', 'y'))))
                p = b.copy()
            elif 'tilt' in seg:                              # tips over on a bottom edge (dominoes): keys of [dt, degrees]
                d = seg['tilt']
                keys = [(t + k[0], float(k[1])) for k in d['keys']]
                yaw = d.get('yaw', r.z); half = d.get('half', 0.025)
                self.plan.append(('tilt', t, dict(keys=keys, half=half, yaw=yaw, base=p.copy())))
                for e in d.get('events', []):
                    self.events.append(dict(t=round(t + e['t'], 3), kind='cue', sound=e['sound'], gain=e.get('gain', 0.0),
                                            pitch=e.get('pitch', 0.0), pan=e.get('pan', 0.0)))
                p, r = tilt_pose(p, keys[-1][1], half, yaw)
            elif 'press' in seg:
                self.events.append(dict(t=round(t, 3), kind='press', sound=seg.get('sound', 'click')))
            elif 'show' in seg or 'hide' in seg:
                pass
            if 'event' in seg:
                self.events.append(dict(t=round(seg['t'], 3), kind='cue', sound=seg['event']))

    def state(self, t):
        """(location, rotation_deg, scale vector) at time t."""
        cur = None
        for item in self.plan:
            if item[1] <= t + 1e-9:
                cur = item
        p, r, s = self.p0.copy(), self.r0.copy(), Vector((self.s0,) * 3) if not isinstance(self.s0, (list, tuple)) else Vector(self.s0)
        if cur is None:
            return p, r, s
        kind, t0, d = cur; u = t - t0
        if kind == 'at':
            return d['p'], d['r'], s
        if kind == 'drop':
            to, h, g, tf = d['to'], d['h'], d['g'], d['tf']
            if u < tf:
                z = h - 0.5 * g * u * u
                st = 1.0 + 0.10 * min(1.0, u / tf)            # stretch while falling
                return Vector((to.x, to.y, to.z + z)), d['r'] + d['spin'] * (u - tf), Vector((s.x / math.sqrt(st), s.y / math.sqrt(st), s.z * st))
            times = d['times']; v = math.sqrt(2 * g * h)
            for i in range(len(times)):
                ti = times[i] - t0
                tn = (times[i + 1] - t0) if i + 1 < len(times) else None
                if tn is None or u < tn:
                    du = u - ti
                    vi = v * (d['e'] ** (i + 1))
                    z = max(0.0, vi * du - 0.5 * g * du * du) if tn is not None else 0.0
                    sq = d['squash'] * (0.45 ** i)
                    k = du * FPS
                    if k < 2.0:
                        f = 1.0 - sq * (1.0 - abs(k - 1.0) * 0.5)
                    elif k < 7.0:
                        f = 1.0 + sq * 0.35 * math.sin((k - 2.0) / 5.0 * math.pi)
                    else:
                        f = 1.0
                    return Vector((to.x, to.y, to.z + z)), d['r'], Vector((s.x / math.sqrt(f), s.y / math.sqrt(f), s.z * f))
            return to, d['r'], s
        if kind == 'fly':
            k = min(1.0, max(0.0, u / d['dur']))
            pos = d['a'].lerp(d['b'], k) + Vector((0, 0, 4 * d['arc'] * k * (1 - k)))
            return pos, d['r'] + d['spin'] * min(u, d['dur']), s
        if kind == 'ballistic':
            pos = d['a'] + d['v'] * u + Vector((0, 0, -0.5 * d['g'] * u * u))
            return pos, d['r'] + d['spin'] * u, s
        if kind == 'roll':
            k = min(1.0, max(0.0, u / d['dur']))
            e = k * k if d['ease'] == 'in' else (1 - (1 - k) ** 2 if d['ease'] == 'out' else k)
            pos = d['a'].lerp(d['b'], e)
            dist = (d['b'] - d['a']).length * e
            ang = math.degrees(dist / d['radius'])
            dv = d['b'] - d['a']
            yaw = math.degrees(math.atan2(dv.y, dv.x))
            return pos, Vector((90.0, -ang, yaw)), s       # standing on its edge, spinning on its axle, facing the path
        if kind == 'tilt':
            keys = d['keys']
            if t <= keys[0][0]:
                th = keys[0][1]
            elif t >= keys[-1][0]:
                th = keys[-1][1]
            else:
                lo, hi = 0, len(keys) - 1
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if keys[mid][0] <= t:
                        lo = mid
                    else:
                        hi = mid
                (ta, a), (tb, b) = keys[lo], keys[hi]
                th = a + (b - a) * (t - ta) / max(1e-9, tb - ta)
            pos, rot = tilt_pose(d['base'], th, d['half'], d['yaw'])
            return pos, rot, s
        return p, r, s


def tilt_pose(base, th, half, yaw):
    """a box with its origin at the bottom centre, tipped by th degrees towards its local +y about the bottom edge
    (towards -y about the back edge when th < 0), then turned by yaw about z."""
    a = math.radians(th); sg = 1.0 if th >= 0 else -1.0
    oy = sg * half * (1.0 - math.cos(a)); oz = half * abs(math.sin(a))
    py = math.radians(yaw)
    return Vector((base.x - oy * math.sin(py), base.y + oy * math.cos(py), base.z + oz)), Vector((-th, 0.0, yaw))


def bake_prop(ob, track, spec, n, parts):
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = 'LINEAR'
    sparse = any('tilt' in s_ for s_ in track.segs)           # many still dominoes: key only where they move
    states = [track.state((f - 1) / FPS) for f in range(1, n + 1)] if sparse else None

    def still(i):
        a, b = states[i], states[i - 1]
        c = states[i + 1]
        return all((a[k] - b[k]).length < 1e-7 and (a[k] - c[k]).length < 1e-7 for k in range(3))

    for f in range(1, n + 1):
        t = (f - 1) / FPS
        if sparse:
            if 1 < f < n and still(f - 1):
                continue
            p, r, s = states[f - 1]
        else:
            p, r, s = track.state(t)
        ob.location = p
        ob.rotation_euler = Euler([math.radians(a) for a in r])
        ob.scale = s
        ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_euler', frame=f); ob.keyframe_insert('scale', frame=f)
    # presses: the cap goes down and comes back up
    cap = parts.get('cap')
    if cap is not None:
        z0 = cap.location.z
        cap.keyframe_insert('location', frame=1)
        for seg in track.segs:
            if 'press' in seg:
                depth = seg.get('press', 0.025); dur = seg.get('dur', 0.35)
                f0 = int(round(seg['t'] * FPS)) + 1
                for df, z in ((0, z0), (2, z0 - depth), (2 + int(dur * FPS), z0 - depth), (5 + int(dur * FPS), z0)):
                    cap.location.z = z; cap.keyframe_insert('location', frame=f0 + df)
    # visibility windows
    vis = [s_ for s_ in track.segs if 'show' in s_ or 'hide' in s_]
    if vis or spec.get('hidden'):
        prefs.keyframe_new_interpolation_type = 'CONSTANT'
        objs = [ob] + list(ob.children_recursive)
        state = bool(spec.get('hidden', False))
        for o in objs:
            o.hide_render = state; o.hide_viewport = state
            o.keyframe_insert('hide_render', frame=1); o.keyframe_insert('hide_viewport', frame=1)
        for s_ in vis:
            f = int(round(s_['t'] * FPS)) + 1
            hide = 'hide' in s_
            for o in objs:
                o.hide_render = hide; o.hide_viewport = hide
                o.keyframe_insert('hide_render', frame=f); o.keyframe_insert('hide_viewport', frame=f)
        prefs.keyframe_new_interpolation_type = 'LINEAR'


# ------------------------------------------------------------------ characters
def resolve(t, marks):
    """a time is a number or "mark", "mark+0.4", "mark-0.2" (marks are set by actions with "mark")."""
    if isinstance(t, (int, float)):
        return float(t)
    s = str(t).replace(' ', '')
    for sign in ('+', '-'):
        if sign in s[1:]:
            i = s.index(sign, 1)
            return marks[s[:i]] + float(s[i:])
    return marks[s]


def run_char_actions(ch, actions, chars, props, base, ctx):
    """the engine's actions, plus:
       {"until": t}            idle until an absolute time (or a mark)
       {"press": "button"}     step to the right distance from the button and press it with a finger
       "mark": "name"          on any action: remember when it starts (for press: the moment of the click)
    """
    marks = ctx['marks']
    for a in actions:
        a = dict(a)
        if 'until' in a:
            tt = resolve(a['until'], marks)
            # the next clip starts one blend before the end of the wait: aim so that it starts exactly at tt
            d = tt - ch.now + a.get('blend', 0.3) + a.get('next_blend', 0.25)
            if d > 0.04 and ch.state == 'floor':           # sitting on the floor: stay down, do not pop up
                c = ch.tl.add(floor_idle(ch.ctx, d, a.get('dizzy', True)), d, 0.3)
                ch.log.append(('floor_idle', c.start, c.end))
            elif d > 0.04:
                ch.wait(d, blend=a.get('blend', 0.3))
            elif d < -0.08:
                print('WARNING %s: "until %s" arrives late by %.2f s' % (ch.name, a['until'], -d))
            continue
        if 'press' in a:
            name = a['press']; tr = ctx['tracks'][name]; ps = ctx['specs'][name]
            pe, _, _ = tr.state(1e5)
            sz = ps.get('size', 1.0); cap = ps.get('cap', 0.13) * sz
            P = ch.tl.next_origin().translation
            d = Vector((P.x - pe.x, P.y - pe.y, 0.0))
            d = d.normalized() if d.length > 1e-6 else Vector((0, 1, 0))
            T = Vector((pe.x, pe.y, pe.z + 0.47 * sz)) + d * cap * 0.55      # the near half of the cap
            Q = Vector((T.x, T.y, 0.0)) + d * a.get('stand', 0.32)
            if (Q - Vector((P.x, P.y, 0.0))).length > a.get('step_min', 0.08):
                ch.walk_to((Q.x, Q.y))
            ch.point(tuple(T))
            hit = ch.log[-1][1] + a.get('hit', 0.36)
            tr.segs.append({'t': hit, 'press': a.get('depth', 0.03), 'dur': a.get('hold', 0.3)})
            tr.events.append(dict(t=round(hit, 3), kind='press', sound=a.get('sound', 'click')))
            if 'mark' in a:
                marks[a['mark']] = hit
            continue
        if isinstance(a.get('at'), str):
            a['at'] = resolve(a['at'], marks)
        SJ.run_actions(ch, [{k: v for k, v in a.items() if k not in ('mark', 'mark_end')}], chars, props, base)
        if 'mark' in a and ch.log:
            marks[a['mark']] = ch.log[-1][1]
        if 'mark_end' in a and ch.log:
            marks[a['mark_end']] = ch.log[-1][2]


def carriers(chars, spec_chars):
    """squash and stretch: a parent empty under each rig, pivot on the character's feet."""
    prefs = bpy.context.preferences.edit
    for c in spec_chars:
        keys = c.get('squash')
        if not keys:
            continue
        ch = chars[c['name']]; rig = ch.rig; coll = rig.users_collection[0]
        for k in keys:
            px, py = k.get('pivot', c.get('location', (0, 0)))
            e = empty(ch.name + '_carrier_%d' % keys.index(k), coll, (px, py, 0))
            rig.parent = e; rig.location = (-px, -py, 0)
            prefs.keyframe_new_interpolation_type = 'BEZIER'
            f0 = int(round(k['t'] * FPS)) + 1
            amt = k.get('amount', 0.25)
            seq = [(0, 1.0), (2, 1.0 - amt), (5, 1.0 + amt * 0.35), (8, 1.0 - amt * 0.12), (11, 1.0)]
            if k.get('hold'):
                seq = [(0, 1.0), (2, 1.0 - amt), (2 + int(k['hold'] * FPS), 1.0 - amt), (6 + int(k['hold'] * FPS), 1.0 + amt * 0.3),
                       (10 + int(k['hold'] * FPS), 1.0)]
            for df, z in seq:
                xy = 1.0 / math.sqrt(z)
                e.scale = (xy, xy, z); e.keyframe_insert('scale', frame=max(1, f0 + df))
            break                                            # one carrier per character (first key's pivot)
        prefs.keyframe_new_interpolation_type = 'LINEAR'


# ------------------------------------------------------------------ camera
def camera_track(cam, spec, n, events):
    shots = sorted(spec.get('shots') or [dict(t=0, location=spec.get('location', (0.4, -4.3, 0.95)),
                                              target=spec.get('target', (0.4, 0, 0.55)), lens=spec.get('lens', 40))],
                   key=lambda s: s['t'])
    shakes = spec.get('shakes', [])
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = 'LINEAR'
    rnd = random.Random(5)
    noise = [(rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)) for _ in range(n + 1)]
    for s in shots[1:]:
        events.append(dict(t=s['t'], kind='cut'))
    for f in range(1, n + 1):
        t = (f - 1) / FPS
        cur = shots[0]
        for s in shots:
            if s['t'] <= t + 1e-9:
                cur = s
        loc = Vector(cur['location']); tg = Vector(cur['target']); lens = cur.get('lens', 40)
        mv = cur.get('move')
        if mv:                                               # smooth move inside the shot (push-in)
            t0 = cur['t'] + mv.get('delay', 0.0); t1 = t0 + mv['dur']
            k = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
            k = k * k * (3 - 2 * k)
            loc = loc.lerp(Vector(mv.get('location', cur['location'])), k)
            tg = tg.lerp(Vector(mv.get('target', cur['target'])), k)
            lens = lens + (mv.get('lens', lens) - lens) * k
        for sh in shakes:
            u = t - sh['t']
            if 0 <= u < sh.get('dur', 0.35):
                a = sh.get('amount', 0.03) * (1 - u / sh.get('dur', 0.35)) ** 2
                nx, ny, nz = noise[f]
                loc = loc + Vector((nx * a, 0, nz * a)); tg = tg + Vector((nx * a * 0.6, 0, ny * a * 0.6))
        S.aim(cam, tuple(loc), tuple(tg), lens, frame=f)


# ------------------------------------------------------------------ light
def daylight(coll, subject=(0, 0, 0.6), camera=(0, -4, 0.9), sun=3.2, azimuth=-38.0, elevation=48.0, rim=180.0):
    """ZOPPIKO daylight: a warm sun from the front side with crisp soft-edged shadows, the sky as fill
    (world colour), and a cool rim light behind the characters to separate them from the background."""
    s = Vector(subject); c = Vector(camera)
    so = None
    sun_d = bpy.data.lights.new('ZK_Sun', 'SUN'); sun_d.energy = max(sun, 0.0); sun_d.color = (1.0, 0.93, 0.82)
    sun_d.angle = math.radians(3.0)
    try:
        sun_d.shadow_maximum_resolution = 0.01
    except Exception:
        pass
    so = bpy.data.objects.new('ZK_Sun', sun_d); coll.objects.link(so)
    az, el = math.radians(azimuth), math.radians(elevation)
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))   # from the subject toward the sun
    so.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    back = Vector((c.x - s.x, c.y - s.y, 0)).normalized()
    rim_l = bpy.data.lights.new('ZK_Rim', 'AREA'); rim_l.energy = rim; rim_l.color = (0.75, 0.86, 1.0); rim_l.size = 1.6
    ro = bpy.data.objects.new('ZK_Rim', rim_l); coll.objects.link(ro)
    ro.location = s - back * 2.4 + Vector((0.8, 0, 1.7))
    ro.rotation_euler = (s + Vector((0, 0, 0.3)) - ro.location).to_track_quat('-Z', 'Y').to_euler()
    return so, ro


# ------------------------------------------------------------------ build
def build(spec, base):
    sc = S.reset()
    st = bpy.data.collections.new('ZK_Stage'); sc.collection.children.link(st)
    stg = spec.get('stage', {})
    hd = stg.get('hdri')
    if hd:                                                   # a real sky photo (Poly Haven / ambientCG, CC0) lights the scene
        A = library()
        if hd.get('lighting'):                               # the photo also lights the scene (its own sun)
            rot = hd.get('rotation')
            if rot is None:
                rot = hdri_rotation(A, hd['id'], hd.get('sun_azimuth', -38.0))
            A.cielo(hd['id'], forza=hd.get('strength', 1.0), rotazione=rot, sfondo=True, scena=sc)
        else:                                                # backdrop only: the light stays the ZOPPIKO daylight
            v = A.scarica(hd['id'])
            sky_photo(sc, A.percorso(v['file_1k']), hd.get('strength', 1.8), hd.get('rotation', 0.0),
                      stg.get('ambient', 0.55), stg.get('ambient_color', '#CFE0FF'))
    else:
        sky_world(sc, stg.get('horizon', '#FFE6C4'), stg.get('zenith', '#8CC4FF'), stg.get('ambient', 0.55),
                  stg.get('ambient_color', '#CFE0FF'), stg.get('sky_strength', 1.8))
    pad_ob = pad(st, stg.get('radius', 3.2), stg.get('grass', 'grass'), stg.get('soil', 'soil'))
    gt = stg.get('grass_texture')
    if gt:                                                   # real grass (PBR texture, CC0)
        A = library()
        m = A.materiale(gt['id'], dimensione=gt.get('size', 0.8), rilievo=gt.get('relief', 1.0), tinta=gt.get('tint'),
                        ruvidita=2.0)
        for nd in m.node_tree.nodes:                         # no glitter: grass is matte
            if nd.type == 'BSDF_PRINCIPLED':
                try:
                    nd.inputs['Specular IOR Level'].default_value = 0.12
                except Exception:
                    pass
        pad_ob.data.materials[0] = m
    if stg.get('flowers', True):
        tufts(st, stg.get('radius', 3.2))
    if stg.get('clouds', not hd):
        clouds(st)
    props = {}; parts = {}; tracks = {}; specs = {}
    for p in spec.get('props', []):
        ob, pa = make_prop(p, st)
        props[p['name']] = ob; parts[p['name']] = pa; specs[p['name']] = p
        if all(isinstance(s_['t'], (int, float)) for s_ in p.get('motion', [])):
            tracks[p['name']] = Track(p)
            p0, r0, s0 = tracks[p['name']].state(0.0)
        else:
            p0, r0, s0 = Vector(p.get('location', (0, 0, 0))), Vector(p.get('rotation', (0, 0, 0))), Vector((1, 1, 1))
        ob.location = p0; ob.rotation_euler = Euler([math.radians(a) for a in r0]); ob.scale = s0
    ctx = dict(marks=dict(spec.get('marks', {})), tracks=tracks, specs=specs)
    chars = {}
    for c in spec.get('characters', []):
        chars[c['name']] = Character(c['name'], CHAR_VARIANT.get(c['name'], c.get('variant', 'zop')),
                                     location=tuple(c.get('location', (0, 0))), facing=c.get('facing', 0.0))
    cam_spec = spec.get('camera', {})
    first = (cam_spec.get('shots') or [cam_spec])[0]
    cam = S.camera(sc, st, tuple(first.get('location', (0.4, -4.3, 0.95))), tuple(first.get('target', (0.4, 0, 0.55))),
                   first.get('lens', 40))
    for c in spec.get('characters', []):
        run_char_actions(chars[c['name']], c.get('actions', []), chars, props, base, ctx)
    for p in spec.get('props', []):                          # props timed on marks: plan them now
        if p['name'] not in tracks:
            q = dict(p); q['motion'] = [dict(s_, t=resolve(s_['t'], ctx['marks'])) for s_ in p.get('motion', [])]
            tracks[p['name']] = Track(q)
    print('marks:', {k: round(v, 2) for k, v in ctx['marks'].items()})
    global LAST_MARKS
    LAST_MARKS = dict(ctx['marks'])
    M = ctx['marks']
    cam_spec = dict(cam_spec)
    cam_spec['shots'] = [dict(s_, t=resolve(s_['t'], M)) for s_ in (cam_spec.get('shots') or [])]
    cam_spec['shakes'] = [dict(s_, t=resolve(s_['t'], M)) for s_ in cam_spec.get('shakes', [])]
    spec = dict(spec)
    spec['characters'] = [dict(c, squash=[dict(k, t=resolve(k['t'], M)) for k in c.get('squash', [])])
                          for c in spec.get('characters', [])]
    spec['cues'] = [dict(c, t=resolve(c['t'], M)) for c in spec.get('cues', [])]
    dur = spec.get('duration')
    if 'duration_from' in spec:
        dur = resolve(spec['duration_from'], M)
    n = int(round(dur * FPS)) if dur else max(int(math.ceil((ch.tl.length + spec.get('end_hold', 0.5)) * FPS)) + 1
                                             for ch in chars.values())
    for ch in chars.values():
        ch.bake(end_hold=max(0.0, (n - 1) / FPS - ch.tl.length - 1e-6))
    sc.frame_start = 1; sc.frame_end = n
    events = []
    for e in spec.get('fx', []):
        events.append(dict(t=round(resolve(e['t'], M), 3), kind='fx', fx=e['type']))
    for name, ob in props.items():
        bake_prop(ob, tracks[name], next(p for p in spec['props'] if p['name'] == name), n, parts[name])
        for e in tracks[name].events:
            events.append(dict(e, prop=name))
    carriers(chars, spec.get('characters', []))
    for name, ch in chars.items():
        for (act, t0, t1) in ch.log:
            events.append(dict(t=round(t0, 3), end=round(t1, 3), kind='action', char=name, action=act))
    camera_track(cam, cam_spec, n, events)
    tg = Vector(first.get('target', (0.4, 0, 0.55))); cl = Vector(first.get('location', (0.4, -4.3, 0.95)))
    if spec.get('lighting', 'daylight') == 'cinema':
        S.cinema_lights(st, tuple(tg), tuple(cl), side=spec.get('light_side', 1), power=spec.get('light_power', 1.0))
    else:
        lt = spec.get('light', {})
        daylight(st, tuple(tg), tuple(cl), sun=lt.get('sun', 3.2), azimuth=lt.get('azimuth', -38.0),
                 elevation=lt.get('elevation', 48.0), rim=lt.get('rim', 180.0))
    from zk import fx as FXM
    FXM.add(spec.get('fx', []), st, lambda t: resolve(t, M))
    r = spec.get('render', {})
    S.setup_render(sc, *r.get('resolution', (1080, 1920)), samples=r.get('samples', 6))
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 94
    for c in spec.get('cues', []):                           # sounds placed by hand in the scene file
        events.append(dict(c, kind='cue'))
    events.sort(key=lambda e: e['t'])
    return sc, chars, props, n, events
