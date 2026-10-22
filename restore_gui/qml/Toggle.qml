// Переключатель в стиле программы.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Switch {
    id: s
    Layout.fillWidth: true
    font.family: P.font; font.pixelSize: 13
    indicator: Rectangle {
        x: s.leftPadding; anchors.verticalCenter: parent.verticalCenter
        width: 40; height: 22; radius: 11
        color: s.checked ? P.accent : P.second
        border.color: s.checked ? P.accent : P.borderLight
        Behavior on color { ColorAnimation { duration: 150 } }
        Rectangle {
            width: 16; height: 16; radius: 8; color: "white"
            anchors.verticalCenter: parent.verticalCenter
            x: s.checked ? parent.width - width - 3 : 3
            Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Text {
        text: s.text; font: s.font; color: P.text; wrapMode: Text.WordWrap
        leftPadding: s.indicator.width + 12; verticalAlignment: Text.AlignVCenter
    }
}
