"""Corpo del personaggio: testa, naso, ciuffo, busto, braccia, mani, gambe, scarpe.

Ogni pezzo e' una mesh procedurale con i pesi delle ossa calcolati in modo analitico (niente pittura a mano, niente
«bone heat» che puo' fallire senza interfaccia). Le giunture sono nascoste dentro le parti vicine (spalla nel busto,
anca nei pantaloncini, polso nel palmo, caviglia nella scarpa): cosi' i movimenti estremi non aprono buchi.
"""
import math
from mathutils import Vector, Matrix, Quaternion

from .. import config as C
from . import geometry as G
from .geometry import smoothstep


def V(t):
    return Vector(t)


def mirror_x(p):
    return Vector((-p[0], p[1], p[2]))


def side_point(p, side):
    p = V(p)
    return p if side == 'L' else mirror_x(p)


# ------------------------------------------------------------------ assi della mano (servono anche al rig)
def hand_frame(side='L'):
    """origine (polso), d (lungo la mano), n (normale del palmo, verso il corpo), f (lato del pollice, avanti)."""
    W = V(C.J['wrist']); E = V(C.J['elbow'])
    d = (W - E).normalized()
    f0 = Vector((0, -1, 0))
    n = d.cross(f0).normalized()             # per il sinistro: punta in giu' e verso il corpo
    if n.x > 0:
        n = -n
    f = n.cross(d).normalized()
    if f.y > 0:
        f = -f
    if side == 'R':
        W, d, n, f = mirror_x(W), mirror_x(d), mirror_x(n), mirror_x(f)
    return W, d, n, f


def finger_chains(side='L'):
    """per ogni dito: lista di punti (radice dentro il palmo, articolazioni, punta) e raggio."""
    W, d, n, f = hand_frame('L')
    palm_c = W + d * 0.040
    out = {}
    F = C.FINGERS
    for k, name in enumerate(F['names']):
        root = palm_c + d * 0.020 + f * F['side'][k] - n * 0.002
        ax = Quaternion(n, math.radians(-F['spread'][k])) @ d     # apertura a ventaglio verso il pollice
        pts = [root]
        for L in F['seg'][k]:
            pts.append(pts[-1] + ax * L)
        out[name] = (pts, F['r'][k])
    root = palm_c + f * 0.023 - d * 0.006 + n * 0.008
    ax = (f * 0.72 + d * 0.62 + n * 0.30).normalized()
    pts = [root]
    for L in F['thumb_seg']:
        pts.append(pts[-1] + ax * L)
    out['thumb'] = (pts, F['thumb_r'])
    if side == 'R':
        out = {k: ([mirror_x(p) for p in pts], r) for k, (pts, r) in out.items()}
    return out


def curl_curve():
    return [V(p) for p in C.CURL['pts']]


# ------------------------------------------------------------------ pezzi del corpo
def part_head():
    m = G.head_mesh(72, 48)
    m['weights'] = [{'head': 1.0} for _ in m['verts']]
    m['mat'] = ['skin'] * len(m['faces'])
    return m


def part_nose():
    p, n = G.head_surface_front(0.0, C.NOSE['z'])
    c = p + n * 0.004
    rot = Vector((0, -1, 0)).rotation_difference(-n)
    m = G.ellipsoid(c, C.NOSE['r'], rot, 20, 14)
    m['weights'] = [{'head': 1.0} for _ in m['verts']]
    m['mat'] = ['nose'] * len(m['faces'])
    return m


def curl_straight():
    """il ciuffo a riposo e' un tubo dritto lungo quanto la curva del «?» (la forma a «?» e' una posa)."""
    _, L = G.polyline_sample(C.CURL['pts'], 0.001)
    base = V(C.CURL['pts'][0])
    return base, L


def part_curl():
    base, Lc = curl_straight()
    r0, r1 = C.CURL['r0'], C.CURL['r1']
    pts = [base, base + Vector((0.0, 0.0, Lc))]
    m = G.tube(pts, lambda s, L: r0 + (r1 - r0) * (s / L) ** 0.8, n=16, step=0.004, cap0=True, cap1=True, up=(0, -1, 0))
    nb = C.CURL['bones']
    L = m['L']
    W = []
    for s in m['s']:
        x = min(nb - 1e-6, max(0.0, s / L * nb))
        k = int(x); f = x - k
        w = {}
        # pesi larghi e morbidi tra un segmento e il successivo: la curva resta liscia
        if f > 0.5 and k < nb - 1:
            b = (f - 0.5)                                     # 0 -> 0.5 lineare verso l'osso successivo
            w['curl.%02d' % (k + 1)] = 1 - b; w['curl.%02d' % (k + 2)] = b
        elif f < 0.5 and k > 0:
            b = 0.5 - f
            w['curl.%02d' % (k + 1)] = 1 - b; w['curl.%02d' % k] = b
        else:
            w['curl.%02d' % (k + 1)] = 1.0
        W.append({kk: vv for kk, vv in w.items() if vv > 1e-4})
    m['weights'] = W
    m['mat'] = ['curl'] * len(m['faces'])
    return m


