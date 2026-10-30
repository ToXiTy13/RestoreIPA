"""Настройки (окно «Настройки»): тема и цвет акцента, папка загрузок, уведомления, проверка обновлений.
Хранятся в settings.json в папке программы (storage.SETTINGS); свойства для QML объявлены в Backend."""
import json
import re
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QFile, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog

import restore_apps as core

from . import storage, theme
from .catalog import plural
from .device import vtuple

REPO = "ToXiTy13/RestoreIPA"
REPO_URL = f"https://github.com/{REPO}"
NOTIFY_AFTER_S = 5  # мигать значком на панели задач, только если операция шла дольше
UPDATE_DELAY_MS = 3000  # автопроверка обновлений — чуть позже запуска, когда окно уже нарисовано
NOTES_LIMIT = 2000  # «Что нового» в окне обновления: столько символов из описания релиза, не больше
OWN_IPA = re.compile(r"_\d{6,12}(_v\d+)?\.ipa$")  # имя .ipa, скачанного программой (tasks.task_download)
# что из свойств Backend сохраняется между запусками, и проверка значения из файла
SAVED = {
    "themeMode": lambda v: v in ("system", "light", "dark"),
    "accentName": lambda v: v in theme.ACCENTS,
    "country": lambda v: isinstance(v, str) and len(v) <= 2,
    "onlyRemoved": lambda v: isinstance(v, bool),
    "purchase": lambda v: isinstance(v, bool),
    "deleteAfterInstall": lambda v: isinstance(v, bool),
    "notifyDone": lambda v: isinstance(v, bool),
    "autoUpdate": lambda v: isinstance(v, bool),
    "skipVersion": lambda v: isinstance(v, str) and len(v) <= 20,
}


