// Список приложений (страницы «Все приложения» и «Мои удалённые») с заглушкой для пустого списка.
import QtQuick
import QtQuick.Controls

ListView {
    id: list
    property string listName: "apps"
    property string emptyTitle: ""
    property string emptySub: ""
    clip: true
    spacing: 6
    boundsBehavior: Flickable.StopAtBounds
    reuseItems: true
    ScrollBar.vertical: ThinScrollBar {}
    delegate: AppRow { listName: list.listName }

    Empty { visible: list.count === 0; title: list.emptyTitle; sub: list.emptySub }
}
