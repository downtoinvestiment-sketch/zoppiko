"""Viso: occhi (bulbo, iride, pupilla con dilatazione, riflessi fissi sulla testa), palpebre a guscio, sopracciglia,
bocca «disegnata» sulla superficie della testa con lingua e denti, rossore sulle guance.

La bocca e' una griglia proiettata sulla testa. Ogni forma (sorriso, «O», urlo...) e' una shape key calcolata dallo stesso
contorno parametrico; lingua e denti sono fasce della stessa griglia, quindi non escono mai dal contorno della bocca,
nemmeno quando le forme si mescolano (combinazioni convesse).
"""
import math
from mathutils import Vector, Matrix, Quaternion

from .. import config as C
from . import geometry as G
from .geometry import smoothstep

UP = Vector((0, 0, 1))
FWD = Vector((0, -1, 0))

LID_UP_REST = 52.0       # gradi: a riposo il bordo della palpebra superiore sta 52 gradi sopra lo sguardo
LID_LOW_REST = -50.0


def eye_center(side):
    e = Vector(C.EYE_C)
    return e if side == 'L' else Vector((-e.x, e.y, e.z))


def _rot_about(axis, deg):
    return Quaternion(Vector(axis).normalized(), math.radians(deg))


# ------------------------------------------------------------------ occhi
def part_eye(side):
    E = eye_center(side); r = C.EYE_R
    ball = G.ellipsoid(E, (r, r, r), None, 32, 22)
    ball['weights'] = [{'eye.' + side: 1.0} for _ in ball['verts']]
    ball['mat'] = ['sclera'] * len(ball['faces'])
    iris = G.sphere_cap(E, r * 1.0018, FWD, C.IRIS_DEG, nr=10, na=40)
    iris['weights'] = [{'eye.' + side: 1.0} for _ in iris['verts']]
    iris['mat'] = ['iris'] * len(iris['faces'])
    p0 = G.sphere_cap(E, r * 1.0036, FWD, C.PUPIL_DEG[0], nr=6, na=40)
    p1 = G.sphere_cap(E, r * 1.0036, FWD, C.PUPIL_DEG[1], nr=6, na=40)
    p0['weights'] = [{'eye.' + side: 1.0} for _ in p0['verts']]
    p0['mat'] = ['pupil'] * len(p0['faces'])
    p0['keys'] = {'pupil': p1['verts']}
    # riflessi: fissi rispetto alla testa (non girano con l'occhio), verso la luce principale (in alto, alla destra di chi guarda)
    shines = []
    for (dx, dz, rad, k) in ((0.38, 0.40, 0.0105, 1.0), (-0.20, -0.22, 0.0048, 1.0)):
        d = Vector((dx, -1.0, dz)).normalized()
        c = E + d * (r * 1.0062)
        rot = Vector((0, 0, 1)).rotation_difference(d)
        sh = G.ellipsoid(c, (rad, rad * 0.92, 0.0009), rot, 14, 8)
        sh['weights'] = [{'head': 1.0} for _ in sh['verts']]
        sh['mat'] = ['shine'] * len(sh['faces'])
        shines.append(sh)
    iris['ref'] = E; p0['ref'] = E
    return dict(ball=ball, iris=iris, pupil=p0, shine=_merge(shines))


def part_lids(side):
    E = eye_center(side); r = C.EYE_R
    # asse X locale dell'osso dell'occhio = -X del mondo (osso verso -Y, Z in su): rotazione positiva = bordo in su
    ax = Vector((-1, 0, 0))
    up_up = _rot_about(ax, LID_UP_REST) @ UP
    up_lo = _rot_about(ax, LID_LOW_REST) @ (-UP)
    ru, rl = r * 1.075, r * 1.058
    upper = G.hemi_shell(E, ru, up_up, nu=44, nv=14, extra_deg=3.0)
    upper['weights'] = [{'lid_up.' + side: 1.0} for _ in upper['verts']]
    upper['mat'] = ['lid'] * len(upper['faces'])
    a = math.radians(3.0)
    rim = G.torus_ring(E - up_up * (ru * math.sin(a)), up_up, ru * math.cos(a) + 0.0003, 0.0023, nu=56, nv=8)
    rim['weights'] = [{'lid_up.' + side: 1.0} for _ in rim['verts']]
    rim['mat'] = ['lash'] * len(rim['faces'])
    lower = G.hemi_shell(E, rl, up_lo, nu=44, nv=12, extra_deg=3.0)
    lower['weights'] = [{'lid_low.' + side: 1.0} for _ in lower['verts']]
    lower['mat'] = ['lid'] * len(lower['faces'])
    up_m = _merge([upper, rim]); up_m['ref'] = E; lower['ref'] = E
    return dict(upper=up_m, lower=lower)


