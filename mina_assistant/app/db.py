from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class MemoryConflictError(ValueError):
    """A memory key is already in use within the requested category."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    started_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ended_at    TEXT,
    summary     TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    tokens      INTEGER,
    model       TEXT
);

CREATE TABLE IF NOT EXISTS assistant_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS pending_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    payload     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'applied', 'cancelled')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    applied_at  TEXT
);

CREATE TABLE IF NOT EXISTS audio_outputs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    audio_id    TEXT NOT NULL,
    audio_url   TEXT NOT NULL,
    provider    TEXT NOT NULL,
    voice       TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS memory_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 0.7,
    source      TEXT,
    source_id   TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    deleted_at  TEXT,
    UNIQUE(kind, key)
);

CREATE TABLE IF NOT EXISTS reflection_candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    kind                TEXT NOT NULL,
    key                 TEXT NOT NULL,
    value               TEXT NOT NULL,
    confidence          REAL NOT NULL DEFAULT 0.6,
    rationale           TEXT,
    evidence            TEXT,
    source              TEXT NOT NULL DEFAULT 'llm',
    source_message_ids  TEXT NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected')),
    memory_item_id      INTEGER REFERENCES memory_items(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    reviewed_at         TEXT
);

CREATE TABLE IF NOT EXISTS wardrobe_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,
    subcategory  TEXT,
    colors       TEXT NOT NULL DEFAULT '[]',
    material     TEXT,
    brand        TEXT,
    size_label   TEXT,
    fit          TEXT,
    season       TEXT,
    occasions    TEXT NOT NULL DEFAULT '[]',
    style_tags   TEXT NOT NULL DEFAULT '[]',
    notes        TEXT,
    favorite     INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
    source       TEXT,
    source_id    TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    deleted_at   TEXT
);

CREATE TABLE IF NOT EXISTS wardrobe_images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id       INTEGER REFERENCES wardrobe_items(id) ON DELETE SET NULL,
    file_path     TEXT NOT NULL,
    thumbnail_path TEXT,
    original_name TEXT,
    mime_type     TEXT,
    width         INTEGER,
    height        INTEGER,
    analysis      TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    deleted_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_session_created
ON messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sessions_updated
ON sessions(updated_at);

CREATE INDEX IF NOT EXISTS idx_audio_outputs_message
ON audio_outputs(message_id, created_at);

CREATE INDEX IF NOT EXISTS idx_pending_actions_session
ON pending_actions(session_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_memory_items_kind_updated
ON memory_items(kind, deleted_at, updated_at);

CREATE INDEX IF NOT EXISTS idx_reflection_candidates_status
ON reflection_candidates(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_reflection_candidates_session
ON reflection_candidates(session_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_wardrobe_items_category_updated
ON wardrobe_items(category, deleted_at, updated_at);

CREATE INDEX IF NOT EXISTS idx_wardrobe_images_item
ON wardrobe_images(item_id, deleted_at, created_at);
"""

