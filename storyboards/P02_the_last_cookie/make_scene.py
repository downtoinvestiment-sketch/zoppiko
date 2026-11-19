"""Writes scene.json for P02 The Last Cookie (the tower of cookies is generated here)."""
import json, math, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(4)
WIDE = {"location": [1.35, -2.6, 1.0], "target": [1.35, 0.8, 0.42], "lens": 40,
        "move": {"delay": 0.45, "dur": 1.7, "location": [2.5, -2.9, 1.1], "target": [2.72, 0.6, 0.38], "lens": 36}}
HOME = {"location": [1.25, -3.1, 0.88], "target": [1.25, 0.9, 0.72], "lens": 48}
R = 0.22
cookie = {"name": "cookie", "type": "cookie", "radius": R, "height": 0.06, "location": [1.25, 0.45, 2.0],
          "motion": [
              {"t": 0.0, "drop": {"to": [1.25, 0.45, 0.0], "h": 2.0, "bounce": 0.05, "bounces": 2, "squash": 0.25,
                                  "rot": [0, 0, 20], "spin": [160, 0, 90], "sound": "thud", "fall_sound": "whistle_short"}},
              {"t": "bonk+1.5", "fly": {"from": [1.25, 0.45, 0.0], "to": [1.25, 0.45, R], "dur": 0.35, "arc": 0.08,
                                         "spin": [257, 0, (0 - 20) / 0.35], "land": False}},
              {"t": "bonk+1.85", "roll": {"from": [1.25, 0.45, R], "to": [3.12, 0.45, R], "dur": 1.5, "radius": R, "ease": "in"}},
              {"t": "bonk+3.35", "ballistic": {"from": [3.12, 0.45, R], "v": [1.8, 0.0, 0.3], "g": 12.0, "spin": [0, -500, 0]}},
              {"t": "bonk+5.0", "hide": True}]}
tower = []
base = [2.08, -0.35]
for i in range(12):
    j = [base[0] + rnd.uniform(-0.025, 0.025) + i * 0.004, base[1] + rnd.uniform(-0.025, 0.025)]
    tower.append({"name": "tower%02d" % i, "type": "cookie", "radius": R, "height": 0.06, "location": [j[0], j[1], 9.0],
                  "hidden": True,
                  "motion": [{"t": "pedge+%.2f" % (0.9 + i * 0.13), "show": True},
                             {"t": "pedge+%.2f" % (0.9 + i * 0.13), "drop": {"to": [j[0], j[1], i * 0.062], "h": 2.4,
                              "bounce": 0.03, "bounces": 1, "squash": 0.15, "rot": [0, 0, rnd.uniform(0, 360)], "spin": [0, 0, 60],
                              "sound": "tap" if i < 11 else "thud", "fall_sound": "none"}}]})
