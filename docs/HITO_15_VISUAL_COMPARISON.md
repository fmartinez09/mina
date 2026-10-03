# Milestone 15 - Visual Comparison

## Goal

Let Mina compare multiple uploaded images and use that comparison to suggest combinations, clothing compatibility, and style decisions.

## Implemented Features

- `POST /api/vision/compare` endpoint.
- Comparison of 2 to 6 images.
- Support for providers:
  - `ollama`;
  - `openai`;
  - `openrouter`.
- UI in `Wardrobe`:
  - `Compare` selector for each image;
  - `Compare selected` button;
  - Markdown result displayed in the gallery.
- Optional `media_memory` containing the comparison result.

## Language Rule

Vision prompts include a fixed rule:

```text
Language rule: answer only in Spanish or English. Prefer Spanish when the user's prompt is Spanish or unclear. Never answer in Chinese.
```

This matters for models such as Xiaomi MiMo, which may respond in Chinese unless a language is specified.

## Current Limitations

- Comparison uses only images uploaded to Mina.
- Local images are not yet compared with images found on the web.
- Wardrobe items are not automatically created from a full photo.

## Next Step

Combine web search, visual comparison, and wardrobe data for purchase recommendations or similar alternatives.
