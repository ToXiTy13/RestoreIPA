// Главная: путь из трёх шагов (Apple ID → iPhone → найти свои приложения) и популярное сеткой иконок.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: home
    signal helpRequested()
    spacing: 14

    ColumnLayout {
        spacing: 2
        Text { text: backend.greeting; color: P.accentText; font.family: P.font; font.pixelSize: 13
               font.weight: Font.DemiBold }
        Text { text: "Вернём удалённые приложения"; color: P.text; font.family: P.font; font.pixelSize: 28
               font.weight: Font.ExtraBold }
        Text { text: "Restore находит в истории вашего Apple ID приложения, которые пропали из App Store, и ставит их обратно на iPhone."
               color: P.muted; font.family: P.font; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }

    // ---------- три шага ----------
    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 6
        spacing: 12

        Step {
            number: 1
            done: backend.loggedIn
            title: "Apple ID"
            sub: backend.loggedIn ? backend.account : "войдите в аккаунт, где были приложения"
            onClicked: backend.openLogin("")
        }
        Step {
            number: 2
            done: backend.deviceState === "ok"
            warn: backend.deviceState === "trust"
            title: "iPhone"
            sub: backend.deviceState === "none" ? "подключите кабелем и нажмите «Доверять»" : backend.deviceText
            onClicked: home.helpRequested()
        }
        Step {
            number: 3
            main: true
            title: "Найти мои приложения"
            sub: "проверим историю Apple ID →"
            onClicked: backend.findMine()
        }
    }

    // ---------- популярное ----------
    RowLayout {
        Layout.topMargin: 12
        Text { text: "Популярное"; color: P.text; font.family: P.font; font.pixelSize: 17; font.weight: Font.Bold }
        Item { Layout.fillWidth: true }
        Text {
            text: "Весь каталог →"; color: allHover.hovered ? P.accent : P.accentText; font.family: P.font
            font.pixelSize: 13; font.weight: Font.DemiBold
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
        readonly property int cols: Math.max(4, Math.floor(width / 128))
        cellWidth: Math.floor(width / cols)
        cellHeight: 136
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ThinScrollBar {}
        delegate: Item {
            id: cell
            required property int index
            required property var model
            width: grid.cellWidth; height: grid.cellHeight
            AppTile {
                anchors.fill: parent; anchors.margins: 4
                index: cell.index
                appId: cell.model.appId; title: cell.model.title; letter: cell.model.letter
                tint: cell.model.tint; icon: cell.model.icon; status: cell.model.status
                statusKind: cell.model.statusKind; selected: cell.model.selected; copies: cell.model.copies
            }
        }
    }

    // шаг пути: номер или ✓, заголовок и пояснение; main — главный шаг, залит акцентом
    component Step: Rectangle {
        id: step
        property int number: 1
        property bool done: false
        property bool warn: false
        property bool main: false
        property string title: ""
        property string sub: ""
        signal clicked()
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        implicitHeight: 92
        radius: 18
        color: main ? (stepHover.hovered ? P.accentHover : P.accent) : (stepHover.hovered ? P.cardHover : P.card)
        border.color: main ? "transparent" : (done ? P.okDim : P.border)
        scale: stepTap.pressed ? 0.98 : 1
        Behavior on color { ColorAnimation { duration: 130 } }
        Behavior on scale { NumberAnimation { duration: 90 } }
        HoverHandler { id: stepHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { id: stepTap; onTapped: step.clicked() }

        RowLayout {
            anchors.fill: parent; anchors.margins: 16
            spacing: 14
            Rectangle {
                width: 38; height: 38; radius: 19
                color: step.main ? Qt.rgba(1, 1, 1, 0.2) : step.done ? P.okBg : step.warn ? P.warnDim : P.second
                Text {
                    anchors.centerIn: parent
                    text: step.done ? "✓" : step.number
                    color: step.main ? "white" : step.done ? P.ok : step.warn ? P.warn : P.muted
                    font.family: P.font; font.pixelSize: 16; font.weight: Font.ExtraBold
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: step.title; color: step.main ? "white" : P.text; font.family: P.font; font.pixelSize: 15
                       font.weight: Font.Bold; elide: Text.ElideRight; Layout.fillWidth: true }
                Text { textFormat: Text.PlainText; text: step.sub; color: step.main ? Qt.rgba(1, 1, 1, 0.85) : step.warn ? P.warn : P.muted
                       font.family: P.font; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
            }
        }
    }
}
