"""Scheletro e controlli.

Gerarchia umanoide compatibile con Mixamo e CMU (Hips > Spine > Spine2 > Neck > Head, braccia con clavicola, gambe con dita
del piede), piu' le parti cartoon: ciuffo a catena, occhi, palpebre, sopracciglia, osso «face» con le proprieta' della bocca.
Le ossa che deformano sono 63; quelle di controllo (IK, poli, bersaglio degli occhi, face) non deformano.

IK/FK: ogni braccio e ogni gamba ha un vincolo IK (con polo) e una «copia rotazione» per mano/piede; l'influenza viene da una
proprieta' sull'osso root (ik_arm.L, ik_leg.R, ...; 0 = FK, 1 = IK). La pipeline Python scrive sempre l'FK (calcola da sola l'IK
in modo analitico e lo «cuoce»), cosi' le animazioni si mescolano e si trasferiscono senza sorprese; l'IK del rig resta per chi
anima a mano in Blender.
"""
import math
import bpy
from mathutils import Vector, Matrix, Quaternion, Euler

from .. import config as C
from . import geometry as G
from . import model as M
from . import facial as F

FWD = (0.0, -1.0, 0.0)
UPV = (0.0, 0.0, 1.0)


def _mx(v):
    return Vector((-v[0], v[1], v[2]))


def curl_joints():
    """giunti del ciuffo a riposo (dritto)."""
    base, L = M.curl_straight()
    nb = C.CURL['bones']
    return [base + Vector((0.0, 0.0, L * k / nb)) for k in range(nb + 1)]


def curl_curve_joints():
    """giunti lungo la curva del «?» (la posa di base)."""
    samples, L = G.polyline_sample(C.CURL['pts'], 0.0005)
    nb = C.CURL['bones']
    pts = []
    for k in range(nb + 1):
        t = L * k / nb
        best = min(samples, key=lambda st: abs(st[1] - t))
        pts.append(best[0])
    return pts


def bone_specs():
    J = {k: Vector(v) for k, v in C.J.items()}
    B = []

    def add(name, head, tail, parent=None, z=FWD, deform=True, connect=False, inherit='FULL'):
        B.append(dict(name=name, head=Vector(head), tail=Vector(tail), parent=parent, z=Vector(z), deform=deform,
                      connect=connect, inherit=inherit))

    add('root', (0, 0, 0), (0, 0.22, 0), None, UPV, deform=False)
    add('hips', J['hips'], J['spine'], 'root')
    add('spine', J['spine'], J['chest'], 'hips', connect=True)
    add('chest', J['chest'], J['neck'], 'spine', connect=True, inherit='NONE')   # niente taglio (shear) dallo squash della colonna
    add('neck', J['neck'], J['head'], 'chest', connect=True, inherit='NONE')
    add('head', J['head'], J['head_top'], 'neck', connect=True)
    add('face', (0, -0.06, 0.815), (0, -0.11, 0.815), 'head', UPV, deform=False)
    cj = curl_joints()
    for k in range(len(cj) - 1):
        add('curl.%02d' % (k + 1), cj[k], cj[k + 1], 'head' if k == 0 else 'curl.%02d' % k, FWD, connect=k > 0)
    add('eye_target', (0, -1.2, 0.80), (0, -1.26, 0.80), 'root', UPV, deform=False)
    # lato sinistro (poi specchiato)
    side = []

    def adds(*a, **k):
        side.append((a, k))

    E = F.eye_center('L')
    adds('eye.L', E, E + Vector((0, -0.05, 0)), 'head', UPV)
    adds('lid_up.L', E, E + Vector((0, -0.04, 0)), 'head', UPV)
    adds('lid_low.L', E, E + Vector((0, -0.035, 0)), 'head', UPV)
    adds('brow.L', Vector(C.HEAD_C), F.brow_center('L'), 'head', UPV)
    W, d, n, f = M.hand_frame('L')
    adds('shoulder.L', J['clav'], J['shoulder'], 'chest', FWD, inherit='NONE')
    adds('upper_arm.L', J['shoulder'], J['elbow'], 'shoulder.L', FWD, connect=True)
    adds('forearm.L', J['elbow'], J['wrist'], 'upper_arm.L', FWD, connect=True)
    adds('hand.L', J['wrist'], J['wrist'] + d * C.HAND['len'], 'forearm.L', FWD, connect=True)
    for name, (pts, r) in M.finger_chains('L').items():
        for i in range(len(pts) - 1):
            adds('%s.%02d.L' % (name, i + 1), pts[i], pts[i + 1], 'hand.L' if i == 0 else '%s.%02d.L' % (name, i), n, connect=i > 0)
    adds('thigh.L', J['hip'], J['knee'], 'hips', FWD, inherit='NONE')
    adds('shin.L', J['knee'], J['ankle'], 'thigh.L', FWD, connect=True)
    adds('foot.L', J['ankle'], J['ball'], 'shin.L', UPV, connect=True)
    adds('toe.L', J['ball'], J['toe'], 'foot.L', UPV, connect=True)
    adds('hand_ik.L', J['wrist'], J['wrist'] + d * C.HAND['len'], 'root', FWD, deform=False)
    adds('elbow_pole.L', J['elbow'] + Vector((0.05, 0.30, 0)), J['elbow'] + Vector((0.05, 0.34, 0)), 'root', UPV, deform=False)
    adds('foot_ik.L', J['ankle'], J['ball'], 'root', UPV, deform=False)
    adds('knee_pole.L', J['knee'] + Vector((0, -0.35, 0)), J['knee'] + Vector((0, -0.39, 0)), 'root', UPV, deform=False)
    for (a, k) in side:
        add(*a, **k)
    for (a, k) in side:
        name, head, tail, parent = a[0], a[1], a[2], a[3]
        z = a[4] if len(a) > 4 else k.get('z', FWD)
        kk = dict(k); kk.pop('z', None)
        add(name.replace('.L', '.R'), _mx(head), _mx(tail), parent.replace('.L', '.R') if parent else None, _mx(z), **kk)
    return B


