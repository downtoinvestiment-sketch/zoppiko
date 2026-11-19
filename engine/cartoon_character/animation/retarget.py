"""Retargeting di animazioni esterne (BVH, FBX) sul personaggio.

Metodo: trasferimento delle rotazioni nel mondo con allineamento delle pose di riposo.
Per ogni osso mappato: D(t) = rotazione dell'osso sorgente rispetto al suo riposo (nel mondo); l'osso del personaggio prende
D(t) applicata al suo riposo, dopo aver allineato le direzioni di riposo misurate tra le giunture (cosi' una sorgente in
T-pose e il nostro rig in A-pose combaciano, e le code arbitrarie delle ossa importate non contano). Le ossa intermedie
della sorgente (Spine1 di Mixamo, Neck1 di CMU...) non servono: conta l'orientamento nel mondo. La sorgente viene girata
perche' guardi -Y; il bacino segue il punto tra le anche della sorgente in scala (rapporto tra le gambe); il movimento a
terra e la direzione del corpo passano alla radice (smussati), cosi' la clip si concatena alle altre; alla fine il blocco
dei piedi del compositore toglie lo scivolamento residuo dovuto alle proporzioni diverse.

Formati: BVH (importatore di Blender), FBX (importatore di Blender: Mixamo, Rokoko e altri). Nomi: mappe pronte per Mixamo e
CMU (config.MIXAMO, config.CMU) piu' una mappatura automatica per parole chiave.
"""
import math
import os
import re
import bpy
from mathutils import Vector, Matrix, Quaternion

from .. import config as C
from ..character.skeleton import BonePose, slerp, euler_q, mirror_euler
from .clip import Frame, HAND_SHAPES
from .blending import yaw_of
from . import collide as CL

KEYWORDS = [  # (osso nostro, regex sul nome normalizzato della sorgente)
    ('hips', r'^(hips|pelvis|hip)$'),          # niente «root»: negli scheletri Unreal e' l'osso a terra
    ('spine', r'^(spine|lowerback|spine0|spine_01|abdomen)$'),
    ('chest', r'^(spine2|spine1|chest|upperchest|spine_03|spine_02)$'),
    ('neck', r'^(neck|neck_01)$'),
    ('head', r'^head$'),
]
SIDE_WORDS = [  # (parte, regex)
    ('shoulder', r'(shoulder|clavicle|collar)'), ('upper_arm', r'(upperarm|arm)$'), ('forearm', r'(forearm|lowerarm|elbow)'),
    ('hand', r'(hand|wrist)$'), ('thigh', r'(upleg|thigh|upperleg|hip)$'), ('shin', r'(leg|shin|calf|knee|lowerleg)$'),
    ('foot', r'(foot|ankle)$'), ('toe', r'(toebase|toe|ball)$'),
]


CORE = ('hips', 'spine', 'chest', 'neck', 'head', 'upper_arm.L', 'forearm.L', 'hand.L', 'upper_arm.R', 'forearm.R', 'hand.R',
        'thigh.L', 'shin.L', 'foot.L', 'thigh.R', 'shin.R', 'foot.R')
REQUIRED = ('hips', 'spine', 'chest', 'head', 'upper_arm.L', 'forearm.L', 'upper_arm.R', 'forearm.R', 'thigh.L', 'shin.L',
            'foot.L', 'thigh.R', 'shin.R', 'foot.R')

