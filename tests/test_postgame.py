import unittest

import leaguetool.postgame as postgame
from leaguetool.postgame import PostGame, analyze_match, analyze_timeline
from leaguetool.riotapi import RiotClient
from tests.test_scouting import FakeLCU, FakeRiot

MY_PUUID = "me-puuid"


def participant(pid, team, puuid, kills=0, deaths=0, assists=0, damage=10000, minions=100,
                vision=20, gold=10000, win=False, role="MIDDLE", name=None):
    return {
        "participantId": pid, "teamId": team, "puuid": puuid, "championId": 100 + pid,
        "kills": kills, "deaths": deaths, "assists": assists,
        "totalDamageDealtToChampions": damage,
        "totalMinionsKilled": minions, "neutralMinionsKilled": 0,
        "visionScore": vision, "wardsPlaced": 8, "goldEarned": gold,
        "teamPosition": role, "win": win, "riotIdGameName": name or f"P{pid}",
    }


def make_match(me_overrides=None):
    base = dict(kills=10, deaths=2, assists=8, damage=30000, minions=210, vision=40,
                gold=14000, win=True, name="Yo")
    base.update(me_overrides or {})
    me = participant(1, 100, MY_PUUID, **base)
    allies = [participant(i, 100, f"a{i}", damage=8000, win=True) for i in range(2, 6)]
    enemies = [participant(i + 5, 200, f"e{i}", damage=9000) for i in range(1, 6)]
    return {"info": {"gameDuration": 1800, "participants": [me] + allies + enemies}}


