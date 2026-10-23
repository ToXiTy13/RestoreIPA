"""Служебные файлы программы (%LOCALAPPDATA%\\Restore) и скачанные .ipa; уборка того, что оставляют Qt, распаковка
exe и прежние версии программы. Ни пароль, ни email Apple ID на диске не хранятся."""
import contextlib
import json
import re
import shutil
import sys
import threading
import time
from pathlib import Path

import restore_apps as core

_LOCK = threading.Lock()  # чтение-изменение-запись файлов ниже идёт из нескольких потоков
HISTORY = core.DATA_DIR / "history.json"  # {app_id: [ID версий, скачанных через программу]}
META_CACHE = core.DATA_DIR / "versions_cache.json"  # номера и даты версий: публичные данные Apple
EMAIL = core.DATA_DIR / "email.txt"  # так прежние версии запоминали email для поля входа; теперь только удаляется
SETTINGS = core.DATA_DIR / "settings.json"  # настройки окна «Настройки» (тема, папка загрузок, …)


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(path, text):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def load_history():
    return _read_json(HISTORY)


def record_download(app_id, version):
    """Помним, какие версии скачаны через эту программу (Apple такой список не отдаёт)."""
    if not version:
        return
    with _LOCK:
        h = load_history()
        lst = h.setdefault(str(app_id), [])
        if str(version) not in lst:
            lst.append(str(version))
        _write(HISTORY, json.dumps(h))


def forget_download(app_id, version):
    """Убрать версию из истории скачиваний (её файл удалён)."""
    with _LOCK:
        h = load_history()
        lst = h.get(str(app_id), [])
        if str(version) not in lst:
            return
        lst.remove(str(version))
        if not lst:
            del h[str(app_id)]
        _write(HISTORY, json.dumps(h))


def load_meta():
    return _read_json(META_CACHE)


def save_meta(app_id, meta):
    """Добавить в кэш номера и даты версий приложения: {ID версии: (номер, дата)}."""
    with _LOCK:
        cache = load_meta()
        cache.setdefault(str(app_id), {}).update({v: list(x) for v, x in meta.items()})
        _write(META_CACHE, json.dumps(cache))


def load_settings():
    s = _read_json(SETTINGS)
    return s if isinstance(s, dict) else {}


def save_settings(settings):
    _write(SETTINGS, json.dumps(settings, ensure_ascii=False, indent=1))


def forget_email():
    """Удалить email.txt прежних версий: email Apple ID программа на диске не держит."""
    try:
        EMAIL.unlink()
    except OSError:
        pass  # нет файла — хорошо; занят или нет прав — попробуем при следующем выходе/закрытии


def archived(app_id):
    """IPA этого приложения, уже лежащие в папке загрузок (новые первыми)."""
    if not core.OUT_DIR.exists():
        return []
    files = [p for p in core.OUT_DIR.glob(f"*_{app_id}*.ipa")
             if re.search(rf"_{app_id}(_v\d+)?\.ipa$", p.name)]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


# ---------- следы вне папки программы ----------
QT_REGISTRY = r"Software\QtProject"  # QSettings «QtProject»: сюда QFileDialog пишет последнюю папку и историю
STALE_AFTER = 600  # с; папка распаковки моложе может принадлежать exe, который распаковывается прямо сейчас


def remove_leftovers():
    """Удалить пустую ~/.pymobiledevice3 от версий до 1.1.0: папка pymobiledevice3 теперь в DATA_DIR
    (см. device.own_pmd_folder); непустую не трогаем."""
    with contextlib.suppress(OSError):
        (Path.home() / ".pymobiledevice3").rmdir()


def remove_stale_unpacked():
    """Удалить брошенные папки распаковки портативного exe во %TEMP%.

    exe одним файлом при каждом запуске распаковывается во %TEMP%\\_MEI… и при выходе удаляет эту папку сам.
    Если же процесс убили (диспетчер задач, отключение питания), папка остаётся навсегда. Удаляем только свои
    (в них наш интерфейс и каталог), не моложе STALE_AFTER и не занятые: у работающего экземпляра загружена
    python3*.dll, а загруженную DLL Windows удалить не даёт (переименовать папку — даёт, так что это не проверка).
    """
    me = Path(getattr(sys, "_MEIPASS", ""))
    if not core.FROZEN or not me.name.startswith("_MEI"):
        return
    now = time.time()
    for d in me.parent.glob("_MEI*"):
        try:
            if (d == me or now - d.stat().st_mtime < STALE_AFTER or not (d / core._CSV).is_file()
                    or not (d / "restore_gui" / "qml" / "Main.qml").is_file()):
                continue
            # python3XX.dll — первой: её загрузчик exe грузит сразу, python3.dll — только позже, с модулями Qt
            for dll in sorted(d.glob("python3*.dll"), key=lambda p: -len(p.name)):
                dll.unlink()
        except OSError:
            continue  # папка работающего экземпляра
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def registry_untouched(path=QT_REGISTRY):
    """После блока раздел реестра HKCU\\path — такой же, как до него.

    QFileDialog при закрытии (даже системного окна Windows) записывает последнюю папку и историю в
    HKCU\\Software\\QtProject — общий раздел всех программ на Qt. Созданное за время блока удаляем, изменённое
    возвращаем: значения других программ остаются как были, своих следов программа там не оставляет.
    """
    if not sys.platform.startswith("win"):
        yield
        return
    before = _reg_snapshot(path)
    try:
        yield
    finally:
        _reg_restore(path, before)


def _reg_snapshot(path):
    """{подраздел: {имя: (значение, тип)}} — раздел HKCU\\path со всеми подразделами; {} — раздела нет."""
    import winreg
    tree, todo = {}, [path]
    while todo:
        sub = todo.pop()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub)
        except OSError:
            continue
        with key:
            n_keys, n_values, _ = winreg.QueryInfoKey(key)
            values = (winreg.EnumValue(key, i) for i in range(n_values))
            tree[sub] = {name: (data, kind) for name, data, kind in values}
            todo += [sub + "\\" + winreg.EnumKey(key, i) for i in range(n_keys)]
    return tree


def _reg_restore(path, before):
    import winreg
    after = _reg_snapshot(path)
    for sub in sorted(after, key=len, reverse=True):  # подразделы — раньше родителей: DeleteKey удаляет только пустой
        with contextlib.suppress(OSError):
            if sub not in before:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
                continue
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_SET_VALUE) as key:
                for name in after[sub].keys() - before[sub].keys():
                    winreg.DeleteValue(key, name)
                for name, (data, kind) in before[sub].items():
                    if after[sub].get(name) != (data, kind):
                        winreg.SetValueEx(key, name, 0, kind, data)
