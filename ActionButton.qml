import QtQuick
import QtQuick.Controls
import "."

Button {
    id: control
    property bool accent: false
    padding: 12
    hoverEnabled: true
    contentItem: Text {
        text: control.text; font: control.font
        color: control.enabled ? Theme.text : "#777f89"
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: Theme.radius
        color: !control.enabled ? "#272a2f" : control.accent ? (control.hovered ? "#547ed0" : "#3e64ad") : (control.hovered ? "#454c56" : "#343a42")
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.border
    }
}
