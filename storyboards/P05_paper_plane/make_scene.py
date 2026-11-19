"""Writes scene.json for P05 The Paper Plane.

A paper plane glides down from the sky and bonks Piko on the forehead. Zop giggles. The plane takes off again by
itself and dives at Piko: this time he ducks, it flies over him and lands behind them. Piko stands up, very proud of
himself... and the plane takes off one last time and bonks him on the back of the head.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ZOP = (-0.40, 0.0); PIKO = (0.40, 0.0)
HEAD_Z = 0.835; HEAD_R = 0.19
L = 0.30                                    # plane length: the nose is L/2 ahead of the origin


def facing_dir(deg):
    a = math.radians(deg)
    return (math.sin(a), -math.cos(a))


def head_point(loc, facing, side=1.0, up=0.05):
    """front (side=1) or back (side=-1) of the head, in world coordinates."""
    fx, fy = facing_dir(facing)
    return (loc[0] + side * fx * HEAD_R * 0.92, loc[1] + side * fy * HEAD_R * 0.92, HEAD_Z + up)


def approach(target, frm, back=L / 2):
    """origin of the plane when its nose touches target, coming from point frm."""
    dx, dy, dz = target[0] - frm[0], target[1] - frm[1], target[2] - frm[2]
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    return [round(target[0] - dx / n * back, 4), round(target[1] - dy / n * back, 4), round(target[2] - dz / n * back, 4)]


PF = -20                                    # Piko's facing
fore = head_point(PIKO, PF, 1.0, 0.06)
nape = head_point(PIKO, PF, -1.0, 0.02)

# flight 1: from the top right, a wide glide in front of them, into Piko's forehead
T1, D1 = 0.0, 2.15
pre1 = (0.05, -0.85, 0.95)
hit1 = approach(fore, pre1)
path1 = [[1.35, 0.7, 2.45], [1.0, 0.0, 2.1], [0.2, -1.1, 1.65], [-0.75, -0.9, 1.3], [-0.55, -0.55, 1.05], list(pre1), hit1]
HIT1 = T1 + D1
GROUND1 = [0.22, -0.52, 0.05]

# flight 2: takes off from the ground, circles behind them and dives at Piko; he ducks, it passes over and lands behind
T2, D2 = HIT1 + 2.55, 2.9
over = [PIKO[0] + 0.02, PIKO[1] + 0.05, 1.22]
path2 = [[0.26, -0.6, 0.2], [0.75, -0.9, 0.6], [1.35, -0.2, 1.1], [1.2, 0.9, 1.35], [0.2, 1.3, 1.45], [-0.6, 0.7, 1.4],
         [-0.55, -0.6, 1.3], [0.05, -0.75, 1.24], over, [0.75, 0.9, 0.7], [0.92, 1.25, 0.2], [1.0, 1.42, 0.07]]
LAND2 = T2 + D2
DUCK = T2 + D2 * 0.63                       # Piko starts ducking a moment before the plane reaches him

# flight 3: a silent take-off behind them, a short loop, into the back of Piko's head
T3, D3 = LAND2 + 2.65, 1.75
pre3 = (0.62, 0.62, 0.95)
hit3 = approach(nape, pre3)
path3 = [[1.08, 1.62, 0.22], [0.8, 1.8, 0.75], [0.15, 1.45, 1.15], [0.2, 0.95, 1.05], list(pre3), hit3]
HIT3 = T3 + D3
GROUND3 = [0.62, -0.05, 0.05]

plane = {"name": "plane", "type": "plane", "length": L, "span": 0.22, "keel": 0.05, "color": "cream", "stripe": "coral",
         "location": path1[0], "rotation": [0, 0, 150],
         "motion": [
             {"t": T1, "path": {"points": path1[1:], "dur": D1, "ease": "linear", "bank": 0.7, "pitch": 0.8}},
             {"t": HIT1, "fly": {"to": GROUND1, "dur": 0.62, "arc": 0.10, "rot_to": [0, 0, 128], "sound": "tap", "strength": 0.3}},
             {"t": T2, "path": {"points": path2, "dur": D2, "ease": "inout", "bank": 0.8, "pitch": 0.8, "land": True,
                                "sound": "tap", "strength": 0.4}},
             {"t": LAND2, "fly": {"to": [1.05, 1.52, 0.05], "dur": 0.3, "arc": 0.0, "rot_to": [0, 0, -27], "land": False}},
             {"t": T3, "path": {"points": path3, "dur": D3, "ease": "in", "bank": 0.8, "pitch": 0.8}},
             {"t": HIT3, "fly": {"to": GROUND3, "dur": 0.7, "arc": 0.12, "rot_to": [0, 0, 300], "sound": "tap", "strength": 0.3}}]}

HOME = {"location": [0.0, -4.0, 0.95], "target": [0.0, 0.0, 0.78], "lens": 40}
WIDE = {"location": [0.1, -4.6, 1.35], "target": [0.15, 0.2, 0.9], "lens": 32}
CLOSE = {"location": [0.32, -2.2, 0.98], "target": [0.36, 0.0, 0.86], "lens": 50}

spec = {
  "name": "P05_paper_plane", "title": "The Paper Plane",
  "logline": "A paper plane keeps coming back for Piko.",
  "render": {"resolution": [1080, 1920], "samples": 6},
  "stage": {"hdri": {"id": "kloofendal_48d_partly_cloudy_puresky", "strength": 2.0, "rotation": 40},
            "grass_texture": {"id": "Grass005", "size": 0.9}, "ambient": 0.55, "ambient_color": "#CFE0FF"},
  "light": {"sun": 3.2, "azimuth": -38, "elevation": 48, "rim": 180},
  "camera": {"shots": [dict(HOME, t=0), dict(WIDE, t=round(T2 + 0.2, 3)),
                       dict(HOME, t=round(LAND2 + 0.25, 3)), dict(CLOSE, t=round(HIT3 + 0.9, 3))],
             "shakes": [{"t": round(HIT1, 3), "amount": 0.008, "dur": 0.2}, {"t": round(HIT3, 3), "amount": 0.01, "dur": 0.22}]},
  "props": [plane],
  "characters": [
    {"name": "Piko", "location": list(PIKO), "facing": PF,
     "actions": [
       {"look_at": [1.0, 0.0, 2.1], "at": 0.0, "duration": 0.5},
       {"look_at": [0.2, -1.1, 1.65], "at": 0.5, "duration": 0.6},
       {"look_at": [-0.7, -0.85, 1.25], "at": 1.1, "duration": 0.5},
       {"look_at": [0.0, -0.9, 0.95], "at": 1.6, "duration": 0.7},
       {"expression": "happy", "at": 0.0, "duration": 1.6},
       {"expression": "surprised", "at": round(HIT1 - 0.35, 3), "duration": 0.45},
       {"until": round(HIT1 + 0.05, 3)}, {"play": "anger"},
       {"expression": "angry", "at": round(HIT1 + 0.1, 3), "duration": 2.2},
       {"look_at": "Zop", "at": round(HIT1 + 1.0, 3), "duration": 1.2},
       {"look_at": GROUND1, "at": round(T2 - 0.4, 3), "duration": 0.6},
       {"expression": "shocked", "at": round(T2 + 0.1, 3), "duration": 0.6},
       {"look_at": [1.35, -0.2, 1.1], "at": round(T2 + 0.6, 3), "duration": 0.5},
       {"look_at": [0.2, 1.3, 1.45], "at": round(T2 + 1.1, 3), "duration": 0.5},
       {"look_at": [-0.55, -0.6, 1.3], "at": round(T2 + 1.6, 3), "duration": 0.3},
       {"expression": "scared", "at": round(DUCK - 0.2, 3), "duration": 1.4},
       {"until": round(DUCK, 3)}, {"play": "fear", "speed": 1.45},
       {"look_at": [1.0, 1.42, 0.0], "at": round(LAND2 + 0.1, 3), "duration": 0.8},
       {"expression": "smug", "at": round(LAND2 + 0.5, 3), "duration": 2.2},
       {"look_at": "camera", "at": round(LAND2 + 0.9, 3), "duration": 1.6},
       {"until": round(LAND2 + 0.9, 3)}, {"play": "happiness"},
       {"expression": "shocked", "at": round(HIT3 + 0.02, 3), "duration": 0.9},
       {"until": round(HIT3 + 0.02, 3)}, {"play": "exaggerated_reaction"},
       {"expression": "angry", "at": round(HIT3 + 1.1, 3), "duration": 1.6},
       {"until": round(HIT3 + 1.4, 3)}, {"play": "facepalm"},
       {"wait": 0.4}]},
    {"name": "Zop", "location": list(ZOP), "facing": 20,
     "actions": [
       {"look_at": [1.0, 0.0, 2.1], "at": 0.0, "duration": 0.55},
       {"look_at": [0.2, -1.1, 1.65], "at": 0.55, "duration": 0.6},
       {"look_at": [-0.7, -0.85, 1.25], "at": 1.15, "duration": 0.45},
       {"look_at": [0.0, -0.9, 0.95], "at": 1.6, "duration": 0.7},
       {"expression": "joy", "at": 0.0, "duration": 1.6},
       {"look_at": "Piko", "at": round(HIT1 + 0.05, 3), "duration": 1.6},
       {"until": round(HIT1 + 0.25, 3)}, {"play": "happiness"},
       {"expression": "joy", "at": round(HIT1 + 0.2, 3), "duration": 2.0},
       {"look_at": [1.35, -0.2, 1.1], "at": round(T2 + 0.6, 3), "duration": 0.5},
       {"look_at": [0.2, 1.3, 1.45], "at": round(T2 + 1.1, 3), "duration": 0.5},
       {"look_at": [-0.55, -0.6, 1.3], "at": round(T2 + 1.6, 3), "duration": 0.6},
       {"expression": "surprised", "at": round(T2 + 0.2, 3), "duration": 1.6},
       {"look_at": [1.0, 1.42, 0.0], "at": round(LAND2 - 0.2, 3), "duration": 1.0},
       {"look_at": "Piko", "at": round(LAND2 + 0.9, 3), "duration": 1.4},
       {"expression": "confused", "at": round(LAND2 + 1.0, 3), "duration": 1.0},
       {"look_at": [0.98, 1.48, 0.4], "at": round(T3 - 0.3, 3), "duration": 0.8},
       {"expression": "surprised", "at": round(T3 - 0.2, 3), "duration": 1.2},
       {"look_at": "Piko", "at": round(HIT3, 3), "duration": 1.6},
       {"until": round(HIT3 + 0.3, 3)}, {"play": "happiness"},
       {"expression": "joy", "at": round(HIT3 + 0.3, 3), "duration": 2.0},
       {"wait": 0.3}]}
  ],
  "fx": [
    {"t": round(HIT1, 3), "type": "sparkle", "at": list(fore), "size": 0.45, "dur": 0.25},
    {"t": round(HIT3, 3), "type": "sparkle", "at": list(nape), "size": 0.5, "dur": 0.25}
  ],
  "duration_from": round(HIT3 + 3.0, 3),
  "cues": []
}
spec['meta'] = dict(hit1=round(HIT1, 3), takeoff2=round(T2, 3), duck=round(DUCK, 3), land2=round(LAND2, 3), takeoff3=round(T3, 3),
                    hit3=round(HIT3, 3))
json.dump(spec, open(os.path.join(HERE, 'scene.json'), 'w'), indent=1)
snd = {
  "music": {"file": "audio/music/Sneaky_Snitch.mp3", "level": -19, "start": 0.0, "offset": 0.0, "fade_in": 0.6,
            "mute": [[round(HIT1 - 0.02, 3), round(HIT1 + 0.9, 3)], [round(DUCK + 0.1, 3), round(LAND2 + 0.3, 3)],
                     [round(T3 - 0.05, 3), round(HIT3 + 0.8, 3)]], "fade": 0.12},
  "rules": True,
  "cues": [
    {"t": round(HIT1 - 0.01, 3), "sound": "boing", "gain": -13},
    {"t": round(HIT1, 3), "sound": "tap", "gain": -6},
    {"t": round(T2, 3), "sound": "woosh", "gain": -12},
    {"t": round(DUCK + 0.55, 3), "sound": "woosh", "gain": -8},
    {"t": round(LAND2 + 1.2, 3), "sound": "rimshot", "gain": -14},
    {"t": round(HIT3 - 0.01, 3), "sound": "boing", "gain": -10},
    {"t": round(HIT3, 3), "sound": "tap", "gain": -5},
    {"t": round(HIT3 + 0.45, 3), "sound": "giggle", "gain": -10, "length": 1.5, "fade_out": 0.35}
  ],
  "credits": "\"Sneaky Snitch\" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/"
}
json.dump(snd, open(os.path.join(HERE, 'sound.json'), 'w'), indent=1)
print('scene.json and sound.json written:', json.dumps(spec['meta']))
