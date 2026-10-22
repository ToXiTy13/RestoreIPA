"""ipatool и сервера Apple: запуск команд, разбор ответов, понятные объяснения ошибок. Без интерфейса."""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import restore_apps as core

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")  # цветовые коды ipatool в журнале не нужны
NOT_OWNED = re.compile(r"license is required", re.I)  # Apple: приложения нет в истории этого Apple ID
SESSION_LOST = re.compile(r"failed to get account|keyring|not logged|sign.?in|password token", re.I)
UNICORN_VERSION = "2.1.4"
UNICORN_SHA256 = "d8f9a89222ffa74493a1d47090e17f8e1db8ac171a3128c6a76a4ea09de11469"  # как в исходниках ipatool
# адреса, без которых не работает вход/скачивание (для «Проверить связь с Apple»)
APPLE_HOSTS = (
    ("buy.itunes.apple.com", "вход и лицензии"),
    ("p25-buy.itunes.apple.com", "покупки и версии"),
    ("init.itunes.apple.com", "настройки магазина"),
    ("fpinit.itunes.apple.com", "подпись входа"),
    ("iosapps.itunes.apple.com", "скачивание IPA"),
    ("itunes.apple.com", "поиск и наличие в App Store"),
    ("swcdn.apple.com", "служебные файлы для первого входа"),
    ("github.com", "резерв для эмулятора (если встроенный не подошёл)"),
)


