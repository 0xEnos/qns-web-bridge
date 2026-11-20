#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! systemctl --user is-active --quiet qns-bridge.service; then
  systemctl --user start qns-bridge.service
fi
exec "$ROOT/launch-brave.sh" "$@"
