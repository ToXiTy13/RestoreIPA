#!/usr/bin/env python3
"""
restore_apps.py — вернуть на iPhone приложения, удалённые из App Store.

Что делает: ищет приложение по названию/ID в таблице removed_ru_appstore_app_ids.csv,
скачивает IPA с серверов Apple через ipatool (под ВАШИМ Apple ID) и ставит на
iPhone по USB через pymobiledevice3 (или ideviceinstaller).

Важно: скачивание сработает только для приложений, которые уже есть в истории
покупок/загрузок этого Apple ID. Для чужих или никогда не скачанных приложений
Apple отдаст ошибку лицензии — обойти это скрипт не пытается.

Зависимости:
  ipatool          https://github.com/majd/ipatool/releases   (в PATH)
  pymobiledevice3  pip install pymobiledevice3                (или ideviceinstaller)

Примеры:
  python restore_apps.py search клик
  python restore_apps.py check 1660762523
  python restore_apps.py login
  python restore_apps.py download 1660762523
  python restore_apps.py restore "ДомКлик (ДКлик)"
"""
import argparse
import csv
import getpass
import json
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # собран PyInstaller'ом
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))  # встроенные ресурсы
HERE = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
_CSV = "removed_ru_appstore_app_ids.csv"
# CSV рядом с программой имеет приоритет над встроенным: его можно править
CATALOG = HERE / _CSV if (HERE / _CSV).exists() else BUNDLE / _CSV
__version__ = "1.0.1"
APP_NAME = "Restore"


def _data_dir():
    """Служебные файлы программы: отдельная папка, ничего не смешивается с другими программами."""
    if sys.platform.startswith("win"):
        import os
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / APP_NAME


def _writable(folder):
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


DATA_DIR = _data_dir()
# ipatool получает свою «домашнюю папку»: его сессия не трогает ~/.ipatool пользователя
IPATOOL_HOME = DATA_DIR / "ipatool-home"
# .ipa: у портативной версии — в папке «ipa» рядом с exe, у установленной — в «Документы\\Restore\\ipa»
INSTALLED = (HERE / "installed.txt").exists()  # файл кладёт установщик
OUT_DIR = HERE / "ipa" if (not INSTALLED and _writable(HERE / "ipa")) else Path.home() / "Documents" / APP_NAME / "ipa"
# пароль к зашифрованному файлу сессии; GUI задаёт случайный на каждый запуск и нигде его не хранит
SESSION_PASSPHRASE = None


# ---------- каталог ----------
def load_catalog():
    if not CATALOG.exists():
        return []
    with CATALOG.open(encoding="utf-8-sig", newline="") as f:
        return [{"id": int(r["app_id"]), "name": r["name"], "cat": (r.get("category") or "").strip()}
                for r in csv.DictReader(f)]


def search(query):
    q = query.casefold()
    return [a for a in load_catalog() if q in a["name"].casefold()]


def resolve(query):
    """'123456789' -> (id, имя); иначе поиск по названию (должен найтись ровно один)."""
    if query.isdigit():
        name = next((a["name"] for a in load_catalog() if a["id"] == int(query)), query)
        return int(query), name
    found = search(query)
    exact = [a for a in found if a["name"].casefold() == query.casefold()]
    if len(exact) == 1:
        found = exact
    if not found:
        sys.exit(f"Не нашёл «{query}» в каталоге. Укажите числовой App ID.")
    if len(found) > 1:
        lines = "\n".join(f"  {a['id']}  {a['name']}" for a in found[:25])
        sys.exit(f"Найдено несколько совпадений, уточните или укажите ID:\n{lines}")
    return found[0]["id"], found[0]["name"]


# ---------- вспомогательное ----------
def need(binary, hint):
    path = shutil.which(binary)
    if not path:
        sys.exit(f"Не найден «{binary}». {hint}")
    return path


SECRET_FLAGS = ("--password", "--keychain-passphrase")


def masked(cmd):
    """Команда для показа в журнале: значения паролей заменены на ***."""
    shown, mask = [], False
    for c in cmd:
        shown.append("***" if mask else shlex.quote(c))
        mask = c in SECRET_FLAGS
    return " ".join(shown)


def ipatool_env():
    """Окружение для ipatool: своя домашняя папка (на Windows ipatool берёт её из HOMEDRIVE+HOMEPATH)."""
    import os
    IPATOOL_HOME.mkdir(parents=True, exist_ok=True)
    drive, rest = os.path.splitdrive(str(IPATOOL_HOME))
    return dict(os.environ, HOME=str(IPATOOL_HOME), USERPROFILE=str(IPATOOL_HOME), HOMEDRIVE=drive,
                HOMEPATH=rest or "\\")


def is_ipatool(cmd):
    return bool(cmd) and Path(str(cmd[0])).stem.lower().startswith("ipatool")


