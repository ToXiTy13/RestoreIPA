// Панель приложения (выезжает справа): проверки, копии под другими названиями, выбор версии, скачивание.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Drawer {
    id: panel
    edge: Qt.RightEdge
    width: Math.min(620, Math.max(520, parent.width * 0.5))
    height: parent.height
    modal: true
    dragMargin: 0  // открывается только по нажатию на приложение
    Overlay.modal: Rectangle { color: P.shade }
    background: Rectangle {
        color: P.bg
        Rectangle { width: 1; height: parent.height; color: P.border }
    }
    onClosed: if (backend.detailOpen) backend.closeDetail()

    Connections {
        target: backend
        function onDetailOpenChanged() { backend.detailOpen ? panel.open() : panel.close() }
    }

    function kindColor(kind) {
        return kind === "ok" ? P.ok : kind === "warn" ? P.warn : kind === "muted" ? P.muted : P.text
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        // ---------- шапка ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            AppIcon { size: 60; icon: backend.detailApp.icon || ""; letter: backend.detailApp.letter || "?"
                      tint: backend.detailApp.tint || P.accent }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 2
                Text { textFormat: Text.PlainText; text: backend.detailApp.name || ""; color: P.text; font.family: P.font; font.pixelSize: 19
                       font.weight: Font.Bold; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Text {
                    text: "App ID " + (backend.detailApp.id || "")
                    color: idHover.hovered ? P.text : P.muted; font.family: P.font; font.pixelSize: 11
                    HoverHandler { id: idHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: backend.copyText(String(backend.detailApp.id)) }
                    ToolTip.visible: idHover.hovered; ToolTip.text: "Скопировать"
                }
            }
            Btn { text: "✕"; kind: "ghost"; lock: false; implicitWidth: 40; implicitHeight: 40; leftPadding: 0
                  rightPadding: 0; onClicked: panel.close() }
        }

        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            ScrollBar.vertical: ThinScrollBar { parent: scroll; x: scroll.width - width; height: scroll.height }

            ColumnLayout {
                width: scroll.availableWidth - 12
                spacing: 12

                // ---------- проверки ----------
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: checksCol.implicitHeight + 24
                    radius: 14; color: P.card
                    ColumnLayout {
                        id: checksCol
                        anchors.fill: parent; anchors.margins: 12; anchors.leftMargin: 16
                        spacing: 6
                        Repeater {
                            model: [["acc", "Apple ID"], ["phone", "iPhone"], ["store", "App Store"]]
                            delegate: RowLayout {
                                required property var modelData
                                readonly property var check: backend.detailChecks[modelData[0]] || ({})
                                Layout.fillWidth: true
                                spacing: 10
                                Text { text: modelData[1]; color: P.muted; font.family: P.font; font.pixelSize: 12
                                       Layout.preferredWidth: 80 }
                                Text { textFormat: Text.PlainText; text: check.text || ""; color: panel.kindColor(check.kind)
                                       font.family: P.font; font.pixelSize: 12; font.weight: Font.Bold
                                       wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                        }
                    }
                }

                // ---------- версии ----------
                Text { textFormat: Text.PlainText; text: backend.versionHead; color: P.muted; font.family: P.font; font.pixelSize: 12
                       font.weight: Font.Bold; Layout.topMargin: 4 }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: versionsCol.implicitHeight + 20
                    radius: 14; color: P.card
                    ColumnLayout {
                        id: versionsCol
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                        anchors.margins: 10
                        spacing: 2

                        RowLayout {  // идёт проверка
                            visible: backend.versionMode === "loading"
                            Layout.margins: 14
                            spacing: 10
                            BusyIndicator { running: parent.visible; implicitWidth: 24; implicitHeight: 24 }
                            Text { text: "Проверяю…"; color: P.muted; font.family: P.font; font.pixelSize: 12 }
                        }

                        ColumnLayout {  // проверка не прошла
                            visible: backend.versionMode === "error"
                            Layout.fillWidth: true; Layout.margins: 6
                            spacing: 8
                            Text { text: "Не удалось получить версии — проверка не прошла. Это ошибка, а не «нет в истории»: "
                                         + "приложение может быть в ваших покупках."
                                   color: P.warn; font.family: P.font; font.pixelSize: 12; font.weight: Font.Bold
                                   wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            Text { textFormat: Text.PlainText; text: backend.detailErr; color: P.text; font.family: P.font; font.pixelSize: 12
                                   wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            Text { text: "Ответ Apple (ipatool)"; color: P.muted; font.family: P.font; font.pixelSize: 10
                                   font.weight: Font.Bold }
                            TextArea {
                                Layout.fillWidth: true
                                textFormat: TextEdit.PlainText; text: backend.detailAnswer
                                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                                color: P.text; font.family: P.mono; font.pixelSize: 11
                                background: Rectangle { radius: 8; color: P.field }
                            }
                            Btn { text: "Повторить проверку"; lock: false; implicitHeight: 34; onClicked: backend.detailRecheck() }
                        }

                        Text {  // нет в истории
                            visible: backend.versionMode === "none"
                            Layout.margins: 14
                            text: "Выбор версии недоступен: приложения нет в истории этого Apple ID."
                            color: P.muted; font.family: P.font; font.pixelSize: 12; wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Repeater {  // список версий
                            model: backend.versions
                            delegate: Rectangle {
                                id: ver
                                required property string value
                                required property string title
                                required property string sub
                                required property bool mine
                                readonly property bool chosen: backend.selectedVersion === value
                                Layout.fillWidth: true
                                height: 50; radius: 10
                                color: chosen ? P.accentSoft : (verHover.hovered ? P.cardHover : P.card)
                                Behavior on color { ColorAnimation { duration: 120 } }
                                HoverHandler { id: verHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: backend.selectedVersion = ver.value }
                                RowLayout {
                                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10
                                    spacing: 12
                                    Rectangle {
                                        width: 18; height: 18; radius: 9
                                        color: "transparent"; border.width: 2
                                        border.color: ver.chosen ? P.accent : P.borderLight
                                        Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4
                                                    color: P.accent; visible: ver.chosen }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 0
                                        Text { textFormat: Text.PlainText; text: ver.title; color: P.text; font.family: P.font; font.pixelSize: 12
                                               font.weight: Font.Bold; Layout.fillWidth: true }
                                        Text { textFormat: Text.PlainText; text: ver.sub; color: ver.mine ? P.ok : P.muted; font.family: P.font
                                               font.pixelSize: 10; Layout.fillWidth: true }
                                    }
                                }
                            }
                        }

                        Btn {
                            visible: backend.moreText !== ""
                            text: backend.moreText; kind: "ghost"; lock: false; implicitHeight: 32
                            Layout.alignment: Qt.AlignHCenter
                            onClicked: backend.detailMore()
                        }
                    }
                }

                // ---------- копии под другими названиями ----------
                ColumnLayout {
                    visible: backend.cloneHead !== ""
                    Layout.fillWidth: true
                    spacing: 6
                    Text { textFormat: Text.PlainText; text: backend.cloneHead; color: backend.cloneHeadOk ? P.ok : P.muted; font.family: P.font
                           font.pixelSize: 12; font.weight: Font.Bold }
                    Text { text: "Это же приложение публиковали под видом других программ. Если вы ставили такую копию, "
                                 + "она в истории вашего Apple ID под своим ID — нажмите на неё, чтобы увидеть её версии."
                           color: P.muted; font.family: P.font; font.pixelSize: 11; wrapMode: Text.WordWrap
                           Layout.fillWidth: true }
                    Repeater {
                        model: backend.clones
                        delegate: Rectangle {
                            id: clone
                            required property int index
                            required property string title
                            required property string sub
                            required property string letter
                            required property string tint
                            required property string icon
                            required property string status
                            required property string statusKind
                            Layout.fillWidth: true
                            height: 52; radius: 12
                            color: cloneHover.hovered ? P.cardHover : P.card
                            Behavior on color { ColorAnimation { duration: 120 } }
                            HoverHandler { id: cloneHover; cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: backend.openDetail("clones", clone.index) }
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10
                                spacing: 10
                                AppIcon { size: 32; icon: clone.icon; letter: clone.letter; tint: clone.tint }
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 0
                                    Text { textFormat: Text.PlainText; text: clone.title; color: P.text; font.family: P.font; font.pixelSize: 12
                                           font.weight: Font.Bold; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { textFormat: Text.PlainText; text: clone.sub; color: P.muted; font.family: P.font; font.pixelSize: 10
                                           elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                Text { textFormat: Text.PlainText; text: clone.status; color: panel.kindColor(clone.statusKind)
                                       font.family: P.font; font.pixelSize: 11 }
                                Text { text: "›"; color: P.muted; font.pixelSize: 18 }
                            }
                        }
                    }
                }
            }
        }

        // ---------- внизу ----------
        Text {
            text: "Apple не хранит и не отдаёт список версий, которые вы скачивали раньше. Здесь только версии, "
                  + "доступные именно вашему Apple ID, и только если приложение есть в его истории. Отметка "
                  + "«скачано через программу» — версии, которые вы уже брали здесь."
            color: P.muted; font.family: P.font; font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Btn {
                text: "Скачать и установить"; kind: "primary"; Layout.fillWidth: true; implicitHeight: 44
                enabled: backend.actionsEnabled && !backend.busy
                onClicked: backend.detailAction(true)
            }
            Btn {
                text: "Только скачать IPA"; implicitHeight: 44
                enabled: backend.actionsEnabled && !backend.busy
                onClicked: backend.detailAction(false)
            }
        }
    }
}
