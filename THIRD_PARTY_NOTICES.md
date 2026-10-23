# Сторонние компоненты

Готовая программа (`RestoreAppStore.exe` и установленная версия) включает следующие компоненты. Исходный код каждого доступен по ссылке.

| Компонент | Версия | Лицензия | Для чего | Исходники |
|---|---|---|---|---|
| ipatool | 2.7.0 | MIT | вход в Apple ID, список версий, скачивание IPA | https://github.com/majd/ipatool |
| Unicorn Engine (`libunicorn.dll`) | 2.1.4 | GPL-2.0 | нужен ipatool для подписи запросов при входе | https://github.com/unicorn-engine/unicorn |
| pymobiledevice3 | 11.41.2 | GPL-3.0-or-later | установка IPA на iPhone по USB | https://github.com/doronz88/pymobiledevice3 |
| pytun-pmd3 | 3.0.3 | GPL-3.0-or-later | зависимость pymobiledevice3 (сетевые туннели к iPhone) | https://github.com/doronz88/pytun-pmd3 |
| Wintun (`wintun.dll`, внутри pytun-pmd3) | — | Prebuilt Binaries License (WireGuard LLC), текст рядом с dll | драйвер туннеля для pytun-pmd3 | https://www.wintun.net |
| Qt for Python (PySide6) и библиотеки Qt 6 | 6.12.0 | LGPL-3.0 | интерфейс (Qt Quick) | https://code.qt.io/cgit/pyside/pyside-setup.git, https://code.qt.io |
| Шрифт Manrope | 0.4.2 (статические начертания) | SIL Open Font License 1.1 (`restore_gui/fonts/OFL.txt`) | шрифт интерфейса | https://github.com/googlefonts/manrope |
| segno | 1.6.6 | BSD-3-Clause | QR-код в окне «Поддержать разработчика» | https://github.com/heuer/segno |
| Python | 3.12 | PSF License | среда выполнения | https://www.python.org |
| PyInstaller (загрузчик) | 6.22.3 | GPL-2.0-or-later с исключением для сборок | упаковка в exe | https://github.com/pyinstaller/pyinstaller |

Плюс зависимости pymobiledevice3 и Python-пакеты, которые PyInstaller упаковывает вместе с ними; их лицензии — в соответствующих пакетах.

Полный текст лицензии Unicorn лежит внутри exe (`UNICORN_COPYING.txt`). Так как pymobiledevice3 распространяется под GPL-3.0, вся программа распространяется под [GPL-3.0](LICENSE).

Библиотеки Qt подключаются динамически: в установленной версии это отдельные файлы `Qt6*.dll` в папке `_internal\PySide6`, их можно заменить своей сборкой Qt той же версии (условие LGPL-3.0).

`ipatool` и `libunicorn.dll` при сборке скачиваются из официальных релизов на GitHub, SHA-256 сверяется (см. `build.ps1`).

## Каталог приложений

`removed_ru_appstore_app_ids.csv` собран из открытых списков удалённых приложений; источник каждой строки указан в колонке `src` (`back-to-iphone`, `IPA_Downloader`; `manual` — добавлено вручную по App ID).

| Список | Лицензия | Откуда |
|---|---|---|
| back-to-iphone (`app/catalog.json`) | GPL-3.0 | https://github.com/n0hard/back-to-iphone |
| IPA_Downloader (`Files/AppsList.txt`), © kda2495 | MIT | https://github.com/kda2495/IPA_Downloader |

Лицензия IPA_Downloader (условие MIT — сохранять этот текст):

```
MIT License

Copyright (c) 2025 kda2495

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
