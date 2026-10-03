from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.profile import ProfileService
from mina_assistant.app.wardrobe import WardrobeService


class ProfileWardrobeTest(unittest.TestCase):
    def test_profile_updates_are_saved_as_confirmed_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            memory = MemoryService(db)
            profile = ProfileService(db=db, memory=memory)

            result = profile.update_profile(
                {
                    "display_name": "Rafa",
                    "city": "Temuco",
                    "fit_preferences": "wide-leg, relaxed and comfortable",
                }
            )

            self.assertEqual(result["display_name"], "Rafa")
            self.assertEqual(result["city"], "Temuco")
            memories = memory.context_items("fashion_context", limit=20)
            values = "\n".join(item["value"] for item in memories)
            self.assertIn("Preferred name: Rafa", values)
            self.assertIn("Fit preferences: wide-leg", values)

    def test_wardrobe_item_syncs_to_memory_and_deletes_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            memory = MemoryService(db)
            wardrobe = WardrobeService(db=db, memory=memory)

            item = wardrobe.create_item(
                name="Black wide-leg jeans",
                category="bottom",
                colors=["black"],
                fit="wide-leg",
                occasions=["casual", "night"],
                style_tags=["minimal"],
                favorite=True,
            )

            self.assertGreater(item["id"], 0)
            self.assertTrue(item["favorite"])
            self.assertEqual(db.list_wardrobe_items()[0]["name"], "Black wide-leg jeans")

            memories = memory.list_items(kind="wardrobe_model")
            self.assertEqual(len(memories), 1)
            self.assertIn("Black wide-leg jeans", memories[0]["value"])
            self.assertIn("colors=black", memories[0]["value"])

            updated = wardrobe.update_item(item["id"], notes="Works well with boots.")
            self.assertIsNotNone(updated)
            memories = memory.list_items(kind="wardrobe_model")
            self.assertIn("Works well with boots", memories[0]["value"])

            self.assertTrue(wardrobe.delete_item(item["id"]))
            self.assertEqual(db.list_wardrobe_items(), [])
            self.assertEqual(memory.list_items(kind="wardrobe_model"), [])


if __name__ == "__main__":
    unittest.main()