# direzione di riposo di ogni osso = dalla sua giuntura a quella del figlio (le code delle ossa importate sono arbitrarie:
# BVH e FBX salvano giunture, non ossa). Le ossa finali prendono l'allineamento del genitore.
CHAIN = {'spine': 'chest', 'chest': 'neck', 'neck': 'head'}
LEAF = {'head': 'neck'}
for _s in 'LR':
    CHAIN.update({'shoulder.' + _s: 'upper_arm.' + _s, 'upper_arm.' + _s: 'forearm.' + _s, 'forearm.' + _s: 'hand.' + _s,
                  'thigh.' + _s: 'shin.' + _s, 'shin.' + _s: 'foot.' + _s, 'foot.' + _s: 'toe.' + _s,
                  'thumb.01.' + _s: 'thumb.02.' + _s})
    LEAF.update({'hand.' + _s: 'forearm.' + _s, 'toe.' + _s: 'foot.' + _s, 'thumb.02.' + _s: 'thumb.01.' + _s})
    for _f in ('f_index', 'f_middle', 'f_ring'):
        CHAIN[_f + '.01.' + _s] = _f + '.02.' + _s
        CHAIN[_f + '.02.' + _s] = _f + '.03.' + _s
        LEAF[_f + '.03.' + _s] = _f + '.02.' + _s


PREFIX = r'^(mixamorig\d*[_]?|bip0*1[_ ]?|character1_|cc_base_)'


def normalize(name):
    n = name.split(':')[-1]
    n = re.sub(PREFIX, '', n, flags=re.I)
    return n.replace(' ', '').replace('.', '').replace('-', '').lower()


SIDE_RX = [
    (r'^(left|right)[ _.\-]?(.+)$', re.I, 1, 2),
    (r'^(.+?)[ _.\-]?(left|right)$', re.I, 2, 1),
    (r'^([LR])(?=[A-Z0-9 _.\-])[ _.\-]?(.+)$', 0, 1, 2),      # LHipJoint, L Hand, L_hand (L maiuscola)
    (r'^([lr])[ _.\-](.+)$', 0, 1, 2),                          # l_hand, r.thigh
    (r'^(.+?)[ _.\-]([LRlr])$', 0, 2, 1),                       # hand_l, Hand.L, upperarm_r
]


def side_split(name):
    """(lato 'L'/'R' o None, resto del nome normalizzato) a partire dal nome originale."""
    n = name.split(':')[-1]
    n = re.sub(PREFIX, '', n, flags=re.I)
    for rx, flags, gs, gr in SIDE_RX:
        m = re.match(rx, n, flags)
        if m:
            side = m.group(gs).lower()
            return ('L' if side.startswith('l') else 'R'), normalize(m.group(gr))
    return None, normalize(n)


def auto_map(src_names):
    """mappa automatica: prima le tabelle note (Mixamo, CMU: vince quella che copre piu' ossa principali, perche' CMU e
    Mixamo hanno molti nomi in comune), poi le parole chiave. Restituisce {osso nostro: osso sorgente}."""
    norm = {normalize(s): s for s in src_names}
    best = None
    for table in (C.MIXAMO, C.CMU):
        hits = {ours: norm[normalize(theirs)] for ours, theirs in table.items() if normalize(theirs) in norm}
        score = (sum(1 for b in CORE if b in hits), len(hits))
        if len(hits) >= 15 and (best is None or score > best[0]):
            best = (score, hits)
    if best is not None:
        return best[1]
    out = {}
    centre = {}
    for orig in src_names:
        side, core = side_split(orig)
        if side:
            for part, rx in SIDE_WORDS:
                if re.search(rx, core):
                    if part == 'upper_arm' and ('fore' in core or 'lower' in core):
                        continue
                    if part == 'thigh' and core.startswith('hipjoint'):
                        continue
                    out.setdefault('%s.%s' % (part, side), orig)
                    break
        else:
            for ours, rx in KEYWORDS:
                if re.match(rx, core):
                    centre.setdefault(ours, []).append(orig)
                    break
    for ours, cands in centre.items():
        # il petto e' l'osso della colonna piu' in alto (spine_03 piuttosto che spine_02)
        out[ours] = sorted(cands, key=lambda c: normalize(c))[-1] if ours == 'chest' else cands[0]
    return out


