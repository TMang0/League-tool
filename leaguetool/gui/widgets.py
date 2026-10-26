import customtkinter as ctk

from ..i18n import t
from . import theme
from .theme import font


class ChampionPicker(ctk.CTkToplevel):
    """Searchable champion grid. Clicking toggles a champion; changes are reported immediately."""

    COLUMNS = 9
    BATCH = 40

    def __init__(self, master, assets, selected, on_change, title=None):
        super().__init__(master)
        title = title or t("widget.pick_champs")
        self.assets = assets
        self.selected = list(selected)
        self.on_change = on_change
        self.title(title)
        self.geometry("860x660")
        self.minsize(640, 480)
        self.configure(fg_color=theme.BG)
        self.transient(master.winfo_toplevel())

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(header, text=title, font=font(18, "bold"), text_color=theme.TEXT).pack(side="left")
        theme.gold_button(header, t("widget.done"), self.destroy, width=80).pack(side="right")
        self.search = ctk.CTkEntry(
            header,
            placeholder_text=t("widget.search"),
            width=240,
            fg_color=theme.CARD,
            border_color=theme.BORDER,
            font=font(13),
        )
        self.search.pack(side="right", padx=12)
        self.search.bind("<KeyRelease>", lambda _e: self._layout())

        self.grid_frame = ctk.CTkScrollableFrame(self, fg_color=theme.CARD, corner_radius=12)
        self.grid_frame.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        self.buttons = {}
        self._queue = assets.sorted_champions()
        self._next = 0
        self.after(10, self._build_batch)
        self.after(150, self.focus_force)

    def _build_batch(self):
        if not self.winfo_exists():
            return
        for champion in self._queue[self._next : self._next + self.BATCH]:
            button = ctk.CTkButton(
                self.grid_frame,
                text=champion["name"][:10],
                image=None,
                compound="top",
                width=84,
                height=84,
                font=font(10),
                fg_color="transparent",
                hover_color=theme.CARD_ALT,
                text_color=theme.TEXT,
                corner_radius=10,
                border_color=theme.GOLD,
                command=lambda cid=champion["id"]: self._toggle(cid),
            )
            self.assets.champion_icon(button, champion["id"], 48)
            self.buttons[champion["id"]] = button
        self._next += self.BATCH
        self._layout()
        if self._next < len(self._queue):
            self.after(15, self._build_batch)

    def _layout(self):
        query = self.search.get().strip().casefold()
        for button in self.buttons.values():
            button.grid_forget()
        column = row = 0
        for champion in self._queue:
            button = self.buttons.get(champion["id"])
            if button is None or (query and query not in champion["name"].casefold()):
                continue
            button.configure(border_width=2 if champion["id"] in self.selected else 0)
            button.grid(row=row, column=column, padx=3, pady=3)
            column += 1
            if column == self.COLUMNS:
                column, row = 0, row + 1

    def _toggle(self, champion_id):
        if champion_id in self.selected:
            self.selected.remove(champion_id)
        else:
            self.selected.append(champion_id)
        self.buttons[champion_id].configure(border_width=2 if champion_id in self.selected else 0)
        self.on_change(list(self.selected))


class ChampionStrip(ctk.CTkFrame):
    """Ordered list of champions with reorder / remove controls and an 'add' button."""

    def __init__(self, master, assets, on_change, picker_title=None, per_row=6, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.assets = assets
        self.on_change = on_change
        self.picker_title = picker_title
        self.per_row = per_row
        self.ids = []
        self._picker = None
        self.render()

    def set_ids(self, ids):
        self.ids = list(ids)
        self.render()

    def _changed(self):
        self.render_later()
        self.on_change(list(self.ids))

    def render_later(self):
        # Chip buttons destroy themselves on click; let the click animation finish first.
        self.after(120, lambda: self.winfo_exists() and self.render())

    def _move(self, index, delta):
        target = index + delta
        if 0 <= target < len(self.ids):
            self.ids[index], self.ids[target] = self.ids[target], self.ids[index]
            self._changed()

    def _remove(self, index):
        del self.ids[index]
        self._changed()

    def _open_picker(self):
        if self._picker is not None and self._picker.winfo_exists():
            self._picker.focus_force()
            return

        def picked(ids):
            self.ids = ids
            self.render_later()
            self.on_change(list(ids))

        self._picker = ChampionPicker(
            self.winfo_toplevel(), self.assets, self.ids, picked, self.picker_title
        )

    def render(self):
        for child in self.winfo_children():
            child.destroy()
        for index, champion_id in enumerate(self.ids):
            chip = ctk.CTkFrame(self, fg_color=theme.CARD_ALT, corner_radius=12, width=104)
            chip.grid(row=index // self.per_row, column=index % self.per_row, padx=4, pady=4)
            badge = ctk.CTkLabel(
                chip, text=str(index + 1), font=font(11, "bold"), text_color=theme.GOLD, width=16
            )
            badge.grid(row=0, column=0, sticky="nw", padx=(8, 0), pady=(4, 0))
            icon = ctk.CTkLabel(chip, text="", width=48, height=48, image=None)
            icon.grid(row=0, column=0, columnspan=3, pady=(6, 2))
            self.assets.champion_icon(icon, champion_id, 48)
            ctk.CTkLabel(
                chip,
                text=self.assets.champion_name(champion_id)[:12],
                font=font(11),
                text_color=theme.TEXT,
            ).grid(row=1, column=0, columnspan=3, padx=6)
            for col, (symbol, action) in enumerate(
                (("‹", lambda i=index: self._move(i, -1)), ("✕", lambda i=index: self._remove(i)),
                 ("›", lambda i=index: self._move(i, 1)))
            ):
                ctk.CTkButton(
                    chip,
                    text=symbol,
                    width=28,
                    height=22,
                    font=font(12, "bold"),
                    fg_color="transparent",
                    hover_color=theme.DANGER if symbol == "✕" else theme.BORDER,
                    text_color=theme.MUTED,
                    command=action,
                ).grid(row=2, column=col, padx=1, pady=(0, 6))
        position = len(self.ids)
        add = ctk.CTkButton(
            self,
            text=t("widget.add"),
            width=104,
            height=106,
            font=font(13, "bold"),
            fg_color="transparent",
            border_width=2,
            border_color=theme.GOLD_DARK,
            hover_color=theme.CARD_ALT,
            text_color=theme.GOLD,
            corner_radius=12,
            command=self._open_picker,
        )
        add.grid(row=position // self.per_row, column=position % self.per_row, padx=4, pady=4)
