#!/usr/bin/env python3
"""Generic .q SOCKS5, HTTPS and local mapping service for Brave."""

import asyncio
import ipaddress
import json
import logging
import os
import re
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, web
from eth_account import Account
from eth_account.messages import encode_defunct
from multidict import CIMultiDict

from certs import DATA_DIR, NAME_RE, create_leaf

SOCKS_PORT = 17777
HTTPS_PORT = 17778
API_PORT = 17779
REGISTRY_URL = os.environ.get(
    "QNS_BRIDGE_REGISTRY_URL",
    "https://0xenos1.qstorage.quilibrium.com/qns-web-bridge/registry.json",
)
REGISTRY_REFRESH_SECONDS = 3600
MAX_REGISTRY_BYTES = 2 * 1024 * 1024
MAPPINGS = DATA_DIR / "mappings.json"
LOCAL_RECORDS_DIR = DATA_DIR / "records"
PUBLISH_DIR = Path(__file__).resolve().parents[1] / "registry"
PUBLISH_FILES = {
    "/.qns-web-bridge/publish": "publish.html",
    "/.qns-web-bridge/publish.js": "publish.js",
    "/.qns-web-bridge/publish.css": "publish.css",
}
OWNER_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
EXT_ORIGIN_RE = re.compile(r"^chrome-extension://[a-p]{32}$")
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
       "te", "trailer", "transfer-encoding", "upgrade"}
LOG = logging.getLogger("qns-bridge")


def destination(value):
    """Normalize a server IP, QStorage bucket name, or legacy HTTPS origin."""
    if isinstance(value, str):  # v1/v2 records remain readable
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (parts.scheme != "https" or not host or parts.username or parts.password
                or parts.port or parts.path not in ("", "/") or parts.query or parts.fragment
                or host.endswith(".q") or "." not in host or host == "localhost"):
            raise ValueError("Use a public server IP or QStorage bucket name")
        return {"kind": "https", "host": host}
    if not isinstance(value, dict):
        raise ValueError("Destination invalide")
    kind = value.get("kind")
    if kind == "ip":
        try:
            address = ipaddress.ip_address(value.get("ip", ""))
        except ValueError as exc:
            raise ValueError("Saisissez une adresse IP valide") from exc
        if not address.is_global:
            raise ValueError("Une IP publique est requise")
        vhost = str(value.get("host", "")).strip().lower().rstrip(".")
        if vhost:
            if (len(vhost) > 253 or "." not in vhost or vhost.endswith(".q")
                    or not re.fullmatch(r"[a-z0-9.-]+", vhost)):
                raise ValueError("Nom d’hôte virtuel invalide")
        return {"kind": "ip", "ip": address.compressed, "host": vhost}
    if kind == "qstorage":
        bucket = str(value.get("bucket", "")).strip().lower()
        if bucket.endswith(".qstorage.quilibrium.com"):
            bucket = bucket[:-len(".qstorage.quilibrium.com")]
        if (not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])?", bucket)
                or len(bucket) < 3 or ".." in bucket or bucket.startswith("xn--")
                or re.fullmatch(r"[0-9.]+", bucket)):
            raise ValueError("Saisissez le nom du bucket QStorage")
        return {"kind": "qstorage", "bucket": bucket}
    raise ValueError("Choisissez une IP de serveur ou un bucket QStorage")


def signed_message(name, target, timestamp, nonce):
    encoded = json.dumps(target, sort_keys=True, separators=(",", ":"))
    return ("QNS Web Bridge v3\nName: " + name + "\nDestination: " + encoded
            + "\nTimestamp: " + str(timestamp) + "\nNonce: " + nonce)


def verify_record(name, record):
    """Validate a signed association without asking a name-resolution service."""
    if not isinstance(record, dict) or record.get("version") != 3 or record.get("name") != name:
        raise ValueError("Invalid signed registry record")
    if not NAME_RE.fullmatch(name):
        raise ValueError("Invalid .q name")
    owner = record.get("authorityKey", "")
    timestamp, nonce, signature = (record.get(k) for k in ("timestamp", "nonce", "signature"))
    if (not OWNER_RE.fullmatch(owner) or type(timestamp) is not int
            or not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce)
            or not isinstance(signature, str)
            or not re.fullmatch(r"0x[0-9a-fA-F]{130}", signature)):
        raise ValueError("Invalid signed registry record")
    target = destination(record.get("destination"))
    recovered = Account.recover_message(
        encode_defunct(text=signed_message(name, target, timestamp, nonce)), signature=signature)
    if recovered.lower() != owner.lower():
        raise ValueError("Owner signature does not match the record")
    return {"version": 3, "name": name, "authorityKey": owner,
            "destination": target, "timestamp": timestamp, "nonce": nonce,
            "signature": signature}