def ipatool_cache_root():
    """Куда ipatool кладёт кэш (Go: os.UserCacheDir()/ipatool)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ipatool"


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seed_unicorn():
    """Положить встроенный libunicorn.dll в кэш ipatool, чтобы первый вход не качал его с GitHub.

    Это тот же официальный файл Unicorn 2.1.4, который ipatool скачивает сам; хеш сверяется.
    Возвращает True, если файл был положен сейчас.
    """
    if not sys.platform.startswith("win"):
        return False
    src = bundled("libunicorn.dll")
    if not src:
        return False
    dest = ipatool_cache_root() / "unicorn" / UNICORN_VERSION / UNICORN_SHA256 / "libunicorn.dll"
    try:
        if dest.exists() and sha256_file(dest) == UNICORN_SHA256:
            return False
        if sha256_file(src) != UNICORN_SHA256:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return True
    except OSError:
        return False


def sap_ready():
    """Скачаны ли уже служебные файлы Apple, нужные ipatool для входа."""
    d = ipatool_cache_root() / "sap" / "apple-assets-v2"
    try:
        return d.is_dir() and any(d.iterdir())
    except OSError:
        return False


HINTS = (
    (r"no such host|getaddrinfo|dial tcp|i/o timeout|connection (reset|refused)|network is unreachable|EOF",
     "Нет связи с серверами Apple. Частая причина — DNS «для обхода блокировок» (Comss, GeoHide и т.п.), он "
     "подменяет адреса Apple: верните автоматический DNS в настройках сети. Также мешают записи в файле hosts. "
     "Нажмите «Проверить связь с Apple» слева."),
    (r"x509|certificate|tls: ",
     "Защищённое соединение с Apple перехватывается. Обычно это антивирус с проверкой HTTPS (Касперский, ESET, "
     "Dr.Web) — отключите в нём проверку защищённых соединений или добавьте программу в исключения."),
    (r"account (is )?(disabled|locked)|has been (disabled|locked)",
     "Apple заблокировал этот Apple ID. Пароль ни при чём: восстановите доступ на iforgot.apple.com."),
    (r"invalid credentials|bad.?credentials|incorrect|password is incorrect|MZFinance.BadLogin",
     "Неверный Apple ID или пароль. Если окно с кодом на iPhone не появилось — почти наверняка ошибка в пароле."),
    (r"429|rate.?limit|too many",
     "Apple временно ограничил попытки. НЕ повторяйте вход подряд: подождите около часа и попробуйте один раз."),
    (r"license is required|license.*not found",
     "Этого приложения нет в истории покупок вашего Apple ID — Apple его не отдаст. Войдите под тем Apple ID, "
     "под которым его когда-то скачивали."),
    (r"password token expired|sign.?in required|failed to get account|not logged",
     "Сессия входа истекла или вход не выполнен. Нажмите «Войти»."),
    (r"mac address", "ipatool не нашёл сетевой адаптер (нужен для подписи запросов). Включите сетевой адаптер."),
    (r"DeviceLocked|PasswordProtected|locked",
     "iPhone заблокирован. Разблокируйте его и держите экран включённым во время установки."),
    (r"No ?Device|device not found|not connected|ConnectionFailed|usbmux",
     "iPhone не найден. Подключите кабелем, нажмите «Доверять» и введите код-пароль. На Windows нужен iTunes "
     "или «Устройства Apple» из Microsoft Store (это драйвер USB)."),
    (r"MinimumOSVersion|DeviceOSVersionTooLow|requires iOS",
     "Эта версия приложения не подходит для iOS на вашем iPhone — выберите «Автоматически» в окне приложения."),
)


def explain_error(text):
    seen = []
    for pat, hint in HINTS:
        if re.search(pat, text or "", re.I) and hint not in seen:
            seen.append(hint)
    return seen


def bundled(name):
    """Путь к инструменту, вшитому в exe (или лежащему рядом с программой)."""
    for base in (core.BUNDLE, core.HERE):
        for n in (name + ".exe", name):
            p = base / n
            if p.is_file():
                return str(p)
    return None


def extract_apps(obj, acc):
    """Достаёт пары (id, название) из JSON-ответа `ipatool list-purchases`.

    ipatool v2.7 печатает элементы как {"id":…, "bundleID":…, "name":…, "version":…};
    ключи сверяются без учёта регистра, на случай других версий.
    """
    if isinstance(obj, dict):
        low = {str(k).lower(): v for k, v in obj.items()}
        i = next((low[k] for k in ("id", "trackid", "appid", "adamid", "app_id") if k in low), None)
        n = next((low[k] for k in ("name", "trackname", "appname", "title") if k in low), None)
        if i is not None and n is not None and str(i).isdigit():
            acc[int(i)] = str(n)
        for v in obj.values():
            extract_apps(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            extract_apps(v, acc)


def parse_purchases(text):
    """Из вывода ipatool: (найденные приложения {id: имя}, totalCount или None)."""
    acc, total = {}, None
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        extract_apps(obj, acc)
        if isinstance(obj, dict):
            low = {str(k).lower(): v for k, v in obj.items()}
            if isinstance(low.get("totalcount"), int):
                total = low["totalcount"]
    return acc, total


def fetch_available(ids, country, chunk=100):
    """ID, которые сейчас есть в App Store страны `country` (iTunes Lookup).

    Возвращает множество; None, если проверить не удалось (нет сети и т. п.).
    """
    ids = list(ids)
    found = set()
    for i in range(0, len(ids), chunk):
        part = ids[i:i + chunk]
        url = "https://itunes.apple.com/lookup?country=%s&id=%s" % (country, ",".join(str(x) for x in part))
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data = json.load(r)
        except (urllib.error.URLError, ValueError, OSError):
            return None
        for x in data.get("results", []):
            if x.get("trackId") is not None:
                found.add(int(x["trackId"]))
    return found

def run_quiet(cmd, timeout=90, env=None):
    """Запуск без построчного журнала: (код возврата, весь вывод без цветовых кодов)."""
    try:
        p = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW,
            env=env if env is not None else (core.ipatool_env() if core.is_ipatool(cmd) else None),
        )
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return p.returncode, ANSI.sub("", (p.stdout or "") + (p.stderr or ""))


def in_session_copies(items, fn, workers):
    """fn(item, env) для каждого item в нескольких потоках: запрос к Apple ждёт сеть 1–2 с, так быстрее.

    ipatool хранит сессию и cookies в ~/.ipatool, и параллельные процессы портят общие файлы (падение
    с panic), поэтому у каждого потока своя копия сессии во временной папке; env — окружение с этой папкой.
    Копии удаляются в конце (и при следующем запуске программы, если она упала — см. wipe_session).
    """
    items = list(items)
    if not items:
        return
    n = max(1, min(workers, len(items)))
    src_dir = core.IPATOOL_HOME / ".ipatool"
    for stale in src_dir.glob("*.lock"):  # остались от аварийно завершённых процессов
        try:
            stale.unlink()
        except OSError:
            pass
    root = Path(tempfile.mkdtemp(prefix="restore_scan_"))
    envs = queue.Queue()
    try:
        for w in range(n):
            h = root / f"w{w}"
            h.mkdir()
            if src_dir.exists():
                shutil.copytree(src_dir, h / ".ipatool", ignore=shutil.ignore_patterns("*.lock"))
            # ipatool на Windows берёт домашнюю папку из HOMEDRIVE+HOMEPATH, на остальных ОС из HOME
            drive, rest = os.path.splitdrive(str(h))
            envs.put(dict(os.environ, USERPROFILE=str(h), HOME=str(h), HOMEDRIVE=drive, HOMEPATH=rest))

        def one(item):
            env = envs.get()
            try:
                fn(item, env)
            finally:
                envs.put(env)

        with ThreadPoolExecutor(max_workers=n) as pool:
            list(pool.map(one, items))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def list_versions_cmd(ipatool, kc, app_id):
    """Проба владения: ничего не скачивает, а Apple отвечает «license is required», если приложения нет в истории."""
    return [ipatool, *kc, "list-versions", "-i", str(app_id), "--format", "json"]


def ownership(rc, out):
    """Ответ list-versions: True — приложение есть в истории Apple ID, False — нет, None — понять нельзя."""
    if rc == 0:
        return True
    return False if NOT_OWNED.search(out) else None


def parse_versions(out):
    """ID версий из ответа list-versions, новые первыми."""
    versions = set()
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("externalVersionIdentifiers"), list):
            versions.update(str(x) for x in obj["externalVersionIdentifiers"])
    return sorted(versions, key=lambda x: int(x) if x.isdigit() else 0, reverse=True)


def clip(text, limit=700, head=450, tail=250):
    """Длинный ответ ipatool для журнала: начало и конец; пустой — «(пустой ответ)»."""
    t = (text or "").strip()
    return (t if len(t) <= limit else t[:head] + "\n …\n" + t[-tail:]) or "(пустой ответ)"
