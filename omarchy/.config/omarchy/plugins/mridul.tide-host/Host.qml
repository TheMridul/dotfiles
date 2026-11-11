import QtQuick
import qs.Commons
import qs.Ui

// Hosts another bar widget unchanged and lets it into the bar only while it
// has something to say. Used for widgets that are not ours to edit (stock
// Omarchy ones, third-party plugins) so they can live in the Tide lane.
//
// shell.json entry:
//   {
//     "id": "mridul.tide-host",
//     "key": "tailscale",                       // any name, for your own reference
//     "widgetSource": "../mridul.tailscale/Panel.qml",   // not "source": the bar claims that key
//     "showIf": "String(item.iconColor) === String(item.foreground)",
//     "widget": { ...settings passed to the hosted widget... }
//   }
//
// `showIf` is a JavaScript expression from your own shell.json, evaluated
// every couple of seconds with `item` (the hosted widget) and `label` (the
// first text it draws) in scope. Leave it out to always show the widget.
BarWidget {
  id: root
  moduleName: "mridul.tide-host"

  readonly property string rawSource: String(setting("widgetSource", ""))
  // Relative paths are taken from this plugin's directory, so a sibling
  // plugin is "../<plugin-id>/BarWidget.qml".
  readonly property string source: rawSource === "" || /^[a-z]+:/.test(rawSource) ? rawSource : Qt.resolvedUrl(rawSource)
  readonly property string showIf: String(setting("showIf", ""))
  readonly property int pollMs: Number(setting("pollMs", 2000))

  property bool show: showIf === ""
  property var test: null

  onShowIfChanged: {
    test = null
    if (showIf === "") { show = true; return }
    try {
      test = new Function("item", "label", "return !!(" + showIf + ")")
    } catch (e) {
      console.warn("mridul.tide-host: bad showIf", showIf, e)
    }
    evaluate()
  }

  function firstLabel(node, depth) {
    if (!node || depth > 6) return ""
    if (node.text !== undefined && typeof node.text === "string" && node.text !== "") return node.text
    var kids = node.children || []
    for (var i = 0; i < kids.length; i++) {
      var found = firstLabel(kids[i], depth + 1)
      if (found !== "") return found
    }
    return ""
  }

  function evaluate() {
    var item = loader.item
    if (!item) { show = false; return }
    if (!test) { show = showIf === ""; return }
    // A widget the user has a panel open on stays put until it closes.
    if (item.opened === true) { show = true; return }
    try {
      show = test(item, firstLabel(item, 0))
    } catch (e) {
      show = false
    }
  }

  Timer {
    interval: Math.max(500, root.pollMs)
    running: root.showIf !== ""
    repeat: true
    triggeredOnStart: true
    onTriggered: root.evaluate()
  }

  function inject() {
    var item = loader.item
    if (!item) return
    item.bar = root.bar
    item.settings = root.setting("widget", {})
  }
  onBarChanged: inject()
  onSettingsChanged: inject()

  // Forward the panel contract so the bar's popout switching treats the
  // hosted widget's panel like any other.
  readonly property bool opened: loader.item ? loader.item.opened === true : false
  function open() { if (loader.item && loader.item.open) loader.item.open() }
  function close() { if (loader.item && loader.item.close) loader.item.close() }
  readonly property bool popoutSwitchClosing: loader.item ? loader.item.popoutSwitchClosing === true : false
  function closeForPopoutSwitch() { if (loader.item && loader.item.closeForPopoutSwitch) loader.item.closeForPopoutSwitch() }

  // Not `item.visible`: that turns false whenever this host is hidden, which
  // would keep it hidden for good. A widget that hides itself reports zero
  // width instead.
  readonly property bool itemVisible: loader.item ? loader.item.implicitWidth > 0 : false
  readonly property real targetWidth: (show && itemVisible && loader.item) ? loader.item.implicitWidth : 0
  property real shownWidth: targetWidth
  Behavior on shownWidth {
    NumberAnimation {
      duration: root.targetWidth > 0 ? Style.duration(240) : Style.duration(150)
      easing.type: Easing.Bezier
      easing.bezierCurve: Style.easeOut
    }
  }

  visible: shownWidth > 0.5
  implicitWidth: shownWidth
  implicitHeight: loader.item ? loader.item.implicitHeight : barSize
  clip: true

  Loader {
    id: loader
    source: root.source
    width: loader.item ? loader.item.implicitWidth : 0
    height: parent.height
    anchors.right: parent.right
    opacity: root.targetWidth > 0 ? 1 : 0
    scale: root.targetWidth > 0 ? 1 : 0.96
    Behavior on opacity { NumberAnimation { duration: Style.duration(root.targetWidth > 0 ? 200 : 120); easing.type: Easing.OutCubic } }
    Behavior on scale { NumberAnimation { duration: Style.duration(200); easing.type: Easing.OutCubic } }
    onLoaded: { root.inject(); Qt.callLater(root.inject); root.evaluate() }
    onStatusChanged: if (status === Loader.Error) console.warn("mridul.tide-host: cannot load", root.source)
  }
}
