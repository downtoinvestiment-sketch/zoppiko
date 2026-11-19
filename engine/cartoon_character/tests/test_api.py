"""Test dell'API Python (Fase 6): play, set_expression, look_at, walk_to, stati, oggetti, labiale, due personaggi."""
import math
import unittest

import bpy
from mathutils import Vector

from .. import config as C
from ..automation import scene as S
from ..automation.controller import Character
from ..animation.blending import root_matrix
from . import shared


def head_forward(ch, frame_index):
    pose = ch.tl.data[frame_index]['pose']
    M = ch.sk.fk(pose)
    return (M['head'].to_3x3().normalized() @ Vector((0, 0, 1))).normalized()


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shared._CH = None
        S.reset()
        cls.ch = Character(C.NAME, 'default')
        shared._CH = cls.ch

    def fresh(self):
        tl_cls = type(self.ch.tl)
        from ..animation.blending import Timeline
        self.ch.tl = Timeline(self.ch.ctx, seed=5)
        self.ch.props = {}
        return self.ch

    def test_play_and_expression(self):
        ch = self.fresh()
        ch.play('idle', duration=1.0).play('surprise').play('idle', duration=1.0)
        ch.set_expression('happy', at=0.2, duration=0.6)
        out = ch.bake()
        f_in = int(0.5 * C.FPS); f_out = len(out) - 2
        self.assertGreater(out[f_in]['props']['smile'], 0.8)
        self.assertLess(out[f_out]['props']['smile'], 0.2)
        # la sorpresa porta il suo viso (bocca a «O») quando non c'e' un'espressione esplicita
        s = [c for c in ch.tl.clips if c.name == 'surprise'][0]
        f = int((s.start + 0.5) * C.FPS)
        self.assertGreater(out[f]['props']['O'], 0.5)
        self.assertTrue(ch.rig.animation_data and ch.rig.animation_data.action)

    def test_italian_aliases(self):
        ch = self.fresh()
        ch.play('cammina', duration=1.0).play('salta').set_expression('felice')
        names = [c.name for c in ch.tl.clips]
        self.assertIn('walk', names); self.assertIn('jump', names)
        self.assertIn('stop', names)                          # frenata inserita da sola prima del salto

    def test_look_at(self):
        ch = self.fresh()
        ch.play('idle', duration=2.0)
        ch.look_at((2.0, -0.3, 0.9), at=0.5, duration=1.0)
        ch.bake()
        fw_look = head_forward(ch, int(1.2 * C.FPS)); fw_free = head_forward(ch, int(0.1 * C.FPS))
        self.assertGreater(fw_look.x, 0.3, 'la testa non gira verso il bersaglio (%.2f)' % fw_look.x)
        self.assertLess(abs(fw_free.x), 0.15)
        ex = ch.tl.data[int(1.2 * C.FPS)]['pose']['eye.L'].rot
        self.assertGreater(abs(ex.angle), 0.02)              # anche gli occhi puntano

    def test_walk_to(self):
        ch = self.fresh()
        ch.play('idle', duration=0.5)
        ch.walk_to((0.0, -1.6))
        ch.walk_to((1.0, -2.4))
        out = ch.bake()
        end = root_matrix(out[-1]['pose']['root']).translation
        err = (Vector((end.x, end.y, 0)) - Vector((1.0, -2.4, 0))).length
        shared.REPORT['walk_to_errore_cm'] = round(err * 100, 2)
        self.assertLess(err, 0.06, 'arriva a %.3f m dal punto' % err)

    def test_states(self):
        ch = self.fresh()
        ch.play('fall').play('wave')                           # da terra si alza da solo prima di salutare
        names = [c.name for c in ch.tl.clips]
        self.assertEqual(names[:3], ['fall', 'get_up', 'wave'])
        ch2 = self.fresh()
        ch2.sit().play('stand_up')
        self.assertEqual([c.name for c in ch2.tl.clips], ['sit', 'stand_up'])

    def test_pick_up_and_throw(self):
        ch = self.fresh()
        me = bpy.data.meshes.new('palla'); import bmesh
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.06); bm.to_mesh(me); bm.free()
        ball = bpy.data.objects.new('palla', me); bpy.context.scene.collection.objects.link(ball)
        ball.location = (0.0, -0.21, 0.06)
        ch.play('idle', duration=0.4).pick_up(ball).throw((0.0, -2.0, 0.0)).play('idle', duration=1.0)
        out = ch.bake()
        sc = bpy.context.scene
        g = [c for c in ch.tl.clips if c.name == 'pick_up'][0]
        sc.frame_set(1); p0 = ball.matrix_world.translation.copy()
        sc.frame_set(int((g.start + 1.9) * C.FPS) + 1); p1 = ball.matrix_world.translation.copy()
        sc.frame_set(len(out)); p2 = ball.matrix_world.translation.copy()
        self.assertLess((p0 - Vector((0, -0.21, 0.06))).length, 0.01)
        self.assertGreater(p1.z, 0.3, 'la palla non e\' stata sollevata')
        self.assertLess(p2.y, -1.0, 'la palla non e\' stata lanciata in avanti')
        self.assertLess(abs(p2.z - 0.06), 0.02, 'la palla non e\' tornata a terra')

    def test_lip_sync(self):
        ch = self.fresh()
        ch.play('idle', duration=2.5)
        ch.say('Ciao, oggi parliamo di scienza', at=0.3, duration=2.0)
        out = ch.bake()
        opens = [fr['props']['open'] + fr['props']['O'] + fr['props']['E'] + fr['props']['U'] for fr in out]
        mid = opens[int(0.5 * C.FPS):int(2.2 * C.FPS)]
        self.assertGreater(max(mid), 0.5)
        self.assertGreater(len([1 for a, b in zip(mid, mid[1:]) if abs(a - b) > 0.08]), 6)   # la bocca si muove

    def test_two_characters(self):
        a = self.ch
        a.tl = type(a.tl)(a.ctx, seed=1)
        b = Character('Bea', 'blu', location=(0.8, -0.2), facing=90)
        a.play('idle', duration=2.0).look_at(b)
        b.play('wave').play('idle', duration=0.5).look_at(a)
        a.bake(); b.bake()
        self.assertNotEqual(a.rig.name, b.rig.name)
        fw = head_forward(a, int(1.5 * C.FPS))
        self.assertGreater(fw.x, 0.2, 'Ciuffo non guarda Bea')

    def test_expression_forever(self):
        """un'espressione senza durata vale fino alla fine ma non allunga la scena (prima creava una scena infinita)."""
        ch = self.fresh()
        ch.play('idle', duration=1.0).set_expression('felice').look_at('camera')
        ch.say('Ciao', duration=0.5)
        out = ch.bake()
        self.assertEqual(len(out), int(round(1.0 * C.FPS)) + 1)
        self.assertGreater(out[-1]['props']['smile'], 0.8)

    def test_zz_scene_json(self):
        """la scena di esempio in JSON si costruisce e si cuoce: due personaggi, palla presa e lanciata (gira per ultimo:
        ricrea la scena da zero)."""
        import json, os
        from ..automation import scene_json as SJ
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples', 'saluto.json')
        with open(path) as fh:
            spec = json.load(fh)
        sc, chars, props, n = SJ.build(spec, os.path.dirname(path))
        shared._CH = None
        self.assertEqual(sorted(chars), ['Bea', 'Ciuffo'])
        self.assertGreater(n, 200)
        for ch in chars.values():
            self.assertIsNotNone(ch.rig.animation_data.action)
        ball = props['palla']
        sc.frame_set(1); z0 = ball.matrix_world.translation.z
        lifted = False
        for f in range(1, n + 1, 3):
            sc.frame_set(f)
            if ball.matrix_world.translation.z > 0.3:
                lifted = True
        sc.frame_set(n)
        self.assertTrue(lifted, 'la palla non viene sollevata')
        self.assertLess(abs(ball.matrix_world.translation.z - z0), 0.02, 'la palla non torna a terra')
        # primo rimbalzo: dove la palla torna a terra dopo essere stata sollevata (a 24 fps si muove ~12 cm per fotogramma)
        target = [a['throw'] for c in spec['characters'] for a in c['actions'] if 'throw' in a][0]
        up = False; err = None
        for f in range(1, n + 1):
            sc.frame_set(f); p = ball.matrix_world.translation
            if p.z > 0.3:
                up = True
            elif up and p.z < z0 + 0.005:
                err = ((p.x - target[0]) ** 2 + (p.y - target[1]) ** 2) ** 0.5
                break
        self.assertIsNotNone(err, 'la palla non torna a terra')
        self.assertLess(err, 0.15, 'la palla non tocca terra dove e\' stata lanciata (%.2f m)' % err)
        shared.REPORT['scena_json'] = dict(fotogrammi=n, personaggi=sorted(chars), errore_lancio_cm=round(err * 100, 1),
                                           clip={k: [c.name for c in v.tl.clips] for k, v in chars.items()})
