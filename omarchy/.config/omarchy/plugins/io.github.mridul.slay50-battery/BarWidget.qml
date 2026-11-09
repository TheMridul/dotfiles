import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.mridul.slay50-battery"

  property bool available: false
  property int percentage: -1
  property int powerCode: -1
  property string statusText: "Waiting for mouse battery data"

  readonly property string watcherPath: Quickshell.env("HOME") + "/.local/bin/slay50-battery"
  readonly property bool critical: available && percentage <= 15
  readonly property string label: available ? percentage + "%" : "—"
  readonly property string tooltip: available
    ? "DAWG Slay 50: " + percentage + "%"
    : statusText

  function acceptUpdate(line) {
    var update
    try {
      update = JSON.parse(String(line || "").trim())
    } catch (error) {
      return
    }

    if (update.available === true) {
      var nextPercentage = Number(update.percentage)
      if (!isFinite(nextPercentage) || nextPercentage < 0 || nextPercentage > 100) return
      available = true
      percentage = Math.round(nextPercentage)
      powerCode = Number(update.power_code)
      statusText = "Battery data received"
      return
    }

    if (update.available === false) {
      available = false
      percentage = -1
      powerCode = -1
      statusText = "Mouse battery unavailable"
    }
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: watcher
    running: true
    command: [root.watcherPath, "watch", "--json"]
    onExited: function(exitCode) {
      root.available = false
      root.statusText = exitCode === 3
        ? "Slay 50 receiver permission denied"
        : "Waiting for Slay 50 receiver"
      restartTimer.restart()
    }
    stdout: SplitParser {
      onRead: function(line) { root.acceptUpdate(line) }
    }
  }

  Timer {
    id: restartTimer
    interval: 3000
    repeat: false
    onTriggered: if (!watcher.running) watcher.running = true
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰍽"
    fontFamily: "JetBrainsMono Nerd Font Mono"
    labelText: root.vertical ? "" : root.label
    slotSize: root.vertical ? Style.bar.iconSlot : Math.max(Style.bar.iconSlot * 2,
      labelWidth + Style.bar.iconCanvas + Style.space(12))
    active: root.critical
    dimmed: !root.available
    interactive: true
    pressable: false
    tooltipText: root.tooltip
  }
}
