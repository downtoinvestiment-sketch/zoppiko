"""ZOPPIKO sound mix: effects placed on the animation's events, music with true silences, -14 LUFS.

    python3 zk/audio.py storyboards/P01_the_button      -> renders/<name>/mix.wav and <name>_final.mp4

Inputs: renders/<name>/events.json (written by zk/render.py) and storyboards/<name>/sound.json:
  {"music": {"file": "audio/music/Sneaky_Snitch.mp3", "level": -17, "start": 0.9, "offset": 0.0,
             "mute": [[3.16, 6.4], [8.9, 12.3]], "fade": 0.12},
   "rules": true,                       # automatic effects from the events (falls, landings, presses...)
   "cues": [{"t": 3.4, "sound": "crickets", "gain": -4}, ...]}   # times may use the scene's marks
Sounds are names of files in audio/library (without .ogg) or paths.
"""
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
LIB = os.path.join(ROOT, 'audio', 'library')
_cache = {}
ALIASES = {'boing_far': dict(sound='boing_metal', gain=-15, lowpass=2200, pan=0.45),
           'whistle_long': dict(sound='whistle', gain=-9, fade_in=0.05),
           'whistle_short': dict(sound='whistle', gain=-9)}


def load(name):
    path = name if os.path.exists(name) else os.path.join(LIB, name + '.ogg')
    if not os.path.exists(path):
        path = os.path.join(ROOT, name)
    if path in _cache:
        return _cache[path]
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy()
    _cache[path] = a
    return a


def db(g):
    return 10 ** (g / 20.0)


def lowpass(x, cutoff):
    """one-pole low-pass (enough to push a sound into the distance)."""
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def repitch(x, semitones):
    """plays the sound faster (higher) or slower (lower), like a tape: fine for clicks and knocks."""
    if not semitones:
        return x
    k = 2 ** (semitones / 12.0)
    idx = np.arange(0, len(x) - 1, k)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def place(buf, snd, t, gain=0.0, fade_in=0.004, fade_out=0.02, pan=0.0, tail=None, start=0.0, length=None, lp=None, pitch=0.0):
    x = repitch(snd, pitch)
    if tail is not None:                                   # the last `tail` seconds (a fall whistle that ends on impact)
        x = x[max(0, len(x) - int(tail * SR)):]
    else:
        x = x[int(start * SR):]
    if length is not None:
        x = x[:int(length * SR)]
    x = x.astype(np.float32) * db(gain)
    if lp:
        x = lowpass(x, lp)
    n = len(x)
    fi = min(n, max(1, int(fade_in * SR))); fo = min(n, max(1, int(fade_out * SR)))
    x[:fi] *= np.linspace(0, 1, fi); x[n - fo:] *= np.linspace(1, 0, fo)
    i0 = int(round(t * SR))
    if i0 < 0:
        x = x[-i0:]; i0 = 0
    i1 = min(buf.shape[1], i0 + len(x))
    if i1 <= i0:
        return
    l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
    buf[0, i0:i1] += x[:i1 - i0] * l * 1.414
    buf[1, i0:i1] += x[:i1 - i0] * r * 1.414


def auto_cues(events):
    """the house rules: every visible action gets its sound."""
    cues = []
    for e in events:
        k = e['kind']; t = e['t']
        if k == 'fall_start':
            snd = e.get('sound', 'whistle')
            if snd and snd != 'none':
                cues.append(dict(t=t, sound='whistle', gain=-9, tail=e['dur'] + 0.05, fade_in=0.15 if t < 0.1 else 0.06))
        elif k == 'land':
            snd = e.get('sound', 'thud')
            if snd == 'thud_metal':
                cues += [dict(t=t, sound='thud_metal', gain=-2), dict(t=t + 0.01, sound='boing', gain=-12)]
            elif snd == 'bonk':
                cues += [dict(t=t - 0.01, sound='boing', gain=0), dict(t=t, sound='bonk_birds', gain=-3)]
            elif snd == 'tap':
                cues.append(dict(t=t, sound='tap', gain=-14 + 6 * e.get('strength', 0.3)))
            elif snd and snd != 'none':
                cues.append(dict(t=t, sound='thud_soft', gain=-6))
        elif k == 'press':
            cues.append(dict(t=t, sound='click', gain=-5))
        elif k == 'action':
            a = e['action']
            if a == 'facepalm':
                cues.append(dict(t=t + 0.42, sound='slap', gain=-10))
            elif a == 'exaggerated_reaction':
                cues.append(dict(t=t + 0.45, sound='pop', gain=-8))
    return cues


