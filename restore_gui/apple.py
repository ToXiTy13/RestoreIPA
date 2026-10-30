"""ipatool и сервера Apple: запуск команд, разбор ответов, понятные объяснения ошибок. Без интерфейса."""
import contextlib
import hashlib
import json
import os
import platform
import queue
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import restore_apps as core

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")  # цветовые коды ipatool в журнале не нужны
NOT_OWNED = re.compile(r"license is required", re.I)  # Apple: приложения нет в истории этого Apple ID
SESSION_LOST = re.compile(r"failed to get account|keyring|not logged|sign.?in|password token", re.I)
# копии сессии для параллельных запросов (in_session_copies); до 1.1.0 — %TEMP%\restore_scan_*
SCAN_ROOT = core.DATA_DIR / "scan"
UNICORN_VERSION = "2.1.4"
UNICORN_SHA256 = "d8f9a89222ffa74493a1d47090e17f8e1db8ac171a3128c6a76a4ea09de11469"  # как в исходниках ipatool
# официальный ipatool 2.7.0 (build.ps1, build_mac.sh): встроенный сверяется с ним перед запуском.
# На macOS — хеш кода без подписи (ipatool_digest): PyInstaller переподписывает программы внутри .app
IPATOOL_SHA256 = {
    "win32-amd64": "7b83589b74ad533f5d5dbab0ca87a5cb76b123bcbeb2553d57e9c154e35d8755",
    "darwin-arm64": "f64c6ccdd10548ef1f0ad69fd539feeee03831fdb4c18ce5946ebaf7329796df",
    "darwin-x86_64": "95108a8328021a4cefe415cb38086e81e9a56c180decc9fcb60e2bdea418c249",
}
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


def adopt_old_cache():
    """Перенести кэш ipatool версий до 1.1.0 из %LOCALAPPDATA%\\ipatool в папку программы (core.IPATOOL_CACHE).

    Там служебные файлы Apple для входа (их первая загрузка — до 15 минут) и Unicorn, вместе ~60 МБ. Переносятся
    только эти две папки и только если в папке программы их ещё нет; пустая старая папка удаляется.
    """
    if not sys.platform.startswith("win"):
        return False
    old = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ipatool"
    if old == core.IPATOOL_CACHE:
        return False
    moved = False
    for name in ("sap", "unicorn"):
        src, dest = old / name, core.IPATOOL_CACHE / name
        if src.is_dir() and not dest.exists():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dest)  # тот же диск: мгновенно, без копирования
                moved = True
            except OSError:
                pass  # занято или нет прав — ipatool скачает заново
    with contextlib.suppress(OSError):
        old.rmdir()  # только пустую: если там что-то ещё, это не наше
    return moved


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def macho_code_sha256(path):
    """SHA-256 программы macOS (64-битный Mach-O) без подписи: всё до подписи, а в заголовке — без описания подписи
    (LC_CODE_SIGNATURE) и сегмента __LINKEDIT, где лежит её размер. Код при переподписи не меняется, хеш тоже."""
    return macho_code_hashes(path)[0]


def macho_code_hashes(path):
    """Хеши кода Mach-O без подписи (см. macho_code_sha256) для двух случаев:
    0 — у официального файла уже была подпись, и при сборке .app её заменили (ipatool для arm64);
    1 — официальный файл был без подписи, и её добавили при сборке (ipatool для Intel): в заголовке на одну команду
        больше, а перед подписью — выравнивание; хеш — как у файла до подписи: команды без LC_CODE_SIGNATURE,
        содержимое до конца таблицы строк (LC_SYMTAB). Без подписи — только первый, второй None."""
    data = bytearray(Path(path).read_bytes())
    if data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("не 64-битный Mach-O")
    ncmds, sizeofcmds = struct.unpack_from("<II", data, 16)
    off, end, sig_size, strings_end = 32, len(data), 0, None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        if cmd == 0x1D:  # LC_CODE_SIGNATURE
            end = struct.unpack_from("<I", data, off + 8)[0]
            sig_size = size
            data[off:off + size] = bytes(size)
        elif cmd == 0x19 and data[off + 8:off + 24].rstrip(b"\0") == b"__LINKEDIT":  # LC_SEGMENT_64
            data[off:off + size] = bytes(size)
        elif cmd == 0x2:  # LC_SYMTAB: symoff, nsyms, stroff, strsize
            stroff, strsize = struct.unpack_from("<II", data, off + 16)
            strings_end = stroff + strsize
        off += size
    replaced = hashlib.sha256(bytes(data[:end])).hexdigest()
    if not sig_size:
        return replaced, None
    struct.pack_into("<II", data, 16, ncmds - 1, sizeofcmds - sig_size)
    added_end = strings_end if strings_end and strings_end <= end else end
    return replaced, hashlib.sha256(bytes(data[:added_end])).hexdigest()


def ipatool_digest(path):
    return macho_code_sha256(path) if sys.platform == "darwin" else sha256_file(path)


