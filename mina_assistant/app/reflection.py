from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from mina_assistant.app.config import Settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.llm import LLMError, LLMService
from mina_assistant.app.memory import (
    MEMORY_KINDS,
    MemoryService,
    classify_memory_fact,
    normalize_memory_key,
)


class ReflectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReflectionRunResult:
    candidates: list[dict[str, Any]]
    skipped: int
    provider: str
    model: str
    source: str


@dataclass(frozen=True)
class ReflectionReviewResult:
    candidate: dict[str, Any]
    memory_item: dict[str, Any] | None = None


class ReflectionService:
    def __init__(
        self,
        *,
        settings: Settings,
        db: SQLiteStore,
        llm: LLMService,
        memory: MemoryService,
    ):
        self.settings = settings
        self.db = db
        self.llm = llm
        self.memory = memory

    def list_candidates(
        self,
        *,
        status: str | None = "pending",
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        _validate_status(status) if status else None
        return self.db.list_reflection_candidates(status=status, session_id=session_id, limit=limit)

    async def reflect_session(
        self,
        *,
        session_id: str,
        provider: str | None = None,
        model: str | None = None,
        limit: int | None = None,
    ) -> ReflectionRunResult:
        if not self.settings.reflection_enabled:
            raise ReflectionError("Reflection engine is disabled.")
        if not self.db.session_exists(session_id):
            raise ReflectionError("Sesion no encontrada.")

        max_messages = max(4, min(limit or self.settings.reflection_recent_message_limit, 80))
        messages = [
            row
            for row in self.db.get_recent_messages(session_id, max_messages)
            if row["role"] in {"user", "assistant"} and str(row["content"]).strip()
        ]
        if len(messages) < 2:
            return ReflectionRunResult(
                candidates=[],
                skipped=0,
                provider=provider or self.llm.default_provider(),
                model=model or self.llm.default_model(provider),
                source="llm",
            )

        active_provider = provider or self.llm.default_provider()
        active_model = model or self.llm.default_model(active_provider)
        prompt_messages = _reflection_prompt(messages, max_candidates=self.settings.reflection_max_candidates)

        try:
            response = await self.llm.chat(
                prompt_messages,
                provider=active_provider,
                model=active_model,
                temperature=0.1,
            )
            drafts = _parse_reflection_response(response.content)
        except (LLMError, ReflectionError):
            raise
        except Exception as exc:
            raise ReflectionError(f"Could not parse reflection response: {exc}") from exc

        candidate_rows: list[dict[str, Any]] = []
        skipped = 0
        source_message_ids = [int(row["id"]) for row in messages if row.get("id") is not None]
        existing = {
            _candidate_signature(candidate)
            for candidate in self.db.list_reflection_candidates(session_id=session_id, limit=500)
        }
        seen: set[tuple[str, str, str]] = set()

        for draft in drafts:
            normalized = _normalize_candidate(draft)
            if not normalized:
                skipped += 1
                continue
            if normalized["confidence"] < self.settings.reflection_min_confidence:
                skipped += 1
                continue

            signature = _candidate_signature(normalized)
            if signature in existing or signature in seen:
                skipped += 1
                continue
            seen.add(signature)

            candidate = self.db.create_reflection_candidate(
                session_id=session_id,
                kind=normalized["kind"],
                key=normalized["key"],
                value=normalized["value"],
                confidence=normalized["confidence"],
                rationale=normalized.get("rationale"),
                evidence=normalized.get("evidence"),
                source="llm",
                source_message_ids=source_message_ids,
            )
            candidate_rows.append(candidate)

        self.db.add_assistant_event(
            session_id=session_id,
            event_type="reflection_run",
            payload={
                "created": len(candidate_rows),
                "skipped": skipped,
                "provider": active_provider,
                "model": active_model,
            },
        )
        return ReflectionRunResult(
            candidates=candidate_rows,
            skipped=skipped,
            provider=active_provider,
            model=active_model,
            source="llm",
        )

    def update_candidate(
        self,
        candidate_id: int,
        *,
        kind: str | None = None,
        key: str | None = None,
        value: str | None = None,
        confidence: float | None = None,
        rationale: str | None = None,
        evidence: str | None = None,
    ) -> dict[str, Any]:
        current = self.db.get_reflection_candidate(candidate_id)
        if not current:
            raise ReflectionError("Candidato de memoria no encontrado.")
        if current["status"] != "pending":
            raise ReflectionError("Solo se pueden editar candidatos pendientes.")

        normalized_kind = kind.strip() if kind is not None else None
        if normalized_kind is not None and normalized_kind not in MEMORY_KINDS:
            raise ReflectionError(f"Tipo de memoria no soportado: {normalized_kind}")

        normalized_key = normalize_memory_key(key) if key is not None else None
        if key is not None and not normalized_key:
            raise ReflectionError("La clave de memoria no puede estar vacia.")

        normalized_value = value.strip() if value is not None else None
        if value is not None and not normalized_value:
            raise ReflectionError("El valor de memoria no puede estar vacio.")

        updated = self.db.update_reflection_candidate(
            candidate_id,
            kind=normalized_kind,
            key=normalized_key,
            value=normalized_value,
            confidence=_bounded_confidence(confidence) if confidence is not None else None,
            rationale=_short_text(rationale, 800) if rationale is not None else None,
            evidence=_short_text(evidence, 1200) if evidence is not None else None,
        )
        if not updated:
            raise ReflectionError("No se pudo actualizar el candidato.")
        return updated

    def approve_candidate(self, candidate_id: int) -> ReflectionReviewResult:
        candidate = self.db.get_reflection_candidate(candidate_id)
        if not candidate:
            raise ReflectionError("Candidato de memoria no encontrado.")
        if candidate["status"] != "pending":
            raise ReflectionError("Solo se pueden aprobar candidatos pendientes.")

        memory_item = self.memory.create_item(
            kind=candidate["kind"],
            key=candidate["key"],
            value=candidate["value"],
            confidence=candidate["confidence"],
            source="reflection",
            source_id=str(candidate["id"]),
        )
        reviewed = self.db.review_reflection_candidate(
            candidate_id,
            status="approved",
            memory_item_id=int(memory_item["id"]),
        )
        if not reviewed:
            raise ReflectionError("No se pudo aprobar el candidato.")

        self.db.add_assistant_event(
            session_id=candidate.get("session_id"),
            event_type="reflection_candidate_approved",
            payload={
                "candidate_id": candidate_id,
                "memory_item_id": memory_item["id"],
                "kind": memory_item["kind"],
                "key": memory_item["key"],
            },
        )
        return ReflectionReviewResult(candidate=reviewed, memory_item=memory_item)

    def reject_candidate(self, candidate_id: int) -> dict[str, Any]:
        candidate = self.db.get_reflection_candidate(candidate_id)
        if not candidate:
            raise ReflectionError("Candidato de memoria no encontrado.")
        if candidate["status"] != "pending":
            raise ReflectionError("Solo se pueden rechazar candidatos pendientes.")

        reviewed = self.db.review_reflection_candidate(candidate_id, status="rejected")
        if not reviewed:
            raise ReflectionError("No se pudo rechazar el candidato.")
        self.db.add_assistant_event(
            session_id=candidate.get("session_id"),
            event_type="reflection_candidate_rejected",
            payload={"candidate_id": candidate_id},
        )
        return reviewed


def _reflection_prompt(messages: list[dict[str, Any]], *, max_candidates: int) -> list[dict[str, str]]:
    transcript = [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
        }
        for row in messages
    ]
    memory_kinds = "|".join(sorted(MEMORY_KINDS))
    return [
        {
            "role": "system",
            "content": (
                "You are Mina's reflection engine. Extract durable memory candidates from a chat transcript. "
                "Only include information that will still matter in future conversations. "
                "Do not include generic assistant answers, temporary chit-chat, secrets, or unsupported guesses. "
                "Use user_model for stable user identity and general preferences; relationship_signal for how the user "
                "wants Mina to respond; personality_profile for Mina's stable traits and values; self_model for Mina's "
                "role, purpose, strengths, and limitations; fashion_preference for fashion, perfume, and style tastes; "
                "wardrobe_model for owned clothing or wardrobe inventory; style_reference for visual references, brands, "
                "designers, celebrities, or inspiration; media_memory for image or media-derived observations; "
                "episodic_event for durable events; project_model only for personal projects. "
                "Return valid JSON only with this exact shape: "
                f'{{"candidates":[{{"kind":"{memory_kinds}",'
                '"key":"short.stable.slug","value":"memory text","confidence":0.0,'
                '"rationale":"why this should be remembered","evidence":"short quote or summary"}]}.'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Return at most {max_candidates} memory candidates. "
                "Use English unless the remembered content is a literal user preference or project name.\n\n"
                + json.dumps(transcript, ensure_ascii=False, indent=2)
            ),
        },
    ]


