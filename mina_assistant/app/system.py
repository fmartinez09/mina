from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mina_assistant.app.config import PROJECT_ROOT, Settings
from mina_assistant.app.db import SQLiteStore


@dataclass(frozen=True)
class SystemLogFile:
    name: str
    path: str
    size_bytes: int
    modified_at: str | None


@dataclass(frozen=True)
class SystemLogTail:
    name: str
    content: str
    lines: int
    truncated: bool


@dataclass(frozen=True)
class SystemBackup:
    path: str
    size_bytes: int
    created_at: str


class SystemService:
    def __init__(self, *, settings: Settings, db: SQLiteStore):
        self.settings = settings
        self.db = db

    def status(self) -> dict[str, Any]:
        database_exists = self.settings.database_path.exists()
        return {
            "app": self.settings.app_name,
            "project_root": str(PROJECT_ROOT),
            "data_dir": str(self.settings.data_dir),
            "database_path": str(self.settings.database_path),
            "database_exists": database_exists,
            "database_size_bytes": _file_size(self.settings.database_path) if database_exists else 0,
            "audio_dir": str(self.settings.audio_dir),
            "media_dir": str(self.settings.media_dir),
            "backups_dir": str(self.backups_dir),
            "logs_dir": str(self.logs_dir),
            "counts": self.db.table_counts(),
            "configured": {
                "llm_provider": self.settings.llm_provider,
                "ollama_base_url": self.settings.ollama_base_url,
                "ollama_chat_model": self.settings.ollama_chat_model,
                "ollama_embed_model": self.settings.ollama_embed_model,
                "openrouter_chat_model": self.settings.openrouter_chat_model,
                "tts_provider": self.settings.tts_provider,
                "semantic_memory_enabled": self.settings.semantic_memory_enabled,
                "qdrant_base_url": self.settings.qdrant_base_url,
                "qdrant_collection": self.settings.qdrant_collection,
                "reflection_enabled": self.settings.reflection_enabled,
                "vision_provider": self.settings.vision_provider,
                "ollama_vision_model": self.settings.ollama_vision_model,
                "openai_vision_model": self.settings.openai_vision_model,
                "openrouter_vision_model": self.settings.openrouter_vision_model,
                "web_search_provider": self.settings.web_search_provider,
                "brave_search_configured": bool(self.settings.brave_search_api_key),
            },
        }

    def create_backup(self) -> SystemBackup:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.backups_dir / f"assistant-{stamp}.sqlite"
        self.db.backup_to(target)
        return SystemBackup(
            path=str(target),
            size_bytes=_file_size(target),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def list_logs(self) -> list[SystemLogFile]:
        logs: list[SystemLogFile] = []
        for root_label, root in self._log_roots():
            if not root.exists():
                continue
            for path in sorted(root.glob("*")):
                if not path.is_file() or path.suffix.lower() not in {".log", ".err"}:
                    continue
                stat = path.stat()
                logs.append(
                    SystemLogFile(
                        name=f"{root_label}/{path.name}",
                        path=str(path),
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    )
                )
        return sorted(logs, key=lambda item: (item.name.endswith(".err"), item.name), reverse=False)

    def tail_log(self, name: str, *, max_lines: int = 200, max_bytes: int = 120_000) -> SystemLogTail:
        log = self._find_log(name)
        if log is None:
            raise FileNotFoundError(f"Log not found: {name}")

        path = Path(log.path)
        content, truncated = _tail_text(path, max_lines=max_lines, max_bytes=max_bytes)
        lines = len(content.splitlines()) if content else 0
        return SystemLogTail(name=log.name, content=content, lines=lines, truncated=truncated)

    @property
    def backups_dir(self) -> Path:
        return self.settings.data_dir / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.settings.data_dir / "logs"

    def _log_roots(self) -> list[tuple[str, Path]]:
        return [
            ("logs", self.logs_dir),
            ("data", self.settings.data_dir),
            ("desktop", PROJECT_ROOT / "desktop"),
        ]

    def _find_log(self, name: str) -> SystemLogFile | None:
        normalized = name.replace("\\", "/").strip("/")
        for log in self.list_logs():
            if log.name == normalized:
                return log
        return None


def _tail_text(path: Path, *, max_lines: int, max_bytes: int) -> tuple[str, bool]:
    size = path.stat().st_size
    truncated = size > max_bytes
    with path.open("rb") as file:
        if truncated:
            file.seek(max(0, size - max_bytes))
        data = file.read()

    text = data.decode("utf-8", errors="replace")
    if truncated:
        first_newline = text.find("\n")
        if first_newline >= 0:
            text = text[first_newline + 1 :]
    lines = text.splitlines()
    if len(lines) > max_lines:
        truncated = True
        lines = lines[-max_lines:]
    return "\n".join(lines), truncated


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
