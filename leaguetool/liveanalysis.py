"""Real-time advice engine: pure functions over Live Client Data snapshots.

Everything here is cheap (no I/O, tiny loops) so it can run every couple of
seconds on any machine. Text is returned as i18n keys; the UI localizes.
"""
from dataclasses import dataclass, field

CARRY_TAGS = {"Marksman", "Mage", "Assassin"}
CC_TAGS = {"Mage", "Tank", "Support"}

# Champions whose kits revolve around healing (Data Dragon ids, normalized).
HEALERS = {
    "aatrox", "briar", "draven", "drmundo", "fiddlesticks", "illaoi", "irelia", "kaisa",
    "kayn", "ksante", "maokai", "milio", "nami", "nidalee", "olaf", "renata", "sona",
    "soraka", "swain", "sylas", "taric", "trundle", "vladimir", "warwick", "yuumi", "zaahen",
}

# Situational item ids (Data Dragon). Kept small on purpose: one row per rule.
ITEMS_MR = [3111, 2504, 4401]       # Mercury's Treads, Kaenic Rookern, Force of Nature
ITEMS_ARMOR = [3047, 3143, 3075]    # Plated Steelcaps, Randuin's Omen, Thornmail
ITEMS_ANTIHEAL = [3123, 3916, 3076]  # Executioner's Calling, Oblivion Orb, Bramble Vest
ITEMS_ANTI_CC = [3111, 3140]        # Mercury's Treads, Quicksilver Sash
ITEMS_ANTI_TANK = [3036, 3135, 3071]  # Lord Dominik's, Void Staff, Black Cleaver
ITEMS_ANTI_ASSASSIN = [3157, 3026]  # Zhonya's Hourglass, Guardian Angel

# Core builds per champion class (class comes from Data Dragon tags/stats, no per-champion data).
BUILD_CORE = {
    "marksman": [3031, 3094, 3036],      # Infinity Edge, Rapid Firecannon, Lord Dominik's
    "assassin": [3142, 6692, 3814],      # Youmuu's Ghostblade, Eclipse, Edge of Night
    "mage": [6655, 4645, 3089],          # Luden's Companion, Shadowflame, Rabadon's
    "fighter": [3078, 3071, 3053],       # Trinity Force, Black Cleaver, Sterak's Gage
    "tank": [6665, 3068, 3075],          # Jak'Sho, Sunfire Aegis, Thornmail
    "enchanter": [6617, 3107, 6616],     # Moonstone, Redemption, Staff of Flowing Water
    "tank_support": [3190, 3050, 3109],  # Locket, Zeke's, Knight's Vow
}
BOOTS_BY_CLASS = {
    "marksman": 3006, "assassin": 3158, "mage": 3020, "fighter": 3047,
    "tank": 3047, "enchanter": 3158, "tank_support": 3047,
}
BOOTS_MR = 3111     # Mercury's Treads
BOOTS_ARMOR = 3047  # Plated Steelcaps

ALL_BOOTS = {3006, 3009, 3020, 3047, 3111, 3158}
TRINKETS = {3340, 3363, 3364}
# Component -> finished items; owning the upgrade silences the component suggestion.
UPGRADES = {3123: [3033, 3011], 3916: [3165], 3076: [3075], 3140: [3139]}
ELIXIR_BY_CLASS = {
    "marksman": 2140, "assassin": 2140, "mage": 2139,
    "fighter": 2138, "tank": 2138, "enchanter": 2139, "tank_support": 2138,
}
PHASE_MID = 480    # 8:00 — situational items unlock
PHASE_LATE = 1200  # 20:00 — elixir check for full builds

DRAGON_SOUL_POINT = 3
GRUB_EVENTS = {"HordeKill", "VoidgrubKill"}


@dataclass
class Suggestion:
    kind: str            # "focus" | "objective" | "item"
    text_key: str        # i18n key
    params: dict = field(default_factory=dict)
    priority: int = 5    # lower shows first
    item_ids: list = field(default_factory=list)
    icon_ids: list = field(default_factory=list)  # champion ids (focus) for icon display


