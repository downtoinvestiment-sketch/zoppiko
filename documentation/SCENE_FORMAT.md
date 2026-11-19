# Scene file format (`storyboards/<ep>/scene.json`)

Example: `storyboards/P01_the_button/scene.json`. Times are seconds, or marks: `"p1"`, `"p1+1.58"`, `"z3-0.3"`.
A mark is set by `"mark": "name"` on a character action (for `press`, the moment of the click).

```json
{
  "name": "P01_the_button",
  "render": {"resolution": [1080, 1920], "samples": 6},
  "stage": {"horizon": "#FFDDB0", "zenith": "#6FB1FF", "sky_strength": 2.4, "ambient": 0.55, "radius": 3.2},
  "light": {"sun": 3.2, "azimuth": -38, "elevation": 48, "rim": 180},
  "camera": {"shots": [...], "shakes": [...]},
  "props": [...],
  "characters": [...],
  "fx": [...],
  "cues": [...],
  "duration_from": "z3+1.40"
}
```

## Stage and light

The Pad: a round lawn (radius 3.2 m, top at z = 0) floating in a gradient sky, flowers near the rim, white clouds.
Daylight: a warm sun (azimuth and elevation in degrees, from the front), the sky as fill, a cool rim light behind.

## Camera

- `shots`: `{"t", "location", "target", "lens", "move": {"dur", "location", "target", "lens", "delay"}}`. A new shot is a hard cut;
  `move` is a smooth push-in inside the shot.
- `shakes`: `{"t", "amount", "dur"}` for impacts.
- Home shot used so far: location [0, -4.0, 0.88], target [0, 0, 0.72], lens 48. Keep faces between 250 and 1550 px from the top.

## Props

`{"name", "type", "location", "rotation", "hidden", "motion": [segments]}`. Types: `button` (with `cap`),
`beachball` (`radius`, `colors`), `cookie`, `banana`, `peel`, `sphere`, `cylinder`, `box` (`dims`). The origin is the ground contact point.

Motion segments (each starts at `t` and lasts until the next one):

| Segment | Meaning |
| --- | --- |
| `{"t", "at": [x,y,z]}` | stays there |
| `{"t", "drop": {"to", "h", "g", "bounce", "bounces", "squash", "rot", "spin", "sound", "fall_sound"}}` | falls from `h` metres above `to`, squashes, small bounces |
| `{"t", "fly": {"from", "to", "dur", "arc", "spin", "land"}}` | arc between two points |
| `{"t", "ballistic": {"v", "g", "spin"}}` | thrown with a velocity |
| `{"t", "roll": {"from", "to", "dur", "radius", "ease"}}` | rolls on its edge |
| `{"t", "show": true}` / `{"t", "hide": true}` | visibility |
| `{"t", "press": 0.03, "dur": 0.3}` | the button cap goes down (added automatically by the `press` action) |

## Characters

`{"name": "Zop" | "Piko", "location": [x, y], "facing": degrees (0 = toward the camera, 90 = toward +X), "actions": [...],
"squash": [{"t", "pivot", "amount", "hold"}]}`.

Actions: everything in `engine/cartoon_character/docs/SCENE_JSON.md` (`play` with the 31 motions, `wait`, `turn`,
`walk_to`, `expression`, `look_at`, `point`, `pick_up`, `throw`, `push`, `pull`, `sit`, `wave`), plus:

- `{"until": t}` — idle until the next action starts exactly at `t`;
- `{"press": "button"}` — steps to the right distance if needed and presses the cap with a finger;
- `"mark": "name"` on any action.

Keep at least 0.8 m between the two characters when one leans (point, press, reactions): heads must never touch.

## Effects and cues

- `fx`: `puff` (dust), `sparkle`, `burst` (stars out of an impact), `dizzy` (stars circling a head): `{"t", "type", "at", "size", "dur", "count"}`.
- `cues`: `{"t", "sound"}` for sounds that are not automatic (crickets, sad trombone, a far boing...).
