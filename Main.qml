import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

ApplicationWindow {
    id: window
    visible: true
    width: 1480; height: 900
    minimumWidth: 1000; minimumHeight: 620
    title: "MultiDiskSearch"
    color: Theme.window
    font.family: "Segoe UI"; font.pixelSize: 13
    palette.window: "#202020"; palette.windowText: "#dedede"
    palette.base: "#252525"; palette.text: "#dedede"; palette.placeholderText: Theme.muted
    palette.button: "#393939"; palette.buttonText: "#eeeeee"
    palette.highlight: "#456fc7"; palette.highlightedText: "white"
    property int candidateRow: -1
    property var candidatePaths: []
    onClosing: function(close) {
        if (backend.busy) { backend.stop(); close.accepted = false }
    }

    FolderDialog { id: folderDialog; title: "Choose a media disk or folder"; onAccepted: backend.addLocation(selectedFolder) }
    Connections {
        target: backend
        function onCandidatesReady(paths, row) {
            window.candidatePaths = paths; window.candidateRow = row
            candidates.currentIndex = -1; candidateDialog.open()
        }
    }
    Dialog {
        id: candidateDialog
        anchors.centerIn: parent
        width: Math.min(window.width - 100, 1050); height: 420
        title: "Choose the correct source"
        modal: true
        standardButtons: Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent
            Label { text: "Select a source path to preview and relink."; color: "#aaaaaa" }
            ListView {
                id: candidates
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; model: window.candidatePaths
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    required property string modelData
                    required property int index
                    width: ListView.view.width; text: modelData
                    highlighted: candidates.currentIndex === index
                    onClicked: candidates.currentIndex = index
                    ToolTip.visible: hovered; ToolTip.text: modelData
                }
            }
            ActionButton { text: "Use selected source"; accent: true; enabled: candidates.currentIndex >= 0; onClicked: { backend.chooseCandidate(window.candidateRow, window.candidatePaths[candidates.currentIndex]); candidateDialog.close() } }
        }
    }
    Dialog {
        id: errorsDialog
        anchors.centerIn: parent; width: Math.min(window.width - 100, 1000); height: 450
        title: "Search details"; modal: true; standardButtons: Dialog.Close
        ScrollView { anchors.fill: parent; TextArea { text: backend.errors; readOnly: true; wrapMode: TextEdit.Wrap; selectByMouse: true } }
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 20; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Image {
                objectName: "brandMark"
                source: "assets/brand/mds-lockup.svg"
                sourceSize.width: 1536; sourceSize.height: 188
                Layout.preferredWidth: 410; Layout.preferredHeight: 52
                fillMode: Image.PreserveAspectFit
                Accessible.name: "MultiDiskSearch"
            }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Find missing media"; accent: true; enabled: backend.connected && !backend.busy; onClicked: backend.find() }
            ActionButton { text: "Relink " + backend.readyCount + (backend.readyCount === 1 ? " match" : " matches"); enabled: !backend.busy && backend.readyCount > 0; onClicked: backend.relink() }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 46; radius: Theme.radius; color: Theme.panel
            RowLayout {
                anchors.fill: parent; anchors.margins: 12; spacing: 24
                Label { text: backend.rows.length + "  MISSING CLIPS"; color: Theme.text; font.pixelSize: 12 }
                Label { text: backend.readyCount + "  READY"; color: Theme.accent; font.pixelSize: 12 }
                Label { text: backend.duplicateCount + "  DUPLICATES"; color: Theme.muted; font.pixelSize: 12 }
                Label { text: backend.missingCount + "  NOT FOUND"; color: Theme.muted; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                Label { text: backend.appVersion; color: Theme.muted; font.pixelSize: 11 }
            }
        }
        SplitView {
            id: split
            Layout.fillWidth: true; Layout.fillHeight: true
            orientation: Qt.Horizontal
            handle: Rectangle { implicitWidth: 8; color: SplitHandle.hovered ? Theme.accent : Theme.window }
            Rectangle {
                SplitView.preferredWidth: 370; SplitView.minimumWidth: 280
                color: Theme.panel; radius: Theme.radius
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 14; spacing: 12
                    RowLayout {
                        Label { text: "SEARCH LOCATIONS"; font.weight: Font.DemiBold; color: "#bbbbbb" }
                        Item { Layout.fillWidth: true }
                        Label { text: backend.roots.length; color: "#999999" }
                    }
                    ActionButton { text: "+ Add disk or folder"; Layout.fillWidth: true; enabled: !backend.busy; onClicked: folderDialog.open() }
                    ListView {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; spacing: 7; model: backend.roots
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: ListView.view.width; height: 90; radius: Theme.radius; color: Theme.card
                            RowLayout {
                                anchors.fill: parent; anchors.margins: 12; spacing: 10
                                Rectangle { width: 30; height: 22; radius: 3; color: "#454545"; border.color: "#777777"; Rectangle { width: 5; height: 3; radius: 1; color: Theme.accent; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 4 } }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: modelData.name; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Label { text: modelData.path; color: "#aaaaaa"; font.pixelSize: 12; wrapMode: Text.WrapAnywhere; maximumLineCount: 2; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                }
                                ActionButton { text: "×"; enabled: !backend.busy; onClicked: backend.removeLocation(index); ToolTip.visible: hovered; ToolTip.text: "Remove location" }
                            }
                        }
                    }
                    Label { text: "Saved automatically\nSystem and recovery folders excluded"; color: "#909090"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
            Rectangle {
                SplitView.fillWidth: true; SplitView.minimumWidth: 550
                color: Theme.panel; radius: Theme.radius
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                    RowLayout {
                        Label { text: "MISSING MEDIA"; font.weight: Font.DemiBold; color: "#bbbbbb" }
                        Item { Layout.fillWidth: true }
                        Label { text: backend.rows.length + (backend.rows.length === 1 ? " clip" : " clips"); color: Theme.muted }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        TextField {
                            id: searchField
                            Layout.fillWidth: true
                            placeholderText: "Filter clips or source paths…"
                            selectByMouse: true
                            color: Theme.text; placeholderTextColor: Theme.muted
                            background: Rectangle { radius: Theme.radius; color: Theme.card; border.color: searchField.activeFocus ? Theme.accent : Theme.border }
                            onTextChanged: backend.setFilter(text, statusFilter.currentText)
                        }
                        ComboBox {
                            id: statusFilter
                            Layout.preferredWidth: 160
                            model: ["All clips", "Ready to relink", "Needs review", "Not found", "Relinked"]
                            contentItem: Text { text: statusFilter.displayText; color: Theme.text; font: statusFilter.font; verticalAlignment: Text.AlignVCenter; leftPadding: 10; rightPadding: 22; elide: Text.ElideRight }
                            background: Rectangle { radius: Theme.radius; color: Theme.card; border.color: statusFilter.activeFocus ? Theme.accent : Theme.border }
                            indicator: Text { text: "v"; font.pixelSize: 10; color: Theme.muted; x: statusFilter.width - 18; anchors.verticalCenter: parent.verticalCenter }
                            delegate: ItemDelegate { width: statusFilter.width; text: modelData; contentItem: Text { text: modelData; color: Theme.text; font: statusFilter.font } background: Rectangle { color: highlighted ? "#454c56" : Theme.panel } }
                            onActivated: backend.setFilter(searchField.text, currentText)
                        }
                    }
                    ListView {
                        id: media
                        Layout.fillWidth: true; Layout.fillHeight: true
                        model: backend.displayRows; clip: true; spacing: 6
                        ScrollBar.vertical: ScrollBar {}
                        Label { anchors.centerIn: parent; visible: media.count === 0; text: backend.rows.length > 0 ? "No clips match this filter" : backend.busy ? "Reading project media…" : "Find missing media to see clips and previews here"; color: Theme.muted }
                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: ListView.view.width; height: 128; radius: 4
                            color: index % 2 ? "#303030" : "#2c2c2c"
                            RowLayout {
                                anchors.fill: parent; anchors.margins: 10; spacing: 14
                                Rectangle {
                                    Layout.preferredWidth: 164; Layout.preferredHeight: 104
                                    color: "#191919"; radius: 3
                                    Image { anchors.fill: parent; anchors.margins: 2; source: modelData.thumbnail; fillMode: Image.PreserveAspectFit; asynchronous: true }
                                    Label { anchors.centerIn: parent; visible: !modelData.thumbnail; text: "NO PREVIEW"; color: "#777777"; font.pixelSize: 11 }
                                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 18; color: "#bb171717"; Label { anchors.centerIn: parent; text: modelData.previewLabel; font.pixelSize: 10; color: "#bbbbbb" } }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 6
                                    RowLayout {
                                        Label { text: modelData.name; font.weight: Font.DemiBold; font.pixelSize: 14; elide: Text.ElideRight; Layout.fillWidth: true }
                                        Label { text: modelData.status; color: modelData.status === "Relinked" ? Theme.success : modelData.status === "Match" || modelData.status === "Chosen" ? Theme.accent : Theme.muted; elide: Text.ElideRight; Layout.maximumWidth: 200 }
                                    }
                                    Label { text: "Original  " + modelData.old; color: "#999999"; elide: Text.ElideMiddle; Layout.fillWidth: true; ToolTip.visible: originalHover.hovered; ToolTip.text: modelData.old; HoverHandler { id: originalHover } }
                                    Label { text: modelData.target ? "Found     " + modelData.target : "Source has not been selected"; color: modelData.target ? "#cccccc" : "#777777"; elide: Text.ElideMiddle; Layout.fillWidth: true; ToolTip.visible: targetHover.hovered; ToolTip.text: modelData.target; HoverHandler { id: targetHover } }
                                }
                                ActionButton { text: "Sources"; enabled: !backend.busy && modelData.status !== "Relinked" && modelData.status !== "Not found"; onClicked: backend.showCandidates(modelData.sourceIndex) }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 14
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                RowLayout {
                    Label { text: backend.phase; color: "#cccccc" }
                    Item { Layout.fillWidth: true }
                    Label { text: backend.total > 0 ? backend.completed + " / " + backend.total + "  ·  " + Math.floor(100 * backend.completed / backend.total) + "%" : ""; color: "#bcbcbc" }
                }
                ProgressBar {
                    id: progress
                    Layout.fillWidth: true; from: 0; to: Math.max(1, backend.total); value: backend.completed
                    indeterminate: backend.busy && backend.total === 0
                    background: Rectangle { implicitHeight: 6; color: "#383838"; radius: 3 }
                    contentItem: Item {
                        implicitHeight: 6
                        Rectangle { width: progress.indeterminate ? parent.width * 0.2 : progress.visualPosition * parent.width; height: parent.height; radius: 3; color: Theme.accent
                            SequentialAnimation on opacity { running: progress.indeterminate; loops: Animation.Infinite; NumberAnimation { to: 0.3; duration: 650 } NumberAnimation { to: 1; duration: 650 } }
                        }
                    }
                }
                Label { text: backend.status; color: "#999999"; elide: Text.ElideMiddle; Layout.fillWidth: true }
            }
            ActionButton { text: "Search details"; visible: backend.errors.length > 0; onClicked: errorsDialog.open() }
            ActionButton { text: "Stop"; enabled: backend.busy; onClicked: backend.stop() }
        }
    }
}
