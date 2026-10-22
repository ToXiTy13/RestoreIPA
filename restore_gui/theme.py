"""Оформление: палитра, шрифт и размеры. Палитра тёмная «графит» с фиолетово-синим градиентом.
QML получает её словарём QML (Backend.palette) — цвета задаются только здесь."""

BG, RAIL, CARD, CARD_H, FIELD = "#111114", "#16161b", "#1c1c22", "#23232b", "#24242c"
BORDER, BORDER_LIGHT = "#2a2a33", "#4a4a56"
ACCENT, ACCENT_H, ACCENT_TX, ACCENT_DIM = "#6d5dfc", "#5b4ce0", "#a99fff", "#3b3570"
GRAD1, GRAD2 = "#6d5dfc", "#3b82f6"
SECOND, SECOND_H = "#24242c", "#2e2e38"
TEXT, MUTED, DISABLED_TX = "#f2f2f5", "#8d8d99", "#5a5a66"
OKC, OK_BG, OK_DIM = "#34d399", "#15302a", "#1f5a46"
WARN, WARN_DIM = "#fbbf24", "#5a4a1a"
DANGER, DANGER_BG = "#f87171", "#3a1f22"
AVATARS = ("#6d5dfc", "#3b82f6", "#10b981", "#f97316", "#ec4899", "#22c55e", "#0ea5e9", "#eab308")
FONT = "Segoe UI"

VERSIONS_PAGE = 15  # версий в панели за раз: для каждой видимой версии номер и дату спрашиваем у Apple

QML = {
    "bg": BG, "rail": RAIL, "card": CARD, "cardHover": CARD_H, "field": FIELD, "border": BORDER,
    "borderLight": BORDER_LIGHT, "accent": ACCENT, "accentHover": ACCENT_H, "accentText": ACCENT_TX,
    "accentDim": ACCENT_DIM, "grad1": GRAD1, "grad2": GRAD2, "second": SECOND, "secondHover": SECOND_H,
    "text": TEXT, "muted": MUTED, "disabled": DISABLED_TX, "ok": OKC, "okBg": OK_BG, "okDim": OK_DIM,
    "warn": WARN, "warnDim": WARN_DIM, "danger": DANGER, "dangerBg": DANGER_BG, "font": FONT,
}
