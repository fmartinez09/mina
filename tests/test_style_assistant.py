from __future__ import annotations

import unittest

from mina_assistant.app.llm import LLMResponse
from mina_assistant.app.style import StyleAssistantService
from mina_assistant.app.web_search import WebSearchResponse, WebSearchResult


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def chat(self, messages, *, provider=None, model=None, temperature=0.4):
        self.calls.append(
            {
                "messages": messages,
                "provider": provider,
                "model": model,
                "temperature": temperature,
            }
        )
        return LLMResponse(content="Brief with source [1].", provider=provider or "openai", model=model or "gpt-test")


class FakeWebSearch:
    async def search(self, query, *, provider=None, limit=None):
        return WebSearchResponse(
            query=query,
            provider=provider or "duckduckgo",
            results=[
                WebSearchResult(
                    title="Winter boots guide",
                    url="https://example.com/boots",
                    snippet="Boots work well in wet cold weather.",
                    source="duckduckgo",
                )
            ],
        )


class StyleAssistantServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_research_brief_passes_sources_to_llm(self) -> None:
        llm = FakeLLM()
        service = StyleAssistantService(db=None, llm=llm, profile=None, web_search=FakeWebSearch())  # type: ignore[arg-type]

        result = await service.research_brief(
            query="best boots for rain",
            provider="openrouter",
            model="openai/gpt-oss-120b:free",
        )

        self.assertEqual(result.provider, "openrouter")
        self.assertEqual(result.model, "openai/gpt-oss-120b:free")
        user_prompt = llm.calls[0]["messages"][1]["content"]
        self.assertIn("[1] Winter boots guide", user_prompt)
        self.assertIn("Do not invent facts", user_prompt)

    async def test_wardrobe_draft_from_json_analysis(self) -> None:
        service = StyleAssistantService(db=None, llm=None, profile=None, web_search=None)  # type: ignore[arg-type]
        draft = service.wardrobe_draft_from_analysis(
            """```json
{
  "name": "Black ankle boots",
  "category": "shoes",
  "subcategory": "ankle boots",
  "colors": ["black", "black", "cream"],
  "material": "leather",
  "occasions": ["rain", "casual"],
  "style_tags": ["minimal"],
  "notes": "Chunky sole, good for wet weather.",
  "confidence": 0.82
}
```""",
            image={"id": 9, "original_name": "boots.png"},
        )

        self.assertEqual(draft["name"], "Black ankle boots")
        self.assertEqual(draft["category"], "shoes")
        self.assertEqual(draft["colors"], ["black", "cream"])
        self.assertEqual(draft["source"], "vision")
        self.assertEqual(draft["source_id"], "9")
        self.assertAlmostEqual(draft["confidence"], 0.82)

    async def test_wardrobe_draft_falls_back_when_json_is_missing(self) -> None:
        service = StyleAssistantService(db=None, llm=None, profile=None, web_search=None)  # type: ignore[arg-type]
        draft = service.wardrobe_draft_from_analysis(
            "Looks like a soft pink blouse with a delicate drape.",
            image={"id": 4, "original_name": "pink-blouse.jpg"},
        )

        self.assertEqual(draft["name"], "pink blouse")
        self.assertEqual(draft["category"], "other")
        self.assertIn("soft pink blouse", draft["notes"])


if __name__ == "__main__":
    unittest.main()
