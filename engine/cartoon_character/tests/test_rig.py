"""Test del modello e del rig (Fase 4). Si eseguono con: python3 cartoon_character/main.py test"""
import math
import random
import unittest

import bpy
from mathutils import Vector, Quaternion, Euler, Matrix

from .. import config as C
from ..character import geometry as G
from ..character import facial as F
from ..character.skeleton import BonePose, euler_q
from ..animation import face as FACE
from . import shared


class TestRig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = shared.character()
        cls.rig = cls.ch.rig
        cls.sk = cls.ch.sk

    def setUp(self):
        shared.reset_pose(self.rig)

    def test_hierarchy_compatible(self):
        """catena umanoide come Mixamo/CMU: Hips > Spine > Spine2 > Neck > Head, braccia e gambe complete."""
        b = self.rig.data.bones
        chain = [('spine', 'hips'), ('chest', 'spine'), ('neck', 'chest'), ('head', 'neck')]
        for s in 'LR':
            chain += [('shoulder.' + s, 'chest'), ('upper_arm.' + s, 'shoulder.' + s), ('forearm.' + s, 'upper_arm.' + s),
                      ('hand.' + s, 'forearm.' + s), ('thigh.' + s, 'hips'), ('shin.' + s, 'thigh.' + s),
                      ('foot.' + s, 'shin.' + s), ('toe.' + s, 'foot.' + s)]
        for child, parent in chain:
            self.assertIn(child, b)
            self.assertEqual(b[child].parent.name, parent)
        for ours in C.MIXAMO:
            self.assertIn(ours, b, 'osso mancante per la mappa Mixamo: ' + ours)
        deform = [x for x in b if x.use_deform]
        self.assertGreaterEqual(len(deform), 50)

    def test_fk_matches_blender(self):
        """la cinematica in Python coincide con quella di Blender (pose casuali, anche con scala e spostamenti)."""
        rnd = random.Random(4)
        worst = 0.0
        for trial in range(4):
            pose = {}
            for pb in self.rig.pose.bones:
                if pb.name in ('root',) or 'ik' in pb.name or 'pole' in pb.name or pb.name == 'eye_target':
                    continue
                pose[pb.name] = BonePose(rot=euler_q([rnd.uniform(-35, 35) for _ in range(3)]))
            pose['hips'].loc = Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05)))
            pose['spine'].scl = Vector((1.05, 0.9, 1.05))
            pose['root'] = BonePose(loc=(0.3, -0.2, 0.0), rot=Quaternion((0, 0, 1), 0.4))
            shared.apply(self.rig, pose)
            M = self.sk.fk(pose)
            oe = shared.evaluated(self.rig)
            for n in M:
                d = (oe.pose.bones[n].head - M[n].translation).length
                worst = max(worst, d)
        self.assertLess(worst, 1e-4, 'errore massimo %.6f m' % worst)

    def test_weights_normalized(self):
        """ogni vertice ha pesi che sommano a 1, al massimo 4 ossa, solo ossa che deformano."""
        deform = {b.name for b in self.rig.data.bones if b.use_deform}
        for ob in self.ch.h['meshes'].values():
            names = {g.index: g.name for g in ob.vertex_groups}
            for g in names.values():
                self.assertIn(g, deform, '%s: gruppo %s non e\' un osso che deforma' % (ob.name, g))
            for v in ob.data.vertices:
                tot = sum(g.weight for g in v.groups)
                self.assertAlmostEqual(tot, 1.0, delta=2e-3, msg='%s v%d somma %.4f' % (ob.name, v.index, tot))
                self.assertLessEqual(len(v.groups), 4)

    def test_ik_fk_switch(self):
        """IK del rig: con ik=1 il polso raggiunge il bersaglio; con ik=0 torna l'FK."""
        P = self.rig.pose.bones
        for s, chain, tgt, key in (('L', 'forearm', 'hand_ik', 'ik_arm'), ('R', 'shin', 'foot_ik', 'ik_leg')):
            P['root']['%s.%s' % (key, s)] = 1.0
            P['%s.%s' % (tgt, s)].location = (0.0, -0.05, 0.05) if key == 'ik_arm' else (0.0, 0.03, 0.06)
            oe = shared.evaluated(self.rig)
            ik_bone = oe.pose.bones['%s.%s' % (tgt, s)]
            tail = oe.pose.bones['%s.%s' % (chain, s)].tail
            self.assertLess((tail - ik_bone.head).length, 0.003, '%s: IK non raggiunge (%.4f m)' % (s, (tail - ik_bone.head).length))
            P['root']['%s.%s' % (key, s)] = 0.0
            oe = shared.evaluated(self.rig)
            rest_tail = self.rig.data.bones['%s.%s' % (chain, s)].tail_local
            self.assertLess((oe.pose.bones['%s.%s' % (chain, s)].tail - rest_tail).length, 1e-4)
            P['%s.%s' % (tgt, s)].location = (0, 0, 0)

    def test_two_bone_analytic(self):
        """IK analitico della pipeline: raggiunge bersagli casuali e il gomito resta dalla parte del polo."""
        rnd = random.Random(7)
        ctx = self.ch.ctx
        for trial in range(40):
            pose = {}
            M = self.sk.fk(pose)
            S = M['upper_arm.L'].translation
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
            T = S + d * rnd.uniform(0.12, 0.26)
            pole = S + Vector((0.2, 0.3, -0.2))
            self.sk.two_bone(pose, 'upper_arm.L', 'forearm.L', T, pole, M, end='hand.L')
            M2 = self.sk.fk(pose)
            self.assertLess((self.sk.tail(M2, 'forearm.L') - T).length, 1e-3)
            E = self.sk.tail(M2, 'upper_arm.L')
            u = (T - S).normalized(); side = (E - S) - u * (E - S).dot(u); pv = (pole - S) - u * (pole - S).dot(u)
            if side.length > 1e-3 and pv.length > 1e-3:
                self.assertGreater(side.dot(pv), 0.0)

    def test_face_drivers(self):
        """le proprieta' del viso comandano le shape keys (bocca, pupille, rossore): i vertici si muovono davvero."""
        import numpy as np
        from .metrics import mesh_arrays
        P = self.rig.pose.bones
        for mesh_name, k in (('mouth', 'smile_open'), ('mouth', 'scream'), ('pupil.L', 'pupil'), ('blush', 'blush')):
            ob = self.ch.h['meshes'][mesh_name]
            P['face'][k] = 0.0
            shared.evaluated(self.rig)
            a = mesh_arrays(ob, bpy.context.evaluated_depsgraph_get())
            P['face'][k] = 1.0
            shared.evaluated(self.rig)
            b = mesh_arrays(ob, bpy.context.evaluated_depsgraph_get())
            P['face'][k] = 0.55 if k == 'pupil' else 0.0
            self.assertGreater(float(np.abs(b - a).max()), 0.004, '%s/%s: la shape key non si muove' % (mesh_name, k))

    def test_eyes_independent(self):
        """ogni occhio si muove da solo; i riflessi restano fissi sulla testa."""
        P = self.rig.pose.bones
        P['eye.L'].rotation_quaternion = euler_q((10, 0, 25))
        oe = shared.evaluated(self.rig)
        self.assertGreater(abs(oe.pose.bones['eye.L'].matrix.to_quaternion().angle), 0.3)
        self.assertLess(abs(oe.pose.bones['eye.R'].matrix.to_quaternion().angle - self.rig.data.bones['eye.R'].matrix_local.to_quaternion().angle), 1e-5)

    def test_lids_close(self):
        """a palpebre chiuse il bordo superiore scende sotto quello inferiore (niente fessura)."""
        for low in (0.0, 0.5, 1.0):
            beta, gamma = FACE.lid_angles(0.0, low, 0.0)
            self.assertLess(beta, gamma)
            beta1, _ = FACE.lid_angles(1.0, low, 0.0)
            self.assertGreater(beta1, C.IRIS_DEG - 2)          # a occhio aperto l'iride si vede tutta

    def test_mouth_layers_inside(self):
        """lingua e denti restano dentro il contorno della bocca per tutte le forme e i loro mix."""
        for name in C.MOUTH_SHAPES:
            m2, t2, d2 = F._mouth_grid(C.MOUTH_PARAMS[name])
            cols = F.mouth_curves(C.MOUTH_PARAMS[name], F.NU)
            for i, (s, tu, tl) in enumerate(cols):
                for j in range(4):
                    t = t2[i * 4 + j][1]
                    self.assertGreaterEqual(t, tl - 1e-6); self.assertLessEqual(t, tu + 1e-6)
                for j in range(6):
                    t = d2[i * 6 + j][1]
                    self.assertGreaterEqual(t, tl - 1e-6); self.assertLessEqual(t, tu + 1e-6)

    def test_brows_stay_on_forehead(self):
        """con ogni espressione le sopracciglia restano davanti alla fronte (fuori dalla testa, vicine alla pelle)."""
        verts = [Vector(v) for v in F.part_brow('L')['verts']]
        rest = self.rig.data.bones['brow.L'].matrix_local
        for name in C.EXPRESSIONS:
            ch = FACE.expression(name)
            pose = {}
            FACE.apply(ch, pose, self.ch.ctx.curl_poses)
            M = self.sk.fk(pose)
            T = M['brow.L'] @ rest.inverted()
            sd = [G.head_sdf(T @ v) for v in verts]
            self.assertGreater(min(sd), -0.0015, '%s: sopracciglio dentro la testa (%.4f)' % (name, min(sd)))
            self.assertLess(max(sd), 0.03, '%s: sopracciglio staccato (%.4f)' % (name, max(sd)))

    def test_pose_deformation(self):
        """pose ampie (gomito 90, ginocchio 100, braccia su, busto torto, dita chiuse): niente collassi, volumi stabili.
        Pose estreme (gomito 140, ginocchio 130): solo misurate e riportate (la piega interna si schiaccia)."""
        from .metrics import deformation
        fingers = [b.name for b in self.rig.data.bones if b.name.startswith(('f_', 'thumb'))]
        moderate = {
            'braccia_su': {'upper_arm.L': (0, 0, 120), 'upper_arm.R': (0, 0, -120), 'forearm.L': (30, 0, 0), 'forearm.R': (30, 0, 0)},
            'gomiti_90': {'upper_arm.L': (60, 0, 20), 'upper_arm.R': (60, 0, -20), 'forearm.L': (90, 0, 0), 'forearm.R': (90, 0, 0)},
            'ginocchia_100': {'thigh.L': (80, 0, 0), 'shin.L': (-100, 0, 0), 'thigh.R': (40, 0, 0), 'shin.R': (-70, 0, 0)},
            'busto': {'spine': (25, 20, 10), 'chest': (20, 20, 10), 'neck': (15, 30, 0), 'head': (20, 45, 10)},
            'dita_45': {n: (45, 0, 0) for n in fingers},
        }
        extreme = {
            'pugno_80': {n: (80, 0, 0) for n in fingers},
            'gomito_140': {'forearm.L': (140, 0, 0)},
            'ginocchio_130': {'thigh.L': (100, 0, 0), 'shin.L': (-130, 0, 0)},
        }
        sc = bpy.context.scene
        objs = [o for k, o in self.ch.h['meshes'].items() if k.split('.')[0] in ('torso', 'arm', 'leg', 'hand', 'shoe', 'curl')]
        rep = {}
        for group, poses in (('moderate', moderate), ('estreme', extreme)):
            for pname, spec in poses.items():
                shared.reset_pose(self.rig)
                for b, e in spec.items():
                    self.rig.pose.bones[b].rotation_quaternion = euler_q(e)
                res = deformation(sc, objs, [sc.frame_current])
                for k, v in res.items():
                    if v['stretch'] > 1.02 or v['compress'] < 0.98 or abs(v['vol_min'] - 1) > 0.005:
                        rep['%s/%s/%s' % (group, pname, k.split('_', 1)[1])] = dict(allungamento=round(v['stretch'], 2),
                                                                                 schiacciamento=round(v['compress'], 2),
                                                                                 volume=round(v['vol_min'], 3))
                    if v['v0'] > 1e-6:
                        self.assertGreater(v['vol_min'], 0.85, '%s %s: volume %.2f' % (pname, k, v['vol_min']))
                        self.assertLess(v['vol_max'], 1.15, '%s %s: volume %.2f' % (pname, k, v['vol_max']))
                    if group == 'moderate':
                        self.assertLess(v['stretch'], C.LIMITS['stretch'], '%s %s: allungamento %.2f' % (pname, k, v['stretch']))
                        if '_hand' not in k:          # dita corte e grosse: la piega interna si schiaccia sempre (riportato)
                            self.assertGreater(v['compress'], C.LIMITS['compress'], '%s %s: schiacciamento %.2f' % (pname, k, v['compress']))
        shared.reset_pose(self.rig)
        shared.REPORT['deformazioni (pose del test del rig)'] = rep
