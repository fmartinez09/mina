# Architecture - Mina Assistant

## Goal

Create a local personal assistant for a single user, with chat, voice output, persistent memory, a stable personality, personal fashion/style support, and controlled reflection on conversations.

The current goal is not for Mina to write code or manage external workflows. Mina should first become a persistent cognitive companion that:

- understands the user's personal context;
- remembers preferences, fashion tastes, wardrobe, and conversational style;
- maintains a core personality and a model of itself;
- distinguishes confirmed memories from tentative observations;
- reviews conversations and proposes memory items;
- allows memory approval, editing, and deletion;
- responds through text and, when requested, voice.

## Main Decision

Keep the Python backend as the system's core and use Electron as the desktop shell. Memory, context, LLM providers, TTS, and persistence logic live in FastAPI/Python.

```text
Electron Desktop / CLI
      |
      | HTTP + WebSocket
      v
FastAPI backend
      |
      +-- Orchestrator
      |     +-- Intent Classifier
      |     +-- Context Builder
      |     +-- Personal Knowledge Layer
      |
      +-- LLM service       -> local Ollama, OpenAI, Anthropic, OpenRouter
      +-- TTS service       -> Orpheus, ElevenLabs, Windows SAPI
      +-- Profile service   -> confirmed profile as structured memory
      +-- Wardrobe service  -> editable clothing inventory
      +-- Media service     -> local wardrobe and reference images
      +-- Vision service    -> local Ollama Vision, OpenAI Vision, or OpenRouter multimodal
      +-- Web search        -> DuckDuckGo HTML or Brave Search
      +-- Reflection engine -> memory candidates for review
      +-- Semantic memory   -> optional Qdrant
      +-- System service    -> diagnostics, backups, logs
      |
      +-- SQLite            -> sessions, messages, audio, memory, reflections, wardrobe, images
```

Electron must not become the core. It is the rich interface for using the local backend.

## Components

### Orchestrator

Responsible for coordinating conversational behavior:

- receives text input;
- requests context from `ContextBuilder`;
- calls the LLM;
- saves the conversation;
- decides whether to respond with text, voice, or both;
- emits events over WebSocket.

Main endpoints:

```text
POST /api/chat
WS   /ws/chat
GET  /api/sessions
GET  /api/sessions/{session_id}/messages
```

### Personality

Personality lives in three layers.

#### Core Personality

Mina's stable identity. It changes little and must survive changes to the LLM.

Memory type: `personality_profile`.

Examples:

- traits: curious, warm, honest, intelligent;
- values: truth, loyalty, kindness, growth;
- boundaries: do not invent memories or pretend to be certain.

#### Adaptive Personality

Interaction preferences that can evolve with approval:

- tone;
- humor;
- formality;
- initiative;
- response depth;
- conversational style.

Memory type: `relationship_signal`.

#### Self Model

How Mina understands its own role:

- role: cognitive companion;
- purpose: help with continuity, judgment, and memory;
- strengths: synthesis, memory, conversation, organization;
- limitations: does not experience reality directly.

Memory type: `self_model`.

The core personality lives in `MINA_SYSTEM_PROMPT`, with a default in `config.py`.

Current prompt rules:

- Mina speaks the user's language by default.
- It is warm, direct, curious, helpful, and concise.
- It maintains a calm, pragmatic, attentive, honest, and slightly playful personality.
- It does not invent memories or preferences.
- It uses saved memory only when relevant.

### Shared Context Layer

Before calling the model, Mina builds a prompt with:

- core personality;
- relevant structured memory;
- relevant semantic memory, if Qdrant is available;
- recent session messages.

Components:

- `IntentClassifier`;
- `ContextBuilder`;
- `MemoryService`;
- `SemanticMemoryService`.

### Personal Knowledge Layer

Stable memory is stored in SQLite as `memory_items`.

Types:

- `user_model`: identity, preferences, tastes, and stable user information;
- `project_model`: personal or active projects;
- `episodic_event`: relevant events;
- `relationship_signal`: tone, style, and conversational dynamics;
- `personality_profile`: Mina's traits, values, and core personality;
- `self_model`: Mina's role, purpose, strengths, and limitations;
- `fashion_preference`: fashion tastes, perfumes, silhouettes, colors, and aesthetics;
- `wardrobe_model`: clothing, accessories, and perfumes the user owns;
- `style_reference`: reference brands, designers, celebrities, or moodboards;
- `media_memory`: observations derived from images or media.

Memory is more than chat history. It is an editable representation that can be reviewed.

### Fashion Assistant

Mina should be able to discuss fashion and style in the main chat.

Examples:

- "What outfit can I put together with this jacket?"
- "Do these pants fit my style?"
- "Which perfume suits this look?"
- "Remember that I like Korean casual silhouettes."

The `fashion_context` intent retrieves:

- wardrobe;
- fashion preferences;
- visual references;
- visual observations saved as `media_memory`;
- relevant conversational style.

Actual image ingestion already exists in `MediaService`. Visual analysis runs through `VisionService` and can save `media_memory` items so Mina can reuse observations about clothing, colors, materials, silhouettes, and references.

### Media and Vision

`MediaService` stores local files in `MINA_MEDIA_DIR` and metadata in `wardrobe_images`.

Endpoints:

```text
GET    /api/wardrobe/images
POST   /api/wardrobe/images
PATCH  /api/wardrobe/images/{image_id}
DELETE /api/wardrobe/images/{image_id}
```

`VisionService` analyzes uploaded images.

Providers:

