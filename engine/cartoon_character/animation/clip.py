"""Clip di animazione: tracce di chiavi con interpolazione morbida, viso, IK di piedi e mani, eventi.

Le pose si scrivono in gradi (Euler XYZ nello spazio locale dell'osso). Una chiave su «upper_arm» vale per entrambi i lati
(il destro viene specchiato da solo); «upper_arm.R» vale solo per il destro ma si scrive con i valori «del sinistro».

Interpolazione: Hermite cubica con tangenti «auto clamped» (come Blender): fluida tra le chiavi, senza superare i valori
estremi. Per chiave si puo' chiedere 'stop' (arriva e riparte da fermo), 'linear', 'hold' (scatto), 'fast' (arrivo secco).
"""
import math
import random
from mathutils import Vector, Matrix, Quaternion, Euler

from .. import config as C
from ..character.skeleton import BonePose, euler_q, mirror_euler, mirror_name, slerp
from . import face as FACE

CENTER = ('root', 'hips', 'spine', 'chest', 'neck', 'head')


def hips_local(d):
    """spostamento dei fianchi scritto come nel mondo (x sinistra, y indietro, z su) -> spazio locale dell'osso hips."""
    return Vector((d[0], d[2], -d[1]))


# ------------------------------------------------------------------ tracce
class Track:
    def __init__(self, size):
        self.size = size
        self.keys = []              # (t, valori, modo)
        self._dirty = True
        self.period = None          # per i cicli: tangenti continue tra l'ultima e la prima chiave

    def add(self, t, value, mode='auto'):
        value = tuple(float(v) for v in value)
        self.keys = [k for k in self.keys if abs(k[0] - t) > 1e-6]
        self.keys.append((float(t), value, mode))
        self.keys.sort(key=lambda k: k[0])
        self._dirty = True

    def _tangents(self):
        K = self.keys
        n = len(K)
        tans = []
        cyc = self.period is not None and n > 2 and abs(K[0][0]) < 1e-6 and abs(K[-1][0] - self.period) < 1e-6
        for i in range(n):
            mode = K[i][2]
            edge = i == 0 or i == n - 1
            if n == 1 or mode in ('stop', 'hold') or (edge and not cyc):
                tans.append([0.0] * self.size)
                continue
            if edge:
                if i == 0:
                    t0, v0 = K[-2][0] - self.period, K[-2][1]; t2, v2 = K[1][0], K[1][1]
                else:
                    t0, v0 = K[-2][0], K[-2][1]; t2, v2 = K[1][0] + self.period, K[1][1]
                t1, v1 = K[i][0], K[i][1]
            else:
                t0, v0, _ = K[i - 1]; t1, v1, _ = K[i]; t2, v2, _ = K[i + 1]
            m = []
            for c in range(self.size):
                if (v1[c] - v0[c]) * (v2[c] - v1[c]) <= 0:        # estremo locale: tangente piatta (niente sbordare)
                    m.append(0.0)
                else:
                    s = (v2[c] - v0[c]) / max(1e-6, t2 - t0)
                    # limita la tangente per restare monotona (Fritsch-Carlson semplificato)
                    s0 = (v1[c] - v0[c]) / max(1e-6, t1 - t0); s1 = (v2[c] - v1[c]) / max(1e-6, t2 - t1)
                    lim = 3.0 * min(abs(s0), abs(s1))
                    m.append(max(-lim, min(lim, s)))
            tans.append(m)
        self._tan = tans
        self._dirty = False

    def eval(self, t):
        K = self.keys
        if not K:
            return None
        if t <= K[0][0]:
            return K[0][1]
        if t >= K[-1][0]:
            return K[-1][1]
        if self._dirty:
            self._tangents()
        lo, hi = 0, len(K) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if K[mid][0] <= t:
                lo = mid
            else:
                hi = mid
        t0, v0, _ = K[lo]; t1, v1, mode = K[hi]
        dt = t1 - t0
        x = (t - t0) / dt
        if mode == 'hold':
            return v0
        if mode == 'linear':
            return tuple(a + (b - a) * x for a, b in zip(v0, v1))
        if mode == 'fast':                       # parte veloce e arriva frenando forte (scatto cartoon)
            e = 1 - (1 - x) ** 3
            return tuple(a + (b - a) * e for a, b in zip(v0, v1))
        if mode == 'slow':                       # parte piano e accelera (caduta)
            e = x ** 2.2
            return tuple(a + (b - a) * e for a, b in zip(v0, v1))
        m0 = self._tan[lo]; m1 = self._tan[hi]
        if K[lo][2] == 'fast':
            m0 = [0.0] * self.size
        h00 = 2 * x ** 3 - 3 * x ** 2 + 1; h10 = x ** 3 - 2 * x ** 2 + x; h01 = -2 * x ** 3 + 3 * x ** 2; h11 = x ** 3 - x ** 2
        return tuple(h00 * a + h10 * dt * ma + h01 * b + h11 * dt * mb for a, b, ma, mb in zip(v0, v1, m0, m1))

    def times(self):
        return [k[0] for k in self.keys]


