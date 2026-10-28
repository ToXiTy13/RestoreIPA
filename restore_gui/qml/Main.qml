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
    // стандартные элементы Qt (меню «⋯», подсказки, индикатор загрузки) — тоже в цветах темы
    palette.window: P.card; palette.windowText: P.text; palette.base: P.field; palette.text: P.text
    palette.button: P.second; palette.buttonText: P.text; palette.highlight: P.accent; palette.highlightedText: "white"
    palette.light: P.card; palette.mid: P.border; palette.dark: P.muted; palette.placeholderText: P.muted
    palette.toolTipBase: P.card; palette.toolTipText: P.text

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        // пока открыта панель приложения или всплывающее окно, окно под ними нажатий не получает: иначе
        // нажатие на копию в панели срабатывало ещё и на плитке главной под панелью (Drawer пропускает
        // нажатия к тому, что под ним, — TapHandler их не «съедает»)
        enabled: !detail.visible && !dialogs.anyOpen

        TopBar {
            Layout.fillWidth: true
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
                radius: 31; color: P.accentSoft; border.color: P.accentDim
                Behavior on Layout.preferredHeight { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 18; anchors.rightMargin: 12
                    Text { text: backend.selectedText; color: P.text; font.family: P.font; font.pixelSize: 14
                           font.weight: Font.Bold; Layout.fillWidth: true }
                    Btn { text: "Снять"; kind: "ghost"; lock: false; onClicked: backend.clearSelection() }
                    Btn { text: "Поставить выбранные"; kind: "primary"; onClicked: backend.installSelected() }
                }
            }

            // ---------- строка состояния ----------
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 28; Layout.rightMargin: 28; Layout.topMargin: 6; Layout.bottomMargin: 8
                spacing: 10
                Text { textFormat: Text.PlainText; text: backend.status; color: P.muted; font.family: P.font; font.pixelSize: 12
                       elide: Text.ElideRight; Layout.fillWidth: true }
                ProgressBar {
                    visible: backend.busy
                    indeterminate: true
                    implicitWidth: 160; implicitHeight: 4
                    background: Rectangle { radius: 2; color: P.border }
                    contentItem: Item {
                        clip: true
                        Rectangle {
                            id: runner
                            width: parent.width * 0.35; height: parent.height; radius: 2; color: P.accent
                            // Animator идёт в потоке отрисовки: полоса движется ровно, даже когда поток окна
                            // занят (обновление списков, журнал). Иначе кадры шли неровно — на мониторе с
                            // G-SYNC/FreeSync частота обновления прыгала вслед за ними и экран мерцал.
                            XAnimator {
                                target: runner; running: backend.busy; loops: Animation.Infinite
                                from: -50; to: 160; duration: 1100; easing.type: Easing.InOutQuad
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
                        id: logText; textFormat: TextEdit.PlainText
                        readOnly: true; selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: P.logText; selectionColor: P.accentDim
                        font.family: P.mono; font.pixelSize: 12
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
        // долгая операция закончилась, а окно не на переднем плане — мигнуть значком на панели задач
        function onTaskFinished() { if (!win.active) win.alert(0) }
    }
}