@dataclass
class Advice:
    game_time: float = 0.0
    focus: list = field(default_factory=list)
    objectives: list = field(default_factory=list)
    items: list = field(default_factory=list)


def _norm(name):
    return "".join(c for c in (name or "").lower() if c.isalnum())


def build_champion_db(champions):
    """champions: Assets.champions {id: {"key", "name", "tags", "info"}} -> lookup by normalized key."""
    db = {}
    for champ in champions.values():
        db[_norm(champ["key"])] = champ
    return db


def classify(champ):
    """Damage profile from Data Dragon summary stats: 'AP', 'AD', 'MIXED' or 'TANK'."""
    info = champ.get("info") or {}
    tags = set(champ.get("tags") or [])
    attack, magic = info.get("attack", 0), info.get("magic", 0)
    if "Tank" in tags and attack <= 5 and magic <= 5:
        return "TANK"
    if magic >= attack + 2:
        return "AP"
    if attack >= magic + 2:
        return "AD"
    return "MIXED"


def champion_class(champ, position=""):
    """Build class from your lane position (live data) + Data Dragon tags/stats.

    Position wins: a support champion played top lane gets a solo-lane build,
    never the support core.
    """
    tags = set(champ.get("tags") or [])
    damage = classify(champ)
    if position == "UTILITY":
        return "tank_support" if "Tank" in tags or damage == "TANK" else "enchanter"
    if "Marksman" in tags:
        return "marksman"
    if "Assassin" in tags and damage != "AP":
        return "assassin"
    if not position and "Support" in tags:
        # Unknown position (blind pick, ARAM): trust the tags.
        return "tank_support" if "Tank" in tags else "enchanter"
    if "Tank" in tags or damage == "TANK":
        return "tank"
    if "Mage" in tags or damage == "AP":
        return "mage"
    return "fighter"


def _player_gold(player):
    return sum(item.get("price", 0) * item.get("count", 1) for item in player.get("items", []))


def _kda(player):
    scores = player.get("scores") or {}
    kills = scores.get("kills", 0)
    assists = scores.get("assists", 0)
    deaths = max(scores.get("deaths", 0), 1)
    return (kills + assists) / deaths, kills


def _enemies(data, champion_db):
    """Enemy players enriched with champion info, sorted by threat (most dangerous first)."""
    active_name = (data.get("activePlayer") or {}).get("summonerName", "")
    players = data.get("allPlayers") or []
    my_team = next((p.get("team") for p in players if p.get("summonerName") == active_name), None)
    enemies = []
    for player in players:
        if player.get("team") == my_team:
            continue
        champ = champion_db.get(_norm(player.get("championName")), {})
        gold = _player_gold(player)
        kda, kills = _kda(player)
        threat = gold / 1000 + kda * 1.5 + player.get("level", 1) * 0.4
        name = champ.get("name", player.get("championName", "?"))
        if player.get("isBot"):
            name += " 🤖"
        enemies.append(
            {
                "name": name,
                "champion": champ,
                "damage": classify(champ) if champ else "MIXED",
                "tags": set(champ.get("tags") or []),
                "gold": gold,
                "kills": kills,
                "kda": kda,
                "level": player.get("level", 1),
                "threat": threat,
            }
        )
    enemies.sort(key=lambda e: e["threat"], reverse=True)
    return enemies


def _focus(enemies):
    suggestions = []
    for rank, enemy in enumerate(enemies[:3]):
        tags = enemy["tags"]
        if enemy["kills"] >= 5 and enemy["kda"] >= 3:
            key, priority = "live.focus.fed", 1
        elif tags & CARRY_TAGS and rank == 0:
            key, priority = "live.focus.carry", 2
        elif enemy["threat"] < enemies[0]["threat"] * 0.45:
            key, priority = "live.focus.easy", 3
        else:
            key, priority = "live.focus.threat", 2
        suggestions.append(
            Suggestion(
                "focus", key, {"champion": enemy["name"]}, priority + rank,
                icon_ids=[enemy["champion"].get("id", 0)],
            )
        )
    return suggestions


