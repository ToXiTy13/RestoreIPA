"""Панель приложения: есть ли оно в истории Apple ID, копии под другими названиями, выбор версии.

Состояние открытой панели — словарь d (см. open_detail); на экран оно попадает через свойства Backend
(detailApp, detailChecks, clones, versions …). Проверки идут в фоновых потоках и обновляют панель через
self.ui(d, fn): если панель уже закрыли или открыли другое приложение (d["alive"] = False), обновление
пропускается.
"""
import re
import threading
import time

import restore_apps as core

from . import storage
from .apple import (SESSION_LOST, clip, explain_error, fetch_available, in_session_copies, list_versions_cmd,
                    ownership, parse_versions, run_quiet)
from .catalog import split_disguise
from .device import probe_device
from .theme import VERSIONS_PAGE

CHECKING = {"text": "проверяю…", "kind": "text"}


class DetailMixin:
    # ---------- открыть / закрыть ----------
    def open_detail(self, app):
        if self.detail is not None:
            self.detail["alive"] = False  # фоновые проверки прежнего приложения больше не нужны
        clones = self.catalog.family(app)
        # check: None — ещё проверяется, "owned" / "none" (нет в истории) / "error" (проверка не удалась)
        d = {"app": app, "owned": False, "alive": True, "check": None, "err": "", "answer": "",
             "vshow": VERSIONS_PAGE, "vkey": None, "meta_fail": set(), "meta_pending": set(),
             "clones": clones, "clone_err": set(), "clone_wait": False, "meta": {}}
        self.detail = d
        name = app["name"]
        self.detailApp = {"id": app["id"], "name": name, "letter": self.letter_of(name), "tint": self.tint_of(app["id"]),
                          "icon": self.icon_urls.get(app["id"], "")}
        self.detailChecks = {"acc": CHECKING, "phone": CHECKING, "store": CHECKING}
        self.clones.set_items(clones)
        self.paint_clones(d)
        self.versions.set_items([])
        self.versionMode, self.versionHead, self.moreText = "loading", "Версия", ""
        self.detailErr, self.detailAnswer = "", ""
        self.selectedVersion, self.actionsEnabled = "", False
        self.detailOpen = True
        threading.Thread(target=self.detail_task, args=(d,), daemon=True).start()

    def close_detail(self):
        if self.detail is not None:
            self.detail["alive"] = False
        self.detailOpen = False

    def ui(self, d, fn):
        """Выполнить fn в главном потоке, если панель всё ещё показывает это приложение."""
        self.post(lambda: fn() if d["alive"] else None)

    def set_lbl(self, d, key, text, kind="text"):
        """Строка проверки (Apple ID / iPhone / App Store). kind — цвет: text, ok, warn, muted."""
        def apply():
            checks = dict(self.detailChecks)
            checks[key] = {"text": text, "kind": kind}
            self.detailChecks = checks
        self.ui(d, apply)

    # ---------- копии под другими названиями ----------
    def clone_row(self, a):
        d = self.detail or {}
        main_name, alias = split_disguise(a["name"])
        st = self.owned_state.get(a["id"])
        if st is True:
            status, kind = "✓ есть у вас", "ok"
        elif st is False:
            status, kind = "нет в истории", "muted"
        elif a["id"] in d.get("clone_err", ()):
            status, kind = "не удалось проверить", "warn"
        elif d.get("clone_wait"):
            status, kind = "проверяю…", "muted"
        else:
            status, kind = "", "muted"
        return {"appId": a["id"], "title": f"«{alias}»" if alias else main_name,
                "sub": ("копия под видом другого приложения" if alias else "оригинальное приложение") + f" · ID {a['id']}",
                "letter": self.letter_of(alias or main_name), "tint": self.tint_of(a["id"]),
                "icon": self.icon_urls.get(a["id"], ""), "status": status, "statusKind": kind}

    def paint_clones(self, d):
        """Подписи «есть у вас / нет в истории» у копий и счётчик в заголовке блока."""
        clones = d.get("clones") or []
        self.clones.refresh_all()
        mine = sum(self.owned_state.get(a["id"]) is True for a in clones)
        self.cloneHead = (f"Это же приложение под другими названиями · {len(clones)}"
                          + (f" · у вас: {mine}" if mine else "")) if clones else ""
        self.cloneHeadOk = mine > 0

    def clone_check(self, d, ipatool, kc, workers=2):
        """Какие копии есть в истории Apple ID: та же проба list-versions, что и в панели (ничего не скачивает)."""
        todo = [a for a in d.get("clones") or [] if self.owned_state.get(a["id"]) is None]
        if not todo or not d["alive"]:
            return
        d["clone_wait"], d["clone_err"] = True, set()
        self.ui(d, lambda: self.paint_clones(d))
        errors = []

        def one(a, env):
            if not d["alive"]:
                return
            rc, out = run_quiet(list_versions_cmd(ipatool, kc, a["id"]), timeout=120, env=env)
            owned = ownership(rc, out)
            if owned is None:
                d["clone_err"].add(a["id"])
                errors.append((a, out))
            else:
                self.owned_state[a["id"]] = owned
            self.ui(d, lambda: self.paint_clones(d))

        in_session_copies(todo, one, workers, lock=self.dlock)
        d["clone_wait"] = False
        self.ui(d, lambda: self.paint_clones(d))
        self.post(self.refresh_list_keep)
        if not d["alive"]:
            return
        name = split_disguise(d["app"]["name"])[0]
        found = [a for a in d["clones"] if self.owned_state.get(a["id"]) is True]
        if found:
            self.log(f"{name}: в истории Apple ID есть копии — "
                     + ", ".join(f"«{split_disguise(a['name'])[1] or a['name']}» ({a['id']})" for a in found))
        if errors:
            a, o = errors[0]
            self.log(f"{name}: не удалось проверить {len(errors)} из {len(todo)} копий. Ответ ipatool для "
                     f"{a['name']} ({a['id']}):\n" + clip(o))

    # ---------- проверки ----------
    def detail_task(self, d):
        app = d["app"]
        ipatool = self.find_tool("ipatool", "", ask=False)
        if not ipatool:
            self.set_lbl(d, "acc", "ipatool не найден", "warn")
            d["check"], d["err"], d["answer"] = "error", "Не найден ipatool — без него Apple не спросить.", "—"
            self.ui(d, lambda: self.fill_versions(d, [], {}))
            return
        kc = core.keychain_args()
        if self.dlock.locked():  # ipatool занят скачиванием или входом — сессия у него
            self.set_lbl(d, "acc", "жду окончания текущей операции…", "muted")
        else:
            self.set_lbl(d, "acc", "спрашиваю Apple… обычно 5–30 секунд", "muted")
        t0 = time.time()
        rc, out = self.dq(list_versions_cmd(ipatool, kc, app["id"]), timeout=180)
        took = time.time() - t0
        versions = parse_versions(out)
        d["answer"] = clip(out, 900, 300, 550)
        owned = ownership(rc, out)
        d["owned"] = owned is True
        if owned:
            d["check"] = "owned"
            self.owned_state[app["id"]] = True
            self.set_lbl(d, "acc", "✓ Приложение есть в истории вашего Apple ID", "ok")
            self.log(f"{app['name']}: в истории Apple ID, версий у Apple: {len(versions)} (ответ за {took:.0f} с)")
            if not versions:
                self.log(f"{app['name']}: Apple не прислал список версий. Ответ ipatool:\n" + d["answer"])
        elif owned is False:
            d["check"] = "none"
            self.owned_state[app["id"]] = False
            self.set_lbl(d, "acc", "Не было у этого Apple ID — Apple не отдаст его, версий нет", "warn")
            self.log(f"{app['name']}: нет в истории Apple ID (ответ за {took:.0f} с)")
        elif rc == 124:
            d["check"], d["err"] = "error", "Apple не ответил за 3 минуты — проверьте связь («Проверить связь с Apple» в меню «⋯» вверху справа)."
            self.set_lbl(d, "acc", "Ошибка проверки: Apple не ответил за 3 минуты", "warn")
            self.log(f"{app['name']}: Apple не ответил за 3 минуты.")
        elif SESSION_LOST.search(out):
            d["check"], d["err"] = "error", "Вход не выполнен или истёк — войдите в Apple ID и повторите проверку."
            self.set_lbl(d, "acc", "Ошибка проверки: вход не выполнен или истёк", "warn")
            self.log(f"{app['name']}: list-versions — нет входа в Apple ID:\n" + d["answer"])
        else:
            hints = explain_error(out)
            d["check"] = "error"
            d["err"] = hints[0] if hints else "Apple вернул ошибку, по ней нельзя понять, есть ли приложение в истории."
            self.set_lbl(d, "acc", "Ошибка проверки — это не значит, что приложения нет в истории", "warn")
            self.log(f"{app['name']}: ошибка list-versions (код {rc}):\n" + d["answer"])
            self.hint(out)
        self.post(self.refresh_list_keep)

        # версии показываем сразу, остальное — параллельно
        d["vlist"] = versions
        cache = storage.load_meta().get(str(app["id"]), {})
        meta = {v: tuple(cache[v]) for v in versions if v in cache}
        d["ipatool"], d["kc"], d["meta_live"] = ipatool, kc, meta  # для «Показать ещё»
        self.ui(d, lambda: self.fill_versions(d, versions if d["owned"] else [], dict(meta)))
        threading.Thread(target=self.store_check, args=(d,), daemon=True).start()
        threading.Thread(target=self.phone_check, args=(d,), daemon=True).start()
        if d["check"] in ("owned", "none"):  # вход работает — можно спросить Apple и про копии
            threading.Thread(target=self.clone_check, args=(d, ipatool, kc), daemon=True).start()
        if not d["owned"] or not versions:
            return
        self.fetch_meta(d, ipatool, kc, versions, meta)

    def recheck_detail(self):
        """Повторить проверку в открытой панели (после ошибки)."""
        d = self.detail
        if d is None:
            return
        d["check"], d["err"], d["answer"] = None, "", ""
        d["meta_fail"], d["meta_pending"], d["vshow"], d["vkey"] = set(), set(), VERSIONS_PAGE, None
        self.versions.set_items([])
        self.versionMode, self.moreText, self.actionsEnabled = "loading", "", False
        self.detailChecks = {"acc": CHECKING, "phone": CHECKING, "store": CHECKING}
        threading.Thread(target=self.detail_task, args=(d,), daemon=True).start()

    def fetch_meta(self, d, ipatool, kc, versions, meta, workers=3):
        """Номера и даты показанных версий (get-version-metadata): 3 параллельных запроса, кэш на диске."""
        pending = d.setdefault("meta_pending", set())
        todo = [v for v in self.shown_versions(d, versions) if v not in meta and v not in pending]
        if not todo:
            return
        pending.update(todo)
        d.setdefault("meta_fail", set()).difference_update(todo)
        app_id = str(d["app"]["id"])
        lock = threading.Lock()
        fails = []  # (version, ответ ipatool) — чтобы причину было видно в журнале
        name = d["app"]["name"]

        def one(v, env):
            if not d["alive"]:
                return
            cmd = [ipatool, *kc, "get-version-metadata", "-i", app_id, "--external-version-id", v, "--format", "json"]
            r, o = run_quiet(cmd, timeout=120, env=env)
            if r != 0 and d["alive"]:
                r, o = self.dq(cmd, timeout=120)  # повтор через основную сессию: копия могла не подойти
            if r != 0:
                with lock:
                    d["meta_fail"].add(v)
                    fails.append((v, o.strip()))
                    if len(fails) == 1:
                        self.log(f"{name}: Apple не отдал номер версии {v} (код {r}). Ответ ipatool:\n" + clip(o))
                return
            m = re.search(r'"displayVersion"\s*:\s*"([^"]*)"', o)
            dt = re.search(r'"releaseDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', o)
            with lock:
                meta[v] = ((m.group(1) if m else "?"), (dt.group(1) if dt else ""))
                snap = dict(meta)
            self.ui(d, lambda: self.fill_versions(d, versions, snap))

        try:
            in_session_copies(todo, one, workers, lock=self.dlock)
        finally:
            pending.difference_update(todo)
        snap = dict(meta)
        self.ui(d, lambda: self.fill_versions(d, versions, snap))
        if fails:
            self.log(f"{name}: номера не получены для {len(fails)} из {len(todo)} версий. Такую версию всё равно "
                     "можно выбрать и скачать.")
            self.hint("\n".join(o for _, o in fails))
        storage.save_meta(app_id, snap)  # не meta: его может дополнять параллельный fetch_meta («Показать ещё»)

    def store_check(self, d):
        app = d["app"]
        country = self.store_country()
        av = fetch_available([app["id"]], country)
        if av is None:
            self.set_lbl(d, "store", "не удалось проверить (нет сети?)", "muted")
        elif app["id"] in av:
            self.set_lbl(d, "store", f"сейчас доступно в App Store ({country})", "text")
        else:
            self.set_lbl(d, "store", f"удалено из App Store ({country})", "warn")

    def phone_check(self, d):
        info = probe_device()
        if info and info.get("ios"):
            self.set_lbl(d, "phone", f"{info.get('model') or 'iPhone'} · iOS {info['ios']} — подключён", "ok")
        else:
            self.set_lbl(d, "phone", "не подключён (подключите кабелем и нажмите «Доверять»)", "muted")

    # ---------- версии ----------
    def shown_versions(self, d, versions):
        """Версии, которые видны в панели: новейшие порциями + скачанные через программу (их всегда видно)."""
        n = d.get("vshow", VERSIONS_PAGE)
        mine = set(storage.load_history().get(str(d["app"]["id"]), []))
        return versions[:n] + [v for v in versions[n:] if v in mine]

    def more_versions(self):
        d = self.detail
        if d is None:
            return
        d["vshow"] = d.get("vshow", VERSIONS_PAGE) + VERSIONS_PAGE
        self.fill_versions(d, d.get("vlist") or [], dict(d.get("meta_live") or {}))
        if d.get("ipatool"):
            threading.Thread(target=self.fetch_meta, daemon=True,
                             args=(d, d["ipatool"], d["kc"], d["vlist"], d["meta_live"])).start()

    def version_row(self, v):
        d = self.detail or {}
        if v == "":
            return {"value": "", "title": "Автоматически",
                    "sub": "новейшая версия, которая подходит для iOS вашего iPhone", "mine": False}
        meta = d.get("meta", {})
        if v in meta:
            title = "Версия " + meta[v][0] + (f" · {meta[v][1]}" if meta[v][1] else "")
        elif v in d.get("meta_fail", ()):
            title = "Версия — номер не получен"
        else:
            title = "Версия …"
        mine = v in d.get("mine", ())
        return {"value": v, "title": title, "sub": f"ID {v}" + ("  ·  скачано через программу" if mine else ""),
                "mine": mine}

    def fill_versions(self, d, versions, meta):
        d["meta"] = meta
        if d["check"] == "owned" and d["owned"]:
            shown = self.shown_versions(d, versions)
            if d.get("vkey") == tuple(shown):
                self.versions.refresh_all()  # тот же список: только подписи, прокрутка не сбрасывается
                return
        d["vkey"] = None
        self.versionHead, self.moreText = "Версия", ""
        if d["check"] == "error":
            self.detailErr, self.detailAnswer = d["err"], d["answer"]
            self.versions.set_items([])
            self.versionMode = "error"
            return
        if not d["owned"]:
            self.versions.set_items([])
            self.versionMode = "none"
            return
        d["mine"] = set(storage.load_history().get(str(d["app"]["id"]), []))
        shown = self.shown_versions(d, versions)
        total = len(versions)
        self.versionHead = (f"Версия · показано {len(shown)} из {total}" if total > len(shown) else
                            (f"Версия · {total}" if total else "Версия"))
        self.versions.set_items([""] + shown)
        rest = total - len(shown)
        self.moreText = f"Показать ещё {min(VERSIONS_PAGE, rest)} (осталось {rest})" if rest > 0 else ""
        d["vkey"] = tuple(shown)
        self.versionMode = "list"
        self.actionsEnabled = True

    def detail_action(self, install):
        d = self.detail
        if d is None:
            return
        if self.busy:
            self.show_notice("Подождите", "Сейчас выполняется другая операция.")
            return
        ipatool = self.need_ipatool()
        if not ipatool:
            return
        app, version = d["app"], self.selectedVersion or None
        if install:
            installer = self.find_installer()
            if not installer:
                return
            self.start("Скачивание и установка", self.task_restore, ipatool, installer, app["id"], app["name"],
                       self.purchase, version, d.get("vlist") or [])
        else:
            self.start("Скачивание", self.task_download, ipatool, app["id"], app["name"], self.purchase, version)