- `ollama`: local vision models such as Qwen2.5-VL/Qwen3-VL;
- `openai`: external vision with `MINA_OPENAI_API_KEY`;
- `openrouter`: external multimodal models with `MINA_OPENROUTER_API_KEY`.

Endpoints:

```text
POST /api/vision/analyze
POST /api/vision/compare
```

Individual analysis results are saved in `wardrobe_images.analysis`. Both individual analysis and comparisons can be synchronized as `media_memory`.

Vision prompts include a language rule for multimodal models that tend to respond in Chinese:

```text
Language rule: answer only in Spanish or English. Prefer Spanish when the user's prompt is Spanish or unclear. Never answer in Chinese.
```

### Web Search

`WebSearchService` searches for external references from `Wardrobe`.

Endpoint:

```text
POST /api/web/search
```

Providers:

- `duckduckgo`: fallback without an API key;
- `brave`: structured API with `MINA_BRAVE_SEARCH_API_KEY`.

Web results are not automatically saved as memory.

### Style Assistant

`StyleAssistantService` combines existing providers for fashion tasks:

- `LLMService` for reasoning and writing;
- `WebSearchService` for external sources;
- `ProfileService` for confirmed personal context;
- `SQLiteStore` for wardrobe data and analyzed images;
- `VisionService` through extraction endpoints.

Endpoints:

```text
POST /api/style/research
POST /api/style/outfit-plan
POST /api/wardrobe/images/{image_id}/extract
```

Responsibilities:

- create briefs with numbered citations from web results;
- plan outfits using the profile, wardrobe, visual notes, and external sources;
- turn JSON visual analysis into `wardrobe_items` drafts;
- let the UI save a draft as an actual item and link the original image.

Image extraction includes a strong language rule because some multimodal models respond in Chinese by default. If the model does not return valid JSON, Mina creates an editable draft with raw notes.

### Chat-First Tool Context

`ChatToolService` is the first layer of conversational orchestration.

The goal is for the user to access these capabilities without opening `Wardrobe`, `Web research`, or `Outfit planner`.

Flow:

1. The user writes in chat.
2. `AssistantOrchestrator` saves the message.
3. `ChatToolService` decides whether it needs style, wardrobe, web, product, price, or planning context.
4. The context is injected into the turn's system prompt.
5. The LLM responds in chat with sources, visible cards, a plan, and a next action.
6. If Mina proposes saving something, the orchestrator creates a `pending_action`.
7. A conversational confirmation such as "yes, save it" applies the pending action to stable memory.

Current tools:

- confirmed profile;
- relevant wardrobe;
- automatic web search for questions that call for it;
- `product_search` to search for actual products;
- `get_prices` to search for visible prices, stock, or availability;
- `build_outfit` to combine candidate wardrobe items and generate complete outfits from chat;
- `style_profile_questionnaire` to request personal style information only when it is missing;
- `preference_candidate` to propose memories such as style preferences or perfume notes.

Tool contexts are recorded for observability:

```text
assistant_events.event_type = chat_tool_context
```

Pending actions are stored in SQLite:

```text
pending_actions.action_type = save_memory
pending_actions.status = pending | applied | cancelled
```

Policy:

- Mina can propose saving memory, clothing, or a plan.
- Mina must not save stable state without explicit user confirmation.
- Mina must not invent prices, stores, or stock; it can only use information visible in the results.
- For outfits, Mina should first combine items the user owns and suggest missing pieces only when they add value.
- Mina must not use generic AI disclaimers about lacking a sense of smell, taste, a body, or personal experience.
- If the user asks which option it likes better, Mina should choose one using curatorial judgment and explain why.
- The UI must show `tool_status` and `tool_result` inside the message as visible activity, with cards and rendered Markdown tables.
- The profile questionnaire should appear when useful, rather than permanently: it is offered for incomplete profiles and broad questions, and its answers are then saved as stable memory.

### Reflection Engine

Mina can review a conversation and propose memory items.

Flow:

1. The user talks with Mina.
2. In `Memory`, the user runs reflection on the current session.
3. Mina proposes candidates with evidence, rationale, and confidence.
4. The user approves or rejects them.
5. Only approved items become stable memory.

### Voice

Voice output is implemented through `TTSService`.

Providers:

- Orpheus-compatible server;
- ElevenLabs;
- Windows SAPI.

Voice input is not yet implemented. Local STT is the next recommended milestone.

### System Service

Provides operational observability:

- system diagnostics;
- SQLite record counts;
- safe backups;
- log listing and tail reading.

## Persistence

SQLite stores:

- sessions;
- messages;
- generated audio;
- internal events;
- pending actions;
- structured memory;
- reflection candidates;
- structured wardrobe;
- wardrobe images and visual analysis.

Qdrant is optional and is only used as an auxiliary semantic index. It does not replace SQLite.

## Desktop

The desktop app has five main views:

- `Chat`: main conversation, streaming, and voice output.
- `Profile`: confirmed user information for fit, preferences, context, and privacy.
- `Wardrobe`: editable inventory of clothing, accessories, perfumes, and makeup, plus the gallery and visual analysis.
- `Memory`: editable memory, projects, reflection, context preview, and semantic search.
- `System`: diagnostics, backups, and logs.

## Currently Out of Scope

Mina does not operate external workflows or external tools. These capabilities are not part of the current focus.

## Next Recommended Milestone

Search and visual comparison:

- connect web search with chat as citable context;
- compare uploaded images with external references;
- extract clothing items from full outfit photos;
- generate actual thumbnails;
- make suggestions combining the profile, wardrobe, visual memory, and external results.

External capabilities must remain explicit and reviewable. Mina must not save new preferences or stable visual conclusions without approval or a clear user action.
