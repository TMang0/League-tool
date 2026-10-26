import queue
import time

import customtkinter as ctk

from .. import __version__, i18n
from ..assets import Assets
from ..automation import Automation
from ..config import Config
from ..i18n import t
from ..lcu import LCUClient
from . import theme
from .dashboard import DashboardPage
from .profiles import ProfilesPage
from .runes import RunesPage
from .settings import SettingsPage
from .theme import font

NAV_KEYS = ["dashboard", "profiles", "runes", "settings"]


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

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.sidebar = self.content = None
        self.pages = {}
        self._build_ui("dashboard")

        self.assets.load_async()
        self.engine.start()
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
            "settings": SettingsPage(self.content, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        for level, text, stamp in self.log_history:
            self.pages["dashboard"].append_log(level, text, stamp)
        self.assets.on_ready(self._on_assets_ready)
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

    def _poll(self):
        self.assets.pump()
        dashboard = self.pages["dashboard"]
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
        if status.connected:
            self.connection.configure(text=t("app.connected"), text_color=theme.OK)
        else:
            self.connection.configure(text=t("app.waiting"), text_color=theme.WARN)
        self.after(100, self._poll)

    def _close(self):
        self.engine.stop()
        self.assets.shutdown()
        self.cfg.save()
        self.destroy()


def run():
    App().mainloop()