class SQLiteStore:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)

    def backup_to(self, target_path: str | Path) -> Path:
        destination = Path(target_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(self.database_path))
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return destination

    def table_counts(self) -> dict[str, int]:
        tables = [
            "sessions",
            "messages",
            "memory_items",
            "reflection_candidates",
            "assistant_events",
            "pending_actions",
            "audio_outputs",
            "wardrobe_items",
            "wardrobe_images",
        ]
        counts: dict[str, int] = {}
        with self._connect() as conn:
            for table in tables:
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                counts[table] = int(row["count"]) if row else 0
        return counts

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_session(self, session_id: str | None = None, title: str | None = None) -> str:
        if session_id and self.session_exists(session_id):
            if title:
                self.set_session_title_if_empty(session_id, title)
            return session_id

        new_session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title)
                VALUES (?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (new_session_id, title),
            )
        return new_session_id

    def session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def set_session_title_if_empty(self, session_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET title = COALESCE(NULLIF(title, ''), ?)
                WHERE id = ?
                """,
                (title, session_id),
            )

    def touch_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (session_id,),
            )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        tokens: int | None = None,
        model: str | None = None,
    ) -> int:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Rol no soportado: {role}")

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (session_id, role, content, tokens, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, tokens, model),
            )
            conn.execute(
                """
                UPDATE sessions
                SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (session_id,),
            )
            return int(cursor.lastrowid)

    def get_recent_messages(self, session_id: str, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, created_at, tokens, model
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [_message_from_row(row) for row in reversed(rows)]

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.id,
                    m.session_id,
                    m.role,
                    m.content,
                    m.created_at,
                    m.tokens,
                    m.model,
                    ao.audio_url,
                    ao.provider AS audio_provider,
                    ao.voice AS audio_voice
                FROM messages m
                LEFT JOIN audio_outputs ao ON ao.id = (
                    SELECT latest_audio.id
                    FROM audio_outputs latest_audio
                    WHERE latest_audio.message_id = m.id
                    ORDER BY latest_audio.created_at DESC, latest_audio.id DESC
                    LIMIT 1
                )
                WHERE m.session_id = ?
                ORDER BY m.created_at, m.id
                """,
                (session_id,),
            ).fetchall()
        return [_message_from_row(row) for row in rows]

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.started_at,
                    s.updated_at,
                    s.ended_at,
                    s.summary,
                    COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC, s.started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def close_session(self, session_id: str, summary: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    summary = COALESCE(?, summary)
                WHERE id = ?
                """,
                (summary, session_id),
            )

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def add_audio_output(
        self,
        *,
        message_id: int,
        audio_id: str,
        audio_url: str,
        provider: str,
        voice: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audio_outputs (message_id, audio_id, audio_url, provider, voice)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, audio_id, audio_url, provider, voice),
            )
            return int(cursor.lastrowid)

    def upsert_memory_item(
        self,
        *,
        kind: str,
        key: str,
        value: str,
        confidence: float,
        source: str | None = None,
        source_id: str | None = None,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO memory_items (kind, key, value, confidence, source, source_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(kind, key) DO UPDATE SET
                    value = excluded.value,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    source_id = excluded.source_id,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    deleted_at = NULL
                WHERE ? OR memory_items.deleted_at IS NOT NULL
                """,
                (kind, key, value, confidence, source, source_id, overwrite),
            )
            if cursor.rowcount == 0:
                raise MemoryConflictError(
                    "A memory with this category and key already exists. Edit it or choose another key."
                )
            row = conn.execute(
                """
                SELECT id, kind, key, value, confidence, source, source_id, created_at, updated_at, deleted_at
                FROM memory_items
                WHERE kind = ? AND key = ?
                """,
                (kind, key),
            ).fetchone()
        return _memory_item_from_row(row)

    def get_memory_item(
        self,
        item_id: int,
        *,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        query = """
            SELECT id, kind, key, value, confidence, source, source_id, created_at, updated_at, deleted_at
            FROM memory_items
            WHERE id = ?
        """
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        with self._connect() as conn:
            row = conn.execute(query, (item_id,)).fetchone()
        return _memory_item_from_row(row) if row else None

    def list_memory_items(
        self,
        *,
        kind: str | None = None,
        kinds: list[str] | None = None,
        keys: list[str] | None = None,
        sources: list[str | None] | None = None,
        include_deleted: bool = False,
        limit: int | None = 100,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if kind:
            where.append("kind = ?")
            params.append(kind)
        for column, values in (("kind", kinds), ("key", keys)):
            if values is not None:
                if not values:
                    return []
                where.append(f"{column} IN ({','.join('?' for _ in values)})")
                params.extend(values)
        if sources is not None:
            if not sources:
                return []
            named_sources = [source for source in sources if source is not None]
            source_conditions = []
            if named_sources:
                source_conditions.append(f"source IN ({','.join('?' for _ in named_sources)})")
                params.extend(named_sources)
            if None in sources:
                source_conditions.append("source IS NULL")
            where.append("(" + " OR ".join(source_conditions) + ")")
        if not include_deleted:
            where.append("deleted_at IS NULL")
        query = """
            SELECT id, kind, key, value, confidence, source, source_id, created_at, updated_at, deleted_at
            FROM memory_items
        """
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_memory_item_from_row(row) for row in rows]

    def update_memory_item(
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
        updates: list[str] = []
        params: list[Any] = []
        for column, next_value in (
            ("kind", kind),
            ("key", key),
            ("value", value),
            ("confidence", confidence),
            ("source", source),
            ("source_id", source_id),
        ):
            if next_value is not None:
                updates.append(f"{column} = ?")
                params.append(next_value)
        if not updates:
            return self.get_memory_item(item_id)

        updates.append("updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')")
        params.append(item_id)
        with self._connect() as conn:
            try:
                conn.execute(
                    f"""
                    UPDATE memory_items
                    SET {", ".join(updates)}
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    params,
                )
            except sqlite3.IntegrityError as exc:
                if exc.sqlite_errorcode != sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                    raise
                raise MemoryConflictError(
                    "A memory with this category and key already exists. Choose another key."
                ) from exc
        return self.get_memory_item(item_id)

    def delete_memory_item(self, item_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE memory_items
                SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ? AND deleted_at IS NULL
                """,
                (item_id,),
            )
        return cursor.rowcount > 0

    def delete_memory_item_by_kind_key(self, *, kind: str, key: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE memory_items
                SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE kind = ? AND key = ? AND deleted_at IS NULL
                """,
                (kind, key),
            )
        return cursor.rowcount > 0

    def delete_memory_items_by_source(self, *, source: str, source_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE memory_items
                SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE source = ? AND source_id = ? AND deleted_at IS NULL
                """,
                (source, source_id),
            )
        return cursor.rowcount

    def create_wardrobe_item(
        self,
        *,
        name: str,
        category: str,
        subcategory: str | None = None,
        colors: list[str] | None = None,
        material: str | None = None,
        brand: str | None = None,
        size_label: str | None = None,
        fit: str | None = None,
        season: str | None = None,
        occasions: list[str] | None = None,
        style_tags: list[str] | None = None,
        notes: str | None = None,
        favorite: bool = False,
        source: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO wardrobe_items (
                    name, category, subcategory, colors, material, brand, size_label,
                    fit, season, occasions, style_tags, notes, favorite, source, source_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    category,
                    subcategory,
                    _dump_json_list(colors),
                    material,
                    brand,
                    size_label,
                    fit,
                    season,
                    _dump_json_list(occasions),
                    _dump_json_list(style_tags),
                    notes,
                    1 if favorite else 0,
                    source,
                    source_id,
                ),
            )
            row = conn.execute(
                _WARDROBE_ITEM_SELECT + " WHERE wi.id = ? GROUP BY wi.id",
                (int(cursor.lastrowid),),
            ).fetchone()
        return _wardrobe_item_from_row(row)

    def get_wardrobe_item(self, item_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
        query = _WARDROBE_ITEM_SELECT + " WHERE wi.id = ?"
        if not include_deleted:
            query += " AND wi.deleted_at IS NULL"
        query += " GROUP BY wi.id"
        with self._connect() as conn:
            row = conn.execute(query, (item_id,)).fetchone()
        return _wardrobe_item_from_row(row) if row else None

    def list_wardrobe_items(
        self,
        *,
        category: str | None = None,
        query: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if category:
            where.append("wi.category = ?")
            params.append(category)
        if query:
            like = f"%{query}%"
            where.append(
                "(wi.name LIKE ? OR wi.category LIKE ? OR wi.subcategory LIKE ? OR wi.brand LIKE ? "
                "OR wi.notes LIKE ? OR wi.colors LIKE ? OR wi.style_tags LIKE ?)"
            )
            params.extend([like, like, like, like, like, like, like])
        if not include_deleted:
            where.append("wi.deleted_at IS NULL")

        sql = _WARDROBE_ITEM_SELECT
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " GROUP BY wi.id ORDER BY wi.favorite DESC, wi.updated_at DESC, wi.id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_wardrobe_item_from_row(row) for row in rows]

    def update_wardrobe_item(self, item_id: int, **fields: Any) -> dict[str, Any] | None:
        column_map = {
            "name": "name",
            "category": "category",
            "subcategory": "subcategory",
            "colors": "colors",
            "material": "material",
            "brand": "brand",
            "size_label": "size_label",
            "fit": "fit",
            "season": "season",
            "occasions": "occasions",
            "style_tags": "style_tags",
            "notes": "notes",
            "favorite": "favorite",
            "source": "source",
            "source_id": "source_id",
        }
        updates: list[str] = []
        params: list[Any] = []
        for key, column in column_map.items():
            if key not in fields:
                continue
            value = fields[key]
            if key in {"colors", "occasions", "style_tags"}:
                value = _dump_json_list(value)
            if key == "favorite":
                value = 1 if value else 0
            updates.append(f"{column} = ?")
            params.append(value)

        if not updates:
            return self.get_wardrobe_item(item_id)

        updates.append("updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')")
        params.append(item_id)
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE wardrobe_items
                SET {", ".join(updates)}
                WHERE id = ? AND deleted_at IS NULL
                """,
                params,
            )
        return self.get_wardrobe_item(item_id)

    def delete_wardrobe_item(self, item_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE wardrobe_items
                SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ? AND deleted_at IS NULL
                """,
                (item_id,),
            )
        return cursor.rowcount > 0

    def create_wardrobe_image(
        self,
        *,
        file_path: str,
        item_id: int | None = None,
        thumbnail_path: str | None = None,
        original_name: str | None = None,
        mime_type: str | None = None,
        width: int | None = None,
        height: int | None = None,
        analysis: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO wardrobe_images (
                    item_id, file_path, thumbnail_path, original_name,
                    mime_type, width, height, analysis
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_id, file_path, thumbnail_path, original_name, mime_type, width, height, analysis),
            )
            row = conn.execute(_WARDROBE_IMAGE_SELECT + " WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
        return _wardrobe_image_from_row(row)

    def get_wardrobe_image(self, image_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
        query = _WARDROBE_IMAGE_SELECT + " WHERE id = ?"
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        with self._connect() as conn:
            row = conn.execute(query, (image_id,)).fetchone()
        return _wardrobe_image_from_row(row) if row else None

    def list_wardrobe_images(
        self,
        *,
        item_id: int | None = None,
        include_deleted: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if item_id is not None:
            where.append("item_id = ?")
            params.append(item_id)
        if not include_deleted:
            where.append("deleted_at IS NULL")

        query = _WARDROBE_IMAGE_SELECT
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_wardrobe_image_from_row(row) for row in rows]

    def update_wardrobe_image(
        self,
        image_id: int,
        *,
        item_id: int | None = None,
        analysis: str | None = None,
    ) -> dict[str, Any] | None:
        updates: list[str] = []
        params: list[Any] = []
        if item_id is not None:
            updates.append("item_id = ?")
            params.append(item_id)
        if analysis is not None:
            updates.append("analysis = ?")
            params.append(analysis)
        if not updates:
            return self.get_wardrobe_image(image_id)

        params.append(image_id)
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE wardrobe_images
                SET {", ".join(updates)}
                WHERE id = ? AND deleted_at IS NULL
                """,
                params,
            )
        return self.get_wardrobe_image(image_id)

    def delete_wardrobe_image(self, image_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE wardrobe_images
                SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ? AND deleted_at IS NULL
                """,
                (image_id,),
            )
        return cursor.rowcount > 0

    def create_reflection_candidate(
        self,
        *,
        kind: str,
        key: str,
        value: str,
        confidence: float,
        session_id: str | None = None,
        rationale: str | None = None,
        evidence: str | None = None,
        source: str = "llm",
        source_message_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reflection_candidates (
                    session_id, kind, key, value, confidence, rationale,
                    evidence, source, source_message_ids
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    kind,
                    key,
                    value,
                    confidence,
                    rationale,
                    evidence,
                    source,
                    json.dumps(source_message_ids or [], separators=(",", ":")),
                ),
            )
            row = conn.execute(_REFLECTION_SELECT + " WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
        return _reflection_candidate_from_row(row)

    def get_reflection_candidate(self, candidate_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(_REFLECTION_SELECT + " WHERE id = ?", (candidate_id,)).fetchone()
        return _reflection_candidate_from_row(row) if row else None

    def list_reflection_candidates(
        self,
        *,
        status: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if session_id:
            where.append("session_id = ?")
            params.append(session_id)
        query = _REFLECTION_SELECT
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_reflection_candidate_from_row(row) for row in rows]

    def update_reflection_candidate(
        self,
        candidate_id: int,
        *,
        kind: str | None = None,
        key: str | None = None,
        value: str | None = None,
        confidence: float | None = None,
        rationale: str | None = None,
        evidence: str | None = None,
    ) -> dict[str, Any] | None:
        updates: list[str] = []
        params: list[Any] = []
        for column, next_value in (
            ("kind", kind),
            ("key", key),
            ("value", value),
            ("confidence", confidence),
            ("rationale", rationale),
            ("evidence", evidence),
        ):
            if next_value is not None:
                updates.append(f"{column} = ?")
                params.append(next_value)
        if not updates:
            return self.get_reflection_candidate(candidate_id)
        updates.append("updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')")
        params.append(candidate_id)
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE reflection_candidates
                SET {", ".join(updates)}
                WHERE id = ? AND status = 'pending'
                """,
                params,
            )
        return self.get_reflection_candidate(candidate_id)

    def review_reflection_candidate(
        self,
        candidate_id: int,
        *,
        status: str,
        memory_item_id: int | None = None,
    ) -> dict[str, Any] | None:
        if status not in {"approved", "rejected"}:
            raise ValueError(f"Estado de candidato no soportado: {status}")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reflection_candidates
                SET status = ?,
                    memory_item_id = COALESCE(?, memory_item_id),
                    reviewed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ? AND status = 'pending'
                """,
                (status, memory_item_id, candidate_id),
            )
        return self.get_reflection_candidate(candidate_id)

    def add_assistant_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> int:
        serialized_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO assistant_events (session_id, event_type, payload)
                VALUES (?, ?, ?)
                """,
                (session_id, event_type, serialized_payload),
            )
            return int(cursor.lastrowid)

    def list_assistant_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, event_type, payload, created_at
                FROM assistant_events
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(str(item.get("payload") or "{}"))
            except json.JSONDecodeError:
                item["payload"] = {}
            events.append(item)
        return events

    def create_pending_action(
        self,
        *,
        session_id: str,
        action_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        serialized_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pending_actions (session_id, action_type, payload)
                VALUES (?, ?, ?)
                """,
                (session_id, action_type, serialized_payload),
            )
            row = conn.execute(
                """
                SELECT id, session_id, action_type, payload, status, created_at, updated_at, applied_at
                FROM pending_actions
                WHERE id = ?
                """,
                (int(cursor.lastrowid),),
            ).fetchone()
        return _pending_action_from_row(row)

    def latest_pending_action(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, session_id, action_type, payload, status, created_at, updated_at, applied_at
                FROM pending_actions
                WHERE session_id = ? AND status = 'pending'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return _pending_action_from_row(row) if row else None

    def resolve_pending_action(
        self,
        action_id: int,
        *,
        status: str,
    ) -> dict[str, Any] | None:
        if status not in {"applied", "cancelled"}:
            raise ValueError(f"Estado de accion pendiente no soportado: {status}")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pending_actions
                SET status = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    applied_at = CASE WHEN ? = 'applied' THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE applied_at END
                WHERE id = ? AND status = 'pending'
                """,
                (status, status, action_id),
            )
            row = conn.execute(
                """
                SELECT id, session_id, action_type, payload, status, created_at, updated_at, applied_at
                FROM pending_actions
                WHERE id = ?
                """,
                (action_id,),
            ).fetchone()
        return _pending_action_from_row(row) if row else None


