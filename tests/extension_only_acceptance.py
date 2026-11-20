#!/usr/bin/env python3
"""Open obscura.q in a clean Brave profile with only the unpacked extension."""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"
BRAVE = shutil.which("brave") or shutil.which("brave-browser")
EXPECTED = "https://0xenos.qstorage.quilibrium.com/"


async def run():
    if not BRAVE:
        raise RuntimeError("Brave is not installed")
    with tempfile.TemporaryDirectory(prefix="qns-ext-only-") as tmp:
        profile = Path(tmp) / "profile"
        process = subprocess.Popen(
            [BRAVE, f"--user-data-dir={profile}", "--headless=new", "--no-sandbox",
             "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--remote-debugging-port=0", f"--disable-extensions-except={EXTENSION}",
             f"--load-extension={EXTENSION}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        try:
            port_file = profile / "DevToolsActivePort"
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not port_file.exists():
                if process.poll() is not None:
                    raise RuntimeError(f"Brave exited with status {process.returncode}")
                await asyncio.sleep(0.2)
            if not port_file.exists():
                raise RuntimeError("Brave DevTools endpoint did not start")
            port = int(port_file.read_text().splitlines()[0])
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{port}/json/list") as response:
                    pages = await response.json()
                page = next(item for item in pages if item.get("type") == "page")
                async with session.ws_connect(page["webSocketDebuggerUrl"]) as ws:
                    next_id = 0
                    events = []

                    async def command(method, params=None):
                        nonlocal next_id
                        next_id += 1
                        command_id = next_id
                        await ws.send_json({"id": command_id, "method": method,
                                            "params": params or {}})
                        async with asyncio.timeout(15):
                            while True:
                                message = await ws.receive_json()
                                if "method" in message:
                                    events.append(message)
                                if message.get("id") == command_id:
                                    if "error" in message:
                                        raise RuntimeError(f"{method}: {message['error']}")
                                    return message.get("result", {})

                    async def evaluate(source):
                        result = await command("Runtime.evaluate", {
                            "expression": source, "returnByValue": True,
                            "awaitPromise": True,
                        })
                        if result.get("exceptionDetails"):
                            raise RuntimeError(result["exceptionDetails"].get("text", "JS error"))
                        return result.get("result", {}).get("value")

                    await command("Page.enable")
                    await command("Runtime.enable")
                    await command("Network.enable")
                    await command("Page.navigate", {"url": "https://obscura.q/"})

                    state = None
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        await asyncio.sleep(0.4)
                        try:
                            state = await evaluate(
                                "({url:location.href,title:document.title,"
                                "ready:document.readyState,secure:isSecureContext,"
                                "styles:document.styleSheets.length,"
                                "scriptChars:[...document.scripts].map(s=>s.textContent.length).reduce((a,b)=>a+b,0),"
                                "body:document.body?.innerText?.slice(0,180)})"
                            )
                        except Exception:
                            continue
                        if state and state.get("ready") == "complete" and state.get("title"):
                            break

                    if not state or state.get("url") != EXPECTED:
                        raise RuntimeError(f".q redirect failed or final URL unexpected: {state}")
                    if not state.get("secure"):
                        raise RuntimeError(f"QStorage page did not load as a secure origin: {state}")
                    if state.get("styles", 0) < 1 or state.get("scriptChars", 0) < 500:
                        raise RuntimeError(f"Expected page CSS/JavaScript did not load: {state}")
                    responses = [event["params"].get("response", {}) for event in events
                                 if event.get("method") == "Network.responseReceived"]
                    main_response = next((item for item in responses
                                          if item.get("url") == EXPECTED), None)
                    if not main_response or main_response.get("status") != 200:
                        raise RuntimeError(f"QStorage page did not return 200: {main_response}")

                    print(json.dumps({
                        "freshProfile": True,
                        "localBridgeOrCertificateConfigured": False,
                        "requested": "https://obscura.q/",
                        "finalUrl": state["url"],
                        "title": state["title"],
                        "secureContext": state["secure"],
                        "stylesheets": state["styles"],
                        "inlineJavaScriptCharacters": state["scriptChars"],
                        "mainDocumentStatus": main_response["status"],
                    }, indent=2))
        finally:
            # Brave launches renderer/helper children. Stop the test-only
            # process group so the temporary profile can be removed reliably.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(run())
