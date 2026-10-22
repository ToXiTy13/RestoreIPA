"""Ресурс версии для exe (свойства файла в Проводнике). Версия берётся из restore_apps.__version__.

Запуск: python tools\\write_version_info.py build\\version_info.txt
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
version = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "restore_apps.py").read_text(encoding="utf-8")).group(1)
nums = (tuple(int(x) for x in re.findall(r"\d+", version)) + (0, 0, 0, 0))[:4]

TEMPLATE = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041904B0', [
      StringStruct('CompanyName', 'Restore'),
      StringStruct('FileDescription', 'Restore — возврат удалённых из App Store приложений на iPhone'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'RestoreAppStore'),
      StringStruct('OriginalFilename', 'RestoreAppStore.exe'),
      StringStruct('ProductName', 'Restore'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [0x0419, 1200])])
  ]
)
"""

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(TEMPLATE, encoding="utf-8")
print(version)
