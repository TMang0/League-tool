"""Post-game analysis tab: your stats, highlights and the full scoreboard."""
import customtkinter as ctk

from ..i18n import t
from . import theme
from .theme import font

STAT_KEYS = ("kda", "damage", "cs", "vision", "gold", "gold15")


class AnalysisPage(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        theme.title_label(left, t("post.title")).pack(anchor="w")
        theme.muted_label(left, t("post.subtitle")).pack(anchor="w")
        theme.ghost_button(header, t("post.refresh"), app.refresh_postgame).pack(side="right")

        self.status = ctk.CTkLabel(self, text=t("post.waiting"), font=font(13, "bold"), text_color=theme.WARN)
        self.status.pack(anchor="w", pady=(8, 12))

        result = theme.card(self)
        result.pack(fill="x", pady=(0, 14))
        row = ctk.CTkFrame(result, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=14)
        self.icon = ctk.CTkLabel(row, text="", width=48, height=48, fg_color=theme.CARD_ALT, corner_radius=8)
        self.icon.pack(side="left")
        block = ctk.CTkFrame(row, fg_color="transparent")
        block.pack(side="left", padx=14)
        self.result_label = ctk.CTkLabel(block, text="", font=font(20, "bold"), text_color=theme.TEXT, anchor="w")
        self.result_label.pack(fill="x")
        self.result_sub = ctk.CTkLabel(block, text="", font=font(12), text_color=theme.MUTED, anchor="w")
        self.result_sub.pack(fill="x")

        stats = theme.card(self)
        stats.pack(fill="x", pady=(0, 14))
        grid = ctk.CTkFrame(stats, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=14)
        for column in range(len(STAT_KEYS)):
            grid.columnconfigure(column, weight=1, uniform="stat")
        self._stats = {}
        for column, key in enumerate(STAT_KEYS):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=0, column=column)
            value = ctk.CTkLabel(cell, text="—", font=font(17, "bold"), text_color=theme.TEAL)
            value.pack()
            theme.muted_label(cell, t(f"post.stat.{key}"), 10).pack()
            self._stats[key] = value

        highlights = theme.card(self)
        highlights.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(highlights, text=t("post.highlights"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=18, pady=(14, 4)
        )
        self._highlight_labels = []
        for _ in range(8):
            label = ctk.CTkLabel(
                highlights, text="", font=font(12), text_color=theme.TEXT, anchor="w", justify="left",
                wraplength=760,
            )
            label.pack(fill="x", padx=18, pady=2)
            self._highlight_labels.append(label)
        ctk.CTkFrame(highlights, fg_color="transparent", height=10).pack()

        board = theme.card(self)
        board.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(board, text=t("post.scoreboard"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=18, pady=(14, 4)
        )
        self._board_rows = []
        for _ in range(10):
            row = ctk.CTkFrame(board, fg_color="transparent")
            icon = ctk.CTkLabel(row, text="", width=26, height=26, fg_color=theme.CARD_ALT, corner_radius=5)
            icon.pack(side="left")
            name = ctk.CTkLabel(row, text="", font=font(12), text_color=theme.TEXT, anchor="w", width=200)
            name.pack(side="left", padx=10)
            kda = ctk.CTkLabel(row, text="", font=font(12, "bold"), text_color=theme.TEXT, anchor="e", width=90)
            kda.pack(side="right", padx=10)
            damage = ctk.CTkLabel(row, text="", font=font(12), text_color=theme.MUTED, anchor="e", width=90)
            damage.pack(side="right")
            self._board_rows.append((row, icon, name, kda, damage))
        ctk.CTkFrame(board, fg_color="transparent", height=10).pack()

        timeline = theme.card(self)
        timeline.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(timeline, text=t("post.timeline"), font=font(15, "bold"), text_color=theme.GOLD).pack(
            anchor="w", padx=18, pady=(14, 4)
        )
        self._timeline_frame = ctk.CTkFrame(timeline, fg_color="transparent")
        self._timeline_frame.pack(fill="x", padx=18)
        ctk.CTkFrame(timeline, fg_color="transparent", height=10).pack()

    def update(self, status, analysis):
        if status != "ok" or not analysis:
            message = {"loading": "post.loading", "waiting": "post.waiting"}.get(status, f"post.{status}")
            self.status.configure(text=t(message), text_color=theme.WARN)
            return
        self.status.configure(text="")

        win = analysis["win"]
        self.result_label.configure(
            text=t("post.win" if win else "post.loss"),
            text_color=theme.OK if win else theme.DANGER,
        )
        champion = self.app.assets.champion_name(analysis["champion_id"])
        minutes, seconds = divmod(analysis["duration"], 60)
        self.result_sub.configure(
            text=f"{champion} · {minutes}:{seconds:02d} · {analysis['kills']}/{analysis['deaths']}/{analysis['assists']}"
        )
        self.app.assets.champion_icon(self.icon, analysis["champion_id"], 44)

        gold15 = analysis["gold15_diff"]
        values = {
            "kda": f"{analysis['kills']}/{analysis['deaths']}/{analysis['assists']}",
            "damage": f"{analysis['damage']:,} ({analysis['damage_share']}%)",
            "cs": f"{analysis['cs']} ({analysis['csm']}/m)",
            "vision": str(analysis["vision"]),
            "gold": f"{analysis['gold']:,}",
            "gold15": f"{gold15:+,}" if gold15 is not None else "—",
        }
        for key, value in values.items():
            self._stats[key].configure(text=value)

        highlights = analysis["highlights"]
        for index, label in enumerate(self._highlight_labels):
            if index >= len(highlights):
                label.configure(text="")
                continue
            key, params, good = highlights[index]
            label.configure(
                text=f"● {t(key, **self._localize(params))}",
                text_color=theme.OK if good else theme.DANGER,
            )

        for child in self._timeline_frame.winfo_children():
            child.destroy()
        mono = ctk.CTkFont(family=theme.MONO_FONT, size=11)
        for row_data in analysis.get("timeline", []):
            events = []
            died = False
            for kind, params, good in row_data["events"]:
                died = died or kind == "post.ev.death"
                events.append(("▲" if good else "▽") + " " + t(kind, **self._localize(params)))
            text = (
                f"{row_data['minute']:02d}'  {row_data['diff']:+,} oro  ·  CS {row_data['cs']:>3}"
                + ("  ·  " + "  ".join(events) if events else "")
            )
            color = theme.DANGER if died else (theme.OK if row_data["diff"] >= 0 else theme.MUTED)
            ctk.CTkLabel(
                self._timeline_frame, text=text, font=mono, text_color=color, anchor="w"
            ).pack(fill="x", pady=0)

        for (row, icon, name, kda, damage), player in zip(self._board_rows, analysis["players"] + [None] * 10):
            if player is None:
                row.pack_forget()
                continue
            row.pack(fill="x", padx=18, pady=1)
            self.app.assets.champion_icon(icon, player["champion_id"], 22)
            display = player["name"] + (f"  ({t('post.you')})" if player["is_me"] else "")
            name.configure(
                text=f"{display} — {self.app.assets.champion_name(player['champion_id'])}",
                text_color=theme.GOLD if player["is_me"] else (theme.TEXT if player["mine"] else theme.MUTED),
            )
            kda.configure(text=f"{player['kills']}/{player['deaths']}/{player['assists']}")
            damage.configure(text=f"{player['damage']:,}")

    @staticmethod
    def _localize(params):
        """Nested objective names arrive as i18n keys; translate them before formatting."""
        params = dict(params)
        what = params.get("what")
        if isinstance(what, str) and what.startswith("post.obj."):
            params["what"] = t(what)
        return params
