"""ZOPPIKO brand kit: logo, profile picture, YouTube banner, Facebook cover and a one-page brand sheet.

    python3 brand/make_brand.py          (needs brand/renders/*.png from tools/brand_renders.py)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'kit')
os.makedirs(OUT, exist_ok=True)
FREDOKA = os.path.join(HERE, 'fonts', 'Fredoka.ttf')
POPPINS = os.path.join(HERE, 'fonts', 'Poppins-Black.ttf')

PAL = dict(orange=(255, 148, 102), orange_dark=(242, 117, 63), blue=(127, 178, 255), blue_dark=(106, 156, 240),
           yellow=(255, 178, 63), teal=(28, 140, 140), navy=(31, 44, 82), cream=(255, 241, 220), coral=(255, 111, 60),
           brown=(58, 36, 22), ink=(29, 42, 74), white=(255, 255, 255))


def fredoka(size, weight=700):
    f = ImageFont.truetype(FREDOKA, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def curl_points(cx, base_y, h, flip=1, n=60):
    """antenna like a question mark: up from the top of the O, then a hook that curls over."""
    pts = []
    stem = h * 0.55
    for i in range(n // 3):
        t = i / (n // 3)
        pts.append((cx + flip * 0.05 * h * math.sin(t * 1.2), base_y - stem * t))
    top = pts[-1]
    r = h * 0.24
    ccx, ccy = top[0] + flip * r, top[1] - r * 0.15
    for i in range(n):
        a = math.pi + flip * (math.pi * 1.35) * i / n
        pts.append((ccx + r * math.cos(a) * (1 if flip > 0 else 1), ccy - abs(r * math.sin(a)) * 1.05 + (0 if i < n * 0.5 else r * 0.05)))
    return pts


def draw_curl(d, cx, base_y, h, color, width, flip=1):
    """antenna: a stem that rises from the O and a question-mark hook curling to the right (flip=1) or left (-1)."""
    pts = []
    stem = h * 0.50
    for i in range(30):
        t = i / 29
        pts.append((cx + h * 0.06 * t * t, base_y - stem * t))
    x0, y0 = pts[-1]
    r = h * 0.25
    ccx, ccy = x0 + r, y0
    for i in range(1, 46):
        a = math.pi - (1.25 * math.pi) * i / 45          # from the left point, over the top, down the right side
        pts.append((ccx + r * math.cos(a), ccy - r * math.sin(a)))
    if flip < 0:
        pts = [(2 * cx - x, y) for (x, y) in pts]
    d.line(pts, fill=color, width=width, joint='curve')
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=color)


def eye_o(img, box, ring, pupil_col, look, curl_col, size):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = min(x1 - x0, y1 - y0) / 2
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=ring)
    r = R * 0.60
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=PAL['white'])
    pr = r * 0.62; px, py = cx + look * r * 0.34, cy + r * 0.08
    d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=pupil_col)
    hr = pr * 0.30
    d.ellipse((px - pr * 0.35 - hr, py - pr * 0.42 - hr, px - pr * 0.35 + hr, py - pr * 0.42 + hr), fill=PAL['white'])
    # antenna on top of the O, curling toward the outside of the word
    w = max(6, int(size * 0.075))
    draw_curl(d, cx, cy - R + w * 0.6, R * 1.25, curl_col, w, flip=-look)


def wordmark(color, size=520, pad=60):
    f = fredoka(size)
    text = 'ZOPPIKO'
    adv = [f.getlength(ch) for ch in text]
    track = -size * 0.02
    W = int(sum(adv) + track * (len(text) - 1) + 2 * pad)
    asc, desc = f.getmetrics()
    H = int(asc + desc + pad * 2 + size * 0.75)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad; base = pad + size * 0.75
    os_ = []
    for ch, a in zip(text, adv):
        if ch == 'O':
            bb = f.getbbox('O')
            os_.append((x + bb[0], base + bb[1], x + bb[2], base + bb[3]))
        else:
            d.text((x, base), ch, font=f, fill=color)
        x += a + track
    eye_o(img, os_[0], PAL['orange'], PAL['brown'], +1, PAL['orange_dark'], size)
    eye_o(img, os_[1], PAL['blue'], PAL['ink'], -1, PAL['blue_dark'], size)
    return img.crop(img.getbbox())


def shadowed(im, off=(0, 18), blur=22, alpha=70):
    sh = Image.new('RGBA', (im.width + 120, im.height + 120), (0, 0, 0, 0))
    a = im.split()[3].point(lambda v: v * alpha // 255)
    blk = Image.new('RGBA', im.size, (20, 26, 50, 255)); blk.putalpha(a)
    sh.paste(blk, (60 + off[0], 60 + off[1]), blk)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.paste(im, (60, 60), im)
    return sh


def bg_pattern(W, H, base, seed=3, n=None, alpha=70, keep_clear=None):
    """cream background with soft orange and blue dots (never inside keep_clear = (x0, y0, x1, y1))."""
    import random
    rnd = random.Random(seed)
    img = Image.new('RGBA', (W, H), base + (255,))
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    n = n or int(W * H / 90000)
    for i in range(n):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.uniform(10, 24) * W / 2560
        if keep_clear and keep_clear[0] - r < x < keep_clear[2] + r and keep_clear[1] - r < y < keep_clear[3] + r:
            continue
        col = (PAL['orange'] if i % 2 else PAL['blue']) + (alpha,)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    img.alpha_composite(layer)
    return img


def fit(im, h):
    return im.resize((int(im.width * h / im.height), int(h)), Image.LANCZOS)


def main():
    logo = wordmark(PAL['navy']); logo.save(os.path.join(OUT, 'logo_navy.png'))
    logo_c = wordmark(PAL['cream']); logo_c.save(os.path.join(OUT, 'logo_cream.png'))
    R = os.path.join(HERE, 'renders')
    # profile picture: heads together on deep navy, circle-safe
    av = Image.open(os.path.join(R, 'avatar_duo.png')).convert('RGBA')
    crop = av.crop((95, 150, 985, 1040)).resize((1000, 1000), Image.LANCZOS)
    pic = Image.new('RGBA', (1080, 1080), PAL['navy'] + (255,))
    glow = Image.new('RGBA', (1080, 1080), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse((140, 160, 940, 960), fill=(60, 82, 140, 255)); glow = glow.filter(ImageFilter.GaussianBlur(120))
    pic.alpha_composite(glow)
    pic.alpha_composite(crop, (40, 70))
    pic.convert('RGB').save(os.path.join(OUT, 'profile_1080.png'))
    m = Image.new('L', (1080, 1080), 0); ImageDraw.Draw(m).ellipse((0, 0, 1079, 1079), fill=255)
    circ = pic.copy(); circ.putalpha(m); circ.save(os.path.join(OUT, 'profile_preview_circle.png'))
    # characters for banners
    A = Image.open(os.path.join(R, 'banner_a.png')).convert('RGBA'); Bb = Image.open(os.path.join(R, 'banner_b.png')).convert('RGBA')
    zop = A.crop((0, 0, A.width // 2, A.height)); zop = zop.crop(zop.getbbox())
    piko = Bb.crop((Bb.width // 2, 0, Bb.width, Bb.height)); piko = piko.crop(piko.getbbox())
    tag_f = ImageFont.truetype(POPPINS, 64)
    # YouTube banner 2560x1440, safe area 1546x423 in the centre
    W, H = 2560, 1440
    sx0, sy0 = (W - 1546) // 2, (H - 423) // 2
    yt = bg_pattern(W, H, PAL['cream'], keep_clear=(sx0 - 40, sy0 - 40, sx0 + 1586, sy0 + 463))
    lg = fit(logo, 190); yt.alpha_composite(lg, ((W - lg.width) // 2, sy0 + 70))
    d = ImageDraw.Draw(yt)
    tag = 'Zero words. Pure chaos.'
    tw = d.textlength(tag, font=tag_f)
    d.text(((W - tw) / 2, sy0 + 70 + 190 + 34), tag, font=tag_f, fill=PAL['teal'])
    zh = 400
    z = fit(zop, zh); p = fit(piko, zh)
    yt.alpha_composite(z, (sx0 + 20, sy0 + 423 - zh + 4)); yt.alpha_composite(p, (sx0 + 1546 - p.width - 20, sy0 + 423 - zh + 4))
    yt.convert('RGB').save(os.path.join(OUT, 'youtube_banner_2560x1440.png'))
    prev = yt.copy(); dp = ImageDraw.Draw(prev)
    dp.rectangle((sx0, sy0, sx0 + 1546, sy0 + 423), outline=(230, 57, 70), width=4)
    prev.convert('RGB').resize((1280, 720)).save(os.path.join(OUT, 'youtube_banner_safe_area_check.jpg'), quality=88)
    # Facebook cover 1640x624
    W, H = 1640, 624
    fb = bg_pattern(W, H, PAL['cream'], seed=5, keep_clear=(120, 110, W - 120, H - 20))
    lg = fit(logo, 160); fb.alpha_composite(lg, ((W - lg.width) // 2, 150))
    d = ImageDraw.Draw(fb); tf = ImageFont.truetype(POPPINS, 52); tw = d.textlength(tag, font=tf)
    d.text(((W - tw) / 2, 150 + 160 + 30), tag, font=tf, fill=PAL['teal'])
    z = fit(zop, 470); p = fit(piko, 470)
    fb.alpha_composite(z, (190, H - 470 - 30)); fb.alpha_composite(p, (W - 190 - p.width, H - 470 - 30))
    fb.convert('RGB').save(os.path.join(OUT, 'facebook_cover_1640x624.png'))
    # brand sheet
    W, H = 1800, 1500
    sh = Image.new('RGBA', (W, H), PAL['cream'] + (255,)); d = ImageDraw.Draw(sh)
    lg = fit(logo, 230); sh.alpha_composite(lg, ((W - lg.width) // 2, 70))
    d.text(((W - d.textlength(tag, font=tag_f)) / 2, 340), tag, font=tag_f, fill=PAL['teal'])
    sw = [('Zop Orange', 'orange', '#FF9466'), ('Piko Blue', 'blue', '#7FB2FF'), ('Sunny Yellow', 'yellow', '#FFB23F'),
          ('Teal', 'teal', '#1C8C8C'), ('Deep Navy', 'navy', '#1F2C52'), ('Cream', 'cream', '#FFF1DC'), ('Coral', 'coral', '#FF6F3C')]
    lf = ImageFont.truetype(POPPINS, 30); sf = fredoka(30, 500)
    for i, (n, k, hx) in enumerate(sw):
        x = 90 + i * 235; y = 470
        d.rounded_rectangle((x, y, x + 200, y + 200), 28, fill=PAL[k], outline=(31, 44, 82) if k == 'cream' else None, width=3)
        d.text((x, y + 215), n, font=lf, fill=PAL['navy']); d.text((x, y + 255), hx, font=sf, fill=PAL['navy'])
    pc = Image.open(os.path.join(OUT, 'profile_preview_circle.png')).resize((560, 560), Image.LANCZOS)
    sh.alpha_composite(pc, (110, 820))
    big = fredoka(96); d.text((780, 860), 'Fredoka Bold', font=big, fill=PAL['navy'])
    d.text((780, 990), 'Poppins Black for short text', font=ImageFont.truetype(POPPINS, 46), fill=PAL['navy'])
    d.text((780, 1080), 'Two characters. Endless chaos.', font=fredoka(52, 500), fill=PAL['teal'])
    d.text((780, 1150), 'Pure visual comedy.', font=fredoka(52, 500), fill=PAL['teal'])
    d.text((780, 1260), '@zoppiko  ·  YouTube  ·  TikTok  ·  Instagram  ·  Facebook', font=ImageFont.truetype(POPPINS, 30), fill=PAL['navy'])
    sh.convert('RGB').save(os.path.join(OUT, 'brand_sheet.jpg'), quality=92)
    print('kit:', sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main()
