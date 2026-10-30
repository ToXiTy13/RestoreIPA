"""Запуск оконной программы: Qt Quick (QML в папке qml/) + Backend (backend.py)."""
import os
import sys
from pathlib import Path

QML_DIR = Path(__file__).resolve().parent / "qml"


def create(app, background=True, visible=True):
    """Окно и Backend в уже созданном QApplication: (engine, backend). engine.rootObjects() пуст — QML не загрузился.
    background=False, visible=False — для тестов: без фоновых потоков и без показа окна."""
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from PySide6.QtGui import QFontDatabase

    from .backend import Backend

    for ttf in sorted((Path(__file__).resolve().parent / "fonts").glob("*.ttf")):  # Manrope: все начертания
        QFontDatabase.addApplicationFont(str(ttf))
    backend = Backend(background=background)
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("P", backend.current_palette())  # палитра: P.card, P.accent …
    # сменили тему или акцент — QML пересчитает все привязки к P
    backend.paletteChanged.connect(lambda: ctx.setContextProperty("P", backend.current_palette()))
    ctx.setContextProperty("startVisible", visible)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine, backend


def qt_environment():
    """Настройки Qt, которые читаются при создании окна, — до QApplication. Заданные снаружи не трогаем."""
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")  # стиль Windows не даёт перекрашивать поля и полосы
    # Кадры — без flip-модели Direct3D 11 (рисует по-прежнему видеокарта). С flip-моделью драйвер NVIDIA
    # включает G-SYNC в оконном режиме и для окна программы: монитор подстраивает частоту под каждую анимацию
    # интерфейса, и экран мерцает. Без flip VRR не включается; плавность прокрутки та же.
    os.environ.setdefault("QT_D3D_NO_FLIP", "1")
    # Портативный exe при каждом запуске распаковывается в новую папку %TEMP%\_MEI…, а кэш скомпилированного QML
    # привязан к пути файла: у него кэш ни разу не пригождался и только рос. У установленной версии путь
    # постоянный — там кэш оставляем.
    if Path(getattr(sys, "_MEIPASS", "")).name.startswith("_MEI"):
        os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--pmd":  # режим установщика (pymobiledevice3)
        from pymobiledevice3.__main__ import main as pmd_main

        from .device import own_pmd_folder
        own_pmd_folder()
        sys.argv = ["pymobiledevice3"] + sys.argv[2:]
        sys.exit(int(pmd_main()))
    qt_environment()
    if "--check-ui" in sys.argv:  # проверка сборки: загрузить интерфейс без показа и выйти
        report = sys.argv[sys.argv.index("--check-ui") + 1]
        try:
            sys.exit(check_ui(report))
        except Exception:  # noqa: BLE001 — у exe без консоли ошибка иначе пропадёт (в т.ч. импорт Qt)
            import traceback
            Path(report).write_text("FAIL\n" + traceback.format_exc(), encoding="utf-8")
            sys.exit(1)

    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .apple import bundled

    app = QApplication(sys.argv)  # QApplication (а не QGuiApplication): системные окна выбора файла
    app.setApplicationName("Restore")
    tr = QTranslator(app)  # «Да»/«Нет» и «Открыть» в стандартных окнах Qt
    if tr.load(QLocale("ru_RU"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    ico = bundled("icon.ico")
    if ico:
        app.setWindowIcon(QIcon(ico))
    lock = single_instance()
    if lock is None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, "Restore", "Restore уже запущена — её окно открыто или ещё запускается.")
        sys.exit(0)
    engine, backend = create(app)
    if not engine.rootObjects():
        sys.exit("Не удалось загрузить интерфейс (qml/Main.qml).")
    app.aboutToQuit.connect(backend.shutdown)
    code = app.exec()
    lock.unlock()
    sys.exit(code)


def single_instance():
    """Замок «программа уже запущена» (QLockFile) или None, если его держит другой экземпляр.

    Второй экземпляр при запуске стёр бы сессию первого (уборка после прошлого запуска), а портативный exe
    распаковывается несколько секунд — двойной клик легко запускает два. Замок упавшего процесса QLockFile
    распознаёт по PID и снимает сам.
    """
    from PySide6.QtCore import QLockFile

    import restore_apps as core

    core.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(core.DATA_DIR / "restore.lock"))
    lock.setStaleLockTime(0)  # программа держит замок часами: по возрасту он не устаревает, только по PID
    return lock if lock.tryLock(0) else None


def check_ui(report):
    """Загрузить окно без показа и фоновых задач; в report — сообщения Qt. Код 0 — интерфейс цел."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    msgs = []
    # qt.qpa.fonts — подсказка Qt о подборе шрифтов (на macOS без экрана, при проверке сборки), не ошибка окна
    qInstallMessageHandler(lambda kind, ctx, text: msgs.append(text)
                           if kind != QtMsgType.QtDebugMsg and not str(ctx.category or "").startswith("qt.qpa.fonts")
                           else None)
    app = QApplication(sys.argv[:1])
    engine, _backend = create(app, background=False, visible=False)
    for _ in range(5):
        app.processEvents()
    import restore_apps as core
    if core.FROZEN:  # в сборке должен быть официальный ipatool (не та версия или сломана переподпись — ошибка)
        from .apple import bundled, ipatool_genuine
        tool = bundled("ipatool")
        if not tool or ipatool_genuine(tool) is False:
            msgs.append(f"Встроенный ipatool не совпадает с официальным (apple.IPATOOL_SHA256): {tool}")
    ok = bool(engine.rootObjects()) and not msgs
    Path(report).write_text(("OK" if ok else "FAIL") + "\n" + "\n".join(msgs), encoding="utf-8")
    return 0 if ok else 1
