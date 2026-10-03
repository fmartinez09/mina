# Milestone 13 - Vision Service

## Goal

Let Mina analyze uploaded images to understand clothing, colors, materials, silhouettes, references, and possible outfit combinations.

## Implemented Features

- Configuration:
  - `MINA_VISION_PROVIDER`;
  - `MINA_OLLAMA_VISION_MODEL`;
  - `MINA_OPENAI_VISION_MODEL`;
  - `MINA_OPENROUTER_VISION_MODEL`;
  - `MINA_VISION_MAX_IMAGE_BYTES`.
- `VisionService` with providers:
  - `ollama` for local models such as Qwen2.5-VL/Qwen3-VL;
  - `openai` for external vision with an API key;
  - `openrouter` for external multimodal models.
- Provider status in `/api/health`.
- Endpoint:
  - `POST /api/vision/analyze`.
- Visual analysis saved in `wardrobe_images.analysis`.
- Optional creation of `media_memory` from the analysis result.
- Optional semantic indexing of visual memory when Qdrant is enabled.
- UI in `Wardrobe` to:
  - choose a vision provider;
  - adjust the model;
  - enter an optional prompt;
  - analyze individual images;
  - read the analysis as rendered Markdown.

## Default Prompt

If the user does not provide a prompt, Mina uses one focused on fashion:

- what is visible;
- clothing or product attributes;
- colors, materials, silhouette, and pattern;
- styling suggestions;
- uncertainties.

The prompt avoids claiming that the user owns the clothing unless the image is associated with a wardrobe item.

## Providers

### Ollama

Uses `/api/chat` with `images` in the message. The vision model must be downloaded in Ollama.

Example:

```powershell
ollama pull qwen2.5vl:7b
```

If Mina reports that the provider is not ready, check:

- that Ollama is running;
- that `MINA_OLLAMA_VISION_MODEL` exactly matches a model in `ollama list`;
- that the model supports vision.

### OpenAI

Uses `MINA_OPENAI_API_KEY` and sends the image as a data URL to the compatible chat completions endpoint.

### OpenRouter

Uses `MINA_OPENROUTER_API_KEY` and the `https://openrouter.ai/api/v1/chat/completions` endpoint.

Configuration examples for `.env`:

```dotenv
MINA_VISION_PROVIDER=openrouter
MINA_OPENROUTER_VISION_MODEL=xiaomi/mimo-v2.5
MINA_OPENROUTER_VISION_MODELS=xiaomi/mimo-v2.5
```

For text:

```dotenv
MINA_LLM_PROVIDER=openrouter
MINA_OPENROUTER_MODEL=openai/gpt-oss-120b:free
MINA_OPENROUTER_MODELS=openai/gpt-oss-120b:free,xiaomi/mimo-v2.5
```

## Current Limitations

- No automatic comparison across multiple images.
- No visual web search.
- No automatic clothing extraction from a full outfit photo.
- Analysis runs manually for each image.

## Next Step

Recommended milestone 14: web search and visual comparison so Mina can bring in external references, compare clothing, and suggest purchases or combinations with more context.
