# Milestone 6 - Desktop Memory and Projects Panel

Status: initial implementation complete.

## Goal

Make Mina's memory visible, editable, and correctable from the desktop app.

## Implemented Scope

- Main `Memory & context` view in Electron.
- `Memory` navigation in the sidebar.
- Filters for:
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
- Complete list of memory items.
- Memory editor with:
  - type;
  - key;
  - value;
  - confidence;
  - saving through `PATCH /api/memory/items/{id}`;
  - deletion through `DELETE /api/memory/items/{id}`.
- Project creation from the desktop app using `POST /api/projects`.
- List of active projects.
- Context preview using `GET /api/context`.
- The compact memory panel in the sidebar remains available for quick access.

## API Contracts Used

```text
GET    /api/memory/items
POST   /api/memory/items
PATCH  /api/memory/items/{id}
DELETE /api/memory/items/{id}
GET    /api/context
GET    /api/projects
POST   /api/projects
```

## Result

### Editing Improvements

- New memories can be saved without entering a technical key; the desktop app generates a stable key automatically.
- The editor highlights the selected memory, focuses its content, and shows save progress and inline success/error messages.
- Failed saves preserve the draft. Field limits and normalized key conflicts are validated before submission.
- Creating a memory with an existing category/key returns a conflict instead of silently replacing it. Renaming an item to an occupied key also returns a clear conflict.
- Saved and deleted items update the visible list immediately. Category filters follow saved edits, and profile/context views are refreshed after changes.
- SQLite persistence completes before optional semantic indexing. Background indexing reads the latest saved state and serializes updates so queued edits or deletions do not leave stale indexed values.

Mina no longer stores memory as a black box. The user can view, create, correct, and delete memory from the desktop app before moving on to semantic memory.

## Out of Scope

- Qdrant.
- Embeddings.
- Semantic search.
- Automatic reflection.
- Granular approval of inferred memories.

These are deferred to milestones 7 and 8.
