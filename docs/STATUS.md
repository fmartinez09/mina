# Project Status

This document tracks implemented milestones and the remaining project horizon. For current capabilities, screenshots, installation, and usage, see the [README](../README.md). The broader design is documented in [ARCHITECTURE.md](../ARCHITECTURE.md).

## Implemented Milestones

### Milestone 1

Text-to-text core:

- SQLite for sessions and messages.
- Ollama client.
- Basic orchestrator.
- Local CLI.
- FastAPI API with HTTP and WebSocket.
- Persistence and orchestration tests.

### Milestone 2

Legacy local web UI:

- Text chat.
- Session list and history.
- Model selector.
- `text | voice | both` output selector.

### Milestone 3

Streaming:

- Streaming from Ollama.
- `/ws/chat` WebSocket.
- Persistence of the final response.

### Milestone 4

Voice output:

- `/api/tts` endpoint.
- `orpheus`, `elevenlabs`, and `windows_sapi` providers.
- Audio files served from `/audio`.
- Audio linked to messages in SQLite.

### Earlier Cloud Milestone

External providers:

- Text: `ollama`, `openai`, `anthropic`.
- API keys read from `.env`.
- Voice: `orpheus`, `elevenlabs`, `windows_sapi`.

### Milestone 4.5

Desktop:

- App in `desktop/` with Electron + React + TypeScript + Vite.
- Desktop UI connected to FastAPI and WebSocket.
- Electron starts the Python backend in development.
- Preload exposes only the local backend URL.

### Milestone 5

Shared Context Layer + Personal Knowledge Layer MVP.

Details: [docs/HITO_5_CONTEXT_LAYER.md](HITO_5_CONTEXT_LAYER.md).

Scope:

- `MemoryService` to read/write structured memory.
- `ContextBuilder` that adds personal context, projects, and recent messages.
- Simple `IntentClassifier`.
- Memory models:
  - `user_model`;
  - `project_model`;
  - `episodic_event`;
  - `relationship_signal`;
  - `personality_profile`;
  - `self_model`;
  - `fashion_preference`;
  - `wardrobe_model`;
  - `style_reference`;
  - `media_memory`.
- Basic memory panel in the desktop app.

### Milestone 6

Desktop panel for context and editable memory.

Details: [docs/HITO_6_MEMORY_PANEL.md](HITO_6_MEMORY_PANEL.md).

Scope:

- dedicated memory view;
- filters by memory type;
- memory editor;
- active projects view;
- preview of the context Mina will send to the LLM.

### Milestone 7

Semantic memory with Qdrant.

Details: [docs/HITO_7_SEMANTIC_MEMORY.md](HITO_7_SEMANTIC_MEMORY.md).

Scope:

- `docker-compose.qdrant.yml`;
- embeddings with Ollama;
- `memory_items` indexing;
- semantic search through the API;
- optional integration in `ContextBuilder`;
- semantic memory status, indexing, and search in the desktop app.

### Milestone 8

Reflection Engine and learning memory with approval.

Details: [docs/HITO_8_REFLECTION_ENGINE.md](HITO_8_REFLECTION_ENGINE.md).

Scope:

- `reflection_candidates` table;
- manual reflection per session;
- pending proposals with evidence, rationale, and confidence;
- approval that creates/updates `memory_items`;
- optional semantic indexing on approval;
- reflection queue in `Memory & context`.

### Milestone 9

Personality, fashion, and style memory.

Details: [docs/HITO_9_PERSONALITY_FASHION.md](HITO_9_PERSONALITY_FASHION.md).

Scope:

- distinct memory types for Mina's personality, self model, fashion preferences, wardrobe, visual references, and media;
- initial classification of messages about fashion, wardrobe, perfumes, tone, and personality;
- `fashion_context` and `personality_context` intents;
- context retrieval tailored to fashion or personality conversations;
- Reflection Engine updated to propose memories in these categories;
- desktop panel updated with filters and an editor for the new types.

### Milestone 10

Confirmed personal profile.

Details: [docs/HITO_10_PROFILE.md](HITO_10_PROFILE.md).

Scope:

- `GET /api/profile` endpoint;
- `PUT /api/profile` endpoint;
- `Profile` view in the desktop app;
- city/climate, height, sizes, fit, colors, style, comfort, budget, and privacy details;
- saved as confirmed `profile.*` memory for Mina to use in context.

### Milestone 11

Actual wardrobe inventory.

