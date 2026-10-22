// Логотип: круг с градиентом и стрелкой «скачать» (как иконка программы).
import QtQuick

Rectangle {
    id: logo
    property int size: 40
    width: size; height: size; radius: size / 2
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: P.grad1 }
        GradientStop { position: 1; color: P.grad2 }
    }
    Canvas {
        anchors.fill: parent
        onPaint: {
            const c = getContext("2d"), s = width
            c.strokeStyle = "white"; c.lineWidth = Math.max(2, s * 0.08)
            c.lineCap = "round"; c.lineJoin = "round"
            c.beginPath()
            c.moveTo(s / 2, s * 0.27); c.lineTo(s / 2, s * 0.58)
            c.moveTo(s / 2 - s * 0.14, s * 0.45); c.lineTo(s / 2, s * 0.59); c.lineTo(s / 2 + s * 0.14, s * 0.45)
            c.moveTo(s * 0.32, s * 0.72); c.lineTo(s * 0.68, s * 0.72)
            c.stroke()
        }
    }
}
