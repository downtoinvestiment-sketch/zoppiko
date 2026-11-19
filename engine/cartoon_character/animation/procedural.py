"""Locomozione procedurale: camminata, corsa, scatto (cicli analitici) e passi pianificati (girarsi, fermarsi).

Il piede appoggiato resta fermo nello spazio della clip per costruzione: il bacino avanza con la velocita' della clip e
il piede a terra arretra rispetto al bacino esattamente della stessa quantita'. Tallone-pianta-punta: il piede atterra sul
tallone, si appiattisce e si stacca ruotando sulla pianta (le dita restano a terra).
"""
import math
from mathutils import Vector, Matrix, Quaternion

from .. import config as C
from ..character.skeleton import BonePose, euler_q, mirror_euler
from .clip import Frame, solve_leg, hips_local, HAND_SHAPES, _expand, propagate_squash, reach_fix


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def smoother(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


def _rot_lat(alpha_deg, yaw_deg):
    """rotazione del piede attorno al suo asse laterale (alpha > 0 = punta in su)."""
    lat = Matrix.Rotation(math.radians(yaw_deg), 3, 'Z') @ Vector((-1.0, 0.0, 0.0))
    return Matrix.Rotation(math.radians(alpha_deg), 3, lat)


def ankle_from_pivot(ctx, plant, yaw, alpha):
    """posizione della caviglia per un piede con pianta in `plant` (punto a terra sotto la caviglia a piede piatto)."""
    Rz = Matrix.Rotation(math.radians(yaw), 3, 'Z')
    heel = Rz @ ctx.heel_off; ball = Rz @ ctx.ball_off
    flat_ankle = Vector((plant.x, plant.y, ctx.ankle_h))
    if alpha > 0:
        P = flat_ankle + heel
        return P - _rot_lat(alpha, yaw) @ heel
    if alpha < 0:
        P = flat_ankle + ball
        return P - _rot_lat(alpha, yaw) @ ball
    return flat_ankle


def _apply_spec(pose, spec):
    for b, v in _expand(spec).items():
        bp = pose.setdefault(b, BonePose())
        bp.rot = bp.rot @ euler_q(v)


GAITS = {
    #            velocita' m/s, ciclo s, appoggio, alzata piede, rimbalzo, inclinazione, braccia, gomito, ondeggio, torsione
    'walk':   dict(speed=0.48, cycle=0.84, duty=0.60, step_h=0.060, bob=0.014, lean=4.0, arm=24.0, elbow=16.0, sway=0.012,
                   twist=7.0, drop=4.0, heel=14.0, toe=22.0, base_drop=0.022, bounce=0.03, run=False),
    'run':    dict(speed=1.20, cycle=0.56, duty=0.38, step_h=0.110, bob=0.024, lean=12.0, arm=48.0, elbow=78.0, sway=0.008,
                   twist=10.0, drop=3.0, heel=10.0, toe=28.0, base_drop=0.040, bounce=0.06, run=True),
    'sprint': dict(speed=1.95, cycle=0.46, duty=0.33, step_h=0.140, bob=0.022, lean=22.0, arm=55.0, elbow=80.0, sway=0.006,
                   twist=12.0, drop=2.0, heel=6.0, toe=34.0, base_drop=0.050, bounce=0.07, run=True),
}


class Gait:
    kind = 'gait'
    category = 'locomotion'
    loop = True
    start_state = 'stand'
    end_state = 'stand'

    def __init__(self, name, phase=None, **over):
        p = dict(GAITS[name]); p.update(over)
        self.name = name; self.p = p
        # fase iniziale: di base parte con il piede sinistro a meta' appoggio (sotto il bacino, vicino alla posizione da fermo)
        self.phase = p['duty'] / 2 if phase is None else phase
        self.cycle = p['cycle']; self.duration = p['cycle']
        self.speed = p['speed']
        self.events = []
        self.description = {'walk': 'camminata a passo allegro', 'run': 'corsa con fase di volo', 'sprint': 'scatto cartoon'}.get(name, '')

    # posizione del piede di un lato al tempo t
    def foot_state(self, ctx, side, t):
        p = self.p; T = self.cycle; v = self.speed; duty = p['duty']
        t = t + self.phase * T
        off = 0.0 if side == 'L' else 0.5
        u = t / T + off
        k = math.floor(u); ph = u - k
        x = ctx.ankle[side].x * 0.94
        yaw = 4.0 if side == 'L' else -4.0
        def plant_y(kk):
            tk = (kk - off) * T
            return -v * (tk + duty * T / 2) + v * self.phase * T

        def stance(kk, pr):
            if pr < 0.15:
                a = p['heel'] * (1 - smooth(pr / 0.15))
            elif pr > 0.62:
                a = -p['toe'] * ((pr - 0.62) / 0.38) ** 1.4
            else:
                a = 0.0
            plant = Vector((x, plant_y(kk), 0.0))
            return ankle_from_pivot(ctx, plant, yaw, a), a
        if ph < duty:
            A, a = stance(k, ph / duty)
            toe = -a if a < 0 else 0.0
            return A, a, toe, True, yaw
        s = (ph - duty) / (1 - duty)
        A0, a0 = stance(k, 1.0)
        A1, a1 = stance(k + 1, 0.0)
        e = smoother(s)
        A = A0.lerp(A1, e)
        lift = math.sin(math.pi * s) ** (0.8 if p['run'] else 1.1)
        A.z += p['step_h'] * lift
        if p['run']:                                   # tallone verso il sedere nella corsa
            A.y += 0.05 * math.sin(math.pi * min(1.0, s * 1.6)) * (1 - s)
        a = a0 + (a1 - a0) * smooth(s * 1.15)
        toe = (p['toe'] * 0.6) * (1 - smooth(s * 2.2))
        return A, a, toe, False, yaw

    def evaluate(self, t, ctx, params=None, t_prev=None):
        p = self.p; T = self.cycle; v = self.speed; duty = p['duty']
        sk = ctx.sk
        ph = t / T + self.phase
        pose = {'root': BonePose(loc=(0.0, -v * t, 0.0))}
        w2 = 2 * math.pi * (ph - duty / 2)            # 0 a meta' appoggio sinistro
        bob = math.cos(2 * w2)
        if p['run']:
            bob = -bob
        hz = -p['base_drop'] + p['bob'] * bob
        hx = p['sway'] * math.cos(w2)
        pose['hips'] = BonePose(loc=hips_local((hx, 0.0, hz)),
                                rot=euler_q((p['lean'] * 0.5, -p['twist'] * math.cos(2 * math.pi * ph), p['drop'] * math.cos(w2))))
        # squash leggero all'appoggio (cartoon)
        sq = 1.0 - p['bounce'] * max(0.0, -math.cos(2 * w2)) * 0.5
        pose['spine'] = BonePose(rot=euler_q((p['lean'] * 0.3, p['twist'] * 0.5 * math.cos(2 * math.pi * ph), 0.0)),
                                 scl=(1.0 / math.sqrt(sq), sq, 1.0 / math.sqrt(sq)))
        pose['chest'] = BonePose(rot=euler_q((p['lean'] * 0.3, p['twist'] * 1.1 * math.cos(2 * math.pi * ph),
                                              -p['drop'] * 0.6 * math.cos(w2))))
        # testa stabile: compensa le rotazioni del busto, con un piccolo ritardo
        lag = 2 * math.pi * 0.06
        pose['neck'] = BonePose(rot=euler_q((-p['lean'] * 0.4, -p['twist'] * 0.6 * math.cos(2 * math.pi * ph - lag), 0.0)))
        pose['head'] = BonePose(rot=euler_q((-p['lean'] * 0.5 + 2.0 * math.cos(2 * w2 - lag), -p['twist'] * 0.4 * math.cos(2 * math.pi * ph - lag),
                                             -p['drop'] * 0.3 * math.cos(w2 - lag))))
        # braccia opposte alle gambe, con ritardo (follow-through)
        alag = 0.05
        for s in ('L', 'R'):
            phase = 2 * math.pi * (ph - alag - (0.5 if s == 'L' else 0.0))
            sw = p['arm'] * math.cos(phase)
            el = p['elbow'] + (p['elbow'] * 0.35 + 6) * max(0.0, math.cos(phase))
            spec = {'upper_arm': (sw + 4.0, 0.0, -20.0 - (8.0 if p['run'] else 0.0)), 'forearm': (el, 0.0, 0.0),
                    'hand': (6.0 * math.cos(phase - 0.6), 0.0, 0.0), 'shoulder': (0.0, 0.0, -2.0 + 2.0 * math.cos(phase))}
            for b, val in _expand({k + '.' + s: (val if s == 'L' else val) for k, val in spec.items()}).items():
                pose[b] = BonePose(rot=euler_q(val))
            shape = 'fist' if self.name == 'sprint' else ('grab' if p['run'] else 'relax')
            for k, val in HAND_SHAPES[shape].items():
                vv = val if s == 'L' else mirror_euler(val)
                pose['%s.%s' % (k, s)] = BonePose(rot=euler_q(vv))
        propagate_squash(pose)
        frame = Frame(pose)
        mats = sk.fk(pose)
        states = {s: self.foot_state(ctx, s, t) for s in ('L', 'R')}
        reach_fix(ctx, pose, mats, {s: st[0] for s, st in states.items()})
        for s in ('L', 'R'):
            A, a, toe, planted, yaw = states[s]
            solve_leg(ctx, pose, mats, s, A, yaw, a)
            pose['toe.' + s] = BonePose(rot=euler_q((toe, 0.0, 0.0)))
            frame.contacts[s] = planted
        return frame


# ------------------------------------------------------------------ passi pianificati
class Footsteps:
    """piani di passi: per ogni lato, appoggi (tempo di arrivo, punto, yaw) e sollevamenti."""

    def __init__(self, ctx, init):
        self.ctx = ctx
        self.steps = {s: [] for s in 'LR'}
        self.init = init          # s -> (Vector plant xy, yaw)

    def step(self, side, lift, land, plant, yaw, height=0.05):
        self.steps[side].append((lift, land, Vector(plant), yaw, height))
        self.steps[side].sort(key=lambda x: x[0])

    def state(self, side, t):
        cur, cyaw = self.init[side]
        for (lift, land, plant, yaw, h) in self.steps[side]:
            if t < lift:
                break
            if t < land:
                s = (t - lift) / (land - lift)
                e = smoother(s)
                P = cur.lerp(plant, e)
                yy = cyaw + (yaw - cyaw) * e
                alpha = -14.0 * math.sin(math.pi * min(1.0, s * 1.4)) * (1 - s) + 8.0 * math.sin(math.pi * max(0.0, (s - 0.55) / 0.45)) * (s > 0.55)
                A = Vector((P.x, P.y, self.ctx.ankle_h)) + Vector((0, 0, h * math.sin(math.pi * s)))
                return A, yy, alpha, False
            cur, cyaw = plant, yaw
        return Vector((cur.x, cur.y, self.ctx.ankle_h)), cyaw, 0.0, True


def home_plant(ctx, side, root_xy=(0.0, 0.0), yaw=0.0, spread=0.0):
    a = ctx.ankle[side]
    local = Vector((a.x + (spread if side == 'L' else -spread), a.y, 0.0))
    p = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ local
    return Vector((root_xy[0] + p.x, root_xy[1] + p.y, 0.0))


class PlannedSteps:
    """clip generica fatta di passi pianificati + traccia del bacino + pose del busto (funzione di t)."""
    kind = 'steps'
    loop = False
    start_state = 'stand'
    end_state = 'stand'

    def __init__(self, name, duration, category, plan_fn, body_fn, root_fn, description=''):
        self.name = name; self.duration = duration; self.category = category
        self.plan_fn = plan_fn; self.body_fn = body_fn; self.root_fn = root_fn
        self.description = description
        self.events = []
        self._plan = None

    def evaluate(self, t, ctx, params=None, t_prev=None):
        params = params or {}
        if self._plan is None or self._plan[0] is not ctx or self._plan[2] != repr(sorted(params.items())):
            self._plan = (ctx, self.plan_fn(ctx, params), repr(sorted(params.items())))
        plan = self._plan[1]
        pose = {}
        rx, ry, ryaw = self.root_fn(t, params)
        pose['root'] = BonePose(loc=(rx, ry, 0.0), rot=Quaternion((0, 0, 1), math.radians(ryaw)))
        self.body_fn(t, pose, params)
        frame = Frame(pose)
        mats = ctx.sk.fk(pose)
        reach_fix(ctx, pose, mats, {s: plan.state(s, t)[0] for s in ('L', 'R')})
        for s in ('L', 'R'):
            A, yaw, alpha, planted = plan.state(s, t)
            if alpha:
                plant = Vector((A.x, A.y, 0.0))
                A2 = ankle_from_pivot(ctx, plant, yaw, alpha)
                A = Vector((A2.x, A2.y, A.z + (A2.z - ctx.ankle_h)))
            solve_leg(ctx, pose, mats, s, A, yaw, alpha)
            frame.contacts[s] = planted
        return frame


def make_turn(angle=90.0, duration=None):
    D = duration or (0.9 + 0.5 * abs(angle) / 180.0)
    lead = 'L' if angle > 0 else 'R'
    other = 'R' if lead == 'L' else 'L'

    def yaw_at(t):
        return angle * smoother(t / D)

    def plan(ctx, params):
        fs = Footsteps(ctx, {s: (home_plant(ctx, s), 0.0) for s in 'LR'})
        # l'ultimo passo di ogni piede arriva all'angolo finale (alla fine i piedi sono affiancati e girati)
        if abs(angle) > 45:
            seq = [(lead, 0.5), (other, 1.0), (lead, 1.0)]
        else:
            seq = [(lead, 1.0), (other, 1.0)]
        n = len(seq)
        for i, (s, frac) in enumerate(seq):
            lift = D * (0.04 + 0.80 * i / n)
            land = lift + D * (0.80 / n + 0.06)
            ty = angle * frac
            fs.step(s, lift, land, home_plant(ctx, s, (0, 0), ty), ty, 0.045)
        return fs

    def body(t, pose, params):
        x = t / D
        lead_head = math.sin(math.pi * min(1.0, x * 1.3)) * 0.22 * angle
        dip = -0.012 * math.sin(math.pi * x)
        pose['hips'] = BonePose(loc=hips_local((0, 0, -0.012 + dip)), rot=euler_q((2.0, 0.08 * angle * math.sin(math.pi * x), 0)))
        pose['chest'] = BonePose(rot=euler_q((0, 0.12 * angle * math.sin(math.pi * x), 0)))
        pose['head'] = BonePose(rot=euler_q((0, lead_head * 0.6, 0)))
        pose['neck'] = BonePose(rot=euler_q((0, lead_head * 0.4, 0)))
        _apply_spec(pose, {'upper_arm': (6.0, 0, -22.0), 'forearm': (16.0, 0, 0)})
        for k, val in HAND_SHAPES['relax'].items():
            pose[k + '.L'] = BonePose(rot=euler_q(val)); pose[k + '.R'] = BonePose(rot=euler_q(mirror_euler(val)))

    def root(t, params):
        return 0.0, 0.0, yaw_at(t)

    m = PlannedSteps('turn', D, 'locomotion', plan, body, root, 'si gira sul posto con passi veri (%+d gradi)' % angle)
    m.params = dict(angle=angle)
    return m


def make_stop(gait='walk', speed=None):
    g = GAITS[gait]
    v = speed or g['speed']; T = g['cycle']; duty = g['duty']
    yL = -v * (duty * T / 2)
    yR = v * (0.5 * T - duty * T / 2)
    Ddec = 2 * abs(yL) / v
    D = Ddec + 0.75

    def plan(ctx, params):
        aL = ctx.ankle['L']; aR = ctx.ankle['R']
        fs = Footsteps(ctx, {'L': (Vector((aL.x * 0.94, yL, 0)), 4.0), 'R': (Vector((aR.x * 0.94, yR, 0)), -4.0)})
        if g['run']:
            # nella corsa il piede destro e' in aria alla fase 0: il passo e' gia' cominciato (stacco nel passato)
            lift = -(0.5 - duty) * T
            fs.step('R', lift, 0.22, Vector((aR.x, yL + 0.004, 0)), 0.0, g['step_h'] * 0.9)
            fs.step('L', 0.30, 0.48, Vector((aL.x, yL + 0.004, 0)), 0.0, 0.015)
        else:
            fs.step('R', 0.02, 0.40, Vector((aR.x, yL + 0.004, 0)), 0.0, 0.05)
            fs.step('L', 0.46, 0.66, Vector((aL.x, yL + 0.004, 0)), 0.0, 0.012)
        return fs

    def root(t, params):
        if t < Ddec:
            y = -v * (t - t * t / (2 * Ddec))
        else:
            y = -v * Ddec / 2
        return 0.0, y, 0.0

    def body(t, pose, params):
        # il busto continua in avanti e torna (follow-through), le braccia oscillano e si fermano
        x = t
        lean = 6.0 * math.exp(-((x - Ddec) / 0.16) ** 2) - 2.5 * math.exp(-((x - Ddec - 0.28) / 0.14) ** 2)
        lean += g['lean'] * max(0.0, 1 - t / Ddec)
        drop = -g['base_drop'] * max(0.0, 1 - t / (Ddec + 0.2)) - 0.012 * math.exp(-((x - Ddec - 0.05) / 0.12) ** 2)
        pose['hips'] = BonePose(loc=hips_local((0, 0, drop)), rot=euler_q((lean * 0.4, 0, 0)))
        pose['spine'] = BonePose(rot=euler_q((lean * 0.35, 0, 0)))
        pose['chest'] = BonePose(rot=euler_q((lean * 0.35, 0, 0)))
        pose['head'] = BonePose(rot=euler_q((-lean * 0.5 + 3 * math.exp(-((x - Ddec - 0.12) / 0.12) ** 2), 0, 0)))
        amp = g['arm'] * 0.95
        sw = amp * math.exp(-t / 0.35) * math.cos(2 * math.pi * t / 0.7)
        relax = math.exp(-t / 0.28)
        for s in ('L', 'R'):
            sg = -1.0 if s == 'L' else 1.0            # come il ciclo alla fase 0: sinistra indietro, destra avanti
            el = 16.0 + (g['elbow'] - 16.0 + (g['elbow'] * 0.35 + 6) * (1.0 if sg > 0 else 0.0) * 0.9) * relax
            spec = {'upper_arm.' + s: (6.0 + sg * sw, 0, -22.0 - (8.0 if g['run'] else 0.0) * relax), 'forearm.' + s: (el, 0, 0)}
            _apply_spec(pose, spec)
            start = 'fist' if gait == 'sprint' else ('grab' if g['run'] else 'relax')
            for k, val in HAND_SHAPES['relax'].items():
                v0 = HAND_SHAPES[start][k]
                vv = tuple(b + (a - b) * relax for a, b in zip(v0, val))
                pose['%s.%s' % (k, s)] = BonePose(rot=euler_q(vv if s == 'L' else mirror_euler(vv)))

    m = PlannedSteps('stop', D, 'locomotion', plan, body, root, 'frena dalla camminata e si ferma con un piccolo ondeggio')
    m.follows = gait
    return m
