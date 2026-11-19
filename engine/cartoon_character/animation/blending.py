"""Montaggio e cottura: mette in fila le clip con dissolvenze, aggiunge espressioni, sguardo, battito delle palpebre,
labiale, molle del ciuffo, blocco dei piedi, oggetti in mano; poi scrive tutto in una Action di Blender (una chiave per
fotogramma, FK puro: si mescola e si trasferisce senza vincoli attivi).

Radice: ogni clip parte dove la precedente finisce (posizione e direzione alla FINE della clip precedente), cosi' durante
la dissolvenza il personaggio non torna mai indietro e, finita la dissolvenza, la clip e' esattamente dove deve essere
(importante per prendere oggetti).
"""
import math
import random
from mathutils import Vector, Matrix, Quaternion, Euler

from .. import config as C
from ..character.skeleton import BonePose, euler_q, slerp
from . import face as FACE
from .clip import solve_leg, RigInfo


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def yaw_of(q):
    v = q @ Vector((0, -1, 0))
    return math.atan2(v.x, -v.y)


def root_matrix(bp):
    return Matrix.Translation(bp.loc) @ bp.rot.to_matrix().to_4x4()


def mat_to_root(M):
    loc = M.translation.copy(); loc.z = 0.0
    yaw = yaw_of(M.to_quaternion())
    return BonePose(loc=loc, rot=Quaternion((0, 0, 1), yaw))


def _knee_pole(sk, M, side):
    """polo lungo l'asse Z (avanti) della coscia attuale: il piano della gamba non cambia, anche a gamba tesa."""
    knee = M['shin.' + side].translation
    z = (M['thigh.' + side].to_3x3().normalized() @ Vector((0.0, 0.0, 1.0))).normalized()
    return knee + z * 0.3


class ClipInstance:
    def __init__(self, motion, start, duration, blend, params, origin, speed=1.0):
        self.motion = motion; self.start = start; self.duration = duration; self.blend = blend
        self.params = params or {}; self.origin = origin; self.speed = speed
        self.name = motion.name

    @property
    def end(self):
        return self.start + self.duration

    def local_t(self, t):
        return (t - self.start) * self.speed


