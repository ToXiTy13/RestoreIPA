// Главное окно Restore. Состояние и действия — в объекте backend (restore_gui/backend.py), палитра — P.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    width: 1200; height: 820
    minimumWidth: 1000; minimumHeight: 660
    visible: startVisible
    title: "Restore " + backend.version + " — возврат приложений на iPhone"
    color: P.bg
    font.family: P.font

    RowLayout {
        anchors.fill: parent
        spacing: 0
        // пока открыта панель приложения или всплывающее окно, окно под ними нажатий не получает: иначе
        // нажатие на копию в панели срабатывало ещё и на плитке главной под панелью (Drawer пропускает
        // нажатия к тому, что под ним, — TapHandler их не «съедает»)
        enabled: !detail.visible && !dialogs.anyOpen

        Sidebar {
            Layout.fillHeight: true
            Layout.preferredWidth: 236
            onHelpRequested: dialogs.openHelp()
            onSettingsRequested: dialogs.openSettings()
            onSupportRequested: dialogs.openSupport()
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            StackLayout {
                id: pages
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 28
                Layout.bottomMargin: 8
                currentIndex: ["home", "apps", "mine", "ipa"].indexOf(backend.page)
                HomePage { onHelpRequested: dialogs.openHelp() }
                AppsPage {}
                MinePage {}
                IpaPage {}
            }

            // ---------- выбранные для установки по очереди ----------
            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 28; Layout.rightMargin: 28
                Layout.preferredHeight: backend.selectedCount > 0 ? 62 : 0
                visible: Layout.preferredHeight > 0
                clip: true
                radius: 16; color: P.card; border.color: P.accentDim
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 18; anchors.rightMargin: 12
                    Text { text: backend.selectedText; color: P.text; font.family: P.font; font.pixelSize: 14
                           font.bold: true; Layout.fillWidth: true }
                    Btn { text: "Снять"; kind: "ghost"; lock: false; onClicked: backend.clearSelection() }
                    Btn { text: "Поставить выбранные"; kind: "primary"; onClicked: backend.installSelected() }
                }
            }

            // ---------- строка состояния ----------
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 28; Layout.rightMargin: 28; Layout.topMargin: 6; Layout.bottomMargin: 8
                spacing: 10
                Text { text: backend.status; color: P.muted; font.family: P.font; font.pixelSize: 12
                       elide: Text.ElideRight; Layout.fillWidth: true }
                ProgressBar {
                    visible: backend.busy
                    indeterminate: true
                    implicitWidth: 160; implicitHeight: 4
                    background: Rectangle { radius: 2; color: P.border }
                    contentItem: Item {
                        clip: true
                        Rectangle {
                            width: parent.width * 0.35; height: parent.height; radius: 2; color: P.accent
                            SequentialAnimation on x {
                                running: backend.busy; loops: Animation.Infinite
                                NumberAnimation { from: -50; to: 160; duration: 1100; easing.type: Easing.InOutQuad }
                            }
                        }
                    }
                }
                Btn { visible: backend.busy; text: "Остановить"; kind: "danger"; lock: false; implicitHeight: 28
                      onClicked: backend.stop() }
                Btn { text: backend.logOpen ? "Скрыть журнал" : "Журнал"; kind: "ghost"; lock: false; implicitHeight: 28
                      onClicked: backend.logOpen = !backend.logOpen }
            }

            // ---------- журнал ----------
            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 28; Layout.rightMargin: 28; Layout.bottomMargin: backend.logOpen ? 14 : 0
                Layout.preferredHeight: backend.logOpen ? 190 : 0
                visible: Layout.preferredHeight > 0
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                radius: 14; color: P.rail; border.color: P.border
                clip: true
                ScrollView {
                    id: logScroll
                    anchors.fill: parent; anchors.margins: 6
                    TextArea {
                        id: logText
                        readOnly: true; selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: "#c9c9d3"; selectionColor: P.accent
                        font.family: "Consolas"; font.pixelSize: 12
                        background: null
                    }
                }
            }
        }
    }

    DetailPanel { id: detail }
    Dialogs { id: dialogs }

    Connections {
        target: backend
        function onLogAppended(text) {
            logText.append(text)
            if (logText.length > 400000) {  // длинный журнал тормозит: обрезаем начало по границе строки
                const cut = logText.text.indexOf("\n", logText.length - 300000)
                logText.remove(0, cut + 1)
            }
            logText.cursorPosition = logText.length
        }
    }
}
