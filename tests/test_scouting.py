import unittest

import leaguetool.scouting as scouting
from leaguetool.riotapi import RiotClient
from leaguetool.scouting import Scout


class FakeLCU:
    def __init__(self, region="EUW1", puuid="me-puuid", game_name="Yo", tag_line="EUW"):
        summoner = {"puuid": puuid, "gameName": game_name, "tagLine": tag_line}
        self.routes = {
            "/lol-summoner/v1/current-summoner": (200, summoner),
            "/riotclient/region-locale": (200, {"region": region, "locale": "es-MX"}),
        }

    def get(self, path):
        return self.routes.get(path, (404, None))


class FakeRiot(RiotClient):
    """Routes by URL substring; counts every request."""

    def __init__(self, routes):
        super().__init__("RGAPI-test")
        self.routes = routes
        self.calls = []

    def _get(self, url, params=None, retries=1):
        self.calls.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                return response(url) if callable(response) else response
        return 404, None


SPECTATOR = (
    200,
    {
        "participants": [
            {"puuid": "me-puuid", "teamId": 100, "championId": 103},
            {"puuid": "e1", "teamId": 200, "championId": 238},
            {"puuid": "e2", "teamId": 200, "championId": 51},
        ]
    },
)

FULL_ROUTES = {
    "by-riot-id": (200, {"puuid": "me-puuid"}),  # short LCU puuid -> resolved via Riot ID
    "active-games": SPECTATOR,
    "accounts/by-puuid/e1": (200, {"gameName": "RivalOne", "tagLine": "EUW"}),
    "accounts/by-puuid/e2": (200, {"gameName": "RivalTwo", "tagLine": "EUW"}),
    "by-puuid/e1/by-champion": (200, {"championLevel": 7, "championPoints": 2500000}),
    "by-puuid/e2/by-champion": (200, {"championLevel": 2, "championPoints": 8000}),
    "entries/by-puuid/e1": (200, [{"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "II",
                                   "leaguePoints": 45, "wins": 60, "losses": 40}]),
    "entries/by-puuid/e2": (200, []),
}


def make_scout(routes, **lcu_kwargs):
    return Scout(FakeRiot(routes), FakeLCU(**lcu_kwargs))


class ScoutTest(unittest.TestCase):
    def setUp(self):
        scouting._puuid_cache.clear()

    def test_no_key(self):
        scout = Scout(RiotClient(""), FakeLCU())
        self.assertEqual(scout.scout(), ("no_key", []))

    def test_bad_key(self):
        scout = make_scout({"active-games": (403, None), "by-riot-id": (403, None)})
        self.assertEqual(scout.scout(), ("bad_key", []))

    def test_bad_key_during_spectator(self):
        riot_routes = {**FULL_ROUTES, "active-games": (403, None)}
        scout = Scout(FakeRiot(riot_routes), FakeLCU(puuid="x" * 78))
        self.assertEqual(scout.scout(), ("bad_key", []))

    def test_missing_lcu_context(self):
        scout = make_scout(FULL_ROUTES, puuid="", game_name="")
        self.assertEqual(scout.scout(), ("unavailable", []))

    def test_full_scout(self):
        scout = make_scout(FULL_ROUTES)
        status, players = scout.scout()
        self.assertEqual(status, "ok")
        self.assertEqual(len(players), 2)
        fed, weak = players
        self.assertEqual(fed["riot_id"], "RivalOne#EUW")
        self.assertEqual(fed["champion_id"], 238)
        self.assertEqual(fed["tier"], "Diamond")
        self.assertEqual(fed["lp"], 45)
        self.assertEqual(fed["winrate"], 60)
        self.assertEqual(fed["mastery_level"], 7)
        self.assertEqual(weak["tier"], "")  # unranked
        self.assertIsNone(weak["winrate"])

    def test_spectator_retries_then_succeeds(self):
        attempts = []

        def spectator(_url):
            attempts.append(1)
            return SPECTATOR if len(attempts) >= 3 else (404, None)

        original_sleep = scouting.time.sleep
        scouting.time.sleep = lambda _s: None
        try:
            scout = make_scout({**FULL_ROUTES, "active-games": spectator})
            status, players = scout.scout()
        finally:
            scouting.time.sleep = original_sleep
        self.assertEqual(status, "ok")
        self.assertEqual(len(attempts), 3)

    def test_spectator_gives_up_after_retries(self):
        original_sleep = scouting.time.sleep
        scouting.time.sleep = lambda _s: None
        try:
            scout = make_scout({"active-games": (404, None)})
            status, _ = scout.scout()
        finally:
            scouting.time.sleep = original_sleep
        self.assertEqual(status, "unavailable")

    def test_cache_avoids_repeating_player_calls(self):
        riot = FakeRiot(FULL_ROUTES)
        scout = Scout(riot, FakeLCU())
        scout.scout()
        first_calls = len(riot.calls)
        scout.scout()
        new_calls = riot.calls[first_calls:]
        self.assertEqual(len(new_calls), 1)  # only the spectator call is repeated
        self.assertIn("active-games", new_calls[0])

    def test_long_puuid_skips_account_resolution(self):
        riot = FakeRiot(FULL_ROUTES)
        scout = Scout(riot, FakeLCU(puuid="x" * 78))
        scout.scout()
        self.assertFalse(any("by-riot-id" in url for url in riot.calls))

    def test_uuid_puuid_is_resolved_via_riot_id(self):
        riot = FakeRiot(FULL_ROUTES)
        scout = Scout(riot, FakeLCU(puuid="f438ad2c-f609-53b3-8b6c-ee9599c809d0"))
        status, _players = scout.scout()
        self.assertEqual(status, "ok")
        self.assertTrue(any("by-riot-id" in url for url in riot.calls))


if __name__ == "__main__":
    unittest.main()
