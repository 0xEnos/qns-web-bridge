#!/usr/bin/env python3
"""Fresh-HOME bridge and Brave acceptance run; never uses the host user profile."""

import asyncio
import http.server
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
BRAVE = shutil.which("brave") or shutil.which("brave-browser")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class OutageManifestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503)
        self.end_headers()
        self.wfile.write(b"temporary QStorage manifest outage")

    def log_message(self, *_args):
        pass


def setup_fresh_install(app, home, xdg, fakebin, env):
    shutil.copytree(ROOT, app, ignore=shutil.ignore_patterns(
        ".git", ".venv", "__pycache__", "*.pyc", "dist", "tests"))
    fakebin.mkdir()
    (fakebin / "systemctl").write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$XDG_CONFIG_HOME/systemctl.log\"\n"
        "if [[ \"$*\" == *' is-active '* ]]; then exit 1; fi\n"
        "exit 0\n")
    (fakebin / "brave").write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" > \"$XDG_CONFIG_HOME/brave-install.log\"\n"
        "exit 0\n")
    for script in (fakebin / "systemctl", fakebin / "brave"):
        script.chmod(0o755)
    install_env = dict(env, HOME=str(home), XDG_CONFIG_HOME=str(xdg),
                       PATH=str(fakebin) + os.pathsep + env["PATH"],
                       PIP_DISABLE_PIP_VERSION_CHECK="1")
    result = subprocess.run([str(app / "install.sh")], cwd=app, env=install_env,
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError("fresh install failed:\n" + result.stdout + result.stderr)
    unit = xdg / "systemd/user/qns-bridge.service"
    assert unit.is_file()
    assert not (home / ".local/share/qns-bridge/mappings.json").exists()
    assert (home / ".pki/nssdb/cert9.db").is_file()
    assert (xdg / "brave-install.log").read_text().find("https://obscura.q/") >= 0
    return install_env


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.next_id = 1
        self.events = []

    async def call(self, method, params=None, timeout=15):
        call_id = self.next_id
        self.next_id += 1
        await self.ws.send_json({"id": call_id, "method": method,
                                 "params": params or {}})
        async with asyncio.timeout(timeout):
            while True:
                message = await self.ws.receive_json()
                if "method" in message:
                    self.events.append(message)
                if message.get("id") == call_id:
                    if "error" in message:
                        raise RuntimeError(f"CDP {method}: {message['error']}")
                    return message.get("result", {})

    async def value(self, expression):
        result = await self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError("Page script evaluation failed: " +
                               result["exceptionDetails"].get("text", "unknown error"))
        return result.get("result", {}).get("value")


async def browser_check(app, home, xdg, fakebin, env, socks_port):
    # This test-only wrapper runs a real, separate Brave process with DevTools so
    # the test can inspect the isolated page and close only that process group.
    wrapper = fakebin / "brave"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {BRAVE} --headless=new --disable-gpu --remote-debugging-port=0 "
        "--remote-allow-origins='*' \"$@\"\n")
    wrapper.chmod(0o755)
    browser_env = dict(env, HOME=str(home), XDG_CONFIG_HOME=str(xdg),
                       PATH=str(fakebin) + os.pathsep + env["PATH"])
    proc = subprocess.Popen([str(app / "launch-brave.sh"), "https://obscura.q/"],
                            cwd=app, env=browser_env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    profile = xdg / "qns-web-bridge/brave-profile"
    port_file = profile / "DevToolsActivePort"
    try:
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline and not port_file.exists():
            if proc.poll() is not None:
                raise RuntimeError(f"Brave exited early with status {proc.returncode}")
            await asyncio.sleep(0.25)
        if not port_file.exists():
            raise RuntimeError("Brave did not create its isolated DevTools endpoint")
        debug_port = int(port_file.read_text().splitlines()[0])
        base = f"http://127.0.0.1:{debug_port}"
        async with aiohttp.ClientSession() as session:
            deadline = time.monotonic() + 15
            version = None
            while time.monotonic() < deadline:
                try:
                    async with session.get(base + "/json/version") as response:
                        version = await response.json()
                    break
                except Exception:
                    await asyncio.sleep(0.25)
            if not version:
                raise RuntimeError("Brave DevTools endpoint did not become ready")
            async with session.get(base + "/json/list") as response:
                targets = await response.json()
            page = next((target for target in targets if target.get("type") == "page"), None)
            if not page:
                raise RuntimeError("Brave did not create a page target")
            async with session.ws_connect(page["webSocketDebuggerUrl"], timeout=15) as ws:
                cdp = CDP(ws)
                await cdp.call("Page.enable")
                await cdp.call("Runtime.enable")
                await cdp.call("Network.enable")
                # Let the unpacked extension's startup listener commit its PAC
                # proxy settings before the first .q navigation.
                await asyncio.sleep(2)
                await cdp.call("Page.navigate", {"url": "https://obscura.q/"})
                state = None
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    await asyncio.sleep(0.5)
                    try:
                        state = await cdp.value("({url:location.href,title:document.title,ready:document.readyState,secure:isSecureContext,styles:document.styleSheets.length,scriptText:[...document.scripts].map(s=>s.textContent.length).reduce((a,b)=>a+b,0),anchors:[...document.querySelectorAll('a[href]')].map(a=>a.href),body:document.body?.innerText?.slice(0,500)})")
                    except Exception:
                        continue
                    if state and state.get("title"):
                        break
                if not state or state.get("title") != "Obscura Exchange · Paper mode":
                    raise RuntimeError(f"Brave did not render the expected page: {state}")
                if not state.get("secure") or state.get("styles", 0) < 1 or state.get("scriptText", 0) < 500:
                    raise RuntimeError(f"TLS secure context or inline assets failed: {state}")
                responses = [event["params"].get("response", {})
                             for event in cdp.events if event.get("method") == "Network.responseReceived"]
                doc = next((r for r in responses if r.get("url", "").startswith("https://obscura.q/")), None)
                if not doc or doc.get("status") != 200:
                    raise RuntimeError(f"Brave document did not return HTTP 200: {doc}")
                same_origin_failures = []
                requests = {event["params"].get("requestId"): event["params"].get("request", {}).get("url", "")
                            for event in cdp.events if event.get("method") == "Network.requestWillBeSent"}
                for event in cdp.events:
                    if event.get("method") == "Network.loadingFailed":
                        failed_url = requests.get(event["params"].get("requestId"), "")
                        if failed_url.startswith("https://obscura.q/"):
                            same_origin_failures.append(failed_url)
                if same_origin_failures:
                    raise RuntimeError("Same-origin page resources failed: " + repr(same_origin_failures))
                cert = await cdp.call("Network.getCertificate", {"origin": "https://obscura.q"})
                chain = cert.get("tableNames", [])
                if not chain:
                    raise RuntimeError("Brave did not report the HTTPS certificate chain")

                # The current Obscura page contains no same-origin links. Verify
                # same-origin fragment navigation and history without clicking
                # its external GitHub link or submitting any paper-trade action.
                await cdp.call("Page.navigate", {"url": "https://obscura.q/#history"})
                await asyncio.sleep(0.5)
                fragment = await cdp.value("location.origin + location.hash")
                if fragment != "https://obscura.q#history":
                    raise RuntimeError(f"Same-origin navigation failed: {fragment}")
                if any(url.startswith("https://obscura.q/") for url in state["anchors"]):
                    raise RuntimeError("Unexpected same-origin anchor appeared; review navigation test")

                # Browser gets the current session's origin again through the
                # extension SOCKS PAC route; a failed proxy or TLS trust breaks
                # the document request above.
                print(json.dumps({
                    "brave": "real headless browser process with unpacked extension",
                    "page": state["title"], "secureContext": state["secure"],
                    "styleSheets": state["styles"], "inlineScriptChars": state["scriptText"],
                    "sameOriginFragment": fragment,
                    "currentPageHasSameOriginLinks": any(
                        url.startswith("https://obscura.q/") for url in state["anchors"]),
                    "certificateChainEntries": len(chain),
                    "socksPortUsedByExtension": socks_port,
                }, indent=2))

            browser_ws = version.get("webSocketDebuggerUrl")
            if browser_ws:
                async with session.ws_connect(browser_ws, timeout=5) as ws:
                    await ws.send_json({"id": 1, "method": "Browser.close"})
    finally:
        deadline = time.monotonic() + 5
        while proc.poll() is None and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=3)


