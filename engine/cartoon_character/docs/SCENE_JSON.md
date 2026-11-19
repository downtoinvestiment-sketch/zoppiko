# Scene in JSON

Una scena si descrive in un file JSON e si trasforma in video con un comando:

```
python3 cartoon_character/main.py render scena.json                  # rende tutto; rilanciato riparte dal fotogramma mancante
python3 cartoon_character/main.py render scena.json --solo-cottura   # costruisce e cuoce l'animazione, niente render
python3 cartoon_character/main.py render scena.json --anteprima      # metà risoluzione, 4 campioni
python3 cartoon_character/main.py render scena.json --budget 540     # rende al massimo per 540 secondi, poi si ferma
```

I fotogrammi vanno in `out/scene/<nome>/frames_<risoluzione>/` e il video in `out/scene/<nome>/<nome>_<risoluzione>.mp4`.
Esempio completo: [`examples/saluto.json`](../examples/saluto.json) (due personaggi, una palla, saluti e un lancio).

## Struttura

```json
{
  "render":  {"resolution": [540, 960], "samples": 8, "output": "percorso/facoltativo", "audio": "voce.m4a"},
  "stage":   {"color": "#E9E2D6", "ambient": 0.30},
  "camera":  {"location": [0.6, -3.4, 0.85], "target": [0.4, 0.0, 0.55], "lens": 42, "follow": "Ciuffo", "smooth": 0.6},
  "props":   [{"name": "palla", "type": "sphere", "radius": 0.06, "location": [0, -0.6, 0.06], "color": "#E63946"}],
  "characters": [
    {"name": "Ciuffo", "variant": "default", "location": [-1.2, 0.2], "facing": 60, "actions": [ ... ]}
  ],
  "end_hold": 0.5
}
```

- **render**: risoluzione e campioni di EEVEE; `audio` (facoltativo) viene montato nel video.
- **camera**: con `follow` la camera e le luci seguono quel personaggio con una media mobile di `smooth` secondi; in quel
  caso `location` e `target` sono relativi al personaggio.
- **props**: `sphere` (radius), `box` (size [x, y, z], appoggiata a terra), `cylinder` (radius, height); `color` in esadecimale.
- **characters**: `facing` in gradi (0 = verso -Y, cioè verso una camera davanti; 90 = verso +X). Varianti: `default`,
  `blu`, `lime`. Le azioni si eseguono in ordine; ogni personaggio ha il suo tempo.

## Azioni

| Azione | Esempio | Note |
|---|---|---|
| movimento | `{"play": "jump"}`, `{"play": "walk", "duration": 2.0}`, `{"play": "turn", "angle": -90}` | nomi inglesi o italiani; `duration`, `loops`, `blend`, `speed` e i parametri del movimento |
| attesa | `{"wait": 0.8}` | idle |
| girarsi | `{"turn": 45}` | gradi, positivi verso la sinistra del personaggio |
| andare in un punto | `{"walk_to": [1.0, -0.5], "gait": "walk"}` | si gira, cammina e si ferma esattamente lì |
| espressione | `{"expression": "happy", "duration": 2.0, "intensity": 0.8}` | `at` in secondi; senza `duration` dura finché non cambia |
| sguardo | `{"look_at": "camera"}`, `{"look_at": "Bea"}`, `{"look_at": [1, -2, 0.9]}` | anche il nome di un oggetto |
| sguardo libero | `{"look_forward": true}` | |
| labiale | `{"say": "Ciao a tutti", "duration": 1.5}` | con `words: [["Ciao", 0.30, 0.62], ...]` usa i tempi di Whisper |
| oggetti | `{"pick_up": "palla"}`, `{"throw": [0, -2.5, 0]}`, `{"push": "scatola"}`, `{"pull": "scatola"}` | |
| altri gesti | `{"sit": true}`, `{"point": "camera"}`, `{"wave": true}` | |
| mocap | `{"mocap": "../assets/animations/cmu/02_01.bvh", "frames": [1, 300]}` | BVH o FBX trasferito sul personaggio; percorsi relativi al file JSON |

Se un'azione non è riconosciuta il comando si ferma con un messaggio che la nomina.
