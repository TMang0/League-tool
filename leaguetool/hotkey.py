"""Global hotkey on Windows via RegisterHotKey (no extra dependencies). No-op elsewhere."""
import sys
import threading

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1

_MODS = {"ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "alt": 0x0001, "win": 0x0008}
_SPECIAL = {
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}


def parse(combo):
    """'ctrl+shift+l' -> (modifiers, virtual key), or None if the combo is not usable."""
    mods = 0
    key = None
    for part in (combo or "").lower().split("+"):
        part = part.strip()
        if part in _MODS:
            mods |= _MODS[part]
        elif part:
            key = part
    if not key:
        return None
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in _SPECIAL:
        vk = _SPECIAL[key]
    else:
        return None
    return mods, vk


class Hotkey:
    def __init__(self):
        self._thread = None
        self._tid = None

    @property
    def supported(self):
        return sys.platform == "win32"

    def register(self, combo, callback):
        """Returns True if the hotkey was registered. The callback runs on the hotkey thread."""
        self.unregister()
        parsed = parse(combo)
        if not self.supported or not parsed:
            return False
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        mods, vk = parsed
        ready = threading.Event()
        result = []

        def loop():
            self._tid = kernel32.GetCurrentThreadId()
            if not user32.RegisterHotKey(None, HOTKEY_ID, mods | MOD_NOREPEAT, vk):
                result.append(False)
                ready.set()
                return
            result.append(True)
            ready.set()
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    callback()
            user32.UnregisterHotKey(None, HOTKEY_ID)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        ready.wait(2)
        return bool(result and result[0])

    def unregister(self):
        if self._tid:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread = self._tid = None