class Rel:
    """bersaglio relativo a un osso (es. davanti alla faccia): si calcola con la posa del momento.
    offset nello spazio dell'osso a riposo allineato: per la testa Y = su, Z = avanti, X = sinistra del personaggio."""
    def __init__(self, bone, offset):
        self.bone = bone; self.offset = Vector(offset)

    def resolve(self, ctx, mats):
        return mats[self.bone] @ self.offset


class FaceTrack:
    """cambi d'espressione con transizione: (inizio, canali, durata della transizione)."""

    def __init__(self):
        self.keys = []

    def add(self, t, channels, dur=0.2):
        self.keys.append((float(t), channels, max(1e-3, float(dur))))
        self.keys.sort(key=lambda k: k[0])

    def eval(self, t):
        if not self.keys:
            return None
        cur = self.keys[0][1]
        if t < self.keys[0][0]:
            return dict(cur)
        for (t0, ch, d) in self.keys[1:]:
            if t < t0:
                break
            x = min(1.0, (t - t0) / d)
            e = x * x * (3 - 2 * x)
            cur = FACE.mix(cur, ch, e) if e < 1 else ch
        return dict(cur)


# ------------------------------------------------------------------ fotogramma valutato
class Frame:
    __slots__ = ('pose', 'face', 'events', 'contacts', 'hands', 'objects')

    def __init__(self, pose=None, face=None):
        self.pose = pose or {}
        self.face = face
        self.events = []
        self.contacts = {}          # 'L'/'R' -> True se il piede e' appoggiato (per il blocco dei piedi e i test)
        self.hands = {}             # 'L'/'R' -> posizione del polso (spazio clip), utile per gli oggetti
        self.objects = {}


# ------------------------------------------------------------------ forme della mano (valori «del lato sinistro»)
def _fingers(c1, c2, c3, thumb=(10, 8), spread=0.0, index=None):
    d = {}
    for k, n in enumerate(C.FINGERS['names']):
        sp = spread * (1 - k)            # indice verso il pollice, anulare dall'altra parte
        vals = index if (index is not None and n == 'f_index') else (c1, c2, c3)
        d[n + '.01'] = (vals[0], 0.0, sp)
        d[n + '.02'] = (vals[1], 0.0, 0.0)
        d[n + '.03'] = (vals[2], 0.0, 0.0)
    d['thumb.01'] = (thumb[0], 0.0, 0.0); d['thumb.02'] = (thumb[1], 0.0, 0.0)
    return d


HAND_SHAPES = {
    'relax': _fingers(14, 16, 10, (8, 10)),
    'open': _fingers(-4, -2, 0, (-6, 0), spread=9.0),
    'fist': _fingers(82, 92, 70, (38, 52)),
    'point': _fingers(80, 92, 70, (36, 46), index=(0, 0, 0)),
    'grab': _fingers(42, 48, 30, (22, 20)),
    'thumbs_up': _fingers(82, 92, 70, (-18, -10)),
    'claw': _fingers(30, 55, 50, (20, 30), spread=6.0),
    'flat': _fingers(0, 0, 0, (0, 0)),
}


