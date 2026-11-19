"""Fase 8: scena di prova del personaggio, con misure e video di anteprima.

    python3 cartoon_character/main.py validate                    # misure + anteprima (si riprende se interrotta)
    python3 cartoon_character/main.py validate --solo-misure      # solo le misure, senza render
    python3 cartoon_character/main.py validate --res 360x640 --samples 6 --budget 540

Una sola ripresa che segue il personaggio su un pavimento con tacche ogni 50 cm (servono a vedere se i piedi scivolano):
  1 camminata con espressione felice      (punto 8 della richiesta: movimento del corpo + espressione insieme)
  2 corsa, presa dalla camminata in corsa  (punto 7: transizione tra due movimenti, senza fermarsi)
    frenata automatica e giro verso la camera
  3 salto
  5 reazione di sorpresa
  4 caduta (si rialza da solo: lo stato «a terra» lo impone)
  6 danza con espressione felice

Uscite in out/validate/: report.json, REPORT.md, i fotogrammi (frames_<risoluzione>/) e validate_<risoluzione>.mp4.
Ogni comando rende al massimo per --budget secondi e poi si ferma: rilanciandolo riparte dal primo fotogramma mancante.
"""
import json
import math
import os
import subprocess
import sys
import time

import bpy
from mathutils import Vector, Matrix

from .. import config as C
from ..automation import scene as S
from ..automation.controller import Character
from ..animation.blending import root_matrix
from . import metrics as MT

OUT = os.path.join(C.OUT, 'validate')
# parti del corpo su cui valgono i limiti di deformazione; occhi, palpebre, bocca, lingua e denti cambiano forma per
# costruzione (shape keys, palpebre che ruotano, pupille che si dilatano) e le loro superfici aperte non hanno volume
BODY = ('head', 'nose', 'torso', 'arm.L', 'arm.R', 'hand.L', 'hand.R', 'leg.L', 'leg.R', 'shoe.L', 'shoe.R', 'curl')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
START = (-2.6, 0.0)


def parse(args):
    o = dict(res=(360, 640), samples=6, budget=540.0, render=True, deform_step=2)
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--solo-misure':
            o['render'] = False
        elif a == '--res':
            w, h = args[i + 1].lower().split('x'); o['res'] = (int(w), int(h)); i += 1
        elif a == '--samples':
            o['samples'] = int(args[i + 1]); i += 1
        elif a == '--budget':
            o['budget'] = float(args[i + 1]); i += 1
        i += 1
    return o


# ---------------------------------------------------------------- scena
def floor_marks(coll):
    """tacche scure sul pavimento ogni 50 cm, davanti e dietro il percorso: riferimenti fissi per lo scivolamento."""
    import bmesh
    me = bpy.data.meshes.new('Tacche'); bm = bmesh.new()

    def quad(x0, y0, x1, y1):
        vs = [bm.verts.new((x0, y0, 0.0015)), bm.verts.new((x1, y0, 0.0015)), bm.verts.new((x1, y1, 0.0015)), bm.verts.new((x0, y1, 0.0015))]
        bm.faces.new(vs)
    for k in range(-8, 9):
        x = k * 0.5
        quad(x - 0.006, 0.42, x + 0.006, 0.58)              # dietro il percorso
        quad(x - 0.006, -0.95, x + 0.006, -0.83)            # davanti
    quad(-4.2, 0.494, 4.2, 0.506)                           # riga lunga
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('Tacche', me); coll.objects.link(ob)
    m = bpy.data.materials.new('Tacche'); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.09, 0.085, 0.08, 1); b.inputs['Roughness'].default_value = 0.9
    me.materials.append(m)
    return ob


