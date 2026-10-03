from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks, HTTPException

from mina_assistant.app.db import MemoryConflictError, SQLiteStore
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.schemas import MemoryItemCreate, MemoryItemUpdate
from mina_assistant.app.semantic import SemanticMemoryError


class MemoryEditingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from mina_assistant.app import main

        self.main = main
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = SQLiteStore(Path(self.directory.name) / "memory.sqlite")
        self.db.initialize()
        self.memory = MemoryService(self.db)
        self.semantic = SimpleNamespace(
            upsert_memory_item=AsyncMock(), delete_memory_item=AsyncMock(),
        )
        for name, value in (
            ("db", self.db), ("memory_service", self.memory),
            ("semantic_memory_service", self.semantic), ("memory_index_lock", asyncio.Lock()),
        ):
            self.enterContext(patch.object(main, name, value))

    async def create(self, key="notes.style", value="I prefer relaxed outfits", kind="user_model"):
        tasks = BackgroundTasks()
        item = await self.main.create_memory_item(
            MemoryItemCreate(kind=kind, key=key, value=value, source="desktop"), tasks,
        )
        return item, tasks

    async def test_save_and_edit_persist_before_semantic_indexing(self):
        item, create_tasks = await self.create()
        self.assertEqual(self.db.get_memory_item(item["id"])["value"], "I prefer relaxed outfits")
        self.semantic.upsert_memory_item.assert_not_awaited()

        update_tasks = BackgroundTasks()
        updated = await self.main.update_memory_item(
            item["id"], MemoryItemUpdate(value="I prefer tailored outfits", confidence=0.95), update_tasks,
        )
        self.assertEqual(updated["value"], "I prefer tailored outfits")
        self.assertEqual(updated["source"], "desktop")
        self.semantic.upsert_memory_item.assert_not_awaited()

        await create_tasks()
        await update_tasks()
        self.assertEqual(self.semantic.upsert_memory_item.await_count, 2)
        for call in self.semantic.upsert_memory_item.await_args_list:
            self.assertEqual(call.args[0]["value"], "I prefer tailored outfits")

    async def test_duplicate_create_returns_conflict_without_overwriting(self):
        item, _ = await self.create(key="notes.cafe", value="Original memory")
        with self.assertRaises(HTTPException) as error:
            await self.create(key="Notes Café", value="Replacement")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.db.get_memory_item(item["id"])["value"], "Original memory")

    async def test_duplicate_edit_returns_conflict_and_preserves_both_memories(self):
        first, _ = await self.create(key="notes.first", value="First")
        second, _ = await self.create(key="notes.second", value="Second")
        with self.assertRaises(HTTPException) as error:
            await self.main.update_memory_item(
                second["id"], MemoryItemUpdate(key="notes.first", value="Changed"), BackgroundTasks(),
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.db.get_memory_item(first["id"])["value"], "First")
        self.assertEqual(self.db.get_memory_item(second["id"])["value"], "Second")

    async def test_category_change_and_key_change_persist(self):
        item, _ = await self.create()
        result = await self.main.update_memory_item(
            item["id"], MemoryItemUpdate(kind="fashion_preference", key="Style Colors"), BackgroundTasks(),
        )
        self.assertEqual(result["kind"], "fashion_preference")
        self.assertEqual(result["key"], "style.colors")
        self.assertEqual(self.memory.list_items(kind="user_model"), [])
        self.assertEqual(self.memory.list_items(kind="fashion_preference")[0]["id"], item["id"])

    async def test_delete_before_index_does_not_recreate_deleted_memory(self):
        item, create_tasks = await self.create()
        delete_tasks = BackgroundTasks()
        await self.main.delete_memory_item(item["id"], delete_tasks)
        self.assertIsNone(self.db.get_memory_item(item["id"]))
        self.semantic.delete_memory_item.assert_not_awaited()
        await create_tasks()
        await delete_tasks()
        self.semantic.upsert_memory_item.assert_not_awaited()
        self.assertEqual(self.semantic.delete_memory_item.await_count, 2)

    async def test_deleted_key_can_be_reused_without_losing_internal_upsert_behavior(self):
        item, _ = await self.create()
        self.db.delete_memory_item(item["id"])
        restored, _ = await self.create(value="Restored")
        self.assertEqual(restored["id"], item["id"])
        self.assertIsNone(restored["deleted_at"])
        overwritten = self.memory.create_item(kind="user_model", key="notes.style", value="Internal update")
        self.assertEqual(overwritten["value"], "Internal update")
        with self.assertRaises(MemoryConflictError):
            self.memory.create_item(kind="user_model", key="notes.style", value="Manual duplicate", overwrite=False)

    async def test_index_unavailable_does_not_undo_saved_memory(self):
        self.semantic.upsert_memory_item.side_effect = SemanticMemoryError("Ollama unavailable")
        item, tasks = await self.create()
        await tasks()
        self.assertEqual(self.db.get_memory_item(item["id"])["value"], "I prefer relaxed outfits")

    async def test_invalid_or_missing_memory_returns_actionable_error(self):
        with self.assertRaises(HTTPException) as blank:
            await self.create(value="   ")
        self.assertEqual(blank.exception.status_code, 400)
        with self.assertRaises(HTTPException) as missing:
            await self.main.update_memory_item(9999, MemoryItemUpdate(value="Changed"), BackgroundTasks())
        self.assertEqual(missing.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
