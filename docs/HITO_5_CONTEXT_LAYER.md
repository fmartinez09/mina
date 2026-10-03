# Milestone 5 - Shared Context Layer + Personal Knowledge Layer MVP

Status: initial implementation complete.

## Goal

Have Mina build structured context before calling the LLM.

Milestone 5 does not aim for full semantic memory or autonomous learning. It moves Mina from responding with only `system_prompt + recent messages` to responding with:

```text
intent + user_model + project_model + episodic_events + relationship_signals + recent messages
```

## Principles

- SQLite remains the primary source of truth.
- Qdrant is outside this milestone's scope.
- Memory must be inspectable and editable.
- Mina must not invent memories and present them as facts.
- Each memory item must have a type, confidence, source, and date.
- The user must be able to delete or correct memory.

## Explicit Corrections and Style Personalization

Manually saved user notes are included in chat tool context and the dedicated outfit planner, alongside the structured profile. Direct identity declarations in English or Spanish can correct an older gender profile field even when saved under an automatically generated memory key. The latest explicit declaration wins by update time; reading the profile does not rewrite or delete the original memories. Editing or deleting that note recomputes the effective profile.

Current identity and recent user-authored preferences receive reserved space in the chat context budget. Older profile conflicts, previous assistant suggestions, and image-derived guesses must not override an explicit correction. Gender identity and clothing preferences remain separate: a romantic aesthetic does not imply womenswear, and a request for men's clothing is respected independently of gender identity. Reference images do not establish wardrobe ownership.

## New Components

### `intent.py`

Initially classifies incoming messages using simple rules.

Initial types:

- `general_chat`
- `personal_context`
- `project_context`
- `memory_query`
- `task_or_next_action`
- `voice_or_tts`

The first version does not need a separate model. Keyword and pattern rules are sufficient.

### `memory.py`

Structured memory service.

Responsibilities:

- create memory items;
- list memory items by type;
- update memory items;
- delete memory items;
- retrieve context for a message;
- record episodic events.

Initial types:

- `user_model`
- `project_model`
- `episodic_event`
- `relationship_signal`
- `personality_profile`
- `self_model`
- `fashion_preference`
- `wardrobe_model`
- `style_reference`
- `media_memory`

### `context.py`

Builds the context passed to the LLM.

Responsibilities:

- receive `session_id`, the normalized message, and the intent;
- retrieve relevant structured memory;
- retrieve recent messages;
- return a final message list for the LLM provider.

## Proposed Data Model

Keep the existing tables:

- `sessions`
- `messages`
- `user_facts`
- `assistant_events`
- `audio_outputs`

Add a general table for typed memory:

```sql
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
```

`value` can contain serialized JSON to support flexible models without migrating tables for every change.

## Endpoints

```text
GET    /api/context
GET    /api/memory/items
POST   /api/memory/items
PATCH  /api/memory/items/{id}
DELETE /api/memory/items/{id}
GET    /api/projects
POST   /api/projects
```

Acceptable first version:

- `GET /api/memory/items`
- `POST /api/memory/items`
- `DELETE /api/memory/items/{id}`
- `GET /api/context?session_id=...`

## Orchestrator Changes

Before:

```text
system_prompt + recent_messages -> LLM
```

After:

```text
normalized_user_message
  -> IntentClassifier
  -> ContextBuilder
  -> LLM
```

`ContextBuilder` must include a system block similar to:

```text
Relevant personal context:
- user_model.preferences.communication: thoughtful, direct
- fashion_preference.silhouettes: likes relaxed korean casual silhouettes
- wardrobe_model.items.black.wide.leg.pants: owns black wide-leg pants
- relationship_signal.preferred_tone: warm, direct, lightly playful

Use this context only when relevant. Do not claim certainty beyond the confidence of the memory item.
```

## Saving Flow

During this milestone, Mina must not learn aggressively. Memory should be saved through:

- explicit user actions;
- clear conversational events, such as marking something as important;
- conservative rules, such as detecting "remember that...".

Example:

```text
User: Remember that I prefer minimalist outfits with loose silhouettes.
MemoryService:
  kind=fashion_preference
  key=fashion.preferences.outfits.minimalist.loose.silhouettes
  value="I prefer minimalist outfits with loose silhouettes"
  confidence=0.95
  source=message
```

## Implementation Steps

1. Extend `SQLiteStore` with `memory_items`.
2. Add Pydantic schemas for memory and context.
3. Create `MemoryService`.
4. Create `IntentClassifier`.
5. Create `ContextBuilder`.
6. Modify `AssistantOrchestrator._build_messages`.
7. Add memory/context endpoints.
8. Add basic desktop controls for viewing memory.
9. Add tests for persistence, retrieval, and the constructed prompt.

## Expected Tests

- Create a `user_model` memory item.
- Confirm it is listed through the API.
- Send a question that needs personal context.
- Confirm that the constructed prompt includes the memory item.
- Delete the memory item.
- Confirm it is no longer included in the prompt.

## Out of Scope

- Qdrant.
- Embeddings.
- Automatic daily summaries.
- External automations.
- Large-scale preference inference.
- Non-editable memory.
