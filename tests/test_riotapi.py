import tempfile
import unittest
from pathlib import Path

from leaguetool.riotapi import (
    RiotClient,
    load_env_key,
    platform_from_region,
    resolve_key,
)


class EnvKeyTest(unittest.TestCase):
    def write(self, text):
        path = Path(tempfile.mkdtemp()) / ".env"
        path.write_text(text, encoding="utf-8")
        return path

    def test_reads_key(self):
        path = self.write("# comment\nAPI_KEY_RIOT=RGAPI-abc-123\nOTHER=x\n")
        self.assertEqual(load_env_key(path), "RGAPI-abc-123")

    def test_quoted_and_spaced(self):
        path = self.write('API_KEY_RIOT = "RGAPI-xyz"\n')
        self.assertEqual(load_env_key(path), "RGAPI-xyz")

    def test_missing_file_or_key(self):
        self.assertEqual(load_env_key(Path("does/not/exist/.env")), "")
        self.assertEqual(load_env_key(self.write("FOO=bar\n")), "")

    def test_resolve_prefers_configured(self):
        self.assertEqual(resolve_key("RGAPI-user"), "RGAPI-user")
        self.assertEqual(resolve_key("  "), load_env_key() or "")


class RegionTest(unittest.TestCase):
    def test_lcu_regions_map_to_platforms(self):
        self.assertEqual(platform_from_region("EUW1"), "euw1")
        self.assertEqual(platform_from_region("la2"), "la2")
        self.assertEqual(platform_from_region(""), "")

    def test_short_cluster_codes_map_too(self):
        self.assertEqual(platform_from_region("EUW"), "euw1")
        self.assertEqual(platform_from_region("lan"), "la1")
        self.assertEqual(platform_from_region("LAS"), "la2")
        self.assertEqual(platform_from_region("KR"), "kr")
        self.assertEqual(platform_from_region("unknown"), "")


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requests.append((url, headers))
        return self.responses.pop(0)


class RiotClientTest(unittest.TestCase):
    def make(self, responses):
        client = RiotClient("RGAPI-test")
        client._session = FakeSession(responses)
        client._throttle = lambda: None  # tests stay instant
        return client

    def test_no_key_short_circuits(self):
        client = RiotClient("")
        self.assertFalse(client.available)
        self.assertEqual(client.platform_get("euw1", "/x"), (None, None))

    def test_sends_token_header(self):
        client = self.make([FakeResponse(200, {"ok": True})])
        status, body = client.platform_get("euw1", "/lol/status/v4/platform-data")
        self.assertEqual((status, body), (200, {"ok": True}))
        self.assertEqual(client._session.requests[0][1]["X-Riot-Token"], "RGAPI-test")
        self.assertTrue(client._session.requests[0][0].startswith("https://euw1.api.riotgames.com"))

    def test_regional_routing(self):
        client = self.make([FakeResponse(200, {})])
        client.regional_get("LA2", "/lol/match/v5/matches/x")
        self.assertTrue(client._session.requests[0][0].startswith("https://americas.api.riotgames.com"))

    def test_retries_on_429(self):
        client = self.make([FakeResponse(429, headers={"Retry-After": "0"}), FakeResponse(200, {"ok": 1})])
        import leaguetool.riotapi as riotapi

        original_sleep = riotapi.time.sleep
        riotapi.time.sleep = lambda _s: None
        try:
            status, body = client._get("https://x")
        finally:
            riotapi.time.sleep = original_sleep
        self.assertEqual((status, body), (200, {"ok": 1}))
        self.assertEqual(len(client._session.requests), 2)


if __name__ == "__main__":
    unittest.main()
