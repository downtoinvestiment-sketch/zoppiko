"""Storyboard contact sheet: stills in a grid with their time and a note.

    python3 tools/contact_sheet.py renders/P01_the_button/stills out.jpg [cols] [notes.json]
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_B = os.path.join(ROOT, 'brand', 'fonts', 'Fredoka-Bold.ttf')
FONT_R = os.path.join(ROOT, 'brand', 'fonts', 'Nunito-Regular.ttf')


def font(path, size, fallback='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(fallback, size)


def main(folder, out, cols=6, notes=None):
    files = sorted(glob.glob(os.path.join(folder, 's_*.jpg')), key=lambda f: float(os.path.basename(f)[2:-4]))
    notes = json.load(open(notes)) if notes and os.path.exists(notes) else {}
    ims = [Image.open(f).convert('RGB') for f in files]
    w, h = ims[0].size
    tw = 360; th = int(h * tw / w); lab = 62
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw + (cols + 1) * 12, rows * (th + lab) + (rows + 1) * 12), (255, 241, 220))
    d = ImageDraw.Draw(sheet)
    fb = font(FONT_B, 24); fr = font(FONT_R, 17, '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    for i, (f, im) in enumerate(zip(files, ims)):
        x = 12 + (i % cols) * (tw + 12); y = 12 + (i // cols) * (th + lab + 12)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        t = os.path.basename(f)[2:-4].lstrip('0') or '0'
        t = t if not t.startswith('.') else '0' + t
        d.text((x + 4, y + th + 4), '%s s' % t, fill=(31, 44, 82), font=fb)
        note = notes.get(t, notes.get(str(float(t)), ''))
        if note:
            d.text((x + 4, y + th + 34), note[:40], fill=(31, 44, 82), font=fr)
    sheet.save(out, quality=90)
    print(out, sheet.size)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 6, a[3] if len(a) > 3 else None)
