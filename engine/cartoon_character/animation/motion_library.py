"""Libreria dei movimenti (30): locomozione, reazioni, comiche, interazioni.

Ogni movimento e' una funzione che riceve il contesto del personaggio (RigInfo) e i parametri, e restituisce una clip.
I movimenti iniziano e finiscono in uno «stato» (stand, floor, chair, holding): l'API usa gli stati per scegliere le varianti
(es. «stand_up» da terra diventa «get_up») e i test verificano che le posizioni iniziali e finali combacino.

Principi usati (Thomas & Johnston): anticipazione, azioni che si sovrappongono e seguono (il busto continua dopo l'arresto),
archi, rallentamenti in entrata e in uscita, squash & stretch sui salti e sugli impatti, tempi diversi per le parti del corpo,
esagerazione nelle reazioni. La fisica dei voli e' una parabola vera (g = 9,81 m/s2).
"""
import math
from mathutils import Vector, Matrix, Quaternion

from .. import config as C
from ..character.skeleton import euler_q
from .clip import Motion, HAND_SHAPES, Rel
from . import face as FACE
from . import procedural as P

G = 9.81

# posa in piedi di riferimento (valori «del lato sinistro»)
STAND = {
    'spine': (0, 0, 0), 'chest': (0, 0, 0), 'neck': (0, 0, 0), 'head': (0, 0, 0),
    'shoulder': (0, 0, 0), 'upper_arm': (6, 0, -22), 'forearm': (16, 0, 0), 'hand': (0, 0, 0),
    'toe': (0, 0, 0),
}
FLOOR_HIPS = (0.0, 0.13, -0.285)          # seduto per terra: fianchi indietro e in basso
CHAIR_H = 0.22


def floor_feet_y():
    return -0.18


def hand_orient(ctx, side, finger_dir, palm_dir):
    """rotazione (delta rispetto alla mano a riposo) che punta le dita verso finger_dir con il palmo verso palm_dir."""
    y = Vector(finger_dir).normalized()
    pn = Vector(palm_dir)
    pn = (pn - y * pn.dot(y)).normalized()
    x = pn if side == 'L' else -pn           # palmo = +X locale a sinistra, -X a destra
    z = x.cross(y).normalized()
    x = y.cross(z).normalized()
    R = Matrix((x, y, z)).transposed()
    return (R @ ctx.hand_rest[side].inverted()).to_quaternion()


def stand(m, t, ctx, mode='auto', y=0.0, face=None, hands=True, feet=True):
    m.pose(t, STAND, mode)
    m.hand_shape(t, 'both', 'relax', mode)
    m.hips(t, loc=(0, y, 0), rot=(0, 0, 0), scale=(1, 1, 1), mode=mode)
    for b in ('spine', 'chest', 'head'):
        m.scale(t, b, (1, 1, 1), mode)
    if feet:
        m.plant_feet(t, mode, y=y)
    if hands:
        for s in 'LR':
            m.hand(t, s, ctx.wrist[s], None, 0.0, mode)
    if face:
        m.face(t, face, 0.2)
    return m


def flight(m, ctx, t0, t1, z0, z1=0.0, y0=0.0, y1=0.0, tuck=0.06, n=10, feet_y=0.0, pitch_air=-18.0):
    """volo balistico dei fianchi da t0 a t1 (altezze relative), piedi raccolti sotto il corpo."""
    T = t1 - t0
    v0 = (z1 - z0 + 0.5 * G * T * T) / T
    for i in range(1, n):
        x = i / n
        t = t0 + T * x
        z = z0 + v0 * (t - t0) - 0.5 * G * (t - t0) ** 2
        y = y0 + (y1 - y0) * x
        m.hips(t, loc=(0, y, z), mode='linear')
        tk = tuck * math.sin(math.pi * x)
        for s in 'LR':
            a = ctx.ankle[s]
            m.foot(t, s, (a.x, a.y + y + feet_y + 0.03 * math.sin(math.pi * x), a.z + z + tk), 0.0, pitch_air * math.sin(math.pi * x), 1.0, 'linear')
    return v0


def on_toes(ctx, side, pitch=-28.0, y=0.0, dz=0.0):
    """posizione della caviglia per stare in punta di piedi (pivot sulla pianta)."""
    a = ctx.ankle[side]
    A = P.ankle_from_pivot(ctx, Vector((a.x, a.y + y, 0)), 0.0, pitch)
    return (A.x, A.y, A.z + dz)


def heel_down(ctx, side, pitch, y=0.0, x=None):
    """caviglia per un piede appoggiato sul tallone con la punta in su (gambe stese a terra)."""
    a = ctx.ankle[side]
    A = P.ankle_from_pivot(ctx, Vector((a.x if x is None else x, a.y + y, 0)), 0.0, pitch)
    return (A.x, A.y, A.z)


# ================================================================== LOCOMOZIONE
def idle(ctx):
    m = Motion('idle', 4.0, 'locomotion', loop=True, description='respiro, peso che si sposta, piccoli movimenti della testa')
    for t, hx, roll, chest, head, arm in ((0.0, 0.0, 0.0, 0.0, (0, 0, 0), 0.0), (1.0, 0.009, 1.6, -1.6, (2.0, 3.0, 1.0), 1.5),
                                          (2.0, 0.0, 0.0, 0.6, (0.5, 0.0, 0.0), 0.0), (3.0, -0.009, -1.6, -1.6, (1.5, -3.0, -1.0), -1.5),
                                          (4.0, 0.0, 0.0, 0.0, (0, 0, 0), 0.0)):
        m.pose(t, dict(STAND, chest=(chest, 0, 0), head=head, neck=(0.5 * head[0], 0.4 * head[1], 0),
                       spine=(0, 0, -roll * 0.6), upper_arm=(6 + arm * 0.5, 0, -22 + abs(arm)), forearm=(16 + abs(arm), 0, 0)))
        m.hips(t, loc=(hx, 0, -0.004 - abs(hx) * 0.3), rot=(0, 0, roll), scale=(1, 1, 1))
        br = 1.0 + 0.012 * (1 if t in (1.0, 3.0) else 0)
        m.scale(t, 'chest', (br, 1.0, br)); m.scale(t, 'spine', (1, 1, 1)); m.scale(t, 'head', (1, 1, 1))
        m.hand_shape(t, 'both', 'relax', amount=1.0 + 0.15 * math.sin(t * 1.6))
    m.plant_feet(0.0); m.plant_feet(4.0)
    for s in 'LR':
        m.hand(0.0, s, ctx.wrist[s], None, 0.0)
    return m


def jump(ctx, height=0.26):
    m = Motion('jump', 1.55, 'locomotion', description='salto verticale con anticipazione, volo balistico e atterraggio morbido')
    stand(m, 0.0, ctx, face='neutral')
    # anticipazione: si accuccia, braccia indietro
    m.pose(0.24, dict(STAND, spine=(14, 0, 0), chest=(8, 0, 0), head=(-14, 0, 0), upper_arm=(-48, 0, -12), forearm=(22, 0, 0)), 'stop')
    m.hips(0.24, loc=(0, 0.012, -0.095), rot=(16, 0, 0), mode='stop')
    m.scale(0.24, 'spine', (1.06, 0.90, 1.06), 'stop')
    m.face(0.06, 'determined', 0.12)
    m.plant_feet(0.24)
    # spinta: in punta di piedi, braccia su, corpo allungato
    m.pose(0.36, dict(STAND, spine=(-4, 0, 0), chest=(-4, 0, 0), head=(-8, 0, 0), upper_arm=(60, 0, 60), forearm=(12, 0, 0)))
    m.hips(0.33, loc=(0, -0.004, 0.035), rot=(-3, 0, 0), mode='fast')
    m.scale(0.33, 'spine', (0.94, 1.13, 0.94), 'fast')
    for s in 'LR':
        m.foot(0.33, s, on_toes(ctx, s, -34), 0, -34, 1.0, 'fast')
    m.face(0.30, 'joy', 0.1)
    t_off, t_land = 0.36, 0.36 + 2 * math.sqrt(2 * height / G)
    m.hips(t_off, loc=(0, -0.006, 0.05), rot=(-2, 0, 0))
    for s in 'LR':
        m.foot(t_off, s, on_toes(ctx, s, -30, dz=0.02), 0, -30, 1.0)
    flight(m, ctx, t_off, t_land, 0.05, 0.0, -0.006, 0.0, tuck=0.07)
    m.pose(t_off + 0.12, dict(STAND, spine=(2, 0, 0), head=(-12, 0, 0), upper_arm=(70, 0, 75), forearm=(18, 0, 0)))
    m.scale(t_off + 0.12, 'spine', (1.0, 1.0, 1.0))
    m.pose(t_land - 0.06, dict(STAND, spine=(6, 0, 0), head=(-4, 0, 0), upper_arm=(40, 0, 45), forearm=(30, 0, 0)))
    # atterraggio: squash e ritorno con un piccolo rimbalzo
    m.hips(t_land, loc=(0, 0.0, -0.01), rot=(4, 0, 0), mode='linear')
    m.plant_feet(t_land, 'linear')
    m.hips(t_land + 0.09, loc=(0, 0.01, -0.105), rot=(14, 0, 0), mode='stop')
    m.scale(t_land + 0.09, 'spine', (1.07, 0.88, 1.07), 'stop')
    m.pose(t_land + 0.09, dict(STAND, spine=(16, 0, 0), chest=(8, 0, 0), head=(-14, 0, 0), upper_arm=(30, 0, 30), forearm=(40, 0, 0)), 'stop')
    m.hips(t_land + 0.24, loc=(0, 0.0, 0.006), rot=(-2, 0, 0))
    m.scale(t_land + 0.24, 'spine', (0.98, 1.03, 0.98))
    m.face(t_land + 0.05, 'happy', 0.2)
    stand(m, 1.55, ctx, hands=False)
    return m


def turn(ctx, angle=90.0):
    return P.make_turn(angle)


def stop(ctx):
    return P.make_stop('walk')


