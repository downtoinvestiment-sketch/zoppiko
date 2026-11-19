"""Canali del viso: espressioni -> rotazioni di sopracciglia, palpebre, occhi e ciuffo, piu' le proprieta' della bocca.

Un «viso» e' un dizionario piatto di canali numerici, facile da mescolare:
  brow_raise.L, brow_tilt.L, brow_in.L, lid.L, lid_tilt.L, low.L (e .R), eye_yaw, eye_pitch, pupil, blush,
  m.<forma bocca> (pesi), c.<posa ciuffo> (pesi).
"""
import math
from mathutils import Quaternion, Euler

from .. import config as C
from ..character.skeleton import BonePose, euler_q, slerp
from ..character import facial as F

SIDES = ('L', 'R')
SIDE_KEYS = ('brow_raise', 'brow_tilt', 'brow_in', 'lid', 'lid_tilt', 'low')


def neutral():
    ch = {}
    for s in SIDES:
        ch.update({'brow_raise.' + s: 0.0, 'brow_tilt.' + s: 0.0, 'brow_in.' + s: 0.0, 'lid.' + s: 1.0, 'lid_tilt.' + s: 0.0,
                   'low.' + s: 0.0})
    ch.update({'eye_yaw': 0.0, 'eye_pitch': 0.0, 'pupil': 0.55, 'blush': 0.0})
    for m in C.MOUTH_SHAPES:
        ch['m.' + m] = 0.0
    for c in C.CURL_POSES:
        ch['c.' + c] = 0.0
    return ch


NEUTRAL = neutral()


def resolve(name):
    name = C.ALIASES.get(name, name)
    if name not in C.EXPRESSIONS:
        raise KeyError('espressione sconosciuta: %s (disponibili: %s)' % (name, ', '.join(sorted(C.EXPRESSIONS))))
    return name


def expression(name, intensity=1.0):
    """canali di un'espressione. intensity > 1 esagera (caricatura), < 1 attenua."""
    e = C.EXPRESSIONS[resolve(name)]
    ch = neutral()
    for s in SIDES:
        for k in SIDE_KEYS:
            v = e.get(k, NEUTRAL[k + '.' + s])
            v = e.get('side', {}).get(s, {}).get(k, v)
            ch[k + '.' + s] = v
    ch['pupil'] = e.get('pupil', 0.55); ch['blush'] = e.get('blush', 0.0)
    if 'eyes' in e:
        ch['eye_yaw'], ch['eye_pitch'] = e['eyes']
    for m, w in e.get('mouth', {}).items():
        if m in C.MOUTH_SHAPES:
            ch['m.' + m] = w
    for c, w in e.get('curl', {}).items():
        ch['c.' + c] = w
    if intensity != 1.0:
        ch = mix(NEUTRAL, ch, intensity)
    return clamp(ch)


def mix(a, b, t):
    """interpolazione (t puo' andare oltre 1 per esagerare)."""
    out = {}
    for k in NEUTRAL:
        va = a.get(k, NEUTRAL[k]); vb = b.get(k, NEUTRAL[k])
        out[k] = va + (vb - va) * t
    return out


def add(base, delta, w=1.0):
    out = dict(base)
    for k, v in delta.items():
        out[k] = out.get(k, NEUTRAL.get(k, 0.0)) + (v - NEUTRAL.get(k, 0.0)) * w
    return out


def clamp(ch):
    for s in SIDES:
        ch['lid.' + s] = max(0.0, min(1.35, ch['lid.' + s]))
        ch['low.' + s] = max(0.0, min(1.0, ch['low.' + s]))
    ch['pupil'] = max(0.0, min(1.0, ch['pupil'])); ch['blush'] = max(0.0, min(1.0, ch['blush']))
    tot = 0.0
    for m in C.MOUTH_SHAPES:
        ch['m.' + m] = max(0.0, ch['m.' + m]); tot += ch['m.' + m]
    if tot > 1.0:                                 # le forme della bocca restano una combinazione convessa
        for m in C.MOUTH_SHAPES:
            ch['m.' + m] /= tot
    for c in C.CURL_POSES:
        ch['c.' + c] = max(0.0, min(1.0, ch['c.' + c]))
    return ch


# ------------------------------------------------------------------ canali -> pose delle ossa
def lid_angles(lid, low, pitch):
    """angoli (gradi) del bordo della palpebra superiore e inferiore rispetto allo sguardo."""
    gamma = F.LID_LOW_REST + 45.0 * low + 0.35 * pitch
    b1 = F.LID_UP_REST + 0.75 * pitch
    b0 = gamma - 7.0
    if lid <= 1.0:
        beta = b0 + (b1 - b0) * lid
    else:
        beta = b1 + (lid - 1.0) * 80.0
    return min(86.0, beta), gamma


def apply(ch, pose, curl_poses, eye_extra=None):
    """scrive in pose (dict nome->BonePose) le rotazioni del viso; restituisce le proprieta' dell'osso «face»."""
    ey = ch.get('eye_yaw', 0.0); ep = ch.get('eye_pitch', 0.0)
    for s in SIDES:
        sg = 1.0 if s == 'L' else -1.0
        # 1 grado attorno al centro della testa = circa 3 mm sulla fronte: valori scritti «da animatore», qui ridotti
        pose['brow.' + s] = BonePose(rot=euler_q((0.45 * ch['brow_raise.' + s], sg * ch['brow_tilt.' + s], -sg * 0.5 * ch['brow_in.' + s])))
        yaw, pitch = ey, ep
        if eye_extra and s in eye_extra:
            yaw += eye_extra[s][0]; pitch += eye_extra[s][1]
        pose['eye.' + s] = BonePose(rot=euler_q((pitch, 0.0, yaw)))
        beta, gamma = lid_angles(ch['lid.' + s], ch['low.' + s], pitch)
        pose['lid_up.' + s] = BonePose(rot=euler_q((beta - F.LID_UP_REST, sg * ch['lid_tilt.' + s], 0.0)))
        pose['lid_low.' + s] = BonePose(rot=euler_q((gamma - F.LID_LOW_REST, -sg * 0.3 * ch['lid_tilt.' + s], 0.0)))
    # ciuffo: parte dal «?» di base e va verso le pose richieste, nell'ordine
    names = ['curl.%02d' % (k + 1) for k in range(C.CURL['bones'])]
    for n in names:
        q = curl_poses['default'][n].copy() if 'default' in curl_poses else Quaternion()
        for c in C.CURL_POSES:
            w = ch.get('c.' + c, 0.0)
            if w > 1e-4 and c in curl_poses:
                q = slerp(q, curl_poses[c][n], min(1.0, w))
        bp = pose.get(n)
        if bp is None:
            pose[n] = BonePose(rot=q)
        else:
            bp.rot = q @ bp.rot
    props = {m: ch['m.' + m] for m in C.MOUTH_SHAPES}
    props['pupil'] = ch['pupil']; props['blush'] = ch['blush']
    return props
