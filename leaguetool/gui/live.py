"""In-app mirror of the overlay: live advice while a game is running."""
import customtkinter as ctk

from ..i18n import t
from . import theme
from .theme import font
from .overlay import SECTIONS


class LivePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        theme.title_label(self, t("live.title")).pack(anchor="w")
        theme.muted_label(self, t("live.subtitle")).pack(anchor="w", pady=(0, 12))
        self.status = ctk.CTkLabel(self, text=t("live.waiting"), font=font(13, "bold"), text_color=theme.WARN)
        self.status.pack(anchor="w", pady=(0, 12))

        rivals = theme.card(self)
        rivals.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(rivals, text=t("live.rivals"), font=font(15, "bold"), text_color=theme.DANGER).pack(
            anchor="w", padx=18, pady=(14, 4)
        )
        self.scout_status = ctk.CTkLabel(
            rivals, text="", font=font(11), text_color=theme.MUTED, anchor="w"
        )
        self.scout_status.pack(fill="x", padx=18)
        self._rival_rows = []
        for _ in range(5):
            row = ctk.CTkFrame(rivals, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=3)
            icon = ctk.CTkLabel(row, text="", width=32, height=32, fg_color=theme.CARD_ALT, corner_radius=6)
            icon.pack(side="left")
            lines = ctk.CTkFrame(row, fg_color="transparent")
            lines.pack(side="left", padx=10, fill="x", expand=True)
            main = ctk.CTkLabel(lines, text="", font=font(13, "bold"), text_color=theme.TEXT, anchor="w")
            main.pack(fill="x")
            sub = ctk.CTkLabel(lines, text="", font=font(11), text_color=theme.MUTED, anchor="w")
            sub.pack(fill="x")
            self._rival_rows.append((row, icon, main, sub))
        ctk.CTkFrame(rivals, fg_color="transparent", height=10).pack()

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True)
        for column in range(3):
            columns.columnconfigure(column, weight=1, uniform="live")

        self._rows = {}
        for column, (key, color, count) in enumerate(SECTIONS):
            card = theme.card(columns)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0 if column == 2 else 8))
            ctk.CTkLabel(card, text=t(f"overlay.{key}"), font=font(15, "bold"), text_color=color).pack(
                anchor="w", padx=18, pady=(16, 6)
            )
            labels = []
            for _ in range(count):
                label = ctk.CTkLabel(
                    card, text="—", font=font(13), text_color=theme.TEXT, anchor="w", justify="left",
                    wraplength=230,
                )
                label.pack(fill="x", padx=18, pady=4)
                labels.append(label)
            ctk.CTkFrame(card, fg_color="transparent", height=12).pack()
            self._rows[key] = labels

        theme.muted_label(self, t("live.hint"), 11).pack(anchor="w", pady=(14, 0))

    def update_scouting(self, status, players):
        if status != "ok":
            self.scout_status.configure(text=t(f"live.scout.{status}"))
            players = []
        else:
            self.scout_status.configure(text="")
        for (row, icon, main, sub), player in zip(self._rival_rows, players + [None] * 5):
            if player is None:
                row.pack_forget()
                continue
            row.pack(fill="x", padx=18, pady=3)
            riot_id = player.get("riot_id") or t("live.scout.unknown")
            champion = self.app.assets.champion_name(player.get("champion_id", 0))
            main.configure(text=f"{riot_id}  ·  {champion}")
            self.app.assets.champion_icon(icon, player.get("champion_id", 0), 28)
            if player.get("tier"):
                rank = f"{player['tier']} {player['rank']} · {player['lp']} LP"
                if player.get("winrate") is not None:
                    rank += f" · {player['winrate']}% WR"
            else:
                rank = t("live.scout.unranked")
            mastery = t(
                "live.scout.mastery",
                level=player.get("mastery_level", 0),
                points=f"{player.get('mastery_points', 0):,}".replace(",", " "),
            )
            sub.configure(text=f"{rank}  ·  {mastery}")

    def set_in_game(self, in_game):
        text, color = (t("live.active"), theme.OK) if in_game else (t("live.waiting"), theme.WARN)
        self.status.configure(text=text, text_color=color)
        if not in_game:
            for labels in self._rows.values():
                for label in labels:
                    label.configure(text="—")

    def update(self, advice):
        self.set_in_game(True)
        groups = {"focus": advice.focus, "objectives": advice.objectives, "items": advice.items}
        for key, labels in self._rows.items():
            suggestions = groups[key]
            for index, label in enumerate(labels):
                if index >= len(suggestions):
                    label.configure(text="—")
                    continue
                suggestion = suggestions[index]
                text = t(suggestion.text_key, **suggestion.params)
                if suggestion.item_ids:
                    names = ", ".join(self.app.assets.item_name(i) for i in suggestion.item_ids)
                    text = f"{text}\n→ {names}"
                label.configure(text=text)
