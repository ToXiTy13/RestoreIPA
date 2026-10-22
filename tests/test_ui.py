"""Окно загружается без ошибок QML и основные действия не падают. Без сети, Apple ID и показа окна.
python -m unittest discover tests"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from restore_gui import app as gui  # noqa: E402

MESSAGES = []


def _collect(kind, _ctx, text):
    if kind != QtMsgType.QtDebugMsg:
        MESSAGES.append(text)


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        qInstallMessageHandler(_collect)
        cls.qapp = QApplication.instance() or QApplication([])
        cls.engine, cls.backend = gui.create(cls.qapp, background=False, visible=False)

    @classmethod
    def tearDownClass(cls):
        qInstallMessageHandler(None)

    def pump(self):
        for _ in range(5):
            self.qapp.processEvents()

    def test_loads_without_qml_warnings(self):
        self.assertTrue(self.engine.rootObjects(), "Main.qml не загрузился")
        self.pump()
        self.assertEqual(MESSAGES, [], "предупреждения QML:\n" + "\n".join(MESSAGES))

    def test_pages_search_and_selection(self):
        b = self.backend
        for page in ("apps", "mine", "ipa", "home"):
            b.showPage(page)
            self.assertEqual(b.page, page)
        b.setQuery("сбер")
        self.assertGreater(b.apps.rowCount(), 0)
        b.setCategory("Банки")
        self.assertTrue(all(a.get("cat") == "Банки" for a in b.apps.items))
        b.setCategory("Все")
        b.setQuery("")
        self.assertEqual(b.apps.rowCount(), len(b.catalog.apps))
        b.toggleSelected("popular", 0)
        self.assertEqual(b.selectedCount, 1)
        self.assertTrue(b.popular.rows[0]["selected"])
        b.clearSelection()
        self.assertEqual(b.selectedCount, 0)
        self.pump()
        self.assertEqual(MESSAGES, [], "\n".join(MESSAGES))

    def test_logout_and_close_erase_email(self):
        import tempfile
        from restore_gui import storage
        b = self.backend
        with tempfile.TemporaryDirectory() as d:
            old, storage.EMAIL = storage.EMAIL, Path(d) / "email.txt"
            wipe = b.wipe_session
            b.wipe_session = lambda revoke=True: False  # настоящую сессию пользователя не трогаем
            try:
                for action in (b.logout, b.shutdown):
                    storage.EMAIL.write_text("someone@example.com", encoding="utf-8")
                    b.loggedIn, b.account = True, "someone@example.com"
                    action()
                    self.assertFalse(storage.EMAIL.exists(), f"{action.__name__} не стёр email")
                    if action == b.logout:
                        self.assertEqual(b.account, "", "после «Выйти» email остался на экране")
            finally:
                storage.EMAIL = old
                b.wipe_session = wipe

    def test_download_creates_missing_parent_folders(self):
        """У установленной версии папка — Документы\\Restore\\ipa; если нет даже Restore, скачивание не падает."""
        import tempfile
        import restore_apps as core
        b = self.backend
        with tempfile.TemporaryDirectory() as d:
            old, core.OUT_DIR = core.OUT_DIR, Path(d) / "Documents" / "Restore" / "ipa"
            stream, b.stream = b.stream, lambda cmd, quiet_json=False: (1, "")  # ipatool не запускаем
            try:
                self.assertIsNone(b.task_download("ipatool", 492224193, "Сбербанк", False))
                self.assertTrue(core.OUT_DIR.is_dir())
            finally:
                core.OUT_DIR, b.stream = old, stream

    def test_dialogs_open(self):
        b = self.backend
        b.openLogin("")
        self.assertTrue(b.loginOpen)
        b.loginOpen = False
        self.assertIn("Компоненты", b.helpText())
        self.pump()
        self.assertEqual(MESSAGES, [], "\n".join(MESSAGES))


if __name__ == "__main__":
    unittest.main()
