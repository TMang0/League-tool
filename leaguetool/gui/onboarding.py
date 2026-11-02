"""First-run welcome modal: how to get a Riot API key + demo disclaimer."""
import webbrowser

import customtkinter as ctk

from ..i18n import t
from . import theme
from .theme import font

DEV_PORTAL = "https://developer.riotgames.com/"


class OnboardingModal(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app, fg_color=theme.BG)
        self.app = app
        self.title(t("onboard.title"))
        self.resizable(False, False)
        self.transient(app)
        self.protocol("WM_DELETE_WINDOW", self._close)

        card = theme.card(self)
        card.pack(padx=20, pady=20)
        theme.title_label(card, t("onboard.title"), 18).pack(anchor="w", padx=20, pady=(18, 4))
        theme.muted_label(card, t("onboard.intro"), 12).pack(anchor="w", padx=20, pady=(0, 10))

        steps = ctk.CTkFrame(card, fg_color="transparent")
        steps.pack(fill="x", padx=20)
        for index, key in enumerate(("onboard.s1", "onboard.s2", "onboard.s3"), start=1):
            row = ctk.CTkFrame(steps, fg_color="transparent")
            row.pack(fill="x", pady=5)
            badge = ctk.CTkLabel(
                row, text=str(index), width=26, height=26, corner_radius=13,
                fg_color=theme.CARD_ALT, text_color=theme.GOLD, font=font(12, "bold"),
            )
            badge.pack(side="left")
            text = t(key)
            if key == "onboard.s1":
                text = f"{text}  ({DEV_PORTAL})"
            label = ctk.CTkLabel(
                row, text=text, font=font(12), text_color=theme.TEXT,
                anchor="w", justify="left", wraplength=430,
            )
            label.pack(side="left", padx=10, fill="x", expand=True)
            if key == "onboard.s1":
                label.configure(cursor="hand2", text_color=theme.TEAL)
                label.bind("<Button-1>", lambda _e: webbrowser.open(DEV_PORTAL))

        note = ctk.CTkLabel(
            card, text=t("onboard.note"), font=font(11), text_color=theme.WARN,
            anchor="w", justify="left", wraplength=470,
        )
        note.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(
            card, text=t("onboard.demo"), font=font(11), text_color=theme.DANGER, anchor="w"
        ).pack(fill="x", padx=20, pady=(6, 0))

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(16, 18))
        self._dont_show = ctk.CTkCheckBox(
            footer, text=t("onboard.dont_show"), font=font(11),
            text_color=theme.MUTED, checkbox_width=18, checkbox_height=18,
            fg_color=theme.TEAL,
        )
        self._dont_show.pack(side="left")
        theme.gold_button(footer, t("onboard.done"), self._close, width=110).pack(side="right")

        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_reqwidth()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()

    def _close(self):
        if self._dont_show.get():
            self.app.cfg.data["onboarding_shown"] = True
            self.app.cfg.save()
        self.destroy()


def maybe_show(app):
    """Shows the modal on first run (unless the user opted out)."""
    if not app.cfg.data.get("onboarding_shown"):
        OnboardingModal(app)
