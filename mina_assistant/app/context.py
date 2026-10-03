from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mina_assistant.app.config import Settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.intent import IntentClassifier, IntentResult
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.profile import PERSONALIZATION_POLICY, ProfileService
from mina_assistant.app.semantic import SemanticMemoryError, SemanticMemoryService


RESPONSE_POLICY = """Mina response policy:
- Do not use generic AI disclaimers about lacking smell, taste, feelings, body, senses, or personal experience.
- If the user asks for Mina's preference, pick one based on evidence, saved preferences, notes, use case, and sources.
- For fashion, beauty, perfume, and shopping, act as a curator: rank options, explain why, mention when/for whom each fits, and give a useful next step.
- Do not invent prices, availability, stores, or saved user preferences.
- For product or web research, never pass a vague user instruction as the query. Use concrete fashion/product terms from the current request and recent context.
- Do not generate literal questionnaires with letter choices when Mina has provided or should provide an interactive questionnaire card.
"""


@dataclass(frozen=True)
class ContextPackage:
    intent: IntentResult
    system_context: str
    memory_items: list[dict[str, Any]]
    semantic_items: list[dict[str, Any]]
    messages: list[dict[str, str]]


class ContextBuilder:
    def __init__(
        self,
        *,
        settings: Settings,
        db: SQLiteStore,
        memory: MemoryService,
        intent_classifier: IntentClassifier,
        semantic_memory: SemanticMemoryService | None = None,
    ):
        self.settings = settings
        self.db = db
        self.memory = memory
        self.intent_classifier = intent_classifier
        self.semantic_memory = semantic_memory
        self.profile = ProfileService(db=db, memory=memory)

    async def build(self, *, session_id: str | None, content: str = "") -> ContextPackage:
        intent = self.intent_classifier.classify(content)
        memory_items = self.memory.context_items(intent.name)
        semantic_items = await self._semantic_items(content)
        user_items = self.profile.user_context_items()
        identity = self.profile.current_identity_memory()
        if identity:
            user_items = [identity, *[item for item in user_items if item["id"] != identity["id"]]]
            # Suppress an older canonical identity rather than send contradictory facts to the model.
            memory_items = [item for item in memory_items if (
                item["key"] != "profile.gender_identity" or item["id"] == identity["id"]
            )]
            semantic_items = [item for item in semantic_items if (
                item["key"] != "profile.gender_identity" or item["id"] == identity["id"]
            )]
        context_items = _merge_memory_items(
            memory_items + user_items, semantic_items,
            priority_ids={int(item["id"]) for item in user_items},
        )
        system_context = self._system_context(context_items)
        recent_messages = (
            self.db.get_recent_messages(session_id, limit=self.settings.recent_turn_limit)
            if session_id
            else []
        )

        messages = [{"role": "system", "content": system_context}]
        messages.extend(
            {"role": row["role"], "content": row["content"]}
            for row in recent_messages
            if row["role"] in {"user", "assistant"}
        )

        normalized_content = content.strip()
        if normalized_content and (
            not recent_messages or str(recent_messages[-1]["content"]).strip() != normalized_content
        ):
            messages.append({"role": "user", "content": normalized_content})

        return ContextPackage(
            intent=intent,
            system_context=system_context,
            memory_items=context_items,
            semantic_items=semantic_items,
            messages=messages,
        )

    def _system_context(self, memory_items: list[dict[str, Any]]) -> str:
        base_prompt = (
            f"{self.settings.system_prompt.strip()}\n\n{RESPONSE_POLICY.strip()}\n\n"
            f"{PERSONALIZATION_POLICY.strip()}"
        )
        if not memory_items:
            return base_prompt

        memory_lines = [_memory_line(item) for item in memory_items]
        memory_block = "\n".join(f"- {line}" for line in memory_lines)
        return (
            f"{base_prompt}\n\n"
            "Relevant structured context:\n"
            f"{memory_block}\n\n"
            "Use this context only when it is relevant to the user's request. "
            "Do not claim certainty beyond the confidence of the memory item. "
            "If a memory conflicts with the current message, prefer the current message. "
            "For conflicting saved facts, prefer the latest explicit user correction by updated_at; "
            "assistant history and image-derived suggestions do not override it."
        )

    async def _semantic_items(self, content: str) -> list[dict[str, Any]]:
        if not self.semantic_memory or not content.strip():
            return []

        try:
            results = await self.semantic_memory.search(content, limit=6)
        except SemanticMemoryError:
            return []

        items: list[dict[str, Any]] = []
        for result in results:
            if not result.memory_item:
                continue
            item = dict(result.memory_item)
            item["semantic_score"] = result.score
            items.append(item)
        return items


def _memory_line(item: dict[str, Any]) -> str:
    confidence = float(item.get("confidence") or 0.0)
    value = _compact(str(item.get("value") or ""))
    if item.get("identity"):
        value = f"Current explicitly stated gender identity: {item['identity']}; {value}"
    source = item.get("source")
    source_id = item.get("source_id")
    source_text = f"; source={source}:{source_id}" if source and source_id else ""
    if source and not source_id:
        source_text = f"; source={source}"
    updated_text = f"; updated_at={item['updated_at']}" if item.get("updated_at") else ""
    semantic_score = item.get("semantic_score")
    semantic_text = f"; semantic_score={float(semantic_score):.3f}" if semantic_score is not None else ""
    return (
        f"{item.get('kind')}.{item.get('key')}: {value} "
        f"(confidence={confidence:.2f}{source_text}{updated_text}{semantic_text})"
    )


def _merge_memory_items(
    structured_items: list[dict[str, Any]],
    semantic_items: list[dict[str, Any]],
    *,
    priority_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for item in semantic_items + structured_items:
        item_id = int(item["id"])
        current = merged.get(item_id, {})
        merged[item_id] = {**current, **item}
    return sorted(
        merged.values(),
        key=lambda row: (
            int(row["id"]) in (priority_ids or set()),
            float(row.get("semantic_score") or 0.0),
            str(row.get("updated_at") or ""), int(row["id"]),
        ),
        reverse=True,
    )[:16]


def _compact(value: str, *, limit: int = 420) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."
