# Test e misure

Pagina generata da `tools/test_doc.py` con i rapporti di `main.py test` e `main.py validate`. Tutti i numeri sono misurati, nessuno è stimato. Limiti (`config.LIMITS`): scivolamento del piede appoggiato 1.0 cm, suola sotto il pavimento 0.8 cm, compenetrazione tra parti del corpo 1.5 cm (contatti voluti, come la mano sul viso, fino a 6 cm), rotazione di un osso tra due fotogrammi 75 gradi (90 per il lancio), allungamento della mesh 2.3 volte, schiacciamento fino a 0.25.

## Test automatici

`python3 cartoon_character/main.py test`: **28 test, 0 falliti, 0 errori** in 19 s.

| Gruppo | Cosa verifica |
|---|---|
| rig (11) | gerarchia umanoide, pesi (somma 1, massimo 4 ossa), cinematica Python identica a Blender, IK, occhi indipendenti, palpebre che si chiudono, sopracciglia sulla fronte, bocca (lingua e denti dentro), shape keys guidate, pose ampie senza collassi |
| movimenti (3) | i 31 movimenti uno per uno; attacco a «idle» prima e dopo; camminata, frenata, giro, corsa, frenata |
| API (10) | play ed espressioni, espressione senza durata, nomi italiani, sguardo, walk_to (errore 0.0 cm), stati a terra e seduto, raccogli e lancia, labiale, due personaggi che si guardano, scena JSON (la palla tocca terra a 3.8 cm dal punto di lancio) |
| retargeting (4) | mappatura automatica (Mixamo, CMU, nomi Unreal), BVH CMU reali, FBX con i nomi Mixamo andata e ritorno |

## Libreria dei movimenti

Ogni movimento da solo. Scarto della posa iniziale e finale da quella in piedi, in gradi (vuoto per cicli e movimenti che finiscono a terra o seduti).

| Movimento | Categoria | Durata (s) | Piedi L / R (cm) | Suola min (cm) | Rotazione max (gradi/fotogramma) | Compenetrazioni (cm) | Pose inizio / fine |
|---|---|---|---|---|---|---|---|
| idle | locomotion | 4.00 | 0.01 / 0.01 | 0.02 | 0.3 (shin.R) | - | - / - |
| walk | locomotion | 0.84 | 0.04 / 0.03 | -0.00 | 14.7 (thigh.L) | - | - / - |
| run | locomotion | 0.56 | 0.00 / 0.00 | -0.00 | 42.4 (thigh.L) | - | - / - |
| jump | locomotion | 1.55 | 0.00 / 0.00 | -0.36 | 59.9 (upper_arm.R) | - | 0.1 / 0.1 |
| sprint | locomotion | 0.46 | 0.00 / 0.00 | -0.00 | 71.4 (thigh.L) | - | - / - |
| turn | locomotion | 1.15 | 0.00 / 0.00 | -0.00 | 21.8 (shin.L) | footL-footR 0.2 | 9.3 / 9.3 |
| stop | locomotion | 1.25 | 0.00 / 0.00 | -0.00 | 20.4 (shin.L) | - | - / 0.2 |
| surprise | reactions | 1.40 | 0.02 / 0.02 | -0.00 | 53.3 (forearm.L) | - | 0.1 / 0.1 |
| shock | reactions | 2.00 | 0.00 / 0.00 | -0.08 | 25.1 (foot.R) | - | 0.1 / 0.1 |
| fear | reactions | 2.70 | 0.01 / 0.00 | -0.00 | 58.4 (forearm.L) | - | 0.1 / 0.1 |
| confusion | reactions | 2.70 | 0.00 / 0.00 | 0.18 | 67.3 (forearm.R) | - | 0.1 / 0.1 |
| happiness | reactions | 2.20 | 0.01 / 0.01 | -0.34 | 37.6 (upper_arm.R) | - | 0.1 / 0.1 |
| anger | reactions | 2.40 | 0.02 / 0.01 | -0.00 | 39.1 (shin.R) | - | 0.1 / 10.0 |
| sadness | reactions | 3.00 | 0.00 / 0.00 | -0.00 | 2.2 (shin.L) | - | 0.1 / - |
| fall | comedy | 2.50 | 0.01 / 0.01 | -0.01 | 55.1 (forearm.L) | - | 0.1 / - |
| trip | comedy | 1.90 | 0.03 / 0.03 | -0.16 | 72.0 (shin.R) | handL-handR 2.3 | 0.1 / 0.1 |
| slip | comedy | 2.30 | 0.00 / 0.01 | -0.06 | 49.2 (shin.L) | handL-handR 5.8 | 0.1 / - |
| dance | comedy | 4.00 | 0.00 / 0.02 | -0.00 | 12.5 (upper_arm.R) | - | - / - |
| celebrate | comedy | 2.10 | 0.00 / 0.00 | -0.02 | 58.7 (upper_arm.R) | - | 0.1 / 0.1 |
| facepalm | comedy | 2.80 | 0.00 / 0.00 | 0.18 | 55.3 (hand.R) | - | 0.1 / 0.1 |
| look_around | comedy | 3.20 | 0.01 / 0.01 | 0.17 | 6.9 (head) | - | 0.1 / 0.1 |
| exaggerated_reaction | comedy | 2.30 | 0.01 / 0.01 | -0.00 | 63.0 (upper_arm.R) | - | 0.1 / 0.1 |
| point | interactions | 1.70 | 0.00 / 0.01 | 0.17 | 34.8 (forearm.L) | - | 0.1 / 0.1 |
| wave | interactions | 2.10 | 0.01 / 0.01 | 0.02 | 60.2 (forearm.R) | - | 0.1 / 0.1 |
| pick_up | interactions | 2.40 | 0.01 / 0.01 | -0.00 | 28.7 (forearm.L) | - | 0.1 / - |
| throw | interactions | 1.70 | 0.04 / 0.01 | -0.00 | 84.8 (upper_arm.R) | - | - / 0.1 |
| push | interactions | 2.70 | 0.01 / 0.00 | -0.00 | 29.8 (forearm.L) | - | 0.1 / 0.1 |
| pull | interactions | 2.70 | 0.01 / 0.01 | -0.00 | 24.1 (shin.R) | - | 0.1 / 0.1 |
| sit | interactions | 1.80 | 0.00 / 0.00 | -0.00 | 16.6 (forearm.L) | - | 0.1 / - |
| stand_up | interactions | 1.70 | 0.00 / 0.00 | -0.00 | 16.3 (forearm.L) | - | - / 0.1 |
| get_up | interactions | 2.50 | 0.00 / 0.00 | -0.26 | 15.7 (shin.L) | - | - / 0.6 |

