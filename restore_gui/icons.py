"""Иконки приложений из App Store: ссылки — из iTunes Lookup (тот же публичный сервис, что проверка наличия),
картинки — с серверов Apple. Кэш — в папке программы (%LOCALAPPDATA%\\Restore\\icons). Для приложений, удалённых
отовсюду, Apple картинку не отдаёт — у них остаётся буква; такие ID помним неделю, чтобы не спрашивать зря."""
import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import restore_apps as core

ICONS = core.DATA_DIR / "icons"
MISSING = ICONS / "missing.json"  # {app_id: время последней неудачной попытки}
RETRY_AFTER = 7 * 24 * 3600
COUNTRIES = ("ru", "us", "kz", "tr")  # удалённое из российского App Store часто есть в других странах
ART_URL = re.compile(r"https://[a-z0-9-]+\.mzstatic\.com/\S+\Z")  # картинки App Store раздаёт Apple с mzstatic.com
MAX_ICON = 2 * 1024 * 1024  # иконка 128×128 весит десятки КБ; больше — не иконка


def cached(app_id):
    p = ICONS / f"{app_id}.png"
    return p if p.is_file() else None


class IconLoader:
    """Фоновая загрузка иконок; on_ready(app_id, path) вызывается из рабочего потока."""

    def __init__(self, on_ready):
        self.on_ready = on_ready
        self.pool = ThreadPoolExecutor(max_workers=6)
        self._stop = threading.Event()

    def start(self, ids):
        self.pool.submit(self._run, list(ids))

    def stop(self):
        self._stop.set()
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _run(self, ids):
        try:
            ICONS.mkdir(parents=True, exist_ok=True)
            missing = json.loads(MISSING.read_text(encoding="utf-8")) if MISSING.exists() else {}
        except (OSError, ValueError):
            missing = {}
        now = time.time()
        todo = [i for i in ids if not cached(i) and now - missing.get(str(i), 0) > RETRY_AFTER]
        urls = {}
        unchecked = set()  # запрос не удался хотя бы в одной стране: «нет иконки» про них знать нельзя
        for country in COUNTRIES:
            left = [i for i in todo if i not in urls]
            for k in range(0, len(left), 100):
                if self._stop.is_set():
                    return
                part = left[k:k + 100]
                url = f"https://itunes.apple.com/lookup?country={country}&id=" + ",".join(map(str, part))
                try:
                    with urllib.request.urlopen(url, timeout=20) as r:
                        data = json.load(r)
                except (OSError, ValueError):
                    unchecked.update(part)
                    continue
                for x in data.get("results", []):
                    art = x.get("artworkUrl100")
                    if art and x.get("trackId"):
                        urls[int(x["trackId"])] = art.replace("100x100bb", "128x128bb")
        # «нет иконки на неделю» — только если Apple во всех странах ответил и иконки не дал;
        # иначе запуск без сети оставлял все приложения без иконок на 7 дней
        for i in todo:
            if i not in urls and i not in unchecked:
                missing[str(i)] = now
        try:
            MISSING.write_text(json.dumps(missing), encoding="utf-8")
        except OSError:
            pass
        for app_id, art in urls.items():
            if not self._stop.is_set():
                self.pool.submit(self._download, app_id, art)

    def _download(self, app_id, art):
        # картинка — только с серверов Apple по https и не больше MAX_ICON: адрес приходит из ответа iTunes Lookup
        if not ART_URL.match(art or ""):
            return
        dest = ICONS / f"{int(app_id)}.png"
        tmp = dest.with_suffix(".part")
        try:
            with urllib.request.urlopen(art, timeout=20) as r:
                data = r.read(MAX_ICON + 1)
            if len(data) > MAX_ICON or not data.startswith((b"\x89PNG", b"\xff\xd8")):  # PNG или JPEG
                return
            tmp.write_bytes(data)
            tmp.replace(dest)
        except OSError:
            return
        self.on_ready(app_id, dest)
