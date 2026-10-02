import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "io.github.selenophilezh.aqi"
  ipcTarget: "io.github.selenophilezh.aqi"
  manageIpc: true

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  // ---- Bar pill state, read by BarWidget.qml -------------------------------
  property string label: "…"
  property color labelColor: bar ? bar.barForeground : Color.foreground
  property string tooltipText: "Air Quality"

  // ---- Fetched data ----------------------------------------------------
  // Kept on failure so stale data stays visible rather than blanking out.
  property var report: null
  property string errorMessage: ""

  // ---- Click-to-edit state for the location label, mirroring the Weather
  // plugin's picker so location can be changed from either panel.
  property bool editingLocation: false
  property bool savingLocation: false
  property bool savingLocationQueryStarted: false
  property var locationSuggestions: []
  property int suggestionIndex: 0
  property string geocodePendingQuery: ""
  property string geocodeActiveQuery: ""

  // Configured location, read from the same state file the Weather plugin
  // owns (~/.local/state/omarchy/settings/weather.json), so users only set
  // a location once. A watch makes hand edits (or Weather's own picker)
  // take effect live.
  property var configuredLocationState: ({ name: "", latitude: null, longitude: null })
  // IP-based auto-detect fallback, resolved via wttr.in when no coordinates
  // are configured. Not persisted anywhere — re-resolved each session.
  property var detectedLocationState: ({ name: "", latitude: null, longitude: null })

  readonly property bool hasConfiguredCoordinates: configuredLocationState.latitude !== null && configuredLocationState.longitude !== null
  readonly property real effectiveLat: hasConfiguredCoordinates ? configuredLocationState.latitude : detectedLocationState.latitude
  readonly property real effectiveLon: hasConfiguredCoordinates ? configuredLocationState.longitude : detectedLocationState.longitude
  readonly property bool hasLocation: !isNaN(parseFloat(String(effectiveLat))) && !isNaN(parseFloat(String(effectiveLon)))
  readonly property string locationName: configuredLocationState.name || detectedLocationState.name

  // Watched instead of configuredLocationState directly: that property holds
  // a freshly-parsed object on every reload (even when nothing changed), and
  // object identity always differs, so watching it would re-trigger refresh()
  // every tick. This derived string only changes when the content does.
  readonly property string locationKey: configuredLocationState.name + "|" + configuredLocationState.latitude + "|" + configuredLocationState.longitude

  property FileView locationFile: FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/settings/weather.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.configuredLocationState = Model.parseLocationFile(text())
    onLoadFailed: root.configuredLocationState = Model.parseLocationFile("")
  }

  onLocationKeyChanged: Qt.callLater(refresh)

  function refresh() {
    locationFile.reload()
    if (root.hasConfiguredCoordinates) {
      fetchAirQuality()
    } else if (!detectProc.running) {
      detectProc.running = true
    }
  }

  // ---- Location editing. Clicking the location label swaps it for a search
  //      field; picking a geocoded suggestion persists name + coordinates via
  //      omarchy-weather-location, the same state file (and CLI) the Weather
  //      plugin owns — so either panel can change it and both stay in sync.
  function startEditingLocation() {
    editingLocation = true
    savingLocation = false
    savingLocationQueryStarted = false
    locationSuggestions = []
    suggestionIndex = 0
    Qt.callLater(function() {
      locationField.text = root.configuredLocationState.name || root.locationName
      locationField.selectAll()
      locationField.forceActiveFocus()
    })
  }

  function cancelEditingLocation() {
    editingLocation = false
    savingLocation = false
    savingLocationQueryStarted = false
    locationSuggestions = []
    geocodeDebounce.stop()
    Qt.callLater(function() { if (keyCatcher) keyCatcher.forceActiveFocus() })
  }

  function commitLocation() {
    var location = Model.locationCommit(locationField.text, locationSuggestions, suggestionIndex)
    if (location.name === "") {
      clearLocation()
      return
    }
    savingLocation = true
    savingLocationQueryStarted = false
    configuredLocationState = {
      name: location.name,
      latitude: location.latitude,
      longitude: location.longitude
    }
    persistLocation(location.name, location.latitude, location.longitude)
  }

  function clearLocation() {
    persistLocation("", null, null)
    detectedLocationState = { name: "", latitude: null, longitude: null }
    cancelEditingLocation()
  }

  function pickSuggestion(suggestion) {
    if (!suggestion) return
    savingLocation = true
    savingLocationQueryStarted = false
    configuredLocationState = {
      name: suggestion.name,
      latitude: suggestion.latitude,
      longitude: suggestion.longitude
    }
    persistLocation(suggestion.name, suggestion.latitude, suggestion.longitude)
  }

  function finishSavingLocation() {
    if (savingLocation && savingLocationQueryStarted) cancelEditingLocation()
  }

  function persistLocation(name, latitude, longitude) {
    if (name && latitude !== null && longitude !== null)
      locationSaveProc.command = ["omarchy-weather-location", "--set", name, latitude + "," + longitude]
    else if (name)
      locationSaveProc.command = ["omarchy-weather-location", "--set", name]
    else
      locationSaveProc.command = ["omarchy-weather-location", "--clear"]
    locationSaveProc.running = true
  }

  // Debounced geocoding. Only one curl runs at a time; if the query moved on
  // while a fetch was in flight, the latest query is fetched right after.
  function requestGeocode() {
    var query = locationField.text.trim()
    if (query.length < 2) {
      locationSuggestions = []
      return
    }
    geocodePendingQuery = query
    if (!geocodeProc.running) startGeocode()
  }

  function startGeocode() {
    geocodeActiveQuery = geocodePendingQuery
    // --max-filesize catches an oversized reply up front when the server
    // reports Content-Length; --limit-rate is the real backstop, since it
    // caps worst-case bytes (rate × --max-time) even against a chunked,
    // length-less reply that --max-filesize can't see coming.
    geocodeProc.command = ["curl", "-fsS", "--max-time", "5", "--max-filesize", "1000000", "--limit-rate", "512k",
      "https://geocoding-api.open-meteo.com/v1/search?name=" + encodeURIComponent(geocodeActiveQuery) + "&count=5&language=en&format=json"]
    geocodeProc.running = true
  }

  Process {
    id: geocodeProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.locationSuggestions = root.editingLocation ? Model.parseGeocodingResults(text) : []
        root.suggestionIndex = 0
        if (root.geocodePendingQuery !== root.geocodeActiveQuery) Qt.callLater(root.startGeocode)
      }
    }
  }

  Timer {
    id: geocodeDebounce
    interval: 300
    onTriggered: root.requestGeocode()
  }

  Process {
    id: locationSaveProc
    onExited: function(exitCode) {
      if (exitCode !== 0 || !root.savingLocation) return
      // FileView handles changed locations. Explicitly refresh here too so
      // saving the already-active location cannot strand the spinner.
      locationFile.reload()
      if (!root.savingLocationQueryStarted) {
        root.savingLocationQueryStarted = true
        root.aqiRetries = 0
        aqiProc.running = false
        Qt.callLater(root.refresh)
      }
    }
  }

  function fetchAirQuality() {
    if (!root.hasLocation || aqiProc.running) return
    var url = "https://air-quality-api.open-meteo.com/v1/air-quality"
      + "?latitude=" + encodeURIComponent(String(root.effectiveLat))
      + "&longitude=" + encodeURIComponent(String(root.effectiveLon))
      + "&current=us_aqi,us_aqi_pm2_5,us_aqi_pm10,us_aqi_carbon_monoxide,us_aqi_nitrogen_dioxide,us_aqi_sulphur_dioxide,us_aqi_ozone,pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
      + "&timezone=auto"
    aqiProc.command = ["curl", "-fsS", "--max-time", "6", "--max-filesize", "2000000", "--limit-rate", "512k", url]
    aqiProc.running = true
  }

  function applyReport(parsed) {
    root.report = parsed
    root.errorMessage = ""
    root.label = String(parsed.aqi)
    root.labelColor = parsed.category.color
    root.tooltipText = "AQI " + parsed.aqi + " · " + parsed.category.label
      + (root.locationName ? " · " + root.locationName : "")
    root.finishSavingLocation()
  }

  function applyFailure() {
    root.errorMessage = "Air quality unavailable"
    if (!root.report) {
      root.label = "—"
      root.labelColor = bar ? bar.barForeground : Color.foreground
      root.tooltipText = "Air quality unavailable"
    }
    root.finishSavingLocation()
  }

  Process {
    id: aqiProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var parsed = Model.parseAirQualityResponse(String(text || ""))
        if (parsed) {
          root.aqiRetries = 0
          root.applyReport(parsed)
        } else {
          root.scheduleAqiRetry()
        }
      }
    }
  }

  property int aqiRetries: 0
  function scheduleAqiRetry() {
    if (aqiRetries >= 3) {
      root.applyFailure()
      return
    }
    aqiRetries++
    aqiRetryTimer.restart()
  }

  Timer {
    id: aqiRetryTimer
    interval: 2500
    onTriggered: root.fetchAirQuality()
  }

  // IP auto-detect fallback: same trick the Weather plugin's j1 fetch relies
  // on, reused here only for its nearest_area coordinates.
  Process {
    id: detectProc
    command: ["curl", "-fsS", "--max-time", "5", "--max-filesize", "2000000", "--limit-rate", "512k", "https://wttr.in/?format=j1"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var area = Model.parseNearestArea(String(text || ""))
        if (area) {
          root.detectedLocationState = area
          root.fetchAirQuality()
        } else {
          root.applyFailure()
        }
      }
    }
  }

  Timer {
    id: refreshTimer
    interval: Math.max(5, root.setting("refreshMinutes", 15)) * 60 * 1000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: Qt.callLater(refresh)

  // ------------------------------------------------------------------ popup
  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(aqiColumn.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: root.editingLocation
      onReturnRequested: root.startEditingLocation()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: aqiScroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: aqiColumn.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: aqiColumn
          width: aqiScroll.width
          spacing: Style.space(14)
          topPadding: Style.space(16)
          bottomPadding: Style.space(16)

          // ---- Hero: big AQI number + category, location underneath.
          Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Style.space(16)

            Text {
              text: root.report ? String(root.report.aqi) : "—"
              color: root.report ? root.report.category.color : (root.bar ? root.bar.foreground : Color.foreground)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: 56
              font.bold: true
            }

            Column {
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(2)

              Text {
                text: root.report ? root.report.category.label : root.errorMessage || "Loading…"
                color: root.report ? root.report.category.color : (root.bar ? root.bar.foreground : Color.foreground)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.display
                font.bold: true
              }
              Text {
                visible: root.report && root.report.dominant !== ""
                text: root.report ? "Dominant: " + root.report.dominant : ""
                color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.4)
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
              }
            }
          }

          // ---- Location: click the name to swap it for a search field.
          // Uses a MouseArea rather than TapHandler/HoverHandler for
          // reliability. Plain Item (not Row) as the container: Row is a
          // layout positioner and doesn't support anchoring its children, so
          // an anchors.fill MouseArea inside one would be undefined.
          Item {
            visible: !root.editingLocation && root.locationName !== ""
            anchors.horizontalCenter: parent.horizontalCenter
            width: locationNameText.implicitWidth + Style.space(16)
            height: locationNameText.implicitHeight + Style.space(8)

            Text {
              id: locationNameText
              anchors.centerIn: parent
              text: (root.locationName || "").toUpperCase()
              color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.4)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.letterSpacing: 1
            }

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.startEditingLocation()
            }
          }

          Item {
            visible: !root.editingLocation && root.locationName === ""
            anchors.horizontalCenter: parent.horizontalCenter
            width: setLocationText.implicitWidth + Style.space(16)
            height: setLocationText.implicitHeight + Style.space(8)

            Text {
              id: setLocationText
              anchors.centerIn: parent
              text: "SET LOCATION"
              color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.4)
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.letterSpacing: 1
            }

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.startEditingLocation()
            }
          }

          Row {
            visible: root.editingLocation
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Style.space(6)

            TextField {
              id: locationField
              width: Style.space(200)
              enabled: !root.savingLocation
              placeholderText: "Search city"
              foreground: root.bar ? root.bar.foreground : Color.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family

              onTextChanged: if (root.editingLocation && !root.savingLocation) geocodeDebounce.restart()

              Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Escape) {
                  root.cancelEditingLocation()
                  event.accepted = true
                } else if (event.key === Qt.Key_Down) {
                  if (root.suggestionIndex < root.locationSuggestions.length - 1) root.suggestionIndex++
                  event.accepted = true
                } else if (event.key === Qt.Key_Up) {
                  if (root.suggestionIndex > 0) root.suggestionIndex--
                  event.accepted = true
                } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                  root.commitLocation()
                  event.accepted = true
                }
              }
            }

            // Clear back to IP auto-detect. While a committed location is
            // loading, this same compact affordance becomes a spinner.
            Rectangle {
              width: Style.space(18)
              height: Style.space(18)
              anchors.verticalCenter: parent.verticalCenter
              radius: Math.min(4, Style.cornerRadius)
              color: !root.savingLocation && clearLocationArea.containsMouse
                ? Style.hoverFillFor(root.bar ? root.bar.foreground : Color.foreground, Color.accent) : "transparent"

              Text {
                anchors.centerIn: parent
                text: root.savingLocation ? "󰦖" : "✕"
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.4)
                font.pixelSize: Style.font.bodySmall

                RotationAnimator on rotation {
                  running: root.savingLocation
                  from: 0; to: 360
                  duration: 800
                  loops: Animation.Infinite
                }
              }

              MouseArea {
                id: clearLocationArea
                anchors.fill: parent
                enabled: !root.savingLocation
                hoverEnabled: true
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: root.clearLocation()
              }
            }
          }

          // ---- Geocoding suggestions while the location is being edited.
          Column {
            visible: root.editingLocation && !root.savingLocation && root.locationSuggestions.length > 0
            width: parent.width
            spacing: 0

            Repeater {
              model: root.locationSuggestions

              delegate: Rectangle {
                required property var modelData
                required property int index
                width: parent.width
                height: suggestionRow.implicitHeight + Style.space(12)
                radius: Style.cornerRadius
                color: index === root.suggestionIndex
                  ? Style.hoverFillFor(root.bar ? root.bar.foreground : Color.foreground, Color.accent) : "transparent"

                Row {
                  id: suggestionRow
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(16)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(8)

                  Text {
                    text: modelData.name
                    color: index === root.suggestionIndex
                      ? Style.hoverStateColor(root.bar ? root.bar.foreground : Color.foreground, Color.accent)
                      : (root.bar ? root.bar.foreground : Color.foreground)
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.body
                  }
                  Text {
                    visible: text !== ""
                    text: modelData.description
                    color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.5)
                    font.family: root.bar ? root.bar.fontFamily : Style.font.family
                    font.pixelSize: Style.font.bodySmall
                    anchors.verticalCenter: parent.verticalCenter
                  }
                }

                MouseArea {
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onPositionChanged: root.suggestionIndex = index
                  onClicked: root.pickSuggestion(modelData)
                }
              }
            }
          }

          Rectangle {
            width: parent.width
            height: Style.spacing.hairline
            color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.8)
          }

          // ---- Pollutant breakdown grid: label / sub-index / concentration.
          Grid {
            width: parent.width
            leftPadding: Style.space(16)
            rightPadding: Style.space(16)
            columns: 2
            rowSpacing: Style.space(10)
            columnSpacing: Style.space(20)

            Repeater {
              model: root.report ? root.report.breakdown : []

              delegate: Row {
                width: (aqiColumn.width - Style.space(52)) / 2
                spacing: Style.space(8)

                Text {
                  text: modelData.label
                  width: Style.space(48)
                  color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.3)
                  font.family: root.bar ? root.bar.fontFamily : Style.font.family
                  font.pixelSize: Style.font.body
                }
                Text {
                  text: modelData.subIndex !== null ? String(modelData.subIndex) : "—"
                  color: Model.categoryForUsAqi(modelData.subIndex).color
                  font.family: root.bar ? root.bar.fontFamily : Style.font.family
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
                Text {
                  text: modelData.concentration !== null ? modelData.concentration + " " + modelData.unit : ""
                  color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.5)
                  font.family: root.bar ? root.bar.fontFamily : Style.font.family
                  font.pixelSize: Style.font.body
                }
              }
            }
          }

          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.errorMessage !== "" && root.report
            text: root.errorMessage + " — showing last known reading"
            color: bar ? bar.urgent : Color.urgent
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.body
          }

          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Data: open-meteo.com  ·  US AQI"
            color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.8)
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.body
          }
        }
      }
    }
  }
}
