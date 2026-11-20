#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if command -v brave >/dev/null 2>&1; then
  browser=brave
elif command -v brave-browser >/dev/null 2>&1; then
  browser=brave-browser
else
  printf 'Brave est introuvable. Installe Brave ou charge extension/ dans ton Brave actuel.\n' >&2
  exit 1
fi

profile_dir="${XDG_CONFIG_HOME:-$HOME/.config}/qns-web-bridge/brave-profile"
mkdir -p -- "$profile_dir"
if (($# == 0)); then
  set -- 'about:blank'
fi
exec "$browser" \
  --user-data-dir="$profile_dir" \
  --load-extension="$script_dir/extension" \
  --disable-extensions-except="$script_dir/extension" \
  --no-first-run \
  "$@"
