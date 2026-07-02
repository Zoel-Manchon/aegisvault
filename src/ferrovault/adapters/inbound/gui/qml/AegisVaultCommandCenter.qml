import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1220
    height: 760
    visible: true
    title: "AegisVault · QML Command Center"
    color: "#070b14"

    property bool paletteOpen: false

    Shortcut {
        sequence: "Ctrl+K"
        onActivated: { paletteOpen = true; paletteInput.forceActiveFocus(); }
    }
    Shortcut {
        sequence: "Meta+K"
        onActivated: { paletteOpen = true; paletteInput.forceActiveFocus(); }
    }

    Timer {
        interval: 1500
        repeat: true
        running: true
        onTriggered: vaultBridge.refresh()
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0b1020" }
            GradientStop { position: 1.0; color: "#05070d" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Text { text: "AegisVault"; color: "#f8fafc"; font.pixelSize: 26; font.bold: true }
            Text { text: "QML Zero Trust Preview"; color: "#94a3b8"; font.pixelSize: 14; Layout.alignment: Qt.AlignBottom }
            Item { Layout.fillWidth: true }
            Button { text: "⌘K Command"; onClicked: { paletteOpen = true; paletteInput.forceActiveFocus(); } }
            Button { text: "Refresh"; onClicked: vaultBridge.refresh() }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18

            Rectangle {
                radius: 24
                color: "#0f172a"
                border.color: "#1e293b"
                Layout.preferredWidth: 380
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 22
                    spacing: 16
                    Text { text: "Security score"; color: "#94a3b8"; font.pixelSize: 13; font.letterSpacing: 1.2 }
                    Text {
                        text: vaultBridge.score
                        color: vaultBridge.score >= 80 ? "#22d3ee" : "#f59e0b"
                        font.pixelSize: 86
                        font.bold: true
                        Behavior on text { NumberAnimation { duration: 350 } }
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        from: 0; to: 100; value: vaultBridge.score
                        Behavior on value { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
                    }
                    Text { text: vaultBridge.grade; color: "#e2e8f0"; font.pixelSize: 22; font.bold: true }
                    Text { text: vaultBridge.totalEntries + " entries · " + vaultBridge.twofaPercent + "% 2FA · " + vaultBridge.activeGrants + " grants"; color: "#94a3b8"; wrapMode: Text.WordWrap }
                    Text { text: vaultBridge.overdueRotations + " overdue rotations"; color: vaultBridge.overdueRotations > 0 ? "#fb7185" : "#86efac" }
                    Rectangle { height: 1; color: "#1e293b"; Layout.fillWidth: true }
                    Text { text: "Selected"; color: "#94a3b8"; font.pixelSize: 13 }
                    Text { text: vaultBridge.selectedEntry || "None"; color: "#f8fafc"; font.pixelSize: 18; font.bold: true; wrapMode: Text.WordWrap }
                    Button { text: "Reveal selected"; enabled: vaultBridge.selectedEntry.length > 0; onClicked: secretText.text = vaultBridge.reveal(vaultBridge.selectedEntry) }
                    Text { id: secretText; color: "#22d3ee"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                    Item { Layout.fillHeight: true }
                }
            }

            Rectangle {
                radius: 24
                color: "#0f172a"
                border.color: "#1e293b"
                Layout.fillWidth: true
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12
                    Text { text: "Live audit stream"; color: "#f8fafc"; font.pixelSize: 22; font.bold: true }
                    Text { text: "Animated QML feed backed by the existing tamper-evident audit ledger."; color: "#94a3b8" }
                    ListView {
                        id: auditList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: vaultBridge.auditEvents()
                        delegate: Rectangle {
                            width: auditList.width
                            height: 64
                            radius: 14
                            color: index % 2 === 0 ? "#111827" : "#0b1220"
                            border.color: "#1e293b"
                            opacity: 0
                            Component.onCompleted: opacity = 1
                            Behavior on opacity { NumberAnimation { duration: 250 } }
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                Text { text: "#" + modelData.index; color: "#64748b"; Layout.preferredWidth: 52 }
                                Text { text: modelData.event_type; color: "#22d3ee"; font.bold: true; Layout.preferredWidth: 130 }
                                Text { text: modelData.message; color: "#cbd5e1"; elide: Text.ElideRight; Layout.fillWidth: true }
                                Text { text: "sev " + modelData.severity; color: modelData.severity >= 7 ? "#fb7185" : "#94a3b8" }
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: palette
        visible: paletteOpen
        opacity: paletteOpen ? 1 : 0
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 760)
        height: Math.min(parent.height - 120, 560)
        radius: 28
        color: "#0f172a"
        border.color: "#334155"
        z: 20
        scale: paletteOpen ? 1.0 : 0.94
        Behavior on opacity { NumberAnimation { duration: 180 } }
        Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12
            TextField {
                id: paletteInput
                Layout.fillWidth: true
                placeholderText: "Search entries and actions…"
                font.pixelSize: 18
                Keys.onEscapePressed: paletteOpen = false
            }
            ListView {
                id: commandList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: vaultBridge.commands(paletteInput.text)
                delegate: Rectangle {
                    width: commandList.width
                    height: 62
                    radius: 16
                    color: mouse.containsMouse ? "#1e293b" : "transparent"
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        Text { text: modelData.kind === "entry" ? "↳" : "⌘"; color: "#22d3ee"; font.pixelSize: 20; Layout.preferredWidth: 28 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { text: modelData.title; color: "#f8fafc"; font.pixelSize: 16; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                            Text { text: modelData.subtitle; color: "#94a3b8"; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                    }
                    MouseArea {
                        id: mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: { vaultBridge.selectCommand(modelData.id); paletteOpen = false; }
                    }
                }
            }
        }
    }
}
