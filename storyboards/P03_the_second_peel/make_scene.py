"""Writes scene.json for P03 The Second Peel (the rain of peels at the end is generated here)."""
import json, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(9)
HOME = {"location": [-0.1, -4.4, 0.92], "target": [-0.1, -0.35, 0.62], "lens": 46}
CLOSE = {"location": [0.3, -2.75, 0.9], "target": [0.35, -0.9, 0.8], "lens": 50}
peel = lambda name, at, t, h=2.2, extra=None: dict({"name": name, "type": "peel", "scale": 1.5, "location": [at[0], at[1], 9.0],
                                               "hidden": True,
                                               "motion": [{"t": t, "show": True},
                                                          {"t": t, "drop": {"to": [at[0], at[1], 0.0], "h": h, "bounce": 0.04, "bounces": 2,
                                                                            "squash": 0.25, "rot": [0, 0, rnd.uniform(0, 360)], "spin": [0, 0, 200],
                                                                            "sound": "tap", "fall_sound": "none"}}]}, **(extra or {}))
props = [peel("peel1", (0.08, -0.25), 0.0, 1.9)]
props[0]["location"] = [0.08, -0.25, 1.9]; props[0]["hidden"] = False; props[0]["motion"] = props[0]["motion"][1:]
props[0]["motion"][0]["drop"].update({"sound": "thud", "fall_sound": "whistle_short"})
p2 = peel("peel2", (0.32, -1.24), "gloat+1.35", 2.4)
p2["motion"].append({"t": "slip+0.25", "fly": {"from": [0.32, -1.24, 0.0], "to": [0.30, -1.30, 0.66], "dur": 0.75, "arc": 0.7,
                                               "spin": [0, 0, 380], "land": True, "sound": "pop"}})
props.append(p2)
for i in range(14):
    at = (rnd.uniform(-1.2, 0.9), rnd.uniform(-1.4, 0.4))
    props.append(peel("rain%02d" % i, at, "slip+%.2f" % (3.0 + i * 0.09 + rnd.uniform(0, 0.05)), 2.6 + rnd.uniform(0, 1.0)))
zh = peel("hat_zop", (-0.45, 0.04), "slip+4.35", 2.6)
zh["motion"][1]["drop"].update({"to": [-0.45, 0.04, 1.0], "squash": 0.3, "bounces": 1, "bounce": 0.03, "sound": "pop"})
props.append(zh)
spec = {
  "name": "P03_the_second_peel", "title": "The Second Peel",
  "logline": "A banana peel falls from the sky. Piko smugly walks around it, gloats to the camera, and slips on a second one.",
  "render": {"resolution": [1080, 1920], "samples": 6},
  "stage": {"hdri": {"id": "kloofendal_48d_partly_cloudy_puresky", "strength": 2.0, "rotation": 40},
            "grass_texture": {"id": "Grass005", "size": 0.9}, "ambient": 0.55, "ambient_color": "#CFE0FF"},
  "light": {"sun": 3.2, "azimuth": -38, "elevation": 48, "rim": 180},
  "camera": {"shots": [dict(HOME, t=0), dict(CLOSE, t="gloat"), dict(HOME, t="gloat+1.3")],
             "shakes": [{"t": "slip+0.95", "amount": 0.025, "dur": 0.3}]},
  "props": props,
  "characters": [
    {"name": "Piko", "location": [0.45, 0.0], "facing": -25,
     "actions": [
       {"until": 0.55}, {"play": "surprise"},
       {"expression": "surprised", "at": 0.55, "duration": 1.0},
       {"look_at": [0.08, -0.25, 0.0], "at": 0.6, "duration": 1.4},
       {"expression": "smug", "at": 1.8, "duration": 2.2},
       {"until": 2.0}, {"play": "point", "target": [0.08, -0.25, 0.05], "speed": 1.5},
       {"look_at": "Zop", "at": 2.8, "duration": 0.5},
       {"walk_to": [0.35, -0.9]},
       {"play": "celebrate", "speed": 1.3, "mark": "gloat"},
       {"look_at": [0.3, -2.75, 0.9], "at": "gloat+0.2", "duration": 1.1},
       {"expression": "smug", "at": "gloat+0.1", "duration": 1.8},
       {"until": "gloat+2.2"},
       {"walk_to": [0.33, -1.20], "mark_end": "step"},
       {"play": "slip", "mark": "slip"},
       {"expression": "shocked", "at": "slip", "duration": 0.9},
       {"expression": "dizzy", "at": "slip+1.0", "duration": 2.0},
       {"until": "slip+3.1"},
       {"look_at": [-0.3, -0.6, 4.0], "at": "slip+3.1", "duration": 2.0},
       {"expression": "shocked", "at": "slip+3.15", "duration": 2.0},
       {"until": "slip+5.8", "dizzy": False}]},
    {"name": "Zop", "location": [-0.45, 0.05], "facing": 25,
     "actions": [
       {"until": 0.55}, {"play": "surprise"},
       {"expression": "surprised", "at": 0.55, "duration": 1.0},
       {"look_at": [0.08, -0.25, 0.0], "at": 0.6, "duration": 1.5},
       {"until": 1.4}, {"play": "confusion"},
       {"look_at": "Piko", "at": 3.6, "duration": 3.0},
       {"look_at": [0.32, -1.24, 0.2], "at": "gloat+1.6", "duration": 1.0},
       {"expression": "shocked", "at": "gloat+1.7", "duration": 0.9},
       {"until": "gloat+1.9"}, {"point": [0.32, -1.24, 0.1]},
       {"look_at": "Piko", "at": "slip", "duration": 1.6},
       {"until": "slip+1.2"}, {"play": "happiness"},
       {"expression": "joy", "at": "slip+1.2", "duration": 1.6},
       {"look_at": "camera", "at": "slip+2.2", "duration": 0.8},
       {"look_at": [0.0, -0.6, 4.0], "at": "slip+3.1", "duration": 2.0},
       {"expression": "scared", "at": "slip+3.15", "duration": 2.0},
       {"play": "fear"},
       {"wait": 1.0}]}
  ],
  "fx": [
    {"t": 0.52, "type": "puff", "at": [0.08, -0.27, 0.05], "count": 2, "spread": 0.3, "size": 0.32, "dur": 0.45},
    {"t": "slip+0.95", "type": "puff", "at": [0.3, -1.32, 0.06], "count": 3, "spread": 0.32, "size": 0.36, "dur": 0.5},
    {"t": "slip+0.95", "type": "burst", "at": [0.3, -1.32, 0.45], "dur": 0.5, "count": 5}
  ],
  "duration_from": "slip+5.4",
  "cues": [
    {"t": "slip", "sound": "woosh"},
    {"t": "slip+0.95", "sound": "thud_soft"},
    {"t": "slip+1.25", "sound": "giggle"},
    {"t": "slip+2.9", "sound": "whistle_long"},
    {"t": "slip+4.95", "sound": "boing", "gain": -6}
  ]
}

json.dump(spec, open(os.path.join(HERE, 'scene.json'), 'w'), indent=1)
print('scene.json written')
