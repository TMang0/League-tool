"""Post-game analysis: fetches your last match (Match-V5) and extracts insights."""
import time

from .i18n import t
from .lcu import ok
from .scouting import client_context

MATCH_RETRIES = 4
MATCH_RETRY_DELAY = 10  # Riot takes a few seconds to publish a finished game
GOLD_AT_MINUTE = 15


MONSTER_KEYS = {
    "DRAGON": "post.obj.DRAGON", "BARON_NASHOR": "post.obj.BARON_NASHOR",
    "RIFTHERALD": "post.obj.RIFTHERALD", "HORDE": "post.obj.HORDE",
    "ATAKHAN": "post.obj.ATAKHAN",
}
BUILDING_KEYS = {"TOWER_BUILDING": "post.obj.TOWER_BUILDING", "INHIB_BUILDING": "post.obj.INHIB_BUILDING"}
SWING_THRESHOLD = 1500
DEATH_OBJECTIVE_WINDOW = 2  # minutes after a death to blame it for a lost objective


def analyze_timeline(timeline, my_team_id, my_pid):
    """Per-minute rows (gold diff, my CS, key events) + 'what went wrong/right' insights."""
    info = timeline.get("info") or {}
    frames = info.get("frames") or []
    if not frames or not my_pid:
        return [], []
    their_team = 200 if my_team_id == 100 else 100

    rows = []
    my_cs = []
    my_deaths = []
    kills = deaths = assists = 0
    lost_objectives = []  # (minute, name key)
    for minute, frame in enumerate(frames):
        pf = frame.get("participantFrames") or {}
        gold = {100: 0, 200: 0}
        for pid, data in pf.items():
            gold[100 if int(pid) <= 5 else 200] += data.get("totalGold", 0)
        diff = gold[my_team_id] - gold[their_team]
        me = pf.get(str(my_pid)) or {}
        cs = me.get("minionsKilled", 0) + me.get("jungleMinionsKilled", 0)
        my_cs.append(cs)

        events = []
        for event in frame.get("events") or []:
            etype = event.get("type")
            if etype == "CHAMPION_KILL":
                if event.get("victimId") == my_pid:
                    deaths += 1
                    events.append(("post.ev.death", {}, False))
                    my_deaths.append(minute)
                else:
                    if event.get("killerId") == my_pid:
                        kills += 1
                    if my_pid in (event.get("assistingParticipantIds") or []):
                        assists += 1
                    if event.get("killerId") == my_pid or my_pid in (
                        event.get("assistingParticipantIds") or []
                    ):
                        events.append(("post.ev.kill", {}, True))
            elif etype == "ELITE_MONSTER_KILL":
                mine = (event.get("killerTeamId") or (100 if (event.get("killerId") or 0) <= 5 else 200)) == my_team_id
                key = MONSTER_KEYS.get(event.get("monsterType", ""))
                if key:
                    events.append(("post.ev.objective", {"what": key}, mine))
                    if not mine:
                        lost_objectives.append((minute, key))
            elif etype == "BUILDING_KILL":
                key = BUILDING_KEYS.get(event.get("buildingType", ""))
                lost = event.get("teamId") == my_team_id  # teamId = building's owner
                if key:
                    events.append(("post.ev.objective", {"what": key}, not lost))
                    if lost:
                        lost_objectives.append((minute, key))
        rows.append({
            "minute": minute, "diff": diff, "cs": cs, "events": events,
            "gold": me.get("totalGold", 0), "level": me.get("level", 1),
            "kda": (kills, deaths, assists),
        })

    insights = _timeline_insights(rows, my_cs, my_deaths, lost_objectives)
    return rows, insights


def _timeline_insights(rows, my_cs, my_deaths, lost_objectives):
    insights = []
    # Deaths that gifted an objective within the next two minutes.
    blamed = set()
    for death_min in my_deaths:
        for obj_min, key in lost_objectives:
            if death_min <= obj_min <= death_min + DEATH_OBJECTIVE_WINDOW and obj_min not in blamed:
                blamed.add(obj_min)
                insights.append(("post.ti.death_objective", {"minute": death_min, "what": key}, False))
                break
        if len(blamed) >= 3:
            break

    # Biggest gold swing against us (lost teamfight).
    worst_drop, worst_min = 0, None
    for prev, cur in zip(rows, rows[1:]):
        drop = prev["diff"] - cur["diff"]
        if drop > worst_drop:
            worst_drop, worst_min = drop, cur["minute"]
    if worst_drop >= SWING_THRESHOLD and worst_min:
        insights.append(("post.ti.swing", {"minute": worst_min, "gold": f"-{worst_drop:,}"}, False))

    # Comeback: gold diff crosses from clearly negative to positive and stays.
    for prev, cur in zip(rows, rows[1:]):
        if prev["diff"] <= -500 < cur["diff"]:
            insights.append(("post.ti.comeback", {"minute": cur["minute"]}, True))
            break

    # Farm stall: 5+ minutes below 4 CS/min after laning phase.
    start = 10
    for i in range(start, max(len(my_cs) - 5, start)):
        if (my_cs[i + 5] - my_cs[i]) / 5 < 4:
            insights.append(
                ("post.ti.cs_stall", {"start": i, "end": i + 5,
                                      "csm": f"{(my_cs[i + 5] - my_cs[i]) / 5:.1f}"}, False)
            )
            break
    return insights


