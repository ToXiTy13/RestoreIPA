// Поле ввода в стиле программы.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

TextField {
    id: f
    Layout.fillWidth: true
    implicitHeight: 46
    leftPadding: 14; rightPadding: 14
    color: P.text
    placeholderTextColor: P.muted
    selectionColor: P.accent
    font.family: P.font; font.pixelSize: 14
    background: Rectangle {
        radius: 12; color: f.activeFocus ? P.card : P.rail
        border.color: f.activeFocus ? P.accent : P.border
        border.width: f.activeFocus ? 2 : 1
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }
}
