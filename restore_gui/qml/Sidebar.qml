// Боковая панель: логотип, разделы, вход в Apple ID и ссылки.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: side
    signal helpRequested()
    signal settingsRequested()
    signal supportRequested()
    color: P.rail

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 2

        RowLayout {
            spacing: 10
            Layout.bottomMargin: 24
            Layout.leftMargin: 2
            Logo { size: 40 }
            Column {
                Text { text: "Restore"; color: P.text; font.family: P.font; font.pixelSize: 17; font.bold: true }
                Text { text: "для iPhone"; color: P.muted; font.family: P.font; font.pixelSize: 11 }
            }
        }

        Repeater {
            model: [["home", "Главная", "⌂"], ["apps", "Все приложения", "☰"], ["mine", "Мои удалённые", "↺"],
                    ["ipa", "Файлы .ipa", "▤"]]
            delegate: Rectangle {
                id: nav
                required property var modelData
                readonly property bool current: backend.page === modelData[0]
                Layout.fillWidth: true
                height: 42; radius: 10
                color: current ? P.card : (navHover.hovered ? "#1b1b21" : "transparent")
                Behavior on color { ColorAnimation { duration: 120 } }
                Rectangle { width: 3; height: nav.current ? 20 : 0; radius: 2; color: P.accent; x: 4
                            anchors.verticalCenter: parent.verticalCenter
                            Behavior on height { NumberAnimation { duration: 150 } } }
                Text { x: 16; anchors.verticalCenter: parent.verticalCenter; text: nav.modelData[2]
                       color: nav.current ? P.accentText : P.muted; font.pixelSize: 15; width: 18
                       horizontalAlignment: Text.AlignHCenter }
                Text { x: 44; anchors.verticalCenter: parent.verticalCenter; text: nav.modelData[1]
                       color: nav.current ? P.text : P.muted; font.family: P.font; font.pixelSize: 14
                       font.bold: nav.current }
                HoverHandler { id: navHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: backend.showPage(nav.modelData[0]) }
            }
        }

        Item { Layout.fillHeight: true }

        Btn {
            visible: backend.supportUrl !== ""
            text: "♡ Поддержать разработчика"
            kind: "ghost"; lock: false; implicitHeight: 34; leftPadding: 6; rightPadding: 6
            Layout.fillWidth: true; Layout.bottomMargin: 10
            onClicked: side.supportRequested()
        }
        Text {
            Layout.fillWidth: true; Layout.leftMargin: 6; Layout.bottomMargin: 8
            text: backend.loggedIn ? "Apple ID\n" + backend.account : "Вход не выполнен"
            color: backend.loggedIn ? P.text : P.muted
            font.family: P.font; font.pixelSize: 12; elide: Text.ElideRight
        }
        Btn {
            visible: !backend.loggedIn
            text: "Войти в Apple ID"; kind: "primary"; lock: false; implicitHeight: 40
            Layout.fillWidth: true
            onClicked: backend.openLogin("")
        }
        Btn {
            visible: backend.loggedIn
            text: "Выйти"; kind: "danger"; lock: false; implicitHeight: 34
            Layout.fillWidth: true
            onClicked: backend.logout()
        }
        RowLayout {
            Layout.topMargin: 12
            spacing: 14
            Repeater {
                model: ["Справка", "Настройки", "Связь"]
                delegate: Text {
                    required property string modelData
                    text: modelData
                    color: linkHover.hovered ? P.text : P.muted
                    font.family: P.font; font.pixelSize: 12
                    HoverHandler { id: linkHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: modelData === "Справка" ? side.helpRequested()
                                : modelData === "Настройки" ? side.settingsRequested() : backend.netCheck()
                    }
                }
            }
        }
    }
}
