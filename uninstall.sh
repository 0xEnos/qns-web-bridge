#!/usr/bin/env bash
set -euo pipefail

PURGE_DATA=0
PURGE_PROFILE=0
for arg in "$@"; do
  case "$arg" in
    --purge-data) PURGE_DATA=1 ;;
    --purge-profile) PURGE_PROFILE=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./uninstall.sh [--purge-data] [--purge-profile]

Removes the per-user bridge service and its locally trusted CA. The CA key,
certificates, and mappings are retained unless --purge-data is confirmed.
The dedicated Brave profile is retained unless --purge-profile is confirmed.
EOF
      exit 0
      ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

confirm_purge() {
  local label="$1" answer
  read -r -p "$label This permanently deletes local data. Continue? [y/N] " answer
  case "$answer" in y|Y|yes|YES) return 0 ;; *) echo 'Cancelled.'; exit 1 ;; esac
}

if ((PURGE_DATA)); then
  confirm_purge 'Delete the bridge CA private key, issued certificates and local mappings?'
fi
if ((PURGE_PROFILE)); then
  confirm_purge 'Delete the dedicated Brave profile, cookies and browser data?'
fi

systemctl --user disable --now qns-bridge.service 2>/dev/null || true
unit="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/qns-bridge.service"
if [[ -f "$unit" ]]; then
  rm -- "$unit"
fi
systemctl --user daemon-reload

db="$HOME/.pki/nssdb"
if command -v certutil >/dev/null 2>&1 && [[ -f "$db/cert9.db" ]]; then
  certutil -D -d "sql:$db" -n 'QNS Web Bridge local CA' >/dev/null 2>&1 || true
fi

if ((PURGE_DATA)); then
  data="$HOME/.local/share/qns-bridge"
  [[ ! -d "$data" ]] || rm -r -- "$data"
fi
if ((PURGE_PROFILE)); then
  profile="${XDG_CONFIG_HOME:-$HOME/.config}/qns-web-bridge/brave-profile"
  [[ ! -d "$profile" ]] || rm -r -- "$profile"
fi

echo 'QNS Web Bridge was removed. The installation directory can now be deleted.'
