// Все всплывающие окна: вход, код 2FA, справка, настройки, поддержка, сообщения.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: dialogs
    readonly property bool anyOpen: login.visible || ask.visible || help.visible || settings.visible
                                    || support.visible || noticeBox.visible
    function openHelp() { helpText.text = backend.helpText(); help.open() }
    function openSettings() { settings.open() }
    function openSupport() { copyBtn.text = "Скопировать ссылку"; support.open() }
    function notice(title, text) { noticeBox.title = title; noticeText.text = text; noticeBox.open() }

    // ---------- вход ----------
    Modal {
        id: login
        width: 440
        // email тоже не держим: после «Выйти» поле пустое (на диск программа его не пишет)
        onClosed: { email.text = ""; password.text = ""; backend.loginOpen = false }
        onOpened: email.forceActiveFocus()

        Logo { size: 56; Layout.alignment: Qt.AlignHCenter }
        Text { text: "Вход в Apple ID"; color: P.text; font.family: P.font; font.pixelSize: 22; font.bold: true
               Layout.alignment: Qt.AlignHCenter }
        Text { text: backend.loginNote; color: P.muted; font.family: P.font; font.pixelSize: 12
               wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
        Field { id: email; placeholderText: "Apple ID (email)"; onAccepted: password.forceActiveFocus() }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Field { id: password; placeholderText: "Пароль"; echoMode: showPw.checked ? TextInput.Normal : TextInput.Password
                    onAccepted: backend.login(email.text, password.text) }
            Btn { id: showPw; checkable: true; text: checked ? "Скрыть" : "Показать"; kind: "ghost"; lock: false
                  implicitHeight: 46 }
        }
        Btn { text: backend.busy ? "Входим…" : "Войти"; kind: "primary"; implicitHeight: 48; Layout.fillWidth: true
              onClicked: backend.login(email.text, password.text) }
        Text { text: "Пароль не сохраняется. Сессия удаляется при выходе и при закрытии программы. Код "
                     + "подтверждения придёт на ваши устройства Apple."
               color: P.muted; font.family: P.font; font.pixelSize: 11; wrapMode: Text.WordWrap
               horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
    }

    // ---------- код двухфакторной аутентификации ----------
    Modal {
        id: ask
        title: backend.askTitle
        width: 400
        closePolicy: Popup.NoAutoClose  // рабочий поток ждёт ответа: закрыть можно только кнопками
        onOpened: { code.text = ""; code.forceActiveFocus() }
        Text { text: backend.askPrompt; color: P.text; font.family: P.font; font.pixelSize: 13
               wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Field { id: code; placeholderText: "123456"; inputMethodHints: Qt.ImhDigitsOnly
                onAccepted: backend.answerAsk(code.text, true) }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Btn { text: "Отмена"; lock: false; kind: "ghost"; onClicked: backend.answerAsk("", false) }
            Btn { text: "Продолжить"; lock: false; kind: "primary"; onClicked: backend.answerAsk(code.text, true) }
        }
    }

    // ---------- справка ----------
    Modal {
        id: help
        title: "Что нужно для работы"
        width: 560
        Text { id: helpText; color: P.text; font.family: P.font; font.pixelSize: 13; wrapMode: Text.WordWrap
               Layout.fillWidth: true; lineHeight: 1.15 }
        Btn { text: "Понятно"; lock: false; Layout.alignment: Qt.AlignRight; onClicked: help.close() }
    }

    // ---------- настройки ----------
    Modal {
        id: settings
        title: "Настройки"
        width: 520
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Магазин (код страны) для проверки наличия"; color: P.text; font.family: P.font
                   font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Field { Layout.fillWidth: false; implicitWidth: 64; horizontalAlignment: Text.AlignHCenter
                    text: backend.country; maximumLength: 2; onTextEdited: backend.country = text }
        }
        Toggle { text: "В «Моих удалённых» скрывать то, что есть в App Store"; checked: backend.onlyRemoved
                 onToggled: backend.setOnlyRemoved(checked) }
        Toggle { text: "Получать лицензию, если приложение ещё продаётся в App Store"; checked: backend.purchase
                 onToggled: backend.purchase = checked }
        Btn { text: "Готово"; lock: false; Layout.alignment: Qt.AlignRight; onClicked: settings.close() }
    }

    // ---------- поддержать разработчика ----------
    Modal {
        id: support
        title: "Поддержать разработчика"
        width: 420
        Text { text: "Restore бесплатная. Если она помогла вернуть нужное приложение, можно поблагодарить "
                     + "разработчика через CloudTips любой суммой."
               color: P.text; font.family: P.font; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Btn { text: "Отблагодарить по СБП или картой РФ"; kind: "primary"; lock: false; implicitHeight: 44
              Layout.fillWidth: true
              onClicked: backend.openUrl(backend.supportUrl) }
        Text { text: "или наведите камеру телефона на QR-код"; color: P.muted; font.family: P.font; font.pixelSize: 12
               Layout.alignment: Qt.AlignHCenter; Layout.topMargin: 4 }
        Image { source: backend.qrUrl; visible: backend.qrUrl !== ""; Layout.preferredWidth: 220
                Layout.preferredHeight: 220; Layout.alignment: Qt.AlignHCenter; fillMode: Image.PreserveAspectFit
                smooth: true; mipmap: true }
        Text { text: "QR-код недоступен: pip install segno"; visible: backend.qrUrl === ""; color: P.warn
               font.family: P.font; font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter }
        Text { text: backend.supportUrl; color: P.muted; font.family: P.font; font.pixelSize: 11
               Layout.alignment: Qt.AlignHCenter }
        Btn { id: copyBtn; text: "Скопировать ссылку"; kind: "ghost"; lock: false; implicitHeight: 32
              Layout.alignment: Qt.AlignHCenter
              onClicked: { backend.copyText(backend.supportUrl); text = "Ссылка скопирована" } }
    }

    // ---------- сообщение ----------
    Modal {
        id: noticeBox
        width: 420
        Text { id: noticeText; color: P.text; font.family: P.font; font.pixelSize: 13; wrapMode: Text.WordWrap
               Layout.fillWidth: true }
        Btn { text: "OK"; lock: false; kind: "primary"; Layout.alignment: Qt.AlignRight; onClicked: noticeBox.close() }
    }

    // открываются по свойствам Backend (а не привязкой visible: её рвёт закрытие по Esc)
    Connections {
        target: backend
        function onNoticeRequested(title, text) { dialogs.notice(title, text) }
        function onLoginOpenChanged() { backend.loginOpen ? login.open() : login.close() }
        function onAskOpenChanged() { backend.askOpen ? ask.open() : ask.close() }
    }
}
