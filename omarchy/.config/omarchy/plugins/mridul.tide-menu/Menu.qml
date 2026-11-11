import QtQuick
import qs.Commons
import qs.Ui

// The Omarchy menu button with the themridul.in favicon (its dark variant,
// rendered to PNG because Qt's SVG renderer drops the clip paths) in place of the
// Omarchy logo. Left click opens the menu, right click a terminal, as stock.
BarWidget {
  id: root
  moduleName: "mridul.tide-menu"

  readonly property real iconSize: Math.round(barSize * 0.62)

  implicitWidth: vertical ? barSize : iconSize + Style.space(14)
  implicitHeight: barSize

  Image {
    id: icon
    // Placed by hand: the bar hands widgets their width late, so centring on
    // the parent put the icon half outside the pill.
    x: Math.round((root.implicitWidth - width) / 2)
    anchors.verticalCenter: parent.verticalCenter
    width: root.iconSize
    height: width
    source: Qt.resolvedUrl("favicon.png")
    sourceSize.width: Math.round(width * Screen.devicePixelRatio)
    sourceSize.height: Math.round(height * Screen.devicePixelRatio)
    smooth: true
    scale: mouse.pressed ? 0.88 : (mouse.containsMouse ? 1.08 : 1)
    Behavior on scale { NumberAnimation { duration: Style.duration(160); easing.type: Easing.OutCubic } }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    cursorShape: Qt.PointingHandCursor
    onClicked: function(m) {
      if (!root.bar) return
      if (m.button === Qt.RightButton) root.bar.run("xdg-terminal-exec")
      else root.bar.run("omarchy-shell shell toggle omarchy.menu '{\"menu\":\"root\"}'")
    }
  }
}
