"""Always-on-top overlay with live advice. Compact (icons, key info) and expanded (full text)."""
import customtkinter as ctk

from ..i18n import t
from . import theme
from .theme import font

SECTIONS = (("focus", theme.DANGER, 3), ("objectives", theme.TEAL, 3), ("items", theme.GOLD, 6))
ICONS_PER_ROW = 3
ICON_SIZE = 22
WIDTHS = {True: 250, False: 310}  # compact / expanded


class LiveOverlay(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app, fg_color=theme.BG)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self._last_advice = None

        header = ctk.CTkFrame(self, fg_color=theme.CARD_ALT, corner_radius=0, height=30)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = ctk.CTkLabel(header, text=t("overlay.title"), font=font(12, "bold"), text_color=theme.GOLD)
        title.pack(side="left", padx=10)
        close = self._header_button(header, "✕", self.hide)
        close.pack(side="right", padx=(2, 4))
        self._size_button = self._header_button(header, "", self._toggle_size)
        self._size_button.pack(side="right")
        for widget in (header, title):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_end)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        body.columnconfigure(0, weight=1)
        self._rows = {}   # section -> [(row_frame, [icon labels], text label)]
        self._titles = {}
        row_index = 0
        for key, color, count in SECTIONS:
            title_label = ctk.CTkLabel(
                body, text=t(f"overlay.{key}"), font=font(11, "bold"), text_color=color, anchor="w"
            )
            title_label.grid(row=row_index, column=0, sticky="ew", pady=(5, 0))
            row_index += 1
            rows = []
            for _ in range(count):
                row = ctk.CTkFrame(body, fg_color="transparent")
                row.grid(row=row_index, column=0, sticky="ew", pady=1)
                row_index += 1
                icons = []
                for _ in range(ICONS_PER_ROW):
                    icon = ctk.CTkLabel(
                        row, text="", width=ICON_SIZE, height=ICON_SIZE,
                        fg_color=theme.CARD_ALT, corner_radius=5,
                    )
                    icons.append(icon)
                text = ctk.CTkLabel(row, text="", font=font(12), text_color=theme.TEXT,
                                    anchor="w", justify="left")
                rows.append((row, icons, text))
            self._rows[key] = rows
            self._titles[key] = title_label
        self._waiting = ctk.CTkLabel(
            body, text=t("live.waiting"), font=font(11), text_color=theme.MUTED,
            anchor="w", wraplength=WIDTHS[True] - 30,
        )
        self._waiting.grid(row=row_index, column=0, sticky="ew", pady=(6, 0))

        self.apply_settings()
        self.withdraw()

    def _header_button(self, master, text, command):
        return ctk.CTkButton(
            master, text=text, width=26, height=22, font=font(11, "bold"),
            fg_color="transparent", hover_color=theme.BORDER, text_color=theme.MUTED,
            command=command,
        )

    # ---- Behavior --------------------------------------------------
    @property
    def _compact(self):
        return bool(self.app.cfg.data["overlay"].get("compact", True))

    def _toggle_size(self):
        self.app.cfg.data["overlay"]["compact"] = not self._compact
        self.app.cfg.save()
        self.apply_settings()
        self.update(self._last_advice)

    def apply_settings(self):
        cfg = self.app.cfg.data["overlay"]
        self.attributes("-alpha", float(cfg.get("opacity", 0.92)))
        if cfg.get("x") is None or cfg.get("y") is None:
            x, y = self.winfo_screenwidth() - 340, 60
        else:
            x, y = int(cfg["x"]), int(cfg["y"])
        self.geometry(f"{WIDTHS[self._compact]}x320+{x}+{y}")
        self._size_button.configure(text="＋" if self._compact else "－")

    def show(self):
        if not self.app.cfg.data["overlay"]["enabled"]:
            return
        self.deiconify()
        self.lift()

    def hide(self):
        self.withdraw()

    def toggle(self):
        if self.winfo_viewable():
            self.hide()
        else:
            self.show()

    def _drag_start(self, event):
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event):
        offset = getattr(self, "_drag_offset", (0, 0))
        self.geometry(f"+{event.x_root - offset[0]}+{event.y_root - offset[1]}")

    def _drag_end(self, _event):
        cfg = self.app.cfg.data["overlay"]
        cfg["x"], cfg["y"] = self.winfo_x(), self.winfo_y()
        self.app.cfg.save()

    # ---- Content ---------------------------------------------------
    def update(self, advice):
        self._last_advice = advice
        if advice is None:
            self._waiting.grid()
            for key, rows in self._rows.items():
                self._titles[key].grid_remove()
                for row, _icons, _text in rows:
                    row.grid_remove()
            self._fit_height()
            return
        self._waiting.grid_remove()
        groups = {"focus": advice.focus, "objectives": advice.objectives, "items": advice.items}
        for key, rows in self._rows.items():
            suggestions = groups[key]
            if not suggestions:
                self._titles[key].grid_remove()
                for row, _icons, _text in rows:
                    row.grid_remove()
                continue
            self._titles[key].grid()
            for index, (row, icons, text) in enumerate(rows):
                if index >= len(suggestions):
                    row.grid_remove()
                    continue
                self._fill_row(key, suggestions[index], icons, text)
                row.grid()
        self._fit_height()

    def _fill_row(self, section, suggestion, icons, text):
        compact = self._compact
        icon_ids = suggestion.icon_ids if section == "focus" else (
            suggestion.item_ids if section == "items" else []
        )
        for index, icon in enumerate(icons):
            if index < len(icon_ids):
                icon.pack(side="left", padx=(0, 2))
                if section == "focus":
                    self.app.assets.champion_icon(icon, icon_ids[index], ICON_SIZE)
                else:
                    self.app.assets.item_icon(icon, icon_ids[index], ICON_SIZE)
            else:
                icon.pack_forget()

        wrap = (WIDTHS[compact] - 30) - ICONS_PER_ROW * (ICON_SIZE + 2)
        if compact:
            if section == "focus":
                content = suggestion.params.get("champion", t(suggestion.text_key, **suggestion.params))
            elif section == "objectives":
                content = t(suggestion.text_key, **suggestion.params)
            else:
                content = ""
        else:
            content = t(suggestion.text_key, **suggestion.params)
            if suggestion.item_ids:
                names = ", ".join(self.app.assets.item_name(i) for i in suggestion.item_ids)
                content = f"{content}\n→ {names}" if content else names
        if content:
            text.pack(side="left", fill="x", expand=True, padx=(4, 0))
            text.configure(text=content, wraplength=max(wrap, 120), font=font(11 if compact else 12))
        else:
            text.pack_forget()

    def _fit_height(self):
        self.update_idletasks()
        height = max(self.winfo_reqheight(), 70)
        self.geometry(f"{WIDTHS[self._compact]}x{height}+{self.winfo_x()}+{self.winfo_y()}")