# ------------------------------------------------------------------ informazioni sul personaggio (dal rig costruito)
class RigInfo:
    def __init__(self, skeleton, curl_poses):
        self.sk = skeleton
        self.curl_poses = curl_poses
        mats = skeleton.fk({})
        self.rest_mats = mats
        self.ankle = {s: skeleton.head(mats, 'foot.' + s) for s in 'LR'}
        self.ball = {s: skeleton.head(mats, 'toe.' + s) for s in 'LR'}
        self.wrist = {s: skeleton.head(mats, 'hand.' + s) for s in 'LR'}
        self.shoulder = {s: skeleton.head(mats, 'upper_arm.' + s) for s in 'LR'}
        self.hip = {s: skeleton.head(mats, 'thigh.' + s) for s in 'LR'}
        self.hips_rest = skeleton.head(mats, 'hips')
        self.foot_rest = {s: mats['foot.' + s].to_3x3().normalized() for s in 'LR'}
        self.hand_rest = {s: mats['hand.' + s].to_3x3().normalized() for s in 'LR'}
        a = Vector(C.J['ankle'])
        self.heel_off = Vector((0.0, C.FOOT['heel'][1], -a.z))           # tallone a terra rispetto alla caviglia
        self.ball_off = Vector((0.0, C.J['ball'][1] - a.y, -a.z))         # pianta sotto l'articolazione delle dita
        self.ankle_h = a.z
        self.leg_len = skeleton.length['thigh.L'] + skeleton.length['shin.L']

    def foot_matrix(self, side, yaw_deg, pitch_deg=0.0, roll_deg=0.0):
        Rz = Matrix.Rotation(math.radians(yaw_deg), 3, 'Z')
        Rl = Euler((math.radians(pitch_deg), math.radians(roll_deg), 0.0), 'XYZ').to_matrix()
        return Rz @ self.foot_rest[side] @ Rl


# ------------------------------------------------------------------ clip a chiavi
def _expand(spec):
    """{'upper_arm': (x,y,z), 'head': ...} -> {'upper_arm.L': ..., 'upper_arm.R': (specchiato), ...}"""
    out = {}
    for k, v in spec.items():
        if k.endswith('.L') or k.endswith('.R') or k in CENTER or k.startswith('curl') or k in ('face', 'eye_target'):
            if k.endswith('.R'):
                out[k] = mirror_euler(v)
            else:
                out[k] = tuple(v)
        else:
            out[k + '.L'] = tuple(v); out[k + '.R'] = mirror_euler(v)
    return out