def resolve(t, marks):
    if isinstance(t, (int, float)):
        return float(t)
    s = str(t).replace(' ', '')
    for sign in ('+', '-'):
        if sign in s[1:]:
            i = s.index(sign, 1)
            return marks[s[:i]] + float(s[i:])
    return marks[s]


def music_track(spec, n, marks):
    m = load(os.path.join(ROOT, spec['file']))
    start = resolve(spec.get('start', 0.0), marks); off = spec.get('offset', 0.0)
    out = np.zeros(n, dtype=np.float32)
    i0 = int(start * SR); src = m[int(off * SR):int(off * SR) + n - i0]
    out[i0:i0 + len(src)] = src
    env = np.full(n, db(spec.get('level', -17)), dtype=np.float32)
    fi = int(spec.get('fade_in', 0.3) * SR); env[i0:i0 + fi] *= np.linspace(0, 1, fi)
    env[:i0] = 0
    f = int(spec.get('fade', 0.12) * SR)
    for a, b in spec.get('mute', []):
        a = int(resolve(a, marks) * SR); b = int(resolve(b, marks) * SR)
        a0 = max(0, a - f); env[a0:a] *= np.linspace(1, 0, a - a0); env[a:b] = 0
        b1 = min(n, b + f * 3); env[b:b1] *= np.linspace(0, 1, b1 - b)
    end = spec.get('end')
    if end is not None:
        e = int(resolve(end, marks) * SR); env[e:] = 0
    return out * env


def loudnorm(src, dst, I=-14.0, TP=-2.0, LRA=11.0):
    """two-pass EBU R128 normalisation: measure, then apply linearly (short clips miss the target in one pass)."""
    import re
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', src, '-af',
                        'loudnorm=I=%g:TP=%g:LRA=%g:print_format=json' % (I, TP, LRA), '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    if not m:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-af', 'loudnorm=I=%g:TP=%g:LRA=%g' % (I, TP, LRA), '-ar', str(SR), dst],
                       check=True)
        return
    j = json.loads(m.group(0))
    af = ('loudnorm=I=%g:TP=%g:LRA=%g:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true'
          % (I, TP, LRA, j['input_i'], j['input_tp'], j['input_lra'], j['input_thresh'], j['target_offset']))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-af', af, '-ar', str(SR), dst], check=True)


def main(story):
    story = os.path.abspath(story)
    scene = json.load(open(os.path.join(story, 'scene.json')))
    name = scene.get('name', os.path.basename(story))
    rd = os.path.join(ROOT, 'renders', name)
    ev = json.load(open(os.path.join(rd, 'events.json')))
    snd = json.load(open(os.path.join(story, 'sound.json')))
    marks = ev.get('marks', {})
    dur = ev['frames'] / ev['fps']
    n = int(dur * SR) + 1
    buf = np.zeros((2, n), dtype=np.float32)
    cues = auto_cues(ev['events']) if snd.get('rules', True) else []
    for c in ev['events']:
        if c['kind'] == 'cue' and c.get('sound'):
            cues.append(dict(c))
    cues += [dict(c, t=resolve(c['t'], marks)) for c in snd.get('cues', [])]
    cues = [dict(ALIASES[c['sound']], **{k: v for k, v in c.items() if k != 'sound'}) if c.get('sound') in ALIASES else c
            for c in cues]
    for c in cues:
        place(buf, load(c['sound']), c['t'], gain=c.get('gain', 0), fade_in=c.get('fade_in', 0.004),
              fade_out=c.get('fade_out', 0.03), pan=c.get('pan', 0.0), tail=c.get('tail'), start=c.get('start', 0.0),
              length=c.get('length'), lp=c.get('lowpass'), pitch=c.get('pitch', 0.0))
    if snd.get('music'):
        mt = music_track(snd['music'], n, marks)
        buf += np.vstack([mt, mt])
    peak = np.abs(buf).max()
    if peak > 0.98:
        buf *= 0.98 / peak
    raw = os.path.join(rd, 'mix_raw.wav'); mix = os.path.join(rd, 'mix.wav')
    pcm = (np.clip(buf.T, -1, 1) * 32767).astype(np.int16)
    import wave
    with wave.open(raw, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    loudnorm(raw, mix)
    vids = sorted(f for f in os.listdir(rd) if f.endswith('_silent.mp4'))
    if vids:
        out = os.path.join(rd, '%s_final.mp4' % name)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', os.path.join(rd, vids[-1]), '-i', mix, '-map', '0:v', '-map', '1:a',
                        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], check=True)
        print('final:', out)
    print('mix:', mix, '%d cues' % len(cues))


if __name__ == '__main__':
    main(sys.argv[1])
