"""Post-game analysis tab: your stats, highlights, scoreboard and minute-by-minute."""
import customtkinter as ctk

from ..i18n import t
from . import theme
from .theme import font

STAT_KEYS = ("kda", "damage", "cs", "vision", "gold", "gold15")


class AnalysisPage(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        theme.title_label(left, t("post.title")).pack(anchor="w")
        theme.muted_label(left, t("post.subtitle")).pack(anchor="w")
        theme.ghost_button(header, t("post.refresh"), app.refresh_postgame).pack(side="right")

        self.status = ctk.CTkLabel(self, text=t("post.waiting"), font=font(13, "bold"), text_color=theme.WARN)
        self.status.grid(row=1, column=0, sticky="w", pady=(6, 10))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure((0, 1), weight=1, uniform="ana")
        self._build_result_card(top)
        self._build_stats_card(top)

        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        mid.columnconfigure((0, 1), weight=1, uniform="ana")
        self._build_highlights_card(mid)
        self._build_scoreboard_card(mid)

        self._build_timeline_card()

    # ---- Cards -----------------------------------------------------
    def _build_result_card(self, parent):
        result = theme.card(parent)
        result.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        row = ctk.CTkFrame(result, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)
        self.icon = ctk.CTkLabel(row, text="", width=44, height=44, fg_color=theme.CARD_ALT, corner_radius=8)
        self.icon.pack(side="left")
        block = ctk.CTkFrame(row, fg_color="transparent")
        block.pack(side="left", padx=12)
        self.result_label = ctk.CTkLabel(block, text="", font=font(18, "bold"), text_color=theme.TEXT, anchor="w")
        self.result_label.pack(fill="x")
        self.result_sub = ctk.CTkLabel(block, text="", font=font(11), text_color=theme.MUTED, anchor="w")
        self.result_sub.pack(fill="x")

    def _build_stats_card(self, parent):
        stats = theme.card(parent)
        stats.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        grid = ctk.CTkFrame(stats, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=14, pady=10)
        for column in range(3):
            grid.columnconfigure(column, weight=1, uniform="stat")
        self._stats = {}
        for index, key in enumerate(STAT_KEYS):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=index // 3, column=index % 3, pady=2)
            value = ctk.CTkLabel(cell, text="—", font=font(13, "bold"), text_color=theme.TEAL)
            value.pack()
            theme.muted_label(cell, t(f"post.stat.{key}"), 9).pack()
            self._stats[key] = value

    def _build_highlights_card(self, parent):
        highlights = theme.card(parent)
        highlights.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(highlights, text=t("post.highlights"), font=font(13, "bold"),
                     text_color=theme.GOLD).pack(anchor="w", padx=14, pady=(10, 2))
        self._highlight_labels = []
        for _ in range(8):
            label = ctk.CTkLabel(
                highlights, text="", font=font(11), text_color=theme.TEXT, anchor="w", justify="left",
                wraplength=370,
            )
            label.pack(fill="x", padx=14, pady=0)
            self._highlight_labels.append(label)
        ctk.CTkFrame(highlights, fg_color="transparent", height=8).pack()

    def _build_scoreboard_card(self, parent):
        board = theme.card(parent)
        board.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(board, text=t("post.scoreboard"), font=font(13, "bold"),
                     text_color=theme.GOLD).pack(anchor="w", padx=14, pady=(10, 2))
        self._board_rows = []
        for _ in range(10):
            row = ctk.CTkFrame(board, fg_color="transparent")
            icon = ctk.CTkLabel(row, text="", width=22, height=22, fg_color=theme.CARD_ALT, corner_radius=5)
            icon.pack(side="left")
            name = ctk.CTkLabel(row, text="", font=font(11), text_color=theme.TEXT, anchor="w", width=150)
            name.pack(side="left", padx=8)
            kda = ctk.CTkLabel(row, text="", font=font(11, "bold"), text_color=theme.TEXT, anchor="e", width=70)
            kda.pack(side="right", padx=6)
            damage = ctk.CTkLabel(row, text="", font=font(11), text_color=theme.MUTED, anchor="e", width=70)
            damage.pack(side="right")
            self._board_rows.append((row, icon, name, kda, damage))
        ctk.CTkFrame(board, fg_color="transparent", height=8).pack()

    def _build_timeline_card(self):
        timeline = theme.card(self)
        timeline.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        header = ctk.CTkFrame(timeline, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(header, text=t("post.timeline"), font=font(13, "bold"),
                     text_color=theme.GOLD).pack(side="left")
        self._timeline_open = False
        self._timeline_button = ctk.CTkButton(
            header, text="▸", width=28, height=22, font=font(13, "bold"),
            fg_color="transparent", hover_color=theme.BORDER, text_color=theme.MUTED,
            command=self._toggle_timeline,
        )
        self._timeline_button.pack(side="right")
        self._timeline_preview = ctk.CTkLabel(
            timeline, text="", font=ctk.CTkFont(family=theme.MONO_FONT, size=11),
            text_color=theme.MUTED, anchor="w",
        )
        self._timeline_preview.pack(fill="x", padx=14, pady=(0, 8))
        self._timeline_content = ctk.CTkFrame(timeline, fg_color="transparent")
        theme.muted_label(
            self._timeline_content, t("post.timeline.legend"), 10
        ).pack(anchor="w", padx=4, pady=(0, 4))
        self._timeline_frame = ctk.CTkFrame(self._timeline_content, fg_color="transparent")
        self._timeline_frame.pack(fill="x")
        ctk.CTkFrame(self._timeline_content, fg_color="transparent", height=8).pack()

    def _toggle_timeline(self):
        self._timeline_open = not self._timeline_open
        if self._timeline_open:
            self._timeline_preview.pack_forget()
            self._timeline_content.pack(fill="x", padx=10, pady=(0, 4))
            self._timeline_button.configure(text="▾")
        else:
            self._timeline_content.pack_forget()
            self._timeline_preview.pack(fill="x", padx=14, pady=(0, 8))
            self._timeline_button.configure(text="▸")

    # ---- Content ---------------------------------------------------
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
        self.app.assets.champion_icon(self.icon, analysis["champion_id"], 40)

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
        rows_data = analysis.get("timeline", [])
        self._timeline_preview.configure(text=self._timeline_summary(rows_data))
        mono = ctk.CTkFont(family=theme.MONO_FONT, size=11)
        for row_data in rows_data:
            events = []
            died = False
            for kind, params, good in row_data["events"]:
                died = died or kind == "post.ev.death"
                events.append(("▲" if good else "▽") + " " + t(kind, **self._localize(params)))
            kills, deaths, assists = row_data.get("kda", (0, 0, 0))
            text = (
                f"{row_data['minute']:02d}'  {row_data['diff']:>+7,}  ·  "
                f"{row_data.get('gold', 0) / 1000:4.1f}k  ·  Nv {row_data.get('level', 1):>2}  ·  "
                f"CS {row_data['cs']:>3}  ·  {kills}/{deaths}/{assists}"
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
            row.pack(fill="x", padx=14, pady=0)
            self.app.assets.champion_icon(icon, player["champion_id"], 18)
            display = player["name"] + (f"  ({t('post.you')})" if player["is_me"] else "")
            name.configure(
                text=f"{display} — {self.app.assets.champion_name(player['champion_id'])}",
                text_color=theme.GOLD if player["is_me"] else (theme.TEXT if player["mine"] else theme.MUTED),
            )
            kda.configure(text=f"{player['kills']}/{player['deaths']}/{player['assists']}")
            damage.configure(text=f"{player['damage']:,}")

    @staticmethod
    def _timeline_summary(rows):
        """One-line preview while collapsed: gold curve samples + final KDA + objectives."""
        if not rows:
            return ""
        samples = [rows[m] for m in (10, 20, 30, len(rows) - 1) if m < len(rows)]
        seen, curve = set(), []
        for row in samples:
            if row["minute"] not in seen:
                seen.add(row["minute"])
                label = t("post.timeline.end") if row is rows[-1] else f"{row['minute']}'"
                curve.append(f"{label} {row['diff']:+,}")
        kills, deaths, assists = rows[-1].get("kda", (0, 0, 0))
        won = lost = 0
        for row in rows:
            for kind, _params, good in row["events"]:
                if kind == "post.ev.objective":
                    won, lost = won + good, lost + (not good)
        return (
            "  →  ".join(curve)
            + f"   ·   ⚔ {kills}  💀 {deaths}   ·   ▲ {won} ▽ {lost} {t('post.timeline.objs')}"
        )

    @staticmethod
    def _localize(params):
        """Nested objective names arrive as i18n keys; translate them before formatting."""
        params = dict(params)
        what = params.get("what")
        if isinstance(what, str) and what.startswith("post.obj."):
            params["what"] = t(what)
        return params
