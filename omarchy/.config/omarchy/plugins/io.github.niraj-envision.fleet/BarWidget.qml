import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Fleet pill for the Omarchy bar.
//
// Shows how many of your servers are reachable, and turns urgent the moment
// one is not. Everything comes from `fleet bar --json`, which reads the
// running Fleet server, so the widget holds no fleet state of its own and
// costs one cheap local command per poll.
BarWidget {
  id: root
  moduleName: "io.github.niraj-envision.fleet"

  property string label: ""
  property string tooltip: ""
  property string state: "empty"      // ok | warn | down | stopped | error | empty
  property int down: 0
  property int worstDisk: 0
  property var hosts: []
  property bool popupOpen: false

  readonly property bool alert: state === "down" || state === "error"
  readonly property bool warn: state === "warn"
  readonly property bool stopped: state === "stopped"
  readonly property bool needsSetup: state === "setup"

  // `omarchy plugin add` clones this repo into the plugins directory but does
  // not run anything, so the widget can be live before the application it
  // fronts has ever been installed. Rather than failing silently with `fleet`
  // missing from PATH, say so and make the fix one click.
  readonly property string installPath: Qt.resolvedUrl("install.sh").toString().replace(/^file:\/\//, "")
  readonly property string statusHelper: Qt.resolvedUrl("bin/fleet-bar-status").toString().replace(/^file:\/\//, "")
  readonly property string fleetPath: (Quickshell.env("HOME") || "") + "/.local/bin/fleet"

  readonly property int pollInterval: Math.min(300, Math.max(5, Number(setting("pollInterval", 20))))
  readonly property bool showIcon: setting("showIcon", true) !== false
  readonly property bool onlyWhenTrouble: setting("onlyWhenTrouble", false) === true

  readonly property string icon: ""      // nf-fa-server

  readonly property string displayText: label === ""
    ? (showIcon ? icon : "Fleet")
    : (showIcon ? icon + "  " + label : label)

  readonly property bool opened: popupOpen
  readonly property var visibleHosts: hosts.slice(0, 6)
  readonly property int hiddenHostCount: Math.max(0, hosts.length - visibleHosts.length)
  readonly property string summaryText: needsSetup
    ? "Fleet needs to be installed"
    : stopped
      ? "Fleet service is stopped"
      : state === "error"
        ? "Network status unavailable"
        : state === "empty"
          ? "No hosts configured"
          : alert
            ? down + " host" + (down === 1 ? "" : "s") + " unavailable"
            : warn
              ? "Online with a disk warning"
              : "All systems online"

  function refresh() {
    if (!poller.running) poller.running = true
  }

  function open() {
    popupOpen = true
    refresh()
  }

  function close() {
    popupOpen = false
  }

  function togglePopup() {
    popupOpen = !popupOpen
    if (popupOpen) refresh()
  }

  function closeForPopoutSwitch() {
    close()
  }

  function statusColor(status) {
    if (status === "online" || status === "connecting") return Color.accent
    if (status === "stopped" || status === "idle") return Color.muted
    return root.bar ? root.bar.urgent : Color.urgent
  }

  function fallbackRows(text) {
    var raw = String(text || "").slice(0, 4096).trim()
    if (raw === "") return []
    var lines = raw.split("\n")
    var rows = []
    for (var i = 0; i < Math.min(lines.length, 32); i++) {
      var line = lines[i].trim()
      if (line === "") continue
      var split = line.search(/\s{2,}/)
      rows.push({
        name: split < 0 ? line : line.slice(0, split),
        detail: split < 0 ? "" : line.slice(split).trim(),
        status: state === "ok" || state === "warn" ? "online" : state
      })
    }
    return rows
  }

  function openFleet() {
    close()
    if (root.needsSetup) root.installFleet()
    else Quickshell.execDetached([root.fleetPath])
  }

  function installFleet() {
    if (!installerProc.running) installerProc.running = true
  }

  function notifyStatus() {
    if (!notificationProc.running) {
      notificationProc.command = [
        "/usr/share/omarchy/bin/omarchy-notification-send",
        "Fleet",
        root.tooltip.slice(0, 512)
      ]
      notificationProc.running = true
    }
  }

  // A quiet bar is the point of onlyWhenTrouble: with everything healthy the
  // pill disappears entirely rather than parking a permanent "2/2" in the bar.
  visible: displayText !== ""
    && (!onlyWhenTrouble || alert || warn || stopped || needsSetup)
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: poller
    // Resolve `fleet` if it is installed; otherwise report the setup state
    // instead of letting the Process fail with nothing to show.
    command: [root.statusHelper]
    running: true
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (raw === "" || raw.length > 65536) return
        try {
          var data = JSON.parse(raw)
          root.label = String(data.text || "").slice(0, 80)
          root.tooltip = String(data.tooltip || "").slice(0, 512)
          root.state = String(data.state || "empty").slice(0, 16)
          root.down = Math.max(0, Math.min(100000, Number(data.down || 0)))
          root.worstDisk = Math.max(0, Math.min(100, Number(data.worstDisk || 0)))
          root.hosts = data.hosts instanceof Array
            ? data.hosts.slice(0, 32)
            : root.fallbackRows(root.tooltip)
        } catch (e) {
          // Keep the last good reading rather than blanking the bar on a
          // partial line or a half-written response.
        }
      }
    }
  }

  Timer {
    interval: 5000
    repeat: false
    running: poller.running
    onTriggered: poller.running = false
  }

  Process {
    id: installerProc
    command: [
      "/usr/bin/setsid", "/usr/bin/uwsm-app", "--", "/usr/bin/xdg-terminal-exec",
      "--app-id=org.omarchy.terminal", "--title=Fleet Setup",
      "-e", "/bin/bash", root.installPath
    ]
    onExited: function(exitCode, exitStatus) { root.refresh() }
  }

  Process { id: notificationProc }

  Timer {
    interval: 3000
    repeat: false
    running: notificationProc.running
    onTriggered: notificationProc.running = false
  }

  Timer {
    interval: root.pollInterval * 1000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  IpcHandler {
    target: "io.github.niraj-envision.fleet"

    function refresh(): void { root.refresh() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.togglePopup() }
    function openApp(): void { root.openFleet() }
    function status(): string { return root.label }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    labelVisible: false
    hasVisualContent: root.displayText !== ""
    horizontalMargin: 8.75
    fixedWidth: root.vertical ? -1 : visual.implicitWidth + scaledHorizontalMargin * 2
    verticalPadding: 8.75
    tooltipText: root.tooltip
    active: root.popupOpen || root.alert || root.needsSetup
    activeColor: root.popupOpen && !root.alert && !root.needsSetup
      ? Color.accent
      : (root.bar ? root.bar.urgent : Color.urgent)

    // Urgent when a host is unreachable, warning when a disk is nearly full,
    // muted when Fleet itself is not running — three states you want to read
    // without stopping to think.
    foreground: root.alert
      ? (root.bar ? root.bar.urgent : Color.urgent)
      : (root.warn || root.needsSetup)
        ? Color.accent
        : root.stopped
          ? Color.muted
          : (root.bar ? root.bar.barForeground : Color.foreground)

    onPressed: function(b) {
      if (b === Qt.RightButton) root.notifyStatus()
      else if (b === Qt.MiddleButton) root.refresh()
      else root.togglePopup()
    }

    Row {
      id: visual
      anchors.centerIn: parent
      spacing: root.vertical ? 0 : 3

      OpticalGlyph {
        visible: root.showIcon
        width: 16
        height: 16
        text: root.icon
        fontFamily: "JetBrainsMono Nerd Font Mono"
        fontSize: 17
        color: button.active && button.useActiveColor ? button.activeColor : button.foreground
      }

      Text {
        visible: !root.vertical && (root.label !== "" || !root.showIcon)
        text: root.label === "" ? "Fleet" : root.label
        font.family: button.fontFamily
        font.pixelSize: Style.font.body
        color: button.active && button.useActiveColor ? button.activeColor : button.foreground
      }
    }
  }

  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(Style.space(330))
    contentHeight: popup.fittedContentHeight(panel.implicitHeight, Style.space(440))

    Column {
      id: panel
      anchors.fill: parent
      spacing: Style.space(10)

      Row {
        width: parent.width
        spacing: Style.space(10)

        Text {
          text: root.icon
          textFormat: Text.PlainText
          color: root.alert ? (root.bar ? root.bar.urgent : Color.urgent) : Color.accent
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.display
          anchors.verticalCenter: parent.verticalCenter
        }

        Column {
          width: parent.width - Style.space(38)
          spacing: Style.space(2)

          Text {
            width: parent.width
            text: "Fleet network"
            textFormat: Text.PlainText
            color: Color.popups.text
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.title
            font.bold: true
          }

          Text {
            width: parent.width
            text: root.summaryText
            textFormat: Text.PlainText
            color: root.alert ? (root.bar ? root.bar.urgent : Color.urgent) : Color.muted
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.bodySmall
            elide: Text.ElideRight
          }
        }
      }

      PanelSeparator { foreground: Color.popups.text }

      Column {
        width: parent.width
        spacing: Style.space(4)

        Repeater {
          model: root.visibleHosts

          Item {
            required property var modelData
            width: parent ? parent.width : 0
            height: Style.space(34)

            Rectangle {
              width: Style.space(8)
              height: width
              radius: width / 2
              color: root.statusColor(parent.modelData.status || "idle")
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
            }

            Column {
              anchors.left: parent.left
              anchors.leftMargin: Style.space(18)
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: 0

              Text {
                width: parent.width
                text: parent.parent.modelData.name || "Host"
                textFormat: Text.PlainText
                color: Color.popups.text
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                text: parent.parent.modelData.detail || parent.parent.modelData.status || ""
                textFormat: Text.PlainText
                color: Color.muted
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }
          }
        }

        Text {
          visible: root.hosts.length === 0
          width: parent.width
          text: root.needsSetup ? "Install Fleet to see your hosts." : "No network details available."
          textFormat: Text.PlainText
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.WordWrap
          topPadding: Style.space(8)
          bottomPadding: Style.space(8)
        }

        Text {
          visible: root.hiddenHostCount > 0
          width: parent.width
          text: "+" + root.hiddenHostCount + " more in Fleet"
          textFormat: Text.PlainText
          color: Color.muted
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.caption
          horizontalAlignment: Text.AlignHCenter
        }
      }

      PanelSeparator { foreground: Color.popups.text }

      Button {
        width: parent.width
        text: root.needsSetup ? "Install Fleet" : "Open full app"
        iconText: root.needsSetup ? "󰏔" : "󰍉"
        foreground: Color.popups.text
        accent: Color.accent
        background: Style.normalFillFor(Color.popups.text, Color.accent)
        bordered: true
        focusable: true
        onClicked: root.openFleet()
      }
    }
  }
}
