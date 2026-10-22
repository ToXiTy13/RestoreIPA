"""Служебные файлы программы (%LOCALAPPDATA%\\Restore) и скачанные .ipa. Ни пароль, ни email Apple ID здесь
не хранятся."""
import json
import re

import restore_apps as core

HISTORY = core.DATA_DIR / "history.json"  # {app_id: [ID версий, скачанных через программу]}
META_CACHE = core.DATA_DIR / "versions_cache.json"  # номера и даты версий: публичные данные Apple
EMAIL = core.DATA_DIR / "email.txt"  # так прежние версии запоминали email для поля входа; теперь только удаляется


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
    h = load_history()
    lst = h.setdefault(str(app_id), [])
    if str(version) not in lst:
        lst.append(str(version))
    _write(HISTORY, json.dumps(h))


def load_meta():
    return _read_json(META_CACHE)


def save_meta(app_id, meta):
    """Добавить в кэш номера и даты версий приложения: {ID версии: (номер, дата)}."""
    cache = load_meta()
    cache.setdefault(str(app_id), {}).update({v: list(x) for v, x in meta.items()})
    _write(META_CACHE, json.dumps(cache))


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
