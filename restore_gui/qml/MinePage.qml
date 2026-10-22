// «Мои удалённые»: приложения из истории Apple ID, которых больше нет в App Store.
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 10

    PageTitle { title: "Мои удалённые"; sub: "Приложения, которые были у вашего Apple ID и пропали из App Store." }

    RowLayout {
        Layout.topMargin: 6
        spacing: 8
        Btn { text: "Проверить по каталогу"; kind: "primary"; onClicked: backend.findMine() }
        Btn { text: "Загрузить список покупок"; onClicked: backend.loadPurchases() }
    }

    AppsList {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.topMargin: 4
        listName: "mine"
        model: backend.mine
        emptyTitle: backend.loggedIn ? "Пока пусто" : "Сначала войдите в Apple ID"
        emptySub: backend.loggedIn ? "Нажмите «Проверить по каталогу» — это займёт несколько минут."
                                   : "Потом проверим, какие приложения были у вас и пропали из App Store."
    }
}