# ------------------------------------------------------------------ sopracciglia
def brow_points(side, n=9):
    B = C.BROW
    pts = []
    for i in range(n):
        u = -1 + 2 * i / (n - 1)                     # -1 = interno, +1 = esterno
        x = B['x'] + u * B['len'] / 2
        z = B['z'] + 0.006 * (1 - u * u) - math.radians(B['tilt']) * (u * B['len'] / 2)
        p = G.on_face(x, z, 0.0105)
        pts.append(p if side == 'L' else Vector((-p.x, p.y, p.z)))
    return pts


def brow_center(side):
    pts = brow_points(side)
    return pts[len(pts) // 2]


def part_brow(side):
    pts = brow_points(side)
    th = C.BROW['thick']
    m = G.tube(pts, lambda s, L: th / 2 * (0.62 + 0.38 * math.sin(math.pi * min(1.0, s / L * 0.9 + 0.05))), n=14,
               step=0.003, cap0=True, cap1=True, up=(0, -1, 0), flat=0.70)
    m['weights'] = [{'brow.' + side: 1.0} for _ in m['verts']]
    m['mat'] = ['brow'] * len(m['faces'])
    return m


# ------------------------------------------------------------------ bocca
def mouth_curves(p, nu):
    """contorno: per ogni colonna u in [-1, 1] restituisce (s, t_su, t_giu) in metri sul piano della faccia."""
    sw, sh = C.MOUTH.get('scale', (1.0, 1.0))
    w = p['w'] * sw; k = p.get('k', 0.0) * sh; kl = p.get('kl', p.get('k', 0.0)) * sh; kr = p.get('kr', p.get('k', 0.0)) * sh
    up, lo = p['up'] * sh, p['lo'] * sh; eu, el = p.get('eu', 1.0), p.get('el', 1.0); wave = p.get('wave', 0.0) * sh
    out = []
    for i in range(nu):
        x = -math.cos(math.pi * i / (nu - 1))       # piu' fitto agli angoli
        kk = kl if x > 0 else kr                    # x > 0 = lato sinistro del personaggio
        b = kk * x * x + wave * math.sin(3.2 * math.pi * x) * (1 - x * x)
        q = max(0.0, 1 - x * x)
        tu = b + up * q ** eu + 0.0004 * q ** 0.5
        tl = b - lo * q ** el - 0.0004 * q ** 0.5
        out.append((x * w, tu, tl))
    return out


NU, NV = 33, 8


def _mouth_grid(params):
    """griglie (in 2D) di bocca, lingua, denti per una forma."""
    cols = mouth_curves(params, NU)
    mouth, tongue, teeth = [], [], []
    tf = params.get('tongue', 0.0); te = params.get('teeth', 0.0); tlo = params.get('teeth_lo', 0.0)
    for i, (s, tu, tl) in enumerate(cols):
        x = -math.cos(math.pi * i / (NU - 1))
        h = tu - tl
        for j in range(NV):
            mouth.append((s, tl + h * j / (NV - 1)))
        # lingua: fascia bassa con la cima tonda, larga il 76% della bocca
        g = max(0.0, 1 - (x / 0.76) ** 2) ** 0.5 if abs(x) < 0.76 else 0.0
        top = tl + h * tf * g
        for j in range(4):
            tongue.append((s * 0.98, min(tu, tl + (top - tl) * j / 3 + 0.0002)))
        # denti sopra (e sotto se teeth_lo): fasce vicino al labbro
        g2 = max(0.0, 1 - (x / 0.80) ** 2) ** 0.5 if abs(x) < 0.80 else 0.0
        bt = tu - min(0.017, h * te) * g2
        for j in range(3):
            teeth.append((s * 0.97, max(tl, tu - (tu - bt) * j / 2 - 0.0002)))
        bl = tl + min(0.015, h * tlo) * g2
        for j in range(3):
            teeth.append((s * 0.97, min(tu, tl + (bl - tl) * j / 2 + 0.0002)))
    return mouth, tongue, teeth


def _grid_faces(ncols, nrows, off=0, stride=None):
    stride = stride or nrows
    faces = []
    for i in range(ncols - 1):
        for j in range(nrows - 1):
            a = off + i * stride + j; b = off + (i + 1) * stride + j
            faces.append((a, b, b + 1, a + 1))
    return faces


def _project(pts2d, offset):
    z0 = C.MOUTH['z']
    out = []
    for (s, t) in pts2d:
        out.append(tuple(G.on_mouth(s, t, offset, z0)))
    return out


def part_mouth():
    base = C.MOUTH_PARAMS['base']
    m2, t2, d2 = _mouth_grid(base)
    keys_m, keys_t, keys_d = {}, {}, {}
    for name in C.MOUTH_SHAPES:
        mm, tt, dd = _mouth_grid(C.MOUTH_PARAMS[name])
        keys_m[name] = _project(mm, 0.0020); keys_t[name] = _project(tt, 0.0026); keys_d[name] = _project(dd, 0.0030)
    mouth = dict(verts=_project(m2, 0.0020), faces=_grid_faces(NU, NV), keys=keys_m)
    tongue = dict(verts=_project(t2, 0.0026), faces=_grid_faces(NU, 4), keys=keys_t)
    tf = _grid_faces(NU, 3, 0, 6) + _grid_faces(NU, 3, 3, 6)
    teeth = dict(verts=_project(d2, 0.0030), faces=tf, keys=keys_d)
    for p, mat in ((mouth, 'mouth'), (tongue, 'tongue'), (teeth, 'teeth')):
        p['weights'] = [{'head': 1.0} for _ in p['verts']]
        p['mat'] = [mat] * len(p['faces'])
        p['ref'] = Vector(C.HEAD_C)
    return dict(mouth=mouth, tongue=tongue, teeth=teeth)


def part_blush():
    parts = []
    for sx in (1, -1):
        cx, cz = C.BLUSH['x'] * sx, C.BLUSH['z']
        rx, rz = C.BLUSH['r']
        nr, na = 5, 28
        flat = [(cx, cz)]
        small = [(cx, cz)]
        uv = [(0.0, 0.0)]
        for j in range(1, nr + 1):
            for i in range(na):
                a = 2 * math.pi * i / na
                f = j / nr
                flat.append((cx + rx * f * math.cos(a), cz + rz * f * math.sin(a)))
                small.append((cx + rx * f * math.cos(a) * 0.04, cz + rz * f * math.sin(a) * 0.04))
                uv.append((f, i / na))
        verts = [tuple(G.on_face(x, z, 0.0012)) for (x, z) in small]
        key = [tuple(G.on_face(x, z, 0.0012)) for (x, z) in flat]
        faces = [(0, 1 + i, 1 + (i + 1) % na) for i in range(na)]
        for j in range(nr - 1):
            r0, r1 = 1 + j * na, 1 + (j + 1) * na
            for i in range(na):
                faces.append((r0 + i, r1 + i, r1 + (i + 1) % na, r0 + (i + 1) % na))
        parts.append(dict(verts=verts, faces=faces, keys={'blush': key}, uv=uv))
    m = _merge(parts)
    m['weights'] = [{'head': 1.0} for _ in m['verts']]
    m['mat'] = ['blush'] * len(m['faces'])
    m['ref'] = Vector(C.HEAD_C)
    return m


# ------------------------------------------------------------------ utilita'
def _merge(parts):
    verts, faces, W, mats, uv = [], [], [], [], []
    keys = {}
    for p in parts:
        o = len(verts)
        verts += list(p['verts']); W += p.get('weights', [{}] * len(p['verts'])); mats += p.get('mat', [])
        faces += [tuple(i + o for i in f) for f in p['faces']]
        uv += p.get('uv', [(0.0, 0.0)] * len(p['verts']))
    names = set()
    for p in parts:
        names |= set(p.get('keys', {}).keys())
    for name in names:
        kv = []
        for p in parts:
            kv += list(p.get('keys', {}).get(name, p['verts']))
        keys[name] = kv
    out = dict(verts=verts, faces=faces, weights=W, mat=mats, uv=uv)
    if keys:
        out['keys'] = keys
    return out


def face_parts():
    P = {}
    for s in ('L', 'R'):
        e = part_eye(s)
        P['eye.' + s] = e['ball']; P['iris.' + s] = e['iris']; P['pupil.' + s] = e['pupil']; P['shine.' + s] = e['shine']
        l = part_lids(s)
        P['lid_up.' + s] = l['upper']; P['lid_low.' + s] = l['lower']
        P['brow.' + s] = part_brow(s)
    P.update(part_mouth())
    P['blush'] = part_blush()
    return P
