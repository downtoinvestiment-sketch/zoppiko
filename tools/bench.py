"""Render speed test: one frame of a scene under different Eevee settings.

    python3 tools/bench.py storyboards/P04_domino_day/scene.json 4.0
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zk import scene as Z                     # noqa: E402
import bpy                                    # noqa: E402


def main(path, t):
    spec = json.load(open(path))
    sc, chars, props, n, events = Z.build(spec, os.path.dirname(os.path.abspath(path)))
    f = min(n, int(round(t * Z.FPS)) + 1)
    sc.frame_set(f)
    ee = sc.eevee
    print('eevee settings:', {k: getattr(ee, k) for k in dir(ee) if k.startswith(('use_', 'shadow', 'ray', 'fast_gi', 'horizon'))
                              and not callable(getattr(ee, k))})
    base = dict(taa_render_samples=6, shadow_ray_count=2, shadow_resolution_scale=0.5)
    variants = [('baseline', {}, 100), ('samples4', dict(taa_render_samples=4), 100), ('720p', {}, 67),
                ('shadowray1', dict(shadow_ray_count=1), 100), ('shadowres025', dict(shadow_resolution_scale=0.25), 100)]
    out = '/tmp/zk_bench'; os.makedirs(out, exist_ok=True)
    sc.render.resolution_percentage = 25; sc.render.filepath = os.path.join(out, 'warmup.jpg')
    bpy.ops.render.render(write_still=True)                  # shaders compile here, not in the timings
    for name, ch, pct in variants:
        for k, v in base.items():
            setattr(ee, k, v)
        for k, v in ch.items():
            setattr(ee, k, v)
        sc.render.resolution_percentage = pct
        sc.render.filepath = os.path.join(out, '%s.jpg' % name)
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print('BENCH %-14s %.1f s' % (name, time.time() - t0), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]))