def ipatool_digests(path):
    """Все хеши, по которым ipatool сверяется с IPATOOL_SHA256 (на macOS — оба случая macho_code_hashes)."""
    if sys.platform == "darwin":
        return {h for h in macho_code_hashes(path) if h}
    return {sha256_file(path)}


_ipatool_checked = {}  # путь -> (размер, время изменения, результат): 40 МБ не читаем на каждый запуск ipatool


def ipatool_genuine(path):
    """Совпадает ли ipatool с официальным (IPATOOL_SHA256). None — для этой системы хеша нет (сборок под неё нет)."""
    expected = IPATOOL_SHA256.get(f"{sys.platform}-{platform.machine().lower()}")
    if not expected:
        return None
    try:
        st = os.stat(path)
        key = (st.st_size, st.st_mtime_ns)
        if _ipatool_checked.get(path, (None,))[:2] != key:
            _ipatool_checked[path] = (*key, expected in ipatool_digests(path))
        return _ipatool_checked[path][2]
    except (OSError, ValueError, struct.error):
        return False


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
    dest = core.IPATOOL_CACHE / "unicorn" / UNICORN_VERSION / UNICORN_SHA256 / "libunicorn.dll"
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
    d = core.IPATOOL_CACHE / "sap" / "apple-assets-v2"
    try:
        return d.is_dir() and any(d.iterdir())
    except OSError:
        return False


# ошибки, после которых следующие запросы к Apple упадут так же (пакетная установка на них прерывается)
NET_ERROR = (r"no such host|getaddrinfo|dial tcp|i/o timeout|connection (reset|refused)|network is unreachable"
             r"|unexpected EOF|\": EOF\b")
ACCOUNT_LOCKED = r"account (is )?(disabled|locked)|has been (disabled|locked)"
NO_SESSION = r"password token expired|sign.?in required|failed to get account|not logged"

HINTS = (
    (NET_ERROR,
     "Нет связи с серверами Apple. Частая причина — DNS «для обхода блокировок» (Comss, GeoHide и т.п.), он "
     "подменяет адреса Apple: верните автоматический DNS в настройках сети. Также мешают записи в файле hosts. "
     "Нажмите «Проверить связь с Apple» в меню «⋯» вверху справа."),
    (r"x509|certificate|tls: ",
     "Защищённое соединение с Apple перехватывается. Обычно это антивирус с проверкой HTTPS (Касперский, ESET, "
     "Dr.Web). Добавьте в его исключения проверки защищённых соединений адреса Apple (*.apple.com) или программу "
     "Restore — отключать проверку целиком не нужно."),
    (ACCOUNT_LOCKED,
     "Apple заблокировал этот Apple ID. Пароль ни при чём: восстановите доступ на iforgot.apple.com."),
    # «Your Apple ID or password was entered incorrectly.» — но не любое «incorrect» в выводе
    (r"invalid credentials|bad.?credentials|(apple id|password|credentials)[^\n]{0,40}incorrect|MZFinance.BadLogin",
     "Неверный Apple ID или пароль. Если окно с кодом на iPhone не появилось — почти наверняка ошибка в пароле."),
    (r"\b429\b|rate.?limit|too many",  # \b: не цифры внутри App ID или размера файла
     "Apple временно ограничил попытки. НЕ повторяйте вход подряд: подождите около часа и попробуйте один раз."),
    (r"license is required|license.*not found",
     "Этого приложения нет в истории покупок вашего Apple ID — Apple его не отдаст. Войдите под тем Apple ID, "
     "под которым его когда-то скачивали."),
    (NO_SESSION,
     "Сессия входа истекла или вход не выполнен. Нажмите «Войти»."),
    (r"mac address", "ipatool не нашёл сетевой адаптер (нужен для подписи запросов). Включите сетевой адаптер."),
    # не просто «locked»: иначе «account is locked» даёт ещё и совет разблокировать iPhone
    (r"DeviceLocked|PasswordProtected|(device|phone) (is )?locked",
     "iPhone заблокирован. Разблокируйте его и держите экран включённым во время установки."),
    (r"No ?Device|device not found|not connected|ConnectionFailed|usbmux",
     "iPhone не найден. Подключите кабелем, нажмите «Доверять» и введите код-пароль."
     + (" На Windows нужен iTunes или «Устройства Apple» из Microsoft Store (это драйвер USB)."
        if sys.platform.startswith("win") else "")),
    (r"MinimumOSVersion|DeviceOSVersionTooLow|requires iOS",
     "Эта версия приложения не подходит для iOS на вашем iPhone — выберите «Автоматически» в окне приложения."),
)


def explain_error(text):
    seen = []
    for pat, hint in HINTS:
        if re.search(pat, text or "", re.I) and hint not in seen:
            seen.append(hint)
    return seen