def _count_events(events, names, team_of):
    """Count events per team: team_of(killer_name) -> 'ORDER'/'CHAOS'/None."""
    mine = theirs = 0
    last_time = {}
    for event in events:
        name = event.get("EventName", "")
        if name not in names:
            continue
        team = team_of(event.get("KillerName", ""))
        if team == "mine":
            mine += 1
        elif team == "theirs":
            theirs += 1
        last_time[name] = event.get("EventTime", 0)
    return mine, theirs, last_time


def _objectives(data, enemies):
    players = data.get("allPlayers") or []
    active_name = (data.get("activePlayer") or {}).get("summonerName", "")
    my_team = next((p.get("team") for p in players if p.get("summonerName") == active_name), None)
    teams = {p.get("summonerName"): ("mine" if p.get("team") == my_team else "theirs") for p in players}
    team_of = lambda name: teams.get(name)

    events = (data.get("events") or {}).get("Events") or []
    game_time = (data.get("gameData") or {}).get("gameTime", 0)
    suggestions = []

    my_dragons, their_dragons, _ = _count_events(events, {"DragonKill"}, team_of)
    if their_dragons >= DRAGON_SOUL_POINT:
        suggestions.append(Suggestion("objective", "live.obj.soul", {}, 1))
    elif their_dragons > my_dragons:
        suggestions.append(Suggestion("objective", "live.obj.dragon", {}, 2))

    my_grubs, their_grubs, _ = _count_events(events, GRUB_EVENTS, team_of)
    if game_time < 900 and their_grubs > my_grubs:
        suggestions.append(Suggestion("objective", "live.obj.grubs", {}, 3))

    my_herald, their_herald, _ = _count_events(events, {"HeraldKill"}, team_of)
    if 840 <= game_time < 1200 and not my_herald and not their_herald:
        suggestions.append(Suggestion("objective", "live.obj.herald", {}, 4))

    my_baron, their_baron, baron_times = _count_events(events, {"BaronKill"}, team_of)
    if game_time >= 1500:
        last_baron = baron_times.get("BaronKill", -999)
        if their_baron and game_time - last_baron < 180:
            suggestions.append(Suggestion("objective", "live.obj.enemy_baron", {}, 1))
        elif my_baron and game_time - last_baron < 180:
            suggestions.append(Suggestion("objective", "live.obj.push_baron", {}, 1))
        else:
            suggestions.append(Suggestion("objective", "live.obj.baron", {}, 4))

    for event in reversed(events[-8:]):
        if event.get("EventName") == "Ace" and game_time - event.get("EventTime", 0) < 60:
            if team_of(event.get("Acer", "")) == "mine":
                suggestions.append(Suggestion("objective", "live.obj.ace", {}, 1))
            break

    suggestions.sort(key=lambda s: s.priority)
    return suggestions[:3]


def _me(data, champion_db):
    """Your player entry and champion data. (None, None) if unknown."""
    active = (data.get("activePlayer") or {}).get("summonerName", "")
    for player in data.get("allPlayers") or []:
        if player.get("summonerName") == active:
            return player, champion_db.get(_norm(player.get("championName")))
    return None, None


def _owned_ids(player):
    """Item ids the player currently owns (trinkets ignored)."""
    if not player:
        return set()
    return {
        item.get("itemID")
        for item in player.get("items", [])
        if item.get("count", 1) > 0 and item.get("itemID") not in TRINKETS
    }


def _is_owned(owned, item_id):
    return item_id in owned or any(upgrade in owned for upgrade in UPGRADES.get(item_id, []))


