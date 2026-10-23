// Приложение в «Популярном» — как значок на экране iPhone: иконка, подпись, состояние; без карточки.
// Галочка «выбрать» появляется у иконки при наведении и остаётся, если приложение выбрано.
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
    color: selected ? P.accentSoft : (hover.hovered ? P.card : P.bg)
    border.color: selected ? P.accentDim : (hover.hovered ? P.border : P.bg)
    Behavior on color { ColorAnimation { duration: 120 } }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: backend.openDetail("popular", tile.index) }

    ColumnLayout {
        anchors.centerIn: parent
        width: parent.width - 12
        spacing: 3
        Item {
            Layout.alignment: Qt.AlignHCenter
            width: 62; height: 62
            AppIcon {
                anchors.fill: parent
                icon: tile.icon; letter: tile.letter; tint: tile.tint; size: 62
                scale: tap.pressed ? 0.94 : (hover.hovered ? 1.05 : 1)
                Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
            CheckDot {
                visible: tile.selected || hover.hovered
                x: parent.width - width + 6; y: -6
                checked: tile.selected
                onToggled: backend.toggleSelected("popular", tile.index)
            }
        }
        Text { textFormat: Text.PlainText; text: tile.title; color: P.text; font.family: P.font; font.pixelSize: 13; font.weight: Font.Bold
               horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; Layout.fillWidth: true
               Layout.topMargin: 4 }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            font.family: P.font; font.pixelSize: 11; font.weight: Font.Medium
            color: tile.statusKind === "ok" ? P.ok : P.muted
            textFormat: Text.PlainText
            text: tile.status !== "" ? tile.status : (tile.copies !== "" ? tile.copies : "открыть")
        }
    }
}
