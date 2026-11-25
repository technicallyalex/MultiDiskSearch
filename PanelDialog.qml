import QtQuick
import QtQuick.Controls
import "."

Dialog {
    id: control
    padding: 20
    font.family: "Segoe UI"; font.pixelSize: 13
    background: Rectangle { color: Theme.panel; radius: Theme.radius + 2; border.color: Theme.border }
    header: Label {
        text: control.title; color: Theme.text; font.pixelSize: 15; font.weight: Font.DemiBold
        leftPadding: 20; rightPadding: 20; topPadding: 18; bottomPadding: 12
        elide: Text.ElideRight
    }
    footer: DialogButtonBox {
        standardButtons: control.standardButtons
        alignment: Qt.AlignRight
        leftPadding: 20; rightPadding: 20; topPadding: 12; bottomPadding: 18
        spacing: 8
        background: Item {}
        delegate: ActionButton {}
        onAccepted: control.accept()
        onRejected: control.reject()
    }
    Overlay.modal: Rectangle { color: "#800d1015" }
}
