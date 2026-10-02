#!/bin/bash

# Prints a one-line AQI status string, e.g. "New York  ·  AQI 64  ·  Moderate"
# Used by the bar pill's right-click "send notification" action.
#
# Location: reuses the Weather plugin's state file
# (~/.local/state/omarchy/settings/weather.json) so there's nothing extra to
# configure. Falls back to IP-based auto-detect via wttr.in when unset,
# same as the panel does.

LOC_FILE="$HOME/.local/state/omarchy/settings/weather.json"

name=""
lat=""
lon=""
if [[ -f $LOC_FILE ]]; then
  name=$(jq -r '.name // "" | if type == "string" then . else "" end' "$LOC_FILE" 2>/dev/null)
  lat=$(jq -r '.latitude // "" | if type == "number" then . else "" end' "$LOC_FILE" 2>/dev/null)
  lon=$(jq -r '.longitude // "" | if type == "number" then . else "" end' "$LOC_FILE" 2>/dev/null)
fi

if [[ -z $lat || -z $lon ]]; then
  # --max-filesize/--limit-rate bound the reply curl will buffer; head -c is
  # a hard backstop regardless of what curl does with a chunked, length-less
  # response, since --max-time alone bounds duration, not size.
  area=$(curl -fsS --max-time 4 --max-filesize 2000000 --limit-rate 512k "https://wttr.in/?format=j1" 2>/dev/null | head -c 2000000)
  lat=$(jq -r '.nearest_area[0].latitude // ""' <<<"$area" 2>/dev/null)
  lon=$(jq -r '.nearest_area[0].longitude // ""' <<<"$area" 2>/dev/null)
  [[ -z $name ]] && name=$(jq -r '.nearest_area[0].areaName[0].value // ""' <<<"$area" 2>/dev/null)
fi

if [[ -z $lat || -z $lon ]]; then
  echo "Air quality unavailable"
  exit 1
fi

resp=$(curl -fsS --max-time 5 --max-filesize 2000000 --limit-rate 512k "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&current=us_aqi&timezone=auto" 2>/dev/null | head -c 2000000)
aqi=$(jq -r '.current.us_aqi // ""' <<<"$resp" 2>/dev/null)

if [[ -z $aqi ]]; then
  echo "Air quality unavailable"
  exit 1
fi

category="Good"
if   (( aqi > 300 )); then category="Hazardous"
elif (( aqi > 200 )); then category="Very Unhealthy"
elif (( aqi > 150 )); then category="Unhealthy"
elif (( aqi > 100 )); then category="Unhealthy for Sensitive Groups"
elif (( aqi > 50 ));  then category="Moderate"
fi

[[ -n $name ]] && name="${name^}  ·  "
echo "${name}AQI ${aqi}  ·  ${category}"