def _parse_reflection_response(content: str) -> list[dict[str, Any]]:
    parsed = _loads_json_object(content)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if not isinstance(parsed, dict):
        raise ReflectionError("Reflection response was not a JSON object.")
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list):
        raise ReflectionError("Reflection response did not include a candidates list.")
    return [item for item in candidates if isinstance(item, dict)]


def _loads_json_object(content: str) -> Any:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start >= 0 and object_end > object_start:
        return json.loads(cleaned[object_start : object_end + 1])

    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    if array_start >= 0 and array_end > array_start:
        return json.loads(cleaned[array_start : array_end + 1])

    raise ReflectionError("Reflection response did not contain JSON.")


def _normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    value = _short_text(candidate.get("value") or candidate.get("memory") or candidate.get("fact"), 4000)
    if not value:
        return None

    raw_kind = str(candidate.get("kind") or "").strip()
    raw_key = str(candidate.get("key") or "").strip()
    if raw_kind not in MEMORY_KINDS or not raw_key:
        classified_kind, classified_key = classify_memory_fact(value)
        raw_kind = raw_kind if raw_kind in MEMORY_KINDS else classified_kind
        raw_key = raw_key or classified_key

    key = normalize_memory_key(raw_key)
    if not key:
        return None

    return {
        "kind": raw_kind,
        "key": key[:160],
        "value": value,
        "confidence": _bounded_confidence(candidate.get("confidence", 0.6)),
        "rationale": _short_text(candidate.get("rationale") or candidate.get("reason"), 800),
        "evidence": _short_text(candidate.get("evidence") or candidate.get("quote"), 1200),
    }


def _candidate_signature(candidate: dict[str, Any]) -> tuple[str, str, str]:
    value = re.sub(r"\s+", " ", str(candidate.get("value") or "")).strip().lower()
    return (str(candidate.get("kind") or ""), str(candidate.get("key") or ""), value)


def _short_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text[:limit]


def _bounded_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.6


def _validate_status(status: str | None) -> None:
    if status not in {"pending", "approved", "rejected"}:
        raise ReflectionError(f"Estado de reflexion no soportado: {status}")