### Attacco da «idle» e ritorno a «idle» (dissolvenze di 0,25 s)

| Movimento | Rotazione max | Accelerazione radice (m/s2) | Piedi L / R (cm) |
|---|---|---|---|
| walk | 29.9 | 11.1 | 0.73 / 0.03 |
| run | 42.3 | 27.8 | 0.24 / 0.01 |
| jump | 59.9 | 0.0 | 0.09 / 0.07 |
| sprint | 74.4 | 45.2 | 0.23 / 0.01 |
| turn | 16.6 | 0.0 | 0.01 / 0.03 |
| stop (solo dopo un ciclo: da ferma non ha senso, provata a parte) | 22.1 | 5.0 | 9.65 / 0.01 |
| surprise | 30.2 | 0.0 | 0.06 / 0.05 |
| shock | 11.8 | 0.0 | 0.03 / 0.03 |
| fear | 58.4 | 0.0 | 0.09 / 0.01 |
| confusion | 67.3 | 0.0 | 0.02 / 0.02 |
| happiness | 30.9 | 0.0 | 0.04 / 0.04 |
| anger | 39.1 | 0.0 | 0.02 / 0.02 |
| sadness | 4.6 | 0.0 | 0.05 / 0.05 |
| fall | 55.1 | 1.9 | 0.02 / 0.02 |
| trip | 72.0 | 5.9 | 0.03 / 0.04 |
| slip | 49.2 | 1.8 | 0.00 / 0.01 |
| dance | 17.5 | 0.0 | 0.02 / 0.05 |
| celebrate | 58.7 | 0.0 | 0.05 / 0.05 |
| facepalm | 55.3 | 0.0 | 0.02 / 0.02 |
| look_around | 6.9 | 0.0 | 0.04 / 0.04 |
| exaggerated_reaction | 63.0 | 0.0 | 0.08 / 0.08 |
| point | 32.8 | 0.0 | 0.02 / 0.03 |
| wave | 60.2 | 0.0 | 0.02 / 0.03 |
| pick_up | 65.2 | 2.8 | 0.07 / 0.10 |
| push | 29.8 | 0.8 | 0.02 / 0.02 |
| pull | 24.1 | 0.8 | 0.02 / 0.02 |
| sit | 21.3 | 0.0 | 0.03 / 0.03 |

### Deformazioni nelle pose del test del rig

Allungamento e schiacciamento = rapporto massimo e minimo tra un lato della mesh e lo stesso lato a riposo.

