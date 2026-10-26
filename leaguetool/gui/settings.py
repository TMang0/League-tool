import customtkinter as ctk

from ..i18n import LANGUAGES, get_language, t
from . import theme
from .theme import font


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        settings = app.cfg.settings

        theme.title_label(self, t("set.title")).pack(anchor="w")
        theme.muted_label(self, t("set.subtitle")).pack(anchor="w", pady=(0, 14))

        language = theme.card(self)
        language.pack(fill="x", pady=(0, 14))
        row = ctk.CTkFrame(language, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=16)
        ctk.CTkLabel(row, text=t("set.language"), font=font(15, "bold"), text_color=theme.GOLD).pack(side="left")
        self._codes = {name: code for code, name in LANGUAGES.items()}
        selector = ctk.CTkSegmentedButton(
            row,
            values=list(LANGUAGES.values()),
            command=lambda name: app.set_language(self._codes[name]),
            font=font(13, "bold"),
            selected_color=theme.GOLD,
            selected_hover_color="#dcc184",
            unselected_color=theme.CARD_ALT,
            unselected_hover_color=theme.BORDER,
            text_color=theme.TEXT,
            fg_color=theme.CARD_ALT,
        )
        selector.pack(side="right")
        selector.set(LANGUAGES[get_language()])

        timing = theme.card(self)
        timing.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(timing, text=t("set.timing"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        self._slider(timing, t("set.accept_delay"), "accept_delay", 0, 8, settings)
        self._slider(timing, t("set.action_delay"), "action_delay", 0, 15, settings)
        self._slider(timing, t("set.ban_delay"), "ban_delay", 0, 30, settings)
        ctk.CTkFrame(timing, fg_color="transparent", height=10).pack()

        behaviour = theme.card(self)
        behaviour.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(behaviour, text=t("set.behaviour"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        for key in ("hover", "avoid", "recommended", "overwrite"):
            setting = {
                "hover": "hover_early",
                "avoid": "avoid_ally_bans",
                "recommended": "use_recommended_runes",
                "overwrite": "overwrite_rune_page",
            }[key]
            self._switch(behaviour, t(f"set.{key}"), t(f"set.{key}.desc"), setting, settings)
        ctk.CTkFrame(behaviour, fg_color="transparent", height=10).pack()

    def _slider(self, parent, label, key, low, high, settings):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=label, font=font(13), text_color=theme.TEXT).pack(side="left")
        value = ctk.CTkLabel(
            row, text=f"{settings[key]:.1f} s", font=font(13, "bold"), text_color=theme.TEAL, width=50
        )
        value.pack(side="right")

        def changed(raw):
            settings[key] = round(float(raw) * 2) / 2
            value.configure(text=f"{settings[key]:.1f} s")
            self.app.cfg.save()

        slider = ctk.CTkSlider(
            row,
            from_=low,
            to=high,
            number_of_steps=(high - low) * 2,
            width=240,
            progress_color=theme.TEAL,
            button_color=theme.GOLD,
            button_hover_color="#dcc184",
            command=changed,
        )
        slider.set(settings[key])
        slider.pack(side="right", padx=14)

    def _switch(self, parent, label, description, key, settings):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=7)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left")
        ctk.CTkLabel(text, text=label, font=font(14, "bold"), text_color=theme.TEXT).pack(anchor="w")
        theme.muted_label(text, description, 11).pack(anchor="w")

        def changed():
            settings[key] = bool(switch.get())
            self.app.cfg.save()

        switch = ctk.CTkSwitch(row, text="", width=46, progress_color=theme.TEAL, command=changed)
        switch.pack(side="right")
        if settings[key]:
            switch.select()
