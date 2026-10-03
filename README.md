# Mina Assistant

Mina is a local personal assistant for a single user, with chat, voice output, editable memory, controlled reflection, and a focus on personal continuity, personality, and fashion/style.

The project direction is defined in [ARCHITECTURE.md](ARCHITECTURE.md).

## Current Capabilities

The current implementation provides a personal assistant that:

- converses through text with streaming;
- can respond with voice;
- remembers stable user information, fashion preferences, wardrobe, and conversational style;
- allows editing a concise, confirmed profile;
- allows creating and editing an actual wardrobe inventory;
- allows uploading, viewing, analyzing, and deleting wardrobe images;
- maintains a core personality and an editable model of how it should respond;
- builds context before calling the LLM;
- can review chats and propose memory items;
- only saves stable memory when the user approves;
- allows inspecting, editing, and deleting memory from the desktop app.

## Demo

Chat-based outfit recommendations using the saved profile and wardrobe:

![Mina recommending outfits based on the user profile and leather jacket](docs/Screenshot%202026-10-03%20195727.png)

<details>
<summary>More screenshots: chat tools, memory, wardrobe, and research</summary>

### Chat tools

Profile and wardrobe context are gathered before building an outfit suggestion.

![Mina chat showing profile lookup, wardrobe context, and outfit builder cards](docs/Screenshot%202026-10-03%20195657.png)

### Memory and context

Create or edit memories, review reflection proposals, and inspect context and optional semantic memory.

![Mina memory editor with reflection, projects, context preview, and semantic memory panels](docs/Screenshot%202026-10-03%20195745.png)

### Wardrobe and image gallery

Manage saved clothing and upload images for visual analysis or item extraction.

![Mina wardrobe inventory and image gallery with analysis and extraction controls](docs/Screenshot%202026-10-03%20195758.png)

### Extraction, research, and outfit planning

Review an extracted garment draft and access the web research and outfit planner panels.

![Mina garment extraction draft above the web research and outfit planner panels](docs/Screenshot%202026-10-03%20195807.png)

</details>

## Core Decisions

- Backend: Python + FastAPI.
- Main UI: Electron + React + TypeScript.
- LLM: local Ollama, OpenAI, Anthropic, OpenRouter, or Google Gemini through the OpenAI-compatible client.
- Primary memory: SQLite.
- Optional semantic memory: Qdrant.
- TTS: Orpheus-compatible server, ElevenLabs, or Windows SAPI.
- Vision: local Ollama, OpenAI, Google Gemini through the OpenAI-compatible client, or multimodal OpenRouter.
- Desktop: Electron as the shell; logic lives in the backend.

## Architecture Overview

```text
Electron Desktop / CLI
      |
      | HTTP + WebSocket
      v
FastAPI backend
      |
      +-- Orchestrator
      +-- Intent Classifier
      +-- Context Builder
      +-- Personal Knowledge Layer
      |     +-- User Model
      |     +-- Episodic Memory
      |     +-- Relationship Model
      |     +-- Personality Profile
      |     +-- Self Model
      |     +-- Fashion Preferences
      |     +-- Wardrobe Model
      |     +-- Style References
      |
      +-- LLM providers     -> Ollama, OpenAI/Gemini, Anthropic, OpenRouter
      +-- TTS service       -> Orpheus, ElevenLabs, Windows SAPI
      +-- Profile service   -> confirmed profile
      +-- Wardrobe service  -> clothing inventory
      +-- Media service     -> local wardrobe images
      +-- Vision service    -> Ollama, OpenAI/Gemini, OpenRouter
      +-- Reflection Engine -> memory candidates for approval
      +-- System service    -> diagnostics, backups, logs
      |
      +-- SQLite            -> sessions, messages, audio, memory, reflections, wardrobe, images
      +-- Optional Qdrant   -> semantic memory search
```

## Local Installation

Requires Python 3.11 or later. The desktop app also requires Node.js and npm.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

Optionally copy `.env.example` to `.env` and adjust the model:

```powershell
copy .env.example .env
```

Main variables:

