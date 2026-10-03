from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mina_assistant.app.config import get_settings
from mina_assistant.app.context import ContextBuilder
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.intent import IntentClassifier
from mina_assistant.app.memory import MemoryService, classify_memory_fact


class PersonalityFashionMemoryTest(unittest.IsolatedAsyncioTestCase):
    def test_classifies_fashion_personality_and_response_style(self) -> None:
        self.assertEqual(
            classify_memory_fact("me gustan los pantalones wide leg negros")[0],
            "fashion_preference",
        )
        self.assertEqual(
            classify_memory_fact("tengo una chaqueta negra oversize en mi guardarropa")[0],
            "wardrobe_model",
        )
        self.assertEqual(
            classify_memory_fact("la personalidad de Mina debe ser curiosa y honesta")[0],
            "personality_profile",
        )
        self.assertEqual(
            classify_memory_fact("prefiero que Mina me responda con humor ligero")[0],
            "relationship_signal",
        )

    async def test_fashion_context_retrieves_wardrobe_and_style_memories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            memory = MemoryService(db)
            memory.create_item(
                kind="wardrobe_model",
                key="wardrobe.items.black.wide.leg.pants",
                value="User owns black wide-leg pants.",
                confidence=0.9,
            )
            memory.create_item(
                kind="fashion_preference",
                key="fashion.preferences.korean.casual",
                value="User likes Korean casual silhouettes.",
                confidence=0.8,
            )

            builder = ContextBuilder(
                settings=settings,
                db=db,
                memory=memory,
                intent_classifier=IntentClassifier(),
            )

            context = await builder.build(session_id=None, content="Que outfit puedo armar con mis pantalones?")

            self.assertEqual(context.intent.name, "fashion_context")
            self.assertIn("wardrobe_model.wardrobe.items.black.wide.leg.pants", context.system_context)
            self.assertIn("fashion_preference.fashion.preferences.korean.casual", context.system_context)

    async def test_context_includes_response_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            memory = MemoryService(db)
            builder = ContextBuilder(
                settings=settings,
                db=db,
                memory=memory,
                intent_classifier=IntentClassifier(),
            )

            context = await builder.build(session_id=None, content="Cual perfume te gusta mas?")

            self.assertIn("Mina response policy", context.system_context)
            self.assertIn("Do not use generic AI disclaimers", context.system_context)


if __name__ == "__main__":
    unittest.main()