# ================================================================== REAZIONI
def surprise(ctx):
    m = Motion('surprise', 1.4, 'reactions', description='sobbalzo indietro, mani al petto, occhi spalancati')
    stand(m, 0.0, ctx)
    m.pose(0.09, dict(STAND, spine=(4, 0, 0), head=(5, 0, 0), upper_arm=(10, 0, -22), forearm=(20, 0, 0)), 'stop')
    m.hips(0.09, loc=(0, -0.004, -0.014), mode='stop')
    m.pose(0.2, dict(STAND, spine=(-12, 0, 0), chest=(-6, 0, 0), head=(-10, 0, 0), shoulder=(0, 0, 8),
                     upper_arm=(58, 0, 8), forearm=(98, 0, 0), hand=(-20, 0, 0)), 'fast')
    m.hips(0.2, loc=(0, 0.045, 0.018), mode='fast')
    m.scale(0.2, 'spine', (0.96, 1.08, 0.96), 'fast')
    m.hand_shape(0.2, 'both', 'open', 'fast')
    m.face(0.13, 'surprised', 0.07)
    m.hips(0.32, loc=(0, 0.04, 0.004)); m.scale(0.32, 'spine', (1.01, 0.99, 1.01))
    m.pose(0.75, dict(STAND, spine=(-8, 0, 0), chest=(-4, 0, 0), head=(-6, 0, 0), shoulder=(0, 0, 5),
                      upper_arm=(48, 0, 4), forearm=(90, 0, 0), hand=(-14, 0, 0)))
    m.hips(0.75, loc=(0, 0.035, 0.0))
    m.face(1.0, 'surprised', 0.3, intensity=0.5)
    stand(m, 1.4, ctx, hands=False)
    m.plant_feet(0.75)
    return m


def shock(ctx):
    m = Motion('shock', 2.0, 'reactions', description='si irrigidisce e si allunga, ciuffo dritto, trema')
    stand(m, 0.0, ctx)
    m.hips(0.1, loc=(0, 0, -0.035), mode='stop'); m.scale(0.1, 'spine', (1.06, 0.9, 1.06), 'stop')
    m.pose(0.1, dict(STAND, spine=(6, 0, 0), head=(6, 0, 0)), 'stop')
    m.plant_feet(0.1)
    m.hips(0.2, loc=(0, 0.01, 0.03), mode='fast'); m.scale(0.2, 'spine', (0.93, 1.13, 0.93), 'fast')
    m.scale(0.2, 'head', (1.05, 1.05, 1.05), 'fast')
    m.pose(0.2, dict(STAND, spine=(-6, 0, 0), head=(-8, 0, 0), shoulder=(0, 0, 10), upper_arm=(-4, 0, -30), forearm=(0, 0, 0)), 'fast')
    m.hand_shape(0.2, 'both', 'open', 'fast')
    for s in 'LR':
        m.foot(0.2, s, on_toes(ctx, s, -16), 0, -16, 1.0, 'fast')
    m.face(0.17, 'shocked', 0.05)
    m.shake(0.24, 1.3, ['spine', 'head', 'upper_arm.L', 'upper_arm.R'], amp=2.2, freq=12.0, seed=3)
    m.scale(1.3, 'head', (1.03, 1.03, 1.03))
    for s in 'LR':
        m.foot(1.3, s, on_toes(ctx, s, -12), 0, -12, 1.0)
    m.hips(1.3, loc=(0, 0.01, 0.022)); m.scale(1.3, 'spine', (0.95, 1.1, 0.95))
    m.pose(1.3, dict(STAND, spine=(-5, 0, 0), head=(-6, 0, 0), shoulder=(0, 0, 8), upper_arm=(-3, 0, -28), forearm=(2, 0, 0)))
    m.hips(1.6, loc=(0, 0, -0.02)); m.scale(1.6, 'spine', (1.04, 0.95, 1.04)); m.scale(1.6, 'head', (1, 1, 1))
    m.plant_feet(1.6)
    m.face(1.5, 'shocked', 0.3, intensity=0.55)
    stand(m, 2.0, ctx, hands=False)
    return m


def fear(ctx):
    m = Motion('fear', 2.7, 'reactions', description='si rannicchia, mani davanti alla faccia, trema, sbircia e torna in piedi')
    stand(m, 0.0, ctx)
    face_l = lambda side, dy=0.0, dz=0.0: Rel('head', (0.085 * (1 if side == 'L' else -1), 0.12 + dz, 0.33 - dy))
    rot = {s: hand_orient(ctx, s, (0.15 * (1 if s == 'L' else -1), -0.1, 1.0), (0.0, -1.0, 0.0)) for s in 'LR'}
    m.face(0.1, 'scared', 0.08)
    m.pose(0.24, dict(STAND, spine=(10, 0, 0), chest=(6, 0, 0), neck=(2, -8, 0), head=(4, -16, 0), shoulder=(0, 0, 10)))
    m.hips(0.24, loc=(0, 0.06, -0.065), rot=(8, 0, 0))
    m.scale(0.2, 'spine', (1.04, 0.93, 1.04), 'fast')
    for s in 'LR':
        m.hand(0.36, s, face_l(s), rot[s], 1.0)
    m.hand_shape(0.2, 'both', 'open', 'fast')
    a = ctx.ankle['R']
    m.foot(0.06, 'R', (a.x, a.y, a.z), 0, 0, 1.0)
    m.foot(0.18, 'R', (a.x - 0.01, a.y + 0.06, a.z + 0.04), 0, -10, 1.0)
    m.foot(0.3, 'R', (a.x - 0.01, a.y + 0.11, a.z), 0, 0, 1.0)
    m.plant_feet(0.0)
    m.shake(0.3, 2.1, ['spine', 'chest', 'head', 'upper_arm.L', 'upper_arm.R'], amp=1.6, freq=14.0, seed=5)
    m.pose(1.2, dict(STAND, spine=(12, 0, 0), chest=(7, 0, 0), neck=(2, -8, 0), head=(5, -14, 0), shoulder=(0, 0, 12)))
    m.hips(1.2, loc=(0, 0.065, -0.07), rot=(9, 0, 0))
    for s in 'LR':
        m.hand(1.2, s, face_l(s), rot[s], 1.0)
    # sbircia tra le dita
    m.pose(1.6, dict(STAND, spine=(10, 0, 0), chest=(6, 0, 0), neck=(2, 0, 0), head=(-2, 4, 0), shoulder=(0, 0, 10)))
    for s in 'LR':
        m.hand(1.6, s, face_l(s, -0.01, -0.09), rot[s], 1.0)
    m.face(1.55, 'scared', 0.2, intensity=0.8)
    m.hips(2.0, loc=(0, 0.05, -0.04), rot=(6, 0, 0))
    m.pose(2.4, dict(STAND, spine=(4, 0, 0), chest=(2, 0, 0), shoulder=(0, 0, 4), upper_arm=(12, 0, -20), forearm=(30, 0, 0)))
    for s in 'LR':
        m.hand(2.0, s, face_l(s, 0.0, -0.14), rot[s], 0.6)
        m.hand(2.4, s, ctx.wrist[s], None, 0.0)
    m.hips(2.05, loc=(0, 0.05, -0.02), rot=(3, 0, 0)); m.scale(2.4, 'spine', (1, 1, 1))
    m.hand_shape(2.4, 'both', 'relax')
    # passo di ritorno: il piede destro torna accanto al sinistro (la clip finisce in piedi, pronta per «idle»)
    m.foot(2.05, 'R', (a.x - 0.01, a.y + 0.11, a.z), 0, 0, 1.0)
    m.foot(2.2, 'R', (a.x - 0.005, a.y + 0.055, a.z + 0.035), 0, -6, 1.0)
    m.foot(2.36, 'R', (a.x, a.y, a.z), 0, 0, 1.0, 'stop')
    m.foot(2.7, 'R', (a.x, a.y, a.z), 0, 0, 1.0)
    m.hips(2.36, loc=(0, 0.015, -0.01), rot=(1, 0, 0))
    m.pose(2.7, dict(STAND))
    m.hips(2.7, loc=(0, 0, 0), rot=(0, 0, 0))
    return m


def confusion(ctx):
    m = Motion('confusion', 2.7, 'reactions', description='testa inclinata, si gratta la testa, poi alza le spalle')
    stand(m, 0.0, ctx)
    m.face(0.2, 'confused', 0.25)
    scratch = lambda k: Rel('head', (-0.228 - 0.004 * (k % 2), 0.235 + 0.012 * (k % 2), 0.0 + 0.012 * (k % 2)))
    rot_r = hand_orient(ctx, 'R', (0.25, 0.1, 1.0), (1.0, 0.0, 0.2))
    m.pose(0.45, dict(STAND, head=(-4, 6, -14), neck=(0, 4, -6), spine=(0, 0, 4), shoulder=(0, 0, 0)))
    m.hand(0.0, 'R', ctx.wrist['R'], None, 0.0)
    m.hand(0.45, 'R', scratch(0), rot_r, 1.0)
    for k in range(1, 6):
        m.hand(0.45 + 0.11 * k, 'R', scratch(k), rot_r, 1.0, 'linear')
    m.hand(0.0, 'L', ctx.wrist['L'], None, 0.0)
    hip_l = (0.175, -0.01, 0.49)
    m.hand(0.5, 'L', hip_l, hand_orient(ctx, 'L', (-0.4, -0.2, -1.0), (-1.0, 0.0, 0.0)), 1.0,
           pole=(0.45, 0.2, 0.62))
    m.hand_shape(0.45, 'R', 'claw'); m.hand_shape(0.5, 'L', 'flat')
    m.hand(1.2, 'R', scratch(5), rot_r, 1.0)
    m.hand(1.2, 'L', hip_l, hand_orient(ctx, 'L', (-0.4, -0.2, -1.0), (-1.0, 0.0, 0.0)), 1.0, pole=(0.45, 0.2, 0.62))
    m.pose(1.2, dict(STAND, head=(-6, 8, -16), neck=(0, 4, -6), spine=(0, 0, 4)))
    # alzata di spalle con i palmi in su
    m.hand(1.55, 'R', ctx.wrist['R'], None, 0.0); m.hand(1.55, 'L', ctx.wrist['L'], None, 0.0)
    m.pose(1.75, dict(STAND, head=(-2, -4, 10), neck=(0, 0, 4), shoulder=(0, 0, 16), upper_arm=(18, 0, -2), forearm=(80, -55, 0),
                      hand=(-10, 0, 0)), 'fast')
    m.hand_shape(1.75, 'both', 'open')
    m.hips(1.75, loc=(0, 0, 0.012), mode='fast')
    m.face(1.7, 'confused', 0.15, intensity=1.15)
    m.pose(2.15, dict(STAND, head=(-2, -4, 8), neck=(0, 0, 3), shoulder=(0, 0, 10), upper_arm=(14, 0, -6), forearm=(72, -50, 0)))
    m.hips(2.15, loc=(0, 0, 0.0))
    stand(m, 2.7, ctx, hands=False)
    return m