def analyze_match(match, timeline, my_puuid):
    """Pure function: match + timeline JSON -> structured analysis with i18n highlight keys."""
    info = match.get("info") or {}
    participants = info.get("participants") or []
    me = next((p for p in participants if p.get("puuid") == my_puuid), None)
    if me is None:
        return None

    duration = info.get("gameDuration", 0) or 1
    minutes = duration / 60
    my_team_id = me.get("teamId")
    team = [p for p in participants if p.get("teamId") == my_team_id]
    team_damage = sum(p.get("totalDamageDealtToChampions", 0) for p in team) or 1
    damage = me.get("totalDamageDealtToChampions", 0)
    cs = me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0)
    kills, deaths, assists = me.get("kills", 0), me.get("deaths", 0), me.get("assists", 0)
    kda = (kills + assists) / max(deaths, 1)
    vision = me.get("visionScore", 0)
    role = me.get("teamPosition", "")

    gold15_diff = None
    if timeline:
        frames = (timeline.get("info") or {}).get("frames") or []
        frame = frames[GOLD_AT_MINUTE] if len(frames) > GOLD_AT_MINUTE else (frames[-1] if frames else None)
        if frame:
            gold = {100: 0, 200: 0}
            for pid, pf in (frame.get("participantFrames") or {}).items():
                gold[100 if int(pid) <= 5 else 200] += pf.get("totalGold", 0)
            gold15_diff = gold[my_team_id] - gold[200 if my_team_id == 100 else 100]

    highlights = []
    win = bool(me.get("win"))
    highlights.append(("post.hi.win" if win else "post.hi.loss", {}, win))
    if damage / team_damage >= 0.30 and len(team) > 1:
        highlights.append(("post.hi.damage", {"pct": round(damage / team_damage * 100)}, True))
    if kda >= 5:
        highlights.append(("post.hi.kda", {"kda": f"{kda:.1f}"}, True))
    if deaths >= 8:
        highlights.append(("post.hi.deaths", {"deaths": deaths}, False))
    csm = cs / minutes
    if role != "UTILITY":
        if csm >= 7:
            highlights.append(("post.hi.cs_high", {"csm": f"{csm:.1f}"}, True))
        elif csm < 4.5:
            highlights.append(("post.hi.cs_low", {"csm": f"{csm:.1f}"}, False))
    vision_per_min = vision / minutes
    if vision_per_min >= 1.5:
        highlights.append(("post.hi.vision_high", {"vpm": f"{vision_per_min:.1f}"}, True))
    elif vision_per_min < 0.8:
        highlights.append(("post.hi.vision_low", {"vpm": f"{vision_per_min:.1f}"}, False))
    if gold15_diff is not None:
        if gold15_diff >= 1500:
            highlights.append(("post.hi.gold_ahead", {"gold": f"+{gold15_diff:,}"}, True))
        elif gold15_diff <= -1500:
            highlights.append(("post.hi.gold_behind", {"gold": f"{gold15_diff:,}"}, False))

    players = [
        {
            "name": p.get("riotIdGameName") or p.get("summonerName") or "?",
            "champion_id": p.get("championId", 0),
            "mine": p.get("teamId") == my_team_id,
            "is_me": p.get("puuid") == my_puuid,
            "kills": p.get("kills", 0),
            "deaths": p.get("deaths", 0),
            "assists": p.get("assists", 0),
            "damage": p.get("totalDamageDealtToChampions", 0),
        }
        for p in participants
    ]
    players.sort(key=lambda p: (not p["mine"], -p["damage"]))

    timeline_rows = []
    if timeline:
        timeline_rows, timeline_insights = analyze_timeline(
            timeline, my_team_id, me.get("participantId")
        )
        highlights.extend(timeline_insights)

    return {
        "win": win,
        "duration": duration,
        "champion_id": me.get("championId", 0),
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "damage": damage,
        "damage_share": round(damage / team_damage * 100),
        "cs": cs,
        "csm": round(csm, 1),
        "vision": vision,
        "gold": me.get("goldEarned", 0),
        "gold15_diff": gold15_diff,
        "highlights": highlights,
        "players": players,
        "timeline": timeline_rows,
    }


class PostGame:
    """Fetches and analyzes your latest match. Runs once per game; ~3 requests."""

    def __init__(self, riot, lcu, log=None):
        self.riot = riot
        self.lcu = lcu
        self.log = log or (lambda _level, _text: None)

    def fetch_latest(self):
        """Returns (status, analysis). status: ok | no_key | bad_key | unavailable."""
        if not self.riot.available:
            return "no_key", None
        status, context = client_context(self.lcu, self.riot)
        if status != "ok":
            if status == "unavailable":
                self.log("warn", t("log.post.no_context"))
            return status, None
        puuid, platform = context
        self.log("info", t("log.post.fetch"))

        match_id = None
        for attempt in range(MATCH_RETRIES):
            code, ids = self.riot.regional_get(
                platform, f"/lol/match/v5/matches/by-puuid/{puuid}/ids", params={"count": 1}
            )
            if code in (401, 403):
                self.log("error", t("log.post.http", code=code, step="match ids"))
                return "bad_key", None
            if ok(code) and isinstance(ids, list) and ids:
                match_id = ids[0]
                break
            if attempt < MATCH_RETRIES - 1:
                self.log("info", t("log.post.waiting_publish", attempt=attempt + 1))
                time.sleep(MATCH_RETRY_DELAY)
            else:
                self.log("warn", t("log.post.http", code=code, step="match ids"))
        if not match_id:
            return "unavailable", None

        code, match = self.riot.regional_get(platform, f"/lol/match/v5/matches/{match_id}")
        if not ok(code) or not isinstance(match, dict):
            self.log("warn", t("log.post.http", code=code, step="match"))
            return "unavailable", None
        code, timeline = self.riot.regional_get(platform, f"/lol/match/v5/matches/{match_id}/timeline")
        timeline = timeline if ok(code) and isinstance(timeline, dict) else None

        analysis = analyze_match(match, timeline, puuid)
        return ("ok", analysis) if analysis else ("unavailable", None)
