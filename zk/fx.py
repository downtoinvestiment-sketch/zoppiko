"""Cartoon effects for ZOPPIKO scenes.

- billboard(): flat glowing image that always faces the camera (dust puffs, sparkles). Adapted from the effect
  function of the Pippo e Tumbo asset library (assets/pt_assets.py, CC0 images from Kenney).
- stars(): small yellow 3D cartoon stars circling above a head (dizzy), or bursting out (impact).

Scene file:  "fx": [{"t": 0.57, "type": "puff", "at": [0, -0.1, 0.05], "size": 0.5, "dur": 0.6},
                    {"t": "p1+1.58", "type": "sparkle", "at": [0.3, 0, 1.0], "size": 0.6, "dur": 0.3},
                    {"t": "p1+1.7", "type": "dizzy", "at": [0.3, 0.05, 0.7], "dur": 2.4},
                    {"t": "p1+1.58", "type": "burst", "at": [0.3, 0, 1.05], "dur": 0.6}]
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, 'world', 'fx')
FPS = 24


def _lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def billboard(file, loc, width=1.0, color=None, light=1.0, frame=None, dur=12, coll=None, opacity=1.0, rot=0.0):
    img = bpy.data.images.load(file, check_existing=True)
    w, h = width / 2, width * img.size[1] / max(1, img.size[0]) / 2
    a = math.radians(rot); ca, sa = math.cos(a), math.sin(a)
    me = bpy.data.meshes.new('ZK_fx')
    me.from_pydata([(x * ca - y * sa, x * sa + y * ca, 0) for x, y in ((-w, -h), (w, -h), (w, h), (-w, h))], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for i, co in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = co
    key = 'ZK_fx_%s_%s_%.2f' % (os.path.basename(file), color, light)
    mat = bpy.data.materials.get(key)
    if not mat:
        mat = bpy.data.materials.new(key); mat.use_nodes = True
        nt = mat.node_tree; nt.nodes.clear()
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
        emi = nt.nodes.new('ShaderNodeEmission'); emi.inputs['Strength'].default_value = light
        if color:
            mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0
            nt.links.new(tex.outputs['Color'], mix.inputs[6])
            mix.inputs[7].default_value = (*_lin(color), 1.0)
            nt.links.new(mix.outputs[2], emi.inputs['Color'])
        else:
            nt.links.new(tex.outputs['Color'], emi.inputs['Color'])
        info = nt.nodes.new('ShaderNodeObjectInfo')
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
        nt.links.new(tex.outputs['Alpha'], mul.inputs[0]); nt.links.new(info.outputs['Alpha'], mul.inputs[1])
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); ms = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(mul.outputs[0], ms.inputs[0]); nt.links.new(tr.outputs[0], ms.inputs[1]); nt.links.new(emi.outputs[0], ms.inputs[2])
        out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(ms.outputs[0], out.inputs['Surface'])
        try:
            mat.surface_render_method = 'BLENDED'
        except Exception:
            pass
    me.materials.append(mat)
    ob = bpy.data.objects.new('ZK_fx_' + os.path.splitext(os.path.basename(file))[0], me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc; ob.color = (1, 1, 1, opacity); ob.visible_shadow = False
    cam = bpy.context.scene.camera
    if cam:
        con = ob.constraints.new('COPY_ROTATION'); con.target = cam
    if frame is not None:
        prefs = bpy.context.preferences.edit; prefs.keyframe_new_interpolation_type = 'BEZIER'
        dur = max(3, int(dur))
        for f, s, al in ((frame - 1, 0.0, opacity), (frame, 0.35, opacity), (frame + round(dur * 0.4), 1.0, opacity),
                         (frame + dur, 1.25, 0.0), (frame + dur + 1, 0.0, 0.0)):
            ob.scale = (s, s, s); ob.color = (1, 1, 1, al)
            ob.keyframe_insert('scale', frame=max(1, f)); ob.keyframe_insert('color', frame=max(1, f))
    return ob


def star_mesh(r=0.075, depth=0.022, points=5, inner=0.48):
    bm = bmesh.new()
    top, bot = [], []
    for i in range(points * 2):
        a = math.pi / 2 + math.pi * i / points
        rr = r if i % 2 == 0 else r * inner
        top.append(bm.verts.new((rr * math.cos(a), depth / 2, rr * math.sin(a))))
        bot.append(bm.verts.new((rr * math.cos(a), -depth / 2, rr * math.sin(a))))
    ct = bm.verts.new((0, depth, 0)); cb = bm.verts.new((0, -depth, 0))
    n = len(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top[i], top[j], ct)); bm.faces.new((bot[j], bot[i], cb))
        bm.faces.new((top[j], top[i], bot[i], bot[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('ZK_star'); bm.to_mesh(me); bm.free()
    return me


def star_material():
    m = bpy.data.materials.get('ZK_star_mat')
    if m:
        return m
    m = bpy.data.materials.new('ZK_star_mat'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*_lin((1.0, 0.82, 0.18)), 1)
    b.inputs['Emission Color'].default_value = (*_lin((1.0, 0.85, 0.25)), 1)
    b.inputs['Emission Strength'].default_value = 0.9
    b.inputs['Roughness'].default_value = 0.4
    return m


def stars(center, t0, dur, coll, n=3, radius=0.17, height=0.05, burst=False, n_frames=10000):
    """dizzy: n stars orbit above a head for dur seconds. burst: stars fly outward and fade in dur seconds."""
    prefs = bpy.context.preferences.edit
    rnd = random.Random(int(t0 * 100))
    c = Vector(center); f0 = int(round(t0 * FPS)) + 1; f1 = f0 + int(dur * FPS)
    me = star_mesh(); mat = star_material()
    for k in range(n):
        ob = bpy.data.objects.new('ZK_star', me.copy()); ob.data.materials.append(mat)
        coll.objects.link(ob); ob.visible_shadow = False
        prefs.keyframe_new_interpolation_type = 'CONSTANT'
        ob.hide_render = True; ob.keyframe_insert('hide_render', frame=1)
        ob.hide_render = False; ob.keyframe_insert('hide_render', frame=f0)
        ob.hide_render = True; ob.keyframe_insert('hide_render', frame=f1 + 1)
        prefs.keyframe_new_interpolation_type = 'LINEAR'
        if burst:
            a = 2 * math.pi * k / n + rnd.uniform(-0.3, 0.3)
            d = Vector((math.cos(a), rnd.uniform(-0.3, 0.1), math.sin(a) * 0.8 + 0.25)).normalized()
        for f in range(f0, f1 + 1):
            u = (f - f0) / FPS
            if burst:
                k_ = u / dur
                pos = c + d * (0.42 * (1 - (1 - k_) ** 2))
                s = (1.0 - k_) * 1.2 + 0.2
                rot = (0, u * 9 + k, 0)
            else:
                a = 2 * math.pi * (k / n + u * 1.1)
                pos = c + Vector((radius * math.cos(a), radius * 0.45 * math.sin(a), height * math.sin(a * 2)))
                s = 1.0 if (f - f0) > 3 and (f1 - f) > 3 else 0.4
                rot = (0, u * 4 + k, 0)
            ob.location = pos; ob.scale = (s, s, s); ob.rotation_euler = rot
            ob.keyframe_insert('location', frame=f); ob.keyframe_insert('scale', frame=f); ob.keyframe_insert('rotation_euler', frame=f)


def add(spec_fx, coll, resolve):
    """build every effect listed in the scene file; returns the sound cues they imply."""
    cues = []
    for e in spec_fx:
        t = resolve(e['t']); f = int(round(t * FPS)) + 1; kind = e['type']
        at = Vector(e.get('at', (0, 0, 0)))
        if kind == 'puff':
            rnd = random.Random(f)
            for i in range(e.get('count', 2)):
                dx = (i - (e.get('count', 2) - 1) / 2) * e.get('spread', 0.32)
                billboard(os.path.join(FX, 'whitepuff0%d.png' % rnd.randint(0, 5)), at + Vector((dx, 0, 0)),
                          e.get('size', 0.4) * rnd.uniform(0.85, 1.1), color=e.get('color', (1.0, 0.97, 0.9)),
                          light=e.get('light', 1.1), frame=f + i, dur=e.get('dur', 0.6) * FPS, coll=coll, rot=rnd.uniform(0, 360),
                          opacity=e.get('opacity', 0.9))
        elif kind == 'sparkle':
            billboard(os.path.join(FX, 'star_06.png'), at, e.get('size', 0.6), color=e.get('color', (1.0, 0.95, 0.7)),
                      light=e.get('light', 2.0), frame=f, dur=e.get('dur', 0.3) * FPS, coll=coll)
        elif kind == 'dizzy':
            stars(at, t, e.get('dur', 2.0), coll, n=e.get('count', 3), radius=e.get('radius', 0.17))
        elif kind == 'burst':
            stars(at, t, e.get('dur', 0.6), coll, n=e.get('count', 6), burst=True)
    return cues
