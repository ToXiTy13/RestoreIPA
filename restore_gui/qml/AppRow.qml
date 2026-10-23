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
    readonly property bool last: ListView.view ? index === ListView.view.count - 1 : true

    width: ListView.view ? ListView.view.width - 10 : 600
    height: 62
    radius: 10
    color: selected ? P.accentSoft : (hover.hovered ? P.cardHover : P.card)
    Behavior on color { ColorAnimation { duration: 110 } }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; onTapped: backend.openDetail(row.listName, row.index) }

    // разделитель — от начала текста до края, как в списках iOS; у выделенной/наведённой строки и последней не нужен
    Rectangle {
        visible: !row.last && !row.selected && !hover.hovered
        anchors.bottom: parent.bottom
        x: 14 + 22 + 12 + 42 + 12
        width: parent.width - x - 12; height: 1
        color: P.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 12
        CheckDot { checked: row.selected; onToggled: backend.toggleSelected(row.listName, row.index) }
        AppIcon {
            icon: row.icon; letter: row.letter; tint: row.tint
            scale: tap.pressed ? 0.94 : 1
            Behavior on scale { NumberAnimation { duration: 90 } }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Text { textFormat: Text.PlainText; text: row.title; color: P.text; font.family: P.font; font.pixelSize: 14; font.weight: Font.DemiBold
                   elide: Text.ElideRight; Layout.fillWidth: true }
            Text { textFormat: Text.PlainText; text: row.sub; color: P.muted; font.family: P.font; font.pixelSize: 12
                   visible: text.length > 0; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Text {
            visible: row.status !== ""
            textFormat: Text.PlainText
            text: row.status
            font.family: P.font; font.pixelSize: 12; font.weight: Font.DemiBold
            color: row.statusKind === "ok" ? P.ok : P.muted
        }
        Text { text: "›"; color: hover.hovered ? P.accentText : P.disabled; font.pixelSize: 22 }
    }
}
