import unittest

from leaguetool.liveanalysis import (
    Advice,
    analyze,
    build_champion_db,
    champion_class,
    classify,
    _enemies,
    _items,
    _objectives,
)

CHAMPIONS = {
    103: {"id": 103, "key": "Ahri", "name": "Ahri", "tags": ["Mage", "Assassin"],
          "info": {"attack": 3, "defense": 4, "magic": 8}},
    51: {"id": 51, "key": "Caitlyn", "name": "Caitlyn", "tags": ["Marksman"],
         "info": {"attack": 8, "defense": 2, "magic": 2}},
    54: {"id": 54, "key": "Malphite", "name": "Malphite", "tags": ["Tank", "Fighter"],
         "info": {"attack": 5, "defense": 9, "magic": 3}},
    16: {"id": 16, "key": "Soraka", "name": "Soraka", "tags": ["Support", "Mage"],
         "info": {"attack": 2, "defense": 5, "magic": 7}},
    238: {"id": 238, "key": "Zed", "name": "Zed", "tags": ["Assassin"],
          "info": {"attack": 9, "defense": 2, "magic": 1}},
    222: {"id": 222, "key": "Jinx", "name": "Jinx", "tags": ["Marksman"],
          "info": {"attack": 9, "defense": 2, "magic": 2}},
}

DB = build_champion_db(CHAMPIONS)


def player(name, champion, team, kills=0, deaths=0, assists=0, level=10, gold_items=(), position=""):
    return {
        "summonerName": name,
        "championName": champion,
        "team": team,
        "level": level,
        "position": position,
        "scores": {"kills": kills, "deaths": deaths, "assists": assists, "creepScore": 100},
        "items": [{"itemID": i, "price": price, "count": 1} for i, price in gold_items],
    }


def game_data(players, events=(), game_time=600):
    return {
        "activePlayer": {"summonerName": "me"},
        "allPlayers": players,
        "events": {"Events": list(events)},
        "gameData": {"gameTime": game_time},
    }


def enemy_set():
    return [
        player("me", "Ahri", "ORDER"),
        player("ally", "Malphite", "ORDER"),
        player("e1", "Caitlyn", "CHAOS", kills=7, deaths=1, assists=4, level=13,
               gold_items=((3031, 3400), (3036, 3000))),
        player("e2", "Soraka", "CHAOS", kills=1, deaths=2, assists=8, gold_items=((3065, 2800),)),
        player("e3", "Zed", "CHAOS", kills=6, deaths=2, assists=1, level=12,
               gold_items=((3142, 3000),)),
    ]


class ClassifyTest(unittest.TestCase):
    def test_damage_profiles(self):
        self.assertEqual(classify(CHAMPIONS[103]), "AP")
        self.assertEqual(classify(CHAMPIONS[51]), "AD")
        self.assertEqual(classify(CHAMPIONS[54]), "TANK")

    def test_missing_data_defaults(self):
        self.assertEqual(classify({}), "MIXED")
        self.assertEqual(classify({"info": {"attack": 5, "magic": 5}}), "MIXED")


class EnemiesTest(unittest.TestCase):
    def test_filters_allies_and_sorts_by_threat(self):
        enemies = _enemies(game_data(enemy_set()), DB)
        self.assertEqual([e["name"] for e in enemies], ["Caitlyn", "Soraka", "Zed"])
        self.assertTrue(all(e["gold"] > 0 for e in enemies))

    def test_unknown_champion_still_listed(self):
        data = game_data([player("me", "Ahri", "ORDER"), player("e1", "NewChamp", "CHAOS")])
        enemies = _enemies(data, DB)
        self.assertEqual(enemies[0]["name"], "NewChamp")
        self.assertEqual(enemies[0]["damage"], "MIXED")

    def test_bots_are_tagged(self):
        bot = player("e1", "Malphite", "CHAOS")
        bot["isBot"] = True
        data = game_data([player("me", "Ahri", "ORDER"), bot])
        self.assertIn("🤖", _enemies(data, DB)[0]["name"])