_REFLECTION_SELECT = """
    SELECT
        id, session_id, kind, key, value, confidence, rationale,
        evidence, source, source_message_ids, status, memory_item_id,
        created_at, updated_at, reviewed_at
    FROM reflection_candidates
"""

_WARDROBE_ITEM_SELECT = """
    SELECT
        wi.id,
        wi.name,
        wi.category,
        wi.subcategory,
        wi.colors,
        wi.material,
        wi.brand,
        wi.size_label,
        wi.fit,
        wi.season,
        wi.occasions,
        wi.style_tags,
        wi.notes,
        wi.favorite,
        wi.source,
        wi.source_id,
        wi.created_at,
        wi.updated_at,
        wi.deleted_at,
        COUNT(wimg.id) AS image_count
    FROM wardrobe_items wi
    LEFT JOIN wardrobe_images wimg ON wimg.item_id = wi.id AND wimg.deleted_at IS NULL
"""

_WARDROBE_IMAGE_SELECT = """
    SELECT
        id,
        item_id,
        file_path,
        thumbnail_path,
        original_name,
        mime_type,
        width,
        height,
        analysis,
        created_at,
        deleted_at
    FROM wardrobe_images
"""


def _pending_action_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["payload"] = json.loads(str(item.get("payload") or "{}"))
    except json.JSONDecodeError:
        item["payload"] = {}
    return item


def _message_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _memory_item_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["confidence"] = float(item["confidence"])
    return item


def _reflection_candidate_from_row(row: sqlite3.Row) -> dict[str, Any]:
    candidate = dict(row)
    raw_message_ids = candidate.get("source_message_ids") or "[]"
    try:
        parsed_message_ids = json.loads(raw_message_ids)
    except json.JSONDecodeError:
        parsed_message_ids = []
    candidate["source_message_ids"] = [
        int(item) for item in parsed_message_ids if isinstance(item, int) or str(item).isdigit()
    ]
    candidate["confidence"] = float(candidate["confidence"])
    return candidate


def _wardrobe_item_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["colors"] = _load_json_list(item.get("colors"))
    item["occasions"] = _load_json_list(item.get("occasions"))
    item["style_tags"] = _load_json_list(item.get("style_tags"))
    item["favorite"] = bool(item.get("favorite"))
    item["image_count"] = int(item.get("image_count") or 0)
    return item


def _wardrobe_image_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _dump_json_list(value: list[str] | None) -> str:
    clean = [str(item).strip() for item in (value or []) if str(item).strip()]
    return json.dumps(clean, ensure_ascii=False, separators=(",", ":"))


def _load_json_list(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]