def import_file(path, scale=1.0):
    """importa BVH o FBX; restituisce l'oggetto armatura importato."""
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext == '.bvh':
        bpy.ops.import_anim.bvh(filepath=path, global_scale=scale, frame_start=1, use_fps_scale=False,
                                update_scene_fps=False, update_scene_duration=False, rotate_mode='NATIVE')
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=path, use_anim=True, ignore_leaf_bones=True, global_scale=scale)
    else:
        raise ValueError('formato non supportato: ' + ext)
    new = [o for o in bpy.data.objects if o not in before]
    arms = [o for o in new if o.type == 'ARMATURE']
    if not arms:
        raise RuntimeError('nessuna armatura nel file ' + path)
    return arms[0], new


def action_range(arm):
    ad = arm.animation_data
    if not ad or not ad.action:
        return 1, 1
    r = ad.action.frame_range
    return int(r[0]), int(r[1])


class SampledClip:
    """clip fatta di pose campionate (risultato del retargeting): si usa come ogni altro movimento."""
    kind = 'sampled'
    loop = False
    start_state = 'stand'
    end_state = 'stand'
    category = 'mocap'

    def __init__(self, name, poses, contacts, fps):
        self.name = name; self.poses = poses; self.contacts = contacts; self.fps = fps
        self.duration = (len(poses) - 1) / fps
        self.events = []
        self.description = 'animazione importata (%d fotogrammi)' % len(poses)

    def evaluate(self, t, ctx, params=None, t_prev=None):
        x = max(0.0, min(len(self.poses) - 1, t * self.fps))
        i = int(x); f = x - i
        a = self.poses[i]; b = self.poses[min(i + 1, len(self.poses) - 1)]
        pose = {}
        for n in set(a) | set(b):
            pa = a.get(n) or BonePose(); pb = b.get(n) or BonePose()
            pose[n] = BonePose(pa.loc.lerp(pb.loc, f), slerp(pa.rot, pb.rot, f), pa.scl.lerp(pb.scl, f))
        fr = Frame(pose)
        k = min(len(self.contacts) - 1, int(round(x)))
        fr.contacts = dict(self.contacts[k])
        return fr


def _front_yaw(left):
    """yaw (come blending.yaw_of: 0 = guarda -Y) di un corpo con il fianco sinistro in direzione `left`."""
    l = Vector((left.x, left.y, 0.0))
    if l.length < 1e-9:
        return 0.0
    f = l.normalized().cross(Vector((0.0, 0.0, 1.0)))
    return math.atan2(f.x, -f.y)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _smooth(vals, half):
    """media mobile centrata con finestra simmetrica (ai bordi si restringe: il primo e l'ultimo valore restano esatti)."""
    n = len(vals); out = []
    for i in range(n):
        h = min(half, i, n - 1 - i)
        out.append(sum(vals[i - h:i + h + 1]) / (2 * h + 1))
    return out


def _leg_length(heads):
    tot = 0.0
    for s in 'LR':
        tot += (heads['shin.' + s] - heads['thigh.' + s]).length + (heads['foot.' + s] - heads['shin.' + s]).length
    return tot / 2


def _alignments(mapping, rest_s, rest_t):
    """rotazione che porta la direzione di riposo nostra su quella della sorgente, osso per osso."""
    align = {}
    for o in mapping:
        if o == 'hips':
            align[o] = Quaternion()                     # bacino: entrambi in piedi e rivolti a -Y (dopo la correzione)
            continue
        c = CHAIN.get(o)
        if c and c in mapping:
            dt = rest_t[c].translation - rest_t[o].translation
            ds = rest_s[c].translation - rest_s[o].translation
            if dt.length > 1e-5 and ds.length > 1e-5:
                align[o] = dt.rotation_difference(ds)
    for o in mapping:
        if o in align:
            continue
        p = LEAF.get(o)
        if p in align:
            align[o] = align[p].copy()
        else:                                            # ultima risorsa: l'asse Y delle ossa
            ys = rest_s[o].to_3x3().normalized() @ Vector((0, 1, 0))
            yt = rest_t[o].to_3x3().normalized() @ Vector((0, 1, 0))
            align[o] = yt.rotation_difference(ys)
    return align


