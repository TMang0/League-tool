from .i18n import t

ROLE_KEYS = ["ANY", "TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
SPELL_IDS = [1, 3, 4, 6, 7, 11, 12, 14, 21]
SHARD_ROWS = [
    [5008, 5005, 5007],
    [5008, 5010, 5001],
    [5011, 5013, 5001],
]

RUNE_PAGE_PREFIX = "LT - "


def roles():
    return [(key, t(f"role.{key}")) for key in ROLE_KEYS]


def role_name(key):
    return t(f"role.{key}")


def spell_names():
    return {spell_id: t(f"spell.{spell_id}") for spell_id in SPELL_IDS}


def shard_name(shard_id):
    return t(f"shard.{shard_id}")


def phase_name(phase):
    text = t(f"phase.{phase}")
    return phase if text == f"phase.{phase}" else text
