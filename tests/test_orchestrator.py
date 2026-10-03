from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mina_assistant.app.config import get_settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.llm import LLMResponse, LLMStreamChunk
from mina_assistant.app.orchestrator import AssistantOrchestrator


class FakeLLM:
    def default_provider(self):
        return "ollama"

    def default_model(self, provider=None):
        return "fake-model"

    async def chat(self, messages: list[dict[str, str]], *, provider=None, model=None, temperature=0.4):
        self.messages = messages
        return LLMResponse(
            content="Respuesta de prueba",
            model=model or "fake-model",
            provider=provider or "ollama",
            prompt_eval_count=3,
            eval_count=4,
        )

    async def chat_stream(self, messages: list[dict[str, str]], *, provider=None, model=None, temperature=0.4):
        self.messages = messages
        yield LLMStreamChunk(content="Respuesta ", model=model or "fake-model", provider=provider or "ollama")
        yield LLMStreamChunk(content="en stream", model=model or "fake-model", provider=provider or "ollama")
        yield LLMStreamChunk(
            content="",
            model=model or "fake-model",
            provider=provider or "ollama",
            done=True,
            prompt_eval_count=5,
            eval_count=6,
        )


class WeakDisclaimerLLM(FakeLLM):
    async def chat(self, messages: list[dict[str, str]], *, provider=None, model=None, temperature=0.4):
        self.messages = messages
        return LLMResponse(
            content=(
                "Como soy una asistente sin sentido del olfato, no puedo probarlas directamente. "
                "Mi favorita seria La Nuit Tresor por su perfil de frambuesa y vainilla."
            ),
            model=model or "fake-model",
            provider=provider or "ollama",
        )


class OrchestratorTest(unittest.IsolatedAsyncioTestCase):
    async def test_chat_builds_context_and_persists_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            llm = FakeLLM()
            orchestrator = AssistantOrchestrator(settings=settings, db=db, llm=llm)  # type: ignore[arg-type]

            result = await orchestrator.chat("  Hola   Mina  ", model="fake-model")

            self.assertEqual(result.content, "Respuesta de prueba")
            self.assertEqual(result.tokens_used, 7)
            self.assertEqual(llm.messages[0]["role"], "system")
            self.assertEqual(llm.messages[-1]["content"], "Hola Mina")

            persisted = db.list_messages(result.session_id)
            self.assertEqual(len(persisted), 2)
            self.assertEqual(persisted[0]["role"], "user")
            self.assertEqual(persisted[1]["role"], "assistant")

    async def test_stream_chat_yields_chunks_and_persists_final_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            llm = FakeLLM()
            orchestrator = AssistantOrchestrator(settings=settings, db=db, llm=llm)  # type: ignore[arg-type]

            events = [
                event
                async for event in orchestrator.stream_chat("Hola", model="fake-model")
            ]

            self.assertEqual([event.type for event in events], [
                "turn_started",
                "assistant_chunk",
                "assistant_chunk",
                "assistant_message",
            ])
            self.assertEqual(events[1].delta, "Respuesta ")
            self.assertEqual(events[2].delta, "en stream")
            self.assertEqual(events[-1].content, "Respuesta en stream")
            self.assertEqual(events[-1].tokens_used, 11)

            persisted = db.list_messages(events[-1].session_id)
            self.assertEqual([row["role"] for row in persisted], ["user", "assistant"])
            self.assertEqual(persisted[-1]["content"], "Respuesta en stream")

    async def test_explicit_memory_is_captured_and_injected_into_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            llm = FakeLLM()
            orchestrator = AssistantOrchestrator(settings=settings, db=db, llm=llm)  # type: ignore[arg-type]

            await orchestrator.chat("Recuerda que prefiero respuestas tecnicas y detalladas", model="fake-model")

            items = db.list_memory_items(kind="user_model")
            self.assertEqual(len(items), 1)
            self.assertIn("prefiero respuestas tecnicas", items[0]["value"])
            self.assertIn("Relevant structured context", llm.messages[0]["content"])
            self.assertIn("preferences", llm.messages[0]["content"])

    async def test_existing_memory_is_used_in_next_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            llm = FakeLLM()
            orchestrator = AssistantOrchestrator(settings=settings, db=db, llm=llm)  # type: ignore[arg-type]
            orchestrator.memory.create_item(
                kind="project_model",
                key="mina.next_actions",
                value="Implementar Shared Context Layer",
                confidence=0.9,
                source="test",
            )

            await orchestrator.chat("Que dejamos pendiente en el proyecto Mina?", model="fake-model")

            self.assertIn("project_model.mina.next_actions", llm.messages[0]["content"])
            self.assertIn("Implementar Shared Context Layer", llm.messages[0]["content"])

    async def test_chat_sanitizes_weak_ai_disclaimers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()
            llm = WeakDisclaimerLLM()
            orchestrator = AssistantOrchestrator(settings=settings, db=db, llm=llm)  # type: ignore[arg-type]

            result = await orchestrator.chat("Cual te gusta mas?", model="fake-model")

            self.assertNotIn("sin sentido del olfato", result.content)
            self.assertNotIn("no puedo probarlas", result.content)
            self.assertIn("Mi favorita seria La Nuit Tresor", result.content)


if __name__ == "__main__":
    unittest.main()