def build_sequence():
    """costruisce il personaggio e la sequenza; restituisce (personaggio, segmenti etichettati)."""
    ch = Character(C.NAME, 'default', location=START, facing=90)       # cammina verso +X, di profilo per la camera
    seg = []

    def last():
        return ch.tl.clips[-1]

    ch.play('idle', duration=1.0)
    ch.look_at('camera', at=0.0, duration=0.9, fade=0.25)
    ch.play('walk', duration=3.4)
    w = last()
    ch.set_expression('happy', at=w.start + 0.2, duration=w.duration + 0.6, fade=0.3)
    seg.append(('1', 'Camminata + viso felice', 'walk', w.start, w.end))
    ch.play('run', duration=2.2)
    r = last()
    seg.append(('7', 'Da camminata a corsa', 'transition', r.start - 0.3, r.start + r.blend + 0.3))
    seg.append(('2', 'Corsa', 'run', r.start, r.end))
    ch.play('turn', angle=-90)                                      # prima si ferma da solo (frenata di corsa)
    t = last()
    stop = [c for c in ch.tl.clips if c.name == 'stop'][-1]
    seg.append(('-', 'Frenata e giro', 'stop_turn', stop.start, t.end))
    ch.play('jump')
    j = last()
    seg.append(('3', 'Salto', 'jump', j.start, j.end))
    ch.play('surprise')
    s = last()
    seg.append(('5', 'Reazione: sorpresa', 'surprise', s.start, s.end))
    ch.play('fall')
    f = last()
    seg.append(('4', 'Caduta', 'fall', f.start, f.end))
    ch.play('dance', duration=3.2)                                  # da terra: prima «get_up» (stato del personaggio)
    g = [c for c in ch.tl.clips if c.name == 'get_up'][-1]
    seg.append(('-', 'Si rialza', 'get_up', g.start, g.end))
    d = last()
    ch.set_expression('happy', at=d.start, duration=d.duration + 0.5, fade=0.3)
    ch.look_at('camera', at=d.start + 0.4, duration=d.duration, fade=0.4)
    seg.append(('6', 'Danza + viso felice', 'dance', d.start, d.end))
    ch.play('idle', duration=0.9)
    return ch, seg


def smooth_path(out, half):
    xs = []; ys = []
    for fr in out:
        p = root_matrix(fr['pose']['root']).translation
        xs.append(p.x); ys.append(p.y)
    n = len(xs)

    def sm(v):
        r = []
        for i in range(n):
            a = max(0, i - half); b = min(n, i + half + 1)
            r.append(sum(v[a:b]) / (b - a))
        return r
    return sm(xs), sm(ys)


def setup_scene(o):
    sc = S.reset()
    st = S.stage(sc, ambient=0.28, size=8.0)
    floor_marks(st)
    ch, seg = build_sequence()
    out = ch.bake()
    n = len(out)
    sc.frame_start = 1; sc.frame_end = n
    # camera e luci seguono il personaggio con calma (media mobile di 1,2 s sul percorso)
    xs, ys = smooth_path(out, int(0.6 * C.FPS))
    cam = S.camera(sc, st, (START[0], -2.7, 0.78), (START[0], 0.0, 0.56), 45)
    rig = bpy.data.objects.new('Luci', None); st.objects.link(rig)
    lights = S.cinema_lights(st, (0, 0, 0.6), (0.0, -2.7, 0.72))
    for L in lights.values():
        L.parent = rig
    for f in range(n):
        x, y = xs[f], ys[f]
        S.aim(cam, (x, y - 2.7, 0.78), (x, y, 0.56), None, frame=f + 1)
        rig.location = (x, y, 0.0); rig.keyframe_insert('location', frame=f + 1)
    S.setup_render(sc, o['res'][0], o['res'][1], o['samples'])
    return sc, ch, seg, out


# ---------------------------------------------------------------- misure
def frames_of(a, b, n):
    return max(0, int(math.floor(a * C.FPS))), min(n - 1, int(math.ceil(b * C.FPS)))


