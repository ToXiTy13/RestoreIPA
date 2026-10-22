"""Тесты логики без интерфейса и без сети: python -m unittest discover tests"""
import json
import sys
import tempfile
import unittest
import zipfile
import plistlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import restore_apps as core  # noqa: E402
from restore_gui import apple, device, storage  # noqa: E402
from restore_gui.catalog import (BANKS, Catalog, categorize, family_key, parse_app_ref, plural,  # noqa: E402
                                 split_disguise)


class CatalogFunctions(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
