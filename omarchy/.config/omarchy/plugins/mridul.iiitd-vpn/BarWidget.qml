import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

BarWidget {
  id: root
  moduleName: "mridul.iiitd-vpn"

  readonly property string unit: "openfortivpn@iiitd.service"
  property string state: "off"
  property bool installed: true

  // "onlyWhenActive": true hides the widget while the VPN is off, so it only
  // takes bar space when there is something to say.
  readonly property bool onlyWhenActive: setting("onlyWhenActive", false) === true
  visible: !onlyWhenActive || (root.installed && root.state !== "off")
  implicitWidth: visible ? button.implicitWidth : 0
  implicitHeight: button.implicitHeight

  function refresh() {
    if (!poll.running) poll.running = true
  }

  function toggle() {
    var verb = root.state === "off" || root.state === "failed" ? "start" : "stop"
    if (verb === "start") root.state = "connecting"
    control.command = ["systemctl", verb, root.unit]
    control.running = true
  }

  Process {
    id: poll
    command: ["sh", "-c",
      "systemctl cat " + root.unit + " >/dev/null 2>&1 || { echo missing; exit; }; " +
      "s=$(systemctl is-active " + root.unit + "); " +
      "if [ \"$s\" = active ] && ls /sys/class/net | grep -q '^ppp'; then echo on; " +
      "elif [ \"$s\" = active ] || [ \"$s\" = activating ]; then echo connecting; " +
      "elif [ \"$s\" = failed ]; then echo failed; else echo off; fi"]
    stdout: SplitParser {
      onRead: function(line) {
        var s = String(line).trim()
        root.installed = s !== "missing"
        root.state = s === "missing" ? "off" : s
      }
    }
  }

  Process {
    id: control
    onExited: root.refresh()
  }

  Timer {
    interval: root.state === "connecting" ? 1000 : 4000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    fontSize: 16
    text: root.state === "on" ? "󰖂" : "󰖂"
    active: root.state === "on"
    dimmed: root.state === "off" || root.state === "failed" || !root.installed
    tooltipText: !root.installed ? "IIITD VPN not set up yet"
      : root.state === "on" ? "IIITD VPN connected (click to disconnect)"
      : root.state === "connecting" ? "IIITD VPN connecting…"
      : root.state === "failed" ? "IIITD VPN failed (journalctl -u openfortivpn@iiitd). Click to retry"
      : "IIITD VPN off (click to connect)"
    onPressed: function(b) {
      if (root.installed) root.toggle()
    }
  }
}
