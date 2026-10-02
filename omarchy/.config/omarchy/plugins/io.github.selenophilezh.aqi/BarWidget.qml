import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

// Thin bar-slot host. All state and fetching live in Panel.qml; this file
// just wires the bar's injected properties through to it and renders the
// pill button, mirroring the built-in Weather plugin's BarWidget/Panel split.
BarWidget {
  id: root
  moduleName: "io.github.selenophilezh.aqi"

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  function refresh() {
    if (panelLoader.item && panelLoader.item.refresh) panelLoader.item.refresh()
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  // Shape contract for shell.summon/hide/toggle routing (Bar.findPanelWidget
  // requires open/close/opened on the bar-widget root); the base Panel item
  // already implements these, so we just forward.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.open) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  visible: panelLoader.item && panelLoader.item.label !== ""
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  WidgetButton {
    id: button
    bar: root.bar
    anchors.fill: parent
    text: panelLoader.item ? panelLoader.item.label : ""
    // Category color drives the pill text directly, same idiom the shell
    // uses for urgent/active states elsewhere — no custom background pill.
    foreground: panelLoader.item && panelLoader.item.labelColor
      ? panelLoader.item.labelColor
      : (bar ? bar.barForeground : Color.foreground)
    useActiveColor: false
    tooltipText: panelLoader.item ? panelLoader.item.tooltipText : ""

    onPressed: function(b) {
      if (!root.bar) return
      if (b === Qt.RightButton) {
        // Built from moduleName (== the plugin's install directory name)
        // rather than a second hardcoded literal, so it can't drift out of
        // sync with the id if the plugin is ever renamed.
        var scriptPath = Quickshell.env("HOME") + "/.config/omarchy/plugins/" + root.moduleName + "/aqi-status.sh"
        root.bar.run("omarchy-notification-send \"$(bash '" + scriptPath + "')\"")
      } else if (b === Qt.MiddleButton) root.refresh()
      else root.togglePanel()
    }
  }
}
