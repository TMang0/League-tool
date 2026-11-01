import queue
import threading
import time

import customtkinter as ctk

from .. import __version__, assets, i18n
from ..assets import Assets
from ..automation import Automation
from ..config import Config
from ..hotkey import Hotkey
from ..i18n import t
from ..lcu import LCUClient
from ..liveengine import LiveEngine
from ..postgame import PostGame
from ..riotapi import RiotClient, resolve_key
from ..scouting import Scout
from . import theme
from .analysis import AnalysisPage
from .dashboard import DashboardPage
from .live import LivePage
from .overlay import LiveOverlay
from .profiles import ProfilesPage
from .runes import RunesPage
from .settings import SettingsPage
from .theme import font

NAV_KEYS = ["dashboard", "profiles", "runes", "live", "analysis", "settings"]


class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=theme.BG)
        self.title("League Tool")
        self.geometry("1120x760")
        self.minsize(980, 660)

        self.cfg = Config().load()
        i18n.set_language(self.cfg.data["language"])
        self.assets = Assets(i18n.DDRAGON_LOCALES[i18n.get_language()])
        self.lcu = LCUClient()
        self.logs = queue.Queue()
        self.log_history = []
        self.engine = Automation(
            self.cfg, self.lcu, self.assets.champion_name, lambda level, text: self.logs.put((level, text))
        )
        self.live_updates = queue.Queue()
        self.live_engine = LiveEngine(self.engine, self.assets, self.live_updates)
        self.hotkey = Hotkey()
        self.overlay = None
        self.riot = RiotClient(resolve_key(self.cfg.data["riot"]["api_key"]))
        self.scout = Scout(self.riot, self.lcu)
        self._scouted = False
        self.postgame = PostGame(
            self.riot, self.lcu, lambda level, text: self.logs.put((level, text))
        )
        self._postgame_done = False
        self._postgame_fetching = False
        self._analysis_loaded = False

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.sidebar = self.content = None
        self.pages = {}
        self._build_ui("dashboard")

        self.assets.load_async()
        self.engine.start()
        self.live_engine.start()
        self.set_hotkey(self.cfg.data["overlay"].get("hotkey", ""))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)

    # ---- Layout ----------------------------------------------------
    def _build_ui(self, page_key):
        self.assets.reset_listeners()
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=26, pady=22)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.pages = {
            "dashboard": DashboardPage(self.content, self),
            "profiles": ProfilesPage(self.content, self),
            "runes": RunesPage(self.content, self),
            "live": LivePage(self.content, self),
            "analysis": AnalysisPage(self.content, self),
            "settings": SettingsPage(self.content, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        for level, text, stamp in self.log_history:
            self.pages["dashboard"].append_log(level, text, stamp)
        self.assets.on_ready(self._on_assets_ready)
        if self.overlay:
            visible = self.overlay.winfo_viewable()
            self.overlay.destroy()
        else:
            visible = False
        self.overlay = LiveOverlay(self)
        if visible or self.live_engine.in_game:
            self.overlay.show()
        self.show(page_key)

    def _build_sidebar(self):
        self.sidebar = sidebar = ctk.CTkFrame(self, fg_color=theme.SIDEBAR, corner_radius=0, width=224)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(10, weight=1)

        ctk.CTkLabel(sidebar, text="LEAGUE", font=font(26, "bold"), text_color=theme.GOLD).grid(
            row=0, column=0, sticky="w", padx=26, pady=(30, 0)
        )
        ctk.CTkLabel(sidebar, text="T O O L", font=font(13, "bold"), text_color=theme.TEAL).grid(
            row=1, column=0, sticky="w", padx=28, pady=(0, 28)
        )
        self.nav_buttons = {}
        for index, key in enumerate(NAV_KEYS):
            button = ctk.CTkButton(
                sidebar,
                text=t(f"nav.{key}"),
                anchor="w",
                height=42,
                font=font(14, "bold"),
                fg_color="transparent",
                hover_color=theme.CARD_ALT,
                text_color=theme.MUTED,
                corner_radius=10,
                command=lambda k=key: self.show(k),
            )
            button.grid(row=2 + index, column=0, sticky="ew", padx=14, pady=3)
            self.nav_buttons[key] = button

        self.connection = ctk.CTkLabel(sidebar, text=t("app.waiting"), font=font(12, "bold"), text_color=theme.WARN)
        self.connection.grid(row=11, column=0, sticky="w", padx=26, pady=(0, 6))
        ctk.CTkLabel(sidebar, text=f"v{__version__}", font=font(11), text_color=theme.MUTED).grid(
            row=12, column=0, sticky="w", padx=26, pady=(0, 22)
        )

    def show(self, key):
        for name, page in self.pages.items():
            if name != key:
                page.grid_remove()
        page = self.pages[key]
        if key == "profiles":
            page.refresh()
        if key == "analysis" and not self._analysis_loaded:
            self.refresh_postgame()
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = key
        for name, button in self.nav_buttons.items():
            active = name == key
            button.configure(
                fg_color=theme.CARD_ALT if active else "transparent",
                text_color=theme.GOLD if active else theme.MUTED,
            )

    # ---- Language --------------------------------------------------
    def set_language(self, code):
        if code == i18n.get_language():
            return
        i18n.set_language(code)
        self.cfg.data["language"] = code
        self.cfg.save()
        self.assets.set_locale(i18n.DDRAGON_LOCALES[code])
        # The language selector that triggered this is destroyed by the rebuild; let its click finish first.
        self.after(150, self._rebuild)

    def _rebuild(self):
        page_key = self.current_page
        self.sidebar.destroy()
        self.content.destroy()
        self._build_ui(page_key)

    # ---- Runtime ---------------------------------------------------
    def _on_assets_ready(self):
        if not self.assets.champions:
            self.pages["dashboard"].append_log("warn", t("app.no_data"))
        else:
            self.pages["profiles"].refresh()

    # ---- Live overlay -----------------------------------------------
    def set_hotkey(self, combo):
        combo = (combo or "").strip()
        if not combo:
            self.cfg.data["overlay"]["hotkey"] = ""
            self.cfg.save()
            self.hotkey.unregister()
            return True
        if self.hotkey.register(combo, lambda: self.live_updates.put(("toggle", None))):
            self.cfg.data["overlay"]["hotkey"] = combo
            self.cfg.save()
            return True
        return False

    def _run_scout(self):
        status, players = self.scout.scout()
        self.live_updates.put(("scouting", (status, players)))

    def refresh_postgame(self, auto=False):
        """auto=True marks the fetch triggered by a finished game (tab switch on success)."""
        if self._postgame_fetching:
            return
        self._postgame_fetching = True
        self.pages["analysis"].update("loading", None)
        threading.Thread(target=self._run_postgame, args=(auto,), daemon=True).start()

    def _run_postgame(self, auto):
        status, analysis = self.postgame.fetch_latest()
        self.live_updates.put(("postgame", (status, analysis, auto)))

    def set_riot_key(self, key):
        """Stores the user's key; empty falls back to the local .env (developer mode)."""
        self.cfg.data["riot"]["api_key"] = key.strip()
        self.cfg.save()
        self.riot.set_key(resolve_key(key))

    def set_overlay_enabled(self, enabled):
        self.cfg.data["overlay"]["enabled"] = enabled
        self.cfg.save()
        if not enabled and self.overlay:
            self.overlay.hide()
        elif enabled and self.live_engine.in_game and self.overlay:
            self.overlay.show()

    def _poll(self):
        # A broken widget must never kill the poll loop: reschedule first, guard everything.
        self.after(100, self._poll)
        try:
            self._poll_body()
        except Exception as exc:
            try:
                self.pages["dashboard"].append_log("error", t("log.unexpected", error=repr(exc)))
            except Exception:
                pass

    def _poll_body(self):
        self.assets.pump()
        dashboard = self.pages["dashboard"]
        while True:
            try:
                kind, payload = self.live_updates.get_nowait()
            except queue.Empty:
                break
            if kind == "state":
                in_game = payload == "started"
                self.pages["live"].set_in_game(in_game)
                if in_game:
                    self.overlay.show()
                else:
                    self.overlay.hide()
            elif kind == "advice":
                self.pages["live"].update(payload)
                self.overlay.update(payload)
            elif kind == "scouting":
                self.pages["live"].update_scouting(*payload)
            elif kind == "postgame":
                status_pg, analysis_pg, auto = payload
                self._postgame_fetching = False
                self._analysis_loaded = status_pg == "ok"
                self.pages["analysis"].update(status_pg, analysis_pg)
                if auto and status_pg == "ok":
                    self.show("analysis")
                    self.lift()
            elif kind == "toggle":
                self.overlay.toggle()
        while True:
            try:
                level, text = self.logs.get_nowait()
            except queue.Empty:
                break
            stamp = time.strftime("%H:%M:%S")
            self.log_history.append((level, text, stamp))
            del self.log_history[:-300]
            dashboard.append_log(level, text, stamp)
        status = self.engine.status
        dashboard.update_status(status, self.assets.champion_name)
        if status.phase in ("GameStart", "InProgress"):
            if not self._scouted:
                self._scouted = True
                self._analysis_loaded = False
                self.pages["live"].update_scouting("loading", [])
                threading.Thread(target=self._run_scout, daemon=True).start()
        elif status.phase in ("WaitingForStats", "PreEndOfGame", "EndOfGame"):
            if not self._postgame_done:
                self._postgame_done = True
                self.refresh_postgame(auto=True)
        elif status.phase in ("None", "Lobby", "Matchmaking", "ReadyCheck"):
            self._scouted = False
            self._postgame_done = False
        if status.connected:
            self.connection.configure(text=t("app.connected"), text_color=theme.OK)
        else:
            self.connection.configure(text=t("app.waiting"), text_color=theme.WARN)

    def _close(self):
        self.hotkey.unregister()
        self.live_engine.stop()
        self.engine.stop()
        self.assets.shutdown()
        self.cfg.save()
        if self.overlay:
            self.overlay.destroy()
        self.destroy()


def run():
    app = App()
    icon_path = assets.app_icon_path()
    if icon_path:
        from PIL import Image, ImageTk

        icon = ImageTk.PhotoImage(Image.open(icon_path))
        app.iconphoto(True, icon)  # True: future toplevels (the overlay) inherit it
        app._icon_ref = icon  # keep a reference so Tk does not lose the image
    app.mainloop()
