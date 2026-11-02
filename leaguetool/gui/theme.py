import sys

import customtkinter as ctk

from ..assets import asset_path

BG = "#0a0e13"
SIDEBAR = "#0e141b"
CARD = "#141b24"
CARD_ALT = "#1b2430"
BORDER = "#263241"
GOLD = "#c8aa6e"
GOLD_DARK = "#8a7440"
TEAL = "#0ac8b9"
TEXT = "#ece8dc"
MUTED = "#8793a1"
OK = "#3ddc97"
WARN = "#f0b429"
DANGER = "#e84057"

_FALLBACK_FONT = {"win32": "Segoe UI", "darwin": "Helvetica Neue"}.get(sys.platform, "DejaVu Sans")
FONT = _FALLBACK_FONT
MONO_FONT = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "DejaVu Sans Mono")


def load_private_fonts():
    """Registers the bundled Inter fonts for this process only (Windows GDI).

    On other platforms the font files are not registered; the system fallback is used.
    Safe to call before Tk starts.
    """
    global FONT
    if sys.platform != "win32":
        return
    import ctypes

    FR_PRIVATE = 0x10
    loaded = 0
    for name in ("Inter-Regular.ttf", "Inter-Bold.ttf"):
        path = asset_path(f"fonts/{name}")
        if path and ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0):
            loaded += 1
    if loaded:
        FONT = "Inter"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def title_label(master, text, size=26):
    return ctk.CTkLabel(master, text=text, font=font(size, "bold"), text_color=TEXT)


def muted_label(master, text, size=12, **kwargs):
    return ctk.CTkLabel(master, text=text, font=font(size), text_color=MUTED, **kwargs)


def card(master, **kwargs):
    kwargs.setdefault("fg_color", CARD)
    kwargs.setdefault("corner_radius", 14)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("border_color", BORDER)
    return ctk.CTkFrame(master, **kwargs)


def gold_button(master, text, command, **kwargs):
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        font=font(13, "bold"),
        fg_color=GOLD,
        hover_color="#dcc184",
        text_color="#1a1408",
        corner_radius=10,
        **kwargs,
    )


def ghost_button(master, text, command, **kwargs):
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        font=font(13),
        fg_color=CARD_ALT,
        hover_color=BORDER,
        text_color=TEXT,
        corner_radius=10,
        **kwargs,
    )
