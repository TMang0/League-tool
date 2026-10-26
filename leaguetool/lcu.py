"""Minimal client for the League Client Update (LCU) local API."""
import base64
import re
import string
from pathlib import Path

import psutil
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CLIENT_PROCESSES = ("leagueclientux.exe", "leagueclientux")
LOCKFILE_CANDIDATES = [
    *(Path(f"{drive}:\\Riot Games\\League of Legends\\lockfile") for drive in string.ascii_uppercase[2:8]),
    Path("/Applications/League of Legends.app/Contents/LoL/lockfile"),
]


def _from_process():
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            if (proc.info["name"] or "").lower() not in CLIENT_PROCESSES:
                continue
            cmdline = " ".join(proc.info["cmdline"] or [])
        except (psutil.Error, OSError):
            continue
        port = re.search(r"--app-port=(\d+)", cmdline)
        token = re.search(r"--remoting-auth-token=([\w-]+)", cmdline) or re.search(
            r"--remote-auth-token=([\w-]+)", cmdline
        )
        if port and token:
            return int(port.group(1)), token.group(1)
    return None


def _from_lockfile():
    for path in LOCKFILE_CANDIDATES:
        try:
            parts = path.read_text().split(":")
            return int(parts[2]), parts[3]
        except (OSError, ValueError, IndexError):
            continue
    return None


def find_credentials():
    return _from_process() or _from_lockfile()


class LCUClient:
    def __init__(self):
        self._session = None
        self._base = None

    @property
    def connected(self):
        return self._session is not None

    def connect(self):
        creds = find_credentials()
        if not creds:
            self.disconnect()
            return False
        port, token = creds
        session = requests.Session()
        session.verify = False
        auth = base64.b64encode(f"riot:{token}".encode()).decode()
        session.headers.update({"Authorization": f"Basic {auth}", "Accept": "application/json"})
        self._session, self._base = session, f"https://127.0.0.1:{port}"
        return True

    def disconnect(self):
        if self._session:
            self._session.close()
        self._session = self._base = None

    def request(self, method, path, json=None, timeout=5):
        """Returns (status_code, body). status_code is None if the client is unreachable."""
        if not self._session:
            return None, None
        try:
            response = self._session.request(method, self._base + path, json=json, timeout=timeout)
        except requests.ConnectionError:
            self.disconnect()
            return None, None
        except requests.RequestException:
            return None, None
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, response.text

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, json=None):
        return self.request("POST", path, json)

    def put(self, path, json=None):
        return self.request("PUT", path, json)

    def patch(self, path, json=None):
        return self.request("PATCH", path, json)

    def delete(self, path):
        return self.request("DELETE", path)


def ok(status):
    return status is not None and 200 <= status < 300
