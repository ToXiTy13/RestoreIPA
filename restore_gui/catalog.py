"""Каталог удалённых приложений: категории, «семьи» копий под другими названиями, поиск. Без интерфейса."""
import re

# быстрый выбор: (подпись, App ID); показываются только те, что есть в каталоге
BANKS = (
    ("Сбербанк", 492224193), ("ВТБ", 472951966), ("Т-Банк", 455652438), ("Альфа-Банк", 353127685),
    ("Райффайзен", 557857165), ("Газпромбанк", 1406492297), ("Росбанк", 1438090038), ("Почта Банк", 979116495),
    ("МТС Банк", 1184367593), ("ПСБ", 548000415), ("Хоум Банк", 1061008282), ("ДомКлик", 1660762523),
    ("Госуслуги", 1367959794), ("MAX", 6739530834), ("Ozon", 407804998), ("Wildberries", 597880187),
)

CATEGORY_ORDER = ("Банки", "Инвестиции и бизнес", "Страхование", "Маркетплейсы", "Еда и продукты",
                  "Транспорт и путешествия", "Связь", "Госуслуги и документы", "Соцсети и мессенджеры",
                  "Видео и музыка", "ИИ и VPN", "Яндекс", "Сервисы", "Игры", "Прочее")
_CAT_MAP = {"Инвестиции": "Инвестиции и бизнес", "Для бизнеса": "Инвестиции и бизнес",
            "Транспорт и АЗС": "Транспорт и путешествия", "Игры Supercell": "Игры"}
_CAT_WORDS = (
    ("Яндекс", r"яндекс|yandex"),
    ("Банки", r"банк|bank|сбер|втб|альфа|тиньк|т-банк|халва|юmoney|qiwi|кошел"),
    ("Маркетплейсы", r"ozon|озон|wildberries|\bwb\b|мегамаркет|авито|avito|lamoda|ламода|detsky|детский мир|золотое"),
    ("Еда и продукты", r"еда|лавка|самокат|купер|вкусвилл|перекр|пят[её]р|магнит|лента|азбука|delivery|доставк|кофе|пицц"),
    ("Связь", r"мтс|билайн|мегафон|tele2|\bт2\b|yota|ростелеком"),
    ("Госуслуги и документы", r"госуслуг|налог|мос\.ру|пфр|соцфонд|электронн.*подпис|цифров.*подпис"),
    ("Транспорт и путешествия", r"такси|maxim|азс|ржд|аэро|туту|авиа|travel|метро|парков|каршер|самол"),
    ("Соцсети и мессенджеры", r"\bvk\b|вк |вконтакт|max|телеграм|одноклас|мессендж"),
    ("Видео и музыка", r"кино|видео|музык|ivi|okko|кинопоиск|wink|звук|premier"),
    ("ИИ и VPN", r"vpn|gpt|нейро|\bai\b|алиса"),
)


def categorize(name, cat):
    if cat:
        return _CAT_MAP.get(cat, cat)
    low = name.lower()
    for title, pat in _CAT_WORDS:
        if re.search(pat, low):
            return title
    return "Прочее"


def split_disguise(name):
    """«Альфа-Банк (Cashliner)» -> ("Альфа-Банк", "Cashliner"): банк, опубликованный под видом другого приложения."""
    m = re.match(r"^(.*?)\s*\((.+)\)\s*$", name)
    return (m.group(1), m.group(2)) if m else (name, None)


def family_key(name):
    """Ключ «семьи» в каталоге: оригинал и его копии под видом других приложений дают один ключ.

    «Альфа-Банк (Cashliner)» и «Альфа-Банк» -> «альфа-банк».
    """
    return re.sub(r"\s+", " ", split_disguise(name)[0]).strip().casefold().replace("ё", "е")


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def parse_app_ref(text):
    """App ID из числа или ссылки App Store (…/id123456789)."""
    t = (text or "").strip()
    m = re.search(r"apps\.apple\.com/.*?id(\d{6,12})", t) or re.fullmatch(r"(?:id)?(\d{6,12})", t)
    return int(m.group(1)) if m else None


class Catalog:
    """Приложения каталога [{"id", "name", "cat"}] и всё, что из них считается один раз при запуске."""

    def __init__(self, apps):
        self.apps = apps
        self.families = {}  # ключ семьи -> оригинал первым, затем копии по алфавиту
        for a in apps:
            a["cat"] = categorize(a["name"], a.get("cat", ""))
            self.families.setdefault(family_key(a["name"]), []).append(a)
        for fam in self.families.values():
            fam.sort(key=lambda a: (split_disguise(a["name"])[1] is not None,
                                    (split_disguise(a["name"])[1] or "").casefold()))
        self.byid = {a["id"]: a for a in apps}
        self.by_name = sorted(apps, key=lambda a: a["name"].casefold())
        self.categories = [c for c in CATEGORY_ORDER if any(a["cat"] == c for a in apps)]

    def search(self, text, extra=()):
        """Поиск по каталогу и приложениям extra (найденные покупки); число или ссылка App Store — по App ID."""
        q = text.strip().casefold()
        pool = dict(self.byid)
        for a in extra:
            pool.setdefault(a["id"], a)
        ref = parse_app_ref(text)
        if ref is not None:
            hit = pool.get(ref)
            return [hit] if hit else [{"id": ref, "name": f"Приложение {ref}", "adhoc": True}]
        items = [a for a in pool.values() if q in a["name"].casefold()]
        popular = {i for _t, i in BANKS}
        items.sort(key=lambda a: (a["id"] not in popular, not a["name"].casefold().startswith(q),
                                  "(" in a["name"], a["name"].casefold()))
        return items

    def popular(self):
        return [dict(self.byid[i], name=t) for t, i in BANKS if i in self.byid]

    def family(self, app):
        """Другие приложения той же семьи: оригинал первым, затем копии по алфавиту.

        Название берём из каталога: у плиток «Популярного» оно заменено коротким («Сбербанк»).
        """
        name = self.byid.get(app["id"], app).get("name")
        if not name:
            return []
        return [a for a in self.families.get(family_key(name), []) if a["id"] != app["id"]]

    def copies_note(self, app):
        n = len(self.family(app))
        return f" · +{n} {plural(n, 'копия', 'копии', 'копий')}" if n else ""