def part_torso():
    m = G.torso_mesh(48)
    W = []
    # pesi a «cappello» lineari lungo l'altezza (partizione dell'unita'): curve lunghe e morbide quando il busto si piega
    ctrl = ((0.430, 'hips'), (0.510, 'spine'), (0.590, 'chest'), (0.654, 'neck'))
    for z in m['z']:
        w = {}
        if z <= ctrl[0][0]:
            w[ctrl[0][1]] = 1.0
        elif z >= ctrl[-1][0]:
            w[ctrl[-1][1]] = 1.0
        else:
            for (z0, b0), (z1, b1) in zip(ctrl[:-1], ctrl[1:]):
                if z0 <= z <= z1:
                    f = (z - z0) / (z1 - z0)
                    w[b0] = 1 - f; w[b1] = f
                    break
        W.append({k: v for k, v in w.items() if v > 1e-4})
    m['weights'] = W
    mats = []
    for f in m['faces']:
        zc = sum(m['verts'][i][2] for i in f) / len(f)
        mats.append('shorts' if zc < C.TORSO['shorts_top'] else 'shirt')
    m['mat'] = mats
    return m


def part_arm(side):
    S = V(C.J['shoulder']); E = V(C.J['elbow']); Wr = V(C.J['wrist'])
    inner = V((0.064, 0.006, 0.606))
    d = (Wr - E).normalized()
    pts = [inner, S, E, Wr + d * 0.010]
    s_sh = (S - inner).length
    s_el = s_sh + (E - S).length
    sl = s_sh + C.ARM['sleeve_len']
    A = C.ARM

    def rad(s, L):
        if s < sl:
            return A['sleeve_r'] * (1.0 - 0.10 * smoothstep(s_sh, sl, s))
        t = (s - s_sh) / max(1e-6, (L - s_sh))
        return A['r_up'] + (A['r_low'] - A['r_up']) * t

    m = G.tube(pts, rad, n=22, step=0.006, cap0=True, cap1=True, breaks=(sl - 0.0004, sl + 0.0004), up=(0, -1, 0))
    W = []
    for s in m['s']:
        b = min(1.0, max(0.0, (s - (s_el - 0.046)) / 0.092))     # fusione lineare lunga: curva costante (gomito «a tubo»)
        W.append({k: v for k, v in (('upper_arm.L', 1 - b), ('forearm.L', b)) if v > 1e-4})
    mats = []
    for f in m['faces']:
        sc = sum(m['s'][i] for i in f) / len(f)
        mats.append('shirt' if sc <= sl + 1e-4 else 'skin')
    m['weights'] = W; m['mat'] = mats
    return _side(m, side)


def part_hand(side):
    W, d, n, f = hand_frame('L')
    c = W + d * 0.040
    R = Matrix((f, d, n)).transposed()          # colonne: x = f, y = d, z = n
    pr = C.HAND['palm']
    palm = G.ellipsoid(c, (pr[0], pr[2] * 0.95, pr[1]), R, 24, 16)
    palm['weights'] = [{'hand.L': 1.0} for _ in palm['verts']]
    palm['mat'] = ['skin'] * len(palm['faces'])
    parts = [palm]
    for name, (pts, r) in finger_chains('L').items():
        seglen = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
        joints = [sum(seglen[:i + 1]) for i in range(len(seglen) - 1)]
        fm = G.tube(pts, (lambda rr: (lambda s, L: rr * (1.0 - 0.10 * s / L)))(r), n=12, step=0.003, cap0=True, cap1=True,
                    up=tuple(n), flat=0.92)
        nb = len(pts) - 1
        Wt = []
        for s in fm['s']:
            k = sum(1 for j in joints if s > j)
            w = {}
            done = False
            for ji, j in enumerate(joints):
                if abs(s - j) < 0.006:
                    b = (s - (j - 0.006)) / 0.012
                    w['%s.%02d.L' % (name, ji + 1)] = 1 - b; w['%s.%02d.L' % (name, ji + 2)] = b
                    done = True
                    break
            if not done:
                w['%s.%02d.L' % (name, min(nb, k + 1))] = 1.0
            Wt.append({kk: vv for kk, vv in w.items() if vv > 1e-4})
        fm['weights'] = Wt
        fm['mat'] = ['skin'] * len(fm['faces'])
        parts.append(fm)
    m = _merge(parts)
    return _side(m, side)


