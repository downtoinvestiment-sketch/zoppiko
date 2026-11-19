"""Test del retargeting: BVH reali del database CMU (conversione cgspeed in assets/animations/cmu/) e un FBX con i nomi
Mixamo creato qui (andata e ritorno): verifica la catena import -> mappatura -> trasferimento. Non sono file Mixamo veri:
quelli richiedono un account Adobe e non si possono ridistribuire."""
import math
import os
import unittest

import bpy
from mathutils import Vector, Quaternion, Matrix

from .. import config as C
from ..animation import retarget as RT
from ..animation import motion_library as ML
from ..animation.blending import Timeline, root_matrix, write_action
from . import shared
from . import metrics as MT

CMU = os.path.join(C.ASSETS, 'animations', 'cmu')


class TestRetarget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = shared.character()
        cls.ctx = cls.ch.ctx
        shared.REPORT.setdefault('retargeting', {})

    def test_auto_map_tables(self):
        mix = ['mixamorig:' + v for v in C.MIXAMO.values()] + ['mixamorig:Spine1', 'mixamorig:LeftHandPinky1']
        m = RT.auto_map(mix)
        self.assertEqual(m['upper_arm.L'], 'mixamorig:LeftArm'); self.assertEqual(m['chest'], 'mixamorig:Spine2')
        cmu = ['Hips', 'LHipJoint', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase', 'RHipJoint', 'RightUpLeg', 'RightLeg',
               'RightFoot', 'RightToeBase', 'LowerBack', 'Spine', 'Spine1', 'Neck', 'Neck1', 'Head', 'LeftShoulder', 'LeftArm',
               'LeftForeArm', 'LeftHand', 'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand']
        m = RT.auto_map(cmu)
        self.assertEqual(m['thigh.L'], 'LeftUpLeg'); self.assertEqual(m['spine'], 'LowerBack')
        other = ['pelvis', 'spine_01', 'spine_03', 'neck_01', 'head', 'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l',
                 'thigh_l', 'calf_l', 'foot_l', 'ball_l', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_r', 'calf_r', 'foot_r', 'ball_r']
        m = RT.auto_map(other)
        for k, v in (('hips', 'pelvis'), ('upper_arm.L', 'upperarm_l'), ('forearm.R', 'lowerarm_r'), ('shin.L', 'calf_l'), ('toe.R', 'ball_r')):
            self.assertEqual(m.get(k), v, 'mappa automatica (nomi Unreal): %s -> %s' % (k, m.get(k)))

    def _cmu(self, name):
        p = os.path.join(CMU, name + '.bvh')
        if not os.path.exists(p):
            self.skipTest('file CMU mancante: %s (mettere qui i BVH CMU della conversione cgspeed)' % p)
        return p

    def test_cmu_walk(self):
        p = self._cmu('02_01')
        clip, mapping = RT.load(p, self.ctx)
        self.assertGreaterEqual(len(mapping), 15)
        tl = Timeline(self.ctx, seed=1); tl.add(clip, clip.duration, 0.0)
        out = tl.evaluate_all()
        start = root_matrix(out[0]['pose']['root']).translation; end = root_matrix(out[-1]['pose']['root']).translation
        dist = (end - start).length
        fs = MT.foot_slide(self.ctx, out); fl = MT.floor_penetration(self.ctx, out); pj = MT.pose_jumps(out)
        col = MT.collisions(self.ctx, out)
        shared.REPORT['retargeting']['CMU 02_01 (camminata)'] = dict(
            durata_s=round(clip.duration, 2), distanza_m=round(dist, 2), ossa_mappate=len(mapping),
            scivolamento_cm={k: round(v['max_cm'], 2) for k, v in fs.items()}, appoggi={k: v['intervals'] for k, v in fs.items()},
            suola_minima_cm=round(fl['min_cm'], 2), scatto_max=round(pj['max_deg'], 1),
            compenetrazioni_cm={k: round(v['depth_cm'], 1) for k, v in col.items() if v['depth_cm'] > 0.2})
        self.assertGreater(dist, 0.8, 'la camminata non avanza (%.2f m)' % dist)
        for s in 'LR':
            self.assertGreater(fs[s]['intervals'], 1, 'nessun appoggio riconosciuto per il piede ' + s)
            self.assertLess(fs[s]['max_cm'], 2.0, 'piede %s scivola %.2f cm' % (s, fs[s]['max_cm']))
        self.assertGreater(fl['min_cm'], -1.5)

    def test_cmu_jump_and_wave(self):
        for name, label in (('16_01', 'salto'), ('13_27', 'saluto e indica')):
            p = self._cmu(name)
            frames = (1, 600) if name == '13_27' else None
            clip, mapping = RT.load(p, self.ctx, frames=frames)
            tl = Timeline(self.ctx, seed=1); tl.add(clip, clip.duration, 0.0)
            out = tl.evaluate_all()
            pj = MT.pose_jumps(out); fl = MT.floor_penetration(self.ctx, out)
            col = MT.collisions(self.ctx, out)
            shared.REPORT['retargeting']['CMU %s (%s)' % (name, label)] = dict(
                durata_s=round(clip.duration, 2), scatto_max=round(pj['max_deg'], 1), suola_minima_cm=round(fl['min_cm'], 2),
                compenetrazioni_cm={k: round(v['depth_cm'], 1) for k, v in col.items() if v['depth_cm'] > 0.2})
            self.assertLess(pj['max_deg'], 75.0, '%s: scatto %.1f' % (name, pj['max_deg']))

    def test_fbx_roundtrip_mixamo_names(self):
        """esporta la nostra camminata su uno scheletro con i nomi Mixamo (FBX), la reimporta e la ritrasferisce:
        le articolazioni devono tornare dove erano (verifica FBX + mappatura Mixamo + metodo, non i file di Mixamo)."""
        import tempfile
        ch = self.ch; ctx = self.ctx
        tl = Timeline(ctx, seed=1); tl.secondary = False; tl.blinks = False
        g = ML.make('walk', ctx); tl.add(g, 2 * g.cycle, 0.0)
        out = tl.evaluate_all()
        # copia dell'armatura con i nomi Mixamo (solo le ossa mappate restano col nome nuovo)
        src = ch.rig.copy(); src.data = ch.rig.data.copy(); src.name = 'MixamoTest'
        bpy.context.scene.collection.objects.link(src)
        rename = {k: 'mixamorig:' + v for k, v in C.MIXAMO.items()}
        for b in src.data.bones:
            if b.name in rename:
                b.name = rename[b.name]
        for pb in src.pose.bones:
            for c in list(pb.constraints):
                pb.constraints.remove(c)
        out2 = []
        for fr in out:
            out2.append(dict(fr, pose={rename.get(k, k): v for k, v in fr['pose'].items()}))
        write_action(src, out2, 'MixamoTestAnim')
        if src.animation_data:
            src.animation_data.drivers.clear() if src.animation_data.drivers else None
        path = os.path.join(tempfile.gettempdir(), 'cc_mixamo_test.fbx')
        for o in bpy.context.scene.objects:
            o.select_set(False)
        src.select_set(True); bpy.context.view_layer.objects.active = src
        sc = bpy.context.scene
        sc.frame_start = 1; sc.frame_end = len(out)
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'ARMATURE'}, bake_anim=True,
                                 add_leaf_bones=False, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False)
        bpy.data.objects.remove(src, do_unlink=True)
        clip, mapping = RT.load(path, ctx, in_place=False)
        self.assertGreaterEqual(len(mapping), 30)
        tl2 = Timeline(ctx, seed=1); tl2.secondary = False; tl2.blinks = False; tl2.foot_lock = False
        tl2.add(clip, clip.duration, 0.0)
        back = tl2.evaluate_all()
        n = min(len(out), len(back))
        # la clip ritrasferita parte guardando -Y in media nel primo secondo: tolgo questa rotazione costante attorno a Z
        # (stimata ai minimi quadrati sulle stesse articolazioni) prima di misurare l'errore
        bones = ('hand.L', 'hand.R', 'foot.L', 'foot.R', 'head', 'forearm.L', 'shin.R')
        pairs = []
        for i in range(2, n - 2):
            A = MT.world_mats(ctx.sk, out[i]); B = MT.world_mats(ctx.sk, back[i])
            ra = A['hips'].translation; rb = B['hips'].translation
            for b in bones:
                pairs.append(((A[b].translation - ra), (B[b].translation - rb)))
        sxy = sum(a.y * b.x - a.x * b.y for a, b in pairs); cxx = sum(a.x * b.x + a.y * b.y for a, b in pairs)
        yaw = math.atan2(sxy, cxx)
        Rz = Matrix.Rotation(yaw, 3, 'Z')
        worst = max(((a - Rz @ b).length for a, b in pairs), default=1.0)
        shared.REPORT['retargeting']['FBX nomi Mixamo (andata e ritorno)'] = dict(
            ossa_mappate=len(mapping), errore_max_cm=round(worst * 100, 2), rotazione_iniziale_tolta_gradi=round(math.degrees(yaw), 2))
        self.assertLess(worst, 0.02, 'errore massimo %.3f m' % worst)
