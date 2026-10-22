"""iPhone (подключение, установщик) и файлы .ipa. Без интерфейса."""
import plistlib
import re
import shutil
import zipfile


def probe_device(timeout=8):
    """Сведения о подключённом iPhone через встроенный pymobiledevice3, без отдельного процесса.

    {"ios": "17.5", "model": "iPhone 13", "name": "iPhone", "paired": bool} или None.
    """
    try:
        import asyncio
        from pymobiledevice3.lockdown import create_using_usbmux
    except Exception:  # noqa: BLE001 — модуль может отсутствовать при запуске из исходников
        return None

    async def go():
        ld = await create_using_usbmux(autopair=False)
        try:
            v = ld.all_values or {}
            return {"ios": v.get("ProductVersion"), "model": ld.display_name or v.get("ProductType"),
                    "name": v.get("DeviceName"), "paired": bool(getattr(ld, "paired", False))}
        finally:
            try:
                await ld.close()
            except Exception:  # noqa: BLE001
                pass

    try:
        return asyncio.run(asyncio.wait_for(go(), timeout))
    except Exception:  # noqa: BLE001 — нет устройства, нет драйвера, не доверено и т.п.
        return None


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)

def ipa_ok(path):
    try:
        with zipfile.ZipFile(path) as z:
            return any(n.startswith("Payload/") and n.endswith(".app/Info.plist") for n in z.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def ipa_info(ipa):
    """Info.plist приложения внутри IPA (CFBundleIdentifier, MinimumOSVersion, …) или {}."""
    try:
        with zipfile.ZipFile(ipa) as z:
            name = next(n for n in z.namelist()
                        if n.count("/") == 2 and n.startswith("Payload/") and n.endswith(".app/Info.plist"))
            return plistlib.loads(z.read(name))
    except (OSError, StopIteration, zipfile.BadZipFile, ValueError, plistlib.InvalidFileException):
        return {}


def installer_cmd(installer, action, ipa=None):
    """Команда установщика: action — "install" (ipa), "list" (установленные приложения) или "info" (сведения
    о телефоне). installer — ("builtin", [exe, "--pmd"]) | ("pymobiledevice3", путь) | ("ideviceinstaller", путь).
    None — у установщика нет такой команды."""
    kind, path = installer
    if kind in ("builtin", "pymobiledevice3"):
        base = list(path) if kind == "builtin" else [path]
        return base + {"install": ["apps", "install", str(ipa)], "list": ["apps", "list"],
                       "info": ["lockdown", "info"]}[action]
    if action == "install":
        return [path, "-i", str(ipa)]
    if action == "list":
        return [path, "-l"]
    info = shutil.which("ideviceinfo")  # у ideviceinstaller сведения о телефоне — отдельная программа
    return [info, "-k", "ProductVersion"] if info else None
