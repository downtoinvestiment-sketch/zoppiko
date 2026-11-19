"""Schede del personaggio: giro attorno (4 viste) ed espressioni (primi piani), con la pipeline completa."""
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont
from cartoon_character import config as C
from cartoon_character.automation import scene as S
from cartoon_character.automation.controller import Character

what = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'all'
variant = sys.argv[sys.argv.index('--') + 2] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 2 else 'default'
out = os.path.join(C.OUT, 'sheet'); os.makedirs(out, exist_ok=True)
try:
    FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
except Exception:
    FONT = None

def grid(files, cols, labels, path, bg=(255, 255, 255)):
    ims = [Image.open(f).convert('RGB') for f in files]
    w, h = ims[0].size; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (w * cols, (h + 28) * rows), bg); d = ImageDraw.Draw(sheet)
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * w, (i // cols) * (h + 28)
        sheet.paste(im, (x, y + 28)); d.text((x + 8, y + 4), lab, fill=(30, 30, 30), font=FONT)
    sheet.save(path, quality=90); return path

sc = S.reset()
st = S.stage(sc)
ch = Character(C.NAME, variant)
cam = S.camera(sc, st, (0, -3.2, 0.62), (0, 0, 0.56), 50)
S.cinema_lights(st, (0, 0, 0.6), (0.9, -3.2, 0.9))
t0 = time.time()
if what in ('all', 'turn'):
    ch.play('idle', duration=1.0); ch.tl.blinks = False; ch.bake()
    sc.frame_set(1)
    S.setup_render(sc, 380, 600, 12)
    files = []
    for i, ang in enumerate((0, 35, 90, 180)):
        a = math.radians(ang)
        S.aim(cam, (3.0 * math.sin(a), -3.0 * math.cos(a), 0.66), (0, 0, 0.56), 50)
        files.append(S.render_still(sc, os.path.join(out, 'giro%d.png' % i)))
    print('giro', grid(files, 4, ['davanti', 'tre quarti', 'lato', 'dietro'], os.path.join(out, 'giro_%s.jpg' % variant)), round(time.time() - t0, 1))
if what in ('all', 'expr'):
    names = ['neutral', 'happy', 'joy', 'sad', 'angry', 'surprised', 'shocked', 'scared', 'confused', 'thinking', 'disgust',
             'embarrassed', 'smug', 'determined', 'sleepy', 'dizzy']
    ch2 = ch
    ch2.tl.clips.clear(); ch2.tl.expressions.clear()
    ch2.play('idle', duration=len(names) * 1.0 + 0.5)
    for i, n in enumerate(names):
        ch2.set_expression(n, at=i * 1.0, duration=0.8, fade=0.15)
    ch2.tl.blinks = False; ch2.tl.secondary = False
    ch2.bake()
    S.setup_render(sc, 320, 320, 12)
    files = []
    for i, n in enumerate(names):
        sc.frame_set(int((i * 1.0 + 0.6) * C.FPS) + 1)
        S.aim(cam, (0.30, -1.15, 0.92), (0, 0, 0.86), 50)
        files.append(S.render_still(sc, os.path.join(out, 'e_%s.png' % n)))
    print('espressioni', grid(files, 4, names, os.path.join(out, 'espressioni_%s.jpg' % variant)), round(time.time() - t0, 1))
