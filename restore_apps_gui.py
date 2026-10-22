#!/usr/bin/env python3
"""
restore_apps_gui.py — оконная программа Restore (код — в пакете restore_gui, см. restore_gui/__init__.py).

Положите рядом: restore_apps.py и removed_ru_appstore_app_ids.csv.
Нужны: ipatool (в PATH или укажите файл), pymobiledevice3 или ideviceinstaller.
Запуск: python restore_apps_gui.py

Скачивание работает только для приложений из истории покупок вашего Apple ID.
"""
from restore_gui.app import main

if __name__ == "__main__":
    main()
