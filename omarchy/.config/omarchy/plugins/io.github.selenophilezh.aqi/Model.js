// Pure helpers for the AQI plugin: parsing, US AQI category/color mapping,
// and pollutant display metadata. Kept side-effect free so it can be unit
// tested outside Quickshell if needed (module.exports below).

// weather.json holds {"name": ..., "latitude": ..., "longitude": ...} (see
// omarchy-weather-location, which owns the format). This plugin reuses that
// same file read-only so users don't have to configure a location twice.
// Missing, blank, or unparseable means no configured coordinates; the panel
// falls back to IP-based auto-detect via wttr.in's nearest_area.
function parseLocationFile(raw) {
  var unset = { name: "", latitude: null, longitude: null }
  try {
    var data = JSON.parse(String(raw || ""))
    if (!data || typeof data !== "object") return unset

    var latitude = parseFloat(data.latitude)
    var longitude = parseFloat(data.longitude)
    var hasCoordinates = !isNaN(latitude) && !isNaN(longitude)
    return {
      name: typeof data.name === "string" ? data.name.replace(/^\s+|\s+$/g, "") : "",
      latitude: hasCoordinates ? latitude : null,
      longitude: hasCoordinates ? longitude : null
    }
  } catch (e) {
    return unset
  }
}

// Open-Meteo geocoding response → suggestion rows for the location picker.
function parseGeocodingResults(raw) {
  try {
    var data = JSON.parse(String(raw || "{}"))
    var results = data.results
    if (!results || !results.length) return []

    var out = []
    for (var i = 0; i < results.length; i++) {
      var r = results[i]
      if (!r || !r.name || r.latitude === undefined || r.longitude === undefined) continue
      var region = [r.admin1, r.country].filter(function(part) { return !!part }).join(", ")
      out.push({
        name: String(r.name),
        description: region,
        latitude: r.latitude,
        longitude: r.longitude
      })
    }
    return out
  } catch (e) {
    return []
  }
}

function locationCommit(text, suggestions, selectedIndex) {
  var name = String(text || "").replace(/^\s+|\s+$/g, "")
  if (name === "") return { name: "", latitude: null, longitude: null }

  var choices = suggestions || []
  var index = Math.max(0, Math.min(parseInt(selectedIndex, 10) || 0, choices.length - 1))
  var suggestion = choices[index]
  if (suggestion) return suggestion

  return { name: name, latitude: null, longitude: null }
}

// wttr.in's j1 report (used only as an IP-geolocation fallback here) carries
// the detected area's name and coordinates in nearest_area[0].
function parseNearestArea(raw) {
  try {
    var data = JSON.parse(String(raw || "{}"))
    var area = data && data.nearest_area && data.nearest_area[0] ? data.nearest_area[0] : null
    if (!area) return null

    var latitude = parseFloat(area.latitude)
    var longitude = parseFloat(area.longitude)
    if (isNaN(latitude) || isNaN(longitude)) return null

    var name = area.areaName && area.areaName[0] ? String(area.areaName[0].value || "") : ""
    return { name: name, latitude: latitude, longitude: longitude }
  } catch (e) {
    return null
  }
}

// US AQI (EPA) breakpoints: 0-50 Good ... 301-500 Hazardous. Colors are
// toned-down variants of the official EPA palette, chosen to stay readable
// as text directly on the bar in both light and dark themes.
var CATEGORIES = [
  { max: 50, label: "Good", color: "#4caf50" },
  { max: 100, label: "Moderate", color: "#d4b106" },
  { max: 150, label: "Unhealthy for Sensitive Groups", color: "#ff8c00" },
  { max: 200, label: "Unhealthy", color: "#e53935" },
  { max: 300, label: "Very Unhealthy", color: "#8e24aa" },
  { max: Infinity, label: "Hazardous", color: "#6d2932" }
]

function categoryForUsAqi(aqi) {
  var n = parseFloat(String(aqi))
  if (isNaN(n)) return { label: "", color: "#888888" }
  for (var i = 0; i < CATEGORIES.length; i++) {
    if (n <= CATEGORIES[i].max) return CATEGORIES[i]
  }
  return CATEGORIES[CATEGORIES.length - 1]
}

// Display metadata for each pollutant the air-quality-api response carries,
// in the order they should render in the breakdown grid.
var POLLUTANTS = [
  { key: "pm2_5", subIndexKey: "us_aqi_pm2_5", label: "PM2.5" },
  { key: "pm10", subIndexKey: "us_aqi_pm10", label: "PM10" },
  { key: "ozone", subIndexKey: "us_aqi_ozone", label: "O₃" },
  { key: "nitrogen_dioxide", subIndexKey: "us_aqi_nitrogen_dioxide", label: "NO₂" },
  { key: "sulphur_dioxide", subIndexKey: "us_aqi_sulphur_dioxide", label: "SO₂" },
  { key: "carbon_monoxide", subIndexKey: "us_aqi_carbon_monoxide", label: "CO" }
]

function roundNum(value) {
  if (value === undefined || value === null || value === "") return null
  var n = parseFloat(String(value))
  return isNaN(n) ? null : Math.round(n)
}

function oneDecimal(value) {
  if (value === undefined || value === null || value === "") return null
  var n = parseFloat(String(value))
  return isNaN(n) ? null : Math.round(n * 10) / 10
}

// Parses an Open-Meteo /v1/air-quality response (current= block) into the
// shape the panel renders: overall AQI + category, and a breakdown row per
// pollutant with its own sub-index, concentration, and unit.
function parseAirQualityResponse(raw) {
  try {
    var data = JSON.parse(String(raw || "{}"))
    var current = data && data.current ? data.current : null
    if (!current || current.us_aqi === undefined || current.us_aqi === null) return null

    var units = data.current_units || {}
    var aqi = roundNum(current.us_aqi)
    if (aqi === null) return null

    var breakdown = []
    for (var i = 0; i < POLLUTANTS.length; i++) {
      var p = POLLUTANTS[i]
      breakdown.push({
        key: p.key,
        label: p.label,
        subIndex: roundNum(current[p.subIndexKey]),
        concentration: oneDecimal(current[p.key]),
        unit: units[p.key] || "µg/m³"
      })
    }

    return {
      aqi: aqi,
      category: categoryForUsAqi(aqi),
      time: current.time || "",
      dominant: dominantPollutant(breakdown, aqi),
      breakdown: breakdown
    }
  } catch (e) {
    return null
  }
}

// The pollutant whose sub-index matches (or comes closest to) the overall
// AQI is the one driving it, matching how the EPA defines the headline
// number as the max of the individual pollutant sub-indices.
function dominantPollutant(breakdown, aqi) {
  var best = null
  var bestDiff = Infinity
  for (var i = 0; i < breakdown.length; i++) {
    var entry = breakdown[i]
    if (entry.subIndex === null) continue
    var diff = Math.abs(entry.subIndex - aqi)
    if (diff < bestDiff) {
      bestDiff = diff
      best = entry.label
    }
  }
  return best || ""
}

if (typeof module !== "undefined") {
  module.exports = {
    parseLocationFile: parseLocationFile,
    parseGeocodingResults: parseGeocodingResults,
    locationCommit: locationCommit,
    parseNearestArea: parseNearestArea,
    categoryForUsAqi: categoryForUsAqi,
    roundNum: roundNum,
    oneDecimal: oneDecimal,
    parseAirQualityResponse: parseAirQualityResponse,
    dominantPollutant: dominantPollutant
  }
}