class Timeline:
    def __init__(self, ctx, fps=C.FPS, seed=1):
        self.ctx = ctx
        self.fps = fps
        self.clips = []
        self.expressions = []      # (inizio, fine, canali, entrata, uscita, peso)
        self.looks = []            # (inizio, fine, bersaglio, entrata, uscita)
        self.visemes = []          # (tempo, forma, peso)
        self.objects = {}          # nome -> dict(obj=oggetto Blender, attach=[...])
        self.seed = seed
        self.blinks = True
        self.secondary = True
        self.foot_lock = True
        self.clearance = True       # mani e avambracci fuori da testa, busto e gambe (vedi collide.resolve_arms)
        self.origin = Matrix.Identity(4)
        self.state = 'stand'
        self.cursor = 0.0
        self.data = None

    # --------------------------------------------------------------- costruzione
    def end_root(self, clip):
        """trasformazione del mondo della radice alla fine della clip."""
        fr = clip.motion.evaluate(clip.duration * clip.speed - 1e-6 if not clip.motion.loop else clip.duration * clip.speed,
                                  self.ctx, clip.params)
        return clip.origin @ root_matrix(fr.pose['root'])

    def add(self, motion, duration=None, blend=0.25, params=None, start=None, speed=1.0, auto=True):
        # da un ciclo di locomozione a un movimento fermo: prima una frenata vera (i piedi non scivolano)
        if auto and self.clips:
            prev = self.clips[-1]
            pk = getattr(prev.motion, 'kind', ''); nk = getattr(motion, 'kind', '')
            if pk == 'gait' and nk != 'gait' and motion.name != 'stop':
                from . import procedural as P
                self.snap_gait(prev)
                self.add(P.make_stop(prev.motion.name if prev.motion.name in P.GAITS else 'walk', prev.motion.speed), None, 0.08, auto=False)
        d = duration if duration is not None else motion.duration / speed
        if self.clips and getattr(motion, 'kind', '') == 'gait':
            blend = min(blend, 0.12)          # il primo piede in volo deve atterrare dopo la dissolvenza (niente scivolate)
        if self.clips and motion.name == 'stop' and getattr(self.clips[-1].motion, 'kind', '') == 'gait':
            self.snap_gait(self.clips[-1])
            blend = 0.0                                   # la frenata continua esattamente il passo del ciclo
        if self.clips:
            prev = self.clips[-1]
            origin = self.end_root(prev)
            s = start if start is not None else prev.end - min(blend, prev.duration * 0.5, d * 0.5)
            if blend <= 0:
                s = prev.end
        else:
            origin = self.origin.copy()
            s = start if start is not None else 0.0
            blend = 0.0
        c = ClipInstance(motion, s, d, blend, params, origin, speed)
        self.clips.append(c)
        self.cursor = c.end
        self.state = getattr(motion, 'end_state', 'stand')
        return c

    def snap_gait(self, clip):
        """accorcia/allunga un ciclo perche' finisca con il tallone sinistro a terra (dove parte la frenata)."""
        g = clip.motion
        T = g.cycle
        k = max(1, round((clip.duration / T) + g.phase))
        clip.duration = max(0.3 * T, (k - g.phase) * T)
        self.cursor = clip.end

    def world_to_next_local(self, p):
        """punto del mondo -> spazio della prossima clip (che partira' dalla fine dell'ultima)."""
        origin = self.end_root(self.clips[-1]) if self.clips else self.origin
        return origin.inverted() @ Vector(p)

    def next_origin(self):
        return self.end_root(self.clips[-1]) if self.clips else self.origin.copy()

    def expression(self, channels, start, end, fade_in=0.2, fade_out=0.25, weight=1.0):
        self.expressions.append((start, end, channels, fade_in, fade_out, weight))

    def look_at(self, target, start, end, fade_in=0.3, fade_out=0.3):
        self.looks.append((start, end, target, fade_in, fade_out))

    @property
    def length(self):
        """fine dell'animazione: ultima clip, ultima espressione o sguardo con una fine, ultima sillaba del labiale
        (le espressioni e gli sguardi «per sempre» non allungano la scena)."""
        ends = [c.end for c in self.clips]
        ends += [e[1] for e in self.expressions if e[1] < 1e8]
        ends += [lk[1] for lk in self.looks if lk[1] < 1e8]
        ends += [v[0] + (v[3] if len(v) > 3 else 0.1) for v in self.visemes]
        return max(ends + [0.0])

    # --------------------------------------------------------------- valutazione del corpo
    def body(self, t):
        active = [c for c in self.clips if c.start - 1e-9 <= t < c.end + 1e-9]
        if not active:
            # prima della prima clip o dopo l'ultima: tieni il primo/ultimo fotogramma
            c = self.clips[0] if t < self.clips[0].start else self.clips[-1]
            tt = 0.0 if t < c.start else c.duration * c.speed - 1e-6
            active = [c]
            times = {c: tt}
        else:
            times = {c: min(c.local_t(t), c.duration * c.speed - 1e-6) for c in active}
        pose = None; face = None; contacts = {}; root_M = None; events = []; hands = {}
        for c in active:
            tl = times[c]
            fr = c.motion.evaluate(tl, self.ctx, c.params, tl - c.speed / self.fps)
            M = c.origin @ root_matrix(fr.pose['root'])
            w = 1.0 if (pose is None or c.blend <= 0) else smooth((t - c.start) / c.blend)
            if pose is None:
                pose = {k: v.copy() for k, v in fr.pose.items()}
                face = fr.face; contacts = dict(fr.contacts); root_M = M
            else:
                names = set(pose) | set(fr.pose)
                prev = getattr(self, '_prev_pose', None) or {}
                for n in names:
                    a = pose.get(n) or BonePose(); b = fr.pose.get(n) or BonePose()
                    q1 = slerp(a.rot, b.rot, w)
                    p0 = prev.get(n)
                    if p0 is not None and 0.0 < w < 1.0:
                        # due rotazioni quasi opposte: la strada piu' corta puo' cambiare da un fotogramma all'altro.
                        # Si sceglie la strada piu' vicina al risultato del fotogramma prima (continuita' nel tempo).
                        q2 = a.rot.slerp(-b.rot if a.rot.dot(b.rot) >= 0 else b.rot, w)
                        if abs(q2.dot(p0)) > abs(q1.dot(p0)):
                            q1 = q2
                    pose[n] = BonePose(a.loc.lerp(b.loc, w), q1, a.scl.lerp(b.scl, w))
                if fr.face is not None:
                    face = FACE.mix(face, fr.face, w) if face is not None else fr.face
                for s in 'LR':
                    contacts[s] = (contacts.get(s, False) and fr.contacts.get(s, False)) if 0.05 < w < 0.95 else \
                        (fr.contacts.get(s, False) if w >= 0.95 else contacts.get(s, False))
                pa = root_M.translation; pb = M.translation
                ya = yaw_of(root_M.to_quaternion()); yb = yaw_of(M.to_quaternion())
                dy = (yb - ya + math.pi) % (2 * math.pi) - math.pi
                root_M = Matrix.Translation(pa.lerp(pb, w)) @ Matrix.Rotation(ya + dy * w, 4, 'Z')
            for e in fr.events:
                events.append((c, e))
            for s, p in fr.hands.items():
                hands[s] = (c, p)
        pose['root'] = mat_to_root(root_M)
        self._prev_pose = {k: v.rot.copy() for k, v in pose.items()}
        return pose, face, contacts, events

    # --------------------------------------------------------------- strati del viso
    def face_at(self, t, base):
        ch = dict(base) if base is not None else FACE.neutral()
        for (s, e, chans, fi, fo, w) in self.expressions:
            if s - fi <= t <= e + fo:
                k = w * (smooth((t - (s - fi)) / max(1e-3, fi)) if t < s else (1.0 if t <= e else 1 - smooth((t - e) / max(1e-3, fo))))
                if k > 0:
                    ch = FACE.mix(ch, chans, k)
        return ch

    def blink_curve(self, n):
        rnd = random.Random(self.seed)
        b = [0.0] * n
        t = rnd.uniform(0.6, 1.8)
        while t * self.fps < n:
            f0 = t * self.fps
            for f in range(int(f0), min(n, int(f0 + 0.2 * self.fps) + 1)):
                x = (f - f0) / self.fps
                if x < 0:
                    continue
                v = smooth(x / 0.055) if x < 0.055 else (1.0 if x < 0.085 else 1 - smooth((x - 0.085) / 0.08))
                b[f] = max(b[f], v)
            t += rnd.uniform(2.2, 4.6)
        return b

    def viseme_curve(self, n):
        out = [dict() for _ in range(n)]
        for (t, shape, w, dur) in self.visemes:
            f0 = (t - dur * 0.5) * self.fps; f1 = (t + dur * 0.5) * self.fps
            for f in range(max(0, int(f0) - 2), min(n, int(f1) + 3)):
                x = (f - f0) / max(1e-3, f1 - f0)
                env = math.sin(math.pi * min(1.0, max(0.0, x)))
                if env > 0:
                    out[f][shape] = max(out[f].get(shape, 0.0), w * env)
        return out

    # --------------------------------------------------------------- sguardo
    def _target_point(self, target, t):
        if callable(target):
            return Vector(target(t))
        if hasattr(target, 'matrix_world'):
            return target.matrix_world.translation.copy()
        return Vector(target)

    def apply_look(self, t, pose, mats, eye_state):
        """ruota collo, testa e occhi verso il bersaglio. Restituisce gli angoli extra degli occhi per lato."""
        sk = self.ctx.sk
        best = None
        for (s, e, target, fi, fo) in self.looks:
            if s - fi <= t <= e + fo:
                k = smooth((t - (s - fi)) / max(1e-3, fi)) if t < s else (1.0 if t <= e else 1 - smooth((t - e) / max(1e-3, fo)))
                if k > 0 and (best is None or k > best[0]):
                    best = (k, target)
        if best is None:
            return None, 0.0
        k, target = best
        P = self._target_point(target, t)
        Pl = P                                                # spazio dell'armatura = mondo
        chest = mats['chest']
        eyes_mid = (sk.head(mats, 'eye.L') + sk.head(mats, 'eye.R')) * 0.5
        d = chest.to_3x3().normalized().inverted() @ (Pl - eyes_mid)
        # assi del petto: Y su, Z avanti (-Y del mondo), X sinistra
        yaw = math.degrees(math.atan2(d.x, max(1e-6, d.z))) if d.z > -abs(d.x) * 3 else math.copysign(80.0, d.x)
        pitch = math.degrees(math.atan2(d.y, math.hypot(d.x, d.z)))
        yaw = max(-80.0, min(80.0, yaw)); pitch = max(-40.0, min(35.0, pitch))
        # lo sguardo della testa segue con un piccolo ritardo (filtro)
        st = eye_state.setdefault('look', [yaw, pitch])
        a = 1 - math.exp(-1.0 / (self.fps * 0.10))
        st[0] += (yaw - st[0]) * a; st[1] += (pitch - st[1]) * a
        hy, hp = st[0] * k, st[1] * k
        for n, f in (('neck', 0.35), ('head', 0.6)):
            bp = pose.setdefault(n, BonePose())
            bp.rot = bp.rot @ euler_q((-hp * f, hy * f, 0.0))
        mats2 = sk.fk(pose)
        extra = {}
        for side in 'LR':
            E = sk.head(mats2, 'eye.' + side)
            Rh = mats2['head'].to_3x3().normalized()
            v = Rh.inverted() @ (Pl - E)                    # spazio della testa: Y su (osso), Z avanti
            ey = math.degrees(math.atan2(v.x, max(1e-6, v.z)))
            ep = math.degrees(math.atan2(v.y, math.hypot(v.x, v.z)))
            extra[side] = (max(-32.0, min(32.0, ey)) * k, max(-24.0, min(24.0, ep)) * k)
        return extra, k

    # --------------------------------------------------------------- cottura
    def evaluate_all(self, frames=None):
        ctx = self.ctx; sk = ctx.sk
        n = frames or int(math.ceil(self.length * self.fps)) + 1
        blink = self.blink_curve(n) if self.blinks else [0.0] * n
        vis = self.viseme_curve(n)
        out = []
        eye_state = {}
        self._prev_pose = None
        for f in range(n):
            t = f / self.fps
            pose, face, contacts, events = self.body(t)
            mats = sk.fk(pose)
            ch = self.face_at(t, face)
            # labiale: le forme della bocca vanno verso i visemi (l'espressione resta in parte)
            if vis[f]:
                tot = sum(vis[f].values())
                k = min(1.0, tot)
                for m in C.MOUTH_SHAPES:
                    ch['m.' + m] *= (1 - 0.75 * k)
                for sh, w in vis[f].items():
                    ch['m.' + sh] = ch.get('m.' + sh, 0.0) + w * 0.9
            extra, lk = self.apply_look(t, pose, mats, eye_state)
            if extra:
                ch['eye_yaw'] *= (1 - lk); ch['eye_pitch'] *= (1 - lk)
            if blink[f] > 0:
                for s in 'LR':
                    ch['lid.' + s] = ch['lid.' + s] * (1 - blink[f])
            ch = FACE.clamp(ch)
            props = FACE.apply(ch, pose, ctx.curl_poses, extra)
            out.append(dict(t=t, pose=pose, props=props, contacts=contacts, events=events, face=ch))
        if self.foot_lock:
            self.lock_feet(out)
        if self.clearance:
            from . import collide as CL
            self.arm_fixes = CL.resolve_arms(ctx, [fr['pose'] for fr in out])
        if self.secondary:
            self.springs(out)
        self.data = out
        return out

    # --------------------------------------------------------------- blocco dei piedi e pavimento
    def lock_feet(self, out):
        """blocco dei piedi: se il punto che tocca terra (tallone o pianta) scivola durante un appoggio (succede nelle
        dissolvenze tra clip), sposta la caviglia per annullare lo scivolamento; l'orientamento del piede resta quello
        della clip (il rullare tallone-pianta continua). Alla fine dell'appoggio la correzione si scioglie in pochi fotogrammi."""
        ctx = self.ctx; sk = ctx.sk
        n = len(out)
        for side in 'LR':
            foot = 'foot.' + side
            corr = Vector((0.0, 0.0, 0.0)); prev = None; release = 0
            for k in range(n):
                fr = out[k]; pose = fr['pose']
                M = sk.fk(pose)                      # spazio dell'armatura = mondo (la radice porta la posizione)
                Mf = M[foot]
                Rinv = ctx.foot_rest[side].inverted()
                heel = Mf @ (Rinv @ ctx.heel_off); ball = Mf @ (Rinv @ ctx.ball_off)
                cur = dict(heel=heel, ball=ball)
                contact = fr['contacts'].get(side, False)
                if contact and prev is not None and prev[2]:
                    slide = Vector((0.0, 0.0, 0.0)); best = None
                    for key in ('heel', 'ball'):
                        if cur[key].z < 0.008 and prev[0][key].z < 0.008:
                            d = cur[key] - prev[0][key]; d.z = 0.0
                            if best is None or d.length < best.length:
                                best = d
                    if best is not None:
                        corr = corr - best
                        if corr.length > 0.03:              # oltre 3 cm non e' uno scivolamento ma un passo mancante
                            corr = corr.normalized() * 0.03
                    release = 4
                elif not contact and release > 0:
                    corr = corr * (release - 1) / release
                    release -= 1
                elif not contact:
                    corr = Vector((0.0, 0.0, 0.0))
                prev = (cur, None, contact)
                if corr.length > 1e-4:
                    target = Mf.translation + corr
                    Rf = M[foot].to_3x3().normalized()
                    solve_leg(ctx, pose, M, side, target, 0.0, 0.0, 1.0, pole=_knee_pole(sk, M, side), soft=0.0, rot=Rf)
                    sk.update_subtree(pose, foot, M)
        # pavimento: tallone e pianta mai sotto z = 0
        for fr in out:
            pose = fr['pose']
            M = sk.fk(pose)
            for side in 'LR':
                Mf = M['foot.' + side]
                Rinv = ctx.foot_rest[side].inverted()
                heel = Mf @ (Rinv @ ctx.heel_off)
                ball = Mf @ (Rinv @ ctx.ball_off)
                low = min(heel.z, ball.z)
                if low < -0.004:
                    target = Mf.translation + Vector((0, 0, -low))
                    Rf = M['foot.' + side].to_3x3().normalized()
                    solve_leg(ctx, pose, M, side, target, 0.0, 0.0, 1.0, pole=_knee_pole(sk, M, side), soft=0.0, rot=Rf)

    # --------------------------------------------------------------- molle del ciuffo
    def springs(self, out, freq=3.6, zeta=0.22):
        ctx = self.ctx; sk = ctx.sk
        names = ['curl.%02d' % (k + 1) for k in range(C.CURL['bones'])]
        K = (2 * math.pi * freq) ** 2; Cd = 2 * zeta * math.sqrt(K)
        dt = 1.0 / self.fps
        Rh0 = sk.rest['head'].to_3x3()
        axes = {}
        for nme in names:
            Rb = sk.rest[nme].to_3x3()
            axes[nme] = (Rb.inverted() @ Rh0 @ Vector((1, 0, 0)), Rb.inverted() @ Rh0 @ Vector((0, 0, 1)))
        th = ph = vth = vph = 0.0
        prev = []
        for fr in out:
            pose = fr['pose']
            M = sk.fk(pose)
            Hw = M['head']
            tip = Hw @ Vector((0, sk.length['head'] * 1.15, 0))
            prev.append(tip)
            if len(prev) >= 3:
                acc = (prev[-1] - 2 * prev[-2] + prev[-3]) / (dt * dt)
            else:
                acc = Vector((0, 0, 0))
            acc = acc + Vector((0, 0, 9.81))
            al = Hw.to_3x3().normalized().inverted() @ acc     # spazio della testa: X lato, Y su, Z avanti
            # sub-passi per stabilita'
            for _ in range(4):
                h = dt / 4
                a_th = -K * th - Cd * vth - K * 0.02 * al.z
                a_ph = -K * ph - Cd * vph + K * 0.02 * al.x
                vth += a_th * h; vph += a_ph * h
                th += vth * h; ph += vph * h
            th = max(-0.7, min(0.7, th)); ph = max(-0.7, min(0.7, ph))
            for i, nme in enumerate(names):
                f = 0.10 + 0.05 * i
                ax_x, ax_z = axes[nme]
                q = Quaternion(ax_x, th * f) @ Quaternion(ax_z, ph * f)
                bp = pose.setdefault(nme, BonePose())
                bp.rot = q @ bp.rot

    # --------------------------------------------------------------- oggetti
    def object_track(self, out, name, obj, hand_side='R', start_world=None):
        """calcola le posizioni di un oggetto preso con «grab» e lasciato con «release» (lancio balistico se c'e' target)."""
        sk = self.ctx.sk
        state = 'free'; off = None; pos = start_world.copy() if start_world else obj.matrix_world.translation.copy()
        rot = obj.matrix_world.to_quaternion()
        vel = Vector((0, 0, 0)); track = []
        rest_z = pos.z
        root = Matrix.Identity(4)
        for fr in out:
            pose = fr['pose']
            M = sk.fk(pose)
            for (c, (ev, data)) in fr['events']:
                if ev == 'grab' and data.get('object', name) == name and state != 'held':
                    sides = ('L', 'R') if data.get('side') == 'both' else (data.get('side', hand_side),)
                    hm = self._hands_mid(root, M, sides)
                    off = (hm.inverted() @ Matrix.Translation(pos) @ rot.to_matrix().to_4x4())
                    state = 'held'; held_sides = sides
                elif ev == 'release' and state == 'held':
                    state = 'flying' if data.get('target') else 'free'
                    tgt = data.get('target')
                    if tgt is not None:
                        Tw = c.origin @ Vector(tgt)
                        Tw.z = max(Tw.z, rest_z)          # il bersaglio e' dove la palla tocca terra la prima volta
                        dist = (Tw - pos).length
                        T = max(0.35, min(1.1, dist / 3.0))
                        vel = (Tw - pos) / T + Vector((0, 0, 0.5 * 9.81 * T))
                    else:
                        vel = Vector((0, 0, 0))
            if state == 'held':
                hm = self._hands_mid(root, M, held_sides)
                W = hm @ off
                pos = W.translation.copy(); rot = W.to_quaternion()
            elif state == 'flying':
                dt = 1.0 / self.fps
                vel.z -= 9.81 * dt
                pos = pos + vel * dt
                if pos.z <= rest_z and vel.z < 0:
                    pos.z = rest_z
                    vel = Vector((vel.x * 0.5, vel.y * 0.5, -vel.z * 0.35))
                    if abs(vel.z) < 0.4:
                        vel = Vector((0, 0, 0)); state = 'free'
            track.append((pos.copy(), rot.copy()))
        return track

    def _hands_mid(self, root, M, sides):
        sk = self.ctx.sk
        mats = [root @ M['hand.' + s] @ Matrix.Translation((0, sk.length['hand.' + s] * 0.45, 0)) for s in sides]
        if len(mats) == 1:
            return mats[0]
        p = (mats[0].translation + mats[1].translation) * 0.5
        R = (root @ M['chest']).to_3x3().normalized()
        Mx = R.to_4x4(); Mx.translation = p
        return Mx


