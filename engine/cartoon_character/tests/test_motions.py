"""Test della libreria di movimenti (Fase 5): durata, fluidita', posa iniziale e finale, scivolamento dei piedi, pavimento,
collisioni, cicli, mescolanza con le altre clip. I numeri finiscono nel rapporto (out/test_report_motions.json)."""
import math
import unittest

from mathutils import Quaternion

from .. import config as C
from ..animation import motion_library as ML
from ..animation.blending import Timeline
from . import shared
from . import metrics as MT

BODY = ['spine', 'chest', 'neck', 'head'] + [b + s for b in ('upper_arm.', 'forearm.', 'thigh.', 'shin.', 'foot.') for s in 'LR']
# velocita' massima per fotogramma: oltre 75 gradi c'e' un salto vero (inversione, scatto); sotto e' un movimento veloce ma continuo
POP = 75.0
FAST = {'throw': 90.0}        # limite noto: nella frusta del lancio il braccio ruota su se stesso di ~85 gradi in un fotogramma
CONTACT_OK = {'facepalm': ('handR-head', 'armR-head'), 'confusion': ('handR-head', 'armR-head', 'handL-torso'),
              'fear': ('handL-head', 'handR-head', 'armL-head', 'armR-head'),
              'sit': ('handL-legL', 'handR-legR'), 'stand_up': ('handL-legL', 'handR-legR'), 'pick_up': ('handL-handR', 'handL-legL', 'handR-legR'),
              'throw': ('handL-handR',), 'get_up': ('handL-legL', 'handR-legR'), 'fall': ('handL-torso', 'handR-torso', 'armL-head', 'armR-head'),
              'slip': ('handL-torso', 'handR-torso', 'armL-head', 'armR-head', 'handL-handR'), 'trip': ('handL-handR',), 'dance': ('handL-head', 'handR-head', 'armL-head', 'armR-head')}


def angle(a, b):
    return math.degrees(a.rotation_difference(b).angle) % 360


def pose_dist(pa, pb, bones=BODY):
    worst = 0.0
    for n in bones:
        qa = pa[n].rot if n in pa else Quaternion(); qb = pb[n].rot if n in pb else Quaternion()
        d = angle(qa, qb); d = min(d, 360 - d)
        worst = max(worst, d)
    return worst


