"""Configurazione unica del personaggio e della pipeline.

Tutte le misure sono in metri, con il personaggio in piedi sull'origine e la faccia verso -Y (convenzione Blender: vista frontale).
Il lato sinistro del personaggio e' +X (suffisso .L). Le ossa destre (.R) sono costruite specchiando le sinistre.

Convenzioni degli assi locali delle ossa (servono per scrivere le pose a mano):
  * colonna, testa, gambe, braccia: asse Z locale = avanti (-Y del mondo). Rotazione X positiva = la punta dell'osso va in avanti.
  * braccia: rotazione Z positiva = il braccio si alza di lato (per entrambi i lati, perche' le pose del lato destro
    si scrivono «come se fossero il sinistro» e vengono specchiate da sole: (x, y, z) -> (x, -y, -z)).
  * dita: asse Z locale = verso il palmo. Rotazione X positiva = il dito si chiude.
  * piedi: rotazione X positiva = punta in su.
  * colonna e testa: Y positiva = gira verso la sinistra del personaggio (+X), Z positiva = si piega verso la sua destra.
"""
import math
import os

QUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(QUI, 'assets')
OUT = os.path.join(QUI, 'out')

NAME = 'Zop'                    # ZOPPIKO: personaggio principale
FPS = 24

# ------------------------------------------------------------------ colori (sRGB 0-1) e varianti
def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

VARIANTS = {
    # pelle corallo, maglietta verde petrolio, pantaloncini blu notte, scarpe crema con suola petrolio
    'default': dict(skin='#FF9466', skin_dark='#F0754C', shirt='#1C8C8C', shirt_dark='#136B6B', shorts='#1F2C52',
                    shoe='#FFF1DC', sole='#1C8C8C', iris='#3A2416', brow='#3B1F14', blush='#FF5E7A', curl='#F2753F'),
    # seconda e terza variante: per scene con piu' personaggi
    'blu': dict(skin='#7FB2FF', skin_dark='#5C8FE0', shirt='#FFB23F', shirt_dark='#E09520', shorts='#2B2B3A',
                shoe='#FFFFFF', sole='#FF6F3C', iris='#1D2A4A', brow='#1E2440', blush='#FF7DA8', curl='#6A9CF0'),
    'lime': dict(skin='#9BD45A', skin_dark='#7AB33E', shirt='#7A4FD1', shirt_dark='#5C36AE', shorts='#2A2440',
                 shoe='#FFF6E8', sole='#7A4FD1', iris='#2A2A12', brow='#2B3313', blush='#FF6E6E', curl='#86C246'),
}

# ZOPPIKO: nomi ufficiali dei due personaggi (le stesse identiche varianti: nessuna modifica al design)
VARIANTS['zop'] = VARIANTS['default']
VARIANTS['piko'] = VARIANTS['blu']

# ------------------------------------------------------------------ proporzioni (schema del bambino, 2,8 teste di altezza)
HEAD_C = (0.0, 0.0, 0.835)       # centro della testa
HEAD_R = (0.198, 0.186, 0.186)   # semiassi x (larghezza), y (profondita'), z (altezza)
CHEEK = dict(amp=0.016, sigma=0.32, dirs=((0.55, -0.62, -0.45), (-0.55, -0.62, -0.45)))   # guance piene in basso ai lati
CHIN_FLAT = 0.010                # la testa e' appena piu' piatta sotto (mento morbido)

EYE_R = 0.066                    # occhi grandi e bassi (fronte alta)
EYE_C = (0.080, -0.121, 0.811)
IRIS_DEG = 36.0
PUPIL_DEG = (15.0, 27.0)         # pupilla piccola (paura) -> grande (tenerezza); a riposo a meta'
BROW = dict(z=0.912, x=0.080, len=0.070, thick=0.0175, tilt=5.0)
NOSE = dict(z=0.763, r=(0.020, 0.016, 0.016))
MOUTH = dict(z=0.716, half_w=0.036, scale=(1.45, 1.35))   # scala (larghezza, apertura) di tutte le forme
BLUSH = dict(x=0.128, z=0.752, r=(0.030, 0.019))

