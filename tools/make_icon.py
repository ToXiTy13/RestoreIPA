"""Иконка программы (assets/icon.ico): тот же логотип, что рисует App._logo — круг с градиентом и стрелка вниз.

Запуск: build\\venv\\Scripts\\python tools\\make_icon.py  (нужен Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

GRAD1, GRAD2 = (0x6D, 0x5D, 0xFC), (0x3B, 0x82, 0xF6)
SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


def draw(size, ss=4):
    s = size * ss  # рисуем крупно и уменьшаем — так края гладкие
    grad = Image.new("RGB", (s, s))
    px = grad.load()
    for x in range(s):
        t = x / (s - 1)
        c = tuple(int(a + (b - a) * t) for a, b in zip(GRAD1, GRAD2))
        for y in range(s):
            px[x, y] = c
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = max(int(s * .085), 2)
    cx = s / 2
    white = (255, 255, 255, 255)
    d.line([(cx, s * .26), (cx, s * .57)], fill=white, width=w)
    d.line([(cx - s * .15, s * .44), (cx, s * .59), (cx + s * .15, s * .44)], fill=white, width=w, joint="curve")
    d.line([(s * .31, s * .73), (s * .69, s * .73)], fill=white, width=w)
    for x, y in ((cx, s * .26), (cx - s * .15, s * .44), (cx + s * .15, s * .44), (s * .31, s * .73),
                 (s * .69, s * .73)):
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=white)  # скруглённые концы
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    big = draw(256)
    big.save(OUT, sizes=[(n, n) for n in SIZES], append_images=[draw(n) for n in SIZES[:-1]])
    big.save(OUT.with_suffix(".png"))
    print(OUT)
