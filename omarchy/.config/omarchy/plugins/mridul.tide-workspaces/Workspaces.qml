import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "mridul.tide-workspaces"

  // Every monitor has workspaces 1-10 of its own, which Hyprland numbers in a
  // block of ten per monitor: 1-10, 11-20, and so on (see
  // default/hypr/monitor-workspaces.lua). Each bar shows its own monitor's block,
  // numbered 1-10, and the one that monitor shows, whichever monitor has focus.
  readonly property int slots: 10

  readonly property var monitor: {
    var window = root.QsWindow.window
    var screen = window ? window.screen : null
    return screen ? Hyprland.monitorFor(screen) : Hyprland.focusedMonitor
  }
  readonly property string monitorName: root.monitor ? root.monitor.name : ""

  // Connector -> block, from the file Hyprland keeps them in.
  property var blocks: ({})

  function readBlocks(text) {
    var next = {}
    var lines = String(text || "").split("\n")
    for (var i = 0; i < lines.length; i++) {
      var fields = lines[i].split("\t")
      if (fields.length >= 3 && fields[1] !== "") next[fields[1]] = parseInt(fields[0], 10)
    }
    root.blocks = next
  }

  FileView {
    path: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/omarchy/monitor-workspaces"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.readBlocks(text())
    onLoadFailed: root.readBlocks("")
  }

  function blockOf(id) {
    return Math.floor((id - 1) / root.slots)
  }

  function slotOf(id) {
    return (id - 1) % root.slots + 1
  }

  function activeWorkspaceId() {
    return root.monitor && root.monitor.activeWorkspace ? root.monitor.activeWorkspace.id : -1
  }

  // Until Hyprland has written the file, the workspace a monitor shows is in
  // its own block.
  readonly property int block: {
    var block = root.blocks[root.monitorName]
    if (block !== undefined) return block
    var active = root.activeWorkspaceId()
    return active > 0 ? root.blockOf(active) : 0
  }

  function workspaceById(id) {
    var values = Hyprland.workspaces.values
    for (var i = 0; i < values.length; i++) {
      if (values[i].id === id) return values[i]
    }

    return null
  }

  // The first five of the monitor's own, and any of the rest that exist. After
  // them come workspaces that are only visiting: those of a monitor that is
  // unplugged, which had no room to join this one's.
  function workspaceIds() {
    var base = root.block * root.slots
    var ids = [base + 1, base + 2, base + 3, base + 4, base + 5]
    var guests = []
    var values = Hyprland.workspaces.values

    for (var i = 0; i < values.length; i++) {
      var id = values[i].id
      if (id <= 0) continue
      if (root.blockOf(id) === root.block) {
        if (ids.indexOf(id) === -1) ids.push(id)
      } else if (values[i].monitor && values[i].monitor.name === root.monitorName) {
        guests.push(id)
      }
    }

    ids.sort(function(left, right) { return left - right })
    guests.sort(function(left, right) { return left - right })
    return ids.concat(guests)
  }

  function dispatch(expression) {
    if (root.bar) root.bar.run("hyprctl dispatch " + Util.shellQuote(expression))
  }

  function focusWorkspace(id) {
    if (root.blockOf(id) === root.block) {
      root.dispatch("o.workspaces.focus(" + root.slotOf(id) + ", \"" + root.monitorName + "\")")
    } else {
      root.dispatch("hl.dsp.focus({ workspace = \"" + id + "\" })")
    }
  }

  // A wheel notch moves one entry along the row, and a touchpad adds up its
  // smaller deltas until they make a notch's worth.
  property real wheelAccumulator: 0

  function scrollWorkspaces(delta) {
    var wheel = Util.wheelSteps(root.wheelAccumulator, delta)
    root.wheelAccumulator = wheel.remainder
    if (wheel.steps === 0) return

    // Holds at either end rather than wrapping, so a touchpad swipe that runs
    // long stops on the last workspace.
    var ids = root.workspaceIds()
    var index = ids.indexOf(root.activeWorkspaceId())
    if (index === -1) return
    var target = ids[Util.clamp(index - wheel.steps, 0, ids.length - 1)]
    if (target !== ids[index]) root.focusWorkspace(target)
  }

  // The workspace each monitor shows carries its layout: a square tiles, a
  // circle scrolls, and a triangle floats. Clicking it cycles to the next one,
  // as Super + L does.
  property string activeMode: "dwindle"
  property bool modeStale: false

  function modeGlyph(mode) {
    if (mode === "scrolling") return "󰝥"
    if (mode === "floating") return "󰔶"
    return "󱓻"
  }

  // A layout only changes through the layout commands, which ask for a refresh,
  // or a config reload, so each workspace's mode is read once and cached rather
  // than running the script on every workspace switch.
  property var modeCache: ({})
  property int modeGeneration: 0
  property int modeProcWorkspace: -1
  property int modeProcGeneration: 0

  function showActiveMode() {
    var mode = root.modeCache[root.activeWorkspaceId()]
    if (mode !== undefined) root.activeMode = mode
    else readMode()
  }

  function readMode() {
    if (modeProc.running) {
      root.modeStale = true
      return
    }
    var id = root.activeWorkspaceId()
    if (id === -1) return
    root.modeProcWorkspace = id
    root.modeProcGeneration = root.modeGeneration
    modeProc.command = ["omarchy-hyprland-workspace-layout-current", String(id)]
    modeProc.running = true
  }

  function refresh() {
    root.modeCache = ({})
    root.modeGeneration++
    readMode()
  }

  // The layout commands act on the focused workspace, so a click on another
  // monitor's bar focuses that monitor first.
  function cycleLayout() {
    if (!root.bar) return
    var command = "omarchy-hyprland-workspace-layout-toggle"
    if (root.monitor && !root.monitor.focused) {
      command = "hyprctl dispatch " + Util.shellQuote("hl.dsp.focus({ monitor = \"" + root.monitorName + "\" })") + " >/dev/null && " + command
    }
    root.bar.run(command)
  }

  Component.onCompleted: refresh()
  onMonitorChanged: root.showActiveMode()

  Connections {
    target: root.monitor
    function onActiveWorkspaceChanged() { root.showActiveMode() }
  }

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      var name = event ? String(event.name) : ""
      if (name === "configreloaded") root.refresh()
      // Quickshell credits every workspace switch to the focused monitor, as
      // the event doesn't say which one switched, and misses the workspace a
      // monitor falls back to when its own is moved away. Moving workspaces
      // between monitors switches the others, so ask Hyprland for the truth.
      // A workspace that changes number is only learned by asking too. Every
      // bar shares what Hyprland answers, so one asks after a plain switch.
      var switched = name === "workspacev2" && root.monitor !== null && root.monitor.focused
      if (switched || name === "moveworkspacev2" || name === "changeworkspaceid") {
        Hyprland.refreshMonitors()
        Hyprland.refreshWorkspaces()
      }
    }
  }

  Process {
    id: modeProc
    stdout: StdioCollector {
      onStreamFinished: {
        var mode = text.trim()
        // A read that started before a refresh may predate the change.
        if (!mode || root.modeProcGeneration !== root.modeGeneration) return
        root.modeCache[root.modeProcWorkspace] = mode
        if (root.modeProcWorkspace === root.activeWorkspaceId()) root.activeMode = mode
      }
    }
    onExited: {
      if (!root.modeStale) return
      root.modeStale = false
      // Deferred: the process still reports running while it signals exit.
      Qt.callLater(root.showActiveMode)
    }
  }

  // Super + L and the default layout change the mode without a focus change,
  // so they ask every bar to read it again.
  ShellIpc {
    target: "mridul.tide-workspaces"

    function refresh(): void { root.broadcast("refresh") }
  }


  // ---- Tide rendering. Occupied and shown workspaces print their number,
  //      empty ones shrink to a dot, and one accent pill slides to whichever
  //      is shown. The pill's text colour is picked by contrast so generated
  //      (Aether) themes with a pale accent stay readable.
  readonly property var ids: root.workspaceIds()
  readonly property int activeId: root.monitor && root.monitor.activeWorkspace ? root.monitor.activeWorkspace.id : -1
  readonly property int activeIndex: ids.indexOf(activeId)

  readonly property real cell: Style.space(18)
  readonly property real dotCell: Style.space(12)
  readonly property real pillHeight: Math.round(barSize * 0.66)
  readonly property real trailingGap: Style.spaceReal(1.5)
  readonly property bool animate: Style.duration(100) > 0

  function luminance(c) {
    function lin(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
  }
  function contrast(a, b) {
    var la = luminance(a), lb = luminance(b)
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
  }
  readonly property color fg: root.bar ? root.bar.barForeground : Color.foreground
  readonly property color pillColor: Color.accent
  readonly property color onPill: contrast(Color.background, pillColor) >= contrast(fg, pillColor) ? Color.background : fg

  function occupiedAt(id) {
    var ws = root.workspaceById(id)
    return ws !== null && ws.toplevels.values.length > 0
  }

  // Cells are laid out by hand so the pill can track an exact x.
  function cellWidth(id) {
    return (id === root.activeId || root.occupiedAt(id)) ? root.cell : root.dotCell
  }
  function cellX(index) {
    var x = 0
    for (var i = 0; i < index && i < root.ids.length; i++) x += root.cellWidth(root.ids[i])
    return x
  }

  implicitWidth: vertical ? barSize : row.width + trailingGap
  implicitHeight: vertical ? row.height : barSize

  Item {
    id: row
    width: root.cellX(root.ids.length)
    height: root.barSize
    anchors.verticalCenter: parent.verticalCenter

    Rectangle {
      id: pill
      visible: root.activeIndex >= 0
      height: root.pillHeight
      radius: height / 2
      color: root.pillColor
      anchors.verticalCenter: parent.verticalCenter
      width: root.cell
      x: root.activeIndex >= 0 ? root.cellX(root.activeIndex) : 0

      Behavior on x {
        enabled: root.animate
        SpringAnimation { spring: 5; damping: 0.42; epsilon: 0.25 }
      }
      Behavior on color { ColorAnimation { duration: Style.duration(250); easing.type: Easing.OutCubic } }
    }

    Repeater {
      model: root.ids

      Item {
        id: slotItem
        required property int modelData
        required property int index
        readonly property bool shown: modelData === root.activeId
        readonly property bool occupied: root.occupiedAt(modelData)
        readonly property bool showNumber: shown || occupied
        readonly property int slot: root.slotOf(modelData)

        x: root.cellX(index)
        width: root.cellWidth(modelData)
        height: root.barSize

        Behavior on x { enabled: root.animate; NumberAnimation { duration: Style.duration(180); easing.type: Easing.OutCubic } }
        Behavior on width { enabled: root.animate; NumberAnimation { duration: Style.duration(180); easing.type: Easing.OutCubic } }

        Text {
          id: numberLabel
          anchors.centerIn: parent
          // Centre the figures, not the line box (same formula as WidgetButton).
          anchors.verticalCenterOffset: (numberMetrics.descent - numberMetrics.ascent + numberMetrics.tightBoundingRect("0").height) / 2
          renderType: Text.NativeRendering
          textFormat: Text.PlainText
          text: slotItem.slot === root.slots ? "0" : String(slotItem.slot)
          color: slotItem.shown ? root.onPill : root.fg
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
          font.weight: slotItem.shown ? Font.DemiBold : Font.Normal
          opacity: slotItem.showNumber ? (slotItem.shown ? 1 : 0.75) : 0
          scale: slotItem.showNumber ? 1 : 0.6
          Behavior on opacity { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
          Behavior on scale { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
          Behavior on color { ColorAnimation { duration: Style.duration(160) } }
        }
        FontMetrics { id: numberMetrics; font: numberLabel.font }

        Rectangle {
          anchors.centerIn: parent
          width: Style.space(4)
          height: width
          radius: width / 2
          color: root.fg
          opacity: slotItem.showNumber ? 0 : 0.35
          scale: slotItem.showNumber ? 0.4 : 1
          Behavior on opacity { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
          Behavior on scale { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
        }

        MouseArea {
          anchors.fill: parent
          acceptedButtons: Qt.LeftButton
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            if (slotItem.shown) root.cycleLayout()
            else root.focusWorkspace(slotItem.modelData)
          }
          onWheel: function(wheel) { root.scrollWorkspaces(wheel.angleDelta.y) }
        }
      }
    }
  }
}
