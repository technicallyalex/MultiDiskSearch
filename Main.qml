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
    FolderDialog { id: indexFolderDialog; title: "Choose a local folder for the file index"; onAccepted: backend.setIndexFolder(selectedFolder) }
    PanelDialog {
        id: indexDialog
        objectName: "indexDialog"
        title: "Settings"
        anchors.centerIn: parent; width: Math.min(window.width - 60, 920); height: Math.min(window.height - 60, 740)
        modal: true; standardButtons: Dialog.Close
        onOpened: backend.refreshIndexUsage()
        Timer { interval: 2000; running: indexDialog.visible; repeat: true; onTriggered: backend.refreshIndexUsage() }
        ColumnLayout {
            anchors.fill: parent; spacing: 10
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Label { text: "Version " + backend.appVersion; color: Theme.text }
                Label {
                    text: backend.updateStatus; color: Theme.muted; font.pixelSize: 12
                    Layout.fillWidth: true; elide: Text.ElideRight
                    Accessible.ignored: text.length === 0
                    ToolTip.visible: updateStatusHover.hovered && text.length > 0
                    ToolTip.text: text
                    HoverHandler { id: updateStatusHover }
                }
                ActionButton {
                    text: backend.updateChecking ? "Checking…" : "Check for updates"
                    enabled: !backend.updateChecking
                    onClicked: backend.checkForUpdates()
                }
                ActionButton {
                    text: "View release"; visible: backend.updateUrl.length > 0
                    onClicked: Qt.openUrlExternally(backend.updateUrl)
                }
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
            Label { text: "INDEX FOLDER"; font.pixelSize: 12; color: Theme.muted }
            RowLayout {
                Layout.fillWidth: true
                TextField {
                    text: backend.indexFolder; readOnly: true; selectByMouse: true
                    Layout.fillWidth: true; implicitHeight: 40; padding: 10
                    color: Theme.text; selectionColor: Theme.accent; selectedTextColor: Theme.window
                    background: Rectangle { radius: Theme.radius; color: Theme.card; border.color: parent.activeFocus ? Theme.accent : Theme.border }
                }
                ActionButton { text: "Choose folder…"; enabled: !backend.busy; onClicked: indexFolderDialog.open() }
            }
            Label {
                objectName: "indexDiskUsage"
                text: "Index size on disk: " + backend.indexDiskSize
                color: Theme.text; font.pixelSize: 12
                ToolTip.visible: diskUsageHover.hovered
                ToolTip.text: "Includes the database, SQLite working files and recovery backups in the selected index folder."
                HoverHandler { id: diskUsageHover }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                CheckBox {
                text: "Keep index up to date while MultiDiskSearch is open"
                checked: backend.autoIndexEnabled
                onToggled: backend.setAutoIndex(checked)
                padding: 0; implicitHeight: 32
                indicator: Rectangle {
                    width: 18; height: 18; radius: 4; y: (parent.height - height) / 2
                    color: parent.checked ? Theme.accent : Theme.card
                    border.color: parent.visualFocus ? Theme.accent : Theme.border
                    Canvas {
                        anchors.centerIn: parent; width: 12; height: 12; visible: parent.parent.checked
                        onVisibleChanged: requestPaint()
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset(); ctx.strokeStyle = Theme.window; ctx.lineWidth = 2
                            ctx.beginPath(); ctx.moveTo(1, 6); ctx.lineTo(4.5, 9); ctx.lineTo(11, 2); ctx.stroke()
                        }
                    }
                }
                contentItem: Text { text: parent.text; leftPadding: 26; color: Theme.text; font: parent.font; verticalAlignment: Text.AlignVCenter }
                }
                Label {
                    text: backend.autoIndexStatus; color: Theme.muted; font.pixelSize: 12
                    elide: Text.ElideRight; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                    ToolTip.visible: autoStatusHover.hovered; ToolTip.text: text
                    HoverHandler { id: autoStatusHover }
                }
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border; Layout.topMargin: 4; Layout.bottomMargin: 4 }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "INDEXED LOCATIONS"; font.pixelSize: 12; color: Theme.muted }
                Item { Layout.fillWidth: true }
                Label { text: backend.roots.length + " locations"; font.pixelSize: 12; color: Theme.muted }
            }
            RowLayout {
                ActionButton { text: "Refresh all"; accent: true; enabled: !backend.busy; onClicked: backend.refreshIndex() }
                ActionButton { text: "Rebuild index"; enabled: !backend.busy; onClicked: backend.rebuildIndex() }
                ActionButton { text: "Stop"; enabled: backend.busy; onClicked: backend.stop() }
            }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; model: backend.roots; clip: true; spacing: 7
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: ListView.view.width; height: 88; radius: Theme.radius; color: Theme.card
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 14
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 4
                            Label { text: modelData.name; font.weight: Font.DemiBold; color: Theme.text; elide: Text.ElideRight; Layout.fillWidth: true }
                            Label { text: modelData.path; font.pixelSize: 12; color: Theme.muted; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            Label { text: modelData.indexDetail + (modelData.watchState ? " · " + modelData.watchState : ""); font.pixelSize: 12; color: Theme.muted; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        ColumnLayout {
                            Label { text: modelData.scanState; color: Theme.accent; font.pixelSize: 11; Layout.alignment: Qt.AlignRight }
                            ActionButton { text: "Refresh"; padding: 8; enabled: !backend.busy; onClicked: backend.refreshLocation(index) }
                        }
                    }
                }
            }
        }
    }
    Connections {
        target: backend
        function onCandidatesReady(paths, row) {
            window.candidatePaths = paths; window.candidateRow = row
            candidates.currentIndex = -1; candidateDialog.open()
        }
    }
    PanelDialog {
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
    PanelDialog {
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
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Label { text: "Scope"; color: Theme.muted; visible: window.width >= 1180 }
            ChoiceBox {
                id: scopeChoice
                objectName: "scopeChoice"
                Accessible.name: "Search scope"
                Layout.preferredWidth: window.width < 1180 ? 145 : 155
                model: ["Entire project", "Current timeline"]
                currentIndex: backend.searchScope === "timeline" ? 1 : 0
                enabled: !backend.busy
                onActivated: backend.configureSearch(currentIndex === 1 ? "timeline" : "project", methodChoice.selectedMethod, workerChoice.value)
            }
            Label { text: "Search"; color: Theme.muted; visible: window.width >= 1180 }
            ChoiceBox {
                id: methodChoice
                objectName: "methodChoice"
                Accessible.name: "Search method"
                Layout.preferredWidth: window.width < 1180 ? 180 : 195
                model: ["Drives directly", "File index", "Index first, then disks"]
                property var methods: ["direct", "index", "index_first"]
                property string selectedMethod: methods[currentIndex] || "direct"
                implicitWidth: 195
                currentIndex: backend.searchMethod === "index_first" ? 2 : backend.searchMethod === "index" ? 1 : 0
                enabled: !backend.busy
                onActivated: backend.configureSearch(scopeChoice.currentIndex === 1 ? "timeline" : "project", selectedMethod, workerChoice.value)
            }
            Label { text: "Workers"; color: Theme.muted; visible: window.width >= 1180 }
            ChoiceBox {
                id: workerChoice
                objectName: "workerChoice"
                model: ["Auto", "1", "2", "3", "4", "5", "6", "7", "8"]
                currentIndex: backend.maxWorkers
                readonly property int value: Math.max(0, currentIndex)
                enabled: !backend.busy
                Accessible.name: "Maximum parallel storage groups"
                Layout.preferredWidth: window.width < 1180 ? 96 : 110
                ToolTip.visible: hovered && !popup.visible
                ToolTip.text: "Auto balances searches across disks and network shares. A number sets a manual limit."
                onActivated: backend.configureSearch(scopeChoice.currentIndex === 1 ? "timeline" : "project", methodChoice.selectedMethod, currentIndex)
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            ActionButton { text: "Settings"; onClicked: indexDialog.open() }
            ActionButton { text: "Find missing media"; accent: true; enabled: backend.connected && !backend.busy; onClicked: backend.find() }
            ActionButton { text: "Relink " + backend.readyCount + (backend.readyCount === 1 ? " match" : " matches"); enabled: !backend.busy && backend.readyCount > 0; onClicked: backend.relink() }
        }
        Label { text: "Timeline: " + backend.timelineName; visible: backend.timelineName.length > 0; color: Theme.accent; elide: Text.ElideRight; Layout.fillWidth: true }
        Label { text: backend.locationSummary; visible: text.length > 0; color: Theme.muted; Layout.fillWidth: true }
        Label { text: "Current timeline scope includes direct video/audio sources. Nested timelines, compound and multicam internals are not included. Relinking shared sources also updates other timelines."; visible: backend.searchScope === "timeline"; color: Theme.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
                            width: ListView.view.width; height: 165; radius: Theme.radius; color: Theme.card
                            RowLayout {
                                anchors.fill: parent; anchors.margins: 12; spacing: 10
                                Rectangle { width: 30; height: 22; radius: 3; color: "#454545"; border.color: "#777777"; Rectangle { width: 5; height: 3; radius: 1; color: Theme.accent; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 4 } }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Label { text: modelData.name; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Label { text: modelData.path; color: "#aaaaaa"; font.pixelSize: 12; wrapMode: Text.WrapAnywhere; maximumLineCount: 2; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    Label { text: modelData.scanState + (modelData.scanDetail ? " · " + modelData.scanDetail : ""); color: Theme.accent; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    Label { text: modelData.indexDetail; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    ActionButton { text: "Refresh index"; enabled: !backend.busy; onClicked: backend.refreshLocation(index) }
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
                        ChoiceBox {
                            id: statusFilter
                            Layout.preferredWidth: 160
                            model: ["All clips", "Ready to relink", "Needs review", "Not found", "Relinked"]
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
