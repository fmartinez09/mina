from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mina_assistant.app.chat_tools import ChatToolService
from mina_assistant.app.config import get_settings
from mina_assistant.app.context import ContextBuilder
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.intent import IntentClassifier
from mina_assistant.app.llm import LLMResponse
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.orchestrator import AssistantOrchestrator
from mina_assistant.app.profile import ProfileService
from mina_assistant.app.style import StyleAssistantService


class RecordingLLM:
    def __init__(self):
        self.messages = []

    def default_provider(self):
        return "ollama"

    def default_model(self, provider=None):
        return "fake-model"

    async def chat(self, messages, **kwargs):
        self.messages = messages
        return LLMResponse(content="Test outfit", model="fake-model", provider="ollama")


class PersonalizationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = SQLiteStore(Path(self.directory.name) / "assistant.sqlite")
        self.db.initialize()
        self.memory = MemoryService(self.db)
        self.profile = ProfileService(db=self.db, memory=self.memory)
        self.settings = replace(get_settings(), database_path=self.db.database_path)

    def add_note(self, value, *, key="manual.identity", kind="user_model", source="desktop"):
        return self.memory.create_item(kind=kind, key=key, value=value, source=source, confidence=0.8)

    def old_profile_and_correction(self):
        self.profile.update_profile({"gender_identity": "Mujer", "style_keywords": "romantica"})
        return self.add_note("I im a men. I prefer men clothes.")

    async def test_new_manual_identity_overrides_older_profile_in_chat_and_planner(self):
        self.old_profile_and_correction()
        llm = RecordingLLM()
        tools = ChatToolService(db=self.db, profile=self.profile, web_search=None)
        orchestrator = AssistantOrchestrator(
            settings=self.settings, db=self.db, memory=self.memory, llm=llm, chat_tools=tools,
        )
        await orchestrator.chat("Mina, analiza mi armario y recomiendame un outfit.")

        system_context = llm.messages[0]["content"]
        self.assertIn("style gender identity: Hombre", system_context)
        self.assertIn("I prefer men clothes.", system_context)
        self.assertNotIn("Style gender identity: Mujer", system_context)
        self.assertNotIn("style gender identity: Mujer", system_context)
        outfit = tools._build_outfit_result("recomiendame un outfit")
        self.assertIn("I prefer men clothes.", outfit.content)

    async def test_dedicated_outfit_endpoint_uses_manual_notes_and_corrected_profile(self):
        self.old_profile_and_correction()
        llm = RecordingLLM()
        style = StyleAssistantService(db=self.db, llm=llm, profile=self.profile, web_search=None)
        await style.outfit_plan(prompt="Recomiendame un outfit")

        prompt = llm.messages[1]["content"]
        self.assertIn("Hombre", prompt)
        self.assertNotIn("Mujer", prompt)
        self.assertIn("I prefer men clothes.", prompt)
        self.assertIn("romantica", prompt)  # Keep the aesthetic; it is independent of clothing direction.

    async def test_identity_survives_context_budget_and_newer_image_memories(self):
        identity = self.old_profile_and_correction()
        for index in range(25):
            self.add_note(f"Image analysis {index}", key=f"media.{index}", kind="media_memory", source="media")
        for index in range(18):
            self.add_note(f"Preference {index}", key=f"fashion.{index}", kind="fashion_preference")
        builder = ContextBuilder(
            settings=self.settings, db=self.db, memory=self.memory, intent_classifier=IntentClassifier(),
        )
        context = await builder.build(session_id=None, content="Recomiendame un outfit")
        self.assertIn(identity["id"], [item["id"] for item in context.memory_items])
        self.assertIn("I prefer men clothes.", context.system_context)
        self.assertNotIn("Style gender identity: Mujer", context.system_context)
        self.assertLessEqual(len(context.memory_items), 16)

    async def test_edit_and_delete_reconcile_identity_without_rewriting_memories(self):
        identity = self.old_profile_and_correction()
        self.assertEqual(self.profile.get_profile()["gender_identity"], "Hombre")
        self.memory.update_item(identity["id"], value="Soy una persona no binaria. Prefiero ropa neutra.")
        self.assertEqual(self.profile.get_profile()["gender_identity"], "No binario")
        self.memory.delete_item(identity["id"])
        self.assertEqual(self.profile.get_profile()["gender_identity"], "Mujer")

    async def test_later_explicit_profile_update_wins_over_old_note(self):
        identity = self.old_profile_and_correction()
        self.profile.update_profile({"gender_identity": "No binario"})
        # Use distinct timestamps so the test does not depend on the clock's millisecond resolution.
        with self.db._connect() as conn:
            conn.execute("UPDATE memory_items SET updated_at='2026-10-01T00:00:00.000Z' WHERE id=?", (identity["id"],))
            conn.execute("UPDATE memory_items SET updated_at='2026-10-02T00:00:00.000Z' WHERE key='profile.gender_identity'")
        self.assertEqual(self.profile.get_profile()["gender_identity"], "No binario")

    async def test_clothing_preferences_negation_and_reference_people_do_not_infer_identity(self):
        self.profile.update_profile({"gender_identity": "Mujer"})
        for index, value in enumerate([
            "I prefer men clothes.", "No soy hombre.", "I am not a man.",
            'Example phrase: "I am a man".', "Mi pareja es hombre.",
        ]):
            self.add_note(value, key=f"manual.{index}")
        self.add_note("Soy hombre.", key="media.identity", source="media")
        self.assertEqual(self.profile.get_profile()["gender_identity"], "Mujer")
        self.assertIn("I prefer men clothes.", self.profile.user_context_block())

    async def test_spanish_and_english_explicit_identity_with_arbitrary_keys(self):
        for value, expected in [("Soy hombre", "Hombre"), ("I am a woman.", "Mujer"), ("I'm non-binary.", "No binario")]:
            with self.subTest(value=value):
                self.add_note(value, key="manual.identity")
                self.assertEqual(self.profile.get_profile()["gender_identity"], expected)


if __name__ == "__main__":
    unittest.main()
