"""Тесты логики без интерфейса и без сети: python -m unittest discover tests"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
import plistlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sandbox  # noqa: E402 — до restore_apps: тесты не трогают настоящие данные программы
assert sandbox.ROOT

import restore_apps as core  # noqa: E402
from restore_gui import apple, device, icons, storage  # noqa: E402
from restore_gui.catalog import (BANKS, Catalog, categorize, family_key, parse_app_ref, plural,  # noqa: E402
                                 split_disguise)


class CatalogFunctions(unittest.TestCase):
    def test_theme_palettes_have_same_keys(self):
        from restore_gui import theme
        self.assertEqual(set(theme.LIGHT), set(theme.DARK))
        keys = {frozenset(light) | frozenset(dark) for _t, light, dark in theme.ACCENTS.values()}
        self.assertEqual(len(keys), 1, "у акцентов разные наборы цветов")
        for dark in (False, True):
            for acc in theme.ACCENTS:
                self.assertTrue(all(isinstance(v, (str, bool)) for v in theme.palette(dark, acc).values()))

    def test_categorize(self):
        self.assertEqual(categorize("что угодно", "Инвестиции"), "Инвестиции и бизнес")  # категория из CSV
        self.assertEqual(categorize("Банки", "Банки"), "Банки")
        self.assertEqual(categorize("Яндекс Go", ""), "Яндекс")
        self.assertEqual(categorize("ВТБ Онлайн", ""), "Банки")
        self.assertEqual(categorize("Совсем другое", ""), "Прочее")

    def test_split_disguise_and_family(self):
        self.assertEqual(split_disguise("Альфа-Банк (Cashliner)"), ("Альфа-Банк", "Cashliner"))
        self.assertEqual(split_disguise("Альфа-Банк"), ("Альфа-Банк", None))
        self.assertEqual(family_key("Альфа-Банк (Cashliner)"), family_key("альфа-банк"))
        self.assertEqual(family_key("Ёлка  Банк"), "елка банк")

    def test_plural(self):
        forms = ("копия", "копии", "копий")
        expected = {1: "копия", 2: "копии", 4: "копии", 5: "копий", 11: "копий", 12: "копий", 14: "копий",
                    21: "копия", 22: "копии", 25: "копий", 111: "копий", 101: "копия"}
        for n, word in expected.items():
            self.assertEqual(plural(n, *forms), word, n)

    def test_parse_app_ref(self):
        self.assertEqual(parse_app_ref("492224193"), 492224193)
        self.assertEqual(parse_app_ref(" id492224193 "), 492224193)
        self.assertEqual(parse_app_ref("https://apps.apple.com/ru/app/sberbank/id492224193?l=en"), 492224193)
        self.assertIsNone(parse_app_ref("сбер"))
        self.assertIsNone(parse_app_ref("12345"))  # слишком короткий для App ID
        self.assertIsNone(parse_app_ref(""))


class CatalogClass(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog([
            {"id": 3, "name": "Альфа-Банк (Cashliner)", "cat": ""},
            {"id": 1, "name": "Альфа-Банк", "cat": "Банки"},
            {"id": 2, "name": "Альфа-Банк (Budget)", "cat": ""},
            {"id": 492224193, "name": "СберБанк Онлайн", "cat": "Банки"},
            {"id": 7, "name": "Сбор посылок", "cat": "Сервисы"},
        ])

    def test_family_original_first_then_copies_sorted(self):
        self.assertEqual([a["id"] for a in self.cat.family({"id": 3})], [1, 2])
        self.assertEqual([a["id"] for a in self.cat.family({"id": 1})], [2, 3])
        self.assertEqual(self.cat.family({"id": 999, "name": "Нет такого"}), [])
        self.assertEqual(self.cat.copies_note({"id": 1}), " · +2 копии")
        self.assertEqual(self.cat.copies_note({"id": 7}), "")

    def test_search(self):
        found = [a["id"] for a in self.cat.search("сб")]
        self.assertEqual(found[0], 492224193)  # популярное (BANKS) — первым
        self.assertIn(7, found)
        self.assertEqual(self.cat.search("492224193")[0]["id"], 492224193)
        adhoc = self.cat.search("id123456789")[0]
        self.assertTrue(adhoc["adhoc"])
        self.assertEqual(adhoc["id"], 123456789)
        # найденные покупки участвуют в поиске, но каталог в приоритете
        self.assertEqual([a["id"] for a in self.cat.search("мой", [{"id": 55, "name": "Мой банк"}])], [55])

    def test_lists(self):
        self.assertEqual([a["name"] for a in self.cat.by_name][:1], ["Альфа-Банк"])
        self.assertEqual(self.cat.categories, ["Банки", "Сервисы"])
        self.assertEqual([a["name"] for a in self.cat.popular()], ["Сбербанк"])  # подпись из BANKS


class RealCatalog(unittest.TestCase):
    def test_csv(self):
        apps = core.load_catalog()
        self.assertGreater(len(apps), 100)
        ids = [a["id"] for a in apps]
        self.assertEqual(len(ids), len(set(ids)), "App ID в каталоге повторяются")
        cat = Catalog(apps)
        missing = [t for t, i in BANKS if i not in cat.byid]
        self.assertEqual(missing, [], "плитки «Популярного» без приложения в каталоге")


class AppleAnswers(unittest.TestCase):
    def test_ownership(self):
        self.assertIs(apple.ownership(0, "{}"), True)
        self.assertIs(apple.ownership(1, "error: license is required"), False)
        self.assertIsNone(apple.ownership(1, "dial tcp: i/o timeout"))

    def test_parse_versions(self):
        out = 'log line\n{"externalVersionIdentifiers": [100, 300, 200], "bundleID": "x"}\n{"other": 1}\nbad {'
        self.assertEqual(apple.parse_versions(out), ["300", "200", "100"])
        self.assertEqual(apple.parse_versions("ничего"), [])

    def test_parse_purchases(self):
        out = "\n".join([
            "INF something",
            json.dumps({"apps": [{"id": 1, "name": "Один"}, {"trackId": "2", "trackName": "Два"}], "totalCount": 2}),
        ])
        self.assertEqual(apple.parse_purchases(out), ({1: "Один", 2: "Два"}, 2))

    def test_explain_error(self):
        self.assertIn("DNS", apple.explain_error("Get https://x: dial tcp: lookup x: no such host")[0])
        self.assertIn("истории покупок", apple.explain_error("license is required")[0])
        self.assertEqual(apple.explain_error("всё хорошо"), [])

    def test_clip(self):
        self.assertEqual(apple.clip("  коротко "), "коротко")
        self.assertEqual(apple.clip(""), "(пустой ответ)")
        long = "a" * 500 + "b" * 500
        self.assertEqual(apple.clip(long), "a" * 450 + "\n …\n" + "b" * 250)

    def test_list_versions_cmd(self):
        self.assertEqual(apple.list_versions_cmd("ipatool", ["--k", "v"], 42),
                         ["ipatool", "--k", "v", "list-versions", "-i", "42", "--format", "json"])

    def test_in_session_copies_runs_every_item_with_private_home(self):
        seen = []
        apple.in_session_copies(range(7), lambda i, env: seen.append((i, env["HOME"])), workers=3)
        self.assertEqual(sorted(i for i, _ in seen), list(range(7)))
        homes = {h for _, h in seen}
        self.assertLessEqual(len(homes), 3)
        self.assertFalse(any(Path(h).exists() for h in homes), "временные копии сессии не удалены")


class Device(unittest.TestCase):
    def test_vtuple(self):
        self.assertGreater(device.vtuple("17.10"), device.vtuple("17.9.1"))
        self.assertEqual(device.vtuple("нет"), (0,))

    def test_installer_cmd(self):
        b = ("builtin", ["app.exe", "--pmd"])
        self.assertEqual(device.installer_cmd(b, "install", "a.ipa"), ["app.exe", "--pmd", "apps", "install", "a.ipa"])
        self.assertEqual(device.installer_cmd(("pymobiledevice3", "pmd"), "list"), ["pmd", "apps", "list"])
        self.assertEqual(device.installer_cmd(("pymobiledevice3", "pmd"), "info"), ["pmd", "lockdown", "info"])
        self.assertEqual(device.installer_cmd(("ideviceinstaller", "idi"), "install", "a.ipa"), ["idi", "-i", "a.ipa"])
        self.assertEqual(device.installer_cmd(("ideviceinstaller", "idi"), "list"), ["idi", "-l"])

    def test_ipa_info(self):
        with tempfile.TemporaryDirectory() as d:
            ipa = Path(d) / "x.ipa"
            with zipfile.ZipFile(ipa, "w") as z:
                z.writestr("Payload/X.app/Info.plist", plistlib.dumps(
                    {"CFBundleIdentifier": "ru.test.x", "MinimumOSVersion": "15.0"}))
                z.writestr("Payload/X.app/Frameworks/F.framework/Info.plist", plistlib.dumps({"CFBundleIdentifier": "f"}))
            self.assertTrue(device.ipa_ok(ipa))
            info = device.ipa_info(ipa)
            self.assertEqual((info["CFBundleIdentifier"], info["MinimumOSVersion"]), ("ru.test.x", "15.0"))
            bad = Path(d) / "bad.ipa"
            bad.write_text("не zip", encoding="utf-8")
            self.assertFalse(device.ipa_ok(bad))
            self.assertEqual(device.ipa_info(bad), {})


class Storage(unittest.TestCase):
    def test_history_and_meta(self):
        with tempfile.TemporaryDirectory() as d:
            old = storage.HISTORY, storage.META_CACHE
            storage.HISTORY, storage.META_CACHE = Path(d) / "h.json", Path(d) / "m.json"
            try:
                self.assertEqual(storage.load_history(), {})
                storage.record_download(5, "100")
                storage.record_download(5, "100")
                storage.record_download(5, None)
                self.assertEqual(storage.load_history(), {"5": ["100"]})
                storage.save_meta(5, {"100": ("1.0", "2024-01-01")})
                self.assertEqual(storage.load_meta(), {"5": {"100": ["1.0", "2024-01-01"]}})
                storage.record_download(5, "200")
                storage.forget_download(5, "100")
                storage.forget_download(5, "999")  # такой нет — не ошибка
                self.assertEqual(storage.load_history(), {"5": ["200"]})
                storage.forget_download(5, "200")
                self.assertEqual(storage.load_history(), {})
            finally:
                storage.HISTORY, storage.META_CACHE = old

    def test_forget_email(self):
        with tempfile.TemporaryDirectory() as d:
            old, storage.EMAIL = storage.EMAIL, Path(d) / "email.txt"
            try:
                storage.EMAIL.write_text("someone@example.com", encoding="utf-8")
                storage.forget_email()
                self.assertFalse(storage.EMAIL.exists())
                storage.forget_email()  # файла нет — не ошибка
            finally:
                storage.EMAIL = old
        self.assertFalse(hasattr(storage, "save_email"), "email больше не должен записываться на диск")


# ---------- остановка, процессы, подсказки, следы программы в системе ----------
class ErrorHints(unittest.TestCase):
    def test_explain_error_is_not_too_broad(self):
        # 429 внутри App ID или размера — не «Apple ограничил попытки»
        self.assertEqual(apple.explain_error("failed to download app 1429500000 (14290 bytes)"), [])
        self.assertIn("ограничил", apple.explain_error("HTTP 429 Too Many Requests")[0])
        # блокировка аккаунта — без совета разблокировать iPhone
        hints = apple.explain_error("your account has been locked")
        self.assertEqual(len(hints), 1)
        self.assertIn("Apple ID", hints[0])
        self.assertIn("iPhone заблокирован", apple.explain_error("DeviceLocked")[0])
        self.assertIn("пароль", apple.explain_error("Your Apple ID or password was entered incorrectly.")[0])
        self.assertEqual(apple.explain_error("incorrect bundle version format"), [])
        self.assertEqual(apple.explain_error("reading passphrase: EOF"), [])  # не «нет связи»
        self.assertIn("DNS", apple.explain_error('Get "https://buy.itunes.apple.com/x": EOF')[0])

    def test_fatal_error(self):
        self.assertTrue(apple.fatal_error("dial tcp: i/o timeout"))
        self.assertTrue(apple.fatal_error("failed to get account"))
        self.assertTrue(apple.fatal_error("account is disabled"))
        self.assertFalse(apple.fatal_error("license is required"))
        self.assertFalse(apple.fatal_error(""))


SLEEPER = [sys.executable, "-c", "import time; time.sleep(30)"]


class Processes(unittest.TestCase):
    def test_run_quiet_timeout_kills_process(self):
        t0 = time.time()
        self.assertEqual(apple.run_quiet(SLEEPER, timeout=1), (124, "timeout"))
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(apple._PROCS, {}, "процесс остался в списке запущенных")

    def test_run_quiet_output(self):
        rc, out = apple.run_quiet([sys.executable, "-c", "print('\\x1b[31mok\\x1b[0m')"])
        self.assertEqual((rc, out.strip()), (0, "ok"))

    def test_kill_procs_by_tag(self):
        task, other = apple.popen(SLEEPER, tag="task"), apple.popen(SLEEPER)
        try:
            apple.kill_procs("task")
            task.wait(timeout=10)
            self.assertIsNone(other.poll(), "«Остановить» завершил не только основную операцию")
            apple.kill_procs()
            other.wait(timeout=10)
        finally:
            for p in (task, other):
                apple.forget(p)
                if p.poll() is None:
                    p.kill()

    def test_close_procs_blocks_new_processes(self):
        """После закрытия окна новые процессы не запускаются — кроме уборки сессии (tag="wipe")."""
        p = apple.popen(SLEEPER)
        try:
            apple.close_procs()
            p.wait(timeout=10)
            self.assertRaises(apple.ProcsClosed, apple.popen, SLEEPER)
            self.assertEqual(apple.run_quiet(SLEEPER)[0], 1)
            rc, out = apple.run_quiet([sys.executable, "-c", "print('wipe')"], tag="wipe")
            self.assertEqual((rc, out.strip()), (0, "wipe"))
        finally:
            apple._CLOSED = False
            apple.forget(p)

    def test_clear_stale_locks(self):
        with tempfile.TemporaryDirectory() as d:
            old, core.IPATOOL_HOME = core.IPATOOL_HOME, Path(d)
            try:
                session = Path(d) / ".ipatool"
                session.mkdir()
                (session / "cookies.lock").write_text("", encoding="utf-8")
                (session / "cookies").write_text("{}", encoding="utf-8")
                apple.clear_stale_locks()
                self.assertEqual([p.name for p in session.iterdir()], ["cookies"])
                apple.clear_stale_locks()  # папки или lock-файлов нет — не ошибка
            finally:
                core.IPATOOL_HOME = old


@unittest.skipUnless(sys.platform.startswith("win"), "поиск программ в текущей папке есть только на Windows")
class ToolLookup(unittest.TestCase):
    def test_planted_exe_in_current_folder_is_not_used(self):
        """ipatool.exe в текущей папке не должен находиться раньше PATH: он получил бы пароль Apple ID."""
        self.assertEqual(os.environ.get("NoDefaultCurrentDirectoryInExePath"), "1")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ipatool_planted_test.exe").write_bytes(b"")
            old = os.getcwd()
            os.chdir(d)
            try:
                self.assertIsNone(shutil.which("ipatool_planted_test"))
            finally:
                os.chdir(old)


@unittest.skipUnless(sys.platform == "darwin", "только на macOS")
class MacOnly(unittest.TestCase):
    def test_ipatool_home_sees_user_keychain(self):
        """С подменённым HOME macOS ищет «Связку ключей» в HOME/Library/Keychains — там ссылка на настоящую;
        удаление копии сессии удаляет ссылку, а не связку ключей (sandbox: «настоящая» — во временной папке)."""
        core.USER_KEYCHAINS.mkdir(parents=True, exist_ok=True)
        (core.USER_KEYCHAINS / "login.keychain-db").write_bytes(b"")
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "w0"
            env = core.ipatool_env(home)
            link = home / "Library" / "Keychains"
            self.assertEqual(env["HOME"], str(home))
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), core.USER_KEYCHAINS.resolve())
            core.ipatool_env(home)  # повторный вызов ничего не ломает
            self.assertTrue(link.is_symlink())
            shutil.rmtree(home)
        self.assertTrue((core.USER_KEYCHAINS / "login.keychain-db").is_file())

    def test_https_has_ca_bundle(self):
        """Python на macOS не видит системные сертификаты: без SSL_CERT_FILE падали бы иконки и проверки."""
        import ssl
        path = Path(os.environ.get("SSL_CERT_FILE", ""))
        self.assertTrue(path.is_file(), f"нет набора сертификатов: {path}")
        self.assertGreater(ssl.create_default_context().cert_store_stats()["x509_ca"], 0)


def lookup_answer(body):
    """Подмена urlopen: ответ iTunes Lookup с телом body."""
    return lambda *_a, **_k: contextlib.nullcontext(io.BytesIO(body))


class Icons(unittest.TestCase):
    def test_offline_does_not_hide_icons_for_a_week(self):
        with tempfile.TemporaryDirectory() as d:
            old = icons.ICONS, icons.MISSING
            icons.ICONS, icons.MISSING = Path(d), Path(d) / "missing.json"
            loader = icons.IconLoader(lambda *_: None)
            try:
                with mock.patch.object(icons.urllib.request, "urlopen", side_effect=OSError("no network")):
                    loader._run([111111111, 222222222])
                self.assertEqual(json.loads(icons.MISSING.read_text(encoding="utf-8")), {})
                # Apple ответил везде и иконки не дал — тогда «нет иконки» запоминается
                with mock.patch.object(icons.urllib.request, "urlopen", side_effect=lookup_answer(b'{"results": []}')):
                    loader._run([111111111])
                self.assertIn("111111111", json.loads(icons.MISSING.read_text(encoding="utf-8")))
            finally:
                loader.stop()
                icons.ICONS, icons.MISSING = old


class IconSource(unittest.TestCase):
    def test_icon_only_from_apple_and_small(self):
        """Адрес картинки приходит из ответа Apple: качаем только с *.mzstatic.com по https и только картинку."""
        with tempfile.TemporaryDirectory() as d:
            old = icons.ICONS
            icons.ICONS = Path(d)
            got = []
            loader = icons.IconLoader(lambda app_id, path: got.append(app_id))
            png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
            try:
                with mock.patch.object(icons.urllib.request, "urlopen", side_effect=lookup_answer(png)) as op:
                    for url in ("http://is1-ssl.mzstatic.com/a.jpg", "https://evil.example.com/a.jpg",
                                "https://is1-ssl.mzstatic.com.evil.com/a.jpg", "file:///C:/a.png"):
                        loader._download(1, url)
                    self.assertFalse(op.called, "иконка скачивалась не с сервера Apple")
                    loader._download(2, "https://is1-ssl.mzstatic.com/image/thumb/x/128x128bb.jpg")
                with mock.patch.object(icons.urllib.request, "urlopen", side_effect=lookup_answer(b"<html>")):
                    loader._download(3, "https://is1-ssl.mzstatic.com/image/thumb/y/128x128bb.jpg")
                self.assertEqual(got, [2])
                self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["2.png"])
            finally:
                loader.stop()
                icons.ICONS = old


class ReleaseNotes(unittest.TestCase):
    def test_notes_plain_text_until_downloads(self):
        """«Что нового» в окне обновления: начало описания релиза без разметки; файлы, хеши и ссылки — нет."""
        from restore_gui.prefs import release_notes
        body = ("Новый дизайн и **тёмная** тема.\r\n\r\n![Главный экран](https://example.com/home.png)\r\n\r\n"
                "## Исправления\r\n\r\n- Кнопка `Остановить` работает\r\n* Подробнее — в [README](https://evil.example.com)"
                "\r\n<img src=x onerror=alert(1)>\r\n\r\n\r\n\r\n## Что скачать\r\n\r\n| Файл | Что это |\r\n"
                "```\r\n57feb7  RestoreSetup.exe\r\n```")
        self.assertEqual(release_notes(body), "Новый дизайн и тёмная тема.\n\nИсправления\n\n"
                                              "• Кнопка Остановить работает\n• Подробнее — в README")
        self.assertEqual(release_notes(None), "")
        self.assertEqual(release_notes("Коротко.\n\n## Что нового\n\n- пункт"), "Коротко.\n\n• пункт")
        long = release_notes("\n".join(f"- пункт {i}" for i in range(1000)), limit=100)
        self.assertLessEqual(len(long), 102)
        self.assertTrue(long.endswith("\n…"))


class ConsoleLogin(unittest.TestCase):
    def run_login(self, answers, typed_code):
        """cmd_login с ответами ipatool answers: (код возврата, спросили ли код 2FA)."""
        calls = iter(answers)
        args = mock.Mock(email="someone@example.com", code=None)
        with mock.patch.object(core, "need", return_value="ipatool"), \
                mock.patch.object(core, "keychain_args", return_value=[]), \
                mock.patch.object(core, "run", side_effect=lambda cmd: next(calls)), \
                mock.patch.object(core.getpass, "getpass", return_value="pw"), \
                mock.patch("builtins.input", return_value=typed_code) as ask, \
                mock.patch("builtins.print"):
            return core.cmd_login(args), ask.called

    def test_asks_2fa_even_when_ipatool_exits_0(self):
        """ipatool 2.7: «2FA code is required…» с кодом 0 — консольная версия считала это входом."""
        need = mock.Mock(returncode=0, stdout="INF 2FA code is required; supply it using '--auth-code'\n", stderr="")
        ok = mock.Mock(returncode=0, stdout="INF success=true\n", stderr="")
        self.assertEqual(self.run_login([need, ok], "123456"), (0, True))
        self.assertEqual(self.run_login([need], ""), (1, True))  # код не ввели — не вход
        self.assertEqual(self.run_login([ok], ""), (0, False))


class Footprint(unittest.TestCase):
    """Служебное — только в %LOCALAPPDATA%\\Restore (и в папке «ipa» рядом с портативным exe)."""

    def test_writable_probe_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(core._writable(Path(d)))
            self.assertEqual(os.listdir(d), [])
            self.assertFalse(core._writable(Path(d) / "нет"))
            self.assertFalse((Path(d) / "нет").exists(), "проба создала папку")

    def test_ipatool_cache_and_scan_copies_inside_data_dir(self):
        env = core.ipatool_env()
        self.assertEqual((env["LOCALAPPDATA"], env["HOME"]), (str(core.DATA_DIR), str(core.IPATOOL_HOME)))
        self.assertTrue(core.IPATOOL_CACHE.is_relative_to(core.DATA_DIR))
        seen = []
        apple.in_session_copies([1, 2], lambda i, env: seen.append(env), workers=2)
        for env in seen:
            self.assertEqual(env["LOCALAPPDATA"], str(core.DATA_DIR))
            self.assertTrue(Path(env["HOME"]).is_relative_to(apple.SCAN_ROOT), env["HOME"])
        self.assertEqual(apple.scan_copies(), [])

    @unittest.skipUnless(sys.platform.startswith("win"), "кэш ipatool в %LOCALAPPDATA% — только на Windows")
    def test_adopt_old_cache(self):
        old = Path(os.environ["LOCALAPPDATA"]) / "ipatool"
        (old / "sap" / "apple-assets-v2").mkdir(parents=True)
        (old / "sap" / "apple-assets-v2" / "a.bin").write_bytes(b"1")
        (old / "unicorn").mkdir()
        try:
            self.assertTrue(apple.adopt_old_cache())
            self.assertTrue(apple.sap_ready())
            self.assertTrue((core.IPATOOL_CACHE / "unicorn").is_dir())
            self.assertFalse(old.exists(), "пустая старая папка осталась")
            (old / "sap").mkdir(parents=True)  # уже перенесено: второй раз не затирает
            (old / "other").mkdir()
            self.assertFalse(apple.adopt_old_cache())
            self.assertEqual(sorted(p.name for p in old.iterdir()), ["other", "sap"], "тронуто чужое")
        finally:
            shutil.rmtree(old, ignore_errors=True)
            shutil.rmtree(core.IPATOOL_CACHE, ignore_errors=True)

    def test_pymobiledevice3_folder_inside_data_dir(self):
        import pymobiledevice3.common as pmd_common
        saved = pmd_common._HOMEFOLDER
        try:
            device.own_pmd_folder()
            self.assertEqual(pmd_common.get_home_folder(), core.DATA_DIR / "pymobiledevice3")
            self.assertFalse((Path.home() / ".pymobiledevice3").exists())
        finally:
            pmd_common._HOMEFOLDER = saved

    def test_remove_leftovers(self):
        pmd = Path.home() / ".pymobiledevice3"
        pmd.mkdir(exist_ok=True)
        storage.remove_leftovers()
        self.assertFalse(pmd.exists())
        pmd.mkdir()  # с записями сопряжения pymobiledevice3, которым пользуются отдельно, — не трогаем
        (pmd / "00008030-0011.plist").write_bytes(b"")
        try:
            storage.remove_leftovers()
            self.assertTrue((pmd / "00008030-0011.plist").exists(), "удалена непустая папка")
        finally:
            shutil.rmtree(pmd, ignore_errors=True)

    @unittest.skipUnless(sys.platform.startswith("win"), "занятый файл нельзя удалить только на Windows")
    def test_remove_stale_unpacked(self):
        with tempfile.TemporaryDirectory() as d:
            def unpacked(name, ours=True, age=3600):
                p = Path(d) / name
                (p / "restore_gui" / "qml").mkdir(parents=True)
                if ours:
                    (p / core._CSV).write_text("", encoding="utf-8")
                    (p / "restore_gui" / "qml" / "Main.qml").write_text("", encoding="utf-8")
                for dll in ("python3.dll", "python312.dll"):
                    (p / dll).write_bytes(b"")
                os.utime(p, (time.time() - age,) * 2)
                return p

            me, stale, fresh = unpacked("_MEI1"), unpacked("_MEI2"), unpacked("_MEI3", age=0)
            foreign, busy = unpacked("_MEI4", ours=False), unpacked("_MEI5")
            with open(busy / "python312.dll", "rb"), mock.patch.object(core, "FROZEN", True), \
                    mock.patch.object(sys, "_MEIPASS", str(me), create=True):
                storage.remove_stale_unpacked()
            self.assertFalse(stale.exists())
            for p in (me, fresh, foreign, busy):
                self.assertTrue((p / "python3.dll").exists(), p.name)

    @unittest.skipUnless(sys.platform.startswith("win"), "реестр — только на Windows")
    def test_registry_untouched(self):
        import uuid
        import winreg
        root = rf"Software\RestoreTests-{uuid.uuid4().hex}"
        hk = winreg.HKEY_CURRENT_USER

        def delete_tree(path):
            with contextlib.suppress(OSError), winreg.OpenKey(hk, path) as key:
                for sub in [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]:
                    delete_tree(path + "\\" + sub)
            with contextlib.suppress(OSError):
                winreg.DeleteKey(hk, path)

        try:
            with storage.registry_untouched(root):  # раздела не было — не остаётся ничего
                with winreg.CreateKey(hk, root + r"\OrganizationDefaults\FileDialog") as key:
                    winreg.SetValueEx(key, "lastVisited", 0, winreg.REG_SZ, "file:///C:/x")
            self.assertRaises(OSError, winreg.OpenKey, hk, root)

            with winreg.CreateKey(hk, root + r"\FileDialog") as key:  # раздел был — значения как до блока
                winreg.SetValueEx(key, "lastVisited", 0, winreg.REG_SZ, "до")
                winreg.SetValueEx(key, "history", 0, winreg.REG_MULTI_SZ, ["a", "b"])
            with storage.registry_untouched(root):
                with winreg.CreateKey(hk, root + r"\FileDialog") as key:
                    winreg.SetValueEx(key, "lastVisited", 0, winreg.REG_SZ, "после")
                    winreg.SetValueEx(key, "viewMode", 0, winreg.REG_SZ, "Detail")
                    winreg.DeleteValue(key, "history")
                winreg.CreateKey(hk, root + r"\Qt\customColors").Close()
            with winreg.OpenKey(hk, root + r"\FileDialog") as key:
                values = {winreg.EnumValue(key, i)[0]: winreg.EnumValue(key, i)[1]
                          for i in range(winreg.QueryInfoKey(key)[1])}
            self.assertEqual(values, {"lastVisited": "до", "history": ["a", "b"]})
            self.assertRaises(OSError, winreg.OpenKey, hk, root + r"\Qt")
        finally:
            delete_tree(root)


if __name__ == "__main__":
    unittest.main()
