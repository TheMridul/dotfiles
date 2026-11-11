import QtQuick
import qs.Commons

// The shell takes its corner radius from Hyprland's `decoration:rounding`, so
// with square windows every popup, tooltip, menu and toggle is square too.
// Style.cornerRadius is used only by shell UI, never by windows, so pinning
// it here rounds the shell and leaves the windows alone. Style re-reads
// Hyprland on a config reload; the Connections puts the radius back.
Item {
  id: root
  visible: false

  property var settings: ({})
  readonly property int radius: {
    var n = Number(settings && settings.radius)
    return isFinite(n) && n >= 0 && settings && settings.radius !== undefined ? n : 10
  }

  function apply() { if (Style.cornerRadius !== root.radius) Style.cornerRadius = root.radius }

  Component.onCompleted: apply()
  onRadiusChanged: apply()

  Connections {
    target: Style
    function onCornerRadiusChanged() { Qt.callLater(root.apply) }
  }
}