def _build(me_champ, enemies, owned, game_time, position=""):
    """Core progression + adaptive boots + late-game elixir, minus what you already own."""
    if not me_champ:
        return []
    cls = champion_class(me_champ, position)
    if cls not in BUILD_CORE:
        return []
    suggestions = []

    remaining_core = [i for i in BUILD_CORE[cls] if not _is_owned(owned, i)]
    if remaining_core:
        suggestions.append(Suggestion("item", f"live.build.core.{cls}", {}, 0, remaining_core))

    if not owned & ALL_BOOTS:
        cc_count = sum(1 for e in enemies if e["tags"] & CC_TAGS)
        total_gold = sum(e["gold"] for e in enemies) or 1
        ap_share = sum(e["gold"] for e in enemies if e["damage"] == "AP") / total_gold
        ad_share = sum(e["gold"] for e in enemies if e["damage"] == "AD") / total_gold
        if cc_count >= 3 or ap_share >= 0.55:
            key, boots = "live.build.boots.mr", BOOTS_MR
        elif ad_share >= 0.55:
            key, boots = "live.build.boots.armor", BOOTS_ARMOR
        else:
            key, boots = "live.build.boots.dmg", BOOTS_BY_CLASS[cls]
        suggestions.append(Suggestion("item", key, {}, 1, [boots]))
    if game_time >= PHASE_LATE and len(owned) >= 6 and not _is_owned(owned, ELIXIR_BY_CLASS[cls]):
        suggestions.append(Suggestion("item", "live.build.elixir", {}, 1, [ELIXIR_BY_CLASS[cls]]))
    return suggestions


def _items(enemies, owned, game_time):
    if not enemies:
        return []
    suggestions = []
    total_gold = sum(e["gold"] for e in enemies) or 1
    ap_gold = sum(e["gold"] for e in enemies if e["damage"] == "AP")
    ad_gold = sum(e["gold"] for e in enemies if e["damage"] == "AD")

    if ap_gold / total_gold >= 0.55:
        suggestions.append(Suggestion("item", "live.item.mr", {}, 2, ITEMS_MR))
    elif ad_gold / total_gold >= 0.55:
        suggestions.append(Suggestion("item", "live.item.armor", {}, 2, ITEMS_ARMOR))

    fed_healer = next(
        (e for e in enemies if _norm(e["champion"].get("key", "")) in HEALERS and e["kills"] >= 3), None
    )
    if fed_healer:
        suggestions.append(
            Suggestion("item", "live.item.antiheal_fed", {"champion": fed_healer["name"]}, 1, ITEMS_ANTIHEAL)
        )
    elif any(_norm(e["champion"].get("key", "")) in HEALERS for e in enemies):
        suggestions.append(Suggestion("item", "live.item.antiheal", {}, 3, ITEMS_ANTIHEAL))

    if sum(1 for e in enemies if e["tags"] & CC_TAGS) >= 3:
        suggestions.append(Suggestion("item", "live.item.tenacity", {}, 3, ITEMS_ANTI_CC))

    if sum(1 for e in enemies if "Tank" in e["tags"]) >= 2:
        suggestions.append(Suggestion("item", "live.item.pen", {}, 3, ITEMS_ANTI_TANK))

    fed_assassin = next((e for e in enemies if "Assassin" in e["tags"] and e["kills"] >= 5), None)
    if fed_assassin:
        suggestions.append(
            Suggestion(
                "item", "live.item.survive", {"champion": fed_assassin["name"]}, 1, ITEMS_ANTI_ASSASSIN
            )
        )

    # Drop what you already own (or own the upgrade of); drop emptied rules.
    for suggestion in suggestions:
        suggestion.item_ids = [i for i in suggestion.item_ids if not _is_owned(owned, i)]
    suggestions = [s for s in suggestions if s.item_ids]
    # Lane phase only shows urgent rules (fed assassin, fed healer); comp items wait for mid game.
    if game_time < PHASE_MID:
        suggestions = [s for s in suggestions if s.priority <= 1]
    suggestions.sort(key=lambda s: s.priority)
    return suggestions[:4]


def analyze(data, champion_db):
    """Turns one allgamedata snapshot into prioritized advice."""
    advice = Advice(game_time=(data.get("gameData") or {}).get("gameTime", 0))
    if not isinstance(data, dict) or not data.get("allPlayers"):
        return advice
    enemies = _enemies(data, champion_db)
    me_player, me_champ = _me(data, champion_db)
    owned = _owned_ids(me_player)
    position = (me_player or {}).get("position", "")
    advice.focus = _focus(enemies)
    advice.objectives = _objectives(data, enemies)
    build = _build(me_champ, enemies, owned, advice.game_time, position)
    advice.items = sorted(
        build + _items(enemies, owned, advice.game_time), key=lambda s: s.priority
    )[:6]
    return advice
