// Всплывающее окно поверх главного: заголовок + содержимое (дочерние элементы кладутся в колонку).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: m
    property string title: ""
    default property alias content: body.data
    parent: Overlay.overlay
    anchors.centerIn: parent
    modal: true
    focus: true
    width: 460
    padding: 24
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle { color: "#99000000" }
    background: Rectangle { radius: 20; color: P.bg; border.color: P.border }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140 }
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 140; easing.type: Easing.OutCubic }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100 } }

    contentItem: ColumnLayout {
        spacing: 12
        Text { text: m.title; visible: text !== ""; color: P.text; font.family: P.font; font.pixelSize: 20
               font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        ColumnLayout { id: body; spacing: 12; Layout.fillWidth: true }
    }
}
