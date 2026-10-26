import customtkinter as ctk

from ..constants import roles, spell_names
from ..i18n import t
from . import theme
from .theme import font
from .widgets import ChampionStrip


class ProfilesPage(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.role = "ANY"
        self._role_by_label = {label: key for key, label in roles()}
        self._spell_by_label = {name: spell_id for spell_id, name in spell_names().items()}
        self._preset_by_label = {}

        theme.title_label(self, t("prof.title")).pack(anchor="w")
        theme.muted_label(self, t("prof.subtitle")).pack(anchor="w", pady=(0, 14))

        self.role_selector = ctk.CTkSegmentedButton(
            self,
            values=[label for _, label in roles()],
            command=self._on_role,
            font=font(13, "bold"),
            selected_color=theme.GOLD,
            selected_hover_color="#dcc184",
            unselected_color=theme.CARD,
            unselected_hover_color=theme.CARD_ALT,
            text_color=theme.TEXT,
            fg_color=theme.CARD,
        )
        self.role_selector.pack(fill="x", pady=(0, 14))
        self.role_selector.set(roles()[0][1])

        self.picks = self._section(t("prof.picks"), "picks", t("prof.picks_picker"))
        self.bans = self._section(t("prof.bans"), "bans", t("prof.bans_picker"))

        extras = theme.card(self)
        extras.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(extras, text=t("prof.extras"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 8)
        )
        grid = ctk.CTkFrame(extras, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=(0, 18))
        self.spell1 = self._menu(grid, t("prof.spell_d"), 0, lambda v: self._set_spell("spell1", v))
        self.spell2 = self._menu(grid, t("prof.spell_f"), 1, lambda v: self._set_spell("spell2", v))
        self.rune_menu = self._menu(grid, t("prof.preset"), 2, self._set_preset, width=240)
        self.refresh()

    def _section(self, title, key, picker_title):
        frame = theme.card(self)
        frame.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(frame, text=title, font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        strip = ChampionStrip(
            frame, self.app.assets, lambda ids, k=key: self._set_list(k, ids), picker_title, per_row=6
        )
        strip.pack(fill="x", padx=14, pady=(0, 14))
        return strip

    def _menu(self, parent, label, column, command, width=170):
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=column, padx=(0, 20), sticky="w")
        theme.muted_label(cell, label).pack(anchor="w")
        menu = ctk.CTkOptionMenu(
            cell,
            values=[t("prof.none")],
            command=command,
            width=width,
            font=font(13),
            fg_color=theme.CARD_ALT,
            button_color=theme.BORDER,
            button_hover_color=theme.GOLD_DARK,
            dropdown_fg_color=theme.CARD_ALT,
        )
        menu.pack(anchor="w", pady=(4, 0))
        return menu

    @property
    def profile(self):
        return self.app.cfg.profile(self.role)

    def _save(self):
        self.app.cfg.save()

    def _set_list(self, key, ids):
        self.profile[key] = ids
        self._save()

    def _set_spell(self, key, label):
        self.profile[key] = self._spell_by_label.get(label)
        self._save()

    def _set_preset(self, label):
        self.profile["rune_preset"] = self._preset_by_label.get(label)
        self._save()

    def _on_role(self, label):
        self.role = self._role_by_label[label]
        self.refresh()

    def refresh(self):
        """Reloads every control from the config (called on show / role change)."""
        profile = self.profile
        self.picks.set_ids(profile["picks"])
        self.bans.set_ids(profile["bans"])

        spells = spell_names()
        empty = t("prof.none") if self.role == "ANY" else t("prof.inherit")
        spell_values = [empty] + list(spells.values())
        for menu, key in ((self.spell1, "spell1"), (self.spell2, "spell2")):
            menu.configure(values=spell_values)
            menu.set(spells.get(profile[key], empty))

        self._preset_by_label = {}
        for preset_id, preset in self.app.cfg.presets.items():
            label = preset["name"]
            while label in self._preset_by_label:
                label += " ·"
            self._preset_by_label[label] = preset_id
        self.rune_menu.configure(values=[empty] + list(self._preset_by_label))
        current = next(
            (label for label, pid in self._preset_by_label.items() if pid == profile["rune_preset"]), empty
        )
        self.rune_menu.set(current)
