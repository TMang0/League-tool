"""Overlay render test with synthetic advice. Skipped where Tk has no display (CI)."""
import unittest

from leaguetool.liveanalysis import Advice, Suggestion


def _make_app():
    import customtkinter as ctk

    class Cfg:
        def __init__(self):
            self.data = {"overlay": {"enabled": True, "opacity": 0.9, "compact": True,
                                     "x": None, "y": None, "hotkey": ""}}

        def save(self):
            pass

    class Assets:
        def champion_icon(self, _w, _i, _s):
            pass

        def item_icon(self, _w, _i, _s):
            pass

        def item_name(self, item_id):
            return f"Item{item_id}"

    app = ctk.CTk()
    app.withdraw()
    app.cfg = Cfg()
    app.assets = Assets()
    return app


def _sample_advice():
    advice = Advice(game_time=600)
    advice.focus = [Suggestion("focus", "live.focus.fed", {"champion": "Caitlyn"}, 1, icon_ids=[51])]
    advice.objectives = [Suggestion("objective", "live.obj.baron", {}, 4)]
    advice.items = [Suggestion("item", "live.build.core.marksman", {}, 0, [3031, 3094, 3036])]
    return advice


class OverlayTest(unittest.TestCase):
    def setUp(self):
        try:
            self.app = _make_app()
        except Exception as exc:  # no display (CI) -> nothing to test
            self.skipTest(f"Tk no disponible: {exc}")

    def tearDown(self):
        self.app.destroy()

    def test_full_render_cycle(self):
        from leaguetool.gui.overlay import LiveOverlay

        overlay = LiveOverlay(self.app)
        overlay.update(_sample_advice())
        overlay.update_idletasks()
        self.assertIn("focus", overlay._titles)
        overlay._toggle_size()  # expanded
        overlay.update_idletasks()
        overlay._toggle_size()  # back to compact
        overlay.update(None)    # waiting state
        overlay.update(_sample_advice())
        overlay.update_idletasks()
        overlay.hide()
        overlay.destroy()

    def test_empty_sections_are_hidden(self):
        from leaguetool.gui.overlay import LiveOverlay

        overlay = LiveOverlay(self.app)
        advice = Advice(game_time=60)  # no suggestions at all
        overlay.update(advice)
        overlay.update_idletasks()
        for title in overlay._titles.values():
            self.assertFalse(title.winfo_manager())
        overlay.destroy()


if __name__ == "__main__":
    unittest.main()
