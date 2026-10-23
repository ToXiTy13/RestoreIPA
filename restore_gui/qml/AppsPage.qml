// «Каталог»: поиск, категории и все приложения.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    spacing: 10

    PageTitle {
        title: "Каталог"
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
            radius: height / 2; color: P.card
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

    // категории — текстовыми вкладками с подчёркиванием
    Item {
        Layout.fillWidth: true
        implicitHeight: 36
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: P.border }
        ListView {
            anchors.fill: parent
            orientation: ListView.Horizontal
            spacing: 22
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: backend.categories
            delegate: Item {
                id: cat
                required property string modelData
                readonly property bool on: modelData === backend.category
                height: 36
                width: catText.implicitWidth
                Text { id: catText; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -2
                       text: cat.modelData; font.family: P.font; font.pixelSize: 13
                       font.weight: cat.on ? Font.Bold : Font.Medium
                       color: cat.on ? P.text : (catHover.hovered ? P.text : P.muted) }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 3; radius: 1.5
                            color: P.accent; visible: cat.on }
                HoverHandler { id: catHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: { backend.setCategory(cat.modelData); list.positionViewAtBeginning() } }
            }
        }
    }

    Text { text: "Найдено: " + list.count; color: P.muted; font.family: P.font; font.pixelSize: 12
           Layout.topMargin: 4 }

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