TORSO = dict(bottom=0.345, top=0.662, rings=(          # (z, raggio x, raggio y, spostamento y)
    (0.345, 0.000, 0.000, 0.000), (0.352, 0.060, 0.052, -0.004), (0.365, 0.105, 0.090, -0.008), (0.385, 0.135, 0.115, -0.012),
    (0.415, 0.152, 0.128, -0.016), (0.450, 0.156, 0.132, -0.018), (0.490, 0.152, 0.130, -0.017), (0.530, 0.144, 0.124, -0.012),
    (0.570, 0.134, 0.114, -0.006), (0.605, 0.122, 0.102, -0.002), (0.630, 0.104, 0.088, 0.000), (0.648, 0.078, 0.068, 0.002),
    (0.658, 0.050, 0.046, 0.002), (0.662, 0.000, 0.000, 0.002)),
    shorts_top=0.452)            # sotto questa quota il busto e' «pantaloncini»

ARM = dict(r_up=0.034, r_low=0.029, sleeve_r=0.045, sleeve_len=0.050)
LEG = dict(r_up=0.050, r_low=0.038, shorts_r=0.060, shorts_len=0.070)

# ------------------------------------------------------------------ scheletro (posizioni delle articolazioni del lato sinistro)
J = dict(
    hips=(0.0, 0.0, 0.400), spine=(0.0, 0.0, 0.470), chest=(0.0, 0.0, 0.550), neck=(0.0, 0.0, 0.645), head=(0.0, 0.0, 0.675),
    head_top=(0.0, 0.0, 1.021),
    clav=(0.030, 0.004, 0.603), shoulder=(0.124, 0.008, 0.612), elbow=(0.235, 0.020, 0.520), wrist=(0.338, 0.004, 0.436),
    hip=(0.074, 0.000, 0.398), knee=(0.074, -0.010, 0.230), ankle=(0.074, 0.004, 0.078), ball=(0.074, -0.088, 0.032),
    toe=(0.074, -0.160, 0.032),
)
FOOT = dict(heel=(0.0, 0.050, -0.078), len=0.222, width=0.116, height=0.096)   # tallone rispetto alla caviglia
HAND = dict(len=0.080, palm=(0.044, 0.024, 0.047))
FINGERS = dict(                  # (nome, spostamento verso il pollice, angolo di apertura, lunghezze dei 3 segmenti, raggio)
    names=('f_index', 'f_middle', 'f_ring'),
    side=(0.0205, 0.0, -0.0205), spread=(15.0, 1.0, -14.0), seg=((0.021, 0.018, 0.015), (0.022, 0.019, 0.016), (0.020, 0.017, 0.014)),
    r=(0.0128, 0.0132, 0.0124),
    thumb_seg=(0.021, 0.018), thumb_r=0.0140)

CURL = dict(r0=0.0200, r1=0.0085, pts=(   # il ciuffo a «?» visto da davanti (x, z) con poca profondita' y
    (0.000, 0.000, 0.994), (0.000, 0.005, 1.046), (0.005, 0.007, 1.089), (0.027, 0.013, 1.124), (0.050, 0.018, 1.157),
    (0.050, 0.022, 1.189), (0.027, 0.025, 1.209), (-0.003, 0.025, 1.209), (-0.025, 0.022, 1.194), (-0.033, 0.018, 1.171)),
    bones=14)

