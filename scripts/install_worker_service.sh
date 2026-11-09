#!/usr/bin/env bash
# Run ON the host: installs and (re)starts the es.pieza3d.worker LaunchAgent.
set -euo pipefail

LABEL="es.pieza3d.worker"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/$LABEL.plist"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE_HOME="/Users/jorgeclawd"
DOMAIN="gui/$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
if [ "$HOME" != "$TEMPLATE_HOME" ]; then
  sed "s#$TEMPLATE_HOME#$HOME#g" "$SRC" > "$DEST"
else
  cp "$SRC" "$DEST"
fi
plutil -lint "$DEST"

if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL" || true
fi
launchctl bootstrap "$DOMAIN" "$DEST"
launchctl kickstart -k "$DOMAIN/$LABEL"
echo "Servicio $LABEL instalado y arrancado. Logs: tail -f ~/Library/Logs/pieza3d-worker.log"
