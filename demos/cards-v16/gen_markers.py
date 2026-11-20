#!/usr/bin/env python3
"""v10 标记：36px 画布（显示 18px）+ 20fps 连续运动，形状极简、无超采样模糊。"""
import math, os
from PIL import Image, ImageDraw

W = 18          # 设计坐标（显示尺寸）
S = 2           # 渲染倍率 -> 36px，浏览器缩到 18px 自然获得抗锯齿
CANVAS = W * S
OUT = '/home/tongjx/WorkBuddy/github/The-garden-of-sinner/demos/cards'
DELAY = 50      # 20fps

COL = {
    'blue':        (91, 118, 247),
    'light_blue':  (146, 164, 253),
    'violet':      (177, 140, 245),
    'pink':        (229, 138, 176),
    'amber':       (224, 168, 78),
    'teal':        (58, 186, 168),
    'neutral':     (150, 160, 175),
    'dim_neutral': (92, 100, 112),
    'deep_blue':   (58, 78, 188),
    'deep_violet': (132, 100, 196),
    'deep_pink':   (176, 100, 130),
    'deep_teal':   (34, 116, 106),
    'deep_amber':  (150, 108, 40),
    'ink':         (22, 26, 32),
    'paper':       (246, 244, 236),
    'paper_line':  (148, 154, 163),
    'clip':        (214, 102, 82),
}
ORDER = list(COL)
IDX = {k: i + 1 for i, k in enumerate(ORDER)}
PAL = [0, 0, 0]                      # index 0 = 透明
PAL += [v for k in ORDER for v in COL[k]]   # index i+1 = COL[ORDER[i]]
PAL += [0, 0, 0] * (256 - 1 - len(ORDER))
assert len(PAL) == 768 and PAL[3:6] == list(COL['blue'])


def U(v):
    return int(round(v * S))


def canvas():
    return Image.new('RGBA', (CANVAS, CANVAS), (0, 0, 0, 0))


def box(d, x0, y0, x1, y1, r, color):
    d.rounded_rectangle([U(x0), U(y0), U(x1) - 1, U(y1) - 1],
                        radius=U(r), fill=COL[color] + (255,))


def dot(d, cx, cy, r, color):
    d.ellipse([U(cx - r), U(cy - r), U(cx + r) - 1, U(cy + r) - 1], fill=COL[color] + (255,))


def to_palette(im):
    out = Image.new('P', (CANVAS, CANVAS), 0)
    out.putpalette(PAL)
    px = im.load()
    opaque = [(i + 1, COL[k]) for i, k in enumerate(ORDER)]
    for y in range(CANVAS):
        for x in range(CANVAS):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            best, bd = 0, 1 << 30
            for i, (cr, cg, cb) in opaque:
                dd = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
                if dd < bd:
                    bd, best = dd, i
            out.putpixel((x, y), best)
    return out


