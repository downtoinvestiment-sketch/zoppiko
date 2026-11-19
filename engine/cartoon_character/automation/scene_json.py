"""Scene descritte in JSON: personaggi, azioni, oggetti, camera -> video, senza scrivere Python.

    python3 cartoon_character/main.py render scena.json                  # rende tutto (si riprende se interrotto)
    python3 cartoon_character/main.py render scena.json --solo-cottura   # costruisce e cuoce l'animazione, niente render
    python3 cartoon_character/main.py render scena.json --budget 540     # rende al massimo 540 s, poi si ferma
    python3 cartoon_character/main.py render scena.json --anteprima      # meta' risoluzione, 4 campioni

Formato: vedi docs/SCENE_JSON.md (esempio completo in examples/saluto.json).
"""
import json
import math
import os
import time

import bpy
from mathutils import Vector

from .. import config as C
from . import scene as S
from .controller import Character, world_position
from ..animation.blending import root_matrix

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path(p, base):
    if p is None:
        return None
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def make_prop(spec, coll):
    """oggetti semplici: sphere (palla), box (scatola), cylinder; colore e posizione."""
    import bmesh
    name = spec['name']; kind = spec.get('type', 'box')
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    if kind == 'sphere':
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=spec.get('radius', 0.06))
    elif kind == 'cylinder':
        r = spec.get('radius', 0.05); h = spec.get('height', 0.15)
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r, radius2=r, depth=h)
    else:
        sx, sy, sz = spec.get('size', (0.3, 0.3, 0.4))
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= sx; v.co.y *= sy; v.co.z *= sz
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = kind != 'box'
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    loc = list(spec.get('location', (0, 0, 0)))
    if kind == 'box' and len(loc) == 3 and spec.get('on_floor', True):
        loc[2] = max(loc[2], spec.get('size', (0.3, 0.3, 0.4))[2] / 2)
    ob.location = loc
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*S._hex_lin(spec.get('color', '#E63946')), 1)
    b.inputs['Roughness'].default_value = spec.get('roughness', 0.45)
    me.materials.append(m)
    return ob


def _target(v, chars, props):
    if isinstance(v, str):
        if v == 'camera':
            return 'camera'
        if v in chars:
            return chars[v]
        if v in props:
            return world_position(props[v])
        raise ValueError('bersaglio sconosciuto: %s' % v)
    return tuple(v)


def run_actions(ch, actions, chars, props, base):
    for a in actions:
        a = dict(a)
        if 'play' in a:
            name = a.pop('play')
            for k in ('target', 'obj', 'box'):
                if k in a:
                    a[k] = _target(a[k], chars, props)
            ch.play(name, **a)
        elif 'wait' in a:
            ch.wait(a['wait'])
        elif 'turn' in a:
            ch.turn(a['turn'])
        elif 'walk_to' in a:
            ch.walk_to(a['walk_to'], gait=a.get('gait', 'walk'), stop=a.get('stop', True))
        elif 'expression' in a:
            ch.set_expression(a['expression'], at=a.get('at'), duration=a.get('duration'), intensity=a.get('intensity', 1.0),
                              fade=a.get('fade', 0.2))
        elif 'look_at' in a:
            ch.look_at(_target(a['look_at'], chars, props), at=a.get('at'), duration=a.get('duration'), fade=a.get('fade', 0.3))
        elif 'look_forward' in a:
            ch.look_forward(at=a.get('at'))
        elif 'say' in a:
            ch.say(a['say'], at=a.get('at'), duration=a.get('duration'), words=a.get('words'), strength=a.get('strength', 1.0))
        elif 'pick_up' in a:
            ch.pick_up(props[a['pick_up']])
        elif 'throw' in a:
            ch.throw(_target(a['throw'], chars, props))
        elif 'push' in a:
            ch.push(props[a['push']])
        elif 'pull' in a:
            ch.pull(props[a['pull']])
        elif 'sit' in a:
            ch.sit(a['sit'] if isinstance(a['sit'], (int, float)) and not isinstance(a['sit'], bool) else 0.22)
        elif 'point' in a:
            ch.point(_target(a['point'], chars, props))
        elif 'wave' in a:
            ch.wave()
        elif 'mocap' in a:
            ch.play_file(_path(a['mocap'], base), blend=a.get('blend', 0.3), frames=a.get('frames'),
                         in_place=a.get('in_place', False))
        else:
            raise ValueError('azione sconosciuta: %s' % a)


