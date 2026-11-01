"""Analysis page render test with a real-shaped analysis dict. Skipped without display."""
import unittest


def _make_app():
    import customtkinter as ctk

    class Cfg:
        data = {"overlay": {"enabled": True, "opacity": 0.9, "compact": True, "x": None, "y": None}}

        def save(self):
            pass

    class Assets:
        def champion_icon(self, _w, _i, _s):
            pass

        def champion_name(self, champion_id):
            return f"Champ{champion_id}"

    app = ctk.CTk()
    app.withdraw()
    app.cfg = Cfg()
    app.assets = Assets()
    app.refresh_postgame = lambda: None
    return app


def _analysis(highlights=2, players=10):
    return {
        "win": False, "duration": 1920, "champion_id": 14,
        "kills": 2, "deaths": 6, "assists": 2, "damage": 18000, "damage_share": 22,
        "cs": 210, "csm": 6.6, "vision": 24, "gold": 11500, "gold15_diff": -4339,
        "highlights": [("post.hi.loss", {}, False)] * highlights,
        "timeline": [
            {"minute": m, "diff": m * 100 - 1000, "cs": m * 6,
             "events": [("post.ev.death", {}, False)] if m == 5 else
                       ([("post.ev.objective", {"what": "post.obj.DRAGON"}, True)] if m == 8 else [])}
            for m in range(20)
        ],
        "players": [
            {"name": f"P{i}", "champion_id": 100 + i, "mine": i < 5, "is_me": i == 0,
             "kills": i, "deaths": 10 - i, "assists": 3, "damage": 10000 + i}
            for i in range(players)
        ],
    }


class AnalysisPageTest(unittest.TestCase):
    def setUp(self):
        try:
            self.app = _make_app()
        except Exception as exc:
            self.skipTest(f"Tk no disponible: {exc}")

    def tearDown(self):
        self.app.destroy()

    def test_renders_with_few_highlights(self):
        from leaguetool.gui.analysis import AnalysisPage

        page = AnalysisPage(self.app, self.app)
        page.update("ok", _analysis(highlights=2))  # fewer highlights than labels: must not crash
        page.update_idletasks()
        self.assertEqual(page._board_rows[0][2].cget("text")[:3], "P0 ")
        page.destroy()

    def test_renders_with_more_highlights_and_partial_scoreboard(self):
        from leaguetool.gui.analysis import AnalysisPage

        page = AnalysisPage(self.app, self.app)
        page.update("ok", _analysis(highlights=6, players=10))
        page.update("unavailable", None)  # error states must not crash either
        page.destroy()


if __name__ == "__main__":
    unittest.main()
