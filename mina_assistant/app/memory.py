from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from mina_assistant.app.db import SQLiteStore


MEMORY_KINDS = {
    "user_model",
    "project_model",
    "episodic_event",
    "relationship_signal",
    "personality_profile",
    "self_model",
    "fashion_preference",
    "wardrobe_model",
    "style_reference",
    "media_memory",
}


@dataclass(frozen=True)
class CapturedMemory:
    item: dict[str, Any]
    fact: str


class MemoryService:
    def __init__(self, db: SQLiteStore):
        self.db = db

    def create_item(
        self,
        *,
        kind: str,
        key: str,
        value: str,
        confidence: float = 0.7,
        source: str | None = None,
        source_id: str | None = None,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        _validate_kind(kind)
        normalized_key = _normalize_key(key)
        if not normalized_key:
            raise ValueError("La clave de memoria no puede estar vacia.")
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("El valor de memoria no puede estar vacio.")

        return self.db.upsert_memory_item(
            kind=kind,
            key=normalized_key,
            value=normalized_value,
            confidence=_bounded_confidence(confidence),
            source=source,
            source_id=source_id,
            overwrite=overwrite,
        )

    def update_item(
        self,
        item_id: int,
        *,
        kind: str | None = None,
        key: str | None = None,
        value: str | None = None,
        confidence: float | None = None,
        source: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any] | None:
        if kind is not None:
            _validate_kind(kind)
        next_key = _normalize_key(key) if key is not None else None
        next_value = value.strip() if value is not None else None
        if key is not None and not next_key:
            raise ValueError("La clave de memoria no puede estar vacia.")
        if value is not None and not next_value:
            raise ValueError("El valor de memoria no puede estar vacio.")

        return self.db.update_memory_item(
            item_id,
            kind=kind,
            key=next_key,
            value=next_value,
            confidence=_bounded_confidence(confidence) if confidence is not None else None,
            source=source,
            source_id=source_id,
        )

    def delete_item(self, item_id: int) -> bool:
        return self.db.delete_memory_item(item_id)

    def list_items(
        self,
        *,
        kind: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if kind is not None:
            _validate_kind(kind)
        return self.db.list_memory_items(kind=kind, include_deleted=include_deleted, limit=limit)

    def context_items(self, intent: str, *, limit: int = 12) -> list[dict[str, Any]]:
        kinds = _kinds_for_intent(intent)
        items: list[dict[str, Any]] = []
        for kind in kinds:
            items.extend(self.list_items(kind=kind, limit=max(3, limit)))
        unique: dict[int, dict[str, Any]] = {}
        for item in items:
            unique[int(item["id"])] = item
        return sorted(unique.values(), key=lambda row: str(row["updated_at"]), reverse=True)[:limit]

    def capture_from_user_message(
        self,
        *,
        session_id: str,
        message_id: int,
        content: str,
    ) -> CapturedMemory | None:
        fact = _explicit_memory_fact(content)
        if not fact:
            return None

        kind, key = _classify_fact(fact)
        item = self.create_item(
            kind=kind,
            key=key,
            value=fact,
            confidence=0.95,
            source="message",
            source_id=str(message_id),
        )
        self.db.add_assistant_event(
            session_id=session_id,
            event_type="memory_captured",
            payload={
                "memory_item_id": item["id"],
                "kind": item["kind"],
                "key": item["key"],
                "source_message_id": message_id,
            },
        )
        return CapturedMemory(item=item, fact=fact)

    def record_turn_event(
        self,
        *,
        session_id: str,
        user_message_id: int,
        assistant_message_id: int,
        provider: str,
        model: str,
    ) -> int:
        return self.db.add_assistant_event(
            session_id=session_id,
            event_type="chat_turn",
            payload={
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "provider": provider,
                "model": model,
            },
        )


def _validate_kind(kind: str) -> None:
    if kind not in MEMORY_KINDS:
        raise ValueError(f"Tipo de memoria no soportado: {kind}")


def _bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_key(key: str | None) -> str:
    return normalize_memory_key(key)


def normalize_memory_key(key: str | None) -> str:
    if not key:
        return ""
    normalized = unicodedata.normalize("NFKD", key)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", ".", without_accents.strip().lower())
    return re.sub(r"\.+", ".", slug).strip(".")


def _explicit_memory_fact(content: str) -> str | None:
    patterns = [
        r"\brecuerda que\s+(.+)$",
        r"\bremember that\s+(.+)$",
        r"\brecuerda:\s*(.+)$",
        r"\bremember:\s*(.+)$",
    ]
    normalized = re.sub(r"\s+", " ", content).strip()
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
    return None


def _classify_fact(fact: str) -> tuple[str, str]:
    return classify_memory_fact(fact)


def classify_memory_fact(fact: str) -> tuple[str, str]:
    text = _plain(fact)
    slug = normalize_memory_key(fact)[:80] or "note"

    if _contains_any(text, RESPONSE_STYLE_KEYWORDS):
        return "relationship_signal", f"interaction.style.{slug}"
    if _contains_any(text, SELF_MODEL_KEYWORDS):
        return "self_model", f"mina.self.{slug}"
    if _contains_any(text, MINA_PERSONALITY_KEYWORDS):
        return "personality_profile", f"mina.personality.{slug}"
    if _contains_any(text, MEDIA_KEYWORDS) and _contains_any(text, FASHION_KEYWORDS):
        return "media_memory", f"fashion.media.{slug}"
    if _contains_any(text, STYLE_REFERENCE_KEYWORDS):
        return "style_reference", f"fashion.references.{slug}"
    if _contains_any(text, WARDROBE_KEYWORDS) and _contains_any(text, FASHION_KEYWORDS):
        return "wardrobe_model", f"wardrobe.items.{slug}"
    if _contains_any(text, FASHION_KEYWORDS):
        return "fashion_preference", f"fashion.preferences.{slug}"
    if text.startswith(("prefiero ", "i prefer ", "me gusta ", "i like ")):
        return "user_model", f"preferences.{slug}"
    if text.startswith(("soy ", "i am ", "mi profesion ", "my profession ")):
        return "user_model", f"identity.{slug}"
    if "proyecto" in text or "project" in text or "hito" in text:
        return "project_model", f"mina.{slug}"
    if "tono" in text or "tone" in text or "hablame" in text or "style" in text:
        return "relationship_signal", f"style.{slug}"
    return "user_model", f"notes.{slug}"


def _kinds_for_intent(intent: str) -> list[str]:
    if intent == "fashion_context":
        return [
            "wardrobe_model",
            "fashion_preference",
            "style_reference",
            "media_memory",
            "user_model",
            "relationship_signal",
            "episodic_event",
        ]
    if intent == "personality_context":
        return ["personality_profile", "self_model", "relationship_signal", "user_model", "episodic_event"]
    if intent == "personal_context":
        return [
            "user_model",
            "relationship_signal",
            "personality_profile",
            "self_model",
            "fashion_preference",
            "wardrobe_model",
            "episodic_event",
        ]
    if intent == "project_context" or intent == "task_or_next_action":
        return ["project_model", "episodic_event", "user_model", "relationship_signal"]
    if intent == "memory_query":
        return sorted(MEMORY_KINDS)
    if intent == "voice_or_tts":
        return ["personality_profile", "self_model", "relationship_signal", "user_model"]
    return [
        "user_model",
        "relationship_signal",
        "personality_profile",
        "self_model",
        "fashion_preference",
        "wardrobe_model",
        "style_reference",
        "media_memory",
        "episodic_event",
        "project_model",
    ]


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


FASHION_KEYWORDS = (
    "moda",
    "fashion",
    "estilo",
    "style",
    "outfit",
    "look",
    "ropa",
    "clothing",
    "guardarropa",
    "wardrobe",
    "closet",
    "armario",
    "pantalon",
    "pantalones",
    "pants",
    "jeans",
    "chaqueta",
    "jacket",
    "camisa",
    "shirt",
    "falda",
    "skirt",
    "vestido",
    "dress",
    "sneakers",
    "zapatos",
    "shoes",
    "botas",
    "boots",
    "silueta",
    "silhouette",
    "aesthetic",
    "estetica",
    "perfume",
    "perfumes",
    "fragancia",
    "fragrance",
    "gourmand",
    "amaderado",
    "woody",
)

WARDROBE_KEYWORDS = (
    "tengo ",
    "uso ",
    "mi guardarropa",
    "mi closet",
    "mi armario",
    "mis ",
    "my wardrobe",
    "my closet",
    "i own ",
    "i have ",
    "i wear ",
)

STYLE_REFERENCE_KEYWORDS = (
    "referencia",
    "references",
    "inspiracion",
    "inspiration",
    "moodboard",
    "lookbook",
    "pinterest",
    "disenador",
    "designer",
    "marca",
    "brand",
    "chaewon",
    "jennie",
    "le sserafim",
)

MEDIA_KEYWORDS = (
    "imagen",
    "image",
    "foto",
    "photo",
    "screenshot",
    "captura",
    "media",
    "video",
)

RESPONSE_STYLE_KEYWORDS = (
    "hablame",
    "respondeme",
    "responde",
    "como me respondes",
    "como quiero que respondas",
    "tono",
    "tone",
    "formalidad",
    "formality",
    "humor",
    "playfulness",
    "proactividad",
    "proactive",
    "iniciativa",
    "initiative",
    "estilo de respuesta",
    "communication style",
)

MINA_PERSONALITY_KEYWORDS = (
    "personalidad de mina",
    "mina personality",
    "core personality",
    "personalidad base",
    "rasgos de mina",
    "mina traits",
    "mina debe ser",
    "mina should be",
    "valores de mina",
    "mina values",
)

SELF_MODEL_KEYWORDS = (
    "self model",
    "autoimagen",
    "modelo de si misma",
    "modelo de ella misma",
    "rol de mina",
    "mina role",
    "proposito de mina",
    "mina purpose",
    "limitaciones de mina",
    "mina limitations",
    "fortalezas de mina",
    "mina strengths",
)