def retarget(src, ctx, mapping=None, fps=C.FPS, frames=None, name='mocap', root_motion=True, in_place=False,
             skip_tpose=True, hands='relax', smooth_s=0.25, clearance=True):
    """campiona l'armatura sorgente (con la sua Action) e restituisce (SampledClip, mappatura) per il personaggio.

    - la sorgente viene girata perche' guardi -Y come il personaggio (lo dicono i fianchi nella posa di riposo);
    - allineamento delle pose di riposo con le direzioni tra le giunture (T-pose sorgente, A-pose nostra);
    - scala = rapporto tra le lunghezze delle gambe; il bacino segue il punto tra le anche della sorgente;
    - la clip parte dall'origine guardando -Y; la radice segue il bacino a terra (posizione e direzione, smussate):
      cosi' la clip si concatena alle altre e chi viene dopo parte dalla direzione giusta;
    - skip_tpose: salta il primo fotogramma se e' una posa a T aggiunta (i BVH CMU di cgspeed ne hanno una);
    - hands: forma delle dita non mappate (i BVH CMU non hanno le dita);
    - clearance: mani e avambracci fuori da testa, busto e gambe (il nostro corpo e' piu' tondo di quello catturato)."""
    sk = ctx.sk
    names_src = [b.name for b in src.data.bones]
    mapping = dict(mapping or auto_map(names_src))
    missing = [b for b in REQUIRED if b not in mapping]
    if missing:
        raise RuntimeError('mappatura incompleta, mancano: %s (trovate: %s)' % (missing, sorted(mapping)))
    sc = bpy.context.scene
    f0, f1 = frames or action_range(src)
    src_fps = sc.render.fps / sc.render.fps_base
    W = src.matrix_world.copy()
    rest_s = {o: W @ src.data.bones[s].matrix_local for o, s in mapping.items()}
    yaw_rest = _front_yaw(rest_s['thigh.L'].translation - rest_s['thigh.R'].translation)
    Q = Matrix.Rotation(-yaw_rest, 4, 'Z')
    rest_s = {o: Q @ M for o, M in rest_s.items()}
    rest_t = {o: sk.rest[o] for o in mapping}
    align = {o: q.to_matrix() for o, q in _alignments(mapping, rest_s, rest_t).items()}
    rs3inv = {o: M.to_3x3().normalized().inverted() for o, M in rest_s.items()}
    rt3 = {o: M.to_3x3().normalized() for o, M in rest_t.items()}
    heads_s = {o: M.translation for o, M in rest_s.items()}
    heads_t = {o: sk.rest[o].translation for o in sk.names}
    k_scale = _leg_length(heads_t) / max(1e-9, _leg_length(heads_s))
    mid_t = (heads_t['thigh.L'] + heads_t['thigh.R']) / 2
    hip_off = mid_t - heads_t['hips']                   # dal bacino al punto tra le anche (riposo)

    def sample(fsrc):
        sc.frame_set(int(math.floor(fsrc)), subframe=fsrc - math.floor(fsrc))
        dg = bpy.context.evaluated_depsgraph_get()
        se = src.evaluated_get(dg)
        Ws = Q @ se.matrix_world
        return {o: Ws @ se.pose.bones[s].matrix for o, s in mapping.items()}

    if skip_tpose and f1 - f0 >= 2:
        a = sample(f0); b = sample(f0 + 1)
        jump = 0.0
        for o in a:
            ang = math.degrees(a[o].to_quaternion().rotation_difference(b[o].to_quaternion()).angle)
            jump = max(jump, min(ang, 360 - ang))
        if jump > 20.0:
            f0 += 1
    n_out = int((f1 - f0) / src_fps * fps + 1e-6) + 1
    curs = [sample(f0 + i * src_fps / fps) for i in range(n_out)]
    # bacino della sorgente: punto tra le anche (in scala) e direzione del corpo
    mids = [(c['thigh.L'].translation + c['thigh.R'].translation) / 2 * k_scale for c in curs]
    yaws = [_front_yaw(c['thigh.L'].translation - c['thigh.R'].translation) for c in curs]
    for i in range(1, len(yaws)):                        # continuita' (niente salti di 360 gradi)
        yaws[i] = yaws[i - 1] + _wrap(yaws[i] - yaws[i - 1])
    n0 = max(1, min(len(yaws), int(1.0 * fps)))         # direzione media del primo secondo (il bacino ruota a ogni passo)
    yaw0 = math.atan2(sum(math.sin(y) for y in yaws[:n0]), sum(math.cos(y) for y in yaws[:n0]))
    Z0 = Matrix.Rotation(-yaw0, 3, 'Z')
    m0 = Vector((mids[0].x, mids[0].y, 0.0))
    mids = [Z0 @ (m - m0) for m in mids]                 # la clip parte dall'origine guardando -Y
    yaws = [y - yaw0 for y in yaws]
    half = max(0, int(smooth_s * fps))
    rx = _smooth([m.x for m in mids], half); ry = _smooth([m.y for m in mids], half); ryaw = _smooth(yaws, half)
    hand_pose = {}
    if hands:
        for s in 'LR':
            for kname, v in HAND_SHAPES[hands].items():
                bn = '%s.%s' % (kname, s)
                if bn in sk.parent and bn not in mapping:
                    hand_pose[bn] = euler_q(v if s == 'L' else mirror_euler(v))
    poses = []
    for i, cur in enumerate(curs):
        pose = {}; mats = {}
        if root_motion and not in_place:
            pose['root'] = BonePose(loc=(rx[i], ry[i], 0.0), rot=Quaternion((0, 0, 1), ryaw[i]))
            target = mids[i].copy()
        elif in_place:
            pose['root'] = BonePose()
            target = Vector((mids[i].x - rx[i], mids[i].y - ry[i], mids[i].z))   # resta sul posto, con l'ondeggio
        else:
            pose['root'] = BonePose()
            target = mids[i].copy()
        for n in sk.names:
            if n == 'root':
                mats['root'] = sk.base_matrix('root', mats) @ pose['root'].matrix()
                continue
            if n in mapping:
                D = Z0 @ cur[n].to_3x3().normalized() @ rs3inv[n]
                R = D @ align[n] @ rt3[n]
                if n == 'hips':
                    bp = pose['hips'] = BonePose()
                    head = target - (R @ rt3['hips'].inverted()) @ hip_off
                    base = sk.base_matrix('hips', mats)
                    bp.loc = base.to_3x3().normalized().inverted() @ (head - base.translation)
                sk.set_world_rotation(pose, n, R, mats)
            else:
                if n in hand_pose:
                    pose[n] = BonePose(rot=hand_pose[n])
                base = sk.base_matrix(n, mats)
                bp = pose.get(n)
                mats[n] = base @ bp.matrix() if bp is not None else base.copy()
        poses.append(pose)
    fixes = CL.resolve_arms(ctx, poses) if clearance else 0
    contacts = detect_contacts(ctx, poses, fps)
    clip = SampledClip(name, poses, contacts, fps)
    clip.source = dict(frames=(f0, f1), fps=src_fps, scale=k_scale, yaw_rest=math.degrees(yaw_rest),
                       yaw_start=math.degrees(yaw0), arm_fixes=fixes)
    return clip, mapping


