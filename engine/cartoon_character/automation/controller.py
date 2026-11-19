"""API per comandare il personaggio da Python.

    from cartoon_character.automation.controller import Character
    ch = Character('Ciuffo', 'default', location=(0, 0), facing=0)
    ch.play('walk', duration=2.0)
    ch.play('surprise')
    ch.set_expression('happy')                 # durante l'ultima clip (e oltre, finche' non cambia)
    ch.look_at('camera')
    ch.play('fall'); ch.play('stand_up')       # da terra diventa «get_up» da solo
    ch.walk_to((1.0, -0.5))
    ch.say('Ciao! Oggi parliamo di scienza', duration=2.0)
    ch.play_file('assets/animations/cmu/02_01.bvh')   # mocap BVH/FBX trasferito sul personaggio
    ch.bake()                                  # scrive l'animazione nel rig (Action), pronta per il render

Tutti i nomi accettano anche gli alias italiani di config.ALIASES (cammina, corri, salta, felice, triste, ...).
"""
import math
import bpy
from mathutils import Vector, Matrix

from .. import config as C
from ..character.builder import build
from ..character.skeleton import Skeleton
from ..animation.clip import RigInfo
from ..animation import motion_library as ML
from ..animation import procedural as P
from ..animation import face as FACE
from ..animation.blending import Timeline, write_action, write_object_action, root_matrix

INF = 1e9

VOWELS = {'a': 'open', 'à': 'open', 'e': 'E', 'è': 'E', 'é': 'E', 'i': 'E', 'ì': 'E', 'o': 'O', 'ò': 'O', 'u': 'U', 'ù': 'U'}
LABIALS = set('mbp')


def world_position(obj):
    """posizione nel mondo di un oggetto Blender, aggiornando la scena se e' stato appena spostato o creato."""
    bpy.context.view_layer.update()
    return obj.matrix_world.translation.copy()


