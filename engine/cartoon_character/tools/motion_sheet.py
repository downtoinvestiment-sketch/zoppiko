"""Scheda dei movimenti: per ogni movimento 4 istanti, renderizzati in piccolo (controllo visivo veloce)."""
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from mathutils import Vector, Matrix
from cartoon_character import config as C
from cartoon_character.automation import scene as S
from cartoon_character.automation.controller import Character
from cartoon_character.animation import motion_library as ML
from cartoon_character.animation.blending import Timeline, root_matrix

def apply_pose(rig, fr):
    for pb in rig.pose.bones:
        bp = fr['pose'].get(pb.name)
        if bp is None:
            pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
        else:
            pb.location = bp.loc; pb.rotation_quaternion = bp.rot; pb.scale = bp.scl
    for k, v in fr['props'].items():
        rig.pose.bones['face'][k] = v
    rig.data.update_tag() if hasattr(rig.data, 'update_tag') else None
    bpy.context.view_layer.update()

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['idle', 'walk', 'jump', 'surprise']
names = [a for a in args if not a.startswith('@')]
tag = ([a[1:] for a in args if a.startswith('@')] or ['sheet'])[0]
fracs = (0.12, 0.35, 0.58, 0.85)
sc = S.reset(); S.setup_render(sc, 260, 400, 4)
st = S.stage(sc)
ch = Character(C.NAME, 'default')
ch.rig.animation_data_clear() if ch.rig.animation_data else None
cam = S.camera(sc, st, (1.2, -3.0, 0.75), (0, 0, 0.5), 50)
S.cinema_lights(st, (0, 0, 0.6), (1.2, -3.0, 0.9))
out_dir = os.path.join(C.OUT, 'motions'); os.makedirs(out_dir, exist_ok=True)
from PIL import Image, ImageDraw
rows = []
t0 = time.time()
for nm in names:
    tl = Timeline(ch.ctx, seed=3)
    m = ML.make(nm, ch.ctx)
    d = m.duration if not getattr(m, 'loop', False) else (m.duration if m.duration > 1.5 else 2 * m.duration)
    tl.add(m, d, 0.0)
    out = tl.evaluate_all()
    ims = []
    for fr_ in fracs:
        f = min(len(out) - 1, int(fr_ * (len(out) - 1)))
        fr = out[f]
        apply_pose(ch.rig, fr)
        root = root_matrix(fr['pose']['root']).translation
        tgt = Vector((root.x, root.y, 0.5))
        S.aim(cam, tgt + Vector((1.1, -2.9, 0.25)), tgt, 50)
        p = S.render_still(sc, os.path.join(out_dir, '_tmp.png'))
        im = Image.open(p).convert('RGB'); d_ = ImageDraw.Draw(im)
        d_.text((6, 4), '%s %.2fs' % (nm, fr['t']), fill=(20, 20, 20))
        ims.append(im)
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height), (255, 255, 255)); x = 0
    for im in ims:
        row.paste(im, (x, 0)); x += im.width
    rows.append(row)
    print(nm, 'ok', round(time.time() - t0, 1), flush=True)
W = rows[0].width; H = sum(r.height for r in rows)
sheet = Image.new('RGB', (W, H)); y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height
path = os.path.join(out_dir, '%s.jpg' % tag); sheet.save(path, quality=88); print('saved', path)