def detect_contacts(ctx, poses, fps, h=0.022, v=0.20):
    from .blending import root_matrix
    sk = ctx.sk
    out = []
    prev = None
    for pose in poses:
        M = sk.fk(pose)
        cur = {}
        for s in 'LR':
            Mf = M['foot.' + s]
            Rinv = ctx.foot_rest[s].inverted()
            heel = Mf @ (Rinv @ ctx.heel_off); ball = Mf @ (Rinv @ ctx.ball_off)
            cur[s] = (heel, ball)
        c = {}
        for s in 'LR':
            low = min(cur[s][0].z, cur[s][1].z)
            spd = 0.0
            if prev is not None:
                spd = max((cur[s][0] - prev[s][0]).length, (cur[s][1] - prev[s][1]).length) * fps
            c[s] = low < h and spd < v
        out.append(c)
        prev = cur
    # niente appoggi di un solo fotogramma
    for s in 'LR':
        for i in range(1, len(out) - 1):
            if out[i][s] and not out[i - 1][s] and not out[i + 1][s]:
                out[i][s] = False
    return out


def ground_offset(ctx, clip):
    """sposta in su/giu' il bacino perche' il piede piu' basso tocchi il pavimento (proporzioni diverse dalla sorgente)."""
    from .blending import root_matrix
    sk = ctx.sk
    lows = []
    for pose in clip.poses:
        M = sk.fk(pose)
        for s in 'LR':
            Mf = M['foot.' + s]
            Rinv = ctx.foot_rest[s].inverted()
            lows.append(min((Mf @ (Rinv @ ctx.heel_off)).z, (Mf @ (Rinv @ ctx.ball_off)).z))
    lows.sort()
    ref = lows[max(0, int(len(lows) * 0.05))]           # il 5% piu' basso: robusto ai salti
    R = sk.rest['hips'].to_3x3().normalized()
    for pose in clip.poses:
        pose['hips'].loc = pose['hips'].loc + R.inverted() @ Vector((0, 0, -ref))
    clip.contacts = detect_contacts(ctx, clip.poses, clip.fps)
    return ref


