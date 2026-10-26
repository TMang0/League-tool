"""Background worker that drives the League client: ready check, champ select, spells and runes."""
import threading
import time
from dataclasses import dataclass

from .constants import ROLE_KEYS, RUNE_PAGE_PREFIX
from .i18n import t
from .lcu import ok

MAX_ATTEMPTS = 3
CONFIRM_DELAY = 1.0  # seconds between selecting a champion and pressing the pick/ban button
VERIFY_DELAY = 1.5  # seconds to wait for the client to report the action as completed before retrying


@dataclass
class Status:
    connected: bool = False
    phase: str = "None"
    role: str = ""
    champion_id: int = 0


class Automation(threading.Thread):
    def __init__(self, config, lcu, champion_name, log):
        super().__init__(daemon=True)
        self.config = config
        self.lcu = lcu
        self.champion_name = champion_name
        self.log = log
        self.status = Status()
        self._last_code = None
        self._halt = threading.Event()
        self._accept_at = None
        self._reset_champ_select()

    def stop(self):
        self._halt.set()

    def run(self):
        while not self._halt.is_set():
            try:
                delay = self.tick()
            except Exception as exc:  # keep the worker alive whatever happens
                self.log("error", t("log.unexpected", error=repr(exc)))
                delay = 2
            self._halt.wait(delay)

    def _reset_champ_select(self):
        self._attempts = {}
        self._turn_seen = {}
        self._hovered = {}
        self._selected = {}
        self._confirm_sent = {}
        self._announced = set()
        self._done = set()
        self._warned = set()

    def _try(self, key, limit=MAX_ATTEMPTS):
        """Counts an attempt for `key`; False once the limit is reached."""
        count = self._attempts.get(key, 0)
        if count >= limit:
            return False
        self._attempts[key] = count + 1
        return True

    def _warn_once(self, key, message):
        if key not in self._warned:
            self._warned.add(key)
            self.log("warn", message)

    def tick(self):
        if not self.lcu.connected:
            if not self.lcu.connect():
                self._set_disconnected()
                return 3
            self.log("info", t("log.client_detected"))
        code, phase = self.lcu.get("/lol-gameflow/v1/gameflow-phase")
        if code is None:
            self._set_disconnected()
            return 3
        if not ok(code) or not isinstance(phase, str):
            return 2

        self.status.connected = True
        if phase != self.status.phase:
            self.status.phase = phase
            self._on_phase_change(phase)

        if not self.config.data["active"]:
            return 1
        if phase == "ReadyCheck":
            self._ready_check()
            return 0.5
        if phase == "ChampSelect":
            self._champ_select()
            return 0.5
        return 1

    def _set_disconnected(self):
        if self.status.connected:
            self.log("warn", t("log.connection_lost"))
        self.status = Status()
        self._accept_at = None
        self._reset_champ_select()

    def _on_phase_change(self, phase):
        self._accept_at = None
        self._reset_champ_select()
        self.status.role = ""
        self.status.champion_id = 0
        if phase == "ChampSelect":
            self.log("info", t("log.champ_select_started"))

    # ---- Ready check -------------------------------------------------
    def _ready_check(self):
        if not self.config.features["accept"]:
            return
        code, check = self.lcu.get("/lol-matchmaking/v1/ready-check")
        if not ok(code) or not isinstance(check, dict):
            return
        if check.get("state") != "InProgress" or check.get("playerResponse") != "None":
            return
        now = time.monotonic()
        if self._accept_at is None:
            self._accept_at = now + float(self.config.settings["accept_delay"])
        if now >= self._accept_at:
            code, _ = self.lcu.post("/lol-matchmaking/v1/ready-check/accept")
            if ok(code):
                self.log("ok", t("log.match_accepted"))
            else:
                self.log("warn", t("log.accept_failed", code=code))

    # ---- Champ select ------------------------------------------------
    def _ids(self, path):
        code, data = self.lcu.get(path)
        if ok(code) and isinstance(data, list):
            return {i for i in data if isinstance(i, int)}
        return None

    def _champ_select(self):
        code, session = self.lcu.get("/lol-champ-select/v1/session")
        if not ok(code) or not isinstance(session, dict) or "localPlayerCellId" not in session:
            return
        cell = session["localPlayerCellId"]
        team = session.get("myTeam", [])
        me = next((p for p in team if p.get("cellId") == cell), {})
        role = (me.get("assignedPosition") or "").upper()
        role = role if role in ROLE_KEYS else "ANY"
        self.status.role = role
        # PLANNING is the declaration phase: only hover, never lock or ban.
        planning = (session.get("timer") or {}).get("phase") == "PLANNING"
        all_actions = [a for group in session.get("actions", []) for a in group]
        taken = self._taken(session, all_actions)

        my_actions = [a for a in all_actions if a.get("actorCellId") == cell]
        team_cells = {p.get("cellId") for p in team}
        ally_hovers = {
            a["championId"]
            for a in all_actions
            if a.get("type") == "pick"
            and a.get("championId")
            and a.get("actorCellId") in team_cells
            and a.get("actorCellId") != cell
        }
        features = self.config.features
        for action in my_actions:
            if action.get("completed"):
                self._announce_completed(action)
                continue
            if action.get("type") == "ban" and features["ban"]:
                if action.get("isInProgress") and not planning:
                    self._ban(action, role, team, cell, taken, ally_hovers)
            elif action.get("type") == "pick" and features["pick"]:
                self._pick(action, role, taken, planning)

        champion = self._my_champion(my_actions, me)
        if champion:
            self.status.champion_id = champion
        if features["spells"] and ("spells" not in self._done):
            self._apply_spells(role)
        if features["runes"] and champion and ("runes", champion) not in self._done:
            self._apply_runes(role, champion)

    @staticmethod
    def _my_champion(my_actions, me):
        picks = [a for a in my_actions if a.get("type") == "pick"]
        if picks:
            return next((a["championId"] for a in picks if a.get("completed") and a.get("championId")), 0)
        return me.get("championId") or 0

    def _delay_elapsed(self, action, setting="action_delay"):
        started = self._turn_seen.setdefault(action["id"], time.monotonic())
        return time.monotonic() - started >= float(self.config.settings[setting])

    def _announce_completed(self, action):
        """Logs success only once the client itself reports the action as completed."""
        action_id = action["id"]
        if action_id in self._selected and action_id not in self._announced:
            self._announced.add(action_id)
            kind = "ban" if action.get("type") == "ban" else "pick"
            self.log("ok", t(f"log.confirmed.{kind}", name=self.champion_name(action.get("championId"))))

    @staticmethod
    def _taken(session, all_actions):
        """Champions that can no longer be picked: banned or already locked by someone."""
        taken = set()
        bans = session.get("bans") or {}
        for key in ("myTeamBans", "theirTeamBans"):
            taken.update(c for c in bans.get(key, []) if isinstance(c, int) and c > 0)
        for action in all_actions:
            if action.get("completed") and action.get("championId"):
                taken.add(action["championId"])
        return taken

    def _pick(self, action, role, taken, planning):
        action_id = action["id"]
        wishes = self.config.effective_list(role, "picks")
        if not wishes:
            return
        # The pickable list is often empty before the pick phase, so it only narrows the choice when present.
        pickable = self._ids("/lol-champ-select/v1/pickable-champion-ids") or set()
        candidates = [c for c in wishes if c not in taken and (not pickable or c in pickable)]

        if planning or not action.get("isInProgress"):
            if self.config.settings["hover_early"]:
                self._hover(action, candidates)
            return

        if not candidates:
            self._warn_once(("nopick", action_id), t("log.no_pick_available"))
            return
        if not self._delay_elapsed(action):
            return
        choice = self._next_choice("pick", action_id, candidates)
        if choice is None:
            self._warn_once(("nopick-rejected", action_id), t("log.pick_rejected"))
            return
        self._select_and_confirm(action, choice, "pick")

    def _hover(self, action, candidates):
        """Shows the preferred champion to the team without locking it."""
        action_id = action["id"]
        for champion in candidates:
            if action.get("championId") == champion or self._hovered.get(action_id) == champion:
                return
            if not self._try(("hover", action_id, champion), limit=2):
                continue
            if self._patch_action(action_id, {"championId": champion}):
                self._hovered[action_id] = champion
                self.log("info", t("log.hovered", name=self.champion_name(champion)))
            return

    def _next_choice(self, kind, action_id, candidates):
        """First candidate the client hasn't rejected too often, keeping the one already selected on top."""
        selected = self._selected.get(action_id)
        if selected and selected[0] in candidates:
            candidates = [selected[0]] + [c for c in candidates if c != selected[0]]
        return next(
            (
                c
                for c in candidates
                if self._attempts.get((kind + "-select", action_id, c), 0) < 2
                and self._attempts.get((kind + "-confirm", action_id, c), 0) < 2 * MAX_ATTEMPTS
            ),
            None,
        )

    def _select_and_confirm(self, action, choice, kind):
        """Two steps, like doing it by hand: select the champion, then press the pick/ban button."""
        action_id = action["id"]
        name = self.champion_name(choice)
        selected = self._selected.get(action_id)

        if not selected or selected[0] != choice:
            if action.get("championId") != choice:
                key = (kind + "-select", action_id, choice)
                self._attempts[key] = self._attempts.get(key, 0) + 1
                if not self._patch_action(action_id, {"championId": choice}):
                    self.log("warn", t("log.select_failed", name=name, code=self._last_code))
                    return
            self.log("info", t(f"log.selected.{kind}", name=name))
            self._selected[action_id] = (choice, time.monotonic())
            return

        # Give the selection a moment to register before pressing the button.
        now = time.monotonic()
        if now - selected[1] < CONFIRM_DELAY:
            return
        # A request the client accepts doesn't guarantee the action completed: wait and re-check on later ticks.
        if now - self._confirm_sent.get(action_id, -VERIFY_DELAY) < VERIFY_DELAY:
            return
        key = (kind + "-confirm", action_id, choice)
        attempt = self._attempts.get(key, 0)
        self._attempts[key] = attempt + 1
        self._confirm_sent[action_id] = now
        if self._confirm_action(action_id, choice, attempt):
            self.log("info", t(f"log.confirming.{kind}", name=name, attempt=attempt + 1, code=self._last_code))
        else:
            self.log("warn", t(f"log.confirm_failed.{kind}", name=name, code=self._last_code))

    def _ban(self, action, role, team, cell, taken, ally_hovers):
        action_id = action["id"]
        wishes = self.config.effective_list(role, "bans")
        if not wishes:
            return
        if not self._delay_elapsed(action, "ban_delay"):
            return
        # The bannable list is unreliable (empty at turn start, sometimes missing champions the UI allows),
        # so it only decides the order: listed champions first, the rest are still tried.
        bannable = self._ids("/lol-champ-select/v1/bannable-champion-ids") or set()
        avoid = {c: t("log.skip.own_pick") for c in self.config.effective_list(role, "picks")}
        if self.config.settings["avoid_ally_bans"]:
            for player in team:
                if player.get("cellId") != cell:
                    for c in (player.get("championId"), player.get("championPickIntent")):
                        if c:
                            avoid[c] = t("log.skip.ally")
            for c in ally_hovers:
                avoid[c] = t("log.skip.ally")
        candidates, skipped = [], []
        for champion in wishes:
            if champion in taken:
                reason = t("log.skip.taken")
            elif champion in avoid:
                reason = avoid[champion]
            else:
                candidates.append(champion)
                continue
            skipped.append(f"{self.champion_name(champion)} ({reason})")
        candidates.sort(key=lambda c: bool(bannable) and c not in bannable)
        choice = self._next_choice("ban", action_id, candidates)
        if choice is None:
            skipped += [f"{self.champion_name(c)} ({t('log.skip.rejected')})" for c in candidates]
            self._warn_once(("noban", action_id), t("log.no_ban", details=", ".join(skipped)))
            return
        self._select_and_confirm(action, choice, "ban")

    def _patch_action(self, action_id, body):
        code, _ = self.lcu.patch(f"/lol-champ-select/v1/session/actions/{action_id}", body)
        self._last_code = code
        return ok(code)

    def _confirm_action(self, action_id, champion_id, attempt=0):
        """Presses the pick/ban button. Each retry starts with a different request style the client may accept."""
        path = f"/lol-champ-select/v1/session/actions/{action_id}"

        def post_with_champion():
            return self.lcu.post(path + "/complete", {"championId": champion_id})[0]

        def patch_completed():
            return self.lcu.patch(path, {"championId": champion_id, "completed": True})[0]

        def post_plain():
            return self.lcu.post(path + "/complete")[0]

        # Plain POST is the style confirmed to lock a pick on a real client; the others are fallbacks.
        styles = [post_plain, patch_completed, post_with_champion]
        start = attempt % len(styles)
        for style in styles[start:] + styles[:start]:
            self._last_code = style()
            if ok(self._last_code):
                return True
        return False

    def _apply_spells(self, role):
        spells = self.config.effective_spells(role)
        if not spells or not self._try("spells"):
            return
        code, _ = self.lcu.patch(
            "/lol-champ-select/v1/session/my-selection", {"spell1Id": spells[0], "spell2Id": spells[1]}
        )
        if ok(code):
            self._done.add("spells")
            self.log("ok", t("log.spells_set"))

    def _apply_runes(self, role, champion):
        if not self._try(("runes", champion), limit=2):
            return
        # Order: preset made for this champion, then the client's recommendation, then the role preset.
        preset = self.config.champion_preset(champion)
        if preset and self.set_rune_page(preset):
            self._runes_applied(champion, preset["name"])
            return
        if not preset and self.config.settings["use_recommended_runes"]:
            recommended = self._recommended_runes(role, champion)
            if recommended and self._write_rune_page(t("runes.page_recommended"), *recommended):
                self._runes_applied(champion, t("log.runes_recommended"))
                return
        preset = self.config.role_preset(role)
        if preset and self.set_rune_page(preset):
            self._runes_applied(champion, preset["name"])
        elif not preset:
            self._warn_once(("norunes", champion), t("log.no_runes"))

    def _runes_applied(self, champion, label):
        self._done.add(("runes", champion))
        self.log("ok", t("log.runes_applied", label=label))

    def _map_id(self):
        code, session = self.lcu.get("/lol-gameflow/v1/session")
        map_id = (session.get("map") or {}).get("id") if ok(code) and isinstance(session, dict) else None
        return map_id if isinstance(map_id, int) else 11

    def _recommended_runes(self, role, champion):
        """Reads the page the client itself recommends: (primary style, secondary style, 9 perk ids)."""
        map_id = self._map_id()
        positions = ([role.lower()] if role != "ANY" else []) + ["none"]
        for position in positions:
            code, pages = self.lcu.get(
                f"/lol-perks/v1/recommended-pages/champion/{champion}/position/{position}/map/{map_id}"
            )
            if not ok(code) or not isinstance(pages, list) or not pages:
                continue
            page = pages[0]
            primary, secondary = page.get("primaryPerkStyleId"), page.get("secondaryPerkStyleId")
            perks = [p for p in page.get("perks", []) if isinstance(p, dict) and p.get("id")]
            if not primary or not secondary or len(perks) != 9:
                continue
            main = [p["id"] for p in perks if p.get("styleId") == primary]
            sub = [p["id"] for p in perks if p.get("styleId") == secondary]
            shards = [p["id"] for p in perks if p.get("styleId") not in (primary, secondary)]
            if (len(main), len(sub), len(shards)) == (4, 2, 3):
                return primary, secondary, main + sub + shards
            return primary, secondary, [p["id"] for p in perks]
        return None

    def set_rune_page(self, preset):
        return self._write_rune_page(
            preset["name"],
            preset["primary"],
            preset["secondary"],
            preset["primary_runes"] + preset["secondary_runes"] + preset["shards"],
        )

    def _write_rune_page(self, name, primary, secondary, perk_ids):
        body = {
            "name": (RUNE_PAGE_PREFIX + name)[:25],
            "primaryStyleId": primary,
            "subStyleId": secondary,
            "selectedPerkIds": perk_ids,
            "current": True,
        }
        code, pages = self.lcu.get("/lol-perks/v1/pages")
        if not ok(code) or not isinstance(pages, list):
            return False
        editable = [p for p in pages if p.get("isEditable", True)]
        target = next((p for p in editable if str(p.get("name", "")).startswith(RUNE_PAGE_PREFIX)), None)
        if target is None:
            code, inventory = self.lcu.get("/lol-perks/v1/inventory")
            capacity = inventory.get("ownedPageCount", 0) if ok(code) and isinstance(inventory, dict) else 0
            if len(editable) >= capacity:
                if not (self.config.settings["overwrite_rune_page"] and editable):
                    self._warn_once("pagefull", t("log.page_full"))
                    return False
                target = editable[-1]

        if target is not None:
            page_id = target["id"]
            code, _ = self.lcu.put(f"/lol-perks/v1/pages/{page_id}", body)
        else:
            code, created = self.lcu.post("/lol-perks/v1/pages", body)
            page_id = created.get("id") if isinstance(created, dict) else None
        if not ok(code) or page_id is None:
            self.log("warn", t("log.page_failed", code=code))
            return False
        self.lcu.put("/lol-perks/v1/currentpage", page_id)
        return True
