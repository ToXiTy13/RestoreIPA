"""Долгие операции: выполняются в рабочем потоке (start). С окном общаются только через self.log, self.post(fn)
(выполнить fn в главном потоке) и self.set_status; вопросы человеку — ask_yes_no / ask_file / show_notice
(их даёт Backend)."""
import ipaddress
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import restore_apps as core

from . import storage
from .apple import (ANSI, APPLE_HOSTS, NO_WINDOW, SESSION_LOST, bundled, clip, explain_error, fetch_available,
                    in_session_copies, list_versions_cmd, ownership, parse_purchases, parse_versions, run_quiet,
                    sap_ready, seed_unicorn)
from .device import installer_cmd, ipa_info, ipa_ok, probe_device, vtuple

SCAN_WORKERS = 4  # параллельных проверок владения
IPATOOL_MISSING = "ipatool не найден в PATH (https://github.com/majd/ipatool/releases)."


class TasksMixin:
    # ---------- обработчики кнопок (главный поток) ----------
    def need_ipatool(self):
        return self.find_tool("ipatool", IPATOOL_MISSING)

    def store_country(self):
        """Код страны App Store из настроек (по умолчанию ru)."""
        return (self._country.strip().lower() or "ru")[:2]

    def on_login(self, email, password):
        email = email.strip()
        if not email or not password:
            self.show_notice("Вход", "Введите Apple ID и пароль.")
            return
        ipatool = self.need_ipatool()
        if ipatool:
            self.start("Вход в Apple ID", self.task_login, ipatool, email, password)

    def on_purchases(self):
        ipatool = self.need_ipatool()
        if ipatool:
            self.start("Загрузка списка покупок", self.task_purchases, ipatool, self.store_country())

    def on_scan(self):
        ipatool = self.need_ipatool()
        if ipatool:
            self.start("Поиск среди удалённых приложений", self.task_scan, ipatool, self.store_country())

    def on_netcheck(self):
        self.open_log()
        self.start("Проверка связи с Apple", self.task_netcheck)

    def on_stop(self):
        self.stop_flag = True

    def on_install_file(self):
        ipa = self.ask_file("Выберите IPA", core.OUT_DIR if core.OUT_DIR.exists() else core.HERE,
                            "IPA (*.ipa);;Все файлы (*.*)")
        if ipa:
            self.install_path(ipa)

    def install_path(self, ipa):
        installer = self.find_installer()
        if installer:
            self.start("Установка", self.task_install, installer, Path(ipa))

    def on_batch(self):
        if not self.selected:
            return
        ipatool = self.need_ipatool()
        installer = self.find_installer() if ipatool else None
        if ipatool and installer:
            apps = list(self.selected.values())
            self.start(f"Пакетная установка ({len(apps)})", self.task_batch, ipatool, installer, apps)

    def start(self, label, fn, *args):
        if self.busy:
            return

        self.set_busy(True)  # сразу: вторая кнопка до старта потока уже не сработает
        self.set_status(label + "…")

        def runner():
            try:
                fn(*args)
            except Exception as e:  # noqa: BLE001
                self.log(f"Ошибка: {e}")
            finally:
                self.post(lambda: self.set_busy(False))
                self.set_status("Готово")

        threading.Thread(target=runner, daemon=True).start()

    # ---------- инструменты ----------
    def find_tool(self, name, hint, ask=True):
        path = self.tool_paths.get(name) or bundled(name) or shutil.which(name)
        if path and Path(path).exists():
            return path
        if not ask:
            return None
        if self.ask_yes_no(f"Не найден {name}", f"{hint}\n\nУказать путь к {name} вручную?"):
            path = self.ask_file(f"Укажите {name}", core.HERE, "Программы (*.exe);;Все файлы (*.*)")
            if path:
                self.tool_paths[name] = path
                return path
        return None

    def find_installer(self, ask=True):
        if core.FROZEN:  # pymobiledevice3 встроен в этот же exe (режим --pmd)
            return "builtin", [sys.executable, "--pmd"]
        for name in ("pymobiledevice3", "ideviceinstaller"):
            p = self.find_tool(name, "", ask=False)
            if p:
                return name, p
        if ask:
            self.show_notice("Нет установщика",
                             "Нужен pymobiledevice3 (pip install pymobiledevice3) или ideviceinstaller.")
        return None

    def tool_status(self):
        """Строка «Компоненты» для справки: что из инструментов найдено."""
        def mark(n):
            return "✓" if self.find_tool(n, "", ask=False) else "✗"

        text = f"ipatool {mark('ipatool')}{' (встроен)' if bundled('ipatool') else ''}   "
        if core.FROZEN:
            return text + "установщик ✓ (встроен)"
        return text + f"pymobiledevice3 {mark('pymobiledevice3')}   ideviceinstaller {mark('ideviceinstaller')}"

    def stream(self, cmd, quiet_json=False):
        self.log("$ " + core.masked(cmd))
        p = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
            env=core.ipatool_env() if core.is_ipatool(cmd) else None,
        )
        lines = []
        for line in p.stdout:
            line = ANSI.sub("", line)
            lines.append(line)
            if quiet_json and line.lstrip().startswith("{") and '"apps"' in line:
                continue  # длинный JSON со списком не засоряет журнал; ошибки при этом остаются видны
            self.log(line)
        p.wait()
        return p.returncode, "".join(lines)

    def dq(self, cmd, timeout=90):
        """run_quiet через основную сессию ipatool — по одной команде за раз (общая папка сессии)."""
        with self.dlock:
            return run_quiet(cmd, timeout=timeout)

    def hint(self, text):
        hints = explain_error(text)
        for h in hints:
            self.log("ⓘ " + h)
        if hints:
            self.post(self.open_log)

    # ---------- задачи (выполняются в потоке) ----------
    def task_login(self, ipatool, email, password):
        code = None
        if not sap_ready():
            self.log("Первый вход на этом компьютере: ipatool скачивает служебные файлы Apple для подписи "
                     "запросов. Это может занять от минуты до 10–15 минут при медленной сети — не закрывайте "
                     "программу. В следующий раз будет быстро.")
        while True:
            cmd = [ipatool, *core.keychain_args(), "auth", "login", "--email", email, "--password", password]
            if code:
                cmd += ["--auth-code", code]
            rc, out = self.stream(cmd)
            if rc == 0:
                self.log("Вход выполнен.")
                self.post(lambda: self.on_login_result(True, email))  # ни email, ни пароль на диск не пишутся
                return
            if not code and re.search(r"2fa|auth.?code|verification|two.?factor", out, re.I):
                code = self.ask_main("Двухфакторная аутентификация", "Введите код с вашего устройства Apple:")
                if code:
                    continue
            self.log("Вход не удался.")
            self.hint(out)
            self.post(lambda: self.on_login_result(False, ""))
            return

    def _prepare_engine(self):
        if seed_unicorn():
            self.log("Эмулятор для входа (Unicorn 2.1.4) подготовлен из встроенной копии — GitHub не нужен.")

    # ---------- сессия ----------
    def wipe_session(self, revoke=True):
        """Завершить сессию Apple ID: `ipatool auth revoke` и удалить папку сессии ~/.ipatool.

        Возвращает True, если сессия была. Пароль и email Apple ID программа на диске не хранит.
        """
        folder = core.IPATOOL_HOME / ".ipatool"
        existed = folder.exists() and any(folder.iterdir())
        ipatool = self.find_tool("ipatool", "", ask=False)
        if revoke and existed and ipatool:
            run_quiet([ipatool, *core.keychain_args(), "auth", "revoke"], timeout=15)
        shutil.rmtree(folder, ignore_errors=True)
        # копии сессии для параллельных запросов (apple.in_session_copies), в т.ч. оставшиеся после сбоя
        for d in Path(tempfile.gettempdir()).glob("restore_scan_*"):
            existed = existed or (d / "w0" / ".ipatool").exists()
            shutil.rmtree(d, ignore_errors=True)
        return existed

    def task_purchases(self, ipatool, country="ru"):
        acc, total, first_json, failed = {}, None, "", False
        # ipatool отдаёт покупки страницами (новые первыми), максимум 100 за раз — читаем все
        for page in range(1, 101):
            cmd = [ipatool, *core.keychain_args(), "list-purchases", "--format", "json",
                   "--max-results", "100", "--page", str(page)]
            rc, out = self.stream(cmd, quiet_json=True)
            if rc != 0:
                self.log("Не удалось получить список покупок. Выполнен ли вход? (кнопка «Войти»)")
                failed = True
                break
            got, tot = parse_purchases(out)
            if page == 1:
                first_json = next((ln for ln in out.splitlines() if ln.lstrip().startswith("{")), out.strip())
            if tot is not None:
                total = tot
            new = set(got) - set(acc)
            acc.update(got)
            self.log(f"Страница {page}: получено {len(got)}, всего найдено {len(acc)}"
                     + (f" из {total}" if total is not None else ""))
            if not new or (total is not None and len(acc) >= total):
                break
        if acc:
            self.log(f"Покупок всего: {len(acc)}. Проверяю, какие из них ещё есть в App Store ({country})…")
            avail = fetch_available(acc, country)
            if avail is None:
                self.log("Не удалось проверить наличие в App Store (нет доступа к itunes.apple.com?). "
                         "Показываю все покупки без фильтра.")
            else:
                gone = [i for i in acc if i not in avail]
                self.log(f"Удалены из App Store ({country}): {len(gone)} из {len(acc)}. "
                         + ("Они показаны в списке «Мои покупки»." if gone else
                            "Все покупки сейчас в сторе; снимите галочку фильтра, чтобы увидеть весь список."))
            self.post(lambda: self.on_purchases_result(acc, avail))
        elif failed:
            return
        elif total == 0:
            self.log(
                "Apple вернул 0 покупок для этого аккаунта. Возможные причины: приложения покупались под другим "
                "Apple ID или в другом регионе; вход выполнен под другим аккаунтом, чем на iPhone."
            )
        else:
            self.log("Список разобрать не удалось. Начало ответа ipatool: " + first_json[:400])

    def task_scan(self, ipatool, country="ru"):
        """Какие из известных удалённых приложений каталога когда-либо были у этого Apple ID.

        Проба владения — `ipatool list-versions -i ID`: ничего не скачивает, а Apple отвечает
        «license is required», если приложения нет в истории аккаунта.
        """
        self.stop_flag = False
        names = {a["id"]: a["name"] for a in self.catalog.apps}
        ids = list(names)
        if not ids:
            self.log("Каталог пуст: нечего проверять.")
            return
        self.log(f"В каталоге {len(ids)} приложений. Смотрю, какие из них уже удалены из App Store ({country})…")
        avail = fetch_available(ids, country)
        if avail is None:
            todo = ids
            self.log("Нет доступа к itunes.apple.com: проверю по аккаунту все приложения каталога (дольше).")
        else:
            todo = [i for i in ids if i not in avail]
            self.log(f"Удалено из App Store: {len(todo)}. Спрашиваю Apple, какие из них были у вас. Это может занять "
                     "несколько минут; кнопка «Остановить» прервёт проверку, найденное останется в списке.")
        owned, state = {}, {"unknown": 0, "consec": 0, "err": "", "done": 0, "abort": False}
        lock = threading.Lock()
        kc = core.keychain_args()

        def probe(app_id, env):
            if self.stop_flag or state["abort"]:
                return
            rc, out = run_quiet(list_versions_cmd(ipatool, kc, app_id), env=env)
            owns = ownership(rc, out)
            with lock:
                state["done"] += 1
                if owns is not None:
                    state["consec"] = 0
                    self.owned_state[app_id] = owns
                    if owns:
                        owned[app_id] = names[app_id]
                        self.log(f"  ✓ {names[app_id]} ({app_id}) — есть в вашей истории")
                        found = dict(owned)
                        self.post(lambda: self.on_purchases_result(found, set()))
                elif SESSION_LOST.search(out):
                    self.log("Вход не выполнен или сессия истекла. Нажмите «Войти» и повторите.")
                    state["abort"] = True
                else:
                    state["unknown"] += 1
                    state["consec"] += 1
                    state["err"] = clip(out)
                    if state["consec"] >= 12 and not state["abort"]:
                        self.log("Подряд 12 непонятных ответов, проверка прервана. Последний ответ ipatool: "
                                 + state["err"])
                        state["abort"] = True
                if state["done"] % 50 == 0:
                    self.log(f"Проверено {state['done']} из {len(todo)}, найдено {len(owned)}")

        in_session_copies(todo, probe, SCAN_WORKERS)
        self.post(self.refresh_list_keep)
        if self.stop_flag:
            self.log("Остановлено.")
        if state["abort"]:
            return
        unknown, last_err = state["unknown"], state["err"]
        self.log(f"Итог: найдено приложений в вашей истории — {len(owned)}"
                 + (f"; ответов без ясного результата — {unknown}" if unknown else "") + ".")
        if unknown and last_err:
            self.log("Пример неясного ответа: " + last_err)
        if not owned:
            self.log("Не найдено ни одного. Возможно, вход выполнен под другим Apple ID или регионом, чем скачивались "
                     "эти приложения.")

    def task_download(self, ipatool, app_id, name, purchase, version=None, fallback=False):
        core.OUT_DIR.mkdir(parents=True, exist_ok=True)  # у установленной версии это Документы\Restore\ipa
        suffix = f"_v{version}" if version else ""
        dest = core.OUT_DIR / f"{core.slug(name)}_{app_id}{suffix}.ipa"
        if version:
            same = next((p for p in storage.archived(app_id) if p.name.endswith(f"_v{version}.ipa")), None)
            if same and ipa_ok(same):
                self.log(f"Эта версия уже есть в архиве ({same.stat().st_size // 1048576} МБ) — скачивать не нужно.")
                return same
        cmd = [ipatool, *core.keychain_args(), "download", "-i", str(app_id), "-o", str(dest)]
        if version:
            cmd += ["--external-version-id", str(version)]
        if purchase:
            cmd.append("--purchase")
        out = ""
        for attempt in (1, 2, 3):  # ipatool сам докачивает с места обрыва
            rc, out = self.stream(cmd)
            if rc == 0 and dest.exists():
                break
            if not re.search(r"timeout|reset|EOF|connection|unexpected", out, re.I) or attempt == 3:
                break
            self.log(f"Сеть подвисла — повтор {attempt + 1} из 3, докачиваем с места обрыва…")
            time.sleep(3)
        if rc != 0 or not dest.exists():
            self.log("Не удалось скачать.")
            self.hint(out)
            old = [p for p in storage.archived(app_id) if ipa_ok(p)]
            if fallback and old:
                self.log(f"Беру ранее скачанный файл из архива: {old[0].name}")
                return old[0]
            if old:
                self.log(f"В архиве есть ранее скачанный файл: {old[0].name} — его можно поставить кнопкой "
                         "«Установить IPA из файла…».")
            return None
        self.log(f"Готово: {dest}")
        storage.record_download(app_id, version)
        return dest

    def task_install(self, installer, ipa):
        self.log("Подключите iPhone по USB, разблокируйте и нажмите «Доверять».")
        self.note_if_installed(installer, ipa)
        rc, out = self.stream(installer_cmd(installer, "install", ipa))
        self.log("Установлено." if rc == 0 else "Установка не удалась (код %s)." % rc)
        if rc != 0:
            self.hint(out)
        return rc == 0

    def note_if_installed(self, installer, ipa):
        """Подсказка в журнале, если такое приложение уже стоит на iPhone (установка пойдёт поверх)."""
        bid = ipa_info(ipa).get("CFBundleIdentifier")
        if not bid:
            return
        rc, out = run_quiet(installer_cmd(installer, "list"), timeout=60)
        if rc == 0 and bid in out:
            self.log(f"Приложение {bid} уже установлено на iPhone — ставлю поверх, данные сохранятся.")

    def device_ios(self, installer):
        """Версия iOS подключённого iPhone или None."""
        info = probe_device()
        if info and info.get("ios"):
            return info["ios"]
        cmd = installer_cmd(installer, "info") if installer else None
        if not cmd:
            return None
        rc, out = run_quiet(cmd, timeout=45)
        if rc != 0:
            return None
        m = re.search(r'"?ProductVersion"?\s*[:=]\s*"?(\d+(?:\.\d+){0,2})', out) or \
            re.fullmatch(r"\s*(\d+(?:\.\d+){0,2})\s*", out)
        return m.group(1) if m else None

    def task_restore(self, ipatool, installer, app_id, name, purchase, version=None, versions=None):
        """Скачать и установить. version=None — «автоматически»: новейшая версия, подходящая под iOS телефона."""
        ios = self.device_ios(installer)
        self.log(f"iPhone: iOS {ios}" if ios else "Версию iOS iPhone определить не удалось — подбор версии пропущен.")
        versions = list(versions or [])
        auto = version is None
        if auto and versions:
            version = versions[0]  # последняя известная версия — с ID, чтобы работал архив
        dest = self.task_download(ipatool, app_id, name, purchase, version, fallback=True)
        if not dest:
            return False
        plist = ipa_info(dest)
        need, shown = plist.get("MinimumOSVersion"), plist.get("CFBundleShortVersionString")
        if ios and need and vtuple(need) > vtuple(ios):
            self.log(f"Версия {shown or '?'} требует iOS {need}, а на iPhone iOS {ios}.")
            if not auto or len(versions) < 2:
                self.log("Выберите в окне приложения «Автоматически» — программа сама подберёт подходящую версию.")
                return False
            dest = self.pick_compatible(ipatool, app_id, name, versions, ios)
            if not dest:
                return False
        elif ios and need:
            self.log(f"Версия {shown or '?'} подходит: нужна iOS {need}, на iPhone {ios}.")
        return self.task_install(installer, dest)

    def pick_compatible(self, ipatool, app_id, name, versions, ios, budget=7):
        """Двоичный поиск новейшей подходящей версии: старые версии требуют более старую iOS.

        versions — ID по убыванию (новые первыми); versions[0] уже известна как неподходящая.
        Каждая проба — скачивание IPA (попадает в архив и повторно не качается).
        """
        lo, hi, best = 1, len(versions) - 1, None
        tries = 0
        while lo <= hi and tries < budget and not self.stop_flag:
            mid = (lo + hi) // 2
            tries += 1
            self.log(f"Подбор версии для iOS {ios}: проверяю вариант {mid + 1} из {len(versions)}…")
            path = self.task_download(ipatool, app_id, name, False, versions[mid])
            if not path:
                return None
            plist = ipa_info(path)
            need, shown = plist.get("MinimumOSVersion"), plist.get("CFBundleShortVersionString")
            if need and vtuple(need) > vtuple(ios):
                lo = mid + 1
            else:
                best = (path, shown, need)
                hi = mid - 1
        if not best:
            self.log("Не нашлось версии этого приложения для вашей iOS: даже старые требуют iOS новее, "
                     "или Apple отдал не все версии.")
            return None
        self.log(f"Подходит версия {best[1] or '?'} (нужна iOS {best[2] or '?'}).")
        return best[0]

    def task_batch(self, ipatool, installer, apps):
        self.stop_flag = False
        done, skipped, failed = [], [], []
        kc = core.keychain_args()
        for n, app in enumerate(apps, 1):
            if self.stop_flag:
                self.log("Остановлено.")
                break
            self.log(f"── {n}/{len(apps)}: {app['name']} ({app['id']})")
            rc, out = self.dq(list_versions_cmd(ipatool, kc, app["id"]))
            owned = ownership(rc, out)
            if not owned:
                if owned is False:
                    self.owned_state[app["id"]] = False
                    self.log("Нет в истории вашего Apple ID — пропускаю.")
                    skipped.append(app["name"])
                else:
                    self.log("Не удалось проверить приложение.")
                    self.hint(out)
                    failed.append(app["name"])
                    if explain_error(out) and re.search(r"Сессия|Нет связи|блокир", explain_error(out)[0]):
                        break  # дальше будет то же самое
                continue
            self.owned_state[app["id"]] = True
            ok = self.task_restore(ipatool, installer, app["id"], app["name"], False, None, parse_versions(out))
            (done if ok else failed).append(app["name"])
        self.post(self.refresh_list_keep)
        self.log(f"Итог: установлено {len(done)}, нет в истории {len(skipped)}, ошибок {len(failed)}.")
        if skipped:
            self.log("Нет в истории Apple ID: " + ", ".join(skipped))
        if failed:
            self.log("С ошибкой: " + ", ".join(failed))
        if done:
            self.post(self.clear_selection)

    # ---------- iPhone ----------
    def watch_device(self):
        """Фоновая проверка подключения iPhone (раз в 4 с, пока нет долгой операции)."""
        while True:
            if not self.busy:
                info = probe_device()
                if info != self.device:
                    self.device = info
                    self.post(self.update_device)
            time.sleep(4)

    def task_netcheck(self):
        self.log("Проверка связи с серверами Apple:")
        bad, reasons = [], []
        for host, purpose in APPLE_HOSTS:
            try:
                ips = sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})
            except OSError:
                self.log(f"  ✗ {host} — {purpose}: адрес не находится (DNS)")
                bad.append(host)
                continue
            fake = [ip for ip in ips if ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback
                    or ip.startswith("0.")]
            if fake:
                self.log(f"  ✗ {host} — {purpose}: подменён адрес {fake[0]} (DNS для обхода блокировок или hosts)")
                bad.append(host)
                continue
            try:
                req = urllib.request.Request(f"https://{host}/", method="HEAD")
                urllib.request.urlopen(req, timeout=10)
                ok = True
            except urllib.error.HTTPError:
                ok = True  # сервер ответил (404/403 — нормально для корня)
            except (urllib.error.URLError, OSError) as e:
                ok = False
                reason = getattr(e, "reason", e)
            if ok:
                self.log(f"  ✓ {host} — {purpose}")
            else:
                self.log(f"  ✗ {host} — {purpose}: {reason}")
                bad.append(host)
                reasons.append(str(reason))
        if not bad:
            self.log("Связь с Apple в порядке.")
        else:
            if any(re.search(r"certificate|x509|ssl", r, re.I) for r in reasons):
                self.hint("x509")
            else:
                self.hint("no such host")
