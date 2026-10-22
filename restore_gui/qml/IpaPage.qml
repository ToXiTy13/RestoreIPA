// «Файлы .ipa»: поставить готовый файл; скачанное программой тоже здесь.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    spacing: 10

    PageTitle { title: "Файлы .ipa"; sub: "Поставить готовый файл без Apple ID. Скачанное программой тоже хранится здесь." }

    RowLayout {
        Layout.topMargin: 6
        spacing: 8
        Btn { text: "Выбрать .ipa с диска…"; kind: "primary"; onClicked: backend.installFile() }
        Btn { text: "Открыть папку"; lock: false; onClicked: backend.openFolder() }
    }
    Text { text: "Если файл скачан с чужого Apple ID, при первом запуске приложение попросит пароль того аккаунта."
           color: P.muted; font.family: P.font; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }

    ListView {
        id: files
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 6
        boundsBehavior: Flickable.StopAtBounds
        model: backend.ipaFiles
        ScrollBar.vertical: ThinScrollBar {}
        delegate: Rectangle {
            id: row
            required property string path
            required property string title
            required property string info
            required property string letter
            required property string tint
            required property string icon
            width: ListView.view.width - 14
            height: 64; radius: 14
            color: rowHover.hovered ? P.cardHover : P.card
            border.color: P.border
            Behavior on color { ColorAnimation { duration: 120 } }
            HoverHandler { id: rowHover }
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 12
                spacing: 12
                AppIcon { icon: row.icon; letter: row.letter; tint: row.tint; size: 40 }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 1
                    Text { text: row.title; color: P.text; font.family: P.font; font.pixelSize: 13
                           elide: Text.ElideMiddle; Layout.fillWidth: true }
                    Text { text: row.info; color: P.muted; font.family: P.font; font.pixelSize: 11 }
                }
                Btn { text: "Установить"; kind: "ghost"; implicitHeight: 34; onClicked: backend.installIpa(row.path) }
            }
        }
        Empty { visible: files.count === 0; title: "Здесь появятся скачанные .ipa"
                sub: "Скачайте приложение или выберите файл с диска." }
    }
}
