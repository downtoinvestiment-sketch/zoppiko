"""Render a ZOPPIKO scene file. See zk/scene.py for the options."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zk import scene as Z                     # noqa: E402
import bpy                                    # noqa: E402

ROOT = Z.ROOT


def main(argv):
    path = os.path.abspath(argv[0]); args = argv[1:]
    base = os.path.dirname(path)
    spec = json.load(open(path))
    name = spec.get('name', os.path.basename(base))
    out_dir = os.path.join(ROOT, 'renders', name)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    sc, chars, props, n, events = Z.build(spec, base)
    json.dump(dict(name=name, fps=Z.FPS, frames=n, duration=round((n) / Z.FPS, 3), marks=Z.LAST_MARKS, events=events),
              open(os.path.join(out_dir, 'events.json'), 'w'), indent=1)
    print('%s: %d frames (%.2f s), built in %.1f s' % (name, n, n / Z.FPS, time.time() - t0))
    if '--bake-only' in args:
        return 0
    if '--stills' in args:
        times = [float(x) for x in args[args.index('--stills') + 1].split(',')]
        pct = int(args[args.index('--pct') + 1]) if '--pct' in args else 40
        sc.render.resolution_percentage = pct; sc.eevee.taa_render_samples = 4
        folder = os.path.join(out_dir, 'stills'); os.makedirs(folder, exist_ok=True)
        for t in times:
            f = min(n, int(round(t * Z.FPS)) + 1)
            sc.frame_set(f); sc.render.filepath = os.path.join(folder, 's_%06.2f.jpg' % t)
            bpy.ops.render.render(write_still=True)
        print('stills:', folder)
        return 0
    if '--samples' in args:
        sc.eevee.taa_render_samples = int(args[args.index('--samples') + 1])
    if '--preview' in args:
        sc.render.resolution_percentage = 50; sc.eevee.taa_render_samples = 4
    budget = float(args[args.index('--budget') + 1]) if '--budget' in args else 1e9
    rng = None
    if '--frames' in args:
        a, b = args[args.index('--frames') + 1].split('-'); rng = (int(a), int(b))
    tag = '%dx%d' % (sc.render.resolution_x * sc.render.resolution_percentage // 100,
                     sc.render.resolution_y * sc.render.resolution_percentage // 100)
    folder = os.path.join(out_dir, 'frames_' + tag); os.makedirs(folder, exist_ok=True)
    t1 = time.time(); done = 0; left = 0
    f0, f1 = rng or (1, n)
    for f in range(f0, f1 + 1):
        p = os.path.join(folder, 'f%04d.jpg' % f)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        if time.time() - t1 > budget:
            left += 1
            continue
        sc.frame_set(f); sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        done += 1
        if done % 10 == 0:
            el = time.time() - t1
            print('frame %d/%d  %.1f s/frame' % (f, n, el / done), flush=True)
    missing = [f for f in range(1, n + 1) if not os.path.exists(os.path.join(folder, 'f%04d.jpg' % f))]
    print('rendered %d frames, %d missing' % (done, len(missing)))
    if not missing:
        import subprocess
        video = os.path.join(out_dir, '%s_%s_silent.mp4' % (name, tag))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(Z.FPS), '-i', os.path.join(folder, 'f%04d.jpg'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'veryfast', video], check=True)
        print('video:', video)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
