"""Data Dragon data (champions, runes) and cached icons."""
import io
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
import requests
from PIL import Image, ImageEnhance, ImageOps

from .config import APP_DIR

DDRAGON = "https://ddragon.leagueoflegends.com"
CACHE_DIR = APP_DIR / "cache"


class Assets:
    def __init__(self, locale="es_MX"):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.locale = locale
        self.version = None
        self.champions = {}  # id -> {"id": int, "key": str, "name": str}
        self.trees = []  # runesReforged
        self.perks = {}  # perk id -> perk dict
        self.ready = False
        self._images = {}
        self._pending = queue.Queue()
        self._pool = ThreadPoolExecutor(max_workers=6)
        self._listeners = []

    # ---- Data ------------------------------------------------------
    def on_ready(self, callback):
        self._listeners.append(callback)
        if self.ready:
            callback()

    def reset_listeners(self):
        self._listeners.clear()

    def set_locale(self, locale):
        if locale != self.locale:
            self.locale = locale
            self.load_async()

    def load_async(self):
        threading.Thread(target=self._load, args=(self.locale,), daemon=True).start()

    def _fetch_json(self, url, cache_name):
        path = CACHE_DIR / cache_name
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (requests.RequestException, ValueError, OSError):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None

    def _load(self, locale):
        versions = self._fetch_json(f"{DDRAGON}/api/versions.json", "versions.json")
        if not versions:
            self._pending.put(("ready", None))
            return
        self.version = versions[0]
        champions = self._fetch_json(
            f"{DDRAGON}/cdn/{self.version}/data/{locale}/champion.json", f"champions_{locale}.json"
        )
        runes = self._fetch_json(
            f"{DDRAGON}/cdn/{self.version}/data/{locale}/runesReforged.json", f"runes_{locale}.json"
        )
        if champions:
            self.champions = {
                int(c["key"]): {"id": int(c["key"]), "key": c["id"], "name": c["name"]}
                for c in champions["data"].values()
            }
        if runes:
            self.trees = runes
            self.perks = {
                rune["id"]: rune
                for tree in runes
                for slot in tree["slots"]
                for rune in slot["runes"]
            }
        self._pending.put(("ready", None))

    def champion_name(self, champion_id):
        champion = self.champions.get(champion_id)
        return champion["name"] if champion else f"#{champion_id}"

    def sorted_champions(self):
        return sorted(self.champions.values(), key=lambda c: c["name"].casefold())

    # ---- Images ----------------------------------------------------
    def champion_icon(self, widget, champion_id, size):
        champion = self.champions.get(champion_id)
        if champion and self.version:
            url = f"{DDRAGON}/cdn/{self.version}/img/champion/{champion['key']}.png"
            self._bind(widget, url, f"champ_{self.version}_{champion['key']}.png", size)

    def tree_icon(self, widget, tree, size, dim=False):
        self._bind(widget, f"{DDRAGON}/cdn/img/{tree['icon']}", f"tree_{tree['id']}.png", size, dim)

    def rune_icon(self, widget, rune, size, dim=False):
        self._bind(widget, f"{DDRAGON}/cdn/img/{rune['icon']}", f"rune_{rune['id']}.png", size, dim)

    def _bind(self, widget, url, filename, size, dim=False):
        key = (filename, size, dim)
        widget._lt_image_key = key  # late downloads of a stale variant are ignored
        image = self._images.get(key)
        if image:
            widget.configure(image=image)
            return
        self._pool.submit(self._download, widget, url, filename, size, dim, key)

    def _download(self, widget, url, filename, size, dim, key):
        path = CACHE_DIR / filename
        try:
            if path.exists():
                raw = path.read_bytes()
            else:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                raw = response.content
                path.write_bytes(raw)
            pil = Image.open(io.BytesIO(raw)).convert("RGBA")
        except (requests.RequestException, OSError, ValueError):
            return
        if dim:
            alpha = pil.getchannel("A")
            gray = ImageOps.grayscale(pil.convert("RGB"))
            gray = ImageEnhance.Brightness(gray).enhance(0.55).convert("RGBA")
            gray.putalpha(alpha.point(lambda a: int(a * 0.8)))
            pil = gray
        self._pending.put(("image", (widget, key, pil)))

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)

    def pump(self):
        """Runs on the Tk thread: turns downloaded images into widgets' images."""
        while True:
            try:
                kind, payload = self._pending.get_nowait()
            except queue.Empty:
                return
            if kind == "ready":
                self.ready = True
                for callback in list(self._listeners):
                    callback()
                continue
            widget, key, pil = payload
            image = self._images.get(key)
            if image is None:
                image = ctk.CTkImage(light_image=pil, dark_image=pil, size=(key[1], key[1]))
                self._images[key] = image
            if getattr(widget, "_lt_image_key", key) != key:
                continue
            try:
                widget.configure(image=image)
            except Exception:  # widget destroyed meanwhile
                pass
