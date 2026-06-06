import tempfile
import unittest
from pathlib import Path

from backend.memory.preferences import PreferenceExtractor, PreferenceStore
from backend.memory.scoring import MemoryScorer
from backend.skills import SkillManager


class TestMemoryAndSkills(unittest.TestCase):
    def test_memory_scoring_and_preferences(self):
        scorer = MemoryScorer()
        important = scorer.score_text("Always use Brave as my default browser", {"use_count": 3}, query="browser")
        smalltalk = scorer.score_text("thanks", {}, query="browser")
        self.assertGreater(important.final, smalltalk.final)
        prefs = PreferenceExtractor().extract("I prefer Brave and call me Zarrar")
        self.assertIn("preferred_browser", {p.key for p in prefs})
        self.assertIn("preferred_name", {p.key for p in prefs})

    def test_preference_store_and_skill_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PreferenceStore(str(Path(tmp) / "prefs.json"))
            store.ingest_text("I prefer Chrome")
            self.assertEqual(store.get("preferred_browser").value, "chrome")

            manager = SkillManager(str(Path(tmp) / "skills"))
            skill = manager.create_from_commands("coding mode", ["open notepad"], trigger_phrases=["start coding mode"])
            self.assertIsNotNone(manager.find_match("start coding mode"))
            reloaded = SkillManager(str(Path(tmp) / "skills"))
            self.assertIsNotNone(reloaded.get(skill.id))


if __name__ == "__main__":
    unittest.main()
