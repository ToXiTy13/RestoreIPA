# -*- mode: python ; coding: utf-8 -*-
# Сборка: build.ps1 (он же скачивает и проверяет ресурсы в build/res).
# Каталог и иконка — из репозитория; ipatool.exe, libunicorn.dll и лицензия Unicorn — из build\res.
# Всё кладётся в корень ресурсов (core.BUNDLE).
# Два варианта (RESTORE_ONEDIR):
#   0 — dist\RestoreAppStore.exe одним файлом (портативный): при каждом запуске распаковывается во временную папку;
#   1 — dist\RestoreAppStore\ папкой (для установщика): распаковывать нечего, запускается в разы быстрее.
import os
import re
import sys

from PyInstaller.utils.hooks import collect_all

ONEDIR = os.environ.get("RESTORE_ONEDIR") == "1"
MAC = sys.platform == "darwin"  # macOS: всегда Restore.app (папкой), ipatool для Mac, без Unicorn и ресурса версии

RES = "build/res"
datas = [("removed_ru_appstore_app_ids.csv", "."), ("assets/icon.ico", "."), ("assets/cloudtips_qr.png", "."),
         ("restore_gui/qml", "restore_gui/qml"),  # интерфейс (QML) — рядом с модулями пакета, см. app.QML_DIR
         ("restore_gui/fonts", "restore_gui/fonts")]  # шрифт Manrope и его лицензия OFL
if MAC:
    binaries = [(f"{RES}/ipatool", ".")]  # Unicorn ipatool нужен только на Windows
else:
    datas.append((f"{RES}/UNICORN_COPYING.txt", "."))
    binaries = [(f"{RES}/ipatool.exe", "."), (f"{RES}/libunicorn.dll", ".")]
# segno — QR-код в «Поддержать», если нет картинки; модули Qt ниже нужны QML и импортируются не из Python
hiddenimports = ["restore_apps", "segno", "PySide6.QtQuick", "PySide6.QtQuickControls2"]
# pymobiledevice3 встроен для режима `exe --pmd` (установка IPA); подмодули он грузит динамически.
# pytun_pmd3 — его зависимость с wintun.dll внутри пакета: без collect_all dll не попадает в сборку
# и `--pmd lockdown …` падает при импорте.
for pkg in ("pymobiledevice3", "pytun_pmd3"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["restore_apps_gui.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # pymobiledevice3 тянет консоль IPython (с jedi/parso — 5,5 тыс. файлов) и PyAV (видеокодеки, 64 МБ).
    # Оба импортируются лениво — только в `shell` и `serve-vnc`, которые программе не нужны.
    # Pillow ему нужен только для трансляции экрана в веб-инспекторе (cdp_screencast) — тоже не используется.
    # sslpsk_pmd3 (TLS-PSK для беспроводных туннелей iOS 17+) установке по кабелю не нужен, а на macOS везёт свой
    # старый libcrypto.3.dylib, который подменяет нужный cryptography (на Intel тот падает: нет EVP_DigestSqueeze)
    excludes=["IPython", "jedi", "parso", "traitlets", "av", "PIL"] + (["sslpsk_pmd3"] if MAC else []),
    noarchive=False,
)

# PyInstaller забирает почти весь Qt (браузер WebEngine — 194 МБ, 3D, мультимедиа, PDF, 2600 файлов QML-модулей).
# Интерфейсу нужны только QtQuick, Controls (стиль Basic), Layouts и Effects — остальное вырезаем.
# Если что-то нужное пропало, сборку остановит проверка `RestoreAppStore.exe --check-ui` в build.ps1.
DROP = re.compile(
    r"webengine|webview|webchannel|websockets|qt6?pdf|quick3d|qt3d|/3d|multimedia|spatialaudio|charts|datavis"
    r"|graphs|location|positioning|sensors|serialport|serialbus|bluetooth|nfc|remoteobjects|scxml|statemachine"
    r"|texttospeech|virtualkeyboard|designer|qt6?help|qt6?sql|qt6?test|opengl32sw|qtopengl|openglwidgets"
    r"|shadertools|httpserver|svgwidgets|uitools|lottie|bodymovin|particles|timeline|qtquick/dialogs|/labs/"
    r"|qtquick/controls/(fusion|imagine|material|universal|fluentwinui3|windows|macos|ios)"
    r"|quickcontrols2(fusion|imagine|material|universal|fluentwinui3|windowsstyle|macos|ios)"
    r"|qt6?(concurrent|dbus|printsupport|xml|networkauth|quickwidgets|quicktest|wayland|pdfwidgets)"
    r"|qt63d|quickdialogs|labs|nativestyle|/pdf/|scene2d|scene3d|localstorage|qt5compat|/tooling/"
    r"|vectorimage|quicklayouts?designer"
)

# на macOS QtGui ссылается на QtDBus, а модуль QtQuick — на QtOpenGL (на Windows ни то ни другое не нужно)
MAC_KEEP = re.compile(r"qtdbus|qtopengl(?!widgets)")


def needed(entry):
    dest = entry[0].replace("\\", "/").lower()
    if "/translations/" in dest:  # переводы Qt: оставляем только русский для стандартных окон
        return dest.endswith("qtbase_ru.qm")
    if MAC and MAC_KEEP.search(dest):
        return True
    if len(entry) > 2 and entry[2] == "SYMLINK":
        # на macOS у каждого фреймворка Qt есть ссылка вида «QtWebSockets» -> PySide6/…/QtWebSockets.framework;
        # если сам фреймворк вырезан, ссылка остаётся битой и ломает подпись .app — проверяем, куда она ведёт
        target = str(entry[1]).replace("\\", "/").lower()
        if "pyside6" in target and DROP.search(target) and not (MAC and MAC_KEEP.search(target)):
            return False
    return not ("pyside6" in dest and DROP.search(dest))


a.binaries = [e for e in a.binaries if needed(e)]
a.datas = [e for e in a.datas if needed(e)]
pyz = PYZ(a.pure)
common = dict(name="RestoreAppStore", icon="assets/icon.ico", version="build/version_info.txt", console=False,
              upx=False)
if MAC:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', open("restore_apps.py", encoding="utf-8").read()).group(1)
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RestoreAppStore", console=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="RestoreAppStore", upx=False)
    app = BUNDLE(coll, name="Restore.app", icon=f"{RES}/icon.icns", bundle_identifier="io.github.toxity13.restore",
                 version=VERSION,
                 info_plist={"CFBundleDisplayName": "Restore", "CFBundleShortVersionString": VERSION,
                             "CFBundleVersion": VERSION, "LSMinimumSystemVersion": "12.0",
                             "NSHighResolutionCapable": True,
                             "LSApplicationCategoryType": "public.app-category.utilities"})
elif ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, name="RestoreAppStore", upx=False)
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **common)