def measure(sc, ch, seg, out, deform_step=2):
    ctx = ch.ctx; n = len(out)
    rep = dict(fotogrammi=n, durata_s=round((n - 1) / C.FPS, 2), segmenti=[], transizioni=[], limiti=C.LIMITS)

    def block(i0, i1):
        sl = out[i0:i1 + 1]
        fs = MT.foot_slide(ctx, sl); fl = MT.floor_penetration(ctx, sl); pj = MT.pose_jumps(sl); rj = MT.root_jumps(sl)
        col = MT.collisions(ctx, sl)
        return dict(fotogrammi=[i0 + 1, i1 + 1],
                    scivolamento_piedi_cm={k: round(v['max_cm'], 2) for k, v in fs.items()},
                    appoggi={k: v['intervals'] for k, v in fs.items()},
                    suola_minima_cm=round(fl['min_cm'], 2),
                    scatto_max_gradi=round(pj['max_deg'], 1), scatto_osso=pj['bone'],
                    scatto_fotogramma=(pj['frame'] + i0 + 1) if pj['frame'] is not None else None,
                    accelerazione_radice_max=round(rj['max_acc'], 1),
                    compenetrazioni_cm={k: round(v['depth_cm'], 1) for k, v in col.items() if v['depth_cm'] > 0.2})
    for (num, label, key, a, b) in seg:
        i0, i1 = frames_of(a, b, n)
        d = block(i0, i1); d.update(numero=num, nome=label, chiave=key, inizio_s=round(a, 2), fine_s=round(b, 2))
        rep['segmenti'].append(d)
    for prev, c in zip(ch.tl.clips, ch.tl.clips[1:]):
        i0, i1 = frames_of(c.start - 0.15, c.start + c.blend + 0.15, n)
        d = block(i0, i1); d.update(da=prev.name, a=c.name, inizio_s=round(c.start, 2), dissolvenza_s=round(c.blend, 2))
        rep['transizioni'].append(d)
    rep['tutto'] = block(0, n - 1)
    # deformazioni sulle mesh valutate (quello che si vede nel render)
    t0 = time.time()
    objs = [ob for ob in ch.h['meshes'].values() if ob.type == 'MESH']
    dfm = MT.deformation(sc, objs, list(range(1, n + 1, deform_step)))
    rep['deformazioni'] = {k.replace(C.NAME + '_', ''): {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                           for k, v in dfm.items()}
    rep['deformazioni_secondi'] = round(time.time() - t0, 1)
    return rep


def verdict(d, lim=C.LIMITS, pop=75.0):
    bad = []
    for s, v in d['scivolamento_piedi_cm'].items():
        if v > lim['foot_slide_cm']:
            bad.append('piede %s scivola %.2f cm' % (s, v))
    if d['suola_minima_cm'] < -lim['floor_cm']:
        bad.append('suola sotto il pavimento %.2f cm' % d['suola_minima_cm'])
    if d['scatto_max_gradi'] > pop:
        bad.append('scatto %.0f gradi/fotogramma (%s)' % (d['scatto_max_gradi'], d['scatto_osso']))
    for k, v in d['compenetrazioni_cm'].items():
        if v > lim['penetration_cm']:
            bad.append('compenetrazione %s %.1f cm' % (k, v))
    return bad


def write_report(rep):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'report.json'), 'w') as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False, default=str)
    L = ['# Scena di prova (Fase 8): misure', '',
         'Generato da `python3 cartoon_character/main.py validate`. %d fotogrammi a %d fps (%.1f s). Limiti da `config.LIMITS`: '
         'scivolamento %.1f cm, suola %.1f cm sotto il pavimento, compenetrazione %.1f cm, scatto 75 gradi per fotogramma.'
         % (rep['fotogrammi'], C.FPS, rep['durata_s'], C.LIMITS['foot_slide_cm'], C.LIMITS['floor_cm'], C.LIMITS['penetration_cm']), '',
         '| # | Segmento | Secondi | Piedi L/R (cm) | Suola min (cm) | Scatto max | Compenetrazioni (cm) | Esito |',
         '|---|---|---|---|---|---|---|---|']
    for d in rep['segmenti']:
        bad = verdict(d)
        col = ', '.join('%s %.1f' % kv for kv in d['compenetrazioni_cm'].items()) or '-'
        L.append('| %s | %s | %.2f-%.2f | %.2f / %.2f | %.2f | %.1f (%s) | %s | %s |' % (
            d['numero'], d['nome'], d['inizio_s'], d['fine_s'], d['scivolamento_piedi_cm']['L'], d['scivolamento_piedi_cm']['R'],
            d['suola_minima_cm'], d['scatto_max_gradi'], d['scatto_osso'], col, 'OK' if not bad else '; '.join(bad)))
    L += ['', '## Transizioni tra le clip', '', 'Finestra: da 0,15 s prima a 0,15 s dopo la dissolvenza.', '',
          '| Da > a | Inizio (s) | Dissolvenza (s) | Piedi L/R (cm) | Scatto max | Accel. radice (m/s2) | Esito |', '|---|---|---|---|---|---|---|']
    for d in rep['transizioni']:
        bad = verdict(d)
        L.append('| %s > %s | %.2f | %.2f | %.2f / %.2f | %.1f (%s) | %.1f | %s |' % (
            d['da'], d['a'], d['inizio_s'], d['dissolvenza_s'], d['scivolamento_piedi_cm']['L'], d['scivolamento_piedi_cm']['R'],
            d['scatto_max_gradi'], d['scatto_osso'], d['accelerazione_radice_max'], 'OK' if not bad else '; '.join(bad)))
    L += ['', '## Deformazioni (mesh valutate, un fotogramma ogni %d)' % rep.get('deform_step', 2), '',
          'Allungamento e compressione = rapporto massimo e minimo tra un lato della mesh e lo stesso lato a riposo; '
          'volume = rapporto con il volume a riposo (solo mesh chiuse).', '',
          '| Parte | Allungamento max | Compressione min | Percentile 99 | Volume min-max | Fotogramma peggiore | Esito |',
          '|---|---|---|---|---|---|---|']
    for k in BODY:
        v = rep['deformazioni'].get(k)
        if not v:
            continue
        bad = []
        if v['stretch'] > C.LIMITS['stretch']:
            bad.append('allungamento oltre %.1f' % C.LIMITS['stretch'])
        if v['compress'] < C.LIMITS['compress']:
            bad.append('piega: lati schiacciati al %d%%' % round(v['compress'] * 100))
        L.append('| %s | %.2f | %.2f | %.2f | %.2f-%.2f | %s | %s |' % (k, v['stretch'], v['compress'], v['p99'], v['vol_min'], v['vol_max'],
                                                                v.get('frame_compress', v['frame']), 'OK' if not bad else '; '.join(bad)))
    with open(os.path.join(OUT, 'REPORT.md'), 'w') as fh:
        fh.write('\n'.join(L) + '\n')
    return os.path.join(OUT, 'REPORT.md')


