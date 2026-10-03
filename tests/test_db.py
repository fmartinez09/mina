from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mina_assistant.app.db import SQLiteStore


class SQLiteStoreTest(unittest.TestCase):
    def test_session_and_messages_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()

            session_id = db.ensure_session(title="Primera conversacion")
            user_id = db.add_message(session_id, "user", "Hola")
            assistant_id = db.add_message(session_id, "assistant", "Hola, soy Mina", tokens=4)

            self.assertGreater(user_id, 0)
            self.assertGreater(assistant_id, user_id)

            messages = db.list_messages(session_id)
            self.assertEqual([row["role"] for row in messages], ["user", "assistant"])
            self.assertEqual(messages[1]["tokens"], 4)

            sessions = db.list_sessions()
            self.assertEqual(sessions[0]["id"], session_id)
            self.assertEqual(sessions[0]["message_count"], 2)

    def test_delete_session_removes_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()

            session_id = db.ensure_session(title="Delete me")
            db.add_message(session_id, "user", "Hola")
            db.add_message(session_id, "assistant", "Hola")

            self.assertTrue(db.delete_session(session_id))
            self.assertFalse(db.session_exists(session_id))
            self.assertEqual(db.list_messages(session_id), [])

    def test_audio_output_is_joined_to_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()

            session_id = db.ensure_session(title="Audio")
            message_id = db.add_message(session_id, "assistant", "Hola", model="fake")
            audio_id = db.add_audio_output(
                message_id=message_id,
                audio_id="tts_test.wav",
                audio_url="/audio/tts_test.wav",
                provider="windows_sapi",
                voice="Test Voice",
            )

            self.assertGreater(audio_id, 0)
            messages = db.list_messages(session_id)
            self.assertEqual(messages[0]["audio_url"], "/audio/tts_test.wav")
            self.assertEqual(messages[0]["audio_provider"], "windows_sapi")
            self.assertEqual(messages[0]["audio_voice"], "Test Voice")

    def test_memory_items_can_be_upserted_listed_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()

            item = db.upsert_memory_item(
                kind="user_model",
                key="preferences.communication",
                value="Prefiere respuestas tecnicas",
                confidence=0.9,
                source="test",
            )
            self.assertGreater(item["id"], 0)

            updated = db.upsert_memory_item(
                kind="user_model",
                key="preferences.communication",
                value="Prefiere respuestas tecnicas y detalladas",
                confidence=0.95,
                source="test",
            )
            self.assertEqual(updated["id"], item["id"])
            self.assertEqual(updated["value"], "Prefiere respuestas tecnicas y detalladas")

            items = db.list_memory_items(kind="user_model")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["confidence"], 0.95)

            self.assertTrue(db.delete_memory_item(item["id"]))
            self.assertEqual(db.list_memory_items(kind="user_model"), [])

    def test_reflection_candidates_can_be_created_listed_and_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteStore(Path(tmpdir) / "assistant.sqlite")
            db.initialize()

            session_id = db.ensure_session(title="Reflection")
            message_id = db.add_message(session_id, "user", "I prefer thoughtful concise answers")
            candidate = db.create_reflection_candidate(
                session_id=session_id,
                kind="user_model",
                key="preferences.communication",
                value="The user prefers thoughtful concise answers.",
                confidence=0.88,
                rationale="Stable communication preference.",
                evidence="I prefer thoughtful concise answers",
                source_message_ids=[message_id],
            )

            self.assertGreater(candidate["id"], 0)
            self.assertEqual(candidate["source_message_ids"], [message_id])

            pending = db.list_reflection_candidates(status="pending")
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["key"], "preferences.communication")

            reviewed = db.review_reflection_candidate(candidate["id"], status="rejected")
            self.assertIsNotNone(reviewed)
            self.assertEqual(reviewed["status"], "rejected")
            self.assertEqual(db.list_reflection_candidates(status="pending"), [])


if __name__ == "__main__":
    unittest.main()