| Gruppo / posa / parte | Allungamento | Schiacciamento | Volume |
|---|---|---|---|
| moderate/braccia_su/arm.L | 1.20 | 0.80 | 1.000 |
| moderate/braccia_su/arm.R | 1.20 | 0.80 | 1.000 |
| moderate/gomiti_90/arm.L | 1.65 | 0.37 | 1.000 |
| moderate/gomiti_90/arm.R | 1.65 | 0.37 | 1.000 |
| moderate/ginocchia_100/leg.L | 1.74 | 0.26 | 1.000 |
| moderate/ginocchia_100/leg.R | 1.52 | 0.50 | 1.000 |
| moderate/busto/torso | 1.76 | 0.62 | 0.923 |
| moderate/dita_45/hand.L | 1.80 | 0.19 | 0.994 |
| moderate/dita_45/hand.R | 1.80 | 0.19 | 0.994 |
| estreme/pugno_80/hand.L | 2.30 | 0.17 | 0.982 |
| estreme/pugno_80/hand.R | 2.30 | 0.17 | 0.982 |
| estreme/gomito_140/arm.L | 1.95 | 0.09 | 1.000 |
| estreme/ginocchio_130/leg.L | 1.92 | 0.03 | 1.000 |

## Retargeting

BVH reali del database CMU (conversione cgspeed, 120 fps) e un FBX con i nomi Mixamo esportato e reimportato. Non provato su file scaricati da Mixamo o Rokoko.

| Prova | Risultato |
|---|---|
| CMU 16_01 (salto) | durata s: 2.67; scatto max: 25.6; suola minima cm: -0.18; compenetrazioni cm: nessuna |
| CMU 13_27 (saluto e indica) | durata s: 4.96; scatto max: 38.6; suola minima cm: -0.36; compenetrazioni cm: nessuna |
| CMU 02_01 (camminata) | durata s: 2.83; distanza m: 1.28; ossa mappate: 21; scivolamento cm: L 0.0, R 0.0; appoggi: L 3, R 2; suola minima cm: -0.36; scatto max: 19.4; compenetrazioni cm: nessuna |
| FBX nomi Mixamo (andata e ritorno) | ossa mappate: 33; errore max cm: 0.64; rotazione iniziale tolta gradi: 0.17 |

## Fase 8: scena di prova

`python3 cartoon_character/main.py validate`: una sola ripresa di 18.7 s (450 fotogrammi) con camminata e viso felice, transizione camminata-corsa, corsa, frenata e giro, salto, sorpresa, caduta, rialzata, danza e viso felice. Il video di anteprima (360×640, EEVEE, luce cinema, etichette per ogni prova) si rifà con lo stesso comando in `out/validate/validate_360x640.mp4`; un fotogramma per prova è in [img/scena_prova.jpg](img/scena_prova.jpg).


Generato da `python3 cartoon_character/main.py validate`. 450 fotogrammi a 24 fps (18.7 s). Limiti da `config.LIMITS`: scivolamento 1.0 cm, suola 0.8 cm sotto il pavimento, compenetrazione 1.5 cm, scatto 75 gradi per fotogramma.

| # | Segmento | Secondi | Piedi L/R (cm) | Suola min (cm) | Scatto max | Compenetrazioni (cm) | Esito |
|---|---|---|---|---|---|---|---|
| 1 | Camminata + viso felice | 0.88-4.28 | 0.72 / 0.04 | -0.37 | 39.2 (forearm.L) | - | OK |
| 7 | Da camminata a corsa | 3.86-4.58 | 0.04 / 0.01 | -0.37 | 40.8 (thigh.L) | - | OK |
| 2 | Corsa | 4.16-6.36 | 0.04 / 0.01 | -0.37 | 42.4 (thigh.R) | - | OK |
| - | Frenata e giro | 6.29-8.16 | 0.02 / 0.00 | -0.38 | 35.3 (foot.L) | footL-footR 0.2 | OK |
| 3 | Salto | 7.91-9.46 | 0.02 / 0.02 | -0.38 | 56.0 (upper_arm.R) | - | OK |
| 5 | Reazione: sorpresa | 9.21-10.61 | 0.03 / 0.03 | 0.10 | 29.1 (forearm.R) | - | OK |
| 4 | Caduta | 10.36-12.86 | 0.01 / 0.01 | -0.40 | 53.3 (forearm.R) | - | OK |
| - | Si rialza | 12.61-15.11 | 0.00 / 0.00 | -0.40 | 18.3 (forearm.R) | - | OK |
| 6 | Danza + viso felice | 14.86-18.06 | 0.03 / 0.02 | -0.16 | 18.3 (forearm.R) | - | OK |

### Transizioni tra le clip

Finestra: da 0,15 s prima a 0,15 s dopo la dissolvenza.

