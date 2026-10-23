"""Окно загружается без ошибок QML и основные действия не падают. Без сети, Apple ID и показа окна.
python -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sandbox  # noqa: E402 — до restore_apps: тесты не трогают настоящие данные программы
assert sandbox.ROOT
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from restore_gui import app as gui  # noqa: E402
from restore_gui import storage  # noqa: E402

# настройки тестового окна — во временную папку, а не в settings.json пользователя
_SETTINGS_DIR = tempfile.TemporaryDirectory()
storage.SETTINGS = Path(_SETTINGS_DIR.name) / "settings.json"

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
                        self.wait_idle()  # сессия стирается в фоне
            finally:
                storage.EMAIL = old
                b.wipe_session = wipe
                self.reopen()

    def wait_idle(self, seconds=10):
        import time
        end = time.time() + seconds
        while self.backend.busy and time.time() < end:
            self.qapp.processEvents()
            time.sleep(0.01)
        self.assertFalse(self.backend.busy, "фоновая операция не закончилась")

    def reopen(self):
        """После shutdown() в тесте: окно и процессы снова доступны следующим тестам."""
        from restore_gui import apple
        apple._CLOSED = False
        self.backend.stop_flag = False

    # ---------- остановка, сессия, выход из аккаунта, следы программы в системе ----------
    def test_wipe_session_removes_console_session_password(self):
        """Окно стирает общую с консольной версией сессию — и keychain.pass, пароль к ней."""
        import restore_apps as core
        session = core.IPATOOL_HOME / ".ipatool"
        session.mkdir(parents=True, exist_ok=True)
        (session / "cookies").write_text("{}", encoding="utf-8")
        core.KEYCHAIN_PASS.write_text("пароль консольной версии", encoding="utf-8")
        self.assertTrue(self.backend.wipe_session(revoke=False))
        self.assertFalse(session.exists())
        self.assertFalse(core.KEYCHAIN_PASS.exists())

    def test_update_items_keeps_list_instead_of_reset(self):
        """Добавление, удаление и изменение строк — без сброса модели: сброс прокручивает ListView к началу."""
        from restore_gui.models import RowsModel
        m = RowsModel(("id", "name"), key=lambda a: a["id"])
        log = []
        m.modelReset.connect(lambda: log.append("reset"))
        m.rowsInserted.connect(lambda _p, a, z: log.append(("ins", a)))
        m.rowsRemoved.connect(lambda _p, a, z: log.append(("del", a)))
        m.dataChanged.connect(lambda a, z: log.append(("chg", a.row())))
        m.set_items([{"id": 1, "name": "a"}, {"id": 3, "name": "c"}])
        log.clear()
        m.update_items([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}])
        m.update_items([{"id": 2, "name": "b"}, {"id": 3, "name": "C"}])
        self.assertEqual(log, [("ins", 1), ("del", 0), ("chg", 1)])
        self.assertEqual([r["name"] for r in m.rows], ["b", "C"])
        self.assertEqual(m.index_of, {2: 0, 3: 1})
        log.clear()
        m.update_items([{"id": 3, "name": "C"}, {"id": 2, "name": "b"}])  # другой порядок — пересборка
        self.assertEqual(log, ["reset"])
        self.assertEqual([r["id"] for r in m.rows], [3, 2])

    def test_scan_find_does_not_reset_or_recount_lists(self):
        """Находка поиска вставляет строку в «Мои» (прокрутка на месте) и не пересчитывает весь каталог."""
        b = self.backend
        saved = b.purchases, b.avail, b.owned_state.copy()
        resets, made = [], []
        b.mine.modelReset.connect(lambda: resets.append(1))
        row = b.app_row
        b._apps.make_row = lambda a: made.append(a["id"]) or row(a)
        try:
            b.on_purchases_result({1: "Банк", 2: "Магазин"}, set())
            resets.clear()
            made.clear()
            i = b.catalog.apps[0]["id"]
            b.add_found({i: b.catalog.apps[0]["name"]})
            self.assertEqual(resets, [], "список «Мои» пересобран — прокрутка сбросилась бы к началу")
            self.assertEqual(b.mine.rowCount(), 3)
            self.assertLessEqual(len(made), 1, "при каждой находке пересчитывался весь каталог")
            self.assertEqual(b.apps.rows[b.apps.index_of[i]]["status"], "✓ было у вас")
        finally:
            b._apps.make_row = row
            b.mine.modelReset.disconnect()
            b.purchases, b.avail = saved[0], saved[1]
            b.owned_state.clear()
            b.owned_state.update(saved[2])
            b.refresh_list_keep()
            b.refresh_mine()
            b.showPage("home")

    def test_qt_environment(self):
        """Без flip-модели драйвер NVIDIA не включает G-SYNC для окна (мерцание); кэш QML отключён только у
        портативного exe (он распаковывается каждый раз в новую папку); заданное снаружи не трогаем."""
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            for var in ("QT_D3D_NO_FLIP", "QML_DISABLE_DISK_CACHE"):
                os.environ.pop(var, None)
            gui.qt_environment()
            self.assertEqual(os.environ["QT_D3D_NO_FLIP"], "1")
            self.assertNotIn("QML_DISABLE_DISK_CACHE", os.environ, "кэш QML отключён у установленной версии")
            with mock.patch.object(sys, "_MEIPASS", r"C:\Temp\_MEI12345", create=True):
                gui.qt_environment()
            self.assertEqual(os.environ["QML_DISABLE_DISK_CACHE"], "1")
            os.environ["QT_D3D_NO_FLIP"] = "0"
            gui.qt_environment()
            self.assertEqual(os.environ["QT_D3D_NO_FLIP"], "0")

    def test_open_url_only_known_links(self):
        """Окно открывает в браузере только ссылки программы: донат и страницу/релизы на GitHub."""
        from unittest import mock

        from restore_gui import backend as backend_module
        b = self.backend
        opened = []
        with mock.patch.object(backend_module.QDesktopServices, "openUrl",
                               side_effect=lambda u: opened.append(u.toString()) or True):
            for url in (b.supportUrl, b.repoUrl, b.repoUrl + "/releases/tag/v9.9.9",
                        "https://evil.example.com", b.repoUrl + ".evil.com", "file:///C:/Windows/notepad.exe"):
                b.openUrl(url)
        self.assertEqual(opened, [b.supportUrl, b.repoUrl, b.repoUrl + "/releases/tag/v9.9.9"])

    def test_file_dialog_leaves_registry_as_it_was(self):
        """ask_file оборачивает QFileDialog в storage.registry_untouched: Qt пишет туда последнюю папку."""
        from unittest import mock

        from restore_gui import backend as backend_module
        entered = []

        class Guard:
            def __enter__(self):
                entered.append("in")

            def __exit__(self, *exc):
                entered.append("out")

        with mock.patch.object(backend_module.storage, "registry_untouched", Guard), \
                mock.patch.object(backend_module.QFileDialog, "getOpenFileName",
                                  side_effect=lambda *a: entered.append("dialog") or ("", "")):
            self.assertIsNone(self.backend.ask_file("t", ".", "*.ipa"))
        self.assertEqual(entered, ["in", "dialog", "out"])

    def test_logout_forgets_account_data(self):
        """После «Выйти» не остаётся покупок, отметок и выбора прежнего Apple ID, панель приложения закрыта."""
        b = self.backend
        wipe = b.wipe_session
        calls = []
        b.wipe_session = lambda revoke=True: calls.append(1) or False
        b.detail_task = lambda d: None  # без ipatool: панель открывается, проверки не идут
        try:
            b.on_purchases_result({1: "Банк A", 2: "Магазин A"}, set())
            b.toggleSelected("mine", 0)
            b.open_detail(b.mine.items[0])
            detail = b.detail
            b.loggedIn, b.account = True, "someone@example.com"
            b.logout()
            self.assertEqual((b.purchases, b.avail, b.selected, b.owned_state), ([], None, {}, {}))
            self.assertEqual(b.account, "", "после «Выйти» email остался на экране")
            self.assertEqual(b.mine.rowCount(), 0)
            self.assertFalse(b.detailOpen)
            self.assertFalse(detail["alive"], "проверки панели продолжили бы идти по стираемой сессии")
            self.wait_idle()
            self.assertEqual(calls, [1], "сессия не стёрта")
            b.add_found({3: "Найдено у B"})  # следующий аккаунт видит только своё
            self.assertEqual([a["name"] for a in b.purchases], ["Найдено у B"])
        finally:
            b.wipe_session = wipe
            del b.detail_task
            b.purchases, b.avail = [], None
            b.owned_state.clear()
            b.clear_selection()
            b.refresh_mine()
            b.showPage("home")

    def test_stop_while_waiting_for_session(self):
        """«Остановить», пока команда ждёт очереди к сессии (её держит панель приложения), — команда не запускается."""
        import threading
        import time
        b = self.backend
        b.stop_flag = False
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "ran"
            # «ipatool» по имени: is_ipatool смотрит на имя файла, а запустится python с маркером
            fake = Path(d) / "ipatool.cmd"
            fake.write_text(f'@"{sys.executable}" -c "open(r\'{marker}\', \'w\').close()"\n', encoding="utf-8")
            results = {}
            b.dlock.acquire()  # сессию держит «панель приложения»
            try:
                for name, call in (("stream", lambda: b.stream([str(fake)])),
                                   ("dq", lambda: b.dq([str(fake)], tag="task"))):
                    b.stop_flag = False
                    t = threading.Thread(target=lambda n=name, c=call: results.update({n: c()}))
                    t.start()
                    time.sleep(0.5)
                    b.on_stop()
                    t.join(timeout=5)
                    self.assertFalse(t.is_alive(), f"{name}: «Остановить» не прервал ожидание сессии")
                    self.assertNotEqual(results[name][0], 0)
            finally:
                b.dlock.release()
                b.stop_flag = False
            time.sleep(0.5)
            self.assertFalse(marker.exists(), "команда запустилась после «Остановить»")

    def test_single_instance(self):
        """Второй экземпляр не получает замок: иначе он стёр бы сессию первого."""
        first = gui.single_instance()
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(gui.single_instance())
        finally:
            first.unlock()
        second = gui.single_instance()
        self.assertIsNotNone(second, "после выхода первого замок не освободился")
        second.unlock()

    def test_scan_finds_keep_purchases_and_page(self):
        """Находка «Найти мои удалённые» добавляется к покупкам и не переключает страницу."""
        b = self.backend
        saved = b.purchases, b.avail, b.owned_state.copy()
        try:
            b.on_purchases_result({1: "Банк", 2: "Магазин"}, set())
            b.showPage("apps")
            b.add_found({3: "Ещё банк"})
            b.add_found({3: "Ещё банк"})  # повтор не дублирует
            self.assertEqual(b.page, "apps")
            self.assertEqual([a["id"] for a in b.purchases], [1, 3, 2])  # по названию
            self.assertTrue(b.owned_state[3])
            self.assertEqual(b.mine.rowCount(), 3)
        finally:
            b.purchases, b.avail = saved[0], saved[1]
            b.owned_state.clear()
            b.owned_state.update(saved[2])
            b.refresh_mine()
            b.showPage("home")

    def test_stop_interrupts_running_command(self):
        """«Остановить» завершает процесс (раньше скачивание продолжалось до конца)."""
        import threading
        import time
        b = self.backend
        b.stop_flag = False
        result = {}
        cmd = [sys.executable, "-c", "import time; print('start', flush=True); time.sleep(60)"]
        t = threading.Thread(target=lambda: result.update(r=b.stream(cmd)))
        t0 = time.time()
        t.start()
        time.sleep(1)
        b.on_stop()
        t.join(timeout=15)
        self.assertFalse(t.is_alive(), "stream не вернулся после «Остановить»")
        self.assertLess(time.time() - t0, 15)
        self.assertNotEqual(result["r"][0], 0)
        b.stop_flag = False

    def test_no_new_command_after_stop(self):
        """«Остановить» между командами (например, во время проверки iPhone) — следующая не запускается."""
        b = self.backend
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "ran"
            b.stop_flag = True
            try:
                rc, _ = b.stream([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])
            finally:
                b.stop_flag = False
            self.assertNotEqual(rc, 0)
            self.assertFalse(marker.exists(), "команда запустилась после «Остановить»")

    def test_pick_compatible_removes_probe_downloads(self):
        """Подбор версии оставляет в архиве только подошедшую версию, пробные IPA удаляет."""
        import restore_apps as core
        from restore_gui import tasks
        b = self.backend
        b.stop_flag = False
        with tempfile.TemporaryDirectory() as d:
            old, core.OUT_DIR = core.OUT_DIR, Path(d)
            saved = b.task_download, tasks.ipa_info

            def download(ipatool, app_id, name, purchase, version=None, fallback=False):
                if version in fail:
                    return None
                p = Path(d) / f"x_{app_id}_v{version}.ipa"
                p.write_bytes(b"ipa")
                storage.record_download(app_id, version)  # как настоящий task_download
                return p

            # версии 3 и новее требуют iOS 18, старые — iOS 15
            b.task_download = download
            tasks.ipa_info = lambda p: {"MinimumOSVersion": "18.0" if int(p.stem.split("_v")[1]) >= 3 else "15.0"}
            fail = set()
            try:
                # на телефоне iOS 16: пробуются 3 (не подходит) и 2 (подходит); 3 удаляется вместе с записью в истории
                best = b.pick_compatible("ipatool", 1, "x", ["5", "4", "3", "2", "1"], "16.0")
                self.assertEqual(best.name, "x_1_v2.ipa")
                self.assertEqual(sorted(p.name for p in Path(d).glob("*.ipa")), ["x_1_v2.ipa"])
                self.assertEqual(storage.load_history().get("1"), ["2"], "удалённая проба осталась в истории")
                # iOS 18: 3 подходит, следующая проба (4) не скачалась — берём 3, а не отменяем установку
                fail = {"4"}
                best = b.pick_compatible("ipatool", 1, "x", ["5", "4", "3", "2", "1"], "18.0")
                self.assertIsNotNone(best, "сбой сети на пробе выбросил уже найденную подходящую версию")
                self.assertEqual(best.name, "x_1_v3.ipa")
            finally:
                core.OUT_DIR = old
                b.task_download, tasks.ipa_info = saved
                storage.forget_download(1, "2")
                storage.forget_download(1, "3")

    def test_login_asks_2fa_even_when_ipatool_exits_0(self):
        """ipatool 2.7: «2FA code is required…» с кодом возврата 0 — это не вход, нужно спросить код (ошибка 1.0.0)."""
        from restore_gui import tasks
        b = self.backend
        need = (0, "INF preparing authentification\nINF 2FA code is required; run the command again and supply "
                   "a code using the '--auth-code' flag\n")
        saved = (b.stream, b.ask_main, b.session_ok, b.post, tasks.sap_ready, b.loggedIn, b.account)
        b.post, tasks.sap_ready = (lambda fn: fn()), (lambda: True)
        try:
            for answers, code, session, expected in (
                    ([need, (0, "INF success=true\n")], "123456", True, True),   # код введён — вход
                    ([need], None, True, False),                                  # код не введён — не вход
                    ([need, need], "000000", True, False),                        # код не подошёл
                    ([(0, "INF success=true\n")], None, False, False)):           # «успех» без сессии
                calls = iter(answers)
                b.stream = lambda cmd, quiet_json=False: next(calls)
                b.ask_main = lambda title, prompt: code
                b.session_ok = lambda ipatool: session
                b.loggedIn, b.account = False, ""
                b.task_login("ipatool", "someone@example.com", "pw")
                self.assertEqual(b.loggedIn, expected, f"{answers[0][1][-40:]!r}, код {code}, сессия {session}")
        finally:
            b.stream, b.ask_main, b.session_ok, b.post, tasks.sap_ready, b.loggedIn, b.account = saved

    def test_download_creates_missing_parent_folders(self):
        """У установленной версии папка — Документы\\Restore\\ipa; если нет даже Restore, скачивание не падает."""
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

    def test_theme_accent_and_settings_saved(self):
        import json
        b = self.backend
        ctx = self.engine.rootContext()
        try:
            b.themeMode = "dark"
            self.assertTrue(ctx.contextProperty("P")["dark"], "тёмная тема не дошла до QML")
            b.accentName = "ocean"
            self.assertEqual(ctx.contextProperty("P")["accent"], "#0b8fd4")
            b.themeMode = "light"
            self.assertFalse(ctx.contextProperty("P")["dark"])
            self.assertEqual(json.loads(storage.SETTINGS.read_text(encoding="utf-8"))["accentName"], "ocean")
            self.pump()
            self.assertEqual(MESSAGES, [], "\n".join(MESSAGES))
        finally:
            b.themeMode, b.accentName = "system", "emerald"

    def test_settings_window_sections(self):
        from PySide6.QtCore import QObject
        win = self.engine.rootObjects()[0]
        sw = next(o for o in win.findChildren(QObject) if o.metaObject().className().startswith("SettingsWindow"))
        sw.open()
        for i in range(5):
            sw.setProperty("section", i)
            self.pump()
        sw.close()
        self.pump()
        self.assertEqual(MESSAGES, [], "\n".join(MESSAGES))

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
