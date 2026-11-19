"""Volumi semplici del corpo (sfere legate alle ossa e l'ellissoide della testa) e correzione delle braccia che entrano nel
corpo.

Servono ai test (misure delle compenetrazioni) e al retargeting: un corpo umano catturato in mocap ha testa, pancia e cosce
molto piu' piccole del nostro personaggio, quindi mani e avambracci finirebbero dentro la testa, la pancia o le gambe.
La correzione sposta il polso fuori dal volume (e il gomito, se e' l'avambraccio a entrare) e risolve il braccio con l'IK a
due ossa: la mano conserva l'orientamento nel mondo, cambia solo dove si trova.
"""
from mathutils import Vector, Matrix

from .. import config as C
from ..character.skeleton import BonePose


def proxies(ctx=None):
    """sfere (osso, punto lungo l'osso 0..1, raggio, gruppo); la testa e' un ellissoide (vedi head_push)."""
    P = [('head', None, None, 'head')]
    for t, r in ((0.2, 0.135), (0.8, 0.150)):
        P.append(('hips', t, r, 'torso'))
    for t, r in ((0.5, 0.145),):
        P.append(('spine', t, r, 'torso'))
    for t, r in ((0.3, 0.130), (0.9, 0.095)):
        P.append(('chest', t, r, 'torso'))
    for s in 'LR':
        for t in (0.3, 0.75):
            P.append(('forearm.' + s, t, 0.028, 'arm' + s))
        P.append(('hand.' + s, 0.5, 0.040, 'hand' + s))
        for t in (0.35, 0.8):
            P.append(('thigh.' + s, t, 0.046, 'leg' + s))
        for t in (0.3, 0.75):
            P.append(('shin.' + s, t, 0.038, 'leg' + s))
        P.append(('foot.' + s, 0.6, 0.050, 'foot' + s))
    return P


PAIRS = [('handL', 'head'), ('handR', 'head'), ('armL', 'head'), ('armR', 'head'), ('handL', 'torso'), ('handR', 'torso'),
         ('legL', 'legR'), ('footL', 'footR'), ('handL', 'legL'), ('handR', 'legR'), ('handL', 'handR')]


def point(sk, W, bone, t):
    return W[bone] @ Vector((0.0, sk.length[bone] * t, 0.0))


def _ray_exit(u, w):
    """t > 0 con |u + t w| = 1 (u dentro la sfera unitaria): uscita lungo la direzione w."""
    ww = w.dot(w)
    if ww < 1e-12:
        return 0.0
    uw = u.dot(w)
    disc = uw * uw - ww * (u.dot(u) - 1.0)
    return (-uw + max(0.0, disc) ** 0.5) / ww


def head_push(sk, W, p, r, margin=0.0, prev=None):
    """spostamento (mondo) che porta la sfera (p, r) fuori dall'ellissoide della testa gonfiato di r + margin.
    prev: direzione di spinta del fotogramma prima; se quella radiale di adesso e' opposta (il punto ha passato il
    centro), si continua a spingere dalla stessa parte: niente salti da un lato all'altro."""
    Hm = W['head'] @ sk.rest['head'].inverted()                 # testa a riposo -> testa in posa
    H3 = Hm.to_3x3()
    q = Hm.inverted() @ p - Vector(C.HEAD_C)
    a = Vector(C.HEAD_R) + Vector((r + margin,) * 3)
    u = Vector((q.x / a.x, q.y / a.y, q.z / a.z))
    dn = u.length
    if dn >= 1.0:
        return Vector((0.0, 0.0, 0.0))
    push = H3 @ (q / dn - q) if dn > 1e-9 else Vector((0.0, 0.0, 0.0))
    if prev is not None and (dn <= 1e-9 or push.dot(prev) < 0.0):
        wl = H3.inverted() @ prev
        w = Vector((wl.x / a.x, wl.y / a.y, wl.z / a.z))
        push = prev * _ray_exit(u, w)
    return push


def sphere_push(c, R, p, r, margin=0.0, prev=None):
    d = p - c
    need = R + r + margin
    L = d.length
    if L >= need:
        return Vector((0.0, 0.0, 0.0))
    if prev is not None and (L < 1e-9 or d.dot(prev) < 0.0):
        b = d.dot(prev)
        t = -b + max(0.0, b * b - (L * L - need * need)) ** 0.5
        return prev * t
    if L < 1e-9:
        d = Vector((0.0, -1.0, 0.0)); L = 1.0
    return d / L * (need - L)


def body_spheres(sk, W, side):
    """sfere da cui tenere lontano il braccio di un lato: busto e la gamba dello stesso lato (chiave, centro, raggio)."""
    out = []
    for k, (b, t, r, g) in enumerate(proxies()):
        if g == 'torso' or g == 'leg' + side:
            out.append(('%s%d' % (b, k), point(sk, W, b, t), r))
    return out