# ------------------------------------------------------------------ nomi per il retargeting (Mixamo, CMU in BVH di cgspeed)
MIXAMO = {
    'hips': 'Hips', 'spine': 'Spine', 'chest': 'Spine2', 'neck': 'Neck', 'head': 'Head',
    'shoulder.L': 'LeftShoulder', 'upper_arm.L': 'LeftArm', 'forearm.L': 'LeftForeArm', 'hand.L': 'LeftHand',
    'shoulder.R': 'RightShoulder', 'upper_arm.R': 'RightArm', 'forearm.R': 'RightForeArm', 'hand.R': 'RightHand',
    'thigh.L': 'LeftUpLeg', 'shin.L': 'LeftLeg', 'foot.L': 'LeftFoot', 'toe.L': 'LeftToeBase',
    'thigh.R': 'RightUpLeg', 'shin.R': 'RightLeg', 'foot.R': 'RightFoot', 'toe.R': 'RightToeBase',
    'f_index.01.L': 'LeftHandIndex1', 'f_index.02.L': 'LeftHandIndex2', 'f_index.03.L': 'LeftHandIndex3',
    'f_middle.01.L': 'LeftHandMiddle1', 'f_middle.02.L': 'LeftHandMiddle2', 'f_middle.03.L': 'LeftHandMiddle3',
    'f_ring.01.L': 'LeftHandRing1', 'f_ring.02.L': 'LeftHandRing2', 'f_ring.03.L': 'LeftHandRing3',
    'thumb.01.L': 'LeftHandThumb1', 'thumb.02.L': 'LeftHandThumb2',
    'f_index.01.R': 'RightHandIndex1', 'f_index.02.R': 'RightHandIndex2', 'f_index.03.R': 'RightHandIndex3',
    'f_middle.01.R': 'RightHandMiddle1', 'f_middle.02.R': 'RightHandMiddle2', 'f_middle.03.R': 'RightHandMiddle3',
    'f_ring.01.R': 'RightHandRing1', 'f_ring.02.R': 'RightHandRing2', 'f_ring.03.R': 'RightHandRing3',
    'thumb.01.R': 'RightHandThumb1', 'thumb.02.R': 'RightHandThumb2',
}
CMU = {   # nomi delle giunture nei BVH CMU convertiti da cgspeed (verificati sul file 02_01.bvh, vedi tests)
    'hips': 'Hips', 'spine': 'LowerBack', 'chest': 'Spine1', 'neck': 'Neck', 'head': 'Head',
    'shoulder.L': 'LeftShoulder', 'upper_arm.L': 'LeftArm', 'forearm.L': 'LeftForeArm', 'hand.L': 'LeftHand',
    'shoulder.R': 'RightShoulder', 'upper_arm.R': 'RightArm', 'forearm.R': 'RightForeArm', 'hand.R': 'RightHand',
    'thigh.L': 'LeftUpLeg', 'shin.L': 'LeftLeg', 'foot.L': 'LeftFoot', 'toe.L': 'LeftToeBase',
    'thigh.R': 'RightUpLeg', 'shin.R': 'RightLeg', 'foot.R': 'RightFoot', 'toe.R': 'RightToeBase',
}

# ------------------------------------------------------------------ canali del viso (proprieta' dell'osso «face» -> shape keys)
MOUTH_SHAPES = ('smile', 'smile_open', 'frown', 'frown_open', 'open', 'wide', 'O', 'U', 'E', 'M', 'wavy', 'smirk_L', 'smirk_R', 'grr', 'scream')
FACE_PROPS = MOUTH_SHAPES + ('pupil', 'blush')

# parametri del contorno della bocca per ogni forma (vedi facial.mouth_curves):
#   w = mezza larghezza, k = alzata degli angoli (sorriso > 0), up/lo = apertura sopra/sotto, eu/el = rotondita'
#   wave = ondulazione, kl/kr = alzata separata degli angoli (sorriso storto), teeth/tongue = quanto si vedono
MOUTH_PARAMS = {
    'base':       dict(w=0.037, k=0.008, up=0.0016, lo=0.0085, eu=1.0, el=1.2),
    'smile':      dict(w=0.040, k=0.013, up=0.0012, lo=0.0120, eu=1.0, el=1.3),
    'smile_open': dict(w=0.043, k=0.012, up=0.0015, lo=0.030, eu=1.6, el=0.75, teeth=0.30, tongue=0.42),
    'frown':      dict(w=0.032, k=-0.011, up=0.0095, lo=0.0012, eu=1.2, el=1.0),
    'frown_open': dict(w=0.033, k=-0.012, up=0.020, lo=0.006, eu=0.8, el=1.0, teeth=0.18, tongue=0.0),
    'open':       dict(w=0.030, k=0.002, up=0.010, lo=0.026, eu=0.8, el=0.7, teeth=0.16, tongue=0.40),
    'wide':       dict(w=0.048, k=0.004, up=0.010, lo=0.030, eu=0.9, el=0.8, teeth=0.18, tongue=0.36),
    'O':          dict(w=0.018, k=0.000, up=0.017, lo=0.020, eu=0.55, el=0.55, teeth=0.0, tongue=0.30),
    'U':          dict(w=0.012, k=0.000, up=0.006, lo=0.007, eu=0.6, el=0.6),
    'E':          dict(w=0.042, k=0.004, up=0.006, lo=0.012, eu=1.3, el=1.1, teeth=0.40, tongue=0.0),
    'M':          dict(w=0.032, k=0.000, up=0.0015, lo=0.0035, eu=1.0, el=1.0),
    'wavy':       dict(w=0.036, k=0.000, up=0.0040, lo=0.0050, eu=1.0, el=1.0, wave=0.0060),
    'smirk_L':    dict(w=0.036, k=0.0, kl=0.016, kr=-0.002, up=0.0015, lo=0.0080, eu=1.0, el=1.2),
    'smirk_R':    dict(w=0.036, k=0.0, kl=-0.002, kr=0.016, up=0.0015, lo=0.0080, eu=1.0, el=1.2),
    'grr':        dict(w=0.040, k=-0.004, up=0.008, lo=0.009, eu=2.5, el=2.5, teeth=0.48, teeth_lo=0.42),
    'scream':     dict(w=0.040, k=-0.002, up=0.020, lo=0.040, eu=0.7, el=0.6, teeth=0.12, tongue=0.30),
}

