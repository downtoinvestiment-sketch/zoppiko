# ZOPPIKO

**Two characters. Endless chaos. Pure visual comedy.** Zero words. Pure chaos.

Zop (orange) and Piko (blue) live on the Pad, a small floating island where strange things fall from the sky.
Dialogue-free 3D slapstick in vertical 15–30 s episodes, for everyone, everywhere. Handle: **@zoppiko**.

- Brand & Character Bible (Claude doc): https://claude.ai/artifact/PmPxEZ47ASG7gFnVVeL22c
- How a video is made: `documentation/PIPELINE.md` · scene files: `documentation/SCENE_FORMAT.md`

## Status (20 Nov 2026)

| Item | State |
| --- | --- |
| Characters | locked, procedural rig in `engine/` (31 motions, 16 expressions), references in `characters/references/` |
| Brand kit | logo, profile picture, YouTube banner, Facebook cover, brand sheet in `brand/kit/` |
| Social accounts | YouTube Zoppiko (@Zoppiko), Facebook page Zoppiko, TikTok @unseenworld (handle change possible from 5 Dec 2026), Instagram zoppiko to sign in on the desktop browser |
| Concepts | 30 scored in `ideas/concepts.csv` |
| P01 The Button | final video done and checked: `exports/P01_the_button/` (master H.264, upload HEVC ≤3.7 MB) |
| P02 The Last Cookie | final video done and checked (rolling cookie re-rendered in front of Piko's feet): `exports/P02_the_last_cookie/` |
| P03 The Second Peel | final render in progress (4 samples: same look as 6, 35% faster) |
| P04 Domino Day | format test "satisfying + gag": simulated chain of 46 dominoes, storyboard stills checked, render after P03 |
| P05 The Paper Plane | scene and sound written (flight paths, ducking); preview stills to check |
| Publishing | approved by the author (19 Nov 2026); auto mode on (20 Nov); uploads need a PC folder connected to the chat (author to add `Video\Zoppiko`); YouTube: not made for kids, no AI label (author's decisions); texts in `published/drafts.md` |

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