def happiness(ctx):
    m = Motion('happiness', 2.2, 'reactions', description='saltella in punta di piedi con le braccia aperte')
    stand(m, 0.0, ctx)
    m.face(0.1, 'joy', 0.2)
    up = dict(STAND, spine=(-6, 0, 0), chest=(-4, 0, 0), head=(-8, 0, 0), upper_arm=(22, 0, 104), forearm=(14, 0, 0), hand=(-10, 0, 0))
    down = dict(STAND, spine=(6, 0, 0), chest=(2, 0, 0), head=(2, 0, 0), upper_arm=(24, 0, 80), forearm=(30, 0, 0))
    m.hand_shape(0.25, 'both', 'open')
    t = 0.16
    for k in range(3):
        m.pose(t, down, 'stop'); m.hips(t, loc=(0, 0, -0.04), mode='stop'); m.scale(t, 'spine', (1.04, 0.93, 1.04), 'stop')
        m.plant_feet(t)
        m.pose(t + 0.16, up); m.hips(t + 0.16, loc=(0, 0, 0.05 if k < 2 else 0.035)); m.scale(t + 0.16, 'spine', (0.96, 1.07, 0.96))
        for s in 'LR':
            m.foot(t + 0.16, s, on_toes(ctx, s, -30, dz=0.03 if k < 2 else 0.0), 0, -30, 1.0)
        t += 0.32
    m.pose(t, down, 'stop'); m.hips(t, loc=(0, 0, -0.03), mode='stop'); m.plant_feet(t); m.scale(t, 'spine', (1.03, 0.95, 1.03), 'stop')
    m.pose(t + 0.3, dict(STAND, spine=(-8, 0, 0), chest=(-6, 0, 0), head=(-10, 0, 6), upper_arm=(26, 0, 98), forearm=(12, 0, 0), hand=(-14, 0, 0)))
    m.hips(t + 0.3, loc=(0, 0.01, 0.0)); m.scale(t + 0.3, 'spine', (1, 1, 1))
    m.face(t + 0.5, 'happy', 0.3)
    stand(m, 2.2, ctx, hands=False)
    return m


def anger(ctx):
    m = Motion('anger', 2.4, 'reactions', description='pugni stretti, pestata di piede, trema dalla rabbia')
    stand(m, 0.0, ctx)
    m.face(0.18, 'angry', 0.15)
    a = ctx.ankle['R']
    m.pose(0.25, dict(STAND, spine=(-4, 0, 0), chest=(-6, 0, 0), head=(-6, 0, 0), shoulder=(0, 0, 8), upper_arm=(-10, 0, -18), forearm=(60, 0, 0)))
    m.hand_shape(0.2, 'both', 'fist')
    m.hips(0.25, loc=(0.03, 0.0, -0.006), rot=(0, 0, 3))
    m.foot(0.1, 'R', (a.x, a.y, a.z), 0, 0, 1.0)
    m.foot(0.3, 'R', (a.x, a.y - 0.02, a.z + 0.13), 0, 12, 1.0)
    m.foot(0.42, 'R', (a.x, a.y - 0.02, a.z), 0, 0, 1.0, 'slow')
    m.pose(0.44, dict(STAND, spine=(14, 0, 0), chest=(8, 0, 0), neck=(4, 0, 0), head=(10, 0, 0), shoulder=(0, 0, 10),
                      upper_arm=(-14, 0, -26), forearm=(34, 0, 0)), 'fast')
    m.hips(0.44, loc=(0.0, -0.01, -0.045), rot=(6, 0, 0), mode='fast')
    m.scale(0.44, 'spine', (1.05, 0.92, 1.05), 'fast')
    m.shake(0.46, 1.7, ['spine', 'head', 'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R'], amp=1.8, freq=13.0, seed=7)
    m.hips(0.6, loc=(0, -0.008, -0.03), rot=(5, 0, 0)); m.scale(0.6, 'spine', (1.02, 0.97, 1.02))
    m.pose(1.6, dict(STAND, spine=(10, 0, 0), chest=(4, 0, 0), neck=(4, 0, 0), head=(8, 0, 0), shoulder=(0, 0, 10),
                     upper_arm=(-12, 0, -24), forearm=(36, 0, 0)))
    # sbuffa: il petto si gonfia e si sgonfia
    m.pose(1.9, dict(STAND, spine=(2, 0, 0), chest=(-8, 0, 0), head=(-4, 0, 0), shoulder=(0, 0, 14), upper_arm=(-8, 0, -22), forearm=(30, 0, 0)))
    m.scale(1.9, 'chest', (1.05, 1.0, 1.05)); m.scale(0.0, 'chest', (1, 1, 1)); m.scale(1.6, 'chest', (1, 1, 1))
    m.hips(1.9, loc=(0, 0, 0.0))
    m.pose(2.4, dict(STAND, spine=(6, 0, 0), chest=(4, 0, 0), head=(4, 0, 0), shoulder=(0, 0, 4), upper_arm=(-2, 0, -22), forearm=(26, 0, 0)))
    m.scale(2.4, 'chest', (1, 1, 1)); m.scale(2.4, 'spine', (1, 1, 1))
    m.hips(2.4, loc=(0, 0, -0.004), rot=(2, 0, 0))
    m.plant_feet(2.4); m.plant_feet(0.0)
    return m


def sadness(ctx):
    m = Motion('sadness', 3.0, 'reactions', description='si affloscia, sospira, testa bassa e ciuffo giu\'')
    m.hold_end = True                                  # resta afflosciato: la clip successiva lo riporta su
    stand(m, 0.0, ctx)
    m.face(0.3, 'sad', 0.6)
    slump = dict(STAND, spine=(10, 0, 0), chest=(12, 0, 0), neck=(8, 0, 0), head=(14, 0, 0), shoulder=(6, 0, -8),
                 upper_arm=(12, 0, -24), forearm=(8, 0, 0))
    m.pose(0.8, slump); m.hips(0.8, loc=(0, 0.01, -0.022), rot=(4, 0, 0))
    m.pose(1.5, dict(slump, chest=(2, 0, 0), head=(6, 0, 0), shoulder=(2, 0, 2)))       # inspira
    m.scale(1.5, 'chest', (1.035, 1.0, 1.035)); m.scale(0.0, 'chest', (1, 1, 1)); m.scale(0.8, 'chest', (1, 1, 1))
    m.hips(1.5, loc=(0, 0.01, -0.012))
    m.pose(2.1, dict(slump, chest=(15, 0, 0), head=(16, 0, 0), shoulder=(8, 0, -10)))  # sospiro
    m.scale(2.1, 'chest', (0.99, 1.0, 0.99)); m.hips(2.1, loc=(0, 0.012, -0.026), rot=(5, 0, 0))
    m.pose(2.45, dict(slump, chest=(14, 0, 0), head=(16, 6, 0), shoulder=(8, 0, -10)))
    m.pose(3.0, dict(slump, chest=(13, 0, 0), head=(15, -3, 0), shoulder=(7, 0, -9)))
    m.scale(3.0, 'chest', (1, 1, 1)); m.hips(3.0, loc=(0, 0.01, -0.024), rot=(4, 0, 0))
    m.plant_feet(3.0); m.plant_feet(0.0)
    m.hand_shape(0.8, 'both', 'relax', amount=0.6)
    return m


# ================================================================== COMICHE
def _floor_pose(m, t, ctx, mode='auto', lean=-6.0, head=(0, 0, 0)):
    """seduto per terra con le gambe in avanti (stato «floor»)."""
    hx, hy, hz = FLOOR_HIPS
    m.hips(t, loc=(hx, hy, hz), rot=(lean, 0, 0), mode=mode)
    m.pose(t, dict(STAND, spine=(10, 0, 0), chest=(6, 0, 0), head=head, upper_arm=(-18, 0, -8), forearm=(20, 0, 0), hand=(-30, 0, 0)), mode)
    for s in 'LR':
        a = ctx.ankle[s]
        m.foot(t, s, heel_down(ctx, s, 52.0, y=floor_feet_y() - a.y, x=a.x * 1.15), 0, 52.0, 1.0, mode)
        m.hand(t, s, (0.17 * (1 if s == 'L' else -1), hy + 0.06, 0.035), hand_orient(ctx, s, (0.25 * (1 if s == 'L' else -1), -0.3, -1.0), (0, 0, -1)), 0.8, mode)


