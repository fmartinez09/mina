from __future__ import annotations

from typing import Any

from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.memory import MemoryService, normalize_memory_key


class WardrobeService:
    def __init__(self, *, db: SQLiteStore, memory: MemoryService):
        self.db = db
        self.memory = memory

    def list_items(
        self,
        *,
        category: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.db.list_wardrobe_items(category=_clean_optional(category), query=_clean_optional(query), limit=limit)

    def create_item(self, **values: Any) -> dict[str, Any]:
        item = self.db.create_wardrobe_item(**_normalize_item_values(values, require_name=True))
        self.sync_memory(item)
        return item

    def update_item(self, item_id: int, **values: Any) -> dict[str, Any] | None:
        item = self.db.update_wardrobe_item(item_id, **_normalize_item_values(values, require_name=False))
        if item:
            self.sync_memory(item)
        return item

    def delete_item(self, item_id: int) -> bool:
        deleted = self.db.delete_wardrobe_item(item_id)
        if deleted:
            self.db.delete_memory_items_by_source(source="wardrobe", source_id=str(item_id))
        return deleted

    def sync_memory(self, item: dict[str, Any]) -> dict[str, Any]:
        item_id = int(item["id"])
        return self.memory.create_item(
            kind="wardrobe_model",
            key=f"wardrobe.items.{item_id}",
            value=_wardrobe_memory_value(item),
            confidence=0.92,
            source="wardrobe",
            source_id=str(item_id),
        )


def _normalize_item_values(values: dict[str, Any], *, require_name: bool) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if key in {"colors", "occasions", "style_tags"}:
            normalized[key] = _clean_list(value)
        elif key == "favorite":
            normalized[key] = bool(value)
        else:
            normalized[key] = _clean_optional(value)

    if require_name:
        if not normalized.get("name"):
            raise ValueError("El nombre de la prenda no puede estar vacio.")
        if not normalized.get("category"):
            raise ValueError("La categoria de la prenda no puede estar vacia.")
    elif "name" in normalized and not normalized["name"]:
        raise ValueError("El nombre de la prenda no puede estar vacio.")
    elif "category" in normalized and not normalized["category"]:
        raise ValueError("La categoria de la prenda no puede estar vacia.")

    return normalized


def _clean_optional(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.replace("\n", ",").split(",")
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    seen: set[str] = set()
    result: list[str] = []
    for item in raw:
        cleaned = str(item).strip()
        slug = normalize_memory_key(cleaned)
        if not cleaned or slug in seen:
            continue
        seen.add(slug)
        result.append(cleaned)
    return result


def _wardrobe_memory_value(item: dict[str, Any]) -> str:
    parts = [
        f"User owns wardrobe item: {item['name']}",
        f"category={item['category']}",
    ]
    for key, label in (
        ("subcategory", "subcategory"),
        ("brand", "brand"),
        ("size_label", "size"),
        ("fit", "fit"),
        ("material", "material"),
        ("season", "season"),
    ):
        if item.get(key):
            parts.append(f"{label}={item[key]}")
    if item.get("colors"):
        parts.append(f"colors={', '.join(item['colors'])}")
    if item.get("occasions"):
        parts.append(f"occasions={', '.join(item['occasions'])}")
    if item.get("style_tags"):
        parts.append(f"style_tags={', '.join(item['style_tags'])}")
    if item.get("notes"):
        parts.append(f"notes={item['notes']}")
    if item.get("favorite"):
        parts.append("favorite=true")
    return "; ".join(parts) + "."
