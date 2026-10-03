from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.memory import MemoryService


@dataclass(frozen=True)
class ProfileField:
    kind: str
    key: str
    label: str


PROFILE_FIELDS: dict[str, ProfileField] = {
    "display_name": ProfileField("user_model", "profile.display_name", "Preferred name"),
    "gender_identity": ProfileField("user_model", "profile.gender_identity", "Style gender identity"),
    "age_range": ProfileField("user_model", "profile.age_range", "Age range"),
    "city": ProfileField("user_model", "profile.city", "Base city or climate"),
    "height": ProfileField("user_model", "profile.height", "Height"),
    "body_notes": ProfileField("user_model", "profile.body_notes", "Body or proportion notes"),
    "size_tops": ProfileField("user_model", "profile.size_tops", "Top size"),
    "size_bottoms": ProfileField("user_model", "profile.size_bottoms", "Bottom size"),
    "size_shoes": ProfileField("user_model", "profile.size_shoes", "Shoe size"),
    "fit_preferences": ProfileField("fashion_preference", "profile.fit_preferences", "Fit preferences"),
    "favorite_colors": ProfileField("fashion_preference", "profile.favorite_colors", "Favorite colors"),
    "avoided_colors": ProfileField("fashion_preference", "profile.avoided_colors", "Avoided colors"),
    "style_keywords": ProfileField("fashion_preference", "profile.style_keywords", "Style keywords"),
    "primary_occasion": ProfileField("fashion_preference", "profile.primary_occasion", "Primary style occasion"),
    "style_focus": ProfileField("fashion_preference", "profile.style_focus", "Style focus"),
    "comfort_notes": ProfileField("fashion_preference", "profile.comfort_notes", "Comfort constraints"),
    "budget_notes": ProfileField("fashion_preference", "profile.budget_notes", "Budget or brand notes"),
    "privacy_notes": ProfileField("relationship_signal", "profile.privacy_notes", "Privacy preferences"),
}


PERSONALIZATION_POLICY = """Personalization rules:
- The current request and the latest explicit user corrections take precedence over older profile fields, assistant replies, inferred preferences, and image analysis. Confidence scores do not override an explicit correction.
- Respect the user's stated clothing preferences. Gender identity and clothing preferences are separate; do not infer either from aesthetics, perfume, makeup, or people in reference images.
- A romantic or delicate aesthetic does not imply womenswear. If the user explicitly prefers men's clothing, build the outfit in that clothing direction unless the current request asks otherwise.
- Reference images and previous assistant outfit suggestions are not evidence of the user's identity, preferences, or ownership. Only claim an item is owned when it is in the saved wardrobe.
"""

USER_MEMORY_SOURCES = [None, "desktop", "api", "message", "chat_confirmation"]


class ProfileService:
    def __init__(self, *, db: SQLiteStore, memory: MemoryService):
        self.db = db
        self.memory = memory

    def get_profile(self) -> dict[str, Any]:
        items = self.db.list_memory_items(
            keys=[field.key for field in PROFILE_FIELDS.values()],
            limit=None,
        )
        by_key = {(item["kind"], item["key"]): item for item in items}
        profile: dict[str, Any] = {field_id: "" for field_id in PROFILE_FIELDS}
        updated_at: str | None = None

        for field_id, field in PROFILE_FIELDS.items():
            item = by_key.get((field.kind, field.key))
            if not item:
                continue
            profile[field_id] = _strip_label(str(item["value"]), field.label)
            item_updated_at = str(item["updated_at"])
            if updated_at is None or item_updated_at > updated_at:
                updated_at = item_updated_at

        identity = self.current_identity_memory()
        if identity:
            profile["gender_identity"] = identity["identity"]
            updated_at = max(updated_at or "", str(identity["updated_at"]))
        profile["updated_at"] = updated_at
        return profile

    def user_context_items(self, *, limit: int = 12) -> list[dict[str, Any]]:
        items = self.db.list_memory_items(
            kinds=["user_model", "fashion_preference", "relationship_signal"],
            sources=USER_MEMORY_SOURCES,
            limit=limit + len(PROFILE_FIELDS),
        )
        return [item for item in items if not item["key"].startswith("profile.")][:limit]

    def current_identity_memory(self) -> dict[str, Any] | None:
        # Read-only reconciliation: keep the original memories editable and reversible.
        candidates = self.db.list_memory_items(
            kinds=["user_model", "fashion_preference", "relationship_signal"],
            sources=USER_MEMORY_SOURCES + ["profile"], limit=None,
        )
        field = PROFILE_FIELDS["gender_identity"]
        for item in candidates:  # newest first, with id as a deterministic tie-breaker
            if item["key"] == field.key and item["kind"] == field.kind:
                identity = _strip_label(item["value"], field.label)
            else:
                identity = _explicit_gender_identity(item["value"])
            if identity:
                return {**item, "identity": identity}
        return None

    def user_context_block(self) -> str:
        lines = [
            f"- {str(item['value'])[:600]} (updated_at={item['updated_at']}; source={item.get('source') or 'manual'})"
            for item in self.user_context_items()
        ]
        if not lines:
            return "No additional user-authored notes."
        return "User-authored notes and explicitly saved preferences (newest first):\n" + "\n".join(lines)

    def update_profile(self, values: dict[str, Any]) -> dict[str, Any]:
        for field_id, raw_value in values.items():
            field = PROFILE_FIELDS.get(field_id)
            if not field:
                continue
            value = str(raw_value or "").strip()
            if value:
                self.memory.create_item(
                    kind=field.kind,
                    key=field.key,
                    value=f"{field.label}: {value}",
                    confidence=0.95,
                    source="profile",
                    source_id=field_id,
                )
            else:
                self.db.delete_memory_item_by_kind_key(kind=field.kind, key=field.key)

        return self.get_profile()


def _strip_label(value: str, label: str) -> str:
    prefix = f"{label}:"
    if value.startswith(prefix):
        return value.removeprefix(prefix).strip()
    return value.strip()


def _explicit_gender_identity(value: str) -> str | None:
    # Match direct first-person declarations only, never clothing choices or visual guesses.
    text = unicodedata.normalize("NFKD", value.lower().replace("’", "'"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    identities = {
        "hombre": "Hombre", "man": "Hombre", "men": "Hombre", "male": "Hombre",
        "mujer": "Mujer", "woman": "Mujer", "female": "Mujer",
        "no binario": "No binario", "no binaria": "No binario",
        "nonbinary": "No binario", "non-binary": "No binario", "non binary": "No binario",
    }
    identity = None
    for sentence in re.split(r"[.!?;,\n]+", text):
        match = re.fullmatch(
            r"\s*(?:(?:yo\s+)?soy\s+(?:un\s+|una\s+|una persona\s+)?|"
            r"(?:i am|i'm|i im)\s+(?:a\s+|an\s+)?)(" + "|".join(identities) + r")\s*",
            sentence,
        )
        if match:
            identity = identities[match.group(1)]
    return identity