class AnalyzeTest(unittest.TestCase):
    def test_empty_snapshot_returns_empty_advice(self):
        advice = analyze({}, DB)
        self.assertIsInstance(advice, Advice)
        self.assertEqual(advice.focus, [])

    def test_focus_prioritizes_fed_carry(self):
        advice = analyze(game_data(enemy_set()), DB)
        top = advice.focus[0]
        self.assertEqual(top.params["champion"], "Caitlyn")
        self.assertEqual(top.text_key, "live.focus.fed")
        self.assertLessEqual(len(advice.focus), 3)

    def test_focus_carries_champion_icons(self):
        advice = analyze(game_data(enemy_set()), DB)
        self.assertEqual(advice.focus[0].icon_ids, [51])  # Caitlyn, for the overlay icon

    def test_items_for_ad_heavy_team(self):
        advice = analyze(game_data(enemy_set()), DB)
        kinds = {s.text_key for s in advice.items}
        self.assertIn("live.item.armor", kinds)
        self.assertIn("live.item.antiheal", kinds)  # Soraka
        self.assertIn("live.item.survive", kinds)   # fed Zed
        for suggestion in advice.items:
            self.assertTrue(suggestion.item_ids)

    def test_items_for_ap_heavy_team(self):
        players = [
            player("me", "Caitlyn", "ORDER"),
            player("e1", "Ahri", "CHAOS", kills=4, gold_items=((3089, 3600), (3135, 3000))),
            player("e2", "Soraka", "CHAOS", gold_items=((3065, 2800),)),
            player("e3", "Malphite", "CHAOS", gold_items=((3068, 2700),)),
        ]
        # Malphite classifies as TANK, so AP gold = Ahri + Soraka > AD gold
        advice = analyze(game_data(players), DB)
        kinds = {s.text_key for s in advice.items}
        self.assertIn("live.item.mr", kinds)
        self.assertNotIn("live.item.pen", kinds)  # only one tank
        self.assertNotIn("live.item.armor", kinds)

    def test_penetration_against_two_tanks(self):
        players = [
            player("me", "Caitlyn", "ORDER"),
            player("e1", "Malphite", "CHAOS"),
            player("e2", "Malphite", "CHAOS"),
            player("e3", "Zed", "CHAOS"),
        ]
        advice = analyze(game_data(players), DB)
        self.assertIn("live.item.pen", {s.text_key for s in advice.items})

    def test_dragon_soul_warning(self):
        events = [
            {"EventName": "DragonKill", "KillerName": n, "EventTime": t}
            for n, t in (("e1", 300), ("e2", 600), ("e1", 900))
        ]
        advice = analyze(game_data(enemy_set(), events, game_time=1000), DB)
        self.assertEqual(advice.objectives[0].text_key, "live.obj.soul")

    def test_baron_push_after_our_kill(self):
        events = [{"EventName": "BaronKill", "KillerName": "me", "EventTime": 1560}]
        advice = analyze(game_data(enemy_set(), events, game_time=1600), DB)
        self.assertEqual(advice.objectives[0].text_key, "live.obj.push_baron")

    def test_enemy_baron_warning(self):
        events = [{"EventName": "BaronKill", "KillerName": "e1", "EventTime": 1560}]
        advice = analyze(game_data(enemy_set(), events, game_time=1600), DB)
        self.assertEqual(advice.objectives[0].text_key, "live.obj.enemy_baron")

    def test_ace_suggestion(self):
        events = [{"EventName": "Ace", "Acer": "me", "EventTime": 590}]
        advice = analyze(game_data(enemy_set(), events, game_time=600), DB)
        keys = {s.text_key for s in advice.objectives}
        self.assertIn("live.obj.ace", keys)

    def test_objectives_capped_and_prioritized(self):
        advice = analyze(game_data(enemy_set(), game_time=1700), DB)
        self.assertLessEqual(len(advice.objectives), 3)
        priorities = [s.priority for s in advice.objectives]
        self.assertEqual(priorities, sorted(priorities))