def push_for(sk, W, p, r, side, margin, memo=None, head_only=False):
    """spostamento totale per una sfera del braccio: testa, poi busto e gamba (due passate: uscire da un volume puo'
    far entrare in un altro). memo: direzioni usate nel fotogramma prima per ogni volume (aggiornato qui).
    head_only: solo la testa (per l'avambraccio: vicino alla spalla il braccio tocca il busto per anatomia)."""
    q = p.copy()
    spheres = [] if head_only else body_spheres(sk, W, side)
    used = {}
    for _ in range(2):
        d = head_push(sk, W, q, r, margin, memo.get('head') if memo else None)
        if d.length > 1e-9:
            used['head'] = d.normalized()
        q += d
        for (key, c, R) in spheres:
            d = sphere_push(c, R, q, r, margin, memo.get(key) if memo else None)
            if d.length > 1e-9:
                used[key] = d.normalized()
            q += d
    if memo is not None:
        memo.clear(); memo.update(used)
    return q - p


def _swing(a, b):
    """rotazione minima (3x3) che porta la direzione a sulla direzione b: la torsione dell'osso non cambia."""
    if a.length < 1e-9 or b.length < 1e-9:
        return Matrix.Identity(3)
    return a.normalized().rotation_difference(b.normalized()).to_matrix()


def resolve_arms(ctx, poses, margin=0.006, sides='LR', iterations=4):
    """corregge le braccia che entrano nel corpo, fotogramma per fotogramma. Restituisce il numero di correzioni.
    Coppie controllate (le stesse delle misure): mano-testa, avambraccio-testa, mano-busto, mano-gamba dello stesso lato.

    Metodo (tipo FABRIK, solo in avanti dalla spalla): si calcolano dove dovrebbero stare gomito e polso per uscire dai
    volumi, poi si ruotano braccio e avambraccio con la rotazione minima verso quei punti. Le rotazioni minime conservano
    la torsione del mocap (niente scatti quando la correzione si accende o si spegne); la mano segue l'avambraccio."""
    sk = ctx.sk
    fixes = 0
    memo = {s: {'hand': {}, 'fw': {}, 'fe': {}} for s in sides}
    for pose in poses:
        W = None
        for s in sides:
            ua, fa, hd = 'upper_arm.' + s, 'forearm.' + s, 'hand.' + s
            if ua not in sk.parent or hd not in sk.parent:
                continue
            if W is None:
                W = sk.fk(pose)
            mats = W
            for b in (ua, fa):                          # le pose possono condividere oggetti tra fotogrammi: si copia
                if b in pose:
                    pose[b] = pose[b].copy()
            touched = False
            mm = memo[s]
            for it in range(iterations):
                # le direzioni del fotogramma prima valgono solo alla prima iterazione (poi si parte da quelle nuove)
                pw = push_for(sk, mats, point(sk, mats, hd, 0.5), 0.040, s, margin, mm['hand'])
                pf = push_for(sk, mats, point(sk, mats, fa, 0.75), 0.028, s, margin, mm['fw'], head_only=True)
                pe = push_for(sk, mats, point(sk, mats, fa, 0.3), 0.028, s, margin, mm['fe'], head_only=True)
                if pf.length > pw.length:
                    pw = pf
                if pw.length < 2e-4 and pe.length < 2e-4:
                    break
                S = mats[ua].translation.copy(); E0 = mats[fa].translation.copy(); W0 = mats[hd].translation.copy()
                L1 = (E0 - S).length
                e_star = E0 + pe
                w_star = W0 + pw + pe * 0.5
                E1 = S + (e_star - S).normalized() * L1
                # braccio: rotazione minima verso il nuovo gomito
                Rua = _swing(E0 - S, E1 - S) @ mats[ua].to_3x3().normalized()
                sk.set_world_rotation(pose, ua, Rua, mats)
                base = sk.base_matrix(fa, mats)
                mats[fa] = base @ pose.get(fa, BonePose()).matrix()
                # avambraccio: dal nuovo gomito verso il polso desiderato
                Rfa = mats[fa].to_3x3().normalized()
                yf = Rfa @ Vector((0.0, 1.0, 0.0))
                Rfa = _swing(yf, w_star - mats[fa].translation) @ Rfa
                sk.set_world_rotation(pose, fa, Rfa, mats)
                base = sk.base_matrix(hd, mats)
                mats[hd] = base @ pose.get(hd, BonePose()).matrix()
                touched = True
            if touched:
                fixes += 1
                W = None                                 # l'altro braccio riparte da una cinematica pulita
    return fixes
