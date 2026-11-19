# How a ZOPPIKO episode is made

Everything runs in the cloud workspace for free: Blender 5.3 as a Python module (`bpy`), Eevee, ffmpeg, numpy, Pillow.
No paid tools, no generative video. Cost per episode: zero (only time).

## Steps

1. **Idea** — pick from `ideas/concepts.csv` (scores 1–5 on visual appeal, clarity, comedy, emotion, shareability,
   rewatch, ease of production). One situation, one object, one twist, a last beat that loops.
2. **Scene file** — write `storyboards/<ep>/scene.json` (format in `SCENE_FORMAT.md`): props and their physics,
   the two characters' actions on absolute times or marks, camera shots, effects, sound cues.
3. **Storyboard check** — `python3 zk/render.py storyboards/<ep>/scene.json --stills 0,0.5,2.3,...` renders key moments
   at 40 % in about 10 s each; `python3 tools/contact_sheet.py renders/<ep>/stills storyboards/<ep>/storyboard.jpg 6`
   makes the sheet. Fix staging until every still passes the checklist (faces visible, no intersections).
4. **Render** — `nohup python3 zk/render.py storyboards/<ep>/scene.json --samples 6 --budget 7000 > /tmp/<ep>.log 2>&1 &`
   1080×1920, 24 fps, about 25 s per frame (2 cores, no GPU): a 15 s episode takes about 2.5 hours. Rerun the same
   command to resume; when all frames exist it writes `renders/<ep>/<ep>_1080x1920_silent.mp4`.
5. **Sound** — `storyboards/<ep>/sound.json` (music with true silences + extra cues); effects for falls, landings,
   presses, slaps and reactions come automatically from `renders/<ep>/events.json`.
   `python3 zk/audio.py storyboards/<ep>` writes the -14 LUFS mix and `renders/<ep>/<ep>_final.mp4`.
6. **QC** — extract frames every 0.5 s, check against `characters/CONSISTENCY_CHECKLIST.md`, watch with sound.
   Reject and fix anything off-model, unreadable on a phone, or with a sound out of sync.
7. **Export and publish** — copy to `exports/`, write titles, descriptions (with music credits) and hashtags,
   log in `published/registry.csv`. Publishing only on the schedule the author approved.
8. **Measure** — fill `analytics/metrics.csv` at 48 hours and 7 days; one change per experiment (`experiments/log.md`).

## Tools in this repository

| Need | Tool |
| --- | --- |
| Characters, motions, expressions | `engine/cartoon_character` (Character API, 31 motions, 16 expressions) |
| Island, sky, props, physics, camera, squash | `zk/scene.py` |
| Dust, sparkles, impact and dizzy stars | `zk/fx.py` |
| Frames, stills, video | `zk/render.py` |
| Sound effects and music mix | `zk/audio.py` |
| Logo, profile picture, banners | `tools/brand_renders.py` then `brand/make_brand.py` |

## Measured costs (19 Nov 2026)

- Stills at 40 %: about 11 s each. Full frame 1080×1920 at 6 samples: about 25 s.
- Building a scene (characters, physics, keys): about 5 s.
- Sound mix: about 2 s.
