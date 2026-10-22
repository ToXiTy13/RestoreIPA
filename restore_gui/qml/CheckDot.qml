// Круглая галочка «выбрать для установки по очереди».
// MouseArea (а не TapHandler): она забирает нажатие себе, иначе срабатывает и строка вокруг — открывается приложение.
import QtQuick

Rectangle {
    id: c
    property bool checked: false
    signal toggled()
    width: 22; height: 22; radius: 11
    color: checked ? P.accent : "transparent"
    border.color: checked ? P.accent : (area.containsMouse ? P.muted : P.borderLight)
    border.width: 2
    Behavior on color { ColorAnimation { duration: 120 } }
    Text { anchors.centerIn: parent; text: "✓"; color: "white"; font.pixelSize: 13; font.bold: true; visible: c.checked }
    MouseArea {
        id: area
        anchors.fill: parent
        anchors.margins: -6  // попасть по маленькому кружку проще
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: c.toggled()
    }
}
