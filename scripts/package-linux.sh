#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 - "$ROOT/extension/manifest.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    print(json.load(f)["version"])
PY
)"
OUT="${1:-$ROOT/dist/qns-web-bridge-linux-$VERSION.tar.gz}"
mkdir -p "$(dirname -- "$OUT")"
STAGE="$(mktemp -d -t qns-package-XXXXXX)"
cleanup() { python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)' "$STAGE"; }
trap cleanup EXIT
APP="$STAGE/qns-web-bridge"
mkdir -p "$APP"
for path in README.md install.sh launch-brave.sh qns-web-bridge.sh uninstall.sh \
            requirements.txt requirements-linux.lock extension local registry; do
  cp -a "$ROOT/$path" "$APP/"
done
python3 - "$APP" <<'PY'
import shutil, sys
from pathlib import Path
for path in Path(sys.argv[1]).rglob("__pycache__"):
    shutil.rmtree(path, ignore_errors=True)
PY
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"
tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner \
  -C "$STAGE" -cf - qns-web-bridge | gzip -n > "$OUT"
printf 'Built %s\n' "$OUT"