def part_leg(side):
    Hj = V(C.J['hip']); K = V(C.J['knee']); A = V(C.J['ankle'])
    top = Hj + Vector((-0.006, 0.0, 0.030))
    pts = [top, Hj, K, A + Vector((0, 0, -0.012))]
    s_h = (Hj - top).length
    s_k = s_h + (K - Hj).length
    sl = s_h + C.LEG['shorts_len']
    Lg = C.LEG

    def rad(s, L):
        if s < sl:
            return Lg['shorts_r'] * (1.0 - 0.06 * smoothstep(s_h, sl, s))
        t = (s - s_h) / max(1e-6, (L - s_h))
        return Lg['r_up'] + (Lg['r_low'] - Lg['r_up']) * t

    m = G.tube(pts, rad, n=24, step=0.006, cap0=True, cap1=True, breaks=(sl - 0.0004, sl + 0.0004), up=(0, -1, 0))
    W = []
    for s in m['s']:
        b = min(1.0, max(0.0, (s - (s_k - 0.060)) / 0.120))      # ginocchio: fusione lineare lunga
        W.append({k: v for k, v in (('thigh.L', 1 - b), ('shin.L', b)) if v > 1e-4})
    mats = []
    for f in m['faces']:
        sc = sum(m['s'][i] for i in f) / len(f)
        mats.append('shorts' if sc <= sl + 1e-4 else 'skin')
    m['weights'] = W; m['mat'] = mats
    return _side(m, side)


def part_shoe(side):
    A = V(C.J['ankle']); B = V(C.J['ball'])
    F = C.FOOT
    y_heel = A.y + F['heel'][1]
    y_toe = y_heel - F['len']
    yc = (y_heel + y_toe) / 2
    xc = A.x + 0.004
    H = F['height']; zc = H * 0.42
    dirs, faces = G.uv_sphere(40, 28)
    verts = []
    for (dx, dy, dz) in dirs:
        # dy < 0 = verso la punta
        toe = smoothstep(0.2, -0.9, dy)                # 0 al tallone, 1 alla punta
        wprof = 0.86 + 0.22 * toe
        hprof = 1.0 - 0.30 * toe
        x = xc + dx * (F['width'] / 2) * wprof + 0.006 * toe
        y = yc + dy * (F['len'] / 2)
        if dz >= 0:
            z = zc + dz * (H - zc) * hprof
        else:
            z = zc * (1.0 - min(1.0, (-dz) / 0.55) ** 1.6)
        verts.append((x, y, z))
    m = dict(verts=verts, faces=faces)
    W = []
    for (x, y, z) in verts:
        b = smoothstep(B.y + 0.014, B.y - 0.014, y)
        W.append({k: v for k, v in (('foot.L', 1 - b), ('toe.L', b)) if v > 1e-4})
    mats = []
    for f in faces:
        zc_ = sum(verts[i][2] for i in f) / len(f)
        mats.append('sole' if zc_ < 0.013 else 'shoe')
    m['weights'] = W; m['mat'] = mats
    return _side(m, side)


# ------------------------------------------------------------------ utilita'
def _merge(parts):
    verts, faces, W, mats = [], [], [], []
    for p in parts:
        o = len(verts)
        verts += p['verts']; W += p['weights']; mats += p['mat']
        faces += [tuple(i + o for i in f) for f in p['faces']]
    return dict(verts=verts, faces=faces, weights=W, mat=mats)


def _side(m, side):
    if side == 'L':
        return m
    verts = [(-x, y, z) for (x, y, z) in m['verts']]
    faces = [tuple(reversed(f)) for f in m['faces']]          # lo specchio inverte il verso delle facce
    W = [{k.replace('.L', '.R'): v for k, v in w.items()} for w in m['weights']]
    return dict(m, verts=verts, faces=faces, weights=W)


def body_parts():
    """tutti i pezzi del corpo: nome -> mesh con pesi e materiali per faccia."""
    P = dict(head=part_head(), nose=part_nose(), curl=part_curl(), torso=part_torso())
    for s in ('L', 'R'):
        P['arm.' + s] = part_arm(s)
        P['hand.' + s] = part_hand(s)
        P['leg.' + s] = part_leg(s)
        P['shoe.' + s] = part_shoe(s)
    return P
