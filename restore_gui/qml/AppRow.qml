// Строка списка приложений. listName — какой список (apps / mine): по нему Backend находит приложение.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: row
    required property int index
    required property var appId
    required property string title
    required property string sub
    required property string letter
    required property string tint
    required property string icon
    required property string status
    required property string statusKind
    required property bool selected
    property string listName: "apps"

    width: ListView.view ? ListView.view.width - 14 : 600
    height: 64
    radius: 14
    color: hover.hovered ? P.cardHover : P.card
    border.color: selected ? P.accent : P.border
    border.width: selected ? 2 : 1
    scale: tap.pressed ? 0.99 : 1
    Behavior on color { ColorAnimation { duration: 120 } }
    Behavior on scale { NumberAnimation { duration: 90 } }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: backend.openDetail(row.listName, row.index) }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 12
        CheckDot { checked: row.selected; onToggled: backend.toggleSelected(row.listName, row.index) }
        AppIcon { icon: row.icon; letter: row.letter; tint: row.tint }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Text { text: row.title; color: P.text; font.family: P.font; font.pixelSize: 14
                   elide: Text.ElideRight; Layout.fillWidth: true }
            Text { text: row.sub; color: P.muted; font.family: P.font; font.pixelSize: 11
                   visible: text.length > 0; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Rectangle {
            visible: row.status !== ""
            height: 24; radius: 12
            width: pill.implicitWidth + 20
            color: row.statusKind === "ok" ? P.okBg : P.second
            Text { id: pill; anchors.centerIn: parent; text: row.status; font.family: P.font; font.pixelSize: 11
                   color: row.statusKind === "ok" ? P.ok : P.muted }
        }
        Text { text: "›"; color: P.muted; font.pixelSize: 22 }
    }
}
