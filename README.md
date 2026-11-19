# ZOPPIKO

**Two characters. Endless chaos. Pure visual comedy.** Zero words. Pure chaos.

Zop (orange) and Piko (blue) live on the Pad, a small floating island where strange things fall from the sky.
Dialogue-free 3D slapstick in vertical 15–30 s episodes, for everyone, everywhere. Handle: **@zoppiko**.

- Brand & Character Bible (Claude doc): https://claude.ai/artifact/PmPxEZ47ASG7gFnVVeL22c
- How a video is made: `documentation/PIPELINE.md` · scene files: `documentation/SCENE_FORMAT.md`

## Status (19 Nov 2026)

| Item | State |
| --- | --- |
| Characters | locked, procedural rig in `engine/` (31 motions, 16 expressions), references in `characters/references/` |
| Brand kit | logo, profile picture, YouTube banner, Facebook cover, brand sheet in `brand/kit/` |
| Social accounts | the author is creating @zoppiko on YouTube, TikTok, Instagram, Facebook |
| Concepts | 30 scored in `ideas/concepts.csv` |
| P01 The Button | storyboard done, final render in progress |
| P02 The Last Cookie, P03 The Second Peel | to storyboard |
| Publishing | nothing published; needs the author's approval of the schedule |

## Folders

| Folder | What it holds |
| --- | --- |
| `engine/cartoon_character/` | the character engine (vendored copy; only change: variant names `zop` and `piko`) |
| `zk/` | ZOPPIKO layer: the Pad and sky, props, physics, camera, effects (`scene.py`, `fx.py`), render (`render.py`), sound mix (`audio.py`) |
| `storyboards/<ep>/` | `scene.json` (the episode), `sound.json` (the mix), `storyboard.jpg` (contact sheet) |
| `renders/<ep>/` | frames, events, mixes, final mp4 (frames are not committed) |
| `characters/` | references, expression sheets, `CHARACTER_SPEC.json`, `CONSISTENCY_CHECKLIST.md` |
| `world/fx/` | effect images (Kenney CC0) |
| `audio/library/`, `audio/music/` | sound effects and music, licences in `audio/CREDITS.md` |
| `brand/` | fonts, renders, `make_brand.py`, `kit/` |
| `ideas/`, `scripts/` | concepts and episode notes |
| `exports/` | approved final videos, one per platform when needed |
| `published/`, `analytics/`, `experiments/`, `reports/` | publishing log, metrics, tests, weekly reports |
| `tools/` | contact sheets, brand renders |