# ---------------------------------------------------------------- video
def encode_with_labels(folder, path, seg, n, height):
    lab_dir = os.path.join(OUT, 'labels'); os.makedirs(lab_dir, exist_ok=True)
    filters = []
    shown = [s for s in seg if s[0] != '7'] + [s for s in seg if s[0] == '7']
    for i, (num, label, key, a, b) in enumerate(shown):
        p = os.path.join(lab_dir, '%02d.txt' % i)
        with open(p, 'w') as fh:
            fh.write(('%s  %s' % (num, label)) if num != '-' else label)
        second = num == '7'                            # la transizione si sovrappone a camminata e corsa: seconda riga, piu' piccola
        y = 'h*0.045' if not second else 'h*0.045+%d' % int(height * 0.062)
        size = max(12, int(height * (0.027 if second else 0.032)))
        filters.append("drawtext=fontfile=%s:textfile=%s:fontsize=%d:fontcolor=white:box=1:boxcolor=black@0.55:"
                       "boxborderw=10:x=(w-tw)/2:y=%s:enable='between(t,%.3f,%.3f)'" % (FONT, p, size, y, a, b))
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(C.FPS), '-start_number', '1', '-i', os.path.join(folder, 'f%04d.png'),
           '-frames:v', str(n), '-vf', ','.join(filters), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'veryfast', path]
    subprocess.run(cmd, check=True)
    return path


def main(args):
    o = parse(args)
    t0 = time.time()
    sc, ch, seg, out = setup_scene(o)
    n = len(out)
    print('scena pronta: %d fotogrammi (%.1f s) in %.1f s' % (n, (n - 1) / C.FPS, time.time() - t0))
    rp = os.path.join(OUT, 'report.json')
    if not os.path.exists(rp) or not o['render']:
        rep = measure(sc, ch, seg, out, o['deform_step'])
        rep['deform_step'] = o['deform_step']
        print('rapporto:', write_report(rep))
        for d in rep['segmenti']:
            print(' ', d['numero'], d['nome'], 'OK' if not verdict(d) else verdict(d))
    if not o['render']:
        return 0
    tag = '%dx%d' % o['res']
    folder = os.path.join(OUT, 'frames_' + tag)
    os.makedirs(folder, exist_ok=True)
    todo = [f for f in range(1, n + 1) if not (os.path.exists(os.path.join(folder, 'f%04d.png' % f))
                                                and os.path.getsize(os.path.join(folder, 'f%04d.png' % f)) > 0)]
    t1 = time.time(); done = 0
    for f in todo:
        if time.time() - t1 > o['budget']:
            break
        sc.frame_set(f)
        sc.render.filepath = os.path.join(folder, 'f%04d.png' % f)
        bpy.ops.render.render(write_still=True)
        done += 1
    left = len(todo) - done
    per = (time.time() - t1) / max(1, done)
    print('resi %d fotogrammi (%.1f s ciascuno), ne mancano %d (circa %.0f min)' % (done, per, left, left * per / 60))
    if left == 0:
        path = encode_with_labels(folder, os.path.join(OUT, 'validate_%s.mp4' % tag), seg, n, o['res'][1])
        print('video:', path)
    sys.stdout.flush()
    return 0