class TestMotions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = shared.character()
        cls.ctx = cls.ch.ctx
        tl = Timeline(cls.ctx); tl.add(ML.make('idle', cls.ctx), 1.0, 0.0); tl.blinks = False
        cls.stand = tl.evaluate_all(2)[0]['pose']
        shared.REPORT.setdefault('movimenti', {})

    def run_motion(self, name):
        tl = Timeline(self.ctx, seed=2)
        m = ML.make(name, self.ctx)
        d = m.duration if not getattr(m, 'loop', False) else (2 * m.duration if m.duration < 1.5 else m.duration)
        tl.add(m, d, 0.0)
        out = tl.evaluate_all()
        return m, out

    def test_all_motions(self):
        failures = []
        for name in ML.names() + ['get_up']:
            m, out = self.run_motion(name)
            rep = dict(categoria=m.category, durata_s=round(m.duration, 2), fotogrammi=len(out),
                       stato_iniziale=getattr(m, 'start_state', 'stand'), stato_finale=getattr(m, 'end_state', 'stand'))
            # fluidita'
            pj = MT.pose_jumps(out)
            rep['scatto_max_gradi_per_fotogramma'] = round(pj['max_deg'], 1); rep['scatto_osso'] = pj['bone']
            lim = FAST.get(name, POP)
            if pj['max_deg'] > lim:
                failures.append('%s: scatto %.1f gradi/fotogramma su %s (limite %.0f)' % (name, pj['max_deg'], pj['bone'], lim))
            # posa iniziale e finale
            loco = getattr(m, 'kind', '') in ('gait',)
            if not loco and not m.loop and rep['stato_iniziale'] == 'stand' and name not in ('stop',):
                d0 = pose_dist(out[0]['pose'], self.stand)
                rep['scarto_posa_iniziale_gradi'] = round(d0, 1)
                if d0 > 12:
                    failures.append('%s: la posa iniziale non e\' quella in piedi (%.1f gradi)' % (name, d0))
            if not loco and rep['stato_finale'] == 'stand' and not m.loop and not getattr(m, 'hold_end', False):
                d1 = pose_dist(out[-1]['pose'], self.stand)
                rep['scarto_posa_finale_gradi'] = round(d1, 1)
                if d1 > 14:
                    failures.append('%s: la posa finale non e\' quella in piedi (%.1f gradi)' % (name, d1))
            # piedi
            fs = MT.foot_slide(self.ctx, out)
            rep['scivolamento_piedi_cm'] = {s: round(v['max_cm'], 2) for s, v in fs.items()}
            for s, v in fs.items():
                if v['max_cm'] > C.LIMITS['foot_slide_cm']:
                    failures.append('%s: il piede %s scivola di %.2f cm' % (name, s, v['max_cm']))
            fl = MT.floor_penetration(self.ctx, out)
            rep['suola_minima_cm'] = round(fl['min_cm'], 2)
            if fl['min_cm'] < -C.LIMITS['floor_cm']:
                failures.append('%s: la suola entra nel pavimento (%.2f cm)' % (name, fl['min_cm']))
            # collisioni (volumi semplici)
            col = MT.collisions(self.ctx, out)
            allowed = CONTACT_OK.get(name, ())
            rep['compenetrazioni_cm'] = {k: round(v['depth_cm'], 1) for k, v in col.items() if v['depth_cm'] > 0.2}
            for k, v in col.items():
                lim = 6.0 if k in allowed else C.LIMITS['penetration_cm']     # contatti voluti (mano sulla faccia, mani che si toccano)
                if v['depth_cm'] > lim:
                    failures.append('%s: compenetrazione %s di %.1f cm (fotogramma %s)' % (name, k, v['depth_cm'], v['frame']))
            # cicli
            if m.loop:
                if getattr(m, 'kind', '') == 'gait':
                    a = m.evaluate(0.0, self.ctx).pose; b = m.evaluate(m.cycle, self.ctx).pose
                else:
                    a = m.evaluate(0.0, self.ctx).pose; b = m.evaluate(m.duration - 1e-6, self.ctx).pose
                dl = pose_dist(a, b, [n for n in BODY])
                rep['chiusura_ciclo_gradi'] = round(dl, 2)
                if dl > 2.0:
                    failures.append('%s: il ciclo non si chiude (%.2f gradi)' % (name, dl))
            shared.REPORT['movimenti'][name] = rep
        if failures:
            self.fail('\n' + '\n'.join(failures))

    def test_blending_from_idle(self):
        """ogni movimento si attacca a «idle» prima e dopo senza scatti e senza piedi che scivolano (dissolvenze di 0,25 s)."""
        failures = []
        rep = {}
        for name in ML.names():
            if name in ('idle',):
                continue
            tl = Timeline(self.ctx, seed=2)
            tl.add(ML.make('idle', self.ctx), 1.0, 0.0)
            m = ML.make(name, self.ctx)
            if getattr(m, 'start_state', 'stand') != 'stand':
                continue
            d = m.duration if not getattr(m, 'loop', False) else 2 * m.duration
            tl.add(m, d, 0.25)
            if getattr(m, 'end_state', 'stand') == 'floor':
                tl.add(ML.make('get_up', self.ctx), None, 0.25)
            elif getattr(m, 'end_state', 'stand') == 'chair':
                tl.add(ML.make('stand_up', self.ctx), None, 0.25)
            elif getattr(m, 'end_state', 'stand') == 'holding':
                tl.add(ML.make('throw', self.ctx), None, 0.25)
            tl.add(ML.make('idle', self.ctx), 1.0, 0.3)
            out = tl.evaluate_all()
            pj = MT.pose_jumps(out)
            rj = MT.root_jumps(out)
            fs = MT.foot_slide(self.ctx, out)
            rep[name] = dict(scatto_max=round(pj['max_deg'], 1), accel_radice=round(rj['max_acc'], 1),
                             scivolamento_cm={s: round(v['max_cm'], 2) for s, v in fs.items()})
            lim = FAST.get(name, POP)
            if pj['max_deg'] > lim:
                failures.append('%s: scatto %.1f nella mescolanza (%s)' % (name, pj['max_deg'], pj['bone']))
            if rj['max_acc'] > 60.0:          # partenze di scatto: rampa breve ma continua
                failures.append('%s: la radice accelera di colpo (%.1f m/s2)' % (name, rj['max_acc']))
            # piedi fermi anche nelle dissolvenze (la frenata «stop» ha senso solo dopo un ciclo: provata a parte)
            for s, v in fs.items():
                if name != 'stop' and v['max_cm'] > C.LIMITS['foot_slide_cm']:
                    failures.append('%s: il piede %s scivola di %.2f cm nella mescolanza' % (name, s, v['max_cm']))
        shared.REPORT['mescolanze_da_idle'] = rep
        if failures:
            self.fail('\n' + '\n'.join(failures))

    def test_walk_to_stop_and_turn(self):
        """camminata -> frenata -> giro -> corsa -> frenata: piedi fermi negli appoggi."""
        tl = Timeline(self.ctx, seed=2)
        tl.add(ML.make('idle', self.ctx), 0.6, 0.0)
        g = ML.make('walk', self.ctx); tl.add(g, 3 * g.cycle, 0.25)
        from ..animation import procedural as P
        tl.add(P.make_stop('walk'), None, 0.08)
        tl.add(ML.make('turn', self.ctx, angle=90), None, 0.2)
        r = ML.make('run', self.ctx); tl.add(r, 4 * r.cycle, 0.25)
        tl.add(P.make_stop('run'), None, 0.08)
        tl.add(ML.make('idle', self.ctx), 0.8, 0.3)
        out = tl.evaluate_all()
        fs = MT.foot_slide(self.ctx, out)
        shared.REPORT['sequenza_cammina_gira_corri'] = {s: round(v['max_cm'], 2) for s, v in fs.items()}
        for s, v in fs.items():
            self.assertLess(v['max_cm'], 2.0, 'piede %s scivola %.2f cm' % (s, v['max_cm']))
