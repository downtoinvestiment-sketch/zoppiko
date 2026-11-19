"""Background scenarios for the author to choose from: same frame of an episode, different skies and grass.

    python3 tools/scenarios.py storyboards/P01_the_button/scene.json 2.3 out.jpg
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from zk import scene as Z      # noqa: E402
import bpy                     # noqa: E402
from PIL import Image, ImageDraw, ImageFont   # noqa: E402

SCEN = [
    ('A', 'Now: pastel sky, smooth lawn', {}, {}),
    ('B', 'Clear blue sky, lush grass', {'hdri': {'id': 'kloofendal_43d_clear_puresky', 'strength': 2.0}, 'grass_texture': {'id': 'Grass005', 'size': 0.9}}, {}),
    ('C', 'Fluffy clouds, lush grass', {'hdri': {'id': 'kloofendal_48d_partly_cloudy_puresky', 'strength': 2.0, 'rotation': 40}, 'grass_texture': {'id': 'Grass005', 'size': 0.9}}, {}),
    ('D', 'Fluffy clouds, short lawn', {'hdri': {'id': 'kloofendal_48d_partly_cloudy_puresky', 'strength': 2.0, 'rotation': 140}, 'grass_texture': {'id': 'Grass004', 'size': 0.7}}, {}),
    ('E', 'Golden hour, lush grass', {'hdri': {'id': 'sunflowers_puresky', 'strength': 1.9}, 'grass_texture': {'id': 'Grass005', 'size': 0.9}}, {'sun': 2.8}),
]


def main(scene_path, t, out, wide=False):
    spec0 = json.load(open(scene_path))
    tiles = []
    for key, label, stage, light in SCEN:
        spec = copy.deepcopy(spec0)
        spec['stage'] = dict(spec.get('stage', {}), **stage)
        spec['light'] = dict(spec.get('light', {}), **light)
        if wide:
            spec['camera']['shots'] = [{"t": 0, "location": [0.0, -7.4, 1.6], "target": [0.0, 0.0, 0.25], "lens": 40}]
        sc, chars, props, n, ev = Z.build(spec, os.path.dirname(scene_path))
        sc.render.resolution_percentage = 50; sc.eevee.taa_render_samples = 6
        f = int(round(t * Z.FPS)) + 1; sc.frame_set(f)
        p = '/tmp/scen_%s%s.jpg' % (key, '_wide' if wide else '')
        sc.render.filepath = p; bpy.ops.render.render(write_still=True)
        tiles.append((key, label, p))
    ims = [Image.open(p) for _, _, p in tiles]
    w, h = ims[0].size; tw = 400; th = int(h * tw / w)
    sheet = Image.new('RGB', (len(ims) * (tw + 14) + 14, th + 90), (255, 241, 220)); d = ImageDraw.Draw(sheet)
    fb = ImageFont.truetype(os.path.join(ROOT, 'brand', 'fonts', 'Poppins-Black.ttf'), 30)
    fs = ImageFont.truetype(os.path.join(ROOT, 'brand', 'fonts', 'Poppins-Black.ttf'), 15)
    for i, ((key, label, _), im) in enumerate(zip(tiles, ims)):
        x = 14 + i * (tw + 14)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, 14))
        d.text((x + 4, th + 22), key, font=fb, fill=(31, 44, 82)); d.text((x + 40, th + 34), label, font=fs, fill=(31, 44, 82))
    sheet.save(out, quality=90); print(out, sheet.size)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], float(a[1]), a[2], wide='--wide' in a)
