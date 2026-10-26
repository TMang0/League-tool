import tempfile
import unittest
from pathlib import Path

from leaguetool import automation, i18n
from leaguetool.automation import Automation
from leaguetool.config import Config, new_preset

automation.CONFIRM_DELAY = 0
i18n.set_language("es")


class FakeLCU:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.complete_bodies = []
        self.connected = True

    def request(self, method, path, json=None, timeout=5):
        # The confirmation body is kept apart so call assertions only depend on method and path.
        if path.endswith("/complete"):
            self.complete_bodies.append(json)
            json = None
        self.calls.append((method, path, json))
        handler = self.routes.get((method, path))
        if handler is None:
            return 404, None
        return handler(json) if callable(handler) else handler

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, json=None):
        return self.request("POST", path, json)

    def put(self, path, json=None):
        return self.request("PUT", path, json)

    def patch(self, path, json=None):
        return self.request("PATCH", path, json)


def make_config():
    cfg = Config(Path(tempfile.mkdtemp()) / "config.json").load()
    cfg.settings["accept_delay"] = 0
    cfg.settings["action_delay"] = 0
    cfg.settings["ban_delay"] = 0
    return cfg


def confirmed(lcu):
    return any(
        c[1].endswith("/complete") or (c[0] == "PATCH" and c[2] and c[2].get("completed")) for c in lcu.calls
    )


def make_engine(cfg, routes):
    logs = []
    lcu = FakeLCU(routes)
    engine = Automation(cfg, lcu, lambda i: f"champ{i}", lambda level, text: logs.append((level, text)))
    return engine, lcu, logs


def session(actions, role="MIDDLE", my_champion=0, ally_champion=0, phase=None, bans=None):
    return {
        "localPlayerCellId": 0,
        "timer": {"phase": phase} if phase else {},
        "bans": {"myTeamBans": bans or [], "theirTeamBans": []},
        "myTeam": [
            {"cellId": 0, "assignedPosition": role, "championId": my_champion},
            {"cellId": 1, "assignedPosition": "TOP", "championId": ally_champion, "championPickIntent": 0},
        ],
        "actions": actions,
    }


def action(action_id, kind, in_progress, completed=False, champion=0, actor=0):
    return {
        "id": action_id,
        "actorCellId": actor,
        "type": kind,
        "isInProgress": in_progress,
        "completed": completed,
        "championId": champion,
    }


class ReadyCheckTests(unittest.TestCase):
    def test_accepts_pending_ready_check(self):
        engine, lcu, _ = make_engine(
            make_config(),
            {
                ("GET", "/lol-gameflow/v1/gameflow-phase"): (200, "ReadyCheck"),
                ("GET", "/lol-matchmaking/v1/ready-check"): (200, {"state": "InProgress", "playerResponse": "None"}),
                ("POST", "/lol-matchmaking/v1/ready-check/accept"): (204, None),
            },
        )
        engine.tick()
        self.assertIn(("POST", "/lol-matchmaking/v1/ready-check/accept", None), lcu.calls)

    def test_does_nothing_when_disabled(self):
        cfg = make_config()
        cfg.features["accept"] = False
        engine, lcu, _ = make_engine(cfg, {("GET", "/lol-gameflow/v1/gameflow-phase"): (200, "ReadyCheck")})
        engine.tick()
        self.assertEqual(len(lcu.calls), 1)


