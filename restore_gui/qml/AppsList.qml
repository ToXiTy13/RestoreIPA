// Список приложений (страницы «Каталог» и «Мои удалённые»): строки в одном белом блоке через разделители,
// с заглушкой для пустого списка. Занимает всё место на странице; короткий список — блок по высоте строк.
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property string listName: "apps"
    property string emptyTitle: ""
    property string emptySub: ""
    property alias model: list.model
    readonly property alias count: list.count
    function positionViewAtBeginning() { list.positionViewAtBeginning() }

    Rectangle {
        width: parent.width
        // высота по числу строк (62 — высота AppRow), а не по contentHeight: у ListView он приблизительный
        height: Math.min(parent.height, list.count * 62 + 8)
        visible: list.count > 0
        radius: 16
        color: P.card

        ListView {
            id: list
            anchors.fill: parent
            anchors.margins: 4
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            ScrollBar.vertical: ThinScrollBar {}
            delegate: AppRow { listName: root.listName }
        }
    }

    Empty { visible: list.count === 0; title: root.emptyTitle; sub: root.emptySub }
}