def make_timeline(my_team_gold=25000, their_team_gold=21000):
    frames = []
    for _ in range(20):
        frames.append({
            "participantFrames": {
                **{str(i): {"totalGold": my_team_gold // 5} for i in range(1, 6)},
                **{str(i): {"totalGold": their_team_gold // 5} for i in range(6, 11)},
            }
        })
    return {"info": {"frames": frames}}


class AnalyzeMatchTest(unittest.TestCase):
    def test_core_stats(self):
        analysis = analyze_match(make_match(), make_timeline(), MY_PUUID)
        self.assertTrue(analysis["win"])
        self.assertEqual((analysis["kills"], analysis["deaths"], analysis["assists"]), (10, 2, 8))
        self.assertEqual(analysis["damage"], 30000)
        # Team damage = 30000 + 4*8000 = 62000 -> 48%
        self.assertEqual(analysis["damage_share"], 48)
        self.assertEqual(analysis["csm"], 7.0)  # 210 cs / 30 min
        self.assertEqual(analysis["gold15_diff"], 4000)

    def test_highlights_for_good_game(self):
        analysis = analyze_match(make_match(), make_timeline(), MY_PUUID)
        keys = {key for key, _params, _good in analysis["highlights"]}
        self.assertIn("post.hi.win", keys)
        self.assertIn("post.hi.damage", keys)      # 48% share
        self.assertIn("post.hi.kda", keys)         # 9.0
        self.assertIn("post.hi.gold_ahead", keys)  # +4000

    def test_highlights_for_bad_game(self):
        overrides = {"kills": 1, "deaths": 10, "assists": 2, "damage": 5000, "minions": 80,
                     "vision": 10, "win": False}
        analysis = analyze_match(make_match(overrides), make_timeline(18000, 26000), MY_PUUID)
        keys = {key for key, _params, _good in analysis["highlights"]}
        self.assertIn("post.hi.loss", keys)
        self.assertIn("post.hi.deaths", keys)
        self.assertIn("post.hi.cs_low", keys)       # 80/30 = 2.7
        self.assertIn("post.hi.vision_low", keys)   # 10/30 = 0.33
        self.assertIn("post.hi.gold_behind", keys)  # -8000
        self.assertNotIn("post.hi.damage", keys)

    def test_support_skips_cs_warnings(self):
        overrides = {"minions": 20, "role": "UTILITY", "vision": 60}
        analysis = analyze_match(make_match(overrides), make_timeline(), MY_PUUID)
        keys = {key for key, _params, _good in analysis["highlights"]}
        self.assertNotIn("post.hi.cs_low", keys)
        self.assertIn("post.hi.vision_high", keys)

    def test_no_timeline_means_no_gold_diff(self):
        analysis = analyze_match(make_match(), None, MY_PUUID)
        self.assertIsNone(analysis["gold15_diff"])

    def test_unknown_puuid_returns_none(self):
        self.assertIsNone(analyze_match(make_match(), make_timeline(), "someone-else"))

    def test_scoreboard_my_team_first_and_damage_sorted(self):
        analysis = analyze_match(make_match(), make_timeline(), MY_PUUID)
        players = analysis["players"]
        self.assertEqual(len(players), 10)
        self.assertTrue(all(p["mine"] for p in players[:5]))
        self.assertTrue(all(not p["mine"] for p in players[5:]))
        self.assertTrue(players[0]["is_me"])  # highest damage on my team


def rich_frame(minute, diff, my_cs, events=()):
    """A frame where team100 minus team200 gold equals diff; participant 1 is me."""
    base = 5000 + minute * 400
    frames = {}
    for pid in range(1, 6):
        frames[str(pid)] = {"totalGold": base + diff // 10, "level": min(18, 1 + minute // 2),
                            "minionsKilled": my_cs if pid == 1 else 0, "jungleMinionsKilled": 0}
    for pid in range(6, 11):
        frames[str(pid)] = {"totalGold": base - diff // 10, "level": 1, "minionsKilled": 0,
                            "jungleMinionsKilled": 0}
    return {"participantFrames": frames, "events": list(events)}


def rich_timeline():
    frames = []
    for m in range(25):
        diff = 2000 if m < 15 else -3000            # huge swing at minute 15
        my_cs = m * 7 if m <= 12 else 84 + (m - 12) * 2  # farm stalls after min 12
        events = []
        if m == 14:
            events.append({"type": "CHAMPION_KILL", "killerId": 7, "victimId": 1})
        if m == 15:
            events.append({"type": "ELITE_MONSTER_KILL", "killerId": 7, "monsterType": "DRAGON"})
        frames.append(rich_frame(m, diff, my_cs, events))
    return {"info": {"frames": frames}}


class TimelineTest(unittest.TestCase):
    def test_rows_have_diff_cs_and_events(self):
        rows, _ = analyze_timeline(rich_timeline(), my_team_id=100, my_pid=1)
        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[5]["diff"], 2000)
        self.assertEqual(rows[14]["events"], [("post.ev.death", {}, False)])
        kind, params, good = rows[15]["events"][0]
        self.assertEqual((kind, params["what"], good), ("post.ev.objective", "post.obj.DRAGON", False))

    def test_death_blamed_for_lost_dragon(self):
        _rows, insights = analyze_timeline(rich_timeline(), my_team_id=100, my_pid=1)
        self.assertIn(("post.ti.death_objective", {"minute": 14, "what": "post.obj.DRAGON"}, False),
                      insights)

    def test_swing_and_cs_stall_detected(self):
        _rows, insights = analyze_timeline(rich_timeline(), my_team_id=100, my_pid=1)
        keys = {key for key, _p, _g in insights}
        self.assertIn("post.ti.swing", keys)      # -5000 at min 15
        self.assertIn("post.ti.cs_stall", keys)   # 3.0 CS/min between 11 and 16
        self.assertNotIn("post.ti.comeback", keys)

    def test_comeback_detected(self):
        frames = [rich_frame(m, -2000 if m < 12 else 2500, m * 6) for m in range(20)]
        _rows, insights = analyze_timeline({"info": {"frames": frames}}, 100, 1)
        self.assertIn(("post.ti.comeback", {"minute": 12}, True), insights)

    def test_empty_timeline(self):
        self.assertEqual(analyze_timeline({}, 100, 1), ([], []))

    def test_rows_track_gold_level_and_cumulative_kda(self):
        frames = []
        for m in range(10):
            events = []
            if m == 3:
                events.append({"type": "CHAMPION_KILL", "killerId": 1, "victimId": 6})
            if m == 4:
                events.append({"type": "CHAMPION_KILL", "killerId": 7, "victimId": 1})
            if m == 5:
                events.append({"type": "CHAMPION_KILL", "killerId": 2, "victimId": 6,
                               "assistingParticipantIds": [1]})
            frames.append(rich_frame(m, 500, m * 6, events))
        rows, _ = analyze_timeline({"info": {"frames": frames}}, 100, 1)
        self.assertEqual(rows[9]["kda"], (1, 1, 1))  # kill min 3, death min 4, assist min 5
        self.assertEqual(rows[9]["level"], 5)
        self.assertGreater(rows[9]["gold"], 0)

    def test_match_analysis_includes_timeline(self):
        analysis = analyze_match(make_match(), rich_timeline(), MY_PUUID)
        self.assertEqual(len(analysis["timeline"]), 25)
        keys = {key for key, _p, _g in analysis["highlights"]}
        self.assertIn("post.ti.swing", keys)


class FetchFlowTest(unittest.TestCase):
    ROUTES = {
        "by-riot-id": (200, {"puuid": MY_PUUID}),
        "/ids": (200, ["EUW1_123"]),
        "/matches/EUW1_123/timeline": (200, make_timeline()),
        "/matches/EUW1_123": (200, make_match()),
    }

    def make(self, routes):
        return PostGame(FakeRiot(routes), FakeLCU())

    def test_no_key(self):
        pg = PostGame(RiotClient(""), FakeLCU())
        self.assertEqual(pg.fetch_latest(), ("no_key", None))

    def test_bad_key(self):
        pg = self.make({"by-riot-id": (401, None), "/ids": (401, None)})
        self.assertEqual(pg.fetch_latest(), ("bad_key", None))

    def test_ok_flow(self):
        status, analysis = self.make(self.ROUTES).fetch_latest()
        self.assertEqual(status, "ok")
        self.assertEqual(analysis["champion_id"], 101)

    def test_retries_until_match_is_published(self):
        calls = []

        def ids(_url):
            calls.append(1)
            return (200, ["EUW1_123"]) if len(calls) >= 2 else (200, [])

        original_sleep = postgame.time.sleep
        postgame.time.sleep = lambda _s: None
        try:
            status, analysis = self.make({**self.ROUTES, "/ids": ids}).fetch_latest()
        finally:
            postgame.time.sleep = original_sleep
        self.assertEqual(status, "ok")
        self.assertEqual(len(calls), 2)

    def test_match_never_appears(self):
        original_sleep = postgame.time.sleep
        postgame.time.sleep = lambda _s: None
        try:
            status, _ = self.make({"/ids": (200, [])}).fetch_latest()
        finally:
            postgame.time.sleep = original_sleep
        self.assertEqual(status, "unavailable")


if __name__ == "__main__":
    unittest.main()