class Motion:
    """clip fatto di chiavi. Vedi motion_library.py per gli esempi."""
    kind = 'keys'

    def __init__(self, name, duration, category='misc', loop=False, start='stand', end='stand', base=None, description=''):
        self.name = name; self.duration = float(duration); self.category = category; self.loop = loop
        self.start_state = start; self.end_state = end; self.description = description
        self.rot = {}; self.loc = {}; self.scl = {}
        self.root_track = Track(3)
        self.feet = {}              # side -> Track(6): x, y, z, yaw, pitch, peso
        self.hands = {}             # side -> lista di chiavi (t, posizione o funzione, rotazione o None, peso, modo, polo)
        self.face_track = FaceTrack()
        self.events = []
        self.noise = []
        self.procs = []
        self.params = {}
        if base:
            self.pose(0.0, base)

    # --------------------------------------------------------------- scrittura
    def pose(self, t, spec, mode='auto'):
        for bone, v in _expand(spec).items():
            self.rot.setdefault(bone, Track(3)).add(t, v, mode)
        return self

    def hand_shape(self, t, side, shape, mode='auto', amount=1.0):
        sh = HAND_SHAPES[shape]
        sides = ('L', 'R') if side in ('both', 'LR') else (side,)
        for s in sides:
            for k, v in sh.items():
                vv = tuple(x * amount for x in v)
                self.rot.setdefault('%s.%s' % (k, s), Track(3)).add(t, vv if s == 'L' else mirror_euler(vv), mode)
        return self

    def hips(self, t, loc=None, rot=None, scale=None, mode='auto'):
        if loc is not None:
            self.loc.setdefault('hips', Track(3)).add(t, loc, mode)
        if rot is not None:
            self.rot.setdefault('hips', Track(3)).add(t, rot, mode)
        if scale is not None:
            self.scl.setdefault('hips', Track(3)).add(t, scale, mode)
        return self

    def scale(self, t, bone, s, mode='auto'):
        for b in ([bone + '.L', bone + '.R'] if bone not in CENTER and not bone[-2:] in ('.L', '.R') else [bone]):
            self.scl.setdefault(b, Track(3)).add(t, s, mode)
        return self

    def root(self, t, x=0.0, y=0.0, yaw=0.0, mode='auto'):
        self.root_track.add(t, (x, y, yaw), mode)
        return self

    def foot(self, t, side, pos, yaw=0.0, pitch=0.0, w=1.0, mode='auto'):
        self.feet.setdefault(side, Track(6)).add(t, (*pos, yaw, pitch, w), mode)
        return self

    def plant_feet(self, t, mode='auto', spread=0.0, y=0.0):
        """i due piedi fermi nella posizione di riposo (spostati di y)."""
        for s in 'LR':
            a = Vector(C.J['ankle'])
            x = a.x + spread if s == 'L' else -(a.x + spread)
            self.foot(t, s, (x, a.y + y, a.z), 0.0, 0.0, 1.0, mode)
        return self

    def hand(self, t, side, pos, rot=None, w=1.0, mode='auto', pole=None):
        """bersaglio del polso in spazio clip (o funzione(params, ctx) -> posizione); rot = Euler in gradi nello spazio clip."""
        self.hands.setdefault(side, []).append((float(t), pos, rot, float(w), mode, pole))
        self.hands[side].sort(key=lambda k: k[0])
        return self

    def face(self, t, name_or_channels, dur=0.18, intensity=1.0):
        ch = FACE.expression(name_or_channels, intensity) if isinstance(name_or_channels, str) else name_or_channels
        self.face_track.add(t, ch, dur)
        return self

    def event(self, t, name, **data):
        self.events.append((float(t), name, data))
        return self

    def shake(self, t0, t1, bones, amp=3.0, freq=11.0, seed=1, fade=0.15):
        self.noise.append((t0, t1, bones, amp, freq, seed, fade))
        return self

    def proc(self, fn):
        self.procs.append(fn)
        return self

    # --------------------------------------------------------------- lettura
    def _hand_eval(self, side, t, params, ctx, mats=None):
        keys = self.hands.get(side)
        if not keys:
            return None
        def resolve(p):
            if isinstance(p, Rel):
                return p.resolve(ctx, mats)
            return Vector(p(params, ctx)) if callable(p) else Vector(p)
        if t <= keys[0][0]:
            k = keys[0]; return resolve(k[1]), _q(k[2]), k[3], k[5]
        if t >= keys[-1][0]:
            k = keys[-1]; return resolve(k[1]), _q(k[2]), k[3], k[5]
        for i in range(len(keys) - 1):
            a, b = keys[i], keys[i + 1]
            if a[0] <= t <= b[0]:
                x = (t - a[0]) / max(1e-6, b[0] - a[0])
                mode = b[4]
                e = x if mode == 'linear' else (1 - (1 - x) ** 3 if mode == 'fast' else x * x * (3 - 2 * x))
                pa, pb = resolve(a[1]), resolve(b[1])
                rot = None
                qa = _q(a[2]); qb = _q(b[2])
                if qa is not None and qb is not None:
                    rot = slerp(qa, qb, e)
                elif qb is not None:
                    rot = qb
                elif qa is not None:                # mentre il peso dell'IK scende, la mano tiene l'ultimo orientamento
                    rot = qa
                pole = b[5] if b[5] is not None else a[5]
                return pa.lerp(pb, e), rot, a[3] + (b[3] - a[3]) * e, pole
        return None

    def evaluate(self, t, ctx, params=None, t_prev=None):
        params = params or {}
        if self.loop and self.duration > 0:
            t = t % self.duration
            if not getattr(self, '_cyc', False):
                for tr in list(self.rot.values()) + list(self.loc.values()) + list(self.scl.values()) + list(self.feet.values()):
                    tr.period = self.duration; tr._dirty = True
                self._cyc = True
        sk = ctx.sk
        pose = {}
        for b, tr in self.rot.items():
            v = tr.eval(t)
            if v is not None:
                pose[b] = BonePose(rot=euler_q(v))
        for b, tr in self.loc.items():
            v = tr.eval(t)
            if v is not None:
                pose.setdefault(b, BonePose()).loc = hips_local(v) if b == 'hips' else Vector(v)
        for b, tr in self.scl.items():
            v = tr.eval(t)
            if v is not None:
                pose.setdefault(b, BonePose()).scl = Vector(v)
        rv = self.root_track.eval(t) or (0.0, 0.0, 0.0)
        pose['root'] = BonePose(loc=(rv[0], rv[1], 0.0), rot=Quaternion((0, 0, 1), math.radians(rv[2])))
        for (t0, t1, bones, amp, freq, seed, fade) in self.noise:
            if t0 <= t <= t1:
                env = min(1.0, (t - t0) / fade, (t1 - t) / fade) if fade > 0 else 1.0
                rnd = random.Random(seed)
                for b in bones:
                    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
                    v = tuple(amp * env * math.sin(freq * 6.283 * t * (1 + 0.13 * i) + ph[i]) for i in range(3))
                    bp = pose.setdefault(b, BonePose())
                    bp.rot = bp.rot @ euler_q(v)
        for fn in self.procs:
            fn(self, t, pose, ctx, params)
        propagate_squash(pose)
        frame = Frame(pose)
        mats = sk.fk(pose)
        root_yaw = rv[2]
        # IK dei piedi (prima abbassa i fianchi se un piede non si raggiunge)
        fv = {s: tr.eval(t) for s, tr in self.feet.items()}
        tg = {s: Vector(v[:3]) for s, v in fv.items() if v is not None and v[5] > 0.99}
        if tg:
            reach_fix(ctx, pose, mats, tg)
        for s, tr in self.feet.items():
            v = fv[s]
            if v is None or v[5] <= 1e-4:
                continue
            x, y, z, yaw, pitch, w = v
            solve_leg(ctx, pose, mats, s, Vector((x, y, z)), yaw, pitch, w)
            vp = self.feet[s].eval(max(0.0, t - 1.0 / 48))
            moving = vp is not None and math.hypot(vp[0] - x, vp[1] - y) * 48 > 0.05
            frame.contacts[s] = (w > 0.99 and z <= ctx.ankle_h + 0.004 and abs(pitch) < 1.0 and not moving)
        # IK delle mani
        for s in ('L', 'R'):
            hv = self._hand_eval(s, t, params, ctx, mats)
            if hv is None:
                continue
            pos, rot, w, pole = hv
            if w <= 1e-4:
                continue
            solve_arm(ctx, pose, mats, s, pos, rot, w, pole)
            frame.hands[s] = pos
        frame.face = self.face_track.eval(t)
        if t_prev is not None:
            for (te, name, data) in self.events:
                if t_prev < te <= t:
                    frame.events.append((name, data))
        return frame


