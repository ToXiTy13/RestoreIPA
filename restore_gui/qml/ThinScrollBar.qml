// Тонкая полоса прокрутки: проявляется при наведении и прокрутке.
import QtQuick
import QtQuick.Controls

ScrollBar {
    id: sb
    policy: ScrollBar.AsNeeded
    visible: size < 1  // AsNeeded в Basic оставляет полосу на всю высоту, даже когда прокручивать нечего
    implicitWidth: 10
    contentItem: Rectangle {
        implicitWidth: 6
        radius: 3
        color: sb.pressed ? P.muted : P.borderLight
        opacity: sb.active || sb.hovered ? 1 : 0.35
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }
}
