"""Enemy scouting for the loading screen: rank, winrate and champion mastery via the Riot API."""
import threading
import time

from .lcu import ok
from .riotapi import platform_from_region

CACHE_TTL = 600  # seconds; dodged lobbies must not burn the dev rate limit
MAX_ENEMIES = 5
SPECTATOR_RETRIES = 4
SPECTATOR_RETRY_DELAY = 5  # the spectator endpoint 404s until the game really starts


# Some clients report a UUID-shaped puuid that the Riot API cannot decrypt (HTTP 400).
# The reliable path is resolving the real puuid from the Riot ID via Account-V1.
_puuid_cache = {}


def client_context(lcu, riot):
    """Returns (status, context): 'ok' -> (puuid, platform); otherwise context is None."""
    code, summoner = lcu.get("/lol-summoner/v1/current-summoner")
    if not ok(code) or not isinstance(summoner, dict):
        return "unavailable", None
    code, region = lcu.get("/riotclient/region-locale")
    platform = (
        platform_from_region(region.get("region", "")) if ok(code) and isinstance(region, dict) else ""
    )
    if not platform:
        return "unavailable", None
    puuid = summoner.get("puuid", "")
    if len(puuid) >= 70:
        return "ok", (puuid, platform)
    game, tag = summoner.get("gameName", ""), summoner.get("tagLine", "")
    if not game:
        return "unavailable", None
    cache_key = f"{game}#{tag}"
    if cache_key not in _puuid_cache:
        code, account = riot.regional_get(
            platform, f"/riot/account/v1/accounts/by-riot-id/{game}/{tag}"
        )
        if code in (401, 403):
            return "bad_key", None
        if not ok(code) or not isinstance(account, dict) or not account.get("puuid"):
            return "unavailable", None
        _puuid_cache[cache_key] = account["puuid"]
    return "ok", (_puuid_cache[cache_key], platform)


class Scout:
    """Runs once per game. Costs ~16 requests total (1 spectator + 3 per enemy)."""

    def __init__(self, riot, lcu):
        self.riot = riot
        self.lcu = lcu
        self._cache = {}  # puuid -> (timestamp, info)
        self._lock = threading.Lock()

    def _context(self):
        return client_context(self.lcu, self.riot)

    def scout(self):
        """Returns (status, players). status: ok | no_key | bad_key | unavailable."""
        if not self.riot.available:
            return "no_key", []
        status, context = self._context()
        if status != "ok":
            return status, []
        puuid, platform = context

        game = None
        for attempt in range(SPECTATOR_RETRIES):
            code, body = self.riot.platform_get(
                platform, f"/lol/spectator/v5/active-games/by-summoner/{puuid}"
            )
            if code in (401, 403):
                return "bad_key", []
            if code == 404 or code is None:
                if attempt < SPECTATOR_RETRIES - 1:
                    time.sleep(SPECTATOR_RETRY_DELAY)
                continue
            if ok(code) and isinstance(body, dict):
                game = body
            break
        if not game:
            return "unavailable", []

        participants = game.get("participants") or []
        my_team = next((p.get("teamId") for p in participants if p.get("puuid") == puuid), None)
        enemies = [p for p in participants if p.get("teamId") != my_team][:MAX_ENEMIES]
        return "ok", [self._player_info(platform, p) for p in enemies]

    def _player_info(self, platform, participant):
        puuid = participant.get("puuid", "")
        with self._lock:
            cached = self._cache.get(puuid)
        if cached and time.monotonic() - cached[0] < CACHE_TTL:
            info = dict(cached[1])
        else:
            info = {"riot_id": "", "mastery_level": 0, "mastery_points": 0,
                    "tier": "", "rank": "", "lp": 0, "winrate": None}

            code, account = self.riot.regional_get(platform, f"/riot/account/v1/accounts/by-puuid/{puuid}")
            if ok(code) and isinstance(account, dict) and account.get("gameName"):
                tag = f"#{account['tagLine']}" if account.get("tagLine") else ""
                info["riot_id"] = f"{account['gameName']}{tag}"

            code, mastery = self.riot.platform_get(
                platform,
                f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{participant.get('championId')}",
            )
            if ok(code) and isinstance(mastery, dict):
                info["mastery_level"] = mastery.get("championLevel", 0)
                info["mastery_points"] = mastery.get("championPoints", 0)

            code, entries = self.riot.platform_get(platform, f"/lol/league/v4/entries/by-puuid/{puuid}")
            if ok(code) and isinstance(entries, list):
                solo = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
                if solo:
                    wins, losses = solo.get("wins", 0), solo.get("losses", 0)
                    info.update(
                        tier=solo.get("tier", "").capitalize(),
                        rank=solo.get("rank", ""),
                        lp=solo.get("leaguePoints", 0),
                        winrate=round(wins / (wins + losses) * 100) if wins + losses else None,
                    )
            with self._lock:
                self._cache[puuid] = (time.monotonic(), dict(info))
        info["champion_id"] = participant.get("championId", 0)
        return info
