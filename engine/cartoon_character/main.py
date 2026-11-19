"""Riga di comando della pipeline del personaggio cartoon.

    python3 cartoon_character/main.py build [variante]          # costruisce il personaggio e salva assets/models/<nome>.blend
    python3 cartoon_character/main.py library                   # elenca i movimenti e le espressioni
    python3 cartoon_character/main.py test [rig|motions|api|retarget]   # test automatici + rapporto in out/test_report.json
    python3 cartoon_character/main.py validate [--solo-misure]  # scena di prova della Fase 8 (misure + video, si riprende)
    python3 cartoon_character/main.py render scena.json         # una scena descritta in JSON (vedi docs/SCENE_JSON.md)
    python3 cartoon_character/main.py retarget file.bvh|fbx     # prova un'animazione esterna sul personaggio (misure)
    python3 cartoon_character/main.py sheets                    # schede: giro attorno ed espressioni

Si lancia con il Python che ha il modulo bpy (in questo ambiente: python3).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cartoon_character import config as C  # noqa: E402


def cmd_build(args):
    import bpy
    from cartoon_character.automation import scene as S
    from cartoon_character.character.builder import build
    variant = args[0] if args else 'default'
    S.reset()
    t0 = time.time()
    h = build(C.NAME, variant)
    os.makedirs(os.path.join(C.ASSETS, 'models'), exist_ok=True)
    path = os.path.join(C.ASSETS, 'models', '%s_%s.blend' % (C.NAME.lower(), variant))
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print('salvato', path, 'in %.1f s' % (time.time() - t0))


def cmd_library(args):
    import bpy  # noqa: F401  (mathutils arriva con bpy)
    from cartoon_character.animation import motion_library as ML
    for cat, names in ML.LIBRARY.items():
        print(cat + ':', ', '.join(names))
    print('espressioni:', ', '.join(sorted(C.EXPRESSIONS)))


def cmd_test(args):
    import unittest
    from cartoon_character.tests import shared
    suites = args or ['rig', 'motions', 'api', 'retarget']
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for s in suites:
        suite.addTests(loader.loadTestsFromName('cartoon_character.tests.test_' + s))
    t0 = time.time()
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    os.makedirs(C.OUT, exist_ok=True)
    rep = dict(shared.REPORT)
    rep['_riassunto'] = dict(eseguiti=res.testsRun, falliti=len(res.failures), errori=len(res.errors), saltati=len(res.skipped),
                             secondi=round(time.time() - t0, 1),
                             fallimenti=[str(t[0]) + ': ' + t[1].strip().splitlines()[-1] for t in res.failures + res.errors])
    path = os.path.join(C.OUT, 'test_report_%s.json' % '_'.join(suites))
    with open(path, 'w') as fh:
        json.dump(rep, fh, indent=1, default=str, ensure_ascii=False)
    print('rapporto:', path)
    return 0 if res.wasSuccessful() else 1


def cmd_validate(args):
    from cartoon_character.tests import validate
    validate.main(args)


def cmd_render(args):
    from cartoon_character.automation import scene_json
    scene_json.render(args[0], *args[1:])


def cmd_retarget(args):
    """trasferisce un file BVH/FBX sul personaggio e stampa mappatura e misure (niente render)."""
    import bpy  # noqa: F401
    from cartoon_character.tests import shared, metrics as MT
    from cartoon_character.animation import retarget as RT
    from cartoon_character.animation.blending import Timeline
    ch = shared.character()
    clip, mapping = RT.load(args[0], ch.ctx)
    tl = Timeline(ch.ctx, seed=1); tl.add(clip, clip.duration, 0.0)
    out = tl.evaluate_all()
    fs = MT.foot_slide(ch.ctx, out); fl = MT.floor_penetration(ch.ctx, out); pj = MT.pose_jumps(out)
    print('ossa mappate (%d):' % len(mapping), ', '.join('%s<-%s' % kv for kv in sorted(mapping.items())))
    print('sorgente:', clip.source)
    print('durata %.2f s, scivolamento piedi %s cm, suola minima %.2f cm, scatto max %.1f gradi (%s)' % (
        clip.duration, {k: round(v['max_cm'], 2) for k, v in fs.items()}, fl['min_cm'], pj['max_deg'], pj['bone']))


def cmd_sheets(args):
    import runpy
    sys.argv = ['sheets', '--'] + (args or ['all'])
    runpy.run_path(os.path.join(HERE, 'tools', 'sheets.py'), run_name='__main__')


if __name__ == '__main__':
    argv = [a for a in sys.argv[1:] if a != '--']
    if not argv:
        print(__doc__)
        sys.exit(0)
    cmd = {'build': cmd_build, 'library': cmd_library, 'test': cmd_test, 'validate': cmd_validate, 'render': cmd_render,
           'sheets': cmd_sheets, 'retarget': cmd_retarget}.get(argv[0])
    if cmd is None:
        print(__doc__); sys.exit(1)
    sys.exit(cmd(argv[1:]) or 0)
