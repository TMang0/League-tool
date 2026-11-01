"""Client for the Live Client Data API: local and free, available only while a game is running."""
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://127.0.0.1:2999/liveclientdata"


class LiveClient:
    def __init__(self):
        self._session = requests.Session()
        self._session.verify = False

    def _get(self, path, timeout=2):
        try:
            response = self._session.get(BASE + path, timeout=timeout)
            if response.status_code != 200:
                return None
            return response.json()
        except (requests.RequestException, ValueError):
            return None

    def all_game_data(self):
        """Single request with players, items, events and game time (keeps polling cheap)."""
        return self._get("/allgamedata")
