"""Scrive docs/TEST.md dai rapporti JSON dei test (out/test_report_*.json) e della scena di prova (out/validate/report.json).

    python3 cartoon_character/tools/test_doc.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(HERE))
from cartoon_character import config as C  # noqa: E402

OUT = os.path.join(HERE, 'out')
VAL = os.path.join(OUT, 'validate')


def load(name):
    p = os.path.join(OUT, name)
    return json.load(open(p)) if os.path.exists(p) else None


def fmt_slide(d):
    return '%.2f / %.2f' % (d.get('L', 0.0), d.get('R', 0.0))


def main():
    rep = load('test_report_rig_motions_api_retarget.json') or {}
    val = json.load(open(os.path.join(VAL, 'report.json'))) if os.path.exists(os.path.join(VAL, 'report.json')) else None
    L = ['# Test e misure', '',
         'Pagina generata da `tools/test_doc.py` con i rapporti di `main.py test` e `main.py validate`. Tutti i numeri sono '
         'misurati, nessuno è stimato. Limiti (`config.LIMITS`): scivolamento del piede appoggiato %.1f cm, suola sotto il '
         'pavimento %.1f cm, compenetrazione tra parti del corpo %.1f cm (contatti voluti, come la mano sul viso, fino a 6 cm), '
         'rotazione di un osso tra due fotogrammi 75 gradi (90 per il lancio), allungamento della mesh %.1f volte, '
         'schiacciamento fino a %.2f.' % (C.LIMITS['foot_slide_cm'], C.LIMITS['floor_cm'], C.LIMITS['penetration_cm'],
                                         C.LIMITS['stretch'], C.LIMITS['compress']), '']
    r = rep.get('_riassunto')
    if r:
        L += ['## Test automatici', '',
              '`python3 cartoon_character/main.py test`: **%d test, %d falliti, %d errori** in %.0f s.' % (
                  r['eseguiti'], r['falliti'], r['errori'], r['secondi']), '',
              '| Gruppo | Cosa verifica |', '|---|---|',
              '| rig (11) | gerarchia umanoide, pesi (somma 1, massimo 4 ossa), cinematica Python identica a Blender, IK, occhi indipendenti, '
              'palpebre che si chiudono, sopracciglia sulla fronte, bocca (lingua e denti dentro), shape keys guidate, pose ampie senza collassi |',
              '| movimenti (3) | i 31 movimenti uno per uno; attacco a «idle» prima e dopo; camminata, frenata, giro, corsa, frenata |',
              '| API (10) | play ed espressioni, espressione senza durata, nomi italiani, sguardo, walk_to (errore %s cm), stati a terra e '
              'seduto, raccogli e lancia, labiale, due personaggi che si guardano, scena JSON (la palla tocca terra a %s cm dal punto '
              'di lancio) |' % (rep.get('walk_to_errore_cm', '-'), (rep.get('scena_json') or {}).get('errore_lancio_cm', '-')),
              '| retargeting (4) | mappatura automatica (Mixamo, CMU, nomi Unreal), BVH CMU reali, FBX con i nomi Mixamo andata e ritorno |', '']
    mv = rep.get('movimenti')
    if mv:
        L += ['## Libreria dei movimenti', '',
              'Ogni movimento da solo. Scarto della posa iniziale e finale da quella in piedi, in gradi (vuoto per cicli e movimenti che '
              'finiscono a terra o seduti).', '',
              '| Movimento | Categoria | Durata (s) | Piedi L / R (cm) | Suola min (cm) | Rotazione max (gradi/fotogramma) | Compenetrazioni (cm) | Pose inizio / fine |',
              '|---|---|---|---|---|---|---|---|']
        for k, v in mv.items():
            col = ', '.join('%s %.1f' % kv for kv in v.get('compenetrazioni_cm', {}).items()) or '-'
            a = v.get('scarto_posa_iniziale_gradi'); b = v.get('scarto_posa_finale_gradi')
            L.append('| %s | %s | %.2f | %s | %.2f | %.1f (%s) | %s | %s / %s |' % (
                k, v['categoria'], v['durata_s'], fmt_slide(v['scivolamento_piedi_cm']), v['suola_minima_cm'],
                v['scatto_max_gradi_per_fotogramma'], v['scatto_osso'], col, '-' if a is None else a, '-' if b is None else b))
        L.append('')
    bl = rep.get('mescolanze_da_idle')
    if bl:
        L += ['### Attacco da «idle» e ritorno a «idle» (dissolvenze di 0,25 s)', '',
              '| Movimento | Rotazione max | Accelerazione radice (m/s2) | Piedi L / R (cm) |', '|---|---|---|---|']
        for k, v in bl.items():
            note = ' (solo dopo un ciclo: da ferma non ha senso, provata a parte)' if k == 'stop' else ''
            L.append('| %s%s | %.1f | %.1f | %s |' % (k, note, v['scatto_max'], v['accel_radice'], fmt_slide(v['scivolamento_cm'])))
        L.append('')
    df = rep.get('deformazioni (pose del test del rig)')
    if df:
        L += ['### Deformazioni nelle pose del test del rig', '',
              'Allungamento e schiacciamento = rapporto massimo e minimo tra un lato della mesh e lo stesso lato a riposo.', '',
              '| Gruppo / posa / parte | Allungamento | Schiacciamento | Volume |', '|---|---|---|---|']
        for k, v in df.items():
            L.append('| %s | %.2f | %.2f | %.3f |' % (k, v['allungamento'], v['schiacciamento'], v['volume']))
        L.append('')
    rt = rep.get('retargeting')
    if rt:
        L += ['## Retargeting', '',
              'BVH reali del database CMU (conversione cgspeed, 120 fps) e un FBX con i nomi Mixamo esportato e reimportato. '
              'Non provato su file scaricati da Mixamo o Rokoko.', '',
              '| Prova | Risultato |', '|---|---|']
        def fmtv(x):
            if isinstance(x, dict):
                return ', '.join('%s %s' % kv for kv in x.items()) or 'nessuna'
            return str(x)
        for k, v in rt.items():
            L.append('| %s | %s |' % (k, '; '.join('%s: %s' % (kk.replace('_', ' '), fmtv(vv)) for kk, vv in v.items())))
        L.append('')
    if val:
        L += ['## Fase 8: scena di prova', '',
              '`python3 cartoon_character/main.py validate`: una sola ripresa di %.1f s (%d fotogrammi) con camminata e viso felice, '
              'transizione camminata-corsa, corsa, frenata e giro, salto, sorpresa, caduta, rialzata, danza e viso felice. '
              'Il video di anteprima (360×640, EEVEE, luce cinema, etichette per ogni prova) si rifà con lo stesso comando in '
              '`out/validate/validate_360x640.mp4`; un fotogramma per prova è in [img/scena_prova.jpg](img/scena_prova.jpg).'
              % (val['durata_s'], val['fotogrammi']), '']
        md = os.path.join(VAL, 'REPORT.md')
        if os.path.exists(md):
            body = open(md).read().split('\n')
            body = [('#' + x) if x.startswith('## ') else x for x in body if not x.startswith('# ')]
            L += body
    L += ['## Limiti noti', '',
          '- **Pieghe interne nelle flessioni profonde**: con il ginocchio oltre i 120 gradi (corsa, rialzata) e il gomito oltre i 130 i '
          'lati interni della mesh si schiacciano (fino al 3% della lunghezza a riposo); i volumi restano stabili. Nei primi piani '
          'dei fotogrammi peggiori della scena di prova la piega non si vede ([immagine](img/pieghe_fotogrammi_peggiori.jpg): '
          'ginocchia nella corsa, busto nella rialzata, mano nella danza). Lo strato «Corrective Smooth» di Blender è stato '
          'provato e non migliora le misure, quindi non è stato aggiunto.',
          '- **Dita grosse**: nel pugno la piega interna delle dita si schiaccia (17%).',
          '- **Frusta del lancio**: nel «throw» il braccio ruota su se stesso di circa 85 gradi in un fotogramma (limite alzato a 90 per '
          'questo movimento).',
          '- **Retargeting**: provato su BVH CMU e su un FBX con i nomi Mixamo creato qui; non su file scaricati da Mixamo o Rokoko. '
          'Le mani dei mocap umani vengono tenute fuori dalla testa del personaggio, che è molto più grande: i gesti vicino al viso '
          'diventano gesti di lato.',
          '- **Ciuffo**: nella posa di riposo del rig è dritto; la forma a «?» la dà lo strato del viso.', '']
    path = os.path.join(HERE, 'docs', 'TEST.md')
    with open(path, 'w') as fh:
        fh.write('\n'.join(L))
    print(path)


if __name__ == '__main__':
    main()