- `MINA_SYSTEM_PROMPT`: Mina's core personality.
- `MINA_LLM_PROVIDER`: default text provider: `ollama`, `openai`, `anthropic`, or `openrouter`.
- `MINA_OLLAMA_BASE_URL`: local Ollama URL.
- `MINA_OLLAMA_MODEL`: chat model.
- `MINA_OPENAI_API_KEY`: OpenAI API key. Also accepts `OPENAI_API_KEY`.
- `MINA_OPENAI_MODEL`: default OpenAI model.
- `MINA_OPENROUTER_API_KEY`: OpenRouter API key. Also accepts `OPENROUTER_API_KEY`.
- `MINA_OPENROUTER_MODEL`: default OpenRouter text model.
- `MINA_OPENROUTER_MODELS`: comma-separated list for the desktop selector.
- `MINA_OPENROUTER_VISION_MODEL`: default OpenRouter vision model.
- `MINA_OPENROUTER_VISION_MODELS`: comma-separated list of multimodal models.
- `MINA_ANTHROPIC_API_KEY`: Anthropic API key. Also accepts `ANTHROPIC_API_KEY`.
- `MINA_ANTHROPIC_MODEL`: default Anthropic model.
- `MINA_DATABASE_PATH`: local SQLite path.
- `MINA_AUDIO_DIR`: directory for generated audio.
- `MINA_MEDIA_DIR`: directory for local images.
- `MINA_TTS_PROVIDER`: TTS provider: `orpheus`, `elevenlabs`, or `windows_sapi`.
- `MINA_TTS_VOICE`: TTS voice.
- `MINA_ORPHEUS_BASE_URL`: Orpheus-compatible server URL.
- `MINA_ELEVENLABS_API_KEY`: ElevenLabs API key. Also accepts `ELEVENLABS_API_KEY`.
- `MINA_VISION_PROVIDER`: default vision provider: `ollama`, `openai`, or `openrouter`.
- `MINA_OLLAMA_VISION_MODEL`: local vision model.
- `MINA_OPENAI_VISION_MODEL`: OpenAI vision model.
- `MINA_VISION_MAX_IMAGE_BYTES`: maximum image size for upload/analysis.
- `MINA_WEB_SEARCH_PROVIDER`: search provider: `duckduckgo` or `brave`.
- `MINA_BRAVE_SEARCH_API_KEY`: optional Brave Search API key.
- `MINA_WEB_SEARCH_MAX_RESULTS`: maximum number of web results.
- `MINA_REFLECTION_ENABLED`: enables the Reflection Engine.
- `MINA_SEMANTIC_MEMORY_ENABLED`: enables Qdrant as auxiliary semantic memory.

## CLI Usage

For direct Google Gemini configuration or access through OpenRouter, see [docs/GOOGLE_GEMINI.md](docs/GOOGLE_GEMINI.md).

A direct question:

```powershell
.venv\Scripts\mina-assistant "Hello, respond in one sentence."
```

Using a cloud provider:

```powershell
.venv\Scripts\mina-assistant --provider openai --model gpt-5.5 "Answer in one sentence."
.venv\Scripts\mina-assistant --provider anthropic --model claude-opus-4-1-20250805 "Answer in one sentence."
```

Interactive mode:

```powershell
.venv\Scripts\mina-assistant --interactive
```

## API Usage

Start the server:

```powershell
.venv\Scripts\python -m mina_assistant.app.main
```

Open the legacy web UI:

```text
http://127.0.0.1:8000
```

## Desktop Usage

Install desktop dependencies once, then start the app:

```powershell
cd desktop
npm install
npm run dev
```

Electron opens the desktop window and starts the Python backend if it is not already running. Vite serves the renderer at `http://127.0.0.1:5174`, and the backend runs at `http://127.0.0.1:8000`.

The desktop app provides:

- `Chat`: main conversation, streaming, and voice output.
- `Profile`: confirmed user profile.
- `Wardrobe`: inventory, image gallery, and visual analysis.
- `Memory`: memory items, projects, context preview, semantic search, and reflection.
- `System`: diagnostics, backups, and logs.

See [desktop/README.md](desktop/README.md) for desktop development and packaging details.

## Next Steps

See [Project status and horizon](docs/STATUS.md) for remaining work and the next stage.
