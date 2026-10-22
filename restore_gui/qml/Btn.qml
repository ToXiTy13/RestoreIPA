// Кнопка программы. kind: primary (главное действие), second, ghost (как ссылка), danger.
// lock — блокировать, пока идёт долгая операция (backend.busy).
import QtQuick
import QtQuick.Controls

Button {
    id: b
    property string kind: "second"
    property bool lock: true
    property int radius: 12
    enabled: !(lock && backend.busy)
    implicitHeight: 40
    leftPadding: 18; rightPadding: 18
    hoverEnabled: true
    font.family: P.font
    font.pixelSize: kind === "primary" ? 14 : 13
    font.bold: kind === "primary"
    scale: down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: 80 } }

    contentItem: Text {
        text: b.text
        font: b.font
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: !b.enabled ? (b.kind === "primary" ? "#9b93d9" : P.disabled)
             : b.kind === "primary" ? "white"
             : b.kind === "ghost" ? P.accentText
             : b.kind === "danger" ? P.danger : P.text
    }
    background: Rectangle {
        radius: b.radius
        color: b.kind === "primary" ? (!b.enabled ? P.accentDim : b.hovered ? P.accentHover : P.accent)
             : b.kind === "second" ? (b.hovered ? P.secondHover : P.second)
             : b.kind === "danger" ? (b.hovered ? P.dangerBg : "transparent")
             : (b.hovered ? P.second : "transparent")
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    HoverHandler { cursorShape: b.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