def fall(ctx):
    m = Motion('fall', 2.5, 'comedy', end='floor', description='perde l\'equilibrio, mulinella le braccia e cade seduto, stordito')
    stand(m, 0.0, ctx)
    m.face(0.12, 'surprised', 0.08)
    # mulinello delle braccia (cerchi all'indietro)
    m.pose(0.12, {'spine': (-8, 0, 0), 'chest': (-6, 0, 0), 'head': (-6, 0, 0)})
    m.pose(0.26, {'upper_arm.L': (40, 0, 40), 'upper_arm.R': (-40, 0, 40), 'forearm': (20, 0, 0)})
    for k in range(1, 7):                            # mulinello: cerchi all'indietro, sfasati tra le braccia
        t = 0.26 + 0.075 * k
        aL = 40 - 55 * k; aR = -40 - 55 * k
        m.pose(t, {'upper_arm.L': (aL, 0, 40), 'upper_arm.R': (aR, 0, 40), 'forearm': (20, 0, 0)})
    # chiude il giro: -320 e' lo stesso orientamento di +40 (salto di 360 gradi invisibile), poi si riparte da valori normali
    m.pose(0.785, {'upper_arm.L': (-320, 0, 40), 'upper_arm.R': (-400, 0, 40)})
    m.pose(0.79, {'upper_arm.L': (40, 0, 40), 'upper_arm.R': (-40, 0, 40)}, 'hold')
    m.hips(0.12, loc=(0, 0.02, 0.0), rot=(-6, 0, 0))
    m.hand_shape(0.15, 'both', 'open')
    a = {s: ctx.ankle[s] for s in 'LR'}
    m.plant_feet(0.15)
    for s in 'LR':                                   # i piedi scappano in avanti
        m.foot(0.5, s, (a[s].x, a[s].y - 0.10, a[s].z + 0.06), 0, 28, 1.0)
        m.foot(0.66, s, (a[s].x * 1.1, a[s].y - 0.2, a[s].z + 0.10), 0, 45, 1.0)
    m.hips(0.45, loc=(0, 0.07, -0.05), rot=(-16, 0, 0))
    m.pose(0.6, {'spine': (-14, 0, 0), 'chest': (-8, 0, 0), 'head': (4, 0, 0)})
    m.hips(0.66, loc=(0, 0.12, -0.17), rot=(-20, 0, 0), mode='slow')
    # impatto (accelera cadendo) + rimbalzo
    hx, hy, hz = FLOOR_HIPS
    m.hips(0.8, loc=(hx, hy, hz - 0.012), rot=(-22, 0, 0), mode='slow')
    m.scale(0.8, 'spine', (1.08, 0.86, 1.08), 'slow')
    m.pose(0.98, dict(STAND, spine=(-18, 0, 0), chest=(-6, 0, 0), head=(14, 0, 0), upper_arm=(40, 0, 60), forearm=(30, 0, 0)))
    for s in 'LR':
        m.foot(0.78, s, heel_down(ctx, s, 58.0, y=floor_feet_y() - a[s].y - 0.03, x=a[s].x * 1.15), 0, 58.0, 1.0, 'slow')
    m.hips(0.9, loc=(hx, hy, hz + 0.03), rot=(-12, 0, 0)); m.scale(0.9, 'spine', (0.97, 1.05, 0.97))
    m.hips(1.0, loc=(hx, hy, hz), rot=(-6, 0, 0), mode='stop'); m.scale(1.05, 'spine', (1, 1, 1))
    for s in 'LR':
        m.hand(0.0, s, ctx.wrist[s], None, 0.0)
        m.hand(0.8, s, ctx.wrist[s], None, 0.0)
    _floor_pose(m, 1.1, ctx, head=(8, 0, 0))
    m.face(1.0, 'dizzy', 0.25)
    # testa che gira stordita
    for k in range(6):
        t = 1.2 + 0.2 * k
        ang = k * 1.6
        m.pose(t, {'head': (6 + 7 * math.sin(ang), 8 * math.cos(ang), 7 * math.sin(ang + 0.6)), 'neck': (3, 3 * math.cos(ang), 0)})
    _floor_pose(m, 2.5, ctx, head=(5, 0, 0))
    m.pose(2.5, {'head': (5, 0, 0), 'neck': (2, 0, 0)})
    return m


def trip(ctx):
    m = Motion('trip', 1.9, 'comedy', description='inciampa camminando, barcolla in avanti e si riprende')
    stand(m, 0.0, ctx)
    a = {s: ctx.ankle[s] for s in 'LR'}
    # avanza con un passo, il piede destro resta agganciato
    m.root(0.0, 0, 0, 0); m.root(0.45, 0, -0.22, 0); m.root(0.9, 0, -0.5, 0, 'auto'); m.root(1.3, 0, -0.66, 0); m.root(1.9, 0, -0.70, 0)
    m.foot(0.05, 'L', (a['L'].x, a['L'].y, a['L'].z), 0, 0, 1.0)
    m.foot(0.3, 'L', (a['L'].x, a['L'].y - 0.14, a['L'].z + 0.05), 0, 10, 1.0)
    m.foot(0.45, 'L', (a['L'].x, a['L'].y - 0.26, a['L'].z), 0, 0, 1.0)
    m.foot(0.0, 'R', (a['R'].x, a['R'].y, a['R'].z), 0, 0, 1.0)
    m.foot(0.5, 'R', (a['R'].x, a['R'].y + 0.02, a['R'].z + 0.02), 0, -30, 1.0)     # agganciato
    m.foot(0.62, 'R', (a['R'].x, a['R'].y - 0.28, a['R'].z + 0.07), 0, 6, 1.0, 'fast')
    m.foot(0.74, 'R', (a['R'].x, a['R'].y - 0.52, a['R'].z), 0, 0, 1.0)
    m.foot(0.75, 'L', (a['L'].x, a['L'].y - 0.26, a['L'].z), 0, -20, 1.0)
    m.foot(0.92, 'L', (a['L'].x, a['L'].y - 0.62, a['L'].z + 0.05), 0, 4, 1.0, 'fast')
    m.foot(1.04, 'L', (a['L'].x, a['L'].y - 0.70, a['L'].z), 0, 0, 1.0)
    m.foot(1.1, 'R', (a['R'].x, a['R'].y - 0.52, a['R'].z), 0, 0, 1.0)
    m.foot(1.3, 'R', (a['R'].x, a['R'].y - 0.70, a['R'].z), 0, 0, 1.0)
    m.foot(1.9, 'R', (a['R'].x, a['R'].y - 0.70, a['R'].z), 0, 0, 1.0); m.foot(1.9, 'L', (a['L'].x, a['L'].y - 0.70, a['L'].z), 0, 0, 1.0)
    m.face(0.48, 'shocked', 0.06); m.face(1.35, 'embarrassed', 0.3)
    m.pose(0.45, dict(STAND, spine=(4, 0, 0)))
    m.pose(0.6, dict(STAND, spine=(30, 0, 0), chest=(14, 0, 0), head=(-26, 0, 0), upper_arm=(95, 0, 30), forearm=(20, 0, 0)), 'fast')
    m.hips(0.45, loc=(0, 0.0, -0.02), rot=(4, 0, 0))
    m.hips(0.6, loc=(0, -0.08, -0.06), rot=(26, 0, 0), mode='fast')
    m.hand_shape(0.6, 'both', 'open', 'fast')
    m.pose(0.75, {'upper_arm.L': (60, 0, 50), 'upper_arm.R': (130, 0, 20)})
    m.pose(0.9, {'upper_arm.L': (130, 0, 30), 'upper_arm.R': (50, 0, 60)})
    m.hips(0.8, loc=(0, -0.06, -0.05), rot=(20, 0, 0)); m.hips(1.0, loc=(0, -0.03, -0.03), rot=(10, 0, 0))
    m.pose(1.1, dict(STAND, spine=(6, 0, 0), chest=(0, 0, 0), head=(-4, 0, 0), upper_arm=(10, 0, 75), forearm=(10, 0, 0)))
    m.hips(1.25, loc=(0.01, 0.0, -0.008), rot=(-3, 0, 2))
    m.pose(1.35, dict(STAND, spine=(-4, 0, 0), head=(2, 0, 0), upper_arm=(6, 0, 70), forearm=(10, 0, 0)))
    m.hips(1.5, loc=(-0.008, 0.0, -0.004), rot=(0, 0, -2))
    stand(m, 1.9, ctx, hands=False, feet=False)
    return m


def slip(ctx):
    m = Motion('slip', 2.3, 'comedy', end='floor', description='scivola (buccia di banana): piedi in aria e atterraggio sul sedere')
    stand(m, 0.0, ctx)
    a = {s: ctx.ankle[s] for s in 'LR'}
    m.face(0.12, 'shocked', 0.06)
    m.foot(0.06, 'L', (a['L'].x, a['L'].y, a['L'].z), 0, 0, 1.0)
    m.foot(0.3, 'L', (a['L'].x, a['L'].y - 0.30, a['L'].z + 0.22), 0, 40, 1.0, 'fast')
    m.foot(0.42, 'L', (a['L'].x, a['L'].y - 0.26, a['L'].z + 0.36), 0, 60, 1.0)
    m.foot(0.1, 'R', (a['R'].x, a['R'].y, a['R'].z), 0, 0, 1.0)
    m.foot(0.34, 'R', (a['R'].x, a['R'].y - 0.18, a['R'].z + 0.16), 0, 40, 1.0)
    m.foot(0.42, 'R', (a['R'].x, a['R'].y - 0.22, a['R'].z + 0.30), 0, 60, 1.0)
    # il corpo va orizzontale in aria e cade sul sedere
    m.hips(0.18, loc=(0, 0.04, 0.02), rot=(-20, 0, 0))
    m.hips(0.36, loc=(0, 0.10, -0.06), rot=(-55, 0, 0))
    m.pose(0.36, dict(STAND, spine=(-10, 0, 0), chest=(-6, 0, 0), head=(26, 0, 0), upper_arm=(70, 0, 95), forearm=(20, 0, 0)))
    m.hand_shape(0.2, 'both', 'open')
    hx, hy, hz = FLOOR_HIPS
    m.hips(0.56, loc=(hx, hy + 0.01, hz - 0.012), rot=(-48, 0, 0), mode='slow')
    m.scale(0.56, 'spine', (1.07, 0.88, 1.07), 'slow')
    for s in 'LR':
        m.foot(0.56, s, heel_down(ctx, s, 56.0, y=floor_feet_y() - a[s].y - 0.02, x=a[s].x * 1.15), 0, 56.0, 1.0, 'slow')
    m.pose(0.56, dict(STAND, spine=(-14, 0, 0), chest=(-6, 0, 0), head=(30, 0, 0), upper_arm=(110, 0, 70), forearm=(20, 0, 0)), 'slow')
    m.hips(0.68, loc=(hx, hy, hz + 0.035), rot=(-32, 0, 0)); m.scale(0.7, 'spine', (0.97, 1.05, 0.97))
    m.hips(0.82, loc=(hx, hy, hz), rot=(-20, 0, 0), mode='stop'); m.scale(0.85, 'spine', (1, 1, 1))
    for s in 'LR':
        m.hand(0.0, s, ctx.wrist[s], None, 0.0); m.hand(0.75, s, ctx.wrist[s], None, 0.0)
    _floor_pose(m, 1.15, ctx, head=(8, 0, 0))
    m.face(1.0, 'dizzy', 0.3)
    for k in range(5):
        t = 1.3 + 0.2 * k; ang = k * 1.7
        m.pose(t, {'head': (6 + 6 * math.sin(ang), 7 * math.cos(ang), 6 * math.sin(ang + 0.7))})
    _floor_pose(m, 2.3, ctx, head=(5, 0, 0)); m.pose(2.3, {'head': (5, 0, 0)})
    return m


