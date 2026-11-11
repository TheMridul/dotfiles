import QtQuick
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Takes no space itself. It finds the widgets of each bar section on its own
// screen and draws one surface behind each group: left, centre and right
// pills floating just inside the top edge.
//
// Use it with the bar background left "opaque": the widget sets the theme's
// `bar.background-alpha` to 0 at runtime so the full strip disappears while
// text keeps the theme colour. (A "none" bar samples the wallpaper and can
// switch to dark text, which is unreadable on a dark notch.) The original
// alpha is restored when the widget goes away, e.g. on the classic profile.
//
// The surfaces are parented to the bar window's root item at z -1, so they
// sit under the bar's (clear) strip and every widget, and share its
// coordinates. They follow the widgets live: any width or position change in
// a tracked widget, its slot or its section row re-measures on the next tick.
BarWidget {
  id: root
  moduleName: "mridul.tide-islands"

  implicitWidth: 0
  implicitHeight: barSize
  visible: true

  readonly property real padX: Number(setting("padding", 8))
  readonly property real inset: Number(setting("inset", 2))
  readonly property real edgeInset: Number(setting("edgeInset", 10))
  // ---- Theme overrides, applied while this widget lives and undone when
  //      it goes (e.g. on the classic profile). Caelestia-style: the full
  //      strip disappears, popups lose their hard border and take the same
  //      accent-tinted surface as the pills.
  readonly property color bg: Commons.Color.background
  readonly property color accent: Commons.Color.accent
  function tint(base, over, amount) { return Qt.tint(base, Util.alpha(over, amount)) }
  function hex(c) { return String(Qt.rgba(c.r, c.g, c.b, 1)) }
  readonly property var overrides: ({
    "bar.background-alpha": "0",
    "popups.border-alpha": "0",
    "popups.background": hex(tint(bg, accent, 0.06))
  })
  property var saved: ({})
  property bool overriding: false

  function applyOverride() {
    var values = Commons.Color.shellValues || {}
    var changed = false
    var keep = root.overriding ? root.saved : {}
    for (var key in overrides) {
      if (values[key] === overrides[key]) continue
      changed = true
      keep[key] = typeof values[key] === "string" ? values[key] : ""
    }
    if (!changed) return
    root.saved = keep
    var next = {}
    for (var k in values) next[k] = values[k]
    for (var o in overrides) next[o] = overrides[o]
    root.overriding = true
    Commons.Color.shellValues = next
  }
  function restoreOverride() {
    if (!root.overriding) return
    var values = Commons.Color.shellValues || {}
    var next = {}
    for (var k in values) if (!(k in overrides)) next[k] = values[k]
    for (var key in root.saved) if (root.saved[key] !== "") next[key] = root.saved[key]
    root.overriding = false
    Commons.Color.shellValues = next
  }
  onOverridesChanged: if (overriding) Qt.callLater(applyOverride)
  Connections {
    target: Commons.Color
    // A theme change replaces shellValues; take the new values and re-apply.
    function onShellValuesChanged() { if (root.overriding) Qt.callLater(root.applyOverride) }
  }
  readonly property string savedAlpha: saved["bar.background-alpha"] || ""

  readonly property real notchAlpha: {
    var n = Number(root.savedAlpha)
    return root.savedAlpha !== "" && isFinite(n) ? Util.clampAlpha(n) : 1
  }
  // Surface container: the theme background lifted a little toward the accent.
  readonly property color surface: Util.alpha(tint(bg, accent, 0.08), Math.min(notchAlpha, 0.94))

  readonly property var layout: root.bar && root.bar.layoutConfig ? root.bar.layoutConfig : ({})
  readonly property var groups: [
    ["left"],
    ["centerBegin", "center", "centerEnd"],
    ["right"]
  ]

  property Item canvas: null
  property var rects: [null, null, null]
  property var tracked: []

  function windowRoot() {
    var w = root.QsWindow.window
    return w ? w.contentItem : null
  }

  function idsFor(sections) {
    var ids = []
    for (var i = 0; i < sections.length; i++) {
      var list = layout[sections[i]] || []
      for (var j = 0; j < list.length; j++) {
        var id = typeof list[j] === "string" ? list[j] : (list[j] && list[j].id)
        if (id && id !== root.moduleName && ids.indexOf(id) === -1) ids.push(id)
      }
    }
    return ids
  }

  // Slot hosts in this bar window: the bar wraps each widget in a host that
  // carries `moduleName` and `activeItem`. The plugin API only lets a widget
  // look itself up, so the window's item tree is walked instead.
  property var hosts: []
  function findHosts() {
    var top = windowRoot()
    var found = []
    function walk(node, depth) {
      if (!node || depth > 14) return
      if (node.activeItem !== undefined && typeof node.moduleName === "string" && node !== root) {
        found.push(node)
        return
      }
      var kids = node.children || []
      for (var i = 0; i < kids.length; i++) walk(kids[i], depth + 1)
    }
    walk(top, 0)
    hosts = found
  }

  function itemsFor(sections) {
    var ids = idsFor(sections)
    var out = []
    for (var i = 0; i < hosts.length; i++) {
      if (ids.indexOf(hosts[i].moduleName) !== -1) out.push(hosts[i])
    }
    return out
  }

  function markDirty() { Qt.callLater(root.measure) }

  // Re-wire change signals to the current widgets and their slot and row.
  function rewire() {
    findHosts()
    for (var i = 0; i < tracked.length; i++) {
      var t = tracked[i]
      try { t.xChanged.disconnect(root.markDirty); t.widthChanged.disconnect(root.markDirty) } catch (e) {}
    }
    var next = []
    for (var g = 0; g < groups.length; g++) {
      var items = itemsFor(groups[g])
      for (var n = 0; n < items.length; n++) {
        var node = items[n]
        for (var depth = 0; node && depth < 3; depth++, node = node.parent) {
          if (next.indexOf(node) !== -1) continue
          node.xChanged.connect(root.markDirty)
          node.widthChanged.connect(root.markDirty)
          next.push(node)
        }
      }
    }
    tracked = next
    measure()
  }

  function measure() {
    var top = windowRoot()
    if (!top || root.vertical) return
    ensureCanvas(top)
    for (var g = 0; g < groups.length; g++) {
      var items = itemsFor(groups[g])
      var minX = Infinity, maxX = -Infinity
      for (var i = 0; i < items.length; i++) {
        var it = items[i]
        if (!it.visible || it.width < 0.5) continue
        var p = it.mapToItem(top, 0, 0)
        minX = Math.min(minX, p.x)
        maxX = Math.max(maxX, p.x + it.width)
      }
      var r = rects[g]
      if (!r) continue
      if (minX === Infinity) { r.shown = false; continue }
      r.targetX = Math.max(root.edgeInset, minX - root.padX)
      r.targetW = Math.min(top.width - root.edgeInset, maxX + root.padX) - r.targetX
      r.shown = true
    }
  }

  function ensureCanvas(top) {
    if (canvas && canvas.parent === top) return
    if (canvas) canvas.destroy()
    canvas = canvasComponent.createObject(top, { z: -1 })
    rects = [canvas.r0, canvas.r1, canvas.r2]
  }

  Component {
    id: canvasComponent
    Item {
      property alias r0: n0
      property alias r1: n1
      property alias r2: n2
      anchors.fill: parent
      Notch { id: n0 }
      Notch { id: n1 }
      Notch { id: n2 }
    }
  }

  component Notch: Rectangle {
    property bool shown: false
    property real targetX: 0
    property real targetW: 0
    x: targetX
    width: Math.max(0, targetW)
    // A floating pill, inset evenly so its middle is the bar's middle.
    y: root.inset
    height: root.barSize - 2 * root.inset
    color: root.surface
    radius: height / 2
    // A hairline lifts the pill off busy, light wallpapers. (A shadow would
    // be cut off: the bar window is only as tall as the bar.)
    border.width: 1
    border.color: Util.alpha(Commons.Color.foreground, 0.08)
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: Style.duration(250); easing.type: Easing.OutCubic } }
  }

  // Catches widgets that appear or are rebuilt (layout edits, plugin reloads).
  Timer {
    interval: 1500
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.rewire()
  }

  onLayoutChanged: rewire()
  Component.onCompleted: applyOverride()
  Component.onDestruction: {
    restoreOverride()
    for (var i = 0; i < tracked.length; i++) {
      try { tracked[i].xChanged.disconnect(root.markDirty); tracked[i].widthChanged.disconnect(root.markDirty) } catch (e) {}
    }
    if (canvas) canvas.destroy()
  }
}