# pose del ciuffo (le rotazioni per osso si calcolano in rig.py). La mesh del ciuffo e' costruita DRITTA (cosi' raddrizzarlo
# in un «!» non lascia onde) e il «?» e' la posa di base che il viso applica sempre: domanda (piu' arricciato),
# esclamazione (dritto in su, come un «!»), giu' (triste, cade di lato)
CURL_POSES = ('question', 'exclaim', 'droop')

# ------------------------------------------------------------------ espressioni (canali del viso)
# brow_raise/tilt/in: gradi (alza, inclina: + = interno in giu' (arrabbiato), avvicina); lid: apertura palpebra superiore 0-1.2;
# lid_tilt: gradi (+ = angolo interno in giu'); low: palpebra inferiore 0-1; pupil 0-1; mouth: pesi; curl: pesi; eyes: (yaw, pitch)
_N = dict(brow_raise=0.0, brow_tilt=0.0, brow_in=0.0, lid=1.0, lid_tilt=0.0, low=0.0, pupil=0.55, blush=0.0)
EXPRESSIONS = {
    'neutral':   dict(_N),
    'happy':     dict(_N, brow_raise=6, brow_tilt=-6, lid=0.92, low=0.52, pupil=0.7, blush=0.5, mouth={'smile': 1.0}),
    'joy':       dict(_N, brow_raise=12, brow_tilt=-8, lid=0.85, low=0.62, pupil=0.8, blush=0.9, mouth={'smile_open': 1.0}, curl={'exclaim': 0.35}),
    'sad':       dict(_N, brow_raise=4, brow_tilt=-22, brow_in=4, lid=0.72, lid_tilt=-12, low=0.15, pupil=0.75, mouth={'frown': 1.0}, curl={'droop': 0.9}, eyes=(0, -10)),
    'angry':     dict(_N, brow_raise=-12, brow_tilt=26, brow_in=6, lid=0.78, lid_tilt=16, low=0.25, pupil=0.35, mouth={'grr': 1.0}),
    'surprised': dict(_N, brow_raise=22, brow_tilt=-4, lid=1.2, low=0.0, pupil=0.45, mouth={'O': 1.0}, curl={'exclaim': 1.0}),
    'shocked':   dict(_N, brow_raise=26, brow_tilt=-10, lid=1.25, low=0.0, pupil=0.18, mouth={'scream': 1.0}, curl={'exclaim': 1.0}),
    'scared':    dict(_N, brow_raise=18, brow_tilt=-20, brow_in=5, lid=1.15, lid_tilt=-8, low=0.1, pupil=0.2, mouth={'frown_open': 1.0}, curl={'droop': 0.3}),
    'confused':  dict(_N, brow_raise=0, brow_tilt=0, lid=0.92, low=0.1, pupil=0.55, mouth={'wavy': 1.0}, curl={'question': 1.0},
                      side=dict(L=dict(brow_raise=16, brow_tilt=-6), R=dict(brow_raise=-6, brow_tilt=10, lid=0.8)), eyes=(8, 6)),
    'thinking':  dict(_N, brow_raise=4, lid=0.88, low=0.2, mouth={'smirk_R': 0.7}, curl={'question': 0.6},
                      side=dict(L=dict(brow_raise=12), R=dict(brow_raise=-2)), eyes=(-14, 14)),
    'disgust':   dict(_N, brow_raise=-6, brow_tilt=14, brow_in=4, lid=0.7, low=0.45, pupil=0.4, mouth={'frown': 0.6, 'smirk_L': 0.4}),
    'embarrassed': dict(_N, brow_raise=6, brow_tilt=-14, lid=0.8, low=0.35, pupil=0.75, blush=1.0, mouth={'smile': 0.5, 'wavy': 0.5}, eyes=(-10, -12)),
    'smug':      dict(_N, brow_raise=2, brow_tilt=6, lid=0.7, low=0.3, mouth={'smirk_L': 1.0}, side=dict(L=dict(brow_raise=10), R=dict(brow_raise=-2))),
    'determined': dict(_N, brow_raise=-6, brow_tilt=16, brow_in=3, lid=0.85, lid_tilt=8, low=0.3, mouth={'M': 1.0}),
    'sleepy':    dict(_N, brow_raise=-2, brow_tilt=-6, lid=0.38, lid_tilt=-4, low=0.2, mouth={'base': 0.0}, curl={'droop': 0.6}),
    'dizzy':     dict(_N, brow_raise=8, brow_tilt=-12, lid=0.75, low=0.2, pupil=0.3, mouth={'wavy': 1.0}, curl={'droop': 0.5}),
}
ALIASES = {   # nomi italiani accettati dall'API
    'neutro': 'neutral', 'felice': 'happy', 'contento': 'happy', 'gioia': 'joy', 'triste': 'sad', 'tristezza': 'sad', 'arrabbiato': 'angry',
    'rabbia': 'angry', 'sorpreso': 'surprised', 'sorpresa': 'surprised', 'scioccato': 'shocked', 'spaventato': 'scared', 'paura': 'scared',
    'confuso': 'confused', 'confusione': 'confused', 'pensieroso': 'thinking', 'disgusto': 'disgust', 'imbarazzato': 'embarrassed',
    'furbo': 'smug', 'deciso': 'determined', 'assonnato': 'sleepy', 'stordito': 'dizzy',
    'cammina': 'walk', 'corri': 'run', 'salta': 'jump', 'scatta': 'sprint', 'gira': 'turn', 'fermati': 'stop', 'fermo': 'idle',
    'cadi': 'fall', 'inciampa': 'trip', 'scivola': 'slip', 'balla': 'dance', 'festeggia': 'celebrate', 'mano_in_faccia': 'facepalm',
    'guarda_intorno': 'look_around', 'reazione': 'exaggerated_reaction', 'indica': 'point', 'saluta': 'wave', 'raccogli': 'pick_up',
    'lancia': 'throw', 'spingi': 'push', 'tira': 'pull', 'siediti': 'sit', 'alzati': 'stand_up',
    'shock': 'shock', 'spavento': 'fear', 'felicita': 'happiness', 'sorpresa_corpo': 'surprise',
}

# ------------------------------------------------------------------ limiti per i test
LIMITS = dict(
    foot_slide_cm=1.0,          # scivolamento massimo del piede appoggiato, in cm
    penetration_cm=1.5,         # compenetrazione massima tra parti del corpo, in cm
    floor_cm=0.8,               # quanto puo' scendere la suola sotto il pavimento
    stretch=2.3,                # un lato della mesh puo' al massimo allungarsi di 2,3 volte (esterno del gomito a 110 gradi)
    compress=0.25,              # e accorciarsi fino a un quarto (sotto = la mesh collassa, «effetto caramella»)
    pose_jump_deg=28.0,         # salto massimo di rotazione di un osso tra due fotogrammi (scatti)
)

RENDER = dict(preview=(540, 960, 8), final=(1080, 1920, 16))
