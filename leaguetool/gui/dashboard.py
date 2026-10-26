import time

import customtkinter as ctk

from ..constants import phase_name, role_name
from ..i18n import t
from . import theme
from .theme import font

FEATURE_KEYS = ["accept", "pick", "ban", "spells", "runes"]


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        theme.title_label(left, t("dash.title")).pack(anchor="w")
        theme.muted_label(left, t("dash.subtitle")).pack(anchor="w")
        self.master_switch = ctk.CTkSwitch(
            header,
            text=t("dash.master"),
            font=font(14, "bold"),
            progress_color=theme.TEAL,
            command=self._toggle_master,
        )
        self.master_switch.pack(side="right")
        if app.cfg.data["active"]:
            self.master_switch.select()

        features = theme.card(self)
        features.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(features, text=t("dash.features"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        self.switches = {}
        for key in FEATURE_KEYS:
            row = ctk.CTkFrame(features, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=7)
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left")
            ctk.CTkLabel(text, text=t(f"feature.{key}"), font=font(14, "bold"), text_color=theme.TEXT).pack(
                anchor="w"
            )
            theme.muted_label(text, t(f"feature.{key}.desc"), 11).pack(anchor="w")
            switch = ctk.CTkSwitch(
                row, text="", width=46, progress_color=theme.TEAL, command=lambda k=key: self._toggle(k)
            )
            switch.pack(side="right")
            if app.cfg.features[key]:
                switch.select()
            self.switches[key] = switch
        ctk.CTkFrame(features, fg_color="transparent", height=8).pack()

        status = theme.card(self)
        status.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(status, text=t("dash.status"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 8)
        )
        self.values = {}
        for key in ("client", "phase", "role", "champion"):
            row = ctk.CTkFrame(status, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=6)
            theme.muted_label(row, t(f"dash.{key}"), 12).pack(side="left")
            value = ctk.CTkLabel(row, text="—", font=font(13, "bold"), text_color=theme.TEXT)
            value.pack(side="right")
            self.values[key] = value

        log_card = theme.card(self)
        log_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        ctk.CTkLabel(log_card, text=t("dash.log"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(14, 6)
        )
        self.log_box = ctk.CTkTextbox(
            log_card,
            fg_color=theme.BG,
            font=ctk.CTkFont(family=theme.MONO_FONT, size=12),
            wrap="word",
            corner_radius=10,
            height=140,
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for level, color in (("info", theme.MUTED), ("ok", theme.OK), ("warn", theme.WARN), ("error", theme.DANGER)):
            self.log_box.tag_config(level, foreground=color)
        self.log_box.configure(state="disabled")

    def _toggle_master(self):
        self.app.cfg.data["active"] = bool(self.master_switch.get())
        self.app.cfg.save()

    def _toggle(self, key):
        self.app.cfg.features[key] = bool(self.switches[key].get())
        self.app.cfg.save()

    def append_log(self, level, text, stamp=None):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{stamp or time.strftime('%H:%M:%S')}] {text}\n", level)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def update_status(self, status, champion_name):
        client, color = (
            (t("dash.connected"), theme.OK) if status.connected else (t("dash.waiting"), theme.WARN)
        )
        self.values["client"].configure(text=client, text_color=color)
        self.values["phase"].configure(text=phase_name(status.phase))
        self.values["role"].configure(text=role_name(status.role) if status.role else "—")
        self.values["champion"].configure(text=champion_name(status.champion_id) if status.champion_id else "—")
