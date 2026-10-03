from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

from mina_assistant.app.config import Settings
from mina_assistant.app.db import SQLiteStore


class SemanticMemoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SemanticStatus:
    enabled: bool
    available: bool
    collection: str
    qdrant_url: str
    embedding_model: str
    detail: str | None = None


@dataclass(frozen=True)
class SemanticSearchResult:
    score: float
    memory_item: dict[str, Any] | None
    payload: dict[str, Any]


class SemanticMemoryService:
    def __init__(self, settings: Settings, db: SQLiteStore):
        self.settings = settings
        self.db = db

    async def status(self) -> SemanticStatus:
        if not self.settings.semantic_memory_enabled:
            return SemanticStatus(
                enabled=False,
                available=False,
                collection=self.settings.qdrant_collection,
                qdrant_url=self.settings.qdrant_base_url,
                embedding_model=self.settings.ollama_embed_model,
                detail="Semantic memory is disabled.",
            )

        try:
            async with self._client() as client:
                response = await client.get("/")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return SemanticStatus(
                enabled=True,
                available=False,
                collection=self.settings.qdrant_collection,
                qdrant_url=self.settings.qdrant_base_url,
                embedding_model=self.settings.ollama_embed_model,
                detail=f"Qdrant is not reachable: {exc}",
            )

        return SemanticStatus(
            enabled=True,
            available=True,
            collection=self.settings.qdrant_collection,
            qdrant_url=self.settings.qdrant_base_url,
            embedding_model=self.settings.ollama_embed_model,
        )

    async def index_memory_items(self, *, kind: str | None = None, limit: int = 500) -> dict[str, Any]:
        self._ensure_enabled()
        await self.ensure_collection()
        items = self.db.list_memory_items(kind=kind, limit=limit)
        indexed = 0
        skipped = 0

        for item in items:
            try:
                await self.upsert_memory_item(item)
                indexed += 1
            except SemanticMemoryError:
                skipped += 1

        return {
            "indexed": indexed,
            "skipped": skipped,
            "collection": self.settings.qdrant_collection,
        }

    async def upsert_memory_item(self, item: dict[str, Any]) -> None:
        self._ensure_enabled()
        await self.ensure_collection()
        text = memory_item_text(item)
        vector = await self.embed(text)
        point = {
            "id": _point_id(item),
            "vector": vector,
            "payload": {
                "source": "memory_item",
                "memory_item_id": int(item["id"]),
                "kind": item["kind"],
                "key": item["key"],
                "value": item["value"],
                "confidence": item["confidence"],
                "updated_at": item["updated_at"],
                "text": text,
            },
        }
        try:
            async with self._client() as client:
                response = await client.put(
                    f"/collections/{self.settings.qdrant_collection}/points",
                    json={"points": [point]},
                )
        except httpx.HTTPError as exc:
            raise SemanticMemoryError(f"Could not upsert Qdrant point: {exc}") from exc

        if response.status_code >= 400:
            raise SemanticMemoryError(f"Could not upsert Qdrant point: {response.text[:500]}")

    async def search(self, query: str, *, limit: int = 8) -> list[SemanticSearchResult]:
        self._ensure_enabled()
        normalized_query = " ".join(query.split()).strip()
        if not normalized_query:
            return []

        try:
            async with self._client() as client:
                collection_response = await client.get(
                    f"/collections/{self.settings.qdrant_collection}"
                )
                if collection_response.status_code == 404:
                    return []
                if collection_response.status_code >= 400:
                    raise SemanticMemoryError(
                        f"Could not inspect Qdrant collection: {collection_response.text[:500]}"
                    )

            vector = await self.embed(normalized_query)
            async with self._client() as client:
                response = await client.post(
                    f"/collections/{self.settings.qdrant_collection}/points/search",
                    json={
                        "vector": vector,
                        "limit": limit,
                        "with_payload": True,
                    },
                )
        except httpx.HTTPError as exc:
            raise SemanticMemoryError(f"Could not search Qdrant: {exc}") from exc

        if response.status_code == 404:
            return []
        if response.status_code >= 400:
            raise SemanticMemoryError(f"Could not search Qdrant: {response.text[:500]}")
        rows = response.json().get("result") or []

        results: list[SemanticSearchResult] = []
        for row in rows:
            payload = row.get("payload") or {}
            item_id = payload.get("memory_item_id")
            item = self.db.get_memory_item(int(item_id)) if item_id is not None else None
            results.append(
                SemanticSearchResult(
                    score=float(row.get("score") or 0.0),
                    memory_item=item,
                    payload=payload,
                )
            )
        return results

    async def delete_memory_item(self, item_id: int) -> None:
        self._ensure_enabled()
        try:
            async with self._client() as client:
                response = await client.post(
                    f"/collections/{self.settings.qdrant_collection}/points/delete",
                    json={
                        "points": [_point_id({"id": item_id})],
                    },
                )
        except httpx.HTTPError as exc:
            raise SemanticMemoryError(f"Could not delete Qdrant point: {exc}") from exc

        if response.status_code == 404:
            return
        if response.status_code >= 400:
            raise SemanticMemoryError(f"Could not delete Qdrant point: {response.text[:500]}")

    async def ensure_collection(self) -> None:
        self._ensure_enabled()
        try:
            async with self._client() as client:
                response = await client.get(f"/collections/{self.settings.qdrant_collection}")
                if response.status_code == 200:
                    return
                if response.status_code != 404:
                    raise SemanticMemoryError(
                        f"Could not inspect Qdrant collection: {response.text[:500]}"
                    )

                create_response = await client.put(
                    f"/collections/{self.settings.qdrant_collection}",
                    json={
                        "vectors": {
                            "size": self.settings.qdrant_vector_size,
                            "distance": "Cosine",
                        }
                    },
                )
        except httpx.HTTPError as exc:
            raise SemanticMemoryError(f"Could not connect to Qdrant: {exc}") from exc

        if create_response.status_code >= 400:
            raise SemanticMemoryError(
                f"Could not create Qdrant collection: {create_response.text[:500]}"
            )

    async def embed(self, text: str) -> list[float]:
        normalized_text = " ".join(text.split()).strip()
        if not normalized_text:
            raise SemanticMemoryError("Cannot embed empty text.")

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/embeddings",
                    json={
                        "model": self.settings.ollama_embed_model,
                        "prompt": normalized_text,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SemanticMemoryError(f"Could not create embedding with Ollama: {exc}") from exc

        embedding = response.json().get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise SemanticMemoryError("Ollama returned an invalid embedding.")
        return [float(value) for value in embedding]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.qdrant_base_url,
            timeout=self.settings.qdrant_timeout_seconds,
        )

    def _ensure_enabled(self) -> None:
        if not self.settings.semantic_memory_enabled:
            raise SemanticMemoryError("Semantic memory is disabled.")


def memory_item_text(item: dict[str, Any]) -> str:
    return (
        f"kind: {item.get('kind')}\n"
        f"key: {item.get('key')}\n"
        f"value: {item.get('value')}\n"
        f"confidence: {item.get('confidence')}"
    )


def _point_id(item: dict[str, Any]) -> str:
    raw = f"memory_item:{item['id']}".encode("utf-8")
    digest = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