class Resolver:
    def __init__(self, session):
        self.session = session
        self.cache = {}
        self.lock = asyncio.Lock()
        self.registry_lock = asyncio.Lock()
        self.registry = {}
        self.registry_refresh_at = 0
        self.mappings = json.loads(MAPPINGS.read_text()) if MAPPINGS.exists() else {}
        LOCAL_RECORDS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        for path in LOCAL_RECORDS_DIR.glob("*.json"):
            try:
                record = json.loads(path.read_text())
                self.registry[record.get("name", "")] = verify_record(record.get("name", ""), record)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                LOG.warning("Ignoring invalid local signed record: %s", path.name)

    def save(self, name, target):
        self.mappings[name] = target
        DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = MAPPINGS.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.mappings, indent=2) + "\n")
        tmp.chmod(0o600)
        tmp.replace(MAPPINGS)
        self.cache.pop(name, None)

    def delete(self, name):
        self.mappings.pop(name, None)
        self.save_all()

    def save_all(self):
        tmp = MAPPINGS.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.mappings, indent=2) + "\n")
        tmp.chmod(0o600)
        tmp.replace(MAPPINGS)
        self.cache.clear()

    def save_signed_record(self, record):
        name = record["name"]
        verified = verify_record(name, record)
        tmp = LOCAL_RECORDS_DIR / (name[:-2] + ".tmp")
        path = LOCAL_RECORDS_DIR / (name[:-2] + ".json")
        tmp.write_text(json.dumps(verified, indent=2) + "\n")
        tmp.chmod(0o600)
        tmp.replace(path)
        self.registry[name] = verified
        self.cache.pop(name, None)

    async def refresh_registry(self, force=False):
        if not force and time.monotonic() < self.registry_refresh_at:
            return
        async with self.registry_lock:
            if not force and time.monotonic() < self.registry_refresh_at:
                return
            try:
                async with self.session.get(REGISTRY_URL) as response:
                    response.raise_for_status()
                    body = await response.content.read(MAX_REGISTRY_BYTES + 1)
                if len(body) > MAX_REGISTRY_BYTES:
                    raise ValueError("QStorage registry is too large")
                document = json.loads(body)
                if not isinstance(document, dict) or document.get("version") != 1:
                    raise ValueError("Unsupported QStorage registry format")
                entries = document.get("sites", [])
                if isinstance(entries, dict):
                    entries = [
                        dict(entry, name=entry.get("name", name))
                        for name, entry in entries.items()
                        if isinstance(entry, dict)
                    ]
                if not isinstance(entries, list) or len(entries) > 10000:
                    raise ValueError("Invalid QStorage registry entries")
                verified = {}
                for entry in entries:
                    name = entry.get("name", "") if isinstance(entry, dict) else ""
                    try:
                        verified[name] = verify_record(name, entry)
                    except (ValueError, TypeError):
                        LOG.warning("Ignoring invalid QStorage registry entry: %s", name)
                for name, entry in self.registry.items():
                    if (LOCAL_RECORDS_DIR / (name[:-2] + ".json")).exists():
                        verified[name] = entry
                self.registry = verified
                self.registry_refresh_at = time.monotonic() + REGISTRY_REFRESH_SECONDS
                LOG.info("Loaded %d signed .q associations from the QStorage manifest", len(verified))
            except Exception as exc:
                # Keep the last valid snapshot and retry soon; no per-name fallback.
                self.registry_refresh_at = time.monotonic() + 300
                LOG.warning("QStorage manifest unavailable: %s", exc)

    async def target(self, name):
        if not NAME_RE.fullmatch(name):
            raise ValueError("Invalid .q name")
        async with self.lock:
            cached = self.cache.get(name)
            if cached and cached[1] > time.monotonic():
                return cached[0]
            if name in self.mappings:
                target = destination(self.mappings[name])
            else:
                record = self.registry.get(name)
                if not record:
                    await self.refresh_registry()
                    record = self.registry.get(name)
                if not record:
                    raise ValueError("No signed association for this .q name in the QStorage manifest")
                target = destination(record["destination"])
            self.cache[name] = (target, time.monotonic() + 60)
            return target


