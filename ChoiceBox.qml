import QtQuick
import QtQuick.Controls
import "."

ComboBox {
    id: control
    implicitWidth: 155
    implicitHeight: 40
    leftPadding: 12; rightPadding: 32
    hoverEnabled: true
    contentItem: Text {
        text: control.displayText; font: control.font
        color: control.enabled ? Theme.text : Theme.muted
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    indicator: Canvas {
        x: control.width - width - 12; y: (control.height - height) / 2
        width: 10; height: 6
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset(); ctx.strokeStyle = Theme.muted; ctx.lineWidth = 1.5
            ctx.beginPath(); ctx.moveTo(1, 1); ctx.lineTo(5, 5); ctx.lineTo(9, 1); ctx.stroke()
        }
    }
    background: Rectangle {
        radius: Theme.radius
        color: control.hovered && control.enabled ? "#353b44" : Theme.card
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.border
    }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width - 10; height: 38
        highlighted: control.highlightedIndex === index
        contentItem: Text { text: modelData; color: Theme.text; font: control.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 4; color: highlighted ? "#35445e" : "transparent" }
    }
    popup: Popup {
        y: control.height + 5; width: control.width; padding: 5
        implicitHeight: Math.min(contentItem.implicitHeight + 10, 250)
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle { radius: Theme.radius; color: Theme.panel; border.color: Theme.border }
    }
}
