"""Onboarding modal test. Skipped where Tk has no display (CI)."""
import unittest


class OnboardingTest(unittest.TestCase):
    def setUp(self):
        try:
            import customtkinter as ctk

            class Cfg:
                def __init__(self):
                    self.data = {"onboarding_shown": False}
                    self.saved = False

                def save(self):
                    self.saved = True

            self.app = ctk.CTk()
            self.app.withdraw()
            self.app.cfg = Cfg()
        except Exception as exc:
            self.skipTest(f"Tk no disponible: {exc}")

    def tearDown(self):
        self.app.destroy()

    def test_shows_on_first_run_and_persists_opt_out(self):
        from leaguetool.gui.onboarding import OnboardingModal, maybe_show

        maybe_show(self.app)
        modals = [w for w in self.app.winfo_children() if isinstance(w, OnboardingModal)]
        self.assertEqual(len(modals), 1)

        modal = modals[0]
        modal._dont_show.select()
        modal._close()
        self.assertTrue(self.app.cfg.data["onboarding_shown"])
        self.assertTrue(self.app.cfg.saved)
        maybe_show(self.app)  # opted out: no new modal
        self.assertFalse([w for w in self.app.winfo_children() if isinstance(w, OnboardingModal)])

    def test_close_without_opt_out_keeps_showing(self):
        from leaguetool.gui.onboarding import OnboardingModal, maybe_show

        maybe_show(self.app)
        modal = next(w for w in self.app.winfo_children() if isinstance(w, OnboardingModal))
        modal._close()
        self.assertFalse(self.app.cfg.data["onboarding_shown"])


if __name__ == "__main__":
    unittest.main()
