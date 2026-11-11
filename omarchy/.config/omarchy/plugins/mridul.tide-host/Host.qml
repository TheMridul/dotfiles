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
// Arrive loud, settle quiet: a chip that appears shows its full width, then
// folds to `foldWidth` (its icon) after `foldAfter` ms. Hovering unfolds it.
// `pinIf` (same form as showIf) keeps it unfolded, e.g. for a failed job.
// Set "foldAfter": 0 to never fold.
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

  readonly property string pinIf: String(setting("pinIf", ""))
  readonly property int foldAfter: Number(setting("foldAfter", 3500))
  readonly property real foldWidth: Number(setting("foldWidth", Style.bar.iconSlot + Style.space(6)))

  property bool show: showIf === ""
  property var test: null
  property var pinTest: null
  property bool pinned: false
  property bool folded: false
  property bool hovered: false

  onPinIfChanged: {
    pinTest = null
    if (pinIf === "") { pinned = false; return }
    try { pinTest = new Function("item", "label", "return !!(" + pinIf + ")") }
    catch (e) { console.warn("mridul.tide-host: bad pinIf", pinIf, e) }
  }

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
    if (pinTest) {
      try { pinned = pinTest(item, firstLabel(item, 0)) } catch (e) { pinned = false }
    }
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
    running: root.showIf !== "" || root.pinIf !== ""
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

  // The host itself always stays `visible` (at zero width when hidden) so
  // the hosted widget's own `visible` keeps meaning what it says: an
  // invisible ancestor would force it false. A widget hides itself either by
  // `visible: false` or by reporting zero width.
  readonly property bool itemVisible: loader.item ? (loader.item.visible && loader.item.implicitWidth > 0) : false
  readonly property real fullWidth: (show && itemVisible && loader.item) ? loader.item.implicitWidth : 0
  readonly property bool canFold: foldAfter > 0 && fullWidth > foldWidth + Style.space(8)
  readonly property bool collapsed: canFold && folded && !hovered && !pinned && !opened
  readonly property real targetWidth: fullWidth > 0 ? (collapsed ? foldWidth : fullWidth) : 0
  property real shownWidth: targetWidth

  // Fold a while after arriving, and again a moment after the pointer leaves.
  onFullWidthChanged: {
    if (fullWidth <= 0) { folded = false; foldTimer.stop() }
    else if (!foldTimer.running && !folded) foldTimer.restart()
  }
  Timer { id: foldTimer; interval: Math.max(0, root.foldAfter); onTriggered: root.folded = true }
  Timer { id: refoldTimer; interval: 1200; onTriggered: root.hovered = false }
  HoverHandler {
    onHoveredChanged: {
      if (hovered) { refoldTimer.stop(); root.hovered = true }
      else refoldTimer.restart()
    }
  }
  Behavior on shownWidth {
    NumberAnimation {
      duration: root.targetWidth > 0 ? Style.duration(240) : Style.duration(150)
      easing.type: Easing.Bezier
      easing.bezierCurve: Style.easeOut
    }
  }

  visible: true
  implicitWidth: shownWidth
  implicitHeight: loader.item ? loader.item.implicitHeight : barSize
  clip: true

  Loader {
    id: loader
    source: root.source
    width: loader.item ? loader.item.implicitWidth : 0
    height: parent.height
    anchors.left: parent.left
    opacity: root.targetWidth > 0 ? 1 : 0
    scale: root.targetWidth > 0 ? 1 : 0.96
    Behavior on opacity { NumberAnimation { duration: Style.duration(root.targetWidth > 0 ? 200 : 120); easing.type: Easing.OutCubic } }
    Behavior on scale { NumberAnimation { duration: Style.duration(200); easing.type: Easing.OutCubic } }
    onLoaded: { root.inject(); Qt.callLater(root.inject); root.evaluate() }
    onStatusChanged: if (status === Loader.Error) console.warn("mridul.tide-host: cannot load", root.source)
  }
}
