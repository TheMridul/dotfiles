import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Services.SystemTray
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Quick settings: the toggles you set yourself and the two sliders, so none
// of them needs its own bar icon. Each tile reads real state and flips it
// with the same command or shell service the stock widgets use.
Panel {
  id: root
  moduleName: "mridul.tide-vitals"
  ipcTarget: "mridul.tide-vitals"

  property Item anchorItem: null
  property var hostWidget: null
  // Hosted stock widgets whose full panels the tiles can open.
  property var bluetoothWidget: null

  readonly property color fg: bar ? bar.foreground : Commons.Color.foreground
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  readonly property var shellApi: bar ? bar.shell : null
  readonly property var notifications: shellApi && shellApi.firstPartyServiceFor ? shellApi.firstPartyServiceFor("omarchy.notifications") : null
  readonly property var nightlight: shellApi && shellApi.firstPartyServiceFor ? shellApi.firstPartyServiceFor("omarchy.nightlight") : null
  readonly property var idle: shellApi && shellApi.firstPartyServiceFor ? shellApi.firstPartyServiceFor("omarchy.idle") : null

  // ---- State read by polling a small shell script while the panel is open.
  property int volume: -1
  property bool volumeMuted: false
  property bool micMuted: false
  property int brightness: -1
  property bool bluetoothOn: false
  property bool tailscaleOn: false
  property bool tailscaleInstalled: false
  property string vpnState: "off"
  property bool vpnInstalled: false

  readonly property string vpnUnit: "openfortivpn@iiitd.service"

  function refresh() { if (!stateProc.running) stateProc.running = true }

  function run(argv) {
    actionProc.command = argv
    actionProc.running = true
  }

  Process {
    id: stateProc
    command: ["sh", "-c",
      "v=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null); echo \"vol $v\"; " +
      "m=$(wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null); echo \"mic $m\"; " +
      "echo \"bri $(brightnessctl -m 2>/dev/null | head -1 | cut -d, -f4)\"; " +
      "bluetoothctl show 2>/dev/null | grep -q 'Powered: yes' && echo bt on || echo bt off; " +
      "if command -v tailscale >/dev/null; then s=$(tailscale status --json 2>/dev/null | jq -r .BackendState 2>/dev/null); echo \"ts $s\"; else echo ts missing; fi; " +
      "if systemctl cat " + root.vpnUnit + " >/dev/null 2>&1; then echo \"vpn $(systemctl is-active " + root.vpnUnit + ")\"; else echo vpn missing; fi"]
    stdout: SplitParser {
      onRead: function(line) {
        var s = String(line).trim()
        var key = s.split(" ")[0]
        var rest = s.slice(key.length + 1)
        if (key === "vol") {
          var m = rest.match(/([0-9.]+)/)
          root.volume = m ? Math.round(parseFloat(m[1]) * 100) : -1
          root.volumeMuted = rest.indexOf("MUTED") !== -1
        } else if (key === "mic") {
          root.micMuted = rest.indexOf("MUTED") !== -1
        } else if (key === "bri") {
          var b = parseInt(rest, 10)
          root.brightness = isNaN(b) ? -1 : b
        } else if (key === "bt") {
          root.bluetoothOn = rest === "on"
        } else if (key === "ts") {
          root.tailscaleInstalled = rest !== "missing"
          root.tailscaleOn = rest === "Running"
        } else if (key === "vpn") {
          root.vpnInstalled = rest !== "missing"
          root.vpnState = rest === "active" ? "on" : (rest === "activating" ? "connecting" : "off")
        }
      }
    }
  }

  Process { id: actionProc; onExited: root.refresh() }

  Timer {
    interval: 2000
    running: root.opened
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // ---- Tiles. `on` is what the tile shows, `act` flips it.
  readonly property var tiles: [
    { key: "bluetooth", glyph: "󰂯", label: "Bluetooth", on: root.bluetoothOn,
      sub: root.bluetoothOn ? "on" : "off", more: root.bluetoothWidget !== null },
    { key: "mic", glyph: root.micMuted ? "󰍭" : "󰍬", label: "Microphone", on: !root.micMuted,
      sub: root.micMuted ? "muted" : "live" },
    { key: "dnd", glyph: "󰂛", label: "Do not disturb", on: root.notifications ? root.notifications.doNotDisturb : false,
      sub: (root.notifications && root.notifications.doNotDisturb) ? "on" : "off" },
    { key: "night", glyph: "󰔎", label: "Night light", on: root.nightlight ? root.nightlight.enabled : false,
      sub: (root.nightlight && root.nightlight.enabled) ? "on" : "off" },
    { key: "awake", glyph: "󰅶", label: "Stay awake", on: root.idle ? root.idle.stayAwake : false,
      sub: (root.idle && root.idle.stayAwake) ? "on" : "off" },
    { key: "tailscale", glyph: "󰖂", label: "Tailscale", on: root.tailscaleOn,
      sub: !root.tailscaleInstalled ? "not installed" : (root.tailscaleOn ? "connected" : "off") },
    { key: "vpn", glyph: "󰒃", label: "IIITD VPN", on: root.vpnState !== "off",
      sub: !root.vpnInstalled ? "not set up" : (root.vpnState === "on" ? "connected" : root.vpnState) }
  ]

  function activate(key) {
    if (key === "bluetooth") { root.bluetoothOn = !root.bluetoothOn; run(["bluetoothctl", "power", root.bluetoothOn ? "on" : "off"]) }
    else if (key === "mic") { root.micMuted = !root.micMuted; run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]) }
    else if (key === "dnd" && root.notifications) root.notifications.setDoNotDisturb(!root.notifications.doNotDisturb)
    else if (key === "night" && root.nightlight) root.nightlight.setNightlight(!root.nightlight.enabled)
    else if (key === "awake" && root.idle) root.idle.setIdleEnabled(root.idle.stayAwake)
    else if (key === "tailscale" && root.tailscaleInstalled) { root.tailscaleOn = !root.tailscaleOn; run(["tailscale", root.tailscaleOn ? "up" : "down"]) }
    else if (key === "vpn" && root.vpnInstalled) {
      var start = root.vpnState === "off"
      root.vpnState = start ? "connecting" : "off"
      run(["systemctl", start ? "start" : "stop", root.vpnUnit])
    }
  }

  function more(key) {
    if (key === "bluetooth" && root.bluetoothWidget) {
      root.close()
      Qt.callLater(function() { if (root.bluetoothWidget.open) root.bluetoothWidget.open() })
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight)

    content: PanelKeyCatcher {
      anchors.fill: parent
      implicitHeight: column.implicitHeight
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(12)

        Text {
          textFormat: Text.PlainText
          text: "Quick settings"
          color: root.fg
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.weight: Font.DemiBold
        }

        // Sliders.
        Repeater {
          model: [
            { key: "volume", glyph: root.volumeMuted ? "󰝟" : "󰕾", value: root.volume },
            { key: "brightness", glyph: "󰃠", value: root.brightness }
          ]
          RowLayout {
            required property var modelData
            width: column.width
            spacing: Style.space(10)
            visible: modelData.value >= 0
            // Optically centred, so the glyph's ink (not its line box) sits
            // on the slider track's axis.
            OpticalGlyph {
              Layout.preferredWidth: Style.space(22)
              Layout.preferredHeight: Style.space(22)
              Layout.alignment: Qt.AlignVCenter
              text: modelData.glyph
              fontFamily: "JetBrainsMono Nerd Font Mono"
              fontSize: Style.font.heading
              color: root.fg
              MouseArea {
                anchors.fill: parent
                enabled: modelData.key === "volume"
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.volumeMuted = !root.volumeMuted; root.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]) }
              }
            }
            PanelSlider {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              bar: root.bar
              minimum: 0
              maximum: 100
              step: 1
              integer: true
              value: Math.max(0, modelData.value)
              onReleased: function(v) {
                var n = Math.round(v)
                if (modelData.key === "volume") { root.volume = n; root.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", n + "%"]) }
                else { root.brightness = n; root.run(["omarchy-brightness-display", "--no-osd", n + "%"]) }
              }
            }
            Text {
              textFormat: Text.PlainText
              text: String(modelData.value)
              color: root.fg
              opacity: 0.6
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              horizontalAlignment: Text.AlignRight
              Layout.preferredWidth: Style.space(26)
            }
          }
        }

        // The system tray, folded in here so it takes no bar space. Left
        // click activates, right click opens the app's menu, middle click is
        // the app's secondary action.
        Flow {
          id: trayRow
          width: column.width
          spacing: Style.space(6)
          visible: SystemTray.items.values.length > 0

          Repeater {
            model: SystemTray.items
            Rectangle {
              id: trayTile
              required property var modelData
              width: Style.space(34)
              height: Style.space(34)
              radius: Style.cornerRadius > 0 ? Style.space(9) : 0
              color: Qt.tint(Commons.Color.background, Util.alpha(Commons.Color.accent, trayMouse.containsMouse ? 0.2 : 0.12))
              Behavior on color { ColorAnimation { duration: Style.duration(160) } }

              Image {
                anchors.centerIn: parent
                width: Style.space(18)
                height: width
                fillMode: Image.PreserveAspectFit
                sourceSize.width: Math.round(width * Screen.devicePixelRatio)
                sourceSize.height: Math.round(height * Screen.devicePixelRatio)
                source: String(trayTile.modelData.icon || "")
              }

              function showMenu(mouse) {
                var win = trayTile.QsWindow.window
                var p = trayTile.QsWindow.contentItem.mapFromItem(trayTile, mouse.x, mouse.y)
                trayTile.modelData.display(win, p.x, p.y)
              }

              MouseArea {
                id: trayMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                cursorShape: Qt.PointingHandCursor
                onClicked: function(mouse) {
                  var it = trayTile.modelData
                  if (mouse.button === Qt.RightButton || (mouse.button === Qt.LeftButton && it.onlyMenu)) trayTile.showMenu(mouse)
                  else if (mouse.button === Qt.MiddleButton) it.secondaryActivate()
                  else it.activate()
                }
                onEntered: if (root.bar) root.bar.showTooltip(trayTile, it_title(trayTile.modelData))
                onExited: if (root.bar) root.bar.hideTooltip(trayTile)
                function it_title(it) { return it.tooltipTitle || it.title || it.id || "" }
              }
            }
          }
        }

        GridLayout {
          width: column.width
          columns: 2
          columnSpacing: Style.space(8)
          rowSpacing: Style.space(8)

          Repeater {
            model: root.tiles
            Rectangle {
              id: tile
              required property var modelData
              Layout.fillWidth: true
              Layout.preferredHeight: Style.space(46)
              radius: Style.cornerRadius > 0 ? Style.space(10) : 0
              // Tiles that are on take the accent; text on it is picked by
              // contrast, so pale accents from generated themes stay legible.
              readonly property color onColor: Commons.Color.accent
              readonly property color ink: tile.modelData.on ? root.inkOn(onColor) : root.fg
              color: tile.modelData.on ? onColor : Qt.tint(Commons.Color.background, Util.alpha(Commons.Color.accent, tileMouse.containsMouse ? 0.2 : 0.12))
              Behavior on color { ColorAnimation { duration: Style.duration(180); easing.type: Easing.OutCubic } }

              Text {
                id: tileGlyph
                anchors.left: parent.left
                anchors.leftMargin: Style.space(12)
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: tile.modelData.glyph
                color: tile.ink
                font.family: "JetBrainsMono Nerd Font Mono"
                font.pixelSize: Style.font.icon
              }
              Column {
                anchors.left: tileGlyph.right
                anchors.leftMargin: Style.space(10)
                anchors.right: moreButton.visible ? moreButton.left : parent.right
                anchors.rightMargin: Style.space(6)
                anchors.verticalCenter: parent.verticalCenter
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  text: tile.modelData.label
                  elide: Text.ElideRight
                  color: tile.ink
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.weight: Font.DemiBold
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  text: tile.modelData.sub
                  elide: Text.ElideRight
                  color: tile.ink
                  opacity: 0.7
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
              MouseArea {
                id: tileMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.activate(tile.modelData.key)
              }
              Text {
                id: moreButton
                visible: tile.modelData.more === true
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.PlainText
                text: "›"
                color: tile.ink
                font.pixelSize: Style.font.title
                MouseArea {
                  anchors.fill: parent
                  anchors.margins: -Style.space(8)
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.more(tile.modelData.key)
                }
              }
            }
          }
        }
      }
    }
  }

  function luminance(c) {
    function lin(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
  }
  function contrast(a, b) {
    var la = luminance(a), lb = luminance(b)
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
  }
  function inkOn(fill) {
    return contrast(Commons.Color.background, fill) >= contrast(root.fg, fill) ? Commons.Color.background : root.fg
  }
}