def release_notes(body, limit=NOTES_LIMIT):
    """Описание релиза с GitHub -> «что нового» обычным текстом для окна обновления.

    Берём начало — до раздела «Что скачать» (дальше таблица файлов, VirusTotal и хеши) — и убираем разметку
    Markdown: картинки, ссылки (остаётся только текст), **жирный**, `код`, заголовки; пункты списка -> «•».
    """
    text = re.split(r"^#{1,6}\s*Что скачать", str(body or ""), maxsplit=1, flags=re.M | re.I)[0]
    text = text.replace("\r\n", "\n")
    text = re.sub(r"<[^>\n]+>", "", text)                       # HTML-теги
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)            # картинки
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)        # ссылки -> текст
    text = re.sub(r"(\*\*|__|`)", "", text)
    text = re.sub(r"^#{1,6}[ \t]*Что нового[ \t]*$", "", text, flags=re.M | re.I)  # он и так над текстом в окне
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)          # заголовки
    text = re.sub(r"^[ \t]*[-*+][ \t]+", "• ", text, flags=re.M)  # пункты списка
    text = re.sub(r"^[ \t]*(---+|\*\*\*+)[ \t]*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit("\n", 1)[0].rstrip() + "\n…"
    return text


def writable_dir(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".restore_write_test"
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


class PrefsMixin:
    def load_prefs(self):
        """Прочитать settings.json и применить; дальше каждое изменение сразу пишется на диск."""
        self.default_out = core.OUT_DIR
        saved = storage.load_settings()
        for key, ok in SAVED.items():
            if key in saved and ok(saved[key]):
                setattr(self, "_" + key, saved[key])
        folder = saved.get("ipaDir")
        if isinstance(folder, str) and folder and writable_dir(Path(folder)):
            core.OUT_DIR = Path(folder)
        self._ipaDir = str(core.OUT_DIR)
        for key in (*SAVED, "ipaDir"):
            getattr(self, key + "Changed").connect(self.save_prefs)
        for key in ("themeMode", "accentName"):
            getattr(self, key + "Changed").connect(self.apply_theme)
        hints = QGuiApplication.styleHints()
        hints.colorSchemeChanged.connect(lambda _scheme: self._themeMode == "system" and self.paletteChanged.emit())
        self.apply_theme()

    def save_prefs(self):
        data = {key: getattr(self, "_" + key) for key in SAVED}
        if Path(self._ipaDir) != self.default_out:
            data["ipaDir"] = self._ipaDir
        storage.save_settings(data)

    # ---------- тема ----------
    def is_dark(self):
        if self._themeMode != "system":
            return self._themeMode == "dark"
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def current_palette(self):
        return theme.palette(self.is_dark(), self._accentName)

    def apply_theme(self):
        # заголовок окна Windows (светлый/тёмный) Qt рисует по схеме приложения; Unknown — как в системе
        QGuiApplication.styleHints().setColorScheme(
            {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(self._themeMode, Qt.ColorScheme.Unknown))
        self.paletteChanged.emit()

    def accent_list(self):
        return [{"key": k, "title": t, "color": light["accent"], "grad1": light["grad1"], "grad2": light["grad2"]}
                for k, (t, light, _dark) in theme.ACCENTS.items()]

    # ---------- загрузки ----------
    def ipa_files(self):
        return sorted(core.OUT_DIR.glob("*.ipa"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if core.OUT_DIR.exists() else []

    @staticmethod
    def files_summary(files):
        size = sum(p.stat().st_size for p in files) / 1024 ** 3
        n = len(files)
        return f"{n} {plural(n, 'файл', 'файла', 'файлов')} · " + \
            (f"{size:.1f} ГБ".replace(".", ",") if size >= 0.1 else f"{size * 1024:.0f} МБ")

    def update_ipa_summary(self, files):
        self.ipaSummary = self.files_summary(files) if files else "Скачанных файлов нет"

    def choose_ipa_dir(self):
        with storage.registry_untouched():  # QFileDialog запоминает папку в реестре — см. registry_untouched
            path = QFileDialog.getExistingDirectory(None, "Папка для скачанных .ipa", str(core.OUT_DIR))
        if path:
            self.set_ipa_dir(Path(path))

    def set_ipa_dir(self, path):
        if not writable_dir(path):
            self.show_notice("Папка загрузок", f"В эту папку нельзя записывать файлы:\n{path}")
            return
        core.OUT_DIR = path
        self.ipaDir = str(path)
        self.refresh_ipa()
        self.log(f"Скачанные .ipa теперь сохраняются в {path}")

    def clear_ipa(self):
        # только файлы, скачанные программой (имя …_<App ID>[_v<версия>].ipa): другие .ipa в папке не трогаем
        files = [p for p in self.ipa_files() if OWN_IPA.search(p.name)]
        if not files:
            self.show_notice("Скачанные файлы", "В папке загрузок нет .ipa, скачанных программой.")
            return
        if not self.ask_yes_no("Скачанные файлы", f"Переместить в корзину .ipa, скачанные программой "
                                                  f"({self.files_summary(files)})?\n\n"
                                                  "Другие файлы в папке останутся. Приложения на iPhone это не "
                                                  "затронет; нужную версию можно будет скачать заново."):
            return
        left = [p for p in files if not QFile.moveToTrash(str(p))]
        self.refresh_ipa()
        self.log(f"В корзину перемещено файлов: {len(files) - len(left)}"
                 + (f"; не удалось: {len(left)} (заняты другой программой?)" if left else ""))

    def drop_installed(self, ipa):
        """После установки: удалить .ipa, если так выбрано в настройках (из рабочего потока)."""
        if not self._deleteAfterInstall:
            return
        try:
            Path(ipa).unlink()
            self.log(f"Файл удалён после установки (см. «Настройки» → «Загрузки»): {Path(ipa).name}")
        except OSError as e:
            self.log(f"Не удалось удалить {Path(ipa).name}: {e}")
        self.post(self.refresh_ipa)

    # ---------- обновления ----------
    @staticmethod
    def fetch_latest():
        """Последний релиз на GitHub: (версия, ссылка на релиз, «что нового») или None, если версия не новее.
        Из рабочего потока; без сети — исключение."""
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                     headers={"User-Agent": "Restore", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            rel = json.load(r)
        tag = str(rel.get("tag_name", "")).lstrip("vV")
        if not re.fullmatch(r"\d+(\.\d+){1,3}", tag) or vtuple(tag) <= vtuple(core.__version__):
            return None
        url = str(rel.get("html_url") or "")
        if not url.startswith(REPO_URL + "/releases/"):  # ссылка — только на релиз нашего репозитория
            url = REPO_URL + "/releases/latest"
        return tag, url, release_notes(rel.get("body"))

    def check_updates(self):
        """Кнопка «Проверить» в «Настройки» → «О программе»: результат — строкой там же."""
        self.updateText, self.updateUrl = "Проверяю…", ""

        def run():
            try:
                found = self.fetch_latest()
                text, url = (f"Доступна версия {found[0]}", found[1]) if found else \
                    (f"У вас последняя версия ({core.__version__})", "")
            except Exception:  # noqa: BLE001 — нет сети, лимит GitHub, неожиданный ответ
                text, url = "Не удалось проверить: нет связи с GitHub", ""
            self.post(lambda: (setattr(self, "updateText", text), setattr(self, "updateUrl", url)))

        threading.Thread(target=run, daemon=True).start()

    def auto_check_updates(self):
        """При запуске: окно «Доступна новая версия» — только если она есть и её не пропустили; иначе молча."""
        if not self._autoUpdate:
            return

        def run():
            try:
                found = self.fetch_latest()
            except Exception:  # noqa: BLE001
                self.log("Проверка обновлений: нет связи с GitHub.")
                return
            if found and found[0] != self._skipVersion:
                self.post(lambda: self.offer_update(*found))

        threading.Thread(target=run, daemon=True).start()

    def offer_update(self, tag, url, notes):
        self.updateText, self.updateUrl = f"Доступна версия {tag}", url
        self.updateVersion, self.updateNotes = tag, notes
        self.updateOpen = True  # QML откроет окно, когда закроются вход, код 2FA и другие окна

    def answer_update(self, action):
        """Кнопки окна обновления: download — открыть страницу релиза, skip — не напоминать об этой версии."""
        self.updateOpen = False
        if action == "download":
            self.openUrl(self._updateUrl)
        elif action == "skip":
            self.skipVersion = self._updateVersion
            self.log(f"Версия {self._updateVersion} пропущена: о ней программа больше не напомнит "
                     "(проверить вручную — «Настройки» → «О программе»).")