def clamp01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def smooth(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def seg(p, a, b):
    return smooth((p - a) / (b - a)) if b > a else 0.0


# ---------------- 01 MDAP：方形三块错位展开，细线连回中心 ----------------
def mdap(p):
    im = canvas()
    d = ImageDraw.Draw(im)
    if p < 0.18:
        s = 0.0
    elif p < 0.46:
        s = seg(p, 0.18, 0.46)
    elif p < 0.70:
        s = 1.0
    elif p < 0.96:
        s = 1 - seg(p, 0.70, 0.96)
    else:
        s = 0.0

    db, dv, da = -3.2 * s, 3.0 * s, 3.0 * s
    if s > 0.06:
        for (x0, y0) in ((5.0 + db, 9.0), (11.0 + dv, 6.0 + -3.0 * s), (11.0 + da, 11.5 + da)):
            d.line([U(x0), U(y0), U(9), U(9)], fill=COL['neutral'] + (255,), width=S)
        dot(d, 9, 9, 1.15 + 0.15 * math.sin(p * 2 * math.pi * 2), 'pink')

    box(d, 4 + db, 4, 8 + db, 14, 0.8, 'blue')
    box(d, 8 + dv, 4 - 3.0 * s, 14 + dv, 9 - 3.0 * s, 0.8, 'violet')
    box(d, 8 + da, 9 + da, 14 + da, 14 + da, 0.8, 'amber')
    return to_palette(im)


# ---------------- 02 token-trace：四色柱固定颜色，高度依次波动 ----------------
BARS = [(2.6, 5.4, 'teal'),
        (6.6, 8.6, 'blue'),
        (10.6, 6.4, 'violet'),
        (14.6, 10.2, 'pink')]
BASE_Y = 15.4


def token(p):
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle([U(2), U(BASE_Y), U(17) - 1, U(BASE_Y) + S - 1], fill=COL['dim_neutral'] + (255,))
    for i, (x, base, color) in enumerate(BARS):
        # 相位依次错开 1/4 周期：四根柱像均衡器一样挨个抬起
        wave = math.sin(2 * math.pi * (p - i * 0.25))
        h = base + 1.5 * wave
        box(d, x, BASE_Y - h, x + 2.2, BASE_Y, 0.5, color)
    return to_palette(im)


# ---------------- 03 SuperV：Super+V 同按 -> 缩小消失 -> 📋 clipboard 弹出 ----------------
KEY_W, KEY_H = 5.4, 5.8
KEY_Y = 10.2
KEYS = [(2.2, 'blue'), (10.4, 'pink')]


def _keycap(d, x, y, color, sc):
    if sc < 0.12:
        return
    w, h = KEY_W * sc, KEY_H * sc
    cx = x + KEY_W / 2
    cy = y + KEY_H / 2
    x0, y0 = cx - w / 2, cy - h / 2
    box(d, x0, y0 + 0.8 * sc, x0 + w, y0 + h + 0.8 * sc, min(1.6 * sc, w / 3), 'dim_neutral')
    box(d, x0, y0, x0 + w, y0 + h, min(1.6 * sc, w / 3), color)


def _clipboard(d, cx, cy, sc):
    if sc < 0.5:
        return
    w, h = 9.6 * sc, 10.2 * sc
    x, y = cx - w / 2, cy - h / 2
    box(d, x - 0.35 * sc, y + 0.35 * sc, x + w + 0.35 * sc, y + h + 0.35 * sc,
        min(1.1 * sc, w / 3), 'dim_neutral')
    box(d, x - 0.15 * sc, y - 0.15 * sc, x + w + 0.15 * sc, y + h + 0.15 * sc,
        min(1.0 * sc, w / 3), 'ink')
    box(d, x, y, x + w, y + h, min(0.9 * sc, w / 3), 'paper')
    box(d, cx - 2.0 * sc, y + 0.4 * sc, cx + 2.0 * sc, y + 2.2 * sc, 0.5 * sc, 'clip')
    for i, frac in enumerate((0.36, 0.52, 0.68)):
        box(d, x + 1.4 * sc, y + (4.0 + i * 1.7) * sc,
            x + w * (frac + 0.30), y + (4.0 + i * 1.7) * sc + max(0.7 * sc, 0.55),
            0.2 * sc, 'paper_line')


def superv(p):
    im = canvas()
    d = ImageDraw.Draw(im)
    # 5s 周期：0.05-0.15 按下 / 0.15-0.30 键帽缩小消失 /
    # 0.28-0.42 剪贴板弹出 / 0.42-0.88 完全展开停留 2.3s / 0.88-0.96 收回
    press = clamp01(seg(p, 0.05, 0.15) - seg(p, 0.18, 0.26))
    vanish = clamp01(seg(p, 0.15, 0.30) - seg(p, 0.92, 1.00))
    pop = clamp01(seg(p, 0.28, 0.42) - seg(p, 0.88, 0.96))

    ky = KEY_Y + 1.2 * press
    ksc = 1.0 - vanish
    for x0, color in KEYS:
        _keycap(d, x0, ky, color, ksc)
    if ksc > 0.45:
        d.line([U(4.1), U(ky + 1.8), U(5.7), U(ky + 1.8)], fill=COL['ink'] + (255,), width=S)
        d.line([U(4.9), U(ky + 1.0), U(4.9), U(ky + 2.6)], fill=COL['ink'] + (255,), width=S)
        d.line([U(11.9), U(ky + 2.0), U(13.1), U(ky + 4.3)], fill=COL['ink'] + (255,), width=S)
        d.line([U(13.1), U(ky + 4.3), U(14.3), U(ky + 2.0)], fill=COL['ink'] + (255,), width=S)

    sc = 0.70 + 0.30 * pop
    if pop > 0.02:
        _clipboard(d, 9.0, 9.8 - 4.2 * pop, sc)
    return to_palette(im)


BUILD = [('mdap', mdap, 2.4), ('token-trace', token, 2.0), ('superv', superv, 5.0)]


def save_gif(path, frames):
    # 关键：optimize=False + disposal=1，每帧存完整画面。
    # optimize=True 会把 39/41 帧编码成局部 delta 帧；配合透明背景 + disposal=2，
    # PIL 能正确解码，但 Chrome / 文件管理器渲染不一致 -> clipboard 消失。
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=DELAY,
                   loop=0, transparency=0, disposal=1, optimize=False)


def main():
    for name, fn, period in BUILD:
        for tag in ('0.5', '0.75', '1'):
            f = float(tag)
            n = max(8, int(round(period / (DELAY / 1000.0 * f))))
            frames = [fn(i / n) for i in range(n)]
            p = os.path.join(OUT, '%s-%sx.gif' % (name, tag))
            save_gif(p, frames)
            print('%-12s %-4s frames=%3d  bytes=%6d  cycle=%.2fs' %
                  (name, tag, n, os.path.getsize(p), n * DELAY / 1000.0))


if __name__ == '__main__':
    main()