Details: [docs/HITO_11_WARDROBE.md](HITO_11_WARDROBE.md).

Scope:

- `wardrobe_items` table;
- `wardrobe_images` table prepared for the visual milestone;
- wardrobe CRUD endpoints;
- `Wardrobe` view in the desktop app;
- synchronization of each clothing item as `wardrobe_model` memory.

### Milestone 12

Image gallery.

Details: [docs/HITO_12_MEDIA_GALLERY.md](HITO_12_MEDIA_GALLERY.md).

Scope:

- `MINA_MEDIA_DIR`;
- local files served from `/media`;
- image `GET`, `POST`, and `DELETE` endpoints;
- uploads from the desktop app;
- optional association with clothing items;
- soft deletion in SQLite and removal of the local file.

### Milestone 13

Visual analysis.

Details: [docs/HITO_13_VISION_SERVICE.md](HITO_13_VISION_SERVICE.md).

Scope:

- `VisionService`;
- local `ollama` provider for Qwen2.5-VL/Qwen3-VL or another compatible model;
- external `openai` provider;
- `openrouter` provider for multimodal models;
- vision status in `/api/health`;
- `POST /api/vision/analyze` endpoint;
- analysis saved with the image;
- optional `media_memory` so Mina can reuse visual observations.

### Milestone 14

Controlled web search.

Details: [docs/HITO_14_WEB_SEARCH.md](HITO_14_WEB_SEARCH.md).

Scope:

- `WebSearchService`;
- `POST /api/web/search` endpoint;
- `duckduckgo` provider without an API key;
- `brave` provider with an optional API key;
- `Web research` panel in `Wardrobe`.

### Milestone 15

Visual comparison.

Details: [docs/HITO_15_VISUAL_COMPARISON.md](HITO_15_VISUAL_COMPARISON.md).

Scope:

- `POST /api/vision/compare` endpoint;
- comparison of 2 to 6 uploaded images;
- `Compare selected` button in the gallery;
- Markdown result;
- optional `media_memory`;
- language rule for models such as Xiaomi MiMo: respond only in Spanish or English, never in Chinese.

### Milestones 16-19

Research, planning, and wardrobe extraction.

Details: [docs/HITO_16_19_STYLE_ASSISTANT.md](HITO_16_19_STYLE_ASSISTANT.md).

Scope:

- `POST /api/style/research` endpoint for briefs with citable sources;
- `POST /api/style/outfit-plan` endpoint for outfits using the profile, wardrobe, vision, and web;
- `POST /api/wardrobe/images/{image_id}/extract` endpoint to turn an image into a clothing item draft;
- `PATCH /api/wardrobe/images/{image_id}` endpoint to link images to items;
- `Brief` button in `Web research`;
- `Outfit planner` subpanel;
- `Extract` button on each image;
- saving the extracted draft as an actual wardrobe item.

### Milestone 20

Chat-first orchestration.

Details: [docs/HITO_20_CHAT_FIRST_ORCHESTRATION.md](HITO_20_CHAT_FIRST_ORCHESTRATION.md).

Scope:

- `ChatToolService`;
- automatic web search from chat when the message calls for it;
- search for actual products from chat;
- search for prices/availability visible in stores when requested;
- `build_outfit` from chat using candidate wardrobe items;
- dynamic style profile questionnaire when context is missing;
- profile and wardrobe context injected into chat;
- citable sources `[1]`, `[2]`;
- internal `chat_tool_context` events;
- `tool_status` and `tool_result` WebSocket events;
- cards for sources, images, products, profile questionnaires, and preference candidates;
- `pending_actions` for applying "yes, save it";
- policy of asking for confirmation before saving memory, wardrobe items, or plans.

## Recent Improvements

- Google Gemini text and vision support through the existing OpenAI-compatible client, plus OpenRouter configuration. See [Google Gemini setup](GOOGLE_GEMINI.md).
- Memory creation with automatic keys, clearer editing feedback, duplicate-key validation, and draft preservation after failed saves. Optional semantic indexing runs after the local save.
- Current user identity and clothing preferences included in chat and outfit planning. Newer explicit corrections take priority over older profile fields and inferred visual context.

## Next Steps and Horizon

The next stage is to complete more actions directly from chat. Remaining work includes:

- attach images from the composer;
- analyze attached images in the same thread;
- save clothing and plans as actual entities from conversational proposals;
- action cards requiring confirmation to save a product, outfit, or clothing item;
- more structured shopping search by store when providers are available;
- local STT for voice input.