def dance(ctx, bpm=120):
    beat = 60.0 / bpm
    D = 8 * beat
    m = Motion('dance', D, 'comedy', loop=True, description='step-touch a tempo, braccia «raise the roof», twist')
    a = {s: ctx.ankle[s] for s in 'LR'}
    m.face(0.0, 'joy', 0.1)
    m.hand_shape(0.0, 'both', 'fist', amount=0.6)
    def feet(t, lx, rx, lz=0.0, rz=0.0, lp=0.0, rp=0.0, mode='auto'):
        m.foot(t, 'L', (a['L'].x + lx, a['L'].y, a['L'].z + lz), 0, lp, 1.0, mode)
        m.foot(t, 'R', (a['R'].x + rx, a['R'].y, a['R'].z + rz), 0, rp, 1.0, mode)
    # battute 1-4: step-touch a sinistra e a destra con le braccia che oscillano
    seq = [  # (dx L, dx R, fianchi x, braccia L, braccia R)
        (0.0, 0.0, 0.0), (0.09, 0.0, 0.04), (0.09, 0.07, 0.03), (0.0, 0.0, -0.04), (0.0, -0.09, -0.04), (-0.07, -0.09, -0.03),
        (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    for i in range(9):
        t = i * beat
        lx, rx, hx = seq[i]
        down = (i % 2 == 0)
        feet(t, lx, rx, mode='auto')
        m.hips(t, loc=(hx, 0, -0.035 if down else -0.012), rot=(4, -8 * math.copysign(1, hx) if hx else 0, -6 * (hx / 0.04) if hx else 0))
        m.scale(t, 'spine', (1.03, 0.95, 1.03) if down else (0.98, 1.03, 0.98)); m.scale(t, 'chest', (1, 1, 1)); m.scale(t, 'head', (1, 1, 1))
        if i < 4:
            sw = 35 if i % 2 else -35
            m.pose(t, dict(STAND, spine=(4, sw * 0.2, 0), chest=(0, sw * 0.3, 0), head=(8 if down else -3, -sw * 0.2, 0),
                           upper_arm=(sw + 20, 0, 10), forearm=(90, 0, 0)))
        elif i < 6:   # braccia in alto a V, a tempo
            m.pose(t, dict(STAND, spine=(-2, 0, 0), head=(10 if down else -6, 0, 0), shoulder=(0, 0, 8),
                           upper_arm=(14, 0, 102 if down else 92), forearm=(18, 0, 0), hand=(-20, 0, 0)))
        elif i < 8:   # twist
            tw = 28 if i % 2 == 0 else -28
            m.pose(t, dict(STAND, spine=(4, tw * 0.5, 0), chest=(0, tw * 0.6, 0), head=(6 if down else -2, -tw * 0.6, 0),
                           upper_arm=(30, 0, 30), forearm=(80, 0, 0)))
        else:
            m.pose(t, dict(STAND, spine=(4, -7, 0), chest=(0, -10.5, 0), head=(8, 7, 0), upper_arm=(-15, 0, 10), forearm=(90, 0, 0)))
    # le chiavi a meta' battuta per il rimbalzo
    for i in range(8):
        t = (i + 0.5) * beat
        m.hips(t, loc=(seq[i][2] * 0.6 + seq[i + 1][2] * 0.4, 0, -0.01))
    # ultimo fotogramma = primo (ciclo)
    t = D
    m.pose(t, dict(STAND, spine=(4, -7, 0), chest=(0, -10.5, 0), head=(8, 7, 0), upper_arm=(-15, 0, 10), forearm=(90, 0, 0)))
    m.pose(0.0, dict(STAND, spine=(4, -7, 0), chest=(0, -10.5, 0), head=(8, 7, 0), upper_arm=(-15, 0, 10), forearm=(90, 0, 0)))
    m.hips(D, loc=(0, 0, -0.035), rot=(4, 0, 0)); m.hips(0.0, loc=(0, 0, -0.035), rot=(4, 0, 0))
    m.scale(D, 'spine', (1.03, 0.95, 1.03)); m.scale(0.0, 'spine', (1.03, 0.95, 1.03))
    feet(D, 0.0, 0.0)
    for s in 'LR':
        m.hand(0.0, s, ctx.wrist[s], None, 0.0)
    m.params = dict(bpm=bpm)
    return m


def celebrate(ctx):
    m = Motion('celebrate', 2.1, 'comedy', description='pugno al cielo con saltello, poi doppio «yes!»')
    stand(m, 0.0, ctx)
    m.face(0.1, 'joy', 0.15)
    m.hand_shape(0.12, 'both', 'fist')
    m.pose(0.16, dict(STAND, spine=(10, 0, 0), head=(-6, 0, 0), upper_arm=(-10, 0, 10), forearm=(105, 0, 0),
                      **{'upper_arm.R': (20, 0, 30), 'forearm.R': (125, 0, 0)}), 'stop')
    m.hips(0.16, loc=(0, 0, -0.06), mode='stop'); m.scale(0.16, 'spine', (1.05, 0.91, 1.05), 'stop')
    m.plant_feet(0.16)
    t_off, h = 0.36, 0.10
    t_land = t_off + 2 * math.sqrt(2 * h / G)
    m.pose(t_off, dict(STAND, spine=(-6, 0, 0), head=(-14, 0, 0), **{'upper_arm.R': (135, 0, 48), 'forearm.R': (8, 0, 0),
                                                                    'upper_arm.L': (-24, 0, -6), 'forearm.L': (95, 0, 0)}))
    m.hips(t_off, loc=(0, 0, 0.03), mode='fast'); m.scale(t_off, 'spine', (0.95, 1.1, 0.95), 'fast')
    for s in 'LR':
        m.foot(t_off, s, on_toes(ctx, s, -30, dz=0.01), 0, -30, 1.0, 'fast')
    flight(m, ctx, t_off, t_land, 0.03, 0.0, 0.0, 0.0, tuck=0.05, n=6)
    m.hips(t_land, loc=(0, 0, -0.005), mode='linear'); m.plant_feet(t_land, 'linear')
    m.pose(t_land + 0.06, dict(STAND, spine=(4, 0, 0), head=(-10, 0, 0), **{'upper_arm.R': (132, 0, 48), 'forearm.R': (10, 0, 0),
                                                                          'upper_arm.L': (-20, 0, -6), 'forearm.L': (100, 0, 0)}))
    m.hips(t_land + 0.08, loc=(0, 0, -0.06), mode='stop'); m.scale(t_land + 0.08, 'spine', (1.05, 0.9, 1.05), 'stop')
    m.scale(t_land + 0.25, 'spine', (1, 1, 1)); m.hips(t_land + 0.25, loc=(0, 0, -0.03))
    # doppio pugno «yes!»
    t = t_land + 0.30
    for k in range(3):
        m.pose(t, dict(STAND, spine=(12, 0, 0), chest=(6, 0, 0), head=(4, 0, 0), upper_arm=(-6, 0, 42), forearm=(105, 0, 0)), 'fast')
        m.hips(t, loc=(0, 0, -0.045))
        m.pose(t + 0.12, dict(STAND, spine=(4, 0, 0), head=(-4, 0, 0), upper_arm=(24, 0, 44), forearm=(120, 0, 0)))
        m.hips(t + 0.12, loc=(0, 0, -0.02))
        t += 0.24
    stand(m, 2.1, ctx, hands=False)
    m.face(1.8, 'happy', 0.3)
    return m


def facepalm(ctx):
    m = Motion('facepalm', 2.8, 'comedy', description='mano sulla faccia, scuote la testa, sospiro')
    stand(m, 0.0, ctx)
    rot = hand_orient(ctx, 'R', (0.15, 0.25, 1.0), (0.0, 1.0, -0.1))
    on_face = lambda dz=0.0, dy=0.0: Rel('head', (-0.012, 0.075 + dz, 0.245 + dy))     # il polso sotto il mento, il palmo sulla faccia
    m.hand(0.0, 'R', ctx.wrist['R'], None, 0.0)
    m.hand(0.25, 'R', ctx.wrist['R'], None, 0.0)          # l'IK parte dopo la dissolvenza d'ingresso
    m.hand(0.55, 'R', (-0.09, -0.26, 0.52), rot, 1.0)      # la mano ruota di quasi mezzo giro: le serve tempo
    m.hand(0.78, 'R', on_face(), rot, 1.0)
    m.hand_shape(0.45, 'R', 'flat')
    m.pose(0.7, dict(STAND, spine=(6, 0, 0), neck=(6, 0, 0), head=(8, 0, 0)))
    face = FACE.expression('sad'); face['lid.L'] = face['lid.R'] = 0.05; face['m.frown'] = 0.8
    m.face(0.55, face, 0.2)
    m.pose(0.9, dict(STAND, spine=(10, 0, 0), neck=(8, 0, 0), head=(18, 0, 0), shoulder=(4, 0, -4)))
    m.hand(0.9, 'R', on_face(-0.01), rot, 1.0)
    for k, yaw in enumerate((10, -10, 9, -8, 0)):
        t = 1.0 + 0.16 * k
        m.pose(t, {'head': (18, yaw, 0), 'neck': (8, yaw * 0.4, 0)})
    m.scale(1.4, 'chest', (1.03, 1.0, 1.03)); m.scale(0.0, 'chest', (1, 1, 1)); m.scale(1.0, 'chest', (1, 1, 1))
    m.scale(1.9, 'chest', (0.99, 1.0, 0.99))
    m.hand(1.65, 'R', on_face(-0.01), rot, 1.0)
    m.hand(1.95, 'R', on_face(-0.10, 0.04), rot, 0.8)
    m.hand(2.4, 'R', ctx.wrist['R'], None, 0.0)
    m.face(1.9, 'disgust', 0.3, intensity=0.6)
    m.pose(2.0, dict(STAND, spine=(6, 0, 0), neck=(4, 0, 0), head=(6, 0, 0)))
    stand(m, 2.8, ctx, hands=False)
    m.scale(2.8, 'chest', (1, 1, 1))
    return m


def look_around(ctx):
    m = Motion('look_around', 3.2, 'comedy', description='si guarda intorno: gli occhi anticipano la testa')
    stand(m, 0.0, ctx)
    base = FACE.expression('neutral'); base['brow_raise.L'] = base['brow_raise.R'] = 8
    def eyes(t, yaw, pitch=0.0, dur=0.1):
        ch = dict(base); ch['eye_yaw'] = yaw; ch['eye_pitch'] = pitch
        m.face(t, ch, dur)
    eyes(0.0, 0.0)
    eyes(0.2, 26, 0, 0.08); m.pose(0.55, dict(STAND, chest=(0, 12, 0), neck=(0, 14, 0), head=(-2, 30, 4)))
    eyes(0.6, 14, 0, 0.12)
    m.pose(1.05, dict(STAND, chest=(0, 12, 0), neck=(0, 14, 0), head=(-4, 32, 3)))
    eyes(1.12, -28, 0, 0.08); m.pose(1.6, dict(STAND, chest=(0, -12, 0), neck=(0, -14, 0), head=(-2, -30, -4)))
    eyes(1.68, -14, 0, 0.12)
    m.pose(2.1, dict(STAND, chest=(0, -10, 0), neck=(0, -14, 0), head=(-4, -32, -3)))
    eyes(2.15, 0, 18, 0.1); m.pose(2.6, dict(STAND, neck=(-4, 0, 0), head=(-14, 0, 0)))
    eyes(2.7, 0, 0, 0.2)
    m.hips(0.55, loc=(0.0, 0.0, -0.004), rot=(0, 5, 0)); m.hips(1.6, loc=(0, 0, -0.004), rot=(0, -5, 0))
    stand(m, 3.2, ctx, hands=False)
    return m


def exaggerated_reaction(ctx):
    m = Motion('exaggerated_reaction', 2.3, 'comedy', description='«doppia presa» cartoon: si accartoccia, poi scatta allungato con gli occhi fuori')
    stand(m, 0.0, ctx)
    m.face(0.0, 'neutral', 0.1)
    m.pose(0.28, dict(STAND, spine=(12, 0, 0), chest=(6, 0, 0), head=(12, 0, 0), shoulder=(0, 0, 8), upper_arm=(10, 0, -26), forearm=(30, 0, 0)), 'stop')
    m.hips(0.28, loc=(0, 0, -0.07), mode='stop'); m.scale(0.28, 'spine', (1.09, 0.86, 1.09), 'stop')
    sq = FACE.expression('neutral'); sq['lid.L'] = sq['lid.R'] = 0.45; sq['m.M'] = 1.0
    m.face(0.18, sq, 0.1)
    m.plant_feet(0.28)
    m.pose(0.4, dict(STAND, spine=(-10, 0, 0), chest=(-8, 0, 0), head=(-16, 0, 0), shoulder=(0, 0, 14), upper_arm=(40, 0, 82),
                     forearm=(8, 0, 0), hand=(-30, 0, 0)), 'fast')
    m.hips(0.4, loc=(0, 0.02, 0.10), mode='fast'); m.scale(0.4, 'spine', (0.88, 1.24, 0.88), 'fast')
    m.scale(0.4, 'head', (1.1, 1.1, 1.1), 'fast')
    m.hand_shape(0.4, 'both', 'open', 'fast')
    for s in 'LR':
        m.foot(0.4, s, on_toes(ctx, s, -40, dz=0.05), 0, -40, 1.0, 'fast')
    m.face(0.37, 'shocked', 0.04, intensity=1.3)
    m.shake(0.42, 0.95, ['spine', 'head', 'upper_arm.L', 'upper_arm.R'], amp=2.8, freq=15.0, seed=9)
    m.hips(0.95, loc=(0, 0.02, 0.09)); m.scale(0.95, 'spine', (0.9, 1.2, 0.9)); m.scale(0.95, 'head', (1.08, 1.08, 1.08))
    for s in 'LR':
        m.foot(0.95, s, on_toes(ctx, s, -38, dz=0.04), 0, -38, 1.0)
    m.pose(0.95, dict(STAND, spine=(-9, 0, 0), chest=(-7, 0, 0), head=(-14, 0, 0), shoulder=(0, 0, 12), upper_arm=(38, 0, 78), forearm=(10, 0, 0)))
    # ricaduta con oscillazione
    m.hips(1.15, loc=(0, 0.01, -0.05), mode='slow'); m.scale(1.15, 'spine', (1.08, 0.88, 1.08), 'slow'); m.scale(1.15, 'head', (0.97, 0.97, 0.97), 'slow')
    m.plant_feet(1.15, 'slow')
    m.pose(1.15, dict(STAND, spine=(8, 0, 0), head=(6, 0, 0), upper_arm=(20, 0, 20), forearm=(30, 0, 0)), 'slow')
    m.hips(1.32, loc=(0, 0, 0.012)); m.scale(1.32, 'spine', (0.97, 1.05, 0.97)); m.scale(1.32, 'head', (1.02, 1.02, 1.02))
    m.hips(1.5, loc=(0, 0, -0.008)); m.scale(1.5, 'spine', (1.01, 0.99, 1.01)); m.scale(1.5, 'head', (1, 1, 1))
    m.face(1.2, 'shocked', 0.3, intensity=0.5)
    m.face(1.8, 'surprised', 0.3, intensity=0.4)
    stand(m, 2.3, ctx, hands=False)
    return m


# ================================================================== INTERAZIONI
def point(ctx, target=(0.6, -1.4, 0.9), side=None):
    m = Motion('point', 1.7, 'interactions', description='indica un punto (bersaglio nello spazio)')
    stand(m, 0.0, ctx)
    T = Vector(target)
    if side is None:                       # usa il braccio dalla parte del bersaglio (non incrocia il corpo)
        side = 'L' if T.x >= 0 else 'R'
    S = ctx.shoulder[side] + Vector((0, -0.01, 0.0))
    d = (T - S).normalized()
    reach = (ctx.sk.length['upper_arm.' + side] + ctx.sk.length['forearm.' + side]) * 0.97
    W = S + d * reach
    rot = hand_orient(ctx, side, d, (0, 0, -1) if abs(d.z) < 0.8 else (0, 1, 0))
    m.hand(0.0, side, ctx.wrist[side], None, 0.0)
    m.hand(0.3, side, tuple(W + Vector((0, 0, 0.03))), rot, 1.0, 'fast')
    m.hand(0.42, side, tuple(W), rot, 1.0)
    m.hand(1.3, side, tuple(W), rot, 1.0)
    m.hand(1.7, side, ctx.wrist[side], None, 0.0)
    m.hand_shape(0.28, side, 'point', 'fast')
    yaw = math.degrees(math.atan2(T.x, -T.y)); pitch = math.degrees(math.atan2(T.z - 0.85, math.hypot(T.x, T.y)))
    yaw = max(-60, min(60, yaw))
    m.pose(0.35, dict(STAND, chest=(0, yaw * 0.25, 0), neck=(-pitch * 0.3, yaw * 0.3, 0), head=(-pitch * 0.5, yaw * 0.45, 0)))
    m.pose(1.3, dict(STAND, chest=(0, yaw * 0.25, 0), neck=(-pitch * 0.3, yaw * 0.3, 0), head=(-pitch * 0.5, yaw * 0.45, 0)))
    m.hips(0.35, loc=(0.0, -0.006, -0.004), rot=(2, yaw * 0.1, 0))
    m.face(0.3, 'happy', 0.2, intensity=0.6)
    stand(m, 1.7, ctx, hands=False)
    m.params = dict(target=tuple(target), side=side)
    return m


def wave(ctx, side='R'):
    m = Motion('wave', 2.1, 'interactions', description='saluta con la mano')
    stand(m, 0.0, ctx)
    sg = 1 if side == 'L' else -1
    rot = hand_orient(ctx, side, (0.05 * sg, -0.05, 1.0), (0, -1, 0))
    rot_in = hand_orient(ctx, side, (-0.30 * sg, -0.05, 1.0), (0, -1, 0))
    rot_out = hand_orient(ctx, side, (0.35 * sg, -0.05, 1.0), (0, -1, 0))
    pole = (0.45 * sg, 0.25, 0.35)
    m.hand(0.0, side, ctx.wrist[side], None, 0.0)
    m.hand(0.35, side, (0.33 * sg, -0.08, 0.92), rot, 1.0, pole=pole)
    xs = (0.40, 0.31, 0.40, 0.31, 0.39, 0.32)
    for k, x in enumerate(xs):
        m.hand(0.52 + 0.16 * k, side, (x * sg, -0.08, 0.93 + 0.01 * (k % 2)), rot_out if k % 2 == 0 else rot_in, 1.0, pole=pole)
    m.hand(1.6, side, (0.33 * sg, -0.08, 0.90), rot, 1.0, pole=pole)
    m.hand(2.05, side, ctx.wrist[side], None, 0.0)
    m.hand_shape(0.3, side, 'open')
    m.pose(0.4, dict(STAND, chest=(0, 0, -4 * sg), head=(-2, 0, 6 * sg), spine=(0, 0, -3 * sg)))
    m.pose(1.6, dict(STAND, chest=(0, 0, -4 * sg), head=(-2, 0, 6 * sg), spine=(0, 0, -3 * sg)))
    m.hips(0.4, loc=(0.008 * sg, 0, -0.004), rot=(0, 0, 2 * sg))
    m.face(0.2, 'happy', 0.25)
    stand(m, 2.1, ctx, hands=False)
    m.params = dict(side=side)
    return m


def pick_up(ctx, obj=(0.0, -0.21, 0.06), size=0.06):
    m = Motion('pick_up', 2.4, 'interactions', end='holding', description='si accovaccia, prende l\'oggetto con due mani e lo solleva')
    stand(m, 0.0, ctx)
    O = Vector(obj)
    hold = Vector((0.0, -0.20, 0.55))
    rot = {s: hand_orient(ctx, s, (0, -0.4, -1.0), (-1 if s == 'L' else 1, 0, 0)) for s in 'LR'}
    rot_up = {s: hand_orient(ctx, s, (0, -1.0, 0.3), (-1 if s == 'L' else 1, 0, 0)) for s in 'LR'}
    off = {s: Vector(((size + 0.025) * (1 if s == 'L' else -1), 0.012, 0.03)) for s in 'LR'}
    m.pose(0.5, dict(STAND, spine=(10, 0, 0), chest=(6, 0, 0), neck=(6, 0, 0), head=(10, 0, 0)))
    m.hips(0.5, loc=(0, 0.05, -0.14), rot=(10, 0, 0))
    m.pose(0.95, dict(STAND, spine=(14, 0, 0), chest=(8, 0, 0), neck=(8, 0, 0), head=(6, 0, 0)))
    m.hips(0.95, loc=(0, 0.07, -0.235), rot=(14, 0, 0))
    m.scale(0.95, 'spine', (1, 1, 1))
    for s in 'LR':
        m.hand(0.0, s, ctx.wrist[s], None, 0.0)
        m.hand(0.25, s, ctx.wrist[s], None, 0.0)
        m.hand(0.6, s, tuple(O + off[s] * 1.6 + Vector((0, 0, 0.10))), rot[s], 1.0)
        m.hand(0.95, s, tuple(O + off[s]), rot[s], 1.0)
        m.hand(1.1, s, tuple(O + off[s]), rot[s], 1.0)
        m.hand(1.75, s, tuple(hold + off[s]), rot_up[s], 1.0)
        m.hand(2.4, s, tuple(hold + off[s]), rot_up[s], 1.0)
    m.hand_shape(0.6, 'both', 'open'); m.hand_shape(1.0, 'both', 'grab')
    m.event(1.02, 'grab', side='both')
    m.face(0.4, 'determined', 0.3, intensity=0.6)
    m.pose(1.75, dict(STAND, spine=(-2, 0, 0), chest=(-2, 0, 0), head=(4, 0, 0)))
    m.hips(1.75, loc=(0, 0.01, -0.01), rot=(0, 0, 0))
    m.pose(2.4, dict(STAND, spine=(-2, 0, 0), chest=(-2, 0, 0), head=(6, 0, 0)))
    m.hips(2.4, loc=(0, 0, 0)); m.face(1.9, 'happy', 0.3)
    m.plant_feet(0.0); m.plant_feet(2.4)
    m.params = dict(obj=tuple(obj), size=size, hold=tuple(hold))
    return m


def throw(ctx, target=(0.0, -2.2, 0.5)):
    m = Motion('throw', 1.7, 'interactions', start='holding', description='carica, lancia con un passo avanti e accompagna il gesto')
    hold = Vector((0.0, -0.20, 0.55))
    rot_up = {s: hand_orient(ctx, s, (0, -1.0, 0.3), (-1 if s == 'L' else 1, 0, 0)) for s in 'LR'}
    off = {s: Vector((0.085 * (1 if s == 'L' else -1), 0.012, 0.03)) for s in 'LR'}
    m.pose(0.0, dict(STAND, spine=(-2, 0, 0), chest=(-2, 0, 0), head=(6, 0, 0)))
    m.hand_shape(0.0, 'both', 'grab'); m.hips(0.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1))
    for b in ('spine', 'chest', 'head'):
        m.scale(0.0, b, (1, 1, 1))
    m.plant_feet(0.0)
    for s in 'LR':
        m.hand(0.0, s, tuple(hold + off[s]), rot_up[s], 1.0)
    a = {s: ctx.ankle[s] for s in 'LR'}
    # carica: la destra va dietro la spalla, la sinistra indica avanti, torsione del busto
    rot_back = hand_orient(ctx, 'R', (0, 0.4, 1.0), (0, -1, 0))
    m.hand(0.42, 'R', (-0.32, 0.08, 0.60), rot_back, 1.0)
    m.hand(0.42, 'L', (0.22, -0.33, 0.56), hand_orient(ctx, 'L', (0, -1, 0.2), (0, 0, -1)), 1.0)
    m.hand_shape(0.3, 'L', 'open')
    m.pose(0.42, dict(STAND, spine=(-4, -14, 0), chest=(-4, -20, 0), head=(-4, 22, 0)))
    m.hips(0.42, loc=(-0.015, 0.02, -0.03), rot=(0, -10, 0))
    m.foot(0.2, 'L', (a['L'].x, a['L'].y, a['L'].z), 0, 0, 1.0)
    m.foot(0.42, 'L', (a['L'].x, a['L'].y - 0.02, a['L'].z + 0.05), 0, 8, 1.0)
    # lancio: passo avanti e frusta del braccio
    m.foot(0.6, 'L', (a['L'].x, a['L'].y - 0.14, a['L'].z), 0, 0, 1.0, 'fast')
    m.hand(0.58, 'R', (-0.29, -0.14, 0.64), hand_orient(ctx, 'R', (0, -1, 0.3), (0.5, 0, -1)), 1.0)
    m.hand(0.76, 'R', (-0.12, -0.38, 0.62), hand_orient(ctx, 'R', (0, -1, 0.1), (0, 0, -1)), 1.0)
    m.event(0.60, 'release', side='R', target=tuple(target))
    m.hand_shape(0.62, 'R', 'open')
    m.pose(0.6, dict(STAND, spine=(14, 10, 0), chest=(8, 18, 0), head=(-8, -10, 0)), 'fast')
    m.hips(0.6, loc=(0.0, -0.06, -0.035), rot=(6, 10, 0), mode='fast')
    # accompagnamento
    m.hand(0.9, 'R', (0.06, -0.26, 0.44), hand_orient(ctx, 'R', (0.3, -0.6, -1.0), (0, 0, 1)), 1.0)
    m.hand(0.85, 'L', (0.16, -0.05, 0.52), None, 0.4)
    m.hand(1.3, 'R', ctx.wrist['R'], None, 0.0); m.hand(1.3, 'L', ctx.wrist['L'], None, 0.0)
    m.face(0.3, 'determined', 0.2); m.face(0.9, 'happy', 0.3)
    m.pose(1.0, dict(STAND, spine=(6, 4, 0), chest=(2, 6, 0)))
    m.hips(1.0, loc=(0, -0.05, -0.01), rot=(2, 4, 0))
    m.hips(1.5, loc=(0, 0.0, -0.006), rot=(0, 0, 0))
    # il piede destro raggiunge il sinistro: si chiude in piedi, una quindicina di centimetri piu' avanti
    m.foot(0.0, 'R', (a['R'].x, a['R'].y, a['R'].z), 0, 0, 1.0); m.foot(1.05, 'R', (a['R'].x, a['R'].y, a['R'].z), 0, 0, 1.0)
    m.foot(1.2, 'R', (a['R'].x, a['R'].y - 0.07, a['R'].z + 0.04), 0, -6, 1.0)
    m.foot(1.35, 'R', (a['R'].x, a['R'].y - 0.14, a['R'].z), 0, 0, 1.0)
    m.foot(1.7, 'R', (a['R'].x, a['R'].y - 0.14, a['R'].z), 0, 0, 1.0)
    m.foot(1.7, 'L', (a['L'].x, a['L'].y - 0.14, a['L'].z), 0, 0, 1.0)
    m.root(0.0, 0, 0, 0); m.root(1.0, 0, 0, 0); m.root(1.5, 0, -0.14, 0); m.root(1.7, 0, -0.14, 0)
    stand(m, 1.7, ctx, hands=False, feet=False, y=0.0)
    m.params = dict(target=tuple(target))
    return m


def _push_pull(ctx, name, direction, dist=0.28, box=(0.0, -0.42, 0.0), size=(0.30, 0.30, 0.40)):
    """direction = -1 spinge (avanti, verso -Y), +1 tira (indietro)."""
    m = Motion(name, 2.7, 'interactions', description='spinge la scatola camminando' if direction < 0 else 'tira la scatola camminando all\'indietro')
    stand(m, 0.0, ctx)
    face_y = box[1] + size[1] / 2
    hz = min(0.50, size[2] * 0.8)
    if direction < 0:
        rot = {s: hand_orient(ctx, s, (0, -0.15, 1.0), (0, -1, 0)) for s in 'LR'}
    else:
        rot = {s: hand_orient(ctx, s, (0, -1.0, 0.2), ((-1 if s == 'L' else 1), 0, 0)) for s in 'LR'}
    lean = 22 if direction < 0 else -12
    yfinal = -dist if direction < 0 else dist
    m.root(0.0, 0, 0, 0); m.root(0.65, 0, 0, 0); m.root(2.05, 0, yfinal, 0); m.root(2.7, 0, yfinal, 0)
    for s in 'LR':
        xs = (size[0] * 0.33) * (1 if s == 'L' else -1)
        contact = Vector((xs, face_y + (0.012 if direction < 0 else -0.01), hz))
        m.hand(0.0, s, ctx.wrist[s], None, 0.0)
        m.hand(0.55, s, tuple(contact), rot[s], 1.0)
        m.hand(2.1, s, tuple(contact + Vector((0, yfinal, 0))), rot[s], 1.0)
        m.hand(2.6, s, ctx.wrist[s], None, 0.0)
    m.hand_shape(0.45, 'both', 'flat' if direction < 0 else 'grab')
    m.event(0.6, 'grab', side='both'); m.event(2.08, 'release', side='both')
    for t in (0.55, 2.05):
        m.pose(t, dict(STAND, spine=(lean * 0.6, 0, 0), chest=(lean * 0.3, 0, 0), head=(-lean * 0.4, 0, 0)))
        m.hips(t, loc=(0, (0.05 if direction < 0 else 0.07) + (yfinal if t > 1 else 0.0) * 0, -0.04), rot=(lean * 0.4, 0, 0))
    m.face(0.5, 'determined', 0.3)
    # passi alternati: ogni piede fa due passi uguali e alla fine i piedi sono di nuovo affiancati
    a = {s: ctx.ankle[s] for s in 'LR'}
    pos = {s: a[s].y for s in 'LR'}
    for s in 'LR':
        m.foot(0.0, s, (a[s].x, pos[s], a[s].z), 0, 0, 1.0)
    order = ['L', 'R', 'L', 'R']
    for k, s in enumerate(order):
        t0 = 0.70 + 0.32 * k
        target = a[s].y + yfinal * (0.5 if k < 2 else 1.0)
        m.foot(t0, s, (a[s].x, pos[s], a[s].z), 0, 0, 1.0)
        m.foot(t0 + 0.13, s, (a[s].x, (pos[s] + target) / 2, a[s].z + 0.045), 0, -6 if direction < 0 else 6, 1.0)
        m.foot(t0 + 0.26, s, (a[s].x, target, a[s].z), 0, 0, 1.0)
        pos[s] = target
    for s in 'LR':
        m.foot(2.7, s, (a[s].x, pos[s], a[s].z), 0, 0, 1.0)
    stand(m, 2.7, ctx, hands=False, feet=False, y=0.0)
    m.params = dict(box=tuple(box), size=tuple(size), dist=dist)
    return m


def push(ctx, box=(0.0, -0.42, 0.0), size=(0.30, 0.30, 0.40)):
    return _push_pull(ctx, 'push', -1, box=box, size=size)


def pull(ctx, box=(0.0, -0.42, 0.0), size=(0.30, 0.30, 0.40)):
    return _push_pull(ctx, 'pull', +1, box=box, size=size)


def sit(ctx, height=CHAIR_H):
    m = Motion('sit', 1.8, 'interactions', end='chair', description='si siede su una seduta alle sue spalle')
    stand(m, 0.0, ctx)
    hz = height + 0.055 - C.J['hips'][2]
    m.pose(0.35, dict(STAND, spine=(10, 0, 0), chest=(6, 0, 0), head=(14, 0, 0)))
    m.hips(0.35, loc=(0, 0.02, -0.03), rot=(6, 0, 0))
    m.pose(0.95, dict(STAND, spine=(26, 0, 0), chest=(12, 0, 0), head=(-14, 0, 0), upper_arm=(30, 0, -10), forearm=(30, 0, 0)))
    m.hips(0.95, loc=(0, 0.10, hz + 0.02), rot=(22, 0, 0))
    m.hips(1.12, loc=(0, 0.125, hz - 0.006), rot=(8, 0, 0), mode='slow')
    m.scale(1.12, 'spine', (1.03, 0.95, 1.03), 'slow')
    m.hips(1.35, loc=(0, 0.125, hz), rot=(0, 0, 0)); m.scale(1.4, 'spine', (1, 1, 1))
    knee_top = lambda s: (0.135 * (1 if s == 'L' else -1), -0.07, height + 0.08)
    for s in 'LR':
        m.hand(0.0, s, ctx.wrist[s], None, 0.0); m.hand(1.05, s, ctx.wrist[s], None, 0.0)
        m.hand(1.5, s, knee_top(s), hand_orient(ctx, s, (0, -1.0, -0.3), (0, 0, -1)), 1.0)
        m.hand(1.8, s, knee_top(s), hand_orient(ctx, s, (0, -1.0, -0.3), (0, 0, -1)), 1.0)
    m.pose(1.5, dict(STAND, spine=(-2, 0, 0), chest=(0, 0, 0), head=(0, 0, 0)))
    m.pose(1.8, dict(STAND, spine=(-2, 0, 0), chest=(0, 0, 0), head=(-2, 0, 0)))
    m.hand_shape(1.5, 'both', 'flat')
    m.face(1.4, 'happy', 0.3, intensity=0.6)
    m.plant_feet(0.0); m.plant_feet(1.8)
    m.params = dict(height=height)
    return m


def stand_up(ctx, height=CHAIR_H):
    m = Motion('stand_up', 1.7, 'interactions', start='chair', description='si alza dalla seduta spingendo sulle ginocchia')
    hz = height + 0.055 - C.J['hips'][2]
    knee_top = lambda s: (0.135 * (1 if s == 'L' else -1), -0.07, height + 0.08)
    m.pose(0.0, dict(STAND, spine=(-2, 0, 0), chest=(0, 0, 0), head=(-2, 0, 0)))
    m.hand_shape(0.0, 'both', 'flat'); m.hips(0.0, loc=(0, 0.125, hz), rot=(0, 0, 0), scale=(1, 1, 1))
    for b in ('spine', 'chest', 'head'):
        m.scale(0.0, b, (1, 1, 1))
    m.plant_feet(0.0)
    for s in 'LR':
        rot = hand_orient(ctx, s, (0, -1.0, -0.3), (0, 0, -1))
        m.hand(0.0, s, knee_top(s), rot, 1.0)
        m.hand(0.55, s, knee_top(s), rot, 1.0)
        m.hand(1.0, s, ctx.wrist[s], None, 0.0)
    m.pose(0.45, dict(STAND, spine=(28, 0, 0), chest=(14, 0, 0), head=(-16, 0, 0)))
    m.hips(0.45, loc=(0, 0.10, hz + 0.01), rot=(24, 0, 0))
    m.pose(0.9, dict(STAND, spine=(16, 0, 0), chest=(8, 0, 0), head=(-6, 0, 0)))
    m.hips(0.9, loc=(0, 0.05, -0.06), rot=(14, 0, 0))
    m.hips(1.25, loc=(0, 0.0, 0.008), rot=(-2, 0, 0))
    m.face(0.3, 'determined', 0.3, intensity=0.5); m.face(1.2, 'neutral', 0.3)
    stand(m, 1.7, ctx, hands=False)
    m.params = dict(height=height)
    return m


def get_up(ctx):
    m = Motion('get_up', 2.5, 'interactions', start='floor', description='si rialza da terra passando per l\'accovacciata')
    _floor_pose(m, 0.0, ctx, head=(5, 0, 0))
    for b in ('spine', 'chest', 'head'):
        m.scale(0.0, b, (1, 1, 1))
    m.hand_shape(0.0, 'both', 'relax')
    hx, hy, hz = FLOOR_HIPS
    a = {s: ctx.ankle[s] for s in 'LR'}
    yf = floor_feet_y() + 0.02           # dove finiranno i piedi (e il personaggio in piedi)
    # piega le ginocchia: i piedi tornano verso il sedere
    for s in 'LR':
        m.foot(0.5, s, (a[s].x * 1.1, yf + 0.04, a[s].z), 0, 0, 1.0)
        m.hand(0.5, s, (0.17 * (1 if s == 'L' else -1), hy + 0.02, 0.035), hand_orient(ctx, s, (0.2 * (1 if s == 'L' else -1), -0.4, -1.0), (0, 0, -1)), 1.0)
    m.hips(0.5, loc=(hx, hy, hz), rot=(4, 0, 0))
    m.pose(0.5, dict(STAND, spine=(22, 0, 0), chest=(10, 0, 0), head=(-6, 0, 0)))
    # spinge con le mani e porta il peso sui piedi (accovacciato)
    m.hips(1.05, loc=(0, yf + 0.06, -0.20), rot=(30, 0, 0))
    m.pose(1.05, dict(STAND, spine=(30, 0, 0), chest=(16, 0, 0), head=(-14, 0, 0)))
    for s in 'LR':
        m.hand(0.95, s, (0.15 * (1 if s == 'L' else -1), yf - 0.10, 0.05), hand_orient(ctx, s, (0, -0.6, -1.0), (0, 0, -1)), 0.8)
        m.hand(1.4, s, ctx.wrist[s], None, 0.0)
        m.foot(1.05, s, (a[s].x, yf + a[s].y * 0 + 0.0, a[s].z), 0, 0, 1.0)
    m.hips(1.6, loc=(0, yf + 0.02, -0.12), rot=(20, 0, 0))
    m.pose(1.6, dict(STAND, spine=(20, 0, 0), chest=(10, 0, 0), head=(-8, 0, 0)))
    m.hips(2.05, loc=(0, yf, 0.008), rot=(-2, 0, 0))
    m.face(0.3, 'determined', 0.3, intensity=0.5); m.face(2.0, 'neutral', 0.3)
    # alla fine il personaggio e' in piedi sopra i piedi: la radice avanza fino a li'
    m.root(0.0, 0, 0, 0); m.root(1.6, 0, 0, 0); m.root(2.5, 0, yf, 0)
    m.pose(2.5, STAND); m.hand_shape(2.5, 'both', 'relax')
    m.hips(2.5, loc=(0, 0, 0), rot=(0, 0, 0))
    for s in 'LR':
        m.foot(2.5, s, (a[s].x, a[s].y + yf, a[s].z), 0, 0, 1.0)
    return m


# ================================================================== registro
def walk(ctx):
    return P.Gait('walk')


def run(ctx):
    return P.Gait('run')


def sprint(ctx):
    return P.Gait('sprint')


LIBRARY = {
    'locomotion': ['idle', 'walk', 'run', 'jump', 'sprint', 'turn', 'stop'],
    'reactions': ['surprise', 'shock', 'fear', 'confusion', 'happiness', 'anger', 'sadness'],
    'comedy': ['fall', 'trip', 'slip', 'dance', 'celebrate', 'facepalm', 'look_around', 'exaggerated_reaction'],
    'interactions': ['point', 'wave', 'pick_up', 'throw', 'push', 'pull', 'sit', 'stand_up'],
}
EXTRA = ['get_up']
FACTORIES = {n: globals()[n] for cat in LIBRARY.values() for n in cat}
FACTORIES['get_up'] = get_up


def names():
    return [n for cat in LIBRARY.values() for n in cat]


def make(name, ctx, **params):
    name = C.ALIASES.get(name, name)
    if name not in FACTORIES:
        raise KeyError('movimento sconosciuto: %s (disponibili: %s)' % (name, ', '.join(names())))
    return FACTORIES[name](ctx, **params)
