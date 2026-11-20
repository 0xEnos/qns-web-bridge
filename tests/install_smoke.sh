#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP="$(mktemp -d -t qns-install-smoke-XXXXXX)"
cleanup() {
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)' "$TEMP"
}
trap cleanup EXIT

HOME="$TEMP/home"
XDG_CONFIG_HOME="$TEMP/config"
XDG_CACHE_HOME="$TEMP/cache"
FAKE_BIN="$TEMP/fake-bin"
APP="$TEMP/installed app"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$FAKE_BIN" "$APP"
export HOME XDG_CONFIG_HOME XDG_CACHE_HOME
cp -a "$SOURCE/." "$APP/"
python3 - "$APP" <<'PY'
import shutil, sys
from pathlib import Path
root = Path(sys.argv[1])
for name in (".git", ".venv", "__pycache__"):
    path = root / name
    if path.is_dir():
        shutil.rmtree(path)
PY

cat > "$FAKE_BIN/systemctl" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$XDG_CONFIG_HOME/systemctl.log"
if [[ "$*" == *' is-active '* ]]; then exit 1; fi
exit 0
SH
cat > "$FAKE_BIN/brave" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$XDG_CONFIG_HOME/brave.log"
exit 0
SH
chmod +x "$FAKE_BIN/systemctl" "$FAKE_BIN/brave"
export PATH="$FAKE_BIN:$PATH"
export PIP_DISABLE_PIP_VERSION_CHECK=1

"$APP/install.sh"

test -x "$APP/.venv/bin/python"
test -f "$XDG_CONFIG_HOME/systemd/user/qns-bridge.service"
test -f "$HOME/.local/share/qns-bridge/ca.key"
test -f "$HOME/.pki/nssdb/cert9.db"
test ! -e "$HOME/.local/share/pki/nssdb/cert9.db"
grep -F "$APP/.venv/bin/python" "$XDG_CONFIG_HOME/systemd/user/qns-bridge.service" >/dev/null
grep -F -- "--user-data-dir=$XDG_CONFIG_HOME/qns-web-bridge/brave-profile" "$XDG_CONFIG_HOME/brave.log" >/dev/null
grep -F -- "--load-extension=$APP/extension" "$XDG_CONFIG_HOME/brave.log" >/dev/null
grep -F 'https://obscura.q/' "$XDG_CONFIG_HOME/brave.log" >/dev/null
test "$(grep -c 'restart qns-bridge.service' "$XDG_CONFIG_HOME/systemctl.log" || true)" -eq 0
"$APP/uninstall.sh"
test ! -e "$XDG_CONFIG_HOME/systemd/user/qns-bridge.service"
test -f "$HOME/.local/share/qns-bridge/ca.key"
certutil -L -d "sql:$HOME/.pki/nssdb" | grep -F 'QNS Web Bridge local CA' >/dev/null && exit 1 || true
printf 'y\ny\n' | "$APP/uninstall.sh" --purge-data --purge-profile
test ! -e "$HOME/.local/share/qns-bridge"
test ! -e "$XDG_CONFIG_HOME/qns-web-bridge/brave-profile"
echo 'Install smoke test passed in a temporary HOME; systemd and Brave were isolated shims.'
