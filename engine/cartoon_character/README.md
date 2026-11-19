# Ciuffo: personaggio cartoon 3D comandato da Python (Blender)

Un personaggio originale, pensato per video social e divulgazione: si costruisce da codice, ha un rig compatibile con
Mixamo e CMU, una libreria di 31 movimenti, 16 espressioni, sguardo, labiale e oggetti, e si comanda con poche righe.
Ogni animazione si genera da sola: si sceglie il movimento, si assegna l'espressione, si cuoce e si rende.

Il nome «Ciuffo» è provvisorio: si cambia in `config.py` (`NAME`).

## Avvio rapido

Serve il Python con il modulo `bpy` (Blender 5.x come modulo). Dalla cartella che contiene `cartoon_character/`:

```python
import bpy
from cartoon_character.automation import scene as S
from cartoon_character.automation.controller import Character

sc = S.reset()
studio = S.stage(sc)
cam = S.camera(sc, studio, (0.9, -3.2, 0.85), (0, 0, 0.55), 45)
S.cinema_lights(studio, (0, 0, 0.6), (0.9, -3.2, 0.85))

ch = Character('Ciuffo', 'default')          # varianti: default, blu, lime
ch.play('idle', duration=1.0)
ch.look_at('camera')
ch.play('cammina', duration=2.5)             # nomi inglesi o italiani
ch.set_expression('felice')                  # vale dalla clip appena aggiunta in poi
ch.play('salta')                             # prima della clip ferma arriva da sola la frenata
ch.say('Ciao! Oggi parliamo di scienza', duration=2.0)
ch.walk_to((0.8, -0.6))                      # si gira, cammina e si ferma esattamente lì
ch.play('cadi'); ch.play('balla')            # da terra si rialza da solo prima di ballare
ch.bake()                                    # scrive l'animazione nel rig (Action)

S.setup_render(sc, 540, 960, 8)
S.render_frames(sc, 'out/demo', 1, ch.frames)    # si riprende da dove si era fermato
S.encode('out/demo', 'out/demo.mp4')
```

Le stesse cose senza Python, con una scena in JSON: `python3 cartoon_character/main.py render cartoon_character/examples/saluto.json`
(formato in [docs/SCENE_JSON.md](docs/SCENE_JSON.md)).

## Comandi

```
python3 cartoon_character/main.py build [variante]       # costruisce il personaggio e salva assets/models/<nome>_<variante>.blend
python3 cartoon_character/main.py library                # elenca movimenti ed espressioni
python3 cartoon_character/main.py test [rig motions api retarget]   # test automatici + rapporto JSON in out/
python3 cartoon_character/main.py validate               # scena di prova della Fase 8: misure + video (si riprende)
python3 cartoon_character/main.py render scena.json      # scena descritta in JSON -> video
python3 cartoon_character/main.py retarget file.bvh      # prova un'animazione esterna sul personaggio
python3 cartoon_character/main.py sheets                 # schede: giro attorno ed espressioni
```

## Cosa sa fare

| Categoria | Movimenti |
|---|---|
| Locomozione | idle, walk, run, jump, sprint, turn, stop |
| Reazioni | surprise, shock, fear, confusion, happiness, anger, sadness |
| Comicità | fall, trip, slip, dance, celebrate, facepalm, look_around, exaggerated_reaction |
| Interazioni | point, wave, pick_up, throw, push, pull, sit, stand_up (+ get_up, per rialzarsi da terra) |

Espressioni: neutral, happy, joy, sad, angry, surprised, shocked, scared, confused, thinking, disgust, embarrassed, smug,
determined, sleepy, dizzy (si possono mescolare e dosare con `intensity`). Gli alias italiani sono in `config.ALIASES`.

L'API (`automation/controller.py`):

| Metodo | Cosa fa |
|---|---|
| `play(nome, duration, loops, blend, speed, **parametri)` | aggiunge un movimento; gestisce gli stati (a terra, seduto) e la frenata dopo camminata e corsa |
| `walk_to((x, y))`, `turn(gradi)`, `wait(s)` | spostamenti precisi nel mondo (arrivo entro pochi millimetri) |
| `set_expression(nome, at, duration, intensity)` | espressione del viso, con dissolvenze |
| `look_at('camera' | punto | altro personaggio)`, `look_forward()` | sguardo con collo, testa e occhi (convergenza compresa) |
| `say(testo, duration, words)` | labiale dal testo; con `words` usa i tempi di Whisper |
| `pick_up(oggetto)`, `throw(punto)`, `push(scatola)`, `pull(scatola)`, `sit()`, `point(bersaglio)`, `wave()` | interazioni; gli oggetti si muovono con la mano e cadono con la gravità |
| `play_file('file.bvh' | 'file.fbx')` | animazione esterna (mocap CMU, Mixamo, Rokoko) trasferita sul personaggio |
| `bake()` | scrive tutto nel rig e negli oggetti; restituisce i fotogrammi calcolati |

Strati automatici: battiti delle palpebre, ciuffo con molle (si muove in ritardo), blocco dei piedi a terra (niente
scivolate), pavimento, mani e avambracci tenuti fuori da testa, busto e gambe.

## Animazioni esterne

`play_file` e `main.py retarget` leggono BVH e FBX con gli importatori di Blender, riconoscono da soli i nomi di Mixamo,
CMU e degli scheletri tipo Unreal, e trasferiscono il movimento allineando le pose di riposo. Provati su BVH reali del
database CMU (camminata, salto, gesti) e su un FBX con i nomi Mixamo creato qui; **non** su file scaricati da Mixamo,
che servono un account Adobe e non si possono ridistribuire. Dettagli e licenze in [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

I BVH CMU usati nei test vanno in `assets/animations/cmu/` (conversione cgspeed del database CMU); non sono nel
repository.

## File

```
cartoon_character/
  main.py            riga di comando
  config.py          misure, colori, scheletro, espressioni, limiti dei test: tutto in un posto
  character/         geometry.py (forme), model.py (corpo), facial.py (viso), rig.py (scheletro e controlli),
                     skeleton.py (cinematica e IK in Python), builder.py (mette insieme il personaggio)
  animation/         clip.py (formato delle clip), procedural.py (camminata, corsa, passi), motion_library.py (31 movimenti),
                     face.py (espressioni), blending.py (compositore: transizioni, sguardo, labiale, piedi, molle),
                     retarget.py (BVH/FBX), collide.py (volumi del corpo e correzione delle braccia)
  automation/        controller.py (API Character), scene.py (studio, luci cinema, camera, render), scene_json.py
  tests/             test_rig, test_motions, test_api, test_retarget, validate.py (Fase 8), metrics.py
  tools/             schede del personaggio
  examples/          scene JSON di esempio
  docs/              ARCHITETTURA.md, DESIGN.md, SCENE_JSON.md, TEST.md
  assets/            modelli, animazioni, texture e materiali (i file generati restano fuori da git)
```

## Stato

Test automatici: 28 su 28 superati (rig, movimenti, API, retargeting, scena JSON). Scena di prova della Fase 8 con
misure e video: [docs/TEST.md](docs/TEST.md). Limiti noti, misurati e non nascosti, nella stessa pagina.