def fatal_error(text):
    """Нет связи, нет сессии или аккаунт заблокирован: следующие приложения пакета упадут так же."""
    return any(re.search(p, text or "", re.I) for p in (NET_ERROR, ACCOUNT_LOCKED, NO_SESSION))


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

# запущенные ipatool и установщик: {процесс: метка}. Без этого «Остановить» не может прервать скачивание,
# а после закрытия окна процессы остаются работать (на Windows дочерний процесс не завершается с родителем).
_PROCS, _PROCS_LOCK = {}, threading.Lock()
_CLOSED = False  # программа закрывается: новых процессов не запускаем (кроме уборки сессии, tag="wipe")


class ProcsClosed(OSError):
    """Программа закрывается — процесс не запущен."""


def popen(cmd, tag="", **kw):
    """subprocess.Popen с учётом в _PROCS; tag="task" — основная операция (её прерывает «Остановить»).

    Запуск и учёт — под одной блокировкой: kill_procs не может проскочить между ними, а после close_procs
    поток, ещё не узнавший о закрытии, не запустит ipatool, переживающий программу."""
    with _PROCS_LOCK:
        if _CLOSED and tag != "wipe":
            raise ProcsClosed("программа закрывается")
        p = subprocess.Popen(cmd, creationflags=NO_WINDOW, **kw)
        _PROCS[p] = tag
    return p


def forget(p):
    with _PROCS_LOCK:
        _PROCS.pop(p, None)


def kill_procs(tag=None):
    """Завершить запущенные процессы: с меткой tag или все (tag=None — при закрытии программы)."""
    with _PROCS_LOCK:
        procs = [p for p, t in _PROCS.items() if tag is None or t == tag]
    for p in procs:
        with contextlib.suppress(OSError):  # уже завершился
            p.kill()


def close_procs():
    """При закрытии программы: завершить все процессы и не запускать новых (кроме tag="wipe")."""
    global _CLOSED
    with _PROCS_LOCK:
        _CLOSED = True
    kill_procs()


def clear_stale_locks():
    """Удалить *.lock в основной сессии. Звать, только когда в ней точно не работает ipatool (под dlock):
    lock-файлы остаются от убитых процессов — после «Остановить» или аварийного завершения."""
    for stale in (core.IPATOOL_HOME / ".ipatool").glob("*.lock"):
        with contextlib.suppress(OSError):
            stale.unlink()


def run_quiet(cmd, timeout=90, env=None, tag=""):
    """Запуск без построчного журнала: (код возврата, весь вывод без цветовых кодов)."""
    try:
        p = popen(cmd, tag=tag, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                  encoding="utf-8", errors="replace",
                  env=env if env is not None else (core.ipatool_env() if core.is_ipatool(cmd) else None))
    except ProcsClosed:
        return 1, "программа закрывается"
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        return 124, "timeout"
    finally:
        forget(p)
    return p.returncode, ANSI.sub("", (out or "") + (err or ""))


def in_session_copies(items, fn, workers, lock=None):
    """fn(item, env) для каждого item в нескольких потоках: запрос к Apple ждёт сеть 1–2 с, так быстрее.

    ipatool хранит сессию и cookies в ~/.ipatool, и параллельные процессы портят общие файлы (падение
    с panic), поэтому у каждого потока своя копия сессии во временной папке внутри SCAN_ROOT; env — окружение
    с этой папкой. Копии удаляются в конце (и при следующем запуске программы, если она упала — см. wipe_session).
    lock — блокировка основной сессии: копируем её, только когда ipatool в неё не пишет.
    """
    items = list(items)
    if not items:
        return
    n = max(1, min(workers, len(items)))
    src_dir = core.IPATOOL_HOME / ".ipatool"
    SCAN_ROOT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(dir=SCAN_ROOT))
    envs = queue.Queue()
    try:
        with lock or contextlib.nullcontext():
            clear_stale_locks()  # остались от аварийно завершённых процессов
            for w in range(n):
                h = root / f"w{w}"
                h.mkdir()
                if src_dir.exists():
                    shutil.copytree(src_dir, h / ".ipatool", ignore=shutil.ignore_patterns("*.lock"))
                envs.put(core.ipatool_env(h))

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


def scan_copies():
    """Папки с копиями сессии от in_session_copies, в том числе оставшиеся после сбоя (и от версий до 1.1.0)."""
    found = list(SCAN_ROOT.glob("*")) if SCAN_ROOT.is_dir() else []
    return found + list(Path(tempfile.gettempdir()).glob("restore_scan_*"))


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
            versions.update(str(x) for x in obj["externalVersionIdentifiers"] if str(x).isdigit())
    return sorted(versions, key=int, reverse=True)


def clip(text, limit=700, head=450, tail=250):
    """Длинный ответ ipatool для журнала: начало и конец; пустой — «(пустой ответ)»."""
    t = (text or "").strip()
    return (t if len(t) <= limit else t[:head] + "\n …\n" + t[-tail:]) or "(пустой ответ)"
