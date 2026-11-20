"""Writes scene.json for P04 Domino Day.

Piko has built a long winding line of dominoes. A red button falls from the sky and lands a hair from the end of the
line: the last dominoes wobble and stay up. Piko celebrates with a hop, and the hop knocks over the first domino.
The wave runs along the whole line (growing bigger at the end) while Zop dances with joy; the biggest domino falls on
the button, and the button sends a beach ball onto Zop's head.

The dominoes are simulated here (tipping on their front edge, knocking the next one, leaning on it) and written as
"tilt" keys for each prop, with a wooden click at every contact that climbs in pitch along the line.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 24
G = 9.81

# ------------------------------------------------------------------ the path (rows across the frame, U-turns)
R = 0.30
ROWS = [-0.55, 0.05, 0.65, 1.25]
X0, X1 = -0.60, 0.60
START = (0.66, -1.10)                       # beside Piko's right foot


def path_pieces():
    p = []
    p.append(('line', (START[0], START[1]), (START[0], ROWS[0] - R)))
    p.append(('arc', (START[0] - R, ROWS[0] - R), R, 0.0, 90.0))                 # +y then turning to -x
    p.append(('line', (START[0] - R, ROWS[0]), (X0, ROWS[0])))
    p.append(('arc', (X0, ROWS[0] + R), R, -90.0, -270.0))                       # -x, round the left end, to +x
    p.append(('line', (X0, ROWS[1]), (X1, ROWS[1])))
    p.append(('arc', (X1, ROWS[1] + R), R, -90.0, 90.0))                         # +x, round the right end, to -x
    p.append(('line', (X1, ROWS[2]), (X0, ROWS[2])))
    p.append(('arc', (X0, ROWS[2] + R), R, -90.0, -270.0))                       # -x, round the left end, to +x
    p.append(('line', (X0, ROWS[3]), (-0.25, ROWS[3])))
    return p


def piece_len(pc):
    if pc[0] == 'line':
        (ax, ay), (bx, by) = pc[1], pc[2]
        return math.hypot(bx - ax, by - ay)
    return abs(math.radians(pc[4] - pc[3])) * pc[2]


def point_at(s):
    """position and unit tangent at arc length s."""
    for pc in path_pieces():
        L = piece_len(pc)
        if s <= L + 1e-9:
            if pc[0] == 'line':
                (ax, ay), (bx, by) = pc[1], pc[2]
                k = s / L
                return (ax + (bx - ax) * k, ay + (by - ay) * k), ((bx - ax) / L, (by - ay) / L)
            (cx, cy), r, a0, a1 = pc[1], pc[2], pc[3], pc[4]
            a = math.radians(a0 + (a1 - a0) * s / L)
            sg = 1.0 if a1 > a0 else -1.0
            return (cx + r * math.cos(a), cy + r * math.sin(a)), (-math.sin(a) * sg, math.cos(a) * sg)
        s -= L
    pc = path_pieces()[-1]
    (ax, ay), (bx, by) = pc[1], pc[2]
    L = piece_len(pc)
    return (bx + (bx - ax) / L * s, by + (by - ay) / L * s), ((bx - ax) / L, (by - ay) / L)


TOTAL = sum(piece_len(pc) for pc in path_pieces())

# ------------------------------------------------------------------ the dominoes
COLORS = ['zop', 'piko', 'yellow', 'teal', 'coral', 'cream']
H, W, WIDE_ = 0.26, 0.05, 0.14
GAP = 0.17                                  # front edge to front edge
dominoes = []
s = 0.0
while s <= TOTAL + 1e-6:
    dominoes.append(dict(s=s, h=H, w=W, b=WIDE_))
    s += GAP
GROW = 1.27                                 # the end of the line: three bigger and bigger ones
for k in range(3):
    last = dominoes[-1]
    h = last['h'] * GROW
    dominoes.append(dict(s=last['s'] + 0.60 * last['h'] + 0.5 * (h * W / H - last['w']), h=h, w=h * W / H, b=h * WIDE_ / H))
N = len(dominoes)
for i, d in enumerate(dominoes):
    (x, y), (tx, ty) = point_at(d['s'])
    d['x'], d['y'] = x, y
    d['yaw'] = math.degrees(math.atan2(-tx, ty))          # local +y along the path
    d['color'] = COLORS[(i * 5) % len(COLORS)] if i < N - 3 else ['coral', 'yellow', 'red'][i - (N - 3)]

# pivot-to-pivot spacing (front edges), measured along the path
for i in range(N - 1):
    a, b = dominoes[i], dominoes[i + 1]
    dominoes[i]['d'] = (b['s'] + b['w'] / 2) - (a['s'] + a['w'] / 2)

# ------------------------------------------------------------------ the button at the end
BS, BCAP = 0.72, 0.17                       # button size and cap radius (as in make_prop)
last = dominoes[-1]
cap_r = BCAP * BS; cap_c = 0.465 * BS; cap_hz = 0.42 * BCAP * BS


def contact_angle(h, w, x_c):
    """angle (deg) at which a domino tipping about its front edge (x = 0) first touches the button cap whose centre
    is at distance x_c along the path. The cap is an ellipsoid: half-axes cap_r, cap_r, cap_hz at height cap_c."""
    for k in range(0, 9000):
        th = k * 0.01
        a = math.radians(th)
        # sample the front face and the top of the domino
        for j in range(0, 41):
            u = j / 40.0
            px, pz = u * h * math.sin(a), u * h * math.cos(a)            # front face
            for (qx, qz) in ((px, pz), (px - w * math.cos(a) * (1 if j == 40 else 0), pz + w * math.sin(a) * (1 if j == 40 else 0))):
                if ((qx - x_c) / cap_r) ** 2 + ((qz - cap_c) / cap_hz) ** 2 <= 1.0:
                    return th
    return 90.0


BX_OFF = last['h'] * 0.80                    # cap centre beyond the last domino's front edge
th_press = contact_angle(last['h'], last['w'], BX_OFF)
(bx0, by0), (btx, bty) = point_at(last['s'] + last['w'] / 2 + BX_OFF)
BUTTON = (round(bx0, 4), round(by0, 4))

# ------------------------------------------------------------------ the chain reaction
DT = 1.0 / 480


def simulate(omega0=2.2, omega_ss=4.5):
    th = [0.0] * N; om = [0.0] * N
    phase = ['stand'] * N                    # stand -> free -> lean -> rest
    phase[0] = 'free'; om[0] = omega0
    t = 0.0
    hist = [[] for _ in range(N)]
    contacts = []
    pressed = None
    while t < 12.0:
        for i in range(N):
            if phase[i] == 'free':
                h, w = dominoes[i]['h'], dominoes[i]['w']
                acc = 3 * G / (h * h + w * w) * (h / 2 * math.sin(th[i]) - w / 2 * math.cos(th[i]))
                om[i] += acc * DT; th[i] += om[i] * DT
                if i < N - 1:
                    nx = dominoes[i + 1]
                    if h * math.sin(th[i]) >= dominoes[i]['d'] - nx['w']:
                        phase[i] = 'lean'; phase[i + 1] = 'free'
                        om[i + 1] = omega_ss * (1 - 0.45 * 0.55 ** (i + 1)) * math.sqrt(H / nx['h'])
                        contacts.append((t, i))
                else:
                    if math.degrees(th[i]) >= th_press:
                        th[i] = math.radians(th_press); phase[i] = 'press'; pressed = t; om[i] = 0.0
            elif phase[i] == 'press':
                k = min(1.0, (t - pressed) / 0.12)
                th[i] = math.radians(th_press + 4.0 * (1 - (1 - k) ** 2))
                if k >= 1.0:
                    phase[i] = 'rest'
        for i in range(N - 2, -1, -1):        # leaning ones follow the next one
            if phase[i] in ('lean', 'rest') and phase[i + 1] != 'stand':
                h = dominoes[i]['h']; d = dominoes[i]['d']; wn = dominoes[i + 1]['w']; tn = th[i + 1]
                v = (d * math.cos(tn) - wn) / h
                v = max(-1.0, min(1.0, v))
                th[i] = max(th[i], tn + math.asin(v))
        for i in range(N):
            hist[i].append((t, math.degrees(th[i])))
        if pressed is not None and t > pressed + 0.6:
            break
        t += DT
    return hist, contacts, pressed


hist, contacts, pressed = simulate()
print('dominoes %d, path %.2f m, button press at %.2f s after the push, contact angle %.1f' % (N, TOTAL, pressed, th_press))


def keys_for(i):
    """frame-rate keys from the first movement to the rest."""
    hs = hist[i]
    moving = [k for k, (t, a) in enumerate(hs) if a > 0.05]
    if not moving:
        return None, None
    k0 = moving[0]
    t0 = hs[k0][0]
    out = [[0.0, 0.0]]
    f = 1
    while True:
        tt = f / FPS
        if t0 + tt > hs[-1][0]:
            break
        j = min(len(hs) - 1, int(round((t0 + tt) / DT)))
        out.append([round(tt, 4), round(hs[j][1], 2)])
        f += 1
    # drop the trailing still keys
    while len(out) > 2 and abs(out[-1][1] - out[-2][1]) < 0.01:
        out.pop()
    return t0, out


# ------------------------------------------------------------------ timing
PUSH = 0.66                                 # Piko's hop lands 0.646 s into "celebrate"
DROP_T, DROP_H = 0.35, 1.9                  # the button falls
DROP_G = 14.0
LAND = DROP_T + math.sqrt(2 * DROP_H / DROP_G)
PRESS = PUSH + pressed                      # after "cel"

props = []
for i, d in enumerate(dominoes):
    t0, keys = keys_for(i)
    motion = []
    if i >= N - 2:                          # the two big ones nearest the button wobble when it lands
        A = 6.0 if i == N - 1 else 3.0
        wk = []
        for f in range(0, int(1.3 * FPS) + 1):
            tt = f / FPS
            wk.append([round(tt, 4), round(A * math.exp(-tt / 0.32) * math.sin(2 * math.pi * 3.2 * tt), 2)])
        wk.append([1.35, 0.0])
        ev = [dict(t=0.08 + 0.156 * k, sound='domino_%d' % (k % 5), gain=(-17 if i == N - 1 else -23) - 4 * k, pitch=-3)
              for k in range(3)]
        motion.append({"t": round(LAND + 0.02, 3), "tilt": {"keys": wk, "half": d['w'] / 2, "yaw": d['yaw'], "events": ev}})
    if keys:
        ev = []
        for (tc, ic) in contacts:
            if ic == i:
                big = i >= N - 4
                ev.append(dict(t=round(tc - t0, 4), sound=('domino_big_%d' % (i % 2)) if big else 'domino_%d' % (i % 5),
                               gain=-7 if big else -11, pitch=round(7.0 * i / N, 2) if not big else 0.0,
                               pan=round(max(-0.7, min(0.7, d['x'] / 1.1)), 2)))
        motion.append({"t": "cel+%.4f" % (PUSH + t0), "tilt": {"keys": keys, "half": d['w'] / 2, "yaw": d['yaw'], "events": ev}})
    props.append({"name": "dom%02d" % i, "type": "box", "dims": [round(d['b'], 4), round(d['w'], 4), round(d['h'], 4)],
                  "color": d['color'], "roughness": 0.35, "location": [round(d['x'], 4), round(d['y'], 4), 0.0],
                  "rotation": [0, 0, round(d['yaw'], 3)], "motion": motion})

ZOP = (-0.42, -1.18); PIKO = (0.30, -1.18)
BALL_H = 9.0
BALL_FALL = math.sqrt(2 * BALL_H / DROP_G)
BALL_T = PRESS + 0.25                       # after "cel"
HIT = BALL_T + BALL_FALL                    # after "cel"

button = {"name": "button", "type": "button", "size": BS, "cap": BCAP, "location": [BUTTON[0], BUTTON[1], DROP_H],
          "motion": [{"t": DROP_T, "drop": {"to": [BUTTON[0], BUTTON[1], 0.0], "h": DROP_H, "bounce": 0.05, "bounces": 2,
                                           "squash": 0.3, "rot": [0, 0, 25], "spin": [-150, 0, 70], "sound": "thud_metal",
                                           "fall_sound": "whistle_short"}},
                     {"t": "cel+%.4f" % PRESS, "press": 0.03, "dur": 6.0}]}
ball = {"name": "ball", "type": "beachball", "radius": 0.3, "location": [ZOP[0] + 0.02, ZOP[1] + 0.02, 12.0], "hidden": True,
        "motion": [{"t": "cel+%.4f" % BALL_T, "show": True},
                   {"t": "cel+%.4f" % BALL_T, "drop": {"to": [ZOP[0] + 0.02, ZOP[1] + 0.02, 0.98], "h": BALL_H, "bounces": 0,
                                                     "squash": 0.35, "sound": "bonk", "fall_sound": "whistle_long",
                                                     "rot": [0, 0, 0], "spin": [0, 0, 120]}},
                   {"t": "cel+%.4f" % (HIT + 0.02), "ballistic": {"v": [-1.9, 1.5, 4.2], "g": 12.0, "spin": [0, -420, 90]}},
                   {"t": "cel+%.4f" % (HIT + 0.9), "hide": True}]}

WIDE = {"location": [0.0, -2.8, 4.0], "target": [0.0, 0.5, 0.0], "lens": 46}
MED = {"location": [0.1, -4.2, 0.95], "target": [0.1, -1.1, 0.55], "lens": 40}
INSERT = {"location": [0.9, -2.6, 0.6], "target": [0.45, -0.95, 0.35], "lens": 38}
CHAIN = dict(WIDE, move={"delay": 0.2, "dur": 4.2, "location": [0.05, -2.45, 3.6], "target": [0.08, 0.6, 0.0], "lens": 46})
END = {"location": [-0.06, -3.6, 0.95], "target": [-0.06, -1.15, 0.62], "lens": 40}

spec = {
  "name": "P04_domino_day", "title": "Domino Day",
  "logline": "A red button lands a hair from Piko's domino line and nothing falls. Then Piko celebrates with a hop.",
  "render": {"resolution": [1080, 1920], "samples": 6},
  "stage": {"hdri": {"id": "kloofendal_48d_partly_cloudy_puresky", "strength": 2.0, "rotation": 40, "haze": True},
            "grass_texture": {"id": "Grass005", "size": 0.9}, "ambient": 0.55, "ambient_color": "#CFE0FF"},
  "light": {"sun": 3.2, "azimuth": -38, "elevation": 48, "rim": 180},
  "camera": {"shots": [dict(WIDE, t=0), dict(MED, t=2.05), dict(INSERT, t="cel+0.40"), dict(CHAIN, t="cel+1.30"),
                       dict(END, t="cel+%.3f" % (PRESS + 0.35))],
             "shakes": [{"t": round(LAND, 3), "amount": 0.012, "dur": 0.25},
                        {"t": "cel+%.3f" % HIT, "amount": 0.03, "dur": 0.35}]},
  "props": [button, ball] + props,
  "characters": [
    {"name": "Piko", "location": list(PIKO), "facing": -20,
     "actions": [
       {"expression": "smug", "at": 0.0, "duration": 0.5},
       {"look_at": [0.0, 0.2, 0.1], "at": 0.0, "duration": 0.45},
       {"until": 0.45}, {"play": "shock", "speed": 1.3},
       {"look_at": [BUTTON[0], BUTTON[1], 1.4], "at": 0.42, "duration": 0.4},
       {"look_at": [BUTTON[0], BUTTON[1], 0.2], "at": 0.82, "duration": 1.2},
       {"expression": "scared", "at": 0.45, "duration": 1.3},
       {"expression": "happy", "at": 1.85, "duration": 0.4},
       {"look_at": "camera", "at": 2.05, "duration": 0.35},
       {"until": 2.35},
       {"play": "celebrate", "mark": "cel"},
       {"look_at": "camera", "at": "cel", "duration": 1.6},
       {"look_at": [0.6, -0.8, 0.1], "at": "cel+1.7", "duration": 0.5},
       {"expression": "shocked", "at": "cel+1.75", "duration": 1.0},
       {"play": "fear"},
       {"look_at": [-0.2, 0.3, 0.1], "at": "cel+2.6", "duration": 1.6},
       {"expression": "sad", "at": "cel+2.8", "duration": 1.6},
       {"until": "cel+%.3f" % (PRESS - 0.1)},
       {"look_at": [BUTTON[0], BUTTON[1], 0.3], "at": "cel+%.3f" % (PRESS - 0.2), "duration": 0.5},
       {"look_at": [ZOP[0], ZOP[1], 3.0], "at": "cel+%.3f" % (BALL_T + 0.3), "duration": 0.6},
       {"expression": "surprised", "at": "cel+%.3f" % (BALL_T + 0.3), "duration": 0.8},
       {"look_at": "Zop", "at": "cel+%.3f" % (HIT + 0.05), "duration": 1.2},
       {"until": "cel+%.3f" % (HIT + 0.35)},
       {"play": "happiness"},
       {"expression": "joy", "at": "cel+%.3f" % (HIT + 0.3), "duration": 1.6},
       {"look_at": "camera", "at": "cel+%.3f" % (HIT + 1.3), "duration": 0.9},
       {"wait": 0.6}]},
    {"name": "Zop", "location": list(ZOP), "facing": 20,
     "squash": [{"t": "cel+%.3f" % HIT, "pivot": list(ZOP), "amount": 0.22}],
     "actions": [
       {"look_at": "Piko", "at": 0.0, "duration": 0.45},
       {"until": 0.5}, {"play": "surprise"},
       {"expression": "surprised", "at": 0.5, "duration": 1.2},
       {"look_at": [BUTTON[0], BUTTON[1], 1.4], "at": 0.47, "duration": 0.4},
       {"look_at": [BUTTON[0], BUTTON[1], 0.2], "at": 0.87, "duration": 1.3},
       {"look_at": "Piko", "at": "cel", "duration": 0.6},
       {"look_at": [0.6, -1.0, 0.1], "at": "cel+0.6", "duration": 0.7},
       {"expression": "surprised", "at": "cel+0.65", "duration": 0.6},
       {"expression": "joy", "at": "cel+1.25", "duration": 1.0},
       {"until": "cel+1.2"},
       {"play": "dance", "duration": round(HIT - 0.06 - 1.2 - 0.25, 3)},
       {"look_at": [0.0, 0.2, 0.1], "at": "cel+1.3", "duration": 2.2},
       {"look_at": "camera", "at": "cel+%.3f" % (PRESS - 0.6), "duration": 1.2},
       {"until": "cel+%.3f" % (HIT - 0.06)},
       {"play": "fall"},
       {"expression": "dizzy", "at": "cel+%.3f" % (HIT + 0.2), "duration": 2.6},
       {"until": "cel+%.3f" % (HIT + 2.6), "dizzy": True}]}
  ],
  "fx": [
    {"t": round(LAND, 3), "type": "puff", "at": [BUTTON[0], BUTTON[1], 0.06], "count": 2, "spread": 0.3, "size": 0.32, "dur": 0.5},
    {"t": "cel+%.3f" % (PRESS + 0.02), "type": "sparkle", "at": [BUTTON[0], BUTTON[1], cap_c + 0.1], "size": 0.5, "dur": 0.3},
    {"t": "cel+%.3f" % HIT, "type": "sparkle", "at": [ZOP[0], ZOP[1] + 0.05, 1.0], "size": 0.8, "dur": 0.3},
    {"t": "cel+%.3f" % HIT, "type": "burst", "at": [ZOP[0], ZOP[1] + 0.05, 1.02], "dur": 0.55, "count": 6},
    {"t": "cel+%.3f" % (HIT + 0.75), "type": "puff", "at": [ZOP[0] + 0.04, ZOP[1] + 0.02, 0.06], "count": 2, "spread": 0.3, "size": 0.32, "dur": 0.5},
    {"t": "cel+%.3f" % (HIT + 0.9), "type": "dizzy", "at": [ZOP[0] + 0.04, ZOP[1] + 0.05, 0.8], "dur": 1.8, "count": 3}
  ],
  "duration_from": "cel+%.3f" % (HIT + 2.4),
  "cues": []
}
spec['meta'] = dict(press_after_cel=round(PRESS, 3), hit_after_cel=round(HIT, 3), land=round(LAND, 3), dominoes=N,
                    chain_s=round(pressed, 3), button=BUTTON)
json.dump(spec, open(os.path.join(HERE, 'scene.json'), 'w'), indent=1)
print('scene.json written:', json.dumps(spec['meta']))

snd = {
  "music": {"file": "audio/music/Fluffing_a_Duck.mp3", "level": -19, "start": "cel+0.05", "offset": 0.0, "fade_in": 0.25,
            "mute": [["cel+%.3f" % (PRESS - 0.03), "cel+%.3f" % (HIT + 0.55)]], "fade": 0.12},
  "rules": True,
  "cues": [
    {"t": "cel+%.3f" % (HIT + 0.5), "sound": "giggle", "gain": -10, "length": 1.5, "fade_out": 0.35},
    {"t": "cel+%.3f" % (HIT + 0.78), "sound": "thud_soft", "gain": -7},
    {"t": "cel+%.3f" % (HIT + 1.15), "sound": "boing_far"}
  ],
  "credits": "\"Fluffing a Duck\" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/"
}
json.dump(snd, open(os.path.join(HERE, 'sound.json'), 'w'), indent=1)
