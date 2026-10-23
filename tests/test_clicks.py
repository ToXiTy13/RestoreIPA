"""Настоящие клики мышью по окну: нажатие попадает только в то, по чему нажали.
(Ошибка, которую ловит тест: TapHandler не «съедает» нажатие, и оно срабатывало ещё и на том, что под ним —
клик по копии в панели приложения открывал плитку главной под панелью, клик по галочке открывал приложение.)"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sandbox  # noqa: E402 — до restore_apps: тесты не трогают настоящие данные программы
assert sandbox.ROOT
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtQuick import QQuickWindow  # noqa: E402 — с этим импортом окно приходит как QQuickWindow
from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from restore_gui import app as gui  # noqa: E402
from restore_gui import storage  # noqa: E402

# настройки тестового окна — во временную папку, а не в settings.json пользователя
_SETTINGS_DIR = tempfile.TemporaryDirectory()
storage.SETTINGS = Path(_SETTINGS_DIR.name) / "settings.json"

SBER = 492224193


def wait(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


class Clicks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])
        cls.engine, cls.b = gui.create(cls.qapp, background=False, visible=True)
        cls.win = cls.engine.rootObjects()[0]
        assert isinstance(cls.win, QQuickWindow)
        cls.win.setProperty("width", 1200)
        cls.win.setProperty("height", 800)
        cls.b.detail_task = lambda d: None  # без ipatool: панель открывается, проверки не идут
        wait(cls.qapp, 0.8)

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def items(self, **props):
        """Видимые элементы окна (по дереву отображения: строки списков и панели в findChildren не попадают),
        у которых свойства совпадают с props."""
        # корни: содержимое окна и всплывающие панели (Drawer/Popup живут в отдельном слое поверх окна)
        stack = [self.win.contentItem()]
        for o in self.win.findChildren(QObject):
            if "Popup" in o.metaObject().superClass().className() or "Drawer" in o.metaObject().className() \
                    or "Popup" in o.metaObject().className():
                content = o.property("contentItem")
                if content is not None and content.parentItem() is not None:
                    stack.append(content.parentItem())
        out = []
        while stack:
            it = stack.pop()
            if it is None or not it.isVisible():
                continue
            if all(it.property(k) == v for k, v in props.items()):
                out.append(it)
            stack.extend(it.childItems())
        return out

    def click(self, item, dx=None):
        w, h = item.property("width"), item.property("height")
        p = item.mapToScene(QPointF(w / 2 if dx is None else dx, h / 2))
        QTest.mouseClick(self.win, Qt.LeftButton, Qt.NoModifier, QPoint(int(p.x()), int(p.y())))
        wait(self.qapp, 0.6)

    def test_clone_click_opens_clone_not_tile_below(self):
        b = self.b
        b.showPage("home")
        b.openDetail("popular", 0)  # Сбербанк
        wait(self.qapp, 0.8)
        clones = [c for c in self.items() if c.property("statusKind") is not None and
                  isinstance(c.property("title"), str) and c.property("title").startswith("«Бюджет")]
        self.assertTrue(clones, "копия «Бюджет Онлайн» не найдена в панели")
        target = clones[0]
        expected = b.clones.items[target.property("index")]["id"]
        self.click(target)
        self.assertEqual(b.detailApp.get("id"), expected,
                         f"открылось {b.detailApp.get('name')} вместо копии")
        b.closeDetail()
        wait(self.qapp, 0.5)

    def test_checkbox_selects_without_opening_app(self):
        b = self.b
        b.closeDetail()
        b.clearSelection()
        b.showPage("apps")
        wait(self.qapp, 0.5)
        rows = [r for r in self.items(listName="apps") if r.property("index") == 1]
        self.assertTrue(rows, "строка списка не найдена")
        self.click(rows[0], dx=14 + 11)  # центр круглой галочки слева в строке
        self.assertEqual(b.selectedCount, 1, "галочка не отметилась")
        self.assertFalse(b.detailOpen, "нажатие на галочку открыло приложение")
        b.clearSelection()
        self.click(rows[0])  # нажатие по строке — открывает приложение
        self.assertTrue(b.detailOpen)
        self.assertEqual(b.selectedCount, 0)
        b.closeDetail()
        wait(self.qapp, 0.5)


if __name__ == "__main__":
    unittest.main()