def keychain_args():
    """Флаги ipatool для работы без консоли.

    ipatool хранит сессию в зашифрованном файле и на Windows спрашивает пароль к нему
    через терминал; у оконной программы терминала нет ("The handle is invalid").
    Поэтому пароль к хранилищу генерируется один раз, лежит в профиле пользователя
    и передаётся флагом. Это пароль ТОЛЬКО к локальному файлу сессии, не пароль Apple ID.
    """
    import os
    import secrets

    if SESSION_PASSPHRASE:
        return ["--keychain-passphrase", SESSION_PASSPHRASE, "--non-interactive"]
    folder = DATA_DIR
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / "keychain.pass"
    if not f.exists() or not f.read_text(encoding="utf-8").strip():
        f.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
    return ["--keychain-passphrase", f.read_text(encoding="utf-8").strip(), "--non-interactive"]


def run(cmd, capture=True):
    print("$ " + masked(cmd))
    return subprocess.run(cmd, capture_output=capture, text=True, env=ipatool_env() if is_ipatool(cmd) else None)


def slug(s):
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")[:60] or "app"


# ---------- команды ----------
def cmd_search(a):
    found = search(a.query)
    if not found:
        print("Ничего не найдено.")
        return 1
    for x in found[:100]:
        print(f"{x['id']:>12}  {x['name']}")
    if len(found) > 100:
        print(f"... и ещё {len(found) - 100}")
    return 0


def cmd_check(a):
    """Сверка ID через iTunes Lookup: жив ли в сторе, чей bundle id и разработчик."""
    app_id, name = resolve(a.app)
    print(f"{name} ({app_id})")
    for cc in a.countries.split(","):
        url = f"https://itunes.apple.com/lookup?id={app_id}&country={cc.strip()}"
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.load(r)
        except (urllib.error.URLError, ValueError) as e:
            print(f"  {cc}: ошибка запроса ({e})")
            continue
        if data.get("resultCount"):
            x = data["results"][0]
            print(f"  {cc}: ДОСТУПНО — {x.get('trackName')} | {x.get('bundleId')} | {x.get('sellerName')}")
        else:
            print(f"  {cc}: нет в сторе")
    return 0


def cmd_login(a):
    ipatool = need("ipatool", "Скачайте: https://github.com/majd/ipatool/releases")
    email = a.email or input("Apple ID (email): ").strip()
    password = getpass.getpass("Пароль Apple ID: ")
    code = a.code
    while True:
        cmd = [ipatool, *keychain_args(), "auth", "login", "--email", email, "--password", password]
        if code:
            cmd += ["--auth-code", code]
        r = run(cmd)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            print(out.strip() or "Вход выполнен.")
            return 0
        if not code and re.search(r"2fa|auth.?code|verification|two.?factor", out, re.I):
            code = input("Код двухфакторной аутентификации: ").strip()
            continue
        print(out.strip())
        return 1


def cmd_download(a):
    app_id, name = resolve(a.app)
    ipatool = need("ipatool", "Скачайте: https://github.com/majd/ipatool/releases")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{slug(name)}_{app_id}.ipa"
    cmd = [ipatool, *keychain_args(), "download", "-i", str(app_id), "-o", str(dest)]
    if a.purchase:
        cmd.append("--purchase")  # только для приложений, которые ещё продаются
    r = run(cmd)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0 or not dest.exists():
        print(out)
        print(
            "\nНе удалось скачать. Частые причины:\n"
            " • нет входа: сначала `login`;\n"
            " • приложения нет в истории покупок этого Apple ID (для удалённых это обязательно);\n"
            " • регион аккаунта не тот, под которым приложение скачивалось;\n"
            " • другая версия ipatool: проверьте `ipatool download --help`."
        )
        return 1
    print(f"Готово: {dest}")
    a.ipa = str(dest)
    return 0


def cmd_install(a):
    ipa = Path(a.ipa)
    if not ipa.exists():
        sys.exit(f"Файл не найден: {ipa}")
    pmd = shutil.which("pymobiledevice3")
    ideviceinstaller = shutil.which("ideviceinstaller")
    if pmd:
        cmd = [pmd, "apps", "install", str(ipa)]
    elif ideviceinstaller:
        cmd = [ideviceinstaller, "-i", str(ipa)]
    else:
        sys.exit("Нужен pymobiledevice3 (pip install pymobiledevice3) или ideviceinstaller.")
    print("Подключите iPhone по USB, разблокируйте и нажмите «Доверять».")
    r = run(cmd, capture=False)
    return r.returncode


def cmd_restore(a):
    rc = cmd_download(a)
    return rc if rc else cmd_install(a)


def main():
    p = argparse.ArgumentParser(description="Восстановление удалённых из App Store приложений")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="поиск в каталоге по названию")
    s.add_argument("query")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("check", help="проверить ID через iTunes Lookup")
    s.add_argument("app", help="App ID или название")
    s.add_argument("--countries", default="ru,kz,tr,us")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("login", help="войти в Apple ID через ipatool")
    s.add_argument("--email")
    s.add_argument("--code", help="код 2FA, если уже есть")
    s.set_defaults(fn=cmd_login)

    for name, fn, hlp in (("download", cmd_download, "скачать IPA"),
                          ("restore", cmd_restore, "скачать и установить")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("app", help="App ID или название из каталога")
        s.add_argument("--purchase", action="store_true",
                       help="получить лицензию (только для приложений, которые ещё в сторе)")
        s.set_defaults(fn=fn)

    s = sub.add_parser("install", help="установить готовый IPA на iPhone")
    s.add_argument("ipa")
    s.set_defaults(fn=cmd_install)

    a = p.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