def build_armature(name, collection):
    arm = bpy.data.armatures.new(name + '_rig')
    arm.display_type = 'STICK'
    ob = bpy.data.objects.new(name + '_rig', arm)
    collection.objects.link(ob)
    ob.show_in_front = True
    vl = bpy.context.view_layer
    prev = vl.objects.active
    vl.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    specs = bone_specs()
    for s in specs:
        eb = arm.edit_bones.new(s['name'])
        eb.head = s['head']; eb.tail = s['tail']
        eb.align_roll(s['z'])
        eb.use_deform = s['deform']
    for s in specs:
        eb = arm.edit_bones[s['name']]
        if s['parent']:
            eb.parent = arm.edit_bones[s['parent']]
            eb.use_connect = s['connect']
        eb.inherit_scale = s['inherit']
    bpy.ops.object.mode_set(mode='OBJECT')
    vl.objects.active = prev
    for pb in ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    _controls(ob)
    return ob


def _prop(pb, key, val, lo=0.0, hi=1.0):
    pb[key] = float(val)
    try:
        pb.id_properties_ui(key).update(min=lo, max=hi, soft_min=lo, soft_max=hi)
    except Exception:
        pass


def _driver(owner, path, arm_ob, prop_path, index=-1):
    fc = owner.driver_add(path) if index < 0 else owner.driver_add(path, index)
    drv = fc.driver
    drv.type = 'AVERAGE'
    var = drv.variables.new()
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = arm_ob
    var.targets[0].data_path = prop_path
    return fc


def _controls(ob):
    P = ob.pose.bones
    root = P['root']
    for s in ('L', 'R'):
        _prop(root, 'ik_arm.' + s, 0.0); _prop(root, 'ik_leg.' + s, 0.0)
    _prop(root, 'eyes_track', 0.0)
    face = P['face']
    for k in C.FACE_PROPS:
        _prop(face, k, 0.55 if k == 'pupil' else 0.0)
    for s in ('L', 'R'):
        for chain, tgt, pole, end, key in (('forearm', 'hand_ik', 'elbow_pole', 'hand', 'ik_arm'),
                                           ('shin', 'foot_ik', 'knee_pole', 'foot', 'ik_leg')):
            pb = P['%s.%s' % (chain, s)]
            c = pb.constraints.new('IK'); c.name = 'IK'
            c.target = ob; c.subtarget = '%s.%s' % (tgt, s)
            c.pole_target = ob; c.pole_subtarget = '%s.%s' % (pole, s)
            c.chain_count = 2; c.use_tail = True; c.use_stretch = False
            _driver(c, 'influence', ob, 'pose.bones["root"]["%s.%s"]' % (key, s))
            e = P['%s.%s' % (end, s)]
            c2 = e.constraints.new('COPY_ROTATION'); c2.name = 'IK_rot'
            c2.target = ob; c2.subtarget = '%s.%s' % (tgt, s)
            _driver(c2, 'influence', ob, 'pose.bones["root"]["%s.%s"]' % (key, s))
        eye = P['eye.' + s]
        c3 = eye.constraints.new('DAMPED_TRACK'); c3.name = 'look'
        c3.target = ob; c3.subtarget = 'eye_target'; c3.track_axis = 'TRACK_Y'
        _driver(c3, 'influence', ob, 'pose.bones["root"]["eyes_track"]')


def _eval_dirs(ob, names):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    return {n: (oe.pose.bones[n].tail - oe.pose.bones[n].head).normalized() for n in names}