def translated(value, source, destination):
    return value.replace(source, destination).replace(source.replace("https://", "http://"), destination)


async def publish_page(request, name):
    if request.path == "/.qns-web-bridge/api/publish":
        if request.method != "POST":
            raise web.HTTPMethodNotAllowed(request.method, ["POST"])
        body = await request.content.read(4097)
        if len(body) > 4096:
            raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=len(body))
        try:
            data = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise web.HTTPBadRequest(text="Publication invalide") from exc
        if not isinstance(data, dict) or data.get("name") != name:
            raise web.HTTPBadRequest(text="Le nom signé doit correspondre à l’adresse .q ouverte")
        try:
            target = destination(data.get("destination"))
            timestamp, nonce, signature = (data.get(k) for k in ("timestamp", "nonce", "signature"))
            if (type(timestamp) is not int or abs(time.time() - timestamp) > 300
                    or not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce)
                    or not isinstance(signature, str)
                    or not re.fullmatch(r"0x[0-9a-fA-F]{130}", signature)):
                raise ValueError("Signature expirée ou invalide")
            signer = Account.recover_message(
                encode_defunct(text=signed_message(
                    name, target, timestamp, nonce)), signature=signature,
            )
            record = verify_record(name, {
                "version": 3, "name": name, "authorityKey": signer,
                "destination": target, "timestamp": timestamp,
                "nonce": nonce, "signature": signature,
            })
            request.app["resolver"].save_signed_record(record)
        except (ValueError, TypeError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return web.json_response({"ok": True, "record": record, "registryUrl": REGISTRY_URL},
                                headers={"Cache-Control": "no-store"})
    filename = PUBLISH_FILES.get(request.path)
    if filename and request.method in ("GET", "HEAD"):
        return web.FileResponse(
            PUBLISH_DIR / filename,
            headers={"Cache-Control": "no-store"},
        )
    raise web.HTTPNotFound()


async def website(request):
    name = request.host.split(":")[0].lower()
    try:
        if not NAME_RE.fullmatch(name):
            raise ValueError("Invalid .q name")
        if request.path.startswith("/.qns-web-bridge/"):
            return await publish_page(request, name)
        target = await request.app["resolver"].target(name)
        if target["kind"] == "ip":
            ip = target["ip"]
            host = target["host"] or ip
            url_host = "[" + ip + "]" if ":" in ip else ip
            fetch_origin = "https://" + url_host
            upstream_origin = "https://" + host
            server_hostname = host
        elif target["kind"] == "qstorage":
            host = target["bucket"] + ".qstorage.quilibrium.com"
            fetch_origin = upstream_origin = "https://" + host
            server_hostname = host
        else:
            host = target["host"]
            fetch_origin = upstream_origin = "https://" + host
            server_hostname = host
        origin = upstream_origin
        public = "https://" + name
        if not request.raw_path.startswith("/"):
            raise ValueError("Invalid request path")
        headers = CIMultiDict()
        for key, value in request.headers.items():
            if key.lower() in HOP | {"host", "content-length", "accept-encoding"}:
                continue
            if key.lower() in {"origin", "referer"}:
                value = translated(value, public, origin)
            headers.add(key, value)
        headers["Host"] = ("[" + host + "]") if ":" in host else host
        data = request.content.iter_chunked(65536) if request.can_read_body else None
        async with request.app["session"].request(
            request.method, fetch_origin + request.raw_path, headers=headers, data=data,
            allow_redirects=False, auto_decompress=False, server_hostname=server_hostname,
        ) as upstream:
            response_headers = CIMultiDict()
            for key, value in upstream.headers.items():
                if key.lower() in HOP:
                    continue
                if key.lower() in {"location", "content-location", "access-control-allow-origin", "link"}:
                    value = translated(value, origin, public)
                    if fetch_origin != origin:
                        value = translated(value, fetch_origin, public)
                if key.lower() == "set-cookie":
                    value = value.replace("Domain=" + urlsplit(origin).hostname, "Domain=" + name)
                response_headers.add(key, value)
            result = web.StreamResponse(status=upstream.status, headers=response_headers)
            await result.prepare(request)
            async for chunk in upstream.content.iter_chunked(65536):
                await result.write(chunk)
            await result.write_eof()
            return result
    except Exception as exc:
        LOG.exception("Bridge request failed: %s %s", name, request.raw_path)
        return web.Response(status=502, text="QNS bridge error: " + str(exc))


def api_headers(request):
    origin = request.headers.get("Origin", "")
    if origin and not EXT_ORIGIN_RE.fullmatch(origin):
        raise web.HTTPForbidden(text="Extension origin required")
    headers = {"Vary": "Origin",
            "Access-Control-Allow-Headers": "Content-Type, X-QNS-Bridge",
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS"}
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    return headers


async def api(request):
    headers = api_headers(request)
    if request.method == "OPTIONS":
        return web.Response(headers=headers)
    if request.headers.get("X-QNS-Bridge") != "1":
        raise web.HTTPForbidden(text="Extension request required")
    resolver = request.app["resolver"]
    if request.method == "GET":
        return web.json_response({"ok": True, "mappings": resolver.mappings}, headers=headers)
    if request.method == "POST":
        data = await request.json()
        name = str(data.get("name", "")).strip().lower()
        if not NAME_RE.fullmatch(name):
            raise web.HTTPBadRequest(text="Enter a one-label .q name")
        try:
            target = destination(data.get("destination"))
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        # A local choice is always scoped to this user's browser.
        resolver.save(name, target)
        return web.json_response({"name": name, "destination": target}, headers=headers)
    if request.method == "DELETE":
        name = request.match_info["name"]
        resolver.delete(name)
        return web.json_response({"deleted": name}, headers=headers)
    raise web.HTTPMethodNotAllowed(request.method, ["GET", "POST", "DELETE", "OPTIONS"])


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def socks(reader, writer, resolver, contexts):
    try:
        header = await reader.readexactly(2)
        if header[0] != 5 or header[1] > 16:
            return
        methods = await reader.readexactly(header[1])
        if 0 not in methods:
            writer.write(b"\x05\xff")
            await writer.drain()
            return
        writer.write(b"\x05\x00")
        await writer.drain()
        request = await reader.readexactly(4)
        if request[:3] != b"\x05\x01\x00" or request[3] != 3:
            return
        length = (await reader.readexactly(1))[0]
        name = (await reader.readexactly(length)).decode("ascii").lower()
        port = int.from_bytes(await reader.readexactly(2), "big")
        if port != 443 or not NAME_RE.fullmatch(name):
            raise ValueError("Only HTTPS .q names are supported")
        if name not in contexts:
            cert, key = await asyncio.to_thread(create_leaf, name)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            contexts[name] = context
        remote_reader, remote_writer = await asyncio.open_connection("127.0.0.1", HTTPS_PORT)
        writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()
        await asyncio.gather(pipe(reader, remote_writer), pipe(remote_reader, writer))
    except Exception as exc:
        LOG.info("SOCKS refused request: %s", exc)
        try:
            writer.write(b"\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
        except (ConnectionError, OSError):
            pass
    finally:
        writer.close()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    async with ClientSession(timeout=ClientTimeout(total=60)) as session:
        resolver = Resolver(session)
        contexts = {}
        # Preserve the already trusted certificate on an upgraded workstation.
        old_cert = DATA_DIR / "stonks.q.crt"
        old_key = DATA_DIR / "stonks.q.key"
        cert, key = (old_cert, old_key) if old_cert.exists() and old_key.exists() else create_leaf("stonks.q")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        contexts["stonks.q"] = context

        def select_context(ssl_socket, server_name, default_context):
            if not isinstance(server_name, str) or not NAME_RE.fullmatch(server_name):
                raise ssl.SSLError("Unknown .q name")
            if server_name not in contexts:
                cert, key = create_leaf(server_name)
                leaf = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                leaf.load_cert_chain(cert, key)
                contexts[server_name] = leaf
            ssl_socket.context = contexts[server_name]

        context.set_servername_callback(select_context)
        app = web.Application(client_max_size=32 * 1024 * 1024)
        app["resolver"], app["session"] = resolver, session
        app.router.add_route("*", "/{tail:.*}", website)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", HTTPS_PORT, ssl_context=context).start()
        admin = web.Application(client_max_size=16384)
        admin["resolver"] = resolver
        admin.router.add_route("*", "/api/mappings", api)
        admin.router.add_route("*", "/api/mappings/{name}", api)
        admin_runner = web.AppRunner(admin)
        await admin_runner.setup()
        await web.TCPSite(admin_runner, "127.0.0.1", API_PORT).start()
        server = await asyncio.start_server(
            lambda r, w: socks(r, w, resolver, contexts), "127.0.0.1", SOCKS_PORT,
        )
        LOG.info("SOCKS5 %d, HTTPS %d and local API %d ready", SOCKS_PORT, HTTPS_PORT, API_PORT)
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
