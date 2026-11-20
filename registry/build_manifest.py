#!/usr/bin/env python3
"""Combine owner-signed QNS Web Bridge entries into one privacy-friendly snapshot."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct

NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$")
OWNER = re.compile(r"^0x[0-9a-fA-F]{40}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")
SIGNATURE = re.compile(r"^0x[0-9a-fA-F]{130}$")


def validate_record(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    name = record.get("name", "")
    if record.get("version") != 3 or not NAME.fullmatch(name):
        raise ValueError(f"{path}: unsupported or invalid record")
    owner = record.get("authorityKey", "")
    timestamp, nonce, signature = (record.get(k) for k in ("timestamp", "nonce", "signature"))
    if (not OWNER.fullmatch(owner) or type(timestamp) is not int
            or not isinstance(nonce, str) or not NONCE.fullmatch(nonce)
            or not isinstance(signature, str) or not SIGNATURE.fullmatch(signature)):
        raise ValueError(f"{path}: incomplete signed record")
    target = record.get("destination")
    if not isinstance(target, dict) or target.get("kind") not in {"ip", "qstorage"}:
        raise ValueError(f"{path}: invalid destination")
    encoded = json.dumps(target, sort_keys=True, separators=(",", ":"))
    message = (f"QNS Web Bridge v3\nName: {name}\nDestination: {encoded}"
               f"\nTimestamp: {timestamp}\nNonce: {nonce}")
    recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    if recovered.lower() != owner.lower():
        raise ValueError(f"{path}: signature does not match authorityKey")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entries", nargs="+", type=Path,
                        help="signed JSON files or directories containing signed JSON files")
    parser.add_argument("-o", "--output", type=Path, default=Path("registry/manifest.json"))
    args = parser.parse_args()

    paths = []
    for entry in args.entries:
        paths.extend(sorted(entry.glob("*.json")) if entry.is_dir() else [entry])
    records = {}
    for path in paths:
        record = validate_record(path)
        name = record["name"]
        if name in records and records[name] != record:
            raise ValueError(f"Conflicting signed entries for {name}")
        records[name] = record

    manifest = {
        "version": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "sites": [records[name] for name in sorted(records)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} signed entries to {args.output}")


if __name__ == "__main__":
    main()
