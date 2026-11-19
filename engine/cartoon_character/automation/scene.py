"""Scena di lavoro: studio con fondale curvo, luce «cinema» (principale calda di lato con ombre nette, riempimento freddo
debole, controluce azzurro, poca luce ambiente), camera e render Eevee.
"""
import math
import os
import subprocess
import bpy
import bmesh
from mathutils import Vector

from .. import config as C


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def setup_render(sc, w=540, h=960, samples=8, fps=C.FPS):
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.eevee.taa_render_samples = samples
    sc.eevee.shadow_ray_count = 2
    sc.eevee.shadow_resolution_scale = 0.5
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Punchy'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False


def _hex_lin(h):
    c = C.hexrgb(h)
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def stage(sc, color='#E9E2D6', wall='#D9CFC0', ambient=0.30, size=8.0):
    """pavimento + fondale curvo (ciclorama) dietro al personaggio."""
    coll = bpy.data.collections.new('Studio')
    sc.collection.children.link(coll)
    w = bpy.data.worlds.new('Studio'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*_hex_lin('#BFC8D6'), 1); bg.inputs['Strength'].default_value = ambient
    me = bpy.data.meshes.new('Ciclorama'); bm = bmesh.new()
    nx, ny = 32, 40
    R = 1.2; depth = 3.0
    rows = []
    for j in range(ny + 1):
        t = j / ny
        L = 6.0 + depth + R * math.pi / 2 + 4.0
        s = t * L
        if s < 6.0 + depth:
            y, z = -6.0 + s, 0.0
        elif s < 6.0 + depth + R * math.pi / 2:
            a = (s - 6.0 - depth) / R
            y, z = depth + R * math.sin(a), R * (1 - math.cos(a))
        else:
            y, z = depth + R, R + (s - 6.0 - depth - R * math.pi / 2)
        row = [bm.verts.new((-size + 2 * size * i / nx, y, z)) for i in range(nx + 1)]
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('Ciclorama', me); coll.objects.link(ob)
    m = bpy.data.materials.new('Studio_fondale'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*_hex_lin(color), 1); b.inputs['Roughness'].default_value = 0.85
    me.materials.append(m)
    return coll


def _light(coll, name, kind, pos, target, energy, color, shadow=True, **kw):
    L = bpy.data.lights.new(name, kind); L.energy = energy; L.color = color; L.use_shadow = shadow
    for k, v in kw.items():
        setattr(L, k, v)
    o = bpy.data.objects.new(name, L); coll.objects.link(o); o.location = pos
    o.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    return o


def cinema_lights(coll, subject=(0, 0, 0.6), camera=(1.2, -3.2, 1.0), side=1, power=1.0):
    """tre luci attorno al soggetto, pensate per quella camera (come scripts/luci.py di Pippo e Tumbo)."""
    s = Vector(subject); c = Vector(camera)
    d = Vector((c.x - s.x, c.y - s.y, 0)).normalized()
    r = Vector((-d.y, d.x, 0)) * side
    a = math.radians(32)
    key = _light(coll, 'Chiave', 'SPOT', s + (d * math.cos(a) + r * math.sin(a)) * 3.2 + Vector((0, 0, 1.9)), s,
                 620 * power, (1.0, 0.80, 0.58), True, spot_size=1.1, spot_blend=0.6, shadow_soft_size=0.06)
    fill = _light(coll, 'Riempimento', 'AREA', s + (d * 0.8 - r * 0.7) * 3.0 + Vector((0, 0, 0.8)), s,
                  60 * power, (0.72, 0.84, 1.0), False, size=2.5)
    rim = _light(coll, 'Controluce', 'AREA', s + (-d * 0.9 - r * 0.5) * 2.2 + Vector((0, 0, 1.6)), s + Vector((0, 0, 0.35)),
                 260 * power, (0.62, 0.78, 1.0), False, size=1.2)
    return dict(key=key, fill=fill, rim=rim)


def camera(sc, coll, loc, target, lens=50.0):
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    coll.objects.link(cam); sc.camera = cam
    aim(cam, loc, target, lens)
    return cam


def aim(cam, loc, target, lens=None, frame=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if lens:
        cam.data.lens = lens
    if frame is not None:
        cam.keyframe_insert('location', frame=frame); cam.keyframe_insert('rotation_euler', frame=frame)
        cam.data.keyframe_insert('lens', frame=frame)


def render_still(sc, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def render_frames(sc, folder, f0, f1, resume=True):
    """rende i fotogrammi f0..f1 in folder/f####.png; se resume salta quelli gia' fatti."""
    os.makedirs(folder, exist_ok=True)
    done = 0
    for f in range(f0, f1 + 1):
        p = os.path.join(folder, 'f%04d.png' % f)
        if resume and os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        sc.frame_set(f)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        done += 1
    return done


def encode(folder, out, fps=C.FPS, f0=1, audio=None):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-start_number', str(f0),
           '-i', os.path.join(folder, 'f%04d.png')]
    if audio:
        cmd += ['-i', audio, '-shortest']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'veryfast', out]
    subprocess.run(cmd, check=True)
    return out