def wait_port(port, process, logs):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("bridge exited:\n" + logs.read_text(errors="replace"))
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("bridge did not open its isolated test ports")


def request_page(home, socks_port):
    ca = home / ".local/share/qns-bridge/ca.crt"
    result = subprocess.run([
        "curl", "--fail", "--silent", "--show-error", "--proxy",
        f"socks5h://127.0.0.1:{socks_port}", "--noproxy", "", "--cacert", str(ca),
        "--dump-header", "/dev/stderr", "https://obscura.q/",
    ], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("TLS/SOCKS request failed: " + result.stderr)
    if "200" not in result.stderr.splitlines()[0]:
        raise RuntimeError("Unexpected HTTP response: " + result.stderr[:300])
    html = result.stdout
    if "Obscura Exchange · Paper mode" not in html or "<style>" not in html or "<script>" not in html:
        raise RuntimeError("Expected Obscura HTML, CSS and JavaScript were not present")
    return html


async def main():
    if not BRAVE:
        raise RuntimeError("Brave is required for the real-browser acceptance run")
    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="qns-bridge-acceptance-") as tmp:
        base = Path(tmp)
        home, xdg = base / "home", base / "config"
        app, fakebin = base / "app", base / "fake-bin"
        home.mkdir(); xdg.mkdir()
        install_env = setup_fresh_install(app, home, xdg, fakebin, env)
        socks_port, https_port, api_port = free_port(), free_port(), free_port()
        while len({socks_port, https_port, api_port}) < 3:
            socks_port, https_port, api_port = free_port(), free_port(), free_port()

        background = app / "extension/background.js"
        code = background.read_text()
        code = code.replace("127.0.0.1:17777", f"127.0.0.1:{socks_port}")
        code = code.replace("127.0.0.1:17779", f"127.0.0.1:{api_port}")
        background.write_text(code)
        manifest = app / "extension/manifest.json"
        manifest.write_text(manifest.read_text().replace(
            "http://127.0.0.1:17779/*", f"http://127.0.0.1:{api_port}/*"))

        outage = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OutageManifestHandler)
        threading.Thread(target=outage.serve_forever, daemon=True).start()
        bridge_env = dict(install_env,
                          QNS_BRIDGE_SOCKS_PORT=str(socks_port),
                          QNS_BRIDGE_HTTPS_PORT=str(https_port),
                          QNS_BRIDGE_API_PORT=str(api_port),
                          QNS_BRIDGE_REGISTRY_URLS=(
                              f"http://127.0.0.1:{outage.server_port}/manifest.json,"
                              "bundled://registry/manifest.json"))
        logs = base / "bridge.log"
        with logs.open("w") as output:
            bridge = subprocess.Popen([str(app / ".venv/bin/python"),
                                       str(app / "local/bridge_v2.py")],
                                      cwd=app, env=bridge_env, stdout=output,
                                      stderr=subprocess.STDOUT, start_new_session=True)
        try:
            wait_port(socks_port, bridge, logs)
            html = request_page(home, socks_port)
            if not (home / ".local/share/qns-bridge/mappings.json").exists():
                print("Fresh install has no manually entered mapping.")
            else:
                raise RuntimeError("Fresh install unexpectedly has local mappings")

            # Simulate a bridge service restart and confirm state remains valid.
            bridge.terminate(); bridge.wait(timeout=5)
            with logs.open("a") as output:
                bridge = subprocess.Popen([str(app / ".venv/bin/python"),
                                           str(app / "local/bridge_v2.py")],
                                          cwd=app, env=bridge_env, stdout=output,
                                          stderr=subprocess.STDOUT, start_new_session=True)
            wait_port(socks_port, bridge, logs)
            request_page(home, socks_port)
            print("Restarted bridge serves obscura.q over verified HTTPS.")
            await browser_check(app, home, xdg, fakebin, env, socks_port)
            print("Bundled fallback was used while the simulated QStorage manifest returned HTTP 503.")
            print("The current Obscura page uses inline CSS/JavaScript and has no same-origin links.")
            print(f"HTML bytes: {len(html.encode())}; no mapping was entered manually.")
        finally:
            if bridge.poll() is None:
                bridge.terminate()
                try: bridge.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(bridge.pid, signal.SIGKILL)
            outage.shutdown(); outage.server_close()


if __name__ == "__main__":
    asyncio.run(main())
