#!/usr/bin/env python3
"""Publish owner-signed .q destinations behind an existing HTTPS reverse proxy."""

import asyncio
import json
import os
import ipaddress
import re
import tempfile
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web
from eth_account import Account
from eth_account.messages import encode_defunct

NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.q$")
OWNER = re.compile(r"^0x[0-9a-fA-F]{40}$")
NONCE = re.compile(r"^[0-9a-f]{32}$")
ROOT = Path(os.environ.get(
    "QNS_REGISTRY_DIR", "/srv/qns-bridge/.well-known/qns-bridge"
))


def destination(value):
    if not isinstance(value, dict):
        raise ValueError("Choisissez une IP de serveur ou un bucket QStorage")
    if value.get("kind") == "ip":
        try:
            address = ipaddress.ip_address(value.get("ip", ""))
        except ValueError as exc:
            raise ValueError("Saisissez une adresse IP valide") from exc
        if not address.is_global:
            raise ValueError("Une IP publique est requise")
        host = str(value.get("host", "")).strip().lower().rstrip(".")
        if host and (len(host) > 253 or "." not in host or host.endswith(".q")
                     or not re.fullmatch(r"[a-z0-9.-]+", host)):
            raise ValueError("Nom d’hôte virtuel invalide")
        return {"kind": "ip", "ip": address.compressed, "host": host}
    if value.get("kind") == "qstorage":
        bucket = str(value.get("bucket", "")).strip().lower()
        if bucket.endswith(".qstorage.quilibrium.com"):
            bucket = bucket[:-len(".qstorage.quilibrium.com")]
        if (not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])?", bucket)
                or len(bucket) < 3 or ".." in bucket or bucket.startswith("xn--")
                or re.fullmatch(r"[0-9.]+", bucket)):
            raise ValueError("Saisissez le nom du bucket QStorage")
        return {"kind": "qstorage", "bucket": bucket}
    raise ValueError("Destination non prise en charge")


def message(name, target, timestamp, nonce):
    encoded = json.dumps(target, sort_keys=True, separators=(",", ":"))
    return (f"QNS Web Bridge v3\nName: {name}\nDestination: {encoded}"
            f"\nTimestamp: {timestamp}\nNonce: {nonce}")


async def publish(request):
    try:
        data = await request.json()
        name = data.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("Nom .q invalide")
        target = destination(data.get("destination"))
        timestamp, nonce, signature = (data.get(k) for k in ("timestamp", "nonce", "signature"))
        if (type(timestamp) is not int or abs(time.time() - timestamp) > 300 or
                not isinstance(nonce, str) or not NONCE.fullmatch(nonce) or
                not isinstance(signature, str) or not re.fullmatch(r"0x[0-9a-fA-F]{130}", signature)):
            raise ValueError("Signature expirée ou invalide")
        async with request.app["session"].get(
            "https://names.quilibrium.com/resolve/" + name[:-2]
        ) as response:
            response.raise_for_status()
            qns = await response.json()
        header = qns.get("header") or {}
        owner = header.get("authorityKey", "")
        if header.get("name") != name[:-2] or not OWNER.fullmatch(owner):
            raise ValueError("Propriétaire QNS introuvable")
        signer = Account.recover_message(
            encode_defunct(text=message(name, target, timestamp, nonce)),
            signature=signature,
        )
        if signer.lower() != owner.lower():
            raise ValueError("Cette signature ne correspond pas au propriétaire QNS")
        record = {"version": 3, "name": name, "authorityKey": owner,
                  "destination": target, "timestamp": timestamp, "nonce": nonce,
                  "signature": signature}
        ROOT.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".qns-", dir=ROOT)
        try:
            with os.fdopen(fd, "w") as output:
                json.dump(record, output, indent=2)
                output.write("\n")
            os.chmod(temp, 0o644)
            os.replace(temp, ROOT / (name[:-2] + ".json"))
        finally:
            Path(temp).unlink(missing_ok=True)
        return web.json_response({"ok": True, "name": name, "destination": target})
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc


async def main():
    async with ClientSession(timeout=ClientTimeout(total=15)) as session:
        app = web.Application(client_max_size=4096)
        app["session"] = session
        app.router.add_post("/api/qns-bridge/publish", publish)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 17780).start()
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
