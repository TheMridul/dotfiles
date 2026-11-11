import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

// The time, alone, until the pointer rests on it. Then it grows from its
// centre: the date on the left, weather and air quality on the right. The two
// sides are kept the same width so the time itself never moves.
//
// The clock, weather and AQI are the existing widgets, hosted here, so their
// panels (calendar, forecast, AQI detail) open exactly as before.
BarWidget {
  id: root
  moduleName: "mridul.tide-clock"
  fixedEdge: "center"

  readonly property string clockSource: setting("clockSource", "qs:///usr/share/omarchy/shell/plugins/panels/clock/BarWidget.qml")
  readonly property string weatherSource: setting("weatherSource", Qt.resolvedUrl("../mridul.weather/BarWidget.qml"))
  readonly property string aqiSource: setting("aqiSource", Qt.resolvedUrl("../io.github.selenophilezh.aqi/BarWidget.qml"))
  readonly property string dateFormat: setting("dateFormat", "ddd d MMM")

  readonly property color fg: root.bar ? root.bar.barForeground : Color.foreground

  // The stock bar shows every inactive indicator (screen record, reminders and
  // so on) whenever the pointer is near the centre. Tide keeps those in quick
  // settings, so the clock holds that reveal off. Stock panels clear the flag
  // when they close, so it is put back each time.
  readonly property bool revealSuppressed: root.bar ? root.bar.centerHoverRevealSuppressed === true : true
  function suppressReveal() {
    if (root.bar && typeof root.bar.setCenterHoverRevealSuppressed === "function")
      root.bar.setCenterHoverRevealSuppressed(true)
  }
  onRevealSuppressedChanged: if (!revealSuppressed) Qt.callLater(root.suppressReveal)
  Component.onCompleted: Qt.callLater(root.suppressReveal)
  Component.onDestruction: {
    if (root.bar && typeof root.bar.setCenterHoverRevealSuppressed === "function")
      root.bar.setCenterHoverRevealSuppressed(false)
  }

  // Held open while hovered, while any hosted panel is open, and briefly
  // after the pointer leaves so it can travel between the pieces.
  readonly property bool panelOpen: [clockLoader, weatherLoader, aqiLoader].some(function(l) {
    return l.item && l.item.opened === true
  })
  property bool hovered: false
  readonly property bool expanded: !vertical && (hovered || panelOpen || leaveTimer.running)

  Timer { id: leaveTimer; interval: 350 }
  HoverHandler {
    onHoveredChanged: {
      root.hovered = hovered
      if (!hovered) leaveTimer.restart()
    }
  }

  function injectInto(item, settings) {
    if (!item) return
    item.bar = root.bar
    item.settings = settings
  }
  function inject() {
    root.injectInto(clockLoader.item, root.setting("clock", { format: "HH:mm", formatAlt: "ddd d MMM HH:mm" }))
    root.injectInto(weatherLoader.item, root.setting("weather", {}))
    root.injectInto(aqiLoader.item, root.setting("aqi", {}))
  }
  onBarChanged: { inject(); Qt.callLater(root.suppressReveal) }
  onSettingsChanged: inject()

  // Same contract as the stock clock, so `shell toggle` style IPC and the
  // bar's popout switching still find the calendar.
  readonly property bool opened: clockLoader.item ? clockLoader.item.opened === true : false
  function open() { if (clockLoader.item) clockLoader.item.open() }
  function close() { if (clockLoader.item) clockLoader.item.close() }
  readonly property bool popoutSwitchClosing: clockLoader.item ? clockLoader.item.popoutSwitchClosing === true : false
  function closeForPopoutSwitch() { if (clockLoader.item) clockLoader.item.closeForPopoutSwitch() }

  readonly property real dateWidth: dateLabel.implicitWidth + Style.space(10)
  readonly property real extrasWidth: extrasRow.implicitWidth
  readonly property real sideWidth: Math.max(dateWidth, extrasWidth)
  property real reveal: expanded ? 1 : 0
  Behavior on reveal {
    NumberAnimation {
      duration: root.expanded ? Style.duration(240) : Style.duration(160)
      easing.type: Easing.Bezier
      easing.bezierCurve: Style.easeOut
    }
  }

  readonly property real clockWidth: clockLoader.item ? clockLoader.item.implicitWidth : 0
  implicitWidth: vertical ? (clockLoader.item ? clockLoader.item.implicitWidth : barSize) : clockWidth + 2 * sideWidth * reveal
  implicitHeight: clockLoader.item ? clockLoader.item.implicitHeight : barSize

  Item {
    id: dateSide
    clip: true
    x: 0
    width: root.sideWidth * root.reveal
    height: parent.height
    Text {
      id: dateLabel
      anchors.verticalCenter: parent.verticalCenter
      anchors.verticalCenterOffset: (dateMetrics.descent - dateMetrics.ascent + dateMetrics.tightBoundingRect("0").height) / 2
      renderType: Text.NativeRendering
      anchors.right: parent.right
      anchors.rightMargin: Style.space(2)
      textFormat: Text.PlainText
      text: (clockLoader.item && clockLoader.item.displayDate ? clockLoader.item.displayDate : new Date()).toLocaleString(Qt.locale(I18n.formatLocale), root.dateFormat)
      color: root.fg
      opacity: 0.6 * root.reveal
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.body
    }
    FontMetrics { id: dateMetrics; font: dateLabel.font }
  }

  Loader {
    id: clockLoader
    x: root.sideWidth * root.reveal
    width: root.clockWidth
    height: parent.height
    source: root.clockSource
    onLoaded: { root.inject(); Qt.callLater(root.inject) }
  }

  Item {
    id: extrasSide
    clip: true
    x: clockLoader.x + root.clockWidth
    width: root.sideWidth * root.reveal
    height: parent.height
    Row {
      id: extrasRow
      height: parent.height
      opacity: root.reveal
      Loader {
        id: weatherLoader
        height: parent.height
        // Weather Icons glyphs sit high after stock optical centring.
        y: Number(root.setting("weatherNudge", 3))
        width: item && item.visible ? item.implicitWidth : 0
        source: root.weatherSource
        onLoaded: { root.inject(); Qt.callLater(root.inject) }
      }
      // The AQI widget prints a bare number, which reads as a temperature
      // next to the weather glyph, so it gets a quiet label.
      Text {
        visible: aqiLoader.item !== null && aqiLoader.item.visible
        height: parent.height
        verticalAlignment: Text.AlignVCenter
        leftPadding: Style.space(4)
        renderType: Text.NativeRendering
        textFormat: Text.PlainText
        text: "AQI"
        color: root.fg
        opacity: 0.5
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.caption
      }
      Loader {
        id: aqiLoader
        height: parent.height
        width: item && item.visible ? item.implicitWidth : 0
        source: root.aqiSource
        onLoaded: { root.inject(); Qt.callLater(root.inject) }
      }
    }
  }
}
