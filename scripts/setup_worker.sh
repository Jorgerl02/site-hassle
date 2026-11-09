#!/usr/bin/env bash
# Worker host setup for the delivery step: installs the pinned glTF Transform CLI
# (tools/gltf/package-lock.json) used by harness.post.deliver, and fetches the CC0 PBR
# material library into data/materials/. Needs Node.js ≥ 18 (npm) and uv.
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci --prefix tools/gltf --no-audit --no-fund
tools/gltf/node_modules/.bin/gltf-transform --version
uv run python scripts/fetch_materials.py
