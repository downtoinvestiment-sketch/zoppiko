# Architettura e scelte tecniche

Questo documento segue le fasi del master prompt: ambiente, strumenti, rig, libreria dei movimenti, API, struttura dei
file. Il design del personaggio è in [DESIGN.md](DESIGN.md), i risultati dei test in [TEST.md](TEST.md).

## Fase 1: ambiente (rapporto tecnico)

| Voce | Valore misurato |
|---|---|
| Blender | 5.3.0, usato come modulo Python (`bpy`) su Python 3.13.18, senza interfaccia |
| Motori di render | solo EEVEE (Cycles non è compilato in questo `bpy`) |
| Grafica | OpenGL via software, nessuna GPU |
| CPU e memoria | 2 core, circa 8 GB di RAM |
| Video | ffmpeg 6.1.1 |
| Tempi di render (EEVEE, luce cinema) | ~5 s a fotogramma a 260×400 con 4 campioni; ~8,5 s a 360×640 con 6; ~18 s a 420×640 con 16 |

Conseguenze sul progetto:

- niente simulazioni pesanti: cinematica, IK, molle e contatti sono calcolati in Python e poi «cotti» nel rig come
  Action (FK puro), così il render legge solo curve;
- i render vanno a pezzi e si riprendono dal primo fotogramma mancante; mai due render insieme (8 GB);
- nessuna installazione: bastano gli importatori/esportatori di Blender (BVH, FBX), numpy e ffmpeg, già presenti.

## Fase 2: strumenti valutati

| Strumento | Cosa offre | Licenza e costi | Scelta |
|---|---|---|---|
| Rigify (incluso in Blender) | rig completo con controlli IK/FK | GPL, incluso | funziona anche senza interfaccia, ma genera 706 ossa: pesante da comandare da codice. Usato come riferimento per la gerarchia, non come rig |
| Plugin Rokoko per Blender | streaming dalle tute Rokoko e retargeting | gratuito; il retargeting nel plugin non richiede un account a pagamento | non installato: serve il loro flusso con interfaccia; il retargeting che ci serve è scritto qui |
| Rokoko Studio e Motion Library | registrazione, pulizia e libreria di animazioni | piano Starter gratuito, Basic 20 $/mese e Plus 50 $/mese (annuali); animazioni della libreria a 3 o 6 $ | compatibile: esporta FBX, che il nostro retargeting legge |
| Estensione «Retarget» (extensions.blender.org) | retargeting con interfaccia; fork di Expy Kit e AnimAide | gratuita; solo Blender 5 e successivi | non usata: pensata per l'interfaccia, non per una pipeline senza GUI |
| Mixamo (Adobe) | personaggi e animazioni mocap | gratis con un Adobe ID; uso senza royalty in progetti personali, commerciali e non profit; vietato ridistribuire i file grezzi | compatibile: tabella dei nomi `mixamorig:` in `config.MIXAMO` |
| Database CMU | 2.600 sequenze mocap (ASF/AMC, conversioni BVH) | gratis anche per prodotti commerciali; vietato rivendere i dati, anche convertiti | usato nei test (BVH della conversione cgspeed) |
| Shape keys e driver di Blender | forme della bocca, pupille, rossore | inclusi | usati: le proprietà dell'osso `face` guidano le shape keys |
| API Python di Blender 5 | Action a slot, layer e strip, channelbag | inclusa | usata per scrivere le animazioni (`blending.write_action`) |

## Fase 4: rig

- **Gerarchia umanoide** compatibile con Mixamo e CMU: `root > hips > spine > chest > neck > head`, clavicola, braccio,
  avambraccio, mano con pollice e tre dita (3 falangi), coscia, stinco, piede, punta. Le ossa destre sono le sinistre
  specchiate.
- **IK/FK**: vincoli IK su braccia e gambe con poli, accesi da proprietà sull'osso `root` (`ik_arm.L`, `ik_leg.R`, ...).
  La pipeline cuoce sempre FK puro: l'IK lo risolve il Python (due ossa, analitico, con estensione morbida), così il
  risultato è identico in ogni render.
- **Cinematica in Python identica a Blender** (verificata a meno di 0,1 mm su pose casuali, anche con scala).
- **Viso**: occhi come ossa (ognuno si muove da solo, riflessi fissi sulla testa); palpebre e sopracciglia come ossa che
  ruotano su gusci sferici; bocca come decalcomania 2,5D proiettata sulla testa con 15 shape keys (lingua e denti
  compresi); pupille e rossore come shape keys. L'osso `face` porta le proprietà; i driver le passano alle shape keys.
- **Ciuffo a «?»**: catena di 14 ossa su un tubo dritto; le forme (domanda, esclamazione, giù) sono pose della catena,
  e in più c'è una molla che lo fa muovere in ritardo.
- **Pesi**: calcolati da formule (non dipinti), con dissolvenze lunghe a gomito, ginocchio, dita e busto; al massimo 4
  ossa per vertice, somma 1; «preserve volume» (dual quaternion) su braccia, gambe e ciuffo.

## Fase 5: libreria dei movimenti

31 movimenti (i 30 richiesti più `get_up`, per rialzarsi da terra) in `animation/motion_library.py` e
`animation/procedural.py`:

