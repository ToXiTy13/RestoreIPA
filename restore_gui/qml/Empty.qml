// Пустой список: заголовок и подсказка по центру.
import QtQuick

Column {
    property string title: ""
    property string sub: ""
    anchors.centerIn: parent
    spacing: 6
    Text { anchors.horizontalCenter: parent.horizontalCenter; text: parent.title; color: P.text
           font.family: P.font; font.pixelSize: 16; font.weight: Font.Bold }
    Text { anchors.horizontalCenter: parent.horizontalCenter; text: parent.sub; color: P.muted
           font.family: P.font; font.pixelSize: 12; visible: text !== "" }
}
