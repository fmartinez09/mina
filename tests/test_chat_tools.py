from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mina_assistant.app.chat_tools import ChatToolService
from mina_assistant.app.config import get_settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.llm import LLMResponse
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.orchestrator import AssistantOrchestrator
from mina_assistant.app.profile import ProfileService
from mina_assistant.app.web_search import WebImageResult, WebImageSearchResponse, WebSearchResponse, WebSearchResult


class FakeWebSearch:
    def __init__(self):
        self.search_queries: list[str] = []
        self.image_queries: list[str] = []

    async def search(self, query, *, provider=None, limit=None):
        self.search_queries.append(query)
        return WebSearchResponse(
            query=query,
            provider="duckduckgo",
            results=[
                WebSearchResult(
                    title="Perfume review",
                    url="https://example.com/perfume",
                    snippet="A floral amber fragrance with soft projection.",
                    source="duckduckgo",
                )
            ],
        )

    async def image_search(self, query, *, provider=None, limit=None):
        self.image_queries.append(query)
        return WebImageSearchResponse(
            query=query,
            provider="duckduckgo",
            images=[
                WebImageResult(
                    title="Perfume bottle",
                    url="https://example.com/perfume-image",
                    image_url="https://example.com/perfume.jpg",
                    thumbnail_url="https://example.com/perfume-thumb.jpg",
                    source="duckduckgo",
                )
            ],
        )


class FakeLLM:
    def __init__(self):
        self.calls = 0
        self.messages: list[dict[str, str]] = []

    def default_provider(self):
        return "ollama"

    def default_model(self, provider=None):
        return "fake-model"

    async def chat(self, messages: list[dict[str, str]], *, provider=None, model=None, temperature=0.4):
        self.calls += 1
        self.messages = messages
        return LLMResponse(content="Respuesta con contexto", model="fake-model", provider="ollama")


def _services(tmpdir: str):
    settings = replace(get_settings(), database_path=Path(tmpdir) / "assistant.sqlite")
    db = SQLiteStore(settings.database_path)
    db.initialize()
    memory = MemoryService(db)
    profile = ProfileService(db=db, memory=memory)
    return settings, db, memory, profile


class ChatToolServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_adds_web_and_wardrobe_context_for_perfume_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, db, memory, profile = _services(tmpdir)
            profile.update_profile({"style_keywords": "minimal, delicate"})
            db.create_wardrobe_item(name="Soft musk perfume", category="perfume", style_tags=["clean"])
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]

            context = await tools.prepare("Mina, conoces este perfume? vale la pena?")
            system_message = context.system_message() or ""

            self.assertIn("profile_context", system_message)
            self.assertIn("wardrobe_context", system_message)
            self.assertIn("web_search", system_message)
            self.assertIn("[1] Perfume review", system_message)
            self.assertIn("Image references", system_message)
            self.assertIn("Soft musk perfume", system_message)

    async def test_prepare_adds_product_search_and_preference_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, db, _, profile = _services(tmpdir)
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]

            context = await tools.prepare("Mina, que perfumes son ricos con olor a frambuesa?")
            system_message = context.system_message() or ""
            names = [result.name for result in context.results]

            self.assertIn("product_search", names)
            self.assertIn("preference_candidate", names)
            self.assertIn("Product/image references", system_message)
            self.assertIn("Preferencia expresada: perfumes con olor o nota de frambuesa.", system_message)
            product_result = next(result for result in context.results if result.name == "product_search")
            self.assertEqual(product_result.payload["products"][0]["title"], "Perfume review")
            self.assertEqual(product_result.payload["images"][0]["title"], "Perfume bottle")

    async def test_prepare_builds_outfit_with_owned_wardrobe_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, db, _, profile = _services(tmpdir)
            db.create_wardrobe_item(
                name="Black wide-leg jeans",
                category="pants",
                colors=["black"],
                occasions=["casual"],
                style_tags=["minimal"],
            )
            db.create_wardrobe_item(
                name="Cream knit sweater",
                category="top",
                colors=["cream"],
                occasions=["casual"],
                style_tags=["soft"],
            )
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]

            context = await tools.prepare("Mina, armame un outfit casual con mis jeans")
            outfit = next(result for result in context.results if result.name == "build_outfit")

            self.assertEqual(outfit.status, "ready")
            self.assertIn("Black wide-leg jeans", outfit.content)
            self.assertEqual(outfit.payload["owned_count"], 1)
            self.assertEqual(outfit.payload["items"][0]["name"], "Black wide-leg jeans")

    async def test_prepare_contextualizes_followup_product_search_from_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, db, _, profile = _services(tmpdir)
            fake_search = FakeWebSearch()
            tools = ChatToolService(db=db, profile=profile, web_search=fake_search)  # type: ignore[arg-type]
            session_id = db.ensure_session(title="Hedi Slimane")
            db.add_message(session_id, "user", "Quiero vestirme como la estetica de Hedi Slimane.")
            db.add_message(
                session_id,
                "assistant",
                (
                    "Faltan pantalon sastre negro slim, camiseta basica blanca y "
                    "botines Chelsea negros para completar la chaqueta biker."
                ),
            )

            context = await tools.prepare("Arma un plan y busca en internet", session_id=session_id)
            names = [result.name for result in context.results]
            product = next(result for result in context.results if result.name == "product_search")

            self.assertIn("web_search", names)
            self.assertIn("product_search", names)
            self.assertNotIn("Arma un plan", product.payload["query"])
            self.assertIn("Hedi Slimane", product.payload["query"])
            self.assertIn("pantalon sastre negro slim", product.payload["query"])
            self.assertIn("Zara", product.payload["query"])
            self.assertTrue(any("Hedi Slimane" in query for query in fake_search.search_queries))

    async def test_prepare_offers_style_questionnaire_only_when_profile_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, db, _, profile = _services(tmpdir)
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]

            context = await tools.prepare(
                "Mina, eres una experta asistente de moda, maquillaje, ropa y perfumeria. Hazme preguntas."
            )
            questionnaire = next(result for result in context.results if result.name == "style_profile_questionnaire")
            self.assertEqual(questionnaire.status, "needs_input")
            self.assertIn("gender_identity", questionnaire.payload["missing_fields"])
            self.assertGreaterEqual(len(questionnaire.payload["questions"]), 5)

            profile.update_profile(
                {
                    "gender_identity": "Mujer",
                    "age_range": "25-34",
                    "style_keywords": "minimalista",
                    "primary_occasion": "salidas social",
                    "style_focus": "todo look completo",
                }
            )
            context = await tools.prepare(
                "Mina, eres una experta asistente de moda, maquillaje, ropa y perfumeria. Hazme preguntas."
            )
            self.assertNotIn("style_profile_questionnaire", [result.name for result in context.results])

    async def test_prepare_offers_shopping_questionnaire_as_interactive_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, db, _, profile = _services(tmpdir)
            profile.update_profile(
                {
                    "gender_identity": "Mujer",
                    "age_range": "25-34",
                    "style_keywords": "Hedi Slimane",
                    "primary_occasion": "salidas social",
                    "style_focus": "outfits y ropa",
                }
            )
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]

            context = await tools.prepare("Haz un cuestionario dinamico para seleccionar usando el backend")
            questionnaire = next(result for result in context.results if result.name == "shopping_questionnaire")

            self.assertNotIn("style_profile_questionnaire", [result.name for result in context.results])
            self.assertEqual(questionnaire.status, "needs_input")
            self.assertEqual(questionnaire.payload["ui_schema"], "shopping_questionnaire.v1")
            self.assertGreaterEqual(len(questionnaire.payload["questions"]), 5)
            self.assertIn("context_hint", questionnaire.payload)

    async def test_orchestrator_short_circuits_llm_for_interactive_questionnaire(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings, db, memory, profile = _services(tmpdir)
            llm = FakeLLM()
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]
            orchestrator = AssistantOrchestrator(
                settings=settings,
                db=db,
                llm=llm,  # type: ignore[arg-type]
                memory=memory,
                chat_tools=tools,
            )

            result = await orchestrator.chat("Hazme un cuestionario dinamico", model="fake-model")

            self.assertEqual(llm.calls, 0)
            self.assertIn("cuestionario interactivo", result.content)
            self.assertNotIn("a)", result.content)
            events = db.list_assistant_events(limit=5)
            self.assertTrue(any(event["event_type"] == "chat_tool_context" for event in events))

    async def test_orchestrator_short_circuits_llm_for_shopping_questionnaire(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings, db, memory, profile = _services(tmpdir)
            llm = FakeLLM()
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]
            orchestrator = AssistantOrchestrator(
                settings=settings,
                db=db,
                llm=llm,  # type: ignore[arg-type]
                memory=memory,
                chat_tools=tools,
            )

            result = await orchestrator.chat("Haz un cuestionario dinamico para seleccionar usando el backend", model="fake-model")

            self.assertEqual(llm.calls, 0)
            self.assertIn("selector interactivo", result.content)
            self.assertNotIn("A -", result.content)
            events = db.list_assistant_events(limit=5)
            payloads = [event["payload"] for event in events if event["event_type"] == "chat_tool_context"]
            self.assertTrue(any(tool["name"] == "shopping_questionnaire" for payload in payloads for tool in payload["tools"]))

    async def test_orchestrator_injects_chat_tool_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings, db, memory, profile = _services(tmpdir)
            llm = FakeLLM()
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]
            orchestrator = AssistantOrchestrator(
                settings=settings,
                db=db,
                llm=llm,  # type: ignore[arg-type]
                memory=memory,
                chat_tools=tools,
            )

            result = await orchestrator.chat("Conoces este perfume?", model="fake-model")

            self.assertIn("Internal Mina tool context", llm.messages[0]["content"])
            self.assertIn("[1] Perfume review", llm.messages[0]["content"])
            self.assertIn("Quieres que guarde", result.content)
            events = db.list_assistant_events(limit=5)
            self.assertTrue(any(event["event_type"] == "chat_tool_context" for event in events))

    async def test_orchestrator_applies_pending_preference_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings, db, memory, profile = _services(tmpdir)
            llm = FakeLLM()
            tools = ChatToolService(db=db, profile=profile, web_search=FakeWebSearch())  # type: ignore[arg-type]
            orchestrator = AssistantOrchestrator(
                settings=settings,
                db=db,
                llm=llm,  # type: ignore[arg-type]
                memory=memory,
                chat_tools=tools,
            )

            first = await orchestrator.chat("Mina, que perfumes son ricos con olor a frambuesa?", model="fake-model")
            pending = db.latest_pending_action(first.session_id)
            self.assertIsNotNone(pending)
            self.assertIn("Quieres que guarde esta preferencia", first.content)

            second = await orchestrator.chat("si, guardalo", session_id=first.session_id, model="fake-model")

            self.assertIn("Listo, lo guarde en memoria", second.content)
            self.assertIsNone(db.latest_pending_action(first.session_id))
            memories = db.list_memory_items(kind="fashion_preference")
            self.assertEqual(len(memories), 1)
            self.assertIn("frambuesa", memories[0]["value"])
            events = db.list_assistant_events(limit=10)
            self.assertTrue(any(event["event_type"] == "pending_action_applied" for event in events))

            await orchestrator.chat("Que perfumes deberia mirar despues?", session_id=first.session_id, model="fake-model")
            self.assertIn("fashion_preference", llm.messages[0]["content"])
            self.assertIn("frambuesa", llm.messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