- **formato delle clip** (`clip.py`): chiavi per osso con interpolazione di Hermite, bersagli IK per piedi e mani
  (anche relativi alla testa, per le mani sul viso), forme della mano, rotolamento tallone-pianta dei piedi, viso,
  eventi (per gli oggetti) e stato iniziale e finale (in piedi, a terra, seduto);
- **locomozione procedurale**: camminata, corsa e scatto sono cicli analitici in cui il piede appoggiato resta fermo per
  costruzione; giro e frenata sono passi pianificati;
- **controlli per ogni movimento** (test automatici): durata, fluidità, posa iniziale e finale, scivolamento dei piedi,
  pavimento, compenetrazioni, chiusura dei cicli, attacco da «idle» senza scatti.

## Fase 6: API e compositore

L'API è descritta nel [README](../README.md). Sotto, il compositore (`animation/blending.py`) mette in fila le clip:

1. ogni clip parte dalla posizione e dalla direzione in cui è finita la precedente (radice nel mondo);
2. transizioni con dissolvenza (quaternioni senza salti di emisfero); dopo camminata o corsa arriva da sola una frenata
   vera, che parte dal passo giusto del ciclo;
3. strati sopra il corpo, in quest'ordine: espressioni, sguardo (collo 35%, testa 60%, occhi con convergenza), labiale,
   battiti delle palpebre, blocco dei piedi (annulla lo scivolamento del punto a terra), pavimento, braccia fuori dal
   corpo (`collide.py`), molle del ciuffo, traiettorie degli oggetti (presi, lanciati, spinti);
4. `write_action` scrive tutto in una Action di Blender 5 (slot, layer, strip, channelbag).

## Retargeting (BVH e FBX)

`animation/retarget.py`, usato da `Character.play_file` e da `main.py retarget`:

1. importa il file con l'importatore di Blender (BVH: legge anche gli fps dal file; i CMU sono a 120 fps);
2. riconosce i nomi: tabelle Mixamo e CMU (vince quella che copre più ossa principali, perché i due schemi hanno molti
   nomi in comune), altrimenti parole chiave con il lato letto dal nome originale (`LHipJoint`, `upperarm_l`, `Hand.L`);
3. gira la sorgente perché guardi -Y come il personaggio, salta la posa a T aggiunta in testa ai file (cgspeed);
4. allinea le pose di riposo con le direzioni tra le giunture (non con le code delle ossa, che negli import sono
   arbitrarie): una sorgente in T e il nostro rig in A combaciano;
5. trasferisce le rotazioni nel mondo; scala = rapporto tra le gambe; il bacino segue il punto tra le anche;
6. il movimento a terra e la direzione del corpo passano alla radice (smussati): la clip si concatena alle altre;
7. dita non mappate in posa rilassata; mani e avambracci tenuti fuori dal corpo (il nostro è più tondo di quello
   catturato); piedi appoggiati al pavimento; poi il blocco dei piedi del compositore.

Verifiche (dettagli in [TEST.md](TEST.md)): camminata CMU 02_01, salto 16_01 e gesti 13_27; FBX con i nomi Mixamo
esportato e reimportato (errore massimo 0,64 cm). Non verificato su file scaricati da Mixamo o Rokoko.

## Fase 7: struttura dei file

La struttura proposta nel master prompt è stata seguita e allargata dove Blender lo richiedeva:

| Proposta | Realizzata | Perché |
|---|---|---|
| `character/model.py`, `rig.py`, `facial.py` | più `geometry.py`, `skeleton.py`, `builder.py` | le forme sono funzioni pure riusate da corpo e viso; la cinematica in Python serve a IK, test e retargeting |
| `animation/retarget.py`, `motion_library.py`, `blending.py` | più `clip.py`, `procedural.py`, `face.py`, `collide.py` | formato delle clip, locomozione, espressioni e volumi del corpo sono parti separate e testate da sole |
| `automation/controller.py` | più `scene.py`, `scene_json.py` | studio, luci cinema, render a pezzi; scene descritte in JSON |
| `tests/` | `test_rig`, `test_motions`, `test_api`, `test_retarget`, `validate.py`, `metrics.py` | misure condivise tra test e Fase 8 |
| `assets/` | `models`, `animations`, `textures`, `materials` | i file generati (`.blend`, BVH, rendering) restano fuori da git |
| `main.py`, `config.py` | uguali | una sola riga di comando e un solo file di misure e limiti |

## Fonti

- Mixamo, domande frequenti (Adobe): https://helpx.adobe.com/gr_en/creative-cloud/faq/mixamo-faq.html
- Mixamo, licenze e ridistribuzione (FAQ della comunità Adobe): https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/td-p/13234775
- Rokoko, prezzi: https://rokoko.com/pricing/
- Rokoko, retargeting in Blender senza account a pagamento: https://support.rokoko.com/hc/en-us/articles/4410463481489
- Rokoko Motion Library, prezzi delle animazioni: https://marketplace.autodesk.com/apps/6abdb119-cb73-4e68-ac10-e3736f639669
- Estensione Retarget per Blender 5: https://extensions.blender.org/add-ons/retarget/
- Expy Kit: https://github.com/pKrime/Expy-Kit
- Database CMU: http://mocap.cs.cmu.edu/ (licenza nella pagina principale e in http://mocap.cs.cmu.edu/faqs.php)
- Conversione BVH di B. Hahne (cgspeed): READMEFIRST v1.1 del 2010, citato nei file scaricati; sito www.cgspeed.com
