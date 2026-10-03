# Milestone 7 - Semantic Memory with Qdrant

Status: initial implementation complete.

## Goal

Add meaning-based search over Mina's memory without replacing SQLite as the primary source of truth.

SQLite continues to store:

- sessions;
- messages;
- structured memory items;
- projects;
- events;
- audio.

Qdrant stores vectors for retrieving memory items by semantic similarity.

## Services

Qdrant runs as an auxiliary service:

```powershell
docker compose -f docker-compose.qdrant.yml up -d
```

Local endpoint:

```text
http://127.0.0.1:6333
```

Persistent data:

```text
data/qdrant
```

## Variables

```text
MINA_SEMANTIC_MEMORY_ENABLED=true
MINA_QDRANT_BASE_URL=http://127.0.0.1:6333
MINA_QDRANT_COLLECTION=mina_memory
MINA_QDRANT_VECTOR_SIZE=768
MINA_QDRANT_TIMEOUT_SECONDS=8
MINA_OLLAMA_EMBED_MODEL=nomic-embed-text:latest
```

`MINA_QDRANT_VECTOR_SIZE=768` corresponds to `nomic-embed-text`.

## Backend

New module:

```text
mina_assistant/app/semantic.py
```

Responsibilities:

- create embeddings with Ollama;
- create the Qdrant collection if it does not exist;
- index `memory_items`;
- search for memory items by similarity;
- degrade gracefully without breaking the app if Qdrant is unavailable.

## Endpoints

```text
GET  /api/semantic/status
POST /api/semantic/index
GET  /api/semantic/search?q=...
```

Quick usage:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/semantic/status

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/semantic/index

Invoke-RestMethod `
  "http://127.0.0.1:8000/api/semantic/search?q=fashion%20preferences"
```

## Context Integration

`ContextBuilder` now combines:

- structured memory by type and intent;
- semantic results from Qdrant, if available;
- recent messages.

If Qdrant does not respond, Mina continues to work with structured memory.

## Desktop

The `Memory & context` view includes:

- semantic memory status;
- an `Index` button;
- semantic search;
- scored results;
- a context preview with `semantic_items`.

## Out of Scope

- Indexing external documents.
- Automatic summaries.
- File chunks.
- Advanced hybrid search.
- Approval of inferred memories.

These are deferred to milestone 8 and future tool/document milestones.
