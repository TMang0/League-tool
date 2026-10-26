import json
import tempfile
import unittest
from pathlib import Path

from leaguetool import i18n
from leaguetool.config import Config
from leaguetool.constants import ROLE_KEYS, SHARD_ROWS, SPELL_IDS


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("es")

    def test_both_languages_define_the_same_keys(self):
        self.assertEqual(set(i18n.STRINGS["es"]), set(i18n.STRINGS["en"]))

    def test_placeholders_match_between_languages(self):
        import string

        def fields(text):
            return {name for _, name, _, _ in string.Formatter().parse(text) if name}

        for key, text in i18n.STRINGS["es"].items():
            self.assertEqual(fields(text), fields(i18n.STRINGS["en"][key]), key)

    def test_game_data_has_names_in_both_languages(self):
        keys = [f"role.{r}" for r in ROLE_KEYS] + [f"spell.{s}" for s in SPELL_IDS]
        keys += [f"shard.{s}" for row in SHARD_ROWS for s in row]
        for language in i18n.LANGUAGES:
            for key in keys:
                self.assertIn(key, i18n.STRINGS[language])

    def test_t_switches_language_and_falls_back_to_key(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("log.match_accepted"), "Match accepted.")
        i18n.set_language("es")
        self.assertEqual(i18n.t("log.match_accepted"), "Partida aceptada.")
        self.assertEqual(i18n.t("missing.key"), "missing.key")

    def test_unknown_language_falls_back_to_spanish(self):
        i18n.set_language("fr")
        self.assertEqual(i18n.get_language(), "es")


class ConfigTests(unittest.TestCase):
    def path(self):
        return Path(tempfile.mkdtemp()) / "config.json"

    def test_overwrite_rune_page_is_on_by_default(self):
        self.assertTrue(Config(self.path()).load().settings["overwrite_rune_page"])

    def test_old_config_with_old_default_is_migrated(self):
        path = self.path()
        path.write_text(json.dumps({"settings": {"overwrite_rune_page": False, "ban_delay": 7}}), encoding="utf-8")
        cfg = Config(path).load()
        self.assertTrue(cfg.settings["overwrite_rune_page"])
        self.assertEqual(cfg.settings["ban_delay"], 7)

    def test_choice_is_kept_once_config_is_current(self):
        path = self.path()
        cfg = Config(path).load()
        cfg.settings["overwrite_rune_page"] = False
        cfg.data["language"] = "en"
        cfg.save()
        again = Config(path).load()
        self.assertFalse(again.settings["overwrite_rune_page"])
        self.assertEqual(again.data["language"], "en")


if __name__ == "__main__":
    unittest.main()
