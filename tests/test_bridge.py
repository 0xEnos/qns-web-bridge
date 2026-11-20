import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp import ClientSession, web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "local"))
import bridge_v2  # noqa: E402


class BundledResolverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="qns-resolver-test-")
        state = Path(self.temp.name)
        bridge_v2.DATA_DIR = state / "state"
        bridge_v2.MAPPINGS = bridge_v2.DATA_DIR / "mappings.json"
        bridge_v2.LOCAL_RECORDS_DIR = bridge_v2.DATA_DIR / "records"
        bridge_v2.PUBLISH_DIR = ROOT / "registry"
        self.qstorage = web.Application()
        self.qstorage.router.add_get("/manifest.json", self.unavailable)
        self.runner = web.AppRunner(self.qstorage)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        bridge_v2.REGISTRY_URLS = (
            f"http://127.0.0.1:{self.port}/manifest.json",
            "bundled://registry/manifest.json",
        )
        self.session = ClientSession()
        self.resolver = bridge_v2.Resolver(self.session)

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()
        self.temp.cleanup()

    async def unavailable(self, request):
        return web.Response(status=503, text="simulated QStorage outage")

    async def test_obscura_resolves_from_bundled_manifest_without_local_mapping(self):
        self.assertFalse(bridge_v2.MAPPINGS.exists())
        await self.resolver.refresh_registry(force=True)
        self.assertEqual(
            await self.resolver.target("obscura.q"),
            {"kind": "qstorage", "bucket": "0xenos"},
        )
        self.assertEqual(self.resolver.mappings, {})

    async def test_bundled_directory_contains_only_expected_minimal_entry(self):
        await self.resolver.refresh_registry(force=True)
        names = sorted(self.resolver.registry)
        self.assertIn("obscura.q", names)
        self.assertEqual(self.resolver.registry["obscura.q"]["destination"],
                         {"kind": "qstorage", "bucket": "0xenos"})


class ProxyTranslationTests(unittest.TestCase):
    def test_absolute_redirects_rewrite_upstream_origin_to_q_name(self):
        self.assertEqual(
            bridge_v2.translated("https://bucket.qstorage.quilibrium.com/login?next=/",
                                 "https://bucket.qstorage.quilibrium.com", "https://obscura.q"),
            "https://obscura.q/login?next=/",
        )

    def test_upstream_http_links_are_upgraded_to_the_q_https_origin(self):
        self.assertEqual(
            bridge_v2.translated("http://bucket.qstorage.quilibrium.com/a.css",
                                 "https://bucket.qstorage.quilibrium.com", "https://obscura.q"),
            "https://obscura.q/a.css",
        )


if __name__ == "__main__":
    unittest.main()
