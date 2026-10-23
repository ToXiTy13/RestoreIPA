// Заголовок страницы с подзаголовком.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    property string title: ""
    property string sub: ""
    Layout.fillWidth: true
    spacing: 2
    Text { text: parent.title; color: P.text; font.family: P.font; font.pixelSize: 28; font.weight: Font.ExtraBold }
    Text { text: parent.sub; color: P.muted; font.family: P.font; font.pixelSize: 13; visible: text !== ""
           wrapMode: Text.WordWrap; Layout.fillWidth: true }
}
