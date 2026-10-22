"""Backend — всё, что видит окно (QML): состояние в свойствах, списки в моделях, действия в слотах.

Логика долгих операций — в TasksMixin (tasks.py) и DetailMixin (detail.py); они работают в рабочих потоках
и трогают окно только через post(fn) — fn выполнится в главном потоке.
"""
import datetime
import re
import secrets
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog, QMessageBox

import restore_apps as core

from . import storage, theme
from .catalog import Catalog, parse_app_ref, plural, split_disguise
from .detail import DetailMixin
from .icons import IconLoader, cached
from .models import RowsModel
from .tasks import TasksMixin

# страница CloudTips для «Поддержать разработчика»; пустая строка — кнопка не показывается.
# assets/cloudtips_qr.png — фирменный QR CloudTips на эту же ссылку; сменили ссылку — замените или удалите
# картинку (без неё QR рисуется сам).
SUPPORT_URL = "https://pay.cloudtips.ru/p/d4214684"
LOG_FLUSH_MS = 100  # журнал копится и уходит в окно одним куском: ipatool при скачивании пишет сотни строк

APP_KEYS = ("appId", "title", "sub", "letter", "tint", "icon", "status", "statusKind", "selected", "copies")


def qprop(type_, name):
    """Свойство для QML: (сигнал nameChanged, свойство name); значение хранится в self._name."""
    changed = Signal()

    def fget(self):
        return getattr(self, "_" + name)

    def fset(self, value):
        if getattr(self, "_" + name) != value:
            setattr(self, "_" + name, value)
            getattr(self, name + "Changed").emit()

    return changed, Property(type_, fget, fset, notify=changed)


