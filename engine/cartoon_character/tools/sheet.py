"""Foglio del personaggio: quattro viste a riposo (davanti, tre quarti, lato, dietro)."""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from mathutils import Vector
from cartoon_character import config as C
from cartoon_character.character.builder import build
from cartoon_character.automation import scene as S

out = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else os.path.join(C.OUT, 'sheet')
variant = sys.argv[sys.argv.index('--') + 2] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 2 else 'default'
sc = S.reset(); S.setup_render(sc, 360, 560, 8)
st = S.stage(sc)
import time; t0 = time.time()
ch = build(C.NAME, variant)
print('build', round(time.time() - t0, 2), 's', 'poles', {k: v[1] for k, v in ch['poles'].items()})
cam = S.camera(sc, st, (0, -3.2, 0.62), (0, 0, 0.56), 50)
L = S.cinema_lights(st, (0, 0, 0.6), (0.9, -3.2, 0.9))
files = []
for i, ang in enumerate((0, 35, 90, 180)):
    a = math.radians(ang)
    pos = Vector((3.0 * math.sin(a), -3.0 * math.cos(a), 0.66))
    S.aim(cam, pos, (0, 0, 0.56), 50)
    f = S.render_still(sc, os.path.join(out, 'v%d.png' % i)); files.append(f)
from PIL import Image
ims = [Image.open(f) for f in files]
W = sum(im.width for im in ims); H = ims[0].height
sheet = Image.new('RGB', (W, H), (255, 255, 255)); x = 0
for im in ims:
    sheet.paste(im, (x, 0)); x += im.width
sheet.save(os.path.join(out, 'foglio.png')); print('ok', os.path.join(out, 'foglio.png'), round(time.time() - t0, 1))
