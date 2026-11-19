"""Geometria pura (senza bpy): forma analitica della testa, tubi lungo un percorso, gusci, calotte, ellissoidi.

Ogni funzione restituisce un dizionario: verts (lista di tuple), faces (liste di indici), e attributi per vertice
(per esempio «s» = ascissa curvilinea, usata per i pesi delle ossa e per i materiali).
"""
import math
from mathutils import Vector, Matrix, Quaternion

from .. import config as C


def smoothstep(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ testa analitica
_HC = Vector(C.HEAD_C)
_CHEEKS = [Vector(d).normalized() for d in C.CHEEK['dirs']]


def head_radius(d):
    """raggio della testa lungo la direzione unitaria d (coordinate relative al centro della testa)."""
    a, b, c = C.HEAD_R
    r = 1.0 / math.sqrt((d.x / a) ** 2 + (d.y / b) ** 2 + (d.z / c) ** 2)
    for ch in _CHEEKS:                                   # guance piene
        q = (d - ch).length_squared
        r += C.CHEEK['amp'] * math.exp(-q / (2 * C.CHEEK['sigma'] ** 2))
    if d.z < 0:                                          # sotto e' un poco piu' piatta
        r -= C.CHIN_FLAT * (d.z ** 2)
    return r


def head_sdf(p):
    """>0 fuori dalla testa, <0 dentro (distanza approssimata lungo il raggio)."""
    q = Vector(p) - _HC
    L = q.length
    if L < 1e-9:
        return -head_radius(Vector((0, 0, 1)))
    return L - head_radius(q / L)


def head_surface_front(x, z):
    """punto della superficie della testa davanti (y < 0) alle coordinate x, z del mondo, piu' la normale."""
    lo, hi = -0.45, 0.02                                  # lo e' fuori (davanti), hi e' dentro o dietro il centro
    if head_sdf((x, lo, z)) <= 0:
        raise ValueError('punto fuori dalla faccia')
    if head_sdf((x, hi, z)) > 0:                          # la retta non entra nella testa
        raise ValueError('la retta non tocca la testa (%.3f, %.3f)' % (x, z))
    for _ in range(48):
        m = (lo + hi) / 2
        if head_sdf((x, m, z)) > 0:
            lo = m
        else:
            hi = m
    p = Vector((x, (lo + hi) / 2, z))
    return p, head_normal(p)


def head_normal(p, e=1e-4):
    p = Vector(p)
    g = Vector((head_sdf(p + Vector((e, 0, 0))) - head_sdf(p - Vector((e, 0, 0))),
                head_sdf(p + Vector((0, e, 0))) - head_sdf(p - Vector((0, e, 0))),
                head_sdf(p + Vector((0, 0, e))) - head_sdf(p - Vector((0, 0, e)))))
    return g.normalized()


def ray_surface(q, d):
    """punto della superficie della testa lungo il raggio q + t d (q dentro la testa)."""
    q = Vector(q); d = Vector(d).normalized()
    lo, hi = 0.0, 0.6
    for _ in range(50):
        m = (lo + hi) / 2
        if head_sdf(q + d * m) < 0:
            lo = m
        else:
            hi = m
    p = q + d * ((lo + hi) / 2)
    return p, head_normal(p)


MOUTH_Q_DY = 0.0
def on_mouth(s, t, offset, z0, depth=0.172):
    """proiezione «a raggiera» per la bocca: da un punto dentro la testa verso (s, t) sul piano della faccia.
    Cosi' anche le bocche molto aperte si avvolgono bene sul mento invece di stirarsi."""
    q = Vector((0.0, MOUTH_Q_DY, z0 + 0.02))
    p, n = ray_surface(q, (s, -depth, t - 0.02))
    return p + n * offset


def on_face(x, z, offset):
    p, n = head_surface_front(x, z)
    return p + n * offset


# ------------------------------------------------------------------ sfera deformata (testa, ellissoidi, scarpe)
def uv_sphere(nu=48, nv=32):
    """sfera unitaria: verts come direzioni, faces a quadrilateri e triangoli ai poli."""
    verts = [(0.0, 0.0, 1.0)]
    for j in range(1, nv):
        th = math.pi * j / nv
        for i in range(nu):
            ph = 2 * math.pi * i / nu
            verts.append((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
    verts.append((0.0, 0.0, -1.0))
    faces = []
    for i in range(nu):
        faces.append((0, 1 + i, 1 + (i + 1) % nu))
    for j in range(nv - 2):
        r0, r1 = 1 + j * nu, 1 + (j + 1) * nu
        for i in range(nu):
            faces.append((r0 + i, r1 + i, r1 + (i + 1) % nu, r0 + (i + 1) % nu))
    last = len(verts) - 1
    r0 = 1 + (nv - 2) * nu
    for i in range(nu):
        faces.append((r0 + (i + 1) % nu, r0 + i, last))
    return verts, faces


def head_mesh(nu=72, nv=48):
    dirs, faces = uv_sphere(nu, nv)
    verts = []
    for d in dirs:
        d = Vector(d)
        verts.append(tuple(_HC + d * head_radius(d)))
    return dict(verts=verts, faces=faces)


def ellipsoid(center, radii, rot=None, nu=24, nv=16):
    dirs, faces = uv_sphere(nu, nv)
    R = rot.to_matrix() if isinstance(rot, Quaternion) else (rot if rot is not None else Matrix.Identity(3))
    c = Vector(center)
    verts = [tuple(c + R @ Vector((d[0] * radii[0], d[1] * radii[1], d[2] * radii[2]))) for d in dirs]
    return dict(verts=verts, faces=faces)


# ------------------------------------------------------------------ busto a tornio
def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


def resample_profile(rows, sub=4):
    out = []
    n = len(rows)
    for i in range(n - 1):
        p0 = rows[max(0, i - 1)]; p1 = rows[i]; p2 = rows[i + 1]; p3 = rows[min(n - 1, i + 2)]
        for k in range(sub):
            out.append(_catmull(p0, p1, p2, p3, k / sub))
    out.append(rows[-1])
    return out


def torso_mesh(nseg=48, power=2.3):
    """busto a pera: anelli a superellisse (un poco squadrati) interpolati con Catmull-Rom."""
    rows = resample_profile(C.TORSO['rings'], 4)
    verts, faces, zs = [], [], []
    bottom = len(verts); verts.append((0.0, rows[0][3], rows[0][0])); zs.append(rows[0][0])
    ring_idx = []
    for (z, rx, ry, oy) in rows[1:-1]:
        start = len(verts)
        for i in range(nseg):
            a = 2 * math.pi * i / nseg
            ca, sa = math.cos(a), math.sin(a)
            # superellisse: |x/rx|^p + |y/ry|^p = 1
            k = (abs(ca) ** power + abs(sa) ** power) ** (-1.0 / power)
            x, y = rx * ca * k, ry * sa * k
            if y < 0:                                    # la pancia sporge un poco davanti
                y *= 1.06
            verts.append((x, y + oy, z)); zs.append(z)
        ring_idx.append(start)
    top = len(verts); verts.append((0.0, rows[-1][3], rows[-1][0])); zs.append(rows[-1][0])
    for i in range(nseg):
        faces.append((bottom, ring_idx[0] + (i + 1) % nseg, ring_idx[0] + i))
    for r in range(len(ring_idx) - 1):
        a0, a1 = ring_idx[r], ring_idx[r + 1]
        for i in range(nseg):
            faces.append((a0 + i, a0 + (i + 1) % nseg, a1 + (i + 1) % nseg, a1 + i))
    last = ring_idx[-1]
    for i in range(nseg):
        faces.append((last + i, last + (i + 1) % nseg, top))
    return dict(verts=verts, faces=faces, z=zs)


# ------------------------------------------------------------------ tubi lungo un percorso
def polyline_sample(points, step, breaks=()):
    """ricampiona una spezzata (liscia con Catmull-Rom) con passo circa costante; restituisce punti e ascisse."""
    P = [Vector(p) for p in points]
    dense = []
    if len(P) == 2:
        for k in range(41):
            dense.append(P[0].lerp(P[1], k / 40))
    else:
        for i in range(len(P) - 1):
            p0 = P[max(0, i - 1)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(len(P) - 1, i + 2)]
            for k in range(24):
                dense.append(Vector(_catmull(p0, p1, p2, p3, k / 24)))
        dense.append(P[-1])
    s = [0.0]
    for i in range(1, len(dense)):
        s.append(s[-1] + (dense[i] - dense[i - 1]).length)
    L = s[-1]
    n = max(2, int(round(L / step)))
    targets = sorted(set([L * k / n for k in range(n + 1)] + [b for b in breaks if 0 < b < L]))
    out, j = [], 0
    for t in targets:
        while j < len(s) - 2 and s[j + 1] < t:
            j += 1
        f = 0.0 if s[j + 1] == s[j] else (t - s[j]) / (s[j + 1] - s[j])
        out.append((dense[j].lerp(dense[j + 1], f), t))
    return out, L


def tube(points, radius_fn, n=20, step=0.006, cap0=True, cap1=True, breaks=(), up=(0, 0, 1), cap_rings=6, flat=1.0):
    """tubo con cappucci tondi. radius_fn(s, L) -> raggio. flat < 1 schiaccia la sezione lungo la «normale».
    Restituisce verts, faces e per ogni vertice: s (ascissa sul percorso), frac (s/L)."""
    samples, L = polyline_sample(points, step, breaks)
    C_ = [p for p, _ in samples]; S = [t for _, t in samples]
    T = []
    for i in range(len(C_)):
        a = C_[max(0, i - 1)]; b = C_[min(len(C_) - 1, i + 1)]
        T.append((b - a).normalized())
    upv = Vector(up)
    N = []
    n0 = upv - T[0] * upv.dot(T[0])
    if n0.length < 1e-6:
        n0 = Vector((1, 0, 0)) - T[0] * T[0].x
    n0.normalize(); N.append(n0)
    for i in range(1, len(T)):                         # trasporto parallelo: niente torsioni strane
        v = T[i - 1].cross(T[i])
        if v.length < 1e-9:
            N.append(N[-1].copy())
        else:
            ang = math.asin(min(1.0, v.length))
            if T[i - 1].dot(T[i]) < 0:
                ang = math.pi - ang
            N.append((Quaternion(v.normalized(), ang) @ N[-1]).normalized())
    verts, faces, s_attr = [], [], []
    rings = []

    def ring(c, t, nn, r, sval):
        b = t.cross(nn)
        idx = len(verts)
        for k in range(n):
            a = 2 * math.pi * k / n
            off = nn * (math.cos(a) * r * flat) + b * (math.sin(a) * r)
            verts.append(tuple(c + off)); s_attr.append(sval)
        rings.append(idx)

    if cap0:
        r = radius_fn(0.0, L)
        pole = len(verts); verts.append(tuple(C_[0] - T[0] * r)); s_attr.append(0.0)
        for k in range(1, cap_rings):
            a = (math.pi / 2) * k / cap_rings
            ring(C_[0] - T[0] * r * math.cos(a), T[0], N[0], r * math.sin(a), 0.0)
        for k in range(n):
            faces.append((pole, rings[0] + (k + 1) % n, rings[0] + k))
    for i in range(len(C_)):
        ring(C_[i], T[i], N[i], radius_fn(S[i], L), S[i])
    if cap1:
        r = radius_fn(L, L)
        for k in range(1, cap_rings):
            a = (math.pi / 2) * k / cap_rings
            ring(C_[-1] + T[-1] * r * math.sin(a), T[-1], N[-1], r * math.cos(a), L)
    for q in range(len(rings) - 1):
        a0, a1 = rings[q], rings[q + 1]
        for k in range(n):
            faces.append((a0 + k, a0 + (k + 1) % n, a1 + (k + 1) % n, a1 + k))
    if cap1:
        pole = len(verts); verts.append(tuple(C_[-1] + T[-1] * radius_fn(L, L))); s_attr.append(L)
        a0 = rings[-1]
        for k in range(n):
            faces.append((a0 + k, a0 + (k + 1) % n, pole))
    return dict(verts=verts, faces=faces, s=s_attr, L=L, frac=[v / L for v in s_attr])


# ------------------------------------------------------------------ gusci e calotte sferiche (occhi e palpebre)
def sphere_cap(center, radius, axis, half_angle_deg, nr=10, na=40, uv=True):
    """calotta sferica attorno ad `axis`; uv[0] = frazione radiale (0 al centro, 1 al bordo)."""
    c = Vector(center); ax = Vector(axis).normalized()
    ref = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    e1 = ax.cross(ref).normalized(); e2 = ax.cross(e1).normalized()
    A = math.radians(half_angle_deg)
    verts = [tuple(c + ax * radius)]; uvs = [(0.0, 0.5)]
    for j in range(1, nr + 1):
        th = A * j / nr
        for i in range(na):
            ph = 2 * math.pi * i / na
            d = ax * math.cos(th) + (e1 * math.cos(ph) + e2 * math.sin(ph)) * math.sin(th)
            verts.append(tuple(c + d * radius)); uvs.append((j / nr, i / na))
    faces = [(0, 1 + i, 1 + (i + 1) % na) for i in range(na)]
    for j in range(nr - 1):
        r0, r1 = 1 + j * na, 1 + (j + 1) * na
        for i in range(na):
            faces.append((r0 + i, r1 + i, r1 + (i + 1) % na, r0 + (i + 1) % na))
    return dict(verts=verts, faces=faces, uv=uvs)


def hemi_shell(center, radius, up, nu=40, nv=12, extra_deg=0.0):
    """mezzo guscio sferico: le direzioni con componente lungo `up` >= -sin(extra). Il bordo e' un cerchio massimo."""
    c = Vector(center); u = Vector(up).normalized()
    ref = Vector((1, 0, 0)) if abs(u.x) < 0.9 else Vector((0, 1, 0))
    e1 = u.cross(ref).normalized(); e2 = u.cross(e1).normalized()
    verts = [tuple(c + u * radius)]
    top = math.radians(90 + extra_deg)
    for j in range(1, nv + 1):
        th = top * j / nv
        for i in range(nu):
            ph = 2 * math.pi * i / nu
            d = u * math.cos(th) + (e1 * math.cos(ph) + e2 * math.sin(ph)) * math.sin(th)
            verts.append(tuple(c + d * radius))
    faces = [(0, 1 + i, 1 + (i + 1) % nu) for i in range(nu)]
    for j in range(nv - 1):
        r0, r1 = 1 + j * nu, 1 + (j + 1) * nu
        for i in range(nu):
            faces.append((r0 + i, r1 + i, r1 + (i + 1) % nu, r0 + (i + 1) % nu))
    rim = list(range(1 + (nv - 1) * nu, 1 + nv * nu))
    return dict(verts=verts, faces=faces, rim=rim)


def torus_ring(center, normal, R, r, nu=48, nv=8):
    c = Vector(center); nrm = Vector(normal).normalized()
    ref = Vector((1, 0, 0)) if abs(nrm.x) < 0.9 else Vector((0, 1, 0))
    e1 = nrm.cross(ref).normalized(); e2 = nrm.cross(e1).normalized()
    verts, faces = [], []
    for i in range(nu):
        ph = 2 * math.pi * i / nu
        radial = e1 * math.cos(ph) + e2 * math.sin(ph)
        for j in range(nv):
            th = 2 * math.pi * j / nv
            verts.append(tuple(c + radial * (R + r * math.cos(th)) + nrm * (r * math.sin(th))))
    for i in range(nu):
        for j in range(nv):
            a = i * nv + j; b = ((i + 1) % nu) * nv + j; c2 = ((i + 1) % nu) * nv + (j + 1) % nv; d = i * nv + (j + 1) % nv
            faces.append((a, b, c2, d))
    return dict(verts=verts, faces=faces)


def merge(*parts):
    """unisce piu' pezzi in una sola mesh, conservando gli attributi per vertice (lista) e un indice di pezzo."""
    verts, faces, part = [], [], []
    for k, p in enumerate(parts):
        o = len(verts)
        verts += list(p['verts'])
        faces += [tuple(i + o for i in f) for f in p['faces']]
        part += [k] * len(p['verts'])
    return dict(verts=verts, faces=faces, part=part)