class Backend(QObject, TasksMixin, DetailMixin):
    DEFAULTS = {
        "page": "home", "loggedIn": False, "account": "", "deviceState": "none", "deviceText": "iPhone не подключён",
        "busy": False, "status": "", "selectedCount": 0, "selectedText": "", "category": "Все", "logOpen": False,
        "country": "ru", "onlyRemoved": True, "purchase": False, "loginOpen": False, "loginNote": "",
        "askOpen": False, "askTitle": "", "askPrompt": "",
        "detailOpen": False, "detailApp": {}, "detailChecks": {}, "cloneHead": "", "cloneHeadOk": False,
        "versionHead": "Версия", "versionMode": "loading", "detailErr": "", "detailAnswer": "", "moreText": "",
        "actionsEnabled": False, "selectedVersion": "",
    }
    pageChanged, page = qprop(str, "page")
    loggedInChanged, loggedIn = qprop(bool, "loggedIn")
    accountChanged, account = qprop(str, "account")
    deviceStateChanged, deviceState = qprop(str, "deviceState")  # none / trust / ok
    deviceTextChanged, deviceText = qprop(str, "deviceText")
    busyChanged, busy = qprop(bool, "busy")
    statusChanged, status = qprop(str, "status")
    selectedCountChanged, selectedCount = qprop(int, "selectedCount")
    selectedTextChanged, selectedText = qprop(str, "selectedText")
    categoryChanged, category = qprop(str, "category")
    logOpenChanged, logOpen = qprop(bool, "logOpen")
    countryChanged, country = qprop(str, "country")
    onlyRemovedChanged, onlyRemoved = qprop(bool, "onlyRemoved")
    purchaseChanged, purchase = qprop(bool, "purchase")
    loginOpenChanged, loginOpen = qprop(bool, "loginOpen")
    loginNoteChanged, loginNote = qprop(str, "loginNote")
    askOpenChanged, askOpen = qprop(bool, "askOpen")
    askTitleChanged, askTitle = qprop(str, "askTitle")
    askPromptChanged, askPrompt = qprop(str, "askPrompt")
    detailOpenChanged, detailOpen = qprop(bool, "detailOpen")
    detailAppChanged, detailApp = qprop("QVariantMap", "detailApp")
    detailChecksChanged, detailChecks = qprop("QVariantMap", "detailChecks")
    cloneHeadChanged, cloneHead = qprop(str, "cloneHead")
    cloneHeadOkChanged, cloneHeadOk = qprop(bool, "cloneHeadOk")
    versionHeadChanged, versionHead = qprop(str, "versionHead")
    versionModeChanged, versionMode = qprop(str, "versionMode")  # loading / error / none / list
    detailErrChanged, detailErr = qprop(str, "detailErr")
    detailAnswerChanged, detailAnswer = qprop(str, "detailAnswer")
    moreTextChanged, moreText = qprop(str, "moreText")
    actionsEnabledChanged, actionsEnabled = qprop(bool, "actionsEnabled")
    selectedVersionChanged, selectedVersion = qprop(str, "selectedVersion")

    logAppended = Signal(str)
    noticeRequested = Signal(str, str)  # заголовок, текст
    _posted = Signal(object)

    def __init__(self, background=True):
        """background=False — без фоновых потоков (iPhone, иконки, уборка сессии): для тестов окна."""
        QObject.__init__(self)
        for k, v in self.DEFAULTS.items():
            setattr(self, "_" + k, v)
        core.SESSION_PASSPHRASE = secrets.token_urlsafe(32)  # только в памяти, на диск не пишется
        try:
            (Path.home() / ".restore_appstore" / "keychain.pass").unlink()  # пароль к сессии из ранних версий
        except OSError:
            pass
        storage.forget_email()  # email.txt прежних версий: email Apple ID на диске не храним
        self.catalog = Catalog(core.load_catalog())
        self.purchases = []
        self.avail = None  # ID покупок, которые сейчас есть в сторе; None — не проверялось
        self.owned_state = {}  # id -> True/False: есть ли приложение в истории Apple ID
        self.selected = {}  # id -> app, отмеченные для пакетной установки
        self.device = None
        self.after_login = None
        self.detail = None  # состояние открытой панели приложения (см. DetailMixin.open_detail)
        self.dlock = threading.Lock()  # проверки в панели идут по одной (общая папка сессии ipatool)
        self.stop_flag = False
        self.tool_paths = {}
        self._query = ""
        self._ask = None  # (событие, ответ) для вопроса из рабочего потока (код 2FA)
        self._log_lock, self._log_buf = threading.Lock(), []
        self.icon_urls = {a["id"]: QUrl.fromLocalFile(str(p)).toString()
                          for a in self.catalog.apps if (p := cached(a["id"]))}

        key = lambda a: a["id"]  # noqa: E731
        self._popular = RowsModel(APP_KEYS, self.app_row, key)
        self._apps = RowsModel(APP_KEYS, self.app_row, key)
        self._mine = RowsModel(APP_KEYS, self.app_row, key)
        self._clones = RowsModel(APP_KEYS, self.clone_row, key)
        self._versions = RowsModel(("value", "title", "sub", "mine"), self.version_row)
        self._ipa = RowsModel(("path", "title", "info", "letter", "tint", "icon"))

        self._posted.connect(self._run_posted)
        self._log_timer = QTimer(self, interval=LOG_FLUSH_MS, timeout=self._flush_log)
        self._log_timer.start()
        self._popular.set_items(self.catalog.popular())
        self.apply_filter()
        self.refresh_mine()
        if not self.catalog.apps:
            self.log(f"Каталог не найден: {core.CATALOG.name}. Можно вводить App ID вручную в поиске.")
        self.icons = IconLoader(lambda app_id, path: self.post(lambda: self.on_icon(app_id, path)))
        if background:
            self.start_background()

    def start_background(self):
        # сессия живёт только пока открыта программа: остатки прошлого запуска (например, после сбоя) стираем.
        # `ipatool auth revoke` может идти секунды — в фоне; кнопки на это время заблокированы (start).
        if (core.IPATOOL_HOME / ".ipatool").exists() or any(Path(tempfile.gettempdir()).glob("restore_scan_*")):
            self.start("Удаление сессии прошлого запуска", self.task_wipe_old)
        # слежение за iPhone импортирует pymobiledevice3 (секунду с лишним под GIL): сначала дорисуем окно
        QTimer.singleShot(1000, lambda: [threading.Thread(target=fn, daemon=True).start()
                                         for fn in (self._prepare_engine, self.watch_device)])
        QTimer.singleShot(1500, lambda: self.icons.start(a["id"] for a in self.catalog.apps))

    def task_wipe_old(self):
        if self.wipe_session():
            self.log("Найдена сессия Apple ID от прошлого запуска — удалена. Войдите заново.")

    # ---------- модели и постоянные свойства для QML ----------
    popular = Property(QObject, lambda self: self._popular, constant=True)
    apps = Property(QObject, lambda self: self._apps, constant=True)
    mine = Property(QObject, lambda self: self._mine, constant=True)
    clones = Property(QObject, lambda self: self._clones, constant=True)
    versions = Property(QObject, lambda self: self._versions, constant=True)
    ipaFiles = Property(QObject, lambda self: self._ipa, constant=True)
    categories = Property("QVariantList", lambda self: ["Все"] + self.catalog.categories, constant=True)
    supportUrl = Property(str, lambda self: SUPPORT_URL, constant=True)
    version = Property(str, lambda self: core.__version__, constant=True)
    palette = Property("QVariantMap", lambda self: theme.QML, constant=True)

    @Property(str, constant=True)
    def greeting(self):
        h = datetime.datetime.now().hour
        return "Доброй ночи" if h < 5 else "Доброе утро" if h < 12 else "Добрый день" if h < 18 else "Добрый вечер"

    @Property(str, constant=True)
    def qrUrl(self):
        """Фирменный QR CloudTips (assets/cloudtips_qr.png); без него — QR по ссылке через segno."""
        for p in (core.BUNDLE / "cloudtips_qr.png", core.HERE / "assets" / "cloudtips_qr.png"):
            if p.is_file():
                return QUrl.fromLocalFile(str(p)).toString()
        try:
            import segno
            p = core.DATA_DIR / "support_qr.png"
            core.DATA_DIR.mkdir(parents=True, exist_ok=True)
            segno.make(SUPPORT_URL, error="m").save(str(p), scale=8, border=4)
            return QUrl.fromLocalFile(str(p)).toString()
        except Exception:  # noqa: BLE001 — нет segno: в окне останется ссылка
            return ""

    # ---------- связь с рабочими потоками ----------
    def post(self, fn):
        """Выполнить fn в главном потоке (можно звать из любого)."""
        self._posted.emit(fn)

    def _run_posted(self, fn):
        try:
            fn()
        except Exception:  # noqa: BLE001 — ошибка в одном обновлении не должна ронять окно
            import traceback
            self.log("Внутренняя ошибка интерфейса:\n" + traceback.format_exc())

    def log(self, text):
        with self._log_lock:
            self._log_buf.append(text.rstrip("\n"))

    def _flush_log(self):
        with self._log_lock:
            lines, self._log_buf = self._log_buf, []
        if not lines:
            return
        self.logAppended.emit("\n".join(lines))
        for ln in reversed(lines):
            last = ln.strip().splitlines()[-1] if ln.strip() else ""
            if last and not last.startswith("$"):
                self.status = last[:150]
                break

    def set_status(self, text):
        self.post(lambda: setattr(self, "status", text))

    def set_busy(self, value):
        self.busy = value

    def open_log(self):
        self.logOpen = True

    def show_notice(self, title, text):
        self.noticeRequested.emit(title, text)

    def ask_yes_no(self, title, text):
        return QMessageBox.question(None, title, text) == QMessageBox.Yes

    def ask_file(self, title, folder, filters):
        path, _ = QFileDialog.getOpenFileName(None, title, str(folder), filters)
        return path or None

    def ask_main(self, title, prompt):
        """Вопрос из рабочего потока (код 2FA): окно в главном потоке, поток ждёт ответа."""
        ev, box = threading.Event(), {}

        def show():
            self._ask = (ev, box)
            self.askTitle, self.askPrompt, self.askOpen = title, prompt, True
        self.post(show)
        ev.wait()
        return box.get("v")

    @Slot(str, bool)
    def answerAsk(self, text, ok):
        self.askOpen = False
        if self._ask:
            ev, box = self._ask
            box["v"] = text.strip() if ok and text.strip() else None
            self._ask = None
            ev.set()

    # ---------- строки списков ----------
    @staticmethod
    def letter_of(name):
        return next((ch for ch in name if ch.isalnum()), "?").upper()

    @staticmethod
    def tint_of(app_id):
        return theme.AVATARS[int(app_id) % len(theme.AVATARS)]

    def app_row(self, a):
        app_id = a["id"]
        name, alias = split_disguise(a["name"])
        st = self.owned_state.get(app_id)
        return {
            "appId": app_id, "title": name,
            "sub": f"под видом «{alias}»" if alias else ("не из каталога — по App ID" if a.get("adhoc")
                                                          else a.get("cat", "")),
            "letter": self.letter_of(name), "tint": self.tint_of(app_id), "icon": self.icon_urls.get(app_id, ""),
            "status": "✓ было у вас" if st is True else "нет в истории" if st is False else "",
            "statusKind": "ok" if st is True else "none" if st is False else "",
            "selected": app_id in self.selected,
            "copies": self.catalog.copies_note(a).lstrip(" ·"),
        }

    def app_models(self):
        return self._popular, self._apps, self._mine

    def refresh_list_keep(self):
        """Обновить отметки «было у вас» во всех списках, не сбрасывая прокрутку."""
        for m in self.app_models():
            m.refresh_all()
        if self.detail is not None:
            self.paint_clones(self.detail)

    def on_icon(self, app_id, path):
        url = QUrl.fromLocalFile(str(path)).toString()
        self.icon_urls[app_id] = url
        for m in (*self.app_models(), self._clones):
            m.refresh_keys([app_id])
        if self.detailApp.get("id") == app_id:
            self.detailApp = dict(self.detailApp, icon=url)

    # ---------- страницы ----------
    @Slot(str)
    def showPage(self, name):
        self.page = name
        if name == "mine":
            self.refresh_mine()
        elif name == "ipa":
            self.refresh_ipa()

    @Slot(str)
    def setQuery(self, q):
        self._query = q
        self.apply_filter()

    @Slot(str)
    def setCategory(self, c):
        self.category = c
        self.apply_filter()

    def apply_filter(self):
        q = self._query.strip()
        items = self.catalog.search(q, self.purchases) if q else self.catalog.by_name
        if self._category != "Все" and not parse_app_ref(q):
            items = [a for a in items if a.get("cat") == self._category]
        self._apps.set_items(items)

    def my_removed(self):
        base = self.purchases
        if self._onlyRemoved and self.avail is not None:
            base = [a for a in base if a["id"] not in self.avail]
        return [dict(self.catalog.byid.get(a["id"], {}), **a) for a in base]

    def refresh_mine(self):
        self._mine.set_items(self.my_removed())

    @Slot(bool)
    def setOnlyRemoved(self, on):
        self.onlyRemoved = on
        self.refresh_mine()

    def refresh_ipa(self):
        files = sorted(core.OUT_DIR.glob("*.ipa"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if core.OUT_DIR.exists() else []
        rows = []
        for p in files[:200]:
            m = re.search(r"_(\d{6,12})(?:_v(\d+))?\.ipa$", p.name)
            app_id = int(m.group(1)) if m else 0
            st = p.stat()
            rows.append({"path": str(p), "title": p.stem.replace("_", " "), "letter": self.letter_of(p.stem),
                         "tint": self.tint_of(app_id), "icon": self.icon_urls.get(app_id, ""),
                         "info": f"{st.st_size / 1048576:.0f} МБ · "
                                 + datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y")})
        self._ipa.set_items(rows)

    def update_device(self):
        d = self.device
        if not d:
            self.deviceState, self.deviceText = "none", "iPhone не подключён"
        elif not d.get("ios"):
            self.deviceState, self.deviceText = "trust", "Нажмите «Доверять» на iPhone"
        else:
            self.deviceState, self.deviceText = "ok", f"{d.get('model') or 'iPhone'} · iOS {d['ios']}"

    def item_of(self, list_name, row):
        model = {"popular": self._popular, "apps": self._apps, "mine": self._mine, "clones": self._clones}[list_name]
        return model.items[row] if 0 <= row < len(model.items) else None

    # ---------- выбор нескольких ----------
    @Slot(str, int)
    def toggleSelected(self, list_name, row):
        app = self.item_of(list_name, row)
        if app is None:
            return
        if app["id"] in self.selected:
            del self.selected[app["id"]]
        else:
            self.selected[app["id"]] = app
        self._selection_changed([app["id"]])

    def clear_selection(self):
        ids = list(self.selected)
        self.selected.clear()
        self._selection_changed(ids)

    @Slot()
    def clearSelection(self):
        self.clear_selection()

    def _selection_changed(self, ids):
        for m in self.app_models():
            m.refresh_keys(ids)
        n = len(self.selected)
        self.selectedCount = n
        self.selectedText = f"Выбрано: {n} {plural(n, 'приложение', 'приложения', 'приложений')}" if n else ""

    @Slot()
    def installSelected(self):
        self.on_batch()

    # ---------- вход и выход ----------
    @Slot(str)
    def openLogin(self, note=""):
        if self._loggedIn:
            return
        self.loginNote = note or "Нужен Apple ID, на котором приложения были раньше"
        self.loginOpen = True

    @Slot(str, str)
    def login(self, email, password):
        self.on_login(email, password)

    def on_login_result(self, ok, who):
        self.loggedIn, self.account = ok, (who if ok else "")
        if ok:
            self.loginOpen = False
            if self.after_login == "scan":
                self.after_login = None
                self.showPage("mine")
                self.when_idle(self.on_scan)
        self.refresh_mine()

    def when_idle(self, fn):
        if self._busy:
            QTimer.singleShot(300, lambda: self.when_idle(fn))
        else:
            fn()

    @Slot()
    def logout(self):
        if self._busy:
            self.show_notice("Подождите", "Сначала дождитесь окончания текущей операции или нажмите «Остановить».")
            return
        self.wipe_session()
        storage.forget_email()
        self.owned_state.clear()
        self.refresh_list_keep()
        self.on_login_result(False, "")
        self.log("Вы вышли из Apple ID, сессия и email удалены с компьютера.")
        self.showPage("home")

    def on_purchases_result(self, acc, avail):
        self.purchases = [{"id": i, "name": n} for i, n in sorted(acc.items(), key=lambda kv: kv[1].casefold())]
        self.avail = avail
        for i in acc:
            self.owned_state[i] = True
        self.refresh_list_keep()
        self.showPage("mine")

    # ---------- кнопки ----------
    @Slot()
    def findMine(self):
        if not self._loggedIn:
            self.after_login = "scan"
            self.openLogin("Войдите, чтобы найти ваши удалённые приложения")
            return
        self.showPage("mine")
        self.on_scan()

    @Slot()
    def loadPurchases(self):
        if not self._loggedIn:
            self.openLogin("")
            return
        self.on_purchases()

    @Slot()
    def netCheck(self):
        self.on_netcheck()

    @Slot()
    def stop(self):
        self.on_stop()

    @Slot()
    def installFile(self):
        self.on_install_file()

    @Slot(str)
    def installIpa(self, path):
        self.install_path(path)

    @Slot()
    def openFolder(self):
        core.OUT_DIR.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.OUT_DIR))):
            self.log(f"Не удалось открыть папку: {core.OUT_DIR}")

    @Slot(str)
    def openUrl(self, url):
        if not QDesktopServices.openUrl(QUrl(url)):
            self.log(f"Не удалось открыть браузер. Ссылка: {url}")

    @Slot(str)
    def copyText(self, text):
        QGuiApplication.clipboard().setText(text)

    @Slot(result=str)
    def helpText(self):
        return (
            "1. iPhone и кабель. Разблокируйте телефон и нажмите «Доверять».\n\n"
            "2. Драйвер Apple на Windows: iTunes или «Устройства Apple» (Apple Devices) из Microsoft Store.\n\n"
            "3. Apple ID, под которым приложение когда-то скачивалось. Apple отдаёт только то, что есть в "
            "истории покупок этого аккаунта.\n\n"
            "4. Самый первый вход на компьютере может занять до 10–15 минут: ipatool скачивает служебные "
            "файлы Apple.\n\n"
            "5. Если вход или скачивание не работает — «Связь» внизу слева. Частые причины: DNS «для обхода "
            "блокировок», антивирус с проверкой HTTPS, записи в файле hosts.\n\n"
            f"Скачанные .ipa хранятся в папке {core.OUT_DIR} и повторно не скачиваются.\n\n"
            f"Версия {core.__version__}. Компоненты: " + self.tool_status())

    # ---------- панель приложения ----------
    @Slot(str, int)
    def openDetail(self, list_name, row):
        app = self.item_of(list_name, row)
        if app is not None:
            self.open_detail(app)

    @Slot()
    def closeDetail(self):
        self.close_detail()

    @Slot()
    def detailRecheck(self):
        self.recheck_detail()

    @Slot()
    def detailMore(self):
        self.more_versions()

    @Slot(bool)
    def detailAction(self, install):
        self.detail_action(install)

    # ---------- закрытие ----------
    @Slot()
    def shutdown(self):
        self.stop_flag = True
        self.icons.stop()
        if self.detail is not None:
            self.detail["alive"] = False
        self.wipe_session()
        storage.forget_email()
