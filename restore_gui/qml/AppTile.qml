// Плитка «Популярного» на главной.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: tile
    required property int index
    required property var appId
    required property string title
    required property string letter
    required property string tint
    required property string icon
    required property string status
    required property string statusKind
    required property bool selected
    required property string copies

    radius: 18
    color: hover.hovered ? P.cardHover : P.card
    border.color: selected ? P.accent : P.border
    border.width: selected ? 2 : 1
    scale: tap.pressed ? 0.98 : (hover.hovered ? 1.01 : 1)
    Behavior on color { ColorAnimation { duration: 120 } }
    Behavior on scale { NumberAnimation { duration: 120 } }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: backend.openDetail("popular", tile.index) }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            AppIcon { icon: tile.icon; letter: tile.letter; tint: tile.tint; size: 46 }
            Item { Layout.fillWidth: true }
            CheckDot { Layout.alignment: Qt.AlignTop; checked: tile.selected
                       onToggled: backend.toggleSelected("popular", tile.index) }
        }
        Item { Layout.fillHeight: true }
        Text { text: tile.title; color: P.text; font.family: P.font; font.pixelSize: 14; font.bold: true
               elide: Text.ElideRight; Layout.fillWidth: true }
        Text {
            Layout.fillWidth: true
            elide: Text.ElideRight
            font.family: P.font; font.pixelSize: 11
            color: tile.statusKind === "ok" ? P.ok : P.muted
            text: (tile.status !== "" ? tile.status : "Открыть") + (tile.copies !== "" ? " · " + tile.copies : "")
        }
    }
}