def propagate_squash(pose):
    """il petto non eredita la scala della colonna (inherit NONE, per evitare il taglio): qui la si compone a mano."""
    sp = pose.get('spine')
    if sp is not None and (sp.scl - Vector((1, 1, 1))).length > 1e-6:
        ch = pose.setdefault('chest', BonePose())
        ch.scl = Vector((ch.scl.x * sp.scl.x, ch.scl.y * sp.scl.y, ch.scl.z * sp.scl.z))


def _q(r):
    if r is None:
        return None
    if isinstance(r, Quaternion):
        return r
    return euler_q(r)


# ------------------------------------------------------------------ IK di gambe e braccia (risultato scritto come FK)
def reach_fix(ctx, pose, mats, targets, margin=0.985):
    """abbassa i fianchi quanto basta perche' le caviglie bersaglio siano raggiungibili (niente piedi che restano indietro)."""
    sk = ctx.sk
    drop = 0.0
    for s, A in targets.items():
        H = mats['thigh.' + s].translation
        L = (sk.length['thigh.' + s] + sk.length['shin.' + s]) * margin
        d = H - A
        h = math.hypot(d.x, d.y)
        if d.length > L and h < L:
            drop = max(drop, d.z - math.sqrt(L * L - h * h))
    if drop > 1e-5:
        bp = pose.setdefault('hips', BonePose())
        bp.loc = bp.loc + hips_local((0.0, 0.0, -drop))
        new = sk.fk(pose)
        mats.clear(); mats.update(new)
    return drop