class ChampSelectTests(unittest.TestCase):
    def routes(self, actions, pickable, bannable, **session_kwargs):
        return {
            ("GET", "/lol-gameflow/v1/gameflow-phase"): (200, "ChampSelect"),
            ("GET", "/lol-champ-select/v1/session"): (200, session(actions, **session_kwargs)),
            ("GET", "/lol-champ-select/v1/pickable-champion-ids"): (200, pickable),
            ("GET", "/lol-champ-select/v1/bannable-champion-ids"): (200, bannable),
            ("PATCH", "/lol-champ-select/v1/session/actions/5"): (204, None),
            ("POST", "/lol-champ-select/v1/session/actions/5/complete"): (204, None),
            ("PATCH", "/lol-champ-select/v1/session/my-selection"): (204, None),
        }

    def test_locks_first_available_pick(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10, 20, 30]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "pick", True)]], [20, 30], []))
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 20}), lcu.calls)
        self.assertFalse([c for c in lcu.calls if c[1].endswith("/complete")])
        engine.tick()
        self.assertIn(("POST", "/lol-champ-select/v1/session/actions/5/complete", None), lcu.calls)

    def test_pick_waits_confirm_delay_and_skips_patch_if_already_hovered(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [20]
        routes = self.routes([[action(5, "pick", True, champion=20)]], [20], [], phase="BAN_PICK")
        engine, lcu, logs = make_engine(cfg, routes)
        automation.CONFIRM_DELAY = 5
        try:
            engine.tick()
            engine.tick()
            self.assertFalse([c for c in lcu.calls if "/actions/5" in c[1]])
            engine._selected[5] = (20, engine._selected[5][1] - 5)
            engine.tick()
        finally:
            automation.CONFIRM_DELAY = 0
        self.assertTrue(confirmed(lcu))
        routes[("GET", "/lol-champ-select/v1/session")] = (
            200, session([[action(5, "pick", False, completed=True, champion=20)]], phase="BAN_PICK")
        )
        engine.tick()
        self.assertTrue(any("Pick confirmado" in text for _, text in logs))

    def test_pick_confirmation_falls_back_to_patch_completed(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [20]
        routes = self.routes([[action(5, "pick", True, champion=20)]], [20], [], phase="BAN_PICK")
        routes[("POST", "/lol-champ-select/v1/session/actions/5/complete")] = (400, None)
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        engine.tick()
        self.assertIn(
            ("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 20, "completed": True}), lcu.calls
        )

    def test_role_list_has_priority_over_default(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10]
        cfg.profile("MIDDLE")["picks"] = [99]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "pick", True)]], [10, 99], []))
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 99}), lcu.calls)

    def test_hovers_without_locking_before_turn(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "pick", False)]], [10], []))
        engine.tick()
        engine.tick()
        patches = [c for c in lcu.calls if c[0] == "PATCH" and c[1].endswith("/actions/5")]
        self.assertEqual(len(patches), 1)
        self.assertFalse([c for c in lcu.calls if c[1].endswith("/complete")])

    def test_ban_skips_ally_hover_and_own_picks(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10]
        cfg.profile("ANY")["bans"] = [10, 20, 30]
        routes = self.routes([[action(5, "ban", True)]], [], [10, 20, 30], ally_champion=20)
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 30}), lcu.calls)

    def test_ban_works_when_bannable_list_is_empty(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "ban", True)]], [], [], phase="BAN_PICK"))
        engine.tick()
        engine.tick()
        self.assertIn(("POST", "/lol-champ-select/v1/session/actions/5/complete", None), lcu.calls)

    def test_ban_skips_already_banned_and_explains(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30, 40]
        routes = self.routes([[action(5, "ban", True)]], [], [], phase="BAN_PICK", bans=[30])
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 40}), lcu.calls)

        cfg.profile("ANY")["bans"] = [30]
        engine, lcu, logs = make_engine(cfg, routes)
        engine.tick()
        self.assertTrue(any("champ30 (ya está baneado o elegido)" in text for _, text in logs))

    def test_ban_waits_for_ban_delay(self):
        cfg = make_config()
        cfg.settings["ban_delay"] = 10
        cfg.profile("ANY")["bans"] = [30]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "ban", True)]], [], [30], phase="BAN_PICK"))
        engine.tick()
        self.assertFalse([c for c in lcu.calls if "/actions/" in c[1]])
        engine._turn_seen[5] -= 10
        engine.tick()
        engine.tick()
        self.assertIn(("POST", "/lol-champ-select/v1/session/actions/5/complete", None), lcu.calls)

    def test_ban_still_tried_when_bannable_list_lacks_champion(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "ban", True)]], [], [40], phase="BAN_PICK"))
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 30}), lcu.calls)

    def test_ban_prefers_champions_listed_as_bannable(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30, 40]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "ban", True)]], [], [40], phase="BAN_PICK"))
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 40}), lcu.calls)

    def test_ban_skips_champion_declared_by_ally_in_actions(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30, 40]
        actions = [[action(2, "pick", True, champion=30, actor=1)], [action(5, "ban", True)]]
        engine, lcu, _ = make_engine(cfg, self.routes(actions, [], [30, 40], phase="BAN_PICK"))
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 40}), lcu.calls)

    def test_ban_falls_back_to_next_champion_when_client_rejects(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30, 40]
        routes = self.routes([[action(5, "ban", True)]], [], [], phase="BAN_PICK")
        routes[("PATCH", "/lol-champ-select/v1/session/actions/5")] = (
            lambda body: (400, None) if body["championId"] == 30 else (204, None)
        )
        engine, lcu, _ = make_engine(cfg, routes)
        for _ in range(7):
            engine.tick()
        self.assertIn(("POST", "/lol-champ-select/v1/session/actions/5/complete", None), lcu.calls)

    def test_ban_selects_first_then_confirms_after_delay(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        routes = self.routes([[action(5, "ban", True)]], [], [30], phase="BAN_PICK")
        engine, lcu, logs = make_engine(cfg, routes)
        automation.CONFIRM_DELAY = 5
        try:
            engine.tick()
            engine.tick()
            self.assertEqual(
                [c[:2] for c in lcu.calls if "/actions/5" in c[1]],
                [("PATCH", "/lol-champ-select/v1/session/actions/5")],
            )
            engine._selected[5] = (30, engine._selected[5][1] - 5)
            engine.tick()
        finally:
            automation.CONFIRM_DELAY = 0
        self.assertTrue(confirmed(lcu))
        self.assertEqual(lcu.complete_bodies[0], None)
        self.assertFalse(any("Ban confirmado" in text for _, text in logs))
        routes[("GET", "/lol-champ-select/v1/session")] = (
            200, session([[action(5, "ban", False, completed=True, champion=30)]], phase="BAN_PICK")
        )
        engine.tick()
        self.assertTrue(any("Ban confirmado" in text for _, text in logs))

    def test_confirmation_is_retried_with_other_style_until_client_reports_completed(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        routes = self.routes([[action(5, "ban", True)]], [], [30], phase="BAN_PICK")
        engine, lcu, logs = make_engine(cfg, routes)
        automation.VERIFY_DELAY = 0
        try:
            for _ in range(5):
                engine.tick()
        finally:
            automation.VERIFY_DELAY = 1.5
        styles = [(c[0], c[1].endswith("/complete"), c[2]) for c in lcu.calls if "/actions/5" in c[1]][1:]
        self.assertIn(("PATCH", False, {"championId": 30, "completed": True}), styles)
        self.assertEqual(lcu.complete_bodies, [None, {"championId": 30}, None])

    def test_ban_confirmation_falls_back_to_patch_completed(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        routes = self.routes([[action(5, "ban", True)]], [], [30], phase="BAN_PICK")
        routes[("POST", "/lol-champ-select/v1/session/actions/5/complete")] = (400, None)
        engine, lcu, _ = make_engine(cfg, routes)
        for _ in range(3):
            engine.tick()
        self.assertIn(
            ("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 30, "completed": True}), lcu.calls
        )

    def test_ban_not_repeated_after_success(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        engine, lcu, _ = make_engine(cfg, self.routes([[action(5, "ban", True)]], [], [30]))
        engine.tick()
        engine.tick()
        engine.tick()
        completes = [c for c in lcu.calls if c[1].endswith("/complete")]
        self.assertEqual(len(completes), 1)

    def test_planning_hovers_even_if_pickable_list_is_empty_and_never_locks(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10, 20]
        routes = self.routes([[action(5, "pick", True)]], [], [], phase="PLANNING")
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        engine.tick()
        self.assertEqual(
            [c for c in lcu.calls if c[0] == "PATCH" and c[1].endswith("/actions/5")],
            [("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 10})],
        )
        self.assertFalse([c for c in lcu.calls if c[1].endswith("/complete")])

    def test_planning_skips_banned_champions(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10, 20]
        routes = self.routes([[action(5, "pick", True)]], [], [], phase="PLANNING", bans=[10])
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 20}), lcu.calls)

    def test_no_ban_during_planning_only_on_my_turn(self):
        cfg = make_config()
        cfg.profile("ANY")["bans"] = [30]
        planning = self.routes([[action(5, "ban", True)]], [], [30], phase="PLANNING")
        engine, lcu, _ = make_engine(cfg, planning)
        engine.tick()
        self.assertFalse([c for c in lcu.calls if c[1].endswith("/complete")])

        waiting = self.routes([[action(5, "ban", False)]], [], [30], phase="BAN_PICK")
        engine, lcu, _ = make_engine(cfg, waiting)
        engine.tick()
        self.assertFalse([c for c in lcu.calls if c[1].endswith("/complete")])

        my_turn = self.routes([[action(5, "ban", True)]], [], [30], phase="BAN_PICK")
        engine, lcu, _ = make_engine(cfg, my_turn)
        engine.tick()
        engine.tick()
        self.assertIn(("POST", "/lol-champ-select/v1/session/actions/5/complete", None), lcu.calls)

    def test_pick_phase_skips_champions_taken_or_banned(self):
        cfg = make_config()
        cfg.profile("ANY")["picks"] = [10, 20, 30]
        actions = [[action(9, "pick", True, completed=True, champion=20, actor=3)], [action(5, "pick", True)]]
        routes = self.routes(actions, [], [], phase="BAN_PICK", bans=[10])
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        self.assertIn(("PATCH", "/lol-champ-select/v1/session/actions/5", {"championId": 30}), lcu.calls)

    def test_applies_spells_once(self):
        cfg = make_config()
        engine, lcu, _ = make_engine(cfg, self.routes([], [], []))
        engine.tick()
        engine.tick()
        spells = [c for c in lcu.calls if c[1].endswith("/my-selection")]
        self.assertEqual(spells, [("PATCH", "/lol-champ-select/v1/session/my-selection", {"spell1Id": 4, "spell2Id": 14})])

    def test_updates_existing_rune_page(self):
        cfg = make_config()
        preset = new_preset("Electrocutar")
        preset.update(
            primary=8100, secondary=8000, primary_runes=[8112, 8126, 8138, 8135],
            secondary_runes=[9111, 9104], shards=[5008, 5008, 5011],
        )
        cfg.presets["p1"] = preset
        cfg.profile("ANY")["rune_preset"] = "p1"
        cfg.profile("ANY")["picks"] = [10]
        routes = self.routes([[action(5, "pick", False, completed=True, champion=10)]], [10], [])
        routes[("GET", "/lol-perks/v1/pages")] = (200, [{"id": 7, "name": "LT - Viejo", "isEditable": True}])
        routes[("PUT", "/lol-perks/v1/pages/7")] = (204, None)
        routes[("PUT", "/lol-perks/v1/currentpage")] = (204, None)
        engine, lcu, _ = make_engine(cfg, routes)
        engine.tick()
        engine.tick()
        puts = [c for c in lcu.calls if c[0] == "PUT" and c[1] == "/lol-perks/v1/pages/7"]
        self.assertEqual(len(puts), 1)
        self.assertEqual(puts[0][2]["selectedPerkIds"], [8112, 8126, 8138, 8135, 9111, 9104, 5008, 5008, 5011])
        self.assertIn(("PUT", "/lol-perks/v1/currentpage", 7), lcu.calls)

    def test_creates_rune_page_when_there_is_room(self):
        cfg = make_config()
        preset = new_preset("X")
        preset.update(
            primary=8100, secondary=8000, primary_runes=[1, 2, 3, 4], secondary_runes=[5, 6], shards=[7, 8, 9]
        )
        cfg.presets["p1"] = preset
        cfg.profile("ANY")["rune_preset"] = "p1"
        engine, lcu, _ = make_engine(
            cfg,
            {
                ("GET", "/lol-perks/v1/pages"): (200, [{"id": 1, "name": "Mia", "isEditable": True}]),
                ("GET", "/lol-perks/v1/inventory"): (200, {"ownedPageCount": 3}),
                ("POST", "/lol-perks/v1/pages"): (200, {"id": 42}),
                ("PUT", "/lol-perks/v1/currentpage"): (204, None),
            },
        )
        self.assertTrue(engine.set_rune_page(preset))
        self.assertIn(("PUT", "/lol-perks/v1/currentpage", 42), lcu.calls)

    def test_full_pages_without_overwrite_is_refused(self):
        cfg = make_config()
        cfg.settings["overwrite_rune_page"] = False
        preset = new_preset("X")
        engine, lcu, logs = make_engine(
            cfg,
            {
                ("GET", "/lol-perks/v1/pages"): (200, [{"id": 1, "name": "Mia", "isEditable": True}]),
                ("GET", "/lol-perks/v1/inventory"): (200, {"ownedPageCount": 1}),
            },
        )
        preset.update(primary_runes=[1, 2, 3, 4], secondary_runes=[5, 6], shards=[7, 8, 9])
        self.assertFalse(engine.set_rune_page(preset))
        self.assertFalse([c for c in lcu.calls if c[0] in ("POST", "PUT")])

    def test_full_pages_are_overwritten_by_default(self):
        cfg = make_config()
        preset = new_preset("X")
        engine, lcu, logs = make_engine(
            cfg,
            {
                ("GET", "/lol-perks/v1/pages"): (200, [{"id": 1, "name": "Mia", "isEditable": True}]),
                ("GET", "/lol-perks/v1/inventory"): (200, {"ownedPageCount": 1}),
                ("PUT", "/lol-perks/v1/pages/1"): (204, None),
                ("PUT", "/lol-perks/v1/currentpage"): (204, None),
            },
        )
        preset.update(primary_runes=[1, 2, 3, 4], secondary_runes=[5, 6], shards=[7, 8, 9])
        self.assertTrue(engine.set_rune_page(preset))
        self.assertTrue([c for c in lcu.calls if c[:2] == ("PUT", "/lol-perks/v1/pages/1")])


class RecommendedRunesTests(unittest.TestCase):
    PAGE = {
        "primaryPerkStyleId": 8100,
        "secondaryPerkStyleId": 8000,
        # Shuffled on purpose: the engine must rebuild primary(4) + secondary(2) + shards(3).
        "perks": [
            {"id": 5008, "styleId": 5000}, {"id": 9111, "styleId": 8000}, {"id": 8112, "styleId": 8100},
            {"id": 8126, "styleId": 8100}, {"id": 5011, "styleId": 5000}, {"id": 8138, "styleId": 8100},
            {"id": 9104, "styleId": 8000}, {"id": 8135, "styleId": 8100}, {"id": 5008, "styleId": 5000},
        ],
    }

    def routes(self, recommended=None):
        routes = {
            ("GET", "/lol-gameflow/v1/gameflow-phase"): (200, "ChampSelect"),
            ("GET", "/lol-champ-select/v1/session"): (
                200, session([[action(5, "pick", False, completed=True, champion=10)]], phase="BAN_PICK")
            ),
            ("PATCH", "/lol-champ-select/v1/session/my-selection"): (204, None),
            ("GET", "/lol-perks/v1/pages"): (200, [{"id": 7, "name": "LT - Vieja", "isEditable": True}]),
            ("PUT", "/lol-perks/v1/pages/7"): (204, None),
            ("PUT", "/lol-perks/v1/currentpage"): (204, None),
        }
        if recommended is not None:
            routes[("GET", "/lol-perks/v1/recommended-pages/champion/10/position/middle/map/11")] = recommended
        return routes

    def run_engine(self, cfg, routes):
        engine, lcu, logs = make_engine(cfg, routes)
        engine.tick()
        engine.tick()
        return lcu, logs

    def page_puts(self, lcu):
        return [c for c in lcu.calls if c[0] == "PUT" and c[1] == "/lol-perks/v1/pages/7"]

    def test_applies_clients_recommended_page_reordered(self):
        lcu, logs = self.run_engine(make_config(), self.routes((200, [self.PAGE])))
        puts = self.page_puts(lcu)
        self.assertEqual(len(puts), 1)
        self.assertEqual(puts[0][2]["selectedPerkIds"], [8112, 8126, 8138, 8135, 9111, 9104, 5008, 5011, 5008])
        self.assertEqual((puts[0][2]["primaryStyleId"], puts[0][2]["subStyleId"]), (8100, 8000))
        self.assertIn(("PUT", "/lol-perks/v1/currentpage", 7), lcu.calls)
        self.assertTrue(any("recomendadas del cliente" in text for _, text in logs))

    def test_champion_preset_beats_recommendation(self):
        cfg = make_config()
        preset = new_preset("Mio")
        preset.update(
            primary=8100, secondary=8000, primary_runes=[1, 2, 3, 4], secondary_runes=[5, 6],
            shards=[7, 8, 9], champions=[10],
        )
        cfg.presets["p1"] = preset
        lcu, _ = self.run_engine(cfg, self.routes((200, [self.PAGE])))
        self.assertEqual(self.page_puts(lcu)[0][2]["selectedPerkIds"], [1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_role_preset_is_fallback_when_recommendation_missing_or_disabled(self):
        for disabled in (False, True):
            cfg = make_config()
            cfg.settings["use_recommended_runes"] = not disabled
            preset = new_preset("Rol")
            preset.update(
                primary=8100, secondary=8000, primary_runes=[1, 2, 3, 4], secondary_runes=[5, 6], shards=[7, 8, 9]
            )
            cfg.presets["p1"] = preset
            cfg.profile("ANY")["rune_preset"] = "p1"
            routes = self.routes((200, [self.PAGE]) if disabled else (404, None))
            lcu, _ = self.run_engine(cfg, routes)
            self.assertEqual(self.page_puts(lcu)[0][2]["selectedPerkIds"], [1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_incomplete_recommendation_is_ignored(self):
        broken = dict(self.PAGE, perks=self.PAGE["perks"][:5])
        lcu, logs = self.run_engine(make_config(), self.routes((200, [broken])))
        self.assertFalse(self.page_puts(lcu))
        self.assertTrue(any("No hay runas" in text for _, text in logs))


if __name__ == "__main__":
    unittest.main()
