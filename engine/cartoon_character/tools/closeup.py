"""Primi piani di controllo: viso e mano."""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from mathutils import Vector
from cartoon_character import config as C
from cartoon_character.character.builder import build
from cartoon_character.automation import scene as S
out = os.path.join(C.OUT, 'sheet')
sc = S.reset(); S.setup_render(sc, 420, 420, 8)
st = S.stage(sc)
ch = build(C.NAME, 'default')
cam = S.camera(sc, st, (0, -3.2, 0.62), (0, 0, 0.56), 50)
S.cinema_lights(st, (0, 0, 0.6), (0.9, -3.2, 0.9))
shots = [((0.25, -1.1, 0.86), (0, 0, 0.82), 50), ((0.75, -0.55, 0.50), (0.33, 0, 0.42), 50)]
files = []
for i, (loc, tgt, lens) in enumerate(shots):
    S.aim(cam, loc, tgt, lens); files.append(S.render_still(sc, os.path.join(out, 'c%d.png' % i)))
from PIL import Image
ims = [Image.open(f) for f in files]; sheet = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
for im in ims: sheet.paste(im, (x, 0)); x += im.width
sheet.save(os.path.join(out, 'primi_piani.png')); print('ok')
