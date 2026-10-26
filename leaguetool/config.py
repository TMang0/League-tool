import json
import locale
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from .constants import ROLE_KEYS

CONFIG_VERSION = 2


def _app_dir():
    if sys.platform == "win32":
        return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "LeagueTool"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LeagueTool"
    return Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "LeagueTool"


APP_DIR = _app_dir()
CONFIG_PATH = APP_DIR / "config.json"


def _empty_profile():
    return {"picks": [], "bans": [], "spell1": None, "spell2": None, "rune_preset": None}


def default_config():
    profiles = {role: _empty_profile() for role in ROLE_KEYS}
    profiles["ANY"]["spell1"] = 4
    profiles["ANY"]["spell2"] = 14
    return {
        "version": CONFIG_VERSION,
        "language": "es",
        "active": True,
        "features": {"accept": True, "pick": True, "ban": True, "spells": True, "runes": True},
        "settings": {
            "accept_delay": 1.0,
            "action_delay": 1.0,
            "ban_delay": 10.0,
            "hover_early": True,
            "avoid_ally_bans": True,
            "overwrite_rune_page": True,
            "use_recommended_runes": True,
        },
        "profiles": profiles,
        "rune_presets": {},
    }


def new_preset(name="Nuevo preset"):
    return {
        "name": name,
        "primary": 0,
        "secondary": 0,
        "primary_runes": [0, 0, 0, 0],
        "secondary_runes": [],
        "shards": [0, 0, 0],
        "champions": [],
    }


def preset_is_valid(preset):
    if not preset:
        return False
    primary, secondary = preset.get("primary"), preset.get("secondary")
    if not primary or not secondary or primary == secondary:
        return False
    primary_runes = preset.get("primary_runes", [])
    shards = preset.get("shards", [])
    return (
        len(primary_runes) == 4
        and all(primary_runes)
        and len(preset.get("secondary_runes", [])) == 2
        and len(shards) == 3
        and all(shards)
    )


def _merge(base, loaded):
    for key, value in loaded.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict) and key != "rune_presets":
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def _system_locale():
    try:
        if sys.platform == "win32":
            import ctypes

            buffer = ctypes.create_unicode_buffer(85)
            ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, 85)
            return buffer.value
        if sys.platform == "darwin":
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3
            )
            return result.stdout.replace("(", "").replace('"', "").strip().split(",")[0].strip()
        return os.getenv("LANG", "") or (locale.getlocale()[0] or "")
    except Exception:
        return ""


def _detect_language():
    return "es" if _system_locale().lower().startswith("es") else "en"


class Config:
    def __init__(self, path=CONFIG_PATH):
        self.path = Path(path)
        self.data = default_config()
        self._lock = threading.Lock()

    def load(self):
        loaded_version = 0
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded_version = loaded.get("version", 1)
                _merge(self.data, loaded)
        except (OSError, ValueError):
            loaded_version = CONFIG_VERSION
            self.data["language"] = _detect_language()
        if loaded_version < 2:
            # Version 2 made overwriting a rune page the default; older files only stored the old default.
            self.data["settings"]["overwrite_rune_page"] = True
        self.data["version"] = CONFIG_VERSION
        for role in ROLE_KEYS:
            profile = self.data["profiles"].setdefault(role, _empty_profile())
            for key, value in _empty_profile().items():
                profile.setdefault(key, value)
        return self

    def save(self):
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                pass

    @property
    def features(self):
        return self.data["features"]

    @property
    def settings(self):
        return self.data["settings"]

    @property
    def presets(self):
        return self.data["rune_presets"]

    def profile(self, role):
        return self.data["profiles"].get(role) or self.data["profiles"]["ANY"]

    def add_preset(self, name="Nuevo preset"):
        preset_id = uuid.uuid4().hex[:8]
        self.presets[preset_id] = new_preset(name)
        return preset_id

    def delete_preset(self, preset_id):
        self.presets.pop(preset_id, None)
        for profile in self.data["profiles"].values():
            if profile.get("rune_preset") == preset_id:
                profile["rune_preset"] = None

    # Resolution helpers: the role profile wins, "ANY" is the fallback.
    def effective_list(self, role, key):
        result = []
        for source in (role, "ANY"):
            for champion_id in self.profile(source).get(key, []):
                if champion_id not in result:
                    result.append(champion_id)
        return result

    def effective_spells(self, role):
        for source in (role, "ANY"):
            profile = self.profile(source)
            if profile.get("spell1") and profile.get("spell2"):
                return profile["spell1"], profile["spell2"]
        return None

    def champion_preset(self, champion_id):
        return next(
            (
                p
                for p in self.presets.values()
                if champion_id in p.get("champions", []) and preset_is_valid(p)
            ),
            None,
        )

    def role_preset(self, role):
        for source in (role, "ANY"):
            preset = self.presets.get(self.profile(source).get("rune_preset"))
            if preset_is_valid(preset):
                return preset
        return None

    def effective_preset(self, role, champion_id):
        return self.champion_preset(champion_id) or self.role_preset(role)
