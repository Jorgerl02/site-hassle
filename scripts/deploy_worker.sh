#!/usr/bin/env bash
# Deploy the platform worker to the always-on host (default: SSH alias "mac-mini").
# Usage: scripts/deploy_worker.sh [host]
set -euo pipefail

HOST="${1:-mac-mini}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="apps/pieza3d"

echo "==> rsync $ROOT/ -> $HOST:~/$DEST/"
ssh "$HOST" "mkdir -p ~/$DEST"
rsync -az --delete --itemize-changes \
  --exclude '.git/' --exclude '.venv/' --exclude 'node_modules/' \
  --exclude 'runs/' --exclude 'outputs/' \
  --exclude 'data/images/' --exclude 'data/materials/' \
  --exclude 'platform/' --exclude 'reports/' --exclude 'research_notes/' \
  --exclude '.superpowers/' --exclude '.env' \
  --exclude '*.pyc' --exclude '__pycache__/' \
  --exclude '.pytest_cache/' --exclude '.ruff_cache/' \
  "$ROOT/" "$HOST:$DEST/"

echo "==> uv sync (sin dependencias de desarrollo)"
ssh "$HOST" 'cd ~/apps/pieza3d && ~/.local/bin/uv sync --frozen --no-dev'

echo "==> npm ci (tools/gltf)"
ssh "$HOST" 'cd ~/apps/pieza3d && PATH=~/.local/node/bin:$PATH npm ci --prefix tools/gltf --no-audit --no-fund --omit=dev'

echo "==> materiales"
ssh "$HOST" 'cd ~/apps/pieza3d && ~/.local/bin/uv run --no-dev python scripts/fetch_materials.py'

echo "==> reinicio del agente launchd es.pieza3d.worker"
ssh "$HOST" 'if launchctl print "gui/$(id -u)/es.pieza3d.worker" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/es.pieza3d.worker" && echo "reiniciado"
else
  echo "agente no cargado: ejecuta scripts/install_worker_service.sh en el host"
fi'

echo "==> Listo: código sincronizado en $HOST:~/$DEST"
