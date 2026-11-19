"""Misure per la validazione: scivolamento dei piedi, pavimento, scatti, collisioni tra parti del corpo, deformazioni.

Le misure sui giunti usano la cinematica in Python (identica a Blender, verificato in test_rig); le deformazioni usano
le mesh valutate da Blender (depsgraph), quindi misurano quello che si vede davvero nel render.
"""
import math
import numpy as np
from mathutils import Vector, Matrix

from .. import config as C
from ..animation.blending import root_matrix


def world_mats(sk, fr):
    # l'armatura sta nell'origine: lo spazio dell'armatura (radice compresa) e' gia' quello del mondo
    return sk.fk(fr['pose'])


def foot_points(ctx, W, side):
    Mf = W['foot.' + side]
    Rinv = ctx.foot_rest[side].inverted()
    return Mf @ (Rinv @ ctx.heel_off), Mf @ (Rinv @ ctx.ball_off), Mf.translation.copy()


def foot_slide(ctx, out):
    """per ogni lato: scivolamento massimo (cm) dentro gli intervalli di appoggio dichiarati dalle clip."""
    sk = ctx.sk
    res = {}
    W = [world_mats(sk, fr) for fr in out]
    for side in 'LR':
        worst = 0.0; frames = 0; intervals = 0
        f = 0
        n = len(out)
        while f < n:
            if not out[f]['contacts'].get(side):
                f += 1; continue
            g = f
            while g + 1 < n and out[g + 1]['contacts'].get(side):
                g += 1
            if g > f:
                intervals += 1
                # scivolamento vero: il punto a terra (tallone, pianta o entrambi) non deve muoversi tra un fotogramma e l'altro
                tot = 0.0
                prev = None
                for k in range(f, g + 1):
                    heel, ball, ank = foot_points(ctx, W[k], side)
                    cur = dict(heel=heel, ball=ball)
                    if prev is not None:
                        step = 0.0
                        for key in ('heel', 'ball'):
                            if cur[key].z < 0.006 and prev[key].z < 0.006:      # quel punto tocca terra in entrambi
                                dv = cur[key] - prev[key]; dv.z = 0.0
                                step = max(step, dv.length)
                        tot += step
                    prev = cur
                    frames += 1
                worst = max(worst, tot)
            f = g + 1
        res[side] = dict(max_cm=worst * 100, contact_frames=frames, intervals=intervals)
    return res


def floor_penetration(ctx, out):
    sk = ctx.sk
    low = 1e9; at = None
    for i, fr in enumerate(out):
        W = world_mats(sk, fr)
        for side in 'LR':
            heel, ball, ank = foot_points(ctx, W, side)
            z = min(heel.z, ball.z)
            if z < low:
                low = z; at = i
    return dict(min_cm=low * 100, frame=at)


def pose_jumps(out, skip=('root',)):
    """massima rotazione di un osso tra due fotogrammi consecutivi (gradi) e dove succede."""
    worst = (0.0, None, None)
    for i in range(1, len(out)):
        a = out[i - 1]['pose']; b = out[i]['pose']
        for n in set(a) | set(b):
            if n in skip or n.startswith(('curl', 'lid_', 'eye', 'brow')):      # il battito delle palpebre e' veloce per natura
                continue
            qa = a[n].rot if n in a else None
            qb = b[n].rot if n in b else None
            if qa is None or qb is None:
                continue
            ang = math.degrees(qa.rotation_difference(qb).angle)
            ang = min(ang, 360 - ang)
            if ang > worst[0]:
                worst = (ang, i, n)
    return dict(max_deg=worst[0], frame=worst[1], bone=worst[2])


def root_jumps(out, fps=C.FPS):
    worst = 0.0; at = None
    for i in range(2, len(out)):
        p0 = out[i - 2]['pose']['root'].loc; p1 = out[i - 1]['pose']['root'].loc; p2 = out[i]['pose']['root'].loc
        acc = (p2 - 2 * p1 + p0).length * fps * fps
        if acc > worst:
            worst = acc; at = i
    return dict(max_acc=worst, frame=at)


