#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for program in python3 openssl certutil; do
  if ! command -v "$program" >/dev/null 2>&1; then
  echo "Missing command: $program" >&2
    exit 1
  fi
done
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" "$ROOT/local/certs.py"
mkdir -p "$HOME/.config/systemd/user"
sed "s|%h/hal/qns-bridge|$ROOT|g" "$ROOT/local/qns-bridge.service" > "$HOME/.config/systemd/user/qns-bridge.service"
systemctl --user daemon-reload
systemctl --user enable --now qns-bridge.service
systemctl --user restart qns-bridge.service
echo "Local bridge is running. Load $ROOT/extension in brave://extensions."
