// Верхняя панель: логотип, разделы вкладками-«пилюлей», состояние iPhone, вход в Apple ID и меню «⋯».
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: bar
    signal helpRequested()
    signal settingsRequested()
    signal supportRequested()
    implicitHeight: 64
    color: P.topbar
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: P.border }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20; anchors.rightMargin: 16
        spacing: 18

        RowLayout {
            spacing: 10
            Logo { size: 32 }
            Text { text: "Restore"; color: P.text; font.family: P.font; font.pixelSize: 17; font.weight: Font.ExtraBold }
        }

        // разделы
        Rectangle {
            radius: height / 2
            color: P.second
            implicitHeight: 40
            implicitWidth: tabs.implicitWidth + 8
            Row {
                id: tabs
                anchors.centerIn: parent
                spacing: 2
                Repeater {
                    model: [["home", "Главная"], ["apps", "Каталог"], ["mine", "Мои удалённые"], ["ipa", "Файлы .ipa"]]
                    delegate: Rectangle {
                        id: tab
                        required property var modelData
                        readonly property bool current: backend.page === modelData[0]
                        height: 32; radius: 16
                        width: tabText.implicitWidth + 32
                        color: current ? P.card : P.second
                        border.color: current ? P.border : P.second
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Text {
                            id: tabText
                            anchors.centerIn: parent
                            text: tab.modelData[1]
                            font.family: P.font; font.pixelSize: 13
                            font.weight: tab.current ? Font.Bold : Font.Medium
                            color: tab.current || tabHover.hovered ? P.text : P.muted
                        }
                        HoverHandler { id: tabHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: backend.showPage(tab.modelData[0]) }
                    }
                }
            }
        }

        Item { Layout.fillWidth: true }

        // поддержать разработчика
        Btn {
            visible: backend.supportUrl !== ""
            text: "♡ Поддержать"; kind: "ghost"; lock: false; implicitHeight: 32
            leftPadding: 14; rightPadding: 14
            onClicked: bar.supportRequested()
        }

        // iPhone
        RowLayout {
            spacing: 6
            Rectangle {
                width: 8; height: 8; radius: 4
                color: backend.deviceState === "ok" ? P.ok : backend.deviceState === "trust" ? P.warn : P.borderLight
            }
            Text {
                textFormat: Text.PlainText
                text: backend.deviceText
                color: backend.deviceState === "trust" ? P.warn : P.muted
                font.family: P.font; font.pixelSize: 12; font.weight: Font.Medium
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: bar.helpRequested() }
            }
        }

        // Apple ID
        Btn {
            visible: !backend.loggedIn
            text: "Войти в Apple ID"; kind: "primary"; lock: false; implicitHeight: 36
            onClicked: backend.openLogin("")
        }
        RowLayout {
            visible: backend.loggedIn
            spacing: 4
            Rectangle {
                radius: 16; implicitHeight: 32; implicitWidth: acc.implicitWidth + 24
                color: P.accentSoft
                Text { id: acc; anchors.centerIn: parent; textFormat: Text.PlainText; text: backend.account; color: P.accentText
                       font.family: P.font; font.pixelSize: 12; font.weight: Font.DemiBold
                       elide: Text.ElideMiddle; width: Math.min(implicitWidth, 220) }
            }
            Btn { text: "Выйти"; kind: "danger"; lock: false; implicitHeight: 32; leftPadding: 12; rightPadding: 12
                  onClicked: backend.logout() }
        }

        // меню «⋯»
        Btn {
            id: more
            text: "⋯"; kind: "second"; lock: false
            implicitWidth: 36; implicitHeight: 36; leftPadding: 0; rightPadding: 0
            font.pixelSize: 18
            onClicked: menu.popup(more, 0, more.height + 6)
            Menu {
                id: menu
                font.family: P.font
                MenuItem { text: "Справка"; onTriggered: bar.helpRequested() }
                MenuItem { text: "Настройки"; onTriggered: bar.settingsRequested() }
                MenuItem { text: "Проверить связь с Apple"; onTriggered: backend.netCheck() }
            }
        }
    }
}
