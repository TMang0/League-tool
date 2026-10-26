import customtkinter as ctk

from ..config import preset_is_valid
from ..constants import SHARD_ROWS, shard_name
from ..i18n import t
from . import theme
from .theme import font
from .widgets import ChampionStrip


class RunesPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.assets = app.assets
        self.selected_id = None
        self._rune_buttons = []
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        theme.title_label(header, t("runes.title")).pack(anchor="w")
        theme.muted_label(header, t("runes.subtitle")).pack(anchor="w")

        side = theme.card(self, width=240)
        side.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        side.grid_propagate(False)
        theme.gold_button(side, t("runes.new"), self._new_preset).pack(fill="x", padx=14, pady=14)
        self.list_frame = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        self.editor = ctk.CTkScrollableFrame(self, fg_color=theme.CARD, corner_radius=14)
        self.editor.grid(row=1, column=1, sticky="nsew")
        self.assets.on_ready(self.refresh)

    @property
    def presets(self):
        return self.app.cfg.presets

    def refresh(self):
        if self.selected_id not in self.presets:
            self.selected_id = next(iter(self.presets), None)
        self._render_list()
        self._render_editor()

    def _save(self):
        self.app.cfg.save()

    # ---- Preset list -----------------------------------------------
    def _render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        for preset_id, preset in self.presets.items():
            active = preset_id == self.selected_id
            ctk.CTkButton(
                self.list_frame,
                text=("✓  " if preset_is_valid(preset) else "•  ") + preset["name"],
                anchor="w",
                font=font(13, "bold" if active else "normal"),
                fg_color=theme.CARD_ALT if active else "transparent",
                hover_color=theme.CARD_ALT,
                text_color=theme.GOLD if active else theme.TEXT,
                command=lambda pid=preset_id: self._select(pid),
            ).pack(fill="x", pady=2)

    def _deferred(self, *steps):
        # The clicked widget is destroyed by the rebuild; let its click animation finish first.
        def run():
            for step in steps:
                step()

        self.after(120, run)

    def _select(self, preset_id):
        self.selected_id = preset_id
        self._deferred(self._render_list, self._render_editor)

    def _new_preset(self):
        self.selected_id = self.app.cfg.add_preset(t("runes.default_name", n=len(self.presets) + 1))
        self._save()
        self._deferred(self._render_list, self._render_editor)

    def _delete(self):
        self.app.cfg.delete_preset(self.selected_id)
        self._save()
        self._deferred(self.refresh)

    # ---- Editor ----------------------------------------------------
    def _render_editor(self):
        for child in self.editor.winfo_children():
            child.destroy()
        self._rune_buttons = []
        if not self.assets.ready:
            theme.muted_label(self.editor, t("runes.loading"), 14).pack(pady=40)
            return
        if not self.assets.trees:
            theme.muted_label(self.editor, t("runes.unavailable"), 14).pack(pady=40)
            return
        if self.selected_id is None:
            theme.muted_label(self.editor, t("runes.create_first"), 14).pack(pady=40)
            return

        preset = self.presets[self.selected_id]
        top = ctk.CTkFrame(self.editor, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 4))
        self.name_entry = ctk.CTkEntry(
            top, width=260, font=font(15, "bold"), fg_color=theme.BG, border_color=theme.BORDER
        )
        self.name_entry.insert(0, preset["name"])
        self.name_entry.pack(side="left")
        self.name_entry.bind("<KeyRelease>", self._on_name)
        theme.ghost_button(top, t("runes.delete"), self._delete, width=90).pack(side="right")
        self.valid_label = ctk.CTkLabel(top, text="", font=font(12, "bold"), width=230, anchor="e")
        self.valid_label.pack(side="right", padx=14)

        self._section_title(t("runes.primary"))
        self.primary_frame = ctk.CTkFrame(self.editor, fg_color="transparent")
        self.primary_frame.pack(fill="x", padx=18)
        self._section_title(t("runes.secondary"))
        self.secondary_frame = ctk.CTkFrame(self.editor, fg_color="transparent")
        self.secondary_frame.pack(fill="x", padx=18)
        self._section_title(t("runes.shards"))
        self.shards_frame = ctk.CTkFrame(self.editor, fg_color="transparent")
        self.shards_frame.pack(fill="x", padx=18)
        self._section_title(t("runes.champions"))
        strip = ChampionStrip(
            self.editor, self.assets, self._set_champions, t("runes.champions_picker"), per_row=6
        )
        strip.set_ids(preset["champions"])
        strip.pack(fill="x", padx=12, pady=(0, 18))

        self._build_primary()
        self._build_secondary()
        self._build_shards()
        self._update_validity()

    def _section_title(self, text):
        ctk.CTkLabel(self.editor, text=text, font=font(14, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=18, pady=(18, 6)
        )

    def _tree(self, tree_id):
        return next((t for t in self.assets.trees if t["id"] == tree_id), None)

    def _on_name(self, _event):
        name = self.name_entry.get().strip() or t("runes.nameless")
        self.presets[self.selected_id]["name"] = name
        self._save()
        self._render_list()

    def _set_champions(self, ids):
        self.presets[self.selected_id]["champions"] = ids
        self._save()

    def _update_validity(self):
        valid = preset_is_valid(self.presets[self.selected_id])
        self.valid_label.configure(
            text=t("runes.valid") if valid else t("runes.incomplete"),
            text_color=theme.OK if valid else theme.WARN,
        )
        self._render_list()

    def _tree_row(self, parent, selected_id, on_pick, disabled=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", pady=(0, 8))
        for tree in self.assets.trees:
            button = ctk.CTkButton(
                row,
                text="",
                image=None,
                width=48,
                height=48,
                fg_color="transparent",
                hover_color=theme.CARD_ALT,
                border_color=theme.GOLD,
                border_width=2 if tree["id"] == selected_id else 0,
                corner_radius=24,
                state="disabled" if tree["id"] == disabled else "normal",
                command=lambda t=tree["id"]: on_pick(t),
            )
            self.assets.tree_icon(button, tree, 36, dim=tree["id"] != selected_id)
            button.pack(side="left", padx=3)

    def _rune_row(self, parent, runes, size, group, slot):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", pady=3)
        for rune in runes:
            button = ctk.CTkButton(
                row,
                text="",
                image=None,
                width=size + 14,
                height=size + 14,
                fg_color="transparent",
                hover_color=theme.CARD_ALT,
                border_color=theme.GOLD,
                corner_radius=(size + 14) // 2,
                command=lambda r=rune["id"], s=slot, g=group: self._on_rune(g, s, r),
            )
            button.pack(side="left", padx=4)
            self._rune_buttons.append((button, rune, size, group))
        return row

    def _clear(self, frame, group):
        for child in frame.winfo_children():
            child.destroy()
        self._rune_buttons = [b for b in self._rune_buttons if b[3] != group]

    def _build_primary(self):
        preset = self.presets[self.selected_id]
        self._clear(self.primary_frame, "primary")
        self._tree_row(self.primary_frame, preset["primary"], self._set_primary)
        tree = self._tree(preset["primary"])
        if tree:
            for index, slot in enumerate(tree["slots"]):
                self._rune_row(self.primary_frame, slot["runes"], 46 if index == 0 else 36, "primary", index)
        self._update_runes()

    def _build_secondary(self):
        preset = self.presets[self.selected_id]
        self._clear(self.secondary_frame, "secondary")
        self._tree_row(self.secondary_frame, preset["secondary"], self._set_secondary, disabled=preset["primary"])
        tree = self._tree(preset["secondary"])
        if tree:
            for index, slot in enumerate(tree["slots"][1:], start=1):
                self._rune_row(self.secondary_frame, slot["runes"], 36, "secondary", index)
        self._update_runes()

    def _build_shards(self):
        preset = self.presets[self.selected_id]
        for child in self.shards_frame.winfo_children():
            child.destroy()
        for row_index, options in enumerate(SHARD_ROWS):
            row = ctk.CTkFrame(self.shards_frame, fg_color="transparent")
            row.pack(anchor="w", pady=3)
            for shard_id in options:
                name = shard_name(shard_id)
                chosen = preset["shards"][row_index] == shard_id
                ctk.CTkButton(
                    row,
                    text=name,
                    width=116,
                    height=34,
                    font=font(12, "bold" if chosen else "normal"),
                    fg_color=theme.GOLD if chosen else theme.CARD_ALT,
                    hover_color="#dcc184" if chosen else theme.BORDER,
                    text_color="#1a1408" if chosen else theme.TEXT,
                    command=lambda r=row_index, s=shard_id: self._set_shard(r, s),
                ).pack(side="left", padx=4)

    def _update_runes(self):
        preset = self.presets[self.selected_id]
        chosen = set(preset["primary_runes"]) | set(preset["secondary_runes"])
        for button, rune, size, _group in self._rune_buttons:
            selected = rune["id"] in chosen
            button.configure(border_width=2 if selected else 0)
            self.assets.rune_icon(button, rune, size, dim=not selected)

    # ---- Actions ---------------------------------------------------
    def _changed(self):
        self._save()
        self._update_validity()

    def _set_primary(self, tree_id):
        preset = self.presets[self.selected_id]
        if preset["primary"] != tree_id:
            preset["primary"] = tree_id
            preset["primary_runes"] = [0, 0, 0, 0]
            if preset["secondary"] == tree_id:
                preset["secondary"] = 0
                preset["secondary_runes"] = []
        self._deferred(self._build_primary, self._build_secondary)
        self._changed()

    def _set_secondary(self, tree_id):
        preset = self.presets[self.selected_id]
        if preset["secondary"] != tree_id:
            preset["secondary"] = tree_id
            preset["secondary_runes"] = []
        self._deferred(self._build_secondary)
        self._changed()

    def _set_shard(self, row, shard_id):
        self.presets[self.selected_id]["shards"][row] = shard_id
        self._deferred(self._build_shards)
        self._changed()

    def _row_of(self, tree_id, rune_id):
        tree = self._tree(tree_id)
        for index, slot in enumerate(tree["slots"] if tree else []):
            if any(r["id"] == rune_id for r in slot["runes"]):
                return index
        return -1

    def _on_rune(self, group, slot, rune_id):
        preset = self.presets[self.selected_id]
        if group == "primary":
            preset["primary_runes"][slot] = rune_id
        else:
            chosen = preset["secondary_runes"]
            if rune_id in chosen:
                chosen.remove(rune_id)
            else:
                chosen[:] = [r for r in chosen if self._row_of(preset["secondary"], r) != slot]
                chosen.append(rune_id)
                if len(chosen) > 2:
                    chosen.pop(0)
            chosen.sort(key=lambda r: self._row_of(preset["secondary"], r))
        self._update_runes()
        self._changed()
