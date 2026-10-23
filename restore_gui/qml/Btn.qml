// Кнопка программы — «пилюля». kind: primary (главное действие), second, ghost (как ссылка), danger.
// lock — блокировать, пока идёт долгая операция (backend.busy).
import QtQuick
import QtQuick.Controls

Button {
    id: b
    property string kind: "second"
    property bool lock: true
    property real radius: height / 2
    enabled: !(lock && backend.busy)
    implicitHeight: 40
    leftPadding: 20; rightPadding: 20
    hoverEnabled: true
    font.family: P.font
    font.pixelSize: 13
    font.weight: kind === "primary" ? Font.Bold : Font.DemiBold
    scale: down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: 80 } }

    contentItem: Text {
        text: b.text
        font: b.font
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: !b.enabled ? P.disabled
             : b.kind === "primary" ? "white"
             : b.kind === "ghost" ? P.accentText
             : b.kind === "danger" ? P.danger : P.text
    }
    background: Rectangle {
        // цвет наведения у ghost/danger; без наведения — он же с нулевой прозрачностью: при переходе
        // из "transparent" (прозрачный чёрный) кнопка на мгновение темнеет
        readonly property color soft: b.kind === "danger" ? P.dangerBg : P.accentSoft
        radius: b.radius
        color: b.kind === "primary" ? (!b.enabled ? P.second : b.hovered ? P.accentHover : P.accent)
             : b.kind === "second" ? (b.hovered ? P.secondHover : P.second)
             : b.hovered ? soft : Qt.rgba(soft.r, soft.g, soft.b, 0)
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    HoverHandler { cursorShape: b.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
