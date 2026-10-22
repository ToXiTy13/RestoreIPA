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