# ------------------------------------------------------------------ collisioni con volumi semplici legati alle ossa
# (definiti in animation/collide.py: gli stessi volumi servono anche a correggere le braccia nel retargeting)
from ..animation.collide import proxies, PAIRS  # noqa: E402


def collisions(ctx, out, pairs=PAIRS):
    sk = ctx.sk
    hc = Vector(C.HEAD_C); hr = Vector(C.HEAD_R)
    head_rest = sk.rest['head']
    P = proxies(ctx)
    worst = {}
    for i, fr in enumerate(out):
        W = world_mats(sk, fr)
        pts = {}
        for (b, t, r, g) in P:
            if b == 'head':
                continue
            p = W[b] @ Vector((0, sk.length[b] * t, 0))
            pts.setdefault(g, []).append((p, r))
        Hm = W['head'] @ head_rest.inverted()                 # testa a riposo -> testa in posa
        Hinv = Hm.inverted()
        for (ga, gb) in pairs:
            A = pts.get(ga, []); B = pts.get(gb, [])
            depth = 0.0
            if gb == 'head':
                for (p, r) in A:
                    q = Hinv @ p - hc                          # spazio della testa a riposo
                    d = Vector((q.x / hr.x, q.y / hr.y, q.z / hr.z)).length
                    sd = (d - 1.0) * min(hr) - r               # distanza approssimata (negativa = dentro)
                    depth = max(depth, -sd)
            else:
                for (p, r) in A:
                    for (q, s) in B:
                        depth = max(depth, r + s - (p - q).length)
            key = ga + '-' + gb
            if depth > worst.get(key, (0.0, None))[0]:
                worst[key] = (depth, i)
    return {k: dict(depth_cm=v[0] * 100, frame=v[1]) for k, v in worst.items()}


# ------------------------------------------------------------------ deformazioni sulle mesh valutate
def mesh_arrays(ob, dg):
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64); me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    oe.to_mesh_clear()
    return co


def mesh_topology(ob):
    me = ob.data
    e = np.empty(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get('vertices', e)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64); me.loop_triangles.foreach_get('vertices', tri)
    return e.reshape(-1, 2), tri.reshape(-1, 3)


def signed_volume(co, tri):
    a = co[tri[:, 0]]; b = co[tri[:, 1]]; c = co[tri[:, 2]]
    return float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)


def deformation(scene, objects, frames):
    """per ogni oggetto: rapporto massimo e minimo tra lunghezza dei lati e riposo, percentile 99, rapporto di volume (mesh chiuse)."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    scene.frame_set(frames[0])
    info = {}
    for ob in objects:
        e, tri = mesh_topology(ob)
        rest = np.array([v.co for v in ob.data.vertices])
        L0 = np.linalg.norm(rest[e[:, 0]] - rest[e[:, 1]], axis=1)
        ok = L0 > 0.0015              # i lati minuscoli dei poli (ventagli dei cappucci) darebbero rapporti senza senso
        v0 = abs(signed_volume(rest, tri))
        info[ob.name] = dict(e=e[ok], L0=L0[ok], tri=tri, v0=v0, stretch=1.0, compress=1.0, p99=1.0, vol_min=1.0, vol_max=1.0, frame=None,
                             frame_compress=None)
    for f in frames:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in objects:
            d = info[ob.name]
            if len(d['e']) == 0:                  # mesh fatta solo di lati minuscoli (riflessi negli occhi): niente da misurare
                continue
            co = mesh_arrays(ob, dg)
            L = np.linalg.norm(co[d['e'][:, 0]] - co[d['e'][:, 1]], axis=1)
            r = L / d['L0']
            mx = float(r.max()); mn = float(r.min())
            if mx > d['stretch']:
                d['stretch'] = mx; d['frame'] = f
            if mn < d['compress']:
                d['compress'] = mn; d['frame_compress'] = f
            d['p99'] = max(d['p99'], float(np.percentile(r, 99)))
            if d['v0'] > 1e-7:
                r = abs(signed_volume(co, d['tri'])) / d['v0']
                d['vol_min'] = min(d['vol_min'], r); d['vol_max'] = max(d['vol_max'], r)
    return {k: {kk: vv for kk, vv in v.items() if kk not in ('e', 'L0', 'tri')} for k, v in info.items()}
