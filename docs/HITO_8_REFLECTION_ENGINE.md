# Milestone 8 - Reflection Engine

Status: initial implementation complete.

## Goal

Let Mina learn from conversations without silently writing memory.

The flow is:

```text
chat transcript -> ReflectionService -> reflection_candidates pending
pending candidate -> approve -> memory_items -> optional Qdrant index
pending candidate -> reject  -> archived as rejected
```

SQLite remains the primary source of truth.

## New Table

```text
reflection_candidates
```

Stores proposals inferred from conversations:

- `kind`;
- `key`;
- `value`;
- `confidence`;
- `rationale`;
- `evidence`;
- `source_message_ids`;
- `status`: `pending`, `approved`, or `rejected`;
- `memory_item_id`, when the proposal has been approved.

## Backend

New module:

```text
mina_assistant/app/reflection.py
```

Responsibilities:

- read recent messages from a session;
- ask the LLM for memory candidates in JSON;
- normalize type, key, value, and confidence;
- discard duplicate candidates or those below the threshold;
- save pending candidates;
- approve candidates by converting them into `memory_items`;
- reject candidates without deleting their records.

## Variables

```text
MINA_REFLECTION_ENABLED=true
MINA_REFLECTION_RECENT_MESSAGE_LIMIT=24
MINA_REFLECTION_MAX_CANDIDATES=8
MINA_REFLECTION_MIN_CONFIDENCE=0.55
```

When run from the UI, the engine uses the provider/model selected in the desktop app.

## Endpoints

```text
GET   /api/reflections/candidates
POST  /api/reflections/run
PATCH /api/reflections/candidates/{candidate_id}
POST  /api/reflections/candidates/{candidate_id}/approve
POST  /api/reflections/candidates/{candidate_id}/reject
```

Quick usage:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/reflections/run `
  -Body '{"session_id":"sess_x","provider":"openai","model":"gpt-5.5","limit":24}'

Invoke-RestMethod http://127.0.0.1:8000/api/reflections/candidates

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/reflections/candidates/1/approve
```

## Desktop

The `Memory & context` view includes:

- a queue of pending candidates;
- a `Reflect` button for the current session;
- candidate approval;
- candidate rejection;
- a pending candidate count in the header.

Approval creates or updates structured memory. If Qdrant is available, the approved memory item is also indexed semantically.

## Out of Scope

- Automatic overnight reflection.
- Daily summaries.
- Advanced privacy policies.
- Intelligent merging of contradictory memories.
- Bulk approval.
- Learning without human review.

These items are deferred to the next iteration of learning memory.
