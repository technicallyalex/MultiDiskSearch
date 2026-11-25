import QtQuick
import QtQuick.Controls
import "."

SpinBox {
    id: control
    implicitWidth: 110; implicitHeight: 40
    leftPadding: 34; rightPadding: 34
    hoverEnabled: true
    contentItem: TextInput {
        text: control.textFromValue(control.value, control.locale)
        font: control.font; color: control.enabled ? Theme.text : Theme.muted
        selectionColor: Theme.accent; selectedTextColor: Theme.window
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        readOnly: !control.editable; validator: control.validator
        inputMethodHints: Qt.ImhDigitsOnly
    }
    validator: IntValidator { bottom: Math.min(control.from, control.to); top: Math.max(control.from, control.to) }
    background: Rectangle {
        radius: Theme.radius; color: Theme.card
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.border
    }
    down.indicator: Rectangle {
        x: 1; y: 1; width: 30; height: control.height - 2; radius: Theme.radius - 1
        color: control.down.pressed ? "#3c4655" : control.down.hovered ? "#454c56" : "#343a42"
        opacity: control.enabled && control.value > control.from ? 1 : 0.45
        Text { anchors.centerIn: parent; text: "−"; font.pixelSize: 18; color: Theme.text }
    }
    up.indicator: Rectangle {
        x: control.width - width - 1; y: 1; width: 30; height: control.height - 2; radius: Theme.radius - 1
        color: control.up.pressed ? "#3c4655" : control.up.hovered ? "#454c56" : "#343a42"
        opacity: control.enabled && control.value < control.to ? 1 : 0.45
        Text { anchors.centerIn: parent; text: "+"; font.pixelSize: 18; color: Theme.text }
    }
}
