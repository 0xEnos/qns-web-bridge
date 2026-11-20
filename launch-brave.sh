#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if command -v brave >/dev/null 2>&1; then
  browser=brave
elif command -v brave-browser >/dev/null 2>&1; then
  browser=brave-browser
else
  printf 'Brave was not found. Install Brave or load extension/ in your existing Brave browser.\n' >&2
  exit 1
fi

profile_dir="${XDG_CONFIG_HOME:-$HOME/.config}/qns-web-bridge/brave-profile"
mkdir -p -- "$profile_dir"
if [[ ! -f "$script_dir/extension/manifest.json" ]]; then
  printf 'Extension files are missing from %s. Reinstall QNS Web Bridge.\n' "$script_dir" >&2
  exit 1
fi
if (($# == 0)); then
  set -- 'about:blank'
fi
exec "$browser" \
  --user-data-dir="$profile_dir" \
  --load-extension="$script_dir/extension" \
  --disable-extensions-except="$script_dir/extension" \
  --no-first-run \
  --new-window \
  "$@"