def calibrate_poles(ob):
    """sceglie l'angolo del polo che lascia la catena ferma quando il bersaglio IK e' nella posa di riposo."""
    P = ob.pose.bones
    root = P['root']
    result = {}
    for s in ('L', 'R'):
        for chain, upper, key in (('forearm', 'upper_arm', 'ik_arm'), ('shin', 'thigh', 'ik_leg')):
            names = ['%s.%s' % (upper, s), '%s.%s' % (chain, s)]
            rest = {n: (ob.data.bones[n].tail_local - ob.data.bones[n].head_local).normalized() for n in names}
            root['%s.%s' % (key, s)] = 1.0
            best = None
            for ang in (-180, -90, 0, 90):
                P[names[1]].constraints['IK'].pole_angle = math.radians(ang)
                dirs = _eval_dirs(ob, names)
                err = sum(math.degrees(dirs[n].angle(rest[n])) for n in names)
                if best is None or err < best[0]:
                    best = (err, ang)
            # rifinitura fine attorno al migliore
            for ang in [best[1] + d for d in range(-20, 21, 1)]:
                P[names[1]].constraints['IK'].pole_angle = math.radians(ang)
                dirs = _eval_dirs(ob, names)
                err = sum(math.degrees(dirs[n].angle(rest[n])) for n in names)
                if err < best[0]:
                    best = (err, ang)
            P[names[1]].constraints['IK'].pole_angle = math.radians(best[1])
            root['%s.%s' % (key, s)] = 0.0
            result['%s.%s' % (chain, s)] = best
    bpy.context.view_layer.update()
    return result


# ------------------------------------------------------------------ pose del ciuffo
def curl_pose_targets():
    """forme bersaglio del ciuffo: liste di punti (stesso numero dei giunti)."""
    rest = curl_joints()
    q = curl_curve_joints()
    base = rest[0]
    seg = [(rest[i + 1] - rest[i]).length for i in range(len(rest) - 1)]
    out = {'default': q}
    # esclamazione: dritto in su, appena in avanti (si legge come «!»)
    pts = [base]
    for L in seg:
        pts.append(pts[-1] + Vector((0.0, -0.08, 1.0)).normalized() * L)
    out['exclaim'] = pts
    # domanda: il gancio del «?» si chiude di piu'
    pts = [base, q[1]]
    d = (q[1] - q[0]).normalized()
    for i in range(1, len(seg)):
        d0 = (q[i + 1] - q[i]).normalized(); dp = (q[i] - q[i - 1]).normalized()
        ang = math.atan2(dp.cross(d0).y, dp.dot(d0)) * 1.35
        d = (Quaternion((0, 1, 0), ang) @ d).normalized()
        pts.append(pts[-1] + d * seg[i])
    out['question'] = pts
    # giu': il ciuffo cade di lato (verso la destra del personaggio) e si apre
    pts = [base]
    d = Vector((-0.45, 0.04, 0.89)).normalized()
    for i, L in enumerate(seg):
        pts.append(pts[-1] + d * L)
        d = (Quaternion((0, 1, 0), math.radians(-15)) @ d).normalized()
    out['droop'] = pts
    return out


def chain_basis_for_points(ob, names, targets, plane_axis=(0.0, 1.0, 0.0)):
    """rotazioni locali (quaternioni) che portano la catena `names` sui punti `targets` (spazio armatura).
    Le rotazioni sono attorno all'asse del piano del ciuffo (Y): cosi' le ossa vicine non si torcono tra loro
    (con la rotazione minima, un segmento che passa da giu' a su si girerebbe di 180 gradi su se stesso)."""
    bones = ob.data.bones
    ax = Vector(plane_axis).normalized()
    out = {}
    parent_pose = None
    parent_rest = None
    for i, n in enumerate(names):
        b = bones[n]
        R = b.matrix_local.copy()
        if parent_pose is None:
            M0 = R.copy()                       # il genitore (testa) e' a riposo
        else:
            M0 = parent_pose @ (parent_rest.inverted() @ R)
        h = M0.translation.copy()
        cur = (M0.to_3x3() @ Vector((0, 1, 0))).normalized()
        want = (Vector(targets[i + 1]) - Vector(targets[i])).normalized()
        c2 = (cur - ax * cur.dot(ax)); w2 = (want - ax * want.dot(ax))
        if c2.length > 1e-6 and w2.length > 1e-6:
            c2.normalize(); w2.normalize()
            ang = math.atan2(c2.cross(w2).dot(ax), c2.dot(w2))
            q = Quaternion(ax, ang)
        else:
            q = Quaternion()
        cur2 = q @ cur
        q = cur2.rotation_difference(want) @ q            # piccola correzione fuori dal piano
        Mk = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ M0
        basis = M0.inverted() @ Mk
        out[n] = basis.to_quaternion()
        parent_pose, parent_rest = Mk, R
    return out


def curl_poses(ob):
    names = ['curl.%02d' % (k + 1) for k in range(C.CURL['bones'])]
    return {k: chain_basis_for_points(ob, names, pts) for k, pts in curl_pose_targets().items()}


def deform_bones(ob):
    return [b.name for b in ob.data.bones if b.use_deform]
