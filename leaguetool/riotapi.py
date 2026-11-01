"""Riot Games API client.

The key comes from the user's Settings field or, for local development, from a
.env file (API_KEY_RIOT=...). The .env is git-ignored and never shipped in builds.
"""
import os
import threading
import time
from collections import deque
from pathlib import Path

import requests

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Platform (server) ids -> regional routing used by Match-V5 / Account-V1.
REGION_OF_PLATFORM = {
    "br1": "americas", "la1": "americas", "la2": "americas", "na1": "americas", "me1": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "sg2": "sea", "tw2": "sea", "vn2": "sea",
}

# Dev keys allow 20 req/s and 100 req/2min; stay clearly below that.
MAX_PER_SECOND = 15
MAX_PER_TWO_MINUTES = 90


def load_env_key(path=ENV_PATH):
    """Reads API_KEY_RIOT from a local .env (plain KEY=VALUE lines, no dependency)."""
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() == "API_KEY_RIOT":
                    return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


class RiotClient:
    def __init__(self, key=""):
        self._key = key
        self._session = requests.Session()
        self._calls = deque()
        self._lock = threading.Lock()

    @property
    def available(self):
        return bool(self._key)

    def set_key(self, key):
        with self._lock:
            self._key = key

    def _throttle(self):
        with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > 120:
                self._calls.popleft()
            recent = sum(1 for stamp in self._calls if now - stamp < 1)
            if len(self._calls) >= MAX_PER_TWO_MINUTES:
                time.sleep(120 - (now - self._calls[0]) + 0.1)
            elif recent >= MAX_PER_SECOND:
                time.sleep(1 - (now - self._calls[-1]) + 0.05)
            self._calls.append(time.monotonic())

    def _get(self, url, params=None, retries=1):
        """Returns (status, body). status None if unreachable or no key configured."""
        if not self._key:
            return None, None
        for _ in range(retries + 1):
            self._throttle()
            try:
                response = self._session.get(
                    url, params=params, headers={"X-Riot-Token": self._key}, timeout=8
                )
            except requests.RequestException:
                return None, None
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 2)))
                continue
            try:
                return response.status_code, response.json()
            except ValueError:
                return response.status_code, None
        return 429, None

    def platform_get(self, platform, path, params=None):
        """Server-scoped endpoints (summoner, league, champion mastery, spectator)."""
        return self._get(f"https://{platform}.api.riotgames.com{path}", params)

    def regional_get(self, platform, path, params=None):
        """Region-scoped endpoints (match, account). Platform id is translated automatically."""
        region = REGION_OF_PLATFORM.get(platform.lower(), "americas")
        return self._get(f"https://{region}.api.riotgames.com{path}", params)


# LCU reports either platform ids ('EUW1') or short cluster codes ('EUW', 'LAN').
REGION_ALIASES = {
    "br": "br1", "eune": "eun1", "euw": "euw1", "lan": "la1", "las": "la2", "na": "na1",
    "oce": "oc1", "ru": "ru", "tr": "tr1", "jp": "jp1", "kr": "kr", "me": "me1",
    "sg": "sg2", "tw": "tw2", "vn": "vn2",
}


def platform_from_region(region):
    """LCU region ('EUW1', 'EUW', 'lan'…) -> Riot API platform id, or '' if unknown."""
    platform = (region or "").lower()
    if platform in REGION_OF_PLATFORM:
        return platform
    return REGION_ALIASES.get(platform, "")


def resolve_key(configured):
    """The user's Settings key wins; the local .env is the developer fallback."""
    return (configured or "").strip() or load_env_key()
