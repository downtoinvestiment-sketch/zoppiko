"""Renders of Zop and Piko for the brand kit (transparent PNG):
brand/renders/avatar_duo.png (heads together, for the profile picture) and brand/renders/banner_duo.png (full bodies).

    python3 tools/brand_renders.py
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from zk import scene as Z                                     # noqa: E402
import bpy                                                    # noqa: E402
from cartoon_character.automation import scene as S          # noqa: E402
from cartoon_character.automation.controller import Character  # noqa: E402

OUT = os.path.join(ROOT, 'brand', 'renders')
os.makedirs(OUT, exist_ok=True)


def setup(res, cam_loc, cam_tg, lens):
    sc = S.reset()
    st = bpy.data.collections.new('ZK_Stage'); sc.collection.children.link(st)
    Z.sky_world(sc)
    cam = S.camera(sc, st, cam_loc, cam_tg, lens)
    Z.daylight(st, cam_tg, cam_loc, sun=3.4, azimuth=-30, elevation=40, rim=220)
    S.setup_render(sc, res[0], res[1], samples=12)
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    return sc, st


def avatar():
    sc, st = setup((1080, 1080), (0.0, -1.62, 0.90), (0.0, 0.0, 0.86), 50)
    zop = Character('Zop', 'zop', location=(-0.215, 0.0), facing=8)
    piko = Character('Piko', 'piko', location=(0.215, 0.0), facing=-8)
    for ch, ex in ((zop, 'joy'), (piko, 'smug')):
        ch.wait(1.2)
        ch.set_expression(ex, at=0.0)
        ch.look_at('camera', at=0.0)
        ch.bake()
    sc.frame_set(20)
    S.render_still(sc, os.path.join(OUT, 'avatar_duo.png'))


def banner():
    sc, st = setup((2000, 1100), (0.0, -4.6, 0.62), (0.0, 0.0, 0.55), 50)
    zop = Character('Zop', 'zop', location=(-0.95, 0.0), facing=18)
    piko = Character('Piko', 'piko', location=(0.95, 0.0), facing=-18)
    zop.wait(0.3); zop.play('wave'); zop.set_expression('happy', at=0.0); zop.look_at('camera', at=0.0)
    piko.wait(0.3); piko.play('celebrate'); piko.set_expression('joy', at=0.0); piko.look_at('camera', at=0.0)
    zop.bake(end_hold=1.0); piko.bake(end_hold=1.0)
    for f, name in ((int(0.95 * 24), 'banner_a'), (int(1.15 * 24), 'banner_b')):
        sc.frame_set(f)
        S.render_still(sc, os.path.join(OUT, name + '.png'))


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('all', 'avatar'):
        avatar()
    if what in ('all', 'banner'):
        banner()
