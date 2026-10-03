from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mina_assistant.app.config import get_settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.llm import LLMResponse
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.reflection import ReflectionService


class FakeReflectionLLM:
    def default_provider(self):
        return "ollama"

    def default_model(self, provider=None):
        return "fake-model"

    async def chat(self, messages: list[dict[str, str]], *, provider=None, model=None, temperature=0.4):
        self.messages = messages
        return LLMResponse(
            content=(
                '{"candidates":[{'
                '"kind":"user_model",'
                '"key":"preferences.communication",'
                '"value":"The user prefers thoughtful concise answers.",'
                '"confidence":0.91,'
                '"rationale":"Stable communication preference.",'
                '"evidence":"I prefer thoughtful concise answers."'
                "}]}"
            ),
            model=model or "fake-model",
            provider=provider or "ollama",
        )


class ReflectionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_reflect_session_creates_pending_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            memory = MemoryService(db)
            service = ReflectionService(
                settings=settings,
                db=db,
                llm=FakeReflectionLLM(),  # type: ignore[arg-type]
                memory=memory,
            )

            session_id = db.ensure_session(title="Reflection")
            db.add_message(session_id, "user", "I prefer thoughtful concise answers.")
            db.add_message(session_id, "assistant", "Understood.")

            result = await service.reflect_session(session_id=session_id, model="fake-model")

            self.assertEqual(result.skipped, 0)
            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0]["status"], "pending")
            self.assertEqual(result.candidates[0]["key"], "preferences.communication")

    async def test_approve_candidate_creates_memory_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            memory = MemoryService(db)
            service = ReflectionService(
                settings=settings,
                db=db,
                llm=FakeReflectionLLM(),  # type: ignore[arg-type]
                memory=memory,
            )

            candidate = db.create_reflection_candidate(
                kind="user_model",
                key="preferences.communication",
                value="The user prefers thoughtful concise answers.",
                confidence=0.91,
            )

            result = service.approve_candidate(candidate["id"])

            self.assertEqual(result.candidate["status"], "approved")
            self.assertIsNotNone(result.memory_item)
            self.assertEqual(result.memory_item["key"], "preferences.communication")
            self.assertEqual(len(db.list_memory_items(kind="user_model")), 1)


if __name__ == "__main__":
    unittest.main()
