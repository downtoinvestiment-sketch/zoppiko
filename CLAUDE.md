# ZOPPIKO — instructions for Claude

ZOPPIKO is a dialogue-free 3D comedy brand: two friends, Zop (orange) and Piko (blue), on a floating island called the Pad,
where things fall from the sky. Vertical 15–30 s episodes for YouTube Shorts, TikTok, Instagram Reels and Facebook Reels.

1. Read `README.md` (status, structure) and `documentation/PIPELINE.md` before any work. The Brand & Character Bible is a
   Claude doc: https://claude.ai/artifact/PmPxEZ47ASG7gFnVVeL22c
2. Reply to the author in Italian, with short messages: he writes from his phone. All public metadata (titles,
   descriptions, captions, bios) is in natural international English.
3. **The characters are locked.** Never change design, proportions, colours or clothes. Use only the engine variants
   `zop` and `piko` (`engine/cartoon_character/config.py`). Check every render against `characters/CONSISTENCY_CHECKLIST.md`.
4. ZOPPIKO is its own brand: no characters, names or references from Pippo e Tumbo, Ma che Scienza or Lumeconomy.
   Since 19 Nov 2026 the author allows reusing the Pippo e Tumbo production library (props, effects, HDRI, Kenney and
   Mixkit sounds, Kevin MacLeod music): copy what you use into this repository and record its licence in `audio/CREDITS.md`.
5. No words anywhere in the videos (no captions, signs or labels), no intros, no logos. Family friendly: no insults,
   no swearing, nobody really gets hurt.
6. Publishing, account settings, money, deletions and anything irreversible need the author's explicit approval.
   Never change passwords, buy anything or accept contracts. If a platform asks for verification, stop and ask.
   Never invent metrics: if a number is not accessible, say so.
7. Commit and push after every meaningful change (`git -C /home/claude/zoppiko push`).
8. Rendering: one Blender at a time (8 GB RAM, 2 cores). Long renders in the background with `--budget`; rerun the
   same command to resume. Wait for or stop a process with its PID (`kill -0 PID`), never `pgrep -f`/`pkill -f`.
   Disk is tight: delete `renders/*/frames_*` after the final video is checked.
9. Quality control before showing anything: look at stills of every shot (faces visible, no body or head
   intersections, characters on model, props readable on a phone), then watch the final video.
