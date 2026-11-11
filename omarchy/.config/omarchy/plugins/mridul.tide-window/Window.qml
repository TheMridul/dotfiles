import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui

// The focused window as "App  title". The app name is dimmed and the title
// loses the " - App Name" suffix most apps append, so the useful part fits.
BarWidget {
  id: root
  moduleName: "mridul.tide-window"

  readonly property var toplevel: ToplevelManager.activeToplevel
  readonly property string appId: toplevel ? String(toplevel.appId || "") : ""
  readonly property string rawTitle: toplevel ? String(toplevel.title || "") : ""
  readonly property int maxLabelWidth: Number(setting("maxWidth", 360))

  // "brave-origin" -> "Brave", "org.gnome.Nautilus" -> "Nautilus",
  // "foot" -> "Foot".
  readonly property string appName: {
    var id = appId
    if (id === "") return ""
    var parts = id.split(".")
    id = parts[parts.length - 1]
    id = id.split(/[-_]/)[0]
    return id.charAt(0).toUpperCase() + id.slice(1)
  }

  readonly property string title: {
    var t = rawTitle
    var name = appName.toLowerCase()
    var cut = Math.max(t.lastIndexOf(" - "), t.lastIndexOf(" — "))
    if (cut > 0 && name !== "" && t.slice(cut + 3).toLowerCase().indexOf(name) !== -1) t = t.slice(0, cut)
    return t.replace(/ - /g, " · ")
  }

  readonly property color fg: root.bar ? root.bar.barForeground : Color.foreground

  visible: toplevel !== null && (title !== "" || appName !== "") && !vertical
  implicitWidth: visible ? Math.min(maxLabelWidth, content.implicitWidth) + Style.space(18) : 0
  implicitHeight: barSize

  Behavior on implicitWidth {
    NumberAnimation { duration: Style.duration(200); easing.type: Easing.OutCubic }
  }

  // A hairline between the workspaces and the title.
  Rectangle {
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    width: 1
    height: Math.round(root.barSize * 0.4)
    color: root.fg
    opacity: root.visible ? 0.18 : 0
  }

  Item {
    anchors.fill: parent
    anchors.leftMargin: Style.space(10)
    anchors.rightMargin: Style.space(8)
    clip: true

    FontMetrics { id: titleMetrics; font: titleLabel.font }

    Row {
      id: content
      anchors.verticalCenter: parent.verticalCenter
      anchors.verticalCenterOffset: (titleMetrics.descent - titleMetrics.ascent + titleMetrics.tightBoundingRect("0").height) / 2
      spacing: Style.space(7)
      opacity: root.visible ? 1 : 0

      Text {
        id: appLabel
        renderType: Text.NativeRendering
        textFormat: Text.PlainText
        text: root.appName
        // Hidden when the title already names the app ("T3 Code (Beta)").
        visible: text !== "" && root.title.toLowerCase().replace(/[^a-z0-9]/g, "").indexOf(text.toLowerCase().replace(/[^a-z0-9]/g, "")) === -1
        color: Color.accent
        opacity: 0.85
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.body
      }

      Text {
        id: titleLabel
        renderType: Text.NativeRendering
        textFormat: Text.PlainText
        text: root.title
        width: Math.min(implicitWidth, root.maxLabelWidth - (appLabel.visible ? appLabel.implicitWidth + content.spacing : 0))
        elide: Text.ElideRight
        color: root.fg
        opacity: 0.9
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.body
      }
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.MiddleButton
    cursorShape: Qt.PointingHandCursor
    onClicked: function(mouse) {
      if (!root.toplevel) return
      if (mouse.button === Qt.MiddleButton) root.toplevel.close()
      else root.toplevel.activate()
    }
    onEntered: if (root.bar) root.bar.showTooltip(root, root.rawTitle)
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