| Da > a | Inizio (s) | Dissolvenza (s) | Piedi L/R (cm) | Scatto max | Accel. radice (m/s2) | Esito |
|---|---|---|---|---|---|---|
| idle > walk | 0.88 | 0.12 | 0.72 / 0.00 | 22.3 (thigh.R) | 11.1 | OK |
| walk > run | 4.16 | 0.12 | 0.04 / 0.00 | 40.8 (thigh.L) | 21.9 | OK |
| run > stop | 6.29 | 0.00 | 0.00 / 0.00 | 34.5 (foot.L) | 5.6 | OK |
| stop > turn | 7.01 | 0.25 | 0.02 / 0.00 | 16.9 (shin.R) | 0.0 | OK |
| turn > jump | 7.91 | 0.25 | 0.01 / 0.00 | 56.0 (upper_arm.R) | 0.0 | OK |
| jump > surprise | 9.21 | 0.25 | 0.01 / 0.01 | 29.1 (forearm.R) | 0.0 | OK |
| surprise > fall | 10.36 | 0.25 | 0.02 / 0.02 | 34.6 (upper_arm.L) | 0.0 | OK |
| fall > get_up | 12.61 | 0.25 | 0.00 / 0.00 | 9.2 (foot.L) | 0.0 | OK |
| get_up > dance | 14.86 | 0.25 | 0.00 / 0.00 | 18.3 (forearm.R) | 1.9 | OK |
| dance > idle | 17.81 | 0.25 | 0.03 / 0.02 | 15.8 (forearm.R) | 0.0 | OK |

### Deformazioni (mesh valutate, un fotogramma ogni 2)

Allungamento e compressione = rapporto massimo e minimo tra un lato della mesh e lo stesso lato a riposo; volume = rapporto con il volume a riposo (solo mesh chiuse).

| Parte | Allungamento max | Compressione min | Percentile 99 | Volume min-max | Fotogramma peggiore | Esito |
|---|---|---|---|---|---|---|
| head | 1.00 | 1.00 | 1.00 | 1.00-1.00 | 31 | OK |
| nose | 1.00 | 1.00 | 1.00 | 1.00-1.00 | 35 | OK |
| torso | 1.76 | 0.04 | 1.67 | 0.93-1.03 | 325 | piega: lati schiacciati al 4% |
| arm.L | 1.78 | 0.21 | 1.67 | 1.00-1.00 | 119 | piega: lati schiacciati al 21% |
| arm.R | 1.78 | 0.21 | 1.67 | 1.00-1.00 | 139 | piega: lati schiacciati al 21% |
| hand.L | 1.90 | 0.06 | 1.62 | 0.99-1.00 | 363 | piega: lati schiacciati al 6% |
| hand.R | 1.90 | 0.06 | 1.62 | 0.99-1.00 | 363 | piega: lati schiacciati al 6% |
| leg.L | 1.90 | 0.03 | 1.84 | 1.00-1.00 | 121 | piega: lati schiacciati al 3% |
| leg.R | 1.90 | 0.03 | 1.84 | 1.00-1.00 | 141 | piega: lati schiacciati al 3% |
| shoe.L | 1.48 | 0.31 | 1.40 | 0.98-1.00 | 103 | OK |
| shoe.R | 1.49 | 0.30 | 1.40 | 0.98-1.00 | 123 | OK |
| curl | 1.41 | 0.61 | 1.33 | 1.00-1.00 | 435 | OK |

## Limiti noti

- **Pieghe interne nelle flessioni profonde**: con il ginocchio oltre i 120 gradi (corsa, rialzata) e il gomito oltre i 130 i lati interni della mesh si schiacciano (fino al 3% della lunghezza a riposo); i volumi restano stabili. Nei primi piani dei fotogrammi peggiori della scena di prova la piega non si vede ([immagine](img/pieghe_fotogrammi_peggiori.jpg): ginocchia nella corsa, busto nella rialzata, mano nella danza). Lo strato «Corrective Smooth» di Blender è stato provato e non migliora le misure, quindi non è stato aggiunto.
- **Dita grosse**: nel pugno la piega interna delle dita si schiaccia (17%).
- **Frusta del lancio**: nel «throw» il braccio ruota su se stesso di circa 85 gradi in un fotogramma (limite alzato a 90 per questo movimento).
- **Retargeting**: provato su BVH CMU e su un FBX con i nomi Mixamo creato qui; non su file scaricati da Mixamo o Rokoko. Le mani dei mocap umani vengono tenute fuori dalla testa del personaggio, che è molto più grande: i gesti vicino al viso diventano gesti di lato.
- **Ciuffo**: nella posa di riposo del rig è dritto; la forma a «?» la dà lo strato del viso.
