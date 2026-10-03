# Google Gemini

Mina can connect directly to the Gemini API through Google's OpenAI-compatible endpoint. It reuses the existing `openai` clients for text and vision, so the desktop provider selector still displays `OpenAI`.

## Direct Google Configuration

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey). Replace the corresponding entries in the root `.env`:

```dotenv
MINA_LLM_PROVIDER=openai
MINA_OPENAI_API_KEY=your_google_api_key
MINA_OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
MINA_OPENAI_MODEL=gemini-3.8-flash
```

For image analysis and comparison, also configure:

```dotenv
MINA_VISION_PROVIDER=openai
MINA_OPENAI_VISION_MODEL=gemini-3.8-flash
```

Text and vision share the configured API key and base URL. Use a model available to your Google account. This configuration replaces the OpenAI connection; it does not add a separate Google provider.

Keep one definition per variable. Mina's `.env` loader uses the first definition and does not override variables already present in the process environment. Restart the backend after changing configuration; if Electron started it, close Mina and run `npm run dev` again from `desktop/`.

## OpenRouter Alternative

To keep the OpenAI connection available, use the separate `openrouter` provider with an OpenRouter API key:

```dotenv
MINA_LLM_PROVIDER=openrouter
MINA_OPENROUTER_API_KEY=your_openrouter_api_key
MINA_OPENROUTER_MODEL=google/gemini-2.5-flash
MINA_OPENROUTER_MODELS=google/gemini-2.5-flash
MINA_VISION_PROVIDER=openrouter
MINA_OPENROUTER_VISION_MODEL=google/gemini-2.5-flash
MINA_OPENROUTER_VISION_MODELS=google/gemini-2.5-flash
```

Check the [OpenRouter model page](https://openrouter.ai/google/gemini-2.5-flash) for availability. Google and OpenRouter API keys are not interchangeable.

## Compatibility and Troubleshooting

Google supports chat completions, streaming, and image inputs through its [OpenAI compatibility API](https://ai.google.dev/gemini-api/docs/openai).

Mina omits `store` when calling `generativelanguage.googleapis.com`, because Google rejects that parameter. Other providers retain `store=false`.

When a streaming request fails, Mina reads the error body before closing the HTTP response. The WebSocket can then deliver the provider's error to the chat and accept another request.

If a request fails, use the reported error to check the API key, model availability, quota, or request settings. A provider being marked available in the desktop UI indicates that a key is configured; it does not confirm that a request has succeeded.