def load(path, ctx, name=None, frames=None, fps=C.FPS, keep_source=False, mapping=None, **kw):
    """importa un file BVH/FBX, lo trasferisce sul personaggio e restituisce (SampledClip, mappatura usata).
    kw passa a retarget: root_motion, in_place, skip_tpose, hands, smooth_s. La scena torna com'era (fotogramma, fps)."""
    arm, new = import_file(path)
    src_fps = None
    if path.lower().endswith('.bvh'):
        with open(path) as fh:                       # i BVH hanno una chiave per fotogramma della sorgente
            for line in fh:
                if line.strip().startswith('Frame Time'):
                    src_fps = 1.0 / float(line.split(':')[1]); break
    sc = bpy.context.scene
    old = sc.render.fps, sc.render.fps_base
    f_now = sc.frame_current
    if src_fps:
        sc.render.fps = int(round(src_fps)); sc.render.fps_base = 1.0
    try:
        clip, mapping = retarget(arm, ctx, mapping, fps, frames, name or os.path.splitext(os.path.basename(path))[0], **kw)
    finally:
        sc.render.fps, sc.render.fps_base = old
        sc.frame_set(f_now)
    clip.source['file'] = os.path.basename(path)
    clip.source['ground_cm'] = round(ground_offset(ctx, clip) * 100, 2)
    if not keep_source:
        acts = set(); datas = set()
        for o in new:
            if o.animation_data and o.animation_data.action:
                acts.add(o.animation_data.action)
            if o.data is not None:
                datas.add(o.data)
            bpy.data.objects.remove(o, do_unlink=True)
        for a in acts:
            if a.users == 0:
                bpy.data.actions.remove(a)
        for d in datas:
            if d.users == 0:
                if isinstance(d, bpy.types.Armature):
                    bpy.data.armatures.remove(d)
                elif isinstance(d, bpy.types.Mesh):
                    bpy.data.meshes.remove(d)
    return clip, mapping
