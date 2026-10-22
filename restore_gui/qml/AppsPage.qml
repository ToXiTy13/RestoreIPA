// «Все приложения»: поиск, категории и весь каталог.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    spacing: 10

    PageTitle {
        title: "Все приложения"
        sub: "Поиск по названию, App ID или ссылке App Store. Отметьте несколько — поставим по очереди."
    }

    TextField {
        id: search
        Layout.fillWidth: true
        Layout.topMargin: 6
        implicitHeight: 46
        leftPadding: 44
        placeholderText: "Например: Сбербанк, 492224193 или ссылка apps.apple.com"
        placeholderTextColor: P.muted
        color: P.text
        selectionColor: P.accent
        font.family: P.font; font.pixelSize: 14
        onTextChanged: debounce.restart()
        Timer { id: debounce; interval: 180; onTriggered: { backend.setQuery(search.text); list.positionViewAtBeginning() } }
        background: Rectangle {
            radius: 14; color: P.card
            border.color: search.activeFocus ? P.accent : P.border
            border.width: search.activeFocus ? 2 : 1
            Behavior on border.color { ColorAnimation { duration: 150 } }
            Text { text: "⌕"; color: P.muted; font.pixelSize: 20; x: 16; anchors.verticalCenter: parent.verticalCenter }
            Text {
                visible: search.text !== ""
                text: "✕"; color: clearHover.hovered ? P.text : P.muted; font.pixelSize: 14
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                HoverHandler { id: clearHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: search.clear() }
            }
        }
    }

    ListView {
        Layout.fillWidth: true
        implicitHeight: 34
        orientation: ListView.Horizontal
        spacing: 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: backend.categories
        delegate: Rectangle {
            id: chip
            required property string modelData
            readonly property bool on: modelData === backend.category
            height: 32; radius: 16
            width: chipText.implicitWidth + 28
            color: on ? P.accent : (chipHover.hovered ? P.cardHover : P.card)
            border.color: on ? P.accent : P.border
            Behavior on color { ColorAnimation { duration: 150 } }
            Text { id: chipText; anchors.centerIn: parent; text: chip.modelData; font.family: P.font
                   font.pixelSize: 12; color: chip.on ? "white" : P.muted }
            HoverHandler { id: chipHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: { backend.setCategory(chip.modelData); list.positionViewAtBeginning() } }
        }
    }

    Text { text: "Найдено: " + list.count; color: P.muted; font.family: P.font; font.pixelSize: 12 }

    AppsList {
        id: list
        Layout.fillWidth: true
        Layout.fillHeight: true
        listName: "apps"
        model: backend.apps
        emptyTitle: "Ничего не нашлось"
        emptySub: "Попробуйте App ID или ссылку App Store."
    }
}