class ChampionClassTest(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(champion_class(CHAMPIONS[51]), "marksman")    # Caitlyn
        self.assertEqual(champion_class(CHAMPIONS[238]), "assassin")   # Zed
        self.assertEqual(champion_class(CHAMPIONS[54]), "tank")        # Malphite
        self.assertEqual(champion_class(CHAMPIONS[16]), "enchanter")   # Soraka
        self.assertEqual(champion_class(CHAMPIONS[103]), "mage")       # Ahri: assassin tag but AP

    def test_unknown_defaults_to_fighter(self):
        self.assertEqual(champion_class({}), "fighter")

    def test_role_overrides_support_tags(self):
        soraka, malphite = CHAMPIONS[16], CHAMPIONS[54]
        self.assertEqual(champion_class(soraka, "TOP"), "mage")         # off-role: solo-lane core
        self.assertEqual(champion_class(soraka, "UTILITY"), "enchanter")
        self.assertEqual(champion_class(malphite, "UTILITY"), "tank_support")
        self.assertEqual(champion_class(malphite, "TOP"), "tank")
        self.assertEqual(champion_class(soraka), "enchanter")           # unknown position: trust tags

    def test_off_role_support_gets_solo_lane_build(self):
        players = [
            player("me", "Soraka", "ORDER", position="TOP"),
            player("e1", "Zed", "CHAOS"),
        ]
        advice = analyze(game_data(players), DB)
        self.assertEqual(advice.items[0].text_key, "live.build.core.mage")


class BuildTest(unittest.TestCase):
    def test_marksman_core_and_adaptive_armor_boots(self):
        players = [
            player("me", "Caitlyn", "ORDER"),
            player("e1", "Zed", "CHAOS", gold_items=((3142, 3000),)),
            player("e2", "Jinx", "CHAOS", gold_items=((3031, 3400),)),
            player("e3", "Malphite", "CHAOS", gold_items=((3068, 2700),)),
        ]
        advice = analyze(game_data(players), DB)
        self.assertEqual(advice.items[0].text_key, "live.build.core.marksman")
        self.assertEqual(advice.items[0].item_ids, [3031, 3094, 3036])
        self.assertEqual(advice.items[1].text_key, "live.build.boots.armor")  # AD-heavy enemies
        self.assertEqual(advice.items[1].item_ids, [3047])

    def test_mercury_boots_against_cc(self):
        players = [
            player("me", "Jinx", "ORDER"),
            player("e1", "Ahri", "CHAOS", gold_items=((6655, 2900),)),
            player("e2", "Malphite", "CHAOS", gold_items=((3068, 2700),)),
            player("e3", "Soraka", "CHAOS", gold_items=((3065, 2800),)),
        ]
        advice = analyze(game_data(players), DB)
        keys = [(s.text_key, s.item_ids) for s in advice.items]
        self.assertIn(("live.build.boots.mr", [3111]), keys)

    def test_build_comes_before_situational(self):
        advice = analyze(game_data(enemy_set()), DB)
        self.assertEqual(advice.items[0].priority, 0)
        self.assertTrue(advice.items[0].text_key.startswith("live.build.core"))
        self.assertTrue(advice.items[1].text_key.startswith("live.build.boots"))

    def test_no_build_without_champion_data(self):
        advice = analyze(game_data(enemy_set()), {})
        self.assertFalse(any(s.text_key.startswith("live.build") for s in advice.items))


class ProgressionTest(unittest.TestCase):
    def test_owned_core_items_drop_off(self):
        players = [
            player("me", "Caitlyn", "ORDER", gold_items=((3031, 3400),)),  # owns IE
            player("e1", "Zed", "CHAOS"),
        ]
        advice = analyze(game_data(players), DB)
        core = next(s for s in advice.items if s.text_key == "live.build.core.marksman")
        self.assertEqual(core.item_ids, [3094, 3036])  # next core pieces only

    def test_completed_core_disappears(self):
        players = [
            player("me", "Caitlyn", "ORDER", gold_items=((3031, 1), (3094, 1), (3036, 1))),
            player("e1", "Zed", "CHAOS"),
        ]
        advice = analyze(game_data(players), DB)
        self.assertFalse(any(s.text_key.startswith("live.build.core") for s in advice.items))

    def test_owned_boots_silence_boots(self):
        players = [
            player("me", "Caitlyn", "ORDER", gold_items=((3047, 1100),)),
            player("e1", "Zed", "CHAOS"),
        ]
        advice = analyze(game_data(players), DB)
        self.assertFalse(any(s.text_key.startswith("live.build.boots") for s in advice.items))

    def test_upgrade_silences_component(self):
        players = [
            player("me", "Caitlyn", "ORDER", gold_items=((3033, 3000),)),  # Mortal Reminder
            player("e1", "Soraka", "CHAOS", kills=4),
        ]
        advice = analyze(game_data(players), DB)
        antiheal = next(s for s in advice.items if "antiheal" in s.text_key)
        self.assertNotIn(3123, antiheal.item_ids)  # Executioner's covered by its upgrade
        self.assertTrue(antiheal.item_ids)

    def test_lane_phase_hides_composition_items(self):
        players = [
            player("me", "Caitlyn", "ORDER"),
            player("e1", "Zed", "CHAOS", gold_items=((3142, 3000),)),
            player("e2", "Jinx", "CHAOS", gold_items=((3031, 3400),)),
        ]
        early = analyze(game_data(players, game_time=300), DB)
        self.assertNotIn("live.item.armor", {s.text_key for s in early.items})
        mid = analyze(game_data(players, game_time=900), DB)
        self.assertIn("live.item.armor", {s.text_key for s in mid.items})

    def test_full_build_late_game_suggests_elixir(self):
        full = ((3031, 1), (3094, 1), (3036, 1), (3006, 1), (3035, 1), (3026, 1))
        players = [
            player("me", "Caitlyn", "ORDER", gold_items=full),
            player("e1", "Zed", "CHAOS"),
        ]
        advice = analyze(game_data(players, game_time=1500), DB)
        elixir = next((s for s in advice.items if s.text_key == "live.build.elixir"), None)
        self.assertIsNotNone(elixir)
        self.assertEqual(elixir.item_ids, [2140])  # Elixir of Wrath for marksmen


if __name__ == "__main__":
    unittest.main()
