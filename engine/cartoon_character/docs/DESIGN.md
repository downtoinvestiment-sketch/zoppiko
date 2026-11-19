# Design del personaggio (Fase 3)

Obiettivo: un personaggio originale, simpatico a colpo d'occhio, con emozioni leggibili anche sullo schermo di un
telefono, e facile da animare da codice. È costruito da forme semplici scritte in Python (`character/`), senza partire
da personaggi esistenti.

## Principi e da dove vengono

| Principio | Studio | Come è applicato |
|---|---|---|
| **Schema del bambino**: viso tondo e fronte alta rendono un volto più tenero e attirano attenzione e cura | Glocker et al. 2009, *Ethology* 115(3):257-263: lo hanno dimostrato manipolando foto di neonati (prima prova sperimentale su volti veri) | testa grande e tonda (circa 2,7 teste di altezza in tutto), fronte alta, guance piene, mento morbido, naso e bocca piccoli, corpo rotondo con arti corti |
| **Occhi grandi** da soli aumentano la tenerezza percepita, con ogni espressione | Yao et al. 2022, *Frontiers in Psychology* 12:674456 | occhi di 13 cm di diametro su una testa larga 40, bassi sul viso; pupille che si dilatano nella tenerezza e si stringono nella paura |
| **Caricatura delle espressioni**: esagerare la differenza dal viso neutro rende l'emozione più intensa e più veloce da riconoscere, ma oltre un certo punto il volto sembra meno un volto | Calder et al. 2000, *Cognition* 76(2):105-146 | sopracciglia, palpebre e bocca con escursioni ampie, ma ogni espressione resta dentro forme da viso; il ciuffo amplifica (punto esclamativo nella sorpresa, giù nella tristezza) |
| **Antropomorfismo**: attribuiamo emozioni e intenzioni a ciò che ha tratti e comportamenti umani, soprattutto quando ci aiutano a capire che cosa farà | Epley, Waytz e Cacioppo 2007, *Psychological Review* 114(4):864-886 | sguardo che segue la camera o un altro personaggio, occhi che convergono, battiti delle palpebre, reazioni che anticipano l'azione (si sorprende prima di cadere) |

## Silhouette e firma visiva

- **Il ciuffo a «?»** è la firma: richiama la curiosità della divulgazione scientifica e cambia forma con l'emozione
  (punto di domanda a riposo e nella confusione, punto esclamativo nella sorpresa, giù nella tristezza). Si legge anche
  in miniatura o in controluce.
- **Testa e ciuffo** si riconoscono da soli in una copertina; mani e scarpe grandi rendono leggibili i gesti e i passi.
- **Mani con pollice e tre dita**: convenzione del cartoon, gesti più chiari e meno ossa da animare.

## Colori

| Variante | Pelle | Maglietta | Pantaloncini | Scarpe | Uso |
|---|---|---|---|---|---|
| default | corallo `#FF9466` | verde petrolio `#1C8C8C` | blu notte `#1F2C52` | crema con suola petrolio | personaggio principale |
| blu | azzurro `#7FB2FF` | arancio `#FFB23F` | grafite `#2B2B3A` | bianche con suola arancio | secondo personaggio |
| lime | verde `#9BD45A` | viola `#7A4FD1` | melanzana `#2A2440` | avorio con suola viola | terzo personaggio |

La pelle non ha un colore umano realistico: il personaggio resta un cartoon, senza richiamare un'etnia. Ogni variante
abbina colori complementari (corallo e petrolio, azzurro e arancio, verde e viola) per staccare il corpo dalla maglietta.

## Espressioni

16 espressioni costruite con gli stessi canali (`config.EXPRESSIONS`): alzata, inclinazione e avvicinamento delle
sopracciglia, apertura e inclinazione delle palpebre, palpebra inferiore (il sorriso «degli occhi»), pupille, rossore,
forme della bocca, forma del ciuffo e direzione degli occhi. Si mescolano tra loro e si dosano con l'intensità:
neutral, happy, joy, sad, angry, surprised, shocked, scared, confused, thinking, disgust, embarrassed, smug, determined,
sleepy, dizzy. Le schede con il giro attorno e i primi piani si rifanno con `main.py sheets`.

## Fonti

- Glocker, M. L. et al. (2009). Baby schema in infant faces induces cuteness perception and motivation for caretaking
  in adults. *Ethology*, 115(3), 257-263. https://repository.upenn.edu/cog_neuro_pubs/11
- Yao, L. et al. (2022). Eye size affects cuteness in different facial expressions and ages. *Frontiers in Psychology*,
  12, 674456. https://www.frontiersin.org/articles/10.3389/fpsyg.2021.674456
- Calder, A. J. et al. (2000). Caricaturing facial expressions. *Cognition*, 76(2), 105-146.
  https://www.mrc-cbu.cam.ac.uk/bibliography/articles/3988
- Epley, N., Waytz, A., Cacioppo, J. T. (2007). On seeing human: a three-factor theory of anthropomorphism.
  *Psychological Review*, 114(4), 864-886. https://pubmed.ncbi.nlm.nih.gov/17907867/
