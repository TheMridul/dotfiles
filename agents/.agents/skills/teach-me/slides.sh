#!/usr/bin/env bash
# Page-accurate access to a lecture deck. Poppler only, no Python deps.
#   probe  <pdf>                    per-page text/image census + a verdict
#   text   <pdf> [first] [last]     text with === page N === markers
#   render <pdf> [first] [last] [dpi]  PNGs under /tmp/slides/<deck>/, prints paths
#   find   <pdf> <pattern>          which pages mention it, with context
set -euo pipefail

usage() { sed -n '2,7p' "$0" | sed 's/^# \?//'; exit 2; }
[ $# -ge 2 ] || usage
cmd=$1; pdf=$2; shift 2
[ -f "$pdf" ] || { echo "no such file: $pdf" >&2; exit 1; }

pages() { pdfinfo "$pdf" | awk '/^Pages:/{print $2}'; }
deck() { basename "$pdf" .pdf | tr -c 'A-Za-z0-9._-' '-'; }

case $cmd in
probe)
  n=$(pages)
  printf 'file    %s\n' "$pdf"
  pdfinfo "$pdf" | grep -E '^(Pages|Producer|Creator|Page size|Encrypted):' || true
  printf '\n%-5s %8s %7s  %s\n' page chars images verdict
  for p in $(seq 1 "$n"); do
    c=$(pdftotext -f "$p" -l "$p" "$pdf" - 2>/dev/null | tr -d '\f \t\n' | wc -c)
    i=$(pdfimages -list -f "$p" -l "$p" "$pdf" 2>/dev/null | tail -n +3 | wc -l)
    if   [ "$c" -lt 20 ];               then v='RENDER  no usable text layer'
    elif [ "$i" -ge 5 ];                then v='CHECK   text may be an OCR layer, render and compare'
    else                                     v='TEXT    extract normally'; fi
    printf '%-5s %8s %7s  %s\n' "$p" "$c" "$i" "$v"
  done
  ;;
text)
  f=${1:-1}; l=${2:-$(pages)}
  for p in $(seq "$f" "$l"); do
    printf '\n=== page %s ===\n' "$p"
    pdftotext -layout -f "$p" -l "$p" "$pdf" -
  done
  ;;
render)
  f=${1:-1}; l=${2:-$(pages)}; dpi=${3:-110}
  out=/tmp/slides/$(deck); mkdir -p "$out"
  pdftoppm -png -r "$dpi" -f "$f" -l "$l" "$pdf" "$out/p"
  ls -1 "$out"/p*.png
  ;;
find)
  pat=${1:?pattern required}
  n=$(pages)
  for p in $(seq 1 "$n"); do
    if pdftotext -f "$p" -l "$p" "$pdf" - 2>/dev/null | grep -iqE "$pat"; then
      printf '\n--- page %s ---\n' "$p"
      pdftotext -f "$p" -l "$p" "$pdf" - | grep -iE -A2 -B2 "$pat" | head -20
    fi
  done
  ;;
*) usage ;;
esac
