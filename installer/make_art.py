"""Рисует иконку программы (assets/icon.png, assets/icon.ico) и картинки мастера установки (installer/wizard/)
в цветах интерфейса: изумрудный градиент, белая стрелка «скачать», шрифт Manrope.
Запуск: python installer/make_art.py — результат кладётся в репозиторий, при сборке скрипт не нужен."""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QImage, QLinearGradient, QPainter,  # noqa: E402
                           QPen)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from restore_gui import theme  # noqa: E402

P = theme.QML
GRAD1, GRAD2 = QColor(P["grad1"]), QColor(P["grad2"])
# масштабы экрана, под которые Inno Setup выбирает картинку (100–200 %)
SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)


def image(w, h):
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    return img


def painter(img):
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    return p


def arrow(p, x, y, s, color):
    """Стрелка «скачать» с чертой, как в Logo.qml; (x, y) — левый верхний угол квадрата s×s."""
    pen = QPen(color, max(1.5, s * 0.085), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    pt = lambda fx, fy: QPointF(x + s * fx, y + s * fy)  # noqa: E731
    p.drawLine(pt(0.5, 0.25), pt(0.5, 0.58))
    p.drawPolyline([pt(0.35, 0.44), pt(0.5, 0.59), pt(0.65, 0.44)])
    p.drawLine(pt(0.31, 0.73), pt(0.69, 0.73))


def logo(p, x, y, s):
    """Круг с изумрудным градиентом и белой стрелкой."""
    g = QLinearGradient(x, y, x + s, y + s)
    g.setColorAt(0, GRAD1)
    g.setColorAt(1, GRAD2)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QRectF(x, y, s, s))
    arrow(p, x, y, s, QColor("white"))


def icon(size):
    img = image(size, size)
    p = painter(img)
    m = size * 0.02  # отступ, чтобы край круга не обрезался сглаживанием
    logo(p, m, m, size - 2 * m)
    p.end()
    return img


def png_bytes(img):
    buf = QBuffer()
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def save_ico(path, sizes):
    """ICO из нескольких PNG (так Windows берёт чёткую картинку под каждый размер)."""
    pngs = [png_bytes(icon(s)) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, data in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(head + entries + b"".join(pngs))


def wizard_image(k):
    """Большая картинка слева на первой и последней страницах мастера (164×314 при 100 %)."""
    w, h = round(164 * k), round(314 * k)
    img = image(w, h)
    p = painter(img)
    g = QLinearGradient(0, 0, w * 0.4, h)
    g.setColorAt(0, GRAD1)
    g.setColorAt(1, GRAD2)
    p.fillRect(0, 0, w, h, g)
    # мягкие круги на фоне
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 22))
    p.drawEllipse(QPointF(w * 1.05, h * 0.08), w * 0.62, w * 0.62)
    p.setBrush(QColor(255, 255, 255, 16))
    p.drawEllipse(QPointF(-w * 0.1, h * 0.98), w * 0.75, w * 0.75)
    # белый круг со стрелкой
    s = 76 * k
    x, y = (w - s) / 2, h * 0.27
    p.setBrush(QColor("white"))
    p.drawEllipse(QRectF(x, y, s, s))
    arrow(p, x, y, s, GRAD2)
    # название и подпись
    p.setPen(QColor("white"))
    f = QFont(theme.FONT)
    f.setPixelSize(round(24 * k))
    f.setWeight(QFont.ExtraBold)
    p.setFont(f)
    p.drawText(QRectF(0, y + s + 14 * k, w, 34 * k), Qt.AlignHCenter | Qt.AlignVCenter, "Restore")
    f.setPixelSize(round(11 * k))
    f.setWeight(QFont.Medium)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 215))
    p.drawText(QRectF(10 * k, y + s + 48 * k, w - 20 * k, 40 * k), Qt.AlignHCenter | Qt.TextWordWrap,
               "возврат удалённых\nприложений на iPhone")
    p.end()
    return img


def wizard_small(k):
    """Маленькая картинка в шапке остальных страниц (55×55 при 100 %): логотип на прозрачном фоне."""
    n = round(55 * k)
    img = image(n, n)
    p = painter(img)
    s = n * 0.8
    logo(p, (n - s) / 2, (n - s) / 2, s)
    p.end()
    return img


def main():
    app = QGuiApplication([])  # noqa: F841 — без приложения Qt не рисует текст
    for ttf in sorted((ROOT / "restore_gui" / "fonts").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    icon(256).save(str(ROOT / "assets" / "icon.png"))
    save_ico(ROOT / "assets" / "icon.ico", (16, 20, 24, 32, 40, 48, 64, 128, 256))
    out = ROOT / "installer" / "wizard"
    out.mkdir(exist_ok=True)
    for k in SCALES:
        pct = round(k * 100)
        wizard_image(k).save(str(out / f"image-{pct}.png"))
        wizard_small(k).save(str(out / f"small-{pct}.png"))
    print("готово:", out)


if __name__ == "__main__":
    main()
