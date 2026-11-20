#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DEPS=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--install-deps]

Install the per-user QNS bridge and open obscura.q in its dedicated Brave profile.
System packages are never installed unless --install-deps is supplied and
confirmed interactively.
EOF
}

case "${1:-}" in
  "") ;;
  --install-deps) INSTALL_DEPS=1 ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

missing=()
for program in python3 openssl certutil systemctl; do
  command -v "$program" >/dev/null 2>&1 || missing+=("$program")
done
if command -v python3 >/dev/null 2>&1 && ! python3 -m venv --help >/dev/null 2>&1; then
  missing+=("python3-venv")
fi

if ((${#missing[@]})); then
  packages=()
  if command -v apt-get >/dev/null 2>&1; then
    packages=(python3 python3-venv openssl libnss3-tools systemd)
  elif command -v dnf >/dev/null 2>&1; then
    packages=(python3 python3-pip openssl nss-tools systemd)
  elif command -v pacman >/dev/null 2>&1; then
    packages=(python python-pip openssl nss systemd)
  else
    printf 'Missing required commands: %s\n' "${missing[*]}" >&2
    printf 'Install Python 3, OpenSSL, NSS certutil, and systemd, then rerun.\n' >&2
    exit 1
  fi
  if ((INSTALL_DEPS == 0)); then
    printf 'Missing required commands: %s\n' "${missing[*]}" >&2
    printf 'To install the listed system dependencies, rerun with --install-deps.\n' >&2
    exit 1
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    printf 'sudo is required for the optional system package installation.\n' >&2
    exit 1
  fi
  printf 'This will change system packages using: %s\n' "${packages[*]}"
  read -r -p 'Continue with system package installation? [y/N] ' answer
  case "$answer" in y|Y|yes|YES) ;; *) echo 'Cancelled.'; exit 1 ;; esac
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y "${packages[@]}"
  else
    sudo pacman -S --needed "${packages[@]}"
  fi
  for program in python3 openssl certutil systemctl; do
    command -v "$program" >/dev/null 2>&1 || {
      printf 'Required command still unavailable after installation: %s\n' "$program" >&2
      exit 1
    }
  done
fi

if ! command -v brave >/dev/null 2>&1 && ! command -v brave-browser >/dev/null 2>&1; then
  printf 'Brave is not installed. Install Brave from brave.com, then rerun this installer.\n' >&2
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf 'Python 3.10 or newer is required.\n' >&2
  exit 1
fi

if ! systemctl --user show-environment >/dev/null 2>&1; then
  printf 'systemd user services are unavailable in this session. Log into your desktop session and rerun.\n' >&2
  exit 1
fi

python3 -m venv "$ROOT/.venv"
lockfile="$ROOT/requirements-linux.lock"
if [[ -f "$lockfile" ]]; then
  "$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check --quiet -r "$lockfile"
else
  "$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check --quiet -r "$ROOT/requirements.txt"
fi
"$ROOT/.venv/bin/python" "$ROOT/local/certs.py"

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
python3 - "$ROOT" "$unit_dir/qns-bridge.service" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
unit = Path(sys.argv[2])
python = json.dumps(str(root / ".venv/bin/python"))
program = json.dumps(str(root / "local/bridge_v2.py"))
unit.write_text(
    "[Unit]\n"
    "Description=QNS HTTPS bridge for .q websites\n"
    "After=network-online.target\n"
    "Wants=network-online.target\n\n"
    "[Service]\n"
    "Type=simple\n"
    f"ExecStart={python} {program}\n"
    "Restart=on-failure\n"
    "RestartSec=3\n\n"
    "[Install]\n"
    "WantedBy=default.target\n",
    encoding="utf-8",
)
unit.chmod(0o600)
PY

systemctl --user daemon-reload
if systemctl --user is-active --quiet qns-bridge.service; then
  systemctl --user restart qns-bridge.service
else
  systemctl --user enable --now qns-bridge.service
fi
"$ROOT/launch-brave.sh" "https://obscura.q/"