def smooth_path(chars, out_by_char, follow, n, half):
    ch = chars[follow]; out = out_by_char[follow]
    xs = []; ys = []
    for f in range(n):
        fr = out[min(f, len(out) - 1)]
        p = root_matrix(fr['pose']['root']).translation
        xs.append(p.x); ys.append(p.y)

    def sm(v):
        r = []
        for i in range(n):
            a = max(0, i - half); b = min(n, i + half + 1)
            r.append(sum(v[a:b]) / (b - a))
        return r
    return sm(xs), sm(ys)


def build(spec, base):
    sc = S.reset()
    stg = spec.get('stage', {})
    st = S.stage(sc, color=stg.get('color', '#E9E2D6'), wall=stg.get('wall', '#D9CFC0'), ambient=stg.get('ambient', 0.30))
    props = {p['name']: make_prop(p, st) for p in spec.get('props', [])}
    chars = {}
    for c in spec.get('characters', []):
        chars[c['name']] = Character(c['name'], c.get('variant', 'default'), location=tuple(c.get('location', (0, 0))),
                                     facing=c.get('facing', 0.0))
    # camera prima delle azioni: look_at('camera') la legge
    cam_spec = spec.get('camera', {})
    cam = S.camera(sc, st, tuple(cam_spec.get('location', (0.9, -3.2, 0.85))), tuple(cam_spec.get('target', (0, 0, 0.55))),
                   cam_spec.get('lens', 45))
    for c in spec.get('characters', []):
        run_actions(chars[c['name']], c.get('actions', []), chars, props, base)
    hold = spec.get('end_hold', 0.5)
    n = max(int(math.ceil((ch.tl.length + hold) * C.FPS)) + 1 for ch in chars.values())
    outs = {name: ch.bake(end_hold=max(0.0, (n - 1) / C.FPS - ch.tl.length - 1e-6)) for name, ch in chars.items()}
    sc.frame_start = 1; sc.frame_end = n
    # luci «cinema» (ed eventualmente camera) che seguono un personaggio
    follow = cam_spec.get('follow')
    light_rig = bpy.data.objects.new('Luci', None); st.objects.link(light_rig)
    cl = Vector(cam_spec.get('location', (0.9, -3.2, 0.85))); tg = Vector(cam_spec.get('target', (0, 0, 0.55)))
    lights = S.cinema_lights(st, tuple(tg), tuple(cl), side=spec.get('light_side', 1))
    for L in lights.values():
        L.parent = light_rig
    if follow:
        xs, ys = smooth_path(chars, outs, follow, n, int(cam_spec.get('smooth', 0.6) * C.FPS))
        off = cl - tg
        for f in range(n):
            p = Vector((xs[f], ys[f], 0.0))
            S.aim(cam, tuple(tg + p + off), tuple(tg + p), None, frame=f + 1)
            light_rig.location = p; light_rig.keyframe_insert('location', frame=f + 1)
    r = spec.get('render', {})
    S.setup_render(sc, *r.get('resolution', (540, 960)), samples=r.get('samples', 8))
    return sc, chars, props, n


def render(path, *args):
    args = list(args)
    base = os.path.dirname(os.path.abspath(path))
    with open(path) as fh:
        spec = json.load(fh)
    t0 = time.time()
    sc, chars, props, n = build(spec, base)
    print('scena %s: %d personaggi, %d fotogrammi (%.1f s), costruita in %.1f s'
          % (os.path.basename(path), len(chars), n, (n - 1) / C.FPS, time.time() - t0))
    if '--solo-cottura' in args:
        return 0
    if '--anteprima' in args:
        sc.render.resolution_percentage = 50; sc.eevee.taa_render_samples = 4
    budget = float(args[args.index('--budget') + 1]) if '--budget' in args else 1e9
    r = spec.get('render', {})
    name = os.path.splitext(os.path.basename(path))[0]
    out_dir = _path(r.get('output', os.path.join(C.OUT, 'scene', name)), base)
    tag = '%dx%d' % (sc.render.resolution_x * sc.render.resolution_percentage // 100,
                     sc.render.resolution_y * sc.render.resolution_percentage // 100)
    folder = os.path.join(out_dir, 'frames_' + tag)
    os.makedirs(folder, exist_ok=True)
    t1 = time.time(); done = 0; left = 0
    for f in range(1, n + 1):
        p = os.path.join(folder, 'f%04d.png' % f)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        if time.time() - t1 > budget:
            left += 1
            continue
        sc.frame_set(f); sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        done += 1
    print('resi %d fotogrammi, ne mancano %d' % (done, left))
    if left == 0:
        video = os.path.join(out_dir, '%s_%s.mp4' % (name, tag))
        S.encode(folder, video, C.FPS, 1, _path(r.get('audio'), base))
        print('video:', video)
    return 0