# ------------------------------------------------------------------ scrittura nell'Action di Blender
def _channelbag(action, slot):
    layer = action.layers[0] if action.layers else action.layers.new('Layer')
    strip = layer.strips[0] if layer.strips else layer.strips.new(type='KEYFRAME')
    return strip.channelbag(slot, ensure=True)


def write_action(rig, out, name, fps=C.FPS, frame_start=1):
    import bpy
    act = bpy.data.actions.get(name)
    if act:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    slot = act.slots.new(id_type='OBJECT', name=rig.name)
    cb = _channelbag(act, slot)
    n = len(out)
    frames = [frame_start + i for i in range(n)]
    bones = set()
    for fr in out:
        bones |= set(fr['pose'].keys())
    bones = [b for b in bones if b in rig.pose.bones]

    def fcurve(path, idx, vals, group):
        fc = cb.fcurves.new(path, index=idx)
        try:
            fc.group = cb.groups.get(group) or cb.groups.new(group)
        except Exception:
            pass
        fc.keyframe_points.add(n)
        co = []
        for fno, v in zip(frames, vals):
            co += [fno, v]
        fc.keyframe_points.foreach_set('co', co)
        fc.keyframe_points.foreach_set('interpolation', [bpy.types.Keyframe.bl_rna.properties['interpolation'].enum_items['LINEAR'].value] * n)
        fc.update()
        return fc

    for b in bones:
        qs = []
        prev = None
        locs = []; scls = []
        for fr in out:
            bp = fr['pose'].get(b)
            q = bp.rot.copy() if bp else Quaternion()
            if prev is not None and prev.dot(q) < 0:
                q = -q
            prev = q
            qs.append(q)
            locs.append(bp.loc if bp else Vector((0, 0, 0)))
            scls.append(bp.scl if bp else Vector((1, 1, 1)))
        path = 'pose.bones["%s"]' % b
        for i in range(4):
            fcurve(path + '.rotation_quaternion', i, [q[i] for q in qs], b)
        if any(v.length > 1e-7 for v in locs):
            for i in range(3):
                fcurve(path + '.location', i, [v[i] for v in locs], b)
        if any((v - Vector((1, 1, 1))).length > 1e-7 for v in scls):
            for i in range(3):
                fcurve(path + '.scale', i, [v[i] for v in scls], b)
    for k in C.FACE_PROPS:
        fc = cb.fcurves.new('pose.bones["face"]["%s"]' % k)
        fc.keyframe_points.add(n)
        co = []
        for fno, fr in zip(frames, out):
            co += [fno, fr['props'][k]]
        fc.keyframe_points.foreach_set('co', co)
        fc.update()
    rig.animation_data_create()
    rig.animation_data.action = act
    rig.animation_data.action_slot = slot
    return act


def write_object_action(obj, track, name, frame_start=1):
    import bpy
    act = bpy.data.actions.new(name)
    slot = act.slots.new(id_type='OBJECT', name=obj.name)
    cb = _channelbag(act, slot)
    n = len(track)
    obj.rotation_mode = 'QUATERNION'
    for path, size, get in (('location', 3, lambda p, r: p), ('rotation_quaternion', 4, lambda p, r: r)):
        for i in range(size):
            fc = cb.fcurves.new(path, index=i)
            fc.keyframe_points.add(n)
            co = []
            for f, (p, r) in enumerate(track):
                co += [frame_start + f, get(p, r)[i]]
            fc.keyframe_points.foreach_set('co', co)
            fc.update()
    obj.animation_data_create(); obj.animation_data.action = act; obj.animation_data.action_slot = slot
    return act
