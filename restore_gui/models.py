"""Списки для QML: строки — словари, роли — их ключи. Модель хранит готовые строки и обновляет только
изменившиеся (QML перерисовывает лишь видимые строки, так что и обновление всего списка дёшево)."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal


class RowsModel(QAbstractListModel):
    """Список строк-словарей с заданным набором ключей. make_row(item) -> словарь строки (по умолчанию item)."""

    countChanged = Signal()

    def __init__(self, keys, make_row=None, key=None):
        super().__init__()
        self._roles = {Qt.UserRole + n: k.encode() for n, k in enumerate(keys)}
        self._by_name = {k: r for r, k in self._roles.items()}
        self.make_row = make_row or (lambda item: item)
        self.key = key  # item -> ключ для обновления отдельных строк (refresh_keys)
        self.items, self.rows, self.index_of = [], [], {}

    def roleNames(self):
        return self._roles

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        return self.rows[index.row()].get(self._roles.get(role, b"").decode())

    def set_items(self, items):
        self.beginResetModel()
        self.items = list(items)
        self.rows = [self.make_row(a) for a in self.items]
        self.index_of = {self.key(a): n for n, a in enumerate(self.items)} if self.key else {}
        self.endResetModel()
        self.countChanged.emit()

    def update_items(self, items):
        """Как set_items, но без сброса списка, когда строки только добавились, убрались или изменились:
        сброс модели прокручивает ListView к началу (так каждая находка поиска сбивала прокрутку «Мои»),
        а вставка и удаление строк — нет. Если порядок оставшихся строк другой, список пересобирается."""
        items = list(items)
        if not self.key:
            self.set_items(items)
            return
        old = [self.key(a) for a in self.items]
        new = [self.key(a) for a in items]
        old_set, new_set = set(old), set(new)
        if len(old_set) != len(old) or len(new_set) != len(new) \
                or [k for k in old if k in new_set] != [k for k in new if k in old_set]:
            self.set_items(items)
            return
        for n in range(len(old) - 1, -1, -1):  # с конца: номера ещё не удалённых строк не съезжают
            if old[n] not in new_set:
                self.beginRemoveRows(QModelIndex(), n, n)
                del self.items[n], self.rows[n]
                self.endRemoveRows()
        for n, (k, item) in enumerate(zip(new, items)):  # остались общие строки в нужном порядке
            row = self.make_row(item)
            if n < len(self.items) and self.key(self.items[n]) == k:
                self.items[n] = item
                if row != self.rows[n]:
                    self.rows[n] = row
                    self.dataChanged.emit(self.index(n), self.index(n))
            else:
                self.beginInsertRows(QModelIndex(), n, n)
                self.items.insert(n, item)
                self.rows.insert(n, row)
                self.endInsertRows()
        self.index_of = {k: n for n, k in enumerate(new)}
        if len(old) != len(new):
            self.countChanged.emit()

    def refresh_all(self):
        """Пересчитать строки, не сбрасывая список (прокрутка и выделение сохраняются)."""
        if not self.rows:
            return
        self.rows = [self.make_row(a) for a in self.items]
        self.dataChanged.emit(self.index(0), self.index(len(self.rows) - 1))

    def refresh_keys(self, keys):
        for k in keys:
            n = self.index_of.get(k)
            if n is not None:
                self.rows[n] = self.make_row(self.items[n])
                self.dataChanged.emit(self.index(n), self.index(n))
