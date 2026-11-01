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

        overlay = theme.card(self)
        overlay.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(overlay, text=t("set.overlay_section"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        self._overlay_switch(overlay)
        self._opacity_slider(overlay)
        self._hotkey_row(overlay)
        ctk.CTkFrame(overlay, fg_color="transparent", height=10).pack()

        riot = theme.card(self)
        riot.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(riot, text=t("set.riot_section"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 0)
        )
        theme.muted_label(riot, t("set.riot.desc"), 11).pack(anchor="w", padx=20, pady=(0, 6))
        row = ctk.CTkFrame(riot, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 14))
        entry = ctk.CTkEntry(row, width=280, font=font(12), show="•",
                             placeholder_text=t("set.riot.placeholder"))
        if self.app.cfg.data["riot"]["api_key"]:
            entry.insert(0, self.app.cfg.data["riot"]["api_key"])
        entry.pack(side="left")

        def apply():
            self.app.set_riot_key(entry.get())
            status.configure(
                text=t("set.riot.saved" if self.app.riot.available else "set.riot.missing"),
                text_color=theme.OK if self.app.riot.available else theme.WARN,
            )

        theme.ghost_button(row, t("set.hotkey.apply"), apply, width=70).pack(side="left", padx=10)
        entry.bind("<Return>", lambda _e: apply())
        status = ctk.CTkLabel(
            row,
            text=t("set.riot.ok" if self.app.riot.available else "set.riot.missing"),
            font=font(11),
            text_color=theme.OK if self.app.riot.available else theme.WARN,
        )
        status.pack(side="left")

    def _overlay_switch(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=7)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left")
        ctk.CTkLabel(text, text=t("set.overlay"), font=font(14, "bold"), text_color=theme.TEXT).pack(anchor="w")
        theme.muted_label(text, t("set.overlay.desc"), 11).pack(anchor="w")
        switch = ctk.CTkSwitch(
            row,
            text="",
            width=46,
            progress_color=theme.TEAL,
            command=lambda: self.app.set_overlay_enabled(bool(switch.get())),
        )
        switch.pack(side="right")
        if self.app.cfg.data["overlay"]["enabled"]:
            switch.select()

    def _opacity_slider(self, parent):
        cfg = self.app.cfg.data["overlay"]
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=t("set.opacity"), font=font(13), text_color=theme.TEXT).pack(side="left")
        value = ctk.CTkLabel(
            row, text=f"{int(cfg['opacity'] * 100)}%", font=font(13, "bold"), text_color=theme.TEAL, width=50
        )
        value.pack(side="right")

        def changed(raw):
            cfg["opacity"] = round(float(raw) * 20) / 20
            value.configure(text=f"{int(cfg['opacity'] * 100)}%")
            self.app.cfg.save()
            if self.app.overlay:
                self.app.overlay.attributes("-alpha", cfg["opacity"])

        slider = ctk.CTkSlider(
            row,
            from_=0.4,
            to=1.0,
            number_of_steps=12,
            width=240,
            progress_color=theme.TEAL,
            button_color=theme.GOLD,
            button_hover_color="#dcc184",
            command=changed,
        )
        slider.set(cfg["opacity"])
        slider.pack(side="right", padx=14)

    def _hotkey_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=t("set.hotkey"), font=font(13), text_color=theme.TEXT).pack(side="left")
        warning = ctk.CTkLabel(row, text="", font=font(11), text_color=theme.DANGER)
        warning.pack(side="right", padx=(0, 8))

        def apply():
            combo = entry.get().strip()
            if self.app.set_hotkey(combo):
                entry.delete(0, "end")
                entry.insert(0, self.app.cfg.data["overlay"]["hotkey"])
                warning.configure(text="")
            else:
                warning.configure(text=t("set.hotkey.invalid"))

        button = ctk.CTkButton(
            row,
            text=t("set.hotkey.apply"),
            width=70,
            font=font(12, "bold"),
            fg_color=theme.CARD_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            corner_radius=8,
            command=apply,
        )
        button.pack(side="right", padx=(8, 0))
        entry = ctk.CTkEntry(row, width=150, font=font(12))
        entry.insert(0, self.app.cfg.data["overlay"]["hotkey"])
        entry.bind("<Return>", lambda _e: apply())
        entry.pack(side="right")

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
