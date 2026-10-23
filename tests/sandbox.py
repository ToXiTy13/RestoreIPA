"""Тесты не трогают настоящие данные программы. Импортировать ДО restore_apps: пути к папкам программы
(%LOCALAPPDATA%\\Restore, профиль, %TEMP%) вычисляются при импорте. Иначе Backend() в тестах удалял бы
настоящие сессию и keychain.pass консольной версии, а проверки сессии — lock-файлы работающего ipatool
(build.ps1 запускает тесты при каждой сборке)."""
import atexit
import os
import shutil
import sys
import tempfile

ROOT = tempfile.mkdtemp(prefix="restore_tests_")
for var, sub in (("LOCALAPPDATA", "localappdata"), ("USERPROFILE", "home"), ("HOME", "home"),
                 ("TEMP", "temp"), ("TMP", "temp")):
    os.makedirs(os.path.join(ROOT, sub), exist_ok=True)
    os.environ[var] = os.path.join(ROOT, sub)
tempfile.tempdir = None  # gettempdir() возьмёт новый %TEMP%
assert "restore_apps" not in sys.modules, "sandbox нужно импортировать до restore_apps"
atexit.register(shutil.rmtree, ROOT, ignore_errors=True)
