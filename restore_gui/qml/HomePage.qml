// Главная: приветствие, состояние iPhone и Apple ID, кнопка поиска своих приложений, популярные.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: home
    signal helpRequested()
    spacing: 14

    PageTitle { title: backend.greeting; sub: "Вернём на iPhone приложения, которые пропали из App Store." }

    RowLayout {
        spacing: 8
        Repeater {
            model: 2
            delegate: Rectangle {
                id: chip
                required property int index
                readonly property bool isDevice: index === 0
                readonly property string state_: isDevice ? backend.deviceState : (backend.loggedIn ? "ok" : "login")
                height: 34; radius: 17
                width: chipText.implicitWidth + 30
                color: chipHover.hovered ? P.cardHover : P.card
                border.color: state_ === "ok" ? P.okDim : state_ === "trust" ? P.warnDim
                            : state_ === "login" ? P.accentDim : P.border
                Behavior on color { ColorAnimation { duration: 120 } }
                Text {
                    id: chipText
                    anchors.centerIn: parent
                    font.family: P.font; font.pixelSize: 12
                    color: chip.state_ === "ok" ? P.ok : chip.state_ === "trust" ? P.warn
                         : chip.state_ === "login" ? P.accentText : P.muted
                    text: (chip.state_ === "ok" ? "●  " : chip.state_ === "trust" ? "!  " : "○  ")
                          + (chip.isDevice ? backend.deviceText
                             : backend.loggedIn ? backend.account : "Войти в Apple ID")
                }
                HoverHandler { id: chipHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: chip.isDevice ? home.helpRequested() : backend.openLogin("") }
            }
        }
    }

    Rectangle {
        id: banner
        Layout.fillWidth: true
        Layout.preferredHeight: 96
        radius: 18
        scale: bannerTap.pressed ? 0.99 : 1
        Behavior on scale { NumberAnimation { duration: 90 } }
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: bannerHover.hovered ? Qt.lighter(P.grad1, 1.08) : P.grad1 }
            GradientStop { position: 1; color: bannerHover.hovered ? Qt.lighter(P.grad2, 1.08) : P.grad2 }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            x: 24
            spacing: 4
            Text { text: "Найти мои удалённые приложения"; color: "white"; font.family: P.font
                   font.pixelSize: 19; font.bold: true }
            Text { text: "Проверим историю вашего Apple ID и покажем, что можно вернуть"; color: "#e4e1ff"
                   font.family: P.font; font.pixelSize: 13 }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right; anchors.rightMargin: bannerHover.hovered ? 20 : 26
            Behavior on anchors.rightMargin { NumberAnimation { duration: 150 } }
            text: "→"; color: "white"; font.pixelSize: 26; font.bold: true
        }
        HoverHandler { id: bannerHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { id: bannerTap; onTapped: backend.findMine() }
    }

    RowLayout {
        Layout.topMargin: 8
        Text { text: "Популярное"; color: P.text; font.family: P.font; font.pixelSize: 16; font.bold: true }
        Item { Layout.fillWidth: true }
        Text {
            text: "Все приложения →"; color: allHover.hovered ? P.text : P.accentText; font.family: P.font
            font.pixelSize: 12
            HoverHandler { id: allHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: backend.showPage("apps") }
        }
    }

    GridView {
        id: grid
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: backend.popular
        readonly property int cols: 4
        cellWidth: Math.floor((width - 10) / cols)
        cellHeight: 142
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ThinScrollBar {}
        delegate: Item {
            id: cell
            required property int index
            required property var model
            width: grid.cellWidth; height: grid.cellHeight
            AppTile {
                anchors.fill: parent; anchors.margins: 5
                index: cell.index
                appId: cell.model.appId; title: cell.model.title; letter: cell.model.letter
                tint: cell.model.tint; icon: cell.model.icon; status: cell.model.status
                statusKind: cell.model.statusKind; selected: cell.model.selected; copies: cell.model.copies
            }
        }
    }
}
