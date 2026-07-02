#!/usr/bin/env bash
# Record a demo GIF of aegisvault for the README (Ubuntu).
#   sudo apt install ffmpeg wmctrl   (or use Peek: sudo apt install peek)
# 1) start the GUI:      aegisvault-gui --vault demo.fv &
# 2) run this script, then perform the demo flow (unlock -> add -> reveal ->
#    2FA -> health -> history). Ctrl+C to stop.
set -euo pipefail
OUT=${1:-docs/demo}
mkdir -p "$(dirname "$OUT")"
GEOM=$(wmctrl -lG | grep -i aegisvault | head -1 | awk '{print $5"x"$6"+"$3"+"$4}')
[ -z "$GEOM" ] && { echo "aegisvault window not found - launch the GUI first"; exit 1; }
SIZE=${GEOM%%+*}; POS=${GEOM#*+}; X=${POS%%+*}; Y=${POS#*+}
echo "recording ${SIZE} at +${X},${Y} - Ctrl+C to stop"
ffmpeg -y -f x11grab -video_size "$SIZE" -framerate 15 -i ":0.0+${X},${Y}" "$OUT.mp4"
ffmpeg -y -i "$OUT.mp4" -vf "fps=12,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" "$OUT.gif"
echo "wrote $OUT.gif - embed with: ![demo](docs/demo.gif)"
