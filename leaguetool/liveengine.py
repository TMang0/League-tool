"""Background worker: watches for a running game and produces live advice."""
import threading

from .liveanalysis import analyze, build_champion_db
from .liveclient import LiveClient


class LiveEngine(threading.Thread):
    """Polls the Live Client Data API while a game runs and pushes advice to a queue.

    Messages: ("state", "started"|"ended") and ("advice", Advice).
    """

    def __init__(self, automation, assets, updates, interval=2.5):
        super().__init__(daemon=True)
        self.automation = automation
        self.assets = assets
        self.updates = updates
        self.interval = interval
        self.client = LiveClient()
        self.in_game = False
        self._halt = threading.Event()
        self._champion_db = {}
        self._db_version = None
        self._signature = None

    def stop(self):
        self._halt.set()

    def run(self):
        while not self._halt.is_set():
            try:
                delay = self.tick()
            except Exception:
                delay = 3
            self._halt.wait(delay)

    def tick(self):
        if self.automation.status.phase != "InProgress":
            if self.in_game:
                self.in_game = False
                self._signature = None
                self.updates.put(("state", "ended"))
            return 2
        data = self.client.all_game_data()
        if not isinstance(data, dict) or not data.get("allPlayers"):
            return 2  # loading screen or reconnect window
        if self._db_version != self.assets.version:
            self._champion_db = build_champion_db(self.assets.champions)
            self._db_version = self.assets.version
        advice = analyze(data, self._champion_db)
        signature = self._signature_of(advice)
        if not self.in_game:
            self.in_game = True
            self._signature = signature
            self.updates.put(("state", "started"))
            self.updates.put(("advice", advice))
        elif signature != self._signature:
            self._signature = signature
            self.updates.put(("advice", advice))
        return self.interval

    @staticmethod
    def _signature_of(advice):
        """What the UI shows; game time is ignored so the overlay only redraws on real changes."""

        def sig(suggestions):
            return tuple((s.text_key, tuple(sorted(s.params.items())), tuple(s.item_ids)) for s in suggestions)

        return sig(advice.focus), sig(advice.objectives), sig(advice.items)