class Character:
    def __init__(self, name=C.NAME, variant='default', location=(0.0, 0.0), facing=0.0, collection=None):
        self.name = name
        self.h = build(name, variant, collection)
        self.rig = self.h['rig']
        self.sk = Skeleton.from_armature(self.rig)
        self.ctx = RigInfo(self.sk, self.h['curl_poses'])
        self.tl = Timeline(self.ctx, seed=sum(ord(c) for c in name))
        self.tl.origin = Matrix.Translation((location[0], location[1], 0.0)) @ Matrix.Rotation(math.radians(facing), 4, 'Z')
        self.props = {}
        self.log = []

    # ---------------------------------------------------------------- corpo
    @property
    def now(self):
        return self.tl.cursor

    @property
    def state(self):
        return self.tl.state

    def _last_start(self):
        return self.tl.clips[-1].start if self.tl.clips else 0.0

    def play(self, name, duration=None, loops=None, blend=0.25, speed=1.0, **params):
        """aggiunge un movimento in coda. duration in secondi (per i cicli), loops = numero di ripetizioni."""
        name = C.ALIASES.get(name, name)
        # stati: da terra o dalla sedia ci si alza prima di fare altro
        if name == 'stand_up' and self.state == 'floor':
            name = 'get_up'
        if self.state in ('floor', 'chair') and name not in ('stand_up', 'get_up', 'idle'):
            self.play('get_up' if self.state == 'floor' else 'stand_up')
        if self.state == 'holding' and name not in ('throw', 'idle', 'walk', 'turn'):
            pass
        # parametri nel mondo -> spazio della clip
        local = dict(params)
        for key in ('target', 'obj', 'box'):
            if key in local and local[key] is not None:
                p = local[key]
                if hasattr(p, 'matrix_world'):
                    p = world_position(p)
                elif isinstance(p, Character):
                    p = p.head_position()
                local[key] = tuple(self.tl.world_to_next_local(p))
        if name == 'stop':
            prev = self.tl.clips[-1] if self.tl.clips else None
            if prev is not None and getattr(prev.motion, 'kind', '') == 'gait':
                self.tl.snap_gait(prev)
                m = P.make_stop(prev.motion.name if prev.motion.name in P.GAITS else 'walk', prev.motion.speed)
                c = self.tl.add(m, blend=0.08, auto=False)
                self.log.append(('stop', c.start, c.end))
                return self
            name = 'idle'; duration = duration or 0.6
        m = ML.make(name, self.ctx, **local)
        d = duration
        if d is None and loops:
            d = loops * m.duration
        if d is None and getattr(m, 'loop', False):
            d = 2 * m.duration if m.duration < 1.5 else m.duration
        c = self.tl.add(m, d, blend, params=local, speed=speed)
        self.log.append((name, c.start, c.end))
        return self

    def play_file(self, path, blend=0.3, frames=None, **kw):
        """aggiunge un'animazione da file BVH o FBX (mocap CMU, Mixamo, Rokoko...) trasferita sul personaggio.
        kw: in_place, skip_tpose, hands, clearance (vedi animation/retarget.py)."""
        from ..animation import retarget as RT
        clip, mapping = RT.load(path, self.ctx, frames=frames, **kw)
        c = self.tl.add(clip, clip.duration, blend)
        self.log.append((clip.name, c.start, c.end))
        return self

    def wait(self, seconds=1.0, blend=0.3):
        return self.play('idle', duration=seconds, blend=blend)

    def turn(self, angle):
        return self.play('turn', angle=angle)

    def walk_to(self, target, gait='walk', stop=True, blend=0.25):
        """cammina fino al punto (x, y) del mondo: si gira se serve, cammina e si ferma esattamente li'."""
        origin = self.tl.next_origin()
        p = Vector((target[0], target[1], 0.0))
        loc = origin.inverted() @ p
        ang = math.degrees(math.atan2(loc.x, -loc.y))
        if abs(ang) > 15:
            self.play('turn', angle=ang)
            origin = self.tl.next_origin()
            loc = origin.inverted() @ p
        dist = max(0.0, -loc.y)
        if dist < 0.06:                                    # gia' arrivato: niente passi
            return self
        g = P.GAITS[gait]; T = g['cycle']
        # il ciclo parte dalla fase duty/2 e snap_gait lo chiude a (k - duty/2) cicli; la frenata percorre v*duty*T/2:
        # in totale v*k*T, con o senza frenata. Quindi k cicli interi alla velocita' che fa arrivare esattamente al punto.
        k = max(1, round(dist / (g['speed'] * T)))
        v = dist / (k * T)
        m = P.Gait(gait, speed=v)
        c = self.tl.add(m, k * T, blend)
        self.log.append((gait, c.start, c.end))
        if stop:
            self.tl.snap_gait(c)
            c2 = self.tl.add(P.make_stop(gait, v), blend=0.08, auto=False)
            self.log.append(('stop', c2.start, c2.end))
        return self

    # ---------------------------------------------------------------- interazioni con oggetti
    def pick_up(self, obj, size=None):
        name = obj.name
        start = world_position(obj)
        size = size or max(obj.dimensions) / 2
        self.props[name] = dict(obj=obj, start=start)
        return self.play('pick_up', obj=obj, size=size)

    def throw(self, target):
        return self.play('throw', target=target)

    def push(self, box, size=None):
        self.props[box.name] = dict(obj=box, start=world_position(box), slide=True)
        return self.play('push', box=box, size=size or tuple(box.dimensions))

    def pull(self, box, size=None):
        self.props[box.name] = dict(obj=box, start=world_position(box), slide=True)
        return self.play('pull', box=box, size=size or tuple(box.dimensions))

    def sit(self, height=ML.CHAIR_H):
        return self.play('sit', height=height)

    def point(self, target):
        return self.play('point', target=target)

    def wave(self):
        return self.play('wave')

    # ---------------------------------------------------------------- viso e sguardo
    def set_expression(self, name, at=None, duration=None, intensity=1.0, fade=0.2):
        """espressione dal tempo `at` (predefinito: inizio dell'ultima clip) per `duration` secondi (predefinito: sempre)."""
        ch = FACE.expression(name, intensity) if isinstance(name, str) else name
        s = self._last_start() if at is None else at
        e = INF if duration is None else s + duration
        # un'espressione «per sempre» finisce dove ne comincia un'altra
        for i, ex in enumerate(self.tl.expressions):
            if ex[1] >= INF and ex[0] < s:
                self.tl.expressions[i] = (ex[0], s, ex[2], ex[3], fade, ex[5])
        self.tl.expression(ch, s, e, fade, fade, 1.0)
        return self

    def look_at(self, target, at=None, duration=None, fade=0.3):
        s = self._last_start() if at is None else at
        e = INF if duration is None else s + duration
        for i, lk in enumerate(self.tl.looks):
            if lk[1] >= INF and lk[0] < s:
                self.tl.looks[i] = (lk[0], s, lk[2], lk[3], fade)
        self.tl.look_at(self._resolve_target(target), s, e, fade, fade)
        return self

    def look_forward(self, at=None):
        s = self._last_start() if at is None else at
        for i, lk in enumerate(self.tl.looks):
            if lk[1] >= INF and lk[0] < s:
                self.tl.looks[i] = (lk[0], s, lk[2], lk[3], lk[4])
        return self

    def _resolve_target(self, target):
        if isinstance(target, str) and target == 'camera':
            def cam(t):
                sc = bpy.context.scene
                cam_ob = sc.camera
                if cam_ob is None:
                    return Vector((0, -3, 0.8))
                f = sc.frame_current
                sc.frame_set(int(round(t * self.tl.fps)) + 1)
                p = cam_ob.matrix_world.translation.copy()
                sc.frame_set(f)
                return p
            # la camera di solito e' ferma: un campione basta (veloce)
            cam_ob = bpy.context.scene.camera
            if cam_ob is not None and not (cam_ob.animation_data and cam_ob.animation_data.action):
                return cam_ob.matrix_world.translation.copy()
            return cam
        if isinstance(target, Character):
            other = target
            return lambda t: other.head_position(t)
        return target

    def head_position(self, t=None):
        if t is None:
            M = self.tl.next_origin()
        else:
            pose, _, _, _ = self.tl.body(t)
            M = root_matrix(pose['root'])
        return M @ Vector((0.0, -0.05, C.HEAD_C[2] - 0.02))

    def say(self, text, at=None, duration=None, words=None, strength=1.0):
        """labiale semplice dal testo (vocali -> forme della bocca). words = [(parola, inizio, fine), ...] dai tempi di Whisper."""
        s = self._last_start() if at is None else at
        items = words or [(w, None, None) for w in text.split()]
        if words is None:
            dur = duration or max(0.6, 0.075 * len(text))
            letters = sum(len(w) for w, _, _ in items) + len(items)
            t = s
            per = dur / max(1, letters)
            timed = []
            for w, _, _ in items:
                timed.append((w, t, t + per * len(w)))
                t += per * (len(w) + 1)
            items = timed
        for (w, a, b) in items:
            chars = [ch for ch in w.lower() if ch.isalpha()]
            if not chars:
                continue
            step = (b - a) / len(chars)
            for i, ch in enumerate(chars):
                tc = a + step * (i + 0.5)
                if ch in VOWELS:
                    self.tl.visemes.append((tc, VOWELS[ch], 0.85 * strength, max(0.10, step * 1.6)))
                elif ch in LABIALS:
                    self.tl.visemes.append((tc, 'M', 0.9 * strength, max(0.07, step * 1.2)))
                elif ch in 'fv':
                    self.tl.visemes.append((tc, 'E', 0.4 * strength, max(0.07, step * 1.2)))
        return self

    # ---------------------------------------------------------------- cottura
    def bake(self, frame_start=1, end_hold=0.0):
        n = int(math.ceil((self.tl.length + end_hold) * self.tl.fps)) + 1
        out = self.tl.evaluate_all(n)
        write_action(self.rig, out, self.name + '_anim', self.tl.fps, frame_start)
        for nm, pr in self.props.items():
            track = self.tl.object_track(out, nm, pr['obj'], start_world=pr['start'])
            if pr.get('slide'):
                z0 = pr['start'].z
                track = [(Vector((p.x, p.y, z0)), pr['obj'].matrix_world.to_quaternion()) for p, r in track]
            write_object_action(pr['obj'], track, nm + '_anim', frame_start)
        self.frames = n
        return out