def solve_leg(ctx, pose, mats, s, ankle, yaw, pitch, w=1.0, pole=None, soft=0.012, rot=None):
    sk = ctx.sk
    thigh, shin, foot = 'thigh.' + s, 'shin.' + s, 'foot.' + s
    old = {n: (pose[n].rot.copy() if n in pose else Quaternion()) for n in (thigh, shin, foot)}
    hip = mats[thigh].translation
    fwd = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Vector((0, -1, 0))
    if pole is None:
        # il ginocchio va verso il davanti del bacino (anche sdraiati o con il piede alto) e verso la punta del piede
        Rh = mats['hips'].to_3x3().normalized()
        front = (Rh @ Vector((0.0, 0.0, 1.0))).normalized() + fwd * 0.6
        up = Rh @ Vector((0.0, 1.0, 0.0))
        pole = hip + front.normalized() * 0.6 + up * 0.12
    R = rot if rot is not None else ctx.foot_matrix(s, yaw, pitch)
    sk.two_bone(pose, thigh, shin, ankle, pole, mats, end=foot, end_rot=R, soft=soft)
    if w < 1.0:
        for n in (thigh, shin, foot):
            pose[n].rot = slerp(old[n], pose[n].rot, w)
        for n in (thigh,):
            base = sk.base_matrix(n, mats); mats[n] = base @ pose[n].matrix(); sk.update_subtree(pose, n, mats)


def solve_arm(ctx, pose, mats, s, wrist, rot=None, w=1.0, pole=None):
    sk = ctx.sk
    up, fo, ha = 'upper_arm.' + s, 'forearm.' + s, 'hand.' + s
    old = {n: (pose[n].rot.copy() if n in pose else Quaternion()) for n in (up, fo, ha)}
    S = mats[up].translation
    if pole is None:
        # polo dal gomito della posa FK attuale: il piano del braccio resta quello dell'FK (niente torsioni nel passaggio FK -> IK)
        E = mats[fo].translation; Wp = mats[ha].translation
        d = E - (S + Wp) * 0.5
        if d.length < 0.004:
            d = -(mats[up].to_3x3().normalized() @ Vector((0.0, 0.0, 1.0)))
        pole = E + d.normalized() * 0.3
    else:
        pole = Vector(pole)
    R = None
    if rot is not None:
        R = rot.to_matrix() @ ctx.hand_rest[s] if isinstance(rot, Quaternion) else rot
    if w < 1.0:
        # il peso dell'IK mescola i BERSAGLI nel mondo (posizione e orientamento della mano), non le rotazioni locali:
        # cosi' il passaggio FK -> IK non torce il braccio
        Wfk = mats[ha].translation.copy()
        Rfk = mats[ha].to_3x3().normalized()
        wrist = Wfk.lerp(Vector(wrist), w)
        if R is not None:
            R = slerp(Rfk.to_quaternion(), R.to_quaternion() if hasattr(R, 'to_quaternion') else R, w).to_matrix()
        else:
            R = Rfk
    sk.two_bone(pose, up, fo, wrist, pole, mats, end=ha, end_rot=R)
