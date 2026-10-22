// Иконка приложения: настоящая из App Store (скруглённая, как на iPhone) или первая буква на цветном фоне.
import QtQuick
import QtQuick.Effects

Item {
    id: root
    property string icon: ""
    property string letter: "?"
    property color tint: P.accent
    property int size: 42
    width: size; height: size
    readonly property real r: size * 0.26
    readonly property bool hasImage: icon !== "" && img.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: root.r
        color: root.tint
        visible: !root.hasImage
        Text {
            anchors.centerIn: parent
            text: root.letter
            color: "white"
            font.family: P.font
            font.pixelSize: root.size * 0.42
            font.bold: true
        }
    }
    Image {
        id: img
        anchors.fill: parent
        source: root.icon
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        smooth: true; mipmap: true
        sourceSize.width: root.size * 2; sourceSize.height: root.size * 2
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        layer.enabled: true  // скругление: clip в Qt режет только прямоугольником
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }
    }
    Rectangle { id: mask; anchors.fill: parent; radius: root.r; visible: false; layer.enabled: true }
}
