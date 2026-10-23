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

    // файлы — строками в одном белом блоке, как списки приложений (блок по высоте строк, см. AppsList)
    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.topMargin: 4
        Rectangle {
            width: parent.width
            height: Math.min(parent.height, files.count * 62 + 8)
            visible: files.count > 0
            radius: 16
            color: P.card

            ListView {
                id: files
                anchors.fill: parent
                anchors.margins: 4
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: backend.ipaFiles
                ScrollBar.vertical: ThinScrollBar {}
                delegate: Rectangle {
                    id: row
                    required property int index
                    required property string path
                    required property string title
                    required property string info
                    required property string letter
                    required property string tint
                    required property string icon
                    width: ListView.view.width - 10
                    height: 62; radius: 10
                    color: rowHover.hovered ? P.cardHover : P.card
                    Behavior on color { ColorAnimation { duration: 110 } }
                    HoverHandler { id: rowHover }
                    Rectangle {
                        visible: row.index < files.count - 1 && !rowHover.hovered
                        anchors.bottom: parent.bottom
                        x: 14 + 40 + 12
                        width: parent.width - x - 12; height: 1
                        color: P.border
                    }
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 10
                        spacing: 12
                        AppIcon { icon: row.icon; letter: row.letter; tint: row.tint; size: 40 }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 1
                            Text { textFormat: Text.PlainText; text: row.title; color: P.text; font.family: P.font; font.pixelSize: 14
                                   font.weight: Font.DemiBold; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            Text { text: row.info; color: P.muted; font.family: P.font; font.pixelSize: 12 }
                        }
                        Btn { text: "Установить"; kind: "ghost"; implicitHeight: 34; onClicked: backend.installIpa(row.path) }
                    }
                }
            }
        }
        Empty { visible: files.count === 0; title: "Здесь появятся скачанные .ipa"
                sub: "Скачайте приложение или выберите файл с диска." }
    }
}
