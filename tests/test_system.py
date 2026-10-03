from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mina_assistant.app.config import get_settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.system import SystemService


class SystemServiceTest(unittest.TestCase):
    def test_backup_and_log_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = get_settings()
            data_dir = Path(tmpdir)
            db = SQLiteStore(data_dir / "assistant.sqlite")
            db.initialize()
            session_id = db.ensure_session(title="System")
            db.add_message(session_id, "user", "Hola")

            test_settings = settings.__class__(
                **{
                    **settings.__dict__,
                    "data_dir": data_dir,
                    "database_path": data_dir / "assistant.sqlite",
                    "audio_dir": data_dir / "audio",
                }
            )
            service = SystemService(settings=test_settings, db=db)

            backup = service.create_backup()
            self.assertTrue(Path(backup.path).exists())
            self.assertGreater(backup.size_bytes, 0)

            logs_dir = data_dir / "logs"
            logs_dir.mkdir(parents=True)
            (logs_dir / "mina-backend.log").write_text("line 1\nline 2\n", encoding="utf-8")

            logs = service.list_logs()
            self.assertIn("logs/mina-backend.log", {log.name for log in logs})

            tail = service.tail_log("logs/mina-backend.log", max_lines=1)
            self.assertEqual(tail.content, "line 2")
            self.assertEqual(tail.lines, 1)


if __name__ == "__main__":
    unittest.main()