spec = {
  "name": "P02_the_last_cookie", "title": "The Last Cookie",
  "logline": "One giant cookie lands between them. Both dive, bonk heads, and it rolls off the Edge, while a whole tower of cookies lands behind them unseen.",
  "render": {"resolution": [1080, 1920], "samples": 6},
  "stage": {"hdri": {"id": "kloofendal_48d_partly_cloudy_puresky", "strength": 2.0, "rotation": 40},
            "grass_texture": {"id": "Grass005", "size": 0.9}, "ambient": 0.55, "ambient_color": "#CFE0FF"},
  "light": {"sun": 3.2, "azimuth": -38, "elevation": 48, "rim": 180},
  "camera": {"shots": [dict(HOME, t=0), dict(WIDE, t="bonk+1.4")],
             "shakes": [{"t": 0.53, "amount": 0.01, "dur": 0.25}, {"t": "bonk", "amount": 0.03, "dur": 0.35}]},
  "props": [cookie] + tower,
  "characters": [
    {"name": "Zop", "location": [0.82, 0.9], "facing": 50,
     "squash": [{"t": "bonk", "pivot": [1.03, 0.78], "amount": 0.18}],
     "actions": [
       {"until": 0.55}, {"play": "surprise"},
       {"expression": "surprised", "at": 0.55, "duration": 1.2},
       {"look_at": [1.25, 0.45, 0.05], "at": 0.6, "duration": 1.6},
       {"expression": "joy", "at": 1.6, "duration": 0.7},
       {"look_at": "Piko", "at": 2.2, "duration": 1.2},
       {"expression": "determined", "at": 2.2, "duration": 1.4},
       {"until": 3.4},
       {"walk_to": [1.03, 0.78], "gait": "run"},
       {"play": "fall", "speed": 1.25},
       {"expression": "dizzy", "at": "bonk+0.3", "duration": 1.6},
       {"look_at": [2.4, 0.45, 0.2], "at": "bonk+1.9", "duration": 1.6},
       {"expression": "shocked", "at": "bonk+1.9", "duration": 1.2},
       {"until": "bonk+2.7"}, {"play": "get_up", "speed": 1.6},
       {"walk_to": [2.45, 1.6], "gait": "run", "mark_end": "zedge"},
       {"look_at": [3.6, 1.9, -1.0], "at": "zedge", "duration": 2.6},
       {"expression": "sad", "at": "zedge+0.2", "duration": 2.4},
       {"play": "sadness"},
       {"until": "pedge+2.55"},
       {"play": "turn", "angle": -125, "speed": 1.4},
       {"look_at": [2.08, -0.35, 0.45], "at": "pedge+3.0", "duration": 2.2},
       {"play": "surprise"},
       {"expression": "surprised", "at": "pedge+3.3", "duration": 0.5},
       {"expression": "joy", "at": "pedge+3.8", "duration": 1.6},
       {"wait": 1.2}]},
    {"name": "Piko", "location": [1.68, 0.9], "facing": -50,
     "squash": [{"t": "bonk", "pivot": [1.47, 0.78], "amount": 0.18}],
     "actions": [
       {"until": 0.55}, {"play": "surprise"},
       {"expression": "surprised", "at": 0.55, "duration": 1.2},
       {"look_at": [1.25, 0.45, 0.05], "at": 0.6, "duration": 1.6},
       {"expression": "joy", "at": 1.6, "duration": 0.7},
       {"look_at": "Zop", "at": 2.2, "duration": 1.2},
       {"expression": "determined", "at": 2.2, "duration": 1.4},
       {"until": 3.4},
       {"walk_to": [1.47, 0.78], "gait": "run", "mark_end": "bonk"},
       {"play": "fall", "speed": 1.25},
       {"expression": "dizzy", "at": "bonk+0.3", "duration": 1.6},
       {"look_at": [2.4, 0.45, 0.2], "at": "bonk+1.9", "duration": 1.4},
       {"expression": "shocked", "at": "bonk+1.9", "duration": 1.2},
       {"until": "bonk+1.9"}, {"play": "get_up", "speed": 1.6},
       {"play": "turn", "angle": 150, "speed": 1.5},
       {"walk_to": [2.95, 0.40], "gait": "run", "mark_end": "pedge"},
       {"look_at": [3.9, 0.45, -1.2], "at": "pedge", "duration": 4.5},
       {"expression": "sad", "at": "pedge+0.2", "duration": 4.5},
       {"play": "sadness"},
       {"wait": 2.0}]}
  ],
  "fx": [
    {"t": 0.53, "type": "puff", "at": [1.25, 0.43, 0.06], "count": 2, "spread": 0.4, "size": 0.4, "dur": 0.5, "color": [0.95, 0.82, 0.62]},
    {"t": "bonk", "type": "sparkle", "at": [1.25, 0.76, 0.86], "size": 0.7, "dur": 0.3},
    {"t": "bonk", "type": "burst", "at": [1.25, 0.76, 0.88], "dur": 0.55, "count": 6},
    {"t": "bonk+0.7", "type": "puff", "at": [1.25, 0.95, 0.06], "count": 3, "spread": 0.38, "size": 0.32, "dur": 0.5},
    {"t": "bonk+0.8", "type": "dizzy", "at": [0.88, 1.0, 0.74], "dur": 1.0, "count": 3},
    {"t": "bonk+0.8", "type": "dizzy", "at": [1.62, 1.0, 0.74], "dur": 1.0, "count": 3}
  ],
  "duration_from": "pedge+5.3",
  "cues": [
    {"t": "bonk", "sound": "boing"},
    {"t": "bonk+0.02", "sound": "bonk_birds", "gain": -3},
    {"t": "bonk+0.75", "sound": "thud_soft", "gain": -6},
    {"t": "bonk+3.4", "sound": "whistle_long"},
    {"t": "zedge+0.5", "sound": "sad_trombone"}
  ]
}
spec['characters'] = spec['characters'][::-1]   # Piko first: Zop's actions use Piko's marks
json.dump(spec, open(os.path.join(HERE, 'scene.json'), 'w'), indent=1)
print('scene.json written')
