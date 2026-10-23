"""Оформление: светлая и тёмная палитры, цвет акцента на выбор и шрифт Manrope (restore_gui/fonts, лицензия OFL).
QML получает палитру словарём (palette(), в QML — P): цвета задаются только здесь."""

FONT = "Manrope"
AVATARS = ("#6d5dfc", "#3b82f6", "#10b981", "#f97316", "#ec4899", "#22c55e", "#0ea5e9", "#eab308")

VERSIONS_PAGE = 15  # версий в панели за раз: для каждой видимой версии номер и дату спрашиваем у Apple

LIGHT = {
    # поверхности
    "bg": "#f3f5f4",          # фон окна
    "topbar": "#ffffff",      # верхняя панель
    "card": "#ffffff",        # карточки, списки, окна
    "cardHover": "#f2f6f4",
    "field": "#ffffff",       # поля ввода
    "second": "#edf1ef",      # второстепенные кнопки, подложка вкладок
    "secondHover": "#e2e8e5",
    "rail": "#f8faf9",        # журнал, поля во всплывающих окнах
    "border": "#e2e7e4",
    "borderLight": "#c4ccc8",
    "shade": "#5915181c",     # затемнение под всплывающими окнами
    # текст
    "text": "#15181c",
    "muted": "#68717a",
    "disabled": "#a6adb3",
    "logText": "#3a4148",
    # состояния
    "ok": "#0e9f6e", "okBg": "#dcf5ea", "okDim": "#a7e3c9",
    "warn": "#b45309", "warnDim": "#f3d9a6",
    "danger": "#dc2626", "dangerBg": "#fde4e4",
}

DARK = {
    "bg": "#0f1413",
    "topbar": "#151b19",
    "card": "#19201e",
    "cardHover": "#212a27",
    "field": "#19201e",
    "second": "#232b28",
    "secondHover": "#2d3733",
    "rail": "#141a18",
    "border": "#29322f",
    "borderLight": "#414c48",
    "shade": "#99000000",
    "text": "#e9eeec",
    "muted": "#94a19b",
    "disabled": "#59645f",
    "logText": "#c3cdc8",
    "ok": "#34d399", "okBg": "#123329", "okDim": "#1e5a44",
    "warn": "#f5a524", "warnDim": "#4a3913",
    "danger": "#f87171", "dangerBg": "#3a1b1b",
}

# цвет акцента: (название, светлая тема, тёмная тема). Ключи акцента: accent — кнопки и выделение,
# accentHover, accentText — ссылки и «призрачные» кнопки, accentDim — рамки выбранного, accentSoft — подсветка
# выбранного, grad1/grad2 — логотип и главный шаг.
ACCENTS = {
    "emerald": ("Изумрудный",
                {"accent": "#0e9f6e", "accentHover": "#0b8a5f", "accentText": "#0a7a55", "accentDim": "#bfe9d8",
                 "accentSoft": "#e6f6ef", "grad1": "#10b981", "grad2": "#0d9488"},
                {"accent": "#10a874", "accentHover": "#13bf85", "accentText": "#34d399", "accentDim": "#1e5a44",
                 "accentSoft": "#14302a", "grad1": "#10b981", "grad2": "#0d9488"}),
    "ocean": ("Морской",
              {"accent": "#0284c7", "accentHover": "#0369a1", "accentText": "#0369a1", "accentDim": "#bae0f5",
               "accentSoft": "#e5f3fb", "grad1": "#0ea5e9", "grad2": "#2563eb"},
              {"accent": "#0b8fd4", "accentHover": "#22a5ea", "accentText": "#5cc2f5", "accentDim": "#18486a",
               "accentSoft": "#122a3a", "grad1": "#0ea5e9", "grad2": "#2563eb"}),
    "rose": ("Малиновый",
             {"accent": "#db2777", "accentHover": "#be185d", "accentText": "#be185d", "accentDim": "#f8c7dd",
              "accentSoft": "#fdeaf3", "grad1": "#f43f5e", "grad2": "#db2777"},
             {"accent": "#e0397f", "accentHover": "#ec5b97", "accentText": "#f48fb8", "accentDim": "#5c1f3b",
              "accentSoft": "#33172a", "grad1": "#f43f5e", "grad2": "#db2777"}),
    "amber": ("Янтарный",
              {"accent": "#d97706", "accentHover": "#b45309", "accentText": "#b45309", "accentDim": "#f6dcae",
               "accentSoft": "#fdf3e1", "grad1": "#f59e0b", "grad2": "#ea580c"},
              {"accent": "#d97f0b", "accentHover": "#eb951f", "accentText": "#fbbf4d", "accentDim": "#5a3d12",
               "accentSoft": "#33260f", "grad1": "#f59e0b", "grad2": "#ea580c"}),
}
DEFAULT_ACCENT = "emerald"


def palette(dark=False, accent=DEFAULT_ACCENT):
    """Палитра для QML: поверхности и текст по теме + цвета выбранного акцента."""
    name, light_acc, dark_acc = ACCENTS.get(accent, ACCENTS[DEFAULT_ACCENT])
    return {"font": FONT, "dark": dark, **(DARK if dark else LIGHT), **(dark_acc if dark else light_acc)}


QML = palette()  # светлая с изумрудным акцентом — для скриптов и проверок, которым не нужен выбор
