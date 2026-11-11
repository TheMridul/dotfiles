import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// One pill on the right of the bar: network, volume and battery, each still
// the stock widget with its own full panel, inside a single capsule, then a
// button for quick settings. Bluetooth is hosted out of sight so its full
// panel can still be opened from the quick-settings tile.
BarWidget {
  id: root
  moduleName: "mridul.tide-vitals"

  // Fresh clones made with `omarchy plugin clone`; widgets loaded straight
  // from /usr/share cannot resolve their inline components from a user plugin.
  readonly property string base: Qt.resolvedUrl("../mridul.")
  readonly property var shown: setting("widgets", ["network", "audio", "power"])
  readonly property var nudge: setting("nudge", { "audio": 1.25 })
  readonly property color fg: root.bar ? root.bar.barForeground : Commons.Color.foreground

  function inject() {
    for (var i = 0; i < hosts.count; i++) {
      var l = hosts.itemAt(i)
      if (l && l.item) { l.item.bar = root.bar; l.item.settings = root.setting(l.name, {}) }
    }
    if (bluetoothLoader.item) { bluetoothLoader.item.bar = root.bar; bluetoothLoader.item.settings = root.setting("bluetooth", {}) }
    if (monitorLoader.item) { monitorLoader.item.bar = root.bar; monitorLoader.item.settings = root.setting("monitor", {}) }
    root.shareMedia()
    var q = quickLoader.item
    if (q) {
      q.bar = root.bar
      q.anchorItem = quickButton
      q.hostWidget = root
      q.bluetoothWidget = bluetoothLoader.item
    }
  }
  // Widgets hosted here get a bar handle without shell services, so the audio
  // clone's now-playing section has no media service of its own. The stock
  // media widget in the lane has one; find it in the bar and lend it over.
  function findMediaService(item, depth) {
    if (!item || depth > 14) return null
    if (item.moduleName === "omarchy.media" && item.mediaService) return item.mediaService
    var kids = item.children || []
    for (var i = 0; i < kids.length; i++) {
      var found = root.findMediaService(kids[i], depth + 1)
      if (found) return found
    }
    return null
  }
  function shareMedia() {
    var win = root.QsWindow.window
    var service = win ? root.findMediaService(win.contentItem, 0) : null
    for (var i = 0; i < hosts.count; i++) {
      var l = hosts.itemAt(i)
      if (l && l.item && l.item.mediaServiceOverride !== undefined && l.item.mediaServiceOverride !== service)
l.item.mediaServiceOverride = service
    }
  }
  Timer { interval: 3000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.shareMedia() }

  onBarChanged: inject()
  onSettingsChanged: inject()

  // Panel contract, for the quick-settings panel.
  readonly property bool opened: quickLoader.item ? quickLoader.item.opened === true : false
  function open() { if (quickLoader.item) quickLoader.item.open() }
  function close() { if (quickLoader.item) quickLoader.item.close() }
  readonly property bool popoutSwitchClosing: quickLoader.item ? quickLoader.item.popoutSwitchClosing === true : false
  function closeForPopoutSwitch() { if (quickLoader.item) quickLoader.item.closeForPopoutSwitch() }

  readonly property real padX: Style.space(4)
  implicitWidth: vertical ? barSize : row.implicitWidth + padX * 2
  implicitHeight: vertical ? row.implicitHeight : barSize

  Rectangle {
    anchors.fill: parent
    anchors.topMargin: Math.round(root.barSize * 0.14)
    anchors.bottomMargin: anchors.topMargin
    anchors.leftMargin: Style.space(2)
    anchors.rightMargin: Style.space(2)
    radius: height / 2
    color: Qt.tint(Commons.Color.background, Util.alpha(Commons.Color.accent, root.opened ? 0.28 : 0.16))
    Behavior on color { ColorAnimation { duration: Style.duration(160) } }
  }

  Row {
    id: row
    x: root.padX
    height: root.barSize

    Repeater {
      id: hosts
      model: root.shown
      Loader {
        required property string modelData
        readonly property string name: modelData
        height: row.height
        width: item ? item.implicitWidth : 0
        // Optical nudge in logical px: the speaker glyph's ink is shorter
        // than its neighbours' and the stock widget does not compensate.
        y: Number(root.nudge[modelData] || 0)
        source: root.base + modelData + "/Panel.qml"
        onLoaded: { root.inject(); Qt.callLater(root.inject) }
      }
    }

    BarIconButton {
      id: quickButton
      width: Style.bar.iconSlot
      height: row.height
      bar: root.bar
      text: "󰒓"
      fontFamily: "JetBrainsMono Nerd Font Mono"
      slotSize: Style.bar.iconSlot
      tooltipText: "Quick settings"
      onPressed: function(b) { if (quickLoader.item) quickLoader.item.toggle() }
    }
  }

  // Out of sight, kept for its panel.
  Loader {
    id: bluetoothLoader
    x: quickButton.x + root.padX
    width: 1
    height: row.height
    opacity: 0
    source: root.base + "bluetooth/Panel.qml"
    onLoaded: { root.inject(); Qt.callLater(root.inject) }
  }

  // Also out of sight: the display panel, so Super+Ctrl+D still opens it.
  Loader {
    id: monitorLoader
    x: quickButton.x + root.padX
    width: 1
    height: row.height
    opacity: 0
    source: root.base + "monitor/Panel.qml"
    onLoaded: { root.inject(); Qt.callLater(root.inject) }
  }

  Loader {
    id: quickLoader
    source: Qt.resolvedUrl("QuickPanel.qml")
    visible: false
    onLoaded: { root.inject(); Qt.callLater(root.inject) }
  }
}
